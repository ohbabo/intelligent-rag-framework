# PR #008 — Disputed Claim Lifecycle MVP

> Status: ready to merge (after Draft PR review).
> Branch: `feat/disputed-lifecycle-mvp` → `main`
> Base: `a23b4d6` (PR7 merged)
> Tests: 464 passing (local)

## 목적

PR7 까지의 흐름:

```text
candidate + contradiction → refute_claim_if_ready → refuted
confirmed + contradiction → register 가능, refute_if_ready 는 no-op (의도된 보호)
                            → 이 상태가 PR8 의 트리거
```

PR8 추가:

```text
confirmed + contradiction → dispute_claim_if_ready → disputed (refuted 아님)
```

즉 PR8 은 **confirmed Claim 에 contradiction 이 들어왔을 때 refuted 로 바로
떨어뜨리지 않고 disputed 로 격리** 하는 lifecycle 확장.

## PR8 의 한 줄 정의

> **PR8 은 "상태 추가" 가 아니라 "confirmed 이후 충돌을 refuted 로 오판하지
> 않게 격리한 lifecycle 확장" 이다.**

PR6/PR7 의 기본 판단 삼각형은 보존된다. PR8 은 그 위에 격리 레이어를 얹는다.

## 핵심 명제 (§20.2)

```text
A confirmed claim with explicit contradiction is not automatically refuted.
It becomes disputed.

Disputed means the claim was previously confirmed, but now has registered
contradiction evidence requiring re-evaluation.
```

한국어:

```text
confirmed Claim 에 contradiction 이 생겼다고 곧바로 refuted 가 되는 것은 아니다.
그 상태는 disputed 다.

disputed 는 과거에는 confirmed 였지만, 이후 반대 근거가 등록되어 재검토가
필요한 상태다.
```

## lifecycle 구조 — 삼각형 보존 + 격리 레이어

```text
기본 판단 삼각형 (PR6/PR7 보존):
  candidate
    ├─ confirmed   (PR6)
    └─ refuted     (PR7)

Post-confirmation conflict quarantine (PR8 추가):
  confirmed
    └─ disputed    (PR8)  ← confirmed + 명시 contradiction 등록
```

`disputed` 는 삼각형의 4번째 꼭짓점이 아니라 **confirmed 위에 얹는 격리 상태**.
`candidate → disputed`, `refuted → disputed` 같은 진입은 금지.

## 닫힌 흐름 (PR8 추가분)

```python
# 1) candidate → confirmed (PR6)
claim = engine.add_claim(subject_id=s, ...)  # status=CANDIDATE
engine.add_gap(claim_id=claim, ...)
ev = engine.add_evidence(claim_id=claim, ...)
engine.resolve_gaps_for_evidence(ev)
engine.confirm_claim_if_ready(claim)  # → True, status=CONFIRMED

# 2) 나중에 반박 evidence 등장 (cross-claim, PR7)
ev_contra = engine.add_evidence(claim_id=other_claim, ...)
engine.register_contradiction(claim, ev_contra)  # → True (status 무관 등록)

# 3) PR7 의 refute 는 status guard 에 막힘
engine.refute_claim_if_ready(claim)   # → False (confirmed 이므로 refute 안 함)
engine.get_claim(claim).status         # → CONFIRMED 유지

# 4) PR8 의 dispute 가 confirmed → disputed
engine.dispute_claim_if_ready(claim)  # → True (confirmed → disputed)
engine.get_claim(claim).status         # → CLAIM_STATUS_DISPUTED

# 5) Idempotent
engine.dispute_claim_if_ready(claim)  # → False (이미 disputed, no-op)
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `706329b` | docs(contract): define disputed claim lifecycle MVP (§20) |
| 2 | `e98600e` | test(core): lock disputed lifecycle invariants |
| 3 | `d2138f1` | feat(engine): add disputed claim lifecycle |
| 4 | (this) | docs(dev): PR8 record |

## 주요 설계 결정 (§20)

### 1. Level-1 결정 — disputed = lifecycle status (옵션 A)

```python
CLAIM_STATUS_DISPUTED = 3
```

대안 (옵션 B: flag/relation) 를 거부한 이유:

> **confirmed 상태는 소비자가 가장 믿기 쉬운 상태다.** confirmed 에 contradiction
> 이 붙어 있는데도 status 를 그대로 두면, 나중에 UI/리포트/조치 엔진이 "확정됨"
> 으로 오해할 수 있다. 켈베로스 기준에서는 이게 위험하다.

status 자체로 명확한 의미 분리:

```text
confirmed = 현재 근거상 확정
disputed  = 확정됐지만 이후 반대 근거가 들어와 재검토 필요
refuted   = candidate 단계에서 명시적 반대 근거로 반박됨
```

### 2. Sub-decision D — YAML 룰 output 에 노출 안 함

`disputed` 는 lifecycle 전이 결과 상태이지 **룰이 처음부터 만드는 초기 상태가
아니다**. 따라서 `ragcore/rule_output.py` 의 정적 매핑 / validation 에는
**추가하지 않는다**:

```python
# PR8 후에도 변경 없음
CLAIM_STATUS_MAP: dict[str, int] = {
    "candidate": CLAIM_STATUS_CANDIDATE,
    "confirmed": CLAIM_STATUS_CONFIRMED,
    "refuted":   CLAIM_STATUS_REFUTED,
}

_ALLOWED_CLAIM_STATUSES = frozenset({
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_REFUTED,
})
```

이유:

> A YAML rule MUST NOT create a disputed claim directly. Only
> `dispute_claim_if_ready` may transition a confirmed claim to disputed.

만약 YAML 룰이 다음과 같이 작성되면 컴파일 단계에서 거부됨:

```yaml
output:
  claim:
    status: disputed   # → 컴파일 거부 (CLAIM_STATUS_MAP 에 키 없음)
```

이게 `disputed` 의 lifecycle 의미를 코드 차원에서 보호한다. 39차의
`TestSubDecisionD` 가 이 보장을 잠그며, 40차에서도 변경 0.

### 3. PR6/PR7/PR8 API 미러 + status guard 차이

| API | 진입 status | 결과 status | Trigger |
|---|---|---|---|
| `confirm_claim_if_ready` | candidate | confirmed | 모든 gap resolved (충분 조건) |
| `refute_claim_if_ready` | candidate | refuted | ≥1 contradiction (존재 조건) |
| `dispute_claim_if_ready` | **confirmed** | **disputed** | ≥1 contradiction (존재 조건) |

**`refute_claim_if_ready` 와 `dispute_claim_if_ready` 는 같은 contradiction
데이터를 본다.** 차이는 status guard 만:
- `status == CANDIDATE` → refute 영역
- `status == CONFIRMED` → dispute 영역

status 는 한 시점에 한 값이므로 두 API 가 동시에 trigger 될 수 없다. 의미가
깔끔하게 분리.

### 4. `confirmed → refuted` 직접 전이 금지 — PR7 일관

PR7 §19 에서 `refute_claim_if_ready` 의 status guard 가 `CONFIRMED` 일 때 False
반환하도록 잠금. PR8 은 그 가드를 **약화하지 않는다**. 대신 `dispute_claim_if_ready`
가 별도 상태 (`disputed`) 로 격리.

이유:
- `confirmed → refuted` 직접 전이는 history / audit 의미 손실
- 과거에 confirmed 였다는 사실 자체가 정보. 단순 refuted 로 떨어뜨리면
  "처음부터 반박된 candidate" 와 구분 불가.
- `disputed` 는 "원래 confirmed 였다는 history 가 status 자체에 박힌 상태".

### 5. `disputed` 의 진입 한정

`disputed` 는 오직 `confirmed` 에서 진입. `candidate → disputed`, `refuted →
disputed` 는 모두 금지:

```python
if claim.status != CLAIM_STATUS_CONFIRMED:
    return False
```

이게 `disputed` 의 의미를 좁게 잠금 — "원래 confirmed 였던 것" 의 격리.

### 6. Idempotency + fail-fast (PR1~PR7 패턴 일관)

```python
engine.dispute_claim_if_ready(c)  # → True  (전이)
engine.dispute_claim_if_ready(c)  # → False (이미 disputed, no-op)
engine.dispute_claim_if_ready(999)  # → KeyError
```

### 7. `register_contradiction` 의 status 무관성 유지 (PR7 §19.6 일관)

```python
engine.register_contradiction(disputed_claim, ev)  # → True (정상 등록)
```

`disputed` 에도 추가 contradiction 등록 가능. 데이터 등록과 lifecycle 결정의
분리 원칙은 PR7 §19.6 에서 이미 잠겼고 PR8 도 그대로 유지.

### 8. dispute 전이가 다른 state 무변화

| | PR8 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` dataclass | 없음 |
| `add_claim` / `add_evidence` / `add_gap` 의미 | 없음 |
| `resolve_gaps_for_evidence` / `gap_resolution` 의미 | 없음 |
| `confirm_claim_if_ready` 의미 | 없음 (단 `disputed` 입력 시 status guard 가 False) |
| `refute_claim_if_ready` 의미 | 없음 (단 `disputed` 입력 시 status guard 가 False) |
| `register_contradiction` / `contradictions_for_claim` | 없음 |
| `_contradictions` 인덱스 | 없음 (PR8 이 transition 만 추가) |
| `base_confidence` / scoring | 없음 |
| `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 (Sub-decision D) |
| `fire_rule*` / `RuleStats` | 없음 |

## 불변식 (테스트로 잠금)

§20.10 의 14 개 invariant. 39차에 test-first 로 잠금, 40차 impl 후 13/14 전환.

1. confirmed + 0 contradiction → False
2. confirmed + 1+ contradiction → True, DISPUTED
3. candidate + 1+ contradiction → dispute False (PR7 refute 영역 보호)
4. refuted + 1+ contradiction → dispute False
5. 이미 disputed → False (idempotent)
6. unknown claim_id → KeyError
7. `confirm_claim_if_ready(disputed)` → False (PR6 status guard 자동 동작)
8. `refute_claim_if_ready(disputed)` → False (PR7 status guard 자동 동작)
9. `register_contradiction(disputed, ev)` → 정상 등록 (status 무관)
10. dispute 후 contradictions / gap state 보존
11. dispute 후 base_confidence 무변화
12. **`CLAIM_STATUS_MAP` 에 'disputed' 키 없음** (Sub-decision D) — 39차 이미 통과
13. `CLAIM_STATUS_DISPUTED` export (`ragcore` + `ragcore.types` 양쪽)
14. 기존 450 회귀 없음 (전체 통과로 입증)

## 테스트

**464 passing** in ~0.34s (450 → 464, delta 정확히 +14)

### Test-first 흐름

39차 (test-first 잠금):

```text
14 새 tests 추가
실행 결과 (의도된 분포):
- 11 fails: AttributeError 'Engine' has no attribute 'dispute_claim_if_ready'
-  2 fails: assert None == 3 (CLAIM_STATUS_DISPUTED 부재, getattr 패턴)
-  1 pass:  TestSubDecisionD (Sub-decision D 가 현재 코드 상태와 정합)
+ 기존 450 통과
```

**Collection-error 회피** (사용자 짚어준 패턴):
- `CLAIM_STATUS_DISPUTED` 를 module-level import 안 함
- dynamic `getattr` 로 접근 — collection time `ImportError` 회피
- `_EXPECTED_DISPUTED_VALUE = 3` (PR8 §20.4 spec value hardcode)

40차 (구현):

```text
- ragcore/types.py: CLAIM_STATUS_DISPUTED = 3
- ragcore/__init__.py: re-export
- ragcore/engine.py: dispute_claim_if_ready 메서드
실행 결과: 464 통과 (13 fail → 13 pass + 기존 1 pass 유지 + 기존 450)
```

### 변경 파일 (PR8 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §20 신설 (+227 lines) |
| `tests/test_engine_disputed_lifecycle.py` | 신규 (14 tests, +292 lines) |
| `ragcore/types.py` | `CLAIM_STATUS_DISPUTED = 3` (+1 line) |
| `ragcore/__init__.py` | re-export (+2 lines) |
| `ragcore/engine.py` | import + slot 1 + method 1 (+33 lines) |
| `docs/dev/PR_008_DISPUTED_LIFECYCLE_MVP.md` | 이 파일 (신규) |
| `ragcore/rule_output.py` | **변경 없음** (Sub-decision D 보장) |

### 테스트 분포

| 파일 | PR7 후 | PR8 (39차) | PR8 (40차) | 변동 |
|---|---|---|---|---|
| `test_engine_disputed_lifecycle.py` | 0 | 14 (13 fail + 1 pass) | **14 (pass)** | +14 |
| 나머지 12 파일 | 450 | 450 | **450** | 0 |
| **Total** | 450 | 450 + 1 pass + 13 fail | **464** | **+14** |

### 신규 테스트 그룹

**TestDisputeClaimIfReady (6):** inv 1~6 (전이 + no-op + KeyError)
**TestCrossAPIWithDisputed (3):** inv 7~9 (disputed × 다른 lifecycle API)
**TestDisputeIsolation (2):** inv 10~11 (contradiction/gap/base_confidence 보존)
**TestSubDecisionD (1):** inv 12 (D-NO — `CLAIM_STATUS_MAP` 무변경)
**TestDisputedConstantExport (2):** inv 13 (`ragcore` + `ragcore.types` 양쪽 export)

confirmed / refuted / disputed 상태 setup 은 white-box (`engine._claims[c] =
replace(..., status=...)`) — PR8 에 다른 경로 없음 (PR6/PR7 와 동일 기법).

## 구현 요약 (40차)

```python
# ragcore/types.py
CLAIM_STATUS_DISPUTED = 3  # PR8 §20: confirmed → disputed lifecycle quarantine

# ragcore/__init__.py — CLAIM_STATUS_DISPUTED re-export + __all__ 등록

# ragcore/engine.py — # ---- Disputed lifecycle (PR8 §20) ----
def dispute_claim_if_ready(self, claim_id) -> bool:
    if claim_id not in self._claims: raise KeyError(...)
    claim = self._claims[claim_id]
    if claim.status != CLAIM_STATUS_CONFIRMED: return False
    if not self._contradictions.get(claim_id): return False
    self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_DISPUTED)
    return True
```

배치: `# ---- Disputed lifecycle (PR8 §20) ----` 섹션 신설, PR7 의
`refute_claim_if_ready` 직후 / `register_rule` 직전.

`ragcore/rule_output.py` 는 **건드리지 않음** — Sub-decision D 보장.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| `disputed → confirmed` 복구 | history / audit / 정책 필요 — PR9+ |
| `disputed → refuted` 강제 전이 | 별도 결정점 |
| `disputed → resolved` / `archived` / `closed` | lifecycle 종결 정책 — 별도 PR |
| `candidate → disputed` / `refuted → disputed` 진입 | `disputed` 의미 보호 (오직 confirmed 출신) |
| `confirmed → refuted` 직접 전이 (PR7 와 일관 금지) | history 보호, PR9+ 결정점 |
| `superseded` / `retracted` 같은 추가 상태 | PR9+ |
| `confidence` 재계산 / scoring 변경 | 별도 PR |
| `disputed_at` timestamp / status transition history | 직렬화 PR |
| Auto-dispute (`register_contradiction` 안 side effect) | 명시성 원칙 (§17.7 정신) |
| YAML 룰 output 에 `disputed` 노출 (Sub-decision D) | §20.5 참조 |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| A | **`disputed → confirmed` / `disputed → refuted` 해소 정책** — 재검토 후 lifecycle 종결 | 높음 (PR8 자연 후속) |
| B | **Lifecycle trace / history** — confirm/refute/dispute 이벤트 기록 + audit | 높음 (PR8 의 history 의미 정착) |
| C | `superseded` / `retracted` 추가 상태 | 중 (도메인 요구 명확해진 뒤) |
| D | Effective confidence 재계산 (resolved gap / contradiction 반영) | 중 |
| E | Engine bulk fire (등록된 모든 룰 일괄 평가) | 중 |
| F | `not` combinator + nested field access | 중 |
| G | Trace 직렬화 / pretty-printer | 낮음 |
| H | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **A (disputed 해소 정책)** 또는 **B (lifecycle trace)**.

A 는 PR8 의 직접 자연 후속 — `disputed` 가 들어왔으니 나가는 길도 정의해야
실제 lifecycle 이 완결됨. B 는 PR8 이 강조한 history 의미 ("원래 confirmed
였다는 사실") 를 명시적 기록으로 정착시키는 PR. 어느 쪽도 PR8 의 결정 (history
보호, disputed = quarantine) 을 더 단단하게 한다.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §20](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed lifecycle contract (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §19](../contracts/05_DATA_CONTRACT_MVP.md) — Claim refutation (PR7 base)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §18](../contracts/05_DATA_CONTRACT_MVP.md) — Claim lifecycle / confirm (PR6 base)
- [docs/dev/PR_006_CLAIM_LIFECYCLE_MVP.md](PR_006_CLAIM_LIFECYCLE_MVP.md)
- [docs/dev/PR_007_CLAIM_REFUTATION_MVP.md](PR_007_CLAIM_REFUTATION_MVP.md) — PR7 base

## How to Run

```bash
git checkout feat/disputed-lifecycle-mvp
pip install -e .
pytest -v
```

464 tests in ~0.34s. No new external dependencies.

## Result

PR8 은 PR6/PR7 의 단순 확장이 아니라 **"confirmed 이후 충돌을 refuted 로
오판하지 않게 격리한 lifecycle 확장"** 으로 잠겼다.

엔진이 이제 명시적으로:

```text
"이 Claim 의 gap 이 다 채워졌는가?" → confirmed
"이 candidate Claim 에 반박 근거가 있는가?" → refuted
"이 confirmed Claim 에 반박 근거가 들어왔는가?" → disputed
```

세 lifecycle 질문에 분리해서 답할 수 있다. PR1~PR8 흐름으로 lifecycle 의 기본
삼각형 (`candidate → confirmed / refuted`) + post-confirmation conflict
quarantine (`confirmed → disputed`) 가 닫혔다.

```text
candidate
  ├─ confirmed  (PR6) ─── disputed  (PR8)
  └─ refuted    (PR7)
```

남은 lifecycle 결정점들 (`disputed` 해소 정책, history, scoring 재계산) 은
PR9+ 에서.
