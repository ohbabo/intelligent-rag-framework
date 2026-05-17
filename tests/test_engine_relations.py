"""Tests for Observation / Claim / Evidence add APIs and relation types."""

from __future__ import annotations

import pytest

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    Engine,
    Gap,
    Relation,
    ScoreValue,
)


class TestObservation:
    def test_attaches_to_existing_entity(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        obs_id = engine.add_observation(
            entity_id=entity_id, raw_ref_id=100, observation_type=5
        )
        obs = engine.get_observation(obs_id)
        assert obs.entity_id == entity_id
        assert obs.raw_ref_id == 100
        assert obs.type == 5
        assert obs.source_type == 0

    def test_rejects_unknown_entity(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.add_observation(entity_id=999, raw_ref_id=1, observation_type=1)

    def test_ids_independent_from_entity_ids(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        obs_id = engine.add_observation(
            entity_id=entity_id, raw_ref_id=1, observation_type=1
        )
        assert obs_id == 1
        assert entity_id == 1


class TestClaim:
    def test_preserves_generated_by_fields(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=42,
            rule_id=7,
            rule_version=10,
            reason_code=3,
        )
        claim = engine.get_claim(claim_id)
        assert claim.subject_id == entity_id
        assert claim.type == 42
        assert claim.created_by_rule == 7
        assert claim.created_by_rule_version == 10
        assert claim.reason_code == 3

    def test_status_defaults_to_candidate(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=1,
            rule_id=1,
            rule_version=1,
            reason_code=0,
        )
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CANDIDATE

    def test_status_can_be_set_confirmed(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=1,
            rule_id=1,
            rule_version=1,
            reason_code=0,
            status=CLAIM_STATUS_CONFIRMED,
        )
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    def test_rejects_unknown_subject(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.add_claim(
                subject_id=999,
                claim_type=1,
                rule_id=1,
                rule_version=1,
                reason_code=0,
            )


class TestEvidence:
    def _make_claim(self, engine: Engine) -> tuple[int, int]:
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=1,
            rule_id=1,
            rule_version=1,
            reason_code=0,
        )
        return entity_id, claim_id

    def test_links_to_existing_claim(self) -> None:
        engine = Engine()
        _, claim_id = self._make_claim(engine)
        ev_id = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=500, evidence_type=2, strength=0.75
        )
        evidence = engine.get_evidence(ev_id)
        assert evidence.claim_id == claim_id
        assert evidence.raw_ref_id == 500
        assert evidence.type == 2

    def test_strength_wrapped_in_score_value(self) -> None:
        engine = Engine()
        _, claim_id = self._make_claim(engine)
        ev_id = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=1, evidence_type=1, strength=0.7234
        )
        evidence = engine.get_evidence(ev_id)
        assert isinstance(evidence.strength, ScoreValue)
        assert evidence.strength.value == pytest.approx(0.7234)
        assert evidence.strength.to_uint16_scale() == 7234

    def test_rejects_out_of_range_strength(self) -> None:
        engine = Engine()
        _, claim_id = self._make_claim(engine)
        with pytest.raises(ValueError):
            engine.add_evidence(
                claim_id=claim_id, raw_ref_id=1, evidence_type=1, strength=1.5
            )

    def test_rejects_unknown_claim(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.add_evidence(
                claim_id=999, raw_ref_id=1, evidence_type=1, strength=0.5
            )


class TestClaimEvidenceLink:
    def test_evidences_for_claim_returns_all_attached(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_a = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
        )
        claim_b = engine.add_claim(
            subject_id=entity_id, claim_type=2,
            rule_id=1, rule_version=1, reason_code=0,
        )
        engine.add_evidence(claim_id=claim_a, raw_ref_id=1, evidence_type=1, strength=0.4)
        engine.add_evidence(claim_id=claim_a, raw_ref_id=2, evidence_type=1, strength=0.6)
        engine.add_evidence(claim_id=claim_b, raw_ref_id=3, evidence_type=1, strength=0.8)

        attached_to_a = engine.evidences_for_claim(claim_a)
        attached_to_b = engine.evidences_for_claim(claim_b)
        assert len(attached_to_a) == 2
        assert len(attached_to_b) == 1
        assert {ev.raw_ref_id for ev in attached_to_a} == {1, 2}
        assert attached_to_b[0].raw_ref_id == 3

    def test_evidences_for_claim_rejects_unknown_claim(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.evidences_for_claim(claim_id=999)


class TestIdsAreKindIndependent:
    def test_each_kind_starts_at_one(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        obs_id = engine.add_observation(
            entity_id=entity_id, raw_ref_id=1, observation_type=1
        )
        claim_id = engine.add_claim(
            subject_id=entity_id, claim_type=1,
            rule_id=1, rule_version=1, reason_code=0,
        )
        ev_id = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=1, evidence_type=1, strength=0.5
        )
        assert entity_id == 1
        assert obs_id == 1
        assert claim_id == 1
        assert ev_id == 1


class TestRelationAndGapTypes:
    def test_relation_is_frozen_dataclass(self) -> None:
        relation = Relation(id=1, from_id=2, to_id=3, type=4, rule_id=5, reason_code=6)
        assert relation.from_id == 2
        assert relation.to_id == 3
        with pytest.raises(AttributeError):
            relation.from_id = 99  # type: ignore[misc]

    def test_gap_carries_required_evidence_type_and_severity(self) -> None:
        gap = Gap(
            id=1,
            claim_id=2,
            type=3,
            required_evidence_type=42,
            severity=ScoreValue(0.8),
            created_by_rule=7,
        )
        assert gap.required_evidence_type == 42
        assert gap.severity.value == 0.8
        with pytest.raises(AttributeError):
            gap.severity = ScoreValue(0.1)  # type: ignore[misc]
