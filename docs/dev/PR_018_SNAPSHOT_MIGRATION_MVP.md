# PR #018 — Snapshot Migration MVP (PR18-K, K 트랙)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/snapshot-migration-mvp` → `main`
> Base: `ff30d9d` (PR17 merged)
> Tests: 652 passing (local)

## 목적

PR17 까지의 흐름:

```text
to_snapshot() → schema_version=1 (hardcoded)
from_snapshot(dict):
  missing schema_version → ValueError
  version != 1 → ValueError
  → 미래 schema 변경 대응 framework 없음
```

PR18-K 추가:

```text
to_snapshot() → schema_version = _CURRENT_SNAPSHOT_SCHEMA_VERSION (= 1)
from_snapshot(dict):
  1. _migrate_snapshot_to_current(snapshot)
     - missing → ValueError
     - unsupported → ValueError + supported set 명시
     - v1 → identity (사본 반환)
  2. PR17 restore 로직 (변경 없음)

미래 (PR19+ schema 변경 시):
  _SUPPORTED = frozenset({1, 2})
  _CURRENT = 2
  _migrate 에 v1 → v2 step 추가
  → to_snapshot 자동 v2 출력
  → from_snapshot 자동 v1 / v2 둘 다 받음
```

## PR18-K 의 한 줄 정의

> **PR18-K 는 실제 migration 을 수행한 PR 이 아니라, 미래 schema 변경을 받을
> 수 있는 migration framework 자리를 만든 PR 이다.**

PR17 §29.5 의 명시적 미래 자리 ("migration 로직은 PR-H+") 에 framework 도입.

## 핵심 명제 (§30.2)

```text
Snapshot migration preserves compatibility, not truth.
It may reshape snapshot structure, but it must not re-run rules,
recompute lifecycle transitions, or reinterpret evidence.
```

한국어:

```text
Snapshot migration 은 호환성을 보존한다. 진실 판단을 다시 하지 않는다.

구조는 바꿀 수 있지만 의미를 재계산하면 안 된다.
```

PR17 의 "state preservation, not re-judgment" → **compatibility preservation,
not re-judgment** 로 확장.

## 닫힌 흐름 (PR18-K 추가분)

```python
# 1) 정상 round-trip (PR17 동작 그대로 보존)
engine = Engine()
snap = engine.to_snapshot()           # → {"schema_version": 1, ...}
restored = Engine.from_snapshot(snap)  # → round-trip identity

# 2) Migration helper 단독 호출 (private — 테스트 / 미래 PR 만)
from ragcore.engine import _migrate_snapshot_to_current
migrated = _migrate_snapshot_to_current(snap)  # → identity for v1
assert migrated == snap

# 3) Unsupported version → ValueError
Engine.from_snapshot({"schema_version": 99})  # ValueError
Engine.from_snapshot({"schema_version": 2})   # ValueError (현재 SUPPORTED 아님)

# 4) Missing → ValueError
Engine.from_snapshot({})  # ValueError

# 5) 미래 schema 변경 시나리오 (PR19+ 예시)
# _SUPPORTED = frozenset({1, 2})
# _CURRENT = 2
# def _migrate_snapshot_to_current(snap):
#     if snap["schema_version"] == 1:
#         snap = _v1_to_v2(snap)  # v1 → v2 변환
#     return snap
# → from_snapshot 이 v1 snapshot 도 자동으로 처리
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `e59f947` | docs(contract): define snapshot migration MVP (§30) |
| 2 | `02c2e04` | test(core): lock snapshot migration invariants |
| 3 | `54056db` | feat(engine): add snapshot migration framework |
| 4 | (this) | docs(dev): PR18-K record |

## 주요 설계 결정 (§30)

### 1. Sub-decision K-1 — Framework only

| 옵션 | 채택 | 이유 |
|---|---|---|
| **(K-1-framework-only)** | ✓ | 현재 v1 만 존재. 가짜 migration 도입 회피 |
| (K-1-with-first-migration) | ✗ | v2 가 아직 없으므로 가상 migration 은 의미 X |

MVP 는 **migration 호출 경로만** 잠금. 실제 migrator 등록은 PR19+ schema 변경
시점에.

### 2. Sub-decision K-2 — Schema version constants

```python
_CURRENT_SNAPSHOT_SCHEMA_VERSION = 1
_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})
```

- engine 내부 private
- PR17 의 hardcoded `1` 을 상수화
- 미래 schema 변경 시 두 상수만 업데이트

### 3. Sub-decision K-3, K-4 — ValueError 보존

| 시나리오 | 결과 |
|---|---|
| missing schema_version | `ValueError` (PR17 동작 그대로) |
| unsupported version (99, 2, 등) | `ValueError + supported set 명시` |

PR17 의 `version != 1 → ValueError` 의 일반화. 미래 supported 확장 시 자연
적용.

### 4. Sub-decision K-5 — v1 identity migration

```python
if version == _CURRENT_SNAPSHOT_SCHEMA_VERSION:
    return dict(snapshot)  # identity (shallow copy)
```

현재 v1 만 supported → identity. `dict(snapshot)` 로 사본 반환 (mutation 회피).

### 5. Sub-decision K-6 — Pure function (dict → dict)

```text
input:  snapshot dict
output: snapshot dict (current version)
side effect: 없음
engine state: 직접 건드리지 않음
```

이유:
- 결정성 (같은 input → 같은 output)
- 테스트 친화 (engine 인스턴스 없이도 검증 가능)
- 미래 migration chain (1 → 2 → 3) 의 step-by-step 구성

### 6. Sub-decision K-7 — `from_snapshot` 통합

```python
# Before (PR17)
if "schema_version" not in snapshot:
    raise ValueError(...)
if snapshot["schema_version"] != 1:
    raise ValueError(...)

# After (PR18-K)
snapshot = _migrate_snapshot_to_current(snapshot)
```

검증을 helper 안으로 흡수. 단일 책임. caller 시그니처 / KeyError-style
ValueError / return type 무변경.

### 7. API — Public 노출 안 함

PR18-K 가 추가하는 것은 **engine 내부 private 만**:

- `_CURRENT_SNAPSHOT_SCHEMA_VERSION` (module level)
- `_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS` (module level)
- `_migrate_snapshot_to_current` (module level)

`ragcore` / `ragcore.types` / `ragcore.__init__` 새 export 없음. caller 시점
에서 **invisible**.

### 8. PR17 호환성 100%

| | PR18-K 영향 |
|---|---|
| `to_snapshot` 시그니처 / 동작 / 출력 (schema_version=1) | 없음 |
| `from_snapshot` 시그니처 / KeyError-style ValueError / return type | 없음 |
| PR17 round-trip identity (22 invariant) | 모두 유효 |
| 모든 engine state (PR1~PR12-D) | 없음 |
| 5 lifecycle API + PR11-B sibling | 없음 |
| `compute_effective_confidence` (4-modifier) | 없음 |
| `register_contradiction*` / 모든 query | 없음 |
| All private constants (PR10-A, PR11-D/C, PR12-D) | 없음 |
| `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 (Sub-decision D 정합) |
| public exports | 없음 |
| 외부 dependency | 없음 |

PR18-K 는 **engine 내부 private framework 만 추가**. caller 시점에서 PR18-K
는 invisible.

## 불변식 (테스트로 잠금)

§30.13 의 14 invariant:

1. `_CURRENT_SNAPSHOT_SCHEMA_VERSION == 1`
2. `_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS` 가 1 포함
3. `_migrate_snapshot_to_current` callable
4. **v1 snapshot → identity migration** (사본 반환)
5. **PR17 round-trip identity 보존** ★ (모든 query 동일)
6. missing schema_version → `ValueError`
7. unsupported version (99) → `ValueError`
8. version=2 (currently unsupported) → `ValueError`
9. **migration 결정성** (같은 input → 같은 output)
10. **migration input mutate 안 함** (deep equality 보존)
11. constants / function public export 차단 (ragcore + types)
12. `to_snapshot` 출력 schema_version=1 (PR17 동작 보존)
13. PR17 의 22 invariant 모두 유효
14. 기존 636 회귀 없음

## 테스트

**652 passing** in ~0.54s (636 → 652, delta 정확히 +16)

### Test-first 흐름 (PR11-A 59차 / PR17 75차 동일 mixed pattern)

79차 (test-first 잠금):

```text
16 새 tests 추가
실행 결과 (의도된 mixed 분포):
- 7 fails (framework 부재):
    * _CURRENT_SNAPSHOT_SCHEMA_VERSION 미존재 (None == 1 fail)
    * _SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS 미존재
    * _migrate_snapshot_to_current 미존재 × 5
- 9 pass (PR17 동작 보존 + Privacy 정합으로 이미 통과):
    * 3 ValueError 케이스 (missing/unsupported high/version=2)
    * 1 from_snapshot round-trip integration
    * 3 Privacy (ragcore + types 미노출)
    * 2 PR17 동작 보존 (to_snapshot schema=1, round-trip identity)
+ 기존 636 통과
```

Collection-error 회피 (사용자 권고 getattr 패턴):
- `ragcore.engine` 모듈 직접 import (whitebox internal access)
- `getattr(engine_module, "name", None)` 동적 접근
- import error 없이 의도된 assertion fail

80차 (구현):

```text
- ragcore/engine.py:
    _CURRENT_SNAPSHOT_SCHEMA_VERSION = 1 (private)
    _SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = frozenset({1}) (private)
    # ---- Snapshot migration framework (PR18-K §30) ---- 섹션 신설
    _migrate_snapshot_to_current 함수 (검증 + identity)
    from_snapshot 통합 (검증을 helper 안으로)
    to_snapshot hardcoded 1 → 상수
실행 결과: 652 통과 (7 fail → 7 pass, 9 pass 유지)
```

### 변경 파일 (PR18-K 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §30 신설 (+230 lines) |
| `tests/test_engine_snapshot_migration.py` | 신규 (16 tests, +232 lines) |
| `ragcore/engine.py` | 2 private constants + 1 helper + from_snapshot 통합 + to_snapshot 가독성 (+41, -7) |
| `docs/dev/PR_018_SNAPSHOT_MIGRATION_MVP.md` | 이 파일 (신규) |
| `ragcore/types.py` | **변경 없음** |
| `ragcore/__init__.py` | **변경 없음** (PR18-K 전체 private) |
| `ragcore/rule_output.py` | **변경 없음** (Sub-decision D 정합) |

### 테스트 분포

| 파일 | PR17 후 | PR18-K (79차) | PR18-K (80차) | 변동 |
|---|---|---|---|---|
| `test_engine_snapshot_migration.py` | 0 | 16 (7 fail + 9 pass) | **16 (pass)** | +16 |
| 나머지 22 파일 | 636 | 636 | **636** | 0 |
| **Total** | 636 | 636 + 9 pass + 7 fail | **652** | **+16** |

### 신규 테스트 그룹

**TestSnapshotMigrationConstants (2):** schema version constants
**TestSnapshotMigrationFunction (2):** `_migrate_snapshot_to_current` exists + callable
**TestSnapshotMigrationValidation (3):** missing / unsupported(99) / version=2 → ValueError (이미 pass)
**TestSnapshotMigrationIdentity (1):** v1 identity migration
**TestSnapshotMigrationIntegration (1):** from_snapshot 의 round-trip 보존 (이미 pass)
**TestSnapshotMigrationDeterminismAndPurity (2):** deterministic + mutate 안 함
**TestSnapshotMigrationPrivacy (3):** ragcore + ragcore.types 미노출 (이미 pass)
**TestPriorPersistenceBehaviorUnchanged (2):** to_snapshot=1 + PR17 round-trip (이미 pass)

## 구현 요약 (80차)

```python
# ragcore/engine.py (module level — _GAP_PENALTY_MODIFIER 다음)
_CURRENT_SNAPSHOT_SCHEMA_VERSION = 1
_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})

# ---- Snapshot migration framework (PR18-K §30) ----
def _migrate_snapshot_to_current(snapshot: dict[str, Any]) -> dict[str, Any]:
    version = snapshot.get("schema_version")
    if version is None:
        raise ValueError("Snapshot schema_version is required")
    if version not in _SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS:
        raise ValueError(
            f"Unsupported snapshot schema_version: {version}; "
            f"supported: {sorted(_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS)}"
        )
    if version == _CURRENT_SNAPSHOT_SCHEMA_VERSION:
        return dict(snapshot)  # identity (shallow copy)
    # 미래 자리: 중간 버전 → CURRENT 변환 chain
    raise ValueError(f"Unsupported snapshot schema_version: {version}")

# from_snapshot 통합 (Sub-decision K-7)
@classmethod
def from_snapshot(cls, snapshot: dict[str, Any]) -> "Engine":
    snapshot = _migrate_snapshot_to_current(snapshot)  # ← PR18-K 신규 step
    engine = cls()
    # ... PR17 restore 로직 (변경 없음)
    return engine

# to_snapshot 가독성 (Sub-decision K-2)
def to_snapshot(self) -> dict[str, Any]:
    return {
        "schema_version": _CURRENT_SNAPSHOT_SCHEMA_VERSION,  # hardcoded 1 대신
        ...
    }
```

배치: `# ---- Snapshot migration framework (PR18-K §30) ----` 섹션 신설,
PR17 의 Persistence helpers 직전 (module-level).

`types.py` / `__init__.py` / `rule_output.py` 변경 0.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| 실제 v0 → v1 migration | v0 snapshot 이 존재하지 않음 (PR17 이 v1 부터 시작) |
| v1 → v2 migration | v2 가 아직 정의되지 않음 — PR19+ schema 변경 시 |
| 자동 추론 migration | 명시성 원칙 — caller 가 명시적 등록 |
| Partial migration | 별도 결정점 |
| 데이터 복구 (corrupt snapshot 복구) | 의미 추론 → core 밖 |
| Rule 재실행 / lifecycle 재판단 | PR17 §29.2 / PR18-K §30.2 정신 |
| File IO | PR17 Sub-decision H-2 일관 (caller 책임) |
| Migration registry public API | engine 내부 private — 미래 정책 |
| Pickle / Python-specific migration | PR17 Sub-decision H-2 일관 |
| Migration 의 cryptographic verification | core 밖 |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| G | **superseded/retracted 추가 상태** | 중 (도메인 운영 의미 — 입력 필요) |
| E | **Contradiction count modifier** — active 개수 기반 추가 감쇠 | 중 |
| F | **RuleStats-based modifier** — `observed_precision` / `false_positive_rate` | 중 |
| L | **File IO wrapper** — `to_file(path)` / `from_file(path)` (PR17 위 편의 layer) | 낮음 (caller 자체 처리 가능) |
| M | **fire_rule audit** — PR10-B history 를 transition 외 영역으로 확장 | 중 |
| J | **Gap freshness / type-aware modifier** — PR12-D 의 단순 binary 정교화 | 중 |
| N | Engine bulk fire / `not` combinator / trace 직렬화 | 낮음 |
| O | C/Rust hot loop port (Phase 5) | 낮음 |
| P | **첫 schema 변경 (v1 → v2)** — PR18-K framework 의 첫 실사용 | (도메인 요구 명확해진 뒤) |

추천: **G (superseded/retracted)** 또는 **E (count modifier)**.

G 는 도메인 운영 의미 (취소 / 대체) 가 확정되면. PR8 disputed 와 다른 의미.
E 는 PR11-C / PR12-D 의 modifier 분해 자리 또 한 번 활용 — `effective = base
× status × freshness × gap × count`. 도메인 입력 무관.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §30](../contracts/05_DATA_CONTRACT_MVP.md) — Snapshot migration (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §29](../contracts/05_DATA_CONTRACT_MVP.md) — Engine persistence (PR17 base)
- [docs/dev/PR_017_ENGINE_PERSISTENCE_MVP.md](PR_017_ENGINE_PERSISTENCE_MVP.md) — PR17 base (이전 PR)

## How to Run

```bash
git checkout feat/snapshot-migration-mvp
pip install -e .
pytest -v
```

652 tests in ~0.54s. No new external dependencies.

## Result

PR18-K 가 PR17 의 `schema_version` 자리에 migration framework 도입.

```text
PR17: state preservation (engine state → JSON snapshot → restored)
PR18-K: + compatibility preservation (snapshot migration framework)
```

미래 schema 변경 (v1 → v2 → ...) 시:
- `_SUPPORTED` 확장
- `_CURRENT` 업데이트
- `_migrate_snapshot_to_current` 에 변환 step 추가
- `to_snapshot` 자동으로 새 version 출력
- `from_snapshot` 자동으로 이전 version 받아서 변환

caller 코드 변경 없이 schema evolution 가능.

PR18-K 의 본질:

> **"실제 migration 을 수행한 PR 이 아니라, 미래 schema 변경을 받을 수 있는
> migration framework 자리를 만든 PR."**
>
> Compatibility preservation, not re-judgment.

PR17 의 "state preservation, not re-judgment" → PR18-K 의 "compatibility
preservation, not re-judgment" 로 자연 확장. 두 PR 모두 "재판단 없이 보존"
정신.
