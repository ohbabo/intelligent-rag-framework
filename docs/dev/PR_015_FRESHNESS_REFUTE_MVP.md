# PR #015 — Freshness-aware Refute MVP (PR11-B)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/freshness-refute-mvp` → `main`
> Base: `a6d9911` (PR11-C merged)
> Tests: 589 passing (local)

## 목적

PR10-A 까지의 흐름:

```text
disputed + active 중 ANY strength >= 0.8 → refute_disputed_claim_if_ready → REFUTED
freshness 정렬 정보 안 봄.
```

PR11-A / PR11-C 까지:

```text
PR11-A: active_contradictions_by_freshness query (read-only)
PR11-C: effective = base × status × freshness_modifier (continuous attenuation)
```

PR11-B 추가:

```text
disputed + active FIRST (by freshness) strength >= 0.8
  → refute_disputed_claim_if_ready_by_freshness → REFUTED

sibling API. PR10-A 무변경.
```

## PR11-B 의 한 줄 정의

> **PR11-B 는 PR10-A 를 대체한 PR 이 아니라, refute 판단 경로를 sibling 으로
> 분리한 PR 이다.**

PR9-A `active_contradictions_for_claim` (asc) vs PR11-A
`active_contradictions_by_freshness` (desc) 가 같은 set 의 다른 정렬 view
였듯, PR11-B 는 PR10-A 의 refute 와 같은 status target (REFUTED) 의 다른
input view (FIRST by freshness 만) sibling.

## 핵심 명제 (§27.2)

```text
PR11-B introduces a sibling refute API that inspects the most recent active
contradiction only, not all of them.

PR10-A inspects ANY active contradiction.
PR11-B inspects FIRST (by freshness) active contradiction only.

Both produce CLAIM_STATUS_REFUTED. Both use the same threshold (0.8).
The difference is which input set the policy reads — not threshold, not output.

PR11-B does not change PR10-A semantics. Existing callers and tests of
PR10-A remain valid.
```

## API 비교 표

| | PR10-A | PR11-B |
|---|---|---|
| API | `refute_disputed_claim_if_ready` | `refute_disputed_claim_if_ready_by_freshness` |
| 진입 status | DISPUTED | DISPUTED |
| 검사 대상 | **ANY** active contradiction | **FIRST** (by freshness) active contradiction |
| Threshold | `>= 0.8` | `>= 0.8` (재사용) |
| 결과 status | REFUTED | REFUTED |
| transition label | `"refute_disputed_if_ready"` | `"refute_disputed_by_freshness_if_ready"` |

## 핵심 분리 케이스

```text
disputed Claim 에:
  ev_older  (strength=0.9, id=1)
  ev_recent (strength=0.3, id=2)

active_contradictions_by_freshness(c) → (ev_recent, ev_older)
                                         (desc, recent first)

PR10-A: ANY active strength >= 0.8?
  → ev_older (0.9) >= 0.8 → TRUE → REFUTED

PR11-B: FIRST by freshness strength >= 0.8?
  → ev_recent (0.3) < 0.8 → FALSE → disputed 유지
```

이 케이스가 PR10-A 와 PR11-B 의 의미 분리를 명확히 보여준다.

## 닫힌 흐름 (PR11-B 추가분)

```python
# 1) disputed Claim setup
_, claim_id = _candidate_claim(engine, base_confidence=1.0)
ev_older = engine.add_evidence(claim_id, ..., strength=0.9)  # id=1
ev_recent = engine.add_evidence(claim_id, ..., strength=0.3) # id=2
engine.register_contradiction(claim_id, ev_older)
engine.register_contradiction(claim_id, ev_recent)
engine._claims[claim_id] = replace(..., status=CONFIRMED)
engine.dispute_claim_if_ready(claim_id)
# status = DISPUTED, active = {ev_older(0.9), ev_recent(0.3)}

# 2) PR11-B 호출 — FIRST=ev_recent(0.3) < 0.8 → False
engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
# → False, disputed 유지

# 3) PR10-A 호출 — ANY=ev_older(0.9) >= 0.8 → True
engine.refute_disputed_claim_if_ready(claim_id)
# → True, REFUTED

# 4) lifecycle history audit
engine.claim_lifecycle_history(claim_id)
# → ((dispute_if_ready ...), (refute_disputed_if_ready ...))
#   PR10-A path 가 audit 됨
```

대안 시나리오 (older weak + recent strong):

```python
ev_older = engine.add_evidence(..., strength=0.3)   # id=1
ev_recent = engine.add_evidence(..., strength=0.9)  # id=2
# active_by_freshness → (ev_recent, ev_older)

# PR11-B 호출 — FIRST=ev_recent(0.9) >= 0.8 → True, REFUTED
engine.refute_disputed_claim_if_ready_by_freshness(claim_id)
# → True

engine.claim_lifecycle_history(claim_id)
# → ((dispute_if_ready ...), (refute_disputed_by_freshness_if_ready ...))
#   PR11-B path 가 audit 됨
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `580466b` | docs(contract): define freshness-aware disputed refutation MVP (§27) |
| 2 | `02d7cc6` | test(core): lock freshness-aware refute invariants |
| 3 | `3a45ad4` | feat(engine): activate freshness-aware refute |
| 4 | (this) | docs(dev): PR11-B record |

## 주요 설계 결정 (§27)

### 1. Sibling pattern — PR10-A 변경 0

PR9-A asc vs PR11-A desc 패턴 일관. 두 API 가 같은 set 을 다른 view 로 본다:
- PR10-A: ANY view (모든 active 중 하나라도 >= 0.8)
- PR11-B: FIRST view (가장 최근 active 의 strength >= 0.8)

PR10-A 의 시그니처 / 동작 / threshold 모두 변경 0. PR10-A 의 기존 caller /
테스트 모두 그대로 유효.

### 2. Sub-decision Q — Trigger 정의

```python
active = self.active_contradictions_by_freshness(claim_id)  # PR11-A query
if not active: return False
most_recent = self._evidences[active[0]]
if most_recent.strength.value >= _REFUTATION_STRENGTH_THRESHOLD: refute
```

`active[0]` 만 본다. PR11-C Sub-decision O (최신 1개만) 정신 일관.

### 3. Sub-decision R — Threshold 재사용

```python
# 기존 PR10-A constant 그대로
_REFUTATION_STRENGTH_THRESHOLD = 0.8
```

**새 상수 도입 안 함**. PR10-A 와 같은 의미축. 두 정책의 차이는 input set
만 (ANY vs FIRST). threshold 도 달라지면 의미 분기 부담 큼.

### 4. Sub-decision S — Transition label 분리

PR10-B 의 5 → 6 transition labels:

| label | API | path |
|---|---|---|
| `"confirm_if_ready"` | PR6 | candidate → confirmed |
| `"refute_if_ready"` | PR7 | candidate → refuted |
| `"dispute_if_ready"` | PR8 | confirmed → disputed |
| `"resolve_disputed_if_ready"` | PR9-A | disputed → confirmed |
| `"refute_disputed_if_ready"` | PR10-A | disputed → refuted (ANY) |
| **`"refute_disputed_by_freshness_if_ready"`** | **PR11-B** | **disputed → refuted (FIRST by freshness)** |

PR10-B Sub-decision I (private string literal audit label) 정합. caller 가
`claim_lifecycle_history` 의 `transition` 으로 두 refute path 구분 가능.

### 5. PR9-A / PR10-A / PR11-B mutual exclusivity (§27.8)

| Claim 상태 + active | PR9-A resolve | PR10-A refute | PR11-B refute_by_freshness |
|---|---|---|---|
| disputed + active 0 | **True** (confirmed 복귀) | False | False |
| disputed + ANY≥0.8, FIRST<0.8 | False (active 잔존) | **True** (REFUTED) | False |
| disputed + FIRST≥0.8 | False | **True** | **True** |
| disputed + 모두 weak | False | False | False (disputed 유지) |

세 API 가 같은 시점에 동시 True 불가 (PR9-A 는 active 0 필요, PR10-A/B 는
active 1+ 필요). 호출 순서로 어느 path 가 audit 에 기록되는지 결정.

### 6. PR11-C 와 의미 분리 보존

| | PR11-C | PR11-B |
|---|---|---|
| 영향 | scoring 감쇠 | status 전이 |
| 표현 | continuous attenuation (`× 0.5` multiplier) | binary trigger (`>= 0.8`) |
| 상수 | `_FRESHNESS_PENALTY_WEIGHT = 0.5` | `_REFUTATION_STRENGTH_THRESHOLD = 0.8` (재사용) |
| Trigger evidence | `active[0]` (PR11-A query) | `active[0]` (PR11-A query) |

같은 `active[0]` 를 input 으로 보지만:
- PR11-C: strength → continuous attenuation
- PR11-B: strength → binary refute trigger

의미 충돌 없음.

### 7. lifecycle history 자동 통합

PR11-B 의 True path 가 PR10-B `_record_claim_lifecycle_transition` 호출 —
시그니처 / 호출 패턴 모두 PR10-A 와 동일:

```python
# True path
old_status = claim.status  # DISPUTED
self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_REFUTED)
self._record_claim_lifecycle_transition(
    claim_id, old_status, CLAIM_STATUS_REFUTED,
    "refute_disputed_by_freshness_if_ready",  # Sub-decision S
)
return True
```

caller 가 lifecycle history 의 `transition` 으로 refute path 구분 가능 —
PR10-B 의 audit 본질.

## 불변식 (테스트로 잠금)

§27.12 의 21 invariant:

1. unknown claim_id → `KeyError`
2. status guard 3 (candidate / confirmed / refuted → False)
3. disputed + active 0 → `False`
4. disputed + FIRST < 0.8 → `False`
5. **disputed + FIRST >= 0.8 → `True`, REFUTED ★**
6. Threshold boundary 0.8 정확 → `True`
7. Threshold 직하 0.799999 → `False`
8. **older strong + recent weak → `False`** ★ (Sub-decision Q, PR10-A 와 다름)
9. Resolved contradiction 제외 (PR9-A 차집합 정합)
10. refuted 재호출 → `False` (idempotent)
11. **lifecycle event 기록, transition label = "refute_disputed_by_freshness_if_ready"** ★
12. **PR10-A `refute_disputed_claim_if_ready` 무변화** ★
13. **PR11-C `compute_effective_confidence` 무변화** ★
14. PR11-A query 무변화
15. PR9-A asc 무변화
16. Isolation (gap state / contradictions / resolved / base_confidence 무변화)
17. **PR9-A / PR10-A / PR11-B mutual exclusivity** ★
18. `_REFUTATION_STRENGTH_THRESHOLD` 재사용 (새 상수 없음 — Sub-decision R)
19. 새 transition label private literal (Sub-decision S)
20. 기존 564 회귀 없음

## 테스트

**589 passing** in ~0.40s (564 → 589, delta 정확히 +25)

### Test-first 흐름 (PR11-A / PR11-C 와 동일 mixed pattern)

67차 (test-first 잠금):

```text
25 새 tests 추가
실행 결과 (의도된 mixed 분포):
- 19 fails: AttributeError (refute_disputed_claim_if_ready_by_freshness 미구현)
-  6 pass (Sub-decision: 기존 정책 무변화로 이미 통과):
    * test_pr10a_refute_disputed_unchanged                      (★ Sub-decision: PR10-A 호환)
    * test_pr11c_effective_confidence_unchanged                  (★ PR11-C 무변화)
    * test_pr11a_queries_unchanged                                (★ PR11-A 무변화)
    * test_pr9a_active_contradictions_asc_unchanged               (★ PR9-A 무변화)
    * test_no_new_threshold_constant_in_public                    (★ Sub-decision R)
    * test_no_new_threshold_constant_in_types                     (★ Sub-decision R)
+ 기존 564 통과
```

이 6 pass 는 PR11-B 의 본질 (sibling API, 기존 정책 변경 0) 을 코드 구조 차원에서
미리 보장.

68차 (구현):

```text
- ragcore/engine.py: # ---- Freshness-aware refutation (PR11-B §27) ---- 섹션
- refute_disputed_claim_if_ready_by_freshness 메서드 추가
실행 결과: 589 통과 (19 fail → 19 pass, 6 pass 유지)
```

### 변경 파일 (PR11-B 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §27 신설 (+282 lines) |
| `tests/test_engine_freshness_refute.py` | 신규 (25 tests, +476 lines) |
| `ragcore/engine.py` | 신규 섹션 + 1 sibling API (+51 lines) |
| `docs/dev/PR_015_FRESHNESS_REFUTE_MVP.md` | 이 파일 (신규) |
| `ragcore/types.py` | **변경 없음** |
| `ragcore/__init__.py` | **변경 없음** |
| `ragcore/rule_output.py` | **변경 없음** (Sub-decision D 정합) |

### 테스트 분포

| 파일 | PR11-C 후 | PR11-B (67차) | PR11-B (68차) | 변동 |
|---|---|---|---|---|
| `test_engine_freshness_refute.py` | 0 | 25 (19 fail + 6 pass) | **25 (pass)** | +25 |
| 나머지 19 파일 | 564 | 564 | **564** | 0 |
| **Total** | 564 | 564 + 6 pass + 19 fail | **589** | **+25** |

### 신규 테스트 그룹

**TestRefuteDisputedByFreshness (10):** KeyError + status guard 3 + transition 2 + boundary 2 + idempotent
**TestSubDecisionQ (2):** ★ older strong + recent weak (PR10-A 와 다름) / older weak + recent strong
**TestResolvedExcluded (1):** PR9-A 차집합 정합 (resolved recent strong 제외)
**TestLifecycleHistoryIntegration (3):** ★ PR10-B audit 통합 + 신규 label / no-op 무기록 / label 분리
**TestPriorPolicyUnchanged (4):** PR10-A / PR11-C / PR11-A / PR9-A 무변화 (이미 pass)
**TestMutualExclusivity (2):** ★ PR9-A / PR10-A / PR11-B 가드 분리
**TestRefutationIsolation (1):** gap state / contradictions / base_confidence 보존
**TestThresholdReuse (2):** Sub-decision R (새 threshold 상수 없음, 이미 pass)

## 구현 요약 (68차)

```python
# ragcore/engine.py — # ---- Freshness-aware refutation (PR11-B §27) ----

def refute_disputed_claim_if_ready_by_freshness(self, claim_id):
    if claim_id not in self._claims:
        raise KeyError(...)
    claim = self._claims[claim_id]
    if claim.status != CLAIM_STATUS_DISPUTED:
        return False
    active = self.active_contradictions_by_freshness(claim_id)  # PR11-A query
    if not active:
        return False
    most_recent = self._evidences[active[0]]
    if most_recent.strength.value >= _REFUTATION_STRENGTH_THRESHOLD:
        old_status = claim.status
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_REFUTED)
        self._record_claim_lifecycle_transition(
            claim_id, old_status, CLAIM_STATUS_REFUTED,
            "refute_disputed_by_freshness_if_ready",  # Sub-decision S
        )
        return True
    return False
```

배치: `# ---- Freshness-aware refutation (PR11-B §27) ----` 섹션 신설,
PR11-A `# ---- Evidence freshness (PR11-A §25) ----` 직후 / `register_rule`
직전.

`types.py` / `__init__.py` / `rule_output.py` 변경 0.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| PR10-A `refute_disputed_claim_if_ready` 정책 변경 | Sub-decision (sibling 패턴 — 호환 유지) |
| Threshold 변경 / 새 threshold 도입 | Sub-decision R (재사용) |
| 모든 active 가중합 / max / rank weighting | Sub-decision Q (FIRST 만) |
| Older strong evidence 고려 | Sub-decision Q (FIRST 만) |
| PR11-C `compute_effective_confidence` 변경 | continuous vs binary 의미 분리 |
| Gap-based / count-based / RuleStats-based refute trigger | PR12+ |
| LLM / semantic 기반 refute | core 밖 |
| 자동 호출 (resolve / register / add_evidence side effect) | 명시 호출 원칙 |
| 새 status / 새 lifecycle 전이 | sibling refute 만 |
| Public `_REFUTATION_STRENGTH_THRESHOLD` | engine 내부 private 유지 |
| Public `TRANSITION_*` constants | PR10-B Sub-decision I 정합 |
| Wall-clock timestamp | PR10-A/B / PR11-A/C/D 일관 영구 OOS |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| D | **Gap-based modifier** — `effective × gap_modifier` (unresolved gap 페널티) | 높음 (PR11-C 의 modifier 분해 자리 활용) |
| E | **Contradiction count modifier** — active 개수 기반 추가 감쇠 | 중 |
| F | **RuleStats-based modifier** — `observed_precision` / `false_positive_rate` | 중 |
| G | **`superseded` / `retracted` 추가 상태** | 중 (도메인 요구 명확해진 뒤) |
| H | **Persistence / 직렬화** — engine state + lifecycle history 저장/복원 | 중 |
| I | **fire_rule audit** — PR10-B history 를 transition 외 영역으로 확장 | 중 |
| J | Engine bulk fire / `not` combinator / trace 직렬화 | 낮음 |
| K | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **D (Gap-based modifier)** 또는 **G (superseded/retracted)**.

D 는 PR11-C 의 modifier 분해 자리를 또 한 번 활용 — `effective = base × status
× freshness × gap`. unresolved gap 이 많은 claim 의 effective 가 낮아지는
자연스러운 의미.

G 는 도메인 요구 (예: claim 의 "취소" 같은 운영 신호) 가 명확해지면. PR8 의
disputed 와 다른 의미 — superseded 는 "더 새 정보로 대체", retracted 는
"명시적 취소".

## Architecture (after PR11-B)

```text
lifecycle map (사면 + audit + scoring 정교화 + refute path 분리):
  candidate
    ├─ confirmed  (PR6)  ─── disputed  (PR8)
    │      ↑                       ├─ confirmed       (PR9-A)
    │      └─── PR9-A ─────────────┤
    └─ refuted    (PR7)            ├─ refuted (ANY)   (PR10-A)
                                   └─ refuted (FIRST) (PR11-B) ★

PR10-B audit: 6 transition labels (PR11-B 가 1 추가)

PR11 그룹 (freshness):
  PR11-A: freshness noun (read-only query)
  PR11-C: freshness verb on effective (continuous attenuation)
  PR11-B: freshness verb on refute (binary trigger, sibling)

PR1~PR11 의 freshness 활용 완성.
```

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §27](../contracts/05_DATA_CONTRACT_MVP.md) — Freshness-aware disputed refutation (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §26](../contracts/05_DATA_CONTRACT_MVP.md) — Effective freshness modifier (PR11-C, 변경 안 됨)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §25](../contracts/05_DATA_CONTRACT_MVP.md) — Evidence freshness query (PR11-A, 변경 안 됨)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §22](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed refutation (PR10-A base)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §23](../contracts/05_DATA_CONTRACT_MVP.md) — Lifecycle history (PR10-B audit)
- [docs/dev/PR_010_DISPUTED_REFUTATION_MVP.md](PR_010_DISPUTED_REFUTATION_MVP.md)
- [docs/dev/PR_011_LIFECYCLE_HISTORY_MVP.md](PR_011_LIFECYCLE_HISTORY_MVP.md)
- [docs/dev/PR_013_EVIDENCE_FRESHNESS_MVP.md](PR_013_EVIDENCE_FRESHNESS_MVP.md)
- [docs/dev/PR_014_EFFECTIVE_FRESHNESS_MODIFIER_MVP.md](PR_014_EFFECTIVE_FRESHNESS_MODIFIER_MVP.md) — PR11-C base

## How to Run

```bash
git checkout feat/freshness-refute-mvp
pip install -e .
pytest -v
```

589 tests in ~0.40s. No new external dependencies.

## Result

PR11-B 가 PR10-A 의 sibling 으로 refute path 를 freshness 기반으로 분리.
PR11 그룹의 freshness 활용 완성:

```text
PR11-A: freshness noun (read-only query)
PR11-C: freshness verb on effective (continuous attenuation)
PR11-B: freshness verb on refute (binary trigger, sibling) ★
```

PR10-A 의 binary refute 정신과 PR11-C 의 continuous attenuation 정신 보존:
- PR10-A: ANY active >= 0.8 → REFUTED
- PR11-B: FIRST by freshness >= 0.8 → REFUTED (sibling)
- PR11-C: `most_recent.strength × 0.5` → effective × multiplier (continuous)

PR10-B 의 audit 이 6 transition path 를 명시화 — caller 가
`claim_lifecycle_history` 로 어느 path 로 refuted 됐는지 구분 가능.

PR11-B 의 본질:

> **PR10-A 를 대체한 PR 이 아니라, refute 판단 경로를 sibling 으로 분리한 PR.**
> PR9-A asc / PR11-A desc 가 같은 set 의 sibling view 였듯, PR11-B 는 PR10-A
> refute 의 sibling. 호환 100%.
