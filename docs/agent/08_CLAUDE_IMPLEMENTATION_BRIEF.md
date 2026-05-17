# 08. Claude Implementation Brief

Claude에게 구현을 맡길 때 이 문서를 그대로 준다.

---

## Role

너는 전체 프레임워크 설계자가 아니다.

너의 역할은 아래 계약을 지키는 C Core 구현자다.

---

## Goal

관계-판단-수치 기반 지능형 RAG 프레임워크의 최소 C Core를 구현한다.

초기 목표는 다음 세 가지다.

```text
1. 관계가 만들어진다.
2. 왜 만들어졌는지 rule_id / reason_code가 남는다.
3. 신뢰도와 우선순위가 수치로 계산된다.
```

---

## Hard Constraints

```text
문자열 직접 저장 금지
모든 연결은 ID 기반
score는 uint16_t 0~10000
원본 데이터는 raw_ref_id로만 참조
malloc 남발 금지
Python이 C 내부 구조체를 직접 만지지 않게 할 것
도메인 특화 로직 금지
LLM/RAG 연결 금지
```

---

## Required Files

```text
include/ragcore.h
src/engine.c
src/entity.c
src/observation.c
src/claim.c
src/evidence.c
src/relation.c
src/rule.c
src/gap.c
src/score.c
src/memory_gate.c
tests/test_core.c
Makefile
```

---

## Required API

```c
typedef struct Engine Engine;

Engine* engine_create(void);
void engine_free(Engine* e);

uint32_t engine_add_entity(Engine* e, uint16_t entity_type);
uint32_t engine_add_observation(Engine* e, uint32_t entity_id, uint32_t raw_ref_id, uint16_t observation_type);
uint32_t engine_add_claim(Engine* e, uint32_t entity_id, uint16_t claim_type, uint16_t rule_id, uint16_t reason_code);
uint32_t engine_add_evidence(Engine* e, uint32_t claim_id, uint32_t raw_ref_id, uint16_t evidence_type, uint16_t strength);
uint32_t engine_add_relation(Engine* e, uint32_t from_id, uint32_t to_id, uint16_t relation_type, uint16_t rule_id, uint16_t reason_code);

uint32_t engine_run_rules(Engine* e);
uint16_t engine_get_priority(Engine* e, uint32_t target_id);
uint16_t engine_get_confidence(Engine* e, uint32_t target_id);
int engine_is_memory_candidate(Engine* e, uint32_t target_id);
```

---

## MVP Test Scenario

```text
1. Entity 생성
2. Observation 생성
3. Rule 실행
4. Claim 생성 확인
5. Evidence가 없으면 Gap 생성 확인
6. Evidence 추가
7. confidence 상승 확인
8. priority 계산 확인
9. memory candidate 여부 확인
```

---

## Output Rule

구현 후 반드시 다음을 설명한다.

```text
파일별 역할
데이터 흐름
메모리 소유권
테스트 실행 방법
현재 한계
다음 구현 단위
```
