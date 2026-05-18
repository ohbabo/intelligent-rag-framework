# PR #002 — Rule Engine MVP

> Status: ready to merge (after Draft PR review).
> Branch: `feat/rule-engine-mvp` → `main`
> Base: `ed83747` (Phase 1 merged)
> Tests: 371 passing (local)

## 목적

Phase 2 Rule Engine MVP. YAML 룰 스펙을 읽고 컴파일해서 Engine 에 등록하고, condition 을 평가해서 (true 일 때) Claim 과 Gaps 를 만들어내는 **첫 실행 가능한 룰 파이프라인**을 닫는다.

핵심은 "각 단계를 별도 모듈 / 별도 contract" 로 분리한 것이다 — header validation, condition 평가, output claim compile, required_evidence compile, runtime firing 이 모두 자기 책임만 진다.

## 닫힌 흐름

```python
engine = Engine()
spec = load_rule_spec_from_yaml(yaml_text)

definition = register_rule_spec(engine, spec)    # Engine 등록 + 빈 RuleStats
condition  = compile_rule_condition(spec)        # ConditionTree
output     = compile_rule_output(spec)           # RuleOutputTemplate
required   = compile_required_evidence(spec)     # RequiredEvidenceTemplate

subject_id = engine.add_entity(entity_type=1)

claim_id = fire_rule(
    engine, definition, condition, output,
    subject_id=subject_id,
    context={"port": 22, "banner": "OpenSSH_7.4p1"},
    required_evidence=required,
)
# → Claim + N Gaps + firing_count +1   (condition true)
# → None                                (condition false, 상태 변화 0)
```

## 들어간 커밋 (20)

| # | SHA | 내용 |
|---|---|---|
| 1 | `3dee22a` | docs: RuleVersion = monotonic uint16 |
| 2 | `55df4ef` | docs: yaml rule id field normalize (`id` vs `rule_id`) |
| 3 | `2b26217` | feat: parse yaml rule spec header → RuleSpec |
| 4 | `0021d86` | fix: harden raw deep copy + blank string validation |
| 5 | `8e73743` | docs: define condition syntax MVP |
| 6 | `b517226` | feat: evaluate structured condition tree |
| 7 | `66e33c0` | fix: tighten condition node shape contract (extra keys 거부) |
| 8 | `cb28396` | feat: compile_rule_condition (RuleSpec → ConditionTree bridge) |
| 9 | `5866158` | docs: define condition trace MVP |
| 10 | `1d88512` | feat: evaluate_condition_with_trace (explain layer) |
| 11 | `c0f9215` | docs: define RuleId mapping MVP |
| 12 | `6abbb4e` | feat: compile_rule_definition |
| 13 | `5ec2184` | feat: register_rule_spec helper |
| 14 | `6ba72eb` | docs: define rule output claim MVP |
| 15 | `25bff1f` | feat: compile_rule_output (RuleOutputTemplate) |
| 16 | `3ff4d72` | feat: fire_rule MVP |
| 17 | `e055e69` | docs: define required evidence gap MVP |
| 18 | `b49b030` | feat: compile_required_evidence |
| 19 | `d1371c1` | feat: fire_rule creates gaps |
| 20 | (this) | docs(dev): PR2 record |

리듬: `docs(contract) → feat 1~2개 → fix 정합성` 반복. 결정점을 코드 직전에 박는 패턴 유지.

## 신규 모듈

| 파일 | 역할 |
|---|---|
| `ragcore/rule_loader.py` | YAML/dict → `RuleSpec` header validation + `compile_rule_condition` bridge |
| `ragcore/condition.py` | `ConditionTree` + `evaluate_condition` (fast path) + `evaluate_condition_with_trace` (explain) |
| `ragcore/rule_compile.py` | `RuleSpec` → `RuleDefinition` (string id/maturity → uint16/uint8) + `register_rule_spec` |
| `ragcore/rule_output.py` | `RuleSpec.raw["output"]["claim"]` → `RuleOutputTemplate` (type/status/base_confidence/reason_code) |
| `ragcore/rule_gap.py` | `RuleSpec.raw["output"]["claim"]["required_evidence"]` → `RequiredEvidenceTemplate` |
| `ragcore/rule_runtime.py` | `fire_rule` — condition 평가 + (true 시) claim/gap 생성 + firing_count +1 |

각 모듈마다 짝지은 test 파일이 추가됨.

## 주요 설계 결정

### RuleVersion = monotonic uint16 정수 (§8.3)

- semver 문자열 (`0.1.0`) 폐기, yaml 정수 사용
- "rule firing behavior version" — 문서 릴리즈 버전 아님
- (rule_id, rule_version) 이 안정적 룰 식별자

### YAML 식별자 필드명 컨벤션 (8차 normalize)

```text
룰 정의 파일:        id           (RuleDefinition.id 와 1:1)
claim generated_by:  rule_id      (Claim 의 출처 표기)
engine 내부 키:      (id, version) 튜플
```

### Condition syntax = structured form (§10)

- 문자열 DSL (`"port == 22"`) 폐기 → `{field, op, value}` 구조화
- Combinators: `all` / `any` (`not` 은 deferred)
- Operators: `eq, ne, lt, le, gt, ge, contains` (7개)
- **Lenient semantics**: missing field / type mismatch → `false` (예외 X)
- **Bool 차단**: numeric op 에서 `True == 1` Python 함정 명시적 거부
- Predicate / combinator 노드의 **extra key 거부** (silent ignore 차단)

### Condition trace = explain layer (§11)

- `evaluate_condition_with_trace` 는 별도 함수, **short-circuit 안 함** (full eval)
- 4종 reason: `MATCH` / `MISMATCH` / `MISSING_FIELD` / `TYPE_MISMATCH`
- `actual_present` 플래그로 명시적 `None` 과 missing 구별
- judgment 아닌 explain layer — RuleStats 에 안 들어감
- `trace.result == evaluate_condition(...)` 동치성 보장

### Naming triangle 보존 (Phase 1 결정 유지)

```text
RuleDefinition.prior_confidence    — 룰 자체의 사전 신뢰도
Claim.base_confidence              — Claim 생성 시점 초기 확신도 (스냅샷, frozen)
compute_effective_confidence       — 종합 확신도 함수 (Phase 1 stub)
```

세 슬롯을 한 곳에 합치지 않음.

### Static mapping table 패턴 (§12 / §13 / §14)

매핑 6개 모두 같은 패턴:

| 매핑 | 위치 | 검증 |
|---|---|---|
| `RULE_ID_MAP` | `rule_compile.py` | uint16 1..65535 |
| `RULE_MATURITY_MAP` | `rule_compile.py` | 상태 상수 집합 |
| `CLAIM_TYPE_MAP` | `rule_output.py` | uint16 1..65535 |
| `CLAIM_STATUS_MAP` | `rule_output.py` | 상태 상수 집합 (status=0 valid) |
| `REASON_CODE_MAP` | `rule_output.py` | uint16 1..65535 |
| `REQUIRED_EVIDENCE_MAP` | `rule_gap.py` | uint16 1..65535 |

- 무결성: 범위 / 중복 / 빈 키 / bool 차단, 모듈 로딩 시 정적 `AssertionError`
- 새 항목 추가는 PR review 로 충돌 검토

### 책임 분리

- `compile_rule_output` 은 4 필드만 (`type, status, base_confidence, reason_code`)
- `required_evidence` 는 별도 함수 `compile_required_evidence` 로 분리 (output template 비대화 방지)
- `subject_id` 는 YAML 안 읽음 — `fire_rule` 호출자가 외부에서 제공 (entity resolver 결정점 분리)
- `compile_rule_definition` (rule_compile.py) ↔ `compile_rule_condition` (rule_loader.py) ↔ `compile_rule_output` (rule_output.py) — 각 책임 모듈 분리

### Fail-fast

- `fire_rule` 은 미등록 rule → 즉시 `KeyError` (claim 생성 전)
- 부분 mutation 방지 — claim 만 만들어지고 stats 업데이트 실패하는 일 없음

### Gap 생성 정책 (§14)

- `Gap.claim_id` 로 명시적 link (Gap struct 의 기존 슬롯 사용)
- 단일 GapType: `GAP_TYPE_MISSING_EVIDENCE`
- severity 고정 default 0.5 (차별화는 별도 결정점)
- dedup 안 함 (MVP) — yaml 에 중복 evidence → 중복 Gap

## 테스트

371 passing in ~0.4s

| 파일 | 테스트 수 | 범위 |
|---|---|---|
| `test_condition.py` | 88 | load + evaluate + trace |
| `test_rule_loader.py` | 52 | header + condition bridge |
| `test_rule_output.py` | 56 | output template + maps |
| `test_rule_compile.py` | 35 | RuleDefinition compile + register |
| `test_rule_runtime.py` | 34 | fire_rule (16차 + 19차) |
| `test_rule_gap.py` | 29 | required_evidence template |
| Phase 1 tests | 77 | 변경 없음 (engine_basic / relations / relation_gap / rules) |

총 신규 +294, 기존 77 → 371.

## Out of Scope

이 PR 에서 의도적으로 안 한 것:

- **Entity resolver** — `subject_id` 는 caller 책임
- **Trace-returning fire_rule** — `fire_rule` 은 `claim_id | None` 만, trace 는 별도 helper (다음 PR)
- **Gap dedup / merge** — 중복 evidence_types → 중복 Gap (의도)
- **Gap severity 차별화** — per-evidence severity yaml 표기 미지원
- **다양한 GapType** — `MISSING_EVIDENCE` 외 (STALE, AMBIGUOUS 등)
- **다중 claim 출력** — 룰 하나 firing → claim 하나
- **`reason_code` list** — 단일 reason_code 만
- **Claim 승격 logic** — `candidate → confirmed/refuted` 자동 전이 없음
- **`not` combinator** — `all` / `any` 만
- **Nested field access** — context 는 flat dict, dot notation 미지원
- **Regex / 산술식 / Custom functions**
- **변수 binding / cross-evidence join**
- **Trace 직렬화 / pretty-printer**
- **외부 rule registry / hot reload** — static map only
- **룰 yaml 폴더 자동 스캔** — `register_rule_spec` 수동 호출
- **Batch firing**
- **C/Rust hot loop port** — Phase 5

## 다음 PR 후보

| 후보 | 내용 | 우선도 추정 |
|---|---|---|
| A | Trace-returning `fire_rule_with_trace` | 중 |
| B | Gap dedup / merge (multi-rule 합치기) | 중 |
| C | Required evidence → Action 연결 | 낮음 (도구 매핑 결정점 필요) |
| D | Claim 승격 logic (evidence 채워지면 candidate → confirmed) | 높음 (실제 활용 가치) |
| E | Engine bulk fire (등록된 모든 룰을 context 에 일괄 평가) | 중 |
| F | `not` combinator + nested field access | 중 |
| G | C/Rust hot loop port (Phase 5) | 낮음 (5개 조건 충족 후) |

다음 PR 의 첫 결정점은 사용자 선택.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md) — 출처 + 용어 충돌 방지
- [docs/contracts/04_C_CORE_BOUNDARY.md](../contracts/04_C_CORE_BOUNDARY.md) — 이식 목표 계약
- [docs/contracts/05_DATA_CONTRACT_MVP.md](../contracts/05_DATA_CONTRACT_MVP.md) — Phase 2 결정점 §§8.3 / 10 / 11 / 12 / 13 / 14 추가
- [docs/agent/08_CLAUDE_IMPLEMENTATION_BRIEF.md](../agent/08_CLAUDE_IMPLEMENTATION_BRIEF.md) — Engine API surface
- [docs/roadmap/07_IMPLEMENTATION_ROADMAP.md](../roadmap/07_IMPLEMENTATION_ROADMAP.md) — Phase 1~5
- [docs/dev/PR_001_PYTHON_REFERENCE_CORE_MVP.md](PR_001_PYTHON_REFERENCE_CORE_MVP.md) — Phase 1 record (base for this PR)

## How to Run

```bash
git checkout feat/rule-engine-mvp
pip install -e .
pytest -v
```

371 tests in ~0.4s. External deps: `PyYAML>=6.0` (Phase 2 추가).
