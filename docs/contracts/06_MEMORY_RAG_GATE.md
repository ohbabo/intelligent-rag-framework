# 06. Memory / RAG Eligibility Gate

## 1. 원칙

본 프레임워크에서 RAG는 모든 데이터를 저장하지 않는다.

RAG는 원본 저장소가 아니라, 재사용 가능한 판단 흐름 저장소다.

## 2. 저장 후보 조건

Memory Candidate가 되려면 아래 조건을 통과해야 한다.

```text
1. 특정 대상 또는 문제 상황과 연결되어 있는가?
2. 단순 원본 데이터가 아니라 판단 흐름 안에서 의미가 생겼는가?
3. 이후 유사 상황에서 재사용 가능한가?
4. Gap 계산 또는 Action Selection에 영향을 주었는가?
5. 수치 판단 데이터가 함께 존재하는가?
6. 중복 저장 없이 기존 기억과 연결 가능한가?
```

## 3. MVP Gate

초기 구현 기준:

```text
memory_candidate = true if
    priority_score >= 7000
    and evidence_strength >= 6000
    and confidence >= 5000
    and created_by_rule exists
```

## 4. 저장하지 말아야 할 것

```text
근거 없는 자연어 요약
점수 없는 관계
rule_id 없는 판단
raw data 전체 복사본
도메인 전용 임시 로그
재사용 불가능한 단발 이벤트
```

## 5. 저장해야 할 것

```text
관계 묶음
rule_id / reason_code
Gap 종류
Action 후보
Outcome 요약 ID
Score Vector
재사용 이유 memory_reason
```

## 6. RAG Adapter의 역할

Core는 Memory 후보 여부만 계산한다.

실제 저장 방식은 Adapter가 담당한다.

```text
Vector DB Adapter
Graph DB Adapter
SQLite/Postgres Adapter
File-based Knowledge Store
```
