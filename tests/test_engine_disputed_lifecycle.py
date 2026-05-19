"""Tests for PR8 — Disputed claim lifecycle (MVP).

Invariants of ``dispute_claim_if_ready`` + ``CLAIM_STATUS_DISPUTED``
constant + Sub-decision D (YAML rule output 거부).

**39차 (test-first) 상태**: ``CLAIM_STATUS_DISPUTED`` 상수와
``dispute_claim_if_ready`` 메서드 모두 미존재. 따라서 호출/접근하는
테스트는 ``AttributeError`` 로 fail — 정상. 40차 구현 후 pass 로 전환.

**Collection-error 회피**: ``CLAIM_STATUS_DISPUTED`` 를 module-level
import 하지 않는다. dynamic ``getattr`` 로 접근. 그렇지 않으면 39차에
``ImportError`` 가 collection time 에 터져 전체 모듈이 깨진다.

§20.10 의 14 개 invariant 매핑:
1.  confirmed + 0 contradiction → dispute False        — dispute side
2.  confirmed + 1+ contradiction → True, DISPUTED      — dispute side
3.  candidate + 1+ contradiction → dispute False       — dispute side
4.  refuted + 1+ contradiction → dispute False         — dispute side
5.  disputed 재호출 idempotent                          — dispute side
6.  unknown claim_id → KeyError                         — dispute side
7.  confirm_claim_if_ready(disputed) → False            — cross-API
8.  refute_claim_if_ready(disputed) → False             — cross-API
9.  register_contradiction(disputed, ev) 정상 등록       — cross-API
10. dispute 후 contradictions / gap state 보존         — isolation
11. dispute 후 base_confidence 무변화                   — isolation
12. CLAIM_STATUS_MAP 에 'disputed' 키 없음             — Sub-decision D
13. CLAIM_STATUS_DISPUTED export (ragcore + ragcore.types)
14. 기존 450 회귀 없음 (전체 통과로 입증, 별도 테스트 없음)

**기대 fail 분포 (39차)**:
- AttributeError (dispute_claim_if_ready 호출): inv 1~6, 7~11 일부
- AttributeError (CLAIM_STATUS_DISPUTED 부재): inv 13
- Sub-decision D (inv 12): **이미 통과** (D-NO 가 현재 코드 상태와 정합)
"""

from __future__ import annotations

from dataclasses import replace

import pytest

# CLAIM_STATUS_DISPUTED 는 의도적으로 import 안 함 (collection-error 회피).
from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_REFUTED,
    Engine,
)

# PR8 §20.4 spec: CLAIM_STATUS_DISPUTED 의 값은 3.
# 상수가 아직 없을 때도 invariant 잠금이 가능하도록 hardcode.
_EXPECTED_DISPUTED_VALUE = 3


def _candidate_claim(engine: Engine) -> tuple[int, int]:
    """entity + candidate claim helper."""
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


def _confirmed_claim_with_contradiction(engine: Engine) -> tuple[int, int]:
    """confirmed Claim + 1 contradiction 등록. PR8 의 표준 setup."""
    _, claim_id = _candidate_claim(engine)
    ev = _evidence(engine, claim_id)
    engine.register_contradiction(claim_id, ev)
    # white-box: confirmed 로 (PR6 confirm 경로를 거치지 않고 직접)
    engine._claims[claim_id] = replace(
        engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
    )
    return claim_id, ev


class TestDisputeClaimIfReady:
    """§20.10 invariants 1~6 — dispute_claim_if_ready 전이 / no-op / KeyError."""

    # invariant 1
    def test_confirmed_with_zero_contradictions_returns_false(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        result = engine.dispute_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    # invariant 2
    def test_confirmed_with_contradiction_becomes_disputed(self) -> None:
        engine = Engine()
        claim_id, _ = _confirmed_claim_with_contradiction(engine)

        result = engine.dispute_claim_if_ready(claim_id)

        assert result is True
        assert engine.get_claim(claim_id).status == _EXPECTED_DISPUTED_VALUE

    # invariant 3 — PR7 refute 영역 보호
    def test_candidate_with_contradiction_is_not_disputed(self) -> None:
        """candidate + contradiction 은 PR7 refute 영역. dispute 는 confirmed 출신만."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)
        # candidate 상태 그대로

        result = engine.dispute_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CANDIDATE

    # invariant 4
    def test_refuted_with_contradiction_is_not_disputed(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)
        # white-box: refuted 로
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )

        result = engine.dispute_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 5
    def test_disputed_reinvocation_is_noop(self) -> None:
        """첫 호출 True, 두 번째 호출 False, 상태 DISPUTED 유지."""
        engine = Engine()
        claim_id, _ = _confirmed_claim_with_contradiction(engine)

        first = engine.dispute_claim_if_ready(claim_id)
        second = engine.dispute_claim_if_ready(claim_id)

        assert first is True
        assert second is False
        assert engine.get_claim(claim_id).status == _EXPECTED_DISPUTED_VALUE

    # invariant 6
    def test_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.dispute_claim_if_ready(999)


class TestCrossAPIWithDisputed:
    """§20.10 invariants 7~9 — disputed Claim 과 다른 lifecycle API 들."""

    # invariant 7
    def test_confirm_claim_if_ready_does_not_confirm_disputed(self) -> None:
        engine = Engine()
        claim_id, _ = _confirmed_claim_with_contradiction(engine)
        engine.dispute_claim_if_ready(claim_id)
        assert engine.get_claim(claim_id).status == _EXPECTED_DISPUTED_VALUE

        result = engine.confirm_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == _EXPECTED_DISPUTED_VALUE

    # invariant 8
    def test_refute_claim_if_ready_does_not_refute_disputed(self) -> None:
        engine = Engine()
        claim_id, _ = _confirmed_claim_with_contradiction(engine)
        engine.dispute_claim_if_ready(claim_id)
        assert engine.get_claim(claim_id).status == _EXPECTED_DISPUTED_VALUE

        result = engine.refute_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == _EXPECTED_DISPUTED_VALUE

    # invariant 9
    def test_register_contradiction_on_disputed_is_allowed(self) -> None:
        """disputed Claim 에도 contradiction 추가 등록 가능 (PR7 §19.6 일관)."""
        engine = Engine()
        claim_id, _ = _confirmed_claim_with_contradiction(engine)
        engine.dispute_claim_if_ready(claim_id)
        # 새 evidence 로 추가 contradiction
        ev2 = _evidence(engine, claim_id)

        result = engine.register_contradiction(claim_id, ev2)

        assert result is True
        # 등록은 됐지만 상태 변화 없음
        assert engine.get_claim(claim_id).status == _EXPECTED_DISPUTED_VALUE
        # 두 contradiction 다 보존
        assert len(engine.contradictions_for_claim(claim_id)) == 2


class TestDisputeIsolation:
    """§20.10 invariants 10~11 — dispute 전이가 다른 state 무변화."""

    # invariant 10
    def test_dispute_preserves_contradictions_and_gap_state(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        gap_id = engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev_gap = _evidence(engine, claim_id, evidence_type=42)
        engine.resolve_gaps_for_evidence(ev_gap)
        ev_contra = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev_contra)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        before_resolutions = dict(engine._gap_resolutions)
        before_contradictions = engine.contradictions_for_claim(claim_id)
        before_gap = engine.get_gap(gap_id)

        engine.dispute_claim_if_ready(claim_id)

        assert engine._gap_resolutions == before_resolutions
        assert engine.contradictions_for_claim(claim_id) == before_contradictions
        assert engine.get_gap(gap_id) == before_gap
        assert engine.gap_resolution(gap_id) == ev_gap

    # invariant 11
    def test_dispute_does_not_change_base_confidence(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.42,
        )
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        before = engine.get_claim(claim_id).base_confidence

        engine.dispute_claim_if_ready(claim_id)

        after = engine.get_claim(claim_id).base_confidence
        assert after == before
        assert after.value == pytest.approx(0.42)


class TestSubDecisionD:
    """§20.10 invariant 12 — YAML rule output 에 disputed 노출 금지."""

    # invariant 12 — 이미 통과해야 정상 (D-NO 정합)
    def test_claim_status_map_does_not_expose_disputed(self) -> None:
        """Sub-decision D: CLAIM_STATUS_MAP 에 'disputed' 키 없음 + _ALLOWED_CLAIM_STATUSES 에 3 없음."""
        from ragcore.rule_output import CLAIM_STATUS_MAP, _ALLOWED_CLAIM_STATUSES

        assert "disputed" not in CLAIM_STATUS_MAP
        assert _EXPECTED_DISPUTED_VALUE not in _ALLOWED_CLAIM_STATUSES


class TestDisputedConstantExport:
    """§20.10 invariant 13 — CLAIM_STATUS_DISPUTED export."""

    # invariant 13a
    def test_constant_exported_from_ragcore_types(self) -> None:
        """ragcore.types.CLAIM_STATUS_DISPUTED == 3."""
        import ragcore.types

        value = getattr(ragcore.types, "CLAIM_STATUS_DISPUTED", None)
        assert value == _EXPECTED_DISPUTED_VALUE

    # invariant 13b
    def test_constant_exported_from_ragcore_root(self) -> None:
        """ragcore.CLAIM_STATUS_DISPUTED == 3 (top-level re-export)."""
        import ragcore

        value = getattr(ragcore, "CLAIM_STATUS_DISPUTED", None)
        assert value == _EXPECTED_DISPUTED_VALUE
