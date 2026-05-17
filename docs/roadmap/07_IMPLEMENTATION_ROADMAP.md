# 07. Implementation Roadmap

## Phase 0. 문서 고정

목표:

```text
프로젝트 정체성 고정
C Core 경계 고정
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

## Phase 1. C Core Skeleton

구현 범위:

```text
engine_create / engine_free
entity_add
observation_add
claim_add
evidence_add
relation_add
gap_add
score_get
memory_candidate_check
```

금지:

```text
RAG 연결 금지
LLM 연결 금지
JSON 파서 내장 금지
도메인 로직 삽입 금지
```

완료 조건:

```text
main.c에서 최소 시나리오 실행
테스트 5개 이상 통과
메모리 누수 없음
```

---

## Phase 2. Rule Engine MVP

구현 Rule:

```text
Observation → Claim
Claim without Evidence → Gap
Evidence → Confidence Update
Gap → Action Candidate
Score → Memory Candidate
```

완료 조건:

```text
Rule 실행 전/후 상태가 테스트로 검증된다.
각 생성 결과에 rule_id와 reason_code가 남는다.
```

---

## Phase 3. Python Binding

초기 방식:

```text
ctypes
```

구현 범위:

```text
ragcore.py
Engine class wrapper
add_entity
add_observation
run_rules
get_scores
check_memory_candidate
```

---

## Phase 4. Adapter Layer

구현 범위:

```text
JSON Adapter
Simple File Adapter
SQLite Adapter
```

아직 Vector DB/LLM은 붙이지 않는다.

---

## Phase 5. RAG / LLM 연결

조건:

```text
C Core MVP가 안정화된 이후
Rule / Score / Memory Gate가 테스트로 고정된 이후
```

연결 방향:

```text
C Core → Memory Candidate 산출
Python Adapter → RAG 저장
LLM → 설명 생성
```
