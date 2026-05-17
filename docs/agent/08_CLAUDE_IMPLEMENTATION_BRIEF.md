# 08. Claude Implementation Brief

Claude에게 구현을 맡길 때 이 문서를 그대로 준다.

---

## Role

너는 전체 프레임워크 설계자가 아니다.

너의 역할은 아래 계약을 지키는 **Core Contract Implementer**다.

초기 MVP는 **Python Reference Core**로 구현한다. 단, 모든 데이터 구조와 함수 경계는 향후 C/Rust hot loop 이식을 전제로 고정한다. C 구현은 판단 루프와 룰 계약이 검증된 뒤, 성능 병목 구간에 한정하여 적용한다.

목표는 "빠른 엔진"이 아니라 **틀리지 않게 판단 흐름이 닫히는 엔진**을 만드는 것이다.

---

## Goal

관계-판단-수치 기반 지능형 RAG 프레임워크의 최소 Reference Core를 구현한다.

초기 목표는 다음 세 가지다.

```text
1. 관계가 만들어진다.
2. 왜 만들어졌는지 rule_id / reason_code가 남는다.
3. 신뢰도와 우선순위가 수치로 계산된다.
```

---

## Hard Constraints

```text
Core 객체에 긴 자연어 저장 금지 (raw_ref_id로만 참조)
모든 연결은 ID 기반
score 의미값은 float 0.0~1.0, 저장 / hot loop에서만 uint16 0~10000으로 패킹 (ScoreValue 래퍼 사용)
원본 데이터는 raw_ref_id로만 참조
도메인 특화 로직은 adapter layer로 분리 (Core에 삽입 금지)
LLM/RAG/Vector DB 연결은 Phase 4 이후
Python dataclass 필드는 C struct 형태로 1:1 대응 가능해야 함
dict / 동적 필드 남발 금지 (계약된 필드만 사용)
판단 결과에는 반드시 rule_id, rule_version, reason_code, trace 정보가 남아야 함
claim_confidence와 rule_reliability는 분리해 저장 (MVP에서는 후자를 null 허용 hook으로)
```

---

## Required Files

Python Reference Core 구조. 파일 경계는 향후 C 이식 시 모듈 경계와 1:1 대응한다.

```text
ragcore/__init__.py
ragcore/types.py          # dataclass mirrors of target C structs
ragcore/engine.py         # Engine lifecycle, ID 할당
ragcore/entity.py
ragcore/observation.py
ragcore/claim.py
ragcore/evidence.py
ragcore/relation.py
ragcore/rule.py           # Rule loader + condition evaluator
ragcore/gap.py
ragcore/score.py
ragcore/memory_gate.py
rules/                    # 도메인/룰 정의 (yaml/json) — 코드 아님
tests/test_core.py
```

---

## Required API

Python Reference Engine은 다음 클래스 인터페이스를 제공한다.

```python
class Engine:
    def add_entity(self, entity_type: int) -> int: ...
    def add_observation(self, entity_id: int, raw_ref_id: int,
                        observation_type: int) -> int: ...
    def add_claim(self, entity_id: int, claim_type: int,
                  rule_id: int, reason_code: int,
                  status: int = CLAIM_STATUS_CANDIDATE) -> int: ...
    def add_evidence(self, claim_id: int, raw_ref_id: int,
                     evidence_type: int, strength: float) -> int: ...
    # strength는 0.0~1.0 의미 계층. 저장 시 ScoreValue.to_uint16_scale()로 변환.
    def add_relation(self, from_kind: int, from_id: int,
                     to_kind: int, to_id: int,
                     relation_type: int,
                     rule_id: int, reason_code: int) -> int: ...
    # from_kind / to_kind는 KIND_* 상수. ID가 kind 독립이므로 두 객체를
    # 가로지르는 링크는 (kind, id) 쌍으로만 명확하다.

    def run_rules(self) -> int: ...
    def get_priority(self, target_id: int) -> int: ...
    def get_confidence(self, target_id: int) -> int: ...
    def is_memory_candidate(self, target_id: int) -> bool: ...
```

### Target C Boundary (이식 목표)

향후 C 이식 시 다음 C ABI로 노출되어야 한다. Python 구현은 이 시그니처와 1:1 호환되어야 한다.

```c
typedef struct Engine Engine;

Engine* engine_create(void);
void engine_free(Engine* e);

uint32_t engine_add_entity(Engine* e, uint16_t entity_type);
uint32_t engine_add_observation(Engine* e, uint32_t entity_id,
                                uint32_t raw_ref_id, uint16_t observation_type);
uint32_t engine_add_claim(Engine* e, uint32_t entity_id, uint16_t claim_type,
                          uint16_t rule_id, uint16_t reason_code, uint16_t status);
uint32_t engine_add_evidence(Engine* e, uint32_t claim_id, uint32_t raw_ref_id,
                             uint16_t evidence_type, uint16_t strength);
uint32_t engine_add_relation(Engine* e,
                             uint8_t from_kind, uint32_t from_id,
                             uint8_t to_kind, uint32_t to_id,
                             uint16_t relation_type,
                             uint16_t rule_id, uint16_t reason_code);

uint32_t engine_run_rules(Engine* e);
uint16_t engine_get_priority(Engine* e, uint32_t target_id);
uint16_t engine_get_confidence(Engine* e, uint32_t target_id);
int engine_is_memory_candidate(Engine* e, uint32_t target_id);
```

---

## MVP Test Scenario

```text
1. Entity 생성
2. Observation 생성 (e.g. port 22 open, banner=OpenSSH_7.4)
3. Rule 실행 — Lifecycle 룰이 Evidence 정규화
4. Domain 룰(RULE_DOMAIN_SSH_001) firing → Claim(status=candidate) 생성 확인
5. 필요 Evidence 미달 → Gap 생성 확인 (required_evidence_type 명시)
6. Evidence 보강 → confidence 상승 확인
7. priority 계산 확인
8. Claim status가 candidate → confirmed 승격되는 조건 확인
9. memory_candidate 여부 확인
```

---

## Output Rule

구현 후 반드시 다음을 설명한다.

```text
파일별 역할
데이터 흐름
ID 할당 / 참조 무결성
테스트 실행 방법
현재 한계
다음 구현 단위
C 이식 시 영향 받는 모듈
```
