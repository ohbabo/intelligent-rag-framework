# PR #001 — Python Reference Core MVP

> Status: ready to merge.
> Branch: `feat/python-core-mvp` → `main`
> Tests: 77 passing (local)

## 목적

Intelligent RAG Framework Phase 1의 판단 코어 자료구조와 Engine API surface를 닫는다. Rule Engine 구현 전, 모든 후속 PR이 의존할 최소 인터페이스를 고정한다.

이 PR은 "판단 수식"을 결정하지 않는다 — 자료구조와 슬롯만 잡고, 실제 scoring 로직은 다음 PR에서 명시적으로 들어온다.

## 들어간 커밋

| # | SHA | 내용 | 추가 테스트 |
|---|---|---|---|
| 1 | `279a032` | Engine + Entity + ScoreValue 골격 | +18 |
| 2 | `c71a737` | Observation / Claim / Evidence / Relation / Gap dataclass + 3개 add API | +16 |
| 3 | `f0e5ac4` | Relation / Gap engine 연결 + 최소 루프 end-to-end | +14 |
| 4 | `2931818` | **Relation kind-aware (BREAKING)** — from_kind / to_kind 도입 | +4 |
| 5 | `26fbe3e` | Claim.base_confidence + RuleDefinition / RuleStats registry | +21 |
| 6 | `3ce1044` | compute_effective_confidence stub + doc 08 sync | +4 |

총 **77 tests passing**.

## 변경된 핵심 구조

### dataclass (모두 `frozen=True`)

| 타입 | 필드 |
|---|---|
| `Entity` | id, type, flags |
| `Observation` | id, entity_id, raw_ref_id, type, source_type |
| `Claim` | id, subject_id, type, status, created_by_rule, created_by_rule_version, reason_code, **base_confidence**, flags |
| `Evidence` | id, claim_id, raw_ref_id, type, strength |
| `Relation` | id, **from_kind, from_id, to_kind, to_id**, type, rule_id, reason_code |
| `Gap` | id, claim_id, type, required_evidence_type, severity, created_by_rule |
| `ScoreValue` | value (float 0.0~1.0, packing/unpacking 함수 동봉) |
| `RuleDefinition` | id, version, maturity, prior_confidence |
| `RuleStats` | rule_id, rule_version, firing_count, confirmed_true_count, confirmed_false_count, observed_precision, false_positive_rate |

### 상수

- `KIND_ENTITY` (1) / `KIND_OBSERVATION` (2) / `KIND_CLAIM` (3) / `KIND_EVIDENCE` (4) / `KIND_RELATION` (5) / `KIND_GAP` (6)
- `CLAIM_STATUS_CANDIDATE` (0) / `CLAIM_STATUS_CONFIRMED` (1) / `CLAIM_STATUS_REFUTED` (2)
- `RULE_MATURITY_EXPERIMENTAL` (0) / `RULE_MATURITY_STABLE` (1) / `RULE_MATURITY_DEPRECATED` (2)

### Engine API surface

```text
add_entity / get_entity
add_observation / get_observation
add_claim / get_claim
add_evidence / get_evidence / evidences_for_claim
add_relation / get_relation
add_gap / get_gap / gaps_for_claim
register_rule / get_rule / get_rule_stats / update_rule_stats
compute_effective_confidence (MVP stub)
```

## 주요 설계 결정

### 1. Python-first, C는 Phase 5

초기 MVP는 Python Reference Core로 구현. C/Rust hot loop port는 다음 5가지 조건이 **모두** 충족된 뒤에만 시작한다.

```text
1. Evidence / Claim / Gap 구조 안정화
2. 룰 firing 계약 안정화
3. 최소 도메인 시나리오 end-to-end 동작
4. profiler 병목 확인
5. Python 구현이 test oracle 역할
```

### 2. Score 의미 계층 ↔ 저장 계층 분리

```text
의미 계층:  float 0.0 ~ 1.0  (계산, 임계값, 디버깅)
저장 계층:  uint16 0 ~ 10000 (DB, 직렬화, hot loop)
```

`ScoreValue.to_uint16_scale()` / `from_uint16_scale()` 가 변환 담당. 룰 튜닝 단계에서 0.72를 7200으로 환산해가며 디버깅하지 않는다.

### 3. ID는 kind 독립

Engine의 ID 발급은 kind별 단조 증가 카운터를 쓴다. 따라서:

```text
entity:1, claim:1, evidence:1 모두 동시 존재 가능
같은 정수 1 이지만 서로 다른 객체
```

### 4. Relation은 kind-aware (commit 4의 BREAKING change)

ID가 kind 독립이므로 Relation은 id만 저장하면 "entity → claim 이었는지 claim → evidence 였는지" 구분되지 않는다. 그래서 Relation은 반드시 `(from_kind, from_id)` + `(to_kind, to_id)` 쌍을 저장한다.

- 잘못된 kind → `ValueError`
- 해당 kind에 id 없음 → `KeyError`

이 결정은 GPT 검수에서 짚힌 모호성 (`_id_exists_anywhere`가 polymorphic ID를 너무 느슨하게 허용)을 막기 위함.

### 5. Naming triangle — confidence 3슬롯 절대 분리

이 PR의 가장 중요한 설계 결정.

```text
RuleDefinition.prior_confidence
  = 룰 자체의 사전 신뢰도
  = 룰 등록 시 고정, 운영 통계와 무관

Claim.base_confidence
  = Claim 생성 시점의 초기 확신도 (firing 스냅샷)
  = frozen, 이후 evidence/stats가 와도 변하지 않음

compute_effective_confidence(claim_id)
  = 현재 종합 확신도 (base + evidence + RuleStats 조합)
  = 함수로만 노출, 저장 슬롯 없음
  = MVP에서는 base_confidence 그대로 반환하는 stub
```

세 슬롯을 같은 곳에 합치면:
- evidence 갱신이 룰 정의를 흔든다
- 룰 통계 갱신이 Claim 스냅샷을 오염시킨다

이름이 `Claim.confidence` 단독이 아닌 `Claim.base_confidence` 인 것도 같은 이유 — "현재 종합" 처럼 읽히는 함정을 차단.

### 6. RuleDefinition / RuleStats 분리

룰의 정의와 운영 통계를 같은 구조체에 섞지 않는다.

```text
RuleDefinition (frozen)  = 등록 시 고정, 시간에 따라 변하지 않음
RuleStats (frozen)       = 통계 누적 시 새 인스턴스로 교체 (mutate 금지)
```

`Engine.update_rule_stats(...)` 는 기존 RuleStats를 mutate 하지 않고 새 인스턴스로 dict 에 교체한다. precision/fpr 인자가 `None` 이면 "변경 안 함" (nullify 아님).

### 7. compute_effective_confidence는 의도된 stub

```python
def compute_effective_confidence(self, claim_id: int) -> ScoreValue:
    # MVP stub: base_confidence 그대로 반환.
    # Phase 2+에서 evidence_strength 와 RuleStats(observed_precision / FPR) 조합.
    return self._claims[claim_id].base_confidence
```

테스트가 이 행동을 명시적으로 잠그고 있다 (`TestComputeEffectiveConfidence`). 다음 PR에서 logic이 들어오면 이 테스트가 가이드로 동작한다.

### 8. Rule registry는 MVP advisory

`add_claim(rule_id, rule_version, ...)` 이 등록된 룰만 허용하는지 MVP에서는 강제하지 않는다. 테스트와 초기 실험 부담을 줄이기 위함. Rule Engine 단계에서 strict mode 옵션이 들어온다.

## 테스트

```text
77 passed in ~0.1s
```

| 파일 | 테스트 수 | 범위 |
|---|---|---|
| `tests/test_engine_basic.py` | 18 | Entity + ScoreValue (bounds, packing, immutability) |
| `tests/test_engine_relations.py` | 16 | Observation / Claim / Evidence add + linkage |
| `tests/test_engine_relation_gap.py` | 18 | Relation kind-aware / Gap / 최소 루프 end-to-end |
| `tests/test_engine_rules.py` | 25 | Claim.base_confidence / RuleDefinition / RuleStats / naming triangle / stub |

## Out of Scope (이 PR에서 의도적으로 안 함)

- YAML rule loader
- condition evaluator
- `RULE_LIFE_001` / `RULE_LIFE_002` / `RULE_LIFE_003`
- `RULE_DOMAIN_SSH_001`
- strict rule registry mode
- 실제 effective confidence 계산 (현재는 stub)
- priority calculation
- memory gate
- Claim status 승격 logic (`candidate → confirmed`)
- RAG / Vector DB / LLM 연결
- C/Rust hot loop port

## 다음 PR (`feat/rule-engine-mvp`) 작업 순서

먼저 정해야 할 결정점:

1. **RuleVersion 변환 규칙** — yaml `version: 0.1.0` (semver) ↔ Python `rule_version: int` / C `uint16_t RuleVersion` 매핑 규칙
   - 후보: `0.1.0 → 10`, `1.2.3 → 10203` (major\*10000 + minor\*100 + patch)
   - 후보: MVP는 `version: 1` 같은 단순 정수만 허용

그 다음 구현 순서:

2. YAML rule loader
3. condition evaluator (`port == 22`, `banner contains "OpenSSH_7."` 같은 식 평가)
4. lifecycle rules:
   - `RULE_LIFE_001` Observation Registration
   - `RULE_LIFE_002` Evidence Normalization
   - `RULE_LIFE_003` Claim-Gap Lifecycle
5. 도메인 룰 한 개 (추상화 빈틈 검증용):
   - `RULE_DOMAIN_SSH_001` SSH Outdated Version Candidate

## 후속 정리 항목 (PR #002 이후 언제든)

- `update_rule_stats` 음수 delta 방어 — 현재 검증 없음, monotonic 깨질 수 있음
- Claim status `candidate → confirmed` 승격 조건 정의
- `compute_effective_confidence` 실제 logic
- AGENTS.md / docs/agent/08 의 "C struct 형태로 1:1 대응" 표현 정리 (현재 의미는 맞지만 C-first 인상을 줄 수 있음)

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md) — 켈베로스 출처 + 용어 충돌 방지
- [docs/01_CORE_PHILOSOPHY.md](../01_CORE_PHILOSOPHY.md) — 저장보다 확장 이유
- [docs/02_LAYER_MODEL.md](../02_LAYER_MODEL.md) — Relation / Judgment / Numeric 3계층
- [docs/03_RUNTIME_LOOP.md](../03_RUNTIME_LOOP.md) — 기본 루프 + 재평가 루프
- [docs/contracts/04_C_CORE_BOUNDARY.md](../contracts/04_C_CORE_BOUNDARY.md) — 이식 목표 계약
- [docs/contracts/05_DATA_CONTRACT_MVP.md](../contracts/05_DATA_CONTRACT_MVP.md) — Kind / Claim / RuleDefinition / RuleStats 출처
- [docs/contracts/06_MEMORY_RAG_GATE.md](../contracts/06_MEMORY_RAG_GATE.md) — Memory Eligibility 원칙
- [docs/agent/08_CLAUDE_IMPLEMENTATION_BRIEF.md](../agent/08_CLAUDE_IMPLEMENTATION_BRIEF.md) — Engine API surface (코드와 일치)
- [docs/roadmap/07_IMPLEMENTATION_ROADMAP.md](../roadmap/07_IMPLEMENTATION_ROADMAP.md) — Phase 1~5 + C 이식 5개 조건

## How to Run

```bash
git checkout feat/python-core-mvp
pip install -e .
pytest -v
```

77 tests in ~0.1s, no external dependencies (pytest only).
