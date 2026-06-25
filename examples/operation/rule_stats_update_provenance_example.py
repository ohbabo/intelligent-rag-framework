"""RuleStats Update Provenance — PR78-M09 consumer-owned example.

A local illustrative example that exercises the approved M09 contract

  docs/architecture/RULE_STATS_UPDATE_PROVENANCE_CONTRACT.md

over the existing Engine RuleStats surface. It runs three cases —
VALUE_CHANGED, NO_VALUE_CHANGE, and a REJECTED unknown-pair attempt —
each through the full authority-gated handoff (candidate -> operator
review -> Stage 5.5 revalidation -> reviewed request -> Stage 6
revalidation -> directly-written Engine call or rejection -> receipt),
and records the six OC-G provenance meanings as distinct, inspectable
facts.

This file and the dict it returns are NOT:
  - a public ragcore type
  - a canonical provenance schema
  - a snapshot schema
  - an Engine return type
  - a cross-consumer wire format
  - an authentication record
  - a truth verdict
  - a rule-quality verdict

Each plain-dict record (candidate, operator decision, reviewed
mutation request, receipt) is an example-local illustrative record.
The Engine's real opaque engine_token is recorded as-is; nothing here
adds provenance to the Engine, its snapshot, or its public API.

Entry point:

    run_rule_stats_update_provenance_example() -> dict[str, Any]
"""

from __future__ import annotations

import copy
from dataclasses import fields
from typing import Any

from ragcore import (
    RULE_MATURITY_STABLE,
    Engine,
    RuleDefinition,
    RuleStats,
    ScoreValue,
)


# ----------------------------------------------------------------------
# Local record helpers (plain dict only; example-local).
# ----------------------------------------------------------------------


def _next_id_factory():
    """Per-call deterministic id generator. A fresh generator is used
    for each run so no module-level state leaks across calls and the
    non-token report content stays deterministic."""
    state = {"n": 0}

    def next_id(prefix: str) -> str:
        state["n"] += 1
        return f"{prefix}-{state['n']}"

    return next_id


def _identity_dict(identity) -> dict:
    """Plain-dict projection of EngineStateIdentity. The real opaque
    engine_token is preserved as-is (no normalization, no fabrication)."""
    return {
        "engine_token": identity.engine_token,
        "revision": identity.revision,
    }


def _build_candidate(
    next_id,
    rule_id: int,
    rule_version: int,
    arguments: dict,
    score_actions: dict,
    provenance: dict,
    expected_effect: str,
    materialized_at_state_identity: dict,
) -> dict:
    return {
        "record_kind": "rule_stats_update_candidate",
        "candidate_id": next_id("cand"),
        "target_method": "update_rule_stats",
        "rule_id": rule_id,
        "rule_version": rule_version,
        "arguments": copy.deepcopy(arguments),
        "score_actions": copy.deepcopy(score_actions),
        "expected_effect": expected_effect,
        "explicit_non_effects": [
            "does not transition any Claim lifecycle state",
            "does not assert the rule is correct or high quality",
            "does not register a new rule",
        ],
        # Six OC-G provenance meanings, each a distinct field.
        "caller_identity_reference": provenance["caller_identity_reference"],
        "update_reason": copy.deepcopy(provenance["update_reason"]),
        "source_observation_references": copy.deepcopy(
            provenance["source_observation_references"],
        ),
        "delta_provenance": copy.deepcopy(provenance["delta_provenance"]),
        "precision_input_basis": copy.deepcopy(
            provenance["precision_input_basis"],
        ),
        "policy_reference": provenance["policy_reference"],
        "materialized_at_state_identity": copy.deepcopy(
            materialized_at_state_identity,
        ),
    }


def _build_operator_decision(
    next_id, candidate: dict, decision_state_identity: dict,
) -> dict:
    return {
        "record_kind": "operator_decision_record",
        "status": "OPERATOR_REVIEW",
        "decision_record_id": next_id("dec"),
        "decision_family": "rule_stats_update_review",
        "subject_snapshot": copy.deepcopy(candidate),
        "disposition": "approved",
        "decision_state_identity": copy.deepcopy(decision_state_identity),
        "note": "approved on local consumer review",
    }


def _revalidate(
    decision_state_identity: dict, current_state_identity: dict, moment: str,
) -> dict:
    eligible = decision_state_identity == current_state_identity
    return {
        "moment": moment,
        "status": "STATE_REVALIDATED",
        "decision_state_identity": copy.deepcopy(decision_state_identity),
        "current_state_identity": copy.deepcopy(current_state_identity),
        "verdict": "eligible" if eligible else "not_eligible",
        "invocation_suppressed": not eligible,
    }


def _build_reviewed_request(
    next_id, candidate: dict, decision_record_id: str,
    decision_state_identity: dict,
) -> dict:
    """The approved_candidate_snapshot and the request arguments are
    each a separate deepcopy, so candidate.arguments, snapshot.arguments,
    request.arguments, and (later) receipt.reviewed_arguments are four
    distinct value-equal dict objects."""
    return {
        "record_kind": "reviewed_mutation_request",
        "request_id": next_id("req"),
        "approved_candidate_snapshot": copy.deepcopy(candidate),
        "approved_decision_record_id": decision_record_id,
        "target_method": candidate["target_method"],
        "arguments": copy.deepcopy(candidate["arguments"]),
        "decision_state_identity": copy.deepcopy(decision_state_identity),
    }


def _build_success_receipt(
    next_id, request: dict, identity_before: dict, identity_after: dict,
    rule_stats_before: RuleStats, rule_stats_after: RuleStats,
    engine_return_value, actual_effect: str,
) -> dict:
    return {
        "record_kind": "rule_stats_update_receipt",
        "receipt_id": next_id("rcpt"),
        "request_id": request["request_id"],
        "target_method": request["target_method"],
        "reviewed_arguments": copy.deepcopy(request["arguments"]),
        "identity_before": copy.deepcopy(identity_before),
        "identity_after": copy.deepcopy(identity_after),
        "rule_stats_before": rule_stats_before,
        "rule_stats_after": rule_stats_after,
        "engine_return_value": engine_return_value,
        "actual_effect": actual_effect,
        "update_invoked": True,
    }


def _build_failed_attempt_receipt(
    next_id, request: dict, identity_before_attempt: dict,
    rejection_cause: str,
) -> dict:
    """Records only the facts actually available for a rejected attempt.
    For an unknown (rule_id, rule_version) the pre-read raises, so there
    is no RuleStats before/after to record — those keys are deliberately
    omitted (never fabricated)."""
    return {
        "record_kind": "rule_stats_update_failed_attempt_receipt",
        "receipt_id": next_id("rcpt"),
        "request_id": request["request_id"],
        "target_method": request["target_method"],
        "reviewed_arguments": copy.deepcopy(request["arguments"]),
        "identity_before_attempt": copy.deepcopy(identity_before_attempt),
        "rejection_cause": rejection_cause,
        "actual_effect": "REJECTED",
        "update_invoked": False,
        "available_facts_only": True,
    }


# ----------------------------------------------------------------------
# Authority handoff up to the pre-invocation boundary (shared).
# ----------------------------------------------------------------------


def _review_and_revalidate(
    engine: Engine, next_id, rule_id, rule_version, arguments,
    score_actions, provenance, expected_effect,
) -> dict:
    """candidate -> decision -> Stage 5.5 -> request -> Stage 6.
    Returns a dict with all materialized records and the eligibility
    of both revalidation moments. No Engine mutation occurs here."""
    materialized_identity = _identity_dict(engine.state_identity())
    candidate = _build_candidate(
        next_id, rule_id, rule_version, arguments, score_actions,
        provenance, expected_effect, materialized_identity,
    )
    decision_identity = _identity_dict(engine.state_identity())
    decision = _build_operator_decision(next_id, candidate, decision_identity)

    reval_5_5 = _revalidate(
        decision_identity, _identity_dict(engine.state_identity()),
        "stage_5_5_materialization",
    )
    request = None
    reval_6 = None
    if decision["disposition"] == "approved" and (
        reval_5_5["verdict"] == "eligible"
    ):
        request = _build_reviewed_request(
            next_id, candidate, decision["decision_record_id"],
            decision_identity,
        )
        reval_6 = _revalidate(
            decision_identity, _identity_dict(engine.state_identity()),
            "stage_6_invocation",
        )
    return {
        "candidate": candidate,
        "operator_decision_record": decision,
        "reviewed_mutation_request": request,
        "revalidations": {
            "stage_5_5_materialization": reval_5_5,
            **(
                {"stage_6_invocation": reval_6}
                if reval_6 is not None else {}
            ),
        },
        "_decision_disposition": decision["disposition"],
        "_stage_5_5_eligible": reval_5_5["verdict"] == "eligible",
        "_stage_6_eligible": (
            reval_6 is not None and reval_6["verdict"] == "eligible"
        ),
    }


def _assemble_case(reviewed: dict, receipt: dict, rule_id, rule_version,
                   extra: dict | None = None) -> dict:
    case = {
        "pair": {"rule_id": rule_id, "rule_version": rule_version},
        "candidate": reviewed["candidate"],
        "operator_decision_record": reviewed["operator_decision_record"],
        "reviewed_mutation_request": reviewed["reviewed_mutation_request"],
        "revalidations": reviewed["revalidations"],
        "receipt": receipt,
    }
    if extra:
        case.update(extra)
    return case


# ----------------------------------------------------------------------
# Case: VALUE_CHANGED / NO_VALUE_CHANGE (successful invocation).
# ----------------------------------------------------------------------


def _successful_case(
    rule_id, rule_version, arguments, score_actions, provenance,
    expected_effect, next_id,
) -> dict:
    """Registers a rule on a fresh Engine and performs one fully gated,
    directly-written update_rule_stats call, classifying the effect from
    actual public before/after reads (not from the None return)."""
    engine = Engine()
    engine.register_rule(
        RuleDefinition(
            id=rule_id,
            version=rule_version,
            maturity=RULE_MATURITY_STABLE,
            prior_confidence=ScoreValue(0.5),
        )
    )
    reviewed = _review_and_revalidate(
        engine, next_id, rule_id, rule_version, arguments, score_actions,
        provenance, expected_effect,
    )
    assert reviewed["_stage_6_eligible"], (
        "happy-path successful case must reach Stage 6 eligible"
    )
    request = reviewed["reviewed_mutation_request"]
    req_args = request["arguments"]

    identity_before = _identity_dict(engine.state_identity())
    stats_before = engine.get_rule_stats(rule_id, rule_version)

    result = engine.update_rule_stats(
        rule_id,
        rule_version,
        firing_delta=req_args["firing_delta"],
        true_delta=req_args["true_delta"],
        false_delta=req_args["false_delta"],
        observed_precision=req_args["observed_precision"],
        false_positive_rate=req_args["false_positive_rate"],
    )

    identity_after = _identity_dict(engine.state_identity())
    stats_after = engine.get_rule_stats(rule_id, rule_version)

    # Classify from the actual reads, NOT from the None return.
    if stats_before != stats_after:
        actual_effect = "VALUE_CHANGED"
    else:
        actual_effect = "NO_VALUE_CHANGE"

    receipt = _build_success_receipt(
        next_id, request, identity_before, identity_after,
        stats_before, stats_after, result, actual_effect,
    )
    return _assemble_case(reviewed, receipt, rule_id, rule_version)


# ----------------------------------------------------------------------
# Case: REJECTED unknown pair (suppressed invocation).
# ----------------------------------------------------------------------


def _rejected_unknown_pair_case(
    rule_id, rule_version, arguments, score_actions, provenance, next_id,
) -> dict:
    """A fully reviewed attempt against an unknown (rule_id, rule_version)
    pair. The pre-read raises, so update_rule_stats is never invoked and
    no RuleStats before/after is fabricated."""
    engine = Engine()
    reviewed = _review_and_revalidate(
        engine, next_id, rule_id, rule_version, arguments, score_actions,
        provenance, "attempt a RuleStats update for an unknown pair",
    )
    request = reviewed["reviewed_mutation_request"]
    identity_before_attempt = _identity_dict(engine.state_identity())

    update_invoked = False
    rejection_cause = None
    try:
        engine.get_rule_stats(rule_id, rule_version)
    except KeyError as exc:
        rejection_cause = (
            "pre-read engine.get_rule_stats failed for an unknown "
            f"(rule_id, rule_version) pair: {exc.args[0]!r}; "
            "update_rule_stats invocation suppressed"
        )
    # update_rule_stats is intentionally NOT called for the unknown pair.

    if rejection_cause is None:
        # Defensive: the contract assumes the unknown pair rejects at
        # pre-read; if it somehow did not, do not fabricate a success.
        rejection_cause = (
            "unknown pair did not reject at pre-read; invocation still "
            "suppressed (available-facts-only)"
        )

    receipt = _build_failed_attempt_receipt(
        next_id, request, identity_before_attempt, rejection_cause,
    )
    # update_invoked stays False; no Engine mutation occurred.
    assert update_invoked is False
    return _assemble_case(reviewed, receipt, rule_id, rule_version)


# ----------------------------------------------------------------------
# Non-authority locks (M09 §20) — example-local strings, not constants.
# ----------------------------------------------------------------------


_NON_AUTHORITY_LOCKS = (
    "provenance completeness != update correctness",
    "operator approval != Engine truth",
    "source observation != ragcore.Evidence",
    "observed_precision != ground truth",
    "observed_precision != probability of truth",
    "RuleStats modifier != rule quality verdict",
    "VALUE_CHANGED != rule quality improvement",
    "RuleStats update != Claim lifecycle transition",
    "caller identity reference != authentication proof",
    "policy reference != semantic correctness proof",
)


def _snapshot_boundary() -> dict:
    """Computed from the public snapshot surface; asserts no provenance
    history was added to the snapshot."""
    snapshot = Engine().to_snapshot()
    return {
        "schema_version": snapshot["schema_version"],
        "top_level_keys": len(snapshot),
        "has_provenance_history_key": (
            "rule_stats_update_provenance" in snapshot
            or "rule_stats_provenance_history" in snapshot
        ),
        "rule_stats_field_count": len(fields(RuleStats)),
    }


def _historical_boundary() -> dict:
    return {
        "m01_six_no_diagnosis": "historical; not modified by this example",
        "m01_future_contract": "OC-G (unchanged)",
        "m08_rule_stats_provenance_status": (
            "NOT_ENTERED_M09 (historical; not modified)"
        ),
        "retroactive_modification": False,
    }


# ----------------------------------------------------------------------
# Entry point.
# ----------------------------------------------------------------------


def run_rule_stats_update_provenance_example() -> dict[str, Any]:
    """Run one full RuleStats-update-provenance example and return its
    local illustrative report. Each call uses fresh Engines and fresh
    records; no module-level mutable state persists between calls."""
    next_id = _next_id_factory()

    value_changed = _successful_case(
        rule_id=101,
        rule_version=1,
        arguments={
            "rule_id": 101,
            "rule_version": 1,
            "firing_delta": 1,
            "true_delta": 1,
            "false_delta": 0,
            "observed_precision": ScoreValue(0.75),
            "false_positive_rate": None,
        },
        score_actions={
            "observed_precision": "SET",
            "false_positive_rate": "KEEP",
        },
        provenance={
            "caller_identity_reference": (
                "example:caller:rule-stats-reviewer"
            ),
            "update_reason": (
                "reviewed operational-outcome aggregation justified a "
                "firing+1 / true+1 update and a SET of observed_precision"
            ),
            "source_observation_references": [
                "example:observation:outcome-batch-0007",
            ],
            "delta_provenance": {
                "firing_delta": "one reviewed firing observation",
                "true_delta": "one reviewed confirmed-true outcome",
                "false_delta": "no confirmed-false outcomes in this set",
                "selection_rule": "consumer policy local-example.v1",
            },
            "precision_input_basis": {
                "set_value": 0.75,
                "numerator_meaning": "reviewed confirmed-true outcomes",
                "denominator_meaning": "reviewed fired outcomes",
                "note": "consumer-derived maturity evidence, NOT ground "
                        "truth or a probability of truth",
            },
            "policy_reference": "example:policy:rule-stats-update.v1",
        },
        expected_effect="advance firing_count and confirmed_true_count "
                        "and set observed_precision",
        next_id=next_id,
    )

    no_value_change = _successful_case(
        rule_id=202,
        rule_version=1,
        arguments={
            "rule_id": 202,
            "rule_version": 1,
            "firing_delta": 0,
            "true_delta": 0,
            "false_delta": 0,
            "observed_precision": None,
            "false_positive_rate": None,
        },
        score_actions={
            "observed_precision": "KEEP",
            "false_positive_rate": "KEEP",
        },
        provenance={
            "caller_identity_reference": (
                "example:caller:rule-stats-reviewer"
            ),
            "update_reason": (
                "deliberate zero-delta administrative re-review; no "
                "values change and both scores are kept"
            ),
            "source_observation_references": "NOT_APPLICABLE",
            "delta_provenance": {
                "firing_delta": "zero by design",
                "true_delta": "zero by design",
                "false_delta": "zero by design",
                "selection_rule": "administrative re-review; no outcomes "
                                  "selected",
            },
            "precision_input_basis": "NOT_APPLICABLE",
            "policy_reference": "example:policy:rule-stats-update.v1",
        },
        expected_effect="no aggregate value change; both scores kept",
        next_id=next_id,
    )

    rejected_unknown_pair = _rejected_unknown_pair_case(
        rule_id=999,
        rule_version=1,
        arguments={
            "rule_id": 999,
            "rule_version": 1,
            "firing_delta": 1,
            "true_delta": 0,
            "false_delta": 0,
            "observed_precision": None,
            "false_positive_rate": None,
        },
        score_actions={
            "observed_precision": "KEEP",
            "false_positive_rate": "KEEP",
        },
        provenance={
            "caller_identity_reference": (
                "example:caller:rule-stats-reviewer"
            ),
            "update_reason": (
                "attempt to update a rule pair that is not registered"
            ),
            "source_observation_references": [
                "example:observation:outcome-batch-0009",
            ],
            "delta_provenance": {
                "firing_delta": "one reviewed firing observation",
                "selection_rule": "consumer policy local-example.v1",
            },
            "precision_input_basis": "NOT_APPLICABLE",
            "policy_reference": "example:policy:rule-stats-update.v1",
        },
        next_id=next_id,
    )

    return {
        "overall_status": "RULE_STATS_UPDATE_PROVENANCE_EXAMPLE_COMPLETE",
        "cases": {
            "value_changed": value_changed,
            "no_value_change": no_value_change,
            "rejected_unknown_pair": rejected_unknown_pair,
        },
        "non_authority_locks": list(_NON_AUTHORITY_LOCKS),
        "snapshot_boundary": _snapshot_boundary(),
        "historical_boundary": _historical_boundary(),
    }


if __name__ == "__main__":
    import json

    report = run_rule_stats_update_provenance_example()
    print(json.dumps(report, default=str, indent=2))
