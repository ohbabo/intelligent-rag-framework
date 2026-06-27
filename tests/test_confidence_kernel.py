"""Phase 2 — focused tests for the pure effective-confidence kernel.

These lock the FIXED v1 numeric policy at the kernel level
(ragcore._engine.confidence), independent of Engine state projection. The
Engine-level characterization tests (state projection + public behavior) live
elsewhere; these test the pure arithmetic and the status admission domain.

Forbidden by the fixed policy and NOT tested as configurable: runtime modifier
registry, dynamic order, added/removed modifiers, policy-id change.
"""

from __future__ import annotations

import pytest

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
)
from ragcore._engine import confidence as c


class TestStatusModifier:
    @pytest.mark.parametrize(("status", "expected"), [
        (CLAIM_STATUS_CANDIDATE, 1.0),
        (CLAIM_STATUS_CONFIRMED, 1.0),
        (CLAIM_STATUS_DISPUTED, 0.5),
        (CLAIM_STATUS_REFUTED, 0.0),
    ])
    def test_four_statuses(self, status, expected):
        assert c.status_modifier(status) == expected


class TestFreshnessModifier:
    def test_none_is_neutral(self):
        assert c.freshness_modifier(None) == 1.0

    @pytest.mark.parametrize(("strength", "expected"), [
        (0.0, 1.0),       # 1 - 0 * 0.5
        (1.0, 0.5),       # 1 - 1 * 0.5
        (0.6, 0.7),       # 1 - 0.6 * 0.5
    ])
    def test_strength(self, strength, expected):
        assert c.freshness_modifier(strength) == pytest.approx(expected)


class TestGapModifier:
    @pytest.mark.parametrize(("count", "expected"), [
        (0, 1.0), (1, 0.9), (2, 0.8), (3, 0.7), (4, 0.7),
    ])
    def test_tiers(self, count, expected):
        assert c.gap_modifier(count) == expected


class TestCountModifier:
    def test_fewer_than_two_is_neutral(self):
        assert c.count_modifier(()) == 1.0
        assert c.count_modifier((0.9,)) == 1.0

    @pytest.mark.parametrize(("strengths", "expected"), [
        ((0.0, 0.0), 1.0),        # avg 0 -> 1 - 0*0.25
        ((0.8, 0.8), 0.8),        # avg 0.8 -> 1 - 0.8*0.25 (PR19-E center)
        ((0.4, 0.4), 0.9),        # avg 0.4 -> 1 - 0.4*0.25
        ((1.0, 1.0), 0.75),       # avg 1.0 -> 1 - 1.0*0.25
        ((0.0, 1.0), 0.875),      # avg 0.5 -> 1 - 0.5*0.25
    ])
    def test_two_or_more_average(self, strengths, expected):
        assert c.count_modifier(strengths) == pytest.approx(expected)


class TestRuleStatsModifier:
    def test_no_applicable_stats_is_neutral(self):
        # firing_count None covers sentinel rule id 0 and lookup miss.
        assert c.rule_stats_modifier(None, None) == 1.0
        assert c.rule_stats_modifier(None, 0.5) == 1.0

    @pytest.mark.parametrize(("firing", "expected"), [
        (0, 0.8), (1, 0.9), (2, 1.0), (5, 1.0),   # maturity, precision None
    ])
    def test_maturity_precision_none(self, firing, expected):
        assert c.rule_stats_modifier(firing, None) == pytest.approx(expected)

    @pytest.mark.parametrize(("firing", "precision", "expected"), [
        (0, 0.0, 0.72),     # 0.8 * 0.9
        (1, 0.5, 0.855),    # 0.9 * 0.95
        (2, 1.0, 1.0),      # 1.0 * 1.0
        (2, 0.0, 0.9),      # 1.0 * 0.9
    ])
    def test_maturity_times_precision(self, firing, precision, expected):
        assert c.rule_stats_modifier(firing, precision) == pytest.approx(expected)


class TestEvidenceTypeModifier:
    def test_empty_hint_set_is_neutral(self):
        assert c.evidence_type_modifier((1, 2), frozenset()) == 1.0

    def test_no_direct_evidence_is_neutral(self):
        assert c.evidence_type_modifier((), frozenset({1})) == 1.0

    def test_all_hint_penalised(self):
        assert c.evidence_type_modifier((1, 1), frozenset({1, 2})) == 0.9

    def test_mixed_is_neutral(self):
        assert c.evidence_type_modifier((1, 3), frozenset({1, 2})) == 1.0


class TestCompose:
    def test_exact_product_order(self):
        # base × status × freshness × gap × count × rule_stats × evidence_type
        assert c.compose_effective_confidence(
            0.5, 1.0, 0.9, 0.8, 1.0, 1.0, 0.9
        ) == pytest.approx(0.5 * 1.0 * 0.9 * 0.8 * 1.0 * 1.0 * 0.9)

    def test_refuted_zero_dominates(self):
        assert c.compose_effective_confidence(
            0.9, 0.0, 0.9, 0.9, 0.9, 0.9, 0.9
        ) == 0.0


class TestPolicyIdAndAdmission:
    def test_policy_id_exact_string(self):
        assert c._EFFECTIVE_CONFIDENCE_POLICY_ID == "ragcore.effective-confidence.v1"

    @pytest.mark.parametrize("status", [
        CLAIM_STATUS_CANDIDATE, CLAIM_STATUS_CONFIRMED,
        CLAIM_STATUS_DISPUTED, CLAIM_STATUS_REFUTED,
    ])
    def test_admission_admits_four(self, status):
        c._validate_claim_status_admission(status)  # no raise

    @pytest.mark.parametrize("bad", [True, False, 1.0, "1", None])
    def test_admission_wrong_type_is_type_error(self, bad):
        with pytest.raises(TypeError):
            c._validate_claim_status_admission(bad)

    @pytest.mark.parametrize("bad", [-1, 4, 99])
    def test_admission_out_of_range_is_value_error(self, bad):
        with pytest.raises(ValueError):
            c._validate_claim_status_admission(bad)


class TestKernelPurity:
    def test_inputs_not_mutated(self):
        strengths = (0.8, 0.9)
        hints = frozenset({1, 2})
        types = (1, 2)
        c.count_modifier(strengths)
        c.evidence_type_modifier(types, hints)
        assert strengths == (0.8, 0.9)
        assert hints == frozenset({1, 2})
        assert types == (1, 2)
