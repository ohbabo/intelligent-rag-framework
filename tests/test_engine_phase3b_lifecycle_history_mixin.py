"""Phase 3B-6 — runtime contracts for the extracted C6 lifecycle-history mixin.

Locks only what the *extraction* introduces and that the existing PR6–PR11
lifecycle/history suite does not already cover: that the two C6 methods are
inherited from LifecycleHistoryMixin yet remain resolvable through Engine with the
public surface unchanged, that the five previously-merged mixins are still present
(6-mixin accumulation), that the C5→C6 runtime self-call seam is preserved, and
that the public history reader is read-only. Deliberately RUNTIME and
location-agnostic; the C5→C6 spy is installed on the method's defining class so the
test leaves Engine.__dict__ unpolluted. The full lifecycle/event semantics are
already locked by the existing suite and are NOT re-asserted here.
"""

from __future__ import annotations

import inspect

import ragcore
from ragcore import Engine
from ragcore._engine.confidence_adapters import ConfidenceAdaptersMixin
from ragcore._engine.gaps import GapsMixin
from ragcore._engine.hint_evidence import HintEvidenceMixin
from ragcore._engine.lifecycle_history import LifecycleHistoryMixin
from ragcore._engine.relations import RelationsMixin
from ragcore._engine.rules import RulesMixin
from ragcore.types import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_REFUTED,
    ClaimLifecycleEvent,
)

_C6 = ("_record_claim_lifecycle_transition", "claim_lifecycle_history")

# The prefix-order contract: the five prior mixins keep their declaration order
# and LifecycleHistoryMixin is appended last. This is a prefix SLICE, not the
# full MRO tuple or the base count — a future appended mixin lands at index 7 and
# leaves this slice unchanged, so it does not block later Phase-3 additions.
_EXPECTED_MIXIN_PREFIX = (
    HintEvidenceMixin,
    RelationsMixin,
    RulesMixin,
    GapsMixin,
    ConfidenceAdaptersMixin,
    LifecycleHistoryMixin,
)


def _defining_class(cls, name):
    for base in cls.__mro__:
        if name in base.__dict__:
            return base
    raise AttributeError(name)


def _candidate(e):
    ent = e.add_entity(entity_type=1)
    return e.add_claim(subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
                       reason_code=0, base_confidence=0.7)


class TestLifecycleHistoryComposition:
    def test_mixin_mro_prefix_exact(self):
        # Locks both "the five prior mixins keep their order" and
        # "LifecycleHistoryMixin is appended last".
        assert Engine.__mro__[1:7] == _EXPECTED_MIXIN_PREFIX

    def test_engine_module_path_preserved(self):
        assert Engine.__module__ == "ragcore.engine"
        assert ragcore.Engine is Engine

    def test_public_surface_counts_unchanged(self):
        public = [n for n in dir(Engine)
                  if not n.startswith("_") and callable(getattr(Engine, n))]
        assert len(public) == 42
        assert len(ragcore.__all__) == 50

    def test_c6_methods_owned_by_mixin_without_engine_promotion(self):
        for name in _C6:
            fn = getattr(Engine, name)
            assert callable(fn)
            assert name not in Engine.__dict__
            assert _defining_class(Engine, name) is LifecycleHistoryMixin
            assert getattr(Engine, name) is LifecycleHistoryMixin.__dict__[name]
            assert fn.__module__ == "ragcore._engine.lifecycle_history"
            assert fn.__qualname__ == f"LifecycleHistoryMixin.{name}"

    def test_c6_getsource_returns_real_body(self):
        rec = inspect.getsource(Engine._record_claim_lifecycle_transition)
        assert "_lifecycle_seq" in rec and "ClaimLifecycleEvent" in rec
        assert "super()" not in rec
        hist = inspect.getsource(Engine.claim_lifecycle_history)
        assert "_assert_claim_exists" in hist and "super()" not in hist


class TestLifecycleHistorySignatures:
    _EXPECTED = {
        "_record_claim_lifecycle_transition":
            "(self, claim_id: 'int', from_status: 'int', to_status: 'int', "
            "transition: 'str') -> 'None'",
        "claim_lifecycle_history":
            "(self, claim_id: 'int') -> 'tuple[ClaimLifecycleEvent, ...]'",
    }

    def test_signatures_exact(self):
        for name, expected in self._EXPECTED.items():
            assert str(inspect.signature(getattr(Engine, name))) == expected


class TestLifecycleHistorySeamAndReadOnly:
    def test_c5_to_c6_runtime_self_resolution(self, monkeypatch):
        # A real C5 transition (candidate + contradiction -> refute_if_ready) must
        # reach the inherited C6 recorder via self/MRO. The recorder is spied on
        # its defining class so Engine.__dict__ stays unpolluted.
        e = Engine()
        c = _candidate(e)
        ev = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=42, strength=0.9)
        e.register_contradiction(c, ev)
        calls = []
        name = "_record_claim_lifecycle_transition"
        owner = _defining_class(Engine, name)
        original = owner.__dict__[name]

        def spy(self, claim_id, from_status, to_status, transition):
            calls.append((claim_id, from_status, to_status, transition))
            return original(self, claim_id, from_status, to_status, transition)

        # Close the patch context INSIDE the test so the restoration + the
        # no-promotion result are asserted here (not deferred to fixture teardown).
        with monkeypatch.context() as m:
            m.setattr(owner, name, spy)
            assert e.refute_claim_if_ready(c) is True
            assert name not in Engine.__dict__
            assert _defining_class(Engine, name) is LifecycleHistoryMixin

        # after the patch closes: original identity restored on the defining
        # class, and the inherited method was never promoted onto Engine.
        assert name not in Engine.__dict__
        assert _defining_class(Engine, name) is LifecycleHistoryMixin
        assert getattr(Engine, name) is original
        assert LifecycleHistoryMixin.__dict__[name] is original

        assert len(calls) == 1
        cid, frm, to, label = calls[0]
        assert cid == c
        assert frm == CLAIM_STATUS_CANDIDATE
        assert to == CLAIM_STATUS_REFUTED
        assert label == "refute_if_ready"

    def test_history_reflects_transition(self):
        e = Engine()
        c = _candidate(e)
        ev = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=42, strength=0.9)
        e.register_contradiction(c, ev)
        e.refute_claim_if_ready(c)
        history = e.claim_lifecycle_history(c)
        assert isinstance(history, tuple)
        assert len(history) == 1
        assert isinstance(history[0], ClaimLifecycleEvent)
        assert history[0].transition == "refute_if_ready"

    def test_history_is_read_only(self):
        e = Engine()
        c = _candidate(e)
        ev = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=42, strength=0.9)
        e.register_contradiction(c, ev)
        e.refute_claim_if_ready(c)
        before_identity = e.state_identity()
        before_snapshot = e.to_snapshot()
        e.claim_lifecycle_history(c)
        assert e.state_identity() == before_identity
        assert e.to_snapshot() == before_snapshot

    def test_unknown_claim_raises(self):
        e = Engine()
        before = e.to_snapshot()
        try:
            e.claim_lifecycle_history(99999)
            raised = False
        except KeyError:
            raised = True
        assert raised
        assert e.to_snapshot() == before
