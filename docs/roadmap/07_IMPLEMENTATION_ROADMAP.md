# 07. Implementation Roadmap

## Phase 0. 문서 고정

목표:

```text
프로젝트 정체성 고정
Core 경계 고정
MVP 데이터 계약 고정
Claude 구현 지시문 고정
```

완료 조건:

```text
README.md
docs/00~06
AGENTS.md 또는 CLAUDE.md
```

---

## Phase 1. Python Reference Core

목표는 성능 최적화가 아니라 **관계-판단-수치 루프의 검증**이다.

구현 범위:

```text
ragcore.Engine (생성/해제)
add_entity
add_observation
add_claim
add_evidence
add_relation
add_gap
run_rules
get_priority
get_confidence
is_memory_candidate
```

원칙:

```text
dict 남발 금지
동적 필드 남발 금지
명확한 dataclass / Enum 사용
score 계산 함수는 순수 함수
rule input/output 계약 고정
trace / reason_code 반드시 남김
C struct와 1:1 대응 가능한 구조 유지
```

금지:

```text
RAG 연결 금지
LLM 연결 금지
Vector DB 연결 금지
도메인 로직을 Core 코드에 삽입 금지 (룰 정의는 데이터로 외부 로드)
```

완료 조건:

```text
최소 시나리오 1개가 끝까지 실행됨
테스트 5개 이상 통과
모든 Claim/Gap에 rule_id, reason_code 존재
```

---

## Phase 2. Rule Engine MVP

룰은 두 종류로 분리해 구현한다.

### Lifecycle Rules — 엔진 운영 규칙

```text
RULE_LIFE_001 Observation Registration
RULE_LIFE_002 Evidence Normalization
RULE_LIFE_003 Claim-Gap Lifecycle
```

### Judgment Rules — 도메인 판단 규칙

MVP에는 도메인 룰 **최소 1개**를 반드시 포함한다. 추상 룰만 있는 MVP는 판단 빈틈을 노출하지 못한다.

```text
RULE_DOMAIN_SSH_001 SSH Outdated Version Candidate (예시 도메인 룰)
RULE_GAP_001 Required Evidence Gap Detection
RULE_ACTION_001 Gap-to-Check Action Selection
```

도메인 룰은 코드가 아니라 **데이터(yaml/json)** 로 정의하고, Core는 condition 평가 엔진만 제공한다.

완료 조건:

```text
Lifecycle 3개 + Domain 1개 + Gap/Action 룰 각 1개로
관찰 → 증거 → 후보 Claim → Gap → 다음 Action 루프가 닫힌다.
각 생성 결과에 rule_id, reason_code가 남는다.
Claim.status가 candidate → confirmed 로 승격되는 조건이 테스트로 검증된다.
```

---

## Phase 3. Adapter Layer

구현 범위:

```text
JSON Adapter
File Adapter
SQLite Adapter (영속화 — score는 uint16 packing)
```

아직 Vector DB / LLM은 붙이지 않는다.

---

## Phase 4. RAG / LLM 연결

조건:

```text
Reference Core MVP가 안정화된 이후
Rule / Score / Memory Gate가 테스트로 고정된 이후
```

연결 방향:

```text
Core → Memory Candidate 산출
Adapter → RAG 저장
LLM → 설명 생성
```

---

## Phase 5. C/Rust Hot Loop Port

C/Rust 이식은 다음 5개 조건이 **모두** 충족된 뒤에만 시작한다.

```text
1. Evidence / Claim / Gap 구조가 거의 안 바뀐다
2. 룰 firing 계약이 안정됐다
3. 최소 도메인 시나리오가 1개 이상 끝까지 돈다
4. profiler로 병목 구간이 확인됐다
5. Python 구현이 테스트 기준선 역할을 한다
```

이식 대상 (예상 hot loop):

```text
score 계산 반복
claim matching
evidence correlation
rule firing 대량 반복
snapshot serialization
uint16 packing / unpacking
```

원칙:

```text
Python = 판단 구조 검증
C / Rust = 확정된 반복 계산 최적화
```

Python Reference Core는 이식 후에도 **테스트 oracle**로 보존된다.
