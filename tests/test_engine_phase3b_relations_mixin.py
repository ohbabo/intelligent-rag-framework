"""Phase 3B-2 — runtime contracts for the extracted C3 relations mixin.

Locks only what the *extraction* introduces and that the existing suite does not
already cover: that ``add_relation`` / ``get_relation`` are inherited from
``RelationsMixin`` yet remain resolvable / patchable through ``Engine`` with the
public surface unchanged, AND that the previously-merged ``HintEvidenceMixin`` is
still present (the first multi-mixin accumulation check). Deliberately RUNTIME
and location-agnostic (no source-file reads, no line numbers, no
``__bases__`` / MRO exact-order locks, no private-method-count / base-count
locks) so the next Phase-3 mixin can be added without tripping them.

Relation semantics (validation order, fields, revision gate, snapshot) are
already locked by the existing suite and are NOT re-asserted here.
"""

from __future__ import annotations

import inspect

import ragcore
from ragcore import Engine
from ragcore._engine.hint_evidence import HintEvidenceMixin
from ragcore._engine.relations import RelationsMixin
from ragcore.types import KIND_CLAIM, KIND_ENTITY

_C3 = ("add_relation", "get_relation")


class TestRelationsMixinComposition:
    def test_relations_mixin_in_mro(self):
        assert RelationsMixin in Engine.__mro__

    def test_hint_evidence_mixin_still_present(self):
        # Multi-mixin accumulation: the previously-merged mixin is preserved.
        assert HintEvidenceMixin in Engine.__mro__

    def test_engine_module_path_preserved(self):
        assert Engine.__module__ == "ragcore.engine"
        assert ragcore.Engine is Engine

    def test_public_surface_count_unchanged(self):
        public = [n for n in dir(Engine)
                  if not n.startswith("_") and callable(getattr(Engine, n))]
        assert len(public) == 42

    def test_c3_methods_callable_through_engine(self):
        for name in _C3:
            assert callable(getattr(Engine, name))

    def test_c3_methods_declared_on_mixin(self):
        for name in _C3:
            assert name not in Engine.__dict__
            assert getattr(Engine, name).__module__ == "ragcore._engine.relations"

    def test_c3_getsource_returns_real_body(self):
        src = inspect.getsource(Engine.add_relation)
        assert "_id_exists" in src and "_allocate_id" in src
        assert "_advance_state_revision" in src
        assert "super()" not in src


class TestRelationsPublicSignatures:
    _EXPECTED = {
        "add_relation": (
            "(self, from_kind: 'int', from_id: 'int', to_kind: 'int', "
            "to_id: 'int', relation_type: 'int', rule_id: 'int', "
            "reason_code: 'int') -> 'int'"
        ),
        "get_relation": "(self, relation_id: 'int') -> 'Relation'",
    }

    def test_signatures_exact(self):
        for name, expected in self._EXPECTED.items():
            assert str(inspect.signature(getattr(Engine, name))) == expected


class TestRelationsEngineSeams:
    """The C1 reference/id/revision seams stay patchable on Engine after the
    move, and a single normal add_relation exercises them the documented number
    of times (spies installed after setup so only the relation call counts)."""

    def test_c1_seams_monkeypatchable_and_call_counts(self, monkeypatch):
        e = Engine()
        a = e.add_entity(entity_type=1)
        c = e.add_claim(subject_id=a, claim_type=1, rule_id=1, rule_version=1,
                        reason_code=0, base_confidence=0.5)
        counts = {"_id_exists": 0, "_allocate_id": 0, "_advance_state_revision": 0}
        for name in counts:
            original = getattr(Engine, name)

            def make(orig, key):
                def spy(self, *args, **kwargs):
                    counts[key] += 1
                    return orig(self, *args, **kwargs)
                return spy

            monkeypatch.setattr(Engine, name, make(original, name))
        rid = e.add_relation(KIND_ENTITY, a, KIND_CLAIM, c, 7, 1, 0)
        assert counts["_id_exists"] == 2          # from-side + to-side
        assert counts["_allocate_id"] == 1
        assert counts["_advance_state_revision"] == 1
        assert e.get_relation(rid).from_kind == KIND_ENTITY
