"""Tests for PR11-B — Freshness-aware disputed refutation (MVP, sibling API).

Invariants of ``refute_disputed_claim_if_ready_by_freshness``.

**67차 (test-first) 상태**: 신규 sibling API 미구현. 호출 테스트는
``AttributeError`` 로 fail. 단, "PR10-A / PR11-C / PR11-A / PR9-A / PR11-D
무변화" 검증과 "threshold 재사용" 검증은 **이미 pass** (PR11-A 59차 / PR11-C
63차 패턴).

§27.12 의 21 invariant 매핑:
1.  unknown claim_id → KeyError                                  [AttrErr fail]
2.  status guard 3 (candidate / confirmed / refuted → False)     [AttrErr fail]
3.  disputed + active 0 → False                                  [AttrErr fail]
4.  disputed + FIRST < 0.8 → False                                [AttrErr fail]
5.  disputed + FIRST >= 0.8 → True, REFUTED ★                    [AttrErr fail]
6.  Threshold boundary 0.8 정확 → True                            [AttrErr fail]
7.  Threshold 직하 0.799999 → False                               [AttrErr fail]
8.  older strong + recent weak → False ★ (Sub-decision Q)         [AttrErr fail]
9.  Resolved contradiction 제외                                    [AttrErr fail]
10. Refuted 재호출 idempotent False                                [AttrErr fail]
11. lifecycle event 기록 (transition label) ★                      [AttrErr fail]
12. PR10-A refute_disputed_claim_if_ready 무변화                   [이미 pass]
13. PR11-C compute_effective_confidence 무변화                     [이미 pass]
14. PR11-A query 무변화                                            [이미 pass]
15. PR9-A asc 무변화                                               [이미 pass]
16. Isolation (gap state / contradictions / base_confidence)       [AttrErr fail]
17. Mutual exclusivity (PR9-A / PR10-A / PR11-B)                   [부분 fail / 부분 pass]
18. _REFUTATION_STRENGTH_THRESHOLD 재사용 (새 상수 없음) —
    Sub-decision R                                                  [이미 pass]
19. 기존 564 회귀 없음 — 전체 통과로 입증
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    Engine,
)


def _candidate_claim(engine: Engine, *, base_confidence: float = 0.8) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=1,
        rule_version=1,
        reason_code=0,
        base_confidence=base_confidence,
    )
    return entity_id, claim_id


def _evidence(
    engine: Engine, claim_id: int, *, evidence_type: int = 42, strength: float = 0.8,
) -> int:
    return engine.add_evidence(
        claim_id=claim_id,
        raw_ref_id=0,
        evidence_type=evidence_type,
        strength=strength,
    )


def _setup_disputed_with(
    engine: Engine, contradictions: list[float],
) -> tuple[int, list[int]]:
    """disputed Claim + 주어진 strength 순서 그대로 contradiction 등록.

    리스트 순서 = evidence 등록 순서 = freshness 정렬 (asc by id, recent=last).
    Returns: (claim_id, [evidence_id, ...]) in 등록 순서.
    """
    _, claim_id = _candidate_claim(engine)
    evs = []
    for s in contradictions:
        ev = _evidence(engine, claim_id, strength=s)
        engine.register_contradiction(claim_id, ev)
        evs.append(ev)
    # confirmed → disputed (PR8 정식 경로)
    engine._claims[claim_id] = replace(
        engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
    )
    if contradictions:
        engine.dispute_claim_if_ready(claim_id)
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED
    else:
        # active 0 + disputed white-box (PR9-A 가 normally confirmed 로 보냄)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
    return claim_id, evs


class TestRefuteDisputedByFreshness:
    """§27.12 invariants 1~7, 10 — basic transitions + threshold + idempotent."""

    # invariant 1
    def test_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.refute_disputed_claim_if_ready_by_freshness(999)

    # invariant 2 (candidate)
    def test_candidate_returns_false(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        result = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CANDIDATE

    # invariant 2 (confirmed)
    def test_confirmed_returns_false(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    # invariant 2 (refuted)
    def test_refuted_returns_false(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 3
    def test_disputed_with_no_active_contradictions_returns_false(self) -> None:
        engine = Engine()
        claim_id, _ = _setup_disputed_with(engine, [])
        result = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED

    # invariant 4
    def test_disputed_with_weak_first_returns_false(self) -> None:
        """FIRST (= 가장 최근) active strength < 0.8 → False."""
        engine = Engine()
        claim_id, _ = _setup_disputed_with(engine, [0.3, 0.5])
        # 등록 순서: ev_1 (s=0.3), ev_2 (s=0.5). FIRST by freshness = ev_2 (recent)
        result = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED

    # invariant 5 ★
    def test_disputed_with_strong_first_becomes_refuted(self) -> None:
        """FIRST active strength >= 0.8 → True, REFUTED."""
        engine = Engine()
        claim_id, _ = _setup_disputed_with(engine, [0.3, 0.9])
        # FIRST = ev_2 (strength=0.9), >= 0.8 → refute
        result = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 6
    def test_threshold_exactly_at_boundary_refutes(self) -> None:
        """FIRST strength == 0.8 정확 → True (`>=` 비교, PR10-A 와 동일)."""
        engine = Engine()
        claim_id, _ = _setup_disputed_with(engine, [0.8])
        result = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 7
    def test_threshold_just_below_does_not_refute(self) -> None:
        """FIRST strength == 0.799999 → False."""
        engine = Engine()
        claim_id, _ = _setup_disputed_with(engine, [0.799999])
        result = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED

    # invariant 10 — idempotent
    def test_idempotent_after_refute(self) -> None:
        engine = Engine()
        claim_id, _ = _setup_disputed_with(engine, [0.9])
        first = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        second = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert first is True
        assert second is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED


class TestSubDecisionQ:
    """§27.12 invariant 8 — older strong + recent weak (PR10-A 와 다름) ★."""

    def test_older_strong_recent_weak_does_not_refute(self) -> None:
        """older active strong (>= 0.8) + recent active weak (< 0.8) → PR11-B False.

        같은 setup 에서 PR10-A 는 True 를 반환 (ANY active >= 0.8 있음).
        PR11-B 는 FIRST 만 보므로 False — 의미 분리 핵심.
        """
        engine = Engine()
        # 등록 순서: ev_1 (s=0.9 older strong), ev_2 (s=0.3 recent weak)
        claim_id, evs = _setup_disputed_with(engine, [0.9, 0.3])

        # FIRST by freshness = ev_2 (s=0.3) → < 0.8 → PR11-B False
        result_b = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert result_b is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED

        # PR10-A 는 ANY 정책 — ev_1 (s=0.9) 가 >= 0.8 → True
        # (같은 setup 으로 PR10-A 호출 시 분리 입증)
        result_a = engine.refute_disputed_claim_if_ready(claim_id)
        assert result_a is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    def test_older_weak_recent_strong_refutes(self) -> None:
        """older weak (< 0.8) + recent strong (>= 0.8) → PR11-B True."""
        engine = Engine()
        # 등록 순서: ev_1 (s=0.3 older weak), ev_2 (s=0.9 recent strong)
        claim_id, _ = _setup_disputed_with(engine, [0.3, 0.9])

        result = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED


class TestResolvedExcluded:
    """§27.12 invariant 9 — resolved 차집합 정합 (PR9-A 의미 보존)."""

    def test_resolved_recent_strong_does_not_trigger_refute(self) -> None:
        """resolved 된 recent strong evidence 는 active 에서 제외, FIRST 변경.

        시나리오:
          ev_1 (s=0.3 older weak, active)
          ev_2 (s=0.9 recent strong) → resolved 후 active 에서 제외

        active_contradictions_by_freshness = (ev_1,) — ev_2 가 제외됨
        FIRST = ev_1 (s=0.3) → False
        """
        engine = Engine()
        claim_id, evs = _setup_disputed_with(engine, [0.3, 0.9])
        # ev_2 (recent strong) 를 resolved
        engine.register_contradiction_resolution(claim_id, evs[1])

        result = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED


class TestLifecycleHistoryIntegration:
    """§27.12 invariants 11, 20 — PR10-B audit 통합 + 신규 transition label."""

    def test_refute_records_lifecycle_event_with_new_label(self) -> None:
        """True 반환 시 lifecycle event 기록, transition == 신규 label."""
        engine = Engine()
        claim_id, _ = _setup_disputed_with(engine, [0.9])

        # dispute_claim_if_ready 호출 시 이미 1 event 기록 (CONFIRMED → DISPUTED)
        before_history = engine.claim_lifecycle_history(claim_id)
        before_seqs = [e.seq for e in before_history]

        engine.refute_disputed_claim_if_ready_by_freshness(claim_id)

        after_history = engine.claim_lifecycle_history(claim_id)
        # 정확히 1 event 추가됨
        assert len(after_history) == len(before_history) + 1
        new_event = after_history[-1]
        # PR11-B 신규 transition label
        assert new_event.transition == "refute_disputed_by_freshness_if_ready"
        assert new_event.from_status == CLAIM_STATUS_DISPUTED
        assert new_event.to_status == CLAIM_STATUS_REFUTED
        # seq 는 strictly increasing
        if before_seqs:
            assert new_event.seq > max(before_seqs)

    def test_no_event_recorded_on_false_return(self) -> None:
        """False (no-op) 반환 시 lifecycle event 기록 없음 (PR10-B Sub-decision J)."""
        engine = Engine()
        claim_id, _ = _setup_disputed_with(engine, [0.3])  # weak → False

        before_history = engine.claim_lifecycle_history(claim_id)

        result = engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
        assert result is False

        after_history = engine.claim_lifecycle_history(claim_id)
        # event 추가 없음
        assert after_history == before_history

    def test_label_distinct_from_pr10a(self) -> None:
        """PR10-A label 과 PR11-B label 이 다른 string 임을 명시 잠금."""
        engine = Engine()
        # PR11-B path
        claim_b, _ = _setup_disputed_with(engine, [0.9])
        engine.refute_disputed_claim_if_ready_by_freshness(claim_b)
        history_b = engine.claim_lifecycle_history(claim_b)

        # PR10-A path
        claim_a, _ = _setup_disputed_with(engine, [0.9])
        engine.refute_disputed_claim_if_ready(claim_a)
        history_a = engine.claim_lifecycle_history(claim_a)

        # 두 path 의 마지막 transition label 이 다름
        assert history_b[-1].transition == "refute_disputed_by_freshness_if_ready"
        assert history_a[-1].transition == "refute_disputed_if_ready"
        assert history_b[-1].transition != history_a[-1].transition


class TestPriorPolicyUnchanged:
    """§27.12 invariants 12, 13, 14, 15 — PR10-A / PR11-C / PR11-A / PR9-A 무변화 (이미 pass)."""

    # invariant 12 — PR10-A refute 무변화
    def test_pr10a_refute_disputed_unchanged(self) -> None:
        """PR10-A: ANY active >= 0.8 정책 그대로."""
        engine = Engine()
        # older strong + recent weak → PR10-A True (ANY)
        claim_id, _ = _setup_disputed_with(engine, [0.9, 0.3])
        result = engine.refute_disputed_claim_if_ready(claim_id)
        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 13 — PR11-C effective 무변화
    def test_pr11c_effective_confidence_unchanged(self) -> None:
        """PR11-C: base × status × freshness_modifier 그대로."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        ev = _evidence(engine, claim_id, strength=0.8)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        # PR11-C: 1.0 × 0.5 × (1.0 - 0.8 × 0.5) = 1.0 × 0.5 × 0.6 = 0.3
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.3)

    # invariant 14 — PR11-A 무변화
    def test_pr11a_queries_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_a = _evidence(engine, claim_id, strength=0.3)
        ev_b = _evidence(engine, claim_id, strength=0.9)
        engine.register_contradiction(claim_id, ev_a)
        engine.register_contradiction(claim_id, ev_b)

        # PR11-A desc
        assert engine.active_contradictions_by_freshness(claim_id) == (ev_b, ev_a)
        # primitive
        assert engine.evidence_freshness(ev_b) == ev_b

    # invariant 15 — PR9-A asc 무변화
    def test_pr9a_active_contradictions_asc_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_a = _evidence(engine, claim_id)
        ev_b = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev_b)
        engine.register_contradiction(claim_id, ev_a)
        # PR9-A asc: evidence_id asc
        assert engine.active_contradictions_for_claim(claim_id) == (ev_a, ev_b)


class TestMutualExclusivity:
    """§27.12 invariant 17 — PR9-A / PR10-A / PR11-B trigger 의 mutually exclusive."""

    def test_active_zero_resolve_true_both_refutes_false(self) -> None:
        """active 0 + disputed: PR9-A True, PR10-A False, PR11-B False."""
        engine = Engine()
        claim_id, _ = _setup_disputed_with(engine, [])  # white-box active 0 disputed

        # PR10-A: active 없음 → False
        assert engine.refute_disputed_claim_if_ready(claim_id) is False
        # PR11-B: active 없음 → False
        assert engine.refute_disputed_claim_if_ready_by_freshness(claim_id) is False
        # PR9-A: active 0 → True (status DISPUTED + active 0)
        assert engine.resolve_disputed_claim_if_ready(claim_id) is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    def test_active_strong_first_weak_pr10a_true_pr11b_false(self) -> None:
        """older strong + recent weak:
        PR9-A False, PR10-A True, PR11-B False.

        (이미 TestSubDecisionQ.test_older_strong_recent_weak_does_not_refute
         에서 separately 검증되지만 mutual exclusivity 묶음에서도 명시.)
        """
        engine = Engine()
        claim_id, _ = _setup_disputed_with(engine, [0.9, 0.3])

        # PR11-B 먼저 — FIRST=0.3 → False
        assert engine.refute_disputed_claim_if_ready_by_freshness(claim_id) is False
        # PR9-A — active 잔존 → False
        assert engine.resolve_disputed_claim_if_ready(claim_id) is False
        # PR10-A — ANY 0.9 → True
        assert engine.refute_disputed_claim_if_ready(claim_id) is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED


class TestRefutationIsolation:
    """§27.12 invariant 16 — transition 이 다른 state 무변화."""

    def test_refute_preserves_other_state(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.42,
        )
        # strong contradiction
        ev = _evidence(engine, claim_id, strength=0.9)
        engine.register_contradiction(claim_id, ev)
        # gap + resolve (다른 영역)
        gap_id = engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=43,
            severity=0.5, rule_id=1,
        )
        ev_gap = _evidence(engine, claim_id, evidence_type=43, strength=0.7)
        engine.resolve_gaps_for_evidence(ev_gap)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        engine.dispute_claim_if_ready(claim_id)

        before_gap_res = dict(engine._gap_resolutions)
        before_contras = engine.contradictions_for_claim(claim_id)
        before_resolved = engine.resolved_contradictions_for_claim(claim_id)
        before_base = engine.get_claim(claim_id).base_confidence
        before_gap = engine.get_gap(gap_id)

        engine.refute_disputed_claim_if_ready_by_freshness(claim_id)

        # status 만 바뀜, 나머지 무변화
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED
        assert engine._gap_resolutions == before_gap_res
        assert engine.contradictions_for_claim(claim_id) == before_contras
        assert engine.resolved_contradictions_for_claim(claim_id) == before_resolved
        assert engine.get_claim(claim_id).base_confidence == before_base
        assert engine.get_gap(gap_id) == before_gap


class TestThresholdReuse:
    """§27.12 invariant 18 — Sub-decision R (새 threshold 상수 없음)."""

    def test_no_new_threshold_constant_in_public(self) -> None:
        """새 freshness refute 전용 threshold constant 가 public 에 노출 안 됨."""
        import ragcore

        names = [
            "_FRESHNESS_REFUTE_THRESHOLD",
            "FRESHNESS_REFUTE_THRESHOLD",
            "_FRESHNESS_REFUTATION_THRESHOLD",
            "FRESHNESS_REFUTATION_THRESHOLD",
        ]
        for n in names:
            assert not hasattr(ragcore, n), f"ragcore should not expose {n}"
            assert n not in getattr(ragcore, "__all__", []), (
                f"__all__ should not include {n}"
            )

    def test_no_new_threshold_constant_in_types(self) -> None:
        import ragcore.types

        names = [
            "_FRESHNESS_REFUTE_THRESHOLD",
            "FRESHNESS_REFUTE_THRESHOLD",
            "_FRESHNESS_REFUTATION_THRESHOLD",
            "FRESHNESS_REFUTATION_THRESHOLD",
        ]
        for n in names:
            assert not hasattr(ragcore.types, n), (
                f"ragcore.types should not expose {n}"
            )
