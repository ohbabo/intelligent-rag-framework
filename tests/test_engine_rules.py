"""Tests for Claim.base_confidence + RuleDefinition + RuleStats + rule registry.

Naming triangle 보존 검증:
- Claim.base_confidence       (firing 시점 스냅샷)
- RuleDefinition.prior_confidence (룰 자체의 사전 신뢰도)
- effective_confidence        (다음 PR 함수, 여기선 미포함)
"""

from __future__ import annotations

import pytest

from ragcore import (
    RULE_MATURITY_EXPERIMENTAL,
    RULE_MATURITY_STABLE,
    Engine,
    RuleDefinition,
    RuleStats,
    ScoreValue,
)


def _entity(engine: Engine) -> int:
    return engine.add_entity(entity_type=1)


def _register(
    engine: Engine,
    rule_id: int = 1,
    rule_version: int = 1,
    *,
    maturity: int = RULE_MATURITY_EXPERIMENTAL,
    prior_confidence: float = 0.5,
) -> RuleDefinition:
    definition = RuleDefinition(
        id=rule_id,
        version=rule_version,
        maturity=maturity,
        prior_confidence=ScoreValue(prior_confidence),
    )
    engine.register_rule(definition)
    return definition


class TestClaimBaseConfidence:
    def test_default_is_half(self) -> None:
        engine = Engine()
        e = _entity(engine)
        c = engine.add_claim(
            subject_id=e, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
        )
        assert engine.get_claim(c).base_confidence == ScoreValue(0.5)

    def test_explicit_value(self) -> None:
        engine = Engine()
        e = _entity(engine)
        c = engine.add_claim(
            subject_id=e, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.85,
        )
        assert engine.get_claim(c).base_confidence.value == pytest.approx(0.85)

    def test_rejects_out_of_range(self) -> None:
        engine = Engine()
        e = _entity(engine)
        with pytest.raises(ValueError):
            engine.add_claim(
                subject_id=e, claim_type=1,
                rule_id=1, rule_version=1, reason_code=0,
                base_confidence=1.5,
            )

    def test_base_confidence_is_frozen_with_claim(self) -> None:
        engine = Engine()
        e = _entity(engine)
        c = engine.add_claim(
            subject_id=e, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.55,
        )
        claim = engine.get_claim(c)
        with pytest.raises(AttributeError):
            claim.base_confidence = ScoreValue(0.99)  # type: ignore[misc]


class TestRuleDefinition:
    def test_is_frozen(self) -> None:
        rd = RuleDefinition(
            id=1, version=1,
            maturity=RULE_MATURITY_EXPERIMENTAL,
            prior_confidence=ScoreValue(0.5),
        )
        with pytest.raises(AttributeError):
            rd.version = 2  # type: ignore[misc]


class TestRuleStats:
    def test_is_frozen(self) -> None:
        rs = RuleStats(rule_id=1, rule_version=1)
        with pytest.raises(AttributeError):
            rs.firing_count = 5  # type: ignore[misc]

    def test_defaults(self) -> None:
        rs = RuleStats(rule_id=1, rule_version=1)
        assert rs.firing_count == 0
        assert rs.confirmed_true_count == 0
        assert rs.confirmed_false_count == 0
        assert rs.observed_precision is None
        assert rs.false_positive_rate is None


class TestRegisterRule:
    def test_stores_definition_and_initial_stats(self) -> None:
        engine = Engine()
        rd = _register(engine, rule_id=42, rule_version=10)
        assert engine.get_rule(42, 10) == rd
        stats = engine.get_rule_stats(42, 10)
        assert stats.rule_id == 42
        assert stats.rule_version == 10
        assert stats.firing_count == 0
        assert stats.observed_precision is None

    def test_rejects_duplicate(self) -> None:
        engine = Engine()
        _register(engine, rule_id=1, rule_version=1)
        with pytest.raises(ValueError):
            _register(engine, rule_id=1, rule_version=1)

    def test_same_id_different_version_ok(self) -> None:
        engine = Engine()
        _register(engine, rule_id=1, rule_version=1, prior_confidence=0.5)
        _register(engine, rule_id=1, rule_version=2, prior_confidence=0.6)
        assert engine.get_rule(1, 1).prior_confidence == ScoreValue(0.5)
        assert engine.get_rule(1, 2).prior_confidence == ScoreValue(0.6)


class TestRuleLookup:
    def test_get_rule_unknown_raises(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.get_rule(999, 1)

    def test_get_rule_stats_unknown_raises(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.get_rule_stats(999, 1)

    def test_get_rule_wrong_version_raises(self) -> None:
        engine = Engine()
        _register(engine, rule_id=1, rule_version=1)
        with pytest.raises(KeyError):
            engine.get_rule(1, 2)


class TestUpdateRuleStats:
    def test_firing_delta_accumulates(self) -> None:
        engine = Engine()
        _register(engine)
        engine.update_rule_stats(1, 1, firing_delta=3)
        engine.update_rule_stats(1, 1, firing_delta=2)
        assert engine.get_rule_stats(1, 1).firing_count == 5

    def test_replaces_with_new_instance_not_mutate(self) -> None:
        engine = Engine()
        _register(engine)
        old = engine.get_rule_stats(1, 1)
        engine.update_rule_stats(1, 1, firing_delta=1)
        new = engine.get_rule_stats(1, 1)
        assert old.firing_count == 0  # old 인스턴스는 그대로 (frozen)
        assert new.firing_count == 1
        assert old is not new

    def test_confirmed_counts_accumulate(self) -> None:
        engine = Engine()
        _register(engine)
        engine.update_rule_stats(1, 1, true_delta=5, false_delta=2)
        s = engine.get_rule_stats(1, 1)
        assert s.confirmed_true_count == 5
        assert s.confirmed_false_count == 2

    def test_precision_and_fpr_set(self) -> None:
        engine = Engine()
        _register(engine)
        engine.update_rule_stats(
            1, 1,
            observed_precision=ScoreValue(0.8),
            false_positive_rate=ScoreValue(0.15),
        )
        s = engine.get_rule_stats(1, 1)
        assert s.observed_precision == ScoreValue(0.8)
        assert s.false_positive_rate == ScoreValue(0.15)

    def test_precision_none_keeps_existing(self) -> None:
        """observed_precision=None 은 '변경 안 함' 의미, nullify 아님."""
        engine = Engine()
        _register(engine)
        engine.update_rule_stats(1, 1, observed_precision=ScoreValue(0.7))
        engine.update_rule_stats(1, 1, firing_delta=1)  # precision 인자 없음
        assert engine.get_rule_stats(1, 1).observed_precision == ScoreValue(0.7)

    def test_unknown_rule_raises(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.update_rule_stats(999, 1, firing_delta=1)


class TestComputeEffectiveConfidence:
    """MVP stub 행동을 명시적으로 잠근다. Phase 2에서 logic이 들어올 때 이 테스트가 가이드."""

    def test_mvp_stub_returns_base_confidence(self) -> None:
        engine = Engine()
        e = _entity(engine)
        c = engine.add_claim(
            subject_id=e, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.73,
        )
        assert engine.compute_effective_confidence(c) == ScoreValue(0.73)

    def test_unknown_claim_raises(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.compute_effective_confidence(999)

    def test_stub_ignores_evidence_in_mvp(self) -> None:
        """MVP stub은 evidence가 추가돼도 base_confidence만 반환.
        Phase 2에서 evidence_strength와 RuleStats를 조합."""
        engine = Engine()
        e = _entity(engine)
        c = engine.add_claim(
            subject_id=e, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.50,
        )
        engine.add_evidence(
            claim_id=c, raw_ref_id=1, evidence_type=1, strength=0.95
        )
        # 강한 evidence가 들어왔지만 stub은 여전히 base_confidence
        assert engine.compute_effective_confidence(c) == ScoreValue(0.50)

    def test_stub_ignores_rule_stats_in_mvp(self) -> None:
        """RuleStats가 어떻게 갱신돼도 stub은 base_confidence만."""
        engine = Engine()
        _register(engine, rule_id=1, rule_version=1, prior_confidence=0.5)
        e = _entity(engine)
        c = engine.add_claim(
            subject_id=e, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.60,
        )
        engine.update_rule_stats(
            1, 1,
            firing_delta=100, true_delta=90,
            observed_precision=ScoreValue(0.9),
        )
        assert engine.compute_effective_confidence(c) == ScoreValue(0.60)


class TestNamingTriangleSeparation:
    """Claim.base_confidence ≠ RuleDefinition.prior_confidence 임을 검증."""

    def test_base_and_prior_are_independent_slots(self) -> None:
        engine = Engine()
        # 룰 자체 신뢰도는 0.50 (experimental)
        _register(engine, rule_id=1, rule_version=1, prior_confidence=0.50)
        # 하지만 특정 입력에서 Claim의 초기 확신도는 0.55
        e = _entity(engine)
        c = engine.add_claim(
            subject_id=e, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.55,
        )
        assert engine.get_rule(1, 1).prior_confidence == ScoreValue(0.50)
        assert engine.get_claim(c).base_confidence == ScoreValue(0.55)
        # 두 값은 서로 다른 슬롯, 서로 영향 없음

    def test_rule_stats_can_evolve_without_touching_claim(self) -> None:
        engine = Engine()
        _register(engine, rule_id=1, rule_version=1, prior_confidence=0.50)
        e = _entity(engine)
        c = engine.add_claim(
            subject_id=e, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.55,
        )
        # 운영하면서 룰의 precision 측정값이 들어옴
        engine.update_rule_stats(
            1, 1,
            firing_delta=10,
            true_delta=8, false_delta=2,
            observed_precision=ScoreValue(0.8),
        )
        # Claim.base_confidence 는 변하지 않음 (firing 시점 스냅샷)
        assert engine.get_claim(c).base_confidence == ScoreValue(0.55)
        # Rule stats는 별도로 갱신됨
        assert engine.get_rule_stats(1, 1).observed_precision == ScoreValue(0.8)
