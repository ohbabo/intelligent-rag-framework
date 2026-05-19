"""Core data types — frozen dataclasses with explicit fields.

Mirrors the contract in docs/contracts/05_DATA_CONTRACT_MVP.md.
ID-based linking, no nested objects.

Naming triangle (절대 한 슬롯에 섞지 말 것):
- RuleDefinition.prior_confidence  = 룰 자체의 사전 신뢰도
- Claim.base_confidence            = 이 Claim 생성 시점의 초기 확신도
- effective_confidence             = base + evidence + rule_stats 조합 (다음 PR의 함수)
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Kind discriminators for cross-kind references.
KIND_ENTITY = 1
KIND_OBSERVATION = 2
KIND_CLAIM = 3
KIND_EVIDENCE = 4
KIND_RELATION = 5
KIND_GAP = 6

CLAIM_STATUS_CANDIDATE = 0
CLAIM_STATUS_CONFIRMED = 1
CLAIM_STATUS_REFUTED = 2
CLAIM_STATUS_DISPUTED = 3  # PR8 §20: confirmed → disputed lifecycle quarantine

RULE_MATURITY_EXPERIMENTAL = 0
RULE_MATURITY_STABLE = 1
RULE_MATURITY_DEPRECATED = 2


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
    """A judgment a rule asserted about a subject at firing time.

    `base_confidence`는 룰이 firing 한 순간의 초기 확신도다. Evidence나
    RuleStats가 채워져도 이 값은 **변하지 않는다**. 현재 종합 확신도가
    필요하면 별도 `compute_effective_confidence(claim_id)` 함수를 쓴다.
    """

    id: int
    subject_id: int
    type: int
    status: int
    created_by_rule: int
    created_by_rule_version: int
    reason_code: int
    base_confidence: ScoreValue
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
    """Cross-kind link.

    IDs in this framework are kind-independent (entity:1 and claim:1 are
    distinct), so a Relation must carry both kind discriminators to be
    unambiguous about what it connects.
    """

    id: int
    from_kind: int
    from_id: int
    to_kind: int
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


@dataclass(frozen=True)
class RuleDefinition:
    """룰의 고정 정의. 운영 통계와 분리.

    `prior_confidence`는 이 룰 자체를 처음부터 얼마나 믿을지에 대한 사전
    신뢰도. 특정 Claim의 확신도와 다르다 — Claim.base_confidence와 절대
    혼동하지 말 것.
    """

    id: int
    version: int
    maturity: int
    prior_confidence: ScoreValue


@dataclass(frozen=True)
class RuleStats:
    """룰의 운영 통계. 정의와 분리해 시간에 따라 누적.

    Frozen이지만 누적은 새 인스턴스로 교체 (Engine.update_rule_stats가 담당).
    """

    rule_id: int
    rule_version: int
    firing_count: int = 0
    confirmed_true_count: int = 0
    confirmed_false_count: int = 0
    observed_precision: ScoreValue | None = None
    false_positive_rate: ScoreValue | None = None
