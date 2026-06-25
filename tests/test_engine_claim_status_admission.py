"""Tests for §51 — Claim Status Admission Domain.

These tests lock the admission gate for ``Claim.status`` per
``docs/contracts/05_DATA_CONTRACT_MVP.md`` §51.

Two admission paths are covered:

  - ``Engine.add_claim()``     (§51.3 fail-fast at admission)
  - ``Engine.from_snapshot()`` (§51.4 restore-time rejection)

Per §51.2 exact-int requirement:

  - ``bool`` is rejected even though Python treats ``bool`` as an
    ``int`` subclass.
  - A ``float`` is rejected even when its numeric value equals a
    status constant (e.g. ``1.0`` is not ``CLAIM_STATUS_CONFIRMED``).
  - ``str`` / ``None`` / out-of-range ``int`` are rejected.

Per §51.5 error type convention:

  - Non-int / ``bool`` / ``None`` / ``str`` / ``float`` raises
    ``TypeError``.
  - An ``int`` that is not one of the four admissible constants
    raises ``ValueError``.

Per §51.3 mutation safety:

  - The Engine snapshot before a rejected ``add_claim`` equals the
    Engine snapshot after the rejection.
  - A subsequent valid ``add_claim`` receives the next sequential
    claim ID (rejection does not consume an ID).

Per §51.4 restore safety:

  - ``from_snapshot`` rejects a snapshot containing an invalid
    Claim.status without returning an Engine.
  - The input snapshot dictionary is not mutated.
"""

from __future__ import annotations

import copy
from enum import IntEnum

import pytest

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    Engine,
)


# ---------------------------------------------------------------------------
# Exact-built-in-int helpers (§51.2)
# ---------------------------------------------------------------------------

# A non-bool int subclass. Numerically equal to a valid status constant
# but rejected because its type is not the built-in ``int`` (§51.2).
class _DerivedInt(int):
    pass


# An IntEnum member numerically equal to a valid status constant; still
# an int subclass, so rejected by the exact-built-in-int gate (§51.2).
class _StatusLikeIntEnum(IntEnum):
    CONFIRMED_LIKE = CLAIM_STATUS_CONFIRMED


# Admissible status set, derived in the test from the four public status
# constants (NOT from any private Engine symbol). Matches the admissible
# set that §51.5 ValueError messages must expose.
ADMISSIBLE_STATUSES: list[int] = sorted(
    [
        CLAIM_STATUS_CANDIDATE,
        CLAIM_STATUS_CONFIRMED,
        CLAIM_STATUS_REFUTED,
        CLAIM_STATUS_DISPUTED,
    ]
)


# ---------------------------------------------------------------------------
# Invalid value catalogues
# ---------------------------------------------------------------------------

# (label, value) — values whose Python type is not int (or is bool, which
# is an int subclass but rejected by §51.2).
INVALID_STATUS_TYPE_VALUES: list[tuple[str, object]] = [
    ("bool_true", True),
    ("bool_false", False),
    ("str_word", "candidate"),
    ("str_digit", "1"),
    ("none", None),
    ("float_zero", 0.0),
    ("float_one", 1.0),
    ("float_three", 3.0),
    ("float_out_of_range", 999.0),
    # §51.2 — non-bool int subclasses are rejected even when numerically
    # equal to a valid status constant (type is not the built-in int).
    ("derived_int_equals_confirmed", _DerivedInt(CLAIM_STATUS_CONFIRMED)),
    ("intenum_equals_confirmed", _StatusLikeIntEnum.CONFIRMED_LIKE),
]

# (label, value) — values whose Python type IS int but the value is not
# one of the four admissible constants.
INVALID_STATUS_VALUE_INTS: list[tuple[str, int]] = [
    ("negative", -1),
    ("just_above_max", 4),
    ("far_above_max", 999),
]

VALID_STATUSES: list[tuple[str, int]] = [
    ("candidate", CLAIM_STATUS_CANDIDATE),
    ("confirmed", CLAIM_STATUS_CONFIRMED),
    ("refuted", CLAIM_STATUS_REFUTED),
    ("disputed", CLAIM_STATUS_DISPUTED),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seeded_engine() -> tuple[Engine, int]:
    engine = Engine()
    entity_id = engine.add_entity(entity_type=1)
    return engine, entity_id


def _baseline_snapshot(engine: Engine) -> dict:
    return copy.deepcopy(engine.to_snapshot())


# ---------------------------------------------------------------------------
# §51.3 — add_claim admission
# ---------------------------------------------------------------------------


class TestAddClaimRejectsInvalidStatusType:
    """Non-int / bool / None / str / float raise TypeError."""

    @pytest.mark.parametrize(
        ("label", "value"), INVALID_STATUS_TYPE_VALUES,
    )
    def test_rejects_with_type_error(self, label: str, value: object) -> None:
        engine, entity_id = _seeded_engine()
        with pytest.raises(TypeError) as exc_info:
            engine.add_claim(
                subject_id=entity_id,
                claim_type=1,
                rule_id=1,
                rule_version=1,
                reason_code=0,
                status=value,  # type: ignore[arg-type]
            )
        # §51.5 — TypeError message carries the offending runtime type name.
        assert type(value).__name__ in str(exc_info.value)


class TestAddClaimRejectsInvalidStatusValue:
    """Out-of-range int values raise ValueError."""

    @pytest.mark.parametrize(
        ("label", "value"), INVALID_STATUS_VALUE_INTS,
    )
    def test_rejects_with_value_error(self, label: str, value: int) -> None:
        engine, entity_id = _seeded_engine()
        with pytest.raises(ValueError) as exc_info:
            engine.add_claim(
                subject_id=entity_id,
                claim_type=1,
                rule_id=1,
                rule_version=1,
                reason_code=0,
                status=value,
            )
        # §51.5 — ValueError message carries the offending value and the
        # admissible set (derived here from the public status constants).
        message = str(exc_info.value)
        assert str(value) in message
        assert str(ADMISSIBLE_STATUSES) in message


class TestAddClaimRejectionDoesNotMutateState:
    """§51.3 — snapshot before == snapshot after rejection."""

    @pytest.mark.parametrize(
        ("label", "value"),
        INVALID_STATUS_TYPE_VALUES + INVALID_STATUS_VALUE_INTS,
    )
    def test_snapshot_unchanged(self, label: str, value: object) -> None:
        engine, entity_id = _seeded_engine()
        before = _baseline_snapshot(engine)
        with pytest.raises((TypeError, ValueError)):
            engine.add_claim(
                subject_id=entity_id,
                claim_type=1,
                rule_id=1,
                rule_version=1,
                reason_code=0,
                status=value,  # type: ignore[arg-type]
            )
        after = engine.to_snapshot()
        assert after == before

    @pytest.mark.parametrize(
        ("label", "value"),
        INVALID_STATUS_TYPE_VALUES + INVALID_STATUS_VALUE_INTS,
    )
    def test_next_claim_id_not_consumed(
        self, label: str, value: object,
    ) -> None:
        """A valid add_claim after a rejection gets the next sequential ID."""
        engine, entity_id = _seeded_engine()

        # Pre-rejection: register a valid claim to fix the counter position.
        first_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=1,
            rule_id=1,
            rule_version=1,
            reason_code=0,
        )

        with pytest.raises((TypeError, ValueError)):
            engine.add_claim(
                subject_id=entity_id,
                claim_type=1,
                rule_id=1,
                rule_version=1,
                reason_code=0,
                status=value,  # type: ignore[arg-type]
            )

        next_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=1,
            rule_id=1,
            rule_version=1,
            reason_code=0,
        )
        assert next_id == first_id + 1


class TestAddClaimAdmitsValidStatuses:
    """All four constants are admissible (§51.1)."""

    @pytest.mark.parametrize(("label", "status"), VALID_STATUSES)
    def test_admits_constant(self, label: str, status: int) -> None:
        engine, entity_id = _seeded_engine()
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=1,
            rule_id=1,
            rule_version=1,
            reason_code=0,
            status=status,
        )
        assert engine.get_claim(claim_id).status == status


# ---------------------------------------------------------------------------
# §51.4 — from_snapshot rejection
# ---------------------------------------------------------------------------


def _valid_single_claim_snapshot() -> dict:
    engine, entity_id = _seeded_engine()
    engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=1,
        rule_version=1,
        reason_code=0,
    )
    return engine.to_snapshot()


def _mutate_claim_status(snapshot: dict, new_status: object) -> dict:
    out = copy.deepcopy(snapshot)
    out["claims"][0]["value"]["status"] = new_status
    return out


class TestFromSnapshotRejectsInvalidStatusType:
    """Non-int / bool / str / None / float in claims raises TypeError."""

    @pytest.mark.parametrize(
        ("label", "value"), INVALID_STATUS_TYPE_VALUES,
    )
    def test_rejects_with_type_error(self, label: str, value: object) -> None:
        base = _valid_single_claim_snapshot()
        mutated = _mutate_claim_status(base, value)
        with pytest.raises(TypeError) as exc_info:
            Engine.from_snapshot(mutated)
        # §51.5 — TypeError message carries the offending runtime type name.
        assert type(value).__name__ in str(exc_info.value)


class TestFromSnapshotRejectsInvalidStatusValue:
    """Out-of-range int in claims raises ValueError."""

    @pytest.mark.parametrize(
        ("label", "value"), INVALID_STATUS_VALUE_INTS,
    )
    def test_rejects_with_value_error(self, label: str, value: int) -> None:
        base = _valid_single_claim_snapshot()
        mutated = _mutate_claim_status(base, value)
        with pytest.raises(ValueError) as exc_info:
            Engine.from_snapshot(mutated)
        # §51.5 — ValueError message carries the offending value and the
        # admissible set (derived here from the public status constants).
        message = str(exc_info.value)
        assert str(value) in message
        assert str(ADMISSIBLE_STATUSES) in message


class TestFromSnapshotDoesNotMutateInput:
    """§51.4 — input snapshot dict is not mutated on rejection."""

    @pytest.mark.parametrize(
        ("label", "value"),
        INVALID_STATUS_TYPE_VALUES + INVALID_STATUS_VALUE_INTS,
    )
    def test_input_dict_unchanged(self, label: str, value: object) -> None:
        base = _valid_single_claim_snapshot()
        mutated = _mutate_claim_status(base, value)
        before = copy.deepcopy(mutated)
        with pytest.raises((TypeError, ValueError)):
            Engine.from_snapshot(mutated)
        assert mutated == before


class TestFromSnapshotValidRoundTrip:
    """Regression — valid v2 snapshot still round-trips for all four
    admissible statuses."""

    @pytest.mark.parametrize(("label", "status"), VALID_STATUSES)
    def test_round_trip(self, label: str, status: int) -> None:
        engine, entity_id = _seeded_engine()
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=1,
            rule_id=1,
            rule_version=1,
            reason_code=0,
            status=status,
        )
        snapshot = engine.to_snapshot()
        before = copy.deepcopy(snapshot)
        restored = Engine.from_snapshot(snapshot)
        assert restored.get_claim(claim_id).status == status
        # Input snapshot still intact after a successful restore.
        assert snapshot == before


# ---------------------------------------------------------------------------
# §51.4 — supported v1 migration path
# ---------------------------------------------------------------------------

# (label, invalid status value, expected exception) for a supported v1
# snapshot whose single claim carries an invalid Claim.status.
V1_INVALID_STATUS_CASES: list[tuple[str, object, type]] = [
    ("v1_bool_true", True, TypeError),
    ("v1_float_one", 1.0, TypeError),
    ("v1_out_of_range", 999, ValueError),
]


def _valid_v1_snapshot() -> dict:
    """A supported v1-shape snapshot built from a valid current snapshot.

    The v1->v2 migration step (PR21-L §33) only adds the
    ``hint_evidence_types`` default, so a faithful v1 shape is the
    current snapshot with that key removed and ``schema_version`` set
    to 1.
    """
    v1 = copy.deepcopy(_valid_single_claim_snapshot())
    v1["schema_version"] = 1
    v1.pop("hint_evidence_types", None)
    return v1


class TestFromSnapshotV1MigrationRejectsInvalidStatus:
    """§51.4 + v1->v2 migration — a supported v1 snapshot whose claim
    carries an invalid status is still rejected; migration never coerces
    the status, and the input v1 dict is not mutated."""

    @pytest.mark.parametrize(
        ("label", "value", "exc_type"), V1_INVALID_STATUS_CASES,
    )
    def test_v1_invalid_status_rejected(
        self, label: str, value: object, exc_type: type,
    ) -> None:
        v1 = _valid_v1_snapshot()
        v1["claims"][0]["value"]["status"] = value
        before = copy.deepcopy(v1)
        with pytest.raises(exc_type):
            Engine.from_snapshot(v1)
        # Migration did not coerce/rewrite the input; v1 dict unchanged.
        assert v1 == before
