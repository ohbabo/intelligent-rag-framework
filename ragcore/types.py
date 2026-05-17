"""Core data types — frozen dataclasses with explicit fields.

Mirrors the contract in docs/contracts/05_DATA_CONTRACT_MVP.md.
ID-based linking, no nested objects.
"""

from __future__ import annotations

from dataclasses import dataclass

CLAIM_STATUS_CANDIDATE = 0
CLAIM_STATUS_CONFIRMED = 1
CLAIM_STATUS_REFUTED = 2


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


@dataclass(frozen=True)
class Observation:
    id: int
    entity_id: int
    raw_ref_id: int
    type: int
    source_type: int = 0


@dataclass(frozen=True)
class Claim:
    id: int
    subject_id: int
    type: int
    status: int
    created_by_rule: int
    created_by_rule_version: int
    reason_code: int
    flags: int = 0


@dataclass(frozen=True)
class Evidence:
    id: int
    claim_id: int
    raw_ref_id: int
    type: int
    strength: ScoreValue


@dataclass(frozen=True)
class Relation:
    id: int
    from_id: int
    to_id: int
    type: int
    rule_id: int
    reason_code: int


@dataclass(frozen=True)
class Gap:
    id: int
    claim_id: int
    type: int
    required_evidence_type: int
    severity: ScoreValue
    created_by_rule: int
