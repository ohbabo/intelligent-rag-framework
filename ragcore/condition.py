"""Structured condition tree loader + evaluator.

Two-stage design (per docs/contracts/05 §10):

    raw dict
      ↓ load_condition_tree(raw)
    ConditionTree (Predicate | Combinator)
      ↓ evaluate_condition(tree, context)
    bool

- Load 단계: 구조 검증, operator/combinator allowlist 확인. 잘못된 모양은 예외.
- Eval 단계: 평가는 lenient. 데이터 누락/타입 불일치는 false 로 흘리고
  예외 던지지 않음. "왜 false 인가" 는 다음 단계의 evaluator trace 책임.

Scope: 헤더 검증 + 평가.
Out of scope: not 콤비네이터, nested field (dot notation), regex,
arithmetic, custom functions, 문자열 DSL, trace/explainability.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

VALID_OPS = frozenset({"eq", "ne", "lt", "le", "gt", "ge", "contains"})
NUMERIC_OPS = frozenset({"lt", "le", "gt", "ge"})
VALID_COMBINATORS = frozenset({"all", "any"})
REJECTED_COMBINATORS = frozenset({"not"})  # 명시적 deferral
PREDICATE_KEYS = frozenset({"field", "op", "value"})


@dataclass(frozen=True)
class Predicate:
    field: str
    op: str
    value: Any


@dataclass(frozen=True)
class Combinator:
    kind: str  # "all" or "any"
    children: tuple[Any, ...]  # tuple[ConditionTree, ...] — recursive alias


ConditionTree = Predicate | Combinator


# =====================================================================
# Load — structural validation
# =====================================================================

def load_condition_tree(raw: Mapping[str, Any]) -> ConditionTree:
    """Validate condition structure and produce a typed tree.

    Raises:
        TypeError: raw 가 mapping 아님 / op 가 str 아님 / 자식이 list 아님 등 타입 문제.
        ValueError: 누락 필드 / 알 수 없는 op / 미지원 combinator / 잘못된 노드 형태.
    """
    if not isinstance(raw, Mapping):
        raise TypeError(
            f"condition node must be mapping, got {type(raw).__name__}"
        )

    keys = set(raw.keys())

    rejected = keys & REJECTED_COMBINATORS
    if rejected:
        raise ValueError(
            f"combinator(s) not allowed in MVP: {sorted(rejected)}"
        )

    predicate_shape_keys = PREDICATE_KEYS & keys
    combinator_keys = keys & VALID_COMBINATORS

    if predicate_shape_keys and combinator_keys:
        raise ValueError(
            f"node cannot mix predicate and combinator; keys: {sorted(keys)}"
        )

    if combinator_keys:
        if len(combinator_keys) > 1:
            raise ValueError(
                f"combinator node must have exactly one of all/any, "
                f"got {sorted(combinator_keys)}"
            )
        kind = next(iter(combinator_keys))
        extras = keys - {kind}
        if extras:
            raise ValueError(
                f"combinator '{kind}' node has unexpected extra keys: "
                f"{sorted(extras)}"
            )
        return _load_combinator(raw, kind)

    if not (PREDICATE_KEYS <= keys):
        missing = PREDICATE_KEYS - keys
        raise ValueError(
            f"node is neither predicate (missing fields: {sorted(missing)}) "
            f"nor known combinator (got keys: {sorted(keys)})"
        )

    extras = keys - PREDICATE_KEYS
    if extras:
        raise ValueError(
            f"predicate node has unexpected extra keys: {sorted(extras)}"
        )

    return _load_predicate(raw)


def _load_predicate(raw: Mapping[str, Any]) -> Predicate:
    field = raw["field"]
    op = raw["op"]
    value = raw["value"]

    if not isinstance(field, str):
        raise TypeError(
            f"predicate.field must be string, got {type(field).__name__}"
        )
    field_stripped = field.strip()
    if not field_stripped:
        raise ValueError("predicate.field must be non-empty")

    if not isinstance(op, str):
        raise TypeError(
            f"predicate.op must be string, got {type(op).__name__}"
        )
    if op not in VALID_OPS:
        raise ValueError(
            f"unknown operator: {op!r}. Allowed: {sorted(VALID_OPS)}"
        )

    return Predicate(field=field_stripped, op=op, value=value)


def _load_combinator(raw: Mapping[str, Any], kind: str) -> Combinator:
    children_raw = raw[kind]
    if not isinstance(children_raw, list):
        raise TypeError(
            f"combinator '{kind}' value must be list, "
            f"got {type(children_raw).__name__}"
        )
    children = tuple(load_condition_tree(child) for child in children_raw)
    return Combinator(kind=kind, children=children)


# =====================================================================
# Evaluate — lenient evaluation against flat context
# =====================================================================

def evaluate_condition(
    tree: ConditionTree, context: Mapping[str, Any]
) -> bool:
    """Evaluate condition against a flat context dict.

    Lenient semantics:
    - field 누락 → predicate false
    - type mismatch (numeric op 가 non-number 받음 등) → predicate false
    - empty all → true (vacuous)
    - empty any → false
    """
    if isinstance(tree, Predicate):
        return _evaluate_predicate(tree, context)
    if isinstance(tree, Combinator):
        return _evaluate_combinator(tree, context)
    raise TypeError(f"unexpected tree node type: {type(tree).__name__}")


def _evaluate_predicate(pred: Predicate, context: Mapping[str, Any]) -> bool:
    if pred.field not in context:
        return False

    actual = context[pred.field]
    expected = pred.value
    op = pred.op

    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op in NUMERIC_OPS:
        if not _is_numeric(actual) or not _is_numeric(expected):
            return False
        if op == "lt":
            return actual < expected
        if op == "le":
            return actual <= expected
        if op == "gt":
            return actual > expected
        if op == "ge":
            return actual >= expected
    if op == "contains":
        return _evaluate_contains(actual, expected)

    # Validated at load time, shouldn't reach.
    raise ValueError(f"unknown op at eval time: {op!r}")


def _is_numeric(value: Any) -> bool:
    """int or float, but explicitly NOT bool.

    Python 에서 bool 은 int 의 subclass 라 isinstance(True, int) == True.
    Numeric 비교에서 True 를 1 처럼 다루지 않게 명시적으로 차단.
    """
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float))


def _evaluate_contains(actual: Any, expected: Any) -> bool:
    """contains: str 의 substring 또는 list/tuple 의 membership. 그 외 false."""
    if isinstance(actual, str):
        if not isinstance(expected, str):
            return False
        return expected in actual
    if isinstance(actual, (list, tuple)):
        return expected in actual
    return False


def _evaluate_combinator(comb: Combinator, context: Mapping[str, Any]) -> bool:
    if comb.kind == "all":
        return all(evaluate_condition(child, context) for child in comb.children)
    if comb.kind == "any":
        return any(evaluate_condition(child, context) for child in comb.children)
    raise ValueError(f"unknown combinator kind at eval time: {comb.kind!r}")
