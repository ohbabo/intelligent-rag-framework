# PR #016 — Gap Modifier MVP (PR12-D)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/gap-modifier-mvp` → `main`
> Base: `a4c734e` (PR11-B merged)
> Tests: 612 passing (local)

## 목적

PR11-B 까지의 흐름:

```text
effective = base × status_modifier × freshness_modifier
→ gap 정보는 effective 에 반영 안 됨
→ caller 가 gap 상태를 보려면 gaps_for_claim 직접 호출 필요
```

PR12-D 추가:

```text
effective = base × status_modifier × freshness_modifier × gap_modifier
→ PR5 의 gap_resolution 의미가 effective 에 처음 연결
→ unresolved gap 1+ 시 약한 페널티 (× 0.8)
→ 모든 gap resolved / gap 0 개 시 영향 없음 (× 1.0)
```

## PR12-D 의 한 줄 정의

> **PR12-D 는 gap 판단을 정교화하는 PR 이 아니라, PR5 의 gap resolution
> 의미가 effective_confidence 에 처음 연결되는 최소 연결 PR 이다.**

PR11-D §24.5 의 modifier 분해 자리 (status × freshness 이미 채워짐) 의 **세
번째 modifier** 활용. PR5 noun (gap_resolution) → PR12-D verb (effective
scoring 통합).

## 핵심 명제 (§28.2)

```text
Gap modifier is binary and weak:
unresolved gap means information is incomplete, not contradicted.
```

한국어:

```text
Gap modifier 는 binary 이고 약하다:
unresolved gap 은 '정보 부족' 이지 '반박' 이 아니다.
```

이 명제가 Sub-decision T (값 0.8) 의 근거. PR10-A refute / PR11-C effective
attenuation 보다 명확히 약한 페널티.

## 공식 — 4-modifier composition 완성

```python
effective_confidence(claim) = (
    base_confidence                              # PR1
    × status_modifier(claim.status)              # PR11-D §24
    × freshness_modifier(claim_id)               # PR11-C §26
    × gap_modifier(claim_id)                     # PR12-D §28 (신규)
)
```

| modifier | PR | 형태 | 범위 |
|---|---|---|---|
| status_modifier | PR11-D | 4 값 (1.0/1.0/0.5/0.0) | [0.0, 1.0] |
| freshness_modifier | PR11-C | continuous (1 - s × 0.5) | [0.5, 1.0] |
| **gap_modifier** | **PR12-D** | **binary (1.0 또는 0.8)** | **[0.8, 1.0]** |

## Modifier composition 표

| Claim status | active 0 | active 0.8 | active 1.0 |
|---|---|---|---|
| candidate/confirmed + no gap | base | base × 0.6 | base × 0.5 |
| candidate/confirmed + unresolved gap | **base × 0.8** | **base × 0.48** | **base × 0.4** |
| disputed + no gap | base × 0.5 | base × 0.3 | base × 0.25 |
| disputed + unresolved gap | **base × 0.4** | **base × 0.24** | **base × 0.2** |
| refuted + any | 0.0 | 0.0 | 0.0 |

## 닫힌 흐름 (PR12-D 추가분)

```python
# 1) Claim + 모든 gap resolved (PR5)
claim = engine.add_claim(..., base_confidence=1.0)
gap = engine.add_gap(claim, gap_type=1, required_evidence_type=42, ...)
ev = engine.add_evidence(claim, ..., evidence_type=42)
engine.resolve_gaps_for_evidence(ev)
engine.compute_effective_confidence(claim)
# → 1.0 × 1.0 × 1.0 × 1.0 = 1.0  (gap_modifier = 1.0)

# 2) Claim + unresolved gap (다른 evidence type)
gap_unresolved = engine.add_gap(
    claim, gap_type=1, required_evidence_type=99, rule_id=2, ...
)
# evidence_type=99 인 evidence 없음 → unresolved
engine.compute_effective_confidence(claim)
# → 1.0 × 1.0 × 1.0 × 0.8 = 0.8  (gap_modifier = 0.8)

# 3) Confirmed + active contradiction + unresolved gap
ev_contra = engine.add_evidence(claim, strength=0.8)
engine.register_contradiction(claim, ev_contra)
engine.confirm_claim_if_ready(claim)  # status → CONFIRMED
engine.compute_effective_confidence(claim)
# → 1.0 × 1.0 × (1.0 - 0.8 × 0.5) × 0.8
# = 1.0 × 1.0 × 0.6 × 0.8 = 0.48

# 4) Disputed + active strong + unresolved
engine.dispute_claim_if_ready(claim)  # status → DISPUTED
engine.compute_effective_confidence(claim)
# → 1.0 × 0.5 × 0.6 × 0.8 = 0.24

# 5) Refuted + 어떤 active + 어떤 gap (Sub-decision P 자연 보존)
engine._claims[claim] = replace(..., status=REFUTED)
engine.compute_effective_confidence(claim)
# → 1.0 × 0.0 × X × Y = 0.0
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `3fdb804` | docs(contract): define effective confidence gap modifier MVP (§28) |
| 2 | `3bfcef2` | test(core): lock gap modifier invariants |
| 3 | `5c64475` | feat(engine): activate gap modifier |
| 4 | (this) | docs(dev): PR12-D record |

## 주요 설계 결정 (§28)

### 1. Sub-decision T — Constant 0.8

```python
_GAP_PENALTY_MODIFIER = 0.8
```

| 옵션 | 채택 | 이유 |
|---|---|---|
| (T-0.3) 강한 페널티 | ✗ | gap 부족이 거의 disputed 수준 — 과한 의미 부여 |
| (T-0.5) 중간 (PR11-D `disputed` / PR11-C max attenuation 와 동급) | ✗ | gap 신호 = lifecycle / contradiction 신호와 같은 무게 |
| **(T-0.8) 약한 페널티** | ✓ | "정보 부족" 의 약한 신호 |

**0.8 의 의미축**: gap = "incomplete", contradiction = "contradicted", status
= "lifecycle 상태". PR12-D 가 가장 약한 신호 (20% 감쇠).

### 2. Sub-decision U — Binary, N 무관

```text
unresolved gap 1+ → 0.8
그 외 → 1.0
N 의존 없음 (1개든 10개든 동일).
```

| 옵션 | 채택 | 이유 |
|---|---|---|
| **(U-binary)** | ✓ | "최소 연결 PR" 정신. PR11-C Sub-decision O ("최신 1개만") 와 같은 단순성 |
| (U-N-dependent) | ✗ | 함수 형태 / saturation 추가 결정 부담 |

### 3. PR5 와의 정합 — input 활용만

`gap_modifier` 는 PR5 의 `gap_resolution(g.id)` 를 input 으로만 활용. PR5
의 의미 / return / first-keep / KeyError 동작 변경 0.

```python
def gap_modifier(claim_id):
    gaps = self.gaps_for_claim(claim_id)  # PR5
    if not gaps:
        return 1.0
    if all(self.gap_resolution(g.id) is not None for g in gaps):  # PR5
        return 1.0
    return _GAP_PENALTY_MODIFIER  # 0.8
```

### 4. PR11-D / PR11-C 와의 정합 — 시그니처 보존

```python
# PR11-D / PR11-C (변경 안 됨)
def compute_effective_confidence(self, claim_id: int) -> ScoreValue: ...
```

PR12-D 는 **시그니처 변경 0**:
- `claim_id: int` 입력 그대로
- `ScoreValue` 반환 그대로
- unknown claim_id → KeyError 그대로
- 본문에 `× gap_modifier(claim_id)` 추가만

### 5. 의미 분리 — gap vs contradiction vs status

| modifier | 의미 신호 | 강도 | 값 |
|---|---|---|---|
| status_modifier | lifecycle 상태 (확정 / 반박 / 격리) | **강** | refuted = 0.0, disputed = 0.5 |
| freshness_modifier (PR11-C) | 최근 contradiction strength | **중** | max 50% 감쇠 |
| **gap_modifier (PR12-D)** | **정보 부족** | **약** | **20% 감쇠 (= 0.8)** |

gap 신호가 contradiction / lifecycle 보다 명확히 약한 게 §28.2 명제의 직접
표현.

### 6. Sub-decision P 자연 보존 — refuted = 0

```text
refuted:
  status_modifier = 0.0
  freshness_modifier × gap_modifier 무엇이든
  effective = base × 0.0 × X × Y = 0.0
```

PR11-C Sub-decision P 와 같은 자연 결과. gap_modifier 가 무엇이든 status=0
이면 effective=0.

### 7. 결정성 (Determinism)

```text
같은 (claim.base_confidence, claim.status,
      active_contradictions_by_freshness(c),
      gaps_for_claim(c), gap_resolution(g) for g in gaps,
      evidence.strength) → 항상 같은 effective_confidence
```

PR12-D 는:
- wall-clock 안 봄
- random / external state 안 봄
- PR5 `gaps_for_claim` / `gap_resolution` 결정성 그대로 유지

PR11-D / PR11-C 결정성 그대로 + PR5 gap 의 결정성 통합.

### 8. Private constant

```python
# Engine module level
_GAP_PENALTY_MODIFIER = 0.8
```

- **Public export 안 함** (engine 내부 private)
- PR10-A `_REFUTATION_STRENGTH_THRESHOLD` / PR11-C `_FRESHNESS_PENALTY_WEIGHT`
  / PR11-D `_STATUS_MODIFIER_*` 와 동일 정신
- 미래 정책 변경 자유 확보

## 불변식 (테스트로 잠금)

§28.12 의 24 invariant:

1. unknown claim_id → `KeyError`
2~5. gap 0 + 4 status → 기존 effective (gap_modifier=1.0)
6. 모든 gap resolved → gap_modifier=1.0
7~9. **unresolved 1+ + candidate/confirmed/disputed → 추가 감쇠** ★
10. unresolved 1+ + refuted → 0.0 (Sub-decision P)
11. **N 무관 (1 vs 10)** ★ (Sub-decision U)
12. **resolved + unresolved 혼재 → 0.8** ★
13. **PR11-C freshness × PR12-D gap 결합** ★
14~18. PR5 / PR10-A / PR11-B / PR11-A / PR9-A 무변화
19. PR11-D `_STATUS_MODIFIER_*` 값 무변화 (간접)
20. effective ≤ base (no boost)
21. compute is read-only
22. determinism
23. `_GAP_PENALTY_MODIFIER` private (ragcore + ragcore.types 미노출)
24. 기존 589 회귀 없음

## 테스트

**612 passing** in ~0.41s (589 → 612, delta 정확히 +23)

### Test-first 흐름 (PR11-C 63차 동일 mixed pattern)

71차 (test-first 잠금):

```text
23 새 tests 추가
실행 결과 (의도된 mixed 분포):
- 6 fails (의도된 assertion — gap_modifier 미적용):
    * test_candidate_with_unresolved_gap_attenuates              (expected 0.8, actual 1.0)
    * test_confirmed_with_unresolved_gap_attenuates              (expected 0.8, actual 1.0)
    * test_disputed_with_unresolved_gap_compounds                (expected 0.4, actual 0.5)
    * test_one_or_many_unresolved_same_modifier                  (Sub-decision U binary)
    * test_resolved_and_unresolved_mixed_attenuates              (혼재 시 0.8)
    * test_confirmed_with_freshness_and_gap_compounds            (PR11-C × PR12-D, expected 0.48)
- 17 pass (이미 정합):
    * TestEffectiveConfidenceGapModifier (5): KeyError + gap 0 + 4 status + refuted+gap
    * TestGapModifierResolutionSemantics (1): 모든 resolved → 1.0
    * TestPriorPolicyUnchanged (5): PR5 / PR10-A / PR11-B / PR11-A / PR9-A 무변화
    * TestGapModifierIsolation (3): no boost / read-only / deterministic
    * TestGapModifierPrivacy (2): _GAP_PENALTY_MODIFIER 미노출
    * 1 추가 (invariant 10 inline: refuted + unresolved → 0.0)
+ 기존 589 통과
```

이 17 pass 는 PR11-C 63차의 13 pass / PR11-A 59차의 3 pass 패턴 일관.

72차 (구현):

```text
- ragcore/engine.py:
    _GAP_PENALTY_MODIFIER = 0.8 (private)
    compute_effective_confidence 본문에 × gap_modifier 추가
실행 결과: 612 통과 (6 fail → 6 pass, 17 pass 유지)
```

### 변경 파일 (PR12-D 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §28 신설 (+271 lines) |
| `tests/test_engine_gap_modifier.py` | 신규 (23 tests, +431 lines) |
| `ragcore/engine.py` | 1 private constant + 본문 확장 (+36, -7) |
| `docs/dev/PR_016_GAP_MODIFIER_MVP.md` | 이 파일 (신규) |
| `ragcore/types.py` | **변경 없음** |
| `ragcore/__init__.py` | **변경 없음** |
| `ragcore/rule_output.py` | **변경 없음** (Sub-decision D 정합) |

### 테스트 분포

| 파일 | PR11-B 후 | PR12-D (71차) | PR12-D (72차) | 변동 |
|---|---|---|---|---|
| `test_engine_gap_modifier.py` | 0 | 23 (6 fail + 17 pass) | **23 (pass)** | +23 |
| 나머지 20 파일 | 589 | 589 | **589** | 0 |
| **Total** | 589 | 589 + 17 pass + 6 fail | **612** | **+23** |

### 신규 테스트 그룹

**TestEffectiveConfidenceGapModifier (10):** KeyError + gap 0 × 4 status + unresolved × 4 status + refuted+gap (Sub-decision P)
**TestGapModifierResolutionSemantics (3):** 모든 resolved + N 무관 binary + 혼재
**TestGapModifierWithFreshness (1):** ★ PR11-C × PR12-D 결합 (status × freshness × gap)
**TestPriorPolicyUnchanged (5):** PR5 / PR10-A / PR11-B / PR11-A / PR9-A 무변화
**TestGapModifierIsolation (3):** no boost (5 시나리오 loop) + read-only + deterministic
**TestGapModifierPrivacy (2):** ragcore + ragcore.types 미노출

## 구현 요약 (72차)

```python
# ragcore/engine.py (module level — _FRESHNESS_PENALTY_WEIGHT 다음)
_GAP_PENALTY_MODIFIER = 0.8  # Sub-decision T, private

# compute_effective_confidence 본문 (시그니처 / KeyError 그대로)
def compute_effective_confidence(self, claim_id):
    if claim_id not in self._claims:
        raise KeyError(...)
    claim = self._claims[claim_id]
    status_modifier = _STATUS_TO_MODIFIER[claim.status]      # PR11-D

    active = self.active_contradictions_by_freshness(claim_id)  # PR11-A query
    if not active:
        freshness_modifier = 1.0
    else:
        most_recent_evidence = self._evidences[active[0]]
        freshness_modifier = (
            1.0 - most_recent_evidence.strength.value * _FRESHNESS_PENALTY_WEIGHT
        )

    gaps = self.gaps_for_claim(claim_id)                      # PR5
    if not gaps:
        gap_modifier = 1.0
    elif all(self.gap_resolution(g.id) is not None for g in gaps):  # PR5
        gap_modifier = 1.0
    else:
        gap_modifier = _GAP_PENALTY_MODIFIER                  # 0.8

    return ScoreValue(
        claim.base_confidence.value
        * status_modifier
        * freshness_modifier
        * gap_modifier
    )
```

배치: module level constant 는 `_FRESHNESS_PENALTY_WEIGHT` 다음. 메서드는
PR11-C 의 위치 그대로 (본문만 확장).

`types.py` / `__init__.py` / `rule_output.py` 변경 0.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| N-dependent gap modifier (`f(N)` 형태) | Sub-decision U (binary, "최소 연결 PR" 정신) |
| Gap 종류별 가중치 (`gap_type` / `severity` / `required_evidence_type`) | 단순화. PR12+ |
| Gap freshness (오래된 gap 의 약한 페널티) | PR12+ |
| RuleStats modifier (`observed_precision` / `false_positive_rate`) | PR12+ |
| Contradiction count modifier | PR12+ |
| Lifecycle history-based modifier | PR12+ |
| `superseded` / `retracted` 추가 상태 | PR12-G 자리 |
| Confidence boost (modifier > 1.0) | PR11-D Sub-decision N 일관 — 영구 OOS |
| Caller-driven modifier / config injection | PR10-A / PR11-D 정신 |
| LLM / semantic confidence | core 밖 |
| Mutable confidence / setter | immutability |
| Public `_GAP_PENALTY_MODIFIER` | engine 내부 private |
| Wall-clock timestamp | PR10-A/B / PR11-A/B/C/D 일관 영구 OOS |
| PR5 `gap_resolution` 정책 변경 | input 활용만 |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| G | **PR12-G: `superseded` / `retracted` 추가 상태** | 중 (도메인 운영 신호 — claim 의 "취소" / "대체") |
| E | **Contradiction count modifier** — active 개수 기반 추가 감쇠 | 중 |
| F | **RuleStats-based modifier** — `observed_precision` / `false_positive_rate` | 중 |
| H | **Persistence / 직렬화** | 중 |
| I | **fire_rule audit** — PR10-B history 를 transition 외 영역으로 확장 | 중 |
| J | **Gap freshness / type-aware modifier** — PR12-D 의 단순 binary 를 정교화 | 중 |
| K | Engine bulk fire / `not` combinator / trace 직렬화 | 낮음 |
| L | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **G (superseded/retracted) 또는 H (persistence)**.

G 는 도메인 운영 의미 (취소 / 대체) 가 명확해지면. PR8 의 disputed 와 다른
의미 — disputed 는 재판정 대기, superseded 는 더 새 정보로 교체.

H 는 lifecycle + audit + scoring 4-modifier 완성 이후 운영 단계 진입. engine
state + lifecycle history 저장/복원 — 분리된 process 간 호환 (현재는 in-memory only).

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §28](../contracts/05_DATA_CONTRACT_MVP.md) — Effective confidence gap modifier (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §26](../contracts/05_DATA_CONTRACT_MVP.md) — Effective freshness modifier (PR11-C, 변경 안 됨)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §24](../contracts/05_DATA_CONTRACT_MVP.md) — Effective confidence (PR11-D base)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §17](../contracts/05_DATA_CONTRACT_MVP.md) — Gap resolution (PR5 base — input source)
- [docs/dev/PR_005_GAP_RESOLUTION_MVP.md](PR_005_GAP_RESOLUTION_MVP.md) — PR5 base
- [docs/dev/PR_012_EFFECTIVE_CONFIDENCE_MVP.md](PR_012_EFFECTIVE_CONFIDENCE_MVP.md) — PR11-D base
- [docs/dev/PR_014_EFFECTIVE_FRESHNESS_MODIFIER_MVP.md](PR_014_EFFECTIVE_FRESHNESS_MODIFIER_MVP.md) — PR11-C base
- [docs/dev/PR_015_FRESHNESS_REFUTE_MVP.md](PR_015_FRESHNESS_REFUTE_MVP.md) — PR11-B (이전 PR)

## How to Run

```bash
git checkout feat/gap-modifier-mvp
pip install -e .
pytest -v
```

612 tests in ~0.41s. No new external dependencies.

## Result

PR12-D 가 PR5 의 gap resolution 의미를 PR11-D 의 modifier 분해 자리에 처음
연결. **4-modifier composition 완성**:

```python
effective = base × status_modifier × freshness_modifier × gap_modifier
```

PR1 부터 PR12-D 까지의 noun → verb 연결 패턴:

```text
PR5  noun: gap_resolution (gap_id → evidence_id)
PR11-A noun: evidence_freshness / active_contradictions_by_freshness
PR11-D verb: effective = base × status_modifier (stub 활성화)
PR11-C verb: × freshness_modifier (continuous attenuation)
PR12-D verb: × gap_modifier (binary weak attenuation) ★
```

엔진의 observable axes + scoring 정교화 (PR12-D 까지):

```text
"이 Claim 의 현재 상태는?"                    → status (PR6~PR10-A)
"어떤 path 로 여기에 왔는가?"                  → claim_lifecycle_history (PR10-B)
"현재 상태에서 얼마나 믿을 수 있는가?"          → compute_effective_confidence (PR11-D + PR11-C + PR12-D) ★
"각 evidence 의 등록 순서는?"                  → evidence_freshness (PR11-A)
"활성 contradiction 을 최신순으로 보면?"        → active_contradictions_by_freshness (PR11-A)
```

PR12-D 의 본질:

> **PR5 의 gap resolution 의미가 effective confidence 에 처음 연결된 PR.**
> 4-modifier composition (PR11-D × PR11-C × PR12-D) 완성. gap 신호는
> contradiction / lifecycle 보다 약한 "정보 부족" 의 의미축.

남은 결정점 (gap freshness, contradiction count, RuleStats, superseded /
retracted, persistence, fire_rule audit) 은 PR12+ 또는 PR13+ 에서.
