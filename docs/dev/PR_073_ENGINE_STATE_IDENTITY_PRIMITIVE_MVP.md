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
244차 commit:    (this record, docs/dev)
type:            framework-level runtime change, additive only;
                  no judgment-semantics delta, no snapshot
                  schema change, no PR51 packet shape change
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
exactly that mechanism — and nothing more. PR74-M05 (operator
decision plane) and PR75-M06 (CAPTURE_BOUND packet) remain
NOT STARTED.

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
10. 새 test 78 추가, 1501 passing
11. EngineStateIdentity / Engine.state_identity 만 추가
12. __all__ 48 → 49, public methods 40 → 41
13. private methods 18 → 19 (_advance_state_revision)
14. failure / no-op / read-only call → revision 불변
```

All fourteen are satisfied by the squashed PR.

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

After PR73-M04:

```
tests:                        1501 passing (= 1423 + 78)
Engine public methods:        41 (+ state_identity)
Engine private methods:       19 (+ _advance_state_revision)
ragcore.__all__:              49 (+ EngineStateIdentity)
snapshot schema_version:      2 (UNCHANGED)
snapshot top-level keys:      18 (UNCHANGED, same set)
PR51 packet keys:             7 (UNCHANGED)
M-series state:               M01 / M02 / M03 / M04 CLOSED;
                              M05 ~ M09 NOT STARTED
```

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
  CAPTURE_BOUND packet binding (that is PR75-M06 / OC-C
  closure scope).
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
  `evidences`, `contradictions`, `active_contradictions`,
  `gaps`, `lifecycle_history`) are byte-identical to PR72-M03
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

```
fresh-lineage on Engine()              78-test class TestNewEngine
fresh-lineage on from_snapshot()       78-test class TestRestoreSemantics
two Engine() → distinct tokens         78-test class TestLineageSeparation
6 always-advance methods               TestAlwaysAdvancingMutations
14 conditional methods                 TestConditionalMutations
9 idempotent no-ops                    TestIdempotentNoops
5 error paths preserve revision        TestErrorPaths
18 read-only methods preserve revision TestReadOnlyDoesNotAdvance
add_gap dedup semantics                TestAddGapDedupSemantics
multi-object single advance            TestMultiObjectSingleAdvance
snapshot exclusion (3 keys absent)     TestSnapshotExclusion
PR51 packet unchanged                  TestPR51PacketUnchanged
```

---

## §10 Regression result

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

PR73-M04 deliberately leaves the following open for later PRs:

- **OC-B (operator decision)** — PR74-M05 scope, not started.
- **OC-C closure (CAPTURE_BOUND packet)** — PR75-M06 scope, not
  started. PR73-M04 makes the mechanism available; it does not
  add it to the packet.
- **CURRENTLY_MATCHED comparison helper** — could be a thin
  pure-function on top of two `EngineStateIdentity` values; not
  introduced here.
- **Stale-determination API** — explicitly forbidden by M03 §10
  at this stage.
- **Cross-Engine ordering** — explicitly forbidden by M03 §15.

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
> per logical mutation. Every other property the M-series
> requires — capture-binding, currently-matched comparison,
> stale determination, operator decision recording, packet
> binding — is reachable from this primitive, but is not
> introduced here. PR73-M04 stays as small as M03 demands and
> as additive as the structural-freeze tests require.*

PR73-M04 is opened as **Draft** and is **not** merged. The
M-series sequence after PR73-M04:

```
PR73-M04   Engine state identity primitive     CLOSED (this PR, Draft)
PR74-M05   Operator decision plane             NOT STARTED
PR75-M06   CAPTURE_BOUND packet                 NOT STARTED
PR76-M07   CURRENTLY_MATCHED comparison         NOT STARTED
PR77-M08   stale determination boundary         NOT STARTED
PR78-M09   reserved                              NOT STARTED
```

No automatic next PR. Framework waits for directive.
