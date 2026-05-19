"""Tests for PR10-A — Disputed refutation (MVP).

Invariants of ``refute_disputed_claim_if_ready`` — Sub-decision F (strength-only)
+ Sub-decision G (private threshold 0.8) 잠금.

**47차 (test-first) 상태**: ``refute_disputed_claim_if_ready`` 미구현. 호출
하는 테스트는 ``AttributeError`` 로 fail — 정상. 48차에서 impl 후 통과로 전환.

§22.11 의 14 invariant 매핑 + 사용자 13 분리:
1.  unknown claim_id → KeyError
2.  candidate → False
3.  confirmed → False
4.  refuted → False
5.  disputed + active 0 → False (active 없음 가드)
6.  disputed + active 1+ 모두 strength < 0.8 → False
7.  disputed + active 강한 evidence (strength >= 0.8) → True, REFUTED ★
8.  Threshold 경계 정확히 0.8 → refute (>= 비교 잠금)
9.  Threshold 직하 0.799999 → refute 안 함
10. Resolved 단독 strength 0.95 → refute 안 함 (active 만 본다) ★
11. active weak + resolved strong → False (resolved 의 strength 무관)
12. active strong + resolved weak → True (active 만 본다)
13. refuted 재호출 idempotent
14. PR9-A resolve 와 mutually exclusive (active 0 vs active 1+ 가드 배타)
15. PR7 refute_claim_if_ready 의 의미 무변화 (strength 안 봄)
16. refute 전이가 gap state / base_confidence / contradiction 무변화
17. _REFUTATION_STRENGTH_THRESHOLD 가 public export 안 됨 (Sub-decision G)

inv 14 (기존 482 회귀) 는 전체 통과로 입증.
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


def _candidate_claim(engine: Engine) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=1,
        rule_version=1,
        reason_code=0,
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


def _disputed_claim_with(
    engine: Engine, contradiction_strengths: list[float],
) -> tuple[int, list[int]]:
    """disputed Claim + 주어진 strength 의 contradiction evidence 들 등록.

    Returns: (claim_id, [evidence_id, ...]) — 등록 순서대로.
    """
    _, claim_id = _candidate_claim(engine)
    evs = []
    for s in contradiction_strengths:
        ev = _evidence(engine, claim_id, strength=s)
        engine.register_contradiction(claim_id, ev)
        evs.append(ev)
    # white-box: confirmed → dispute_claim_if_ready 통해 disputed
    engine._claims[claim_id] = replace(
        engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
    )
    if contradiction_strengths:
        engine.dispute_claim_if_ready(claim_id)
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED
    else:
        # active 0 + disputed 시나리오 — white-box 로 직접 disputed
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
    return claim_id, evs


class TestRefuteDisputedClaimIfReady:
    """§22.11 invariants 1~5, 9 — basic transitions + KeyError + idempotent."""

    # invariant 1
    def test_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.refute_disputed_claim_if_ready(999)

    # invariant 2 (candidate)
    def test_candidate_returns_false(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        result = engine.refute_disputed_claim_if_ready(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CANDIDATE

    # invariant 2 (confirmed)
    def test_confirmed_returns_false(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.refute_disputed_claim_if_ready(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    # invariant 2 (refuted)
    def test_refuted_returns_false(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.refute_disputed_claim_if_ready(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 3 — active 0 + disputed
    def test_disputed_with_no_active_contradictions_returns_false(self) -> None:
        """active 0 인 disputed Claim — refute 가드: 'active 없음' → False.

        PR9-A 의 resolve_disputed_claim_if_ready 가 active 0 면 confirmed 로
        보내는 정상 흐름 외에, white-box 로 만든 disputed+active=0 상태도 안전.
        """
        engine = Engine()
        claim_id, _ = _disputed_claim_with(engine, [])  # active 0
        result = engine.refute_disputed_claim_if_ready(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED

    # invariant 4 — 모두 weak
    def test_disputed_with_all_weak_contradictions_returns_false(self) -> None:
        """모든 active contradiction 의 strength < 0.8 → disputed 유지."""
        engine = Engine()
        claim_id, _ = _disputed_claim_with(engine, [0.3, 0.5, 0.7])
        result = engine.refute_disputed_claim_if_ready(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED

    # invariant 5 ★ — strong 명백 케이스
    def test_disputed_with_strong_contradiction_becomes_refuted(self) -> None:
        """active 중 단 하나라도 strength >= 0.8 → refuted 전이."""
        engine = Engine()
        claim_id, _ = _disputed_claim_with(engine, [0.3, 0.9])
        result = engine.refute_disputed_claim_if_ready(claim_id)
        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 9 — idempotent
    def test_idempotent_after_refute(self) -> None:
        engine = Engine()
        claim_id, _ = _disputed_claim_with(engine, [0.9])
        first = engine.refute_disputed_claim_if_ready(claim_id)
        second = engine.refute_disputed_claim_if_ready(claim_id)
        assert first is True
        assert second is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED


class TestRefutationStrengthThreshold:
    """§22.11 invariants 6, 7 — threshold boundary (Sub-decision F/G 핵심)."""

    # invariant 6 — boundary 정확
    def test_threshold_exactly_at_boundary_refutes(self) -> None:
        """strength == 0.8 (정확히 threshold) → refute (>= 비교)."""
        engine = Engine()
        claim_id, _ = _disputed_claim_with(engine, [0.8])
        result = engine.refute_disputed_claim_if_ready(claim_id)
        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 7 — boundary 직하
    def test_threshold_just_below_does_not_refute(self) -> None:
        """strength == 0.799999 → refute 안 함 (>= 비교, < 0.8)."""
        engine = Engine()
        claim_id, _ = _disputed_claim_with(engine, [0.799999])
        result = engine.refute_disputed_claim_if_ready(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED


class TestResolvedContradictionsIgnored:
    """§22.11 invariant 8 + 보강 — resolved 제외 정책 (PR9-A 정합)."""

    # invariant 8 ★ — resolved 단독 강함
    def test_resolved_strong_contradiction_does_not_trigger_refute(self) -> None:
        """resolved 만 있고 active 없음 → refute 안 함.

        resolved contradiction 의 strength 가 0.95 라도 active = 0 이면 refute
        trigger 안 됨. active 만 본다.
        """
        engine = Engine()
        claim_id, evs = _disputed_claim_with(engine, [0.95])
        engine.register_contradiction_resolution(claim_id, evs[0])
        # 이제 active = 0, resolved = 1 (strength 0.95)

        result = engine.refute_disputed_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED

    # 보강 (사용자 #8)
    def test_active_weak_with_resolved_strong_does_not_refute(self) -> None:
        """active 약함 (0.3) + resolved 강함 (0.95) → refute 안 함."""
        engine = Engine()
        claim_id, evs = _disputed_claim_with(engine, [0.95, 0.3])
        engine.register_contradiction_resolution(claim_id, evs[0])  # strong 만 resolve
        # active = ev[1] (0.3), resolved = ev[0] (0.95)

        result = engine.refute_disputed_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED

    # 보강 (사용자 #9)
    def test_active_strong_with_resolved_weak_refutes(self) -> None:
        """active 강함 (0.9) + resolved 약함 (0.3) → refute."""
        engine = Engine()
        claim_id, evs = _disputed_claim_with(engine, [0.3, 0.9])
        engine.register_contradiction_resolution(claim_id, evs[0])  # weak 만 resolve
        # active = ev[1] (0.9), resolved = ev[0] (0.3)

        result = engine.refute_disputed_claim_if_ready(claim_id)

        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED


class TestCrossAPIConsistency:
    """§22.11 invariants 11~12 — PR9-A resolve 와 배타 + PR7 무변화."""

    # invariant 11
    def test_resolve_and_refute_are_mutually_exclusive(self) -> None:
        """active 0 이면 resolve True / refute False.
        active 1+ 이면 resolve False / refute = (strong evidence 있냐에 의존).
        동시 trigger 불가.
        """
        engine = Engine()

        # case 1: active 0 (모두 resolved)
        claim_a, evs_a = _disputed_claim_with(engine, [0.9])
        engine.register_contradiction_resolution(claim_a, evs_a[0])
        # PR9-A: confirmed 로 가능, PR10-A: active 0 가드로 False
        assert engine.refute_disputed_claim_if_ready(claim_a) is False
        # 상태는 여전히 disputed (resolve 호출 안 함)
        assert engine.get_claim(claim_a).status == CLAIM_STATUS_DISPUTED
        # resolve 호출하면 confirmed
        assert engine.resolve_disputed_claim_if_ready(claim_a) is True
        assert engine.get_claim(claim_a).status == CLAIM_STATUS_CONFIRMED

        # case 2: active 1+ (resolve 가 active 잔존 가드로 False, refute 가능)
        claim_b, _ = _disputed_claim_with(engine, [0.9])
        assert engine.resolve_disputed_claim_if_ready(claim_b) is False
        # 여전히 disputed
        assert engine.get_claim(claim_b).status == CLAIM_STATUS_DISPUTED
        # refute 호출 → REFUTED
        assert engine.refute_disputed_claim_if_ready(claim_b) is True
        assert engine.get_claim(claim_b).status == CLAIM_STATUS_REFUTED

    # invariant 12 — PR7 무변화
    def test_pr7_refute_claim_if_ready_unaffected_by_threshold(self) -> None:
        """PR7 의 refute_claim_if_ready 는 candidate 만 + strength 무관 (개수만).

        PR10-A 의 threshold 정책이 PR7 영역 침범하지 않음을 잠금:
        weak contradiction (strength=0.3) 하나만으로도 PR7 refute 는 True.
        """
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        weak_ev = _evidence(engine, claim_id, strength=0.3)
        engine.register_contradiction(claim_id, weak_ev)
        # candidate + weak contradiction 1개
        # PR7 의 refute_claim_if_ready 는 strength 안 봄 → True
        result = engine.refute_claim_if_ready(claim_id)
        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED


class TestRefutationIsolation:
    """§22.11 invariant 10 — transition 이 다른 state 무변화."""

    def test_refute_preserves_other_state(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.42,
        )
        # contradiction (strong)
        strong_ev = _evidence(engine, claim_id, strength=0.9)
        engine.register_contradiction(claim_id, strong_ev)
        # gap + resolution
        gap_id = engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=43,
            severity=0.5, rule_id=1,
        )
        ev_gap = _evidence(engine, claim_id, evidence_type=43, strength=0.7)
        engine.resolve_gaps_for_evidence(ev_gap)
        # confirmed → disputed
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        engine.dispute_claim_if_ready(claim_id)

        before_gap_res = dict(engine._gap_resolutions)
        before_contras = engine.contradictions_for_claim(claim_id)
        before_resolved = engine.resolved_contradictions_for_claim(claim_id)
        before_base = engine.get_claim(claim_id).base_confidence
        before_gap = engine.get_gap(gap_id)

        engine.refute_disputed_claim_if_ready(claim_id)

        # status 만 바뀜, 나머지 무변화
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED
        assert engine._gap_resolutions == before_gap_res
        assert engine.contradictions_for_claim(claim_id) == before_contras
        assert engine.resolved_contradictions_for_claim(claim_id) == before_resolved
        assert engine.get_claim(claim_id).base_confidence == before_base
        assert engine.get_gap(gap_id) == before_gap


class TestThresholdPrivacy:
    """§22.11 invariant 13 — Sub-decision G (threshold private)."""

    def test_threshold_not_in_ragcore_public_export(self) -> None:
        """REFUTATION_STRENGTH_THRESHOLD 는 ragcore 에 public export 안 됨."""
        import ragcore

        # public 이름으로 노출되면 안 됨
        assert not hasattr(ragcore, "REFUTATION_STRENGTH_THRESHOLD")
        # __all__ 에도 없음
        assert "REFUTATION_STRENGTH_THRESHOLD" not in getattr(ragcore, "__all__", [])
        # private 이름도 ragcore 에 직접 노출 안 됨
        assert not hasattr(ragcore, "_REFUTATION_STRENGTH_THRESHOLD")

    def test_threshold_not_in_types_module(self) -> None:
        """types.py 에도 threshold 상수 없음 (engine 내부 전용)."""
        import ragcore.types

        assert not hasattr(ragcore.types, "REFUTATION_STRENGTH_THRESHOLD")
        assert not hasattr(ragcore.types, "_REFUTATION_STRENGTH_THRESHOLD")
