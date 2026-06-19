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

import pytest

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    Engine,
)


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
    @pytest.mark.parametrize(("label", "bad_key"), [
        ("two_element",   [1, 2]),
        ("three_element", [1, 2, 3]),
        ("five_element",  [1, 2, 3, 4, 5]),
        ("not_a_list",    "1:2:3:4"),
        ("bool_component", [True, 2, 3, 4]),
        ("float_component", [1, 2, 3, 4.0]),
        ("str_component",  ["1", 2, 3, 4]),
    ])
    def test_invalid_key_shape_raises_type_error(
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
        """An entry with empty resolved set is admissible — nothing to subset-check."""
        snap = _baseline_snapshot()
        # claim 1 has contradiction registered; empty resolved set is fine.
        snap["resolved_contradictions"].append(_collection_item(1, []))
        # claim 1 already in contradictions, so this works.
        restored = Engine.from_snapshot(snap)
        assert restored is not None


# ===========================================================================
# §52.4 — RuleStats identity shape
# ===========================================================================


_RULE_STATS_VALUE_TEMPLATE = {
    "rule_id": 9, "rule_version": 9, "firing_count": 0,
    "confirmed_true_count": 0, "confirmed_false_count": 0,
    "observed_precision": None, "false_positive_rate": None,
}


class TestRuleStatsIdentityShape:
    @pytest.mark.parametrize(("label", "bad_key"), [
        ("one_element",   [1]),
        ("three_element", [1, 1, 1]),
        ("not_a_list",    "1:1"),
        ("bool_first",    [True, 1]),
        ("bool_second",   [1, True]),
        ("float_first",   [1.0, 1]),
        ("float_second",  [1, 1.0]),
        ("str_first",     ["1", 1]),
        ("str_second",    [1, "1"]),
        ("none_first",    [None, 1]),
        ("none_second",   [1, None]),
    ])
    def test_invalid_identity_shape_raises_type_error(
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
        assert public == 41
        assert private == 19

    def test_ragcore_all_unchanged(self) -> None:
        import ragcore
        # PR73-M04 shift: 48 → 49 (added EngineStateIdentity).
        assert len(ragcore.__all__) == 49

    def test_snapshot_schema_version_unchanged(self) -> None:
        assert Engine().to_snapshot()["schema_version"] == 2

    def test_snapshot_top_level_keys_unchanged(self) -> None:
        assert len(Engine().to_snapshot()) == 18
