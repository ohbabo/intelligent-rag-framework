# PR #023 — Gap Severity Tiering MVP (PR23-M)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/gap-severity-tiering-mvp` → `main`
> Base: `212ab2d` (PR22-S merged)
> Tests: 827 passing (local)

## Summary

PR23-M refines the existing gap modifier from binary (0.8 / 1.0) to
count-tiered (1.0 / 0.9 / 0.8 / 0.7).

The effective confidence formula shape remains unchanged:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
```

Only the internal `gap` term changes. PR23-M does **not** introduce a new
`Gap.severity` field, taxonomy enum, LLM-based classification, snapshot
schema bump, lifecycle transition, or public API.

## PR23-M 의 한 줄 정의

> **PR23-M 은 gap 의 의미를 새로 정의하는 PR 이 아니다.**
> **PR23-M 은 이미 존재하는 unresolved gap penalty 를 count tier 로 정제하는 PR 이다.**

PR11-D §24.5 의 modifier 분해 자리에서 **gap 항만** 정제. PR11-C / PR19-E /
PR20-F / PR21-L / PR22-S 의 자리는 그대로. Claim 판단 / lifecycle / refute /
새 Gap 구조 모두 변경 없음.

## 핵심 명제 (§35.2)

```text
Gap severity is derived from unresolved gap count, not from a new taxonomy.
An unresolved gap is still information shortage, not contradiction.
PR23-M only refines the weak gap modifier from binary to tiered.
```

한국어:

```text
gap severity 는 unresolved gap 개수에서 파생되는 신호다.
새 taxonomy 가 아니다.

unresolved gap 은 여전히 "정보 부족" 을 의미하지, "반박" 이 아니다.

PR23-M 은 약한 gap modifier 를 binary 에서 tier 로 정제할 뿐이다.
```

대조:

```text
gap_modifier ≠ "이 Claim 이 틀렸다" (← refute / status 영역)
gap_modifier ≠ "이 Claim 에 반박이 쌓였다" (← count / freshness 영역)
gap_modifier = "이 Claim 에 모이지 못한 evidence 가 몇 개인가?"
```

## Tier table

```text
| unresolved gap count | gap modifier |
|---:|---:|
| 0  | 1.0 |
| 1  | 0.9 |
| 2  | 0.8 |
| 3+ | 0.7 |
```

특징:
- monotonic non-increasing
- 0.7 hard floor — 어떤 count 에서도 0.7 미만 안 됨
- 1 gap 강도가 PR12-D binary 0.8 보다 약함 (0.9) — "1 gap 은 약한 정보 부족"
- 2 gap 강도가 PR12-D binary 와 동일 (0.8) — 기존 정의의 자연 지점
- 3+ 누적 불확실성이지만 contradiction (status disputed=0.5) 보다는 약함

## 7-Modifier Composition (formula shape 보존)

```python
effective_confidence(claim) = (
    base_confidence                              # PR1
    × status_modifier(claim.status)              # PR11-D
    × freshness_modifier(claim_id)               # PR11-C
    × gap_modifier(claim_id)                     # PR12-D → PR23-M (내부만 변경)
    × count_modifier(claim_id)                   # PR19-E
    × rule_stats_modifier(claim)                 # PR20-F
    × evidence_type_modifier(claim_id)           # PR21-L (PR22-S 강화 후)
)
```

| modifier | PR | 형태 | 강도 |
|---|---|---|---|
| status_modifier | PR11-D | 4 값 (1.0/1.0/0.5/0.0) | 강 |
| freshness_modifier | PR11-C | continuous (1 - s × 0.5) | 중 |
| **gap_modifier** | **PR12-D + PR23-M** | **tier (1.0 / 0.9 / 0.8 / 0.7)** | **약 (정제)** |
| count_modifier | PR19-E | binary (0.8 / 1.0) | 약 |
| rule_stats_modifier | PR20-F | binary (0.9 / 1.0) | 매우 약 |
| evidence_type_modifier | PR21-L | binary (0.9 / 1.0) | 매우 약 |

PR23-M 후 modifier 강도 순위에서 **gap 항만 tier 로 진화** — 다른 행 무변화.

## 닫힌 흐름 (PR23-M 추가분)

```text
add_gap(claim_id, ...)
  → self._gaps[gap_id] = Gap(...) (PR4 unchanged)
  → self._claim_gap_refs[claim_id].add(gap_id) (PR4 unchanged)

resolve_gaps_for_evidence(evidence_id)
  → self._gap_resolutions[gap_id] = evidence_id (PR5 unchanged)

compute_effective_confidence(claim_id)
  → _gap_modifier_for_claim(claim_id) 호출 (신규 helper)
       ├─ unresolved_count = sum(1 for gap_id in _claim_gap_refs[claim_id]
       │                          if gap_id not in _gap_resolutions)
       ├─ 0   → _GAP_TIER_ZERO_UNRESOLVED_MODIFIER (1.0)
       ├─ 1   → _GAP_TIER_ONE_UNRESOLVED_MODIFIER (0.9)
       ├─ 2   → _GAP_TIER_TWO_UNRESOLVED_MODIFIER (0.8)
       └─ 3+  → _GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER (0.7)
  → 기존 6 modifier 와 곱셈 결합 (compute 본문 +1 라인)
  → ScoreValue 반환 (engine state 무변경)
```

## 들어간 커밋 4

```text
98차  3a991c0 docs(contract): define gap severity tiering MVP (§35)
99차  0e7787f test(core):     lock gap severity tiering invariants
100차 82d2f33 feat(engine):   activate gap severity tiering
101차 (이번)   docs(dev):      record PR23 gap severity tiering MVP
```

## 주요 설계 결정

### Sub-decision AO — Severity source = unresolved gap count only

`gap_modifier` 는 **claim 당 unresolved gap 개수** 만 본다.

배제:
- 새 `Gap.severity` 필드 추가
- gap taxonomy enum (critical / major / minor / ...)
- public severity 상수
- LLM 기반 severity 분류
- gap type / rule / evidence_type 별 weight table

이유: PR12-D 가 이미 unresolved gap → effective 의 연결을 만들었다. PR23-M
은 그 연결의 정제 (binary → tier) 만 한다. domain taxonomy 를 도입하는 순간
framework 가 도메인 의미를 소유 — PR21-L Sub-decision AF 정신 위반.

### Sub-decision AP — Tier table

```text
0  → 1.0
1  → 0.9
2  → 0.8
3+ → 0.7
```

monotonic non-increasing + 0.7 hard floor.

### Sub-decision AQ — Information shortage remains weak

- gap modifier 절대 0.0 안 됨 (refute 영역과 분리)
- gap modifier 절대 1.0 초과 안 됨 (Sub-decision AR boost 금지)
- status disputed (0.5) 보다 항상 약함 (`0.7 > 0.5`)
- lifecycle 전이 0 (PR6/PR8 동작 무변화)
- contradiction set 무변화 (PR7/PR10-A 무관)
- lifecycle audit event 0 (PR10-B 무관)

### Sub-decision AR — Formula shape unchanged

7 modifier 항 / 순서 / 곱셈 결합 / `[0.0, 1.0]` 범위 / boost 금지 — 모두
보존. 본 PR 은 `gap_modifier` 의 **내부 계산식** 만 정제.

### Sub-decision AS — `_GAP_PENALTY_MODIFIER` 제거 + 4 tier 상수 도입

```python
# Removed
_GAP_PENALTY_MODIFIER = 0.8

# Added
_GAP_TIER_ZERO_UNRESOLVED_MODIFIER = 1.0
_GAP_TIER_ONE_UNRESOLVED_MODIFIER = 0.9
_GAP_TIER_TWO_UNRESOLVED_MODIFIER = 0.8
_GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER = 0.7
```

PR12-D privacy 테스트 (§28 invariant 23) 는 "ragcore / ragcore.types 에 노출되지
않는지" 만 검사 → 상수 제거 자체에는 영향 없음 (없는 것은 노출되지 않은 것).

### Sub-decision AT — PR12-D 자연 만료 테스트 명시 갱신 (100차 동봉)

PR12-D 의 "1 unresolved gap = binary 0.8" 을 가정한 expected 값들이 자연
만료. PR19-E 가 PR11-C 의 active=2 expected 를 갱신했던 패턴과 동일. 100차
에서 16 개 자연 만료 테스트 갱신 완료:

| 파일 | 갱신 수 |
|---|---|
| `test_engine_gap_modifier.py` | 6 |
| `test_engine_count_modifier.py` | 2 |
| `test_engine_rule_stats_modifier.py` | 3 |
| `test_engine_evidence_type_modifier.py` | 3 |
| `test_engine_persistence.py` | 2 |

특수 케이스: `test_one_or_many_unresolved_same_modifier` (PR12-D Sub-decision
U binary 명제) → `test_one_vs_many_unresolved_apply_different_tiers` (PR23-M
tier 분화 명제) 로 의미 자체 갱신. PR12-D 의 "unresolved → attenuation"
의미는 모든 갱신본에 명시 코멘트로 보존.

### Sub-decision AU — Snapshot schema bump 없음

```text
_CURRENT_SNAPSHOT_SCHEMA_VERSION = 2  (그대로)
_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = frozenset({1, 2})  (그대로)
```

PR23-M 은 engine state shape 를 바꾸지 않는다:
- `_gaps` / `_gap_resolutions` / `_claim_gap_refs` 구조 동일
- `Gap` dataclass 구조 동일 (`severity` 필드 활용 안 함 — Sub-decision AO 정신)
- snapshot 직렬화 형식 동일

오직 `compute_effective_confidence` 의 `gap_modifier` 계산식만 변경.
PR18-K 정신: 의미 있는 변화 때만 bump.

### PR1~PR22-S 정합

- `types.py` 변경 0 — Sub-decision D 영구 보존
- `__init__.py` 변경 0 — public export 추가 없음
- `rule_output.py` 변경 0 — Sub-decision D 영구 보존
- PR5 `gap_resolution` 동작 — 무변화 (helper 가 read-only)
- PR11-C freshness modifier 의미 — 변경 0
- PR12-D 의 "unresolved → attenuation" 의미 — 보존, 강도만 갱신
- PR19-E count modifier 의미 — 변경 0
- PR20-F rule_stats modifier 의미 — 변경 0
- PR21-L evidence_type modifier 의미 — 변경 0
- PR22-S strict validation — 변경 0
- PR17 round-trip identity — 보존
- PR18-K migration framework — 변경 0 (snapshot schema 변경 없음)
- PR9-A `active_contradictions_for_claim` asc 동작 — 변경 0
- PR10-A refute / PR11-B refute_by_freshness 동작 — 변경 0

## 불변식 (테스트로 잠금)

§35.13 의 48 invariants. 99차에서 잠금, 100차 통과로 입증. 신규 테스트 파일
47 tests (7 클래스).

### Tier mapping (Sub-decision AP)
1. 0 unresolved → 1.0
2. no gaps → 1.0
3. 1 unresolved → 0.9 ★
4. 2 unresolved → 0.8
5. 3 unresolved → 0.7 ★
6. 10 unresolved → 0.7 ★ (3+ tier 통합)
7. 100 unresolved → 0.7 ★ (open-ended)

### Resolution semantics (PR12-D 정신 보존)
8. 3 gaps 모두 resolved → 1.0
9. 3 gaps, 2 resolved + 1 unresolved → 0.9 ★
10. 3 gaps, 1 resolved + 2 unresolved → 0.8
11. gap resolution 후 modifier 자동 복구 ★

### Monotonicity / boundary
12. tier monotonic non-increasing
13. 0.7 hard floor (20 unresolved 도 0.7) ★
14. gap modifier 절대 0.0 안 됨
15. gap modifier 절대 1.0 초과 안 됨

### Composition (status × freshness × gap × count × rule_stats × evidence_type)
16. refuted + N gaps → 0.0 (status dominate)
17. disputed + 1 unresolved → base × 0.5 × 0.9 = 0.45 ★
18. disputed + 2 unresolved → base × 0.5 × 0.8 = 0.40
19. confirmed + freshness 0.6 + 1 unresolved → base × 0.6 × 0.9 = 0.54 ★
20. candidate + 2 unresolved + active 2 → base × 0.8 × 0.8 = 0.64
21. **7-modifier full composition** (disputed + active 2 (most 0.8) + 3 unresolved + firing 1 + hint-only):
    `base × 0.5 × 0.6 × 0.7 × 0.8 × 0.9 × 0.9 = base × 0.13608` ★

### No state mutation (Sub-decision AQ)
22. `to_snapshot()` identical before/after compute
23. `_gaps` / `_gap_resolutions` / `_claim_gap_refs` 변경 없음
24. `_lifecycle_seq` 변경 없음
25. lifecycle history 변경 없음
26. contradiction set 변경 없음

### Snapshot / formula shape (Sub-decision AU + AR)
27. `to_snapshot()["schema_version"] == 2` 유지
28. snapshot keys 집합 변경 없음
29. round-trip 후 tier 동일하게 적용 ★
30. `Gap` dataclass 구조 변경 없음

### Private constants (Sub-decision AS)
31. `_GAP_TIER_ZERO_UNRESOLVED_MODIFIER == 1.0` private ★
32. `_GAP_TIER_ONE_UNRESOLVED_MODIFIER == 0.9` private ★
33. `_GAP_TIER_TWO_UNRESOLVED_MODIFIER == 0.8` private ★
34. `_GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER == 0.7` private ★
35. 4 개 신규 상수 모두 `ragcore` / `ragcore.types` 에 미노출
36. 구 `_GAP_PENALTY_MODIFIER` 미노출 (제거됨)

### Public namespace (Sub-decision D + AF 정신 보존)
37. `types.py` 변경 없음
38. `__init__.py` 변경 없음
39. `rule_output.py` 변경 없음
40. public namespace 신규 export 0

### Regression boundaries (PR1~PR22-S 보존)
41. PR11-C freshness modifier 의미 보존
42. PR19-E count modifier 의미 보존
43. PR20-F rule_stats modifier 의미 보존
44. PR21-L evidence_type modifier 의미 보존
45. PR22-S strict validation API 의미 보존
46. PR10-A refute / PR11-B refute_by_freshness 동작 무변화
47. PR9-A `active_contradictions_for_claim` asc 동작 무변화
48. PR17 round-trip identity 보존

## 테스트 결과

```text
98차 docs-only            : 780 passing
99차 test-first           : 신규 47 (15 fail + 32 pass), 기존 780 회귀 0
                            → 812 passed + 15 failed
100차 feat impl           : 15/15 fail 정확히 pass 전환
                            + PR12-D 자연 만료 테스트 16 개 expected 갱신
                            → 827 passed, 0 fail
101차 docs-only           : 827 passed, 0 fail 유지
```

### 99차 fail-to-pass mapping

| 차단 영역 | Fail 수 | 100차 메커니즘 |
|---|---|---|
| Tier mapping (1/3/10/100 unresolved) | 4 | `_gap_modifier_for_claim` count 분기 |
| Resolution semantics (2 res + 1 unres / recovery) | 2 | resolved 는 count 제외 |
| Hard floor (20 unresolved → 0.7) | 1 | `if count >= 3 → 0.7` open-ended |
| Composition (disputed/freshness/full-7) | 3 | gap helper 호출 + tier 분기 |
| Snapshot round-trip with 3 gaps | 1 | restored engine 도 tier 적용 |
| Private constants (4 신규 상수) | 4 | 모듈 레벨 상수 추가 |

## Composition 값 갱신 정리 (PR12-D 자연 만료)

| 시나리오 | Before (PR12-D binary) | After (PR23-M tier) |
|---|---:|---:|
| candidate + 1 unresolved | 0.8 | **0.9** |
| confirmed + 1 unresolved | 0.8 | **0.9** |
| disputed + 1 unresolved | 0.4 | **0.45** |
| confirmed + freshness 0.6 + 1 unresolved | 0.48 | **0.54** |
| disputed + active 2 + 1 unresolved | 0.192 | **0.216** |
| 1 unresolved + firing 1 | 0.72 | **0.81** |
| disputed + active 2 + 1 unresolved + firing 1 (6-mod) | 0.1728 | **0.1944** |
| 1 unresolved + hint-only | 0.72 | **0.81** |
| disputed + active 2 + 1 unresolved + firing 1 + hint-only (7-mod) | 0.15552 | **0.17496** |
| round-trip with 1 unresolved | 0.48 | **0.54** |
| "1 vs 10" binary 동일 (PR12-D U) | 0.8 == 0.8 | **0.9 ≠ 0.7** (tier 분화) |

각 갱신 위치에 명시 코멘트:

```python
# PR23-M §35.5 (AP): 1 unresolved → tier 1 → 0.9 (PR12-D binary 0.8 정제).
# 의미 보존, 강도만 갱신.
```

## 변경 파일

| 파일 | 변경 | 차수 |
|---|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | +349 (§35 신규) | 98 |
| `tests/test_engine_gap_severity_tiering.py` | +706 (신규, 47 tests) | 99 |
| `ragcore/engine.py` | +35 / -25 (4 tier 상수 + helper + compute 본문) | 100 |
| `tests/test_engine_gap_modifier.py` | +35 / -14 (PR12-D 자연 만료 6 개) | 100 |
| `tests/test_engine_count_modifier.py` | +15 / -8 (PR19-E composition 2 개) | 100 |
| `tests/test_engine_rule_stats_modifier.py` | +19 / -14 (PR20-F composition 3 개) | 100 |
| `tests/test_engine_evidence_type_modifier.py` | +22 / -12 (PR21-L composition 3 개) | 100 |
| `tests/test_engine_persistence.py` | +14 / -10 (PR17 round-trip 2 개) | 100 |
| `docs/dev/PR_023_GAP_SEVERITY_TIERING_MVP.md` | 신규 | 101 |

## 신규 테스트 그룹

```text
tests/test_engine_gap_severity_tiering.py
  TestGapSeverityTierMapping                       (7 tests — Sub-decision AP)
  TestGapSeverityResolutionSemantics               (4 tests — resolved 제외 + recovery)
  TestGapSeverityMonotonicityAndBoundary           (4 tests — monotonic / 0.7 floor / never 0.0 / never > 1.0)
  TestGapSeverityComposition                       (6 tests — 7-modifier composition)
  TestGapSeverityReadOnly                          (5 tests — no state mutation)
  TestGapSeveritySnapshot                          (4 tests — schema unchanged / round-trip / Gap dataclass)
  TestGapSeverityPrivacyAndRegression              (17 tests — private constants + Sub-decision D + 회귀)
```

## 구현 요약 (engine.py)

```python
# Private constants (module-level) — Sub-decision AS
# Removed
_GAP_PENALTY_MODIFIER = 0.8

# Added
_GAP_TIER_ZERO_UNRESOLVED_MODIFIER = 1.0
_GAP_TIER_ONE_UNRESOLVED_MODIFIER = 0.9
_GAP_TIER_TWO_UNRESOLVED_MODIFIER = 0.8
_GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER = 0.7

# Helper (Engine method)
def _gap_modifier_for_claim(self, claim_id: int) -> float:
    unresolved_gap_count = sum(
        1
        for gap_id in self._claim_gap_refs.get(claim_id, ())
        if gap_id not in self._gap_resolutions
    )
    if unresolved_gap_count == 0:
        return _GAP_TIER_ZERO_UNRESOLVED_MODIFIER
    if unresolved_gap_count == 1:
        return _GAP_TIER_ONE_UNRESOLVED_MODIFIER
    if unresolved_gap_count == 2:
        return _GAP_TIER_TWO_UNRESOLVED_MODIFIER
    return _GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER

# compute_effective_confidence 본문 (gap 항 5 라인 → 1 라인)
gap_modifier = self._gap_modifier_for_claim(claim_id)

# ScoreValue 곱셈은 PR21-L 과 동일 — 항 추가 없음
return ScoreValue(
    claim.base_confidence.value
    * status_modifier * freshness_modifier * gap_modifier
    * count_modifier * rule_stats_modifier
    * evidence_type_modifier
)
```

## Design note

Gap remains a weak confidence signal.

A gap means incomplete information.
A gap does not mean the claim is false.
A gap does not create contradiction.
A gap does not trigger lifecycle transition.

The gap modifier now has a hard floor of `0.7`, which keeps it weaker than
`disputed = 0.5` status modifier — gap penalty never overpowers status
penalty.

## Out of Scope (PR23-M 외)

| 제외 | 이유 / 향후 |
|---|---|
| 새 `Gap.severity` 필드 추가 | Sub-decision AO — types.py 영구 보존 |
| Gap taxonomy enum (critical / major / minor) | Sub-decision AO — taxonomy 소유 금지 |
| Public severity 상수 | Sub-decision D + AS — private 유지 |
| LLM 기반 severity 분류 | Sub-decision AO — domain semantics 회피 |
| Gap type / rule / evidence_type 별 weight table | binary → tier MVP, multi-class weight 별도 PR |
| Lifecycle 전이 (gap → refuted 자동) | Sub-decision AQ 영구 |
| Gap modifier → contradiction 등록 | Sub-decision AQ |
| Tier 경계 조정 (3 → N) | MVP 잠금, 별도 PR |
| Tier 값 조정 (0.9/0.8/0.7 → 다른 값) | MVP 잠금 |
| Continuous gap modifier (`f(count)` 함수) | tier MVP, 별도 PR |
| Resolved gap 도 약하게 감쇠 | Sub-decision AP — resolved 영향 없음 (PR5 정신) |
| Snapshot schema v3 bump | Sub-decision AU — state shape 무변화 |
| Public `_GAP_TIER_*` 상수 export | Sub-decision AS — engine 내부 private |
| Per-rule / per-gap-type tier override | engine-global tier 만 |
| RuleStats outcome ratio (Q/R 트랙) | 별도 PR |
| `rule_output.py` 변경 | Sub-decision D 영구 |

## 다음 PR 후보

PR23-M 닫음 후 PR24+ 후보 (사용자 결정 대기):

- **PR24 후보 N — contradiction strength averaging** (PR19-E 자연 후속): count_modifier 를 N>=2 binary → average strength 기반 continuous.
- **PR24 후보 T — unregister/clear hint API** (PR21-L+PR22-S 닫음, 가장 작음): PR22-S 가 OOS 로 남긴 `unregister_hint_evidence_types` / `clear_hint_evidence_types`.
- **PR24 후보 G — superseded/retracted 상태**: types.py / __init__.py 손대야 함, **사용자 명시 승인 필요**.
- **PR24 후보 J — multi-rule claim composition**: prior 합성 규칙.
- **PR24 후보 O — rule version pinning**: rule update 시 claim 영향도.
- **PR24 후보 P — external integration spec**: 외부 소비자 패키지 계약.
- **PR24 후보 Q — rule_stats outcome ratio**: claim lifecycle 결과 역전파 (대규모).
- **PR24 후보 R — rule_stats observed_precision 사용**: 기존 필드를 modifier 에 반영.

권고: **N (count strength averaging, PR19-E 자연 후속)** — PR23-M 의 gap tier
패턴과 동일하게 PR19-E 의 binary count modifier 도 continuous 로 정제하면 7-modifier
강도 분포가 더 부드러워진다. 또는 **T (가장 작음)** 로 PR21-L+PR22-S 영역 마무리.

## Spec Reference

- §35 (Gap modifier severity tiering, PR23-M)
- §34 (Evidence_type registration strict validation, PR22-S)
- §33 (Evidence_type modifier MVP, PR21-L)
- §32 (Rule_stats modifier MVP, PR20-F)
- §31 (Count modifier MVP, PR19-E)
- §30 (Snapshot migration framework, PR18-K) — 무영향
- §29 (Persistence MVP, PR17)
- §28 (Gap modifier MVP, PR12-D) — PR23-M 의 자연 후속
- §26 (Evidence freshness modifier, PR11-C)
- §24 (Effective confidence, PR11-D)

## How to Run

```bash
# PR23-M invariants 만
pytest tests/test_engine_gap_severity_tiering.py -v

# 전체
pytest -q
```

## Result

```text
Before PR23-M (main = 212ab2d):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  gap_modifier (binary): 0 unresolved → 1.0, 1+ → 0.8
  780 passing

After PR23-M (main = <new sha>):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  (formula shape unchanged)
  gap_modifier (tier): 0 → 1.0, 1 → 0.9, 2 → 0.8, 3+ → 0.7
  827 passing, 0 fail
```

7-modifier composition formula shape 보존. gap 항만 binary → count tier 로
정제. **PR23-M 의 본질은 gap 의미 확장이 아니라 기존 unresolved gap penalty
의 count-tier 정제다.**
