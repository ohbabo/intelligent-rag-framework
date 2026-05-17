# 관계-판단-수치 기반 지능형 RAG 프레임워크

> **Status**: archived original design memo. 정식 문서는 `docs/00~09`. 이 노트는 프로젝트 분리 시점의 사고 흐름을 보존하기 위해 그대로 둔다.

## 1. 문서 목적

본 문서는 켈베로스 보안 도메인 문서가 아니라, 별도의 범용 AI Agentic RAG 프레임워크 프로젝트 문서다.

이 프레임워크는 특정 도메인의 데이터를 단순히 저장하거나 검색하는 RAG 구조가 아니다. 새로운 데이터가 들어왔을 때, 해당 데이터가 어떤 대상과 연결되는지, 어떤 규칙에 의해 새로운 판단 데이터로 확장되는지, 그 판단을 어느 정도 신뢰할 수 있는지, 그리고 이후 어떤 행동 또는 장기 기억으로 이어질지를 계산하는 구조를 목표로 한다.

따라서 본 프레임워크의 핵심은 다음 세 가지를 분리해 관리하는 데 있다.

```text
1. 관계 데이터
2. 지능 판단 데이터
3. 수치 판단 데이터
```

이 세 계층은 독립적으로 존재하지 않는다. 관계 데이터는 판단의 대상이 되고, 지능 판단 데이터는 관계가 확장된 이유를 설명하며, 수치 판단 데이터는 해당 판단의 신뢰도와 우선순위를 계산한다.

---

## 2. 프로젝트 정체성

이 프레임워크는 보안 진단 도구 자체가 아니다.

보안, 교육, 연구, 비즈니스, 의료, 법률, 운영 자동화 등 여러 도메인에 적용할 수 있는 범용 판단 프레임워크다. 각 도메인은 별도의 Adapter로 연결되며, 프레임워크의 본체는 관계, 판단, 수치, 행동 선택, 기억 축적의 공통 구조를 담당한다.

```text
Framework Core
→ 범용 관계-판단-수치 처리 구조

Domain Adapter
→ 보안, 교육, 연구, 비즈니스 등 도메인별 데이터 변환

Action Adapter
→ 도구 실행, 검색, 질의, 보고서 생성, 검증 등 행동 연결

Memory / RAG Layer
→ 재사용 가능한 판단 흐름과 지식 패턴 축적
```

켈베로스는 이 프레임워크를 보안 진단 도메인에 적용하는 하나의 구현 사례가 될 수 있다. 그러나 본 문서의 중심은 켈베로스가 아니라 범용 프레임워크 자체다.

---

## 3. 기존 RAG 구조와의 차이

일반적인 RAG 구조는 외부 문서나 데이터를 벡터화한 뒤, 사용자의 질문과 유사한 문서를 검색해 LLM의 답변을 보강한다.

```text
Document
→ Chunk
→ Embedding
→ Vector Search
→ LLM Answer
```

하지만 본 프레임워크는 단순 문서 검색 중심 RAG가 아니다.

본 프레임워크는 데이터가 들어왔을 때 다음 질문을 먼저 다룬다.

```text
이 데이터는 어떤 대상과 연결되는가?
이 데이터는 기존 관계를 확장하는가?
그 확장은 어떤 규칙에 의해 발생했는가?
현재 판단에 부족한 정보는 무엇인가?
다음 행동은 무엇이어야 하는가?
이 흐름은 장기 기억으로 저장할 가치가 있는가?
```

즉, 본 프레임워크에서 RAG는 단순 저장소가 아니라, 관계·판단·수치 계산을 거친 뒤 재사용 가치가 있는 흐름만 축적하는 기억 계층이다.

---

## 4. 핵심 철학

본 프레임워크는 데이터를 무조건 축적하지 않는다.

새로운 데이터는 기존 대상, 관찰, 주장, 증거, 판단 상태와의 관계 안에서 의미를 가진다. 데이터가 저장되기 위해서는 단순히 존재하는 것만으로는 충분하지 않다. 해당 데이터가 어떤 규칙에 의해 확장되었고, 어떤 판단 Gap을 만들거나 줄였으며, 어떤 행동 선택 또는 장기 기억으로 연결되는지가 추적 가능해야 한다.

핵심 문장은 다음과 같다.

```text
본 프레임워크는 “무엇을 저장했는가”보다
“어떤 근거와 규칙 때문에 이 데이터가 다음 판단 데이터로 확장되었는가”를 더 중요하게 다룬다.
```

---

## 5. 전체 구조 개요

본 프레임워크는 세 개의 주요 계층으로 구성된다.

```text
[1층] 관계 데이터 계층
- 무엇과 무엇이 연결되었는가?

[2층] 지능 판단 데이터 계층
- 왜 그렇게 연결되었는가?

[3층] 수치 판단 데이터 계층
- 그 연결과 판단을 얼마나 신뢰하고, 어떤 우선순위로 처리할 것인가?
```

이 세 계층은 루프형으로 동작한다.

```text
Raw Input
→ Observation
→ Claim
→ Evidence
→ Rule-based Expansion
→ Gap Calculation
→ Action Candidate
→ Numeric Scoring
→ Action Selection
→ Outcome
→ Relation Update
→ Memory / RAG Eligibility Check
```

---

## 6. 1층: 관계 데이터 계층

관계 데이터 계층은 프레임워크 안에서 어떤 객체들이 서로 연결되어 있는지를 표현한다.

범용 개념은 다음과 같다.

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

도메인별 객체는 달라질 수 있다.

```text
교육 도메인:
Student → Concept → Exercise Result → Weakness → Next Practice

연구 도메인:
Paper → Claim → Method → Evidence → Limitation → Follow-up Question

비즈니스 도메인:
Customer → Event → Need → Proposal → Response → Next Action

보안 도메인:
Asset → Service → Evidence → Risk Signal → Verification Action
```

도메인 객체는 달라도 공통 구조는 유지된다.

```text
대상 식별
→ 관찰
→ 주장 생성
→ 증거 연결
→ 참조 신호 연결
→ 부족한 정보 계산
→ 다음 행동 선택
→ 결과 반영
→ 기억 축적 여부 판단
```

---

## 7. 2층: 지능 판단 데이터 계층

지능 판단 데이터 계층은 관계가 왜 생겼는지를 기록한다.

관계 데이터가 다음 질문에 답한다면:

```text
무엇과 무엇이 연결되었는가?
```

지능 판단 데이터는 다음 질문에 답한다.

```text
왜 이 관계가 생겼는가?
왜 이 데이터가 다음 데이터로 확장되었는가?
왜 아직 판단이 부족한가?
왜 이 행동을 선택해야 하는가?
왜 이 흐름을 장기 기억으로 남겨야 하는가?
```

기본 구성 요소는 다음과 같다.

```text
rule_id
reason_code
condition_snapshot
decision_trace
gap_type
action_reason
memory_reason
```

이 계층이 없으면 프레임워크는 단순 관계형 DB에 머문다. 이 계층이 있어야 데이터 확장 과정이 설명 가능하고, 재계산 가능하며, Agent의 다음 행동 선택으로 이어질 수 있다.

---

## 8. 3층: 수치 판단 데이터 계층

수치 판단 데이터 계층은 관계와 판단의 강도, 신뢰도, 우선순위를 계산한다.

기본 수치 요소는 다음과 같다.

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

도메인별로 수치 요소는 달라질 수 있다.

```text
교육 도메인:
understanding_score, error_rate, review_interval

연구 도메인:
citation_strength, methodological_confidence, novelty_score

비즈니스 도메인:
conversion_probability, urgency_score, customer_temperature

보안 도메인:
risk_score, exposure_score, exploit_likelihood
```

중요한 점은 수치 데이터가 관계 데이터 안에 섞여 들어가는 것이 아니라, 별도 판단 계층으로 관리되어야 한다는 것이다.

```text
관계 데이터
→ 무엇이 연결되었는가

지능 판단 데이터
→ 왜 연결되었는가

수치 판단 데이터
→ 얼마나 신뢰하고 어떤 우선순위로 처리할 것인가
```

---

## 9. 루프형 확장 구조

본 프레임워크는 한 번 저장하고 끝나는 정적 구조가 아니다.

새로운 데이터가 들어오면 기존 관계와 판단 상태가 다시 평가된다.

```text
새 Observation 발생
→ 기존 Claim과 연결 가능성 계산
→ Rule 기반 확장 여부 판단
→ Gap 갱신
→ Action 후보 재계산
→ Numeric Score 갱신
→ Outcome 반영
→ Memory 저장 여부 재평가
```

따라서 본 프레임워크는 일반적인 ERD와 다르다.

일반 ERD는 주로 다음 관계를 표현한다.

```text
A has B
B belongs to C
C produces D
```

본 프레임워크는 다음을 함께 표현한다.

```text
A가 왜 B로 확장되었는가?
그 확장은 어떤 규칙을 통과했는가?
그 판단은 얼마나 신뢰 가능한가?
그 결과 어떤 Gap이 생겼는가?
다음 행동은 무엇인가?
이 흐름은 장기 기억으로 남길 가치가 있는가?
```

---

## 10. Memory / RAG Eligibility Gate

본 프레임워크에서 RAG는 모든 데이터를 저장하지 않는다.

RAG 또는 장기 기억에 저장되기 위해서는 별도의 Eligibility Gate를 통과해야 한다.

기본 조건은 다음과 같다.

```text
1. 특정 대상 또는 문제 상황과 연결되어 있는가?
2. 단순 원본 데이터가 아니라 판단 흐름 안에서 의미가 생겼는가?
3. 이후 유사 상황에서 재사용 가능한가?
4. Gap 계산 또는 Action Selection에 영향을 주었는가?
5. 수치 판단 데이터가 함께 존재하는가?
6. 중복 저장 없이 기존 기억과 연결 가능한가?
```

이 조건을 통과한 데이터만 Memory / RAG Layer로 이동한다.

---

## 11. 프레임워크의 최소 실행 흐름

초기 구현은 작게 닫아야 한다.

최소 흐름은 다음과 같다.

```text
1. Raw Input 수집
2. Observation 생성
3. Claim 생성
4. Evidence 연결
5. Rule 기반 확장
6. Gap 계산
7. Action 후보 생성
8. Numeric Scoring
9. Action 선택 이유 기록
10. Outcome 반영
11. Memory 저장 여부 판단
```

처음부터 모든 도메인, 모든 규칙, 모든 기억 구조를 구현하지 않는다.

초기 목표는 다음 세 가지다.

```text
관계가 만들어지는 것
관계가 만들어진 이유가 기록되는 것
그 관계의 신뢰도와 우선순위가 수치로 계산되는 것
```

이 세 가지가 닫히면 프레임워크의 핵심 뼈대가 완성된다.

---

## 12. 도메인 적용 방식

도메인 적용은 Core를 수정하는 방식이 아니라 Adapter를 추가하는 방식으로 진행한다.

```text
Framework Core
- Entity / Observation / Claim / Evidence / Gap / Action / Memory 구조 관리
- Rule Engine
- Numeric Scoring
- Memory Eligibility
- Relation Update Loop

Domain Adapter
- 도메인 원본 데이터를 Observation / Claim / Evidence로 변환
- 도메인별 Reference Signal 연결
- 도메인별 Numeric Feature 제공

Action Adapter
- 도메인별 행동 실행
- 검색, 도구 호출, 질의, 보고서 생성, 검증 등

Memory Adapter
- RAG, Knowledge Graph, Vector DB, Relational DB 등 저장소 연결
```

---

## 13. 이 프레임워크가 해결하려는 문제

기존 RAG 시스템은 보통 데이터를 잘 검색하는 데 집중한다.

하지만 실제 AI Agent가 필요한 것은 단순 검색이 아니다.

```text
무엇을 알고 있는가?
무엇을 모르는가?
왜 다음 행동이 필요한가?
어떤 정보가 더 필요한가?
어떤 행동이 가장 적합한가?
어떤 경험을 장기 기억으로 남길 것인가?
```

본 프레임워크는 이 질문들을 관계, 판단, 수치, 기억 계층으로 분리해 계산하려는 구조다.

---

## 14. 한 줄 정의

```text
관계-판단-수치 기반 지능형 RAG 프레임워크는
데이터가 왜 확장되었고, 얼마나 믿을 수 있으며,
다음 행동과 장기 기억으로 어떻게 이어질지를 계산하는
범용 AI Agent 판단 프레임워크다.
```

---

## 15. 현재 결론

이 프레임워크는 특정 보안 프로젝트 내부 문서로 묶으면 안 된다.

보안은 하나의 적용 도메인일 뿐이며, 프레임워크의 본질은 다음 구조에 있다.

```text
관계 데이터
+ 지능 판단 데이터
+ 수치 판단 데이터
+ 규칙 기반 확장
+ Gap 계산
+ Action Selection
+ Memory / RAG 축적 판단
```

따라서 별도 프레임워크 프로젝트로 분리하고, 이후 각 도메인은 Adapter 형태로 붙이는 것이 맞다.
