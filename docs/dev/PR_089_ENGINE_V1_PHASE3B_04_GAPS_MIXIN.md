# PR_089 — Engine v1 Phase 3B-4: Extract C4 Gaps Mixin (development record)

GitHub PR **#90** (internal dev-record number = GitHub number − 1 = 089;
confirmed by creating the Draft PR first).

## Identity / purpose
Fourth and most complex production-code decomposition under the approved Phase 3A
ADR. A behaviour-preserving move of the five C4 gap methods from the `Engine`
class body into a private `GapsMixin`. No change to the dedup contract,
severity-before-dedup ordering, cross-claim gap sharing, conditional revision,
first-evidence-wins resolution, signatures, snapshot, or public API.

## Baseline
```
baseline main   275676bd2a205b85094869890b81b4408a15951b (Phase 3B-3 merged)
baseline tests  2098 passed (local; no GitHub Actions on this repo)
guard           HEAD == 275676b verified; tracked working tree clean before start
```

## Why C4 fourth
Per the Phase 3A 3B sequence: it is the highest-coupling cluster among the
single-owner set — four C4 stores, a read of the C2 `_claims`/`_evidences`
stores, an intra-C4 self-call (`resolve_gaps_for_evidence` -> `gaps_for_claim`),
and a C5 -> C4 cross-cluster runtime call (`confirm_claim_if_ready`). Scheduled
after C8/C3/C7 and before C9.

## Exact methods moved (5)
```
add_gap                     (public, mutator: _gaps A, _gap_dedup_index A, _claim_gap_refs A/W)
get_gap                     (public, read-only)
gaps_for_claim              (public, read-only; ascending by Gap.id)
resolve_gaps_for_evidence   (public, mutator: _gap_resolutions A; first-evidence-wins)
gap_resolution              (public, read-only)
```
**Not moved:** the four C4 stores (`_gaps` / `_gap_dedup_index` /
`_claim_gap_refs` / `_gap_resolutions`, in `Engine.__init__`); the C2 stores this
cluster reads (`_claims` / `_evidences`); the C1 seams (`_assert_claim_exists` /
`_assert_evidence_exists` / `_assert_gap_exists` / `_allocate_id` /
`_advance_state_revision`); C5 `confirm_claim_if_ready`; the confidence adapter
`_gap_modifier_for_claim`; snapshot/install; `Gap` / `ScoreValue` (`ragcore.types`).

## Preserved C4 contracts (probed, all pass)
- **add_gap ordering:** `_assert_claim_exists` -> `ScoreValue(severity)` ->
  read `_claims[claim_id].subject_id` -> build dedup key -> hit/miss. Severity is
  admitted BEFORE the dedup decision, so an invalid severity raises on a dedup-hit
  path too and adds no claim->gap ref / no id / no store change / no revision.
- **dedup key = (subject_id, rule_id, gap_type, required_evidence_type)** —
  `claim_id` and `severity` are NOT in the key.
- **miss:** `_allocate_id("gap")` -> `_gaps[id]=Gap(...)` -> `_gap_dedup_index[key]=id`
  (membership-guarded insert, `A`) -> `_claim_gap_refs.setdefault(claim_id,set()).add(id)`
  -> revision +1. Gap fields (id / claim_id=first claim / type / required_evidence_type
  / severity / created_by_rule) exact.
- **same-claim hit:** full no-op — same id, Gap/index/refs/next-id/revision all unchanged.
- **cross-claim shared hit:** same subject's other claim with the same key returns
  the same gap_id, adds only the claim->gap ref, revision +1, no id allocation, and
  **Gap.claim_id + Gap.severity keep the FIRST registrant's values.** A second call
  for the same claim is a no-op.
- **lookup:** `gaps_for_claim` returns a `list[Gap]` ascending by Gap.id (shared
  gaps included via the ref set, not a `Gap.claim_id` filter); `get_gap` is a direct
  dict read; unknown claim/gap -> KeyError; reads do not advance the revision.
- **resolution:** `resolve_gaps_for_evidence` selects matching unresolved gaps
  (`required_evidence_type == evidence.type`), skips already-resolved ones,
  registers gap->evidence first-evidence-wins (no overwrite), advances the revision
  exactly once when >=1 gap is newly resolved (zero on no match / repeat), and
  returns an ascending tuple. It keeps calling the inherited `self.gaps_for_claim`.
- **C5 integration:** `confirm_claim_if_ready` is False with an unresolved
  referenced gap and True once that gap is resolved — reaching the inherited C4
  methods through the MRO (no C5 change).

## C1 seam call counts (spies installed after setup)
```
add_gap miss          : _assert_claim_exists ×1, _allocate_id ×1, _advance_state_revision ×1
add_gap same-claim hit: _assert_claim_exists ×1, _allocate_id ×0, _advance_state_revision ×0
add_gap new-ref hit   : _assert_claim_exists ×1, _allocate_id ×0, _advance_state_revision ×1
resolve (match)       : _assert_evidence_exists ×1, gaps_for_claim ×1, _advance_state_revision ×1
resolve (no match)    : _assert_evidence_exists ×1, gaps_for_claim ×1, _advance_state_revision ×0
gap_resolution        : _assert_gap_exists ×1
```

## Before → after ownership / accumulated MRO
`class Engine(HintEvidenceMixin, RelationsMixin, RulesMixin):` →
`class Engine(HintEvidenceMixin, RelationsMixin, RulesMixin, GapsMixin):` (new
mixin appended, existing prefix preserved). All four mixins in `Engine.__mro__`;
the five methods resolve via the MRO (no forwarding wrapper). engine.py 1345 → 1219.

## Engine state did NOT move (proof)
`Engine.__init__` still owns the four C4 stores; the `Gap` import is retained for
`self._gaps: dict[int, Gap]`. The mixin has no `__init__`/state/back-reference; it
reaches the gap stores, the C2 read stores, and the C1 seams through `self`.
Snapshot still serialises all four stores; restore round-trips; 18 top-level keys.

## Import graph
```
ragcore.engine -> ragcore._engine.gaps            (added)
ragcore._engine.gaps imports: {__future__, ragcore.types}  (Gap, ScoreValue)
ragcore._engine.gaps -> ragcore.engine / other mixins : NONE  (no cycle, no inter-mixin coupling)
hint_evidence / relations / rules / confidence / serialization / types / ragcore.__init__ : unchanged
```
The C4->C4 (`resolve` -> `gaps_for_claim`) and C5->C4 (`confirm` -> C4) calls are
Python runtime `self` resolution, not module-import coupling.

## AST equivalence
`ast.dump(..., include_attributes=False)` baseline `275676b:ragcore/engine.py`
(Engine) vs `ragcore/_engine/gaps.py` (GapsMixin): **5/5 identical**; all five
methods absent from the current Engine class body.

## Accepted introspection deltas / preserved surface
the five methods' `__module__` -> `ragcore._engine.gaps`, `__qualname__` ->
`GapsMixin.*`, declaring class -> `GapsMixin`, inherited. Preserved:
`from ragcore import Engine`; `Engine.__module__ == "ragcore.engine"`; runtime
public **42**; `ragcore.__all__` **50**; exact signatures; `getattr`/`setattr`/
`monkeypatch` on Engine; `getsource` real body; no extra traceback frame; the
three prior mixins unchanged and in the MRO.

## Exact signatures (unchanged)
```
add_gap(self, claim_id, gap_type, required_evidence_type, severity, rule_id) -> int
get_gap(self, gap_id) -> Gap
gaps_for_claim(self, claim_id) -> list[Gap]
resolve_gaps_for_evidence(self, evidence_id) -> tuple[int, ...]
gap_resolution(self, gap_id) -> int | None
```

## Tests
```
new: tests/test_engine_phase3b_gaps_mixin.py (10 runtime, location-agnostic locks)
targeted: phase0 + 3b hint/relations/rules + the rg-discovered gap/dedup/resolution/
          lifecycle/snapshot/state-identity tests -> 1400 passed
full suite: 2098 -> 2108 passed (+10 new; no existing test weakened or changed)
```

## Review severity self-triage (this PR's one in-PR finding)
- **NON-BLOCKING NIT / test-authoring fix (mine, found+fixed before review):** the
  new test first asserted `name not in Engine.__dict__` for the C4 methods. It
  passed alone but failed in the full suite, because another test
  (`test_complete_domain_neutral_reference_operation.py`, "Spy Engine.gap_resolution")
  uses the `orig = getattr(Engine, name); setattr(Engine, name, spy); ...;
  setattr(Engine, name, orig)` restore pattern, which **promotes the inherited
  GapsMixin method into `Engine.__dict__`** (the exact `__dict__`-promotion
  subtlety recorded in the Phase 3A introspection experiment). `Engine.__dict__`
  membership is therefore NOT a robust invariant. Fixed by asserting resolution to
  the mixin function (`__module__ == "ragcore._engine.gaps"` + `__qualname__ ==
  "GapsMixin.<name>"`) instead. This is a test-robustness fix, not a production
  issue — the extraction is AST 5/5 identical and every behavioural probe passes.
  (The earlier C8/C3/C7 mixin tests carry the same `not in __dict__` assertion and
  pass only because their methods are not spied by a setattr/restore test; they are
  already merged and out of scope for this PR.)

## Files changed / line delta
```
production/test: 3 files, +293/-128
  ragcore/_engine/gaps.py                          +151 (new)
  ragcore/engine.py                                +2/-128
  tests/test_engine_phase3b_gaps_mixin.py          +140 (new)
+ docs/dev/PR_089_…                                (this file)
NOT changed: ragcore/_engine/{hint_evidence,relations,rules,confidence,serialization}.py,
ragcore/_engine/__init__.py, ragcore/types.py, ragcore/__init__.py, snapshot
schema, examples/**, config/deps, C5 lifecycle, C9 confidence, Phase 3A docs.
```

## Commit chronology
```
437710a refactor(engine): extract C4 gaps mixin
9484c10 test(engine): lock inherited C4 runtime contracts
<this>  docs(dev): record Phase 3B-4 gaps mixin extraction
```
No commit amended, rebased, or squashed.

## STOP-AND-REPORT review
None triggered: AST 5/5 identical; no Engine wrapper; no public-signature /
`Engine.__module__` / public-count / `__all__` change; the four C4 stores and the
C2 read stores stay on Engine; no C1 seam moved; no C5/C9 change; severity-order /
dedup key / Gap.claim_id+severity first-registration / membership-guarded
`_gap_dedup_index` insert / conditional dedup-hit revision / first-evidence-wins /
single-revision multi-resolve all preserved; the three prior mixins unchanged;
`gaps.py` imports neither `ragcore.engine` nor another mixin; no import cycle; no
snapshot change; no existing test weakened; no source-location lock added.

## Lifecycle
OPEN — Draft. Recommendation on completion: **READY FOR GPT INDEPENDENT REVIEW**
(not self-merged). **Phase 3B-5 (C9 confidence adapters) remains prohibited** until
this PR passes independent review (APPROVE), squash merge, branch cleanup, and
post-merge `main` verification.
