"""Tests for PR77-M08 — Complete Domain-Neutral Reference Operation.

Locks the §0~§22 contract invariants from the test side. These tests
are added before the 266차 example implementation; running them on
265차 produces:

  - normal test-file collection (no ImportError / FileNotFoundError /
    SyntaxError at collection time)
  - one explicit red gate failure
    (test_operation_example_exists)
  - implementation-dependent tests are explicitly skipped at runtime
    because the example file does not yet exist
  - zero unrelated failures across the 1607 existing tests

After 266차, all 22 test classes are expected to pass and the
existing 1607 tests continue to pass.

Contract reference:
  docs/architecture/COMPLETE_DOMAIN_NEUTRAL_REFERENCE_OPERATION_CONTRACT.md

Class index:
  A.  TestImplementationSurface             — entry-point shape
  B.  TestReportBaselineShape               — overall_status + lanes
  C.  TestM01HistoricalPreservation         — M01 scaffold unchanged
  D.  TestExistingArtifactReuse             — reuse PR51/PR53/PR55/
                                              PR56/PR62/PR61/PR64 + M07
  E.  TestLaneAEngineProduction             — fixture_origin_for_engine
                                              == "PRODUCED_BY_LANE_A"
  F.  TestGeneratedIdSequentialMaterialization
                                            — generated id sequential
                                              substitution
  G.  TestLocalRecordBoundaries             — plain dict shape
  H.  TestApprovedOnlyRequestMaterialization
                                            — rejected/hold ⇒ no RMR
  I.  TestExactReviewBinding                — content snapshot lock
  J.  TestNoDynamicDispatch                 — AST scan for forbidden
                                              dispatch patterns
  K.  TestStateRevalidation                 — two-moment revalidation
  L.  TestDecisionReuseRejection            — M05 §7.3 B/C/D probes
  M.  TestPacketBoundaryPreservation        — 7 keys + UNBOUND + UNKNOWN
  N.  TestConfidenceTraceSeparation         — trace ≠ packet identity
  O.  TestProposalBoundary                  — PR55/PR56 + sibling
                                              disposition
  P.  TestDownstreamResultBoundary          — no network/tool/subprocess
  Q.  TestSeparateReentryMutations          — three separate cycles
  R.  TestFinalState                        — CONFIRMED + boundaries
  S.  TestNoRuleStatsAutomation             — M09 NOT_ENTERED
  T.  TestDomainNeutrality                  — §18.1 raw zero scan
  U.  TestInputImmutability                 — imported fixtures unchanged
  V.  TestStructuralInvariants              — 42/20 + 50 + 18 + 7
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import re
import typing
from pathlib import Path
from typing import Any

import pytest

import ragcore
from ragcore import Engine


# ---------------------------------------------------------------------------
# Paths and lazy loading
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_OPERATION_PATH = (
    _REPO_ROOT
    / "examples"
    / "operation"
    / "complete_domain_neutral_reference_operation.py"
)
_M01_SCAFFOLD_PATH = (
    _REPO_ROOT
    / "examples"
    / "operation"
    / "minimal_operational_scaffold.py"
)
_ADAPTER_PATH = (
    _REPO_ROOT
    / "examples"
    / "adapter"
    / "minimal_external_adapter_example.py"
)
_ROLE_EXAMPLE_PATH = (
    _REPO_ROOT
    / "examples"
    / "role_assignment"
    / "minimal_consumer_example.py"
)


def _example_exists() -> bool:
    return _OPERATION_PATH.is_file()


def _skip_if_no_example() -> None:
    if not _example_exists():
        pytest.skip(
            "266차 example implementation not yet present "
            f"({_OPERATION_PATH.name})",
        )


def _load_example_module():
    """Lazy-load the M08 example module via importlib so this test
    file collects cleanly even when the example does not yet exist."""
    _skip_if_no_example()
    spec = importlib.util.spec_from_file_location(
        "complete_domain_neutral_reference_operation",
        _OPERATION_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_external_module(path: Path, mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_REPORT_CACHE: dict[str, Any] | None = None


def _get_report() -> dict[str, Any]:
    """Run the operation once per session and cache the report."""
    global _REPORT_CACHE
    _skip_if_no_example()
    if _REPORT_CACHE is None:
        module = _load_example_module()
        run = getattr(
            module, "run_complete_domain_neutral_reference_operation", None,
        )
        if run is None:
            pytest.skip(
                "266차 entry point "
                "run_complete_domain_neutral_reference_operation "
                "not yet present",
            )
        _REPORT_CACHE = run()
    return _REPORT_CACHE


def _example_source() -> str:
    _skip_if_no_example()
    return _OPERATION_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Runtime invocation spies (266차 R-D)
# ---------------------------------------------------------------------------


_SPY_TARGETS_GLOBAL: tuple[str, ...] = (
    "validate_role_assignment_boundaries",
    "build_engine_context_packet",
    "validate_consumer_packet_interpretation",
    "validate_llm_proposal_shape",
    "validate_proposal_safety",
)


def _install_spies(module):
    """Wrap each reusable callable that the example imported into its
    globals (matched by `value.__name__` per directive §2.3), and wrap
    Engine.compute_effective_confidence_with_trace at the class level.

    Returns:
        (call_counts, captured_args, restore_fn)
        call_counts:   dict[name -> int]
        captured_args: dict[name -> list of (deepcopy(args), deepcopy(kwargs))]
        restore_fn:    callable that restores both module globals and
                       the Engine class attribute
    """
    spy_names = list(_SPY_TARGETS_GLOBAL) + [
        "compute_effective_confidence_with_trace",
    ]
    call_counts: dict[str, int] = {n: 0 for n in spy_names}
    captured: dict[str, list[Any]] = {n: [] for n in spy_names}

    # 1) Patch validators in the example module's globals by walking
    #    every attribute and matching value.__name__ against the
    #    target set. Allows the example to alias the import.
    module_patches: list[tuple[Any, str, Any]] = []
    for attr_name, value in list(module.__dict__.items()):
        if not callable(value):
            continue
        target = getattr(value, "__name__", None)
        if target in _SPY_TARGETS_GLOBAL:
            orig = value

            def make_spy(orig=orig, target=target):
                def spy(*args, **kwargs):
                    call_counts[target] += 1
                    try:
                        captured[target].append(
                            (copy.deepcopy(args), copy.deepcopy(kwargs)),
                        )
                    except Exception:
                        captured[target].append(("<unpicklable>", {}))
                    return orig(*args, **kwargs)
                spy.__name__ = target
                spy.__wrapped__ = orig
                return spy

            spy = make_spy()
            module_patches.append((module, attr_name, orig))
            setattr(module, attr_name, spy)

    # 2) Patch Engine.compute_effective_confidence_with_trace at the
    #    class level so engine.compute_effective_confidence_with_trace(
    #    claim_id) goes through the spy.
    orig_trace = Engine.compute_effective_confidence_with_trace

    def trace_spy(self, claim_id):
        call_counts["compute_effective_confidence_with_trace"] += 1
        captured["compute_effective_confidence_with_trace"].append(claim_id)
        return orig_trace(self, claim_id)

    trace_spy.__name__ = "compute_effective_confidence_with_trace"
    Engine.compute_effective_confidence_with_trace = trace_spy

    def restore() -> None:
        for mod, attr, orig in module_patches:
            setattr(mod, attr, orig)
        Engine.compute_effective_confidence_with_trace = orig_trace

    return call_counts, captured, restore


_SPY_RESULT_CACHE: tuple[dict[str, Any], dict[str, int], dict[str, list[Any]]] | None = None


def _run_with_spies() -> tuple[
    dict[str, Any], dict[str, int], dict[str, list[Any]],
]:
    """Run the operation once under runtime spies and cache the
    result for the session. Returns (report, call_counts, captured)."""
    global _SPY_RESULT_CACHE
    _skip_if_no_example()
    if _SPY_RESULT_CACHE is None:
        module = _load_example_module()
        if not hasattr(
            module, "run_complete_domain_neutral_reference_operation",
        ):
            pytest.skip(
                "266차 entry point not yet present (spy run)",
            )
        call_counts, captured, restore = _install_spies(module)
        try:
            report = module.run_complete_domain_neutral_reference_operation()
        finally:
            restore()
        _SPY_RESULT_CACHE = (report, call_counts, captured)
    return _SPY_RESULT_CACHE


# ---------------------------------------------------------------------------
# Forbidden domain-specific vocabulary (M08 §18 inventory)
# ---------------------------------------------------------------------------


_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "cerberus",
    "vulnerability",
    "exploit",
    "scanner",
    "host",
    "port",
    "service",
    "cve",
    "security verdict",
)


def _word_boundary_regex(token: str) -> re.Pattern[str]:
    # "security verdict" carries whitespace; bracket the whole phrase
    # with word boundaries.
    return re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)


def _serialize_for_scan(obj: Any) -> str:
    """Stable string projection of a dict report for raw-token scan."""
    if isinstance(obj, dict):
        return "{" + ",".join(
            f"{_serialize_for_scan(k)}:{_serialize_for_scan(v)}"
            for k, v in obj.items()
        ) + "}"
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(_serialize_for_scan(x) for x in obj) + "]"
    return repr(obj)


# ===========================================================================
# A. Implementation surface — entry-point shape
# ===========================================================================


class TestImplementationSurface:

    def test_operation_example_exists(self):
        """RED GATE — must fail until 266차 implementation lands."""
        assert _OPERATION_PATH.is_file(), (
            "266차 example implementation is not yet present at "
            f"{_OPERATION_PATH}. This is the explicit red gate for "
            "tests-first; the 266차 commit will make this pass."
        )

    def test_entry_point_name_present(self):
        module = _load_example_module()
        assert hasattr(
            module, "run_complete_domain_neutral_reference_operation",
        )

    def test_entry_point_is_callable_with_no_args(self):
        module = _load_example_module()
        run = module.run_complete_domain_neutral_reference_operation
        report = run()
        assert isinstance(report, dict)

    def test_entry_point_return_annotation(self):
        module = _load_example_module()
        run = module.run_complete_domain_neutral_reference_operation
        hints = typing.get_type_hints(run)
        ret = hints.get("return")
        # accept dict, dict[str, Any], or typing.Dict[str, Any]
        if ret is dict:
            return
        origin = typing.get_origin(ret)
        assert origin in (dict,), (
            f"entry-point return annotation expected to be dict[str, Any]; "
            f"got {ret!r}"
        )


# ===========================================================================
# B. Report baseline shape
# ===========================================================================


class TestReportBaselineShape:

    def test_overall_status_is_complete(self):
        report = _get_report()
        assert report.get("overall_status") == "COMPLETE_REFERENCE_OPERATION"

    def test_required_top_level_sections_present(self):
        report = _get_report()
        for key in (
            "lanes",
            "final_state",
            "non_authority_locks",
        ):
            assert key in report, f"required top-level key missing: {key!r}"

    def test_three_lane_keys_present(self):
        report = _get_report()
        lanes = report["lanes"]
        assert isinstance(lanes, dict)
        for lane_key in (
            "external_ingress",
            "engine_read_and_proposal",
            "downstream_reentry",
        ):
            assert lane_key in lanes, f"missing lane: {lane_key!r}"

    def test_no_blocked_undefined_todo_on_happy_path(self):
        report = _get_report()
        serialized = _serialize_for_scan(report)
        for forbidden in ("BLOCKED", "UNDEFINED", "TODO"):
            # status values are recorded as strings; the report is the
            # happy path so they must not appear as stage statuses.
            pattern = re.compile(rf"'status':\s*'{forbidden}'")
            assert not pattern.search(serialized), (
                f"happy-path report contains {forbidden!r} as a stage status"
            )


# ===========================================================================
# C. M01 historical preservation
# ===========================================================================


class TestM01HistoricalPreservation:

    def test_m01_scaffold_still_incomplete(self):
        module = _load_external_module(
            _M01_SCAFFOLD_PATH, "minimal_operational_scaffold",
        )
        report = module.build_minimal_operational_scaffold()
        assert report["overall_status"] == "INCOMPLETE"

    def test_m01_scaffold_still_preseeded_fixture(self):
        module = _load_external_module(
            _M01_SCAFFOLD_PATH, "minimal_operational_scaffold",
        )
        report = module.build_minimal_operational_scaffold()
        assert report["fixture_origin_for_engine"] == (
            "PRESEEDED_FOR_READ_LANE_ONLY"
        )


# ===========================================================================
# D. Existing artifact reuse
# ===========================================================================


class TestExistingArtifactReuse:

    @pytest.fixture
    def src(self):
        return _example_source()

    def test_pr64_adapter_trace_referenced(self, src):
        assert "RESOLVED_TRANSLATION_TRACE" in src

    def test_pr61_role_example_referenced(self, src):
        assert "RESOLVED_EXAMPLE" in src

    def test_pr62_role_validator_referenced(self, src):
        assert "validate_role_assignment_boundaries" in src

    def test_pr51_packet_builder_referenced(self, src):
        assert "build_engine_context_packet" in src

    def test_pr53_packet_validator_referenced(self, src):
        assert "validate_consumer_packet_interpretation" in src

    def test_pr55_proposal_shape_validator_referenced(self, src):
        assert "validate_llm_proposal_shape" in src

    def test_pr56_proposal_safety_validator_referenced(self, src):
        assert "validate_proposal_safety" in src

    def test_m07_trace_api_referenced(self, src):
        assert "compute_effective_confidence_with_trace" in src


# ===========================================================================
# E. Lane A engine production
# ===========================================================================


class TestLaneAEngineProduction:

    def test_fixture_origin_produced_by_lane_a(self):
        report = _get_report()
        # The fixture_origin marker may live at the report root or
        # inside the external_ingress lane; accept either.
        lane_a = report["lanes"]["external_ingress"]
        if "fixture_origin_for_engine" in report:
            origin = report["fixture_origin_for_engine"]
        else:
            origin = lane_a.get("fixture_origin_for_engine")
        assert origin == "PRODUCED_BY_LANE_A"

    def test_fixture_origin_not_preseeded(self):
        report = _get_report()
        lane_a = report["lanes"]["external_ingress"]
        if "fixture_origin_for_engine" in report:
            origin = report["fixture_origin_for_engine"]
        else:
            origin = lane_a.get("fixture_origin_for_engine")
        assert origin != "PRESEEDED_FOR_READ_LANE_ONLY"

    def test_lane_a_invokes_add_entity_then_add_claim_then_add_gap(self):
        report = _get_report()
        lane_a = report["lanes"]["external_ingress"]
        invocations = lane_a.get("explicit_invocation_sequence")
        assert isinstance(invocations, list)
        method_sequence = [inv.get("target_method") for inv in invocations]
        assert method_sequence == [
            "add_entity", "add_claim", "add_gap",
        ], f"unexpected Lane A invocation sequence: {method_sequence!r}"


# ===========================================================================
# F. Generated-ID sequential materialization
# ===========================================================================


class TestGeneratedIdSequentialMaterialization:

    def test_claim_args_use_returned_entity_id(self):
        report = _get_report()
        invocations = report["lanes"]["external_ingress"][
            "explicit_invocation_sequence"
        ]
        entity_call = invocations[0]
        claim_call = invocations[1]
        entity_id = entity_call.get("returned_id")
        claim_subject = claim_call.get("arguments", {}).get("subject_id")
        assert entity_id is not None
        assert claim_subject == entity_id, (
            f"add_claim subject_id ({claim_subject!r}) does not equal "
            f"add_entity returned id ({entity_id!r})"
        )

    def test_gap_args_use_returned_claim_id(self):
        report = _get_report()
        invocations = report["lanes"]["external_ingress"][
            "explicit_invocation_sequence"
        ]
        claim_call = invocations[1]
        gap_call = invocations[2]
        claim_id = claim_call.get("returned_id")
        gap_claim_arg = gap_call.get("arguments", {}).get("claim_id")
        assert claim_id is not None
        assert gap_claim_arg == claim_id

    def test_no_placeholder_ids_in_arguments(self):
        report = _get_report()
        invocations = report["lanes"]["external_ingress"][
            "explicit_invocation_sequence"
        ]
        for inv in invocations:
            args = inv.get("arguments", {})
            for k, v in args.items():
                if k.endswith("_id"):
                    assert isinstance(v, int), (
                        f"placeholder / non-int id at {k!r}: {v!r}"
                    )


# ===========================================================================
# G. Local record boundaries — plain dict shape
# ===========================================================================


class TestLocalRecordBoundaries:

    _CANDIDATE_FIELDS = {
        "record_kind", "candidate_id", "target_method", "arguments",
        "source_basis", "expected_effect", "policy_assumptions",
        "materialized_at_revision",
    }
    _REQUEST_FIELDS = {
        "record_kind", "request_id", "approved_candidate_snapshot",
        "approved_decision_record_id", "target_method", "arguments",
        "decision_state_identity",
    }
    _DECISION_FIELDS = {
        "record_kind", "decision_record_id", "decision_family",
        "subject_snapshot", "disposition", "decision_state_identity",
        "supersedes", "note",
    }

    def _walk(self, obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from self._walk(v)
        elif isinstance(obj, list):
            for x in obj:
                yield from self._walk(x)

    def _records_of_kind(self, report, kind: str) -> list[dict]:
        return [
            d for d in self._walk(report)
            if isinstance(d, dict) and d.get("record_kind") == kind
        ]

    def test_engine_input_candidate_records_present_with_fields(self):
        report = _get_report()
        records = self._records_of_kind(report, "engine_input_candidate")
        assert records, "no engine_input_candidate records found"
        for rec in records:
            missing = self._CANDIDATE_FIELDS - set(rec.keys())
            assert not missing, (
                f"candidate missing fields {missing!r}: {rec!r}"
            )
            # plain dict only — not a dataclass / TypedDict /
            # NamedTuple / Protocol / Pydantic instance
            assert type(rec) is dict

    def test_reviewed_mutation_request_records_present_with_fields(self):
        report = _get_report()
        records = self._records_of_kind(report, "reviewed_mutation_request")
        assert records, "no reviewed_mutation_request records found"
        for rec in records:
            missing = self._REQUEST_FIELDS - set(rec.keys())
            assert not missing, f"request missing fields {missing!r}"
            assert type(rec) is dict

    def test_operator_decision_records_present_with_fields(self):
        report = _get_report()
        records = self._records_of_kind(report, "operator_decision_record")
        assert records, "no operator_decision_record records found"
        for rec in records:
            missing = self._DECISION_FIELDS - set(rec.keys())
            assert not missing, f"decision missing fields {missing!r}"
            assert type(rec) is dict

    def test_no_dataclass_or_typeddict_anywhere(self):
        """The example must not introduce any framework-level dataclass /
        TypedDict / NamedTuple / Protocol / Pydantic model."""
        src = _example_source()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = [ast.unparse(b) for b in node.bases]
                joined = " ".join(bases)
                assert not any(
                    bad in joined
                    for bad in ("TypedDict", "NamedTuple", "Protocol",
                                "BaseModel")
                ), f"forbidden base class on {node.name}: {bases!r}"
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                for deco in getattr(node, "decorator_list", []):
                    text = ast.unparse(deco)
                    assert "dataclass" not in text, (
                        f"@dataclass forbidden on {node.name}; got {text!r}"
                    )


# ===========================================================================
# H. Approved-only request materialization
# ===========================================================================


class TestApprovedOnlyRequestMaterialization:

    def _walk(self, obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from self._walk(v)
        elif isinstance(obj, list):
            for x in obj:
                yield from self._walk(x)

    def test_every_request_has_approved_decision(self):
        report = _get_report()
        requests = [
            d for d in self._walk(report)
            if isinstance(d, dict)
            and d.get("record_kind") == "reviewed_mutation_request"
        ]
        decisions_by_id = {
            d["decision_record_id"]: d
            for d in self._walk(report)
            if isinstance(d, dict)
            and d.get("record_kind") == "operator_decision_record"
        }
        for req in requests:
            dec_id = req.get("approved_decision_record_id")
            assert dec_id in decisions_by_id, (
                f"request references missing decision id {dec_id!r}"
            )
            assert decisions_by_id[dec_id]["disposition"] == "approved"

    def test_rejected_and_hold_decisions_have_no_request(self):
        report = _get_report()
        decisions = [
            d for d in self._walk(report)
            if isinstance(d, dict)
            and d.get("record_kind") == "operator_decision_record"
        ]
        request_decision_refs = {
            d.get("approved_decision_record_id")
            for d in self._walk(report)
            if isinstance(d, dict)
            and d.get("record_kind") == "reviewed_mutation_request"
        }
        for dec in decisions:
            if dec["disposition"] in ("rejected", "hold"):
                assert dec["decision_record_id"] not in request_decision_refs


# ===========================================================================
# I. Exact review binding
# ===========================================================================


class TestExactReviewBinding:

    def _walk(self, obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from self._walk(v)
        elif isinstance(obj, list):
            for x in obj:
                yield from self._walk(x)

    def test_request_args_match_candidate_snapshot_args(self):
        report = _get_report()
        for d in self._walk(report):
            if (isinstance(d, dict)
                    and d.get("record_kind") == "reviewed_mutation_request"):
                snap = d["approved_candidate_snapshot"]
                assert d["target_method"] == snap["target_method"]
                assert d["arguments"] == snap["arguments"]

    def test_request_target_method_matches_invocation_target_method(self):
        report = _get_report()
        invocations = []
        for lane in report["lanes"].values():
            if isinstance(lane, dict):
                seq = lane.get("explicit_invocation_sequence")
                if seq:
                    invocations.extend(seq)
        for inv in invocations:
            rmr = inv.get("reviewed_mutation_request")
            if rmr is not None:
                assert rmr["target_method"] == inv["target_method"]
                assert rmr["arguments"] == inv["arguments"]


# ===========================================================================
# J. No dynamic dispatch — AST scan
# ===========================================================================


class TestNoDynamicDispatch:

    def _tree(self):
        return ast.parse(_example_source())

    def test_no_getattr_on_engine(self):
        for node in ast.walk(self._tree()):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "getattr":
                    if node.args and isinstance(node.args[0], ast.Name):
                        first = node.args[0].id
                        assert first != "engine", (
                            "getattr(engine, ...) is forbidden by §J / §13"
                        )

    def test_no_eval_or_exec(self):
        for node in ast.walk(self._tree()):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
                    raise AssertionError("eval / exec forbidden in example")

    def test_no_request_execute_or_apply_request(self):
        for node in ast.walk(self._tree()):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    if func.attr in (
                        "execute", "apply_request",
                        "auto_dispatch",
                    ):
                        # Allow .execute() ONLY if it is clearly NOT a
                        # request method (we forbid all to be safe).
                        raise AssertionError(
                            f"forbidden dispatch attribute: {func.attr}()"
                        )

    def test_request_dicts_carry_no_callable_field(self):
        """The local ReviewedMutationRequest dicts must not contain a
        callable / lambda / bound method as a field value."""
        report = _get_report()
        def walk(o):
            if isinstance(o, dict):
                yield o
                for v in o.values():
                    yield from walk(v)
            elif isinstance(o, list):
                for x in o:
                    yield from walk(x)
        for d in walk(report):
            if (isinstance(d, dict)
                    and d.get("record_kind") == "reviewed_mutation_request"):
                for k, v in d.items():
                    assert not callable(v), (
                        f"request field {k!r} is callable: forbidden"
                    )


# ===========================================================================
# K. State revalidation — two moments
# ===========================================================================


class TestStateRevalidation:

    def test_each_invocation_has_two_revalidation_moments(self):
        report = _get_report()
        invocations = []
        for lane in report["lanes"].values():
            if isinstance(lane, dict):
                seq = lane.get("explicit_invocation_sequence")
                if seq:
                    invocations.extend(seq)
        assert invocations, "no explicit invocations recorded"
        for inv in invocations:
            reval = inv.get("revalidations")
            assert isinstance(reval, dict)
            assert "stage_5_5_materialization" in reval
            assert "stage_6_invocation" in reval

    def test_revalidation_records_eligible_for_happy_path(self):
        report = _get_report()
        invocations = []
        for lane in report["lanes"].values():
            if isinstance(lane, dict):
                seq = lane.get("explicit_invocation_sequence")
                if seq:
                    invocations.extend(seq)
        for inv in invocations:
            reval = inv["revalidations"]
            for moment in (
                "stage_5_5_materialization", "stage_6_invocation",
            ):
                v = reval[moment]
                assert v.get("verdict") == "eligible", (
                    f"happy-path revalidation at {moment} expected "
                    f"'eligible'; got {v!r}"
                )


# ===========================================================================
# L. Decision-reuse rejection (M05 §7.3 B / C / D)
# ===========================================================================


class TestDecisionReuseRejection:

    def test_negative_stale_decision_probe_present(self):
        report = _get_report()
        probe = report.get("negative_stale_decision_probe")
        assert isinstance(probe, dict), (
            "report must include a 'negative_stale_decision_probe' "
            "block (M08 §17)"
        )

    def test_case_b_same_token_diff_revision_suppresses_invocation(self):
        report = _get_report()
        probe = report["negative_stale_decision_probe"]
        case_b = probe.get("case_B_same_token_diff_revision")
        assert case_b is not None
        assert case_b.get("verdict") == "not_eligible"
        assert case_b.get("invocation_suppressed") is True

    def test_case_c_different_token_suppresses_invocation(self):
        report = _get_report()
        probe = report["negative_stale_decision_probe"]
        case_c = probe.get("case_C_different_token")
        assert case_c is not None
        assert case_c.get("verdict") == "not_eligible"
        assert case_c.get("invocation_suppressed") is True

    def test_case_d_missing_or_malformed_identity_suppresses(self):
        report = _get_report()
        probe = report["negative_stale_decision_probe"]
        case_d = probe.get("case_D_missing_or_malformed_identity")
        assert case_d is not None
        assert case_d.get("verdict") == "not_eligible"
        assert case_d.get("invocation_suppressed") is True

    def test_no_m03_packet_stale_label_in_probe(self):
        report = _get_report()
        probe = report["negative_stale_decision_probe"]
        serialized = _serialize_for_scan(probe)
        for forbidden in (
            "M03 packet STALE",
            "packet stale",
            "CAPTURE_BOUND stale",
        ):
            assert forbidden.lower() not in serialized.lower(), (
                f"probe must not label decision reuse as {forbidden!r}"
            )
        # The acceptable phrase must appear somewhere in the probe.
        # 268차 typo fix: lowercase BOTH sides so the case-insensitive
        # comparison the surrounding loop already uses applies to the
        # needle as well. The example records the phrase per contract
        # M08 §13 with uppercase "M05"; this assertion is intended to
        # match it case-insensitively.
        assert (
            "not eligible for decision reuse under M05".lower()
            in serialized.lower()
        )


# ===========================================================================
# M. Packet boundary preservation
# ===========================================================================


class TestPacketBoundaryPreservation:

    _EXPECTED_KEYS = (
        "claim",
        "effective_confidence",
        "supporting_evidence",
        "contradictions",
        "active_contradictions",
        "unresolved_gaps",
        "lifecycle_history",
    )

    _FORBIDDEN_KEYS = (
        "state_identity",
        "engine_token",
        "revision",
        "capture_token",
        "snapshot_digest",
        "confidence_trace",
        "calculation_policy_id",
    )

    def _packet(self):
        report = _get_report()
        lane_b = report["lanes"]["engine_read_and_proposal"]
        pkt = lane_b.get("pr51_packet")
        assert isinstance(pkt, dict)
        return pkt

    def test_packet_key_order_exact(self):
        pkt = self._packet()
        assert tuple(pkt.keys()) == self._EXPECTED_KEYS

    def test_packet_has_no_forbidden_keys(self):
        pkt = self._packet()
        for forbidden in self._FORBIDDEN_KEYS:
            assert forbidden not in pkt, (
                f"PR51 packet must not carry {forbidden!r}"
            )

    def test_packet_binding_status_unbound(self):
        report = _get_report()
        lane_b = report["lanes"]["engine_read_and_proposal"]
        assert lane_b.get("packet_binding_status") == "UNBOUND"

    def test_packet_comparison_status_unknown(self):
        report = _get_report()
        lane_b = report["lanes"]["engine_read_and_proposal"]
        assert lane_b.get("packet_comparison_status") == "UNKNOWN"


# ===========================================================================
# N. Confidence trace separation
# ===========================================================================


class TestConfidenceTraceSeparation:

    def _trace_block(self):
        report = _get_report()
        lane_b = report["lanes"]["engine_read_and_proposal"]
        block = lane_b.get("effective_confidence_trace")
        assert isinstance(block, dict)
        return block

    def test_trace_effective_equals_legacy(self):
        block = self._trace_block()
        assert block.get("trace_effective_equals_legacy") is True

    def test_calculation_policy_id_exact(self):
        block = self._trace_block()
        assert block.get("calculation_policy_id") == (
            "ragcore.effective-confidence.v1"
        )

    def test_trace_source_identity_equals_engine_state(self):
        block = self._trace_block()
        assert block.get("source_identity_equals_engine_state") is True

    def test_trace_not_in_packet(self):
        report = _get_report()
        lane_b = report["lanes"]["engine_read_and_proposal"]
        pkt = lane_b["pr51_packet"]
        for forbidden in (
            "effective_confidence_trace",
            "confidence_trace",
            "calculation_policy_id",
            "source_state_identity",
        ):
            assert forbidden not in pkt

    def test_no_packet_binding_or_freshness_labels_for_trace(self):
        block = self._trace_block()
        serialized = _serialize_for_scan(block).lower()
        for forbidden in (
            "capture_bound", "currently_matched", "stale",
            "freshness proof", "probability",
        ):
            assert forbidden not in serialized, (
                f"trace block must not assert {forbidden!r}"
            )


# ===========================================================================
# O. Proposal boundary
# ===========================================================================


class TestProposalBoundary:

    def _block(self):
        report = _get_report()
        lane_b = report["lanes"]["engine_read_and_proposal"]
        block = lane_b.get("proposal")
        assert isinstance(block, dict)
        return block

    def test_pr55_shape_validator_called(self):
        block = self._block()
        assert block.get("pr55_shape_violations") == []

    def test_pr56_safety_validator_called(self):
        block = self._block()
        assert block.get("pr56_safety_violations") == []

    def test_no_network_or_llm_invocation_marker(self):
        block = self._block()
        assert block.get("network_invocation") is False
        assert block.get("llm_invocation") is False

    def test_operator_disposition_is_schedule_manual_inspection(self):
        block = self._block()
        assert block.get("operator_disposition") == (
            "schedule-manual-inspection"
        )

    def test_disposition_is_sibling_not_accept_suboption(self):
        block = self._block()
        # The example must record an explicit sibling marker; the
        # disposition must not be expressed as "accept" with a
        # sub-option.
        assert block.get("disposition_is_sibling_of_accept") is True
        assert block.get("operator_disposition") != "accept"


# ===========================================================================
# P. Downstream result boundary
# ===========================================================================


class TestDownstreamResultBoundary:

    def _trace(self):
        report = _get_report()
        lane_c = report["lanes"]["downstream_reentry"]
        trace = lane_c.get("result_trace")
        assert isinstance(trace, dict)
        return trace

    def test_no_network_no_tool_no_subprocess(self):
        report = _get_report()
        lane_c = report["lanes"]["downstream_reentry"]
        assert lane_c.get("network_invocation") is False
        assert lane_c.get("tool_invocation") is False
        assert lane_c.get("subprocess_invocation") is False

    def test_result_trace_is_plain_dict(self):
        trace = self._trace()
        assert type(trace) is dict
        assert trace.get("record_kind") == "downstream_result_trace"

    def test_external_result_is_not_marked_as_evidence(self):
        trace = self._trace()
        # The trace must not claim to BE an Evidence record.
        assert trace.get("is_ragcore_evidence", False) is False

    def test_external_score_not_direct_strength_identity(self):
        report = _get_report()
        lane_c = report["lanes"]["downstream_reentry"]
        # The add_evidence candidate's strength must record a
        # consumer translation basis distinct from any raw external
        # score.
        add_ev = next(
            (inv for inv in lane_c.get("explicit_invocation_sequence", [])
             if inv.get("target_method") == "add_evidence"),
            None,
        )
        assert add_ev is not None
        basis = add_ev.get("source_basis") or {}
        assert basis.get("strength_translation") is not None, (
            "add_evidence candidate must record a 'strength_translation' "
            "basis distinct from any raw external score"
        )


# ===========================================================================
# Q. Separate re-entry mutations
# ===========================================================================


class TestSeparateReentryMutations:

    def _lane_c_invocations(self):
        report = _get_report()
        lane_c = report["lanes"]["downstream_reentry"]
        return lane_c.get("explicit_invocation_sequence", [])

    def test_three_lane_c_engine_calls_present(self):
        invs = self._lane_c_invocations()
        methods = [inv.get("target_method") for inv in invs]
        assert methods == [
            "add_evidence",
            "resolve_gaps_for_evidence",
            "confirm_claim_if_ready",
        ], f"unexpected Lane C invocation sequence: {methods!r}"

    def test_each_lane_c_call_has_separate_records(self):
        invs = self._lane_c_invocations()
        candidate_ids = []
        request_ids = []
        decision_ids = []
        for inv in invs:
            cand = inv.get("candidate")
            req = inv.get("reviewed_mutation_request")
            dec = inv.get("operator_decision_record")
            assert cand is not None
            assert req is not None
            assert dec is not None
            assert "stage_5_5_materialization" in inv["revalidations"]
            assert "stage_6_invocation" in inv["revalidations"]
            candidate_ids.append(cand["candidate_id"])
            request_ids.append(req["request_id"])
            decision_ids.append(dec["decision_record_id"])
        # uniqueness — no shared record across the three calls
        assert len(set(candidate_ids)) == 3
        assert len(set(request_ids)) == 3
        assert len(set(decision_ids)) == 3


# ===========================================================================
# R. Final state
# ===========================================================================


class TestFinalState:

    def _final(self):
        report = _get_report()
        final = report.get("final_state")
        assert isinstance(final, dict)
        return final

    def test_lane_a_engine_produced(self):
        assert self._final().get("lane_a_engine_produced") is True

    def test_entity_claim_gap_evidence_created(self):
        f = self._final()
        assert f.get("entity_created") is True
        assert f.get("claim_created") is True
        assert f.get("gap_created") is True
        assert f.get("evidence_registered") is True

    def test_packet_built_with_seven_keys(self):
        f = self._final()
        assert f.get("packet_built_seven_keys") is True

    def test_confidence_trace_available(self):
        assert self._final().get("confidence_trace_available") is True

    def test_proposal_operator_decision_recorded(self):
        assert self._final().get("proposal_operator_decision_recorded") is True

    def test_downstream_result_trace_recorded(self):
        assert self._final().get("downstream_result_trace_recorded") is True

    def test_gap_explicitly_resolved_and_lifecycle_invoked(self):
        f = self._final()
        assert f.get("gap_explicitly_resolved") is True
        assert f.get("lifecycle_explicitly_invoked") is True

    def test_claim_final_status_confirmed(self):
        assert self._final().get("claim_final_status") == "CONFIRMED"


# ===========================================================================
# S. No RuleStats automation — M09 not entered
# ===========================================================================


class TestNoRuleStatsAutomation:

    def test_no_update_rule_stats_call_in_source(self):
        src = _example_source()
        # Allow textual mention inside docstrings forbidden? — we lock
        # the call form only.
        assert "update_rule_stats(" not in src, (
            "example must not call engine.update_rule_stats(...) (M08 §16)"
        )

    def test_report_marks_m09_not_entered(self):
        report = _get_report()
        assert report.get("rule_stats_provenance_status") == (
            "NOT_ENTERED_M09"
        )

    def test_no_register_rule_call_in_source(self):
        # M08 §16 prefers absence of register_rule. The example may
        # rely on the sentinel rule-id = 0 path, so no register_rule
        # call should appear in the operation source.
        src = _example_source()
        assert "register_rule(" not in src, (
            "M08 §16: example should not call engine.register_rule(...)"
        )


# ===========================================================================
# T. Domain neutrality — §18.1 raw zero scan
# ===========================================================================


class TestDomainNeutrality:

    def test_example_source_zero_raw_forbidden_tokens(self):
        src = _example_source()
        for token in _FORBIDDEN_TOKENS:
            pattern = _word_boundary_regex(token)
            matches = pattern.findall(src)
            assert not matches, (
                f"M08 §18.1 violation in example source: {token!r} "
                f"appears {len(matches)} times"
            )

    def test_serialized_report_zero_raw_forbidden_tokens(self):
        report = _get_report()
        serialized = _serialize_for_scan(report)
        for token in _FORBIDDEN_TOKENS:
            pattern = _word_boundary_regex(token)
            matches = pattern.findall(serialized)
            assert not matches, (
                f"M08 §18.1 violation in serialized operation report: "
                f"{token!r} appears {len(matches)} times"
            )


# ===========================================================================
# U. Input immutability
# ===========================================================================


class TestInputImmutability:

    def test_pr64_adapter_trace_unchanged_after_operation(self):
        adapter = _load_external_module(
            _ADAPTER_PATH, "minimal_external_adapter_example",
        )
        before = copy.deepcopy(adapter.RESOLVED_TRANSLATION_TRACE)
        _get_report()
        # reload after run to compare fresh
        adapter2 = _load_external_module(
            _ADAPTER_PATH, "minimal_external_adapter_example_2",
        )
        assert adapter2.RESOLVED_TRANSLATION_TRACE == before

    def test_pr61_role_example_unchanged_after_operation(self):
        role = _load_external_module(
            _ROLE_EXAMPLE_PATH, "minimal_consumer_example",
        )
        before = copy.deepcopy(role.RESOLVED_EXAMPLE)
        _get_report()
        role2 = _load_external_module(
            _ROLE_EXAMPLE_PATH, "minimal_consumer_example_2",
        )
        assert role2.RESOLVED_EXAMPLE == before


# ===========================================================================
# V. Structural invariants
# ===========================================================================


class TestStructuralInvariants:

    def _ast_counts(self):
        import ragcore as r
        src = open("ragcore/engine.py").read()
        tree = ast.parse(src)
        public, private = 0, 0
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Engine":
                for item in node.body:
                    if isinstance(
                        item, (ast.FunctionDef, ast.AsyncFunctionDef),
                    ):
                        if item.name.startswith("_"):
                            private += 1
                        else:
                            public += 1
        return public, private

    def test_engine_public_method_count(self):
        public, _ = self._ast_counts()
        assert public == 42

    def test_engine_private_method_count(self):
        _, private = self._ast_counts()
        assert private == 20

    def test_ragcore_all_count(self):
        assert len(ragcore.__all__) == 50

    def test_snapshot_schema_and_key_count(self):
        snap = Engine().to_snapshot()
        assert snap["schema_version"] == 2
        assert len(snap) == 18

    def test_pr51_packet_key_count(self):
        spec = importlib.util.spec_from_file_location(
            "engine_inspector",
            _REPO_ROOT / "examples" / "inspector" / "engine_inspector.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        e = Engine()
        ent = e.add_entity(entity_type=1)
        cid = e.add_claim(
            subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
            reason_code=0, base_confidence=0.5,
        )
        pkt = mod.build_engine_context_packet(e, cid)
        assert len(pkt) == 7


# ===========================================================================
# W. Runtime invocation spies — R-D (266차)
# ===========================================================================


class TestRuntimeInvocationSpies:
    """Replace the 265차 name-only / source-text checks with actual
    runtime call_count spies. Each target must be CALLED, not merely
    mentioned in source.

    Static name-presence checks (TestExistingArtifactReuse) are kept
    in addition to these runtime invocation checks per the directive:
    "static scans only without a runtime spy are insufficient".
    """

    def _counts(self) -> dict[str, int]:
        _, call_counts, _ = _run_with_spies()
        return call_counts

    def test_validate_role_assignment_boundaries_invoked(self):
        assert self._counts()["validate_role_assignment_boundaries"] >= 1

    def test_build_engine_context_packet_invoked(self):
        assert self._counts()["build_engine_context_packet"] >= 1

    def test_validate_consumer_packet_interpretation_invoked(self):
        assert self._counts()["validate_consumer_packet_interpretation"] >= 1

    def test_validate_llm_proposal_shape_invoked(self):
        assert self._counts()["validate_llm_proposal_shape"] >= 1

    def test_validate_proposal_safety_invoked(self):
        assert self._counts()["validate_proposal_safety"] >= 1

    def test_compute_effective_confidence_with_trace_invoked(self):
        assert self._counts()["compute_effective_confidence_with_trace"] >= 1

    def test_happy_path_invocation_counts_exact(self):
        """All six reusable callables are invoked exactly once on the
        happy path. If the example's implementation has a documented
        reason to invoke a target more than once, this assertion can
        be relaxed; until then we lock exact 1."""
        counts = self._counts()
        for target in (
            "validate_role_assignment_boundaries",
            "build_engine_context_packet",
            "validate_consumer_packet_interpretation",
            "validate_llm_proposal_shape",
            "validate_proposal_safety",
            "compute_effective_confidence_with_trace",
        ):
            assert counts[target] == 1, (
                f"happy-path invocation count for {target!r} is "
                f"{counts[target]}, expected exactly 1"
            )

    def test_both_proposal_validators_receive_same_exact_proposal(self):
        """PR55 and PR56 must inspect the same exact proposal content.
        The example must not fork the proposal into two different
        mutable copies before validation."""
        _, _, captured = _run_with_spies()
        pr55 = captured["validate_llm_proposal_shape"]
        pr56 = captured["validate_proposal_safety"]
        assert pr55 and pr56
        # signature: validate_*(proposal, source_packet) — proposal is
        # the first positional argument.
        pr55_proposal = pr55[0][0][0]
        pr56_proposal = pr56[0][0][0]
        assert pr55_proposal == pr56_proposal, (
            "PR55 and PR56 must inspect the same proposal content"
        )


# ===========================================================================
# X. Extended input immutability — R-U (266차)
# ===========================================================================


class TestExtendedInputImmutability:
    """Extend U's PR64/PR61 immutability to:
      - manual proposal fixture
      - downstream result fixture
      - candidate/request/receipt argument records (no-alias lock)
    """

    def test_pr64_adapter_trace_value_equality_with_freshly_loaded(self):
        """The example must consume the actual on-disk PR64 trace,
        not a hand-copied dict literal of equal shape. We verify by
        loading the artifact fresh and comparing with what the
        example's report records as having consumed."""
        report, _, _ = _run_with_spies()
        consumed = report["lanes"]["external_ingress"].get(
            "consumed_adapter_trace",
        )
        assert consumed is not None, (
            "external_ingress report must record "
            "'consumed_adapter_trace' for PR64 value-equality lock"
        )
        adapter = _load_external_module(
            _ADAPTER_PATH, "minimal_external_adapter_example_X1",
        )
        assert consumed == adapter.RESOLVED_TRANSLATION_TRACE

    def test_pr61_role_example_value_equality_with_freshly_loaded(self):
        report, _, _ = _run_with_spies()
        consumed = report["lanes"]["external_ingress"].get(
            "consumed_role_example",
        )
        assert consumed is not None, (
            "external_ingress report must record "
            "'consumed_role_example' for PR61 value-equality lock"
        )
        role = _load_external_module(
            _ROLE_EXAMPLE_PATH, "minimal_consumer_example_X2",
        )
        assert consumed == role.RESOLVED_EXAMPLE

    def test_proposal_fixture_unchanged_after_operation(self):
        """The proposal object PR55 saw at call time must be value-
        equal to the proposal object PR56 saw, and value-equal to
        the report's record of the consumed proposal after the
        operation completes."""
        report, _, captured = _run_with_spies()
        pr55 = captured["validate_llm_proposal_shape"]
        pr56 = captured["validate_proposal_safety"]
        assert pr55 and pr56
        # Both validators got deepcopy snapshots at call time; both
        # must match.
        assert pr55[0][0][0] == pr56[0][0][0]
        # The post-operation report's recorded proposal must also
        # match the value the validators saw at call time.
        recorded = report["lanes"]["engine_read_and_proposal"][
            "proposal"
        ].get("proposal_content_snapshot")
        if recorded is not None:
            assert recorded == pr55[0][0][0]

    def test_downstream_source_fixture_unchanged_after_operation(self):
        """The downstream-result source fixture must be value-equal to
        a freshly-recorded snapshot after the operation completes.
        The example must expose a 'downstream_source_fixture_before'
        snapshot in the lane_c report so the test can compare it to
        the 'downstream_source_fixture_after' snapshot."""
        report, _, _ = _run_with_spies()
        lane_c = report["lanes"]["downstream_reentry"]
        before = lane_c.get("downstream_source_fixture_before")
        after = lane_c.get("downstream_source_fixture_after")
        assert before is not None
        assert after is not None
        assert before == after, (
            "downstream source fixture must not be mutated by the "
            "operation (no-alias / immutability lock)"
        )

    def test_result_trace_no_alias_with_downstream_fixture(self):
        """Mutating the result_trace's `result_fragment` value must
        not change the downstream source fixture (no shared mutable
        alias)."""
        report, _, _ = _run_with_spies()
        lane_c = report["lanes"]["downstream_reentry"]
        result_trace = lane_c["result_trace"]
        source_before = copy.deepcopy(
            lane_c.get("downstream_source_fixture_after"),
        )
        if isinstance(result_trace.get("result_fragment"), dict):
            result_trace["result_fragment"]["__test_marker__"] = "X"
        elif isinstance(result_trace.get("result_fragment"), list):
            result_trace["result_fragment"].append("__test_marker__")
        # downstream source must be unchanged
        source_after = lane_c.get("downstream_source_fixture_after")
        assert source_after == source_before, (
            "result_trace.result_fragment shares a mutable alias "
            "with the downstream source fixture"
        )

    def _walk(self, obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from self._walk(v)
        elif isinstance(obj, list):
            for x in obj:
                yield from self._walk(x)

    def test_candidate_request_receipt_arguments_no_mutable_alias(self):
        """For every invocation in every lane, the candidate's
        arguments dict, the approved_candidate_snapshot's arguments
        dict, the ReviewedMutationRequest's arguments dict, and the
        invocation receipt's reviewed-arguments dict must:
          - be value-equal (==)
          - be distinct objects (is-not)
        """
        report, _, _ = _run_with_spies()
        invocations = []
        for lane in report["lanes"].values():
            if isinstance(lane, dict):
                seq = lane.get("explicit_invocation_sequence")
                if seq:
                    invocations.extend(seq)
        assert invocations, "no explicit invocations found"
        for inv in invocations:
            candidate = inv.get("candidate")
            request = inv.get("reviewed_mutation_request")
            assert candidate is not None
            assert request is not None
            cand_args = candidate.get("arguments")
            snap_args = request["approved_candidate_snapshot"].get(
                "arguments",
            )
            req_args = request.get("arguments")
            inv_args = inv.get("arguments")
            assert cand_args is not None
            assert snap_args is not None
            assert req_args is not None
            assert inv_args is not None
            # value-equality across the four argument records
            assert cand_args == snap_args == req_args == inv_args
            # identity distinctness — no mutable alias
            ids = {id(cand_args), id(snap_args), id(req_args), id(inv_args)}
            assert len(ids) == 4, (
                "candidate.arguments, approved_candidate_snapshot."
                "arguments, request.arguments, and invocation.arguments "
                "must be four distinct dict objects (no mutable alias)"
            )

    def test_mutating_candidate_args_does_not_change_request_args(self):
        """Concrete no-alias verification: mutate one record's
        arguments and confirm the others are unchanged."""
        report, _, _ = _run_with_spies()
        invocations = []
        for lane in report["lanes"].values():
            if isinstance(lane, dict):
                seq = lane.get("explicit_invocation_sequence")
                if seq:
                    invocations.extend(seq)
        assert invocations
        inv = invocations[0]
        candidate = inv["candidate"]
        request = inv["reviewed_mutation_request"]
        snap = request["approved_candidate_snapshot"]
        req_before = copy.deepcopy(request["arguments"])
        snap_before = copy.deepcopy(snap["arguments"])
        candidate["arguments"]["__test_alias_marker__"] = "Y"
        assert request["arguments"] == req_before, (
            "mutating candidate.arguments leaked into request.arguments"
        )
        assert snap["arguments"] == snap_before, (
            "mutating candidate.arguments leaked into "
            "approved_candidate_snapshot.arguments"
        )


# ===========================================================================
# Y. Trace identity precision — construction-time lock (266차)
# ===========================================================================


class TestTraceIdentityConstructionTimeLock:
    """trace.source_state_identity must equal the Engine state
    identity at trace construction, NOT against the final post-Lane-C
    identity. The example records:
      - identity_before_trace_equal_to_source: bool
      - identity_after_trace_equal_to_source: bool
      - identity_before_equals_identity_after: bool  (read-only proof)
      - trace_identity_revision: int
      - final_engine_identity_revision: int  (in final_state)
    """

    def _block(self):
        report = _get_report()
        return report["lanes"]["engine_read_and_proposal"][
            "effective_confidence_trace"
        ]

    def test_trace_source_identity_equals_identity_before_trace(self):
        b = self._block()
        assert b.get("identity_before_trace_equal_to_source") is True

    def test_trace_source_identity_equals_identity_after_trace(self):
        b = self._block()
        assert b.get("identity_after_trace_equal_to_source") is True

    def test_identity_before_equals_identity_after_trace_call(self):
        """state_identity() is read-only (M04 §1.2); a trace call does
        not advance the revision."""
        b = self._block()
        assert b.get("identity_before_equals_identity_after") is True

    def test_final_engine_identity_not_equal_to_trace_identity(self):
        """The trace is captured during Lane B. Lane C performs
        further state mutations (add_evidence /
        resolve_gaps_for_evidence / confirm_claim_if_ready). The
        final engine identity revision must therefore exceed the
        trace identity revision; equality would be wrong (it would
        either mean Lane C performed no mutation, or the example
        compared against the wrong identity moment)."""
        report = _get_report()
        block = self._block()
        trace_rev = block.get("trace_identity_revision")
        final_rev = report["final_state"].get(
            "final_engine_identity_revision",
        )
        assert isinstance(trace_rev, int)
        assert isinstance(final_rev, int)
        assert trace_rev < final_rev, (
            f"final_engine_identity_revision ({final_rev}) must be "
            f"greater than trace_identity_revision ({trace_rev}); "
            "the trace identity must NOT be compared against the "
            "final post-Lane-C engine identity"
        )

    def test_trace_block_does_not_claim_final_identity_match(self):
        """The trace block must NOT carry a boolean asserting that
        trace.source_state_identity equals the final engine identity.
        Such a field would invert the contract."""
        b = self._block()
        for forbidden in (
            "source_identity_equals_final_engine_identity",
            "trace_identity_equals_final_engine_identity",
        ):
            assert forbidden not in b, (
                f"trace block must not assert {forbidden!r}; the "
                "trace identity is locked at construction time only"
            )


# ===========================================================================
# 271차 — Post-Draft authority-gate and final-verification locks.
#
# These tests are added AFTER the 269차 example exists. They are intentionally
# red against 3d15918 because the 269차 example records review/revalidation
# verdicts as advisory strings without using them to gate Engine invocation,
# its final block is a hardcoded boolean summary instead of an actual public
# Engine read, and it does not carry the contract's positive status
# vocabulary at the documented positions. Classes Z ~ AH lock those three
# defects (R-GATE / R-FINAL / R-STATUS) from the test side. The 272차 example
# implementation is expected to turn these green without weakening any of
# the 25 existing classes A ~ Y.
#
#   Z.  TestRoleValidationGate              — role violation → no mutation
#   AA. TestRejectedReviewSuppression       — rejected / hold → no mutation
#   AB. TestStage5_5SuppressionPerCycle     — Stage 5.5 not_eligible per cycle
#   AC. TestStage6SuppressionPerCycle       — Stage 6 not_eligible per cycle
#   AD. TestFinalPublicEngineReads          — get_entity/.../gap_resolution
#                                              actually invoked in final block
#   AE. TestFinalReadValueBinding           — final fields bound to lane IDs
#   AF. TestFinalNoHardcodedSummary         — AST evidence of actual reads
#   AG. TestFinalPacketClassification       — final == Lane B (UNBOUND+UNKNOWN)
#   AH. TestPositiveStatusVocabulary        — CONSUMER_DECISION/OPERATOR_REVIEW
#                                              /STATE_REVALIDATED/EXPLICIT_
#                                              INVOCATION/CONNECTED|COMPLETED
#                                              /BOUNDARY_PRESERVED
# ===========================================================================


# ---------------------------------------------------------------------------
# Helper utilities for 271차 authority-gate tests.
# ---------------------------------------------------------------------------


_MUTATION_METHOD_NAMES: tuple[str, ...] = (
    "add_entity",
    "add_claim",
    "add_gap",
    "add_evidence",
    "resolve_gaps_for_evidence",
    "confirm_claim_if_ready",
)


_READ_METHOD_NAMES: tuple[str, ...] = (
    "get_entity",
    "get_claim",
    "get_gap",
    "get_evidence",
    "gap_resolution",
)


# Cycle index → (engine method, dependent methods following it). The
# happy-path cycle order is fixed by M08 §6 / §14 (Lane A: add_entity →
# add_claim → add_gap; Lane C: add_evidence → resolve_gaps_for_evidence
# → confirm_claim_if_ready), so dependents always follow strict prefix
# order.
_CYCLE_DEFINITIONS: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (1, "add_entity", (
        "add_claim", "add_gap", "add_evidence",
        "resolve_gaps_for_evidence", "confirm_claim_if_ready",
    )),
    (2, "add_claim", (
        "add_gap", "add_evidence",
        "resolve_gaps_for_evidence", "confirm_claim_if_ready",
    )),
    (3, "add_gap", (
        "add_evidence",
        "resolve_gaps_for_evidence", "confirm_claim_if_ready",
    )),
    (4, "add_evidence", (
        "resolve_gaps_for_evidence", "confirm_claim_if_ready",
    )),
    (5, "resolve_gaps_for_evidence", (
        "confirm_claim_if_ready",
    )),
    (6, "confirm_claim_if_ready", ()),
)


def _install_engine_method_spies(
    method_names: tuple[str, ...],
) -> tuple[dict[str, int], dict[str, list[Any]], typing.Callable[[], None]]:
    """Install runtime call-count + argument-capture spies on the named
    Engine methods at the class level. Returns
    (call_counts, captured, restore_fn). restore_fn MUST be called in a
    finally block to undo the class-level patching."""
    call_counts: dict[str, int] = {n: 0 for n in method_names}
    captured: dict[str, list[Any]] = {n: [] for n in method_names}
    originals: dict[str, Any] = {}

    for name in method_names:
        orig = getattr(Engine, name)
        originals[name] = orig

        def make_spy(orig=orig, name=name):
            def spy(self, *args, **kwargs):
                call_counts[name] += 1
                try:
                    captured[name].append(
                        (copy.deepcopy(args), copy.deepcopy(kwargs)),
                    )
                except Exception:
                    captured[name].append(("<unpicklable>", {}))
                return orig(self, *args, **kwargs)
            spy.__name__ = name
            spy.__wrapped__ = orig
            return spy

        setattr(Engine, name, make_spy())

    def restore() -> None:
        for name, orig in originals.items():
            setattr(Engine, name, orig)

    return call_counts, captured, restore


def _run_with_engine_spies(
    method_names: tuple[str, ...],
    patches: dict[str, Any] | None = None,
) -> tuple[Any, Any, dict[str, int], dict[str, list[Any]]]:
    """Load a fresh example module, apply requested module-level
    monkeypatches, install Engine class spies on the requested method
    names, run the operation, then restore EVERY patch in a finally
    block — regardless of whether the operation raised.

    Returns (module, report_or_exception_marker, call_counts, captured).
    On exception, the second element is a sentinel dict
    {'__exception__': '<repr>'} so the caller can distinguish from a
    normal empty report.
    """
    module = _load_example_module()
    patch_records: list[tuple[Any, str, Any]] = []
    if patches:
        for name, new_value in patches.items():
            if not hasattr(module, name):
                pytest.skip(
                    "module-level attribute "
                    f"{name!r} not present in example",
                )
            patch_records.append((module, name, getattr(module, name)))
            setattr(module, name, new_value)
    call_counts, captured, restore_engine = _install_engine_method_spies(
        method_names,
    )
    try:
        try:
            report = module.run_complete_domain_neutral_reference_operation()
        except Exception as exc:
            report = {"__exception__": repr(exc)}
    finally:
        restore_engine()
        for mod, attr, orig in patch_records:
            setattr(mod, attr, orig)
    return module, report, call_counts, captured


def _make_role_violation_patch(violations: list[Any]):
    def patched(role_example):
        return list(violations)
    patched.__name__ = "validate_role_assignment_boundaries"
    return patched


def _make_review_patch(forced_disposition: str):
    def patched(approved: bool, note: str) -> str:
        return forced_disposition
    patched.__name__ = "_explicit_review"
    return patched


def _make_revalidate_patch(
    target_moment: str, target_call_index: int,
):
    """Returns a patched _revalidate that returns not_eligible on the
    `target_call_index`-th invocation of `target_moment` (1-based,
    counting only calls whose moment matches target_moment), and
    delegates the original eligibility computation for every other
    call. The cycle order in the current happy path is fixed by M08
    §6 / §14, so the K-th call for a given moment corresponds to
    cycle K."""
    state = {"counts_by_moment": {}}

    def patched(decision_identity, current_identity, moment):
        state["counts_by_moment"][moment] = (
            state["counts_by_moment"].get(moment, 0) + 1
        )
        eligible = decision_identity == current_identity
        verdict = "eligible" if eligible else "not_eligible"
        if (
            moment == target_moment
            and state["counts_by_moment"][moment] == target_call_index
        ):
            verdict = "not_eligible"
        return {
            "moment": moment,
            "decision_state_identity": copy.deepcopy(decision_identity),
            "current_state_identity": copy.deepcopy(current_identity),
            "verdict": verdict,
        }

    patched.__name__ = "_revalidate"
    return patched


def _collect_invocation_records(report: Any) -> list[dict]:
    """Collect every per-cycle invocation record from the report,
    across every lane's `explicit_invocation_sequence`. Returns []
    when no recognizable lane structure is present (which is itself
    a meaningful signal — the calling test interprets it)."""
    if not isinstance(report, dict):
        return []
    out: list[dict] = []
    lanes = report.get("lanes", {})
    if isinstance(lanes, dict):
        for lane in lanes.values():
            if not isinstance(lane, dict):
                continue
            seq = lane.get("explicit_invocation_sequence", [])
            if isinstance(seq, list):
                for entry in seq:
                    if isinstance(entry, dict):
                        out.append(entry)
    return out


def _ids_seen_in_capture(
    captured: dict[str, list[Any]], name: str,
) -> set[int]:
    """Collect every int value that was passed as a positional or
    keyword argument to the spied method `name`."""
    seen: set[int] = set()
    for args, kwargs in captured.get(name, []):
        if isinstance(args, tuple):
            for v in args:
                if isinstance(v, int) and not isinstance(v, bool):
                    seen.add(v)
        if isinstance(kwargs, dict):
            for v in kwargs.values():
                if isinstance(v, int) and not isinstance(v, bool):
                    seen.add(v)
    return seen


# ---------------------------------------------------------------------------
# Phase-isolated final-block spy infrastructure (271차 R-FINAL correction).
#
# The first 271차 cut wrapped Engine.get_* spies around the WHOLE operation,
# which let two incidental calls (compute_effective_confidence's internal
# get_claim; Engine internals' gap_resolution) satisfy "called at least
# once". The corrected design installs the spy ONLY for the lifetime of the
# example's `_final_state` helper, so reads that happened in Lane B / Engine
# internals BEFORE `_final_state` was entered are NOT counted as final-block
# verification evidence. `_final_state` is pinned as the canonical final-
# verification helper; a future refactor that renames it must update the
# helper-name lookup here.
# ---------------------------------------------------------------------------


def _require_final_state_callable(module) -> Any:
    """Return module._final_state or fail the test with a clear message."""
    if not hasattr(module, "_final_state"):
        pytest.fail(
            "example module must expose a module-level `_final_state` "
            "callable as the canonical final-verification helper; the "
            "271차 R-FINAL locks wrap this helper to count only reads "
            "that occur from within it",
        )
    return module._final_state


def _run_with_final_phase_spies(
    method_names: tuple[str, ...],
) -> tuple[
    Any, Any, dict[str, int], dict[str, list[Any]], dict[str, list[Any]],
]:
    """Run the operation with Engine class spies on `method_names`
    installed ONLY during the lifetime of `_final_state`. Returns
    (module, report_or_exception, final_counts, final_captured,
    final_returns). final_returns[name] is the list of return values
    observed for the spy on `name` (used by derivation tests).

    Reads that happen outside `_final_state` (e.g. in Lane B or inside
    Engine internals running before `_final_state` is entered) are
    NOT counted."""
    module = _load_example_module()
    original_final_state = _require_final_state_callable(module)

    final_counts: dict[str, int] = {n: 0 for n in method_names}
    final_captured: dict[str, list[Any]] = {n: [] for n in method_names}
    final_returns: dict[str, list[Any]] = {n: [] for n in method_names}

    def wrapped_final_state(*args, **kwargs):
        originals: dict[str, Any] = {}
        for name in method_names:
            originals[name] = getattr(Engine, name)

            def make_spy(name=name, orig=originals[name]):
                def spy(self, *a, **kw):
                    final_counts[name] += 1
                    try:
                        final_captured[name].append(
                            (copy.deepcopy(a), copy.deepcopy(kw)),
                        )
                    except Exception:
                        final_captured[name].append(("<unpicklable>", {}))
                    result = orig(self, *a, **kw)
                    try:
                        final_returns[name].append(copy.deepcopy(result))
                    except Exception:
                        final_returns[name].append(result)
                    return result
                spy.__name__ = name
                spy.__wrapped__ = orig
                return spy

            setattr(Engine, name, make_spy())
        try:
            return original_final_state(*args, **kwargs)
        finally:
            for name, orig in originals.items():
                setattr(Engine, name, orig)

    setattr(module, "_final_state", wrapped_final_state)
    try:
        try:
            report = module.run_complete_domain_neutral_reference_operation()
        except Exception as exc:
            report = {"__exception__": repr(exc)}
    finally:
        setattr(module, "_final_state", original_final_state)
    return module, report, final_counts, final_captured, final_returns


class _AttrAccessTracker:
    """Wraps an arbitrary object and records every attribute access
    performed on it (other than the three private bookkeeping attrs).
    The wrapped object's actual attribute is returned, and equality
    / hash / repr delegate to the wrapped value.

    Used by the claim_status derivation lock: wrapping the result of
    Engine.get_claim with a tracker lets the test prove that
    `_final_state` actually accessed `.status` on the returned Claim,
    rather than synthesizing the value from a hardcoded constant or
    from the confirm_claim_if_ready() return flag."""

    def __init__(self, wrapped):
        self._wrapped = wrapped
        self._accessed_attrs: list[str] = []
        self._returned_values: dict[str, Any] = {}

    def __getattr__(self, name):
        # __getattr__ fires only when normal attribute lookup misses,
        # so `_wrapped` / `_accessed_attrs` / `_returned_values` are
        # resolved directly and never re-enter this path.
        v = getattr(self._wrapped, name)
        self._accessed_attrs.append(name)
        self._returned_values[name] = v
        return v

    def __eq__(self, other):
        if isinstance(other, _AttrAccessTracker):
            return self._wrapped == other._wrapped
        return self._wrapped == other

    def __hash__(self):
        return hash(self._wrapped)

    def __repr__(self):
        return repr(self._wrapped)


def _run_with_get_claim_proxy_in_final_state() -> tuple[Any, list[Any]]:
    """Run the operation with Engine.get_claim wrapped — ONLY during
    `_final_state` — so the returned Claim is an _AttrAccessTracker.

    Returns (report, trackers) where trackers is a list of
    (claim_id_arg, tracker) tuples for each get_claim call observed
    inside `_final_state`."""
    module = _load_example_module()
    original_final_state = _require_final_state_callable(module)
    trackers: list[tuple[int, _AttrAccessTracker]] = []
    original_get_claim = Engine.get_claim

    def proxy_get_claim(self, claim_id):
        result = original_get_claim(self, claim_id)
        tracker = _AttrAccessTracker(result)
        trackers.append((claim_id, tracker))
        return tracker

    def wrapped_final_state(*args, **kwargs):
        Engine.get_claim = proxy_get_claim
        try:
            return original_final_state(*args, **kwargs)
        finally:
            Engine.get_claim = original_get_claim

    setattr(module, "_final_state", wrapped_final_state)
    try:
        try:
            report = module.run_complete_domain_neutral_reference_operation()
        except Exception as exc:
            report = {"__exception__": repr(exc)}
    finally:
        setattr(module, "_final_state", original_final_state)
    return report, trackers


def _final_state_function_node() -> ast.FunctionDef | None:
    """Return the top-level FunctionDef AST node for `_final_state`
    in the example source. Returns None when the function is absent
    so callers can fail with their own message."""
    src = _example_source()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_final_state":
            return node
    return None


def _attribute_method_names_called_in(func: ast.FunctionDef) -> set[str]:
    """Set of attribute names invoked as `<something>.<name>(...)`
    anywhere inside `func`'s body (e.g. `engine.get_claim(...)` →
    {'get_claim'} and `engine.state_identity()` → {'state_identity'})."""
    names: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            func_expr = node.func
            if isinstance(func_expr, ast.Attribute):
                names.add(func_expr.attr)
    return names


# ---------------------------------------------------------------------------
# Gate-path evidence helpers (271-corr2).
# ---------------------------------------------------------------------------


def _collect_report_values(obj: Any, key_name: str) -> list[Any]:
    """Recursively collect every value stored under `key_name` anywhere
    in a nested dict / list structure. Lets the gate tests assert the
    PRESENCE of a specifically-named field (e.g. termination_stage)
    without fixing where in the report tree the example chooses to put
    it."""
    found: list[Any] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key_name:
                found.append(v)
            found.extend(_collect_report_values(v, key_name))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            found.extend(_collect_report_values(item, key_name))
    return found


def _preceding_cycle_methods(target_method: str) -> tuple[str, ...]:
    """Mutation methods that, per the fixed M08 §6 / §14 cycle order,
    must each have been invoked exactly once before `target_method`
    is reached. Derived from _CYCLE_DEFINITIONS so the two never drift
    apart."""
    order = [d[1] for d in _CYCLE_DEFINITIONS]
    idx = order.index(target_method)
    return tuple(order[:idx])


def _find_cycle_records(report: Any, target_method: str) -> list[dict]:
    """Every invocation record across all lanes whose target_method
    equals `target_method`."""
    return [
        inv for inv in _collect_invocation_records(report)
        if inv.get("target_method") == target_method
    ]


def _matching_returns_for_expected_id(
    captured: list[Any], returns: list[Any], expected_id: int,
) -> list[Any]:
    """Pair captured (args, kwargs) with their positionally-aligned
    return value and keep only the returns whose call included
    `expected_id` among its int arguments."""
    matching: list[Any] = []
    for (args, kwargs), result in zip(captured, returns):
        arg_ids = [
            v for v in tuple(args) + tuple(kwargs.values())
            if isinstance(v, int) and not isinstance(v, bool)
        ]
        if expected_id in arg_ids:
            matching.append(result)
    return matching


def _assert_cycle_succeeded(
    report: Any, method: str, target_method: str,
) -> None:
    """Assert that the cycle for `method` fully succeeded in the
    report: exactly one record, a call_receipt present (its Engine
    method was actually invoked), and both revalidations 'eligible'.
    Report-record based so the negative probes' throwaway
    Engine.add_entity calls do not pollute the proof."""
    records = _find_cycle_records(report, method)
    assert len(records) == 1, (
        f"preceding cycle {method!r} (before target {target_method!r}) "
        f"must have exactly one invocation record; found {len(records)}"
    )
    rec = records[0]
    assert rec.get("call_receipt"), (
        f"preceding cycle {method!r} must carry a call_receipt proving "
        f"its Engine method was actually invoked before reaching "
        f"{target_method!r}; this rules out an early termination that "
        "never reached the targeted cycle"
    )
    revs = rec.get("revalidations", {})
    assert isinstance(revs, dict)
    for moment in ("stage_5_5_materialization", "stage_6_invocation"):
        rev = revs.get(moment)
        assert isinstance(rev, dict) and rev.get("verdict") == "eligible", (
            f"preceding cycle {method!r} must have an 'eligible' "
            f"{moment} verdict; got: {rev!r}"
        )


# ===========================================================================
# Z. Role validation must actually gate execution
# ===========================================================================


class TestRoleValidationGate:
    """When validate_role_assignment_boundaries returns a non-empty
    violation list, the example must abort the operation BEFORE any
    Engine mutation. It must not declare COMPLETE_REFERENCE_OPERATION,
    must not materialize any ReviewedMutationRequest, and must not
    record any call receipt."""

    _FORCED_VIOLATIONS = [("role_assignment", "forced test violation")]

    def _patches(self) -> dict[str, Any]:
        return {
            "validate_role_assignment_boundaries":
                _make_role_violation_patch(self._FORCED_VIOLATIONS),
        }

    def test_role_violation_blocks_every_mutation(self):
        _skip_if_no_example()
        _, _, calls, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=self._patches(),
        )
        for name in _MUTATION_METHOD_NAMES:
            assert calls[name] == 0, (
                f"role validation failure must suppress Engine.{name}; "
                f"observed call_count={calls[name]}"
            )

    def test_role_violation_returns_termination_report_not_exception(self):
        _skip_if_no_example()
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=self._patches(),
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(
                "role validation failure must produce a local "
                "termination report rather than an uncaught "
                f"exception: {report['__exception__']}"
            )
        assert isinstance(report, dict)
        assert report.get("overall_status") != "COMPLETE_REFERENCE_OPERATION", (
            "role-failed run must not declare "
            "overall_status == 'COMPLETE_REFERENCE_OPERATION'"
        )

    def test_role_violation_preserved_in_termination_report(self):
        _skip_if_no_example()
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=self._patches(),
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.skip("role-failed run raised; see other test")
        serialized = _serialize_for_scan(report)
        assert "forced test violation" in serialized, (
            "termination report must preserve the injected role "
            "violation so the reason for termination is visible"
        )

    def test_role_violation_yields_no_reviewed_request_or_receipt(self):
        _skip_if_no_example()
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=self._patches(),
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.skip("role-failed run raised; see other test")
        invocations = _collect_invocation_records(report)
        for inv in invocations:
            assert not inv.get("reviewed_mutation_request"), (
                "role-failed run must not materialize a "
                f"ReviewedMutationRequest; got: {inv.get('reviewed_mutation_request')!r}"
            )
            assert not inv.get("call_receipt"), (
                "role-failed run must not produce a call_receipt; "
                f"got: {inv.get('call_receipt')!r}"
            )

    # --- 271-corr2 G-ROLE-POSITION ---

    def test_role_violation_sets_termination_stage(self):
        """The termination must be reported through an explicit
        `termination_stage` field whose text identifies role
        validation — not merely by flipping overall_status. The
        violation text incidentally surviving inside source_basis is
        NOT sufficient evidence of where the run stopped."""
        _skip_if_no_example()
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=self._patches(),
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(f"role-failed run raised: {report['__exception__']}")
        stages = _collect_report_values(report, "termination_stage")
        assert stages, (
            "role-failed run must expose an explicit `termination_stage` "
            "field in the report; flipping overall_status alone is not "
            "sufficient"
        )
        role_identifying = [
            s for s in stages
            if isinstance(s, str)
            and "role" in s.lower()
            and "validation" in s.lower()
        ]
        assert role_identifying, (
            "at least one `termination_stage` value must identify role "
            "validation (lowercase must contain both 'role' and "
            f"'validation'); observed termination_stage values: {stages!r}"
        )

    def test_role_violation_sets_termination_reason(self):
        """The termination must carry an explicit `termination_reason`
        field that preserves the injected violation text. This is
        stronger than the whole-report serialized scan, which would
        pass on an incidental source_basis copy."""
        _skip_if_no_example()
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=self._patches(),
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(f"role-failed run raised: {report['__exception__']}")
        reasons = _collect_report_values(report, "termination_reason")
        assert reasons, (
            "role-failed run must expose an explicit `termination_reason` "
            "field in the report"
        )
        preserving = [
            r for r in reasons
            if "forced test violation" in _serialize_for_scan(r)
        ]
        assert preserving, (
            "at least one `termination_reason` value must preserve the "
            "injected violation text 'forced test violation'; observed "
            f"termination_reason values: {reasons!r}"
        )


# ===========================================================================
# AA. Rejected / hold dispositions must suppress invocation
# ===========================================================================


class TestRejectedReviewSuppression:
    """When _explicit_review yields a rejected or hold disposition,
    the example must NOT materialize a ReviewedMutationRequest, must
    NOT call any Engine mutation, and must preserve the disposition
    text in the termination report."""

    @pytest.mark.parametrize("disposition", ["rejected", "hold"])
    def test_non_approved_review_blocks_every_mutation(self, disposition):
        _skip_if_no_example()
        patches = {"_explicit_review": _make_review_patch(disposition)}
        _, _, calls, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=patches,
        )
        for name in _MUTATION_METHOD_NAMES:
            assert calls[name] == 0, (
                f"disposition={disposition!r} must suppress "
                f"Engine.{name}; observed call_count={calls[name]}"
            )

    @pytest.mark.parametrize("disposition", ["rejected", "hold"])
    def test_non_approved_review_returns_termination_report(
        self, disposition,
    ):
        _skip_if_no_example()
        patches = {"_explicit_review": _make_review_patch(disposition)}
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=patches,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(
                f"disposition={disposition!r} must produce a "
                "termination report rather than an uncaught "
                f"exception: {report['__exception__']}"
            )
        assert isinstance(report, dict)
        assert report.get("overall_status") != "COMPLETE_REFERENCE_OPERATION"
        serialized = _serialize_for_scan(report)
        assert disposition in serialized, (
            "termination report must preserve the "
            f"{disposition!r} disposition that blocked the cycle"
        )

    @pytest.mark.parametrize("disposition", ["rejected", "hold"])
    def test_non_approved_review_yields_no_request_or_receipt(
        self, disposition,
    ):
        _skip_if_no_example()
        patches = {"_explicit_review": _make_review_patch(disposition)}
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=patches,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.skip(
                f"disposition={disposition!r} raised; see other test",
            )
        invocations = _collect_invocation_records(report)
        for inv in invocations:
            assert not inv.get("reviewed_mutation_request"), (
                f"disposition={disposition!r} must not materialize a "
                f"ReviewedMutationRequest; got: "
                f"{inv.get('reviewed_mutation_request')!r}"
            )
            assert not inv.get("call_receipt"), (
                f"disposition={disposition!r} must not produce a "
                f"call_receipt; got: {inv.get('call_receipt')!r}"
            )

    # --- 271-corr2 G-REACH (add_entity decision record) ---

    @pytest.mark.parametrize("disposition", ["rejected", "hold"])
    def test_non_approved_review_records_add_entity_decision(
        self, disposition,
    ):
        """The run must actually REACH the first mutation cycle
        (add_entity), materialize its candidate and operator decision
        record carrying the injected disposition, and then stop — with
        no request and no receipt — rather than terminating before the
        cycle is even formed. Locating the disposition string anywhere
        in the report is not sufficient; it must be the disposition of
        the add_entity cycle's operator_decision_record."""
        _skip_if_no_example()
        patches = {"_explicit_review": _make_review_patch(disposition)}
        _, report, calls, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=patches,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(
                f"disposition={disposition!r} raised: "
                f"{report['__exception__']}"
            )
        for name in _MUTATION_METHOD_NAMES:
            assert calls[name] == 0, (
                f"disposition={disposition!r} must suppress Engine.{name}"
            )
        records = _find_cycle_records(report, "add_entity")
        assert len(records) == 1, (
            "exactly one add_entity cycle record must exist (the run "
            "must reach the first cycle before the disposition blocks "
            f"it); found {len(records)}"
        )
        rec = records[0]
        assert rec.get("candidate"), (
            "add_entity cycle must materialize a candidate before review"
        )
        odr = rec.get("operator_decision_record")
        assert isinstance(odr, dict), (
            "add_entity cycle must carry an operator_decision_record"
        )
        assert odr.get("disposition") == disposition, (
            "add_entity operator_decision_record.disposition must equal "
            f"the injected {disposition!r}; got: {odr.get('disposition')!r}"
        )
        assert not rec.get("reviewed_mutation_request"), (
            f"disposition={disposition!r} must not materialize the "
            "add_entity ReviewedMutationRequest"
        )
        assert not rec.get("call_receipt"), (
            f"disposition={disposition!r} must not produce the "
            "add_entity call_receipt"
        )


# ===========================================================================
# AB. Stage 5.5 (materialization) revalidation must gate request creation
# ===========================================================================


class TestStage5_5SuppressionPerCycle:
    """When _revalidate returns not_eligible for the
    stage_5_5_materialization moment of cycle K, the example must NOT
    materialize cycle K's ReviewedMutationRequest, must NOT call
    cycle K's Engine method, and must NOT call any cycle that depends
    on K's success."""

    @pytest.mark.parametrize(
        "cycle_index,target_method,dependents",
        _CYCLE_DEFINITIONS,
        ids=[d[1] for d in _CYCLE_DEFINITIONS],
    )
    def test_stage_5_5_failure_suppresses_target_and_dependents(
        self, cycle_index, target_method, dependents,
    ):
        _skip_if_no_example()
        patches = {
            "_revalidate": _make_revalidate_patch(
                "stage_5_5_materialization", cycle_index,
            ),
        }
        _, _, calls, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=patches,
        )
        assert calls[target_method] == 0, (
            f"Stage 5.5 not_eligible for cycle {cycle_index} "
            f"({target_method}) must suppress Engine.{target_method}; "
            f"observed call_count={calls[target_method]}"
        )
        for dep in dependents:
            assert calls[dep] == 0, (
                f"cycle {target_method} suppressed at Stage 5.5; "
                f"dependent Engine.{dep} must not be invoked either; "
                f"observed call_count={calls[dep]}"
            )

    @pytest.mark.parametrize(
        "cycle_index,target_method,dependents",
        _CYCLE_DEFINITIONS,
        ids=[d[1] for d in _CYCLE_DEFINITIONS],
    )
    def test_stage_5_5_failure_omits_request_and_receipt(
        self, cycle_index, target_method, dependents,
    ):
        _skip_if_no_example()
        patches = {
            "_revalidate": _make_revalidate_patch(
                "stage_5_5_materialization", cycle_index,
            ),
        }
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=patches,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(
                f"Stage 5.5 not_eligible for cycle {cycle_index} "
                f"({target_method}) must produce a termination report "
                f"rather than raise: {report['__exception__']}"
            )
        assert isinstance(report, dict)
        assert report.get("overall_status") != "COMPLETE_REFERENCE_OPERATION"
        invocations = _collect_invocation_records(report)
        # No invocation entry may carry both target_method AND a
        # populated reviewed_mutation_request — Stage 5.5 suppression
        # must omit materialization of the request entirely.
        bad_with_request = [
            inv for inv in invocations
            if inv.get("target_method") == target_method
            and inv.get("reviewed_mutation_request")
        ]
        assert not bad_with_request, (
            f"Stage 5.5 suppression for cycle {target_method} must "
            "omit reviewed_mutation_request; offending entries: "
            f"{bad_with_request}"
        )
        bad_with_receipt = [
            inv for inv in invocations
            if inv.get("target_method") == target_method
            and inv.get("call_receipt")
        ]
        assert not bad_with_receipt, (
            f"Stage 5.5 suppression for cycle {target_method} must "
            "omit call_receipt; offending entries: "
            f"{bad_with_receipt}"
        )
        # Likewise no dependent cycle may produce a call_receipt.
        for dep in dependents:
            dep_with_receipt = [
                inv for inv in invocations
                if inv.get("target_method") == dep
                and inv.get("call_receipt")
            ]
            assert not dep_with_receipt, (
                f"dependent cycle {dep!r} of suppressed "
                f"{target_method!r} must not produce a call_receipt; "
                f"offending entries: {dep_with_receipt}"
            )

    # --- 271-corr2 G-REACH (preceding cycles succeeded) ---

    @pytest.mark.parametrize(
        "cycle_index,target_method,dependents",
        _CYCLE_DEFINITIONS,
        ids=[d[1] for d in _CYCLE_DEFINITIONS],
    )
    def test_stage_5_5_preceding_cycles_succeeded(
        self, cycle_index, target_method, dependents,
    ):
        """The injected Stage 5.5 failure must land on cycle K only
        AFTER every preceding cycle actually succeeded — each preceding
        cycle must have exactly one record carrying a call_receipt
        (proof its Engine method was invoked) and both revalidations
        eligible. This rules out a run that terminates early at an
        earlier cycle and never reaches the targeted one.

        The proof reads the report's per-cycle records, NOT class-level
        spy counts, because the negative probes invoke Engine.add_entity
        on throwaway engines and would pollute a raw add_entity count."""
        _skip_if_no_example()
        patches = {
            "_revalidate": _make_revalidate_patch(
                "stage_5_5_materialization", cycle_index,
            ),
        }
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=patches,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(
                f"Stage 5.5 cycle {cycle_index} ({target_method}) "
                f"raised: {report['__exception__']}"
            )
        for prev in _preceding_cycle_methods(target_method):
            _assert_cycle_succeeded(report, prev, target_method)

    # --- 271-corr2 G-REACH (target cycle artifact shape) ---

    @pytest.mark.parametrize(
        "cycle_index,target_method,dependents",
        _CYCLE_DEFINITIONS,
        ids=[d[1] for d in _CYCLE_DEFINITIONS],
    )
    def test_stage_5_5_target_cycle_artifacts(
        self, cycle_index, target_method, dependents,
    ):
        """The targeted cycle record must show that the run formed the
        candidate and an approved operator decision, then recorded the
        Stage 5.5 not_eligible verdict and stopped — with no request,
        no Stage 6 revalidation, and no receipt."""
        _skip_if_no_example()
        patches = {
            "_revalidate": _make_revalidate_patch(
                "stage_5_5_materialization", cycle_index,
            ),
        }
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=patches,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(
                f"Stage 5.5 cycle {cycle_index} ({target_method}) "
                f"raised: {report['__exception__']}"
            )
        records = _find_cycle_records(report, target_method)
        assert len(records) == 1, (
            f"exactly one {target_method} cycle record must exist; "
            f"found {len(records)}"
        )
        rec = records[0]
        assert rec.get("candidate"), (
            f"{target_method} cycle must form a candidate before review"
        )
        odr = rec.get("operator_decision_record")
        assert isinstance(odr, dict), (
            f"{target_method} cycle must carry an operator_decision_record"
        )
        assert odr.get("disposition") == "approved", (
            f"{target_method} operator decision must be 'approved' "
            "(the block is Stage 5.5, not the review step); got: "
            f"{odr.get('disposition')!r}"
        )
        revs = rec.get("revalidations", {})
        assert isinstance(revs, dict)
        s55 = revs.get("stage_5_5_materialization")
        assert isinstance(s55, dict), (
            f"{target_method} cycle must record a "
            "stage_5_5_materialization revalidation"
        )
        assert s55.get("verdict") == "not_eligible", (
            f"{target_method} stage_5_5_materialization verdict must be "
            f"preserved as 'not_eligible'; got: {s55.get('verdict')!r}"
        )
        assert not rec.get("reviewed_mutation_request"), (
            f"{target_method} Stage 5.5 failure must omit the "
            "ReviewedMutationRequest"
        )
        assert not revs.get("stage_6_invocation"), (
            f"{target_method} Stage 5.5 failure must not reach the "
            "stage_6_invocation revalidation"
        )
        assert not rec.get("call_receipt"), (
            f"{target_method} Stage 5.5 failure must omit the call_receipt"
        )


# ===========================================================================
# AC. Stage 6 (invocation) revalidation must gate Engine call
# ===========================================================================


class TestStage6SuppressionPerCycle:
    """When _revalidate returns not_eligible for the stage_6_invocation
    moment of cycle K (after Stage 5.5 had already returned eligible),
    the example must NOT call cycle K's Engine method and must NOT
    call any cycle that depends on K's success. The candidate, the
    operator decision, AND the ReviewedMutationRequest for cycle K
    may still appear in the report (their materialization preceded
    Stage 6), but the call receipt must NOT."""

    @pytest.mark.parametrize(
        "cycle_index,target_method,dependents",
        _CYCLE_DEFINITIONS,
        ids=[d[1] for d in _CYCLE_DEFINITIONS],
    )
    def test_stage_6_failure_suppresses_target_and_dependents(
        self, cycle_index, target_method, dependents,
    ):
        _skip_if_no_example()
        patches = {
            "_revalidate": _make_revalidate_patch(
                "stage_6_invocation", cycle_index,
            ),
        }
        _, _, calls, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=patches,
        )
        assert calls[target_method] == 0, (
            f"Stage 6 not_eligible for cycle {cycle_index} "
            f"({target_method}) must suppress Engine.{target_method}; "
            f"observed call_count={calls[target_method]}"
        )
        for dep in dependents:
            assert calls[dep] == 0, (
                f"cycle {target_method} suppressed at Stage 6; "
                f"dependent Engine.{dep} must not be invoked either; "
                f"observed call_count={calls[dep]}"
            )

    @pytest.mark.parametrize(
        "cycle_index,target_method,dependents",
        _CYCLE_DEFINITIONS,
        ids=[d[1] for d in _CYCLE_DEFINITIONS],
    )
    def test_stage_6_failure_omits_receipt_but_keeps_request(
        self, cycle_index, target_method, dependents,
    ):
        _skip_if_no_example()
        patches = {
            "_revalidate": _make_revalidate_patch(
                "stage_6_invocation", cycle_index,
            ),
        }
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=patches,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(
                f"Stage 6 not_eligible for cycle {cycle_index} "
                f"({target_method}) must produce a termination report "
                f"rather than raise: {report['__exception__']}"
            )
        assert isinstance(report, dict)
        assert report.get("overall_status") != "COMPLETE_REFERENCE_OPERATION"
        invocations = _collect_invocation_records(report)
        bad_with_receipt = [
            inv for inv in invocations
            if inv.get("target_method") == target_method
            and inv.get("call_receipt")
        ]
        assert not bad_with_receipt, (
            f"Stage 6 suppression for cycle {target_method} must "
            "omit call_receipt; offending entries: "
            f"{bad_with_receipt}"
        )
        for dep in dependents:
            dep_with_receipt = [
                inv for inv in invocations
                if inv.get("target_method") == dep
                and inv.get("call_receipt")
            ]
            assert not dep_with_receipt, (
                f"dependent cycle {dep!r} of Stage-6-suppressed "
                f"{target_method!r} must not produce a call_receipt; "
                f"offending entries: {dep_with_receipt}"
            )

    # --- 271-corr2 G-REACH (preceding cycles succeeded) ---

    @pytest.mark.parametrize(
        "cycle_index,target_method,dependents",
        _CYCLE_DEFINITIONS,
        ids=[d[1] for d in _CYCLE_DEFINITIONS],
    )
    def test_stage_6_preceding_cycles_succeeded(
        self, cycle_index, target_method, dependents,
    ):
        """The injected Stage 6 failure must land on cycle K only after
        every preceding cycle actually succeeded — each preceding cycle
        must have exactly one record carrying a call_receipt and both
        revalidations eligible (report-record based, not class-spy
        counts, to avoid negative-probe add_entity pollution)."""
        _skip_if_no_example()
        patches = {
            "_revalidate": _make_revalidate_patch(
                "stage_6_invocation", cycle_index,
            ),
        }
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=patches,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(
                f"Stage 6 cycle {cycle_index} ({target_method}) raised: "
                f"{report['__exception__']}"
            )
        for prev in _preceding_cycle_methods(target_method):
            _assert_cycle_succeeded(report, prev, target_method)

    # --- 271-corr2 G-STAGE6-ARTIFACT (full pre-invocation artifact) ---

    @pytest.mark.parametrize(
        "cycle_index,target_method,dependents",
        _CYCLE_DEFINITIONS,
        ids=[d[1] for d in _CYCLE_DEFINITIONS],
    )
    def test_stage_6_target_cycle_artifacts(
        self, cycle_index, target_method, dependents,
    ):
        """A Stage 6 failure happens AFTER request materialization, so
        the targeted cycle record must retain the full pre-invocation
        artifact chain — candidate, approved operator decision, a
        ReviewedMutationRequest whose approved_decision_record_id and
        target_method match the cycle, a Stage 5.5 'eligible' verdict,
        and a Stage 6 'not_eligible' verdict — while omitting only the
        call receipt."""
        _skip_if_no_example()
        patches = {
            "_revalidate": _make_revalidate_patch(
                "stage_6_invocation", cycle_index,
            ),
        }
        _, report, _, _ = _run_with_engine_spies(
            _MUTATION_METHOD_NAMES, patches=patches,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(
                f"Stage 6 cycle {cycle_index} ({target_method}) raised: "
                f"{report['__exception__']}"
            )
        records = _find_cycle_records(report, target_method)
        assert len(records) == 1, (
            f"exactly one {target_method} cycle record must exist; "
            f"found {len(records)}"
        )
        rec = records[0]
        assert rec.get("candidate"), (
            f"{target_method} cycle must form a candidate"
        )
        odr = rec.get("operator_decision_record")
        assert isinstance(odr, dict), (
            f"{target_method} cycle must carry an operator_decision_record"
        )
        assert odr.get("disposition") == "approved", (
            f"{target_method} operator decision must be 'approved'; "
            f"got: {odr.get('disposition')!r}"
        )
        rmr = rec.get("reviewed_mutation_request")
        assert isinstance(rmr, dict), (
            f"{target_method} Stage 6 failure must RETAIN the "
            "ReviewedMutationRequest (it was materialized before "
            "Stage 6 ran)"
        )
        assert rmr.get("approved_decision_record_id") == odr.get(
            "decision_record_id",
        ), (
            f"{target_method} request.approved_decision_record_id must "
            "match the operator decision's decision_record_id; got "
            f"{rmr.get('approved_decision_record_id')!r} vs "
            f"{odr.get('decision_record_id')!r}"
        )
        assert rmr.get("target_method") == target_method, (
            f"{target_method} request.target_method must equal the "
            f"cycle method; got {rmr.get('target_method')!r}"
        )
        revs = rec.get("revalidations", {})
        assert isinstance(revs, dict)
        s55 = revs.get("stage_5_5_materialization")
        assert isinstance(s55, dict) and s55.get("verdict") == "eligible", (
            f"{target_method} stage_5_5_materialization must be present "
            f"and 'eligible'; got: {s55!r}"
        )
        s6 = revs.get("stage_6_invocation")
        assert isinstance(s6, dict) and s6.get("verdict") == "not_eligible", (
            f"{target_method} stage_6_invocation must be present and "
            f"preserved as 'not_eligible'; got: {s6!r}"
        )
        assert not rec.get("call_receipt"), (
            f"{target_method} Stage 6 failure must omit the call_receipt"
        )


# ===========================================================================
# AD. Final verification block must invoke Engine public read API
# ===========================================================================


class TestFinalPublicEngineReads:
    """Each listed Engine public read API must be invoked AT LEAST ONCE
    FROM WITHIN the example's `_final_state` helper. The spy is installed
    only for the lifetime of `_final_state` so that incidental reads
    from Lane B or from inside Engine methods running BEFORE
    `_final_state` is entered (e.g. compute_effective_confidence's
    internal get_claim, Engine internals' gap_resolution after
    resolve_gaps_for_evidence) are NOT counted as final-verification
    evidence. state_identity() alone does not satisfy this requirement
    (M08 §15 / §16 + 271차 §7 / R-FINAL §1)."""

    def test_each_public_read_invoked_from_final_state(self):
        _skip_if_no_example()
        _, report, final_counts, _, _ = _run_with_final_phase_spies(
            _READ_METHOD_NAMES,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(
                "happy-path operation must not raise; got: "
                f"{report['__exception__']}"
            )
        for name in _READ_METHOD_NAMES:
            assert final_counts[name] >= 1, (
                f"final verification block (`_final_state`) must invoke "
                f"Engine.{name} at least once; observed in-final "
                f"call_count={final_counts[name]} (incidental reads from "
                "Lane B / Engine internals running BEFORE _final_state "
                "are intentionally NOT counted)"
            )

    def test_get_entity_called_with_lane_a_entity_id_in_final_state(self):
        _skip_if_no_example()
        _, report, _, final_captured, _ = _run_with_final_phase_spies(
            _READ_METHOD_NAMES,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(f"raised: {report['__exception__']}")
        lane_a = report.get("lanes", {}).get("external_ingress", {})
        entity_id = lane_a.get("produced_ids", {}).get("entity_id")
        assert isinstance(entity_id, int)
        assert entity_id in _ids_seen_in_capture(
            final_captured, "get_entity",
        ), (
            f"Engine.get_entity must be called with the Lane A "
            f"entity_id ({entity_id}) FROM WITHIN `_final_state`; "
            f"observed final-phase captured args: "
            f"{final_captured.get('get_entity')}"
        )

    def test_get_claim_called_with_lane_a_claim_id_in_final_state(self):
        _skip_if_no_example()
        _, report, _, final_captured, _ = _run_with_final_phase_spies(
            _READ_METHOD_NAMES,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(f"raised: {report['__exception__']}")
        lane_a = report.get("lanes", {}).get("external_ingress", {})
        claim_id = lane_a.get("produced_ids", {}).get("claim_id")
        assert isinstance(claim_id, int)
        assert claim_id in _ids_seen_in_capture(
            final_captured, "get_claim",
        ), (
            f"Engine.get_claim must be called with the Lane A claim_id "
            f"({claim_id}) FROM WITHIN `_final_state`; observed final-"
            f"phase captured args: {final_captured.get('get_claim')} "
            "(compute_effective_confidence's internal get_claim that "
            "fires earlier in Lane B does NOT satisfy this requirement)"
        )

    def test_get_gap_called_with_lane_a_gap_id_in_final_state(self):
        _skip_if_no_example()
        _, report, _, final_captured, _ = _run_with_final_phase_spies(
            _READ_METHOD_NAMES,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(f"raised: {report['__exception__']}")
        lane_a = report.get("lanes", {}).get("external_ingress", {})
        gap_id = lane_a.get("produced_ids", {}).get("gap_id")
        assert isinstance(gap_id, int)
        assert gap_id in _ids_seen_in_capture(
            final_captured, "get_gap",
        ), (
            f"Engine.get_gap must be called with the Lane A gap_id "
            f"({gap_id}) FROM WITHIN `_final_state`; observed final-"
            f"phase captured args: {final_captured.get('get_gap')}"
        )

    def test_get_evidence_called_with_lane_c_evidence_id_in_final_state(
        self,
    ):
        _skip_if_no_example()
        _, report, _, final_captured, _ = _run_with_final_phase_spies(
            _READ_METHOD_NAMES,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(f"raised: {report['__exception__']}")
        lane_c = report.get("lanes", {}).get("downstream_reentry", {})
        evidence_id = lane_c.get("produced_ids", {}).get("evidence_id")
        assert isinstance(evidence_id, int)
        assert evidence_id in _ids_seen_in_capture(
            final_captured, "get_evidence",
        ), (
            f"Engine.get_evidence must be called with the Lane C "
            f"evidence_id ({evidence_id}) FROM WITHIN `_final_state`; "
            f"observed final-phase captured args: "
            f"{final_captured.get('get_evidence')}"
        )

    def test_gap_resolution_called_with_lane_a_gap_id_in_final_state(self):
        _skip_if_no_example()
        _, report, _, final_captured, _ = _run_with_final_phase_spies(
            _READ_METHOD_NAMES,
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(f"raised: {report['__exception__']}")
        lane_a = report.get("lanes", {}).get("external_ingress", {})
        gap_id = lane_a.get("produced_ids", {}).get("gap_id")
        assert isinstance(gap_id, int)
        assert gap_id in _ids_seen_in_capture(
            final_captured, "gap_resolution",
        ), (
            f"Engine.gap_resolution must be called with the Lane A "
            f"gap_id ({gap_id}) FROM WITHIN `_final_state` to verify "
            f"the post-Lane-C resolution; observed final-phase "
            f"captured args: {final_captured.get('gap_resolution')} "
            "(internal gap_resolution calls fired by Engine while "
            "resolve_gaps_for_evidence was running do NOT satisfy "
            "this requirement)"
        )


# ===========================================================================
# AE. Final block must bind to actual reads, not boolean flags
# ===========================================================================


class TestFinalReadValueBinding:
    """The final verification block must record actual projections /
    actual-ID-equality evidence for each of {entity, claim, gap,
    evidence, gap_resolution, claim_status} — boolean success flags
    alone are not sufficient (271차 §8 / §9). The canonical anchor
    key is `final_state` (the 269차 example's own naming)."""

    def _final(self):
        report = _get_report()
        assert isinstance(report, dict)
        final = report.get("final_state")
        assert isinstance(final, dict), (
            "report must include a `final_state` dict that records "
            "actual end-of-run reads from the Engine"
        )
        return report, final

    def _lane_ids(self, report):
        lane_a = report.get("lanes", {}).get("external_ingress", {})
        lane_c = report.get("lanes", {}).get("downstream_reentry", {})
        ids_a = lane_a.get("produced_ids", {})
        ids_c = lane_c.get("produced_ids", {})
        return (
            ids_a.get("entity_id"),
            ids_a.get("claim_id"),
            ids_a.get("gap_id"),
            ids_c.get("evidence_id"),
        )

    def test_final_state_has_entity_read_projection(self):
        _skip_if_no_example()
        _, final = self._final()
        ent = final.get("entity")
        assert ent is not None and not isinstance(ent, bool), (
            "final_state['entity'] must hold a real projection of "
            "Engine.get_entity(entity_id); a True / False flag does "
            "not constitute final-state verification evidence"
        )

    def test_final_state_has_claim_read_projection(self):
        _skip_if_no_example()
        _, final = self._final()
        cl = final.get("claim")
        assert cl is not None and not isinstance(cl, bool), (
            "final_state['claim'] must hold a real projection of "
            "Engine.get_claim(claim_id); a True / False flag does "
            "not constitute final-state verification evidence"
        )

    def test_final_state_has_gap_read_projection(self):
        _skip_if_no_example()
        _, final = self._final()
        g = final.get("gap")
        assert g is not None and not isinstance(g, bool), (
            "final_state['gap'] must hold a real projection of "
            "Engine.get_gap(gap_id); a True / False flag does not "
            "constitute final-state verification evidence"
        )

    def test_final_state_has_evidence_read_projection(self):
        _skip_if_no_example()
        _, final = self._final()
        ev = final.get("evidence")
        assert ev is not None and not isinstance(ev, bool), (
            "final_state['evidence'] must hold a real projection of "
            "Engine.get_evidence(evidence_id); a True / False flag "
            "does not constitute final-state verification evidence"
        )

    def test_final_state_gap_resolution_equals_evidence_id(self):
        _skip_if_no_example()
        report, final = self._final()
        _, _, _, evidence_id = self._lane_ids(report)
        assert isinstance(evidence_id, int)
        gr = final.get("gap_resolution")
        assert not isinstance(gr, bool), (
            "final_state['gap_resolution'] must hold the integer "
            "evidence_id read from Engine.gap_resolution(gap_id); a "
            "True / False flag is not acceptable"
        )
        assert gr == evidence_id, (
            f"final_state['gap_resolution'] must equal the Lane C "
            f"evidence_id ({evidence_id}); got: {gr!r}"
        )

    def test_final_state_claim_status_equals_confirmed_constant(self):
        _skip_if_no_example()
        _, final = self._final()
        cs = final.get("claim_status")
        assert cs == ragcore.CLAIM_STATUS_CONFIRMED, (
            f"final_state['claim_status'] must equal "
            f"ragcore.CLAIM_STATUS_CONFIRMED "
            f"({ragcore.CLAIM_STATUS_CONFIRMED}) read from "
            "Engine.get_claim(claim_id).status; a hardcoded "
            "'\"CONFIRMED\"' string is not sufficient. "
            f"got: {cs!r}"
        )

    # --- 271차 R-FINAL §3 — derivation locks ---
    # The two tests below prove that the claim_status value AND the
    # gap_resolution value carried by `final_state` came from real
    # Engine reads performed FROM WITHIN `_final_state`, not from a
    # hardcoded constant and not from the confirm_claim_if_ready()
    # return flag. `test_final_state_claim_status_..._constant` above
    # checks the numeric value; these two tests check the source path
    # of the value.

    def test_final_state_claim_status_derived_from_get_claim_in_final_state(
        self,
    ):
        """Wrap Engine.get_claim during `_final_state` so the returned
        Claim is an _AttrAccessTracker. Then assert: (a) get_claim was
        called inside `_final_state` for the Lane A claim_id; (b)
        `.status` was actually accessed on the returned Claim; and (c)
        the report's `final_state['claim_status']` equals the value
        observed via that access. A hardcoded
        `"claim_status": CLAIM_STATUS_CONFIRMED` cannot pass (a) and
        (b); a hardcoded value that incidentally equals the constant
        but is not derived from the read cannot pass (c)."""
        _skip_if_no_example()
        report, trackers = _run_with_get_claim_proxy_in_final_state()
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(f"raised: {report['__exception__']}")
        lane_a = report.get("lanes", {}).get("external_ingress", {})
        claim_id = lane_a.get("produced_ids", {}).get("claim_id")
        assert isinstance(claim_id, int)
        matching = [
            t for cid, t in trackers if cid == claim_id
        ]
        assert matching, (
            f"`_final_state` must call Engine.get_claim(claim_id="
            f"{claim_id}); observed get_claim calls inside _final_state "
            f"were on claim_ids: {[cid for cid, _ in trackers]!r}"
        )
        status_access_seen = any(
            "status" in t._accessed_attrs for t in matching
        )
        assert status_access_seen, (
            f"`_final_state` must access `.status` on the Claim "
            f"returned by Engine.get_claim(claim_id={claim_id}); "
            "this is the contract-locked source of "
            "final_state['claim_status']. Observed attribute accesses "
            f"on matching trackers: "
            f"{[t._accessed_attrs for t in matching]}"
        )
        observed_status_values = [
            t._returned_values["status"] for t in matching
            if "status" in t._returned_values
        ]
        assert observed_status_values, (
            "no `.status` value was captured on the wrapped Claim(s) — "
            "did `_final_state` access status before this test could "
            "observe it?"
        )
        final = report.get("final_state", {})
        fs_status = final.get("claim_status")
        assert fs_status in observed_status_values, (
            f"final_state['claim_status'] ({fs_status!r}) must equal "
            f"the `.status` value actually read from "
            f"Engine.get_claim(claim_id={claim_id}) during "
            f"`_final_state`; observed status values: "
            f"{observed_status_values!r}"
        )
        assert fs_status == ragcore.CLAIM_STATUS_CONFIRMED, (
            f"the read status must be ragcore.CLAIM_STATUS_CONFIRMED "
            f"({ragcore.CLAIM_STATUS_CONFIRMED}); got {fs_status!r}"
        )

    def test_final_state_gap_resolution_derived_from_gap_resolution_in_final_state(
        self,
    ):
        """Spy Engine.gap_resolution during `_final_state` only; assert
        that (a) gap_resolution was called for the Lane A gap_id, (b)
        one of its returns equals the Lane C evidence_id, and (c) the
        report's `final_state['gap_resolution']` equals that exact
        observed return — proving the value was derived from the read,
        not synthesized from the evidence_id elsewhere."""
        _skip_if_no_example()
        _, report, _, final_captured, final_returns = (
            _run_with_final_phase_spies(("gap_resolution",))
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(f"raised: {report['__exception__']}")
        lane_a = report.get("lanes", {}).get("external_ingress", {})
        gap_id = lane_a.get("produced_ids", {}).get("gap_id")
        lane_c = report.get("lanes", {}).get("downstream_reentry", {})
        evidence_id = lane_c.get("produced_ids", {}).get("evidence_id")
        assert isinstance(gap_id, int) and isinstance(evidence_id, int)

        captured = final_captured.get("gap_resolution", [])
        returns = final_returns.get("gap_resolution", [])
        # Pair captures with their returns by position so the test can
        # restrict its attention to calls whose argument matched gap_id.
        matching_returns: list[Any] = []
        for (args, kwargs), result in zip(captured, returns):
            arg_ids = [
                v for v in tuple(args) + tuple(kwargs.values())
                if isinstance(v, int) and not isinstance(v, bool)
            ]
            if gap_id in arg_ids:
                matching_returns.append(result)

        assert matching_returns, (
            f"`_final_state` must call Engine.gap_resolution(gap_id="
            f"{gap_id}); observed final-phase captured args: "
            f"{captured}"
        )
        assert evidence_id in matching_returns, (
            f"Engine.gap_resolution(gap_id={gap_id}) must return the "
            f"Lane C evidence_id ({evidence_id}) inside `_final_state`; "
            f"observed final-phase returns for that gap_id: "
            f"{matching_returns!r}"
        )
        final = report.get("final_state", {})
        fs_gr = final.get("gap_resolution")
        assert fs_gr in matching_returns, (
            f"final_state['gap_resolution'] ({fs_gr!r}) must equal a "
            f"value actually returned by Engine.gap_resolution(gap_id="
            f"{gap_id}) during `_final_state`; observed returns: "
            f"{matching_returns!r}"
        )
        assert fs_gr == evidence_id, (
            f"the read value must equal the Lane C evidence_id "
            f"({evidence_id}); got {fs_gr!r}"
        )

    # --- 271-corr2 F-READ-BINDING (entity/claim/gap/evidence) ---

    # (final_state field, Engine read method, lane key, produced-id key)
    _READ_BINDINGS = (
        ("entity", "get_entity", "external_ingress", "entity_id"),
        ("claim", "get_claim", "external_ingress", "claim_id"),
        ("gap", "get_gap", "external_ingress", "gap_id"),
        ("evidence", "get_evidence", "downstream_reentry", "evidence_id"),
    )

    @pytest.mark.parametrize(
        "field,method,lane_key,id_key",
        _READ_BINDINGS,
        ids=[b[0] for b in _READ_BINDINGS],
    )
    def test_final_field_bound_to_phase_isolated_read_return(
        self, field, method, lane_key, id_key,
    ):
        """final_state[field] must equal a value actually returned by
        the matching public Engine read, called FROM WITHIN
        `_final_state` with the actual Lane A / Lane C produced ID.
        This rules out `engine.get_entity(entity_id)` being called and
        its result discarded while final_state[field] holds a hardcoded
        summary, and rules out an incidental Lane B read substituting
        for the final-phase read."""
        _skip_if_no_example()
        _, report, _, final_captured, final_returns = (
            _run_with_final_phase_spies((method,))
        )
        if isinstance(report, dict) and "__exception__" in report:
            pytest.fail(f"raised: {report['__exception__']}")
        lane = report.get("lanes", {}).get(lane_key, {})
        expected_id = lane.get("produced_ids", {}).get(id_key)
        assert isinstance(expected_id, int), (
            f"Lane {lane_key!r} must publish an int {id_key!r}; got: "
            f"{expected_id!r}"
        )
        matching = _matching_returns_for_expected_id(
            final_captured.get(method, []),
            final_returns.get(method, []),
            expected_id,
        )
        assert matching, (
            f"`_final_state` must call Engine.{method}({id_key}="
            f"{expected_id}); observed final-phase captured args: "
            f"{final_captured.get(method)}"
        )
        final = report.get("final_state", {})
        fs_value = final.get(field)
        assert fs_value is not None and not isinstance(fs_value, bool), (
            f"final_state[{field!r}] must hold the read return value, "
            f"not a bool/None flag; got: {fs_value!r}"
        )
        assert any(fs_value == m for m in matching), (
            f"final_state[{field!r}] ({fs_value!r}) must be value-equal "
            f"to a value actually returned by Engine.{method}({id_key}="
            f"{expected_id}) inside `_final_state`; observed matching "
            f"returns: {matching!r}"
        )


# ===========================================================================
# AF. Final block must be backed by source-level evidence of real reads
# ===========================================================================


class TestFinalNoHardcodedSummary:
    """AST scan limited to the `_final_state` FunctionDef body. The
    first 271차 cut scanned the whole example source, which would let
    a dead `def unused(): engine.get_entity(...)` or a Lane B call
    satisfy the lock while `_final_state` itself stayed a hardcoded
    boolean dict. The corrected design parses the example with
    `ast.parse`, locates the `_final_state` FunctionDef, and asserts
    each required Engine read appears as `<...>.<name>(...)` somewhere
    inside that function's body."""

    @pytest.mark.parametrize(
        "method_name",
        [
            "get_entity",
            "get_claim",
            "get_gap",
            "get_evidence",
            "gap_resolution",
        ],
    )
    def test_final_state_body_calls_engine_read(self, method_name):
        _skip_if_no_example()
        node = _final_state_function_node()
        assert node is not None, (
            "example source must contain a top-level `_final_state` "
            "FunctionDef so the AST scan can verify in-scope reads"
        )
        calls = _attribute_method_names_called_in(node)
        assert method_name in calls, (
            f"`_final_state` body must contain a `.{method_name}(...)` "
            "call site so the final block cannot be implemented as a "
            "pure constant dictionary; reads in Lane B / dead helpers "
            "outside `_final_state` do NOT satisfy this lock. "
            f"Observed attribute calls inside `_final_state`: {calls}"
        )

    def test_final_state_body_calls_a_public_read_not_only_state_identity(
        self,
    ):
        """Companion lock: `_final_state` must invoke at least one
        public Engine read API beyond `state_identity()`."""
        _skip_if_no_example()
        node = _final_state_function_node()
        assert node is not None, (
            "example source must contain a top-level `_final_state` "
            "FunctionDef so the AST scan can verify in-scope reads"
        )
        calls = _attribute_method_names_called_in(node)
        required_any = {
            "get_entity", "get_claim", "get_gap",
            "get_evidence", "gap_resolution",
        }
        assert calls & required_any, (
            "`_final_state` body must invoke at least one of "
            f"{sorted(required_any)} (state_identity() alone is not "
            f"sufficient); observed attribute calls: {calls}"
        )

# ===========================================================================
# AG. Final packet classification must match Lane B (UNBOUND + UNKNOWN)
# ===========================================================================


class TestFinalPacketClassification:
    """The final verification block must record the same packet
    classification as Lane B: UNBOUND + UNKNOWN. M03 §10 forbids
    re-classifying the PR51 packet as CAPTURE_BOUND, CURRENTLY_MATCHED
    or STALE — those terms describe a binding the M08 example does
    not introduce."""

    def test_final_packet_binding_status_unbound(self):
        _skip_if_no_example()
        report = _get_report()
        final = report.get("final_state", {})
        assert final.get("packet_binding_status") == "UNBOUND", (
            "final_state['packet_binding_status'] must equal 'UNBOUND' "
            "(matching Lane B); the example must not re-bind the packet"
        )

    def test_final_packet_comparison_status_unknown(self):
        _skip_if_no_example()
        report = _get_report()
        final = report.get("final_state", {})
        assert final.get("packet_comparison_status") == "UNKNOWN", (
            "final_state['packet_comparison_status'] must equal "
            "'UNKNOWN' (matching Lane B); the example must not "
            "re-classify the packet"
        )

    def test_final_packet_classification_matches_lane_b(self):
        _skip_if_no_example()
        report = _get_report()
        final = report.get("final_state", {})
        lane_b = report.get("lanes", {}).get("engine_read_and_proposal", {})
        assert final.get("packet_binding_status") == lane_b.get(
            "packet_binding_status",
        ), (
            "final_state['packet_binding_status'] must equal "
            "Lane B's packet_binding_status"
        )
        assert final.get("packet_comparison_status") == lane_b.get(
            "packet_comparison_status",
        ), (
            "final_state['packet_comparison_status'] must equal "
            "Lane B's packet_comparison_status"
        )

    def test_final_packet_status_not_capture_bound_or_stale(self):
        _skip_if_no_example()
        report = _get_report()
        final = report.get("final_state", {})
        forbidden_values = {"CAPTURE_BOUND", "CURRENTLY_MATCHED", "STALE"}
        for key in ("packet_binding_status", "packet_comparison_status"):
            val = final.get(key)
            assert val not in forbidden_values, (
                f"final_state[{key!r}] must not re-classify the packet "
                f"as {val!r}; M03 §10 forbids "
                "CAPTURE_BOUND/CURRENTLY_MATCHED/STALE on a still-"
                "UNBOUND packet"
            )


# ===========================================================================
# AH. Positive status vocabulary must appear at documented positions
# ===========================================================================


class TestPositiveStatusVocabulary:
    """The contract §5.4 / §9 / §10 / §13 status vocabulary must
    appear at the documented positions in the report. record_kind,
    disposition, and verdict are separate fields and cannot substitute
    for the positive status label."""

    def test_lane_a_bridge_decision_status_consumer_decision(self):
        _skip_if_no_example()
        report = _get_report()
        lane_a = report.get("lanes", {}).get("external_ingress", {})
        bridge = lane_a.get("bridge_decision", {})
        assert isinstance(bridge, dict)
        assert bridge.get("status") == "CONSUMER_DECISION", (
            "Lane A bridge_decision must carry status == "
            f"'CONSUMER_DECISION'; got: {bridge.get('status')!r}"
        )

    def test_every_operator_decision_record_status_operator_review(self):
        _skip_if_no_example()
        report = _get_report()
        invocations = _collect_invocation_records(report)
        assert invocations, (
            "report must contain at least one invocation record for "
            "the happy path"
        )
        for inv in invocations:
            odr = inv.get("operator_decision_record")
            assert isinstance(odr, dict), (
                "every invocation record must include an "
                "operator_decision_record dict"
            )
            assert odr.get("status") == "OPERATOR_REVIEW", (
                "every OperatorDecisionRecord must carry status == "
                f"'OPERATOR_REVIEW'; got: {odr.get('status')!r} in "
                f"cycle {inv.get('target_method')!r}"
            )

    def test_every_revalidation_record_status_state_revalidated(self):
        _skip_if_no_example()
        report = _get_report()
        invocations = _collect_invocation_records(report)
        revs_seen = 0
        for inv in invocations:
            revs = inv.get("revalidations", {})
            assert isinstance(revs, dict)
            for moment, rev in revs.items():
                if not isinstance(rev, dict):
                    continue
                revs_seen += 1
                assert rev.get("status") == "STATE_REVALIDATED", (
                    "every revalidation record must carry status == "
                    f"'STATE_REVALIDATED'; got: {rev.get('status')!r} "
                    f"in cycle {inv.get('target_method')!r} moment "
                    f"{moment!r}"
                )
        assert revs_seen >= 12, (
            "happy path must record at least 12 revalidations "
            "(6 cycles × Stage 5.5 + Stage 6); "
            f"observed: {revs_seen}"
        )

    def test_every_invocation_record_status_explicit_invocation(self):
        _skip_if_no_example()
        report = _get_report()
        invocations = _collect_invocation_records(report)
        for inv in invocations:
            assert inv.get("status") == "EXPLICIT_INVOCATION", (
                "every invocation record must carry status == "
                f"'EXPLICIT_INVOCATION'; got: {inv.get('status')!r} "
                f"in cycle {inv.get('target_method')!r}"
            )

    def test_lane_stage_status_in_positive_vocabulary(self):
        _skip_if_no_example()
        report = _get_report()
        allowed = {"CONNECTED", "COMPLETED"}
        for lane_key in (
            "external_ingress",
            "engine_read_and_proposal",
            "downstream_reentry",
        ):
            lane = report.get("lanes", {}).get(lane_key, {})
            assert isinstance(lane, dict)
            status = lane.get("stage_status")
            assert status in allowed, (
                f"lane {lane_key!r} stage_status must be in {allowed}; "
                f"got: {status!r}"
            )

    def test_final_block_status_boundary_preserved(self):
        _skip_if_no_example()
        report = _get_report()
        final = report.get("final_state", {})
        assert final.get("status") == "BOUNDARY_PRESERVED", (
            "final_state must carry status == 'BOUNDARY_PRESERVED'; "
            f"got: {final.get('status')!r}"
        )
