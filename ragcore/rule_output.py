"""Compile rule output claim template (docs/contracts/05 §13).

YAML ``output.claim`` → ``RuleOutputTemplate`` (정수 매핑된 frozen dataclass).

Static mapping table approach (§12 패턴):

- ``CLAIM_TYPE_MAP`` / ``REASON_CODE_MAP``: uint16 1..65535 (0 reserved)
- ``CLAIM_STATUS_MAP``: allowed values ``{CANDIDATE, CONFIRMED, REFUTED}``

Out-of-scope fields are silently ignored (parser 가 안 봄):

- ``output.claim.subject`` — entity resolver 결정점 분리, fire_rule 호출자 책임
- ``output.claim.required_evidence`` — Gap 결정점 (17차)
- ``output.claim.evidence_strength`` — Claim 슬롯 없음, 별도 evidence 흐름
- 다중 claim, ``reason_code`` list, dynamic interpolation
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ragcore.rule_loader import RuleSpec
from ragcore.types import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_REFUTED,
    ScoreValue,
)


CLAIM_TYPE_MAP: dict[str, int] = {
    "outdated_ssh_candidate": 1,
    # 새 claim type: PR review 로 충돌 검토 후 한 줄 추가
}

CLAIM_STATUS_MAP: dict[str, int] = {
    "candidate": CLAIM_STATUS_CANDIDATE,
    "confirmed": CLAIM_STATUS_CONFIRMED,
    "refuted":   CLAIM_STATUS_REFUTED,
}

REASON_CODE_MAP: dict[str, int] = {
    "OPENSSH_7_SERIES_BANNER": 1,
    "SSH_PORT_OPEN":           2,
    # 새 reason code: PR review 로 충돌 검토 후 한 줄 추가
}


_UINT16_MIN = 1
_UINT16_MAX = 65535

_ALLOWED_CLAIM_STATUSES = frozenset({
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_REFUTED,
})


@dataclass(frozen=True)
class RuleOutputTemplate:
    """Compiled output claim template.

    fire_rule 시점에 호출자가 ``subject_id`` 와 함께
    ``engine.add_claim`` 호출에 사용한다.
    """

    claim_type: int
    status: int
    base_confidence: ScoreValue
    reason_code: int


def compile_rule_output(spec: RuleSpec) -> RuleOutputTemplate:
    """``spec.raw["output"]["claim"]`` → ``RuleOutputTemplate``.

    Out-of-scope fields (subject / evidence_strength / required_evidence
    등) 는 무시 — §9 SSH_001 broader-intent yaml 과의 호환성 유지.

    Raises:
        ValueError: 필수 필드 누락 / 알 수 없는 type/status/reason_code /
            base_confidence 범위 위반.
        TypeError: output 블록이 mapping 아님 / 필드 타입이 잘못됨.
    """
    raw = spec.raw
    if "output" not in raw:
        raise ValueError("missing required field: output")
    output_block = raw["output"]
    if not isinstance(output_block, Mapping):
        raise TypeError(
            f"output must be mapping, got {type(output_block).__name__}"
        )
    if "claim" not in output_block:
        raise ValueError("missing required field: output.claim")
    claim_block = output_block["claim"]
    if not isinstance(claim_block, Mapping):
        raise TypeError(
            f"output.claim must be mapping, got {type(claim_block).__name__}"
        )

    for required in ("type", "status", "base_confidence", "reason_code"):
        if required not in claim_block:
            raise ValueError(
                f"missing required field: output.claim.{required}"
            )

    claim_type = _lookup_str(
        claim_block, "type", CLAIM_TYPE_MAP, "claim type"
    )
    status = _lookup_str(
        claim_block, "status", CLAIM_STATUS_MAP, "claim status"
    )
    reason_code = _lookup_str(
        claim_block, "reason_code", REASON_CODE_MAP, "reason code"
    )

    bc = claim_block["base_confidence"]
    if isinstance(bc, bool) or not isinstance(bc, (int, float)):
        raise TypeError(
            f"output.claim.base_confidence must be number, "
            f"got {type(bc).__name__}"
        )

    return RuleOutputTemplate(
        claim_type=claim_type,
        status=status,
        base_confidence=ScoreValue(float(bc)),
        reason_code=reason_code,
    )


def _lookup_str(
    block: Mapping[str, object],
    field: str,
    mapping: Mapping[str, int],
    label: str,
) -> int:
    value = block[field]
    if not isinstance(value, str):
        raise TypeError(
            f"output.claim.{field} must be string, "
            f"got {type(value).__name__}"
        )
    if value not in mapping:
        raise ValueError(f"unknown {label}: {value!r}")
    return mapping[value]


def _validate_uint16_map(mapping: Mapping[str, int], label: str) -> None:
    """For ``CLAIM_TYPE_MAP`` / ``REASON_CODE_MAP`` — values must be 1..65535."""
    for name, value in mapping.items():
        if not isinstance(name, str) or not name.strip():
            raise AssertionError(f"{label} keys must be non-empty strings")
        if isinstance(value, bool) or not isinstance(value, int):
            raise AssertionError(
                f"{label} value for {name!r} must be int, "
                f"got {type(value).__name__}"
            )
        if not (_UINT16_MIN <= value <= _UINT16_MAX):
            raise AssertionError(
                f"{label} value for {name!r} out of range "
                f"[{_UINT16_MIN}, {_UINT16_MAX}]: {value}"
            )
    values = list(mapping.values())
    if len(values) != len(set(values)):
        raise AssertionError(f"duplicate values in {label}")


def _validate_claim_status_map(mapping: Mapping[str, int]) -> None:
    """``CLAIM_STATUS_MAP`` — values must be in allowed status constants set.

    `uint16 1..65535` 검증과 별개 — status 는 0 (candidate) 도 valid 이고
    값이 사전 정의 상수 집합 안에 있어야 함.
    """
    for name, value in mapping.items():
        if not isinstance(name, str) or not name.strip():
            raise AssertionError(
                "CLAIM_STATUS_MAP keys must be non-empty strings"
            )
        if isinstance(value, bool) or not isinstance(value, int):
            raise AssertionError(
                f"CLAIM_STATUS_MAP value for {name!r} must be int, "
                f"got {type(value).__name__}"
            )
        if value not in _ALLOWED_CLAIM_STATUSES:
            raise AssertionError(
                f"CLAIM_STATUS_MAP value for {name!r} not in allowed set "
                f"{sorted(_ALLOWED_CLAIM_STATUSES)}: {value}"
            )
    values = list(mapping.values())
    if len(values) != len(set(values)):
        raise AssertionError("duplicate values in CLAIM_STATUS_MAP")


# 모듈 로딩 시 정적 검증 — 매핑 손상은 import 시점에 발견
_validate_uint16_map(CLAIM_TYPE_MAP, "CLAIM_TYPE_MAP")
_validate_uint16_map(REASON_CODE_MAP, "REASON_CODE_MAP")
_validate_claim_status_map(CLAIM_STATUS_MAP)
