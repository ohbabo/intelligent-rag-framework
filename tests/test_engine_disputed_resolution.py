"""Tests for PR9-A — Disputed resolution (MVP).

Invariants of ``register_contradiction_resolution`` /
``resolved_contradictions_for_claim`` / ``active_contradictions_for_claim`` /
``resolve_disputed_claim_if_ready``.

**43차 (test-first) 상태**: 위 4 메서드 모두 미구현. 따라서 호출하는 테스트는
``AttributeError`` 로 fail — 정상. 44차에서 impl 후 통과로 전환.

§21.11 의 14 invariant + 사용자 분리한 14 케이스 매핑:
1.  register unknown claim_id → KeyError                              — register
2.  register unknown evidence_id → KeyError                           — register
3.  active_contradictions_for_claim unknown claim → KeyError          — query
4.  (pair) 가 _contradictions[claim] 에 미등록 → ValueError ★          — Sub-decision E
5.  첫 register_contradiction_resolution → True                       — register
6.  같은 pair 두 번째 → False (idempotent first-keep)                 — register
7.  resolved/active 둘 다 evidence_id asc tuple                       — query (결정성)
8.  active = contradictions - resolved (차집합)                       — query
9.  resolved 후에도 contradictions_for_claim 에 evidence 포함 (audit) — audit
10. disputed + active 1+ → resolve False, disputed 유지              — transition
11. disputed + active 0 → True, status=CONFIRMED ★                   — transition (핵심)
12. candidate → resolve False                                         — status guard
13. confirmed → resolve False                                         — status guard
14. refuted → resolve False                                           — status guard

추가 (§21.11 inv 11/12/13 잠금 — PR7/PR8 isolation 패턴 일관):
- resolve_disputed_claim_if_ready unknown claim_id → KeyError
- resolved_contradictions_for_claim unknown claim → KeyError (query 보강)
- resolve 전이가 gap state / base_confidence / contradiction list 무변화
- PR8 dispute 가 resolved contradiction 있어도 active 1+ 면 정상 동작

inv 14 (회귀 방지) 는 전체 통과로 입증.
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


def _evidence(engine: Engine, claim_id: int, evidence_type: int = 42) -> int:
    return engine.add_evidence(
        claim_id=claim_id,
        raw_ref_id=0,
        evidence_type=evidence_type,
        strength=0.8,
    )


def _disputed_claim_with_contradiction(engine: Engine) -> tuple[int, int]:
    """disputed Claim + 1 contradiction. PR9 표준 setup.

    PR6/PR7/PR8 의 white-box 패턴: confirmed → dispute_claim_if_ready 로 disputed.
    """
    _, claim_id = _candidate_claim(engine)
    ev = _evidence(engine, claim_id)
    engine.register_contradiction(claim_id, ev)
    engine._claims[claim_id] = replace(
        engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
    )
    engine.dispute_claim_if_ready(claim_id)
    assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED
    return claim_id, ev


class TestRegisterContradictionResolution:
    """§21.11 invariants 1, 2, 3, 4 — register-side: KeyError/ValueError + idempotent."""

    # invariant 1
    def test_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        with pytest.raises(KeyError):
            engine.register_contradiction_resolution(999, ev)

    # invariant 2
    def test_unknown_evidence_id_raises_key_error(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        with pytest.raises(KeyError):
            engine.register_contradiction_resolution(claim_id, 999)

    # invariant 3 ★ — Sub-decision E (relationship-bound)
    def test_unregistered_pair_raises_value_error(self) -> None:
        """둘 다 존재하지만 (claim, evidence) pair 가 contradiction 미등록 → ValueError.

        '둘 다 존재한다는 것만으로 해소 등록이 정당해지지 않는다.
         pair 자체가 contradiction 관계여야 한다.' (§21.2 명제)
        """
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        # ev 는 존재하지만 claim 의 contradiction 으로 등록 안 됨
        with pytest.raises(ValueError):
            engine.register_contradiction_resolution(claim_id, ev)

    # invariant 4
    def test_first_resolution_returns_true(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)

        result = engine.register_contradiction_resolution(claim_id, ev)

        assert result is True

    # invariant 5 — idempotent (PR5 first-keep)
    def test_duplicate_resolution_returns_false(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)
        engine.register_contradiction_resolution(claim_id, ev)

        second = engine.register_contradiction_resolution(claim_id, ev)

        assert second is False


class TestResolvedAndActiveContradictions:
    """§21.11 invariants 5~7 (audit + 차집합 + asc) + KeyError 보강."""

    # invariant — active KeyError
    def test_active_contradictions_unknown_claim_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.active_contradictions_for_claim(999)

    # invariant — resolved KeyError (보강)
    def test_resolved_contradictions_unknown_claim_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.resolved_contradictions_for_claim(999)

    # invariant 5 (audit) ★
    def test_resolved_contradiction_preserved_in_contradictions_for_claim(self) -> None:
        """resolved 등록이 원본 _contradictions 를 삭제하지 않음 (audit 보존).

        '_contradictions 의 원본 entry 는 삭제하지 않는다 (audit 보존)' (§21.6 Notes)
        """
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)

        before = engine.contradictions_for_claim(claim_id)
        engine.register_contradiction_resolution(claim_id, ev)
        after = engine.contradictions_for_claim(claim_id)

        assert ev in after
        assert before == after

    # invariant 6 (차집합) ★
    def test_active_contradictions_excludes_resolved(self) -> None:
        """active = contradictions - resolved (§21.5)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev1 = _evidence(engine, claim_id)
        ev2 = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)
        engine.register_contradiction_resolution(claim_id, ev1)

        assert engine.active_contradictions_for_claim(claim_id) == (ev2,)
        assert engine.resolved_contradictions_for_claim(claim_id) == (ev1,)

    # invariant 7 (asc — 결정성)
    def test_resolved_and_active_return_sorted_tuples(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev1 = _evidence(engine, claim_id)
        ev2 = _evidence(engine, claim_id)
        ev3 = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)
        engine.register_contradiction(claim_id, ev3)
        # 의도적으로 뒤섞은 순서로 resolve
        engine.register_contradiction_resolution(claim_id, ev3)
        engine.register_contradiction_resolution(claim_id, ev1)

        resolved = engine.resolved_contradictions_for_claim(claim_id)
        active = engine.active_contradictions_for_claim(claim_id)
        assert list(resolved) == sorted([ev1, ev3])
        assert list(active) == [ev2]


class TestResolveDisputedClaimIfReady:
    """§21.11 invariants 8~11 — transition + status guard + KeyError."""

    # invariant 8
    def test_disputed_with_active_contradiction_stays_disputed(self) -> None:
        engine = Engine()
        claim_id, _ = _disputed_claim_with_contradiction(engine)
        # 아무 resolve 안 함 → active 1+
        result = engine.resolve_disputed_claim_if_ready(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED

    # invariant 9 ★ — PR9-A 핵심 전이
    def test_disputed_with_all_resolved_becomes_confirmed(self) -> None:
        """disputed + 모든 contradiction resolved → confirmed 복귀."""
        engine = Engine()
        claim_id, ev = _disputed_claim_with_contradiction(engine)
        engine.register_contradiction_resolution(claim_id, ev)
        # active = 0

        result = engine.resolve_disputed_claim_if_ready(claim_id)

        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    # invariant 10 (candidate)
    def test_candidate_is_not_resolved(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        result = engine.resolve_disputed_claim_if_ready(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CANDIDATE

    # invariant 10 (confirmed)
    def test_confirmed_is_not_resolved(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.resolve_disputed_claim_if_ready(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    # invariant 10 (refuted)
    def test_refuted_is_not_resolved(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.resolve_disputed_claim_if_ready(claim_id)
        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 11
    def test_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.resolve_disputed_claim_if_ready(999)


class TestResolveIsolation:
    """§21.11 invariants 12~13 — resolve 가 무관 state 무변화 + PR8 dispute 정합."""

    # invariant 12 (isolation — gap state / base_confidence / contradiction 보존)
    def test_resolve_preserves_other_state(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.42,
        )
        # contradiction + gap 둘 다 추가
        ev_contra = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev_contra)
        gap_id = engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=43,
            severity=0.5, rule_id=1,
        )
        ev_gap = _evidence(engine, claim_id, evidence_type=43)
        engine.resolve_gaps_for_evidence(ev_gap)
        # confirmed → disputed
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        engine.dispute_claim_if_ready(claim_id)
        engine.register_contradiction_resolution(claim_id, ev_contra)

        before_gap_res = dict(engine._gap_resolutions)
        before_contras = engine.contradictions_for_claim(claim_id)
        before_resolved = engine.resolved_contradictions_for_claim(claim_id)
        before_base = engine.get_claim(claim_id).base_confidence
        before_gap = engine.get_gap(gap_id)

        engine.resolve_disputed_claim_if_ready(claim_id)

        # status 만 바뀌고 나머지 state 무변화
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED
        assert engine._gap_resolutions == before_gap_res
        assert engine.contradictions_for_claim(claim_id) == before_contras
        assert engine.resolved_contradictions_for_claim(claim_id) == before_resolved
        assert engine.get_claim(claim_id).base_confidence == before_base
        assert engine.get_gap(gap_id) == before_gap
        assert engine.gap_resolution(gap_id) == ev_gap

    # invariant 13 (PR8 dispute 정합)
    def test_dispute_still_works_with_resolved_but_active_contradiction(self) -> None:
        """resolved contradiction 이 있어도 active 1+ 면 dispute 정상 동작.

        PR8 의미 보존: dispute 는 'active 가 있느냐' 가 아니라 PR7 §19.6 의
        contradictions_for_claim 결과만 본다. 단 PR9 후속에서는 자연스럽게
        active 기준으로 보아야 할 수 있지만, PR9-A 범위에서는 PR8 의미 보존.
        """
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev1 = _evidence(engine, claim_id)
        ev2 = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)
        engine.register_contradiction_resolution(claim_id, ev1)  # ev1 만 resolve
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        result = engine.dispute_claim_if_ready(claim_id)

        # PR8 의 dispute_claim_if_ready 는 _contradictions.get(claim_id) 만 본다.
        # ev1 이 resolved 됐어도 _contradictions[claim_id] 에는 ev1, ev2 둘 다 있음.
        # → 1+ 이므로 dispute True (PR8 의미 그대로 보존)
        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED
