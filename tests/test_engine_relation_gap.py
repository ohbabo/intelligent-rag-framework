"""Tests for add_relation / add_gap / gaps_for_claim — engine wiring of Relation+Gap.

Relation은 kind-aware로 동작한다 (from_kind, to_kind 명시).
"""

from __future__ import annotations

import pytest

from ragcore import (
    KIND_CLAIM,
    KIND_ENTITY,
    KIND_EVIDENCE,
    KIND_GAP,
    KIND_OBSERVATION,
    Engine,
    ScoreValue,
)


def _entity_and_claim(engine: Engine) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=1,
        rule_version=1,
        reason_code=0,
    )
    return entity_id, claim_id


class TestAddRelation:
    def test_stores_and_retrieves(self) -> None:
        engine = Engine()
        a = engine.add_entity(entity_type=1)
        b = engine.add_entity(entity_type=1)
        rel_id = engine.add_relation(
            from_kind=KIND_ENTITY,
            from_id=a,
            to_kind=KIND_ENTITY,
            to_id=b,
            relation_type=5,
            rule_id=2,
            reason_code=3,
        )
        rel = engine.get_relation(rel_id)
        assert rel.from_kind == KIND_ENTITY
        assert rel.from_id == a
        assert rel.to_kind == KIND_ENTITY
        assert rel.to_id == b
        assert rel.type == 5
        assert rel.rule_id == 2
        assert rel.reason_code == 3

    def test_rejects_unknown_from_id(self) -> None:
        engine = Engine()
        b = engine.add_entity(entity_type=1)
        with pytest.raises(KeyError):
            engine.add_relation(
                from_kind=KIND_ENTITY,
                from_id=999,
                to_kind=KIND_ENTITY,
                to_id=b,
                relation_type=1,
                rule_id=1,
                reason_code=0,
            )

    def test_rejects_unknown_to_id(self) -> None:
        engine = Engine()
        a = engine.add_entity(entity_type=1)
        with pytest.raises(KeyError):
            engine.add_relation(
                from_kind=KIND_ENTITY,
                from_id=a,
                to_kind=KIND_ENTITY,
                to_id=999,
                relation_type=1,
                rule_id=1,
                reason_code=0,
            )

    def test_can_relate_claim_to_evidence(self) -> None:
        engine = Engine()
        _, claim_id = _entity_and_claim(engine)
        evidence_id = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=1, evidence_type=1, strength=0.5
        )
        rel_id = engine.add_relation(
            from_kind=KIND_CLAIM,
            from_id=claim_id,
            to_kind=KIND_EVIDENCE,
            to_id=evidence_id,
            relation_type=1,
            rule_id=1,
            reason_code=0,
        )
        rel = engine.get_relation(rel_id)
        assert rel.from_kind == KIND_CLAIM
        assert rel.to_kind == KIND_EVIDENCE
        assert rel.from_id == claim_id
        assert rel.to_id == evidence_id

    def test_relation_id_independent_from_other_kinds(self) -> None:
        engine = Engine()
        a = engine.add_entity(entity_type=1)
        b = engine.add_entity(entity_type=1)
        rel_id = engine.add_relation(
            from_kind=KIND_ENTITY,
            from_id=a,
            to_kind=KIND_ENTITY,
            to_id=b,
            relation_type=1,
            rule_id=1,
            reason_code=0,
        )
        assert rel_id == 1


class TestKindDisambiguation:
    def test_same_id_different_kinds_remain_distinct(self) -> None:
        """entity:1 과 claim:1 이 동시에 존재할 때, Relation은 kind로 정확히 구분된다."""
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=1,
            rule_id=1,
            rule_version=1,
            reason_code=0,
        )
        # 두 ID는 같은 정수 1을 가짐 (kind 독립 발급).
        assert entity_id == 1
        assert claim_id == 1

        rel_id = engine.add_relation(
            from_kind=KIND_ENTITY,
            from_id=entity_id,
            to_kind=KIND_CLAIM,
            to_id=claim_id,
            relation_type=1,
            rule_id=1,
            reason_code=0,
        )
        rel = engine.get_relation(rel_id)
        # 같은 ID(=1)지만 kind로 명확히 entity → claim 임을 보존.
        assert rel.from_kind == KIND_ENTITY
        assert rel.to_kind == KIND_CLAIM
        assert rel.from_id == 1
        assert rel.to_id == 1

    def test_rejects_unknown_kind(self) -> None:
        engine = Engine()
        e = engine.add_entity(entity_type=1)
        with pytest.raises(ValueError):
            engine.add_relation(
                from_kind=99,
                from_id=e,
                to_kind=KIND_ENTITY,
                to_id=e,
                relation_type=1,
                rule_id=1,
                reason_code=0,
            )

    def test_rejects_id_missing_in_specified_kind(self) -> None:
        """entity:1 존재해도 claim:1 미존재면 add_relation(to_kind=CLAIM, to_id=1) 거부."""
        engine = Engine()
        engine.add_entity(entity_type=1)
        with pytest.raises(KeyError):
            engine.add_relation(
                from_kind=KIND_ENTITY,
                from_id=1,
                to_kind=KIND_CLAIM,
                to_id=1,
                relation_type=1,
                rule_id=1,
                reason_code=0,
            )

    def test_observation_kind_works(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        obs_id = engine.add_observation(
            entity_id=entity_id, raw_ref_id=1, observation_type=1
        )
        rel_id = engine.add_relation(
            from_kind=KIND_OBSERVATION,
            from_id=obs_id,
            to_kind=KIND_ENTITY,
            to_id=entity_id,
            relation_type=1,
            rule_id=1,
            reason_code=0,
        )
        assert engine.get_relation(rel_id).from_kind == KIND_OBSERVATION


class TestAddGap:
    def test_attaches_to_existing_claim(self) -> None:
        engine = Engine()
        _, claim_id = _entity_and_claim(engine)
        gap_id = engine.add_gap(
            claim_id=claim_id,
            gap_type=2,
            required_evidence_type=42,
            severity=0.8,
            rule_id=7,
        )
        gap = engine.get_gap(gap_id)
        assert gap.claim_id == claim_id
        assert gap.type == 2
        assert gap.required_evidence_type == 42
        assert gap.severity.value == pytest.approx(0.8)
        assert gap.created_by_rule == 7

    def test_severity_wrapped_in_score_value(self) -> None:
        engine = Engine()
        _, claim_id = _entity_and_claim(engine)
        gap_id = engine.add_gap(
            claim_id=claim_id,
            gap_type=1,
            required_evidence_type=1,
            severity=0.6234,
            rule_id=1,
        )
        gap = engine.get_gap(gap_id)
        assert gap.severity.to_uint16_scale() == 6234

    def test_rejects_unknown_claim(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.add_gap(
                claim_id=999,
                gap_type=1,
                required_evidence_type=1,
                severity=0.5,
                rule_id=1,
            )

    def test_rejects_out_of_range_severity(self) -> None:
        engine = Engine()
        _, claim_id = _entity_and_claim(engine)
        with pytest.raises(ValueError):
            engine.add_gap(
                claim_id=claim_id,
                gap_type=1,
                required_evidence_type=1,
                severity=1.5,
                rule_id=1,
            )

    def test_gap_id_independent_from_other_kinds(self) -> None:
        engine = Engine()
        _, claim_id = _entity_and_claim(engine)
        gap_id = engine.add_gap(
            claim_id=claim_id,
            gap_type=1,
            required_evidence_type=1,
            severity=0.5,
            rule_id=1,
        )
        assert gap_id == 1


class TestAddGapDedup:
    """PR4 §16 — exact-match Gap dedup smoke tests.

    27차 implementation 의 핵심 동작 잠금. 11개 invariant 의 완전한
    잠금은 28차 (별도 test 추가) 책임.
    """

    def test_same_claim_same_key_returns_same_gap_id(self) -> None:
        """같은 claim + 같은 key 로 두 번 호출 → 같은 gap_id."""
        engine = Engine()
        _, claim_id = _entity_and_claim(engine)
        gap1 = engine.add_gap(
            claim_id=claim_id, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        gap2 = engine.add_gap(
            claim_id=claim_id, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        assert gap1 == gap2

    def test_cross_claim_same_key_reuses_gap(self) -> None:
        """다른 claim 이지만 (subject, rule, type, evidence) 동일 → 같은 gap_id."""
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_a = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=7, rule_version=1, reason_code=0,
        )
        claim_b = engine.add_claim(
            subject_id=entity_id, claim_type=2,
            rule_id=7, rule_version=1, reason_code=0,
        )
        gap_a = engine.add_gap(
            claim_id=claim_a, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        gap_b = engine.add_gap(
            claim_id=claim_b, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        assert gap_a == gap_b

    def test_gaps_for_claim_returns_reused_gap_for_second_claim(self) -> None:
        """dedup hit 시에도 _claim_gap_refs 가 갱신 — 두 claim 모두 같은 gap 참조."""
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_a = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=7, rule_version=1, reason_code=0,
        )
        claim_b = engine.add_claim(
            subject_id=entity_id, claim_type=2,
            rule_id=7, rule_version=1, reason_code=0,
        )
        gap_a = engine.add_gap(
            claim_id=claim_a, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        engine.add_gap(
            claim_id=claim_b, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        gaps_a = engine.gaps_for_claim(claim_a)
        gaps_b = engine.gaps_for_claim(claim_b)
        assert len(gaps_a) == 1
        assert len(gaps_b) == 1
        assert gaps_a[0].id == gap_a
        assert gaps_b[0].id == gap_a  # 같은 gap, reused

    def test_first_registering_claim_id_preserved_on_dedup(self) -> None:
        """dedup hit 시 Gap.claim_id 는 first registering claim 유지 (§16 의미 약화)."""
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_a = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=7, rule_version=1, reason_code=0,
        )
        claim_b = engine.add_claim(
            subject_id=entity_id, claim_type=2,
            rule_id=7, rule_version=1, reason_code=0,
        )
        gap_id = engine.add_gap(
            claim_id=claim_a, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        engine.add_gap(
            claim_id=claim_b, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        # 두 번째 add_gap 호출이 dedup hit — Gap.claim_id 갱신되지 않음
        gap = engine.get_gap(gap_id)
        assert gap.claim_id == claim_a


class TestAddGapDedupKeyFields:
    """§16 dedup key 의 각 필드가 의도대로 작동하는지 invariant 잠금.

    dedup key = (subject_id, created_by_rule, gap_type, required_evidence_type)
    명시적 제외: rule_version, severity
    """

    def _claim_for(
        self, engine: Engine, entity_id: int, *,
        claim_type: int = 1, rule_id: int = 7, rule_version: int = 1,
    ) -> int:
        return engine.add_claim(
            subject_id=entity_id, claim_type=claim_type,
            rule_id=rule_id, rule_version=rule_version, reason_code=0,
        )

    def test_different_subject_creates_new_gap(self) -> None:
        """subject_id 가 dedup key 의 첫 필드 — 다른 entity 는 별개 gap."""
        engine = Engine()
        ent_a = engine.add_entity(entity_type=1)
        ent_b = engine.add_entity(entity_type=1)
        claim_a = self._claim_for(engine, ent_a)
        claim_b = self._claim_for(engine, ent_b)

        gap_a = engine.add_gap(
            claim_id=claim_a, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        gap_b = engine.add_gap(
            claim_id=claim_b, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        assert gap_a != gap_b

    def test_different_rule_creates_new_gap(self) -> None:
        """created_by_rule (rule_id) 이 dedup key — 다른 룰은 별개."""
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_x = self._claim_for(engine, entity_id, rule_id=7)
        claim_y = self._claim_for(engine, entity_id, claim_type=2, rule_id=8)

        gap_x = engine.add_gap(
            claim_id=claim_x, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        gap_y = engine.add_gap(
            claim_id=claim_y, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=8,
        )
        assert gap_x != gap_y

    def test_different_gap_type_creates_new_gap(self) -> None:
        """gap_type 이 dedup key — 같은 evidence_type 이라도 다른 gap_type 은 별개."""
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = self._claim_for(engine, entity_id)

        gap1 = engine.add_gap(
            claim_id=claim_id, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        gap2 = engine.add_gap(
            claim_id=claim_id, gap_type=2,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        assert gap1 != gap2

    def test_different_required_evidence_type_creates_new_gap(self) -> None:
        """required_evidence_type 이 dedup key."""
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = self._claim_for(engine, entity_id)

        gap1 = engine.add_gap(
            claim_id=claim_id, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        gap2 = engine.add_gap(
            claim_id=claim_id, gap_type=1,
            required_evidence_type=43, severity=0.5, rule_id=7,
        )
        assert gap1 != gap2

    def test_severity_excluded_from_dedup_key(self) -> None:
        """severity 는 정체성 아닌 우선순위 속성 — 다른 severity 라도 같은 key 면 reuse."""
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_a = self._claim_for(engine, entity_id)
        claim_b = self._claim_for(engine, entity_id, claim_type=2)

        gap_a = engine.add_gap(
            claim_id=claim_a, gap_type=1,
            required_evidence_type=42, severity=0.3, rule_id=7,
        )
        gap_b = engine.add_gap(
            claim_id=claim_b, gap_type=1,
            required_evidence_type=42, severity=0.9, rule_id=7,
        )
        assert gap_a == gap_b

    def test_severity_of_first_registering_call_preserved_on_dedup(self) -> None:
        """severity merge 금지 — 기존 Gap 의 severity 유지 (§16 명시)."""
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_a = self._claim_for(engine, entity_id)
        claim_b = self._claim_for(engine, entity_id, claim_type=2)

        gap_id = engine.add_gap(
            claim_id=claim_a, gap_type=1,
            required_evidence_type=42, severity=0.3, rule_id=7,
        )
        # 두 번째 호출은 더 높은 severity 지만 무시되어야 함
        engine.add_gap(
            claim_id=claim_b, gap_type=1,
            required_evidence_type=42, severity=0.9, rule_id=7,
        )
        assert engine.get_gap(gap_id).severity == ScoreValue(0.3)

    def test_dedup_hit_still_rejects_out_of_range_severity(self) -> None:
        """dedup hit 이라도 잘못된 severity 입력은 ValueError.

        severity 는 dedup key 가 아니지만, 입력 검증 의미는 보존되어야 한다.
        dedup hit/miss 모두 동일하게 ScoreValue 의 [0.0, 1.0] 범위 검증 적용.
        기존 Gap 의 severity 는 영향 받지 않음 (merge 금지).
        """
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_a = self._claim_for(engine, entity_id)
        claim_b = self._claim_for(engine, entity_id, claim_type=2)

        gap_id = engine.add_gap(
            claim_id=claim_a, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )

        # 같은 dedup key, 잘못된 severity → ValueError (dedup hit 검증 우회 X)
        with pytest.raises(ValueError):
            engine.add_gap(
                claim_id=claim_b, gap_type=1,
                required_evidence_type=42, severity=1.5, rule_id=7,
            )

        # 기존 Gap 의 severity 는 first registering 값 그대로 유지
        assert engine.get_gap(gap_id).severity == ScoreValue(0.5)


class TestAddGapDedupConsistency:
    """§16 — public API ↔ private state 일관성, engine 격리."""

    def test_gaps_for_claim_matches_internal_claim_gap_refs(self) -> None:
        """gaps_for_claim 결과 ≡ _claim_gap_refs 의 gap 목록 (§16 invariant).

        Private 필드 직접 검증 — 계약 잠금 목적으로 허용된 단일 예외.
        """
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=7, rule_version=1, reason_code=0,
        )
        engine.add_gap(
            claim_id=claim_id, gap_type=1,
            required_evidence_type=1, severity=0.5, rule_id=7,
        )
        engine.add_gap(
            claim_id=claim_id, gap_type=1,
            required_evidence_type=2, severity=0.5, rule_id=7,
        )

        public_ids = {g.id for g in engine.gaps_for_claim(claim_id)}
        private_ids = engine._claim_gap_refs[claim_id]
        assert public_ids == private_ids

    def test_dedup_index_isolated_per_engine_instance(self) -> None:
        """두 Engine 인스턴스가 dedup index 를 공유하지 않음."""
        engine_a = Engine()
        engine_b = Engine()

        ent_a = engine_a.add_entity(entity_type=1)
        ent_b = engine_b.add_entity(entity_type=1)
        claim_a = engine_a.add_claim(
            subject_id=ent_a, claim_type=1, rule_id=7,
            rule_version=1, reason_code=0,
        )
        claim_b = engine_b.add_claim(
            subject_id=ent_b, claim_type=1, rule_id=7,
            rule_version=1, reason_code=0,
        )

        gap_a = engine_a.add_gap(
            claim_id=claim_a, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        # engine_b 도 같은 key 로 등록 가능 (independent state)
        gap_b = engine_b.add_gap(
            claim_id=claim_b, gap_type=1,
            required_evidence_type=42, severity=0.5, rule_id=7,
        )
        # 두 engine 모두 첫 gap 이므로 gap_id == 1, 하지만 다른 Engine
        assert gap_a == 1
        assert gap_b == 1
        # 다른 engine 의 _gap_dedup_index 는 독립
        assert engine_a._gap_dedup_index is not engine_b._gap_dedup_index


class TestGapsForClaim:
    def test_returns_only_attached_gaps(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_a = engine.add_claim(
            subject_id=entity_id,
            claim_type=1,
            rule_id=1,
            rule_version=1,
            reason_code=0,
        )
        claim_b = engine.add_claim(
            subject_id=entity_id,
            claim_type=2,
            rule_id=1,
            rule_version=1,
            reason_code=0,
        )
        engine.add_gap(
            claim_id=claim_a,
            gap_type=1,
            required_evidence_type=1,
            severity=0.3,
            rule_id=1,
        )
        engine.add_gap(
            claim_id=claim_a,
            gap_type=2,
            required_evidence_type=2,
            severity=0.7,
            rule_id=1,
        )
        engine.add_gap(
            claim_id=claim_b,
            gap_type=1,
            required_evidence_type=1,
            severity=0.5,
            rule_id=1,
        )

        gaps_a = engine.gaps_for_claim(claim_a)
        gaps_b = engine.gaps_for_claim(claim_b)

        assert len(gaps_a) == 2
        assert len(gaps_b) == 1
        assert {g.type for g in gaps_a} == {1, 2}
        assert gaps_b[0].type == 1

    def test_returns_empty_when_no_gaps(self) -> None:
        engine = Engine()
        _, claim_id = _entity_and_claim(engine)
        assert engine.gaps_for_claim(claim_id) == []

    def test_rejects_unknown_claim(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.gaps_for_claim(claim_id=999)


class TestMinimalLoopClosesEnd2End:
    """Entity → Observation → Claim → Evidence → Gap → Relation 최소 루프."""

    def test_full_chain(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        engine.add_observation(
            entity_id=entity_id, raw_ref_id=100, observation_type=1
        )
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=10,
            rule_id=42,
            rule_version=1,
            reason_code=3,
        )
        evidence_id = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=200, evidence_type=2, strength=0.4
        )
        gap_id = engine.add_gap(
            claim_id=claim_id,
            gap_type=5,
            required_evidence_type=7,
            severity=0.6,
            rule_id=42,
        )
        engine.add_relation(
            from_kind=KIND_GAP,
            from_id=gap_id,
            to_kind=KIND_EVIDENCE,
            to_id=evidence_id,
            relation_type=99,
            rule_id=42,
            reason_code=0,
        )

        assert engine.get_claim(claim_id).created_by_rule == 42
        assert engine.evidences_for_claim(claim_id)[0].id == evidence_id
        assert engine.gaps_for_claim(claim_id)[0].id == gap_id
