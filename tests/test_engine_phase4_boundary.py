"""Phase 4 — final v1 boundary re-verification.

Locks the *closed* Engine v1 boundary after the Phase-1 serialization compatibility
shim and the stale C9/C10 engine imports were removed: the relocated private
serialization internals are no longer ragcore.engine attributes (they live only at
their real owner), the public import surface is unchanged, the nine-mixin MRO is
exact, the C1 infrastructure stays directly on Engine while no extracted-cluster
method is promoted back, the full C2–C10 ownership map holds (descriptor-aware for
the from_snapshot classmethod), each mixin is a pure stateless contributor, and the
final import graph has no cycles or re-export hubs. Deliberately RUNTIME + AST; no
git SHA is hardcoded here (the two-kernel byte-identity check is a review-material /
dev-record item).
"""

from __future__ import annotations

import ast

import ragcore
import ragcore.engine as engine_module
from ragcore import Engine
from ragcore._engine import confidence, serialization
from ragcore._engine.confidence_adapters import ConfidenceAdaptersMixin
from ragcore._engine.crud import CrudMixin
from ragcore._engine.gaps import GapsMixin
from ragcore._engine.hint_evidence import HintEvidenceMixin
from ragcore._engine.lifecycle import LifecycleMixin
from ragcore._engine.lifecycle_history import LifecycleHistoryMixin
from ragcore._engine.relations import RelationsMixin
from ragcore._engine.rules import RulesMixin
from ragcore._engine.snapshot import SnapshotMixin

# The 26 Phase-1 serialization symbols ragcore.engine used to re-export.
_PHASE1_SERIALIZATION_SHIM_NAMES = (
    "_CURRENT_SNAPSHOT_SCHEMA_VERSION", "_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS",
    "_claim_from_dict", "_entity_from_dict", "_evidence_from_dict", "_gap_from_dict",
    "_migrate_snapshot_to_current", "_migrate_snapshot_v1_to_v2",
    "_observation_from_dict", "_relation_from_dict", "_restore_dict_int",
    "_restore_dict_int_int", "_restore_dict_int_list_dataclass",
    "_restore_dict_int_set", "_restore_dict_tuple", "_restore_dict_tuple4_int",
    "_rule_def_from_dict", "_rule_stats_from_dict", "_serialize_dict_int_dataclass",
    "_serialize_dict_int_int", "_serialize_dict_int_list_dataclass",
    "_serialize_dict_int_set", "_serialize_dict_tuple4_int",
    "_serialize_dict_tuple_dataclass", "_sv_from_dict", "_sv_to_dict",
)
# Stale C9/C10 engine imports removed in Phase 4 (were never public).
_REMOVED_STALE_ENGINE_BINDINGS = (
    "asdict", "Any", "confidence", "DecodedEngineState", "encode_snapshot",
    "validate_and_decode_snapshot",
)

# The nine extracted mixins, in MRO order (after Engine itself).
_MIXINS = (
    ("C8", HintEvidenceMixin), ("C3", RelationsMixin), ("C7", RulesMixin),
    ("C4", GapsMixin), ("C9", ConfidenceAdaptersMixin),
    ("C6", LifecycleHistoryMixin), ("C2", CrudMixin), ("C5", LifecycleMixin),
    ("C10", SnapshotMixin),
)
_MIXIN_ORDER = tuple(m for _, m in _MIXINS)

# C1 infrastructure that stays directly on the Engine base.
_C1_ON_ENGINE = (
    "__init__", "_allocate_id", "_advance_state_revision", "state_identity",
    "_storage_for_kind", "_id_exists", "_assert_entity_exists",
    "_assert_claim_exists", "_assert_evidence_exists", "_assert_gap_exists",
    "_assert_rule_pair_exists", "_assert_rule_stats_pair_exists",
)


def _defining_class(cls, name):
    for base in cls.__mro__:
        if name in base.__dict__:
            return base
    raise AttributeError(name)


def _contributed_methods(mixin):
    return [n for n in mixin.__dict__
            if not n.startswith("__")
            and (callable(mixin.__dict__[n]) or isinstance(mixin.__dict__[n], classmethod))]


def _module_src(mod):
    return open(mod.__file__).read()


def _imported_modules(mod):
    """All module paths imported by `mod` (ImportFrom module + Import names)."""
    out = set()
    for n in ast.walk(ast.parse(_module_src(mod))):
        if isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module)
        elif isinstance(n, ast.Import):
            for a in n.names:
                out.add(a.name)
    return out


# ---- 7.1 shim removal lock -------------------------------------------------
class TestShimRemoval:
    def test_serialization_shim_relocated_not_on_engine(self):
        for name in _PHASE1_SERIALIZATION_SHIM_NAMES:
            assert hasattr(serialization, name), f"serialization lost {name}"
            assert not hasattr(engine_module, name), f"engine still re-exports {name}"

    def test_stale_engine_bindings_removed(self):
        for name in _REMOVED_STALE_ENGINE_BINDINGS:
            assert not hasattr(engine_module, name), f"engine still binds {name}"

    def test_shim_count_is_26(self):
        assert len(_PHASE1_SERIALIZATION_SHIM_NAMES) == 26


# ---- 7.2 public import boundary --------------------------------------------
class TestPublicImportBoundary:
    def test_engine_import_paths(self):
        from ragcore import Engine as E1
        from ragcore.engine import Engine as E2
        assert E1 is E2 is Engine
        assert ragcore.Engine is ragcore.engine.Engine
        assert Engine.__module__ == "ragcore.engine"

    def test_all_is_exactly_50(self):
        assert len(ragcore.__all__) == 50

    def test_private_engine_symbols_not_promoted(self):
        # the relocated privates are not in the public surface.
        for name in _PHASE1_SERIALIZATION_SHIM_NAMES:
            assert name not in ragcore.__all__
            assert not hasattr(ragcore, name)


# ---- 7.3 final MRO boundary ------------------------------------------------
class TestFinalMro:
    def test_bases_are_exactly_nine_mixins(self):
        assert Engine.__bases__ == _MIXIN_ORDER

    def test_mro_prefix_exact(self):
        assert Engine.__mro__[1:10] == _MIXIN_ORDER

    def test_no_duplicate_or_core_mixin(self):
        assert len(set(_MIXIN_ORDER)) == 9
        names = [m.__name__ for m in Engine.__mro__]
        assert "CoreMixin" not in names
        # Engine, 9 mixins, object — no extra stateful mixin.
        assert Engine.__mro__[0] is Engine
        assert Engine.__mro__[-1] is object


# ---- 7.4 C1 retention boundary ---------------------------------------------
class TestC1Retention:
    def test_c1_methods_remain_directly_on_engine(self):
        for name in _C1_ON_ENGINE:
            assert name in Engine.__dict__, f"C1 {name} left the Engine base"

    def test_no_extracted_method_promoted_back(self):
        contributed = set()
        for _, mixin in _MIXINS:
            contributed.update(_contributed_methods(mixin))
        promoted = [n for n in contributed if n in Engine.__dict__]
        assert promoted == [], f"extracted methods promoted onto Engine: {promoted}"

    def test_engine_dict_has_only_c1_callables(self):
        own = [n for n in Engine.__dict__
               if not n.startswith("__") and callable(Engine.__dict__[n])]
        assert set(own) == set(n for n in _C1_ON_ENGINE if not n.startswith("__"))


# ---- 7.5 aggregate ownership -----------------------------------------------
class TestAggregateOwnership:
    def test_every_cluster_method_owned_by_its_mixin(self):
        seen = {}
        for tag, mixin in _MIXINS:
            for name in _contributed_methods(mixin):
                # no duplicate contribution across mixins
                assert name not in seen, f"{name} contributed by {seen[name]} and {tag}"
                seen[name] = tag
                assert name not in Engine.__dict__
                assert _defining_class(Engine, name) is mixin
                raw = mixin.__dict__[name]
                if isinstance(raw, classmethod):
                    assert Engine.from_snapshot.__func__ is raw.__func__
                    assert Engine.from_snapshot.__self__ is Engine
                else:
                    assert getattr(Engine, name) is raw

    def test_from_snapshot_classmethod_subclass_binding(self):
        raw = SnapshotMixin.__dict__["from_snapshot"]
        assert isinstance(raw, classmethod)
        assert "from_snapshot" not in Engine.__dict__

        class DerivedEngine(Engine):
            pass

        e = Engine(); e.add_entity(entity_type=1)
        restored = DerivedEngine.from_snapshot(e.to_snapshot())
        assert type(restored) is DerivedEngine


# ---- 7.6 mixin structure boundary ------------------------------------------
class TestMixinStructure:
    def test_mixins_are_stateless_non_cooperative(self):
        for tag, mixin in _MIXINS:
            # no instance constructor, no state, no inheritance, pure object base.
            assert "__init__" not in mixin.__dict__, f"{tag} has __init__"
            assert mixin.__bases__ == (object,), f"{tag} inherits {mixin.__bases__}"
            mod = __import__(mixin.__module__, fromlist=["x"])
            tree = ast.parse(_module_src(mod))
            # AST (not substring — the docstrings legitimately mention "super()").
            supers = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Name) and n.func.id == "super"]
            assert not supers, f"{tag} calls super()"
            assert "ragcore.engine" not in _imported_modules(mod), \
                f"{tag} imports ragcore.engine"


# ---- 7.7 import graph boundary ---------------------------------------------
class TestImportGraph:
    def test_engine_imports(self):
        mods = _imported_modules(engine_module)
        # only stdlib + ragcore.types + the nine mixin modules.
        mixin_mods = {m.__module__ for _, m in _MIXINS}
        allowed = {"__future__", "uuid", "ragcore.types"} | mixin_mods
        assert mods == allowed, f"unexpected engine imports: {mods - allowed}"
        # the removed kernels are no longer imported by engine.
        assert "ragcore._engine.confidence" not in mods
        assert "ragcore._engine.serialization" not in mods

    def test_pure_kernels_import_exact_sets(self):
        # Exact import sets — a startswith/"." heuristic would let `import numpy`
        # or `import requests` slip through. Lock the precise final boundary.
        assert _imported_modules(serialization) == {
            "__future__", "dataclasses", "typing", "ragcore.types"}
        assert _imported_modules(confidence) == {"__future__", "ragcore.types"}

    def test_snapshot_imports_kernels_not_engine(self):
        import ragcore._engine.snapshot as snap
        tree = ast.parse(_module_src(snap))
        mods = _imported_modules(snap)
        # serialization imported as a module; confidence imported as a name from
        # the ragcore._engine package (AST-precise, not substring).
        assert "ragcore._engine.serialization" in mods
        imports_confidence = any(
            isinstance(n, ast.ImportFrom) and n.module == "ragcore._engine"
            and any(a.name == "confidence" for a in n.names)
            for n in ast.walk(tree))
        assert imports_confidence
        assert "ragcore.engine" not in mods

    def test_no_engine_inversion_or_reexport_hub(self):
        # no ragcore._engine.* module imports ragcore.engine (mixins + kernels +
        # the snapshot façade + the package __init__ itself).
        import ragcore._engine as pkg
        import ragcore._engine.snapshot as snap
        to_check = [__import__(m.__module__, fromlist=["x"]) for _, m in _MIXINS]
        to_check += [serialization, confidence, snap, pkg]
        for mod in to_check:
            assert "ragcore.engine" not in _imported_modules(mod), \
                f"{mod.__name__} imports ragcore.engine (inversion)"
        # ragcore._engine.__init__ is not a re-export hub for the privates.
        for name in _PHASE1_SERIALIZATION_SHIM_NAMES:
            assert not hasattr(pkg, name), f"_engine/__init__ re-exports {name}"
