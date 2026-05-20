"""Tests for PR20-F — Effective confidence rule_stats modifier (MVP, weak maturity).

Invariants of ``compute_effective_confidence`` 의 6-modifier composition:
    effective = base × status × freshness × gap × count × rule_stats

**87차 (test-first) 상태**: PR19-E 의 5-modifier (base × status × freshness × gap × count)
까지만. rule_stats_modifier 미적용. fail pattern mixed (PR12-D 71차 / PR19-E 83차 동일):

§32.12 의 24 invariant 매핑:
1.  created_by_rule == 0 sentinel → modifier 1.0                     [이미 pass]
2.  created_by_rule_version 있어도 created_by_rule == 0 → 1.0        [이미 pass]
3.  (rule_id, version) lookup miss → modifier 1.0                    [이미 pass]
4.  rule_id 같고 version 다르면 lookup miss → 1.0                    [이미 pass]
5.  firing_count == 0 → 0.9 ★                                        [의도 fail]
6.  firing_count == 1 → 0.9 ★                                        [의도 fail]
7.  firing_count == 2 → 1.0                                          [이미 pass]
8.  firing_count == 10 → 1.0 (boost 없음)                            [이미 pass]
9.  firing_count == 1_000_000 → 1.0 (여전히 boost 없음)              [이미 pass]
10. refuted + firing_count == 1 → 0.0 (status dominate)              [이미 pass]
11. candidate + firing_count == 1 → base × 0.9 ★                     [의도 fail]
12. confirmed + firing_count == 1 → base × 0.9 ★                     [의도 fail]
13. disputed + firing_count == 1 → base × 0.5 × 0.9 ★                [의도 fail]
14. freshness + firing_count == 1 → freshness × 0.9 ★                [의도 fail]
15. unresolved gap + firing_count == 1 → gap × 0.9 ★                 [의도 fail]
16. active count 2 + firing_count == 1 → count × 0.9 ★               [의도 fail]
17. 6-modifier full composition (disputed + freshness + gap + count + fire=1) ★ [의도 fail]
18. compute 호출 전후 to_snapshot() 동일 (read-only)                 [이미 pass]
19. _rule_stats 내용 mutate 없음                                     [이미 pass]
20. _lifecycle_seq 변경 없음                                          [이미 pass]
21. claim_lifecycle_history 변경 없음                                 [이미 pass]
22. PR11-C freshness modifier 의미 변경 없음 (lookup miss claim 기준) [이미 pass]
23. PR12-D gap modifier 의미 변경 없음 (lookup miss claim 기준)       [이미 pass]
24. PR19-E count modifier 의미 변경 없음 (lookup miss claim 기준)     [이미 pass]
"""

from __future__ import annotations

from dataclasses import replace

import pytest

import ragcore
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
    maturity: int = 0,
    prior_confidence: float = 0.5,
) -> None:
    """Register a rule (initial firing_count = 0)."""
    engine.register_rule(
        RuleDefinition(
            id=rule_id,
            version=rule_version,
            maturity=maturity,
            prior_confidence=ScoreValue(prior_confidence),
        )
    )


def _bump_firing(
    engine: Engine,
    *,
    rule_id: int = 1,
    rule_version: int = 1,
    delta: int,
) -> None:
    """Increment RuleStats.firing_count by `delta`."""
    engine.update_rule_stats(
        rule_id=rule_id, rule_version=rule_version, firing_delta=delta,
    )


def _claim_with_rule(
    engine: Engine,
    *,
    rule_id: int = 1,
    rule_version: int = 1,
    base_confidence: float = 1.0,
) -> tuple[int, int]:
    """Create entity + claim linked to (rule_id, rule_version)."""
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=rule_id,
        rule_version=rule_version,
        reason_code=0,
        base_confidence=base_confidence,
    )
    return entity_id, claim_id


def _claim_without_rule(
    engine: Engine, *, base_confidence: float = 1.0,
) -> tuple[int, int]:
    """Create entity + claim with created_by_rule == 0 sentinel (no rule source)."""
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=0,
        rule_version=0,
        reason_code=0,
        base_confidence=base_confidence,
    )
    return entity_id, claim_id


def _evidence(
    engine: Engine, claim_id: int, *, strength: float = 0.5,
) -> int:
    return engine.add_evidence(
        claim_id=claim_id, raw_ref_id=0, evidence_type=42, strength=strength,
    )


def _unresolved_gap(engine: Engine, claim_id: int) -> int:
    return engine.add_gap(
        claim_id=claim_id, gap_type=1, required_evidence_type=99,
        severity=0.5, rule_id=1,
    )


# ---- 1. Sentinel + lookup miss (Sub-decision Y) ----------------------------


class TestRuleStatsModifierSentinelAndLookup:
    """§32.12 invariants 1~4 — Sub-decision Y (no rule source / miss → 1.0)."""

    # invariant 1
    def test_sentinel_rule_id_zero_returns_one(self) -> None:
        engine = Engine()
        _, claim_id = _claim_without_rule(engine, base_confidence=0.7)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 2
    def test_sentinel_rule_id_zero_with_nonzero_version_still_one(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=0, rule_version=5,  # sentinel rule_id, nonzero version
            reason_code=0, base_confidence=0.8,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.8)

    # invariant 3
    def test_unregistered_rule_pair_is_lookup_miss(self) -> None:
        engine = Engine()
        # Claim references rule (99, 1) but no register_rule call → miss.
        _, claim_id = _claim_with_rule(
            engine, rule_id=99, rule_version=1, base_confidence=0.6,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.6)

    # invariant 4
    def test_same_rule_id_different_version_is_lookup_miss(self) -> None:
        engine = Engine()
        # Register rule (1, 1) and bump firing_count → ensure penalty would
        # otherwise apply for (1, 1). Then create claim referencing (1, 2)
        # which is NOT registered → miss → 1.0 (no penalty).
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)  # firing=1 → would be 0.9
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=2, base_confidence=0.5,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.5)


# ---- 2. Threshold (Sub-decision W/X) ---------------------------------------


class TestRuleStatsModifierThreshold:
    """§32.12 invariants 5~9 — Sub-decision W (threshold=2) + X (no boost)."""

    # invariant 5 ★ — 의도 fail (현재 코드 1.0, 88차 후 0.9)
    def test_firing_count_zero_applies_penalty(self) -> None:
        """register_rule 직후 firing_count = 0 → modifier = 0.9."""
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        # base 1.0 × all_other 1.0 × rule_stats 0.9 = 0.9
        assert result.value == pytest.approx(0.9)

    # invariant 6 ★
    def test_firing_count_one_applies_penalty(self) -> None:
        """firing_count = 1 → modifier = 0.9."""
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.9)

    # invariant 7 — 이미 pass (threshold 도달)
    def test_firing_count_two_no_penalty(self) -> None:
        """firing_count = 2 → modifier = 1.0."""
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=2)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)

    # invariant 8 — Sub-decision X (no boost)
    def test_firing_count_ten_no_boost(self) -> None:
        """firing_count = 10 → modifier = 1.0 (boost 없음)."""
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=10)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)

    # invariant 9 — Sub-decision X (large firing_count still no boost)
    def test_firing_count_million_no_boost(self) -> None:
        """firing_count 매우 크게 → 여전히 modifier = 1.0."""
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1_000_000)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)


# ---- 3. Composition with status (PR11-D) -----------------------------------


class TestRuleStatsCompositionWithStatus:
    """§32.12 invariants 10~13 — status × rule_stats composition."""

    # invariant 10 — refuted dominate, rule_stats 무관
    def test_refuted_with_firing_one_is_zero(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.0)

    # invariant 11 ★
    def test_candidate_with_firing_one_applies_rule_stats_only(self) -> None:
        """candidate + firing 1 → base × 1.0 × 1.0 × 1.0 × 1.0 × 0.9 = 0.9."""
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.9)

    # invariant 12 ★
    def test_confirmed_with_firing_one_applies_rule_stats_only(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # confirmed = 1.0, rule_stats = 0.9 → 0.9
        assert result.value == pytest.approx(0.9)

    # invariant 13 ★
    def test_disputed_with_firing_one_combines_status_and_rule_stats(self) -> None:
        """disputed + firing 1 → base × 0.5 × 0.9 = 0.45."""
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # 1.0 × 0.5 × 1.0 × 1.0 × 1.0 × 0.9 = 0.45
        assert result.value == pytest.approx(0.45)


# ---- 4. Composition with other PR modifiers --------------------------------


class TestRuleStatsCompositionWithExistingModifiers:
    """§32.12 invariants 14~17 — freshness/gap/count × rule_stats composition."""

    # invariant 14 ★ — freshness × rule_stats
    def test_freshness_and_firing_one(self) -> None:
        """active 1 + strength 0.8 + firing 1 → 1.0 × 0.6 × 1.0 × 1.0 × 0.9 = 0.54."""
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        ev = _evidence(engine, claim_id, strength=0.8)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # freshness = 1.0 - 0.8 × 0.5 = 0.6; rule_stats = 0.9
        assert result.value == pytest.approx(0.54)

    # invariant 15 ★ — gap × rule_stats
    def test_unresolved_gap_and_firing_one(self) -> None:
        """unresolved gap 1 개 + firing 1 → 1.0 × 1.0 × 1.0 × 0.9 × 1.0 × 0.9 = 0.81.

        PR23-M §35.5 (AP): 1 unresolved → tier 1 → 0.9 (PR12-D binary 0.8 정제).
        의미 (gap × rule_stats 결합) 보존, gap 강도만 갱신.
        """
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        _unresolved_gap(engine, claim_id)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.81)

    # invariant 16 ★ — count × rule_stats (independence)
    def test_active_two_and_firing_one(self) -> None:
        """active 2 (strength 0) + firing 1 → 1.0 × 1.0 × 1.0 × 1.0 × 0.8 × 0.9 = 0.72."""
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        ev1 = _evidence(engine, claim_id, strength=0.0)
        ev2 = _evidence(engine, claim_id, strength=0.0)
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)
        result = engine.compute_effective_confidence(claim_id)
        # count = 0.8, rule_stats = 0.9 → 0.72
        assert result.value == pytest.approx(0.72)

    # invariant 17 ★ — full 6-modifier composition
    def test_full_six_modifier_composition(self) -> None:
        """disputed + active 2 (most recent strength 0.8) + unresolved gap 1 개 + firing 1.

        PR23-M §35.5 (AP): 1 unresolved → tier 1 → 0.9 (PR12-D binary 0.8 정제).
        의미 (6-modifier 결합) 보존, gap 강도만 갱신.

        base × status × freshness × gap × count × rule_stats
        = 1.0 × 0.5 × (1.0 - 0.8 × 0.5) × 0.9 × 0.8 × 0.9
        = 1.0 × 0.5 × 0.6 × 0.9 × 0.8 × 0.9
        = 0.1944
        """
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        ev1 = _evidence(engine, claim_id, strength=0.3)
        ev2 = _evidence(engine, claim_id, strength=0.8)
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)
        _unresolved_gap(engine, claim_id)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.1944)


# ---- 5. No state mutation (Sub-decision Z) ---------------------------------


class TestRuleStatsNoStateMutation:
    """§32.12 invariants 18~21 — read-only compute."""

    # invariant 18 — to_snapshot identity before/after compute
    def test_snapshot_identical_before_and_after_compute(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=0.8,
        )
        snap_before = engine.to_snapshot()
        _ = engine.compute_effective_confidence(claim_id)
        snap_after = engine.to_snapshot()
        assert snap_before == snap_after

    # invariant 19 — _rule_stats unchanged
    def test_rule_stats_dict_unchanged_after_compute(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _bump_firing(engine, rule_id=1, rule_version=1, delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=0.7,
        )
        before = dict(engine._rule_stats)
        _ = engine.compute_effective_confidence(claim_id)
        after = dict(engine._rule_stats)
        assert before == after

    # invariant 20 — _lifecycle_seq unchanged
    def test_lifecycle_seq_unchanged_after_compute(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=1, rule_version=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=0.7,
        )
        seq_before = engine._lifecycle_seq
        _ = engine.compute_effective_confidence(claim_id)
        assert engine._lifecycle_seq == seq_before

    # invariant 21 — lifecycle history unchanged
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


# ---- 6. Regression boundaries (PR11-C / PR12-D / PR19-E 무변화) -----------


class TestRuleStatsRegressionBoundaries:
    """§32.12 invariants 22~24 — 기존 modifier 의미 변경 없음.

    각 테스트는 **rule_stats lookup miss** 또는 **firing_count >= 2** Claim 으로
    만들어 rule_stats_modifier = 1.0 으로 고정. 이렇게 해야 기존 modifier
    의미만 검증된다.
    """

    # invariant 22 — PR11-C freshness modifier 무변화
    def test_pr11c_freshness_modifier_meaning_preserved(self) -> None:
        """active 1, strength 0.8, confirmed, rule_stats=1.0 → base × 0.6 (PR11-C 그대로)."""
        engine = Engine()
        # No register_rule → lookup miss → rule_stats = 1.0
        _, claim_id = _claim_with_rule(
            engine, rule_id=42, rule_version=1, base_confidence=1.0,
        )
        ev = _evidence(engine, claim_id, strength=0.8)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # PR11-C: 1.0 × 1.0 × 0.6 × 1.0 × 1.0 × 1.0 (lookup miss) = 0.6
        assert result.value == pytest.approx(0.6)

    # invariant 23 — PR12-D gap modifier 의미 보존 (PR23-M tier 강도 갱신)
    def test_pr12d_gap_modifier_meaning_preserved(self) -> None:
        """unresolved gap 1 개, candidate, rule_stats=1.0 → base × 0.9 (PR12-D + PR23-M).

        PR23-M §35.5 (AP): 1 unresolved → tier 1 → 0.9. PR12-D 의 "unresolved →
        attenuation" 의미 보존, 강도만 binary 0.8 → tier 0.9 로 정제.
        """
        engine = Engine()
        _, claim_id = _claim_with_rule(
            engine, rule_id=42, rule_version=1, base_confidence=1.0,
        )
        _unresolved_gap(engine, claim_id)
        result = engine.compute_effective_confidence(claim_id)
        # PR12-D + PR23-M: 1.0 × 1.0 × 1.0 × 0.9 (1 unresolved tier) × 1.0 × 1.0 = 0.9
        assert result.value == pytest.approx(0.9)

    # invariant 24 — PR19-E count modifier 무변화
    def test_pr19e_count_modifier_meaning_preserved(self) -> None:
        """active 2 (strength 0), candidate, rule_stats=1.0 → base × 0.8 (PR19-E 그대로)."""
        engine = Engine()
        _, claim_id = _claim_with_rule(
            engine, rule_id=42, rule_version=1, base_confidence=1.0,
        )
        ev1 = _evidence(engine, claim_id, strength=0.0)
        ev2 = _evidence(engine, claim_id, strength=0.0)
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)
        result = engine.compute_effective_confidence(claim_id)
        # PR19-E: 1.0 × 1.0 × 1.0 × 1.0 × 0.8 × 1.0 = 0.8
        assert result.value == pytest.approx(0.8)
