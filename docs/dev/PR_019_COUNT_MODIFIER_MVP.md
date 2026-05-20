# PR #019 — Count Modifier MVP (PR19-E)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/count-modifier-mvp` → `main`
> Base: `0fbba09` (PR18-K merged)
> Tests: 670 passing (local)

## 목적

PR12-D 까지의 흐름:

```text
effective = base × status × freshness × gap
→ active contradiction 의 count dimension 은 effective 에 반영 안 됨
```

PR19-E 추가:

```text
effective = base × status × freshness × gap × count
→ active >= 2 일 때만 0.8 추가 감쇠 (binary supplemental)
```

## PR19-E 의 한 줄 정의

> **PR19-E 는 contradiction strength 를 다시 평가한 PR 이 아니다. PR11-C 가
> 이미 그 역할을 한다. PR19-E 는 active contradiction 이 2 개 이상 누적될
> 때의 repeated-pressure 를 effective_confidence 에 반영한 PR 이다.**

PR11-D §24.5 modifier 분해 자리의 **네 번째 modifier**. PR11-C / PR12-D 다음
5th composition layer.

## 핵심 명제 (§31.2)

```text
Count modifier is binary and supplemental:
one active contradiction is handled by freshness,
multiple active contradictions add repeated-pressure attenuation.
```

한국어:

```text
count modifier 는 이진적이고 보조적인 감쇠다.
활성 반박 1개는 freshness 가 처리하고,
활성 반박이 여러 개일 때만 누적 압력으로 추가 감쇠한다.
```

## 5-Modifier Composition 완성

```python
effective_confidence(claim) = (
    base_confidence                              # PR1
    × status_modifier(claim.status)              # PR11-D §24
    × freshness_modifier(claim_id)               # PR11-C §26
    × gap_modifier(claim_id)                     # PR12-D §28
    × count_modifier(claim_id)                   # PR19-E §31 (신규)
)
```

| modifier | PR | 형태 | 강도 |
|---|---|---|---|
| status_modifier | PR11-D | 4 값 (1.0/1.0/0.5/0.0) | 강 (refuted=0) |
| freshness_modifier | PR11-C | continuous (1 - s × 0.5) | 중 (max 50%) |
| gap_modifier | PR12-D | binary (0.8 / 1.0) | 약 (20%) |
| **count_modifier** | **PR19-E** | **binary (0.8 / 1.0)** | **약 보조** |

## Composition Table

| 시나리오 | effective |
|---|---|
| candidate/confirmed + active 0 + no gap | base |
| candidate/confirmed + active 1 + strong 0.8 | base × 0.6 |
| candidate/confirmed + active 2 + strong 0.8 + no gap | **base × 0.48** |
| candidate/confirmed + active 2 + strong 0.8 + unresolved gap | **base × 0.384** |
| disputed + active 0 + no gap | base × 0.5 |
| disputed + active 2 + strong 0.8 + unresolved gap | **base × 0.192** |
| refuted + any | 0.0 |

## 닫힌 흐름 (PR19-E 추가분)

```python
# 1) active 0 — count = 1.0 (PR12-D 까지의 동작 그대로)
engine = Engine()
_, c = engine.add_entity(...), engine.add_claim(..., base_confidence=1.0)
engine.compute_effective_confidence(c)  # → 1.0 (no contradiction)

# 2) active 1 — PR11-C freshness 단독 (count = 1.0)
ev = engine.add_evidence(claim_id=c, ..., strength=0.8)
engine.register_contradiction(c, ev)
engine.compute_effective_confidence(c)
# → 1.0 × 1.0 (cand) × 0.6 (PR11-C) × 1.0 (no gap) × 1.0 (count, active=1) = 0.6

# 3) active 2 — PR11-C + PR19-E 둘 다 적용 ★
ev2 = engine.add_evidence(claim_id=c, ..., strength=0.3)
engine.register_contradiction(c, ev2)
# active = {ev (0.8), ev2 (0.3)}, most recent = ev2 (strength=0.3)
engine.compute_effective_confidence(c)
# → 1.0 × 1.0 × 0.85 (freshness, recent=0.3) × 1.0 × 0.8 (count, active=2) = 0.68

# 4) Resolved 제외 — active back to 1
engine.register_contradiction_resolution(c, ev2)
# active = {ev (0.8)}, count = 1.0
engine.compute_effective_confidence(c)
# → 1.0 × 1.0 × 0.6 × 1.0 × 1.0 = 0.6 (PR11-C 단독)

# 5) N 무관 — active 10 도 count = 0.8
for _ in range(8):
    extra_ev = engine.add_evidence(...)
    engine.register_contradiction(c, extra_ev)
# active = 9 (ev + 8 extras), 모두 strength=0.5 라고 가정
# count_modifier = 0.8 (active >= 2)
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `efb77cc` | docs(contract): define effective confidence count modifier MVP (§31) |
| 2 | `f6b24a3` | test(core): lock count modifier invariants |
| 3 | `976b4f6` | feat(engine): activate count modifier |
| 4 | (this) | docs(dev): PR19-E record |

## 주요 설계 결정 (§31)

### 1. Sub-decision E-1 — Count 대상

`active_contradictions_for_claim(claim_id)` — PR9-A 차집합 그대로 활용. count
만 보니 정렬 무관 (asc/desc 둘 다 같은 set).

### 2. Sub-decision E-2 — Threshold = 2

**왜 2 인가?**
- active 1 개는 PR11-C freshness modifier 가 이미 처리 (most recent strength)
- 2 개부터 "반박이 누적되고 있다" 는 별도 신호
- PR11-C 와 PR19-E 가 함께 적용되는 case 는 active >= 2 일 때만

### 3. Sub-decision E-3 — Modifier 값 0.8

```python
_COUNT_PENALTY_MODIFIER = 0.8
```

PR12-D `_GAP_PENALTY_MODIFIER = 0.8` 와 같은 값 — "약한 보조 신호" 정신 일관.

### 4. Sub-decision E-4 — Binary, N 무관

```text
active 2 개 → 0.8
active 10 개 → 0.8 (동일)
```

N-dependent / log / saturation 함수는 PR20+ 자연 확장.

### 5. Sub-decision E-5 — Resolved 제외

PR9-A 차집합 의미 활용 — resolved 된 contradiction 은 count 에서 자연 제외.

### 6. Sub-decision E-6 — PR11-C 와 역할 분리

```text
PR11-C freshness_modifier:
- input: most recent active contradiction.strength.value
- 동작: 1.0 - strength × 0.5 (continuous, max 50%)
- 활성화: active ≥ 1

PR19-E count_modifier:
- input: len(active_contradictions_for_claim)
- 동작: 0.8 (binary, if N ≥ 2)
- 활성화: active ≥ 2
```

같은 active set 을 다른 차원에서 본다:
- PR11-C: strength dimension (most recent 한 개)
- PR19-E: count dimension (개수)

### 7. PR1~PR18-K 와의 정합 — 의미 무변화

PR19-E 는 `compute_effective_confidence` 본문에 **곱셈 1개 추가만**.

| | PR19-E 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` / `ScoreValue` / `ClaimLifecycleEvent` dataclass | 없음 |
| PR9-A `active_contradictions_for_claim` (input only) | 없음 |
| PR11-A `active_contradictions_by_freshness` | 없음 |
| 5 lifecycle API + PR11-B sibling | 없음 |
| `register_contradiction*` / PR5 gap_resolution | 없음 |
| All private constants (PR10-A, PR11-D, PR11-C, PR12-D) | 없음 |
| `compute_effective_confidence` 시그니처 | 없음 (본문 곱셈만 추가) |
| PR17 `to_snapshot` / `from_snapshot` round-trip identity | 없음 (engine state 변경 0) |
| PR18-K migration framework | 없음 |
| `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 (Sub-decision D 정합) |
| public exports | 없음 (`_COUNT_PENALTY_MODIFIER` private) |
| 외부 dependency | 없음 |

### 8. PR11-C 기존 테스트 1개 expected 값 업데이트

`test_only_most_recent_active_strength_affects_modifier` (PR11-C, active=2
시나리오) — PR11-C invariant 의미 ("older strong 이 freshness 에 영향 X")
그대로 보존하면서 expected 값 PR19-E composition 반영:

```text
expected 0.9 → 0.72 (= 0.9 × 0.8, count_modifier 추가 적용)

invariant 의미 (older 영향 없음) 검증 로직:
  PR19-E 도 적용된 경우:
    older 영향 있다면: 1.0 × 1.0 × 0.5 × 1.0 × 0.8 = 0.4
    older 영향 없으면: 1.0 × 1.0 × 0.9 × 1.0 × 0.8 = 0.72
  → 0.72 ≠ 0.4 이므로 older 영향 없음 유지 검증
```

PR11-C 의 의미는 변경 0. composition 확장만 반영.

## 불변식 (테스트로 잠금)

§31.12 의 21 invariant:

1. unknown claim_id → `KeyError`
2~3. active 0 + 2 status → base (count = 1.0)
4. **active 1 + freshness 만 (count = 1.0) ★**
5. **active 2 + count 0.8 추가 감쇠 ★**
6. active 2 + confirmed + strength 0.8 → base × 0.48
7. **active 10 + count = 0.8 (N 무관, Sub-decision E-4) ★**
8. active 2 + refuted → 0.0 (Sub-decision P)
9. **5-modifier 결합 (disputed + active 2 + gap) → base × 0.192 ★**
10. **Resolved 제외 (3 중 2 resolved → active 1 → count 1.0) ★**
11~15. PR11-C / PR12-D / PR10-A / PR11-B / PR9-A 무변화
16. effective ≤ base (no boost)
17. compute is read-only
18. determinism
19. **PR17 round-trip identity 보존 ★**
20. `_COUNT_PENALTY_MODIFIER` private
21. 기존 652 회귀 없음

## 테스트

**670 passing** in ~0.46s (652 → 670, delta 정확히 +18)

### Test-first 흐름 (PR12-D 71차 동일 mixed pattern)

83차 (test-first 잠금):

```text
18 새 tests 추가
실행 결과 (의도된 mixed 분포):
- 4 fails (의도된 assertion — count_modifier 미적용):
    * test_active_two_applies_count_modifier              (expected 0.8, actual 1.0)
    * test_active_two_confirmed_with_strong_freshness     (expected 0.48, actual 0.6)
    * test_n_invariant_two_vs_ten_same_count_modifier     (Sub-decision E-4)
    * test_disputed_with_active_two_and_unresolved_gap    (5-modifier expected 0.192)
- 14 pass (이미 정합):
    * TestEffectiveConfidenceCountModifier (4)
    * TestCountModifierThreshold (1, active 1)
    * TestCountModifierResolvedIsolation (1)
    * TestCountModifierPriorBehaviorUnchanged (5)
    * TestCountModifierPersistenceRoundtrip (1)
    * TestCountModifierPrivacy (2)
+ 기존 652 통과
```

84차 (구현):

```text
- ragcore/engine.py:
    _COUNT_PENALTY_MODIFIER = 0.8 (private)
    compute_effective_confidence 본문에 × count_modifier 추가
- PR11-C 기존 테스트 1개 expected 값 업데이트 (invariant 의미 보존)
실행 결과: 670 통과 (4 fail → 4 pass, 14 pass 유지)
```

### 변경 파일 (PR19-E 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §31 신설 (+259 lines) |
| `tests/test_engine_count_modifier.py` | 신규 (18 tests, +365 lines) |
| `ragcore/engine.py` | 1 private constant + 본문 확장 (+25, -6) |
| `tests/test_engine_effective_freshness_modifier.py` | 1 expected 값 + 코멘트 업데이트 (+15, -9) |
| `docs/dev/PR_019_COUNT_MODIFIER_MVP.md` | 이 파일 (신규) |
| `ragcore/types.py` | **변경 없음** |
| `ragcore/__init__.py` | **변경 없음** |
| `ragcore/rule_output.py` | **변경 없음** (Sub-decision D 정합) |

### 테스트 분포

| 파일 | PR18-K 후 | PR19-E (83차) | PR19-E (84차) | 변동 |
|---|---|---|---|---|
| `test_engine_count_modifier.py` | 0 | 18 (4 fail + 14 pass) | **18 (pass)** | +18 |
| 나머지 23 파일 | 652 | 652 | 652 (PR11-C 테스트 1개 expected 업데이트) | 0 |
| **Total** | 652 | 652 + 14 pass + 4 fail | **670** | **+18** |

### 신규 테스트 그룹

**TestEffectiveConfidenceCountModifier (5):** KeyError + active 0 × 2 status + active 2 + refuted+active 2
**TestCountModifierThreshold (3):** active 1 freshness only + active 2 + N 무관 (Sub-decision E-4)
**TestCountModifierResolvedIsolation (1):** Resolved 제외 (Sub-decision E-5)
**TestCountModifierComposition (1):** 5-modifier 결합 (disputed + active 2 + gap)
**TestCountModifierPriorBehaviorUnchanged (5):** PR11-C / PR12-D / PR10-A / PR11-B / PR9-A 무변화
**TestCountModifierPersistenceRoundtrip (1):** PR17 round-trip identity 보존
**TestCountModifierPrivacy (2):** `_COUNT_PENALTY_MODIFIER` 미노출

## 구현 요약 (84차)

```python
# ragcore/engine.py (module level — _GAP_PENALTY_MODIFIER 다음)
_COUNT_PENALTY_MODIFIER = 0.8  # Sub-decision E-3, private

# compute_effective_confidence 본문 (시그니처 / KeyError 그대로)
def compute_effective_confidence(self, claim_id):
    if claim_id not in self._claims:
        raise KeyError(...)
    claim = self._claims[claim_id]
    status_modifier = _STATUS_TO_MODIFIER[claim.status]      # PR11-D

    active = self.active_contradictions_by_freshness(claim_id)
    if not active:
        freshness_modifier = 1.0
    else:
        most_recent_evidence = self._evidences[active[0]]
        freshness_modifier = (
            1.0 - most_recent_evidence.strength.value * _FRESHNESS_PENALTY_WEIGHT
        )

    gaps = self.gaps_for_claim(claim_id)
    if not gaps:
        gap_modifier = 1.0
    elif all(self.gap_resolution(g.id) is not None for g in gaps):
        gap_modifier = 1.0
    else:
        gap_modifier = _GAP_PENALTY_MODIFIER

    # PR19-E §31 신규
    active_count = len(self.active_contradictions_for_claim(claim_id))
    count_modifier = (
        _COUNT_PENALTY_MODIFIER if active_count >= 2 else 1.0
    )

    return ScoreValue(
        claim.base_confidence.value
        * status_modifier
        * freshness_modifier
        * gap_modifier
        * count_modifier
    )
```

`types.py` / `__init__.py` / `rule_output.py` 변경 0.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| N-dependent decay (`f(N)` 형태) | Sub-decision E-4 (binary) |
| Log / count 비선형 함수 | 단순성 정신, PR20+ |
| Independence_class 기반 count | PR20+ |
| Strength 합산 / weighted count | freshness 와 의미 중복 위험 |
| Source diversity | PR20+ |
| RuleStats 결합 (F 자리) | PR20+ |
| PR10-A refute 정책 변경 | 본 PR 범위 밖 |
| 새 lifecycle 상태 (G 자리) | 별도 |
| Confidence boost (> 1.0) | PR11-D Sub-decision N 영구 OOS |
| Public `_COUNT_PENALTY_MODIFIER` | engine 내부 private |
| Wall-clock timestamp | 영구 OOS |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| F | **RuleStats-based modifier** — `observed_precision` / `false_positive_rate` (6th modifier) | 중 (5-modifier 자연 후속) |
| G | **superseded/retracted 추가 상태** | 중 (도메인 운영 의미) |
| J | **Gap freshness / type-aware modifier** — PR12-D 정교화 | 중 |
| L | **File IO wrapper** — `to_file(path)` / `from_file(path)` | 낮음 |
| M | **fire_rule audit** — PR10-B 확장 | 중 |
| N | Engine bulk fire / `not` combinator / trace 직렬화 | 낮음 |
| O | C/Rust hot loop port (Phase 5) | 낮음 |
| P | 첫 schema 변경 (v1 → v2) — PR18-K framework 첫 실사용 | (도메인 요구 명확해진 뒤) |

추천: **F (RuleStats modifier)** 또는 **G (superseded/retracted)**.

F 는 5-modifier composition 자연 후속 — `effective = base × status × freshness
× gap × count × rule_stats`. PR2 의 `RuleStats.observed_precision` / `false_positive_rate`
를 활용. 도메인 입력 무관.

G 는 도메인 운영 의미 (취소 / 대체) 가 확정되면.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §31](../contracts/05_DATA_CONTRACT_MVP.md) — Count modifier (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §28](../contracts/05_DATA_CONTRACT_MVP.md) — Gap modifier (PR12-D)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §26](../contracts/05_DATA_CONTRACT_MVP.md) — Freshness modifier (PR11-C)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §24](../contracts/05_DATA_CONTRACT_MVP.md) — Effective confidence (PR11-D base)
- [docs/dev/PR_014_EFFECTIVE_FRESHNESS_MODIFIER_MVP.md](PR_014_EFFECTIVE_FRESHNESS_MODIFIER_MVP.md)
- [docs/dev/PR_016_GAP_MODIFIER_MVP.md](PR_016_GAP_MODIFIER_MVP.md)
- [docs/dev/PR_018_SNAPSHOT_MIGRATION_MVP.md](PR_018_SNAPSHOT_MIGRATION_MVP.md) — PR18-K base (이전 PR)

## How to Run

```bash
git checkout feat/count-modifier-mvp
pip install -e .
pytest -v
```

670 tests in ~0.46s. No new external dependencies.

## Result

PR19-E 가 PR11-D 의 modifier 분해 자리에 네 번째 modifier 추가. **5-modifier
composition 완성**:

```python
effective = base × status × freshness × gap × count
```

PR1~PR19-E 의 modifier composition 진화:

```text
PR11-D: effective = base × status_modifier            (stub 활성화)
PR11-C: + × freshness_modifier (continuous attenuation)
PR12-D: + × gap_modifier (binary weak)
PR19-E: + × count_modifier (binary supplemental) ★
```

의미 강도 분리:
- status_modifier: refuted=0.0, disputed=0.5 (강)
- freshness_modifier: max 50% 감쇠 (중)
- gap_modifier: 20% 감쇠 (약)
- **count_modifier: 20% 감쇠 (약 보조)**

PR11-C 와 PR19-E 의 역할 분리:
- active = 0 → 둘 다 1.0
- active = 1 → freshness=strength-based, count = 1.0 (PR11-C 단독)
- active ≥ 2 → freshness=most-recent, count = 0.8 (둘 다 활성화)

PR19-E 의 본질:

> **"contradiction strength 를 다시 평가한 PR 이 아니라, active contradiction
> 이 2 개 이상 누적될 때의 repeated-pressure 를 effective confidence 에
> 반영한 PR."**

PR11-C 와 의미 분리 + PR12-D 의 binary weak modifier 패턴 재사용. 5-modifier
composition 완성.
