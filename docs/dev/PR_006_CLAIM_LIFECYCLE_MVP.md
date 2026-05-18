# PR #006 — Claim Lifecycle MVP

> Status: ready to merge (after Draft PR review).
> Branch: `feat/claim-lifecycle-mvp` → `main`
> Base: `a37c9e7` (PR5 merged)
> Tests: 435 passing (local)

## 목적

PR5 까지의 흐름:

```text
Rule fires    → Claim (candidate) + Gap(s) (dedup)
Evidence 추가 → resolve_gaps_for_evidence(ev) → matching gap 닫힘
gap_resolution(g) → 누가 닫았는지 조회
```

PR6 추가:

```text
필요시 confirm_claim_if_ready(claim_id) 호출
  → 이 Claim 이 참조하는 모든 Gap 이 resolved 인지 검사
  → 조건 만족 시 candidate → confirmed
```

즉 PR6 는 **Claim 의 상태 전이** 최소 기능. 새 판단을 만드는 게 아니라
"이미 존재하는 Claim 이 요구했던 Gap 들이 다 채워졌는가?" 만 확인한다.

전이는 **단일 방향**:

```text
candidate → confirmed
```

**명시 호출만.** `resolve_gaps_for_evidence` 나 `add_evidence` 에 side effect
로 자동 confirm 하지 않는다 (§17.7 의 명시성 원칙과 같은 정신).

## 닫힌 흐름 (PR6 추가분)

```python
# 1) Rule fires → candidate Claim + Gap
claim = fire_rule(engine, def_, cond, out, subject_id=s, context=ctx,
                  required_evidence=template)
engine.get_claim(claim).status  # → CLAIM_STATUS_CANDIDATE

# 2) Evidence 추가 + resolve
ev = engine.add_evidence(claim_id=claim, raw_ref_id=0,
                         evidence_type=T, strength=0.8)
engine.resolve_gaps_for_evidence(ev)

# 3) confirm 시도
confirmed = engine.confirm_claim_if_ready(claim)
# → True (모든 referenced gap 이 resolved 인 경우)
engine.get_claim(claim).status  # → CLAIM_STATUS_CONFIRMED

# 4) 재호출은 idempotent
engine.confirm_claim_if_ready(claim)  # → False (no-op)
engine.get_claim(claim).status         # → CLAIM_STATUS_CONFIRMED (유지)
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `2043d98` | docs(contract): define claim lifecycle MVP (§18) |
| 2 | `996ab09` | test(core): lock claim lifecycle invariants |
| 3 | `59d8c39` | feat(engine): add confirm_claim_if_ready |
| 4 | (this) | docs(dev): PR6 record |

## 주요 설계 결정 (§18)

### 1. API 이름 — `confirm_claim_if_ready`

| 후보 | 채택 | 이유 |
|---|---|---|
| `promote_claim_if_resolved` | ✗ | "promote" 는 가치판단 함의 |
| `evaluate_claim_readiness` | ✗ | 동작 (전이) 보다 검사처럼 들림 |
| `confirm_claim_if_ready` | ✓ | 동작 + 조건 + 결과를 한 이름에 |

### 2. Resolved 의 정의 — PR5 truth-source 그대로

```python
gap is resolved  ⇔  self.gap_resolution(gap.id) is not None
                 ⇔  gap.id in self._gap_resolutions
```

`Gap` dataclass 에 `status` / `resolved_by_evidence_id` 같은 필드를 **추가하지
않는다** (PR5 §17.2 결정 유지). `_gap_resolutions: dict[gap_id, evidence_id]` 가
유일한 resolved truth-source.

이 결정이 중요한 이유: PR5 가 PR4 의 "Gap dataclass 단일 필드" 결정을 보존하면서
resolution 을 Engine 내부 인덱스로 표현했는데, PR6 가 다시 `Gap.status` 같은
필드를 도입하면 PR4/PR5 결정이 무효화된다. PR6 는 자기 신규 상태 (Claim status
전이) 만 추가하고 기존 데이터 구조는 건드리지 않는다.

### 3. 전이 규칙 — 결정표

| Claim 상태 | gap 개수 | 모든 gap resolved? | 결과 상태 | 반환 |
|---|---|---|---|---|
| `candidate` | 0 | — | `candidate` | `False` |
| `candidate` | 1+ | yes | **`confirmed`** | **`True`** |
| `candidate` | 1+ | no | `candidate` | `False` |
| `confirmed` | any | any | `confirmed` | `False` (no-op) |
| `refuted` | any | any | `refuted` | `False` (no-op) |

### 4. Gap 0 개 candidate 자동 confirm 금지

"검증 끝남" 이 아니라 "확인 근거 없음" 이 PR6 의 해석. confirm 의 의미를
"resolved gap 들이 Claim 을 올렸다" 로 좁게 잠그기 위함.

### 5. Idempotency — 재호출 no-op

```python
engine.confirm_claim_if_ready(c)  # → True  (전이)
engine.confirm_claim_if_ready(c)  # → False (이미 confirmed, no-op)
```

`False` 는 실패가 아니라 "전이 발생하지 않음" 일 뿐.

### 6. Refuted 복구 금지

`refuted → candidate` 또는 `refuted → confirmed` 같은 복구는 PR6 범위 밖.
`refuted` 상태 Claim 은 모든 조건이 충족돼도 무조건 `False` + 상태 유지.

PR6 자체에는 refuted 로 만드는 API 가 없지만, 미래 PR7 에서 도입돼도 PR6 의
이 보장은 깨지면 안 된다.

### 7. unknown claim_id — KeyError

PR1~PR5 의 fail-fast 패턴과 일관 (`add_*` / `gap_resolution` / `resolve_*`
모두 unknown id → `KeyError`).

### 8. frozen Claim 의 status 갱신 — `dataclasses.replace`

`Claim` 은 `@dataclass(frozen=True)` 이므로 직접 변경 불가. 표준 라이브러리의
`replace(claim, status=CLAIM_STATUS_CONFIRMED)` 로 새 인스턴스 생성 후 storage
교체.

## 불변식 (테스트로 잠금)

§18.7 의 10 개 invariant:

1. candidate + gap 0 개 → False, candidate 유지
2. candidate + 모든 gap resolved → True, confirmed
3. candidate + 일부 unresolved → False, candidate 유지
4. 이미 confirmed → False, confirmed 유지 (idempotent)
5. refuted → False, refuted 유지 (복구 금지)
6. 두 번째 호출 idempotent — 첫 True, 두 번째 False
7. unknown `claim_id` → `KeyError`
8. confirm 호출 시 `_gap_resolutions` / `Gap` fields 무변화
9. confirm 호출 시 `base_confidence` 무변화
10. 기존 425 tests 그대로 통과 (회귀 방지) — 전체 통과로 입증

## 테스트

**435 passing** in ~0.31s (425 → 435, delta 정확히 +10)

### Test-first 흐름

31차 (test-first 잠금):

```text
TestConfirmClaimIfReady 10 tests 추가
실행 결과: 10 fail (AttributeError: 'Engine' object has no attribute 'confirm_claim_if_ready')
                + 기존 425 통과
→ 의도된 상태. 테스트가 정확히 새 API 부재를 잡는다.
```

32차 (구현):

```text
Engine.confirm_claim_if_ready 추가
실행 결과: 435 통과 (10 AttributeError → 10 pass)
```

### 변경 파일 (PR6 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §18 신설 (+152 lines) |
| `tests/test_engine_claim_lifecycle.py` | 신규 (10 tests, +258 lines) |
| `ragcore/engine.py` | imports + `confirm_claim_if_ready` method (+38 lines) |
| `docs/dev/PR_006_CLAIM_LIFECYCLE_MVP.md` | 이 파일 (신규) |

### 테스트 분포

| 파일 | PR5 후 | PR6 (31차) | PR6 (32차) | 변동 |
|---|---|---|---|---|
| `test_engine_claim_lifecycle.py` | 0 | 10 (fail) | **10 (pass)** | +10 |
| 나머지 10 파일 | 425 | 425 | **425** | 0 |
| **Total** | 425 | 425 + 10 fail | **435** | **+10** |

### 신규 테스트 그룹

**TestConfirmClaimIfReady (10):**
- `test_candidate_with_zero_gaps_returns_false_and_keeps_status` — inv 1
- `test_candidate_with_all_gaps_resolved_promotes_to_confirmed` — inv 2
- `test_candidate_with_partial_resolution_returns_false` — inv 3
- `test_candidate_with_no_evidence_returns_false` — inv 3 보강
- `test_confirmed_reinvocation_is_noop` — inv 4
- `test_second_call_after_promotion_is_idempotent` — inv 6
- `test_refuted_claim_is_not_revived` — inv 5
- `test_unknown_claim_id_raises_key_error` — inv 7
- `test_confirm_does_not_mutate_gap_state` — inv 8
- `test_confirm_does_not_change_base_confidence` — inv 9

`refuted` / `confirmed` 상태 setup 은 PR6 에 다른 경로가 없으므로 white-box
(`engine._claims[c] = replace(..., status=...)`) 방식. 32차 impl 이후에도
동일하게 동작.

## 구현 요약 (32차)

```python
# ragcore/engine.py
from dataclasses import replace
from ragcore.types import CLAIM_STATUS_CANDIDATE, CLAIM_STATUS_CONFIRMED

def confirm_claim_if_ready(self, claim_id: int) -> bool:
    if claim_id not in self._claims:
        raise KeyError(f"unknown claim_id: {claim_id}")
    claim = self._claims[claim_id]
    if claim.status != CLAIM_STATUS_CANDIDATE:
        return False
    gaps = self.gaps_for_claim(claim_id)
    if not gaps:
        return False
    if not all(self.gap_resolution(g.id) is not None for g in gaps):
        return False
    self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_CONFIRMED)
    return True
```

배치: `# ---- Claim lifecycle (PR6 §18) ----` 섹션 신설, `gap_resolution`
직후 / `register_rule` 직전. PR5 `Gap resolution` 섹션과 시각적 연속성.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| `refuted` 전이 / contradiction evidence 정의 | PR7 |
| Auto-transition (`resolve` / `add_evidence` side effect) | 명시성 원칙 (§17.7 정신) |
| `confidence` (`base_confidence` / `effective`) 재계산 | scoring 변경 별도 PR |
| `confirmed_at` timestamp / history / lifecycle trace | 직렬화 PR |
| Partial confirmation (일부 gap 만으로 confirm) | confirm 의 의미 약화 — 금지 |
| Evidence strength-weighted promotion | PR9+ |
| Gap 0 개 Claim 자동 confirm | §18.4 참조 |
| `refuted → candidate` 복구 / `confirmed → candidate` 강등 | 별도 결정점 |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| A | **`refuted` 전이 + contradiction evidence 정의** — `refute_claim` API + contradiction 의미 | 높음 (PR6 의 자연 후속) |
| B | Strength-weighted resolution / overwrite policy | 중 |
| C | Lifecycle trace / `confirmed_at` timestamp | 중 |
| D | Engine bulk fire (등록된 모든 룰 일괄 평가) | 중 |
| E | `not` combinator + nested field access | 중 |
| F | Trace 직렬화 / pretty-printer | 낮음 |
| G | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **A (`refuted` 전이)** — Claim lifecycle 의 다른 한 축. PR6 가 "positive"
방향 (candidate → confirmed) 을 잠갔으므로 PR7 에서 "negative" 방향
(candidate → refuted) 의 contradiction evidence 정의 + API 를 결정하면
lifecycle 양 끝이 닫힌다.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §18](../contracts/05_DATA_CONTRACT_MVP.md) — Claim lifecycle contract (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §17](../contracts/05_DATA_CONTRACT_MVP.md) — Gap resolution (PR5 base, resolved truth-source)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §16](../contracts/05_DATA_CONTRACT_MVP.md) — Gap dedup (PR4 base)
- [docs/dev/PR_001_PYTHON_REFERENCE_CORE_MVP.md](PR_001_PYTHON_REFERENCE_CORE_MVP.md)
- [docs/dev/PR_002_RULE_ENGINE_MVP.md](PR_002_RULE_ENGINE_MVP.md)
- [docs/dev/PR_003_RULE_FIRING_TRACE_MVP.md](PR_003_RULE_FIRING_TRACE_MVP.md)
- [docs/dev/PR_004_GAP_DEDUP_MVP.md](PR_004_GAP_DEDUP_MVP.md)
- [docs/dev/PR_005_GAP_RESOLUTION_MVP.md](PR_005_GAP_RESOLUTION_MVP.md) — Phase 4 base

## How to Run

```bash
git checkout feat/claim-lifecycle-mvp
pip install -e .
pytest -v
```

435 tests in ~0.31s. No new external dependencies.

## Result

PR6 는 PR5 의 gap resolution 결과를 Claim 상태 전이로 연결하는 가장 작은 다리.
엔진이 이제 명시적으로:

```text
"이 Claim 이 요구했던 모든 증거가 채워졌는가?
 그렇다면 candidate 에서 confirmed 로 올린다."
```

라는 한 문장을 수행할 수 있다. `refuted` 방향과 confidence 재계산은 PR7+ 에서.
