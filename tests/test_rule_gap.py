"""Tests for ragcore.rule_gap — required_evidence compile (§14).

Coverage:
- 누락 / 빈 list / null → empty tuple
- 단일 / 다중 entry → 매핑된 정수 tuple
- 순서 보존
- 중복 보존 (MVP 는 dedup 안 함)
- unknown evidence type → ValueError
- non-list / non-string entry → TypeError
- output block 자체 누락 → empty tuple
- RequiredEvidenceTemplate frozen
- REQUIRED_EVIDENCE_MAP 무결성
- 상수 (GAP_TYPE_MISSING_EVIDENCE, DEFAULT_GAP_SEVERITY)
- _validate_uint16_map helper
- YAML → RuleSpec → RequiredEvidenceTemplate end-to-end
"""

from __future__ import annotations

from typing import Any

import pytest

from ragcore import RuleSpec, ScoreValue
from ragcore.rule_gap import (
    DEFAULT_GAP_SEVERITY,
    GAP_TYPE_MISSING_EVIDENCE,
    REQUIRED_EVIDENCE_MAP,
    RequiredEvidenceTemplate,
    _validate_uint16_map,
    compile_required_evidence,
)
from ragcore.rule_loader import load_rule_spec, load_rule_spec_from_yaml


def _spec_with(**claim_overrides: Any) -> RuleSpec:
    """Valid spec; claim_overrides 로 output.claim 의 필드를 추가/덮어쓰기."""
    claim_block: dict[str, Any] = {
        "type": "outdated_ssh_candidate",
        "status": "candidate",
        "base_confidence": 0.55,
        "reason_code": "OPENSSH_7_SERIES_BANNER",
    }
    claim_block.update(claim_overrides)
    spec_dict = {
        "id": "RULE_DOMAIN_SSH_001",
        "version": 1,
        "maturity": "experimental",
        "reliability": {"prior_confidence": 0.5},
        "output": {"claim": claim_block},
    }
    return load_rule_spec(spec_dict)


def _spec_no_output() -> RuleSpec:
    return load_rule_spec({
        "id": "RULE_DOMAIN_SSH_001",
        "version": 1,
        "maturity": "experimental",
        "reliability": {"prior_confidence": 0.5},
    })


# =====================================================================
# Basic compile — missing / empty / null / values
# =====================================================================

class TestCompileBasic:
    def test_missing_required_evidence_returns_empty(self) -> None:
        """output.claim 에 required_evidence 키 자체가 없을 때."""
        template = compile_required_evidence(_spec_with())
        assert template.evidence_types == ()

    def test_empty_list_returns_empty(self) -> None:
        template = compile_required_evidence(_spec_with(required_evidence=[]))
        assert template.evidence_types == ()

    def test_null_value_treated_as_empty(self) -> None:
        """YAML `required_evidence: null` 또는 explicit Python None."""
        template = compile_required_evidence(
            _spec_with(required_evidence=None)
        )
        assert template.evidence_types == ()

    def test_single_entry(self) -> None:
        template = compile_required_evidence(
            _spec_with(required_evidence=["exact_openssh_version"])
        )
        assert template.evidence_types == (1,)

    def test_three_entries(self) -> None:
        template = compile_required_evidence(
            _spec_with(required_evidence=[
                "exact_openssh_version",
                "os_family",
                "package_backport_status",
            ])
        )
        assert template.evidence_types == (1, 2, 3)


# =====================================================================
# Order + dedup behavior (MVP: preserve both)
# =====================================================================

class TestOrderAndDedup:
    def test_order_preserved(self) -> None:
        template = compile_required_evidence(
            _spec_with(required_evidence=[
                "os_family",
                "exact_openssh_version",
                "package_backport_status",
            ])
        )
        assert template.evidence_types == (2, 1, 3)

    def test_duplicates_preserved(self) -> None:
        """MVP — dedup 안 함. yaml 에 두 번 → 결과도 두 번."""
        template = compile_required_evidence(
            _spec_with(required_evidence=["os_family", "os_family"])
        )
        assert template.evidence_types == (2, 2)


# =====================================================================
# No-output handling (graceful)
# =====================================================================

class TestNoOutput:
    def test_no_output_block_returns_empty(self) -> None:
        template = compile_required_evidence(_spec_no_output())
        assert template.evidence_types == ()


# =====================================================================
# Error paths
# =====================================================================

class TestErrors:
    def test_unknown_evidence_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown evidence type"):
            compile_required_evidence(
                _spec_with(required_evidence=["never_heard_of"])
            )

    def test_non_list_required_evidence_rejected(self) -> None:
        with pytest.raises(
            TypeError, match="required_evidence must be list"
        ):
            compile_required_evidence(
                _spec_with(required_evidence="not a list")
            )

    def test_non_string_element_rejected(self) -> None:
        with pytest.raises(
            TypeError, match="required_evidence entry must be string"
        ):
            compile_required_evidence(
                _spec_with(required_evidence=[123])
            )

    def test_mixed_valid_invalid_rejected_at_invalid(self) -> None:
        """첫 valid + 둘째 invalid → invalid 에서 raise."""
        with pytest.raises(ValueError):
            compile_required_evidence(
                _spec_with(required_evidence=[
                    "os_family",
                    "totally_invalid",
                ])
            )

    def test_bool_element_rejected(self) -> None:
        """bool 도 string 아니라서 거부."""
        with pytest.raises(TypeError):
            compile_required_evidence(
                _spec_with(required_evidence=[True])
            )


# =====================================================================
# Template immutability
# =====================================================================

class TestTemplateImmutability:
    def test_frozen(self) -> None:
        template = compile_required_evidence(
            _spec_with(required_evidence=["os_family"])
        )
        with pytest.raises(AttributeError):
            template.evidence_types = (99,)  # type: ignore[misc]


# =====================================================================
# Production map integrity
# =====================================================================

class TestRequiredEvidenceMapIntegrity:
    def test_no_duplicate_values(self) -> None:
        values = list(REQUIRED_EVIDENCE_MAP.values())
        assert len(values) == len(set(values))

    def test_values_in_range(self) -> None:
        for name, value in REQUIRED_EVIDENCE_MAP.items():
            assert 1 <= value <= 65535, f"{name}={value} out of range"

    def test_known_ssh_evidence_present(self) -> None:
        for required in (
            "exact_openssh_version",
            "os_family",
            "package_backport_status",
        ):
            assert required in REQUIRED_EVIDENCE_MAP


# =====================================================================
# Constants
# =====================================================================

class TestConstants:
    def test_gap_type_missing_evidence_is_one(self) -> None:
        assert GAP_TYPE_MISSING_EVIDENCE == 1

    def test_default_gap_severity_is_score_value(self) -> None:
        assert isinstance(DEFAULT_GAP_SEVERITY, ScoreValue)
        assert DEFAULT_GAP_SEVERITY.value == 0.5


# =====================================================================
# Validation helper
# =====================================================================

class TestValidateUint16Map:
    def test_valid_passes(self) -> None:
        _validate_uint16_map({"A": 1, "B": 65535}, "test")

    def test_empty_passes(self) -> None:
        _validate_uint16_map({}, "test")

    def test_zero_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_uint16_map({"A": 0}, "test")

    def test_above_max_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_uint16_map({"A": 65536}, "test")

    def test_duplicate_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_uint16_map({"A": 1, "B": 1}, "test")

    def test_empty_key_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_uint16_map({"": 1}, "test")

    def test_bool_value_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_uint16_map({"A": True}, "test")  # type: ignore[dict-item]


# =====================================================================
# End-to-end YAML → RequiredEvidenceTemplate
# =====================================================================

class TestEndToEndYaml:
    def test_yaml_with_required_evidence(self) -> None:
        yaml_text = """
id: RULE_DOMAIN_SSH_001
version: 1
maturity: experimental
reliability:
  prior_confidence: 0.55
output:
  claim:
    type: outdated_ssh_candidate
    status: candidate
    base_confidence: 0.55
    reason_code: OPENSSH_7_SERIES_BANNER
    required_evidence:
      - exact_openssh_version
      - os_family
      - package_backport_status
"""
        spec = load_rule_spec_from_yaml(yaml_text)
        template = compile_required_evidence(spec)
        assert template.evidence_types == (1, 2, 3)

    def test_yaml_without_required_evidence(self) -> None:
        yaml_text = """
id: RULE_DOMAIN_SSH_001
version: 1
maturity: experimental
reliability:
  prior_confidence: 0.55
output:
  claim:
    type: outdated_ssh_candidate
    status: candidate
    base_confidence: 0.55
    reason_code: OPENSSH_7_SERIES_BANNER
"""
        spec = load_rule_spec_from_yaml(yaml_text)
        template = compile_required_evidence(spec)
        assert template.evidence_types == ()

    def test_yaml_with_explicit_null(self) -> None:
        yaml_text = """
id: RULE_DOMAIN_SSH_001
version: 1
maturity: experimental
reliability:
  prior_confidence: 0.55
output:
  claim:
    type: outdated_ssh_candidate
    status: candidate
    base_confidence: 0.55
    reason_code: OPENSSH_7_SERIES_BANNER
    required_evidence: null
"""
        spec = load_rule_spec_from_yaml(yaml_text)
        template = compile_required_evidence(spec)
        assert template.evidence_types == ()
