"""Tests for PR27-P — External integration usage boundary.

PR27-P §39:
    External integration is a call-boundary contract, not a new engine feature.

Core proposition:
    External consumers such as a product adapter, CLI wrapper, web backend,
    report generator, or Cerberus-side integration layer may use Engine through
    public APIs only.

This test file does not request a new Engine feature.

It locks the fact that the existing public API surface is already sufficient for:

    - caller-owned normalization -> Engine registration
    - lifecycle / contradiction API calls
    - effective confidence query
    - snapshot handoff
    - caller-owned Evidence.type taxonomy
    - no Engine-owned file IO
    - no Cerberus-specific public adapter

Expected result:
    All tests pass immediately.
"""

from __future__ import annotations

import inspect
import json

import ragcore
from ragcore import (
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    Engine,
    RULE_MATURITY_EXPERIMENTAL,
    RuleDefinition,
    ScoreValue,
)


def _register_rule(
    engine: Engine,
    *,
    rule_id: int = 100,
    rule_version: int = 1,
) -> None:
    engine.register_rule(
        RuleDefinition(
            id=rule_id,
            version=rule_version,
            maturity=RULE_MATURITY_EXPERIMENTAL,
            prior_confidence=ScoreValue(0.6),
        )
    )


def _claim(
    engine: Engine,
    *,
    base_confidence: float = 1.0,
    rule_id: int = 0,
    rule_version: int = 0,
    status: int | None = None,
) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)

    kwargs: dict[str, int] = {}
    if status is not None:
        kwargs["status"] = status

    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=rule_id,
        rule_version=rule_version,
        reason_code=0,
        base_confidence=base_confidence,
        **kwargs,
    )
    return entity_id, claim_id


def _evidence(
    engine: Engine,
    claim_id: int,
    *,
    evidence_type: int = 10,
    strength: float = 0.5,
) -> int:
    return engine.add_evidence(
        claim_id=claim_id,
        raw_ref_id=0,
        evidence_type=evidence_type,
        strength=strength,
    )


def _gap(
    engine: Engine,
    claim_id: int,
    *,
    required_evidence_type: int = 10,
    rule_id: int = 100,
) -> int:
    return engine.add_gap(
        claim_id=claim_id,
        gap_type=1,
        required_evidence_type=required_evidence_type,
        severity=0.5,
        rule_id=rule_id,
    )


class TestExternalConsumerRecommendedCallOrder:
    """§39.3 — public API call order is enough for external integration."""

    def test_consumer_can_register_query_and_snapshot_using_public_api(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        engine.register_hint_evidence_types([900])

        _, claim_id = _claim(
            engine,
            base_confidence=1.0,
            rule_id=100,
            rule_version=1,
        )
        _gap(engine, claim_id, required_evidence_type=900, rule_id=100)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=900,
            strength=0.7,
        )

        assert engine.resolve_gaps_for_evidence(evidence_id) == (1,)

        engine.update_rule_stats(100, 1, firing_delta=2)

        score = engine.compute_effective_confidence(claim_id)
        snapshot = engine.to_snapshot()

        # rule_stats saturated = 1.0, gap resolved = 1.0,
        # status/freshness/count = 1.0, all direct evidence is caller-registered hint = 0.9.
        assert score.value == 0.9
        assert snapshot["schema_version"] == 2
        assert snapshot["hint_evidence_types"] == [900]

    def test_consumer_can_apply_lifecycle_transition_before_querying_score(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0, status=CLAIM_STATUS_CONFIRMED)
        evidence_id = _evidence(engine, claim_id, evidence_type=30, strength=0.6)

        assert engine.register_contradiction(claim_id, evidence_id) is True
        assert engine.dispute_claim_if_ready(claim_id) is True

        score = engine.compute_effective_confidence(claim_id)
        history = engine.claim_lifecycle_history(claim_id)

        # disputed status modifier = 0.5
        # freshness modifier = 1.0 - 0.6 * 0.5 = 0.7
        assert score.value == 0.35
        assert len(history) == 1
        assert history[0].from_status == CLAIM_STATUS_CONFIRMED
        assert history[0].to_status == CLAIM_STATUS_DISPUTED
        assert history[0].transition == "dispute_if_ready"


class TestExternalConsumerSnapshotBoundary:
    """§39.4 — snapshot handoff is state preservation, not re-judgment."""

    def test_from_snapshot_preserves_query_outputs(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, rule_version=1)
        engine.register_hint_evidence_types([900])

        _, claim_id = _claim(
            engine,
            base_confidence=1.0,
            rule_id=100,
            rule_version=1,
        )
        _gap(engine, claim_id, required_evidence_type=900, rule_id=100)
        evidence_id = _evidence(
            engine,
            claim_id,
            evidence_type=900,
            strength=0.5,
        )
        engine.resolve_gaps_for_evidence(evidence_id)
        engine.update_rule_stats(100, 1, firing_delta=2)

        before = engine.compute_effective_confidence(claim_id).value
        restored = Engine.from_snapshot(engine.to_snapshot())
        after = restored.compute_effective_confidence(claim_id).value

        assert after == before
        assert restored.to_snapshot() == engine.to_snapshot()

    def test_snapshot_is_json_compatible_dict_not_file_io_contract(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine)
        _evidence(engine, claim_id, evidence_type=1, strength=0.5)

        snapshot = engine.to_snapshot()

        assert isinstance(snapshot, dict)
        assert json.loads(json.dumps(snapshot)) == snapshot

    def test_snapshot_api_accepts_state_not_file_path(self) -> None:
        to_snapshot_sig = inspect.signature(Engine.to_snapshot)
        from_snapshot_sig = inspect.signature(Engine.from_snapshot)

        assert list(to_snapshot_sig.parameters) == ["self"]
        assert list(from_snapshot_sig.parameters) == ["snapshot"]


class TestExternalConsumerHintEvidenceTypeBoundary:
    """§39.6 — Evidence.type taxonomy is caller-owned."""

    def test_hint_type_register_unregister_clear_updates_score_boundary(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=77, strength=0.5)

        assert engine.compute_effective_confidence(claim_id).value == 1.0

        engine.register_hint_evidence_types([77])
        assert engine.compute_effective_confidence(claim_id).value == 0.9

        engine.unregister_hint_evidence_types([77])
        assert engine.compute_effective_confidence(claim_id).value == 1.0

        engine.register_hint_evidence_types([77])
        engine.clear_hint_evidence_types()
        assert engine.compute_effective_confidence(claim_id).value == 1.0

    def test_caller_can_use_domain_taxonomy_without_framework_owning_meaning(self) -> None:
        caller_taxonomy = {
            "banner_hint": 7001,
            "cpe_mapper_hint": 7002,
            "api_enrichment_hint": 7003,
        }

        engine = Engine()
        engine.register_hint_evidence_types(caller_taxonomy.values())

        _, claim_id = _claim(engine, base_confidence=1.0)
        _evidence(
            engine,
            claim_id,
            evidence_type=caller_taxonomy["banner_hint"],
            strength=0.5,
        )

        assert engine.compute_effective_confidence(claim_id).value == 0.9
        assert engine.to_snapshot()["hint_evidence_types"] == [7001, 7002, 7003]


class TestExternalConsumerQueryBoundaries:
    """§39.5 / §39.7 — queries are read-side integration outputs."""

    def test_compute_effective_confidence_does_not_mutate_snapshot_state(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0)
        _evidence(engine, claim_id, evidence_type=1, strength=0.5)

        before = engine.to_snapshot()
        first = engine.compute_effective_confidence(claim_id)
        second = engine.compute_effective_confidence(claim_id)
        after = engine.to_snapshot()

        assert first == second
        assert after == before

    def test_lifecycle_history_survives_snapshot_round_trip(self) -> None:
        engine = Engine()
        _, claim_id = _claim(engine, base_confidence=1.0, status=CLAIM_STATUS_CONFIRMED)
        evidence_id = _evidence(engine, claim_id, evidence_type=30, strength=0.4)

        engine.register_contradiction(claim_id, evidence_id)
        engine.dispute_claim_if_ready(claim_id)

        restored = Engine.from_snapshot(engine.to_snapshot())

        assert restored.claim_lifecycle_history(claim_id) == engine.claim_lifecycle_history(
            claim_id
        )
        assert restored.get_claim(claim_id).status == CLAIM_STATUS_DISPUTED


class TestNoCerberusSpecificPublicAdapter:
    """§39.8 — PR27-P does not add a Cerberus-specific public adapter."""

    def test_public_namespace_has_no_cerberus_specific_adapter(self) -> None:
        exported = {name.lower() for name in ragcore.__all__}

        assert "cerberus" not in exported
        assert "cerberusclient" not in exported
        assert "cerberus_client" not in exported
        assert not hasattr(ragcore, "CerberusClient")
        assert not hasattr(ragcore, "cerberus_client")

    def test_public_namespace_does_not_export_hint_taxonomy_enum(self) -> None:
        exported = {name.lower() for name in ragcore.__all__}

        assert "hint" not in exported
        assert "hint_evidence_type" not in exported
        assert "hintevidencetype" not in exported
