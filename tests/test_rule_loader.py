"""Tests for ragcore.rule_loader — YAML/dict rule spec header validation.

범위 (scope) 검증:
- header 4개 필드(id, version, maturity, reliability.prior_confidence) 검증
- 잘못된 타입/범위 거부
- raw dict 보존
- frozen RuleSpec
- YAML wrapper

범위 외 (deferred):
- condition / output / required_evidence
- Engine.register_rule 연동
- RuleId 문자열 → uint16 매핑
- RuleMaturity 문자열 → uint8 매핑
"""

from __future__ import annotations

from typing import Any

import pytest

from ragcore import ScoreValue
from ragcore.condition import Combinator, Predicate, evaluate_condition
from ragcore.rule_loader import (
    RuleSpec,
    compile_rule_condition,
    load_rule_spec,
    load_rule_spec_from_yaml,
)


def _minimal_spec(**overrides: Any) -> dict[str, Any]:
    """Valid minimal spec dict; overrides replace top-level fields."""
    spec: dict[str, Any] = {
        "id": "RULE_DOMAIN_SSH_001",
        "version": 1,
        "maturity": "experimental",
        "reliability": {"prior_confidence": 0.5},
    }
    spec.update(overrides)
    return spec


class TestVersionValidation:
    def test_version_1_passes(self) -> None:
        result = load_rule_spec(_minimal_spec(version=1))
        assert result.version == 1

    def test_version_65535_passes(self) -> None:
        result = load_rule_spec(_minimal_spec(version=65535))
        assert result.version == 65535

    def test_version_0_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_rule_spec(_minimal_spec(version=0))

    def test_version_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_rule_spec(_minimal_spec(version=-1))

    def test_version_65536_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_rule_spec(_minimal_spec(version=65536))

    def test_version_semver_string_rejected(self) -> None:
        with pytest.raises(TypeError):
            load_rule_spec(_minimal_spec(version="0.1.0"))

    def test_version_numeric_string_rejected(self) -> None:
        with pytest.raises(TypeError):
            load_rule_spec(_minimal_spec(version="1"))

    def test_version_bool_rejected(self) -> None:
        """bool is subclass of int in Python — must be excluded explicitly."""
        with pytest.raises(TypeError):
            load_rule_spec(_minimal_spec(version=True))

    def test_version_float_rejected(self) -> None:
        with pytest.raises(TypeError):
            load_rule_spec(_minimal_spec(version=1.0))


class TestIdValidation:
    def test_id_missing_rejected(self) -> None:
        spec = _minimal_spec()
        del spec["id"]
        with pytest.raises(ValueError):
            load_rule_spec(spec)

    def test_id_non_string_rejected(self) -> None:
        with pytest.raises(TypeError):
            load_rule_spec(_minimal_spec(id=123))

    def test_id_empty_string_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_rule_spec(_minimal_spec(id=""))

    def test_id_whitespace_only_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_rule_spec(_minimal_spec(id="   "))

    def test_id_tab_and_newline_only_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_rule_spec(_minimal_spec(id="\t\n  "))

    def test_id_surrounding_whitespace_stripped_on_store(self) -> None:
        result = load_rule_spec(_minimal_spec(id="  SSH_001  "))
        assert result.id == "SSH_001"

    def test_id_preserved_as_string(self) -> None:
        result = load_rule_spec(_minimal_spec(id="RULE_DOMAIN_SSH_001"))
        assert result.id == "RULE_DOMAIN_SSH_001"
        assert isinstance(result.id, str)


class TestMaturityValidation:
    def test_maturity_missing_rejected(self) -> None:
        spec = _minimal_spec()
        del spec["maturity"]
        with pytest.raises(ValueError):
            load_rule_spec(spec)

    def test_maturity_non_string_rejected(self) -> None:
        with pytest.raises(TypeError):
            load_rule_spec(_minimal_spec(maturity=0))

    def test_maturity_empty_string_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_rule_spec(_minimal_spec(maturity=""))

    def test_maturity_whitespace_only_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_rule_spec(_minimal_spec(maturity="   "))

    def test_maturity_surrounding_whitespace_stripped_on_store(self) -> None:
        result = load_rule_spec(_minimal_spec(maturity="  experimental  "))
        assert result.maturity == "experimental"

    def test_maturity_preserved_as_string(self) -> None:
        result = load_rule_spec(_minimal_spec(maturity="experimental"))
        assert result.maturity == "experimental"
        assert isinstance(result.maturity, str)


class TestPriorConfidenceValidation:
    def test_missing_reliability_rejected(self) -> None:
        spec = _minimal_spec()
        del spec["reliability"]
        with pytest.raises(ValueError):
            load_rule_spec(spec)

    def test_missing_prior_confidence_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_rule_spec(_minimal_spec(reliability={}))

    def test_prior_confidence_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_rule_spec(
                _minimal_spec(reliability={"prior_confidence": -0.1})
            )

    def test_prior_confidence_above_one_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_rule_spec(
                _minimal_spec(reliability={"prior_confidence": 1.5})
            )

    def test_prior_confidence_zero_accepted(self) -> None:
        result = load_rule_spec(
            _minimal_spec(reliability={"prior_confidence": 0.0})
        )
        assert result.prior_confidence == ScoreValue(0.0)

    def test_prior_confidence_one_accepted(self) -> None:
        result = load_rule_spec(
            _minimal_spec(reliability={"prior_confidence": 1.0})
        )
        assert result.prior_confidence == ScoreValue(1.0)

    def test_prior_confidence_string_rejected(self) -> None:
        with pytest.raises(TypeError):
            load_rule_spec(
                _minimal_spec(reliability={"prior_confidence": "0.5"})
            )

    def test_reliability_non_mapping_rejected(self) -> None:
        with pytest.raises(TypeError):
            load_rule_spec(_minimal_spec(reliability=[1, 2, 3]))


class TestRawPreservation:
    def test_raw_contains_all_header_fields(self) -> None:
        result = load_rule_spec(_minimal_spec())
        assert result.raw["id"] == "RULE_DOMAIN_SSH_001"
        assert result.raw["version"] == 1
        assert result.raw["maturity"] == "experimental"

    def test_raw_preserves_non_header_fields(self) -> None:
        spec = _minimal_spec()
        spec["domain"] = "security.ssh"
        spec["unknown_field"] = "preserved"
        result = load_rule_spec(spec)
        assert result.raw["domain"] == "security.ssh"
        assert result.raw["unknown_field"] == "preserved"

    def test_raw_is_independent_copy(self) -> None:
        spec = _minimal_spec()
        result = load_rule_spec(spec)
        spec["version"] = 999
        assert result.raw["version"] == 1

    def test_raw_nested_mapping_is_independent_copy(self) -> None:
        """top-level 만이 아니라 nested mapping 도 입력 시점 snapshot 으로 고정."""
        spec = _minimal_spec()
        result = load_rule_spec(spec)
        spec["reliability"]["prior_confidence"] = 0.9
        assert result.raw["reliability"]["prior_confidence"] == 0.5

    def test_raw_preserves_original_id_before_strip(self) -> None:
        """raw 에는 원문 보존 (strip 적용된 canonical 형태는 RuleSpec.id 에만)."""
        spec = _minimal_spec(id="  SSH_001  ")
        result = load_rule_spec(spec)
        assert result.id == "SSH_001"
        assert result.raw["id"] == "  SSH_001  "


class TestRuleSpecImmutability:
    def test_is_frozen(self) -> None:
        result = load_rule_spec(_minimal_spec())
        with pytest.raises(AttributeError):
            result.id = "OTHER"  # type: ignore[misc]


class TestYamlLoader:
    def test_basic_yaml_passes(self) -> None:
        text = """
id: RULE_DOMAIN_SSH_001
version: 1
maturity: experimental
reliability:
  prior_confidence: 0.5
"""
        result = load_rule_spec_from_yaml(text)
        assert result.id == "RULE_DOMAIN_SSH_001"
        assert result.version == 1
        assert result.maturity == "experimental"
        assert result.prior_confidence == ScoreValue(0.5)

    def test_yaml_with_human_label_comment_passes(self) -> None:
        text = """
id: RULE_DOMAIN_SSH_001
version: 1
# human_label: 0.1.0
maturity: experimental
reliability:
  prior_confidence: 0.5
"""
        result = load_rule_spec_from_yaml(text)
        assert result.version == 1

    def test_yaml_version_semver_string_rejected(self) -> None:
        text = """
id: RULE_DOMAIN_SSH_001
version: "0.1.0"
maturity: experimental
reliability:
  prior_confidence: 0.5
"""
        with pytest.raises(TypeError):
            load_rule_spec_from_yaml(text)

    def test_yaml_non_mapping_root_rejected(self) -> None:
        with pytest.raises(TypeError):
            load_rule_spec_from_yaml("[1, 2, 3]")

    def test_yaml_extra_fields_preserved_in_raw(self) -> None:
        text = """
id: RULE_DOMAIN_SSH_001
version: 1
maturity: experimental
domain: security.ssh
author: core
reliability:
  prior_confidence: 0.5
"""
        result = load_rule_spec_from_yaml(text)
        assert result.raw["domain"] == "security.ssh"
        assert result.raw["author"] == "core"

    def test_yaml_returns_rule_spec_instance(self) -> None:
        text = """
id: X
version: 1
maturity: experimental
reliability:
  prior_confidence: 0.5
"""
        result = load_rule_spec_from_yaml(text)
        assert isinstance(result, RuleSpec)


# =====================================================================
# compile_rule_condition — bridge from RuleSpec to ConditionTree
# =====================================================================

class TestCompileRuleCondition:
    def test_returns_predicate_for_single_predicate_condition(self) -> None:
        spec_dict = _minimal_spec()
        spec_dict["condition"] = {"field": "port", "op": "eq", "value": 22}
        spec = load_rule_spec(spec_dict)
        tree = compile_rule_condition(spec)
        assert isinstance(tree, Predicate)
        assert tree.field == "port"

    def test_returns_combinator_for_all_condition(self) -> None:
        spec_dict = _minimal_spec()
        spec_dict["condition"] = {
            "all": [
                {"field": "port", "op": "eq", "value": 22},
                {"field": "protocol", "op": "eq", "value": "tcp"},
            ]
        }
        spec = load_rule_spec(spec_dict)
        tree = compile_rule_condition(spec)
        assert isinstance(tree, Combinator)
        assert tree.kind == "all"
        assert len(tree.children) == 2

    def test_missing_condition_rejected(self) -> None:
        """RuleSpec 에 condition 없으면 compile_rule_condition 이 ValueError."""
        spec = load_rule_spec(_minimal_spec())  # condition 미포함
        with pytest.raises(ValueError):
            compile_rule_condition(spec)

    def test_malformed_combinator_propagates_type_error(self) -> None:
        spec_dict = _minimal_spec()
        spec_dict["condition"] = {"all": "not a list"}
        spec = load_rule_spec(spec_dict)
        with pytest.raises(TypeError):
            compile_rule_condition(spec)

    def test_unknown_op_in_condition_propagates_value_error(self) -> None:
        spec_dict = _minimal_spec()
        spec_dict["condition"] = {
            "field": "port", "op": "unknown_op", "value": 22
        }
        spec = load_rule_spec(spec_dict)
        with pytest.raises(ValueError):
            compile_rule_condition(spec)

    def test_predicate_extra_key_in_condition_propagates_value_error(self) -> None:
        spec_dict = _minimal_spec()
        spec_dict["condition"] = {
            "field": "port", "op": "eq", "value": 22, "typo": "x"
        }
        spec = load_rule_spec(spec_dict)
        with pytest.raises(ValueError):
            compile_rule_condition(spec)


class TestEndToEndSshScenario:
    """YAML → RuleSpec → compile_rule_condition → evaluate_condition full chain."""

    SSH_YAML = """
id: RULE_DOMAIN_SSH_001
version: 1
maturity: experimental
reliability:
  prior_confidence: 0.55
condition:
  all:
    - field: port
      op: eq
      value: 22
    - field: protocol
      op: eq
      value: tcp
    - field: service
      op: eq
      value: ssh
    - field: banner
      op: contains
      value: "OpenSSH_7."
"""

    def _compile(self) -> object:
        spec = load_rule_spec_from_yaml(self.SSH_YAML)
        return compile_rule_condition(spec)

    def test_match(self) -> None:
        tree = self._compile()
        ctx = {
            "port": 22,
            "protocol": "tcp",
            "service": "ssh",
            "banner": "OpenSSH_7.4p1",
        }
        assert evaluate_condition(tree, ctx) is True

    def test_banner_mismatch(self) -> None:
        tree = self._compile()
        ctx = {
            "port": 22,
            "protocol": "tcp",
            "service": "ssh",
            "banner": "OpenSSH_9.0p1",
        }
        assert evaluate_condition(tree, ctx) is False

    def test_banner_missing(self) -> None:
        """Lenient: 누락 field → predicate false → all false."""
        tree = self._compile()
        ctx = {"port": 22, "protocol": "tcp", "service": "ssh"}
        assert evaluate_condition(tree, ctx) is False

    def test_spec_metadata_preserved_alongside_compiled_tree(self) -> None:
        """compile_rule_condition 은 RuleSpec 을 mutate 하지 않음."""
        spec = load_rule_spec_from_yaml(self.SSH_YAML)
        _ = compile_rule_condition(spec)
        assert spec.id == "RULE_DOMAIN_SSH_001"
        assert spec.version == 1
        assert spec.prior_confidence == ScoreValue(0.55)
        assert "condition" in spec.raw  # raw 보존
