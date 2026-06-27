# Engine v1 — Phase 3A Architecture Decision Record

## Status
**DRAFT — decision gate. Documentation only. No production code, test, or public
API change.** Phase 3B implementation remains prohibited until all Phase 3A entry
conditions (§ Phase 3B entry conditions) are independently reviewed, approved,
merged, and post-merge verified.

This record is written in two commits by intent: the first records *measured
evidence and a neutral three-candidate comparison* (no conclusion fixed); the
second records the *selection, rejections, consequences, and 3B plan*. The
no-expansion rule that appears in "Consequences" is a **result of the
selection**, never a premise of it.

## Context
Phases 0–2 (PRs #83/#84/#85, merged) migrated the engine's test taxonomy off
implementation-location locks, extracted the snapshot serialization
(`ragcore/_engine/serialization.py`) and the fixed-v1 effective-confidence kernel
(`ragcore/_engine/confidence.py`) as pure module functions, and reduced
`engine.py` to 1596 lines. The `Engine` class remains a single ~1461-line body.
Phase 3 finalizes the internal decomposition so a future v2 (a physics/derived
layer) can extend it without disturbing the public surface or the integration
boundary. Phase 3A (this record) selects **one** internal architecture —
**mixins**, **delegation**, or **module functions behind a thin façade** — by
measuring the current engine and comparing the three against mandatory gates.

The historical `docs/architecture/ENGINE_INTERNAL_MAP.md` is a **1145-test-era
input**, not current authoritative topology and not an automatic architecture
selection. Every number below was re-measured on the current main.

## Starting baseline (re-measured, not from history)
```
main SHA                         6f4f8e06c352d96199b8335fa84ce33c99475743
pytest                           2070 passed (local; no GitHub Actions on this repo)
engine.py physical lines         1596
Engine class span                lines 136–1596 (1461 lines)
Engine direct method defs        64  (42 public + 22 private incl __init__)
runtime public methods           42  (dir(Engine), location-agnostic)
runtime private own-dict methods 21
ragcore.__all__                  50
snapshot schema_version          2
snapshot top-level keys          18 (order locked, unchanged)
PR51 packet keys                 7  (examples/inspector/engine_inspector.build_engine_context_packet — NOT an Engine method)
state-identity                   _state_identity_token (uuid hex) + _state_revision; fresh lineage on Engine() and from_snapshot()
ragcore/_engine modules          __init__.py, confidence.py, serialization.py
import graph (ragcore.*)         engine -> {_engine, _engine.serialization, types}; serialization -> {types}; confidence -> {types}; types -> {}
```
Historical figures deliberately NOT reused: "engine.py 1800", "40 public / 21
private", "1145 tests". Superseded by the table above.

## Current measured topology

### State inventory (19 instance fields)
17 persisted (in snapshot / `_state_view` / `_install`):
`_next_id`, `_lifecycle_seq`, `_entities`, `_observations`, `_claims`,
`_evidences`, `_relations`, `_gaps`, `_rule_definitions`, `_rule_stats`,
`_gap_dedup_index`, `_claim_gap_refs`, `_gap_resolutions`, `_contradictions`,
`_resolved_contradictions`, `_claim_lifecycle_events`, `_hint_evidence_types`.
2 runtime-only (NOT persisted; fresh on construct/restore):
`_state_identity_token`, `_state_revision`.
Each persisted store is a **per-kind** dict/set. The directive forbids collapsing
them into one generic state object; this record honors that.

### Self-call graph (AST, manually verified)
- **0 non-trivial strongly-connected components** — the self-call graph is a
  **DAG**. There is no mutual recursion to untangle; clusters can be moved.
- Single shared authorities (high fan-in):
  - `_advance_state_revision` — **20 callers**, the *only* writer of
    `_state_revision` (single revision authority).
  - `_allocate_id` — **6 callers**, the *only* writer of `_next_id` (single ID
    authority).
  - `_assert_claim_exists` (18), `_record_claim_lifecycle_transition` (6, the
    only writer of `_lifecycle_seq` + `_claim_lifecycle_events`),
    `_assert_evidence_exists` (4), and the other `_assert_*_exists` guards.
- Highest fan-out: `_compute_effective_confidence_core` (8 → six modifier seams +
  guard + `state_identity`); the lifecycle mutators (4–5 each).

### Store read/write matrix (AST) — cross-cluster write coupling
Per-store true mutators (excluding `_install`, which is the bulk-restore
boundary):

| store | mutators |
|---|---|
| `_claims` | add_claim **and** confirm/dispute/refute(×3)/resolve lifecycle (7) |
| every other persisted store | exactly **one** mutator (its CRUD/register method) |
| `_state_revision` | `_advance_state_revision` only |
| `_next_id` | `_allocate_id` only |
| `_state_identity_token` | none (set once in `__init__`) |

**Cross-cluster WRITE coupling is `_claims` and only `_claims`** (creation vs.
status-transition). Every other store has a single owning cluster.

### Cluster proposal (from the call graph + store ownership, not comments)
| cluster | methods (abbrev.) | owns (writes) | non-infra cross-cluster calls |
|---|---|---|---|
| C1 core/identity/id/guards | `_advance_state_revision`, `_allocate_id`, `_assert_*_exists`, `_id_exists`, `_storage_for_kind`, `state_identity` | `_state_revision`, `_next_id` | — (everyone calls *into* C1) |
| C2 entity/obs/claim/evidence CRUD | add_/get_ entity·observation·claim·evidence, evidences_for_claim | `_entities`,`_observations`,`_claims`(add),`_evidences` | — |
| C3 relations | add_relation, get_relation | `_relations` | — |
| C4 gaps + resolution | add_gap, get_gap, gaps_for_claim, gap_resolution, resolve_gaps_for_evidence | `_gaps`,`_gap_dedup_index`,`_claim_gap_refs`,`_gap_resolutions` | — |
| C5 lifecycle + contradiction | confirm/dispute/refute/resolve_*_if_ready, register_contradiction(_resolution), *contradictions_* queries | `_claims`(status),`_contradictions`,`_resolved_contradictions` | → C4 (2), → C6 (6) |
| C6 lifecycle history | `_record_claim_lifecycle_transition`, claim_lifecycle_history | `_lifecycle_seq`,`_claim_lifecycle_events` | — |
| C7 rules + RuleStats | register_rule, get_rule, get_rule_stats, update_rule_stats | `_rule_definitions`,`_rule_stats` | — |
| C8 hint evidence | register/unregister/clear_hint_evidence_types, `_validate_hint_evidence_type_values` | `_hint_evidence_types` | — |
| C9 effective-confidence adapters | compute_effective_confidence(_with_trace), `_compute_effective_confidence_core`, six `_*_modifier_for_claim`, evidence_freshness | — (read-only) | → C5 (2) |
| C10 snapshot façade | to_snapshot, from_snapshot, `_state_view`, `_install` | (bulk via `_install`) | — |

Honest non-independence (measured, not glossed): the clusters are **not** ten
independent islands. They share C1 (every mutator calls into it) and C6 (the
lifecycle recorder), and **C2/C5 co-own `_claims`**. C9 reads C5; C5 reads C4.
All other coupling is *into* shared infrastructure. Because the graph is a DAG,
this is an ordering constraint for 3B, not a blocker.

## Existing test / introspection assumptions (§4 lock inventory)
Repository-wide scan of `tests/` and `docs/`:

| pattern | tests hits | meaning |
|---|---|---|
| `open("engine.py")` / `Path(...engine.py)` | **0** | Phase 0–2 already removed fixed-file Engine-source locks |
| `vars(Engine)` / `__mro__` / `__bases__` / `getattr_static` | **0** | not asserted |
| `Engine.__dict__` / `__qualname__` / declaring-class assertions in tests | **0** | only discussed in the plan doc, not asserted by a test |
| `dir(Engine)` public count `== 42` | several | **runtime** count — location-agnostic, survives all candidates |
| `inspect.getsource(Engine._compute_effective_confidence_core)` | M07 | runtime-resolved; asserts the seam **body**: one `ScoreValue` around one composer delegation, leaf order, no Mult |
| `setattr(Engine, name, spy)` / `monkeypatch.setattr(Engine, …)` | public methods + the six `_*_modifier_for_claim` seams | call-count / gate tests |
| `inspect.getsource(ragcore.engine)` (module) | adapter-sim | forbidden-import string scan of `engine.py` source (passes in all candidates; Phase 0 has a package-wide AST filesystem scan over `ragcore/engine.py` + `ragcore/_engine/**` that covers any new module) |
| AST `ClassDef` / class-body scans | several | all parse **example** sources (engine_inspector / scaffold / domain-neutral), **not** `engine.py` |

Classification: there is **no** surviving implementation-location lock on
`engine.py`. The binding constraints are (a) `dir(Engine)` public count, (b)
`inspect.getsource` of the **named private seams** returning their real body, and
(c) `setattr(Engine, name, …)` resolving/setting those names. All three are
runtime-resolved, so the question is purely how each candidate affects runtime
attribute resolution and `getsource` of a *runtime-resolved* method.

## Candidate architectures (analyzed equally)

### Candidate A — Mixins
`class Engine(CoreMixin, CrudMixin, GapMixin, LifecycleMixin, RuleMixin, …)` with
mixin bodies in `ragcore/_engine/*.py`; `__init__` and the per-kind stores stay
on `Engine`. Mixin methods use `self._<store>` and `self._advance_state_revision()`
exactly as today (no imports between mixins; they share `self`).

### Candidate B — Delegation
`Engine.__init__` constructs per-domain operation objects
(`self._crud = CrudOps(self)`, …). Public methods become façade wrappers
(`def add_entity(...): return self._crud.add_entity(...)`). Each delegate needs a
back-reference to the engine to reach `self._<store>`, `_advance_state_revision`,
`_allocate_id`, the guards, and sibling queries.

### Candidate C — Module functions behind a thin façade
`def add_gap(state, …): …` in `ragcore/_engine/*.py`; `Engine` methods become
wrappers that pass a `state` port (`return crud_fns.add_gap(self, …)`). The
`state` port must expose every private member the functions touch.

> A single generic state object is explicitly **excluded** as a solution for B
> and C (directive); per-kind stores are retained in all three.

## Mandatory gate result (neutral, applied to all three)
G1 import path/`__module__`, G2 42 names/signatures, G3 semantics, G5
snapshot/identity boundary, G8 fixed confidence policy, G10 v2 boundary, G12
rollback granularity — **PASS for all three** (G1–G3 confirmed by the
introspection experiment below; G5/G8/G10 are unaffected by internal
decomposition).

The **discriminating** gates:

| gate | Candidate A mixin | Candidate B delegation | Candidate C module-fn |
|---|---|---|---|
| **G4** named private seams preserved (`Engine._seam` resolvable **and** `getsource` returns the seam's real body for the M07-pinned `_compute_effective_confidence_core`) | **PASS** — inherited; `getsource` follows the function to the mixin module → real body (measured) | **CONDITIONAL** — if the confidence cluster is delegated, `getsource(Engine._compute_effective_confidence_core)` returns the **wrapper**, not the body (measured) → M07 body assertions fail; passes only if this seam is kept on `Engine` (an exception to the pattern) | **CONDITIONAL** — identical to B |
| **G6** no runtime import cycle | PASS (mixins use `self`, import `types`+kernels only) | PASS (TYPE_CHECKING-only Engine import) | PASS (TYPE_CHECKING-only port import) |
| **G7** per-kind stores, no generic store | PASS (stores on `self`, accessed directly) | PASS on letter — but each delegate's back-ref exposes the **whole** store set | PASS on letter — but the `state` port must expose **14 stores + 12 private methods** (measured; ≈ entire private surface) |
| **G9** 3B as independent cluster PRs | PASS — one mixin per cluster; shared C1 extracted/retained as base | CONDITIONAL — shared infra (12 methods) must be resolved into the port/base first; heavier first PR | CONDITIONAL — same |
| **G11** don't revert tests to location locks | PASS — no test change needed | CONDITIONAL — delegating the seam forces an M07 change/re-pin | CONDITIONAL — same |

No candidate fails a *hard* gate outright. A and (B,C) differ on whether G4/G9/G11
pass **cleanly** (A) or only **conditionally, at a cost** (B, C).

## Introspection-delta experiment (measured, 4 prototypes)
Four faithful minimal prototypes (`/tmp`, not committed): a monolithic baseline
and one per candidate, each with a representative **public** method (`add_entity`,
`get_entity`) and a **named private seam** (`_core`, modeling
`_compute_effective_confidence_core`; plus `_advance_state_revision`,
`_allocate_id`). Measured:

| property | MONO | MIXIN | DELEGATION | MODULE-FN |
|---|---|---|---|---|
| `Engine.__module__` | engine | engine | engine | engine |
| public `dir()` count | = | = | = | = |
| `'add_entity' in Engine.__dict__` | True | **False** | True | True |
| `Engine._core` resolvable | True | True | True | True |
| `add_entity.__qualname__` | Engine.x | **Mixin.x** | Engine.x | Engine.x |
| `add_entity.__module__` | engine | **mixin-mod** | engine | engine |
| declaring class | Engine | **Mixin** | Engine | Engine |
| `getsource(Engine._core)` succeeds | yes | yes | yes | yes |
| **`getsource(Engine._core)` shows real body** | True | **True** | **False** | **False** |
| `__mro__` / `__bases__` | 2/1 | **4/2** | 2/1 | 2/1 |
| runtime behavior / `setattr` spy | ok | ok | ok | ok |
| **traceback frame depth** | 2 | **2** | **3** | **3** |

Honest reading (no property hidden):
- **Mixin changes** `__dict__` membership, `__qualname__`, `__module__`,
  declaring class, `__mro__`/`__bases__`, and `help()`/pydoc grouping. **No
  current test asserts any of these** (§4: 0 hits). Classification:
  **ACCEPTABLE-BUT-EXPLICIT** (recorded, approved in Consequences, not hidden).
- **Mixin preserves** the one property a test *does* pin —
  `getsource(Engine._compute_effective_confidence_core)` returns the **real
  body** — because `getsource` follows the function object into the mixin module.
- **Delegation / module-fn preserve** `__dict__`/`__qualname__`/declaring-class,
  but the seam's `getsource` returns the **wrapper** (the real body moved to the
  delegate/module). For the M07-pinned seam this is a **test-relevant break**
  unless that seam is kept on `Engine`. They also add **one traceback frame**.
  The traceback frame is a **cost** (no test asserts traceback depth), **not a
  blocker**; the seam-`getsource` break **is** test-relevant (G4/G11).

Caveat recorded: the prototype `_core` is a one-liner, so "real body" is a proxy
for M07's AST assertions on the actual multi-line composer-delegation body; the
direction of the delta (mixin preserves, B/C wrap) is what the prototype
establishes, and it matches M07's mechanism.

## Dependency / circular-import analysis (per candidate)
Fixed boundary (all candidates): `ragcore/engine.py` = public façade;
`ragcore/_engine/` = private implementation package; **replacing
`ragcore/engine.py` with an `engine/` package is forbidden**; `serialization.py`
and `confidence.py` stay pure (`{__future__, ragcore.types}` only).

- **Mixin**: mixin modules reference `self` only → import `ragcore.types` (+ the
  existing pure kernels) → **no runtime cycle**; `engine.py` imports the mixins.
  Confirmed structurally by the experiment (mixin variant imported cleanly).
- **Delegation / module-fn**: delegates/functions receive the engine/state at
  runtime (no runtime import of `engine`); any `Engine`/port typing is
  `TYPE_CHECKING`-only → no runtime cycle. The forbidden shapes
  (`confidence.py → engine`, `serialization.py → engine`, `serialization ↔
  confidence`) are introduced by **none** of the candidates.

## v2 extension-seam analysis
The v2 physics/derived layer reads an **immutable/read-only state projection**,
computes derived results with a **separate trace identity**, and mutates the
engine (advancing `_state_revision`) **only** through an explicit official API.
The seam for this is the **existing** `_state_view() → DecodedEngineState`
projection plus the public mutation API — it is **independent of the internal
decomposition**, so all three candidates can host it. The relevant differentiator
is incidental: under mixin a future read-only physics adapter reads `self._<store>`
through the same shared-`self` pattern with no back-ref; under delegation it needs
another back-ref'd delegate. No candidate forces a generic store, a runtime
modifier registry, a new snapshot schema, or a new state kind — and **none of
those is designed or implemented here** (out of Phase 3A scope).

---

## Decision
**Selected: Candidate A — mixin composition** for the ten stateful method
clusters, with the existing pure stateless kernels (`confidence.py`,
`serialization.py`) retained as module functions.

**Selection reason — grounded in the measured discriminating gates and costs,
not in an a-priori preference.** Among the gate-passing candidates, mixins
produce the **least delta from this engine's measured shared-state topology and
existing introspection surface**:
1. The topology is pervasively shared-`self`: every mutator calls the single
   revision authority (`_advance_state_revision`, 20 callers) + single ID
   authority (`_allocate_id`) + guards, and writes a per-kind `self._<store>`.
   Mixins reach all of this through the same `self` with **zero back-reference
   and zero generic store**. Delegation needs a back-reference that exposes the
   whole store set to every delegate; module functions need a `state` port
   **measured at 14 stores + 12 private methods** (≈ the entire private surface).
2. Mixins pass **G4/G9/G11 cleanly**: `getsource(Engine._compute_effective_confidence_core)`
   still returns the real body (the M07 lock), zero façade boilerplate, zero test
   change. Delegation/module-fn pass these only **conditionally** — by keeping
   that seam on `Engine` (an exception to their own pattern) — and add a
   traceback frame.
3. The introspection properties mixins change (`__qualname__`, `__module__`,
   `__dict__` membership, declaring class, `__mro__`/`__bases__`, help-grouping)
   are asserted by **no** current test (§4 lock inventory: 0 hits).

This is **not** a claim that mixins are generally superior. It is that, for *this*
shared-state topology and *this* introspection surface, mixins change the least
while preserving the one seam-introspection property a test actually pins.

## Rejected alternatives
### Rejected — Candidate B (delegation)
- Conditional G4/G11: delegating the confidence cluster makes
  `getsource(Engine._compute_effective_confidence_core)` return the wrapper
  (measured `real body = False`) → M07's body assertions fail. Avoidable only by
  keeping the seam on `Engine`, i.e. an exception to delegation for the very
  cluster the pattern would target.
- G7 spirit: each `Ops(self)` delegate holds a back-reference and reaches
  `engine._<store>`, `engine._advance_state_revision`, the guards, and sibling
  queries — exposing the **whole** private surface to every delegate (the
  opposite of the encapsulation delegation is meant to buy).
- Cost: ~42 public façade wrappers + the private seams that must stay on Engine;
  +1 traceback frame (measured depth 3 vs 2) — a cost, not a hard blocker.
- Decisive: it changes more of the *test-pinned* surface (seam `getsource`) than
  mixins, for *more* boilerplate, to solve a coupling problem the measured DAG +
  shared-`self` topology does not have.

### Rejected — Candidate C (module functions)
- Same conditional G4/G11 seam-`getsource` break + traceback frame as B.
- G7 quantified: the `state` port is **measured at 14 stores + 12 private
  methods** — essentially the entire private surface threaded as a parameter.
  Either the port is `self` (then the functions are relocated methods that still
  need Engine wrappers — B's boilerplate) or a `Protocol` duplicating the whole
  private surface.
- Decisive: highest structural exposure of the private surface of the three, for
  no gate it passes better than mixins.

## Consequences
Because the selected architecture composes mixins that share `self`:

- **No-expansion rule (a 3B design constraint that FOLLOWS from selecting mixins
  — it was not a premise of the selection):** any cluster that reads or writes a
  `self._<store>`, or calls a shared-`self` seam (`_advance_state_revision`,
  `_allocate_id`, `_assert_*_exists`, `_record_claim_lifecycle_transition`), is
  implemented as a **mixin**. Only **fully stateless pure computation** may be a
  module function. That exception is closed today at exactly **two** modules —
  `confidence.py` and `serialization.py` — and may not expand to any stateful
  cluster.
- **Accepted introspection deltas (explicitly approved, not hidden):**
  `method.__qualname__` becomes `"<Mixin>.<name>"`; `method.__module__` becomes
  the mixin module; the declaring class becomes the mixin; methods are inherited
  (not in `Engine.__dict__`); `Engine.__mro__`/`__bases__` grow; `help()`/pydoc
  group methods by mixin. Preserved: `from ragcore.engine import Engine`,
  `Engine.__module__ == "ragcore.engine"`, 42 public names/signatures, runtime
  behavior, `dir(Engine)` count, `setattr(Engine, name, …)`,
  `getsource(Engine._seam)` real body.
- **C1 (core/identity/id/guards) stays on the assembling `Engine` class** as the
  shared base; mixins call `self._advance_state_revision()` etc., resolved via
  the MRO. No store ownership transfer is required — every store stays a
  `self._<kind>` attribute of `Engine`; mixins only *contribute methods*.
- **`_claims` co-ownership (C2 + C5)** needs no special handling: both mixins
  write `self._claims`; the store never leaves `Engine`.

## Phase 3B decomposition sequence
Each 3B PR moves **one** cluster's method bodies into a mixin module under
`ragcore/_engine/`, has `Engine` inherit it, and leaves all stores + C1 on
`Engine`. Ordered by **ascending coupling** (lowest write-coupling first — NOT
largest line count):

```
3B-1  C8 hint-evidence     cluster: register/unregister/clear_hint_evidence_types + _validate_hint_evidence_type_values
                           store: _hint_evidence_types (1, single-owner)  xcall: C1 only
                           rationale: leaf, write=1, smallest rollback, proves the mixin seam
3B-2  C3 relations         add_relation, get_relation | store _relations(1) | xcall C1 only
3B-3  C7 rules             register_rule, get_rule, get_rule_stats, update_rule_stats | _rule_definitions,_rule_stats | xcall C1
3B-4  C4 gaps              add_gap,get_gap,gaps_for_claim,gap_resolution,resolve_gaps_for_evidence | 4 stores single-owner | xcall C1
3B-5  C9 confidence adapt. read-only; compute_*+_compute_effective_confidence_core+6 _*_modifier_for_claim+evidence_freshness
                           NOTE: M07 pins getsource(Engine._compute_effective_confidence_core)=real body — the mixin PRESERVES it
3B-6  C6 lifecycle history _record_claim_lifecycle_transition, claim_lifecycle_history (recorder; precede C5)
3B-7  C2+C5 together       CRUD + lifecycle/contradiction — co-own _claims; the only cross-cluster write coupling → one PR
3B-8  C10 snapshot façade  to_snapshot, from_snapshot, _state_view, _install (delegate to serialization kernel)
(C1 core/identity/id/guards: stays on the Engine base — optional final CoreMixin extraction only if it adds clarity)
```
Each step must keep green: full pytest; public 42 exact signatures; `__all__` 50;
snapshot 2/18/key-order/canonical bytes; PR51 7 keys; fresh lineage; policy id;
no import cycle; intended files only.

## Phase 3B entry conditions
```
[x] Phase 3A ADR selects ONE architecture (mixins) explicitly
[x] both alternatives rejected with decisive, measured reasons
[x] self-call graph complete (DAG, 0 SCCs)
[x] store read/write matrix complete (cross-cluster write coupling = _claims only)
[x] introspection-delta experiment complete (4 prototypes, measured)
[x] import-graph / cycle proof complete (no candidate adds a runtime cycle)
[x] v2 seam evaluated (state projection + public API; decomposition-independent)
[x] 3B cluster sequence defined (ascending coupling, lowest first)
[x] test-migration list: NONE required by 3A; 3B keeps runtime/getsource locks (no reversion)
[x] accepted introspection deltas explicitly listed and approved
[ ] GPT independent review APPROVE  (pending)
[ ] Phase 3A squash merge           (pending)
[ ] post-merge main full suite green (pending)
```
**Phase 3B remains prohibited until all Phase 3A entry conditions are
independently reviewed, approved, merged, and post-merge verified.**

## Adversarial review record (performed inline)
A multi-agent review panel was started but stopped at the user's request (it
generated repeated approval prompts); the adversarial review below was performed
inline instead, producing the same record.

**Strongest objection per candidate, and disposition:**
- *Delegation should win — it preserves `__qualname__`/`__dict__`/declaring
  class.* → True but **not the test-pinned properties**: it breaks
  `getsource(seam)=real body` (M07) and adds a traceback frame. Net it changes
  *more* of what tests actually assert. Rejected.
- *Module functions are the most testable/pure.* → The pure parts are **already**
  module functions (confidence/serialization). For the stateful clusters the
  measured port is 14 stores + 12 private methods ≈ the whole private surface.
  Rejected on measured exposure.
- *Mixins are a code smell / MRO is fragile.* → The self-call graph is a **DAG
  with 0 SCCs**; no `super()` cooperation or diamond is required (mixins are
  disjoint method sets over a shared `self`). MRO risk is structurally absent
  here.

**Evidence checked:** baseline counts, SCC count (Tarjan), per-store mutators,
cross-cluster coupling, port width, and the four-prototype introspection deltas
were each computed from the source, not asserted.

**Measurement error found:** one — the cluster-assignment script left
`evidences_for_claim` unassigned (a read-only claim→evidence query; belongs with
C2/C9 reads). It does not change any coupling conclusion (read-only, single
store). Recorded, not hidden.

**Premature-mixin-bias verdict:** one risk found and corrected — an earlier draft
embedded the no-expansion rule inside the decision, which could read as a
premise. Corrected so the rule appears strictly under *Consequences* as a result
of the selection; the candidate comparison and gate application are stated before
any selection.

**Seven verification points (requested):**
1. prototypes included a representative public method **and** a named private
   seam — yes (`add_entity`/`get_entity` + `_core`/`_advance_state_revision`).
2. mixin's `__dict__`/`__qualname__`/declaring-class/mro changes are shown, not
   hidden — yes (measured table + Accepted deltas).
3. delegation's +1 traceback frame classified as a **cost**, not a blocker — yes;
   the blocker-candidate (seam `getsource`) is separated out as G4/G11.
4. module-fn state-port width proven from the store matrix — yes (14 + 12).
5. the 10 clusters' real independence stated honestly — yes (DAG, but shared C1 +
   C6 + `_claims` co-ownership; not ten islands).
6. first 3B cluster is the lowest write-coupling, not the largest — yes (C8/C3,
   write=1).
7. the pure-kernel exception is closed at exactly two modules — yes
   (confidence.py, serialization.py), with a hard no-expansion rule.

**Final verdict:** mixin selection stands after adversarial review; the one
measurement slip and the one bias risk were corrected above; no gate decision was
overturned.

## Rollback / stop conditions (for 3B)
STOP-AND-REPORT (do not improvise) if any 3B step would: change a public
signature; change `Engine.__module__`; replace `ragcore/engine.py` with a
package; require a generic store; require a runtime modifier registry; change
state-revision semantics; break the `serialization.py`/`confidence.py` pure
boundary; introduce a runtime import cycle; force an M07/seam test to be re-pinned
to a location; or make the first 3B cluster non-isolable as its own PR.

## Forbidden conclusions
This ADR does **not**: implement any cluster; create a 3B branch; design a v2
physics algorithm, a new public API, a generic store, a modifier registry, a new
snapshot schema, or a new state kind; or treat "the runtime API is the same" as a
reason to ignore an introspection delta (each delta is classified explicitly
above).

