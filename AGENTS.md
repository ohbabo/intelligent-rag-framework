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
rule_id / reason_code 기록 (Claim은 generated_by.rule_id + rule_version 포함)
score 의미값은 float 0.0~1.0, 저장은 uint16 0~10000 (두 계층 분리)
raw data는 raw_ref_id로 참조
rule_reliability 필드 자리 예약 (MVP에서는 null 가능)
테스트 우선 작성
작은 단위 커밋
```

## First Implementation Target

```text
Python Reference Core + Minimal Rule Engine + Tests
```

초기 MVP는 Python으로 구현한다. 단, 모든 데이터 구조와 함수 경계는 향후 C/Rust hot loop 이식을 전제로 고정한다. C 구현은 판단 루프와 룰 계약이 검증된 뒤, 성능 병목 구간에 한정하여 적용한다.

자세한 구현 지시는 `docs/agent/08_CLAUDE_IMPLEMENTATION_BRIEF.md`를 따른다.
