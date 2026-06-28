"""C9 effective-confidence ADAPTER mixin.

Behaviour-preserving extraction from ragcore.engine.Engine (Phase 3B-5 of the
Engine v1 refactoring; ADR docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md).
The ten method bodies are moved verbatim (AST-identical). This is the ADAPTER
layer: it COLLECTS input facts from the Engine stores and delegates the numeric
composition to the pure arithmetic kernel ragcore/_engine/confidence.py (which is
NOT modified). It is read-only (zero mutators) but NOT coupling-free: it reads the
Engine-owned stores (_claims / _evidences / _claim_gap_refs / _gap_resolutions /
_rule_stats / _contradictions / _resolved_contradictions / _hint_evidence_types),
uses the C1 seams (self._assert_claim_exists / self._assert_evidence_exists /
self.state_identity) and the C5 contradiction queries
(self.active_contradictions_for_claim / self.active_contradictions_by_freshness)
through ``self`` (runtime MRO resolution; no C5 import). The M07 contract holds:
inspect.getsource(Engine._compute_effective_confidence_core) returns this real
body (one ScoreValue around one composer delegation; no second formula). This
mixin contributes methods only — no __init__, no state, no Engine back-reference.
"""

from __future__ import annotations

from ragcore._engine import confidence
from ragcore.types import EffectiveConfidenceTrace, ScoreValue


class ConfidenceAdaptersMixin:
    """C9 cluster: evidence freshness + the six effective-confidence modifier
    adapters + the calculation core + the two public confidence APIs. Adapter
    layer over the pure ragcore._engine.confidence kernel; reads Engine stores
    and the C1/C5 seams through ``self`` (Engine MRO)."""

    def evidence_freshness(self, evidence_id: int) -> int:
        """Return the freshness signal of the evidence.

        PR11-A §25.3 — freshness = evidence.id (PR1 _next_id 기반 등록 순서).
        더 큰 값일수록 더 최근 등록.

        Returns:
            evidence.id (= evidence_id 자체).

        Raises:
            KeyError: unknown evidence_id.

        Note:
            wall-clock 안 봄 (PR10-A / PR10-B 정신 일관). engine-local 의미만
            가짐 (cross-engine 비교 무의미).
        """
        self._assert_evidence_exists(evidence_id)
        return evidence_id

    def _status_modifier_for_claim(self, claim_id: int) -> float:
        """PR11-D §24.8 — status-only multiplier. Engine wrapper: read the
        claim status, delegate to the pure confidence kernel."""
        return confidence.status_modifier(self._claims[claim_id].status)

    def _freshness_modifier_for_claim(self, claim_id: int) -> float:
        """PR11-C §26 — most-recent active contradiction strength weight.
        Engine wrapper: collect the most-recent active strength (None if none),
        delegate to the pure kernel."""
        active = self.active_contradictions_by_freshness(claim_id)
        most_recent_strength = (
            None if not active
            else self._evidences[active[0]].strength.value
        )
        return confidence.freshness_modifier(most_recent_strength)

    def _gap_modifier_for_claim(self, claim_id: int) -> float:
        """PR12-D §28 + PR23-M §35 — count-tier weak attenuation. Engine
        wrapper: count unresolved gaps, delegate to the pure kernel."""
        unresolved_gap_count = sum(
            1
            for gap_id in self._claim_gap_refs.get(claim_id, ())
            if gap_id not in self._gap_resolutions
        )
        return confidence.gap_modifier(unresolved_gap_count)

    def _count_modifier_for_claim(self, claim_id: int) -> float:
        """PR19-E §31 + PR24-N §36 — repeated-pressure strength averaging. Engine
        wrapper: collect active contradiction strengths, delegate to the pure
        kernel. (An empty-strength contradiction is not repeated pressure.)"""
        active = self.active_contradictions_for_claim(claim_id)
        strengths = tuple(
            self._evidences[evidence_id].strength.value
            for evidence_id in active
        )
        return confidence.count_modifier(strengths)

    def _rule_stats_modifier_for_claim(self, claim_id: int) -> float:
        """PR20-F §32 + PR26-R §38 + PR29-R §41 — continuous maturity × bounded
        precision. Engine wrapper: resolve the applicable rule stats (sentinel
        rule id 0 or a lookup miss → no applicable stats → ``firing_count``
        None), then delegate the arithmetic to the pure confidence kernel.
        false_positive_rate is ignored (PR29-R OOS)."""
        claim = self._claims[claim_id]
        if claim.created_by_rule == 0:
            firing_count = None
            observed_precision = None
        else:
            stats = self._rule_stats.get(
                (claim.created_by_rule, claim.created_by_rule_version)
            )
            if stats is None:
                firing_count = None
                observed_precision = None
            else:
                firing_count = stats.firing_count
                observed_precision = (
                    None if stats.observed_precision is None
                    else stats.observed_precision.value
                )
        return confidence.rule_stats_modifier(firing_count, observed_precision)

    def _evidence_type_modifier_for_claim(self, claim_id: int) -> float:
        """PR21-L §33 — weak source-quality signal (NOT truth verdict). Engine
        wrapper: collect the types of DIRECT supporting evidence (Evidence.claim_id
        == claim_id, excluding contradiction / resolved-contradiction evidence),
        then delegate to the pure kernel with the caller-registered hint set."""
        contradicting = self._contradictions.get(claim_id, set())
        resolved = self._resolved_contradictions.get(claim_id, set())
        excluded = contradicting | resolved
        direct_evidence_types = tuple(
            ev.type
            for ev in self._evidences.values()
            if ev.claim_id == claim_id and ev.id not in excluded
        )
        return confidence.evidence_type_modifier(
            direct_evidence_types, self._hint_evidence_types
        )

    def compute_effective_confidence(self, claim_id: int) -> ScoreValue:
        """Effective confidence as base × status × freshness × gap × count × rule_stats × evidence_type.

        Composition (PR11-D §24 + PR11-C §26 + PR12-D §28 + PR19-E §31 + PR20-F §32 + PR21-L §33):
            effective = base
                      × status_modifier(claim.status)         # PR11-D
                      × freshness_modifier(claim_id)           # PR11-C
                      × gap_modifier(claim_id)                 # PR12-D
                      × count_modifier(claim_id)               # PR19-E
                      × rule_stats_modifier(claim)             # PR20-F
                      × evidence_type_modifier(claim_id)       # PR21-L

        status_modifier (PR11-D §24.3, unchanged):
            candidate / confirmed → 1.0
            disputed → 0.5
            refuted → 0.0

        freshness_modifier (PR11-C §26.3, Sub-decision O — 최신 1개만):
            active = active_contradictions_by_freshness(claim_id)
            if not active: → 1.0
            else: → 1.0 - most_recent.strength.value × _FRESHNESS_PENALTY_WEIGHT

        gap_modifier (PR12-D §28.3 + PR23-M §35.5, Sub-decision AP — count-tier):
            unresolved_count = #{gap in _claim_gap_refs[claim_id] : not in _gap_resolutions}
            0   → _GAP_TIER_ZERO_UNRESOLVED_MODIFIER (1.0)
            1   → _GAP_TIER_ONE_UNRESOLVED_MODIFIER (0.9)
            2   → _GAP_TIER_TWO_UNRESOLVED_MODIFIER (0.8)
            3+  → _GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER (0.7)

        count_modifier (PR19-E §31.3 + PR24-N §36, Sub-decision AV~BB — strength averaging):
            active = active_contradictions_for_claim(claim_id)
            if len(active) < 2: → 1.0 (PR11-C freshness 영역)
            else:
                avg_strength = average(_evidences[ev].strength.value for ev in active)
                → 1.0 - avg_strength × _COUNT_STRENGTH_PENALTY_WEIGHT (0.25)
            # avg 0.0 → 1.0 / avg 0.4 → 0.9 / avg 0.8 → 0.8 (PR19-E 중심점) / avg 1.0 → 0.75
            # 핵심: 빈 강도의 contradiction 은 repeated pressure 가 아니다.

        rule_stats_modifier (PR20-F §32 + PR26-R §38 + PR29-R §41, Sub-decision BK~BQ + A~J):
            if claim.created_by_rule == 0: → 1.0
            elif (rule_id, rule_version) miss: → 1.0
            else:
                # maturity (PR26-R)
                clamped = min(max(firing_count, 0), 2)
                maturity_ratio = clamped / 2
                maturity_modifier = 1.0 - (1.0 - maturity_ratio) × 0.2
                # precision (PR29-R)
                if observed_precision is None:
                    precision_modifier = 1.0
                else:
                    precision_modifier = 0.9 + observed_precision.value × 0.1
                → maturity_modifier × precision_modifier
            # PR26-R maturity: firing 0 → 0.8 / 1 → 0.9 / 2+ → 1.0
            # PR29-R precision: None → 1.0 / p=0.0 → 0.9 / p=0.5 → 0.95 / p=1.0 → 1.0
            # 핵심 (§41.1): Observed precision is a bounded adjustment signal,
            #               not a rule quality verdict.
            # range: [0.72, 1.0] (maturity floor 0.8 × precision floor 0.9)

        evidence_type_modifier (PR21-L §33.13, Sub-decision AA~AE — caller-registered):
            if not self._hint_evidence_types: → 1.0
            direct = [ev for ev in self._evidences if ev.claim_id == claim_id
                      and ev.id not in (_contradictions | _resolved_contradictions)]
            if not direct: → 1.0
            elif all ev.type in self._hint_evidence_types for ev in direct:
                → _EVIDENCE_TYPE_PENALTY_MODIFIER (0.9)
            else: → 1.0

        의미 분리:
            PR11-C: most recent active contradiction strength (1 개 시 단독)
            PR19-E: active contradiction count pressure (2 개 이상 시 추가)
            PR20-F: rule maturity (rule-global 신호)
            PR21-L: direct supporting evidence source-quality (claim-local, caller-registered)

        Returns:
            ScoreValue (effective ≤ base, no boost — §24.5 N / §32.6 X / §33.7 AD).

        Raises:
            KeyError: unknown claim_id.
        """
        # PR76-M07 §6 — delegate to the single private calculation core
        # so the typed-trace API and the legacy API share one formula.
        return self._compute_effective_confidence_core(claim_id).effective_confidence

    def _compute_effective_confidence_core(
        self, claim_id: int,
    ) -> EffectiveConfidenceTrace:
        """PR76-M07 §6 — single calculation core for both confidence APIs.

        Computes each modifier once into a local variable, multiplies them
        together to produce the effective confidence, and packages the
        components into a frozen EffectiveConfidenceTrace value. Both
        ``compute_effective_confidence`` and
        ``compute_effective_confidence_with_trace`` delegate here so the
        composition formula has exactly one site (§6).

        Raises:
            KeyError: unknown claim_id (same surface as the legacy API).
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        status_modifier = self._status_modifier_for_claim(claim_id)
        freshness_modifier = self._freshness_modifier_for_claim(claim_id)
        gap_modifier = self._gap_modifier_for_claim(claim_id)
        count_modifier = self._count_modifier_for_claim(claim_id)
        rule_stats_modifier = self._rule_stats_modifier_for_claim(claim_id)
        evidence_type_modifier = self._evidence_type_modifier_for_claim(claim_id)
        effective_confidence = ScoreValue(
            confidence.compose_effective_confidence(
                claim.base_confidence.value,
                status_modifier,
                freshness_modifier,
                gap_modifier,
                count_modifier,
                rule_stats_modifier,
                evidence_type_modifier,
            )
        )
        return EffectiveConfidenceTrace(
            claim_id=claim_id,
            source_state_identity=self.state_identity(),
            calculation_policy_id=confidence._EFFECTIVE_CONFIDENCE_POLICY_ID,
            base_confidence=claim.base_confidence,
            status_modifier=status_modifier,
            freshness_modifier=freshness_modifier,
            gap_modifier=gap_modifier,
            count_modifier=count_modifier,
            rule_stats_modifier=rule_stats_modifier,
            evidence_type_modifier=evidence_type_modifier,
            effective_confidence=effective_confidence,
        )

    def compute_effective_confidence_with_trace(
        self, claim_id: int,
    ) -> EffectiveConfidenceTrace:
        """PR76-M07 §5 — return a typed breakdown of the same calculation.

        Returns the EffectiveConfidenceTrace value produced by the single
        private calculation core. By construction:

            self.compute_effective_confidence_with_trace(claim_id)
                .effective_confidence
              == self.compute_effective_confidence(claim_id)

        Read-only: does not advance the M04 revision (§5.1 / §11.1) and
        does not mutate snapshot-visible state.

        Raises:
            KeyError: unknown claim_id (same surface as
                ``compute_effective_confidence``).
        """
        return self._compute_effective_confidence_core(claim_id)
