"""Phase 3B-3 — runtime contracts for the extracted C7 rules mixin.

Locks only what the *extraction* introduces and that the existing suite does not
already cover: that the four C7 methods are inherited from ``RulesMixin`` yet
remain resolvable / patchable through ``Engine`` with the public surface
unchanged, and that the two previously-merged mixins are still present (the
3-mixin accumulation). The ``update_rule_stats`` revision gate (advance only on
real value change) is locked at runtime because it is the C7-specific behaviour
the move must preserve. Deliberately RUNTIME and location-agnostic (no
source-file reads, no line numbers, no ``__bases__`` / MRO exact-order locks, no
base / private-method-count locks).

The full rule semantics (duplicate ValueError, default stats, definition/stats
independent restore, stats-replacement) are already locked by the existing suite
and are NOT re-asserted here; the local dev-record probe records their results.
"""

from __future__ import annotations

import inspect

import ragcore
from ragcore import Engine
from ragcore._engine.hint_evidence import HintEvidenceMixin
from ragcore._engine.relations import RelationsMixin
from ragcore._engine.rules import RulesMixin
from ragcore.types import RULE_MATURITY_STABLE, RuleDefinition, ScoreValue

_C7 = ("register_rule", "get_rule", "get_rule_stats", "update_rule_stats")


def _rule(rule_id: int = 5, version: int = 1) -> RuleDefinition:
    return RuleDefinition(id=rule_id, version=version,
                          maturity=RULE_MATURITY_STABLE,
                          prior_confidence=ScoreValue(0.7))


class TestRulesMixinComposition:
    def test_rules_mixin_in_mro(self):
        assert RulesMixin in Engine.__mro__

    def test_prior_mixins_still_present(self):
        assert HintEvidenceMixin in Engine.__mro__
        assert RelationsMixin in Engine.__mro__

    def test_engine_module_path_preserved(self):
        assert Engine.__module__ == "ragcore.engine"
        assert ragcore.Engine is Engine

    def test_public_surface_count_unchanged(self):
        public = [n for n in dir(Engine)
                  if not n.startswith("_") and callable(getattr(Engine, n))]
        assert len(public) == 42

    def test_c7_methods_declared_on_mixin(self):
        for name in _C7:
            assert callable(getattr(Engine, name))
            assert name not in Engine.__dict__
            assert getattr(Engine, name).__module__ == "ragcore._engine.rules"

    def test_c7_getsource_returns_real_body(self):
        reg = inspect.getsource(Engine.register_rule)
        assert "_rule_definitions" in reg and "_rule_stats" in reg
        assert "super()" not in reg
        upd = inspect.getsource(Engine.update_rule_stats)
        assert "_assert_rule_stats_pair_exists" in upd and "super()" not in upd


class TestRulesPublicSignatures:
    _EXPECTED = {
        "register_rule": "(self, definition: 'RuleDefinition') -> 'None'",
        "get_rule": "(self, rule_id: 'int', rule_version: 'int') -> 'RuleDefinition'",
        "get_rule_stats": "(self, rule_id: 'int', rule_version: 'int') -> 'RuleStats'",
        "update_rule_stats": (
            "(self, rule_id: 'int', rule_version: 'int', *, "
            "firing_delta: 'int' = 0, true_delta: 'int' = 0, "
            "false_delta: 'int' = 0, "
            "observed_precision: 'ScoreValue | None' = None, "
            "false_positive_rate: 'ScoreValue | None' = None) -> 'None'"
        ),
    }

    def test_signatures_exact(self):
        for name, expected in self._EXPECTED.items():
            assert str(inspect.signature(getattr(Engine, name))) == expected


class TestRulesEngineSeams:
    """C1 guard/revision seams stay patchable on Engine; the update_rule_stats
    revision gate (advance only on real change) is preserved through the move."""

    def _spy(self, monkeypatch, names):
        counts = {n: 0 for n in names}
        for name in names:
            original = getattr(Engine, name)

            def make(orig, key):
                def spy(self, *args, **kwargs):
                    counts[key] += 1
                    return orig(self, *args, **kwargs)
                return spy

            monkeypatch.setattr(Engine, name, make(original, name))
        return counts

    def test_changed_update_advances_revision_once(self, monkeypatch):
        e = Engine(); e.register_rule(_rule(7, 1))
        counts = self._spy(monkeypatch,
                           ["_assert_rule_stats_pair_exists", "_advance_state_revision"])
        e.update_rule_stats(7, 1, firing_delta=1)
        assert counts["_assert_rule_stats_pair_exists"] == 1
        assert counts["_advance_state_revision"] == 1

    def test_noop_update_does_not_advance_revision(self, monkeypatch):
        e = Engine(); e.register_rule(_rule(7, 1))
        counts = self._spy(monkeypatch,
                           ["_assert_rule_stats_pair_exists", "_advance_state_revision"])
        e.update_rule_stats(7, 1)
        assert counts["_assert_rule_stats_pair_exists"] == 1
        assert counts["_advance_state_revision"] == 0

    def test_register_rule_advances_revision_once(self, monkeypatch):
        e = Engine()
        counts = self._spy(monkeypatch, ["_advance_state_revision"])
        e.register_rule(_rule(8, 1))
        assert counts["_advance_state_revision"] == 1
