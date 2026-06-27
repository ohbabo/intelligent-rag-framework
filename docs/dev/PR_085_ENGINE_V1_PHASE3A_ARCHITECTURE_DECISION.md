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
cross-cluster WRITE coupling: _claims only — operational mutation ownership,
  excluding the C10 bulk _install restore (C2 CRUD-add + C5 lifecycle status)
lock inventory: 0 fixed-file engine.py locks; binding = dir(Engine)==42 (runtime),
  getsource(Engine._seam)=real body, setattr(Engine, name, spy)
introspection deltas (4 prototypes): mixin changes __dict__/__qualname__/__module__/
  declaring-class/mro (asserted by NO test) but preserves getsource(seam)=real body;
  delegation/module-fn wrap the seam (getsource=wrapper) + add 1 traceback frame
module-fn state-port width: 14 stores + 11 infra methods called directly;
  transitive closure = all 19 stores + 12 private methods (≈ entire private surface)
full per-method evidence + recomputed derived values: docs/architecture/ENGINE_V1_PHASE3A_EVIDENCE.md
```

## Commit chronology
```
f49cedc docs(architecture): audit current Engine topology and compare decomposition candidates
        (ADR commit 1 — evidence + NEUTRAL 3-candidate comparison; no conclusion fixed)
a785d01 docs(architecture): select Phase 3 architecture (mixins) and define 3B entry gates
        (ADR commit 2 — selection AFTER comparison; consequences/3B/entry/adversarial record + plan addendum)
c3d0a95 docs(dev): record Phase 3A decision-gate history (this file, initial)
8ed8aaf docs(review): correct Phase 3A scope, store ownership, and 3B sequencing
        (GPT review round 1: v2 over-spec removed; mutator/owner matrix; C2/C5 split; wording)
a369b5b docs(review): add persistent evidence appendix, scope C1 in the no-expansion rule, fix chronology
        (GPT review round 2: BLOCKER 1 evidence file; BLOCKER 2 C1 boundary; BLOCKER 3 chronology/qualifier)
bc0f9b7 docs(review): correct evidence-table store-access classification
        (GPT review round 3: read false-positives removed; lifecycle/update_rule_stats A->W; _install next_id ID->W; direct port lists)
bd66e5c docs(review): fix two evidence-table cells (add_gap dedup insert, register_rule stats) + alias-read note
        (GPT review round 4: add_gap _gap_dedup_index W->A via membership-guard; register_rule _rule_stats A/W; alias-read scope option B)
<this>  docs(review): final audit synchronization (register_rule cell A/W; dev-record round 4/5 sync)
        (GPT review round 5: table cell A/W matches the note; chronology + corrections synced)
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

## GPT independent review corrections (round 2 — second review)
- **BLOCKER 1 — persistent audit evidence was missing.** The raw self-call graph
  and read/write matrix lived only in uncommitted `/tmp` scripts, so a reviewer
  could not re-verify "DAG", "C2↔C5 = 0", "C9→C5 edges", or the port width from
  the documents alone. Added `docs/architecture/ENGINE_V1_PHASE3A_EVIDENCE.md`: a
  sparse 63-method table (visibility, cluster, read stores, mutated stores + op,
  all self-call edges, cross-cluster callees, read-only/mutating) plus every
  derived value recomputed from it. Referenced from the ADR.
- **BLOCKER 2 — C1 boundary self-contradiction.** The no-expansion rule
  ("touch a `self._store` or shared-`self` seam ⇒ mixin") would have implied C1
  (which writes `_next_id`/`_state_revision` and owns the seams) must be a mixin,
  contradicting "C1 retained on Engine". Scoped the rule to *extracted* clusters
  ("except for the explicitly retained C1 core infrastructure, every extracted
  state-accessing cluster is a mixin"), and closed the 3B plan: **C1 remains on
  Engine; no optional CoreMixin extraction is authorized by this ADR** (moving C1
  later needs a separate change-control decision, not an ad-hoc "adds clarity").
- **BLOCKER 3 — chronology placeholder + missing qualifier.** Replaced the
  `<R1-R4>` placeholder with the real SHA `8ed8aaf389cfe9d9499dddcc1fc043366b4b65a3`,
  and made the "only store written by >1 cluster" claim consistently carry the
  qualifier "operational mutation ownership, excluding the C10 bulk `_install`
  restore". Also refined the port-width figure to "14 stores + 11 infra methods
  directly; transitive closure all 19 stores + 12 private methods" (the earlier
  bare "12" was the transitive count; the table now shows both).

## GPT independent review corrections (round 3 — third review)
- **BLOCKER 1 — evidence-table store-access classification was wrong.** The AST
  analyzer counted the write-container load of `self._store[k] = …` (and of
  `self._store.append(…)`) as a **read**, producing false `reads` (e.g.
  `add_entity reads entities`, `register_rule reads rule_stats`). It also marked
  every subscript-assign as `A`, so the lifecycle replace
  (`self._claims[id] = replace(self._claims[id], …)`) and `update_rule_stats`
  showed `A` instead of `W`, and `_install`'s whole rebind `self._next_id = …`
  showed `ID` instead of `W`. Rewrote the analyzer parent-aware:
  `R` = read of contents only; `W` = whole-rebind or subscript replace-existing
  (the method also subscript-reads the store); `A` = insert of a new key /
  append; `ID` = only `_allocate_id`'s counter; `I` = only the revision counter.
  Regenerated the 63-method table. The fix removed the false reads and corrected
  lifecycle/`update_rule_stats` → `W`, `_install` `next_id` → `W`.
- **BLOCKER 2 — direct port-width list was missing.** Added to the evidence the
  explicit **direct port stores (14)** and **direct infra methods (11)** lists,
  plus the **transitive-only additions** (5 stores + the one method
  `_storage_for_kind`, reached via `_id_exists`), and stated that "direct"
  excludes the C1/C6 infra and the C10 `_install`/`_state_view` boundary. The
  totals are unchanged (14+11 direct / 19+12 transitive) — the corrected reads
  were of stores already counted via their writes — but are now reproducible.
- **BLOCKER 3 — chronology placeholder + PR stale figure.** Replaced the
  dev-record `<this>` with the real round-2 SHA `a369b5b…`; corrected the one
  remaining `14+12` figure in the PR body's adversarial record to the
  direct/transitive form.

## GPT independent review corrections (round 4 — fourth review)
- **`add_gap` → `_gap_dedup_index`: `W` → `A`.** The subscript-assign runs only in
  the dedup miss branch after `if key in self._gap_dedup_index: … return`, so it
  is an insert. Added membership-guard detection to the analyzer: a subscript-
  assign guarded by `if <k> [not] in self._store:` with a returning/raising branch
  is `A`. (`register_rule`'s `_rule_definitions` is guarded the same way and stays
  `A`; the lifecycle / `update_rule_stats` replaces have no such guard and stay `W`.)
- **`register_rule` → `_rule_stats`: documented `A/W`** (insert for a fresh rule;
  replace if an orphan restored `_rule_stats` key exists per the restore contract).
- **Alias-read scope (option B).** Added a note that the `reads` column shows
  direct syntactic `self._store` access only; content reads via a local alias
  (`bucket = self._contradictions.setdefault(…); evidence_id in bucket`) are not
  separately listed — affects only the reads column, not ops / ownership / port /
  decision.

## GPT independent review corrections (round 5 — fifth review, final audit sync)
- **`register_rule` → `_rule_stats` table cell now reads `A/W`** (not `A` with a
  note). The authoritative sparse table records the real operation set the method
  can perform; the classification note no longer says "the table shows A". The
  contract-derived `W` is annotated via a documented override (it cannot be
  inferred from `register_rule`'s AST, whose guard is on `_rule_definitions`).
- **Dev-record synchronization.** The chronology now carries the real SHAs for
  round 3 (`bc0f9b7`) and round 4 (`bd66e5c`); the only `<this>` is this round-5
  bookkeeping commit. This corrections history is now complete through round 5,
  matching the PR body — the permanent audit record is no longer a step behind.

## Authoritative selected architecture
**Mixin composition for the state-accessing Engine method clusters,** with C1
core infrastructure on the `Engine` base and `confidence.py` + `serialization.py`
kept as module functions. Selected for **least delta** from the measured
shared-`self` topology and existing introspection surface, preserving the M07
seam-`getsource` lock. Delegation and module functions rejected with measured
reasons (conditional seam break + traceback frame; back-ref / 14-store+11-method
direct, 19+12 transitive port exposure). The no-expansion rule (scoped to
extracted clusters; C1 stays on Engine) + accepted introspection deltas + the 3B
sequence (C2 and C5 separate) are in the ADR.

## No-code-move proof
```
git diff --stat main..HEAD  -> only:
  docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md (new)
  docs/architecture/ENGINE_V1_PHASE3A_EVIDENCE.md              (new — persistent evidence appendix)
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
