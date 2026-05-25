"""Minimal LLM Proposal Schema MVP — PR55.

Scope limitation (locked, user 2026-05-25)
------------------------------------------
PR55 is a consumer-side shape validator for LLM proposal drafts.

It detects whether an LLM proposal draft conforms to the minimal
allowed shape and whether it contains any forbidden keys named
in PR54 §10 (P1 / P3 / P4 / P5 / P6 / P7).

It is NOT:
  - an executable plan builder
  - a normalizer ("normalize_llm_proposal" is OUT OF PR55 SCOPE)
  - a judgment validator
  - a tool execution authorizer
  - a final report writer

It honors PR54 §12 5 must-hold entry conditions:
  1. no ragcore source modification
  2. no ragcore public symbol addition
  3. no proposal → Engine judgment auto-mutation
  4. no proposal → tool execution authorization
  5. human / operator decision boundary preserved

And honors PR47 §3 / PR49 §5 / PR52 §5 / PR52 §8 /
PR53 false-positive prevention philosophy.

Minimal allowed proposal shape
------------------------------
required:
  category               : str    (one of the 5 allowed categories)
  target_claim_id        : int    (must match source_packet claim.id)
  note                   : str

optional:
  target_evidence_id     : int
  target_gap_id          : int
  supporting_packet_ref  : str

Allowed categories (PR54 §5):
  uncertainty_note
  evidence_gap_question
  next_inspection_question
  packet_summary_note
  report_note_candidate

Forbidden key detection (PR54 §10, structural only):
  P1   verdict / label / judgment / decision / ruling
  P3   status_change / set_status / change_status / claim_status_change /
       force_status
  P4   tool_run / tool_command / execute_tool / execute_command /
       run_command / run_tool / tool_invocation
       (also: keys starting with "execute_")
  P5   engine_call / engine_mutation / engine_call_args /
       mutation_payload / add_evidence_args / add_claim_args /
       add_gap_args / add_observation_args / add_relation_args /
       engine_write / engine_writeback
  P6   final_report / published / final_verdict / final_published /
       publication_status / report_finalized
  P7   binary_verdict / threshold_verdict / auto_verdict /
       threshold_decision

OUT OF PR55 SCOPE (deferred to PR56 Proposal Safety Validator):
  P2   probability translation of effective_confidence
       (semantic / text inference; not pure key naming)
  P8   domain vocabulary on ragcore-side identifiers
       (semantic; overlaps with PR53 packet validator scope)
"""

from __future__ import annotations

from typing import Any


# ============================================================================
# Allowed shape constants.
# ============================================================================


_REQUIRED_FIELDS = frozenset({"category", "target_claim_id", "note"})

_OPTIONAL_FIELDS = frozenset(
    {"target_evidence_id", "target_gap_id", "supporting_packet_ref"}
)

_ALLOWED_TOP_LEVEL_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS

_ALLOWED_CATEGORIES = frozenset(
    {
        "uncertainty_note",
        "evidence_gap_question",
        "next_inspection_question",
        "packet_summary_note",
        "report_note_candidate",
    }
)


# ============================================================================
# Forbidden key vocabularies (PR54 §10, structural).
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

# Narrow prefix policy: only "execute_" matches as prefix to avoid
# false-positives on legitimate names (e.g., "run_id" would falsely
# trigger if "run_" were a prefix). "run_*" forms are caught only via
# the explicit set above ("run_command", "run_tool").
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
# Classification helper.
# ============================================================================


def _classify_unknown_key(key: str) -> str | None:
    """Return the forbidden P_id a key matches, or None if the key
    is unknown for an unrelated reason.

    Classification order: P1 → P3 → P4 (exact) → P4 (prefix) →
    P5 → P6 → P7.
    """
    kl = key.lower()
    if kl in _P1_VERDICT_KEYS:
        return "P1"
    if kl in _P3_STATUS_MUTATION_KEYS:
        return "P3"
    if kl in _P4_TOOL_EXECUTION_KEYS:
        return "P4"
    for prefix in _P4_TOOL_EXECUTION_PREFIXES:
        if kl.startswith(prefix):
            return "P4"
    if kl in _P5_ENGINE_MUTATION_KEYS:
        return "P5"
    if kl in _P6_FINAL_REPORT_KEYS:
        return "P6"
    if kl in _P7_THRESHOLD_VERDICT_KEYS:
        return "P7"
    return None


# ============================================================================
# Public validator entry point.
# ============================================================================


def validate_llm_proposal_shape(
    proposal: dict[str, Any],
    source_packet: dict[str, Any],
) -> list[tuple[str, str]]:
    """Detect shape violations and forbidden keys in an LLM proposal.

    Returns an empty list when the proposal conforms to the minimal
    allowed shape and contains no forbidden keys.
    Returns a list of (code, message) tuples otherwise.
    The function NEVER raises and NEVER mutates proposal or
    source_packet.

    Codes
    -----
    Shape errors:
      S1   proposal is not a dict
      S2   missing required field(s)
      S3   category is not one of the allowed 5
      S4   target_claim_id is not an int
      S5   target_claim_id does not match source_packet claim.id
           (only checked if source_packet has a claim with an id;
            otherwise skipped — packet-level cross-check is
            optional in this MVP)
      S6   note is not a str
      S7   unknown top-level key(s) other than the allowed shape

    Forbidden key detect (PR54 §10):
      P1   verdict / label / judgment / decision / ruling
      P3   status_change / set_status / change_status / etc.
      P4   tool_run / execute_command / etc.
      P5   engine_call / mutation_payload / add_*_args / etc.
      P6   final_report / published / etc.
      P7   binary_verdict / threshold_verdict / etc.
    """
    violations: list[tuple[str, str]] = []

    # S1 — proposal must be a dict; if not, cannot continue.
    if not isinstance(proposal, dict):
        violations.append(("S1", "proposal must be a dict"))
        return violations

    # S2 — required fields present.
    proposal_keys = set(proposal.keys())
    missing = _REQUIRED_FIELDS - proposal_keys
    if missing:
        violations.append(
            ("S2", f"missing required field(s): {sorted(missing)}")
        )

    # S3 — category is one of the allowed 5.
    category = proposal.get("category")
    if category is not None:
        if not isinstance(category, str) or category not in _ALLOWED_CATEGORIES:
            violations.append(
                (
                    "S3",
                    f"category must be one of "
                    f"{sorted(_ALLOWED_CATEGORIES)}; got {category!r}",
                )
            )

    # S4 — target_claim_id is int (and not bool, which Python treats
    # as a subclass of int).
    target_claim_id = proposal.get("target_claim_id")
    if target_claim_id is not None:
        if not isinstance(target_claim_id, int) or isinstance(
            target_claim_id, bool
        ):
            violations.append(
                ("S4", "target_claim_id must be int (not bool)")
            )
        else:
            # S5 — cross-check with source_packet claim.id, if available.
            packet_claim = (
                source_packet.get("claim")
                if isinstance(source_packet, dict)
                else None
            )
            packet_claim_id = (
                getattr(packet_claim, "id", None)
                if packet_claim is not None
                else None
            )
            if packet_claim_id is not None and packet_claim_id != target_claim_id:
                violations.append(
                    (
                        "S5",
                        f"target_claim_id ({target_claim_id}) does not "
                        f"match source_packet claim.id "
                        f"({packet_claim_id})",
                    )
                )

    # S6 — note must be str.
    note = proposal.get("note")
    if note is not None and not isinstance(note, str):
        violations.append(("S6", "note must be str"))

    # S7 + P1~P7 — classify top-level unknown keys.
    unknown_keys = proposal_keys - _ALLOWED_TOP_LEVEL_FIELDS

    by_pid: dict[str, list[str]] = {
        "P1": [],
        "P3": [],
        "P4": [],
        "P5": [],
        "P6": [],
        "P7": [],
    }
    other_unknown: list[str] = []

    for key in unknown_keys:
        if not isinstance(key, str):
            other_unknown.append(repr(key))
            continue
        pid = _classify_unknown_key(key)
        if pid is None:
            other_unknown.append(key)
        else:
            by_pid[pid].append(key)

    if by_pid["P1"]:
        violations.append(
            (
                "P1",
                f"verdict/label/judgment/decision/ruling key not "
                f"allowed: {sorted(by_pid['P1'])} "
                f"(PR54 §10 P1 / PR44-D AP-CF-1 / PR52 §5 F10)",
            )
        )
    if by_pid["P3"]:
        violations.append(
            (
                "P3",
                f"status_change / set_status / claim status mutation "
                f"key not allowed: {sorted(by_pid['P3'])} "
                f"(PR54 §10 P3 / PR43-C §4.6 / PR44-D AP-L-1)",
            )
        )
    if by_pid["P4"]:
        violations.append(
            (
                "P4",
                f"tool execution key not allowed: "
                f"{sorted(by_pid['P4'])} "
                f"(PR54 §10 P4 — no proposal may authorize tool "
                f"execution)",
            )
        )
    if by_pid["P5"]:
        violations.append(
            (
                "P5",
                f"engine mutation payload key not allowed: "
                f"{sorted(by_pid['P5'])} "
                f"(PR54 §10 P5 / PR52 §5 F13 / PR44-D AP-E-1)",
            )
        )
    if by_pid["P6"]:
        violations.append(
            (
                "P6",
                f"final report / published key not allowed: "
                f"{sorted(by_pid['P6'])} "
                f"(PR54 §10 P6 / PR54 §11 — human / operator decision "
                f"is the gating event)",
            )
        )
    if by_pid["P7"]:
        violations.append(
            (
                "P7",
                f"threshold-based binary verdict key not allowed: "
                f"{sorted(by_pid['P7'])} "
                f"(PR54 §10 P7 / PR52 §5 F12 / PR44-D AP-CF-2)",
            )
        )

    if other_unknown:
        violations.append(
            (
                "S7",
                f"unknown top-level key(s) not allowed under PR55 "
                f"minimal shape: {sorted(other_unknown)}",
            )
        )

    return violations
