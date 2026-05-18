"""Tests for ragcore.rule_compile — RuleSpec → RuleDefinition compile.

Coverage:
- known id + each maturity → correct RuleDefinition
- unknown id / maturity → ValueError
- version / prior_confidence 보존
- RULE_ID_MAP 자체 무결성 (production 데이터)
- _validate_rule_id_map 유닛 검증 (fake mappings)
- YAML → RuleSpec → RuleDefinition end-to-end
"""

from __future__ import annotations

from typing import Any

import pytest

from ragcore import Engine, RuleDefinition, ScoreValue
from ragcore.rule_compile import (
    RULE_ID_MAP,
    RULE_ID_MAX,
    RULE_ID_MIN,
    _validate_rule_id_map,
    compile_rule_definition,
    register_rule_spec,
)
from ragcore.rule_loader import load_rule_spec, load_rule_spec_from_yaml
from ragcore.types import (
    RULE_MATURITY_DEPRECATED,
    RULE_MATURITY_EXPERIMENTAL,
    RULE_MATURITY_STABLE,
)


def _minimal_spec_dict(**overrides: Any) -> dict[str, Any]:
    spec = {
        "id": "RULE_DOMAIN_SSH_001",
        "version": 1,
        "maturity": "experimental",
        "reliability": {"prior_confidence": 0.5},
    }
    spec.update(overrides)
    return spec


# =====================================================================
# Compile — basic shape
# =====================================================================

class TestCompileBasic:
    def test_known_id_experimental(self) -> None:
        spec = load_rule_spec(_minimal_spec_dict())
        definition = compile_rule_definition(spec)
        assert isinstance(definition, RuleDefinition)
        assert definition.id == 1
        assert definition.version == 1
        assert definition.maturity == RULE_MATURITY_EXPERIMENTAL
        assert definition.prior_confidence == ScoreValue(0.5)

    def test_stable_maturity(self) -> None:
        spec = load_rule_spec(_minimal_spec_dict(maturity="stable"))
        assert compile_rule_definition(spec).maturity == RULE_MATURITY_STABLE

    def test_deprecated_maturity(self) -> None:
        spec = load_rule_spec(_minimal_spec_dict(maturity="deprecated"))
        assert compile_rule_definition(spec).maturity == RULE_MATURITY_DEPRECATED


# =====================================================================
# Compile — field preservation
# =====================================================================

class TestCompileVersionPreserved:
    def test_version_1(self) -> None:
        spec = load_rule_spec(_minimal_spec_dict(version=1))
        assert compile_rule_definition(spec).version == 1

    def test_version_65535(self) -> None:
        spec = load_rule_spec(_minimal_spec_dict(version=65535))
        assert compile_rule_definition(spec).version == 65535


class TestCompilePriorConfidencePreserved:
    def test_zero(self) -> None:
        spec = load_rule_spec(
            _minimal_spec_dict(reliability={"prior_confidence": 0.0})
        )
        assert compile_rule_definition(spec).prior_confidence == ScoreValue(0.0)

    def test_one(self) -> None:
        spec = load_rule_spec(
            _minimal_spec_dict(reliability={"prior_confidence": 1.0})
        )
        assert compile_rule_definition(spec).prior_confidence == ScoreValue(1.0)

    def test_arbitrary_value(self) -> None:
        spec = load_rule_spec(
            _minimal_spec_dict(reliability={"prior_confidence": 0.55})
        )
        assert compile_rule_definition(spec).prior_confidence == ScoreValue(0.55)


# =====================================================================
# Compile — unknown id / maturity
# =====================================================================

class TestCompileUnknown:
    def test_unknown_id_rejected(self) -> None:
        spec = load_rule_spec(_minimal_spec_dict(id="NO_SUCH_RULE"))
        with pytest.raises(ValueError, match="unknown rule id"):
            compile_rule_definition(spec)

    def test_unknown_maturity_rejected(self) -> None:
        spec = load_rule_spec(_minimal_spec_dict(maturity="alpha"))
        with pytest.raises(ValueError, match="unknown maturity"):
            compile_rule_definition(spec)


# =====================================================================
# _validate_rule_id_map — integrity helper
# =====================================================================

class TestValidateRuleIdMap:
    def test_empty_map_ok(self) -> None:
        _validate_rule_id_map({})

    def test_valid_map(self) -> None:
        _validate_rule_id_map({"A": 1, "B": 2, "C": 65535})

    def test_zero_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_rule_id_map({"A": 0})

    def test_negative_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_rule_id_map({"A": -1})

    def test_above_max_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_rule_id_map({"A": 65536})

    def test_duplicate_values_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_rule_id_map({"A": 1, "B": 1})

    def test_empty_key_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_rule_id_map({"": 1})

    def test_whitespace_only_key_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_rule_id_map({"   ": 1})

    def test_non_int_value_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_rule_id_map({"A": "1"})  # type: ignore[dict-item]

    def test_bool_value_rejected(self) -> None:
        """bool 은 int subclass — 명시적 차단."""
        with pytest.raises(AssertionError):
            _validate_rule_id_map({"A": True})  # type: ignore[dict-item]


# =====================================================================
# RULE_ID_MAP — production data integrity
# =====================================================================

class TestRuleIdMapIntegrity:
    def test_no_duplicate_values(self) -> None:
        values = list(RULE_ID_MAP.values())
        assert len(values) == len(set(values))

    def test_all_values_in_range(self) -> None:
        for name, value in RULE_ID_MAP.items():
            assert RULE_ID_MIN <= value <= RULE_ID_MAX, (
                f"{name}={value} out of range"
            )

    def test_all_keys_non_empty(self) -> None:
        for key in RULE_ID_MAP:
            assert isinstance(key, str)
            assert key.strip()

    def test_ssh_001_present(self) -> None:
        """Reference rule from §9 SSH_001 yaml example."""
        assert "RULE_DOMAIN_SSH_001" in RULE_ID_MAP


# =====================================================================
# End-to-end YAML → RuleSpec → RuleDefinition
# =====================================================================

class TestEndToEndYamlToRuleDefinition:
    YAML_TEXT = """
id: RULE_DOMAIN_SSH_001
version: 1
maturity: experimental
reliability:
  prior_confidence: 0.55
"""

    def test_full_chain(self) -> None:
        spec = load_rule_spec_from_yaml(self.YAML_TEXT)
        definition = compile_rule_definition(spec)
        assert isinstance(definition, RuleDefinition)
        assert definition.id == 1
        assert definition.version == 1
        assert definition.maturity == RULE_MATURITY_EXPERIMENTAL
        assert definition.prior_confidence == ScoreValue(0.55)

    def test_spec_not_mutated(self) -> None:
        spec = load_rule_spec_from_yaml(self.YAML_TEXT)
        _ = compile_rule_definition(spec)
        # spec 은 그대로 (compile 은 새 RuleDefinition 만 만듬)
        assert spec.id == "RULE_DOMAIN_SSH_001"
        assert spec.maturity == "experimental"


# =====================================================================
# register_rule_spec — Engine bridge
# =====================================================================

class TestRegisterRuleSpec:
    def test_registers_compiled_definition_in_engine(self) -> None:
        engine = Engine()
        spec = load_rule_spec(_minimal_spec_dict())
        definition = register_rule_spec(engine, spec)

        # 반환값은 compile 결과 그대로
        assert isinstance(definition, RuleDefinition)
        assert definition.id == 1
        assert definition.version == 1

        # Engine 에서 조회 가능
        retrieved = engine.get_rule(rule_id=1, rule_version=1)
        assert retrieved == definition

    def test_rule_stats_auto_initialized(self) -> None:
        """Engine.register_rule 이 빈 RuleStats 도 함께 만든다."""
        engine = Engine()
        spec = load_rule_spec(_minimal_spec_dict())
        register_rule_spec(engine, spec)

        stats = engine.get_rule_stats(rule_id=1, rule_version=1)
        assert stats.rule_id == 1
        assert stats.rule_version == 1
        assert stats.firing_count == 0
        assert stats.confirmed_true_count == 0
        assert stats.confirmed_false_count == 0
        assert stats.observed_precision is None
        assert stats.false_positive_rate is None

    def test_duplicate_registration_rejected(self) -> None:
        """같은 (id, version) 두 번 등록 → Engine.register_rule 이 ValueError."""
        engine = Engine()
        spec = load_rule_spec(_minimal_spec_dict())
        register_rule_spec(engine, spec)
        with pytest.raises(ValueError, match="already registered"):
            register_rule_spec(engine, spec)

    def test_unknown_rule_id_propagates(self) -> None:
        """compile 단계의 ValueError 가 그대로 전파."""
        engine = Engine()
        spec = load_rule_spec(_minimal_spec_dict(id="NO_SUCH_RULE"))
        with pytest.raises(ValueError, match="unknown rule id"):
            register_rule_spec(engine, spec)

    def test_unknown_maturity_propagates(self) -> None:
        engine = Engine()
        spec = load_rule_spec(_minimal_spec_dict(maturity="alpha"))
        with pytest.raises(ValueError, match="unknown maturity"):
            register_rule_spec(engine, spec)

    def test_spec_not_mutated_by_register(self) -> None:
        engine = Engine()
        spec = load_rule_spec(_minimal_spec_dict())
        _ = register_rule_spec(engine, spec)
        # spec 은 register 이후에도 원본 그대로
        assert spec.id == "RULE_DOMAIN_SSH_001"
        assert spec.maturity == "experimental"
        assert spec.version == 1

    def test_two_engines_isolated(self) -> None:
        """서로 다른 Engine 인스턴스는 rule registry 공유 안 함."""
        engine_a = Engine()
        engine_b = Engine()
        spec = load_rule_spec(_minimal_spec_dict())

        register_rule_spec(engine_a, spec)
        # engine_b 는 아직 모름
        with pytest.raises(KeyError):
            engine_b.get_rule(rule_id=1, rule_version=1)
        # engine_b 도 동일 spec 으로 등록 가능 (중복 아님)
        register_rule_spec(engine_b, spec)
        assert engine_b.get_rule(rule_id=1, rule_version=1).id == 1

    def test_yaml_to_engine_end_to_end(self) -> None:
        engine = Engine()
        yaml_text = """
id: RULE_DOMAIN_SSH_001
version: 1
maturity: experimental
reliability:
  prior_confidence: 0.55
"""
        spec = load_rule_spec_from_yaml(yaml_text)
        register_rule_spec(engine, spec)

        rule = engine.get_rule(rule_id=1, rule_version=1)
        assert rule.id == 1
        assert rule.version == 1
        assert rule.maturity == RULE_MATURITY_EXPERIMENTAL
        assert rule.prior_confidence == ScoreValue(0.55)

    def test_same_id_different_version_both_registerable(self) -> None:
        """RuleVersion 으로 같은 룰의 evolution 표현 — 둘 다 등록 가능."""
        engine = Engine()
        spec_v1 = load_rule_spec(_minimal_spec_dict(version=1))
        spec_v2 = load_rule_spec(_minimal_spec_dict(version=2))

        register_rule_spec(engine, spec_v1)
        register_rule_spec(engine, spec_v2)

        # 둘 다 조회 가능
        assert engine.get_rule(rule_id=1, rule_version=1).version == 1
        assert engine.get_rule(rule_id=1, rule_version=2).version == 2
