"""Proposal Safety Validator MVP — PR56.

Scope limitation (locked, user 2026-05-25)
------------------------------------------
PR56 validates proposal safety interpretation.
It does not judge claims.
It does not execute tools.
It does not mutate Engine state.

Coverage
--------
PR56 detects 3 categories that PR55 deferred:

  - nested P1 / P3 / P4 / P5 / P6 / P7
    (PR55 catches the same vocabularies at TOP LEVEL only;
     PR56 catches them at any nested depth ≥ 1)

  - P2: probability-like identifier at any path
    (PR54 §10 P2 — probability translation of effective_confidence)

  - P8: domain vocabulary identifier at any path
    (PR54 §10 P8 — domain vocabulary intrusion;
     mirrors PR44-D §5.6 and PR45-E §3 forbidden vocabulary)

Out of PR56 scope
-----------------
  - new proposal categories (PR55 / PR54 §5 list is canonical)
  - free-text semantic analysis on value strings
    (this validator is structural-only; it does NOT inspect
     phrasing inside note / supporting_packet_ref values)
  - tool planning
  - report wording guard
  - Engine call plan
  - adapter translation policy

Composition with PR55
---------------------
A safe proposal satisfies BOTH:

  PR55 validate_llm_proposal_shape(...)            returns []
  PR56 validate_proposal_safety(...)               returns []

Consumer is expected to call both validators. PR56 does not
replace PR55; they cover disjoint regions:

  PR55 — top-level shape and top-level P1/P3/P4/P5/P6/P7
  PR56 — nested P1/P3/P4/P5/P6/P7 + P2 (any path) + P8 (any path)

Invariants honored
------------------
  - ragcore-free at runtime (no import ragcore / from ragcore)
  - NEVER raises
  - NEVER mutates proposal or source_packet
  - structural key/path scan only
  - free-text value content is not inspected
"""

from __future__ import annotations

from typing import Any, Iterator


# ============================================================================
# Nested P1 ~ P7 vocabularies (mirror of PR55 top-level vocabularies;
# self-contained in this module to avoid examples/* internal imports).
# ============================================================================


_P1_VERDICT_KEYS = frozenset(
    {"verdict", "label", "judgment", "decision", "ruling"}
)

_P3_STATUS_MUTATION_KEYS = frozenset(
    {
        "status_change",
        "set_status",
        "change_status",
        "claim_status_change",
        "force_status",
    }
)

_P4_TOOL_EXECUTION_KEYS = frozenset(
    {
        "tool_run",
        "tool_command",
        "execute_tool",
        "execute_command",
        "run_command",
        "run_tool",
        "tool_invocation",
    }
)
_P4_TOOL_EXECUTION_PREFIXES = ("execute_",)

_P5_ENGINE_MUTATION_KEYS = frozenset(
    {
        "engine_call",
        "engine_mutation",
        "engine_call_args",
        "mutation_payload",
        "add_evidence_args",
        "add_claim_args",
        "add_gap_args",
        "add_observation_args",
        "add_relation_args",
        "engine_write",
        "engine_writeback",
    }
)

_P6_FINAL_REPORT_KEYS = frozenset(
    {
        "final_report",
        "published",
        "final_verdict",
        "final_published",
        "publication_status",
        "report_finalized",
    }
)

_P7_THRESHOLD_VERDICT_KEYS = frozenset(
    {
        "binary_verdict",
        "threshold_verdict",
        "auto_verdict",
        "threshold_decision",
    }
)


# ============================================================================
# P2 (probability translation) — exact + prefix.
# ============================================================================


_P2_EXACT_KEYS = frozenset(
    {
        "probability",
        "prob",
        "p_true",
        "truth_probability",
        "confidence_probability",
    }
)
_P2_PREFIXES = (
    "probability_of_",
    "prob_of_",
    "p_true_",
)


# ============================================================================
# P8 (domain vocabulary intrusion) — word-boundary identifier component
# match (snake_case / kebab-case / dot-separated). Substring matching is
# intentionally NOT used to avoid false-positives on legitimate compound
# identifiers (e.g., "hostname" must NOT trigger on "host", "port_number"
# must NOT silently bypass — the latter still triggers because "port" is
# a component).
#
# Forbidden list mirrors PR44-D §5.6 / PR45-E §3.
# ============================================================================


_P8_FORBIDDEN_VOCAB = frozenset(
    {
        "cerberus",
        "vulnerability",
        "scanner",
        "exploit",
        "ssh",
        "cve",
        "nmap",
        "host",
        "port",
        "service",
        "asset",
    }
)


# ============================================================================
# Structural walker — yields (path, depth, key, value) for every nested
# dict entry. Walks dicts, lists, and tuples. Does NOT walk into
# Engine-owned dataclasses (Claim / Evidence / Gap / ScoreValue) —
# those are not consumer-side proposal content.
# ============================================================================


def _walk_with_path(
    obj: Any,
    path: str = "",
    depth: int = 0,
) -> Iterator[tuple[str, int, str, Any]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str):
                current_path = f"{path}.{key}" if path else key
                yield current_path, depth, key, value
                yield from _walk_with_path(value, current_path, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for idx, item in enumerate(obj):
            indexed_path = f"{path}[{idx}]"
            yield from _walk_with_path(item, indexed_path, depth + 1)


# ============================================================================
# Identifier component splitter — word-boundary match for P8.
# ============================================================================


def _identifier_components(key: str) -> set[str]:
    """Split a key into snake/kebab/dot-separated components.

    "cve_id"          -> {"cve", "id"}
    "scan-host-port"  -> {"scan", "host", "port"}
    "metadata.host"   -> {"metadata", "host"}
    "hostname"        -> {"hostname"}     (NOT split — exact whole)
    "host"            -> {"host"}
    """
    normalized = key.lower().replace("-", "_").replace(".", "_")
    return {comp for comp in normalized.split("_") if comp}


# ============================================================================
# Per-key detection.
# ============================================================================


def _detect_nested_p1_p7(key_lower: str) -> str | None:
    """Return the P_id for a nested key, or None if no match.

    Order: P1 -> P3 -> P4 (exact) -> P4 (prefix) -> P5 -> P6 -> P7.
    """
    if key_lower in _P1_VERDICT_KEYS:
        return "P1"
    if key_lower in _P3_STATUS_MUTATION_KEYS:
        return "P3"
    if key_lower in _P4_TOOL_EXECUTION_KEYS:
        return "P4"
    for prefix in _P4_TOOL_EXECUTION_PREFIXES:
        if key_lower.startswith(prefix):
            return "P4"
    if key_lower in _P5_ENGINE_MUTATION_KEYS:
        return "P5"
    if key_lower in _P6_FINAL_REPORT_KEYS:
        return "P6"
    if key_lower in _P7_THRESHOLD_VERDICT_KEYS:
        return "P7"
    return None


def _is_p2_probability_identifier(key_lower: str) -> bool:
    if key_lower in _P2_EXACT_KEYS:
        return True
    for prefix in _P2_PREFIXES:
        if key_lower.startswith(prefix):
            return True
    return False


def _p8_intrusion_components(key: str) -> set[str]:
    """Return the set of P8-forbidden components found in this key."""
    return _identifier_components(key) & _P8_FORBIDDEN_VOCAB


# ============================================================================
# Public validator entry point.
# ============================================================================


def validate_proposal_safety(
    proposal: dict[str, Any],
    source_packet: dict[str, Any],
) -> list[tuple[str, str]]:
    """Detect unsafe nested / semantic identifiers in an LLM proposal.

    Returns [] when no safety violation is found.
    Returns a list of (code, message) tuples otherwise.
    NEVER raises; NEVER mutates inputs.

    source_packet is accepted for signature consistency with the PR55
    validator. PR56 itself does not consult source_packet — the
    detection is purely identifier-level. The argument is kept so
    that consumers can pass the same packet to both validators in a
    composed call.

    Codes
    -----
    P1   nested verdict / label / judgment / decision / ruling key
    P2   probability-like identifier at any path
    P3   nested status_change / set_status / change_status / etc.
    P4   nested tool execution key (or "execute_" prefix)
    P5   nested engine mutation payload key
    P6   nested final report / published key
    P7   nested threshold-based binary verdict key
    P8   domain vocabulary identifier at any path
         (component-level word-boundary match)

    PR55 vs PR56 overlap
    --------------------
    PR55 catches P1/P3/P4/P5/P6/P7 ONLY at top level.
    PR56 catches the same vocabularies ONLY at depth >= 1
    (i.e., inside a nested dict / list / tuple).

    PR55 does NOT catch P2 or P8 at all.
    PR56 catches P2 and P8 at any depth, including top level.

    A safe proposal satisfies both:
      validate_llm_proposal_shape(proposal, source_packet) == []
      validate_proposal_safety(proposal, source_packet) == []
    """
    # If proposal is not a dict, leave it for PR55's S1 to flag.
    if not isinstance(proposal, dict):
        return []

    violations: list[tuple[str, str]] = []

    for path, depth, key, _value in _walk_with_path(proposal):
        key_lower = key.lower()

        # Nested P1 ~ P7 (depth >= 1 only).
        if depth >= 1:
            nested_pid = _detect_nested_p1_p7(key_lower)
            if nested_pid is not None:
                msg_label = {
                    "P1": "nested verdict-like key",
                    "P3": "nested status mutation key",
                    "P4": "nested tool execution key",
                    "P5": "nested engine mutation payload key",
                    "P6": "nested final report key",
                    "P7": "nested threshold-based binary verdict key",
                }[nested_pid]
                violations.append(
                    (
                        nested_pid,
                        f"{msg_label} at path {path} (PR56 nested-{nested_pid})",
                    )
                )

        # P2 — any depth, including top level.
        if _is_p2_probability_identifier(key_lower):
            violations.append(
                (
                    "P2",
                    f"probability-like identifier at path {path} "
                    f"(PR56 P2 / PR54 §10 P2 / PR52 §5 F1/F2 / "
                    f"PR44-D AP-CF-1)",
                )
            )

        # P8 — any depth, word-boundary component match.
        intrusion = _p8_intrusion_components(key)
        if intrusion:
            violations.append(
                (
                    "P8",
                    f"domain vocabulary identifier at path {path} "
                    f"(components: {sorted(intrusion)}; "
                    f"PR56 P8 / PR54 §10 P8 / PR44-D AP-X-6 / "
                    f"PR45-E §3)",
                )
            )

    return violations
