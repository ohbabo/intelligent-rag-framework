# PR_094 — Engine v1 Phase 3B-9: Extract C10 Snapshot Façade Mixin (development record)

GitHub PR **#95** (internal dev-record number = GitHub number − 1 = 094).

## Identity / purpose
Ninth and **final** production-code decomposition under the approved Phase 3A ADR.
A behaviour-preserving move of the four C10 snapshot-façade methods from the
`Engine` class body into a private `SnapshotMixin`. This is a relocation of
stateful **orchestration** only — the pure serialization / migration / integrity
helpers extracted in Phase 1 (`ragcore._engine.serialization`) are neither moved
nor modified. No change to snapshot schema, canonical bytes, key order, migration,
integrity rejection, claim-status admission, restore authority order,
subclass/classmethod behaviour, the persisted/runtime field boundary, signatures,
or public API.

## Baseline
```
baseline main   5ac28babb85ab7412f3382c23b692b1ab42b364f  (Phase 3B-8 merged, #94)
baseline tests  2165 passed (local; no GitHub Actions on this repo)
guard           HEAD == 5ac28ba verified; tracked working tree clean before start
```

## Exact methods moved (4)
```
to_snapshot     public instance method   live state -> _state_view() -> encode_snapshot()
_state_view     private instance method  project 17 persisted stores into DecodedEngineState (alias, no copy)
from_snapshot   public CLASSMETHOD       decode/integrity -> claim-status admission -> cls() -> _install
_install        private instance method  replace 17 persisted stores; runtime identity untouched
public 2 (1 classmethod) / private 2 / total 4
```
**Not moved:** the seventeen persisted stores + the two runtime-only identity
fields stay in `Engine.__init__`; the C1 infrastructure (guards / `_allocate_id` /
`_advance_state_revision` / `state_identity` / `_storage_for_kind`); the pure
serialization / migration / integrity helpers (`ragcore._engine.serialization`);
the claim-status-admission kernel (`ragcore._engine.confidence`).

## classmethod + annotation preservation (the load-bearing detail)
`from_snapshot` stays an inherited `@classmethod`. The method source, AST
(including the `@classmethod` decorator and the `"Engine"` forward-reference return
annotation), signature, and docstring are moved verbatim. Verified at runtime:
`SnapshotMixin.__dict__["from_snapshot"]` is a `classmethod`;
`Engine.from_snapshot.__func__ is SnapshotMixin.__dict__["from_snapshot"].__func__`;
`Engine.from_snapshot.__self__ is Engine`; `__module__` =
`ragcore._engine.snapshot`, `__qualname__` = `SnapshotMixin.from_snapshot`. The
body's `cls()` is the real construction authority — a subclass
(`DerivedEngine.from_snapshot(snap)`) restores to its own type and binds
`__self__` to the subclass. `inspect.signature` is preserved verbatim
(`(snapshot: 'dict[str, Any]') -> "'Engine'"`; the raw `__func__` shows `cls`).

### Accepted non-contract introspection delta
`typing.get_type_hints(Engine.from_snapshot)` now raises `NameError` because the
`"Engine"` forward-reference string is resolved against the new module's globals,
where `Engine` is intentionally **not** imported (importing it would be a
`snapshot → engine` cycle, forbidden). A repository scan found **no** test or
contract that calls `get_type_hints` on `from_snapshot` (the only `get_type_hints`
runtime call targets the example's `run` function), and the full suite passes, so
this is a non-contract delta. `inspect.signature` (which preserves the string
verbatim) is the authority. The annotation was NOT changed to `Self`/`SnapshotMixin`
and `Engine` was NOT imported.

## Restore authority order (preserved, AST + runtime locked)
`from_snapshot`:
```
1. validate_and_decode_snapshot(snapshot)        decode / migrate / integrity-validate
2. for each decoded claim: confidence._validate_claim_status_admission(status)
3. engine = cls()                                fresh lineage
4. engine._install(decoded)                      install 17 persisted stores
5. return engine
```
On a decode failure or an admission failure, **no** Engine is constructed and
`_install` is never called (locked by spying `Engine.__init__` + `_install` and
asserting zero calls). `_install` receives the exact object `decode` returned.

## Persisted / runtime boundary
`_state_view` projects exactly the 17 persisted fields into a `DecodedEngineState`,
each mutable store **aliasing** the live object (no copy); the two runtime identity
fields (`_state_identity_token` / `_state_revision`) are excluded. `_install`
replaces exactly those 17 stores with the decoded objects and does **not** touch
the runtime identity lineage or call `_advance_state_revision` (restore intends a
fresh lineage). 17 persisted fields:
```
_next_id _lifecycle_seq _entities _observations _claims _evidences _relations
_gaps _rule_definitions _rule_stats _gap_dedup_index _claim_gap_refs
_gap_resolutions _contradictions _resolved_contradictions _claim_lifecycle_events
_hint_evidence_types
runtime-only (excluded): _state_identity_token  _state_revision
```

## Before → after ownership / accumulated MRO
`class Engine(HintEvidenceMixin, RelationsMixin, RulesMixin, GapsMixin, ConfidenceAdaptersMixin, LifecycleHistoryMixin, CrudMixin, LifecycleMixin):`
→ append `SnapshotMixin`. All **nine** mixins in `Engine.__mro__`; the four methods
resolve via the MRO (no forwarding wrapper). engine.py 334 → 243; the emptied
Region K removed.

## engine.py import / compatibility surface (intentionally unchanged)
Only `from ragcore._engine.snapshot import SnapshotMixin` was added and
`SnapshotMixin` appended to the bases; the four methods + Region K were removed.
The Phase-1 module-level compatibility shim and the existing imports
(`asdict`, `Any`, `confidence`, `DecodedEngineState`, `encode_snapshot`,
`validate_and_decode_snapshot`, the `_serialize_dict_*` / `_restore_dict_*` /
`_*_from_dict` / `_sv_*` / migration / schema-version symbols) were **deliberately
left in place** — they remain `ragcore.engine` module attributes for backward
compatibility (verified still importable). Import/shim cleanup is explicitly
deferred to Phase 4 boundary reconciliation. No import was removed merely for being
unused in the class body.

## Import graph
```
ragcore.engine -> ragcore._engine.snapshot                   (added)
ragcore._engine.snapshot imports: {__future__, typing.Any, ragcore._engine.confidence,
    ragcore._engine.serialization (DecodedEngineState, encode_snapshot, validate_and_decode_snapshot)}
ragcore._engine.snapshot -> ragcore.engine / other mixins : NONE  (no cycle)
serialization.py / confidence.py : unchanged (byte-identical), do NOT import snapshot
```

## AST equivalence
`ast.dump(..., include_attributes=False)` baseline `5ac28ba:ragcore/engine.py`
(Engine) vs `ragcore/_engine/snapshot.py` (SnapshotMixin): **4/4 identical**
(including the `from_snapshot` `@classmethod` decorator and the `Constant('Engine')`
return annotation); all four methods absent from the current Engine class body.

## Accepted introspection deltas / preserved surface
the four methods → `__module__` `ragcore._engine.snapshot`, `__qualname__`
`SnapshotMixin.*`, declaring class, inherited (`from_snapshot` as a classmethod
descriptor). Preserved: `from ragcore import Engine`; `Engine.__module__ ==
"ragcore.engine"`; runtime public **42**; `__all__` **50**; exact signatures;
`getattr`/`setattr`/`monkeypatch` (descriptor-aware for the classmethod);
`getsource` real bodies; the eight prior mixins unchanged and in the MRO.

## Exact signatures (unchanged)
```
to_snapshot(self) -> dict[str, Any]
_state_view(self) -> DecodedEngineState
from_snapshot  bound:  (snapshot: dict[str, Any]) -> "Engine"
               __func__: (cls, snapshot: dict[str, Any]) -> "Engine"
_install(self, decoded: DecodedEngineState) -> None
```

## Ownership / no-promotion + patch-site scan (0 migrations)
The new test locks, for the three regular methods: `name not in Engine.__dict__`,
`_defining_class(Engine, name) is SnapshotMixin`,
`getattr(Engine, name) is SnapshotMixin.__dict__[name]`. For `from_snapshot` a
**descriptor-aware** lock: `"from_snapshot" not in Engine.__dict__`,
`_defining_class is SnapshotMixin`, the raw `__dict__` entry `isinstance(_,
classmethod)`, and `Engine.from_snapshot.__func__ is raw.__func__` (the bound
method and the raw descriptor are deliberately NOT compared by identity). A
repository-wide scan (`setattr(Engine` / `monkeypatch.setattr(Engine` /
`patch.object(Engine` / `Engine.<name> =` against the four C10 names) found **NO**
test that patches a C10 method directly on Engine, and **no** generic name-driven
installer includes a C10 name (the `_install_engine_spies` hit is a function-name
coincidence; its `_SPY_METHODS` is `update_rule_stats`/`get_rule_stats`/
`state_identity`). **Patch-site migration count: 0** (actual scan, not pre-declared).
The classmethod patch lock additionally verifies a `classmethod(spy)` patch closed
by `monkeypatch.context()` restores the exact original descriptor and leaves
`Engine.__dict__` unpolluted.

## Behavioural probes (all pass)
- `_state_view` returns `DecodedEngineState` aliasing the 17 live stores (each
  `is` the Engine store), excludes the runtime identity fields, and is read-only.
- `to_snapshot` calls `_state_view` once and `encode_snapshot` once, passing the
  exact `_state_view` return into `encode` and returning the exact `encode` result;
  state read-only; spies installed on the defining class / module, restored after.
- `from_snapshot` order decode → (all) admissions → construct → install; subclass
  restores to `DerivedEngine` with a fresh lineage; decode-failure and
  admission-failure both construct nothing and install nothing.
- `_install` replaces the 17 persisted stores with the decoded objects and leaves
  `_state_identity_token` / `_state_revision` untouched (no revision advance).
- full populated round-trip (all 17 stores exercised): `snapshot ==
  restored.to_snapshot()`, identical canonical bytes (`json.dumps(sort_keys=True)`),
  identical key order, schema 2, 18 top-level keys.

## Tests
```
new: tests/test_engine_phase3b_snapshot_mixin.py (20 runtime locks)
migrated: none (0 C10 direct-Engine patch sites; no generic installer includes a C10 name)
targeted: engine persistence / snapshot restore integrity / snapshot migration /
          surface freeze / state identity / claim status admission / effective-
          confidence trace / complete reference operation / Phase 3B-1..3B-8 tests
full suite: 2165 -> 2185 passed (+20 new; no existing test weakened or deleted)
```

## Files changed / line delta
```
production/test (stable): 3 files, +603/-93
  ragcore/_engine/snapshot.py                     +137  (new)
  ragcore/engine.py                               +2/-93
  tests/test_engine_phase3b_snapshot_mixin.py     +464  (new)
+ docs/dev/PR_094_…                               (this dev record; its own size
                                                   is self-referential — see the PR #95 diff)
Authoritative full-PR total (incl. this dev record): the GitHub PR #95 diff.
NOT changed: ragcore/_engine/{confidence,serialization,hint_evidence,relations,
rules,gaps,confidence_adapters,lifecycle_history,crud,lifecycle}.py,
ragcore/_engine/__init__.py, ragcore/types.py, ragcore/__init__.py, snapshot schema,
examples/**, config/deps, Phase 3A docs. confidence.py + serialization.py
byte-identical to baseline.
```

## Commit chronology
Stable implementation/test chronology:
```
8e696d9  production extraction (engine.py + snapshot.py)
8e7a138  extraction tests (20 ownership / classmethod / restore-order locks)
```
(The two short SHAs are pinned in the final committed record; they are the first
two commits in
`git log --reverse --format='%h %s' 5ac28ba..<head>`.) This versioned record
intentionally does not self-pin the SHA of the commit that adds the record itself.
Any later review-correction commits are recorded in the GitHub PR #95 commit
history. No commit amended, rebased, or squashed. If a review correction touches
production/test, the stable subtotal above is re-measured.

## STOP-AND-REPORT review
None triggered: base SHA 5ac28ba; AST 4/4 identical; exactly 4 C10 methods;
`from_snapshot` stays a classmethod with binding preserved; signatures unchanged;
`"Engine"` annotation unchanged and Engine not imported (`get_type_hints` delta is
non-contract); subclass restore type preserved; decode → admission → cls() →
install order preserved; no construction/install on a failure path; 17 persisted
fields exact; runtime identity untouched and no revision advance; `_state_view`
aliases (no copy); no serialization helper moved/modified; the Phase-1 compatibility
shim unchanged; serialization.py + confidence.py byte-identical; no wrapper/super/
delegate; all four methods absent from `Engine.__dict__`; the classmethod patch
preserves the descriptor; no direct-Engine C10 patch site; snapshot schema / key
order / canonical bytes / migration / integrity unchanged; public 42 / __all__ 50 /
snapshot 2·18 / packet 7 unchanged; the eight prior mixins unchanged; no import
cycle; no existing test weakened.

## Lifecycle
OPEN — Draft. Recommendation on completion: **READY FOR GPT INDEPENDENT REVIEW**
(not self-merged). On merge + post-merge verification this completes the **Phase 3B
implementation series** (all ten clusters: C1 retained on the Engine base, C2–C10
extracted into nine mixins). **Phase 4 (boundary re-verification / import-shim
reconciliation) becomes UNBLOCKED**; it is NOT auto-started — it awaits a directive.
