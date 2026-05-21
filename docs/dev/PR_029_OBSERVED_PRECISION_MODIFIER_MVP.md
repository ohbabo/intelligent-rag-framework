# PR 029 — Observed Precision Modifier MVP (PR29-R)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/rule-stats-observed-precision-mvp` → `main`
> Base: `a6208be` (PR28-O merged)
> Tests: 1024 passing (local)

## Summary

PR29-R connects `RuleStats.observed_precision` to effective confidence as a
bounded no-boost adjustment signal.

It preserves the existing 7-modifier formula shape and refines only the
internal `rule_stats` modifier:

```text
rule_stats_modifier = maturity_modifier × precision_modifier
```

PR29-R is **not** a rule quality verdict PR. `false_positive_rate` remains
out of scope.

> **PR29-R 은 RuleStats 를 rule quality verdict 로 바꾼 PR 이 아니다.**
> **이미 존재하던 observed_precision 값을 no-boost 범위 안에서**
> **rule_stats modifier 의 약한 adjustment signal 로 연결한 PR 이다.**

---

## Baseline

Before PR29-R:

```text
main:  a6208be
tests: 997 passing, 0 fail
```

Completed immediately before this PR:

```text
PR28-O rule version pinning MVP
```

Active formula entering PR29-R:

```text
effective = base
          × status
          × freshness
          × gap
          × count
          × rule_stats
          × evidence_type
```

PR29-R does not change this formula shape.

---

## Core proposition (§41.1)

```text
Observed precision is a bounded adjustment signal,
not a rule quality verdict.
```

More conservative:

```text
Observed precision is optional evidence for rule maturity,
not ground truth.
```

---

## Commits

### 122차 — docs(contract): define observed precision modifier MVP (§41)

Commit: `6c95aa2`

Added: `docs/contracts/05_DATA_CONTRACT_MVP.md §41`

13 subsections (§41.1 ~ §41.13):
- 41.1 Purpose + core/conservative statements
- 41.2 Background (PR20-F / PR26-R 연결)
- 41.3 Non-goals (14 항목)
- 41.4 Formula shape (unchanged + internal refinement)
- 41.5 Maturity modifier (PR26-R unchanged)
- 41.6 Precision modifier (None → 1.0, p → 0.9 + p × 0.1)
- 41.7 No-boost rule
- 41.8 Interaction with existing modifiers
- 41.9 Snapshot compatibility (no schema bump)
- 41.10 Implementation boundary (engine.py only)
- 41.11 Required invariants A~J (10)
- 41.12 Expected test pattern (mixed fail/pass)
- 41.13 Final lock

### 123차 — test(core): lock observed precision modifier invariants

Commit: `ed7ef5f`

Added: `tests/test_engine_rule_stats_observed_precision_modifier.py`

Size:
```text
522 lines
27 tests
10 classes
```

Result: 11 fail + 16 pass / 기존 997 회귀 0 → 1013 passed + 11 failed.

Test class distribution:

| Class | Tests | Contract mapping |
|---|---:|---|
| `TestObservedPrecisionNonePreservesPR26R` | 3 | §41.11 A |
| `TestObservedPrecisionModifierValues` | 3 | §41.11 B |
| `TestObservedPrecisionComposesWithMaturity` | 3 | §41.11 C |
| `TestObservedPrecisionNoBoost` | 2 | §41.11 D |
| `TestObservedPrecisionDoesNotOverrideStatus` | 3 | §41.11 E/F |
| `TestObservedPrecisionDoesNotAffectOtherModifiers` | 2 | §41.11 G |
| `TestFalsePositiveRateStillIgnored` | 3 | §41.11 H |
| `TestObservedPrecisionSnapshotRoundTrip` | 3 | §41.11 I |
| `TestObservedPrecisionPublicBoundary` | 5 | §41.11 J |

Fail breakdown (11):
- Precision modifier values (saturated + p): 2
- Maturity × precision composition: 2
- Status × precision (disputed + p 0.0): 1
- Other modifiers × precision: 2
- FPR + precision interaction: 1
- Snapshot round-trip computed: 1
- 신규 `_RULE_STATS_PRECISION_BASE` / `_RANGE` 부재: 2

Pass breakdown (16):
- None preserves PR26-R: 3
- Saturated + p 1.0 → 1.0: 1
- No boost: 2
- Status dominance with p 1.0: 2
- FPR ignored basic: 2
- Snapshot schema v2 + value preserve: 2
- Private namespace / dataclass: 4

### 124차 — feat(engine): apply observed precision modifier

Commit: `5f7d5b6`

Changed:
- `ragcore/engine.py` (+84 / -13)
- `tests/test_engine_rules.py` (1 natural-expiry test rename + expected update)

New private constants:
```text
_RULE_STATS_PRECISION_BASE = 0.9
_RULE_STATS_PRECISION_RANGE = 0.1
```

`_rule_stats_modifier_for_claim` body extended:
- maturity (PR26-R) unchanged
- new precision_modifier branch:
  - None → 1.0
  - value p → 0.9 + p × 0.1
- return: `maturity_modifier × precision_modifier`

`compute_effective_confidence` docstring updated for §41 references.

Result: 11 fail → 11 pass, 기존 997 회귀 0 → 1024 passing, 0 fail.

### 125차 — docs(dev): record PR29 observed precision modifier MVP

Commit: this commit.

Added: `docs/dev/PR_029_OBSERVED_PRECISION_MODIFIER_MVP.md`.

---

## Final formula

The public 7-modifier formula shape remains unchanged:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
```

Only `rule_stats` is refined internally:

```text
rule_stats_modifier = maturity_modifier × precision_modifier
```

Maturity (PR26-R, unchanged):

```text
firing_count < 0  -> 0.8 (defensive clamp)
firing_count == 0 -> 0.8
firing_count == 1 -> 0.9
firing_count >= 2 -> 1.0
```

Precision (PR29-R, new):

```text
observed_precision is None -> 1.0
observed_precision value p -> 0.9 + p × 0.1
```

Range:

```text
maturity_modifier  ∈ [0.8, 1.0]
precision_modifier ∈ [0.9, 1.0]
rule_stats_modifier ∈ [0.72, 1.0]
```

---

## Composition table

| firing_count | observed_precision | maturity | precision | rule_stats |
|:---:|:---:|:---:|:---:|:---:|
| 0 | None | 0.8 | 1.0 | 0.8 (PR26-R 보존) |
| 0 | 0.0 | 0.8 | 0.9 | **0.72** ← range floor |
| 0 | 1.0 | 0.8 | 1.0 | 0.8 |
| 1 | 0.5 | 0.9 | 0.95 | **0.855** |
| 2 | 0.0 | 1.0 | 0.9 | 0.9 |
| 2 | 0.5 | 1.0 | 0.95 | 0.95 |
| 2 | 1.0 | 1.0 | 1.0 | 1.0 |
| 100 | 1.0 | 1.0 | 1.0 | 1.0 (saturated) |

---

## Sub-decisions locked (10, A~J)

- **A**: None preserves PR26-R
- **B**: precision_modifier range 0.9/0.95/1.0
- **C**: maturity × precision composition
- **D**: no boost — modifier never > 1.0
- **E**: refuted dominance preserved
- **F**: disputed dominance preserved
- **G**: other modifiers (freshness/gap/count/evidence_type) unchanged
- **H**: false_positive_rate ignored
- **I**: snapshot round-trip preserves observed_precision + computed confidence
- **J**: public namespace unchanged

---

## Implementation footprint

Changed files:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md       (§41 신규)
tests/test_engine_rule_stats_observed_precision_modifier.py  (신규)
ragcore/engine.py                            (constants + helper + docstring)
tests/test_engine_rules.py                   (자연 만료 1 갱신)
docs/dev/PR_029_OBSERVED_PRECISION_MODIFIER_MVP.md  (신규)
```

Unchanged files:

```text
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
```

No snapshot schema change:

```text
schema_version remains 2
```

No formula change:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
```

No lifecycle change:

```text
no new lifecycle state
no new lifecycle transition
```

No taxonomy ownership change:

```text
framework still does not own rule quality verdict
false_positive_rate remains out of scope
```

---

## Natural-expiry boundary update

### `test_stub_ignores_rule_stats_in_mvp` (PR2 era)

Old expectation (PR2 stub):

```text
effective = base_confidence only
RuleStats updates are ignored
```

New PR29-R behavior:

```text
effective = base × rule_stats_modifier (PR20-F → PR26-R → PR29-R)
```

Observed case from the updated test:

```text
base 0.6 × maturity 1.0 × precision 0.99 = 0.594
```

The test was renamed to:

```text
test_rule_stats_modifier_after_pr29r_refinement
```

This is **not a regression**.

It records the natural evolution:

```text
PR2 stub: rule_stats ignored
PR20-F:   binary maturity modifier introduced
PR26-R:   continuous maturity refinement
PR29-R:   maturity × precision_modifier
```

The test now documents this evolution rather than asserting the old stub
behavior.

---

## Test result

```text
122차 docs-only             : 997 passing
123차 test-first            : 신규 27 (11 fail + 16 pass), 기존 997 회귀 0
                              → 1013 passed + 11 failed
124차 feat impl + natural-expiry : 11/11 fail 정확히 pass 전환
                                   + 1 PR2 stub invariant 갱신
                              → 1024 passing, 0 fail
125차 docs-only             : 1024 passing, 0 fail 유지
```

### 123차 fail-to-pass mapping (11 fail → 11 pass)

| 차단 영역 | Fail 수 | 124차 메커니즘 |
|---|---:|---|
| Precision modifier values (saturated + p) | 2 | precision_modifier 공식 적용 |
| Maturity × precision composition | 2 | helper return `maturity * precision` |
| Status × precision (disputed + p 0.0) | 1 | composition order preserved |
| Other modifiers × precision (freshness/gap) | 2 | precision applied uniformly |
| FPR + precision interaction | 1 | precision applied (FPR ignored) |
| Snapshot round-trip computed | 1 | engine state 무변경 → restored 동일 |
| 신규 private constants 부재 | 2 | 상수 2 개 추가 |

---

## PR1~PR28-O 정합

- `types.py` 변경 0 — Sub-decision D / J 영구 보존
- `__init__.py` 변경 0 — public export 없음 (Sub-decision J)
- `rule_output.py` 변경 0 — Sub-decision D 영구 보존
- `RuleStats` dataclass 변경 0 — observed_precision 필드는 PR2 시점부터 존재
- PR9-A `active_contradictions_for_claim` asc — 변경 없음
- PR11-C freshness modifier — 변경 없음
- PR12-D + PR23-M gap modifier — 변경 없음
- PR19-E + PR24-N count modifier — 변경 없음
- PR20-F + PR26-R maturity — 변경 없음 (PR29-R 은 곱셈 추가만)
- PR21-L + PR22-S + PR25-T evidence_type — 변경 없음
- PR10-A refute / PR11-B refute_by_freshness — 변경 없음
- PR17 round-trip identity — 보존
- PR18-K migration framework — 변경 없음
- PR27-P external integration spec — 보존 (engine domain-light 유지)
- PR28-O rule version pinning — 보존 (pinned pair lookup 그대로 사용)
- `update_rule_stats` 외부 동작 — 변경 없음

---

## Out of Scope (PR29-R 외)

| 제외 | 이유 / 향후 |
|---|---|
| `false_positive_rate` 사용 | Sub-decision H — PR29-R OOS |
| `confirmed_true_count` / `confirmed_false_count` outcome ratio | Q 트랙 (대규모, 사용자 승인 필요) |
| Rule quality verdict | Sub-decision K (PR26-R 정신 + §41.1 영구) |
| Confidence boost (modifier > 1.0) | Sub-decision D / No-boost rule §41.7 |
| Precision aggregation policy / time decay | §41.3 — PR29-R OOS |
| Auto-disable rules | §41.3 — PR29-R OOS |
| Snapshot schema v3 bump | Sub-decision I — state shape 무변화 |
| Public `_RULE_STATS_PRECISION_*` 상수 export | Sub-decision J — engine 내부 private |
| `types.py` / `__init__.py` / `rule_output.py` 변경 | Sub-decision J 영구 보존 |
| New public enum or constants | Sub-decision J |

---

## Self-review

- [x] 123차 의도 fail 11개 → 124차 11/11 pass 정확히 전환
- [x] 123차 pass 16개 유지
- [x] 기존 997 회귀 0
- [x] 최종 1024 passing, 0 fail
- [x] `_RULE_STATS_PRECISION_BASE = 0.9` 신규
- [x] `_RULE_STATS_PRECISION_RANGE = 0.1` 신규
- [x] `_rule_stats_modifier_for_claim` 본문 확장 (maturity × precision)
- [x] observed_precision None → precision_modifier 1.0 (PR26-R 보존)
- [x] observed_precision p → precision_modifier 0.9 + p × 0.1
- [x] precision_modifier range [0.9, 1.0]
- [x] rule_stats_modifier range [0.72, 1.0]
- [x] no boost 보장 (Sub-decision D)
- [x] refuted dominance preserved (Sub-decision E)
- [x] disputed dominance preserved (Sub-decision F)
- [x] other modifiers unchanged (Sub-decision G)
- [x] false_positive_rate ignored (Sub-decision H)
- [x] snapshot round-trip preserves observed_precision + computed (Sub-decision I)
- [x] `types.py` / `__init__.py` / `rule_output.py` 변경 0 (Sub-decision J)
- [x] `RuleStats` dataclass 변경 0
- [x] snapshot schema_version `2` 유지
- [x] 7-modifier formula shape / 강도 분포 유지
- [x] lifecycle / refute / contradiction 변경 0
- [x] PR23-M / PR24-N / PR26-R / PR21-L / PR22-S / PR25-T / PR27-P / PR28-O regression 모두 검증
- [x] 자연 만료 1 test (PR2 stub invariant) 명시 코멘트 갱신
- [x] PR cycle 신규 push 패턴 적용 (122차 직후 push + Draft PR, 차수마다 push)
- [x] 모든 차수 commit message body PR19 자세한 스타일

---

## Final definition

> **PR29-R 은 RuleStats 를 rule quality verdict 로 바꾼 PR 이 아니다.**
> **이미 존재하던 observed_precision 값을 no-boost 범위 안에서**
> **rule_stats modifier 의 약한 adjustment signal 로 연결한 PR 이다.**

> *Observed precision is a bounded adjustment signal, not a rule quality verdict.*

PR20-F → PR26-R → PR29-R 누적 효과:
- maturity signal 의미 보존 (firing_count 기반)
- threshold = 2 보존 (PR20-F Sub-decision V 그대로)
- center preservation (firing 1 → maturity 0.9, PR26-R)
- zero-observation 분리 (0회 → maturity 0.8, PR26-R)
- bounded precision adjustment (PR29-R, no boost, [0.9, 1.0])
- defensive clamp 유지 (PR26-R Sub-decision BQ)

정제 패턴 4차 연속 완료:
- PR23-M: gap binary → tier (floor 0.7)
- PR24-N: count binary → continuous (floor 0.75)
- PR26-R: rule_stats binary → continuous maturity (floor 0.8)
- PR29-R: rule_stats × precision_modifier (range [0.72, 1.0])

---

## Result

```text
Before PR29-R (main = a6208be):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  rule_stats_modifier = maturity_modifier (PR26-R)
  997 passing

After PR29-R (main = <new sha>):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  (formula shape unchanged, modifier semantics preserved)
  rule_stats_modifier = maturity_modifier × precision_modifier
  range [0.72, 1.0]
  1024 passing, 0 fail
```

7-modifier composition formula shape 보존. `rule_stats` 항만 maturity ×
precision_modifier 로 정제. **PR29-R 의 본질은 RuleStats 의미 확장이 아니라
PR20-F binary → PR26-R maturity → PR29-R precision 의 bounded refinement.**

정제 패턴 4차 연속 완료. Q 트랙 (outcome ratio, claim lifecycle 역전파) 은
명시적으로 OOS 로 둠 — Sub-decision AF + §41.1 정신 보존.
