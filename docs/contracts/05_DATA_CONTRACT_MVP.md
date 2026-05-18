# 05. Data Contract MVP

이 문서는 **이식 목표 C 계약**을 정의한다. Python Reference Core는 이 구조와 1:1 대응하는 dataclass를 사용한다.

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
typedef uint16_t ClaimStatus;
typedef uint16_t EvidenceType;
typedef uint16_t RelationType;
typedef uint16_t RuleId;
typedef uint16_t RuleVersion;       // monotonic uint16 (1~65535); semver는 metadata only — see §8.3
typedef uint16_t RuleMaturity;      // 0=experimental, 1=stable, 2=deprecated
typedef uint16_t ReasonCode;
typedef uint16_t GapType;
typedef uint16_t ActionType;
typedef uint16_t Score;             // storage form, 0~10000 maps to 0.0~1.0
typedef uint8_t  Kind;              // discriminator for cross-kind references
```

### Kind discriminators

ID는 kind 안에서만 단조 증가한다 — entity:1 과 claim:1 은 서로 다른 객체다. 따라서 두 kind를 가로지르는 참조(Relation 등)는 **반드시 kind와 id를 함께** 전달해야 한다.

```c
#define KIND_ENTITY       1
#define KIND_OBSERVATION  2
#define KIND_CLAIM        3
#define KIND_EVIDENCE     4
#define KIND_RELATION     5
#define KIND_GAP          6
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

Claim은 **확정/후보** 상태를 분리한다. 도메인 룰이 한 번 firing 했다고 곧바로 확정이 아니다. 추가 증거가 채워질 때만 `confirmed`로 승격된다.

Claim은 반드시 자신을 만든 룰 ID와 버전을 보존한다 (`created_by_rule` + `created_by_rule_version`).

Claim은 firing 시점의 **초기 확신도(`base_confidence`)** 를 함께 보존한다. 이 값은 이후 증거나 룰 통계가 채워져도 **변하지 않는다** — Claim은 "이 룰이 이 시점에 이만큼 주장했다"는 스냅샷이다. 현재 종합 확신도는 별도 `compute_effective_confidence(claim_id)` 함수로 계산한다 (다음 단계).

```c
#define CLAIM_STATUS_CANDIDATE  0
#define CLAIM_STATUS_CONFIRMED  1
#define CLAIM_STATUS_REFUTED    2

typedef struct {
    ClaimId id;
    EntityId subject_id;
    ClaimType type;
    ClaimStatus status;
    RuleId created_by_rule;
    RuleVersion created_by_rule_version;
    ReasonCode reason_code;
    Score base_confidence;        // firing 시점 스냅샷, 변하지 않음
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
    Score strength;     // 저장 형태. 의미 계층은 0.0~1.0
} Evidence;
```

## 6. Relation

Relation은 두 객체를 잇는 cross-kind 링크다. ID는 kind 독립이므로 (entity:1 ≠ claim:1), Relation은 **반드시 양쪽 kind를 함께 저장한다**. kind 없이 id만 두면 나중에 "entity → claim 이었는지 claim → evidence 였는지" 구분되지 않는다.

```c
typedef struct {
    RelationId id;
    Kind from_kind;
    uint32_t from_id;
    Kind to_kind;
    uint32_t to_id;
    RelationType type;
    RuleId rule_id;
    ReasonCode reason_code;
} Relation;
```

`add_relation(from_kind, from_id, to_kind, to_id, ...)` 호출 시 Engine은 `(kind, id)` 쌍이 해당 storage에 실제 존재하는지 확인한다 — 잘못된 kind는 `ValueError`, 해당 kind에 id가 없으면 `KeyError`.

## 7. Gap

Gap은 "어떤 종류의 증거가 부족한가"를 명시해야 한다. `required_evidence_type`이 없으면 Gap을 메우는 Action을 선택할 수 없다.

```c
typedef struct {
    GapId id;
    ClaimId claim_id;
    GapType type;
    EvidenceType required_evidence_type;
    Score severity;
    RuleId created_by_rule;
} Gap;
```

## 8. Score Vector

`confidence`(판단 자체에 대한 믿음)와 `evidence_strength`(증거 묶음의 강도)는 분리해 저장한다.

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

---

## 8.1 Score Layer Separation

수치 의미값과 저장값은 분리한다.

```text
의미 계층:  float 0.0 ~ 1.0  (계산, 임계값, 디버깅)
저장 계층:  uint16 0 ~ 10000 (DB, 직렬화, C/Rust hot loop)
```

Python Reference Core는 ScoreValue 래퍼를 사용한다.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ScoreValue:
    value: float

    def __post_init__(self):
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("score must be 0.0 ~ 1.0")

    def to_uint16_scale(self) -> int:
        return round(self.value * 10000)

    @staticmethod
    def from_uint16_scale(raw: int) -> "ScoreValue":
        return ScoreValue(raw / 10000)
```

원칙: **점수의 의미는 float로 검증하고, 점수의 저장은 uint16으로 최적화한다.**

---

## 8.2 Rule Registry — Definition / Stats 분리

모든 Rule은 판단 결과를 생성할 때 `rule_id`와 `rule_version`을 함께 남긴다.

룰의 **정의(definition)** 와 **운영 통계(stats)** 는 같은 구조체에 섞지 않는다. 정의는 룰이 등록될 때 고정되며 시간에 따라 변하지 않고, 통계는 firing이 누적되면서 갱신된다. 두 슬롯을 분리해야 정의 변경(version bump)과 통계 갱신이 충돌하지 않는다.

### RuleDefinition

```c
typedef struct {
    RuleId id;
    RuleVersion version;
    RuleMaturity maturity;      // 0=experimental, 1=stable, 2=deprecated
    Score prior_confidence;     // 룰 자체의 사전 신뢰도 (firing 결과와 별개)
} RuleDefinition;
```

### RuleStats

```c
typedef struct {
    RuleId rule_id;
    RuleVersion rule_version;
    uint32_t firing_count;
    uint32_t confirmed_true_count;
    uint32_t confirmed_false_count;
    Score observed_precision;        // null=Score=0 + flag bit
    Score false_positive_rate;       // null=Score=0 + flag bit
    uint16_t reliability_flags;      // bit0=precision_present, bit1=fpr_present
} RuleStats;
```

운영 데이터가 쌓이기 전까지 `observed_precision` / `false_positive_rate`는 null 가능 (flag bit로 표시).

### Naming triangle — 세 슬롯을 절대 섞지 말 것

```text
RuleDefinition.prior_confidence
  = 이 룰 자체를 처음부터 얼마나 믿을지에 대한 사전 신뢰도
  = 룰 등록 시점에 고정, 운영 통계와 무관

Claim.base_confidence
  = 이 룰이 특정 입력을 보고 Claim을 만들었을 때의 초기 확신도
  = Claim 생성 시점에 박힘, 이후 evidence가 와도 변하지 않음

compute_effective_confidence(claim_id)  (다음 단계)
  = base_confidence + evidence_strength + RuleStats 를 조합한 현재 종합 확신도
  = 함수로만 노출, 저장 슬롯 없음
```

예시:

```text
RuleDefinition.prior_confidence = 0.50   (룰 experimental, 룰 자체 신뢰도 보통)
Claim.base_confidence           = 0.55   (이번 입력에서 OpenSSH_7.x 잡혔으니 +)
RuleStats.observed_precision    = 0.80   (운영 결과 실제 적중률)
→ effective_confidence는 이 셋을 조합해 계산
```

세 값은 서로 다른 계층이며 같은 슬롯에 섞으면 안 된다.

```text
prior_confidence = 0.90, base_confidence = 0.40
→ 룰은 검증됐지만 이번 케이스의 증거가 부족하다.

prior_confidence = 0.50, base_confidence = 0.80
→ 증거만 보면 그럴듯한데, 룰 자체는 아직 검증이 부족하다.
```

### Rule registry (MVP advisory)

Phase 1 Engine은 등록되지 않은 `(rule_id, rule_version)`을 `add_claim`에서 허용한다 (advisory). 테스트와 초기 실험 부담을 줄이기 위함이다. Rule Engine 단계에서 strict mode가 옵션으로 들어간다.

## 8.3 RuleVersion convention

`RuleVersion` is a monotonic `uint16` integer used by the engine to distinguish rule behavior versions.

- Valid range: `1..65535`
- `0` is reserved for invalid/unset state.
- The engine treats `(rule_id, rule_version)` as the stable rule identity.
- RuleVersion is not a semantic version.
- Semver-like labels such as `0.1.0` may be kept only as human-readable metadata or comments.
- YAML rule definitions MUST use integer `version`.

A rule version MUST be bumped when the rule's firing behavior changes, including condition logic, claim generation, scoring/confidence behavior, or output semantics.

A rule version SHOULD NOT be bumped for comment-only, description-only, or documentation-only changes.

### YAML example

```yaml
rule_id: RULE_DOMAIN_SSH_001
version: 1
# human_label: 0.1.0
```

핵심 문장: **RuleVersion은 문서 릴리즈 버전이 아니라, rule firing behavior의 버전이다.**

---

## 9. MVP Rules

룰은 두 종류로 분리한다. **생명주기 룰과 판단 룰이 섞이면 프레임워크는 움직이지만 판단은 하지 않는다.**

### Lifecycle Rules — 엔진 운영 규칙

데이터 흐름을 관리한다. 판단이 아니다.

```text
RULE_LIFE_001 Observation Registration
    새 Observation을 source / timestamp / raw_ref를 가진 Evidence 후보로 등록

RULE_LIFE_002 Evidence Normalization
    원본 필드를 Core 타입으로 정규화

RULE_LIFE_003 Claim-Gap Lifecycle
    Claim 생성 / 부족 증거 → Gap 생성 / 증거 보강 시 Claim 갱신
```

### Judgment Rules — 도메인 판단 규칙

의미 있는 결론을 만든다. MVP에는 도메인 룰 **최소 1개**를 반드시 포함한다.

```text
RULE_DOMAIN_SSH_001 SSH Outdated Version Candidate
RULE_GAP_001 Required Evidence Gap Detection
RULE_ACTION_001 Gap-to-Check Action Selection
```

도메인 룰은 **코드가 아니라 데이터**다. Core는 condition 평가 엔진만 제공하고, 룰 정의는 외부 yaml/json에서 로드한다.

---

### RULE_DOMAIN_SSH_001 상세 (예시)

```yaml
id: RULE_DOMAIN_SSH_001
version: 1
# human_label: 0.1.0
domain: security.ssh
maturity: experimental
author: core
created_at: 2026-05-17

reliability:
  prior_confidence: 0.50
  firing_count: 0
  confirmed_true_count: 0
  confirmed_false_count: 0
  observed_precision: null
  false_positive_rate: null

input:
  - evidence.port_open
  - evidence.service_banner

condition:
  all:
    - port == 22
    - protocol == tcp
    - service == ssh
    - banner contains "OpenSSH_7."

output:
  claim:
    type: outdated_ssh_candidate
    subject: service:ssh
    status: candidate            # 확정 아님
    base_confidence: 0.55        # 의미 계층, 저장 시 5500으로 패킹
    evidence_strength: 0.40
    required_evidence:
      - exact_openssh_version
      - os_family
      - package_backport_status

reason_code:
  - SSH_PORT_OPEN
  - OPENSSH_7_SERIES_BANNER
```

핵심: 이 룰은 `OpenSSH_7.x = 취약`이라고 단정하지 **않는다**. 리눅스 배포판이 보안 패치를 백포트했을 수 있기 때문이다. Claim의 status는 `candidate`로 두고, `required_evidence`가 채워질 때만 `confirmed`로 승격된다.

이 룰이 만든 Claim은 항상 자기 출처를 보존한다.

```yaml
claim:
  id: CLAIM_001
  type: outdated_ssh_candidate
  status: candidate
  base_confidence: 0.55
  generated_by:
    rule_id: RULE_DOMAIN_SSH_001
    rule_version: 1
    rule_maturity: experimental
```

이 룰 하나만 끝까지 끌어봐도 다음 빈틈이 즉시 드러난다.

```text
Evidence에 raw_banner가 있어야 함
Claim에 subject가 있어야 함
Claim에 status (확정 / 후보 / 반증) 가 있어야 함
Claim에 generated_by.rule_id + rule_version 이 있어야 함
Gap에 required_evidence_type 이 있어야 함
Action에 어떤 Gap을 메우는지 표시되어야 함
Score에 confidence와 evidence_strength가 분리되어야 함
Rule에 reliability hook 자리가 예약되어 있어야 함
```

추상 룰만으로는 보이지 않던 구조적 빈틈이, 도메인 룰 하나에서 바로 노출된다.
