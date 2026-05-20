"""Tests for PR23-M — Gap modifier severity tiering (MVP, count-tier).

Invariants of ``compute_effective_confidence`` 의 gap modifier 정제:
    binary 0.8 → count tier (1.0 / 0.9 / 0.8 / 0.7)

**99차 (test-first) 상태**: PR12-D 의 binary `_GAP_PENALTY_MODIFIER = 0.8`
그대로. 따라서 1 unresolved → 0.9 / 3+ unresolved → 0.7 / 4 신규 상수
존재 케이스들이 fail 해야 정상. fail pattern mixed.

§35.13 의 48 invariants 를 7 클래스로 분해. Sub-decision AO~AU 매핑은 각
클래스 docstring 참조.

핵심:
    PR23-M 는 modifier 자리 / 결합 방식 / state shape / snapshot schema 모두 안 바꾼다.
    오직 `gap` 항의 내부 계산식만 binary → count tier 로 정제한다.
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


def _claim(engine: Engine, *, base_confidence: float = 1.0) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id, claim_type=1,
        rule_id=0, rule_version=0, reason_code=0,
        base_confidence=base_confidence,
    )
    return entity_id, claim_id


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


def _add_unresolved_gap(
    engine: Engine, claim_id: int, *, required_evidence_type: int,
) -> int:
    """Gap dedup key 는 (subject, rule, gap_type, required_evidence_type).
    여러 unresolved gap 을 만들려면 required_evidence_type 을 서로 다르게 줘야 한다."""
    return engine.add_gap(
        claim_id=claim_id, gap_type=1,
        required_evidence_type=required_evidence_type,
        severity=0.5, rule_id=1,
    )


def _add_resolved_gap(
    engine: Engine, claim_id: int, *, required_evidence_type: int,
) -> tuple[int, int]:
    """Gap 추가 + 매칭 evidence 등록 → resolved 상태."""
    gap_id = engine.add_gap(
        claim_id=claim_id, gap_type=1,
        required_evidence_type=required_evidence_type,
        severity=0.5, rule_id=1,
    )
    ev_id = engine.add_evidence(
        claim_id=claim_id, raw_ref_id=0,
        evidence_type=required_evidence_type, strength=0.5,
    )
    engine.resolve_gaps_for_evidence(ev_id)
    return gap_id, ev_id


# ---- 1. Tier mapping (Sub-decision AP) -------------------------------------


class TestGapSeverityTierMapping:
    """§35.13 invariants 1~7 — tier mapping 0/1/2/3/3+ → 1.0/0.9/0.8/0.7/0.7."""

    # invariant 1
    def test_zero_unresolved_gap_modifier_is_one(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        # No gaps at all
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)

    # invariant 2 — gap 항목 0 개 (gap 자체가 없음)
    def test_no_gaps_modifier_is_one(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=0.7)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 3 ★ — 1 unresolved → 0.9 (현재 PR12-D 는 0.8)
    def test_one_unresolved_gap_modifier_is_zero_point_nine(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=101)
        result = engine.compute_effective_confidence(claim_id)
        # PR23-M: 1 unresolved → tier 1 → 0.9
        assert result.value == pytest.approx(0.9)

    # invariant 4 — 2 unresolved → 0.8 (PR12-D binary 와 동일 지점)
    def test_two_unresolved_gap_modifier_is_zero_point_eight(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=101)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=102)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.8)

    # invariant 5 ★ — 3 unresolved → 0.7 (현재 PR12-D 는 0.8)
    def test_three_unresolved_gap_modifier_is_zero_point_seven(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=101)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=102)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=103)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 6 ★ — 10 unresolved → 0.7 (3+ tier 통합)
    def test_ten_unresolved_stays_zero_point_seven(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        for et in range(101, 111):
            _add_unresolved_gap(engine, claim_id, required_evidence_type=et)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 7 ★ — 100 unresolved → 0.7 (open-ended)
    def test_hundred_unresolved_stays_zero_point_seven(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        for et in range(1000, 1100):
            _add_unresolved_gap(engine, claim_id, required_evidence_type=et)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)


# ---- 2. Resolution semantics (PR12-D 정신 보존) ----------------------------


class TestGapSeverityResolutionSemantics:
    """§35.13 invariants 8~11 — resolved 는 count 에서 제외."""

    # invariant 8 — 3 gaps 모두 resolved → 1.0
    def test_all_resolved_gaps_modifier_is_one(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _add_resolved_gap(engine, claim_id, required_evidence_type=201)
        _add_resolved_gap(engine, claim_id, required_evidence_type=202)
        _add_resolved_gap(engine, claim_id, required_evidence_type=203)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(1.0)

    # invariant 9 ★ — 3 gaps, 2 resolved + 1 unresolved → 0.9
    def test_two_resolved_one_unresolved_is_zero_point_nine(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _add_resolved_gap(engine, claim_id, required_evidence_type=201)
        _add_resolved_gap(engine, claim_id, required_evidence_type=202)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=301)
        result = engine.compute_effective_confidence(claim_id)
        # PR23-M: 1 unresolved → tier 1 → 0.9
        assert result.value == pytest.approx(0.9)

    # invariant 10 — 3 gaps, 1 resolved + 2 unresolved → 0.8
    def test_one_resolved_two_unresolved_is_zero_point_eight(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _add_resolved_gap(engine, claim_id, required_evidence_type=201)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=301)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=302)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.8)

    # invariant 11 — gap resolution 후 modifier 복구 (1 unresolved → resolve → 1.0)
    def test_gap_modifier_restores_after_resolution(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        gap_id = _add_unresolved_gap(engine, claim_id, required_evidence_type=301)
        before = engine.compute_effective_confidence(claim_id).value
        # PR23-M: 1 unresolved → 0.9
        assert before == pytest.approx(0.9)

        # Resolve via matching evidence
        ev_id = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=301, strength=0.5,
        )
        engine.resolve_gaps_for_evidence(ev_id)
        after = engine.compute_effective_confidence(claim_id).value
        # All resolved → 1.0
        assert after == pytest.approx(1.0)


# ---- 3. Monotonicity and boundary (Sub-decision AP + AQ) -------------------


class TestGapSeverityMonotonicityAndBoundary:
    """§35.13 invariants 12~15 — monotonic / 0.7 floor / no 0.0 / no boost."""

    # invariant 12 — monotonic non-increasing
    def test_tier_monotonic_non_increasing(self) -> None:
        """count 0 → 1 → 2 → 3 → modifier 비-증가 (1.0 → 0.9 → 0.8 → 0.7 → 0.7)."""
        results: list[float] = []
        for n in [0, 1, 2, 3, 5]:
            engine = Engine()
            _, claim_id = _claim(engine, base_confidence=1.0)
            for i in range(n):
                _add_unresolved_gap(
                    engine, claim_id, required_evidence_type=400 + i,
                )
            r = engine.compute_effective_confidence(claim_id).value
            results.append(r)
        # Each successive value <= previous
        for prev, curr in zip(results, results[1:]):
            assert curr <= prev + 1e-9, (
                f"non-monotonic: {results}"
            )

    # invariant 13 ★ — 0.7 hard floor
    def test_zero_point_seven_is_hard_floor(self) -> None:
        """20 unresolved 도 0.7 미만 안 됨."""
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        for et in range(500, 520):
            _add_unresolved_gap(engine, claim_id, required_evidence_type=et)
        result = engine.compute_effective_confidence(claim_id).value
        assert result >= 0.7 - 1e-9
        assert result == pytest.approx(0.7)

    # invariant 14 — gap modifier 절대 0.0 안 됨 (Sub-decision AQ)
    def test_gap_modifier_never_zero(self) -> None:
        """unresolved gap 만 있을 때 effective = 0.0 발생 금지 (refute 영역과 분리).

        confirmed status + 어떤 gap count 도 0.0 이 되면 안 된다.
        """
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        for et in range(600, 610):
            _add_unresolved_gap(engine, claim_id, required_evidence_type=et)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id).value
        assert result > 0.0

    # invariant 15 — gap modifier 절대 1.0 초과 안 됨 (Sub-decision AR boost 금지)
    def test_gap_modifier_never_exceeds_one(self) -> None:
        """0 gap 일 때 1.0 보다 큰 modifier 가 적용되면 effective > base.
        PR11-D Sub-decision N (effective ≤ base) 영구 보존."""
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        # No gap → gap_modifier 1.0
        result = engine.compute_effective_confidence(claim_id).value
        assert result <= 1.0 + 1e-9


# ---- 4. Composition (status × freshness × gap × count × rule_stats × evidence_type)


class TestGapSeverityComposition:
    """§35.13 invariants 16~21 — 7-modifier composition with tiered gap."""

    # invariant 16 — refuted dominate, gap tier 무관
    def test_refuted_with_many_unresolved_gaps_is_zero(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        for et in range(700, 710):
            _add_unresolved_gap(engine, claim_id, required_evidence_type=et)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.compute_effective_confidence(claim_id).value
        assert result == pytest.approx(0.0)

    # invariant 17 ★ — disputed + 1 unresolved → base × 0.5 × 0.9 = 0.45
    def test_disputed_with_one_unresolved_gap(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=801)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id).value
        # base 1.0 × status 0.5 × gap 0.9 = 0.45
        assert result == pytest.approx(0.45)

    # invariant 18 — disputed + 2 unresolved → base × 0.5 × 0.8 = 0.40
    def test_disputed_with_two_unresolved_gap(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=801)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=802)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id).value
        assert result == pytest.approx(0.40)

    # invariant 19 ★ — confirmed + freshness 0.8 + 1 unresolved → base × 0.6 × 0.9 = 0.54
    def test_confirmed_with_freshness_and_one_unresolved_gap(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        # active contradiction with strength 0.8 → freshness 0.6
        ev = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=99, strength=0.8,
        )
        engine.register_contradiction(claim_id, ev)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=801)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id).value
        # 1.0 × 1.0 × 0.6 × 0.9 × 1.0 × 1.0 × 1.0 = 0.54
        assert result == pytest.approx(0.54)

    # invariant 20 — candidate + 2 unresolved + active 2 → base × 0.8 × 0.8 = 0.64
    def test_candidate_with_two_gaps_and_count_two(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=801)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=802)
        c1 = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=99, strength=0.0,
        )
        c2 = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=99, strength=0.0,
        )
        engine.register_contradiction(claim_id, c1)
        engine.register_contradiction(claim_id, c2)
        result = engine.compute_effective_confidence(claim_id).value
        # 1.0 × 1.0 (cand) × 1.0 (freshness, strength=0) × 0.8 (gap, 2 unresolved)
        #   × 0.8 (count, active=2) × 1.0 × 1.0 = 0.64
        assert result == pytest.approx(0.64)

    # invariant 21 ★ — full 7-modifier composition
    def test_full_seven_modifier_composition_with_three_gaps(self) -> None:
        """disputed + active 2 (most strength 0.8) + 3 unresolved gaps
        + firing 1 + hint-only direct evidence.

        effective = base × 0.5 × 0.6 × 0.7 × 0.8 × 0.9 × 0.9
                  = base × 0.13608
        """
        engine = Engine()
        # rule_stats with firing_count = 1 → rule_stats modifier 0.9
        engine.register_rule(
            RuleDefinition(
                id=1, version=1, maturity=0,
                prior_confidence=ScoreValue(0.5),
            )
        )
        engine.update_rule_stats(rule_id=1, rule_version=1, firing_delta=1)
        # hint registration → caller-defined
        engine.register_hint_evidence_types([42])

        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        # direct supporting evidence: type=42 (hint) — counts for evidence_type 0.9
        engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=42, strength=0.5,
        )
        # active contradictions: type=99, strengths 0.3 and 0.8 (most recent 0.8 → freshness 0.6)
        c1 = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=99, strength=0.3,
        )
        c2 = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=99, strength=0.8,
        )
        engine.register_contradiction(claim_id, c1)
        engine.register_contradiction(claim_id, c2)
        # 3 unresolved gaps → tier 0.7
        _add_unresolved_gap(engine, claim_id, required_evidence_type=801)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=802)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=803)
        # disputed status → 0.5
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id).value
        # 1.0 × 0.5 × 0.6 × 0.7 × 0.8 × 0.9 × 0.9 = 0.13608
        assert result == pytest.approx(0.13608)


# ---- 5. Read-only (Sub-decision AQ) ----------------------------------------


class TestGapSeverityReadOnly:
    """§35.13 invariants 22~26 — compute is read-only."""

    # invariant 22
    def test_snapshot_identical_before_and_after_compute(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=0.7)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=901)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=902)
        snap_before = engine.to_snapshot()
        _ = engine.compute_effective_confidence(claim_id)
        snap_after = engine.to_snapshot()
        assert snap_before == snap_after

    # invariant 23
    def test_gaps_dict_unchanged_after_compute(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=0.7)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=901)
        before_gaps = dict(engine._gaps)
        before_res = dict(engine._gap_resolutions)
        _ = engine.compute_effective_confidence(claim_id)
        assert dict(engine._gaps) == before_gaps
        assert dict(engine._gap_resolutions) == before_res

    # invariant 24
    def test_lifecycle_seq_unchanged_after_compute(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=0.7)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=901)
        seq_before = engine._lifecycle_seq
        _ = engine.compute_effective_confidence(claim_id)
        assert engine._lifecycle_seq == seq_before

    # invariant 25
    def test_lifecycle_history_unchanged_after_compute(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=0.7)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=901)
        hist_before = list(engine.claim_lifecycle_history(claim_id))
        _ = engine.compute_effective_confidence(claim_id)
        hist_after = list(engine.claim_lifecycle_history(claim_id))
        assert hist_before == hist_after

    # invariant 26
    def test_contradictions_unchanged_after_compute(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=0.7)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=901)
        before = {k: set(v) for k, v in engine._contradictions.items()}
        _ = engine.compute_effective_confidence(claim_id)
        after = {k: set(v) for k, v in engine._contradictions.items()}
        assert before == after


# ---- 6. Snapshot (Sub-decision AU) -----------------------------------------


class TestGapSeveritySnapshot:
    """§35.13 invariants 27~30 — snapshot schema/serialization unchanged."""

    # invariant 27
    def test_schema_version_still_two(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=1001)
        snap = engine.to_snapshot()
        assert snap["schema_version"] == 2

    # invariant 28
    def test_snapshot_keys_unchanged(self) -> None:
        """PR23-M 후 snapshot 키 집합이 PR21-L/PR22-S 와 동일해야 한다."""
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

    # invariant 29
    def test_round_trip_preserves_tier_modifier(self) -> None:
        """3 unresolved gap 등록 → snapshot → restore → 같은 tier (0.7) 적용."""
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=1001)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=1002)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=1003)
        before = engine.compute_effective_confidence(claim_id).value
        snap = engine.to_snapshot()
        restored = Engine.from_snapshot(snap)
        after = restored.compute_effective_confidence(claim_id).value
        assert before == pytest.approx(after)
        assert after == pytest.approx(0.7)

    # invariant 30 — Gap dataclass 구조 변경 없음 (Sub-decision AO)
    def test_gap_dataclass_fields_unchanged(self) -> None:
        from dataclasses import fields
        from ragcore.types import Gap

        names = {f.name for f in fields(Gap)}
        expected = {
            "id", "claim_id", "type", "required_evidence_type",
            "severity", "created_by_rule",
        }
        assert names == expected


# ---- 7. Privacy + regression (Sub-decision AS + D + AF + PR1~PR22 정합) ----


class TestGapSeverityPrivacyAndRegression:
    """§35.13 invariants 31~48 — private tier constants + Sub-decision D 보존 + 기존 PR 회귀 보존."""

    # invariants 31~34 ★ — 4 신규 tier 상수 존재 (현재 None)
    def test_tier_zero_constant_is_one(self) -> None:
        val = getattr(engine_module, "_GAP_TIER_ZERO_UNRESOLVED_MODIFIER", None)
        assert val == 1.0

    def test_tier_one_constant_is_zero_point_nine(self) -> None:
        val = getattr(engine_module, "_GAP_TIER_ONE_UNRESOLVED_MODIFIER", None)
        assert val == 0.9

    def test_tier_two_constant_is_zero_point_eight(self) -> None:
        val = getattr(engine_module, "_GAP_TIER_TWO_UNRESOLVED_MODIFIER", None)
        assert val == 0.8

    def test_tier_three_or_more_constant_is_zero_point_seven(self) -> None:
        val = getattr(engine_module, "_GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER", None)
        assert val == 0.7

    # invariant 35 — 4 신규 상수 모두 public namespace 미노출
    def test_tier_constants_not_exposed_in_ragcore(self) -> None:
        names = [
            "_GAP_TIER_ZERO_UNRESOLVED_MODIFIER",
            "_GAP_TIER_ONE_UNRESOLVED_MODIFIER",
            "_GAP_TIER_TWO_UNRESOLVED_MODIFIER",
            "_GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER",
            # public 버전 도 미노출
            "GAP_TIER_ZERO_UNRESOLVED_MODIFIER",
            "GAP_TIER_ONE_UNRESOLVED_MODIFIER",
        ]
        for n in names:
            assert not hasattr(ragcore, n), f"ragcore should not expose {n}"
            assert not hasattr(types_module, n), (
                f"ragcore.types should not expose {n}"
            )

    # invariant 36 — 구 _GAP_PENALTY_MODIFIER 도 미노출 (제거되었거나, 부재 OK)
    def test_old_gap_penalty_modifier_not_exposed(self) -> None:
        assert not hasattr(ragcore, "_GAP_PENALTY_MODIFIER")
        assert not hasattr(ragcore, "GAP_PENALTY_MODIFIER")
        assert not hasattr(types_module, "_GAP_PENALTY_MODIFIER")

    # invariant 37 — types.py 변경 없음 (Gap 구조 동일)
    def test_types_module_has_no_new_gap_severity_enum(self) -> None:
        assert not hasattr(types_module, "GAP_SEVERITY_CRITICAL")
        assert not hasattr(types_module, "GAP_SEVERITY_MAJOR")
        assert not hasattr(types_module, "GAP_SEVERITY_MINOR")

    # invariant 38 — __init__.py 변경 없음 (신규 export 0)
    def test_no_new_public_export(self) -> None:
        all_attr = getattr(ragcore, "__all__", None)
        if all_attr is not None:
            for name in all_attr:
                # tier 관련 신규 public 노출 0
                assert "GAP_TIER" not in name
                assert "GAP_SEVERITY" not in name

    # invariant 39 — rule_output.py 변경 없음 (claim_status 허용값 변경 0)
    def test_rule_output_claim_status_unchanged(self) -> None:
        from ragcore import rule_output
        allowed = getattr(rule_output, "_ALLOWED_CLAIM_STATUSES", None)
        if allowed is not None:
            # disputed 미포함 보장 (Sub-decision D 영구) — superseded/retracted 도 없어야 함
            assert "superseded" not in allowed
            assert "retracted" not in allowed

    # invariants 41~44 — 다른 modifier 의미 보존 (gap 무관 케이스)
    def test_pr11c_freshness_modifier_preserved_no_gap(self) -> None:
        """active 1 (strength 0.8), confirmed, gap 0 → 1.0 × 0.6 × 1.0 = 0.6.
        PR23-M 후에도 PR11-C freshness modifier 의미 동일."""
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        ev = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=99, strength=0.8,
        )
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id).value
        assert result == pytest.approx(0.6)

    def test_pr19e_count_modifier_preserved_no_gap(self) -> None:
        """active 2 (strength 0), candidate, gap 0 → 1.0 × 0.8 × 1.0 = 0.8."""
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        c1 = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=99, strength=0.0,
        )
        c2 = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=99, strength=0.0,
        )
        engine.register_contradiction(claim_id, c1)
        engine.register_contradiction(claim_id, c2)
        result = engine.compute_effective_confidence(claim_id).value
        assert result == pytest.approx(0.8)

    def test_pr20f_rule_stats_modifier_preserved_no_gap(self) -> None:
        """firing 1, candidate, gap 0 → 1.0 × 0.9 × 1.0 = 0.9."""
        engine = Engine()
        engine.register_rule(
            RuleDefinition(
                id=1, version=1, maturity=0,
                prior_confidence=ScoreValue(0.5),
            )
        )
        engine.update_rule_stats(rule_id=1, rule_version=1, firing_delta=1)
        _, claim_id = _claim_with_rule(
            engine, rule_id=1, rule_version=1, base_confidence=1.0,
        )
        result = engine.compute_effective_confidence(claim_id).value
        assert result == pytest.approx(0.9)

    def test_pr21l_evidence_type_modifier_preserved_no_gap(self) -> None:
        """hint registered + direct evidence all hint + no gap → 1.0 × 0.9 × 1.0 = 0.9."""
        engine = Engine()
        engine.register_hint_evidence_types([42])
        _, claim_id = _claim(engine, base_confidence=1.0)
        engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=42, strength=0.5,
        )
        result = engine.compute_effective_confidence(claim_id).value
        assert result == pytest.approx(0.9)

    # invariant 45 — PR22-S strict validation 보존 (gap 작업과 무관)
    def test_pr22s_strict_validation_still_rejects_bool(self) -> None:
        engine = Engine()
        with pytest.raises(TypeError):
            engine.register_hint_evidence_types([True])

    # invariant 46 — PR10-A refute 동작 무변화 (smoke)
    def test_pr10a_refute_still_works(self) -> None:
        """refute API 존재 + Claim status 전이 동작."""
        # smoke — refute_claim 또는 동등 API 가 존재하면 호출 가능
        engine = Engine()
        # 단순 status 변경 가능 검증
        _, claim_id = _claim(engine, base_confidence=1.0)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.compute_effective_confidence(claim_id).value
        assert result == pytest.approx(0.0)

    # invariant 47 — PR9-A active_contradictions_for_claim 동작 무변화 (smoke)
    def test_pr9a_active_contradictions_still_returns_asc(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        ev1 = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=99, strength=0.0,
        )
        ev2 = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0,
            evidence_type=99, strength=0.0,
        )
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)
        active = engine.active_contradictions_for_claim(claim_id)
        assert tuple(active) == tuple(sorted(active))

    # invariant 48 — round-trip identity (PR17 정신 보존)
    def test_pr17_round_trip_identity_with_gaps(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=1101)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=1102)
        snap1 = engine.to_snapshot()
        restored = Engine.from_snapshot(snap1)
        snap2 = restored.to_snapshot()
        assert snap1 == snap2
