# PR #011 — Lifecycle History MVP (PR10-B)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/lifecycle-history-mvp` → `main`
> Base: `5b587f2` (PR10-A merged)
> Tests: 517 passing (local)

## 목적

PR10-A 까지의 흐름:

```text
5 lifecycle API 가 status 변경
  → caller 는 현재 status 만 볼 수 있음
  → "어떻게 도달했는가" 의 기록은 없음
```

PR10-B 추가:

```text
5 lifecycle API 가 True 반환 시 → ClaimLifecycleEvent 자동 append
caller 는 claim_lifecycle_history(c) 로 모든 transition 조회 가능
event = (seq, claim_id, from_status, to_status, transition)
```

## PR10-B 의 한 줄 정의

> **PR10-B 는 PR6~PR10-A 가 잠근 5 status transition 들이 "어느 path 로 어느
> 상태에 도달했는가" 의 audit 기록을 남기는 PR 이다. 판단 근거가 아니라
> 추적 기록.**

> **상태 판단을 바꾼 PR 이 아니라, PR6~PR10-A 에서 이미 닫힌 lifecycle 전이들의
> 경로를 engine-local sequence 기반으로 추적 가능하게 만든 audit PR.**

## 핵심 명제 (§23.2)

```text
Lifecycle history records status transitions, not claim creation.

A lifecycle event exists only when an existing claim changes from one status
to another. The event records engine-local order, not wall-clock time or
freshness.
```

한국어:

```text
Lifecycle history 는 status transition 만 기록한다. claim 생성은 transition 이
아니므로 기록되지 않는다.

이벤트는 engine-local 순서만 표현한다. 시간 차이 / freshness 는 PR10-B 가
표현하지 않는다.
```

## 닫힌 흐름 (PR10-B 추가분)

```python
# 1) Claim 생성 (history 빈 tuple)
claim = engine.add_claim(...)                       # status=CANDIDATE
engine.claim_lifecycle_history(claim)               # → ()  (Sub-decision K)

# 2) Gap 추가 + resolve (history 무변화 — 비-transition)
gap = engine.add_gap(...)
ev = engine.add_evidence(...)
engine.resolve_gaps_for_evidence(ev)
engine.claim_lifecycle_history(claim)               # → ()

# 3) Confirm — transition 발생, event 1 기록
engine.confirm_claim_if_ready(claim)                # → True, CONFIRMED
engine.claim_lifecycle_history(claim)
# → (ClaimLifecycleEvent(seq=1, claim_id=claim, from=CAND, to=CONF,
#                        transition="confirm_if_ready"),)

# 4) Register contradiction (history 무변화 — 비-transition)
ev_contra = engine.add_evidence(...)
engine.register_contradiction(claim, ev_contra)

# 5) Dispute — transition 발생, event 2
engine.dispute_claim_if_ready(claim)                # → True, DISPUTED
# history seq: 1 (confirm), 2 (dispute)

# 6) Resolve disputed — transition 발생, event 3
engine.register_contradiction_resolution(claim, ev_contra)
engine.resolve_disputed_claim_if_ready(claim)       # → True, CONFIRMED 복귀
# history seq: 1, 2, 3 (CAND→CONF, CONF→DISP, DISP→CONF)

# 7) Confirm 재호출 — False, history 무변화 (Sub-decision J)
engine.confirm_claim_if_ready(claim)                # → False (이미 confirmed)
# history seq: 1, 2, 3 (그대로)
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `803f6e2` | docs(contract): define claim lifecycle history MVP (§23) |
| 2 | `ddd4c72` | test(core): lock lifecycle history invariants |
| 3 | `80a055f` | feat(types,engine): add lifecycle history |
| 4 | (this) | docs(dev): PR10-B record |

## 주요 설계 결정 (§23)

### 1. Sub-decision H — Sequence id, not timestamp

```python
self._lifecycle_seq: int = 0  # per-engine monotonic
```

- **timestamp 안 씀** — wall-clock 의존성 0, 결정성 100%, 외부 clock 의존 없음
- **시간 거리 / freshness 표현 안 함** — PR10-A 의 timestamp / freshness OOS
  와 정합 (freshness 정책은 PR11+ 별도 결정)

### 2. Sub-decision I — Private string literal transition labels

```python
transition: str   # audit label, NOT public constant
```

5 transition 값:

| API | `transition` 값 |
|---|---|
| `confirm_claim_if_ready` (PR6) | `"confirm_if_ready"` |
| `refute_claim_if_ready` (PR7) | `"refute_if_ready"` |
| `dispute_claim_if_ready` (PR8) | `"dispute_if_ready"` |
| `resolve_disputed_claim_if_ready` (PR9-A) | `"resolve_disputed_if_ready"` |
| `refute_disputed_claim_if_ready` (PR10-A) | `"refute_disputed_if_ready"` |

| 옵션 | 채택 | 이유 |
|---|---|---|
| Public `TRANSITION_*` constants | ✗ | 외부 의존 발생, 변경 자유 손실 |
| **Private literal (audit label)** | ✓ | implementation detail, 미래 변경 자유 |

PR10-A 의 `_REFUTATION_STRENGTH_THRESHOLD` private 정신과 일관.

### 3. Sub-decision J — Record only on actual transition (True)

```python
# True path 에서만 helper 호출
self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_CONFIRMED)
self._record_claim_lifecycle_transition(
    claim_id, old_status, CLAIM_STATUS_CONFIRMED, "confirm_if_ready",
)
return True
```

False (no-op) 은 절대 기록 안 됨. 기존 API 시그니처 / return semantics
**완전 무변경** — caller 코드 100% 호환.

### 4. Sub-decision K — Creation is not transition

`add_claim` / `fire_rule` 통한 claim 생성은 history 에 기록되지 않음:

- "transition" 정의 = `from_status → to_status`. 생성은 `from_status` 없음.
- 모든 Claim 은 candidate 로 시작 — "candidate 진입" 정보 0.
- Claim 의 첫 history 이벤트는 **첫 status 변경 시점**.

`add_claim` / `fire_rule` 코드 변경 0.

### 5. Sub-decision L — Per-engine single counter

```python
self._lifecycle_seq: int = 0  # NOT per-claim
```

같은 engine 안의 모든 claim 의 transition 순서를 비교 가능. cross-claim 분석
의 기반:

```python
# claim_a 가 먼저 confirm, claim_b 가 그 후 refute
seq_a = engine.claim_lifecycle_history(claim_a)[0].seq  # 1
seq_b = engine.claim_lifecycle_history(claim_b)[0].seq  # 2
assert seq_a < seq_b  # cross-claim 순서 표현
```

### 6. 데이터 / 인덱스 분리

```python
# ragcore/types.py
@dataclass(frozen=True)
class ClaimLifecycleEvent:
    seq: int
    claim_id: int
    from_status: int
    to_status: int
    transition: str

# Engine
self._lifecycle_seq: int = 0
self._claim_lifecycle_events: dict[int, list[ClaimLifecycleEvent]] = {}
```

PR4 `_gap_dedup_index` + PR5 `_gap_resolutions` + PR7 `_contradictions` +
PR9-A `_resolved_contradictions` 와 동일 패턴 — Engine 내부 인덱스로 audit
state 표현, dataclass 보존.

### 7. Public read-only API

```python
claim_lifecycle_history(claim_id) -> tuple[ClaimLifecycleEvent, ...]
```

- 반환은 **tuple** (immutable view)
- caller 가 직접 history 를 mutate 할 수 없음 (audit 무결성)
- `_record_claim_lifecycle_transition` 은 private (public mutation API 차단)

### 8. 기존 API 시그니처 / return 무변경

5 lifecycle API:
- `confirm_claim_if_ready`, `refute_claim_if_ready`, `dispute_claim_if_ready`,
  `resolve_disputed_claim_if_ready`, `refute_disputed_claim_if_ready`

PR10-B 가 추가한 것은 **side effect 만** — 시그니처 무변경, return semantics
무변경. PR6~PR10-A 의 호출자 코드 100% 호환.

## 불변식 (테스트로 잠금)

§23.13 의 16 invariant:

1. `claim_lifecycle_history` unknown claim_id → `KeyError`
2. `add_claim` 직후 history 빈 tuple (+ tuple type)
3. **`confirm` 성공 → event (transition="confirm_if_ready", CAND→CONF) ★**
4. `refute_candidate` 성공 → event ("refute_if_ready", CAND→REF)
5. `dispute` 성공 → event ("dispute_if_ready", CONF→DISP)
6. `resolve_disputed` 성공 → event ("resolve_disputed_if_ready", DISP→CONF)
7. `refute_disputed` 성공 → event ("refute_disputed_if_ready", DISP→REF)
8. **False no-op → 기록 안 함** (Sub-decision J)
9. **`add_claim` 단독 → 기록 안 함** (Sub-decision K)
10. 비-transition API (`register_contradiction` / `add_evidence` /
    `resolve_gaps_for_evidence`) → 기록 안 함
11. seq strictly increasing within one claim
12. **seq per-engine monotonic (cross-claim) ★** (Sub-decision L)
13. `ClaimLifecycleEvent` frozen dataclass with 5 fields
14. 기존 500 회귀 없음 (전체 통과로 입증)

(invariant 14, 15 는 inv 3~7 안에 from/to + transition 검증으로 포함)

## 테스트

**517 passing** in ~0.48s (500 → 517, delta 정확히 +17)

### Test-first 흐름

51차 (test-first 잠금):

```text
17 새 tests 추가
실행 결과 (의도된 분포):
- 14 fails: AttributeError 'Engine' has no attribute 'claim_lifecycle_history'
-  3 fails: assert None is not None (ClaimLifecycleEvent missing, getattr 패턴)
+ 기존 500 통과
```

Collection-error 회피 (PR8 39차의 `CLAIM_STATUS_DISPUTED` 패턴):
- `ClaimLifecycleEvent` 를 module-level import 안 함
- `getattr(ragcore, "ClaimLifecycleEvent", None)` dynamic 접근
- 51차에 `ImportError at collection time` 없음

52차 (구현):

```text
- ragcore/types.py: ClaimLifecycleEvent frozen dataclass
- ragcore/__init__.py: re-export + __all__
- ragcore/engine.py: 2 slots + helper + public method + 5 API side effect patch
실행 결과: 517 통과 (17 fail → 17 pass)
```

### 변경 파일 (PR10-B 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §23 신설 (+308 lines) |
| `tests/test_engine_lifecycle_history.py` | 신규 (17 tests, +322 lines) |
| `ragcore/types.py` | `ClaimLifecycleEvent` dataclass (+17 lines) |
| `ragcore/__init__.py` | re-export (+2 lines) |
| `ragcore/engine.py` | import + 2 slots + helper + public + 5 API patch (+71 lines) |
| `docs/dev/PR_011_LIFECYCLE_HISTORY_MVP.md` | 이 파일 (신규) |
| `ragcore/rule_output.py` | **변경 없음** (Sub-decision D 정합) |

### 테스트 분포

| 파일 | PR10-A 후 | PR10-B (51차) | PR10-B (52차) | 변동 |
|---|---|---|---|---|
| `test_engine_lifecycle_history.py` | 0 | 17 (fail) | **17 (pass)** | +17 |
| 나머지 15 파일 | 500 | 500 | **500** | 0 |
| **Total** | 500 | 500 + 17 fail | **517** | **+17** |

### 신규 테스트 그룹

**TestClaimLifecycleEvent (3):** dataclass shape (existence + fields + frozen)
**TestClaimLifecycleHistory (2):** KeyError + 빈 tuple + tuple type
**TestTransitionsAreRecorded (5):** 5 transition 각각의 event shape (from/to + label)
**TestNoOpsAreNotRecorded (5):** False / add_claim / register_contradiction / resolve_gaps 무변화
**TestSequenceProperties (2):** strict increasing + per-engine monotonic (cross-claim)

## 구현 요약 (52차)

```python
# ragcore/types.py
@dataclass(frozen=True)
class ClaimLifecycleEvent:
    seq: int
    claim_id: int
    from_status: int
    to_status: int
    transition: str

# Engine.__init__
self._lifecycle_seq: int = 0
self._claim_lifecycle_events: dict[int, list[ClaimLifecycleEvent]] = {}

# # ---- Lifecycle history (PR10-B §23) ----
def _record_claim_lifecycle_transition(self, claim_id, from_status, to_status, transition):
    self._lifecycle_seq += 1
    event = ClaimLifecycleEvent(
        seq=self._lifecycle_seq, claim_id=claim_id,
        from_status=from_status, to_status=to_status, transition=transition,
    )
    self._claim_lifecycle_events.setdefault(claim_id, []).append(event)

def claim_lifecycle_history(self, claim_id) -> tuple[ClaimLifecycleEvent, ...]:
    if claim_id not in self._claims: raise KeyError(...)
    return tuple(self._claim_lifecycle_events.get(claim_id, ()))

# 5 API patch — True path 에서만 호출
# 예: confirm_claim_if_ready
old_status = claim.status
self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_CONFIRMED)
self._record_claim_lifecycle_transition(
    claim_id, old_status, CLAIM_STATUS_CONFIRMED, "confirm_if_ready",
)
return True
```

배치: `# ---- Lifecycle history (PR10-B §23) ----` 섹션 신설, PR10-A
`refute_disputed_claim_if_ready` 직후 / `register_rule` 직전.

`ragcore/rule_output.py` 변경 0 (Sub-decision D 정합 — 새 status 없음).

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| Wall-clock timestamp | freshness 정책과 같이 갈 결정 — PR11+ |
| Persistence / 직렬화 | 별도 PR (전체 engine state 직렬화) |
| Event sourcing / undo / rollback | lifecycle 단방향성 보장 |
| Freshness scoring (event 시간 거리 기반) | timestamp 없음 |
| History 기반 자동 lifecycle 결정 | side effect 의 side effect — 명시성 위반 |
| Trace 의 public mutation API | caller 직접 mutate 금지 (audit 무결성) |
| Pretty-printer / 시각화 | 별도 도구 PR |
| 기존 5 API 의 signature 변경 | 호환성 (Sub-decision J 정신) |
| `add_claim` / `fire_rule` / 비-transition API 의 audit | Sub-decision K, 별도 PR |
| Trace 의 삭제 / archive | PR9-A audit 보존 정신 |
| Cross-engine seq 비교 | per-engine monotonic — 의미 없음 |
| Public `TRANSITION_*` constants | Sub-decision I |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| A | **Freshness-based 우세도** — PR10-A 의 단순 strength threshold 를 timestamp/sequence 기반으로 확장 | 중 (PR10-A 의 자연 확장 자리, PR10-B 의 seq 활용 가능) |
| B | **Lifecycle persistence / 직렬화** — engine state + history 저장/복원 | 중 (audit 의미 확장) |
| C | **`superseded` / `retracted` 추가 상태** | 중 (도메인 요구 명확해진 뒤) |
| D | **Effective confidence 재계산** — resolved gap / active contradiction / status / history 를 scoring 에 반영 | 높음 (PR1 의 prior/base/effective 분리 활용) |
| E | **fire_rule audit** — PR10-B 의 history 를 transition 외 영역으로 확장 | 중 (PR3 firing trace 와 통합) |
| F | Engine bulk fire (등록된 모든 룰 일괄 평가) | 중 |
| G | `not` combinator + nested field access | 중 |
| H | Trace 직렬화 / pretty-printer | 낮음 |
| I | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **D (Effective confidence 재계산)** 또는 **A (Freshness 우세도)**.

D 는 lifecycle 의 의미를 scoring 으로 연결하는 자연 후속 — PR1 의
`compute_effective_confidence` stub 이 PR6~PR10-B 의 lifecycle 상태와
contradiction/gap 데이터를 활용해 실제 점수를 만들 수 있다.

A 는 PR10-B 의 seq 를 활용해 "최근 contradiction 이 더 강한 가중치" 같은
정책으로 PR10-A 의 단순 threshold 를 자연스럽게 확장.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §23](../contracts/05_DATA_CONTRACT_MVP.md) — Lifecycle history contract (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §22](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed refutation (PR10-A base)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §21](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed resolution (PR9-A)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §20](../contracts/05_DATA_CONTRACT_MVP.md) — Disputed lifecycle (PR8)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §19](../contracts/05_DATA_CONTRACT_MVP.md) — Claim refutation (PR7)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §18](../contracts/05_DATA_CONTRACT_MVP.md) — Claim lifecycle (PR6)
- [docs/dev/PR_006_CLAIM_LIFECYCLE_MVP.md](PR_006_CLAIM_LIFECYCLE_MVP.md)
- [docs/dev/PR_007_CLAIM_REFUTATION_MVP.md](PR_007_CLAIM_REFUTATION_MVP.md)
- [docs/dev/PR_008_DISPUTED_LIFECYCLE_MVP.md](PR_008_DISPUTED_LIFECYCLE_MVP.md)
- [docs/dev/PR_009_DISPUTED_RESOLUTION_MVP.md](PR_009_DISPUTED_RESOLUTION_MVP.md)
- [docs/dev/PR_010_DISPUTED_REFUTATION_MVP.md](PR_010_DISPUTED_REFUTATION_MVP.md) — PR10-A base

## How to Run

```bash
git checkout feat/lifecycle-history-mvp
pip install -e .
pytest -v
```

517 tests in ~0.48s. No new external dependencies.

## Result

PR10-B 가 PR6~PR10-A 의 lifecycle 사면 위에 **audit 레이어** 를 얹었다. 엔진이
이제 다음 두 질문에 분리해서 답할 수 있다:

```text
"이 Claim 의 현재 상태는?"        → status (PR6~PR10-A)
"이 Claim 이 어떤 path 로 여기에 왔는가?" → claim_lifecycle_history (PR10-B)
```

특히 PR7 candidate-origin refuted 와 PR10-A disputed-origin refuted 의 구분이
이제 history 의 transition label 로 명시화 가능:

```python
# PR7 origin: candidate → refuted
event.transition == "refute_if_ready"

# PR10-A origin: disputed → refuted
event.transition == "refute_disputed_if_ready"
```

남은 결정점 (freshness 우세도, persistence, scoring 재계산, superseded /
retracted) 은 PR11+ 에서.

PR10-B 는 **상태 판단을 바꾼 PR 이 아니라**, PR6~PR10-A 에서 이미 닫힌
lifecycle 전이들의 경로를 engine-local sequence 기반으로 추적 가능하게 만든
**audit PR**.
