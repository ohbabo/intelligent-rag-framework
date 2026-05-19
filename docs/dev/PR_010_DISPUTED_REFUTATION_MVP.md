# PR #010 — Disputed Refutation MVP (PR10-A)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/disputed-refutation-mvp` → `main`
> Base: `4501371` (PR9-A merged)
> Tests: 500 passing (local)

## 목적

PR9-A 까지의 흐름:

```text
disputed + active 1+ → resolve_disputed_claim_if_ready False (active 잔존)
disputed + active 0  → resolve_disputed_claim_if_ready True (confirmed 복귀)
```

PR10-A 추가:

```text
disputed + active 중 단 하나라도 strength >= 0.8
  → refute_disputed_claim_if_ready True (REFUTED 전이)
disputed + active 1+ + 모두 strength < 0.8
  → refute_disputed_claim_if_ready False (disputed 유지)
```

즉 PR10-A 는 PR8/PR9-A 가 격리해둔 `disputed` 의 **부정 종결 경로**를 정의한다.
PR9-A 가 disputed 의 긍정 종결 (`disputed → confirmed`) 을 잠갔다면, PR10-A
는 부정 종결 (`disputed → refuted`) 을 잠근다. **lifecycle 사면 완성.**

## PR10-A 의 한 줄 정의

> **PR10-A 는 PR8/PR9-A 가 격리해둔 disputed 의 부정 종결 경로를 정의한다.
> 단, "우세도" 를 똑똑하게 만들지 않고 evidence strength 단일 축으로만 시작한다.**

복잡한 정책 (freshness / RuleStats / 가중합) 은 PR10-A 의 가장 큰 위험. PR11+
로 분리.

## 핵심 명제 (§22.2 — Sub-decision F)

```text
Refutation of a disputed claim is contradiction-strength-driven only.

PR10-A does not consult freshness, rule maturity, evidence count, or weighted
aggregation. A disputed claim becomes refuted when any single active
contradiction evidence has strength >= REFUTATION_STRENGTH_THRESHOLD.
```

한국어:

```text
disputed Claim 의 refute 판정은 contradiction strength 단일 축으로만 한다.
active contradiction 중 단 하나라도 strength >= threshold 면 refuted 로 전이.
```

## 닫힌 흐름 (PR10-A 추가분)

```python
# 1) candidate → confirmed → disputed (PR6/PR7/PR8)
claim = engine.add_claim(...)
engine.confirm_claim_if_ready(claim)             # → True, CONFIRMED
ev = engine.add_evidence(..., strength=0.9)
engine.register_contradiction(claim, ev)          # → True
engine.dispute_claim_if_ready(claim)              # → True, DISPUTED

# 2) PR9-A 의 resolve 시도 — active 1+ 면 False (격리 유지)
engine.resolve_disputed_claim_if_ready(claim)    # → False (active 잔존)

# 3) PR10-A 의 refute — active 중 strong evidence 가 있으면 refuted
engine.refute_disputed_claim_if_ready(claim)     # → True, REFUTED

# 4) Idempotent
engine.refute_disputed_claim_if_ready(claim)     # → False (이미 refuted)
```

대안 경로 (resolved evidence 무시 시나리오):

```python
# resolved 만 강함 (0.95) — active 없음
strong_ev = engine.add_evidence(..., strength=0.95)
engine.register_contradiction(c, strong_ev)
# ... dispute → disputed
engine.register_contradiction_resolution(c, strong_ev)  # active = 0

engine.refute_disputed_claim_if_ready(c)
# → False (active 없음, resolved 의 strength 0.95 는 무관)
# resolve 호출하면 confirmed 복귀 (PR9-A)
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `5e1b6c3` | docs(contract): define disputed refutation MVP (§22) |
| 2 | `00faea0` | test(core): lock disputed refutation invariants |
| 3 | `d18cb47` | feat(engine): add disputed refutation |
| 4 | (this) | docs(dev): PR10 record |

## 주요 설계 결정 (§22)

### 1. Sub-decision F — Strength-only (§22.2)

```python
for evidence_id in self.active_contradictions_for_claim(claim_id):
    evidence = self._evidences[evidence_id]
    if evidence.strength.value >= _REFUTATION_STRENGTH_THRESHOLD:
        # refute
```

PR10-A 가 보지 않는 것 (의도):
- Freshness / timestamp
- Rule maturity / RuleStats
- Evidence 개수 (count)
- 가중합 / average / aggregation
- `base_confidence` / scoring

이 단순성이 PR10-A 의 안전망. "우세도" 를 똑똑하게 만들려는 시도가 가장 큰
위험이며, 복잡한 정책은 PR11+ 로.

### 2. Sub-decision G — Private threshold (§22.5)

```python
# Engine module level, private
_REFUTATION_STRENGTH_THRESHOLD = 0.8
```

| | 선택 |
|---|---|
| Public constant export | ✗ |
| Config 주입 | ✗ |
| Hardcode private | ✓ |
| `ScoreValue.__ge__` 추가 | ✗ |

이유:
- **미래 정책 변경 자유 확보** — freshness / RuleStats / aggregation 이 도입되면
  threshold 정책 자체가 바뀔 수 있음. public 으로 노출하면 외부 의존이 생김.
- **PR1 `ScoreValue` 시그니처 변경 회피** — `__ge__` 추가는 type 시스템 변경,
  scope 확대. `.value` 접근이 PR10-A 단순성에 정합.

threshold 값 0.8 의 근거: "거의 확실한 반박" 의 보수적 기준.

### 3. PR9-A 차집합 의미 정합

```python
# contradictions_for_claim() 직접 사용 안 함
for evidence_id in self.active_contradictions_for_claim(claim_id):
    ...
```

`active_contradictions_for_claim` 만 사용. `contradictions_for_claim` 직접 보면
resolved evidence 의 strength 가 0.95 일 때 false positive 발생 — PR9-A 의
"해소" 의미가 무너진다.

### 4. PR7 / PR10-A — 같은 status, 다른 path

| 출처 | 진입 status | trigger | API |
|---|---|---|---|
| **PR7** | `candidate` | contradiction 등록 (개수만, strength 무관) | `refute_claim_if_ready` |
| **PR10-A** | `disputed` | active 중 strength >= 0.8 | `refute_disputed_claim_if_ready` |

둘 다 결과 `status = CLAIM_STATUS_REFUTED` (2). 같은 상수.

PR10-A 가 PR7 의 의미를 **건드리지 않는다**:
- PR7 의 `refute_claim_if_ready` 는 `CANDIDATE` 만, strength 무관 (개수만).
- PR10-A 의 threshold 정책이 PR7 영역 침범하지 않음 (status guard 분리).

path 의 구분 (candidate origin vs disputed origin) 은 status 만으로는 알 수
없음. lifecycle history (PR10-B+) 의 영역.

### 5. PR9-A 와 PR10-A — Mutually exclusive triggers

```text
resolve trigger: len(active) == 0   (모든 contradiction 해소)
refute  trigger: any(strength >= 0.8 in active)
```

두 trigger 가 동시 만족할 수 없다 (active 0 이면 refute 가드 부족, active 1+
이면 resolve 가 active 잔존 가드로 False). 호출 순서에 의존하지 않음.

### 6. Sibling API — 같은 sigil 가 아니라 분리된 메서드

```python
resolve_disputed_claim_if_ready  # PR9-A: disputed → confirmed
refute_disputed_claim_if_ready   # PR10-A: disputed → refuted (별도 sibling)
```

이유:
- 두 API 의 의미가 비대칭 (조건 / 결과 / 정책)
- 한 API 에 합치면 매개변수로 "방향" 을 받게 되어 호출자 복잡도 증가
- sibling API 가 PR6/PR7/PR8 패턴 일관 (each lifecycle transition has its own API)

### 7. Idempotency + fail-fast

```python
engine.refute_disputed_claim_if_ready(c)  # → True  (전이)
engine.refute_disputed_claim_if_ready(c)  # → False (이미 refuted, no-op)
engine.refute_disputed_claim_if_ready(999)  # → KeyError
```

PR4/PR5/PR6/PR7/PR8/PR9-A 패턴 일관.

### 8. Threshold boundary — `>=` 비교

```python
if evidence.strength.value >= _REFUTATION_STRENGTH_THRESHOLD:
```

- `0.8` 정확 → refute (`>=`)
- `0.799999` → refute 안 함 (`<`)

invariant 테스트로 boundary 명시 잠금 (§22.11 inv 6, 7).

## 불변식 (테스트로 잠금)

§22.11 의 14 invariant:

1. unknown claim_id → `KeyError`
2. status guard 3 (candidate / confirmed / refuted)
3. disputed + active 0 → `False`
4. disputed + 모두 strength < 0.8 → `False`
5. **disputed + 단 하나 strength >= 0.8 → `True`, REFUTED ★**
6. **Threshold 경계 0.8 정확 → refute** (`>=`)
7. Threshold 직하 0.799999 → refute 안 함
8. **Resolved strength 0.95 라도 refute 안 함** (active 만 본다) ★
9. refuted 재호출 idempotent
10. Transition isolation (gap state / contradictions / base_confidence 무변화)
11. PR9-A resolve 와 mutually exclusive
12. PR7 `refute_claim_if_ready` 의미 무변화
13. `_REFUTATION_STRENGTH_THRESHOLD` private (public export 안 됨)
14. 기존 482 회귀 없음

## 테스트

**500 passing** in ~0.34s (482 → 500, delta 정확히 +18)

### Test-first 흐름 + 의도된 pass

47차 (test-first 잠금):

```text
18 새 tests 추가
실행 결과 (의도된 분포):
- 15 fails: AttributeError 'Engine' has no attribute 'refute_disputed_claim_if_ready'
-  3 pass:
    * test_pr7_refute_claim_if_ready_unaffected_by_threshold
        (PR7 API 가 PR10 threshold 영향 받지 않음)
    * test_threshold_not_in_ragcore_public_export
        (Sub-decision G — current code state 정합)
    * test_threshold_not_in_types_module
        (same Sub-decision G boundary)
+ 기존 482 통과
```

PR8 39차의 `TestSubDecisionD` 가 D-NO 정합으로 이미 통과한 패턴과 동일 —
일부 invariant 는 변경 전에도 코드 구조에 박혀 있음. **방어 두께의 신호.**

48차 (구현):

```text
- _REFUTATION_STRENGTH_THRESHOLD = 0.8 (private)
- # ---- Disputed refutation (PR10-A §22) ---- 섹션
- refute_disputed_claim_if_ready 메서드
실행 결과: 500 통과 (15 fail → 15 pass, 47차의 3 pass 유지)
```

수치 정리 — 전체 테스트 수 기준:
- 482 (PR9-A) + 18 (PR10 신규) = 500
- "+15" 는 47차의 fail 만 더한 부분 계산. "+18" 이 전체 테스트 수 변화.

### 변경 파일 (PR10-A 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §22 신설 (+253 lines) |
| `tests/test_engine_disputed_refutation.py` | 신규 (18 tests, +359 lines) |
| `ragcore/engine.py` | private threshold + 1 method (+46 lines) |
| `docs/dev/PR_010_DISPUTED_REFUTATION_MVP.md` | 이 파일 (신규) |
| `ragcore/types.py` | **변경 없음** (Sub-decision G + ScoreValue 무변경) |
| `ragcore/__init__.py` | **변경 없음** (Sub-decision G — threshold private) |
| `ragcore/rule_output.py` | **변경 없음** (Sub-decision D 정합 — 새 status 없음) |

### 테스트 분포

| 파일 | PR9-A 후 | PR10 (47차) | PR10 (48차) | 변동 |
|---|---|---|---|---|
| `test_engine_disputed_refutation.py` | 0 | 18 (15 fail + 3 pass) | **18 (pass)** | +18 |
| 나머지 14 파일 | 482 | 482 | **482** | 0 |
| **Total** | 482 | 482 + 3 pass + 15 fail | **500** | **+18** |

### 신규 테스트 그룹

**TestRefuteDisputedClaimIfReady (8):** inv 1, 2, 3, 4, 5, 9 (KeyError + status guard 3 + transition 3 + idempotent)
**TestRefutationStrengthThreshold (2):** inv 6, 7 (boundary 정확 / 직하)
**TestResolvedContradictionsIgnored (3):** inv 8 + 보강 (active vs resolved 의 strength 시나리오 3)
**TestCrossAPIConsistency (2):** inv 11, 12 (PR9-A 배타 + PR7 무변화)
**TestRefutationIsolation (1):** inv 10 (gap state / contradictions / base_confidence 무변화)
**TestThresholdPrivacy (2):** inv 13 (ragcore + ragcore.types 양쪽 미노출)

## 구현 요약 (48차)

```python
# ragcore/engine.py (module level)
_REFUTATION_STRENGTH_THRESHOLD = 0.8  # Sub-decision G — private

# # ---- Disputed refutation (PR10-A §22) ----
def refute_disputed_claim_if_ready(self, claim_id) -> bool:
    if claim_id not in self._claims:
        raise KeyError(...)
    claim = self._claims[claim_id]
    if claim.status != CLAIM_STATUS_DISPUTED:
        return False
    for evidence_id in self.active_contradictions_for_claim(claim_id):
        evidence = self._evidences[evidence_id]
        if evidence.strength.value >= _REFUTATION_STRENGTH_THRESHOLD:
            self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_REFUTED)
            return True
    return False
```

배치: `# ---- Disputed refutation (PR10-A §22) ----` 섹션 신설, PR9-A
`resolve_disputed_claim_if_ready` 직후 / `register_rule` 직전.

`contradictions_for_claim()` 직접 사용 안 함 — PR9-A 차집합 의미 정합.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| Freshness / timestamp 기반 우세도 | timestamp 정의 필요 — PR11+ |
| RuleStats 기반 우세도 | rule maturity 의 lifecycle 의미 결정 — PR11+ |
| 다중 evidence 가중합 / average / max-of-N | "우세도" 종합 정책 결정 — PR11+ |
| Threshold 의 public export / config 주입 | 미래 정책 자유 확보 |
| `disputed → candidate` 강등 | 별도 결정점 |
| `refuted → 어떤 상태` 복구 | 별도 결정점 |
| LLM / 의미 추론으로 우세도 판정 | core 밖 |
| `confidence` (`base_confidence` / `effective`) 재계산 | scoring 변경 별도 PR |
| Lifecycle history / `refuted_at` timestamp | PR10-B 또는 직렬화 PR |
| Auto-refute (resolve / register side effect) | 명시성 원칙 (§17.7 정신) |
| `superseded` / `retracted` 추가 상태 | PR11+ |
| `ScoreValue` 비교 메서드 (`__ge__` 등) 추가 | PR1 시그니처 변경 회피 |
| PR7 candidate-origin refuted 와 PR10 disputed-origin refuted 의 구분 | lifecycle history 영역 (PR10-B+) |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| A | **PR10-B Lifecycle trace / history** — confirm/refute/dispute/resolve/refute_disputed 이벤트 기록 + audit | 높음 (PR9-A & PR10-A 둘 다 PR10-B 추천 — lifecycle 양 종결 경로 닫혔으니 audit 가 의미 있다) |
| B | **Strength-weighted / freshness 우세도** — PR10-A 의 단순 threshold 를 정교한 정책으로 확장 | 중 (`disputed → refuted` 의 trigger 가 더 정교해질 필요 있으면) |
| C | **Effective confidence 재계산** — resolved gap / active contradiction / status 를 scoring 에 반영 | 중 |
| D | `superseded` / `retracted` 추가 상태 | 중 (도메인 요구 명확해진 뒤) |
| E | Engine bulk fire (등록된 모든 룰 일괄 평가) | 중 |
| F | `not` combinator + nested field access | 중 |
| G | Trace 직렬화 / pretty-printer | 낮음 |
| H | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **A (Lifecycle trace / history)**.

이유:
- PR6~PR10-A 가 lifecycle 의 모든 전이를 잠갔지만, "어떤 path 로 어떤 상태에
  도달했는가" 의 기록은 없음.
- PR7 candidate-origin refuted 와 PR10-A disputed-origin refuted 의 구분이
  status 만으로는 불가능 — PR10-B 가 그 구분을 명시화.
- PR8 의 audit 의미 ("원래 confirmed 였다는 사실") 와 PR9-A 의 audit trail
  (`_contradictions` 보존) 을 lifecycle history 로 통합.
- PR3 firing trace 와 자연스럽게 연결 — 운영 / 디버깅 / 시간 분석 기반.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §22](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed refutation contract (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §21](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed resolution (PR9-A base)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §20](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed lifecycle (PR8 base)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §19](../contracts/05_DATA_CONTRACT_MVP.md) — Claim refutation (PR7 base, candidate origin)
- [docs/dev/PR_006_CLAIM_LIFECYCLE_MVP.md](PR_006_CLAIM_LIFECYCLE_MVP.md)
- [docs/dev/PR_007_CLAIM_REFUTATION_MVP.md](PR_007_CLAIM_REFUTATION_MVP.md)
- [docs/dev/PR_008_DISPUTED_LIFECYCLE_MVP.md](PR_008_DISPUTED_LIFECYCLE_MVP.md)
- [docs/dev/PR_009_DISPUTED_RESOLUTION_MVP.md](PR_009_DISPUTED_RESOLUTION_MVP.md) — PR9-A base

## How to Run

```bash
git checkout feat/disputed-refutation-mvp
pip install -e .
pytest -v
```

500 tests in ~0.34s. No new external dependencies.

## Result

PR10-A 가 PR8/PR9-A 의 자연 후속으로 닫혔다. **lifecycle 사면 완성**:

```text
candidate
  ├─ confirmed  (PR6) ─── disputed  (PR8)
  │      ↑                       ├─ confirmed  (PR9-A)
  │      └────── PR9-A ──────────┤
  └─ refuted    (PR7)            └─ refuted    (PR10-A) ★
```

엔진이 이제 명시적으로 5 lifecycle 전이를 분리해서 답할 수 있다:

```text
PR6: 모든 gap resolved → candidate → confirmed
PR7: contradiction 1+ → candidate → refuted
PR8: contradiction 1+ → confirmed → disputed (격리)
PR9-A: 모든 contradiction 해소 → disputed → confirmed (긍정 종결)
PR10-A: active strength >= 0.8 → disputed → refuted (부정 종결)
```

남은 lifecycle 결정점 (lifecycle history, freshness-based 우세도, scoring
재계산, superseded/retracted) 은 PR10-B+ 에서.
