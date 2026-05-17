# 02. Layer Model

본 프레임워크는 세 계층을 분리한다.

```text
[1층] 관계 데이터 계층
- 무엇과 무엇이 연결되었는가?

[2층] 지능 판단 데이터 계층
- 왜 그렇게 연결되었는가?

[3층] 수치 판단 데이터 계층
- 그 연결과 판단을 얼마나 신뢰하고 어떤 우선순위로 처리할 것인가?
```

---

## 1. Relation Layer

관계 계층은 객체 간 연결을 표현한다.

기본 객체:

```text
Entity
Observation
Claim
Evidence
Context
Reference Signal
Gap
Action
Outcome
Memory Candidate
```

기본 관계:

```text
Entity       ← observed_about       Observation
Observation  → supports_candidate   Claim
Evidence     → supports             Claim
Claim        → requires             Gap
Gap          → suggests             Action
Action       → produces             Outcome
Outcome      → updates              Relation
Outcome      → creates              Memory Candidate
```

---

## 2. Judgment Layer

판단 계층은 관계가 생긴 이유를 기록한다.

기본 필드:

```text
rule_id
reason_code
condition_snapshot_id
decision_trace_id
gap_type
action_reason
memory_reason
```

이 계층이 없으면 단순 관계형 DB다.

이 계층이 있어야 다음이 가능하다.

```text
설명 가능성
재계산 가능성
디버깅 가능성
Agent Action 선택
Memory 축적 기준 판단
```

---

## 3. Numeric Layer

수치 계층은 판단의 강도와 우선순위를 계산한다.

기본 점수:

```text
confidence
relevance_score
freshness_score
importance_score
priority_score
similarity_score
evidence_strength
action_fit_score
memory_value_score
```

수치는 두 계층으로 분리한다.

```text
의미 계층: float 0.0 ~ 1.0  (계산, 임계값, 디버깅)
저장 계층: uint16 0 ~ 10000 (DB, 직렬화, C/Rust hot loop, 대량 matrix 처리)
```

Core 내부 계산은 float로 수행하고, 저장 시에만 정수 스케일로 변환한다.

```text
0.0000 → 0
0.5000 → 5000
1.0000 → 10000
```

두 계층을 섞지 않는다. 룰 튜닝 단계에서 0.72를 7200으로 변환해가며 디버깅하지 않는다.

---

## 4. 계층 분리 기준

```text
Relation Data
→ 무엇이 연결되었는가

Judgment Data
→ 왜 연결되었는가

Numeric Data
→ 얼마나 믿고 어떤 순서로 처리할 것인가
```
