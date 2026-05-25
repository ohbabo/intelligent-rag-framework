"""PR51 / 185차 — external engine inspector read-only invariants.

Locked (user 2026-05-25):
  The inspector reads through public Engine methods only.
  It does not become a new Engine surface.

Six invariants verified:
  1. packet returns exactly the 7 expected keys
  2. packet contains no LLM-facing or forbidden keys
  3. Engine state is unchanged after inspection
     (snapshot before == snapshot after)
  4. ragcore.__all__ remains 48 symbols
  5. inspector source uses no private attribute access
     (engine._... or ragcore._... in real code; docstring/comment
      mentions are excluded by AST-based check)
  6. inspector source has no forbidden domain vocabulary in
     identifiers (docstring/comment mentions are excluded by
     AST-based check)
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest  # noqa: F401  -- used by pytest test discovery

import ragcore
from ragcore import (
    Engine,
    RULE_MATURITY_STABLE,
    RuleDefinition,
    ScoreValue,
)


# ============================================================================
# Load examples/inspector/engine_inspector.py without sys.path pollution.
# ============================================================================

_INSPECTOR_PATH = (
    Path(__file__).resolve().parent.parent
    / "examples"
    / "inspector"
    / "engine_inspector.py"
)
_spec = importlib.util.spec_from_file_location(
    "_engine_inspector_for_test", _INSPECTOR_PATH
)
_engine_inspector_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_engine_inspector_module)
build_engine_context_packet = _engine_inspector_module.build_engine_context_packet


# ============================================================================
# Test-local constants (NOT exported).
# ============================================================================


_EXPECTED_PACKET_KEYS = frozenset(
    {
        "claim",
        "effective_confidence",
        "supporting_evidence",
        "contradictions",
        "active_contradictions",
        "unresolved_gaps",
        "lifecycle_history",
    }
)

_FORBIDDEN_PACKET_KEYS = frozenset(
    {
        "verdict",
        "risk",
        "probability",
        "proposal",
        "tool_plan",
        "tool_recommendation",
        "summary_score",
        "risk_label",
        "vulnerability_probability",
    }
)

# Domain vocabulary forbidden from inspector source code identifiers.
# Mirrors PR44-D §5.6 / PR45-E §3 forbidden vocabulary lock. These
# words may still appear inside the module's docstring as reference
# material; the AST-based check below excludes docstrings/comments/
# string literals.
_FORBIDDEN_DOMAIN_WORDS = frozenset(
    {
        "cerberus",
        "vulnerability",
        "scanner",
        "exploit",
        "ssh",
        "cve",
        "nmap",
        "host",
        "port",
        "service",
        "asset",
    }
)


# ============================================================================
# Test-local helpers.
# ============================================================================


def _make_minimal_engine() -> tuple[Engine, int]:
    """Construct an Engine with a single claim + one supporting
    evidence, returning (engine, claim_id).
    """
    engine = Engine()
    engine.register_rule(
        RuleDefinition(
            id=1,
            version=1,
            maturity=RULE_MATURITY_STABLE,
            prior_confidence=ScoreValue(0.7),
        )
    )
    entity_id = engine.add_entity(entity_type=1)
    engine.add_observation(
        entity_id=entity_id,
        raw_ref_id=100,
        observation_type=10,
        source_type=20,
    )
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=30,
        rule_id=1,
        rule_version=1,
        reason_code=40,
    )
    engine.add_evidence(
        claim_id=claim_id,
        raw_ref_id=101,
        evidence_type=50,
        strength=0.8,
    )
    return engine, claim_id


def _identifiers_in_source(src: str) -> set[str]:
    """Return all identifier names in source, AST-based.

    Excludes docstrings, comments, and string literals — only
    real Python identifiers (variable names, attribute names,
    function names, class names, function arguments).
    """
    tree = ast.parse(src)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def _private_attribute_accesses_in_source(src: str) -> list[str]:
    """Return any attribute access in source where the attribute
    name starts with an underscore.

    AST-based: excludes docstrings and comments. Catches real
    `obj._private_attr` patterns in code.
    """
    tree = ast.parse(src)
    leaks: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            leaks.append(node.attr)
    return leaks


# ============================================================================
# Tests.
# ============================================================================


class TestExternalEngineInspector:
    """The inspector reads through public Engine methods only.
    It does not become a new Engine surface.
    """

    def test_packet_returns_exactly_seven_expected_keys(self) -> None:
        engine, claim_id = _make_minimal_engine()
        packet = build_engine_context_packet(engine, claim_id)
        assert frozenset(packet.keys()) == _EXPECTED_PACKET_KEYS

    def test_packet_contains_no_llm_facing_or_forbidden_keys(self) -> None:
        engine, claim_id = _make_minimal_engine()
        packet = build_engine_context_packet(engine, claim_id)
        for forbidden in _FORBIDDEN_PACKET_KEYS:
            assert forbidden not in packet, (
                f"forbidden LLM-facing key '{forbidden}' must not "
                f"appear in packet"
            )

    def test_engine_state_unchanged_after_inspection(self) -> None:
        engine, claim_id = _make_minimal_engine()
        before_snapshot = engine.to_snapshot()
        before_effective = engine.compute_effective_confidence(claim_id)

        _ = build_engine_context_packet(engine, claim_id)

        after_snapshot = engine.to_snapshot()
        after_effective = engine.compute_effective_confidence(claim_id)

        assert after_snapshot == before_snapshot
        assert after_effective == before_effective

    def test_ragcore_all_unchanged_at_48_symbols(self) -> None:
        # PR43-C 168차 already enforces this from the playbook test
        # boundary. PR51 re-asserts it from the inspector test boundary
        # so the wrapper's "no public surface change" guarantee is
        # explicit at this level too.
        assert len(ragcore.__all__) == 48
        assert len(set(ragcore.__all__)) == 48

    def test_inspector_source_uses_no_private_attribute_access(self) -> None:
        # AST-based check: docstring/comment mentions of private
        # attributes (e.g., the warning list in the module docstring)
        # are excluded. Only real `obj._attr` patterns in code are
        # caught.
        src = _INSPECTOR_PATH.read_text(encoding="utf-8")
        leaks = _private_attribute_accesses_in_source(src)
        assert leaks == [], (
            f"inspector source must not access private attributes; "
            f"found: {leaks}"
        )

    def test_inspector_source_has_no_forbidden_domain_vocabulary(self) -> None:
        # AST-based check: docstring/comment mentions of the
        # forbidden words (used as documentation reference inside
        # the module docstring) are excluded. Only forbidden words
        # used as actual identifiers are caught.
        src = _INSPECTOR_PATH.read_text(encoding="utf-8")
        identifiers = {name.lower() for name in _identifiers_in_source(src)}
        intrusions = sorted(identifiers & _FORBIDDEN_DOMAIN_WORDS)
        assert intrusions == [], (
            f"inspector source identifiers must remain "
            f"domain-neutral; forbidden words appearing as "
            f"identifiers: {intrusions}"
        )
