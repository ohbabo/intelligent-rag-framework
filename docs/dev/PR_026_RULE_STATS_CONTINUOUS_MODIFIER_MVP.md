# PR #026 — RuleStats Continuous Modifier MVP (PR26-R)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/rule-stats-continuous-mvp` → `main`
> Base: `7c48ee6` (PR25-T merged)
> Tests: 969 passing (local)

## Summary

PR26-R refines the rule_stats modifier from PR20-F binary (`0.9` / `1.0`) to
continuous maturity (`1.0 - (1.0 - maturity_ratio) × 0.2`).

The effective confidence formula shape remains **unchanged**:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
```

Only the internal `rule_stats` term changes. PR26-R does **not** introduce a
new dataclass field, observed_precision usage, outcome ratio computation,
rule quality verdict, snapshot schema bump, lifecycle transition, or public
API. PR23-M (gap binary → tier) / PR24-N (count binary → continuous) 와 같은
정제 패턴 — 의미 자체는 보존하고 강도만 정밀화.

## PR26-R 의 한 줄 정의

> **PR26-R 은 RuleStats 를 품질 평가기로 바꾸는 PR 이 아니다.**
> **PR26-R 은 기존 firing_count 기반 maturity penalty 를**
> **binary 에서 continuous 로 정제하는 PR 이다.**

PR11-D §24.5 의 modifier 분해 자리에서 **rule_stats 항만** 정제. PR11-C /
PR12-D / PR23-M / PR19-E / PR24-N / PR21-L / PR22-S / PR25-T 의 자리는 그대로.
Claim 판단 / lifecycle / refute / 새 RuleStats 구조 모두 변경 없음.

## 핵심 명제 (§38.2)

```text
RuleStats modifier is a weak maturity signal, not a rule quality verdict.
Continuous refinement separates zero-observation from one-observation
without introducing quality judgment.
```

한국어:

```text
RuleStats modifier 는 룰의 품질을 판결하는 장치가 아니라,
해당 룰이 엔진 안에서 충분히 관측되었는지를 약하게 반영하는 성숙도 신호다.

PR26-R 의 정제는 0회 관측과 1회 관측을 구분하지만,
품질 판결 (옳다 / 그르다) 을 도입하지 않는다.
```

대조:

```text
PR20-F: "firing_count >= 2 인가?" (binary maturity)
PR26-R: "firing_count 가 saturation 까지 얼마나 채워졌나?" (continuous maturity)
PR23-M (gap): "unresolved gap count 가 얼마인가?" (tier)
PR24-N (count): "active contradiction avg strength 가 얼마인가?" (continuous)
```

## Maturity table

| firing_count | maturity_ratio | rule_stats_modifier | 비고 |
|---:|---:|---:|---|
| < 0 (clamped) | 0.0 | 0.8 | BQ defensive floor |
| 0 | 0.0 | **0.8** | ★ 신규 (PR20-F 0.9 자연 만료) |
| 1 | 0.5 | **0.9** | ← PR20-F binary 중심점 자연 재현 |
| 2 | 1.0 | 1.0 | saturated |
| 10 | 1.0 | 1.0 | saturated |
| 1000 | 1.0 | 1.0 | saturated |

특징:
- range `[0.8, 1.0]` (max 20% attenuation, 0.8 hard floor)
- 중심점 보존 — firing 1 → 0.9 (PR20-F binary 와 동일)
- monotonic non-decreasing (firing_count 증가 시 modifier 강화만)

## 7-Modifier Composition (formula shape 보존)

```python
effective_confidence(claim) = (
    base_confidence                              # PR1
    × status_modifier(claim.status)              # PR11-D
    × freshness_modifier(claim_id)               # PR11-C
    × gap_modifier(claim_id)                     # PR12-D + PR23-M (tier)
    × count_modifier(claim_id)                   # PR19-E + PR24-N (continuous)
    × rule_stats_modifier(claim)                 # PR20-F → PR26-R (continuous, 내부만 변경)
    × evidence_type_modifier(claim_id)           # PR21-L + PR22-S + PR25-T
)
```

| modifier | PR | 형태 | 강도 | PR26-R 영향 |
|---|---|---|---|---|
| status_modifier | PR11-D | 4 값 | 강 | — |
| freshness_modifier | PR11-C | continuous | 중 | — |
| gap_modifier | PR12-D + PR23-M | tier | 약 (floor 0.7) | — |
| count_modifier | PR19-E + PR24-N | continuous | 약 (floor 0.75) | — |
| **rule_stats_modifier** | **PR20-F + PR26-R** | **continuous** | **매우 약 (floor 0.8)** | **본 PR 변경** |
| evidence_type_modifier | PR21-L+PR22-S+PR25-T | binary | 매우 약 (floor 0.9) | — |

count floor 0.75 < rule_stats floor 0.8 < evidence_type floor 0.9 → 강도 순위 일관성 유지.

## 닫힌 흐름 (PR26-R 추가분)

```text
register_rule(rule_definition)
  → self._rule_definitions[(id, version)] / self._rule_stats[(id, version)] 초기화 (firing_count=0)
  → (PR20-F unchanged)

update_rule_stats(rule_id, rule_version, firing_delta=N, ...)
  → self._rule_stats[key] 새 RuleStats (frozen, 교체)
  → (PR20-F unchanged, validation 변경 없음)

compute_effective_confidence(claim_id)
  → _rule_stats_modifier_for_claim(claim) 호출 (본문 교체됨)
       ├─ if claim.created_by_rule == 0 → 1.0          (Sub-decision BO)
       ├─ stats = self._rule_stats.get(key) → None → 1.0 (Sub-decision BO)
       ├─ clamped = min(max(stats.firing_count, 0), 2)  (Sub-decision BQ defensive clamp)
       ├─ maturity_ratio = clamped / 2
       └─ return 1.0 - (1.0 - maturity_ratio) × 0.2     (Sub-decision BM)
  → 기존 6 modifier 와 곱셈 결합 (compute 본문 한 줄 변경 없음)
  → ScoreValue 반환 (engine state 무변경)
```

## 들어간 커밋 4

```text
110차  0ece1c9  docs(contract): define rule stats continuous modifier MVP (§38)
111차  d6fb1a2  test(core):     lock rule stats continuous modifier invariants
112차  112ea1a  feat(engine):   activate rule stats continuous modifier
113차  (이번)   docs(dev):      record PR26 rule stats continuous modifier MVP
```

각 차수 commit message body 는 PR19 자세한 스타일 — `feedback_commit_message_body.md` 적용.
각 차수 commit 직후 즉시 push → PR #26 차수별 갱신 — `feedback_pr_cycle_push.md` 적용 (PR cycle 신규 패턴 3차 PR).

## 주요 설계 결정

### Sub-decision BK — Source = firing_count only

`rule_stats_modifier` 는 **`RuleStats.firing_count` 한 필드만 본다** (PR20-F
Sub-decision V 그대로 유지).

배제:
- `observed_precision` (PR20-F V — 별도 PR)
- `false_positive_rate` (PR20-F V — 별도 PR)
- `confirmed_true_count` / `confirmed_false_count` (outcome ratio — Q 트랙)
- timestamps / rule age (wall-clock 영구 OOS)
- domain type / rule reputation
- quality verdict

이유: PR26-R 의 본질은 **maturity 정제** — quality verdict 와 무관.

### Sub-decision BL — Saturation threshold = 2

```python
_RULE_STATS_MATURITY_SATURATION_COUNT = 2
```

PR20-F 의 `firing_count >= 2 → mature` 정신 그대로 보존.

### Sub-decision BM — Penalty weight = 0.2

```python
_RULE_STATS_MATURITY_PENALTY_WEIGHT = 0.2
```

공식:

```python
clamped = min(max(stats.firing_count, 0), 2)
maturity_ratio = clamped / 2
return 1.0 - (1.0 - maturity_ratio) * 0.2
```

핵심 지점 (중심점 보존):
- `firing_count == 1` → maturity_ratio 0.5 → modifier `1.0 - 0.5 × 0.2 = 0.9` ← PR20-F binary 와 동일
- `firing_count == 0` → maturity_ratio 0.0 → modifier `1.0 - 1.0 × 0.2 = 0.8` ← 신규
- `firing_count >= 2` → maturity_ratio 1.0 → modifier 1.0

### Sub-decision BN — No boost

```text
rule_stats_modifier ∈ [0.8, 1.0]
```

PR11-D Sub-decision N / PR19-E Sub-decision E / PR20-F Sub-decision X /
PR23-M / PR24-N 정신 일관. RuleStats 는 confidence 를 올리지 않는다.
성숙도가 충분하면 `1.0`, 부족하면 약하게 깎기만 한다.

### Sub-decision BO — Sentinel compatibility

```text
claim.created_by_rule == 0 → 1.0   (PR20-F Sub-decision Y 보존)
rule_stats lookup miss → 1.0       (PR20-F Sub-decision Y 보존)
```

PR20-F 가 잠근 호환 의미 그대로. 룰 등록 없이 `add_claim` 으로 직접 만든
Claim 과 미등록 `(rule_id, rule_version)` 페어를 가진 Claim 은 PR26-R 후에도
modifier = 1.0 (무영향).

### Sub-decision BP — PR20-F 자연 만료

PR20-F 의 binary expected 중 **`firing_count == 0` 케이스만** 자연 만료:

```text
firing_count == 0:
  PR20-F: 0.9 (binary "< 2")
  PR26-R: 0.8 (continuous, "0회 관측")

firing_count == 1:
  PR20-F: 0.9 (binary "< 2")
  PR26-R: 0.9 (continuous, "1회 관측") — 중심점 보존, 자연 만료 아님

firing_count >= 2:
  PR20-F: 1.0
  PR26-R: 1.0 — 동일
```

각 갱신 위치에 명시 코멘트:

```python
# PR26-R §38.6 (BM): maturity_ratio 0.0 → 1.0 - 1.0 × 0.2 = 0.8.
# 의미 (firing_count < 2 → attenuation) 보존, 강도만 정밀화.
# PR20-F binary 0.9 가 firing_count == 0 일 때 자연 만료 — 0회 관측은
# 1회 관측보다 더 미성숙.
```

### Sub-decision BQ — Defensive clamp

```python
clamped_count = min(
    max(stats.firing_count, 0),
    _RULE_STATS_MATURITY_SATURATION_COUNT,
)
```

이유:

현재 `update_rule_stats` 는 `firing_delta` 음수를 validate 하지 않는다 (caller
가 외부에서 음수 delta 호출 가능). PR26-R modifier 계산은 음수 firing_count
가 들어와도 안정적으로 동작해야 함:

- `max(firing_count, 0)` — 음수 → 0 으로 clamp → modifier = 0.8 (floor)
- `min(..., saturation)` — 큰 수 → saturation 으로 clamp → modifier = 1.0

PR26-R MVP 는 `update_rule_stats` validation 의미를 **변경하지 않는다** —
modifier 계산 안전성만 보호.

### Sub-decision BR — Snapshot schema bump 없음

```text
_CURRENT_SNAPSHOT_SCHEMA_VERSION = 2  (그대로)
_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = frozenset({1, 2})  (그대로)
```

PR26-R 은 engine state shape 를 바꾸지 않는다:
- `_rule_stats` / `_rule_definitions` 구조 동일
- `RuleStats` dataclass 구조 동일 (이미 존재하는 `firing_count` 필드 활용)
- snapshot 직렬화 형식 동일

오직 `compute_effective_confidence` 의 `rule_stats_modifier` 계산식만 변경.

### Sub-decision BS — `_RULE_STATS_PENALTY_MODIFIER` 제거

```python
# Removed (PR20-F)
_RULE_STATS_PENALTY_MODIFIER = 0.9
_RULE_STATS_MIN_FIRING_COUNT = 2

# Added (PR26-R)
_RULE_STATS_MATURITY_PENALTY_WEIGHT = 0.2
_RULE_STATS_MATURITY_SATURATION_COUNT = 2
```

PR23-M / PR24-N 패턴 일관:
- PR23-M: 구 `_GAP_PENALTY_MODIFIER` 제거 → 4 개 tier 상수
- PR24-N: 구 `_COUNT_PENALTY_MODIFIER` 제거 → `_COUNT_STRENGTH_PENALTY_WEIGHT`
- PR26-R: 구 `_RULE_STATS_PENALTY_MODIFIER` / `_RULE_STATS_MIN_FIRING_COUNT` 제거 → `_RULE_STATS_MATURITY_PENALTY_WEIGHT` + `_RULE_STATS_MATURITY_SATURATION_COUNT`

PR20-F privacy 정신 보존 — 신규 상수 2 개 모두 engine 내부 private,
`ragcore` / `ragcore.types` 미노출.

## 구현 요약 (engine.py)

```python
# Removed (PR20-F)
_RULE_STATS_PENALTY_MODIFIER = 0.9
_RULE_STATS_MIN_FIRING_COUNT = 2

# Added (PR26-R)
_RULE_STATS_MATURITY_PENALTY_WEIGHT = 0.2
_RULE_STATS_MATURITY_SATURATION_COUNT = 2

# Helper body 교체 (Sub-decision BK~BQ)
def _rule_stats_modifier_for_claim(self, claim: Claim) -> float:
    if claim.created_by_rule == 0:
        return 1.0
    key = (claim.created_by_rule, claim.created_by_rule_version)
    stats = self._rule_stats.get(key)
    if stats is None:
        return 1.0
    clamped_count = min(
        max(stats.firing_count, 0),
        _RULE_STATS_MATURITY_SATURATION_COUNT,
    )
    maturity_ratio = clamped_count / _RULE_STATS_MATURITY_SATURATION_COUNT
    return 1.0 - (
        (1.0 - maturity_ratio) * _RULE_STATS_MATURITY_PENALTY_WEIGHT
    )

# compute_effective_confidence docstring (rule_stats 섹션) 갱신 — formula 변경 없음
```

`compute_effective_confidence` 본문 — 변경 0 (helper 호출만 바뀜).
다른 modifier helper / state / snapshot — 모두 변경 0.

## 불변식 (테스트로 잠금)

신규 테스트 파일 `tests/test_engine_rule_stats_continuous_modifier.py` —
10 클래스, 48 tests, 763 라인.

### TestRuleStatsContinuousSentinelAndLookup (4) — Sub-decision BO
- `created_by_rule == 0` sentinel → 1.0
- sentinel + nonzero version → 1.0
- 미등록 (rule_id, version) → lookup miss → 1.0
- 같은 rule_id, 다른 version → miss → 1.0

### TestRuleStatsContinuousMapping (5) — Sub-decision BL/BM
- `firing_count == 0` → 0.8 (★ PR20-F 자연 만료)
- `firing_count == 1` → 0.9 (PR20-F 중심점 보존)
- `firing_count == 2` → 1.0 (saturated)
- `firing_count == 10` → 1.0
- `firing_count == 1_000_000` → 1.0

### TestRuleStatsContinuousDefensiveClamp (3) — Sub-decision BQ
- negative `firing_count` → 0.8 (floor)
- very negative → still 0.8
- stored RuleStats unchanged by clamp

### TestRuleStatsContinuousBoundary (2) — Sub-decision BN
- range `[0.8, 1.0]` for sample values
- never > 1.0 (no boost)

### TestRuleStatsContinuousComposition (7) — 7-modifier
- refuted dominate (any firing → 0.0)
- confirmed + firing 0 → base × 0.8
- confirmed + firing 1 → base × 0.9
- confirmed + firing 2 → base × 1.0
- disputed + firing 0 → 0.40
- disputed + firing 1 → 0.45
- full 7-modifier (disputed + active 2 0.3/0.8 + 3 gaps + firing 0 + hint-only) → 0.130410

### TestRuleStatsContinuousNoStateMutation (4) — read-only
- snapshot identical before/after compute
- `_rule_stats` unchanged
- `_lifecycle_seq` unchanged
- lifecycle history unchanged

### TestRuleStatsContinuousSnapshot (4) — Sub-decision BR
- schema_version 2 유지
- snapshot keys 집합 변경 없음
- round-trip after firing 0 preserves continuous output
- RuleStats dataclass fields unchanged

### TestRuleStatsContinuousPrivateConstants (5) — Sub-decision BS
- `_RULE_STATS_MATURITY_PENALTY_WEIGHT == 0.2` private
- `_RULE_STATS_MATURITY_SATURATION_COUNT == 2` private
- 신규 상수 ragcore / types 미노출
- 구 `_RULE_STATS_PENALTY_MODIFIER` 제거됨
- 구 `_RULE_STATS_MIN_FIRING_COUNT` 제거됨

### TestRuleStatsContinuousPublicNamespace (5) — Sub-decision D 보존
- RuleStats dataclass fields 변경 없음
- `__init__.py` 에 PR26-R 신규 export 0
- `rule_output.py` 변경 없음
- public namespace 신규 export 0
- `update_rule_stats` 외부 동작 변경 없음

### TestRuleStatsContinuousRegressionBoundaries (9) — PR1~PR25-T 보존
- PR11-C freshness modifier 보존
- PR23-M gap modifier 보존
- PR24-N count strength averaging 보존
- PR21-L evidence_type modifier 보존
- PR25-T register/unregister/clear API 보존
- PR10-A refute / PR11-B refute_by_freshness 보존
- PR9-A active_contradictions_for_claim asc 보존
- PR17 round-trip identity 보존
- PR18-K migration framework 보존

## 테스트 결과

```text
110차 docs-only            : 921 passing
111차 test-first           : 신규 48 (11 fail + 37 pass), 기존 921 회귀 0
                            → 958 passed + 11 failed
112차 feat impl + 자연 만료 : 11/11 fail 정확히 pass 전환
                            + PR20-F 자연 만료 테스트 3 개 expected 갱신
                            → 969 passed, 0 fail
113차 docs-only            : 969 passed, 0 fail 유지
```

### 111차 fail-to-pass mapping (11 fail → 11 pass)

| 차단 영역 | Fail 수 | 112차 메커니즘 |
|---|---:|---|
| `firing_count == 0` mapping (0.9 → 0.8) | 1 | continuous formula |
| Defensive clamp (negative → 0.8 floor) | 2 | BQ clamp |
| Boundary range (firing 0 sample) | 1 | continuous formula |
| Composition (confirmed/disputed/full 7-mod with firing 0) | 3 | continuous formula |
| Snapshot round-trip with firing 0 | 1 | engine state 자연 보존 |
| 신규 `_RULE_STATS_MATURITY_*` 부재 | 2 | 신규 상수 추가 |
| 구 `_RULE_STATS_PENALTY_MODIFIER` / `_MIN_FIRING_COUNT` 잔존 | 2 | 구 상수 제거 |

## 자연 만료 테스트 갱신 (3 개, 2 파일)

각 갱신 위치에 명시 코멘트:

```python
# PR26-R §38.6 (BM): maturity_ratio 0.0 → 1.0 - 1.0 × 0.2 = 0.8.
# 의미 (firing_count < 2 → attenuation) 보존, 강도만 정밀화.
# PR20-F binary 0.9 가 firing_count == 0 일 때 자연 만료 — 0회 관측은
# 1회 관측보다 더 미성숙.
```

### 갱신 정리

| 파일 | 테스트 | Before → After |
|---|---|---|
| `test_engine_rule_stats_modifier.py` | `test_firing_count_zero_applies_penalty` (PR20-F 본가 invariant 5) | 0.9 → 0.8 |
| `test_engine_count_strength_averaging.py` | `test_pr20f_rule_stats_modifier_unchanged` → `_meaning_preserved` (PR24-N regression) | 0.9 → 0.8 |
| `test_engine_count_strength_averaging.py` | `test_full_seven_modifier_composition_uses_strength_averaged_count` (composition with firing 0) | rule_stats 0.9 → 0.8 |

### 사용자 분석 보정

110차 §38.9 / 111차 보고에서 "PR20-F test 가 firing_count == 0 영역을 직접
다루지 않을 것" 으로 예측했으나, 실제로는 PR20-F 본가 invariant 5 +
PR24-N regression 2 = **3 개 자연 만료** 발견. PR23-M (16 갱신) / PR24-N
(14 갱신) 보다 작은 규모지만 예측보다는 약간 많음. 112차에서 즉시 갱신
완료.

## PR1~PR25-T 정합

- `types.py` 변경 0 — Sub-decision D 영구 보존
- `__init__.py` 변경 0 — public export 추가 없음
- `rule_output.py` 변경 0 — Sub-decision D 영구 보존
- PR9-A `active_contradictions_for_claim` asc 동작 — 변경 없음
- PR11-C freshness modifier 의미 — 변경 없음
- PR12-D + PR23-M gap modifier 의미 — 변경 없음
- PR19-E + PR24-N count modifier 의미 — 변경 없음
- PR20-F 의 "firing_count maturity attenuation" 의미 — 보존, 강도만 정밀화
- PR21-L + PR22-S + PR25-T evidence_type modifier API + 의미 — 변경 없음
- PR10-A refute / PR11-B refute_by_freshness 동작 — 변경 없음
- PR17 round-trip identity — 보존
- PR18-K migration framework — 변경 없음
- `update_rule_stats` 외부 동작 — 변경 없음

## Out of Scope (PR26-R 외)

| 제외 | 이유 / 향후 |
|---|---|
| `observed_precision` 사용 | Sub-decision BK — quality verdict 영역 |
| `false_positive_rate` 사용 | Sub-decision BK |
| `confirmed_true_count` / `confirmed_false_count` 기반 outcome ratio | Q 트랙 (claim lifecycle 역전파 대규모) |
| Timestamp / rule age 기반 staleness | wall-clock 영구 OOS |
| Rule reputation system | 별도 PR — taxonomy 소유 회피 |
| Domain-specific rule taxonomy | 별도 PR |
| Confidence boost (modifier > 1.0) | Sub-decision BN — 영구 OOS |
| Saturation count 조정 (2 → N) | MVP 잠금 |
| Penalty weight 조정 (0.2 → 다른 값) | MVP 잠금 |
| 비선형 maturity 함수 (log / sqrt) | continuous MVP |
| `update_rule_stats(firing_delta=-1)` validation | Sub-decision BQ — defensive clamp 만, validation 별도 PR |
| Snapshot schema v3 bump | Sub-decision BR |
| Public `_RULE_STATS_MATURITY_*` 상수 export | Sub-decision BS — engine 내부 private |
| `types.py` / `__init__.py` / `rule_output.py` 변경 | Sub-decision D 영구 보존 |
| Per-rule / per-claim weight override | engine-global weight 만 |

## 다음 PR 후보

PR26-R 닫음 후 PR27+ 후보 (사용자 결정 대기):

- **PR27 후보 G — superseded/retracted 상태**: types.py / __init__.py 손대야 함, **사용자 명시 승인 필요**.
- **PR27 후보 J — multi-rule claim composition**: prior 합성 규칙 (max / mean / harmonic).
- **PR27 후보 O — rule version pinning**: rule update 시 claim 영향도.
- **PR27 후보 P — external integration spec**: 외부 소비자 패키지 계약 (docs 위주).
- **PR27 후보 Q — rule_stats outcome ratio**: claim lifecycle 결과 역전파 (대규모).

modifier 정제 패턴 (binary → tier/continuous) 은 PR23-M / PR24-N / PR26-R 3차
연속으로 완료. 다음 PR 은 자연 후속이 적어졌으므로 사용자 결정 영역.

## Spec Reference

- §38 (RuleStats modifier continuous maturity, PR26-R)
- §37 (Hint evidence type deregistration, PR25-T) — 인접 PR
- §36 (Count modifier strength averaging, PR24-N) — 동일 정제 패턴
- §35 (Gap modifier severity tiering, PR23-M) — 동일 정제 패턴
- §34 (Evidence_type registration strict validation, PR22-S)
- §33 (Evidence_type modifier MVP, PR21-L)
- §32 (Rule_stats modifier MVP, PR20-F) — PR26-R 의 자연 후속
- §31 (Count modifier MVP, PR19-E)
- §30 (Snapshot migration framework, PR18-K) — 무영향
- §29 (Persistence MVP, PR17)
- §28 (Gap modifier MVP, PR12-D)
- §26 (Evidence freshness modifier, PR11-C)
- §24 (Effective confidence, PR11-D)

## How to Run

```bash
# PR26-R invariants 만
pytest tests/test_engine_rule_stats_continuous_modifier.py -v

# 전체
pytest -q
```

## Self-review

- [x] 111차 의도 fail 11개 → 112차 11/11 pass 정확히 전환
- [x] 111차 pass 37개 유지
- [x] 기존 921 회귀 0
- [x] 최종 969 passing, 0 fail
- [x] `_RULE_STATS_PENALTY_MODIFIER` 제거 (PR20-F binary)
- [x] `_RULE_STATS_MIN_FIRING_COUNT` 제거 (PR20-F threshold constant)
- [x] `_RULE_STATS_MATURITY_PENALTY_WEIGHT = 0.2` 신규
- [x] `_RULE_STATS_MATURITY_SATURATION_COUNT = 2` 신규
- [x] `_rule_stats_modifier_for_claim` 본문 교체 (continuous + defensive clamp)
- [x] sentinel + lookup miss → 1.0 (PR20-F BO 호환 보존)
- [x] firing_count == 0 → 0.8 (★ PR20-F 0.9 자연 만료)
- [x] firing_count == 1 → 0.9 (PR20-F 중심점 보존)
- [x] firing_count >= 2 → 1.0 (saturated)
- [x] negative firing_count → 0.8 (BQ defensive clamp)
- [x] no boost — modifier ∈ [0.8, 1.0] 보장
- [x] modifier 즉시 반영 (state 무변경, live read)
- [x] `RuleStats` / `Claim` / `Evidence` / `Gap` dataclass 변경 없음
- [x] snapshot schema_version `2` 유지 (Sub-decision BR)
- [x] snapshot 직렬화 형식 변경 없음
- [x] 7-modifier formula shape / 강도 / 순서 변경 없음
- [x] public namespace 신규 export 0
- [x] `types.py` / `__init__.py` / `rule_output.py` 변경 0
- [x] `update_rule_stats` 외부 동작 변경 없음
- [x] lifecycle / refute / contradiction / 다른 modifier 의미 변경 없음
- [x] PR11-C / PR23-M / PR24-N / PR21-L / PR25-T / PR9-A / PR10-A / PR11-B / PR17 / PR18-K regression 모두 검증
- [x] 자연 만료 테스트 3개 명시 코멘트 갱신 (PR20-F binary 0.9 → PR26-R continuous 0.8)
- [x] PR cycle 신규 push 패턴 적용 (110차 직후 push + Draft PR, 이후 차수마다 push)
- [x] 모든 차수 commit message body PR19 자세한 스타일

## Final definition

> **PR26-R 은 RuleStats 를 품질 평가기로 바꾸는 PR 이 아니다.**
> **기존 firing_count 기반 maturity penalty 를 binary 에서 continuous 로 정제하는 PR 이다.**

> *RuleStats modifier is a weak maturity signal, not a rule quality verdict.*
> *Continuous refinement separates zero-observation from one-observation*
> *without introducing quality judgment.*

PR20-F → PR26-R 누적 효과:
- maturity signal 의미 보존 (firing_count 기반, outcome ratio / observed_precision OOS)
- threshold = 2 보존 (PR20-F Sub-decision V 그대로)
- center preservation (firing 1 → 0.9 자연 재현)
- zero-observation 과 one-observation 분리 (0회 → 0.8 신규)
- defensive clamp 도입 (modifier 안전성만 보호, update_rule_stats validation 무변경)

evidence_type 영역 (PR21-L → PR22-S → PR25-T) 의 boundary completion 과는
다른 축의 진화 — modifier 정제. PR23-M (gap binary → tier) / PR24-N (count
binary → continuous) / PR26-R (rule_stats binary → continuous) 정제 패턴 3차
완료.

## Result

```text
Before PR26-R (main = 7c48ee6):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  rule_stats_modifier (binary): firing_count < 2 → 0.9, else → 1.0
  921 passing

After PR26-R (main = <new sha>):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  (formula shape unchanged, modifier semantics preserved)
  rule_stats_modifier (continuous): 1.0 - (1.0 - maturity_ratio) × 0.2, floor 0.8
  969 passing, 0 fail
```

7-modifier composition formula shape 보존. rule_stats modifier 의미 보존
(maturity signal, not quality verdict). firing_count 기반 강도 분포 정밀화
(0회 → 0.8 / 1회 → 0.9 / 2+회 → 1.0). **PR26-R 의 본질은 modifier 의미 확장이
아니라 PR20-F binary maturity 의 continuous refinement 다.**

정제 패턴 3차 연속 완료 (PR23-M tier / PR24-N continuous / PR26-R continuous).
다음 PR 트랙은 사용자 결정 영역.
