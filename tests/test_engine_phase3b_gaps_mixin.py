"""Phase 3B-4 — runtime contracts for the extracted C4 gaps mixin.

Locks only what the *extraction* introduces and that the existing suite does not
already cover: that the five C4 methods are inherited from ``GapsMixin`` yet
remain resolvable / patchable through ``Engine`` with the public surface
unchanged, that the three previously-merged mixins are still present (4-mixin
accumulation), that the C4-specific revision gates survive (dedup-hit conditional
revision, resolution single/no-op revision), and that C5's
``confirm_claim_if_ready`` still reaches the inherited C4 methods (cross-cluster
runtime resolution). Deliberately RUNTIME and location-agnostic (no source-file
reads, no line numbers, no ``__bases__`` / MRO exact-order locks, no base /
private-method-count locks).

The full gap semantics (dedup key, severity-before-dedup ordering, cross-claim
sharing, first-evidence-wins) are already locked by the existing suite and are
NOT re-asserted here; the local dev-record probe records their results.
"""

from __future__ import annotations

import inspect

import ragcore
from ragcore import Engine
from ragcore._engine.gaps import GapsMixin
from ragcore._engine.hint_evidence import HintEvidenceMixin
from ragcore._engine.relations import RelationsMixin
from ragcore._engine.rules import RulesMixin

_C4 = ("add_gap", "get_gap", "gaps_for_claim",
       "resolve_gaps_for_evidence", "gap_resolution")


def _claim(e):
    ent = e.add_entity(entity_type=1)
    return e.add_claim(subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
                       reason_code=0, base_confidence=0.5)


class TestGapsMixinComposition:
    def test_gaps_mixin_in_mro(self):
        assert GapsMixin in Engine.__mro__

    def test_prior_mixins_still_present(self):
        for m in (HintEvidenceMixin, RelationsMixin, RulesMixin):
            assert m in Engine.__mro__

    def test_engine_module_path_preserved(self):
        assert Engine.__module__ == "ragcore.engine"
        assert ragcore.Engine is Engine

    def test_public_surface_count_unchanged(self):
        public = [n for n in dir(Engine)
                  if not n.startswith("_") and callable(getattr(Engine, n))]
        assert len(public) == 42

    def test_c4_methods_resolve_to_mixin(self):
        # The methods are contributed by GapsMixin: they resolve to functions
        # defined in the mixin module / class. (Not asserting absence from
        # Engine.__dict__ — the suite's setattr/restore spy pattern can promote
        # an inherited method into Engine.__dict__, so __dict__ membership is
        # not a robust invariant; resolution to the mixin function is.)
        for name in _C4:
            fn = getattr(Engine, name)
            assert callable(fn)
            assert fn.__module__ == "ragcore._engine.gaps"
            assert fn.__qualname__ == f"GapsMixin.{name}"

    def test_c4_getsource_returns_real_body(self):
        add = inspect.getsource(Engine.add_gap)
        assert "_gap_dedup_index" in add and "_allocate_id" in add and "super()" not in add
        res = inspect.getsource(Engine.resolve_gaps_for_evidence)
        assert "gaps_for_claim" in res and "super()" not in res


class TestGapsPublicSignatures:
    _EXPECTED = {
        "add_gap": (
            "(self, claim_id: 'int', gap_type: 'int', "
            "required_evidence_type: 'int', severity: 'float', "
            "rule_id: 'int') -> 'int'"
        ),
        "get_gap": "(self, gap_id: 'int') -> 'Gap'",
        "gaps_for_claim": "(self, claim_id: 'int') -> 'list[Gap]'",
        "resolve_gaps_for_evidence": "(self, evidence_id: 'int') -> 'tuple[int, ...]'",
        "gap_resolution": "(self, gap_id: 'int') -> 'int | None'",
    }

    def test_signatures_exact(self):
        for name, expected in self._EXPECTED.items():
            assert str(inspect.signature(getattr(Engine, name))) == expected


class TestGapsRevisionGatesAndSeams:
    """C4-specific revision gates + that the C1 seams + the intra-C4
    self-call (resolve -> gaps_for_claim) stay patchable on Engine."""

    def test_add_gap_miss_then_same_hit_revision_gate(self):
        e = Engine(); c = _claim(e)
        r0 = e.state_identity()
        e.add_gap(c, 1, 99, 0.5, 7)          # miss -> advances
        r1 = e.state_identity()
        assert r1 != r0
        e.add_gap(c, 1, 99, 0.9, 7)          # same-claim hit -> no advance
        assert e.state_identity() == r1

    def test_resolve_revision_gate_and_self_call(self, monkeypatch):
        e = Engine(); c = _claim(e)
        e.add_gap(c, 1, 99, 0.5, 7)
        match = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=99, strength=0.8)
        nomatch = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=42, strength=0.5)
        calls = {"gaps_for_claim": 0, "_advance_state_revision": 0}
        for name in calls:
            original = getattr(Engine, name)

            def make(orig, key):
                def spy(self, *args, **kwargs):
                    calls[key] += 1
                    return orig(self, *args, **kwargs)
                return spy

            monkeypatch.setattr(Engine, name, make(original, name))
        # matching evidence: resolves -> uses inherited gaps_for_claim, advances once
        res = e.resolve_gaps_for_evidence(match)
        assert res and calls["gaps_for_claim"] == 1 and calls["_advance_state_revision"] == 1
        # nonmatching evidence: no resolution -> still reads gaps_for_claim, no advance
        assert e.resolve_gaps_for_evidence(nomatch) == ()
        assert calls["gaps_for_claim"] == 2 and calls["_advance_state_revision"] == 1


class TestGapsC5Integration:
    """C5 confirm_claim_if_ready must still reach the inherited C4 methods."""

    def test_confirm_depends_on_gap_resolution(self):
        e = Engine(); c = _claim(e)
        e.add_gap(c, 1, 99, 0.5, 7)
        assert e.confirm_claim_if_ready(c) is False          # unresolved gap
        ev = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=99, strength=0.8)
        e.resolve_gaps_for_evidence(ev)
        assert e.confirm_claim_if_ready(c) is True           # resolved
