# PR #014 — Effective Freshness Modifier MVP (PR11-C)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/effective-freshness-modifier-mvp` → `main`
> Base: `d9b0685` (PR11-A merged)
> Tests: 564 passing (local)

## 목적

PR11-D 까지의 흐름:

```text
effective = base × status_modifier
→ status 만 scoring 에 반영. active contradiction strength 는 무관.
```

PR11-A 까지:

```text
evidence_freshness / active_contradictions_by_freshness query 추가.
하지만 어떤 정책도 freshness 사용 안 함.
```

PR11-C 추가:

```text
effective = base × status_modifier × freshness_modifier
freshness_modifier 는 가장 최근 active contradiction 의 strength 만 본다.
→ PR11-A 가 노출한 query 를 PR11-D modifier 분해에 input 으로 통합.
```

## PR11-C 의 한 줄 정의

> **PR11-C 는 confidence 를 0 까지 죽이는 PR 이 아니라, 최신 active
> contradiction 이 있을 때 보수적으로 감쇠하는 PR 이다. 완전한 부정은 여전히
> PR10-A 의 `refute_disputed_claim_if_ready` 가 담당한다.**

> **PR11-C 는 freshness query 를 effective confidence 에 처음 연결한 PR.**

PR11-D §24.5 의 명시적 미래 자리 ("미래 정책 도입 시 modifier 분해 가능") 의
첫 활용. PR11-A 가 노출한 query (noun) 를 PR11-C 가 modifier 분해에 통합
(verb).

## 핵심 명제 (§26.2)

```text
Effective confidence under freshness modifier is continuous attenuation,
not a binary kill.

같은 active contradiction strength 가 두 정책의 input 이지만 의미가 다르다:
  - PR10-A: strength >= 0.8 → status 전이 (binary, threshold)
  - PR11-C: strength → effective 감쇠 (continuous, modifier)

PR11-C 는 PR10-A refute 정책 / PR11-A freshness query /
PR9-A active contradiction 의미를 변경하지 않는다.
```

## 공식 (§26.3) — modifier 분해

```python
effective_confidence(claim) = (
    base_confidence
    × status_modifier(claim.status)         # PR11-D §24 그대로
    × freshness_modifier(claim_id)           # PR11-C 신규
)
```

`status_modifier` (PR11-D, 변경 없음):

| status | modifier |
|---|---|
| `CANDIDATE` | 1.0 |
| `CONFIRMED` | 1.0 |
| `DISPUTED` | 0.5 |
| `REFUTED` | 0.0 |

`freshness_modifier` (PR11-C 신규):

```python
freshness_modifier(claim_id) = (
    1.0
    if active_contradictions_by_freshness(claim_id) == ()
    else 1.0 - (most_recent_evidence.strength.value × _FRESHNESS_PENALTY_WEIGHT)
)
```

`_FRESHNESS_PENALTY_WEIGHT = 0.5` (engine 내부 private).

| `most_recent.strength.value` | `freshness_modifier` |
|---|---|
| 0.0 | 1.0 (감쇠 없음) |
| 0.5 | 0.75 |
| 0.8 | 0.6 |
| 1.0 | 0.5 (최대 감쇠) |

## Modifier composition 표

| Claim status | active 0 | active strength 0.8 | active strength 1.0 |
|---|---|---|---|
| candidate | base | base × 0.6 | base × 0.5 |
| confirmed | base | base × 0.6 | base × 0.5 |
| disputed | base × 0.5 | base × 0.3 | base × 0.25 |
| refuted | 0.0 | 0.0 | 0.0 |

## 닫힌 흐름 (PR11-C 추가분)

```python
# 1) candidate Claim, base=1.0
claim = engine.add_claim(..., base_confidence=1.0)
engine.compute_effective_confidence(claim)  # → 1.0  (status × 1.0, no active)

# 2) Strong contradiction 등록
ev = engine.add_evidence(..., strength=0.8)
engine.register_contradiction(claim, ev)
engine.compute_effective_confidence(claim)
# candidate × active 0.8 → 1.0 × 1.0 × (1.0 - 0.8 × 0.5) = 1.0 × 0.6 = 0.6

# 3) Confirmed
engine._claims[claim] = replace(..., status=CONFIRMED)
engine.compute_effective_confidence(claim)
# confirmed × active 0.8 → 1.0 × 1.0 × 0.6 = 0.6

# 4) Disputed (white-box 또는 dispute_if_ready)
engine._claims[claim] = replace(..., status=DISPUTED)
engine.compute_effective_confidence(claim)
# disputed × active 0.8 → 1.0 × 0.5 × 0.6 = 0.3

# 5) PR10-A 가 refute 트리거
engine.refute_disputed_claim_if_ready(claim)  # strength 0.8 >= 0.8 → refuted
engine.compute_effective_confidence(claim)
# refuted × any → 1.0 × 0.0 × X = 0.0 (Sub-decision P)
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `9ccfb98` | docs(contract): define effective confidence freshness modifier MVP (§26) |
| 2 | `ee15195` | test(core): lock effective confidence freshness invariants |
| 3 | `2095d9d` | feat(engine): activate freshness modifier |
| 4 | (this) | docs(dev): PR11-C record |

## 주요 설계 결정 (§26)

### 1. Sub-decision O — 최신 1개만 사용

`freshness_modifier` 는 `active_contradictions_by_freshness(c)` 의 **첫 번째
(가장 최근) evidence 하나만** 본다.

| 옵션 | 채택 | 이유 |
|---|---|---|
| **(O-most-recent-only)** | ✓ | 가장 작은 잠금. PR10-A 단순성 정신 |
| (O-all-weighted-sum) 모든 active 가중합 | ✗ | 결정 부담 큼 |
| (O-max-strength) max strength | ✗ | freshness 의미 무시, PR10-A 와 중복 |
| (O-rank-weighted) freshness rank weighting | ✗ | rank 정의 부담 |
| (O-older-strong) older strong evidence 고려 | ✗ | "최근" 정의 모순 |

### 2. Sub-decision P — refuted 시 0 보존

```python
# refuted:
#   status_modifier = 0.0
#   freshness_modifier 무엇이든
#   effective = base × 0.0 × X = 0.0
```

PR11-D 의 "refuted = 확정 부정" 의미 그대로 보존. `freshness_modifier` 자체는
`status` 와 무관하게 계산 가능 (status guard 없음) — 호출 결과만 곱셈으로
자연 0 보장.

### 3. PR10-A 와 의미 분리 (§26.6)

| | PR10-A | PR11-C |
|---|---|---|
| Input | active contradiction strength | active contradiction strength |
| 표현 | binary trigger (`>= 0.8`) | continuous attenuation (`1 - s × 0.5`) |
| 결과 | status 전이 (`disputed → refuted`) | scoring 감쇠 (`effective` 값) |
| Threshold | `_REFUTATION_STRENGTH_THRESHOLD = 0.8` | `_FRESHNESS_PENALTY_WEIGHT = 0.5` |
| 시점 | refute 호출 시 | compute_effective 호출 시 |

**의미 충돌 없음** — 같은 input, 다른 정책 — 하나는 lifecycle 상태 변환,
하나는 scoring view 감쇠.

### 4. PR11-A 와의 정합

PR11-C 가 `active_contradictions_by_freshness(claim_id)` 를 **input 으로만
활용**:
- PR11-A query 의 의미 / return / 정렬 / 차집합 변경 0
- PR11-A 의 Sub-decision B (query only) 정신 — PR11-A 가 노출한 query 를
  PR11-C 가 처음 활용

### 5. PR11-D 와의 정합 — 시그니처 보존

```python
# PR11-D (변경 안 됨)
def compute_effective_confidence(self, claim_id: int) -> ScoreValue: ...
```

PR11-C 는 **시그니처 변경 0**:
- `claim_id: int` 입력 그대로
- `ScoreValue` 반환 그대로
- unknown claim_id → KeyError 그대로
- 본문에 `× freshness_modifier(claim_id)` 추가만

caller 코드 변화 0. PR1~PR11-A 의 모든 호출자가 자연스럽게 더 정교한 값을
받기 시작.

### 6. 결정성 (Determinism)

```text
같은 (claim.base_confidence, claim.status,
      active_contradictions_by_freshness(claim_id) 결과,
      evidence.strength) → 항상 같은 effective_confidence
```

PR11-C 는:
- wall-clock 안 봄
- random / external state 안 봄
- PR1 `_next_id` 카운터 안 봄 (PR11-A query 결과만 input)

PR11-D 결정성 그대로 유지. caller 자체 캐시 자유.

### 7. Private constant (§26.10)

```python
# Engine module level
_FRESHNESS_PENALTY_WEIGHT = 0.5
```

- **Public export 안 함** (engine 내부 private)
- PR10-A `_REFUTATION_STRENGTH_THRESHOLD` / PR11-D `_STATUS_MODIFIER_*` 와
  동일 정신
- 미래 정책 변경 자유 확보 (PR11-D Sub-decision M-impl 정신)

### 8. PR11-A 패턴 vs PR11-C 패턴

| | PR11-A | PR11-C |
|---|---|---|
| 본질 | freshness noun 노출 | freshness verb 활용 |
| API | 2 신규 query (read-only) | 0 신규 API (기존 본문 확장) |
| Engine 동작 | 변경 0 | `compute_effective_confidence` 의미 확장 |
| 패턴 | PR10-B audit-only 패턴 | PR11-D stub 의미 교체 패턴 |

## 불변식 (테스트로 잠금)

§26.12 의 18 invariant:

1. unknown claim_id → `KeyError` (PR11-D 동작 보존)
2. candidate + active 0 → effective == base (PR11-D 와 동일)
3. confirmed + active 0 → effective == base (PR11-D 와 동일)
4. disputed + active 0 → effective == base × 0.5 (PR11-D 와 동일)
5. **refuted + 어떤 active → effective == 0.0** ★ (Sub-decision P)
6. **confirmed + active strength 0.8 → effective == base × 0.6** ★ (PR11-C 핵심)
7. **disputed + active strength 1.0 → effective == base × 0.25** ★ (modifier 곱셈)
8. active 첫 evidence (`active_contradictions_by_freshness[0]`) 만 본다 (Sub-decision O)
9. resolved contradiction 은 freshness 에서 제외 (PR9-A 차집합 정합)
10. **PR10-A `refute_disputed_claim_if_ready` 동작 변경 없음** ★
11. **PR11-A `evidence_freshness` / `active_contradictions_by_freshness` 동작 변경 없음**
12. **PR9-A `active_contradictions_for_claim` asc 동작 변경 없음**
13. **PR11-D status_modifier (`_STATUS_MODIFIER_*`) 값 변경 없음**
14. effective never exceeds base (no boost — Sub-decision N 정신 유지)
15. compute is read-only
16. determinism
17. `_FRESHNESS_PENALTY_WEIGHT` private (ragcore + ragcore.types 미노출)
18. 기존 547 회귀 없음 (전체 통과로 입증)

## 테스트

**564 passing** in ~0.41s (547 → 564, delta 정확히 +17)

### Test-first 흐름 (PR11-D 와 동일 mixed pattern)

PR11-C 는 **기존 의미 확장** 라서 fail 분포가 mixed:

63차 (test-first 잠금):

```text
17 새 tests 추가
실행 결과 (의도된 mixed 분포):
- 4 fails (의도된 assertion — freshness_modifier 미적용):
    * test_confirmed_with_active_strong_attenuates       (expected 0.6, actual 1.0)
    * test_disputed_with_max_active_strength             (expected 0.25, actual 0.5)
    * test_only_most_recent_active_strength_affects_modifier  (expected 0.9, actual 1.0)
    * test_resolved_strong_does_not_affect_freshness_modifier  (expected 0.9, actual 1.0)
- 13 pass (이미 정합):
    * PR11-D 동작 보존 (5): KeyError + candidate/confirmed/disputed active 0 + refuted
    * 정책 무변화 (3): PR10-A refute / PR11-A query / PR9-A asc
    * 일반 속성 (3): no boost (7 시나리오 loop) / read-only / determinism
    * private export (2): ragcore + ragcore.types
+ 기존 547 통과
```

이 13 pass 는 PR11-D 55차 / PR11-A 59차 의 부분 pass 패턴과 동일.

64차 (구현):

```text
- ragcore/engine.py:
    _FRESHNESS_PENALTY_WEIGHT = 0.5 (private)
    compute_effective_confidence 본문에 × freshness_modifier 추가
실행 결과: 564 통과 (4 fail → 4 pass, 13 pass 유지)
```

### 변경 파일 (PR11-C 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §26 신설 (+255 lines) |
| `tests/test_engine_effective_freshness_modifier.py` | 신규 (17 tests, +368 lines) |
| `ragcore/engine.py` | 1 private constant + 본문 확장 (+36, -12) |
| `docs/dev/PR_014_EFFECTIVE_FRESHNESS_MODIFIER_MVP.md` | 이 파일 (신규) |
| `ragcore/types.py` | **변경 없음** (새 dataclass / 상수 없음) |
| `ragcore/__init__.py` | **변경 없음** (Sub-decision: 새 export 없음) |
| `ragcore/rule_output.py` | **변경 없음** (Sub-decision D 정합) |

### 테스트 분포

| 파일 | PR11-A 후 | PR11-C (63차) | PR11-C (64차) | 변동 |
|---|---|---|---|---|
| `test_engine_effective_freshness_modifier.py` | 0 | 17 (4 fail + 13 pass) | **17 (pass)** | +17 |
| 나머지 18 파일 | 547 | 547 | **547** | 0 |
| **Total** | 547 | 547 + 13 pass + 4 fail | **564** | **+17** |

### 신규 테스트 그룹

**TestPriorPR11DBehaviorPreserved (5):** PR11-D 동작 그대로 (active 0 + refuted 케이스)
**TestFreshnessModifierApplied (2):** ★ active 1+ 시 freshness 적용 (PR11-C 핵심)
**TestMostRecentOnly (1):** Sub-decision O — older strong + recent weak → recent 만 영향
**TestResolvedExcluded (1):** resolved strong → freshness 에서 제외 (PR9-A 차집합 정합)
**TestPriorPolicyUnchanged (3):** PR10-A / PR11-A / PR9-A 무변화
**TestEffectiveConfidenceProperties (3):** no boost / read-only / determinism
**TestFreshnessPenaltyWeightPrivacy (2):** ragcore + ragcore.types 미노출

## 구현 요약 (64차)

```python
# ragcore/engine.py — module level (PR11-D _STATUS_TO_MODIFIER 다음)
_FRESHNESS_PENALTY_WEIGHT = 0.5  # Sub-decision, private

# compute_effective_confidence 본문 (시그니처 / KeyError 그대로)
def compute_effective_confidence(self, claim_id):
    if claim_id not in self._claims:
        raise KeyError(...)
    claim = self._claims[claim_id]
    status_modifier = _STATUS_TO_MODIFIER[claim.status]   # PR11-D

    active = self.active_contradictions_by_freshness(claim_id)  # PR11-A query
    if not active:
        freshness_modifier = 1.0
    else:
        most_recent_evidence = self._evidences[active[0]]
        freshness_modifier = (
            1.0 - most_recent_evidence.strength.value * _FRESHNESS_PENALTY_WEIGHT
        )

    return ScoreValue(
        claim.base_confidence.value * status_modifier * freshness_modifier
    )
```

배치: module level 상수는 `_STATUS_TO_MODIFIER` 다음. 메서드는 PR1 stub 위치
그대로 (본문만 확장).

`types.py` / `__init__.py` / `rule_output.py` 변경 0.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| 모든 active contradiction 가중합 / max / rank / older | Sub-decision O |
| PR10-A `refute_disputed_claim_if_ready` 정책 변경 | **PR11-B 자연 후속** |
| Gap-based modifier (unresolved gap 페널티) | PR12+ |
| Contradiction count modifier (active 개수) | PR12+ |
| RuleStats-based modifier (observed_precision / FP rate) | PR12+ |
| Lifecycle history-based modifier | PR12+ |
| Confidence boost (modifier > 1.0) | PR11-D Sub-decision N 일관 — 영구 OOS |
| Caller-driven modifier / config injection | PR10-A / PR11-D 정신 |
| LLM / semantic confidence | core 밖 |
| Mutable confidence / setter | immutability |
| Public `FRESHNESS_PENALTY_WEIGHT` | engine 내부 private |
| Wall-clock timestamp | PR10-A/B / PR11-D / PR11-A 와 일관 OOS |
| Cross-engine freshness 비교 | per-engine 의미 |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| B | **PR11-B — refute 정책 + freshness 통합** — PR10-A 의 `active 중 단 하나라도 >= 0.8` 을 freshness 가중치로 정교화 | 높음 (PR11-C 자연 후속, "다른 표현으로 같은 input" 의 verb 측면) |
| D | **Gap-based modifier** — `effective × gap_modifier` (unresolved gap 페널티) | 중 |
| E | **Contradiction count modifier** — active 개수 기반 추가 감쇠 | 중 |
| F | **RuleStats-based modifier** — `observed_precision` / `false_positive_rate` | 중 |
| G | **`superseded` / `retracted` 추가 상태** | 중 |
| H | **Persistence / 직렬화** | 중 |
| I | **fire_rule audit** — PR10-B history 를 transition 외 영역으로 확장 | 중 |
| J | Engine bulk fire / `not` combinator / trace 직렬화 | 낮음 |
| K | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **B (PR11-B — refute 정책 + freshness 통합)**.

이유:
- PR11-A 가 freshness noun 노출, PR11-C 가 effective 의 verb 측면 통합.
  PR11-B 가 refute 의 verb 측면 통합 — 정확한 자연 후속.
- PR10-A `_REFUTATION_STRENGTH_THRESHOLD = 0.8` 정책이 단일 threshold 로 너무
  좁음. freshness 가중치로 정교화하면 "가장 최근 active strong evidence 우선"
  같은 의미 표현 가능.
- PR11-A query (`active_contradictions_by_freshness`) 와 PR11-C modifier
  (`_FRESHNESS_PENALTY_WEIGHT`) 둘 다 PR11-B 의 input 으로 자연스럽게 통합.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §26](../contracts/05_DATA_CONTRACT_MVP.md) — Effective freshness modifier (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §25](../contracts/05_DATA_CONTRACT_MVP.md) — Evidence freshness query (PR11-A, 변경 안 됨)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §24](../contracts/05_DATA_CONTRACT_MVP.md) — Effective confidence (PR11-D base)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §22](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed refutation (PR10-A, 변경 안 됨)
- [docs/dev/PR_010_DISPUTED_REFUTATION_MVP.md](PR_010_DISPUTED_REFUTATION_MVP.md)
- [docs/dev/PR_011_LIFECYCLE_HISTORY_MVP.md](PR_011_LIFECYCLE_HISTORY_MVP.md)
- [docs/dev/PR_012_EFFECTIVE_CONFIDENCE_MVP.md](PR_012_EFFECTIVE_CONFIDENCE_MVP.md) — PR11-D base
- [docs/dev/PR_013_EVIDENCE_FRESHNESS_MVP.md](PR_013_EVIDENCE_FRESHNESS_MVP.md) — PR11-A base

## How to Run

```bash
git checkout feat/effective-freshness-modifier-mvp
pip install -e .
pytest -v
```

564 tests in ~0.41s. No new external dependencies.

## Result

PR11-C 가 PR11-A 의 freshness noun 을 PR11-D 의 modifier 분해 자리에 처음
연결. PR11-D §24.5 의 명시적 미래 자리가 실제로 활성화됨.

PR11-A / PR11-C 의 두 단계:

```text
PR11-A: freshness noun 노출 (read-only query 만)
PR11-C: freshness verb 활용 (effective 의 multiplicative modifier)
```

엔진의 scoring 정교화 (status × freshness):

```text
candidate / confirmed + active 0       → base
candidate / confirmed + active strong  → base × 0.6 (strength 0.8 시)
disputed + active 0                    → base × 0.5
disputed + active strong               → base × 0.25 (strength 1.0 시)
refuted + any                          → 0.0 (Sub-decision P)
```

PR10-A 와의 의미 분리 보존:
- PR10-A: binary status 전이 (strength >= 0.8 trigger)
- PR11-C: continuous scoring 감쇠 (× modifier)

남은 결정점 (PR11-B refute + freshness 통합, gap modifier, RuleStats, superseded
/retracted, persistence) 은 후속 PR 에서.

PR11-C 의 본질:

> **freshness query 를 effective confidence 에 처음 연결한 PR.** modifier
> 분해 자리 (PR11-D §24.5) 의 첫 활용. PR10-A refute 정책은 그대로.
