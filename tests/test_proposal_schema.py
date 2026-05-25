"""PR55 / 195차 — minimal LLM proposal schema invariants.

Locked (user 2026-05-25):
  PR55 locks the minimal shape of LLM proposal drafts.
  It validates proposal structure.
  It does not validate truth.
  It does not authorize execution.
  It does not mutate Engine state.

11 invariants verified:
  1.  valid required-only proposal returns []
  2.  valid proposal with optional refs returns []
  3.  non-dict proposal returns S1 and does NOT raise
  4.  missing required fields reported deterministically (sorted)
  5.  invalid category rejected (S3)
  6.  bool target_claim_id rejected (S4)
  7.  target_claim_id mismatch with source_packet claim.id (S5)
  8.  forbidden top-level keys classified (P1/P3/P4/P5/P6/P7)
  9.  unknown random top-level key rejected as S7
  10. inputs are not mutated
  11. validator remains ragcore-free
       (AST-based source check; no import ragcore / from ragcore)
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest  # noqa: F401  -- used by pytest test discovery

from ragcore import (
    Engine,
    RULE_MATURITY_STABLE,
    RuleDefinition,
    ScoreValue,
)


# ============================================================================
# Load modules without sys.path pollution.
# ============================================================================

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
_PROPOSAL_PATH = _EXAMPLES_DIR / "proposal" / "proposal_schema.py"
_INSPECTOR_PATH = _EXAMPLES_DIR / "inspector" / "engine_inspector.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_proposal_schema = _load_module("_proposal_schema_for_test", _PROPOSAL_PATH)
_engine_inspector = _load_module(
    "_engine_inspector_for_proposal_test", _INSPECTOR_PATH
)

validate_llm_proposal_shape = _proposal_schema.validate_llm_proposal_shape
build_engine_context_packet = _engine_inspector.build_engine_context_packet


# ============================================================================
# Test-local helpers.
# ============================================================================


def _make_engine_and_packet() -> tuple[Engine, int, dict]:
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
    packet = build_engine_context_packet(engine, claim_id)
    return engine, claim_id, packet


def _codes(violations: list[tuple[str, str]]) -> list[str]:
    return [code for code, _msg in violations]


# ============================================================================
# Tests — 11 methods.
# ============================================================================


class TestProposalSchema:
    """PR55 locks the minimal shape of LLM proposal drafts.
    It validates structure, not truth or execution authority.
    """

    def test_valid_required_only_proposal_returns_no_violations(self) -> None:
        _, claim_id, packet = _make_engine_and_packet()
        proposal = {
            "category": "uncertainty_note",
            "target_claim_id": claim_id,
            "note": "engine_confidence is low; worth a closer look.",
        }
        assert validate_llm_proposal_shape(proposal, packet) == []

    def test_valid_proposal_with_optional_refs_returns_no_violations(self) -> None:
        _, claim_id, packet = _make_engine_and_packet()
        evidence_id = packet["supporting_evidence"][0].id
        proposal = {
            "category": "evidence_gap_question",
            "target_claim_id": claim_id,
            "note": "what evidence would resolve this gap?",
            "target_evidence_id": evidence_id,
            "target_gap_id": 0,
            "supporting_packet_ref": "opaque-ref-1",
        }
        assert validate_llm_proposal_shape(proposal, packet) == []

    def test_non_dict_proposal_returns_S1_and_does_not_raise(self) -> None:
        _, _, packet = _make_engine_and_packet()
        for non_dict in ("not a dict", None, [], 42, 3.14):
            violations = validate_llm_proposal_shape(non_dict, packet)
            assert _codes(violations) == ["S1"], (
                f"non-dict input {non_dict!r} should produce exactly [S1]"
            )

    def test_missing_required_fields_are_reported_deterministically(self) -> None:
        _, _, packet = _make_engine_and_packet()

        # All three required fields missing.
        violations = validate_llm_proposal_shape({}, packet)
        assert "S2" in _codes(violations)
        # Message should list missing fields in deterministic (sorted)
        # order — for empty dict, all three required fields are missing.
        s2_msg = next(msg for code, msg in violations if code == "S2")
        assert "'category'" in s2_msg
        assert "'note'" in s2_msg
        assert "'target_claim_id'" in s2_msg

        # Only category present — note and target_claim_id missing.
        violations_partial = validate_llm_proposal_shape(
            {"category": "uncertainty_note"}, packet
        )
        assert "S2" in _codes(violations_partial)
        s2_msg_partial = next(
            msg for code, msg in violations_partial if code == "S2"
        )
        assert "'note'" in s2_msg_partial
        assert "'target_claim_id'" in s2_msg_partial

    def test_invalid_category_is_rejected(self) -> None:
        _, claim_id, packet = _make_engine_and_packet()

        # Unknown category string.
        violations = validate_llm_proposal_shape(
            {
                "category": "not_allowed",
                "target_claim_id": claim_id,
                "note": "x",
            },
            packet,
        )
        assert "S3" in _codes(violations)

        # Non-string category (int).
        violations_int = validate_llm_proposal_shape(
            {
                "category": 123,
                "target_claim_id": claim_id,
                "note": "x",
            },
            packet,
        )
        assert "S3" in _codes(violations_int)

    def test_bool_target_claim_id_is_rejected_even_though_bool_is_int_subclass(
        self,
    ) -> None:
        _, _, packet = _make_engine_and_packet()
        for bool_value in (True, False):
            violations = validate_llm_proposal_shape(
                {
                    "category": "uncertainty_note",
                    "target_claim_id": bool_value,
                    "note": "x",
                },
                packet,
            )
            assert "S4" in _codes(violations), (
                f"bool target_claim_id={bool_value!r} should trigger S4"
            )

    def test_target_claim_id_mismatch_with_source_packet_is_rejected(self) -> None:
        _, claim_id, packet = _make_engine_and_packet()

        # Mismatch should trigger S5.
        violations = validate_llm_proposal_shape(
            {
                "category": "uncertainty_note",
                "target_claim_id": claim_id + 999,
                "note": "x",
            },
            packet,
        )
        assert "S5" in _codes(violations)

        # If source_packet has no claim object, S5 must be skipped
        # (validator falls back to S4 type check only and leaves S5
        # cross-check as advisory).
        empty_packet = {}
        violations_no_packet = validate_llm_proposal_shape(
            {
                "category": "uncertainty_note",
                "target_claim_id": 999,
                "note": "x",
            },
            empty_packet,
        )
        assert "S5" not in _codes(violations_no_packet)

    def test_forbidden_top_level_keys_are_classified(self) -> None:
        _, claim_id, packet = _make_engine_and_packet()

        base_proposal = {
            "category": "uncertainty_note",
            "target_claim_id": claim_id,
            "note": "x",
        }

        scenarios: list[tuple[str, dict]] = [
            # P1 verdict
            ("P1", {**base_proposal, "verdict": "TRUE"}),
            ("P1", {**base_proposal, "label": "verified"}),
            ("P1", {**base_proposal, "judgment": "x"}),
            ("P1", {**base_proposal, "decision": "x"}),
            ("P1", {**base_proposal, "ruling": "x"}),

            # P3 status mutation
            ("P3", {**base_proposal, "status_change": "REFUTED"}),
            ("P3", {**base_proposal, "set_status": 2}),
            ("P3", {**base_proposal, "change_status": "x"}),
            ("P3", {**base_proposal, "claim_status_change": "x"}),
            ("P3", {**base_proposal, "force_status": "x"}),

            # P4 tool execution (exact + prefix)
            ("P4", {**base_proposal, "tool_run": "scanner"}),
            ("P4", {**base_proposal, "tool_command": "x"}),
            ("P4", {**base_proposal, "execute_tool": "x"}),
            ("P4", {**base_proposal, "execute_command": "rm -rf /"}),
            ("P4", {**base_proposal, "run_command": "x"}),
            ("P4", {**base_proposal, "run_tool": "x"}),
            ("P4", {**base_proposal, "tool_invocation": "x"}),
            ("P4", {**base_proposal, "execute_something_new": "x"}),  # prefix

            # P5 engine mutation
            ("P5", {**base_proposal, "engine_call": "add_evidence"}),
            ("P5", {**base_proposal, "engine_mutation": {}}),
            ("P5", {**base_proposal, "engine_call_args": {}}),
            ("P5", {**base_proposal, "mutation_payload": {}}),
            ("P5", {**base_proposal, "add_evidence_args": {}}),
            ("P5", {**base_proposal, "add_claim_args": {}}),
            ("P5", {**base_proposal, "add_gap_args": {}}),
            ("P5", {**base_proposal, "add_observation_args": {}}),
            ("P5", {**base_proposal, "add_relation_args": {}}),
            ("P5", {**base_proposal, "engine_write": True}),
            ("P5", {**base_proposal, "engine_writeback": True}),

            # P6 final report
            ("P6", {**base_proposal, "final_report": "x"}),
            ("P6", {**base_proposal, "published": True}),
            ("P6", {**base_proposal, "final_verdict": "x"}),
            ("P6", {**base_proposal, "final_published": True}),
            ("P6", {**base_proposal, "publication_status": "x"}),
            ("P6", {**base_proposal, "report_finalized": True}),

            # P7 threshold verdict
            ("P7", {**base_proposal, "binary_verdict": True}),
            ("P7", {**base_proposal, "threshold_verdict": "TRUE"}),
            ("P7", {**base_proposal, "auto_verdict": "TRUE"}),
            ("P7", {**base_proposal, "threshold_decision": "TRUE"}),
        ]

        for expected_pid, proposal in scenarios:
            violations = validate_llm_proposal_shape(proposal, packet)
            assert expected_pid in _codes(violations), (
                f"proposal {sorted(proposal.keys())} should trigger "
                f"{expected_pid}; got codes {_codes(violations)}"
            )

    def test_unknown_random_top_level_key_is_rejected_as_S7(self) -> None:
        _, claim_id, packet = _make_engine_and_packet()

        # An unknown key that does NOT match any P_id pattern.
        violations = validate_llm_proposal_shape(
            {
                "category": "uncertainty_note",
                "target_claim_id": claim_id,
                "note": "x",
                "random_unknown_field": 1,
            },
            packet,
        )
        codes = _codes(violations)
        assert "S7" in codes
        # Should NOT misclassify as any P_id.
        for pid in ("P1", "P3", "P4", "P5", "P6", "P7"):
            assert pid not in codes

        # Mixing a P_id key with a random unknown key — both reported.
        violations_mixed = validate_llm_proposal_shape(
            {
                "category": "uncertainty_note",
                "target_claim_id": claim_id,
                "note": "x",
                "verdict": "TRUE",
                "random_unknown_field": 1,
            },
            packet,
        )
        codes_mixed = _codes(violations_mixed)
        assert "P1" in codes_mixed
        assert "S7" in codes_mixed

    def test_inputs_are_not_mutated(self) -> None:
        _, claim_id, packet = _make_engine_and_packet()

        proposal = {
            "category": "uncertainty_note",
            "target_claim_id": claim_id,
            "note": "x",
            "verdict": "TRUE",  # forbidden, will trigger P1
        }
        # Snapshot input identity + keys + packet keys.
        proposal_keys_before = set(proposal.keys())
        proposal_id_before = id(proposal)
        packet_keys_before = set(packet.keys())

        _ = validate_llm_proposal_shape(proposal, packet)

        # Inputs must remain identical objects with identical keys.
        assert id(proposal) == proposal_id_before
        assert set(proposal.keys()) == proposal_keys_before
        assert proposal["verdict"] == "TRUE"
        assert set(packet.keys()) == packet_keys_before

    def test_validator_remains_ragcore_free(self) -> None:
        # AST-based static check: examples/proposal/proposal_schema.py
        # must NOT contain `import ragcore` or `from ragcore ...`.
        # The validator design lock (PR55 / direction_rag_framework_proposal_layer)
        # requires the consumer-side validator to be fully ragcore-free.
        src = _PROPOSAL_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("ragcore"), (
                        f"proposal_schema.py must not import ragcore; "
                        f"found `import {alias.name}`"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("ragcore"), (
                    f"proposal_schema.py must not import from ragcore; "
                    f"found `from {module} import ...`"
                )
