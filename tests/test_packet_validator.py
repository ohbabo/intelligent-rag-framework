"""PR53 / 190차 — consumer packet validator forbidden-reading detection.

Locked (user 2026-05-25):
  The validator detects unsafe consumer interpretations.
  It does not create Engine truth.

Six forbidden readings (PR52 §5 subset) are verified to trigger:
  F3   evidence.strength exposed as probability
  F5   contradictions non-empty → auto refutation
  F7   unresolved_gaps → refutation
  F10  Claim.status renamed to verdict / label / judgment
  F12  threshold → auto true / verified
  F13  raw_ref_id used as engine mutation payload (intent only)

F5 / F7 false-positive skip (claim.status == CLAIM_STATUS_REFUTED)
is asserted inside the same F5 / F7 tests, so the test count
stays at 7.

Seventh test verifies that a neutral, well-shaped consumer_output
produces zero violations.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest  # noqa: F401  -- used by pytest test discovery

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_REFUTED,
    Engine,
    RULE_MATURITY_STABLE,
    RuleDefinition,
    ScoreValue,
)


# ============================================================================
# Load examples/inspector/* modules without sys.path pollution.
# ============================================================================

_EXAMPLES_DIR = (
    Path(__file__).resolve().parent.parent / "examples" / "inspector"
)


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        name, _EXAMPLES_DIR / filename
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_engine_inspector = _load_module("_engine_inspector_for_validator_test", "engine_inspector.py")
_packet_validator = _load_module("_packet_validator_for_validator_test", "packet_validator.py")

build_engine_context_packet = _engine_inspector.build_engine_context_packet
validate_consumer_packet_interpretation = (
    _packet_validator.validate_consumer_packet_interpretation
)


# ============================================================================
# Test-local helpers.
# ============================================================================


def _make_engine_with_claim(
    *,
    status: int = CLAIM_STATUS_CANDIDATE,
    with_contradiction: bool = False,
    with_unresolved_gap: bool = False,
) -> tuple[Engine, int]:
    """Construct an Engine + a single Claim at the requested status.

    Optionally add a contradicting evidence (registered as
    contradiction) and an unresolved Gap, to drive F5 / F7 scenarios.
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
        status=status,
    )
    # supporting evidence so the packet is non-trivial
    engine.add_evidence(
        claim_id=claim_id,
        raw_ref_id=101,
        evidence_type=50,
        strength=0.8,
    )
    if with_contradiction:
        opposing = engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=200,
            evidence_type=51,
            strength=0.7,
        )
        engine.register_contradiction(claim_id=claim_id, evidence_id=opposing)
    if with_unresolved_gap:
        engine.add_gap(
            claim_id=claim_id,
            gap_type=60,
            required_evidence_type=70,
            severity=0.5,
            rule_id=1,
        )
    return engine, claim_id


def _collect_f_ids(violations: list[tuple[str, str]]) -> set[str]:
    return {f_id for f_id, _msg in violations}


# ============================================================================
# Tests — 7 methods.
# ============================================================================


class TestConsumerPacketValidator:
    """The validator detects unsafe consumer interpretations.
    It does not create Engine truth.
    """

    def test_F3_evidence_strength_probability_label_detected(self) -> None:
        engine, claim_id = _make_engine_with_claim()
        packet = build_engine_context_packet(engine, claim_id)

        # Consumer derived dict exposes evidence strength under
        # a probability-named key.
        consumer_output = {
            "evidence_summary": {"probability": 0.8},
        }
        violations = validate_consumer_packet_interpretation(
            consumer_output, packet
        )
        assert "F3" in _collect_f_ids(violations)

        # Prefix variants also trigger.
        for prob_key in (
            "prob",
            "p_true",
            "probability_of_true",
            "prob_of_match",
            "p_true_value",
        ):
            consumer_output = {prob_key: 0.5}
            assert "F3" in _collect_f_ids(
                validate_consumer_packet_interpretation(consumer_output, packet)
            ), f"F3 should trigger on key '{prob_key}'"

    def test_F5_contradictions_auto_refutation_detected(self) -> None:
        # Setup: contradictions non-empty, claim NOT yet REFUTED.
        engine, claim_id = _make_engine_with_claim(
            status=CLAIM_STATUS_CANDIDATE,
            with_contradiction=True,
        )
        packet = build_engine_context_packet(engine, claim_id)
        assert len(packet["contradictions"]) > 0

        consumer_output = {"final": {"outcome": "refuted"}}
        violations = validate_consumer_packet_interpretation(
            consumer_output, packet
        )
        assert "F5" in _collect_f_ids(violations)

        # False-positive skip: when Engine has already transitioned
        # the claim to REFUTED via an explicit refute_*_if_ready
        # call, the same consumer_output should NOT trigger F5 —
        # the "refuted" label there is simply restating the Engine
        # result, not an unsafe auto-inference.
        engine2, claim_id2 = _make_engine_with_claim(
            status=CLAIM_STATUS_REFUTED,
            with_contradiction=True,
        )
        packet_refuted = build_engine_context_packet(engine2, claim_id2)
        assert packet_refuted["claim"].status == CLAIM_STATUS_REFUTED
        violations_refuted = validate_consumer_packet_interpretation(
            consumer_output, packet_refuted
        )
        assert "F5" not in _collect_f_ids(violations_refuted)

    def test_F7_unresolved_gaps_refutation_detected(self) -> None:
        # Setup: unresolved_gaps non-empty, claim NOT yet REFUTED.
        engine, claim_id = _make_engine_with_claim(
            status=CLAIM_STATUS_CANDIDATE,
            with_unresolved_gap=True,
        )
        packet = build_engine_context_packet(engine, claim_id)
        assert len(packet["unresolved_gaps"]) > 0

        consumer_output = {"conclusion": "rejected"}
        violations = validate_consumer_packet_interpretation(
            consumer_output, packet
        )
        assert "F7" in _collect_f_ids(violations)

        # False-positive skip: when Engine claim status is already
        # REFUTED, the same consumer_output should NOT trigger F7.
        engine2, claim_id2 = _make_engine_with_claim(
            status=CLAIM_STATUS_REFUTED,
            with_unresolved_gap=True,
        )
        packet_refuted = build_engine_context_packet(engine2, claim_id2)
        assert packet_refuted["claim"].status == CLAIM_STATUS_REFUTED
        violations_refuted = validate_consumer_packet_interpretation(
            consumer_output, packet_refuted
        )
        assert "F7" not in _collect_f_ids(violations_refuted)

    def test_F10_status_verdict_relabel_detected(self) -> None:
        engine, claim_id = _make_engine_with_claim()
        packet = build_engine_context_packet(engine, claim_id)

        for verdict_key in ("verdict", "label", "judgment", "decision", "ruling"):
            consumer_output = {verdict_key: "anything"}
            violations = validate_consumer_packet_interpretation(
                consumer_output, packet
            )
            assert "F10" in _collect_f_ids(violations), (
                f"F10 should trigger on key '{verdict_key}'"
            )

        # Nested verdict key should also trigger.
        consumer_output = {"summary": {"nested": {"verdict": "anything"}}}
        assert "F10" in _collect_f_ids(
            validate_consumer_packet_interpretation(consumer_output, packet)
        )

    def test_F12_threshold_auto_verified_detected(self) -> None:
        engine, claim_id = _make_engine_with_claim()
        packet = build_engine_context_packet(engine, claim_id)

        # Boolean values trigger F12.
        for verified_key in (
            "verified",
            "is_true",
            "auto_true",
            "is_confirmed",
            "auto_confirmed",
        ):
            consumer_output = {verified_key: True}
            assert "F12" in _collect_f_ids(
                validate_consumer_packet_interpretation(consumer_output, packet)
            ), f"F12 should trigger on '{verified_key}: True'"

        # Same key with a non-boolean (e.g., string note) should NOT
        # trigger F12 — the key-name-only heuristic without the
        # boolean check would false-positive on legitimate free-text
        # notes like "verified_by: 'analyst-7'".
        consumer_output = {"verified": "maybe"}
        assert "F12" not in _collect_f_ids(
            validate_consumer_packet_interpretation(consumer_output, packet)
        )

    def test_F13_raw_ref_engine_mutation_intent_detected(self) -> None:
        engine, claim_id = _make_engine_with_claim()
        packet = build_engine_context_packet(engine, claim_id)

        for mutation_key in (
            "engine_mutation",
            "engine_call_args",
            "mutation_payload",
            "add_evidence_args",
            "add_claim_args",
            "add_gap_args",
            "add_observation_args",
            "engine_write",
            "engine_writeback",
        ):
            consumer_output = {mutation_key: {"raw_ref_id": 999}}
            assert "F13" in _collect_f_ids(
                validate_consumer_packet_interpretation(consumer_output, packet)
            ), f"F13 should trigger on key '{mutation_key}'"

    def test_valid_consumer_output_returns_no_violations(self) -> None:
        # A neutral, well-shaped consumer_output should produce zero
        # violations. Uses safe vocabulary aligned with PR52 §6:
        # engine_confidence / computed_signal / opaque ids / counts.
        engine, claim_id = _make_engine_with_claim(
            with_contradiction=True,
            with_unresolved_gap=True,
        )
        packet = build_engine_context_packet(engine, claim_id)

        consumer_output = {
            "claim_summary": {
                "subject_id": packet["claim"].subject_id,
                "engine_claim_type_int": packet["claim"].type,
                "lifecycle_phase": "CANDIDATE",
                "engine_confidence": packet["effective_confidence"].value,
            },
            "evidence_list": [
                {
                    "opaque_id": ev.id,
                    "evidence_type": ev.type,
                    "engine_strength": ev.strength.value,
                }
                for ev in packet["supporting_evidence"]
            ],
            "missing_information_count": len(packet["unresolved_gaps"]),
            "active_conflicts_count": len(packet["active_contradictions"]),
            "lifecycle_event_count": len(packet["lifecycle_history"]),
        }
        violations = validate_consumer_packet_interpretation(
            consumer_output, packet
        )
        assert violations == [], (
            f"valid consumer_output should produce zero violations, "
            f"got: {violations}"
        )
