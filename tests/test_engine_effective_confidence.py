"""Tests for PR11-D — Effective confidence (MVP, status-only multiplier).

Invariants of ``compute_effective_confidence`` — PR1 stub 의 본문이 status
modifier 를 적용하도록 교체됨.

**55차 (test-first) 상태**: stub 그대로 (base_confidence 반환). 일부 invariant
는 이미 정합 (candidate / confirmed / KeyError / type / private export),
일부는 의도 fail (disputed / refuted / lifecycle transition trace).

§24.10 의 17 invariant 매핑:
1.  unknown claim_id → KeyError                                [이미 pass]
2.  candidate → effective == base                              [이미 pass]
3.  confirmed → effective == base                              [이미 pass]
4.  **refuted → effective.value == 0.0**                       [의도 fail ★]
5.  **disputed → effective.value == base × 0.5**               [의도 fail ★]
6.  return type is ScoreValue                                  [이미 pass]
7.  deterministic — same input same output                     [이미 pass]
8.  effective ≤ base (Sub-decision N, no boost)               [이미 pass — stub 도 base 반환]
9.  base=0.5 + candidate → 0.5                                 [pass]
10. base=0.8 + disputed → 0.4                                  [의도 fail ★]
11. base=1.0 + refuted → 0.0                                   [의도 fail ★]
12. base=0.0 + any status → 0.0                                [pass — 모두]
13. compute 가 read-only (lifecycle_history / base 무변화)     [pass]
14. **lifecycle transition 통한 effective 변화 추적** ★         [의도 fail (disputed/refuted 부분)]
15. _STATUS_MODIFIER_* private export 안 됨 (ragcore + types)  [이미 pass]
16. 기존 517 회귀 없음 — 전체 통과로 입증
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


def _candidate_claim(engine: Engine, *, base_confidence: float = 0.5) -> tuple[int, int]:
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


class TestComputeEffectiveConfidenceBasics:
    """§24.10 invariants 1, 6, 7 — fail-fast / type / deterministic."""

    # invariant 1
    def test_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.compute_effective_confidence(999)

    # invariant 6
    def test_returns_score_value_type(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        result = engine.compute_effective_confidence(claim_id)
        assert isinstance(result, ScoreValue)

    # invariant 7
    def test_deterministic_same_input_same_output(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        first = engine.compute_effective_confidence(claim_id)
        second = engine.compute_effective_confidence(claim_id)
        assert first == second


class TestStatusModifier:
    """§24.10 invariants 2, 3, 4, 5 — 4 status × effective 검증."""

    # invariant 2
    def test_candidate_returns_base(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 3
    def test_confirmed_returns_base(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.7)

    # invariant 5 ★ — disputed
    def test_disputed_halves_base(self) -> None:
        """disputed → effective = base × 0.5."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.4)

    # invariant 4 ★ — refuted
    def test_refuted_zero(self) -> None:
        """refuted → effective = 0.0 (확정 부정)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.0)


class TestBoundaryValues:
    """§24.10 invariants 8, 9, 10, 11, 12 — modifier boundary + 곱셈 정확성."""

    # invariant 9 (base 0.5 × candidate 1.0 = 0.5)
    def test_base_half_candidate(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.5)
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.5)

    # invariant 10 ★ (base 0.8 × disputed 0.5 = 0.4)
    def test_base_high_disputed(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.4)

    # invariant 11 ★ (base 1.0 × refuted 0.0 = 0.0)
    def test_base_max_refuted(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=1.0)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        result = engine.compute_effective_confidence(claim_id)
        assert result.value == pytest.approx(0.0)

    # invariant 12 (base 0.0 × any = 0.0)
    def test_base_zero_any_status_returns_zero(self) -> None:
        """base = 0.0 이면 어떤 status 든 effective = 0.0 (0 × anything = 0)."""
        engine = Engine()
        for status in (
            CLAIM_STATUS_CANDIDATE,
            CLAIM_STATUS_CONFIRMED,
            CLAIM_STATUS_DISPUTED,
            CLAIM_STATUS_REFUTED,
        ):
            _, claim_id = _candidate_claim(engine, base_confidence=0.0)
            engine._claims[claim_id] = replace(
                engine._claims[claim_id], status=status,
            )
            result = engine.compute_effective_confidence(claim_id)
            assert result.value == pytest.approx(0.0)

    # invariant 8 (no boost — effective ≤ base)
    def test_effective_never_exceeds_base(self) -> None:
        """Sub-decision N — modifier ∈ [0.0, 1.0]. effective ≤ base 보장."""
        engine = Engine()
        for status in (
            CLAIM_STATUS_CANDIDATE,
            CLAIM_STATUS_CONFIRMED,
            CLAIM_STATUS_DISPUTED,
            CLAIM_STATUS_REFUTED,
        ):
            _, claim_id = _candidate_claim(engine, base_confidence=0.6)
            engine._claims[claim_id] = replace(
                engine._claims[claim_id], status=status,
            )
            result = engine.compute_effective_confidence(claim_id)
            assert result.value <= 0.6


class TestLifecycleTransitionTrace:
    """§24.10 invariant 14 ★ — status 변화에 따라 effective 재계산."""

    def test_effective_changes_with_lifecycle_transitions(self) -> None:
        """confirmed → dispute → refute path 에서 effective 가 status 따라 변함."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)

        # 1. candidate → base
        eff_candidate = engine.compute_effective_confidence(claim_id)
        assert eff_candidate.value == pytest.approx(0.8)

        # 2. 강제 confirmed (white-box, lifecycle history 보존)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        eff_confirmed = engine.compute_effective_confidence(claim_id)
        assert eff_confirmed.value == pytest.approx(0.8)  # 그대로

        # 3. confirmed → disputed (★ 의도 fail 지점)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        eff_disputed = engine.compute_effective_confidence(claim_id)
        assert eff_disputed.value == pytest.approx(0.4)  # base × 0.5

        # 4. disputed → refuted (★ 의도 fail 지점)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        eff_refuted = engine.compute_effective_confidence(claim_id)
        assert eff_refuted.value == pytest.approx(0.0)


class TestComputeIsReadOnly:
    """§24.10 invariant 13 — compute 가 다른 state 변경 안 함."""

    def test_compute_does_not_change_base_confidence(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.7)
        before = engine.get_claim(claim_id).base_confidence

        engine.compute_effective_confidence(claim_id)
        engine.compute_effective_confidence(claim_id)

        after = engine.get_claim(claim_id).base_confidence
        assert before == after

    def test_compute_does_not_change_lifecycle_history(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        # 어떤 transition 도 일으키지 않음 — history 빈 tuple 유지
        before_history = engine.claim_lifecycle_history(claim_id)

        engine.compute_effective_confidence(claim_id)
        engine.compute_effective_confidence(claim_id)

        after_history = engine.claim_lifecycle_history(claim_id)
        assert before_history == after_history == ()


class TestStatusModifierPrivacy:
    """§24.10 invariant 15 — _STATUS_MODIFIER_* 가 public export 안 됨."""

    def test_status_modifier_constants_not_in_ragcore(self) -> None:
        import ragcore

        names = [
            "_STATUS_MODIFIER_CANDIDATE",
            "_STATUS_MODIFIER_CONFIRMED",
            "_STATUS_MODIFIER_DISPUTED",
            "_STATUS_MODIFIER_REFUTED",
            "STATUS_MODIFIER_CANDIDATE",  # also no public form
            "STATUS_MODIFIER_CONFIRMED",
            "STATUS_MODIFIER_DISPUTED",
            "STATUS_MODIFIER_REFUTED",
        ]
        for n in names:
            assert not hasattr(ragcore, n), f"ragcore should not expose {n}"
            assert n not in getattr(ragcore, "__all__", []), (
                f"__all__ should not include {n}"
            )

    def test_status_modifier_constants_not_in_types(self) -> None:
        import ragcore.types

        names = [
            "_STATUS_MODIFIER_CANDIDATE",
            "_STATUS_MODIFIER_CONFIRMED",
            "_STATUS_MODIFIER_DISPUTED",
            "_STATUS_MODIFIER_REFUTED",
            "STATUS_MODIFIER_CANDIDATE",
            "STATUS_MODIFIER_CONFIRMED",
            "STATUS_MODIFIER_DISPUTED",
            "STATUS_MODIFIER_REFUTED",
        ]
        for n in names:
            assert not hasattr(ragcore.types, n), (
                f"ragcore.types should not expose {n}"
            )
