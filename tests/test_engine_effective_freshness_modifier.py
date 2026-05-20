"""Tests for PR11-C — Effective confidence freshness modifier (MVP).

Invariants of ``compute_effective_confidence`` 의 본문 확장:
    effective = base × status_modifier × freshness_modifier

**63차 (test-first) 상태**: PR11-D 현재 동작 (`base × status_modifier`) 만.
freshness_modifier 미구현. fail pattern mixed (PR11-D 55차와 동일):

§26.12 18 invariant 매핑:
1.  unknown claim_id → KeyError                                [이미 pass]
2.  candidate + active 0 → base                                [이미 pass]
3.  confirmed + active 0 → base                                [이미 pass]
4.  disputed + active 0 → base × 0.5                           [이미 pass]
5.  refuted + 어떤 active → 0.0                                [이미 pass]
6.  confirmed + active strength 0.8 → base × 0.6 ★             [의도 fail]
7.  disputed + active strength 1.0 → base × 0.25 ★             [의도 fail]
8.  최신 1개만 사용 (Sub-decision O)                            [의도 fail]
9.  resolved contradiction은 freshness 에서 제외                [의도 fail]
10. PR10-A refute 정책 무변화                                   [이미 pass]
11. PR11-A query 무변화                                         [이미 pass]
12. PR9-A active_contradictions_for_claim asc 무변화            [이미 pass]
13. PR11-D status_modifier 값 무변화                            [이미 pass]
14. effective ≤ base (no boost)                                 [이미 pass]
15. compute is read-only                                        [이미 pass]
16. determinism                                                 [이미 pass]
17. _FRESHNESS_PENALTY_WEIGHT private                           [이미 pass]
18. 기존 547 회귀 없음 — 전체 통과로 입증
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


class TestPriorPR11DBehaviorPreserved:
    """§26.12 invariants 1, 2, 3, 4, 5 — active 0 / refuted 시 PR11-D 동작 보존 (이미 pass)."""

    # invariant 1
    def test_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.compute_effective_confidence(999)

    # invariant 2
    def test_candidate_no_active_returns_base(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 3
    def test_confirmed_no_active_returns_base(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 4
    def test_disputed_no_active_returns_half_base(self) -> None:
        """disputed + active 0 → base × 0.5 × 1.0 = base × 0.5 (PR11-D 와 동일)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.4)

    # invariant 5 — Sub-decision P
    def test_refuted_with_strong_active_returns_zero(self) -> None:
        """refuted + 어떤 active strong → effective = 0.0 (status × freshness 가 status 0 으로 0).

        Sub-decision P: status_modifier = 0.0 인 refuted 케이스에서
        freshness_modifier 무엇이든 effective = 0.0 보장.
        """
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        ev = _evidence(engine, claim_id, strength=0.95)  # strong
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.0)


class TestFreshnessModifierApplied:
    """§26.12 invariants 6, 7 — active 1+ 시 freshness_modifier 적용 (의도 fail)."""

    # invariant 6 ★
    def test_confirmed_with_active_strong_attenuates(self) -> None:
        """confirmed + active strength 0.8 → base × 1.0 × (1.0 - 0.8 × 0.5) = base × 0.6."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        ev = _evidence(engine, claim_id, strength=0.8)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        result = engine.compute_effective_confidence(claim_id)

        # 1.0 × 1.0 × (1.0 - 0.8 × 0.5) = 1.0 × 0.6 = 0.6
        assert result.value == pytest.approx(0.6)

    # invariant 7 ★
    def test_disputed_with_max_active_strength(self) -> None:
        """disputed + active strength 1.0 → base × 0.5 × (1.0 - 1.0 × 0.5) = base × 0.25.

        modifier 곱셈 분해 — status × freshness 두 modifier 가 모두 적용됨.
        """
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        ev = _evidence(engine, claim_id, strength=1.0)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )

        result = engine.compute_effective_confidence(claim_id)

        # 1.0 × 0.5 × (1.0 - 1.0 × 0.5) = 1.0 × 0.5 × 0.5 = 0.25
        assert result.value == pytest.approx(0.25)


class TestMostRecentOnly:
    """§26.12 invariant 8 — Sub-decision O: 최신 1개만 (의도 fail)."""

    def test_only_most_recent_active_strength_affects_modifier(self) -> None:
        """older strong + most_recent weak → freshness 는 weak (recent) 기준.

        PR11-C invariant: older strong 이 freshness_modifier 에 영향 없음 (recent only).

        active = [older(strength=1.0), recent(strength=0.2)]
        active_contradictions_by_freshness → (recent, older)  desc
        most_recent = recent (strength=0.2)
        freshness_modifier = 1.0 - 0.2 × 0.5 = 0.9 (PR11-C: recent only)
        count_modifier = 0.8 (PR19-E: active >= 2)
        → effective = 1.0 × 1.0 × 0.9 × 1.0 (no gap) × 0.8 = 0.72

        (만약 older 가 freshness 에 영향 줬다면:
            freshness = 1.0 - 1.0 × 0.5 = 0.5
            effective = 1.0 × 1.0 × 0.5 × 1.0 × 0.8 = 0.4
         → 0.72 ≠ 0.4 이므로 older 영향 없음 검증됨)
        """
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        ev_older = _evidence(engine, claim_id, strength=1.0)    # id=1, strong
        ev_recent = _evidence(engine, claim_id, strength=0.2)   # id=2, weak (more recent)
        engine.register_contradiction(claim_id, ev_older)
        engine.register_contradiction(claim_id, ev_recent)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        result = engine.compute_effective_confidence(claim_id)

        # PR11-C 의 freshness_modifier = 0.9 (recent only invariant 보존)
        # PR19-E 의 count_modifier = 0.8 (active >= 2 추가 감쇠)
        # 1.0 × 1.0 (conf) × 0.9 × 1.0 (no gap) × 0.8 = 0.72
        assert result.value == pytest.approx(0.72)


class TestResolvedExcluded:
    """§26.12 invariant 9 — resolved contradiction 은 freshness 에서 제외 (의도 fail)."""

    def test_resolved_strong_does_not_affect_freshness_modifier(self) -> None:
        """resolved 된 strong evidence 가 freshness_modifier 에 영향 없음.

        contradictions = [strong_resolved(strength=1.0), weak_active(strength=0.2)]
        resolved = {strong_resolved}
        active = {weak_active}
        active_contradictions_by_freshness = (weak_active,)
        most_recent = weak_active (strength=0.2) → modifier = 0.9
        → effective = 1.0 × 1.0 × 0.9 = 0.9
        """
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        ev_strong = _evidence(engine, claim_id, strength=1.0)   # id=1, resolved 예정
        ev_weak = _evidence(engine, claim_id, strength=0.2)     # id=2, active
        engine.register_contradiction(claim_id, ev_strong)
        engine.register_contradiction(claim_id, ev_weak)
        engine.register_contradiction_resolution(claim_id, ev_strong)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        result = engine.compute_effective_confidence(claim_id)

        # active = {ev_weak} only, strength=0.2 → modifier 0.9
        # effective = 1.0 × 1.0 × 0.9 = 0.9
        assert result.value == pytest.approx(0.9)


class TestPriorPolicyUnchanged:
    """§26.12 invariants 10, 11, 12, 13 — Sub-decision: 기존 정책 무변화 (이미 pass)."""

    # invariant 10 — PR10-A refute 무변화
    def test_pr10a_refute_disputed_unchanged(self) -> None:
        """PR10-A: active strength >= 0.8 → refuted (PR11-C 영향 없음)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.5)
        ev = _evidence(engine, claim_id, strength=0.9)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        engine.dispute_claim_if_ready(claim_id)

        result = engine.refute_disputed_claim_if_ready(claim_id)

        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 11 — PR11-A query 무변화
    def test_pr11a_freshness_queries_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_a = _evidence(engine, claim_id)
        ev_b = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev_a)
        engine.register_contradiction(claim_id, ev_b)

        # PR11-A 정렬 desc
        assert engine.active_contradictions_by_freshness(claim_id) == (ev_b, ev_a)
        # primitive
        assert engine.evidence_freshness(ev_a) == ev_a
        assert engine.evidence_freshness(ev_b) == ev_b

    # invariant 12 — PR9-A asc 무변화
    def test_pr9a_active_contradictions_asc_unchanged(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_a = _evidence(engine, claim_id)
        ev_b = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev_b)
        engine.register_contradiction(claim_id, ev_a)
        # PR9-A: evidence_id asc
        assert engine.active_contradictions_for_claim(claim_id) == (ev_a, ev_b)


class TestEffectiveConfidenceProperties:
    """§26.12 invariants 14, 15, 16 — no boost / read-only / determinism."""

    # invariant 14
    def test_effective_never_exceeds_base(self) -> None:
        """no boost — modifier 둘 다 ∈ [0.0, 1.0] → product ∈ [0.0, 1.0]."""
        engine = Engine()
        # 다양한 시나리오에서 검증
        for status, ev_strength in [
            (CLAIM_STATUS_CANDIDATE, None),
            (CLAIM_STATUS_CONFIRMED, None),
            (CLAIM_STATUS_CONFIRMED, 0.9),
            (CLAIM_STATUS_DISPUTED, None),
            (CLAIM_STATUS_DISPUTED, 0.9),
            (CLAIM_STATUS_REFUTED, None),
            (CLAIM_STATUS_REFUTED, 0.9),
        ]:
            _, claim_id = _candidate_claim(engine, base_confidence=0.6)
            if ev_strength is not None:
                ev = _evidence(engine, claim_id, strength=ev_strength)
                engine.register_contradiction(claim_id, ev)
            engine._claims[claim_id] = replace(
                engine._claims[claim_id], status=status,
            )
            result = engine.compute_effective_confidence(claim_id)
            assert result.value <= 0.6, (
                f"effective {result.value} > base 0.6 in status={status}, "
                f"ev_strength={ev_strength}"
            )

    # invariant 15
    def test_compute_is_read_only(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)
        ev = _evidence(engine, claim_id, strength=0.5)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )

        before_base = engine.get_claim(claim_id).base_confidence
        before_contras = engine.contradictions_for_claim(claim_id)
        before_active = engine.active_contradictions_for_claim(claim_id)
        before_history = engine.claim_lifecycle_history(claim_id)

        engine.compute_effective_confidence(claim_id)
        engine.compute_effective_confidence(claim_id)

        assert engine.get_claim(claim_id).base_confidence == before_base
        assert engine.contradictions_for_claim(claim_id) == before_contras
        assert engine.active_contradictions_for_claim(claim_id) == before_active
        assert engine.claim_lifecycle_history(claim_id) == before_history

    # invariant 16
    def test_deterministic(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        ev = _evidence(engine, claim_id, strength=0.6)
        engine.register_contradiction(claim_id, ev)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )

        first = engine.compute_effective_confidence(claim_id)
        second = engine.compute_effective_confidence(claim_id)
        assert first == second


class TestFreshnessPenaltyWeightPrivacy:
    """§26.12 invariant 17 — _FRESHNESS_PENALTY_WEIGHT private."""

    def test_freshness_penalty_weight_not_in_ragcore(self) -> None:
        import ragcore

        names = [
            "_FRESHNESS_PENALTY_WEIGHT",
            "FRESHNESS_PENALTY_WEIGHT",
        ]
        for n in names:
            assert not hasattr(ragcore, n), f"ragcore should not expose {n}"
            assert n not in getattr(ragcore, "__all__", []), (
                f"__all__ should not include {n}"
            )

    def test_freshness_penalty_weight_not_in_types(self) -> None:
        import ragcore.types

        names = [
            "_FRESHNESS_PENALTY_WEIGHT",
            "FRESHNESS_PENALTY_WEIGHT",
        ]
        for n in names:
            assert not hasattr(ragcore.types, n), (
                f"ragcore.types should not expose {n}"
            )
