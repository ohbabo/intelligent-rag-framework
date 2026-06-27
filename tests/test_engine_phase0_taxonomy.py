"""Phase 0 — Contract-test taxonomy migration (Engine v1 refactoring plan §5).

These tests REPLACE the implementation-LOCATION locks with location-agnostic
/ behavioral equivalents, and ADD the contract characterization the previous
suite did not cover, so that Phases 1–3 can relocate code without tripping a
test that merely encodes *where* code lives:

  - serialize/restore correctness is locked BEHAVIOURALLY by exercising all
    six snapshot collection shape families through a full round-trip
    (replaces the in-source `_serialize_dict_*` / `_restore_dict_*` regex
    counts in test_engine_method_surface_freeze.py);
  - snapshot top-level KEY ORDER is locked (the frozenset test checks the
    SET only);
  - an empty-engine canonical-JSON byte image is a drift oracle for
    value+order (NOT a new user-facing serialization API contract);
  - the FULL signatures of all 42 public methods are locked (the existing
    tests lock only names + count).

No production code is changed by Phase 0. Semantic expectations (values,
admission, lifecycle, round-trip results) are unchanged.
"""

from __future__ import annotations

import copy
import json

import pytest

from ragcore import (
    Engine,
    RuleDefinition,
    ScoreValue,
    RULE_MATURITY_EXPERIMENTAL,
    KIND_CLAIM,
)


# ----------------------------------------------------------------------
# Populated fixture — every serialization shape family is exercised
# ----------------------------------------------------------------------

def _fully_populated_snapshot() -> dict:
    """An Engine snapshot whose stores cover all six serialization shape
    families, so a broken helper path cannot pass silently on an empty
    store. Built only from proven public-API call patterns."""
    engine = Engine()
    engine.register_rule(
        RuleDefinition(
            id=1, version=1,
            maturity=RULE_MATURITY_EXPERIMENTAL,
            prior_confidence=ScoreValue(0.8),
        )
    )
    engine.register_hint_evidence_types({42})

    e1 = engine.add_entity(entity_type=1)
    e2 = engine.add_entity(entity_type=2)
    engine.add_observation(entity_id=e1, raw_ref_id=0, observation_type=1)

    c1 = engine.add_claim(
        subject_id=e1, claim_type=1, rule_id=1, rule_version=1,
        reason_code=0, base_confidence=0.7,
    )
    c2 = engine.add_claim(
        subject_id=e2, claim_type=1, rule_id=1, rule_version=1,
        reason_code=0, base_confidence=0.8,
    )
    engine.add_relation(
        from_kind=KIND_CLAIM, from_id=c1,
        to_kind=KIND_CLAIM, to_id=c2,
        relation_type=1, rule_id=1, reason_code=0,
    )

    # two gaps on c1 with the same required_evidence_type but different
    # rule_id (avoids PR4 dedup) so both resolve and confirm succeeds.
    engine.add_gap(
        claim_id=c1, gap_type=1, required_evidence_type=42,
        severity=0.5, rule_id=1,
    )
    engine.add_gap(
        claim_id=c1, gap_type=1, required_evidence_type=42,
        severity=0.5, rule_id=2,
    )
    ev1 = engine.add_evidence(
        claim_id=c1, raw_ref_id=0, evidence_type=42, strength=0.8,
    )
    ev2 = engine.add_evidence(
        claim_id=c2, raw_ref_id=0, evidence_type=42, strength=0.7,
    )

    engine.resolve_gaps_for_evidence(ev1)              # gap_resolutions  (int_int)
    engine.confirm_claim_if_ready(c1)                  # claim_lifecycle_events (int_list_dataclass)
    engine.register_contradiction(c2, ev2)             # contradictions   (int_set)
    engine.register_contradiction_resolution(c2, ev2)  # resolved_contradictions (int_set)
    engine.update_rule_stats(                          # rule_stats       (tuple_dataclass)
        1, 1, firing_delta=2, observed_precision=ScoreValue(1.0),
    )
    return engine.to_snapshot()


class TestSerializeRestoreRoundTrip:
    """Behavioral replacement for the in-source serialize/restore helper
    regex counts. Location-agnostic: passes regardless of which module the
    helpers live in."""

    # one non-empty snapshot store per serialization shape family
    _FAMILY_STORE = {
        "int_dataclass": "entities",
        "tuple_dataclass": "rule_definitions",
        "tuple4_int": "gap_dedup_index",
        "int_set": "contradictions",
        "int_int": "gap_resolutions",
        "int_list_dataclass": "claim_lifecycle_events",
    }

    def test_all_six_shape_families_exercised_and_round_trip(self) -> None:
        snap = _fully_populated_snapshot()
        for family, store in self._FAMILY_STORE.items():
            assert snap[store], (
                f"{family} family not exercised: snapshot['{store}'] is empty"
            )
        restored = Engine.from_snapshot(copy.deepcopy(snap))
        assert restored.to_snapshot() == snap

    @pytest.mark.parametrize("family", sorted(_FAMILY_STORE))
    def test_per_family_round_trip(self, family: str) -> None:
        store = self._FAMILY_STORE[family]
        snap = _fully_populated_snapshot()
        restored_snap = Engine.from_snapshot(copy.deepcopy(snap)).to_snapshot()
        assert restored_snap[store] == snap[store], (
            f"{family} family ({store}) did not round-trip"
        )


# ----------------------------------------------------------------------
# Snapshot key order + canonical-bytes drift oracle
# ----------------------------------------------------------------------

_EXPECTED_TOP_LEVEL_KEY_ORDER = [
    "schema_version", "next_id", "lifecycle_seq", "entities", "observations",
    "claims", "evidences", "relations", "gaps", "rule_definitions",
    "rule_stats", "gap_dedup_index", "claim_gap_refs", "gap_resolutions",
    "contradictions", "resolved_contradictions", "claim_lifecycle_events",
    "hint_evidence_types",
]

_EXPECTED_EMPTY_CANONICAL_BYTES = (
    b'{"schema_version":2,"next_id":{},"lifecycle_seq":0,"entities":[],'
    b'"observations":[],"claims":[],"evidences":[],"relations":[],"gaps":[],'
    b'"rule_definitions":[],"rule_stats":[],"gap_dedup_index":[],'
    b'"claim_gap_refs":[],"gap_resolutions":[],"contradictions":[],'
    b'"resolved_contradictions":[],"claim_lifecycle_events":[],'
    b'"hint_evidence_types":[]}'
)


class TestSnapshotKeyOrderAndCanonicalBytes:
    def test_snapshot_top_level_key_order(self) -> None:
        # The frozenset test locks the key SET; this locks the emission ORDER.
        snap = Engine().to_snapshot()
        assert list(snap.keys()) == _EXPECTED_TOP_LEVEL_KEY_ORDER

    def test_populated_key_order_stable(self) -> None:
        snap = _fully_populated_snapshot()
        assert list(snap.keys()) == _EXPECTED_TOP_LEVEL_KEY_ORDER

    def test_empty_snapshot_canonical_bytes(self) -> None:
        # A value+order drift oracle, NOT a user-facing serialization API
        # contract (to_snapshot returns a dict). sort_keys is FORBIDDEN here:
        # it would hide a real emission-order change.
        snap = Engine().to_snapshot()
        encoded = json.dumps(
            snap, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")
        assert encoded == _EXPECTED_EMPTY_CANONICAL_BYTES

    def test_canonical_encoding_is_order_sensitive(self) -> None:
        # Documents that the oracle depends on emission order: sorting keys
        # changes the bytes, so the oracle would catch an order regression.
        snap = Engine().to_snapshot()
        plain = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
        sorted_ = json.dumps(
            snap, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        assert plain != sorted_


# ----------------------------------------------------------------------
# Full public-method signature freeze (names + count are locked elsewhere)
# ----------------------------------------------------------------------

_EXPECTED_PUBLIC_SIGNATURES = {
    "active_contradictions_by_freshness": "(self, claim_id: 'int') -> 'tuple[int, ...]'",
    "active_contradictions_for_claim": "(self, claim_id: 'int') -> 'tuple[int, ...]'",
    "add_claim": "(self, subject_id: 'int', claim_type: 'int', rule_id: 'int', rule_version: 'int', reason_code: 'int', *, base_confidence: 'float' = 0.5, status: 'int' = 0, flags: 'int' = 0) -> 'int'",
    "add_entity": "(self, entity_type: 'int', flags: 'int' = 0) -> 'int'",
    "add_evidence": "(self, claim_id: 'int', raw_ref_id: 'int', evidence_type: 'int', strength: 'float') -> 'int'",
    "add_gap": "(self, claim_id: 'int', gap_type: 'int', required_evidence_type: 'int', severity: 'float', rule_id: 'int') -> 'int'",
    "add_observation": "(self, entity_id: 'int', raw_ref_id: 'int', observation_type: 'int', source_type: 'int' = 0) -> 'int'",
    "add_relation": "(self, from_kind: 'int', from_id: 'int', to_kind: 'int', to_id: 'int', relation_type: 'int', rule_id: 'int', reason_code: 'int') -> 'int'",
    "claim_lifecycle_history": "(self, claim_id: 'int') -> 'tuple[ClaimLifecycleEvent, ...]'",
    "clear_hint_evidence_types": "(self) -> 'None'",
    "compute_effective_confidence": "(self, claim_id: 'int') -> 'ScoreValue'",
    "compute_effective_confidence_with_trace": "(self, claim_id: 'int') -> 'EffectiveConfidenceTrace'",
    "confirm_claim_if_ready": "(self, claim_id: 'int') -> 'bool'",
    "contradictions_for_claim": "(self, claim_id: 'int') -> 'tuple[int, ...]'",
    "dispute_claim_if_ready": "(self, claim_id: 'int') -> 'bool'",
    "evidence_freshness": "(self, evidence_id: 'int') -> 'int'",
    "evidences_for_claim": "(self, claim_id: 'int') -> 'list[Evidence]'",
    "from_snapshot": "(snapshot: 'dict[str, Any]') -> \"'Engine'\"",
    "gap_resolution": "(self, gap_id: 'int') -> 'int | None'",
    "gaps_for_claim": "(self, claim_id: 'int') -> 'list[Gap]'",
    "get_claim": "(self, claim_id: 'int') -> 'Claim'",
    "get_entity": "(self, entity_id: 'int') -> 'Entity'",
    "get_evidence": "(self, evidence_id: 'int') -> 'Evidence'",
    "get_gap": "(self, gap_id: 'int') -> 'Gap'",
    "get_observation": "(self, observation_id: 'int') -> 'Observation'",
    "get_relation": "(self, relation_id: 'int') -> 'Relation'",
    "get_rule": "(self, rule_id: 'int', rule_version: 'int') -> 'RuleDefinition'",
    "get_rule_stats": "(self, rule_id: 'int', rule_version: 'int') -> 'RuleStats'",
    "refute_claim_if_ready": "(self, claim_id: 'int') -> 'bool'",
    "refute_disputed_claim_if_ready": "(self, claim_id: 'int') -> 'bool'",
    "refute_disputed_claim_if_ready_by_freshness": "(self, claim_id: 'int') -> 'bool'",
    "register_contradiction": "(self, claim_id: 'int', evidence_id: 'int') -> 'bool'",
    "register_contradiction_resolution": "(self, claim_id: 'int', evidence_id: 'int') -> 'bool'",
    "register_hint_evidence_types": "(self, types: 'Iterable[int]') -> 'None'",
    "register_rule": "(self, definition: 'RuleDefinition') -> 'None'",
    "resolve_disputed_claim_if_ready": "(self, claim_id: 'int') -> 'bool'",
    "resolve_gaps_for_evidence": "(self, evidence_id: 'int') -> 'tuple[int, ...]'",
    "resolved_contradictions_for_claim": "(self, claim_id: 'int') -> 'tuple[int, ...]'",
    "state_identity": "(self) -> 'EngineStateIdentity'",
    "to_snapshot": "(self) -> 'dict[str, Any]'",
    "unregister_hint_evidence_types": "(self, types: 'Iterable[int]') -> 'None'",
    "update_rule_stats": "(self, rule_id: 'int', rule_version: 'int', *, firing_delta: 'int' = 0, true_delta: 'int' = 0, false_delta: 'int' = 0, observed_precision: 'ScoreValue | None' = None, false_positive_rate: 'ScoreValue | None' = None) -> 'None'",
}


class TestPublicSignatureFreeze:
    def test_public_method_count(self) -> None:
        assert len(_EXPECTED_PUBLIC_SIGNATURES) == 42

    def test_public_method_full_signatures_frozen(self) -> None:
        import inspect
        actual = {
            name: str(inspect.signature(getattr(Engine, name)))
            for name in dir(Engine)
            if not name.startswith("_") and callable(getattr(Engine, name))
        }
        assert actual == _EXPECTED_PUBLIC_SIGNATURES


class TestNamedPrivateSeams:
    """Phase 1: the decode/install boundary seams are pinned by NAME +
    SIGNATURE. The private method TOTAL is intentionally NOT locked (the
    refactor adds private seams); only explicitly named seams are pinned."""

    def test_install_seam(self) -> None:
        import inspect
        assert hasattr(Engine, "_install")
        assert (
            str(inspect.signature(Engine._install))
            == "(self, decoded: 'DecodedEngineState') -> 'None'"
        )

    def test_state_view_seam(self) -> None:
        import inspect
        assert hasattr(Engine, "_state_view")
        assert (
            str(inspect.signature(Engine._state_view))
            == "(self) -> 'DecodedEngineState'"
        )
