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
from ragcore.rule_loader import (
    RuleSpec,
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
