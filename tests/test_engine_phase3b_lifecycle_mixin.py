"""Phase 3B-8 — runtime contracts for the extracted C5 lifecycle-transition +
contradiction-state mixin.

Locks only what the *extraction* introduces and that the existing lifecycle /
contradiction / disputed / freshness suites do not already cover: that the twelve
C5 methods are inherited from LifecycleMixin yet remain resolvable through Engine
with the public surface unchanged, that the seven previously-merged mixins keep
their declaration order and LifecycleMixin is appended last (8-mixin accumulation),
that the C5 transitions still reach the C1 revision/guard seams, the C4 gap
queries, and the C6 lifecycle recorder through self/MRO, that the C9 confidence
adapters still reach the C5 active-contradiction queries, that the load-bearing
status-replace -> lifecycle-record -> revision-advance order is preserved, and that
the C5 inserts/replacements and the C2 CRUD operate on the same Engine-owned
_claims dict. Deliberately RUNTIME and location-agnostic; every spy is installed on
the method's defining class so the test leaves Engine.__dict__ unpolluted. The full
transition / contradiction / threshold semantics are already locked by the existing
suite and are NOT re-asserted here.
"""

from __future__ import annotations

import inspect

import ragcore
from ragcore import Engine
from ragcore._engine.confidence_adapters import ConfidenceAdaptersMixin
from ragcore._engine.crud import CrudMixin
from ragcore._engine.gaps import GapsMixin
from ragcore._engine.hint_evidence import HintEvidenceMixin
from ragcore._engine.lifecycle import LifecycleMixin
from ragcore._engine.lifecycle_history import LifecycleHistoryMixin
from ragcore._engine.relations import RelationsMixin
from ragcore._engine.rules import RulesMixin
from ragcore.types import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
)

_C5 = (
    "confirm_claim_if_ready",
    "register_contradiction",
    "contradictions_for_claim",
    "refute_claim_if_ready",
    "dispute_claim_if_ready",
    "register_contradiction_resolution",
    "resolved_contradictions_for_claim",
    "active_contradictions_for_claim",
    "resolve_disputed_claim_if_ready",
    "refute_disputed_claim_if_ready",
    "active_contradictions_by_freshness",
    "refute_disputed_claim_if_ready_by_freshness",
)
_C5_MUTATORS = (
    "confirm_claim_if_ready",
    "register_contradiction",
    "refute_claim_if_ready",
    "dispute_claim_if_ready",
    "register_contradiction_resolution",
    "resolve_disputed_claim_if_ready",
    "refute_disputed_claim_if_ready",
    "refute_disputed_claim_if_ready_by_freshness",
)
_C5_READERS = (
    "contradictions_for_claim",
    "resolved_contradictions_for_claim",
    "active_contradictions_for_claim",
    "active_contradictions_by_freshness",
)

# The prefix-order contract: the seven prior mixins keep their declaration order
# and LifecycleMixin is appended last. This is a prefix SLICE, not the full MRO
# tuple or the base count — a future appended mixin lands at index 9 and leaves
# this slice unchanged, so it does not block later additions.
_EXPECTED_MIXIN_PREFIX = (
    HintEvidenceMixin,
    RelationsMixin,
    RulesMixin,
    GapsMixin,
    ConfidenceAdaptersMixin,
    LifecycleHistoryMixin,
    CrudMixin,
    LifecycleMixin,
)


def _defining_class(cls, name):
    for base in cls.__mro__:
        if name in base.__dict__:
            return base
    raise AttributeError(name)


# ---------------------------------------------------------------------------
# state builders (use only public Engine API)
# ---------------------------------------------------------------------------
def _candidate(e):
    ent = e.add_entity(entity_type=1)
    return e.add_claim(subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
                       reason_code=0)


def _ready_confirm(e):
    """candidate claim with a single resolved gap — ready to confirm."""
    c = _candidate(e)
    e.add_gap(claim_id=c, gap_type=1, required_evidence_type=42, severity=0.5,
              rule_id=1)
    ev = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=42, strength=0.8)
    e.resolve_gaps_for_evidence(ev)
    return c


def _make_confirmed(e):
    c = _ready_confirm(e)
    assert e.confirm_claim_if_ready(c) is True
    return c


def _ready_refute(e):
    """candidate claim with a registered contradiction — ready to refute."""
    c = _candidate(e)
    ev = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=7, strength=0.9)
    e.register_contradiction(c, ev)
    return c


def _ready_dispute(e):
    """confirmed claim with a registered contradiction — ready to dispute."""
    c = _make_confirmed(e)
    ev = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=7, strength=0.9)
    e.register_contradiction(c, ev)
    return c


def _make_disputed(e, strength=0.9):
    """disputed claim carrying one strong active contradiction; returns (c, ev)."""
    c = _ready_dispute(e)
    # the contradiction registered by _ready_dispute is the active one; recover it.
    ev = e.active_contradictions_for_claim(c)[0]
    assert e._evidences[ev].strength.value == strength
    assert e.dispute_claim_if_ready(c) is True
    return c, ev


def _ready_resolve_disputed(e):
    """disputed claim whose only contradiction is resolved — ready to resolve."""
    c, ev = _make_disputed(e)
    e.register_contradiction_resolution(c, ev)
    return c


class TestLifecycleComposition:
    def test_mixin_mro_prefix_exact(self):
        assert Engine.__mro__[1:9] == _EXPECTED_MIXIN_PREFIX

    def test_engine_module_path_preserved(self):
        assert Engine.__module__ == "ragcore.engine"
        assert ragcore.Engine is Engine

    def test_public_surface_counts_unchanged(self):
        public = [n for n in dir(Engine)
                  if not n.startswith("_") and callable(getattr(Engine, n))]
        assert len(public) == 42
        assert len(ragcore.__all__) == 50

    def test_c5_methods_owned_by_mixin_without_engine_promotion(self):
        assert len(_C5) == 12
        for name in _C5:
            fn = getattr(Engine, name)
            assert callable(fn)
            assert name not in Engine.__dict__
            assert _defining_class(Engine, name) is LifecycleMixin
            assert getattr(Engine, name) is LifecycleMixin.__dict__[name]
            assert fn.__module__ == "ragcore._engine.lifecycle"
            assert fn.__qualname__ == f"LifecycleMixin.{name}"

    def test_threshold_single_private_authority(self):
        # The refutation threshold moved with the two refute APIs; one authority,
        # value 0.8, private, never publicly exported.
        from ragcore._engine.lifecycle import _REFUTATION_STRENGTH_THRESHOLD
        assert _REFUTATION_STRENGTH_THRESHOLD == 0.8
        import ragcore.engine as engmod
        assert not hasattr(engmod, "_REFUTATION_STRENGTH_THRESHOLD")
        assert not hasattr(ragcore, "_REFUTATION_STRENGTH_THRESHOLD")
        assert not hasattr(ragcore.types, "_REFUTATION_STRENGTH_THRESHOLD")

    def test_c5_getsource_returns_real_bodies(self):
        conf = inspect.getsource(Engine.confirm_claim_if_ready)
        assert "gaps_for_claim" in conf and "replace" in conf and "super()" not in conf
        res = inspect.getsource(Engine.register_contradiction_resolution)
        assert "is not registered as a contradiction" in res and "super()" not in res
        rd = inspect.getsource(Engine.refute_disputed_claim_if_ready)
        assert "_REFUTATION_STRENGTH_THRESHOLD" in rd and "active_contradictions_for_claim" in rd
        rf = inspect.getsource(Engine.refute_disputed_claim_if_ready_by_freshness)
        assert "active_contradictions_by_freshness" in rf and "[0]" in rf


class TestLifecycleSignatures:
    _EXPECTED = {
        "confirm_claim_if_ready": "(self, claim_id: 'int') -> 'bool'",
        "register_contradiction":
            "(self, claim_id: 'int', evidence_id: 'int') -> 'bool'",
        "contradictions_for_claim": "(self, claim_id: 'int') -> 'tuple[int, ...]'",
        "refute_claim_if_ready": "(self, claim_id: 'int') -> 'bool'",
        "dispute_claim_if_ready": "(self, claim_id: 'int') -> 'bool'",
        "register_contradiction_resolution":
            "(self, claim_id: 'int', evidence_id: 'int') -> 'bool'",
        "resolved_contradictions_for_claim":
            "(self, claim_id: 'int') -> 'tuple[int, ...]'",
        "active_contradictions_for_claim":
            "(self, claim_id: 'int') -> 'tuple[int, ...]'",
        "resolve_disputed_claim_if_ready": "(self, claim_id: 'int') -> 'bool'",
        "refute_disputed_claim_if_ready": "(self, claim_id: 'int') -> 'bool'",
        "active_contradictions_by_freshness":
            "(self, claim_id: 'int') -> 'tuple[int, ...]'",
        "refute_disputed_claim_if_ready_by_freshness":
            "(self, claim_id: 'int') -> 'bool'",
    }

    def test_signatures_exact(self):
        assert set(self._EXPECTED) == set(_C5)
        for name, expected in self._EXPECTED.items():
            assert str(inspect.signature(getattr(Engine, name))) == expected


class TestLifecycleC4Seam:
    def test_confirm_reaches_c4_queries_via_self(self, monkeypatch):
        e = Engine()
        c = _ready_confirm(e)
        gaps_owner = _defining_class(Engine, "gaps_for_claim")
        res_owner = _defining_class(Engine, "gap_resolution")
        assert gaps_owner is GapsMixin and res_owner is GapsMixin
        gaps_orig = gaps_owner.__dict__["gaps_for_claim"]
        res_orig = res_owner.__dict__["gap_resolution"]
        gaps_calls, res_calls = [], []

        def gaps_spy(self, claim_id):
            gaps_calls.append(claim_id)
            return gaps_orig(self, claim_id)

        def res_spy(self, gap_id):
            res_calls.append(gap_id)
            return res_orig(self, gap_id)

        with monkeypatch.context() as m:
            m.setattr(gaps_owner, "gaps_for_claim", gaps_spy)
            m.setattr(res_owner, "gap_resolution", res_spy)
            assert e.confirm_claim_if_ready(c) is True
            assert e.get_claim(c).status == CLAIM_STATUS_CONFIRMED
            assert len(gaps_calls) == 1
            assert len(res_calls) == 1  # single gap

        for name, owner, orig in (("gaps_for_claim", gaps_owner, gaps_orig),
                                  ("gap_resolution", res_owner, res_orig)):
            assert name not in Engine.__dict__
            assert _defining_class(Engine, name) is GapsMixin
            assert getattr(Engine, name) is orig


class TestLifecycleC6Seam:
    # (builder, transition method, from_status, to_status, label) for all six.
    _CASES = [
        (_ready_confirm, "confirm_claim_if_ready",
         CLAIM_STATUS_CANDIDATE, CLAIM_STATUS_CONFIRMED, "confirm_if_ready"),
        (_ready_refute, "refute_claim_if_ready",
         CLAIM_STATUS_CANDIDATE, CLAIM_STATUS_REFUTED, "refute_if_ready"),
        (_ready_dispute, "dispute_claim_if_ready",
         CLAIM_STATUS_CONFIRMED, CLAIM_STATUS_DISPUTED, "dispute_if_ready"),
        (_ready_resolve_disputed, "resolve_disputed_claim_if_ready",
         CLAIM_STATUS_DISPUTED, CLAIM_STATUS_CONFIRMED, "resolve_disputed_if_ready"),
        (lambda e: _make_disputed(e)[0], "refute_disputed_claim_if_ready",
         CLAIM_STATUS_DISPUTED, CLAIM_STATUS_REFUTED, "refute_disputed_if_ready"),
        (lambda e: _make_disputed(e)[0], "refute_disputed_claim_if_ready_by_freshness",
         CLAIM_STATUS_DISPUTED, CLAIM_STATUS_REFUTED,
         "refute_disputed_by_freshness_if_ready"),
    ]

    def test_six_transitions_record_via_c6_in_order(self, monkeypatch):
        rec_owner = _defining_class(Engine, "_record_claim_lifecycle_transition")
        assert rec_owner is LifecycleHistoryMixin
        rec_orig = rec_owner.__dict__["_record_claim_lifecycle_transition"]
        recorded_labels = []

        for builder, method, frm, to, label in self._CASES:
            e = Engine()
            c = builder(e)
            # pre-state must be the documented origin status for this transition.
            assert e.get_claim(c).status == frm
            rev_before = e.state_identity().revision
            calls = []

            def spy(self, claim_id, from_status, to_status, transition,
                    _calls=calls, _rev=rev_before):
                # status was already replaced; revision not yet advanced.
                assert self._claims[claim_id].status == to_status
                assert self._state_revision == _rev
                _calls.append((claim_id, from_status, to_status, transition))
                return rec_orig(self, claim_id, from_status, to_status, transition)

            with monkeypatch.context() as mp:
                mp.setattr(rec_owner, "_record_claim_lifecycle_transition", spy)
                assert getattr(e, method)(c) is True
                assert len(calls) == 1
                cid, f, t, lab = calls[0]
                assert (cid, f, t, lab) == (c, frm, to, label)
                # revision advanced exactly once, after the record.
                assert e.state_identity().revision == rev_before + 1
            recorded_labels.append(label)

            # context closed: recorder restored, no Engine promotion.
            assert "_record_claim_lifecycle_transition" not in Engine.__dict__
            assert _defining_class(Engine, "_record_claim_lifecycle_transition") is \
                LifecycleHistoryMixin
            assert getattr(Engine, "_record_claim_lifecycle_transition") is rec_orig

        assert len(recorded_labels) == 6
        assert len(set(recorded_labels)) == 6


class TestLifecycleC1RevisionGate:
    def test_revision_advances_only_on_real_state_change(self, monkeypatch):
        owner = _defining_class(Engine, "_advance_state_revision")
        assert owner is Engine
        orig = owner.__dict__["_advance_state_revision"]

        def rev(e, op):
            calls = []

            def spy(self, _c=calls):
                _c.append(1)
                return orig(self)
            with monkeypatch.context() as m:
                m.setattr(owner, "_advance_state_revision", spy)
                op()
            return len(calls)

        # register_contradiction: new +1, duplicate +0
        e = Engine(); c = _candidate(e)
        ev = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=7, strength=0.9)
        assert rev(e, lambda: e.register_contradiction(c, ev)) == 1
        assert rev(e, lambda: e.register_contradiction(c, ev)) == 0

        # register_contradiction_resolution: new +1, duplicate +0, invalid +0
        assert rev(e, lambda: e.register_contradiction_resolution(c, ev)) == 1
        assert rev(e, lambda: e.register_contradiction_resolution(c, ev)) == 0
        ev_other = e.add_evidence(claim_id=c, raw_ref_id=1, evidence_type=7,
                                  strength=0.1)
        # ev_other is not a registered contradiction -> ValueError, no revision.
        def _invalid():
            try:
                e.register_contradiction_resolution(c, ev_other)
            except ValueError:
                pass
        assert rev(e, _invalid) == 0

        # successful status transition +1, repeated no-op +0
        e2 = Engine(); c2 = _ready_refute(e2)
        assert rev(e2, lambda: e2.refute_claim_if_ready(c2)) == 1
        assert rev(e2, lambda: e2.refute_claim_if_ready(c2)) == 0


class TestLifecycleC9IncomingSeam:
    def test_c9_modifiers_reach_c5_active_queries(self, monkeypatch):
        for c5_name, c9_private in (
            ("active_contradictions_for_claim", "_count_modifier_for_claim"),
            ("active_contradictions_by_freshness", "_freshness_modifier_for_claim"),
        ):
            owner = _defining_class(Engine, c5_name)
            assert owner is LifecycleMixin
            orig = owner.__dict__[c5_name]
            e = Engine()
            c, _ev = _make_disputed(e)
            calls = []

            def spy(self, claim_id, _o=orig, _c=calls):
                _c.append(claim_id)
                return _o(self, claim_id)

            with monkeypatch.context() as m:
                m.setattr(owner, c5_name, spy)
                getattr(e, c9_private)(c)
                assert len(calls) == 1

            assert c5_name not in Engine.__dict__
            assert _defining_class(Engine, c5_name) is LifecycleMixin
            assert getattr(Engine, c5_name) is orig


class TestLifecycleC2SharedStore:
    def test_c2_inserts_and_c5_replaces_same_claims_dict(self):
        e = Engine()
        claims_store = e._claims
        c = _ready_refute(e)
        assert e._claims is claims_store
        assert claims_store[c].status == CLAIM_STATUS_CANDIDATE
        assert e.refute_claim_if_ready(c) is True
        # C2 get_claim observes the C5 status replacement on the same dict.
        assert e._claims is claims_store
        assert e.get_claim(c).status == CLAIM_STATUS_REFUTED
        assert claims_store[c].status == CLAIM_STATUS_REFUTED
        # get_claim remains owned by CrudMixin (not promoted).
        assert _defining_class(Engine, "get_claim") is CrudMixin


class TestLifecycleContradictionStoreOwnership:
    def test_register_and_resolve_keep_store_identity(self):
        e = Engine()
        contra_store = e._contradictions
        resolved_store = e._resolved_contradictions
        c = _candidate(e)
        ev = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=7, strength=0.9)
        e.register_contradiction(c, ev)
        e.register_contradiction_resolution(c, ev)
        # same dict objects throughout; original contradiction entry preserved.
        assert e._contradictions is contra_store
        assert e._resolved_contradictions is resolved_store
        assert e.contradictions_for_claim(c) == (ev,)          # not deleted
        assert e.resolved_contradictions_for_claim(c) == (ev,)
        assert e.active_contradictions_for_claim(c) == ()       # active set shrank


class TestLifecycleReadersReadOnly:
    def test_readers_do_not_mutate_and_order_is_deterministic(self):
        e = Engine()
        c, _ev = _make_disputed(e)
        # add a second, lower-id active contradiction to exercise ordering.
        ev2 = e.add_evidence(claim_id=c, raw_ref_id=2, evidence_type=7, strength=0.3)
        e.register_contradiction(c, ev2)
        before_snap = e.to_snapshot()
        before_id = e.state_identity()
        for name in _C5_READERS:
            out = getattr(e, name)(c)
            assert isinstance(out, tuple)
            assert all(isinstance(x, int) for x in out)
        asc = e.active_contradictions_for_claim(c)
        desc = e.active_contradictions_by_freshness(c)
        assert asc == tuple(sorted(asc))
        assert desc == tuple(sorted(asc, reverse=True))
        assert e.to_snapshot() == before_snap
        assert e.state_identity() == before_id

    def test_readers_raise_keyerror_unknown_id_without_state_change(self):
        e = Engine()
        before = e.to_snapshot()
        for name in _C5_READERS:
            try:
                getattr(e, name)(99999)
                raised = False
            except KeyError:
                raised = True
            assert raised
        assert e.to_snapshot() == before


class TestLifecyclePatchEndNoPromotion:
    def test_spying_a_c5_method_on_mixin_does_not_promote(self, monkeypatch):
        name = "refute_claim_if_ready"
        owner = _defining_class(Engine, name)
        assert owner is LifecycleMixin
        original = owner.__dict__[name]
        with monkeypatch.context() as m:
            m.setattr(owner, name, lambda self, claim_id: original(self, claim_id))
            assert name not in Engine.__dict__
            assert _defining_class(Engine, name) is LifecycleMixin
        assert name not in Engine.__dict__
        assert _defining_class(Engine, name) is LifecycleMixin
        assert getattr(Engine, name) is original
        assert LifecycleMixin.__dict__[name] is original
