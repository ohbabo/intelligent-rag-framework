# Engine Internal Map — Frozen Engine Refactor Audit

> **⚠️ SUPERSEDED — historical document.**
> This is the historical 1145-test-era audit of the single-class `Engine` (Region
> A–K inside one `engine.py` body). It is **NOT authoritative for the current
> Engine topology**: after the Phase 0–4 refactoring, `Engine` is a thin C1 core
> composed of nine private mixins, and the "Region" layout below no longer matches
> the source. For the current structure and the frozen external contract, see
> **`docs/architecture/ENGINE_V1_FINAL_BOUNDARY.md`**. The content below is kept for
> historical reference only.

Status: audit document (PR47)
Baseline: main `5bb360f` (PR46-B merged)
Type: doc-only architecture audit, no source change, no refactor

## 0. Scope limitation (locked, user 2026-05-23)

```text
PR47 is a doc-only audit.

PR47 may identify refactor candidates.
PR47 must NOT perform refactor.

PR47 scope:
  ragcore/engine.py only

PR47 does NOT touch:
  ragcore/types.py
  ragcore/__init__.py
  ragcore/rule_output.py
  any test
  any other source file

PR47 produces:
  docs/architecture/ENGINE_INTERNAL_MAP.md   (this file — section + audit)
  docs/dev/PR_047_FROZEN_ENGINE_INTERNAL_REFACTOR_AUDIT.md (PR record)
```

한국어:

```text
PR47 은 리팩토링 PR 이 아니라 audit-first PR 이다.
PR47 은 "동결된 engine.py 를 건드려도 안 깨지는 구역" 과
"건드리면 안 되는 구역" 을 분리해 지도로 그린다.
실제 리팩토링은 PR48 (별도 진입) 이후의 결정.
```

## 1. Status

```text
base:                main 5bb360f
tests:               1145 passing
phase:               doc-only architecture audit
source change:       0
new tests:           0
new public symbol:   0
new engine behavior: 0

Engine freeze ≠ no-touch.
Engine freeze = public behavior / public method surface /
                snapshot contract / judgment semantics unchanged.
```

## 2. ragcore/engine.py overview

```text
File length:        1800 lines
Class:              1   (Engine, L224 ~ L1580)
Engine methods:    61   (40 public + 21 private)
                        — public methods match the PR33-M /
                          PR36-PKG 40 _LOCKED_PUBLIC_METHODS
Module-level:      19 constants (L58 ~ L193)
                        — modifier weights / thresholds /
                          schema version (PR12 ~ PR21, PR23, PR24,
                          PR26 origin)
                   24 module-level helpers (L1588 ~ L1800)
                        — snapshot migration + dataclass
                          restore + dict serialize/restore
```

### 2.1 Major regions (by line range)

```text
Region A   L 1 ~  220   module header
                         - imports
                         - 19 module-level constants (modifier
                           weights / thresholds / schema version)

Region B   L 224 ~  310  Engine __init__ + private guards
                         - __init__ (28 L)
                         - _allocate_id / _storage_for_kind /
                           _id_exists / _assert_*_exists  (8 helpers)

Region C   L 314 ~  512  CRUD layer (Identity + Evidence + Relation)
                         - add_entity / get_entity
                         - add_observation / get_observation
                         - add_claim / get_claim
                         - add_evidence / get_evidence /
                           evidences_for_claim
                         - add_relation / get_relation

Region D   L 514 ~  626  Gap layer
                         - add_gap / get_gap / gaps_for_claim
                         - resolve_gaps_for_evidence
                         - gap_resolution

Region E   L 630 ~  907  Lifecycle layer (transitions + contradictions)
                         - confirm_claim_if_ready
                         - register_contradiction /
                           contradictions_for_claim
                         - refute_claim_if_ready
                         - dispute_claim_if_ready
                         - register_contradiction_resolution /
                           resolved_contradictions_for_claim /
                           active_contradictions_for_claim
                         - resolve_disputed_claim_if_ready
                         - refute_disputed_claim_if_ready

Region F   L 911 ~  996  Lifecycle history + freshness queries
                         - _record_claim_lifecycle_transition (private)
                         - claim_lifecycle_history
                         - evidence_freshness
                         - active_contradictions_by_freshness

Region G   L1000 ~ 1046  Freshness-based refute (single method, 47 L)
                         - refute_disputed_claim_if_ready_by_freshness

Region H   L1050 ~ 1092  Rule meta
                         - register_rule / get_rule / get_rule_stats

Region I   L1103 ~ 1369  7-modifier helper layer
                         - _status_modifier_for_claim         ( 6 L)
                         - _freshness_modifier_for_claim     (12 L)
                         - _gap_modifier_for_claim            (22 L)
                         - _count_modifier_for_claim          (23 L)
                         - _rule_stats_modifier_for_claim    (77 L)  ★largest helper
                         - _validate_hint_evidence_type_values (37 L)
                         - register_hint_evidence_types      (22 L)
                         - unregister_hint_evidence_types    (19 L)
                         - clear_hint_evidence_types         (14 L)
                         - _evidence_type_modifier_for_claim (26 L)

Region J   L1371 ~ 1498  Effective confidence + rule stats update
                         - compute_effective_confidence (90 L)  ★largest method
                         - update_rule_stats             (37 L)

Region K   L1502 ~ 1580  Snapshot serialize / restore (on Engine)
                         - to_snapshot
                         - from_snapshot (classmethod)

Region L   L1588 ~ 1632  Snapshot migration (module-level)
                         - _migrate_snapshot_v1_to_v2
                         - _migrate_snapshot_to_current

Region M   L1638 ~ 1692  Dataclass restore from dict (module-level)
                         - _sv_to_dict / _sv_from_dict
                         - _entity_from_dict / _observation_from_dict /
                           _claim_from_dict / _evidence_from_dict /
                           _relation_from_dict / _gap_from_dict /
                           _rule_def_from_dict / _rule_stats_from_dict

Region N   L1695 ~ 1800  Dict serialize/restore helpers (module-level)
                         - _serialize_* / _restore_* (12 helpers)
```

These 14 regions are the *current* layout. They are an audit artifact, NOT a refactor proposal.

## 3. Do-not-touch boundary

The following are LOCKED. PR47 must NOT propose changes to them. PR48 (if it ever enters) must preserve them by-construction.

```text
1.  7-modifier composition formula
    (PR12 / PR14 / PR16 / PR19 / PR20 / PR21 / PR23 / PR24 /
     PR26 / PR29 / PR34-O / PR36-PKG §48.7)

2.  Lifecycle helper internal decision logic
    (6 _if_ready helpers; PR6 ~ PR10, PR15)

3.  Snapshot serialize/restore symmetry
    (PR35-O7 — 6 × 6 dataclass / dict mirror)

4.  40 public method signatures
    (PR33-M 40/40 + PR36-PKG _LOCKED_PUBLIC_METHODS)

5.  Public observable behavior of every Engine.method(*args)
    (return types, error types, side effects visible from outside)

6.  18 snapshot top-level keys
    (PR36-PKG _LOCKED_SNAPSHOT_TOP_LEVEL_KEYS)

7.  Effective-confidence modifier call chain
    (status × freshness × gap × count × rule_stats × evidence_type;
     base × ... ordering and saturation rules)

8.  Report / read-surface keys
    (PR32-V 6 frozen key sets)

9.  Public namespace / ragcore.__all__
    (PR31-S 48 symbols; PR36-PKG _LOCKED frozensets)

10. Adapter / Cerberus integration code
    (does not exist in ragcore source; must remain that way)
```

These ten items are the **freeze surface.** PR47's job is to identify candidates that can be moved *without* touching any of them.

## 4. Audit category 1 — Internal function split candidates

Per-method internal split candidates. Public signature stays identical; the body may later be reorganized into private helpers.

```text
safe-to-touch candidates:

  - compute_effective_confidence  (L1371-1460, 90 L)
      reads:
        six modifier helpers in sequence;
        contains modifier accumulation + saturation + clipping.
      possible private split (PR48 only):
        _accumulate_modifiers(...)
        _saturate_and_clip(...)
      do-not-touch boundary:
        - the return value for every (claim_id, state) input
          MUST remain bit-identical (see §3 #7).

  - _rule_stats_modifier_for_claim  (L1170-1246, 77 L)
      reads:
        maturity penalty + precision band + saturation logic.
      possible private split:
        _rule_stats_maturity_factor(...)
        _rule_stats_precision_factor(...)
      do-not-touch boundary:
        - composed modifier value MUST stay bit-identical
          (see §3 #1, #7).

  - refute_disputed_claim_if_ready_by_freshness  (L1000-1046, 47 L)
      reads:
        freshness window + contradiction-by-freshness scan +
        transition condition.
      possible private split:
        _disputed_freshness_window(...)
        _evaluate_disputed_freshness_transition(...)
      do-not-touch boundary:
        - the bool the helper returns MUST remain identical for
          every (claim_id, state) input (see §3 #2, #5).

  - refute_disputed_claim_if_ready  (L866-907, 42 L)
      reads:
        standard disputed→refute readiness check.
      possible private split:
        _has_required_contradicting_evidence(...)
      do-not-touch boundary: §3 #2, #5.

  - add_relation  (L464-504, 41 L)
      reads:
        kind validation + dual-side id assertion + storage write.
      possible private split:
        _assert_relation_endpoints(from_kind, from_id, to_kind, to_id)
      do-not-touch boundary: §3 #4, #5.

do-not-touch (split would risk freeze):

  - all six lifecycle *_if_ready helpers' decision logic
    (§3 #2 — internal branches are part of the audit trail
     contract surface even though the methods are public).
  - to_snapshot / from_snapshot bodies
    (§3 #3, #6 — splitting risks reordering of key emission).
  - update_rule_stats body
    (§3 #1 — touches RuleStats persistence path).
```

## 5. Audit category 2 — Duplicate logic candidates

Identical or near-identical local logic that appears in more than one place.

```text
safe-to-touch candidates:

  - _assert_*_exists family
      (_assert_entity_exists / _assert_claim_exists /
       _assert_evidence_exists / _assert_gap_exists /
       _assert_rule_pair_exists / _assert_rule_stats_pair_exists)
      observation:
        six near-identical 2-6 line guards.
      possible consolidation (PR48 only):
        a single generic _assert_id_exists(storage, id, kind_label)
        — only if every existing guard's raised-exception type
          and message remain bit-identical.
      do-not-touch boundary:
        - error type and error message of each existing guard
          MUST be preserved (§3 #5 public observable behavior).

  - lifecycle history recording
      observation:
        every transition method calls
        self._record_claim_lifecycle_transition(...) at exactly
        one place; pattern is already centralized.
      verdict:
        already centralized; no duplication. (kept here only as
        an "audited and clean" marker.)

  - serialize/restore helpers (Region N)
      observation:
        _serialize_dict_* family has six variants by value
        shape (int / set / list / dataclass / tuple4 / int->int).
        _restore_dict_* mirrors the same six.
      verdict:
        intentional symmetry (PR35-O7). NOT duplication.
        do-not-touch (§3 #3).

do-not-touch (apparent duplication is intentional):

  - modifier helper bodies
    (each modifier has its own well-defined formula;
     §3 #1 forbids merging or sharing math).
  - snapshot key emission order
    (§3 #3, #6 — order is part of contract).
```

## 6. Audit category 3 — engine.py section boundaries

Suggested logical section comment-headers for orientation. These would be *comment-only* additions, no code reordering.

```text
safe-to-touch candidates (PR48 — comment-only insertion):

  L  220 region break before  __init__ + guards          (Region B)
  L  311 region break before  CRUD layer                  (Region C)
  L  513 region break before  Gap layer                   (Region D)
  L  629 region break before  Lifecycle layer             (Region E)
  L  909 region break before  Lifecycle history layer     (Region F)
  L  999 region break before  Freshness-based refute      (Region G)
  L 1049 region break before  Rule meta                   (Region H)
  L 1102 region break before  Modifier helpers            (Region I)
  L 1370 region break before  Confidence + rule stats     (Region J)
  L 1501 region break before  Snapshot on Engine          (Region K)
  L 1587 region break before  Snapshot migration (module) (Region L)
  L 1637 region break before  Dataclass restore (module)  (Region M)
  L 1694 region break before  Dict serialize/restore      (Region N)

do-not-touch (boundary moves would shift method order):
  - the order in which Engine methods are declared on the class
    is part of the docstring-audit surface (PR33-M).
    Adding `# ---- region X ----` comments is acceptable;
    moving method definitions across regions is NOT.
```

## 7. Audit category 4 — Private helper relocation candidates

Private helpers currently positioned in places that may or may not match their semantic group.

```text
safe-to-touch candidates (PR48 only):

  - _validate_hint_evidence_type_values  (L1248-1284, 37 L)
      current placement:
        inside modifier helper region (Region I), between
        _count_modifier_for_claim and register_hint_evidence_types.
      observation:
        this is the *validation* path for the hint API; it does
        NOT participate in modifier composition itself.
      possible move:
        adjacent to register_hint_evidence_types (also Region I)
        so the public hint API and its validator sit together.
      do-not-touch boundary:
        - validator's raised-exception type and message MUST
          stay identical (§3 #5).
        - moving the method MUST NOT alter the public method
          order on Engine (§7 declaration order).

do-not-touch (current placement is intentional):

  - _record_claim_lifecycle_transition (Region F)
      placement matches the lifecycle history boundary in PR10-B §23.
      keep where it is.
  - _allocate_id / _storage_for_kind / _id_exists (Region B)
      foundational helpers; correctly placed at top of class.
      keep where they are.
  - all module-level serialize/restore (Regions L/M/N)
      module-level by design (PR35-O7); keep at module scope.
```

## 8. Audit category 5 — Private / helper docstring candidates

PR33-M locked the 40 public method docstrings. PR47 audits the 21 private helpers + 24 module-level helpers for docstring coverage; this is the only category where the audit may safely identify "add missing docstring" work.

```text
safe-to-touch candidates (PR48 — docstring-only):

  Engine private helpers without rich docstrings:
    _allocate_id
    _storage_for_kind
    _id_exists
    _assert_entity_exists  / _assert_claim_exists /
    _assert_evidence_exists / _assert_gap_exists /
    _assert_rule_pair_exists / _assert_rule_stats_pair_exists
    _record_claim_lifecycle_transition
    _status_modifier_for_claim
    _freshness_modifier_for_claim
    _gap_modifier_for_claim
    _count_modifier_for_claim
    _rule_stats_modifier_for_claim
    _validate_hint_evidence_type_values
    _evidence_type_modifier_for_claim

  Module-level helpers without rich docstrings:
    _migrate_snapshot_v1_to_v2 / _migrate_snapshot_to_current
    _sv_to_dict / _sv_from_dict
    _entity_from_dict / _observation_from_dict / _claim_from_dict /
    _evidence_from_dict / _relation_from_dict / _gap_from_dict /
    _rule_def_from_dict / _rule_stats_from_dict
    _serialize_dict_* / _restore_dict_* family

do-not-touch boundary:
  - docstring additions MUST NOT contradict the PR33-M 40/40
    public docstring lock.
  - docstring text MUST NOT redefine behavior — it documents
    existing behavior only.
  - docstring formatting MUST NOT break sphinx/typing tools
    that may consume the module.
```

## 9. Audit category 6 — Import cleanup candidates

Import structure observation.

```text
current module-level imports (L7 ~ L13):

  from __future__ import annotations
  from collections.abc import ...
  from dataclasses import ...
  from typing import ...
  from ragcore.types import ...

verdict:
  - no obvious unused imports detected at audit time.
  - no obvious ordering violations (stdlib → third-party →
    first-party order observed).
  - audit finds no actionable cleanup item.

safe-to-touch candidates (PR48 only, if and only if):
  - a future PR adds new code that introduces unused symbols;
    cleanup is then bundled with that PR, not PR48.

do-not-touch (intentional):
  - `from __future__ import annotations` is required and must
    stay first.
  - third-party imports are deliberately absent; do NOT add
    chromadb / qdrant / pinecone / faiss / neo4j / openai /
    anthropic / psycopg / sqlalchemy.
    (PR44-D AP-X-6 / AP-X-7.)
```

## 10. Summary table

```text
Category                                Safe-to-touch    Do-not-touch
-------------------------------------------------------------- 
1  internal function split                5 candidates      6 items
2  duplicate logic                        2 candidates      2 items
3  section boundaries (comments)         13 insertion lines  0 reordering
4  private helper relocation              1 candidate        3 items
5  private / module docstring            ~25 helpers          0 public
                                                              docstring change
6  import cleanup                          0 actionable        all current
                                                              imports kept
-------------------------------------------------------------- 
TOTAL                                    ~46 candidate moves 11 freeze items

All "safe-to-touch" items, if performed, MUST preserve:
  - 1145 passing tests
  - 48 ragcore.__all__ symbols
  - 40 Engine public methods
  - snapshot schema_version 2
  - 18 snapshot top-level keys
  - 6 × 6 serialize/restore symmetry
  - 7-modifier composition formula
  - effective_confidence value for every (state, claim_id) input
  - lifecycle transition result for every (state, claim_id) input
  - report / read-surface key sets
  - generic identity (0 cerberus mentions, 0 external package imports)
```

## 11. What PR47 deliberately does NOT do

```text
PR47 does NOT:

  - perform any refactor
  - move any function
  - rename any symbol
  - add or remove any comment or docstring in engine.py
  - touch engine.py source bytes
  - touch ragcore/types.py / ragcore/__init__.py / ragcore/rule_output.py
  - add or change any test
  - add new public API
  - add or remove ragcore.__all__ entries
  - propose new contract section (§51 or beyond)
  - propose runtime enforcement
  - propose adapter implementation
  - propose Cerberus-specific code
  - propose modifier formula adjustments
  - propose snapshot schema changes
  - propose report key changes
  - schedule PR48 automatically (PR48 entry is a separate decision)
```

## 12. Followup — PR48 entry conditions

PR48 is **not entered** by PR47. If a future Track A/B decision picks up refactoring, the entry conditions are:

```text
PR48 entry conditions (all must hold):

  1. PR48 selects ONE category from §4 ~ §9.
     (Do not bundle multiple categories in a single PR.)

  2. PR48 selects a subset of "safe-to-touch candidates" inside
     that category. Do not claim to address all candidates at
     once.

  3. PR48 demonstrates that:
       - pytest -q still returns 1145 passing
       - ragcore.__all__ still has 48 symbols
       - Engine public method count still 40
       - snapshot schema_version still 2
       - 18 snapshot top-level keys unchanged
       - to_snapshot()/from_snapshot() round-trip preserves
         compute_effective_confidence for the same claim_ids
       - PR41 simulation tests + PR43-C 168차 invariant tests
         still pass with zero changes

  4. PR48 cycle follows the 2-차수 pattern:
       N차      src refactor commit (engine.py only, minimal diff)
       N+1차    docs(dev) record + ready + squash merge

  5. PR48 cycle does NOT touch any of the 10 do-not-touch items
     listed in §3.
```

## 13. Closing meaning

```text
PR47 maps the inside of frozen engine.py.

It does not refactor.
It identifies what can be safely moved and what must not be touched.

The freeze surface is unchanged.
PR48 is not scheduled. It is a separate, optional decision.

The framework reads as a stack now.
The framework waits.
```

Locked closing sentences:

```text
PR47 may identify refactor candidates.
PR47 must not perform refactor.

frozen baseline preserved.
internal map drawn.
framework waits.
```
