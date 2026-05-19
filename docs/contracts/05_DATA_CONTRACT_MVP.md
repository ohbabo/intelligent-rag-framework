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

## 22. Disputed refutation (MVP)

> 상태: 46/47/48차 (PR10-A). `disputed → refuted` 단일 전이.
> **freshness / RuleStats / 가중합 / 다중 evidence 종합 / scoring 변경 / lifecycle history 는 본 PR 범위 밖** — PR10-B 또는 PR11+.

### 22.1 PR10-A 의 한 줄 정의

> **PR10-A 는 PR8/PR9-A 가 격리해둔 disputed 의 부정 종결 경로를 정의한다.
> 단, "우세도" 를 똑똑하게 만들지 않고 evidence strength 단일 축으로만 시작한다.**

PR9-A 가 disputed 의 **긍정 종결** (`disputed → confirmed`) 을 잠갔다면, PR10-A
는 **부정 종결** (`disputed → refuted`) 을 잠근다. lifecycle 의 사면이 닫힌다.

### 22.2 핵심 명제 (Sub-decision F)

```text
Refutation of a disputed claim is contradiction-strength-driven only.

PR10-A does not consult freshness, rule maturity, evidence count, or weighted
aggregation. A disputed claim becomes refuted when any single active
contradiction evidence has strength >= REFUTATION_STRENGTH_THRESHOLD.
```

한국어:

```text
disputed Claim 의 refute 판정은 contradiction strength 단일 축으로만 한다.

PR10-A 는 freshness / rule maturity / evidence 개수 / 가중합 등을 보지 않는다.
active contradiction evidence 중 단 하나라도 strength 가 threshold 이상이면
refuted 로 전이한다.
```

이 단순성이 PR10-A 의 안전망. **"우세도" 를 똑똑하게 만들려는 시도가 PR10-A
의 가장 큰 위험.** 복잡한 정책은 PR11+ 로.

### 22.3 lifecycle 위치

```text
PR9-A 까지:
  candidate
    ├─ confirmed  (PR6) ─── disputed  (PR8)
    │      ↑                       │
    │      └────── PR9-A ──────────┘
    └─ refuted    (PR7)

PR10-A 추가:
  candidate
    ├─ confirmed  (PR6) ─── disputed  (PR8)
    │      ↑                       ├─ confirmed  (PR9-A)
    │      └────── PR9-A ──────────┤
    └─ refuted    (PR7)            └─ refuted    (PR10-A) ← 신규
```

`disputed → refuted` 가 lifecycle 의 부정 종결 경로. 단방향 — `refuted →
disputed` / `refuted → candidate` 같은 복구는 PR10-A 범위 밖.

### 22.4 PR7 refuted 와 PR10-A refuted — 같은 status, 다른 path

| 출처 | 진입 status | trigger | API |
|---|---|---|---|
| **PR7** | `candidate` | contradiction 등록 (개수만 봄) | `refute_claim_if_ready` |
| **PR10-A** | `disputed` | active contradiction strength >= threshold | `refute_disputed_claim_if_ready` |

둘 다 결과는 `status = CLAIM_STATUS_REFUTED` (2). 같은 상수.

- 어떤 path 로 refuted 가 됐는지 (candidate 출신 / disputed 출신) 의 구분은
  status 만으로는 알 수 없다.
- 이 구분이 필요해지면 lifecycle history (PR10-B 또는 별도 PR) 가 그 역할.
- PR10-A 는 history 영역을 건드리지 않음.

### 22.5 Strength threshold — Sub-decision G

```python
# Engine 내부 private constant
_REFUTATION_STRENGTH_THRESHOLD = 0.8
```

- **Public export 안 함** (`ragcore.__init__` 변경 없음)
- **Private constant** (`_` 접두) — 외부 의존 차단, 미래 정책 변경 자유 확보
- `ScoreValue` 의 비교는 `.value` 로 (Sub-decision F-impl):
  ```python
  if evidence.strength.value >= _REFUTATION_STRENGTH_THRESHOLD:
      ...
  ```
  `ScoreValue` 가 `__ge__` 미정의 (`order=False` dataclass) 라 `.value` 접근이
  유일한 안전한 방법. PR1 의 `ScoreValue` 시그니처를 건드리지 않는다.

| 옵션 | 채택 | 이유 |
|---|---|---|
| Public constant | ✗ | 미래 정책 변경 자유 확보 |
| Config 주입 | ✗ | PR10-A 단순성 보호 |
| Hardcode private | ✓ | MVP 안전 + 변경 시 단일 위치 |
| `ScoreValue.__ge__` 추가 | ✗ | PR1 시그니처 변경 회피 |

threshold 값 0.8 의 근거: "거의 확실한 반박" 의 보수적 기준. PR11+ 에서
freshness/aggregation 들어오면 자연스럽게 조정 또는 대체.

### 22.6 API

```python
def refute_disputed_claim_if_ready(self, claim_id: int) -> bool:
    """Transition disputed → refuted if any active contradiction is strong enough.

    전이 조건 (§22.7):
        - ``claim.status == CLAIM_STATUS_DISPUTED``
        - ``len(active_contradictions_for_claim(claim_id)) >= 1``
        - active contradiction 중 **단 하나라도** evidence.strength.value >=
          ``_REFUTATION_STRENGTH_THRESHOLD`` (= 0.8)

    Returns:
        True  — 이번 호출로 disputed → refuted 전이.
        False — 전이 없음 (status 불일치 / active 없음 / strength 부족 / no-op).

    Raises:
        KeyError: unknown claim_id.

    Notes:
        - PR9-A 의 ``resolve_disputed_claim_if_ready`` 와는 **별도 API**.
          PR9-A 는 "모든 contradiction 해소" 가 trigger, PR10-A 는 "active 중
          하나라도 강함" 이 trigger — 의미가 비대칭이라 sibling API 가 깨끗.
        - Resolved contradiction 은 refute 판정에서 **제외** (active 만 본다).
          §22.7 결정표 참조.
    """
```

### 22.7 결정표

| Claim status | active 수 | active 중 strength >= 0.8 있음? | 결과 status | 반환 |
|---|---|---|---|---|
| `disputed` | 0 | — | `disputed` (no-op) | `False` |
| `disputed` | 1+ | yes | **`refuted`** | **`True`** |
| `disputed` | 1+ | no (모두 < 0.8) | `disputed` (유지) | `False` |
| `candidate` | any | any | `candidate` | `False` |
| `confirmed` | any | any | `confirmed` | `False` |
| `refuted` | any | any | `refuted` (no-op) | `False` |

**Resolved contradiction 은 판정 입력에서 제외**:

```python
active = contradictions_for_claim(c) - resolved_contradictions_for_claim(c)
# refute 판정은 이 active 의 strength 만 본다.
# resolved contradiction 의 strength 가 0.95 라도 무관 (이미 해소됨).
```

이게 PR9-A 의 차집합 의미와 자연스럽게 정합. resolved 가 강하다는 이유로
refuted 가 되면 PR9-A 의 "해소" 의미가 무너진다.

### 22.8 PR7/PR9-A/PR10-A relationship

PR9-A 의 `resolve_disputed_claim_if_ready` 와 PR10-A 의 `refute_disputed_claim_if_ready`
는 **상호 배타적인 trigger** 를 가진다:

```text
resolve trigger: len(active) == 0   (모든 contradiction 해소)
refute  trigger: any(strength >= 0.8 in active)
```

두 trigger 가 동시 만족할 수 없다 (active 0 이면 resolve, active 1+ 이면
refute 후보). 호출 순서에 의존하지 않음.

PR7 의 `refute_claim_if_ready` (candidate origin) 는 PR10-A 와 status guard
만 다르다 (`CANDIDATE` vs `DISPUTED`). 한 시점에 한 status 라서 동시 trigger
불가.

### 22.9 Idempotency

```python
engine.refute_disputed_claim_if_ready(c)  # → True  (disputed → refuted)
engine.refute_disputed_claim_if_ready(c)  # → False (이미 refuted, no-op)
engine.get_claim(c).status                 # → CLAIM_STATUS_REFUTED 유지
```

PR4 dedup + PR5 first-keep + PR6/PR7/PR8/PR9 idempotent 와 일관.

### 22.10 보존 (impact 없음)

| | PR10-A 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` / `ScoreValue` dataclass | 없음 |
| `add_claim` / `add_evidence` / `add_gap` 의미 | 없음 |
| `resolve_gaps_for_evidence` / `gap_resolution` 의미 | 없음 |
| `confirm_claim_if_ready` 의미 | 없음 |
| `refute_claim_if_ready` 의미 | 없음 (PR7 candidate origin 그대로) |
| `dispute_claim_if_ready` 의미 | 없음 |
| `resolve_disputed_claim_if_ready` 의미 | 없음 (PR9-A 그대로) |
| `register_contradiction` / `register_contradiction_resolution` | 없음 |
| `contradictions_for_claim` / `resolved_contradictions_for_claim` / `active_contradictions_for_claim` | 없음 |
| `_contradictions` / `_resolved_contradictions` 인덱스 | 없음 (PR10-A 가 transition 만 추가) |
| `base_confidence` / scoring | 없음 |
| `CLAIM_STATUS_*` 상수 | 없음 (REFUTED 재사용) |
| `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 (Sub-decision D 정합) |
| `fire_rule*` / `RuleStats` | 없음 |
| public exports | 없음 (threshold private) |

### 22.11 Invariants (테스트로 잠금)

1. `refute_disputed_claim_if_ready` unknown claim_id → `KeyError`
2. candidate / confirmed / refuted 는 transition 안 함 (status guard 3 cases)
3. disputed + active 0 → `False`, disputed 유지
4. **disputed + active 1+ 모두 strength < 0.8 → `False`, disputed 유지** (Sub-decision F)
5. **disputed + active 중 단 하나 이상 strength >= 0.8 → `True`, status=REFUTED ★** (PR10-A 핵심)
6. **Threshold 경계 정확히 0.8 → refute** (`>=` 비교)
7. **Threshold 직하 0.799999 → refute 안 함** (`>=` 비교)
8. **Resolved contradiction 의 strength 가 0.95 라도 refute 안 함** (active 만 본다) ★
9. refuted 재호출 idempotent (no-op False, status 유지)
10. refute 전이가 gap state / contradictions / resolved / base_confidence 무변화
11. PR9-A `resolve_disputed_claim_if_ready` 와 동시 trigger 불가 — active 0 이면
    refute False (active 없음 가드), active 1+ 이면 resolve False (active 잔존
    가드). 호출 순서 무관.
12. **PR7 `refute_claim_if_ready` 의 의미 무변화** — candidate 만, contradiction
    개수만 (strength 무관). PR10-A 의 threshold 정책이 PR7 영역 침범 안 함.
13. `_REFUTATION_STRENGTH_THRESHOLD` 가 public export 안 됨 (Sub-decision G)
14. 기존 482 회귀 없음 (전체 통과로 입증)

### 22.12 Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| Freshness / timestamp 기반 우세도 | timestamp 정의 필요 — PR11+ |
| RuleStats 기반 우세도 | rule maturity 의 lifecycle 의미 결정 — PR11+ |
| 다중 evidence 가중합 / average / max-of-N | "우세도" 종합 정책 결정 — PR11+ |
| Threshold 의 public export / config 주입 | 미래 정책 자유 확보 |
| `disputed → candidate` 강등 | 별도 결정점 |
| `refuted → 어떤 상태` 복구 | 별도 결정점 |
| LLM / 의미 추론으로 우세도 판정 | core 밖 |
| `confidence` (`base_confidence` / `effective`) 재계산 | scoring 변경 별도 PR |
| Lifecycle history / `refuted_at` timestamp | PR10-B 또는 직렬화 PR |
| Auto-refute (resolve/register side effect) | 명시성 원칙 (§17.7 / §20.11 정신) |
| `superseded` / `retracted` 추가 상태 | PR11+ |
| `ScoreValue` 비교 메서드 (`__ge__` 등) 추가 | PR1 시그니처 변경 회피 |
| PR7 candidate-origin refuted 와 PR10 disputed-origin refuted 의 구분 | lifecycle history 영역 |

### 22.13 Position in flow

```text
PR9-A 까지:
  disputed + active 1+ → resolve_disputed_claim_if_ready False (active 잔존)
  disputed + active 0  → resolve_disputed_claim_if_ready True (confirmed 복귀)

PR10-A:
  disputed + active 0
    → resolve True (PR9-A), refute False (active 없음 가드)
  disputed + active 1+ + max(strength) >= 0.8
    → resolve False (active 잔존), refute True (PR10-A: REFUTED 전이)
  disputed + active 1+ + max(strength) < 0.8
    → resolve False, refute False — disputed 유지 (재판정 대기)
```

구현 단계 (47/48차) — **테스트 먼저 잠금 → 구현** 순서:
- 47차: tests (위 13 invariant) — `AttributeError` 로 fail 하는 상태로 잠금
- 48차: `_REFUTATION_STRENGTH_THRESHOLD` 상수 + `refute_disputed_claim_if_ready` 구현 — 47차 테스트 통과로 입증

## 23. Claim lifecycle history (MVP)

> 상태: 50/51/52차 (PR10-B). lifecycle status transition 의 engine-local
> 기록.
> **wall-clock timestamp / persistence / freshness / 자동 판단 / 직렬화 /
> rollback / history 기반 결정은 본 PR 범위 밖** — 별도 PR.

### 23.1 PR10-B 의 한 줄 정의

> **PR10-B 는 PR6~PR10-A 가 잠근 5 status transition 들이 "어느 path 로 어느
> 상태에 도달했는가" 의 audit 기록을 남기는 PR 이다. 판단 근거가 아니라
> 추적 기록.**

PR10-A 까지는 "지금 어느 상태인가" 만 답할 수 있었다. PR10-B 이후는 "어떻게
이 상태가 됐는가" 를 같은 engine 안에서 답할 수 있다.

### 23.2 핵심 명제

```text
Lifecycle history records status transitions, not claim creation.

A lifecycle event exists only when an existing claim changes from one status
to another. The event records engine-local order, not wall-clock time or
freshness.
```

한국어:

```text
Lifecycle history 는 status transition 만 기록한다. claim 생성은 transition
이 아니므로 기록되지 않는다.

이벤트는 engine-local 순서만 표현한다. 시간 차이 / freshness 는 PR10-B 가
표현하지 않는다.
```

### 23.3 Sub-decision H — Sequence id, not timestamp

```python
self._lifecycle_seq: int = 0  # per-engine monotonic counter
```

- **timestamp 안 씀** — wall-clock 의존성 없음, 결정성 100%
- **per-engine monotonic** — 서로 다른 claim 사이에서도 "어느 전이가 먼저
  일어났는가" 비교 가능
- **순서만 표현** — 시간 간격 / freshness 의미 없음
- **외부 clock 의존 없음** — 테스트 안정성 + 향후 직렬화 자유

이 결정이 PR10-A 의 timestamp / freshness OOS 결정과 정합. freshness 정책은
PR11+ 에서 별도로 도입 가능.

### 23.4 Sub-decision I — Private string literal transition labels

```python
@dataclass(frozen=True)
class ClaimLifecycleEvent:
    seq: int
    claim_id: int
    from_status: int
    to_status: int
    transition: str   # audit label, not public constant
```

5 transition string 값:

| API | `transition` 값 |
|---|---|
| `confirm_claim_if_ready` (PR6) | `"confirm_if_ready"` |
| `refute_claim_if_ready` (PR7) | `"refute_if_ready"` |
| `dispute_claim_if_ready` (PR8) | `"dispute_if_ready"` |
| `resolve_disputed_claim_if_ready` (PR9-A) | `"resolve_disputed_if_ready"` |
| `refute_disputed_claim_if_ready` (PR10-A) | `"refute_disputed_if_ready"` |

| 옵션 | 채택 | 이유 |
|---|---|---|
| Public string constants (`TRANSITION_*`) | ✗ | 외부 의존 발생, 변경 자유 손실 |
| Public string literals (계약상 노출만) | ✗ | 같은 문제 |
| **Private literal (audit label)** | ✓ | implementation detail, 미래 변경 자유 |

caller 비교 방식:

```python
event.transition == "confirm_if_ready"  # literal 비교 OK
```

PR1 의 mapping table 패턴 (string→uint16 packed) 영역이 아님. lifecycle event
는 audit data 라 packed 안 됨.

### 23.5 Sub-decision J — Record only on actual transition

```text
True 반환 (status 변경 발생) → history append
False (no-op) → 기록 안 함
```

5 lifecycle API 가 `True` 를 반환할 때만 `_record_claim_lifecycle_transition`
호출. 의미상 transition 자체가 일어나지 않으면 history 도 없음.

이 결정의 결과:
- 기존 API 시그니처 무변경 — caller 코드 무영향
- side effect 만으로 기록 — PR10-B 가 PR6~PR10-A 와 100% 호환
- false call 의 횟수는 추적 안 됨 (별도 audit 영역)

### 23.6 Sub-decision K — Claim 생성은 transition 아님

`add_claim` / `fire_rule` 통한 claim 생성은 history 에 기록되지 않음.

이유:
- "transition" 정의 = `from_status → to_status`. 생성은 `from_status` 없음.
- 모든 Claim 은 candidate 로 시작 — "candidate 진입" 은 새 정보 0.
- Claim 의 첫 history 이벤트는 **첫 status 변경 시점** (예: `confirm_if_ready`).

미래에 "claim 생성도 audit" 요구가 있으면 별도 PR (PR3 firing trace 와 통합
가능).

### 23.7 Sub-decision L — Per-engine single counter

```python
self._lifecycle_seq: int = 0  # not per-claim
```

같은 engine 안의 모든 claim 의 transition 순서를 비교 가능. 서로 다른
claim 의 전이도 seq 으로 정렬됨.

per-claim counter 옵션을 거부한 이유:
- 같은 engine 안에서 "어느 claim 의 전이가 먼저 일어났는가" 비교 불가
- 미래에 cross-claim 분석 (예: "claim A 가 confirmed 된 후 claim B 가 disputed
  된 적이 있는가") 의 기반 손실

### 23.8 데이터 구조

```python
# ragcore/types.py
@dataclass(frozen=True)
class ClaimLifecycleEvent:
    seq: int          # per-engine monotonic
    claim_id: int
    from_status: int  # CLAIM_STATUS_*
    to_status: int    # CLAIM_STATUS_*
    transition: str   # private audit label
```

Engine 내부:

```python
self._lifecycle_seq: int = 0
self._claim_lifecycle_events: dict[int, list[ClaimLifecycleEvent]] = {}
```

### 23.9 API

```python
def claim_lifecycle_history(self, claim_id: int) -> tuple[ClaimLifecycleEvent, ...]:
    """Return lifecycle events for the claim in insertion order.

    Returns:
        ClaimLifecycleEvent 들의 tuple, 발생 순서 (= seq 오름차순).
        Status 변경이 한 번도 없었으면 빈 tuple.

    Raises:
        KeyError: unknown claim_id.

    Note:
        seq 는 engine-local monotonic. 서로 다른 claim 의 history 를 합쳐서
        정렬해도 의미가 있다 (cross-claim 순서 표현).
    """
```

Engine 내부 helper (public 아님):

```python
def _record_claim_lifecycle_transition(
    self,
    claim_id: int,
    from_status: int,
    to_status: int,
    transition: str,
) -> None:
    """Append a lifecycle event. Called by 5 transition APIs on actual transition.

    이 helper 는 public 노출 안 됨 — caller 가 직접 history 를 mutate 할 수 없음
    (§23 OOS).
    """
    self._lifecycle_seq += 1
    event = ClaimLifecycleEvent(
        seq=self._lifecycle_seq,
        claim_id=claim_id,
        from_status=from_status,
        to_status=to_status,
        transition=transition,
    )
    self._claim_lifecycle_events.setdefault(claim_id, []).append(event)
```

### 23.10 PR6~PR10-A 5 API 의 변경 지점

각 API 의 `True` 반환 직전에 `_record_claim_lifecycle_transition` 호출:

```python
# 예: confirm_claim_if_ready (PR6)
self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_CONFIRMED)
self._record_claim_lifecycle_transition(
    claim_id, claim.status, CLAIM_STATUS_CONFIRMED, "confirm_if_ready",
)
return True
```

5 API 의 변경 패턴 동일. **시그니처 무변경** — caller 코드 무영향.

### 23.11 결정표

| 시나리오 | history 기록? |
|---|---|
| `confirm_claim_if_ready` returns True (전이 발생) | **기록** |
| `confirm_claim_if_ready` returns False (no-op) | 기록 안 함 |
| `refute_claim_if_ready` returns True | **기록** |
| `dispute_claim_if_ready` returns True | **기록** |
| `resolve_disputed_claim_if_ready` returns True | **기록** |
| `refute_disputed_claim_if_ready` returns True | **기록** |
| 어느 API 든 returns False | 기록 안 함 |
| `add_claim` 호출 | 기록 안 함 (생성) |
| `fire_rule` 호출 (Claim 생성) | 기록 안 함 (생성) |
| `register_contradiction` / `register_contradiction_resolution` | 기록 안 함 (transition 아님) |
| `add_evidence` / `resolve_gaps_for_evidence` | 기록 안 함 |
| `claim_lifecycle_history` 호출 자체 | 기록 안 함 (read-only) |

### 23.12 보존 (impact 없음)

| | PR10-B 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` / `ScoreValue` dataclass | 없음 |
| `Entity` / `Observation` / `RuleDefinition` / `RuleStats` | 없음 |
| 5 lifecycle API 의 **시그니처** | 없음 |
| 5 lifecycle API 의 **return semantics** | 없음 |
| `add_claim` / `add_evidence` / `add_gap` 의미 | 없음 |
| `register_contradiction` / `register_contradiction_resolution` 의미 | 없음 |
| `_contradictions` / `_resolved_contradictions` / `_gap_resolutions` 인덱스 | 없음 |
| `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 (audit, 새 status 아님) |
| `CLAIM_STATUS_*` 상수 | 없음 (재사용) |
| `fire_rule*` / `RuleStats` / `compute_effective_confidence` | 없음 |
| `base_confidence` / scoring | 없음 |
| 외부 dependency | 없음 (외부 clock 의존 안 함, sequence id 만) |

5 lifecycle API 는 **side effect 추가만**. caller 가 보기에 동작 변화 없음.

### 23.13 Invariants (테스트로 잠금)

1. `claim_lifecycle_history` unknown claim_id → `KeyError`
2. `add_claim` 직후 history 는 빈 tuple
3. `confirm_claim_if_ready` 성공 → history 에 event 1, `from=CANDIDATE`, `to=CONFIRMED`, `transition="confirm_if_ready"`
4. `refute_claim_if_ready` 성공 → event, `transition="refute_if_ready"`
5. `dispute_claim_if_ready` 성공 → event, `transition="dispute_if_ready"`
6. `resolve_disputed_claim_if_ready` 성공 → event, `transition="resolve_disputed_if_ready"`
7. `refute_disputed_claim_if_ready` 성공 → event, `transition="refute_disputed_if_ready"`
8. 5 API 중 **`False` 반환 시 history 무변화** (no-op 기록 안 함)
9. `add_claim` / `fire_rule` 단독 호출은 history 무변화
10. `register_contradiction` / `add_evidence` / `resolve_gaps_for_evidence`
    단독 호출은 history 무변화
11. 여러 transition 발생 시 seq 가 strictly increasing
12. **`seq` 는 per-engine monotonic** — 다른 claim 의 transition 도 같은
    counter 공유 (claim_a seq=1, claim_b seq=2 같은 패턴)
13. 같은 claim 의 history 는 발생 순서대로 (insertion order)
14. `from_status` / `to_status` 가 실제 전이와 일치
15. 다중 transition (예: candidate → confirmed → disputed → refuted) full
    path 기록
16. 기존 500 회귀 없음 (전체 통과로 입증)

### 23.14 Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| Wall-clock timestamp | freshness 정책과 같이 갈 결정 — PR11+ |
| Persistence / 직렬화 | 별도 PR (전체 engine state 직렬화 결정과 같이) |
| Event sourcing / undo / rollback | lifecycle 의 단방향성 보장 — 별도 PR |
| Freshness scoring (event 시간 거리 기반) | timestamp 없음 |
| History 기반 자동 lifecycle 결정 (예: 최근 5 번 disputed → refute) | side effect 의 side effect — 명시성 위반 |
| Trace 의 public mutation API | caller 직접 mutate 금지 (audit 무결성) |
| Pretty-printer / 시각화 | 별도 도구 PR |
| 기존 5 API 의 signature 변경 | 호환성 (Sub-decision J 정신) |
| `add_claim` / `fire_rule` / 비-transition API 의 audit | Sub-decision K, 별도 PR |
| Trace 의 삭제 / archive | PR9-A audit 보존 정신 |
| Cross-engine seq 비교 | per-engine monotonic — 의미 없음 |
| Public transition constants (`TRANSITION_*`) | Sub-decision I |

### 23.15 Position in flow

```text
PR10-A 까지:
  status 변경 5 종 → 단순히 status 만 바뀜
  caller 는 현재 status 만 볼 수 있음 (어떻게 도달했는지 모름)

PR10-B:
  status 변경 5 종 → status 바뀜 + lifecycle event append
  claim_lifecycle_history(c) → tuple[ClaimLifecycleEvent, ...]
    각 event: seq / claim_id / from_status / to_status / transition

  예시:
    add_claim → status=CANDIDATE, history=[]
    confirm_claim_if_ready → True, history=[event(seq=1, CAND→CONF)]
    dispute_claim_if_ready  → True, history=[..., event(seq=2, CONF→DISP)]
    register_contradiction_resolution → bool (history 무변화 — transition 아님)
    refute_disputed_claim_if_ready  → True, history=[..., event(seq=3, DISP→REF)]
```

구현 단계 (51/52차) — **테스트 먼저 잠금 → 구현** 순서:
- 51차: tests (위 16 invariant) — `AttributeError` + `from_status` 가 잘못된 값 등으로 fail
- 52차: `ClaimLifecycleEvent` dataclass + `_lifecycle_seq` slot + `_claim_lifecycle_events` slot + `_record_claim_lifecycle_transition` helper + 5 API 변경 + `claim_lifecycle_history` 구현 — 51차 테스트 통과로 입증

## 24. Effective confidence (MVP — status-only multiplier)

> 상태: 54/55/56차 (PR11-D). PR1 의 `compute_effective_confidence` stub 첫
> 활성화.
> **gap / contradiction / freshness / RuleStats / lifecycle history 기반
> modifier 는 본 PR 범위 밖** — PR11-A 또는 PR12+.

### 24.1 PR11-D 의 한 줄 정의

> **PR11-D 는 "정교한 신뢰도 계산기" 가 아니라, lifecycle status 가
> effective_confidence 에 처음 반영되는 최소 연결 PR 이다.**

PR1 의 prior/base/effective confidence 3 슬롯 분리가 처음으로 의미를 갖는다.
이전까지 `effective` 슬롯은 stub 으로 비어 있었음.

### 24.2 핵심 명제

```text
Effective confidence is status-adjusted, not evidence-recomputed.

PR11-D does not re-evaluate evidence, gaps, contradictions, freshness, or
rule maturity. It only applies the current claim lifecycle status as a
bounded multiplier over base confidence.
```

한국어:

```text
Effective confidence 는 status 로 조정될 뿐, evidence 를 재계산하지 않는다.

PR11-D 는 evidence / gap / contradiction / freshness / rule maturity 를 다시
평가하지 않는다. base_confidence 위에 현재 lifecycle status 를 bounded
multiplier 로 적용할 뿐이다.
```

### 24.3 공식 (§24 의 본체)

```python
effective_confidence(claim) = base_confidence × status_modifier(claim.status)
```

`status_modifier` 표:

| status | modifier | 의미 |
|---|---|---|
| `CLAIM_STATUS_CANDIDATE` (0) | `1.0` | 그대로 — 아직 모름 |
| `CLAIM_STATUS_CONFIRMED` (1) | `1.0` | 그대로 — boost 안 함 |
| `CLAIM_STATUS_REFUTED` (2) | `0.0` | 확정 부정 |
| `CLAIM_STATUS_DISPUTED` (3) | `0.5` | 감쇠 — 재판정 대기 |

### 24.4 Sub-decision M — Modifier 의 input

modifier 는 **`claim.status` 만 본다**. 다음 항목은 PR11-D 범위 **밖**:

- `gaps_for_claim(c)` / `gap_resolution(g)`
- `contradictions_for_claim(c)` / `active_contradictions_for_claim(c)`
- `resolved_contradictions_for_claim(c)`
- `claim_lifecycle_history(c)` (PR10-B seq / transition labels)
- `evidence.strength` / 가중합
- `RuleStats` (observed_precision / false_positive_rate)
- `rule_version` / `rule_maturity` / freshness

| 옵션 | 채택 | 이유 |
|---|---|---|
| (i) status only | ✓ | PR10-A 단순성 정신 일관, 다음 PR 자연 확장 |
| (ii) status + gap binary | ✗ | gap 페널티 값 결정 부담 |
| (iii) status + gap + contradiction | ✗ | 결정 폭발 |
| Config-driven | ✗ | PR10-A 정신 위반 |

(ii) / (iii) 같은 확장은 PR11-A (freshness 우세도) 또는 별도 PR 에서.

### 24.5 Sub-decision N — Modifier range [0.0, 1.0]

```text
modifier ∈ [0.0, 1.0]
→ effective_confidence ≤ base_confidence  (보장)
→ no boost  (confirmed 가 base 를 초과하지 않음)
```

이유:
- "confirmed = 근거 충족" 이지 "과신해도 됨" 이 아님
- PR1 `ScoreValue` 의 [0.0, 1.0] 범위 강제와 정합 — `ScoreValue(value)` 에서
  `value > 1.0` 이면 `ValueError`. modifier 가 1.0 초과면 base 가 1.0 인
  케이스에서 effective 가 invariant 위반.
- 미래에 "boost" 가 필요하면 별도 PR 결정점 (확신도 모델 변경)

### 24.6 결정성 (Determinism)

```text
같은 (claim.base_confidence, claim.status) → 항상 같은 effective_confidence
```

PR11-D 는:
- wall-clock 안 봄
- gap / contradiction / history 안 봄
- `_lifecycle_seq` 안 봄
- random / external state 안 봄

테스트 재현 100% 보장.

### 24.7 API — 기존 stub 의 의미 채우기

```python
def compute_effective_confidence(self, claim_id: int) -> ScoreValue:
    """Compute effective confidence as base × status_modifier.

    PR11-D §24 — status-only multiplier MVP.

    Returns:
        ScoreValue (= base_confidence × status_modifier(claim.status)).

    Raises:
        KeyError: unknown claim_id.
    """
```

PR1 stub 의 시그니처와 KeyError 동작은 **그대로 유지**. 본문만 status_modifier
적용으로 채움.

### 24.8 Status modifier 값들 — 결정 잠금

```python
# Engine 내부 private constants (PR10-A _REFUTATION_STRENGTH_THRESHOLD 정신)
_STATUS_MODIFIER_CANDIDATE = 1.0
_STATUS_MODIFIER_CONFIRMED = 1.0
_STATUS_MODIFIER_DISPUTED  = 0.5
_STATUS_MODIFIER_REFUTED   = 0.0
```

값 결정 근거:

- **candidate = 1.0**: 아직 판단 안 됨. base_confidence 가 룰 firing 시점의
  스냅샷이므로 그대로 노출.
- **confirmed = 1.0**: 근거가 채워졌지만 boost 는 안 함 (Sub-decision N).
  PR10-A 의 보수성 정신.
- **disputed = 0.5**: confirmed 였다가 contradiction 으로 재검토. base 의
  절반으로 명확히 감쇠해 caller 가 "주의" 신호로 인식 가능.
- **refuted = 0.0**: 확정 부정. evidence 가 명시적으로 반박 (PR7) 또는
  disputed 후 strong contradiction (PR10-A). effective_confidence 0 으로
  완전 차단.

값 자체는 **engine 내부 private**:
- public export 안 함 (PR10-A `_REFUTATION_STRENGTH_THRESHOLD` 정신)
- 미래 정책 변경 자유 확보 (PR11-A freshness 가 들어오면 modifier 분해 가능)
- caller 가 외부 의존 못 하게 차단

### 24.9 보존 (impact 없음)

| | PR11-D 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` / `ScoreValue` dataclass | 없음 |
| `Claim.base_confidence` 값 | 없음 (수정 안 함, 읽기만) |
| `ClaimLifecycleEvent` / lifecycle history | 없음 |
| `add_claim` / `add_evidence` / `add_gap` 의미 | 없음 |
| `register_contradiction` / `register_contradiction_resolution` | 없음 |
| 5 lifecycle API (confirm/refute/dispute/resolve_disputed/refute_disputed) | 없음 |
| `_contradictions` / `_resolved_contradictions` / `_gap_resolutions` 인덱스 | 없음 |
| `_lifecycle_seq` / `_claim_lifecycle_events` | 없음 (PR10-B audit) |
| `_REFUTATION_STRENGTH_THRESHOLD` (PR10-A) | 없음 |
| `CLAIM_STATUS_*` 상수 / `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 |
| `fire_rule*` / `RuleStats` / `compute_effective_confidence` 시그니처 | 없음 (본문만 변경) |
| public exports | 없음 (status_modifier 상수 private) |
| 외부 dependency | 없음 |

PR11-D 는 **stub 의 본문만 교체**. caller 코드 변화 0.

### 24.10 Invariants (테스트로 잠금)

1. `compute_effective_confidence` unknown claim_id → `KeyError`
2. candidate Claim → `effective == base_confidence` (modifier 1.0)
3. confirmed Claim → `effective == base_confidence` (modifier 1.0)
4. **refuted Claim → `effective.value == 0.0`** ★ (확정 부정)
5. **disputed Claim → `effective.value == base_confidence.value × 0.5`** ★ (감쇠)
6. **return type is `ScoreValue`** (PR1 정합)
7. 결정성: 같은 (base, status) 두 번 호출 → 같은 결과
8. effective ≤ base (Sub-decision N — boost 없음)
9. base = 0.5 + candidate → effective = 0.5
10. base = 0.5 + confirmed → effective = 0.5
11. base = 0.8 + disputed → effective = 0.4
12. base = 1.0 + refuted → effective = 0.0
13. base = 0.0 + any status → effective = 0.0 (0 × anything)
14. compute 호출이 gap state / contradictions / history / lifecycle_seq /
    base_confidence 무변화 (read-only)
15. lifecycle transition 전후로 effective 값이 status 에 따라 변함
    (예: candidate effective 0.7 → confirm → 0.7 → dispute → 0.35 → refute → 0.0)
16. status modifier 상수 (`_STATUS_MODIFIER_*`) 가 public export 안 됨
17. 기존 517 회귀 없음 (전체 통과로 입증)

### 24.11 Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| Gap 기반 modifier (unresolved gap 페널티) | PR11 후속 또는 PR12+ |
| Contradiction 기반 modifier (active strength 가중) | PR11-A 또는 PR12+ |
| Freshness 기반 modifier (PR10-B seq 활용) | PR11-A 자연 자리 |
| RuleStats 기반 modifier (observed_precision / false_positive_rate) | scoring 정교화 별도 PR |
| Lifecycle history 기반 modifier (transition 횟수 / path 가중) | history 활용 별도 PR |
| Confidence boost (modifier > 1.0) | 확신도 모델 변경 — 별도 결정점 |
| Caller-driven modifier 함수 (config injection) | PR10-A 정신 위반 |
| LLM / semantic 기반 confidence | core 밖 |
| Mutable confidence (setter 도입) | immutability 보존 |
| Public `STATUS_MODIFIER_*` constants | Sub-decision M-impl |
| Effective confidence 의 직렬화 / persistence | 별도 PR |
| `base_confidence` 값 변경 (caller setter) | base 는 firing 시점 스냅샷 — 변경 금지 |
| 결과의 caching / memoization | 결정성 보장이므로 호출자가 자체 캐시 가능 |

### 24.12 Position in flow

```text
PR10-B 까지:
  compute_effective_confidence(c) → base_confidence 그대로 (PR1 stub)
  → status 의 의미가 scoring 에 반영 안 됨

PR11-D:
  compute_effective_confidence(c)
    → base_confidence × status_modifier(claim.status)
    → candidate / confirmed: base 그대로
    → disputed: base × 0.5
    → refuted: 0.0

  caller 가 처음으로:
    "이 claim 의 현재 status 가 신뢰도에 어떻게 반영되는가?"
    질문에 의미 있는 답을 받을 수 있음.
```

구현 단계 (55/56차) — **테스트 먼저 잠금 → 구현** 순서:
- 55차: tests (위 17 invariant) — 기존 stub 동작 (base 그대로) 으로 disputed/refuted 테스트 fail
- 56차: `_STATUS_MODIFIER_*` 4 private constants + `compute_effective_confidence` 본문 교체 — 55차 테스트 통과로 입증

## 25. Evidence freshness query (MVP — query only)

> 상태: 58/59/60차 (PR11-A). evidence 의 등록 순서를 freshness 로 노출.
> **PR10-A refute 정책 / PR11-D effective scoring / 새 lifecycle 전이 / 새
> 상태 / 새 dataclass 모두 본 PR 범위 밖** — PR11-B 또는 PR12+.

### 25.1 PR11-A 의 한 줄 정의

> **PR11-A 는 freshness 를 lifecycle 결정에 도입하는 PR 이 아니라, freshness
> 라는 새 관찰 축을 read-only query 로 처음 노출하는 PR 이다.**

PR10-B 가 lifecycle transition 의 audit 축을 query 로 노출했듯, PR11-A 는
evidence 의 freshness 축을 query 로 노출. engine 동작 변경 0.

### 25.2 핵심 명제

```text
Freshness is evidence-registration order, not wall-clock time.

PR11-A exposes freshness as read-only query state.
It does not change lifecycle transitions, refutation policy, or effective
confidence scoring.
```

한국어:

```text
Freshness 는 evidence 의 등록 순서이며, wall-clock 시간이 아니다.

PR11-A 는 freshness 를 read-only query 로만 노출한다. lifecycle 전이 /
refute 정책 / effective confidence scoring 모두 변경하지 않는다.
```

### 25.3 Sub-decision A — Freshness = evidence.id

```python
evidence_freshness(evidence_id) -> int
# = evidence.id  (PR1 의 _next_id["evidence"] 카운터 기반 등록 순서)
```

| 후보 | 채택 | 이유 |
|---|---|---|
| (a) `evidence.id` | ✓ | PR1 의 `_next_id` 카운터가 이미 등록 순서 표현 |
| (b) `_lifecycle_seq` (PR10-B) | ✗ | lifecycle transition seq 이지 evidence 등록 seq 아님 |
| (c) 새 freshness counter | ✗ | 불필요한 carrier 추가 |
| (d) wall-clock timestamp | ✗ | PR10-A / PR10-B 의 "외부 clock 안 봄" 정신 위반 |

값 의미:
- `evidence.id` 가 클수록 더 최근 등록
- 같은 engine 안에서만 의미 (cross-engine 비교 무의미, PR10-B Sub-decision L 정신)

### 25.4 Sub-decision B — Query only (engine 동작 변경 0)

PR11-A 는 다음을 **건드리지 않는다**:

| 영역 | PR11-A 영향 |
|---|---|
| 5 lifecycle API (`confirm_*` / `refute_*` / `dispute_*` / `resolve_disputed_*` / `refute_disputed_*`) | 없음 |
| `refute_disputed_claim_if_ready` 의 threshold 정책 (PR10-A) | 없음 |
| `compute_effective_confidence` 의 status_modifier (PR11-D) | 없음 |
| `register_contradiction` / `register_contradiction_resolution` | 없음 |
| `_record_claim_lifecycle_transition` (PR10-B) | 없음 |
| `_contradictions` / `_resolved_contradictions` 인덱스 | 없음 |
| `_lifecycle_seq` / `_claim_lifecycle_events` | 없음 |

PR11-A 가 추가하는 것: **2 read-only query API 만**. 호출 결과는 외부 view —
caller 가 그것으로 무엇을 하든 engine 상태 영향 없음.

### 25.5 Sub-decision C — C-pair API

```python
def evidence_freshness(self, evidence_id: int) -> int:
    """Return the freshness signal of the evidence.

    PR11-A §25.3 — freshness = evidence.id (등록 순서, 큰 값일수록 최근).

    Returns:
        evidence.id (즉 PR1 의 _next_id 카운터 기반 등록 순서).

    Raises:
        KeyError: unknown evidence_id.
    """

def active_contradictions_by_freshness(
    self, claim_id: int,
) -> tuple[int, ...]:
    """Return active contradicting evidence_ids ordered by freshness (most recent first).

    PR9-A active_contradictions_for_claim 과 **같은 set** 이지만 정렬 키가 다름:
        active_contradictions_for_claim         → evidence_id asc
        active_contradictions_by_freshness      → evidence_id desc (most recent first)

    Returns:
        active contradiction evidence_ids, **freshness desc** order.
        없으면 빈 tuple.

    Raises:
        KeyError: unknown claim_id.
    """
```

이게 PR11-A 의 전부.

| 옵션 | 채택 | 이유 |
|---|---|---|
| (C-minimal) primitive 1개만 | ✗ | caller 가 매번 정렬 코드 작성 |
| **(C-pair) primitive + 가장 자주 쓰일 패턴** | ✓ | 균형. PR9-A 차집합 의미는 그대로, 정렬 키만 다름 |
| (C-extensive) more | ✗ | 사용 패턴 보고 후속 PR 에서 결정 |

### 25.6 PR9-A 와의 정합 — 같은 set, 다른 정렬

```python
# PR9-A
active_contradictions_for_claim(c)
# = (contradictions_for_claim(c) - resolved_contradictions_for_claim(c))
# 정렬: evidence_id asc

# PR11-A
active_contradictions_by_freshness(c)
# = 같은 set
# 정렬: evidence_id desc (freshness desc — 큰 id 가 최근)
```

PR9-A 의 차집합 의미는 그대로 보존. PR11-A 가 추가하는 것은 **다른 view** 만.

### 25.7 보존 (impact 없음)

| | PR11-A 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` / `ScoreValue` / `ClaimLifecycleEvent` dataclass | 없음 |
| `add_claim` / `add_evidence` / `add_gap` 의미 | 없음 |
| `_next_id` (evidence counter) | 없음 (읽기만, 변경 없음) |
| 5 lifecycle API (PR6~PR10-A) | 없음 |
| `register_contradiction*` (PR7, PR9-A) | 없음 |
| `contradictions_for_claim` / `resolved_contradictions_for_claim` / `active_contradictions_for_claim` | 없음 |
| `_contradictions` / `_resolved_contradictions` / `_gap_resolutions` 인덱스 | 없음 |
| `_lifecycle_seq` / `_claim_lifecycle_events` (PR10-B) | 없음 |
| `claim_lifecycle_history` | 없음 |
| `compute_effective_confidence` (PR11-D) | 없음 |
| `_STATUS_MODIFIER_*` / `_STATUS_TO_MODIFIER` (PR11-D) | 없음 |
| `_REFUTATION_STRENGTH_THRESHOLD` (PR10-A) | 없음 |
| `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 (Sub-decision D 정합) |
| `fire_rule*` / `RuleStats` | 없음 |
| public exports | 없음 (새 dataclass / 상수 없음) |
| 외부 dependency | 없음 (외부 clock 안 봄) |

PR11-A 는 **engine 동작 변경 0**. 2 신규 query API 만 추가.

### 25.8 Invariants (테스트로 잠금)

1. `evidence_freshness` unknown evidence_id → `KeyError`
2. `active_contradictions_by_freshness` unknown claim_id → `KeyError`
3. `evidence_freshness(ev)` 는 `ev` (evidence.id 값) 그대로 반환
4. 더 최근 등록 evidence 의 freshness 가 더 크다
5. `active_contradictions_by_freshness` 는 desc order (가장 최근 첫째)
6. `active_contradictions_by_freshness` 의 set 은 `active_contradictions_for_claim` 와 동일
7. `active_contradictions_by_freshness` 는 resolved contradiction 제외 (PR9-A 차집합 정합)
8. **PR10-A `refute_disputed_claim_if_ready` 의 동작 무변화** ★ (Sub-decision B)
9. **PR11-D `compute_effective_confidence` 의 동작 무변화** ★ (Sub-decision B)
10. PR9-A `active_contradictions_for_claim` 의 asc 정렬 의미 무변화
11. `evidence_freshness` / `active_contradictions_by_freshness` 호출이
    engine 의 어떤 state 도 변경 안 함 (read-only)
12. 빈 active (모두 resolved 또는 없음) → 빈 tuple
13. 같은 evidence_id 의 freshness 가 시간이 흘러도 변하지 않음 (등록 시점 고정)
14. 기존 534 회귀 없음 (전체 통과로 입증)

### 25.9 Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| PR10-A `refute_disputed_claim_if_ready` 정책 변경 (freshness 가중치) | PR11-B 자연 후속 (Sub-decision B 정신) |
| PR11-D `compute_effective_confidence` modifier 분해 (status × freshness) | PR11-C 또는 PR12+ |
| 새 `freshness_for_claim(claim_id)` 같은 claim 전체 freshness 조회 | 사용 패턴 보고 후속 |
| `most_recent_evidence(claim_id)` 같은 single-most-recent 조회 | (C-extensive) — 후속 |
| `freshness_rank(evidence_id)` 같은 normalized rank | 별도 결정점 (PR1 의 _next_id 가 unbounded int) |
| Wall-clock timestamp 도입 | PR10-A / PR10-B 와 일관 영구 OOS |
| Freshness based scoring / refute / lifecycle 자동 결정 | side effect 의 side effect — 명시성 위반 |
| 새 dataclass / 새 상수 (public) | engine read-only query 만 — 새 carrier 없음 |
| Persistence / 직렬화 | 별도 PR |
| Cross-engine freshness 비교 | per-engine — 의미 없음 (PR10-B Sub-decision L 정신) |
| `evidence.id` 외 다른 freshness signal | Sub-decision A 일관 |

### 25.10 Position in flow

```text
PR11-D 까지:
  evidence 의 등록 순서는 evidence.id 에 암묵적으로 표현됨
  → caller 가 직접 evidence.id 비교해야 freshness 비교 가능

PR11-A:
  evidence_freshness(ev) → evidence.id (1급 의미)
  active_contradictions_by_freshness(c) → freshness desc tuple

  엔진은 freshness 자체에 따라 어떤 결정도 자동으로 내리지 않음.
  caller 가 freshness 를 보고 의사결정에 사용할 자유만 부여.

  미래 (PR11-B / PR11-C / PR12):
    - refute 정책에 freshness 가중치 통합
    - effective_confidence modifier 분해 (status × freshness)
    - freshness-aware confidence scoring
```

구현 단계 (59/60차) — **테스트 먼저 잠금 → 구현** 순서:
- 59차: tests (위 14 invariant) — `AttributeError` 로 fail (단, invariant 8/9/10 같은 무변화 검증은 이미 pass)
- 60차: `evidence_freshness` + `active_contradictions_by_freshness` 두 메서드 구현 — 59차 테스트 통과로 입증

## 26. Effective confidence — freshness modifier (MVP)

> 상태: 62/63/64차 (PR11-C). PR11-D 의 modifier 구조를
> `status × freshness` 로 분해.
> **PR10-A refute 정책 변경 / 모든 active 가중합 / max strength / freshness rank
> weighting / older strong evidence 고려 / gap modifier / RuleStats modifier
> 모두 본 PR 범위 밖** — PR11-B 또는 PR12+.

### 26.1 PR11-C 의 한 줄 정의

> **PR11-C 는 confidence 를 0 까지 죽이는 PR 이 아니라, 최신 active
> contradiction 이 있을 때 보수적으로 감쇠하는 PR 이다. 완전한 부정은 여전히
> PR10-A 의 `refute_disputed_claim_if_ready` 가 담당한다.**

PR11-D §24.5 의 명시적 미래 자리 ("미래 정책 도입 시 modifier 분해 가능") 의
첫 활용. PR11-A 가 노출한 query (`active_contradictions_by_freshness`) 를
PR11-D 의 modifier 분해에 input 으로 통합.

### 26.2 핵심 명제

```text
Effective confidence under freshness modifier is continuous attenuation,
not a binary kill.

PR11-C 는 PR10-A 의 binary refute trigger 와 분리된 continuous attenuation
을 도입한다. 같은 active contradiction strength 가 두 정책의 input 이지만
의미가 다르다:
  - PR10-A: strength >= 0.8 → status 전이 (binary, threshold)
  - PR11-C: strength → effective 감쇠 (continuous, modifier)

PR11-C 는 PR10-A refute 정책 / PR11-A freshness query /
PR9-A active contradiction 의미를 변경하지 않는다.
```

### 26.3 공식 — modifier 분해

```python
effective_confidence(claim) = (
    base_confidence
    × status_modifier(claim.status)         # PR11-D §24 그대로
    × freshness_modifier(claim_id)           # PR11-C 신규
)
```

`status_modifier` 표 (PR11-D §24.3 변경 없음):

| status | modifier |
|---|---|
| `CANDIDATE` | 1.0 |
| `CONFIRMED` | 1.0 |
| `DISPUTED` | 0.5 |
| `REFUTED` | 0.0 |

`freshness_modifier` 표 (PR11-C 신규):

```python
freshness_modifier(claim_id) = (
    1.0
    if active_contradictions_by_freshness(claim_id) == ()
    else 1.0 - (most_recent_evidence.strength.value × _FRESHNESS_PENALTY_WEIGHT)
)
```

`_FRESHNESS_PENALTY_WEIGHT = 0.5` (engine 내부 private).

| `most_recent.strength.value` | `freshness_modifier` |
|---|---|
| 0.0 | 1.0 (감쇠 없음) |
| 0.5 | 0.75 |
| 0.8 | 0.6 |
| 1.0 | 0.5 (최대 감쇠) |

### 26.4 Sub-decision O — 최신 1개만 사용

`freshness_modifier` 는 `active_contradictions_by_freshness(c)` 의 **첫 번째
(가장 최근) evidence 하나만** 본다.

| 옵션 | 채택 | 이유 |
|---|---|---|
| **(O-most-recent-only) 최신 1개** | ✓ | 가장 작은 잠금. PR10-A 단순성 정신 |
| (O-all-weighted-sum) 모든 active 가중합 | ✗ | 결정 부담 큼, modifier 의미 복잡 |
| (O-max-strength) max strength | ✗ | freshness 의미 무시, PR10-A 와 의미 중복 |
| (O-rank-weighted) freshness rank weighting | ✗ | rank 정의 부담 |
| (O-older-strong) older strong evidence 고려 | ✗ | "최근" 정의 모순 |

이 단순성이 PR11-C 의 안전망. 확장은 PR11-B / PR12+.

### 26.5 Sub-decision P — status × freshness, refuted 시 0 보존

```python
effective = base × status_modifier × freshness_modifier

# refuted:
#   status_modifier = 0.0
#   freshness_modifier 무엇이든
#   effective = base × 0.0 × X = 0.0
```

`status_modifier = 0.0` 인 refuted 케이스에서 freshness_modifier 가 무엇이든
**effective = 0.0** 보장. PR11-D 의 "refuted = 확정 부정" 의미 유지.

`freshness_modifier` 자체는 `status` 와 무관하게 계산 가능 (read-only on
claim.status, no status guard inside).

### 26.6 PR10-A 와의 정합 — 의미 분리

| | PR10-A | PR11-C |
|---|---|---|
| Input | active contradiction strength | active contradiction strength |
| 표현 | binary trigger (`>= 0.8`) | continuous attenuation (`1 - s × 0.5`) |
| 결과 | status 전이 (`disputed → refuted`) | scoring 감쇠 (`effective` 값) |
| Threshold | `_REFUTATION_STRENGTH_THRESHOLD = 0.8` | `_FRESHNESS_PENALTY_WEIGHT = 0.5` |
| 시점 | refute 호출 시 | compute_effective 호출 시 |

**의미 충돌 없음** — 하나는 lifecycle 상태 변환, 하나는 scoring view 감쇠.
같은 input 을 두 정책에서 따로 활용.

### 26.7 PR11-A 와의 정합

PR11-C 가 `active_contradictions_by_freshness(claim_id)` 를 **input 으로만
활용**. PR11-A query 의 의미 / return 형식 / 정렬 / 차집합 모두 변경 안 함.
PR11-A 의 Sub-decision B (query only) 정신과 정합 — PR11-A 가 노출한 query 를
PR11-C 가 처음 활용.

### 26.8 PR11-D 와의 정합 — 시그니처 / KeyError / return type 보존

```python
# PR11-D (변경 안 됨)
def compute_effective_confidence(self, claim_id: int) -> ScoreValue: ...
```

PR11-C 는 **시그니처 변경 0**:
- `claim_id: int` 입력 그대로
- `ScoreValue` 반환 그대로
- unknown claim_id → KeyError 그대로

본문만 `× freshness_modifier(claim_id)` 추가.

### 26.9 결정성 (Determinism)

```text
같은 (claim.base_confidence, claim.status,
      active_contradictions_by_freshness(claim_id) 결과,
      evidence.strength) → 항상 같은 effective_confidence
```

PR11-C 는:
- wall-clock 안 봄
- random / external state 안 봄
- PR1 `_next_id` 카운터 안 봄 (freshness 가 evidence.id 인 건 PR11-A 결정,
  PR11-C 는 PR11-A 의 query 결과만 input 으로 사용)

테스트 재현 100% 보장. PR11-D 결정성 그대로 유지.

### 26.10 Private constant

```python
# Engine module level (PR11-D _STATUS_MODIFIER_* / PR10-A
# _REFUTATION_STRENGTH_THRESHOLD 와 동일 위치)
_FRESHNESS_PENALTY_WEIGHT = 0.5
```

- **Public export 안 함** (engine 내부 private)
- PR10-A `_REFUTATION_STRENGTH_THRESHOLD` / PR11-D `_STATUS_MODIFIER_*` 와
  동일 정신 — 미래 정책 변경 자유

### 26.11 보존 (impact 없음)

| | PR11-C 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` / `ScoreValue` / `ClaimLifecycleEvent` dataclass | 없음 |
| `Claim.base_confidence` 값 | 없음 (read-only) |
| `compute_effective_confidence` 시그니처 | 없음 (본문만 변경) |
| PR11-D status_modifier 값 (1.0/1.0/0.5/0.0) | 없음 |
| `_STATUS_MODIFIER_*` / `_STATUS_TO_MODIFIER` | 없음 (재활용) |
| PR10-A refute 정책 (`_REFUTATION_STRENGTH_THRESHOLD`, `refute_disputed_claim_if_ready`) | 없음 |
| PR9-A `active_contradictions_for_claim` asc 정렬 | 없음 |
| PR11-A `evidence_freshness` / `active_contradictions_by_freshness` 시그니처 | 없음 |
| 5 lifecycle API / `register_contradiction*` | 없음 |
| `_contradictions` / `_resolved_contradictions` / `_gap_resolutions` 인덱스 | 없음 |
| `_lifecycle_seq` / `_claim_lifecycle_events` (PR10-B) | 없음 |
| `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 (Sub-decision D 정합) |
| `fire_rule*` / `RuleStats` | 없음 |
| public exports | 없음 (새 상수 / 새 메서드 없음, `_FRESHNESS_PENALTY_WEIGHT` private) |

PR11-C 는 `compute_effective_confidence` 의 본문에 **곱셈 1개 추가** 만.

### 26.12 Invariants (테스트로 잠금)

1. unknown claim_id → `KeyError` (PR11-D 동작 보존)
2. **candidate + active 0 → effective == base × 1.0 × 1.0 = base** (PR11-D 와 동일)
3. **confirmed + active 0 → effective == base** (PR11-D 와 동일)
4. **disputed + active 0 → effective == base × 0.5** (PR11-D 와 동일, freshness 1.0)
5. **refuted + 어떤 active → effective == 0.0** ★ (Sub-decision P, status × freshness 와 무관)
6. **confirmed + active 1+ strength 0.8 → effective == base × 1.0 × 0.6 = base × 0.6** ★ (PR11-C 핵심)
7. **disputed + active 1+ strength 1.0 → effective == base × 0.5 × 0.5 = base × 0.25** ★ (modifier 곱셈)
8. active 첫 evidence (`active_contradictions_by_freshness[0]`) 만 본다 (Sub-decision O)
9. resolved contradiction 은 freshness 에서 제외 (PR9-A 차집합 정합)
10. **PR10-A `refute_disputed_claim_if_ready` 동작 변경 없음** ★ (Sub-decision)
11. **PR11-A `evidence_freshness` / `active_contradictions_by_freshness` 동작 변경 없음**
12. **PR9-A `active_contradictions_for_claim` asc 동작 변경 없음**
13. **PR11-D status_modifier (`_STATUS_MODIFIER_*`) 값 변경 없음**
14. effective never exceeds base (no boost — Sub-decision N 정신 유지)
15. compute is read-only (gap / contradictions / lifecycle_history /
    base_confidence 무변화)
16. determinism — 같은 input → 같은 output
17. `_FRESHNESS_PENALTY_WEIGHT` private (ragcore + ragcore.types 미노출)
18. 기존 547 회귀 없음 (전체 통과로 입증)

### 26.13 Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| 모든 active contradiction 가중합 | Sub-decision O |
| max strength (active 들 중) | Sub-decision O |
| Freshness rank weighting | Sub-decision O |
| Older strong evidence 고려 | Sub-decision O (최신 1개만) |
| PR10-A `refute_disputed_claim_if_ready` 정책 변경 (freshness 가중치 포함) | PR11-B 자연 후속 |
| Gap-based modifier (unresolved gap 페널티) | PR12+ |
| Contradiction count modifier (active 개수 기반) | PR12+ |
| RuleStats-based modifier (observed_precision / false_positive_rate) | PR12+ |
| Lifecycle history-based modifier (transition 횟수) | PR12+ |
| Confidence boost (modifier > 1.0) | PR11-D Sub-decision N 일관 — 영구 OOS |
| Caller-driven modifier 함수 / config injection | PR10-A / PR11-D 정신 |
| LLM / semantic confidence | core 밖 |
| Mutable confidence / setter | immutability |
| Public `FRESHNESS_PENALTY_WEIGHT` constant | engine 내부 private |
| Wall-clock timestamp 도입 | PR10-A/B / PR11-D / PR11-A 일관 OOS |
| Cross-engine freshness 비교 | per-engine 의미 |

### 26.14 Position in flow

```text
PR11-D 까지:
  effective = base × status_modifier
  → status 만 scoring 에 반영. active contradiction strength 는 무관.

PR11-A 까지:
  evidence_freshness / active_contradictions_by_freshness query 추가.
  하지만 어떤 정책도 freshness 사용 안 함.

PR11-C:
  effective = base × status_modifier × freshness_modifier(claim_id)
  freshness_modifier 는 가장 최근 active contradiction 의 strength 만 본다.
  → PR11-A 가 노출한 query 를 PR11-D modifier 분해에 input 으로 통합.

  PR10-A refute 와 의미 분리:
    PR10-A: binary trigger (>= 0.8) → status 전이
    PR11-C: continuous attenuation → scoring 감쇠
```

구현 단계 (63/64차) — **테스트 먼저 잠금 → 구현** 순서:
- 63차: tests (위 18 invariant) — PR11-D 본문 변경 전 일부는 이미 pass (active 0 / refuted), 일부는 fail (active 1+ 시 추가 감쇠)
- 64차: `_FRESHNESS_PENALTY_WEIGHT` private constant + `compute_effective_confidence` 본문 확장 (× freshness_modifier 추가) — 63차 테스트 통과로 입증

## 27. Freshness-aware disputed refutation (MVP — sibling API)

> 상태: 66/67/68차 (PR11-B). PR10-A `refute_disputed_claim_if_ready` 의 sibling
> API 추가. 기존 PR10-A 변경 0.
> **PR10-A 정책 변경 / threshold 값 변경 / PR11-C effective scoring 변경 /
> gap modifier / RuleStats / multi-evidence aggregation 모두 본 PR 범위 밖**.

### 27.1 PR11-B 의 한 줄 정의

> **PR11-B 는 PR10-A 의 refute 정책을 바꾸는 PR 이 아니라, freshness 정렬
> 기준으로 refute 하는 sibling API 를 추가하는 PR 이다.**

PR9-A `active_contradictions_for_claim` (asc) 과 PR11-A
`active_contradictions_by_freshness` (desc) 가 같은 set 의 다른 정렬 view
였듯, PR11-B 는 PR10-A 의 refute 와 같은 status target (REFUTED) 의 다른
input view (FIRST by freshness 만) sibling.

### 27.2 핵심 명제

```text
PR11-B introduces a sibling refute API that inspects the most recent active
contradiction only, not all of them.

PR10-A inspects ANY active contradiction.
PR11-B inspects FIRST (by freshness) active contradiction only.

Both produce CLAIM_STATUS_REFUTED. Both use the same threshold (0.8).
The difference is which input set the policy reads — not threshold, not output.

PR11-B does not change PR10-A semantics. Existing callers and tests of
PR10-A remain valid.
```

한국어:

```text
PR11-B 는 sibling refute API 를 도입한다 — 모든 active 가 아니라 가장 최근
active contradiction 하나만 본다.

PR10-A: active 중 ANY 하나라도 strength >= 0.8 → refute
PR11-B: active 중 FIRST (freshness desc) 의 strength >= 0.8 → refute

두 API 모두 CLAIM_STATUS_REFUTED 를 생성. 같은 threshold (0.8). 차이는
정책이 보는 input set 만 — threshold 도 아니고 output 도 아니다.

PR11-B 는 PR10-A 의 의미를 변경하지 않는다. PR10-A 의 기존 caller / 테스트
모두 그대로 유효.
```

### 27.3 lifecycle 위치 — 같은 status target, 다른 path

```text
PR10-A 까지:
  disputed
    └─ refuted  (PR10-A: any active strength >= 0.8)

PR11-B 추가:
  disputed
    ├─ refuted  (PR10-A: any active strength >= 0.8)
    └─ refuted  (PR11-B: first-by-freshness strength >= 0.8)  ← path 추가

같은 target status, 다른 path. PR10-B audit 가 path 구분.
```

### 27.4 Sub-decision Q — Trigger 정의

```python
def refute_disputed_claim_if_ready_by_freshness(self, claim_id):
    if claim.status != CLAIM_STATUS_DISPUTED:
        return False
    active = self.active_contradictions_by_freshness(claim_id)
    if not active:
        return False
    most_recent = self._evidences[active[0]]
    if most_recent.strength.value >= _REFUTATION_STRENGTH_THRESHOLD:
        # refute
```

`active[0]` 만 본다. older active strong 은 무시. PR11-C 의 Sub-decision O
정신 일관 (최신 1개만 사용).

### 27.5 Sub-decision R — Threshold 재사용

```python
# 기존 PR10-A constant 재사용
_REFUTATION_STRENGTH_THRESHOLD = 0.8
```

**새 상수 도입 안 함**. PR10-A 와 같은 의미축 (active contradiction strength).
두 정책의 차이는 보는 set 만 (ANY vs FIRST). threshold 도 달라지면 의미
분기 부담 큼.

PR10-A `_REFUTATION_STRENGTH_THRESHOLD = 0.8` 그대로 활용.

### 27.6 Sub-decision S — Transition label

PR10-B 의 5 transition label 표에 신규 entry 추가:

| API | `transition` 값 |
|---|---|
| PR10-A `refute_disputed_claim_if_ready` (변경 안 됨) | `"refute_disputed_if_ready"` |
| **PR11-B `refute_disputed_claim_if_ready_by_freshness` (신규)** | **`"refute_disputed_by_freshness_if_ready"`** |

PR10-B Sub-decision I (private string literal audit label) 정신 일관.
caller 가 `claim_lifecycle_history` 에서 두 path 를 구분 가능:

```python
event.transition == "refute_disputed_if_ready"               # PR10-A
event.transition == "refute_disputed_by_freshness_if_ready"  # PR11-B
```

### 27.7 결정표 — PR11-B 와 PR10-A 의 분리

| Claim status | active 0 | active 1+ ANY >= 0.8 | active 1+ FIRST(by fresh) >= 0.8 |
|---|---|---|---|
| `disputed` | A: False / B: False | A: True / B: ? | A: True / B: True |
| `disputed` (older strong, recent weak) | — | A: True / B: False ★ | — |
| `disputed` (older weak, recent strong) | — | A: True / B: True | A: True / B: True |
| `confirmed` / `candidate` / `refuted` | False / False | False / False | False / False |

**핵심 분리 케이스 ★**: older active (strength >= 0.8) + recent active
(strength < 0.8) → PR10-A True, PR11-B False. 둘이 다르게 답함.

### 27.8 PR9-A / PR10-A / PR11-B mutual exclusivity

```text
disputed + active 0:
  PR9-A resolve_disputed_claim_if_ready    → True (confirmed 복귀)
  PR10-A refute_disputed_claim_if_ready    → False (active 없음)
  PR11-B refute_disputed_claim_if_ready_by_freshness → False (active 없음)

disputed + active 1+, ANY >= 0.8, FIRST < 0.8:
  PR9-A → False (active 잔존)
  PR10-A → True (REFUTED 전이)
  PR11-B → False (FIRST < 0.8)

disputed + active 1+, ANY < 0.8 (FIRST 도 < 0.8):
  PR9-A → False
  PR10-A → False
  PR11-B → False
  → disputed 유지

disputed + active 1+, FIRST >= 0.8 (당연히 ANY 도 >= 0.8):
  PR9-A → False
  PR10-A → True
  PR11-B → True
  → 호출 순서로 어느 path 가 audit 에 기록되는지 결정
```

**같은 status target (REFUTED)** 이지만 **호출 순서가 audit path 를 결정**.
caller 가 어느 API 를 먼저 호출하든 두 번째 호출은 status guard 로 False
(`status != CANDIDATE` 아니고 `!= DISPUTED` 라서).

### 27.9 호환성 — PR10-A 무변화

PR11-B 의 신규 API 추가가 PR10-A 의 어떤 의미도 변경하지 않음:

| | PR10-A 영향 |
|---|---|
| `refute_disputed_claim_if_ready` 시그니처 | 없음 |
| `refute_disputed_claim_if_ready` 동작 | 없음 (ANY active 정책 그대로) |
| `_REFUTATION_STRENGTH_THRESHOLD` 값 | 없음 (재사용) |
| PR10-A invariants | 모두 유효 |
| PR10-A 기존 caller | 코드 변경 0 |

### 27.10 보존 (impact 없음)

| | PR11-B 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` / `ScoreValue` / `ClaimLifecycleEvent` dataclass | 없음 |
| `add_claim` / `add_evidence` / `add_gap` 의미 | 없음 |
| 5 기존 lifecycle API (PR6/PR7/PR8/PR9-A/PR10-A) | 없음 |
| `register_contradiction*` | 없음 |
| PR9-A `active_contradictions_for_claim` (asc) | 없음 |
| PR11-A `evidence_freshness` / `active_contradictions_by_freshness` | 없음 (input 으로만 사용) |
| PR11-D + PR11-C `compute_effective_confidence` | 없음 (PR11-C 의 continuous attenuation 그대로) |
| `_contradictions` / `_resolved_contradictions` / `_gap_resolutions` 인덱스 | 없음 |
| `_REFUTATION_STRENGTH_THRESHOLD` (재사용) / `_STATUS_MODIFIER_*` / `_FRESHNESS_PENALTY_WEIGHT` | 없음 |
| `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 (Sub-decision D 정합) |
| `fire_rule*` / `RuleStats` | 없음 |
| public exports | 없음 (새 dataclass / 상수 없음, 메서드만 추가) |
| 외부 dependency | 없음 |

PR11-B 는 **신규 API 1개만 추가**. 기존 동작 변경 0.

### 27.11 lifecycle history 통합 — PR10-B audit 확장

PR11-B 의 신규 API 가 True 반환 시 PR10-B 의 `_record_claim_lifecycle_transition`
helper 자동 호출 — 시그니처 / 호출 패턴 모두 PR10-A 와 동일:

```python
# PR11-B 의 True path
old_status = claim.status  # DISPUTED
self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_REFUTED)
self._record_claim_lifecycle_transition(
    claim_id, old_status, CLAIM_STATUS_REFUTED,
    "refute_disputed_by_freshness_if_ready",  # Sub-decision S
)
return True
```

PR10-B 의 transition label 표가 5 → 6 으로 확장 (Sub-decision S):

| transition label | API | path |
|---|---|---|
| `"confirm_if_ready"` | PR6 | candidate → confirmed |
| `"refute_if_ready"` | PR7 | candidate → refuted |
| `"dispute_if_ready"` | PR8 | confirmed → disputed |
| `"resolve_disputed_if_ready"` | PR9-A | disputed → confirmed |
| `"refute_disputed_if_ready"` | PR10-A | disputed → refuted (any active) |
| **`"refute_disputed_by_freshness_if_ready"`** | **PR11-B** | **disputed → refuted (first by freshness)** |

caller 가 lifecycle history 의 `transition` 으로 refute path 구분 가능.

### 27.12 Invariants (테스트로 잠금)

1. `refute_disputed_claim_if_ready_by_freshness` unknown claim_id → `KeyError`
2. candidate / confirmed / refuted (status guard 3) → `False`
3. disputed + active 0 → `False`
4. disputed + 가장 최근 active strength < 0.8 → `False`
5. **disputed + 가장 최근 active strength >= 0.8 → `True`, REFUTED ★**
6. **Threshold boundary 0.8 정확 → `True`** (`>=` 비교)
7. **Threshold 직하 0.799999 → `False`**
8. **Sub-decision Q: older strong + recent weak → `False`** ★ (PR10-A 와 다름)
9. Resolved contradiction 은 판정에서 제외 (PR9-A 차집합 정합)
10. refuted 재호출 → `False` (idempotent)
11. **PR10-B audit 통합**: True 반환 시 lifecycle event 기록,
    `transition == "refute_disputed_by_freshness_if_ready"` ★
12. **PR10-A `refute_disputed_claim_if_ready` 동작 무변화** ★ (호환성)
13. **PR11-C `compute_effective_confidence` 동작 무변화** ★
14. PR11-A `evidence_freshness` / `active_contradictions_by_freshness` 무변화
15. PR9-A `active_contradictions_for_claim` asc 무변화
16. PR11-D `_STATUS_MODIFIER_*` 값 무변화
17. transition isolation (gap state / contradictions / resolved / base_confidence 무변화)
18. **PR9-A / PR10-A / PR11-B mutual exclusivity** ★ (active 0 vs active 1+ 가드)
19. `_REFUTATION_STRENGTH_THRESHOLD` 재사용 (새 상수 없음 — Sub-decision R)
20. 새 transition label `"refute_disputed_by_freshness_if_ready"` private literal
21. 기존 564 회귀 없음 (전체 통과로 입증)

### 27.13 Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| PR10-A `refute_disputed_claim_if_ready` 정책 변경 | sibling 결정 (Sub-decision: 호환 유지) |
| Threshold 변경 / 새 threshold 도입 | Sub-decision R (재사용) |
| 모든 active 가중합 / max / rank weighting | Sub-decision Q (FIRST 만) |
| Older strong evidence 고려 | Sub-decision Q (FIRST 만) |
| PR11-C `compute_effective_confidence` 변경 | PR11-C 의 continuous 와 PR11-B 의 binary 분리 |
| Gap-based / count-based / RuleStats-based refute trigger | PR12+ |
| LLM / semantic 기반 refute | core 밖 |
| 자동 호출 (resolve / register 시 side effect) | 명시 호출 원칙 |
| 새 status / 새 lifecycle 전이 | sibling refute 만 — 같은 REFUTED target |
| Public `_REFUTATION_STRENGTH_THRESHOLD` | engine 내부 private 유지 |
| Public `TRANSITION_*` constants | PR10-B Sub-decision I 정합 |
| Wall-clock timestamp | PR10-A/B / PR11-A/C/D 일관 영구 OOS |

### 27.14 Position in flow

```text
PR10-A 까지:
  disputed + active 중 ANY >= 0.8 → refute_disputed_claim_if_ready True → REFUTED
  freshness 정렬 정보는 사용 안 함

PR11-A:
  active_contradictions_by_freshness query 추가 (read-only)

PR11-C:
  effective = base × status × freshness_modifier
  most_recent 의 strength 를 continuous attenuation 으로 활용

PR11-B:
  refute_disputed_claim_if_ready_by_freshness 추가 (sibling API)
  most_recent 의 strength 를 binary refute trigger 로 활용
  - PR10-A 호환 유지 (PR10-A 변경 0)
  - PR11-C 의 continuous 와 PR11-B 의 binary 분리
  - PR10-B audit 가 두 refute path 구분
```

구현 단계 (67/68차) — **테스트 먼저 잠금 → 구현** 순서:
- 67차: tests (위 21 invariant) — PR11-B API 미구현 → `AttributeError` fail. 단, "PR10-A / PR11-C / PR11-A / PR9-A / PR11-D 무변화" 검증은 이미 pass (PR11-A 59차 / PR11-C 63차 패턴)
- 68차: `refute_disputed_claim_if_ready_by_freshness` 메서드 구현 (PR10-B `_record_claim_lifecycle_transition` 호출 포함) — 67차 테스트 통과로 입증

## 28. Effective confidence — gap modifier (MVP — binary, weak)

> 상태: 70/71/72차 (PR12-D). PR11-D 의 modifier 분해 자리에 `gap_modifier`
> 추가. `effective = base × status × freshness × gap`.
> **N-dependent gap modifier / gap 종류별 가중치 / RuleStats / count modifier
> / superseded/retracted 상태 모두 본 PR 범위 밖** — PR12+.

### 28.1 PR12-D 의 한 줄 정의

> **PR12-D 는 gap 판단을 정교화하는 PR 이 아니라, PR5 의 gap resolution
> 의미가 effective_confidence 에 처음 연결되는 최소 연결 PR 이다.**

PR11-D §24.5 의 modifier 분해 자리 (status × freshness 이미 채워짐) 의 **세
번째 modifier** 활용. PR5 의 `gaps_for_claim` / `gap_resolution` 을
effective scoring 에 input 으로 통합.

### 28.2 핵심 명제 (§28.2)

```text
Gap modifier is binary and weak:
unresolved gap means information is incomplete, not contradicted.
```

한국어:

```text
Gap modifier 는 binary 이고 약하다:
unresolved gap 은 '정보 부족' 이지 '반박' 이 아니다.
```

이 명제가 Sub-decision T (값 0.8) 의 근거. PR10-A refute / PR11-C effective
attenuation 보다 명확히 약한 페널티.

### 28.3 공식 — modifier 분해 (status × freshness × gap)

```python
effective_confidence(claim) = (
    base_confidence
    × status_modifier(claim.status)         # PR11-D §24, 변경 없음
    × freshness_modifier(claim_id)           # PR11-C §26, 변경 없음
    × gap_modifier(claim_id)                 # PR12-D §28, 신규
)
```

`status_modifier` (PR11-D, 변경 없음):

| status | modifier |
|---|---|
| `CANDIDATE` | 1.0 |
| `CONFIRMED` | 1.0 |
| `DISPUTED` | 0.5 |
| `REFUTED` | 0.0 |

`freshness_modifier` (PR11-C, 변경 없음):

```python
1.0 if active 0 else (1.0 - most_recent.strength.value × 0.5)
```

`gap_modifier` (PR12-D 신규, Sub-decision T + U):

```python
def gap_modifier(claim_id):
    gaps = self.gaps_for_claim(claim_id)
    if not gaps:
        return 1.0
    if all(self.gap_resolution(g.id) is not None for g in gaps):
        return 1.0
    return _GAP_PENALTY_MODIFIER  # 0.8
```

`_GAP_PENALTY_MODIFIER = 0.8` (engine 내부 private).

### 28.4 Sub-decision T — Constant 0.8

```python
_GAP_PENALTY_MODIFIER = 0.8
```

| 옵션 | 채택 | 의미 |
|---|---|---|
| (T-0.3) 강한 페널티 | ✗ | gap 부족이 거의 disputed 수준 — 과한 의미 부여 |
| (T-0.5) 중간 | ✗ | PR11-D `disputed=0.5` / PR11-C `weight=0.5` 와 동급 — gap = lifecycle / contradiction 신호와 같은 무게 |
| **(T-0.8) 약한 페널티** | ✓ | "정보 부족" 의 약한 신호. lifecycle / contradiction 보다 명확히 약함 |

값의 의미 (단독으로):

| 시나리오 | gap_modifier | 다른 modifier 1.0 가정 시 effective |
|---|---|---|
| gap 0 개 | 1.0 | base × 1.0 = base |
| 모든 gap resolved | 1.0 | base × 1.0 = base |
| unresolved 1+ | 0.8 | base × 0.8 |

### 28.5 Sub-decision U — Binary, N 무관

```text
unresolved gap 1+ → 0.8
그 외 → 1.0

N 의존 없음 (1개든 10개든 동일).
```

| 옵션 | 채택 | 이유 |
|---|---|---|
| **(U-binary)** | ✓ | "최소 연결 PR" 정신. PR11-C Sub-decision O ("최신 1개만") 와 같은 단순성 |
| (U-N-dependent) | ✗ | 함수 형태 / saturation / hard floor 등 추가 결정 부담 |

PR12-D 의 본질은 "gap resolution 의미를 effective 에 처음 연결". 정교화는
PR12+ 자연 후속.

### 28.6 결정성 (Determinism)

```text
같은 (claim.base_confidence, claim.status,
      active_contradictions_by_freshness(c),
      gaps_for_claim(c), gap_resolution(g) for g in gaps,
      evidence.strength) → 항상 같은 effective_confidence
```

PR12-D 는:
- wall-clock 안 봄
- random / external state 안 봄
- PR5 `gaps_for_claim` + `gap_resolution` 결정성 그대로 유지

PR11-D / PR11-C 결정성 그대로 + PR5 gap 의 결정성 통합.

### 28.7 PR5 와의 정합 — gap_resolution 의미 보존

`gap_modifier` 는 PR5 의 `gap_resolution(g.id)` 를 input 으로만 활용. PR5 의
의미 / return / first-keep / KeyError 동작 변경 0.

```text
PR5: gap_resolution(g.id) → evidence_id | None
PR12-D: gap_resolution(g.id) is None → unresolved
        all resolved → modifier 1.0
        any unresolved → modifier 0.8
```

### 28.8 PR11-D / PR11-C 와의 정합 — modifier 분해 자리 활용

```python
# PR11-D §24.5 의 명시적 미래 자리 (modifier 분해)
effective = base × status_modifier × freshness_modifier × gap_modifier
                                  └── PR11-C ───┘   └── PR12-D 신규 ──┘
```

PR11-D 의 시그니처 / KeyError / return type 그대로. 본문에 `× gap_modifier(claim_id)`
추가만.

| | PR11-D | PR11-C | PR12-D |
|---|---|---|---|
| 영역 | status | freshness | gap |
| MVP 형태 | 4 status 의 4 값 | continuous (× 0.5 weight) | binary (× 0.8 or 1.0) |
| Private constant | `_STATUS_MODIFIER_*` | `_FRESHNESS_PENALTY_WEIGHT = 0.5` | **`_GAP_PENALTY_MODIFIER = 0.8`** |

세 modifier 모두 [0.0, 1.0] (no boost — PR11-D Sub-decision N 정신).

### 28.9 의미 분리 (gap vs contradiction vs status)

같은 effective 공식에 들어가는 세 modifier 의 의미:

| modifier | 의미 신호 | 강도 |
|---|---|---|
| status_modifier | lifecycle 상태 (확정 / 반박 / 격리) | 강 (refuted = 0.0) |
| freshness_modifier (PR11-C) | 최근 contradiction 의 strength | 중 (max 50% 감쇠) |
| **gap_modifier (PR12-D)** | **정보 부족** | **약 (20% 감쇠 = 0.8)** |

gap 신호가 contradiction / lifecycle 보다 명확히 약한 게 §28.2 명제의 직접
표현.

### 28.10 Sub-decision P 정신 보존 — refuted 시 0

```text
refuted:
  status_modifier = 0.0
  freshness_modifier × gap_modifier 무엇이든
  effective = base × 0.0 × X × Y = 0.0
```

PR11-C Sub-decision P 와 같은 자연 결과. gap_modifier 가 무엇이든 status=0
이면 effective=0.

### 28.11 보존 (impact 없음)

| | PR12-D 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` / `ScoreValue` / `ClaimLifecycleEvent` dataclass | 없음 |
| `gaps_for_claim` / `gap_resolution` (PR5) 의미 | 없음 (read-only 활용) |
| `_gap_resolutions` 인덱스 (PR5) | 없음 |
| PR11-D `_STATUS_MODIFIER_*` / `_STATUS_TO_MODIFIER` | 없음 |
| PR11-C `_FRESHNESS_PENALTY_WEIGHT` | 없음 |
| PR10-A `_REFUTATION_STRENGTH_THRESHOLD` | 없음 |
| 5 lifecycle API (PR6~PR10-A) + PR11-B sibling | 없음 |
| `register_contradiction*` | 없음 |
| PR11-A query / PR9-A asc | 없음 |
| `_lifecycle_seq` / `_claim_lifecycle_events` (PR10-B) | 없음 |
| `compute_effective_confidence` 시그니처 | 없음 (본문만 변경) |
| `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 (Sub-decision D 정합) |
| `fire_rule*` / `RuleStats` | 없음 |
| public exports | 없음 (`_GAP_PENALTY_MODIFIER` private) |
| 외부 dependency | 없음 |

PR12-D 는 **`compute_effective_confidence` 본문에 곱셈 1개 추가만**.

### 28.12 Invariants (테스트로 잠금)

1. unknown claim_id → `KeyError` (PR11-D 동작 보존)
2. **gap 0 개 + candidate → effective == base** (gap_modifier = 1.0)
3. **gap 0 개 + confirmed → effective == base** (gap_modifier = 1.0)
4. **gap 0 개 + disputed → effective == base × 0.5** (status × gap 1.0)
5. **gap 0 개 + refuted → effective == 0.0** (status 0)
6. **모든 gap resolved → gap_modifier == 1.0** (effective 변화 없음)
7. **unresolved gap 1+ + candidate → effective == base × 0.8** ★
8. **unresolved gap 1+ + confirmed → effective == base × 0.8** ★
9. **unresolved gap 1+ + disputed → effective == base × 0.5 × 0.8 = base × 0.4** ★
10. **unresolved gap 1+ + refuted → effective == 0.0** (Sub-decision P)
11. **N 무관: unresolved 1개 vs 10개 동일 modifier** (Sub-decision U)
12. **resolved + unresolved 혼재 시 unresolved 1+ → 0.8**
13. PR11-C freshness modifier 결합:
    confirmed + active strong 0.8 + unresolved gap 1+
    → base × 1.0 × 0.6 × 0.8 = base × 0.48
14. **PR5 `gap_resolution` 동작 변경 없음** ★ (입력 활용만)
15. **PR11-C `compute_effective_confidence` 의 freshness_modifier 동작 변경 없음**
16. **PR10-A refute / PR11-B refute_by_freshness 동작 변경 없음**
17. PR11-A query 무변화
18. PR9-A asc 무변화
19. PR11-D `_STATUS_MODIFIER_*` 값 무변화
20. effective ≤ base (no boost — Sub-decision N 정신)
21. compute is read-only (gap / contradictions / lifecycle_history / base 무변화)
22. determinism
23. `_GAP_PENALTY_MODIFIER` private (ragcore + ragcore.types 미노출)
24. 기존 589 회귀 없음 (전체 통과로 입증)

### 28.13 Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| N-dependent gap modifier (`f(N)` 형태) | Sub-decision U (binary, "최소 연결 PR" 정신) |
| Gap 종류별 가중치 (`gap_type` / `severity` / `required_evidence_type`) | 단순화. PR12+ |
| Gap freshness (오래된 gap 의 약한 페널티) | PR12+ 또는 결합 |
| RuleStats modifier (`observed_precision` / `false_positive_rate`) | PR12+ |
| Contradiction count modifier (active 개수 기반 추가 감쇠) | PR12+ |
| Lifecycle history-based modifier | PR12+ |
| `superseded` / `retracted` 추가 상태 | PR12-G 자리 |
| Confidence boost (modifier > 1.0) | PR11-D Sub-decision N 일관 — 영구 OOS |
| Caller-driven modifier / config injection | PR10-A / PR11-D 정신 |
| LLM / semantic confidence | core 밖 |
| Mutable confidence / setter | immutability |
| Public `_GAP_PENALTY_MODIFIER` | engine 내부 private |
| Wall-clock timestamp | PR10-A/B / PR11-A/B/C/D 일관 영구 OOS |
| PR5 `gap_resolution` 정책 변경 | input 활용만 |

### 28.14 Position in flow

```text
PR11-B 까지:
  effective = base × status_modifier × freshness_modifier
  → gap 정보는 effective 에 반영 안 됨
  → caller 가 gap 상태를 보려면 gaps_for_claim 직접 호출 필요

PR12-D:
  effective = base × status × freshness × gap
  → PR5 의 gap_resolution 의미가 effective 에 처음 연결
  → unresolved gap 1+ 시 약한 페널티 (× 0.8)
  → 모든 gap resolved / gap 0 개 시 영향 없음 (× 1.0)
```

구현 단계 (71/72차) — **테스트 먼저 잠금 → 구현** 순서:
- 71차: tests (위 24 invariant) — PR11-C 본문에 gap 적용 안 됨 → gap-affected 시나리오 일부 fail
- 72차: `_GAP_PENALTY_MODIFIER` private constant + `compute_effective_confidence` 본문 확장 (× gap_modifier 추가) — 71차 테스트 통과로 입증
