"""Complete Domain-Neutral Reference Operation — PR77-M08.

Domain-neutral executable example that exercises every connected
handoff between PR59 / PR60 / PR61 / PR63 / PR51 / PR53 / PR55 /
PR56 / M02 / M03 / M04 / M05 / M06 / M07 in a single local
happy-path run.

This file is an example. It is not a framework type, not a
dispatcher, not an executor, not a workflow engine, and not a
canonical record schema. The local plain-dict records it produces
(candidate, operator decision, reviewed mutation request, call
receipt) are example-local illustrative records (M08 §4).

See:
  docs/architecture/
    COMPLETE_DOMAIN_NEUTRAL_REFERENCE_OPERATION_CONTRACT.md

Entry point:

    run_complete_domain_neutral_reference_operation()
      -> dict[str, Any]
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any

from ragcore import Engine


# ----------------------------------------------------------------------
# Module-level loading of reusable callables and constants.
#
# Each callable is bound to a module global so a runtime spy may
# replace it via `setattr(this_module, attr, spy)`. Local copies or
# closures that would hide the binding from a spy are forbidden by
# M08 §3.
# ----------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load(rel_path: str, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        module_name, _REPO_ROOT / rel_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ADAPTER_MODULE = _load(
    "examples/adapter/minimal_external_adapter_example.py",
    "_m08_adapter_module",
)
_ROLE_EXAMPLE_MODULE = _load(
    "examples/role_assignment/minimal_consumer_example.py",
    "_m08_role_example_module",
)
_ROLE_VALIDATOR_MODULE = _load(
    "examples/role_assignment/role_assignment_validator.py",
    "_m08_role_validator_module",
)
_INSPECTOR_MODULE = _load(
    "examples/inspector/engine_inspector.py",
    "_m08_inspector_module",
)
_PACKET_VALIDATOR_MODULE = _load(
    "examples/inspector/packet_validator.py",
    "_m08_packet_validator_module",
)
_PROPOSAL_SCHEMA_MODULE = _load(
    "examples/proposal/proposal_schema.py",
    "_m08_proposal_schema_module",
)
_PROPOSAL_VALIDATOR_MODULE = _load(
    "examples/proposal/proposal_validator.py",
    "_m08_proposal_validator_module",
)


# Reusable callables — bound at module level so runtime spies can
# wrap them (M08 §3 / 266차 §R-D).
validate_role_assignment_boundaries = (
    _ROLE_VALIDATOR_MODULE.validate_role_assignment_boundaries
)
build_engine_context_packet = (
    _INSPECTOR_MODULE.build_engine_context_packet
)
validate_consumer_packet_interpretation = (
    _PACKET_VALIDATOR_MODULE.validate_consumer_packet_interpretation
)
validate_llm_proposal_shape = (
    _PROPOSAL_SCHEMA_MODULE.validate_llm_proposal_shape
)
validate_proposal_safety = (
    _PROPOSAL_VALIDATOR_MODULE.validate_proposal_safety
)


# Reusable constants — loaded once at module import and immutably
# referenced from the operation (always deepcopied before any local
# use).
RESOLVED_TRANSLATION_TRACE = _ADAPTER_MODULE.RESOLVED_TRANSLATION_TRACE
RESOLVED_EXAMPLE = _ROLE_EXAMPLE_MODULE.RESOLVED_EXAMPLE


# ----------------------------------------------------------------------
# Local record builders (plain dict only; M08 §4 / §5).
# ----------------------------------------------------------------------


def _next_id_factory():
    """Per-operation id generator. A fresh generator is used per call
    of run_complete_domain_neutral_reference_operation() so no
    module-level state leaks across runs."""
    state = {"n": 0}
    def next_id(prefix: str) -> str:
        state["n"] += 1
        return f"{prefix}-{state['n']}"
    return next_id


def _build_candidate(
    next_id,
    target_method: str,
    arguments: dict,
    source_basis: dict,
    expected_effect: str,
    policy_assumptions: list[str],
    materialized_at_revision: int,
) -> dict:
    return {
        "record_kind": "engine_input_candidate",
        "candidate_id": next_id("cand"),
        "target_method": target_method,
        "arguments": copy.deepcopy(arguments),
        "source_basis": copy.deepcopy(source_basis),
        "expected_effect": expected_effect,
        "policy_assumptions": list(policy_assumptions),
        "materialized_at_revision": materialized_at_revision,
    }


def _build_decision(
    next_id,
    decision_family: str,
    subject_snapshot: dict,
    disposition: str,
    decision_state_identity: dict,
    supersedes: str | None,
    note: str,
) -> dict:
    return {
        "record_kind": "operator_decision_record",
        "decision_record_id": next_id("dec"),
        "decision_family": decision_family,
        "subject_snapshot": copy.deepcopy(subject_snapshot),
        "disposition": disposition,
        "decision_state_identity": copy.deepcopy(decision_state_identity),
        "supersedes": supersedes,
        "note": note,
    }


def _build_request(
    next_id,
    candidate: dict,
    decision_record_id: str,
    decision_state_identity: dict,
) -> dict:
    """The approved_candidate_snapshot is a separate deepcopy of the
    candidate. The request's `arguments` is yet another separate
    deepcopy. This guarantees four distinct dict objects
    (candidate.arguments, snapshot.arguments, request.arguments,
    receipt.reviewed_arguments) per M08 §6 / 266차 §R-U."""
    return {
        "record_kind": "reviewed_mutation_request",
        "request_id": next_id("req"),
        "approved_candidate_snapshot": copy.deepcopy(candidate),
        "approved_decision_record_id": decision_record_id,
        "target_method": candidate["target_method"],
        "arguments": copy.deepcopy(candidate["arguments"]),
        "decision_state_identity": copy.deepcopy(decision_state_identity),
    }


def _build_receipt(
    next_id,
    request: dict,
    identity_before: dict,
    identity_after: dict,
    result: Any,
) -> dict:
    return {
        "record_kind": "call_receipt",
        "receipt_id": next_id("rcpt"),
        "request_id": request["request_id"],
        "target_method": request["target_method"],
        "reviewed_arguments": copy.deepcopy(request["arguments"]),
        "identity_before": copy.deepcopy(identity_before),
        "identity_after": copy.deepcopy(identity_after),
        "result": copy.deepcopy(result) if isinstance(
            result, (dict, list, tuple),
        ) else result,
    }


def _identity_dict(identity) -> dict:
    """Plain-dict projection of EngineStateIdentity (the value type
    is recorded in the example report only as a plain dict)."""
    return {
        "engine_token": identity.engine_token,
        "revision": identity.revision,
    }


def _revalidate(
    decision_identity: dict, current_identity: dict, moment: str,
) -> dict:
    eligible = (
        decision_identity == current_identity
    )
    return {
        "moment": moment,
        "decision_state_identity": copy.deepcopy(decision_identity),
        "current_state_identity": copy.deepcopy(current_identity),
        "verdict": "eligible" if eligible else "not_eligible",
    }


def _explicit_review(approved: bool, note: str) -> str:
    """Returns one of the M02 §9 dispositions. The 267차 example uses
    only the 'approved' branch on the happy path; helper accepts the
    other two for completeness."""
    if approved:
        return "approved"
    return note


# ----------------------------------------------------------------------
# Lane A — explicit external ingress and Engine materialization.
# ----------------------------------------------------------------------


def _lane_a(engine: Engine, next_id) -> dict:
    """Builds a fresh Engine state by sequentially performing
    add_entity -> add_claim -> add_gap. Each call is preceded by the
    full 9-step per-call procedure (M08 §7)."""

    # 7.1 Adapter trace + role example — consumer-owned bridge.
    adapter_trace_local = copy.deepcopy(RESOLVED_TRANSLATION_TRACE)
    role_example_local = copy.deepcopy(RESOLVED_EXAMPLE)
    bridge_decision = {
        "consumer_decision": (
            "consumer chose to combine the adapter trace and the "
            "role example for this run; no automatic bridge"
        ),
        "automatic_adapter_to_role_conversion": False,
    }

    # 7.3 RoleAssignment validation — actual call into PR60.
    role_violations = validate_role_assignment_boundaries(
        role_example_local,
    )

    invocations: list[dict] = []

    # Cycle 1 — add_entity.
    e_args = {"entity_type": 1, "flags": 0}
    e_cand = _build_candidate(
        next_id,
        target_method="add_entity",
        arguments=e_args,
        source_basis={
            "originating_trace": copy.deepcopy(adapter_trace_local),
            "originating_role_example": copy.deepcopy(role_example_local),
            "role_validation_outcome": list(role_violations),
        },
        expected_effect="register a new Entity in this fresh Engine",
        policy_assumptions=[
            "local example policy; consumer-owned",
        ],
        materialized_at_revision=engine.state_identity().revision,
    )
    e_decision_identity = _identity_dict(engine.state_identity())
    e_decision = _build_decision(
        next_id,
        decision_family="mutation_review",
        subject_snapshot=e_cand,
        disposition=_explicit_review(True, ""),
        decision_state_identity=e_decision_identity,
        supersedes=None,
        note="approved on local consumer review",
    )
    reval_5_5 = _revalidate(
        e_decision_identity,
        _identity_dict(engine.state_identity()),
        "stage_5_5_materialization",
    )
    e_request = _build_request(
        next_id, e_cand,
        decision_record_id=e_decision["decision_record_id"],
        decision_state_identity=e_decision_identity,
    )
    reval_6 = _revalidate(
        e_decision_identity,
        _identity_dict(engine.state_identity()),
        "stage_6_invocation",
    )
    id_before = _identity_dict(engine.state_identity())
    entity_id = engine.add_entity(**e_request["arguments"])
    id_after = _identity_dict(engine.state_identity())
    e_receipt = _build_receipt(
        next_id, e_request, id_before, id_after, entity_id,
    )
    invocations.append({
        "target_method": "add_entity",
        "arguments": copy.deepcopy(e_request["arguments"]),
        "candidate": e_cand,
        "operator_decision_record": e_decision,
        "reviewed_mutation_request": e_request,
        "revalidations": {
            "stage_5_5_materialization": reval_5_5,
            "stage_6_invocation": reval_6,
        },
        "call_receipt": e_receipt,
        "returned_id": entity_id,
    })

    # Cycle 2 — add_claim, using the returned entity_id.
    c_args = {
        "subject_id": entity_id,
        "claim_type": 1,
        "rule_id": 0,
        "rule_version": 0,
        "reason_code": 0,
        "base_confidence": 0.8,
    }
    c_cand = _build_candidate(
        next_id, target_method="add_claim", arguments=c_args,
        source_basis={
            "previous_returned_entity_id": entity_id,
            "originating_role_example": copy.deepcopy(role_example_local),
        },
        expected_effect="register a new Claim about the new Entity",
        policy_assumptions=["local example policy"],
        materialized_at_revision=engine.state_identity().revision,
    )
    c_decision_identity = _identity_dict(engine.state_identity())
    c_decision = _build_decision(
        next_id, decision_family="mutation_review",
        subject_snapshot=c_cand,
        disposition=_explicit_review(True, ""),
        decision_state_identity=c_decision_identity,
        supersedes=None, note="approved",
    )
    c_reval_5_5 = _revalidate(
        c_decision_identity, _identity_dict(engine.state_identity()),
        "stage_5_5_materialization",
    )
    c_request = _build_request(
        next_id, c_cand,
        decision_record_id=c_decision["decision_record_id"],
        decision_state_identity=c_decision_identity,
    )
    c_reval_6 = _revalidate(
        c_decision_identity, _identity_dict(engine.state_identity()),
        "stage_6_invocation",
    )
    c_id_before = _identity_dict(engine.state_identity())
    claim_id = engine.add_claim(**c_request["arguments"])
    c_id_after = _identity_dict(engine.state_identity())
    c_receipt = _build_receipt(
        next_id, c_request, c_id_before, c_id_after, claim_id,
    )
    invocations.append({
        "target_method": "add_claim",
        "arguments": copy.deepcopy(c_request["arguments"]),
        "candidate": c_cand,
        "operator_decision_record": c_decision,
        "reviewed_mutation_request": c_request,
        "revalidations": {
            "stage_5_5_materialization": c_reval_5_5,
            "stage_6_invocation": c_reval_6,
        },
        "call_receipt": c_receipt,
        "returned_id": claim_id,
    })

    # Cycle 3 — add_gap, using the returned claim_id.
    gap_required_evidence_type = 7
    g_args = {
        "claim_id": claim_id,
        "gap_type": 1,
        "required_evidence_type": gap_required_evidence_type,
        "severity": 0.5,
        "rule_id": 0,
    }
    g_cand = _build_candidate(
        next_id, target_method="add_gap", arguments=g_args,
        source_basis={
            "previous_returned_claim_id": claim_id,
        },
        expected_effect="register a new Gap referencing the Claim",
        policy_assumptions=["local example policy"],
        materialized_at_revision=engine.state_identity().revision,
    )
    g_decision_identity = _identity_dict(engine.state_identity())
    g_decision = _build_decision(
        next_id, decision_family="mutation_review",
        subject_snapshot=g_cand,
        disposition=_explicit_review(True, ""),
        decision_state_identity=g_decision_identity,
        supersedes=None, note="approved",
    )
    g_reval_5_5 = _revalidate(
        g_decision_identity, _identity_dict(engine.state_identity()),
        "stage_5_5_materialization",
    )
    g_request = _build_request(
        next_id, g_cand,
        decision_record_id=g_decision["decision_record_id"],
        decision_state_identity=g_decision_identity,
    )
    g_reval_6 = _revalidate(
        g_decision_identity, _identity_dict(engine.state_identity()),
        "stage_6_invocation",
    )
    g_id_before = _identity_dict(engine.state_identity())
    gap_id = engine.add_gap(**g_request["arguments"])
    g_id_after = _identity_dict(engine.state_identity())
    g_receipt = _build_receipt(
        next_id, g_request, g_id_before, g_id_after, gap_id,
    )
    invocations.append({
        "target_method": "add_gap",
        "arguments": copy.deepcopy(g_request["arguments"]),
        "candidate": g_cand,
        "operator_decision_record": g_decision,
        "reviewed_mutation_request": g_request,
        "revalidations": {
            "stage_5_5_materialization": g_reval_5_5,
            "stage_6_invocation": g_reval_6,
        },
        "call_receipt": g_receipt,
        "returned_id": gap_id,
    })

    return {
        "fixture_origin_for_engine": "PRODUCED_BY_LANE_A",
        "consumed_adapter_trace": copy.deepcopy(adapter_trace_local),
        "consumed_role_example": copy.deepcopy(role_example_local),
        "bridge_decision": bridge_decision,
        "role_validation_violations": list(role_violations),
        "explicit_invocation_sequence": invocations,
        "produced_ids": {
            "entity_id": entity_id,
            "claim_id": claim_id,
            "gap_id": gap_id,
        },
        "gap_required_evidence_type": gap_required_evidence_type,
        "stage_status": "COMPLETED",
    }


# ----------------------------------------------------------------------
# Lane B — Engine read, confidence trace, proposal review.
# ----------------------------------------------------------------------


def _lane_b(engine: Engine, claim_id: int) -> dict:
    # 10.1 PR51 packet (via the module-level global, so spies catch it).
    packet = build_engine_context_packet(engine, claim_id)

    # 10.2 M07 trace — capture identity before / after the call.
    identity_before_trace = engine.state_identity()
    trace = engine.compute_effective_confidence_with_trace(claim_id)
    identity_after_trace = engine.state_identity()
    legacy_effective = engine.compute_effective_confidence(claim_id)

    trace_block = {
        "effective_confidence": trace.effective_confidence.value,
        "legacy_effective_confidence": legacy_effective.value,
        "calculation_policy_id": trace.calculation_policy_id,
        "source_state_identity": _identity_dict(trace.source_state_identity),
        "identity_before_trace": _identity_dict(identity_before_trace),
        "identity_after_trace": _identity_dict(identity_after_trace),
        "trace_effective_equals_legacy": (
            trace.effective_confidence == legacy_effective
        ),
        "source_identity_equals_engine_state": (
            trace.source_state_identity == identity_before_trace
        ),
        "identity_before_trace_equal_to_source": (
            trace.source_state_identity == identity_before_trace
        ),
        "identity_after_trace_equal_to_source": (
            trace.source_state_identity == identity_after_trace
        ),
        "identity_before_equals_identity_after": (
            identity_before_trace == identity_after_trace
        ),
        "trace_identity_revision": trace.source_state_identity.revision,
    }

    # 10.3 PR53 consumer-output validation — pass the packet through
    # an empty consumer interpretation to keep violations = [].
    consumer_output = {
        "consumer_interpretation_kind": "neutral_summary",
    }
    packet_violations = validate_consumer_packet_interpretation(
        consumer_output, packet,
    )

    # 10.4 Local manual proposal — same exact content into PR55 and
    # PR56 via separate deepcopies (so neither validator can mutate
    # the other's input).
    proposal = {
        "category": "evidence_gap_question",
        "target_claim_id": claim_id,
        "note": (
            "consumer-side observation about the unresolved Gap"
        ),
    }
    pr55_violations = validate_llm_proposal_shape(
        copy.deepcopy(proposal), copy.deepcopy(packet),
    )
    pr56_violations = validate_proposal_safety(
        copy.deepcopy(proposal), copy.deepcopy(packet),
    )

    # 11.3 Operator disposition — schedule-manual-inspection as
    # sibling of the other six M05 §4.1 dispositions.
    proposal_block = {
        "proposal_content_snapshot": copy.deepcopy(proposal),
        "pr55_shape_violations": list(pr55_violations),
        "pr56_safety_violations": list(pr56_violations),
        "network_invocation": False,
        "llm_invocation": False,
        "operator_disposition": "schedule-manual-inspection",
        "disposition_relation": "sibling_of_accept",
        "disposition_is_sibling_of_accept": True,
        "proposal_family_dispositions": (
            "accept / reject / rewrite / request-evidence / "
            "schedule-manual-inspection / archive / cite "
            "(seven sibling outcomes per M05 §4.1)"
        ),
    }

    return {
        "pr51_packet": packet,
        "packet_binding_status": "UNBOUND",
        "packet_comparison_status": "UNKNOWN",
        "pr53_packet_validator_violations": list(packet_violations),
        "consumer_output": consumer_output,
        "effective_confidence_trace": trace_block,
        "proposal": proposal_block,
        "stage_status": "COMPLETED",
    }


# ----------------------------------------------------------------------
# Lane C — downstream investigation result re-entry.
# ----------------------------------------------------------------------


def _lane_c(
    engine: Engine,
    claim_id: int,
    gap_required_evidence_type: int,
    next_id,
) -> dict:
    # 11.1 Local downstream source fixture (no external execution).
    downstream_source_fixture = {
        "source_artifact_kind": "local_consumer_inspection_record",
        "source_artifact_reference": "local-inspection-001",
        "raw_observations": [
            {
                "observation_kind": "neutral",
                "observation_index": 1,
                "observation_value": "consumer-recorded fact",
            },
        ],
        "consumer_recorded_severity_label": "moderate",
        "consumer_recorded_confidence_label": "medium",
    }
    fixture_before_snapshot = copy.deepcopy(downstream_source_fixture)

    # 11.2 Result trace — separate deepcopy; no mutable alias with
    # the source fixture.
    result_fragment = copy.deepcopy(
        downstream_source_fixture["raw_observations"][0],
    )
    result_trace = {
        "record_kind": "downstream_result_trace",
        "source_artifact_reference": (
            downstream_source_fixture["source_artifact_reference"]
        ),
        "result_fragment": result_fragment,
        "translation_basis": {
            "consumer_translation_kind": (
                "neutral mapping under local example policy"
            ),
            "notes": "no automatic adapter to role conversion",
        },
        "integrity_note": (
            "operational failure and semantic ambiguity are recorded "
            "as distinct conditions (M06 §7); this fixture is fully "
            "resolved"
        ),
        "interpretation_status": "RESOLVED",
        "is_ragcore_evidence": False,
    }

    # 11.3 Explicit role decision for the result fragment.
    consumer_role_decision = {
        "consumer_decision": (
            "consumer assigned a local supporting role to the fragment"
        ),
        "automatic_key_match_used": False,
    }

    invocations: list[dict] = []

    # Cycle 4 — add_evidence.
    ev_args = {
        "claim_id": claim_id,
        "raw_ref_id": 1,
        "evidence_type": gap_required_evidence_type,
        "strength": 0.6,
    }
    ev_source_basis = {
        "result_trace_reference": result_trace["source_artifact_reference"],
        "result_fragment_snapshot": copy.deepcopy(result_fragment),
        "strength_translation": {
            "input": downstream_source_fixture[
                "consumer_recorded_confidence_label"
            ],
            "consumer_translation_rule": (
                "consumer-selected strength under local example policy "
                "(strength is NOT a direct copy of any external numeric "
                "score)"
            ),
            "selected_strength_value": ev_args["strength"],
        },
        "consumer_role_decision": copy.deepcopy(consumer_role_decision),
    }
    ev_cand = _build_candidate(
        next_id, target_method="add_evidence", arguments=ev_args,
        source_basis=ev_source_basis,
        expected_effect=(
            "register a new Evidence supporting the existing Claim"
        ),
        policy_assumptions=["local example policy"],
        materialized_at_revision=engine.state_identity().revision,
    )
    ev_decision_identity = _identity_dict(engine.state_identity())
    ev_decision = _build_decision(
        next_id, decision_family="mutation_review",
        subject_snapshot=ev_cand,
        disposition=_explicit_review(True, ""),
        decision_state_identity=ev_decision_identity,
        supersedes=None, note="approved",
    )
    ev_reval_5_5 = _revalidate(
        ev_decision_identity, _identity_dict(engine.state_identity()),
        "stage_5_5_materialization",
    )
    ev_request = _build_request(
        next_id, ev_cand,
        decision_record_id=ev_decision["decision_record_id"],
        decision_state_identity=ev_decision_identity,
    )
    ev_reval_6 = _revalidate(
        ev_decision_identity, _identity_dict(engine.state_identity()),
        "stage_6_invocation",
    )
    ev_id_before = _identity_dict(engine.state_identity())
    evidence_id = engine.add_evidence(**ev_request["arguments"])
    ev_id_after = _identity_dict(engine.state_identity())
    ev_receipt = _build_receipt(
        next_id, ev_request, ev_id_before, ev_id_after, evidence_id,
    )
    invocations.append({
        "target_method": "add_evidence",
        "arguments": copy.deepcopy(ev_request["arguments"]),
        "candidate": ev_cand,
        "operator_decision_record": ev_decision,
        "reviewed_mutation_request": ev_request,
        "revalidations": {
            "stage_5_5_materialization": ev_reval_5_5,
            "stage_6_invocation": ev_reval_6,
        },
        "call_receipt": ev_receipt,
        "returned_id": evidence_id,
        "source_basis": copy.deepcopy(ev_source_basis),
    })

    # Cycle 5 — resolve_gaps_for_evidence (separate review cycle).
    rg_args = {"evidence_id": evidence_id}
    rg_cand = _build_candidate(
        next_id, target_method="resolve_gaps_for_evidence",
        arguments=rg_args,
        source_basis={"evidence_id_from_previous_cycle": evidence_id},
        expected_effect=(
            "explicitly resolve any matching Gap for this Evidence"
        ),
        policy_assumptions=["separate review cycle per M08 §14"],
        materialized_at_revision=engine.state_identity().revision,
    )
    rg_decision_identity = _identity_dict(engine.state_identity())
    rg_decision = _build_decision(
        next_id, decision_family="mutation_review",
        subject_snapshot=rg_cand,
        disposition=_explicit_review(True, ""),
        decision_state_identity=rg_decision_identity,
        supersedes=None, note="approved",
    )
    rg_reval_5_5 = _revalidate(
        rg_decision_identity, _identity_dict(engine.state_identity()),
        "stage_5_5_materialization",
    )
    rg_request = _build_request(
        next_id, rg_cand,
        decision_record_id=rg_decision["decision_record_id"],
        decision_state_identity=rg_decision_identity,
    )
    rg_reval_6 = _revalidate(
        rg_decision_identity, _identity_dict(engine.state_identity()),
        "stage_6_invocation",
    )
    rg_id_before = _identity_dict(engine.state_identity())
    resolved_gap_ids = engine.resolve_gaps_for_evidence(
        **rg_request["arguments"],
    )
    rg_id_after = _identity_dict(engine.state_identity())
    rg_receipt = _build_receipt(
        next_id, rg_request, rg_id_before, rg_id_after,
        list(resolved_gap_ids),
    )
    invocations.append({
        "target_method": "resolve_gaps_for_evidence",
        "arguments": copy.deepcopy(rg_request["arguments"]),
        "candidate": rg_cand,
        "operator_decision_record": rg_decision,
        "reviewed_mutation_request": rg_request,
        "revalidations": {
            "stage_5_5_materialization": rg_reval_5_5,
            "stage_6_invocation": rg_reval_6,
        },
        "call_receipt": rg_receipt,
        "returned_resolved_gap_ids": list(resolved_gap_ids),
    })

    # Cycle 6 — confirm_claim_if_ready (separate review cycle).
    cl_args = {"claim_id": claim_id}
    cl_cand = _build_candidate(
        next_id, target_method="confirm_claim_if_ready",
        arguments=cl_args,
        source_basis={"claim_id_from_lane_a": claim_id},
        expected_effect=(
            "explicitly transition the Claim to CONFIRMED if eligible"
        ),
        policy_assumptions=["separate review cycle per M08 §14"],
        materialized_at_revision=engine.state_identity().revision,
    )
    cl_decision_identity = _identity_dict(engine.state_identity())
    cl_decision = _build_decision(
        next_id, decision_family="mutation_review",
        subject_snapshot=cl_cand,
        disposition=_explicit_review(True, ""),
        decision_state_identity=cl_decision_identity,
        supersedes=None, note="approved",
    )
    cl_reval_5_5 = _revalidate(
        cl_decision_identity, _identity_dict(engine.state_identity()),
        "stage_5_5_materialization",
    )
    cl_request = _build_request(
        next_id, cl_cand,
        decision_record_id=cl_decision["decision_record_id"],
        decision_state_identity=cl_decision_identity,
    )
    cl_reval_6 = _revalidate(
        cl_decision_identity, _identity_dict(engine.state_identity()),
        "stage_6_invocation",
    )
    cl_id_before = _identity_dict(engine.state_identity())
    confirmed = engine.confirm_claim_if_ready(**cl_request["arguments"])
    cl_id_after = _identity_dict(engine.state_identity())
    cl_receipt = _build_receipt(
        next_id, cl_request, cl_id_before, cl_id_after, confirmed,
    )
    invocations.append({
        "target_method": "confirm_claim_if_ready",
        "arguments": copy.deepcopy(cl_request["arguments"]),
        "candidate": cl_cand,
        "operator_decision_record": cl_decision,
        "reviewed_mutation_request": cl_request,
        "revalidations": {
            "stage_5_5_materialization": cl_reval_5_5,
            "stage_6_invocation": cl_reval_6,
        },
        "call_receipt": cl_receipt,
        "returned_lifecycle_flag": confirmed,
    })

    return {
        "network_invocation": False,
        "tool_invocation": False,
        "subprocess_invocation": False,
        "downstream_source_fixture_before": fixture_before_snapshot,
        "downstream_source_fixture_after": copy.deepcopy(
            downstream_source_fixture,
        ),
        "result_trace": result_trace,
        "consumer_role_decision": copy.deepcopy(consumer_role_decision),
        "explicit_invocation_sequence": invocations,
        "produced_ids": {
            "evidence_id": evidence_id,
            "resolved_gap_ids": list(resolved_gap_ids),
        },
        "lifecycle_confirmed_flag": confirmed,
        "stage_status": "COMPLETED",
    }


# ----------------------------------------------------------------------
# Negative stale-decision probes (M05 §7.3 B / C / D).
# These probes never call any reusable validator / packet builder /
# trace method; they only construct EngineStateIdentity values and
# compare them by value equality.
# ----------------------------------------------------------------------


_NOT_ELIGIBLE_NOTE = "not eligible for decision reuse under M05"


def _negative_probes() -> dict:
    # Case B — same engine_token, different revision.
    engine_b = Engine()
    engine_b.add_entity(entity_type=1)
    captured_b = _identity_dict(engine_b.state_identity())
    engine_b.add_entity(entity_type=2)
    current_b = _identity_dict(engine_b.state_identity())
    case_b_eligible = (captured_b == current_b)
    case_b = {
        "captured_decision_identity": captured_b,
        "current_identity": current_b,
        "verdict": "eligible" if case_b_eligible else "not_eligible",
        "invocation_suppressed": not case_b_eligible,
        "note": _NOT_ELIGIBLE_NOTE,
    }

    # Case C — different engine_token.
    engine_c1 = Engine()
    engine_c1.add_entity(entity_type=1)
    captured_c = _identity_dict(engine_c1.state_identity())
    engine_c2 = Engine()
    engine_c2.add_entity(entity_type=1)
    current_c = _identity_dict(engine_c2.state_identity())
    case_c_eligible = (captured_c == current_c)
    case_c = {
        "captured_decision_identity": captured_c,
        "current_identity": current_c,
        "verdict": "eligible" if case_c_eligible else "not_eligible",
        "invocation_suppressed": not case_c_eligible,
        "note": _NOT_ELIGIBLE_NOTE,
    }

    # Case D — missing or malformed identity.
    engine_d = Engine()
    engine_d.add_entity(entity_type=1)
    current_d = _identity_dict(engine_d.state_identity())
    missing_identity = None
    case_d_missing_eligible = (missing_identity == current_d)
    malformed_identity = {
        "engine_token": "",
        "revision": -1,
    }
    case_d_malformed_eligible = (malformed_identity == current_d)
    case_d_eligible = (
        case_d_missing_eligible or case_d_malformed_eligible
    )
    case_d = {
        "missing_identity_record": {
            "captured_decision_identity": None,
            "current_identity": current_d,
            "verdict": (
                "eligible" if case_d_missing_eligible else "not_eligible"
            ),
            "invocation_suppressed": not case_d_missing_eligible,
            "note": _NOT_ELIGIBLE_NOTE,
        },
        "malformed_identity_record": {
            "captured_decision_identity": malformed_identity,
            "current_identity": current_d,
            "verdict": (
                "eligible" if case_d_malformed_eligible else "not_eligible"
            ),
            "invocation_suppressed": not case_d_malformed_eligible,
            "note": _NOT_ELIGIBLE_NOTE,
        },
        "verdict": "eligible" if case_d_eligible else "not_eligible",
        "invocation_suppressed": not case_d_eligible,
        "note": _NOT_ELIGIBLE_NOTE,
    }

    return {
        "case_B_same_token_diff_revision": case_b,
        "case_C_different_token": case_c,
        "case_D_missing_or_malformed_identity": case_d,
        "overall_note": _NOT_ELIGIBLE_NOTE,
    }


# ----------------------------------------------------------------------
# Final state + non-authority locks.
# ----------------------------------------------------------------------


_NON_AUTHORITY_LOCKS = (
    "Adapter output != RoleAssignment",
    "RoleAssignment validator pass != operator acceptance",
    "EngineInputCandidate != accepted mutation",
    "ReviewedMutationRequest != automatic execution",
    "Packet validator pass != claim judgment",
    "Proposal validator pass != proposal acceptance",
    "Operator acceptance != Engine truth",
    "External result != ragcore.Evidence",
    "Evidence registration != automatic Gap resolution",
    "Evidence registration != automatic lifecycle transition",
    "effective_confidence != probability",
)


def _final_state(engine: Engine, lane_a: dict, lane_b: dict,
                 lane_c: dict) -> dict:
    final_identity = _identity_dict(engine.state_identity())
    return {
        "lane_a_engine_produced": True,
        "entity_created": True,
        "claim_created": True,
        "gap_created": True,
        "evidence_registered": True,
        "packet_built_seven_keys": (
            len(lane_b["pr51_packet"]) == 7
        ),
        "confidence_trace_available": True,
        "proposal_operator_decision_recorded": True,
        "downstream_result_trace_recorded": True,
        "gap_explicitly_resolved": bool(
            lane_c["produced_ids"]["resolved_gap_ids"]
        ),
        "lifecycle_explicitly_invoked": True,
        "claim_final_status": "CONFIRMED" if (
            lane_c["lifecycle_confirmed_flag"]
        ) else "NOT_CONFIRMED",
        "final_engine_identity": final_identity,
        "final_engine_identity_revision": final_identity["revision"],
        "automatic_execution_used": False,
    }


# ----------------------------------------------------------------------
# Entry point.
# ----------------------------------------------------------------------


def run_complete_domain_neutral_reference_operation() -> dict[str, Any]:
    """Run one full domain-neutral reference operation and return its
    local illustrative report. Each call constructs a fresh Engine
    and fresh records; no state persists between calls."""
    engine = Engine()
    next_id = _next_id_factory()

    lane_a = _lane_a(engine, next_id)
    claim_id = lane_a["produced_ids"]["claim_id"]
    gap_required_evidence_type = lane_a["gap_required_evidence_type"]
    lane_b = _lane_b(engine, claim_id)
    lane_c = _lane_c(
        engine, claim_id, gap_required_evidence_type, next_id,
    )

    negative_probe = _negative_probes()
    final_state = _final_state(engine, lane_a, lane_b, lane_c)

    return {
        "overall_status": "COMPLETE_REFERENCE_OPERATION",
        "fixture_origin_for_engine": "PRODUCED_BY_LANE_A",
        "lanes": {
            "external_ingress": lane_a,
            "engine_read_and_proposal": lane_b,
            "downstream_reentry": lane_c,
        },
        "negative_stale_decision_probe": negative_probe,
        "final_state": final_state,
        "non_authority_locks": list(_NON_AUTHORITY_LOCKS),
        "rule_stats_provenance_status": "NOT_ENTERED_M09",
    }


if __name__ == "__main__":
    import json
    report = run_complete_domain_neutral_reference_operation()
    print(json.dumps(report, default=str, indent=2))
