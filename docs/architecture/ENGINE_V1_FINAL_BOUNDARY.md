# Engine v1 — Final Boundary (authoritative)

```
status:   FINAL — Engine v1 refactoring complete (Phase 0–4)
type:     authoritative boundary description (docs-only)
baseline: Phase 3B complete at main 1e89a428ee48a46fc2b8c74dc6537371a7132c20;
          Phase 4 (this change) removed the Phase-1 compatibility shim and the
          stale C9/C10 engine imports and re-verified the whole boundary.
scope:    the closed v1 boundary. v2 (physics) is NOT designed here.
```

> This document is the single authoritative description of the Engine v1
> structural boundary after the refactoring. It supersedes
> `ENGINE_INTERNAL_MAP.md` (a historical 1145-test-era audit) for current
> topology. The *defined external contract* below is frozen; only the internal
> algorithm may evolve in v2.

## 1. Shape — thin orchestration core + nine mixins

`Engine` is a thin core that owns ID allocation, per-kind storage, the
existence/guard seams, the state-identity lineage, and the completed-mutation
revision counter (cluster **C1**). All other behaviour is contributed by nine
private mixins via the MRO — no forwarding wrappers, no cooperative `super()`
chains, no shared base beyond `object`.

```python
class Engine(
    HintEvidenceMixin,        # C8
    RelationsMixin,           # C3
    RulesMixin,               # C7
    GapsMixin,                # C4
    ConfidenceAdaptersMixin,  # C9
    LifecycleHistoryMixin,    # C6
    CrudMixin,                # C2
    LifecycleMixin,           # C5
    SnapshotMixin,            # C10
):
    ...
```

`Engine.__bases__` is exactly these nine mixins; `Engine.__mro__[1:10]` is the
same tuple in the same order; `Engine.__mro__` is `(Engine, *nine mixins, object)`.
There is **no** `CoreMixin` — C1 is retained directly on the `Engine` class body
(its extraction was never approved; moving it would be a separate change-control).

## 2. C1 — retained directly on the Engine base

The following members are defined in `Engine.__dict__` and are the only non-dunder
callables there:

```
__init__                       (allocates state + a fresh identity lineage)
_allocate_id
_advance_state_revision
state_identity                 (public)
_storage_for_kind
_id_exists
_assert_entity_exists
_assert_claim_exists
_assert_evidence_exists
_assert_gap_exists
_assert_rule_pair_exists
_assert_rule_stats_pair_exists
```

No extracted-cluster method is promoted back into `Engine.__dict__`.

## 3. C2–C10 — ownership table (52 contributed methods)

```
cluster  mixin                     module                                  methods
C8       HintEvidenceMixin         ragcore._engine.hint_evidence            4
C3       RelationsMixin            ragcore._engine.relations                2
C7       RulesMixin                ragcore._engine.rules                    4
C4       GapsMixin                 ragcore._engine.gaps                     5
C9       ConfidenceAdaptersMixin   ragcore._engine.confidence_adapters     10
C6       LifecycleHistoryMixin     ragcore._engine.lifecycle_history        2
C2       CrudMixin                 ragcore._engine.crud                     9
C5       LifecycleMixin            ragcore._engine.lifecycle               12
C10      SnapshotMixin             ragcore._engine.snapshot                 4
```

Each contributed method: absent from `Engine.__dict__`; its defining class via the
MRO is its mixin; `getattr(Engine, name)` resolves to that mixin's function; no
name is contributed by two mixins. Each mixin has no `__init__`, no instance state,
no `Engine` back-reference, `__bases__ == (object,)`, and no `super()` call.

## 4. State — 17 persisted + 2 runtime-only, owned by Engine.__init__

```
persisted (serialized, restored):
  _next_id _lifecycle_seq _entities _observations _claims _evidences _relations
  _gaps _rule_definitions _rule_stats _gap_dedup_index _claim_gap_refs
  _gap_resolutions _contradictions _resolved_contradictions
  _claim_lifecycle_events _hint_evidence_types
runtime-only (NOT persisted; fresh lineage on restore):
  _state_identity_token _state_revision
```

`_claims` is the one operational shared-write store: `CrudMixin` (C2) inserts new
Claims and `LifecycleMixin` (C5) replaces their status on the same dict. C10's
`_state_view` aliases the live stores (no copy); `_install` replaces exactly the 17
persisted stores and never touches the 2 runtime-only fields or advances the
revision.

## 5. Pure kernels — serialization + confidence

```
ragcore._engine.serialization   snapshot encode/decode/migrate/integrity helpers
ragcore._engine.confidence      fixed-v1 effective-confidence kernel + status admission
```

Both are pure module functions importing only stdlib + `ragcore.types`. They read
no Engine state and import no mixin or `ragcore.engine`. They have been
byte-identical since Phase 1 / Phase 2 respectively (Phase 4 left them untouched).

## 6. Final import graph (no cycles, no re-export hub)

```
ragcore.engine            -> stdlib (__future__, uuid) + ragcore.types + the 9 mixin modules
ragcore._engine.serialization -> stdlib + ragcore.types
ragcore._engine.confidence    -> stdlib + ragcore.types
ragcore._engine.snapshot      -> ragcore._engine.confidence + ragcore._engine.serialization
ragcore._engine.<other mixin> -> stdlib + ragcore.types (+ confidence for the C9 adapter)
```

No `ragcore._engine.*` module imports `ragcore.engine`. `ragcore._engine/__init__.py`
is **not** a re-export hub for the private serialization symbols.

## 7. Defined external contract (frozen)

```
Engine public methods           42
ragcore.__all__                 50
snapshot schema_version         2
snapshot top-level keys         18
snapshot key order              deterministic
canonical JSON representation   deterministic (json.dumps(sort_keys=True))
PR51 context packet             7 keys (examples/inspector — not an Engine method)
confidence policy id            ragcore.effective-confidence.v1
from_snapshot                   inherited classmethod; cls() restores subclasses
restore authority order         decode/integrity -> claim-status admission -> cls() -> _install
state identity                  fresh lineage on restore; revision counts completed mutations
```

`from ragcore import Engine`, `from ragcore.engine import Engine`, and
`ragcore.engine.Engine` are the same class; `Engine.__module__ == "ragcore.engine"`.

## 8. Accepted (non-contract) introspection deltas

- Each extracted method's `__module__` / `__qualname__` / declaring class is its
  mixin (a new `def`/descriptor executes in the mixin module — a new function
  object; bodies, signatures, AST, and docstrings are preserved verbatim).
- `from_snapshot` keeps its `"Engine"` forward-reference return annotation and AST
  verbatim, but `typing.get_type_hints(Engine.from_snapshot)` now raises
  `NameError` because `Engine` is intentionally not imported into
  `ragcore._engine.snapshot` (that would be a cycle). `inspect.signature`
  (string-preserving) is the authority; no test or contract depends on the resolved
  hint.

## 9. Removed compatibility aliases (Phase 4)

`ragcore.engine` no longer re-exports the 26 Phase-1 serialization internals
(`_CURRENT_SNAPSHOT_SCHEMA_VERSION`, `_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS`,
`_*_from_dict`, `_serialize_dict_*`, `_restore_dict_*`, `_sv_to_dict`/`_sv_from_dict`,
`_migrate_snapshot_to_current`/`_migrate_snapshot_v1_to_v2`); they live only at
`ragcore._engine.serialization`. The stale C9/C10 engine imports (`asdict`, `Any`,
`confidence`, `DecodedEngineState`, `encode_snapshot`, `validate_and_decode_snapshot`)
were removed. None was public (in `ragcore.__all__`) or a defined Engine method.

## 10. Extension rules for v2 (negative boundary only)

```
v2 MAY extend this clean boundary (new clusters, new mixins, new kernels).
v2 MUST NOT silently change the v1 defined external contract (§7).
v2 MUST keep the pure kernels pure (stdlib + ragcore.types) and acyclic.
v2 MUST add new state through Engine.__init__ ownership, not mixin state.
```

The v2 physics engine's philosophy, mathematical model, state projection, identity
model, and materialization boundary are **NOT decided here** — they await a separate
user/GPT design directive. This document only fixes the v1 boundary they must build
on without breaking.
