"""Tests for PR36-PKG — Engine Method Surface Freeze invariants (§48).

PR36-PKG §48.1 (locked):
    PR36-PKG freezes the Engine method surface as a stable package boundary.
    It does not freeze the internal judgment mathematics.

    The engine is allowed to become smarter without forcing consumers
    to rewrite their integration code.

This module locks the public method surface — names, count, presence,
signatures of stable private helpers (modifier + serialize/restore),
snapshot output shape, and import side-effect-free properties.

It does NOT test internal mathematics (values of modifiers, exact score
outputs, formula composition). Those are intentionally allowed to evolve
under §48.3 algorithm evolvability.

If a future framework PR breaks a §48 invariant locked here, the test
fails — that is the regression signal. Intentional method surface
migration (per §48.5) requires updating this file alongside PR31-S
frozenset / PR32-V *_KEYS / docs(contract) breaking-change documentation.

Expected result:
    All tests pass against PR35-O7 main 8dd0535 baseline.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import ragcore
from ragcore import Engine


# Forbidden import roots — ragcore's judgment core must not pull in network /
# process / async modules. Checked by AST over the FILESYSTEM so every import
# form (`from requests import Session`, bare `import socket`, `urllib.parse`)
# is caught, and the modules are never imported/executed (a relocated
# module's internal ModuleNotFoundError cannot mask the scan).
_FORBIDDEN_IMPORT_ROOTS: frozenset[str] = frozenset({
    "requests", "urllib", "urllib3", "httpx", "socket", "subprocess", "asyncio",
})


def _import_roots(source: str) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def _ragcore_refactor_source_files() -> list[Path]:
    """ragcore/engine.py + every file in the private ragcore/_engine package
    (when it exists). Resolved from the package location, not cwd."""
    root = Path(ragcore.__file__).resolve().parent
    files = [root / "engine.py"]
    engine_pkg = root / "_engine"
    if engine_pkg.is_dir():
        files.extend(sorted(engine_pkg.rglob("*.py")))
    return files


# ----------------------------------------------------------------------
# Locked public method surface (41 methods, §48.2 + PR73-M04)
# ----------------------------------------------------------------------

_LOCKED_PUBLIC_METHODS: frozenset[str] = frozenset({
    # Entity / Observation / Claim / Evidence / Relation / Gap CRUD (6)
    "add_entity",
    "add_observation",
    "add_claim",
    "add_evidence",
    "add_relation",
    "add_gap",
    # get_* lookups (8)
    "get_entity",
    "get_observation",
    "get_claim",
    "get_evidence",
    "get_relation",
    "get_gap",
    "get_rule",
    "get_rule_stats",
    # *_for_claim filtered queries (5)
    "evidences_for_claim",
    "gaps_for_claim",
    "contradictions_for_claim",
    "active_contradictions_for_claim",
    "resolved_contradictions_for_claim",
    # gap / resolution helpers (2)
    "gap_resolution",
    "resolve_gaps_for_evidence",
    # contradiction registration (2)
    "register_contradiction",
    "register_contradiction_resolution",
    # lifecycle transitions (6)
    "confirm_claim_if_ready",
    "dispute_claim_if_ready",
    "refute_claim_if_ready",
    "resolve_disputed_claim_if_ready",
    "refute_disputed_claim_if_ready",
    "refute_disputed_claim_if_ready_by_freshness",
    # lifecycle history (1)
    "claim_lifecycle_history",
    # freshness queries (2)
    "evidence_freshness",
    "active_contradictions_by_freshness",
    # rule registry (2)
    "register_rule",
    "update_rule_stats",
    # hint evidence type lifecycle (3)
    "register_hint_evidence_types",
    "unregister_hint_evidence_types",
    "clear_hint_evidence_types",
    # compute (1)
    "compute_effective_confidence",
    # snapshot persistence (2)
    "to_snapshot",
    "from_snapshot",
    # PR73-M04 — engine state identity primitive (1)
    "state_identity",
    # PR76-M07 — effective confidence calculation trace (1)
    "compute_effective_confidence_with_trace",
})  # = 42 methods (PR36-PKG 40 + PR73-M04 1 + PR76-M07 1)


# ----------------------------------------------------------------------
# Locked private modifier helpers (6, §48.2 + PR34-O O2/O3 baseline)
# ----------------------------------------------------------------------

_LOCKED_MODIFIER_HELPERS: tuple[str, ...] = (
    "_status_modifier_for_claim",
    "_freshness_modifier_for_claim",
    "_gap_modifier_for_claim",
    "_count_modifier_for_claim",
    "_rule_stats_modifier_for_claim",
    "_evidence_type_modifier_for_claim",
)


# ----------------------------------------------------------------------
# Locked snapshot top-level keys (18, §48.7)
# ----------------------------------------------------------------------

_LOCKED_SNAPSHOT_TOP_LEVEL_KEYS: frozenset[str] = frozenset({
    "schema_version",
    "next_id",
    "lifecycle_seq",
    "entities",
    "observations",
    "claims",
    "evidences",
    "relations",
    "gaps",
    "rule_definitions",
    "rule_stats",
    "gap_dedup_index",
    "claim_gap_refs",
    "gap_resolutions",
    "contradictions",
    "resolved_contradictions",
    "claim_lifecycle_events",
    "hint_evidence_types",
})  # = 18 keys


class TestPublicNamespaceFreeze:
    """§48.2 — ragcore.__all__ public namespace freeze."""

    def test_ragcore_all_has_exactly_48_symbols(self) -> None:
        # PR73-M04 shift: 48 → 49 (added EngineStateIdentity).
        # PR76-M07 shift: 49 → 50 (added EffectiveConfidenceTrace).
        assert len(ragcore.__all__) == 50

    def test_ragcore_all_has_no_duplicates(self) -> None:
        # PR73-M04 shift: 48 → 49 (added EngineStateIdentity).
        # PR76-M07 shift: 49 → 50 (added EffectiveConfidenceTrace).
        assert len(set(ragcore.__all__)) == 50

    def test_engine_is_exposed_in_ragcore_all(self) -> None:
        assert "Engine" in ragcore.__all__

    def test_from_ragcore_import_engine_works(self) -> None:
        from ragcore import Engine as ImportedEngine
        assert ImportedEngine is Engine


class TestEngineMethodNameFreeze:
    """§48.2 / §48.5 — Engine public method names frozen."""

    def test_engine_public_method_count_is_40(self) -> None:
        # PR73-M04 shift: 40 → 41 (added state_identity).
        # PR76-M07 shift: 41 → 42 (added
        #   compute_effective_confidence_with_trace).
        count = sum(
            1 for name, _ in inspect.getmembers(Engine, callable)
            if not name.startswith("_")
        )
        assert count == 42

    def test_engine_public_method_names_match_locked_set(self) -> None:
        actual = frozenset(
            name for name, _ in inspect.getmembers(Engine, callable)
            if not name.startswith("_")
        )
        assert actual == _LOCKED_PUBLIC_METHODS

    def test_engine_no_renamed_method_silently_added(self) -> None:
        # Any new public method (additive) requires explicit baseline shift.
        actual = frozenset(
            name for name, _ in inspect.getmembers(Engine, callable)
            if not name.startswith("_")
        )
        extra = actual - _LOCKED_PUBLIC_METHODS
        missing = _LOCKED_PUBLIC_METHODS - actual
        assert not extra, f"Unexpected public method added: {extra}"
        assert not missing, f"Locked public method missing: {missing}"


class TestCoreConsumerMethods:
    """§48.6 — the Cerberus consumer integration script must keep working.

    These are the methods explicitly named in §48.6's example script:

        from ragcore import Engine
        engine = Engine()
        claim_id = engine.add_claim(...)
        score = engine.compute_effective_confidence(claim_id)
        history = engine.claim_lifecycle_history(claim_id)
        snapshot = engine.to_snapshot()

    Engine.from_snapshot is also locked because the script's natural
    counterpart (state restore) needs it.

    Note: Engine.claim_report deliberately does NOT exist
    (PR32-V §44.11 OOS). PR36-PKG preserves that invariant. To verify
    its absence, see PR32-V test_engine_does_not_expose_claim_report_helper
    in tests/test_engine_report_surface.py — not duplicated here.
    """

    _CORE_CONSUMER_METHODS = (
        "add_claim",
        "compute_effective_confidence",
        "claim_lifecycle_history",
        "to_snapshot",
        "from_snapshot",
    )

    def test_engine_class_is_importable(self) -> None:
        assert Engine is not None
        assert callable(Engine)

    def test_core_consumer_methods_exist(self) -> None:
        for name in self._CORE_CONSUMER_METHODS:
            assert hasattr(Engine, name), f"Engine missing {name}"
            assert callable(getattr(Engine, name)), f"Engine.{name} not callable"


class TestImportSurfaceSideEffects:
    """§48.9 — importing ragcore is side-effect free."""

    def test_engine_instantiation_no_external_call(self) -> None:
        # Engine() with no arguments must succeed without any external
        # dependency (no network, no file IO, no LLM, no Cerberus).
        engine = Engine()
        assert engine is not None

    def test_empty_engine_to_snapshot_is_valid_dict(self) -> None:
        engine = Engine()
        snap = engine.to_snapshot()
        assert isinstance(snap, dict)
        assert snap["schema_version"] == 2

    def test_empty_engine_snapshot_round_trip_identity(self) -> None:
        engine = Engine()
        restored = Engine.from_snapshot(engine.to_snapshot())
        assert restored.to_snapshot() == engine.to_snapshot()

    def test_ragcore_engine_sources_have_no_forbidden_imports(self) -> None:
        # §48.9 (Phase 0): ragcore's judgment core must not import network /
        # process / async modules. Checked PACKAGE-WIDE by AST over the
        # FILESYSTEM (ragcore/engine.py + ragcore/_engine/** when it exists),
        # so every import form is caught and no module is imported/executed
        # (a relocated module's internal ModuleNotFoundError cannot mask the
        # scan; the previous substring scan missed `from X import ...` forms).
        for path in _ragcore_refactor_source_files():
            offending = _import_roots(path.read_text()) & _FORBIDDEN_IMPORT_ROOTS
            assert not offending, (
                f"{path} imports forbidden module(s): {sorted(offending)} (§48.9)"
            )

    @pytest.mark.parametrize("source", [
        "import socket",
        "from socket import socket",
        "import urllib.request",
        "from urllib.parse import urlparse",
        "from requests import Session",
        "from httpx import Client",
        "import subprocess",
        "import asyncio",
    ])
    def test_forbidden_import_detector_catches_common_forms(
        self, source: str
    ) -> None:
        # Negative control: the AST detector flags the common import forms the
        # previous substring scan silently passed.
        assert _import_roots(source) & _FORBIDDEN_IMPORT_ROOTS


class TestModifierHelperSignatures:
    """§48.2 + PR34-O O2/O3 — all 6 modifier helpers share signature.

    PR34-O §46 O2 normalized the modifier helper signature; PR34-O O3
    extracted _status_modifier_for_claim and _freshness_modifier_for_claim.
    PR36-PKG locks this signature so future modifier internal refactors
    (calibration / formula changes) preserve the helper interface.
    """

    def test_all_6_modifier_helpers_exist(self) -> None:
        for name in _LOCKED_MODIFIER_HELPERS:
            assert hasattr(Engine, name), f"Engine missing {name}"

    def test_all_6_modifier_helpers_take_claim_id_int(self) -> None:
        for name in _LOCKED_MODIFIER_HELPERS:
            helper = getattr(Engine, name)
            sig = inspect.signature(helper)
            params = list(sig.parameters.values())
            # params[0] is self, params[1] should be claim_id: int
            assert len(params) >= 2, f"{name}: expected at least 2 params"
            assert params[1].name == "claim_id", (
                f"{name}: second param should be claim_id, got {params[1].name}"
            )

    def test_all_6_modifier_helpers_return_float(self) -> None:
        for name in _LOCKED_MODIFIER_HELPERS:
            helper = getattr(Engine, name)
            sig = inspect.signature(helper)
            # Return annotation should be float (or "float" string in
            # from __future__ import annotations style).
            assert sig.return_annotation in (float, "float"), (
                f"{name}: return annotation should be float, "
                f"got {sig.return_annotation}"
            )


class TestSerializeRestoreSymmetry:
    """§48.2 — serialize / restore correctness.

    The previous in-source `_serialize_dict_*` / `_restore_dict_*` regex
    counts were an implementation-LOCATION lock (they break a pure
    relocation of the helpers). Per the Engine v1 refactoring plan
    (Phase 0 — contract-test taxonomy migration) the exhaustive coverage
    moved to a location-agnostic BEHAVIORAL round-trip exercising all six
    snapshot shape families: see tests/test_engine_phase0_taxonomy.py
    (TestSerializeRestoreRoundTrip). This smoke test stays as a quick
    in-file guard.
    """

    def test_populated_round_trip_smoke(self) -> None:
        import copy
        e = Engine()
        ent = e.add_entity(entity_type=1)
        e.add_claim(
            subject_id=ent, claim_type=1, rule_id=1, rule_version=1,
            reason_code=0, base_confidence=0.5,
        )
        snap = e.to_snapshot()
        assert Engine.from_snapshot(copy.deepcopy(snap)).to_snapshot() == snap


class TestSnapshotShapeFreeze:
    """§48.7 — snapshot output shape frozen."""

    def test_snapshot_top_level_key_count_is_18(self) -> None:
        engine = Engine()
        snap = engine.to_snapshot()
        assert len(snap) == 18

    def test_snapshot_top_level_keys_match_locked_set(self) -> None:
        engine = Engine()
        snap = engine.to_snapshot()
        assert frozenset(snap.keys()) == _LOCKED_SNAPSHOT_TOP_LEVEL_KEYS

    def test_snapshot_schema_version_is_2(self) -> None:
        engine = Engine()
        snap = engine.to_snapshot()
        assert snap["schema_version"] == 2

    def test_snapshot_is_json_compatible_top_level(self) -> None:
        # §48.7 / §39.4 — snapshot must be JSON-compatible at the top level
        # so external consumers can persist it as JSON.
        import json
        engine = Engine()
        snap = engine.to_snapshot()
        # If snapshot contains non-JSON-serializable types at the top, this
        # raises TypeError. Empty engine should serialize cleanly.
        encoded = json.dumps(snap)
        assert isinstance(encoded, str)


class TestPackageSurfaceStability:
    """§48.9 + §48.12 — package import surface invariants."""

    def test_import_ragcore_does_not_raise(self) -> None:
        # Re-importing should be idempotent and side-effect free.
        import ragcore as ragcore_again  # noqa: F401
        assert ragcore_again is ragcore

    def test_ragcore_all_is_list_or_tuple(self) -> None:
        # __all__ may be list or tuple per Python conventions.
        assert isinstance(ragcore.__all__, (list, tuple))

    def test_ragcore_engine_attribute_matches_imported_engine(self) -> None:
        from ragcore import Engine as imported_engine
        assert ragcore.Engine is imported_engine
