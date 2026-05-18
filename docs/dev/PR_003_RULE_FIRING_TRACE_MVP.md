# PR #003 — Rule Firing Trace MVP

> Status: ready to merge (after Draft PR review).
> Branch: `feat/rule-trace-mvp` → `main`
> Base: `0626ca5` (Phase 2 merged)
> Tests: 394 passing (local)

## 목적

YAML-driven rule runtime 에 firing trace 를 붙인다. **기능 확장 아님** — 기존 `fire_rule` 의미를 깨지 않고 "왜 발화/미발화 했는가" 를 추적 가능하게 만드는 것이 목표.

이번 PR 의 성공 기준은 "trace 를 예쁘게 만들기" 가 아니라 **기존 firing 의미를 계약으로 고정한 상태에서 추적 슬롯만 붙이는 것**.

## 닫힌 흐름 (PR3 추가분)

```python
trace = fire_rule_with_trace(
    engine, definition, condition, output,
    subject_id=subject_id,
    context=ctx,
    required_evidence=required,
)

# trace 가 답하는 것:
#   trace.rule_id, trace.rule_version    — 어떤 룰
#   trace.subject_id                     — 어떤 subject
#   trace.fired                          — 발화됐는가
#   trace.condition_trace                — 왜 발화/미발화 (각 predicate reason)
#   trace.claim_id                       — 생성된 Claim
#   trace.gap_ids                        — 생성된 Gaps
```

기존 `fire_rule` 은 **시그니처/반환값/side effect/예외 동작 모두 변경 없음** — 16/19차 호출자 코드 한 줄도 안 깨짐.

## 들어간 커밋 (3)

| # | SHA | 내용 |
|---|---|---|
| 1 | `ead2850` | docs(contract): define rule firing trace MVP (§15) |
| 2 | `d61fce2` | feat(rule-runtime): add fire_rule_with_trace |
| 3 | (this) | docs(dev): PR3 record |

## 주요 설계 결정

### 1. 두 함수 모두 실제 firing (condition trace 와 비대칭이 다름)

condition trace 의 비대칭:

```text
evaluate_condition           — fast path, short-circuit, bool
evaluate_condition_with_trace — explain path, full eval, NOT state-changing
```

firing trace 의 비대칭은 **다름**:

| | `fire_rule` | `fire_rule_with_trace` |
|---|---|---|
| 반환값 | `int \| None` | `FiringTrace` |
| Engine 상태 변경 | yes | **yes — 동일** |
| condition 평가 | 1회 | 1회 |
| 미등록 rule | `KeyError` | `KeyError` |

핵심: trace 함수도 실제 firing 함수다. "설명만 하고 상태 안 변경" 으로 만들지 않음.

### 2. `_fire_rule_core` 단일 source of truth

두 공개 함수는 **단일 private helper** 만 호출:

```python
def fire_rule(...) -> int | None:
    return _fire_rule_core(...).claim_id

def fire_rule_with_trace(...) -> FiringTrace:
    return _fire_rule_core(...)
```

로직이 두 군데로 복붙되면 한쪽이 나중에 흐른다 — 가장 흔한 AI 실수. 단일 helper 로 divergence 0.

### 3. Condition 평가 1회

`_fire_rule_core` 는 `evaluate_condition_with_trace` 만 사용. `trace.result` 가 firing 결정에 직접 쓰임. `evaluate_condition` 별도 호출 X.

**Trade-off**: fast path 도 항상 full eval (short-circuit 안 함). MVP 에서 비용 미미. 측정 가능한 병목 되면 별도 결정점.

### 4. Engine 은 trace 저장 안 함

- `Engine._firing_traces` 같은 슬롯 추가 안 함
- trace 는 반환만 — 호출자 (logger / 외부 store) 가 결정
- `RuleStats` (aggregate: firing_count) 는 계속 Engine 보유
- trace = detailed event, stats = aggregate — 두 역할 구분

### 5. 미등록 rule = KeyError, FiringTrace 미생성

- `fired=False` trace 로 swallow 하지 않음
- 호출자 버그를 표면화
- fail-fast 보존 (16차 동작 그대로)

## FiringTrace 구조

```python
@dataclass(frozen=True)
class FiringTrace:
    rule_id: int
    rule_version: int
    subject_id: int
    fired: bool
    condition_trace: Trace      # condition.Trace = PredicateTrace | CombinatorTrace
    claim_id: int | None
    gap_ids: tuple[int, ...]
```

## 불변식 (테스트로 잠금)

1. `trace.fired == (trace.claim_id is not None)`
2. `fired=False ⇒ claim_id=None and gap_ids=()`
3. `fired=True and required_evidence is None ⇒ gap_ids=()`
4. `fired=True and required_evidence.evidence_types ⇒ len(gap_ids) == len(evidence_types)`
5. `trace.condition_trace.result == trace.fired`

## 테스트

**394 passing** in ~0.4s

| 파일 | 22차 후 | 변동 |
|---|---|---|
| `test_rule_runtime.py` | 57 | **+23** (16/19차 34개 그대로, trace 23 신규) |
| 나머지 파일들 | 337 | 변경 0 |

기존 371 → 신규 394.

### 신규 테스트 그룹

| 그룹 | 개수 | 내용 |
|---|---|---|
| `TestFireRuleWithTraceTrue` | 6 | true → FiringTrace 반환 / rule_id 보존 / firing_count +1 / children MATCH |
| `TestFireRuleWithTraceFalse` | 4 | false → fired=False / MISMATCH / MISSING_FIELD / 상태 변화 0 |
| `TestFireRuleWithTraceGapIds` | 3 | None / empty / 3 evidence → gap_ids 동작 |
| `TestFireRuleWithTraceInvariants` | 6 | §15 불변식 5개 + frozen |
| `TestFireRuleWithTraceErrors` | 1 | 미등록 rule = KeyError + trace 미생성 |
| `TestFireRuleEquivalence` | 2 | `fire_rule` ↔ `fire_rule_with_trace` 동일 engine 상태 (true/false 각각) |
| `TestFireRuleWithTraceYamlEndToEnd` | 1 | YAML → register → 3 compile → fire_with_trace → trace + engine 상태 일치 |

### 기존 테스트 변경 0

PR2 의 16/19차 fire_rule 테스트 (`TestFireRuleTrue`, `TestFireRuleFalse`, `TestFireRuleErrors`, `TestFireRuleMultiple`, `TestFireRuleYamlEndToEnd`, `TestFireRuleWithRequiredEvidence`, `TestFireRuleFalseWithRequiredEvidence`, `TestFireRuleYamlEndToEndWithGaps`) 모두 수정 없이 그대로 통과. 하위 호환 회귀 방지.

## 변경 파일 요약

| 파일 | 변경 |
|---|---|
| `ragcore/rule_runtime.py` | `FiringTrace` + `_fire_rule_core` 추가, `fire_rule` 은 wrapper 로 전환 (시그니처 0 변경) |
| `ragcore/__init__.py` | `FiringTrace`, `fire_rule_with_trace` export 추가 |
| `tests/test_rule_runtime.py` | 23 new tests (기존 34개 변경 X) |
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §15 신설 |
| `docs/dev/PR_003_RULE_FIRING_TRACE_MVP.md` | 신규 (이 파일) |

## Out of Scope (의도적 제외)

- **Trace 직렬화** (JSON / YAML) — 호출자가 필요할 때 별도 helper
- **Trace pretty-printer** — `__repr__` 강화, indented dump 등
- **Trace 영속화** (DB / file) — Engine 슬롯 추가 X
- **Trace timestamp** — firing 시간 기록
- **Trace context snapshot** — 입력 context 의 deep copy 저장
- **Bulk fire trace 모음** — 여러 룰 동시 firing 시 trace 집합
- **Trace ↔ RuleStats 자동 연동** — observed_precision 자동 갱신
- **Trace diff / comparison** — 두 firing trace 비교
- **Gap dedup / merge** — PR4 후보

확장 기능들은 **trace 소비자** (logger, RAG store, debug UI) 가 생긴 뒤 별도 결정점에서 추가. 지금 넣으면 PR3 범위를 흐림.

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| **A (1순위)** | **Gap dedup / merge** — `(subject, required_evidence_type)` 중복 방지 | 높음 |
| B | Claim 승격 logic (evidence 채워지면 candidate → confirmed) | 중 |
| C | Trace 직렬화 / pretty-printer | 낮음 (소비자 필요 시) |
| D | Engine bulk fire (등록된 모든 룰 일괄 평가) | 중 |
| E | `not` combinator + nested field access | 중 |
| F | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **A (Gap dedup)**. 현재는 같은 룰이 여러 번 fire 되면 동일 evidence 의 gap 이 중복 생성됨 — 운영 단계에서 곧 문제. dedup 정책 결정점이 다음 자연 흐름.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md](../contracts/05_DATA_CONTRACT_MVP.md) — §15 추가 (firing trace)
- [docs/dev/PR_001_PYTHON_REFERENCE_CORE_MVP.md](PR_001_PYTHON_REFERENCE_CORE_MVP.md) — Phase 1 record
- [docs/dev/PR_002_RULE_ENGINE_MVP.md](PR_002_RULE_ENGINE_MVP.md) — Phase 2 record (base)

## How to Run

```bash
git checkout feat/rule-trace-mvp
pip install -e .
pytest -v
```

394 tests in ~0.4s. No new external dependencies.
