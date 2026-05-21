# PR #025 — Hint Evidence Type Deregistration MVP (PR25-T)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/hint-evidence-type-deregistration-mvp` → `main`
> Base: `7114b1a` (PR24-N merged)
> Tests: 921 passing (local)

## Summary

PR25-T adds deregistration APIs for runtime hint evidence type control:

```python
unregister_hint_evidence_types(types: Iterable[int]) -> None
clear_hint_evidence_types() -> None
```

This PR does **not** define an `Evidence.type` taxonomy. It only completes
the operational boundary around the existing hint evidence type set:
`register → unregister → clear`.

The effective confidence formula shape remains **unchanged**:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
```

The `evidence_type_modifier` body, strength (0.9), formula, and snapshot
schema are all unchanged. PR25-T is purely a boundary-completion PR.

## PR25-T 의 한 줄 정의

> **PR25-T 는 Evidence.type taxonomy 를 만드는 PR 이 아니다.**
> **PR25-T 는 hint evidence type set 의 운영 경계를**
> **`register / unregister / clear` 로 닫는 PR 이다.**

PR23-M (gap binary → tier) / PR24-N (count binary → continuous) 이 modifier
강도 정제 PR 이었던 것과 달리, PR25-T 는 **API 완결 PR**. modifier 의미 /
강도 / 공식 모두 변경 없음.

## 핵심 명제 (§37.2)

```text
Deregistration is the inverse of registration, not a redefinition.
The framework still does not own Evidence.type semantics —
caller decides what to put in or take out.
```

한국어:

```text
Deregistration 은 registration 의 역연산이지, 의미의 재정의가 아니다.
framework 는 여전히 Evidence.type 정수의 의미를 소유하지 않는다 —
caller 가 hint set 에 무엇을 넣고 뺄지 결정한다.
```

추가 명제:

```text
Taxonomy ownership stays outside the framework.
The framework owns only strict boundary validation and live modifier application.
```

대조:

```text
PR21-L: register(types) — caller-registered hint set 도입, modifier 정의
PR22-S: register strict validation — implicit cast / partial mutation 차단
PR25-T: unregister(types) + clear() — set 조작 API 완결, validation 공유
```

## API surface 완결

```python
# 기존 (PR21-L + PR22-S, 외부 동작 변경 없음 — Sub-decision BJ)
register_hint_evidence_types(types: Iterable[int]) -> None

# 신규 (PR25-T)
unregister_hint_evidence_types(types: Iterable[int]) -> None
clear_hint_evidence_types() -> None

# 신규 private helper (Sub-decision BD — register / unregister 공유)
_validate_hint_evidence_type_values(types) -> set[int]
```

PR21-L → PR22-S → PR25-T 누적으로 hint evidence type set 의 caller-facing
API 가 완결됨:
- 등록 (PR21-L)
- 등록 시 strict validation (PR22-S)
- 해제 / 초기화 + 양방향 strict 공유 (PR25-T)

## 7-Modifier Composition (formula shape 보존)

```python
effective_confidence(claim) = (
    base_confidence                              # PR1
    × status_modifier(claim.status)              # PR11-D
    × freshness_modifier(claim_id)               # PR11-C
    × gap_modifier(claim_id)                     # PR12-D + PR23-M
    × count_modifier(claim_id)                   # PR19-E + PR24-N
    × rule_stats_modifier(claim)                 # PR20-F
    × evidence_type_modifier(claim_id)           # PR21-L + PR22-S + PR25-T (API 만 확장)
)
```

| modifier | PR | 형태 | 강도 | PR25-T 영향 |
|---|---|---|---|---|
| status_modifier | PR11-D | 4 값 | 강 | — |
| freshness_modifier | PR11-C | continuous | 중 | — |
| gap_modifier | PR12-D + PR23-M | tier | 약 (floor 0.7) | — |
| count_modifier | PR19-E + PR24-N | continuous | 약 (floor 0.75) | — |
| rule_stats_modifier | PR20-F | binary | 매우 약 | — |
| **evidence_type_modifier** | **PR21-L+PR22-S+PR25-T** | **binary** | **매우 약** | **API surface 만 확장** |

PR25-T 후 modifier 강도 분포 변경 없음.

## 닫힌 흐름 (PR25-T 추가분)

```text
Engine 의 hint evidence type 운영 흐름:

register_hint_evidence_types(types)
  → _validate_hint_evidence_type_values(types) → validated set
  → self._hint_evidence_types.update(validated)
  → (PR21-L + PR22-S 그대로, Sub-decision BJ)

unregister_hint_evidence_types(types)  ← 신규
  → _validate_hint_evidence_type_values(types) → validated set (BD strict 공유)
  → self._hint_evidence_types.difference_update(validated)
  → (BE 자연: 없는 type 제거 시 no-op)
  → (BF all-or-nothing: validation 실패 시 set mutation 0)

clear_hint_evidence_types()  ← 신규
  → self._hint_evidence_types.clear()
  → (BG always no-op safe, input 없음, TypeError 절대 raise 안 함)

compute_effective_confidence(claim_id)
  → _evidence_type_modifier_for_claim(claim_id) 호출 (PR21-L 본문 변경 없음)
       → if not self._hint_evidence_types: return 1.0  (PR21-L Sub-decision AE)
       → ... (live read of _hint_evidence_types, Sub-decision BI 자연 적용)

→ unregister/clear 직후 다음 compute 호출에서 modifier 즉시 반영
```

## 들어간 커밋 4

```text
106차  e70c368  docs(contract): define hint evidence type deregistration MVP (§37)
107차  4057bf0  test(core):     lock hint evidence type deregistration invariants
108차  046df5a  feat(engine):   add hint evidence type deregistration
109차  (이번)   docs(dev):      record hint evidence type deregistration MVP
```

각 차수 commit message body 는 PR19 패턴 자세한 본문 — `feedback_commit_message_body.md` 적용.
각 차수 commit 직후 즉시 push → PR #25 차수별 갱신 — `feedback_pr_cycle_push.md` 적용 (PR cycle 신규 패턴 2차 PR).

## 주요 설계 결정

### Sub-decision BC — API surface = unregister + clear

신규 API 정확히 2 개:
- `unregister_hint_evidence_types(types)` — 특정 type id 들을 hint set 에서 제거
- `clear_hint_evidence_types()` — hint set 을 비움

배제:
- `replace_hint_evidence_types(types)` — register + clear 조합으로 표현 가능
- `is_registered_hint_evidence_type(type_id)` — 외부 query API 는 별도 PR
- `list_hint_evidence_types()` — snapshot 으로 이미 접근 가능

이유: 최소 API 표면. register / unregister / clear 3 동사로 set 조작 완결.

### Sub-decision BD — Unregister validation = register 와 동일 strict

PR22-S Sub-decision AI~AM 와 **동일한** strict validation:
- no implicit casting (AI)
- int only, bool 거부 (AJ)
- 값 범위 제한 없음 (AK)
- all-or-nothing (AL)
- non-iterable + str/bytes 컨테이너 거부 (AM)

코드 차원 보장: PR22-S 본문을 `_validate_hint_evidence_type_values` private
helper 로 추출 → register / unregister 가 같은 helper 호출. 두 메서드의
validation 의미가 코드 구조 차원에서 자동 일치.

### Sub-decision BE — Unregister missing type = no-op

```text
register([1, 2]) + unregister([3]) → {1, 2} (no-op)
unregister([99]) on empty set → empty 그대로
unregister([1, 99]) when only 1 registered → {} (1 만 제거, 99 는 no-op)
```

`set.difference_update` 의 자연 의미. `KeyError` 없음 — caller 가 "이 type 이
등록되어 있는지" 모르고 호출해도 안전.

### Sub-decision BF — Unregister all-or-nothing

PR22-S Sub-decision AL 정신 동일하게 양방향 보장:

```text
register([1, 2]) + unregister([3, "4"]) → TypeError, hint set 그대로 {1, 2}
register([7]) + unregister([1, True]) → TypeError, hint set 그대로 {7}
```

구현: helper 가 검증 완료 후에만 validated set 반환. `difference_update` 는
검증된 set 으로만 실행 → partial mutation 불가능.

### Sub-decision BG — Clear 는 항상 no-op safe

```python
def clear_hint_evidence_types(self) -> None:
    self._hint_evidence_types.clear()
```

특징:
- input 없음 → validation 불필요
- 빈 set 에서도 no-op
- 반복 호출 가능
- TypeError 절대 raise 안 함

### Sub-decision BH — Snapshot schema bump 없음

```text
_CURRENT_SNAPSHOT_SCHEMA_VERSION = 2  (그대로)
_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = frozenset({1, 2})  (그대로)
```

PR25-T 는 engine state shape 를 바꾸지 않는다:
- `_hint_evidence_types: set[int]` 그대로
- snapshot 직렬화 `sorted list` 그대로
- v1 → v2 migration step 그대로 (PR21-L 도입분)

### Sub-decision BI — evidence_type modifier 공식 변경 없음

`_evidence_type_modifier_for_claim` 본문 변경 0. PR21-L Sub-decision AE 의
zero-config default (empty hint → 1.0) 가 `clear()` 호출 후에도 자연 적용.
unregister / clear 가 `_hint_evidence_types` 를 비우면 다음
`compute_effective_confidence` 호출 시 modifier 자동으로 1.0.

→ modifier 본문 변경 0. 즉시 반영은 state 변화 결과로 자연 발생.

### Sub-decision BJ — Register 외부 동작 변경 없음

`register_hint_evidence_types` 의 **외부 관찰 가능한 동작** 은 변경 없음:
- 같은 input → 같은 hint set 상태
- 같은 invalid input → 같은 TypeError
- snapshot 직렬화 형식 동일
- PR22-S 의 strict validation 의미 그대로

**내부 구현만** helper 호출로 교체:

```python
# Before (PR22-S, 본문 직접)
def register_hint_evidence_types(self, types: Iterable[int]) -> None:
    if isinstance(types, (str, bytes)): raise TypeError(...)
    validated: set[int] = set()
    for value in types:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(...)
        validated.add(value)
    self._hint_evidence_types.update(validated)

# After (PR25-T, helper 호출)
def register_hint_evidence_types(self, types: Iterable[int]) -> None:
    self._hint_evidence_types.update(
        self._validate_hint_evidence_type_values(types)
    )
```

PR22-S 가 잠근 38 invariants 모두 회귀 0.

## 구현 요약 (engine.py)

```python
# Private helper (PR22-S 본문 추출 — Sub-decision BD 코드 차원 보장)
def _validate_hint_evidence_type_values(self, types: Iterable[int]) -> set[int]:
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
    return validated

# 기존 (Sub-decision BJ — 외부 동작 변경 0)
def register_hint_evidence_types(self, types: Iterable[int]) -> None:
    self._hint_evidence_types.update(
        self._validate_hint_evidence_type_values(types)
    )

# 신규 (Sub-decision BC/BD/BE/BF)
def unregister_hint_evidence_types(self, types: Iterable[int]) -> None:
    self._hint_evidence_types.difference_update(
        self._validate_hint_evidence_type_values(types)
    )

# 신규 (Sub-decision BG)
def clear_hint_evidence_types(self) -> None:
    self._hint_evidence_types.clear()
```

`compute_effective_confidence` 본문 — 변경 0.
`_evidence_type_modifier_for_claim` 본문 — 변경 0.
다른 modifier helper / state / snapshot — 모두 변경 0.

## 불변식 (테스트로 잠금)

신규 테스트 파일 `tests/test_engine_hint_evidence_type_deregistration.py` —
10 클래스, 50 tests, 622 라인.

### TestHintEvidenceTypeUnregisterBasic (6) — Sub-decision BE
- `unregister_hint_evidence_types` 메서드 존재
- single registered type 제거
- multiple registered 부분 제거
- missing type → no-op
- empty iterable → no-op
- duplicate idempotent

### TestHintEvidenceTypeUnregisterStrictValidation (9) — Sub-decision BD
- str element → TypeError
- float element → TypeError
- bytes element → TypeError
- None element → TypeError
- True / False → TypeError
- str container → TypeError
- bytes container → TypeError
- raw int (non-iterable) → TypeError

### TestHintEvidenceTypeUnregisterAllOrNothing (4) — Sub-decision BF
- mixed invalid → prefix 미제거
- bool invalid → mutation 0
- float invalid → mutation 0
- prior register survives failed unregister

### TestHintEvidenceTypeClear (5) — Sub-decision BG
- `clear_hint_evidence_types` 메서드 존재
- register 후 clear → empty
- empty set clear → no-op
- 반복 clear → no-op
- clear 가 다른 state 건드리지 않음

### TestHintEvidenceTypeModifierImmediateReflection (4) — Sub-decision BI
- unregister 후 modifier 1.0 즉시 반영
- 부분 unregister → 남은 hint type penalty 유지
- clear 후 modifier 1.0
- unregister 는 evidence_type modifier 만 변경 (다른 modifier 무영향)

### TestHintEvidenceTypeDeregistrationSnapshot (5) — Sub-decision BH
- schema_version == 2 유지
- unregister 후 sorted list 직렬화
- clear 후 빈 list
- round-trip after unregister 보존
- round-trip after clear 보존

### TestHintEvidenceTypeRegisterBehaviorPreserved (3) — Sub-decision BJ
- accumulation 보존
- duplicate idempotence 보존
- strict validation all-or-nothing 보존

### TestHintEvidenceTypeDeregistrationComposition (3) — Sub-decision BI
- full composition after unregister
- full composition after clear
- formula without deregistration unchanged

### TestHintEvidenceTypeDeregistrationPublicNamespace (3) — Sub-decision D
- ragcore 에 built-in HINT enum 부재
- types.py 에 HINT enum 부재
- Engine method 가 module-level export 아님

### TestHintEvidenceTypeDeregistrationRegressionBoundaries (8)
- PR21-L evidence_type modifier 보존
- PR22-S strict validation 보존
- PR23-M gap modifier 보존
- PR24-N count strength averaging 보존
- PR9-A active_contradictions asc 보존
- PR10-A refute / PR11-B refute_by_freshness 보존
- PR17 round-trip identity 보존

## 테스트 결과

```text
106차 docs-only            : 871 passing
107차 test-first           : 신규 50 (34 fail + 16 pass), 기존 871 회귀 0
                            → 887 passed + 34 failed
108차 feat impl            : 34/34 fail 정확히 pass 전환
                            → 921 passed, 0 fail
109차 docs-only            : 921 passed, 0 fail 유지
```

### 107차 fail-to-pass mapping (34 fail → 34 pass)

| 차단 영역 | Fail 수 | 108차 메커니즘 |
|---|---:|---|
| `unregister_hint_evidence_types` 부재 (AttributeError) | 18 | helper 공유 + `difference_update` |
| `clear_hint_evidence_types` 부재 | 4 | `set.clear` |
| Immediate modifier reflection | 4 | `_evidence_type_modifier_for_claim` body 변경 0, live read |
| Snapshot after unregister/clear | 4 | engine state 변경 자동 직렬화 |
| Composition full (unregister/clear 후) | 2 | 모두 라이브 |
| API existence checks | 2 | 메서드 추가 |

### Pass 16개 (이미 보존)

- Snapshot schema v2 유지 (1)
- Register 외부 동작 보존 (3) — PR22-S 의미 그대로
- Composition without deregistration (1) — register 만 사용 시 동작 동일
- Public namespace (3) — types.py / __init__.py / rule_output.py 변경 없음
- Regression boundaries (8) — PR21-L / PR22-S / PR23-M / PR24-N / PR9-A / PR10-A / PR11-B / PR17 모두 보존

## 변경 파일

| 파일 | 변경 | 차수 |
|---|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | +399 (§37 신규) | 106 |
| `tests/test_engine_hint_evidence_type_deregistration.py` | +622 (신규, 50 tests) | 107 |
| `ragcore/engine.py` | +76 / -22 (helper 추출 + register 본문 교체 + unregister + clear) | 108 |
| `docs/dev/PR_025_HINT_EVIDENCE_TYPE_DEREGISTRATION_MVP.md` | 신규 | 109 |

총 4 파일 — 가장 작은 PR 사이클 footprint.

## 자연 만료 테스트 없음

PR23-M (1 unresolved gap 0.8 → 0.9) / PR24-N (active 2 strength 0/0 0.8 →
1.0) 와 달리 PR25-T 는 **modifier 의미 변경 없음** — 기존 테스트의 expected
값 갱신이 필요 없다.

PR25-T 는 API surface 만 확장하므로 PR1~PR24-N 의 모든 invariant 가 그대로
회귀 0. 기존 871 tests 그대로 통과.

## PR1~PR24-N 정합

- `types.py` 변경 0 — Sub-decision D 영구 보존
- `__init__.py` 변경 0 — public export 추가 없음 (Engine method 만)
- `rule_output.py` 변경 0 — Sub-decision D 영구 보존
- PR9-A `active_contradictions_for_claim` asc 동작 — 변경 없음
- PR11-C freshness modifier 의미 — 변경 없음
- PR12-D + PR23-M gap modifier 의미 — 변경 없음
- PR19-E + PR24-N count modifier 의미 — 변경 없음
- PR20-F rule_stats modifier 의미 — 변경 없음
- PR21-L evidence_type modifier 의미 — 변경 없음
- PR22-S strict validation 의미 — 변경 없음 (helper 추출 후에도 코드 차원 보존)
- PR10-A refute / PR11-B refute_by_freshness 동작 — 변경 없음
- PR17 round-trip identity — 보존
- PR18-K migration framework — 변경 없음 (snapshot schema 변경 없음)

## Out of Scope (PR25-T 외)

| 제외 | 이유 / 향후 |
|---|---|
| Built-in `EVIDENCE_TYPE_HINT` enum | Sub-decision AF 영구 |
| `Evidence.type` 값 의미 해석 / 도메인 제약 | Sub-decision AF — taxonomy 소유 회피 |
| `evidence_type_modifier` 공식 / 강도 변경 | Sub-decision BI — 본 PR 범위 밖 |
| Snapshot schema v3 bump | Sub-decision BH |
| Snapshot 직렬화 형식 변경 | Sub-decision BH |
| `replace_hint_evidence_types(types)` | register + clear 조합으로 표현 가능 |
| `is_registered_hint_evidence_type(type_id)` query API | 별도 PR (read-only query 영역) |
| `list_hint_evidence_types()` getter | snapshot 으로 이미 접근 가능 |
| Per-claim hint set override | engine-global 만 |
| Hint-tiering (weak / strong hint 분리) | 별도 PR |
| Hint set 변경 audit / lifecycle event | 별도 PR — lifecycle 영역 |
| `rule_output.py` 변경 | Sub-decision D 영구 |
| `types.py` / `__init__.py` 변경 | Sub-decision D 영구 |
| Validation 강화 (예: positive-only) | Sub-decision AK 정신 보존 |
| RuleStats outcome ratio (Q/R 트랙) | 별도 PR |

## 다음 PR 후보

PR25-T 닫음 후 PR26+ 후보 (사용자 결정 대기):

- **PR26 후보 R — rule_stats observed_precision 사용** (PR20-F 자연 후속, 권고): 기존 `RuleStats.observed_precision` / `false_positive_rate` 필드를 effective modifier 에 반영. PR24-N continuous 패턴 재활용 가능.
- **PR26 후보 G — superseded/retracted 상태**: types.py / __init__.py 손대야 함, **사용자 명시 승인 필요**.
- **PR26 후보 J — multi-rule claim composition**: prior 합성 규칙 (max / mean / harmonic).
- **PR26 후보 O — rule version pinning**: rule update 시 claim 영향도.
- **PR26 후보 P — external integration spec**: 외부 소비자 패키지 계약 (docs 위주).
- **PR26 후보 Q — rule_stats outcome ratio**: claim lifecycle 결과 역전파 (대규모).

권고: **R (PR20-F 자연 후속, PR24-N continuous 패턴 재활용)** — RuleStats 영역의 자연 심화. observed_precision 이 이미 존재하는 필드라 types.py 영향 없음.

## Spec Reference

- §37 (Hint evidence type deregistration API, PR25-T)
- §34 (Evidence_type registration strict validation, PR22-S) — PR25-T validation 의 모체
- §33 (Evidence_type modifier MVP, PR21-L) — PR25-T 가 보존하는 modifier 의미의 모체
- §36 (Count modifier strength averaging, PR24-N) — 인접 PR
- §35 (Gap modifier severity tiering, PR23-M) — 인접 PR
- §32 (Rule_stats modifier MVP, PR20-F)
- §31 (Count modifier MVP, PR19-E)
- §30 (Snapshot migration framework, PR18-K) — 무영향
- §29 (Persistence MVP, PR17)
- §28 (Gap modifier MVP, PR12-D)
- §26 (Evidence freshness modifier, PR11-C)
- §24 (Effective confidence, PR11-D)

## How to Run

```bash
# PR25-T invariants 만
pytest tests/test_engine_hint_evidence_type_deregistration.py -v

# 전체
pytest -q
```

## Self-review

- [x] 107차 의도 fail 34개 → 108차 34/34 pass 정확히 전환
- [x] 107차 pass 16개 유지
- [x] 기존 871 회귀 0
- [x] 최종 921 passing, 0 fail
- [x] `_validate_hint_evidence_type_values` private helper 추출 (PR22-S 본문 이전)
- [x] register / unregister 가 같은 helper 호출 (Sub-decision BD 코드 차원 보장)
- [x] `unregister_hint_evidence_types` 신규 — set difference + strict validation 공유
- [x] `clear_hint_evidence_types` 신규 — set.clear, no validation
- [x] register 외부 동작 변경 없음 (Sub-decision BJ)
- [x] unregister missing type → no-op (Sub-decision BE)
- [x] unregister all-or-nothing (Sub-decision BF) — 검증 완료 후에만 difference_update
- [x] clear 항상 no-op safe (Sub-decision BG) — TypeError 절대 raise 안 함
- [x] unregister / clear 후 modifier 즉시 반영 (Sub-decision BI) — `_evidence_type_modifier_for_claim` 본문 변경 0
- [x] `Evidence` / `Claim` / `Gap` dataclass 변경 없음
- [x] snapshot schema_version `2` 유지 (Sub-decision BH)
- [x] snapshot 직렬화 형식 변경 없음
- [x] `_EVIDENCE_TYPE_PENALTY_MODIFIER == 0.9` 유지
- [x] 7-modifier formula shape / 강도 / 순서 변경 없음
- [x] public namespace 신규 export 0
- [x] `types.py` / `__init__.py` / `rule_output.py` 변경 0
- [x] built-in HINT enum 부재 (Sub-decision AF 영구)
- [x] lifecycle / refute / contradiction / 다른 modifier 의미 변경 없음
- [x] PR21-L / PR22-S / PR23-M / PR24-N / PR9-A / PR10-A / PR11-B / PR17 regression 모두 검증
- [x] 자연 만료 테스트 없음 — modifier 의미 변경 없으므로 기존 테스트 expected 갱신 불필요
- [x] PR cycle 신규 push 패턴 적용 (106차 직후 push + Draft PR, 이후 차수마다 push)
- [x] 모든 차수 commit message body PR19 자세한 스타일

## Final definition

> **PR25-T 는 Evidence.type taxonomy 를 만드는 PR 이 아니다.**
> **PR25-T 는 hint evidence type set 의 운영 경계를**
> **`register / unregister / clear` 로 닫는 PR 이다.**

> *Taxonomy ownership stays outside the framework.*
> *The framework owns only strict boundary validation and live modifier application.*

PR21-L → PR22-S → PR25-T 누적 효과:
- 등록: caller 가 hint type id 를 framework 에 알림 (PR21-L)
- 등록 input 의 strict validation: implicit cast / partial mutation 차단 (PR22-S)
- 해제: caller 가 등록 취소 가능 (PR25-T unregister)
- 초기화: 전체 hint set 비우기 (PR25-T clear)
- 양방향 validation 공유: register / unregister 가 동일 helper 호출 (PR25-T 구조)

evidence_type modifier 의 의미 / 강도 / 공식 / snapshot schema 는 PR21-L 이후
변경된 적이 없음. PR25-T 는 그 보존을 유지하면서 set 조작 API 만 완결.

## Result

```text
Before PR25-T (main = 7114b1a):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  hint API: register only
  871 passing

After PR25-T (main = <new sha>):
  effective = base × status × freshness × gap × count × rule_stats × evidence_type
  (formula shape unchanged, modifier semantics unchanged)
  hint API: register / unregister / clear (operational boundary completed)
  921 passing, 0 fail
```

7-modifier composition formula shape 보존. evidence_type modifier 의미 변경
없음. hint evidence type 운영 경계 완결. **PR25-T 의 본질은 modifier 의미
확장이 아니라 caller-facing API surface 의 boundary completion 이다.**
