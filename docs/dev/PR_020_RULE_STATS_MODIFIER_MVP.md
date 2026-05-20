# PR #020 — Rule Stats Modifier MVP (PR20-F)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/rule-stats-modifier-mvp` → `main`
> Base: `f165f0d` (PR19-E merged)
> Tests: 694 passing (local)

## 목적

PR19-E 까지의 흐름:

```text
effective = base × status × freshness × gap × count
→ Rule 의 maturity dimension 은 effective 에 반영 안 됨
```

PR20-F 추가:

```text
effective = base × status × freshness × gap × count × rule_stats
→ 룰이 엔진 안에서 충분히 firing 되지 않았을 때 약한 감쇠 추가
```

## PR20-F 의 한 줄 정의

> **PR20-F 는 "이 룰은 맞는가 / 틀린가" 를 판결하는 PR 이 아니다.
> PR20-F 는 "이 룰이 엔진 안에서 충분히 관측되었는가" 를 effective_confidence
> 에 약하게 반영하는 PR 이다.**

PR2 에서 등장한 RuleStats noun 을 PR11-D 의 effective verb 에 연결하는 PR.
PR11-C / PR12-D / PR19-E 옆의 다섯 번째 modifier. **Claim 판단 (lifecycle /
status / refute) 은 한 줄도 바뀌지 않는다.**

## 핵심 명제 (§32.2)

```text
RuleStats modifier is a weak maturity signal,
not a rule quality verdict.
```

한국어:

```text
RuleStats modifier 는 룰의 품질을 판결하는 장치가 아니라,
해당 룰이 엔진 안에서 충분히 관측되었는지를 약하게 반영하는 성숙도 신호다.
```

대조:

```text
RuleStats modifier ≠ "이 룰은 맞다 / 틀리다"
RuleStats modifier = "이 룰은 아직 관측 이력이 충분한가?"
```

## 6-Modifier Composition 완성

```python
effective_confidence(claim) = (
    base_confidence                              # PR1
    × status_modifier(claim.status)              # PR11-D §24
    × freshness_modifier(claim_id)               # PR11-C §26
    × gap_modifier(claim_id)                     # PR12-D §28
    × count_modifier(claim_id)                   # PR19-E §31
    × rule_stats_modifier(claim)                 # PR20-F §32 (신규)
)
```

| modifier | PR | 형태 | 강도 |
|---|---|---|---|
| status_modifier | PR11-D | 4 값 (1.0/1.0/0.5/0.0) | 강 (refuted=0) |
| freshness_modifier | PR11-C | continuous (1 - s × 0.5) | 중 (max 50%) |
| gap_modifier | PR12-D | binary (0.8 / 1.0) | 약 (20%) |
| count_modifier | PR19-E | binary (0.8 / 1.0) | 약 보조 |
| **rule_stats_modifier** | **PR20-F** | **binary (0.9 / 1.0)** | **매우 약 (10%)** |

## RuleStats modifier 규칙

```text
claim.created_by_rule == 0 (sentinel)                                → 1.0
(claim.created_by_rule, claim.created_by_rule_version) lookup miss   → 1.0
firing_count < 2                                                      → 0.9
firing_count >= 2                                                     → 1.0
boost (modifier > 1.0)                                                → 영구 금지
```

## Composition Table (PR20-F 신규 분만)

`Claim` 이 등록된 룰 `(1, 1)` 에 연결되어 있다고 가정 (단, sentinel/miss 행 제외).

| 시나리오 | effective |
|---|---|
| candidate + active 0 + no gap + sentinel (created_by_rule=0) | base |
| candidate + active 0 + no gap + lookup miss | base |
| candidate + active 0 + no gap + firing 0 | base × 0.9 |
| candidate + active 0 + no gap + firing 1 | base × 0.9 |
| candidate + active 0 + no gap + firing 2 | base |
| candidate + active 0 + no gap + firing 1_000_000 | base (boost 없음) |
| confirmed + active 1 (strength 0.8) + firing 1 | base × 0.6 × 0.9 = base × 0.54 |
| candidate + unresolved gap + firing 1 | base × 0.8 × 0.9 = base × 0.72 |
| candidate + active 2 + firing 1 | base × 0.8 × 0.9 = base × 0.72 |
| disputed + active 2 (most 0.8) + unresolved gap + firing 1 | **base × 0.1728** |
| refuted + firing 1 | 0.0 (status dominate) |

## 닫힌 흐름 (PR20-F 추가분)

```text
Claim 생성 (add_claim)
  → created_by_rule + created_by_rule_version 두 필드를 Claim 에 저장 (PR2 unchanged)

Rule 등록 (register_rule)
  → _rule_definitions[(id, version)] + _rule_stats[(id, version)] 초기화 (firing_count=0)

Rule firing 누적 (update_rule_stats)
  → _rule_stats[key] 를 새 RuleStats 인스턴스로 교체 (PR2 unchanged)

compute_effective_confidence(claim_id)
  → _rule_stats_modifier_for_claim(claim) 호출 (신규)
       ├─ created_by_rule == 0 → 1.0
       ├─ _rule_stats.get(key) is None → 1.0
       └─ firing_count < 2 → 0.9, else → 1.0
  → 기존 4 modifier 와 곱셈 결합 (한 줄 추가)
  → ScoreValue 반환 (engine state 무변경)
```

## 들어간 커밋 4

```text
86차 23df790 docs(contract): define rule_stats modifier MVP (§32)
87차 e836287 test(core): lock rule_stats modifier invariants
88차 3314614 feat(engine): activate rule_stats modifier
89차 (이번) docs(dev): record PR20 rule_stats modifier MVP
```

## 주요 설계 결정

### Sub-decision V — `firing_count` only

`rule_stats_modifier` 는 **`RuleStats.firing_count` 한 필드만 본다**:

- `confirmed_true_count` / `confirmed_false_count` (outcome ratio) — OOS, 별도 PR
- `observed_precision` / `false_positive_rate` (rule quality score) — OOS, 별도 PR
- timestamp 기반 firing freshness — OOS (wall-clock 영구 OOS 정신 일관)
- `rule_definition.maturity` / `prior_confidence` — 의미가 다름, 별도 PR

이유: PR20-F MVP 는 **RuleStats noun → effective verb 의 최소 연결**.
outcome ratio / quality score / timestamp 의미는 각자 독립 PR 가치가 있고,
한 번에 묶으면 "룰 품질 평가 시스템" 으로 비대화된다.

### Sub-decision W — Threshold = 2, binary

```python
_RULE_STATS_PENALTY_MODIFIER = 0.9
_RULE_STATS_MIN_FIRING_COUNT = 2
```

- binary — PR19-E count_modifier 와 동일 정신, N-dependent 함수는 OOS
- threshold 2 — "처음 한 번 firing" 과 "두 번째 이상" 의 분리
- 0.9 약함 — status (0.0/0.5) / freshness (max 50%) / gap·count (0.8) 보다 약함

### Sub-decision X — Boost 금지

```text
rule_stats_modifier ∈ {0.9, 1.0}
```

firing_count 가 1_000_000 이어도 modifier 는 1.0 을 초과하지 않는다.
PR11-D §24.5 Sub-decision N (effective ≤ base) / PR19-E Sub-decision E
의 정신과 동일. 본 PR 은 attenuation 만 한다.

### Sub-decision Y — Unknown / no rule source → 1.0

다음 경우 모두 `rule_stats_modifier = 1.0`:

```text
1. claim.created_by_rule == 0 (sentinel — 룰 기반 아닌 Claim)
2. (claim.created_by_rule, claim.created_by_rule_version) 페어가
   _rule_stats 에 등록되어 있지 않음
```

이유: PR20-F 는 **기존 호환 보존이 최우선**. 룰 등록 없이 `add_claim` 으로
직접 만든 Claim 과 등록되지 않은 (rule_id, rule_version) 을 가진 Claim 은
PR11-D 시점부터 존재해온 합법 시나리오. 이들에 0.9 감쇠를 주면 PR1~PR19-E
다수 테스트와 기존 사용자 코드가 회귀한다.

→ **no rule source 와 lookup miss 는 동일하게 처리. modifier = 1.0.**

### Sub-decision Z — Persistence 무영향

`_rule_stats` / `_rule_definitions` / `_claims` 의 engine state 자체는
변경 없음. PR17 round-trip 자동 보존.

`_rule_stats_modifier_for_claim` 은 **stateless 계산** 이므로 snapshot 에
저장할 새 필드 없음. PR18-K `_CURRENT_SNAPSHOT_SCHEMA_VERSION` 도 그대로
유지 (현재 `1`, bump 없음).

### PR1~PR19-E 정합

- `types.py` 변경 0 — `Claim.created_by_rule` / `created_by_rule_version`
  + `RuleStats.firing_count` 는 PR2 시점부터 존재한 필드. PR20-F 는 이를 read.
- `__init__.py` 변경 0 — public export 추가 없음
- `rule_output.py` 변경 0 — Sub-decision D 영구 보존
- PR11-C freshness modifier 의미 — 변경 없음 (test 22 가 lookup miss claim
  으로 검증)
- PR12-D gap modifier 의미 — 변경 없음 (test 23 검증)
- PR19-E count modifier 의미 — 변경 없음 (test 24 검증)
- PR9-A `active_contradictions_for_claim` asc 동작 — 변경 없음
- PR10-A refute / PR11-B refute_by_freshness 동작 — 변경 없음
- PR18-K snapshot schema version — 변경 없음 (정책: bump 없음 / 실제값: 1 그대로)

### §32.10 contract 절대값 정정 (89차 동봉)

86차 §32.10 작성 시 "PR18-K schema_version 도 변경 없음 (여전히 `2`)" 으로
적었으나 실제 `_CURRENT_SNAPSHOT_SCHEMA_VERSION = 1`. 정책 의미("bump 없음")
는 정확했으나 절대값 오기. 89차 docs-only 마무리에 함께 정정:

> PR18-K snapshot schema version 변경 없음 — 정책 의미는 "bump 없음"이며,
> 실제로 `_CURRENT_SNAPSHOT_SCHEMA_VERSION` 은 PR18-K 시점 그대로 유지된다
> (현재 `1`).

숫자 재발 방지 — 절대값을 단정하지 않고 "PR18-K 시점 그대로" 라는 정책
표현 우선, 현재값은 괄호로 부기.

## 불변식 (테스트로 잠금)

§32.12 의 24 invariant. 87차에서 잠금, 88차 통과로 입증.

### Sentinel + lookup miss (Sub-decision Y)
1. `created_by_rule == 0` → 1.0
2. `created_by_rule == 0` + nonzero version → 1.0
3. 미등록 (rule_id, version) → 1.0
4. 같은 rule_id, 다른 version → lookup miss → 1.0

### Threshold (Sub-decision W/X)
5. `firing_count == 0` → 0.9
6. `firing_count == 1` → 0.9
7. `firing_count == 2` → 1.0
8. `firing_count == 10` → 1.0 (boost 없음)
9. `firing_count == 1_000_000` → 1.0 (여전히 boost 없음)

### Status × rule_stats
10. refuted + firing 1 → 0.0 (status dominate)
11. candidate + firing 1 → base × 0.9
12. confirmed + firing 1 → base × 0.9
13. disputed + firing 1 → base × 0.5 × 0.9 = base × 0.45

### Other modifier × rule_stats
14. freshness (active 1, strength 0.8) + firing 1 → base × 0.6 × 0.9
15. unresolved gap + firing 1 → base × 0.8 × 0.9
16. active count 2 + firing 1 → base × 0.8 × 0.9
17. disputed + active 2 (most 0.8) + unresolved gap + firing 1 → base × 0.1728

### No state mutation (Sub-decision Z)
18. `to_snapshot()` identical before/after compute
19. `_rule_stats` dict unchanged
20. `_lifecycle_seq` unchanged
21. `claim_lifecycle_history` unchanged

### Regression boundaries (lookup-miss claim 기준)
22. PR11-C freshness modifier 의미 보존
23. PR12-D gap modifier 의미 보존
24. PR19-E count modifier 의미 보존

## 테스트 결과

```text
86차 docs-only            : 670 passing
87차 test-first           : 신규 24 (9 fail + 15 pass), 기존 670 회귀 0
                            → 685 passed + 9 failed
88차 feat impl            : 9/9 fail 정확히 pass 전환
                            → 694 passed, 0 fail
89차 docs-only            : 694 passed, 0 fail 유지
```

## 변경 파일

| 파일 | 변경 | 차수 |
|---|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | +268 (§32 신규) + §32.10 절대값 정정 | 86 + 89 |
| `tests/test_engine_rule_stats_modifier.py` | +512 (신규) | 87 |
| `ragcore/engine.py` | +45 / -4 (private constants 2 + helper 메서드 + compose 1 줄) | 88 |
| `docs/dev/PR_020_RULE_STATS_MODIFIER_MVP.md` | 신규 | 89 |

## 신규 테스트 그룹

```text
tests/test_engine_rule_stats_modifier.py
  TestRuleStatsModifierSentinelAndLookup     (invariants 1~4)
  TestRuleStatsModifierThreshold             (invariants 5~9)
  TestRuleStatsCompositionWithStatus         (invariants 10~13)
  TestRuleStatsCompositionWithExistingModifiers (invariants 14~17)
  TestRuleStatsNoStateMutation               (invariants 18~21)
  TestRuleStatsRegressionBoundaries          (invariants 22~24)
```

## 구현 요약 (engine.py)

```python
# Private constants (module-level)
_RULE_STATS_PENALTY_MODIFIER = 0.9
_RULE_STATS_MIN_FIRING_COUNT = 2

# Helper method (Engine)
def _rule_stats_modifier_for_claim(self, claim: Claim) -> float:
    if claim.created_by_rule == 0:
        return 1.0
    key = (claim.created_by_rule, claim.created_by_rule_version)
    stats = self._rule_stats.get(key)
    if stats is None:
        return 1.0
    if stats.firing_count < _RULE_STATS_MIN_FIRING_COUNT:
        return _RULE_STATS_PENALTY_MODIFIER
    return 1.0

# compute_effective_confidence 본문 +1 라인
rule_stats_modifier = self._rule_stats_modifier_for_claim(claim)

# ScoreValue 곱셈에 × rule_stats_modifier 추가
return ScoreValue(
    claim.base_confidence.value
    * status_modifier
    * freshness_modifier
    * gap_modifier
    * count_modifier
    * rule_stats_modifier
)
```

## Out of Scope (PR20-F 외)

- `confirmed_true_count` / `confirmed_false_count` 기반 outcome ratio
- `observed_precision` / `false_positive_rate` 사용
- timestamp 기반 firing freshness
- `firing_count`-dependent 함수 (log / sqrt / linear)
- threshold 값 조정 (2 → N)
- boost modifier (영구 OOS)
- `rule_definition.maturity` / `prior_confidence` 사용
- 미등록 rule 에 penalty
- `_rule_stats` 자동 누적
- YAML rule schema 변경
- RuleOutput status 허용값 변경
- `rule_output.py` 변경 (Sub-decision D 영구 보존)
- `types.py` public export 변경
- `RuleStats` 새 필드 추가
- snapshot schema version bump

## 다음 PR 후보

다음 트랙 후보 (사용자 결정 대기):

- **PR21 후보 G — superseded/retracted 상태**: types.py / __init__.py 손대야 함 (Sub-decision D 깨짐), 사용자 명시 승인 필요. lifecycle history 라벨 확장.
- **PR21 후보 J — multi-rule claim composition**: 하나의 Claim 이 여러 rule 에서 도출됐을 때 prior 합성 규칙 (max / mean / harmonic mean).
- **PR21 후보 L — evidence type weight**: evidence_type 별 strength 가중치 (PR11 freshness 와 직교).
- **PR21 후보 M — gap severity tiering**: gap 의 critical / major / minor, gap_modifier 를 binary 0.8 에서 tiered 로 확장.
- **PR21 후보 N — contradiction strength averaging**: count_modifier 를 N>=2 binary → average strength 기반 continuous 확장.
- **PR21 후보 O — rule version pinning**: rule update 시 기존 claim 영향도 분석.
- **PR21 후보 P — external integration spec**: 외부 소비자 패키지 계약 정의.

PR20-F 의 자연 후속은 **rule-stats 영역 심화** (outcome ratio / quality
score) 또는 **새 modifier 추가** (L / M / N).

## Spec Reference

- §32 (Effective confidence — rule_stats modifier, MVP — weak maturity)
- §31 (Count modifier MVP, PR19-E)
- §28 (Gap modifier MVP, PR12-D)
- §26 (Evidence freshness modifier, PR11-C)
- §24 (Effective confidence, PR11-D)
- §29 (Persistence MVP, PR17)
- §30 (Snapshot migration framework, PR18-K)

## How to Run

```bash
# PR20-F invariants 만
pytest tests/test_engine_rule_stats_modifier.py -v

# 전체
pytest -q
```

## Result

```text
Before PR20-F (main = f165f0d):
  effective = base × status × freshness × gap × count
  670 passing

After PR20-F (main = <new sha>):
  effective = base × status × freshness × gap × count × rule_stats
  694 passing, 0 fail
```

5-modifier composition (PR19-E) → 6-modifier composition (PR20-F) 진화 완료.
