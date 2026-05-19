# PR #009 — Disputed Resolution MVP (PR9-A)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/disputed-resolution-mvp` → `main`
> Base: `57c78d7` (PR8 merged)
> Tests: 482 passing (local)

## 목적

PR8 까지의 흐름:

```text
candidate + contradiction → refuted (PR7)
confirmed + contradiction → disputed (PR8, 격리)
disputed                  → 격리 상태, 나가는 길 없음 (PR9 후보)
```

PR9-A 추가:

```text
register_contradiction_resolution(c, ev)  → 명시 해소 등록 (relationship-bound)
active_contradictions_for_claim(c)        → 차집합으로 active 계산
resolve_disputed_claim_if_ready(c)        → active 0 이면 disputed → confirmed 복귀
```

즉 PR9-A 는 PR8 이 격리해둔 `disputed` 라는 재판정 대기 상태를 **어떤 판단
규칙으로 다시 닫을 것인가** 를 정한다.

## PR9-A 의 한 줄 정의

> **PR9-A 는 "상태를 더 늘리는 PR" 이 아니라, PR8 이 격리해둔 disputed 라는
> 재판정 대기 상태를 어떤 판단 규칙으로 다시 닫을 것인가를 정하는 PR 이다.**

PR8 이 confirmed 위에 격리 레이어 (`disputed`) 를 얹었다면, PR9-A 는 그 격리에
**나가는 길** 을 정의한다.

## 핵심 명제 (§21.2)

```text
Resolving a contradiction is relationship-bound.

A contradiction resolution is valid only when the evidence is already
registered as an explicit contradiction for the given claim. Existing IDs
are not sufficient. The pair itself must be a known contradiction relation.
```

한국어:

```text
contradiction 해소는 관계 기반이다.

evidence_id 와 claim_id 가 둘 다 존재한다는 것만으로 해소 등록이 정당해지지
않는다. (claim_id, evidence_id) 쌍 자체가 이미 등록된 contradiction 관계여야
한다.
```

이 명제가 **Sub-decision E** (`ValueError` on mismatched pair) 의 직접 근거.

## lifecycle 위치

```text
PR8 까지:
  candidate
    ├─ confirmed  (PR6) ─── disputed  (PR8)
    └─ refuted    (PR7)

PR9-A 추가:
  candidate
    ├─ confirmed  (PR6) ─── disputed  (PR8)
    │                          └─ confirmed  (PR9-A) ← 격리 해소
    └─ refuted    (PR7)
```

`disputed → confirmed` 는 lifecycle 의 **격리 해소** 경로. `disputed →
refuted` 는 evidence 우세도 / freshness 정책이 필요하므로 PR10+ 로 분리 (같은
API 의 확장으로 들어올 수 있는 자리 남겨둠).

## 닫힌 흐름 (PR9-A 추가분)

```python
# 1) candidate → confirmed → disputed (PR6/PR7/PR8)
claim = engine.add_claim(...)
engine.confirm_claim_if_ready(claim)       # → True, CONFIRMED
ev = engine.add_evidence(...)
engine.register_contradiction(claim, ev)    # → True
engine.dispute_claim_if_ready(claim)        # → True, DISPUTED

# 2) PR9-A — relationship-bound resolution
engine.register_contradiction_resolution(claim, ev)
# → True (새로 등록), pair 가 _contradictions[claim] 에 있음

engine.active_contradictions_for_claim(claim)
# → () (차집합: 전체 - resolved)

engine.contradictions_for_claim(claim)
# → (ev,) — 원본 보존 (audit)

# 3) PR9-A — disputed → confirmed 복귀
engine.resolve_disputed_claim_if_ready(claim)
# → True, status=CONFIRMED

# 4) Idempotent
engine.resolve_disputed_claim_if_ready(claim)  # → False (이미 confirmed)
engine.register_contradiction_resolution(claim, ev)  # → False (이미 resolved)
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `a405893` | docs(contract): define disputed resolution MVP (§21) |
| 2 | `d94378f` | test(core): lock disputed resolution invariants |
| 3 | `08c1691` | feat(engine): add disputed resolution |
| 4 | (this) | docs(dev): PR9 record |

## 주요 설계 결정 (§21)

### 1. Relationship-bound resolution (§21.2 — Sub-decision E)

```python
if evidence_id not in self._contradictions.get(claim_id, set()):
    raise ValueError(...)
```

3 단계 검증의 의미:

| 검증 | Error type | 의미 |
|---|---|---|
| `claim_id in self._claims` | `KeyError` | id 자체가 존재 안 함 |
| `evidence_id in self._evidences` | `KeyError` | id 자체가 존재 안 함 |
| `pair in _contradictions[claim_id]` | **`ValueError`** | id 들은 존재하지만 관계 위반 |

PR1~PR8 의 fail-fast 패턴과 정확히 정합. `KeyError` vs `ValueError` 의 의미
분리가 §21.2 명제의 코드 차원 표현.

### 2. 두 인덱스 분리 — audit 보존 + 차집합 의미

```python
self._contradictions: dict[int, set[int]]            # PR7 (보존, 변경 안 함)
self._resolved_contradictions: dict[int, set[int]]   # PR9-A 신규
```

- `_contradictions` 는 **등록된 사실** (audit trail, 변경 없음)
- `_resolved_contradictions` 는 **해소된 사실** (추가만, 되돌리기 없음)
- `active = contradictions - resolved` (차집합)

`_contradictions` entry 의 **삭제는 금지**. PR8 의 history 의미와 정합 —
"원래 contradiction 이었다는 사실" 도 정보.

### 3. PR6/PR7/PR8/PR9-A lifecycle API 패턴 완성

| API | 진입 status | 결과 status | Trigger |
|---|---|---|---|
| `confirm_claim_if_ready` | candidate | confirmed | 모든 gap resolved |
| `refute_claim_if_ready` | candidate | refuted | ≥1 contradiction |
| `dispute_claim_if_ready` | confirmed | disputed | ≥1 contradiction |
| **`resolve_disputed_claim_if_ready`** | **disputed** | **confirmed** | **모든 contradiction resolved** |

PR9-A 가 **PR6 의 정확한 미러**:

```text
PR6: 모든 gap resolved → candidate → confirmed
PR9: 모든 contradiction resolved → disputed → confirmed
```

"모든 X 해소 → confirmed" 패턴이 lifecycle 의 두 위치에 박힘.

### 4. API 이름 — `resolve_*` 의 미래 확장 자리

```python
resolve_disputed_claim_if_ready(claim_id) -> bool
```

이름이 `resolve_*` 인 이유: PR10+ 에서 `disputed → refuted` 같은 확장이
들어올 수 있는 자리. 그 시점에는 시그니처가 확장되거나 sibling API 가 추가될
수 있음. PR9-A 는 `disputed → confirmed` 만 다룬다.

### 5. First-keep + idempotent — PR4/PR5/PR6/PR7/PR8 일관

```python
register_contradiction_resolution(c, e)  # → True  (첫 등록)
register_contradiction_resolution(c, e)  # → False (이미 resolved)

resolve_disputed_claim_if_ready(c)       # → True  (전이)
resolve_disputed_claim_if_ready(c)       # → False (이미 confirmed)
```

Resolved → unresolved 되돌리기는 PR9-A 범위 밖 (PR5 first-keep 정신 일관).

### 6. Target status 무관 — 데이터 등록과 결정 분리 (PR7 §19.6 일관)

`register_contradiction_resolution` 은 target claim 의 status 와 무관. PR7
의 `register_contradiction` 와 동일 정신:
- **데이터 등록 = "이 evidence 가 더 이상 active contradiction 이 아니라는 사실"** — status 무관 객관 사실
- **lifecycle 결정 = "이 사실로 status 를 바꿀까"** — `resolve_disputed_claim_if_ready` 의 status guard 가 결정

### 7. PR8 의미 보존 — dispute 는 active 차집합 안 봄

PR9-A 는 PR8 의 `dispute_claim_if_ready` 의미를 **건드리지 않는다**:

```python
# PR8 그대로 보존
def dispute_claim_if_ready(self, claim_id):
    if not self._contradictions.get(claim_id):  # _contradictions 전체 본다
        return False
```

`dispute_claim_if_ready` 는 PR7 `_contradictions` 전체를 보지 active 차집합을
보지 않는다. 따라서 `ev1` 이 resolved 됐어도 `ev2` 가 contradictions 에 있으면
dispute 가능. 이게 PR8 의 의미와 정합.

PR10+ 에서 이 의미를 약화시킬지 (active 기준으로 dispute) 는 별도 결정점.

### 8. `active_contradictions_for_claim` 의 status 무관 호출

PR7 `contradictions_for_claim` 패턴 일관 — query 메서드는 status 무관 (모든
status 에서 호출 가능). `KeyError` 는 unknown claim_id 만.

## 불변식 (테스트로 잠금)

§21.11 의 14 개 invariant + Sub-decision E:

1. register unknown claim_id → `KeyError`
2. register unknown evidence_id → `KeyError`
3. **pair 가 contradiction 미등록 → `ValueError`** (Sub-decision E ★)
4. 첫 register_contradiction_resolution → `True`
5. 같은 pair 두 번째 → `False` (idempotent)
6. resolved 후에도 `contradictions_for_claim` 에 포함 (audit)
7. `active_contradictions_for_claim` 은 resolved 제외 (차집합)
8. resolved/active 둘 다 evidence_id asc tuple
9. disputed + active 1+ → resolve `False`, disputed 유지
10. **disputed + active 0 → `True`, status=CONFIRMED ★**
11. candidate / confirmed / refuted 는 resolve_disputed 통해 변경 X
12. resolve unknown claim_id → `KeyError`
13. resolve 전이가 gap state / base_confidence / contradiction list 무변화
14. PR8 dispute_claim_if_ready 는 _contradictions 전체 본다 (PR9-A 무영향)
15. 기존 464 회귀 없음 (전체 통과로 입증)

## 테스트

**482 passing** in ~0.38s (464 → 482, delta 정확히 +18)

### Test-first 흐름

43차 (test-first 잠금):

```text
18 새 tests 추가
실행 결과: 18 fail, 모두 의도된 AttributeError
  - register_contradiction_resolution missing × 11
  - resolve_disputed_claim_if_ready missing × 5
  - resolved_contradictions_for_claim missing × 1
  - active_contradictions_for_claim missing × 1
+ 기존 464 통과
```

44차 (구현):

```text
- Engine._resolved_contradictions 슬롯
- 4 신규 메서드 (# ---- Disputed resolution (PR9-A §21) ---- 섹션)
- rule_output.py / types.py / __init__.py 변경 0
실행 결과: 482 통과 (18 fail → 18 pass)
```

### 변경 파일 (PR9-A 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §21 신설 (+277 lines) |
| `tests/test_engine_disputed_resolution.py` | 신규 (18 tests, +342 lines) |
| `ragcore/engine.py` | slot + 4 methods (+97 lines) |
| `docs/dev/PR_009_DISPUTED_RESOLUTION_MVP.md` | 이 파일 (신규) |
| `ragcore/types.py` | **변경 없음** (새 상수 없음) |
| `ragcore/__init__.py` | **변경 없음** (새 export 없음) |
| `ragcore/rule_output.py` | **변경 없음** (Sub-decision D 정합) |

### 테스트 분포

| 파일 | PR8 후 | PR9 (43차) | PR9 (44차) | 변동 |
|---|---|---|---|---|
| `test_engine_disputed_resolution.py` | 0 | 18 (fail) | **18 (pass)** | +18 |
| 나머지 13 파일 | 464 | 464 | **464** | 0 |
| **Total** | 464 | 464 + 18 fail | **482** | **+18** |

### 신규 테스트 그룹

**TestRegisterContradictionResolution (5):** inv 1~5 (KeyError × 2 + ValueError ★ + first True + idempotent False)
**TestResolvedAndActiveContradictions (5):** KeyError × 2 + audit 보존 + 차집합 + asc
**TestResolveDisputedClaimIfReady (6):** transition + status guard 3종 + KeyError
**TestResolveIsolation (2):** gap state / base_confidence / contradiction list 무변화 + PR8 dispute 정합

confirmed / refuted 상태 setup 은 PR6~PR8 와 동일 white-box (`engine._claims[c] = replace(..., status=...)`). disputed 는 dispute_claim_if_ready 통해.

## 구현 요약 (44차)

```python
# Engine.__init__
self._resolved_contradictions: dict[int, set[int]] = {}

# ---- Disputed resolution (PR9-A §21) ----

def register_contradiction_resolution(self, claim_id, evidence_id) -> bool:
    if claim_id not in self._claims: raise KeyError(...)
    if evidence_id not in self._evidences: raise KeyError(...)
    contras = self._contradictions.get(claim_id, set())
    if evidence_id not in contras:
        raise ValueError(...)  # ★ Sub-decision E
    resolved = self._resolved_contradictions.setdefault(claim_id, set())
    if evidence_id in resolved: return False
    resolved.add(evidence_id); return True

def resolved_contradictions_for_claim(self, claim_id) -> tuple[int, ...]:
    if claim_id not in self._claims: raise KeyError(...)
    return tuple(sorted(self._resolved_contradictions.get(claim_id, set())))

def active_contradictions_for_claim(self, claim_id) -> tuple[int, ...]:
    if claim_id not in self._claims: raise KeyError(...)
    contras = self._contradictions.get(claim_id, set())
    resolved = self._resolved_contradictions.get(claim_id, set())
    return tuple(sorted(contras - resolved))

def resolve_disputed_claim_if_ready(self, claim_id) -> bool:
    if claim_id not in self._claims: raise KeyError(...)
    claim = self._claims[claim_id]
    if claim.status != CLAIM_STATUS_DISPUTED: return False
    if self.active_contradictions_for_claim(claim_id): return False
    self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_CONFIRMED)
    return True
```

배치: `# ---- Disputed resolution (PR9-A §21) ----` 섹션 신설, PR8 `dispute_claim_if_ready` 직후 / `register_rule` 직전.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| `disputed → refuted` 전이 | evidence 우세도 / freshness 정책 필요 — PR10+ (같은 API 확장 가능) |
| Resolved → unresolved 되돌리기 | PR5 first-keep 일관 — 별도 결정점 |
| Evidence 우세도 자동 판정 (priority / strength weighted) | scoring 변경 별도 PR |
| `disputed → confirmed` 자동 trigger (resolved 등록 시 side effect) | 명시성 원칙 (§17.7 / §20.11 정신) |
| Lifecycle trace / history (resolve 이벤트 기록) | PR9-B 또는 직렬화 PR |
| `disputed_resolved_at` timestamp | 직렬화 PR |
| `confirmed → refuted` / `confirmed → candidate` 강등 | 별도 결정점 |
| `_contradictions` entry 의 삭제 (resolved 시 제거) | audit 의미 보존 — **금지** |
| `superseded` / `retracted` 같은 추가 상태 | PR10+ |
| `register_contradiction_resolution` 의 status guard (disputed 만 허용?) | 데이터 등록 / lifecycle 결정 분리 (PR7 §19.6 일관) |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| A | **`disputed → refuted` 전이** — evidence 우세도 정책 + same API 확장 | 높음 (PR9-A 자연 후속, lifecycle 종결의 다른 방향) |
| B | **Lifecycle trace / history** — confirm/refute/dispute/resolve 이벤트 기록 + audit | 높음 (PR8/PR9 audit 의미 정착) |
| C | Effective confidence 재계산 (resolved gap / contradiction 반영) | 중 |
| D | `superseded` / `retracted` 추가 상태 | 중 (도메인 요구 명확해진 뒤) |
| E | Engine bulk fire (등록된 모든 룰 일괄 평가) | 중 |
| F | `not` combinator + nested field access | 중 |
| G | Trace 직렬화 / pretty-printer | 낮음 |
| H | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **A (disputed → refuted)** 또는 **B (lifecycle trace)**.

A 는 PR9-A 가 남겨둔 자리를 채우는 자연 후속 — `resolve_*` API 의 확장으로
들어가거나, evidence 우세도 정책이 결정되면 그 위에 새 API 가 붙는다. B 는
PR6~PR9 의 lifecycle 전이들을 통합적으로 추적 가능하게 하는 audit 레이어 —
운영 / 디버깅 / 시간 분석에 직접 활용.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §21](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed resolution contract (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §20](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed lifecycle (PR8 base)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §19](../contracts/05_DATA_CONTRACT_MVP.md) — Claim refutation (PR7 base)
- [docs/dev/PR_006_CLAIM_LIFECYCLE_MVP.md](PR_006_CLAIM_LIFECYCLE_MVP.md)
- [docs/dev/PR_007_CLAIM_REFUTATION_MVP.md](PR_007_CLAIM_REFUTATION_MVP.md)
- [docs/dev/PR_008_DISPUTED_LIFECYCLE_MVP.md](PR_008_DISPUTED_LIFECYCLE_MVP.md) — PR8 base

## How to Run

```bash
git checkout feat/disputed-resolution-mvp
pip install -e .
pytest -v
```

482 tests in ~0.38s. No new external dependencies.

## Result

PR9-A 가 PR8 의 자연 후속으로 닫혔다. 엔진이 이제 명시적으로:

```text
"이 disputed Claim 의 contradiction 들이 다 해소됐는가?" → confirmed 복귀
"아직 active contradiction 이 남아 있는가?" → disputed 유지
```

라는 두 질문에 분리해서 답할 수 있다. PR1~PR9 흐름으로 lifecycle 의 4 전이가
완성:

```text
candidate
  ├─ confirmed  (PR6)  ─── disputed  (PR8)
  │      ↑                       │
  │      └────── PR9-A ──────────┘
  └─ refuted    (PR7)
```

남은 lifecycle 결정점 (`disputed → refuted`, lifecycle history, scoring
재계산, superseded/retracted) 은 PR10+ 에서.
