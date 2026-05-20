"""Tests for PR25-T — Hint evidence type deregistration API.

PR25-T §37:
    Deregistration is the inverse of registration, not a redefinition.

Core proposition:
    PR25-T does not change the meaning of evidence_type modifier.
    PR25-T completes the caller-facing hint evidence type registration surface
    by adding explicit unregister and clear APIs.

New API surface:
    unregister_hint_evidence_types(types)
    clear_hint_evidence_types()

Existing API unchanged:
    register_hint_evidence_types(types)

Formula shape unchanged:
    effective = base × status × freshness × gap × count × rule_stats × evidence_type

Expected pre-implementation fail pattern:
    - unregister_hint_evidence_types missing
    - clear_hint_evidence_types missing
    - immediate modifier update cases fail because APIs do not exist yet

Existing PR21-L / PR22-S behavior should continue to pass.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

import ragcore
import ragcore.types as types_module
from ragcore import (
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    Engine,
    RuleDefinition,
    ScoreValue,
)


def _claim(
    engine: Engine,
    *,
    base_confidence: float = 1.0,
    rule_id: int = 0,
    rule_version: int = 0,
) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=rule_id,
        rule_version=rule_version,
        reason_code=0,
        base_confidence=base_confidence,
    )
    return entity_id, claim_id


def _evidence(
    engine: Engine,
    claim_id: int,
    *,
    evidence_type: int = 42,
    strength: float = 0.5,
) -> int:
    return engine.add_evidence(
        claim_id=claim_id,
        raw_ref_id=0,
        evidence_type=evidence_type,
        strength=strength,
    )


def _active_contradictions(
    engine: Engine,
    claim_id: int,
    strengths: tuple[float, ...],
) -> tuple[int, ...]:
    ids: list[int] = []
    for strength in strengths:
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=99,
            strength=strength,
        )
        engine.register_contradiction(claim_id, evidence_id)
        ids.append(evidence_id)
    return tuple(ids)


def _unresolved_gap(
    engine: Engine,
    claim_id: int,
    *,
    required_evidence_type: int = 500,
) -> int:
    return engine.add_gap(
        claim_id=claim_id,
        gap_type=1,
        required_evidence_type=required_evidence_type,
        severity=0.5,
        rule_id=1,
    )


def _hint_snapshot(engine: Engine) -> list[int]:
    return engine.to_snapshot()["hint_evidence_types"]


class TestHintEvidenceTypeUnregisterBasic:
    """§37 BE — unregister removes registered values; missing values are no-op."""

    def test_unregister_api_exists(self) -> None:
        engine = Engine()
        assert callable(getattr(engine, "unregister_hint_evidence_types", None))

    def test_unregister_single_registered_type(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2])

        engine.unregister_hint_evidence_types([1])

        assert _hint_snapshot(engine) == [2]

    def test_unregister_multiple_registered_types(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2, 3, 4])

        engine.unregister_hint_evidence_types([1, 3])

        assert _hint_snapshot(engine) == [2, 4]

    def test_unregister_missing_type_is_noop(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2])

        engine.unregister_hint_evidence_types([999])

        assert _hint_snapshot(engine) == [1, 2]

    def test_unregister_empty_iterable_is_noop(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2])

        engine.unregister_hint_evidence_types([])

        assert _hint_snapshot(engine) == [1, 2]

    def test_unregister_duplicates_is_idempotent(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2])

        engine.unregister_hint_evidence_types([1, 1, 1])

        assert _hint_snapshot(engine) == [2]


class TestHintEvidenceTypeUnregisterStrictValidation:
    """§37 BD/BF — unregister validation must match PR22-S strict registration."""

    def test_unregister_str_element_raises_type_error(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1])

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types(["1"])

    def test_unregister_float_element_raises_type_error(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1])

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types([1.0])

    def test_unregister_bytes_element_raises_type_error(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1])

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types([b"1"])

    def test_unregister_none_element_raises_type_error(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1])

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types([None])

    def test_unregister_bool_true_raises_type_error(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1])

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types([True])

    def test_unregister_bool_false_raises_type_error(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1])

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types([False])

    def test_unregister_str_container_raises_type_error(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2, 3])

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types("123")

    def test_unregister_bytes_container_raises_type_error(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2, 3])

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types(b"123")

    def test_unregister_raw_int_non_iterable_raises_type_error(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1])

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types(1)  # type: ignore[arg-type]


class TestHintEvidenceTypeUnregisterAllOrNothing:
    """§37 BF — invalid unregister must not partially mutate the hint set."""

    def test_mixed_invalid_unregister_does_not_remove_valid_prefix(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2, 3])
        before = _hint_snapshot(engine)

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types([1, "2", 3])

        assert _hint_snapshot(engine) == before

    def test_bool_invalid_unregister_does_not_mutate(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2, 3])
        before = _hint_snapshot(engine)

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types([1, True, 3])

        assert _hint_snapshot(engine) == before

    def test_float_invalid_unregister_does_not_mutate(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2, 3])
        before = _hint_snapshot(engine)

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types([1, 2.0, 3])

        assert _hint_snapshot(engine) == before

    def test_prior_successful_registration_survives_failed_unregister(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1])
        before = _hint_snapshot(engine)

        with pytest.raises(TypeError):
            engine.unregister_hint_evidence_types([2, "bad"])

        assert _hint_snapshot(engine) == before


class TestHintEvidenceTypeClear:
    """§37 BG — clear is always no-op safe."""

    def test_clear_api_exists(self) -> None:
        engine = Engine()
        assert callable(getattr(engine, "clear_hint_evidence_types", None))

    def test_clear_after_register_empties_hint_set(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2, 3])

        engine.clear_hint_evidence_types()

        assert _hint_snapshot(engine) == []

    def test_clear_on_empty_set_is_noop(self) -> None:
        engine = Engine()

        engine.clear_hint_evidence_types()

        assert _hint_snapshot(engine) == []

    def test_repeated_clear_is_noop(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2])

        engine.clear_hint_evidence_types()
        engine.clear_hint_evidence_types()

        assert _hint_snapshot(engine) == []

    def test_clear_mutates_only_hint_set(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine)
        _evidence(engine, claim_id, evidence_type=42)
        engine.register_hint_evidence_types([42, 99])

        before = engine.to_snapshot()
        expected = dict(before)
        expected["hint_evidence_types"] = []

        engine.clear_hint_evidence_types()

        assert engine.to_snapshot() == expected


class TestHintEvidenceTypeModifierImmediateReflection:
    """§37 BI — unregister/clear immediately affect evidence_type modifier."""

    def test_unregister_removes_penalty_for_direct_evidence_type(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([42])
        _, claim_id = _claim(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)

        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(0.9)

        engine.unregister_hint_evidence_types([42])

        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(1.0)

    def test_unregister_partial_keeps_other_hint_type_penalty(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([42, 99])
        _, claim_id = _claim(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=99)

        engine.unregister_hint_evidence_types([42])

        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(0.9)

    def test_clear_removes_penalty_for_direct_hint_evidence(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([42])
        _, claim_id = _claim(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)

        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(0.9)

        engine.clear_hint_evidence_types()

        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(1.0)

    def test_unregister_affects_only_direct_evidence_type_modifier(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([42])
        _, claim_id = _claim(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)
        _active_contradictions(engine, claim_id, (0.8, 0.8))

        before = engine.compute_effective_confidence(claim_id).value
        engine.unregister_hint_evidence_types([42])
        after = engine.compute_effective_confidence(claim_id).value

        # Before: freshness 0.6 × count 0.8 × evidence_type 0.9 = 0.432
        # After:  freshness 0.6 × count 0.8 × evidence_type 1.0 = 0.48
        assert before == pytest.approx(0.432)
        assert after == pytest.approx(0.48)


class TestHintEvidenceTypeDeregistrationSnapshot:
    """§37 BH — no schema bump, snapshot shape preserved."""

    def test_snapshot_schema_version_remains_two(self) -> None:
        engine = Engine()
        assert engine.to_snapshot()["schema_version"] == 2

    def test_snapshot_after_unregister_serializes_sorted_updated_set(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([5, 1, 3, 2, 4])

        engine.unregister_hint_evidence_types([2, 4])

        assert engine.to_snapshot()["hint_evidence_types"] == [1, 3, 5]

    def test_snapshot_after_clear_serializes_empty_list(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1, 2, 3])

        engine.clear_hint_evidence_types()

        assert engine.to_snapshot()["hint_evidence_types"] == []

    def test_roundtrip_after_unregister_preserves_updated_set(self) -> None:
        original = Engine()
        original.register_hint_evidence_types([1, 2, 3])
        original.unregister_hint_evidence_types([1, 3])

        restored = Engine.from_snapshot(original.to_snapshot())

        assert restored.to_snapshot()["hint_evidence_types"] == [2]

    def test_roundtrip_after_clear_preserves_empty_set(self) -> None:
        original = Engine()
        original.register_hint_evidence_types([1, 2, 3])
        original.clear_hint_evidence_types()

        restored = Engine.from_snapshot(original.to_snapshot())

        assert restored.to_snapshot()["hint_evidence_types"] == []


class TestHintEvidenceTypeRegisterBehaviorPreserved:
    """§37 BJ — register_hint_evidence_types external behavior unchanged."""

    def test_register_accumulation_unchanged(self) -> None:
        engine = Engine()

        engine.register_hint_evidence_types([1])
        engine.register_hint_evidence_types([2])

        assert _hint_snapshot(engine) == [1, 2]

    def test_register_duplicate_idempotence_unchanged(self) -> None:
        engine = Engine()

        engine.register_hint_evidence_types([1, 1, 1])

        assert _hint_snapshot(engine) == [1]

    def test_register_strict_validation_all_or_nothing_unchanged(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([1])
        before = _hint_snapshot(engine)

        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([2, "3"])

        assert _hint_snapshot(engine) == before


class TestHintEvidenceTypeDeregistrationComposition:
    """§37 BI — formula shape unchanged; only hint set membership changes."""

    def test_full_composition_after_unregister_has_no_evidence_type_penalty(self) -> None:
        engine = Engine()
        engine.register_rule(
            RuleDefinition(
                id=7,
                version=1,
                maturity=0,
                prior_confidence=ScoreValue(0.5),
            )
        )
        engine.update_rule_stats(rule_id=7, rule_version=1, firing_delta=1)

        engine.register_hint_evidence_types([42])
        _, claim_id = _claim(
            engine,
            base_confidence=1.0,
            rule_id=7,
            rule_version=1,
        )
        _evidence(engine, claim_id, evidence_type=42)
        _active_contradictions(engine, claim_id, (0.8, 0.8))
        _unresolved_gap(engine, claim_id)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id],
            status=CLAIM_STATUS_DISPUTED,
        )

        engine.unregister_hint_evidence_types([42])

        result = engine.compute_effective_confidence(claim_id)

        # status 0.5 × freshness 0.6 × gap 0.9 × count 0.8 × rule_stats 0.9
        # evidence_type penalty removed → 1.0
        assert result.value == pytest.approx(0.5 * 0.6 * 0.9 * 0.8 * 0.9)

    def test_full_composition_after_clear_has_no_evidence_type_penalty(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([42])
        _, claim_id = _claim(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)
        _active_contradictions(engine, claim_id, (0.8, 0.8))
        _unresolved_gap(engine, claim_id)

        engine.clear_hint_evidence_types()

        result = engine.compute_effective_confidence(claim_id)

        # freshness 0.6 × gap 0.9 × count 0.8, evidence_type removed.
        assert result.value == pytest.approx(0.6 * 0.9 * 0.8)

    def test_formula_without_deregistration_remains_unchanged(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([42])
        _, claim_id = _claim(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)

        result = engine.compute_effective_confidence(claim_id)

        assert result.value == pytest.approx(0.9)


class TestHintEvidenceTypeDeregistrationPublicNamespace:
    """Sub-decision D boundary — no new module constants or public exports."""

    def test_no_builtin_hint_constant_in_ragcore(self) -> None:
        names = [
            "EVIDENCE_TYPE_HINT",
            "HINT_EVIDENCE_TYPE",
            "HINT_EVIDENCE_TYPES",
        ]
        for name in names:
            assert not hasattr(ragcore, name)
            assert name not in getattr(ragcore, "__all__", [])

    def test_no_builtin_hint_constant_in_types_module(self) -> None:
        names = [
            "EVIDENCE_TYPE_HINT",
            "HINT_EVIDENCE_TYPE",
            "HINT_EVIDENCE_TYPES",
        ]
        for name in names:
            assert not hasattr(types_module, name)

    def test_engine_methods_are_not_module_level_exports(self) -> None:
        names = [
            "register_hint_evidence_types",
            "unregister_hint_evidence_types",
            "clear_hint_evidence_types",
        ]
        for name in names:
            assert not hasattr(ragcore, name)
            assert name not in getattr(ragcore, "__all__", [])


class TestHintEvidenceTypeDeregistrationRegressionBoundaries:
    """PR21-L / PR22-S / PR23-M / PR24-N / lifecycle regressions."""

    def test_pr21l_evidence_type_modifier_unchanged(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([42])
        _, claim_id = _claim(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)

        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(0.9)

    def test_pr22s_register_strict_validation_unchanged(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([1, True, 3])

        assert _hint_snapshot(engine) == []

    def test_pr23m_gap_modifier_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _unresolved_gap(engine, claim_id)
        _unresolved_gap(engine, claim_id, required_evidence_type=501)

        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(0.8)

    def test_pr24n_count_strength_averaging_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _active_contradictions(engine, claim_id, (0.4, 0.4))

        # freshness 0.8 × count 0.9
        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(0.72)

    def test_pr9a_active_contradictions_order_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine)
        ev1, ev2 = _active_contradictions(engine, claim_id, (0.4, 0.8))

        assert engine.active_contradictions_for_claim(claim_id) == (ev1, ev2)

    def test_pr10a_refute_disputed_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine)
        _active_contradictions(engine, claim_id, (0.9,))
        engine._claims[claim_id] = replace(
            engine._claims[claim_id],
            status=CLAIM_STATUS_CONFIRMED,
        )

        assert engine.dispute_claim_if_ready(claim_id) is True
        assert engine.refute_disputed_claim_if_ready(claim_id) is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    def test_pr11b_refute_by_freshness_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine)
        _active_contradictions(engine, claim_id, (0.9,))
        engine._claims[claim_id] = replace(
            engine._claims[claim_id],
            status=CLAIM_STATUS_CONFIRMED,
        )

        assert engine.dispute_claim_if_ready(claim_id) is True
        assert engine.refute_disputed_claim_if_ready_by_freshness(claim_id) is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    def test_pr17_roundtrip_identity_unchanged(self) -> None:
        original = Engine()
        original.register_hint_evidence_types([42])
        _, claim_id = _claim(original, base_confidence=1.0)
        _evidence(original, claim_id, evidence_type=42)

        restored = Engine.from_snapshot(original.to_snapshot())

        assert restored.compute_effective_confidence(claim_id) == (
            original.compute_effective_confidence(claim_id)
        )
