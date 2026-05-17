# Agent Instructions

이 저장소는 관계-판단-수치 기반 지능형 RAG 프레임워크다.

## Core Rule

전체 프레임워크를 한 번에 구현하지 않는다.

먼저 C Core의 닫힌 MVP만 구현한다.

```text
Entity
Observation
Claim
Evidence
Relation
Rule
Gap
Score
Memory Gate
```

## Do Not

```text
초기 MVP에서 LLM 붙이지 말 것
초기 MVP에서 RAG 붙이지 말 것
초기 MVP에서 Graph DB 붙이지 말 것
초기 MVP에서 도메인별 보안 로직 넣지 말 것
C 구조체에 긴 문자열 저장하지 말 것
Python에서 C 내부 구조체를 직접 만지지 말 것
```

## Must

```text
ID 기반 연결
rule_id / reason_code 기록
score는 uint16_t 0~10000
raw data는 raw_ref_id로 참조
테스트 우선 작성
작은 단위 커밋
```

## First Implementation Target

```text
C Core Skeleton + Minimal Rule Engine + Tests
```

자세한 구현 지시는 `docs/agent/08_CLAUDE_IMPLEMENTATION_BRIEF.md`를 따른다.
