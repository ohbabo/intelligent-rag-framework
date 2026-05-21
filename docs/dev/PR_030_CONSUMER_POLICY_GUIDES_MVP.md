# PR 030 — Consumer Policy Guides MVP

## Summary

PR30-P defines how external consumers should interpret Engine outputs.

Core proposition:

```text
Engine outputs are decision-support signals.
They are not domain verdicts by themselves.
```

This PR does not add new Engine behavior, new modifier, new lifecycle state, new public API, file IO, or snapshot schema change.

Instead, it documents and tests the interpretation boundary that consumers must respect when displaying or acting on:

```text
effective_confidence
lifecycle status
modifier strength
observed_precision
rule_version
snapshot
```

The Engine remains a domain-light judgment core.

The consumer remains responsible for translating Engine signals into product, report, or remediation decisions.

> **PR30-P did not add interpretation code.**
> **It locked the interpretation boundary that already existed.**

PR30-P extends PR27-P (§39 external integration spec) one layer outward:

```text
PR27-P  defines  how to call the Engine.
PR30-P  defines  how to read what the Engine returns.
```

---

## Baseline

Before PR30-P:

```text
main:  62fe975
tests: 1024 passing, 0 fail
```

Completed immediately before this PR:

```text
PR29-R observed precision modifier MVP
```

The active confidence formula entering PR30-P:

```text
effective = base
          × status
          × freshness
          × gap
          × count
          × rule_stats
          × evidence_type
```

with `rule_stats = maturity × precision` in range `[0.72, 1.0]` (PR29-R).

PR30-P does not change this formula.

---

## §42 Consumer policy boundary categories

The §42 contract groups consumer-facing interpretation rules into the following boundary categories. These replace ad-hoc sub-decision letter codes used in modifier refinement PRs.

| Category | Boundary                                            | Contract sections      |
| -------- | --------------------------------------------------- | ---------------------- |
| A        | effective_confidence display boundary               | §42.3                  |
| B        | modifier strength interpretation boundary           | §42.4 / §42.5          |
| C        | lifecycle interpretation boundary                   | §42.2 / §42.3 status   |
| D        | snapshot external storage boundary                  | §42.6                  |
| E        | rule_version display boundary                       | §42.7                  |
| F        | observed_precision wording boundary                 | §42.8                  |
| G        | consumer report boundary                            | §42.9                  |
| H        | OOS boundary                                        | §42.10 / §42.11        |

Each category translates into one or more locked test invariants in 127차.

---

## Commits

### 126차 — docs(contract): define consumer policy guides MVP (§42)

Commit:

```text
8a10b83
```

Added:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md §42
```

Section title:

```text
§42 Consumer policy guides MVP
```

Subsections:

```text
42.1  Core proposition
42.2  Lifecycle interpretation
42.3  effective_confidence display policy
42.4  Modifier strength wording
42.5  Modifier composition wording
42.6  Snapshot external storage policy
42.7  rule_version display policy
42.8  observed_precision wording policy
42.9  Consumer report boundary
42.10 No new public API
42.11 No new Engine behavior
42.12 Out of scope
```

Key locked proposition:

```text
Engine outputs are decision-support signals,
not domain verdicts by themselves.
```

Responsibility split:

```text
Framework responsibility:
  - judgment state computation
  - effective_confidence as bounded signal
  - lifecycle state transitions
  - snapshot state preservation
  - rule_version reproducibility metadata
  - observed_precision as bounded no-boost modifier

Consumer responsibility:
  - translating signal into product display
  - choosing severity / triage rules
  - rendering wording for non-expert readers
  - external persistence storage
  - audit / report schema
  - domain verdict
```

PR30-P explicitly kept the following out of scope:

```text
calibrated truth probability
file IO snapshot helpers
new lifecycle state
new modifier
new formula shape
snapshot schema bump
public HINT evidence type enum
framework-owned Evidence.type taxonomy
rule quality verdict
false_positive_rate consumption
LLM integration
report schema definition
```

---

### 127차 — test(core): lock consumer policy guide usage invariants

Commit:

```text
231bf85
```

Added:

```text
tests/test_engine_consumer_policy_guides_usage.py
```

Size:

```text
313 lines
15 tests
5 classes
```

Result:

```text
1039 passing, 0 fail
```

Expected pattern:

```text
all pass
```

This was intentional.

PR30-P is not a test-first implementation PR that expects failing tests.

It is a boundary-locking PR that verifies the existing public Engine surface already satisfies the §42 consumer interpretation policy.

Test class distribution:

| Class                                       | Tests | §42 mapping             | Boundary category |
| ------------------------------------------- | ----: | ----------------------- | ----------------- |
| `TestConsumerPolicyEffectiveConfidence`     |     4 | §42.3                   | A / C             |
| `TestConsumerPolicyObservedPrecision`       |     4 | §42.8                   | B / F / H         |
| `TestConsumerPolicySnapshot`                |     2 | §42.6                   | D                 |
| `TestConsumerPolicyRuleVersion`             |     2 | §42.7                   | E                 |
| `TestConsumerPolicyNoImplementationChange`  |     3 | §42.10 / §42.11         | H                 |

Total:

```text
15 tests
```

---

## 127차 locked invariants

### Category A — effective_confidence display boundary

The tests lock that `effective_confidence`:

```text
returns a ScoreValue signal
is bounded by domain interpretation, not absolute truth probability
does not mutate claim status when computed
```

Verified cases:

| base | status     | expected effective | meaning                                       |
| ---: | ---------- | -----------------: | --------------------------------------------- |
|  0.8 | CANDIDATE  |                0.8 | display signal preserves status              |
|  0.8 | REFUTED    |                0.0 | status dominates effective to zero           |
|  0.8 | DISPUTED   |                0.4 | status 0.5 × base 0.8 — separate signals     |
|  0.8 | CONFIRMED  |                0.8 | CONFIRMED ≠ absolute truth ≠ 1.0             |

This preserves §42.3 and the prior/base/effective three-slot separation.

---

### Category B / F — modifier strength interpretation and observed_precision wording

The tests lock that `observed_precision`:

```text
None  -> precision_modifier = 1.0   (neutral, not "no quality")
0.0   -> precision_modifier = 0.9   (bounded attenuation, not "rule is wrong")
1.0   -> precision_modifier = 1.0   (no boost above base path)
```

Verified composition (firing_count=2, maturity_modifier=1.0):

| observed_precision | expected effective | meaning                                       |
| -----------------: | -----------------: | --------------------------------------------- |
|                None |                0.64 | base 0.8 × maturity 0.8 (firing_count=0)     |
|                 0.0 |                0.72 | maturity saturated × precision floor 0.9     |
|                 1.0 |                0.80 | maturity 1.0 × precision 1.0, no boost       |

This preserves PR29-R bounded no-boost composition.

---

### Category C — lifecycle interpretation boundary

The tests lock that lifecycle status and effective_confidence:

```text
are separate signals
status is dominant for status-zero (REFUTED -> 0.0)
status is attenuating for ambiguity (DISPUTED -> ×0.5)
status preservation across compute calls
```

Consumers must not collapse status into a single number.

---

### Category D — snapshot external storage boundary

The tests lock that snapshot:

```text
schema_version remains 2
round-trip preserves status (DISPUTED preserved)
round-trip preserves created_by_rule / created_by_rule_version
round-trip preserves effective_confidence value
```

Snapshot is state preservation, not re-judgment.

This preserves PR17 (snapshot persistence philosophy) and PR21-L (v1 -> v2 migration locked).

---

### Category E — rule_version display boundary

The tests lock that `rule_version`:

```text
is retained as reproducibility metadata
does not affect effective_confidence by itself
(v1 vs v2 with identical base produces identical effective)
```

`rule_version` is identity / audit metadata, not quality.

This preserves PR28-O rule version pinning meaning.

---

### Category H — OOS boundary

The tests lock that the following are not part of public surface:

```text
Engine.save_snapshot
Engine.load_snapshot
Engine.to_file
Engine.from_file
Engine.compute_truth_probability
Engine.truth_probability
Engine.calibrated_probability
ragcore.EVIDENCE_TYPE_HINT
"EVIDENCE_TYPE_HINT" not in ragcore.__all__
```

Also verified through the FPR-ignored test:

```text
engine_a with false_positive_rate = 0.0
engine_b with false_positive_rate = 1.0
=>  identical effective_confidence
```

This preserves PR29-R §41.3 (false_positive_rate OOS) and Sub-decision AF (no framework-owned HINT taxonomy).

---

## 128차 skipped intentionally

128차 implementation was skipped.

Reason:

```text
PR30-P is a boundary spec PR, not an Engine feature PR.
```

There was no missing Engine behavior to implement after 127차.

The 127차 tests passed immediately because PR1~PR29-R had already produced the required public Engine surface for the §42 consumer policy.

Skipping 128차 prevents unnecessary code churn.

This follows the established 3-commit cycle for boundary spec PRs:

```text
PR27-P  114차 / 115차 / 116차 (skip) / 117차
PR28-O  118차 / 119차 / 120차 (skip) / 121차
PR30-P  126차 / 127차 / 128차 (skip) / 129차
```

vs the 4-commit cycle for modifier refinement PRs:

```text
PR23-M  modifier refinement (gap tiering)
PR24-N  modifier refinement (count strength averaging)
PR26-R  modifier refinement (rule_stats maturity continuous)
PR29-R  modifier refinement (observed_precision composition)
```

---

## Implementation footprint

Changed files:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md
tests/test_engine_consumer_policy_guides_usage.py
docs/dev/PR_030_CONSUMER_POLICY_GUIDES_MVP.md
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

No Evidence.type taxonomy ownership change:

```text
framework still does not own Evidence.type meaning
no built-in HINT enum
```

No new public API:

```text
no calibrated truth probability API
no file IO snapshot helpers
no consumer-specific public symbol
```

---

## Test result

Final test result before merge:

```text
1039 passed, 0 failed
```

Delta:

```text
1024 -> 1039
+15 tests
```

Regression:

```text
0
```

Natural-expiry:

```text
0   (no existing test required wording / value update)
```

---

## Boundary preservation table

| Preserved boundary                            | PR30-P effect             | Status      |
| --------------------------------------------- | ------------------------- | ----------- |
| Sub-decision D (types / __init__ / rule_output unchanged) | tests only       | preserved   |
| Sub-decision AF (HINT taxonomy framework-external)        | invariant added   | reinforced  |
| PR17 snapshot schema v2                       | schema_version=2 invariant | reinforced |
| PR21-L hint validation (caller-registered)    | EVIDENCE_TYPE_HINT absent  | reinforced |
| PR27-P consumer call boundary (§39)           | §42 extends one layer outward | extended  |
| PR28-O rule version pinning                   | rule_version reproducibility invariant | reinforced |
| PR29-R observed_precision bounded no-boost    | None / 0.0 / 1.0 / FPR-ignored invariants | reinforced |
| 7-modifier formula shape                      | unchanged                 | preserved   |
| false_positive_rate OOS                       | FPR-ignored invariant      | reinforced |
| rule quality verdict OOS                      | precision-no-boost invariant | reinforced |

---

## Self-review

### What this PR does

PR30-P locks the interpretation boundary between the Engine and external consumers.

It defines and tests how external code should safely read Engine outputs:

```text
effective_confidence is a display signal, not calibrated truth
lifecycle status is separate from effective_confidence
modifier strength is interpretation guidance, not policy
observed_precision is a bounded no-boost modifier, not a quality verdict
rule_version is reproducibility metadata, not quality
snapshot is state preservation, not re-judgment
consumer reporting is consumer responsibility, not framework responsibility
```

### What this PR does not do

PR30-P does not add:

```text
new Engine API
calibrated truth probability
file IO
database layer
report schema
new modifier
new lifecycle state
new snapshot schema version
public HINT enum
LLM integration
tool execution
domain verdict logic
```

### Why all tests pass immediately

All tests pass immediately because the existing public Engine surface already supports the intended interpretation pattern after PR1~PR29-R.

The purpose of the tests is not to force a new implementation.

The purpose is to prevent future changes from accidentally widening the framework into interpretation, calibration, or quality verdict territory.

If a future PR weakens the boundary — for example, by exposing `Engine.compute_truth_probability`, by boosting effective_confidence above the base path, by adding a built-in HINT enum, by making `false_positive_rate` affect effective_confidence — these tests fail loudly.

---

## Final meaning

PR30-P closes the second external boundary layer.

```text
PR27-P  call boundary    (how to call the Engine)
PR30-P  read boundary    (how to read what the Engine returns)
```

Before PR30-P, the framework had a documented public usage boundary (PR27-P) but no documented interpretation policy.

After PR30-P, the framework has both:

```text
- a documented public call boundary
- a documented public interpretation boundary
```

The Engine remains small.

The consumer remains responsible for domain interpretation, product display, and report rendering.

Core locked statement:

```text
Engine outputs are decision-support signals,
not domain verdicts by themselves.
```
