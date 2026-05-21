"""Tests for PR30-P — Consumer policy guide usage boundary.

PR30-P §42:
    Engine outputs are decision-support signals.
    They are not domain verdicts by themselves.

This file is intentionally an all-pass usage invariant test file.

PR30-P is a boundary/spec PR. The tests verify that current public behavior
already satisfies the §42 consumer interpretation policy:

    - effective_confidence is a computed signal, not a calibrated truth probability
    - lifecycle status remains separate from effective confidence
    - observed_precision remains bounded and no-boost
    - false_positive_rate remains ignored
    - snapshot round-trip preserves state (PR17 정신)
    - rule_version is reproducibility metadata, not quality (PR28-O 정신)
    - no file IO helpers / calibrated truth probability API / built-in HINT enum

Expected result:
    All tests pass immediately.
"""

from __future__ import annotations

import pytest

import ragcore
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


RULE_ID = 4200
RULE_VERSION = 1


def _engine_with_claim(
    *,
    base_confidence: float = 0.8,
    status: int = CLAIM_STATUS_CANDIDATE,
    rule_id: int = 0,
    rule_version: int = 0,
) -> tuple[Engine, int]:
    engine = Engine()
    subject_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=subject_id,
        claim_type=1,
        rule_id=rule_id,
        rule_version=rule_version,
        reason_code=1,
        base_confidence=base_confidence,
        status=status,
    )
    return engine, claim_id


def _register_rule(
    engine: Engine,
    *,
    rule_id: int = RULE_ID,
    rule_version: int = RULE_VERSION,
) -> None:
    engine.register_rule(
        RuleDefinition(
            id=rule_id,
            version=rule_version,
            maturity=RULE_MATURITY_EXPERIMENTAL,
            prior_confidence=ScoreValue(0.8),
        )
    )


class TestConsumerPolicyEffectiveConfidence:
    """§42.3 — effective_confidence display policy."""

    def test_effective_confidence_is_score_signal_and_does_not_mutate_status(self) -> None:
        engine, claim_id = _engine_with_claim(base_confidence=0.8)

        before_status = engine.get_claim(claim_id).status
        score = engine.compute_effective_confidence(claim_id)

        assert isinstance(score, ScoreValue)
        assert score.value == pytest.approx(0.8)
        assert engine.get_claim(claim_id).status == before_status

    def test_refuted_status_dominates_effective_confidence_to_zero(self) -> None:
        engine, claim_id = _engine_with_claim(
            base_confidence=0.8,
            status=CLAIM_STATUS_REFUTED,
        )

        score = engine.compute_effective_confidence(claim_id)

        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED
        assert score.value == pytest.approx(0.0)

    def test_disputed_status_and_confidence_are_separate_signals(self) -> None:
        engine, claim_id = _engine_with_claim(
            base_confidence=0.8,
            status=CLAIM_STATUS_DISPUTED,
        )

        score = engine.compute_effective_confidence(claim_id)

        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED
        assert score.value == pytest.approx(0.4)

    def test_confirmed_status_does_not_mean_absolute_truth_or_confidence_one(self) -> None:
        engine, claim_id = _engine_with_claim(
            base_confidence=0.8,
            status=CLAIM_STATUS_CONFIRMED,
        )

        score = engine.compute_effective_confidence(claim_id)

        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED
        assert score.value == pytest.approx(0.8)


class TestConsumerPolicyObservedPrecision:
    """§42.8 — observed_precision is bounded no-boost adjustment signal."""

    def test_observed_precision_none_keeps_precision_modifier_neutral(self) -> None:
        engine, claim_id = _engine_with_claim(
            base_confidence=0.8,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
        )
        _register_rule(engine)

        score = engine.compute_effective_confidence(claim_id)

        # firing_count=0 -> maturity 0.8
        # observed_precision=None -> precision 1.0
        assert score.value == pytest.approx(0.8 * 0.8)

    def test_observed_precision_zero_is_bounded_attenuation_not_quality_verdict(self) -> None:
        engine, claim_id = _engine_with_claim(
            base_confidence=0.8,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
        )
        _register_rule(engine)
        engine.update_rule_stats(
            RULE_ID,
            RULE_VERSION,
            firing_delta=2,
            observed_precision=ScoreValue(0.0),
        )

        score = engine.compute_effective_confidence(claim_id)

        # firing_count=2 -> maturity 1.0
        # observed_precision=0.0 -> precision 0.9
        assert score.value == pytest.approx(0.8 * 0.9)

    def test_observed_precision_one_does_not_boost_above_base_path(self) -> None:
        engine, claim_id = _engine_with_claim(
            base_confidence=0.8,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
        )
        _register_rule(engine)
        engine.update_rule_stats(
            RULE_ID,
            RULE_VERSION,
            firing_delta=2,
            observed_precision=ScoreValue(1.0),
        )

        score = engine.compute_effective_confidence(claim_id)

        # firing_count=2 -> maturity 1.0
        # observed_precision=1.0 -> precision 1.0
        # no boost above base path
        assert score.value == pytest.approx(0.8)

    def test_false_positive_rate_remains_ignored_by_consumer_policy_boundary(self) -> None:
        engine_a, claim_a = _engine_with_claim(
            base_confidence=0.8,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
        )
        engine_b, claim_b = _engine_with_claim(
            base_confidence=0.8,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
        )
        _register_rule(engine_a)
        _register_rule(engine_b)

        engine_a.update_rule_stats(
            RULE_ID,
            RULE_VERSION,
            firing_delta=2,
            observed_precision=ScoreValue(1.0),
            false_positive_rate=ScoreValue(0.0),
        )
        engine_b.update_rule_stats(
            RULE_ID,
            RULE_VERSION,
            firing_delta=2,
            observed_precision=ScoreValue(1.0),
            false_positive_rate=ScoreValue(1.0),
        )

        assert engine_a.compute_effective_confidence(claim_a).value == pytest.approx(
            engine_b.compute_effective_confidence(claim_b).value
        )


class TestConsumerPolicySnapshot:
    """§42.6 — snapshot persistence is state preservation, not re-judgment."""

    def test_snapshot_schema_version_remains_two(self) -> None:
        engine, _claim_id = _engine_with_claim()

        snapshot = engine.to_snapshot()

        assert snapshot["schema_version"] == 2

    def test_snapshot_roundtrip_preserves_state_not_rejudgment(self) -> None:
        engine, claim_id = _engine_with_claim(
            base_confidence=0.8,
            status=CLAIM_STATUS_DISPUTED,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
        )
        _register_rule(engine)
        engine.update_rule_stats(
            RULE_ID,
            RULE_VERSION,
            firing_delta=2,
            observed_precision=ScoreValue(0.5),
        )

        before_score = engine.compute_effective_confidence(claim_id).value
        snapshot = engine.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        assert restored.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED
        assert restored.get_claim(claim_id).created_by_rule == RULE_ID
        assert restored.get_claim(claim_id).created_by_rule_version == RULE_VERSION
        assert restored.compute_effective_confidence(claim_id).value == pytest.approx(
            before_score
        )


class TestConsumerPolicyRuleVersion:
    """§42.7 — rule_version is reproducibility metadata, not quality."""

    def test_rule_version_is_retained_as_reproducibility_metadata(self) -> None:
        engine, claim_id = _engine_with_claim(
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
        )

        claim = engine.get_claim(claim_id)

        assert claim.created_by_rule == RULE_ID
        assert claim.created_by_rule_version == RULE_VERSION

    def test_rule_version_value_alone_does_not_change_confidence(self) -> None:
        engine = Engine()
        subject_id = engine.add_entity(entity_type=1)
        claim_v1 = engine.add_claim(
            subject_id=subject_id,
            claim_type=1,
            rule_id=RULE_ID,
            rule_version=1,
            reason_code=1,
            base_confidence=0.8,
        )
        claim_v2 = engine.add_claim(
            subject_id=subject_id,
            claim_type=1,
            rule_id=RULE_ID,
            rule_version=2,
            reason_code=1,
            base_confidence=0.8,
        )

        assert engine.compute_effective_confidence(claim_v1).value == pytest.approx(
            engine.compute_effective_confidence(claim_v2).value
        )


class TestConsumerPolicyNoImplementationChange:
    """§42.10 / §42.11 — no new public API, no file IO, no truth probability."""

    def test_engine_does_not_expose_file_io_snapshot_helpers(self) -> None:
        assert not hasattr(Engine, "save_snapshot")
        assert not hasattr(Engine, "load_snapshot")
        assert not hasattr(Engine, "to_file")
        assert not hasattr(Engine, "from_file")

    def test_engine_does_not_expose_calibrated_truth_probability_api(self) -> None:
        assert not hasattr(Engine, "compute_truth_probability")
        assert not hasattr(Engine, "truth_probability")
        assert not hasattr(Engine, "calibrated_probability")

    def test_public_namespace_still_has_no_builtin_hint_evidence_type_enum(self) -> None:
        assert not hasattr(ragcore, "EVIDENCE_TYPE_HINT")
        assert "EVIDENCE_TYPE_HINT" not in ragcore.__all__
