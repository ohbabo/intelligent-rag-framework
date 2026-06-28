"""Tests for PR21-L — Effective confidence evidence_type modifier
(MVP, caller-registered, weak source-quality + snapshot schema v2 bump).

Invariants of ``compute_effective_confidence`` 의 7-modifier composition:
    effective = base × status × freshness × gap × count × rule_stats × evidence_type

**91차 (test-first) 상태**: PR20-F 의 6-modifier 까지만. evidence_type_modifier
미적용. register_hint_evidence_types API 없음. snapshot schema_version 1 유지.
fail pattern mixed (PR20-F 87차 동일):

§33.15 의 40 invariant 매핑은 클래스별 docstring 에 명시.

Collection-error 방지: 아직 존재하지 않을 수 있는 attribute/constant 는
`getattr(target, "...", None)` 패턴으로 lookup. AttributeError 가 collection
단계에서 발생하지 않도록 주의.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

import ragcore
import ragcore.types as types_module
# Phase 4: snapshot schema-version constants + migration internals are owned by
# ragcore._engine.serialization (the Phase-1 ragcore.engine re-export shim was
# removed); look them up at their real owner.
from ragcore._engine import serialization
from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    Engine,
    RuleDefinition,
    ScoreValue,
)


# ---- Helpers ---------------------------------------------------------------


def _register_rule(
    engine: Engine,
    *,
    rule_id: int = 1,
    rule_version: int = 1,
    prior_confidence: float = 0.5,
) -> None:
    engine.register_rule(
        RuleDefinition(
            id=rule_id, version=rule_version, maturity=0,
            prior_confidence=ScoreValue(prior_confidence),
        )
    )


def _bump_firing(
    engine: Engine, *,
    rule_id: int = 1, rule_version: int = 1, delta: int,
) -> None:
    engine.update_rule_stats(
        rule_id=rule_id, rule_version=rule_version, firing_delta=delta,
    )


def _claim_with_rule(
    engine: Engine, *,
    rule_id: int = 1, rule_version: int = 1, base_confidence: float = 1.0,
) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id, claim_type=1,
        rule_id=rule_id, rule_version=rule_version, reason_code=0,
        base_confidence=base_confidence,
    )
    return entity_id, claim_id


def _claim_without_rule(
    engine: Engine, *, base_confidence: float = 1.0,
) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id, claim_type=1,
        rule_id=0, rule_version=0, reason_code=0,
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


def _unresolved_gap(engine: Engine, claim_id: int) -> int:
    return engine.add_gap(
        claim_id=claim_id, gap_type=1, required_evidence_type=99,
        severity=0.5, rule_id=1,
    )


def _safe_register_hint(engine: Engine, types_iter) -> bool:
    """Call engine.register_hint_evidence_types if it exists. Return True if call succeeded."""
    api = getattr(engine, "register_hint_evidence_types", None)
    if api is None:
        return False
    api(types_iter)
    return True


# ---- 1. Registration API contract (Sub-decision AF) ------------------------


class TestEvidenceTypeRegistrationApi:
    """§33.15 invariants 10~13 — register_hint_evidence_types API surface."""

    # invariant 10 (existence)
    def test_register_hint_api_exists(self) -> None:
        engine = Engine()
        assert hasattr(engine, "register_hint_evidence_types")

    # invariant 10 (callable with list)
    def test_register_with_list(self) -> None:
        engine = Engine()
        api = getattr(engine, "register_hint_evidence_types", None)
        assert api is not None
        api([1, 2])
        # post-condition: snapshot 에 sorted list 로 노출되어야 한다 (Sub-decision AG)
        snap = engine.to_snapshot()
        assert snap.get("hint_evidence_types") == [1, 2]

    # invariant 10 (callable with tuple)
    def test_register_with_tuple(self) -> None:
        engine = Engine()
        api = getattr(engine, "register_hint_evidence_types", None)
        assert api is not None
        api((3, 1, 2))
        snap = engine.to_snapshot()
        assert snap.get("hint_evidence_types") == [1, 2, 3]

    # invariant 10 (callable with frozenset)
    def test_register_with_frozenset(self) -> None:
        engine = Engine()
        api = getattr(engine, "register_hint_evidence_types", None)
        assert api is not None
        api(frozenset({5, 1, 3}))
        snap = engine.to_snapshot()
        assert snap.get("hint_evidence_types") == [1, 3, 5]

    # invariant 13 (idempotent — duplicate ignored)
    def test_register_is_idempotent_on_duplicates(self) -> None:
        engine = Engine()
        api = getattr(engine, "register_hint_evidence_types", None)
        assert api is not None
        api([1, 1, 1, 2, 2])
        snap = engine.to_snapshot()
        assert snap.get("hint_evidence_types") == [1, 2]

    # invariant 12 (accumulation across calls)
    def test_register_accumulates_across_calls(self) -> None:
        engine = Engine()
        api = getattr(engine, "register_hint_evidence_types", None)
        assert api is not None
        api([1])
        api([2])
        api([3, 1])  # overlap
        snap = engine.to_snapshot()
        assert snap.get("hint_evidence_types") == [1, 2, 3]

    # invariant 11 (empty iterable is no-op)
    def test_register_empty_iterable_is_noop(self) -> None:
        engine = Engine()
        api = getattr(engine, "register_hint_evidence_types", None)
        assert api is not None
        api([])
        snap = engine.to_snapshot()
        assert snap.get("hint_evidence_types") == []


# ---- 2. Compatibility (Sub-decision AB / AE) -------------------------------


class TestEvidenceTypeModifierCompatibility:
    """§33.15 invariants 1~4 — empty registration / no direct evidence."""

    # invariant 1 — empty registration → all claims modifier 1.0
    def test_empty_registration_all_claims_modifier_one(self) -> None:
        engine = Engine()
        _, claim_id = _claim_with_rule(engine, base_confidence=0.7)
        # no register_hint_evidence_types call → empty
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 2 — empty registration + direct evidence → still 1.0
    def test_empty_registration_with_direct_evidence_is_one(self) -> None:
        engine = Engine()
        _, claim_id = _claim_with_rule(engine, base_confidence=0.7)
        _evidence(engine, claim_id, evidence_type=42)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 3 — empty registration + no direct evidence → 1.0
    def test_empty_registration_no_direct_evidence_is_one(self) -> None:
        engine = Engine()
        _, claim_id = _claim_with_rule(engine, base_confidence=0.7)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 4 — hint registered + no direct evidence → 1.0 (Sub-decision AB)
    def test_hint_registered_no_direct_evidence_is_one(self) -> None:
        engine = Engine()
        _safe_register_hint(engine, [1, 2])
        _, claim_id = _claim_with_rule(engine, base_confidence=0.8)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.8)

    # Sub-decision AA — evidence on different claim does not affect this claim
    def test_other_claim_evidence_not_counted(self) -> None:
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_a = _claim_with_rule(engine, base_confidence=1.0)
        _, claim_b = _claim_with_rule(engine, base_confidence=1.0)
        _evidence(engine, claim_a, evidence_type=42)
        # claim_b has no direct evidence → modifier 1.0 (Sub-decision AB)
        result = engine.compute_effective_confidence(claim_b)
        assert result.value == pytest.approx(1.0)

    # Sub-decision AA — contradiction evidence is NOT counted as direct supporting
    def test_contradiction_evidence_not_counted_as_direct(self) -> None:
        """Hint set = {42}; only direct evidence is a contradiction (type=42).
        → direct supporting evidence = 0 → modifier 1.0 (Sub-decision AB)."""
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        ev = _evidence(engine, claim_id, evidence_type=42, strength=0.0)
        engine.register_contradiction(claim_id, ev)
        # If contradiction WERE counted as direct, all-hint condition would
        # trigger 0.9. But Sub-decision AA excludes contradiction evidence,
        # so direct = [] → modifier 1.0.
        # Composition: base × status × freshness (1.0, strength=0) × no gap × count(1) × no rule_stats × evidence_type
        # = 1.0 × 1.0 × 1.0 × 1.0 × 1.0 × 1.0 × 1.0 = 1.0
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)

    # Sub-decision AA — resolved contradiction evidence also excluded
    def test_resolved_contradiction_evidence_not_counted_as_direct(self) -> None:
        """A contradiction evidence that has been resolved is still NOT
        direct supporting evidence (Sub-decision AA)."""
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        ev = _evidence(engine, claim_id, evidence_type=42, strength=0.0)
        engine.register_contradiction(claim_id, ev)
        engine.register_contradiction_resolution(claim_id, ev)
        result = engine.compute_effective_confidence(claim_id)
        # direct = [] → modifier 1.0
        assert result.value == pytest.approx(1.0)


# ---- 3. Hint-only penalty (Sub-decision AC) --------------------------------


class TestEvidenceTypeHintOnlyPenalty:
    """§33.15 invariants 5~9 — all-hint penalty + mixed → 1.0 + no boost."""

    # invariant 5 — one direct evidence with hint type → 0.9 ★
    def test_single_hint_direct_evidence_penalty(self) -> None:
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42, strength=0.5)
        result = engine.compute_effective_confidence(claim_id)
        # base 1.0 × all_other 1.0 × evidence_type 0.9 = 0.9
        assert result.value == pytest.approx(0.9)

    # invariant 6 — multiple direct evidence all hint → 0.9 ★
    def test_multiple_all_hint_direct_evidence_penalty(self) -> None:
        engine = Engine()
        _safe_register_hint(engine, [42, 43])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)
        _evidence(engine, claim_id, evidence_type=43)
        _evidence(engine, claim_id, evidence_type=42)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.9)

    # invariant 7 — mixed hint + non-hint → 1.0 ★
    def test_mixed_hint_and_non_hint_no_penalty(self) -> None:
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)
        _evidence(engine, claim_id, evidence_type=99)  # non-hint
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)

    # invariant 8 — single non-hint direct evidence → 1.0
    def test_single_non_hint_direct_evidence_no_penalty(self) -> None:
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=99)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)

    # invariant 9 — no boost with many direct hint evidence ★
    def test_no_boost_with_many_hint_evidence(self) -> None:
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        for _ in range(100):
            _evidence(engine, claim_id, evidence_type=42)
        result = engine.compute_effective_confidence(claim_id)
        # still 0.9, NOT > 1.0
        assert result.value == pytest.approx(0.9)

    # vacuous-truth trap protection — all([]) must NOT trigger penalty
    def test_all_empty_does_not_trigger_penalty(self) -> None:
        """all([]) is Python-True, but Sub-decision AB requires modifier=1.0
        when direct evidence is empty. This locks the vacuous-truth trap."""
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        # No add_evidence calls → direct = []
        result = engine.compute_effective_confidence(claim_id)
        # Must be 1.0, NOT 0.9
        assert result.value == pytest.approx(1.0)


# ---- 4. 7-modifier composition ---------------------------------------------


class TestEvidenceTypeComposition:
    """§33.15 invariants 14~21 — composition with status / freshness / gap /
    count / rule_stats."""

    # invariant 14 — refuted dominate
    def test_refuted_with_hint_only_is_zero(self) -> None:
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.0)

    # invariant 15 — candidate + hint-only → base × 0.9 ★
    def test_candidate_with_hint_only_applies_evidence_type_only(self) -> None:
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)
        result = engine.compute_effective_confidence(claim_id)
        # 1.0 × 1.0 (cand) × 1.0 (no contra) × 1.0 (no gap) × 1.0 (count) × 1.0 (no rule stats: rule miss) × 0.9 = 0.9
        assert result.value == pytest.approx(0.9)

    # invariant 16 — disputed + hint-only → base × 0.5 × 0.9 ★
    def test_disputed_with_hint_only_combines_status_and_evidence_type(self) -> None:
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # 1.0 × 0.5 × 1.0 × 1.0 × 1.0 × 1.0 × 0.9 = 0.45
        assert result.value == pytest.approx(0.45)

    # invariant 17 — freshness + hint-only → freshness × 0.9 ★
    def test_freshness_and_hint_only(self) -> None:
        """active 1 contradiction (type 99 / strength 0.8) + 1 hint direct (type 42).
        → freshness=0.6, evidence_type=0.9. 0.6 × 0.9 = 0.54.
        contradiction evidence (type 99) is NOT counted in direct (Sub-decision AA)
        so direct = [type=42] = all hint."""
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)
        contra = _evidence(engine, claim_id, evidence_type=99, strength=0.8)
        engine.register_contradiction(claim_id, contra)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # 1.0 × 1.0 × 0.6 × 1.0 × 1.0 × 1.0 × 0.9 = 0.54
        assert result.value == pytest.approx(0.54)

    # invariant 18 — gap × hint-only → gap (PR23-M tier) × 0.9 ★
    def test_unresolved_gap_and_hint_only(self) -> None:
        """unresolved gap 1 개 + hint-only direct → 1.0 × 0.9 × 0.9 = 0.81.

        PR23-M §35.5 (AP): 1 unresolved → tier 1 → 0.9 (PR12-D binary 0.8 정제).
        의미 (gap × evidence_type 결합) 보존, gap 강도만 갱신.
        """
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)
        _unresolved_gap(engine, claim_id)
        result = engine.compute_effective_confidence(claim_id)
        # 1.0 × 1.0 × 1.0 × 0.9 (1 unresolved tier) × 1.0 × 1.0 × 0.9 = 0.81
        assert result.value == pytest.approx(0.81)

    # invariant 19 — count × hint-only (PR24-N 자연 만료) ★
    def test_active_two_and_hint_only(self) -> None:
        """2 active contradictions (type 99, strength 0) + 1 hint direct (type 42).

        PR24-N §36.6 (AX): active 2 avg 0.0 → count = 1.0 (binary 0.8 자연 만료).
        의미 (count × evidence_type 결합) 보존, count 강도만 정밀화.
        빈 강도의 contradiction 은 repeated pressure 가 아니다.

        → count = 1.0, evidence_type = 0.9. 1.0 × 0.9 = 0.9.
        """
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=42)
        c1 = _evidence(engine, claim_id, evidence_type=99, strength=0.0)
        c2 = _evidence(engine, claim_id, evidence_type=99, strength=0.0)
        engine.register_contradiction(claim_id, c1)
        engine.register_contradiction(claim_id, c2)
        result = engine.compute_effective_confidence(claim_id)
        # 1.0 × 1.0 × 1.0 × 1.0 × 1.0 (count avg 0) × 1.0 × 0.9 = 0.9
        assert result.value == pytest.approx(0.9)

    # invariant 20 — rule_stats + hint-only → rule_stats × 0.9 ★
    def test_rule_stats_penalty_and_hint_only(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)  # firing=1 → 0.9
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        _evidence(engine, claim_id, evidence_type=42)
        result = engine.compute_effective_confidence(claim_id)
        # rule_stats 0.9 × evidence_type 0.9 = 0.81
        assert result.value == pytest.approx(0.81)

    # invariant 21 — full 7-modifier composition (PR24-N 자연 만료) ★
    def test_full_seven_modifier_composition(self) -> None:
        """disputed + active 2 (0.3/0.8) + unresolved gap 1 개 + firing 1
        + hint-only direct evidence.

        PR23-M §35.5 (AP): 1 unresolved → tier 1 → 0.9.
        PR24-N §36.6 (AX): active 2 avg 0.55 → count 0.8625 (PR19-E binary 0.8 정제).
        의미 (7-modifier 결합) 보존, count 강도만 정밀화.

        base × status × freshness × gap × count × rule_stats × evidence_type
        = 1.0 × 0.5 × (1.0 - 0.8 × 0.5) × 0.9 × 0.8625 × 0.9 × 0.9
        = 1.0 × 0.5 × 0.6 × 0.9 × 0.8625 × 0.9 × 0.9
        = 0.18862875
        """
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        _evidence(engine, claim_id, evidence_type=42)  # direct hint
        c1 = _evidence(engine, claim_id, evidence_type=99, strength=0.3)
        c2 = _evidence(engine, claim_id, evidence_type=99, strength=0.8)
        engine.register_contradiction(claim_id, c1)
        engine.register_contradiction(claim_id, c2)
        _unresolved_gap(engine, claim_id)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.18862875)


# ---- 5. Snapshot schema v2 + migration (Sub-decision AG/AH) ----------------


class TestEvidenceTypeSnapshotSchemaV2:
    """§33.15 invariants 25~31 — schema version bump + v1 migration."""

    # invariant 27 — to_snapshot schema_version == 2 ★
    def test_to_snapshot_schema_version_is_two(self) -> None:
        engine = Engine()
        snap = engine.to_snapshot()
        assert snap["schema_version"] == 2

    # invariant 27 — hint_evidence_types key always present in snapshot
    def test_snapshot_has_hint_evidence_types_key(self) -> None:
        engine = Engine()
        snap = engine.to_snapshot()
        assert "hint_evidence_types" in snap

    # invariant 26 — sorted list serialization (deterministic) ★
    def test_hint_evidence_types_serialized_as_sorted_list(self) -> None:
        engine = Engine()
        api = getattr(engine, "register_hint_evidence_types", None)
        assert api is not None
        api([5, 1, 3, 2, 4])
        snap = engine.to_snapshot()
        assert snap["hint_evidence_types"] == [1, 2, 3, 4, 5]

    # invariant 27 — empty registration → []
    def test_empty_registration_snapshot_is_empty_list(self) -> None:
        engine = Engine()
        snap = engine.to_snapshot()
        assert snap.get("hint_evidence_types") == []

    # invariant 25 — round-trip preserves hint set ★
    def test_round_trip_preserves_hint_evidence_types(self) -> None:
        engine = Engine()
        api = getattr(engine, "register_hint_evidence_types", None)
        assert api is not None
        api([1, 2, 7])
        snap = engine.to_snapshot()
        restored = Engine.from_snapshot(snap)
        # restored._hint_evidence_types should equal frozenset({1,2,7})
        attr = getattr(restored, "_hint_evidence_types", None)
        assert attr == frozenset({1, 2, 7})

    # invariant 28 — v1 snapshot migration → hint_evidence_types empty ★
    def test_v1_snapshot_migrates_to_empty_hint_set(self) -> None:
        """v1 snapshot (no hint_evidence_types key) → restored with empty
        frozenset (Sub-decision AH: default migration)."""
        engine = Engine()
        snap_v2 = engine.to_snapshot()
        # synthesize a v1 snapshot from v2: drop hint_evidence_types, downgrade version
        snap_v1 = {k: v for k, v in snap_v2.items() if k != "hint_evidence_types"}
        snap_v1["schema_version"] = 1
        restored = Engine.from_snapshot(snap_v1)
        attr = getattr(restored, "_hint_evidence_types", None)
        assert attr == frozenset()

    # invariant 29 — v1 migration preserves other fields ★
    def test_v1_migration_preserves_other_fields(self) -> None:
        engine = Engine()
        _, claim_id = _claim_with_rule(engine, base_confidence=0.7)
        snap_v2 = engine.to_snapshot()
        snap_v1 = {k: v for k, v in snap_v2.items() if k != "hint_evidence_types"}
        snap_v1["schema_version"] = 1
        restored = Engine.from_snapshot(snap_v1)
        # The Claim should be intact
        assert restored.get_claim(claim_id).base_confidence.value == pytest.approx(0.7)

    # invariant 36 — _CURRENT_SNAPSHOT_SCHEMA_VERSION == 2 ★
    def test_current_snapshot_schema_version_constant_is_two(self) -> None:
        val = getattr(serialization, "_CURRENT_SNAPSHOT_SCHEMA_VERSION", None)
        assert val == 2

    # invariant 30 — _SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS contains 1 and 2 ★
    def test_supported_versions_contains_one_and_two(self) -> None:
        val = getattr(serialization, "_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS", None)
        assert val is not None
        assert 1 in val and 2 in val

    # invariant 38 — _migrate_snapshot_v1_to_v2 does not mutate input ★
    def test_migrate_v1_to_v2_does_not_mutate_input(self) -> None:
        func = getattr(serialization, "_migrate_snapshot_v1_to_v2", None)
        assert func is not None and callable(func)
        v1 = {"schema_version": 1, "some_field": "x"}
        v1_copy = dict(v1)
        _ = func(v1)
        assert v1 == v1_copy, "Migration step must not mutate input snapshot"

    # invariant 31 — unknown high version still raises
    def test_unknown_high_version_still_raises(self) -> None:
        with pytest.raises(ValueError):
            Engine.from_snapshot({"schema_version": 99})


# ---- 6. No state mutation + previous-modifier regression -------------------


class TestEvidenceTypeNoStateMutationAndRegression:
    """§33.15 invariants 22~24 + 32~40 — read-only + previous PR meaning preserved."""

    # invariant 22 — to_snapshot identical before/after compute
    def test_snapshot_identical_before_and_after_compute(self) -> None:
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=0.7)
        _evidence(engine, claim_id, evidence_type=42)
        snap_before = engine.to_snapshot()
        _ = engine.compute_effective_confidence(claim_id)
        snap_after = engine.to_snapshot()
        assert snap_before == snap_after

    # invariant 23 — _hint_evidence_types unchanged after compute
    def test_hint_set_unchanged_after_compute(self) -> None:
        engine = Engine()
        api = getattr(engine, "register_hint_evidence_types", None)
        if api is not None:
            api([42, 7])
        before = getattr(engine, "_hint_evidence_types", None)
        _, claim_id = _claim_with_rule(engine, base_confidence=0.7)
        _ = engine.compute_effective_confidence(claim_id)
        after = getattr(engine, "_hint_evidence_types", None)
        assert before == after

    # invariant 24 — _lifecycle_seq unchanged
    def test_lifecycle_seq_unchanged_after_compute(self) -> None:
        engine = Engine()
        _safe_register_hint(engine, [42])
        _, claim_id = _claim_with_rule(engine, base_confidence=0.7)
        _evidence(engine, claim_id, evidence_type=42)
        seq_before = engine._lifecycle_seq
        _ = engine.compute_effective_confidence(claim_id)
        assert engine._lifecycle_seq == seq_before

    # invariant 32 — PR11-C freshness modifier preserved (empty hint → 1.0)
    def test_pr11c_freshness_modifier_preserved_without_hint(self) -> None:
        """empty hint → evidence_type=1.0; freshness still does its thing."""
        engine = Engine()
        # no register_hint → empty
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        ev = _evidence(engine, claim_id, evidence_type=99, strength=0.8)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # 1.0 × 1.0 × 0.6 × 1.0 × 1.0 × 1.0 × 1.0 (empty hint) = 0.6
        assert result.value == pytest.approx(0.6)

    # invariant 33 — PR12-D gap modifier 의미 보존 (PR23-M tier 강도 갱신, empty hint)
    def test_pr12d_gap_modifier_preserved_without_hint(self) -> None:
        """unresolved gap 1 개, empty hint → 1.0 × 0.9 × 1.0 = 0.9.

        PR23-M §35.5 (AP): 1 unresolved → tier 1 → 0.9. PR12-D 의 "unresolved →
        attenuation" 의미 보존, 강도만 binary 0.8 → tier 0.9 로 정제.
        """
        engine = Engine()
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        _unresolved_gap(engine, claim_id)
        result = engine.compute_effective_confidence(claim_id)
        # gap=0.9 (1 unresolved tier), evidence_type=1.0 → 0.9
        assert result.value == pytest.approx(0.9)

    # invariant 34 — PR19-E threshold=2 보존 (PR24-N tier 강도 갱신)
    def test_pr19e_count_modifier_preserved_without_hint(self) -> None:
        """PR19-E threshold=2 구조는 보존된다.
        PR24-N §36.6 (AX): avg 0.0 → count = 1.0 (PR19-E binary 0.8 자연 만료).
        빈 강도의 contradiction 은 repeated pressure 가 아니다.
        """
        engine = Engine()
        _, claim_id = _claim_with_rule(engine, base_confidence=1.0)
        c1 = _evidence(engine, claim_id, evidence_type=99, strength=0.0)
        c2 = _evidence(engine, claim_id, evidence_type=99, strength=0.0)
        engine.register_contradiction(claim_id, c1)
        engine.register_contradiction(claim_id, c2)
        result = engine.compute_effective_confidence(claim_id)
        # count = 1.0 (avg 0), evidence_type = 1.0 (empty hint) → 1.0
        assert result.value == pytest.approx(1.0)

    # invariant 35 — PR20-F rule_stats modifier preserved (empty hint)
    def test_pr20f_rule_stats_modifier_preserved_without_hint(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        # rule_stats=0.9, evidence_type=1.0 → 0.9
        assert result.value == pytest.approx(0.9)

    # invariant 38 — _EVIDENCE_TYPE_PENALTY_MODIFIER private (not in ragcore)
    def test_evidence_type_penalty_modifier_not_exported(self) -> None:
        assert not hasattr(ragcore, "_EVIDENCE_TYPE_PENALTY_MODIFIER")
        assert not hasattr(types_module, "_EVIDENCE_TYPE_PENALTY_MODIFIER")

    # invariant 39 — _hint_evidence_types not in types_module (engine-private)
    def test_hint_evidence_types_state_not_in_types_module(self) -> None:
        assert not hasattr(types_module, "_hint_evidence_types")
