"""Tests for PR76-M07 — Effective Confidence Calculation Trace.

Locks the §0~§20 contract invariants from the test side. These
tests are added before the 257차 implementation; running them
on 256차 produces expected import / AttributeError failures only
(the new public type and method are not yet implemented).

Categories (per §15 of the directive):
  A. value type / export / frozen behavior / field order
  B. public method existence / signature / read-only / KeyError
  C. single calculation source (value-equality with old API,
     deterministic re-call)
  D. status modifier breakdown (4 statuses)
  E. freshness modifier breakdown
     (no contradiction / one active / multi active most-recent /
      resolved excluded)
  F. gap modifier breakdown (0 / 1 / 2 / 3 / 4 unresolved;
     resolved excluded)
  G. count modifier (0 / 1 active -> 1.0; 2+ active penalty;
     resolved excluded)
  H. RuleStats modifier (sentinel rule id 0 / lookup miss /
     observed_precision None / firing_count tiers /
     false_positive_rate ignored)
  I. evidence-type modifier (empty hint set / no direct /
     all hint / mixed / contradiction excluded /
     resolved contradiction excluded)
  J. policy identity exact-string + stable across reads +
     forbidden equivalences
  K. source state identity equals state_identity() / read-only /
     mutation advances / from_snapshot fresh lineage
  L. preserved boundaries
     (PR51 packet 7 keys / snapshot 18 keys schema_version 2 /
      trace not serialized / no probability / no lifecycle /
      no RuleStats update)
"""

from __future__ import annotations

import ast
import dataclasses
import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

import ragcore
from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    Engine,
    RULE_MATURITY_DEPRECATED,
    RULE_MATURITY_EXPERIMENTAL,
    RULE_MATURITY_STABLE,
    RuleDefinition,
    ScoreValue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_EXPECTED_POLICY_ID = "ragcore.effective-confidence.v1"


_EXPECTED_FIELD_ORDER = (
    "claim_id",
    "source_state_identity",
    "calculation_policy_id",
    "base_confidence",
    "status_modifier",
    "freshness_modifier",
    "gap_modifier",
    "count_modifier",
    "rule_stats_modifier",
    "evidence_type_modifier",
    "effective_confidence",
)


def _build_basic(engine, *, base_confidence: float = 0.8, status=CLAIM_STATUS_CANDIDATE):
    ent = engine.add_entity(entity_type=1)
    cid = engine.add_claim(
        subject_id=ent,
        claim_type=1,
        rule_id=1,
        rule_version=1,
        reason_code=0,
        base_confidence=base_confidence,
        status=status,
    )
    return ent, cid


# ===========================================================================
# A. value type / export / frozen / field order
# ===========================================================================


class TestValueType:

    def test_value_type_exported(self):
        assert hasattr(ragcore, "EffectiveConfidenceTrace")
        assert "EffectiveConfidenceTrace" in ragcore.__all__

    def test_value_type_is_frozen_dataclass(self):
        T = ragcore.EffectiveConfidenceTrace
        assert dataclasses.is_dataclass(T)
        assert T.__dataclass_params__.frozen is True

    def test_value_type_field_order_locked(self):
        T = ragcore.EffectiveConfidenceTrace
        names = tuple(f.name for f in dataclasses.fields(T))
        assert names == _EXPECTED_FIELD_ORDER

    def test_value_type_has_no_extra_fields(self):
        T = ragcore.EffectiveConfidenceTrace
        names = {f.name for f in dataclasses.fields(T)}
        forbidden = {
            "probability", "verdict", "risk_label", "lifecycle_recommendation",
            "modifier_reason", "wall_clock_timestamp", "packet_identity",
            "snapshot_digest", "stale_flag", "caller_identity",
            "rule_stats_update_provenance", "freshness_verdict",
            "error", "error_message",
        }
        assert names.isdisjoint(forbidden)


# ===========================================================================
# B. public method existence / read-only / KeyError
# ===========================================================================


class TestPublicMethod:

    def test_method_exists(self):
        assert hasattr(Engine, "compute_effective_confidence_with_trace")
        assert callable(Engine.compute_effective_confidence_with_trace)

    def test_method_returns_trace(self):
        e = Engine()
        _, cid = _build_basic(e)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert isinstance(trace, ragcore.EffectiveConfidenceTrace)

    def test_method_unknown_claim_raises_keyerror(self):
        e = Engine()
        with pytest.raises(KeyError):
            e.compute_effective_confidence_with_trace(99999)

    def test_method_is_read_only_revision(self):
        e = Engine()
        _, cid = _build_basic(e)
        before = e.state_identity()
        e.compute_effective_confidence_with_trace(cid)
        after = e.state_identity()
        assert before == after

    def test_method_is_read_only_snapshot(self):
        e = Engine()
        _, cid = _build_basic(e)
        before = e.to_snapshot()
        e.compute_effective_confidence_with_trace(cid)
        after = e.to_snapshot()
        assert before == after


# ===========================================================================
# C. single calculation source
# ===========================================================================


class TestSingleCalculationSource:

    def test_trace_effective_equals_old_api(self):
        e = Engine()
        _, cid = _build_basic(e, base_confidence=0.7)
        old = e.compute_effective_confidence(cid)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.effective_confidence == old

    def test_trace_effective_equals_six_modifier_product(self):
        e = Engine()
        _, cid = _build_basic(e, base_confidence=0.6)
        trace = e.compute_effective_confidence_with_trace(cid)
        expected = trace.base_confidence.value * (
            trace.status_modifier
            * trace.freshness_modifier
            * trace.gap_modifier
            * trace.count_modifier
            * trace.rule_stats_modifier
            * trace.evidence_type_modifier
        )
        assert trace.effective_confidence == ScoreValue(expected)

    def test_repeated_reads_return_equal_trace(self):
        e = Engine()
        _, cid = _build_basic(e, base_confidence=0.5)
        a = e.compute_effective_confidence_with_trace(cid)
        b = e.compute_effective_confidence_with_trace(cid)
        assert a == b

    def test_old_api_signature_and_return_type_preserved(self):
        e = Engine()
        _, cid = _build_basic(e, base_confidence=0.4)
        result = e.compute_effective_confidence(cid)
        assert isinstance(result, ScoreValue)


# ===========================================================================
# D. status_modifier breakdown (4 statuses)
# ===========================================================================


class TestStatusModifier:

    def _build_with_status(self, status: int):
        e = Engine()
        _, cid = _build_basic(e, base_confidence=1.0, status=status)
        return e, cid

    def test_candidate_status_modifier_is_one(self):
        e, cid = self._build_with_status(CLAIM_STATUS_CANDIDATE)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.status_modifier == 1.0

    def test_confirmed_status_modifier_is_one(self):
        e, cid = self._build_with_status(CLAIM_STATUS_CONFIRMED)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.status_modifier == 1.0

    def test_disputed_status_modifier_is_half(self):
        e, cid = self._build_with_status(CLAIM_STATUS_DISPUTED)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.status_modifier == 0.5

    def test_refuted_status_modifier_is_zero(self):
        e, cid = self._build_with_status(CLAIM_STATUS_REFUTED)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.status_modifier == 0.0


# ===========================================================================
# E. freshness_modifier breakdown
# ===========================================================================


class TestFreshnessModifier:

    def test_no_active_contradiction_freshness_is_one(self):
        e = Engine()
        _, cid = _build_basic(e)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.freshness_modifier == 1.0

    def test_one_active_contradiction_freshness_below_one(self):
        e = Engine()
        _, cid = _build_basic(e)
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=1, strength=0.5)
        e.register_contradiction(cid, ev)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.freshness_modifier < 1.0

    def test_resolved_contradiction_does_not_apply_to_freshness(self):
        e = Engine()
        _, cid = _build_basic(e)
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=1, strength=0.5)
        e.register_contradiction(cid, ev)
        e.register_contradiction_resolution(cid, ev)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.freshness_modifier == 1.0


# ===========================================================================
# F. gap_modifier breakdown
# ===========================================================================


class TestGapModifier:

    def _build_with_gaps(self, n: int):
        e = Engine()
        _, cid = _build_basic(e)
        for k in range(n):
            e.add_gap(
                claim_id=cid, gap_type=k+1, required_evidence_type=k+1,
                severity=0.5, rule_id=1,
            )
        return e, cid

    def test_zero_gaps_modifier_is_one(self):
        e, cid = self._build_with_gaps(0)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.gap_modifier == 1.0

    def test_one_gap_modifier_is_nine_tenths(self):
        e, cid = self._build_with_gaps(1)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.gap_modifier == 0.9

    def test_two_gaps_modifier_is_eight_tenths(self):
        e, cid = self._build_with_gaps(2)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.gap_modifier == 0.8

    def test_three_gaps_modifier_is_seven_tenths(self):
        e, cid = self._build_with_gaps(3)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.gap_modifier == 0.7

    def test_four_gaps_modifier_is_seven_tenths(self):
        e, cid = self._build_with_gaps(4)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.gap_modifier == 0.7

    def test_resolved_gap_does_not_count(self):
        e, cid = self._build_with_gaps(1)
        gap_id = e.gaps_for_claim(cid)[0].id
        ev = e.add_evidence(
            claim_id=cid, raw_ref_id=0,
            evidence_type=e.get_gap(gap_id).required_evidence_type,
            strength=0.9,
        )
        e.resolve_gaps_for_evidence(ev)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.gap_modifier == 1.0


# ===========================================================================
# G. count_modifier (active contradiction count)
# ===========================================================================


class TestCountModifier:

    def test_zero_active_count_modifier_is_one(self):
        e = Engine()
        _, cid = _build_basic(e)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.count_modifier == 1.0

    def test_one_active_count_modifier_is_one(self):
        e = Engine()
        _, cid = _build_basic(e)
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=1, strength=0.5)
        e.register_contradiction(cid, ev)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.count_modifier == 1.0

    def test_two_active_count_modifier_below_one(self):
        e = Engine()
        _, cid = _build_basic(e)
        ev1 = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=1, strength=0.5)
        ev2 = e.add_evidence(claim_id=cid, raw_ref_id=1, evidence_type=1, strength=0.5)
        e.register_contradiction(cid, ev1)
        e.register_contradiction(cid, ev2)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.count_modifier < 1.0

    def test_resolved_contradiction_does_not_count_for_count_modifier(self):
        e = Engine()
        _, cid = _build_basic(e)
        ev1 = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=1, strength=0.5)
        ev2 = e.add_evidence(claim_id=cid, raw_ref_id=1, evidence_type=1, strength=0.5)
        e.register_contradiction(cid, ev1)
        e.register_contradiction(cid, ev2)
        e.register_contradiction_resolution(cid, ev2)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.count_modifier == 1.0


# ===========================================================================
# H. rule_stats_modifier
# ===========================================================================


class TestRuleStatsModifier:

    def test_sentinel_rule_id_zero_modifier_is_one(self):
        e = Engine()
        ent = e.add_entity(entity_type=1)
        cid = e.add_claim(
            subject_id=ent, claim_type=1, rule_id=0, rule_version=0,
            reason_code=0, base_confidence=0.7,
        )
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.rule_stats_modifier == 1.0

    def test_lookup_miss_modifier_is_one(self):
        e = Engine()
        ent = e.add_entity(entity_type=1)
        cid = e.add_claim(
            subject_id=ent, claim_type=1, rule_id=42, rule_version=1,
            reason_code=0, base_confidence=0.7,
        )
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.rule_stats_modifier == 1.0

    def test_registered_rule_observed_precision_none_modifier_is_one(self):
        # §9.5 — observed_precision None -> precision_modifier 1.0. The
        # overall rule_stats_modifier also lifts to 1.0 only when the
        # maturity floor has been cleared (firing_count >= 2 per PR26-R).
        # With firing_count >= 2 AND observed_precision None, both the
        # maturity and precision factors are 1.0, so the combined modifier
        # equals 1.0.
        e = Engine()
        e.register_rule(RuleDefinition(
            id=7, version=1, maturity=RULE_MATURITY_STABLE,
            prior_confidence=ScoreValue(0.8),
        ))
        e.update_rule_stats(rule_id=7, rule_version=1, firing_delta=2)
        ent = e.add_entity(entity_type=1)
        cid = e.add_claim(
            subject_id=ent, claim_type=1, rule_id=7, rule_version=1,
            reason_code=0, base_confidence=0.7,
        )
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.rule_stats_modifier == 1.0

    def test_false_positive_rate_does_not_affect_modifier(self):
        e = Engine()
        e.register_rule(RuleDefinition(
            id=8, version=1, maturity=RULE_MATURITY_STABLE,
            prior_confidence=ScoreValue(0.8),
        ))
        ent = e.add_entity(entity_type=1)
        cid = e.add_claim(
            subject_id=ent, claim_type=1, rule_id=8, rule_version=1,
            reason_code=0, base_confidence=0.7,
        )
        base = e.compute_effective_confidence_with_trace(cid).rule_stats_modifier
        e.update_rule_stats(
            rule_id=8, rule_version=1,
            false_positive_rate=ScoreValue(0.9),
        )
        new = e.compute_effective_confidence_with_trace(cid).rule_stats_modifier
        assert new == base


# ===========================================================================
# I. evidence_type_modifier
# ===========================================================================


class TestEvidenceTypeModifier:

    def test_empty_hint_set_modifier_is_one(self):
        e = Engine()
        _, cid = _build_basic(e)
        e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.evidence_type_modifier == 1.0

    def test_no_direct_evidence_modifier_is_one(self):
        e = Engine()
        _, cid = _build_basic(e)
        e.register_hint_evidence_types([42])
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.evidence_type_modifier == 1.0

    def test_all_direct_hint_modifier_is_nine_tenths(self):
        e = Engine()
        _, cid = _build_basic(e)
        e.register_hint_evidence_types([42])
        e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.evidence_type_modifier == 0.9

    def test_mixed_direct_modifier_is_one(self):
        e = Engine()
        _, cid = _build_basic(e)
        e.register_hint_evidence_types([42])
        e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        e.add_evidence(claim_id=cid, raw_ref_id=1, evidence_type=99, strength=0.5)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.evidence_type_modifier == 1.0

    def test_contradiction_evidence_excluded(self):
        e = Engine()
        _, cid = _build_basic(e)
        e.register_hint_evidence_types([42])
        e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        ev_contra = e.add_evidence(claim_id=cid, raw_ref_id=1, evidence_type=99, strength=0.5)
        e.register_contradiction(cid, ev_contra)
        trace = e.compute_effective_confidence_with_trace(cid)
        # only direct supporting evidence remains; that one is a hint -> 0.9
        assert trace.evidence_type_modifier == 0.9


# ===========================================================================
# J. policy identity
# ===========================================================================


class TestPolicyIdentity:

    def test_policy_id_exact_string(self):
        e = Engine()
        _, cid = _build_basic(e)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.calculation_policy_id == _EXPECTED_POLICY_ID

    def test_policy_id_is_str(self):
        e = Engine()
        _, cid = _build_basic(e)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert type(trace.calculation_policy_id) is str

    def test_policy_id_stable_across_reads(self):
        e = Engine()
        _, cid = _build_basic(e)
        a = e.compute_effective_confidence_with_trace(cid).calculation_policy_id
        b = e.compute_effective_confidence_with_trace(cid).calculation_policy_id
        assert a == b

    def test_policy_id_not_schema_version_stringification(self):
        e = Engine()
        _, cid = _build_basic(e)
        trace = e.compute_effective_confidence_with_trace(cid)
        snap_version = e.to_snapshot()["schema_version"]
        assert trace.calculation_policy_id != str(snap_version)
        assert trace.calculation_policy_id != f"schema_version:{snap_version}"

    def test_policy_id_not_re_exported_in_all(self):
        # _EFFECTIVE_CONFIDENCE_POLICY_ID is module-private.
        assert "_EFFECTIVE_CONFIDENCE_POLICY_ID" not in ragcore.__all__
        assert "EFFECTIVE_CONFIDENCE_POLICY_ID" not in ragcore.__all__


# ===========================================================================
# K. source state identity
# ===========================================================================


class TestSourceStateIdentity:

    def test_source_state_equals_engine_state(self):
        e = Engine()
        _, cid = _build_basic(e)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.source_state_identity == e.state_identity()

    def test_source_state_type_is_engine_state_identity(self):
        e = Engine()
        _, cid = _build_basic(e)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert isinstance(
            trace.source_state_identity, ragcore.EngineStateIdentity,
        )

    def test_trace_read_leaves_revision_unchanged(self):
        e = Engine()
        _, cid = _build_basic(e)
        r0 = e.state_identity().revision
        e.compute_effective_confidence_with_trace(cid)
        assert e.state_identity().revision == r0

    def test_state_mutating_call_produces_new_revision_in_subsequent_trace(self):
        e = Engine()
        _, cid = _build_basic(e)
        t1 = e.compute_effective_confidence_with_trace(cid)
        e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=1, strength=0.5)
        t2 = e.compute_effective_confidence_with_trace(cid)
        assert t1.source_state_identity.revision != t2.source_state_identity.revision

    def test_from_snapshot_produces_fresh_lineage_token(self):
        e1 = Engine()
        _, cid = _build_basic(e1)
        t1 = e1.compute_effective_confidence_with_trace(cid)
        snap = e1.to_snapshot()
        e2 = Engine.from_snapshot(snap)
        t2 = e2.compute_effective_confidence_with_trace(cid)
        assert t1.source_state_identity.engine_token != t2.source_state_identity.engine_token


# ===========================================================================
# L. preserved boundaries
# ===========================================================================


class TestPreservedBoundaries:

    def test_pr51_packet_still_7_keys(self):
        spec = importlib.util.spec_from_file_location(
            "engine_inspector", "examples/inspector/engine_inspector.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        e = Engine()
        _, cid = _build_basic(e)
        pkt = mod.build_engine_context_packet(e, cid)
        assert len(pkt) == 7
        for forbidden in (
            "effective_confidence_trace",
            "calculation_policy_id",
            "source_state_identity",
            "modifier_breakdown",
        ):
            assert forbidden not in pkt

    def test_snapshot_still_18_keys_schema_v2(self):
        e = Engine()
        _, cid = _build_basic(e)
        e.compute_effective_confidence_with_trace(cid)
        snap = e.to_snapshot()
        assert len(snap) == 18
        assert snap["schema_version"] == 2

    def test_trace_not_serialized_in_snapshot(self):
        e = Engine()
        _, cid = _build_basic(e)
        e.compute_effective_confidence_with_trace(cid)
        snap = e.to_snapshot()
        for forbidden in (
            "effective_confidence_trace",
            "trace_log",
            "calculation_policy_id",
            "last_traced_at",
        ):
            assert forbidden not in snap

    def test_effective_confidence_is_scorevalue_not_float(self):
        e = Engine()
        _, cid = _build_basic(e)
        trace = e.compute_effective_confidence_with_trace(cid)
        # ScoreValue (not raw float / probability)
        assert isinstance(trace.effective_confidence, ScoreValue)
        assert isinstance(trace.base_confidence, ScoreValue)

    def test_trace_does_not_change_lifecycle(self):
        e = Engine()
        _, cid = _build_basic(e)
        history_before = e.claim_lifecycle_history(cid)
        e.compute_effective_confidence_with_trace(cid)
        assert e.claim_lifecycle_history(cid) == history_before

    def test_trace_does_not_change_rule_stats(self):
        e = Engine()
        e.register_rule(RuleDefinition(
            id=7, version=1, maturity=RULE_MATURITY_STABLE,
            prior_confidence=ScoreValue(0.5),
        ))
        ent = e.add_entity(entity_type=1)
        cid = e.add_claim(
            subject_id=ent, claim_type=1, rule_id=7, rule_version=1,
            reason_code=0, base_confidence=0.5,
        )
        before = e.get_rule_stats(7, 1)
        e.compute_effective_confidence_with_trace(cid)
        assert e.get_rule_stats(7, 1) == before


# ===========================================================================
# M. structural counts (post-M07)
# ===========================================================================


class TestStructuralCounts:

    def _ast_counts(self):
        src = open("ragcore/engine.py").read()
        tree = ast.parse(src)
        public, private = 0, 0
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Engine":
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name.startswith("_"):
                            private += 1
                        else:
                            public += 1
        return public, private

    def test_engine_public_method_count(self):
        public, _ = self._ast_counts()
        # 41 baseline (post-M04) + 1 (compute_effective_confidence_with_trace)
        assert public == 42

    def test_engine_named_private_seams_present(self):
        # Phase 0/1 (Engine v1 refactoring): the private method TOTAL is NOT a
        # locked contract — the refactor adds private seams (e.g. _install /
        # _state_view). Only the named private seams are pinned.
        for _seam in (
            "_status_modifier_for_claim", "_freshness_modifier_for_claim",
            "_gap_modifier_for_claim", "_count_modifier_for_claim",
            "_rule_stats_modifier_for_claim", "_evidence_type_modifier_for_claim",
            "_install", "_state_view",
        ):
            assert hasattr(Engine, _seam), f"missing private seam: {_seam}"

    def test_ragcore_all_count(self):
        # 49 baseline (post-M04) + 1 (EffectiveConfidenceTrace)
        assert len(ragcore.__all__) == 50

    def test_effective_confidence_trace_in_all(self):
        assert "EffectiveConfidenceTrace" in ragcore.__all__

    def test_compute_with_trace_method_present(self):
        assert "compute_effective_confidence_with_trace" in [
            name for name in dir(Engine) if not name.startswith("_")
        ]

    def test_compute_core_private_method_present(self):
        assert "_compute_effective_confidence_core" in [
            name for name in dir(Engine) if name.startswith("_")
        ]


# ===========================================================================
# N. 259차 audit-closure locks
# ===========================================================================


class TestExactSignatureLock:
    """Lock the new method's exact signature so accidental
    rename / extra positional / extra keyword / default
    addition / positional-only / keyword-only conversion
    cannot land silently. Contract §5 (and §6 for the
    private core).

    260차 audit closure — each test now also locks
    Parameter.kind (POSITIONAL_OR_KEYWORD) and
    Parameter.default (Parameter.empty) for both self and
    claim_id.
    """

    @staticmethod
    def _assert_exact_two_positional_or_keyword(sig, expected_return):
        import inspect
        params = list(sig.parameters.values())
        # name order
        assert [p.name for p in params] == ["self", "claim_id"]
        # both must be POSITIONAL_OR_KEYWORD (no positional-only,
        # no keyword-only, no var-positional / var-keyword)
        assert params[0].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert params[1].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        # neither may carry a default
        assert params[0].default is inspect.Parameter.empty
        assert params[1].default is inspect.Parameter.empty
        # claim_id is typed int
        assert params[1].annotation in (int, "int")
        # return type matches the API
        assert sig.return_annotation == expected_return or (
            isinstance(sig.return_annotation, str)
            and sig.return_annotation == expected_return.__name__
        )

    def test_compute_with_trace_signature(self):
        import inspect
        sig = inspect.signature(Engine.compute_effective_confidence_with_trace)
        self._assert_exact_two_positional_or_keyword(
            sig, ragcore.EffectiveConfidenceTrace,
        )

    def test_compute_core_signature(self):
        import inspect
        sig = inspect.signature(Engine._compute_effective_confidence_core)
        self._assert_exact_two_positional_or_keyword(
            sig, ragcore.EffectiveConfidenceTrace,
        )

    def test_legacy_compute_signature_preserved(self):
        import inspect
        sig = inspect.signature(Engine.compute_effective_confidence)
        self._assert_exact_two_positional_or_keyword(
            sig, ScoreValue,
        )


class TestModifierHelperCallCount:
    """Lock that each of the six modifier helpers is called
    exactly once per _compute_effective_confidence_core
    invocation. Contract §6 (single calculation core)."""

    _HELPERS = (
        "_status_modifier_for_claim",
        "_freshness_modifier_for_claim",
        "_gap_modifier_for_claim",
        "_count_modifier_for_claim",
        "_rule_stats_modifier_for_claim",
        "_evidence_type_modifier_for_claim",
    )

    def _wrap_helpers(self, engine):
        counts = {name: 0 for name in self._HELPERS}
        originals = {}
        for name in self._HELPERS:
            originals[name] = getattr(Engine, name)
            def make_wrapper(orig, key):
                def wrapper(self, *a, **kw):
                    counts[key] += 1
                    return orig(self, *a, **kw)
                return wrapper
            setattr(Engine, name, make_wrapper(originals[name], name))
        return counts, originals

    def _restore_helpers(self, originals):
        for name, orig in originals.items():
            setattr(Engine, name, orig)

    def test_core_calls_each_helper_exactly_once(self):
        e = Engine()
        _, cid = _build_basic(e)
        counts, originals = self._wrap_helpers(e)
        try:
            e._compute_effective_confidence_core(cid)
            assert counts == {name: 1 for name in self._HELPERS}
        finally:
            self._restore_helpers(originals)

    def test_compute_with_trace_calls_each_helper_exactly_once(self):
        e = Engine()
        _, cid = _build_basic(e)
        counts, originals = self._wrap_helpers(e)
        try:
            e.compute_effective_confidence_with_trace(cid)
            assert counts == {name: 1 for name in self._HELPERS}
        finally:
            self._restore_helpers(originals)

    def test_legacy_compute_calls_each_helper_exactly_once(self):
        # Legacy API delegates to the same core; same call profile.
        e = Engine()
        _, cid = _build_basic(e)
        counts, originals = self._wrap_helpers(e)
        try:
            e.compute_effective_confidence(cid)
            assert counts == {name: 1 for name in self._HELPERS}
        finally:
            self._restore_helpers(originals)


class TestSingleMultiplicationSite:
    """AST-level lock that the six-modifier multiplication
    expression lives in exactly one Engine method body
    (_compute_effective_confidence_core). Contract §6
    explicitly forbids two multiplication sites for the
    same formula."""

    _HELPER_NAMES = frozenset({
        "_status_modifier_for_claim",
        "_freshness_modifier_for_claim",
        "_gap_modifier_for_claim",
        "_count_modifier_for_claim",
        "_rule_stats_modifier_for_claim",
        "_evidence_type_modifier_for_claim",
    })

    def _engine_methods_using_helpers(self):
        """Return Engine method bodies that contain self.<helper>()
        calls for the six modifier helpers."""
        src = open("ragcore/engine.py").read()
        tree = ast.parse(src)
        sites = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Engine":
                for item in node.body:
                    if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    helper_calls = set()
                    for inner in ast.walk(item):
                        if isinstance(inner, ast.Attribute):
                            if (isinstance(inner.value, ast.Name)
                                    and inner.value.id == "self"
                                    and inner.attr in self._HELPER_NAMES):
                                helper_calls.add(inner.attr)
                    if helper_calls:
                        sites.append((item.name, helper_calls))
        return sites

    def test_exactly_one_method_references_all_six_helpers(self):
        sites = self._engine_methods_using_helpers()
        full_sites = [
            name for name, helpers in sites
            if helpers == self._HELPER_NAMES
        ]
        assert full_sites == ["_compute_effective_confidence_core"], (
            "Expected exactly _compute_effective_confidence_core to "
            "reference all six modifier helpers; got "
            f"{full_sites!r}. Two multiplication sites are forbidden "
            "by contract §6."
        )

    def test_legacy_compute_does_not_reference_modifier_helpers(self):
        sites = self._engine_methods_using_helpers()
        helper_bearing = {name for name, _ in sites}
        # compute_effective_confidence must delegate to the core.
        assert "compute_effective_confidence" not in helper_bearing

    def test_compute_with_trace_does_not_reference_modifier_helpers(self):
        sites = self._engine_methods_using_helpers()
        helper_bearing = {name for name, _ in sites}
        assert "compute_effective_confidence_with_trace" not in helper_bearing

    def _engine_method_node(self, method_name: str):
        src = open("ragcore/engine.py").read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Engine":
                for item in node.body:
                    if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and item.name == method_name):
                        return item
        raise AssertionError(f"Engine method {method_name!r} not found")

    @staticmethod
    def _count_mult_ops_in(node) -> int:
        n = 0
        for child in ast.walk(node):
            # ast.Mult appears either as the op of a BinOp or inside the
            # ops list of an augmented assignment / multi-op expression.
            # We only enumerate ast.Mult instances.
            if isinstance(child, ast.Mult):
                n += 1
        return n

    @staticmethod
    def _is_ratio_curve_helper(name: str) -> bool:
        # Each modifier helper computes its own tier-curve internally
        # (e.g., 1.0 - x * 0.2). Those are NOT the six-modifier
        # composition formula; they are private internals owned by the
        # helper. The single-site lock targets the six-helper
        # composition only — see contract §6.
        return name in {
            "_status_modifier_for_claim",
            "_freshness_modifier_for_claim",
            "_gap_modifier_for_claim",
            "_count_modifier_for_claim",
            "_rule_stats_modifier_for_claim",
            "_evidence_type_modifier_for_claim",
        }

    def test_core_contains_the_six_modifier_multiplication_chain(self):
        """The private core's body must contain an expression that
        multiplies base_confidence.value by each of the six
        modifier-helper return values. The simplest mechanical lock
        on that property: the core method body contains at least 6
        ast.Mult operations (base × six modifiers chain at minimum).
        """
        core = self._engine_method_node("_compute_effective_confidence_core")
        mult_count = self._count_mult_ops_in(core)
        # base × m1 × m2 × m3 × m4 × m5 × m6 -> 6 Mult ops.
        # The body may contain incidental multiplications in trace
        # construction / packaging that are not part of the formula,
        # so we lock the LOWER bound, not the exact count.
        assert mult_count >= 6, (
            f"_compute_effective_confidence_core contains only {mult_count} "
            "Mult ops; the six-modifier composition chain requires "
            "at least 6. Composition formula appears truncated."
        )

    def test_legacy_compute_body_contains_no_mult_ops(self):
        """The legacy compute_effective_confidence is reduced to a
        single delegating expression. Its body must contain ZERO
        ast.Mult operations — the formula now lives only in the
        private core.
        """
        legacy = self._engine_method_node("compute_effective_confidence")
        mult_count = self._count_mult_ops_in(legacy)
        assert mult_count == 0, (
            f"compute_effective_confidence body contains {mult_count} "
            "Mult ops; contract §6 requires it to delegate to the core "
            "(no second multiplication site)."
        )

    def test_compute_with_trace_body_contains_no_mult_ops(self):
        """compute_effective_confidence_with_trace must delegate to
        the private core without performing any multiplication of its
        own.
        """
        trace_api = self._engine_method_node(
            "compute_effective_confidence_with_trace",
        )
        mult_count = self._count_mult_ops_in(trace_api)
        assert mult_count == 0, (
            f"compute_effective_confidence_with_trace body contains "
            f"{mult_count} Mult ops; contract §6 requires it to "
            "delegate to the core."
        )

    def test_no_other_engine_method_contains_six_or_more_mult_ops(self):
        """No Engine method body, other than the private core and the
        six modifier helpers, may contain >= 6 ast.Mult operations.
        Six or more multiplications in a single body strongly suggests
        a duplicate composition formula."""
        src = open("ragcore/engine.py").read()
        tree = ast.parse(src)
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Engine":
                for item in node.body:
                    if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    name = item.name
                    if name == "_compute_effective_confidence_core":
                        continue
                    if self._is_ratio_curve_helper(name):
                        continue
                    if self._count_mult_ops_in(item) >= 6:
                        offenders.append(name)
        assert offenders == [], (
            f"Methods with >= 6 Mult ops (potential duplicate "
            f"composition site): {offenders!r}"
        )


class TestExactCompositionExpression:
    """261차 audit closure — contract §6 requires the private core
    to contain exactly one ordered base × six-modifier composition.
    The earlier `>= 6 Mult ops` test detected formula truncation but
    did not lock the exact expression. This class walks the AST of
    the ScoreValue(...) argument inside
    _compute_effective_confidence_core, flattens the left-associative
    Mult chain, and asserts:

      1. exactly one ScoreValue(...) call appears inside the core body
      2. the call's first positional argument is a Mult chain
      3. flattening that chain yields exactly 7 leaf operands
      4. flattening contains exactly 6 ast.Mult nodes
      5. the 7 leaves are, in order:
           claim.base_confidence.value
           status_modifier
           freshness_modifier
           gap_modifier
           count_modifier
           rule_stats_modifier
           evidence_type_modifier
    """

    _EXPECTED_LEAVES = (
        "claim.base_confidence.value",
        "status_modifier",
        "freshness_modifier",
        "gap_modifier",
        "count_modifier",
        "rule_stats_modifier",
        "evidence_type_modifier",
    )

    def _core_node(self):
        src = open("ragcore/engine.py").read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Engine":
                for item in node.body:
                    if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and item.name == "_compute_effective_confidence_core"):
                        return item
        raise AssertionError(
            "_compute_effective_confidence_core not found in Engine class"
        )

    def _score_value_calls(self, core_node):
        """Return ast.Call nodes that look like ScoreValue(...) inside
        the core body."""
        calls = []
        for inner in ast.walk(core_node):
            if isinstance(inner, ast.Call):
                func = inner.func
                if isinstance(func, ast.Name) and func.id == "ScoreValue":
                    calls.append(inner)
        return calls

    def _flatten_mult_chain(self, expr):
        """Flatten a left-associative Mult chain into an ordered list
        of leaf expressions. Returns (leaves, mult_count).

        Example: `(a * b) * c` -> ([a, b, c], 2 Mult ops).
        A non-Mult expression is a single-leaf chain with 0 Mult ops.
        """
        leaves = []
        mult_count = 0
        def visit(node):
            nonlocal mult_count
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
                mult_count += 1
                visit(node.left)
                visit(node.right)
            else:
                leaves.append(node)
        visit(expr)
        return leaves, mult_count

    @staticmethod
    def _leaf_label(node):
        """Render the few AST leaf shapes we expect for this contract.

        Expected leaves are either:
          - Attribute chain `claim.base_confidence.value`
          - Name `<modifier_name>`
        Anything else is flagged so the test fails on unexpected
        operand shapes."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parts = []
            cur = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                return ".".join(reversed(parts))
        return f"<unexpected leaf {type(node).__name__}: {ast.dump(node)}>"

    def test_core_contains_exactly_one_score_value_call(self):
        core = self._core_node()
        calls = self._score_value_calls(core)
        assert len(calls) == 1, (
            f"_compute_effective_confidence_core must contain exactly "
            f"one ScoreValue(...) call (the effective_confidence "
            f"construction); found {len(calls)}."
        )

    def test_composition_chain_leaves_and_mult_count_exact(self):
        """The ScoreValue(...) first arg must flatten to exactly 7
        leaves and 6 Mult ops."""
        core = self._core_node()
        calls = self._score_value_calls(core)
        assert calls, "ScoreValue(...) call not found"
        sv_call = calls[0]
        assert sv_call.args, "ScoreValue() called without positional argument"
        leaves, mult_count = self._flatten_mult_chain(sv_call.args[0])
        assert mult_count == 6, (
            f"Expected exactly 6 ast.Mult ops in the composition "
            f"expression; found {mult_count}. Contract §6 requires "
            f"one base × six-modifier chain."
        )
        assert len(leaves) == 7, (
            f"Expected exactly 7 leaf operands; found {len(leaves)}. "
            f"Leaves: {[self._leaf_label(l) for l in leaves]}"
        )

    def test_composition_leaf_sequence_exact_order(self):
        """The 7 flattened leaves must appear in the exact contract
        order: base × status × freshness × gap × count × rule_stats
        × evidence_type."""
        core = self._core_node()
        sv_call = self._score_value_calls(core)[0]
        leaves, _ = self._flatten_mult_chain(sv_call.args[0])
        actual = tuple(self._leaf_label(l) for l in leaves)
        assert actual == self._EXPECTED_LEAVES, (
            "Composition leaf order does NOT match contract §4 / §6:\n"
            f"  expected: {self._EXPECTED_LEAVES}\n"
            f"  actual:   {actual}"
        )


class TestFreshnessMultiActiveMostRecent:
    """Contract §9.2 — when multiple active contradictions
    exist, only the MOST RECENT (highest evidence_id) one
    contributes to freshness_modifier."""

    def test_multiple_active_uses_most_recent_strength(self):
        # Add two active contradictions with very different strengths.
        # The freshness modifier must reflect the most-recent one
        # (the one with the higher evidence_id), not the other.
        e = Engine()
        _, cid = _build_basic(e)
        weak = e.add_evidence(
            claim_id=cid, raw_ref_id=0, evidence_type=1, strength=0.1,
        )
        strong = e.add_evidence(
            claim_id=cid, raw_ref_id=1, evidence_type=1, strength=0.9,
        )
        e.register_contradiction(cid, weak)
        e.register_contradiction(cid, strong)
        # strong has the higher evidence_id, so it is "most recent".
        trace = e.compute_effective_confidence_with_trace(cid)
        # The freshness modifier must use the most recent (strong)
        # contradiction; compare against a baseline where only the
        # strong one is active.
        e_only_strong = Engine()
        _, cid2 = _build_basic(e_only_strong)
        # Insert evidence with the same strength as `strong` and
        # register it as a contradiction.
        ev2 = e_only_strong.add_evidence(
            claim_id=cid2, raw_ref_id=0, evidence_type=1, strength=0.9,
        )
        e_only_strong.register_contradiction(cid2, ev2)
        trace_only_strong = e_only_strong.compute_effective_confidence_with_trace(cid2)
        assert trace.freshness_modifier == trace_only_strong.freshness_modifier

    def test_most_recent_is_highest_evidence_id_not_lowest(self):
        # Negative: if "most recent" were the lowest evidence_id, the
        # multi-active freshness would equal the weak baseline. Lock
        # that this is not the case.
        e = Engine()
        _, cid = _build_basic(e)
        weak = e.add_evidence(
            claim_id=cid, raw_ref_id=0, evidence_type=1, strength=0.1,
        )
        strong = e.add_evidence(
            claim_id=cid, raw_ref_id=1, evidence_type=1, strength=0.9,
        )
        e.register_contradiction(cid, weak)
        e.register_contradiction(cid, strong)
        trace = e.compute_effective_confidence_with_trace(cid)
        e_only_weak = Engine()
        _, cid_w = _build_basic(e_only_weak)
        ev_w = e_only_weak.add_evidence(
            claim_id=cid_w, raw_ref_id=0, evidence_type=1, strength=0.1,
        )
        e_only_weak.register_contradiction(cid_w, ev_w)
        trace_only_weak = e_only_weak.compute_effective_confidence_with_trace(cid_w)
        assert trace.freshness_modifier != trace_only_weak.freshness_modifier


class TestCountModifierExactStrengthPenalty:
    """Contract §9.4 — count_modifier with 2+ active uses
    1.0 - avg_strength × 0.25 penalty exactly."""

    def test_two_active_avg_strength_exact_value(self):
        # 2 active contradictions, strengths 0.4 and 0.8 (avg 0.6).
        # Expected count_modifier = 1.0 - 0.6 * 0.25 = 0.85.
        e = Engine()
        _, cid = _build_basic(e)
        e1 = e.add_evidence(
            claim_id=cid, raw_ref_id=0, evidence_type=1, strength=0.4,
        )
        e2 = e.add_evidence(
            claim_id=cid, raw_ref_id=1, evidence_type=1, strength=0.8,
        )
        e.register_contradiction(cid, e1)
        e.register_contradiction(cid, e2)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.count_modifier == pytest.approx(0.85, rel=1e-12)

    def test_two_active_avg_zero_modifier_one(self):
        # avg = 0.0 -> 1.0 - 0.0 * 0.25 = 1.0
        e = Engine()
        _, cid = _build_basic(e)
        a = e.add_evidence(
            claim_id=cid, raw_ref_id=0, evidence_type=1, strength=0.0,
        )
        b = e.add_evidence(
            claim_id=cid, raw_ref_id=1, evidence_type=1, strength=0.0,
        )
        e.register_contradiction(cid, a)
        e.register_contradiction(cid, b)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.count_modifier == 1.0

    def test_two_active_avg_one_modifier_three_quarters(self):
        # avg = 1.0 -> 1.0 - 1.0 * 0.25 = 0.75
        e = Engine()
        _, cid = _build_basic(e)
        a = e.add_evidence(
            claim_id=cid, raw_ref_id=0, evidence_type=1, strength=1.0,
        )
        b = e.add_evidence(
            claim_id=cid, raw_ref_id=1, evidence_type=1, strength=1.0,
        )
        e.register_contradiction(cid, a)
        e.register_contradiction(cid, b)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.count_modifier == pytest.approx(0.75, rel=1e-12)


class TestRuleStatsModifierTiers:
    """Contract §9.5 — maturity × observed-precision product.

    maturity: clamped firing_count / 2 ratio, modifier
              = 1.0 - (1.0 - ratio) * 0.2
        firing 0 -> 0.8 / 1 -> 0.9 / 2+ -> 1.0
    precision: None -> 1.0, p=0.0 -> 0.9, p=0.5 -> 0.95, p=1.0 -> 1.0
    """

    def _make_with_stats(self, firing_delta=0, observed_precision=None):
        e = Engine()
        e.register_rule(RuleDefinition(
            id=9, version=1, maturity=RULE_MATURITY_STABLE,
            prior_confidence=ScoreValue(0.5),
        ))
        if firing_delta:
            e.update_rule_stats(
                rule_id=9, rule_version=1, firing_delta=firing_delta,
            )
        if observed_precision is not None:
            e.update_rule_stats(
                rule_id=9, rule_version=1,
                observed_precision=ScoreValue(observed_precision),
            )
        ent = e.add_entity(entity_type=1)
        cid = e.add_claim(
            subject_id=ent, claim_type=1, rule_id=9, rule_version=1,
            reason_code=0, base_confidence=0.7,
        )
        return e, cid

    def test_firing_zero_precision_none_modifier_is_zero_point_eight(self):
        e, cid = self._make_with_stats(firing_delta=0, observed_precision=None)
        trace = e.compute_effective_confidence_with_trace(cid)
        # maturity 0.8 × precision 1.0 = 0.8
        assert trace.rule_stats_modifier == pytest.approx(0.8, rel=1e-12)

    def test_firing_one_precision_none_modifier_is_zero_point_nine(self):
        e, cid = self._make_with_stats(firing_delta=1, observed_precision=None)
        trace = e.compute_effective_confidence_with_trace(cid)
        # maturity 0.9 × precision 1.0 = 0.9
        assert trace.rule_stats_modifier == pytest.approx(0.9, rel=1e-12)

    def test_firing_two_precision_zero_modifier_is_zero_point_nine(self):
        e, cid = self._make_with_stats(firing_delta=2, observed_precision=0.0)
        trace = e.compute_effective_confidence_with_trace(cid)
        # maturity 1.0 × precision 0.9 = 0.9
        assert trace.rule_stats_modifier == pytest.approx(0.9, rel=1e-12)

    def test_firing_two_precision_half_modifier_is_zero_point_nine_five(self):
        e, cid = self._make_with_stats(firing_delta=2, observed_precision=0.5)
        trace = e.compute_effective_confidence_with_trace(cid)
        # maturity 1.0 × precision 0.95 = 0.95
        assert trace.rule_stats_modifier == pytest.approx(0.95, rel=1e-12)

    def test_firing_two_precision_one_modifier_is_one(self):
        e, cid = self._make_with_stats(firing_delta=2, observed_precision=1.0)
        trace = e.compute_effective_confidence_with_trace(cid)
        # maturity 1.0 × precision 1.0 = 1.0
        assert trace.rule_stats_modifier == pytest.approx(1.0, rel=1e-12)

    def test_firing_zero_precision_half_modifier_is_zero_point_seventy_six(self):
        e, cid = self._make_with_stats(firing_delta=0, observed_precision=0.5)
        trace = e.compute_effective_confidence_with_trace(cid)
        # maturity 0.8 × precision 0.95 = 0.76
        assert trace.rule_stats_modifier == pytest.approx(0.76, rel=1e-12)


class TestEvidenceTypeResolvedContradictionExcluded:
    """Contract §9.6 — resolved contradiction evidence is
    excluded from the direct supporting evidence set for the
    evidence_type_modifier."""

    def test_resolved_contradiction_evidence_excluded(self):
        # One direct supporting (hint), one resolved contradiction
        # (non-hint). The resolved contradiction must be excluded so
        # the modifier reflects only the hint -> 0.9.
        e = Engine()
        _, cid = _build_basic(e)
        e.register_hint_evidence_types([42])
        e.add_evidence(
            claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5,
        )
        ev_contra = e.add_evidence(
            claim_id=cid, raw_ref_id=1, evidence_type=99, strength=0.5,
        )
        e.register_contradiction(cid, ev_contra)
        e.register_contradiction_resolution(cid, ev_contra)
        trace = e.compute_effective_confidence_with_trace(cid)
        assert trace.evidence_type_modifier == 0.9


class TestGapSharedReferenceSemantics:
    """Contract §9.3 — shared-gap reference semantics
    (PR4-PR4S / §16). The gap_modifier counts gaps via
    _claim_gap_refs, so a Claim that shares a Gap via dedup
    still contributes one unresolved-gap reference."""

    def test_shared_gap_counts_as_one_reference(self):
        e = Engine()
        ent = e.add_entity(entity_type=1)
        # Same subject + same rule + same gap_type + same required
        # evidence type -> dedup hits a single Gap shared across two
        # Claims.
        cid1 = e.add_claim(
            subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
            reason_code=0, base_confidence=0.8,
        )
        cid2 = e.add_claim(
            subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
            reason_code=0, base_confidence=0.8,
        )
        g1 = e.add_gap(
            claim_id=cid1, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        g2 = e.add_gap(
            claim_id=cid2, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        # Dedup -> same Gap id.
        assert g1 == g2
        # Each Claim now references one unresolved Gap.
        trace1 = e.compute_effective_confidence_with_trace(cid1)
        trace2 = e.compute_effective_confidence_with_trace(cid2)
        assert trace1.gap_modifier == 0.9
        assert trace2.gap_modifier == 0.9
