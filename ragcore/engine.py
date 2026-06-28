"""Engine — owns ID allocation and per-kind storage.

Reference implementation. ID 발급은 kind 별 단조 증가 카운터.
참조 무결성: add_* 메서드는 참조 대상이 (kind, id) 쌍으로 정확히 존재해야 통과.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any
from uuid import uuid4

from ragcore.types import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    KIND_CLAIM,
    KIND_ENTITY,
    KIND_EVIDENCE,
    KIND_GAP,
    KIND_OBSERVATION,
    KIND_RELATION,
    Claim,
    ClaimLifecycleEvent,
    EffectiveConfidenceTrace,
    EngineStateIdentity,
    Entity,
    Evidence,
    Gap,
    Observation,
    Relation,
    RuleDefinition,
    RuleStats,
    ScoreValue,
)

# Phase 2 — the fixed v1 effective-confidence kernel + status admission domain.
# Engine's six _*_modifier_for_claim wrappers collect facts from its stores and
# delegate the arithmetic here; this module reads no Engine state.
from ragcore._engine import confidence
from ragcore._engine.hint_evidence import HintEvidenceMixin
from ragcore._engine.relations import RelationsMixin
from ragcore._engine.rules import RulesMixin

# Phase 1 decode/install boundary — the explicit state-projection surface
# Engine uses for persistence (see ragcore._engine.serialization).
from ragcore._engine.serialization import (
    DecodedEngineState,
    encode_snapshot,
    validate_and_decode_snapshot,
)

# TEMPORARY compatibility shim (Phase 1): the low-level snapshot serialization /
# migration internals were relocated to ragcore._engine.serialization, but
# several existing tests still read them as ragcore.engine attributes
# (e.g. ragcore.engine._migrate_snapshot_to_current). They are re-exported here
# so the relocation stays behavior-preserving. NOT public API (all private).
# These tests should migrate to import from ragcore._engine.serialization, after
# which this shim is removed.
from ragcore._engine.serialization import (  # noqa: F401
    _CURRENT_SNAPSHOT_SCHEMA_VERSION,
    _SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS,
    _claim_from_dict,
    _entity_from_dict,
    _evidence_from_dict,
    _gap_from_dict,
    _migrate_snapshot_to_current,
    _migrate_snapshot_v1_to_v2,
    _observation_from_dict,
    _relation_from_dict,
    _restore_dict_int,
    _restore_dict_int_int,
    _restore_dict_int_list_dataclass,
    _restore_dict_int_set,
    _restore_dict_tuple,
    _restore_dict_tuple4_int,
    _rule_def_from_dict,
    _rule_stats_from_dict,
    _serialize_dict_int_dataclass,
    _serialize_dict_int_int,
    _serialize_dict_int_list_dataclass,
    _serialize_dict_int_set,
    _serialize_dict_tuple4_int,
    _serialize_dict_tuple_dataclass,
    _sv_from_dict,
    _sv_to_dict,
)

# ============================================================================
# Module-level private constant — refutation lifecycle policy
# ----------------------------------------------------------------------------
# Only the refutation-strength threshold remains module-level in engine.py.
# It is a refutation *lifecycle* policy constant (disputed → refuted), NOT part
# of the effective-confidence kernel: the 18 effective-confidence policy
# constants + the status domain moved to ragcore._engine.confidence in Phase 2,
# and the snapshot schema-version constants moved to
# ragcore._engine.serialization in Phase 1. This constant is Engine-internal —
# never exported via __all__, never part of the public API surface
# (PR31-S frozenset).
# ============================================================================

# ---- Refutation helper ----
# PR10-A §22.5 (Sub-decision G): strength-based refutation threshold for
# disputed → refuted. Engine 내부 private — public export 안 함.
# 미래 정책 (freshness / RuleStats / 가중합) 도입 시 자연스럽게 조정/대체.
_REFUTATION_STRENGTH_THRESHOLD = 0.8



# ============================================================================
# class Engine — judgment core (domain-light)
# ----------------------------------------------------------------------------
# Public method layout (section markers below match this order):
#
#   Defensive existence checks (private)
#   Entity / Observation / Claim / Evidence
#   Relation / Gap
#   Gap resolution                       (PR5 §17)
#   Claim lifecycle                      (PR6 §18)
#   Claim refutation                     (PR7 §19)
#   Disputed lifecycle                   (PR8 §20)
#   Disputed resolution                  (PR9-A §21)
#   Disputed refutation                  (PR10-A §22)
#   Lifecycle history                    (PR10-B §23)
#   Evidence freshness                   (PR11-A §25)
#   Freshness-aware refutation           (PR11-B §27)
#   Rule registry
#   Modifier helpers (private)           (PR34-O §46 O2 + O3)
#   Persistence snapshot                 (PR17 §29)
#
# All public methods are part of the PR31-S frozen API surface
# (ragcore.__all__ baseline). Private helpers (_*) may be reorganized
# under PR34-O §46 internal optimization constraints — they do not
# affect the public surface or judgment semantics.
# ============================================================================

class Engine(HintEvidenceMixin, RelationsMixin, RulesMixin):
    # ============================================================================
    # Region B  —  __init__ + private guards
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region B
    # ============================================================================

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
        # PR4 §16 — Gap dedup index + claim↔gap reference index.
        # key = (subject_id, created_by_rule, gap_type, required_evidence_type)
        self._gap_dedup_index: dict[tuple[int, int, int, int], int] = {}
        self._claim_gap_refs: dict[int, set[int]] = {}
        # PR5 §17: gap_id -> evidence_id (first registering, no overwrite).
        self._gap_resolutions: dict[int, int] = {}
        # PR7 §19: claim_id -> set of contradicting evidence_ids.
        self._contradictions: dict[int, set[int]] = {}
        # PR9-A §21: claim_id -> set of resolved evidence_ids (subset of contradictions).
        self._resolved_contradictions: dict[int, set[int]] = {}
        # PR10-B §23: lifecycle history (audit trail of status transitions only).
        # per-engine monotonic counter (NOT timestamp, NOT per-claim).
        self._lifecycle_seq: int = 0
        self._claim_lifecycle_events: dict[int, list[ClaimLifecycleEvent]] = {}
        # PR21-L §33: caller-registered hint evidence type ids.
        # framework 는 Evidence.type 정수 의미를 소유하지 않는다 — caller 가
        # register_hint_evidence_types 로 등록한 set 만 modifier 계산에 사용.
        self._hint_evidence_types: set[int] = set()
        # PR73-M04 §1.1 / §4.1 / §4.2 — per-Engine opaque lineage token + a
        # completed-mutation revision counter. NOT persisted to snapshot
        # (§5); a fresh lineage is allocated on Engine() and on
        # from_snapshot() (§4.4). Public surface: state_identity().
        self._state_identity_token: str = uuid4().hex
        self._state_revision: int = 0

    def _allocate_id(self, kind: str) -> int:
        next_id = self._next_id.get(kind, 0) + 1
        self._next_id[kind] = next_id
        return next_id

    def _advance_state_revision(self) -> None:
        """PR73-M04 §2 — advance the completed-mutation revision counter.

        Called from each state-mutating public method **once** at the
        end of its success path (after the underlying state write).
        Never called from a documented no-op or failure path. Read-only
        public methods (including state_identity itself) never call it.
        """
        self._state_revision += 1

    def state_identity(self) -> EngineStateIdentity:
        """PR73-M04 §1.2 — return the current Engine state identity.

        Read-only. Does not mutate Engine state and does not advance
        ``revision``. The returned value carries this Engine's
        process-local lineage token and the count of completed logical
        state changes that have happened within that lineage.

        Comparison is by value equality. The token is opaque; only
        equality is meaningful for callers. Ordered comparison of
        ``revision`` is consistent with mutation order within the same
        lineage and undefined across lineages. See
        ``docs/architecture/ENGINE_STATE_IDENTITY_PRIMITIVE_CONTRACT.md``.
        """
        return EngineStateIdentity(
            engine_token=self._state_identity_token,
            revision=self._state_revision,
        )

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

    # ---- Defensive existence checks (private — PR34-O §46 O1) -------------
    #
    # Centralize the `if X not in self._storage: raise KeyError(...)` pattern
    # so individual public methods don't repeat it. Each helper preserves the
    # exact error message format the original inline check produced. No
    # behavior change — these are dedup helpers only.

    def _assert_entity_exists(self, entity_id: int) -> None:
        if entity_id not in self._entities:
            raise KeyError(f"unknown entity_id: {entity_id}")

    def _assert_claim_exists(self, claim_id: int) -> None:
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")

    def _assert_evidence_exists(self, evidence_id: int) -> None:
        if evidence_id not in self._evidences:
            raise KeyError(f"unknown evidence_id: {evidence_id}")

    def _assert_gap_exists(self, gap_id: int) -> None:
        if gap_id not in self._gaps:
            raise KeyError(f"unknown gap_id: {gap_id}")

    def _assert_rule_pair_exists(self, rule_id: int, rule_version: int) -> None:
        key = (rule_id, rule_version)
        if key not in self._rule_definitions:
            raise KeyError(
                f"unknown rule: rule_id={rule_id}, version={rule_version}"
            )

    def _assert_rule_stats_pair_exists(self, rule_id: int, rule_version: int) -> None:
        key = (rule_id, rule_version)
        if key not in self._rule_stats:
            raise KeyError(
                f"unknown rule: rule_id={rule_id}, version={rule_version}"
            )

    # ============================================================================
    # Region C  —  CRUD layer (Identity + Evidence + Relation)
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region C
    # ============================================================================

    # ---- Entity / Observation / Claim / Evidence ---------------------------

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

    # ============================================================================
    # Region D  —  Gap layer
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region D
    # ============================================================================

    def add_gap(
        self,
        claim_id: int,
        gap_type: int,
        required_evidence_type: int,
        severity: float,
        rule_id: int,
    ) -> int:
        """Add a Gap or reuse existing one (PR4 §16 dedup).

        dedup key = ``(subject_id, rule_id, gap_type, required_evidence_type)``.

        Dedup hit:
            기존 Gap 의 ``gap_id`` 반환, 새 Gap 생성 안 함.
            ``Gap.claim_id`` / ``severity`` 도 변경 안 함 (최초 등록 시 값 유지).
            현재 호출의 ``claim_id`` 가 그 gap 을 참조하도록 ``_claim_gap_refs`` 갱신.

        Dedup miss:
            기존처럼 새 Gap 생성, ``_gap_dedup_index`` 등록, ``_claim_gap_refs`` 등록.

        Raises:
            KeyError: ``claim_id`` 가 engine 에 없음.
        """
        self._assert_claim_exists(claim_id)

        # severity 검증은 dedup 분기 전에 한다. severity 는 dedup key 가 아니지만,
        # 입력 검증 의미 (ScoreValue 의 [0.0, 1.0] 검증) 는 dedup hit/miss 모두에서
        # 동일하게 적용되어야 한다. dedup hit 시 검증을 건너뛰면 잘못된 severity 가
        # silent pass 됨 — PR4 이전 add_gap 의 입력 검증 의미와 충돌.
        validated_severity = ScoreValue(severity)

        subject_id = self._claims[claim_id].subject_id
        key = (subject_id, rule_id, gap_type, required_evidence_type)

        if key in self._gap_dedup_index:
            existing_gap_id = self._gap_dedup_index[key]
            # PR73-M04 §2.2 — dedup hit advances revision only when
            # the current Claim's _claim_gap_refs entry actually changes.
            refs = self._claim_gap_refs.setdefault(claim_id, set())
            if existing_gap_id not in refs:
                refs.add(existing_gap_id)
                self._advance_state_revision()
            return existing_gap_id

        gap_id = self._allocate_id("gap")
        self._gaps[gap_id] = Gap(
            id=gap_id,
            claim_id=claim_id,  # first registering claim — §16 의미 약화
            type=gap_type,
            required_evidence_type=required_evidence_type,
            severity=validated_severity,
            created_by_rule=rule_id,
        )
        self._gap_dedup_index[key] = gap_id
        self._claim_gap_refs.setdefault(claim_id, set()).add(gap_id)
        self._advance_state_revision()  # PR73-M04 §2.2 (dedup miss)
        return gap_id

    def get_gap(self, gap_id: int) -> Gap:
        """Return the Gap for ``gap_id``.

        Raises:
            KeyError: unknown gap_id.
        """
        return self._gaps[gap_id]

    def gaps_for_claim(self, claim_id: int) -> list[Gap]:
        """Return Gaps this claim references (PR4 §16 의미 확장).

        이전 (Phase 2): ``gap.claim_id == claim_id`` 필터.
        이후 (PR4):    ``_claim_gap_refs[claim_id]`` 기반.

        dedup 으로 reuse 된 gap 도 포함된다. 반환 순서는 gap_id 오름차순
        (결정적).
        """
        self._assert_claim_exists(claim_id)
        gap_ids = self._claim_gap_refs.get(claim_id, set())
        return sorted(
            (self._gaps[gid] for gid in gap_ids),
            key=lambda g: g.id,
        )

    # ---- Gap resolution (PR5 §17) -----------------------------------------

    def resolve_gaps_for_evidence(self, evidence_id: int) -> tuple[int, ...]:
        """Close matching unresolved gaps using the given evidence.

        매칭 규칙: ``gap.required_evidence_type == evidence.type``.
        검사 범위: ``gaps_for_claim(evidence.claim_id)`` — 이 evidence 가 속한
        claim 이 참조하는 gap 들만. created_by_rule 은 매칭 조건에 포함하지 않는다.

        이미 ``_gap_resolutions`` 에 등록된 gap 은 건너뛴다 (first evidence 유지,
        overwrite 금지). 이번 호출에서 새로 resolved 된 gap_id 들만
        gap_id 오름차순 tuple 로 반환한다.

        Raises:
            KeyError: unknown evidence_id.
        """
        self._assert_evidence_exists(evidence_id)
        evidence = self._evidences[evidence_id]
        newly_resolved: list[int] = []
        for gap in self.gaps_for_claim(evidence.claim_id):
            if gap.required_evidence_type != evidence.type:
                continue
            if gap.id in self._gap_resolutions:
                continue
            self._gap_resolutions[gap.id] = evidence_id
            newly_resolved.append(gap.id)
        newly_resolved.sort()
        if newly_resolved:
            self._advance_state_revision()  # PR73-M04 §2.3
        return tuple(newly_resolved)

    def gap_resolution(self, gap_id: int) -> int | None:
        """Return the evidence_id that resolved this gap, or None if unresolved.

        Raises:
            KeyError: unknown gap_id.
        """
        self._assert_gap_exists(gap_id)
        return self._gap_resolutions.get(gap_id)

    # ============================================================================
    # Region E  —  Lifecycle layer (transitions + contradictions)
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region E
    # ============================================================================

    # ---- Claim lifecycle (PR6 §18) ----------------------------------------

    def confirm_claim_if_ready(self, claim_id: int) -> bool:
        """Promote candidate Claim → confirmed if every referenced Gap is resolved.

        전이 조건 (§18.4):
            - ``claim.status == CLAIM_STATUS_CANDIDATE``
            - ``len(gaps_for_claim(claim_id)) >= 1``
            - 모든 gap 에 ``gap_resolution(gap.id) is not None``

        Returns:
            True  — 이번 호출로 candidate → confirmed 전이 발생.
            False — 전이 없음 (조건 불충족 / 이미 confirmed / refuted / Gap 0개).
                    False 는 실패가 아니다 (no-op 도 False).

        Raises:
            KeyError: unknown claim_id.

        Note:
            Resolved 의 truth-source 는 PR5 §17 의 ``_gap_resolutions`` (gap_id →
            evidence_id). Gap dataclass 에는 status 필드가 없다.
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        if claim.status != CLAIM_STATUS_CANDIDATE:
            return False
        gaps = self.gaps_for_claim(claim_id)
        if not gaps:
            return False
        if not all(self.gap_resolution(g.id) is not None for g in gaps):
            return False
        old_status = claim.status
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_CONFIRMED)
        self._record_claim_lifecycle_transition(
            claim_id, old_status, CLAIM_STATUS_CONFIRMED, "confirm_if_ready",
        )
        self._advance_state_revision()  # PR73-M04 §2.4
        return True

    # ---- Claim refutation (PR7 §19) ---------------------------------------

    def register_contradiction(self, claim_id: int, evidence_id: int) -> bool:
        """Register an explicit contradiction relation: evidence contradicts claim.

        Returns:
            True  — 이번 호출로 새로 등록됨.
            False — (claim_id, evidence_id) 가 이미 등록돼 있음 (idempotent no-op).

        Raises:
            KeyError: unknown claim_id or unknown evidence_id.

        Notes (§19.4):
            - Cross-claim 허용: ``evidence.claim_id == claim_id`` 강제 안 함.
            - Target status 무관: confirmed / refuted claim 에도 등록 가능
              (데이터 등록과 lifecycle 결정은 분리).
            - No semantic inference — 호출자 책임.
        """
        self._assert_claim_exists(claim_id)
        self._assert_evidence_exists(evidence_id)
        bucket = self._contradictions.setdefault(claim_id, set())
        if evidence_id in bucket:
            return False
        bucket.add(evidence_id)
        self._advance_state_revision()  # PR73-M04 §2.3
        return True

    def contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]:
        """Return contradicting evidence_ids for the claim.

        Returns:
            evidence_id 오름차순 tuple. 없으면 빈 tuple.

        Raises:
            KeyError: unknown claim_id.
        """
        self._assert_claim_exists(claim_id)
        return tuple(sorted(self._contradictions.get(claim_id, set())))

    def refute_claim_if_ready(self, claim_id: int) -> bool:
        """Transition candidate → refuted if at least one contradiction is registered.

        전이 조건 (§19.5):
            - ``claim.status == CLAIM_STATUS_CANDIDATE``
            - ``len(contradictions_for_claim(claim_id)) >= 1``

        Returns:
            True  — 이번 호출로 candidate → refuted 전이.
            False — 전이 없음 (조건 불충족 / 이미 confirmed / 이미 refuted).

        Raises:
            KeyError: unknown claim_id.

        Note:
            Gap 상태 (unresolved / resolved) 는 이 결정에 영향 없음 — §19.2 핵심
            명제: "증거 부족 ≠ 반박, 반박은 명시적 contradiction 만이 trigger".
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        if claim.status != CLAIM_STATUS_CANDIDATE:
            return False
        if not self._contradictions.get(claim_id):
            return False
        old_status = claim.status
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_REFUTED)
        self._record_claim_lifecycle_transition(
            claim_id, old_status, CLAIM_STATUS_REFUTED, "refute_if_ready",
        )
        self._advance_state_revision()  # PR73-M04 §2.4
        return True

    # ---- Disputed lifecycle (PR8 §20) -------------------------------------

    def dispute_claim_if_ready(self, claim_id: int) -> bool:
        """Transition confirmed → disputed if at least one contradiction is registered.

        전이 조건 (§20.7):
            - ``claim.status == CLAIM_STATUS_CONFIRMED``
            - ``len(contradictions_for_claim(claim_id)) >= 1``

        Returns:
            True  — 이번 호출로 confirmed → disputed 전이.
            False — 전이 없음 (조건 불충족 / 이미 disputed / candidate / refuted).

        Raises:
            KeyError: unknown claim_id.

        Note:
            Disputed 는 confirmed 위에 얹는 격리 상태 (§20.3). candidate /
            refuted 에서 직접 진입 불가. confirmed → refuted 직접 전이 (PR7
            금지) 의 대안 — contradiction 으로 confirmed 가 흔들릴 때 별도
            상태로 격리.
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        if claim.status != CLAIM_STATUS_CONFIRMED:
            return False
        if not self._contradictions.get(claim_id):
            return False
        old_status = claim.status
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_DISPUTED)
        self._record_claim_lifecycle_transition(
            claim_id, old_status, CLAIM_STATUS_DISPUTED, "dispute_if_ready",
        )
        self._advance_state_revision()  # PR73-M04 §2.4
        return True

    # ---- Disputed resolution (PR9-A §21) ----------------------------------

    def register_contradiction_resolution(
        self, claim_id: int, evidence_id: int,
    ) -> bool:
        """Register that this evidence is no longer an active contradiction for this claim.

        Returns:
            True  — 새로 resolved 로 등록됨.
            False — (claim_id, evidence_id) 가 이미 resolved (idempotent no-op).

        Raises:
            KeyError:  unknown claim_id or unknown evidence_id.
            ValueError: (claim_id, evidence_id) 가 ``_contradictions[claim_id]`` 에
                        등록돼 있지 않음 — §21.2 relationship-bound 명제 위반.

        Notes:
            - PR5 first-keep 정신과 일관: 한 번 resolved 면 영구.
            - ``_contradictions`` 원본 entry 는 **삭제하지 않는다** (audit 보존).
            - Target claim status 무관 (데이터 등록, PR7 §19.6 일관).
        """
        self._assert_claim_exists(claim_id)
        self._assert_evidence_exists(evidence_id)
        contras = self._contradictions.get(claim_id, set())
        if evidence_id not in contras:
            raise ValueError(
                f"evidence {evidence_id} is not registered as a contradiction "
                f"for claim {claim_id}"
            )
        resolved = self._resolved_contradictions.setdefault(claim_id, set())
        if evidence_id in resolved:
            return False
        resolved.add(evidence_id)
        self._advance_state_revision()  # PR73-M04 §2.3
        return True

    def resolved_contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]:
        """Return resolved evidence_ids for the claim.

        Returns:
            evidence_id 오름차순 tuple. 없으면 빈 tuple.

        Raises:
            KeyError: unknown claim_id.
        """
        self._assert_claim_exists(claim_id)
        return tuple(sorted(self._resolved_contradictions.get(claim_id, set())))

    def active_contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]:
        """Return contradicting evidence_ids that are still active (not resolved).

        = contradictions_for_claim(c) - resolved_contradictions_for_claim(c)

        Returns:
            evidence_id 오름차순 tuple. status 무관 (모든 status 에서 호출 가능).

        Raises:
            KeyError: unknown claim_id.
        """
        self._assert_claim_exists(claim_id)
        contras = self._contradictions.get(claim_id, set())
        resolved = self._resolved_contradictions.get(claim_id, set())
        return tuple(sorted(contras - resolved))

    def resolve_disputed_claim_if_ready(self, claim_id: int) -> bool:
        """Transition disputed → confirmed if every contradiction is resolved.

        전이 조건 (§21.8):
            - ``claim.status == CLAIM_STATUS_DISPUTED``
            - ``len(active_contradictions_for_claim(claim_id)) == 0``

        Returns:
            True  — 이번 호출로 disputed → confirmed 복귀.
            False — 전이 없음 (status 불일치 / active contradiction 잔존 / no-op).

        Raises:
            KeyError: unknown claim_id.

        Note:
            API 이름 ``resolve_*`` 는 PR10+ 에서 ``disputed → refuted`` 같은
            확장이 들어올 수 있는 자리를 남겨둔 것 (§21.6 Notes).
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        if claim.status != CLAIM_STATUS_DISPUTED:
            return False
        if self.active_contradictions_for_claim(claim_id):
            return False
        old_status = claim.status
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_CONFIRMED)
        self._record_claim_lifecycle_transition(
            claim_id, old_status, CLAIM_STATUS_CONFIRMED, "resolve_disputed_if_ready",
        )
        self._advance_state_revision()  # PR73-M04 §2.4
        return True

    # ---- Disputed refutation (PR10-A §22) ---------------------------------

    def refute_disputed_claim_if_ready(self, claim_id: int) -> bool:
        """Transition disputed → refuted if any active contradiction is strong enough.

        전이 조건 (§22.7):
            - ``claim.status == CLAIM_STATUS_DISPUTED``
            - ``len(active_contradictions_for_claim(claim_id)) >= 1``
            - active contradiction 중 **단 하나라도**
              ``evidence.strength.value >= _REFUTATION_STRENGTH_THRESHOLD`` (= 0.8)

        Returns:
            True  — 이번 호출로 disputed → refuted 전이.
            False — 전이 없음 (status 불일치 / active 없음 / 모두 strength 부족 / no-op).

        Raises:
            KeyError: unknown claim_id.

        Notes:
            - PR9-A 의 ``resolve_disputed_claim_if_ready`` 와 sibling API.
            - **Resolved contradiction 은 판정에서 제외** (§22.7) —
              ``active_contradictions_for_claim`` 만 본다. ``contradictions_for_claim``
              을 직접 보면 안 됨 (PR9-A 의 차집합 의미 정합).
            - PR7 ``refute_claim_if_ready`` (candidate origin) 와는 status guard
              만 다른 sibling. 결과 status 는 같은 ``CLAIM_STATUS_REFUTED``.
              path 구분은 lifecycle history 영역 (PR10-B+).
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        if claim.status != CLAIM_STATUS_DISPUTED:
            return False
        for evidence_id in self.active_contradictions_for_claim(claim_id):
            evidence = self._evidences[evidence_id]
            if evidence.strength.value >= _REFUTATION_STRENGTH_THRESHOLD:
                old_status = claim.status
                self._claims[claim_id] = replace(
                    claim, status=CLAIM_STATUS_REFUTED,
                )
                self._record_claim_lifecycle_transition(
                    claim_id, old_status, CLAIM_STATUS_REFUTED,
                    "refute_disputed_if_ready",
                )
                self._advance_state_revision()  # PR73-M04 §2.4
                return True
        return False

    # ============================================================================
    # Region F  —  Lifecycle history + freshness queries
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region F
    # ============================================================================

    # ---- Lifecycle history (PR10-B §23) -----------------------------------

    def _record_claim_lifecycle_transition(
        self,
        claim_id: int,
        from_status: int,
        to_status: int,
        transition: str,
    ) -> None:
        """Append a lifecycle event. Called by 5 transition APIs on actual transition.

        Public 노출 안 됨 — caller 가 직접 history 를 mutate 할 수 없음 (§23.9
        audit 무결성). 5 lifecycle API 의 ``True`` 반환 직전에만 호출되므로
        no-op (False) 은 절대 기록되지 않음 (§23.5 Sub-decision J).
        """
        self._lifecycle_seq += 1
        event = ClaimLifecycleEvent(
            seq=self._lifecycle_seq,
            claim_id=claim_id,
            from_status=from_status,
            to_status=to_status,
            transition=transition,
        )
        self._claim_lifecycle_events.setdefault(claim_id, []).append(event)

    def claim_lifecycle_history(
        self, claim_id: int,
    ) -> tuple[ClaimLifecycleEvent, ...]:
        """Return lifecycle events for the claim in insertion order.

        Returns:
            ClaimLifecycleEvent 들의 tuple, 발생 순서 (= seq 오름차순).
            Status 변경이 한 번도 없었으면 빈 tuple.

        Raises:
            KeyError: unknown claim_id.

        Note:
            seq 는 engine-local monotonic. 서로 다른 claim 의 history 를 합쳐서
            정렬해도 의미가 있다 (cross-claim 순서 표현).
        """
        self._assert_claim_exists(claim_id)
        return tuple(self._claim_lifecycle_events.get(claim_id, ()))

    # ---- Evidence freshness (PR11-A §25) ----------------------------------

    def evidence_freshness(self, evidence_id: int) -> int:
        """Return the freshness signal of the evidence.

        PR11-A §25.3 — freshness = evidence.id (PR1 _next_id 기반 등록 순서).
        더 큰 값일수록 더 최근 등록.

        Returns:
            evidence.id (= evidence_id 자체).

        Raises:
            KeyError: unknown evidence_id.

        Note:
            wall-clock 안 봄 (PR10-A / PR10-B 정신 일관). engine-local 의미만
            가짐 (cross-engine 비교 무의미).
        """
        self._assert_evidence_exists(evidence_id)
        return evidence_id

    def active_contradictions_by_freshness(
        self, claim_id: int,
    ) -> tuple[int, ...]:
        """Return active contradicting evidence_ids ordered by freshness (most recent first).

        ``active_contradictions_for_claim`` (PR9-A) 와 **같은 set** 이지만
        정렬 키가 다름:
            active_contradictions_for_claim       → evidence_id asc
            active_contradictions_by_freshness    → evidence_id desc (most recent first)

        PR9-A 의 차집합 의미는 그대로 보존 — resolved contradiction 제외.

        Returns:
            active contradicting evidence_ids, evidence_id desc tuple.
            없으면 빈 tuple.

        Raises:
            KeyError: unknown claim_id.
        """
        self._assert_claim_exists(claim_id)
        contras = self._contradictions.get(claim_id, set())
        resolved = self._resolved_contradictions.get(claim_id, set())
        return tuple(sorted(contras - resolved, reverse=True))

    # ============================================================================
    # Region G  —  Freshness-based refute
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region G
    # ============================================================================

    # ---- Freshness-aware refutation (PR11-B §27) --------------------------

    def refute_disputed_claim_if_ready_by_freshness(
        self, claim_id: int,
    ) -> bool:
        """Sibling refute API — inspects most recent active contradiction only.

        PR10-A 의 ``refute_disputed_claim_if_ready`` 와 sibling:

        | API           | inspects                | trigger              |
        |---------------|-------------------------|----------------------|
        | PR10-A refute | ANY active              | any strength >= 0.8  |
        | PR11-B refute | FIRST by freshness only | first strength >= 0.8 |

        같은 status target (REFUTED), 같은 threshold
        (``_REFUTATION_STRENGTH_THRESHOLD = 0.8``, Sub-decision R 재사용),
        다른 input set.

        Returns:
            True  — most_recent active.strength.value >= 0.8 → REFUTED 전이.
            False — 전이 없음.

        Raises:
            KeyError: unknown claim_id.

        Notes:
            - ``active_contradictions_by_freshness(c)[0]`` 만 본다 (Sub-decision Q).
            - True 반환 시 lifecycle event 기록 (transition label
              ``"refute_disputed_by_freshness_if_ready"`` — Sub-decision S).
            - PR10-A ``refute_disputed_claim_if_ready`` 의 의미 / 시그니처
              변경 없음.
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        if claim.status != CLAIM_STATUS_DISPUTED:
            return False
        active = self.active_contradictions_by_freshness(claim_id)
        if not active:
            return False
        most_recent_evidence = self._evidences[active[0]]
        if most_recent_evidence.strength.value >= _REFUTATION_STRENGTH_THRESHOLD:
            old_status = claim.status
            self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_REFUTED)
            self._record_claim_lifecycle_transition(
                claim_id, old_status, CLAIM_STATUS_REFUTED,
                "refute_disputed_by_freshness_if_ready",
            )
            self._advance_state_revision()  # PR73-M04 §2.4
            return True
        return False

    # ============================================================================
    # Region I  —  7-modifier helper layer
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region I
    # ============================================================================

    # ---- Modifier helpers (private — PR34-O §46 O2 + O3) -----------------
    #
    # All 6 modifier helpers share the same signature:
    #     _<name>_modifier_for_claim(self, claim_id: int) -> float
    #
    # status / freshness were inlined in compute_effective_confidence before
    # PR34-O §46 O3 extracted them for symmetry with the existing four
    # (gap / count / rule_stats / evidence_type).

    def _status_modifier_for_claim(self, claim_id: int) -> float:
        """PR11-D §24.8 — status-only multiplier. Engine wrapper: read the
        claim status, delegate to the pure confidence kernel."""
        return confidence.status_modifier(self._claims[claim_id].status)

    def _freshness_modifier_for_claim(self, claim_id: int) -> float:
        """PR11-C §26 — most-recent active contradiction strength weight.
        Engine wrapper: collect the most-recent active strength (None if none),
        delegate to the pure kernel."""
        active = self.active_contradictions_by_freshness(claim_id)
        most_recent_strength = (
            None if not active
            else self._evidences[active[0]].strength.value
        )
        return confidence.freshness_modifier(most_recent_strength)

    def _gap_modifier_for_claim(self, claim_id: int) -> float:
        """PR12-D §28 + PR23-M §35 — count-tier weak attenuation. Engine
        wrapper: count unresolved gaps, delegate to the pure kernel."""
        unresolved_gap_count = sum(
            1
            for gap_id in self._claim_gap_refs.get(claim_id, ())
            if gap_id not in self._gap_resolutions
        )
        return confidence.gap_modifier(unresolved_gap_count)

    def _count_modifier_for_claim(self, claim_id: int) -> float:
        """PR19-E §31 + PR24-N §36 — repeated-pressure strength averaging. Engine
        wrapper: collect active contradiction strengths, delegate to the pure
        kernel. (An empty-strength contradiction is not repeated pressure.)"""
        active = self.active_contradictions_for_claim(claim_id)
        strengths = tuple(
            self._evidences[evidence_id].strength.value
            for evidence_id in active
        )
        return confidence.count_modifier(strengths)

    def _rule_stats_modifier_for_claim(self, claim_id: int) -> float:
        """PR20-F §32 + PR26-R §38 + PR29-R §41 — continuous maturity × bounded
        precision. Engine wrapper: resolve the applicable rule stats (sentinel
        rule id 0 or a lookup miss → no applicable stats → ``firing_count``
        None), then delegate the arithmetic to the pure confidence kernel.
        false_positive_rate is ignored (PR29-R OOS)."""
        claim = self._claims[claim_id]
        if claim.created_by_rule == 0:
            firing_count = None
            observed_precision = None
        else:
            stats = self._rule_stats.get(
                (claim.created_by_rule, claim.created_by_rule_version)
            )
            if stats is None:
                firing_count = None
                observed_precision = None
            else:
                firing_count = stats.firing_count
                observed_precision = (
                    None if stats.observed_precision is None
                    else stats.observed_precision.value
                )
        return confidence.rule_stats_modifier(firing_count, observed_precision)

    def _evidence_type_modifier_for_claim(self, claim_id: int) -> float:
        """PR21-L §33 — weak source-quality signal (NOT truth verdict). Engine
        wrapper: collect the types of DIRECT supporting evidence (Evidence.claim_id
        == claim_id, excluding contradiction / resolved-contradiction evidence),
        then delegate to the pure kernel with the caller-registered hint set."""
        contradicting = self._contradictions.get(claim_id, set())
        resolved = self._resolved_contradictions.get(claim_id, set())
        excluded = contradicting | resolved
        direct_evidence_types = tuple(
            ev.type
            for ev in self._evidences.values()
            if ev.claim_id == claim_id and ev.id not in excluded
        )
        return confidence.evidence_type_modifier(
            direct_evidence_types, self._hint_evidence_types
        )

    # ============================================================================
    # Region J  —  Effective confidence
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region J
    # ============================================================================

    def compute_effective_confidence(self, claim_id: int) -> ScoreValue:
        """Effective confidence as base × status × freshness × gap × count × rule_stats × evidence_type.

        Composition (PR11-D §24 + PR11-C §26 + PR12-D §28 + PR19-E §31 + PR20-F §32 + PR21-L §33):
            effective = base
                      × status_modifier(claim.status)         # PR11-D
                      × freshness_modifier(claim_id)           # PR11-C
                      × gap_modifier(claim_id)                 # PR12-D
                      × count_modifier(claim_id)               # PR19-E
                      × rule_stats_modifier(claim)             # PR20-F
                      × evidence_type_modifier(claim_id)       # PR21-L

        status_modifier (PR11-D §24.3, unchanged):
            candidate / confirmed → 1.0
            disputed → 0.5
            refuted → 0.0

        freshness_modifier (PR11-C §26.3, Sub-decision O — 최신 1개만):
            active = active_contradictions_by_freshness(claim_id)
            if not active: → 1.0
            else: → 1.0 - most_recent.strength.value × _FRESHNESS_PENALTY_WEIGHT

        gap_modifier (PR12-D §28.3 + PR23-M §35.5, Sub-decision AP — count-tier):
            unresolved_count = #{gap in _claim_gap_refs[claim_id] : not in _gap_resolutions}
            0   → _GAP_TIER_ZERO_UNRESOLVED_MODIFIER (1.0)
            1   → _GAP_TIER_ONE_UNRESOLVED_MODIFIER (0.9)
            2   → _GAP_TIER_TWO_UNRESOLVED_MODIFIER (0.8)
            3+  → _GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER (0.7)

        count_modifier (PR19-E §31.3 + PR24-N §36, Sub-decision AV~BB — strength averaging):
            active = active_contradictions_for_claim(claim_id)
            if len(active) < 2: → 1.0 (PR11-C freshness 영역)
            else:
                avg_strength = average(_evidences[ev].strength.value for ev in active)
                → 1.0 - avg_strength × _COUNT_STRENGTH_PENALTY_WEIGHT (0.25)
            # avg 0.0 → 1.0 / avg 0.4 → 0.9 / avg 0.8 → 0.8 (PR19-E 중심점) / avg 1.0 → 0.75
            # 핵심: 빈 강도의 contradiction 은 repeated pressure 가 아니다.

        rule_stats_modifier (PR20-F §32 + PR26-R §38 + PR29-R §41, Sub-decision BK~BQ + A~J):
            if claim.created_by_rule == 0: → 1.0
            elif (rule_id, rule_version) miss: → 1.0
            else:
                # maturity (PR26-R)
                clamped = min(max(firing_count, 0), 2)
                maturity_ratio = clamped / 2
                maturity_modifier = 1.0 - (1.0 - maturity_ratio) × 0.2
                # precision (PR29-R)
                if observed_precision is None:
                    precision_modifier = 1.0
                else:
                    precision_modifier = 0.9 + observed_precision.value × 0.1
                → maturity_modifier × precision_modifier
            # PR26-R maturity: firing 0 → 0.8 / 1 → 0.9 / 2+ → 1.0
            # PR29-R precision: None → 1.0 / p=0.0 → 0.9 / p=0.5 → 0.95 / p=1.0 → 1.0
            # 핵심 (§41.1): Observed precision is a bounded adjustment signal,
            #               not a rule quality verdict.
            # range: [0.72, 1.0] (maturity floor 0.8 × precision floor 0.9)

        evidence_type_modifier (PR21-L §33.13, Sub-decision AA~AE — caller-registered):
            if not self._hint_evidence_types: → 1.0
            direct = [ev for ev in self._evidences if ev.claim_id == claim_id
                      and ev.id not in (_contradictions | _resolved_contradictions)]
            if not direct: → 1.0
            elif all ev.type in self._hint_evidence_types for ev in direct:
                → _EVIDENCE_TYPE_PENALTY_MODIFIER (0.9)
            else: → 1.0

        의미 분리:
            PR11-C: most recent active contradiction strength (1 개 시 단독)
            PR19-E: active contradiction count pressure (2 개 이상 시 추가)
            PR20-F: rule maturity (rule-global 신호)
            PR21-L: direct supporting evidence source-quality (claim-local, caller-registered)

        Returns:
            ScoreValue (effective ≤ base, no boost — §24.5 N / §32.6 X / §33.7 AD).

        Raises:
            KeyError: unknown claim_id.
        """
        # PR76-M07 §6 — delegate to the single private calculation core
        # so the typed-trace API and the legacy API share one formula.
        return self._compute_effective_confidence_core(claim_id).effective_confidence

    def _compute_effective_confidence_core(
        self, claim_id: int,
    ) -> EffectiveConfidenceTrace:
        """PR76-M07 §6 — single calculation core for both confidence APIs.

        Computes each modifier once into a local variable, multiplies them
        together to produce the effective confidence, and packages the
        components into a frozen EffectiveConfidenceTrace value. Both
        ``compute_effective_confidence`` and
        ``compute_effective_confidence_with_trace`` delegate here so the
        composition formula has exactly one site (§6).

        Raises:
            KeyError: unknown claim_id (same surface as the legacy API).
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        status_modifier = self._status_modifier_for_claim(claim_id)
        freshness_modifier = self._freshness_modifier_for_claim(claim_id)
        gap_modifier = self._gap_modifier_for_claim(claim_id)
        count_modifier = self._count_modifier_for_claim(claim_id)
        rule_stats_modifier = self._rule_stats_modifier_for_claim(claim_id)
        evidence_type_modifier = self._evidence_type_modifier_for_claim(claim_id)
        effective_confidence = ScoreValue(
            confidence.compose_effective_confidence(
                claim.base_confidence.value,
                status_modifier,
                freshness_modifier,
                gap_modifier,
                count_modifier,
                rule_stats_modifier,
                evidence_type_modifier,
            )
        )
        return EffectiveConfidenceTrace(
            claim_id=claim_id,
            source_state_identity=self.state_identity(),
            calculation_policy_id=confidence._EFFECTIVE_CONFIDENCE_POLICY_ID,
            base_confidence=claim.base_confidence,
            status_modifier=status_modifier,
            freshness_modifier=freshness_modifier,
            gap_modifier=gap_modifier,
            count_modifier=count_modifier,
            rule_stats_modifier=rule_stats_modifier,
            evidence_type_modifier=evidence_type_modifier,
            effective_confidence=effective_confidence,
        )

    def compute_effective_confidence_with_trace(
        self, claim_id: int,
    ) -> EffectiveConfidenceTrace:
        """PR76-M07 §5 — return a typed breakdown of the same calculation.

        Returns the EffectiveConfidenceTrace value produced by the single
        private calculation core. By construction:

            self.compute_effective_confidence_with_trace(claim_id)
                .effective_confidence
              == self.compute_effective_confidence(claim_id)

        Read-only: does not advance the M04 revision (§5.1 / §11.1) and
        does not mutate snapshot-visible state.

        Raises:
            KeyError: unknown claim_id (same surface as
                ``compute_effective_confidence``).
        """
        return self._compute_effective_confidence_core(claim_id)

    # ============================================================================
    # Region K  —  Snapshot serialize / restore (on Engine)
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region K
    # ============================================================================

    # ---- Persistence snapshot (PR17 §29) ----------------------------------

    def to_snapshot(self) -> dict[str, Any]:
        """Serialize engine state to JSON-compatible dict (PR17 §29).

        결정성 보장 — 같은 engine state → 같은 dict (모든 set/dict iteration
        은 sorted). caller 가 ``json.dumps`` 등으로 영속화 자유.

        Returns:
            JSON-compatible dict with ``schema_version`` + all engine state.
        """
        return encode_snapshot(self._state_view())

    def _state_view(self) -> DecodedEngineState:
        """Project the persisted stores into a DecodedEngineState for encoding.
        Read-only view — the returned object aliases the live stores; encode
        only reads them."""
        return DecodedEngineState(
            next_id=self._next_id,
            lifecycle_seq=self._lifecycle_seq,
            entities=self._entities,
            observations=self._observations,
            claims=self._claims,
            evidences=self._evidences,
            relations=self._relations,
            gaps=self._gaps,
            rule_definitions=self._rule_definitions,
            rule_stats=self._rule_stats,
            gap_dedup_index=self._gap_dedup_index,
            claim_gap_refs=self._claim_gap_refs,
            gap_resolutions=self._gap_resolutions,
            contradictions=self._contradictions,
            resolved_contradictions=self._resolved_contradictions,
            claim_lifecycle_events=self._claim_lifecycle_events,
            hint_evidence_types=self._hint_evidence_types,
        )

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> "Engine":
        """Restore engine from snapshot dict (PR17 §29).

        rule 재실행 / evidence 재평가 / lifecycle 재추론 절대 안 함. 내부
        state 만 그대로 복원.

        Returns:
            New Engine instance with all state restored.

        Raises:
            TypeError: snapshot is not a dict.
            ValueError: missing / unknown schema_version, integrity failure,
                or an invalid claim status.
        """
        # Decode boundary: migrate + integrity-validate + reconstruct into a
        # persisted-state view. No Engine is constructed yet.
        decoded = validate_and_decode_snapshot(snapshot)
        # §51.4 — Engine-specific claim-status admission stays here (it is
        # confidence status-domain, not pure serialization). Reject an invalid
        # status before constructing or populating any Engine state.
        for _claim in decoded.claims.values():
            confidence._validate_claim_status_admission(_claim.status)
        # Install boundary: fresh lineage (cls()) + persisted state.
        engine = cls()
        engine._install(decoded)
        return engine

    def _install(self, decoded: DecodedEngineState) -> None:
        """Install a decoded persisted-state view into this engine. Replaces
        every persisted store; does NOT touch the runtime state-identity lineage
        allocated by __init__ (a fresh lineage is intended on restore)."""
        self._next_id = decoded.next_id
        self._lifecycle_seq = decoded.lifecycle_seq
        self._entities = decoded.entities
        self._observations = decoded.observations
        self._claims = decoded.claims
        self._evidences = decoded.evidences
        self._relations = decoded.relations
        self._gaps = decoded.gaps
        self._rule_definitions = decoded.rule_definitions
        self._rule_stats = decoded.rule_stats
        self._gap_dedup_index = decoded.gap_dedup_index
        self._claim_gap_refs = decoded.claim_gap_refs
        self._gap_resolutions = decoded.gap_resolutions
        self._contradictions = decoded.contradictions
        self._resolved_contradictions = decoded.resolved_contradictions
        self._claim_lifecycle_events = decoded.claim_lifecycle_events
        self._hint_evidence_types = decoded.hint_evidence_types
