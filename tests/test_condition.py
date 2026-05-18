"""Tests for ragcore.condition — structured condition tree loader + evaluator.

Coverage:
- Load: predicate / combinator 구조 검증, 잘못된 모양 거부
- Evaluate: lenient (missing/type mismatch → false), all/any 의미, vacuous truth
- SSH_001 시나리오 end-to-end
"""

from __future__ import annotations

from typing import Any

import pytest

from ragcore.condition import (
    TRACE_REASON_MATCH,
    TRACE_REASON_MISMATCH,
    TRACE_REASON_MISSING_FIELD,
    TRACE_REASON_TYPE_MISMATCH,
    Combinator,
    CombinatorTrace,
    Predicate,
    PredicateTrace,
    evaluate_condition,
    evaluate_condition_with_trace,
    load_condition_tree,
)


def _pred(field: str, op: str, value: Any) -> dict[str, Any]:
    return {"field": field, "op": op, "value": value}


# =====================================================================
# Load — Predicate
# =====================================================================

class TestLoadPredicate:
    def test_basic_predicate(self) -> None:
        tree = load_condition_tree(_pred("port", "eq", 22))
        assert isinstance(tree, Predicate)
        assert tree.field == "port"
        assert tree.op == "eq"
        assert tree.value == 22

    def test_field_stripped(self) -> None:
        tree = load_condition_tree(_pred("  port  ", "eq", 22))
        assert tree.field == "port"

    def test_field_missing_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_condition_tree({"op": "eq", "value": 22})

    def test_op_missing_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_condition_tree({"field": "port", "value": 22})

    def test_value_missing_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_condition_tree({"field": "port", "op": "eq"})

    def test_unknown_op_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_condition_tree(_pred("port", "unknown_op", 22))

    def test_field_non_string_rejected(self) -> None:
        with pytest.raises(TypeError):
            load_condition_tree(_pred(123, "eq", 22))  # type: ignore[arg-type]

    def test_op_non_string_rejected(self) -> None:
        with pytest.raises(TypeError):
            load_condition_tree({"field": "port", "op": 1, "value": 22})

    def test_field_empty_string_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_condition_tree(_pred("", "eq", 22))

    def test_field_whitespace_only_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_condition_tree(_pred("   ", "eq", 22))

    def test_predicate_is_frozen(self) -> None:
        tree = load_condition_tree(_pred("port", "eq", 22))
        assert isinstance(tree, Predicate)
        with pytest.raises(AttributeError):
            tree.field = "other"  # type: ignore[misc]


# =====================================================================
# Load — Combinator
# =====================================================================

class TestLoadCombinator:
    def test_all_with_predicates(self) -> None:
        tree = load_condition_tree({
            "all": [
                _pred("port", "eq", 22),
                _pred("protocol", "eq", "tcp"),
            ]
        })
        assert isinstance(tree, Combinator)
        assert tree.kind == "all"
        assert len(tree.children) == 2

    def test_any_with_predicates(self) -> None:
        tree = load_condition_tree({
            "any": [
                _pred("port", "eq", 22),
                _pred("port", "eq", 2222),
            ]
        })
        assert isinstance(tree, Combinator)
        assert tree.kind == "any"

    def test_empty_all_allowed_at_load(self) -> None:
        tree = load_condition_tree({"all": []})
        assert isinstance(tree, Combinator)
        assert tree.children == ()

    def test_empty_any_allowed_at_load(self) -> None:
        tree = load_condition_tree({"any": []})
        assert isinstance(tree, Combinator)

    def test_nested_combinator(self) -> None:
        tree = load_condition_tree({
            "all": [
                _pred("port", "eq", 22),
                {"any": [
                    _pred("service", "eq", "ssh"),
                    _pred("service", "eq", "sshd"),
                ]},
            ]
        })
        assert isinstance(tree, Combinator)
        assert tree.kind == "all"
        assert isinstance(tree.children[1], Combinator)
        assert tree.children[1].kind == "any"

    def test_combinator_is_frozen(self) -> None:
        tree = load_condition_tree({"all": []})
        with pytest.raises(AttributeError):
            tree.kind = "any"  # type: ignore[misc]


class TestLoadInvalidShape:
    def test_all_and_any_same_node_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_condition_tree({
                "all": [_pred("port", "eq", 22)],
                "any": [_pred("service", "eq", "ssh")],
            })

    def test_combinator_mixed_with_predicate_rejected(self) -> None:
        """all + field + op + value 가 한 노드에 같이 있는 경우."""
        with pytest.raises(ValueError):
            load_condition_tree({
                "field": "port", "op": "eq", "value": 22,
                "any": [_pred("service", "eq", "ssh")],
            })

    def test_combinator_value_non_list_rejected(self) -> None:
        with pytest.raises(TypeError):
            load_condition_tree({"all": "not a list"})

    def test_not_combinator_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_condition_tree({"not": _pred("port", "eq", 22)})

    def test_non_mapping_root_rejected(self) -> None:
        with pytest.raises(TypeError):
            load_condition_tree([1, 2, 3])  # type: ignore[arg-type]

    def test_unknown_root_keys_rejected(self) -> None:
        with pytest.raises(ValueError):
            load_condition_tree({"xor": [_pred("port", "eq", 22)]})

    def test_predicate_extra_key_rejected(self) -> None:
        """predicate 노드는 정확히 {field, op, value} 만 허용 — 오타 차단."""
        with pytest.raises(ValueError):
            load_condition_tree({
                "field": "port", "op": "eq", "value": 22, "typo": "x"
            })

    def test_combinator_extra_key_rejected(self) -> None:
        """combinator 노드는 정확히 {all} 또는 {any} 만 — 추가 키 거부."""
        with pytest.raises(ValueError):
            load_condition_tree({
                "all": [_pred("port", "eq", 22)],
                "unexpected": True,
            })

    def test_top_level_predicate_allowed_per_contract(self) -> None:
        """단일 조건 룰을 위해 top-level predicate 허용 (per §10)."""
        tree = load_condition_tree(_pred("port", "eq", 22))
        assert isinstance(tree, Predicate)


# =====================================================================
# Evaluate — basic ops
# =====================================================================

class TestEvaluateEq:
    def test_int_eq_true(self) -> None:
        tree = load_condition_tree(_pred("port", "eq", 22))
        assert evaluate_condition(tree, {"port": 22}) is True

    def test_int_eq_false(self) -> None:
        tree = load_condition_tree(_pred("port", "eq", 22))
        assert evaluate_condition(tree, {"port": 80}) is False

    def test_string_eq_true(self) -> None:
        tree = load_condition_tree(_pred("protocol", "eq", "tcp"))
        assert evaluate_condition(tree, {"protocol": "tcp"}) is True

    def test_string_eq_false(self) -> None:
        tree = load_condition_tree(_pred("protocol", "eq", "tcp"))
        assert evaluate_condition(tree, {"protocol": "udp"}) is False


class TestEvaluateNe:
    def test_ne_true(self) -> None:
        tree = load_condition_tree(_pred("port", "ne", 22))
        assert evaluate_condition(tree, {"port": 80}) is True

    def test_ne_false(self) -> None:
        tree = load_condition_tree(_pred("port", "ne", 22))
        assert evaluate_condition(tree, {"port": 22}) is False


# =====================================================================
# Evaluate — numeric ops (lt/le/gt/ge)
# =====================================================================

class TestEvaluateNumeric:
    def test_lt_true(self) -> None:
        tree = load_condition_tree(_pred("port", "lt", 1024))
        assert evaluate_condition(tree, {"port": 22}) is True

    def test_lt_boundary_false(self) -> None:
        tree = load_condition_tree(_pred("port", "lt", 22))
        assert evaluate_condition(tree, {"port": 22}) is False

    def test_le_inclusive(self) -> None:
        tree = load_condition_tree(_pred("port", "le", 22))
        assert evaluate_condition(tree, {"port": 22}) is True

    def test_gt_true(self) -> None:
        tree = load_condition_tree(_pred("port", "gt", 1024))
        assert evaluate_condition(tree, {"port": 8080}) is True

    def test_ge_inclusive(self) -> None:
        tree = load_condition_tree(_pred("port", "ge", 22))
        assert evaluate_condition(tree, {"port": 22}) is True

    def test_numeric_on_string_returns_false(self) -> None:
        """type mismatch → false (lenient)"""
        tree = load_condition_tree(_pred("port", "lt", 1024))
        assert evaluate_condition(tree, {"port": "22"}) is False

    def test_actual_bool_not_treated_as_numeric(self) -> None:
        """Python에서 True == 1 이지만, numeric op 에서는 bool 차단."""
        tree = load_condition_tree(_pred("flag", "lt", 2))
        assert evaluate_condition(tree, {"flag": True}) is False

    def test_expected_bool_not_treated_as_numeric(self) -> None:
        tree = load_condition_tree(_pred("port", "lt", True))
        assert evaluate_condition(tree, {"port": 0}) is False

    def test_float_comparison(self) -> None:
        tree = load_condition_tree(_pred("ratio", "ge", 0.5))
        assert evaluate_condition(tree, {"ratio": 0.7}) is True

    def test_int_vs_float_comparison(self) -> None:
        tree = load_condition_tree(_pred("port", "lt", 100.0))
        assert evaluate_condition(tree, {"port": 22}) is True


# =====================================================================
# Evaluate — contains
# =====================================================================

class TestEvaluateContains:
    def test_string_substring_true(self) -> None:
        tree = load_condition_tree(
            _pred("banner", "contains", "OpenSSH_7.")
        )
        assert evaluate_condition(tree, {"banner": "OpenSSH_7.4p1"}) is True

    def test_string_substring_false(self) -> None:
        tree = load_condition_tree(
            _pred("banner", "contains", "OpenSSH_8.")
        )
        assert evaluate_condition(tree, {"banner": "OpenSSH_7.4p1"}) is False

    def test_list_membership_true(self) -> None:
        tree = load_condition_tree(_pred("ports", "contains", 22))
        assert evaluate_condition(tree, {"ports": [22, 80, 443]}) is True

    def test_list_membership_false(self) -> None:
        tree = load_condition_tree(_pred("ports", "contains", 8080))
        assert evaluate_condition(tree, {"ports": [22, 80, 443]}) is False

    def test_tuple_membership_true(self) -> None:
        tree = load_condition_tree(_pred("ports", "contains", 22))
        assert evaluate_condition(tree, {"ports": (22, 80)}) is True

    def test_contains_string_with_non_string_expected_false(self) -> None:
        tree = load_condition_tree(_pred("banner", "contains", 22))
        assert evaluate_condition(tree, {"banner": "OpenSSH"}) is False

    def test_contains_on_int_returns_false(self) -> None:
        tree = load_condition_tree(_pred("port", "contains", 2))
        assert evaluate_condition(tree, {"port": 22}) is False


# =====================================================================
# Evaluate — missing field
# =====================================================================

class TestEvaluateMissingField:
    def test_missing_field_returns_false(self) -> None:
        tree = load_condition_tree(_pred("port", "eq", 22))
        assert evaluate_condition(tree, {"protocol": "tcp"}) is False

    def test_missing_field_does_not_raise(self) -> None:
        tree = load_condition_tree(_pred("nonexistent", "eq", 22))
        # 예외 없이 false 반환
        assert evaluate_condition(tree, {}) is False


# =====================================================================
# Evaluate — combinators
# =====================================================================

class TestEvaluateCombinator:
    def test_all_true_when_all_children_true(self) -> None:
        tree = load_condition_tree({
            "all": [
                _pred("port", "eq", 22),
                _pred("protocol", "eq", "tcp"),
            ]
        })
        assert evaluate_condition(tree, {"port": 22, "protocol": "tcp"}) is True

    def test_all_false_when_one_child_false(self) -> None:
        tree = load_condition_tree({
            "all": [
                _pred("port", "eq", 22),
                _pred("protocol", "eq", "tcp"),
            ]
        })
        assert evaluate_condition(tree, {"port": 22, "protocol": "udp"}) is False

    def test_any_true_when_one_child_true(self) -> None:
        tree = load_condition_tree({
            "any": [
                _pred("port", "eq", 22),
                _pred("port", "eq", 2222),
            ]
        })
        assert evaluate_condition(tree, {"port": 22}) is True

    def test_any_false_when_all_children_false(self) -> None:
        tree = load_condition_tree({
            "any": [
                _pred("port", "eq", 22),
                _pred("port", "eq", 2222),
            ]
        })
        assert evaluate_condition(tree, {"port": 80}) is False

    def test_empty_all_is_vacuously_true(self) -> None:
        tree = load_condition_tree({"all": []})
        assert evaluate_condition(tree, {}) is True

    def test_empty_any_is_false(self) -> None:
        tree = load_condition_tree({"any": []})
        assert evaluate_condition(tree, {}) is False

    def test_nested_combinator_true(self) -> None:
        tree = load_condition_tree({
            "all": [
                _pred("port", "eq", 22),
                {"any": [
                    _pred("service", "eq", "ssh"),
                    _pred("service", "eq", "sshd"),
                ]},
            ]
        })
        assert evaluate_condition(
            tree, {"port": 22, "service": "sshd"}
        ) is True

    def test_nested_combinator_false(self) -> None:
        tree = load_condition_tree({
            "all": [
                _pred("port", "eq", 22),
                {"any": [
                    _pred("service", "eq", "ssh"),
                    _pred("service", "eq", "sshd"),
                ]},
            ]
        })
        assert evaluate_condition(
            tree, {"port": 22, "service": "telnet"}
        ) is False


# =====================================================================
# Evaluate — RULE_DOMAIN_SSH_001 end-to-end scenario (docs/contracts/05 §9)
# =====================================================================

class TestEvaluateSshScenario:
    def _ssh_outdated_tree(self) -> object:
        return load_condition_tree({
            "all": [
                _pred("port", "eq", 22),
                _pred("protocol", "eq", "tcp"),
                _pred("service", "eq", "ssh"),
                _pred("banner", "contains", "OpenSSH_7."),
            ]
        })

    def test_ssh_outdated_match(self) -> None:
        ctx = {
            "port": 22,
            "protocol": "tcp",
            "service": "ssh",
            "banner": "OpenSSH_7.4p1",
        }
        assert evaluate_condition(self._ssh_outdated_tree(), ctx) is True

    def test_ssh_outdated_banner_mismatch(self) -> None:
        ctx = {
            "port": 22,
            "protocol": "tcp",
            "service": "ssh",
            "banner": "OpenSSH_9.0p1",
        }
        assert evaluate_condition(self._ssh_outdated_tree(), ctx) is False

    def test_ssh_outdated_missing_banner(self) -> None:
        """banner 누락 → predicate false → all false (lenient)."""
        ctx = {
            "port": 22,
            "protocol": "tcp",
            "service": "ssh",
        }
        assert evaluate_condition(self._ssh_outdated_tree(), ctx) is False


# =====================================================================
# Trace — explain layer (per §11)
# =====================================================================

class TestTracePredicateMatch:
    def test_eq_match(self) -> None:
        tree = load_condition_tree(_pred("port", "eq", 22))
        trace = evaluate_condition_with_trace(tree, {"port": 22})
        assert isinstance(trace, PredicateTrace)
        assert trace.field == "port"
        assert trace.op == "eq"
        assert trace.expected == 22
        assert trace.actual == 22
        assert trace.actual_present is True
        assert trace.result is True
        assert trace.reason == TRACE_REASON_MATCH

    def test_contains_match(self) -> None:
        tree = load_condition_tree(_pred("banner", "contains", "OpenSSH_7."))
        trace = evaluate_condition_with_trace(
            tree, {"banner": "OpenSSH_7.4p1"}
        )
        assert trace.result is True
        assert trace.reason == TRACE_REASON_MATCH


class TestTracePredicateMismatch:
    def test_eq_mismatch(self) -> None:
        tree = load_condition_tree(_pred("port", "eq", 22))
        trace = evaluate_condition_with_trace(tree, {"port": 80})
        assert trace.result is False
        assert trace.reason == TRACE_REASON_MISMATCH
        assert trace.actual == 80
        assert trace.actual_present is True

    def test_numeric_mismatch(self) -> None:
        tree = load_condition_tree(_pred("port", "lt", 22))
        trace = evaluate_condition_with_trace(tree, {"port": 100})
        assert trace.result is False
        assert trace.reason == TRACE_REASON_MISMATCH

    def test_contains_mismatch(self) -> None:
        tree = load_condition_tree(_pred("banner", "contains", "OpenSSH_8."))
        trace = evaluate_condition_with_trace(
            tree, {"banner": "OpenSSH_7.4"}
        )
        assert trace.result is False
        assert trace.reason == TRACE_REASON_MISMATCH


class TestTraceMissingField:
    def test_missing_field(self) -> None:
        tree = load_condition_tree(_pred("port", "eq", 22))
        trace = evaluate_condition_with_trace(tree, {})
        assert trace.result is False
        assert trace.reason == TRACE_REASON_MISSING_FIELD
        assert trace.actual is None
        assert trace.actual_present is False

    def test_explicit_none_distinguished_from_missing(self) -> None:
        """context = {"x": None} 는 missing 이 아님 — actual_present=True."""
        tree = load_condition_tree(_pred("x", "eq", None))
        trace = evaluate_condition_with_trace(tree, {"x": None})
        assert trace.actual is None
        assert trace.actual_present is True
        assert trace.result is True
        assert trace.reason == TRACE_REASON_MATCH

    def test_explicit_none_ne_other(self) -> None:
        tree = load_condition_tree(_pred("x", "eq", 22))
        trace = evaluate_condition_with_trace(tree, {"x": None})
        assert trace.actual is None
        assert trace.actual_present is True
        assert trace.result is False
        assert trace.reason == TRACE_REASON_MISMATCH


class TestTraceTypeMismatch:
    def test_numeric_op_on_string(self) -> None:
        tree = load_condition_tree(_pred("port", "lt", 1024))
        trace = evaluate_condition_with_trace(tree, {"port": "22"})
        assert trace.result is False
        assert trace.reason == TRACE_REASON_TYPE_MISMATCH

    def test_numeric_op_on_bool(self) -> None:
        tree = load_condition_tree(_pred("flag", "lt", 2))
        trace = evaluate_condition_with_trace(tree, {"flag": True})
        assert trace.result is False
        assert trace.reason == TRACE_REASON_TYPE_MISMATCH

    def test_contains_on_int(self) -> None:
        tree = load_condition_tree(_pred("port", "contains", 2))
        trace = evaluate_condition_with_trace(tree, {"port": 22})
        assert trace.result is False
        assert trace.reason == TRACE_REASON_TYPE_MISMATCH

    def test_contains_string_with_non_string_expected(self) -> None:
        tree = load_condition_tree(_pred("banner", "contains", 22))
        trace = evaluate_condition_with_trace(
            tree, {"banner": "OpenSSH"}
        )
        assert trace.result is False
        assert trace.reason == TRACE_REASON_TYPE_MISMATCH


class TestTraceCombinator:
    def test_all_evaluates_all_children(self) -> None:
        """short-circuit 없이 모든 child 가 평가됨 (full eval)."""
        tree = load_condition_tree({
            "all": [
                _pred("port", "eq", 22),
                _pred("protocol", "eq", "tcp"),
                _pred("service", "eq", "ssh"),
            ]
        })
        trace = evaluate_condition_with_trace(tree, {})
        assert isinstance(trace, CombinatorTrace)
        assert trace.kind == "all"
        # 첫 false 에서 멈추지 않고 셋 다 평가됨
        assert len(trace.children) == 3
        for child in trace.children:
            assert child.result is False
            assert child.reason == TRACE_REASON_MISSING_FIELD
        assert trace.result is False

    def test_any_evaluates_all_children(self) -> None:
        """any 도 첫 true 에서 멈추지 않음."""
        tree = load_condition_tree({
            "any": [
                _pred("port", "eq", 22),
                _pred("port", "eq", 2222),
                _pred("port", "eq", 80),
            ]
        })
        trace = evaluate_condition_with_trace(tree, {"port": 22})
        assert isinstance(trace, CombinatorTrace)
        assert len(trace.children) == 3
        assert trace.children[0].result is True
        assert trace.children[1].result is False
        assert trace.children[2].result is False
        assert trace.result is True

    def test_combinator_has_no_reason_field(self) -> None:
        """CombinatorTrace 의 필드는 kind/children/result 만."""
        from dataclasses import fields
        tree = load_condition_tree({"all": []})
        trace = evaluate_condition_with_trace(tree, {})
        assert isinstance(trace, CombinatorTrace)
        names = {f.name for f in fields(trace)}
        assert names == {"kind", "children", "result"}

    def test_empty_all_is_vacuously_true_trace(self) -> None:
        tree = load_condition_tree({"all": []})
        trace = evaluate_condition_with_trace(tree, {})
        assert trace.result is True
        assert trace.children == ()

    def test_empty_any_is_false_trace(self) -> None:
        tree = load_condition_tree({"any": []})
        trace = evaluate_condition_with_trace(tree, {})
        assert trace.result is False
        assert trace.children == ()

    def test_nested_combinator_full_eval(self) -> None:
        tree = load_condition_tree({
            "all": [
                _pred("port", "eq", 22),
                {"any": [
                    _pred("service", "eq", "ssh"),
                    _pred("service", "eq", "sshd"),
                ]},
            ]
        })
        trace = evaluate_condition_with_trace(
            tree, {"port": 22, "service": "telnet"}
        )
        assert trace.result is False
        assert isinstance(trace, CombinatorTrace)
        nested = trace.children[1]
        assert isinstance(nested, CombinatorTrace)
        assert nested.kind == "any"
        assert len(nested.children) == 2  # 첫 false 에서 멈추지 않음


class TestTraceResultMatchesEvaluate:
    """trace.result 는 evaluate_condition 결과와 항상 일치."""

    @pytest.mark.parametrize("ctx", [
        {"port": 22, "banner": "OpenSSH_7.4"},
        {"port": 22, "banner": "OpenSSH_9.0"},
        {"port": 80, "banner": "OpenSSH_7.4"},
        {"port": 22},
        {},
    ])
    def test_results_agree(self, ctx: dict) -> None:
        tree = load_condition_tree({
            "all": [
                _pred("port", "eq", 22),
                _pred("banner", "contains", "OpenSSH_7."),
            ]
        })
        assert (
            evaluate_condition_with_trace(tree, ctx).result
            == evaluate_condition(tree, ctx)
        )


class TestTraceSshScenario:
    SSH_DICT = {
        "all": [
            {"field": "port", "op": "eq", "value": 22},
            {"field": "protocol", "op": "eq", "value": "tcp"},
            {"field": "service", "op": "eq", "value": "ssh"},
            {"field": "banner", "op": "contains", "value": "OpenSSH_7."},
        ]
    }

    def _tree(self) -> object:
        return load_condition_tree(self.SSH_DICT)

    def test_banner_mismatch_trace(self) -> None:
        ctx = {
            "port": 22,
            "protocol": "tcp",
            "service": "ssh",
            "banner": "OpenSSH_9.0p1",
        }
        trace = evaluate_condition_with_trace(self._tree(), ctx)
        assert trace.result is False
        assert trace.children[0].reason == TRACE_REASON_MATCH      # port
        assert trace.children[1].reason == TRACE_REASON_MATCH      # protocol
        assert trace.children[2].reason == TRACE_REASON_MATCH      # service
        assert trace.children[3].reason == TRACE_REASON_MISMATCH   # banner

    def test_banner_missing_trace(self) -> None:
        ctx = {"port": 22, "protocol": "tcp", "service": "ssh"}
        trace = evaluate_condition_with_trace(self._tree(), ctx)
        assert trace.result is False
        assert trace.children[3].reason == TRACE_REASON_MISSING_FIELD
        assert trace.children[3].actual_present is False
        assert trace.children[3].actual is None

    def test_full_match_trace_all_match(self) -> None:
        ctx = {
            "port": 22,
            "protocol": "tcp",
            "service": "ssh",
            "banner": "OpenSSH_7.4p1",
        }
        trace = evaluate_condition_with_trace(self._tree(), ctx)
        assert trace.result is True
        for child in trace.children:
            assert child.reason == TRACE_REASON_MATCH
