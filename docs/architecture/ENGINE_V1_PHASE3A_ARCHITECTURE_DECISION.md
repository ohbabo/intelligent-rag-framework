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
*(recorded in the second commit — see below)*
