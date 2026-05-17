"""Core data types — frozen dataclasses with explicit fields.

Mirrors the contract in docs/contracts/05_DATA_CONTRACT_MVP.md.
ID-based linking, no nested objects.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreValue:
    """Semantic-layer score.

    의미 계층은 0.0 ~ 1.0. 저장 / hot loop 단계에서만 uint16 0~10000으로 패킹.
    """

    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"score must be in [0.0, 1.0], got {self.value}")

    def to_uint16_scale(self) -> int:
        return round(self.value * 10000)

    @staticmethod
    def from_uint16_scale(raw: int) -> ScoreValue:
        if not 0 <= raw <= 10000:
            raise ValueError(f"packed score must be in [0, 10000], got {raw}")
        return ScoreValue(raw / 10000)


@dataclass(frozen=True)
class Entity:
    id: int
    type: int
    flags: int = 0
