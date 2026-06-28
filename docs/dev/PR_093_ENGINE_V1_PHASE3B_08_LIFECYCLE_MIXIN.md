# PR_093 — Engine v1 Phase 3B-8: Extract C5 Lifecycle Mixin (development record)

GitHub PR **#94** (internal dev-record number = GitHub number − 1 = 093).

## Identity / purpose
Eighth production-code decomposition under the approved Phase 3A ADR. A
behaviour-preserving move of the twelve C5 lifecycle-transition + contradiction-
state methods from the `Engine` class body into a private `LifecycleMixin`, and a
relocation of the private refutation-strength threshold with the two refute APIs
that use it. No change to status-transition conditions, contradiction
registration/resolution semantics, idempotent no-op meaning, KeyError/ValueError
text, active/resolved set algebra, ordering, the strength threshold (0.8), the
ANY-active vs most-recent-only policy split, the status-write → lifecycle-record →
revision-advance order, transition labels, revision-advance conditions/counts,
snapshot, or public API.

## Baseline
```
baseline main   acb041b8445faae6fb30b84c3816a8af863148e4  (Phase 3B-7 merged, #93)
baseline tests  2149 passed (local; no GitHub Actions on this repo)
guard           HEAD == acb041b8 verified; tracked working tree clean before start
```

## Exact methods moved (12)
```
mutators (8):
  confirm_claim_if_ready                          candidate  -> confirmed
  register_contradiction                          contradiction registration (idempotent)
  refute_claim_if_ready                           candidate  -> refuted
  dispute_claim_if_ready                          confirmed  -> disputed
  register_contradiction_resolution               resolution registration (relationship-bound)
  resolve_disputed_claim_if_ready                 disputed   -> confirmed
  refute_disputed_claim_if_ready                  disputed   -> refuted (ANY active strength >= 0.8)
  refute_disputed_claim_if_ready_by_freshness     disputed   -> refuted (FIRST-by-freshness >= 0.8)
readers (4):
  contradictions_for_claim                        evidence_id ascending
  resolved_contradictions_for_claim               evidence_id ascending
  active_contradictions_for_claim                 (contradictions - resolved) ascending
  active_contradictions_by_freshness              same active set, evidence_id descending
public 12 / private 0 / mutators 8 / readers 4 / total 12
```
**Not moved:** the four stores (`_claims` / `_evidences` / `_contradictions` /
`_resolved_contradictions` stay in `Engine.__init__`); the C1 seams
(`_assert_claim_exists` / `_assert_evidence_exists` / `_advance_state_revision`);
the C4 queries (`gaps_for_claim` / `gap_resolution`, GapsMixin); the C6 recorder
(`_record_claim_lifecycle_transition`, LifecycleHistoryMixin); the C9 confidence
adapters that *call into* C5; serialization / snapshot.

## Threshold relocation (single private authority preserved)
`_REFUTATION_STRENGTH_THRESHOLD = 0.8` moves from `ragcore.engine` (module level)
to `ragcore._engine.lifecycle` (module level), with the two refute APIs that use
it. Preserved: name, value `0.8`, `>=` comparison, private status (never in
`__all__`, never a public attribute), and single-authority reuse by both PR10-A
(`refute_disputed_claim_if_ready`) and PR11-B
(`refute_disputed_claim_if_ready_by_freshness`). Accepted introspection delta:
`ragcore.engine._REFUTATION_STRENGTH_THRESHOLD` is no longer the declaring (or any)
location. A repository reference scan found NO runtime dependency on the
`ragcore.engine` location: the only non-doc references are the definition + two
uses (all inside the two moving methods) and two **negative** test assertions
(`not hasattr(ragcore, …)` / `not hasattr(ragcore.types, …)`), which still hold.
No alias is left behind; no STOP-AND-REPORT was triggered.

## Load-bearing transition order (preserved, AST-identical)
Every successful transition keeps: capture `old_status` → `self._claims[claim_id] =
replace(claim, status=…)` → `self._record_claim_lifecycle_transition(…)` →
`self._advance_state_revision()` → `return True`. The recorder runs **after** the
status write and **before** the revision advance (locked by the new test at call
time: `self._claims[claim_id].status == to_status` and `self._state_revision` not
yet advanced). No-op / failure paths mutate nothing, record nothing, advance no
revision.

## Six status transitions (labels preserved)
```
candidate  -> confirmed   confirm_claim_if_ready                        "confirm_if_ready"
candidate  -> refuted     refute_claim_if_ready                         "refute_if_ready"
confirmed  -> disputed    dispute_claim_if_ready                        "dispute_if_ready"
disputed   -> confirmed   resolve_disputed_claim_if_ready               "resolve_disputed_if_ready"
disputed   -> refuted     refute_disputed_claim_if_ready                "refute_disputed_if_ready"
disputed   -> refuted     refute_disputed_claim_if_ready_by_freshness   "refute_disputed_by_freshness_if_ready"
```

## Disputed-refutation policy split (NOT unified)
`refute_disputed_claim_if_ready` (PR10-A) inspects **ANY** active contradiction and
fires if any strength `>= 0.8`. `refute_disputed_claim_if_ready_by_freshness`
(PR11-B) inspects only `active_contradictions_by_freshness()[0]` (the most recent)
and fires if that one strength `>= 0.8`. Same target status (REFUTED), same single
threshold, different input set. The two ASTs are moved verbatim; the policies stay
distinct.

## Before → after ownership / accumulated MRO
`class Engine(HintEvidenceMixin, RelationsMixin, RulesMixin, GapsMixin, ConfidenceAdaptersMixin, LifecycleHistoryMixin, CrudMixin):`
→ append `LifecycleMixin`. All eight mixins in `Engine.__mro__`; the twelve methods
resolve via the MRO (no forwarding wrapper). engine.py 736 → 334; the emptied
Region E (lifecycle) / Region F (freshness queries) / Region G (freshness-based
refute) and the module-level threshold section removed.

## Engine state did NOT move (proof)
`Engine.__init__` still owns `_claims` / `_evidences` / `_contradictions` /
`_resolved_contradictions`. The mixin has no `__init__` / state / back-reference;
it writes the four stores and reaches the C1 / C4 / C6 seams through `self`.
Snapshot still serialises those stores; restore round-trips; 18 top-level keys.

## Import graph
```
ragcore.engine -> ragcore._engine.lifecycle                  (added)
ragcore._engine.lifecycle imports: {__future__, dataclasses.replace,
    ragcore.types (CLAIM_STATUS_CANDIDATE/CONFIRMED/DISPUTED/REFUTED)}
ragcore._engine.lifecycle -> ragcore.engine / other mixins : NONE  (no cycle, no inter-mixin coupling)
```
The C4 (`gaps_for_claim` / `gap_resolution`), C6 (`_record_claim_lifecycle_transition`)
and C1 dependencies are all resolved through `self`/MRO — none imported. Newly-unused
imports dropped from engine.py (each confirmed used in the baseline and unused after
the C5 move): `dataclasses.replace`, and `CLAIM_STATUS_CANDIDATE` /
`CLAIM_STATUS_CONFIRMED` / `CLAIM_STATUS_DISPUTED` / `CLAIM_STATUS_REFUTED` from
`ragcore.types`. `asdict` and the Phase-1 serialization helpers (C5-unrelated) were
left untouched.

## Measured cross-cluster edges (AST Call nodes in lifecycle.py)
```
C5 -> C1   22   (_assert_claim_exists 12 / _assert_evidence_exists 2 / _advance_state_revision 8)
C5 -> C4    2   (gaps_for_claim / gap_resolution, in confirm_claim_if_ready)
C5 -> C6    6   (_record_claim_lifecycle_transition, the six successful transitions)
C9 -> C5    2   (incoming: _count_modifier_for_claim -> active_contradictions_for_claim;
                 _freshness_modifier_for_claim -> active_contradictions_by_freshness)
C2 <-> C5   0   direct calls (the only coupling is the shared Engine-owned _claims dict)
```

## AST equivalence
`ast.dump(..., include_attributes=False)` baseline `acb041b:ragcore/engine.py`
(Engine) vs `ragcore/_engine/lifecycle.py` (LifecycleMixin): **12/12 identical**;
all twelve methods absent from the current Engine class body. The threshold name and
value are preserved as a single authority (verified separately from the method ASTs).

## Accepted introspection deltas / preserved surface
the twelve methods → `__module__` `ragcore._engine.lifecycle`, `__qualname__`
`LifecycleMixin.*`, declaring class, inherited. Preserved: `from ragcore import
Engine`; `Engine.__module__ == "ragcore.engine"`; runtime public **42**; `__all__`
**50**; exact signatures; `getattr`/`setattr`/`monkeypatch`; `getsource` real
bodies; no extra traceback frame; the seven prior mixins unchanged and in the MRO.

## Exact signatures (unchanged)
```
confirm_claim_if_ready(self, claim_id: int) -> bool
register_contradiction(self, claim_id: int, evidence_id: int) -> bool
contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]
refute_claim_if_ready(self, claim_id: int) -> bool
dispute_claim_if_ready(self, claim_id: int) -> bool
register_contradiction_resolution(self, claim_id: int, evidence_id: int) -> bool
resolved_contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]
active_contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]
resolve_disputed_claim_if_ready(self, claim_id: int) -> bool
refute_disputed_claim_if_ready(self, claim_id: int) -> bool
active_contradictions_by_freshness(self, claim_id: int) -> tuple[int, ...]
refute_disputed_claim_if_ready_by_freshness(self, claim_id: int) -> bool
```

## Ownership / no-promotion + patch-site scan (0 migrations)
The new test locks, for all twelve C5 methods: `name not in Engine.__dict__`,
`_defining_class(Engine, name) is LifecycleMixin`,
`getattr(Engine, name) is LifecycleMixin.__dict__[name]` (plus `__module__`/
`__qualname__`). A repository-wide scan (`setattr(Engine` / `monkeypatch.setattr(
Engine` / `patch.object(Engine` / `Engine.<name> =` against the twelve C5 names)
found **NO test that patches a C5 method directly on Engine**. The one generic
name-driven installer that includes a C5 name
(`confirm_claim_if_ready` in `test_complete_domain_neutral_reference_operation.py`)
already patches the runtime-resolved **defining class** (the `_defining_class`
infrastructure migrated in Phase 3B-5/3B-7), so it resolves to `LifecycleMixin`
after this extraction with no promotion. Empirically confirmed: after running the
three installer-bearing suites in one process, no C5 name is in `Engine.__dict__`
and all twelve remain owned by `LifecycleMixin`. **Patch-site migration count: 0**
(determined by the actual scan, not pre-declared).

## Behavioural probes (all pass)
- C5 → C4 seam: a confirm with a single resolved gap calls `self.gaps_for_claim`
  **once** and `self.gap_resolution` **once**; status → CONFIRMED; the queries are
  spied on GapsMixin so `Engine.__dict__` stays unpolluted and the originals
  restore.
- C5 → C6 seam (six transitions): each of the six successful transitions reaches
  the inherited recorder **exactly once** with the exact (from, to, label); at
  record time the status is already replaced and the revision not yet advanced; the
  revision advances exactly once afterward; six distinct labels.
- C9 → C5 incoming seam: `_count_modifier_for_claim` calls
  `active_contradictions_for_claim` **once**; `_freshness_modifier_for_claim` calls
  `active_contradictions_by_freshness` **once** (queries spied on LifecycleMixin).
- C5 → C1 revision gate: `register_contradiction` new +1 / duplicate +0;
  `register_contradiction_resolution` new +1 / duplicate +0 / invalid (ValueError)
  +0; successful transition +1 / no-op +0.
- C2 ↔ C5 shared `_claims`: C2 inserts + C5 status replacement on the same dict
  object (`engine._claims is claims_store`); `get_claim` reflects the replacement
  and stays owned by CrudMixin.
- contradiction store ownership: `_contradictions` / `_resolved_contradictions`
  identity unchanged across register/resolve; original contradiction entry
  preserved; only the active set shrinks.
- readers read-only: the four readers leave snapshot + `state_identity` unchanged,
  return `tuple[int, …]`, ascending vs descending orderings preserved, and raise
  `KeyError` on an unknown claim with no state change.

## Tests
```
new: tests/test_engine_phase3b_lifecycle_mixin.py (16 runtime locks)
migrated: none (0 C5 direct-Engine patch sites; the one C5-touching generic
          installer already uses defining-class resolution)
targeted: claim lifecycle / disputed refutation / freshness refute / lifecycle
          history / state identity + revision / snapshot round-trip-migration-
          integrity / surface freeze / effective-confidence trace / complete
          reference operation / Phase 3B-1..3B-7 mixin tests
full suite: 2149 -> 2165 passed (+16 new; no existing test weakened or deleted)
```

## Files changed / line delta
```
production/test (stable): 3 files, +887/-405
  ragcore/_engine/lifecycle.py                       +415  (new)
  ragcore/engine.py                                  +3/-405
  tests/test_engine_phase3b_lifecycle_mixin.py       +469  (new)
+ docs/dev/PR_093_…                                  (this dev record; its own size
                                                      is self-referential — see the PR #94 diff)
Authoritative full-PR total (incl. this dev record): the GitHub PR #94 diff.
NOT changed: ragcore/_engine/{confidence,serialization,hint_evidence,relations,
rules,gaps,confidence_adapters,lifecycle_history,crud}.py, ragcore/_engine/__init__.py,
ragcore/types.py, ragcore/__init__.py, snapshot schema, examples/**, config/deps,
Phase 3A docs.
```

## Commit chronology
Stable implementation/test chronology:
```
20122df  production extraction (engine.py + lifecycle.py, threshold relocation)
8578ae6  extraction tests (16 ownership / seam / order locks)
```
This versioned record intentionally does not self-pin the SHA of the commit that
adds the record itself. Any later review-correction commits are recorded in the
GitHub PR #94 commit history. No commit amended, rebased, or squashed. If a review
correction touches production/test, the stable subtotal above is re-measured.

## STOP-AND-REPORT review
None triggered: base SHA acb041b8; AST 12/12 identical; exactly 12 C5 methods; no
docstring/body/signature change; threshold value `0.8` / `>=` preserved as one
authority; transition labels unchanged; status-write → record → revision order
unchanged; no event/revision on no-op; C4 reached via `gaps_for_claim`/
`gap_resolution` (no direct-store rewrite); C6 recorder reached via `self` (not
imported); the four stores stay on Engine; no wrapper/super/delegate; all twelve
methods absent from `Engine.__dict__`; no direct-Engine C5 patch site exists; no
snapshot/serialization change; public 42 / __all__ 50 / snapshot 2·18 / packet 7
unchanged; confidence.py byte-identical; the seven prior mixins unchanged; no import
cycle; no existing test weakened.

## Lifecycle
OPEN — Draft. Recommendation on completion: **READY FOR GPT INDEPENDENT REVIEW**
(not self-merged). **Phase 3B-9 (C10 snapshot) remains prohibited** until this PR
passes independent review (APPROVE), all corrections committed, squash merge,
branch cleanup, and post-merge `main` verification.
