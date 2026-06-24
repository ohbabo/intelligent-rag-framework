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
        assert "not eligible for decision reuse under M05" in serialized.lower()


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
