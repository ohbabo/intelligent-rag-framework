# PR #021 — Evidence Type Modifier MVP (PR21-L)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/evidence-type-modifier-mvp` → `main`
> Base: `4496554` (PR20-F merged)
> Tests: 742 passing (local)

## 목적

PR20-F 까지의 흐름:

```text
effective = base × status × freshness × gap × count × rule_stats
→ evidence 의 source-quality 차원은 effective 에 반영 안 됨
```

PR21-L 추가:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
→ caller 가 등록한 hint-like evidence type 만으로 받쳐진 Claim 을 약하게 감쇠
```

## PR21-L 의 한 줄 정의

> **PR21-L is not a built-in evidence taxonomy PR.**
> **It adds a caller-registered hint evidence type set and uses it as a weak
> source-quality modifier.**

한국어:

> **PR21-L 은 framework 내부에 evidence type 분류 체계를 추가한 PR 이 아니다.
> caller 가 등록한 hint-like evidence type 집합을 약한 source-quality
> modifier 로 사용하는 PR 이다.**

## 핵심 명제 (§33.2)

```text
Evidence type modifier is a weak source-quality signal, not a truth verdict.
The framework does not assign semantic meaning to Evidence.type integers.
```

한국어:

```text
Evidence type modifier 는 증거의 출처/성격을 약하게 반영하는 신호이지,
그 Claim 의 참/거짓을 판결하는 장치가 아니다.

Evidence.type 의 정수값 자체에는 framework 가 의미를 부여하지 않는다.
caller 가 등록한 evidence type 집합만 modifier 계산에 사용한다.
```

대조:

```text
Evidence type modifier ≠ "이 evidence 는 옳다 / 그르다"
Evidence type modifier ≠ "이 evidence 가 강하다 / 약하다" (← PR11-C strength 자리)
Evidence type modifier = "이 Claim 의 direct supporting evidence 가 모두
                          caller 가 'hint' 로 등록한 type 인가?"
```

## 7-Modifier Composition 완성

```python
effective_confidence(claim) = (
    base_confidence                              # PR1
    × status_modifier(claim.status)              # PR11-D §24
    × freshness_modifier(claim_id)               # PR11-C §26
    × gap_modifier(claim_id)                     # PR12-D §28
    × count_modifier(claim_id)                   # PR19-E §31
    × rule_stats_modifier(claim)                 # PR20-F §32
    × evidence_type_modifier(claim_id)           # PR21-L §33 (신규)
)
```

| modifier | PR | 형태 | 강도 |
|---|---|---|---|
| status_modifier | PR11-D | 4 값 (1.0/1.0/0.5/0.0) | 강 (refuted=0) |
| freshness_modifier | PR11-C | continuous (1 - s × 0.5) | 중 (max 50%) |
| gap_modifier | PR12-D | binary (0.8 / 1.0) | 약 (20%) |
| count_modifier | PR19-E | binary (0.8 / 1.0) | 약 보조 |
| rule_stats_modifier | PR20-F | binary (0.9 / 1.0) | 매우 약 (10%) |
| **evidence_type_modifier** | **PR21-L** | **binary (0.9 / 1.0)** | **매우 약 (10%)** |

## Direct supporting evidence 정의

```text
Direct supporting evidence is defined as
  Evidence.claim_id == claim_id
  excluding evidence ids registered as contradiction or resolved contradiction
  for that claim.
```

즉:

```python
direct_supporting(claim_id) = {
    ev for ev in self._evidences.values()
    if ev.claim_id == claim_id
       and ev.id not in self._contradictions.get(claim_id, set())
       and ev.id not in self._resolved_contradictions.get(claim_id, set())
}
```

이유:

PR11-C / PR19-E 가 이미 contradiction evidence 를 보고 있어, PR21-L 이
같은 evidence 를 또 "supporting" 으로 세면 modifier 의미가 흐려진다. 따라서
"PR11-C/PR19-E 가 보지 않는 evidence" 만 PR21-L 의 관측 대상이다 — 그게 곧
**direct supporting evidence**.

## Evidence type modifier 규칙

```text
self._hint_evidence_types empty                                       → 1.0
direct supporting evidence 0 개                                       → 1.0
direct supporting evidence 1+ 개 AND 전부 hint set 포함               → 0.9
direct supporting evidence 1+ 개 AND 하나라도 hint set 밖             → 1.0
boost (modifier > 1.0)                                                → 영구 금지
```

`all([])` vacuous truth 함정: 직전 `if not direct: return 1.0` 가드로 차단.

## 닫힌 흐름 (PR21-L 추가분)

```text
Engine.__init__
  → self._hint_evidence_types: set[int] = set()  (PR21-L 추가 state)

register_hint_evidence_types(types)
  → self._hint_evidence_types.update(int(t) for t in types)  (idempotent, 누적)

add_evidence(claim_id, ..., evidence_type, strength)
  → self._evidences[evidence_id] = Evidence(...)  (PR1 unchanged, type 의미 미소유)

register_contradiction(claim_id, evidence_id)
  → self._contradictions[claim_id].add(evidence_id)  (PR7 unchanged)

compute_effective_confidence(claim_id)
  → _evidence_type_modifier_for_claim(claim_id) 호출 (신규)
       ├─ hint set empty → 1.0 (early-return, Sub-decision AE)
       ├─ direct supporting evidence 계산 (contradiction + resolved 제외)
       ├─ direct == [] → 1.0 (Sub-decision AB)
       └─ all-hint → 0.9, mixed/non-hint → 1.0 (Sub-decision AC)
  → 기존 6 modifier 와 곱셈 결합 (한 줄 추가)
  → ScoreValue 반환 (engine state 무변경)

to_snapshot()
  → "schema_version": 2 (PR21-L bump)
  → "hint_evidence_types": sorted(self._hint_evidence_types)  (deterministic list)

from_snapshot(snap)
  → _migrate_snapshot_to_current(snap)
       └─ v1 일 경우 _migrate_snapshot_v1_to_v2(snap) 적용
           ("hint_evidence_types": [] default 채움)
  → engine._hint_evidence_types = set(snap["hint_evidence_types"])
```

## 들어간 커밋 4

```text
90차 77f039e docs(contract): define evidence_type modifier MVP (§33)
91차 d41d4b6 test(core): lock evidence_type modifier invariants
92차 414c2c8 feat(engine): activate evidence_type modifier
93차 (이번) docs(dev): record PR21 evidence_type modifier MVP
```

## 주요 설계 결정

### Sub-decision AA — Direct evidence only (contradiction/resolved 제외)

`evidence_type_modifier` 는 **direct supporting evidence** 만 본다. PR21-L 의
구현은 다음 세 조건을 모두 만족해야 direct supporting evidence:

- `Evidence.claim_id == claim_id`
- `evidence.id` 가 `_contradictions[claim_id]` 에 포함되지 않음
- `evidence.id` 가 `_resolved_contradictions[claim_id]` 에 포함되지 않음

이유: PR11-C / PR19-E 가 이미 contradiction evidence 를 modifier 계산에 사용
중이며, PR21-L 이 같은 evidence 를 "supporting" 으로 다시 세면 modifier 의미가
겹친다. PR21-L 은 **PR11-C/PR19-E 가 보지 않는 evidence** 만 본다.

### Sub-decision AB — Direct evidence 0 개 → 1.0

기존 PR1~PR20-F 의 다수 테스트와 caller 코드는 evidence 없는 Claim 을 흔히
생성한다. PR21-L 이 "evidence 없음" 을 0.9 감쇠로 처리하면 회귀가 광범위
발생. **default behavior 는 비-disruptive.**

### Sub-decision AC — All-hint → 0.9

caller 가 명시적으로 등록한 hint type 만으로 받쳐진 Claim 만 감쇠. 한 개라도
hint set 밖 type 이 섞이면 "충분히 받친 Claim" 으로 간주 → 1.0.

추천 상수: `_EVIDENCE_TYPE_PENALTY_MODIFIER = 0.9` (PR20-F rule_stats 와 동일
강도 — 가장 약한 modifier 자리).

### Sub-decision AD — Boost 금지

```text
evidence_type_modifier ∈ {0.9, 1.0}
```

OBSERVED / DIRECT 계열 evidence 가 있어도 modifier 는 1.0 을 넘지 않는다.
PR11-D Sub-decision N / PR19-E Sub-decision E / PR20-F Sub-decision X 정신
일관. PR21-L 은 attenuation 만 한다.

### Sub-decision AE — Empty registration → 항상 1.0 (zero-config)

```text
caller 가 register_hint_evidence_types 를 호출하지 않으면
  self._hint_evidence_types == set()
  → 모든 Claim 에 evidence_type_modifier = 1.0
```

`if not self._hint_evidence_types: return 1.0` 가 _evidence_type_modifier_for_claim
helper 의 첫 가드. **vacuous truth 함정 (`all([])`)** 도 함께 차단.

PR1~PR20-F 호환 보존이 최우선. caller 가 PR21-L 의 register API 를 호출하지
않는 한 PR21-L 은 보호막 (정확히 1.0 modifier).

### Sub-decision AF — Framework 가 Evidence.type 의미를 소유하지 않음

```text
Evidence.type 은 caller-defined opaque int.
HINT 는 built-in enum 이 아니라 caller registration 결과.
```

영구 제약 (Sub-decision D 정신 보존):
- `types.py` 에 `EVIDENCE_TYPE_*` enum 추가 금지
- `__init__.py` 에 evidence type 카테고리 export 금지
- magic threshold (예: `type < 100` = HINT) 금지

PR21-L 의 가장 중요한 설계 결정. 이 원칙 덕에 framework 의 generic 성격이
보존된다 — RAG framework 는 caller domain 의미를 모르는 판단 엔진.

### Sub-decision AG — Snapshot round-trip 보존

`_hint_evidence_types` 는 engine state 이므로 `to_snapshot()` /
`from_snapshot()` round-trip 후 동일 복원.

- snapshot key: `"hint_evidence_types"`
- 값 형태: `sorted(self._hint_evidence_types)` (deterministic list, set 비결정성 회피)
- restore: `engine._hint_evidence_types = set(snap["hint_evidence_types"])`

### Sub-decision AH — schema_version 1 → 2 bump + migration

```python
_CURRENT_SNAPSHOT_SCHEMA_VERSION = 2
_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = frozenset({1, 2})

def _migrate_snapshot_v1_to_v2(snapshot):
    out = dict(snapshot)
    out["schema_version"] = 2
    out["hint_evidence_types"] = []
    return out
```

`_migrate_snapshot_to_current` 의 chain 자리에 v1 → v2 step 활성화. PR18-K 가
만든 migration framework 의 **첫 실제 활용** — compatibility preservation 정신
그대로.

- v1 snapshot 은 자동 migration 으로 hint 빈 set 복원 → 기존 caller 데이터
  무수정 호환
- input snapshot mutate 금지 (얕은 사본 + 키 추가)

### PR1~PR20-F 정합

- `types.py` 변경 0 — `Evidence.type` 은 PR1 시점부터 opaque int. PR21-L 은
  이를 read.
- `__init__.py` 변경 0 — public export 추가 없음 (`register_hint_evidence_types`
  는 Engine method 이므로 `from ragcore import Engine` 으로 접근)
- `rule_output.py` 변경 0 — Sub-decision D 영구 보존
- PR11-C freshness modifier 의미 — 변경 없음 (회귀 테스트 6.1 lookup-miss 검증)
- PR12-D gap modifier 의미 — 변경 없음 (회귀 테스트 6.2 검증)
- PR19-E count modifier 의미 — 변경 없음 (회귀 테스트 6.3 검증)
- PR20-F rule_stats modifier 의미 — 변경 없음 (회귀 테스트 6.4 검증)
- PR9-A `active_contradictions_for_claim` asc 동작 — 변경 없음
- PR10-A refute / PR11-B refute_by_freshness 동작 — 변경 없음
- PR18-K migration framework — chain 자리 활성화 (의미 보존)

### PR17 / PR18-K v1-pinned 테스트 자연 만료분 갱신

92차 schema bump 후 다음 4 개 테스트가 자연 만료 → v2 기준 명시 갱신:

| 파일:테스트 | 변경 |
|---|---|
| `test_engine_persistence.py::test_snapshot_has_schema_version_1` | → `..._is_two`, `assert == 2`. PR17 invariant ("schema_version 노출") 의미 보존, 절대값만 갱신. |
| `test_engine_snapshot_migration.py::test_current_snapshot_schema_version_is_one` | → `..._is_two`, `assert == 2`. PR18-K invariant ("constant 노출") 의미 보존. |
| `test_engine_snapshot_migration.py::test_version_2_currently_unsupported_raises_value_error` | → `test_version_3_unsupported_raises_value_error`. "미래 버전 = ValueError" invariant 는 v3 로 이전. |
| `test_engine_snapshot_migration.py::test_to_snapshot_outputs_schema_version_1` | → `..._version_2`, `assert == 2`. |

v3 unsupported 테스트를 살린 이유: "미래 unsupported version → ValueError"
invariant 자체는 PR21-L 이후에도 살아 있어야 한다 (다음 schema bump 진입점).

## 불변식 (테스트로 잠금)

§33.15 의 40 invariant. 91차에서 잠금, 92차 통과로 입증. 신규 테스트 파일은
48 테스트 (일부 invariant 가 2~3 테스트로 분해됨).

### Registration API (Sub-decision AF)
1. `register_hint_evidence_types` method 존재
2. list / tuple / frozenset / generator 모두 허용
3. 중복 idempotent (set 의미)
4. 여러 번 호출 시 set union 누적
5. 빈 iterable no-op
6. snapshot 직렬화는 sorted list (deterministic)

### Compatibility (Sub-decision AB / AE)
7. empty registration → 모든 Claim modifier 1.0
8. empty registration + direct evidence → 1.0
9. empty registration + no direct evidence → 1.0
10. hint 등록 + direct evidence 0 개 → 1.0
11. 다른 claim_id 의 evidence 무영향
12. contradiction evidence 는 direct supporting 으로 카운트하지 않음
13. resolved contradiction evidence 도 카운트하지 않음

### Hint-only penalty (Sub-decision AC)
14. 직접 evidence 1 개가 hint type → 0.9
15. 직접 evidence 여러 개 전부 hint → 0.9
16. mixed hint + non-hint → 1.0
17. single non-hint → 1.0
18. direct evidence 100 개 전부 hint → 0.9 (no boost)
19. `all([])` vacuous truth 차단 (direct == [] 시 1.0)

### Composition (status × freshness × gap × count × rule_stats × evidence_type)
20. refuted + hint-only → 0.0 (status dominate)
21. candidate + hint-only → base × 0.9
22. disputed + hint-only → base × 0.5 × 0.9 = base × 0.45
23. confirmed + active 1 (strength 0.8) + hint-only direct → base × 0.6 × 0.9 = 0.54
24. candidate + unresolved gap + hint-only → base × 0.8 × 0.9 = 0.72
25. candidate + active 2 + hint-only → base × 0.8 × 0.9 = 0.72
26. candidate + firing 1 + hint-only → base × 0.9 × 0.9 = 0.81
27. **7-modifier full composition (disputed + active 2 + gap + firing 1 + hint-only) → base × 0.15552**

### Snapshot schema v2 (Sub-decision AG / AH)
28. `to_snapshot()["schema_version"] == 2`
29. snapshot 에 `"hint_evidence_types"` 키 항상 존재
30. sorted list 직렬화 (deterministic)
31. empty registration → `[]` 직렬화
32. round-trip 후 `_hint_evidence_types` 그대로 복원
33. v1 snapshot 자동 migration → 빈 frozenset 복원
34. v1 migration 시 다른 필드 보존
35. `_CURRENT_SNAPSHOT_SCHEMA_VERSION == 2`
36. `_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS == {1, 2}`
37. `_migrate_snapshot_v1_to_v2` 가 input snapshot 을 mutate 하지 않음
38. unknown v99 여전히 raises

### No state mutation
39. `to_snapshot()` identical before/after compute
40. `_hint_evidence_types` unchanged after compute
41. `_lifecycle_seq` unchanged

### Regression boundaries (lookup miss / empty hint 기준)
42. PR11-C freshness modifier 의미 보존
43. PR12-D gap modifier 의미 보존
44. PR19-E count modifier 의미 보존
45. PR20-F rule_stats modifier 의미 보존

### Private constants / state
46. `_EVIDENCE_TYPE_PENALTY_MODIFIER` private (ragcore + ragcore.types 미노출)
47. `_hint_evidence_types` engine attribute private (types.py 미노출)
48. 기존 694 회귀 없음 (전체 통과로 입증)

## 테스트 결과

```text
90차 docs-only            : 694 passing
91차 test-first           : 신규 48 (26 fail + 22 pass), 기존 694 회귀 0
                            → 716 passed + 26 failed
92차 feat impl + v1-test  : 26/26 fail 정확히 pass 전환
                            + PR17/PR18-K v1-pinned 테스트 4 개 v2 기준 갱신
                            → 742 passed, 0 fail
93차 docs-only            : 742 passed, 0 fail 유지
```

## 변경 파일

| 파일 | 변경 | 차수 |
|---|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | +380 (§33 신규) | 90 |
| `tests/test_engine_evidence_type_modifier.py` | +655 (신규, 48 tests) | 91 |
| `ragcore/engine.py` | +110 / -15 (state + API + helper + compose + schema v2 + migration) | 92 |
| `tests/test_engine_persistence.py` | +3 / -2 (v1 → v2 단언 갱신) | 92 |
| `tests/test_engine_snapshot_migration.py` | +9 / -9 (3 개 테스트 v2/v3 기준 갱신) | 92 |
| `docs/dev/PR_021_EVIDENCE_TYPE_MODIFIER_MVP.md` | 신규 | 93 |

## 신규 테스트 그룹

```text
tests/test_engine_evidence_type_modifier.py
  TestEvidenceTypeRegistrationApi              (7 tests — Sub-decision AF)
  TestEvidenceTypeModifierCompatibility        (7 tests — AB/AE/AA contra/resolved)
  TestEvidenceTypeHintOnlyPenalty              (6 tests — AC/AD + all([]) trap)
  TestEvidenceTypeComposition                  (8 tests — 7-modifier composition)
  TestEvidenceTypeSnapshotSchemaV2             (11 tests — AG/AH + migration)
  TestEvidenceTypeNoStateMutationAndRegression (9 tests — read-only + PR11-C/PR12-D/PR19-E/PR20-F)
```

## 구현 요약 (engine.py)

```python
# Imports
from collections.abc import Iterable

# Private constants (module-level)
_EVIDENCE_TYPE_PENALTY_MODIFIER = 0.9
_CURRENT_SNAPSHOT_SCHEMA_VERSION = 2   # ← 1 에서 bump
_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = frozenset({1, 2})

# Engine state
self._hint_evidence_types: set[int] = set()

# Public API (Engine method)
def register_hint_evidence_types(self, types: Iterable[int]) -> None:
    self._hint_evidence_types.update(int(t) for t in types)

# Helper (Engine method)
def _evidence_type_modifier_for_claim(self, claim_id: int) -> float:
    if not self._hint_evidence_types:
        return 1.0
    contradicting = self._contradictions.get(claim_id, set())
    resolved = self._resolved_contradictions.get(claim_id, set())
    excluded = contradicting | resolved
    direct = [
        ev for ev in self._evidences.values()
        if ev.claim_id == claim_id and ev.id not in excluded
    ]
    if not direct:
        return 1.0
    if all(ev.type in self._hint_evidence_types for ev in direct):
        return _EVIDENCE_TYPE_PENALTY_MODIFIER
    return 1.0

# compute_effective_confidence 본문 +1 라인
evidence_type_modifier = self._evidence_type_modifier_for_claim(claim_id)

# ScoreValue 곱셈에 × evidence_type_modifier 추가
return ScoreValue(
    claim.base_confidence.value
    * status_modifier * freshness_modifier * gap_modifier
    * count_modifier * rule_stats_modifier
    * evidence_type_modifier
)

# Snapshot v1 → v2 migration step (module-level private)
def _migrate_snapshot_v1_to_v2(snapshot: dict) -> dict:
    out = dict(snapshot)
    out["schema_version"] = 2
    out["hint_evidence_types"] = []
    return out

# to_snapshot 에 한 줄 추가
"hint_evidence_types": sorted(self._hint_evidence_types),

# from_snapshot 에 한 줄 추가
engine._hint_evidence_types = set(snapshot["hint_evidence_types"])
```

## Out of Scope (PR21-L 외)

| 제외 | 이유 / 향후 |
|---|---|
| Built-in HINT / OBSERVED / DIRECT enum | Sub-decision AF 영구 |
| `Evidence.type` 정수 magic threshold (예: < 100 = HINT) | Sub-decision AF |
| Strict validation of registered evidence type values | MVP `int(t)` cast 사용, 별도 PR — caller 가 hint id 의미 소유 |
| OBSERVED / DIRECT 계열 boost (modifier > 1.0) | Sub-decision AD 영구 |
| `firing_count`-dependent / `strength`-dependent 함수 | binary 정신 |
| Threshold 값 조정 (단일 hint set → multi-class hint tiering) | MVP 잠금 |
| Relation graph traversal (간접 evidence 포함) | Sub-decision AA |
| Contradiction evidence 재사용 | Sub-decision AA — PR11-C / PR19-E 가 본다 |
| Resolved contradiction evidence 고려 | Sub-decision AA |
| `Evidence.strength` 재계산 | PR11-C 의 영역 |
| RuleStats outcome ratio (PR20-F Q / R 트랙) | 별도 PR |
| `lifecycle` 전이 / `refute` 정책 변경 | 본 PR 범위 밖 |
| `rule_output.py` 변경 | Sub-decision D 영구 |
| `register_hint_evidence_types` 명시적 삭제 API | MVP — caller restart 로 충분 |
| `unregister_hint_evidence_types` | 동일 |
| YAML rule schema 변경 | 본 PR 범위 밖 |
| Per-claim hint set override | engine-global 만 |
| Hint-class tiering (예: weak-hint=0.95 / strong-hint=0.85) | binary MVP |

## 다음 PR 후보

다음 트랙 후보 (사용자 결정 대기):

- **PR22 후보 G — superseded/retracted 상태**: types.py / __init__.py 손대야 함 (Sub-decision D 깨짐), 사용자 명시 승인 필요.
- **PR22 후보 J — multi-rule claim composition**: 하나의 Claim 이 여러 rule 에서 도출됐을 때 prior 합성 규칙 (max / mean / harmonic).
- **PR22 후보 M — gap severity tiering**: gap 의 critical / major / minor, gap_modifier 를 binary 0.8 에서 tiered 로 확장 (PR12-D 자연 후속).
- **PR22 후보 N — contradiction strength averaging**: count_modifier 를 N>=2 binary → average strength 기반 continuous (PR19-E 자연 후속).
- **PR22 후보 O — rule version pinning**: rule update 시 기존 claim 영향도 분석.
- **PR22 후보 P — external integration spec**: 외부 소비자 패키지 계약 정의 (docs 위주).
- **PR22 후보 Q — rule_stats outcome ratio modifier**: RuleStats outcome 역전파 mechanism 필요 (대규모).
- **PR22 후보 R — rule_stats observed_precision 사용**: `RuleStats.observed_precision` / `false_positive_rate` 를 modifier 에 반영.
- **PR22 후보 S — evidence_type strict validation**: PR21-L MVP `int(t)` cast OOS 였던 영역 (가장 작음).

PR21-L 의 자연 후속은 **S (evidence_type strict validation)** 또는 **G
(superseded/retracted, Sub-decision D 승인 필요)** 또는 **M (gap tiering)**.

## Spec Reference

- §33 (Effective confidence — evidence_type modifier, MVP — caller-registered, weak source-quality)
- §32 (Rule_stats modifier MVP, PR20-F)
- §31 (Count modifier MVP, PR19-E)
- §30 (Snapshot migration framework, PR18-K) — **첫 실제 활용**
- §29 (Persistence MVP, PR17)
- §28 (Gap modifier MVP, PR12-D)
- §26 (Evidence freshness modifier, PR11-C)
- §24 (Effective confidence, PR11-D)

## How to Run

```bash
# PR21-L invariants 만
pytest tests/test_engine_evidence_type_modifier.py -v

# 전체
pytest -q
```

## Result

```text
Before PR21-L (main = 4496554):
  effective = base × status × freshness × gap × count × rule_stats
  694 passing
  snapshot schema_version = 1

After PR21-L (main = <new sha>):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  742 passing, 0 fail
  snapshot schema_version = 2 (v1 → v2 migration 자동 적용)
```

6-modifier composition (PR20-F) → 7-modifier composition (PR21-L) 진화 완료.
PR18-K 가 만들어둔 snapshot migration framework 가 PR21-L 에서 **첫 실제 활용**
됨 (compatibility preservation, not re-judgment 정신 그대로).
