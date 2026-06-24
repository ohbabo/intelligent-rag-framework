"""PR43-C / 168차 — Engine Method Call Playbook usage invariants.

Scope (locked, user 2026-05-22)
-------------------------------
These tests do NOT verify modifier formulas, threshold calibration,
new lifecycle semantics, or any new Engine behavior.

These tests verify ONLY that the call-order playbook in
docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md uses the frozen
Engine public method surface and reaches the query / snapshot
points without changing Engine source.

Two paths covered:
  - Rule-associated path
      register_rule + add_claim(rule_id, rule_version, ...)
  - Direct claim path
      add_claim(rule_id=0, rule_version=0, ...)  (PR41 pattern,
      i.e. consumer-owned advisory tag without a registered rule)

Guards covered:
  - Engine has no `fire_rule` public method
  - compute_effective_confidence stays in [0.0, 1.0] for both paths
  - to_snapshot / from_snapshot round-trip preserves
    compute_effective_confidence for both paths
  - Gap layer does not create Contradiction state
  - Contradiction layer does not create Gap state
  - Retrieval score (similarity-like float) is NOT identity-piped
    into add_evidence strength in the playbook example

Not in scope
------------
- modifier math
- threshold calibration
- scoring formula
- adapter implementation
- vector DB / graph DB / LLM / SQL / file / API code
- new public symbols
- new lifecycle states
- new Engine behavior
"""

from __future__ import annotations

import pytest

import ragcore
from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    Engine,
    RULE_MATURITY_STABLE,
    RuleDefinition,
    ScoreValue,
)


# ============================================================================
# Test-local helpers (consumer-side simulation, NOT production code)
# ============================================================================


# Test-local consumer-domain integer registries (no semantic meaning to ragcore)
_ENTITY_TYPE_HOST = 1
_OBSERVATION_TYPE_GENERIC = 100
_SOURCE_TYPE_GENERIC = 200
_CLAIM_TYPE_GENERIC = 300
_EVIDENCE_TYPE_GENERIC = 400
_EVIDENCE_TYPE_OPPOSING = 401
_GAP_TYPE_MISSING_DETAIL = 500
_RELATION_TYPE_GENERIC = 600
_REASON_CODE_DIRECT = 700

# Test-local advisory rule (for Rule-associated path)
_RULE_ID_ADVISORY = 42
_RULE_VERSION_ADVISORY = 1


def _translate_similarity_to_strength(similarity: float) -> float:
    """Test-local non-identity translation.

    Mirrors the PR41 simulation pattern: any external retrieval score
    must be transformed by adapter policy before being used as
    Engine `strength`. This is a discrete-tier mapping, NOT a copy.
    """
    if similarity >= 0.8:
        return 0.9
    if similarity >= 0.5:
        return 0.6
    return 0.3


# ============================================================================
# Rule-associated path
# ============================================================================


class TestRuleAssociatedPath:
    """Path A — register_rule + add_claim(rule_id, rule_version, ...).

    The consumer registers a RuleDefinition and attaches every
    Claim it creates to that rule. Engine does NOT fire the rule
    automatically; the rule_id / rule_version are association tags
    only.
    """

    def test_full_path_completes_through_query_and_snapshot(self) -> None:
        engine = Engine()

        engine.register_rule(
            RuleDefinition(
                id=_RULE_ID_ADVISORY,
                version=_RULE_VERSION_ADVISORY,
                maturity=RULE_MATURITY_STABLE,
                prior_confidence=ScoreValue(0.7),
            )
        )

        entity_id = engine.add_entity(entity_type=_ENTITY_TYPE_HOST)
        engine.add_observation(
            entity_id=entity_id,
            raw_ref_id=1001,
            observation_type=_OBSERVATION_TYPE_GENERIC,
            source_type=_SOURCE_TYPE_GENERIC,
        )

        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=_CLAIM_TYPE_GENERIC,
            rule_id=_RULE_ID_ADVISORY,
            rule_version=_RULE_VERSION_ADVISORY,
            reason_code=_REASON_CODE_DIRECT,
            base_confidence=0.6,
            status=CLAIM_STATUS_CANDIDATE,
        )

        external_similarity = 0.85
        translated_strength = _translate_similarity_to_strength(external_similarity)
        evidence_id = engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=1002,
            evidence_type=_EVIDENCE_TYPE_GENERIC,
            strength=translated_strength,
        )

        engine.update_rule_stats(
            _RULE_ID_ADVISORY,
            _RULE_VERSION_ADVISORY,
            firing_delta=1,
            true_delta=1,
        )

        engine.confirm_claim_if_ready(claim_id)

        effective = engine.compute_effective_confidence(claim_id)
        assert 0.0 <= effective.value <= 1.0

        snapshot = engine.to_snapshot()
        restored = Engine.from_snapshot(snapshot)
        restored_effective = restored.compute_effective_confidence(claim_id)
        assert restored_effective.value == effective.value

        assert evidence_id > 0
        assert engine.get_rule(_RULE_ID_ADVISORY, _RULE_VERSION_ADVISORY) is not None


# ============================================================================
# Direct claim path
# ============================================================================


class TestDirectClaimPath:
    """Path B — add_claim(rule_id=0, rule_version=0, ...).

    The consumer does NOT register a rule. rule_id / rule_version
    are used as advisory tag values only (PR41 simulation pattern).
    The full lifecycle including Gap and Contradiction is exercised.
    """

    def _build_claim(self, engine: Engine) -> tuple[int, int]:
        entity_id = engine.add_entity(entity_type=_ENTITY_TYPE_HOST)
        engine.add_observation(
            entity_id=entity_id,
            raw_ref_id=2001,
            observation_type=_OBSERVATION_TYPE_GENERIC,
            source_type=_SOURCE_TYPE_GENERIC,
        )
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=_CLAIM_TYPE_GENERIC,
            rule_id=0,
            rule_version=0,
            reason_code=_REASON_CODE_DIRECT,
            base_confidence=0.5,
            status=CLAIM_STATUS_CANDIDATE,
        )
        return entity_id, claim_id

    def test_full_path_with_gap_resolution_completes(self) -> None:
        engine = Engine()
        _, claim_id = self._build_claim(engine)

        gap_id = engine.add_gap(
            claim_id=claim_id,
            gap_type=_GAP_TYPE_MISSING_DETAIL,
            required_evidence_type=_EVIDENCE_TYPE_GENERIC,
            severity=0.4,
            rule_id=0,
        )
        assert engine.gap_resolution(gap_id) is None

        external_similarity = 0.9
        evidence_id = engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=2002,
            evidence_type=_EVIDENCE_TYPE_GENERIC,
            strength=_translate_similarity_to_strength(external_similarity),
        )
        resolved = engine.resolve_gaps_for_evidence(evidence_id)
        assert gap_id in resolved

        engine.confirm_claim_if_ready(claim_id)
        effective = engine.compute_effective_confidence(claim_id)
        assert 0.0 <= effective.value <= 1.0

    def test_full_path_with_contradiction_completes(self) -> None:
        engine = Engine()
        _, claim_id = self._build_claim(engine)

        engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=2003,
            evidence_type=_EVIDENCE_TYPE_GENERIC,
            strength=_translate_similarity_to_strength(0.85),
        )
        engine.confirm_claim_if_ready(claim_id)

        opposing_evidence_id = engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=2004,
            evidence_type=_EVIDENCE_TYPE_OPPOSING,
            strength=_translate_similarity_to_strength(0.75),
        )
        engine.register_contradiction(
            claim_id=claim_id, evidence_id=opposing_evidence_id
        )
        engine.dispute_claim_if_ready(claim_id)

        # Whether the lifecycle transition fires depends on
        # modifier / threshold math. The playbook does NOT verify
        # transition occurrence; it verifies the method returns a
        # well-typed tuple without raising.
        history = engine.claim_lifecycle_history(claim_id)
        assert isinstance(history, tuple)

        effective = engine.compute_effective_confidence(claim_id)
        assert 0.0 <= effective.value <= 1.0

    def test_snapshot_roundtrip_preserves_effective_confidence(self) -> None:
        engine = Engine()
        _, claim_id = self._build_claim(engine)
        engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=2005,
            evidence_type=_EVIDENCE_TYPE_GENERIC,
            strength=_translate_similarity_to_strength(0.9),
        )
        engine.confirm_claim_if_ready(claim_id)

        before = engine.compute_effective_confidence(claim_id).value
        snapshot = engine.to_snapshot()
        restored = Engine.from_snapshot(snapshot)
        after = restored.compute_effective_confidence(claim_id).value
        assert after == before


# ============================================================================
# Playbook guards
# ============================================================================


class TestPlaybookGuards:
    """Cross-cutting invariants the playbook depends on."""

    def test_engine_class_has_no_fire_rule_method(self) -> None:
        # The playbook says rule association is a Claim tag, not an
        # Engine firing mechanism. `Engine.fire_rule` MUST NOT exist
        # as an instance method on the Engine class.
        #
        # Note: `ragcore.fire_rule` exists as a module-level rule
        # evaluator (rule logic, NOT Engine state mutation). The
        # playbook does NOT call it; it remains adapter-side concern.
        assert not hasattr(Engine, "fire_rule")
        engine_public = [
            name
            for name in dir(Engine)
            if not name.startswith("_") and callable(getattr(Engine, name))
        ]
        assert "fire_rule" not in engine_public

    def test_engine_public_method_surface_is_40(self) -> None:
        # PR73-M04 shift: 40 → 41 (added state_identity).
        # PR76-M07 shift: 41 → 42 (added
        #   compute_effective_confidence_with_trace).
        public_methods = [
            name
            for name in dir(Engine)
            if not name.startswith("_") and callable(getattr(Engine, name))
        ]
        assert len(public_methods) == 42

    def test_ragcore_all_remains_48_symbols(self) -> None:
        # PR73-M04 shift: 48 → 49 (added EngineStateIdentity).
        # PR76-M07 shift: 49 → 50 (added EffectiveConfidenceTrace).
        assert len(ragcore.__all__) == 50
        assert len(set(ragcore.__all__)) == 50

    def test_translation_function_is_not_identity(self) -> None:
        # Mirrors PR41 §50.9 / §50.10 invariant in the playbook context.
        # The playbook example must NEVER pipe a retrieval similarity
        # directly into Engine `strength`.
        for similarity in (0.85, 0.75, 0.55, 0.45, 0.20):
            assert _translate_similarity_to_strength(similarity) != similarity

    def test_gap_layer_does_not_create_contradictions(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=_ENTITY_TYPE_HOST)
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=_CLAIM_TYPE_GENERIC,
            rule_id=0,
            rule_version=0,
            reason_code=_REASON_CODE_DIRECT,
        )
        engine.add_gap(
            claim_id=claim_id,
            gap_type=_GAP_TYPE_MISSING_DETAIL,
            required_evidence_type=_EVIDENCE_TYPE_GENERIC,
            severity=0.5,
            rule_id=0,
        )
        assert engine.active_contradictions_for_claim(claim_id) == ()
        assert engine.contradictions_for_claim(claim_id) == ()

    def test_contradiction_layer_does_not_create_gaps(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=_ENTITY_TYPE_HOST)
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=_CLAIM_TYPE_GENERIC,
            rule_id=0,
            rule_version=0,
            reason_code=_REASON_CODE_DIRECT,
        )
        evidence_id = engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=3001,
            evidence_type=_EVIDENCE_TYPE_OPPOSING,
            strength=_translate_similarity_to_strength(0.8),
        )
        engine.register_contradiction(claim_id=claim_id, evidence_id=evidence_id)
        assert engine.gaps_for_claim(claim_id) == []

    def test_compute_effective_confidence_in_bounds_after_each_path(self) -> None:
        # Combined path: rule-associated then a contradiction.
        # The bounds must hold across BOTH path styles.
        engine = Engine()
        engine.register_rule(
            RuleDefinition(
                id=_RULE_ID_ADVISORY,
                version=_RULE_VERSION_ADVISORY,
                maturity=RULE_MATURITY_STABLE,
                prior_confidence=ScoreValue(0.6),
            )
        )

        entity_id = engine.add_entity(entity_type=_ENTITY_TYPE_HOST)
        rule_claim = engine.add_claim(
            subject_id=entity_id,
            claim_type=_CLAIM_TYPE_GENERIC,
            rule_id=_RULE_ID_ADVISORY,
            rule_version=_RULE_VERSION_ADVISORY,
            reason_code=_REASON_CODE_DIRECT,
        )
        engine.add_evidence(
            claim_id=rule_claim,
            raw_ref_id=4001,
            evidence_type=_EVIDENCE_TYPE_GENERIC,
            strength=_translate_similarity_to_strength(0.9),
        )
        engine.confirm_claim_if_ready(rule_claim)
        assert 0.0 <= engine.compute_effective_confidence(rule_claim).value <= 1.0

        direct_claim = engine.add_claim(
            subject_id=entity_id,
            claim_type=_CLAIM_TYPE_GENERIC,
            rule_id=0,
            rule_version=0,
            reason_code=_REASON_CODE_DIRECT,
        )
        engine.add_evidence(
            claim_id=direct_claim,
            raw_ref_id=4002,
            evidence_type=_EVIDENCE_TYPE_GENERIC,
            strength=_translate_similarity_to_strength(0.6),
        )
        engine.confirm_claim_if_ready(direct_claim)
        assert 0.0 <= engine.compute_effective_confidence(direct_claim).value <= 1.0

    def test_playbook_uses_only_existing_engine_public_methods(self) -> None:
        # Every method name the playbook references must exist on Engine.
        # If a future PR renames any of these, this test fails and the
        # guide / two-path examples must be updated in lockstep.
        required = [
            "add_entity",
            "add_observation",
            "add_relation",
            "add_evidence",
            "add_claim",
            "add_gap",
            "resolve_gaps_for_evidence",
            "gap_resolution",
            "gaps_for_claim",
            "get_gap",
            "register_contradiction",
            "register_contradiction_resolution",
            "contradictions_for_claim",
            "active_contradictions_for_claim",
            "active_contradictions_by_freshness",
            "resolved_contradictions_for_claim",
            "confirm_claim_if_ready",
            "dispute_claim_if_ready",
            "refute_claim_if_ready",
            "refute_disputed_claim_if_ready",
            "refute_disputed_claim_if_ready_by_freshness",
            "resolve_disputed_claim_if_ready",
            "compute_effective_confidence",
            "to_snapshot",
            "from_snapshot",
            "register_rule",
            "get_rule",
            "get_rule_stats",
            "update_rule_stats",
            "register_hint_evidence_types",
            "unregister_hint_evidence_types",
            "clear_hint_evidence_types",
            "claim_lifecycle_history",
            "evidence_freshness",
            "evidences_for_claim",
            "get_claim",
            "get_entity",
            "get_evidence",
            "get_observation",
            "get_relation",
        ]
        for name in required:
            assert hasattr(Engine, name), f"Engine missing public method: {name}"
