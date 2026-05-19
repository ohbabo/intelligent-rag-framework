# PR #012 — Effective Confidence MVP (PR11-D)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/effective-confidence-mvp` → `main`
> Base: `b45d4fa` (PR10-B merged)
> Tests: 534 passing (local)

## 목적

PR10-B 까지의 흐름:

```text
compute_effective_confidence(c) → base_confidence 그대로 (PR1 stub)
→ lifecycle 사면 + audit 닫혔지만 status 가 scoring 으로 연결 안 됨
```

PR11-D 추가:

```text
compute_effective_confidence(c) → base × status_modifier(claim.status)
  candidate / confirmed: 1.0 (그대로)
  disputed: 0.5 (감쇠)
  refuted:  0.0 (확정 부정)
```

PR1 의 prior / base / effective confidence 3 슬롯 분리가 처음으로 의미를
가진다. 이전까지 `effective` 슬롯은 stub 으로 비어 있었음.

## PR11-D 의 한 줄 정의

> **PR11-D 는 "정교한 신뢰도 계산기" 가 아니라, lifecycle status 가
> effective_confidence 에 처음 반영되는 최소 연결 PR 이다.**

PR10-B 가 lifecycle audit 까지 닫았고, PR11-D 가 그 status 를 **scoring 으로
처음 연결**. lifecycle 사면 + audit + scoring 의 3층 구조가 완성.

## 핵심 명제 (§24.2)

```text
Effective confidence is status-adjusted, not evidence-recomputed.

PR11-D does not re-evaluate evidence, gaps, contradictions, freshness, or
rule maturity. It only applies the current claim lifecycle status as a
bounded multiplier over base confidence.
```

한국어:

```text
Effective confidence 는 status 로 조정될 뿐, evidence 를 재계산하지 않는다.

PR11-D 는 evidence / gap / contradiction / freshness / rule maturity 를 다시
평가하지 않는다. base_confidence 위에 현재 lifecycle status 를 bounded
multiplier 로 적용할 뿐이다.
```

## 공식 (§24.3)

```python
effective_confidence(claim) = base_confidence × status_modifier(claim.status)
```

| status | modifier | 의미 |
|---|---|---|
| `CLAIM_STATUS_CANDIDATE` | `1.0` | 그대로 — 아직 모름 |
| `CLAIM_STATUS_CONFIRMED` | `1.0` | 그대로 — boost 없음 |
| `CLAIM_STATUS_DISPUTED` | `0.5` | 감쇠 — 재판정 대기 |
| `CLAIM_STATUS_REFUTED` | `0.0` | 확정 부정 |

## 닫힌 흐름 (PR11-D 추가분)

```python
# 1) Claim 생성, base_confidence=0.8
claim = engine.add_claim(..., base_confidence=0.8)        # CANDIDATE

engine.compute_effective_confidence(claim)
# → ScoreValue(0.8)  (candidate × 1.0)

# 2) 전체 lifecycle 사면 traversal — effective 가 status 에 따라 변함
engine.confirm_claim_if_ready(claim)                       # → True, CONFIRMED
engine.compute_effective_confidence(claim)
# → ScoreValue(0.8)  (confirmed × 1.0, boost 없음)

engine.register_contradiction(claim, contradicting_ev)
engine.dispute_claim_if_ready(claim)                       # → True, DISPUTED
engine.compute_effective_confidence(claim)
# → ScoreValue(0.4)  (disputed × 0.5, 감쇠)

# (option A) 모든 contradiction resolved → confirmed 복귀
engine.register_contradiction_resolution(claim, contradicting_ev)
engine.resolve_disputed_claim_if_ready(claim)              # → True, CONFIRMED
engine.compute_effective_confidence(claim)
# → ScoreValue(0.8)  (다시 확정 — boost 없으니 base 그대로)

# (option B) active strong contradiction → refuted
engine.refute_disputed_claim_if_ready(claim)               # → True, REFUTED
engine.compute_effective_confidence(claim)
# → ScoreValue(0.0)  (refuted × 0.0, 확정 부정)
```

caller 가 처음으로:

```text
"이 claim 의 현재 status 가 신뢰도에 어떻게 반영되는가?"
질문에 의미 있는 답을 받을 수 있음.
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `c48c559` | docs(contract): define effective confidence MVP (§24) |
| 2 | `d5ad86e` | test(core): lock effective confidence invariants |
| 3 | `b30ce0d` | feat(engine): activate effective confidence |
| 4 | (this) | docs(dev): PR11-D record |

## 주요 설계 결정 (§24)

### 1. Sub-decision M — Status only

`modifier` 의 input 은 **`claim.status` 만**:

```python
modifier = _STATUS_TO_MODIFIER[claim.status]
```

PR11-D 범위 **밖** (미래 PR 로 확장):
- `gaps_for_claim(c)` / `gap_resolution(g)`
- `contradictions_for_claim(c)` / `active_contradictions_for_claim(c)`
- `resolved_contradictions_for_claim(c)`
- `claim_lifecycle_history(c)` (PR10-B seq / transition labels)
- `evidence.strength`
- `RuleStats` (`observed_precision`, `false_positive_rate`)
- `rule_version` / `rule_maturity` / freshness

| 옵션 | 채택 | 이유 |
|---|---|---|
| (i) status only | ✓ | PR10-A 단순성 정신 일관, 다음 PR 자연 확장 |
| (ii) status + gap | ✗ | 결정 부담 — 페널티 값 |
| (iii) status + gap + contradiction | ✗ | 결정 폭발 |
| Config-driven | ✗ | PR10-A 정신 위반 |

### 2. Sub-decision N — Bounded modifier, no boost

```text
modifier ∈ [0.0, 1.0]
→ effective_confidence ≤ base_confidence (보장)
→ no boost (confirmed 가 base 를 초과하지 않음)
```

이유:
- **"confirmed = 근거 충족" 이지 "과신해도 됨" 이 아님**
- PR1 `ScoreValue` 의 `[0.0, 1.0]` 범위 강제와 정합
- 미래에 "boost" 필요하면 별도 PR 결정점 (확신도 모델 변경)

### 3. Status modifier 값 — 결정 잠금

```python
_STATUS_MODIFIER_CANDIDATE = 1.0  # 그대로 — 아직 모름
_STATUS_MODIFIER_CONFIRMED = 1.0  # 그대로 — boost 없음
_STATUS_MODIFIER_DISPUTED  = 0.5  # 감쇠 — 재판정 대기
_STATUS_MODIFIER_REFUTED   = 0.0  # 확정 부정
```

값 결정 근거:

- **candidate = 1.0**: base_confidence 는 룰 firing 시점 스냅샷. 아직 판단
  안 됐으므로 그대로 노출.
- **confirmed = 1.0**: 근거 채워졌지만 boost 안 함 (Sub-decision N).
  보수적 단순화.
- **disputed = 0.5**: confirmed 였다가 contradiction 으로 재검토. base 의
  절반으로 명확히 감쇠해 caller 가 "주의" 신호로 인식 가능.
- **refuted = 0.0**: 확정 부정. `effective × 0.0 = 0.0` 으로 완전 차단.

값 자체는 **engine 내부 private** (Sub-decision M-impl):
- public export 안 함
- 미래 정책 변경 자유 확보
- caller 외부 의존 차단

### 4. 결정성 (Determinism)

```text
같은 (claim.base_confidence, claim.status) → 항상 같은 effective_confidence
```

PR11-D 는:
- wall-clock 안 봄
- gap / contradiction / history 안 봄
- `_lifecycle_seq` 안 봄
- random / external state 안 봄

테스트 재현 100% 보장. caller 자체 캐시 / memoization 자유.

### 5. PR1 stub 의 의미 채우기

```python
# 시그니처 / KeyError 동작 / return type — 모두 PR1 stub 그대로 유지
def compute_effective_confidence(self, claim_id: int) -> ScoreValue:
    if claim_id not in self._claims:
        raise KeyError(...)
    claim = self._claims[claim_id]
    # PR11-D 추가: status modifier 적용
    modifier = _STATUS_TO_MODIFIER[claim.status]
    return ScoreValue(claim.base_confidence.value * modifier)
```

caller 코드 변화 0. PR1~PR10-B 의 모든 호출자가 자연스럽게 의미 있는 값을
받기 시작.

### 6. `ScoreValue` 비교 — `.value` 직접 접근

```python
return ScoreValue(claim.base_confidence.value * modifier)
```

`ScoreValue` 가 `__mul__` / `__ge__` 미정의 (`order=False`, frozen dataclass).
PR10-A 의 `evidence.strength.value >= 0.8` 패턴 일관 — PR1 시그니처 변경 회피.

### 7. PR11-D 가 건드리지 않은 데이터

| | PR11-D 영향 |
|---|---|
| `Claim.base_confidence` 값 | 없음 (read-only) |
| `claim.status` | 없음 (read-only) |
| `ClaimLifecycleEvent` / lifecycle history | 없음 (안 봄) |
| `_contradictions` / `_resolved_contradictions` / `_gap_resolutions` | 없음 (안 봄) |
| `_lifecycle_seq` / `_claim_lifecycle_events` | 없음 (안 봄) |
| 5 lifecycle API | 없음 (시그니처 / 동작 무변경) |
| `register_contradiction*` | 없음 |
| `add_claim` / `add_evidence` / `add_gap` | 없음 |
| `fire_rule*` / `RuleStats` | 없음 |
| `_REFUTATION_STRENGTH_THRESHOLD` | 없음 (PR10-A) |
| `CLAIM_STATUS_*` / `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 |
| `ScoreValue` 시그니처 | 없음 |
| public exports | 없음 (status_modifier 상수 private) |

PR11-D 는 **stub 의 본문만 교체**. caller 코드 변화 0.

## 불변식 (테스트로 잠금)

§24.10 의 17 invariant:

1. `compute_effective_confidence` unknown claim_id → `KeyError`
2. **candidate → effective == base ★**
3. **confirmed → effective == base** (boost 없음)
4. **refuted → effective.value == 0.0 ★**
5. **disputed → effective.value == base × 0.5 ★**
6. return type is `ScoreValue`
7. deterministic — same input same output
8. effective ≤ base (Sub-decision N, no boost)
9. base=0.5 + candidate → 0.5
10. base=0.8 + disputed → 0.4
11. base=1.0 + refuted → 0.0
12. base=0.0 + any status → 0.0 (0 × anything)
13. compute is read-only (base_confidence / lifecycle_history 무변화)
14. **lifecycle transition 통한 effective 변화 추적 ★**
    (candidate → confirmed → disputed → refuted full path)
15. `_STATUS_MODIFIER_*` 가 public export 안 됨 (`ragcore` + `ragcore.types`)
16. 기존 517 회귀 없음 (전체 통과로 입증)

## 테스트

**534 passing** in ~0.38s (517 → 534, delta 정확히 +17)

### Test-first 흐름 (PR8/PR10-A 와 다른 패턴)

PR11-D 는 **기존 stub 의 의미 교체** 라서 fail 분포가 mixed:

55차 (test-first 잠금):

```text
17 새 tests 추가
실행 결과 (의도된 mixed 분포):
- 5 fails (의도된 assertion):
    * test_disputed_halves_base                            (stub: 0.7, expected: 0.35)
    * test_refuted_zero                                    (stub: 1.0, expected: 0.0)
    * test_base_high_disputed                              (stub: 0.8, expected: 0.4)
    * test_base_max_refuted                                (stub: 1.0, expected: 0.0)
    * test_effective_changes_with_lifecycle_transitions    (disputed/refuted 부분)
- 12 pass (이미 정합):
    * KeyError / type / deterministic (3)
    * candidate / confirmed → base 그대로 (2)
    * base=0.5 + candidate → 0.5 (1)
    * base=0.0 + any → 0.0 (1)
    * effective ≤ base — stub 도 base 그대로니 자연 만족 (1)
    * compute is read-only (2)
    * _STATUS_MODIFIER_* private export (2)
+ 기존 517 통과
```

이 12 pass 는 PR8 39차 `TestSubDecisionD` 와 PR10-A 47차의 부분 pass 패턴과 동일.

56차 (구현):

```text
- ragcore/engine.py: 4 _STATUS_MODIFIER_* + _STATUS_TO_MODIFIER + stub 본문 교체
실행 결과: 534 통과 (5 fail → 5 pass, 12 pass 유지)
```

### 변경 파일 (PR11-D 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §24 신설 (+229 lines) |
| `tests/test_engine_effective_confidence.py` | 신규 (17 tests, +290 lines) |
| `ragcore/engine.py` | 4 private constants + mapping + stub 본문 교체 (+37, -6) |
| `docs/dev/PR_012_EFFECTIVE_CONFIDENCE_MVP.md` | 이 파일 (신규) |
| `ragcore/types.py` | **변경 없음** (새 상수 없음) |
| `ragcore/__init__.py` | **변경 없음** (Sub-decision M-impl — private) |
| `ragcore/rule_output.py` | **변경 없음** (Sub-decision D 정합) |

### 테스트 분포

| 파일 | PR10-B 후 | PR11-D (55차) | PR11-D (56차) | 변동 |
|---|---|---|---|---|
| `test_engine_effective_confidence.py` | 0 | 17 (5 fail + 12 pass) | **17 (pass)** | +17 |
| 나머지 16 파일 | 517 | 517 | **517** | 0 |
| **Total** | 517 | 517 + 12 pass + 5 fail | **534** | **+17** |

### 신규 테스트 그룹

**TestComputeEffectiveConfidenceBasics (3):** KeyError + ScoreValue type + deterministic
**TestStatusModifier (4):** 4 status × effective 검증 (2 fail intended)
**TestBoundaryValues (5):** base × modifier 곱셈 boundary (2 fail intended)
**TestLifecycleTransitionTrace (1):** ★ status 변화 → effective 재계산 (fail intended)
**TestComputeIsReadOnly (2):** base_confidence + lifecycle_history 무변화
**TestStatusModifierPrivacy (2):** `_STATUS_MODIFIER_*` ragcore + ragcore.types 미노출

## 구현 요약 (56차)

```python
# ragcore/engine.py (module level — PR10-A _REFUTATION_STRENGTH_THRESHOLD 다음)
_STATUS_MODIFIER_CANDIDATE = 1.0
_STATUS_MODIFIER_CONFIRMED = 1.0
_STATUS_MODIFIER_DISPUTED  = 0.5
_STATUS_MODIFIER_REFUTED   = 0.0

_STATUS_TO_MODIFIER: dict[int, float] = {
    CLAIM_STATUS_CANDIDATE: _STATUS_MODIFIER_CANDIDATE,
    CLAIM_STATUS_CONFIRMED: _STATUS_MODIFIER_CONFIRMED,
    CLAIM_STATUS_DISPUTED:  _STATUS_MODIFIER_DISPUTED,
    CLAIM_STATUS_REFUTED:   _STATUS_MODIFIER_REFUTED,
}

# Engine method (PR1 stub 의 본문 교체)
def compute_effective_confidence(self, claim_id) -> ScoreValue:
    if claim_id not in self._claims:
        raise KeyError(...)
    claim = self._claims[claim_id]
    modifier = _STATUS_TO_MODIFIER[claim.status]
    return ScoreValue(claim.base_confidence.value * modifier)
```

배치: module level constants 는 `_REFUTATION_STRENGTH_THRESHOLD` 다음. 메서드는
기존 stub 위치 (`get_rule_stats` 와 `update_rule_stats` 사이) 그대로.

`ragcore/types.py` / `ragcore/__init__.py` / `ragcore/rule_output.py` 변경 0.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| Gap 기반 modifier (unresolved gap 페널티) | PR11 후속 또는 PR12+ |
| Contradiction 기반 modifier (active strength 가중) | PR11-A 또는 PR12+ |
| Freshness 기반 modifier (PR10-B seq 활용) | PR11-A 자연 자리 |
| RuleStats 기반 modifier (observed_precision / false_positive_rate) | scoring 정교화 별도 PR |
| Lifecycle history 기반 modifier (transition 횟수 / path 가중) | history 활용 별도 PR |
| Confidence boost (modifier > 1.0) | 확신도 모델 변경 — 별도 결정점 |
| Caller-driven modifier 함수 (config injection) | PR10-A 정신 위반 |
| LLM / semantic 기반 confidence | core 밖 |
| Mutable confidence (setter 도입) | immutability 보존 |
| Public `STATUS_MODIFIER_*` constants | Sub-decision M-impl |
| Effective confidence 의 직렬화 / persistence | 별도 PR |
| `base_confidence` 값 변경 (caller setter) | base 는 firing 시점 스냅샷 — 변경 금지 |
| 결과의 caching / memoization | 결정성 보장이므로 호출자가 자체 캐시 가능 |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| A | **Freshness-based 우세도** — PR10-A 의 단순 strength threshold 를 PR10-B seq 활용해 확장 + PR11-D modifier 의 한 input 으로 통합 | 높음 (PR10-A / PR10-B / PR11-D 모두의 자연 후속) |
| B | **Gap-based modifier extension** — PR11-D modifier 에 gap_modifier 추가 (unresolved gap 페널티) | 중 |
| C | **Contradiction-strength modifier** — active contradiction 의 strength 를 modifier 에 반영 (PR10-A 정책 + PR11-D 통합) | 중 |
| D | **RuleStats-based modifier** — `observed_precision` / `false_positive_rate` 을 modifier 에 반영 | 중 |
| E | **`superseded` / `retracted` 추가 상태** | 중 (도메인 요구 명확해진 뒤) |
| F | **Persistence / 직렬화** — engine state + lifecycle history 저장/복원 | 중 |
| G | **fire_rule audit** — PR10-B 의 history 를 transition 외 영역으로 확장 (PR3 firing trace 와 통합) | 중 |
| H | Engine bulk fire / `not` combinator / trace 직렬화 | 낮음 |
| I | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **A (Freshness 우세도)**.

이유:
- PR10-A 의 단순 threshold 가 단일 정책으로 너무 좁음 — freshness 가 자연
  확장 자리
- PR10-B 의 `_lifecycle_seq` 가 wall-clock 없이도 순서를 표현하므로 직접 활용
  가능
- PR11-D 의 modifier 분해 가능성 (Sub-decision M-impl 의 "미래 정책 도입 시
  modifier 분해" 가능성) 활용 — `effective = base × status_modifier ×
  freshness_modifier` 같은 분해
- 세 PR (PR10-A / PR10-B / PR11-D) 모두의 자연 후속

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §24](../contracts/05_DATA_CONTRACT_MVP.md) — Effective confidence contract (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §23](../contracts/05_DATA_CONTRACT_MVP.md) — Lifecycle history (PR10-B base)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §22](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed refutation (PR10-A)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §18~§21](../contracts/05_DATA_CONTRACT_MVP.md) — Lifecycle 사면 (PR6~PR9-A)
- [docs/dev/PR_006_CLAIM_LIFECYCLE_MVP.md](PR_006_CLAIM_LIFECYCLE_MVP.md)
- [docs/dev/PR_007_CLAIM_REFUTATION_MVP.md](PR_007_CLAIM_REFUTATION_MVP.md)
- [docs/dev/PR_008_DISPUTED_LIFECYCLE_MVP.md](PR_008_DISPUTED_LIFECYCLE_MVP.md)
- [docs/dev/PR_009_DISPUTED_RESOLUTION_MVP.md](PR_009_DISPUTED_RESOLUTION_MVP.md)
- [docs/dev/PR_010_DISPUTED_REFUTATION_MVP.md](PR_010_DISPUTED_REFUTATION_MVP.md)
- [docs/dev/PR_011_LIFECYCLE_HISTORY_MVP.md](PR_011_LIFECYCLE_HISTORY_MVP.md) — PR10-B base

## How to Run

```bash
git checkout feat/effective-confidence-mvp
pip install -e .
pytest -v
```

534 tests in ~0.38s. No new external dependencies.

## Result

PR11-D 가 PR1 의 stub 을 처음으로 활성화하고, PR6~PR10-A 의 lifecycle 의미를
scoring 으로 연결했다. 엔진이 이제 다음 세 질문에 분리해서 답할 수 있다:

```text
"이 Claim 의 현재 상태는?"                  → status (PR6~PR10-A)
"어떤 path 로 여기에 왔는가?"                → claim_lifecycle_history (PR10-B)
"현재 상태에서 얼마나 믿을 수 있는가?"        → compute_effective_confidence (PR11-D) ★
```

특히 lifecycle 의 의미가 scoring 으로 자연스럽게 흘러 들어옴:

```python
# 같은 claim, status 만 다름 → effective 가 다름
candidate / confirmed: effective = base   (그대로)
disputed:              effective = base × 0.5 (감쇠 — 재판정 대기)
refuted:               effective = 0.0       (확정 부정)
```

남은 결정점 (freshness 우세도, gap/contradiction modifier, RuleStats,
persistence, superseded/retracted) 은 PR11-A 또는 PR12+ 에서.

PR11-D 의 본질:

> **상태 판단을 정교화한 PR 이 아니라**, PR6~PR10-A 에서 잠근 lifecycle status 가
> effective_confidence 에 처음 반영되는 **최소 연결 PR**.

lifecycle 사면 (PR6~PR10-A) + audit (PR10-B) + scoring 연결 (PR11-D) 의
3층 구조가 완성.
