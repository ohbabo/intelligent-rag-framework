"""Tests for PR73-M04 — Engine State Identity Primitive.

Locks the §1-§4 contract invariants from the test side. These
tests are added before the 243차 implementation; running them
on 242차 produces expected failures only.

Categories (per §12 of the directive):
  A. value type / export / frozen behavior
  B. new Engine token + revision 0
  C. same Engine stable equality
  D. different Engine token inequality
  E. all 20 actual mutation paths increment exactly once
  F. idempotent/no-op paths increment zero
  G. documented error paths increment zero
  H. multi-object mutation still increments once
  I. all read-only methods keep identity unchanged
  J. update_rule_stats equal-result no-op
  K. hint set actual-delta semantics
  L. add_gap dedup/new-reference/no-op semantics
  M. snapshot excludes identity
  N. restored Engine gets fresh token + revision 0
  O. current PR51 packet remains unchanged and unbound
  P. public/private/API/schema structural counts
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
    RULE_MATURITY_STABLE,
    RuleDefinition,
    ScoreValue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identity(engine):
    return engine.state_identity()


def _delta(engine, action):
    before = _identity(engine)
    result = action()
    after = _identity(engine)
    return result, before, after


def _build_basic(engine):
    """Build a tiny pre-populated Engine used by many tests."""
    ent = engine.add_entity(entity_type=1)
    cid = engine.add_claim(
        subject_id=ent,
        claim_type=1,
        rule_id=1,
        rule_version=1,
        reason_code=0,
        base_confidence=0.5,
    )
    return ent, cid


# ===========================================================================
# A. value type / export / frozen behavior
# ===========================================================================


class TestValueType:

    def test_value_type_exported(self):
        assert hasattr(ragcore, "EngineStateIdentity")
        assert "EngineStateIdentity" in ragcore.__all__

    def test_value_type_is_frozen_dataclass(self):
        ESI = ragcore.EngineStateIdentity
        assert dataclasses.is_dataclass(ESI)
        params = ESI.__dataclass_params__
        assert params.frozen is True

    def test_value_type_has_two_fields(self):
        ESI = ragcore.EngineStateIdentity
        fields = {f.name: f for f in dataclasses.fields(ESI)}
        assert set(fields.keys()) == {"engine_token", "revision"}

    def test_value_type_equality_supported(self):
        ESI = ragcore.EngineStateIdentity
        a = ESI(engine_token="x", revision=0)
        b = ESI(engine_token="x", revision=0)
        c = ESI(engine_token="x", revision=1)
        d = ESI(engine_token="y", revision=0)
        assert a == b
        assert a != c
        assert a != d


# ===========================================================================
# B. new Engine token + revision 0
# ===========================================================================


class TestNewEngine:

    def test_new_engine_revision_zero(self):
        e = Engine()
        assert e.state_identity().revision == 0

    def test_new_engine_token_non_empty_str(self):
        e = Engine()
        tok = e.state_identity().engine_token
        assert isinstance(tok, str)
        assert tok != ""

    def test_state_identity_returns_value_type(self):
        e = Engine()
        assert isinstance(e.state_identity(), ragcore.EngineStateIdentity)


# ===========================================================================
# C. same Engine stable equality
# ===========================================================================


class TestStableEquality:

    def test_repeated_reads_equal_with_no_mutation(self):
        e = Engine()
        assert e.state_identity() == e.state_identity()

    def test_calling_state_identity_does_not_advance(self):
        e = Engine()
        before = e.state_identity()
        _ = e.state_identity()
        _ = e.state_identity()
        after = e.state_identity()
        assert before == after


# ===========================================================================
# D. different Engine token inequality
# ===========================================================================


class TestLineageSeparation:

    def test_two_engines_have_distinct_tokens(self):
        a = Engine().state_identity()
        b = Engine().state_identity()
        assert a.engine_token != b.engine_token

    def test_two_engines_after_same_action_still_distinct(self):
        e1 = Engine()
        e2 = Engine()
        e1.add_entity(entity_type=1)
        e2.add_entity(entity_type=1)
        assert e1.state_identity().engine_token != e2.state_identity().engine_token


# ===========================================================================
# E. all 20 actual mutation paths increment exactly once
# ===========================================================================


class TestAlwaysAdvancingMutations:

    def test_add_entity_advances_once(self):
        e = Engine()
        r0 = e.state_identity().revision
        e.add_entity(entity_type=1)
        assert e.state_identity().revision == r0 + 1

    def test_add_observation_advances_once(self):
        e = Engine()
        ent = e.add_entity(entity_type=1)
        r0 = e.state_identity().revision
        e.add_observation(entity_id=ent, raw_ref_id=0, observation_type=1)
        assert e.state_identity().revision == r0 + 1

    def test_add_claim_advances_once(self):
        e = Engine()
        ent = e.add_entity(entity_type=1)
        r0 = e.state_identity().revision
        e.add_claim(
            subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
            reason_code=0, base_confidence=0.5,
        )
        assert e.state_identity().revision == r0 + 1

    def test_add_evidence_advances_once(self):
        e = Engine()
        ent, cid = _build_basic(e)
        r0 = e.state_identity().revision
        e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        assert e.state_identity().revision == r0 + 1

    def test_add_relation_advances_once(self):
        from ragcore import KIND_ENTITY, KIND_CLAIM
        e = Engine()
        ent, cid = _build_basic(e)
        r0 = e.state_identity().revision
        e.add_relation(
            from_kind=KIND_ENTITY, from_id=ent,
            to_kind=KIND_CLAIM, to_id=cid,
            relation_type=1, rule_id=1, reason_code=0,
        )
        assert e.state_identity().revision == r0 + 1

    def test_register_rule_advances_once(self):
        e = Engine()
        r0 = e.state_identity().revision
        e.register_rule(RuleDefinition(
            id=7, version=1, maturity=RULE_MATURITY_STABLE,
            prior_confidence=ScoreValue(0.5),
        ))
        assert e.state_identity().revision == r0 + 1


class TestConditionalMutations:

    def test_add_gap_dedup_miss_advances_once(self):
        e = Engine()
        ent, cid = _build_basic(e)
        r0 = e.state_identity().revision
        e.add_gap(
            claim_id=cid, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        assert e.state_identity().revision == r0 + 1

    def test_resolve_gaps_for_evidence_nonempty_advances_once(self):
        e = Engine()
        ent, cid = _build_basic(e)
        e.add_gap(
            claim_id=cid, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        r0 = e.state_identity().revision
        resolved = e.resolve_gaps_for_evidence(ev)
        assert resolved   # non-empty
        assert e.state_identity().revision == r0 + 1

    def test_register_contradiction_true_advances_once(self):
        e = Engine()
        ent, cid = _build_basic(e)
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        r0 = e.state_identity().revision
        assert e.register_contradiction(cid, ev) is True
        assert e.state_identity().revision == r0 + 1

    def test_register_contradiction_resolution_true_advances_once(self):
        e = Engine()
        ent, cid = _build_basic(e)
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        e.register_contradiction(cid, ev)
        r0 = e.state_identity().revision
        assert e.register_contradiction_resolution(cid, ev) is True
        assert e.state_identity().revision == r0 + 1

    def test_confirm_claim_if_ready_true_advances_once(self):
        e = Engine()
        ent, cid = _build_basic(e)
        e.add_gap(
            claim_id=cid, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        e.resolve_gaps_for_evidence(ev)
        r0 = e.state_identity().revision
        assert e.confirm_claim_if_ready(cid) is True
        assert e.state_identity().revision == r0 + 1

    def test_refute_claim_if_ready_true_advances_once(self):
        e = Engine()
        ent, cid = _build_basic(e)
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.9)
        e.register_contradiction(cid, ev)
        r0 = e.state_identity().revision
        assert e.refute_claim_if_ready(cid) is True
        assert e.state_identity().revision == r0 + 1

    def test_dispute_claim_if_ready_true_advances_once(self):
        e = Engine()
        ent, cid = _build_basic(e)
        e.add_gap(
            claim_id=cid, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev_resolve = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        e.resolve_gaps_for_evidence(ev_resolve)
        e.confirm_claim_if_ready(cid)
        ev_contra = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=99, strength=0.9)
        e.register_contradiction(cid, ev_contra)
        r0 = e.state_identity().revision
        assert e.dispute_claim_if_ready(cid) is True
        assert e.state_identity().revision == r0 + 1

    def test_resolve_disputed_claim_if_ready_true_advances_once(self):
        e = Engine()
        ent, cid = _build_basic(e)
        e.add_gap(
            claim_id=cid, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev_r = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        e.resolve_gaps_for_evidence(ev_r)
        e.confirm_claim_if_ready(cid)
        ev_c = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=99, strength=0.5)
        e.register_contradiction(cid, ev_c)
        e.dispute_claim_if_ready(cid)
        e.register_contradiction_resolution(cid, ev_c)
        r0 = e.state_identity().revision
        assert e.resolve_disputed_claim_if_ready(cid) is True
        assert e.state_identity().revision == r0 + 1

    def test_refute_disputed_claim_if_ready_true_advances_once(self):
        e = Engine()
        ent, cid = _build_basic(e)
        e.add_gap(
            claim_id=cid, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev_r = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        e.resolve_gaps_for_evidence(ev_r)
        e.confirm_claim_if_ready(cid)
        ev_c = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=99, strength=0.9)
        e.register_contradiction(cid, ev_c)
        e.dispute_claim_if_ready(cid)
        r0 = e.state_identity().revision
        assert e.refute_disputed_claim_if_ready(cid) is True
        assert e.state_identity().revision == r0 + 1

    def test_refute_disputed_claim_if_ready_by_freshness_true_advances_once(self):
        e = Engine()
        ent, cid = _build_basic(e)
        e.add_gap(
            claim_id=cid, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev_r = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        e.resolve_gaps_for_evidence(ev_r)
        e.confirm_claim_if_ready(cid)
        ev_c = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=99, strength=0.9)
        e.register_contradiction(cid, ev_c)
        e.dispute_claim_if_ready(cid)
        r0 = e.state_identity().revision
        assert e.refute_disputed_claim_if_ready_by_freshness(cid) is True
        assert e.state_identity().revision == r0 + 1

    def test_update_rule_stats_changing_advances_once(self):
        e = Engine()
        e.register_rule(RuleDefinition(
            id=7, version=1, maturity=RULE_MATURITY_STABLE,
            prior_confidence=ScoreValue(0.5),
        ))
        r0 = e.state_identity().revision
        e.update_rule_stats(rule_id=7, rule_version=1, firing_delta=1)
        assert e.state_identity().revision == r0 + 1

    def test_register_hint_evidence_types_actual_extension_advances_once(self):
        e = Engine()
        r0 = e.state_identity().revision
        e.register_hint_evidence_types([42, 99])
        assert e.state_identity().revision == r0 + 1

    def test_unregister_hint_evidence_types_actual_removal_advances_once(self):
        e = Engine()
        e.register_hint_evidence_types([42, 99])
        r0 = e.state_identity().revision
        e.unregister_hint_evidence_types([42])
        assert e.state_identity().revision == r0 + 1

    def test_clear_hint_evidence_types_nonempty_advances_once(self):
        e = Engine()
        e.register_hint_evidence_types([42, 99])
        r0 = e.state_identity().revision
        e.clear_hint_evidence_types()
        assert e.state_identity().revision == r0 + 1


# ===========================================================================
# F. idempotent/no-op paths increment zero
# ===========================================================================


class TestIdempotentNoops:

    def test_register_contradiction_duplicate_does_not_advance(self):
        e = Engine()
        ent, cid = _build_basic(e)
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        e.register_contradiction(cid, ev)
        r0 = e.state_identity().revision
        assert e.register_contradiction(cid, ev) is False
        assert e.state_identity().revision == r0

    def test_register_contradiction_resolution_duplicate_does_not_advance(self):
        e = Engine()
        ent, cid = _build_basic(e)
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        e.register_contradiction(cid, ev)
        e.register_contradiction_resolution(cid, ev)
        r0 = e.state_identity().revision
        assert e.register_contradiction_resolution(cid, ev) is False
        assert e.state_identity().revision == r0

    def test_resolve_gaps_for_evidence_empty_match_does_not_advance(self):
        e = Engine()
        ent, cid = _build_basic(e)
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        # No gaps -> empty result
        r0 = e.state_identity().revision
        assert e.resolve_gaps_for_evidence(ev) == ()
        assert e.state_identity().revision == r0

    def test_lifecycle_false_returns_do_not_advance(self):
        e = Engine()
        ent, cid = _build_basic(e)
        r0 = e.state_identity().revision
        # No gaps, no contradictions, no prior status — all should return False
        assert e.confirm_claim_if_ready(cid) is False
        assert e.refute_claim_if_ready(cid) is False
        assert e.dispute_claim_if_ready(cid) is False
        assert e.resolve_disputed_claim_if_ready(cid) is False
        assert e.refute_disputed_claim_if_ready(cid) is False
        assert e.refute_disputed_claim_if_ready_by_freshness(cid) is False
        assert e.state_identity().revision == r0

    def test_update_rule_stats_logical_noop_does_not_advance(self):
        """All-zero deltas + None precision/fpr = same RuleStats value."""
        e = Engine()
        e.register_rule(RuleDefinition(
            id=7, version=1, maturity=RULE_MATURITY_STABLE,
            prior_confidence=ScoreValue(0.5),
        ))
        r0 = e.state_identity().revision
        e.update_rule_stats(rule_id=7, rule_version=1)  # all defaults
        assert e.state_identity().revision == r0

    def test_register_hint_evidence_types_empty_input_does_not_advance(self):
        e = Engine()
        r0 = e.state_identity().revision
        e.register_hint_evidence_types([])
        assert e.state_identity().revision == r0

    def test_register_hint_evidence_types_duplicates_only_does_not_advance(self):
        e = Engine()
        e.register_hint_evidence_types([42])
        r0 = e.state_identity().revision
        e.register_hint_evidence_types([42, 42])
        assert e.state_identity().revision == r0

    def test_unregister_hint_evidence_types_absent_only_does_not_advance(self):
        e = Engine()
        e.register_hint_evidence_types([42])
        r0 = e.state_identity().revision
        e.unregister_hint_evidence_types([99, 7])
        assert e.state_identity().revision == r0

    def test_clear_hint_evidence_types_already_empty_does_not_advance(self):
        e = Engine()
        r0 = e.state_identity().revision
        e.clear_hint_evidence_types()
        assert e.state_identity().revision == r0


# ===========================================================================
# G. documented error paths increment zero
# ===========================================================================


class TestErrorPaths:

    def test_add_claim_invalid_status_does_not_advance(self):
        e = Engine()
        ent = e.add_entity(entity_type=1)
        r0 = e.state_identity().revision
        with pytest.raises((TypeError, ValueError)):
            e.add_claim(
                subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
                reason_code=0, base_confidence=0.5, status=999,
            )
        assert e.state_identity().revision == r0

    def test_add_evidence_unknown_claim_does_not_advance(self):
        e = Engine()
        r0 = e.state_identity().revision
        with pytest.raises(KeyError):
            e.add_evidence(claim_id=999, raw_ref_id=0, evidence_type=42, strength=0.5)
        assert e.state_identity().revision == r0

    def test_register_rule_duplicate_does_not_advance(self):
        e = Engine()
        e.register_rule(RuleDefinition(
            id=7, version=1, maturity=RULE_MATURITY_STABLE,
            prior_confidence=ScoreValue(0.5),
        ))
        r0 = e.state_identity().revision
        with pytest.raises(ValueError):
            e.register_rule(RuleDefinition(
                id=7, version=1, maturity=RULE_MATURITY_STABLE,
                prior_confidence=ScoreValue(0.5),
            ))
        assert e.state_identity().revision == r0

    def test_register_contradiction_resolution_unrelated_evidence_does_not_advance(self):
        e = Engine()
        ent, cid = _build_basic(e)
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        r0 = e.state_identity().revision
        with pytest.raises(ValueError):
            e.register_contradiction_resolution(cid, ev)
        assert e.state_identity().revision == r0

    def test_register_hint_evidence_types_typeerror_does_not_advance(self):
        e = Engine()
        r0 = e.state_identity().revision
        with pytest.raises(TypeError):
            e.register_hint_evidence_types([True])
        assert e.state_identity().revision == r0


# ===========================================================================
# H. multi-object mutation still increments once
# ===========================================================================


class TestMultiObjectSingleAdvance:

    def test_confirm_advances_only_once_despite_status_plus_event(self):
        """Lifecycle transition writes new Claim status AND new lifecycle
        event; this is one logical mutation per §2.4."""
        e = Engine()
        ent, cid = _build_basic(e)
        e.add_gap(
            claim_id=cid, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        e.resolve_gaps_for_evidence(ev)
        r0 = e.state_identity().revision
        e.confirm_claim_if_ready(cid)
        assert e.state_identity().revision == r0 + 1

    def test_resolve_advances_only_once_for_multi_gap(self):
        """resolve_gaps_for_evidence may resolve multiple gaps;
        §2.3 advances once."""
        e = Engine()
        ent, cid = _build_basic(e)
        e.add_gap(
            claim_id=cid, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        e.add_gap(
            claim_id=cid, gap_type=2, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        r0 = e.state_identity().revision
        resolved = e.resolve_gaps_for_evidence(ev)
        assert len(resolved) >= 2
        assert e.state_identity().revision == r0 + 1


# ===========================================================================
# I. all read-only methods keep identity unchanged
# ===========================================================================


class TestReadOnlyDoesNotAdvance:

    @pytest.fixture
    def populated(self):
        e = Engine()
        ent, cid = _build_basic(e)
        ev = e.add_evidence(claim_id=cid, raw_ref_id=0, evidence_type=42, strength=0.5)
        g = e.add_gap(
            claim_id=cid, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        e.register_contradiction(cid, ev)
        e.register_rule(RuleDefinition(
            id=7, version=1, maturity=RULE_MATURITY_STABLE,
            prior_confidence=ScoreValue(0.5),
        ))
        return e, ent, cid, ev, g

    @pytest.mark.parametrize("method_call", [
        ("get_entity", lambda e, ids: e.get_entity(ids["ent"])),
        ("get_observation_via_existence_only", lambda e, ids: True),
        ("get_claim", lambda e, ids: e.get_claim(ids["cid"])),
        ("get_evidence", lambda e, ids: e.get_evidence(ids["ev"])),
        ("get_gap", lambda e, ids: e.get_gap(ids["g"])),
        ("evidences_for_claim", lambda e, ids: e.evidences_for_claim(ids["cid"])),
        ("gaps_for_claim", lambda e, ids: e.gaps_for_claim(ids["cid"])),
        ("gap_resolution", lambda e, ids: e.gap_resolution(ids["g"])),
        ("contradictions_for_claim", lambda e, ids: e.contradictions_for_claim(ids["cid"])),
        ("resolved_contradictions_for_claim", lambda e, ids: e.resolved_contradictions_for_claim(ids["cid"])),
        ("active_contradictions_for_claim", lambda e, ids: e.active_contradictions_for_claim(ids["cid"])),
        ("active_contradictions_by_freshness", lambda e, ids: e.active_contradictions_by_freshness(ids["cid"])),
        ("claim_lifecycle_history", lambda e, ids: e.claim_lifecycle_history(ids["cid"])),
        ("evidence_freshness", lambda e, ids: e.evidence_freshness(ids["ev"])),
        ("get_rule", lambda e, ids: e.get_rule(7, 1)),
        ("get_rule_stats", lambda e, ids: e.get_rule_stats(7, 1)),
        ("compute_effective_confidence", lambda e, ids: e.compute_effective_confidence(ids["cid"])),
        ("state_identity_itself", lambda e, ids: e.state_identity()),
    ])
    def test_read_only_method_does_not_advance(self, populated, method_call):
        name, call = method_call
        e, ent, cid, ev, g = populated
        ids = {"ent": ent, "cid": cid, "ev": ev, "g": g}
        before = e.state_identity()
        try:
            call(e, ids)
        except Exception:
            pass
        after = e.state_identity()
        assert before == after, f"read-only method {name} advanced revision"


# ===========================================================================
# J. update_rule_stats equal-result no-op  (covered above in TestIdempotentNoops)
# K. hint set actual-delta semantics  (covered above)
# L. add_gap dedup/new-reference/no-op
# ===========================================================================


class TestAddGapDedupSemantics:

    def test_add_gap_dedup_hit_new_reference_advances(self):
        """Two Claims share dedup key; second add_gap creates new
        _claim_gap_refs entry for the second Claim — §2.2."""
        e = Engine()
        ent = e.add_entity(entity_type=1)
        c1 = e.add_claim(
            subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
            reason_code=0, base_confidence=0.5,
        )
        c2 = e.add_claim(
            subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
            reason_code=0, base_confidence=0.5,
        )
        g1 = e.add_gap(
            claim_id=c1, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        r0 = e.state_identity().revision
        g2 = e.add_gap(
            claim_id=c2, gap_type=1, required_evidence_type=42,
            severity=0.7, rule_id=1,
        )
        assert g1 == g2
        # New _claim_gap_refs entry for c2 ⇒ +1
        assert e.state_identity().revision == r0 + 1

    def test_add_gap_dedup_hit_already_referenced_does_not_advance(self):
        """Same Claim re-adds same gap dedup key. _claim_gap_refs[cid]
        already contains gap_id — true no-op."""
        e = Engine()
        ent, cid = _build_basic(e)
        e.add_gap(
            claim_id=cid, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        r0 = e.state_identity().revision
        e.add_gap(
            claim_id=cid, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        assert e.state_identity().revision == r0


# ===========================================================================
# M. snapshot excludes identity
# ===========================================================================


class TestSnapshotExclusion:

    def test_snapshot_has_no_identity_keys(self):
        e = Engine()
        snap = e.to_snapshot()
        for forbidden in (
            "engine_token", "state_token", "state_revision",
            "state_identity", "packet_revision", "capture_token",
            "engine_revision", "snapshot_digest",
        ):
            assert forbidden not in snap

    def test_snapshot_top_level_keys_unchanged(self):
        e = Engine()
        snap = e.to_snapshot()
        assert len(snap) == 18

    def test_snapshot_schema_version_unchanged(self):
        e = Engine()
        snap = e.to_snapshot()
        assert snap["schema_version"] == 2


# ===========================================================================
# N. restored Engine gets fresh token + revision 0
# ===========================================================================


class TestRestoreSemantics:

    def test_restored_engine_starts_at_revision_zero(self):
        e = Engine()
        e.add_entity(entity_type=1)  # advance revision
        snap = e.to_snapshot()
        restored = Engine.from_snapshot(deepcopy(snap))
        assert restored.state_identity().revision == 0

    def test_restored_engine_has_fresh_token(self):
        e = Engine()
        snap = e.to_snapshot()
        restored = Engine.from_snapshot(deepcopy(snap))
        assert e.state_identity().engine_token != restored.state_identity().engine_token

    def test_source_identity_not_equal_to_restored_even_with_byte_equal_snapshot(self):
        e = Engine()
        ent, cid = _build_basic(e)
        snap = e.to_snapshot()
        restored = Engine.from_snapshot(deepcopy(snap))
        # Both engines hold equivalent state but distinct lineage identity.
        assert e.state_identity() != restored.state_identity()


# ===========================================================================
# O. current PR51 packet remains unchanged and unbound
# ===========================================================================


class TestPR51PacketUnchanged:

    def test_packet_keys_unchanged(self):
        # Load the PR51 inspector via importlib.util to keep examples/ as
        # an unpackaged flat directory.
        repo_root = Path(__file__).resolve().parent.parent
        inspector_path = (
            repo_root / "examples" / "inspector" / "engine_inspector.py"
        )
        spec = importlib.util.spec_from_file_location(
            "pr51_inspector_for_m04", inspector_path,
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        build = mod.build_engine_context_packet

        e = Engine()
        ent, cid = _build_basic(e)
        packet = build(e, cid)
        assert sorted(packet.keys()) == [
            "active_contradictions",
            "claim",
            "contradictions",
            "effective_confidence",
            "lifecycle_history",
            "supporting_evidence",
            "unresolved_gaps",
        ]
        for forbidden in (
            "engine_token", "state_token", "state_revision",
            "state_identity", "packet_revision", "capture_token",
        ):
            assert forbidden not in packet


# ===========================================================================
# P. public/private/API/schema structural counts
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
        # 40 baseline + 1 new (state_identity)
        assert public == 41

    def test_engine_private_method_count(self):
        _, private = self._ast_counts()
        # 18 baseline + 1 new (_advance_state_revision)
        assert private == 19

    def test_ragcore_all_count(self):
        # 48 baseline + 1 (EngineStateIdentity)
        assert len(ragcore.__all__) == 49

    def test_engine_state_identity_in_all(self):
        assert "EngineStateIdentity" in ragcore.__all__
