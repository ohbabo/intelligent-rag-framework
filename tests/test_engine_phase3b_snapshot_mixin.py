"""Phase 3B-9 — runtime contracts for the extracted C10 snapshot-façade mixin.

Locks only what the *extraction* introduces and that the existing persistence /
round-trip / migration / integrity suites do not already cover: that the four C10
methods are inherited from SnapshotMixin yet remain resolvable through Engine with
the public surface unchanged, that the eight previously-merged mixins keep their
declaration order and SnapshotMixin is appended last (9-mixin accumulation), that
from_snapshot stays an inherited classmethod that constructs via cls() (subclass
restores to its own type), that the load-bearing restore order decode → claim-
status admission → fresh cls() → _install is preserved (and no construction happens
on a decode/admission failure), that _state_view aliases the live stores and
_install replaces the seventeen persisted stores without touching the two runtime
identity fields, and that a fully-populated engine round-trips to byte-identical
canonical bytes. Deliberately RUNTIME and location-agnostic; every spy is installed
on the runtime-resolved defining class (descriptor-aware for the classmethod) so
the test leaves Engine.__dict__ unpolluted. The full serialization semantics are
already locked by the existing suite and are NOT re-asserted here.
"""

from __future__ import annotations

import ast
import inspect
import json
import subprocess

import ragcore
import ragcore._engine.snapshot as snapshot_mod
from ragcore import Engine
from ragcore._engine import confidence
from ragcore._engine.confidence_adapters import ConfidenceAdaptersMixin
from ragcore._engine.crud import CrudMixin
from ragcore._engine.gaps import GapsMixin
from ragcore._engine.hint_evidence import HintEvidenceMixin
from ragcore._engine.lifecycle import LifecycleMixin
from ragcore._engine.lifecycle_history import LifecycleHistoryMixin
from ragcore._engine.relations import RelationsMixin
from ragcore._engine.rules import RulesMixin
from ragcore._engine.serialization import DecodedEngineState, validate_and_decode_snapshot
from ragcore._engine.snapshot import SnapshotMixin
from ragcore.types import KIND_CLAIM, KIND_ENTITY, RuleDefinition, ScoreValue

_BASE_SHA = "5ac28babb85ab7412f3382c23b692b1ab42b364f"

_C10 = ("to_snapshot", "_state_view", "from_snapshot", "_install")
_C10_REGULAR = ("to_snapshot", "_state_view", "_install")  # plain instance methods

_PERSISTED_FIELDS = (
    "next_id", "lifecycle_seq", "entities", "observations", "claims", "evidences",
    "relations", "gaps", "rule_definitions", "rule_stats", "gap_dedup_index",
    "claim_gap_refs", "gap_resolutions", "contradictions", "resolved_contradictions",
    "claim_lifecycle_events", "hint_evidence_types",
)  # 17

_EXPECTED_MIXIN_PREFIX = (
    HintEvidenceMixin,
    RelationsMixin,
    RulesMixin,
    GapsMixin,
    ConfidenceAdaptersMixin,
    LifecycleHistoryMixin,
    CrudMixin,
    LifecycleMixin,
    SnapshotMixin,
)


def _defining_class(cls, name):
    for base in cls.__mro__:
        if name in base.__dict__:
            return base
    raise AttributeError(name)


def _rich(e):
    """Populate all 17 persisted stores via the public API."""
    e.register_hint_evidence_types([7, 8])
    e.register_rule(RuleDefinition(id=42, version=1, maturity=0,
                                   prior_confidence=ScoreValue(0.5)))
    e.update_rule_stats(rule_id=42, rule_version=1, firing_delta=3)
    ent = e.add_entity(entity_type=1)
    e.add_observation(entity_id=ent, raw_ref_id=5, observation_type=2)
    c1 = e.add_claim(subject_id=ent, claim_type=1, rule_id=42, rule_version=1,
                     reason_code=0)
    ev1 = e.add_evidence(claim_id=c1, raw_ref_id=0, evidence_type=7, strength=0.9)
    e.register_contradiction(c1, ev1)
    e.register_contradiction_resolution(c1, ev1)
    c2 = e.add_claim(subject_id=ent, claim_type=2, rule_id=42, rule_version=1,
                     reason_code=0)
    e.add_gap(claim_id=c2, gap_type=1, required_evidence_type=42, severity=0.5,
              rule_id=1)
    evg = e.add_evidence(claim_id=c2, raw_ref_id=1, evidence_type=42, strength=0.8)
    e.resolve_gaps_for_evidence(evg)
    c3 = e.add_claim(subject_id=ent, claim_type=3, rule_id=42, rule_version=1,
                     reason_code=0)
    ev3 = e.add_evidence(claim_id=c3, raw_ref_id=2, evidence_type=8, strength=0.95)
    e.register_contradiction(c3, ev3)
    e.refute_claim_if_ready(c3)
    e.add_relation(from_kind=KIND_ENTITY, from_id=ent, to_kind=KIND_CLAIM, to_id=c1,
                   relation_type=1, rule_id=42, reason_code=0)
    return e


def _c10_ast(src, cls):
    out = {}
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.ClassDef) and n.name == cls:
            for f in n.body:
                if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name in _C10:
                    out[f.name] = ast.dump(f, include_attributes=False)
    return out


# ---- 14.1 Composition ------------------------------------------------------
class TestSnapshotComposition:
    def test_mixin_mro_prefix_exact(self):
        assert Engine.__mro__[1:10] == _EXPECTED_MIXIN_PREFIX

    def test_engine_module_path_preserved(self):
        assert Engine.__module__ == "ragcore.engine"
        assert ragcore.Engine is Engine

    def test_public_surface_counts_unchanged(self):
        public = [n for n in dir(Engine)
                  if not n.startswith("_") and callable(getattr(Engine, n))]
        assert len(public) == 42
        assert len(ragcore.__all__) == 50


# ---- 14.2 Ownership (incl. classmethod descriptor) -------------------------
class TestSnapshotOwnership:
    def test_regular_methods_owned_by_mixin_without_promotion(self):
        for name in _C10_REGULAR:
            fn = getattr(Engine, name)
            assert callable(fn)
            assert name not in Engine.__dict__
            assert _defining_class(Engine, name) is SnapshotMixin
            assert getattr(Engine, name) is SnapshotMixin.__dict__[name]
            assert fn.__module__ == "ragcore._engine.snapshot"
            assert fn.__qualname__ == f"SnapshotMixin.{name}"

    def test_from_snapshot_classmethod_descriptor_ownership(self):
        assert "from_snapshot" not in Engine.__dict__
        assert _defining_class(Engine, "from_snapshot") is SnapshotMixin
        raw = SnapshotMixin.__dict__["from_snapshot"]
        assert isinstance(raw, classmethod)
        # bound-method vs raw descriptor are NOT the same object; compare __func__.
        assert Engine.from_snapshot.__func__ is raw.__func__
        assert Engine.from_snapshot.__self__ is Engine
        assert Engine.from_snapshot.__func__.__module__ == "ragcore._engine.snapshot"
        assert Engine.from_snapshot.__func__.__qualname__ == "SnapshotMixin.from_snapshot"

    def test_engine_dict_has_no_c10(self):
        assert [n for n in _C10 if n in Engine.__dict__] == []


# ---- 14.3 Exact signatures -------------------------------------------------
class TestSnapshotSignatures:
    def test_signatures_exact(self):
        assert str(inspect.signature(Engine.to_snapshot)) == "(self) -> 'dict[str, Any]'"
        assert str(inspect.signature(Engine._state_view)) == "(self) -> 'DecodedEngineState'"
        assert str(inspect.signature(Engine._install)) == \
            "(self, decoded: 'DecodedEngineState') -> 'None'"
        # bound classmethod hides cls; the raw __func__ shows it.
        assert str(inspect.signature(Engine.from_snapshot)) == \
            "(snapshot: 'dict[str, Any]') -> \"'Engine'\""
        assert str(inspect.signature(SnapshotMixin.__dict__["from_snapshot"].__func__)) == \
            "(cls, snapshot: 'dict[str, Any]') -> \"'Engine'\""


# ---- 14.4 Getsource + 14.5 AST identity ------------------------------------
class TestSnapshotGetsourceAndAst:
    def test_getsource_real_bodies(self):
        ts = inspect.getsource(Engine.to_snapshot)
        assert "encode_snapshot" in ts and "_state_view" in ts and "super()" not in ts
        sv = inspect.getsource(Engine._state_view)
        assert "DecodedEngineState" in sv
        for f in ("next_id", "claims", "hint_evidence_types"):
            assert f in sv
        fs = inspect.getsource(Engine.from_snapshot)
        assert "@classmethod" in fs
        assert "validate_and_decode_snapshot" in fs
        assert "_validate_claim_status_admission" in fs
        assert "cls()" in fs and "_install" in fs and "super()" not in fs
        inst = inspect.getsource(Engine._install)
        for f in ("self._next_id", "self._hint_evidence_types"):
            assert f in inst
        assert "_state_identity_token" not in inst
        assert "_state_revision" not in inst

    def test_ast_4_of_4_identical_to_baseline(self):
        base = subprocess.check_output(
            ["git", "show", f"{_BASE_SHA}:ragcore/engine.py"]).decode()
        bm = _c10_ast(base, "Engine")
        sm = _c10_ast(open(snapshot_mod.__file__).read(), "SnapshotMixin")
        assert len(bm) == 4 and len(sm) == 4
        for n in _C10:
            assert bm[n] == sm[n], f"AST drift in {n}"
        # the @classmethod decorator survives in the moved AST.
        sn = ast.parse(open(snapshot_mod.__file__).read())
        fs = next(f for c in ast.walk(sn) if isinstance(c, ast.ClassDef)
                  for f in c.body
                  if isinstance(f, ast.FunctionDef) and f.name == "from_snapshot")
        assert [d.id for d in fs.decorator_list] == ["classmethod"]
        assert isinstance(fs.returns, ast.Constant) and fs.returns.value == "Engine"

    def test_no_c10_in_engine_class_body(self):
        import ragcore.engine as engine_mod
        eng = open(engine_mod.__file__).read()
        assert _c10_ast(eng, "Engine") == {}


# ---- 14.6 _state_view exact projection -------------------------------------
class TestStateViewProjection:
    def test_state_view_aliases_live_stores(self):
        e = _rich(Engine())
        before_id = e.state_identity()
        before_snap = e.to_snapshot()
        view = e._state_view()
        assert type(view) is DecodedEngineState
        # 17 persisted fields, each mutable store is the SAME live object.
        assert view.next_id is e._next_id
        assert view.lifecycle_seq == e._lifecycle_seq
        assert view.entities is e._entities
        assert view.observations is e._observations
        assert view.claims is e._claims
        assert view.evidences is e._evidences
        assert view.relations is e._relations
        assert view.gaps is e._gaps
        assert view.rule_definitions is e._rule_definitions
        assert view.rule_stats is e._rule_stats
        assert view.gap_dedup_index is e._gap_dedup_index
        assert view.claim_gap_refs is e._claim_gap_refs
        assert view.gap_resolutions is e._gap_resolutions
        assert view.contradictions is e._contradictions
        assert view.resolved_contradictions is e._resolved_contradictions
        assert view.claim_lifecycle_events is e._claim_lifecycle_events
        assert view.hint_evidence_types is e._hint_evidence_types
        # runtime identity fields are not part of the persisted view.
        assert not hasattr(view, "state_identity_token")
        assert not hasattr(view, "state_revision")
        # read-only.
        assert e.state_identity() == before_id
        assert e.to_snapshot() == before_snap


# ---- 14.7 to_snapshot orchestration ----------------------------------------
class TestToSnapshotOrchestration:
    def test_delegates_to_state_view_then_encode(self, monkeypatch):
        e = _rich(Engine())
        sv_owner = _defining_class(Engine, "_state_view")
        sv_orig = sv_owner.__dict__["_state_view"]
        encode_orig = snapshot_mod.encode_snapshot
        sv_calls, enc_calls = [], []
        sentinel = {"sentinel": True}
        result_obj = {"encoded": True}

        def sv_spy(self):
            sv_calls.append(1)
            return sentinel

        def enc_spy(view):
            enc_calls.append(view)
            return result_obj

        before_id = e.state_identity()
        with monkeypatch.context() as m:
            m.setattr(sv_owner, "_state_view", sv_spy)
            m.setattr(snapshot_mod, "encode_snapshot", enc_spy)
            out = e.to_snapshot()
            assert len(sv_calls) == 1 and len(enc_calls) == 1
            assert enc_calls[0] is sentinel       # encode received exactly _state_view's return
            assert out is result_obj              # to_snapshot returned exactly encode's result
        assert e.state_identity() == before_id    # read-only
        # restored + no promotion.
        assert "_state_view" not in Engine.__dict__
        assert getattr(Engine, "_state_view") is sv_orig
        assert snapshot_mod.encode_snapshot is encode_orig


# ---- 14.8 from_snapshot ordered orchestration ------------------------------
class TestFromSnapshotOrder:
    def test_decode_admit_construct_install_order(self, monkeypatch):
        snap = _rich(Engine()).to_snapshot()

        class DerivedEngine(Engine):
            pass

        events = []
        captured = {}
        decode_orig = snapshot_mod.validate_and_decode_snapshot
        admit_orig = confidence._validate_claim_status_admission
        init_orig = Engine.__init__
        install_owner = _defining_class(Engine, "_install")
        install_orig = install_owner.__dict__["_install"]

        def decode_spy(s):
            d = decode_orig(s)
            captured["decoded"] = d
            events.append("decode")
            return d

        def admit_spy(status):
            events.append("admit")
            return admit_orig(status)

        def init_spy(self, *a, **k):
            events.append("construct")
            return init_orig(self, *a, **k)

        def install_spy(self, decoded):
            events.append("install")
            captured["install_arg"] = decoded
            return install_orig(self, decoded)

        with monkeypatch.context() as m:
            m.setattr(snapshot_mod, "validate_and_decode_snapshot", decode_spy)
            m.setattr(confidence, "_validate_claim_status_admission", admit_spy)
            m.setattr(Engine, "__init__", init_spy)          # __init__ is on the Engine base
            m.setattr(install_owner, "_install", install_spy)
            restored = DerivedEngine.from_snapshot(snap)

        assert type(restored) is DerivedEngine
        i_decode = events.index("decode")
        i_construct = events.index("construct")
        i_install = events.index("install")
        admits = [i for i, ev in enumerate(events) if ev == "admit"]
        assert admits, "snapshot must carry at least one claim to exercise admission"
        # decode first; all admissions after decode and before construction;
        # construction before install; install last.
        assert i_decode < min(admits)
        assert max(admits) < i_construct < i_install
        assert events[-1] == "install"
        # _install received the exact object decode returned.
        assert captured["install_arg"] is captured["decoded"]


# ---- 14.9 failure-before-construction --------------------------------------
class TestFromSnapshotFailureBeforeConstruction:
    def _counters(self, monkeypatch):
        constructs, installs = [], []
        init_orig = Engine.__init__
        install_owner = _defining_class(Engine, "_install")
        install_orig = install_owner.__dict__["_install"]
        monkeypatch.setattr(Engine, "__init__",
                            lambda self, *a, **k: (constructs.append(1),
                                                   init_orig(self, *a, **k))[1])
        monkeypatch.setattr(install_owner, "_install",
                            lambda self, d: (installs.append(1),
                                             install_orig(self, d))[1])
        return constructs, installs

    def test_decode_failure_constructs_nothing(self, monkeypatch):
        constructs, installs = self._counters(monkeypatch)

        def boom(_s):
            raise ValueError("decode boom")
        monkeypatch.setattr(snapshot_mod, "validate_and_decode_snapshot", boom)
        try:
            Engine.from_snapshot({"schema_version": 2})
            raised = False
        except ValueError:
            raised = True
        assert raised
        assert constructs == [] and installs == []

    def test_admission_failure_constructs_nothing(self, monkeypatch):
        snap = _rich(Engine()).to_snapshot()
        constructs, installs = self._counters(monkeypatch)

        def boom(_status):
            raise ValueError("admission boom")
        monkeypatch.setattr(confidence, "_validate_claim_status_admission", boom)
        try:
            Engine.from_snapshot(snap)
            raised = False
        except ValueError:
            raised = True
        assert raised
        assert constructs == [] and installs == []


# ---- 14.10 subclass restore ------------------------------------------------
class TestFromSnapshotSubclass:
    def test_subclass_restores_to_own_type_with_fresh_lineage(self):
        original = _rich(Engine())
        snap = original.to_snapshot()

        class DerivedEngine(Engine):
            pass

        assert DerivedEngine.from_snapshot.__self__ is DerivedEngine
        restored = DerivedEngine.from_snapshot(snap)
        assert type(restored) is DerivedEngine
        # fresh runtime lineage (not carried in the snapshot).
        assert restored.state_identity() != original.state_identity()
        assert restored.to_snapshot() == snap


# ---- 14.11 _install persisted/runtime boundary -----------------------------
class TestInstallBoundary:
    def test_install_replaces_persisted_without_touching_runtime_identity(self):
        decoded = validate_and_decode_snapshot(_rich(Engine()).to_snapshot())
        target = Engine()
        token_before = target._state_identity_token
        revision_before = target._state_revision
        target._install(decoded)
        # 17 persisted stores replaced by the exact decoded objects.
        for f in _PERSISTED_FIELDS:
            assert getattr(target, "_" + f) is getattr(decoded, f)
        # runtime identity untouched, no revision advance.
        assert target._state_identity_token == token_before
        assert target._state_revision == revision_before


# ---- 14.12 full populated round-trip ---------------------------------------
class TestFullRoundTrip:
    def test_byte_identical_canonical_round_trip(self):
        original = _rich(Engine())
        snap = original.to_snapshot()
        restored = Engine.from_snapshot(snap)
        snap2 = restored.to_snapshot()
        assert snap == snap2
        assert json.dumps(snap, sort_keys=True) == json.dumps(snap2, sort_keys=True)
        # key order preserved (not just set equality).
        assert list(snap.keys()) == list(snap2.keys())
        assert snap["schema_version"] == 2
        assert len(snap) == 18
        # every populated store survived.
        for f in _PERSISTED_FIELDS:
            assert getattr(restored, "_" + f) or getattr(restored, "_" + f) == 0


# ---- 14.13 no-promotion (context-closed, regular + classmethod) ------------
class TestSnapshotNoPromotion:
    def test_regular_method_patch_does_not_promote(self, monkeypatch):
        name = "to_snapshot"
        owner = _defining_class(Engine, name)
        original = owner.__dict__[name]
        with monkeypatch.context() as m:
            m.setattr(owner, name, lambda self: original(self))
            assert name not in Engine.__dict__
        assert name not in Engine.__dict__
        assert _defining_class(Engine, name) is SnapshotMixin
        assert getattr(Engine, name) is original

    def test_classmethod_patch_preserves_descriptor(self, monkeypatch):
        owner = _defining_class(Engine, "from_snapshot")
        raw = owner.__dict__["from_snapshot"]
        original_func = raw.__func__

        def spy(cls, snapshot):
            return original_func(cls, snapshot)

        with monkeypatch.context() as m:
            m.setattr(owner, "from_snapshot", classmethod(spy))
            assert "from_snapshot" not in Engine.__dict__
            assert isinstance(owner.__dict__["from_snapshot"], classmethod)
        # restored to the exact original classmethod descriptor.
        restored_raw = owner.__dict__["from_snapshot"]
        assert isinstance(restored_raw, classmethod)
        assert restored_raw is raw
        assert Engine.from_snapshot.__func__ is original_func
        assert "from_snapshot" not in Engine.__dict__
