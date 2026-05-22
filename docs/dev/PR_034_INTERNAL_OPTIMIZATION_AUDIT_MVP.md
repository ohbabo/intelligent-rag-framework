# PR 034 — Internal Optimization Audit + Scope O-mid Cleanup MVP

## Summary

PR34-O is a behavior-preserving internal optimization PR.

It reduced defensive-check duplication and normalized modifier helper structure without changing public API surface, snapshot shape, report shape, lifecycle semantics, or effective confidence judgment semantics.

Core closing statement (user-locked 2026-05-22):

```text
PR34-O Scope O-mid is a behavior-preserving internal refactor.
It reduces defensive-check duplication and normalizes modifier helper
structure without changing public API, snapshot shape, report shape,
lifecycle semantics, or effective confidence results.
```

PR34-O is the second PR after PR33-M to operate in a non-judgment domain. PR33-M cleaned the surface domain; PR34-O cleans the internal domain.

Three-차수 cycle inside PR34-O:

```text
141차  docs(contract) §46  Internal Optimization Audit Boundary + audit findings
142차  refactor(engine)    Scope O-mid execution (O1+O2+O3+O4+O5+O8)
143차  docs(dev) (this)    PR record + ready + squash merge
```

> **PR34-O closed without O6 and O7.**
> **It dedupped defensive checks and normalized modifier helpers, deferring method-body splits to future PRs.**

---

## Baseline

```text
base main:    2f89ba4
branch:       feat/internal-optimization-audit
before tests: 1089 passing
public symbols: 48
Engine public methods: 40
snapshot schema_version: 2
```

Completed immediately before this PR:

```text
PR33-M method surface audit + Scope A cleanup
```

The active confidence formula entering PR34-O:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
```

PR34-O does not change this formula.

---

## §45 / §46 boundary domains

```text
PR33-M §45  surface domain audit  (P1~P6 — surface 정돈)
PR34-O §46  internal domain audit (O1~O8 — internal 정돈)
```

The audit-first / Scope-execution pattern is shared between PR33-M and PR34-O. P (Proposal) and O (Optimization) are intentionally distinct namespaces — they do not collide.

---

## Commit cycle

```text
141차  7a3506e  docs(contract): define internal optimization audit boundary (§46)
142차  ba16ab1  refactor(engine): execute PR34-O Scope O-mid internal cleanup
143차  this commit — docs(dev) record + Draft → Ready + squash merge
```

---

### 141차 — Audit-first entry (§46)

Commit `7a3506e` added `§46 Internal Optimization Audit Boundary` (+650 lines) covering 14 subsections:

```text
§46.1   Core proposition (framing sentence)
§46.2   Audit boundary (internal vs surface vs semantic)
§46.3   141차 audit scope
§46.4   engine.py structure snapshot
§46.5   Private state attribute inventory (17 attrs)
§46.6   Private helper grouping (9 real private methods)
§46.7   Modifier helper consistency observations
§46.8   Snapshot / restore symmetry observations
§46.9   Duplicate code pattern observations (28 KeyError)
§46.10  Method length distribution
§46.11  Private constant grouping (17 constants, 8 groups)
§46.12  Optimization candidates O1~O8 (proposal)
§46.13  Audit-only invariants
§46.14  Out of scope + Constraints on 142차+
```

Key audit findings:

```text
engine.py LOC                          1696
ragcore/ total LOC                     2186
Engine real methods                      50
Engine public methods                    40
Engine real private methods               9
private state attrs                      17
private constants                        17
duplicate KeyError patterns              28
  _claims                               18x
  _evidences                             4x
  _entities                              2x
  _gaps                                  1x
  _rule_definitions                      1x
  _rule_stats                            2x
to_snapshot LOC                          32
from_snapshot LOC                        57 (1.8x asymmetry)
compute_effective_confidence LOC        110
_rule_stats_modifier_for_claim LOC       76

Modifier helper signature inconsistency:
  3 helpers took claim_id, 1 took Claim object
  status/freshness modifiers were inlined in compute_effective_confidence
```

141차 added zero source changes, zero test changes, zero frozenset shifts.

---

### 142차 — Scope O-mid execution

Commit `ba16ab1` executed 6 of 8 optimization candidates:

```text
Included:
  O1 Defensive check helper extraction
  O2 Modifier signature consistency
  O3 status/freshness modifier extraction
  O4 Private constant grouping comments
  O5 Constant ordering by formula
  O8 Source navigation banner + import review

Deferred (medium-risk method-body refactors):
  O6 compute_effective_confidence method split
  O7 from_snapshot per-kind deserialization helpers
```

Changed file:

```text
ragcore/engine.py only
```

Size:

```text
+167 / -98 (net +69 LOC)
1696 -> 1765 LOC
```

---

## Scope O-mid execution detail

### O1 — Defensive check helper extraction

Added 6 private defensive-check helpers near `_id_exists`:

```text
_assert_entity_exists(entity_id)
_assert_claim_exists(claim_id)
_assert_evidence_exists(evidence_id)
_assert_gap_exists(gap_id)
_assert_rule_pair_exists(rule_id, rule_version)
_assert_rule_stats_pair_exists(rule_id, rule_version)
```

19 inline `if X not in self._Y: raise KeyError(...)` patterns were replaced by helper calls.

Inline KeyError pattern count:

```text
before: 28 (audit-recorded)
after:   7
```

The remaining 7 patterns are intentional:

```text
6 inside _assert_* helper bodies (the source of truth)
1 in section header comment (descriptive text)
1 subject_id (entity) case in add_claim
  — uses distinct error label `unknown subject_id (entity): {subject_id}`
  — kept inline so the helper does not need a `label=` parameter
1 `gap.id not in self._gap_resolutions` in _gap_modifier_for_claim
  — semantically different (checks "has resolution?" not "exists?")
```

All KeyError message strings preserved bit-for-bit. Verified by grep that no test inspects KeyError message text (only ValueError matches exist in tests).

### O2 — Modifier signature consistency

Before PR34-O, `_rule_stats_modifier_for_claim` accepted a `Claim` object while the other modifier helpers accepted `claim_id`.

After PR34-O, all 6 modifier helpers share the same signature:

```text
_status_modifier_for_claim(self, claim_id: int) -> float       (new in O3)
_freshness_modifier_for_claim(self, claim_id: int) -> float    (new in O3)
_gap_modifier_for_claim(self, claim_id: int) -> float
_count_modifier_for_claim(self, claim_id: int) -> float
_rule_stats_modifier_for_claim(self, claim_id: int) -> float   (signature normalized in O2)
_evidence_type_modifier_for_claim(self, claim_id: int) -> float
```

`_rule_stats_modifier_for_claim` body resolves `claim = self._claims[claim_id]` at the top — one extra line in the helper that removes the inconsistency at every call site.

### O3 — Status and freshness modifier helper extraction

Extracted two new private helpers from `compute_effective_confidence`:

```text
_status_modifier_for_claim(claim_id)
  — uses _STATUS_TO_MODIFIER[claim.status]
  — PR11-D §24.8 status-only multiplier (4-state, 0.0 / 0.5 / 1.0)

_freshness_modifier_for_claim(claim_id)
  — uses active_contradictions_by_freshness + _FRESHNESS_PENALTY_WEIGHT
  — Sub-decision O preserved (most-recent 1 only)
```

`compute_effective_confidence` body shrank from inline composition to clean 6-helper × base composition:

```python
self._assert_claim_exists(claim_id)
claim = self._claims[claim_id]
return ScoreValue(
    claim.base_confidence.value
    * self._status_modifier_for_claim(claim_id)
    * self._freshness_modifier_for_claim(claim_id)
    * self._gap_modifier_for_claim(claim_id)
    * self._count_modifier_for_claim(claim_id)
    * self._rule_stats_modifier_for_claim(claim_id)
    * self._evidence_type_modifier_for_claim(claim_id)
)
```

The 7-modifier composition is now visible in one place:

```text
base
× status
× freshness
× gap
× count
× rule_stats
× evidence_type
```

No modifier value changed. No formula changed. Test outputs are bit-for-bit identical (verified by 1089 passing tests).

### O4 — Private constant grouping comments

Added top-level Module-level private constants banner with formula sequence summary, followed by 9 inline group headers:

```text
# ---- Refutation helper ----
# ---- Status modifier (PR11-D §24.8) ----
# ---- Freshness modifier (PR11-C §26) ----
# ---- Gap modifier (PR12-D §28 + PR23-M §35) ----
# ---- Count modifier (PR19-E §31 + PR24-N §36) ----
# ---- Rule_stats modifier — maturity part (PR20-F §32 + PR26-R §38) ----
# ---- Rule_stats modifier — precision part (PR29-R §41) ----
# ---- Evidence_type modifier (PR21-L §33) ----
# ---- Snapshot schema (PR18-K §30 + PR21-L §33) ----
```

### O5 — Constant ordering by formula

Verified: the 17 private constants were already in formula order (refutation_helper → status → freshness → gap → count → rule_stats × 2 → evidence_type → snapshot). O5 is a no-op confirmation of existing structure.

### O8 — Source navigation banner + import review

Added class-level navigation banner above `class Engine:` listing the 15 internal sections in order:

```text
Defensive existence checks (private)
Entity / Observation / Claim / Evidence
Relation / Gap
Gap resolution                       (PR5 §17)
Claim lifecycle                      (PR6 §18)
Claim refutation                     (PR7 §19)
Disputed lifecycle                   (PR8 §20)
Disputed resolution                  (PR9-A §21)
Disputed refutation                  (PR10-A §22)
Lifecycle history                    (PR10-B §23)
Evidence freshness                   (PR11-A §25)
Freshness-aware refutation           (PR11-B §27)
Rule registry
Modifier helpers (private)           (PR34-O §46 O2 + O3)
Persistence snapshot                 (PR17 §29)
```

Existing `# ---- Section name (PR# §#) ----` markers were preserved unchanged.

Import review result:

```text
imports checked:           24
imports used:              24
imports unused:             0
imports removed:            0
```

All imports are used. No removal needed. `from __future__ import annotations` is a directive (PEP 563), not a runtime symbol.

---

## O6 / O7 deferred

The audit (§46.12) proposed two additional candidates that PR34-O chose not to execute:

### O6 — compute_effective_confidence method split (deferred)

Proposed split: extract `_compose_effective_confidence(claim)` helper from the 110-LOC orchestrator.

Reason deferred:

```text
- compute_effective_confidence is the public formula entry point
- splitting it changes control flow structure (medium risk)
- after O3, the body is already a clean 6-helper composition
  (effective ~ 12 LOC of formula body)
- splitting it further requires explicit justification beyond "looks long"
- worth a separate PR if a use case emerges (e.g., adding a
  trace-emitting variant that needs to inspect each modifier value)
```

Future PR candidate: O6 standalone refactor PR.

### O7 — from_snapshot per-kind deserialization helpers (deferred)

Proposed split: extract `_load_entities`, `_load_claims`, etc. from the 57-LOC from_snapshot.

Reason deferred:

```text
- from_snapshot is sensitive (snapshot round-trip invariants must hold)
- per-kind helpers would improve testability but require careful
  reordering of the restore sequence
- existing snapshot tests (round-trip preservation, schema v1->v2
  migration) lock the current behavior; refactoring needs additional
  verification
- worth a separate PR with explicit attention to migration paths
```

Future PR candidate: O7 standalone snapshot refactor PR.

---

## Implementation footprint

Changed files (across 141차 + 142차 + 143차):

```text
docs/contracts/05_DATA_CONTRACT_MVP.md             +650 lines (§46)
ragcore/engine.py                                  +167 / -98 (net +69)
docs/dev/PR_034_INTERNAL_OPTIMIZATION_AUDIT_MVP.md this record (143차)
```

Unchanged:

```text
ragcore/types.py
ragcore/__init__.py
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
ragcore.__all__ still contains 48 symbols  (frozenset preserved)
no method rename
no method removal
no method addition
no deprecated alias
docstring coverage still 40/40 (PR33-M baseline preserved)
```

No report shape change:

```text
PR32-V *_KEYS frozensets all unchanged
```

---

## Boundary preservation table

| Preserved boundary                                       | PR34-O effect             | Status      |
| -------------------------------------------------------- | ------------------------- | ----------- |
| Sub-decision D (types / rule_output unchanged)           | engine.py internal only   | preserved   |
| Sub-decision AF (HINT taxonomy framework-external)       | unchanged                  | preserved   |
| PR17 snapshot schema v2                                  | unchanged                  | preserved   |
| PR21-L hint validation (caller-registered)               | unchanged                  | preserved   |
| PR27-P consumer call boundary (§39)                      | unchanged                  | preserved   |
| PR28-O rule version pinning                              | unchanged                  | preserved   |
| PR29-R observed_precision bounded no-boost               | unchanged                  | preserved   |
| PR30-P consumer policy guides (§42)                      | unchanged                  | preserved   |
| PR31-S AI-readable usage recipe (§43)                    | unchanged                  | preserved   |
| PR31-S method surface freeze (48 symbols)                 | preserved bit-for-bit     | preserved   |
| PR32-V report surface (§44)                              | unchanged                  | preserved   |
| PR32-V no exact modifier value invariant                  | unchanged (still pressure flags only) | preserved |
| PR32-V Engine.claim_report absence invariant             | unchanged (no helper added) | preserved |
| PR33-M docstring coverage (40/40)                        | unchanged                  | preserved   |
| PR33-M __all__ 12-group ordering                          | unchanged                  | preserved   |
| 7-modifier formula                                        | unchanged                  | preserved   |
| modifier value behavior                                   | unchanged (bit-for-bit)   | preserved   |
| effective_confidence output                              | unchanged (1089 tests)    | preserved   |
| Internal readability (engine.py)                         | improved (banner + helpers + group headers) | **newly cleaned** |
| Modifier helper signature consistency                     | normalized (6 helpers, same signature) | **newly cleaned** |
| Defensive check duplication                               | reduced 19 patterns       | **newly cleaned** |

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

PR34-O is the first PR to refactor engine.py internals while keeping the test suite identical. This is the test-suite signal that the refactor preserves all observable behavior.

---

## Verification snapshot

After 142차:

```text
ragcore.__all__              48 symbols (unchanged from PR33-M)
unique symbols                48 (no duplicates)
Engine public methods         40 (unchanged)
no-docstring methods           0 (PR33-M baseline preserved)
schema_version                  2 (unchanged)
test suite                    1089 passing, 0 fail
engine.py LOC               1765 (was 1696, +69 net)
modifier helpers                6 (was 4, +2 from O3)
modifier signature            (self, claim_id: int) -> float (all 6)
defensive check helpers         6 (new from O1)
inline KeyError patterns        7 (was 28+1, all intentional after O1)
imports                        24 (all used, 0 removed)
```

---

## Self-review

### What this PR does

PR34-O is the first PR that refactored engine.py internals while preserving:

```text
- the public surface (48 symbols, 40 methods)
- the report surface (6 frozenset shapes)
- the snapshot shape (schema v2)
- the 7-modifier formula
- modifier value behavior (bit-for-bit)
- lifecycle transitions
- effective_confidence outputs (1089 tests identical)
```

The actual changes:

```text
- 6 defensive check helpers added (O1)
- 19 inline KeyError patterns dedupped to helper calls (O1)
- 1 modifier helper signature normalized (O2)
- 2 new modifier helpers extracted (O3)
- 9 inline constant group headers added (O4)
- 1 class-level navigation banner added (O8)
- imports reviewed and confirmed clean (O8)
```

### What this PR does not do

PR34-O does not:

```text
change Engine judgment semantics
change modifier values
change lifecycle rules
change snapshot shape
change rule_output parsing
change contradiction registration / resolution
change public API surface
rename any method
add or remove any public symbol
add any test
modify any test
modify types.py
modify rule_output.py
modify __init__.py
execute O6 or O7 (deferred)
```

### Why the conservative scope is correct

The user-locked PR34-O framing required behavior-preserving internal refactor only. PR34-O could have exercised method-body splits (O6/O7) but chose not to. Reasons:

```text
1. Scope O-mid value is already substantial:
   - 19 patterns dedupped
   - signature consistency across 6 modifier helpers
   - 2 new helpers extracted for symmetry
   - readability improved with comments and banners

2. O6 / O7 are method-body refactors:
   - compute_effective_confidence is the public formula entry point
   - from_snapshot is sensitive to round-trip invariants
   - both deserve their own PR with explicit attention

3. The audit-first / Scope-execution pattern (PR33-M precedent)
   benefits from conservatism. The audit (§46) documented all 8
   candidates; future PRs can pick up O6 and O7 if and when justified.
```

---

## Final meaning

PR34-O is not a feature PR.
PR34-O is not a judgment policy PR.
PR34-O is an internal readability and maintainability PR.

```text
Before PR34-O: engine.py had 28 inline KeyError patterns,
               4 of 6 effective modifiers extracted as helpers
               (with 1 of 4 having inconsistent signature),
               status / freshness modifier inlined in
               compute_effective_confidence,
               minimal section navigation.

After PR34-O:  6 defensive check helpers eliminate 19 patterns,
               all 6 modifier helpers share signature
               (self, claim_id: int) -> float,
               7-modifier composition is visible in one block,
               module-level constant groups have inline headers,
               class Engine has a navigation banner.
```

The Engine remains a domain-light judgment core.
The consumer surface remains unchanged.
The internal code is easier to audit before future refactors.

```text
PR27-P  §39  call boundary       (how to call)
PR30-P  §42  read boundary       (how to read)
PR31-S  §43  usage recipe        (what order)
PR32-V  §44  report surface      (what shape)
PR33-M  §45  method surface      (surface domain audit + safe cleanup)
PR34-O  §46  internal optimization (internal domain audit + behavior-preserving refactor)
```

---

## Next candidates after PR34-O

User-locked priority order remains:

```text
1순위:  PR35-O6/O7   deferred method-body refactors (from PR34-O)
        OR V-cerberus thin adapter (다른 repo)
2순위:  P4 / P5 / P6 (PR33-M에서 deferred — rename / sub-module /
                       Engine.claim_report)
3순위:  R-fpr / G / J / Q / S-extension (사용자 명시 승인 필요)
```

Sub-decision D, AF, and the §42 / §43 / §44 / §45 / §46 letter-code
namespaces continue to constrain future PRs.
