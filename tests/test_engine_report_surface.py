"""Tests for PR32-V — Report surface boundary.

PR32-V §44:
    PR27-P §39  call boundary    (how to call the Engine)
    PR30-P §42  read boundary    (how to read Engine outputs)
    PR31-S §43  usage recipe     (what order to call methods in)
    PR32-V §44  report surface   (what shape the result should take)

This file is intentionally an all-pass report surface test file.

PR32-V is a boundary/spec PR. The tests assemble the six canonical §44
report shapes through consumer-side helper functions that use only the
existing public Engine API, and lock the shape invariants:

    Shape A — claim_summary
    Shape B — effective_breakdown
    Shape C — lifecycle
    Shape D — evidence_contradiction
    Shape E — rule_pinning
    Shape F — snapshot_metadata
    Assembly purity
    No Engine report helper method
    Method surface freeze preserved

Expected result:
    All tests pass immediately.
"""

from __future__ import annotations

from typing import Any

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


# -----------------------------------------------------------------------
# §44 frozen key sets (test invariant)
# -----------------------------------------------------------------------

CLAIM_SUMMARY_KEYS: frozenset[str] = frozenset({
    "claim_id",
    "subject_id",
    "claim_type",
    "status",
    "base_confidence",
    "effective_confidence",
    "created_by_rule",
    "created_by_rule_version",
})  # §44.3 — 8 keys

EFFECTIVE_BREAKDOWN_KEYS: frozenset[str] = frozenset({
    "claim_id",
    "base_confidence",
    "effective_confidence",
    "has_status_attenuation",
    "has_unresolved_gaps",
    "has_active_contradictions",
    "has_repeated_pressure",
    "has_rule_binding",
    "has_hint_evidence",
})  # §44.4 — 9 keys (6 boolean pressure flags)

LIFECYCLE_EVENT_KEYS: frozenset[str] = frozenset({
    "seq",
    "claim_id",
    "from_status",
    "to_status",
    "transition",
})  # §44.5 — 5 keys per event

EVIDENCE_CONTRADICTION_KEYS: frozenset[str] = frozenset({
    "claim_id",
    "evidence_count",
    "contradiction_count",
    "active_contradiction_count",
    "resolved_contradiction_count",
})  # §44.6 — 5 keys

RULE_PINNING_KEYS: frozenset[str] = frozenset({
    "claim_id",
    "rule_id",
    "rule_version",
    "has_rule_binding",
    "rule_maturity",
    "firing_count",
    "observed_precision",
    "prior_confidence",
})  # §44.7 — 8 keys

SNAPSHOT_METADATA_KEYS: frozenset[str] = frozenset({
    "schema_version",
    "claims_count",
    "evidences_count",
    "gaps_count",
    "rules_count",
    "rule_stats_count",
    "hint_evidence_types_count",
    "lifecycle_events_count",
})  # §44.8 — 8 keys


# §44 forbidden keys per shape (§44.3 ~ §44.8 forbidden lists)
_FORBIDDEN_KEYS_CLAIM_SUMMARY: frozenset[str] = frozenset({
    "truth_probability", "verdict", "severity", "fixed",
})

_FORBIDDEN_KEYS_EFFECTIVE_BREAKDOWN: frozenset[str] = frozenset({
    "status_modifier_value", "freshness_modifier_value",
    "gap_modifier_value", "count_modifier_value",
    "rule_stats_modifier_value", "evidence_type_modifier_value",
    "truth_probability", "verdict",
})

_FORBIDDEN_KEYS_LIFECYCLE: frozenset[str] = frozenset({
    "timestamp", "wall_clock", "reviewer", "review_note",
})

_FORBIDDEN_KEYS_EVIDENCE_CONTRADICTION: frozenset[str] = frozenset({
    "evidence_strength_sum", "contradiction_strength_sum",
    "evidence_ids", "contradiction_ids",
})

_FORBIDDEN_KEYS_RULE_PINNING: frozenset[str] = frozenset({
    "false_positive_rate", "confirmed_true_count",
    "confirmed_false_count", "rule_quality_score",
})

_FORBIDDEN_KEYS_SNAPSHOT_METADATA: frozenset[str] = frozenset({
    "snapshot_size_bytes", "file_path", "saved_at",
    "schema_migration_log",
})


# -----------------------------------------------------------------------
# Consumer-side assembly helpers (§44.9)
#
# These functions are part of the TEST module, not the framework.
# The framework does NOT provide Engine.claim_report or similar.
# The consumer is responsible for assembling these dicts.
# -----------------------------------------------------------------------

def assemble_claim_summary(engine: Engine, claim_id: int) -> dict[str, Any]:
    """§44.3 Shape A assembler."""
    claim = engine.get_claim(claim_id)
    score = engine.compute_effective_confidence(claim_id)
    return {
        "claim_id":                claim.id,
        "subject_id":              claim.subject_id,
        "claim_type":              claim.type,
        "status":                  claim.status,
        "base_confidence":         claim.base_confidence.value,
        "effective_confidence":    score.value,
        "created_by_rule":         claim.created_by_rule,
        "created_by_rule_version": claim.created_by_rule_version,
    }


def assemble_effective_breakdown(engine: Engine, claim_id: int) -> dict[str, Any]:
    """§44.4 Shape B assembler."""
    claim = engine.get_claim(claim_id)
    score = engine.compute_effective_confidence(claim_id)
    gaps = engine.gaps_for_claim(claim_id)
    active = engine.active_contradictions_for_claim(claim_id)
    evidences = engine.evidences_for_claim(claim_id)
    snapshot = engine.to_snapshot()
    hint_set = set(snapshot["hint_evidence_types"])

    return {
        "claim_id":                  claim.id,
        "base_confidence":           claim.base_confidence.value,
        "effective_confidence":      score.value,
        "has_status_attenuation":    claim.status in {
            CLAIM_STATUS_DISPUTED, CLAIM_STATUS_REFUTED,
        },
        "has_unresolved_gaps":       any(
            engine.gap_resolution(g.id) is None for g in gaps
        ),
        "has_active_contradictions": len(active) > 0,
        "has_repeated_pressure":     len(active) >= 2,
        "has_rule_binding":          claim.created_by_rule != 0,
        "has_hint_evidence":         any(
            ev.type in hint_set for ev in evidences
        ),
    }


def assemble_lifecycle(engine: Engine, claim_id: int) -> list[dict[str, Any]]:
    """§44.5 Shape C assembler (returns list of event dicts)."""
    return [
        {
            "seq":         ev.seq,
            "claim_id":    ev.claim_id,
            "from_status": ev.from_status,
            "to_status":   ev.to_status,
            "transition":  ev.transition,
        }
        for ev in engine.claim_lifecycle_history(claim_id)
    ]


def assemble_evidence_contradiction(
    engine: Engine, claim_id: int,
) -> dict[str, Any]:
    """§44.6 Shape D assembler."""
    return {
        "claim_id": claim_id,
        "evidence_count": len(engine.evidences_for_claim(claim_id)),
        "contradiction_count": len(engine.contradictions_for_claim(claim_id)),
        "active_contradiction_count": len(
            engine.active_contradictions_for_claim(claim_id)
        ),
        "resolved_contradiction_count": len(
            engine.resolved_contradictions_for_claim(claim_id)
        ),
    }


def assemble_rule_pinning(engine: Engine, claim_id: int) -> dict[str, Any]:
    """§44.7 Shape E assembler."""
    claim = engine.get_claim(claim_id)

    if claim.created_by_rule == 0:
        return {
            "claim_id":           claim.id,
            "rule_id":             0,
            "rule_version":        0,
            "has_rule_binding":    False,
            "rule_maturity":       None,
            "firing_count":        0,
            "observed_precision":  None,
            "prior_confidence":    None,
        }

    rule = engine.get_rule(claim.created_by_rule, claim.created_by_rule_version)
    try:
        stats = engine.get_rule_stats(
            claim.created_by_rule, claim.created_by_rule_version,
        )
        firing_count = stats.firing_count
        observed_precision = (
            stats.observed_precision.value
            if stats.observed_precision is not None else None
        )
    except KeyError:
        firing_count = 0
        observed_precision = None

    return {
        "claim_id":           claim.id,
        "rule_id":             claim.created_by_rule,
        "rule_version":        claim.created_by_rule_version,
        "has_rule_binding":    True,
        "rule_maturity":       rule.maturity,
        "firing_count":        firing_count,
        "observed_precision":  observed_precision,
        "prior_confidence":    rule.prior_confidence.value,
    }


def assemble_snapshot_metadata(engine: Engine) -> dict[str, Any]:
    """§44.8 Shape F assembler."""
    snapshot = engine.to_snapshot()
    return {
        "schema_version":            snapshot["schema_version"],
        "claims_count":              len(snapshot["claims"]),
        "evidences_count":           len(snapshot["evidences"]),
        "gaps_count":                len(snapshot["gaps"]),
        "rules_count":               len(snapshot["rule_definitions"]),
        "rule_stats_count":          len(snapshot["rule_stats"]),
        "hint_evidence_types_count": len(snapshot["hint_evidence_types"]),
        "lifecycle_events_count":    len(snapshot["claim_lifecycle_events"]),
    }


# -----------------------------------------------------------------------
# Test fixtures (Engine builders)
# -----------------------------------------------------------------------

_RULE_ID = 4400
_RULE_VERSION = 1
_HINT_TYPE = 9400
_NON_HINT_TYPE = 1400


def _register_rule(engine: Engine) -> None:
    engine.register_rule(
        RuleDefinition(
            id=_RULE_ID,
            version=_RULE_VERSION,
            maturity=RULE_MATURITY_EXPERIMENTAL,
            prior_confidence=ScoreValue(0.8),
        )
    )


def _candidate_engine() -> tuple[Engine, int]:
    """Plain candidate claim, no rule binding, no evidence, no gap."""
    engine = Engine()
    eid = engine.add_entity(entity_type=1)
    cid = engine.add_claim(
        subject_id=eid,
        claim_type=1,
        rule_id=0,
        rule_version=0,
        reason_code=1,
        base_confidence=0.8,
        status=CLAIM_STATUS_CANDIDATE,
    )
    return engine, cid


def _confirmed_engine_with_rule() -> tuple[Engine, int]:
    """Confirmed claim with rule binding, gap resolved, evidence, rule_stats."""
    engine = Engine()
    _register_rule(engine)
    engine.register_hint_evidence_types({_HINT_TYPE})

    eid = engine.add_entity(entity_type=1)
    cid = engine.add_claim(
        subject_id=eid,
        claim_type=1,
        rule_id=_RULE_ID,
        rule_version=_RULE_VERSION,
        reason_code=1,
        base_confidence=0.8,
        status=CLAIM_STATUS_CANDIDATE,
    )
    engine.add_gap(
        claim_id=cid, gap_type=1,
        required_evidence_type=_HINT_TYPE, severity=0.5, rule_id=_RULE_ID,
    )
    evid = engine.add_evidence(
        claim_id=cid, raw_ref_id=0,
        evidence_type=_HINT_TYPE, strength=0.7,
    )
    engine.resolve_gaps_for_evidence(evid)
    engine.confirm_claim_if_ready(cid)
    engine.update_rule_stats(
        _RULE_ID, _RULE_VERSION,
        firing_delta=2, observed_precision=ScoreValue(0.5),
    )
    return engine, cid


def _disputed_engine() -> tuple[Engine, int]:
    """Confirmed → disputed via contradiction registration."""
    engine = Engine()
    eid = engine.add_entity(entity_type=1)
    cid = engine.add_claim(
        subject_id=eid,
        claim_type=1,
        rule_id=0,
        rule_version=0,
        reason_code=1,
        base_confidence=1.0,
        status=CLAIM_STATUS_CONFIRMED,
    )
    evid = engine.add_evidence(
        claim_id=cid, raw_ref_id=0,
        evidence_type=_NON_HINT_TYPE, strength=0.6,
    )
    engine.register_contradiction(cid, evid)
    engine.dispute_claim_if_ready(cid)
    return engine, cid


def _refuted_engine() -> tuple[Engine, int]:
    """Candidate → refuted via contradiction registration."""
    engine = Engine()
    eid = engine.add_entity(entity_type=1)
    cid = engine.add_claim(
        subject_id=eid,
        claim_type=1,
        rule_id=0,
        rule_version=0,
        reason_code=1,
        base_confidence=0.8,
        status=CLAIM_STATUS_CANDIDATE,
    )
    evid = engine.add_evidence(
        claim_id=cid, raw_ref_id=0,
        evidence_type=_NON_HINT_TYPE, strength=0.7,
    )
    engine.register_contradiction(cid, evid)
    engine.refute_claim_if_ready(cid)
    return engine, cid


# -----------------------------------------------------------------------
# Shape A — claim_summary
# -----------------------------------------------------------------------

class TestReportShapeClaimSummary:
    """§44.3 — claim_summary report shape boundary."""

    def test_claim_summary_keys_match_frozen_set(self) -> None:
        engine, cid = _candidate_engine()

        summary = assemble_claim_summary(engine, cid)

        assert frozenset(summary.keys()) == CLAIM_SUMMARY_KEYS

    def test_claim_summary_status_and_score_are_separate_signals(self) -> None:
        engine, cid = _confirmed_engine_with_rule()

        summary = assemble_claim_summary(engine, cid)

        assert summary["status"] == CLAIM_STATUS_CONFIRMED
        assert 0.0 < summary["effective_confidence"] <= 1.0
        # CONFIRMED ≠ truth probability 1.0 (§42.3)
        assert summary["effective_confidence"] != pytest.approx(1.0)

    def test_claim_summary_has_no_forbidden_keys(self) -> None:
        engine, cid = _confirmed_engine_with_rule()

        summary = assemble_claim_summary(engine, cid)

        assert _FORBIDDEN_KEYS_CLAIM_SUMMARY.isdisjoint(summary.keys())


# -----------------------------------------------------------------------
# Shape B — effective_breakdown
# -----------------------------------------------------------------------

class TestReportShapeEffectiveBreakdown:
    """§44.4 — effective_breakdown report shape boundary."""

    def test_effective_breakdown_keys_match_frozen_set(self) -> None:
        engine, cid = _candidate_engine()

        breakdown = assemble_effective_breakdown(engine, cid)

        assert frozenset(breakdown.keys()) == EFFECTIVE_BREAKDOWN_KEYS

    def test_effective_breakdown_pressure_flags_are_booleans(self) -> None:
        engine, cid = _confirmed_engine_with_rule()

        breakdown = assemble_effective_breakdown(engine, cid)

        for key in (
            "has_status_attenuation",
            "has_unresolved_gaps",
            "has_active_contradictions",
            "has_repeated_pressure",
            "has_rule_binding",
            "has_hint_evidence",
        ):
            assert isinstance(breakdown[key], bool)

    def test_effective_breakdown_disputed_claim_has_status_attenuation(self) -> None:
        engine, cid = _disputed_engine()

        breakdown = assemble_effective_breakdown(engine, cid)

        assert breakdown["has_status_attenuation"] is True
        assert breakdown["has_active_contradictions"] is True

    def test_effective_breakdown_does_not_expose_modifier_values(self) -> None:
        engine, cid = _confirmed_engine_with_rule()

        breakdown = assemble_effective_breakdown(engine, cid)

        assert _FORBIDDEN_KEYS_EFFECTIVE_BREAKDOWN.isdisjoint(breakdown.keys())


# -----------------------------------------------------------------------
# Shape C — lifecycle
# -----------------------------------------------------------------------

class TestReportShapeLifecycle:
    """§44.5 — lifecycle report shape boundary."""

    def test_lifecycle_event_keys_match_frozen_set(self) -> None:
        engine, cid = _disputed_engine()

        events = assemble_lifecycle(engine, cid)

        assert len(events) == 1
        assert frozenset(events[0].keys()) == LIFECYCLE_EVENT_KEYS

    def test_lifecycle_for_pristine_candidate_is_empty_list(self) -> None:
        engine, cid = _candidate_engine()

        events = assemble_lifecycle(engine, cid)

        assert events == []

    def test_lifecycle_event_has_no_wall_clock_timestamp(self) -> None:
        engine, cid = _refuted_engine()

        events = assemble_lifecycle(engine, cid)

        assert len(events) == 1
        assert _FORBIDDEN_KEYS_LIFECYCLE.isdisjoint(events[0].keys())


# -----------------------------------------------------------------------
# Shape D — evidence_contradiction
# -----------------------------------------------------------------------

class TestReportShapeEvidenceContradiction:
    """§44.6 — evidence_contradiction report shape boundary."""

    def test_evidence_contradiction_keys_match_frozen_set(self) -> None:
        engine, cid = _candidate_engine()

        counts = assemble_evidence_contradiction(engine, cid)

        assert frozenset(counts.keys()) == EVIDENCE_CONTRADICTION_KEYS

    def test_evidence_contradiction_counts_for_disputed_claim(self) -> None:
        engine, cid = _disputed_engine()

        counts = assemble_evidence_contradiction(engine, cid)

        assert counts["evidence_count"] == 1
        assert counts["contradiction_count"] == 1
        assert counts["active_contradiction_count"] == 1
        assert counts["resolved_contradiction_count"] == 0

    def test_evidence_contradiction_has_no_forbidden_keys(self) -> None:
        engine, cid = _disputed_engine()

        counts = assemble_evidence_contradiction(engine, cid)

        assert _FORBIDDEN_KEYS_EVIDENCE_CONTRADICTION.isdisjoint(counts.keys())


# -----------------------------------------------------------------------
# Shape E — rule_pinning
# -----------------------------------------------------------------------

class TestReportShapeRulePinning:
    """§44.7 — rule_pinning report shape boundary."""

    def test_rule_pinning_keys_match_frozen_set(self) -> None:
        engine, cid = _confirmed_engine_with_rule()

        pinning = assemble_rule_pinning(engine, cid)

        assert frozenset(pinning.keys()) == RULE_PINNING_KEYS

    def test_rule_pinning_for_rule_id_zero_path_is_no_binding(self) -> None:
        engine, cid = _candidate_engine()

        pinning = assemble_rule_pinning(engine, cid)

        assert pinning["has_rule_binding"] is False
        assert pinning["rule_id"] == 0
        assert pinning["rule_version"] == 0
        assert pinning["rule_maturity"] is None
        assert pinning["firing_count"] == 0
        assert pinning["observed_precision"] is None
        assert pinning["prior_confidence"] is None

    def test_rule_pinning_with_rule_binding_exposes_only_allowed_fields(self) -> None:
        engine, cid = _confirmed_engine_with_rule()

        pinning = assemble_rule_pinning(engine, cid)

        assert pinning["has_rule_binding"] is True
        assert pinning["rule_id"] == _RULE_ID
        assert pinning["rule_version"] == _RULE_VERSION
        assert pinning["firing_count"] == 2
        assert pinning["observed_precision"] == pytest.approx(0.5)
        assert pinning["prior_confidence"] == pytest.approx(0.8)

    def test_rule_pinning_has_no_forbidden_keys(self) -> None:
        engine, cid = _confirmed_engine_with_rule()

        pinning = assemble_rule_pinning(engine, cid)

        assert _FORBIDDEN_KEYS_RULE_PINNING.isdisjoint(pinning.keys())


# -----------------------------------------------------------------------
# Shape F — snapshot_metadata
# -----------------------------------------------------------------------

class TestReportShapeSnapshotMetadata:
    """§44.8 — snapshot_metadata report shape boundary."""

    def test_snapshot_metadata_keys_match_frozen_set(self) -> None:
        engine, _cid = _candidate_engine()

        meta = assemble_snapshot_metadata(engine)

        assert frozenset(meta.keys()) == SNAPSHOT_METADATA_KEYS

    def test_snapshot_metadata_schema_version_equals_two(self) -> None:
        engine, _cid = _confirmed_engine_with_rule()

        meta = assemble_snapshot_metadata(engine)

        assert meta["schema_version"] == 2

    def test_snapshot_metadata_counts_for_non_trivial_engine(self) -> None:
        engine, _cid = _confirmed_engine_with_rule()

        meta = assemble_snapshot_metadata(engine)

        assert meta["claims_count"] == 1
        assert meta["evidences_count"] == 1
        assert meta["gaps_count"] == 1
        assert meta["rules_count"] == 1
        assert meta["rule_stats_count"] == 1
        assert meta["hint_evidence_types_count"] == 1
        assert meta["lifecycle_events_count"] == 1

    def test_snapshot_metadata_has_no_forbidden_keys(self) -> None:
        engine, _cid = _confirmed_engine_with_rule()

        meta = assemble_snapshot_metadata(engine)

        assert _FORBIDDEN_KEYS_SNAPSHOT_METADATA.isdisjoint(meta.keys())


# -----------------------------------------------------------------------
# Assembly purity — read-side, no mutation
# -----------------------------------------------------------------------

class TestReportAssemblyPurity:
    """§44.12 invariant 7 — assembly uses only existing public Engine APIs and does not mutate state."""

    def test_full_report_assembly_does_not_mutate_engine(self) -> None:
        engine, cid = _confirmed_engine_with_rule()
        snapshot_before = engine.to_snapshot()

        _ = assemble_claim_summary(engine, cid)
        _ = assemble_effective_breakdown(engine, cid)
        _ = assemble_lifecycle(engine, cid)
        _ = assemble_evidence_contradiction(engine, cid)
        _ = assemble_rule_pinning(engine, cid)
        _ = assemble_snapshot_metadata(engine)

        assert engine.to_snapshot() == snapshot_before

    def test_repeated_assembly_produces_identical_output(self) -> None:
        engine, cid = _confirmed_engine_with_rule()

        first = (
            assemble_claim_summary(engine, cid),
            assemble_effective_breakdown(engine, cid),
            assemble_lifecycle(engine, cid),
            assemble_evidence_contradiction(engine, cid),
            assemble_rule_pinning(engine, cid),
            assemble_snapshot_metadata(engine),
        )
        second = (
            assemble_claim_summary(engine, cid),
            assemble_effective_breakdown(engine, cid),
            assemble_lifecycle(engine, cid),
            assemble_evidence_contradiction(engine, cid),
            assemble_rule_pinning(engine, cid),
            assemble_snapshot_metadata(engine),
        )

        assert first == second


# -----------------------------------------------------------------------
# No Engine report helper method exists
# -----------------------------------------------------------------------

class TestReportSurfaceNoEngineHelper:
    """§44.12 invariant 8 — Engine does not expose any report helper method."""

    def test_engine_does_not_expose_claim_report_helper(self) -> None:
        assert not hasattr(Engine, "claim_report")
        assert not hasattr(Engine, "report_claim")
        assert not hasattr(Engine, "build_report")
        assert not hasattr(Engine, "report")
        assert not hasattr(Engine, "summary")
        assert not hasattr(Engine, "breakdown")
        assert not hasattr(Engine, "render")
        assert not hasattr(Engine, "report_surface")

    def test_ragcore_namespace_does_not_export_report_helpers(self) -> None:
        for forbidden in (
            "claim_report", "report_claim", "build_report",
            "report", "summary", "breakdown", "render", "report_surface",
        ):
            assert forbidden not in ragcore.__all__
            assert not hasattr(ragcore, forbidden) or callable(
                getattr(ragcore, forbidden, None)
            ) is False


# -----------------------------------------------------------------------
# Method surface freeze — PR31-S frozenset preserved
# -----------------------------------------------------------------------

# §44.12 invariant 10 — the PR30-P baseline frozenset locked by PR31-S
# remains the public surface after PR32-V.
# PR73-M04 additive shift: EngineStateIdentity added.
_PR30_BASELINE_PUBLIC_SYMBOLS: frozenset[str] = frozenset({
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


class TestReportSurfacePublicMethodFreeze:
    """§44.12 invariant 10 — PR31-S method surface freeze preserved."""

    def test_ragcore_all_unchanged_from_pr30p_baseline(self) -> None:
        assert frozenset(ragcore.__all__) == _PR30_BASELINE_PUBLIC_SYMBOLS

    def test_ragcore_all_has_no_duplicate_symbols(self) -> None:
        assert len(ragcore.__all__) == len(set(ragcore.__all__))
