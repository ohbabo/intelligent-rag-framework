# PR #022 — Strict Hint Evidence Type Registration (PR22-S)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/evidence-type-strict-validation` → `main`
> Base: `0127741` (PR21-L merged)
> Tests: 780 passing (local)

## Summary

PR22-S closes the evidence_type modifier MVP by hardening the registration
boundary of `Engine.register_hint_evidence_types`.

The effective confidence formula remains unchanged:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
```

This PR adds strict validation to `register_hint_evidence_types` **without
changing snapshot schema, public exports, lifecycle, or modifier semantics**.

## PR22-S 의 한 줄 정의

> **PR22-S 는 evidence_type taxonomy 를 만드는 PR 이 아니다.
> PR22-S 는 `register_hint_evidence_types` API 의 입력 계약을 엄격하게
> 만드는 PR 이다. caller 가 "이 type id 는 hint 다" 라고 명시적 int 로
> 전달해야 한다 — implicit cast / partial mutation / non-iterable 모두
> 거부.**

PR21-L Sub-decision AF 정신 그대로:

```text
framework 는 어떤 type id 가 HINT 인지 결정하지 않는다.
caller 가 등록한 int id 만 받는다.
다만 등록 API 는 int 아닌 값을 조용히 cast 하지 않는다.
```

## 핵심 명제 (§34.2)

```text
Strict validation protects the registration boundary,
not the meaning of Evidence.type.

No implicit casting. No partial mutation. No taxonomy ownership.
```

한국어:

```text
strict validation 은 등록 경계를 보호하는 것이지,
Evidence.type 정수값의 의미를 framework 가 해석하는 것이 아니다.

암묵적 형 변환 없음. 부분 mutation 없음. taxonomy 소유 없음.
```

## Why (변경 필요성)

PR21-L MVP 구현은 다음과 같았다:

```python
self._hint_evidence_types.update(int(t) for t in types)
```

이 한 줄 때문에 다음 silent registration 이 모두 통과했다:

```text
register_hint_evidence_types(["1"])     → 1 등록 (int("1") = 1)
register_hint_evidence_types([1.0])     → 1 등록 (int(1.0) = 1)
register_hint_evidence_types([b"1"])    → 1 등록 (int(b"1") = 1)
register_hint_evidence_types([True])    → 1 등록 (int(True) = 1)
register_hint_evidence_types([False])   → 0 등록 (int(False) = 0)
register_hint_evidence_types("12")      → {1, 2} 등록 (str iterable)
register_hint_evidence_types(b"12")     → {49, 50} 등록 (bytes iterable)
register_hint_evidence_types([1, None]) → {1} partial mutation (1 등록 후 TypeError)
```

이건 PR21-L 의 철학 (Sub-decision AF — Evidence.type 의미는 framework 가
소유하지 않음) 과 살짝 충돌한다. caller 가 명시적 int 를 줘야 하는데,
implicit cast 가 그 경계를 흐리게 만든다.

PR22-S 는 이 경계를 명시적으로 닫는다.

## 6-Modifier ↔ 7-Modifier (composition 영향 없음)

```python
effective_confidence(claim) = (
    base_confidence
    × status_modifier(claim.status)              # PR11-D
    × freshness_modifier(claim_id)               # PR11-C
    × gap_modifier(claim_id)                     # PR12-D
    × count_modifier(claim_id)                   # PR19-E
    × rule_stats_modifier(claim)                 # PR20-F
    × evidence_type_modifier(claim_id)           # PR21-L (PR22-S 변경 없음)
)
```

| modifier | PR | 형태 | 강도 |
|---|---|---|---|
| status_modifier | PR11-D | 4 값 (1.0/1.0/0.5/0.0) | 강 |
| freshness_modifier | PR11-C | continuous | 중 |
| gap_modifier | PR12-D | binary (0.8 / 1.0) | 약 |
| count_modifier | PR19-E | binary (0.8 / 1.0) | 약 |
| rule_stats_modifier | PR20-F | binary (0.9 / 1.0) | 매우 약 |
| evidence_type_modifier | PR21-L | binary (0.9 / 1.0) | 매우 약 |

PR22-S 는 위 표의 어떤 행도 바꾸지 않는다. **registration boundary 만 강화.**

## What changed

```python
def register_hint_evidence_types(self, types: Iterable[int]) -> None:
    if isinstance(types, (str, bytes)):
        raise TypeError(
            "hint evidence types must be an iterable of int values, "
            f"not {type(types).__name__}"
        )
    validated: set[int] = set()
    for value in types:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                "hint evidence type values must be int values, "
                f"not {type(value).__name__}"
            )
        validated.add(value)
    self._hint_evidence_types.update(validated)
```

- `str` / `bytes` 컨테이너는 함수 입구에서 거부
- `bool` 값은 `int` subclass 임에도 거부 (검사 순서 — bool 먼저)
- 순수 `int` element 만 허용
- 검증은 임시 `validated` set 으로 먼저
- engine state 는 모든 검증 통과 후에만 mutate (all-or-nothing)

## What did NOT change

- `ragcore/types.py`: 변경 0
- `ragcore/__init__.py`: 변경 0
- `ragcore/rule_output.py`: 변경 0
- snapshot `schema_version`: `2` 유지
- `_EVIDENCE_TYPE_PENALTY_MODIFIER`: `0.9` 유지
- `_evidence_type_modifier_for_claim` helper: 변경 0
- effective confidence formula: 변경 0
- public namespace: 신규 export 0
- lifecycle / freshness / gap / count / rule_stats modifier: 의미 변경 0
- snapshot 직렬화 형식: 변경 0 (`hint_evidence_types` 그대로 sorted list)

## 들어간 커밋 4

```text
94차 03f4ede docs(contract): define evidence_type registration strict validation (§34)
95차 c2aac99 test(core):     lock evidence_type registration strict validation invariants
96차 6e6f6eb feat(engine):   enforce strict hint evidence type registration
97차 (이번)   docs(dev):      record PR22 strict hint validation MVP
```

## 주요 설계 결정

### Sub-decision AI — No implicit casting

`register_hint_evidence_types` 는 `int(t)` cast 를 하지 않는다.

이유: `Evidence.type` 은 caller-defined int. registration 도 caller 가
명시적 int 를 전달해야 한다. cast 는 caller 의 의도를 framework 가 추측하는
행위 — Sub-decision AF (framework 가 의미를 소유하지 않음) 정신과 어긋남.

### Sub-decision AJ — Only `int` (bool 거부)

```python
if isinstance(value, bool) or not isinstance(value, int):
    raise TypeError(...)
```

검사 순서가 중요: `bool` 검사를 `int` 검사 **이전에**. Python 에서
`isinstance(True, int) == True` 이므로 단순 `isinstance(value, int)` 만으로는
bool 을 못 거른다.

이유: `True`/`False` 를 hint type id 로 받는 것은 명시적 int 계약을 흐림.

### Sub-decision AK — 값 범위 제한 없음

음수 / 0 / 큰 정수 모두 허용. `Evidence.type` 은 opaque caller-defined int.
framework 가 "0 은 안 된다", "양수만 된다", "최대값 제한" 같은 도메인 제약을
넣는 순간 다시 type 의미를 소유하기 시작 — Sub-decision AF 위반.

→ **PR22-S 는 타입 검증만 한다. 값 의미 검증은 하지 않는다.**

### Sub-decision AL — All-or-nothing update

```python
validated: set[int] = set()
for value in types:
    ...validate...
    validated.add(value)
self._hint_evidence_types.update(validated)  # 모든 검증 통과 후에만
```

PR21-L 의 `update(int(t) for t in types)` 는 generator 를 lazy 하게 소비
하면서 valid element 를 먼저 set 에 add 한 뒤 invalid 에서 TypeError 가
발생했다. 따라서 실패 시점에 이미 일부가 등록되어 있었다.

PR22-S 는 임시 `validated` set 으로 모든 검증 완료 후에만 union → atomic.

### Sub-decision AM — Non-iterable + str/bytes 컨테이너 거부

```python
if isinstance(types, (str, bytes)):
    raise TypeError(...)
```

API signature 는 `Iterable[int]`. `str` / `bytes` 는 technically iterable
이지만 API 입력 컨테이너로 거부.

- `"12"` → 만약 그냥 iterate 하면 char `'1'`, `'2'` → AJ 가 비-int 로 reject
  되긴 하지만, intent 가 명백히 잘못이므로 명시적 거부가 더 깨끗
- `b"12"` → byte 값 49, 50 (int!) 이라 AJ 만으로는 통과해버림 → 컨테이너
  자체를 차단해야 함

Non-iterable input (raw int / None / float) 은 `for value in types:` 자체에서
TypeError 자연 발생 — 별도 가드 불필요.

### Sub-decision AN — Snapshot schema bump 없음

```text
_CURRENT_SNAPSHOT_SCHEMA_VERSION = 2  (그대로)
_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = frozenset({1, 2})  (그대로)
```

PR22-S 는 engine state shape 를 바꾸지 않는다. snapshot 호환성 영향 없음
→ schema bump 불필요. PR18-K 정신: 의미 있는 변화 때만 bump.

### PR1~PR21-L 정합

- `types.py` 변경 0 — Sub-decision D 영구 보존
- `__init__.py` 변경 0 — public export 추가 없음
- `rule_output.py` 변경 0
- PR21-L Sub-decision AA~AH 의미 — 변경 없음
- PR11-C / PR12-D / PR19-E / PR20-F modifier 의미 — 변경 없음
- PR17 round-trip identity — 보존
- PR18-K migration framework — 변경 없음 (v1 → v2 step 그대로)
- snapshot 직렬화 결정성 — 보존 (여전히 sorted list)

## 불변식 (테스트로 잠금)

§34.13 의 invariants. 95차에서 잠금, 96차 통과로 입증. 신규 테스트 파일
38 tests (7 클래스).

### Registration API contract (allowed inputs)
1. `list[int]` 허용
2. `tuple[int]` 허용
3. `set[int]` 허용
4. `frozenset[int]` 허용
5. `generator[int]` 허용
6. zero 허용 (Sub-decision AK)
7. negative ints 허용 (AK)
8. very large int (10^18) 허용 (AK)
9. empty iterable no-op
10. duplicates idempotent
11. accumulation across calls (set union)

### Implicit cast rejection (Sub-decision AI)
12. `["1"]` (str element) → TypeError
13. `[1.0]` (float element) → TypeError
14. `[b"1"]` (bytes element) → TypeError
15. `[None]` → TypeError
16. `[object()]` → TypeError

### Bool rejection (Sub-decision AJ)
17. `[True]` → TypeError
18. `[False]` → TypeError
19. `[1, True]` → TypeError + 1 미등록 (all-or-nothing)

### str / bytes 컨테이너 거부 (Sub-decision AM edge)
20. `"1"` (single-digit str) → TypeError
21. `"12"` (multi-char str) → TypeError
22. `b"\x01"` (single-byte) → TypeError
23. `b"12"` (multi-byte) → TypeError

### Non-iterable (Sub-decision AM)
24. raw int → TypeError
25. None → TypeError
26. raw float → TypeError

### All-or-nothing (Sub-decision AL)
27. pre-existing `{7}` + `[1, "2"]` 호출 → TypeError, set 그대로 `{7}`
28. pre-existing `{7}` + `[1, True]` 호출 → TypeError, set 그대로 `{7}`
29. empty + `[1, "2"]` → TypeError, set empty 유지
30. generator yields `1, None, 3` → TypeError, set empty (partial mutation 차단)

### Snapshot / formula 영향 없음 (Sub-decision AN)
31. `to_snapshot()["schema_version"] == 2` 유지
32. empty registration → snapshot `"hint_evidence_types": []` 유지
33. valid registration round-trip 보존
34. invalid registration → snapshot 변경 없음
35. PR21-L hint-only direct evidence → effective `base × 0.9` 유지
36. empty hint → modifier 1.0 유지
37. `_EVIDENCE_TYPE_PENALTY_MODIFIER == 0.9` 유지
38. public namespace 신규 export 0

## 테스트 결과

```text
94차 docs-only            : 742 passing
95차 test-first           : 신규 38 (15 fail + 23 pass), 기존 742 회귀 0
                            → 765 passed + 15 failed
96차 feat impl            : 15/15 fail 정확히 pass 전환
                            → 780 passed, 0 fail
97차 docs-only            : 780 passed, 0 fail 유지
```

### 95차 fail-to-pass mapping

| 차단 영역 | Fail 수 | 96차 메커니즘 |
|---|---|---|
| implicit cast rejection | 3 | `isinstance(value, int)` 가드 |
| bool rejection | 3 | `isinstance(value, bool)` 우선 검사 |
| str / bytes container rejection | 4 | 함수 입구 `isinstance(types, (str, bytes))` 가드 |
| all-or-nothing partial mutation prevention | 5 | `validated` temp set + 검증 완료 후에만 union |

## 변경 파일

| 파일 | 변경 | 차수 |
|---|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | +360 (§34 신규) | 94 |
| `tests/test_engine_evidence_type_strict_validation.py` | +386 (신규, 38 tests) | 95 |
| `ragcore/engine.py` | +35 / -13 (`register_hint_evidence_types` 본문만) | 96 |
| `docs/dev/PR_022_STRICT_HINT_VALIDATION_MVP.md` | 신규 | 97 |

## 신규 테스트 그룹

```text
tests/test_engine_evidence_type_strict_validation.py
  TestStrictValidationAllowedInputs              (11 tests — AJ allowed + AK + accumulation)
  TestStrictValidationRejectsImplicitCast        (5 tests — AI)
  TestStrictValidationRejectsBool                (3 tests — AJ bool trap + all-or-nothing)
  TestStrictValidationRejectsStringContainer     (4 tests — AM edge: str/bytes container)
  TestStrictValidationRejectsNonIterable         (3 tests — AM: raw int/None/float)
  TestStrictValidationAllOrNothing               (4 tests — AL: partial mutation prevention)
  TestStrictValidationSnapshotAndFormulaUnchanged (8 tests — AN: snapshot/formula/exports)
```

## Out of Scope (PR22-S 외)

| 제외 | 이유 / 향후 |
|---|---|
| Built-in `EVIDENCE_TYPE_HINT` enum 도입 | Sub-decision AF 영구 |
| `Evidence.type` 값 의미 해석 / 도메인 제약 | Sub-decision AK — taxonomy 소유 금지 |
| Positive-only / 0 금지 / 범위 제한 | Sub-decision AK |
| `evidence_type_modifier` 공식 / 강도 변경 | 본 PR 범위 밖 |
| Snapshot schema v3 bump | Sub-decision AN |
| Snapshot 직렬화 형식 변경 | Sub-decision AN |
| `unregister_hint_evidence_types` 명시적 삭제 API | MVP 외 |
| `clear_hint_evidence_types` | 동일 |
| Per-claim hint set override | engine-global 만 |
| Relation graph traversal | PR21-L AA 영구 |
| Contradiction evidence 재사용 | PR21-L AA |
| OBSERVED / DIRECT boost | PR21-L AD 영구 |
| Type별 weight table (hint-tiering) | binary MVP 유지 |
| RuleStats outcome ratio (Q/R 트랙) | 별도 PR |
| `types.py` / `__init__.py` / `rule_output.py` 변경 | Sub-decision D 영구 |
| Strict validation 을 `Evidence.type` 등록 path 가 아닌 다른 path 로 확대 | 본 PR 범위 밖 |

## Design note

This PR does not make evidence_type scoring stronger.
It makes evidence_type registration **safer**.

The modifier remains weak and supplemental (0.9 / 1.0 그대로).
The registration boundary is strict because `Evidence.type` is a numeric
signal, and silent coercion would make later scoring / audit behavior
ambiguous.

## 다음 PR 후보

PR22-S 닫음 후 PR23+ 후보 (사용자 결정 대기):

- **PR23 후보 M — gap severity tiering**: gap_modifier 를 binary 0.8 → tiered (PR12-D 자연 후속).
- **PR23 후보 N — contradiction strength averaging**: count_modifier 를 N>=2 binary → average strength 기반 continuous (PR19-E 자연 후속).
- **PR23 후보 G — superseded/retracted 상태**: types.py / __init__.py 손대야 함, **사용자 명시 승인 필요**.
- **PR23 후보 J — multi-rule claim composition**: prior 합성 규칙.
- **PR23 후보 O — rule version pinning**: rule update 시 claim 영향도.
- **PR23 후보 P — external integration spec**: 외부 소비자 패키지 계약.
- **PR23 후보 Q — rule_stats outcome ratio**: claim lifecycle 결과 역전파 (대규모).
- **PR23 후보 R — rule_stats observed_precision 사용**: 기존 필드를 modifier 에 반영.

권고: **M (gap severity tiering, PR12-D 자연 후속)** 또는 **N (count strength averaging, PR19-E 자연 후속)**.

## Spec Reference

- §34 (Evidence_type registration strict validation, PR22-S)
- §33 (Evidence_type modifier MVP, PR21-L)
- §32 (Rule_stats modifier MVP, PR20-F)
- §31 (Count modifier MVP, PR19-E)
- §30 (Snapshot migration framework, PR18-K) — 무영향
- §29 (Persistence MVP, PR17)
- §28 (Gap modifier MVP, PR12-D)
- §26 (Evidence freshness modifier, PR11-C)
- §24 (Effective confidence, PR11-D)

## How to Run

```bash
# PR22-S invariants 만
pytest tests/test_engine_evidence_type_strict_validation.py -v

# 전체
pytest -q
```

## Result

```text
Before PR22-S (main = 0127741):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  742 passing
  register_hint_evidence_types: int(t) implicit cast 통과

After PR22-S (main = <new sha>):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  (formula unchanged)
  780 passing, 0 fail
  register_hint_evidence_types: strict validation + all-or-nothing
```

7-modifier composition formula 보존. evidence_type registration boundary
강화. **PR22-S 의 본질은 scoring 정책 변경이 아니라 evidence_type registration
boundary 를 닫은 것이다.**
