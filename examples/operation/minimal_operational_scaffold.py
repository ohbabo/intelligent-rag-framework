"""Minimal Operational Scaffold — PR70-M01.

Local illustrative operational maturity probe. This is an executable
**historical snapshot of PR70-M01**: the stage statuses describe
repository operational maturity AS OF M01 and are NOT the current
repository capability inventory. They are intentionally not rewritten
to later M02-M09 states. Where a later M-series PR superseded a PR70
open item (e.g. PR76-M07 closing OC-D in the trace layer, PR78-M09
closing OC-G in a consumer-owned layer), that closure is recorded as
``supersession`` metadata on the relevant diagnosis field rather than
by editing the historical rows. The report carries an explicit
``report_temporality`` block (mode=HISTORICAL_SNAPSHOT).

This module assembles the existing repository components into
three lanes (External ingress / Pre-seeded Engine read /
Downstream re-entry) and produces a deterministic plain dict
that exposes:

  - which stages connect to existing artifacts at PR70-M01
  - which stages require an explicit manual fixture because the
    production handoff is not defined
  - which stages are partial
  - which stages are blocked at the current authority boundary
  - which stages are entirely undefined and need a future
    contract

The dict, its keys, the stage status strings, and the lane
labels are local illustrative data. They are NOT:

  - a canonical operational schema
  - a public framework type
  - a snapshot shape
  - a consumer-contract object
  - an operator-decision record format
  - an Engine input contract

This scaffold does not complete the operational spine. It makes
the current operational discontinuities explicit, executable,
and reviewable.

Non-authority locks (also written into the report):

  Adapter output           != RoleAssignment
  RoleAssignment           != Engine object
  RoleAssignment validator
    pass                   != operator acceptance
  EngineInputCandidate     != accepted mutation
  ReviewedMutationRequest  != automatic execution
  Packet validator pass    != claim judgment
  Proposal validator pass  != proposal acceptance
  Operator acceptance      != Engine truth
  External result          != ragcore.Evidence
  Evidence registration    != automatic lifecycle transition
  effective_confidence     != probability

This file uses the existing repository pattern of importlib.util
loading so that examples/ stays untouched as a flat directory
(no __init__.py is added; no PYTHONPATH mutation is performed).
"""

from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path
from pprint import pprint
from typing import Any

from ragcore import (
    Engine,
)


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(
        name, _REPO_ROOT / relative_path,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ----- Existing artifacts loaded from their actual repo paths ---------------


_ADAPTER_TRACE_MOD = _load(
    "pr64_adapter_trace",
    "examples/adapter/minimal_external_adapter_example.py",
)
_ROLE_EXAMPLE_MOD = _load(
    "pr61_role_example",
    "examples/role_assignment/minimal_consumer_example.py",
)
_ROLE_VALIDATOR_MOD = _load(
    "pr62_role_validator",
    "examples/role_assignment/role_assignment_validator.py",
)
_INSPECTOR_MOD = _load(
    "pr51_inspector",
    "examples/inspector/engine_inspector.py",
)
_PACKET_VALIDATOR_MOD = _load(
    "pr53_packet_validator",
    "examples/inspector/packet_validator.py",
)
_PROPOSAL_SCHEMA_MOD = _load(
    "pr55_proposal_schema",
    "examples/proposal/proposal_schema.py",
)
_PROPOSAL_SAFETY_MOD = _load(
    "pr56_proposal_safety",
    "examples/proposal/proposal_validator.py",
)


# Existing entry points — reused, NOT reimplemented.
_RESOLVED_TRANSLATION_TRACE = _ADAPTER_TRACE_MOD.RESOLVED_TRANSLATION_TRACE
_UNRESOLVED_TRANSLATION_TRACE = _ADAPTER_TRACE_MOD.UNRESOLVED_TRANSLATION_TRACE
_RESOLVED_ROLE_EXAMPLE = _ROLE_EXAMPLE_MOD.RESOLVED_EXAMPLE
_UNRESOLVED_ROLE_EXAMPLE = _ROLE_EXAMPLE_MOD.UNRESOLVED_EXAMPLE
_validate_role_assignment_boundaries = (
    _ROLE_VALIDATOR_MOD.validate_role_assignment_boundaries
)
_build_engine_context_packet = (
    _INSPECTOR_MOD.build_engine_context_packet
)
_validate_consumer_packet_interpretation = (
    _PACKET_VALIDATOR_MOD.validate_consumer_packet_interpretation
)
_validate_llm_proposal_shape = (
    _PROPOSAL_SCHEMA_MOD.validate_llm_proposal_shape
)
_validate_proposal_safety = (
    _PROPOSAL_SAFETY_MOD.validate_proposal_safety
)


# ----- Pre-seeded Engine fixture (Lane B only) ------------------------------
#
# This is NOT produced by Lane A. It exists solely so that Lane B has a
# Claim to read. The seeding uses only existing public Engine API calls;
# no dynamic dispatch, no method-name string lookup, no role-label-to-method
# mapping.


def _build_preseeded_engine_for_read_lane_only() -> tuple[Engine, int]:
    """Pre-seed an Engine for read-lane illustration purposes only.

    The returned Engine is NOT produced by Lane A. It is a
    MANUAL_FIXTURE that exists so that the read-lane validators
    have a Claim to look at.
    """
    engine = Engine()
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=1,
        rule_version=1,
        reason_code=0,
        base_confidence=0.5,
    )
    return engine, claim_id


# ----- Safe local consumer-output and proposal fixtures ---------------------
#
# These are hand-authored Lane B fixtures. They are MANUAL_FIXTURE
# objects: they are NOT generated by an LLM, NOT produced by any
# pipeline, NOT canonical schemas. They exist only so that the
# read-lane validators can run end-to-end.


def _build_safe_consumer_output_for_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Build a consumer-output dict that does not trigger packet
    validator F-codes against the given source packet."""
    claim = packet["claim"]
    return {
        "summary_note": (
            "synthetic consumer summary written for the read-lane "
            "scaffold; this is not a verdict and not a judgment"
        ),
        "referenced_claim_id": claim.id,
    }


def _build_safe_proposal_for_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Build a PR55-shape-conforming proposal dict (category =
    uncertainty_note) for the given source packet."""
    claim = packet["claim"]
    return {
        "category": "uncertainty_note",
        "target_claim_id": claim.id,
        "note": (
            "synthetic uncertainty note used by the read-lane "
            "scaffold; this is not a verdict"
        ),
    }


# ----- Lane composition -----------------------------------------------------


def _build_lane_a() -> list[dict[str, Any]]:
    """Lane A — External ingress / interpretation.

    Records seven stages with explicit status. No automatic
    AdapterTrace -> RoleAssignment conversion is performed.
    """
    # Stage A3 actually runs the PR62 validator against PR61 RESOLVED_EXAMPLE.
    resolved_violations = _validate_role_assignment_boundaries(
        deepcopy(_RESOLVED_ROLE_EXAMPLE),
    )
    a3_evidence = list(resolved_violations)  # deterministic list copy

    return [
        {
            "stage_id": "A1",
            "stage_label": "external item -> adapter trace",
            "status": "CONNECTED",
            "uses": [
                "examples/adapter/minimal_external_adapter_example.py "
                "RESOLVED_TRANSLATION_TRACE",
            ],
            "note": (
                "PR64 adapter trace is referenced verbatim; the "
                "scaffold does not construct a new canonical "
                "adapter schema."
            ),
        },
        {
            "stage_id": "A2",
            "stage_label": "adapter trace -> role assignment",
            "status": "UNDEFINED",
            "note": (
                "PR64 adapter representation and PR61 role-assignment "
                "representation are intentionally independent. The "
                "repository does not define a canonical automatic "
                "AdapterTrace -> RoleAssignment conversion."
            ),
            "missing_contract": "AdapterTrace -> RoleAssignment handoff",
        },
        {
            "stage_id": "A3",
            "stage_label": "existing role-assignment example validation",
            "status": "CONNECTED",
            "uses": [
                "examples/role_assignment/minimal_consumer_example.py "
                "RESOLVED_EXAMPLE",
                "examples/role_assignment/role_assignment_validator.py "
                "validate_role_assignment_boundaries",
            ],
            "result": a3_evidence,
            "result_meaning": (
                "validator returned empty list; meaning: 'local "
                "representational boundary violations not detected'. "
                "This does NOT mean: correct semantic role, true, "
                "verified, operator accepted, Engine accepted, "
                "mutation authorized."
            ),
        },
        {
            "stage_id": "A4",
            "stage_label": "unresolved role assignment",
            "status": "BLOCKED",
            "uses": [
                "examples/role_assignment/minimal_consumer_example.py "
                "UNRESOLVED_EXAMPLE",
            ],
            "note": (
                "Unresolved role assignment stays unresolved. The "
                "scaffold does not pick a convenience primary role "
                "and does not advance to EngineInputCandidate."
            ),
        },
        {
            "stage_id": "A5",
            "stage_label": "RoleAssignment -> EngineInputCandidate",
            "status": "UNDEFINED",
            "missing_contract": "EngineInputCandidate shape and source",
            "note": (
                "EngineInputCandidate is referenced as missing "
                "contract name only; no dataclass, TypedDict, or "
                "canonical dict is materialized by this scaffold."
            ),
        },
        {
            "stage_id": "A6",
            "stage_label": "EngineInputCandidate -> ReviewedMutationRequest",
            "status": "UNDEFINED",
            "missing_contract": (
                "ReviewedMutationRequest shape and review record"
            ),
            "note": (
                "Validator pass is NOT review acceptance. No "
                "ReviewedMutationRequest type is materialized."
            ),
        },
        {
            "stage_id": "A7",
            "stage_label": "ReviewedMutationRequest -> Engine mutation",
            "status": "BLOCKED",
            "note": (
                "No reviewed handoff is defined; the scaffold does "
                "not mutate the Engine from Lane A. No automatic "
                "dispatch, no method-name string execution, no role-"
                "label-to-method mapping."
            ),
        },
    ]


def _build_lane_b(engine: Engine, claim_id: int) -> list[dict[str, Any]]:
    """Lane B — Pre-seeded Engine read / proposal review.

    Uses ONLY public Engine API for fixture seeding. Runs PR51
    inspector, PR53 packet validator, PR55 proposal shape
    validator, and PR56 proposal safety validator against
    hand-authored fixtures.
    """
    packet = _build_engine_context_packet(engine, claim_id)
    consumer_output = _build_safe_consumer_output_for_packet(packet)
    proposal = _build_safe_proposal_for_packet(packet)

    packet_violations = _validate_consumer_packet_interpretation(
        consumer_output, packet,
    )
    shape_violations = _validate_llm_proposal_shape(
        proposal, packet,
    )
    safety_violations = _validate_proposal_safety(
        proposal, packet,
    )

    # All three should be empty for the hand-authored safe fixtures.
    b4_evidence = list(packet_violations)
    b6_shape_evidence = list(shape_violations)
    b6_safety_evidence = list(safety_violations)

    return [
        {
            "stage_id": "B1",
            "stage_label": "pre-seeded Engine fixture",
            "status": "MANUAL_FIXTURE",
            "fixture_origin": "PRESEEDED_FOR_READ_LANE_ONLY",
            "note": (
                "This Engine state was NOT produced by Lane A. It "
                "is a manual fixture so that the read-lane "
                "validators have a Claim to look at."
            ),
        },
        {
            "stage_id": "B2",
            "stage_label": "Engine -> context packet",
            "status": "CONNECTED",
            "uses": [
                "examples/inspector/engine_inspector.py "
                "build_engine_context_packet",
            ],
            "packet_keys": sorted(packet.keys()),
            "note": (
                "Packet shape is the existing PR51 seven-key shape. "
                "No new packet key is introduced by this scaffold."
            ),
        },
        {
            "stage_id": "B3",
            "stage_label": "packet state binding",
            "status": "UNDEFINED",
            "missing_contract": (
                "canonical Engine state identity / packet-to-state "
                "binding / capture atomicity proof / state revision / "
                "packet revision / canonical snapshot digest binding"
            ),
            "note": (
                "The scaffold does NOT fabricate packet_revision, "
                "state_revision, engine_revision, snapshot_digest, "
                "or capture_token. Timestamps and object counts are "
                "NOT used as revision proxies."
            ),
        },
        {
            "stage_id": "B4",
            "stage_label": "packet interpretation validator",
            "status": "CONNECTED",
            "uses": [
                "examples/inspector/packet_validator.py "
                "validate_consumer_packet_interpretation",
            ],
            "result": b4_evidence,
            "result_meaning": (
                "validator returned empty list; meaning: 'no "
                "selected structural unsafe interpretation "
                "detected'. This does NOT mean: packet correct, "
                "claim true, consumer output complete, operator "
                "acceptance, or execution permission."
            ),
        },
        {
            "stage_id": "B5",
            "stage_label": "proposal production",
            "status": "MANUAL_FIXTURE",
            "note": (
                "No LLM is invoked. The scaffold uses a PR55-shape-"
                "conforming synthetic proposal authored locally."
            ),
        },
        {
            "stage_id": "B6",
            "stage_label": "proposal validation",
            "status": "CONNECTED",
            "uses": [
                "examples/proposal/proposal_schema.py "
                "validate_llm_proposal_shape",
                "examples/proposal/proposal_validator.py "
                "validate_proposal_safety",
            ],
            "shape_result": b6_shape_evidence,
            "safety_result": b6_safety_evidence,
            "result_meaning": (
                "shape and safety validators returned empty lists; "
                "meaning: 'selected shape/safety violations not "
                "detected'. This does NOT mean: proposal correct, "
                "useful, accepted, executable, Engine mutation "
                "allowed, or final judgment."
            ),
        },
        {
            "stage_id": "B7",
            "stage_label": "validator pass -> operator acceptance",
            "status": "BLOCKED",
            "note": (
                "Operator acceptance is not derived from validator "
                "passes. accepted=True is NOT auto-set. PR57 "
                "boundary preserved."
            ),
        },
        {
            "stage_id": "B8",
            "stage_label": "operator decision record",
            "status": "UNDEFINED",
            "missing_contract": (
                "independent operator decision record and stale "
                "revalidation rule"
            ),
        },
    ]


def _build_lane_c() -> list[dict[str, Any]]:
    """Lane C — Downstream re-entry.

    Every stage records its current operational status; nothing
    is auto-executed.
    """
    return [
        {
            "stage_id": "C1",
            "stage_label": "operator decision record",
            "status": "UNDEFINED",
            "missing_contract": "operator decision record contract",
        },
        {
            "stage_id": "C2",
            "stage_label": "consumer-side investigation",
            "status": "TODO",
            "note": (
                "Investigation procedure is consumer-owned. The "
                "scaffold does not run any external tool or network "
                "call."
            ),
        },
        {
            "stage_id": "C3",
            "stage_label": "new external result trace",
            "status": "TODO",
            "note": (
                "External result traces are produced by adapters "
                "outside the scaffold. No synthetic tool execution "
                "happens here."
            ),
        },
        {
            "stage_id": "C4",
            "stage_label": "result role assignment",
            "status": "TODO",
            "note": (
                "Each new result is reinterpreted by the consumer "
                "policy. The scaffold does not advance this stage "
                "automatically."
            ),
        },
        {
            "stage_id": "C5",
            "stage_label": "EngineInputCandidate",
            "status": "UNDEFINED",
            "missing_contract": "EngineInputCandidate shape and source",
        },
        {
            "stage_id": "C6",
            "stage_label": "ReviewedMutationRequest",
            "status": "UNDEFINED",
            "missing_contract": (
                "ReviewedMutationRequest shape and review record"
            ),
        },
        {
            "stage_id": "C7",
            "stage_label": "explicit re-entry authorization",
            "status": "BLOCKED",
            "note": (
                "External result -> ragcore.Evidence is NOT "
                "automatic. tool output -> Evidence direct pipe is "
                "NOT permitted. score -> Evidence.strength direct "
                "identity is NOT permitted. operator acceptance -> "
                "automatic Engine mutation is NOT permitted. "
                "downstream result -> automatic lifecycle "
                "transition is NOT permitted."
            ),
        },
    ]


def _build_blocked_handoffs(lanes: dict[str, list[dict[str, Any]]]) -> list[str]:
    out: list[str] = []
    for lane_name, stages in lanes.items():
        for stage in stages:
            if stage["status"] in ("BLOCKED", "UNDEFINED"):
                out.append(f"{lane_name}:{stage['stage_id']} {stage['stage_label']}")
    return sorted(out)


def _required_future_contracts() -> list[dict[str, str]]:
    return [
        {
            "id": "OC-A",
            "label": (
                "RoleAssignment -> EngineInputCandidate -> "
                "ReviewedMutationRequest -> explicit Engine "
                "public API call"
            ),
        },
        {
            "id": "OC-C",
            "label": (
                "state identity / packet-to-state binding / "
                "capture atomicity"
            ),
        },
        {
            "id": "OC-B",
            "label": (
                "operator decision record / decision-time state "
                "identity / stale revalidation"
            ),
        },
        {
            "id": "OC-E",
            "label": "downstream result re-entry boundary",
        },
        {
            "id": "OC-D",
            "label": (
                "effective-confidence calculation trace / policy "
                "identity / source-state reference"
            ),
        },
        {
            "id": "OC-F",
            "label": "complete domain-neutral reference operation",
        },
        {
            "id": "OC-G",
            "label": "RuleStats update provenance",
        },
    ]


def _read_consistency_requirements() -> list[str]:
    return [
        (
            "capture atomicity: two reads of the same Engine state "
            "must be mechanically verifiable as the same state"
        ),
        (
            "state identity: a packet must reference the source "
            "Engine state by an explicit identifier"
        ),
        (
            "packet-to-state binding: an external consumer must "
            "be able to detect a stale packet"
        ),
        (
            "calculation policy identity: effective_confidence "
            "values produced under different policies must not "
            "compare equal by value alone"
        ),
    ]


def _consumer_owned_decisions() -> list[str]:
    return [
        "how to interpret an external item in a specific context",
        "which RoleAssignment representation to use",
        "whether to hold an unresolved assignment",
        "whether to materialize an Engine input candidate",
        "whether to route a candidate to operator review",
        "which Engine public API to call",
        "whether to accept a proposal after validators pass",
        "whether to launch a downstream investigation",
        "whether to feed a downstream result back into the Engine",
        "whether to invoke a lifecycle API call explicitly",
        "whether to update RuleStats",
    ]


def _non_authority_locks() -> list[str]:
    return [
        "Adapter output != RoleAssignment",
        "RoleAssignment != Engine object",
        "RoleAssignment validator pass != operator acceptance",
        "EngineInputCandidate != accepted mutation",
        "ReviewedMutationRequest != automatic execution",
        "Packet validator pass != claim judgment",
        "Proposal validator pass != proposal acceptance",
        "Operator acceptance != Engine truth",
        "External result != ragcore.Evidence",
        "Evidence registration != automatic lifecycle transition",
        "effective_confidence != probability",
    ]


def _effective_confidence_trace_diagnosis(packet: dict[str, Any]) -> dict[str, Any]:
    """Diagnose effective_confidence trace completeness AS OF PR70-M01,
    with explicit M07 supersession metadata.

    The historical M01 answers below are intentionally NOT recomputed
    against current capability. PR76-M07 later closed OC-D in the trace
    layer; that closure is recorded in ``supersession`` rather than by
    rewriting the historical answers.
    """
    return {
        "assessment_scope": "HISTORICAL_PR70_M01",
        "value_available_from_pr51_packet_at_m01": (
            "effective_confidence" in packet
        ),
        "modifier_breakdown_available_at_m01": (
            "no — at PR70-M01 the PR51 packet did not include a "
            "per-modifier breakdown; consumers had to call modifier "
            "helpers individually, which were not exposed"
        ),
        "calculation_policy_identity_available_at_m01": (
            "no — at PR70-M01 there was no explicit confidence_policy_id "
            "or composition_revision field"
        ),
        "source_state_reference_available_at_m01": (
            "no — at PR70-M01, see B3 packet state binding UNDEFINED"
        ),
        "forbidden_substitutions": [
            "snapshot schema_version != confidence policy version",
            "module hash != semantic policy identity",
            "effective_confidence != probability",
        ],
        "historical_future_contract": "OC-D",
        "supersession": {
            "status": "CLOSED_BY_PR76_M07",
            "public_type": "EffectiveConfidenceTrace",
            "public_method": (
                "Engine.compute_effective_confidence_with_trace"
            ),
            "trace_capabilities": [
                "status_modifier",
                "freshness_modifier",
                "gap_modifier",
                "count_modifier",
                "rule_stats_modifier",
                "evidence_type_modifier",
                "calculation_policy_id",
                "source_state_identity",
            ],
            "pr51_packet_shape_changed": False,
            "b3_packet_binding_retroactively_connected": False,
        },
    }


def _rule_stats_provenance_diagnosis() -> dict[str, Any]:
    """Record open RuleStats provenance questions AS OF PR70-M01 against
    Engine-internal fields, with explicit M09 supersession metadata.

    The six answers describe Engine-internal provenance fields and remain
    true: PR78-M09 closed OC-G through a consumer-owned provenance
    contract and an executable example, NOT by adding an Engine-internal
    provenance store. "answers remain no" therefore does not mean OC-G
    is unimplemented.
    """
    return {
        "assessment_scope": "ENGINE_INTERNAL_PROVENANCE_FIELDS",
        "caller_identity_recorded": "no",
        "update_reason_recorded": "no",
        "source_observation_reference_recorded": "no",
        "delta_provenance_recorded": "no",
        "precision_input_basis_recorded": "no",
        "policy_reference_recorded": "no",
        "scaffold_note": (
            "PR70-M01 does NOT connect update_rule_stats() to any "
            "operational flow and does NOT add fields to Engine."
        ),
        "historical_future_contract": "OC-G",
        "supersession": {
            "status": "CLOSED_BY_PR78_M09_CONSUMER_OWNED_LAYER",
            "scope": "CONSUMER_OWNED_EXAMPLE_LOCAL",
            "engine_internal_fields_added": False,
            "automatic_rule_stats_update_added": False,
        },
    }


# ----- Public scaffold entry point ------------------------------------------


def build_minimal_operational_scaffold() -> dict[str, Any]:
    """Assemble the PR70-M01 operational scaffold report.

    This is an executable **historical snapshot** of PR70-M01. The stage
    statuses describe repository operational maturity AS OF M01; they are
    NOT a current capability inventory and are intentionally not rewritten
    to later M02-M09 states. Later M-series work may supersede individual
    open items; such closures are recorded as ``supersession`` metadata
    (see the two diagnosis fields) without changing the historical rows.

    Returns a deterministic plain dict. The dict shape is local
    illustrative data; it is not a public framework contract.
    """
    lane_a = _build_lane_a()
    engine, claim_id = _build_preseeded_engine_for_read_lane_only()
    lane_b = _build_lane_b(engine, claim_id)
    lane_c = _build_lane_c()

    # B2 result was already collected inside lane_b construction;
    # rebuild the packet once more for the confidence trace
    # diagnosis so it does not depend on private lane internals.
    packet_for_confidence_trace = _build_engine_context_packet(
        engine, claim_id,
    )

    lanes = {
        "external_ingress": lane_a,
        "engine_read_and_proposal": lane_b,
        "downstream_reentry": lane_c,
    }

    return {
        "scaffold_kind": (
            "local illustrative operational maturity probe"
        ),
        "report_temporality": {
            "mode": "HISTORICAL_SNAPSHOT",
            "internal_track": "PR70-M01",
            "base_commit": (
                "9874b44127c765176cb4ec6bb7158e5f7a8b7316"
            ),
            "merge_commit": (
                "896e01ea3142e17a591a3054963d498744709e2e"
            ),
            "stage_statuses_as_of": "PR70-M01",
            "current_capability_inventory": False,
        },
        "overall_status": "INCOMPLETE",
        "fixture_origin_for_engine": "PRESEEDED_FOR_READ_LANE_ONLY",
        "lanes": lanes,
        "blocked_handoffs": _build_blocked_handoffs(lanes),
        "required_future_contracts": _required_future_contracts(),
        "required_future_contracts_scope": (
            "HISTORICAL_OPEN_ITEMS_AT_PR70_M01"
        ),
        "read_consistency_requirements": _read_consistency_requirements(),
        "consumer_owned_decisions": _consumer_owned_decisions(),
        "non_authority_locks": _non_authority_locks(),
        "effective_confidence_trace_diagnosis": (
            _effective_confidence_trace_diagnosis(packet_for_confidence_trace)
        ),
        "rule_stats_provenance_diagnosis": (
            _rule_stats_provenance_diagnosis()
        ),
    }


if __name__ == "__main__":
    pprint(build_minimal_operational_scaffold(), sort_dicts=False, width=88)
