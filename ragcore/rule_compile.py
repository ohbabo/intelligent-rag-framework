"""Compile RuleSpec (string id/maturity) → RuleDefinition (uint16 id, uint8 maturity).

Static mapping table approach (docs/contracts/05 §12).

- 새 룰 추가: ``RULE_ID_MAP`` 에 한 줄 추가, PR review 에서 충돌 검토.
- Unknown string → ``ValueError`` (compile time).
- 매핑 무결성 (범위 / 중복) → ``AssertionError`` (모듈 로딩 시).

Scope:
- 문자열 → core 정수 매핑만.
- Engine.register_rule 자동 호출, output claim 파싱, condition compile
  등은 모두 별도 결정점.
"""

from __future__ import annotations

from collections.abc import Mapping

from ragcore.rule_loader import RuleSpec
from ragcore.types import (
    RULE_MATURITY_DEPRECATED,
    RULE_MATURITY_EXPERIMENTAL,
    RULE_MATURITY_STABLE,
    RuleDefinition,
)

RULE_ID_MIN = 1
RULE_ID_MAX = 65535


RULE_ID_MAP: dict[str, int] = {
    "RULE_DOMAIN_SSH_001": 1,
    # 새 룰: 다음 안 쓴 정수를 PR 에서 한 줄 추가하고 review 로 충돌 검토
}


RULE_MATURITY_MAP: dict[str, int] = {
    "experimental": RULE_MATURITY_EXPERIMENTAL,
    "stable": RULE_MATURITY_STABLE,
    "deprecated": RULE_MATURITY_DEPRECATED,
}


def _validate_rule_id_map(mapping: Mapping[str, int]) -> None:
    """Static integrity check for a RULE_ID_MAP-shaped mapping.

    Module load time 에 호출돼 corruption 을 즉시 발견시킨다.

    Raises:
        AssertionError: key 가 빈 문자열, value 가 int 아님 (bool 포함),
            value 가 [1, 65535] 범위 밖, 또는 중복 value 존재.
    """
    for name, value in mapping.items():
        if not isinstance(name, str) or not name.strip():
            raise AssertionError("rule id map keys must be non-empty strings")
        # bool is int subclass — exclude explicitly.
        if isinstance(value, bool) or not isinstance(value, int):
            raise AssertionError(
                f"rule id for {name!r} must be int, got {type(value).__name__}"
            )
        if not (RULE_ID_MIN <= value <= RULE_ID_MAX):
            raise AssertionError(
                f"rule id for {name!r} out of range "
                f"[{RULE_ID_MIN}, {RULE_ID_MAX}]: {value}"
            )

    values = list(mapping.values())
    if len(values) != len(set(values)):
        raise AssertionError("duplicate rule id values in mapping")


def compile_rule_definition(spec: RuleSpec) -> RuleDefinition:
    """Compile a header-validated ``RuleSpec`` into a ``RuleDefinition``.

    Lookup-only — Engine 등록도, condition/output 컴파일도 안 한다.

    Raises:
        ValueError: ``spec.id`` 가 ``RULE_ID_MAP`` 에 없거나
            ``spec.maturity`` 가 ``RULE_MATURITY_MAP`` 에 없을 때.
    """
    if spec.id not in RULE_ID_MAP:
        raise ValueError(f"unknown rule id: {spec.id!r}")
    if spec.maturity not in RULE_MATURITY_MAP:
        raise ValueError(f"unknown maturity: {spec.maturity!r}")

    return RuleDefinition(
        id=RULE_ID_MAP[spec.id],
        version=spec.version,
        maturity=RULE_MATURITY_MAP[spec.maturity],
        prior_confidence=spec.prior_confidence,
    )


# 모듈 로딩 시 즉시 검증 — RULE_ID_MAP 손상은 import 시점에 발견.
_validate_rule_id_map(RULE_ID_MAP)
