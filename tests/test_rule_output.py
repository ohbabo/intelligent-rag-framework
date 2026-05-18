"""Tests for ragcore.rule_output — claim output template compile.

Coverage:
- valid output → RuleOutputTemplate
- type/status/reason_code 매핑 확인 (3개 상태 전부 포함)
- base_confidence 경계값 / 범위 위반 / 타입 거부
- 필수 필드 누락 거부 (output/output.claim/4개 sub-field)
- unknown type/status/reason_code 거부
- 비-문자열 type/status/reason_code 거부
- broader-intent 필드 silent ignore (subject, evidence_strength, required_evidence)
- 매핑 무결성 (production data)
- _validate_uint16_map / _validate_claim_status_map helper
- YAML → RuleSpec → RuleOutputTemplate end-to-end
"""

from __future__ import annotations

from typing import Any

import pytest

from ragcore import RuleOutputTemplate, ScoreValue, compile_rule_output
from ragcore.rule_loader import RuleSpec, load_rule_spec, load_rule_spec_from_yaml
from ragcore.rule_output import (
    CLAIM_STATUS_MAP,
    CLAIM_TYPE_MAP,
    REASON_CODE_MAP,
    _validate_claim_status_map,
    _validate_uint16_map,
)
from ragcore.types import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_REFUTED,
)


def _spec_with_output(**claim_overrides: Any) -> RuleSpec:
    """Valid spec dict 에 claim_overrides 적용 후 RuleSpec 로 반환."""
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


def _spec_without_claim_field(field: str) -> RuleSpec:
    spec_dict: dict[str, Any] = {
        "id": "RULE_DOMAIN_SSH_001",
        "version": 1,
        "maturity": "experimental",
        "reliability": {"prior_confidence": 0.5},
        "output": {"claim": {
            "type": "outdated_ssh_candidate",
            "status": "candidate",
            "base_confidence": 0.55,
            "reason_code": "OPENSSH_7_SERIES_BANNER",
        }},
    }
    del spec_dict["output"]["claim"][field]
    return load_rule_spec(spec_dict)


# =====================================================================
# Basic compile
# =====================================================================

class TestCompileBasic:
    def test_returns_template(self) -> None:
        template = compile_rule_output(_spec_with_output())
        assert isinstance(template, RuleOutputTemplate)
        assert template.claim_type == 1
        assert template.status == CLAIM_STATUS_CANDIDATE
        assert template.base_confidence == ScoreValue(0.55)
        assert template.reason_code == 1


class TestStatusMapping:
    def test_candidate(self) -> None:
        assert (
            compile_rule_output(_spec_with_output(status="candidate")).status
            == CLAIM_STATUS_CANDIDATE
        )

    def test_confirmed(self) -> None:
        assert (
            compile_rule_output(_spec_with_output(status="confirmed")).status
            == CLAIM_STATUS_CONFIRMED
        )

    def test_refuted(self) -> None:
        assert (
            compile_rule_output(_spec_with_output(status="refuted")).status
            == CLAIM_STATUS_REFUTED
        )


class TestBaseConfidence:
    def test_zero_accepted(self) -> None:
        template = compile_rule_output(
            _spec_with_output(base_confidence=0.0)
        )
        assert template.base_confidence == ScoreValue(0.0)

    def test_one_accepted(self) -> None:
        template = compile_rule_output(
            _spec_with_output(base_confidence=1.0)
        )
        assert template.base_confidence == ScoreValue(1.0)

    def test_arbitrary_value(self) -> None:
        template = compile_rule_output(
            _spec_with_output(base_confidence=0.72)
        )
        assert template.base_confidence.value == pytest.approx(0.72)

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            compile_rule_output(_spec_with_output(base_confidence=-0.1))

    def test_above_one_rejected(self) -> None:
        with pytest.raises(ValueError):
            compile_rule_output(_spec_with_output(base_confidence=1.1))

    def test_string_rejected(self) -> None:
        with pytest.raises(TypeError):
            compile_rule_output(_spec_with_output(base_confidence="0.5"))

    def test_bool_rejected(self) -> None:
        with pytest.raises(TypeError):
            compile_rule_output(_spec_with_output(base_confidence=True))

    def test_list_rejected(self) -> None:
        with pytest.raises(TypeError):
            compile_rule_output(_spec_with_output(base_confidence=[0.5]))


class TestMissingRequiredFields:
    def test_missing_type(self) -> None:
        with pytest.raises(ValueError, match="output.claim.type"):
            compile_rule_output(_spec_without_claim_field("type"))

    def test_missing_status(self) -> None:
        with pytest.raises(ValueError, match="output.claim.status"):
            compile_rule_output(_spec_without_claim_field("status"))

    def test_missing_base_confidence(self) -> None:
        with pytest.raises(ValueError, match="output.claim.base_confidence"):
            compile_rule_output(_spec_without_claim_field("base_confidence"))

    def test_missing_reason_code(self) -> None:
        with pytest.raises(ValueError, match="output.claim.reason_code"):
            compile_rule_output(_spec_without_claim_field("reason_code"))

    def test_missing_output(self) -> None:
        spec = load_rule_spec({
            "id": "RULE_DOMAIN_SSH_001",
            "version": 1,
            "maturity": "experimental",
            "reliability": {"prior_confidence": 0.5},
        })
        with pytest.raises(ValueError, match=r"^missing required field: output$"):
            compile_rule_output(spec)

    def test_missing_output_claim(self) -> None:
        spec = load_rule_spec({
            "id": "RULE_DOMAIN_SSH_001",
            "version": 1,
            "maturity": "experimental",
            "reliability": {"prior_confidence": 0.5},
            "output": {},
        })
        with pytest.raises(ValueError, match="output.claim"):
            compile_rule_output(spec)


class TestUnknownMappings:
    def test_unknown_type(self) -> None:
        with pytest.raises(ValueError, match="unknown claim type"):
            compile_rule_output(_spec_with_output(type="totally_made_up"))

    def test_unknown_status(self) -> None:
        with pytest.raises(ValueError, match="unknown claim status"):
            compile_rule_output(_spec_with_output(status="alpha"))

    def test_unknown_reason_code(self) -> None:
        with pytest.raises(ValueError, match="unknown reason code"):
            compile_rule_output(_spec_with_output(reason_code="WHAT"))


class TestFieldTypes:
    def test_type_non_string_rejected(self) -> None:
        with pytest.raises(TypeError):
            compile_rule_output(_spec_with_output(type=1))

    def test_status_non_string_rejected(self) -> None:
        with pytest.raises(TypeError):
            compile_rule_output(_spec_with_output(status=0))

    def test_reason_code_non_string_rejected(self) -> None:
        with pytest.raises(TypeError):
            compile_rule_output(_spec_with_output(reason_code=1))


class TestStructuralTypes:
    def test_output_non_mapping_rejected(self) -> None:
        spec = load_rule_spec({
            "id": "RULE_DOMAIN_SSH_001",
            "version": 1,
            "maturity": "experimental",
            "reliability": {"prior_confidence": 0.5},
            "output": "not a mapping",
        })
        with pytest.raises(TypeError, match="output must be mapping"):
            compile_rule_output(spec)

    def test_output_claim_non_mapping_rejected(self) -> None:
        spec = load_rule_spec({
            "id": "RULE_DOMAIN_SSH_001",
            "version": 1,
            "maturity": "experimental",
            "reliability": {"prior_confidence": 0.5},
            "output": {"claim": "not a mapping"},
        })
        with pytest.raises(TypeError, match="output.claim must be mapping"):
            compile_rule_output(spec)


class TestExtraFieldsIgnored:
    """§9 SSH_001 broader-intent 필드는 silent ignore."""

    def test_subject_ignored(self) -> None:
        template = compile_rule_output(
            _spec_with_output(subject="service:ssh")
        )
        assert template.claim_type == 1

    def test_evidence_strength_ignored(self) -> None:
        template = compile_rule_output(
            _spec_with_output(evidence_strength=0.4)
        )
        assert template.base_confidence == ScoreValue(0.55)

    def test_required_evidence_ignored(self) -> None:
        template = compile_rule_output(
            _spec_with_output(
                required_evidence=["exact_openssh_version", "os_family"]
            )
        )
        assert template.claim_type == 1

    def test_full_ssh_001_style_passes(self) -> None:
        """§9 SSH_001 예시 형태 그대로 (subject + evidence_strength + required_evidence)."""
        template = compile_rule_output(_spec_with_output(
            subject="service:ssh",
            evidence_strength=0.4,
            required_evidence=["exact_openssh_version", "os_family"],
        ))
        assert template.claim_type == 1
        assert template.status == CLAIM_STATUS_CANDIDATE
        assert template.base_confidence == ScoreValue(0.55)
        assert template.reason_code == 1


class TestImmutability:
    def test_template_is_frozen(self) -> None:
        template = compile_rule_output(_spec_with_output())
        with pytest.raises(AttributeError):
            template.claim_type = 99  # type: ignore[misc]


# =====================================================================
# Production map integrity
# =====================================================================

class TestClaimTypeMapIntegrity:
    def test_no_duplicate_values(self) -> None:
        values = list(CLAIM_TYPE_MAP.values())
        assert len(values) == len(set(values))

    def test_values_in_range(self) -> None:
        for name, value in CLAIM_TYPE_MAP.items():
            assert 1 <= value <= 65535, f"{name}={value} out of range"


class TestReasonCodeMapIntegrity:
    def test_no_duplicate_values(self) -> None:
        values = list(REASON_CODE_MAP.values())
        assert len(values) == len(set(values))

    def test_values_in_range(self) -> None:
        for name, value in REASON_CODE_MAP.items():
            assert 1 <= value <= 65535, f"{name}={value} out of range"


class TestClaimStatusMapIntegrity:
    def test_only_known_status_values(self) -> None:
        allowed = {
            CLAIM_STATUS_CANDIDATE,
            CLAIM_STATUS_CONFIRMED,
            CLAIM_STATUS_REFUTED,
        }
        for name, value in CLAIM_STATUS_MAP.items():
            assert value in allowed, f"{name}={value} not in allowed set"

    def test_all_three_statuses_present(self) -> None:
        values = set(CLAIM_STATUS_MAP.values())
        assert values == {
            CLAIM_STATUS_CANDIDATE,
            CLAIM_STATUS_CONFIRMED,
            CLAIM_STATUS_REFUTED,
        }


# =====================================================================
# Validation helpers
# =====================================================================

class TestValidateUint16Map:
    def test_valid_passes(self) -> None:
        _validate_uint16_map({"A": 1, "B": 65535}, "test")

    def test_empty_passes(self) -> None:
        _validate_uint16_map({}, "test")

    def test_zero_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_uint16_map({"A": 0}, "test")

    def test_negative_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_uint16_map({"A": -1}, "test")

    def test_above_max_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_uint16_map({"A": 65536}, "test")

    def test_duplicate_value_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_uint16_map({"A": 1, "B": 1}, "test")

    def test_empty_key_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_uint16_map({"": 1}, "test")

    def test_whitespace_key_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_uint16_map({"   ": 1}, "test")

    def test_bool_value_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_uint16_map({"A": True}, "test")  # type: ignore[dict-item]


class TestValidateClaimStatusMap:
    def test_valid_passes(self) -> None:
        _validate_claim_status_map({
            "a": CLAIM_STATUS_CANDIDATE,
            "b": CLAIM_STATUS_CONFIRMED,
            "c": CLAIM_STATUS_REFUTED,
        })

    def test_empty_passes(self) -> None:
        _validate_claim_status_map({})

    def test_out_of_allowed_set_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_claim_status_map({"weird": 99})

    def test_bool_value_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_claim_status_map({"A": True})  # type: ignore[dict-item]

    def test_duplicate_value_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_claim_status_map({
                "a": CLAIM_STATUS_CANDIDATE,
                "b": CLAIM_STATUS_CANDIDATE,
            })

    def test_empty_key_rejected(self) -> None:
        with pytest.raises(AssertionError):
            _validate_claim_status_map({"": CLAIM_STATUS_CANDIDATE})

    def test_status_zero_allowed(self) -> None:
        """CANDIDATE=0 은 valid — uint16 1..65535 검증과 분리되어야 함."""
        _validate_claim_status_map({"candidate": CLAIM_STATUS_CANDIDATE})


# =====================================================================
# End-to-end YAML → RuleOutputTemplate
# =====================================================================

class TestEndToEnd:
    BASIC_YAML = """
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

    BROADER_INTENT_YAML = """
id: RULE_DOMAIN_SSH_001
version: 1
maturity: experimental
reliability:
  prior_confidence: 0.55
output:
  claim:
    type: outdated_ssh_candidate
    subject: service:ssh
    status: candidate
    base_confidence: 0.55
    evidence_strength: 0.40
    reason_code: OPENSSH_7_SERIES_BANNER
    required_evidence:
      - exact_openssh_version
      - os_family
"""

    def test_basic_yaml_to_template(self) -> None:
        spec = load_rule_spec_from_yaml(self.BASIC_YAML)
        template = compile_rule_output(spec)
        assert template.claim_type == 1
        assert template.status == CLAIM_STATUS_CANDIDATE
        assert template.base_confidence == ScoreValue(0.55)
        assert template.reason_code == 1

    def test_broader_intent_yaml_passes(self) -> None:
        """§9 SSH_001 yaml 형태 그대로 compile 통과 (extras ignored)."""
        spec = load_rule_spec_from_yaml(self.BROADER_INTENT_YAML)
        template = compile_rule_output(spec)
        assert template.claim_type == 1
        assert template.status == CLAIM_STATUS_CANDIDATE
        assert template.base_confidence == ScoreValue(0.55)
        assert template.reason_code == 1

    def test_spec_not_mutated(self) -> None:
        spec = load_rule_spec_from_yaml(self.BROADER_INTENT_YAML)
        _ = compile_rule_output(spec)
        # spec.raw 의 output.claim 에는 여전히 broader-intent 필드 보존됨
        assert "subject" in spec.raw["output"]["claim"]
        assert "evidence_strength" in spec.raw["output"]["claim"]
        assert "required_evidence" in spec.raw["output"]["claim"]
