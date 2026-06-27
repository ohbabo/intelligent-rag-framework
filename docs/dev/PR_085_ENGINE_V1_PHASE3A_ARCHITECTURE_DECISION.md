# PR_085 — Engine v1 Phase 3A: Architecture Decision Gate (development record)

GitHub PR **#86** (internal dev-record number = GitHub number − 1 = 085, per the
repository convention confirmed before naming: the internal `PR_<NNN>` sequence
tops out at PR_078 ↔ GitHub #79, and Phase 3A landed as #86 → PR_085).

## Identity / purpose
Phase 3A of the Engine v1 refactoring plan: a **documentation-only decision gate**
that selects one internal Engine architecture (mixins / delegation / module
functions) from measured evidence, and defines the Phase 3B entry gate. No
production code, test, or public API change. ADR:
`docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md`.

## Baseline
```
main SHA   6f4f8e06c352d96199b8335fa84ce33c99475743 (Phase 2 / PR #85 merged)
pytest     2070 passed (local; no GitHub Actions on this repo)
```
SHA guard: verified actual == expected before starting (STOP-AND-REPORT armed for
mismatch; matched).

Naming STOP-AND-REPORT: the directive proposed `PR_085`; the internal sequence
was at PR_078 and #079–#084 were never created (the refactoring PRs #82–#85 used
`docs/architecture/` + the reconstruction index). The naming was surfaced to the
user rather than invented; resolution = create the Draft PR first, then name the
dev record `PR_<GitHub#−1>`. PR is #86 → PR_085.

## Investigation commands (re-measured, not from history)
```
# topology + baseline
ast.parse(engine.py): Engine class span, direct method defs, runtime dir(Engine)
to_snapshot() key order/count; engine_inspector.build_engine_context_packet() keys
__init__ AnnAssign scan -> 19 state fields; _state_view/_install confirm 17 persisted
# self-call graph + SCC (Tarjan) + store R/W matrix (AST classify R/W/A/D/M)
/tmp/p3a/analyze.py  -> /tmp/p3a/graph.json, graph_summary.txt
# cluster + coupling + module-fn port width
/tmp/p3a/cluster_coupling.txt
# lock inventory (tests/ + docs/ pattern scan)
/tmp/p3a/lock_inventory.txt
# introspection-delta experiment (4 faithful prototypes in /tmp, NOT committed)
/tmp/p3a/exp/measure.py -> /tmp/p3a/introspection_deltas.txt
```
All analysis scripts and prototypes were kept under `/tmp` and are **not**
committed (verified by the docs-only diff below).

## Measurement results (key)
```
engine.py 1596 lines; Engine class 1461 lines; 42 public / 21 private runtime methods
__all__ 50; snapshot schema 2 / 18 keys; packet 7 keys
self-call graph: DAG, 0 non-trivial SCCs
single revision authority _advance_state_revision (20 callers); single ID authority _allocate_id (6)
cross-cluster WRITE coupling: _claims only (C2 CRUD-add + C5 lifecycle status)
lock inventory: 0 fixed-file engine.py locks; binding = dir(Engine)==42 (runtime),
  getsource(Engine._seam)=real body, setattr(Engine, name, spy)
introspection deltas (4 prototypes): mixin changes __dict__/__qualname__/__module__/
  declaring-class/mro (asserted by NO test) but preserves getsource(seam)=real body;
  delegation/module-fn wrap the seam (getsource=wrapper) + add 1 traceback frame
module-fn state-port width: 14 stores + 12 private methods (≈ entire private surface)
```

## Commit chronology
```
f49cedc docs(architecture): audit current Engine topology and compare decomposition candidates
        (ADR commit 1 — evidence + NEUTRAL 3-candidate comparison; no conclusion fixed)
a785d01 docs(architecture): select Phase 3 architecture (mixins) and define 3B entry gates
        (ADR commit 2 — selection AFTER comparison; consequences/3B/entry/adversarial record + plan addendum)
c3d0a95 docs(dev): record Phase 3A decision-gate history (this file, initial)
<R1-R4> docs(review): correct Phase 3A scope, store ownership, and 3B sequencing
        (GPT review round 1: v2 over-spec removed; mutator/owner matrix; C2/C5 split; wording)
```
No commit was amended, rebased, or squashed.

## Draft review findings / corrections (this PR)
- An adversarial review **panel** (multi-agent) was started, then **stopped at the
  user's request** because it produced repeated approval prompts. The adversarial
  review was performed **inline** instead and recorded in the ADR
  (§"Adversarial review record").
- **Methodology correction (premature-mixin-bias risk):** an earlier draft placed
  the no-expansion rule ("touch a `self._store` ⇒ mixin") inside the decision,
  where it could read as a *premise* that pre-eliminates delegation/module-fn.
  Corrected: the ADR now runs measurement → neutral gate comparison → selection →
  the rule as a *consequence*.
- **Measurement slip recorded:** the cluster-assignment script left
  `evidences_for_claim` unassigned (read-only claim→evidence query; no coupling
  impact). Recorded, not hidden.

## GPT independent review corrections (round 1 — this PR's first review)
- **R1 — v2 seam over-specified.** The ADR/PR/dev record claimed the existing
  `_state_view() → DecodedEngineState` is the future v2 read-only projection seam.
  Removed: the v2 section now states only that the v1 decomposition must not
  *structurally prevent* a future derived layer; the concrete v2 projection,
  identity, and materialization boundaries are **deferred to a separate v2 design
  phase** and not designed here. `_state_view()` is described only as the current
  internal snapshot-encoding carrier.
- **R2 — method mutator count confused with write-cluster ownership.** The store
  matrix was regenerated with **two separate columns** (mutating methods | owning
  write-cluster). The earlier write-detection also missed `difference_update`, so
  `unregister_hint_evidence_types` was wrongly read-only — corrected. Result:
  `_claims` is the **only** store written by more than one cluster (C2+C5); all
  others have one owning cluster, though `_rule_stats` (2) and
  `_hint_evidence_types` (3) have multiple mutating methods *within* their one
  cluster. Removed: "per-kind 1-mutator" / "every other store exactly one mutator".
- **R3 — C2+C5 combined 3B PR lacked a non-isolability proof.** Split into
  separate steps (3B-7 C2, 3B-8 C5). Evidence: no C2↔C5 direct call (measured
  cross-cluster edges are only C5→C4, C5→C6, C9→C5), so an independent move
  creates no cycle / no broken seam / no unrunnable intermediate `main`. The
  shared `_claims` write is recorded as coupling needing regression verification,
  not a forced combined PR; recombine only on measured non-isolability.
- **R4 — "ten stateful clusters" was inaccurate.** C1 stays on the Engine base,
  C9 is read-only, and the pure kernels are module functions. Wording corrected
  to "mixin composition for the state-accessing Engine method clusters, with C1
  on Engine and confidence/serialization kept as module functions."

## Authoritative selected architecture
**Mixin composition for the state-accessing Engine method clusters,** with C1
core infrastructure on the `Engine` base and `confidence.py` + `serialization.py`
kept as module functions. Selected for **least delta** from the measured
shared-`self` topology and existing introspection surface, preserving the M07
seam-`getsource` lock. Delegation and module functions rejected with measured
reasons (conditional seam break + traceback frame; back-ref / 14+12 port
exposure). The no-expansion rule + accepted introspection deltas + the 3B
sequence (C2 and C5 separate) are in the ADR.

## No-code-move proof
```
git diff --stat main..HEAD  -> only:
  docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md (new)
  docs/architecture/ENGINE_V1_REFACTORING_PLAN.md              (append-only addendum)
  docs/dev/PR_085_ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md   (new)
ragcore/** tests/** examples/** pyproject/config: 0 changed
```
No Engine method, store, import, or class hierarchy was moved in Phase 3A.

## Verification
```
git diff --check    clean
pytest -q           2070 passed (unchanged from baseline; docs-only)
public 42 / __all__ 50 / snapshot 2·18 / packet 7 / policy id / no cycle: unchanged
```
There are no GitHub Actions on this repo; `2070 passed` is a **local** result.
`ragcore.egg-info/` was not staged or committed.

## Lifecycle
OPEN — Draft. Recommendation on completion: **READY FOR GPT INDEPENDENT REVIEW**
(not self-merged). Phase 3B implementation remains prohibited until the Phase 3A
entry conditions are independently reviewed, approved, merged, and post-merge
verified.
