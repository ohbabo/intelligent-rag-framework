"""Tests for PR78-M09 — RuleStats Update Provenance.

Tests-first red gate (280차). These tests lock the approved M09
conceptual contract

  docs/architecture/RULE_STATS_UPDATE_PROVENANCE_CONTRACT.md

as executable requirements for a future consumer-owned example

  examples/operation/rule_stats_update_provenance_example.py

whose single entry point is

  run_rule_stats_update_provenance_example() -> dict[str, Any]

Running these before the 281차 example implementation produces:

  - clean collection (no ImportError / FileNotFoundError /
    SyntaxError at import time — the example is lazy-loaded)
  - exactly one explicit red-gate failure
    (TestImplementationSurface.test_rule_stats_provenance_example_exists)
  - implementation-dependent tests skipped at runtime because the
    example file does not yet exist
  - implementation-independent tests (approved-contract presence,
    M01 / M08 historical preservation, snapshot / structural
    invariants) pass
  - zero unrelated failures across the existing 1806 tests

The example, when later added, is a local illustrative report only.
It is NOT a public ragcore type, a canonical provenance schema, a
snapshot schema, an Engine return type, a cross-consumer wire
format, an authentication record, or a truth / quality verdict.

Class index:
  A. TestImplementationSurface          — entry point + red gate
  B. TestReportBaselineShape            — top-level report shape
  C. TestApprovedContractBoundary       — contract file presence
  D. TestRulePairIdentity               — (rule_id, rule_version)
  E. TestValueChangedCase               — known pair, +1 revision
  F. TestNoValueChangeCase              — known pair, no change
  G. TestRejectedUnknownPairCase        — unknown pair, suppressed
  H. TestSixProvenanceQuestions         — six OC-G meanings
  I. TestCandidateDecisionRequestSeparation — distinct plain dicts
  J. TestStateRevalidation              — Stage 5.5 / Stage 6
  K. TestDirectInvocationBoundary       — AST: no dynamic dispatch
  L. TestSuccessfulReceiptBinding       — before/after reads bound
  M. TestFailedAttemptReceiptBoundary   — no fabricated before/after
  N. TestScoreKeepSetBoundary           — KEEP != SET(0.0); no CLEAR
  O. TestSourceObservationOptionality   — backed vs not-applicable
  P. TestNonAuthorityLocks              — provenance != authority
  Q. TestHistoricalAndSnapshotPreservation — M01 / M08 / snapshot
  R. TestStructuralInvariants           — 42/20 / 50 / 18 / 7
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import typing
from pathlib import Path
from typing import Any

import pytest

import ragcore
from ragcore import Engine, RuleDefinition, RuleStats, ScoreValue


# ---------------------------------------------------------------------------
# Paths and lazy loading
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLE_PATH = (
    _REPO_ROOT
    / "examples"
    / "operation"
    / "rule_stats_update_provenance_example.py"
)
_CONTRACT_PATH = (
    _REPO_ROOT
    / "docs"
    / "architecture"
    / "RULE_STATS_UPDATE_PROVENANCE_CONTRACT.md"
)
_M01_SCAFFOLD_PATH = (
    _REPO_ROOT
    / "examples"
    / "operation"
    / "minimal_operational_scaffold.py"
)
_M08_OPERATION_PATH = (
    _REPO_ROOT
    / "examples"
    / "operation"
    / "complete_domain_neutral_reference_operation.py"
)

_ENTRY_POINT = "run_rule_stats_update_provenance_example"
_OVERALL_STATUS = "RULE_STATS_UPDATE_PROVENANCE_EXAMPLE_COMPLETE"
_CASE_KEYS = ("value_changed", "no_value_change", "rejected_unknown_pair")


def _example_exists() -> bool:
    return _EXAMPLE_PATH.is_file()


def _skip_if_no_example() -> None:
    if not _example_exists():
        pytest.skip(
            "281차 example implementation not yet present "
            f"({_EXAMPLE_PATH.name})",
        )


def _load_example_module():
    """Lazy-load the M09 example via importlib so this file collects
    cleanly even when the example does not yet exist."""
    _skip_if_no_example()
    spec = importlib.util.spec_from_file_location(
        "rule_stats_update_provenance_example", _EXAMPLE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_REPORT_CACHE: dict[str, Any] | None = None


def _get_report() -> dict[str, Any]:
    """Run the example once per session and cache the report."""
    global _REPORT_CACHE
    _skip_if_no_example()
    if _REPORT_CACHE is None:
        module = _load_example_module()
        run = getattr(module, _ENTRY_POINT, None)
        if run is None:
            pytest.skip(f"281차 entry point {_ENTRY_POINT} not yet present")
        _REPORT_CACHE = run()
    return _REPORT_CACHE


def _example_source() -> str:
    _skip_if_no_example()
    return _EXAMPLE_PATH.read_text(encoding="utf-8")


def _case(name: str) -> dict[str, Any]:
    report = _get_report()
    cases = report.get("cases", {})
    assert isinstance(cases, dict), "report['cases'] must be a dict"
    c = cases.get(name)
    assert isinstance(c, dict), f"report['cases'][{name!r}] must be a dict"
    return c


# ---------------------------------------------------------------------------
# Runtime spies (used by implementation-dependent tests; installed only
# for the lifetime of one example run, restored in finally).
# ---------------------------------------------------------------------------

_SPY_METHODS = ("update_rule_stats", "get_rule_stats", "state_identity")


def _install_engine_spies(
    method_names: tuple[str, ...],
) -> tuple[dict[str, int], typing.Callable[[], None]]:
    counts: dict[str, int] = {n: 0 for n in method_names}
    originals: dict[str, Any] = {}
    for name in method_names:
        orig = getattr(Engine, name)
        originals[name] = orig

        def make_spy(orig=orig, name=name):
            def spy(self, *a, **kw):
                counts[name] += 1
                return orig(self, *a, **kw)
            spy.__name__ = name
            spy.__wrapped__ = orig
            return spy

        setattr(Engine, name, make_spy())

    def restore() -> None:
        for name, orig in originals.items():
            setattr(Engine, name, orig)

    return counts, restore


_SPY_CACHE: tuple[dict[str, Any], dict[str, int]] | None = None


def _run_with_spies() -> tuple[dict[str, Any], dict[str, int]]:
    """Run the example once under Engine spies; cache for the session."""
    global _SPY_CACHE
    _skip_if_no_example()
    if _SPY_CACHE is None:
        module = _load_example_module()
        run = getattr(module, _ENTRY_POINT, None)
        if run is None:
            pytest.skip(f"281차 entry point {_ENTRY_POINT} not yet present")
        counts, restore = _install_engine_spies(_SPY_METHODS)
        try:
            report = run()
        finally:
            restore()
        _SPY_CACHE = (report, counts)
    return _SPY_CACHE


def _ast_attr_calls(src: str) -> set[str]:
    """Set of attribute names called as `<x>.<name>(...)` in src."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def _ast_name_calls(src: str) -> set[str]:
    """Set of bare names called as `<name>(...)` in src."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            yield from _walk(x)


def _serialize(obj: Any) -> str:
    if isinstance(obj, dict):
        return "{" + ",".join(
            f"{_serialize(k)}:{_serialize(v)}" for k, v in obj.items()
        ) + "}"
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(_serialize(x) for x in obj) + "]"
    return repr(obj)


def _normalize_engine_tokens(value):
    """Recursively replace every ``engine_token`` field with a fixed
    placeholder so two reports can be compared for structural and
    semantic equality without the per-Engine ``uuid4`` token (which is
    legitimately different on each fresh-Engine run) forcing inequality.
    The real token is left untouched in the reports themselves; only
    the comparison copies are normalized."""
    if isinstance(value, dict):
        return {
            key: (
                "<opaque-engine-token>"
                if key == "engine_token"
                else _normalize_engine_tokens(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_engine_tokens(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_engine_tokens(item) for item in value)
    return value


# ===========================================================================
# A. Implementation surface — entry point + the single explicit red gate
# ===========================================================================


class TestImplementationSurface:

    def test_rule_stats_provenance_example_exists(self):
        """The single explicit red gate. Fails until the 281차 example
        file is added; every other example-dependent test skips."""
        assert _EXAMPLE_PATH.is_file(), (
            "281차 must add "
            "examples/operation/rule_stats_update_provenance_example.py"
        )

    def test_entry_point_present_and_callable(self):
        module = _load_example_module()
        run = getattr(module, _ENTRY_POINT, None)
        assert callable(run), (
            f"example must expose a callable {_ENTRY_POINT}()"
        )

    def test_entry_point_takes_no_required_args(self):
        import inspect
        module = _load_example_module()
        run = getattr(module, _ENTRY_POINT, None)
        if run is None:
            pytest.skip("entry point absent")
        sig = inspect.signature(run)
        required = [
            p for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind in (
                p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD,
            )
        ]
        assert not required, (
            f"{_ENTRY_POINT}() must be callable with no arguments"
        )


# ===========================================================================
# B. Report baseline shape
# ===========================================================================


class TestReportBaselineShape:

    def test_report_is_dict(self):
        assert isinstance(_get_report(), dict)

    def test_overall_status(self):
        assert _get_report().get("overall_status") == _OVERALL_STATUS

    def test_top_level_keys_present(self):
        report = _get_report()
        for key in (
            "overall_status", "cases", "non_authority_locks",
            "snapshot_boundary", "historical_boundary",
        ):
            assert key in report, f"report must carry top-level {key!r}"

    def test_three_cases_present(self):
        cases = _get_report().get("cases", {})
        assert isinstance(cases, dict)
        for name in _CASE_KEYS:
            assert name in cases, f"cases must include {name!r}"

    def test_fresh_report_per_call(self):
        """Each entry-point call must build a fresh report (no module-
        level mutable cache leaking across calls)."""
        module = _load_example_module()
        run = getattr(module, _ENTRY_POINT, None)
        if run is None:
            pytest.skip("entry point absent")
        r1 = run()
        r2 = run()
        # The per-Engine engine_token is a fresh uuid4 on each run and is
        # legitimately recorded in the reports; normalize only the
        # comparison copies so every other structure / value is still
        # required to be equal.
        assert _normalize_engine_tokens(r1) == _normalize_engine_tokens(r2)
        assert r1 is not r2


# ===========================================================================
# C. Approved-contract boundary (implementation-independent)
# ===========================================================================


class TestApprovedContractBoundary:

    def _contract(self) -> str:
        assert _CONTRACT_PATH.is_file(), "approved M09 contract must exist"
        return _CONTRACT_PATH.read_text(encoding="utf-8")

    def test_contract_present(self):
        assert _CONTRACT_PATH.is_file()

    def test_contract_is_docs_only_and_normative(self):
        src = self._contract()
        assert "docs-only architecture contract" in src
        assert "status:  normative" in src

    def test_contract_has_sections_0_through_22(self):
        src = self._contract()
        for n in range(0, 23):
            assert f"## §{n} " in src or f"## §{n}\n" in src, (
                f"contract missing §{n}"
            )

    def test_contract_separates_successful_and_failed_receipt(self):
        src = self._contract()
        assert "§16.1 Successful invocation receipt" in src
        assert "§16.2 Rejected / failed-attempt receipt" in src

    def test_contract_states_m09_overall_open(self):
        # The §22.1 phrase wraps "STARTED /\nOPEN" in the source; match
        # the unambiguous single-line prefix.
        src = self._contract()
        assert "M09 as a whole remains STARTED" in src


# ===========================================================================
# D. Rule pair identity — (rule_id, rule_version) joint
# ===========================================================================


class TestRulePairIdentity:

    @pytest.mark.parametrize("case_name", _CASE_KEYS)
    def test_case_carries_joint_pair(self, case_name):
        c = _case(case_name)
        pair = c.get("pair")
        assert isinstance(pair, dict)
        assert isinstance(pair.get("rule_id"), int)
        assert isinstance(pair.get("rule_version"), int)

    @pytest.mark.parametrize("case_name", _CASE_KEYS)
    def test_candidate_pair_matches_case_pair(self, case_name):
        c = _case(case_name)
        pair = c.get("pair", {})
        cand = c.get("candidate", {})
        assert cand.get("rule_id") == pair.get("rule_id")
        assert cand.get("rule_version") == pair.get("rule_version")


# ===========================================================================
# E. VALUE_CHANGED case
# ===========================================================================


class TestValueChangedCase:

    def _c(self):
        return _case("value_changed")

    def test_actual_effect_value_changed(self):
        receipt = self._c().get("receipt", {})
        assert receipt.get("actual_effect") == "VALUE_CHANGED"

    def test_before_and_after_present_and_differ(self):
        receipt = self._c().get("receipt", {})
        before = receipt.get("rule_stats_before")
        after = receipt.get("rule_stats_after")
        assert before is not None and after is not None
        assert before != after, "VALUE_CHANGED requires before != after"

    def test_revision_advanced_by_one_same_token(self):
        receipt = self._c().get("receipt", {})
        ib = receipt.get("identity_before", {})
        ia = receipt.get("identity_after", {})
        assert ib.get("engine_token") == ia.get("engine_token")
        assert ia.get("revision") == ib.get("revision") + 1

    def test_score_value_passed_as_scorevalue_not_float(self):
        """The observed_precision SET must reach the Engine as a
        ScoreValue, not a bare float."""
        report, _ = _run_with_spies()
        c = report.get("cases", {}).get("value_changed", {})
        args = c.get("receipt", {}).get("reviewed_arguments", {})
        op = args.get("observed_precision")
        assert isinstance(op, ScoreValue), (
            "observed_precision SET must be a ScoreValue in the actual "
            f"reviewed arguments; got {op!r}"
        )


# ===========================================================================
# F. NO_VALUE_CHANGE case
# ===========================================================================


class TestNoValueChangeCase:

    def _c(self):
        return _case("no_value_change")

    def test_actual_effect_no_value_change(self):
        assert self._c().get("receipt", {}).get(
            "actual_effect",
        ) == "NO_VALUE_CHANGE"

    def test_before_equals_after(self):
        receipt = self._c().get("receipt", {})
        assert receipt.get("rule_stats_before") == receipt.get(
            "rule_stats_after",
        )

    def test_identity_unchanged(self):
        receipt = self._c().get("receipt", {})
        assert receipt.get("identity_before") == receipt.get(
            "identity_after",
        )

    def test_effect_not_derived_from_none_return(self):
        """The example must classify NO_VALUE_CHANGE from the public
        before/after reads, not from update_rule_stats' None return.
        Locked by requiring both before==after AND identity equality
        to be recorded (a None-return-only classifier could not
        populate these)."""
        receipt = self._c().get("receipt", {})
        for key in (
            "rule_stats_before", "rule_stats_after",
            "identity_before", "identity_after",
        ):
            assert key in receipt, (
                f"NO_VALUE_CHANGE receipt must record {key!r} so the "
                "classification is read-derived, not return-derived"
            )


# ===========================================================================
# G. REJECTED unknown-pair case
# ===========================================================================


class TestRejectedUnknownPairCase:

    def _c(self):
        return _case("rejected_unknown_pair")

    def test_actual_effect_rejected(self):
        assert self._c().get("receipt", {}).get(
            "actual_effect",
        ) == "REJECTED"

    def test_no_fabricated_before_or_after(self):
        receipt = self._c().get("receipt", {})
        # Either the key is absent or it is explicitly None. A non-None
        # synthetic RuleStats fails.
        assert receipt.get("rule_stats_before") is None
        assert receipt.get("rule_stats_after") is None

    def test_rejection_cause_recorded(self):
        receipt = self._c().get("receipt", {})
        cause = receipt.get("rejection_cause")
        assert cause is not None and _serialize(cause).strip("'\""), (
            "failed-attempt receipt must record a rejection cause"
        )

    def test_not_equated_with_no_value_change(self):
        receipt = self._c().get("receipt", {})
        assert receipt.get("actual_effect") != "NO_VALUE_CHANGE"

    def test_update_not_invoked_for_unknown_pair(self):
        report, counts = _run_with_spies()
        c = report.get("cases", {}).get("rejected_unknown_pair", {})
        assert c.get("receipt", {}).get("update_invoked") is False, (
            "the rejected case must record that update_rule_stats was "
            "not invoked"
        )

    def test_total_update_rule_stats_calls_is_two(self):
        """value_changed + no_value_change invoke update_rule_stats once
        each; the unknown-pair case invokes it zero times."""
        _, counts = _run_with_spies()
        assert counts["update_rule_stats"] == 2, (
            "exactly two successful-path update_rule_stats invocations "
            f"expected across the example; got {counts['update_rule_stats']}"
        )


# ===========================================================================
# H. Six provenance questions (OC-G)
# ===========================================================================


_SIX_PROVENANCE_KEYS = (
    "caller_identity_reference",
    "update_reason",
    "source_observation_references",
    "delta_provenance",
    "precision_input_basis",
    "policy_reference",
)


class TestSixProvenanceQuestions:

    @pytest.mark.parametrize("key", _SIX_PROVENANCE_KEYS)
    def test_value_changed_candidate_has_distinct_provenance_field(
        self, key,
    ):
        cand = _case("value_changed").get("candidate", {})
        assert key in cand, (
            f"observation-backed VALUE_CHANGED candidate must carry a "
            f"distinct {key!r} provenance field (not one merged note)"
        )

    def test_six_meanings_are_independent_keys(self):
        cand = _case("value_changed").get("candidate", {})
        present = [k for k in _SIX_PROVENANCE_KEYS if k in cand]
        assert len(present) == len(_SIX_PROVENANCE_KEYS), (
            "all six provenance meanings must be independently "
            f"identifiable; present={present}"
        )

    def test_caller_reference_not_named_authentication(self):
        """The caller identity must be an opaque reference, not an
        authentication / authorization proof."""
        cand = _case("value_changed").get("candidate", {})
        ref = _serialize(cand.get("caller_identity_reference")).lower()
        for bad in ("password", "auth_token", "bearer", "signature"):
            assert bad not in ref, (
                f"caller_identity_reference must be an opaque reference, "
                f"not an authentication artifact ({bad!r} present)"
            )


# ===========================================================================
# I. Candidate / decision / request separation
# ===========================================================================


class TestCandidateDecisionRequestSeparation:

    @pytest.mark.parametrize("case_name", _CASE_KEYS)
    def test_records_are_plain_dicts(self, case_name):
        c = _case(case_name)
        for key in (
            "candidate", "operator_decision_record",
            "reviewed_mutation_request",
        ):
            rec = c.get(key)
            assert type(rec) is dict, f"{case_name}.{key} must be a plain dict"

    def test_value_changed_argument_dicts_are_distinct_objects(self):
        c = _case("value_changed")
        cand = c["candidate"]
        req = c["reviewed_mutation_request"]
        snap = req.get("approved_candidate_snapshot", {})
        receipt = c.get("receipt", {})
        ids = {
            id(cand.get("arguments")),
            id(snap.get("arguments")),
            id(req.get("arguments")),
            id(receipt.get("reviewed_arguments")),
        }
        # All four argument dicts must be distinct objects (no aliasing).
        present = [
            x for x in (
                cand.get("arguments"), snap.get("arguments"),
                req.get("arguments"), receipt.get("reviewed_arguments"),
            ) if x is not None
        ]
        assert len(ids) == len(present), (
            "candidate / snapshot / request / receipt arguments must be "
            "distinct (deepcopy-separated) dict objects"
        )

    def test_no_callable_in_candidate_or_request(self):
        for case_name in _CASE_KEYS:
            c = _case(case_name)
            for key in ("candidate", "reviewed_mutation_request"):
                for d in _walk(c.get(key, {})):
                    if isinstance(d, dict):
                        for k, v in d.items():
                            assert not callable(v), (
                                f"{case_name}.{key} field {k!r} is callable "
                                "— forbidden"
                            )
                            assert not isinstance(v, Engine), (
                                f"{case_name}.{key} field {k!r} holds an "
                                "Engine instance — forbidden"
                            )


# ===========================================================================
# J. State revalidation — Stage 5.5 / Stage 6
# ===========================================================================


class TestStateRevalidation:

    @pytest.mark.parametrize("case_name", _CASE_KEYS)
    def test_both_revalidation_moments_present(self, case_name):
        revs = _case(case_name).get("revalidations", {})
        assert isinstance(revs, dict)
        assert "stage_5_5_materialization" in revs
        assert "stage_6_invocation" in revs

    def test_successful_cases_revalidations_eligible(self):
        for case_name in ("value_changed", "no_value_change"):
            revs = _case(case_name).get("revalidations", {})
            for moment in ("stage_5_5_materialization", "stage_6_invocation"):
                assert revs.get(moment, {}).get("verdict") == "eligible", (
                    f"{case_name}.{moment} must be 'eligible' on the "
                    "happy path"
                )


# ===========================================================================
# K. Direct invocation boundary — AST scan on the future example source
# ===========================================================================


class TestDirectInvocationBoundary:

    def test_update_rule_stats_called_directly(self):
        src = _example_source()
        assert "update_rule_stats" in _ast_attr_calls(src), (
            "example must contain a direct engine.update_rule_stats(...) "
            "call site"
        )

    def test_no_getattr_eval_exec_dispatch(self):
        src = _example_source()
        name_calls = _ast_name_calls(src)
        for forbidden in ("eval", "exec"):
            assert forbidden not in name_calls, (
                f"{forbidden}() is forbidden in the example"
            )
        attr_calls = _ast_attr_calls(src)
        for forbidden in ("execute", "apply_request", "auto_dispatch"):
            assert forbidden not in attr_calls, (
                f".{forbidden}() dispatch is forbidden"
            )

    def test_no_getattr_on_engine(self):
        src = _example_source()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "getattr" and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Name):
                        assert first.id != "engine", (
                            "getattr(engine, ...) dispatch is forbidden"
                        )

    def test_request_dicts_carry_no_callable_field(self):
        report = _get_report()
        for d in _walk(report):
            if (isinstance(d, dict)
                    and d.get("record_kind") == "reviewed_mutation_request"):
                for k, v in d.items():
                    assert not callable(v), (
                        f"request field {k!r} is callable — forbidden"
                    )


# ===========================================================================
# L. Successful receipt binding (§16.1)
# ===========================================================================


class TestSuccessfulReceiptBinding:

    @pytest.mark.parametrize("case_name", ("value_changed", "no_value_change"))
    def test_successful_receipt_has_before_after_reads(self, case_name):
        receipt = _case(case_name).get("receipt", {})
        for key in (
            "rule_stats_before", "rule_stats_after",
            "identity_before", "identity_after",
            "reviewed_arguments", "actual_effect",
        ):
            assert key in receipt, (
                f"{case_name} successful receipt must record {key!r}"
            )
        assert receipt["rule_stats_before"] is not None
        assert receipt["rule_stats_after"] is not None

    def test_get_rule_stats_invoked_for_successful_cases(self):
        """get_rule_stats must actually be called (pre/post reads), not
        merely echoed into the report."""
        _, counts = _run_with_spies()
        # value_changed (pre+post) + no_value_change (pre+post) +
        # rejected pre-attempt >= 4 reads minimum.
        assert counts["get_rule_stats"] >= 4, (
            "the example must perform actual get_rule_stats reads "
            f"(pre/post per successful case); got {counts['get_rule_stats']}"
        )


# ===========================================================================
# M. Failed-attempt receipt boundary (§16.2)
# ===========================================================================


class TestFailedAttemptReceiptBoundary:

    def test_failed_receipt_kind_distinct_from_successful(self):
        rej = _case("rejected_unknown_pair").get("receipt", {})
        vc = _case("value_changed").get("receipt", {})
        assert rej.get("record_kind") != vc.get("record_kind"), (
            "failed-attempt receipt must be a distinct record_kind from "
            "the successful invocation receipt"
        )

    def test_failed_receipt_available_facts_only(self):
        rej = _case("rejected_unknown_pair").get("receipt", {})
        # before/after must not be fabricated
        assert rej.get("rule_stats_before") is None
        assert rej.get("rule_stats_after") is None
        # but the rejection cause must be present
        assert rej.get("rejection_cause") is not None


# ===========================================================================
# N. KEEP / SET boundary
# ===========================================================================


class TestScoreKeepSetBoundary:

    def test_value_changed_records_keep_and_set_actions(self):
        cand = _case("value_changed").get("candidate", {})
        actions = cand.get("score_actions", {})
        assert actions.get("observed_precision") == "SET"
        assert actions.get("false_positive_rate") == "KEEP"

    def test_keep_passes_none_to_engine(self):
        """A KEEP action must pass None to the Engine argument."""
        args = _case("value_changed").get("receipt", {}).get(
            "reviewed_arguments", {},
        )
        assert args.get("false_positive_rate") is None, (
            "false_positive_rate KEEP must reach the Engine as None"
        )

    def test_no_clear_action_anywhere(self):
        report = _get_report()
        serialized = _serialize(report)
        assert "CLEAR" not in serialized, (
            "M09 introduces no CLEAR action"
        )

    def test_set_zero_distinct_from_keep_concept(self):
        """The contract distinguishes KEEP from SET(ScoreValue(0.0)); the
        example must not collapse them. Locked by requiring score_actions
        to use the KEEP/SET vocabulary rather than a raw None/0.0."""
        cand = _case("value_changed").get("candidate", {})
        actions = cand.get("score_actions", {})
        assert set(actions.values()) <= {"KEEP", "SET"}, (
            "score_actions must use the KEEP / SET vocabulary"
        )


# ===========================================================================
# O. Source observation optionality
# ===========================================================================


class TestSourceObservationOptionality:

    def test_value_changed_has_observation_basis(self):
        cand = _case("value_changed").get("candidate", {})
        refs = cand.get("source_observation_references")
        assert refs, (
            "observation-backed VALUE_CHANGED must carry source "
            "observation references"
        )
        assert cand.get("delta_provenance") is not None
        assert cand.get("precision_input_basis") is not None

    def test_no_value_change_states_absence_explicitly(self):
        """An administrative / no-op update may have no source
        observation, but must state that explicitly rather than
        fabricate a reference."""
        cand = _case("no_value_change").get("candidate", {})
        refs = cand.get("source_observation_references")
        serialized = _serialize(refs).upper()
        explicit_absence = (
            refs in (None, [], {}, "")
            or "NOT_APPLICABLE" in serialized
            or "NONE" in serialized
        )
        assert explicit_absence, (
            "no_value_change must explicitly state the absence of a "
            "source observation (e.g. NOT_APPLICABLE), not fabricate one"
        )


# ===========================================================================
# P. Non-authority locks
# ===========================================================================


class TestNonAuthorityLocks:

    def test_non_authority_locks_present(self):
        locks = _get_report().get("non_authority_locks")
        assert isinstance(locks, list) and locks, (
            "report must carry a non-empty non_authority_locks list"
        )

    def test_required_non_authority_meanings_present(self):
        serialized = _serialize(_get_report().get("non_authority_locks", []))
        for needle in (
            "provenance", "correct", "Evidence", "ground truth",
            "verdict", "authentication",
        ):
            assert needle in serialized, (
                f"non_authority_locks must convey the {needle!r} boundary"
            )


# ===========================================================================
# Q. Historical and snapshot preservation (implementation-independent)
# ===========================================================================


class TestHistoricalAndSnapshotPreservation:

    def test_m01_six_no_diagnosis_preserved(self):
        src = _M01_SCAFFOLD_PATH.read_text(encoding="utf-8")
        for key in (
            "caller_identity_recorded",
            "update_reason_recorded",
            "source_observation_reference_recorded",
            "delta_provenance_recorded",
            "precision_input_basis_recorded",
            "policy_reference_recorded",
        ):
            assert key in src, f"M01 scaffold must still record {key!r}"
        assert 'future_contract": "OC-G"' in src or "OC-G" in src

    def test_m08_not_entered_marker_preserved(self):
        src = _M08_OPERATION_PATH.read_text(encoding="utf-8")
        assert "NOT_ENTERED_M09" in src, (
            "M08 historical marker rule_stats_provenance_status = "
            "NOT_ENTERED_M09 must be preserved"
        )

    def test_snapshot_boundary_unchanged(self):
        snap = Engine().to_snapshot()
        assert snap.get("schema_version") == 2
        assert len(snap) == 18

    def test_rule_stats_field_count(self):
        import dataclasses
        fields = dataclasses.fields(RuleStats)
        assert len(fields) == 7

    def test_report_snapshot_boundary_block(self):
        """When the example exists, its snapshot_boundary block must
        assert no provenance history was added to the snapshot."""
        sb = _get_report().get("snapshot_boundary", {})
        assert sb.get("schema_version") == 2
        assert sb.get("top_level_keys") == 18
        assert sb.get("has_provenance_history_key") is False
        assert sb.get("rule_stats_field_count") == 7


# ===========================================================================
# R. Structural invariants (implementation-independent)
# ===========================================================================


class TestStructuralInvariants:

    def _engine_methods(self):
        public, private = [], []
        for name in dir(Engine):
            if name.startswith("__"):
                continue
            if not callable(getattr(Engine, name)):
                continue
            (private if name.startswith("_") else public).append(name)
        return public, private

    def test_ragcore_all_count(self):
        assert len(ragcore.__all__) == 50

    def test_snapshot_schema_and_keys(self):
        snap = Engine().to_snapshot()
        assert snap.get("schema_version") == 2
        assert len(snap) == 18

    def test_rule_stats_and_score_value_exported(self):
        for name in ("Engine", "RuleStats", "RuleDefinition", "ScoreValue"):
            assert name in ragcore.__all__
