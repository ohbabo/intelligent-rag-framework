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
    RuleDefinition,
    RuleStats,
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
        self._rule_definitions: dict[tuple[int, int], RuleDefinition] = {}
        self._rule_stats: dict[tuple[int, int], RuleStats] = {}

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

    # ---- Entity / Observation / Claim / Evidence ---------------------------

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
        base_confidence: float = 0.5,
        status: int = CLAIM_STATUS_CANDIDATE,
        flags: int = 0,
    ) -> int:
        """Add a Claim.

        `base_confidence`는 룰 firing 시점의 초기 확신도 (0.0~1.0). 시점
        스냅샷이며 이후 evidence가 들어와도 이 값은 변하지 않는다. 종합
        확신도는 향후 compute_effective_confidence(claim_id) 가 담당.

        `rule_id`/`rule_version`이 등록된 룰을 가리켜야 하는지는 MVP에서
        강제하지 않는다 (advisory). Rule Engine 단계에서 strict 옵션 도입.
        """
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
            base_confidence=ScoreValue(base_confidence),
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

    # ---- Relation / Gap ----------------------------------------------------

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

    # ---- Rule registry -----------------------------------------------------

    def register_rule(self, definition: RuleDefinition) -> None:
        """Register a rule and initialize its stats slot.

        같은 (rule_id, rule_version) 이 두 번 등록되면 ValueError.
        같은 rule_id 라도 version 이 다르면 별개 룰로 취급한다.
        """
        key = (definition.id, definition.version)
        if key in self._rule_definitions:
            raise ValueError(
                f"rule already registered: rule_id={definition.id}, "
                f"version={definition.version}"
            )
        self._rule_definitions[key] = definition
        self._rule_stats[key] = RuleStats(
            rule_id=definition.id, rule_version=definition.version
        )

    def get_rule(self, rule_id: int, rule_version: int) -> RuleDefinition:
        key = (rule_id, rule_version)
        if key not in self._rule_definitions:
            raise KeyError(
                f"unknown rule: rule_id={rule_id}, version={rule_version}"
            )
        return self._rule_definitions[key]

    def get_rule_stats(self, rule_id: int, rule_version: int) -> RuleStats:
        key = (rule_id, rule_version)
        if key not in self._rule_stats:
            raise KeyError(
                f"unknown rule: rule_id={rule_id}, version={rule_version}"
            )
        return self._rule_stats[key]

    def compute_effective_confidence(self, claim_id: int) -> ScoreValue:
        """Current effective confidence for a claim.

        **MVP stub**: returns `base_confidence` unchanged. Phase 2+에서
        evidence_strength 와 RuleStats(observed_precision / false_positive_rate)
        를 조합한다. 이 자리는 의도된 stub이므로 무심코 "고치지" 말 것 —
        scoring 로직은 별도 PR에서 명시적으로 들어온다.
        """
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
        return self._claims[claim_id].base_confidence

    def update_rule_stats(
        self,
        rule_id: int,
        rule_version: int,
        *,
        firing_delta: int = 0,
        true_delta: int = 0,
        false_delta: int = 0,
        observed_precision: ScoreValue | None = None,
        false_positive_rate: ScoreValue | None = None,
    ) -> None:
        """Replace the stored RuleStats with a new instance reflecting deltas.

        기존 객체는 mutate 하지 않는다. 새 RuleStats를 만들어 dict에 교체한다.
        precision/fpr 인자가 None이면 "변경 안 함" (기존 값 유지). 명시적으로
        nullify 하려면 별도 API가 필요 (MVP 미포함).
        """
        key = (rule_id, rule_version)
        if key not in self._rule_stats:
            raise KeyError(
                f"unknown rule: rule_id={rule_id}, version={rule_version}"
            )
        current = self._rule_stats[key]
        self._rule_stats[key] = RuleStats(
            rule_id=current.rule_id,
            rule_version=current.rule_version,
            firing_count=current.firing_count + firing_delta,
            confirmed_true_count=current.confirmed_true_count + true_delta,
            confirmed_false_count=current.confirmed_false_count + false_delta,
            observed_precision=(
                observed_precision
                if observed_precision is not None
                else current.observed_precision
            ),
            false_positive_rate=(
                false_positive_rate
                if false_positive_rate is not None
                else current.false_positive_rate
            ),
        )
