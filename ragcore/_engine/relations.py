"""C3 relation creation and lookup mixin.

Behaviour-preserving extraction from ragcore.engine.Engine (Phase 3B-2 of the
Engine v1 refactoring; ADR docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md).
The two method bodies are moved verbatim (AST-identical). The store
(``self._relations``) stays on Engine and the C1 seams (``self._id_exists``,
``self._allocate_id``, ``self._advance_state_revision``) stay on the Engine base.
This mixin contributes methods only — no __init__, no state, no Engine
back-reference.
"""

from __future__ import annotations

from ragcore.types import Relation


class RelationsMixin:
    """C3 cluster: cross-kind relation creation + lookup. Methods reach the
    Engine-owned ``self._relations`` store and the C1 reference/id/revision
    seams through ``self`` (resolved via the Engine MRO)."""

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
        """Add a cross-kind Relation linking ``(from_kind, from_id)`` -> ``(to_kind, to_id)``.

        IDs are kind-independent in this framework (entity:1 and claim:1
        are distinct), so a Relation carries both kind discriminators to
        remain unambiguous about what it connects.

        Raises:
            KeyError: unknown from-side or to-side reference.
            ValueError: unknown kind constant (from ``_storage_for_kind``).
        """
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
        self._advance_state_revision()  # PR73-M04 §2.1
        return relation_id

    def get_relation(self, relation_id: int) -> Relation:
        """Return the Relation for ``relation_id``.

        Raises:
            KeyError: unknown relation_id.
        """
        return self._relations[relation_id]
