# PR 033 — Method Surface Audit + Scope A Cleanup MVP

## Summary

PR33-M is the first PR that explicitly touched the public method surface as a *cleanup* objective rather than a *judgment* objective.

Final scope: **audit-first + Scope A cleanup**.

Core closing statement:

```text
PR33-M did not shift the frozen method surface baseline.
It cleaned the public surface by documenting existing methods,
correcting the 48-symbol count, and grouping __all__ without
changing Engine judgment semantics.
```

This PR adds no new Engine API, no new public symbol, no method rename, no snapshot schema change, no formula change. Sub-decision D is preserved in spirit (engine.py and __init__.py touched only for docstring + ordering; types.py and rule_output.py unchanged).

Two-차수 cycle inside PR33-M:

```text
138차  docs(contract) §45  Method Surface Cleanup Boundary + audit findings
139차  refactor(core)       Scope A execution (P1 + P2 + P3)
140차  docs(dev) (this)     PR record + ready + squash merge
```

> **PR33-M closed without P4/P5/P6.**
> **It cleaned what was safe to clean and deferred renames / restructures / convenience methods to future PRs.**

---

## Why PR33-M after PR32-V

After PR32-V, the framework had:

```text
PR27-P  call boundary       (§39 how to call)
PR30-P  read boundary       (§42 how to read)
PR31-S  usage recipe        (§43 what order)  + method surface freeze
PR32-V  report surface      (§44 what shape)  + report shape freeze
```

What was missing was **surface cleanup affordance**. PR27-P~PR32-V locked external boundaries but did not touch the public surface itself for cleanup purposes. Specifically:

```text
- 13 of 40 Engine public methods had no docstring
- prior PR records said "49 symbols" while the actual count was 48
  (a wording typo carried from PR31-S through PR32-V)
- __all__ was alphabetic, mixing 12 natural groups together
```

PR33-M is the first PR with explicit license to clean the surface — under the strict constraint that judgment semantics remain unchanged.

User-locked framing (2026-05-21):

```text
PR33-M is a surface cleanup PR.
It may intentionally shift the frozen method surface baseline,
but it must not change Engine judgment semantics.
```

The "may intentionally shift" allowance was not exercised in PR33-M. The actual changes preserve `frozenset(ragcore.__all__)` exactly as PR31-S locked it. P4 / P5 / P6 (which *would* shift the baseline) were deferred.

---

## Baseline

Before PR33-M:

```text
main:  5c6a05c
tests: 1089 passing, 0 fail
```

Completed immediately before this PR:

```text
PR32-V report surface MVP (+ report shape freeze)
```

The active confidence formula entering PR33-M:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
```

PR33-M does not change this formula.

---

## §45 boundary category letter codes

§45 introduces the audit-vs-cleanup boundary categorization, distinct from the report-policy / usage-recipe / report-shape categories of §42 / §43 / §44.

Audit-only categories (138차):

| Category | Boundary                                                           |
| -------- | ------------------------------------------------------------------ |
| Surface domain  | method names, signatures, __all__, docstrings, helpers       |
| Semantic domain | modifier formula, lifecycle rules, snapshot schema, parsing  |

PR33-M may touch the surface domain. It must not touch the semantic domain.

Cleanup proposals (138차):

| Proposal | Risk    | Frozenset impact     | Scope A |
| -------- | ------- | -------------------- | ------- |
| P1 Docstring backfill (13 methods)         | low    | unchanged             | yes |
| P2 "49 symbols" -> "48" wording correction | low    | unchanged             | yes |
| P3 __all__ natural grouping reorder        | low    | unchanged (set eq)    | yes |
| P4 Naming consistency renames              | medium | shift                 | no  |
| P5 Tier 3 sub-module reorganization        | high   | large shift           | no  |
| P6 Engine.claim_report convenience method  | high   | sub-decision-level    | no  |

Scope A executed P1 + P2 + P3 only.

---

## §45 13 subsections (138차)

§45 was added to `docs/contracts/05_DATA_CONTRACT_MVP.md` in 138차 (+547 lines):

```text
§45.1   Core proposition (framing sentence)
§45.2   Audit boundary (surface vs judgment semantics)
§45.3   138차 audit scope
§45.4   Current public surface snapshot (48 symbols / 40 methods)
§45.5   Symbol grouping (12 natural groups)
§45.6   Engine public method naming patterns (21 prefixes)
§45.7   Naming consistency observations (A~G)
§45.8   Docstring coverage observations (13/40 missing)
§45.9   Symbol usage tier classification (Tier 1/2/3 proposal)
§45.10  Cleanup candidates P1~P6 (proposal, not decision)
§45.11  Audit-only invariants (read-only verification)
§45.12  Out of scope for 138차
§45.13  Constraints on 139차+ (Scope A/B/C/D-only selection)
```

§45 documented current state and proposed candidates. It did not execute any cleanup.

---

## Commits

### 138차 — docs(contract): define method surface audit boundary (§45)

Commit:

```text
029d635
```

Added:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md §45
```

Audit findings recorded:

```text
ragcore.__all__            48 symbols  (NOT 49 — prior PR narrative typo)
len(set(ragcore.__all__))  48          (no duplicates)
Engine public methods       40          (excluding __init__ and _private)
schema_version              2

12 natural groups identified:
  lifecycle_status_enum (4) / rule_maturity_enum (3) / kind_enum (6) /
  trace_reason_enum (4) / core_dataclass (7) / rule_dataclass (5) /
  trace_dataclass (5) / value_type (1) / engine_class (1) /
  compile_func (4) / evaluate_func (2) / fire_func (2) /
  load_func (3) / register_func (1) = 48

21 naming prefixes across 40 Engine methods (some consistent groups,
some inconsistencies in §45.7 A~G)

13 no-docstring methods (§45.8):
  add_entity, add_observation, add_evidence, add_relation,
  get_entity, get_observation, get_claim, get_evidence, get_gap,
  get_relation, get_rule, get_rule_stats, evidences_for_claim
```

138차 added zero code changes, zero test changes, zero frozenset shifts. It is a read-only audit document.

---

### 139차 — refactor(core): execute PR33-M Scope A surface cleanup

Commit:

```text
9541a1b
```

Changed:

```text
ragcore/engine.py                                P1 — 13 docstring backfill
ragcore/__init__.py                              P3 — __all__ 12-group reorder
docs/dev/PR_031_AI_READABLE_USAGE_RECIPE_MVP.md  P2 — "49" -> "48" (2 places)
docs/dev/PR_032_REPORT_SURFACE_MVP.md            P2 — "49" -> "48" (2 places)
```

Size:

```text
4 files
+129 lines
-22 lines
```

Result:

```text
1089 passing, 0 fail (unchanged)
```

Frozenset baseline impact:

```text
frozenset(ragcore.__all__) == _PR30_BASELINE_PUBLIC_SYMBOLS    OK
len(ragcore.__all__) == len(set(ragcore.__all__))               OK
PR31-S test_ragcore_all_matches_pr30p_baseline_exactly         pass
PR32-V test_ragcore_all_unchanged_from_pr30p_baseline          pass
```

P3 reorder is invisible to set equality. P1 docstrings are not tested. P2 record file edits are not tested.

---

## Scope A execution detail

### P1 — Docstring backfill (engine.py, 13 methods)

Each backfilled docstring follows the existing house style:

```text
English first line — short imperative summary
Korean detail block (optional) — invariant references, edge cases
Raises: section — what KeyError / ValueError can occur
```

Cross-references to relevant contract sections were added:

| Method                  | Contract reference                                          |
| ----------------------- | ----------------------------------------------------------- |
| add_entity              | caller-domain integer note                                  |
| add_observation         | §39 external integration boundary                           |
| add_evidence            | Sub-decision AF + PR21-L / PR22-S / PR25-T                  |
| add_relation            | §13 cross-kind discriminator                                |
| get_claim               | §42.3 / §43.9 read-side                                     |
| get_rule                | PR28-O §40 rule version pinning                             |
| get_rule_stats          | PR29-R §41 + §44.7 rule_pinning shape                       |
| evidences_for_claim     | contradiction separation                                    |
| get_entity / get_observation / get_evidence / get_gap / get_relation | KeyError note |

Docstring coverage shift:

```text
before:  13 / 40 (32.5%) no docstring
after:    0 / 40  (0%)    no docstring
         27 / 40 (67.5%)   ok (>=80 chr)  same as before, no rewrites
```

The 27 already-documented methods were not modified.

### P2 — "49 symbols" wording correction

4 narrative occurrences corrected:

```text
docs/dev/PR_031_AI_READABLE_USAGE_RECIPE_MVP.md:454
  "_PR30_BASELINE_PUBLIC_SYMBOLS = frozenset({...49 symbols...})"
  -> "...48 symbols..."

docs/dev/PR_031_AI_READABLE_USAGE_RECIPE_MVP.md:481
  "49 symbols including:"
  -> "48 symbols including:"

docs/dev/PR_032_REPORT_SURFACE_MVP.md:34
  "(49 symbols frozen at PR30-P main 60bf492)"
  -> "(48 symbols frozen at PR30-P main 60bf492)"

docs/dev/PR_032_REPORT_SURFACE_MVP.md:480
  "(the PR30-P main 60bf492 frozenset of 49 symbols"
  -> "(the PR30-P main 60bf492 frozenset of 48 symbols"
```

The actual frozenset literal in `tests/test_engine_ai_readable_usage_recipe.py` and `tests/test_engine_report_surface.py` was correct from day one (48 items in the literal). Only surrounding narrative was wrong. P2 brings the narrative into agreement with the code.

Note: git commit messages in main history (PR31-S commit, PR32-V commit) cannot be amended and remain as historical record. §45.4 documents the correction forward.

### P3 — __all__ natural grouping reorder

Before (alphabetic, 48 items, no grouping comments):

```python
__all__ = [
    "CLAIM_STATUS_CANDIDATE",
    "CLAIM_STATUS_CONFIRMED",
    ...
    "register_rule_spec",
]
```

After (12-group order, 48 items, inline §-reference comments):

```python
# Public API surface — 48 symbols, grouped by purpose (§45.5).
# Order is documentation, not behavior: tests use frozenset equality.
__all__ = [
    # Lifecycle status enum (4) — §18 / §42.2 / §43.3-5
    "CLAIM_STATUS_CANDIDATE",
    "CLAIM_STATUS_CONFIRMED",
    "CLAIM_STATUS_DISPUTED",
    "CLAIM_STATUS_REFUTED",
    # Rule maturity enum (3) — §27 RuleDefinition.maturity
    "RULE_MATURITY_DEPRECATED",
    ...
    # Register functions (1) — rule spec registration
    "register_rule_spec",
]
```

14 group sections total (one comment block per group), 48 symbols total (unchanged), 0 symbol added or removed.

Tests verifying `__all__`:

| Test                                              | Method               | Order-sensitive? |
| ------------------------------------------------- | -------------------- | ---------------- |
| test_ragcore_all_matches_pr30p_baseline_exactly   | frozenset equality   | no               |
| test_ragcore_all_unchanged_from_pr30p_baseline    | frozenset equality   | no               |
| test_ragcore_all_has_no_duplicate_symbols         | len comparison       | no               |

All three tests pass after reorder.

---

## P4 / P5 / P6 deferred

The audit (§45.10) proposed three additional candidates that PR33-M chose not to execute:

### P4 — Naming consistency renames (deferred)

Proposed renames:

```text
evidence_freshness        -> freshness_for_evidence
gap_resolution            -> get_gap_resolution
```

Reason deferred:

```text
- requires frozenset baseline shift (PR31-S _PR30_BASELINE_PUBLIC_SYMBOLS update)
- requires consumer-side import path update
- consistency-via-docstring is sufficient for now (P1 already documented
  these methods' semantics)
- worth a separate PR with explicit baseline shift documentation
```

Future PR candidate: PR-M-rename or similar surface-rename PR.

### P5 — Tier 3 sub-module reorganization (deferred)

Proposed: move 12 trace/debug symbols to `ragcore.trace.*` namespace.

Reason deferred:

```text
- requires large frozenset shift (12 symbols leave top-level __all__)
- import path change is disruptive for any external consumer
- ragcore is still small enough that the top-level remains comfortable
- worth a separate PR with explicit user approval
```

Future PR candidate: high-risk track requiring user sub-decision.

### P6 — Engine.claim_report convenience method (deferred)

Proposed: add `Engine.claim_report(claim_id) -> dict` bundling §44 shapes A~E.

Reason deferred:

```text
- PR32-V §44.11 explicitly listed Engine.claim_report as OOS
- reversing requires sub-decision-level re-evaluation
- PR32-V §44.12 invariants 8 + 9 explicitly assert absence of this method
- PR33-M consumer-side assembly principle works as designed; no convenience
  method is yet justified
- if ever justified, requires explicit sub-decision shifting from PR32-V
  §44.11 OOS line
```

Future PR candidate: high-risk track requiring user sub-decision + explicit PR32-V invariant amendment.

---

## Implementation footprint

Changed files (across 138차 + 139차):

```text
docs/contracts/05_DATA_CONTRACT_MVP.md            +547 lines (§45)
ragcore/engine.py                                  P1 docstrings
ragcore/__init__.py                                P3 reorder + comments
docs/dev/PR_031_AI_READABLE_USAGE_RECIPE_MVP.md   P2 typo fix (×2)
docs/dev/PR_032_REPORT_SURFACE_MVP.md             P2 typo fix (×2)
docs/dev/PR_033_METHOD_SURFACE_AUDIT_MVP.md       this record (140차)
```

Unchanged:

```text
ragcore/types.py
ragcore/rule_output.py
ragcore/rule_compile.py / rule_loader.py / rule_gap.py / rule_runtime.py / condition.py
all test files
```

No snapshot schema change:

```text
schema_version remains 2
```

No formula change:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
```

No lifecycle change:

```text
no new lifecycle state
no new lifecycle transition
```

No public API change:

```text
ragcore.__all__ still contains the same 48 symbols (P3 reorders only)
frozenset(ragcore.__all__) == _PR30_BASELINE_PUBLIC_SYMBOLS
no method rename
no method removal
no method addition
no deprecated alias
```

No report shape change:

```text
PR32-V CLAIM_SUMMARY_KEYS / EFFECTIVE_BREAKDOWN_KEYS / LIFECYCLE_EVENT_KEYS /
  EVIDENCE_CONTRADICTION_KEYS / RULE_PINNING_KEYS / SNAPSHOT_METADATA_KEYS
all unchanged
```

---

## Boundary preservation table

| Preserved boundary                                       | PR33-M effect                  | Status      |
| -------------------------------------------------------- | ------------------------------ | ----------- |
| Sub-decision D (types / rule_output unchanged)           | tests + docs + surface only    | preserved (engine.py / __init__.py touched for docstring + ordering only) |
| Sub-decision AF (HINT taxonomy framework-external)       | add_evidence docstring cites it | reinforced  |
| PR17 snapshot schema v2                                  | unchanged                      | preserved   |
| PR21-L hint validation (caller-registered)               | unchanged                      | preserved   |
| PR27-P consumer call boundary (§39)                      | add_observation docstring cites it | reinforced |
| PR28-O rule version pinning                              | get_rule docstring cites it    | reinforced  |
| PR29-R observed_precision bounded no-boost               | get_rule_stats docstring cites it | reinforced |
| PR30-P consumer policy guides (§42)                      | get_claim docstring cites §42.3 | reinforced  |
| PR31-S AI-readable usage recipe (§43)                    | get_claim docstring cites §43.9 | reinforced  |
| PR31-S method surface freeze                             | frozenset unchanged after Scope A | preserved |
| PR32-V report surface (§44)                              | get_rule_stats docstring cites §44.7 | reinforced |
| PR32-V Engine.claim_report absence invariant             | P6 deferred, invariant unchanged | preserved |
| PR32-V no exact modifier value invariant                  | unchanged                     | preserved   |
| 7-modifier formula shape                                  | unchanged                     | preserved   |
| Sub-decision-level OOS list (FPR / quality verdict / etc.) | unchanged                    | preserved   |

---

## Test result

Final test result before merge:

```text
1089 passed, 0 failed
```

Delta:

```text
1089 -> 1089
no test added
no test removed
no test modified
```

Regression:

```text
0
```

Natural-expiry:

```text
0
```

The 138차 audit was read-only (zero file changes outside the contract doc). The 139차 Scope A execution touched code and docs but no test asserts docstring presence or `__all__` order, so the test suite is invariant.

If a future PR needs to add docstring-presence or `__all__`-order tests, that is a separate decision (not in PR33-M).

---

## Verification snapshot

After 139차:

```text
total symbols           48 (unchanged)
unique symbols          48 (no duplicates)
no-docstring methods     0  (was 13)
"49 symbols" narrative   0  (was 4 occurrences in PR records)
schema_version            2  (unchanged)
public Engine methods    40 (unchanged)
test suite               1089 passing, 0 fail
```

---

## Self-review

### What this PR does

PR33-M is the first PR that touched the public surface as a cleanup objective. The actual changes are conservative:

```text
- 13 method docstrings added (no signature change)
- 4 narrative typos corrected ("49" -> "48")
- __all__ list reordered into 12 natural groups (same 48 symbols)
- 14 inline group comments added to __init__.py
- §45 audit boundary documented (138차)
```

### What this PR does not do

PR33-M does not:

```text
shift the frozen method surface baseline       (P4/P5/P6 deferred)
add or remove any public symbol
rename any method
change any method signature
introduce any convenience method               (P6 deferred)
move any symbol to a sub-module                (P5 deferred)
modify Engine judgment semantics
modify any modifier formula
modify any lifecycle transition rule
modify snapshot schema
modify rule output parsing logic
modify contradiction registration logic
modify effective_confidence computation
add any new test
modify any existing test
```

### Why the conservative scope is correct

The user-locked PR33-M framing allows baseline shift but requires that judgment semantics remain unchanged. PR33-M could have exercised the shift permission (P4/P5/P6) but chose not to. Reasons:

```text
1. P1 + P2 + P3 are pure surface improvements with zero risk
   (no frozenset shift, no test impact, no consumer breakage)

2. P4 (renames) requires consumer-side import update
   - this is a deliberate baseline shift, deserving its own PR

3. P5 (sub-module) is structurally large
   - ragcore is still small enough that top-level is comfortable;
     premature reorganization

4. P6 (Engine.claim_report) reverses a PR32-V §44.11 OOS decision
   - reversing an explicit OOS line needs a sub-decision, not a
     surface cleanup PR

The PR33-M value is "we now have a safe-cleanup precedent and a
documented audit framework." Future renames / restructures /
convenience methods inherit the §45 boundary categorization.
```

---

## Final meaning

PR33-M closes the surface-cleanup precedent.

```text
PR27-P  call boundary       (how to call)
PR30-P  read boundary       (how to read)
PR31-S  usage recipe        (what order)
PR32-V  report surface      (what shape)
PR33-M  method surface      (audit + safe cleanup, no semantic change)
```

Before PR33-M, every PR either:

```text
- refined modifier formulas (PR23-M / PR24-N / PR26-R / PR29-R)
- locked boundaries via docs + tests (PR27-P / PR28-O / PR30-P / PR31-S / PR32-V)
- never touched the public surface as a cleanup objective
```

After PR33-M, the framework has:

```text
- a documented audit framework (§45)
- a safe-cleanup precedent (Scope A executed)
- explicit deferral list (P4 / P5 / P6 + sub-decision requirement)
- 0 no-docstring public methods
- a grouped __all__ for AI readability
- corrected narrative count (48 symbols, agreeing with code)
```

The Engine remains a domain-light judgment core.
The consumer remains responsible for assembly and rendering.
The modifier values remain internal.
The frozen method surface baseline remains unchanged.

Core closing statement (locked by user 2026-05-21):

```text
PR33-M did not shift the frozen method surface baseline.
It cleaned the public surface by documenting existing methods,
correcting the 48-symbol count, and grouping __all__ without
changing Engine judgment semantics.
```

---

## Next candidates after PR33-M

User-locked priority order remains:

```text
1순위 (now next): PR34-O    Optimization
2순위:            V-cerberus thin adapter (다른 repo)
3순위:            P4 rename PR (separate, requires baseline shift sub-decision)
                  P5 ragcore.trace sub-module PR
                  P6 Engine.claim_report PR
4순위:            R-fpr / G / J / Q / S-extension (사용자 명시 승인 필요)
```

PR34-O Optimization is the next natural step:

```text
- internal refactoring, performance / dedup
- engine.py internal helpers consolidation
- private constant naming consistency
- profiling-driven hot path tuning
- external API surface invariant (PR31-S + PR32-V frozensets preserved)
```

P4 / P5 / P6 each become standalone future PRs with explicit baseline shift documentation if and when the user authorizes them.

Sub-decision D, AF, and the §42 / §43 / §44 / §45 letter-code namespaces continue to constrain future PRs.
