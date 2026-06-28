"""C2 entity / observation / claim / evidence CRUD mixin.

Behaviour-preserving extraction from ragcore.engine.Engine (Phase 3B-7 of the
Engine v1 refactoring; ADR docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md).
The nine method bodies, signatures, method-body ASTs, and method docstring texts
are moved verbatim; the function-object identities and declaring locations
intentionally change to CrudMixin (__module__ / __qualname__ / declaring class).
The four stores (self._entities / self._observations / self._claims /
self._evidences) stay on Engine, and the C1 seams (self._allocate_id /
self._advance_state_revision / self._assert_entity_exists /
self._assert_claim_exists) stay on the Engine base. add_claim keeps its distinct
subject error label ("unknown subject_id (entity): ...") via a direct membership
check (NOT self._assert_entity_exists, which uses an entity_id label) and its
status -> ScoreValue -> id-allocation order. _claims is the one operational
shared-write store: C2 inserts new Claims here and C5 (which stays on Engine in
this phase) replaces their status on the SAME dict via self. This mixin
contributes methods only — no __init__, no state, no Engine back-reference.
"""

from __future__ import annotations

from ragcore._engine import confidence
from ragcore.types import (
    CLAIM_STATUS_CANDIDATE,
    Claim,
    Entity,
    Evidence,
    Observation,
    ScoreValue,
)


class CrudMixin:
    """C2 cluster: entity / observation / claim / evidence creation + lookup.
    Methods write the Engine-owned per-kind stores and use the C1
    id/revision/guard seams through ``self`` (Engine MRO)."""

    def add_entity(self, entity_type: int, flags: int = 0) -> int:
        """Add an Entity (subject of claims) and return its assigned entity_id.

        ``entity_type`` 은 caller-domain 정수. framework 가 의미 미소유.
        """
        entity_id = self._allocate_id("entity")
        self._entities[entity_id] = Entity(id=entity_id, type=entity_type, flags=flags)
        self._advance_state_revision()  # PR73-M04 §2.1
        return entity_id

    def get_entity(self, entity_id: int) -> Entity:
        """Return the Entity for ``entity_id``.

        Raises:
            KeyError: unknown entity_id.
        """
        return self._entities[entity_id]

    def add_observation(
        self,
        entity_id: int,
        raw_ref_id: int,
        observation_type: int,
        source_type: int = 0,
    ) -> int:
        """Add an Observation tied to ``entity_id`` and return its observation_id.

        ``raw_ref_id`` 는 caller-side raw data store 의 식별자. framework 는
        raw 데이터를 들고 있지 않다 (외부 통합 경계 §39).

        Raises:
            KeyError: unknown entity_id.
        """
        self._assert_entity_exists(entity_id)
        obs_id = self._allocate_id("observation")
        self._observations[obs_id] = Observation(
            id=obs_id,
            entity_id=entity_id,
            raw_ref_id=raw_ref_id,
            type=observation_type,
            source_type=source_type,
        )
        self._advance_state_revision()  # PR73-M04 §2.1
        return obs_id

    def get_observation(self, observation_id: int) -> Observation:
        """Return the Observation for ``observation_id``.

        Raises:
            KeyError: unknown observation_id.
        """
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
            # subject_id uses a distinct error label vs add_evidence/add_observation
            # entity_id callers, so keep this inline (helper handles entity_id label).
            raise KeyError(f"unknown subject_id (entity): {subject_id}")
        # §51.3 — reject invalid status before any state mutation.
        confidence._validate_claim_status_admission(status)
        # PR73-M04 §3 C1 — validate base_confidence BEFORE allocating an
        # id so a failed ScoreValue admission cannot consume _next_id
        # while leaving the revision and snapshot unchanged.
        validated_base_confidence = ScoreValue(base_confidence)
        claim_id = self._allocate_id("claim")
        self._claims[claim_id] = Claim(
            id=claim_id,
            subject_id=subject_id,
            type=claim_type,
            status=status,
            created_by_rule=rule_id,
            created_by_rule_version=rule_version,
            reason_code=reason_code,
            base_confidence=validated_base_confidence,
            flags=flags,
        )
        self._advance_state_revision()  # PR73-M04 §2.1
        return claim_id

    def get_claim(self, claim_id: int) -> Claim:
        """Return the Claim for ``claim_id``.

        Read-only: lifecycle 전이를 일으키지 않는다 (§42.3 / §43.9).

        Raises:
            KeyError: unknown claim_id.
        """
        return self._claims[claim_id]

    def add_evidence(
        self,
        claim_id: int,
        raw_ref_id: int,
        evidence_type: int,
        strength: float,
    ) -> int:
        """Add an Evidence supporting ``claim_id`` and return its evidence_id.

        ``evidence_type`` 은 caller-domain 정수 — framework 는 Evidence.type
        의 의미를 소유하지 않는다 (Sub-decision AF). hint 인지 여부는
        ``register_hint_evidence_types`` 로 caller 가 등록한 set 에 의해
        결정 (PR21-L / PR22-S / PR25-T).

        Raises:
            KeyError: unknown claim_id.
        """
        self._assert_claim_exists(claim_id)
        # PR73-M04 §3 C1 — validate strength BEFORE allocating an id so
        # a failed ScoreValue admission cannot consume _next_id while
        # leaving the revision and snapshot unchanged.
        validated_strength = ScoreValue(strength)
        evidence_id = self._allocate_id("evidence")
        self._evidences[evidence_id] = Evidence(
            id=evidence_id,
            claim_id=claim_id,
            raw_ref_id=raw_ref_id,
            type=evidence_type,
            strength=validated_strength,
        )
        self._advance_state_revision()  # PR73-M04 §2.1
        return evidence_id

    def get_evidence(self, evidence_id: int) -> Evidence:
        """Return the Evidence for ``evidence_id``.

        Raises:
            KeyError: unknown evidence_id.
        """
        return self._evidences[evidence_id]

    def evidences_for_claim(self, claim_id: int) -> list[Evidence]:
        """Return all Evidences supporting ``claim_id`` in insertion order.

        contradiction 으로 등록된 evidence 는 별도 ``contradictions_for_claim``
        으로 조회한다 — 같은 evidence_id 가 양쪽에 등록될 수 있다 (PR19 §31).

        Raises:
            KeyError: unknown claim_id.
        """
        self._assert_claim_exists(claim_id)
        return [ev for ev in self._evidences.values() if ev.claim_id == claim_id]
