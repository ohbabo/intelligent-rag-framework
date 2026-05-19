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
id: RULE_DOMAIN_SSH_001
version: 1
# human_label: 0.1.0
```

YAML 필드명 컨벤션 (yaml loader 구현 전 고정):

```text
룰 정의 파일:        id           (RuleDefinition.id 와 1:1)
claim generated_by:  rule_id      (Claim의 출처 표기)
엔진 내부 키:        (id, version) 튜플
```

같은 식별자라도 컨텍스트에 따라 필드명이 다르다. 룰 자체를 정의하는 위치에서는 `id`, 다른 객체가 그 룰을 가리키는 위치에서는 `rule_id`.

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
    - field: port
      op: eq
      value: 22
    - field: protocol
      op: eq
      value: tcp
    - field: service
      op: eq
      value: ssh
    - field: banner
      op: contains
      value: "OpenSSH_7."

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

---

## 10. Condition syntax (MVP)

룰의 `condition` 블록은 **structured form** 으로 표현한다. 문자열 DSL (`- port == 22`) 은 MVP 미지원 — 별도 파서가 필요해 condition evaluator 시작 전 의사결정이 늘어난다.

### Structure

```yaml
condition:
  all:
    - field: <name>
      op: <operator>
      value: <literal>
    - any:
        - field: <name>
          op: <operator>
          value: <literal>
        - ...
```

- 노드는 **정확히** predicate 또는 combinator 중 하나의 모양
- 최상위는 predicate 또는 combinator 둘 다 가능 (단일 조건 룰을 위해 top-level predicate 허용)
- 자식은 predicate 또는 nested combinator
- predicate 노드의 키는 정확히 `{field, op, value}` — 추가 키 거부
- combinator 노드의 키는 정확히 `{all}` 또는 `{any}` — 추가 키 거부 (오타로 인한 silent ignore 차단)
- 중첩 가능 (`all` 안에 `any` 등)

### Supported combinators

| Combinator | 의미 | MVP |
|---|---|---|
| `all` | 모든 자식이 true | ✅ |
| `any` | 자식 중 하나라도 true | ✅ |
| `not` | 부정 | ❌ 다음 단계 |

`not` 을 미루는 이유: 표현력은 늘지만 evaluator 복잡도 증가. 많은 경우 룰 재설계로 우회 가능. 구체적 필요가 보일 때 별도 결정점으로 도입.

### Supported operators

| op | 의미 | 적용 타입 |
|---|---|---|
| `eq` | 같음 | 모든 타입 |
| `ne` | 다름 | 모든 타입 |
| `lt` | `<` | int, float |
| `le` | `<=` | int, float |
| `gt` | `>` | int, float |
| `ge` | `>=` | int, float |
| `contains` | 부분 포함 | str (substring), list/tuple (membership) |

### Input context

evaluator 는 평가 대상을 **flat dict** 으로 받는다.

```python
context: Mapping[str, Any]
# 예: {"port": 22, "protocol": "tcp", "banner": "OpenSSH_7.4"}
```

`field` 값은 context 의 top-level key 만 가리킨다. nested field (`evidence.banner` 같은 dot notation) 는 MVP 미지원.

### Semantics

| 상황 | MVP 결과 |
|---|---|
| field 가 context 에 없음 | 해당 predicate → `false` (전체 절이 아니라 그 predicate 만) |
| context value 타입이 op 와 안 맞음 (예: `lt` 인데 string) | 해당 predicate → `false` |
| `all` 의 자식이 비어있음 | `true` (vacuous truth) |
| `any` 의 자식이 비어있음 | `false` |

**원칙**: condition evaluator 는 입력 데이터 누락/이상에 **관대 (lenient)** 하다. 룰이 firing 못 했을 때 `claim 없음` 으로 표현되고, "왜 안 됐는지" 는 evaluator trace (별도 결정점) 가 책임진다.

### Out of scope (MVP)

- 문자열 DSL (`- port == 22`) — 별도 파서 필요, priority/precedence 결정점 늘어남
- `not` combinator — 표현력은 늘지만 evaluator 복잡도 증가
- Nested field access (`evidence.banner`) — context shape 결정 필요
- Regex match (`re_match`)
- 산술식 (`port * 2`)
- Custom functions (`is_open_port(port)`)
- 변수 binding / 패턴 매칭
- Cross-evidence join

MVP 가 안정화된 뒤 단계적으로 도입.

### Loader 동작 (현재 단계)

`load_rule_spec` 은 현재 condition 블록을 **검증하지 않고** `raw["condition"]` 에 그대로 보존한다. 별도 `load_condition_tree(raw["condition"]) → ConditionTree` 함수가 다음 단계에서 들어온다. 그 시점에 condition 의 구조 검증과 operator allowlist 확인이 발생한다.

---

## 11. Condition trace (MVP)

`evaluate_condition` 은 lenient — missing field / type mismatch / value mismatch 가 전부 `false` 로 흘러간다. 그래서 룰이 firing 못 했을 때 **"왜"** 가 사라진다.

```text
banner 가 없어서 false?
banner 값이 달라서 false?
port 가 다른 타입이라 false?
```

이를 구별하기 위해 evaluation 의 **debug / explain layer** 로 trace 를 둔다. trace 는 judgment 가 아니다 — RuleStats / Claim.base_confidence / scoring 같은 판단 슬롯에 들어가지 않는다.

### Function 비대칭

| | `evaluate_condition` | `evaluate_condition_with_trace` |
|---|---|---|
| 반환값 | `bool` | `Trace` (tree) |
| Short-circuit | yes (`all` 첫 false, `any` 첫 true 에서 멈춤) | **no** — 모든 child 평가 |
| 사용 위치 | 룰 firing 판정 (fast path) | 디버깅 / "왜 안 됐어" 설명 |

이 비대칭은 의도적이다.
- 룰 firing 판정은 빨라야 함 → short-circuit 유지
- "왜 false 인지" 알려면 모든 자식 결과가 필요 → full evaluation

### Types

```python
@dataclass(frozen=True)
class PredicateTrace:
    field: str
    op: str
    expected: Any
    actual: Any | None         # field 가 없으면 None (의미: 표시용 placeholder)
    actual_present: bool       # context 에 field 가 있었는지 (None 값과 구분)
    result: bool
    reason: str                # TRACE_REASON_* 중 하나


@dataclass(frozen=True)
class CombinatorTrace:
    kind: str                  # "all" | "any"
    children: tuple[Trace, ...]
    result: bool


Trace = PredicateTrace | CombinatorTrace
```

`actual` 과 `actual_present` 가 분리되어 있는 이유: context 에 `{"x": None}` 같은 명시적 `None` 값이 들어왔을 때 "field 없음" 과 구별 가능해야 함.

### Reason discriminator

| 상수 | 의미 | 발생 조건 |
|---|---|---|
| `TRACE_REASON_MATCH` | predicate true | 정상 매칭 |
| `TRACE_REASON_MISMATCH` | predicate false (값 다름) | eq/ne/numeric/contains 모두 |
| `TRACE_REASON_MISSING_FIELD` | field 가 context 에 없음 | `pred.field not in context` |
| `TRACE_REASON_TYPE_MISMATCH` | 타입 불일치로 false | numeric op 가 non-number, contains 가 부적절 타입 |

Combinator 노드에는 `reason` 이 없다 — 자식들의 reason 집합이 곧 설명이다.

### Example

```python
from ragcore import (
    evaluate_condition_with_trace,
    load_condition_tree,
    TRACE_REASON_MATCH,
    TRACE_REASON_MISMATCH,
)

tree = load_condition_tree({
    "all": [
        {"field": "port", "op": "eq", "value": 22},
        {"field": "banner", "op": "contains", "value": "OpenSSH_7."},
    ]
})

trace = evaluate_condition_with_trace(
    tree,
    {"port": 22, "banner": "OpenSSH_9.0"},
)

assert trace.result is False
assert trace.kind == "all"
assert trace.children[0].result is True
assert trace.children[0].reason == TRACE_REASON_MATCH
assert trace.children[1].result is False
assert trace.children[1].reason == TRACE_REASON_MISMATCH
```

### Out of scope (MVP)

- Trace 직렬화 (JSON/YAML 등) — debug 단계는 repr 로 충분
- Trace 시간 측정 (latency profile)
- 여러 룰 firing 의 trace aggregation
- RuleStats 갱신과 trace 자동 연동
- Diff/comparison between traces
- Trace pretty-printer

### Loader 동작 변경 없음

`load_condition_tree` 는 동일하게 동작한다. trace 는 evaluator 단계의 새 함수일 뿐, ConditionTree 구조나 loader 책임에는 영향이 없다.

---

## 12. RuleId mapping (MVP)

`RuleSpec.id` 는 문자열이다 (예: `"RULE_DOMAIN_SSH_001"`). `RuleDefinition.id` 는 `uint16` 이다. 두 표현 사이의 매핑 규칙을 여기서 고정한다.

`RuleSpec.maturity` 도 같은 문제 — 문자열 (`"experimental"`) ↔ 정수 (`RULE_MATURITY_*`).

### 결정사항

1. **Static mapping table** — 코드 안에 dict 로 둔다 (외부 파일 / hash / 동적 등록 미사용 MVP)
2. **Compile 시점 1회 lookup** — `compile_rule_definition(spec)` 이 매핑 적용
3. **Unknown id → `ValueError`** — 매핑에 없는 문자열은 거부 (strict)
4. **Unknown maturity → `ValueError`** — 알려진 3개 값 외 거부
5. **0 reserved / 1..65535 range** — `RULE_ID_MAP` 의 값 범위 (RuleVersion 과 동일 규칙)
6. **모듈 로딩 시 정적 검증** — id 값 범위 위반 / 중복은 import 시점에 거부

### 매핑 구조

```python
# 위치 추천: ragcore/rule_loader.py (혹은 ragcore/rule_compile.py)

from collections.abc import Mapping
from ragcore.types import (
    RULE_MATURITY_DEPRECATED,
    RULE_MATURITY_EXPERIMENTAL,
    RULE_MATURITY_STABLE,
)

RULE_ID_MAP: Mapping[str, int] = {
    "RULE_DOMAIN_SSH_001": 1,
    # 새 룰은 여기에 한 줄 추가, PR review 에서 충돌 검토
}

RULE_MATURITY_MAP: Mapping[str, int] = {
    "experimental": RULE_MATURITY_EXPERIMENTAL,  # 0
    "stable":       RULE_MATURITY_STABLE,        # 1
    "deprecated":   RULE_MATURITY_DEPRECATED,    # 2
}
```

### Compile 흐름

```python
def compile_rule_definition(spec: RuleSpec) -> RuleDefinition: ...
```

동작:

```text
spec.id (str)                      → RULE_ID_MAP lookup → uint16 RuleId
spec.version (int)                 → 그대로 (이미 1..65535 검증됨)
spec.maturity (str)                → RULE_MATURITY_MAP lookup → uint8 RuleMaturity
spec.prior_confidence (ScoreValue) → 그대로
```

### Error 분기

| 상황 | 결과 |
|---|---|
| `spec.id` 가 `RULE_ID_MAP` 에 없음 | `ValueError("unknown rule id: {id}")` |
| `spec.maturity` 가 `RULE_MATURITY_MAP` 에 없음 | `ValueError("unknown maturity: {maturity}")` |
| `RULE_ID_MAP` 값이 `<1` 또는 `>65535` | 모듈 로딩 시 assertion 실패 |
| `RULE_ID_MAP` 값에 중복 (다른 키가 같은 int) | 모듈 로딩 시 assertion 실패 |

### 새 룰 추가 절차

1. yaml 룰 정의에 `id: NEW_RULE_NAME` 사용
2. `RULE_ID_MAP` 에 한 줄 추가: `"NEW_RULE_NAME": <next_unused_int>`
3. PR review 에서 id 값 충돌 / 의미 검토 (사람이 검토하는 게 핵심)
4. `compile_rule_definition` 호출 시 자동으로 새 매핑 적용

### Why static map (MVP)

| 후보 | 트레이드오프 |
|---|---|
| **Static map (선택)** | 단순. 코드에서 grep 가능. PR review 로 충돌 검토. 부담 최소. |
| 외부 YAML registry | 룰 추가 시 두 파일 동기화. 로딩 복잡도 ↑. MVP 부담. |
| Hash 기반 자동 매핑 | id 안정성 X (룰 이름 바뀌면 키 충돌 가능). 추적 어려움. |
| 동적 등록 (`Engine.register_rule_id`) | strict mode 결정 필요. Engine 책임 비대. 다음 결정점. |

### Out of scope (MVP)

- 동적 룰 등록 / hot reload
- 외부 매핑 파일 로딩 (yaml/json registry)
- Hash / UUID 기반 자동 id 생성
- 룰 이름 변경 시 alias 처리
- Multi-tenant 룰 namespace
- `Engine.register_rule` 자동 호출 (12차 compile 만 함, Engine 연동은 별도 결정점)

### Compile 모듈 위치 (선택지)

12차 구현 시점에 둘 중 선택:

- **옵션 L** — `ragcore/rule_loader.py` 에 `compile_rule_definition` + 매핑 테이블 추가. 단순.
- **옵션 C** — `ragcore/rule_compile.py` 신규 파일로 분리. loader (header validation) 와 compile (string → int 매핑) 책임 명시적 분리.

추천은 **옵션 C** (책임 분리). 12차 구현 직전 다시 확인.

### Loader 동작 변경 없음

`load_rule_spec` / `load_rule_spec_from_yaml` / `compile_rule_condition` 모두 동작 변경 없음. 이 결정은 다음 단계 (12차 `compile_rule_definition` 구현) 의 전제만 고정.

---

## 13. Rule output claim (MVP)

룰이 firing 됐을 때 어떤 `Claim` 을 만들지 YAML 에서 표현한다. 이 섹션은 **15차 parser/compile 구현의 전제** — 어떤 필드를 받고, 어떤 매핑을 적용하고, 무엇은 호출자 책임인지 고정한다.

### MVP shape

```yaml
output:
  claim:
    type: outdated_ssh_candidate          # str → ClaimType uint16 (CLAIM_TYPE_MAP)
    status: candidate                     # str → ClaimStatus uint16 (CLAIM_STATUS_MAP)
    base_confidence: 0.55                 # float 0.0~1.0
    reason_code: OPENSSH_7_SERIES_BANNER  # str → ReasonCode uint16 (REASON_CODE_MAP)
```

### 핵심 결정: `subject_id` 는 YAML 이 해석하지 않는다

룰 output 은 "어떤 종류의 claim 을 어떤 상태로 만들지" 만 기술한다. **누구에 대한 claim 인가** (subject_id) 는 `fire_rule` 호출자가 외부에서 제공한다.

```python
fire_rule(engine, compiled_rule, subject_id, context)
```

이유: YAML 에 `subject: service:ssh` 같은 표기를 넣는 순간 entity resolver 가 열린다. resolver 는 자체 결정점 (어떤 entity 가 무엇인지, namespace, lookup 정책 등) — MVP 부담 vs 가치 비례 안 맞음.

§9 SSH_001 yaml 예시의 `subject:` 줄은 **broader intent** 의 표기일 뿐, MVP parser 가 해석하지 않음.

### 매핑 (static, §12 RULE_ID_MAP 와 동일 패턴)

```python
# 위치 추천: ragcore/rule_output.py (15차에서 신규 생성)

CLAIM_TYPE_MAP: Mapping[str, int] = {
    "outdated_ssh_candidate": 1,
    # 새 claim type 추가는 PR review 로 충돌 검토
}

CLAIM_STATUS_MAP: Mapping[str, int] = {
    "candidate": CLAIM_STATUS_CANDIDATE,    # 0
    "confirmed": CLAIM_STATUS_CONFIRMED,    # 1
    "refuted":   CLAIM_STATUS_REFUTED,      # 2
}

REASON_CODE_MAP: Mapping[str, int] = {
    "OPENSSH_7_SERIES_BANNER": 1,
    "SSH_PORT_OPEN":           2,
    # 새 reason code 도 PR review 로 충돌 검토
}
```

각 매핑의 무결성 (범위 1..65535 / 중복 / 빈 키 / bool 차단) 은 §12 RULE_ID_MAP 과 동일하게 모듈 로딩 시 정적 검증한다.

### Compile 흐름 (15차)

```python
@dataclass(frozen=True)
class RuleOutputTemplate:
    claim_type: int               # CLAIM_TYPE_MAP lookup
    status: int                   # CLAIM_STATUS_MAP lookup
    base_confidence: ScoreValue
    reason_code: int              # REASON_CODE_MAP lookup


def compile_rule_output(spec: RuleSpec) -> RuleOutputTemplate: ...
```

동작:
- `spec.raw["output"]["claim"]` 에서 4개 필드 꺼냄
- 각 문자열을 매핑으로 변환
- `base_confidence` 는 `ScoreValue` 로 wrap (range 검증)
- frozen 으로 반환

호출자가 firing 시점에 (16차 fire_rule):

```python
template = compile_rule_output(spec)
engine.add_claim(
    subject_id=external_subject_id,           # 외부 제공
    claim_type=template.claim_type,
    rule_id=compiled_rule_def.id,
    rule_version=compiled_rule_def.version,
    reason_code=template.reason_code,
    base_confidence=template.base_confidence.value,
    status=template.status,
)
```

### Error 분기

| 상황 | 결과 |
|---|---|
| `output` 또는 `output.claim` 누락 | `ValueError("missing required field: ...")` |
| `type` 누락 또는 unknown | `ValueError("unknown claim type: ...")` |
| `status` 누락 또는 unknown | `ValueError("unknown claim status: ...")` |
| `reason_code` 누락 또는 unknown | `ValueError("unknown reason code: ...")` |
| `base_confidence` 범위 위반 | `ValueError` (ScoreValue 가 던짐) |
| `base_confidence` 누락 / 비-숫자 | `ValueError` / `TypeError` |
| 매핑 정합성 위반 (값 범위 / 중복) | 모듈 로딩 시 `AssertionError` (§12 패턴) |

### Out of scope (MVP)

- **`subject` 필드** — YAML 에서 entity resolver 안 함, fire_rule 호출자 책임
- **`required_evidence`** — 별도 결정점 (17차, Gap 생성과 연동)
- **`evidence_strength`** — Claim 자체에 evidence_strength 필드 없음. 증거 강도는 별도 evidence 흐름에서 다룸
- **여러 claim 동시 생성** — MVP 는 룰 하나 firing → claim 하나
- **`reason_code` list** — MVP 는 단일 reason_code. 다중 이유는 별도 결정점
- **출력 dynamic interpolation** (`{{ banner }}` 같은 placeholder) — scope 밖
- **claim 의 `flags` 필드 표현** — 표현 안 함, 기본값 0

### YAML loader 동작 변경 없음

`load_rule_spec` / `load_rule_spec_from_yaml` 는 변경 없음. `output` 블록은 여전히 `spec.raw["output"]` 에 보존만 됨. 15차에서 `compile_rule_output(spec)` 이 들어올 때 처음 검증된다.

### Position in flow

```text
YAML
  ↓ load_rule_spec_from_yaml                                            (3차)
RuleSpec
  ↓ compile_rule_definition   id/maturity str → int                     (12차 ✅)
RuleDefinition
  ↓ engine.register_rule (via register_rule_spec)                       (13차 ✅)
Engine (rule registered, stats initialized)

별도 경로:
RuleSpec
  ↓ compile_rule_condition    raw["condition"] → ConditionTree          (8차 ✅)
ConditionTree
  ↓ evaluate_condition / _with_trace                                    (6, 10차 ✅)
bool / Trace

신규 (15차):
RuleSpec
  ↓ compile_rule_output       raw["output"] → RuleOutputTemplate        (15차 신규)
RuleOutputTemplate

16차 (fire_rule) 에서 위 세 가지 결과를 묶는다:
- ConditionTree 평가 (evaluate_condition)
- true 면 RuleOutputTemplate + caller 제공 subject_id 로 engine.add_claim
- RuleStats firing_count 증분
```

---

## 14. Required evidence → Gap (MVP)

룰이 firing 됐을 때 (`condition` true), `output.claim.required_evidence` 에 명시된 evidence type 들을 각각 `Gap` 으로 생성한다. 이 섹션은 17~19차 작업의 전제.

§13 의 `compile_rule_output` 은 4개 핵심 필드만 보고 `required_evidence` 는 무시한다. 이번 결정은 `required_evidence` 를 **별도 compile 함수** (`compile_required_evidence`) 로 처리하는 흐름을 고정한다 — output template 의 책임이 비대해지지 않도록.

### MVP shape

```yaml
output:
  claim:
    type: outdated_ssh_candidate
    status: candidate
    base_confidence: 0.55
    reason_code: OPENSSH_7_SERIES_BANNER
    required_evidence:           # ← 14차 scope
      - exact_openssh_version
      - os_family
      - package_backport_status
```

- 리스트의 각 원소는 **EvidenceType 매핑 가능한 문자열**
- 빈 리스트 또는 누락 = required_evidence 없음 → Gap 0개

### 결정사항

1. **각 string → 별개 Gap** — list 원소 N개면 Gap N개 생성
2. **Gap.claim_id = 방금 생성된 Claim 의 id** — 명시적 link (Gap struct 의 기존 claim_id 슬롯 사용)
3. **Gap.type = `GAP_TYPE_MISSING_EVIDENCE`** (단일 상수, MVP 는 한 종류)
4. **Gap.required_evidence_type = `REQUIRED_EVIDENCE_MAP` lookup**
5. **Gap.severity = `ScoreValue(0.5)`** (MVP 고정 default — 차별화는 별도 결정점)
6. **Gap.created_by_rule = rule_id** (해당 룰 ID)
7. **condition false 시 Gap 생성 0** — Claim 도 없으니 Gap 도 없음
8. **중복 방지 안 함** — 같은 룰이 여러 번 fire 되면 Gap 도 여러 번 생성됨 (dedup 은 별도 결정점)
9. **fire_rule 반환값 unchanged** — `claim_id | None`. Gap ID 들은 `engine.gaps_for_claim(claim_id)` 로 조회

### 매핑 (static, §12 / §13 패턴)

```python
# 위치 추천: ragcore/rule_gap.py (18차 신규)

REQUIRED_EVIDENCE_MAP: Mapping[str, int] = {
    "exact_openssh_version":   1,
    "os_family":               2,
    "package_backport_status": 3,
    # 새 evidence type: PR review 로 충돌 검토 후 한 줄 추가
}

GAP_TYPE_MISSING_EVIDENCE = 1
DEFAULT_GAP_SEVERITY = 0.5
```

각 매핑의 무결성 (값 범위 1..65535 / 중복 / 빈 키 / bool 차단) 은 §12 RULE_ID_MAP 패턴 그대로 모듈 로딩 시 정적 검증.

`GAP_TYPE_MISSING_EVIDENCE` 는 MVP 단일 상수 — 다른 GapType 은 별도 결정점.

### Compile (18차)

```python
# ragcore/rule_gap.py

@dataclass(frozen=True)
class RequiredEvidenceTemplate:
    evidence_types: tuple[int, ...]   # REQUIRED_EVIDENCE_MAP lookup 결과들


def compile_required_evidence(spec: RuleSpec) -> RequiredEvidenceTemplate: ...
```

동작:
- `spec.raw["output"]["claim"]["required_evidence"]` 가 없거나 빈 리스트 → `evidence_types = ()`
- 각 원소 string → `REQUIRED_EVIDENCE_MAP` lookup → uint16
- 결과는 frozen tuple (순서 보존)

`RuleSpec.id` 가 등록된 룰인지 등은 검증 안 함 — 다른 단계 책임.

### Runtime 확장 (19차)

```python
# rule_runtime.py — fire_rule 시그니처 확장

def fire_rule(
    engine: Engine,
    definition: RuleDefinition,
    condition: ConditionTree,
    output: RuleOutputTemplate,
    *,
    subject_id: int,
    context: Mapping[str, Any],
    required_evidence: RequiredEvidenceTemplate | None = None,  # 신규
) -> int | None: ...
```

동작 변경:
- `required_evidence` 인자 추가, 기본값 `None`
- condition true 시 claim 생성 직후 각 evidence_type 마다 `engine.add_gap` 호출
- `required_evidence=None` 또는 `evidence_types=()` 면 Gap 생성 안 함 (16차 동작과 동일)

```python
# pseudo-code
if evaluate_condition(...):
    claim_id = engine.add_claim(...)
    if required_evidence is not None:
        for ev_type in required_evidence.evidence_types:
            engine.add_gap(
                claim_id=claim_id,
                gap_type=GAP_TYPE_MISSING_EVIDENCE,
                required_evidence_type=ev_type,
                severity=DEFAULT_GAP_SEVERITY,
                rule_id=definition.id,
            )
    engine.update_rule_stats(..., firing_delta=1)
    return claim_id
return None
```

기본값 `None` 덕분에 기존 16차 호출자는 변경 없이 동작 — 하위 호환.

### Error 분기

| 상황 | 결과 |
|---|---|
| `required_evidence` 누락 또는 `[]` | Gap 0개 (정상) |
| `required_evidence` 가 list 아님 | `TypeError` |
| 원소가 string 아님 | `TypeError` |
| 원소가 `REQUIRED_EVIDENCE_MAP` 에 없음 | `ValueError("unknown evidence type: ...")` |
| 매핑 정합성 위반 | 모듈 로딩 `AssertionError` |

### Out of scope (MVP)

- **Gap severity 차별화** — yaml 에서 per-evidence severity 표기. MVP 는 `0.5` 고정.
- **다양한 GapType** — `MISSING_EVIDENCE` 외 (예: `STALE_EVIDENCE`, `AMBIGUOUS_EVIDENCE`). 별도 결정점.
- **Gap 중복 방지** — 같은 `(claim_subject, required_evidence_type)` dedup. 별도 merge 단계.
- **Cross-claim Gap** — 여러 claim 의 공통 gap 합치기.
- **Gap 자체에 confidence / reason_code** — gap 메타 확장.
- **Gap → Action 연결** — gap 이 어떤 도구/도메인 action 으로 메워질 수 있는지.
- **`compile_rule_output` 통합** — required_evidence 처리는 의도적으로 별도 함수로 분리.

### YAML loader 동작 변경 없음

`load_rule_spec` / `load_rule_spec_from_yaml` / `compile_rule_output` 모두 변경 없음. `required_evidence` 는 여전히 `spec.raw["output"]["claim"]["required_evidence"]` 에 보존만 됨. 18차에서 `compile_required_evidence(spec)` 가 처음 검증.

### Position in flow

```text
YAML
  ↓ load_rule_spec_from_yaml
RuleSpec
  ↓ register_rule_spec
  ↓ compile_rule_condition       → ConditionTree
  ↓ compile_rule_output          → RuleOutputTemplate
  ↓ compile_required_evidence    → RequiredEvidenceTemplate    ⟵ 18차 신규
  ↓ fire_rule(..., required_evidence=evidence_template)        ⟵ 19차 확장
Claim + 0 or N Gaps
```

19차 끝나면 룰 firing 의 출력이 완성된다 — claim + 필요한 gaps + firing_count.

---

## 15. Rule firing trace (MVP)

`fire_rule` 은 발화 결과를 `claim_id | None` 으로만 알려준다. **왜** 발화했는지 / 왜 안 했는지 / 어떤 condition predicate 가 어떻게 평가됐는지를 추적하려면 별도 함수 `fire_rule_with_trace` 가 필요하다. 이 섹션은 22차 구현의 전제.

### Function 비대칭 (condition trace 와는 다름)

조건 평가의 trace 와 **결정적으로 다른 점**: 두 firing 함수 모두 실제로 상태를 변경한다.

| | `fire_rule` | `fire_rule_with_trace` |
|---|---|---|
| 반환값 | `int \| None` (claim_id) | `FiringTrace` |
| Engine 상태 변경 | yes — Claim/Gap 생성, firing_count +1 | **yes — 동일** |
| condition 평가 | 1회 (full eval internally, 결과만 사용) | 1회 (trace 도 함께 생성) |
| 미등록 rule | `KeyError` (fail-fast) | `KeyError` (fail-fast, trace 미생성) |

`evaluate_condition` ↔ `evaluate_condition_with_trace` 의 비대칭은 "fast path 는 짧게 / explain path 는 완전 평가" 였다. 여기는 다르다 — **둘 다 실제 발화 함수**이고, 단지 반환값이 다를 뿐.

> 핵심: trace 함수라고 해서 "설명만 하고 상태는 안 건드림" 으로 만들면 안 된다. `fire_rule_with_trace` 는 rule firing **runtime** 함수다.

### FiringTrace 구조

```python
@dataclass(frozen=True)
class FiringTrace:
    rule_id: int
    rule_version: int
    subject_id: int
    fired: bool
    condition_trace: Trace      # condition.Trace (= PredicateTrace | CombinatorTrace)
    claim_id: int | None
    gap_ids: tuple[int, ...]
```

`condition_trace` 는 `evaluate_condition_with_trace` 가 반환하는 `Trace` 객체 (조건 평가의 전체 설명).

### 불변식 (반드시 잠가야 할 것)

1. **`trace.fired == (trace.claim_id is not None)`**
   - 두 표현이 항상 같은 사실을 가리킨다 — 별도 슬롯이지만 의미 일치.
2. **`fired=False ⇒ claim_id=None and gap_ids=()`**
   - 발화 안 했으면 Claim/Gap 0개.
3. **`fired=True and required_evidence is None ⇒ gap_ids=()`**
   - 발화했지만 required_evidence 없으면 gap_ids 빈 튜플.
4. **`fired=True and required_evidence.evidence_types ⇒ len(gap_ids) == len(evidence_types)`**
   - 각 evidence type 마다 정확히 1개 gap.
5. **`trace.condition_trace.result == trace.fired`** (단, 미등록 rule 은 KeyError 로 trace 미생성)
   - 평가 결과와 발화 결과 일치.

### Engine ↔ Trace 분리

- **Engine 은 trace 를 저장하지 않는다** — 반환만, 호출자 책임.
- `RuleStats` (aggregate: firing_count 등) 는 계속 Engine 이 보유.
- 두 역할 구분: trace = detailed event, stats = aggregate.
- 무한 누적/persistence 부담은 호출자 (logger / 외부 store) 에게 넘김.

### Internal sharing (divergence 방지)

`fire_rule` 과 `fire_rule_with_trace` 의 로직이 두 군데로 복사되면 한쪽이 나중에 흐른다 — 가장 흔한 AI 실수.

해결: 두 공개 함수는 **단일 private helper** 만 호출한다.

```python
def _fire_rule_core(...) -> FiringTrace:
    """Single source of truth. fire_rule / fire_rule_with_trace 둘 다 이걸 호출."""
    engine.get_rule_stats(...)            # pre-check (fail-fast)
    condition_trace = evaluate_condition_with_trace(condition, context)

    if not condition_trace.result:
        return FiringTrace(
            ...,
            fired=False,
            condition_trace=condition_trace,
            claim_id=None,
            gap_ids=(),
        )

    claim_id = engine.add_claim(...)
    gap_ids = []
    if required_evidence is not None:
        for ev_type in required_evidence.evidence_types:
            gap_ids.append(engine.add_gap(...))
    engine.update_rule_stats(..., firing_delta=1)

    return FiringTrace(
        ...,
        fired=True,
        condition_trace=condition_trace,
        claim_id=claim_id,
        gap_ids=tuple(gap_ids),
    )


def fire_rule(...) -> int | None:
    return _fire_rule_core(...).claim_id


def fire_rule_with_trace(...) -> FiringTrace:
    return _fire_rule_core(...)
```

**의도된 trade-off**: `fire_rule` 의 fast path 도 항상 `evaluate_condition_with_trace` (full eval) 를 호출하게 됨. condition 평가가 한 번뿐이라 divergence 위험은 0. fast path 성능 차이는 MVP 에서 미미. 성능이 측정 가능한 병목이 되면 별도 결정점.

### Pre-check 동작 보존

`fire_rule` 의 16차 fail-fast 동작 그대로:
- `_fire_rule_core` 진입 즉시 `engine.get_rule_stats(rule_id, version)` 호출
- 미등록 rule → `KeyError` raise, **FiringTrace 안 만들어짐**
- 부분 mutation (claim 만 생기고 stats 못 갱신) 방지

이 동작 자체는 trace 가 있든 없든 동일. `fire_rule_with_trace` 는 미등록 rule 을 try/except 로 잡아 "fired=False trace" 로 만들지 **않는다** — 미등록은 호출자 버그이므로 KeyError 가 맞다.

### 하위 호환성

`fire_rule` 의 시그니처는 **변경 없음**:

```python
fire_rule(
    engine, definition, condition, output,
    *,
    subject_id, context,
    required_evidence=None,
) -> int | None
```

16~19차 호출자 코드 한 줄도 안 깨짐.

### Out of scope (MVP)

- **Trace 영속화** — Engine 저장 / DB 저장 / 직렬화 (JSON/YAML)
- **Trace timestamp** — firing 시간 기록 (필요해지면 별도 결정점)
- **Trace context snapshot** — 입력 context 의 deep copy 저장
- **Trace pretty-printer / repr 강화**
- **Bulk fire 의 trace 모음** — 여러 룰 동시 firing 시 trace 집합
- **Trace ↔ RuleStats 자동 연동** — observed_precision 자동 갱신 등
- **Trace diff/comparison** — 두 firing trace 비교

### Tests (22차 최소 세트)

1. `condition true` → `fired=True`, `claim_id` 값 존재, `condition_trace.result=True`
2. `condition false (mismatch)` → `fired=False`, `claim_id=None`, `MISMATCH` reason 자식 trace 확인
3. `condition false (missing field)` → `MISSING_FIELD` reason 확인
4. `required_evidence=None` → `gap_ids=()`
5. `required_evidence 3개` → `len(gap_ids)==3`, 각 id 로 `engine.get_gap` 조회 가능
6. 미등록 rule → `KeyError` 그대로, trace 미생성
7. **불변식**: `trace.fired == (trace.claim_id is not None)`
8. YAML full chain end-to-end (compile 4 + register + fire_with_trace)
9. **하위 호환**: 기존 `fire_rule` 테스트 (test_rule_runtime.py 의 16/19차 테스트들) 그대로 통과
10. **상태 변화 동등성**: 동일 입력으로 `fire_rule` 과 `fire_rule_with_trace` 가 만든 engine 상태(Claim/Gap 개수, firing_count) 가 일치

### Position in flow

```text
PR2 까지:
  YAML → RuleSpec → compile 4종 → fire_rule → Claim + Gaps + stats

PR3 (이 결정):
  YAML → RuleSpec → compile 4종 → fire_rule_with_trace → FiringTrace
                                                         ↳ rule_id, version, subject_id
                                                         ↳ fired
                                                         ↳ condition_trace
                                                         ↳ claim_id, gap_ids

기존 fire_rule 은 그대로 동작 (하위 호환). 둘은 단일 `_fire_rule_core` 공유.
```

---

## 16. Gap dedup (MVP)

같은 의미의 Required Evidence Gap 이 반복 생성되지 않도록 한다. **MVP 는 exact-match dedup** — semantic merge / 유사도 / LLM 판단 안 함.

### 핵심 문제

PR2 §14 의 Gap 모델은 `Gap.claim_id` 단일 필드로 claim 에 강하게 묶여있다. 같은 룰을 같은 subject 에 두 번 firing 하면:

```text
1번째 fire: Claim A + Gap(g1, g2, g3) for (os_family, exact_version, package)
2번째 fire: Claim B + Gap(g4, g5, g6) for same evidence types  ← 중복!
```

이건 운영 노이즈를 만든다. dedup 필요.

### 결정사항

**1. dedup scope**: subject + rule scoped

dedup key:

```python
GapDedupKey = (subject_id, created_by_rule, gap_type, required_evidence_type)
```

키 필드별 이유:

| 필드 | 이유 |
|---|---|
| `subject_id` | 어느 entity 에 대한 gap 인지 — 다른 entity 는 별개 |
| `created_by_rule` | 어느 룰의 gap 인지 — 다른 룰이 같은 evidence 요구해도 별개 |
| `gap_type` | 같은 evidence_type 이라도 gap 종류 다르면 별개 (안전장치) |
| `required_evidence_type` | 진짜 dedup 대상 — 같은 종류 evidence 요구 |

명시적 제외:

| 제외 필드 | 이유 |
|---|---|
| `rule_version` | 룰 버전 올라도 같은 subject 에 같은 evidence slot 요구하면 같은 gap. version 마다 새 gap 만들면 누적 폭발 |
| `severity` | severity 는 gap 의 우선순위 속성이지, "무슨 evidence 가 부족한가" 의 정체성 아님. severity 다른 두 gap = 같은 의미의 gap |

`subject_id` 는 `Gap` 에 직접 없음 — `engine.get_claim(claim_id).subject_id` 로 도출.

**2. Gap.claim_id 의미 약화**

```text
이전: Gap.claim_id = 이 Gap 이 속한 유일한 Claim
이후: Gap.claim_id = 이 Gap 을 최초로 등록한 Claim
```

Gap dataclass 구조는 **변경 없음** (claim_id 그대로 단일 필드). Phase 2 §14 의 "Gap.claim_id 로 명시적 link" 결정은 유지 — 단 의미가 "first registering" 으로 약화.

`Gap.claim_id` 를 `tuple[int, ...]` 로 바꾸는 큰 스키마 변경은 **MVP 밖**.

**3. Engine 내부 참조 인덱스**

```python
# Engine 신규 슬롯
_gap_dedup_index: dict[GapDedupKey, int]   # key → gap_id
_claim_gap_refs: dict[int, set[int]]       # claim_id → set of referenced gap_ids
```

`_claim_gap_refs` 가 핵심 — Gap 의 의미 약화로 인한 정보 손실 방지.

```text
fire SSH_001 on entity:1 (1번째):
  Claim 1 생성, Gap g1/g2/g3 생성
  _claim_gap_refs[1] = {g1, g2, g3}
  _gap_dedup_index[(1, RULE_SSH, GAP_MISSING, OS_FAMILY)] = g1
  ...

fire SSH_001 on entity:1 (2번째):
  Claim 2 생성, dedup hit → g1/g2/g3 재사용
  _claim_gap_refs[2] = {g1, g2, g3}  ← 같은 set
  _gap_dedup_index 변화 없음
```

이제 어느 Claim 이 어떤 Gap 을 요구했는지 Engine 상태에서 추적 가능.

**4. `gaps_for_claim` 의미 확장**

```python
# 이전 (Phase 2):
def gaps_for_claim(self, claim_id: int) -> list[Gap]:
    return [g for g in self._gaps.values() if g.claim_id == claim_id]

# 이후 (PR4):
def gaps_for_claim(self, claim_id: int) -> list[Gap]:
    return [self._gaps[gid] for gid in self._claim_gap_refs.get(claim_id, ())]
```

"이 Claim 이 참조하는 모든 Gap" 으로 의미 확장. dedup 으로 reuse 된 gap 도 포함.

기존 Phase 2 호출자에게는 동작 동일 (dedup 없으면 동일 결과). dedup 발생한 시점부터 의미가 살아남.

**5. `Engine.add_gap` 변경**

```python
def add_gap(
    self,
    claim_id: int,
    gap_type: int,
    required_evidence_type: int,
    severity: float,
    rule_id: int,
) -> int:
    if claim_id not in self._claims:
        raise KeyError(...)

    subject_id = self._claims[claim_id].subject_id
    key = (subject_id, rule_id, gap_type, required_evidence_type)

    if key in self._gap_dedup_index:
        # Dedup hit — 기존 gap 재사용, 새 gap 안 만듦
        existing_gap_id = self._gap_dedup_index[key]
        self._claim_gap_refs.setdefault(claim_id, set()).add(existing_gap_id)
        return existing_gap_id

    # 신규 gap
    gap_id = self._allocate_id("gap")
    self._gaps[gap_id] = Gap(
        id=gap_id,
        claim_id=claim_id,  # first registering claim
        type=gap_type,
        required_evidence_type=required_evidence_type,
        severity=ScoreValue(severity),
        created_by_rule=rule_id,
    )
    self._gap_dedup_index[key] = gap_id
    self._claim_gap_refs.setdefault(claim_id, set()).add(gap_id)
    return gap_id
```

호출자 시그니처/반환 변경 0 — 여전히 `gap_id` 반환. dedup 발생 시 기존 gap_id 반환.

**6. severity 정책**

```text
- dedup key 에 severity 포함 안 함
- 동일 key 재사용 시 기존 Gap 의 severity 유지
- severity merge / update / max-of-N 등은 PR4 범위 밖
```

문서에 명시. 나중에 정책 결정점 열릴 때 별도 PR.

**7. FiringTrace.gap_ids 의미**

```text
gap_ids = [신규 또는 재사용된 gap_id 들 — 호출 순서대로]
```

Phase 3 §15 의 정의 그대로 유지 ("실제 생성 또는 재사용된 Gap id 반환"). dedup hit 면 기존 id 가 들어감.

**8. RuleStats / Claim 의미 보존**

| | dedup 발생해도 |
|---|---|
| Claim | 매 firing 마다 생성 (의미 변화 0) |
| `RuleStats.firing_count` | dedup 무관 +1 (의미 변화 0) |
| FiringTrace 의 다른 필드 | 변화 0 |

### 불변식 (테스트로 잠금)

1. **같은 (subject_id, rule_id, gap_type, evidence_type) 은 정확히 하나의 Gap**
2. **`gaps_for_claim(claim_id)` 는 해당 claim 의 `_claim_gap_refs` 와 일치**
3. **dedup hit 시에도 `FiringTrace.gap_ids` 는 비지 않음** (재사용 id 반환)
4. **2번째 firing 의 `gap_ids` 는 1번째와 동일** (같은 input 일 때)
5. **`gap.severity` 는 최초 등록 시 값으로 유지** (재사용 시 변경 없음)
6. **`Claim` 은 매 firing 생성 — dedup 영향 없음**
7. **`RuleStats.firing_count` 는 매 firing +1 — dedup 영향 없음**

### Out of scope (MVP)

- **`Gap.claim_id` → `claim_ids` tuple 화** — 큰 스키마 변경, MVP 밖
- **Cross-rule dedup** — 다른 룰이 같은 evidence 요구하는 경우 합치기
- **Cross-version dedup 확장 / 격리** — 현재는 version 무시. 격리 필요해지면 별도 결정
- **severity merge / max-of-N / history**
- **Semantic merge / 유사도 / LLM 판단** — exact match 만
- **Gap 삭제 / archive / TTL** — 영구 보존
- **`_gap_dedup_index` 외부 노출** — public API 미공개

### Tests (27/28차 최소 세트)

1. **같은 rule + 같은 subject 2회 firing**: Claim 2개, Gap 중복 없음, 2번째 trace.gap_ids = 1번째 gap_ids
2. **`gaps_for_claim(Claim A)`**: 1번째 gap_ids 반환
3. **`gaps_for_claim(Claim B)`**: 같은 (재사용) gap_ids 반환
4. **다른 subject**: 같은 rule/evidence 라도 신규 Gap
5. **다른 rule**: 같은 subject/evidence 라도 신규 Gap
6. **같은 rule/subject/evidence + 다른 gap_type**: 신규 Gap
7. **다른 rule_version**: 기존 gap 재사용 (version 무시)
8. **다른 severity**: 기존 gap 재사용 (severity 무시), 기존 severity 유지
9. **condition false**: Claim/Gap/ref 모두 0
10. **`RuleStats.firing_count`**: 매 firing +1 (dedup 무관)
11. **기존 394 tests 그대로 통과** (회귀 방지)

### Position in flow

```text
PR3 까지:
  fire_rule_with_trace → Claim 매번 생성 + Gap 매번 생성 + firing_count +1

PR4:
  fire_rule_with_trace → Claim 매번 생성 + Gap dedup (subject+rule+type+evidence)
                                       + firing_count +1
                                       + _claim_gap_refs 업데이트
                                       → gap_ids 에 재사용 id 포함
```

구현 단계 (27/28차):
- 27차: `Engine` 에 `_gap_dedup_index` / `_claim_gap_refs` 추가, `add_gap` dedup 로직, `gaps_for_claim` 의미 확장
- 28차: tests (위 11개 시나리오) + 회귀 보장

## 17. Evidence-based Gap resolution (MVP)

> 상태: 30/31/32차 (PR5). Evidence 가 매칭 Gap 을 닫는 최소 루프. **Claim lifecycle (candidate→confirmed/refuted) 은 본 PR 범위 밖** — PR6.

### 17.1 목적

PR4 까지의 흐름:

```text
Rule fires → Claim + Gap(s) 생성 (또는 reuse)
Evidence 추가 → 어디에도 연결되지 않음
```

PR5 추가:

```text
Rule fires      → Claim + Gap(s)
Evidence 추가   → (변화 없음 — 기존 의미 유지)
resolve 호출    → Evidence 가 매칭 Gap 들을 닫음
```

즉, **"Evidence 가 Gap 을 닫는다"** 는 최소 루프만 만든다.
Evidence 의미는 PR1~PR4 와 동일 — `add_evidence` 자체에는 자동 부작용 없음.

### 17.2 저장 위치

```python
# Engine 내부 신규 슬롯
_gap_resolutions: dict[int, int]   # gap_id → 그 gap 을 resolve 한 evidence_id
```

- `Gap` dataclass 는 **변경 없음** (PR2 §14 / PR4 §16 의 단일 필드 구조 유지)
- 외부에 노출은 `gap_resolution(gap_id) -> int | None` 메서드를 통해서만
- `_gap_resolutions` 자체는 public 아님

이유 (PR4 의 `_gap_dedup_index` 와 동일 패턴):

| 옵션 | 채택 | 이유 |
|---|---|---|
| (A) `Gap.resolved_by_evidence_id` 필드 추가 | ✗ | dataclass 변경. PR4 의 "Gap dataclass 단일 필드" 결정과 충돌 |
| (B) Engine 내부 dict | ✓ | dataclass 보존. PR4 패턴과 일관. 추가 인덱스가 자연스러움 |
| (C) Relation 으로 표현 | ✗ | "resolved by" 는 의미 관계가 아닌 lifecycle 상태. Relation 의미 오염 |

### 17.3 API

```python
def resolve_gaps_for_evidence(self, evidence_id: int) -> tuple[int, ...]:
    """주어진 evidence 로 매칭되는 unresolved gap 들을 resolve.

    매칭 규칙:
        gap.required_evidence_type == evidence.type

    검사 범위:
        gaps_for_claim(evidence.claim_id) — evidence 가 속한 claim 의 gap 들만

    동작:
        - 매칭되는 gap 들 중 _gap_resolutions 에 없는 것만 resolve
        - 이미 resolved 된 gap 은 건너뜀 (first evidence 유지, overwrite 금지)
        - 이번 호출에서 새로 resolved 된 gap_id 들만 반환

    반환:
        gap_id 오름차순 tuple. 매칭 없거나 모두 already-resolved 면 빈 tuple.

    예외:
        KeyError — unknown evidence_id
    """

def gap_resolution(self, gap_id: int) -> int | None:
    """gap 을 resolve 한 evidence_id 반환. unresolved 면 None.

    예외:
        KeyError — unknown gap_id
    """
```

### 17.4 매칭 규칙

```python
gap.required_evidence_type == evidence.type
```

- `gap.created_by_rule` 은 **매칭 조건에 포함하지 않음**
- `gap.gap_type` 은 매칭 조건에 포함하지 않음 (현재 단일값 `MISSING_EVIDENCE=1`)
- `gap.severity` 는 매칭에 무관

### 17.5 검사 범위 — 매우 중요

```python
search_scope = self.gaps_for_claim(evidence.claim_id)
```

즉, **evidence 가 속한 claim 의 gap 들만** 검사한다.

**Global cross-rule search/resolution 은 제외.**
단, `evidence.claim_id` 가 참조하는 gap 목록 안에서는 `created_by_rule` 을 매칭 조건으로 보지 않는다.

> 표현 주의: "cross-rule resolution 제외" 라고만 쓰면 모호. 정확히는:
> - **금지**: engine 전체 / subject 전체 / rule 전체 gap 검색
> - **허용**: 같은 claim 이 참조하는 gap 중 `required_evidence_type` 매칭되는 것 모두 resolve — 그 gap 들이 서로 다른 rule 에서 만들어졌어도 OK (검사 범위 안이라면)

PR5 시점에서는 한 claim 안에 서로 다른 rule_id 의 gap 이 들어올 일은 일반적으로 없지만, 위 정의는 **검사 범위로 boundary 를 그은 것**이지 rule_id 로 boundary 를 그은 것이 아니다.

### 17.6 Cross-claim semantics (PR4 dedup 과의 상호작용)

PR4 dedup 으로 여러 Claim 이 같은 Gap 을 공유할 수 있다.

```python
# fire_rule 2회 (같은 입력)
claim_a = fire_rule(...)  # → Claim A, Gap g1
claim_b = fire_rule(...)  # → Claim B, Gap g1 (reuse)

# Claim A 에 evidence 추가 + resolve
ev = engine.add_evidence(claim_a, raw_ref_id=..., evidence_type=..., strength=...)
resolved = engine.resolve_gaps_for_evidence(ev)  # → (g1,)

# 결과: g1 은 resolved
engine.gap_resolution(g1)  # → ev (Claim B 에서 봐도 동일)
```

**Resolution 은 gap-scoped.** 한 claim 의 evidence 로 닫힌 gap 은 그 gap 을 share 하는 다른 claim 에서도 resolved 로 보인다.

이유:
- Gap 자체가 PR4 부터 "subject+rule+type+evidence" 정체성 — claim_id 보다 위 레벨
- "어떤 evidence 가 그 정체성의 gap 을 채웠는가" 는 claim 과 독립적인 사실
- Claim 별로 다른 resolution 을 갖는다면 Gap 정체성이 다시 claim 종속이 되어 PR4 와 모순

### 17.7 `add_evidence` 의미 — 변화 없음

```python
def add_evidence(self, claim_id, raw_ref_id, evidence_type, strength) -> int:
    # PR1 부터 의미 그대로. 자동 resolve 없음.
```

이유:

| | 자동 resolve 의 문제 |
|---|---|
| 순서 의존성 | `add_evidence` 시점에 모든 Gap 이 이미 만들어졌다는 보장 없음 |
| 명시성 | "evidence 가 gap 을 닫았다" 는 의도된 행위여야 함, 부작용 X |
| 테스트성 | resolve 시점을 명시적으로 분리해야 invariant 검증이 깨끗 |
| 미래 확장성 | strength/score-weighted resolution, partial resolution 등은 명시적 메서드여야 자연스러움 |

→ 호출자가 명시적으로 `resolve_gaps_for_evidence(evidence_id)` 호출.

### 17.8 Re-resolution 정책 — first evidence 유지

```python
# 첫 evidence
ev1 = engine.add_evidence(claim, type=T, ...)
engine.resolve_gaps_for_evidence(ev1)  # → (g1,)
engine.gap_resolution(g1)              # → ev1

# 두 번째 evidence (같은 type)
ev2 = engine.add_evidence(claim, type=T, ...)
engine.resolve_gaps_for_evidence(ev2)  # → () (g1 은 이미 resolved, 빈 tuple 반환)
engine.gap_resolution(g1)              # → ev1 (유지, overwrite 없음)
```

PR4 의 severity 정책 (`first registering keep, no merge`) 과 같은 패턴.

이유:
- "어떤 evidence 가 처음으로 gap 을 닫았는가" 는 stable 한 사실
- 덮어쓰면 동일 입력에 대한 결과가 호출 순서에 의존 (non-deterministic-feeling)
- Strength-weighted "더 좋은 evidence 로 교체" 같은 동작은 미래 PR 의 명시적 결정

### 17.9 반환 순서

```python
resolve_gaps_for_evidence(evidence_id) → tuple[int, ...]   # gap_id 오름차순
```

PR4 의 `gaps_for_claim` 과 동일한 결정성. `set` 의 iteration 비결정성 회피.

### 17.10 예외

| 입력 | 동작 |
|---|---|
| unknown `evidence_id` (`resolve_gaps_for_evidence`) | `KeyError` |
| unknown `gap_id` (`gap_resolution`) | `KeyError` |
| 매칭 gap 없음 | 빈 tuple 반환 (정상) |
| 모든 매칭 gap 이 이미 resolved | 빈 tuple 반환 (정상) |

`gap_resolution` 은 unknown gap_id 에서 `None` 이 아니라 `KeyError` — "resolution 미설정" 과 "gap 자체 없음" 을 구분.

### 17.11 보존 (impact 없음)

| | PR5 영향 |
|---|---|
| `Gap` dataclass | 없음 (필드 변경 없음) |
| `Claim` dataclass | 없음 |
| `Claim.status` | **자동 전이 없음** — PR6 범위 |
| `Evidence` dataclass | 없음 |
| `Relation` | 없음 (resolved-by 는 Relation 아님) |
| `add_evidence` 의미 | 없음 (자동 side effect 없음) |
| `add_gap` / dedup | 없음 |
| `gaps_for_claim` 의미 | 없음 (PR4 정의 그대로) |
| `RuleStats.firing_count` | 없음 |
| `fire_rule*` | 없음 |
| `compute_effective_confidence` | 없음 (scoring 변경 없음) |

### 17.12 Invariants (테스트로 잠금)

1. 매칭되는 unresolved gap 이 있으면 `resolve_gaps_for_evidence` 반환 tuple 에 포함
2. 매칭 gap 없으면 빈 tuple
3. 이미 resolved 된 gap 은 두 번째 호출에서 빈 tuple (first evidence 유지)
4. `gap_resolution(gap_id)` 는 resolve 한 evidence_id 반환, 또는 `None`
5. 반환 순서는 항상 gap_id 오름차순
6. 같은 claim 의 evidence 라도 type 이 다르면 다른 gap 들에 매칭
7. **Cross-claim gap-scoped resolution**: PR4 dedup 으로 share 된 gap 은 한 claim 에서 resolved 되면 다른 claim 에서도 resolved 로 보임
8. unknown `evidence_id` → `KeyError`
9. unknown `gap_id` (in `gap_resolution`) → `KeyError`
10. `add_evidence` 자체는 `_gap_resolutions` 를 변경하지 않음 (자동 resolve 금지)
11. **기존 413 tests 그대로 통과** (회귀 방지)

### 17.13 Out of Scope (의도적 제외)

| 제외 | 이유 |
|---|---|
| `Claim.status` 자동 전이 (`candidate → confirmed/refuted`) | PR6 |
| Strength-weighted resolution (더 좋은 evidence 로 overwrite) | 명시적 정책 결정 필요 |
| Partial resolution / score-weighted gap close | PR6+ |
| Rollback / unresolve | 별도 결정점 |
| Resolution timestamp / history | 직렬화 PR 에서 |
| `add_evidence` 의 auto-resolve side effect | 17.7 참조 |
| Engine 전체 / subject 전체 / rule 전체 gap 검색 | 17.5 참조 |
| Cross-rule global resolution | 17.5 참조 |
| `compute_effective_confidence` 가 resolved gap 을 고려 | scoring 변경은 별도 PR |
| Resolved gap 의 자동 archive / TTL | 별도 결정점 |

### 17.14 Position in flow

```text
PR4 까지:
  Rule fires → Claim + Gap (dedup) + firing_count +1
  Evidence 추가 → 자체 보존만

PR5:
  Rule fires → Claim + Gap (dedup) + firing_count +1
  Evidence 추가 → (변화 없음)
  resolve_gaps_for_evidence(ev) → 매칭 gap 들 닫음
                                  + _gap_resolutions 업데이트
                                  + 새로 resolved 된 gap_id tuple 반환
```

구현 단계 (31/32차):
- 31차: `Engine._gap_resolutions` 추가, `resolve_gaps_for_evidence` / `gap_resolution` 구현
- 32차: tests (위 11개 invariant + 추가 케이스) + 회귀 보장

## 18. Claim lifecycle (MVP)

> 상태: 30/31/32차 (PR6). `candidate → confirmed` 단일 전이 + 명시 호출 API.
> **`refuted` 전이 / scoring 변경 / history / confidence 재계산 / 자동 전이는 본 PR 범위 밖** — PR7+.

### 18.1 목적

PR5 까지의 흐름:

```text
Rule fires       → Claim (candidate) + Gap(s) (dedup)
Evidence 추가    → (의미 변화 없음)
resolve 호출     → matching Gap 들 닫음
gap_resolution   → 누가 닫았는지 조회
```

PR6 추가:

```text
필요시 confirm_claim_if_ready(claim_id) 호출
  → 이 Claim 이 참조하는 모든 Gap 이 resolved 인지 검사
  → 조건 만족 시 candidate → confirmed
```

즉 PR6 는 **Claim 의 상태 전이** 최소 기능. 새 판단을 만드는 게 아니라
"이미 존재하는 Claim 이 요구했던 Gap 들이 다 채워졌는가?" 만 확인한다.

### 18.2 API

```python
def confirm_claim_if_ready(self, claim_id: int) -> bool:
    """모든 referenced Gap 이 resolved 면 candidate → confirmed.

    Returns:
        True  — 이번 호출로 전이가 발생함
        False — 전이가 발생하지 않음 (조건 불충족 / 이미 confirmed / refuted / Gap 0개)

    Raises:
        KeyError — unknown claim_id (PR1~PR5 의 fail-fast 패턴과 일관)

    Note:
        ``False`` 는 실패가 아니다. 예: 이미 confirmed 인 Claim 의 재호출은
        no-op 이므로 자연스럽게 False.
    """
```

API 이름 선택 (대안 vs 채택):

| 후보 | 채택 | 이유 |
|---|---|---|
| `promote_claim_if_resolved` | ✗ | "promote" 는 가치판단 함의 |
| `evaluate_claim_readiness` | ✗ | 동작 (전이) 보다 검사처럼 들림 |
| `confirm_claim_if_ready` | ✓ | 동작 + 조건 + 결과를 한 이름에 |

### 18.3 Resolved 의 정의 — PR5 truth-source 와 정합

```python
gap is resolved  ⇔  self.gap_resolution(gap.id) is not None
                 ⇔  gap.id in self._gap_resolutions
```

`Gap` dataclass 에는 `status` / `resolved_by_evidence_id` 같은 필드를 **추가하지 않는다**
(PR5 §17.2 결정 유지). PR5 의 `_gap_resolutions: dict[gap_id, evidence_id]` 가
유일한 resolved truth-source.

### 18.4 결정표 (전이 규칙)

| Claim 상태 | gap 개수 | 모든 gap resolved? | 결과 상태 | 반환 |
|---|---|---|---|---|
| `candidate` | 0 | — | `candidate` | `False` |
| `candidate` | 1+ | yes | **`confirmed`** | **`True`** |
| `candidate` | 1+ | no | `candidate` | `False` |
| `confirmed` | any | any | `confirmed` | `False` (no-op) |
| `refuted` | any | any | `refuted` | `False` (no-op) |

**Gap 0 개 candidate Claim 은 자동 confirm 금지**:
"검증 끝남" 이 아니라 "확인 근거 없음" 이 PR6 의 해석. confirm 의 의미를
"resolved gap 들이 Claim 을 올렸다" 로 좁게 잠그기 위함.

### 18.5 Idempotency

```python
# 첫 호출
engine.confirm_claim_if_ready(c)  # → True  (전이 발생)

# 두 번째 호출
engine.confirm_claim_if_ready(c)  # → False (이미 confirmed, no-op)
engine.get_claim(c).status         # → CLAIM_STATUS_CONFIRMED (유지)

# refuted 는 PR6 에서 안 다룸 — 외부에서 refuted 로 만들 방법이 현재 없지만,
# 만약 미래에 그런 상태가 들어와도 confirm_claim_if_ready 는 no-op 으로 보존
```

### 18.6 보존 (impact 없음)

| | PR6 영향 |
|---|---|
| `Gap` / `Evidence` / `Relation` dataclass | 없음 |
| `Claim` dataclass | 없음 (`status: int` 필드 그대로 사용, `replace()` 로 갱신) |
| `add_claim` / `add_evidence` / `add_gap` 의미 | 없음 |
| `_gap_resolutions` / `_gap_dedup_index` / `_claim_gap_refs` | 없음 |
| `gaps_for_claim` / `gap_resolution` 의미 | 없음 |
| `fire_rule*` / `RuleStats.firing_count` | 없음 |
| `compute_effective_confidence` (scoring) | 없음 |
| `base_confidence` | 없음 (confidence 재계산 본 PR 범위 밖) |

### 18.7 Invariants (테스트로 잠금)

1. candidate + gap 0 개 → `False`, 상태 보존
2. candidate + 모든 gap resolved → `True`, 상태 `confirmed`
3. candidate + 일부 gap unresolved → `False`, 상태 보존 (`candidate`)
4. 이미 confirmed → `False`, 상태 보존 (no-op)
5. refuted → `False`, 상태 보존 (refuted 복구 금지)
6. 두 번째 호출 idempotent — 첫 호출 `True`, 두 번째 `False`, 상태 `confirmed` 유지
7. unknown `claim_id` → `KeyError` (PR1~PR5 fail-fast 패턴)
8. confirm 발생해도 `gaps_for_claim` / `gap_resolution` 결과 무변화
9. confirm 발생해도 `base_confidence` 무변화
10. **기존 425 tests 그대로 통과** (회귀 방지)

### 18.8 Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| `refuted` 전이 / contradiction evidence 정의 | PR7 |
| Auto-transition (resolve / add_evidence side effect) | 명시성 원칙 (§17.7 과 동일 정신) |
| `confidence` (`base_confidence` / `effective`) 재계산 | scoring 변경 별도 PR |
| `confirmed_at` timestamp / history / lifecycle trace | 직렬화 PR |
| Partial confirmation (일부 gap 만으로 confirm) | confirm 의 의미 약화 — 금지 |
| Evidence strength-weighted promotion | PR9+ |
| Gap 0 개 Claim 자동 confirm | 18.4 참조 |
| `refuted → candidate` 복구 / `confirmed → candidate` 강등 | 별도 결정점 |

### 18.9 Position in flow

```text
PR5 까지:
  Rule fires → Claim (candidate) + Gap (dedup) + firing_count +1
  resolve_gaps_for_evidence(ev) → matching gap 닫힘

PR6:
  Rule fires → Claim (candidate) + Gap
  resolve_gaps_for_evidence(ev) → matching gap 닫힘
  confirm_claim_if_ready(c)
    → all(gap_resolution(g.id) is not None for g in gaps_for_claim(c))
    → 만족 시 status = confirmed, True 반환
    → 아니면 no-op, False 반환
```

구현 단계 (31/32차) — **테스트 먼저 잠금 → 구현** 순서:
- 31차: tests (위 10개 invariant) — 현재 `AttributeError` 로 fail 하는 상태로 잠금
- 32차: `Engine.confirm_claim_if_ready` 구현 — 31차 테스트 통과로 입증

## 19. Claim refutation (MVP)

> 상태: 34/35/36차 (PR7). `candidate → refuted` 단일 전이 + 명시 contradiction 등록.
> **`confidence` 재계산 / history / 자동 추론 / `confirmed → refuted` 전이는 본 PR 범위 밖** — PR8+.

### 19.1 목적 — "모름" 과 "반박" 의 분리

PR6 까지의 흐름:

```text
Rule fires       → Claim (candidate) + Gap(s)
resolve(ev)      → matching Gap 닫힘
confirm_if_ready → 모든 Gap resolved 면 candidate → confirmed
```

PR7 추가:

```text
register_contradiction(claim, evidence)  → 명시 등록
refute_if_ready(claim)                   → contradiction 있으면 candidate → refuted
```

### 19.2 PR7 의 핵심 명제

> **Unresolved evidence gaps do not refute a claim.**
> **Only explicit contradiction relations can make a candidate claim refutable.**

한국어:

> 증거 부족은 반박이 아니다. 증거 부족은 "아직 모름" 이며 `candidate` 가 유지된다.
> 반박은 호출자가 명시적으로 등록한 contradiction relation 이 있을 때만 가능하다.

이 명제가 PR7 의 모든 결정을 지배한다. `refuted` 를 단순히 "confirm 의 반대" 로
잡으면 `candidate` (모름) 와 `refuted` (반박) 가 섞여 엔진 판단력이 흐려진다.

### 19.3 저장 위치 — Engine 내부 dict

```python
# Engine.__init__
self._contradictions: dict[int, set[int]] = {}  # claim_id → set of evidence_ids
```

`Evidence` / `Claim` / `Relation` dataclass 는 **변경 없음** (PR2~PR6 의 single-field
data 결정 유지). 외부 접근은 메서드를 통해서만.

PR4 의 `_gap_dedup_index` / `_claim_gap_refs`, PR5 의 `_gap_resolutions` 와 동일
패턴 — dataclass 보존 + Engine 내부 인덱스로 lifecycle 상태 표현.

### 19.4 API

```python
def register_contradiction(self, claim_id: int, evidence_id: int) -> bool:
    """Register an explicit contradiction relation: evidence contradicts claim.

    Returns:
        True  — 이번 호출로 새로 등록됨.
        False — (claim_id, evidence_id) 가 이미 등록돼 있음 (idempotent no-op).

    Raises:
        KeyError: unknown claim_id or unknown evidence_id.

    Notes:
        - **Cross-claim 허용**: ``evidence.claim_id == claim_id`` 는 강제하지 않는다.
          "Port 22 closed" 같은 다른 claim 의 evidence 가 "SSH exposed" claim 을
          반박하는 흐름이 contradiction 의 본질이다.
        - **Target status 무관**: confirmed / refuted claim 에도 등록 허용.
          데이터 등록과 lifecycle 결정은 분리 (refute_claim_if_ready 의 status
          guard 가 결정 시점에 동작).
        - **No semantic inference**: 엔진은 "이 evidence 가 정말 그 claim 을
          반박하는가" 를 판단하지 않는다. 호출자 책임.
    """

def contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]:
    """Return contradicting evidence_ids for the claim.

    Returns:
        evidence_id 오름차순 tuple. 없으면 빈 tuple.

    Raises:
        KeyError: unknown claim_id.
    """

def refute_claim_if_ready(self, claim_id: int) -> bool:
    """Transition candidate → refuted if at least one contradiction is registered.

    전이 조건:
        - ``claim.status == CLAIM_STATUS_CANDIDATE``
        - ``len(contradictions_for_claim(claim_id)) >= 1``

    Returns:
        True  — 이번 호출로 candidate → refuted 전이.
        False — 전이 없음 (조건 불충족 / 이미 confirmed / 이미 refuted).
                False 는 실패가 아니다 (no-op 도 False).

    Raises:
        KeyError: unknown claim_id.
    """
```

API 이름 선택 (PR6 패턴 미러):

| | PR6 | PR7 |
|---|---|---|
| 명시 호출 promotion | `confirm_claim_if_ready` | `refute_claim_if_ready` |
| Trigger 조건 | 모든 referenced gap resolved | ≥1 contradiction 등록됨 |

**의미는 단순 미러가 아니다** — confirm 은 "충분 조건" (gap 다 채워짐), refute 는
"존재 조건" (반박 1개라도). 19.7 결정표에서 잠금.

### 19.5 결정표 (refute 전이 규칙)

| Claim 상태 | contradictions 수 | 결과 상태 | 반환 |
|---|---|---|---|
| `candidate` | 0 | `candidate` | `False` |
| `candidate` | 1+ | **`refuted`** | **`True`** |
| `confirmed` | any | `confirmed` | `False` (no-op) |
| `refuted` | any | `refuted` | `False` (no-op) |

**Unresolved gap 의 영향은 0**:

| Claim 상태 | gap 상태 | contradictions | refute 결과 |
|---|---|---|---|
| `candidate` | 모두 unresolved | 0 | `False` (gap 부족은 반박 아님) |
| `candidate` | 모두 resolved | 0 | `False` (resolved gap 도 반박 아님) |
| `candidate` | 일부/전부 unresolved | 1+ | `True` (contradiction 만이 trigger) |

### 19.6 `register_contradiction` 결정표

| target claim 상태 | 새 (claim_id, evidence_id)? | 결과 | 반환 |
|---|---|---|---|
| any | 새로움 | `_contradictions[claim_id]` 에 추가 | `True` |
| any | 이미 등록됨 | 무변화 | `False` |

| 에러 케이스 | 동작 |
|---|---|
| unknown `claim_id` | `KeyError` |
| unknown `evidence_id` | `KeyError` |

evidence 의 cross-claim 여부 / target claim 의 status / target claim 의 gap 상태
모두 **등록 조건에 영향 없음**.

### 19.7 Idempotency

```python
# 첫 등록
engine.register_contradiction(c, e)  # → True

# 두 번째 등록 (같은 쌍)
engine.register_contradiction(c, e)  # → False (이미 있음)

# 첫 refute
engine.refute_claim_if_ready(c)  # → True (candidate → refuted)

# 두 번째 refute
engine.refute_claim_if_ready(c)  # → False (이미 refuted, no-op)
engine.get_claim(c).status        # → CLAIM_STATUS_REFUTED (유지)
```

PR4 dedup + PR5 first-keep + PR6 confirm idempotent 와 동일 정신.

### 19.8 보존 (impact 없음)

| | PR7 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` dataclass | 없음 |
| `add_claim` / `add_evidence` / `add_gap` 의미 | 없음 |
| `resolve_gaps_for_evidence` / `gap_resolution` 의미 | 없음 |
| `confirm_claim_if_ready` 의미 | 없음 |
| `gaps_for_claim` / `_gap_resolutions` | 없음 |
| `fire_rule*` / `RuleStats.firing_count` | 없음 |
| `base_confidence` / `compute_effective_confidence` | 없음 |

### 19.9 Invariants (테스트로 잠금)

1. candidate + 0 contradiction → `False`, 상태 보존
2. candidate + 1+ contradiction → `True`, 상태 `refuted`
3. **unresolved gap 만으로 refuted 금지** — PR7 핵심 명제 (§19.2)
4. **resolved gap 도 refute trigger 아님** — refute 의 trigger 는 contradiction 뿐
5. 이미 confirmed → `False`, 상태 보존 (PR7 범위 밖)
6. 이미 refuted → `False`, 상태 보존 (no-op)
7. unknown `claim_id` → `KeyError` (PR1~PR6 fail-fast 패턴)
8. `register_contradiction` idempotent — 같은 쌍 재호출 `False`
9. **Cross-claim contradiction 허용** — `evidence.claim_id != claim_id` 케이스도 `register_contradiction` 정상 동작
10. `register_contradiction` 은 target claim 의 status 와 무관 (confirmed/refuted 에도 등록 가능)
11. `register_contradiction` / `refute_claim_if_ready` 호출은 gap state / base_confidence / 다른 claim 의 상태 무변화
12. `contradictions_for_claim` 은 evidence_id 오름차순 (PR5 결정성 패턴)
13. unknown `evidence_id` 등록 시도 → `KeyError`
14. 기존 435 tests 그대로 통과 (회귀 방지)

### 19.10 Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| `confirmed → refuted` 전이 | history / audit / 재판단 정책 필요 — PR8+ |
| `refuted → candidate` 복구 | 별도 결정점 |
| `confirmed → disputed` / `superseded` / `retracted` | 더 정교한 상태 — PR9+ |
| `confidence` (`base_confidence` / `effective`) 재계산 | scoring 변경 별도 PR |
| `refuted_at` timestamp / contradiction registration history | 직렬화 PR |
| **Semantic contradiction inference** — 엔진이 의미 추론 | 호출자 책임 (§19.4 Notes) |
| Contradiction scope check (target/entity/scope 일치 검증) | 도메인 판단, core 밖 |
| `evidence.type` 기반 contradiction rule | rule engine 확장 |
| Lifecycle trace (refuted 이벤트 trace) | PR3 trace 구조 확장 별도 PR |
| Auto refute (resolve / add_evidence / register_contradiction 안 side effect) | 명시성 원칙 (§17.7 정신) |

### 19.11 Position in flow

```text
PR6 까지:
  Rule fires → Claim (candidate) + Gap
  resolve(ev)  → gap 닫힘
  confirm_if_ready(c) → 모든 gap resolved 면 candidate → confirmed

PR7:
  Rule fires → Claim (candidate) + Gap
  resolve(ev)  → gap 닫힘 (변화 없음)
  register_contradiction(c, ev_b) → 명시 등록
  refute_if_ready(c) → contradiction 1+ 있으면 candidate → refuted
                       (gap 상태 무관 — §19.2 명제)
```

구현 단계 (35/36차) — **테스트 먼저 잠금 → 구현** 순서:
- 35차: tests (위 14개 invariant 중 1~13) — `AttributeError` 로 fail 하는 상태로 잠금
- 36차: `Engine.register_contradiction` / `contradictions_for_claim` / `refute_claim_if_ready` 구현 — 35차 테스트 통과로 입증

## 20. Disputed lifecycle (MVP)

> 상태: 38/39/40차 (PR8). `confirmed → disputed` 단일 전이.
> **`disputed → *` 해소 정책 / `superseded` / scoring / history 는 본 PR 범위 밖** — PR9+.

### 20.1 PR8 의 한 줄 정의

> **PR8 은 판단 삼각형을 무너뜨리는 PR 이 아니라, confirmed 이후 충돌을 안전하게
> 격리하기 위해 `disputed` 라는 재검토 상태를 추가하는 PR 이다.**

### 20.2 핵심 명제

```text
A confirmed claim with explicit contradiction is not automatically refuted.
It becomes disputed.

Disputed means the claim was previously confirmed, but now has registered
contradiction evidence requiring re-evaluation.
```

한국어:

```text
confirmed Claim 에 contradiction 이 생겼다고 곧바로 refuted 가 되는 것은 아니다.
그 상태는 disputed 다.

disputed 는 과거에는 confirmed 였지만, 이후 반대 근거가 등록되어 재검토가
필요한 상태다.
```

`confirmed → refuted` 직접 전이는 PR7 §19 의 `refute_claim_if_ready` status
guard 에서 이미 금지됨. PR8 은 그 부분을 우회하는 게 아니라 **별도 상태** 로
격리.

### 20.3 lifecycle 위치 — 삼각형은 보존, 격리 레이어 추가

```text
기본 판단 삼각형 (PR6/PR7 보존):
  candidate
    ├─ confirmed   (PR6)
    └─ refuted     (PR7)

Post-confirmation conflict quarantine (PR8 추가):
  confirmed
    └─ disputed    (PR8)  ← confirmed Claim 에 명시 contradiction 등록되면 전이
```

`disputed` 는 삼각형의 4번째 꼭짓점이 아니라 **confirmed 위에 얹는 격리 상태**.
`candidate → disputed`, `refuted → disputed` 같은 진입은 금지.

### 20.4 새 상수 — `CLAIM_STATUS_DISPUTED = 3`

```python
# ragcore/types.py
CLAIM_STATUS_CANDIDATE = 0
CLAIM_STATUS_CONFIRMED = 1
CLAIM_STATUS_REFUTED   = 2
CLAIM_STATUS_DISPUTED  = 3   # PR8 추가
```

public export 추가 (`ragcore/__init__.py`).

### 20.5 Sub-decision D — YAML 룰 output 에 노출 안 함

`disputed` 는 lifecycle 전이 결과 상태이지 **룰이 처음부터 만드는 초기 상태가
아니다**. 따라서 `ragcore/rule_output.py` 의 정적 매핑 / validation 에는
**추가하지 않는다**:

```python
# 그대로 유지 (변경 없음)
CLAIM_STATUS_MAP: dict[str, int] = {
    "candidate": CLAIM_STATUS_CANDIDATE,
    "confirmed": CLAIM_STATUS_CONFIRMED,
    "refuted":   CLAIM_STATUS_REFUTED,
}

_ALLOWED_CLAIM_STATUSES = frozenset({
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_REFUTED,
})
```

이유:

> A YAML rule MUST NOT create a disputed claim directly. Only
> `dispute_claim_if_ready` may transition a confirmed claim to disputed.

만약 YAML 룰이 다음과 같이 작성되면 컴파일 단계에서 거부된다 (의도된 동작):

```yaml
output:
  claim:
    status: disputed   # → ValueError at rule_output.compile time
```

이게 `disputed` 의 lifecycle 의미를 코드 차원에서 보호한다.

### 20.6 API

```python
def dispute_claim_if_ready(self, claim_id: int) -> bool:
    """Transition confirmed → disputed if at least one contradiction is registered.

    전이 조건:
        - ``claim.status == CLAIM_STATUS_CONFIRMED``
        - ``len(contradictions_for_claim(claim_id)) >= 1``

    Returns:
        True  — 이번 호출로 confirmed → disputed 전이.
        False — 전이 없음 (조건 불충족 / 이미 disputed / candidate / refuted).
                False 는 실패가 아니다 (no-op 도 False).

    Raises:
        KeyError: unknown claim_id.
    """
```

PR6/PR7 패턴 미러:

| | PR6 (confirm) | PR7 (refute) | PR8 (dispute) |
|---|---|---|---|
| 진입 상태 | `candidate` | `candidate` | `confirmed` |
| 결과 상태 | `confirmed` | `refuted` | `disputed` |
| Trigger | 모든 gap resolved | ≥1 contradiction | ≥1 contradiction |
| 차이 | gap 기반 | candidate + contradiction | **confirmed** + contradiction |

`refute_claim_if_ready` 와 `dispute_claim_if_ready` 는 **같은 contradiction 데이터를 본다**.
다만 status guard 가 다르다 — `candidate` 면 refute, `confirmed` 면 dispute. 둘
다 동일 시점에 trigger 될 수 없다 (status 는 한 시점에 한 값).

### 20.7 결정표

| Claim 상태 | contradictions 수 | `dispute_claim_if_ready` 결과 | 반환 |
|---|---|---|---|
| `candidate` | any | `candidate` (no-op) | `False` |
| `confirmed` | 0 | `confirmed` (no-op) | `False` |
| `confirmed` | 1+ | **`disputed`** | **`True`** |
| `disputed` | any | `disputed` (no-op) | `False` |
| `refuted` | any | `refuted` (no-op) | `False` |

다른 lifecycle API 들이 `disputed` 와 만났을 때:

| API | 입력 상태 | 결과 |
|---|---|---|
| `confirm_claim_if_ready(c)` | `disputed` | `False` (PR6 status guard 자동 동작) |
| `refute_claim_if_ready(c)` | `disputed` | `False` (PR7 status guard 자동 동작) |
| `register_contradiction(c, ev)` | `disputed` | 정상 등록 (status 무관, PR7 §19.6 일관) |

### 20.8 Idempotency

```python
engine.confirm_claim_if_ready(c)   # → True (candidate → confirmed)
engine.register_contradiction(c, e)  # → True (등록 가능, status 무관)
engine.dispute_claim_if_ready(c)   # → True (confirmed → disputed)
engine.dispute_claim_if_ready(c)   # → False (이미 disputed, no-op)
engine.get_claim(c).status          # → CLAIM_STATUS_DISPUTED (유지)
```

PR4 dedup + PR5 first-keep + PR6 confirm + PR7 refute 와 동일 정신.

### 20.9 보존 (impact 없음)

| | PR8 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` dataclass | 없음 |
| `add_claim` / `add_evidence` / `add_gap` 의미 | 없음 |
| `resolve_gaps_for_evidence` / `gap_resolution` 의미 | 없음 |
| `confirm_claim_if_ready` 의미 | 없음 (단 `disputed` 입력 시 status guard 가 False) |
| `refute_claim_if_ready` 의미 | 없음 (단 `disputed` 입력 시 status guard 가 False) |
| `register_contradiction` 의미 | 없음 (status 무관 등록 — PR7 §19.6 결정 그대로) |
| `_contradictions` 인덱스 | 없음 (PR8 이 transition 만 추가) |
| `base_confidence` / scoring | 없음 |
| `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 (Sub-decision D) |
| `fire_rule*` / `RuleStats` | 없음 |

### 20.10 Invariants (테스트로 잠금)

1. confirmed + 0 contradiction → `False`, 상태 보존
2. confirmed + 1+ contradiction → `True`, 상태 `disputed`
3. candidate + 1+ contradiction → `dispute_claim_if_ready` `False` (candidate 보존, PR7 refute 영역)
4. refuted + 1+ contradiction → `False`, refuted 보존
5. 이미 disputed → `False`, disputed 보존 (idempotent)
6. unknown `claim_id` → `KeyError` (PR1~PR7 fail-fast)
7. `confirm_claim_if_ready(disputed_claim)` → `False` (status guard)
8. `refute_claim_if_ready(disputed_claim)` → `False` (status guard)
9. `register_contradiction(disputed_claim, ev)` → 정상 등록 (status 무관)
10. `contradictions_for_claim` 결과는 disputed 전이 후에도 보존 (gap state 와 함께)
11. dispute 전이가 `base_confidence` / gap state 무변화
12. **YAML 룰이 `output.claim.status = "disputed"` 작성 시 컴파일 거부** (Sub-decision D)
13. `CLAIM_STATUS_DISPUTED` 가 `ragcore/__init__.py` 에 export 됨
14. 기존 450 tests 그대로 통과 (회귀 방지)

### 20.11 Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| `disputed → confirmed` 복구 | history / audit / 정책 필요 — PR9+ |
| `disputed → refuted` 강제 전이 | 별도 결정점 |
| `disputed → resolved` / `archived` / `closed` | lifecycle 종결 정책 — 별도 PR |
| `candidate → disputed` / `refuted → disputed` 진입 | `disputed` 의미 보호 (오직 confirmed 출신) |
| `confirmed → refuted` 직접 전이 (PR7 와 일관 금지) | history 보호, PR9+ 결정점 |
| `superseded` / `retracted` 같은 추가 상태 | PR9+ |
| `confidence` 재계산 / scoring 변경 | 별도 PR |
| `disputed_at` timestamp / status transition history | 직렬화 PR |
| Auto-dispute (`register_contradiction` 안 side effect) | 명시성 원칙 (§17.7 정신) |
| YAML 룰 output 에 `disputed` 노출 (Sub-decision D) | 20.5 참조 |

### 20.12 Position in flow

```text
PR7 까지:
  candidate + contradiction → refute_if_ready → refuted
  confirmed + contradiction → register 가능, refute_if_ready 는 no-op (의도된 보호)
                              → 이 상태가 PR8 의 트리거

PR8:
  confirmed + contradiction → dispute_if_ready → disputed
  candidate + contradiction → 여전히 PR7 refute 영역
  refuted   + contradiction → no-op (refuted 복구 금지)
  disputed  + contradiction → register 가능, lifecycle 변화 없음 (PR9+)
```

구현 단계 (39/40차) — **테스트 먼저 잠금 → 구현** 순서:
- 39차: tests (위 14개 invariant 중 1~13) — `AttributeError` + 컴파일 거부로 fail
- 40차: `CLAIM_STATUS_DISPUTED` 상수 + export + `Engine.dispute_claim_if_ready` 구현 — 39차 테스트 통과로 입증

## 21. Disputed resolution (MVP)

> 상태: 42/43/44차 (PR9-A). `disputed → confirmed` 복귀 단일 전이.
> **`disputed → refuted` / evidence 우세도 / lifecycle history 는 본 PR 범위 밖** — PR10+.

### 21.1 PR9-A 의 한 줄 정의

> **PR9-A 는 "상태를 더 늘리는 PR" 이 아니라, PR8 이 격리해둔 `disputed` 라는
> 재판정 대기 상태를 어떤 판단 규칙으로 다시 닫을 것인가를 정하는 PR 이다.**

PR8 이 confirmed 위에 격리 레이어 (`disputed`) 를 얹었다면, PR9-A 는 그 격리에
**나가는 길** 을 정의한다.

### 21.2 핵심 명제

```text
Resolving a contradiction is relationship-bound.

A contradiction resolution is valid only when the evidence is already registered
as an explicit contradiction for the given claim. Existing IDs are not sufficient.
The pair itself must be a known contradiction relation.
```

한국어:

```text
contradiction 해소는 관계 기반이다.

evidence_id 와 claim_id 가 둘 다 존재한다는 것만으로 해소 등록이 정당해지지
않는다. (claim_id, evidence_id) 쌍 자체가 이미 등록된 contradiction 관계여야
한다.
```

이 명제가 Sub-decision E (`ValueError` on mismatched pair) 의 근거.

### 21.3 lifecycle 위치

```text
PR8 까지:
  candidate
    ├─ confirmed  (PR6) ─── disputed  (PR8)
    └─ refuted    (PR7)

PR9-A 추가:
  candidate
    ├─ confirmed  (PR6) ─── disputed  (PR8)
    │                          └─ confirmed  (PR9-A) ← 모든 contradiction 해소
    └─ refuted    (PR7)
```

`disputed → confirmed` 는 lifecycle 의 **격리 해소** 경로. `disputed →
refuted` 는 evidence 우세도 / independence_class / freshness 같은 별도
정책이 필요하므로 PR10+ 로 분리.

### 21.4 저장 위치 — 분리된 두 인덱스

```python
# PR7 §19 (보존)
self._contradictions: dict[int, set[int]]            # claim_id → contradicting ev_ids

# PR9 §21 (신규)
self._resolved_contradictions: dict[int, set[int]]   # claim_id → resolved ev_ids
```

두 인덱스 분리의 의미:
- `_contradictions` 는 **등록된 사실** (변경 안 됨, audit 의미 보존)
- `_resolved_contradictions` 는 **해소된 사실** (새로 추가만, 되돌리기 없음)
- 두 set 의 차집합이 **active contradictions** — 현재 살아있는 반박 근거

PR4 `_gap_dedup_index` + `_claim_gap_refs` 처럼 두 인덱스가 같이 의미를 형성.

### 21.5 active contradiction 의 정의

```python
def active_contradictions_for_claim(self, claim_id):
    contras = self._contradictions.get(claim_id, set())
    resolved = self._resolved_contradictions.get(claim_id, set())
    return tuple(sorted(contras - resolved))
```

disputed 해소 판정의 truth-source:

```python
disputed → confirmed  ⇔  len(active_contradictions_for_claim(claim_id)) == 0
```

### 21.6 API

```python
def register_contradiction_resolution(
    self, claim_id: int, evidence_id: int,
) -> bool:
    """Register that this evidence is no longer an active contradiction for this claim.

    Returns:
        True  — 새로 resolved 로 등록됨.
        False — (claim_id, evidence_id) 가 이미 resolved 상태 (idempotent no-op).

    Raises:
        KeyError:  unknown claim_id or unknown evidence_id.
        ValueError: (claim_id, evidence_id) 가 _contradictions[claim_id] 에 등록돼
                    있지 않음 — relationship-bound 명제 (§21.2) 위반.

    Notes:
        - PR5 first-keep 정신과 일관: 한 번 resolved 면 영구. unresolved 로
          되돌리기는 PR9-A 범위 밖.
        - _contradictions 의 원본 entry 는 **삭제하지 않는다** (audit 보존).
    """

def resolved_contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]:
    """Return resolved evidence_ids for the claim.

    Returns:
        evidence_id 오름차순 tuple. 없으면 빈 tuple.

    Raises:
        KeyError: unknown claim_id.
    """

def active_contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]:
    """Return contradicting evidence_ids that are still active (not resolved).

    = ``contradictions_for_claim(c) - resolved_contradictions_for_claim(c)``

    Returns:
        evidence_id 오름차순 tuple. status 무관 (모든 status 에서 호출 가능).

    Raises:
        KeyError: unknown claim_id.
    """

def resolve_disputed_claim_if_ready(self, claim_id: int) -> bool:
    """Transition disputed → confirmed if every contradiction is resolved.

    전이 조건:
        - ``claim.status == CLAIM_STATUS_DISPUTED``
        - ``len(active_contradictions_for_claim(claim_id)) == 0``

    Returns:
        True  — 이번 호출로 disputed → confirmed 전이.
        False — 전이 없음 (status 불일치 / active contradiction 잔존 /
                이미 confirmed/candidate/refuted).

    Raises:
        KeyError: unknown claim_id.

    Note:
        API 이름이 ``resolve_disputed_claim_if_ready`` 인 이유: PR9-A 는
        disputed → confirmed 만 다루지만, 미래 PR10+ 에서 ``disputed → refuted``
        가 같은 API 의 확장으로 들어올 수 있는 자리를 남겨둔 것.
    """
```

### 21.7 PR6/PR7/PR8/PR9 API 패턴 정합

| API | 진입 status | 결과 status | Trigger |
|---|---|---|---|
| `confirm_claim_if_ready` | candidate | confirmed | 모든 gap resolved |
| `refute_claim_if_ready` | candidate | refuted | ≥1 contradiction |
| `dispute_claim_if_ready` | confirmed | disputed | ≥1 contradiction |
| **`resolve_disputed_claim_if_ready`** | **disputed** | **confirmed** | **모든 contradiction resolved** |

PR9-A 가 PR6 의 정확한 미러 (gap resolved → confirmed 와 같은 "모든 X 해소
→ confirmed" 패턴). 다만 disputed 출신.

### 21.8 결정표

**`register_contradiction_resolution`**:

| (claim, evidence) 조건 | 결과 | 반환 |
|---|---|---|
| unknown claim_id | — | `KeyError` |
| unknown evidence_id | — | `KeyError` |
| 둘 다 존재, but pair 가 contradiction 미등록 | — | **`ValueError`** (§21.2 명제 위반) |
| pair 가 contradiction 등록됨, resolved 미등록 | 추가 | `True` |
| 이미 resolved | 무변화 | `False` |

`register_contradiction_resolution` 은 **target claim 의 status 와 무관** (PR7
의 `register_contradiction` 와 동일 정신: 데이터 등록과 lifecycle 결정 분리).

**`resolve_disputed_claim_if_ready`**:

| Claim status | active contradictions 수 | 결과 status | 반환 |
|---|---|---|---|
| `disputed` | 0 | **`confirmed`** | **`True`** |
| `disputed` | 1+ | `disputed` (no-op) | `False` |
| `candidate` | any | `candidate` (no-op) | `False` |
| `confirmed` | any | `confirmed` (no-op) | `False` |
| `refuted` | any | `refuted` (no-op) | `False` |

### 21.9 Idempotency + first-keep

```python
engine.register_contradiction_resolution(c, e)  # → True  (첫 등록)
engine.register_contradiction_resolution(c, e)  # → False (이미 resolved, no-op)

engine.resolve_disputed_claim_if_ready(c)  # → True  (전이)
engine.resolve_disputed_claim_if_ready(c)  # → False (이미 confirmed, no-op)
```

PR4 dedup + PR5 first-keep + PR6/PR7/PR8 idempotent 와 일관.

### 21.10 보존 (impact 없음)

| | PR9-A 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` dataclass | 없음 |
| `add_claim` / `add_evidence` / `add_gap` 의미 | 없음 |
| `resolve_gaps_for_evidence` / `gap_resolution` 의미 | 없음 |
| `confirm_claim_if_ready` 의미 | 없음 |
| `refute_claim_if_ready` 의미 | 없음 |
| `dispute_claim_if_ready` 의미 | 없음 |
| `register_contradiction` 의미 | 없음 |
| `contradictions_for_claim` 의미 | 없음 (resolved 도 포함) |
| `_contradictions` 인덱스 | 없음 (resolved 추가가 원본 삭제 안 함) |
| `base_confidence` / scoring | 없음 |
| `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 (Sub-decision D 보존) |
| `fire_rule*` / `RuleStats` | 없음 |

### 21.11 Invariants (테스트로 잠금)

1. `register_contradiction_resolution` unknown `claim_id` → `KeyError`
2. unknown `evidence_id` → `KeyError`
3. **(claim, evidence) 가 contradiction 미등록 → `ValueError`** (Sub-decision E)
4. 같은 (claim, evidence) 두 번째 호출 → `False` (idempotent)
5. resolved 후에도 `contradictions_for_claim` 에 포함 (audit 보존)
6. `active_contradictions_for_claim` 은 resolved 제외 (차집합)
7. `resolved_contradictions_for_claim` / `active_contradictions_for_claim` asc order
8. disputed + active contradiction 1+ → `resolve_disputed_claim_if_ready` False, disputed 유지
9. **disputed + 모든 contradiction resolved → True, status=CONFIRMED**
10. candidate / confirmed / refuted 는 `resolve_disputed_claim_if_ready` 통해 변경 X
11. `resolve_disputed_claim_if_ready` unknown claim_id → `KeyError`
12. resolve 전이가 `_contradictions` / `_resolved_contradictions` / gap state /
    base_confidence 무변화 (status 만 바뀜)
13. `dispute_claim_if_ready` 는 PR8 계약 그대로 (resolved contradiction 있어도
    active 가 1+ 면 dispute 가능, active 0 이면 dispute False)
14. 기존 464 회귀 없음 (전체 통과로 입증)

### 21.12 Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| `disputed → refuted` 전이 | evidence 우세도 / independence / freshness 정책 필요 — PR10+ (같은 API 확장 가능) |
| Resolved → unresolved 되돌리기 | PR5 first-keep 정신 일관 — 별도 결정점 |
| Evidence 우세도 (priority / strength weighted) 자동 판정 | scoring 변경 별도 PR |
| `disputed → confirmed` 의 자동 trigger (resolved 등록 시 side effect) | 명시성 원칙 (§17.7 / §20.11 정신) |
| Lifecycle trace / history (resolve 이벤트 기록) | PR9-B 또는 별도 직렬화 PR |
| `disputed_resolved_at` timestamp | 직렬화 PR |
| `confirmed → refuted` / `confirmed → candidate` 강등 | 별도 결정점 |
| `_contradictions` entry 의 삭제 (resolved 시 제거) | audit 의미 보존 — 금지 |
| `superseded` / `retracted` 같은 추가 상태 | PR10+ |
| `register_contradiction_resolution` 의 status guard (disputed 만 허용?) | 데이터 등록 / lifecycle 결정 분리 (PR7 §19.6 일관) |

### 21.13 Position in flow

```text
PR8 까지:
  candidate + contradiction → refute_if_ready → refuted
  confirmed + contradiction → dispute_if_ready → disputed (격리)
  disputed                  → 격리 상태, 나가는 길 없음 (PR9 후보)

PR9-A:
  disputed + active contradiction 1+
    → resolve_disputed_claim_if_ready False (disputed 유지)
  disputed + 모든 contradiction resolved (active 0)
    → resolve_disputed_claim_if_ready True (disputed → confirmed 복귀)

  register_contradiction_resolution(c, e):
    - status 무관 호출 가능 (데이터 등록)
    - relationship-bound (§21.2): pair 가 contradiction 등록돼야 함
    - idempotent first-keep
```

구현 단계 (43/44차) — **테스트 먼저 잠금 → 구현** 순서:
- 43차: tests (위 14 invariant 중 1~13) — `AttributeError` 로 fail 하는 상태로 잠금
- 44차: `_resolved_contradictions` slot + 4 메서드 구현 — 43차 테스트 통과로 입증
