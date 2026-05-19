# PR #013 — Evidence Freshness Query MVP (PR11-A)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/evidence-freshness-mvp` → `main`
> Base: `c9eaa43` (PR11-D merged)
> Tests: 547 passing (local)

## 목적

PR11-D 까지의 흐름:

```text
evidence 의 등록 순서는 evidence.id 에 암묵적으로 표현됨
→ caller 가 직접 evidence.id 비교해야 freshness 비교 가능
→ freshness 가 1급 개념 아님
```

PR11-A 추가:

```text
evidence_freshness(ev) → evidence.id (1급 의미)
active_contradictions_by_freshness(c) → freshness desc tuple

엔진은 freshness 자체에 따라 어떤 결정도 자동으로 내리지 않음.
caller 가 freshness 를 보고 의사결정에 사용할 자유만 부여.
```

## PR11-A 의 한 줄 정의

> **PR11-A 는 freshness 를 lifecycle 결정에 도입하는 PR 이 아니라, freshness
> 라는 새 관찰 축을 read-only query 로 처음 노출하는 PR 이다.**

> **freshness 는 정책이 아니라 query. PR11-A 는 판단을 바꾸지 않고, 판단에
> 쓸 수 있는 순서 정보를 먼저 고정한다.**

PR10-B 가 lifecycle transition 의 audit 축을 query 로 노출했듯, PR11-A 는
evidence 의 freshness 축을 query 로 노출. **engine 동작 변경 0**.

## 핵심 명제 (§25.2)

```text
Freshness is evidence-registration order, not wall-clock time.

PR11-A exposes freshness as read-only query state.
It does not change lifecycle transitions, refutation policy, or effective
confidence scoring.
```

한국어:

```text
Freshness 는 evidence 의 등록 순서이며, wall-clock 시간이 아니다.

PR11-A 는 freshness 를 read-only query 로만 노출한다.
lifecycle 전이 / refute 정책 / effective confidence scoring 모두 변경하지 않는다.
```

## 닫힌 흐름 (PR11-A 추가분)

```python
# 1) Evidence 등록 — 등록 순서로 freshness 가 자연 결정
ev_a = engine.add_evidence(...)  # id=1
ev_b = engine.add_evidence(...)  # id=2
ev_c = engine.add_evidence(...)  # id=3

engine.evidence_freshness(ev_a)  # → 1
engine.evidence_freshness(ev_b)  # → 2
engine.evidence_freshness(ev_c)  # → 3  (most recent)

# 2) Contradiction 등록 — 의도적으로 뒤섞은 순서
engine.register_contradiction(claim, ev_b)
engine.register_contradiction(claim, ev_a)
engine.register_contradiction(claim, ev_c)

# 3) 두 view — 같은 set, 다른 정렬
engine.active_contradictions_for_claim(claim)
# → (1, 2, 3)   PR9-A: evidence_id asc

engine.active_contradictions_by_freshness(claim)
# → (3, 2, 1)   PR11-A: evidence_id desc (most recent first)

# 4) Resolved contradiction 은 양쪽 모두에서 제외
engine.register_contradiction_resolution(claim, ev_b)

engine.active_contradictions_for_claim(claim)
# → (1, 3)   asc, ev_b 빠짐

engine.active_contradictions_by_freshness(claim)
# → (3, 1)   desc, ev_b 빠짐

# 5) PR10-A refute / PR11-D effective 는 변화 없음
engine.refute_disputed_claim_if_ready(...)   # 정책 그대로
engine.compute_effective_confidence(...)      # scoring 그대로
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `4468f0e` | docs(contract): define evidence freshness query MVP (§25) |
| 2 | `349940d` | test(core): lock evidence freshness invariants |
| 3 | `1378dae` | feat(engine): add freshness queries |
| 4 | (this) | docs(dev): PR11-A record |

## 주요 설계 결정 (§25)

### 1. Sub-decision A — Freshness = `evidence.id`

```python
def evidence_freshness(self, evidence_id):
    if evidence_id not in self._evidences:
        raise KeyError(...)
    return evidence_id
```

| 후보 | 채택 | 이유 |
|---|---|---|
| (a) `evidence.id` | ✓ | PR1 `_next_id` 카운터가 이미 등록 순서 표현 |
| (b) `_lifecycle_seq` (PR10-B) | ✗ | lifecycle transition seq 이지 evidence 등록 seq 아님 |
| (c) 새 freshness counter | ✗ | 불필요한 carrier 추가 |
| (d) wall-clock timestamp | ✗ | PR10-A / PR10-B 의 "외부 clock 안 봄" 정신 위반 |

값 의미:
- evidence.id 가 클수록 더 최근 등록
- 같은 engine 안에서만 의미 (cross-engine 비교 무의미)

### 2. Sub-decision B — Query only (engine 동작 변경 0)

PR11-A 는 다음을 **건드리지 않는다**:

| 영역 | PR11-A 영향 |
|---|---|
| 5 lifecycle API | 없음 |
| `refute_disputed_claim_if_ready` 의 threshold 정책 (PR10-A) | 없음 |
| `compute_effective_confidence` 의 status_modifier (PR11-D) | 없음 |
| `register_contradiction*` | 없음 |
| `_record_claim_lifecycle_transition` (PR10-B) | 없음 |
| `_contradictions` / `_resolved_contradictions` 인덱스 | 없음 |
| `_lifecycle_seq` / `_claim_lifecycle_events` | 없음 |

PR11-A 가 추가하는 것은 **2 read-only query API 만**. caller 가 freshness 로
무엇을 하든 engine 상태 영향 없음.

### 3. Sub-decision C — C-pair API

```python
evidence_freshness(evidence_id) -> int                    # primitive
active_contradictions_by_freshness(claim_id) -> tuple[int, ...]  # 자주 쓰일 패턴
```

| 옵션 | 채택 | 이유 |
|---|---|---|
| (C-minimal) primitive 만 | ✗ | caller 가 매번 정렬 코드 작성 |
| **(C-pair) primitive + 패턴** | ✓ | 균형. PR9-A 차집합 의미는 그대로, 정렬 키만 다름 |
| (C-extensive) more | ✗ | 사용 패턴 보고 후속 PR 에서 결정 |

### 4. PR9-A 와의 정합 — 같은 set, 다른 정렬

```python
# PR9-A (변경 없음)
active_contradictions_for_claim(c)
# = (contradictions_for_claim(c) - resolved_contradictions_for_claim(c))
# 정렬: evidence_id asc

# PR11-A (신규)
active_contradictions_by_freshness(c)
# = 같은 set
# 정렬: evidence_id desc (freshness desc — 큰 id 가 최근)
```

PR9-A 의 차집합 의미 그대로 보존. PR11-A 가 추가하는 것은 **다른 view** 만.

### 5. Read-only 보장

```python
# query 가 어떤 state 도 변경하지 않음:
#   _contradictions / _resolved_contradictions / _gap_resolutions
#   _claims (status 포함)
#   _claim_lifecycle_events / _lifecycle_seq
#   _evidences / _next_id (read만, 변경 없음)
```

### 6. PR10-B 패턴 일관 — audit/view 축 확장

| PR | 새 축 | 형태 |
|---|---|---|
| PR10-B | lifecycle transition history | read-only query (`claim_lifecycle_history`) |
| **PR11-A** | **evidence freshness** | **read-only query (`evidence_freshness` / `active_contradictions_by_freshness`)** |

두 PR 모두 "engine 의 새 관찰 축을 read-only 로 노출" 패턴. caller 가 그 위에
의사결정을 작성할 수 있음.

### 7. 외부 의존 절대 안 봄

```text
PR10-A: wall-clock 안 봄 (strength threshold 만)
PR10-B: wall-clock 안 봄 (per-engine sequence id)
PR11-D: wall-clock 안 봄 (status modifier 만)
PR11-A: wall-clock 안 봄 (evidence.id 만)
```

이 일관성이 모든 lifecycle 관련 PR 의 공통 원칙.

## 불변식 (테스트로 잠금)

§25.8 의 14 invariant:

1. `evidence_freshness` unknown evidence_id → `KeyError`
2. `active_contradictions_by_freshness` unknown claim_id → `KeyError`
3. `evidence_freshness(ev) == ev` (primitive)
4. 더 최근 등록 evidence → 더 큰 freshness
5. **`active_contradictions_by_freshness` desc order ★**
6. **PR9-A 와 같은 set** (정렬 키만 다름)
7. **resolved contradiction 제외** (차집합 정합)
8. **PR10-A `refute_disputed_claim_if_ready` 무변화 ★** (Sub-decision B)
9. **PR11-D `compute_effective_confidence` 무변화 ★** (Sub-decision B)
10. PR9-A `active_contradictions_for_claim` asc 정렬 무변화
11. read-only (engine state 무변화)
12. 빈 active → 빈 tuple
13. freshness 등록 시점 고정 (시간 무관)
14. 기존 534 회귀 없음 (전체 통과로 입증)

## 테스트

**547 passing** in ~0.39s (534 → 547, delta 정확히 +13)

### Test-first 흐름 (PR11-D 와 동일 mixed pattern)

59차 (test-first 잠금):

```text
13 새 tests 추가
실행 결과 (의도된 mixed 분포):
- 10 fails (모두 AttributeError):
    * evidence_freshness missing × 5
    * active_contradictions_by_freshness missing × 5
-  3 pass (Sub-decision B 정합 — 이미 통과):
    * test_pr10a_refute_disputed_unchanged
    * test_pr11d_compute_effective_confidence_unchanged
    * test_pr9a_active_contradictions_asc_unchanged
+ 기존 534 통과
```

이 3 pass 는 PR11-A 의 본질을 **미리 보장** — PR11-A 가 query 만 추가하고 정책
변경 0 이라는 사실이 코드 구조 차원에서 이미 잠겨 있음. PR8 39차의
`TestSubDecisionD` 와 PR10-A 47차 / PR11-D 55차 의 부분 pass 패턴과 동일.

60차 (구현):

```text
- ragcore/engine.py: # ---- Evidence freshness (PR11-A §25) ----  섹션 신설
- 2 query 메서드 추가 (evidence_freshness + active_contradictions_by_freshness)
실행 결과: 547 통과 (10 fail → 10 pass, 3 pass 유지)
```

### 변경 파일 (PR11-A 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §25 신설 (+206 lines) |
| `tests/test_engine_evidence_freshness.py` | 신규 (13 tests, +280 lines) |
| `ragcore/engine.py` | 신규 섹션 + 2 query 메서드 (+47 lines) |
| `docs/dev/PR_013_EVIDENCE_FRESHNESS_MVP.md` | 이 파일 (신규) |
| `ragcore/types.py` | **변경 없음** (새 dataclass / 상수 없음) |
| `ragcore/__init__.py` | **변경 없음** (새 export 없음) |
| `ragcore/rule_output.py` | **변경 없음** (Sub-decision D 정합) |

### 테스트 분포

| 파일 | PR11-D 후 | PR11-A (59차) | PR11-A (60차) | 변동 |
|---|---|---|---|---|
| `test_engine_evidence_freshness.py` | 0 | 13 (10 fail + 3 pass) | **13 (pass)** | +13 |
| 나머지 17 파일 | 534 | 534 | **534** | 0 |
| **Total** | 534 | 534 + 3 pass + 10 fail | **547** | **+13** |

### 신규 테스트 그룹

**TestEvidenceFreshness (4):** primitive (KeyError + ev==freshness + monotonic + 등록 시점 고정)
**TestActiveContradictionsByFreshness (5):** KeyError + desc order + PR9-A set 동일 + resolved 제외 + 빈 tuple
**TestQueriesAreReadOnly (1):** contradictions / resolved / active / status / history 보존
**TestPriorPolicyUnchanged (3):** PR10-A refute / PR11-D effective / PR9-A asc 무변화 (★ Sub-decision B 잠금, 이미 pass)

## 구현 요약 (60차)

```python
# ragcore/engine.py — # ---- Evidence freshness (PR11-A §25) ----

def evidence_freshness(self, evidence_id: int) -> int:
    if evidence_id not in self._evidences:
        raise KeyError(...)
    return evidence_id

def active_contradictions_by_freshness(self, claim_id: int) -> tuple[int, ...]:
    if claim_id not in self._claims:
        raise KeyError(...)
    contras = self._contradictions.get(claim_id, set())
    resolved = self._resolved_contradictions.get(claim_id, set())
    return tuple(sorted(contras - resolved, reverse=True))
```

배치: PR10-B `claim_lifecycle_history` 직후 / `register_rule` 직전.

`types.py` / `__init__.py` / `rule_output.py` 변경 0.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| PR10-A `refute_disputed_claim_if_ready` 정책 변경 (freshness 가중치) | **PR11-B 자연 후속** (Sub-decision B 정신) |
| PR11-D modifier 분해 (status × freshness) | **PR11-C 또는 PR12+** |
| 새 `freshness_for_claim(claim_id)` 같은 claim 전체 freshness 조회 | 사용 패턴 보고 후속 |
| `most_recent_evidence(claim_id)` 같은 single-most-recent 조회 | (C-extensive) — 후속 |
| `freshness_rank(evidence_id)` normalized rank | 별도 결정점 |
| Wall-clock timestamp 도입 | PR10-A / PR10-B / PR11-D 와 일관 영구 OOS |
| Freshness based scoring / refute / lifecycle 자동 결정 | side effect 의 side effect — 명시성 위반 |
| 새 dataclass / 새 public 상수 | engine read-only query 만 |
| Persistence / 직렬화 | 별도 PR |
| Cross-engine freshness 비교 | per-engine 의미 (PR10-B Sub-decision L 정신) |
| `evidence.id` 외 다른 freshness signal | Sub-decision A 일관 |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| B | **PR11-B — PR10-A refute 정책 + freshness 통합** — active 중 가장 최근 contradiction 의 strength 우선 또는 freshness 기반 tie-breaking | 높음 (PR11-A 가 noun 노출, PR11-B 가 verb 통합) |
| C | **PR11-C — PR11-D modifier 분해 (status × freshness)** — `effective = base × status_modifier × freshness_modifier` | 중 (PR11-D §24.5 의 "modifier 분해" 활용) |
| D | **Gap-based modifier** — unresolved gap 페널티 | 중 |
| E | **Contradiction strength modifier** — active strength 가중 | 중 |
| F | **RuleStats-based modifier** — observed_precision / false_positive_rate | 중 |
| G | **`superseded` / `retracted` 추가 상태** | 중 (도메인 요구 명확해진 뒤) |
| H | **Persistence / 직렬화** — engine state + lifecycle history 저장/복원 | 중 |
| I | **fire_rule audit** — PR10-B history 를 transition 외 영역으로 확장 | 중 |
| J | Engine bulk fire / `not` combinator / trace 직렬화 | 낮음 |
| K | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **B (PR11-B, refute 정책 + freshness 통합)**.

이유:
- PR11-A 가 freshness 를 noun 으로 노출 — PR11-B 가 그 noun 을 verb (정책 결정)
  에 통합하는 자연 후속
- PR10-A 의 "active 중 단 하나라도 strength >= 0.8" 정책이 freshness 우선 정책
  으로 자연 확장 가능 (예: "가장 최근 active contradiction 의 strength" 우선)
- PR11-A 가 이미 잠근 view (`active_contradictions_by_freshness`) 를 PR11-B
  가 직접 활용 가능 — 새 인덱스 추가 없음

대안: **C (PR11-C, effective modifier 분해)** — PR11-D §24.5 의 명시적 미래
자리. status × freshness 분해. PR11-A 의 query 를 input 으로 자연 통합.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §25](../contracts/05_DATA_CONTRACT_MVP.md) — Evidence freshness query (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §24](../contracts/05_DATA_CONTRACT_MVP.md) — Effective confidence (PR11-D, 변경 안 됨)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §22](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed refutation (PR10-A, 변경 안 됨)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §21](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed resolution (PR9-A, set 의미 보존)
- [docs/dev/PR_010_DISPUTED_REFUTATION_MVP.md](PR_010_DISPUTED_REFUTATION_MVP.md)
- [docs/dev/PR_011_LIFECYCLE_HISTORY_MVP.md](PR_011_LIFECYCLE_HISTORY_MVP.md) — PR10-B (audit query 패턴)
- [docs/dev/PR_012_EFFECTIVE_CONFIDENCE_MVP.md](PR_012_EFFECTIVE_CONFIDENCE_MVP.md) — PR11-D base (변경 안 됨)

## How to Run

```bash
git checkout feat/evidence-freshness-mvp
pip install -e .
pytest -v
```

547 tests in ~0.39s. No new external dependencies.

## Result

PR11-A 가 freshness 라는 새 관찰 축을 **read-only query 로 처음 노출**. PR10-B
가 lifecycle audit 축을 노출했듯, PR11-A 는 evidence registration order 축을
같은 패턴으로 노출.

엔진의 read 가능한 관찰 축 (지금까지):

```text
"이 Claim 의 현재 상태는?"                    → status (PR6~PR10-A)
"어떤 path 로 여기에 왔는가?"                  → claim_lifecycle_history (PR10-B)
"현재 상태에서 얼마나 믿을 수 있는가?"          → compute_effective_confidence (PR11-D)
"각 evidence 의 등록 순서는?"                  → evidence_freshness (PR11-A) ★
"활성 contradiction 을 최신순으로 보면?"        → active_contradictions_by_freshness (PR11-A) ★
```

남은 결정점 (PR11-B refute 통합, PR11-C modifier 분해, gap modifier,
RuleStats, superseded/retracted, persistence) 은 후속 PR 에서.

PR11-A 의 본질:

> **"정책 변경" 이 아니라 "freshness view 를 추가한 PR".** PR11-A 는 판단을
> 바꾸지 않고, 판단에 쓸 수 있는 순서 정보를 먼저 고정한다.
