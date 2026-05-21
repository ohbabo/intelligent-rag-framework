"""Tests for PR28-O — Rule version pinning MVP.

PR28-O §40:
    Rule version pinning is integration stability, not rule quality judgment.

Core proposition:
    Rule identity is the pair (rule_id, rule_version), not rule_id alone.

This test file locks the existing public behavior that:

    - RuleDefinition is keyed by (rule_id, rule_version)
    - RuleStats is keyed by (rule_id, rule_version)
    - Claim stores created_by_rule_version at creation time
    - compute_effective_confidence uses the Claim's pinned rule pair
    - snapshot round-trip preserves rule version pinning
    - Engine does not implement latest-version migration policy

Expected result:
    All tests pass immediately unless a hidden rule-version boundary gap exists.
"""

from __future__ import annotations

import pytest

import ragcore
from ragcore import (
    Engine,
    RULE_MATURITY_EXPERIMENTAL,
    RuleDefinition,
    ScoreValue,
)


def _rule(
    rule_id: int,
    version: int,
    *,
    prior_confidence: float = 0.6,
) -> RuleDefinition:
    return RuleDefinition(
        id=rule_id,
        version=version,
        maturity=RULE_MATURITY_EXPERIMENTAL,
        prior_confidence=ScoreValue(prior_confidence),
    )


def _register_rule(
    engine: Engine,
    *,
    rule_id: int = 100,
    version: int = 1,
    prior_confidence: float = 0.6,
) -> None:
    engine.register_rule(
        _rule(
            rule_id,
            version,
            prior_confidence=prior_confidence,
        )
    )


def _claim(
    engine: Engine,
    *,
    rule_id: int = 100,
    rule_version: int = 1,
    base_confidence: float = 1.0,
) -> int:
    entity_id = engine.add_entity(entity_type=1)
    return engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=rule_id,
        rule_version=rule_version,
        reason_code=0,
        base_confidence=base_confidence,
    )


class TestRuleVersionIdentity:
    """§40.3 — rule identity is (rule_id, rule_version)."""

    def test_same_rule_id_different_versions_can_coexist(self) -> None:
        engine = Engine()

        _register_rule(engine, rule_id=100, version=1)
        _register_rule(engine, rule_id=100, version=2)

        assert engine.get_rule(100, 1).id == 100
        assert engine.get_rule(100, 1).version == 1
        assert engine.get_rule(100, 2).id == 100
        assert engine.get_rule(100, 2).version == 2

    def test_duplicate_same_rule_id_and_version_is_rejected(self) -> None:
        engine = Engine()

        _register_rule(engine, rule_id=100, version=1)

        with pytest.raises(ValueError):
            _register_rule(engine, rule_id=100, version=1)

    def test_rule_stats_slots_are_version_specific(self) -> None:
        engine = Engine()

        _register_rule(engine, rule_id=100, version=1)
        _register_rule(engine, rule_id=100, version=2)

        stats_v1 = engine.get_rule_stats(100, 1)
        stats_v2 = engine.get_rule_stats(100, 2)

        assert stats_v1.rule_id == 100
        assert stats_v1.rule_version == 1
        assert stats_v1.firing_count == 0

        assert stats_v2.rule_id == 100
        assert stats_v2.rule_version == 2
        assert stats_v2.firing_count == 0


class TestClaimRuleVersionPinning:
    """§40.4 — Claim pins the creating rule version at creation time."""

    def test_claim_stores_created_by_rule_version_at_creation(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, version=1)

        claim_id = _claim(engine, rule_id=100, rule_version=1)
        claim = engine.get_claim(claim_id)

        assert claim.created_by_rule == 100
        assert claim.created_by_rule_version == 1

    def test_later_newer_rule_version_does_not_rewrite_existing_claim(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, version=1)

        claim_id = _claim(engine, rule_id=100, rule_version=1)

        _register_rule(engine, rule_id=100, version=2)

        claim = engine.get_claim(claim_id)
        assert claim.created_by_rule == 100
        assert claim.created_by_rule_version == 1

    def test_snapshot_round_trip_preserves_claim_pinned_version(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, version=1)
        _register_rule(engine, rule_id=100, version=2)

        claim_id = _claim(engine, rule_id=100, rule_version=1)

        restored = Engine.from_snapshot(engine.to_snapshot())
        restored_claim = restored.get_claim(claim_id)

        assert restored_claim.created_by_rule == 100
        assert restored_claim.created_by_rule_version == 1


class TestRuleStatsVersionIsolation:
    """§40.5 — RuleStats updates are isolated by rule version."""

    def test_update_rule_stats_for_v1_does_not_affect_v2(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, version=1)
        _register_rule(engine, rule_id=100, version=2)

        engine.update_rule_stats(100, 1, firing_delta=1)

        assert engine.get_rule_stats(100, 1).firing_count == 1
        assert engine.get_rule_stats(100, 2).firing_count == 0

    def test_update_rule_stats_for_v2_does_not_affect_v1(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, version=1)
        _register_rule(engine, rule_id=100, version=2)

        engine.update_rule_stats(100, 2, firing_delta=2)

        assert engine.get_rule_stats(100, 1).firing_count == 0
        assert engine.get_rule_stats(100, 2).firing_count == 2

    def test_effective_confidence_uses_claim_pinned_v1_stats_not_latest_v2(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, version=1)
        _register_rule(engine, rule_id=100, version=2)

        claim_id = _claim(
            engine,
            rule_id=100,
            rule_version=1,
            base_confidence=1.0,
        )

        # Saturate v2 only.
        # If Engine incorrectly used "latest version", score would become 1.0.
        # Correct behavior: pinned v1 still has firing_count 0 -> rule_stats modifier 0.8.
        engine.update_rule_stats(100, 2, firing_delta=2)

        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(0.8)

    def test_effective_confidence_uses_claim_pinned_v2_stats_separately(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, version=1)
        _register_rule(engine, rule_id=100, version=2)

        claim_v1 = _claim(
            engine,
            rule_id=100,
            rule_version=1,
            base_confidence=1.0,
        )
        claim_v2 = _claim(
            engine,
            rule_id=100,
            rule_version=2,
            base_confidence=1.0,
        )

        engine.update_rule_stats(100, 1, firing_delta=1)
        engine.update_rule_stats(100, 2, firing_delta=2)

        # PR26-R rule_stats continuous maturity:
        # firing_count 1 -> 0.9
        # firing_count 2+ -> 1.0
        assert engine.compute_effective_confidence(claim_v1).value == pytest.approx(0.9)
        assert engine.compute_effective_confidence(claim_v2).value == pytest.approx(1.0)

    def test_missing_pinned_rule_stats_uses_existing_fallback_not_latest_version(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, version=2)

        claim_id = _claim(
            engine,
            rule_id=100,
            rule_version=1,
            base_confidence=1.0,
        )

        engine.update_rule_stats(100, 2, firing_delta=2)

        # Existing behavior: if the exact pinned pair is missing, rule_stats modifier is 1.0.
        # It must not search for latest registered version 2.
        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(1.0)


class TestSnapshotRuleVersionPinning:
    """§40.6 — snapshot preserves version-specific rule state."""

    def test_snapshot_round_trip_preserves_version_specific_rule_stats(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, version=1)
        _register_rule(engine, rule_id=100, version=2)

        engine.update_rule_stats(100, 1, firing_delta=1)
        engine.update_rule_stats(100, 2, firing_delta=2)

        restored = Engine.from_snapshot(engine.to_snapshot())

        assert restored.get_rule_stats(100, 1).firing_count == 1
        assert restored.get_rule_stats(100, 2).firing_count == 2

    def test_snapshot_round_trip_preserves_version_specific_confidence_outputs(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, version=1)
        _register_rule(engine, rule_id=100, version=2)

        claim_v1 = _claim(engine, rule_id=100, rule_version=1)
        claim_v2 = _claim(engine, rule_id=100, rule_version=2)

        engine.update_rule_stats(100, 1, firing_delta=1)
        engine.update_rule_stats(100, 2, firing_delta=2)

        restored = Engine.from_snapshot(engine.to_snapshot())

        assert restored.compute_effective_confidence(claim_v1).value == pytest.approx(
            engine.compute_effective_confidence(claim_v1).value
        )
        assert restored.compute_effective_confidence(claim_v2).value == pytest.approx(
            engine.compute_effective_confidence(claim_v2).value
        )

    def test_rule_version_pinning_does_not_bump_snapshot_schema(self) -> None:
        engine = Engine()
        _register_rule(engine, rule_id=100, version=1)
        _register_rule(engine, rule_id=100, version=2)

        assert engine.to_snapshot()["schema_version"] == 2


class TestNoRuleMigrationPolicy:
    """§40.7 / §40.10 — Engine does not own rule migration policy."""

    def test_engine_has_no_public_latest_version_lookup_policy(self) -> None:
        engine = Engine()

        assert not hasattr(engine, "latest_rule_version")
        assert not hasattr(engine, "get_latest_rule")
        assert not hasattr(engine, "resolve_latest_rule_version")

    def test_engine_has_no_public_claim_rule_migration_api(self) -> None:
        engine = Engine()

        assert not hasattr(engine, "migrate_claim_to_rule_version")
        assert not hasattr(engine, "upgrade_claim_rule_version")
        assert not hasattr(engine, "reassign_claim_rule")

    def test_public_namespace_has_no_rule_migration_api(self) -> None:
        exported = {name.lower() for name in ragcore.__all__}

        assert "latest_rule_version" not in exported
        assert "migrate_claim_to_rule_version" not in exported
        assert "upgrade_claim_rule_version" not in exported
        assert "reassign_claim_rule" not in exported
