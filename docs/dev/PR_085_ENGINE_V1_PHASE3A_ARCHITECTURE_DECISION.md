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
<this>  docs(dev): record Phase 3A decision-gate history (this file)
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

## Authoritative selected architecture
**Mixin composition** for the ten stateful clusters; `confidence.py` +
`serialization.py` stay module functions. Selected for **least delta** from the
measured shared-`self` topology and existing introspection surface, preserving
the M07 seam-`getsource` lock. Delegation and module functions rejected with
measured reasons (conditional seam break + traceback frame; back-ref / 14+12 port
exposure). The no-expansion rule + accepted introspection deltas + the 3B
sequence are in the ADR.

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
