# PR #004 — Gap Dedup MVP

> Status: ready to merge (after Draft PR review).
> Branch: `feat/gap-dedup-mvp` → `main`
> Base: `a1a9db3` (Phase 3 merged)
> Tests: 413 passing (local)

## 목적

Engine 의 Gap 모델에 **exact-match deduplication** 을 추가한다.

이 PR 의 핵심은 단순히 "중복 Gap 제거" 가 아니라, 더 정확히는:

> **Claim 은 계속 쌓되, Gap 슬롯은 `(subject, rule, gap_type, evidence_type)` 기준으로 재사용** 하는 구조를 만든 것.

PR3 까지의 동작은 같은 룰이 같은 entity 에 반복 firing 될 때마다 동일한 evidence_type 의 Gap 이 매번 새로 생성됨 — 운영 노이즈가 누적. PR4 로 이게 닫힘.

## 닫힌 흐름 (PR4 추가분)

```python
# 1번째 fire
claim_a = fire_rule(engine, def, cond, out,
                    subject_id=subject, context=ctx,
                    required_evidence=template)
# → Claim A 생성, Gap g1/g2/g3 (신규)

# 2번째 fire (같은 입력)
claim_b = fire_rule(engine, def, cond, out,
                    subject_id=subject, context=ctx,
                    required_evidence=template)
# → Claim B 생성, Gap g1/g2/g3 (reuse — 신규 생성 X)

# 결과 상태:
# - Claim 2개 (각 firing 마다 생성)
# - 실제 Gap 3개 (총 6개 아님)
# - RuleStats.firing_count == 2 (매 firing +1)
# - engine.gaps_for_claim(claim_a) == engine.gaps_for_claim(claim_b)
```

## 들어간 커밋 (5)

| # | SHA | 내용 |
|---|---|---|
| 1 | `952f924` | docs(contract): define gap dedup MVP (§16) |
| 2 | `ef16e08` | feat(engine): add gap dedup behavior |
| 3 | `57b88b7` | test(engine,rule-runtime): lock gap dedup invariants |
| 4 | `4e47367` | fix(engine): validate gap severity before dedup branch |
| 5 | (this) | docs(dev): PR4 record |

## 주요 설계 결정 (§16)

### 1. Dedup key

```python
GapDedupKey = (subject_id, created_by_rule, gap_type, required_evidence_type)
```

각 필드 이유:

| 필드 | 이유 |
|---|---|
| `subject_id` | 어느 entity 에 대한 gap — 다른 entity 는 별개 |
| `created_by_rule` | 어느 룰의 gap — 다른 룰이 같은 evidence 요구해도 별개 |
| `gap_type` | gap 종류 안전장치 |
| `required_evidence_type` | 진짜 dedup 대상 |

명시적 제외:

| 제외 | 이유 |
|---|---|
| `rule_version` | 버전 올라도 같은 슬롯 → 같은 gap (누적 폭발 방지) |
| `severity` | 우선순위 속성, 정체성 아님 |

### 2. `Gap.claim_id` 의미 약화

```text
이전: Gap.claim_id = 이 Gap 이 속한 유일한 Claim
이후: Gap.claim_id = 이 Gap 을 최초로 등록한 Claim
```

`Gap` dataclass 구조는 **변경 없음** (단일 필드 유지). Phase 2 §14 의 "명시적 link" 결정은 유지하면서 의미만 "first registering" 으로 약화.

### 3. Engine 내부 참조 인덱스

```python
_gap_dedup_index: dict[(subject, rule, type, evidence), gap_id]
_claim_gap_refs:  dict[claim_id, set[gap_id]]
```

`_claim_gap_refs` 가 핵심 — `Gap.claim_id` 의미 약화로 인한 정보 손실 방지. 어느 Claim 이 어떤 Gap 을 참조하는지 Engine 상태에서 추적 가능.

### 4. `gaps_for_claim` 의미 확장

```text
이전: gap.claim_id == claim_id 필터
이후: _claim_gap_refs[claim_id] 기반 (참조하는 모든 gap)
```

dedup 으로 reuse 된 gap 도 포함. 반환 순서는 gap_id 오름차순 (결정적).

### 5. severity 정책

- dedup key 에 포함 안 함
- 동일 key 재사용 시 기존 Gap 의 severity 유지 (merge 금지)
- 하지만 **입력 검증은 dedup hit/miss 모두 동일하게 적용** (28.5차 fix)
- 잘못된 severity (e.g., 1.5) 는 dedup hit 이라도 `ValueError`

이 마지막 결정 (`28.5차`) 이 중요 — dedup hit 분기가 입력 검증을 silent skip 하면 API 의 입력 검증 의미가 조용히 약해진다. GPT 검수에서 짚힘.

### 6. Claim / RuleStats 의미 보존

| | dedup 발생해도 |
|---|---|
| Claim | 매 firing 생성 (변화 0) |
| `RuleStats.firing_count` | 매 firing +1 (변화 0) |
| FiringTrace 의 다른 필드 | 변화 0 |

PR3 의 §15 contract 와 충돌 없음.

## 불변식 (테스트로 잠금)

1. 같은 `(subject_id, rule_id, gap_type, evidence_type)` 은 정확히 하나의 Gap
2. `gaps_for_claim(claim_id)` 는 `_claim_gap_refs[claim_id]` 와 일치
3. dedup hit 시에도 `FiringTrace.gap_ids` 비지 않음 (재사용 id 반환)
4. 2번째 firing 의 `gap_ids` = 1번째와 동일 (같은 input)
5. `gap.severity` 는 최초 등록 시 값으로 유지 (재사용 시 변경 없음)
6. `Claim` 은 매 firing 생성 — dedup 영향 없음
7. `RuleStats.firing_count` 는 매 firing +1 — dedup 영향 없음
8. 잘못된 severity 입력은 dedup hit/miss 모두 `ValueError` (28.5차 잠금)

## 테스트

**413 passing** in ~0.4s

### 변경 파일 (PR4 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §16 신설 (+214 lines) |
| `ragcore/engine.py` | `_gap_dedup_index` / `_claim_gap_refs` 슬롯 + `add_gap` dedup 로직 + `gaps_for_claim` 의미 확장 + severity 검증 우선 (+54 lines, -8) |
| `tests/test_engine_relation_gap.py` | TestAddGapDedup (4) + TestAddGapDedupKeyFields (7) + TestAddGapDedupConsistency (2) — 13 new (+301 lines) |
| `tests/test_rule_runtime.py` | TestFireRuleDedupInvariants (6) + 1 updated (`test_duplicate_evidence_types_*`) — 6 new effectively (+181 lines, -1 semantic update) |
| `docs/dev/PR_004_GAP_DEDUP_MVP.md` | 이 파일 (신규) |

### 테스트 분포

| 파일 | 22차 후 | 28차 후 | 28.5차 후 | 변동 |
|---|---|---|---|---|
| `test_engine_relation_gap.py` | 18 | 30 | **31** | +13 |
| `test_rule_runtime.py` | 57 | 63 | **63** | +6 |
| 나머지 8 파일 | 319 | 319 | **319** | 0 |
| **Total** | 394 | 412 | **413** | **+19** |

기존 Phase 1/2/3 의 394 tests 중 `test_duplicate_evidence_types_create_duplicate_gaps` 1개만 의도적 갱신 (이름 + 단언) — 원 docstring 이 `"MVP — dedup 안 함"` 으로 pre-PR4 동작 추적 명시. PR4 가 정확히 그 동작을 바꾸므로 docstring + 단언 동시 업데이트.

### 신규 테스트 그룹

**Engine 레벨 (13):**
- `TestAddGapDedup` (4): same-claim / cross-claim / gaps_for_claim 의미 확장 / first registering 유지
- `TestAddGapDedupKeyFields` (7): subject / rule / gap_type / evidence_type 각각 별개 + severity excluded / preserved / dedup_hit_validates
- `TestAddGapDedupConsistency` (2): public ↔ private 일관성 / engine 격리

**fire_rule 레벨 (6):**
- `TestFireRuleDedupInvariants`: 2회 fire → Claim 2 + Gap 3 / gap_ids 동일 / cross-claim refs 동일 / rule_version excluded / firing_count 보존 / condition false path

## Out of Scope (의도적 제외)

- **`Gap.claim_id` → `claim_ids` tuple 화** — 큰 스키마 변경, 별도 결정점
- **Cross-rule dedup** — 다른 룰이 같은 evidence 요구 시 합치기
- **Cross-version 격리 / 확장** — 현재는 version 무시
- **Severity merge / max-of-N / history**
- **Semantic merge / 유사도 / LLM 판단**
- **Gap 삭제 / archive / TTL**
- **`_gap_dedup_index` public 노출**
- **Claim lifecycle** (candidate → confirmed/refuted 자동 전이)
- **Evidence-based Gap resolution** (evidence 채워지면 gap 닫기)
- **RAG / Vector DB / LLM 통합**
- **직렬화 / 영속화**

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| A | **Claim 승격 logic** — evidence 채워지면 candidate → confirmed | 높음 (실 활용 가치) |
| B | **Evidence-based Gap resolution** — evidence 가 gap 을 만족시키면 자동 닫기 | 높음 (Gap 의 자연 다음 단계) |
| C | Cross-rule Gap merge | 중 |
| D | Engine bulk fire (등록된 모든 룰 일괄 평가) | 중 |
| E | `not` combinator + nested field access | 중 |
| F | Trace 직렬화 / pretty-printer | 낮음 |
| G | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **A (Claim 승격) 또는 B (Evidence resolution)** — 둘 다 Gap-Evidence-Claim 의 살아있는 흐름을 닫는 자연 다음 단계.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §16](../contracts/05_DATA_CONTRACT_MVP.md) — Gap dedup contract
- [docs/contracts/05_DATA_CONTRACT_MVP.md §14](../contracts/05_DATA_CONTRACT_MVP.md) — Phase 2 Gap 모델 (base)
- [docs/dev/PR_001_PYTHON_REFERENCE_CORE_MVP.md](PR_001_PYTHON_REFERENCE_CORE_MVP.md) — Phase 1 record
- [docs/dev/PR_002_RULE_ENGINE_MVP.md](PR_002_RULE_ENGINE_MVP.md) — Phase 2 record
- [docs/dev/PR_003_RULE_FIRING_TRACE_MVP.md](PR_003_RULE_FIRING_TRACE_MVP.md) — Phase 3 record (base)

## How to Run

```bash
git checkout feat/gap-dedup-mvp
pip install -e .
pytest -v
```

413 tests in ~0.4s. No new external dependencies.
