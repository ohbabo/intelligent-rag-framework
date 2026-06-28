"""Phase 3B-1 — runtime contracts for the extracted C8 hint-evidence mixin.

These tests lock only what the *extraction* introduces and that the existing
suite does not already cover: that the four C8 methods are inherited from
``HintEvidenceMixin`` yet remain resolvable / patchable through ``Engine`` with
the public surface unchanged. They are deliberately RUNTIME and
location-agnostic (no source-file reads, no line numbers, no ``__bases__`` /
MRO exact-order locks, no private-method-count lock) so a later Phase-3 mixin
can be added without tripping them.

Behavioural semantics (strict validation, deregistration, revision gates,
snapshot shape, public-42 freeze) are already locked by the existing suite and
are NOT re-asserted here.
"""

from __future__ import annotations

import inspect

import ragcore
from ragcore import Engine
from ragcore._engine.hint_evidence import HintEvidenceMixin

_C8_PUBLIC = (
    "register_hint_evidence_types",
    "unregister_hint_evidence_types",
    "clear_hint_evidence_types",
)
_C8_PRIVATE = ("_validate_hint_evidence_type_values",)


class TestHintEvidenceMixinComposition:
    def test_mixin_is_in_engine_mro(self):
        assert HintEvidenceMixin in Engine.__mro__

    def test_engine_module_path_preserved(self):
        assert Engine.__module__ == "ragcore.engine"
        assert ragcore.Engine is Engine

    def test_public_surface_count_unchanged(self):
        public = [n for n in dir(Engine)
                  if not n.startswith("_") and callable(getattr(Engine, n))]
        assert len(public) == 42

    def test_c8_methods_callable_through_engine(self):
        for name in (*_C8_PUBLIC, *_C8_PRIVATE):
            assert callable(getattr(Engine, name))

    def test_c8_methods_declared_on_mixin(self):
        # Inherited (not redeclared on Engine), and resolve to the mixin module.
        for name in (*_C8_PUBLIC, *_C8_PRIVATE):
            assert name not in Engine.__dict__
            assert getattr(Engine, name).__module__ == "ragcore._engine.hint_evidence"

    def test_c8_getsource_returns_real_body(self):
        # The M07-style runtime getsource lock generalises: the inherited
        # method's source is the real implementation, not a forwarding wrapper.
        src = inspect.getsource(Engine.register_hint_evidence_types)
        assert "_validate_hint_evidence_type_values" in src
        assert "_advance_state_revision" in src
        assert "super()" not in src


class TestHintEvidencePublicSignatures:
    _EXPECTED = {
        "register_hint_evidence_types": "(self, types: 'Iterable[int]') -> 'None'",
        "unregister_hint_evidence_types": "(self, types: 'Iterable[int]') -> 'None'",
        "clear_hint_evidence_types": "(self) -> 'None'",
        "_validate_hint_evidence_type_values": "(self, types: 'Iterable[int]') -> 'set[int]'",
    }

    def test_signatures_exact(self):
        for name, expected in self._EXPECTED.items():
            assert str(inspect.signature(getattr(Engine, name))) == expected


class TestHintEvidenceEnginePatchable:
    """The validator and the C1 revision seam stay patchable on Engine (the
    spy pattern used elsewhere) after the move."""

    def test_validator_monkeypatchable_on_engine(self, monkeypatch):
        calls = {"n": 0}
        original = Engine._validate_hint_evidence_type_values

        def spy(self, types):
            calls["n"] += 1
            return original(self, types)

        monkeypatch.setattr(Engine, "_validate_hint_evidence_type_values", spy)
        Engine().register_hint_evidence_types([1, 2])
        assert calls["n"] == 1

    def test_revision_seam_monkeypatchable_on_engine(self, monkeypatch):
        calls = {"n": 0}
        original = Engine._advance_state_revision

        def spy(self):
            calls["n"] += 1
            return original(self)

        monkeypatch.setattr(Engine, "_advance_state_revision", spy)
        e = Engine()
        e.register_hint_evidence_types([1])   # growth -> one advance
        e.register_hint_evidence_types([1])   # no growth -> no advance
        assert calls["n"] == 1
