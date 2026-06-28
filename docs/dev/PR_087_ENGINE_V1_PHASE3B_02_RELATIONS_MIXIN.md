# PR_087 — Engine v1 Phase 3B-2: Extract C3 Relations Mixin (development record)

GitHub PR **#88** (internal dev-record number = GitHub number − 1 = 087;
confirmed by creating the Draft PR first).

## Identity / purpose
Second production-code decomposition under the approved Phase 3A ADR, and the
**first multi-mixin accumulation**. A behaviour-preserving move of the two C3
relation methods from the `Engine` class body into a private `RelationsMixin`.
No logic, signature, validation-order, ID-allocation, revision, snapshot, or
public-API change.

## Baseline
```
baseline main   3526c39ef16e9c136b59ff30531bf41fa80f5e9b (Phase 3B-1 merged)
baseline tests  2079 passed (local; no GitHub Actions on this repo)
guard           HEAD == 3526c39 verified; tracked working tree clean before start
```

## Why C3 second
Per the Phase 3A 3B sequence (ascending coupling): single store `_relations`,
single owning write-cluster, one mutator (`add_relation`) + one read-only
(`get_relation`), no non-infra cross-cluster call (C3 → C1 `_id_exists` /
`_allocate_id` / `_advance_state_revision` only). Lowest coupling after C8.

## Exact methods moved (2)
```
add_relation   (public, mutator)
get_relation   (public, read-only)
```
Moved verbatim. **Not moved:** `_relations` (state, stays in `Engine.__init__`),
the C1 seams `_id_exists` / `_storage_for_kind` / `_allocate_id` /
`_advance_state_revision`, the `Relation` dataclass (`ragcore.types`),
`HintEvidenceMixin`'s methods, the Gap cluster.

## Before → after ownership
| method | before | after |
|---|---|---|
| add_relation, get_relation | `Engine` (`ragcore.engine`) | `RelationsMixin` (`ragcore._engine.relations`) |
Resolved via the MRO, no forwarding wrapper. engine.py 1491 → 1439.

## Engine MRO (accumulated)
`class Engine:` → (3B-1) `class Engine(HintEvidenceMixin)` → (3B-2)
`class Engine(HintEvidenceMixin, RelationsMixin)`. The new mixin is **appended**,
preserving the existing `HintEvidenceMixin` prefix. Both mixins are in
`Engine.__mro__`. No exact full-MRO tuple is locked.

## Engine state did NOT move (proof)
`Engine.__init__` still sets `self._relations: dict[int, Relation] = {}`; the
`Relation` import is retained in `engine.py` for that annotation. The mixin has
no `__init__`, no state, no Engine back-reference; it reaches the store via
`self._relations` and the C1 seams via `self._id_exists(...)` /
`self._allocate_id(...)` / `self._advance_state_revision()`. Snapshot still
serialises relations; restore round-trips equal; top-level keys remain 18.

## Import graph
```
ragcore.engine -> ragcore._engine.relations            (added)
ragcore._engine.relations imports: {__future__, ragcore.types}  (Relation only)
ragcore._engine.relations -> ragcore.engine            : NONE
ragcore._engine.relations -> ragcore._engine.hint_evidence : NONE   (no cycle, no mixin coupling)
hint_evidence.py / confidence.py / serialization.py / types.py / ragcore/__init__.py : unchanged
```

## AST equivalence
`ast.dump(..., include_attributes=False)` of each moved method, baseline
`3526c39:ragcore/engine.py` (Engine) vs `ragcore/_engine/relations.py`
(RelationsMixin): **2/2 identical**. Both methods are absent from the current
Engine class body.

## Accepted introspection deltas (Phase 3A-approved), measured
```
add_relation, get_relation:
  __module__       ragcore.engine     -> ragcore._engine.relations
  __qualname__     Engine.<m>         -> RelationsMixin.<m>
  declaring class  Engine             -> RelationsMixin
  Engine.__dict__  present            -> inherited / absent
  Engine.__mro__   + RelationsMixin   (HintEvidenceMixin retained)
```
## Preserved runtime surface, measured
```
from ragcore import Engine ; ragcore.Engine is Engine    OK
Engine.__module__ == "ragcore.engine"                    OK
runtime public methods                                   42
ragcore.__all__                                          50
exact public signatures                                  unchanged
getattr(Engine, <C3>) resolves to mixin function         OK
setattr / monkeypatch on Engine (C1 seams)               OK
inspect.getsource(Engine.<C3>) returns real body         OK (no super(), no wrapper)
no extra delegation traceback frame
```

## Behavioural probes (all pass, real KIND_* constants)
- normal cross-kind `add_relation(KIND_ENTITY, a, KIND_CLAIM, c, 7, 1, 0)`:
  all 8 returned `Relation` fields correct; revision exactly +1.
- C1 seam call counts for one normal add_relation: `_id_exists` ×2 (from-side +
  to-side), `_allocate_id` ×1, `_advance_state_revision` ×1.
- validation order / no-mutation: unknown from_id → KeyError; unknown to_id →
  KeyError; unknown from_kind → ValueError; unknown to_kind → ValueError — each
  with `_relations`, relation next-id, and revision unchanged. From-side failure
  allocates no id and stores no relation (does not progress to to-side / ID
  allocation).
- `get_relation` unknown id → KeyError, revision unchanged.
- snapshot: relations restored equal, canonical 18 top-level keys.

## Tests
```
new: tests/test_engine_phase3b_relations_mixin.py (9 runtime, location-agnostic locks)
targeted: phase0 taxonomy, phase3b hint mixin, + rg-discovered relation tests
          (test_engine_relations, test_engine_relation_gap, surface-freeze,
           method-call-playbook, state-identity, external-adapter-sim,
           minimal-scaffold, proposal schema/validator) -> 319 passed
full suite: 2079 -> 2088 passed (+9 new; no existing test weakened or changed)
```

## Files changed / line delta
```
production/test: 3 files, +175/-54
  ragcore/_engine/relations.py                       +71  (new)
  ragcore/engine.py                                  +2/-54
  tests/test_engine_phase3b_relations_mixin.py       +102 (new)
+ docs/dev/PR_087_…                                  (this file)
NOT changed: ragcore/_engine/{hint_evidence,confidence,serialization}.py,
ragcore/_engine/__init__.py, ragcore/types.py, ragcore/__init__.py, snapshot
schema, examples/**, config/deps, any other cluster, Phase 3A docs.
```

## Commit chronology
```
a9cbe6f refactor(engine): extract C3 relations mixin
8c7b3b6 test(engine): lock inherited C3 runtime contracts
<this>  docs(dev): record Phase 3B-2 relations mixin extraction
```
No commit amended, rebased, or squashed. Review-correction commits, if any,
appended after independent review.

## STOP-AND-REPORT review
None triggered: AST 2/2 identical; no Engine wrapper; no public-signature /
`Engine.__module__` / public-count / `__all__` change; `_relations` state stays
on Engine; no C1 method moved; `HintEvidenceMixin` unchanged; no Gap/CRUD change;
`relations.py` does not import `ragcore.engine` or `hint_evidence`; no import
cycle; snapshot schema/keys/bytes unchanged; ID-allocation and revision semantics
unchanged; no existing test weakened; no source-location lock added.

## Lifecycle
OPEN — Draft. Recommendation on completion: **READY FOR GPT INDEPENDENT REVIEW**
(not self-merged). **Phase 3B-3 (C7 rules) remains prohibited** until this PR
passes independent review (APPROVE), squash merge, branch cleanup, and post-merge
`main` verification.
