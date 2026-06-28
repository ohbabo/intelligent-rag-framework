# PR_095 — Engine v1 Phase 4: Boundary Re-verification & Final Closure (development record)

GitHub PR **#96** (internal dev-record number = GitHub number − 1 = 095).

## Identity / purpose
The single closure PR for the Engine v1 refactoring. Three goals, no behaviour
change and no new structure: (1) remove the Phase-1 `ragcore.engine` serialization
compatibility shim and the stale C9/C10 engine imports; (2) re-verify the whole
Phase-3B-complete boundary against the approved final shape; (3) document the final
v1 boundary and mark the plan / ADR complete. No Engine algorithm, public API, or
snapshot change.

## Baseline
```
baseline main   1e89a428ee48a46fc2b8c74dc6537371a7132c20  (Phase 3B complete, #95)
baseline tests  2185 passed (local; no GitHub Actions on this repo)
guard           HEAD == 1e89a42 verified; tracked working tree clean before start
```

## Audit method
For the 26 Phase-1 serialization re-export symbols + the 6 stale C9/C10 engine
imports, a repository-wide search across `tests/ examples/ ragcore/ docs/` for:
`from ragcore.engine import <name>`; `ragcore.engine.<name>` attribute access;
`import ragcore.engine` then alias attribute access; `monkeypatch.setattr` /
`patch.object` / `patch("ragcore.engine...")`; docs / example references. Live
access was distinguished from comment/docstring text and from string-literal frozen
lists by reading each site (substring hits were not treated as dependencies).

## Symbol-use matrix (result)
```
class  meaning                              sites
A  defined public contract                  0   (none of the 32 names is public — STOP guard clear)
B  documented private compatibility         engine.py shim block (the thing being removed)
C  repository-internal test dependency      2 test files, 10 reference sites (see migration)
D  accidental module attribute              the 6 stale C9/C10 imports (unused in engine.py code)
E  historical documentation reference       docs/dev/PR_018_*.md (1 line); comments in 3 tests
```
No class-A (public-contract) symbol was found, so no STOP-AND-REPORT was triggered.

## Consumer migration (actual count: 2 files / 10 sites)
Two test files looked a shim symbol up at the relocation point (`ragcore.engine`,
via `import ragcore.engine as engine_module` + `getattr(engine_module, "_X")`). Both
were repointed to the real owner `ragcore._engine.serialization`
(`from ragcore._engine import serialization`); the now-unused `engine_module` alias
was removed from each:
```
tests/test_engine_snapshot_migration.py    7 sites (_CURRENT.../_SUPPORTED.../_migrate_snapshot_to_current)
tests/test_engine_evidence_type_modifier.py 3 sites (_CURRENT.../_SUPPORTED.../_migrate_snapshot_v1_to_v2)
```
Test semantics unchanged — the migrated tests exercise the same real serialization
functions/constants. **Not migrated** (no live `ragcore.engine` access): the shim
names in `test_engine_method_surface_freeze.py` / `test_engine_phase0_taxonomy.py` /
`test_snapshot_restore_integrity.py` are comment/docstring text; `docs/dev/PR_018_*`
is a historical dev record (class E, left as history). The
`assert not hasattr(engine_module, …)` lines elsewhere target Phase-2 confidence
constants (not the 32 names) and are unaffected.

## Removed from ragcore/engine.py (production diff: 0 insertions / 50 deletions)
- the TEMPORARY 26-symbol serialization re-export block + its comment:
  `_CURRENT_SNAPSHOT_SCHEMA_VERSION`, `_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS`,
  `_claim_from_dict`/`_entity_from_dict`/`_evidence_from_dict`/`_gap_from_dict`/
  `_observation_from_dict`/`_relation_from_dict`/`_rule_def_from_dict`/
  `_rule_stats_from_dict`, `_serialize_dict_int_dataclass`/`_serialize_dict_int_int`/
  `_serialize_dict_int_list_dataclass`/`_serialize_dict_int_set`/
  `_serialize_dict_tuple4_int`/`_serialize_dict_tuple_dataclass`,
  `_restore_dict_int`/`_restore_dict_int_int`/`_restore_dict_int_list_dataclass`/
  `_restore_dict_int_set`/`_restore_dict_tuple`/`_restore_dict_tuple4_int`,
  `_sv_to_dict`/`_sv_from_dict`, `_migrate_snapshot_to_current`/
  `_migrate_snapshot_v1_to_v2`.
- the 6 stale C9/C10 imports unused in the Engine class body after Phase 3B-9:
  `dataclasses.asdict`, `typing.Any`, `ragcore._engine.confidence`, and
  `DecodedEngineState` / `encode_snapshot` / `validate_and_decode_snapshot`.

All 32 were verified unused in engine.py code (AST: pure re-export / stale imports)
before removal. The `ragcore.types` imports (C1 annotation/type boundary) were left
untouched per directive. No method body / signature / class base / MRO / store
initialization changed — the engine.py diff is imports only.

## Phase 4 boundary test
`tests/test_engine_phase4_boundary.py` (19 locks): shim relocated off
`ragcore.engine` and present on `serialization` (×26) + 6 stale bindings absent;
public import boundary (Engine resolvable via `ragcore`/`ragcore.engine`, `__all__`
50, privates not promoted); final `Engine.__bases__` / `__mro__[1:10]` exact nine
mixins, no `CoreMixin`; C1 retained on Engine (12 members) + no extracted method
promoted back + Engine.__dict__ holds only C1 callables; aggregate C2–C10 ownership
(52 methods, no cross-mixin duplication, descriptor-aware `from_snapshot` +
subclass restore); each mixin stateless/non-cooperative (AST: no `__init__`, base
`(object,)`, no `super()` call, no `ragcore.engine` import); import graph
(`engine → stdlib+types+9 mixins`, no kernel import; pure kernels → stdlib+types;
`snapshot → kernels not engine`; no `ragcore._engine → engine` inversion; no
`_engine/__init__` re-export hub).

## Final ownership / MRO (re-verified)
```
Engine.__bases__ == Engine.__mro__[1:10] ==
  (HintEvidenceMixin, RelationsMixin, RulesMixin, GapsMixin, ConfidenceAdaptersMixin,
   LifecycleHistoryMixin, CrudMixin, LifecycleMixin, SnapshotMixin)
C1 on Engine base: __init__ + _allocate_id + _advance_state_revision + state_identity
  + _storage_for_kind + _id_exists + _assert_{entity,claim,evidence,gap}_exists
  + _assert_rule_pair_exists + _assert_rule_stats_pair_exists  (12 members)
C2–C10 contributed methods: 52 (C8 4 / C3 2 / C7 4 / C4 5 / C9 10 / C6 2 / C2 9 / C5 12 / C10 4)
```

## Import graph (re-verified)
```
ragcore.engine            -> {__future__, uuid, ragcore.types, 9 mixin modules}   (no kernel import)
ragcore._engine.serialization -> stdlib + ragcore.types
ragcore._engine.confidence    -> stdlib + ragcore.types
ragcore._engine.snapshot      -> ragcore._engine.confidence + ragcore._engine.serialization  (never engine)
no ragcore._engine.* -> ragcore.engine ; no _engine/__init__ re-export hub
```

## Contract re-verification (full)
```
full pytest                     2185 -> 2204 passed (+19 boundary; migrations behavior-preserving)
Engine public methods           42
ragcore.__all__                 50
snapshot schema / keys / order  2 / 18 / deterministic; canonical JSON round-trip identical
v1 -> v2 migration, integrity rejection, claim-status admission, restore
  failure-before-construction, subclass restore, fresh lineage, revision semantics  all pass
PR51 packet                     7
confidence policy id            ragcore.effective-confidence.v1
package-wide forbidden imports  pass
all Phase 3B ownership tests + Phase 4 aggregate ownership  pass
```

## Pure-kernel byte-identity (§7.8 review material — not a hardcoded-SHA test)
`git diff --exit-code 1e89a42 -- ragcore/_engine/serialization.py
ragcore/_engine/confidence.py` is clean (byte-identical). SHA-256 at this PR:
```
serialization.py  0462e38c958ed3aa5206241acabf441b9e5608d322f79a72c54055c72e057f6f
confidence.py     99252d634cc05ddbe7d28934a926225a4716a322f738debba7f2ae95a0cc99ce
```

## Accepted introspection delta (unchanged from Phase 3B-9)
`typing.get_type_hints(Engine.from_snapshot)` raises `NameError` (the `"Engine"`
forward-ref is not resolvable in `ragcore._engine.snapshot` without a forbidden
cycle); `inspect.signature` is the authority. Recorded in
`ENGINE_V1_FINAL_BOUNDARY.md §8`. Not "fixed" in this Phase.

## Files changed / line delta
```
production:  ragcore/engine.py                                0/-50
test:        tests/test_engine_phase4_boundary.py             +262 (new)
             tests/test_engine_snapshot_migration.py          +11/-8  (consumer migration)
             tests/test_engine_evidence_type_modifier.py      +7/-4   (consumer migration)
docs:        docs/architecture/ENGINE_V1_FINAL_BOUNDARY.md    +183 (new)
             docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md  +21/-4
             docs/architecture/ENGINE_V1_REFACTORING_PLAN.md  +21/-1
             docs/architecture/ENGINE_INTERNAL_MAP.md         +9 (superseded banner)
production+test stable subtotal: 4 files, +280/-62
Authoritative full-PR total (incl. this dev record): the GitHub PR #96 diff.
NOT changed: ragcore/_engine/{serialization,confidence,hint_evidence,relations,
rules,gaps,confidence_adapters,lifecycle_history,crud,lifecycle,snapshot}.py,
ragcore/_engine/__init__.py, ragcore/types.py, ragcore/__init__.py, snapshot schema,
examples/**, config/deps. The Engine class body (methods/bases/MRO) is unchanged.
```

## Commit chronology
Stable implementation/test/docs chronology:
```
1a82dc7  consumer migration (test imports/lookup-sites -> serialization)
c8249a4  shim + stale-import removal (engine.py) + Phase 4 boundary test
99b20c1  closure documentation (FINAL_BOUNDARY new; PLAN/ADR status; INTERNAL_MAP banner)
```
This versioned record intentionally does not self-pin the SHA of the commit that
adds the record itself. The post-review correction (B1/B2/B3 below) modifies the
Phase-4 boundary test and the FINAL_BOUNDARY doc (and this record); its SHA and
order are recorded in the GitHub PR #96 commit history. No commit amended, rebased,
or squashed.

## GPT review corrections (MERGE-TIME, no new production behavior)
GPT independent review: **REQUEST CHANGES — BLOCKER 0 (production) / 3 doc+test
corrections**. The production diff (engine.py 0/-50) and the 10-site consumer
migration were confirmed correct; the three corrections are docs/test precision and
do not change the engine.py change or any runtime behavior. All applied:

- **B1 — canonical-JSON oracle recorded backwards.** The FINAL_BOUNDARY doc listed
  the snapshot canonical representation as `json.dumps(sort_keys=True)` under the
  *defined external contract*. That is wrong: the Phase-0 lock
  (`test_engine_phase0_taxonomy.py`) deliberately FORBIDS `sort_keys=True` (it would
  hide an emission-order regression) and the real form is
  `json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")`.
  Corrected the encoding, and reclassified it as a **value + emission-order drift
  oracle (characterization, NOT a user-facing serialization API contract)** in a new
  §7a; the frozen contract now states "deterministic emission order" only.
- **B2 — Phase 4 over-reached into v2 design.** The doc had pre-decided v2
  ("only the internal algorithm may evolve in v2"; "v2 MUST add new state through
  `Engine.__init__` ownership, not mixin state"). Per the Phase 3A ADR, v2's API
  shape / state ownership / projection / identity / materialization are decided in a
  separate v2 directive. Removed the `Engine.__init__`-ownership mandate and the
  "internal algorithm only" framing; §10 now states the single negative boundary
  (v2 must not silently break the v1 contract) and explicitly defers the rest. The
  intro blockquote was softened to match.
- **B3 — pure-kernel import lock too weak.** The test allowed any dotless import
  (`import numpy` / `import requests` would have passed). Replaced with **exact
  import-set** locks (`serialization == {__future__, dataclasses, typing,
  ragcore.types}`, `confidence == {__future__, ragcore.types}`), removed the unused
  `os` import, and extended the inversion check to include
  `ragcore._engine.snapshot` and `ragcore._engine` (the package `__init__`). A
  negative control confirms the exact set rejects a foreign import.

Re-verification after the correction: Phase-4 boundary test 19 locks pass; full
suite 2204 passed; serialization.py + confidence.py still byte-identical;
production/test stable subtotal unchanged (+280/-62 — the boundary test's net line
count is unchanged).

## STOP-AND-REPORT review
None triggered: base SHA 1e89a42; tree clean; baseline 2185; no class-A public
symbol among the 32 names; no production/example consumer depends on a
`ragcore.engine` private alias; shim removal needed no method-body change;
serialization.py + confidence.py byte-identical; no mixin body change; signatures /
snapshot bytes-order-value / packet / state identity unchanged; `from_snapshot`
descriptor/binding + subclass restore preserved; no import cycle; MRO unchanged;
no C1 moved; no existing test deleted/weakened; no v2 decision required. (Test
import/patch-lookup migration is the expected Phase-4 work, not a STOP cause.)

## Lifecycle
OPEN — Draft. Recommendation on completion: **READY FOR GPT INDEPENDENT REVIEW**
(not self-merged). On merge + post-merge verification this closes **Engine v1
refactoring (COMPLETE)** and **Phase 4 (CLOSED)**; Phase 3B remains CLOSED; the
temporary shim is REMOVED; the final boundary is VERIFIED. **v2 engine: NOT
STARTED** — closure does NOT auto-start v2; its philosophy / math model /
projection / state-identity / materialization boundary await a separate
user/GPT design directive.
