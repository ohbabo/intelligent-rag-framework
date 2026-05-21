"""Tests for PR26-R — RuleStats modifier continuous maturity refinement.

PR26-R §38:
    RuleStats modifier is a weak maturity signal, not a rule quality verdict.
    Continuous refinement separates zero-observation from one-observation
    without introducing quality judgment.

PR26-R changes only the internal calculation of the rule_stats modifier:

Before (PR20-F binary):
    firing_count < 2  → 0.9
    firing_count >= 2 → 1.0
    sentinel / lookup miss → 1.0

After (PR26-R continuous maturity):
    sentinel / lookup miss → 1.0  (Sub-decision BO preserved)
    capped = min(max(firing_count, 0), 2)         (Sub-decision BQ defensive clamp)
    maturity_ratio = capped / 2
    modifier = 1.0 - (1.0 - maturity_ratio) × 0.2 (Sub-decision BM)

Center preservation (Sub-decision BP):
    firing_count == 1 → 0.9 (PR20-F binary 중심점 자연 재현, 자연 만료 아님)

Only firing_count == 0 has natural expiry: 0.9 → 0.8.

111차 expected fail pattern:
    - firing_count == 0 expected 0.8, current 0.9
    - negative firing_count expected 0.8 (defensive clamp), current 0.9
    - _RULE_STATS_MATURITY_PENALTY_WEIGHT missing
    - _RULE_STATS_MATURITY_SATURATION_COUNT missing
    - old _RULE_STATS_PENALTY_MODIFIER still exists
    - old _RULE_STATS_MIN_FIRING_COUNT still exists
    - full composition with firing 0 expected lower value
"""

from __future__ import annotations

from dataclasses import replace

import pytest

import ragcore
import ragcore.engine as engine_module
import ragcore.types as types_module
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


def _set_firing_count(
    engine: Engine, *, rule_id: int = 1, rule_version: int = 1, count: int,
) -> None:
    """register_rule already inits firing_count=0. Use update_rule_stats delta to reach target.

    For testing negative or very large firing_count, we use the delta API directly.
    """
    current = engine._rule_stats[(rule_id, rule_version)].firing_count
    delta = count - current
    if delta != 0:
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


def _active_contradictions(
    engine: Engine, claim_id: int, strengths: tuple[float, ...],
) -> tuple[int, ...]:
    ids: list[int] = []
    for strength in strengths:
        ev = _evidence(engine, claim_id, evidence_type=99, strength=strength)
        engine.register_contradiction(claim_id, ev)
        ids.append(ev)
    return tuple(ids)


def _unresolved_gap(
    engine: Engine, claim_id: int, *,
    required_evidence_type: int = 99, rule_id: int = 1,
) -> int:
    return engine.add_gap(
        claim_id=claim_id, gap_type=1,
        required_evidence_type=required_evidence_type,
        severity=0.5, rule_id=rule_id,
    )


# ---- 1. Sentinel + lookup miss (Sub-decision BO, compat 보존) -------------


class TestRuleStatsContinuousSentinelAndLookup:
    """§38.15 invariants 1~4 — PR20-F Sub-decision Y 호환 보존."""

    # invariant 1
    def test_sentinel_rule_id_zero_returns_one(self) -> None:
        engine = Engine()
        _, claim_id = _claim_without_rule(engine, base_confidence=0.7)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 2
    def test_sentinel_with_nonzero_version_still_one(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=0, rule_version=5,
            reason_code=0, base_confidence=0.8,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.8)

    # invariant 3
    def test_unregistered_rule_pair_is_lookup_miss(self) -> None:
        engine = Engine()
        _, claim_id = _claim_with_rule(
            engine, rule_id=99, rule_version=1, base_confidence=0.6,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.6)

    # invariant 4
    def test_same_rule_id_different_version_is_lookup_miss(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, rule_id=1, rule_version=1, count=0)
        # claim references (1, 2) which is NOT registered → miss → 1.0
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=2, base_confidence=0.5,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.5)


# ---- 2. Firing_count value mapping (Sub-decision BL/BM) -------------------


class TestRuleStatsContinuousMapping:
    """§38.15 invariants 5~9 — continuous mapping."""

    # invariant 5 ★ — firing 0 → 0.8 (PR20-F 0.9 자연 만료)
    def test_firing_count_zero_returns_zero_point_eight(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        # firing_count = 0 (initial)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        # PR26-R: maturity_ratio 0.0 → 1.0 - 1.0 × 0.2 = 0.8
        assert result.value == pytest.approx(0.8)

    # invariant 6 — firing 1 → 0.9 (PR20-F 중심점 보존)
    def test_firing_count_one_preserves_pr20f_center(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        # PR26-R: maturity_ratio 0.5 → 1.0 - 0.5 × 0.2 = 0.9
        # PR20-F binary 0.9 자연 재현
        assert result.value == pytest.approx(0.9)

    # invariant 7 — firing 2 → 1.0 (saturated)
    def test_firing_count_two_is_saturated(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=2)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)

    # invariant 8 — firing 10 → 1.0 (saturated)
    def test_firing_count_ten_stays_saturated(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=10)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)

    # invariant 9 — firing 1_000_000 → 1.0 (saturated, no boost)
    def test_firing_count_million_stays_saturated(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=1_000_000)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)


# ---- 3. Defensive clamp (Sub-decision BQ) ---------------------------------


class TestRuleStatsContinuousDefensiveClamp:
    """§38.15 invariants 10~12 — negative firing_count safe handling."""

    # invariant 10 ★ — negative firing_count clamped to 0 → 0.8
    def test_negative_firing_count_clamps_to_zero(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        # external call manages to push firing_count negative
        engine.update_rule_stats(rule_id=1, rule_version=1, firing_delta=-5)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        # PR26-R: max(-5, 0) = 0 → modifier = 0.8 (floor)
        assert result.value == pytest.approx(0.8)

    # invariant 11 — modifier never < 0.8
    def test_modifier_never_below_floor(self) -> None:
        """Even very negative firing_count must not drop modifier below 0.8."""
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        engine.update_rule_stats(rule_id=1, rule_version=1, firing_delta=-1_000_000)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value >= 0.8 - 1e-9
        assert result.value == pytest.approx(0.8)

    # invariant 12 — clamp does not mutate stored RuleStats
    def test_clamp_does_not_mutate_stored_rule_stats(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        engine.update_rule_stats(rule_id=1, rule_version=1, firing_delta=-3)
        before = engine._rule_stats[(1, 1)].firing_count
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        _ = engine.compute_effective_confidence(claim_id)
        after = engine._rule_stats[(1, 1)].firing_count
        assert before == after == -3  # stored value untouched


# ---- 4. No boost / range (Sub-decision BN) --------------------------------


class TestRuleStatsContinuousBoundary:
    """§38.15 invariants 13~14 — range [0.8, 1.0], no boost."""

    # invariant 13 — modifier range [0.8, 1.0] for sample firing counts
    def test_modifier_range_sample_values(self) -> None:
        for firing in (0, 1, 2, 5, 100):
            engine = Engine()
            _register_rule(engine, rule_id=1, rule_version=1)
            _set_firing_count(engine, count=firing)
            _, claim_id = _claim_with_rule(
                engine, rule_id=1, rule_version=1, base_confidence=1.0,
            )
            result = engine.compute_effective_confidence(claim_id)
            assert 0.8 <= result.value <= 1.0 + 1e-9, (
                f"firing={firing} produced {result.value}, expected ∈ [0.8, 1.0]"
            )

    # invariant 14 — never boost above 1.0 (no rule_stats overrides base_confidence × others)
    def test_modifier_never_exceeds_one(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=1_000_000)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value <= 1.0 + 1e-9


# ---- 5. Composition (7-modifier) ------------------------------------------


class TestRuleStatsContinuousComposition:
    """§38.15 invariants 15~21 — composition with PR23-M/PR24-N/PR21-L."""

    # invariant 15 — refuted dominate (status 0.0)
    def test_refuted_dominates_any_firing(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.0)

    # invariant 16 ★ — confirmed + firing 0 → base × 0.8
    def test_confirmed_with_firing_zero(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # confirmed 1.0 × rule_stats 0.8 = 0.8
        assert result.value == pytest.approx(0.8)

    # invariant 17 — confirmed + firing 1 → base × 0.9 (PR20-F 와 동일)
    def test_confirmed_with_firing_one(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.9)

    # invariant 18 — confirmed + firing 2 → base × 1.0
    def test_confirmed_with_firing_two(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=2)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)

    # invariant 19 ★ — disputed + firing 0 → 0.5 × 0.8 = 0.40
    def test_disputed_with_firing_zero(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.40)

    # invariant 20 — disputed + firing 1 → 0.5 × 0.9 = 0.45 (PR20-F 와 동일)
    def test_disputed_with_firing_one(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.45)

    # invariant 21 ★ — full 7-modifier composition with firing 0
    def test_full_seven_modifier_composition_with_firing_zero(self) -> None:
        """disputed + active 2 (0.3/0.8 avg 0.55) + 3 unresolved gaps + firing 0 + hint-only direct.

        base × status × freshness × gap × count × rule_stats × evidence_type
        = 1.0 × 0.5 × 0.6 × 0.7 × 0.8625 × 0.8 × 0.9
        = 0.130410
        """
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=0)
        engine.register_hint_evidence_types([42])
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        # hint-only direct evidence (type 42)
        _evidence(engine, claim_id, evidence_type=42, strength=0.5)
        # active contradictions: strength 0.3 / 0.8 (most recent 0.8 → freshness 0.6, avg 0.55 → count 0.8625)
        c1 = _evidence(engine, claim_id, evidence_type=99, strength=0.3)
        c2 = _evidence(engine, claim_id, evidence_type=99, strength=0.8)
        engine.register_contradiction(claim_id, c1)
        engine.register_contradiction(claim_id, c2)
        # 3 unresolved gaps → tier 0.7
        _unresolved_gap(engine, claim_id, required_evidence_type=801)
        _unresolved_gap(engine, claim_id, required_evidence_type=802)
        _unresolved_gap(engine, claim_id, required_evidence_type=803)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # 1.0 × 0.5 × 0.6 × 0.7 × 0.8625 × 0.8 × 0.9 = 0.130410
        assert result.value == pytest.approx(0.130410)


# ---- 6. No state mutation -------------------------------------------------


class TestRuleStatsContinuousNoStateMutation:
    """§38.15 invariants 22~25 — compute is read-only."""

    def test_snapshot_identical_before_and_after_compute(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=0)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=0.7,
        )
        snap_before = engine.to_snapshot()
        _ = engine.compute_effective_confidence(claim_id)
        snap_after = engine.to_snapshot()
        assert snap_before == snap_after

    def test_rule_stats_unchanged_after_compute(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _set_firing_count(engine, count=0)
        before = dict(engine._rule_stats)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=0.7,
        )
        _ = engine.compute_effective_confidence(claim_id)
        after = dict(engine._rule_stats)
        assert before == after

    def test_lifecycle_seq_unchanged_after_compute(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=0.7,
        )
        seq_before = engine._lifecycle_seq
        _ = engine.compute_effective_confidence(claim_id)
        assert engine._lifecycle_seq == seq_before

    def test_lifecycle_history_unchanged_after_compute(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=0.7,
        )
        hist_before = list(engine.claim_lifecycle_history(claim_id))
        _ = engine.compute_effective_confidence(claim_id)
        hist_after = list(engine.claim_lifecycle_history(claim_id))
        assert hist_before == hist_after


# ---- 7. Snapshot (Sub-decision BR) ----------------------------------------


class TestRuleStatsContinuousSnapshot:
    """§38.15 invariants 26~29 — schema bump 없음, round-trip."""

    def test_schema_version_remains_two(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        assert engine.to_snapshot()["schema_version"] == 2

    def test_snapshot_keys_unchanged(self) -> None:
        """PR26-R 후 snapshot 키 집합 PR21-L+PR25-T 와 동일."""
        engine = Engine()
        snap = engine.to_snapshot()
        expected_keys = {
            "schema_version", "next_id", "lifecycle_seq",
            "entities", "observations", "claims", "evidences", "relations",
            "gaps", "rule_definitions", "rule_stats",
            "gap_dedup_index", "claim_gap_refs", "gap_resolutions",
            "contradictions", "resolved_contradictions",
            "claim_lifecycle_events", "hint_evidence_types",
        }
        assert set(snap.keys()) == expected_keys

    def test_roundtrip_preserves_continuous_modifier_for_firing_zero(self) -> None:
        original = Engine()
        _register_rule(original, rule_id=1, rule_version=1)
        _set_firing_count(original, count=0)
        _, claim_id = _claim_with_rule(
            original, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        before = original.compute_effective_confidence(claim_id).value
        snap = original.to_snapshot()
        restored = Engine.from_snapshot(snap)
        after = restored.compute_effective_confidence(claim_id).value
        assert before == pytest.approx(after)
        assert after == pytest.approx(0.8)

    def test_rule_stats_dataclass_fields_unchanged(self) -> None:
        """PR26-R 은 RuleStats 구조 변경 0."""
        from dataclasses import fields

        names = {f.name for f in fields(types_module.RuleStats)}
        expected = {
            "rule_id", "rule_version", "firing_count",
            "confirmed_true_count", "confirmed_false_count",
            "observed_precision", "false_positive_rate",
        }
        assert names == expected


# ---- 8. Private constants (Sub-decision BS) -------------------------------


class TestRuleStatsContinuousPrivateConstants:
    """§38.15 invariants 30~34 — 신규 2 상수 + 구 2 상수 제거."""

    # invariant 30 ★ — 신규 weight 상수
    def test_maturity_penalty_weight_constant_is_point_two(self) -> None:
        val = getattr(engine_module, "_RULE_STATS_MATURITY_PENALTY_WEIGHT", None)
        assert val == pytest.approx(0.2)

    # invariant 31 ★ — 신규 saturation 상수
    def test_maturity_saturation_count_constant_is_two(self) -> None:
        val = getattr(engine_module, "_RULE_STATS_MATURITY_SATURATION_COUNT", None)
        assert val == 2

    # invariant 32 — 신규 상수 미노출 (private)
    def test_maturity_constants_not_exposed_publicly(self) -> None:
        names = [
            "_RULE_STATS_MATURITY_PENALTY_WEIGHT",
            "_RULE_STATS_MATURITY_SATURATION_COUNT",
            "RULE_STATS_MATURITY_PENALTY_WEIGHT",
            "RULE_STATS_MATURITY_SATURATION_COUNT",
        ]
        for n in names:
            assert not hasattr(ragcore, n)
            assert not hasattr(types_module, n)

    # invariant 33 ★ — 구 _RULE_STATS_PENALTY_MODIFIER 제거됨
    def test_old_rule_stats_penalty_modifier_removed(self) -> None:
        assert not hasattr(engine_module, "_RULE_STATS_PENALTY_MODIFIER")

    # invariant 34 ★ — 구 _RULE_STATS_MIN_FIRING_COUNT 제거됨
    def test_old_rule_stats_min_firing_count_removed(self) -> None:
        assert not hasattr(engine_module, "_RULE_STATS_MIN_FIRING_COUNT")


# ---- 9. Public namespace + RuleStats dataclass ----------------------------


class TestRuleStatsContinuousPublicNamespace:
    """§38.15 invariants 35~39 — Sub-decision D 보존, update_rule_stats 동작 보존."""

    # invariant 35 — types.py 변경 없음 (RuleStats / RuleDefinition 그대로)
    def test_types_module_rule_stats_dataclass_unchanged(self) -> None:
        from dataclasses import fields

        rs_names = {f.name for f in fields(types_module.RuleStats)}
        rd_names = {f.name for f in fields(types_module.RuleDefinition)}
        assert "firing_count" in rs_names
        assert "id" in rd_names
        assert "prior_confidence" in rd_names

    # invariant 36 — __init__.py 에 PR26-R 신규 export 추가 없음
    def test_no_new_public_export_for_rule_stats_maturity(self) -> None:
        all_attr = getattr(ragcore, "__all__", None)
        if all_attr is not None:
            forbidden_prefixes = (
                "_RULE_STATS_MATURITY",
                "RULE_STATS_MATURITY",
                "RULE_STATS_PENALTY",
            )
            for name in all_attr:
                assert not name.startswith(forbidden_prefixes), (
                    f"PR26-R 신규 상수가 __all__ 에 노출됨: {name}"
                )

    # invariant 37 — rule_output.py 변경 없음
    def test_rule_output_unchanged_no_quality_status(self) -> None:
        from ragcore import rule_output
        allowed = getattr(rule_output, "_ALLOWED_CLAIM_STATUSES", None)
        if allowed is not None:
            assert "rule_quality" not in allowed
            assert "matured" not in allowed

    # invariant 38 — public namespace 신규 export 0
    def test_public_namespace_no_new_export_for_pr26r(self) -> None:
        # PR26-R 후 ragcore 에 신규 public symbol 추가 없음
        new_candidates = [
            "_RULE_STATS_MATURITY_PENALTY_WEIGHT",
            "_RULE_STATS_MATURITY_SATURATION_COUNT",
            "RuleStatsMaturityModifier",
            "rule_stats_continuous_modifier",
        ]
        for name in new_candidates:
            assert not hasattr(ragcore, name)

    # invariant 39 — update_rule_stats 외부 동작 변경 없음
    def test_update_rule_stats_external_behavior_unchanged(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        # firing_delta accumulates as before
        engine.update_rule_stats(rule_id=1, rule_version=1, firing_delta=3)
        engine.update_rule_stats(rule_id=1, rule_version=1, firing_delta=2)
        assert engine._rule_stats[(1, 1)].firing_count == 5


# ---- 10. Regression boundaries --------------------------------------------


class TestRuleStatsContinuousRegressionBoundaries:
    """§38.15 invariants 40~48 — PR1~PR25-T 보존."""

    def test_pr11c_freshness_modifier_preserved(self) -> None:
        engine = Engine()
        _, claim_id = _claim_with_rule(
            engine, rule_id=42, rule_version=1, base_confidence=1.0,
        )
        # rule_stats lookup miss → 1.0
        ev = _evidence(engine, claim_id, evidence_type=99, strength=0.8)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # freshness 0.6, rule_stats 1.0 (miss) → 0.6
        assert result.value == pytest.approx(0.6)

    def test_pr23m_gap_tiering_preserved(self) -> None:
        engine = Engine()
        _, claim_id = _claim_with_rule(
            engine, rule_id=42, rule_version=1, base_confidence=1.0,
        )
        _unresolved_gap(engine, claim_id, required_evidence_type=99)
        _unresolved_gap(engine, claim_id, required_evidence_type=100)
        result = engine.compute_effective_confidence(claim_id)
        # gap 2 unresolved → tier 0.8, rule_stats 1.0 (miss) → 0.8
        assert result.value == pytest.approx(0.8)

    def test_pr24n_count_continuous_preserved(self) -> None:
        engine = Engine()
        _, claim_id = _claim_with_rule(
            engine, rule_id=42, rule_version=1, base_confidence=1.0,
        )
        _active_contradictions(engine, claim_id, (0.4, 0.4))
        result = engine.compute_effective_confidence(claim_id)
        # freshness 0.8 × count 0.9, rule_stats 1.0 (miss) → 0.72
        assert result.value == pytest.approx(0.72)

    def test_pr21l_evidence_type_modifier_preserved(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([42])
        _, claim_id = _claim_with_rule(
            engine, rule_id=99, rule_version=1, base_confidence=1.0,
        )
        _evidence(engine, claim_id, evidence_type=42, strength=0.5)
        result = engine.compute_effective_confidence(claim_id)
        # evidence_type 0.9, rule_stats 1.0 (miss) → 0.9
        assert result.value == pytest.approx(0.9)

    def test_pr25t_deregistration_api_preserved(self) -> None:
        engine = Engine()
        engine.register_hint_evidence_types([42])
        engine.unregister_hint_evidence_types([42])
        assert engine.to_snapshot()["hint_evidence_types"] == []
        engine.clear_hint_evidence_types()
        assert engine.to_snapshot()["hint_evidence_types"] == []

    def test_pr10a_refute_disputed_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _claim_with_rule(
            engine, rule_id=99, rule_version=1, base_confidence=1.0,
        )
        ev = _evidence(engine, claim_id, evidence_type=99, strength=0.9)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        assert engine.dispute_claim_if_ready(claim_id) is True
        assert engine.refute_disputed_claim_if_ready(claim_id) is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    def test_pr9a_active_contradictions_asc_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _claim_with_rule(
            engine, rule_id=99, rule_version=1, base_confidence=1.0,
        )
        ev1, ev2 = _active_contradictions(engine, claim_id, (0.4, 0.8))
        assert engine.active_contradictions_for_claim(claim_id) == (ev1, ev2)

    def test_pr17_round_trip_identity_with_rule_stats(self) -> None:
        original = Engine()
        _register_rule(original, rule_id=1, rule_version=1)
        _set_firing_count(original, count=1)
        _, claim_id = _claim_with_rule(
            original, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        snap1 = original.to_snapshot()
        restored = Engine.from_snapshot(snap1)
        snap2 = restored.to_snapshot()
        assert snap1 == snap2

    def test_pr18k_migration_framework_unchanged(self) -> None:
        # v1 snapshot 가 v2 로 migrate 되는 기존 동작 보존 (snapshot schema 변경 없음)
        v2_snap = Engine().to_snapshot()
        v1_snap = {k: v for k, v in v2_snap.items() if k != "hint_evidence_types"}
        v1_snap["schema_version"] = 1
        restored = Engine.from_snapshot(v1_snap)
        assert restored.to_snapshot()["schema_version"] == 2
