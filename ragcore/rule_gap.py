"""Compile rule output's required_evidence list → RequiredEvidenceTemplate (§14).

YAML ``output.claim.required_evidence`` 의 evidence type 문자열 리스트를
정수 매핑된 frozen tuple 로 변환.

Scope (18차):
- 누락 / 빈 리스트 / null → empty tuple
- 각 문자열을 ``REQUIRED_EVIDENCE_MAP`` 으로 lookup
- 순서 보존, 중복 제거 안 함 (MVP)

Out of scope:
- ``fire_rule`` 통합 (19차)
- 실제 ``Gap`` 생성 (engine.add_gap 호출)
- ``Gap`` severity 차별화
- 다양한 GapType
- dedup / merge
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ragcore.rule_loader import RuleSpec
from ragcore.types import ScoreValue


REQUIRED_EVIDENCE_MAP: dict[str, int] = {
    "exact_openssh_version":   1,
    "os_family":               2,
    "package_backport_status": 3,
    # 새 evidence type: PR review 로 충돌 검토 후 한 줄 추가
}

GAP_TYPE_MISSING_EVIDENCE = 1
DEFAULT_GAP_SEVERITY = ScoreValue(0.5)


_UINT16_MIN = 1
_UINT16_MAX = 65535


@dataclass(frozen=True)
class RequiredEvidenceTemplate:
    """Compiled required_evidence list.

    ``evidence_types`` 는 입력 yaml 의 순서를 보존한다. 중복 제거는 안 함
    (MVP) — 같은 evidence type 이 두 번 적혀있으면 결과도 두 번. dedup 은
    별도 결정점.
    """

    evidence_types: tuple[int, ...]


def compile_required_evidence(spec: RuleSpec) -> RequiredEvidenceTemplate:
    """``spec.raw["output"]["claim"]["required_evidence"]`` → ``RequiredEvidenceTemplate``.

    Lookup-only — runtime 연동 없음. 19차에서 ``fire_rule`` 이 사용.

    Raises:
        TypeError: ``required_evidence`` 가 list 아님, 원소가 string 아님.
        ValueError: 원소가 ``REQUIRED_EVIDENCE_MAP`` 에 없음.
    """
    raw = spec.raw

    # output / output.claim 누락 시 required_evidence 도 없음 → empty.
    output_block = raw.get("output")
    if not isinstance(output_block, Mapping):
        return RequiredEvidenceTemplate(evidence_types=())
    claim_block = output_block.get("claim")
    if not isinstance(claim_block, Mapping):
        return RequiredEvidenceTemplate(evidence_types=())

    if "required_evidence" not in claim_block:
        return RequiredEvidenceTemplate(evidence_types=())

    raw_list = claim_block["required_evidence"]
    # YAML `null` 이면 None — empty 로 다룬다.
    if raw_list is None:
        return RequiredEvidenceTemplate(evidence_types=())
    if not isinstance(raw_list, list):
        raise TypeError(
            f"output.claim.required_evidence must be list, "
            f"got {type(raw_list).__name__}"
        )

    types_list: list[int] = []
    for item in raw_list:
        if not isinstance(item, str):
            raise TypeError(
                f"required_evidence entry must be string, "
                f"got {type(item).__name__}"
            )
        if item not in REQUIRED_EVIDENCE_MAP:
            raise ValueError(f"unknown evidence type: {item!r}")
        types_list.append(REQUIRED_EVIDENCE_MAP[item])

    return RequiredEvidenceTemplate(evidence_types=tuple(types_list))


def _validate_uint16_map(mapping: Mapping[str, int], label: str) -> None:
    """Static integrity check for uint16 1..65535 maps.

    rule_output 의 동명 함수와 같은 패턴. MVP 단계에서는 모듈별 소유.
    """
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


# 모듈 로딩 시 정적 검증 — REQUIRED_EVIDENCE_MAP 손상은 import 시점에 발견
_validate_uint16_map(REQUIRED_EVIDENCE_MAP, "REQUIRED_EVIDENCE_MAP")
