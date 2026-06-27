"""Tests for PR29-R — Observed precision modifier MVP.

PR29-R §41:
    Observed precision is a bounded adjustment signal, not a rule quality verdict.

Conservative:
    Observed precision is optional evidence for rule maturity, not ground truth.

Formula refinement:
    Before PR29-R:
        rule_stats_modifier = maturity_modifier (PR26-R)
    After PR29-R:
        rule_stats_modifier = maturity_modifier × precision_modifier

        maturity_modifier (PR26-R, unchanged):
            firing_count < 0  → 0.8
            firing_count == 0 → 0.8
            firing_count == 1 → 0.9
            firing_count >= 2 → 1.0

        precision_modifier (PR29-R, new):
            observed_precision is None → 1.0
            observed_precision value p → 0.9 + p × 0.1
            range [0.9, 1.0] (no boost)

123차 expected fail pattern:
    - precision attenuation cases (p=0.0 / 0.5)
    - maturity × precision composition (firing 0 + p, firing 1 + p)
    - status × precision interaction (disputed + p=0.0)
    - other-modifier × precision composition
    - snapshot round-trip with computed behavior under p attenuation
    - private constants missing
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
    RULE_MATURITY_EXPERIMENTAL,
    RuleDefinition,
    ScoreValue,
)


def _register_rule(
    engine: Engine,
    *,
    rule_id: int = 100,
    rule_version: int = 1,
    prior_confidence: float = 0.6,
) -> None:
    engine.register_rule(
        RuleDefinition(
            id=rule_id,
            version=rule_version,
            maturity=RULE_MATURITY_EXPERIMENTAL,
            prior_confidence=ScoreValue(prior_confidence),
        )
    )


def _set_firing_count(
    engine: Engine, *,
    rule_id: int = 100, rule_version: int = 1, count: int,
) -> None:
    current = engine._rule_stats[(rule_id, rule_version)].firing_count
    delta = count - current
    if delta != 0:
        engine.update_rule_stats(
            rule_id=rule_id, rule_version=rule_version, firing_delta=delta,
        )


def _set_precision(
    engine: Engine, *,
    rule_id: int = 100, rule_version: int = 1, value: float | None,
) -> None:
    if value is None:
        return  # Do not call update_rule_stats with None (signature treats None as "no change").
    engine.update_rule_stats(
        rule_id=rule_id, rule_version=rule_version,
        observed_precision=ScoreValue(value),
    )


def _set_fpr(
    engine: Engine, *,
    rule_id: int = 100, rule_version: int = 1, value: float,
) -> None:
    engine.update_rule_stats(
        rule_id=rule_id, rule_version=rule_version,
        false_positive_rate=ScoreValue(value),
    )


def _claim_with_rule(
    engine: Engine, *,
    rule_id: int = 100, rule_version: int = 1, base_confidence: float = 1.0,
) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id, claim_type=1,
        rule_id=rule_id, rule_version=rule_version, reason_code=0,
        base_confidence=base_confidence,
    )
    return entity_id, claim_id


def _evidence(
    engine: Engine, claim_id: int, *,
    evidence_type: int = 42, strength: float = 0.5,
) -> int:
    return engine.add_evidence(
        claim_id=claim_id, raw_ref_id=0,
        evidence_type=evidence_type, strength=strength,
    )


def _unresolved_gap(
    engine: Engine, claim_id: int, *,
    required_evidence_type: int = 99, rule_id: int = 100,
) -> int:
    return engine.add_gap(
        claim_id=claim_id, gap_type=1,
        required_evidence_type=required_evidence_type,
        severity=0.5, rule_id=rule_id,
    )


# ---- A. None preserves PR26-R (Sub-decision A) -----------------------------


class TestObservedPrecisionNonePreservesPR26R:
    """§41.11 A — observed_precision is None preserves PR26-R behavior."""

    def test_none_firing_zero_returns_zero_point_eight(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        # observed_precision is None by default (RuleStats init)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        # PR26-R: firing 0 → 0.8, precision None → 1.0 → 0.8 × 1.0 = 0.8
        assert result.value == pytest.approx(0.8)

    def test_none_firing_one_returns_zero_point_nine(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.9)

    def test_none_firing_two_returns_one(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)


# ---- B. Precision modifier values (Sub-decision B) -------------------------


class TestObservedPrecisionModifierValues:
    """§41.11 B — precision_modifier range mapping for saturated maturity."""

    def test_saturated_maturity_precision_zero_returns_zero_point_nine(self) -> None:
        """firing 2 (mature) + p 0.0 → 1.0 × 0.9 = 0.9."""
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _set_precision(engine, value=0.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        # rule_stats = 1.0 × 0.9 = 0.9
        assert result.value == pytest.approx(0.9)

    def test_saturated_maturity_precision_half_returns_zero_point_nine_five(self) -> None:
        """firing 2 + p 0.5 → 1.0 × 0.95 = 0.95."""
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _set_precision(engine, value=0.5)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.95)

    def test_saturated_maturity_precision_one_returns_one(self) -> None:
        """firing 2 + p 1.0 → 1.0 × 1.0 = 1.0."""
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _set_precision(engine, value=1.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)


# ---- C. Maturity × precision composition (Sub-decision C) ------------------


class TestObservedPrecisionComposesWithMaturity:
    """§41.11 C — maturity_modifier × precision_modifier composition."""

    def test_firing_zero_precision_zero_returns_zero_point_seven_two(self) -> None:
        """firing 0 + p 0.0 → 0.8 × 0.9 = 0.72."""
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_precision(engine, value=0.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.72)

    def test_firing_one_precision_half_returns_zero_point_eight_five_five(self) -> None:
        """firing 1 + p 0.5 → 0.9 × 0.95 = 0.855."""
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=1)
        _set_precision(engine, value=0.5)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.855)

    def test_firing_two_precision_one_returns_one(self) -> None:
        """firing 2 + p 1.0 → 1.0 × 1.0 = 1.0 (full saturation)."""
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _set_precision(engine, value=1.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)


# ---- D. No boost (Sub-decision D) ------------------------------------------


class TestObservedPrecisionNoBoost:
    """§41.11 D — rule_stats_modifier never exceeds 1.0."""

    def test_high_precision_never_boosts_above_base(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _set_precision(engine, value=1.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=0.6,
        )
        result = engine.compute_effective_confidence(claim_id)
        # base 0.6 × rule_stats 1.0 = 0.6 (not boosted to e.g. 0.7)
        assert result.value == pytest.approx(0.6)
        assert result.value <= 0.6

    def test_very_high_firing_with_max_precision_still_no_boost(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=100)
        _set_precision(engine, value=1.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=0.6,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value <= 0.6 + 1e-9


# ---- E/F. Status dominance (Sub-decisions E & F) ---------------------------


class TestObservedPrecisionDoesNotOverrideStatus:
    """§41.11 E/F — refuted/disputed dominance preserved with precision."""

    def test_refuted_with_max_precision_returns_zero(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _set_precision(engine, value=1.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.0)

    def test_disputed_with_saturated_firing_and_low_precision(self) -> None:
        """disputed + firing 2 + p 0.0 → 0.5 × (1.0 × 0.9) = 0.45."""
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _set_precision(engine, value=0.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.45)

    def test_disputed_with_max_precision_still_disputed(self) -> None:
        """disputed cannot be erased by precision = 1.0."""
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _set_precision(engine, value=1.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # 1.0 × 0.5 × 1.0 × 1.0 × 1.0 × (1.0 × 1.0) × 1.0 = 0.5
        assert result.value == pytest.approx(0.5)


# ---- G. Other modifiers preserved (Sub-decision G) -------------------------


class TestObservedPrecisionDoesNotAffectOtherModifiers:
    """§41.11 G — freshness/gap/count/evidence_type unchanged by precision."""

    def test_freshness_modifier_unchanged(self) -> None:
        """confirmed + active 1 contradiction (s=0.8) + firing 2 + p 0.0
        → 1.0 × 1.0 (conf) × 0.6 (freshness) × 1.0 (no gap) × 1.0 (count)
          × (1.0 × 0.9) (rule_stats with p=0.0) × 1.0 (no hint) = 0.54.
        """
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _set_precision(engine, value=0.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        ev = _evidence(engine, claim_id, strength=0.8)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # 1.0 × 0.6 × 0.9 = 0.54
        assert result.value == pytest.approx(0.54)

    def test_gap_modifier_unchanged(self) -> None:
        """candidate + 1 unresolved gap + firing 2 + p 0.0
        → 1.0 × 1.0 × 1.0 × 0.9 (gap tier 1) × 1.0 × 0.9 (rule_stats) × 1.0
        = 0.81.
        """
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _set_precision(engine, value=0.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        _unresolved_gap(engine, claim_id)
        result = engine.compute_effective_confidence(claim_id)
        # gap 0.9 × rule_stats 0.9 = 0.81
        assert result.value == pytest.approx(0.81)


# ---- H. false_positive_rate ignored (Sub-decision H) -----------------------


class TestFalsePositiveRateStillIgnored:
    """§41.11 H — false_positive_rate is OOS in PR29-R."""

    def test_fpr_zero_does_not_change_effective_confidence(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        # observed_precision still None — only FPR is set
        _set_fpr(engine, value=0.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        # rule_stats = maturity 1.0 × precision 1.0 (None) = 1.0
        assert result.value == pytest.approx(1.0)

    def test_fpr_one_does_not_change_effective_confidence(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _set_fpr(engine, value=1.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        # FPR is ignored; behavior matches None precision case
        assert result.value == pytest.approx(1.0)

    def test_fpr_value_does_not_interfere_with_precision_attenuation(self) -> None:
        """precision 0.0 should attenuate regardless of FPR."""
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_firing_count(engine, count=2)
        _set_precision(engine, value=0.0)
        _set_fpr(engine, value=0.5)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        # rule_stats = 1.0 × 0.9 = 0.9 (FPR ignored)
        assert result.value == pytest.approx(0.9)


# ---- I. Snapshot round-trip (Sub-decision I) -------------------------------


class TestObservedPrecisionSnapshotRoundTrip:
    """§41.11 I — snapshot preserves observed_precision and computed confidence."""

    def test_snapshot_schema_version_remains_two(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_precision(engine, value=0.0)
        assert engine.to_snapshot()["schema_version"] == 2

    def test_round_trip_preserves_observed_precision_value(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_precision(engine, value=0.5)

        restored = Engine.from_snapshot(engine.to_snapshot())
        restored_stats = restored.get_rule_stats(100, 1)

        assert restored_stats.observed_precision is not None
        assert restored_stats.observed_precision.value == pytest.approx(0.5)

    def test_round_trip_preserves_computed_effective_confidence_with_precision(self) -> None:
        """precision 0.0 + firing 0 → 0.72.

        restored engine 도 동일 값 계산해야 한다.
        """
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        _set_precision(engine, value=0.0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=100, rule_version=1, base_confidence=1.0,
        )
        before = engine.compute_effective_confidence(claim_id).value
        restored = Engine.from_snapshot(engine.to_snapshot())
        after = restored.compute_effective_confidence(claim_id).value

        assert before == pytest.approx(0.72)
        assert after == pytest.approx(before)


# ---- J. Public namespace / private constants (Sub-decision J) --------------


class TestObservedPrecisionPublicBoundary:
    """§41.11 J — no new public exports; private constants exist in engine."""

    def test_precision_base_private_constant_exists_in_engine(self) -> None:
        val = getattr(confidence_module, "_RULE_STATS_PRECISION_BASE", None)
        assert val == pytest.approx(0.9)

    def test_precision_range_private_constant_exists_in_engine(self) -> None:
        val = getattr(confidence_module, "_RULE_STATS_PRECISION_RANGE", None)
        assert val == pytest.approx(0.1)

    def test_precision_constants_not_publicly_exported(self) -> None:
        forbidden = [
            "_RULE_STATS_PRECISION_BASE",
            "_RULE_STATS_PRECISION_RANGE",
            "RULE_STATS_PRECISION_BASE",
            "RULE_STATS_PRECISION_RANGE",
        ]
        for name in forbidden:
            assert not hasattr(ragcore, name)
            assert not hasattr(types_module, name)

    def test_no_new_public_export_for_precision(self) -> None:
        all_attr = getattr(ragcore, "__all__", None)
        if all_attr is not None:
            for name in all_attr:
                assert not name.startswith(
                    ("_RULE_STATS_PRECISION", "RULE_STATS_PRECISION")
                )

    def test_rule_stats_dataclass_fields_unchanged(self) -> None:
        from dataclasses import fields
        names = {f.name for f in fields(types_module.RuleStats)}
        expected = {
            "rule_id", "rule_version", "firing_count",
            "confirmed_true_count", "confirmed_false_count",
            "observed_precision", "false_positive_rate",
        }
        assert names == expected
