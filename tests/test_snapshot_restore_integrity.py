"""Tests for §52 — Snapshot Restore Integrity Enforcement (PR67-P03).

Locks `Engine.from_snapshot()` as the final invariant defender per §52.8.

Coverage map (§52 sub-section ↔ test class):

  §52.2.1 Evidence → Claim            ->  TestEvidenceClaimOrphan
  §52.2.2 Contradiction → Claim       ->  TestContradictionClaimOrphan
          Contradiction → Evidence    ->  TestContradictionEvidenceOrphan
          cross-claim freedom         ->  TestContradictionCrossClaimFreedomPreserved
  §52.2.3 Claim-gap → Claim           ->  TestClaimGapClaimOrphan
          Claim-gap → Gap             ->  TestClaimGapGapOrphan
          Gap.claim_id first-reg meaning ->  TestGapClaimIdFirstRegisteringPreserved
  §52.2.4 Gap resolution → Gap        ->  TestGapResolutionGapOrphan
          Gap resolution → Evidence   ->  TestGapResolutionEvidenceOrphan
  §52.3.1 gap_dedup key shape         ->  TestGapDedupKeyShape
          gap_dedup target orphan     ->  TestGapDedupTargetOrphan
  §52.3.2 resolved ⊆ contradictions   ->  TestResolvedContradictionSubset
  §52.4   RuleStats identity shape    ->  TestRuleStatsIdentityShape
          advisory unregistered       ->  TestRuleStatsAdvisoryUnregisteredPreserved
  §52.5   counter type                ->  TestCounterType
          counter value (negative)    ->  TestCounterValue
          counter collision relation  ->  TestCounterCollisionRelation
          missing kind rule           ->  TestCounterMissingKind
          sparse IDs admitted         ->  TestCounterSparseIdsAdmitted
  §52.6   Claim.status linkage        ->  TestClaimStatusLinkageUnchanged
  §52.7   raw KeyError not exposed    ->  TestNoRawKeyErrorOnContractSurface
  §52.9   v2 round-trip preservation  ->  TestValidRoundTripPreserved
          v1 migration preservation   ->  TestV1MigrationPreserved

§52.7 exception convention:

  TypeError    -> wrong Python type for a structural slot
  ValueError   -> valid type but broken reference / subset / index target /
                  identity-tuple shape / counter relation
"""

from __future__ import annotations

import copy
import enum

import pytest

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    Engine,
)


class _DerivedInt(int):
    """A custom int subclass — exact-int policy must reject it (§51.2)."""


class _StatusLikeIntEnum(enum.IntEnum):
    """An IntEnum member equals its int value but is not a built-in int."""

    CONFIRMED_LIKE = CLAIM_STATUS_CONFIRMED


def _make_claim_value(idv: int) -> dict:
    """Canonical valid serialized Claim value with the given id."""
    return {
        "id": idv, "subject_id": 1, "type": 1,
        "status": CLAIM_STATUS_CANDIDATE,
        "created_by_rule": 1, "created_by_rule_version": 1,
        "reason_code": 0, "base_confidence": {"value": 0.5}, "flags": 0,
    }


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _two_claim_engine() -> tuple[Engine, dict[str, int]]:
    """Build a small Engine with 2 entities, 2 claims, 2 evidences, 2 gaps,
    1 contradiction, 1 gap resolution. Returns the engine + a label map."""
    engine = Engine()
    e1 = engine.add_entity(entity_type=1)
    e2 = engine.add_entity(entity_type=2)
    c1 = engine.add_claim(
        subject_id=e1, claim_type=1, rule_id=1, rule_version=1,
        reason_code=0, base_confidence=0.7,
    )
    c2 = engine.add_claim(
        subject_id=e2, claim_type=1, rule_id=1, rule_version=1,
        reason_code=0, base_confidence=0.8,
    )
    ev1 = engine.add_evidence(
        claim_id=c1, raw_ref_id=0, evidence_type=42, strength=0.6,
    )
    ev2 = engine.add_evidence(
        claim_id=c2, raw_ref_id=0, evidence_type=42, strength=0.7,
    )
    g1 = engine.add_gap(
        claim_id=c1, gap_type=1, required_evidence_type=42,
        severity=0.5, rule_id=1,
    )
    g2 = engine.add_gap(
        claim_id=c2, gap_type=2, required_evidence_type=99,
        severity=0.4, rule_id=1,
    )
    engine.register_contradiction(c1, ev1)
    engine.resolve_gaps_for_evidence(ev1)
    return engine, {
        "e1": e1, "e2": e2,
        "c1": c1, "c2": c2,
        "ev1": ev1, "ev2": ev2,
        "g1": g1, "g2": g2,
    }


def _baseline_snapshot() -> dict:
    engine, _ = _two_claim_engine()
    return copy.deepcopy(engine.to_snapshot())


def _collection_item(key, value):
    return {"key": key, "value": value}


# ---------------------------------------------------------------------------
# Helper: deep-copy + invoke + ensure input unchanged
# ---------------------------------------------------------------------------


def _assert_raises_and_input_unchanged(
    snapshot: dict,
    expected_exc: type | tuple[type, ...],
) -> Exception:
    before = copy.deepcopy(snapshot)
    with pytest.raises(expected_exc) as excinfo:
        Engine.from_snapshot(snapshot)
    assert snapshot == before, "input snapshot was mutated on rejection"
    return excinfo.value


# ===========================================================================
# §52.2.1 — Evidence → Claim
# ===========================================================================


class TestEvidenceClaimOrphan:
    def test_single_orphan_evidence_rejected(self) -> None:
        snap = _baseline_snapshot()
        snap["evidences"].append(_collection_item(99, {
            "id": 99, "claim_id": 9999, "raw_ref_id": 0,
            "type": 42, "strength": {"value": 0.5},
        }))
        # Counter must also be advanced to avoid masking the orphan check.
        snap["next_id"]["evidence"] = 99
        _assert_raises_and_input_unchanged(snap, ValueError)

    def test_first_evidence_valid_second_orphan_rejected(self) -> None:
        snap = _baseline_snapshot()
        snap["evidences"].append(_collection_item(99, {
            "id": 99, "claim_id": 9999, "raw_ref_id": 0,
            "type": 42, "strength": {"value": 0.5},
        }))
        snap["next_id"]["evidence"] = 99
        _assert_raises_and_input_unchanged(snap, ValueError)


# ===========================================================================
# §52.2.2 — Contradiction reference integrity
# ===========================================================================


class TestContradictionClaimOrphan:
    def test_contradiction_key_claim_unknown(self) -> None:
        snap = _baseline_snapshot()
        snap["contradictions"].append(_collection_item(9999, [1]))
        _assert_raises_and_input_unchanged(snap, ValueError)


class TestContradictionEvidenceOrphan:
    def test_contradiction_evidence_unknown(self) -> None:
        snap = _baseline_snapshot()
        snap["contradictions"].append(_collection_item(1, [9999]))
        _assert_raises_and_input_unchanged(snap, ValueError)

    def test_one_of_many_contradiction_evidences_unknown(self) -> None:
        snap = _baseline_snapshot()
        # claim 1 already has a contradiction with ev 1; append a second
        # bucket that has one valid + one orphan
        snap["contradictions"].append(_collection_item(2, [2, 9999]))
        _assert_raises_and_input_unchanged(snap, ValueError)


class TestContradictionCrossClaimFreedomPreserved:
    """§52.2.2 cross-claim freedom — contradiction may reference an Evidence
    whose Evidence.claim_id differs from the contradiction key claim_id."""

    def test_cross_claim_contradiction_round_trip(self) -> None:
        engine, ids = _two_claim_engine()
        # Register a contradiction on c1 using ev2 (which has claim_id=c2).
        engine.register_contradiction(ids["c1"], ids["ev2"])
        snap = engine.to_snapshot()
        restored = Engine.from_snapshot(snap)
        contras = restored.contradictions_for_claim(ids["c1"])
        assert ids["ev2"] in contras


# ===========================================================================
# §52.2.3 — Claim-gap reference integrity
# ===========================================================================


class TestClaimGapClaimOrphan:
    def test_claim_gap_refs_key_claim_unknown(self) -> None:
        snap = _baseline_snapshot()
        snap["claim_gap_refs"].append(_collection_item(9999, [1]))
        _assert_raises_and_input_unchanged(snap, ValueError)


class TestClaimGapGapOrphan:
    def test_claim_gap_refs_gap_unknown(self) -> None:
        snap = _baseline_snapshot()
        snap["claim_gap_refs"].append(_collection_item(1, [9999]))
        _assert_raises_and_input_unchanged(snap, ValueError)

    def test_one_of_many_referenced_gaps_unknown(self) -> None:
        snap = _baseline_snapshot()
        snap["claim_gap_refs"].append(_collection_item(2, [2, 9999]))
        _assert_raises_and_input_unchanged(snap, ValueError)


class TestGapClaimIdFirstRegisteringPreserved:
    """§52.2.3 Gap.claim_id 'first registering claim' meaning is preserved.
    A Gap may legally be referenced by Claims other than Gap.claim_id."""

    def test_shared_gap_dedup_creates_cross_claim_ref(self) -> None:
        engine = Engine()
        e = engine.add_entity(entity_type=1)
        c1 = engine.add_claim(
            subject_id=e, claim_type=1, rule_id=1, rule_version=1,
            reason_code=0, base_confidence=0.5,
        )
        c2 = engine.add_claim(
            subject_id=e, claim_type=1, rule_id=1, rule_version=1,
            reason_code=0, base_confidence=0.6,
        )
        # Both gaps share the same dedup key (same subject + rule + gap_type
        # + required_evidence_type) so the second add_gap returns the same
        # gap_id but appends a new claim_gap_refs entry for c2.
        g1 = engine.add_gap(
            claim_id=c1, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        g2 = engine.add_gap(
            claim_id=c2, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        assert g1 == g2  # dedup hit
        # Now restore and verify: c2 references g1 even though Gap.claim_id == c1
        snap = engine.to_snapshot()
        restored = Engine.from_snapshot(snap)
        assert g1 in {g.id for g in restored.gaps_for_claim(c2)}
        # Gap.claim_id stayed at c1 (first registering claim, §16 의미 약화)
        assert restored.get_gap(g1).claim_id == c1


# ===========================================================================
# §52.2.4 — Gap resolution reference integrity
# ===========================================================================


class TestGapResolutionGapOrphan:
    def test_gap_resolution_key_unknown(self) -> None:
        snap = _baseline_snapshot()
        snap["gap_resolutions"].append(_collection_item(9999, 1))
        _assert_raises_and_input_unchanged(snap, ValueError)


class TestGapResolutionEvidenceOrphan:
    def test_gap_resolution_evidence_unknown(self) -> None:
        snap = _baseline_snapshot()
        snap["gap_resolutions"].append(_collection_item(2, 9999))
        _assert_raises_and_input_unchanged(snap, ValueError)


# ===========================================================================
# §52.3.1 — Gap dedup index
# ===========================================================================


class TestGapDedupKeyShape:
    """§52.7.1 taxonomy — a correct list container with the wrong length is a
    ValueError; a wrong container type or wrong component type is a TypeError.
    The two branches must not be collapsed into one expected exception."""

    @pytest.mark.parametrize(("label", "bad_key"), [
        ("two_element",   [1, 2]),
        ("three_element", [1, 2, 3]),
        ("five_element",  [1, 2, 3, 4, 5]),
    ])
    def test_wrong_length_raises_value_error(
        self, label: str, bad_key,
    ) -> None:
        snap = _baseline_snapshot()
        snap["gap_dedup_index"].append(_collection_item(bad_key, 1))
        _assert_raises_and_input_unchanged(snap, ValueError)

    @pytest.mark.parametrize(("label", "bad_key"), [
        ("container_str",   "1:2:3:4"),
        ("container_tuple", (1, 2, 3, 4)),
        ("container_dict",  {"a": 1}),
        ("container_none",  None),
        ("bool_component",  [True, 2, 3, 4]),
        ("float_component", [1, 2, 3, 4.0]),
        ("str_component",   ["1", 2, 3, 4]),
        ("none_component",  [1, 2, 3, None]),
    ])
    def test_wrong_type_raises_type_error(
        self, label: str, bad_key,
    ) -> None:
        snap = _baseline_snapshot()
        snap["gap_dedup_index"].append(_collection_item(bad_key, 1))
        _assert_raises_and_input_unchanged(snap, TypeError)


class TestGapDedupTargetOrphan:
    def test_target_gap_id_unknown(self) -> None:
        snap = _baseline_snapshot()
        snap["gap_dedup_index"].append(_collection_item([1, 1, 5, 5], 9999))
        _assert_raises_and_input_unchanged(snap, ValueError)


# ===========================================================================
# §52.3.2 — Resolved contradiction ⊆ contradictions
# ===========================================================================


class TestResolvedContradictionSubset:
    def test_resolved_claim_not_in_contradictions(self) -> None:
        snap = _baseline_snapshot()
        snap["resolved_contradictions"].append(_collection_item(2, [2]))
        # claim 2 has no entry in contradictions — invalid
        _assert_raises_and_input_unchanged(snap, ValueError)

    def test_resolved_evidence_not_in_contradiction_set(self) -> None:
        snap = _baseline_snapshot()
        # claim 1 has contradiction {ev=1}; resolving ev=2 is invalid
        snap["resolved_contradictions"].append(_collection_item(1, [2]))
        _assert_raises_and_input_unchanged(snap, ValueError)

    def test_resolved_claim_orphan_claim(self) -> None:
        snap = _baseline_snapshot()
        snap["resolved_contradictions"].append(_collection_item(9999, [1]))
        _assert_raises_and_input_unchanged(snap, ValueError)

    def test_empty_resolved_set_admitted(self) -> None:
        """§52.3.2 — an empty resolved set is admissible ONLY when the same
        Claim is already a key in contradictions. The contradictions-key
        requirement applies to every entry, empty bucket included."""
        snap = _baseline_snapshot()
        # claim 1 has a contradiction registered; empty resolved set is fine.
        snap["resolved_contradictions"].append(_collection_item(1, []))
        restored = Engine.from_snapshot(snap)
        assert restored is not None

    def test_empty_resolved_set_without_contradiction_rejected(self) -> None:
        """§52.3.2 — claim_id must be a key in contradictions for EVERY
        resolved_contradictions entry, including empty buckets (G-P03-RESOLVED
        -EMPTY). claim 2 has no contradictions entry."""
        snap = _baseline_snapshot()
        snap["resolved_contradictions"].append(_collection_item(2, []))
        _assert_raises_and_input_unchanged(snap, ValueError)


# ===========================================================================
# §52.4 — RuleStats identity shape
# ===========================================================================


_RULE_STATS_VALUE_TEMPLATE = {
    "rule_id": 9, "rule_version": 9, "firing_count": 0,
    "confirmed_true_count": 0, "confirmed_false_count": 0,
    "observed_precision": None, "false_positive_rate": None,
}


class TestRuleStatsIdentityShape:
    """§52.7.1 taxonomy — wrong length is a ValueError; wrong container or
    component type is a TypeError."""

    @pytest.mark.parametrize(("label", "bad_key"), [
        ("one_element",   [1]),
        ("three_element", [1, 1, 1]),
    ])
    def test_wrong_length_raises_value_error(
        self, label: str, bad_key,
    ) -> None:
        snap = _baseline_snapshot()
        snap["rule_stats"].append(_collection_item(
            bad_key, dict(_RULE_STATS_VALUE_TEMPLATE),
        ))
        _assert_raises_and_input_unchanged(snap, ValueError)

    @pytest.mark.parametrize(("label", "bad_key"), [
        ("container_str",   "1:1"),
        ("container_tuple", (1, 1)),
        ("container_dict",  {"a": 1}),
        ("container_none",  None),
        ("bool_first",    [True, 1]),
        ("bool_second",   [1, True]),
        ("float_first",   [1.0, 1]),
        ("float_second",  [1, 1.0]),
        ("str_first",     ["1", 1]),
        ("str_second",    [1, "1"]),
        ("none_first",    [None, 1]),
        ("none_second",   [1, None]),
    ])
    def test_wrong_type_raises_type_error(
        self, label: str, bad_key,
    ) -> None:
        snap = _baseline_snapshot()
        snap["rule_stats"].append(_collection_item(
            bad_key, dict(_RULE_STATS_VALUE_TEMPLATE),
        ))
        _assert_raises_and_input_unchanged(snap, TypeError)


class TestRuleStatsAdvisoryUnregisteredPreserved:
    """§52.4 — RuleStats identity is NOT required to match a registered
    rule_definitions entry. Advisory unregistered references are preserved."""

    def test_rule_stats_without_matching_rule_definition_admitted(self) -> None:
        snap = _baseline_snapshot()
        snap["rule_stats"].append(_collection_item(
            [777, 1], {**_RULE_STATS_VALUE_TEMPLATE,
                       "rule_id": 777, "rule_version": 1},
        ))
        # rule_definitions has no (777, 1) — must still restore.
        restored = Engine.from_snapshot(snap)
        assert restored.get_rule_stats(777, 1).rule_id == 777


# ===========================================================================
# §52.5 — Counter integrity
# ===========================================================================


class TestCounterType:
    @pytest.mark.parametrize(("label", "value"), [
        ("bool_true",  True),
        ("bool_false", False),
        ("float_int", 1.0),
        ("string",    "1"),
        ("none",      None),
    ])
    def test_invalid_type_raises_type_error(
        self, label: str, value,
    ) -> None:
        snap = _baseline_snapshot()
        snap["next_id"]["claim"] = value
        _assert_raises_and_input_unchanged(snap, TypeError)


class TestCounterValue:
    def test_negative_counter_raises_value_error(self) -> None:
        snap = _baseline_snapshot()
        snap["next_id"]["claim"] = -1
        _assert_raises_and_input_unchanged(snap, ValueError)


class TestCounterCollisionRelation:
    def test_counter_below_max_restored_raises_value_error(self) -> None:
        snap = _baseline_snapshot()
        # max restored claim id is 2 (we have c1 + c2)
        snap["next_id"]["claim"] = 1
        _assert_raises_and_input_unchanged(snap, ValueError)

    def test_counter_equal_to_max_admitted(self) -> None:
        snap = _baseline_snapshot()
        snap["next_id"]["claim"] = 2  # equals max restored
        restored = Engine.from_snapshot(snap)
        assert restored is not None

    def test_counter_above_max_admitted(self) -> None:
        snap = _baseline_snapshot()
        snap["next_id"]["claim"] = 999
        restored = Engine.from_snapshot(snap)
        assert restored is not None


class TestCounterMissingKind:
    def test_missing_kind_with_no_restored_ids_admitted(self) -> None:
        # Empty Engine: no relations registered. next_id has no 'relation'.
        empty = Engine().to_snapshot()
        assert "relation" not in empty["next_id"]
        restored = Engine.from_snapshot(empty)
        assert restored is not None

    def test_missing_kind_with_restored_ids_raises_value_error(self) -> None:
        snap = _baseline_snapshot()
        # We have claim entries; delete the claim counter
        del snap["next_id"]["claim"]
        _assert_raises_and_input_unchanged(snap, ValueError)


class TestCounterSparseIdsAdmitted:
    def test_sparse_ids_with_counter_above_max_admitted(self) -> None:
        """§52.5 — Sparse (non-contiguous) IDs are permitted."""
        snap = _baseline_snapshot()
        # Add a sparse claim id (5) skipping 3, 4.
        snap["claims"].append(_collection_item(5, {
            "id": 5, "subject_id": 1, "type": 1, "status": CLAIM_STATUS_CANDIDATE,
            "created_by_rule": 1, "created_by_rule_version": 1,
            "reason_code": 0, "base_confidence": {"value": 0.5}, "flags": 0,
        }))
        snap["next_id"]["claim"] = 5
        restored = Engine.from_snapshot(snap)
        assert restored.get_claim(5).id == 5


# ===========================================================================
# §52.6 — Claim.status linkage to §51 (unchanged)
# ===========================================================================


class TestClaimStatusLinkageUnchanged:
    """§51 admission still applies during restore. PR65-P01 already covered
    these; we re-check that PR67 doesn't regress the policy."""

    @pytest.mark.parametrize(("label", "value", "exc"), [
        ("bool",   True,         TypeError),
        ("float",  1.0,          TypeError),
        ("string", "candidate",  TypeError),
        ("none",   None,         TypeError),
        ("out_of_range", 999,    ValueError),
        ("negative",     -1,     ValueError),
    ])
    def test_invalid_claim_status_in_snapshot(
        self, label: str, value, exc: type,
    ) -> None:
        snap = _baseline_snapshot()
        snap["claims"][0]["value"]["status"] = value
        _assert_raises_and_input_unchanged(snap, exc)


# ===========================================================================
# §52.7 — Raw KeyError is NOT a contract surface
# ===========================================================================


class TestNoRawKeyErrorOnContractSurface:
    """§52.7 — every restore contract failure is TypeError or ValueError.
    Lookup misses inside private helpers must not surface as raw KeyError."""

    @pytest.mark.parametrize("missing_key", [
        "entities", "observations", "claims", "evidences", "relations",
        "gaps", "rule_definitions", "rule_stats", "gap_dedup_index",
        "claim_gap_refs", "gap_resolutions", "contradictions",
        "resolved_contradictions", "claim_lifecycle_events",
        "hint_evidence_types", "next_id",
    ])
    def test_missing_top_level_key_raises_contract_exception(
        self, missing_key: str,
    ) -> None:
        snap = _baseline_snapshot()
        del snap[missing_key]
        before = copy.deepcopy(snap)
        with pytest.raises((TypeError, ValueError)) as excinfo:
            Engine.from_snapshot(snap)
        # Specifically NOT a raw KeyError.
        assert not isinstance(excinfo.value, KeyError), (
            f"raw KeyError leaked to contract surface for missing {missing_key!r}"
        )
        assert snap == before

    def test_snapshot_not_a_dict_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            Engine.from_snapshot(["not", "a", "dict"])  # type: ignore[arg-type]

    @pytest.mark.parametrize("collection", [
        "entities", "claims", "evidences", "gaps", "contradictions",
        "claim_gap_refs", "gap_resolutions", "gap_dedup_index",
        "resolved_contradictions", "rule_stats",
    ])
    def test_collection_not_a_list_raises_type_error(
        self, collection: str,
    ) -> None:
        snap = _baseline_snapshot()
        snap[collection] = {"oops": "not a list"}
        _assert_raises_and_input_unchanged(snap, TypeError)


# ===========================================================================
# §52.9 — Valid path preservation
# ===========================================================================


class TestValidRoundTripPreserved:
    def test_v2_round_trip_basic(self) -> None:
        engine, ids = _two_claim_engine()
        snap = engine.to_snapshot()
        before = copy.deepcopy(snap)
        restored = Engine.from_snapshot(snap)
        assert restored.to_snapshot() == before
        # Input snapshot itself unchanged.
        assert snap == before

    @pytest.mark.parametrize(("label", "status"), [
        ("candidate", CLAIM_STATUS_CANDIDATE),
        ("confirmed", CLAIM_STATUS_CONFIRMED),
        ("refuted",   CLAIM_STATUS_REFUTED),
        ("disputed",  CLAIM_STATUS_DISPUTED),
    ])
    def test_all_valid_statuses_round_trip(self, label: str, status: int) -> None:
        engine = Engine()
        e = engine.add_entity(entity_type=1)
        cid = engine.add_claim(
            subject_id=e, claim_type=1, rule_id=1, rule_version=1,
            reason_code=0, base_confidence=0.5, status=status,
        )
        snap = engine.to_snapshot()
        restored = Engine.from_snapshot(snap)
        assert restored.get_claim(cid).status == status

    def test_empty_engine_round_trip(self) -> None:
        snap = Engine().to_snapshot()
        before = copy.deepcopy(snap)
        restored = Engine.from_snapshot(snap)
        assert restored.to_snapshot() == before


class TestV1MigrationPreserved:
    """§52.9 — _migrate_snapshot_v1_to_v2 path remains unchanged."""

    def test_v1_snapshot_round_trip(self) -> None:
        engine, _ = _two_claim_engine()
        snap = engine.to_snapshot()
        # Synthesize a v1 snapshot by stripping schema_version + adding marker.
        v1 = dict(snap)
        del v1["hint_evidence_types"]
        v1["schema_version"] = 1
        before = copy.deepcopy(v1)
        restored = Engine.from_snapshot(v1)
        assert restored is not None
        # PR21-L §33 — input snapshot is not mutated by migration.
        assert v1 == before
        # restored snapshot at v2 has hint_evidence_types added.
        out = restored.to_snapshot()
        assert out["schema_version"] == 2
        assert out["hint_evidence_types"] == []

    def test_missing_schema_version_still_raises_value_error(self) -> None:
        # PR21-L §33 — existing migration error path unchanged.
        with pytest.raises(ValueError):
            Engine.from_snapshot({"something": "else"})

    def test_unsupported_schema_version_still_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            Engine.from_snapshot({"schema_version": 99})


# ===========================================================================
# Structural invariants (smoke check) — Engine method count and __all__
# ===========================================================================


class TestStructuralInvariantsUnchanged:
    """PR67 must not change Engine method count or public surface."""

    def test_engine_method_counts(self) -> None:
        import ast
        src = open("ragcore/engine.py").read()
        tree = ast.parse(src)
        public = private = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Engine":
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name.startswith("_"):
                            private += 1
                        else:
                            public += 1
        # PR73-M04 shift: 40 → 41 public (state_identity);
        # 18 → 19 private (_advance_state_revision).
        # PR76-M07 shift: 41 → 42 public
        # (compute_effective_confidence_with_trace);
        # 19 → 20 private (_compute_effective_confidence_core).
        assert public == 42
        assert private == 20

    def test_ragcore_all_unchanged(self) -> None:
        import ragcore
        # PR73-M04 shift: 48 → 49 (added EngineStateIdentity).
        # PR76-M07 shift: 49 → 50 (added EffectiveConfidenceTrace).
        assert len(ragcore.__all__) == 50

    def test_snapshot_schema_version_unchanged(self) -> None:
        assert Engine().to_snapshot()["schema_version"] == 2

    def test_snapshot_top_level_keys_unchanged(self) -> None:
        assert len(Engine().to_snapshot()) == 18


# ===========================================================================
# §52.1.3 — exact-int serialized collection entry keys (G-P02-05)
# ===========================================================================


_SCALAR_INT_COLLECTIONS = [
    "entities", "observations", "claims", "evidences", "relations",
    "gaps", "claim_gap_refs", "gap_resolutions", "contradictions",
    "resolved_contradictions", "claim_lifecycle_events",
]


class TestCollectionEntryKeyType:
    """§52.1.3 — every scalar int-keyed serialized collection entry key must
    be an exact built-in int. bool/float/str/None/int-subclass/IntEnum are
    rejected with TypeError before any incidental comparison or counter
    failure, and no coercion occurs."""

    @pytest.mark.parametrize("collection", _SCALAR_INT_COLLECTIONS)
    def test_bool_key_rejected_for_every_collection(
        self, collection: str,
    ) -> None:
        snap = _baseline_snapshot()
        snap[collection].append(_collection_item(True, []))
        exc = _assert_raises_and_input_unchanged(snap, TypeError)
        assert collection in str(exc)

    @pytest.mark.parametrize(("label", "bad_key"), [
        ("bool_true",    True),
        ("bool_false",   False),
        ("float",        3.0),
        ("string",       "3"),
        ("none",         None),
        ("int_subclass", _DerivedInt(3)),
        ("int_enum",     _StatusLikeIntEnum.CONFIRMED_LIKE),
    ])
    def test_full_invalid_key_catalogue_on_claims(
        self, label: str, bad_key,
    ) -> None:
        snap = _baseline_snapshot()
        snap["claims"].append(_collection_item(bad_key, _make_claim_value(3)))
        exc = _assert_raises_and_input_unchanged(snap, TypeError)
        # The collection-entry key gate produced the failure (not a counter
        # comparison or dataclass error).
        assert "claims" in str(exc)


# ===========================================================================
# §52 — surrounding key == value['id'] for Claim / Evidence / Gap (G-P02-06)
# ===========================================================================


class TestKeyValueIdIntegrity:
    """§52 — for claims/evidences/gaps the serialized key must equal
    value['id']; a mismatch in either direction is a ValueError and returns
    no Engine. Not extended to entities/observations/relations/rule_*."""

    @staticmethod
    def _mismatch(collection: str, new_id: int) -> dict:
        snap = _baseline_snapshot()
        snap[collection][0]["value"]["id"] = new_id
        return snap

    @pytest.mark.parametrize("collection", ["claims", "evidences", "gaps"])
    def test_key_lower_than_value_id_rejected(self, collection: str) -> None:
        # first entry key is 1; push value id far above it.
        snap = self._mismatch(collection, 999)
        _assert_raises_and_input_unchanged(snap, ValueError)

    @pytest.mark.parametrize("collection", ["claims", "evidences", "gaps"])
    def test_key_higher_than_value_id_rejected(self, collection: str) -> None:
        # first entry key is 1; drop value id below it.
        snap = self._mismatch(collection, 0)
        _assert_raises_and_input_unchanged(snap, ValueError)


# ===========================================================================
# §52.7.1 — rule_definitions serialized identity key shape (G-P02-07)
# ===========================================================================


class TestRuleDefinitionsIdentityShape:
    """§52.7.1 — rule_definitions serialized identity key is a 2-element list
    of exact ints (structural only; no RuleStats match requirement). Wrong
    length -> ValueError; wrong container/component type -> TypeError."""

    @pytest.mark.parametrize(("label", "bad_key"), [
        ("one_element",   [5]),
        ("three_element", [5, 1, 1]),
    ])
    def test_wrong_length_raises_value_error(self, label: str, bad_key) -> None:
        snap = _baseline_snapshot()
        snap["rule_definitions"].append(_collection_item(bad_key, {}))
        _assert_raises_and_input_unchanged(snap, ValueError)

    @pytest.mark.parametrize(("label", "bad_key"), [
        ("container_str",  "5:1"),
        ("container_none", None),
        ("bool_first",     [True, 1]),
        ("float_second",   [5, 1.0]),
        ("str_first",      ["5", 1]),
        ("none_second",    [5, None]),
    ])
    def test_wrong_type_raises_type_error(self, label: str, bad_key) -> None:
        snap = _baseline_snapshot()
        snap["rule_definitions"].append(_collection_item(bad_key, {}))
        _assert_raises_and_input_unchanged(snap, TypeError)


# ===========================================================================
# §52.7 — nested raw-KeyError converted to ValueError (G-P02-08)
# ===========================================================================


class TestNestedFieldKeyErrorConverted:
    """§52.7 — a missing required nested payload field surfaces as ValueError,
    never a raw KeyError, with the input snapshot unchanged."""

    def _assert_value_error_not_keyerror(self, snap: dict) -> None:
        before = copy.deepcopy(snap)
        with pytest.raises(ValueError) as excinfo:
            Engine.from_snapshot(snap)
        assert not isinstance(excinfo.value, KeyError)
        assert snap == before

    def test_claim_missing_status(self) -> None:
        snap = _baseline_snapshot()
        del snap["claims"][0]["value"]["status"]
        self._assert_value_error_not_keyerror(snap)

    def test_claim_missing_base_confidence(self) -> None:
        snap = _baseline_snapshot()
        del snap["claims"][0]["value"]["base_confidence"]
        self._assert_value_error_not_keyerror(snap)

    def test_claim_base_confidence_missing_value(self) -> None:
        snap = _baseline_snapshot()
        snap["claims"][0]["value"]["base_confidence"] = {}
        self._assert_value_error_not_keyerror(snap)

    def test_evidence_missing_strength(self) -> None:
        snap = _baseline_snapshot()
        del snap["evidences"][0]["value"]["strength"]
        self._assert_value_error_not_keyerror(snap)

    def test_evidence_strength_missing_value(self) -> None:
        snap = _baseline_snapshot()
        snap["evidences"][0]["value"]["strength"] = {}
        self._assert_value_error_not_keyerror(snap)

    def test_gap_missing_severity(self) -> None:
        snap = _baseline_snapshot()
        del snap["gaps"][0]["value"]["severity"]
        self._assert_value_error_not_keyerror(snap)

    def test_gap_severity_missing_value(self) -> None:
        snap = _baseline_snapshot()
        snap["gaps"][0]["value"]["severity"] = {}
        self._assert_value_error_not_keyerror(snap)

    def test_rule_definition_missing_prior_confidence(self) -> None:
        snap = _baseline_snapshot()
        snap["rule_definitions"].append(_collection_item([5, 1], {
            "rule_id": 5, "rule_version": 1, "claim_type": 1, "reason_code": 0,
        }))
        self._assert_value_error_not_keyerror(snap)

    def test_rule_definition_prior_confidence_missing_value(self) -> None:
        snap = _baseline_snapshot()
        snap["rule_definitions"].append(_collection_item([5, 1], {
            "rule_id": 5, "rule_version": 1, "claim_type": 1, "reason_code": 0,
            "prior_confidence": {},
        }))
        self._assert_value_error_not_keyerror(snap)

    def test_rule_stats_observed_precision_missing_value(self) -> None:
        snap = _baseline_snapshot()
        snap["rule_stats"].append(_collection_item([9, 9], {
            **_RULE_STATS_VALUE_TEMPLATE, "observed_precision": {},
        }))
        self._assert_value_error_not_keyerror(snap)

    def test_rule_stats_false_positive_rate_missing_value(self) -> None:
        snap = _baseline_snapshot()
        snap["rule_stats"].append(_collection_item([9, 9], {
            **_RULE_STATS_VALUE_TEMPLATE, "false_positive_rate": {},
        }))
        self._assert_value_error_not_keyerror(snap)


# ===========================================================================
# §52.7.2 — duplicate serialized logical keys (G-P03-DUP)
# ===========================================================================


_IDENTITY_DUP_KEYS = {
    "rule_definitions": [9, 9],
    "rule_stats": [9, 9],
    "gap_dedup_index": [9, 9, 9, 9],
}


class TestDuplicateSerializedKeys:
    """§52.7.2 — duplicate logical keys within one serialized collection are
    rejected with ValueError (no first/last-wins, no silent discard, no
    Engine returned). next_id is excluded (already a materialized dict)."""

    @pytest.mark.parametrize("collection", _SCALAR_INT_COLLECTIONS)
    def test_duplicate_scalar_key_rejected(self, collection: str) -> None:
        snap = _baseline_snapshot()
        snap[collection].append(_collection_item(7, []))
        snap[collection].append(_collection_item(7, []))
        _assert_raises_and_input_unchanged(snap, ValueError)

    @pytest.mark.parametrize("collection", list(_IDENTITY_DUP_KEYS))
    def test_duplicate_identity_key_rejected(self, collection: str) -> None:
        snap = _baseline_snapshot()
        key = _IDENTITY_DUP_KEYS[collection]
        snap[collection].append(_collection_item(list(key), {}))
        snap[collection].append(_collection_item(list(key), {}))
        _assert_raises_and_input_unchanged(snap, ValueError)

    def test_conflicting_duplicate_scalar_dataclass_values_rejected(self) -> None:
        snap = _baseline_snapshot()
        snap["claims"].append(_collection_item(7, _make_claim_value(7)))
        snap["claims"].append(_collection_item(7, _make_claim_value(7)))
        _assert_raises_and_input_unchanged(snap, ValueError)

    def test_conflicting_duplicate_bucket_values_rejected(self) -> None:
        snap = _baseline_snapshot()
        # baseline already has a contradictions entry for claim 1.
        snap["contradictions"].append(_collection_item(1, [2]))
        _assert_raises_and_input_unchanged(snap, ValueError)

    def test_conflicting_duplicate_two_int_identity_rejected(self) -> None:
        snap = _baseline_snapshot()
        snap["rule_stats"].append(_collection_item(
            [9, 9], dict(_RULE_STATS_VALUE_TEMPLATE)))
        snap["rule_stats"].append(_collection_item(
            [9, 9], {**_RULE_STATS_VALUE_TEMPLATE, "firing_count": 5}))
        _assert_raises_and_input_unchanged(snap, ValueError)

    def test_conflicting_duplicate_four_int_identity_rejected(self) -> None:
        snap = _baseline_snapshot()
        # baseline gap_dedup_index already carries key [1, 1, 1, 42].
        snap["gap_dedup_index"].append(_collection_item([1, 1, 1, 42], 2))
        _assert_raises_and_input_unchanged(snap, ValueError)


# ===========================================================================
# §52.7 — every canonical list surface rejects non-list with TypeError (§7)
# ===========================================================================


_ALL_LIST_SURFACES = [
    "entities", "observations", "claims", "evidences", "relations",
    "gaps", "rule_definitions", "rule_stats", "gap_dedup_index",
    "claim_gap_refs", "gap_resolutions", "contradictions",
    "resolved_contradictions", "claim_lifecycle_events",
    "hint_evidence_types",
]


class TestAllListCollectionsNonListRejected:
    """§52.7 — every canonical list-encoded surface deliberately rejects a
    non-list with TypeError (not via an incidental downstream operation)."""

    @pytest.mark.parametrize("collection", _ALL_LIST_SURFACES)
    def test_non_list_collection_raises_type_error(
        self, collection: str,
    ) -> None:
        snap = _baseline_snapshot()
        snap[collection] = {"oops": "not a list"}
        _assert_raises_and_input_unchanged(snap, TypeError)


# ===========================================================================
# §52.1.2 — additional top-level metadata admit-and-drop (positive)
# ===========================================================================


class TestExtraTopLevelMetadata:
    """§52.1.2 — additional top-level keys are admitted as caller-adjacent
    metadata, not interpreted as Engine state, and not propagated; canonical
    output stays at 18 keys and the input snapshot is unchanged."""

    @pytest.mark.parametrize(("label", "extra"), [
        ("scalar", "x"),
        ("dict",   {"nested": 1}),
        ("list",   [1, 2, 3]),
    ])
    def test_extra_metadata_admitted_and_dropped(
        self, label: str, extra,
    ) -> None:
        snap = _baseline_snapshot()
        snap["__extra__"] = extra
        before = copy.deepcopy(snap)
        restored = Engine.from_snapshot(snap)
        assert snap == before
        out = restored.to_snapshot()
        assert "__extra__" not in out
        assert len(out) == 18


# ===========================================================================
# §51.2/§52 exact-int — int subclass / IntEnum rejected (positive coverage)
# ===========================================================================


class TestExactIntSubclassEnumRejected:
    """§51.2/§52 exact-int — int subclasses and IntEnum members are rejected
    (never coerced) on next_id values and identity-key components."""

    @pytest.mark.parametrize("value", [
        _DerivedInt(9), _StatusLikeIntEnum.CONFIRMED_LIKE,
    ])
    def test_next_id_value_rejected(self, value) -> None:
        snap = _baseline_snapshot()
        snap["next_id"]["claim"] = value
        _assert_raises_and_input_unchanged(snap, TypeError)

    @pytest.mark.parametrize("comp", [
        _DerivedInt(9), _StatusLikeIntEnum.CONFIRMED_LIKE,
    ])
    def test_rule_stats_identity_component_rejected(self, comp) -> None:
        snap = _baseline_snapshot()
        snap["rule_stats"].append(_collection_item(
            [comp, 9], dict(_RULE_STATS_VALUE_TEMPLATE)))
        _assert_raises_and_input_unchanged(snap, TypeError)

    @pytest.mark.parametrize("comp", [
        _DerivedInt(9), _StatusLikeIntEnum.CONFIRMED_LIKE,
    ])
    def test_gap_dedup_identity_component_rejected(self, comp) -> None:
        snap = _baseline_snapshot()
        snap["gap_dedup_index"].append(_collection_item(
            [comp, 1, 1, 42], 1))
        _assert_raises_and_input_unchanged(snap, TypeError)
