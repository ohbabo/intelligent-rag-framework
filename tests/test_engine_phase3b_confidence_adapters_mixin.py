"""Phase 3B-5 — runtime contracts for the extracted C9 confidence-adapters mixin.

Locks only what the *extraction* introduces and that the existing suite (M07
trace + confidence-kernel tests) does not already cover: that the ten C9 methods
are inherited from ConfidenceAdaptersMixin yet remain resolvable through Engine
with the public surface unchanged, that the four previously-merged mixins are
still present (5-mixin accumulation), that the M07 getsource real-body seam
survives the relocation, that the C9 public APIs are read-only, that the C9->C5
runtime self-resolution is preserved, and that the pure confidence kernel is
untouched. Deliberately RUNTIME and location-agnostic; spies are patched on the
method's defining class so the test leaves Engine.__dict__ unpolluted. The full
modifier/composition semantics are already locked by the M07 + kernel suites and
are NOT re-asserted here.
"""

from __future__ import annotations

import inspect

import ragcore
import ragcore._engine.confidence as confidence
from ragcore import Engine
from ragcore._engine.confidence_adapters import ConfidenceAdaptersMixin
from ragcore._engine.gaps import GapsMixin
from ragcore._engine.hint_evidence import HintEvidenceMixin
from ragcore._engine.relations import RelationsMixin
from ragcore._engine.rules import RulesMixin
from ragcore.types import EffectiveConfidenceTrace, ScoreValue

_C9 = (
    "evidence_freshness",
    "_status_modifier_for_claim",
    "_freshness_modifier_for_claim",
    "_gap_modifier_for_claim",
    "_count_modifier_for_claim",
    "_rule_stats_modifier_for_claim",
    "_evidence_type_modifier_for_claim",
    "compute_effective_confidence",
    "_compute_effective_confidence_core",
    "compute_effective_confidence_with_trace",
)


def _defining_class(cls, name):
    for base in cls.__mro__:
        if name in base.__dict__:
            return base
    raise AttributeError(name)


def _populated():
    e = Engine()
    ent = e.add_entity(entity_type=1)
    c = e.add_claim(subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
                    reason_code=0, base_confidence=0.7)
    ev = e.add_evidence(claim_id=c, raw_ref_id=0, evidence_type=42, strength=0.6)
    e.register_contradiction(c, ev)
    return e, c, ev


class TestConfidenceAdaptersComposition:
    def test_mixin_in_mro(self):
        assert ConfidenceAdaptersMixin in Engine.__mro__

    def test_prior_mixins_still_present(self):
        for m in (HintEvidenceMixin, RelationsMixin, RulesMixin, GapsMixin):
            assert m in Engine.__mro__

    def test_engine_module_path_preserved(self):
        assert Engine.__module__ == "ragcore.engine"
        assert ragcore.Engine is Engine

    def test_public_surface_count_unchanged(self):
        public = [n for n in dir(Engine)
                  if not n.startswith("_") and callable(getattr(Engine, n))]
        assert len(public) == 42

    def test_c9_methods_resolve_to_mixin(self):
        for name in _C9:
            fn = getattr(Engine, name)
            assert callable(fn)
            assert fn.__module__ == "ragcore._engine.confidence_adapters"
            assert fn.__qualname__ == f"ConfidenceAdaptersMixin.{name}"


class TestConfidenceAdaptersSignatures:
    _EXPECTED = {
        "evidence_freshness": "(self, evidence_id: 'int') -> 'int'",
        "compute_effective_confidence": "(self, claim_id: 'int') -> 'ScoreValue'",
        "compute_effective_confidence_with_trace":
            "(self, claim_id: 'int') -> 'EffectiveConfidenceTrace'",
        "_compute_effective_confidence_core":
            "(self, claim_id: 'int') -> 'EffectiveConfidenceTrace'",
    }
    _MODIFIERS = (
        "_status_modifier_for_claim", "_freshness_modifier_for_claim",
        "_gap_modifier_for_claim", "_count_modifier_for_claim",
        "_rule_stats_modifier_for_claim", "_evidence_type_modifier_for_claim",
    )

    def test_named_signatures_exact(self):
        for name, expected in self._EXPECTED.items():
            assert str(inspect.signature(getattr(Engine, name))) == expected

    def test_modifier_signatures_exact(self):
        for name in self._MODIFIERS:
            assert str(inspect.signature(getattr(Engine, name))) == \
                "(self, claim_id: 'int') -> 'float'"


class TestConfidenceCoreGetsourceSeam:
    """The M07 runtime getsource lock survives the mixin relocation: the
    core's real body (one composer delegation in one ScoreValue) is returned."""

    def test_core_getsource_is_real_body(self):
        src = inspect.getsource(Engine._compute_effective_confidence_core)
        assert "compose_effective_confidence" in src
        assert "ScoreValue" in src
        assert "state_identity" in src
        assert "super()" not in src

    def test_public_apis_getsource_delegate_no_super(self):
        for name in ("compute_effective_confidence",
                     "compute_effective_confidence_with_trace"):
            src = inspect.getsource(getattr(Engine, name))
            assert "_compute_effective_confidence_core" in src
            assert "super()" not in src


class TestConfidenceAdaptersReadOnly:
    def test_public_apis_do_not_mutate(self):
        e, c, ev = _populated()
        sid = e.state_identity()
        snap = e.to_snapshot()
        e.evidence_freshness(ev)
        e.compute_effective_confidence(c)
        e.compute_effective_confidence_with_trace(c)
        assert e.state_identity() == sid
        assert e.to_snapshot() == snap

    def test_both_public_apis_agree(self):
        e, c, _ = _populated()
        trace = e.compute_effective_confidence_with_trace(c)
        assert isinstance(trace, EffectiveConfidenceTrace)
        assert e.compute_effective_confidence(c) == trace.effective_confidence
        assert trace.calculation_policy_id == confidence._EFFECTIVE_CONFIDENCE_POLICY_ID


class TestConfidenceCrossClusterAndKernel:
    def test_c9_to_c5_runtime_self_resolution(self, monkeypatch):
        # Patch the C5 queries on their defining class (forward-compatible with
        # a later C5 mixin extraction) and confirm the modifiers reach them.
        e, c, _ = _populated()
        counts = {"active_contradictions_for_claim": 0,
                  "active_contradictions_by_freshness": 0}
        for name in counts:
            owner = _defining_class(Engine, name)
            original = owner.__dict__[name]

            def make(orig, key):
                def spy(self, *a, **k):
                    counts[key] += 1
                    return orig(self, *a, **k)
                return spy

            monkeypatch.setattr(owner, name, make(original, name))
        e._count_modifier_for_claim(c)
        e._freshness_modifier_for_claim(c)
        assert counts["active_contradictions_for_claim"] == 1
        assert counts["active_contradictions_by_freshness"] == 1

    def test_core_uses_pure_composer_exactly_once(self, monkeypatch):
        e, c, _ = _populated()
        calls = {"n": 0}
        original = confidence.compose_effective_confidence

        def spy(*a, **k):
            calls["n"] += 1
            return original(*a, **k)

        monkeypatch.setattr(confidence, "compose_effective_confidence", spy)
        e.compute_effective_confidence_with_trace(c)
        assert calls["n"] == 1

    def test_policy_id_unchanged(self):
        assert confidence._EFFECTIVE_CONFIDENCE_POLICY_ID == "ragcore.effective-confidence.v1"
