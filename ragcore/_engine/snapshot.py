"""C10 snapshot façade mixin.

Behaviour-preserving extraction from ragcore.engine.Engine (Phase 3B-9 of the
Engine v1 refactoring; ADR docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md).
The four method bodies, signatures, method-body ASTs, and method docstring texts
are moved verbatim — including the @classmethod decorator and the "Engine"
return-annotation string on from_snapshot; the function / descriptor identities and
declaring locations intentionally change to SnapshotMixin (__module__ /
__qualname__ / declaring class). This is a relocation of stateful ORCHESTRATION
only: the pure serialization / migration / integrity helpers stay in
ragcore._engine.serialization and are neither moved nor modified.

The seventeen persisted stores and the two runtime-only identity fields
(_state_identity_token / _state_revision) are owned by Engine.__init__ and are
reached through self. from_snapshot is an inherited classmethod that constructs via
cls() (so a subclass restores to its own type) and never hard-codes Engine();
to_snapshot delegates to encode_snapshot(self._state_view()); _state_view aliases
the live stores (no copy) and _install replaces the seventeen persisted stores
without touching the runtime identity lineage or advancing the revision. The
load-bearing from_snapshot order — decode/integrity → claim-status admission →
fresh cls() → _install — is preserved. This mixin contributes methods only — no
__init__, no state, no Engine back-reference, no super(), no wrapper/delegation, no
inter-mixin or ragcore.engine import.

Accepted non-contract introspection delta: from_snapshot's "Engine" return
annotation is a forward-reference string resolved against this module's globals;
typing.get_type_hints(Engine.from_snapshot) no longer resolves it here (Engine is
not imported — that would be a cycle). inspect.signature (which preserves the
string verbatim) is the authority; no test or contract depends on the resolved hint.
"""

from __future__ import annotations

from typing import Any

from ragcore._engine import confidence
from ragcore._engine.serialization import (
    DecodedEngineState,
    encode_snapshot,
    validate_and_decode_snapshot,
)


class SnapshotMixin:
    """C10 cluster: the snapshot serialize/restore façade. to_snapshot/_state_view
    project and encode the seventeen Engine-owned persisted stores; from_snapshot
    (an inherited classmethod) decodes + integrity-validates + admits claim status
    + constructs via cls() + installs; _install replaces the persisted stores on a
    fresh instance without touching the runtime identity lineage. All state is
    reached through ``self`` / ``cls`` (Engine MRO)."""

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
