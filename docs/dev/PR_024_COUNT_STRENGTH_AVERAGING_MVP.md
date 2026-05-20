# PR #024 — Count Strength Averaging MVP (PR24-N)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/count-strength-averaging-mvp` → `main`
> Base: `2eeaa35` (PR23-M merged)
> Tests: 871 passing (local)

## Summary

PR24-N refines the count modifier from PR19-E binary (`0.8` / `1.0`) to
average-strength continuous (`1.0 - avg_strength × 0.25`).

The effective confidence formula shape remains **unchanged**:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
```

Only the internal `count` term changes. PR24-N does **not** introduce a new
dataclass field, taxonomy, snapshot schema bump, lifecycle transition, or
public API. PR23-M (gap binary → tier) 와 같은 정제 패턴: 의미 자체는 보존
하고 강도만 정밀화.

## PR24-N 의 한 줄 정의

> **PR24-N 은 count modifier 의 의미를 새로 정의하는 PR 이 아니다.**
> **PR24-N 은 PR19-E 의 binary repeated-pressure attenuation 을**
> **active contradiction average strength 기반 continuous modifier 로 정제하는 PR 이다.**

PR11-D §24.5 의 modifier 분해 자리에서 **count 항만** 정제. PR11-C / PR12-D /
PR23-M / PR20-F / PR21-L / PR22-S 의 자리는 그대로. Claim 판단 / lifecycle /
refute / 새 Evidence 구조 모두 변경 없음.

## 핵심 명제 (§36.2)

```text
Count modifier remains a repeated-pressure signal.
PR24-N refines repeated pressure from binary count threshold
to average strength of active contradictions.
```

**사용자 강조 문장:**

```text
빈 강도의 contradiction 은 repeated pressure 가 아니다.
```

한국어:

```text
count modifier 는 여전히 "반복 압력" 신호다.
PR24-N 은 반복 압력을 단순 개수 기준에서
활성 contradiction 들의 평균 강도 기준으로 정제한다.

PR19-E 의 'active 2 이상이면 무조건 압력' 가정이
PR24-N 에서는 '강도가 있을 때만 압력' 으로 정제된다.
```

대조:

```text
PR19-E: "active count >= 2 인가?" (binary)
PR24-N: "active count >= 2 이고, 그 활성 contradiction 들의 평균 강도가 얼마인가?" (continuous)
PR23-M (gap): "unresolved gap count 가 얼마인가?" (tier)
```

## Count modifier table

```text
| active count | average strength | count modifier |
|---:|---:|---:|
| 0  | —    | 1.0  |
| 1  | any  | 1.0  |
| 2+ | 0.0  | 1.0  | ← 빈 강도는 repeated pressure 아님
| 2+ | 0.4  | 0.9  |
| 2+ | 0.8  | 0.8  | ← PR19-E binary 중심점 자연 재현
| 2+ | 1.0  | 0.75 | ← hard floor
```

특징:
- range `[0.75, 1.0]` (max 25% attenuation, 0.75 hard floor)
- 중심점 보존 — avg 0.8 → 0.8 (PR19-E binary 와 동일)
- monotonic non-increasing (avg 증가 시 modifier 약화만)

## 7-Modifier Composition (formula shape 보존)

```python
effective_confidence(claim) = (
    base_confidence                              # PR1
    × status_modifier(claim.status)              # PR11-D
    × freshness_modifier(claim_id)               # PR11-C
    × gap_modifier(claim_id)                     # PR12-D + PR23-M (tier)
    × count_modifier(claim_id)                   # PR19-E → PR24-N (continuous, 내부만 변경)
    × rule_stats_modifier(claim)                 # PR20-F
    × evidence_type_modifier(claim_id)           # PR21-L (+ PR22-S 강화)
)
```

| modifier | PR | 형태 | 강도 |
|---|---|---|---|
| status_modifier | PR11-D | 4 값 (1.0/1.0/0.5/0.0) | 강 |
| freshness_modifier | PR11-C | continuous (1 - s × 0.5) | 중 (max 50%) |
| gap_modifier | PR12-D + PR23-M | tier (1.0/0.9/0.8/0.7) | 약 (max 30%, floor 0.7) |
| **count_modifier** | **PR19-E → PR24-N** | **continuous (1.0 - avg × 0.25)** | **약 (max 25%, floor 0.75)** |
| rule_stats_modifier | PR20-F | binary (0.9 / 1.0) | 매우 약 (max 10%) |
| evidence_type_modifier | PR21-L | binary (0.9 / 1.0) | 매우 약 (max 10%) |

count floor `0.75` > gap floor `0.7` → gap 이 여전히 더 강한 신호 (의미 일관성).

## 닫힌 흐름 (PR24-N 추가분)

```text
add_evidence(claim_id, ..., strength)
  → self._evidences[ev_id] = Evidence(... strength=ScoreValue(strength)) (PR1 unchanged)

register_contradiction(claim_id, ev_id)
  → self._contradictions[claim_id].add(ev_id) (PR7 unchanged)

compute_effective_confidence(claim_id)
  → _count_modifier_for_claim(claim_id) 호출 (신규 helper)
       ├─ active = active_contradictions_for_claim(claim_id)  (PR9-A asc 그대로)
       ├─ if len(active) < 2 → 1.0  (Sub-decision AW, PR11-C 영역 보존)
       └─ else:
             avg_strength = mean(self._evidences[ev_id].strength.value for ev_id in active)
             return 1.0 - avg_strength × _COUNT_STRENGTH_PENALTY_WEIGHT (0.25)
  → 기존 6 modifier 와 곱셈 결합 (compute 본문 한 줄 교체)
  → ScoreValue 반환 (engine state 무변경)
```

## 들어간 커밋 4

```text
102차  eb39fba  docs(contract): define count strength averaging MVP (§36)
103차  05725f0  test(core):     lock count strength averaging invariants
104차  0c896e8  feat(engine):   activate count strength averaging
105차  (이번)   docs(dev):      record PR24 count strength averaging MVP
```

각 차수 commit message body 는 PR19 패턴 자세한 본문 (memory `feedback_commit_message_body.md` 적용 1차 PR).

## 주요 설계 결정

### Sub-decision AV — Name / source / threshold=2 유지

- 이름: `count_modifier` (변경 없음)
- 입력 source: `active_contradictions_for_claim(claim_id)` (PR9-A asc, PR19-E 그대로)
- threshold: active count 0~1 → 1.0 (PR19-E §31.5 Sub-decision E-2 보존)
- active count >= 2 부터 modifier 가 1.0 미만이 됨

이유: PR11-C 가 active 1 개 일 때 most recent strength 기반으로 단독 처리.
PR19-E 의 threshold=2 정신은 "count modifier 는 freshness 와 독립인 추가 repeated
pressure 신호" 의 핵심 — 보존.

### Sub-decision AW — Active count >= 2 일 때만 continuous 적용

```text
active_count < 2  → count_modifier = 1.0 (PR19-E 와 동일)
active_count >= 2 → count_modifier = 1.0 - avg_strength × _COUNT_STRENGTH_PENALTY_WEIGHT
```

active count 가 0/1 인 경우 modifier 는 항상 1.0 — PR11-C freshness 가 단독
처리. PR24-N 은 PR19-E 가 손대지 않던 영역 (active 0/1) 을 손대지 않는다.

### Sub-decision AX — Average strength 공식 + penalty weight 0.25

```python
_COUNT_STRENGTH_PENALTY_WEIGHT = 0.25

# active_count >= 2 일 때:
average_strength = mean(ev.strength.value for ev in active_evidences)
count_modifier = 1.0 - average_strength * _COUNT_STRENGTH_PENALTY_WEIGHT
```

range:
- `strength ∈ [0.0, 1.0]` 이므로 `average_strength ∈ [0.0, 1.0]`
- `count_modifier ∈ [0.75, 1.0]` (max 25% attenuation)

### Sub-decision AY — 중심점 보존 (PR19-E 0.8 = avg 0.8)

```text
average_strength = 0.8 → count_modifier = 0.8 (PR19-E binary 와 동일)
```

PR23-M Sub-decision AP 가 "2 unresolved → 0.8" 으로 PR12-D binary 중심점을
자연 보존한 것과 동일 정신.

### Sub-decision AZ — `_COUNT_PENALTY_MODIFIER` 제거 + weight 도입

```python
# Removed (PR19-E)
_COUNT_PENALTY_MODIFIER = 0.8

# Added (PR24-N)
_COUNT_STRENGTH_PENALTY_WEIGHT = 0.25
```

둘 다 engine 내부 private, `ragcore` / `ragcore.types` 미노출 (privacy 정신 유지).

### Sub-decision BA — Snapshot schema bump 없음

```text
_CURRENT_SNAPSHOT_SCHEMA_VERSION = 2  (그대로)
_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = frozenset({1, 2})  (그대로)
```

PR24-N 은 engine state shape 를 바꾸지 않는다:
- `_contradictions` / `_resolved_contradictions` / `_evidences` 구조 동일
- `Evidence` dataclass 구조 동일 (이미 존재하는 `strength` 필드 활용)
- snapshot 직렬화 형식 동일

오직 `compute_effective_confidence` 의 `count_modifier` 계산식만 변경.
PR18-K 정신: 의미 있는 변화 때만 bump.

### Sub-decision BB — PR19-E 자연 만료 테스트 갱신

PR19-E 의 "active 2 이상 → binary 0.8" 가정한 expected 값들이 자연 만료.
가장 큰 의미 변화는 `strength 0/0` 케이스:

```text
PR19-E: active 2 + strength 0/0 → count_modifier = 0.8 (압력 있음)
PR24-N: active 2 + strength 0/0 → count_modifier = 1.0 (압력 없음)
```

이는 PR23-M 자연 만료 (1 gap 0.8 → 0.9) 보다 큰 의미 변화 — *"빈 강도의
contradiction 은 repeated pressure 가 아니다"* 라는 PR24-N 정제 정신 반영.
PR19-E "repeated pressure" 의미는 **강도가 있을 때에만 살아 있다**.

PR19-E 가 PR11-C 의 active=2 expected 를 갱신했던 패턴, PR23-M 이 PR12-D 의
1-gap expected 를 갱신한 패턴과 동일하게, 104차에서 14 개 자연 만료 갱신
완료.

## 자연 만료 테스트 갱신 (14 개, 5 파일)

각 갱신 위치에 명시 코멘트:

```python
# PR24-N §36.6 (AX): active >= 2 일 때 count_modifier = 1.0 - avg × 0.25.
# PR19-E binary 0.8 의 중심점(avg 0.8)은 보존된다.
# 그러나 strength 0/0 은 0.8 → 1.0 으로 자연 만료된다.
# 빈 강도의 contradiction 은 repeated pressure 가 아니다.
```

### 파일별 갱신 정리

| 파일 | 갱신 수 | 주요 시나리오 |
|---|---:|---|
| `test_engine_count_modifier.py` | 4 | active 2 + strength 0/0 (0.8 → 1.0) / 0.3/0.8 (0.48 → 0.5175) / N invariant (둘 다 0.8 → 둘 다 1.0) / 6-mod composition (0.216 → 0.232875) |
| `test_engine_effective_freshness_modifier.py` | 1 | PR11-C older-strong invariant (0.72 → 0.765) — freshness 0.9 보존, count 0.85 |
| `test_engine_rule_stats_modifier.py` | 3 | active 2 strength 0/0 + firing 1 (0.72 → 0.9) / 6-mod (0.1944 → 0.2095875) / PR19-E 보존 (0.8 → 1.0) |
| `test_engine_evidence_type_modifier.py` | 3 | active 2 strength 0/0 + hint (0.72 → 0.9) / 7-mod (0.17496 → 0.18862875) / PR19-E 보존 (0.8 → 1.0) |
| `test_engine_gap_severity_tiering.py` | 3 | 2 gaps + active 2 strength 0/0 (0.64 → 0.8) / 7-mod with 3 gaps (0.13608 → 0.14671125) / PR19-E 보존 (0.8 → 1.0) |

### Composition 값 갱신 정리 (PR24-N 의미 변화)

| 시나리오 | Before (PR19-E binary) | After (PR24-N continuous) |
|---|---:|---:|
| active 2 + strength 0/0 | 0.8 | **1.0** ★ 의미 변화 |
| active 2 + strength 0.3/0.8 (avg 0.55) | 0.8 | 0.8625 |
| active 2 + strength 0.8/0.8 (avg 0.8) | 0.8 | **0.8** ← 중심점 |
| active 2 + strength 1.0/1.0 (avg 1.0) | 0.8 | 0.75 (floor) |
| confirmed + freshness 0.6 + active 2 0.3/0.8 | 0.48 | 0.5175 |
| disputed + active 2 0.3/0.8 + 1 unresolved gap | 0.216 | 0.232875 |
| active 2 strength 0/0 + firing 1 | 0.72 | 0.9 |
| 6-mod (disputed + active 2 0.3/0.8 + 1 gap + firing 1) | 0.1944 | 0.2095875 |
| 7-mod (... + hint-only direct) | 0.17496 | 0.18862875 |
| 7-mod (disputed + active 2 0.3/0.8 + 3 gaps + firing 1 + hint) | 0.13608 | 0.14671125 |
| "active 2 vs 10" N invariant (strength 0) | 0.8 == 0.8 | 1.0 == 1.0 (N 무관 보존) |

## PR1~PR23-M 정합

- `types.py` 변경 0 — `Evidence.strength` 는 PR1 시점부터 존재한 필드, PR24-N 은 이를 read
- `__init__.py` 변경 0 — public export 추가 없음
- `rule_output.py` 변경 0 — Sub-decision D 영구 보존
- PR9-A `active_contradictions_for_claim` asc 동작 — 변경 없음 (PR24-N 의 source)
- PR11-C freshness modifier 의미 — 변경 없음 (active 1 케이스로 검증, 회귀 테스트)
- PR11-C invariant ("older strong is irrelevant to freshness") — 보존, count 강도만 갱신
- PR12-D + PR23-M gap modifier 의미 — 변경 없음 (active 무관 케이스 검증)
- PR20-F rule_stats modifier 의미 — 변경 없음
- PR21-L evidence_type modifier 의미 — 변경 없음
- PR22-S strict validation API — 변경 없음
- PR10-A refute / PR11-B refute_by_freshness 동작 — 변경 없음
- PR17 round-trip identity — 보존 (engine state 변경 없으므로 자동)
- PR18-K migration framework — 변경 없음 (snapshot schema 변경 없음)

## 불변식 (테스트로 잠금)

신규 테스트 파일 `tests/test_engine_count_strength_averaging.py` — 7 클래스, 44 tests.

### TestCountStrengthAveragingThreshold (4) — Sub-decision AV/AW
- `_count_modifier_for_claim` 존재
- active 0 → 1.0
- active 1 (strength any) → 1.0 (threshold 미달)
- active 2 + avg 0.8 → 0.8 (entry)

### TestCountStrengthAveragingContinuous (6) — Sub-decision AX/AY/BB
- active 2 avg 0.0 → 1.0 ★ ("빈 강도 = 압력 아님")
- active 2 avg 0.4 → 0.9
- active 2 avg 0.8 → 0.8 (중심점 보존)
- active 2 avg 1.0 → 0.75
- active 3 avg 0.5333... → continuous
- order-independence (avg 동일 시 결과 동일)

### TestCountStrengthAveragingBoundaries (3) — Sub-decision AX
- never > 1.0 (no boost)
- 0.75 hard floor
- range `[0.75, 1.0]` for sample values

### TestCountStrengthAveragingComposition (6) — formula shape
- active 2 strength 0/0 → effective 1.0 (PR19-E 0.8 자연 만료)
- active 2 avg 0.4 → continuous
- avg 0.8 중심점 보존 (PR11-C × PR24-N composition)
- avg 1.0 → 0.75 floor 적용
- disputed + active 2 strength 0/0 + 1 gap → 0.45 (PR19-E 0.72 자연 만료 X, gap만 0.9 적용)
- 7-modifier full composition (avg 1.0)

### TestCountStrengthAveragingSourceSemantics (3) — Sub-decision AV/AW/BB
- resolved contradictions 는 average 에서 제외 (PR9-A active 정신)
- direct non-contradiction evidence 는 count 에 안 들어감
- freshness (recent 1) 와 count (avg) 역할 분리

### TestCountStrengthAveragingNoStateMutation (4) — read-only
- helper 호출 전후 snapshot 동일
- compute 호출 전후 snapshot 동일
- lifecycle history 변경 없음
- contradiction set 변경 없음

### TestCountStrengthAveragingSnapshot (4) — Sub-decision BA
- schema_version 2 유지
- round-trip 후 strength-averaged behavior 동일
- 원본 strength 값 보존
- snapshot shape 에 count state 키 미존재

### TestCountStrengthAveragingPrivateAndPublicSurface (5) — Sub-decision AZ/BA
- `_COUNT_STRENGTH_PENALTY_WEIGHT == 0.25` private
- 구 `_COUNT_PENALTY_MODIFIER` 제거됨
- ragcore / ragcore.types 미노출
- claim_status 상수 변경 없음

### TestCountStrengthAveragingRegressionBoundaries (9) — PR1~PR23-M 보존
- PR11-C freshness active 1 / PR23-M gap tier / PR20-F rule_stats / PR21-L evidence_type / PR22-S strict / PR10-A refute / PR11-B refute_by_freshness / PR9-A asc / effective ≤ base

## 테스트 결과

```text
102차 docs-only            : 827 passing
103차 test-first           : 신규 44 (25 fail + 19 pass), 기존 827 회귀 0
                            → 846 passed + 25 failed
104차 feat impl + 자연 만료 : 25/25 fail 정확히 pass 전환
                              + PR19-E 자연 만료 테스트 14 개 expected 갱신
                            → 871 passed, 0 fail
105차 docs-only            : 871 passed, 0 fail 유지
```

### 103차 fail-to-pass mapping (25 fail → 25 pass)

| 차단 영역 | Fail 수 | 104차 메커니즘 |
|---|---|---|
| Helper missing (AttributeError) | 17 | `_count_modifier_for_claim` 신규 |
| PR19-E binary 적용으로 expected 불일치 | 5 | Helper 호출 + avg 공식 |
| Snapshot round-trip restored 도 binary | 1 | engine state 무변경, restored 도 자동 |
| `_COUNT_STRENGTH_PENALTY_WEIGHT` 부재 | 1 | 신규 private 상수 |
| 구 `_COUNT_PENALTY_MODIFIER` 잔존 | 1 | 제거 |

## 변경 파일

| 파일 | 변경 | 차수 |
|---|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | +369 (§36 신규) | 102 |
| `tests/test_engine_count_strength_averaging.py` | +611 (신규, 44 tests) | 103 |
| `ragcore/engine.py` | helper 신규 + 상수 교체 + compute 본문 1라인 교체 | 104 |
| `tests/test_engine_count_modifier.py` | 4 expected 갱신 | 104 |
| `tests/test_engine_effective_freshness_modifier.py` | 1 expected 갱신 (PR11-C invariant 보존) | 104 |
| `tests/test_engine_rule_stats_modifier.py` | 3 expected 갱신 | 104 |
| `tests/test_engine_evidence_type_modifier.py` | 3 expected 갱신 | 104 |
| `tests/test_engine_gap_severity_tiering.py` | 3 expected 갱신 | 104 |
| `docs/dev/PR_024_COUNT_STRENGTH_AVERAGING_MVP.md` | 신규 | 105 |

## 구현 요약 (engine.py)

```python
# Private constants (module-level) — Sub-decision AZ
# Removed
_COUNT_PENALTY_MODIFIER = 0.8

# Added
_COUNT_STRENGTH_PENALTY_WEIGHT = 0.25

# Helper (Engine method) — Sub-decision AV~BB
def _count_modifier_for_claim(self, claim_id: int) -> float:
    active = self.active_contradictions_for_claim(claim_id)
    if len(active) < 2:
        return 1.0
    average_strength = sum(
        self._evidences[evidence_id].strength.value
        for evidence_id in active
    ) / len(active)
    return 1.0 - average_strength * _COUNT_STRENGTH_PENALTY_WEIGHT

# compute_effective_confidence count 항 한 줄 교체
count_modifier = self._count_modifier_for_claim(claim_id)

# ScoreValue 곱셈은 PR21-L 과 동일 — 항 추가 없음
return ScoreValue(
    claim.base_confidence.value
    * status_modifier * freshness_modifier * gap_modifier
    * count_modifier * rule_stats_modifier
    * evidence_type_modifier
)
```

## Out of Scope (PR24-N 외)

| 제외 | 이유 / 향후 |
|---|---|
| active count 1 에도 count modifier 적용 | Sub-decision AV / AW — PR11-C 영역 |
| Max strength 사용 (`max(strengths)`) | average 정신, 별도 PR (의미가 다름) |
| Sum strength 사용 (`sum(strengths)`) | average 정신, threshold 효과 흐림 |
| Source diversity (서로 다른 source 가중치) | independence_class 정의 필요, 별도 PR |
| `independence_class` 기반 count | 별도 PR |
| Contradiction type 별 weight | 별도 PR — taxonomy 소유 회피 (Sub-decision AF 정신) |
| Penalty weight 조정 (0.25 → 다른 값) | MVP 잠금 |
| `f(count)` 비선형 함수 결합 | 별도 PR |
| Resolved contradiction 도 약하게 반영 | PR9-A active 정신 — resolved 는 제외 |
| Lifecycle 전이 (count → refuted 자동) | Sub-decision AQ 정신 (PR23-M) |
| Snapshot schema v3 bump | Sub-decision BA — state shape 무변화 |
| Public `_COUNT_STRENGTH_PENALTY_WEIGHT` export | Sub-decision AZ — engine 내부 private |
| RuleStats outcome ratio (Q/R 트랙) | 별도 PR |
| `rule_output.py` 변경 | Sub-decision D 영구 |
| Per-rule / per-claim weight override | engine-global weight 만 |

## 다음 PR 후보

PR24-N 닫음 후 PR25+ 후보 (사용자 결정 대기):

- **PR25 후보 T — unregister/clear hint API** (가장 작음): PR22-S 가 OOS 로 남긴 `unregister_hint_evidence_types` / `clear_hint_evidence_types`.
- **PR25 후보 G — superseded/retracted 상태**: types.py / __init__.py 손대야 함, **사용자 명시 승인 필요**.
- **PR25 후보 J — multi-rule claim composition**: prior 합성 규칙.
- **PR25 후보 O — rule version pinning**: rule update 시 claim 영향도.
- **PR25 후보 P — external integration spec**: 외부 소비자 패키지 계약.
- **PR25 후보 Q — rule_stats outcome ratio**: claim lifecycle 결과 역전파 (대규모).
- **PR25 후보 R — rule_stats observed_precision 사용**: 기존 필드를 modifier 에 반영.

권고: **T (가장 작음, PR21-L+PR22-S 영역 마무리)** 또는 **R (PR20-F 자연 후속,
이미 RuleStats 필드 존재)**.

## Spec Reference

- §36 (Count modifier — strength averaging, PR24-N)
- §35 (Gap modifier severity tiering, PR23-M) — 동일 정제 패턴 (binary → tier/continuous)
- §34 (Evidence_type registration strict validation, PR22-S)
- §33 (Evidence_type modifier MVP, PR21-L)
- §32 (Rule_stats modifier MVP, PR20-F)
- §31 (Count modifier MVP, PR19-E) — PR24-N 의 자연 후속
- §30 (Snapshot migration framework, PR18-K) — 무영향
- §29 (Persistence MVP, PR17)
- §28 (Gap modifier MVP, PR12-D)
- §26 (Evidence freshness modifier, PR11-C)
- §24 (Effective confidence, PR11-D)

## How to Run

```bash
# PR24-N invariants 만
pytest tests/test_engine_count_strength_averaging.py -v

# 전체
pytest -q
```

## Self-review

- [x] 103차 의도 fail 25개 → 104차 25/25 pass 정확히 전환
- [x] 103차 pass 19개 유지
- [x] 기존 827 회귀 0
- [x] 최종 871 passing, 0 fail
- [x] `_COUNT_PENALTY_MODIFIER` 제거
- [x] `_COUNT_STRENGTH_PENALTY_WEIGHT = 0.25` 신규
- [x] `_count_modifier_for_claim` helper 신규
- [x] `compute_effective_confidence` count 항 helper 호출 교체
- [x] active count < 2 → 1.0 (threshold 보존)
- [x] active count >= 2 → 1.0 - avg × 0.25
- [x] avg 0.8 → 0.8 (PR19-E 중심점 보존)
- [x] avg 0.0 → 1.0 (의미 변화, 코멘트 명시)
- [x] resolved contradiction 은 average 에서 제외 (PR9-A active 정신)
- [x] `Evidence` / `Claim` / `Gap` dataclass 변경 없음
- [x] snapshot schema_version 2 유지
- [x] public namespace 신규 export 0
- [x] `types.py` / `__init__.py` / `rule_output.py` 변경 0
- [x] lifecycle / refute / contradiction 변경 없음
- [x] 7-modifier formula shape 유지
- [x] PR19-E 자연 만료 테스트 14 개 명시 코멘트 갱신
- [x] PR11-C / PR12-D + PR23-M / PR20-F / PR21-L / PR22-S regression boundaries 검증
- [x] 5 PR cycle push 패턴 적용 (102/103/104차 push, PR #24 자동 갱신)

## Result

```text
Before PR24-N (main = 2eeaa35):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  count_modifier (binary): active_count >= 2 → 0.8, 그 외 → 1.0
  827 passing

After PR24-N (main = <new sha>):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  (formula shape unchanged)
  count_modifier (continuous): active_count >= 2 → 1.0 - avg × 0.25, 그 외 → 1.0
  871 passing, 0 fail
```

7-modifier composition formula shape 보존. count 항만 binary → strength
average continuous 로 정제. **PR24-N 의 본질은 count 의미 확장이 아니라
PR19-E binary repeated pressure 의 average-strength continuous 정제다.**

PR23-M (gap binary → tier) 와 PR24-N (count binary → continuous) 은 같은
정제 패턴 — modifier 의 의미 자체는 보존하고 강도 분포만 정밀화. 두 PR 의
정제 후 modifier 강도 분포는 자연스럽게 **gap > count** 순서 보존 (gap floor
0.7 < count floor 0.75).

핵심 명제 다시:

```text
빈 강도의 contradiction 은 repeated pressure 가 아니다.
```
