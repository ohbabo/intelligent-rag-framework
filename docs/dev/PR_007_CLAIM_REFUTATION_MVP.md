# PR #007 — Claim Refutation MVP

> Status: ready to merge (after Draft PR review).
> Branch: `feat/claim-refutation-mvp` → `main`
> Base: `542514c` (PR6 merged)
> Tests: 450 passing (local)

## 목적

PR6 까지의 흐름:

```text
Rule fires       → Claim (candidate) + Gap(s)
resolve(ev)      → matching gap 닫힘
confirm_if_ready → 모든 gap resolved 면 candidate → confirmed
```

PR7 추가:

```text
register_contradiction(claim, ev)  → 명시 등록
refute_if_ready(claim)             → contradiction 1+ 있으면 candidate → refuted
```

즉 PR7 은 lifecycle 의 **negative** 방향 (`candidate → refuted`) 을 잠근다. PR6 의
**positive** 방향 (`candidate → confirmed`) 과 합쳐 lifecycle 양 끝이 닫힌다.

## PR7 의 한 줄 정의

> **PR7 은 "반박 전이 구현" 이 아니라 "모름과 반박을 분리한 lifecycle 확장" 이다.**

### 핵심 명제 (§19.2)

```text
Unresolved evidence gaps do not refute a claim.
Only explicit contradiction relations can make a candidate claim refutable.
```

한국어:

```text
증거 부족 = 아직 모름 → candidate 유지
반대 근거 = refuted 자격 → 명시 contradiction 만이 trigger
```

이 분리가 PR7 의 모든 결정을 지배한다. 만약 `refuted` 를 단순히 confirm 의
반대로 잡았다면 `candidate` (모름) 와 `refuted` (반박) 가 섞여 엔진 판단력이
흐려진다.

## 닫힌 흐름 (PR7 추가분)

```python
# 1) candidate Claim 생성
claim_a = engine.add_claim(
    subject_id=s, claim_type=1,
    rule_id=1, rule_version=1, reason_code=0,
)  # → status=CANDIDATE

# 2) 다른 곳의 evidence (cross-claim 허용)
claim_b = engine.add_claim(subject_id=s2, ...)
ev_b = engine.add_evidence(claim_id=claim_b, raw_ref_id=0,
                           evidence_type=42, strength=0.8)

# 3) 명시 contradiction 등록
engine.register_contradiction(claim_a, ev_b)  # → True (새로 등록)

# 4) refute 시도
engine.refute_claim_if_ready(claim_a)         # → True (전이 발생)
engine.get_claim(claim_a).status              # → CLAIM_STATUS_REFUTED

# 5) idempotent
engine.refute_claim_if_ready(claim_a)         # → False (이미 refuted, no-op)
engine.register_contradiction(claim_a, ev_b)  # → False (이미 등록)
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `2bd268f` | docs(contract): define claim refutation MVP (§19) |
| 2 | `48534fe` | test(core): lock claim refutation invariants |
| 3 | `c6e4921` | feat(engine): add contradiction-based claim refutation |
| 4 | (this) | docs(dev): PR7 record |

## 주요 설계 결정 (§19)

### 1. PR7 의 핵심 명제 — gap 과 refute 의 분리

`refute_claim_if_ready` 는 **gap 상태를 보지 않는다**. 오직 `_contradictions`
만 본다.

```python
def refute_claim_if_ready(self, claim_id):
    # gap_resolution 검사 0번. self._contradictions 만 본다.
    if claim.status != CLAIM_STATUS_CANDIDATE: return False
    if not self._contradictions.get(claim_id): return False
    ...
```

이 분리가 PR7 의 본질. PR6 의 `confirm_claim_if_ready` 와는 의미상 비대칭이다.

| | confirm | refute |
|---|---|---|
| Trigger | 모든 referenced gap resolved (충분 조건) | ≥1 contradiction 등록됨 (존재 조건) |
| Gap 상태 의존 | 강한 의존 | 무관 |
| Trigger 의 명시성 | resolve 호출로 간접 trigger 가능 | register_contradiction 명시 등록 필수 |

### 2. 저장 위치 — Engine 내부 dict

```python
self._contradictions: dict[int, set[int]] = {}  # claim_id → evidence_ids
```

`Evidence` / `Claim` / `Relation` dataclass 무변경. PR4 `_gap_dedup_index` /
PR5 `_gap_resolutions` 와 동일 패턴.

### 3. Cross-claim contradiction 허용

`register_contradiction(claim_a, evidence_b)` 에서 `evidence_b.claim_id != claim_a`
케이스를 **허용**. 이게 contradiction 의 본질:

```text
claim_a:  "SSH service is exposed"
ev_b:     "Port 22 is closed" (evidence_b.claim_id = claim_b)
→ ev_b 가 claim_a 를 반박할 수 있어야 함
```

엔진은 의미 추론 안 함 — 호출자가 명시적으로 연결한 contradiction 만 인정.

### 4. 데이터 등록 vs lifecycle 결정의 분리

`register_contradiction` 은 target claim 의 status 와 무관:

```python
engine.register_contradiction(confirmed_claim, ev)  # → True (등록 가능)
engine.register_contradiction(refuted_claim, ev)    # → True (등록 가능)
engine.refute_claim_if_ready(confirmed_claim)       # → False (status guard)
```

이유:
- **데이터 등록 = "이 evidence 가 이 claim 을 반박한다는 사실"** — status 무관한 객관 사실
- **lifecycle 결정 = "이 사실로 상태 전이를 할까"** — status 가드가 결정 시점에서 작동
- 미래 PR 에서 `confirmed → disputed` 같은 상태 도입 시 같은 contradiction
  데이터를 자연스럽게 재활용 가능 (forward-compat)

### 5. API 이름 — PR6 패턴 미러 + 명사 분리

```python
# 등록 (데이터)
register_contradiction(claim_id, evidence_id) -> bool

# 조회 (PR5 contradictions_for_claim 패턴)
contradictions_for_claim(claim_id) -> tuple[int, ...]

# 결정 (PR6 confirm_claim_if_ready 미러)
refute_claim_if_ready(claim_id) -> bool
```

### 6. Idempotency — first-keep + bool 반환

```python
register_contradiction(c, e)  # → True  (첫 등록)
register_contradiction(c, e)  # → False (이미 있음)

refute_claim_if_ready(c)      # → True  (첫 전이)
refute_claim_if_ready(c)      # → False (이미 refuted)
```

PR4 dedup + PR5 first-keep + PR6 confirm idempotent 와 동일 정신.

### 7. 예외 — fail-fast

| 입력 | 동작 |
|---|---|
| `register_contradiction` unknown `claim_id` | `KeyError` |
| `register_contradiction` unknown `evidence_id` | `KeyError` |
| `contradictions_for_claim` unknown `claim_id` | `KeyError` |
| `refute_claim_if_ready` unknown `claim_id` | `KeyError` |

PR1~PR6 의 fail-fast 패턴과 일관.

### 8. 결정성 — `contradictions_for_claim` asc order

`set` iteration 비결정성 회피. PR5 `resolve_gaps_for_evidence` 의 gap_id asc
패턴과 동일.

## 불변식 (테스트로 잠금)

§19.9 의 14 개 invariant:

1. candidate + 0 contradiction → False
2. candidate + 1+ contradiction → True, REFUTED
3. **unresolved gap 만으로 refuted 금지** — PR7 §19.2 핵심 명제
4. **resolved gap 도 refute trigger 아님** — gap 과 refute 의 독립성
5. confirmed → False
6. refuted → False (idempotent)
7. unknown claim_id (refute) → KeyError
8. register_contradiction idempotent (True / False)
9. **Cross-claim contradiction 허용**
10. register status 무관 (confirmed/refuted 에도 등록)
11. refute 가 gap state / base_confidence 무변화
12. contradictions_for_claim asc order
13. unknown evidence_id (register) → KeyError
14. 기존 435 회귀 없음 (전체 통과로 입증)

§19.6 결정표 추가 잠금:
- register-side unknown claim_id → KeyError

## 테스트

**450 passing** in ~0.32s (435 → 450, delta 정확히 +15)

### Test-first 흐름

35차 (test-first 잠금):

```text
15 새 tests 추가
실행 결과: 15 fail (전부 AttributeError: missing register_contradiction /
                                                refute_claim_if_ready)
            + 기존 435 통과
→ 의도된 상태. 테스트가 정확히 미구현 API 부재를 잡는다.
```

36차 (구현):

```text
Engine.register_contradiction / contradictions_for_claim /
refute_claim_if_ready 추가
실행 결과: 450 통과 (15 fail → 15 pass)
```

### 변경 파일 (PR7 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §19 신설 (+224 lines) |
| `tests/test_engine_claim_refutation.py` | 신규 (15 tests, +308 lines) |
| `ragcore/engine.py` | imports + slot + 3 methods (+74 lines) |
| `docs/dev/PR_007_CLAIM_REFUTATION_MVP.md` | 이 파일 (신규) |

### 테스트 분포

| 파일 | PR6 후 | PR7 (35차) | PR7 (36차) | 변동 |
|---|---|---|---|---|
| `test_engine_claim_refutation.py` | 0 | 15 (fail) | **15 (pass)** | +15 |
| 나머지 11 파일 | 435 | 435 | **435** | 0 |
| **Total** | 435 | 435 + 15 fail | **450** | **+15** |

### 신규 테스트 그룹

**TestRefuteClaimIfReady (7):** inv 1~7 (전이 + no-op + KeyError)
**TestRegisterContradiction (5):** inv 8~10, 13 + §19.6 register-side KeyError
**TestContradictionsForClaim (1):** inv 12 (결정성)
**TestRefutationIsolation (2):** inv 11 (gap state + base_confidence 보존)

confirmed / refuted 상태 setup 은 PR7 에 다른 경로가 없으므로 white-box
(`engine._claims[c] = replace(..., status=...)`) — PR6 와 동일 기법.

## 구현 요약 (36차)

```python
# ragcore/engine.py — # ---- Claim refutation (PR7 §19) ----

def register_contradiction(self, claim_id, evidence_id) -> bool:
    if claim_id not in self._claims: raise KeyError(...)
    if evidence_id not in self._evidences: raise KeyError(...)
    bucket = self._contradictions.setdefault(claim_id, set())
    if evidence_id in bucket: return False
    bucket.add(evidence_id); return True

def contradictions_for_claim(self, claim_id) -> tuple[int, ...]:
    if claim_id not in self._claims: raise KeyError(...)
    return tuple(sorted(self._contradictions.get(claim_id, set())))

def refute_claim_if_ready(self, claim_id) -> bool:
    if claim_id not in self._claims: raise KeyError(...)
    claim = self._claims[claim_id]
    if claim.status != CLAIM_STATUS_CANDIDATE: return False
    if not self._contradictions.get(claim_id): return False
    self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_REFUTED)
    return True
```

배치: `# ---- Claim refutation (PR7 §19) ----` 섹션 신설, PR6 의
`confirm_claim_if_ready` 직후 / `register_rule` 직전.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| `confirmed → refuted` 전이 | history / audit / 재판단 정책 필요 — PR8+ |
| `refuted → candidate` 복구 | 별도 결정점 |
| `confirmed → disputed` / `superseded` / `retracted` | 더 정교한 상태 — PR9+ |
| `confidence` (`base_confidence` / `effective`) 재계산 | scoring 변경 별도 PR |
| `refuted_at` timestamp / contradiction history | 직렬화 PR |
| **Semantic contradiction inference** — 엔진이 의미 추론 | 호출자 책임 |
| Contradiction scope check (target/entity/scope 일치 검증) | 도메인 판단, core 밖 |
| Lifecycle trace (refuted 이벤트 trace) | PR3 trace 구조 확장 별도 PR |
| Auto refute (resolve / add_evidence / register side effect) | 명시성 원칙 (§17.7 정신) |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| A | **confirmed 이후 contradiction 처리** — `confirmed → disputed/superseded` 같은 상태 도입 | 높음 (PR7 의 자연 후속) |
| B | **Refutation/lifecycle trace** — PR3 trace 에 refute/confirm 이벤트 확장 | 중 |
| C | Effective confidence 재계산 — resolved gap / contradiction 을 scoring 에 반영 | 중 (PR1 의 prior/base/effective 분리 활용) |
| D | Strength-weighted resolution / overwrite policy | 중 |
| E | Engine bulk fire (등록된 모든 룰 일괄 평가) | 중 |
| F | `not` combinator + nested field access | 중 |
| G | Trace 직렬화 / pretty-printer | 낮음 |
| H | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **A (`confirmed → disputed/superseded`)**.

이유: PR7 가 `register_contradiction` 의 target status 가드를 일부러 빼둔
이유가 바로 이 후속을 위한 것. confirmed claim 에 contradiction 이 등록될 수
있게 데이터 레이어를 열어뒀으니, A 가 그 데이터를 활용하는 lifecycle 결정
레이어를 닫는다. PR7 의 forward-compat 결정 (§19.4 Notes) 이 직접적으로
가리키는 다음 단계.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §19](../contracts/05_DATA_CONTRACT_MVP.md) — Claim refutation contract (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §18](../contracts/05_DATA_CONTRACT_MVP.md) — Claim lifecycle / confirm (PR6 base)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §17](../contracts/05_DATA_CONTRACT_MVP.md) — Gap resolution (PR5 base)
- [docs/dev/PR_001_PYTHON_REFERENCE_CORE_MVP.md](PR_001_PYTHON_REFERENCE_CORE_MVP.md)
- [docs/dev/PR_002_RULE_ENGINE_MVP.md](PR_002_RULE_ENGINE_MVP.md)
- [docs/dev/PR_003_RULE_FIRING_TRACE_MVP.md](PR_003_RULE_FIRING_TRACE_MVP.md)
- [docs/dev/PR_004_GAP_DEDUP_MVP.md](PR_004_GAP_DEDUP_MVP.md)
- [docs/dev/PR_005_GAP_RESOLUTION_MVP.md](PR_005_GAP_RESOLUTION_MVP.md)
- [docs/dev/PR_006_CLAIM_LIFECYCLE_MVP.md](PR_006_CLAIM_LIFECYCLE_MVP.md) — PR6 base

## How to Run

```bash
git checkout feat/claim-refutation-mvp
pip install -e .
pytest -v
```

450 tests in ~0.32s. No new external dependencies.

## Result

PR7 는 PR6 의 미러가 아니라 **"모름과 반박을 분리한 lifecycle 확장"** 으로
잠겼다. 엔진이 이제 명시적으로:

```text
"이 Claim 이 요구했던 증거가 부족한가?"     → candidate 유지 (아직 모름)
"이 Claim 을 반박하는 명시 evidence 가 있는가?" → refuted (반박됨)
```

라는 두 질문을 분리해서 답할 수 있다. PR1~PR7 흐름으로 lifecycle 의 **양 끝**
(`candidate → confirmed` / `candidate → refuted`) 이 닫혔다.

```text
candidate
  ├─ confirmed  (PR6)
  └─ refuted    (PR7)
```

남은 lifecycle 결정점들 (`confirmed → disputed/superseded`, history, scoring
재계산) 은 PR8+ 에서.
