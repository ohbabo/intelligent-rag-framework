"""Engine — owns ID allocation and per-kind storage.

Reference implementation. ID 발급은 kind 별 단조 증가 카운터.
참조 무결성: add_* 메서드는 참조 대상이 (kind, id) 쌍으로 정확히 존재해야 통과.
"""

from __future__ import annotations

from ragcore.types import (
    CLAIM_STATUS_CANDIDATE,
    KIND_CLAIM,
    KIND_ENTITY,
    KIND_EVIDENCE,
    KIND_GAP,
    KIND_OBSERVATION,
    KIND_RELATION,
    Claim,
    Entity,
    Evidence,
    Gap,
    Observation,
    Relation,
    ScoreValue,
)


class Engine:
    def __init__(self) -> None:
        self._next_id: dict[str, int] = {}
        self._entities: dict[int, Entity] = {}
        self._observations: dict[int, Observation] = {}
        self._claims: dict[int, Claim] = {}
        self._evidences: dict[int, Evidence] = {}
        self._relations: dict[int, Relation] = {}
        self._gaps: dict[int, Gap] = {}

    def _allocate_id(self, kind: str) -> int:
        next_id = self._next_id.get(kind, 0) + 1
        self._next_id[kind] = next_id
        return next_id

    def _storage_for_kind(self, kind: int) -> dict[int, object]:
        mapping: dict[int, dict[int, object]] = {
            KIND_ENTITY: self._entities,  # type: ignore[dict-item]
            KIND_OBSERVATION: self._observations,  # type: ignore[dict-item]
            KIND_CLAIM: self._claims,  # type: ignore[dict-item]
            KIND_EVIDENCE: self._evidences,  # type: ignore[dict-item]
            KIND_RELATION: self._relations,  # type: ignore[dict-item]
            KIND_GAP: self._gaps,  # type: ignore[dict-item]
        }
        if kind not in mapping:
            raise ValueError(f"unknown kind: {kind}")
        return mapping[kind]

    def _id_exists(self, kind: int, target_id: int) -> bool:
        return target_id in self._storage_for_kind(kind)

    def add_entity(self, entity_type: int, flags: int = 0) -> int:
        entity_id = self._allocate_id("entity")
        self._entities[entity_id] = Entity(id=entity_id, type=entity_type, flags=flags)
        return entity_id

    def get_entity(self, entity_id: int) -> Entity:
        return self._entities[entity_id]

    def add_observation(
        self,
        entity_id: int,
        raw_ref_id: int,
        observation_type: int,
        source_type: int = 0,
    ) -> int:
        if entity_id not in self._entities:
            raise KeyError(f"unknown entity_id: {entity_id}")
        obs_id = self._allocate_id("observation")
        self._observations[obs_id] = Observation(
            id=obs_id,
            entity_id=entity_id,
            raw_ref_id=raw_ref_id,
            type=observation_type,
            source_type=source_type,
        )
        return obs_id

    def get_observation(self, observation_id: int) -> Observation:
        return self._observations[observation_id]

    def add_claim(
        self,
        subject_id: int,
        claim_type: int,
        rule_id: int,
        rule_version: int,
        reason_code: int,
        *,
        status: int = CLAIM_STATUS_CANDIDATE,
        flags: int = 0,
    ) -> int:
        if subject_id not in self._entities:
            raise KeyError(f"unknown subject_id (entity): {subject_id}")
        claim_id = self._allocate_id("claim")
        self._claims[claim_id] = Claim(
            id=claim_id,
            subject_id=subject_id,
            type=claim_type,
            status=status,
            created_by_rule=rule_id,
            created_by_rule_version=rule_version,
            reason_code=reason_code,
            flags=flags,
        )
        return claim_id

    def get_claim(self, claim_id: int) -> Claim:
        return self._claims[claim_id]

    def add_evidence(
        self,
        claim_id: int,
        raw_ref_id: int,
        evidence_type: int,
        strength: float,
    ) -> int:
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
        evidence_id = self._allocate_id("evidence")
        self._evidences[evidence_id] = Evidence(
            id=evidence_id,
            claim_id=claim_id,
            raw_ref_id=raw_ref_id,
            type=evidence_type,
            strength=ScoreValue(strength),
        )
        return evidence_id

    def get_evidence(self, evidence_id: int) -> Evidence:
        return self._evidences[evidence_id]

    def evidences_for_claim(self, claim_id: int) -> list[Evidence]:
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
        return [ev for ev in self._evidences.values() if ev.claim_id == claim_id]

    def add_relation(
        self,
        from_kind: int,
        from_id: int,
        to_kind: int,
        to_id: int,
        relation_type: int,
        rule_id: int,
        reason_code: int,
    ) -> int:
        # _storage_for_kind raises ValueError on unknown kind.
        if not self._id_exists(from_kind, from_id):
            raise KeyError(
                f"unknown from reference: kind={from_kind}, id={from_id}"
            )
        if not self._id_exists(to_kind, to_id):
            raise KeyError(
                f"unknown to reference: kind={to_kind}, id={to_id}"
            )
        relation_id = self._allocate_id("relation")
        self._relations[relation_id] = Relation(
            id=relation_id,
            from_kind=from_kind,
            from_id=from_id,
            to_kind=to_kind,
            to_id=to_id,
            type=relation_type,
            rule_id=rule_id,
            reason_code=reason_code,
        )
        return relation_id

    def get_relation(self, relation_id: int) -> Relation:
        return self._relations[relation_id]

    def add_gap(
        self,
        claim_id: int,
        gap_type: int,
        required_evidence_type: int,
        severity: float,
        rule_id: int,
    ) -> int:
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
        gap_id = self._allocate_id("gap")
        self._gaps[gap_id] = Gap(
            id=gap_id,
            claim_id=claim_id,
            type=gap_type,
            required_evidence_type=required_evidence_type,
            severity=ScoreValue(severity),
            created_by_rule=rule_id,
        )
        return gap_id

    def get_gap(self, gap_id: int) -> Gap:
        return self._gaps[gap_id]

    def gaps_for_claim(self, claim_id: int) -> list[Gap]:
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
        return [g for g in self._gaps.values() if g.claim_id == claim_id]
