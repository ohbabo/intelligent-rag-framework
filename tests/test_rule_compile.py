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

from ragcore import RuleDefinition, ScoreValue
from ragcore.rule_compile import (
    RULE_ID_MAP,
    RULE_ID_MAX,
    RULE_ID_MIN,
    _validate_rule_id_map,
    compile_rule_definition,
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
