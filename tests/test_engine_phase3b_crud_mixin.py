"""Phase 3B-7 — runtime contracts for the extracted C2 entity/observation/claim/
evidence CRUD mixin.

Locks only what the *extraction* introduces and that the existing CRUD suites do
not already cover: that the nine C2 methods are inherited from CrudMixin yet remain
resolvable through Engine with the public surface unchanged, that the six
previously-merged mixins keep their declaration order and CrudMixin is appended
last (7-mixin accumulation), that the C2 mutators still reach the C1 id/revision/
guard seams through self/MRO, that add_claim/add_evidence preserve their failure
ORDER (guard/admission before any id allocation or revision bump), and that the C2
inserts and the C5 status replacement operate on the SAME Engine-owned _claims
dict. Deliberately RUNTIME and location-agnostic; every spy is installed on the
method's defining class so the test leaves Engine.__dict__ unpolluted. The full
CRUD value semantics are already locked by the existing suite and are NOT
re-asserted here.
"""

from __future__ import annotations

import inspect

import ragcore
from ragcore import Engine
from ragcore._engine.confidence_adapters import ConfidenceAdaptersMixin
from ragcore._engine.crud import CrudMixin
from ragcore._engine.gaps import GapsMixin
from ragcore._engine.hint_evidence import HintEvidenceMixin
from ragcore._engine.lifecycle_history import LifecycleHistoryMixin
from ragcore._engine.relations import RelationsMixin
from ragcore._engine.rules import RulesMixin
from ragcore.types import CLAIM_STATUS_CANDIDATE, CLAIM_STATUS_REFUTED

# Declaration order in CrudMixin: 4 mutators interleaved with 5 readers.
_C2 = (
    "add_entity",
    "get_entity",
    "add_observation",
    "get_observation",
    "add_claim",
    "get_claim",
    "add_evidence",
    "get_evidence",
    "evidences_for_claim",
)
_C2_MUTATORS = ("add_entity", "add_observation", "add_claim", "add_evidence")
_C2_READERS = (
    "get_entity",
    "get_observation",
    "get_claim",
    "get_evidence",
    "evidences_for_claim",
)

# The prefix-order contract: the six prior mixins keep their declaration order and
# CrudMixin is appended last. This is a prefix SLICE, not the full MRO tuple or the
# base count — a future appended mixin lands at index 8 and leaves this slice
# unchanged, so it does not block later Phase-3 additions.
_EXPECTED_MIXIN_PREFIX = (
    HintEvidenceMixin,
    RelationsMixin,
    RulesMixin,
    GapsMixin,
    ConfidenceAdaptersMixin,
    LifecycleHistoryMixin,
    CrudMixin,
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


class TestCrudComposition:
    def test_mixin_mro_prefix_exact(self):
        # Locks both "the six prior mixins keep their order" and
        # "CrudMixin is appended last".
        assert Engine.__mro__[1:8] == _EXPECTED_MIXIN_PREFIX

    def test_engine_module_path_preserved(self):
        assert Engine.__module__ == "ragcore.engine"
        assert ragcore.Engine is Engine

    def test_public_surface_counts_unchanged(self):
        public = [n for n in dir(Engine)
                  if not n.startswith("_") and callable(getattr(Engine, n))]
        assert len(public) == 42
        assert len(ragcore.__all__) == 50

    def test_c2_methods_owned_by_mixin_without_engine_promotion(self):
        for name in _C2:
            fn = getattr(Engine, name)
            assert callable(fn)
            assert name not in Engine.__dict__
            assert _defining_class(Engine, name) is CrudMixin
            assert getattr(Engine, name) is CrudMixin.__dict__[name]
            assert fn.__module__ == "ragcore._engine.crud"
            assert fn.__qualname__ == f"CrudMixin.{name}"

    def test_c2_getsource_returns_real_bodies(self):
        # Spot-check the two mutators whose failure ORDER this PR locks plus a
        # reader; the bodies must be the real ones (not a forwarding wrapper).
        ac = inspect.getsource(Engine.add_claim)
        assert "unknown subject_id (entity)" in ac and "_allocate_id" in ac
        assert "super()" not in ac
        ae = inspect.getsource(Engine.add_evidence)
        assert "_assert_claim_exists" in ae and "ScoreValue" in ae
        assert "super()" not in ae
        efc = inspect.getsource(Engine.evidences_for_claim)
        assert "_assert_claim_exists" in efc and "super()" not in efc


class TestCrudSignatures:
    _EXPECTED = {
        "add_entity":
            "(self, entity_type: 'int', flags: 'int' = 0) -> 'int'",
        "get_entity":
            "(self, entity_id: 'int') -> 'Entity'",
        "add_observation":
            "(self, entity_id: 'int', raw_ref_id: 'int', "
            "observation_type: 'int', source_type: 'int' = 0) -> 'int'",
        "get_observation":
            "(self, observation_id: 'int') -> 'Observation'",
        "add_claim":
            "(self, subject_id: 'int', claim_type: 'int', rule_id: 'int', "
            "rule_version: 'int', reason_code: 'int', *, "
            "base_confidence: 'float' = 0.5, status: 'int' = 0, "
            "flags: 'int' = 0) -> 'int'",
        "get_claim":
            "(self, claim_id: 'int') -> 'Claim'",
        "add_evidence":
            "(self, claim_id: 'int', raw_ref_id: 'int', "
            "evidence_type: 'int', strength: 'float') -> 'int'",
        "get_evidence":
            "(self, evidence_id: 'int') -> 'Evidence'",
        "evidences_for_claim":
            "(self, claim_id: 'int') -> 'list[Evidence]'",
    }

    def test_signatures_exact(self):
        assert set(self._EXPECTED) == set(_C2)
        for name, expected in self._EXPECTED.items():
            assert str(inspect.signature(getattr(Engine, name))) == expected

    def test_add_claim_base_confidence_is_keyword_only(self):
        params = inspect.signature(Engine.add_claim).parameters
        assert params["base_confidence"].kind is inspect.Parameter.KEYWORD_ONLY
        assert params["status"].kind is inspect.Parameter.KEYWORD_ONLY
        assert params["flags"].kind is inspect.Parameter.KEYWORD_ONLY
        assert params["status"].default == CLAIM_STATUS_CANDIDATE


class TestCrudC1Seam:
    def test_mutators_reach_c1_revision_seam_via_self(self, monkeypatch):
        # Each C2 mutator must bump the C1 state-revision exactly once through
        # self/MRO. The C1 seam is spied on its defining class (the Engine base),
        # so no inherited C2 method is promoted onto Engine.__dict__.
        name = "_advance_state_revision"
        owner = _defining_class(Engine, name)
        assert owner is Engine  # C1 infrastructure stays on the Engine base
        original = owner.__dict__[name]

        e = Engine()
        ent = e.add_entity(entity_type=1)
        claim = e.add_claim(subject_id=ent, claim_type=1, rule_id=1,
                            rule_version=1, reason_code=0)

        for op in (
            lambda: e.add_entity(entity_type=2),
            lambda: e.add_observation(entity_id=ent, raw_ref_id=0,
                                      observation_type=1),
            lambda: e.add_claim(subject_id=ent, claim_type=1, rule_id=1,
                                rule_version=1, reason_code=0),
            lambda: e.add_evidence(claim_id=claim, raw_ref_id=0,
                                   evidence_type=42, strength=0.9),
        ):
            calls = []

            def spy(self, *a, _calls=calls, **kw):
                _calls.append(1)
                return original(self, *a, **kw)

            with monkeypatch.context() as m:
                m.setattr(owner, name, spy)
                op()
                assert len(calls) == 1

        # The C1 seam identity is restored and no C2 method leaked into Engine.
        assert getattr(Engine, name) is original
        for c2 in _C2:
            assert c2 not in Engine.__dict__
            assert _defining_class(Engine, c2) is CrudMixin

    def test_patch_end_no_promotion_for_c2_method(self, monkeypatch):
        # Spying a C2 method on its DEFINING class (CrudMixin) must not promote it
        # onto Engine.__dict__, and the original identity is restored afterwards.
        name = "get_claim"
        owner = _defining_class(Engine, name)
        assert owner is CrudMixin
        original = owner.__dict__[name]

        with monkeypatch.context() as m:
            m.setattr(owner, name, lambda self, claim_id: original(self, claim_id))
            assert name not in Engine.__dict__
            assert _defining_class(Engine, name) is CrudMixin

        assert name not in Engine.__dict__
        assert _defining_class(Engine, name) is CrudMixin
        assert getattr(Engine, name) is original
        assert CrudMixin.__dict__[name] is original


class TestCrudFailureOrder:
    def test_add_claim_unknown_subject_label_and_no_consumption(self):
        # Distinct subject label (NOT the entity_id guard label), and the failed
        # attempt consumes no claim id / revision (snapshot + identity unchanged).
        e = Engine()
        ent = e.add_entity(entity_type=1)
        c1 = e.add_claim(subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
                         reason_code=0)
        before_snap = e.to_snapshot()
        before_id = e.state_identity()
        try:
            e.add_claim(subject_id=99999, claim_type=1, rule_id=1, rule_version=1,
                        reason_code=0)
            raised = None
        except KeyError as exc:
            raised = exc
        assert raised is not None
        assert str(raised) == "'unknown subject_id (entity): 99999'"
        assert e.to_snapshot() == before_snap
        assert e.state_identity() == before_id
        # next successful claim takes the sequential id (no gap from the failure).
        c2 = e.add_claim(subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
                         reason_code=0)
        assert c2 == c1 + 1

    def test_add_claim_status_rejected_before_mutation(self):
        e = Engine()
        ent = e.add_entity(entity_type=1)
        before_snap = e.to_snapshot()
        try:
            e.add_claim(subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
                        reason_code=0, status=999)
            raised = False
        except ValueError:
            raised = True
        assert raised
        assert e.to_snapshot() == before_snap

    def test_add_claim_bad_base_confidence_consumes_no_id(self):
        # base_confidence is validated BEFORE _allocate_id (PR73-M04 §3 C1), so a
        # failed ScoreValue admission must not consume a claim id.
        e = Engine()
        ent = e.add_entity(entity_type=1)
        c1 = e.add_claim(subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
                         reason_code=0)
        before_snap = e.to_snapshot()
        try:
            e.add_claim(subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
                        reason_code=0, base_confidence=1.5)
            raised = False
        except ValueError:
            raised = True
        assert raised
        assert e.to_snapshot() == before_snap
        c2 = e.add_claim(subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
                         reason_code=0)
        assert c2 == c1 + 1

    def test_add_evidence_guard_before_strength_validation(self):
        # Unknown claim_id is rejected by the C1 guard (distinct label) before the
        # strength ScoreValue is ever constructed, and consumes no evidence id.
        e = Engine()
        c = _candidate(e)
        e1 = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=42,
                            strength=0.9)
        before_snap = e.to_snapshot()
        try:
            e.add_evidence(claim_id=88888, raw_ref_id=0, evidence_type=42,
                           strength=2.0)
            raised = None
        except KeyError as exc:
            raised = exc
        assert raised is not None
        assert str(raised) == "'unknown claim_id: 88888'"
        assert e.to_snapshot() == before_snap
        # strength is validated BEFORE _allocate_id, so a bad strength on a KNOWN
        # claim also consumes no evidence id.
        try:
            e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=42,
                           strength=2.0)
            raised2 = False
        except ValueError:
            raised2 = True
        assert raised2
        e2 = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=42,
                            strength=0.9)
        assert e2 == e1 + 1


class TestCrudC5SharedStore:
    def test_c2_inserts_and_c5_replaces_same_claims_dict(self):
        # _claims is the one operational shared-write store: C2 (add_claim/
        # get_claim) and C5 (the lifecycle transition that stays on Engine this
        # phase) must operate on the SAME dict object via self.
        e = Engine()
        claims_store = e._claims
        c = _candidate(e)
        assert e._claims is claims_store
        assert claims_store[c].status == CLAIM_STATUS_CANDIDATE

        ev = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=42,
                            strength=0.9)
        e.register_contradiction(c, ev)
        assert e.refute_claim_if_ready(c) is True

        # C2 get_claim observes the C5 status replacement on the same dict.
        assert e._claims is claims_store
        assert e.get_claim(c).status == CLAIM_STATUS_REFUTED
        assert claims_store[c].status == CLAIM_STATUS_REFUTED


class TestCrudReadersReadOnly:
    def test_readers_do_not_mutate_state(self):
        e = Engine()
        ent = e.add_entity(entity_type=1)
        obs = e.add_observation(entity_id=ent, raw_ref_id=0, observation_type=1)
        c = e.add_claim(subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
                        reason_code=0)
        ev = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=42,
                            strength=0.9)
        before_snap = e.to_snapshot()
        before_id = e.state_identity()
        assert e.get_entity(ent).id == ent
        assert e.get_observation(obs).id == obs
        assert e.get_claim(c).id == c
        assert e.get_evidence(ev).id == ev
        assert [x.id for x in e.evidences_for_claim(c)] == [ev]
        assert e.to_snapshot() == before_snap
        assert e.state_identity() == before_id

    def test_readers_raise_keyerror_unknown_id_without_state_change(self):
        e = Engine()
        before = e.to_snapshot()
        for call in (
            lambda: e.get_entity(99999),
            lambda: e.get_observation(99999),
            lambda: e.get_claim(99999),
            lambda: e.get_evidence(99999),
            lambda: e.evidences_for_claim(99999),
        ):
            try:
                call()
                raised = False
            except KeyError:
                raised = True
            assert raised
        assert e.to_snapshot() == before
