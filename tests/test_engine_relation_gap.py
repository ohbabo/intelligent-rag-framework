"""Tests for add_relation / add_gap / gaps_for_claim — engine wiring of Relation+Gap."""

from __future__ import annotations

import pytest

from ragcore import Engine


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
            from_id=a, to_id=b, relation_type=5, rule_id=2, reason_code=3
        )
        rel = engine.get_relation(rel_id)
        assert rel.from_id == a
        assert rel.to_id == b
        assert rel.type == 5
        assert rel.rule_id == 2
        assert rel.reason_code == 3

    def test_rejects_unknown_from_id(self) -> None:
        engine = Engine()
        b = engine.add_entity(entity_type=1)
        with pytest.raises(KeyError):
            engine.add_relation(
                from_id=999, to_id=b, relation_type=1, rule_id=1, reason_code=0
            )

    def test_rejects_unknown_to_id(self) -> None:
        engine = Engine()
        a = engine.add_entity(entity_type=1)
        with pytest.raises(KeyError):
            engine.add_relation(
                from_id=a, to_id=999, relation_type=1, rule_id=1, reason_code=0
            )

    def test_can_relate_claim_to_evidence(self) -> None:
        engine = Engine()
        _, claim_id = _entity_and_claim(engine)
        evidence_id = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=1, evidence_type=1, strength=0.5
        )
        rel_id = engine.add_relation(
            from_id=claim_id,
            to_id=evidence_id,
            relation_type=1,
            rule_id=1,
            reason_code=0,
        )
        rel = engine.get_relation(rel_id)
        assert rel.from_id == claim_id
        assert rel.to_id == evidence_id

    def test_relation_id_independent_from_other_kinds(self) -> None:
        engine = Engine()
        a = engine.add_entity(entity_type=1)
        b = engine.add_entity(entity_type=1)
        rel_id = engine.add_relation(
            from_id=a, to_id=b, relation_type=1, rule_id=1, reason_code=0
        )
        assert rel_id == 1


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
            from_id=gap_id,
            to_id=evidence_id,
            relation_type=99,
            rule_id=42,
            reason_code=0,
        )

        assert engine.get_claim(claim_id).created_by_rule == 42
        assert engine.evidences_for_claim(claim_id)[0].id == evidence_id
        assert engine.gaps_for_claim(claim_id)[0].id == gap_id
