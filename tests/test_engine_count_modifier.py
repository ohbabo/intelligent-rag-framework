"""Tests for PR19-E — Effective confidence count modifier (MVP, binary supplemental).

Invariants of ``compute_effective_confidence`` 의 5-modifier composition:
    effective = base × status × freshness × gap × count

**83차 (test-first) 상태**: PR12-D 의 4-modifier (base × status × freshness × gap)
까지만. count_modifier 미적용. fail pattern mixed (PR12-D 71차 동일):

§31.12 의 21 invariant 매핑:
1.  unknown claim_id → KeyError                                  [이미 pass]
2.  active 0 + candidate → base                                  [이미 pass]
3.  active 0 + confirmed → base                                  [이미 pass]
4.  active 1 + candidate → freshness 만 적용 (count = 1.0)       [이미 pass]
5.  active 2 + candidate → count = 0.8 추가 ★                    [의도 fail]
6.  active 2 + confirmed + strength 0.8 → base × 0.48 ★          [의도 fail]
7.  active 10 + confirmed → count = 0.8 (N 무관) ★               [의도 fail]
8.  active 2 + refuted → 0.0                                     [이미 pass]
9.  5-modifier 결합 (disputed + active 2 + unresolved gap) ★      [의도 fail]
10. Resolved 제외 (3 중 2 resolved → active 1 → count 1.0)        [이미 pass]
11. PR11-C freshness_modifier 무변화                              [이미 pass]
12. PR12-D gap_modifier 무변화                                    [이미 pass]
13. PR10-A / PR11-B refute 무변화                                 [이미 pass]
14. PR9-A asc 무변화                                              [이미 pass]
15. PR11-D _STATUS_MODIFIER_* 값 무변화                           [이미 pass]
16. effective ≤ base (no boost)                                  [이미 pass]
17. compute is read-only                                          [이미 pass]
18. determinism                                                   [이미 pass]
19. PR17 round-trip identity 보존                                [이미 pass]
20. _COUNT_PENALTY_MODIFIER private                              [이미 pass]
21. 기존 652 회귀 없음 — 전체 통과로 입증
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
)


def _candidate_claim(engine: Engine, *, base_confidence: float = 0.8) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=1,
        rule_version=1,
        reason_code=0,
        base_confidence=base_confidence,
    )
    return entity_id, claim_id


def _evidence(
    engine: Engine, claim_id: int, *, evidence_type: int = 42, strength: float = 0.5,
) -> int:
    return engine.add_evidence(
        claim_id=claim_id,
        raw_ref_id=0,
        evidence_type=evidence_type,
        strength=strength,
    )


def _add_unresolved_gap(
    engine: Engine, claim_id: int, *, required_evidence_type: int = 99,
    rule_id: int = 1,
) -> int:
    return engine.add_gap(
        claim_id=claim_id, gap_type=1,
        required_evidence_type=required_evidence_type,
        severity=0.5, rule_id=rule_id,
    )


class TestEffectiveConfidenceCountModifier:
    """§31.12 invariants 1~3, 5, 8 — basic count modifier."""

    # invariant 1
    def test_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.compute_effective_confidence(999)

    # invariant 2
    def test_active_zero_count_is_one_candidate(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        # active 0
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 3
    def test_active_zero_count_is_one_confirmed(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 5 ★
    def test_active_two_applies_count_modifier(self) -> None:
        """active 2 → count = 0.8 추가 감쇠.

        candidate + active=2 (strengths 0.0, 0.0): freshness 영향 최소 (most recent=0)
        → base × 1.0 × (1.0 - 0.0 × 0.5) × 1.0 (no gap) × 0.8 = base × 0.8
        """
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        # Strength 0.0 으로 freshness 영향 제거 (modifier = 1.0)
        ev1 = _evidence(engine, claim_id, strength=0.0)
        ev2 = _evidence(engine, claim_id, strength=0.0)
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)

        result = engine.compute_effective_confidence(claim_id)

        # 1.0 × 1.0 (cand) × 1.0 (freshness, strength=0) × 1.0 (no gap) × 0.8 (count) = 0.8
        assert result.value == pytest.approx(0.8)

    # invariant 8 — refuted + active any → 0.0 (status=0)
    def test_refuted_with_active_two_returns_zero(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        ev1 = _evidence(engine, claim_id, strength=0.5)
        ev2 = _evidence(engine, claim_id, strength=0.5)
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )

        result = engine.compute_effective_confidence(claim_id)

        assert result.value == pytest.approx(0.0)


class TestCountModifierThreshold:
    """§31.12 invariants 4, 6, 7 — threshold + N invariance."""

    # invariant 4 — active 1 시 PR11-C 만 적용 (count = 1.0)
    def test_active_one_count_is_one_freshness_only(self) -> None:
        """active 1 + strength 0.8 → freshness=0.6, count=1.0 → base × 0.6."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        ev = _evidence(engine, claim_id, strength=0.8)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        result = engine.compute_effective_confidence(claim_id)

        # 1.0 × 1.0 (conf) × (1.0 - 0.8 × 0.5) × 1.0 (no gap) × 1.0 (count, active=1) = 0.6
        assert result.value == pytest.approx(0.6)

    # invariant 6 ★ — active 2 + freshness 0.8
    def test_active_two_confirmed_with_strong_freshness(self) -> None:
        """active 2, 최신 strength 0.8 → base × 1.0 × 0.6 × 1.0 × 0.8 = base × 0.48."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        # 등록 순서 = id 증가 순서 — most recent = ev2 (strength=0.8)
        ev1 = _evidence(engine, claim_id, strength=0.3)
        ev2 = _evidence(engine, claim_id, strength=0.8)
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        result = engine.compute_effective_confidence(claim_id)

        # 1.0 × 1.0 × 0.6 (freshness, most recent 0.8) × 1.0 (no gap) × 0.8 (count) = 0.48
        assert result.value == pytest.approx(0.48)

    # invariant 7 ★ — N 무관
    def test_n_invariant_two_vs_ten_same_count_modifier(self) -> None:
        """active 2 와 active 10 의 count_modifier 동일 (Sub-decision E-4)."""
        engine_two = Engine()
        _, claim_two = _candidate_claim(engine_two, base_confidence=1.0)
        # 모두 strength=0.0 으로 freshness 영향 제거
        for _ in range(2):
            ev = _evidence(engine_two, claim_two, strength=0.0)
            engine_two.register_contradiction(claim_two, ev)

        engine_ten = Engine()
        _, claim_ten = _candidate_claim(engine_ten, base_confidence=1.0)
        for _ in range(10):
            ev = _evidence(engine_ten, claim_ten, strength=0.0)
            engine_ten.register_contradiction(claim_ten, ev)

        result_two = engine_two.compute_effective_confidence(claim_two)
        result_ten = engine_ten.compute_effective_confidence(claim_ten)

        # 둘 다 base × 0.8 (count = 0.8, N 무관)
        assert result_two.value == pytest.approx(0.8)
        assert result_ten.value == pytest.approx(0.8)
        assert result_two == result_ten


class TestCountModifierResolvedIsolation:
    """§31.12 invariant 10 — resolved 제외 (Sub-decision E-5)."""

    def test_resolved_excluded_from_count(self) -> None:
        """contradictions 3 중 2 resolved → active 1 → count = 1.0 (PR11-C 만)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        # 3 contradictions
        ev1 = _evidence(engine, claim_id, strength=0.0)
        ev2 = _evidence(engine, claim_id, strength=0.0)
        ev3 = _evidence(engine, claim_id, strength=0.0)
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)
        engine.register_contradiction(claim_id, ev3)
        # 2 resolved → active = 1
        engine.register_contradiction_resolution(claim_id, ev1)
        engine.register_contradiction_resolution(claim_id, ev2)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        result = engine.compute_effective_confidence(claim_id)

        # active=1 (ev3, strength=0.0)
        # 1.0 × 1.0 × 1.0 (freshness, s=0) × 1.0 (no gap) × 1.0 (count, active=1) = 1.0
        assert result.value == pytest.approx(1.0)


class TestCountModifierComposition:
    """§31.12 invariant 9 ★ — 5-modifier 결합."""

    def test_disputed_with_active_two_and_unresolved_gap(self) -> None:
        """disputed + active 2 (최신 0.8) + unresolved gap:
        → base × 0.5 × 0.6 × 0.8 × 0.8 = base × 0.192.
        """
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        ev1 = _evidence(engine, claim_id, strength=0.3)
        ev2 = _evidence(engine, claim_id, strength=0.8)
        engine.register_contradiction(claim_id, ev1)
        engine.register_contradiction(claim_id, ev2)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=99, rule_id=2)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )

        result = engine.compute_effective_confidence(claim_id)

        # 1.0 × 0.5 × 0.6 × 0.8 × 0.8 = 0.192
        assert result.value == pytest.approx(0.192)


class TestCountModifierPriorBehaviorUnchanged:
    """§31.12 invariants 11~15 — 무변화 (이미 pass)."""

    # invariant 11 — PR11-C freshness_modifier 동작 무변화 (active 1 일 때 검증)
    def test_pr11c_freshness_modifier_unchanged(self) -> None:
        """active 1, strength 1.0 → base × 0.5 (PR11-C max). count=1.0."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        ev = _evidence(engine, claim_id, strength=1.0)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # 1.0 × 1.0 × 0.5 × 1.0 × 1.0 = 0.5
        assert result.value == pytest.approx(0.5)

    # invariant 12 — PR12-D gap_modifier 동작 무변화
    def test_pr12d_gap_modifier_unchanged(self) -> None:
        """active 0 + unresolved gap → base × 0.8 (PR12-D 만). count=1.0."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id)
        # active 0
        result = engine.compute_effective_confidence(claim_id)
        # 1.0 × 1.0 × 1.0 × 0.8 × 1.0 = 0.8
        assert result.value == pytest.approx(0.8)

    # invariant 13 — PR10-A refute 무변화
    def test_pr10a_refute_disputed_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id, strength=0.9)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        engine.dispute_claim_if_ready(claim_id)
        assert engine.refute_disputed_claim_if_ready(claim_id) is True

    # invariant 14 — PR9-A asc 무변화
    def test_pr9a_active_contradictions_asc_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_a = _evidence(engine, claim_id)
        ev_b = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev_b)
        engine.register_contradiction(claim_id, ev_a)
        # PR9-A asc
        assert engine.active_contradictions_for_claim(claim_id) == (ev_a, ev_b)

    # invariant 11/12 — PR11-B refute_by_freshness 무변화
    def test_pr11b_refute_by_freshness_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id, strength=0.9)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        engine.dispute_claim_if_ready(claim_id)
        assert engine.refute_disputed_claim_if_ready_by_freshness(claim_id) is True


class TestCountModifierPersistenceRoundtrip:
    """§31.12 invariant 19 — PR17 round-trip identity 보존."""

    def test_pr17_roundtrip_preserves_count_behavior(self) -> None:
        """active 2 + count modifier → snapshot/restore 후에도 동일."""
        original = Engine()
        _, claim_id = _candidate_claim(original, base_confidence=1.0)
        ev1 = _evidence(original, claim_id, strength=0.0)
        ev2 = _evidence(original, claim_id, strength=0.0)
        original.register_contradiction(claim_id, ev1)
        original.register_contradiction(claim_id, ev2)

        snap = original.to_snapshot()
        restored = Engine.from_snapshot(snap)

        # PR17 round-trip — count modifier 도 자연 보존 (engine state 그대로)
        original_eff = original.compute_effective_confidence(claim_id)
        restored_eff = restored.compute_effective_confidence(claim_id)
        assert original_eff == restored_eff


class TestCountModifierPrivacy:
    """§31.12 invariant 20 — _COUNT_PENALTY_MODIFIER private."""

    def test_count_penalty_modifier_not_in_ragcore(self) -> None:
        names = ["_COUNT_PENALTY_MODIFIER", "COUNT_PENALTY_MODIFIER"]
        for n in names:
            assert not hasattr(ragcore, n), f"ragcore should not expose {n}"
            assert n not in getattr(ragcore, "__all__", []), (
                f"__all__ should not include {n}"
            )

    def test_count_penalty_modifier_not_in_types(self) -> None:
        names = ["_COUNT_PENALTY_MODIFIER", "COUNT_PENALTY_MODIFIER"]
        for n in names:
            assert not hasattr(types_module, n), (
                f"ragcore.types should not expose {n}"
            )
