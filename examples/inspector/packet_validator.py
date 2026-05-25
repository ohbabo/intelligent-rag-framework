"""Consumer Packet Validator — PR53 MVP.

PR53 detects structurally unsafe interpretations of the PR51
packet according to PR52 forbidden readings.

Scope limitation (locked, user 2026-05-25)
------------------------------------------
PR53 is not a judgment validator.
PR53 is a consumer-side guard that detects structurally unsafe
interpretations of the PR51 packet according to PR52 forbidden
readings.

The validator blocks unsafe packet interpretations.
It does not judge the claim.

Detects 6 of PR52 §5's 13 forbidden readings (structural only):
  F3   evidence.strength exposed as probability
  F5   contradictions non-empty → auto refutation
  F7   unresolved_gaps → refutation
  F10  Claim.status renamed to verdict / label / judgment
  F12  threshold → auto true / verified
  F13  raw_ref_id resolved as engine mutation payload (intent only)

Does NOT detect (out of PR53 scope):
  F1, F2, F4, F6, F8, F9, F11
    — LLM phrasing / multi-step inference territory.

Does NOT inspect:
  - the LLM response text
  - human reviewer judgement
  - actual Engine mutation calls
    (F13 is narrowed: only the *structural intent* in
     consumer_output is detected; no monitoring of
     Engine.add_evidence / Engine.add_claim is performed.)

Inputs
------
consumer_output: dict
  The derived/augmented dict the consumer built from the
  source packet (e.g., the LLM-facing payload, the report layer
  input, etc.). Shape is consumer's own; this validator walks
  nested dict / list / tuple structures.

source_packet: dict
  The original 7-key packet produced by
  examples/inspector/engine_inspector.py
  (PR51 build_engine_context_packet).

Return
------
list[tuple[str, str]]
  Empty list ⇒ no structural violation detected.
  Non-empty list ⇒ each entry is (F_id, message).
  Caller decides what to do; no exception is raised.
"""

from __future__ import annotations

from typing import Any, Iterator

from ragcore import CLAIM_STATUS_REFUTED


# ============================================================================
# Detection vocabularies (lowercase; matched after .lower()).
# ============================================================================


# F3 — probability-named keys that suggest evidence strength is being
#      surfaced as a probability.
_PROBABILITY_KEY_EXACT = frozenset(
    {
        "probability",
        "prob",
        "p_true",
    }
)
_PROBABILITY_KEY_PREFIXES = (
    "probability_of_",
    "prob_of_",
    "p_true_",
)

# F10 — verdict / label keys that suggest Claim.status was relabeled
#       into a consumer verdict.
_VERDICT_KEYS = frozenset(
    {
        "verdict",
        "label",
        "judgment",
        "decision",
        "ruling",
    }
)

# F12 — auto-verified boolean keys.
_AUTO_VERIFIED_KEYS = frozenset(
    {
        "verified",
        "is_true",
        "auto_true",
        "is_confirmed",
        "auto_confirmed",
    }
)

# F5 / F7 — "auto refutation" outcome value vocabulary.
_AUTO_REFUTATION_VALUES = frozenset(
    {
        "refuted",
        "false",
        "rejected",
        "denied",
        "invalid",
    }
)

# F13 — engine mutation intent keys (structural only; no actual
#       Engine.add_evidence / Engine.add_claim monitoring).
_MUTATION_INTENT_KEYS = frozenset(
    {
        "engine_mutation",
        "engine_call_args",
        "mutation_payload",
        "add_evidence_args",
        "add_claim_args",
        "add_gap_args",
        "add_observation_args",
        "engine_write",
        "engine_writeback",
    }
)


# ============================================================================
# Structural walker.
# ============================================================================


def _walk_keys_and_values(obj: Any) -> Iterator[tuple[str, Any]]:
    """Yield (key, value) pairs from every nested dict in obj.

    Recurses into dicts and into list/tuple of dicts. Does not
    walk into other object types (Claim / Evidence / Gap /
    ScoreValue / etc. — these are Engine-owned dataclasses and
    are NOT consumer_output's derived shape).
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key, value
            yield from _walk_keys_and_values(value)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _walk_keys_and_values(item)


def _all_keys(obj: Any) -> Iterator[str]:
    """Yield every key encountered in nested dicts of obj
    (lowercased str). Non-string keys are skipped.
    """
    for key, _value in _walk_keys_and_values(obj):
        if isinstance(key, str):
            yield key.lower()


def _all_string_values(obj: Any) -> Iterator[str]:
    """Yield every string value encountered in nested dicts of obj
    (lowercased). Non-string values are skipped.
    """
    for _key, value in _walk_keys_and_values(obj):
        if isinstance(value, str):
            yield value.lower()


# ============================================================================
# Individual forbidden-reading detectors.
# ============================================================================


def _detect_f3_probability_label_for_strength(
    consumer_output: dict[str, Any],
) -> bool:
    """F3 — any nested key in consumer_output is named like a
    probability ('probability', 'prob', 'p_true', or
    'probability_of_*' / 'prob_of_*' / 'p_true_*' prefix).
    """
    for key in _all_keys(consumer_output):
        if key in _PROBABILITY_KEY_EXACT:
            return True
        for prefix in _PROBABILITY_KEY_PREFIXES:
            if key.startswith(prefix):
                return True
    return False


def _claim_status_is_already_refuted(source_packet: dict[str, Any]) -> bool:
    """Helper: source_packet's claim has status == REFUTED.

    When the Engine has already transitioned the claim to REFUTED
    via an explicit refute_*_if_ready call, a consumer-side
    "refuted"/"false"/"rejected" label is simply re-stating the
    Engine result, not an unsafe auto-inference. F5 / F7 only flag
    when the Engine has NOT made that judgment.
    """
    claim = source_packet.get("claim")
    if claim is None:
        return False
    status = getattr(claim, "status", None)
    return status == CLAIM_STATUS_REFUTED


def _consumer_output_carries_refutation_value(
    consumer_output: dict[str, Any],
) -> bool:
    """Helper: consumer_output contains any string value that
    looks like a refutation outcome ('refuted' / 'false' /
    'rejected' / 'denied' / 'invalid').
    """
    for value in _all_string_values(consumer_output):
        if value in _AUTO_REFUTATION_VALUES:
            return True
    return False


def _detect_f5_contradictions_auto_refutation(
    consumer_output: dict[str, Any],
    source_packet: dict[str, Any],
) -> bool:
    """F5 — source has non-empty contradictions AND consumer_output
    carries a refutation-outcome value AND Engine has NOT actually
    refuted the claim.
    """
    if _claim_status_is_already_refuted(source_packet):
        return False
    contradictions = source_packet.get("contradictions", ())
    if len(contradictions) == 0:
        return False
    return _consumer_output_carries_refutation_value(consumer_output)


def _detect_f7_unresolved_gaps_refutation(
    consumer_output: dict[str, Any],
    source_packet: dict[str, Any],
) -> bool:
    """F7 — source has non-empty unresolved_gaps AND consumer_output
    carries a refutation-outcome value AND Engine has NOT actually
    refuted the claim.
    """
    if _claim_status_is_already_refuted(source_packet):
        return False
    unresolved_gaps = source_packet.get("unresolved_gaps", ())
    if len(unresolved_gaps) == 0:
        return False
    return _consumer_output_carries_refutation_value(consumer_output)


def _detect_f10_status_verdict_relabel(
    consumer_output: dict[str, Any],
) -> bool:
    """F10 — any nested key in consumer_output is named like a
    verdict/label/judgment/decision/ruling.
    """
    for key in _all_keys(consumer_output):
        if key in _VERDICT_KEYS:
            return True
    return False


def _detect_f12_threshold_auto_verified(
    consumer_output: dict[str, Any],
) -> bool:
    """F12 — any nested key in consumer_output is named like an
    auto-verified boolean ('verified' / 'is_true' / 'auto_true' /
    'is_confirmed' / 'auto_confirmed') AND its value is a boolean.

    The boolean-value check is what distinguishes a forbidden
    auto-decision from, e.g., a free-text "verification_notes"
    string.
    """
    for key, value in _walk_keys_and_values(consumer_output):
        if not isinstance(key, str):
            continue
        if key.lower() in _AUTO_VERIFIED_KEYS and isinstance(value, bool):
            return True
    return False


def _detect_f13_engine_mutation_intent(
    consumer_output: dict[str, Any],
) -> bool:
    """F13 — any nested key in consumer_output is named like an
    Engine-mutation intent (engine_mutation / engine_call_args /
    mutation_payload / add_*_args / engine_write / engine_writeback).

    Narrowed scope (locked): only the structural intent in
    consumer_output is detected. No monitoring of actual
    Engine.add_evidence / Engine.add_claim calls is performed by
    this validator.
    """
    for key in _all_keys(consumer_output):
        if key in _MUTATION_INTENT_KEYS:
            return True
    return False


# ============================================================================
# Public validator entry point.
# ============================================================================


def validate_consumer_packet_interpretation(
    consumer_output: dict[str, Any],
    source_packet: dict[str, Any],
) -> list[tuple[str, str]]:
    """Detect structurally unsafe interpretations of the PR51
    packet.

    Returns an empty list when no structural violation is found.
    Returns a list of (F_id, message) tuples when violations are
    detected. The caller decides what to do — this function does
    NOT raise.

    See module docstring for the in-scope / out-of-scope list
    (PR52 §5 mapping).
    """
    violations: list[tuple[str, str]] = []

    if _detect_f3_probability_label_for_strength(consumer_output):
        violations.append(
            (
                "F3",
                "evidence strength must not be exposed as probability "
                "(PR52 §5 F3 / PR44-D AP-X-1)",
            )
        )

    if _detect_f5_contradictions_auto_refutation(consumer_output, source_packet):
        violations.append(
            (
                "F5",
                "contradictions non-empty must not auto-imply refutation "
                "(PR52 §5 F5 / PR44-D AP-CT-1)",
            )
        )

    if _detect_f7_unresolved_gaps_refutation(consumer_output, source_packet):
        violations.append(
            (
                "F7",
                "unresolved gaps must not be treated as refutation "
                "(PR52 §5 F7 / PR44-D AP-G-1)",
            )
        )

    if _detect_f10_status_verdict_relabel(consumer_output):
        violations.append(
            (
                "F10",
                "claim status must not be relabeled as consumer verdict "
                "(PR52 §5 F10 / PR43-C §4.3)",
            )
        )

    if _detect_f12_threshold_auto_verified(consumer_output):
        violations.append(
            (
                "F12",
                "threshold must not produce an auto-verified boolean "
                "(PR52 §5 F12 / PR44-D AP-CF-2)",
            )
        )

    if _detect_f13_engine_mutation_intent(consumer_output):
        violations.append(
            (
                "F13",
                "raw_ref_id must not be used as engine mutation payload "
                "(PR52 §5 F13 / PR44-D AP-E-1)",
            )
        )

    return violations
