"""PR56 / 198차 — proposal safety validator invariants.

Locked (user 2026-05-25):
  PR56 locks proposal safety interpretation.
  It catches unsafe nested or structural proposal identifiers.
  It does not inspect free-text meaning.
  It does not judge claims.
  It does not execute tools.
  It does not mutate Engine state.

14 invariants verified:
  1.  valid PR55-compatible proposal returns []
  2.  nested P1 verdict-like key triggers
  3.  nested P3 status mutation key triggers
  4.  nested P4 tool execution key triggers (+ execute_ prefix)
  5.  nested P5 engine mutation key triggers
  6.  nested P6 final report key triggers
  7.  nested P7 threshold verdict key triggers
  8.  P2 probability-like identifiers at any path
       (top-level + nested + list-path)
  9.  P8 domain vocabulary identifiers at any path
       (cve_id / scan_host_port / nested ssh / nmap / service / asset)
  10. P8 false-positive prevention
       (hostname / portable / serviceable do NOT trigger)
  11. PR55 territory separation
       (top-level verdict NOT caught by PR56 — that is PR55's job)
  12. inputs not mutated
  13. validator remains ragcore-free (AST check)
  14. PR55 + PR56 compatibility — safe proposal passes both
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest  # noqa: F401  -- used by pytest test discovery


# ============================================================================
# Load examples/proposal/* modules without sys.path pollution.
# ============================================================================

_EXAMPLES_PROPOSAL_DIR = (
    Path(__file__).resolve().parent.parent / "examples" / "proposal"
)
_VALIDATOR_PATH = _EXAMPLES_PROPOSAL_DIR / "proposal_validator.py"
_SCHEMA_PATH = _EXAMPLES_PROPOSAL_DIR / "proposal_schema.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_proposal_validator = _load_module(
    "_proposal_validator_for_test", _VALIDATOR_PATH
)
_proposal_schema = _load_module(
    "_proposal_schema_for_safety_test", _SCHEMA_PATH
)

validate_proposal_safety = _proposal_validator.validate_proposal_safety
validate_llm_proposal_shape = _proposal_schema.validate_llm_proposal_shape


# ============================================================================
# Test-local helpers.
# ============================================================================


def _base_proposal() -> dict:
    """A PR55-shape-valid baseline proposal."""
    return {
        "category": "uncertainty_note",
        "target_claim_id": 1,
        "note": "engine_confidence is low; worth a closer look.",
    }


def _codes(violations: list[tuple[str, str]]) -> list[str]:
    return [code for code, _msg in violations]


# Minimal source_packet stub — PR56 does not consult source_packet,
# so an empty dict is sufficient. PR55 cross-check (S5) is out of
# scope for these tests.
_EMPTY_PACKET: dict = {}


# ============================================================================
# Tests — 14 methods.
# ============================================================================


class TestProposalSafetyValidator:
    """PR56 catches unsafe nested or structural proposal
    identifiers. It does not inspect free-text meaning.
    """

    def test_valid_pr55_compatible_proposal_returns_no_safety_violations(
        self,
    ) -> None:
        assert validate_proposal_safety(_base_proposal(), _EMPTY_PACKET) == []

    def test_nested_P1_verdict_like_key_triggers(self) -> None:
        for verdict_key in ("verdict", "label", "judgment", "decision", "ruling"):
            proposal = {**_base_proposal(), "meta": {verdict_key: "TRUE"}}
            violations = validate_proposal_safety(proposal, _EMPTY_PACKET)
            assert "P1" in _codes(violations), (
                f"nested {verdict_key!r} should trigger P1; "
                f"got {_codes(violations)}"
            )

    def test_nested_P3_status_mutation_key_triggers(self) -> None:
        for key in (
            "status_change",
            "set_status",
            "change_status",
            "claim_status_change",
            "force_status",
        ):
            proposal = {**_base_proposal(), "plan": {key: "REFUTED"}}
            assert "P3" in _codes(
                validate_proposal_safety(proposal, _EMPTY_PACKET)
            ), f"nested {key!r} should trigger P3"

    def test_nested_P4_tool_execution_key_triggers(self) -> None:
        # Exact keys.
        for key in (
            "tool_run",
            "tool_command",
            "execute_tool",
            "execute_command",
            "run_command",
            "run_tool",
            "tool_invocation",
        ):
            proposal = {**_base_proposal(), "plan": {key: "x"}}
            assert "P4" in _codes(
                validate_proposal_safety(proposal, _EMPTY_PACKET)
            ), f"nested {key!r} should trigger P4"

        # execute_ prefix.
        proposal = {**_base_proposal(), "plan": {"execute_something_new": "x"}}
        assert "P4" in _codes(
            validate_proposal_safety(proposal, _EMPTY_PACKET)
        )

    def test_nested_P5_engine_mutation_key_triggers(self) -> None:
        for key in (
            "engine_call",
            "engine_mutation",
            "engine_call_args",
            "mutation_payload",
            "add_evidence_args",
            "add_claim_args",
            "add_gap_args",
            "add_observation_args",
            "add_relation_args",
            "engine_write",
            "engine_writeback",
        ):
            proposal = {**_base_proposal(), "draft": {key: {}}}
            assert "P5" in _codes(
                validate_proposal_safety(proposal, _EMPTY_PACKET)
            ), f"nested {key!r} should trigger P5"

    def test_nested_P6_final_report_key_triggers(self) -> None:
        for key in (
            "final_report",
            "published",
            "final_verdict",
            "final_published",
            "publication_status",
            "report_finalized",
        ):
            proposal = {**_base_proposal(), "wrapper": {key: True}}
            assert "P6" in _codes(
                validate_proposal_safety(proposal, _EMPTY_PACKET)
            ), f"nested {key!r} should trigger P6"

    def test_nested_P7_threshold_verdict_key_triggers(self) -> None:
        for key in (
            "binary_verdict",
            "threshold_verdict",
            "auto_verdict",
            "threshold_decision",
        ):
            proposal = {**_base_proposal(), "score_block": {key: True}}
            assert "P7" in _codes(
                validate_proposal_safety(proposal, _EMPTY_PACKET)
            ), f"nested {key!r} should trigger P7"

    def test_P2_probability_like_identifiers_at_any_path(self) -> None:
        # Top-level (depth 0).
        proposal = {**_base_proposal(), "probability": 0.8}
        violations = validate_proposal_safety(proposal, _EMPTY_PACKET)
        assert "P2" in _codes(violations)
        # path string should mention the top-level key name.
        msg = next(m for c, m in violations if c == "P2")
        assert "probability" in msg

        # Nested truth_probability.
        proposal_nested = {
            **_base_proposal(),
            "meta": {"truth_probability": 0.9},
        }
        violations_nested = validate_proposal_safety(
            proposal_nested, _EMPTY_PACKET
        )
        assert "P2" in _codes(violations_nested)

        # List path: items[0].p_true.
        proposal_list = {
            **_base_proposal(),
            "items": [{"p_true": 0.7}, {"note_only": "ok"}],
        }
        violations_list = validate_proposal_safety(
            proposal_list, _EMPTY_PACKET
        )
        assert "P2" in _codes(violations_list)
        list_msg = next(m for c, m in violations_list if c == "P2")
        assert "items[0]" in list_msg

        # Prefix forms: probability_of_*, prob_of_*, p_true_*.
        for prefix_key in (
            "probability_of_true",
            "prob_of_match",
            "p_true_value",
        ):
            proposal_pre = {**_base_proposal(), prefix_key: 0.5}
            assert "P2" in _codes(
                validate_proposal_safety(proposal_pre, _EMPTY_PACKET)
            ), f"prefix key {prefix_key!r} should trigger P2"

    def test_P8_domain_vocabulary_identifiers_at_any_path(self) -> None:
        # Component-level match scenarios.
        scenarios = [
            {**_base_proposal(), "meta": {"cve_id": "CVE-2024"}},
            {**_base_proposal(), "scan_host_port": 22},
            {**_base_proposal(), "deep": {"ssh_session": True}},
            {**_base_proposal(), "tooling": {"nmap_output": "x"}},
            {**_base_proposal(), "service_descriptor": "ftp"},
            {**_base_proposal(), "asset_id": 99},
            {**_base_proposal(), "list_field": [{"vulnerability_ref": "x"}]},
            {**_base_proposal(), "data": {"scanner_name": "x"}},
            {**_base_proposal(), "ctx": {"exploit_chain": []}},
            {**_base_proposal(), "ctx": {"cerberus_module": "x"}},
        ]
        for proposal in scenarios:
            assert "P8" in _codes(
                validate_proposal_safety(proposal, _EMPTY_PACKET)
            ), (
                f"proposal {sorted(proposal.keys())} should trigger P8; "
                f"got {_codes(validate_proposal_safety(proposal, _EMPTY_PACKET))}"
            )

    def test_P8_false_positive_prevention(self) -> None:
        # Compound identifiers where the forbidden word appears as a
        # substring but NOT as a word-boundary component MUST NOT
        # trigger P8. This is the critical false-positive guard.
        non_triggering = [
            {**_base_proposal(), "hostname": "srv-01"},          # not "host"
            {**_base_proposal(), "portable": True},               # not "port"
            {**_base_proposal(), "serviceable": True},            # not "service"
            {**_base_proposal(), "assets_count": 5},              # not "asset"
            {**_base_proposal(), "exploitable": False},          # not "exploit"
            {**_base_proposal(), "ssh_handle": "x"},              # word-bounded — DOES trigger
                                                                  # (placed here to NEGATE below)
        ]

        # The first 5 must NOT trigger P8.
        for proposal in non_triggering[:5]:
            violations = validate_proposal_safety(proposal, _EMPTY_PACKET)
            assert "P8" not in _codes(violations), (
                f"compound non-bound identifier in {sorted(proposal.keys())} "
                f"should NOT trigger P8; got {_codes(violations)}"
            )

        # Control: the 6th entry SHOULD trigger P8 (sanity that the
        # word-boundary policy is still active).
        violations_ssh = validate_proposal_safety(
            non_triggering[5], _EMPTY_PACKET
        )
        assert "P8" in _codes(violations_ssh)

    def test_PR55_territory_separation(self) -> None:
        # Top-level verdict-like keys are PR55's territory (S7 + P1
        # at top level). PR56 must NOT catch them.
        for top_key in ("verdict", "label", "judgment", "decision", "ruling"):
            proposal = {**_base_proposal(), top_key: "TRUE"}
            violations = validate_proposal_safety(proposal, _EMPTY_PACKET)
            assert "P1" not in _codes(violations), (
                f"top-level {top_key!r} should NOT trigger PR56 P1 "
                f"(it is PR55's territory); got {_codes(violations)}"
            )

        # But a nested verdict-like key MUST trigger PR56 P1.
        proposal_nested = {**_base_proposal(), "meta": {"verdict": "TRUE"}}
        assert "P1" in _codes(
            validate_proposal_safety(proposal_nested, _EMPTY_PACKET)
        )

    def test_inputs_are_not_mutated(self) -> None:
        proposal = {
            **_base_proposal(),
            "meta": {"verdict": "TRUE"},          # nested P1 (triggers)
            "probability": 0.8,                    # P2 (triggers)
            "scan_host_port": 22,                  # P8 (triggers)
        }
        proposal_id_before = id(proposal)
        proposal_keys_before = set(proposal.keys())
        meta_id_before = id(proposal["meta"])

        packet = {"some_field": "x"}
        packet_keys_before = set(packet.keys())

        _ = validate_proposal_safety(proposal, packet)

        # proposal identity, top-level keys, nested dict identity preserved.
        assert id(proposal) == proposal_id_before
        assert set(proposal.keys()) == proposal_keys_before
        assert id(proposal["meta"]) == meta_id_before
        assert proposal["meta"] == {"verdict": "TRUE"}
        # packet keys preserved.
        assert set(packet.keys()) == packet_keys_before

    def test_validator_remains_ragcore_free(self) -> None:
        # AST-based static check: examples/proposal/proposal_validator.py
        # must NOT contain `import ragcore` or `from ragcore ...`.
        # PR56 design lock: validator is ragcore-free at runtime.
        src = _VALIDATOR_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("ragcore"), (
                        f"proposal_validator.py must not import ragcore; "
                        f"found `import {alias.name}`"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("ragcore"), (
                    f"proposal_validator.py must not import from "
                    f"ragcore; found `from {module} import ...`"
                )

    def test_PR55_and_PR56_compatibility_safe_proposal_passes_both(self) -> None:
        # A neutral, PR54 §5 / §6 - aligned proposal must pass BOTH
        # PR55 shape validator and PR56 safety validator.
        proposal = _base_proposal()

        # PR55 needs a source_packet whose claim.id matches; build a
        # minimal duck-typed packet.
        class _FakeClaim:
            id = proposal["target_claim_id"]

        packet = {"claim": _FakeClaim()}

        pr55_violations = validate_llm_proposal_shape(proposal, packet)
        pr56_violations = validate_proposal_safety(proposal, packet)

        assert pr55_violations == [], (
            f"PR55 should pass the safe proposal; got {pr55_violations}"
        )
        assert pr56_violations == [], (
            f"PR56 should pass the safe proposal; got {pr56_violations}"
        )

        # PR56's value over PR55 shows up when PR55 strict shape is
        # bypassed and a consumer uses a shape-relaxed proposal. In
        # that mode, PR55 will reject the unknown top-level key (S7)
        # AND PR56 independently catches the nested forbidden key.
        # The two validators are independent — composing them gives
        # strictest safety; using either alone gives partial cover.
        relaxed_unsafe = {**proposal, "meta": {"probability_of_true": 0.9}}

        # PR55 catches the unknown top-level key "meta" as S7 (strict
        # shape mode). This is the intended behavior; PR55 owns the
        # shape boundary.
        pr55_relaxed = validate_llm_proposal_shape(relaxed_unsafe, packet)
        assert "S7" in _codes(pr55_relaxed)

        # PR56 independently catches the nested probability identifier
        # as P2 — regardless of whether PR55 also flagged the shape
        # via S7. The two validators are decoupled.
        pr56_relaxed = validate_proposal_safety(relaxed_unsafe, packet)
        assert "P2" in _codes(pr56_relaxed)
