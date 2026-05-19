# PR #017 — Engine Persistence MVP (PR17, H 트랙)

> Status: ready to merge (after Draft PR review).
> Branch: `feat/engine-persistence-mvp` → `main`
> Base: `2c21f79` (PR12-D merged)
> Tests: 636 passing (local)

## 목적

PR12-D 까지의 흐름:

```text
engine state 는 in-memory only
→ process 종료 시 모든 state (lifecycle / history / scoring) 소실
→ 같은 lifecycle 결정을 재현하려면 모든 호출 재실행 필요
```

PR17 추가:

```text
engine.to_snapshot() → JSON-compatible dict
caller 가 dict 를 어떻게 보존하든 자유 (file / DB / network)

Engine.from_snapshot(dict) → restored engine
→ rule 재실행 없이 원본과 functionally identical
→ 모든 query (status / history / effective / freshness) 동일
```

## PR17 의 한 줄 정의

> **PR17 persistence MVP 는 engine state 를 versioned snapshot 으로 보존/복원
> 한다. 복원은 rule 재실행이나 lifecycle 재판단이 아니라, 닫힌 state 의
> 결정적 재구성이다.**

## 핵심 명제 (§29.2)

```text
Persistence is state preservation, not re-judgment.

Persistence MVP stores and restores a versioned engine snapshot.
It must not re-run rules, re-evaluate evidence, or infer new lifecycle
transitions.
```

한국어:

```text
복원은 재판단이 아니라, 닫힌 engine 상태의 결정적 복원이다.

PR17 는 versioned engine snapshot 의 저장/복원만 한다.
rule 재실행 / evidence 재평가 / 새 lifecycle 전이 추론 모두 금지.
```

## API

```python
def to_snapshot(self) -> dict[str, Any]:
    """Serialize engine state to JSON-compatible dict.

    Returns:
        dict with "schema_version": 1 + all engine state.
    """

@classmethod
def from_snapshot(cls, snapshot: dict[str, Any]) -> "Engine":
    """Restore engine from snapshot dict.

    Raises:
        ValueError: missing or unknown schema_version.
    """
```

## 닫힌 흐름 (PR17 추가분)

```python
# 1) 원본 engine — 4-modifier composition + lifecycle audit + rule registry
original = Engine()
# ... 다양한 작업 수행 (claims, gaps, contradictions, lifecycle transitions, ...)

# 2) Snapshot
snapshot = original.to_snapshot()
# {
#   "schema_version": 1,
#   "next_id": {...},
#   "lifecycle_seq": 5,
#   "claims": [...],
#   "evidences": [...],
#   "gap_resolutions": [...],
#   "contradictions": [...],
#   "claim_lifecycle_events": [...],
#   "rule_definitions": [...],
#   "rule_stats": [...],
#   ...
# }
import json
serialized = json.dumps(snapshot)  # JSON-compatible

# 3) Restore
loaded = json.loads(serialized)
restored = Engine.from_snapshot(loaded)

# 4) Round-trip identity — 모든 query 동일
restored.get_claim(c) == original.get_claim(c)
restored.claim_lifecycle_history(c) == original.claim_lifecycle_history(c)
restored.compute_effective_confidence(c) == original.compute_effective_confidence(c)
restored.active_contradictions_by_freshness(c) == original.active_contradictions_by_freshness(c)
# ... 모든 query identity

# 5) Restore 후 새 작업 가능 (_next_id 보존)
new_entity = restored.add_entity(entity_type=99)  # 기존 entity 와 ID 충돌 없음
```

## 들어간 커밋 (4)

| # | SHA | 내용 |
|---|---|---|
| 1 | `f935bf0` | docs(contract): define engine persistence MVP (§29) |
| 2 | `6035962` | test(core): lock persistence snapshot invariants |
| 3 | `1783252` | feat(engine): add persistence snapshot |
| 4 | (this) | docs(dev): PR17 record |

표기 정정: 74차 commit message 의 "PR-H" 는 트랙 라벨. 공식 PR 번호는 **PR17**.
record 파일명 `PR_017_*` 도 통합 시퀀스 (PR_016 다음).

## 주요 설계 결정 (§29)

### 1. Sub-decision H-1 — Snapshot, NOT event sourcing

```text
복원 방식: 현재 engine state 의 직접 직렬화
NOT: lifecycle history 재생 / rule 재실행
```

| 옵션 | 채택 | 이유 |
|---|---|---|
| **(H-1-snapshot)** | ✓ | 결정성 100%, 단순, "닫힌 상태 보존" 정신 |
| (H-1-event-sourcing) | ✗ | rule 재실행 필요 → 결정성 / 의미 보존 위험 |

PR10-B `claim_lifecycle_history` 는 보존되지만 **재생 안 함**. snapshot 이
history 도 그대로 저장하고 그대로 복원.

### 2. Sub-decision H-2 — JSON-compatible dict only

```python
to_snapshot() -> dict       # JSON-serializable
from_snapshot(dict) -> Engine
```

file IO / database / encoding format 모두 OOS. caller 가 dict 를 받아서
`json.dumps` 하든 pickle 하든 자유.

### 3. Sub-decision H-3 — schema_version = 1

```python
snapshot["schema_version"] == 1   # 필수
```

PR17 MVP 는 schema_version 검증만 (version != 1 → ValueError, missing →
ValueError). migration 로직은 PR-H+ 또는 별도 PR.

### 4. Sub-decision H-4 — API 형태

```python
engine.to_snapshot() -> dict             # instance method
Engine.from_snapshot(dict) -> Engine     # classmethod
```

`from_snapshot` 가 classmethod 인 이유:
- 새 Engine 인스턴스를 생성하기 때문 (factory pattern)
- caller 가 기존 engine 인스턴스 없이도 복원 가능

### 5. Sub-decision H-5 — 보존 대상 (rule registry 포함)

| 영역 | 보존? | 이유 |
|---|---|---|
| `_next_id` | ✓ | restore 후 새 entity 등록 시 ID 충돌 방지 |
| `_entities` / `_observations` / `_claims` / `_evidences` / `_relations` / `_gaps` | ✓ | core state |
| `_rule_definitions` / `_rule_stats` | ✓ | rule registry (firing_count 누적) |
| `_gap_dedup_index` / `_claim_gap_refs` (PR4) | ✓ | gap dedup 의미 보존 |
| `_gap_resolutions` (PR5) | ✓ | gap resolution 의미 보존 |
| `_contradictions` / `_resolved_contradictions` (PR7/PR9-A) | ✓ | refute 정책 input |
| `_lifecycle_seq` / `_claim_lifecycle_events` (PR10-B) | ✓ | audit trail 보존 |

**Rule registry 포함 결정 이유:**
- `RuleStats.firing_count` 가 PR2 부터 누적된 카운터 — engine state 의 일부
- caller 가 `from_snapshot` 후 같은 rule 로 재실행하려면 rule registry 필수
- "닫힌 engine 상태 보존" 의 의미와 정합

### 6. Sub-decision H-6 — Tuple key / set 직렬화

JSON 은 tuple key / set 미지원. 변환 규칙:

| Python | JSON 표현 |
|---|---|
| `tuple` (in field value) | list |
| `set[int]` | sorted list[int] (결정성) |
| `dict[int, X]` | `[{"key": int, "value": X}, ...]` sorted by key |
| `dict[tuple[int,int], X]` (rule registry) | `[{"key": [t1,t2], "value": X}, ...]` sorted |
| `dict[tuple[int,int,int,int], X]` (`_gap_dedup_index`) | `[{"key": [a,b,c,d], "value": X}, ...]` sorted |
| `ScoreValue` (frozen dataclass) | `{"value": float}` (asdict) |
| `ScoreValue \| None` | `{"value": float}` or `None` |
| frozen dataclass | asdict (모든 필드 평탄화) |

이 규칙이 결정성 + JSON 호환성 + 단순성 모두 만족.

### 7. 결정성 (Determinism)

```text
같은 engine state → to_snapshot() → 같은 dict (모든 set/dict iteration sorted)
같은 dict → from_snapshot() → functionally identical engine

restored.compute_effective_confidence(c) == original.compute_effective_confidence(c)
restored.claim_lifecycle_history(c) == original.claim_lifecycle_history(c)
restored.active_contradictions_by_freshness(c) == original.active_contradictions_by_freshness(c)
... 모든 query 동일
```

PR17 는:
- wall-clock 안 봄
- random / external state 안 봄
- 모든 set / dict iteration sorted

PR10-A/B/PR11-A~D/PR12-D 의 결정성 원칙 그대로 보존 + persistence 안에서도
결정성.

### 8. PR1~PR12-D 와의 정합 — 의미 무변화

PR17 은 **2 신규 메서드 추가만**:

| | PR17 영향 |
|---|---|
| `Claim` / `Evidence` / `Gap` / `Relation` / `ScoreValue` / `ClaimLifecycleEvent` dataclass | 없음 (asdict 활용) |
| 5 lifecycle API + PR11-B sibling | 없음 |
| `compute_effective_confidence` (4-modifier composition) | 없음 |
| `register_contradiction*` (PR7, PR9-A) | 없음 |
| PR11-A query / PR9-A asc / PR5 gap_resolution | 없음 |
| All private constants (`_REFUTATION_STRENGTH_THRESHOLD`, `_STATUS_MODIFIER_*`, `_FRESHNESS_PENALTY_WEIGHT`, `_GAP_PENALTY_MODIFIER`) | 없음 |
| `CLAIM_STATUS_MAP` / `_ALLOWED_CLAIM_STATUSES` | 없음 (Sub-decision D 정합) |
| `fire_rule*` / `RuleStats` 의미 | 없음 |
| public exports | 없음 (instance method + classmethod 추가만) |
| 외부 dependency | 없음 (표준 라이브러리만 — `dataclasses.asdict`, `typing.Any`) |

PR17 는 **engine 동작 변경 0**. caller 코드 변화 0.

## 불변식 (테스트로 잠금)

§29.11 의 22 invariant:

1. `to_snapshot` returns dict
2. snapshot 에 `"schema_version": 1`
3. **Round-trip — 빈 engine** ★
4. **Round-trip — 단일 claim** ★
5. **Round-trip — 전체 lifecycle path** ★
6. **Round-trip — gap_resolution** ★
7. **Round-trip — contradictions / resolved** ★
8. **Round-trip — lifecycle history** ★ (PR10-B audit 보존)
9. **Round-trip — rule registry** ★ (firing_count 보존)
10. **Round-trip — _next_id** (restore 후 새 등록 가능)
11. determinism — 같은 state 두 번 snapshot 동일
12. set sorted (결정성)
13. dict[int] sorted (결정성)
14. schema_version ≠ 1 → ValueError
15. malformed snapshot → ValueError
16. JSON 호환성 (`json.dumps` 동작)
17. **restore 후 compute_effective_confidence 정확** ★ (4-modifier composition)
18. restore 후 lifecycle API 호출 가능
19. restore 후 register API 호출 가능
20. restore 후 add_* API 호출 가능 (_next_id 충돌 없음)
21. **PR1~PR12-D 의미 무변화** ★
22. 기존 612 회귀 없음

## 테스트

**636 passing** in ~0.60s (612 → 636, delta 정확히 +24)

### Test-first 흐름 (PR11-A 59차 / PR11-B 67차 동일 mixed pattern)

75차 (test-first 잠금):

```text
24 새 tests 추가
실행 결과 (의도된 mixed 분포):
- 21 fails (의도된 AttributeError):
    * engine.to_snapshot missing × 19
    * Engine.from_snapshot missing × 2
- 3 pass (PR1~PR12-D 무변화 — 이미 정합):
    * test_compute_effective_confidence_unchanged (4-modifier)
    * test_lifecycle_apis_unchanged (5 + PR11-B sibling)
    * test_register_apis_unchanged
+ 기존 612 통과
```

미세 조정 (75차 안에서): `RuleDefinition` 시그니처 (실제 필드: `prior_confidence`,
`maturity`) 확인. invariant 의미는 그대로.

76차 (구현):

```text
- ragcore/engine.py:
    import asdict + typing.Any
    # ---- Persistence snapshot (PR17 §29) ---- 섹션 신설
    to_snapshot (instance method) + from_snapshot (classmethod)
    module-level helpers (8 _from_dict + 7 serialization + 2 restore)
실행 결과: 636 통과 (21 fail → 21 pass, 3 pass 유지)
```

### 변경 파일 (PR17 범위)

| 파일 | 변경 |
|---|---|
| `docs/contracts/05_DATA_CONTRACT_MVP.md` | §29 신설 (+239 lines) |
| `tests/test_engine_persistence.py` | 신규 (24 tests, +467 lines) |
| `ragcore/engine.py` | import + 2 메서드 + helpers (+219, -1) |
| `docs/dev/PR_017_ENGINE_PERSISTENCE_MVP.md` | 이 파일 (신규) |
| `ragcore/types.py` | **변경 없음** |
| `ragcore/__init__.py` | **변경 없음** (새 export 없음) |
| `ragcore/rule_output.py` | **변경 없음** (Sub-decision D 정합) |

### 테스트 분포

| 파일 | PR12-D 후 | PR17 (75차) | PR17 (76차) | 변동 |
|---|---|---|---|---|
| `test_engine_persistence.py` | 0 | 24 (21 fail + 3 pass) | **24 (pass)** | +24 |
| 나머지 21 파일 | 612 | 612 | **612** | 0 |
| **Total** | 612 | 612 + 3 pass + 21 fail | **636** | **+24** |

### 신규 테스트 그룹

**TestSnapshotAPIExists (2):** API 존재 + schema_version
**TestSchemaVersionValidation (2):** unknown / missing version → ValueError
**TestSnapshotIsJsonCompatible (2):** empty / rich engine 모두 `json.dumps` 동작
**TestRoundtripIdentity (8):** ★ 핵심 — 빈/단일/lifecycle/gap/contradiction/history/rule registry/effective
**TestRestoredEngineCanContinue (4):** restore 후 새 작업 가능 (entity/claim 추가, lifecycle/register 호출)
**TestDeterminism (3):** 반복 호출 동일 + set sorted + dict[int] sorted
**TestPriorAPIUnchanged (3):** PR1~PR12-D 의미 무변화 (이미 pass — 사실은 PR17 의 본질 보장)

## 구현 요약 (76차)

```python
# ragcore/engine.py (file end)

# ---- Persistence snapshot (PR17 §29) ----
def to_snapshot(self) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "next_id": dict(sorted(self._next_id.items())),
        "lifecycle_seq": self._lifecycle_seq,
        "entities": _serialize_dict_int_dataclass(self._entities),
        "claims": _serialize_dict_int_dataclass(self._claims),
        # ... 16 fields total (모든 engine state)
    }

@classmethod
def from_snapshot(cls, snapshot: dict[str, Any]) -> "Engine":
    if "schema_version" not in snapshot:
        raise ValueError("snapshot missing schema_version")
    if snapshot["schema_version"] != 1:
        raise ValueError(f"unknown schema_version: {snapshot['schema_version']}")
    engine = cls()
    # ... 모든 state 복원
    return engine

# Module-level helpers (private):
# - ScoreValue: _sv_to_dict / _sv_from_dict (None 처리 포함)
# - 8 dataclass _from_dict (Entity/Observation/Claim/Evidence/Relation/Gap/
#                            RuleDefinition/RuleStats)
# - 6 serialize patterns: int_dataclass / tuple_dataclass / tuple4_int /
#                          int_set / int_int / int_list_dataclass
# - 2 restore patterns: dict_int / dict_tuple
```

`types.py` / `__init__.py` / `rule_output.py` 변경 0.

## Out of Scope (의도적 제외)

| 제외 | 이유 / 향후 |
|---|---|
| File IO (snapshot 을 파일로 저장/로드) | Sub-decision H-2 (dict 까지만) |
| Database persistence | 같은 이유 — caller 책임 |
| Event sourcing (history 재생으로 복원) | Sub-decision H-1 (snapshot 우선) |
| Migration system (schema_version > 1) | PR-H+ 자연 후속 |
| Partial restore (특정 claim 만 복원) | PR-H+ |
| Cross-version compatibility (1 → 2 → 3) | PR-H+ migration 결정 후 |
| Compression / 직렬화 형식 (msgpack, protobuf 등) | caller 책임 |
| External RAG corpus persistence | core 밖 |
| Pickle / Python-specific 직렬화 | Sub-decision H-2 (JSON-compatible only) |
| Incremental snapshot (diff 기반) | PR-H+ |
| Snapshot 의 cryptographic signing | core 밖 |
| Multi-engine snapshot 통합 | 별도 결정점 |

## 다음 PR 후보

| 후보 | 내용 | 우선도 |
|---|---|---|
| G | **PR18-G: superseded/retracted 추가 상태** | 중 (도메인 운영 의미 — 운영자 입력 필요) |
| E | **Contradiction count modifier** — active 개수 기반 추가 감쇠 | 중 (PR12-D 자연 후속) |
| F | **RuleStats-based modifier** — `observed_precision` / `false_positive_rate` | 중 (PR2/PR12-D 자연 후속) |
| J | **Gap freshness / type-aware modifier** — PR12-D 의 단순 binary 를 정교화 | 중 |
| K | **Migration system** — `schema_version` 1 → 2 변환 (PR17 자연 후속) | 중 (PR17 의 직접 후속) |
| L | **File IO wrapper** — `to_file(path)` / `from_file(path)` (PR17 위의 편의 layer) | 낮음 (caller 자체 처리 가능) |
| M | **fire_rule audit** — PR10-B history 를 transition 외 영역으로 확장 | 중 |
| N | Engine bulk fire / `not` combinator / trace 직렬화 | 낮음 |
| O | C/Rust hot loop port (Phase 5) | 낮음 |

추천: **K (Migration system)** 또는 **G (superseded/retracted)**.

K 는 PR17 의 가장 직접적인 후속 — `schema_version > 1` 도입 시 migration
정책 (1 → 2, 호환성 규칙) 결정.

G 는 도메인 운영 의미 (superseded/retracted) 가 확정되면. PR8 disputed 와
다른 의미 — 더 새 정보로 대체 / 명시적 취소.

## Spec Reference

- [docs/00_PROJECT_IDENTITY.md](../00_PROJECT_IDENTITY.md)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §29](../contracts/05_DATA_CONTRACT_MVP.md) — Engine persistence (this PR)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §28](../contracts/05_DATA_CONTRACT_MVP.md) — Gap modifier (PR12-D base — 보존 대상)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §23](../contracts/05_DATA_CONTRACT_MVP.md) — Lifecycle history (PR10-B — 보존 대상)
- [docs/contracts/05_DATA_CONTRACT_MVP.md §17](../contracts/05_DATA_CONTRACT_MVP.md) — Gap resolution (PR5 — 보존 대상)
- [docs/dev/PR_010_DISPUTED_REFUTATION_MVP.md](PR_010_DISPUTED_REFUTATION_MVP.md)
- [docs/dev/PR_011_LIFECYCLE_HISTORY_MVP.md](PR_011_LIFECYCLE_HISTORY_MVP.md)
- [docs/dev/PR_012_EFFECTIVE_CONFIDENCE_MVP.md](PR_012_EFFECTIVE_CONFIDENCE_MVP.md)
- [docs/dev/PR_014_EFFECTIVE_FRESHNESS_MODIFIER_MVP.md](PR_014_EFFECTIVE_FRESHNESS_MODIFIER_MVP.md)
- [docs/dev/PR_015_FRESHNESS_REFUTE_MVP.md](PR_015_FRESHNESS_REFUTE_MVP.md)
- [docs/dev/PR_016_GAP_MODIFIER_MVP.md](PR_016_GAP_MODIFIER_MVP.md) — PR12-D base (이전 PR)

## How to Run

```bash
git checkout feat/engine-persistence-mvp
pip install -e .
pytest -v
```

636 tests in ~0.60s. No new external dependencies.

## Result

PR17 가 PR1~PR12-D 의 모든 engine state 를 versioned snapshot 으로 보존/복원.
**4-modifier composition + lifecycle audit + rule registry** 모두 round-trip
identity 보장.

Architecture (after PR17):

```text
in-memory engine state → JSON-compatible snapshot (결정성 보장)
        ↓
   caller 자유 (file / DB / network 직렬화)
        ↓
JSON-compatible snapshot → from_snapshot → restored engine
        ↓
모든 query 동일 (status / history / effective / freshness / active)
restore 후 새 작업 가능 (_next_id 충돌 없음)
```

PR17 의 본질:

> **"재판단 PR 이 아니라, 닫힌 engine state 의 결정적 snapshot/restore PR."**
>
> Persistence is state preservation, not re-judgment.

PR1~PR17 흐름으로 in-memory engine 의 **state preservation** 기준선 완성.
미래 PR (migration / file IO / DB / cross-version) 모두 이 snapshot 형식
위에 자연 확장.
