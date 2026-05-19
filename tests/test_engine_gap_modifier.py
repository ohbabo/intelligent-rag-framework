"""Tests for PR12-D — Effective confidence gap modifier (MVP, binary weak).

Invariants of ``compute_effective_confidence`` 의 본문 확장:
    effective = base × status × freshness × gap

**71차 (test-first) 상태**: PR11-C 본문 (base × status × freshness) 만.
gap_modifier 미적용. fail pattern mixed (PR11-C 63차와 동일):

§28.12 의 24 invariant 매핑:
1.  unknown claim_id → KeyError                                  [이미 pass]
2.  gap 0 + candidate → base                                     [이미 pass]
3.  gap 0 + confirmed → base                                     [이미 pass]
4.  gap 0 + disputed → base × 0.5                                [이미 pass]
5.  gap 0 + refuted → 0.0                                        [이미 pass]
6.  all resolved → modifier 1.0 (effective 동일)                 [이미 pass]
7.  unresolved 1+ + candidate → base × 0.8 ★                     [의도 fail]
8.  unresolved 1+ + confirmed → base × 0.8 ★                     [의도 fail]
9.  unresolved 1+ + disputed → base × 0.4 ★                      [의도 fail]
10. unresolved 1+ + refuted → 0.0                                [이미 pass — Sub-decision P]
11. N 무관 (1 vs 10 동일 modifier) ★                              [의도 fail]
12. resolved + unresolved 혼재 → unresolved 1+ 이므로 ×0.8 ★    [의도 fail]
13. PR11-C freshness 결합 (active + unresolved) ★                [의도 fail]
14. PR5 gap_resolution 동작 무변화                                [이미 pass]
15. PR11-C effective (gap 0 시) 무변화                            [이미 pass]
16. PR10-A / PR11-B refute 무변화                                 [이미 pass]
17. PR11-A query 무변화                                           [이미 pass]
18. PR9-A asc 무변화                                              [이미 pass]
19. PR11-D _STATUS_MODIFIER_* 값 무변화 (간접)                    [이미 pass]
20. effective ≤ base (no boost)                                  [이미 pass]
21. compute is read-only                                          [이미 pass]
22. determinism                                                   [이미 pass]
23. _GAP_PENALTY_MODIFIER private                                 [이미 pass]
24. 기존 589 회귀 없음 — 전체 통과로 입증
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    Engine,
    ScoreValue,
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
    engine: Engine, claim_id: int, *, gap_type: int = 1, required_evidence_type: int = 99,
    rule_id: int = 1,
) -> int:
    """gap 추가하지만 matching evidence 등록하지 않음 → unresolved 상태."""
    return engine.add_gap(
        claim_id=claim_id, gap_type=gap_type,
        required_evidence_type=required_evidence_type,
        severity=0.5, rule_id=rule_id,
    )


def _add_resolved_gap(
    engine: Engine, claim_id: int, *, evidence_type: int = 100,
    rule_id: int = 1,
) -> tuple[int, int]:
    """gap 추가 + matching evidence resolve → resolved 상태. (gap_id, evidence_id)."""
    gap_id = engine.add_gap(
        claim_id=claim_id, gap_type=1,
        required_evidence_type=evidence_type,
        severity=0.5, rule_id=rule_id,
    )
    ev_id = _evidence(engine, claim_id, evidence_type=evidence_type)
    engine.resolve_gaps_for_evidence(ev_id)
    return gap_id, ev_id


class TestEffectiveConfidenceGapModifier:
    """§28.12 invariants 1~10 — basic gap modifier 시나리오."""

    # invariant 1
    def test_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.compute_effective_confidence(999)

    # invariant 2
    def test_candidate_no_gap_returns_base(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 3
    def test_confirmed_no_gap_returns_base(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 4
    def test_disputed_no_gap_returns_half_base(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        # 0.8 × 0.5 × 1.0 (no active) × 1.0 (no gap) = 0.4
        assert result.value == pytest.approx(0.4)

    # invariant 5
    def test_refuted_no_gap_returns_zero(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.0)

    # invariant 7 ★
    def test_candidate_with_unresolved_gap_attenuates(self) -> None:
        """candidate + unresolved 1+ → base × 1.0 × 1.0 × 0.8 = base × 0.8."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id)

        result = engine.compute_effective_confidence(claim_id)

        assert result.value == pytest.approx(0.8)

    # invariant 8 ★
    def test_confirmed_with_unresolved_gap_attenuates(self) -> None:
        """confirmed + unresolved 1+ → base × 1.0 × 1.0 × 0.8 = base × 0.8."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        result = engine.compute_effective_confidence(claim_id)

        assert result.value == pytest.approx(0.8)

    # invariant 9 ★
    def test_disputed_with_unresolved_gap_compounds(self) -> None:
        """disputed + unresolved 1+ → base × 0.5 × 1.0 × 0.8 = base × 0.4."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )

        result = engine.compute_effective_confidence(claim_id)

        assert result.value == pytest.approx(0.4)

    # invariant 10
    def test_refuted_with_unresolved_gap_returns_zero(self) -> None:
        """refuted + unresolved 1+ → 0.0 (Sub-decision P, status × gap 곱셈 무관)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )

        result = engine.compute_effective_confidence(claim_id)

        assert result.value == pytest.approx(0.0)


class TestGapModifierResolutionSemantics:
    """§28.12 invariants 6, 11, 12 — resolved/unresolved/혼재."""

    # invariant 6
    def test_all_gaps_resolved_returns_base(self) -> None:
        """모든 gap resolved → gap_modifier 1.0 → effective 변화 없음."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        _add_resolved_gap(engine, claim_id, evidence_type=100)
        _add_resolved_gap(engine, claim_id, evidence_type=101, rule_id=2)

        result = engine.compute_effective_confidence(claim_id)

        assert result.value == pytest.approx(0.7)

    # invariant 11 ★ — N 무관
    def test_one_or_many_unresolved_same_modifier(self) -> None:
        """unresolved 1개와 N개의 modifier 동일 (Sub-decision U binary)."""
        engine_one = Engine()
        _, claim_one = _candidate_claim(engine_one, base_confidence=1.0)
        _add_unresolved_gap(engine_one, claim_one, required_evidence_type=99)
        result_one = engine_one.compute_effective_confidence(claim_one)

        engine_many = Engine()
        _, claim_many = _candidate_claim(engine_many, base_confidence=1.0)
        # 10 개 unresolved gap (모두 다른 evidence_type, 모두 다른 rule_id 로 dedup 회피)
        for i in range(10):
            _add_unresolved_gap(
                engine_many, claim_many,
                required_evidence_type=200 + i,
                rule_id=10 + i,
            )
        result_many = engine_many.compute_effective_confidence(claim_many)

        # 둘 다 base × 0.8 (N 무관)
        assert result_one.value == pytest.approx(0.8)
        assert result_many.value == pytest.approx(0.8)
        assert result_one == result_many

    # invariant 12 ★ — 혼재
    def test_resolved_and_unresolved_mixed_attenuates(self) -> None:
        """resolved + unresolved 혼재 → unresolved 1+ 이므로 ×0.8."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_resolved_gap(engine, claim_id, evidence_type=100)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=99, rule_id=2)

        result = engine.compute_effective_confidence(claim_id)

        # gap_modifier = 0.8 (unresolved 1+)
        assert result.value == pytest.approx(0.8)


class TestGapModifierWithFreshness:
    """§28.12 invariant 13 ★ — PR11-C freshness × PR12-D gap 결합."""

    def test_confirmed_with_freshness_and_gap_compounds(self) -> None:
        """confirmed + active strong 0.8 + unresolved 1+
            → base × 1.0 × 0.6 × 0.8 = base × 0.48.
        """
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        # contradiction (PR11-C freshness path)
        ev_contra = _evidence(engine, claim_id, strength=0.8)
        engine.register_contradiction(claim_id, ev_contra)
        # unresolved gap (PR12-D path)
        _add_unresolved_gap(
            engine, claim_id, required_evidence_type=99, rule_id=2,
        )
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        result = engine.compute_effective_confidence(claim_id)

        # 1.0 × 1.0 (confirmed) × (1.0 - 0.8 × 0.5) × 0.8
        # = 1.0 × 1.0 × 0.6 × 0.8 = 0.48
        assert result.value == pytest.approx(0.48)


class TestPriorPolicyUnchanged:
    """§28.12 invariants 14~18 — PR5/PR10-A/PR11-A/PR11-B/PR9-A 무변화."""

    # invariant 14 — PR5 gap_resolution 동작 무변화
    def test_pr5_gap_resolution_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        gap_id, ev_id = _add_resolved_gap(engine, claim_id, evidence_type=100)
        # PR5: gap_resolution 은 resolve evidence_id 반환
        assert engine.gap_resolution(gap_id) == ev_id

    # invariant 16 — PR10-A refute 무변화
    def test_pr10a_refute_disputed_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id, strength=0.9)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        engine.dispute_claim_if_ready(claim_id)
        # PR10-A: ANY active >= 0.8 → True
        assert engine.refute_disputed_claim_if_ready(claim_id) is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 16 — PR11-B refute_by_freshness 무변화
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
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 17 — PR11-A query 무변화
    def test_pr11a_queries_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_a = _evidence(engine, claim_id)
        ev_b = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev_a)
        engine.register_contradiction(claim_id, ev_b)
        # PR11-A desc
        assert engine.active_contradictions_by_freshness(claim_id) == (ev_b, ev_a)

    # invariant 18 — PR9-A asc 무변화
    def test_pr9a_active_contradictions_asc_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_a = _evidence(engine, claim_id)
        ev_b = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev_b)
        engine.register_contradiction(claim_id, ev_a)
        # PR9-A asc
        assert engine.active_contradictions_for_claim(claim_id) == (ev_a, ev_b)


class TestGapModifierIsolation:
    """§28.12 invariants 20~22 — no boost / read-only / deterministic."""

    # invariant 20 — no boost
    def test_effective_never_exceeds_base(self) -> None:
        """다양한 시나리오 loop: gap × status × freshness 조합 모두 effective ≤ base."""
        scenarios = [
            (CLAIM_STATUS_CANDIDATE, False, None),
            (CLAIM_STATUS_CANDIDATE, True, None),
            (CLAIM_STATUS_CONFIRMED, True, 0.9),
            (CLAIM_STATUS_DISPUTED, True, 0.9),
            (CLAIM_STATUS_REFUTED, True, 0.9),
        ]
        for status, has_unresolved_gap, ev_strength in scenarios:
            engine = Engine()
            _, claim_id = _candidate_claim(engine, base_confidence=0.6)
            if has_unresolved_gap:
                _add_unresolved_gap(engine, claim_id)
            if ev_strength is not None:
                ev = _evidence(engine, claim_id, strength=ev_strength)
                engine.register_contradiction(claim_id, ev)
            engine._claims[claim_id] = replace(
                engine._claims[claim_id], status=status,
            )
            result = engine.compute_effective_confidence(claim_id)
            assert result.value <= 0.6, (
                f"effective {result.value} > base 0.6 in scenario: "
                f"status={status}, unresolved={has_unresolved_gap}, "
                f"ev_strength={ev_strength}"
            )

    # invariant 21 — read-only
    def test_compute_is_read_only(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        gap_id, ev_id = _add_resolved_gap(engine, claim_id, evidence_type=100)
        _add_unresolved_gap(engine, claim_id, required_evidence_type=99, rule_id=2)
        ev_contra = _evidence(engine, claim_id, strength=0.5)
        engine.register_contradiction(claim_id, ev_contra)

        before_base = engine.get_claim(claim_id).base_confidence
        before_gap_res = dict(engine._gap_resolutions)
        before_contras = engine.contradictions_for_claim(claim_id)
        before_history = engine.claim_lifecycle_history(claim_id)

        engine.compute_effective_confidence(claim_id)
        engine.compute_effective_confidence(claim_id)

        assert engine.get_claim(claim_id).base_confidence == before_base
        assert engine._gap_resolutions == before_gap_res
        assert engine.contradictions_for_claim(claim_id) == before_contras
        assert engine.claim_lifecycle_history(claim_id) == before_history

    # invariant 22 — deterministic
    def test_deterministic(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        _add_unresolved_gap(engine, claim_id)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        first = engine.compute_effective_confidence(claim_id)
        second = engine.compute_effective_confidence(claim_id)
        assert first == second


class TestGapModifierPrivacy:
    """§28.12 invariant 23 — _GAP_PENALTY_MODIFIER private."""

    def test_gap_penalty_modifier_not_in_ragcore(self) -> None:
        import ragcore

        names = ["_GAP_PENALTY_MODIFIER", "GAP_PENALTY_MODIFIER"]
        for n in names:
            assert not hasattr(ragcore, n), f"ragcore should not expose {n}"
            assert n not in getattr(ragcore, "__all__", []), (
                f"__all__ should not include {n}"
            )

    def test_gap_penalty_modifier_not_in_types(self) -> None:
        import ragcore.types

        names = ["_GAP_PENALTY_MODIFIER", "GAP_PENALTY_MODIFIER"]
        for n in names:
            assert not hasattr(ragcore.types, n), (
                f"ragcore.types should not expose {n}"
            )
