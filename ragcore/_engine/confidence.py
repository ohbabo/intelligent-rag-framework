"""ragcore._engine.confidence — fixed v1 effective-confidence kernel + status domain.

Phase 2 of the Engine v1 refactoring plan. This module owns the FIXED v1
effective-confidence policy: the seven modifier/composition arithmetic
functions, their policy constants, the policy id, and the claim-status
admission domain (status modifier table → valid statuses → admission).

It imports ragcore.types + stdlib only and never imports ragcore.engine or
ragcore._engine.serialization (no import cycle). The functions here are PURE:
they take already-collected primitive inputs, read no Engine state, mutate
nothing, advance no revision, and touch no snapshot. Engine's six
``_*_modifier_for_claim`` wrappers collect the facts from its stores and call
these functions; Engine owns the EffectiveConfidenceTrace assembly and lineage.

NON-GOALS (forbidden): runtime modifier registry, dynamic modifier order,
adding/removing/duplicating modifiers, policy-id change, numeric change, new
normalization/clamp/rounding, probability/verdict semantics. The policy is
fixed; v2 must use a separate policy with a separate id.
"""

from __future__ import annotations

from ragcore.types import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
)


# ============================================================================
# Status domain (PR11-D §24.8 + PR65-P01 §51)
# ============================================================================

# Status-only effective-confidence multipliers. Private — not exported.
_STATUS_MODIFIER_CANDIDATE = 1.0
_STATUS_MODIFIER_CONFIRMED = 1.0
_STATUS_MODIFIER_DISPUTED = 0.5
_STATUS_MODIFIER_REFUTED = 0.0

_STATUS_TO_MODIFIER: dict[int, float] = {
    CLAIM_STATUS_CANDIDATE: _STATUS_MODIFIER_CANDIDATE,
    CLAIM_STATUS_CONFIRMED: _STATUS_MODIFIER_CONFIRMED,
    CLAIM_STATUS_DISPUTED: _STATUS_MODIFIER_DISPUTED,
    CLAIM_STATUS_REFUTED: _STATUS_MODIFIER_REFUTED,
}

# Effective-confidence calculation policy id (PR76-M07 §7). Module-private —
# observable only via EffectiveConfidenceTrace.calculation_policy_id. FIXED for
# v1; bump under §7.4 conditions only (a v2 policy uses a different id).
_EFFECTIVE_CONFIDENCE_POLICY_ID = "ragcore.effective-confidence.v1"

# Claim status admission domain (PR65-P01 §51): only the four registered
# status constants are admissible. Derived from the status modifier table so
# the status domain stays single-sourced here with admission.
_VALID_CLAIM_STATUSES: frozenset[int] = frozenset(_STATUS_TO_MODIFIER)


def _validate_claim_status_admission(value: object) -> None:
    """§51.2/§51.5 — fail-fast Claim.status admission check.

    Raises:
        TypeError: ``value`` is not a built-in int (includes bool, which
            is an int subclass but rejected for Claim.status).
        ValueError: ``value`` is an int but not one of the four
            admissible status constants.
    """
    # bool is an int subclass; reject explicitly per §51.2.
    if isinstance(value, bool) or type(value) is not int:
        raise TypeError(
            "Claim.status must be a built-in int and one of "
            "CLAIM_STATUS_CANDIDATE / CLAIM_STATUS_CONFIRMED / "
            "CLAIM_STATUS_REFUTED / CLAIM_STATUS_DISPUTED, "
            f"not {type(value).__name__}"
        )
    if value not in _VALID_CLAIM_STATUSES:
        raise ValueError(
            f"Claim.status {value} is not admissible; "
            f"admissible values: {sorted(_VALID_CLAIM_STATUSES)}"
        )


# ============================================================================
# Modifier policy constants (private; the kernel functions own them)
# ============================================================================

# freshness (PR11-C §26)
_FRESHNESS_PENALTY_WEIGHT = 0.5

# gap count-tier (PR12-D §28 + PR23-M §35)
_GAP_TIER_ZERO_UNRESOLVED_MODIFIER = 1.0
_GAP_TIER_ONE_UNRESOLVED_MODIFIER = 0.9
_GAP_TIER_TWO_UNRESOLVED_MODIFIER = 0.8
_GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER = 0.7

# count strength averaging (PR19-E §31 + PR24-N §36)
_COUNT_STRENGTH_PENALTY_WEIGHT = 0.25

# rule stats maturity × precision (PR20-F §32 + PR26-R §38 + PR29-R §41)
_RULE_STATS_MATURITY_PENALTY_WEIGHT = 0.2
_RULE_STATS_MATURITY_SATURATION_COUNT = 2
_RULE_STATS_PRECISION_BASE = 0.9
_RULE_STATS_PRECISION_RANGE = 0.1

# evidence-type caller-registered hint (PR21-L §33)
_EVIDENCE_TYPE_PENALTY_MODIFIER = 0.9


# ============================================================================
# Pure modifier kernel — each takes already-collected primitives
# ============================================================================

def status_modifier(status: int) -> float:
    """PR11-D §24.8 — status-only multiplier (0.0 / 0.5 / 1.0)."""
    return _STATUS_TO_MODIFIER[status]


def freshness_modifier(most_recent_active_strength: float | None) -> float:
    """PR11-C §26 — most-recent active contradiction strength weight.

    ``None`` (no active contradiction) → 1.0; otherwise
    ``1.0 - strength × _FRESHNESS_PENALTY_WEIGHT``.
    """
    if most_recent_active_strength is None:
        return 1.0
    return 1.0 - most_recent_active_strength * _FRESHNESS_PENALTY_WEIGHT


def gap_modifier(unresolved_gap_count: int) -> float:
    """PR12-D §28 + PR23-M §35 — count-tier weak attenuation (never 0.0)."""
    if unresolved_gap_count == 0:
        return _GAP_TIER_ZERO_UNRESOLVED_MODIFIER
    if unresolved_gap_count == 1:
        return _GAP_TIER_ONE_UNRESOLVED_MODIFIER
    if unresolved_gap_count == 2:
        return _GAP_TIER_TWO_UNRESOLVED_MODIFIER
    return _GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER


def count_modifier(active_contradiction_strengths: tuple[float, ...]) -> float:
    """PR19-E §31 + PR24-N §36 — repeated-pressure strength averaging.

    Fewer than two active contradictions → 1.0; otherwise
    ``1.0 - average_strength × _COUNT_STRENGTH_PENALTY_WEIGHT``.
    """
    if len(active_contradiction_strengths) < 2:
        return 1.0
    average_strength = (
        sum(active_contradiction_strengths)
        / len(active_contradiction_strengths)
    )
    return 1.0 - average_strength * _COUNT_STRENGTH_PENALTY_WEIGHT


def rule_stats_modifier(
    firing_count: int | None,
    observed_precision: float | None,
) -> float:
    """PR20-F §32 + PR26-R §38 + PR29-R §41 — continuous maturity × bounded precision.

    ``firing_count is None`` means no applicable rule stats (sentinel rule id 0
    or a lookup miss) → 1.0 (the caller resolves that store-lookup condition).
    Otherwise: maturity from the clamped firing count, precision from the
    observed precision (``None`` → 1.0), composed as ``maturity × precision``.
    """
    if firing_count is None:
        return 1.0
    clamped_count = min(
        max(firing_count, 0),
        _RULE_STATS_MATURITY_SATURATION_COUNT,
    )
    maturity_ratio = clamped_count / _RULE_STATS_MATURITY_SATURATION_COUNT
    maturity_modifier = 1.0 - (
        (1.0 - maturity_ratio) * _RULE_STATS_MATURITY_PENALTY_WEIGHT
    )
    if observed_precision is None:
        precision_modifier = 1.0
    else:
        precision_modifier = (
            _RULE_STATS_PRECISION_BASE
            + observed_precision * _RULE_STATS_PRECISION_RANGE
        )
    return maturity_modifier * precision_modifier


def evidence_type_modifier(
    direct_evidence_types: tuple[int, ...],
    hint_evidence_types: frozenset[int] | set[int],
) -> float:
    """PR21-L §33 — caller-registered source-quality signal (NOT truth verdict).

    Empty hint set → 1.0 (vacuous-truth trap avoided); no direct supporting
    evidence → 1.0; all direct evidence types in the hint set →
    ``_EVIDENCE_TYPE_PENALTY_MODIFIER``; otherwise 1.0. ``direct_evidence_types``
    must already EXCLUDE contradiction / resolved-contradiction evidence.
    """
    if not hint_evidence_types:
        return 1.0
    if not direct_evidence_types:
        return 1.0
    if all(t in hint_evidence_types for t in direct_evidence_types):
        return _EVIDENCE_TYPE_PENALTY_MODIFIER
    return 1.0


def compose_effective_confidence(
    base_confidence: float,
    status_mod: float,
    freshness_mod: float,
    gap_mod: float,
    count_mod: float,
    rule_stats_mod: float,
    evidence_type_mod: float,
) -> float:
    """The SINGLE v1 composition site — fixed seven-factor product, fixed order.

    effective = base × status × freshness × gap × count × rule_stats × evidence_type
    """
    return (
        base_confidence
        * status_mod
        * freshness_mod
        * gap_mod
        * count_mod
        * rule_stats_mod
        * evidence_type_mod
    )
