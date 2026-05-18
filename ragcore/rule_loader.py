"""YAML rule spec loader.

Reads rule definition YAML (or already-parsed dict) and validates the header.
Scope: ``yaml/dict → RuleSpec`` validation only.

Out of scope (deferred to later steps):
- compile id (string) → RuleId (uint16)
- map maturity (string) → RuleMaturity (uint8)
- parse condition / output / required_evidence
- register with Engine

Validation rules (see docs/contracts/05 §8.3):
- id: required, non-empty str
- version: required, int (not bool, not str), 1..65535
- maturity: required, non-empty str
- reliability.prior_confidence: required, number in [0.0, 1.0]
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ragcore.condition import ConditionTree, load_condition_tree
from ragcore.types import ScoreValue

VERSION_MIN = 1
VERSION_MAX = 65535


@dataclass(frozen=True)
class RuleSpec:
    """Validated header of a rule definition.

    ``id`` 와 ``maturity`` 는 이 단계에서 문자열로 보존된다 —
    RuleId / RuleMaturity 의 정수 매핑은 별도 결정점이다.

    ``raw`` 는 입력 dict 의 복사본으로, header 외 필드 (condition,
    output, domain, author 등) 가 다음 단계에서 접근 가능하도록
    보존된다.
    """

    id: str
    version: int
    maturity: str
    prior_confidence: ScoreValue
    raw: dict[str, Any]


def load_rule_spec(data: Mapping[str, Any]) -> RuleSpec:
    """Validate a parsed rule spec mapping and produce a ``RuleSpec``.

    이미 파싱된 dict 든, YAML 에서 온 dict 든 동일하게 받는다. 외부
    의존성 (PyYAML) 이 없어도 단독 사용 가능.
    """
    _require_field(data, "id")
    _require_field(data, "version")
    _require_field(data, "maturity")
    _require_field(data, "reliability")

    id_val = data["id"]
    if not isinstance(id_val, str):
        raise TypeError(f"id must be string, got {type(id_val).__name__}")
    id_stripped = id_val.strip()
    if not id_stripped:
        raise ValueError("id must be non-empty string (whitespace-only rejected)")

    version_val = data["version"]
    # bool is a subclass of int in Python — exclude explicitly.
    if isinstance(version_val, bool) or not isinstance(version_val, int):
        raise TypeError(
            f"version must be int (not string, not bool), "
            f"got {type(version_val).__name__}"
        )
    if not (VERSION_MIN <= version_val <= VERSION_MAX):
        raise ValueError(
            f"version must be in [{VERSION_MIN}, {VERSION_MAX}], "
            f"got {version_val}"
        )

    maturity_val = data["maturity"]
    if not isinstance(maturity_val, str):
        raise TypeError(
            f"maturity must be string, got {type(maturity_val).__name__}"
        )
    maturity_stripped = maturity_val.strip()
    if not maturity_stripped:
        raise ValueError(
            "maturity must be non-empty string (whitespace-only rejected)"
        )

    reliability = data["reliability"]
    if not isinstance(reliability, Mapping):
        raise TypeError(
            f"reliability must be mapping, "
            f"got {type(reliability).__name__}"
        )
    if "prior_confidence" not in reliability:
        raise ValueError("missing required field: reliability.prior_confidence")

    prior = reliability["prior_confidence"]
    if isinstance(prior, bool) or not isinstance(prior, (int, float)):
        raise TypeError(
            f"reliability.prior_confidence must be number, "
            f"got {type(prior).__name__}"
        )
    # ScoreValue 가 [0.0, 1.0] 범위 검증

    # id / maturity 는 strip 된 canonical 형태로 저장. raw 에는 원문 보존
    # (deepcopy 로 nested mapping 도 입력 시점 snapshot 으로 고정).
    return RuleSpec(
        id=id_stripped,
        version=version_val,
        maturity=maturity_stripped,
        prior_confidence=ScoreValue(float(prior)),
        raw=deepcopy(dict(data)),
    )


def load_rule_spec_from_yaml(text: str) -> RuleSpec:
    """Parse YAML text and produce a validated ``RuleSpec``."""
    import yaml

    data = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        raise TypeError(
            f"yaml root must be a mapping, got {type(data).__name__}"
        )
    return load_rule_spec(data)


def _require_field(data: Mapping[str, Any], name: str) -> None:
    if name not in data:
        raise ValueError(f"missing required field: {name}")


def compile_rule_condition(spec: RuleSpec) -> ConditionTree:
    """Extract and compile the condition block from a ``RuleSpec``.

    Bridges header loader (``RuleSpec``) ↔ condition tree (``ConditionTree``).
    ``spec.raw["condition"]`` 에서 dict 를 꺼내 ``load_condition_tree`` 로
    변환한다. ``RuleSpec`` 구조 자체는 건드리지 않음 — header loader 의
    책임 경계 유지.

    Raises:
        ValueError: condition 블록 누락 또는 구조 문제 (allowlist 위반 등).
        TypeError: condition 노드의 타입 문제 (mapping 아님 등).
    """
    if "condition" not in spec.raw:
        raise ValueError("missing required field: condition")
    return load_condition_tree(spec.raw["condition"])
