# PR #005 — Evidence-based Gap Resolution MVP

> Status: ready to merge (after Draft PR review).
> Branch: `feat/gap-resolution-mvp` → `main`
> Base: `46fc376` (PR4 merged)
> Tests: 425 passing (local)

## 목적

Engine 에 **Evidence 가 매칭되는 Gap 을 닫는 최소 루프** 를 추가한다.

PR4 까지의 흐름:

```text
Rule fires    → Claim + Gap(s) (dedup)
Evidence 추가 → 어디에도 연결되지 않음
```

PR5 추가:

```text
Rule fires           → Claim + Gap(s) (dedup)
Evidence 추가        → (의미 변화 없음)
resolve 호출          → matching Gap 들 닫음
gap_resolution(g)    → 누가 닫았는지 조회
```

즉, **"Evidence 가 Gap 을 닫는다"** 는 한 줄을 깨끗하게 잠그는 게 PR5 의 전부.
Claim lifecycle (candidate → confirmed/refuted), scoring 변경, evidence strength
기반 우선순위는 모두 **본 PR 범위 밖** — PR6+.

## 닫힌 흐름 (PR5 추가분)

```python
# 1) Rule fires → Claim + Gap
claim = fire_rule(engine, def_, cond, out, subject_id=s, context=ctx,
                  required_evidence=template)
# → Claim, Gap g (required_evidence_type=T)

# 2) Evidence 추가 (자체 부작용 없음)
ev = engine.add_evidence(claim_id=claim, raw_ref_id=0,
                         evidence_type=T, strength=0.8)
# → engine.gap_resolution(g) is None

# 3) 명시적 resolve
resolved = engine.resolve_gaps_for_evidence(ev)
# → resolved == (g,)
# → engine.gap_resolution(g) == ev
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `df444bf` | docs(contract): define evidence-based gap resolution MVP (§17) |
| 2 | `7e9f365` | feat(engine): add gap resolution APIs |
| 3 | `d4217e6` | test: lock gap resolution invariants |
| 4 | (this) | docs(dev): PR5 record |

## 주요 설계 결정 (§17)

### 1. 저장 위치 — Engine 내부 dict

```python
# Engine.__init__
self._gap_resolutions: dict[int, int] = {}  # gap_id -> evidence_id
```

`Gap` dataclass 는 **변경 없음** — PR2 §14 / PR4 §16 의 "단일 필드" 결정과 충돌하지
않기 위함. 외부에는 `gap_resolution(gap_id)` 메서드로만 노출.

| 옵션 | 채택 | 이유 |
|---|---|---|
| `Gap.resolved_by_evidence_id` 필드 | ✗ | dataclass 변경. 기존 결정과 충돌 |
| Engine 내부 dict | ✓ | PR4 `_gap_dedup_index` / `_claim_gap_refs` 패턴과 일관 |
| `Relation` 으로 표현 | ✗ | "resolved by" 는 의미 관계가 아닌 lifecycle 상태 |

### 2. 매칭 규칙 — type 기준 단일 조건

```python
gap.required_evidence_type == evidence.type
```

명시적 제외:

| 제외 | 이유 |
|---|---|
| `created_by_rule` | 매칭 조건 아님. scope 안이라면 다른 rule 의 gap 도 닫힘 |
| `gap_type` | 현재 단일값 `MISSING_EVIDENCE=1` |
| `gap.severity` | 우선순위 속성, 정체성 아님 |
| `evidence.strength` | strength-weighted resolution 은 별도 PR |

### 3. 검사 범위 — `gaps_for_claim(evidence.claim_id)`

```python
search_scope = self.gaps_for_claim(evidence.claim_id)
```

**Global cross-rule / subject / engine search 는 금지.**
단, 이 scope 안에서는 `created_by_rule` 을 매칭 조건으로 보지 않는다.

> 표현 주의 (30차 작성 시 검토 포인트): "cross-rule resolution 제외" 라고만 쓰면
> 모호. 정확히는 **scope 로 boundary 를 그은 것**이지 `rule_id` 로 boundary 를
> 그은 것이 아니다.

### 4. Cross-claim semantics — gap-scoped

PR4 dedup 으로 여러 Claim 이 같은 Gap 을 공유할 수 있다. 이때 한 claim 의
evidence 로 닫힌 gap 은 그 gap 을 share 하는 **모든 claim 에서 resolved 로 보인다**.

이유:
- Gap 자체가 PR4 부터 `(subject+rule+type+evidence)` 정체성 — claim_id 보다 위 레벨
- "어떤 evidence 가 그 정체성의 gap 을 채웠는가" 는 claim 과 독립적인 사실
- Claim 별 별도 resolution 을 두면 Gap 정체성이 다시 claim 종속 → PR4 와 모순

### 5. First evidence 유지 — overwrite 금지

PR4 의 severity 정책 (`first registering keep`) 과 동일 패턴.

```python
engine.resolve_gaps_for_evidence(ev1)  # → (g,)
engine.resolve_gaps_for_evidence(ev2)  # → ()  (overwrite 안 함)
engine.gap_resolution(g)               # → ev1 (유지)
```

이유:
- "어떤 evidence 가 처음으로 gap 을 닫았는가" 는 stable 한 사실
- 덮어쓰면 동일 입력에 호출 순서 의존 → 비결정적 느낌
- Strength-weighted "더 좋은 evidence 로 교체" 같은 동작은 미래 PR 의 명시적 결정

### 6. `add_evidence` 의미 — 변화 없음

```python
def add_evidence(self, claim_id, raw_ref_id, evidence_type, strength) -> int:
    # PR1 부터 의미 그대로. 자동 resolve 없음.
```

이유 (§17.7):

| | 자동 resolve 의 문제 |
|---|---|
| 순서 의존성 | `add_evidence` 시점에 모든 Gap 이 만들어졌다는 보장 없음 |
| 명시성 | "evidence 가 gap 을 닫았다" 는 의도된 행위여야 함 |
| 테스트성 | resolve 시점이 분리돼야 invariant 검증이 깨끗 |
| 미래 확장성 | strength-weighted / partial resolution 은 명시적이어야 자연스러움 |

### 7. 예외 — fail-fast

```python
resolve_gaps_for_evidence(unknown_id) → KeyError
gap_resolution(unknown_gap_id)        → KeyError  # None 이 아님
gap_resolution(known_unresolved)      → None
```

`gap_resolution` 의 unknown vs unresolved 를 `KeyError` / `None` 으로 구분 —
"resolution 미설정" 과 "gap 자체 없음" 은 의미가 다르다.

### 8. 보존 — 의미 변경 없음

| | PR5 영향 |
|---|---|
| `Gap` / `Claim` / `Evidence` dataclass | 없음 |
| `Claim.status` 자동 전이 | 없음 (PR6 범위) |
| `add_evidence` / `add_gap` / dedup | 없음 |
| `gaps_for_claim` 의미 | 없음 (PR4 정의 그대로) |
| `fire_rule*` / `RuleStats.firing_count` | 없음 |
| `compute_effective_confidence` (scoring) | 없음 |

## 불변식 (테스트로 잠금)

§17.12 의 11개 invariant 를 31차 (smoke 5) + 32차 (invariant 7) 두 라운드로 잠금:

1. matching evidence → matching gap resolved ← smoke
2. non-matching evidence → resolved 없음 ← smoke
3. already resolved gap 재시도 → first evidence 유지, 빈 tuple 반환 ← invariant
4. `gap_resolution(unresolved)` → `None` ← smoke
5. 반환 순서 = gap_id 오름차순 ← invariant
6. 같은 claim 다른 type → 무관 gap 보존 ← invariant
7. cross-claim reused gap → gap-scoped resolution 공유 ← invariant
8. unknown `evidence_id` → `KeyError` ← smoke
9. unknown `gap_id` (in `gap_resolution`) → `KeyError` ← smoke
10. `add_evidence` 자체는 `_gap_resolutions` 변경 없음 ← invariant
11. 기존 418 tests 그대로 통과 (회귀 방지) ← 전체 통과로 입증

추가로 잠그는 경계:
- `created_by_rule` 은 매칭 조건 아님 (다른 rule 의 gap 도 같은 scope 면 닫힘)
- Scope 는 `evidence.claim_id` 로 제한 (다른 subject 의 matching gap 은 보호)

## 테스트

**425 passing** in ~0.33s

### 변경 파일 (PR5 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §17 신설 (+248 lines) |
| `ragcore/engine.py` | `_gap_resolutions` slot + `resolve_gaps_for_evidence` + `gap_resolution` (+42 lines) |
| `tests/test_engine_relation_gap.py` | TestGapResolutionSmoke (5) + TestGapResolutionInvariants (7) (+268 lines) |
| `docs/dev/PR_005_GAP_RESOLUTION_MVP.md` | 이 파일 (신규) |

### 테스트 분포

| 파일 | PR4 후 | PR5 (31차) | PR5 (32차) | 변동 |
|---|---|---|---|---|
| `test_engine_relation_gap.py` | 31 | 36 | **43** | +12 |
| 나머지 9 파일 | 382 | 382 | **382** | 0 |
| **Total** | 413 | 418 | **425** | **+12** |

### 신규 테스트 그룹

**31차 — TestGapResolutionSmoke (5):**
- matching evidence resolves matching gap
- non-matching evidence resolves nothing
- `gap_resolution` returns `None` when unresolved
- unknown `evidence_id` raises `KeyError`
- unknown `gap_id` in `gap_resolution` raises `KeyError`

**32차 — TestGapResolutionInvariants (7):**
- already-resolved gap keeps first evidence (+ second call returns empty)
- one evidence resolves multiple matching gaps (created_by_rule ∉ match)
- evidence does not resolve other-type gap in same claim
- cross-claim reused gap is gap-scoped (PR4 × PR5 핵심 교차)
- scope restricted to evidence.claim_id (다른 subject 보호)
- `add_evidence` does not mutate `_gap_resolutions` (no auto side effect)
- returned gap_ids are ascending (결정성)

## Out of Scope (의도적 제외)

- **`Claim.status` 자동 전이** (`candidate → confirmed/refuted`) — PR6
- **Strength-weighted resolution** (더 좋은 evidence 로 overwrite) — 명시적 정책 결정 필요
- **Partial resolution / score-weighted gap close** — PR6+
- **Rollback / unresolve** — 별도 결정점
- **Resolution timestamp / history** — 직렬화 PR 에서
- **`add_evidence` 의 auto-resolve side effect** — §17.7 참조
- **Engine 전체 / subject 전체 / rule 전체 gap 검색** — §17.5 boundary
- **Cross-rule global resolution** — §17.5 boundary
- **`compute_effective_confidence` 가 resolved gap 을 고려** — scoring 변경은 별도 PR
- **Resolved gap 의 자동 archive / TTL** — 별도 결정점

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| A | **Claim lifecycle** — resolved gaps 기반 candidate → confirmed/refuted 전이 | 높음 (PR5 자연 후속) |
| B | Evidence-strength-weighted resolution (overwrite policy) | 중 |
| C | Cross-rule Gap merge | 중 |
| D | Engine bulk fire (등록된 모든 룰 일괄 평가) | 중 |
| E | `not` combinator + nested field access | 중 |
| F | Trace 직렬화 / pretty-printer | 낮음 |
| G | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **A (Claim lifecycle)** — PR5 가 정확히 그 다음 단계를 위한 토대를 깐 상태.
`gap_resolution(g)` 가 명시적으로 존재하므로 "모든 required gap 이 resolved 인가"
질문이 깨끗하게 표현된다.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §17](../contracts/05_DATA_CONTRACT_MVP.md) — Gap resolution contract (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §16](../contracts/05_DATA_CONTRACT_MVP.md) — Gap dedup (PR4 base, gap-scoped semantics 의 근거)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §14](../contracts/05_DATA_CONTRACT_MVP.md) — Phase 2 Gap 모델
- [docs/dev/PR_001_PYTHON_REFERENCE_CORE_MVP.md](PR_001_PYTHON_REFERENCE_CORE_MVP.md)
- [docs/dev/PR_002_RULE_ENGINE_MVP.md](PR_002_RULE_ENGINE_MVP.md)
- [docs/dev/PR_003_RULE_FIRING_TRACE_MVP.md](PR_003_RULE_FIRING_TRACE_MVP.md)
- [docs/dev/PR_004_GAP_DEDUP_MVP.md](PR_004_GAP_DEDUP_MVP.md) — Phase 3 base

## How to Run

```bash
git checkout feat/gap-resolution-mvp
pip install -e .
pytest -v
```

425 tests in ~0.33s. No new external dependencies.
