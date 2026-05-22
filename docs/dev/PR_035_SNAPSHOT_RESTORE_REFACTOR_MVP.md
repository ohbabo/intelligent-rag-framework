# PR 035 — Snapshot Restore Refactor MVP

## Summary

PR35-O7 is a behavior-preserving snapshot restore refactor.

It completed restore helper symmetry with `to_snapshot` without changing snapshot schema_version, snapshot shape, public API surface, or restored Engine semantics.

Core closing statement (user-locked 2026-05-22):

```text
PR35-O7 S-pair is a behavior-preserving snapshot restore refactor.
It completes restore helper symmetry with to_snapshot
without changing snapshot schema_version, snapshot shape,
or restored Engine semantics.
```

PR35-O7 picked up the deferred §46.12 O7 candidate as a standalone PR. It also retired §46.12 O6 — subsumed by PR34-O O3.

Three-차수 cycle:

```text
144차  docs(contract) §47  Snapshot Restore Refactor Boundary + audit + O6 retirement
145차  refactor(engine)    S1 + S2 execution (4 helpers + from_snapshot rewrite)
146차  docs(dev) (this)    PR record + ready + squash merge
```

> **PR35-O7 completes 6 × 6 serialize/restore helper symmetry.**
> **It does not change schema, shape, surface, or semantics.**

---

## Baseline

```text
base main:    f3dde3a
branch:       feat/snapshot-restore-refactor
before tests: 1089 passing
public symbols: 48
Engine public methods: 40
snapshot schema_version: 2
```

Completed immediately before this PR:

```text
PR34-O internal optimization audit + Scope O-mid cleanup
```

The active confidence formula entering PR35-O7:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
```

PR35-O7 does not change this formula.

---

## Commit cycle

```text
144차  ef6e22d  docs(contract): define snapshot restore refactor boundary (§47)
145차  d9d01cf  refactor(engine): execute PR35-O7 S1+S2 restore helper symmetry
146차  this commit — docs(dev) record + Draft → Ready + squash merge
```

---

### 144차 — Audit-first entry (§47)

Commit `ef6e22d` added `§47 Snapshot Restore Refactor Boundary` (+451 lines) covering 11 subsections:

```text
§47.1   Core proposition (framing + O6 retirement note)
§47.2   Audit boundary (snapshot restore domain)
§47.3   144차 audit scope
§47.4   from_snapshot structure snapshot (45 LOC body)
§47.5   to_snapshot / from_snapshot symmetry comparison
§47.6   Asymmetry source (4 inline dict-comprehensions)
§47.7   Existing helper inventory (6 serialize + 2 restore)
§47.8   Refactor candidates S1 + S2 (proposal)
§47.9   Audit-only invariants
§47.10  Out of scope + Constraints on 145차+
§47.11  O6 retirement note (subsumed by PR34-O O3)
```

Key audit finding:

The original §46.12 O7 idea (per-kind helpers like `_load_entities`, `_load_claims`, etc.) would mostly add one-line wrappers around the existing `_restore_dict_int` calls — indirection without complexity reduction. The better refactor target is **restore helper symmetry** with the existing `_serialize_dict_*` helpers.

```text
to_snapshot:   6 _serialize_dict_* helpers, one per shape class
from_snapshot: 2 _restore_dict_* helpers + 4 inline dict-comprehensions

Asymmetry source:
  4 _restore_dict_* helpers are MISSING (parallel to _serialize_dict_*).
```

144차 added zero source changes, zero test changes, zero frozenset shifts.

---

### 145차 — S1 + S2 execution

Commit `d9d01cf` executed the coupled S1 + S2 pair:

```text
S1 Add 4 missing _restore_dict_* helpers          (low risk)
S2 Rewrite from_snapshot body to use them          (low risk)
```

Changed file:

```text
ragcore/engine.py only
```

Size:

```text
+57 / -22 (net +35 LOC)
1765 -> 1800 LOC
```

#### S1 — Add four missing restore helpers

Added at module level, directly after `_restore_dict_tuple`, in symmetry-order with the `_serialize_dict_*` helpers:

```text
_restore_dict_tuple4_int(items)             — mirrors _serialize_dict_tuple4_int
_restore_dict_int_set(items)                — mirrors _serialize_dict_int_set
_restore_dict_int_int(items)                — mirrors _serialize_dict_int_int
_restore_dict_int_list_dataclass(items, from_dict)
                                            — mirrors _serialize_dict_int_list_dataclass
```

#### S2 — Rewrite from_snapshot body

Replaced 4 inline dict-comprehensions (17 LOC across 6 state attrs) with 4 helper calls (~10 LOC across 6 state attrs):

```text
Before:
  4 inline dict-comprehensions
  body 45 LOC

After:
  4 helper calls (matching to_snapshot's helper pattern)
  body 34 LOC
```

Restore order preserved exactly. No reordering of attribute restoration.

---

## Helper symmetry (completed)

```text
_serialize_dict_int_dataclass         ↔  _restore_dict_int
_serialize_dict_tuple_dataclass       ↔  _restore_dict_tuple
_serialize_dict_tuple4_int            ↔  _restore_dict_tuple4_int             (new)
_serialize_dict_int_set               ↔  _restore_dict_int_set                (new)
_serialize_dict_int_int               ↔  _restore_dict_int_int                (new)
_serialize_dict_int_list_dataclass    ↔  _restore_dict_int_list_dataclass      (new)
```

Note: `_restore_dict_int` and `_restore_dict_tuple` use slightly different naming (no `_dataclass` suffix) because they take an additional `from_dict` factory argument. Their `_serialize_dict_*_dataclass` counterparts encode the dataclass type via `asdict`. Function-naming asymmetry, but shape-class symmetry is exact.

```text
6 serialize helpers × 6 restore helpers
perfect symmetry
```

---

## from_snapshot body (post-S2)

```python
@classmethod
def from_snapshot(cls, snapshot: dict[str, Any]) -> "Engine":
    snapshot = _migrate_snapshot_to_current(snapshot)
    engine = cls()
    engine._next_id = dict(snapshot.get("next_id", {}))
    engine._lifecycle_seq = snapshot.get("lifecycle_seq", 0)
    engine._entities = _restore_dict_int(snapshot["entities"], _entity_from_dict)
    engine._observations = _restore_dict_int(snapshot["observations"], _observation_from_dict)
    engine._claims = _restore_dict_int(snapshot["claims"], _claim_from_dict)
    engine._evidences = _restore_dict_int(snapshot["evidences"], _evidence_from_dict)
    engine._relations = _restore_dict_int(snapshot["relations"], _relation_from_dict)
    engine._gaps = _restore_dict_int(snapshot["gaps"], _gap_from_dict)
    engine._rule_definitions = _restore_dict_tuple(snapshot["rule_definitions"], _rule_def_from_dict)
    engine._rule_stats = _restore_dict_tuple(snapshot["rule_stats"], _rule_stats_from_dict)
    engine._gap_dedup_index = _restore_dict_tuple4_int(snapshot["gap_dedup_index"])
    engine._claim_gap_refs = _restore_dict_int_set(snapshot["claim_gap_refs"])
    engine._gap_resolutions = _restore_dict_int_int(snapshot["gap_resolutions"])
    engine._contradictions = _restore_dict_int_set(snapshot["contradictions"])
    engine._resolved_contradictions = _restore_dict_int_set(
        snapshot["resolved_contradictions"],
    )
    engine._claim_lifecycle_events = _restore_dict_int_list_dataclass(
        snapshot["claim_lifecycle_events"],
        lambda d: ClaimLifecycleEvent(**d),
    )
    engine._hint_evidence_types = set(snapshot["hint_evidence_types"])
    return engine
```

17 state attributes, each restored by a single line — mirrors `to_snapshot` exactly.

---

## O6 retirement

§46.12 candidate O6 (compute_effective_confidence method split) was retired at PR35-O7 entry timing.

```text
Original §46.12 O6 proposal (141차):
  Split the 110-LOC compute_effective_confidence into:
    compute_effective_confidence(claim_id)      — public entry (~5 LOC)
    _compose_effective_confidence(claim)         — formula composition (~20 LOC)

Status after PR34-O O3 (142차):
  compute_effective_confidence body shrank to 11 LOC
  (clean 6-helper × base composition).

  Body now reads:
    self._assert_claim_exists(claim_id)
    claim = self._claims[claim_id]
    return ScoreValue(
        claim.base_confidence.value
        * self._status_modifier_for_claim(claim_id)
        * self._freshness_modifier_for_claim(claim_id)
        * self._gap_modifier_for_claim(claim_id)
        * self._count_modifier_for_claim(claim_id)
        * self._rule_stats_modifier_for_claim(claim_id)
        * self._evidence_type_modifier_for_claim(claim_id)
    )

Retirement reason:
  Splitting an 11-LOC body into a 5-LOC public entry + 8-LOC private
  helper would add indirection without reducing complexity. The split
  goal (readability of the composition) was already achieved by O3.

  Reactivation criterion:
  If a trace-emitting variant (e.g., compute_effective_confidence_with_trace)
  becomes necessary, a _compose_effective_confidence helper may then be
  extracted to share with the trace variant. That would be a separate
  PR with explicit justification, not a follow-up of O6.
```

§46.12 final status:

```text
O1   executed in PR34-O Scope O-mid
O2   executed in PR34-O Scope O-mid
O3   executed in PR34-O Scope O-mid
O4   executed in PR34-O Scope O-mid
O5   executed in PR34-O Scope O-mid (no-op confirmation)
O8   executed in PR34-O Scope O-mid
O6   retired by PR35-O7 §47.11 (subsumed by O3)
O7   selected by PR35-O7, executed as S1+S2
```

All 8 §46.12 candidates resolved: 7 executed, 1 retired.

---

## Implementation footprint

Changed files (across 144차 + 145차 + 146차):

```text
docs/contracts/05_DATA_CONTRACT_MVP.md             +451 lines (§47)
ragcore/engine.py                                  +57 / -22 (net +35)
docs/dev/PR_035_SNAPSHOT_RESTORE_REFACTOR_MVP.md   this record (146차)
```

Unchanged:

```text
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
ragcore/rule_compile.py / rule_loader.py / rule_gap.py / rule_runtime.py / condition.py
all test files
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

No public API change:

```text
ragcore.__all__ still 48 symbols  (PR31-S frozenset preserved)
no method rename
no method removal
no method addition (no public)
no deprecated alias
docstring coverage still 40/40 (PR33-M baseline preserved)
modifier signature consistency preserved (PR34-O baseline)
```

No report shape change:

```text
PR32-V *_KEYS frozensets all unchanged
```

No snapshot output / input shape change:

```text
to_snapshot output shape unchanged
from_snapshot accepted input shape unchanged
migration framework (_migrate_snapshot_v1_to_v2 / _migrate_snapshot_to_current) unchanged
```

---

## Boundary preservation table

| Preserved boundary                                       | PR35-O7 effect                       | Status      |
| -------------------------------------------------------- | ------------------------------------ | ----------- |
| Sub-decision D (types / rule_output unchanged)           | engine.py module-level helpers only  | preserved   |
| Sub-decision AF (HINT taxonomy framework-external)       | unchanged                             | preserved   |
| PR17 snapshot schema v2                                  | unchanged                             | preserved   |
| PR21-L hint validation (caller-registered)               | unchanged                             | preserved   |
| PR27-P consumer call boundary (§39)                      | unchanged                             | preserved   |
| PR28-O rule version pinning                              | unchanged                             | preserved   |
| PR29-R observed_precision bounded no-boost               | unchanged                             | preserved   |
| PR30-P consumer policy guides (§42)                      | unchanged                             | preserved   |
| PR31-S AI-readable usage recipe (§43)                    | unchanged                             | preserved   |
| PR31-S method surface freeze (48 symbols)                | preserved bit-for-bit                | preserved   |
| PR32-V report surface (§44)                              | unchanged                             | preserved   |
| PR32-V SNAPSHOT_METADATA_KEYS invariant                  | schema_version still 2 + 17 attrs   | preserved   |
| PR33-M docstring coverage (40/40)                        | unchanged                             | preserved   |
| PR33-M __all__ 12-group ordering                         | unchanged                             | preserved   |
| PR34-O modifier signature consistency (6 helpers)        | unchanged                             | preserved   |
| PR34-O defensive check helpers (6)                       | unchanged                             | preserved   |
| 7-modifier formula                                        | unchanged                             | preserved   |
| modifier value behavior                                  | unchanged (bit-for-bit)              | preserved   |
| effective_confidence output                              | unchanged (1089 tests identical)     | preserved   |
| Migration framework (PR18-K / PR21-L)                    | unchanged                             | preserved   |
| Internal symmetry (serialize/restore helpers)            | completed (was 6/2, now 6/6)         | **newly cleaned** |

---

## Test result

Final test result before merge:

```text
1089 passed, 0 failed
```

Delta:

```text
1089 -> 1089
no test added
no test removed
no test modified
```

Regression:

```text
0
```

Natural-expiry:

```text
0
```

The existing PR17 snapshot round-trip tests + PR32-V snapshot_metadata invariants + 1089 baseline lock the behavior. PR35-O7 preserved every output bit.

---

## Verification snapshot

After 145차:

```text
ragcore.__all__              48 symbols (PR31-S baseline preserved)
unique symbols                48 (no duplicates)
Engine public methods         40 (PR33-M baseline preserved)
no-docstring methods           0 (PR33-M coverage preserved)
schema_version                  2 (PR21-L preserved)
test suite                   1089 passing, 0 fail
engine.py LOC               1800 (was 1765, +35 net)
_serialize_dict_* helpers      6
_restore_dict_* helpers        6 (was 2, +4 from S1)
symmetry shape pairs           6 / 6 (perfect)
from_snapshot body LOC        34 (was 45)
to_snapshot body LOC          23 (unchanged)
to_snapshot / from_snapshot ratio  1.48x (was 1.96x)
```

---

## Self-review

### What this PR does

PR35-O7 is the second internal refactor PR after PR34-O. The actual changes:

```text
- 4 new _restore_dict_* helpers added (S1)
- 4 inline dict-comprehensions replaced by helper calls (S2)
- from_snapshot body shrank from 45 to 34 LOC
- 6 serialize / 6 restore symmetry achieved
- §46.12 candidate O6 formally retired
```

### What this PR does not do

PR35-O7 does not:

```text
change snapshot schema (still v2)
change to_snapshot output shape
change from_snapshot accepted input shape
change migration framework
change lifecycle / contradiction / rule_output / confidence logic
change public API surface
rename any method (public or private)
add any test
modify any test
modify types.py
modify rule_output.py
modify __init__.py
execute any future candidate beyond O7 (V-cerberus / P4-P6 / R-fpr / G / J / Q / S-extension)
```

### Why the audit-first approach paid off

The audit (§47) corrected the original O7 framing. Without audit-first:

```text
A naive O7 execution would have created per-kind helpers
(_load_entities, _load_claims, _load_evidences, etc.) that
mostly wrap existing _restore_dict_int calls in 1-line wrappers.
That would add 6-8 helper definitions but no real structural value.

The audit identified the real asymmetry source: 4 missing
_restore_dict_* helpers (not per-kind helpers). The corrected
refactor adds 4 helpers and completes 6/6 symmetry. Smaller
change, larger structural benefit.
```

The audit-first pattern (PR33-M / PR34-O / PR35-O7) keeps refactoring honest by measuring before executing.

---

## Final meaning

PR35-O7 is not a feature PR.
PR35-O7 is not a snapshot schema PR.
PR35-O7 is a restore-path readability and symmetry refactor.

```text
Before PR35-O7:
  to_snapshot:   6 _serialize_dict_* helpers, perfectly symmetric
  from_snapshot: 2 _restore_dict_* helpers + 4 inline dict-comprehensions
  Ratio: 1.96x asymmetric body lengths

After PR35-O7:
  to_snapshot:   6 _serialize_dict_* helpers, same as before
  from_snapshot: 6 _restore_dict_* helpers, perfectly symmetric
  Ratio: 1.48x (still slightly larger because from_snapshot's
                 17 state attrs > to_snapshot's 18 keys with
                 some helper call multi-line wrapping)
```

The Engine remains a domain-light judgment core.
The consumer surface remains unchanged.
The snapshot schema remains v2.
The internal serialize/restore symmetry is now complete.

```text
PR27-P  §39  call boundary
PR30-P  §42  read boundary
PR31-S  §43  usage recipe
PR32-V  §44  report surface
PR33-M  §45  method surface audit (surface domain)
PR34-O  §46  internal optimization audit (internal domain)
PR35-O7 §47  snapshot restore refactor (snapshot restore domain)
```

§46.12 candidate enumeration fully resolved (7 executed, 1 retired).

---

## Next candidates after PR35-O7

The §46.12 enumeration is now closed. Remaining future candidates:

```text
V-cerberus thin adapter (다른 repo, framework 변경 0)
P4 / P5 / P6 (PR33-M에서 deferred)
  P4 Naming consistency rename (evidence_freshness / gap_resolution)
  P5 Tier 3 sub-module reorganization (ragcore.trace.*)
  P6 Engine.claim_report convenience method
R-fpr / G / J / Q / S-extension
  R-fpr   false_positive_rate modifier (PR29-R 자연 후속)
  G       superseded/retracted lifecycle (Sub-decision D 변경)
  J       multi-rule claim composition
  Q       rule_stats outcome ratio
  S-extension  8th modifier
visual / method surface presentation work (PR32-V 의 §44 위에 확장)
additional optimization only if a measured target emerges
```

Sub-decision D, AF, and the §42 / §43 / §44 / §45 / §46 / §47 letter-code namespaces continue to constrain future PRs.
