# PR73-M04 — Engine State Identity Primitive MVP

Development record for the first runtime PR in the M-series
(branch `feat/engine-state-identity-primitive`). PR73-M04
implements the §1.1 / §2 / §4 / §5 surface of the M03
architecture contract by introducing a minimal Engine state
identity primitive: a per-Engine opaque lineage token and a
completed-mutation revision counter, exposed as a read-only
`Engine.state_identity()` returning a frozen
`EngineStateIdentity` value type.

```
base:            main 7ce41b3 (PR72-M03 — Engine Read
                                Consistency Contract)
branch:          feat/engine-state-identity-primitive
241차 commit:    86ce33e   docs(contract): define Engine state
                            identity primitive
242차 commit:    b6bcdde   test(core): lock Engine state
                            identity invariants
243차 commit:    9aa65dc   feat(engine): add Engine state
                            identity primitive
244차 commit:    e352ec4   docs(dev): record PR73-M04 Engine
                            state identity primitive MVP
                            (initial pre-review checkpoint)
245차 commit:    2456149   fix(engine): close state identity
                            audit gaps (C1 ~ C7 post-review
                            correction)
246차 commit:    docs(dev): reconcile M04 final audit record
                            (this record, docs-only final
                            cleanup — current revision)
type:            framework-level runtime change, additive only;
                  no judgment-semantics delta, no snapshot
                  schema change, no PR51 packet shape change.

The §2 ~ §13 sections of this record were authored as the
244차 pre-review checkpoint with the four-commit cycle and
1501 / +78 totals; §14 records the 245차 audit correction;
§15 records the 246차 documentation reconciliation and is
authoritative for the final branch totals (1517 / +94 across
the six-commit history).
```

PR73-M04 is the first M-series PR that touches `ragcore/`. The
mechanism it introduces is intentionally narrow: it makes it
possible for a caller that holds two `EngineStateIdentity`
values from the same `Engine` to mechanically conclude whether
the Engine state visible at capture-time was the same Engine
state visible at use-time. PR73-M04 does **not** introduce
CAPTURE_BOUND semantics, does **not** stamp PR51 packets,
does **not** stale-mark stored packets, does **not** modify
M02, and does **not** open OC-B (PR74-M05).

Any future packet-binding or comparison helper built on top of
M04 is **separate, explicitly-directed future work, not assigned
to any of M06-M09 and not automatically scheduled** — see §12.

---

## §1 Origin

PR72-M03 §15 sketches the semantic requirements of a future
state-identity mechanism: per-Engine lineage separation,
revision advance discipline tied to completed logical mutations
(not invocation count), snapshot exclusion, and explicit
non-claims on freshness and atomicity. PR72-M03 deliberately
declines to introduce the mechanism itself; it only describes
the boundary the mechanism must respect.

PR73-M04 activates the conditional M04 slot by implementing
exactly that mechanism — and nothing more. The M01-locked
M-series plan is preserved unchanged:

```
PR74-M05  Operator Decision Record / stale revalidation  (OC-B)
PR75-M06  Downstream Result Re-entry                     (OC-E)
PR76-M07  Effective Confidence Calculation Trace         (OC-D)
PR77-M08  Complete Domain-Neutral Reference Operation    (OC-F)
PR78-M09  RuleStats Update Provenance                    (OC-G)
```

PR74-M05 ~ PR78-M09 all remain NOT STARTED.

The acceptance criteria stated upfront in the directive:

```
1. Engine 의 judgment semantics 변경 없음
2. snapshot schema_version 변경 없음
3. snapshot top-level 18 keys 변경 없음
4. PR51 packet 7-key shape 변경 없음
5. M02 미수정
6. M03 정신 보존: state_identity = mechanism, NOT freshness
7. examples/* 무수정
8. pyproject.toml 무수정
9. 모든 baseline test (1423) 유지
10. 새 test 78 추가, 1501 passing (244차 pre-review checkpoint)
11. EngineStateIdentity / Engine.state_identity 만 추가
12. __all__ 48 → 49, public methods 40 → 41
13. private methods 18 → 19 (_advance_state_revision)
14. failure / no-op / read-only call → revision 불변
```

The initial four-commit cycle (241~244차) implemented the M04
surface. The 245차 post-review correction closed the audit
findings, bringing the verified branch total to 1517 tests (see
§15 for the consolidated final accounting). The PR is opened as
Draft and has not been merged; closure language is deferred
until squash merge.

---

## §2 P-series + M-series frozen baseline

```
main at PR73-M04 start:      7ce41b3fa8ed2d9febb357733ce55a2ffa1e08c9
tests:                        1423 passing
Engine public methods:        40
Engine private methods:       18
ragcore.__all__:              48
snapshot schema_version:      2
snapshot top-level keys:      18
PR51 packet keys:             7
M-series state:               M01 / M02 / M03 CLOSED;
                              M04 CONDITIONAL / not started;
                              M05 ~ M09 NOT STARTED
```

After PR73-M04 244차 pre-review checkpoint:

```
tests:                        1501 passing (= 1423 + 78)
                              [244차 pre-review checkpoint
                               value; superseded by §15 for
                               the final branch total]
Engine public methods:        41 (+ state_identity)
Engine private methods:       19 (+ _advance_state_revision)
ragcore.__all__:              49 (+ EngineStateIdentity)
snapshot schema_version:      2 (UNCHANGED)
snapshot top-level keys:      18 (UNCHANGED, same set)
PR51 packet keys:             7 (UNCHANGED)
M-series state:               M01 / M02 / M03 CLOSED on main;
                              M04 OPEN — DRAFT, NOT MERGED
                                  (this PR);
                              M05 ~ M09 NOT STARTED
```

The final branch totals (after 245차 audit correction and 246차
documentation reconciliation) are consolidated in §15.

---

## §3 Files Changed

### §3.1 Contract (241차, 86ce33e)

```
docs/architecture/ENGINE_STATE_IDENTITY_PRIMITIVE_CONTRACT.md
    +498 (new)
```

The contract pins §0~§10:

- §0 Scope limitation — what this primitive is and is not.
- §1 Public contract — `EngineStateIdentity` (engine_token: str,
  revision: int) + `Engine.state_identity()` read-only method.
- §2 Revision semantics — six always-advancing and fourteen
  conditional mutation rules; one logical mutation = exactly one
  revision step.
- §3 Failure semantics — raised exceptions and idempotent no-ops
  leave the revision unchanged.
- §4 Token allocation — `Engine()` and `from_snapshot()` each
  produce a fresh opaque lineage; the token format is not part of
  the public contract.
- §5 Snapshot exclusion — identity is per-process; it is not
  serialized, not restored, and not derivable from snapshot
  content.
- §6 Atomicity non-claim — the primitive does not promise
  cross-Engine ordering, wall-clock monotonicity, or transaction
  semantics.
- §7 Concurrency non-claim — single-thread per Engine; no locks,
  no memory-model claims.
- §8 Relationship to M02 / M03 / M05 — boundary preservation.
- §9 Non-goals — explicit list of what PR73-M04 does not do.
- §10 Closing position.

### §3.2 Tests (242차, b6bcdde)

```
tests/test_engine_state_identity.py    +821 (new, 78 tests)
                                        [244차 pre-review
                                         checkpoint; §14.8
                                         adds 16 more tests,
                                         §15 records the
                                         final total]
```

15 test classes:

| Class                              | Count | Purpose |
|------------------------------------|------:|---------|
| TestValueType                      | 4     | frozen dataclass shape + equality |
| TestNewEngine                      | 3     | revision = 0 + fresh token + token is str |
| TestStableEquality                 | 2     | repeated state_identity() returns equal value |
| TestLineageSeparation              | 2     | two Engine() instances → distinct tokens |
| TestAlwaysAdvancingMutations       | 6     | one advance per add_entity / add_observation / add_claim / add_evidence / add_relation / register_rule |
| TestConditionalMutations           | 14    | each of 14 conditional methods advances on success path, not on idempotent return |
| TestIdempotentNoops                | 9     | no-op variants leave revision unchanged |
| TestErrorPaths                     | 5     | KeyError / ValueError / TypeError leave revision unchanged |
| TestMultiObjectSingleAdvance       | 2     | one logical mutation = exactly one revision step |
| TestReadOnlyDoesNotAdvance         | 18    | each read-only method, parameterized: revision unchanged |
| TestAddGapDedupSemantics           | 2     | dedup hit + new ref → +1; dedup hit + already-referenced → +0 |
| TestSnapshotExclusion              | 3     | snapshot has no engine_token / revision / state_identity key |
| TestRestoreSemantics               | 3     | from_snapshot → fresh lineage + revision 0 |
| TestPR51PacketUnchanged            | 1     | packet shape preserved exactly |
| TestStructuralCounts               | 4     | public 41 / private 19 / __all__ 49 / EngineStateIdentity present |

### §3.3 Implementation (243차, 9aa65dc)

```
ragcore/types.py        + EngineStateIdentity frozen dataclass
ragcore/__init__.py     + EngineStateIdentity import + __all__ entry
ragcore/engine.py       + uuid4 import
                        + EngineStateIdentity import
                        + Engine.__init__ lineage / revision fields
                        + Engine._advance_state_revision private helper
                        + Engine.state_identity() public method
                        + 20 advance call-sites (6 always + 14 conditional)
tests/test_engine_ai_readable_usage_recipe.py
tests/test_engine_method_call_playbook_usage.py
tests/test_engine_method_surface_freeze.py
tests/test_engine_report_surface.py
tests/test_external_adapter_simulation.py
tests/test_external_engine_inspector.py
tests/test_snapshot_restore_integrity.py
    — additive shifts only:
      Engine public 40 → 41 (added state_identity)
      Engine private 18 → 19 (added _advance_state_revision)
      ragcore.__all__ 48 → 49 (added EngineStateIdentity)
```

No other test file is touched. No `examples/*` file is touched.
`pyproject.toml`, `models/migrations.py` (cerberus-side, not in
this repo), `snapshot_migrations.py`, and snapshot version
constants are not touched.

---

## §4 Mutation-method classification

PR73-M04 classifies the 20 state-mutating public methods from
M02 §12.1 into two groups by directive §7.

### §4.1 Six always-advancing (§2.1)

These methods either succeed (and produce one new entity) or
raise. There is no idempotent no-op path that returns normally
without state change.

| Method            | Site of `_advance_state_revision()` |
|-------------------|-------------------------------------|
| `add_entity`      | after `self._entities[entity_id] = ...` |
| `add_observation` | after `self._observations[obs_id] = ...` |
| `add_claim`       | after `self._claims[claim_id] = Claim(...)` |
| `add_evidence`    | after `self._evidences[evidence_id] = ...` |
| `add_relation`    | after `self._relations[relation_id] = Relation(...)` |
| `register_rule`   | after `self._rule_stats[key] = RuleStats(...)` |

### §4.2 Fourteen conditional (§2.2~§2.6)

These methods may legitimately return without changing state.
The advance call-site is placed on the exact branch where state
actually changes.

| Method | Advance condition |
|--------|-------------------|
| `add_gap` | dedup miss → +1; dedup hit with new `_claim_gap_refs` membership → +1; dedup hit with already-referenced (claim_id, gap_id) → +0 |
| `resolve_gaps_for_evidence` | +1 iff `newly_resolved` is non-empty |
| `register_contradiction` | before `return True`, after the set add; idempotent `return False` → +0 |
| `register_contradiction_resolution` | before final `return True`, after `resolved.add(evidence_id)`; idempotent `return False` → +0 |
| `confirm_claim_if_ready` | before `return True`, after `_record_claim_lifecycle_transition` |
| `refute_claim_if_ready` | before `return True`, after `_record_claim_lifecycle_transition` |
| `dispute_claim_if_ready` | before `return True`, after `_record_claim_lifecycle_transition` |
| `resolve_disputed_claim_if_ready` | before `return True`, after `_record_claim_lifecycle_transition` |
| `refute_disputed_claim_if_ready` | before `return True`, after `_record_claim_lifecycle_transition` |
| `refute_disputed_claim_if_ready_by_freshness` | before `return True`, after `_record_claim_lifecycle_transition` |
| `update_rule_stats` | +1 iff `new_stats != current` |
| `register_hint_evidence_types` | +1 iff `len(self._hint_evidence_types)` changed |
| `unregister_hint_evidence_types` | +1 iff `len(self._hint_evidence_types)` changed |
| `clear_hint_evidence_types` | +1 iff the set was non-empty before the `.clear()` |

The placement matches the True / non-empty return path one-for-one
with the existing lifecycle event append, so an external observer
sees: revision advances ↔ lifecycle event appended ↔ state change
materialized.

### §4.3 Read-only methods (no advance)

The remaining 18 read-only methods plus the new `state_identity()`
method (= 19 total post-M04) advance the revision exactly 0 times.
`TestReadOnlyDoesNotAdvance` parameterizes over 18 of them
explicitly; `state_identity()` itself is covered by
`TestStableEquality`.

---

## §5 Public surface delta

### §5.1 New surface

```
ragcore.types.EngineStateIdentity
    @dataclass(frozen=True)
    engine_token: str
    revision: int
    # value equality; ordered comparison of revision is
    # only meaningful within the same engine_token

ragcore.Engine.state_identity() -> EngineStateIdentity
    # read-only, never raises, never advances the revision
```

### §5.2 No removal, no rename, no resignaturing

- All 40 prior public methods retain identical signatures,
  identical docstrings (where touched, only an
  end-of-docstring note is added if needed; in practice the
  20 mutation methods were instrumented without docstring
  edits).
- All 18 prior private methods retain identical names.
- `ragcore.__all__` is reordered nowhere; `EngineStateIdentity`
  is inserted into the §11~§16 / §23 Core dataclasses group.

### §5.3 Token format

`uuid.uuid4().hex` — a 32-character lowercase hex string. The
format is implementation detail. The test suite checks `isinstance
(token, str)` and `len(token) > 0`, not a regex.

---

## §6 Snapshot identity exclusion

PR73-M04 makes one negative guarantee load-bearing:

```
Engine.to_snapshot() output is byte-identical to the PR72-M03
baseline. Identity is not serialized; not restored; not
derivable from snapshot content.
```

Concrete checks (all enforced by `TestSnapshotExclusion` and
`TestRestoreSemantics`):

- `snap = Engine().to_snapshot()` →
  `"engine_token" not in snap`,
  `"revision" not in snap`,
  `"state_identity" not in snap`,
  `len(snap) == 18`,
  `snap["schema_version"] == 2`.
- `Engine.from_snapshot(snap).state_identity().revision == 0`.
- `Engine.from_snapshot(snap).state_identity().engine_token`
  differs from the originating engine's token (fresh lineage).
- Two consecutive `Engine.from_snapshot(snap)` calls produce
  distinct tokens (fresh lineage per call).

The schema-version field is **not** bumped because the snapshot
shape is genuinely unchanged. A future PR that decides to
persist a lineage would bump it; PR73-M04 does not.

---

## §7 Boundaries explicitly preserved

PR73-M04 preserves every load-bearing boundary established by
the preceding M-series PRs:

- **PR70-M01 (operational scaffold)** — three lanes /
  six status vocab / seven OC tags. PR73-M04 changes none of
  them. The scaffold's status code for OC-C remains UNDEFINED
  at packet binding because PR73-M04 does not introduce
  CAPTURE_BOUND packet binding. Any such wiring would be
  separate, explicitly-directed future work — it is **not**
  re-assigned to PR75-M06, which retains its M01-locked scope
  of Downstream Result Re-entry (OC-E).
- **PR71-M02 (reviewed mutation handoff)** — RoleAssignment →
  EngineInputCandidate → ReviewedMutationRequest → explicit
  invocation. PR73-M04 does not touch any of the 4 layers and
  does not introduce any new mutation entry point.
- **PR72-M03 (read consistency contract)** — four identity
  concepts (§4.1~§4.4), two-axis vocabulary (§7.1~§7.3),
  CAPTURE_BOUND requirements (§8), CURRENTLY_MATCHED
  requirements (§9), stale (§10), M02/M03 distinction (§11),
  PR51 packet preservation (§13), future mechanism semantic
  requirements (§15). PR73-M04 implements exactly the §1.1 /
  §2 / §4 / §5 surface required by §15 and nothing else.

In particular:

- **PR51 packet** remains UNBOUND + UNKNOWN. PR73-M04 does
  **not** add `state_identity` (or anything else) to the packet.
  The packet's 7 keys (`claim`, `effective_confidence`,
  `supporting_evidence`, `contradictions`,
  `active_contradictions`, `unresolved_gaps`,
  `lifecycle_history`) are byte-identical to PR72-M03
  baseline.
- **§52 validator** is untouched. Snapshot restore integrity
  is not extended to validate any identity field.
- **§53 evidence three-layer semantics** are untouched.
- **§54 rule reference / Gap ownership / shared Gap dedup**
  are untouched.
- **6 lifecycle `_if_ready` methods** retain identical
  transition conditions, identical thresholds
  (`_REFUTATION_STRENGTH_THRESHOLD = 0.8`), identical
  lifecycle event payloads.
- **7-modifier formula** retains identical composition.
- **`from_snapshot` restore order** retains the §52 fail-fast
  property; the new lineage allocation runs in `__init__`
  which is called before any state population.

---

## §8 Repository-wide forbidden-vocabulary scan

The directive declares specific phrasings off-limits for this
PR:

| Forbidden token | Reason | Scan result |
|-----------------|--------|-------------|
| `packet_revision` | M03 §6 / §10 — UNBOUND today | 0 in ragcore/ |
| `state_revision` | M03 §15 vocabulary trap | 0 in ragcore/ outside docstrings |
| `engine_revision` | M03 §15 vocabulary trap | 0 in ragcore/ |
| `snapshot_digest` | M03 §4.1 conflation trap | 0 in ragcore/ |
| `capture_token` | M03 §7.2 axis confusion | 0 in ragcore/ |
| `stale_at` / `is_stale` | M03 §10 — mechanically unavailable | 0 in ragcore/ |
| `freshness` (as method name) | M03 — not a freshness signal | only PR11-A `evidence_freshness` (preserved) |

The implementation uses only `engine_token` and `revision` as
field names — both inherited from the M03 §15 / §4.2
vocabulary, both already locked in the contract.

`EngineStateIdentity` is described in code and tests as an
**identity primitive** / **identity value** / **lineage and
revision pair**. It is never described as a freshness signal,
a snapshot digest, a transaction id, or a hash.

---

## §9 Structural and behavioral invariants

### §9.1 Structural counts

```
Engine public methods            40 → 41   (+state_identity)
Engine private methods           18 → 19   (+_advance_state_revision)
ragcore.__all__                  48 → 49   (+EngineStateIdentity)
snapshot schema_version           2  =  2
snapshot top-level keys          18 =  18  (same set)
PR51 packet keys                  7  =  7  (same set, same order)
RuleStats.confirmed_true_count    PR2 baseline preserved
_REFUTATION_STRENGTH_THRESHOLD    0.8 preserved
_status_modifier table            7 entries preserved
test count                        1423 → 1501 (+78)
                                  [244차 pre-review checkpoint;
                                   §15 records final 1517 / +94]
```

### §9.2 Behavioral invariants (delta = 0)

```
judgment semantics                  delta = 0
claim lifecycle condition           delta = 0
effective-confidence formula        delta = 0
modifier value table                delta = 0
Gap matching / resolution semantics delta = 0
contradiction semantics             delta = 0
RuleStats calculation               delta = 0
PR51 packet shape                   delta = 0
snapshot schema                     delta = 0
dependency surface                  delta = 0
```

### §9.3 New invariants pinned by tests

This inventory was authored as the 244차 pre-review checkpoint
(78 tests across the classes listed below). §14.8 records the
245차 additions (16 more tests across two new classes plus the
real-call coverage adjustment to `TestReadOnlyDoesNotAdvance`).
§15 records the consolidated final test inventory.

```
fresh-lineage on Engine()              TestNewEngine
fresh-lineage on from_snapshot()       TestRestoreSemantics
two Engine() → distinct tokens         TestLineageSeparation
6 always-advance methods               TestAlwaysAdvancingMutations
14 conditional methods                 TestConditionalMutations
9 idempotent no-ops                    TestIdempotentNoops
5 error paths preserve revision        TestErrorPaths
18 read-only methods preserve revision TestReadOnlyDoesNotAdvance
                                       [245차 §14.8: real-call
                                        coverage now 19/19]
add_gap dedup semantics                TestAddGapDedupSemantics
multi-object single advance            TestMultiObjectSingleAdvance
snapshot exclusion (3 keys absent)     TestSnapshotExclusion
PR51 packet unchanged                  TestPR51PacketUnchanged
```

---

## §10 Regression result

The result below is the 244차 pre-review checkpoint
(post-implementation, pre-audit). §15 records the consolidated
final regression result for the verified branch.

```
$ python -m pytest -q
....................................................................
....................................................................
[...]
1501 passed in 2.31s
```

```
$ python -c "import ragcore, inspect, ast; \
    from ragcore import Engine; \
    print(sum(1 for n,_ in inspect.getmembers(Engine, callable) \
        if not n.startswith('_')))"
41

$ python -c "import ragcore; print(len(ragcore.__all__))"
49

$ python -c "from ragcore import Engine; \
    snap = Engine().to_snapshot(); \
    print(len(snap), snap['schema_version'])"
18 2
```

All 1423 baseline tests continue to pass with no edit to their
expectations except the seven structural-freeze files listed in
§3.3. All 78 new tests pass.

---

## §11 Self-review (29-point checklist)

```
[x]  1. PR73-M04 is additive only at ragcore.__all__.
[x]  2. PR73-M04 is additive only at Engine public surface.
[x]  3. PR73-M04 is additive only at Engine private surface.
[x]  4. snapshot schema_version unchanged.
[x]  5. snapshot top-level key set unchanged.
[x]  6. PR51 packet shape unchanged.
[x]  7. §52 snapshot validator untouched.
[x]  8. §53 evidence three-layer semantics untouched.
[x]  9. §54 rule reference / Gap ownership / shared Gap dedup
        untouched.
[x] 10. PR70-M01 scaffold untouched.
[x] 11. PR71-M02 4-layer handoff untouched.
[x] 12. PR72-M03 architecture contract untouched (except a
        forward reference is allowed; not introduced here).
[x] 13. M02 §12.1 read-only method list grows from 18 to 19
        by the additive state_identity entry; no read-only
        method was reclassified as mutating, no mutating method
        was reclassified as read-only.
[x] 14. 6 always-advancing methods: every success path advances
        exactly once.
[x] 15. 14 conditional methods: every success path advances
        exactly once, every idempotent no-op does not advance.
[x] 16. Every method that raises leaves revision unchanged.
[x] 17. Engine() produces a fresh lineage.
[x] 18. from_snapshot() produces a fresh lineage with
        revision = 0.
[x] 19. Two Engine() instances produce distinct lineages.
[x] 20. state_identity() never raises.
[x] 21. state_identity() never advances the revision.
[x] 22. Repeated state_identity() calls on the same Engine in
        the same state return equal values.
[x] 23. EngineStateIdentity is a frozen dataclass with exactly
        two fields (engine_token: str, revision: int).
[x] 24. EngineStateIdentity supports value equality and
        hashing.
[x] 25. Engine.to_snapshot() has no engine_token / revision /
        state_identity key.
[x] 26. uuid.uuid4() is used only once per Engine __init__
        and once per from_snapshot.
[x] 27. The advance helper is private (_advance_state_revision)
        and not exported.
[x] 28. examples/* not touched.
[x] 29. pyproject.toml not touched.
```

---

## §12 Forward boundary

The M01-locked M-series plan is preserved verbatim. PR73-M04
does **not** re-assign M06-M09 to identity-mechanism follow-ups.

```
PR74-M05  Operator Decision Record / stale revalidation  (OC-B)
PR75-M06  Downstream Result Re-entry                     (OC-E)
PR76-M07  Effective Confidence Calculation Trace         (OC-D)
PR77-M08  Complete Domain-Neutral Reference Operation    (OC-F)
PR78-M09  RuleStats Update Provenance                    (OC-G)
```

Items that *may* become explicitly-directed future work on top
of M04 but are **not** assigned to any M06-M09 slot and **not**
automatically scheduled:

- A future CAPTURE_BOUND packet binding (OC-C closure) — would
  wire `state_identity()` into the packet builder under M03 §6
  conditions. Separate, explicitly-directed future work.
- A future CURRENTLY_MATCHED comparison helper — could be a
  thin pure-function on top of two `EngineStateIdentity`
  values. Separate, explicitly-directed future work.
- A stale-determination API — explicitly forbidden by M03 §10
  at this stage.
- Cross-Engine ordering — explicitly forbidden by M03 §15.

Each of those is reachable from the M04 primitive without
schema migration. None is reachable from the snapshot, by
design.

---

## §13 Closing position

> *PR73-M04 introduces the smallest possible mechanism that
> turns the M03 read-consistency vocabulary into something an
> external caller can actually use. The mechanism is one frozen
> value type, one read-only method, one private advance helper,
> a token allocator in `__init__`, and one advance call-site
> per logical mutation. Other read-consistency capabilities
> discussed by M03 — such as packet binding or mechanical
> comparison helpers — are separate explicitly-directed future
> work unless already assigned by the M01 plan. PR73-M04 stays
> as small as M03 demands and as additive as the
> structural-freeze tests require.*

Explicit separation of responsibilities at the M04 boundary:

```
M05 (PR74-M05):
  operator decision record / stale revalidation policy
  — M01-locked OC-B responsibility, unchanged

separate, unscheduled work (NOT assigned to M06-M09):
  CAPTURE_BOUND packet binding
  CURRENTLY_MATCHED helper
  mechanical stale-availability mechanism

M06-M09 (PR75-M06 ~ PR78-M09):
  M01-locked responsibilities unchanged
  (downstream re-entry / effective-confidence trace /
   complete domain-neutral reference operation /
   RuleStats provenance)
```

PR73-M04 is opened as **Draft** and is **not** merged. Closure
language (`CLOSED`) is reserved for the post-squash-merge state.
The M-series sequence after PR73-M04:

```
PR73-M04   Engine state identity primitive
           OPEN — DRAFT, NOT MERGED
PR74-M05   Operator Decision Record /
           stale revalidation              (OC-B) NOT STARTED
PR75-M06   Downstream Result Re-entry      (OC-E) NOT STARTED
PR76-M07   Effective Confidence Trace      (OC-D) NOT STARTED
PR77-M08   Complete Domain-Neutral
           Reference Operation             (OC-F) NOT STARTED
PR78-M09   RuleStats Update Provenance     (OC-G) NOT STARTED
```

No automatic next PR. Framework waits for directive.

---

## §14 Post-review correction — 245차

PR73-M04 is held in Draft for post-review correction. The 245차
commit `fix(engine): close state identity audit gaps` lands seven
audit-defect corrections without amending or rebasing 241~244차.

### §14.1 C1 — failed allocation partial mutation

`add_claim` and `add_evidence` previously called `_allocate_id`
**before** instantiating `ScoreValue`. An invalid score would then
raise after the id counter had advanced, leaving:

```
_next_id           advanced
state revision     unchanged
to_snapshot()      changed (because the snapshot includes
                    next_id under the "next_id" top-level key)
registered object  absent
```

That violated the §1 contract that *equal `EngineStateIdentity`
implies equal observable Engine logical state*. Two engines could
end up with the **same `EngineStateIdentity` but a different
serialized Engine state** — the identity surface said "same",
while `to_snapshot()` said "different" by one id step.

**Note on the 245차 commit message.** The 245차 commit message
phrase implying that the pre-fix `to_snapshot()` stayed unchanged
was imprecise. Because `to_snapshot()` includes `next_id`, the
pre-fix failed call **did** change the snapshot while leaving
`EngineStateIdentity` unchanged. The 245차 commit message is not
amended (history rewrite forbidden by directive); **this dev
record is the authoritative correction** of the pre-fix
characterization.

The fix moves `ScoreValue(...)` admission to **before**
`_allocate_id` in both methods. After the fix, an invalid score
leaves `_next_id`, `to_snapshot()`, and `state_identity()` all
unchanged.

Six-always-changing methods re-audit. Among the id-allocating
methods, `add_entity`, `add_observation`, and `add_relation` have
no post-allocation dataclass admission (their dataclasses have no
`__post_init__`). `register_rule` does not allocate an id at all
— it registers `(rule_id, rule_version)` keyed entries that the
caller supplies. `add_gap` is a conditional mutation that already
validates `severity` before allocation. Only `add_claim` and
`add_evidence` needed the validation-order fix:

| Method | Constructor admission | Post-allocate hazard |
|--------|----------------------|----------------------|
| `add_entity` | none (Entity has no `__post_init__`) | none |
| `add_observation` | none (Observation has no `__post_init__`) | none |
| `add_claim` | `ScoreValue(base_confidence)` | **fixed** (validated before allocate) |
| `add_evidence` | `ScoreValue(strength)` | **fixed** (validated before allocate) |
| `add_relation` | none (Relation has no `__post_init__`) | none |
| `add_gap` | `ScoreValue(severity)` | already correct (validated before allocate) |

Validation order for both fixed methods:

```
add_claim
  subject existence
  claim status admission (§51)
  base_confidence validation (§3 C1)
  ID allocation
  Claim storage
  revision +1 (§2.1)

add_evidence
  claim existence
  strength validation (§3 C1)
  ID allocation
  Evidence storage
  revision +1 (§2.1)
```

Failure invariants enforced by `TestFailedAllocationDoesNotConsumeId`:

- `state_identity()` unchanged
- `to_snapshot()` unchanged
- next successful add_claim / add_evidence call does **not** skip
  an id (consecutive integer allocation preserved)

### §14.2 C2 — M-series responsibility drift

Earlier drafts of the dev record and PR body re-assigned M06-M09
to identity-mechanism follow-ups
(`CAPTURE_BOUND packet` / `CURRENTLY_MATCHED comparison` /
`stale determination` / `reserved`). The 245차 correction restores
the M01-locked plan:

```
PR74-M05  Operator Decision Record / stale revalidation  (OC-B)
PR75-M06  Downstream Result Re-entry                     (OC-E)
PR76-M07  Effective Confidence Calculation Trace         (OC-D)
PR77-M08  Complete Domain-Neutral Reference Operation    (OC-F)
PR78-M09  RuleStats Update Provenance                    (OC-G)
```

Any future packet binding or comparison helper built on M04 is
**separate, explicitly-directed future work, not assigned to any
M06-M09 slot, and not automatically scheduled**. See §12.

### §14.3 C3 — `_claim_gap_refs` index wording

§2.2 of the contract previously wrote
`_claim_gap_refs[gap_id]` for the "current Claim already
references this Gap" branch. The actual structure is
`claim_id -> set[gap_id]`, so the correct membership check is
`gap_id in _claim_gap_refs[claim_id]`. The contract wording is
updated; the runtime code was already correct and is unchanged.

### §14.4 C4 — M02 / M03 post-M04 addenda

`ENGINE_READ_CONSISTENCY_CONTRACT.md` (M03) and
`REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md` (M02) gain post-M04
addenda (M03 §19 / M02 §23). The historical M03 §1-§18 baseline
investigation and M02 §1-§22 four-layer model are preserved
verbatim.

M03 §19 records:

```
- M03 baseline state had no mechanized Engine state identity.
- After PR73-M04 merges, EngineStateIdentity and
  state_identity() exist.
- That mechanism alone does NOT lift PR51 packets out of
  UNBOUND + UNKNOWN.
- The current PR51 packet remains UNBOUND + UNKNOWN.
- Atomic capture (§6) and packet binding (§8) are NOT provided
  by PR73-M04.
- CURRENTLY_MATCHED (§9), STALE (§10), and stale-rejection
  policy remain out of scope.
```

M02 §23 records the post-M04 public surface count
(20 state-mutating / 19 read-only / 2 serialization = 41 total)
without overwriting the §12.1 historical baseline of 40 methods
on `main` `896e01e`. `state_identity` is classified explicitly as
**read-only / NOT a M02 mutation candidate target / NOT eligible
to appear in a ReviewedMutationRequest / NOT instrumented to
advance the revision**.

### §14.5 C5 — `EngineStateIdentity` strict admission

The public value type previously accepted any (token, revision)
pair a caller chose to construct. The 245차 fix adds a strict
`__post_init__` admission:

```
engine_token:
  type(value) is str           — wrong type → TypeError
  len(value) > 0                — empty token → ValueError

revision:
  type(value) is int            — wrong type → TypeError (bool
                                   rejected even though
                                   isinstance(True, int) is True)
  value >= 0                    — negative → ValueError
```

`Engine.state_identity()` continues to return admissible values
under the normal Engine path. `TestEngineStateIdentityAdmission`
covers the admission branches in nine test methods, including
the Engine-returned-value sanity check.

### §14.6 C6 — Draft state wording

References to `M04 CLOSED`, `CLOSED (this PR, Draft)`, and
"All fourteen are satisfied by the squashed PR" are replaced
with the Draft-only state:

```
PR73-M04   OPEN — DRAFT, NOT MERGED
```

`CLOSED` is reserved for the post-squash-merge state.

### §14.7 C7 — PR51 packet key names

§7 previously listed the packet's 7 keys as
`(claim, effective_confidence, evidences, contradictions,
active_contradictions, gaps, lifecycle_history)`. The actual
keys emitted by `examples/inspector/engine_inspector.py` are:

```
claim
effective_confidence
supporting_evidence
contradictions
active_contradictions
unresolved_gaps
lifecycle_history
```

The packet runtime code and shape are unchanged. Only the dev
record's listing is corrected to match.

### §14.8 Test surface adjustment

The `TestReadOnlyDoesNotAdvance` parameterization previously
contained one placeholder entry
(`("get_observation_via_existence_only", lambda ...: True)`)
that did not exercise `get_observation`. The 245차 fix:

- enlarges the fixture to also create an `Observation`, a
  `Relation`, and a `Rule` so every read-only method has a
  valid target id;
- replaces the placeholder with a real `get_observation(...)`
  call;
- adds a real `get_relation(...)` call (previously absent);
- removes the broad `except Exception: pass` swallow — a valid
  fixture must let unexpected errors surface as test failures.

Read-only coverage after 245차: all 19 post-M04 read-only public
methods (18 baseline + `state_identity`) exercised via real
calls in the parameterization.

### §14.9 Invariants after 245차

```
Engine public methods            41   (unchanged from 243차)
Engine private methods           19   (unchanged from 243차)
state-mutating public methods    20   (unchanged set; instrumented)
read-only public methods         19   (real-call coverage now 19/19)
serialization boundary            2   (unchanged set)
ragcore.__all__                  49   (unchanged from 243차)
snapshot schema_version           2   (unchanged)
snapshot top-level keys          18   (unchanged set)
PR51 packet keys                  7   (unchanged set, names corrected
                                       in dev record only)
tests                          1517   (1501 prior + 16 in 245차:
                                       6 C1 regression + 9 C5
                                       admission + 1 get_relation
                                       parameterization)
```

Behavioral deltas remain 0 across all ten invariant categories
of §9.2.

Two intended runtime additions:

```
- invalid Claim / Evidence score no longer consumes an ID
- invalid public EngineStateIdentity construction is rejected
```

Both are admission tightening at the boundary, not judgment
semantics change.

### §14.10 245차 file footprint

```
ragcore/engine.py          + C1 validation order fix in
                              add_claim and add_evidence
ragcore/types.py           + EngineStateIdentity.__post_init__
                              strict admission
tests/test_engine_state_identity.py
                            + TestFailedAllocationDoesNotConsumeId
                              (6 tests)
                            + TestEngineStateIdentityAdmission
                              (9 tests)
                            + read-only parameterization fix
                              (placeholder removed, get_relation
                              added, broad except removed)
docs/architecture/ENGINE_STATE_IDENTITY_PRIMITIVE_CONTRACT.md
                            + §2.2 _claim_gap_refs wording fix
docs/architecture/ENGINE_READ_CONSISTENCY_CONTRACT.md
                            + §19 Post-M04 addendum
docs/architecture/REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md
                            + §23 Post-M04 public surface addendum
docs/dev/PR_073_ENGINE_STATE_IDENTITY_PRIMITIVE_MVP.md
                            + §14 (this section)
                            + C2 / C6 / C7 in §1 / §7 / §12 / §13
```

No `examples/*` file is touched. No `pyproject.toml` change. No
other test file's expectations are changed.

---

## §15 Final audit reconciliation — 246차

At 246차 (pre-merge), PR73-M04 was held in Draft for a docs-only
final cleanup (now CLOSED post-merge; see §15.9). The 246차 commit
`docs(dev): reconcile M04 final audit record`
reconciles the dev record and architecture contracts so that
this file accurately describes the verified branch HEAD. No
runtime code, no test code, no `examples/*` file, and no
`pyproject.toml` is touched by 246차.

### §15.1 Six-commit history

```
241차  86ce33e   docs(contract): define Engine state identity
                  primitive
242차  b6bcdde   test(core): lock Engine state identity invariants
243차  9aa65dc   feat(engine): add Engine state identity primitive
244차  e352ec4   docs(dev): record PR73-M04 Engine state identity
                  primitive MVP
                  (initial pre-review checkpoint — §2 ~ §13)
245차  2456149   fix(engine): close state identity audit gaps
                  (C1 ~ C7 post-review correction — §14)
246차  (squashed) docs(dev): reconcile M04 final audit record
                  (docs-only final cleanup — §15. Squashed into the
                   GitHub #74 merge 04f591b; the standalone 246차 SHA
                   was not retained on any ref post-merge. 241~245차
                   SHAs above remain recoverable.)
```

The five preceding commits are **not** amended, rebased, or
squashed. The 245차 commit message phrasing about pre-fix
snapshot state is corrected by §14.1 (this dev record is
authoritative).

### §15.2 Final branch totals (authoritative)

```
baseline tests                 1423   (main 7ce41b3)
initial M04 cycle (241~244차)   +78
post-review correction (245차)  +16
M04 branch total               1517 passing
test delta from baseline       +94
```

Test delta breakdown for 245차:

```
TestFailedAllocationDoesNotConsumeId           6  (C1 regression)
TestEngineStateIdentityAdmission                9  (C5 admission)
TestReadOnlyDoesNotAdvance parameterization
  — get_relation added                          +1
```

### §15.3 Final structural counts

```
Engine public methods          41   (unchanged since 243차)
Engine private methods         19   (unchanged since 243차)
state-mutating public methods  20   (unchanged set; instrumented)
read-only public methods       19   (real-call coverage 19/19)
serialization boundary          2   (unchanged set)
ragcore.__all__                49   (unchanged since 243차)
snapshot schema_version          2   (unchanged)
snapshot top-level keys        18   (unchanged set)
PR51 packet keys                7   (unchanged set, same order)
```

### §15.4 Final regression result

```
$ python -m pytest -q
[...]
1517 passed
$ git diff --check
(clean)
```

### §15.5 246차 file footprint (docs-only)

```
docs/dev/PR_073_ENGINE_STATE_IDENTITY_PRIMITIVE_MVP.md
  — §14.1 pre-fix snapshot wording corrected (R1)
  — top commit block, §2, §3.2, §9.1, §9.3, §10 annotated as
    244차 pre-review checkpoint (R2, R3)
  — §13 closing position rewritten to separate M05 / M06-M09
    from unscheduled future work (R5)
  — §14.1 register_rule re-classified as non-allocator (R6)
  — §14.5 admission test count corrected to nine test methods
    (R7)
  — §15 added (this section)

docs/architecture/ENGINE_STATE_IDENTITY_PRIMITIVE_CONTRACT.md
  — §4.5 / §8.2 M05 process-boundary wording tightened: M05
    persists operator decision record references, NOT Engine
    runtime lineage (R4)

No runtime file is touched. No test file is touched. No
examples/* file is touched. No pyproject.toml change.
```

### §15.6 Repository scan after 246차

```
pre-fix "_next_id advanced + to_snapshot unchanged" residue   0
unqualified final "1501 passed" residue                        0
unqualified final "+78 tests" residue                          0
"four-commit cycle completed all criteria" residue             0
"cross-process Engine lineage persistence = M05" residue       0
"M-series requires CAPTURE_BOUND/CURRENTLY_MATCHED" residue    0
M06-M09 responsibility drift                                   0
_claim_gap_refs[gap_id] residue                                0
M04 CLOSED / CLOSED (this PR, Draft) residue                   0
```

(The scan covers current repository files and the PR body.
The 245차 commit message is preserved as-is in git history.)

### §15.7 246차 invariants

```
tests                          1517   (no test added / removed)
runtime delta from 245차        0
test delta from 245차           0
examples/* delta               0
pyproject.toml delta           0
judgment semantics delta       0
dependency delta               0
packet runtime shape delta     0
snapshot runtime shape delta   0
```

### §15.8 M-series state at 246차 (intermediate, pre-merge)

The table below records the M-series state AT 246차 — before the
GitHub squash merge. It is an explicitly historical intermediate
snapshot, NOT the final merged state (recorded in §15.9 below):

```
P-series   CLOSED
PR70-M01   CLOSED
PR71-M02   CLOSED
PR72-M03   CLOSED
PR73-M04   OPEN — DRAFT, NOT MERGED   (intermediate, at 246차)
PR74-M05   NOT STARTED
PR75-M06   NOT STARTED
PR76-M07   NOT STARTED
PR77-M08   NOT STARTED
PR78-M09   NOT STARTED
```

At that 246차 intermediate point no automatic next PR was
scheduled. The six commits (241~246차) were then squash-merged
into GitHub PR #74.

### §15.9 Original PR73-M04 final merged state (post-merge reconciliation)

```
GitHub PR:              #74
merge mode:             squash
squash merge:           04f591b14b9156bb7b17089ded2670d84745fdd2
merged onto:            7ce41b3  (PR72-M03 squash)
merge date:             2026-06-19  (KST 09:18; UTC 2026-06-19T00:18:03Z)
PR73-M04 status:        CLOSED (merged)
historical tests:       1517 passed
historical Engine:      41 public / 19 private
historical ragcore.__all__: 49
historical snapshot:    schema_version 2 / 18 top-level keys
historical PR51 packet: 7 keys
recoverable commits:    241차 86ce33e / 242차 b6bcdde / 243차 9aa65dc /
                        244차 e352ec4 / 245차 2456149
246차:                  docs-only final cleanup; squashed into 04f591b,
                        standalone SHA not retained on any ref post-merge
```

This post-merge reconciliation block was added by an independent
audit on 2026-06-27 (base `main` faab657). It does not alter M04's
runtime, contract semantics, or the historical 1517 / 41·19 / 49
figures above; later M05~M09 work raised the live repository totals
separately (current `main`: 1999 passed, Engine 42 / 20,
ragcore.__all__ 50).
