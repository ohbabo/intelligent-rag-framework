"""Tests for PR70-M01 — Minimal Operational Scaffold.

These tests lock the scaffold boundaries from §17 of the PR70-M01
directive. They are organized by invariant category (A-K):

  A. Baseline shape
  B. Existing component reuse
  C. Adapter->RoleAssignment discontinuity
  D. Role assignment boundary
  E. Engine fixture separation
  F. Read packet
  G. Packet/proposal validator boundaries
  H. No automatic mutation
  I. No invented official types
  J. Domain neutrality
  K. Input immutability

The scaffold module is loaded via importlib.util so that no
package promotion or sys.path mutation occurs (mirrors the
existing pattern in tests/test_role_assignment_validator.py).
"""

from __future__ import annotations

import ast
import importlib.util
from copy import deepcopy
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCAFFOLD_PATH = (
    _REPO_ROOT / "examples" / "operation" / "minimal_operational_scaffold.py"
)
_ADAPTER_PATH = (
    _REPO_ROOT / "examples" / "adapter" / "minimal_external_adapter_example.py"
)
_ROLE_EXAMPLE_PATH = (
    _REPO_ROOT / "examples" / "role_assignment"
    / "minimal_consumer_example.py"
)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_scaffold = _load("pr70_scaffold", _SCAFFOLD_PATH)
_adapter = _load("pr64_adapter_trace_for_tests", _ADAPTER_PATH)
_role = _load("pr61_role_example_for_tests", _ROLE_EXAMPLE_PATH)

build = _scaffold.build_minimal_operational_scaffold


def _all_stages(report):
    out = []
    for lane in ("external_ingress", "engine_read_and_proposal",
                 "downstream_reentry"):
        out.extend(report["lanes"][lane])
    return out


# ===========================================================================
# A. Baseline shape
# ===========================================================================


class TestBaselineShape:

    def test_returns_plain_dict(self):
        report = build()
        assert type(report) is dict

    def test_overall_status_is_incomplete(self):
        assert build()["overall_status"] == "INCOMPLETE"

    def test_three_lanes_exist(self):
        report = build()
        assert set(report["lanes"].keys()) == {
            "external_ingress",
            "engine_read_and_proposal",
            "downstream_reentry",
        }

    def test_stage_order_is_deterministic(self):
        first = [s["stage_id"] for s in _all_stages(build())]
        second = [s["stage_id"] for s in _all_stages(build())]
        assert first == second

    def test_top_level_keys_are_deterministic(self):
        assert sorted(build().keys()) == sorted(build().keys())

    def test_required_future_contracts_deterministic(self):
        a = [c["id"] for c in build()["required_future_contracts"]]
        b = [c["id"] for c in build()["required_future_contracts"]]
        assert a == b

    def test_blocked_handoffs_sorted(self):
        report = build()
        assert report["blocked_handoffs"] == sorted(report["blocked_handoffs"])

    def test_required_future_contracts_cover_seven_oc_ids(self):
        ids = {c["id"] for c in build()["required_future_contracts"]}
        assert ids == {"OC-A", "OC-B", "OC-C", "OC-D", "OC-E", "OC-F", "OC-G"}


# ===========================================================================
# B. Existing component reuse
# ===========================================================================


class TestExistingComponentReuse:
    """The scaffold must actually invoke each existing entry point;
    it must not embed local copies of any validator logic."""

    def test_loads_pr64_adapter_resolved_trace(self):
        # If the module loads successfully, the scaffold has access
        # to the PR64 trace at scaffold import time.
        assert hasattr(_adapter, "RESOLVED_TRANSLATION_TRACE")

    def test_loads_pr64_adapter_unresolved_trace(self):
        assert hasattr(_adapter, "UNRESOLVED_TRANSLATION_TRACE")

    def test_loads_pr61_role_examples(self):
        assert hasattr(_role, "RESOLVED_EXAMPLE")
        assert hasattr(_role, "UNRESOLVED_EXAMPLE")

    def test_a3_invokes_pr62_validator_and_records_result(self):
        report = build()
        a3 = report["lanes"]["external_ingress"][2]
        assert a3["stage_id"] == "A3"
        assert a3["status"] == "CONNECTED"
        assert a3["result"] == []

    def test_b2_invokes_pr51_inspector_and_records_packet_keys(self):
        report = build()
        b2 = report["lanes"]["engine_read_and_proposal"][1]
        assert b2["stage_id"] == "B2"
        assert b2["status"] == "CONNECTED"
        assert b2["packet_keys"] == [
            "active_contradictions",
            "claim",
            "contradictions",
            "effective_confidence",
            "lifecycle_history",
            "supporting_evidence",
            "unresolved_gaps",
        ]

    def test_b4_invokes_pr53_packet_validator(self):
        report = build()
        b4 = report["lanes"]["engine_read_and_proposal"][3]
        assert b4["stage_id"] == "B4"
        assert b4["status"] == "CONNECTED"
        assert b4["result"] == []

    def test_b6_invokes_pr55_pr56_validators(self):
        report = build()
        b6 = report["lanes"]["engine_read_and_proposal"][5]
        assert b6["stage_id"] == "B6"
        assert b6["status"] == "CONNECTED"
        assert b6["shape_result"] == []
        assert b6["safety_result"] == []

    def test_scaffold_does_not_define_its_own_validator(self):
        src = _SCAFFOLD_PATH.read_text()
        tree = ast.parse(src)
        # Allowed function names are the scaffold's own helpers and
        # the single public entry point. None of them re-implement
        # the existing validators.
        forbidden = {
            "validate_role_assignment_boundaries",
            "validate_consumer_packet_interpretation",
            "validate_llm_proposal_shape",
            "validate_proposal_safety",
            "build_engine_context_packet",
        }
        defined = {
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        assert forbidden.isdisjoint(defined), (
            "scaffold must reuse existing validators, not redefine them"
        )


# ===========================================================================
# C. Adapter -> RoleAssignment discontinuity
# ===========================================================================


class TestAdapterRoleDiscontinuity:

    def test_a2_status_is_undefined(self):
        report = build()
        a2 = report["lanes"]["external_ingress"][1]
        assert a2["stage_id"] == "A2"
        assert a2["status"] == "UNDEFINED"

    def test_a2_records_missing_contract(self):
        a2 = build()["lanes"]["external_ingress"][1]
        assert "missing_contract" in a2

    def test_adapter_input_not_mutated_by_build(self):
        before = deepcopy(_adapter.RESOLVED_TRANSLATION_TRACE)
        build()
        assert _adapter.RESOLVED_TRANSLATION_TRACE == before

    def test_role_example_not_mutated_by_build(self):
        before = deepcopy(_role.RESOLVED_EXAMPLE)
        build()
        assert _role.RESOLVED_EXAMPLE == before


# ===========================================================================
# D. Role assignment boundary
# ===========================================================================


class TestRoleAssignmentBoundary:

    def test_a3_resolved_validation_result_is_empty(self):
        a3 = build()["lanes"]["external_ingress"][2]
        assert a3["result"] == []

    def test_a3_result_meaning_does_not_promote_to_authority(self):
        a3 = build()["lanes"]["external_ingress"][2]
        meaning = a3["result_meaning"]
        for forbidden in (
            "correct semantic role",
            "operator accepted",
            "Engine accepted",
            "mutation authorized",
        ):
            assert forbidden in meaning, (
                f"expected anti-claim '{forbidden}' in A3 meaning"
            )

    def test_a4_unresolved_does_not_advance(self):
        a4 = build()["lanes"]["external_ingress"][3]
        assert a4["stage_id"] == "A4"
        assert a4["status"] == "BLOCKED"

    def test_a3_does_not_carry_acceptance_field(self):
        a3 = build()["lanes"]["external_ingress"][2]
        for key in ("accepted", "operator_accepted", "review_accepted"):
            assert key not in a3


# ===========================================================================
# E. Engine fixture separation
# ===========================================================================


class TestEngineFixtureSeparation:

    def test_b1_fixture_origin_label(self):
        b1 = build()["lanes"]["engine_read_and_proposal"][0]
        assert b1["status"] == "MANUAL_FIXTURE"
        assert b1["fixture_origin"] == "PRESEEDED_FOR_READ_LANE_ONLY"

    def test_report_records_top_level_fixture_origin(self):
        assert (
            build()["fixture_origin_for_engine"]
            == "PRESEEDED_FOR_READ_LANE_ONLY"
        )

    def test_no_lane_a_stage_claims_to_have_produced_the_engine(self):
        for stage in build()["lanes"]["external_ingress"]:
            for k in ("produced_engine", "seeded_engine", "engine_built"):
                assert k not in stage

    def test_scaffold_does_not_access_private_engine_attributes(self):
        src = _SCAFFOLD_PATH.read_text()
        # The scaffold does not access Engine private state via the
        # canonical ``engine._<name>`` attribute pattern.
        for forbidden in (
            "engine._claims",
            "engine._evidences",
            "engine._gaps",
            "engine._next_id",
            "engine._rule_stats",
            "engine._contradictions",
            "engine._claim_gap_refs",
        ):
            assert forbidden not in src

    def test_scaffold_uses_only_public_engine_api_for_seeding(self):
        src = _SCAFFOLD_PATH.read_text()
        # Only public add_entity / add_claim are used during seeding.
        # Other Engine.add_* calls (add_evidence, add_gap, etc.) are
        # not required for M01 and must not appear.
        assert "engine.add_entity(" in src
        assert "engine.add_claim(" in src


# ===========================================================================
# F. Read packet
# ===========================================================================


class TestReadPacket:

    def test_b2_packet_keys_unchanged_from_pr51(self):
        b2 = build()["lanes"]["engine_read_and_proposal"][1]
        assert len(b2["packet_keys"]) == 7

    def test_b3_state_binding_undefined(self):
        b3 = build()["lanes"]["engine_read_and_proposal"][2]
        assert b3["status"] == "UNDEFINED"

    def test_b3_does_not_fabricate_packet_revision(self):
        b3 = build()["lanes"]["engine_read_and_proposal"][2]
        for fabricated in (
            "packet_revision",
            "state_revision",
            "engine_revision",
            "snapshot_digest",
            "capture_token",
        ):
            assert fabricated not in b3, (
                f"scaffold must not fabricate {fabricated} on B3"
            )


# ===========================================================================
# G. Packet/proposal validator boundaries
# ===========================================================================


class TestValidatorBoundaries:

    def test_safe_consumer_output_packet_validator_empty(self):
        b4 = build()["lanes"]["engine_read_and_proposal"][3]
        assert b4["result"] == []

    def test_safe_proposal_shape_validator_empty(self):
        b6 = build()["lanes"]["engine_read_and_proposal"][5]
        assert b6["shape_result"] == []

    def test_safe_proposal_safety_validator_empty(self):
        b6 = build()["lanes"]["engine_read_and_proposal"][5]
        assert b6["safety_result"] == []

    def test_validator_pass_does_not_advance_operator_acceptance(self):
        b7 = build()["lanes"]["engine_read_and_proposal"][6]
        assert b7["stage_id"] == "B7"
        assert b7["status"] == "BLOCKED"


# ===========================================================================
# H. No automatic mutation
# ===========================================================================


class TestNoAutomaticMutation:

    def test_scaffold_does_not_use_eval_or_exec(self):
        src = _SCAFFOLD_PATH.read_text()
        tree = ast.parse(src)
        # Direct lexical scan
        assert "eval(" not in src
        assert "exec(" not in src
        # AST scan covering both Name and Attribute access patterns
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    assert func.id not in {"eval", "exec"}
                if isinstance(func, ast.Attribute):
                    assert func.attr not in {"eval", "exec"}

    def test_scaffold_does_not_use_getattr_on_engine(self):
        src = _SCAFFOLD_PATH.read_text()
        # Method-name-string dispatch is explicitly forbidden.
        assert "getattr(engine" not in src
        assert "getattr(_engine" not in src

    def test_scaffold_does_not_import_inspect_or_operator_dispatch(self):
        src = _SCAFFOLD_PATH.read_text()
        # These imports would suggest dynamic dispatch infrastructure.
        for forbidden in ("import inspect", "from operator import "):
            assert forbidden not in src

    def test_scaffold_does_not_call_add_evidence_or_lifecycle_apis(self):
        src = _SCAFFOLD_PATH.read_text()
        # Lane A is BLOCKED at A7; Lane C is BLOCKED at C7. The
        # scaffold must NOT call mutation APIs beyond the documented
        # fixture seeding (add_entity / add_claim).
        for forbidden in (
            "engine.add_evidence(",
            "engine.add_gap(",
            "engine.add_relation(",
            "engine.add_observation(",
            "engine.register_rule(",
            "engine.confirm_claim_if_ready(",
            "engine.refute_claim_if_ready(",
            "engine.dispute_claim_if_ready(",
            "engine.register_contradiction(",
            "engine.update_rule_stats(",
        ):
            assert forbidden not in src

    def test_a7_status_blocked(self):
        a7 = build()["lanes"]["external_ingress"][6]
        assert a7["stage_id"] == "A7"
        assert a7["status"] == "BLOCKED"

    def test_c7_status_blocked(self):
        c7 = build()["lanes"]["downstream_reentry"][6]
        assert c7["stage_id"] == "C7"
        assert c7["status"] == "BLOCKED"


# ===========================================================================
# I. No invented official types
# ===========================================================================


class TestNoInventedOfficialTypes:

    def test_scaffold_does_not_define_engine_input_candidate_class(self):
        src = _SCAFFOLD_PATH.read_text()
        tree = ast.parse(src)
        forbidden = {
            "EngineInputCandidate",
            "ReviewedMutationRequest",
            "OperatorDecisionRecord",
            "PacketRevision",
            "StateRevision",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in forbidden, (
                    f"scaffold must not materialize {node.name} as a class"
                )

    def test_scaffold_does_not_use_dataclass_or_namedtuple(self):
        """The scaffold must NOT use dataclass / NamedTuple / TypedDict
        as actual code constructs. The strings may legally appear inside
        string literals (e.g. inside an explicit disclaimer noting that
        these are NOT used)."""
        src = _SCAFFOLD_PATH.read_text()
        tree = ast.parse(src)

        # No @dataclass decorator on any class.
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for dec in node.decorator_list:
                    name = (
                        dec.id if isinstance(dec, ast.Name)
                        else getattr(dec, "attr", "")
                    )
                    assert name != "dataclass"

        # No `from dataclasses import ...`, no `from typing import
        # NamedTuple / TypedDict`, no `import dataclasses`.
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "dataclasses":
                    raise AssertionError("scaffold must not import dataclasses")
                if node.module == "typing":
                    for alias in node.names:
                        assert alias.name not in {"NamedTuple", "TypedDict"}
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "dataclasses"

        # No class inherits from NamedTuple / TypedDict.
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = (
                        base.id if isinstance(base, ast.Name)
                        else getattr(base, "attr", "")
                    )
                    assert base_name not in {"NamedTuple", "TypedDict"}

    def test_missing_contract_names_appear_only_as_strings(self):
        # Stage A5/A6 reference EngineInputCandidate and
        # ReviewedMutationRequest as identifier strings. The strings
        # exist inside dict values (missing_contract); the AST should
        # show them only as Constant string literals or string usages.
        report = build()
        a5 = report["lanes"]["external_ingress"][4]
        a6 = report["lanes"]["external_ingress"][5]
        assert "EngineInputCandidate" in a5["missing_contract"]
        assert "ReviewedMutationRequest" in a6["missing_contract"]


# ===========================================================================
# J. Domain neutrality
# ===========================================================================


class TestDomainNeutrality:
    """The scaffold body and report must NOT contain
    security-domain coupling. (The existing validators may reference
    domain words inside their own files; that is their concern.)"""

    _FORBIDDEN_DOMAIN_WORDS = (
        "cerberus",
        "vulnerability",
        "exploit",
        "scanner",
        "host",
        "port",
        "service",
        "security verdict",
    )

    def test_scaffold_source_has_no_domain_vocabulary(self):
        """Word-boundary scan to avoid false positives from substring
        overlap (e.g. 'port' inside 'import')."""
        import re
        src = _SCAFFOLD_PATH.read_text().lower()
        for word in self._FORBIDDEN_DOMAIN_WORDS:
            pattern = r"\b" + re.escape(word) + r"\b"
            assert re.search(pattern, src) is None, (
                f"scaffold source must not contain word-boundary '{word}'"
            )

    def test_report_serialized_has_no_domain_vocabulary(self):
        """Walk the report and apply word-boundary matching, same
        rationale as the source scan."""
        import re

        def walk(obj):
            if isinstance(obj, dict):
                for v in obj.values():
                    yield from walk(v)
                for k in obj.keys():
                    yield str(k)
            elif isinstance(obj, (list, tuple)):
                for v in obj:
                    yield from walk(v)
            else:
                yield str(obj)

        joined = " ".join(walk(build())).lower()
        for word in self._FORBIDDEN_DOMAIN_WORDS:
            pattern = r"\b" + re.escape(word) + r"\b"
            assert re.search(pattern, joined) is None, (
                f"report must not contain word-boundary '{word}'"
            )

    def test_report_mentions_cve_only_if_zero(self):
        # CVE is a particularly load-bearing security identifier;
        # ensure it does not appear at all.
        joined = repr(build()).lower()
        assert "cve" not in joined


# ===========================================================================
# K. Input immutability
# ===========================================================================


class TestInputImmutability:

    def test_adapter_resolved_unchanged(self):
        before = deepcopy(_adapter.RESOLVED_TRANSLATION_TRACE)
        build()
        assert _adapter.RESOLVED_TRANSLATION_TRACE == before

    def test_adapter_unresolved_unchanged(self):
        before = deepcopy(_adapter.UNRESOLVED_TRANSLATION_TRACE)
        build()
        assert _adapter.UNRESOLVED_TRANSLATION_TRACE == before

    def test_role_resolved_unchanged(self):
        before = deepcopy(_role.RESOLVED_EXAMPLE)
        build()
        assert _role.RESOLVED_EXAMPLE == before

    def test_role_unresolved_unchanged(self):
        before = deepcopy(_role.UNRESOLVED_EXAMPLE)
        build()
        assert _role.UNRESOLVED_EXAMPLE == before

    def test_repeated_build_returns_equivalent_reports(self):
        first = build()
        second = build()
        assert first == second


# ===========================================================================
# Cross-cutting: non-authority locks and required future contracts
# ===========================================================================


class TestNonAuthorityLocks:

    def test_locks_list_present(self):
        locks = build()["non_authority_locks"]
        assert isinstance(locks, list)
        assert len(locks) >= 11

    def test_specific_lock_strings_present(self):
        locks = build()["non_authority_locks"]
        for expected in (
            "Adapter output != RoleAssignment",
            "Operator acceptance != Engine truth",
            "effective_confidence != probability",
            "External result != ragcore.Evidence",
            "Evidence registration != automatic lifecycle transition",
        ):
            assert expected in locks


class TestEffectiveConfidenceTraceDiagnosis:

    def test_diagnosis_present(self):
        diag = build()["effective_confidence_trace_diagnosis"]
        assert diag["future_contract"] == "OC-D"

    def test_diagnosis_does_not_substitute_schema_version(self):
        diag = build()["effective_confidence_trace_diagnosis"]
        joined = " ".join(diag["forbidden_substitutions"])
        assert "schema_version" in joined


class TestRuleStatsProvenanceDiagnosis:

    def test_diagnosis_present(self):
        diag = build()["rule_stats_provenance_diagnosis"]
        assert diag["future_contract"] == "OC-G"

    def test_diagnosis_does_not_promote_to_engine_field(self):
        diag = build()["rule_stats_provenance_diagnosis"]
        # Every recorded answer is the string "no" — the scaffold
        # does not pretend that any provenance field exists today.
        for k in (
            "caller_identity_recorded",
            "update_reason_recorded",
            "source_observation_reference_recorded",
            "delta_provenance_recorded",
            "precision_input_basis_recorded",
            "policy_reference_recorded",
        ):
            assert diag[k] == "no"


# ===========================================================================
# Post-audit: historical-snapshot temporality + M07/M09 supersession
# (G-M01-04 / G-M01-14 / G-M01-16)
# ===========================================================================


_HISTORICAL_OC_ORDER = ["OC-A", "OC-C", "OC-B", "OC-E", "OC-D", "OC-F", "OC-G"]


class TestHistoricalSnapshotSupersession:
    """The scaffold report is an explicit PR70-M01 historical snapshot.
    Later M-series supersession (M07 trace, M09 consumer-owned provenance)
    is recorded as metadata WITHOUT rewriting the historical stage statuses."""

    def test_t1_explicit_historical_mode(self):
        report = build()
        assert report["report_temporality"]["mode"] == "HISTORICAL_SNAPSHOT"

    def test_t2_exact_m01_identity(self):
        t = build()["report_temporality"]
        assert t["internal_track"] == "PR70-M01"
        assert t["base_commit"] == "9874b44127c765176cb4ec6bb7158e5f7a8b7316"
        assert t["merge_commit"] == "896e01ea3142e17a591a3054963d498744709e2e"

    def test_t3_stage_status_temporal_boundary(self):
        t = build()["report_temporality"]
        assert t["stage_statuses_as_of"] == "PR70-M01"
        assert t["current_capability_inventory"] is False

    def test_t4_historical_future_contract_scope(self):
        report = build()
        assert (
            report["required_future_contracts_scope"]
            == "HISTORICAL_OPEN_ITEMS_AT_PR70_M01"
        )
        ocs = [c["id"] for c in report["required_future_contracts"]]
        assert ocs == _HISTORICAL_OC_ORDER

    def test_t5_stale_present_tense_confidence_keys_removed(self):
        diag = build()["effective_confidence_trace_diagnosis"]
        for stale in (
            "modifier_breakdown_available_today",
            "calculation_policy_identity_available",
            "source_state_reference_available",
            "future_contract",
        ):
            assert stale not in diag

    def test_t6_m01_historical_confidence_answers_retained(self):
        diag = build()["effective_confidence_trace_diagnosis"]
        for k in (
            "modifier_breakdown_available_at_m01",
            "calculation_policy_identity_available_at_m01",
            "source_state_reference_available_at_m01",
        ):
            assert k in diag
            assert str(diag[k]).lower().startswith("no")

    def test_t7_oc_d_supersession(self):
        diag = build()["effective_confidence_trace_diagnosis"]
        assert diag["historical_future_contract"] == "OC-D"
        assert diag["supersession"]["status"] == "CLOSED_BY_PR76_M07"

    def test_t8_exact_m07_public_surfaces(self):
        sup = build()["effective_confidence_trace_diagnosis"]["supersession"]
        assert sup["public_type"] == "EffectiveConfidenceTrace"
        assert (
            sup["public_method"]
            == "Engine.compute_effective_confidence_with_trace"
        )
        import ragcore
        from ragcore import Engine
        assert "EffectiveConfidenceTrace" in ragcore.__all__
        assert hasattr(Engine, "compute_effective_confidence_with_trace")

    def test_t9_exact_m07_capability_list(self):
        sup = build()["effective_confidence_trace_diagnosis"]["supersession"]
        assert sup["trace_capabilities"] == [
            "status_modifier",
            "freshness_modifier",
            "gap_modifier",
            "count_modifier",
            "rule_stats_modifier",
            "evidence_type_modifier",
            "calculation_policy_id",
            "source_state_identity",
        ]

    def test_t10_b3_and_pr51_packet_boundary_preserved(self):
        report = build()
        stages = {s["stage_id"]: s for s in _all_stages(report)}
        assert stages["B3"]["status"] == "UNDEFINED"
        assert len(stages["B2"]["packet_keys"]) == 7
        sup = report["effective_confidence_trace_diagnosis"]["supersession"]
        assert sup["pr51_packet_shape_changed"] is False
        assert sup["b3_packet_binding_retroactively_connected"] is False

    def test_t11_rule_stats_diagnosis_m09_distinction(self):
        diag = build()["rule_stats_provenance_diagnosis"]
        for k in (
            "caller_identity_recorded",
            "update_reason_recorded",
            "source_observation_reference_recorded",
            "delta_provenance_recorded",
            "precision_input_basis_recorded",
            "policy_reference_recorded",
        ):
            assert diag[k] == "no"
        assert "future_contract" not in diag
        assert diag["historical_future_contract"] == "OC-G"
        sup = diag["supersession"]
        assert sup["status"] == "CLOSED_BY_PR78_M09_CONSUMER_OWNED_LAYER"
        assert sup["engine_internal_fields_added"] is False
        assert sup["scope"] == "CONSUMER_OWNED_EXAMPLE_LOCAL"

    def test_t12_preservation(self):
        import json
        from copy import deepcopy
        report = build()
        stages = _all_stages(report)
        assert len(stages) == 22
        counts = {}
        for s in stages:
            counts[s["status"]] = counts.get(s["status"], 0) + 1
        assert counts == {
            "CONNECTED": 5,
            "MANUAL_FIXTURE": 2,
            "BLOCKED": 4,
            "UNDEFINED": 8,
            "TODO": 3,
        }
        json.dumps(report)  # JSON serializable
        assert build() == build()  # deterministic
        report1 = build()
        report1["report_temporality"]["mode"] = "MUTATED"
        report1["lanes"]["external_ingress"][0]["status"] = "MUTATED"
        report2 = build()
        assert report2["report_temporality"]["mode"] == "HISTORICAL_SNAPSHOT"
        assert report2["lanes"]["external_ingress"][0]["status"] == "CONNECTED"
