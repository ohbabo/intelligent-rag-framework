"""Tests for PR10-B — Claim lifecycle history (MVP).

Invariants of ``ClaimLifecycleEvent`` + ``claim_lifecycle_history`` +
side-effect 기록 (5 lifecycle API).

**51차 (test-first) 상태**:
- ``ClaimLifecycleEvent`` 미정의
- ``claim_lifecycle_history`` 미구현
- 5 lifecycle API 의 history 기록 side effect 미구현

따라서 모든 호출/접근 테스트는 ``AttributeError`` (또는 dynamic getattr 가
None 으로 잡혀 assertion fail) 로 fail — 정상. 52차에서 impl 후 통과 전환.

**Collection-error 회피**: ``ClaimLifecycleEvent`` 를 module-level import
하지 않고 ``getattr(ragcore, "ClaimLifecycleEvent", None)`` 으로 dynamic
접근 (PR8 39차의 CLAIM_STATUS_DISPUTED 패턴).

§23.13 의 16 개 invariant 매핑 (inv 14, 15 는 3~7 안에 포함, inv 16 은 회귀):
1.  unknown claim_id → KeyError
2.  add_claim 직후 history 는 빈 tuple (+ tuple type)
3.  confirm 성공 → event (transition="confirm_if_ready", CAND→CONF)
4.  refute_candidate 성공 → event (transition="refute_if_ready", CAND→REF)
5.  dispute 성공 → event (transition="dispute_if_ready", CONF→DISP)
6.  resolve_disputed 성공 → event (transition="resolve_disputed_if_ready", DISP→CONF)
7.  refute_disputed 성공 → event (transition="refute_disputed_if_ready", DISP→REF)
8.  False no-op → 기록 안 함
9.  add_claim / fire_rule 단독 → 기록 안 함
10. 비-transition API (register_contradiction / add_evidence /
    resolve_gaps_for_evidence) → 기록 안 함
11. seq strict increasing within one claim
12. seq per-engine monotonic (cross-claim)
13. ClaimLifecycleEvent 는 frozen dataclass with 5 fields
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass, replace

import pytest

import ragcore
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


class TestClaimLifecycleEvent:
    """§23.13 invariant 13 — ClaimLifecycleEvent dataclass shape."""

    def test_event_class_exists_and_is_dataclass(self) -> None:
        event_cls = getattr(ragcore, "ClaimLifecycleEvent", None)
        assert event_cls is not None
        assert is_dataclass(event_cls)

    def test_event_has_required_fields(self) -> None:
        event_cls = getattr(ragcore, "ClaimLifecycleEvent", None)
        assert event_cls is not None
        expected = {"seq", "claim_id", "from_status", "to_status", "transition"}
        actual = set(event_cls.__dataclass_fields__.keys())
        assert expected == actual

    def test_event_is_frozen(self) -> None:
        event_cls = getattr(ragcore, "ClaimLifecycleEvent", None)
        assert event_cls is not None
        ev = event_cls(
            seq=1, claim_id=1,
            from_status=CLAIM_STATUS_CANDIDATE,
            to_status=CLAIM_STATUS_CONFIRMED,
            transition="confirm_if_ready",
        )
        with pytest.raises((AttributeError, FrozenInstanceError)):
            ev.seq = 999  # type: ignore[misc]


class TestClaimLifecycleHistory:
    """§23.13 invariants 1, 2 — query API + empty + tuple type."""

    # invariant 1
    def test_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.claim_lifecycle_history(999)

    # invariant 2 + tuple type
    def test_history_empty_after_add_claim(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        history = engine.claim_lifecycle_history(claim_id)
        assert isinstance(history, tuple)
        assert history == ()


class TestTransitionsAreRecorded:
    """§23.13 invariants 3~7 (+ 14, 15) — 5 API 의 event shape."""

    # invariant 3
    def test_confirm_records_event(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = _evidence(engine, claim_id, evidence_type=42)
        engine.resolve_gaps_for_evidence(ev)

        engine.confirm_claim_if_ready(claim_id)

        history = engine.claim_lifecycle_history(claim_id)
        assert len(history) == 1
        evt = history[0]
        assert evt.claim_id == claim_id
        assert evt.from_status == CLAIM_STATUS_CANDIDATE
        assert evt.to_status == CLAIM_STATUS_CONFIRMED
        assert evt.transition == "confirm_if_ready"
        assert evt.seq >= 1

    # invariant 4
    def test_refute_candidate_records_event(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)

        engine.refute_claim_if_ready(claim_id)

        history = engine.claim_lifecycle_history(claim_id)
        assert len(history) == 1
        evt = history[0]
        assert evt.from_status == CLAIM_STATUS_CANDIDATE
        assert evt.to_status == CLAIM_STATUS_REFUTED
        assert evt.transition == "refute_if_ready"

    # invariant 5
    def test_dispute_records_event(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)
        # white-box: confirmed 직접 설정 (caller mutation 은 audit 안 됨 — Sub-decision J 정합)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        engine.dispute_claim_if_ready(claim_id)

        history = engine.claim_lifecycle_history(claim_id)
        # white-box 직접 status 변경은 audit 안 됨, dispute API 만 audit
        assert len(history) == 1
        evt = history[0]
        assert evt.from_status == CLAIM_STATUS_CONFIRMED
        assert evt.to_status == CLAIM_STATUS_DISPUTED
        assert evt.transition == "dispute_if_ready"

    # invariant 6
    def test_resolve_disputed_records_event(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        engine.dispute_claim_if_ready(claim_id)
        engine.register_contradiction_resolution(claim_id, ev)

        engine.resolve_disputed_claim_if_ready(claim_id)

        history = engine.claim_lifecycle_history(claim_id)
        # dispute + resolve_disputed = 2 events
        assert len(history) == 2
        resolve_evt = history[1]
        assert resolve_evt.from_status == CLAIM_STATUS_DISPUTED
        assert resolve_evt.to_status == CLAIM_STATUS_CONFIRMED
        assert resolve_evt.transition == "resolve_disputed_if_ready"

    # invariant 7
    def test_refute_disputed_records_event(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id, strength=0.9)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        engine.dispute_claim_if_ready(claim_id)

        engine.refute_disputed_claim_if_ready(claim_id)

        history = engine.claim_lifecycle_history(claim_id)
        # dispute + refute_disputed = 2 events
        assert len(history) == 2
        ref_evt = history[1]
        assert ref_evt.from_status == CLAIM_STATUS_DISPUTED
        assert ref_evt.to_status == CLAIM_STATUS_REFUTED
        assert ref_evt.transition == "refute_disputed_if_ready"


class TestNoOpsAreNotRecorded:
    """§23.13 invariants 8, 9, 10 — false / 생성 / 비-transition 무변화."""

    # invariant 8a (confirm False)
    def test_confirm_false_no_op_not_recorded(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        # gap 없음 → confirm False
        result = engine.confirm_claim_if_ready(claim_id)
        assert result is False
        assert engine.claim_lifecycle_history(claim_id) == ()

    # invariant 8b (refute False)
    def test_refute_false_no_op_not_recorded(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        # contradiction 없음 → refute False
        result = engine.refute_claim_if_ready(claim_id)
        assert result is False
        assert engine.claim_lifecycle_history(claim_id) == ()

    # invariant 9 — add_claim 단독은 transition 아님
    def test_add_claim_alone_not_recorded(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        # lifecycle API 호출 0번
        assert engine.claim_lifecycle_history(claim_id) == ()

    # invariant 10a (register_contradiction 비-transition)
    def test_register_contradiction_not_recorded(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev)
        assert engine.claim_lifecycle_history(claim_id) == ()

    # invariant 10b (resolve_gaps_for_evidence 비-transition)
    def test_resolve_gaps_for_evidence_not_recorded(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = _evidence(engine, claim_id, evidence_type=42)
        engine.resolve_gaps_for_evidence(ev)
        # gap resolve 는 transition 아님 — claim status 무변화
        assert engine.claim_lifecycle_history(claim_id) == ()


class TestSequenceProperties:
    """§23.13 invariants 11, 12 — seq strict + per-engine monotonic."""

    # invariant 11 — strict increasing within one claim
    def test_seq_strictly_increases_within_one_claim(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id, strength=0.9)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        engine.dispute_claim_if_ready(claim_id)               # event 1
        engine.refute_disputed_claim_if_ready(claim_id)       # event 2

        history = engine.claim_lifecycle_history(claim_id)
        seqs = [e.seq for e in history]
        assert len(seqs) == 2
        assert seqs[0] < seqs[1]

    # invariant 12 — per-engine monotonic (cross-claim 비교)
    def test_seq_is_per_engine_not_per_claim(self) -> None:
        """서로 다른 claim 의 transition 도 같은 counter 공유."""
        engine = Engine()
        _, claim_a = _candidate_claim(engine)
        _, claim_b = _candidate_claim(engine)

        # claim_a: confirm (먼저)
        engine.add_gap(
            claim_id=claim_a, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev_a = _evidence(engine, claim_a, evidence_type=42)
        engine.resolve_gaps_for_evidence(ev_a)
        engine.confirm_claim_if_ready(claim_a)

        # claim_b: refute (나중에)
        ev_b = _evidence(engine, claim_b)
        engine.register_contradiction(claim_b, ev_b)
        engine.refute_claim_if_ready(claim_b)

        seq_a = engine.claim_lifecycle_history(claim_a)[0].seq
        seq_b = engine.claim_lifecycle_history(claim_b)[0].seq

        # per-engine counter: claim_a 가 먼저 → seq_a < seq_b
        # per-claim 이면 둘 다 1 이라서 같은 값 (잘못된 동작)
        assert seq_a < seq_b
