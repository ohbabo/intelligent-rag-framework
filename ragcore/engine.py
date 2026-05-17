"""Engine — owns ID allocation and per-kind storage.

Reference implementation. ID 발급은 kind 별 단조 증가 카운터.
"""

from __future__ import annotations

from ragcore.types import Entity


class Engine:
    def __init__(self) -> None:
        self._next_id: dict[str, int] = {}
        self._entities: dict[int, Entity] = {}

    def _allocate_id(self, kind: str) -> int:
        next_id = self._next_id.get(kind, 0) + 1
        self._next_id[kind] = next_id
        return next_id

    def add_entity(self, entity_type: int, flags: int = 0) -> int:
        entity_id = self._allocate_id("entity")
        self._entities[entity_id] = Entity(id=entity_id, type=entity_type, flags=flags)
        return entity_id

    def get_entity(self, entity_id: int) -> Entity:
        return self._entities[entity_id]
