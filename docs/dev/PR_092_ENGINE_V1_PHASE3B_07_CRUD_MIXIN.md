# PR_092 — Engine v1 Phase 3B-7: Extract C2 Entity/Observation/Claim/Evidence CRUD Mixin (development record)

GitHub PR **#93** (internal dev-record number = GitHub number − 1 = 092).

## Identity / purpose
Seventh production-code decomposition under the approved Phase 3A ADR. A
behaviour-preserving move of the nine C2 CRUD methods from the `Engine` class body
into a private `CrudMixin`. No change to the CRUD value semantics, validation
order, failure labels, id/revision allocation order, signatures, snapshot/
serialization, or public API.

## Baseline
```
baseline main   628fc68afa0d123e0131293eaa8902c3e3134618  (Phase 3B-6 merged, #92)
baseline tests  2133 passed (local; no GitHub Actions on this repo)
guard           HEAD == 628fc68a verified; tracked working tree clean before start
```

## Exact methods moved (9)
```
add_entity          (mutator: writes _entities;  _allocate_id + _advance_state_revision)
get_entity          (read-only)
add_observation     (mutator: writes _observations; _assert_entity_exists guard)
get_observation     (read-only)
add_claim           (mutator: writes _claims;  distinct subject label + status/ScoreValue/id order)
get_claim           (read-only)
add_evidence        (mutator: writes _evidences; _assert_claim_exists guard + ScoreValue/id order)
get_evidence        (read-only)
evidences_for_claim (read-only; _assert_claim_exists guard)
public 9 / mutators 4 / readers 5 / total 9
```
**Not moved:** the four stores (`_entities` / `_observations` / `_claims` /
`_evidences` stay in `Engine.__init__`); the C1 seams (`_allocate_id` /
`_advance_state_revision` / `_assert_entity_exists` / `_assert_claim_exists` stay
on the Engine base); the C5 lifecycle transitions; serialization / snapshot
integrity; the `Entity` / `Observation` / `Claim` / `Evidence` / `ScoreValue` /
`CLAIM_STATUS_CANDIDATE` types (`ragcore.types`).

## add_claim distinct subject label (preserved verbatim)
`add_claim` rejects an unknown subject with a **direct membership check** and the
distinct label `"unknown subject_id (entity): {subject_id}"` — NOT
`self._assert_entity_exists`, which raises an `entity_id`-worded label. The inline
check is moved verbatim so the label, the exception type (`KeyError`), and the
order (subject check → `_validate_claim_status_admission` → `ScoreValue` →
`_allocate_id` → store → `_advance_state_revision`) are all preserved. A failed
admission therefore consumes no claim id and bumps no revision.

## add_evidence validation order (preserved verbatim)
`add_evidence` runs `self._assert_claim_exists(claim_id)` (label
`"unknown claim_id: {claim_id}"`) BEFORE constructing the `ScoreValue(strength)`,
and validates the strength BEFORE `_allocate_id` (PR73-M04 §3 C1), so an unknown
claim and a bad strength both consume no evidence id.

## C2 ↔ C5 shared `_claims` store (operational boundary, preserved)
`_claims` is the one operational shared-write store this phase. C2 (`add_claim`
inserts / `get_claim` reads) and the C5 lifecycle transition (which **stays on
Engine** in 3B-7) replace a Claim's status on the **same dict object** via `self`.
The new test pins `engine._claims is claims_store` across an `add_claim` →
`register_contradiction` → `refute_claim_if_ready` → `get_claim` sequence and
confirms `get_claim` observes the C5 status replacement.

## Before → after ownership / accumulated MRO
`class Engine(HintEvidenceMixin, RelationsMixin, RulesMixin, GapsMixin, ConfidenceAdaptersMixin, LifecycleHistoryMixin):`
→ append `CrudMixin`. All seven mixins in `Engine.__mro__`; the nine methods
resolve via the MRO (no forwarding wrapper). engine.py 905 → 736; the emptied
Region C (entity/observation/claim/evidence CRUD) removed.

## Engine state did NOT move (proof)
`Engine.__init__` still owns `_entities` / `_observations` / `_claims` /
`_evidences`; the `Entity` / `Observation` / `Claim` / `Evidence` imports are
retained for those annotations. The mixin has no `__init__` / state /
back-reference; it writes the four stores and reaches the C1 id/revision/guard
seams through `self`. Snapshot still serialises the four stores; restore
round-trips; 18 top-level keys.

## Import graph
```
ragcore.engine -> ragcore._engine.crud                         (added)
ragcore._engine.crud imports: {__future__, ragcore._engine.confidence,
    ragcore.types (CLAIM_STATUS_CANDIDATE, Claim, Entity, Evidence, Observation, ScoreValue)}
ragcore._engine.crud -> ragcore.engine / other mixins : NONE   (no cycle, no inter-mixin coupling)
```
The now-unused `ScoreValue` import was dropped from `ragcore/engine.py` (it moved
into the mixin with `add_claim`/`add_evidence`); `CLAIM_STATUS_CANDIDATE` (used by
C5), `confidence` (used by `from_snapshot`), and the four entity/record types
(used by `__init__` annotations) remain imported in engine.py.

## AST equivalence
`ast.dump(..., include_attributes=False)` baseline `628fc68:ragcore/engine.py`
(Engine) vs `ragcore/_engine/crud.py` (CrudMixin): **9/9 identical**; all nine
methods absent from the current Engine class body.

## Accepted introspection deltas / preserved surface
the nine methods → `__module__` `ragcore._engine.crud`, `__qualname__`
`CrudMixin.*`, declaring class, inherited. Preserved: `from ragcore import Engine`;
`Engine.__module__ == "ragcore.engine"`; runtime public **42**; `__all__` **50**;
exact signatures (incl. `add_claim` keyword-only `base_confidence`/`status`/
`flags`); `getattr`/`setattr`/`monkeypatch`; `getsource` real bodies; no extra
traceback frame; the six prior mixins unchanged and in the MRO.

## Exact signatures (unchanged)
```
add_entity(self, entity_type: int, flags: int = 0) -> int
get_entity(self, entity_id: int) -> Entity
add_observation(self, entity_id: int, raw_ref_id: int, observation_type: int, source_type: int = 0) -> int
get_observation(self, observation_id: int) -> Observation
add_claim(self, subject_id: int, claim_type: int, rule_id: int, rule_version: int, reason_code: int, *, base_confidence: float = 0.5, status: int = CLAIM_STATUS_CANDIDATE, flags: int = 0) -> int
get_claim(self, claim_id: int) -> Claim
add_evidence(self, claim_id: int, raw_ref_id: int, evidence_type: int, strength: float) -> int
get_evidence(self, evidence_id: int) -> Evidence
evidences_for_claim(self, claim_id: int) -> list[Evidence]
```
(`inspect.signature` renders `status`'s default as `0`, the value of
`CLAIM_STATUS_CANDIDATE`; the test locks that authoritative string.)

## Ownership / no-promotion + patch-site scan (3 sites migrated)
The new test locks, for all nine C2 methods: `name not in Engine.__dict__`,
`_defining_class(Engine, name) is CrudMixin`,
`getattr(Engine, name) is CrudMixin.__dict__[name]` (plus `__module__`/
`__qualname__`). A repository-wide scan (`setattr(Engine` / `monkeypatch.setattr(
Engine` / `Engine.<name> =` against the nine C2 names) found **three** existing
sites in `tests/test_complete_domain_neutral_reference_operation.py` that patched a
C2 method directly on `Engine`. After extraction those methods are inherited, so a
`setattr`-based restore would have **promoted** them into `Engine.__dict__`. All
three were migrated to patch the runtime-resolved **defining class** via a
module-level `_defining_class()` helper (the count was determined by the actual
scan, not pre-estimated):
- `_install_engine_method_spies` (mutation/read spy installer);
- the `wrapped_final_state` spy installer;
- the `proxy_get_claim` wrapper.
The new C2 test additionally asserts, **after** a `monkeypatch.context()` closes,
that the spied C2 method identity is restored on `CrudMixin` and was never promoted
onto `Engine`.

## Behavioural probes (all pass)
- C2 → C1 seam: each of the four mutators bumps `_advance_state_revision` exactly
  once via self/MRO (the seam is spied on its defining class — the Engine base —
  leaving `Engine.__dict__` unpolluted and the original restored).
- add_claim failure order: unknown subject → `KeyError("unknown subject_id
  (entity): 99999")` with snapshot + `state_identity` unchanged and the next
  successful claim taking the sequential id (no gap); invalid `status` → `ValueError`
  before mutation; out-of-range `base_confidence` → `ValueError` consuming no id.
- add_evidence: unknown claim → `KeyError("unknown claim_id: 88888")` before the
  strength `ScoreValue`; out-of-range strength → `ValueError` consuming no id.
- C2 ↔ C5 shared `_claims`: insert + status replacement on the same dict; `get_claim`
  reflects the C5 refutation.
- readers (`get_entity`/`get_observation`/`get_claim`/`get_evidence`/
  `evidences_for_claim`) are read-only (snapshot + `state_identity` unchanged) and
  raise `KeyError` on an unknown id with no state change.

## Tests
```
new: tests/test_engine_phase3b_crud_mixin.py (16 runtime locks)
migrated (no semantic change): tests/test_complete_domain_neutral_reference_operation.py
          (3 C2 patch sites -> defining-class patching; full file still 199 passed)
targeted: test_engine_crud / claim / evidence / observation / entity, state
          identity, snapshot round-trip/migration/integrity, surface freeze,
          packet, 3B-1..3B-6 mixin tests, complete_domain_neutral
full suite: 2133 -> 2149 passed (+16 new; no existing test weakened or deleted)
```

## Files changed / line delta
```
production/test (stable): 4 files, +597/-187
  ragcore/_engine/crud.py                                    +198  (new)
  ragcore/engine.py                                          +2/-171
  tests/test_engine_phase3b_crud_mixin.py                    +367  (new)
  tests/test_complete_domain_neutral_reference_operation.py  +30/-16 (patch-site migration)
+ docs/dev/PR_092_…                                          (this dev record; its own size
                                                              is self-referential — see the PR #93 diff)
Authoritative full-PR total (incl. this dev record): the GitHub PR #93 diff.
NOT changed: ragcore/_engine/{confidence,serialization,hint_evidence,relations,
rules,gaps,confidence_adapters,lifecycle_history}.py, ragcore/_engine/__init__.py,
ragcore/types.py, ragcore/__init__.py, snapshot schema, examples/**, config/deps,
C5 lifecycle transitions, Phase 3A docs.
```

## Commit chronology
Stable implementation/test chronology:
```
eff83f6  production extraction (engine.py + crud.py)
bc46bf4  extraction tests + 3 C2 patch-site migrations
```
This versioned record intentionally does not self-pin the SHA of the commit that
adds the record itself. Any later review-correction commits are recorded in the
GitHub PR #93 commit history. No commit amended, rebased, or squashed.

## STOP-AND-REPORT review
None triggered: base SHA 628fc68; AST 9/9 identical; exactly 9 C2 methods; no
docstring/body/signature change; no Engine wrapper/super(); all nine methods absent
from Engine.__dict__; the four stores stay on Engine; the C1 seams stay on the
Engine base; subject/claim failure labels + validation orders unchanged; no
snapshot/serialization change; public 42 / __all__ 50 / snapshot 2·18 / packet 7
unchanged; the six prior mixins unchanged; no import cycle; the three C2
direct-Engine patch sites were migrated to defining-class patching (no existing
test weakened); no source-location lock added.

## Lifecycle
OPEN — Draft. Recommendation on completion: **READY FOR GPT INDEPENDENT REVIEW**
(not self-merged). **Phase 3B-8 (C5) remains prohibited** until this PR passes
independent review (APPROVE), all corrections committed, squash merge, branch
cleanup, and post-merge `main` verification.
