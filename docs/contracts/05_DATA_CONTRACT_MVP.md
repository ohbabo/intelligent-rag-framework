# 05. Data Contract MVP

## 1. 기본 타입

```c
typedef uint32_t EntityId;
typedef uint32_t ObservationId;
typedef uint32_t ClaimId;
typedef uint32_t EvidenceId;
typedef uint32_t RelationId;
typedef uint32_t GapId;
typedef uint32_t ActionId;
typedef uint32_t RawRefId;

typedef uint16_t EntityType;
typedef uint16_t ObservationType;
typedef uint16_t ClaimType;
typedef uint16_t EvidenceType;
typedef uint16_t RelationType;
typedef uint16_t RuleId;
typedef uint16_t ReasonCode;
typedef uint16_t GapType;
typedef uint16_t ActionType;
typedef uint16_t Score;
```

## 2. Entity

```c
typedef struct {
    EntityId id;
    EntityType type;
    uint16_t flags;
} Entity;
```

## 3. Observation

```c
typedef struct {
    ObservationId id;
    EntityId entity_id;
    RawRefId raw_ref_id;
    ObservationType type;
    uint16_t source_type;
} Observation;
```

## 4. Claim

```c
typedef struct {
    ClaimId id;
    EntityId subject_id;
    ClaimType type;
    RuleId created_by_rule;
    ReasonCode reason_code;
    uint16_t flags;
} Claim;
```

## 5. Evidence

```c
typedef struct {
    EvidenceId id;
    ClaimId claim_id;
    RawRefId raw_ref_id;
    EvidenceType type;
    Score strength;
} Evidence;
```

## 6. Relation

```c
typedef struct {
    RelationId id;
    uint32_t from_id;
    uint32_t to_id;
    RelationType type;
    RuleId rule_id;
    ReasonCode reason_code;
} Relation;
```

## 7. Gap

```c
typedef struct {
    GapId id;
    ClaimId claim_id;
    GapType type;
    Score severity;
    RuleId created_by_rule;
} Gap;
```

## 8. Score Vector

```c
typedef struct {
    uint32_t target_id;
    Score confidence;
    Score relevance;
    Score freshness;
    Score evidence_strength;
    Score priority;
    Score memory_value;
} ScoreVector;
```

## 9. MVP Rule 예시

```text
RULE_001_OBSERVATION_TO_CLAIM
- Observation이 들어오면 Claim 후보를 생성한다.

RULE_002_CLAIM_REQUIRES_EVIDENCE
- Claim이 있는데 Evidence가 부족하면 Gap을 생성한다.

RULE_003_EVIDENCE_UPDATES_CONFIDENCE
- Evidence strength가 높으면 Claim confidence를 올린다.

RULE_004_GAP_CREATES_ACTION_CANDIDATE
- Gap이 있으면 해당 Gap을 줄일 Action 후보를 생성한다.

RULE_005_MEMORY_ELIGIBILITY
- priority와 memory_value가 기준 이상이면 Memory Candidate로 표시한다.
```
