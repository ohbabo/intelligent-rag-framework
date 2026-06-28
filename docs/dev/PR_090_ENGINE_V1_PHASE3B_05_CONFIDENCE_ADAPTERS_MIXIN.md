# PR_090 — Engine v1 Phase 3B-5: Extract C9 Confidence Adapters Mixin (development record)

GitHub PR **#91** (internal dev-record number = GitHub number − 1 = 090).

## Identity / purpose
Fifth production-code decomposition under the approved Phase 3A ADR. A
behaviour-preserving move of the ten C9 effective-confidence **adapter** methods
from the `Engine` class body into a private `ConfidenceAdaptersMixin`. No change
to the modifier arithmetic, policy, calculation order, signatures, snapshot, or
public API. The pure arithmetic kernel `ragcore/_engine/confidence.py` is
byte-for-byte unchanged.

## Baseline
```
baseline main   69a88388225c618874051ab482973fa2b8bcde8d (Phase 3B-4 merged)
baseline tests  2108 passed (local; no GitHub Actions on this repo)
guard           HEAD == 69a8838 verified; tracked working tree clean before start
```

## Why C9 fifth
Read-only adapter cluster (zero mutators). Per the ADR 3B order
(C8 → C3 → C7 → C4 → **C9** → C6 → C2 → C5 → C10) it is scheduled after the
lower-coupling C8/C3/C7/C4 clusters and before C6/C2/C5 (C2 is itself a CRUD
cluster and comes after C9, so "after the CRUD clusters" would be inaccurate). It
is the cluster whose seam (the M07
`getsource(Engine._compute_effective_confidence_core)` real-body lock) most needs
care, and whose existing tests directly patch the moved methods on `Engine`.

## Exact methods moved (10, physical order)
```
evidence_freshness                          (public, read-only)
_status_modifier_for_claim                  (private)
_freshness_modifier_for_claim               (private; -> self.active_contradictions_by_freshness)
_gap_modifier_for_claim                     (private)
_count_modifier_for_claim                   (private; -> self.active_contradictions_for_claim)
_rule_stats_modifier_for_claim              (private)
_evidence_type_modifier_for_claim           (private)
compute_effective_confidence                (public; -> trace.effective_confidence)
_compute_effective_confidence_core          (private; the single composition site)
compute_effective_confidence_with_trace     (public; -> full trace)
public 3 / private 7 / total 10 / mutators 0
```

## Pure-kernel / adapters ownership boundary
`ragcore/_engine/confidence.py` is the **pure arithmetic kernel** (policy
constants, the six modifier functions, the single composer, claim-status
admission) — NOT modified (verified byte-identical to baseline).
`ragcore/_engine/confidence_adapters.py` is the **adapter layer**: it collects
input facts from the Engine stores and delegates numeric composition to the
kernel. C9 is read-only but NOT coupling-free.

## Not moved
- the kernel `confidence.py` (unchanged);
- every Engine store the adapters read (`_claims` / `_evidences` /
  `_claim_gap_refs` / `_gap_resolutions` / `_rule_stats` / `_contradictions` /
  `_resolved_contradictions` / `_hint_evidence_types`) — read-only;
- the C1 seams `_assert_claim_exists` / `_assert_evidence_exists` /
  `state_identity`;
- the C5 queries `active_contradictions_for_claim` /
  `active_contradictions_by_freshness` (C9 reaches them via `self`, MRO, no C5
  import);
- `from_snapshot` and its `confidence._validate_claim_status_admission(...)` call
  (so the `confidence` import is retained in engine.py); snapshot/install; CRUD;
  gaps; lifecycle; `types.py`; `__all__`; snapshot schema; PR51 packet.

## Before → after ownership / accumulated MRO
`class Engine(HintEvidenceMixin, RelationsMixin, RulesMixin, GapsMixin):` →
`class Engine(HintEvidenceMixin, RelationsMixin, RulesMixin, GapsMixin, ConfidenceAdaptersMixin):`
(new mixin appended, existing prefix preserved). All five mixins in
`Engine.__mro__`; the ten methods resolve via the MRO (no forwarding wrapper).
engine.py 1219 → 948. Bookkeeping: the now-empty Region I + Region J removed;
`evidence_freshness` removed from its Region-F subsection; the unused
`EffectiveConfidenceTrace` import removed from engine.py.

## AST equivalence
`ast.dump(..., include_attributes=False)` baseline `69a8838:ragcore/engine.py`
(Engine) vs `ragcore/_engine/confidence_adapters.py` (ConfidenceAdaptersMixin):
**10/10 identical**; all ten methods absent from the current Engine class body.

## M07 getsource preservation (the load-bearing seam)
`inspect.getsource(Engine._compute_effective_confidence_core)` returns the real
ConfidenceAdaptersMixin body — contains `compose_effective_confidence`,
`ScoreValue`, `state_identity`, the six modifier calls; no `super()`, no
delegate, no second multiplication formula. The stronger M07 AST tests in
`test_effective_confidence_trace.py` continue to pass unchanged.

## Existing M07 test-isolation correction (in this PR, by design)
After the extraction the six modifier helpers and the core are inherited. Three
M07 spy sites in `test_effective_confidence_trace.py` patched them on `Engine`
and restored via `setattr(Engine, name, original)` — which **promotes the
inherited method into `Engine.__dict__`** on restore. All three migrated to patch
each method on its **defining class** (a new `_defining_class(Engine, name)`
helper) and restore from that class's own `__dict__`, leaving `Engine.__dict__`
unpolluted:
- `TestModifierHelperCallCount._wrap_helpers` / `_restore_helpers`;
- `TestSingleMultiplicationSite.test_core_invokes_each_wrapper_once_and_composer_once`;
- `TestSingleMultiplicationSite.test_both_public_apis_delegate_to_the_core`.
Assertion meanings and call-count expectations are unchanged; no test
weakened/deleted; only the C9 patch sites were touched (no broad cleanup of other
clusters). Verified: after a defining-class spy/restore, the C9 methods are not in
`Engine.__dict__` and `ConfidenceAdaptersMixin`'s originals are restored.

## Accepted introspection deltas / preserved surface
the ten methods → `__module__` `ragcore._engine.confidence_adapters`,
`__qualname__` `ConfidenceAdaptersMixin.*`, declaring class
`ConfidenceAdaptersMixin`, inherited. Preserved: `from ragcore import Engine`;
`Engine.__module__ == "ragcore.engine"`; runtime public **42**; `__all__` **50**;
exact signatures; `getattr`/`setattr`/`monkeypatch`; `getsource` real body; no
extra traceback frame; the four prior mixins unchanged and in the MRO.

## Exact signatures (unchanged)
```
evidence_freshness(self, evidence_id: int) -> int
the six _*_modifier_for_claim(self, claim_id: int) -> float
compute_effective_confidence(self, claim_id: int) -> ScoreValue
_compute_effective_confidence_core(self, claim_id: int) -> EffectiveConfidenceTrace
compute_effective_confidence_with_trace(self, claim_id: int) -> EffectiveConfidenceTrace
```

## Behavioural probes (all pass)
- `confidence.py` byte-identical to baseline; the core uses
  `confidence.compose_effective_confidence` exactly once; policy id
  `ragcore.effective-confidence.v1` unchanged.
- C9 → C5 runtime self-resolution: `_count_modifier_for_claim` reaches
  `active_contradictions_for_claim` ×1; `_freshness_modifier_for_claim` reaches
  `active_contradictions_by_freshness` ×1.
- read-only: `evidence_freshness` / `compute_effective_confidence` /
  `compute_effective_confidence_with_trace` leave `state_identity()` and the
  snapshot unchanged.
- the two public APIs agree: `compute_effective_confidence(c) ==
  compute_effective_confidence_with_trace(c).effective_confidence`;
  `evidence_freshness(ev) == ev`, unknown → KeyError.

## Tests
```
new: tests/test_engine_phase3b_confidence_adapters_mixin.py (15 runtime locks,
     incl. test_c9_methods_owned_by_mixin_without_engine_promotion)
migrated (C9 spy sites -> defining-class):
  tests/test_effective_confidence_trace.py                  3 M07 spy sites (+24/-8)
  tests/test_complete_domain_neutral_reference_operation.py 1 M08 C9 spy site (+12/-6)
targeted: M07 trace (89), confidence kernel, count-averaging, evidence-type strict,
          gap tiering, rule-stats continuous/observed-precision, surface freeze,
          state identity, snapshot, packet, 3B-1..3B-4 mixin tests; M08 (199)
full suite: 2108 -> 2123 passed (+15 new; no existing test weakened or deleted)
```

## Files changed / line delta
```
production/test: 5 files, +517/-287
  ragcore/_engine/confidence_adapters.py                    +280 (new)
  ragcore/engine.py                                         +2/-273
  tests/test_effective_confidence_trace.py                  +24/-8  (M07 isolation migration)
  tests/test_complete_domain_neutral_reference_operation.py +12/-6  (M1: 4th C9 spy site -> defining-class)
  tests/test_engine_phase3b_confidence_adapters_mixin.py    +199 (new)
+ docs/dev/PR_090_…                                         (this dev record; its own
                                                            size is self-referential —
                                                            see the PR #91 diff)
cumulative production + test (stable): 5 files, +517/-287.
Authoritative full-PR total (incl. this dev record): the GitHub PR #91 diff.
NOT changed: ragcore/_engine/{confidence,serialization,hint_evidence,relations,
rules,gaps}.py, ragcore/_engine/__init__.py, ragcore/types.py, ragcore/__init__.py,
snapshot schema, examples/**, config/deps, C5/C6 clusters, Phase 3A docs.
```

## Commit chronology
```
b8919a3 refactor(engine): extract C9 confidence adapters mixin
a9dd5d3 test(engine): lock inherited C9 contracts and isolate defining-class patches
dfe4964 docs(dev): record Phase 3B-5 confidence adapters extraction
1b1120e test(engine): lock C9 ownership/no-promotion + migrate a 4th C9 patch site
<this>  docs(dev): sync Phase 3B-5 dev-record audit numbers + chronology (M3)
```
No commit amended, rebased, or squashed.

## STOP-AND-REPORT review
None triggered: AST 10/10 identical; no Engine wrapper; no public-signature /
`Engine.__module__` / public-count / `__all__` change; no store/__init__ move; no
C5 change; `confidence.py` unchanged; numeric/policy/order/policy-id unchanged;
snapshot schema/keys/bytes unchanged; the four prior mixins unchanged;
`confidence_adapters.py` imports neither `ragcore.engine` nor another mixin; no
import cycle; the M07 getsource seam preserved; no existing test weakened; no C9
direct-Engine patch remains — all four C9 patch sites were migrated to
defining-class (3 in test_effective_confidence_trace.py + 1 in
test_complete_domain_neutral_reference_operation.py); no source-location lock added.

## GPT review corrections (MERGE-TIME, no new full review round)
GPT independent review: **CHANGES REQUESTED — BLOCKER 0 / MERGE-TIME CORRECTION 2
/ NON-BLOCKING NIT 0**. Production extraction unchanged; both corrections applied:
- **M1 — lock the ownership / no-promotion result.** The original
  `test_c9_methods_resolve_to_mixin` only checked `__module__` / `__qualname__`,
  which do not change if the same function object is rebound onto `Engine`. Added
  `test_c9_methods_owned_by_mixin_without_engine_promotion` asserting, for all ten
  C9 methods: `name not in Engine.__dict__`,
  `_defining_class(Engine, name) is ConfidenceAdaptersMixin`, and
  `getattr(Engine, name) is ConfidenceAdaptersMixin.__dict__[name]`. **This
  surfaced a fourth C9 patch site the review had not enumerated:**
  `tests/test_complete_domain_neutral_reference_operation.py::_install_spies`
  patched `Engine.compute_effective_confidence_with_trace` at the class level and
  restored it on `Engine`, promoting the inherited method into `Engine.__dict__`,
  which made the new ownership test fail in the full suite. Migrated that site to
  patch the method on its **runtime-resolved defining class** (no hardcoded mixin
  name) so the spy + restore stay in that class's `__dict__`. With all four C9
  patch sites (3 in test_effective_confidence_trace.py + this one) on the defining
  class, the ownership test now passes in the full suite (2123), and it serves as
  the global post-patch no-promotion regression lock (it runs after the M07 and
  M08 patch tests, so it also verifies they leave no C9 method promoted).
- **M2 — wording.** "scheduled after the CRUD/store-owning clusters" was
  inaccurate (C2 is a CRUD cluster and comes *after* C9). Corrected to "after the
  lower-coupling C8/C3/C7/C4 clusters and before C6/C2/C5", with the explicit ADR
  order.

## Lifecycle
OPEN — Draft. Recommendation on completion: **READY FOR GPT INDEPENDENT REVIEW**
(not self-merged). **Phase 3B-6 (C6 lifecycle history) remains prohibited** until
this PR passes independent review (APPROVE), all corrections committed, squash
merge, branch cleanup, and post-merge `main` verification.
