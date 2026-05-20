"""Tests for PR18-K — Snapshot migration MVP (framework only).

Invariants of ``_CURRENT_SNAPSHOT_SCHEMA_VERSION`` + ``_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS``
+ ``_migrate_snapshot_to_current``.

**79차 (test-first) 상태**: migration framework 미구현. constants / function
모두 미존재. dynamic getattr 으로 collection-error 회피. fail pattern mixed:

§30.13 의 14 invariant 매핑:
1.  _CURRENT_SNAPSHOT_SCHEMA_VERSION == 1                  [의도 fail]
2.  _SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS contains 1         [의도 fail]
3.  _migrate_snapshot_to_current callable                  [의도 fail]
4.  v1 snapshot → identity migration                       [의도 fail]
5.  PR17 round-trip identity 보존                          [이미 pass]
6.  missing schema_version → ValueError                    [이미 pass]
7.  unsupported version → ValueError                       [이미 pass]
8.  version=2 → ValueError                                 [이미 pass]
9.  migration 결정성                                       [의도 fail]
10. migration input mutate 안 함 (deep equality)          [의도 fail]
11. constants / function public export 차단                [이미 pass]
12. to_snapshot 출력 schema_version=1                      [이미 pass]
13. PR17 22 invariant 유효                                 [이미 pass]
14. 기존 636 회귀 없음 — 전체 통과로 입증
"""

from __future__ import annotations

import copy

import pytest

import ragcore
import ragcore.engine as engine_module
import ragcore.types as types_module
from ragcore import Engine


class TestSnapshotMigrationConstants:
    """§30.13 invariants 1, 2 — schema version constants."""

    def test_current_snapshot_schema_version_is_two(self) -> None:
        """PR21-L §33 Sub-decision AH: bumped 1 → 2 to accommodate
        new ``hint_evidence_types`` engine state."""
        val = getattr(engine_module, "_CURRENT_SNAPSHOT_SCHEMA_VERSION", None)
        assert val == 2

    def test_supported_snapshot_schema_versions_contains_one(self) -> None:
        val = getattr(engine_module, "_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS", None)
        assert val is not None
        assert 1 in val


class TestSnapshotMigrationFunction:
    """§30.13 invariant 3 — _migrate_snapshot_to_current callable."""

    def test_migration_function_exists(self) -> None:
        func = getattr(engine_module, "_migrate_snapshot_to_current", None)
        assert func is not None

    def test_migration_function_is_callable(self) -> None:
        func = getattr(engine_module, "_migrate_snapshot_to_current", None)
        assert func is not None
        assert callable(func)


class TestSnapshotMigrationValidation:
    """§30.13 invariants 6, 7, 8 — version 검증 (PR17 동작 보존, 이미 pass)."""

    def test_missing_schema_version_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            Engine.from_snapshot({})

    def test_unsupported_high_version_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            Engine.from_snapshot({"schema_version": 99})

    def test_version_3_unsupported_raises_value_error(self) -> None:
        """PR21-L 이후 v1/v2 는 supported. 미래 v3 자리는 여전히 unsupported."""
        with pytest.raises(ValueError):
            Engine.from_snapshot({"schema_version": 3})


class TestSnapshotMigrationIdentity:
    """§30.13 invariant 4 — v1 identity migration."""

    def test_v1_snapshot_returns_unchanged(self) -> None:
        """v1 snapshot 을 _migrate_snapshot_to_current 에 넣으면 그대로 반환."""
        func = getattr(engine_module, "_migrate_snapshot_to_current", None)
        assert func is not None

        # 최소 v1 snapshot
        engine = Engine()
        snap = engine.to_snapshot()

        migrated = func(snap)
        assert migrated == snap


class TestSnapshotMigrationIntegration:
    """§30.13 invariant 5 — from_snapshot 안 migration step + PR17 round-trip 보존."""

    def test_from_snapshot_passes_through_migration_step(self) -> None:
        """v1 snapshot 의 from_snapshot round-trip 이 그대로 동작.

        PR17 round-trip identity 가 PR18-K 의 migration step 도입 후에도 유지.
        """
        original = Engine()
        ev_entity = original.add_entity(entity_type=1)
        claim_id = original.add_claim(
            subject_id=ev_entity, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
            base_confidence=0.7,
        )

        snap = original.to_snapshot()
        restored = Engine.from_snapshot(snap)

        # PR17 round-trip identity
        assert restored.get_claim(claim_id) == original.get_claim(claim_id)
        assert restored.compute_effective_confidence(claim_id) == \
               original.compute_effective_confidence(claim_id)


class TestSnapshotMigrationDeterminismAndPurity:
    """§30.13 invariants 9, 10 — 결정성 + input mutate 안 함."""

    def test_migration_is_deterministic(self) -> None:
        """같은 input dict 두 번 호출 → 같은 output."""
        func = getattr(engine_module, "_migrate_snapshot_to_current", None)
        assert func is not None

        engine = Engine()
        snap = engine.to_snapshot()

        first = func(snap)
        second = func(snap)
        assert first == second

    def test_migration_does_not_mutate_input(self) -> None:
        """input dict 이 호출 후에도 deep-equal 으로 그대로."""
        func = getattr(engine_module, "_migrate_snapshot_to_current", None)
        assert func is not None

        engine = Engine()
        snap = engine.to_snapshot()
        snap_copy_before = copy.deepcopy(snap)

        func(snap)

        # input 그대로 (mutation 없음)
        assert snap == snap_copy_before


class TestSnapshotMigrationPrivacy:
    """§30.13 invariant 11 — constants / function public export 차단."""

    def test_migration_constants_not_in_ragcore(self) -> None:
        names = [
            "_CURRENT_SNAPSHOT_SCHEMA_VERSION",
            "_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS",
            "CURRENT_SNAPSHOT_SCHEMA_VERSION",
            "SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS",
        ]
        for n in names:
            assert not hasattr(ragcore, n), f"ragcore should not expose {n}"
            assert n not in getattr(ragcore, "__all__", []), (
                f"__all__ should not include {n}"
            )

    def test_migration_function_not_in_ragcore(self) -> None:
        names = [
            "_migrate_snapshot_to_current",
            "migrate_snapshot_to_current",
            "_migrate_snapshot",
            "migrate_snapshot",
        ]
        for n in names:
            assert not hasattr(ragcore, n), f"ragcore should not expose {n}"
            assert n not in getattr(ragcore, "__all__", []), (
                f"__all__ should not include {n}"
            )

    def test_migration_not_in_types(self) -> None:
        names = [
            "_CURRENT_SNAPSHOT_SCHEMA_VERSION",
            "_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS",
            "_migrate_snapshot_to_current",
            "CURRENT_SNAPSHOT_SCHEMA_VERSION",
            "SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS",
            "migrate_snapshot_to_current",
        ]
        for n in names:
            assert not hasattr(types_module, n), (
                f"ragcore.types should not expose {n}"
            )


class TestPriorPersistenceBehaviorUnchanged:
    """§30.13 invariants 12, 13 — PR17 동작 보존 (이미 pass)."""

    def test_to_snapshot_outputs_schema_version_2(self) -> None:
        """PR21-L §33 Sub-decision AH 후 — schema_version=2."""
        engine = Engine()
        snap = engine.to_snapshot()
        assert snap["schema_version"] == 2

    def test_pr17_round_trip_identity_preserved(self) -> None:
        """PR17 의 가장 강한 invariant — round-trip identity 가 PR18-K 후에도 유지."""
        original = Engine()
        e1 = original.add_entity(entity_type=1)
        c1 = original.add_claim(
            subject_id=e1, claim_type=1, rule_id=1, rule_version=1,
            reason_code=0, base_confidence=0.8,
        )
        original.add_gap(
            claim_id=c1, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = original.add_evidence(
            claim_id=c1, raw_ref_id=0, evidence_type=42, strength=0.7,
        )
        original.resolve_gaps_for_evidence(ev)
        original.confirm_claim_if_ready(c1)

        snap = original.to_snapshot()
        restored = Engine.from_snapshot(snap)

        # 모든 query 동일
        assert restored.get_claim(c1) == original.get_claim(c1)
        assert restored.compute_effective_confidence(c1) == \
               original.compute_effective_confidence(c1)
        assert restored.claim_lifecycle_history(c1) == \
               original.claim_lifecycle_history(c1)
        assert restored.gaps_for_claim(c1) == original.gaps_for_claim(c1)
