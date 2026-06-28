# PR_086 — Engine v1 Phase 3B-1: Extract C8 Hint-Evidence Mixin (development record)

GitHub PR **#87** (internal dev-record number = GitHub number − 1 = 086, per the
repository convention; confirmed by creating the Draft PR first).

## Identity / purpose
First production-code decomposition under the approved Phase 3A ADR
(`docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md`). A
**behaviour-preserving** move of the four C8 hint-evidence methods from the
`Engine` class body into a private `HintEvidenceMixin`. No logic, signature,
validation, revision, snapshot, or public-API change.

## Baseline
```
baseline main   65ee71b207e3ba0534a0e7c30d48614d434b7ee2 (Phase 3A merged)
baseline tests  2070 passed (local; no GitHub Actions on this repo)
guard           HEAD == 65ee71b verified; tracked working tree clean before start
```

## Why C8 first
Per the Phase 3A 3B sequence (ascending coupling, lowest write-coupling first):
- single store: `_hint_evidence_types`, with C8 as its single owning write-cluster;
- no non-infra cross-cluster direct call (C8 → C1 revision seam only);
- smallest rollback surface;
- C9's `_evidence_type_modifier_for_claim` *reads* `_hint_evidence_types` but is
  NOT moved in this PR (its read of the store still resolves through `self`).

## Exact methods moved (4)
```
_validate_hint_evidence_type_values   (private, shared strict validator)
register_hint_evidence_types          (public)
unregister_hint_evidence_types        (public)
clear_hint_evidence_types             (public)
```
Moved verbatim. Not moved (explicitly): `_hint_evidence_types` (state, stays in
`Engine.__init__`), `_evidence_type_modifier_for_claim` / `_compute_effective_confidence_core`
(C9), `_advance_state_revision` / `state_identity` (C1), `_state_view` / `_install` (C10).

## Before → after ownership
| method | before declaring class | after declaring class |
|---|---|---|
| the four C8 methods | `Engine` (`ragcore.engine`) | `HintEvidenceMixin` (`ragcore._engine.hint_evidence`) |
Engine becomes `class Engine(HintEvidenceMixin)`; the methods resolve through the
MRO (no forwarding wrapper). engine.py 1596 → 1491.

## Engine state did NOT move (proof)
`Engine.__init__` still sets `self._hint_evidence_types: set[int] = set()`; the
mixin contains no `__init__`, no state, no store creation, no Engine
back-reference. The mixin reaches state via `self._hint_evidence_types` and the
revision seam via `self._advance_state_revision()`, both resolved on the Engine
instance. Snapshot still serialises `hint_evidence_types` (schema v2, sorted
list); restore round-trips equal; top-level keys remain 18.

## Import graph
```
ragcore.engine -> ragcore._engine.hint_evidence        (added)
ragcore._engine.hint_evidence imports: {__future__, collections.abc}  (stdlib only)
ragcore._engine.hint_evidence -> ragcore.engine        : NONE (no cycle)
confidence.py / serialization.py / types.py / ragcore/__init__.py : unchanged
```

## AST equivalence (behaviour-preserving move)
`ast.dump(..., include_attributes=False)` of each moved method, baseline
`65ee71b:ragcore/engine.py` (Engine) vs `ragcore/_engine/hint_evidence.py`
(HintEvidenceMixin): **4/4 identical**. The four methods are absent from the
current Engine class body.

## Accepted introspection deltas (Phase 3A-approved), measured
```
the four C8 methods:
  __module__       ragcore.engine          -> ragcore._engine.hint_evidence
  __qualname__     Engine.<m>              -> HintEvidenceMixin.<m>
  declaring class  Engine                  -> HintEvidenceMixin
  Engine.__dict__  present                 -> inherited / absent
  Engine.__mro__   + HintEvidenceMixin
```
## Preserved runtime surface, measured
```
from ragcore import Engine                       OK
Engine.__module__ == "ragcore.engine"            OK
runtime public methods                           42
ragcore.__all__                                  50
exact public + validator signatures              unchanged
getattr(Engine, <C8>) resolves to mixin function OK
setattr / monkeypatch on Engine (validator, C1 seam) OK
inspect.getsource(Engine.<C8>) returns real body OK (no super(), no wrapper)
no extra delegation traceback frame
```

## Behavioural probes (all pass)
- revision gate `[Engine(), reg[], reg[1], reg[1], unreg[99], unreg[1], clear(empty),
  reg[2,3], clear()]` → revisions `[0,0,1,1,1,2,2,3,4]` (advance only on real
  growth/shrink/non-empty-clear).
- strict validation: `[1,"2"]`, `[1,True]`, `"ab"`, `b"ab"` → `TypeError`, set/revision
  unchanged; negative / zero / large int and generator accepted.
- snapshot: `hint_evidence_types` sorted-list serialisation, restore equal,
  canonical 18 top-level keys.

## Tests
```
new: tests/test_engine_phase3b_hint_evidence_mixin.py (9 runtime, location-agnostic locks)
targeted: test_engine_evidence_type_strict_validation, test_engine_hint_evidence_type_deregistration,
          test_engine_phase0_taxonomy -> 103 passed
full suite: 2070 -> 2079 passed (+9 new; no existing test weakened or changed)
```
Existing contracts already locking C8 behaviour (so no duplicate validation
tests were added): strict-validation, deregistration, phase-0 taxonomy
(behavioural round-trip + public 42 runtime), surface-freeze signatures.

## Files changed / line delta
```
3 files, +233/-107
  ragcore/_engine/hint_evidence.py                       +126  (new)
  ragcore/engine.py                                      +2/-107
  tests/test_engine_phase3b_hint_evidence_mixin.py       +105  (new)
docs/dev/PR_086_…                                        (this file)
NOT changed: ragcore/types.py, ragcore/__init__.py, _engine/{confidence,serialization}.py,
snapshot schema, examples/**, config/deps, any other cluster, Phase 3A docs.
```

## Commit chronology
```
ae5c083 refactor(engine): extract C8 hint-evidence mixin
c83f1c1 test(engine): lock inherited C8 runtime contracts
<this>  docs(dev): record Phase 3B-1 hint-evidence mixin extraction
```
No commit amended, rebased, or squashed. Review-correction commits, if any,
appended after independent review.

## STOP-AND-REPORT review
None triggered: the four methods moved AST-identically; no Engine wrapper needed;
no public-signature / `Engine.__module__` / public-count / `__all__` change; no
Engine state moved; no C9/C1 method moved; no generic store / registry / delegate;
`hint_evidence.py` does not import `ragcore.engine`; no import cycle; snapshot
schema/keys/bytes unchanged; revision semantics unchanged; no existing test
weakened; no source-location lock added.

## Lifecycle
OPEN — Draft. Recommendation on completion: **READY FOR GPT INDEPENDENT REVIEW**
(not self-merged). **Phase 3B-2 (C3 relations) remains prohibited** until this PR
passes independent review (APPROVE), squash merge, and post-merge `main`
verification.
