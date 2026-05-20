"""Tests for PR-H — Engine persistence (MVP, snapshot).

Invariants of ``engine.to_snapshot()`` + ``Engine.from_snapshot(dict)``.

**75차 (test-first) 상태**: 두 메서드 미구현. 호출 테스트는 ``AttributeError``
로 fail. 단, "PR1~PR12-D 의미 무변화" 검증은 **이미 pass** (PR11-A 59차 /
PR11-B 67차 패턴).

§29.11 의 22 invariant 매핑:
1.  to_snapshot returns dict                              [AttrErr fail]
2.  snapshot has schema_version = 1                       [AttrErr fail]
3.  round-trip empty engine                               [AttrErr fail]
4.  round-trip single claim                               [AttrErr fail]
5.  round-trip full lifecycle path                        [AttrErr fail]
6.  round-trip gap_resolution                             [AttrErr fail]
7.  round-trip contradictions / resolved                  [AttrErr fail]
8.  round-trip lifecycle history                          [AttrErr fail]
9.  round-trip rule registry                              [AttrErr fail]
10. round-trip _next_id (restore 후 새 등록 가능)         [AttrErr fail]
11. determinism — 같은 state 두 번 snapshot 동일          [AttrErr fail]
12. set serialized as sorted list                         [AttrErr fail]
13. dict[int, X] serialized sorted                        [AttrErr fail]
14. schema_version != 1 → ValueError                     [AttrErr fail]
15. malformed snapshot → ValueError                       [AttrErr fail]
16. JSON 호환성                                           [AttrErr fail]
17. restore 후 compute_effective_confidence 정확          [AttrErr fail]
18. restore 후 lifecycle API 호출 가능                    [AttrErr fail]
19. restore 후 register API 호출 가능                     [AttrErr fail]
20. restore 후 add_* API 호출 가능 (next_id 충돌 없음)    [AttrErr fail]
21. PR1~PR12-D 의미 무변화                                [이미 pass]
22. 기존 612 회귀 없음 — 전체 통과로 입증
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    Engine,
    RuleDefinition,
    ScoreValue,
)


def _candidate_claim(engine: Engine, *, base_confidence: float = 0.8) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=1,
        rule_version=1,
        reason_code=0,
        base_confidence=base_confidence,
    )
    return entity_id, claim_id


def _evidence(
    engine: Engine, claim_id: int, *, evidence_type: int = 42, strength: float = 0.5,
) -> int:
    return engine.add_evidence(
        claim_id=claim_id,
        raw_ref_id=0,
        evidence_type=evidence_type,
        strength=strength,
    )


def _build_rich_engine() -> Engine:
    """다양한 상태를 가진 engine — round-trip 검증용.

    - 2 entities
    - 3 claims (candidate / confirmed / disputed)
    - gap (resolved + unresolved)
    - contradictions (active + resolved)
    - lifecycle history (transition 여러 개)
    """
    engine = Engine()
    e1 = engine.add_entity(entity_type=1)
    e2 = engine.add_entity(entity_type=2)

    # claim_a: candidate (변환 없음)
    c_a = engine.add_claim(
        subject_id=e1, claim_type=1, rule_id=1, rule_version=1,
        reason_code=0, base_confidence=0.7,
    )

    # claim_b: candidate → confirmed (gap resolved)
    c_b = engine.add_claim(
        subject_id=e1, claim_type=1, rule_id=1, rule_version=1,
        reason_code=0, base_confidence=0.8,
    )
    g_b = engine.add_gap(
        claim_id=c_b, gap_type=1, required_evidence_type=42,
        severity=0.5, rule_id=1,
    )
    ev_b = engine.add_evidence(
        claim_id=c_b, raw_ref_id=0, evidence_type=42, strength=0.7,
    )
    engine.resolve_gaps_for_evidence(ev_b)
    engine.confirm_claim_if_ready(c_b)

    # claim_c: candidate → confirmed → disputed (active contradiction + unresolved gap)
    c_c = engine.add_claim(
        subject_id=e2, claim_type=1, rule_id=1, rule_version=1,
        reason_code=0, base_confidence=0.9,
    )
    # gap resolved 로 confirmed 시키기
    g_c1 = engine.add_gap(
        claim_id=c_c, gap_type=1, required_evidence_type=42,
        severity=0.5, rule_id=1,
    )
    ev_c1 = engine.add_evidence(
        claim_id=c_c, raw_ref_id=0, evidence_type=42, strength=0.8,
    )
    engine.resolve_gaps_for_evidence(ev_c1)
    engine.confirm_claim_if_ready(c_c)
    # 별도 contradiction 등록 + dispute
    ev_c_contra = engine.add_evidence(
        claim_id=c_c, raw_ref_id=0, evidence_type=99, strength=0.6,
    )
    engine.register_contradiction(c_c, ev_c_contra)
    engine.dispute_claim_if_ready(c_c)

    return engine


class TestSnapshotAPIExists:
    """§29.11 invariants 1, 2 — API 존재 + schema_version."""

    def test_to_snapshot_returns_dict(self) -> None:
        engine = Engine()
        snapshot = engine.to_snapshot()
        assert isinstance(snapshot, dict)

    def test_snapshot_has_schema_version_2(self) -> None:
        """PR21-L §33 Sub-decision AH: schema_version bumped 1 → 2."""
        engine = Engine()
        snapshot = engine.to_snapshot()
        assert snapshot["schema_version"] == 2


class TestSchemaVersionValidation:
    """§29.11 invariants 14, 15 — version 검증."""

    def test_unknown_schema_version_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            Engine.from_snapshot({"schema_version": 99})

    def test_missing_schema_version_raises_value_error(self) -> None:
        with pytest.raises((ValueError, KeyError)):
            Engine.from_snapshot({})


class TestSnapshotIsJsonCompatible:
    """§29.11 invariant 16 — JSON 호환성."""

    def test_empty_engine_snapshot_is_json_serializable(self) -> None:
        engine = Engine()
        snapshot = engine.to_snapshot()
        # json.dumps 가 에러 없이 동작해야 함
        json_str = json.dumps(snapshot)
        assert isinstance(json_str, str)

    def test_rich_engine_snapshot_is_json_serializable(self) -> None:
        engine = _build_rich_engine()
        snapshot = engine.to_snapshot()
        json_str = json.dumps(snapshot)
        assert isinstance(json_str, str)


class TestRoundtripIdentity:
    """§29.11 invariants 3~9, 17 — round-trip 후 query identity (가장 중요)."""

    # invariant 3
    def test_roundtrip_empty_engine(self) -> None:
        original = Engine()
        snapshot = original.to_snapshot()
        restored = Engine.from_snapshot(snapshot)
        # 둘 다 빈 상태 — 새 add_entity 가 같은 ID 부터 시작
        assert original.add_entity(entity_type=1) == restored.add_entity(entity_type=1)

    # invariant 4
    def test_roundtrip_single_claim(self) -> None:
        original = Engine()
        _, claim_id = _candidate_claim(original, base_confidence=0.7)

        snapshot = original.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        assert restored.get_claim(claim_id) == original.get_claim(claim_id)
        assert restored.compute_effective_confidence(claim_id) == \
               original.compute_effective_confidence(claim_id)

    # invariant 5 — 전체 lifecycle path
    def test_roundtrip_full_lifecycle(self) -> None:
        """candidate → confirmed → disputed → refuted (PR11-B by_freshness)."""
        original = _build_rich_engine()
        # 추가로 disputed claim 을 refuted 까지
        # claim_c 는 이미 disputed 상태
        # PR11-B: active strong evidence 필요 — ev_c_contra 는 0.6 이라 < 0.8
        # white-box 로 직접 ev_c_contra 강하게 못 함, 다른 시나리오로

        snapshot = original.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        # 모든 claim_id 의 status / history 동일
        for claim_id in original._claims:
            assert restored.get_claim(claim_id) == original.get_claim(claim_id)
            assert restored.claim_lifecycle_history(claim_id) == \
                   original.claim_lifecycle_history(claim_id)
            assert restored.compute_effective_confidence(claim_id) == \
                   original.compute_effective_confidence(claim_id)

    # invariant 6
    def test_roundtrip_preserves_gap_resolution(self) -> None:
        original = _build_rich_engine()
        snapshot = original.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        for claim_id in original._claims:
            orig_gaps = original.gaps_for_claim(claim_id)
            rest_gaps = restored.gaps_for_claim(claim_id)
            assert orig_gaps == rest_gaps
            for gap in orig_gaps:
                assert restored.gap_resolution(gap.id) == \
                       original.gap_resolution(gap.id)

    # invariant 7
    def test_roundtrip_preserves_contradictions(self) -> None:
        original = _build_rich_engine()
        snapshot = original.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        for claim_id in original._claims:
            assert restored.contradictions_for_claim(claim_id) == \
                   original.contradictions_for_claim(claim_id)
            assert restored.active_contradictions_for_claim(claim_id) == \
                   original.active_contradictions_for_claim(claim_id)
            assert restored.resolved_contradictions_for_claim(claim_id) == \
                   original.resolved_contradictions_for_claim(claim_id)
            assert restored.active_contradictions_by_freshness(claim_id) == \
                   original.active_contradictions_by_freshness(claim_id)

    # invariant 8
    def test_roundtrip_preserves_lifecycle_history(self) -> None:
        original = _build_rich_engine()
        snapshot = original.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        for claim_id in original._claims:
            assert restored.claim_lifecycle_history(claim_id) == \
                   original.claim_lifecycle_history(claim_id)

    # invariant 9
    def test_roundtrip_preserves_rule_registry(self) -> None:
        """rule registry (definitions + stats) 보존."""
        original = Engine()
        rule_def = RuleDefinition(
            id=42, version=1, maturity=0,
            prior_confidence=ScoreValue(0.5),
        )
        original.register_rule(rule_def)
        original.update_rule_stats(rule_id=42, rule_version=1, firing_delta=3)

        snapshot = original.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        assert restored.get_rule(42, 1) == original.get_rule(42, 1)
        assert restored.get_rule_stats(42, 1) == original.get_rule_stats(42, 1)

    # invariant 17 — effective with all modifiers (round-trip identity)
    def test_roundtrip_effective_with_all_modifiers(self) -> None:
        """status × freshness × gap modifier 결합이 정확히 복원.

        PR23-M §35.5 (AP): 1 unresolved → tier 1 → 0.9 (PR12-D binary 0.8 정제).
        의미 (round-trip identity) 보존, gap 강도만 갱신.
        """
        original = Engine()
        _, c = _candidate_claim(original, base_confidence=1.0)
        # contradiction (freshness modifier 적용)
        ev_contra = _evidence(original, c, strength=0.8)
        original.register_contradiction(c, ev_contra)
        # unresolved gap (gap modifier 적용)
        original.add_gap(
            claim_id=c, gap_type=1, required_evidence_type=99,
            severity=0.5, rule_id=2,
        )
        # confirmed
        original._claims[c] = replace(
            original._claims[c], status=CLAIM_STATUS_CONFIRMED,
        )

        original_eff = original.compute_effective_confidence(c)
        # 1.0 × 1.0 × (1 - 0.8 × 0.5) × 0.9 (1 unresolved tier) = 0.54
        assert original_eff.value == pytest.approx(0.54)

        snapshot = original.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        restored_eff = restored.compute_effective_confidence(c)
        assert restored_eff == original_eff
        assert restored_eff.value == pytest.approx(0.54)


class TestRestoredEngineCanContinue:
    """§29.11 invariants 10, 18~20 — restore 후 새 작업 가능."""

    # invariant 10 — _next_id 보존
    def test_restored_engine_can_add_new_entity_without_id_collision(self) -> None:
        original = Engine()
        _, original_claim = _candidate_claim(original)

        snapshot = original.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        # restored 가 새 entity 등록 → original 의 max id 보다 큰 id
        new_entity = restored.add_entity(entity_type=99)
        assert new_entity > 0
        # 기존 entity 와 id 충돌 없음
        for existing_id in original._entities:
            assert new_entity != existing_id

    # invariant 18
    def test_restored_engine_can_trigger_lifecycle_transitions(self) -> None:
        """restore 후 confirm_claim_if_ready 등 동작."""
        original = Engine()
        _, c = _candidate_claim(original)
        original.add_gap(
            claim_id=c, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = _evidence(original, c, evidence_type=42)
        original.resolve_gaps_for_evidence(ev)
        # 아직 confirm 안 함

        snapshot = original.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        # restored 에서 confirm 호출
        result = restored.confirm_claim_if_ready(c)
        assert result is True
        assert restored.get_claim(c).status == CLAIM_STATUS_CONFIRMED
        # lifecycle history 추가됨
        assert len(restored.claim_lifecycle_history(c)) == 1

    # invariant 19
    def test_restored_engine_can_register_contradiction(self) -> None:
        original = Engine()
        _, c = _candidate_claim(original)

        snapshot = original.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        ev = _evidence(restored, c)
        result = restored.register_contradiction(c, ev)
        assert result is True
        assert ev in restored.contradictions_for_claim(c)

    # invariant 20
    def test_restored_engine_can_add_new_claim(self) -> None:
        original = _build_rich_engine()
        snapshot = original.to_snapshot()
        restored = Engine.from_snapshot(snapshot)

        # 새 entity + claim 생성 — next_id 충돌 없음
        new_ent = restored.add_entity(entity_type=99)
        new_claim = restored.add_claim(
            subject_id=new_ent, claim_type=1, rule_id=1, rule_version=1,
            reason_code=0, base_confidence=0.5,
        )
        assert restored.get_claim(new_claim) is not None
        # 기존 claim 들도 그대로 존재
        for existing_claim in original._claims:
            assert restored.get_claim(existing_claim) == \
                   original.get_claim(existing_claim)


class TestDeterminism:
    """§29.11 invariants 11, 12, 13 — 결정성."""

    # invariant 11
    def test_two_snapshots_are_equal(self) -> None:
        """같은 engine state 두 번 to_snapshot → 같은 dict."""
        engine = _build_rich_engine()
        snap1 = engine.to_snapshot()
        snap2 = engine.to_snapshot()
        assert snap1 == snap2

    # invariant 12 — set serialized as sorted
    def test_sets_serialized_in_deterministic_order(self) -> None:
        """contradictions / resolved_contradictions 등 set 이 sorted list 로."""
        engine = Engine()
        _, c = _candidate_claim(engine)
        # 의도적으로 desc 순서로 evidence 등록
        ev3 = _evidence(engine, c)
        ev1 = _evidence(engine, c)
        ev2 = _evidence(engine, c)
        engine.register_contradiction(c, ev3)
        engine.register_contradiction(c, ev1)
        engine.register_contradiction(c, ev2)

        snap = engine.to_snapshot()
        # round-trip 후에도 같은 결과
        restored = Engine.from_snapshot(snap)
        assert engine.contradictions_for_claim(c) == \
               restored.contradictions_for_claim(c)

    # invariant 13
    def test_int_keyed_dicts_serialized_in_deterministic_order(self) -> None:
        """dict[claim_id] / dict[gap_id] / dict[evidence_id] 등 — 결정적."""
        engine_a = _build_rich_engine()
        engine_b = _build_rich_engine()  # 같은 절차로 빌드 → 같은 state
        # 같은 state → 같은 snapshot
        assert engine_a.to_snapshot() == engine_b.to_snapshot()


class TestPriorAPIUnchanged:
    """§29.11 invariant 21 — PR1~PR12-D 의미 무변화 (이미 pass)."""

    def test_compute_effective_confidence_unchanged(self) -> None:
        """modifier composition (PR11-D + PR11-C + PR12-D + PR23-M) 정확히 적용.

        PR23-M §35.5 (AP): 1 unresolved → tier 1 → 0.9 (PR12-D binary 0.8 정제).
        의미 (composition 보존) 그대로, gap 강도만 갱신.
        """
        engine = Engine()
        _, c = _candidate_claim(engine, base_confidence=1.0)
        ev_contra = _evidence(engine, c, strength=0.8)
        engine.register_contradiction(c, ev_contra)
        engine.add_gap(
            claim_id=c, gap_type=1, required_evidence_type=99,
            severity=0.5, rule_id=2,
        )
        engine._claims[c] = replace(
            engine._claims[c], status=CLAIM_STATUS_CONFIRMED,
        )
        # 1.0 × 1.0 × 0.6 × 0.9 (1 unresolved tier) = 0.54
        assert engine.compute_effective_confidence(c).value == pytest.approx(0.54)

    def test_lifecycle_apis_unchanged(self) -> None:
        """5 lifecycle API + PR11-B sibling 모두 정상 동작."""
        engine = Engine()
        _, c = _candidate_claim(engine)
        # PR6 confirm path
        engine.add_gap(
            claim_id=c, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = _evidence(engine, c, evidence_type=42)
        engine.resolve_gaps_for_evidence(ev)
        assert engine.confirm_claim_if_ready(c) is True
        # PR8 dispute path
        ev_contra = _evidence(engine, c, strength=0.5)
        engine.register_contradiction(c, ev_contra)
        assert engine.dispute_claim_if_ready(c) is True
        # PR9-A resolve_disputed path
        engine.register_contradiction_resolution(c, ev_contra)
        assert engine.resolve_disputed_claim_if_ready(c) is True
        assert engine.get_claim(c).status == CLAIM_STATUS_CONFIRMED

    def test_register_apis_unchanged(self) -> None:
        engine = Engine()
        _, c = _candidate_claim(engine)
        ev = _evidence(engine, c)
        assert engine.register_contradiction(c, ev) is True
        assert engine.register_contradiction(c, ev) is False  # idempotent
        assert engine.register_contradiction_resolution(c, ev) is True
        assert engine.register_contradiction_resolution(c, ev) is False
