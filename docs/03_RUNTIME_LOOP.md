# 03. Runtime Loop

## 1. 기본 루프

프레임워크는 한 번 저장하고 끝나는 정적 구조가 아니다.

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

## 2. 재평가 루프

새로운 데이터가 들어오면 기존 관계와 판단 상태가 다시 평가된다.

```text
New Observation
→ Existing Claim 연결 가능성 계산
→ Rule 기반 확장 여부 판단
→ Gap 갱신
→ Action 후보 재계산
→ Numeric Score 갱신
→ Outcome 반영
→ Memory 저장 여부 재평가
```

## 3. 일반 ERD와의 차이

일반 ERD는 주로 소유와 참조를 표현한다.

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

## 4. MVP 루프

초기 구현은 아래만 닫는다.

```text
Entity 생성
Observation 생성
Claim 후보 생성
Evidence 연결
Gap 생성
Score 계산
Action 후보 생성
Memory 후보 판정
```

이후 RAG, LLM, Graph DB는 외부 Adapter로 붙인다.
