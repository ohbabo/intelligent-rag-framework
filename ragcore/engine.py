"""Engine — owns ID allocation and per-kind storage.

Reference implementation. ID 발급은 kind 별 단조 증가 카운터.
참조 무결성: add_* 메서드는 참조 대상이 (kind, id) 쌍으로 정확히 존재해야 통과.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from ragcore.types import (
    KIND_CLAIM,
    KIND_ENTITY,
    KIND_EVIDENCE,
    KIND_GAP,
    KIND_OBSERVATION,
    KIND_RELATION,
    Claim,
    ClaimLifecycleEvent,
    EngineStateIdentity,
    Entity,
    Evidence,
    Gap,
    Observation,
    Relation,
    RuleDefinition,
    RuleStats,
)

# Phase 2 — the fixed v1 effective-confidence kernel + status admission domain.
# Engine's six _*_modifier_for_claim wrappers collect facts from its stores and
# delegate the arithmetic here; this module reads no Engine state.
from ragcore._engine import confidence
from ragcore._engine.hint_evidence import HintEvidenceMixin
from ragcore._engine.relations import RelationsMixin
from ragcore._engine.rules import RulesMixin
from ragcore._engine.gaps import GapsMixin
from ragcore._engine.confidence_adapters import ConfidenceAdaptersMixin
from ragcore._engine.lifecycle_history import LifecycleHistoryMixin
from ragcore._engine.crud import CrudMixin
from ragcore._engine.lifecycle import LifecycleMixin

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

class Engine(HintEvidenceMixin, RelationsMixin, RulesMixin, GapsMixin, ConfidenceAdaptersMixin, LifecycleHistoryMixin, CrudMixin, LifecycleMixin):
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
