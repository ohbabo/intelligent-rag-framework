"""Tests for PR31-S — AI-readable usage recipe boundary.

PR31-S §43:
    PR27-P §39  call boundary    (how to call the Engine)
    PR30-P §42  read boundary    (how to read Engine outputs)
    PR31-S §43  usage recipe     (what order to call methods in)

This file is intentionally an all-pass usage recipe test file.

PR31-S is a boundary/spec PR. The tests execute the six canonical §43
usage scenarios through the existing public Engine API and lock the
recipe invariants:

    Recipe A — candidate confirmation
    Recipe B — disputed review
    Recipe C — refutation
    Recipe D — snapshot restore
    Recipe E — observed_precision feedback
    Recipe F — hint evidence type cycle
    Read-side purity
    Method surface invariance

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


RULE_ID = 4300
RULE_VERSION = 1
HINT_TYPE = 9300
NON_HINT_TYPE = 1300


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


def _candidate_claim(
    engine: Engine,
    *,
    base_confidence: float = 0.8,
    rule_id: int = 0,
    rule_version: int = 0,
) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=rule_id,
        rule_version=rule_version,
        reason_code=1,
        base_confidence=base_confidence,
        status=CLAIM_STATUS_CANDIDATE,
    )
    return entity_id, claim_id


def _confirmed_claim(
    engine: Engine,
    *,
    base_confidence: float = 1.0,
) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=0,
        rule_version=0,
        reason_code=1,
        base_confidence=base_confidence,
        status=CLAIM_STATUS_CONFIRMED,
    )
    return entity_id, claim_id


def _evidence(
    engine: Engine,
    claim_id: int,
    *,
    evidence_type: int = NON_HINT_TYPE,
    strength: float = 0.5,
) -> int:
    return engine.add_evidence(
        claim_id=claim_id,
        raw_ref_id=0,
        evidence_type=evidence_type,
        strength=strength,
    )


def _gap(
    engine: Engine,
    claim_id: int,
    *,
    required_evidence_type: int = NON_HINT_TYPE,
    rule_id: int = 0,
) -> int:
    return engine.add_gap(
        claim_id=claim_id,
        gap_type=1,
        required_evidence_type=required_evidence_type,
        severity=0.5,
        rule_id=rule_id,
    )


# §43 invariant 8 — locked symbol set from PR30-P main 60bf492.
# PR73-M04 additive shift: EngineStateIdentity added.
# PR76-M07 additive shift: EffectiveConfidenceTrace added.
_PR30_BASELINE_PUBLIC_SYMBOLS: frozenset[str] = frozenset({
    "EffectiveConfidenceTrace",
    "CLAIM_STATUS_CANDIDATE",
    "CLAIM_STATUS_CONFIRMED",
    "CLAIM_STATUS_DISPUTED",
    "CLAIM_STATUS_REFUTED",
    "Claim",
    "ClaimLifecycleEvent",
    "Combinator",
    "CombinatorTrace",
    "Engine",
    "EngineStateIdentity",
    "Entity",
    "Evidence",
    "FiringTrace",
    "Gap",
    "KIND_CLAIM",
    "KIND_ENTITY",
    "KIND_EVIDENCE",
    "KIND_GAP",
    "KIND_OBSERVATION",
    "KIND_RELATION",
    "Observation",
    "Predicate",
    "PredicateTrace",
    "RULE_MATURITY_DEPRECATED",
    "RULE_MATURITY_EXPERIMENTAL",
    "RULE_MATURITY_STABLE",
    "Relation",
    "RequiredEvidenceTemplate",
    "RuleDefinition",
    "RuleOutputTemplate",
    "RuleSpec",
    "RuleStats",
    "ScoreValue",
    "TRACE_REASON_MATCH",
    "TRACE_REASON_MISMATCH",
    "TRACE_REASON_MISSING_FIELD",
    "TRACE_REASON_TYPE_MISMATCH",
    "compile_required_evidence",
    "compile_rule_condition",
    "compile_rule_definition",
    "compile_rule_output",
    "evaluate_condition",
    "evaluate_condition_with_trace",
    "fire_rule",
    "fire_rule_with_trace",
    "load_condition_tree",
    "load_rule_spec",
    "load_rule_spec_from_yaml",
    "register_rule_spec",
})


class TestRecipeCandidateConfirmation:
    """§43.3 Recipe A — candidate confirmation through public API."""

    def test_recipe_a_confirm_flow_promotes_candidate_to_confirmed(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)
        _gap(engine, claim_id, required_evidence_type=NON_HINT_TYPE)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=NON_HINT_TYPE,
            strength=0.7,
        )

        assert engine.resolve_gaps_for_evidence(evidence_id) == (1,)
        assert engine.confirm_claim_if_ready(claim_id) is True

        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    def test_recipe_a_score_is_positive_and_at_most_one(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)
        _gap(engine, claim_id, required_evidence_type=NON_HINT_TYPE)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=NON_HINT_TYPE,
            strength=0.7,
        )
        engine.resolve_gaps_for_evidence(evidence_id)
        engine.confirm_claim_if_ready(claim_id)

        score = engine.compute_effective_confidence(claim_id)

        # base 0.8 × status 1.0 × freshness 1.0 × gap 1.0
        # × count 1.0 × rule_stats 1.0 × evidence_type 1.0 = 0.8
        assert score.value == pytest.approx(0.8)
        assert 0.0 < score.value <= 1.0

    def test_recipe_a_lifecycle_history_records_confirm_transition(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)
        _gap(engine, claim_id, required_evidence_type=NON_HINT_TYPE)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=NON_HINT_TYPE,
            strength=0.7,
        )
        engine.resolve_gaps_for_evidence(evidence_id)
        engine.confirm_claim_if_ready(claim_id)

        history = engine.claim_lifecycle_history(claim_id)

        assert len(history) == 1
        assert history[0].from_status == CLAIM_STATUS_CANDIDATE
        assert history[0].to_status == CLAIM_STATUS_CONFIRMED
        assert history[0].transition == "confirm_if_ready"


class TestRecipeDisputedReview:
    """§43.4 Recipe B — disputed review through public API."""

    def test_recipe_b_dispute_flow_marks_claim_disputed(self) -> None:
        engine = Engine()
        _, claim_id = _confirmed_claim(engine, base_confidence=1.0)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=NON_HINT_TYPE,
            strength=0.6,
        )

        assert engine.register_contradiction(claim_id, evidence_id) is True
        assert engine.dispute_claim_if_ready(claim_id) is True

        assert engine.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED

    def test_recipe_b_score_reflects_status_half_modifier(self) -> None:
        engine = Engine()
        _, claim_id = _confirmed_claim(engine, base_confidence=1.0)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=NON_HINT_TYPE,
            strength=0.6,
        )
        engine.register_contradiction(claim_id, evidence_id)
        engine.dispute_claim_if_ready(claim_id)

        score = engine.compute_effective_confidence(claim_id)

        # base 1.0 × status disputed 0.5 × freshness (1.0 - 0.6*0.5)=0.7
        # × gap 1.0 × count 1.0 (<2 active) × rule_stats 1.0 × evidence_type 1.0 = 0.35
        assert score.value == pytest.approx(0.35)

    def test_recipe_b_lifecycle_history_records_dispute_transition(self) -> None:
        engine = Engine()
        _, claim_id = _confirmed_claim(engine, base_confidence=1.0)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=NON_HINT_TYPE,
            strength=0.6,
        )
        engine.register_contradiction(claim_id, evidence_id)
        engine.dispute_claim_if_ready(claim_id)

        history = engine.claim_lifecycle_history(claim_id)

        assert len(history) == 1
        assert history[0].from_status == CLAIM_STATUS_CONFIRMED
        assert history[0].to_status == CLAIM_STATUS_DISPUTED
        assert history[0].transition == "dispute_if_ready"


class TestRecipeRefutation:
    """§43.5 Recipe C — refutation through public API."""

    def test_recipe_c_refute_flow_marks_claim_refuted(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=NON_HINT_TYPE,
            strength=0.7,
        )

        assert engine.register_contradiction(claim_id, evidence_id) is True
        assert engine.refute_claim_if_ready(claim_id) is True

        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    def test_recipe_c_score_dominates_to_zero(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=NON_HINT_TYPE,
            strength=0.7,
        )
        engine.register_contradiction(claim_id, evidence_id)
        engine.refute_claim_if_ready(claim_id)

        score = engine.compute_effective_confidence(claim_id)

        assert score.value == pytest.approx(0.0)

    def test_recipe_c_lifecycle_history_records_refute_transition(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=NON_HINT_TYPE,
            strength=0.7,
        )
        engine.register_contradiction(claim_id, evidence_id)
        engine.refute_claim_if_ready(claim_id)

        history = engine.claim_lifecycle_history(claim_id)

        assert len(history) == 1
        assert history[0].from_status == CLAIM_STATUS_CANDIDATE
        assert history[0].to_status == CLAIM_STATUS_REFUTED
        assert history[0].transition == "refute_if_ready"


class TestRecipeSnapshotRestore:
    """§43.6 Recipe D — snapshot restore as state preservation."""

    def _setup_non_trivial_engine(self) -> tuple[Engine, int]:
        engine = Engine()
        _register_rule(engine)
        engine.register_hint_evidence_types({HINT_TYPE})

        _, claim_id = _candidate_claim(
            engine,
            base_confidence=0.8,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
        )
        _gap(engine, claim_id, required_evidence_type=HINT_TYPE, rule_id=RULE_ID)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=HINT_TYPE,
            strength=0.7,
        )
        engine.resolve_gaps_for_evidence(evidence_id)
        engine.confirm_claim_if_ready(claim_id)
        engine.update_rule_stats(
            RULE_ID,
            RULE_VERSION,
            firing_delta=2,
            observed_precision=ScoreValue(1.0),
        )
        return engine, claim_id

    def test_recipe_d_snapshot_roundtrip_preserves_status(self) -> None:
        engine, claim_id = self._setup_non_trivial_engine()

        snapshot = engine.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        assert restored.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    def test_recipe_d_snapshot_roundtrip_preserves_rule_pinning(self) -> None:
        engine, claim_id = self._setup_non_trivial_engine()

        restored = Engine.from_snapshot(engine.to_snapshot())

        restored_claim = restored.get_claim(claim_id)
        assert restored_claim.created_by_rule == RULE_ID
        assert restored_claim.created_by_rule_version == RULE_VERSION

    def test_recipe_d_snapshot_roundtrip_preserves_effective_confidence(self) -> None:
        engine, claim_id = self._setup_non_trivial_engine()

        before = engine.compute_effective_confidence(claim_id).value
        restored = Engine.from_snapshot(engine.to_snapshot())
        after = restored.compute_effective_confidence(claim_id).value

        assert after == pytest.approx(before)
        assert restored.to_snapshot() == engine.to_snapshot()


class TestRecipeObservedPrecisionFeedback:
    """§43.7 Recipe E — observed_precision feedback into rule_stats."""

    def _claim_with_rule(self, engine: Engine) -> int:
        _register_rule(engine)
        _, claim_id = _candidate_claim(
            engine,
            base_confidence=0.8,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
        )
        return claim_id

    def test_recipe_e_observed_precision_one_means_no_boost(self) -> None:
        engine = Engine()
        claim_id = self._claim_with_rule(engine)
        engine.update_rule_stats(
            RULE_ID,
            RULE_VERSION,
            firing_delta=2,
            observed_precision=ScoreValue(1.0),
        )

        score = engine.compute_effective_confidence(claim_id)

        # firing_count=2 -> maturity_modifier = 1.0
        # observed_precision=1.0 -> precision_modifier = 1.0
        # rule_stats_modifier = 1.0 (no boost above base path)
        assert score.value == pytest.approx(0.8)

    def test_recipe_e_observed_precision_zero_means_bounded_attenuation(self) -> None:
        engine = Engine()
        claim_id = self._claim_with_rule(engine)
        engine.update_rule_stats(
            RULE_ID,
            RULE_VERSION,
            firing_delta=2,
            observed_precision=ScoreValue(0.0),
        )

        score = engine.compute_effective_confidence(claim_id)

        # firing_count=2 -> maturity_modifier = 1.0
        # observed_precision=0.0 -> precision_modifier = 0.9 (floor)
        # rule_stats_modifier = 0.9
        assert score.value == pytest.approx(0.8 * 0.9)

    def test_recipe_e_observed_precision_none_keeps_precision_neutral(self) -> None:
        engine = Engine()
        claim_id = self._claim_with_rule(engine)

        score = engine.compute_effective_confidence(claim_id)

        # firing_count=0 -> maturity_modifier = 0.8 (floor)
        # observed_precision=None -> precision_modifier = 1.0 (neutral)
        # rule_stats_modifier = 0.8
        assert score.value == pytest.approx(0.8 * 0.8)


class TestRecipeHintEvidenceTypes:
    """§43.8 Recipe F — hint evidence type register / unregister / clear."""

    def _claim_with_hint_evidence(self, engine: Engine) -> int:
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _evidence(
            engine,
            claim_id,
            evidence_type=HINT_TYPE,
            strength=0.5,
        )
        return claim_id

    def test_recipe_f_register_attenuates_evidence_type_modifier(self) -> None:
        engine = Engine()
        claim_id = self._claim_with_hint_evidence(engine)

        score_before = engine.compute_effective_confidence(claim_id)
        engine.register_hint_evidence_types({HINT_TYPE})
        score_after = engine.compute_effective_confidence(claim_id)

        # before: no hint registered -> evidence_type_modifier = 1.0
        # after: HINT_TYPE registered, all evidence is hint -> evidence_type_modifier = 0.9
        assert score_before.value == pytest.approx(1.0)
        assert score_after.value == pytest.approx(0.9)

    def test_recipe_f_unregister_restores_evidence_type_modifier(self) -> None:
        engine = Engine()
        claim_id = self._claim_with_hint_evidence(engine)
        engine.register_hint_evidence_types({HINT_TYPE})

        engine.unregister_hint_evidence_types({HINT_TYPE})
        score_after_unregister = engine.compute_effective_confidence(claim_id)

        assert score_after_unregister.value == pytest.approx(1.0)

    def test_recipe_f_clear_resets_to_fresh_engine_state(self) -> None:
        engine = Engine()
        claim_id = self._claim_with_hint_evidence(engine)
        engine.register_hint_evidence_types({HINT_TYPE, HINT_TYPE + 1, HINT_TYPE + 2})

        engine.clear_hint_evidence_types()
        score_after_clear = engine.compute_effective_confidence(claim_id)

        assert score_after_clear.value == pytest.approx(1.0)


class TestReadSidePurity:
    """§43.9 — read-side methods do not mutate Engine state."""

    def _setup_engine(self) -> tuple[Engine, int]:
        engine = Engine()
        _register_rule(engine)
        _, claim_id = _candidate_claim(
            engine,
            base_confidence=0.8,
            rule_id=RULE_ID,
            rule_version=RULE_VERSION,
        )
        _gap(engine, claim_id, required_evidence_type=NON_HINT_TYPE, rule_id=RULE_ID)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=NON_HINT_TYPE,
            strength=0.7,
        )
        engine.resolve_gaps_for_evidence(evidence_id)
        engine.confirm_claim_if_ready(claim_id)
        engine.update_rule_stats(
            RULE_ID,
            RULE_VERSION,
            firing_delta=2,
            observed_precision=ScoreValue(0.5),
        )
        return engine, claim_id

    def test_compute_effective_confidence_does_not_mutate_snapshot(self) -> None:
        engine, claim_id = self._setup_engine()
        snapshot_before = engine.to_snapshot()

        _ = engine.compute_effective_confidence(claim_id)
        _ = engine.compute_effective_confidence(claim_id)
        _ = engine.compute_effective_confidence(claim_id)

        assert engine.to_snapshot() == snapshot_before

    def test_get_methods_do_not_mutate_snapshot(self) -> None:
        engine, claim_id = self._setup_engine()
        snapshot_before = engine.to_snapshot()

        _ = engine.get_claim(claim_id)
        _ = engine.evidences_for_claim(claim_id)
        _ = engine.gaps_for_claim(claim_id)
        _ = engine.contradictions_for_claim(claim_id)
        _ = engine.claim_lifecycle_history(claim_id)
        _ = engine.get_rule(RULE_ID, RULE_VERSION)
        _ = engine.get_rule_stats(RULE_ID, RULE_VERSION)

        assert engine.to_snapshot() == snapshot_before


class TestMethodSurfaceInvariance:
    """§43.9 / §43.11 — ragcore.__all__ unchanged from PR30-P main 60bf492."""

    def test_ragcore_all_matches_pr30p_baseline_exactly(self) -> None:
        current = frozenset(ragcore.__all__)

        assert current == _PR30_BASELINE_PUBLIC_SYMBOLS

    def test_ragcore_all_has_no_duplicate_symbols(self) -> None:
        assert len(ragcore.__all__) == len(set(ragcore.__all__))

    def test_ragcore_all_does_not_expose_recipe_helper_methods(self) -> None:
        # §43 is a recipe, not a new API surface.
        assert "use_recipe" not in ragcore.__all__
        assert "run_scenario" not in ragcore.__all__
        assert "explain" not in ragcore.__all__
        assert "ai_usage_guide" not in ragcore.__all__
        assert not hasattr(Engine, "use_recipe")
        assert not hasattr(Engine, "run_scenario")
        assert not hasattr(Engine, "explain")
        assert not hasattr(Engine, "ai_usage_guide")
