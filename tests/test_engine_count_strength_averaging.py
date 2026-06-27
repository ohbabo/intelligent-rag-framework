"""Tests for PR24-N — Count modifier strength averaging.

PR24-N §36:
    Count modifier remains a repeated-pressure signal.
    PR24-N refines repeated pressure from binary count threshold
    to average strength of active contradictions.

Core sentence:
    빈 강도의 contradiction 은 repeated pressure 가 아니다.

Formula shape unchanged:
    effective = base × status × freshness × gap × count × rule_stats × evidence_type

PR24-N changes only the internal calculation of the count modifier:

Before (PR19-E):
    active count < 2  → 1.0
    active count >= 2 → 0.8

After (PR24-N):
    active count < 2  → 1.0
    active count >= 2 → 1.0 - average_active_strength × 0.25

Center preservation:
    average strength 0.8 → count_modifier 0.8
    This naturally reproduces PR19-E binary 0.8 at the center point.

103차 expected fail pattern:
    - _count_modifier_for_claim helper missing
    - _COUNT_STRENGTH_PENALTY_WEIGHT missing
    - continuous expected values differ from PR19-E binary count behavior
"""

from __future__ import annotations

from dataclasses import replace

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
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    Engine,
)
from ragcore.types import (
    RULE_MATURITY_EXPERIMENTAL,
    RuleDefinition,
    ScoreValue,
)


def _candidate_claim(
    engine: Engine,
    *,
    base_confidence: float = 1.0,
    rule_id: int = 1,
    rule_version: int = 1,
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


def _add_active_contradictions(
    engine: Engine,
    claim_id: int,
    strengths: tuple[float, ...],
) -> tuple[int, ...]:
    ids: list[int] = []
    for strength in strengths:
        evidence_id = _evidence(engine, claim_id, strength=strength)
        engine.register_contradiction(claim_id, evidence_id)
        ids.append(evidence_id)
    return tuple(ids)


def _add_unresolved_gap(
    engine: Engine,
    claim_id: int,
    *,
    required_evidence_type: int = 99,
    rule_id: int = 1,
) -> int:
    return engine.add_gap(
        claim_id=claim_id,
        gap_type=1,
        required_evidence_type=required_evidence_type,
        severity=0.5,
        rule_id=rule_id,
    )


def _set_status(engine: Engine, claim_id: int, status: int) -> None:
    engine._claims[claim_id] = replace(engine._claims[claim_id], status=status)


class TestCountStrengthAveragingThreshold:
    """§36 AV/AW — name/source/threshold=2 preserved from PR19-E."""

    def test_count_modifier_helper_exists(self) -> None:
        engine = Engine()
        helper = getattr(engine, "_count_modifier_for_claim", None)
        assert callable(helper)

    def test_active_count_zero_returns_one(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)

        assert engine._count_modifier_for_claim(claim_id) == pytest.approx(1.0)

    def test_active_count_one_returns_one_even_when_strength_is_high(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (1.0,))

        # active 1은 PR11-C freshness 영역이다. count는 개입하지 않는다.
        assert engine._count_modifier_for_claim(claim_id) == pytest.approx(1.0)

    def test_active_count_two_enters_count_modifier(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.8, 0.8))

        assert engine._count_modifier_for_claim(claim_id) == pytest.approx(0.8)


class TestCountStrengthAveragingContinuous:
    """§36 AX/AY/BB — continuous average-strength behavior."""

    def test_active_two_average_zero_returns_one(self) -> None:
        """빈 강도의 contradiction 은 repeated pressure 가 아니다."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.0, 0.0))

        assert engine._count_modifier_for_claim(claim_id) == pytest.approx(1.0)

    def test_active_two_average_point_four_returns_point_nine(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.4, 0.4))

        assert engine._count_modifier_for_claim(claim_id) == pytest.approx(0.9)

    def test_active_two_average_point_eight_preserves_pr19_center(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.8, 0.8))

        # avg 0.8 → 1.0 - 0.8 × 0.25 = 0.8
        # PR19-E binary 0.8 중심점 자연 재현.
        assert engine._count_modifier_for_claim(claim_id) == pytest.approx(0.8)

    def test_active_two_average_one_returns_point_seven_five(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (1.0, 1.0))

        assert engine._count_modifier_for_claim(claim_id) == pytest.approx(0.75)

    def test_active_three_uses_average_strength_not_count_tier(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.2, 0.4, 1.0))

        # avg = 1.6 / 3 = 0.533333...
        # modifier = 1.0 - avg × 0.25 = 0.866666...
        assert engine._count_modifier_for_claim(claim_id) == pytest.approx(
            1.0 - ((0.2 + 0.4 + 1.0) / 3.0) * 0.25
        )

    def test_average_is_order_independent(self) -> None:
        engine_a = Engine()
        _, claim_a = _candidate_claim(engine_a)
        _add_active_contradictions(engine_a, claim_a, (0.2, 0.6, 1.0))

        engine_b = Engine()
        _, claim_b = _candidate_claim(engine_b)
        _add_active_contradictions(engine_b, claim_b, (1.0, 0.2, 0.6))

        assert engine_a._count_modifier_for_claim(claim_a) == pytest.approx(
            engine_b._count_modifier_for_claim(claim_b)
        )


class TestCountStrengthAveragingBoundaries:
    """§36 AX — range [0.75, 1.0], no boost, no collapse."""

    def test_count_modifier_never_boosts_above_one(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.0, 0.0, 0.0))

        assert engine._count_modifier_for_claim(claim_id) <= 1.0

    def test_count_modifier_floor_is_point_seven_five(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (1.0, 1.0, 1.0, 1.0))

        assert engine._count_modifier_for_claim(claim_id) == pytest.approx(0.75)

    def test_count_modifier_is_inside_expected_range_for_sample_values(self) -> None:
        for strengths in (
            (0.0, 0.0),
            (0.4, 0.4),
            (0.8, 0.8),
            (1.0, 1.0),
            (0.1, 0.9, 1.0),
        ):
            engine = Engine()
            _, claim_id = _candidate_claim(engine)
            _add_active_contradictions(engine, claim_id, strengths)

            modifier = engine._count_modifier_for_claim(claim_id)
            assert 0.75 <= modifier <= 1.0


class TestCountStrengthAveragingComposition:
    """§36 formula shape — only count term changes."""

    def test_effective_active_two_zero_strength_no_longer_attenuates_by_count(self) -> None:
        """PR19-E natural expiry: strength 0/0 used to be ×0.8, now ×1.0."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_active_contradictions(engine, claim_id, (0.0, 0.0))

        result = engine.compute_effective_confidence(claim_id)

        # status 1.0 × freshness 1.0 × gap 1.0 × count 1.0 = 1.0
        assert result.value == pytest.approx(1.0)

    def test_effective_active_two_point_four_average_uses_continuous_count(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_active_contradictions(engine, claim_id, (0.4, 0.4))

        result = engine.compute_effective_confidence(claim_id)

        # freshness = 1.0 - 0.4 × 0.5 = 0.8
        # count     = 1.0 - 0.4 × 0.25 = 0.9
        assert result.value == pytest.approx(0.8 * 0.9)

    def test_effective_active_two_point_eight_preserves_center(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_active_contradictions(engine, claim_id, (0.8, 0.8))

        result = engine.compute_effective_confidence(claim_id)

        # freshness = 0.6, count = 0.8
        # This equals the PR19-E center behavior.
        assert result.value == pytest.approx(0.6 * 0.8)

    def test_effective_active_two_one_strength_uses_point_seven_five_count(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_active_contradictions(engine, claim_id, (1.0, 1.0))

        result = engine.compute_effective_confidence(claim_id)

        # freshness = 0.5, count = 0.75
        assert result.value == pytest.approx(0.5 * 0.75)

    def test_disputed_gap_zero_strength_repeated_pressure_removed(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_active_contradictions(engine, claim_id, (0.0, 0.0))
        _add_unresolved_gap(engine, claim_id)
        _set_status(engine, claim_id, CLAIM_STATUS_DISPUTED)

        result = engine.compute_effective_confidence(claim_id)

        # status = 0.5
        # freshness = 1.0
        # gap = 0.9 (PR23-M: 1 unresolved)
        # count = 1.0 (avg strength 0.0)
        assert result.value == pytest.approx(0.5 * 1.0 * 0.9 * 1.0)

    def test_full_seven_modifier_composition_uses_strength_averaged_count(self) -> None:
        engine = Engine()
        engine.register_rule(
            RuleDefinition(
                id=7,
                version=1,
                maturity=RULE_MATURITY_EXPERIMENTAL,
                prior_confidence=ScoreValue(0.5),
            )
        )
        _, claim_id = _candidate_claim(
            engine,
            base_confidence=1.0,
            rule_id=7,
            rule_version=1,
        )

        _add_active_contradictions(engine, claim_id, (1.0, 1.0))
        for required_type in (101, 102, 103):
            _add_unresolved_gap(
                engine,
                claim_id,
                required_evidence_type=required_type,
                rule_id=7,
            )

        # Evidence type modifier: direct supporting evidence, all hint-only.
        engine.register_hint_evidence_types((900,))
        _evidence(engine, claim_id, evidence_type=900, strength=0.2)

        _set_status(engine, claim_id, CLAIM_STATUS_DISPUTED)

        result = engine.compute_effective_confidence(claim_id)

        # PR26-R §38.6 (BM): firing_count 0 → maturity_ratio 0.0 → rule_stats 0.8
        # (PR20-F binary 0.9 자연 만료).
        # status        = 0.5
        # freshness     = 0.5  (most recent active contradiction strength 1.0)
        # gap           = 0.7  (PR23-M: 3+ unresolved gaps)
        # count         = 0.75 (PR24-N: avg strength 1.0)
        # rule_stats    = 0.8  (PR26-R continuous: registered rule, firing_count 0)
        # evidence_type = 0.9  (hint-only direct evidence)
        assert result.value == pytest.approx(
            0.5 * 0.5 * 0.7 * 0.75 * 0.8 * 0.9
        )


class TestCountStrengthAveragingSourceSemantics:
    """§36 AV/AW/BB — source is active contradiction set."""

    def test_resolved_contradictions_are_excluded_from_average(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev1, ev2, ev3 = _add_active_contradictions(engine, claim_id, (1.0, 1.0, 0.0))

        engine.register_contradiction_resolution(claim_id, ev1)
        engine.register_contradiction_resolution(claim_id, ev2)

        # active only ev3 → active count 1 → count modifier 1.0
        assert engine._count_modifier_for_claim(claim_id) == pytest.approx(1.0)

    def test_direct_non_contradiction_evidence_is_not_counted(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.8, 0.8))
        _evidence(engine, claim_id, strength=1.0)  # direct supporting evidence only

        # average is still (0.8 + 0.8) / 2
        assert engine._count_modifier_for_claim(claim_id) == pytest.approx(0.8)

    def test_freshness_and_count_roles_remain_separate(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_active_contradictions(engine, claim_id, (0.0, 1.0))

        result = engine.compute_effective_confidence(claim_id)

        # freshness sees most recent active only: 1.0 → 0.5
        # count sees average of active set: (0.0 + 1.0) / 2 = 0.5 → 0.875
        assert result.value == pytest.approx(0.5 * 0.875)


class TestCountStrengthAveragingNoStateMutation:
    """§36 — compute/helper are read-only."""

    def test_count_helper_does_not_mutate_snapshot(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.4, 0.4))

        before = engine.to_snapshot()
        engine._count_modifier_for_claim(claim_id)
        after = engine.to_snapshot()

        assert before == after

    def test_compute_does_not_mutate_snapshot(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.4, 0.4))

        before = engine.to_snapshot()
        engine.compute_effective_confidence(claim_id)
        after = engine.to_snapshot()

        assert before == after

    def test_lifecycle_history_unchanged_after_compute(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.4, 0.4))

        before = engine.claim_lifecycle_history(claim_id)
        engine.compute_effective_confidence(claim_id)
        after = engine.claim_lifecycle_history(claim_id)

        assert before == after

    def test_contradiction_sets_unchanged_after_compute(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.4, 0.4))

        before = engine.active_contradictions_for_claim(claim_id)
        engine.compute_effective_confidence(claim_id)
        after = engine.active_contradictions_for_claim(claim_id)

        assert before == after


class TestCountStrengthAveragingSnapshot:
    """§36 BA — no snapshot schema bump; behavior round-trips."""

    def test_snapshot_schema_version_stays_two(self) -> None:
        engine = Engine()
        assert engine.to_snapshot()["schema_version"] == 2

    def test_roundtrip_preserves_strength_averaged_count_behavior(self) -> None:
        original = Engine()
        _, claim_id = _candidate_claim(original, base_confidence=1.0)
        _add_active_contradictions(original, claim_id, (0.4, 0.4))

        restored = Engine.from_snapshot(original.to_snapshot())

        assert restored.compute_effective_confidence(claim_id).value == pytest.approx(
            0.8 * 0.9
        )

    def test_roundtrip_preserves_active_contradiction_strengths(self) -> None:
        original = Engine()
        _, claim_id = _candidate_claim(original)
        ev1, ev2 = _add_active_contradictions(original, claim_id, (0.4, 0.8))

        restored = Engine.from_snapshot(original.to_snapshot())

        assert restored.get_evidence(ev1).strength.value == pytest.approx(0.4)
        assert restored.get_evidence(ev2).strength.value == pytest.approx(0.8)

    def test_snapshot_shape_does_not_add_count_state(self) -> None:
        engine = Engine()
        snapshot = engine.to_snapshot()

        assert "count_modifier" not in snapshot
        assert "count_strength_penalty_weight" not in snapshot
        assert "count_strengths" not in snapshot


class TestCountStrengthAveragingPrivateAndPublicSurface:
    """§36 AZ/BA — private constant, no public namespace expansion."""

    def test_count_strength_penalty_weight_private_constant_exists_in_engine(self) -> None:
        assert getattr(
            confidence_module,
            "_COUNT_STRENGTH_PENALTY_WEIGHT",
            None,
        ) == pytest.approx(0.25)

    def test_old_count_penalty_modifier_removed_from_engine(self) -> None:
        assert not hasattr(engine_module, "_COUNT_PENALTY_MODIFIER")

    def test_count_strength_penalty_weight_not_publicly_exported(self) -> None:
        names = [
            "_COUNT_STRENGTH_PENALTY_WEIGHT",
            "COUNT_STRENGTH_PENALTY_WEIGHT",
            "_COUNT_PENALTY_MODIFIER",
            "COUNT_PENALTY_MODIFIER",
        ]
        for name in names:
            assert not hasattr(ragcore, name)
            assert name not in getattr(ragcore, "__all__", [])

    def test_count_strength_penalty_weight_not_in_types_module(self) -> None:
        names = [
            "_COUNT_STRENGTH_PENALTY_WEIGHT",
            "COUNT_STRENGTH_PENALTY_WEIGHT",
            "_COUNT_PENALTY_MODIFIER",
            "COUNT_PENALTY_MODIFIER",
        ]
        for name in names:
            assert not hasattr(types_module, name)

    def test_no_new_claim_status_public_constants(self) -> None:
        assert CLAIM_STATUS_CANDIDATE == 0
        assert CLAIM_STATUS_CONFIRMED == 1
        assert CLAIM_STATUS_REFUTED == 2
        assert CLAIM_STATUS_DISPUTED == 3


class TestCountStrengthAveragingRegressionBoundaries:
    """PR11-C / PR23-M / PR20-F / PR21-L / lifecycle/refute boundaries."""

    def test_pr11c_freshness_active_one_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_active_contradictions(engine, claim_id, (1.0,))

        result = engine.compute_effective_confidence(claim_id)

        # active 1 → freshness 0.5, count 1.0
        assert result.value == pytest.approx(0.5)

    def test_pr23m_gap_tier_unchanged_without_active_contradictions(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=100)

        result = engine.compute_effective_confidence(claim_id)

        # PR23-M: 2 unresolved gaps → gap modifier 0.8
        assert result.value == pytest.approx(0.8)

    def test_pr20f_rule_stats_modifier_meaning_preserved(self) -> None:
        """PR20-F 의 "firing_count attenuation 적용" 의미 보존,
        PR26-R §38 으로 강도만 정밀화 (firing 0 → 0.8 continuous).

        PR20-F threshold=2 구조는 보존된다 (firing 2+ → 1.0).
        PR26-R §38.6 (BM): firing_count 0 → maturity_ratio 0.0 → 0.8.
        PR20-F binary 0.9 가 firing == 0 케이스에서 자연 만료.
        """
        engine = Engine()
        engine.register_rule(
            RuleDefinition(
                id=7,
                version=1,
                maturity=RULE_MATURITY_EXPERIMENTAL,
                prior_confidence=ScoreValue(0.5),
            )
        )
        _, claim_id = _candidate_claim(
            engine,
            base_confidence=1.0,
            rule_id=7,
            rule_version=1,
        )

        result = engine.compute_effective_confidence(claim_id)

        # PR26-R continuous: firing_count 0 → 0.8 (PR20-F binary 0.9 자연 만료)
        assert result.value == pytest.approx(0.8)

    def test_pr21l_evidence_type_modifier_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        engine.register_hint_evidence_types((900,))
        _evidence(engine, claim_id, evidence_type=900, strength=0.5)

        result = engine.compute_effective_confidence(claim_id)

        # hint-only direct evidence → evidence_type modifier 0.9
        assert result.value == pytest.approx(0.9)

    def test_pr22s_strict_validation_unchanged(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([1, "2", 3])

        assert engine.to_snapshot()["hint_evidence_types"] == []

    def test_pr10a_refute_disputed_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.9,))
        _set_status(engine, claim_id, CLAIM_STATUS_CONFIRMED)

        assert engine.dispute_claim_if_ready(claim_id) is True
        assert engine.refute_disputed_claim_if_ready(claim_id) is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    def test_pr11b_refute_by_freshness_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        _add_active_contradictions(engine, claim_id, (0.9,))
        _set_status(engine, claim_id, CLAIM_STATUS_CONFIRMED)

        assert engine.dispute_claim_if_ready(claim_id) is True
        assert engine.refute_disputed_claim_if_ready_by_freshness(claim_id) is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    def test_pr9a_active_contradictions_asc_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev1, ev2 = _add_active_contradictions(engine, claim_id, (0.4, 0.8))

        assert engine.active_contradictions_for_claim(claim_id) == (ev1, ev2)

    def test_effective_confidence_never_exceeds_base(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        _add_active_contradictions(engine, claim_id, (0.0, 0.0))

        result = engine.compute_effective_confidence(claim_id)

        assert result.value <= 0.7
