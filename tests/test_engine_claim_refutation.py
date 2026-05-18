"""Tests for PR7 — Claim refutation (MVP).

Invariants of ``register_contradiction`` / ``contradictions_for_claim`` /
``refute_claim_if_ready``.

**35차 (test-first) 상태**: 위 3 메서드는 아직 구현되지 않았다. 따라서 호출
하는 모든 테스트는 ``AttributeError`` 로 fail 한다. **그게 정상.** 36차에서
구현하면 전부 통과로 전환된다.

§19.9 의 14 개 invariant 매핑:
1.  candidate + 0 contradiction → False, candidate 유지       — refute side
2.  candidate + 1+ contradiction → True, REFUTED              — refute side
3.  unresolved gap 만으로 refuted 금지 (§19.2 핵심)          — refute side
4.  resolved gap 도 refute trigger 아님                       — refute side
5.  confirmed → False, 상태 보존                              — refute side
6.  refuted → False, 상태 보존 (idempotent)                  — refute side
7.  unknown claim_id → KeyError (refute)                      — refute side
8.  register_contradiction idempotent (True / False)          — register
9.  cross-claim contradiction 허용                            — register
10. register status 무관 (confirmed/refuted 에도 등록)        — register
11. refute 가 gap_state / base_confidence 무변화 (2 tests)    — isolation
12. contradictions_for_claim asc order                        — query
13. unknown evidence_id → KeyError (register)                 — register
14. 기존 435 회귀 없음 — 전체 통과로 입증 (별도 테스트 없음)

§19.6 결정표 lock (inv 7 의 register-side 쌍):
- unknown claim_id (register) → KeyError                      — register
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_REFUTED,
    Engine,
)


def _candidate_claim(engine: Engine) -> tuple[int, int]:
    """entity + candidate claim helper. PR6 와 동일 패턴."""
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


class TestRefuteClaimIfReady:
    """§19.9 invariants 1~7 — refute_claim_if_ready 의 전이 / no-op / KeyError."""

    # invariant 1
    def test_candidate_with_zero_contradictions_returns_false(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)

        result = engine.refute_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CANDIDATE

    # invariant 2
    def test_candidate_with_contradiction_becomes_refuted(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)

        result = engine.refute_claim_if_ready(claim_id)

        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 3 — PR7 핵심 명제 (§19.2)
    def test_unresolved_gap_alone_does_not_refute(self) -> None:
        """증거 부족 ≠ 반박. unresolved gap 만으로는 refute trigger 아님."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        # 의도적으로 contradiction 등록 안 함

        result = engine.refute_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CANDIDATE

    # invariant 4
    def test_resolved_gap_alone_does_not_refute(self) -> None:
        """resolved gap 도 refute trigger 아님. gap 상태와 refute 는 독립 축."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = _evidence(engine, claim_id, evidence_type=42)
        engine.resolve_gaps_for_evidence(ev)
        # gap 은 resolved, 하지만 contradiction 은 등록 없음

        result = engine.refute_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CANDIDATE

    # invariant 5
    def test_confirmed_claim_is_not_refuted(self) -> None:
        """PR7 범위: confirmed → refuted 금지 (PR8+ 결정)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)
        # white-box: confirmed 상태로 (PR7 에는 다른 경로 없음)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        result = engine.refute_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    # invariant 6
    def test_refuted_reinvocation_is_noop(self) -> None:
        """첫 호출 True, 두 번째 호출 False, 상태 REFUTED 유지."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)

        first = engine.refute_claim_if_ready(claim_id)
        second = engine.refute_claim_if_ready(claim_id)

        assert first is True
        assert second is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 7
    def test_refute_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.refute_claim_if_ready(999)


class TestRegisterContradiction:
    """§19.9 invariants 8~10, 13 + §19.6 결정표 KeyError 쌍."""

    # invariant 8
    def test_first_registration_returns_true_second_returns_false(self) -> None:
        """Idempotent — 같은 (claim_id, evidence_id) 쌍 두 번째 호출은 no-op False."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)

        first = engine.register_contradiction(claim_id, ev)
        second = engine.register_contradiction(claim_id, ev)

        assert first is True
        assert second is False

    # invariant 9 — PR7 의 본질
    def test_cross_claim_contradiction_allowed(self) -> None:
        """evidence.claim_id != target claim_id 케이스가 contradiction 의 본질.

        예: claim_a = "SSH exposed", evidence_b = "Port 22 closed" (claim_b 에 부착).
        evidence_b 가 claim_a 를 반박할 수 있어야 한다.
        """
        engine = Engine()
        _, claim_a = _candidate_claim(engine)
        entity_b = engine.add_entity(entity_type=1)
        claim_b = engine.add_claim(
            subject_id=entity_b, claim_type=1,
            rule_id=2, rule_version=1, reason_code=0,
        )
        ev_b = _evidence(engine, claim_b)  # evidence.claim_id == claim_b

        result = engine.register_contradiction(claim_a, ev_b)

        assert result is True
        # 그리고 refute_if_ready 도 정상 동작 — cross-claim ev 가 trigger
        assert engine.refute_claim_if_ready(claim_a) is True
        assert engine.get_claim(claim_a).status == CLAIM_STATUS_REFUTED

    # invariant 10
    def test_register_on_non_candidate_claim_is_allowed(self) -> None:
        """confirmed / refuted claim 에도 contradiction 등록 가능.

        데이터 등록 (register_contradiction) 과 lifecycle 결정 (refute_if_ready)
        은 분리 — §19.6 결정표.
        """
        engine = Engine()
        _, c_confirmed = _candidate_claim(engine)
        _, c_refuted = _candidate_claim(engine)
        ev = _evidence(engine, c_confirmed)
        engine._claims[c_confirmed] = replace(
            engine._claims[c_confirmed], status=CLAIM_STATUS_CONFIRMED,
        )
        engine._claims[c_refuted] = replace(
            engine._claims[c_refuted], status=CLAIM_STATUS_REFUTED,
        )

        r_conf = engine.register_contradiction(c_confirmed, ev)
        r_ref = engine.register_contradiction(c_refuted, ev)

        assert r_conf is True
        assert r_ref is True

    # invariant 13
    def test_register_unknown_evidence_id_raises_key_error(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        with pytest.raises(KeyError):
            engine.register_contradiction(claim_id, 999)

    # §19.6 결정표 — register-side KeyError on unknown claim_id
    def test_register_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        with pytest.raises(KeyError):
            engine.register_contradiction(999, ev)


class TestContradictionsForClaim:
    """§19.9 invariant 12 — 결정성."""

    # invariant 12
    def test_returns_ascending_order(self) -> None:
        """contradictions_for_claim 은 evidence_id 오름차순 tuple (PR5 패턴)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev1 = _evidence(engine, claim_id)
        ev2 = _evidence(engine, claim_id)
        ev3 = _evidence(engine, claim_id)
        # 의도적으로 등록 순서 뒤섞기
        engine.register_contradiction(claim_id, ev3)
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)

        result = engine.contradictions_for_claim(claim_id)

        assert result == tuple(sorted([ev1, ev2, ev3]))
        assert list(result) == sorted(result)  # 강한 단언


class TestRefutationIsolation:
    """§19.9 invariant 11 (gap state + base_confidence 보존, 2 tests)."""

    # invariant 11a
    def test_refute_does_not_mutate_gap_state(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        gap_id = engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = _evidence(engine, claim_id, evidence_type=42)
        engine.resolve_gaps_for_evidence(ev)
        engine.register_contradiction(claim_id, ev)

        before_resolutions = dict(engine._gap_resolutions)
        before_gap = engine.get_gap(gap_id)
        before_gaps_for_claim = engine.gaps_for_claim(claim_id)

        engine.refute_claim_if_ready(claim_id)

        assert engine._gap_resolutions == before_resolutions
        assert engine.get_gap(gap_id) == before_gap
        assert engine.gaps_for_claim(claim_id) == before_gaps_for_claim
        assert engine.gap_resolution(gap_id) == ev

    # invariant 11b
    def test_refute_does_not_change_base_confidence(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.42,
        )
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)
        before = engine.get_claim(claim_id).base_confidence

        engine.refute_claim_if_ready(claim_id)

        after = engine.get_claim(claim_id).base_confidence
        assert after == before
        assert after.value == pytest.approx(0.42)
