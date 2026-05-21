# PR 032 — Report Surface MVP

## Summary

PR32-V documents and locks the canonical consumer-side report shapes that an external consumer (human-facing report, AI-readable summary, JSON dump) should assemble from the existing public Engine surface.

Core proposition:

```text
PR27-P §39  call boundary    (how to call the Engine)
PR30-P §42  read boundary    (how to read Engine outputs)
PR31-S §43  usage recipe     (what order to call methods in)
PR32-V §44  report surface   (what shape the result should take)
```

§43 answered "in what order should I call the Engine."
§44 answers "in what shape should I render the result."

This PR does not add a new Engine feature, a new public API, an `Engine.claim_report` / `Engine.report` / `Engine.summary` method, a method rename, or a snapshot schema change. It documents the canonical report shape that an external consumer can assemble using only the existing public surface, and locks the shape as executable frozenset invariants.

> **PR32-V did not add report helper methods.**
> **It locked the report shape boundary that an external consumer can build using existing public APIs.**

---

## Why PR32-V after PR31-S

After PR31-S, the framework had:

```text
PR27-P  documented call boundary  (you CAN call in this order)
PR30-P  documented read boundary  (this is what the output means)
PR31-S  documented usage recipe   (these are canonical scenarios)
PR31-S  method surface freeze     (49 symbols frozen at PR30-P main 60bf492)
```

What was missing was the **visible / reportable surface**. An AI consumer reading PR31-S could see the recipes but had to invent its own report shape — leading to drift across consumers (Cerberus adapter, CLI wrapper, web backend, JSON dump).

PR32-V closes that gap. It enumerates six canonical report shapes and locks each as a deterministic frozenset key set:

```text
A. claim_summary
B. effective_breakdown
C. lifecycle
D. evidence_contradiction
E. rule_pinning
F. snapshot_metadata
```

Each shape is assemblable using only public APIs that already existed after PR1~PR30-P.

User direction (sequence locking the PR32-V track, 2026-05-21):

```text
1순위: Visual/report surface         ← PR32-V (이 PR)
2순위: Method surface 정돈 / API 사용감 검토
3순위: Optimization
4순위: V-cerberus thin adapter
```

Reason for preferring PR32-V before V-cerberus:

```text
V-cerberus를 먼저 가면 adapter가 임시 report shape를 만들고,
나중에 framework가 다른 report shape를 잠그면 충돌.
report shape를 framework 측에서 먼저 잠그고
adapter가 그걸 따르게 하는 순서가 안전.
```

---

## Baseline

Before PR32-V:

```text
main:  9900883
tests: 1062 passing, 0 fail
```

Completed immediately before this PR:

```text
PR31-S AI-readable usage recipe MVP
                (+ method surface freeze)
```

The active confidence formula entering PR32-V:

```text
effective = base
          × status
          × freshness
          × gap
          × count
          × rule_stats
          × evidence_type
```

PR32-V does not change this formula.

---

## §44 boundary category letter codes

§44 introduces a new boundary category namespace distinct from §42 A~H (read-policy categories) and §43 A~H (usage-recipe categories). §44 codes are report-shape categories.

| Category | Boundary                                       | Contract section |
| -------- | ---------------------------------------------- | ---------------- |
| A        | claim_summary report shape boundary            | §44.3            |
| B        | effective_breakdown report shape boundary      | §44.4            |
| C        | lifecycle report shape boundary                | §44.5            |
| D        | evidence_contradiction report shape boundary   | §44.6            |
| E        | rule_pinning report shape boundary             | §44.7            |
| F        | snapshot_metadata report shape boundary        | §44.8            |
| G        | report assembly mental model boundary          | §44.9            |
| H        | OOS / no API change boundary                   | §44.11           |

§42 A~H, §43 A~H, and §44 A~H are three intentionally separate namespaces.

---

## §44 13 subsections

§44 was added to `docs/contracts/05_DATA_CONTRACT_MVP.md` (+640 lines in 134차, plus 1-character typo fix in 135차):

```text
§44.1   Core proposition
§44.2   Report shape overview
§44.3   Shape A — claim_summary             (8 keys)
§44.4   Shape B — effective_breakdown        (9 keys, 6 pressure flags)
§44.5   Shape C — lifecycle                  (5 keys per event)
§44.6   Shape D — evidence_contradiction     (5 keys)
§44.7   Shape E — rule_pinning               (8 keys)
§44.8   Shape F — snapshot_metadata          (8 keys, schema_version=2)
§44.9   Report assembly recipe
§44.10  AI consumer report rendering checklist (10 items)
§44.11  Out of scope
§44.12  Invariants (10 report shape invariants for 135차 test-first)
§44.13  Constraints on 135/137차 (3-commit cycle, 136차 skip)
```

---

## Pressure flag design (key decision)

§44.4 Shape B (`effective_breakdown`) exposes 6 boolean pressure flags instead of exact modifier values:

```text
has_status_attenuation       (status in DISPUTED / REFUTED)
has_unresolved_gaps          (any gap without resolution)
has_active_contradictions    (active_contradictions_for_claim non-empty)
has_repeated_pressure        (active_contradictions_for_claim length >= 2)
has_rule_binding             (created_by_rule != 0)
has_hint_evidence            (any evidence.type in registered hint set)
```

Forbidden in §44.4:

```text
status_modifier_value
freshness_modifier_value
gap_modifier_value
count_modifier_value
rule_stats_modifier_value
evidence_type_modifier_value
```

Why pressure flags, not modifier values:

```text
Modifier refinement PRs (PR23-M / PR24-N / PR26-R / PR29-R) have
already shifted modifier values multiple times:
  - gap modifier: binary → tier (count-based, floor 0.7)
  - count modifier: binary → continuous (avg strength, floor 0.75)
  - rule_stats: binary → continuous maturity (floor 0.8)
  - rule_stats × precision_modifier (range [0.72, 1.0])

If consumer report shape exposed exact modifier values, every
modifier refinement PR would break consumer rendering. The
pressure surface ("yes, gap pressure exists") is stable across
all four refinements; the exact value (0.7, 0.85, etc.) is not.

Pressure flags are forward-compatible. Exact modifier values
are not.
```

Sub-decision (PR32-V scope):

```text
Pressure flags belong in the public report surface.
Exact modifier values stay internal to the Engine formula.
```

---

## Commits

### 134차 — docs(contract): define report surface MVP (§44)

Commit:

```text
6fda976
```

Added:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md §44
```

Section title:

```text
§44 Report Surface MVP
```

Six canonical report shapes documented (A~F), each with:

```text
Purpose
Required keys (name + type)
Assembly source (which public methods produce the value)
Forbidden keys (what must NOT appear)
Frozenset key set (test invariant)
Meaning / notes
```

Report assembly recipe documented in §44.9 — describes how a consumer combines multiple shapes into a single claim report, while emphasizing that the framework does not provide `Engine.claim_report`.

AI consumer rendering checklist documented in §44.10 with 10 items linking back to §42 / §43 / §44 boundaries.

PR32-V explicitly kept the following out of scope:

```text
new public API
Engine.claim_report / Engine.report / Engine.summary / Engine.breakdown
method renaming
deprecated alias
__all__ change
new enum
new modifier
new lifecycle state
file IO wrapper
rendering format (markdown / HTML / TUI / TTY color)
localization
exact modifier values in any shape
truth probability / verdict / severity fields
wall-clock timestamps
false_positive_rate / confirmed_true_count / confirmed_false_count exposure
rule quality verdict
LLM-generated narrative summary
visualization library binding
```

---

### 135차 — test(core): lock report surface invariants

Commit:

```text
3e26fad
```

Added:

```text
tests/test_engine_report_surface.py
```

Also corrected in same commit:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md  §44.12 invariant 5
  "(9 keys)" -> "(8 keys)"
```

This is a one-character copy-paste typo correction tied to 135차 test reality (Shape E §44.7 spec listed 8 fields; §44.12 invariant 5 mis-stated 9). Not a spec change — Shape E always had 8 fields.

Size:

```text
767 lines
27 tests
9 classes
```

Result:

```text
1089 passing, 0 fail
```

Expected pattern:

```text
all pass
```

This was intentional.

PR32-V is not a test-first implementation PR that expects failing tests.

It is a boundary-locking PR that verifies the existing public Engine surface already supports the §44 canonical report shapes through consumer-side assembly.

Test class distribution:

| Class                                   | Tests | §44 mapping       | Category |
| --------------------------------------- | ----: | ----------------- | -------- |
| `TestReportShapeClaimSummary`           |     3 | §44.3             | A        |
| `TestReportShapeEffectiveBreakdown`     |     4 | §44.4             | B        |
| `TestReportShapeLifecycle`              |     3 | §44.5             | C        |
| `TestReportShapeEvidenceContradiction`  |     3 | §44.6             | D        |
| `TestReportShapeRulePinning`            |     4 | §44.7             | E        |
| `TestReportShapeSnapshotMetadata`       |     4 | §44.8             | F        |
| `TestReportAssemblyPurity`              |     2 | §44.9             | G        |
| `TestReportSurfaceNoEngineHelper`       |     2 | §44.12 inv. 8     | H        |
| `TestReportSurfacePublicMethodFreeze`   |     2 | §44.12 inv. 10    | H        |

Total:

```text
27 tests
```

---

## 135차 locked invariants

### Six frozenset key sets

Each shape's required key set is locked as a module-level frozenset constant in the test file:

```text
CLAIM_SUMMARY_KEYS                       8 keys
EFFECTIVE_BREAKDOWN_KEYS                 9 keys (6 boolean pressure flags)
LIFECYCLE_EVENT_KEYS                     5 keys per event
EVIDENCE_CONTRADICTION_KEYS              5 keys
RULE_PINNING_KEYS                        8 keys
SNAPSHOT_METADATA_KEYS                   8 keys
```

Per-shape `_FORBIDDEN_KEYS_*` frozensets capture the §44.3 ~ §44.8 forbidden lists and assert `isdisjoint` against each assembled dict.

### Consumer-side assembly helpers (test module only)

Six `assemble_*` helpers in the test module — NOT in `ragcore`:

```text
assemble_claim_summary(engine, claim_id) -> dict
assemble_effective_breakdown(engine, claim_id) -> dict
assemble_lifecycle(engine, claim_id) -> list[dict]
assemble_evidence_contradiction(engine, claim_id) -> dict
assemble_rule_pinning(engine, claim_id) -> dict
assemble_snapshot_metadata(engine) -> dict
```

All six use only the existing public read-side APIs from PR1~PR30-P:

```text
get_claim, evidences_for_claim, gaps_for_claim, gap_resolution
contradictions_for_claim, active_contradictions_for_claim
resolved_contradictions_for_claim
claim_lifecycle_history
get_rule, get_rule_stats
compute_effective_confidence
to_snapshot
```

No private attribute access. No internal helper. No modifier value extraction.

### Category A — claim_summary shape

Locked invariants:

```text
frozenset(summary.keys()) == CLAIM_SUMMARY_KEYS
forbidden keys absent (truth_probability / verdict / severity / fixed)
status and effective_confidence are separate signals:
  CONFIRMED status with effective_confidence == 0.72 (rule_stats × base)
  CONFIRMED status with effective_confidence != 1.0
```

### Category B — effective_breakdown shape

Locked invariants:

```text
frozenset(breakdown.keys()) == EFFECTIVE_BREAKDOWN_KEYS
6 pressure flags are all isinstance(x, bool)
DISPUTED claim has has_status_attenuation=True and has_active_contradictions=True
no modifier value key appears (status_modifier_value / gap_modifier_value / etc.)
```

### Category C — lifecycle shape

Locked invariants:

```text
each event dict in list has frozenset(keys) == LIFECYCLE_EVENT_KEYS
pristine candidate (no lifecycle transition) -> empty list
no wall-clock timestamp / reviewer / review_note key
```

### Category D — evidence_contradiction shape

Locked invariants:

```text
frozenset(counts.keys()) == EVIDENCE_CONTRADICTION_KEYS
disputed claim: evidence_count=1, contradiction_count=1,
                active=1, resolved=0
no evidence_strength_sum / contradiction_strength_sum /
   evidence_ids / contradiction_ids
```

### Category E — rule_pinning shape

Locked invariants:

```text
frozenset(pinning.keys()) == RULE_PINNING_KEYS
rule_id=0 path:
  has_rule_binding=False
  rule_maturity=None, firing_count=0,
  observed_precision=None, prior_confidence=None
rule binding path:
  rule_id=RULE_ID, rule_version=RULE_VERSION
  has_rule_binding=True
  firing_count=2, observed_precision=0.5, prior_confidence=0.8
no false_positive_rate / confirmed_true_count /
   confirmed_false_count / rule_quality_score
```

### Category F — snapshot_metadata shape

Locked invariants:

```text
frozenset(meta.keys()) == SNAPSHOT_METADATA_KEYS
schema_version == 2 (PR17 / PR21-L / §32 / §42.6)
non-trivial engine state counts (claims=1, evidences=1, gaps=1,
                                  rules=1, rule_stats=1,
                                  hint_evidence_types=1,
                                  lifecycle_events=1)
no snapshot_size_bytes / file_path / saved_at /
   schema_migration_log
```

### Category G — assembly purity

Locked invariants:

```text
running all six assemblers does not mutate engine.to_snapshot()
repeated assembly produces identical output (tuple equality)
```

### Category H — no Engine report helper + method surface freeze

Locked invariants:

```text
not hasattr(Engine, "claim_report")
not hasattr(Engine, "report_claim")
not hasattr(Engine, "build_report")
not hasattr(Engine, "report")
not hasattr(Engine, "summary")
not hasattr(Engine, "breakdown")
not hasattr(Engine, "render")
not hasattr(Engine, "report_surface")

"claim_report" / "report_claim" / "build_report" / "report" /
"summary" / "breakdown" / "render" / "report_surface"
   not in ragcore.__all__

frozenset(ragcore.__all__) == _PR30_BASELINE_PUBLIC_SYMBOLS
   (the PR30-P main 60bf492 frozenset of 49 symbols
    locked by PR31-S)
```

---

## Consumer-side assembly helper principle

PR32-V locks an important principle: **the framework does not assemble report dicts; the consumer does.**

```text
WHAT framework provides:
  - public read-side APIs (get_claim, evidences_for_claim, etc.)
  - the documented frozen key set for each shape (§44.3 ~ §44.8)
  - the documented forbidden key list per shape
  - the documented assembly source per shape

WHAT framework does NOT provide:
  - Engine.claim_report(claim_id) -> dict
  - Engine.summary(claim_id) -> dict
  - Engine.build_report(claim_id) -> dict
  - any other report-producing method

WHAT consumer must do:
  - call the documented read-side APIs
  - assemble values into a dict matching §44 frozen key set
  - render the dict (markdown / HTML / JSON / TUI) on their own
```

Rationale:

```text
Adding Engine.claim_report would violate Sub-decision D
(engine.py change 0) and PR31-S method surface freeze
(_PR30_BASELINE_PUBLIC_SYMBOLS frozenset).

PR32-V is the shape-locking layer. If thin convenience methods
are ever needed, they belong in PR33-M (method surface 정리)
as an intentional surface expansion with explicit baseline shift.
```

This preserves all three external boundaries (call / read / usage recipe) without changing the public symbol count.

---

## 136차 skipped intentionally

136차 implementation was skipped.

Reason:

```text
PR32-V is a boundary spec PR, not an Engine feature PR.
```

There was no missing Engine behavior to implement after 135차.

The 135차 tests passed immediately because PR1~PR31-S had already produced the required public Engine surface for the §44 report shapes.

Skipping 136차 prevents unnecessary code churn.

This follows the established 3-commit cycle for boundary spec PRs:

```text
PR27-P  114차 / 115차 / 116차 (skip) / 117차
PR28-O  118차 / 119차 / 120차 (skip) / 121차
PR30-P  126차 / 127차 / 128차 (skip) / 129차
PR31-S  130차 / 131차 / 132차 (skip) / 133차
PR32-V  134차 / 135차 / 136차 (skip) / 137차
```

---

## Implementation footprint

Changed files:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md
tests/test_engine_report_surface.py
docs/dev/PR_032_REPORT_SURFACE_MVP.md
```

No changes:

```text
ragcore/engine.py
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
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
ragcore.__all__ identical to PR30-P main 60bf492 frozenset
no method rename
no method removal
no method addition (no Engine.claim_report / report / summary / etc.)
no deprecated alias
```

No Evidence.type taxonomy ownership change:

```text
framework still does not own Evidence.type meaning
no built-in HINT enum
```

---

## §44.12 invariant 5 typo correction (135차)

134차 docs(contract) §44.12 invariant 5 originally read:

```text
Shape E frozenset — rule_pinning(claim_id).keys() == RULE_PINNING_KEYS (9 keys).
```

§44.7 Shape E spec listed 8 fields:

```text
claim_id, rule_id, rule_version, has_rule_binding,
rule_maturity, firing_count, observed_precision, prior_confidence
```

The "(9 keys)" wording was a copy-paste error.

135차 commit corrected the invariant wording to "(8 keys)" — a one-character fix. Shape E always had 8 fields. This is documented here as the only natural-expiry-style amendment in the PR32-V cycle.

---

## Test result

Final test result before merge:

```text
1089 passed, 0 failed
```

Delta:

```text
1062 -> 1089
+27 tests
```

Regression:

```text
0
```

Natural-expiry:

```text
0   (no existing test required wording / value update;
     the §44.12 fix is a typo correction, not a test change)
```

---

## Boundary preservation table

| Preserved boundary                                       | PR32-V effect                | Status      |
| -------------------------------------------------------- | ---------------------------- | ----------- |
| Sub-decision D (types / __init__ / engine / rule_output) | tests + contract only        | preserved   |
| Sub-decision AF (HINT taxonomy framework-external)       | has_hint_evidence flag       | reinforced  |
| PR17 snapshot schema v2                                  | snapshot_metadata.schema_version=2 | reinforced |
| PR21-L hint validation (caller-registered)               | has_hint_evidence from snapshot["hint_evidence_types"] | reinforced |
| PR27-P consumer call boundary (§39)                      | §44 extends three layers outward | extended  |
| PR28-O rule version pinning                              | rule_pinning shape (rule_id, rule_version) preserved | reinforced |
| PR29-R observed_precision bounded no-boost               | rule_pinning shape exposes precision, omits FPR | reinforced |
| PR30-P consumer policy guides (§42)                      | §44.10 rendering checklist links to §42 | reinforced |
| PR31-S AI-readable usage recipe (§43)                    | §44 builds on §43 recipes for assembly | extended  |
| PR31-S method surface freeze                             | _PR30_BASELINE_PUBLIC_SYMBOLS unchanged | reinforced |
| 7-modifier formula shape                                  | unchanged, modifier values hidden | preserved   |
| false_positive_rate OOS                                  | rule_pinning omits FPR        | reinforced  |
| rule quality verdict OOS                                 | rule_pinning omits quality fields | reinforced  |
| modifier value confidentiality                           | Shape B exposes pressure flags only | **newly locked** |
| Consumer-owned reporting                                  | no Engine.claim_report method | **newly locked** |

---

## Self-review

### What this PR does

PR32-V documents and locks the canonical consumer-side report shapes for the existing Engine public API.

It defines and tests how an external consumer should assemble report dicts:

```text
claim_summary through get_claim + compute_effective_confidence
effective_breakdown through pressure flag derivation from
                      get_claim, gaps_for_claim, active_contradictions_for_claim,
                      evidences_for_claim, to_snapshot
lifecycle through claim_lifecycle_history
evidence_contradiction through count of evidences_for_claim,
                      contradictions_for_claim, active/resolved contradictions
rule_pinning through get_claim + get_rule + get_rule_stats
                      (handling rule_id=0 path explicitly)
snapshot_metadata through to_snapshot top-level counts
assembly purity (no mutation, repeated assembly identical)
method surface freeze preserved (ragcore.__all__ unchanged)
```

### What this PR does not do

PR32-V does not add:

```text
new Engine method
new public symbol
method rename
deprecated alias
Engine.claim_report / report / summary / breakdown / render
calibrated truth probability
file IO
database layer
new modifier
new lifecycle state
new snapshot schema version
public HINT enum
LLM integration
tool execution
domain verdict logic
visualization helpers
rendering format
localization
```

### Why all tests pass immediately

All 27 tests pass immediately because the existing public Engine surface already supports the intended assembly pattern after PR1~PR31-S.

The purpose of the tests is not to force a new implementation.

The purpose is to prevent future changes from accidentally:

```text
- exposing exact modifier values in the consumer report surface
- adding an Engine.claim_report method silently
- changing a shape's required key set
- introducing forbidden keys (truth_probability, FPR, wall-clock, etc.)
- drifting ragcore.__all__ away from the PR30-P baseline frozenset
```

If a future PR weakens any shape — for example, by adding a method that returns a report dict, by exposing the gap modifier value, by adding a wall-clock timestamp to lifecycle events, by removing the schema_version=2 invariant — these tests fail loudly.

---

## Final meaning

PR32-V closes the fourth external boundary layer.

```text
PR27-P  call boundary    (how to call the Engine)
PR30-P  read boundary    (how to read what the Engine returns)
PR31-S  usage recipe     (what order to call methods in)
PR32-V  report surface   (what shape the result should take)
```

Together with the PR31-S method surface freeze, these four PRs form the documented external integration surface of the framework with shape-level locking.

```text
Before PR27-P:  strong internal Engine, undocumented external usage.
After PR27-P:   call boundary locked.
After PR30-P:   read boundary locked.
After PR31-S:   usage recipe locked, method surface frozen.
After PR32-V:   report surface locked, modifier values stay internal.
```

The Engine remains a domain-light judgment core.

The consumer remains responsible for assembling and rendering reports.

The modifier values remain internal — only pressure flags are exposed.

Core locked statement:

```text
The canonical consumer-side report shapes are dicts assembled
from existing public APIs. They are shapes, not new APIs.
```

---

## Next candidates after PR32-V

User-locked priority order (2026-05-21):

```text
1순위: PR33-M    Method surface 정돈 / API 사용감 검토
2순위: PR34-O    Optimization
3순위: V-cerberus thin adapter (다른 repo)
4순위: PR35+     R-fpr / G / J / Q / S-extension (사용자 명시 승인 필요)
```

Reason for PR33-M next:

```text
PR32-V locked report shape but did not touch method surface.
If thin convenience methods (Engine.claim_report etc.) are
actually wanted, PR33-M is the right place to make that
intentional with explicit baseline shift, not silently in
some other PR.
```

V-cerberus moves to slot 3 — after framework-side report surface
and method surface are both stabilized, adapter implementation
becomes a straight follow-through rather than a shape-discovery
process.

Sub-decision D, AF, and the §42 / §43 / §44 letter-code namespaces
will continue to constrain future PRs.
