# PR_091 — Engine v1 Phase 3B-6: Extract C6 Lifecycle History Mixin (development record)

GitHub PR **#92** (internal dev-record number = GitHub number − 1 = 091).

## Identity / purpose
Sixth production-code decomposition under the approved Phase 3A ADR. A
behaviour-preserving move of the two C6 lifecycle-history methods from the
`Engine` class body into a private `LifecycleHistoryMixin`. No change to the
lifecycle policy, event order, global lifecycle-seq increment, transition labels,
`ClaimLifecycleEvent` shape, snapshot/serialization, state-revision semantics,
signatures, or public API.

## Baseline
```
baseline main   1fedf50e6a46ac601ae148f40439ed7e0dba405b (Phase 3B-5 merged)
baseline tests  2123 passed (local; no GitHub Actions on this repo)
guard           HEAD == 1fedf50 verified; tracked working tree clean before start
```

## Exact methods moved (2)
```
_record_claim_lifecycle_transition   (private mutator: writes _lifecycle_seq + _claim_lifecycle_events)
claim_lifecycle_history              (public read-only; _assert_claim_exists guard)
public 1 / private 1 / mutators 1 (private) / total 2
```
**Not moved:** the two stores (`_lifecycle_seq`, `_claim_lifecycle_events` stay in
`Engine.__init__`); the C1 guard `_assert_claim_exists`; the C5 lifecycle methods;
`active_contradictions_by_freshness`; `_state_view` / `_install`; serialization /
snapshot integrity; `ClaimLifecycleEvent` (`ragcore.types`).

## C5 → C6 boundary (6 caller paths, preserved)
The six C5 lifecycle transitions keep calling `self._record_claim_lifecycle_transition(...)`
via the MRO (runtime self-resolution; no C6 import, no wrapper, no event creation
or seq increment in C5):
`confirm_if_ready` / `refute_if_ready` / `dispute_if_ready` /
`resolve_disputed_if_ready` / `refute_disputed_if_ready` /
`refute_disputed_by_freshness_if_ready`. Measured: `engine.py` contains exactly 6
`self._record_claim_lifecycle_transition(` call sites.

## Pre-existing "5 lifecycle API" docstring (historical wording, preserved)
`_record_claim_lifecycle_transition`'s docstring says "Called by 5 transition APIs"
/ "5 lifecycle API". The measured runtime/self-call fan-in is **6** after the
freshness-based refutation path (`refute_disputed_by_freshness_if_ready`) was
added. This extraction **preserves the method bodies, signatures, method-body AST,
and docstring text verbatim** (so `__doc__` is unchanged and the move is
AST-identical); the **function-object identity and declaring location
intentionally change** (`__module__` / `__qualname__` / declaring class — a new
`def` executes in the mixin module, producing a new function object). It does NOT
reinterpret the contract or update the count. The "5 lifecycle API" wording is a
pre-existing historical residue, recorded here, not introduced by this PR.

## Before → after ownership / accumulated MRO
`class Engine(HintEvidenceMixin, RelationsMixin, RulesMixin, GapsMixin, ConfidenceAdaptersMixin):`
→ append `LifecycleHistoryMixin`. All six mixins in `Engine.__mro__`; the two
methods resolve via the MRO (no forwarding wrapper). engine.py 948 → 905; the
emptied "Lifecycle history" subsection comment removed; Region F header trimmed to
"Freshness queries".

## Engine state did NOT move (proof)
`Engine.__init__` still owns `self._lifecycle_seq: int = 0` and
`self._claim_lifecycle_events: dict[int, list[ClaimLifecycleEvent]] = {}`; the
`ClaimLifecycleEvent` import is retained for that annotation. The mixin has no
`__init__`/state/back-reference; it writes the two stores and reads the C1 guard
through `self`. Snapshot still serialises `lifecycle_seq` + `claim_lifecycle_events`;
restore round-trips; 18 top-level keys.

## Import graph
```
ragcore.engine -> ragcore._engine.lifecycle_history            (added)
ragcore._engine.lifecycle_history imports: {__future__, ragcore.types}  (ClaimLifecycleEvent)
ragcore._engine.lifecycle_history -> ragcore.engine / other mixins : NONE  (no cycle, no inter-mixin coupling)
```

## AST equivalence
`ast.dump(..., include_attributes=False)` baseline `1fedf50:ragcore/engine.py`
(Engine) vs `ragcore/_engine/lifecycle_history.py` (LifecycleHistoryMixin):
**2/2 identical**; both methods absent from the current Engine class body.

## Accepted introspection deltas / preserved surface
the two methods → `__module__` `ragcore._engine.lifecycle_history`, `__qualname__`
`LifecycleHistoryMixin.*`, declaring class, inherited. Preserved:
`from ragcore import Engine`; `Engine.__module__ == "ragcore.engine"`; runtime
public **42**; `__all__` **50**; exact signatures; `getattr`/`setattr`/`monkeypatch`;
`getsource` real body; no extra traceback frame; the five prior mixins unchanged
and in the MRO.

## Exact signatures (unchanged)
```
_record_claim_lifecycle_transition(self, claim_id: int, from_status: int, to_status: int, transition: str) -> None
claim_lifecycle_history(self, claim_id: int) -> tuple[ClaimLifecycleEvent, ...]
```

## Ownership / no-promotion + patch-site scan
The new test locks, for both C6 methods: `name not in Engine.__dict__`,
`_defining_class(Engine, name) is LifecycleHistoryMixin`,
`getattr(Engine, name) is LifecycleHistoryMixin.__dict__[name]` (plus
`__module__`/`__qualname__`). A repository-wide scan
(`git grep` for `setattr(Engine` / `monkeypatch.setattr(Engine` against the two C6
names) found **NO existing test that patches a C6 method on Engine**, so no
patch-site migration was required (unlike C9). All C6 test references are plain
calls/assertions.

## Behavioural probes (all pass)
- C5 → C6 seam: a candidate + contradiction `refute_claim_if_ready` reaches the
  inherited recorder **exactly once** with `(claim_id, CANDIDATE→REFUTED,
  "refute_if_ready")`; the recorder is spied on its defining class, leaving
  `Engine.__dict__` unpolluted and the original restored.
- `claim_lifecycle_history` reflects the recorded event (tuple of
  `ClaimLifecycleEvent`, `seq >= 1`), is read-only (`state_identity()` + snapshot
  unchanged), and raises `KeyError` on an unknown claim with no state change.

## Tests
```
new: tests/test_engine_phase3b_lifecycle_history_mixin.py (10 runtime locks)
targeted: test_engine_lifecycle_history, test_engine_claim_lifecycle/refutation,
          disputed lifecycle/resolution/refutation, evidence_freshness,
          gap_severity_tiering, state identity, snapshot round-trip/migration/
          integrity, surface freeze, packet, 3B-1..3B-5 mixin tests
full suite: 2123 -> 2133 passed (+10 new; no existing test weakened or deleted)
```

## Files changed / line delta
```
production/test (stable): 3 files, +229/-46
  ragcore/_engine/lifecycle_history.py                   +68  (new)
  ragcore/engine.py                                      +3/-46
  tests/test_engine_phase3b_lifecycle_history_mixin.py   +158 (new)
+ docs/dev/PR_091_…                                      (this dev record; its own size
                                                          is self-referential — see the PR #92 diff)
Authoritative full-PR total (incl. this dev record): the GitHub PR #92 diff.
NOT changed: ragcore/_engine/{confidence,serialization,hint_evidence,relations,
rules,gaps,confidence_adapters}.py, ragcore/_engine/__init__.py, ragcore/types.py,
ragcore/__init__.py, snapshot schema, examples/**, config/deps, C5/C2 clusters,
Phase 3A docs.
```

## Commit chronology
Stable implementation/test chronology:
```
a5d251e refactor(engine): extract C6 lifecycle history mixin
5cb7d40 test(engine): lock C6 ownership and the C5->C6 self-call seam
```
The dev-record commit and any subsequent docs-only audit-sync commits are
docs-only; their authoritative SHAs and order are the GitHub PR #92 commit
history. This versioned record intentionally does not self-pin the SHA of commits
that modify the record itself. No commit amended, rebased, or squashed.

## STOP-AND-REPORT review
None triggered: base SHA 1fedf50; AST 2/2 identical; exactly 2 C6 methods; no
docstring/body/signature change; no Engine wrapper/super(); both methods absent
from Engine.__dict__; the two stores stay on Engine; no C5 transition body change;
transition label/order/seq semantics unchanged; no snapshot/serialization change;
public 42 / __all__ 50 / snapshot 2·18 / packet 7 unchanged; the five prior mixins
unchanged; no import cycle; no C6 direct-Engine patch site exists; no existing test
weakened; no source-location lock added.

## GPT review corrections (MERGE-TIME, no new full review round)
GPT independent review: **CHANGES REQUESTED — BLOCKER 0 / MERGE-TIME CORRECTION 2
/ NON-BLOCKING NIT 0**. Production extraction unchanged; both applied:
- **M1 — complete the structure/isolation tests to the level claimed.** (a) The
  MRO test only checked membership; it now locks the exact prefix
  `Engine.__mro__[1:7] == (HintEvidenceMixin, RelationsMixin, RulesMixin, GapsMixin,
  ConfidenceAdaptersMixin, LifecycleHistoryMixin)` (a prefix slice — append-
  compatible with later mixins, not a full-tuple / base-count lock). The two
  membership tests collapsed into this one, so the new-test count is 10 (full
  suite 2123 -> 2133). (b) The C5->C6 seam test now closes the patch with
  `monkeypatch.context()` and asserts, after the context, that the original
  function identity is restored on the defining class and the inherited method was
  never promoted onto `Engine` (`name not in Engine.__dict__`,
  `_defining_class(...) is LifecycleHistoryMixin`, `getattr(Engine, name) is
  original`, `LifecycleHistoryMixin.__dict__[name] is original`).
- **M2 — "original function object" wording corrected.** A new `def` in the mixin
  module produces a NEW function object (and this PR explicitly accepts the
  `__module__` / `__qualname__` / declaring-class deltas), so "preserves the
  original function object" was wrong. Corrected to "preserves the method bodies,
  signatures, method-body AST, and docstring text verbatim; the function-object
  identity and declaring location intentionally change" in the mixin module
  docstring, this dev record, and the PR body. The Exact-signatures lines now
  include the parameter type annotations (the test signatures were already
  authoritative).

## Lifecycle
OPEN — Draft. Recommendation on completion: **READY FOR GPT INDEPENDENT REVIEW**
(not self-merged). **Phase 3B-7 (C2 CRUD) remains prohibited** until this PR passes
independent review (APPROVE), all corrections committed, squash merge, branch
cleanup, and post-merge `main` verification.
