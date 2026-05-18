"""Smoke tests for the Python Reference Core skeleton."""

from __future__ import annotations

import pytest

from ragcore import Engine, ScoreValue


class TestEngineEntity:
    def test_allocates_distinct_ids(self) -> None:
        engine = Engine()
        first = engine.add_entity(entity_type=1)
        second = engine.add_entity(entity_type=1)
        assert first != second

    def test_ids_are_monotonic_starting_at_one(self) -> None:
        engine = Engine()
        ids = [engine.add_entity(entity_type=7) for _ in range(3)]
        assert ids == [1, 2, 3]

    def test_preserves_entity_type_and_flags(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=42, flags=3)
        entity = engine.get_entity(entity_id)
        assert entity.id == entity_id
        assert entity.type == 42
        assert entity.flags == 3

    def test_default_flags_is_zero(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        assert engine.get_entity(entity_id).flags == 0

    def test_entity_is_immutable(self) -> None:
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        entity = engine.get_entity(entity_id)
        with pytest.raises(AttributeError):
            entity.type = 99  # type: ignore[misc]

    def test_two_engines_share_no_state(self) -> None:
        first_engine = Engine()
        second_engine = Engine()
        first_engine.add_entity(entity_type=1)
        first_engine.add_entity(entity_type=1)
        new_id = second_engine.add_entity(entity_type=1)
        assert new_id == 1


class TestScoreValueBounds:
    def test_accepts_lower_bound(self) -> None:
        assert ScoreValue(0.0).value == 0.0

    def test_accepts_upper_bound(self) -> None:
        assert ScoreValue(1.0).value == 1.0

    def test_accepts_midpoint(self) -> None:
        assert ScoreValue(0.5).value == 0.5

    def test_rejects_negative(self) -> None:
        with pytest.raises(ValueError):
            ScoreValue(-0.0001)

    def test_rejects_above_one(self) -> None:
        with pytest.raises(ValueError):
            ScoreValue(1.0001)


class TestScoreValuePacking:
    def test_pack_zero_maps_to_zero(self) -> None:
        assert ScoreValue(0.0).to_uint16_scale() == 0

    def test_pack_one_maps_to_ten_thousand(self) -> None:
        assert ScoreValue(1.0).to_uint16_scale() == 10000

    def test_pack_half_maps_to_five_thousand(self) -> None:
        assert ScoreValue(0.5).to_uint16_scale() == 5000

    def test_pack_unpack_roundtrip(self) -> None:
        original = ScoreValue(0.7234)
        packed = original.to_uint16_scale()
        assert packed == 7234
        unpacked = ScoreValue.from_uint16_scale(packed)
        assert unpacked.value == pytest.approx(0.7234)

    def test_unpack_rejects_above_max(self) -> None:
        with pytest.raises(ValueError):
            ScoreValue.from_uint16_scale(10001)

    def test_unpack_rejects_negative(self) -> None:
        with pytest.raises(ValueError):
            ScoreValue.from_uint16_scale(-1)


class TestScoreValueImmutability:
    def test_is_frozen(self) -> None:
        score = ScoreValue(0.5)
        with pytest.raises(AttributeError):
            score.value = 0.7  # type: ignore[misc]
