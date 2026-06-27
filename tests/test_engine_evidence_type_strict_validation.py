"""Tests for PR22-S — Evidence_type registration strict validation
(MVP, no implicit cast / no partial mutation / no taxonomy ownership).

Invariants of ``Engine.register_hint_evidence_types`` 의 입력 계약 강화:

**95차 (test-first) 상태**: PR21-L 의 `self._hint_evidence_types.update(int(t) for t in types)`
구현 그대로. 따라서 implicit cast / bool / str/bytes 컨테이너 / partial
mutation 케이스들이 fail 해야 정상. fail pattern mixed.

§34.13 의 40 invariant 매핑은 클래스 docstring 에 명시.

핵심:
    PR22-S 는 modifier / 공식 / state shape / snapshot schema 모두 안 바꾼다.
    오직 register_hint_evidence_types 본문의 입력 검증만 강화한다.
"""

from __future__ import annotations

import pytest

import ragcore
import ragcore.engine as engine_module
# Phase 2: confidence policy constants + status admission relocated to
# ragcore._engine.confidence; read them from their new canonical home.
import ragcore._engine.confidence as confidence_module
import ragcore.types as types_module
from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    Engine,
)


# ---- Helpers ---------------------------------------------------------------


def _entity_claim(engine: Engine, *, base_confidence: float = 1.0) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id, claim_type=1,
        rule_id=0, rule_version=0, reason_code=0,
        base_confidence=base_confidence,
    )
    return entity_id, claim_id


def _hint_set(engine: Engine) -> set[int]:
    """Expose `_hint_evidence_types` for test-only assertions on partial mutation."""
    return set(engine._hint_evidence_types)


# ---- 1. Allowed int inputs (Sub-decision AJ + AK) --------------------------


class TestStrictValidationAllowedInputs:
    """§34.13 invariants 1~9 + 24~26 — valid int inputs / accumulation."""

    # 1
    def test_list_of_int_allowed(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2, 3])
        assert _hint_set(engine) == {1, 2, 3}

    # 2
    def test_tuple_of_int_allowed(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types((4, 5, 6))
        assert _hint_set(engine) == {4, 5, 6}

    # 3 — bare set
    def test_set_of_int_allowed(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types({7, 8})
        assert _hint_set(engine) == {7, 8}

    # 4 — frozenset
    def test_frozenset_of_int_allowed(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types(frozenset({10, 20}))
        assert _hint_set(engine) == {10, 20}

    # 5 — generator
    def test_generator_of_int_allowed(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types(iter([100, 200, 300]))
        assert _hint_set(engine) == {100, 200, 300}

    # 6 — Sub-decision AK: zero allowed
    def test_zero_allowed(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([0])
        assert _hint_set(engine) == {0}

    # 7 — Sub-decision AK: negative allowed
    def test_negative_ints_allowed(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([-1, -100])
        assert _hint_set(engine) == {-1, -100}

    # 8 — Sub-decision AK: very large int allowed
    def test_very_large_int_allowed(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([10**18])
        assert _hint_set(engine) == {10**18}

    # 9 — empty iterable no-op
    def test_empty_iterable_is_noop(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([])
        assert _hint_set(engine) == set()

    # 24 — duplicate idempotent
    def test_duplicates_idempotent(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 1, 1])
        assert _hint_set(engine) == {1}

    # 25 — accumulation across calls
    def test_accumulates_across_calls(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1])
        engine.register_hint_evidence_types([2])
        assert _hint_set(engine) == {1, 2}


# ---- 2. Implicit cast rejection (Sub-decision AI) --------------------------


class TestStrictValidationRejectsImplicitCast:
    """§34.13 invariants 10~13 — silent cast 차단 (현재 PR21-L 에서 통과)."""

    # 10 ★ — str element silently cast to int via int("1") currently
    def test_string_element_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types(["1"])
        # All-or-nothing: nothing registered
        assert _hint_set(engine) == set()

    # 11 ★ — float element
    def test_float_element_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([1.0])
        assert _hint_set(engine) == set()

    # 12 ★ — bytes-of-len-1 element
    def test_bytes_element_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([b"1"])
        assert _hint_set(engine) == set()

    # 13 — None element (currently passes since int(None) raises TypeError too,
    # but invariant must still hold AFTER 96차 with all-or-nothing semantics)
    def test_none_element_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([None])
        assert _hint_set(engine) == set()

    # Generic object element
    def test_generic_object_element_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([object()])
        assert _hint_set(engine) == set()


# ---- 3. Bool rejection (Sub-decision AJ) -----------------------------------


class TestStrictValidationRejectsBool:
    """§34.13 invariants 14~16 — bool 함정 차단.

    Python 에서 `isinstance(True, int)` 는 True 이므로 bool 검사를
    int 검사 **이전에** 별도 해야 한다.
    """

    # 14 ★
    def test_true_element_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([True])
        assert _hint_set(engine) == set()

    # 15 ★
    def test_false_element_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([False])
        assert _hint_set(engine) == set()

    # 16 ★ — mixed bool + int → all-or-nothing
    def test_mixed_int_and_bool_rejected_atomically(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([1, True])
        # int 1 must NOT have been registered before bool was reached
        assert _hint_set(engine) == set()


# ---- 4. str / bytes container rejection (Sub-decision AM edge) -------------


class TestStrictValidationRejectsStringContainer:
    """§34.13 invariants 18~21 — str/bytes 자체 입력 차단.

    str / bytes 는 technically iterable 이지만 API 의미상 `Iterable[int]`
    컨테이너로 인정하면 안 된다.
    """

    # 18 ★ — single-digit str
    def test_string_input_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types("1")
        assert _hint_set(engine) == set()

    # 19 ★ — multi-char str
    def test_multichar_string_input_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types("12")
        # Currently iterates chars "1", "2" → int cast → silently registers {1, 2}.
        # After 96차: TypeError + no registration.
        assert _hint_set(engine) == set()

    # 20 ★ — single-byte bytes
    def test_bytes_input_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types(b"\x01")
        assert _hint_set(engine) == set()

    # 21 ★ — multi-byte bytes (currently registers byte values 49, 50)
    def test_multibyte_bytes_input_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types(b"12")
        # Currently iterates bytes → 49, 50 silently registered.
        # After 96차: TypeError + no registration.
        assert _hint_set(engine) == set()


# ---- 5. Non-iterable rejection (Sub-decision AM) ---------------------------


class TestStrictValidationRejectsNonIterable:
    """§34.13 invariants 17, 22~23 — non-iterable input."""

    # 17 — raw int (PR21-L 도 TypeError, 이미 pass)
    def test_raw_int_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types(1)

    # 22 — None
    def test_none_input_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types(None)

    # 23 — raw float
    def test_raw_float_rejected(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types(1.0)


# ---- 6. All-or-nothing update (Sub-decision AL) ----------------------------


class TestStrictValidationAllOrNothing:
    """§34.13 invariants 20~22 — partial mutation 차단.

    현재 PR21-L 의 `update(int(t) for t in types)` 는 generator 를 lazy 하게
    소비하면서 valid 한 element 를 먼저 set 에 add 한 뒤 invalid 에서
    TypeError 가 발생하기 때문에, 실패 시점에 이미 일부가 등록되어 있다.
    PR22-S 는 이를 atomic 으로 만든다.
    """

    # 20 ★ — pre-existing set + invalid call: pre-state must remain
    def test_invalid_call_preserves_pre_existing_set(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([7])
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([1, "2"])
        # set must remain {7} — 1 NOT registered
        assert _hint_set(engine) == {7}

    # 21 ★ — pre-existing set + bool invalid call
    def test_invalid_bool_call_preserves_pre_existing_set(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([7])
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([1, True])
        assert _hint_set(engine) == {7}

    # 22 ★ — empty set + invalid call: still empty
    def test_invalid_call_on_empty_set_leaves_empty(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([1, "2"])
        assert _hint_set(engine) == set()

    # generator with mid-stream invalid
    def test_generator_with_invalid_element_no_partial_mutation(self) -> None:
        """Generator yields 1, then None — PR21-L lazily adds 1 then TypeErrors
        on int(None). PR22-S must validate fully before any update."""
        def gen():
            yield 1
            yield None
            yield 3

        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types(gen())
        assert _hint_set(engine) == set()


# ---- 7. Snapshot / formula / regression unchanged (Sub-decision AN) --------


class TestStrictValidationSnapshotAndFormulaUnchanged:
    """§34.13 invariants 27~37 — PR21-L 의 모든 호환 동작 보존."""

    # 27 — snapshot schema_version still 2
    def test_snapshot_schema_version_still_two(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2])
        snap = engine.to_snapshot()
        assert snap["schema_version"] == 2

    # 28 — empty registration → hint_evidence_types: [] in snapshot
    def test_empty_registration_snapshot_empty_list(self) -> None:
        engine = Engine()
        snap = engine.to_snapshot()
        assert snap["hint_evidence_types"] == []

    # 29 — valid registration round-trip preserves hint set
    def test_round_trip_preserves_hint_set_after_valid_call(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([3, 1, 2])
        snap = engine.to_snapshot()
        restored = Engine.from_snapshot(snap)
        assert _hint_set(restored) == {1, 2, 3}

    # 31 — invalid registration: snapshot must NOT show partial changes
    def test_invalid_registration_snapshot_unchanged(self) -> None:
        engine = Engine()
        snap_before = engine.to_snapshot()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([1, "2"])
        snap_after = engine.to_snapshot()
        assert snap_before == snap_after

    # 30/32 — evidence_type modifier value unchanged from PR21-L semantics
    def test_hint_only_direct_evidence_still_yields_0_9(self) -> None:
        """PR21-L 의 hint-only penalty (0.9) 가 PR22-S 후에도 동일해야 한다."""
        engine = Engine()
        engine.register_hint_evidence_types([42])
        _, claim_id = _entity_claim(engine, base_confidence=1.0)
        engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=42, strength=0.5,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.9)

    # 33 — empty hint registration still gives modifier 1.0
    def test_empty_hint_modifier_still_one(self) -> None:
        engine = Engine()
        _, claim_id = _entity_claim(engine, base_confidence=0.8)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.8)

    # 34 — _EVIDENCE_TYPE_PENALTY_MODIFIER constant unchanged
    def test_penalty_modifier_constant_unchanged(self) -> None:
        val = getattr(confidence_module, "_EVIDENCE_TYPE_PENALTY_MODIFIER", None)
        assert val == 0.9

    # 36 — no new public export
    def test_no_new_public_export_added(self) -> None:
        # PR22-S must NOT add any new public symbol to ragcore namespace
        assert not hasattr(ragcore, "_EVIDENCE_TYPE_PENALTY_MODIFIER")
        assert not hasattr(ragcore, "EVIDENCE_TYPE_HINT")
        assert not hasattr(ragcore, "EVIDENCE_TYPE_OBSERVED")
        assert not hasattr(types_module, "EVIDENCE_TYPE_HINT")
