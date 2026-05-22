# PR 031 — AI-Readable Usage Recipe MVP

## Summary

PR31-S documents and locks the AI-readable usage recipes for the existing Engine public API.

Core proposition:

```text
PR27-P §39  call boundary    (how to call the Engine)
PR30-P §42  read boundary    (how to read Engine outputs)
PR31-S §43  usage recipe     (what order to call methods in)
```

§42 answered "what does the output mean."
§43 answers "in what order should I make calls to get that output."

This PR does not add a new Engine feature, a new public API, a method rename, or a snapshot schema change. It documents the canonical call sequence that an external AI consumer can follow using only the existing public surface, and locks the sequence as executable invariants.

> **PR31-S did not add recipe helper methods.**
> **It locked the usage recipe boundary that already existed.**

---

## Why PR31-S after PR30-P

After PR30-P, the framework had:

```text
PR27-P  documented call boundary  (you CAN call in this order)
PR30-P  documented read boundary  (this is what the output means)
```

What was missing was the canonical recipe — the actual recommended call sequence for typical usage scenarios. An AI consumer reading the framework could see the API list and the policy boundary, but had to reconstruct the call order itself.

PR31-S closes that gap. It enumerates six canonical scenarios and locks each as a deterministic recipe:

```text
A. candidate confirmation
B. disputed review
C. refutation
D. snapshot restore
E. observed_precision feedback
F. hint evidence type cycle
```

Each scenario uses only public APIs that already existed after PR1~PR30-P.

---

## Baseline

Before PR31-S:

```text
main:  60bf492
tests: 1039 passing, 0 fail
```

Completed immediately before this PR:

```text
PR30-P consumer policy guides MVP
```

The active confidence formula entering PR31-S:

```text
effective = base
          × status
          × freshness
          × gap
          × count
          × rule_stats
          × evidence_type
```

PR31-S does not change this formula.

---

## §43 boundary category letter codes

§43 introduces a new boundary category namespace distinct from §42 A~H (read-policy categories). §43 codes are usage-recipe categories.

| Category | Boundary                                       | Contract section |
| -------- | ---------------------------------------------- | ---------------- |
| A        | candidate confirmation recipe boundary         | §43.3            |
| B        | disputed review recipe boundary                | §43.4            |
| C        | refutation recipe boundary                     | §43.5            |
| D        | snapshot restore recipe boundary               | §43.6            |
| E        | rule_stats feedback recipe boundary            | §43.7            |
| F        | hint evidence type recipe boundary             | §43.8            |
| G        | method surface mental model boundary           | §43.9            |
| H        | OOS / no API change boundary                   | §43.11           |

§42 A~H and §43 A~H are intentionally separate namespaces.

---

## §43 13 subsections

§43 was added to `docs/contracts/05_DATA_CONTRACT_MVP.md` (+521 lines):

```text
§43.1   Core proposition
§43.2   Recipe overview
§43.3   Scenario A — candidate confirmation recipe
§43.4   Scenario B — disputed review recipe
§43.5   Scenario C — refutation recipe
§43.6   Scenario D — snapshot restore recipe
§43.7   Scenario E — rule_stats observed_precision feedback recipe
§43.8   Scenario F — hint evidence type recipe
§43.9   Method surface mental model (write-side vs read-side)
§43.10  AI consumer interpretation checklist (10 items linking to §42)
§43.11  Out of scope
§43.12  Invariants (8 recipe invariants for 131차 test-first)
§43.13  Constraints on 131/133차 (3-commit cycle, 132차 skip)
```

---

## Commits

### 130차 — docs(contract): define AI-readable usage recipe MVP (§43)

Commit:

```text
67bfc4d
```

Added:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md §43
```

Section title:

```text
§43 AI-Readable Usage Recipe MVP
```

Six canonical scenarios documented (A~F), each with:

```text
Given:    prerequisite state
Steps:    public API call sequence
Read:     value to query at the end
Meaning:  interpretation under §42 wording
```

Method surface mental model documented in §43.9:

```text
write-side methods (state mutation)
read-side methods (no mutation)
naming rule of thumb
```

AI consumer interpretation checklist documented in §43.10 with 10 items linking back to §42.

PR31-S explicitly kept the following out of scope:

```text
new public API
method renaming
deprecated alias
__all__ change
new enum
new modifier
new lifecycle state
file IO wrapper
report schema
serialization format other than the existing snapshot dict
visualization helpers
LLM integration
tool execution
Cerberus-side adapter
```

---

### 131차 — test(core): lock AI-readable usage recipe invariants

Commit:

```text
816299b
```

Added:

```text
tests/test_engine_ai_readable_usage_recipe.py
```

Size:

```text
597 lines
23 tests
8 classes
```

Result:

```text
1062 passing, 0 fail
```

Expected pattern:

```text
all pass
```

This was intentional.

PR31-S is not a test-first implementation PR that expects failing tests.

It is a boundary-locking PR that verifies the existing public Engine surface already supports the §43 canonical recipes.

Test class distribution:

| Class                                  | Tests | §43 mapping       | Category |
| -------------------------------------- | ----: | ----------------- | -------- |
| `TestRecipeCandidateConfirmation`      |     3 | §43.3             | A        |
| `TestRecipeDisputedReview`             |     3 | §43.4             | B        |
| `TestRecipeRefutation`                 |     3 | §43.5             | C        |
| `TestRecipeSnapshotRestore`            |     3 | §43.6             | D        |
| `TestRecipeObservedPrecisionFeedback`  |     3 | §43.7             | E        |
| `TestRecipeHintEvidenceTypes`          |     3 | §43.8             | F        |
| `TestReadSidePurity`                   |     2 | §43.9             | G        |
| `TestMethodSurfaceInvariance`          |     3 | §43.9 / §43.11    | G / H    |

Total:

```text
23 tests
```

---

## 131차 locked invariants

### Category A — candidate confirmation recipe

Recipe A flow:

```text
add_entity
add_claim(rule_id=0, base_confidence=0.8, status=CLAIM_STATUS_CANDIDATE)
add_gap(claim_id, required_evidence_type=...)
add_evidence(claim_id, evidence_type=..., strength=...)
resolve_gaps_for_evidence(evidence_id)   -> (1,)
confirm_claim_if_ready(claim_id)         -> True
compute_effective_confidence(claim_id)
claim_lifecycle_history(claim_id)
```

Locked values:

```text
status                       = CLAIM_STATUS_CONFIRMED
score                        = 0.8   (base × 1.0 × 1.0 × 1.0 × 1.0 × 1.0 × 1.0)
lifecycle event count        = 1
lifecycle transition         = "confirm_if_ready"
lifecycle from_status        = CLAIM_STATUS_CANDIDATE
lifecycle to_status          = CLAIM_STATUS_CONFIRMED
```

---

### Category B — disputed review recipe

Recipe B flow:

```text
add_entity
add_claim(base_confidence=1.0, status=CLAIM_STATUS_CONFIRMED)
add_evidence(claim_id, evidence_type=..., strength=0.6)
register_contradiction(claim_id, evidence_id)   -> True
dispute_claim_if_ready(claim_id)                -> True
compute_effective_confidence(claim_id)
claim_lifecycle_history(claim_id)
```

Locked values:

```text
status                       = CLAIM_STATUS_DISPUTED
score                        = 0.35
                               = base 1.0
                               × status 0.5      (DISPUTED)
                               × freshness 0.7   (1.0 - 0.6 × 0.5)
                               × gap 1.0
                               × count 1.0       (<2 active contradictions)
                               × rule_stats 1.0  (rule_id=0 path)
                               × evidence_type 1.0
lifecycle event count        = 1
lifecycle transition         = "dispute_if_ready"
lifecycle from_status        = CLAIM_STATUS_CONFIRMED
lifecycle to_status          = CLAIM_STATUS_DISPUTED
```

---

### Category C — refutation recipe

Recipe C flow:

```text
add_entity
add_claim(base_confidence=0.8, status=CLAIM_STATUS_CANDIDATE)
add_evidence(claim_id, evidence_type=..., strength=0.7)
register_contradiction(claim_id, evidence_id)   -> True
refute_claim_if_ready(claim_id)                 -> True
compute_effective_confidence(claim_id)
claim_lifecycle_history(claim_id)
```

Locked values:

```text
status                       = CLAIM_STATUS_REFUTED
score                        = 0.0   (status dominates)
lifecycle event count        = 1
lifecycle transition         = "refute_if_ready"
lifecycle from_status        = CLAIM_STATUS_CANDIDATE
lifecycle to_status          = CLAIM_STATUS_REFUTED
```

---

### Category D — snapshot restore recipe

Recipe D flow:

```text
# non-trivial setup with rule registered, hint type registered,
# claim confirmed via gap + evidence + resolve_gaps_for_evidence,
# rule_stats updated with firing_delta=2, observed_precision=1.0

snapshot = engine.to_snapshot()
restored = Engine.from_snapshot(snapshot)
```

Locked values:

```text
restored.get_claim(claim_id).status                   == engine.get_claim(claim_id).status
restored.get_claim(claim_id).created_by_rule          == engine.get_claim(claim_id).created_by_rule
restored.get_claim(claim_id).created_by_rule_version  == engine.get_claim(claim_id).created_by_rule_version
restored.compute_effective_confidence(claim_id).value == engine.compute_effective_confidence(claim_id).value
restored.to_snapshot()                                == engine.to_snapshot()
```

Snapshot is state preservation, not re-judgment (PR17 + §42.6).

---

### Category E — rule_stats observed_precision feedback recipe

Recipe E three cases:

```text
Case 1 — observed_precision=1.0 (no boost)
  register_rule(...)
  add_claim(base=0.8, rule_id=RULE_ID, rule_version=RULE_VERSION)
  update_rule_stats(firing_delta=2, observed_precision=ScoreValue(1.0))
  compute_effective_confidence(claim_id)
  -> score = 0.8   (base × rule_stats 1.0)

Case 2 — observed_precision=0.0 (bounded attenuation)
  update_rule_stats(firing_delta=2, observed_precision=ScoreValue(0.0))
  -> score = 0.72  (base 0.8 × rule_stats 0.9)
                   precision_modifier floor 0.9

Case 3 — observed_precision=None (neutral)
  # no update_rule_stats call
  # firing_count = 0
  -> score = 0.64  (base 0.8 × rule_stats 0.8)
                   maturity_modifier floor 0.8
                   precision_modifier neutral 1.0
```

Locked range:

```text
rule_stats_modifier in [0.72, 1.0]
no boost above base path (PR29-R §41.1)
false_positive_rate ignored (PR29-R §41.3 + §42.10)
```

---

### Category F — hint evidence type recipe

Recipe F three operations:

```text
# baseline: claim with evidence type=HINT_TYPE, strength=0.5,
# no hint registered yet

score_before                = engine.compute_effective_confidence(claim_id)
register_hint_evidence_types({HINT_TYPE})
score_after_register        = engine.compute_effective_confidence(claim_id)

unregister_hint_evidence_types({HINT_TYPE})
score_after_unregister      = engine.compute_effective_confidence(claim_id)

register_hint_evidence_types({HINT_TYPE, HINT_TYPE+1, HINT_TYPE+2})
clear_hint_evidence_types()
score_after_clear           = engine.compute_effective_confidence(claim_id)
```

Locked values:

```text
score_before              = 1.0   (no hint registered, evidence_type modifier = 1.0)
score_after_register      = 0.9   (HINT_TYPE registered, evidence_type modifier = 0.9)
score_after_unregister    = 1.0   (HINT_TYPE removed)
score_after_clear         = 1.0   (set emptied)
```

Caller-registered hint set is the framework's only source of truth for hint types (PR21-L / PR22-S / PR25-T + Sub-decision AF).

---

### Category G — read-side purity

The tests lock that `compute_effective_confidence` and read-only `get_*` / `*_for_claim` / `*_history` methods do not mutate Engine state.

```text
snapshot_before = engine.to_snapshot()
compute_effective_confidence(claim_id)   # called three times
get_claim / evidences_for_claim / gaps_for_claim
contradictions_for_claim / claim_lifecycle_history
get_rule / get_rule_stats
assert engine.to_snapshot() == snapshot_before
```

This supports §42.3 (effective_confidence is read-side output) and §39.5.

---

### Category H — method surface invariance

The tests lock the exact set of 49 public symbols in `ragcore.__all__` as of PR30-P main `60bf492`:

```text
_PR30_BASELINE_PUBLIC_SYMBOLS = frozenset({...48 symbols...})

assert frozenset(ragcore.__all__) == _PR30_BASELINE_PUBLIC_SYMBOLS
```

Also verified:

```text
ragcore.__all__ has no duplicate symbols
no recipe helper method exists:
    Engine.use_recipe        not exists
    Engine.run_scenario      not exists
    Engine.explain           not exists
    Engine.ai_usage_guide    not exists
    "use_recipe" / "run_scenario" / "explain" / "ai_usage_guide"
        not in ragcore.__all__
```

This locks the public surface against drift.

---

## ragcore.__all__ PR30-P baseline freeze

PR31-S's strongest single invariant is the `frozenset` of 49 public symbols, captured from PR30-P main `60bf492`:

```text
48 symbols including:
  Engine, Claim, Evidence, Gap, Relation, Entity, Observation
  RuleDefinition, RuleStats, RuleSpec, RuleOutputTemplate
  RequiredEvidenceTemplate, ClaimLifecycleEvent, ScoreValue
  Combinator, CombinatorTrace, FiringTrace, Predicate, PredicateTrace
  CLAIM_STATUS_CANDIDATE / CONFIRMED / DISPUTED / REFUTED
  KIND_CLAIM / ENTITY / EVIDENCE / GAP / OBSERVATION / RELATION
  RULE_MATURITY_EXPERIMENTAL / STABLE / DEPRECATED
  TRACE_REASON_MATCH / MISMATCH / MISSING_FIELD / TYPE_MISMATCH
  compile_required_evidence / compile_rule_condition
  compile_rule_definition / compile_rule_output
  evaluate_condition / evaluate_condition_with_trace
  fire_rule / fire_rule_with_trace
  load_condition_tree / load_rule_spec / load_rule_spec_from_yaml
  register_rule_spec
```

Meaning:

```text
After PR31-S, any PR that adds, removes, or renames a symbol in
ragcore.__all__ must intentionally update _PR30_BASELINE_PUBLIC_SYMBOLS
and the corresponding §43 invariant 8.

Public API drift no longer slips through silently.
```

This is the strongest method surface lock introduced by any PR in the PR1~PR31-S cycle.

---

## 132차 skipped intentionally

132차 implementation was skipped.

Reason:

```text
PR31-S is a boundary spec PR, not an Engine feature PR.
```

There was no missing Engine behavior to implement after 131차.

The 131차 tests passed immediately because PR1~PR30-P had already produced the required public Engine surface for the §43 recipes.

Skipping 132차 prevents unnecessary code churn.

This follows the established 3-commit cycle for boundary spec PRs:

```text
PR27-P  114차 / 115차 / 116차 (skip) / 117차
PR28-O  118차 / 119차 / 120차 (skip) / 121차
PR30-P  126차 / 127차 / 128차 (skip) / 129차
PR31-S  130차 / 131차 / 132차 (skip) / 133차
```

---

## Implementation footprint

Changed files:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md
tests/test_engine_ai_readable_usage_recipe.py
docs/dev/PR_031_AI_READABLE_USAGE_RECIPE_MVP.md
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
no method addition
no deprecated alias
```

No Evidence.type taxonomy ownership change:

```text
framework still does not own Evidence.type meaning
no built-in HINT enum
```

---

## Test result

Final test result before merge:

```text
1062 passed, 0 failed
```

Delta:

```text
1039 -> 1062
+23 tests
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

| Preserved boundary                                       | PR31-S effect              | Status      |
| -------------------------------------------------------- | -------------------------- | ----------- |
| Sub-decision D (types / __init__ / engine / rule_output) | tests only                 | preserved   |
| Sub-decision AF (HINT taxonomy framework-external)       | recipe F invariant         | reinforced  |
| PR17 snapshot schema v2                                  | recipe D round-trip        | reinforced  |
| PR21-L hint validation (caller-registered)               | recipe F register/unregister/clear | reinforced |
| PR27-P consumer call boundary (§39)                      | §43 extends one layer outward | extended  |
| PR28-O rule version pinning                              | recipe D rule pinning preserved | reinforced |
| PR29-R observed_precision bounded no-boost               | recipe E three cases       | reinforced |
| PR30-P consumer policy guides (§42)                      | §43.10 checklist links to §42 | reinforced |
| 7-modifier formula shape                                  | unchanged                  | preserved   |
| false_positive_rate OOS                                  | recipe E omits FPR        | reinforced  |
| rule quality verdict OOS                                 | recipe E bounded only     | reinforced  |
| ragcore.__all__ symbol set                               | frozenset locked          | **newly locked** |

---

## Self-review

### What this PR does

PR31-S documents and locks the canonical AI-readable usage recipes for the existing Engine public API.

It defines and tests how an external AI consumer should call the Engine:

```text
candidate confirmation through add_claim + add_gap + add_evidence
                          + resolve_gaps_for_evidence + confirm_claim_if_ready
disputed review through register_contradiction + dispute_claim_if_ready
refutation through register_contradiction + refute_claim_if_ready
snapshot restore through to_snapshot + Engine.from_snapshot
observed_precision feedback through register_rule + update_rule_stats
hint evidence type cycle through register / unregister / clear
read-side purity (compute_effective_confidence + get_* do not mutate)
method surface invariance (ragcore.__all__ frozen at 60bf492 baseline)
```

### What this PR does not do

PR31-S does not add:

```text
new Engine method
new public symbol
method rename
deprecated alias
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
visualization helpers
```

### Why all tests pass immediately

All 23 tests pass immediately because the existing public Engine surface already supports the intended recipe pattern after PR1~PR30-P.

The purpose of the tests is not to force a new implementation.

The purpose is to prevent future changes from accidentally breaking the canonical recipe or drifting the public surface.

If a future PR weakens any recipe — for example, by changing `confirm_claim_if_ready` to no longer require resolved gaps, by changing the dispute status modifier from 0.5, by changing the freshness formula, by adding `Engine.use_recipe()`, by adding `EVIDENCE_TYPE_HINT` to `ragcore.__all__`, by removing a symbol from `__all__` — these tests fail loudly.

---

## Final meaning

PR31-S closes the third external boundary layer.

```text
PR27-P  call boundary    (how to call the Engine)
PR30-P  read boundary    (how to read what the Engine returns)
PR31-S  usage recipe     (what order to call methods in)
```

Together, these three PRs form the documented external integration surface of the framework.

```text
Before PR27-P:  strong internal Engine, undocumented external usage.
After PR27-P:   call boundary locked.
After PR30-P:   read boundary locked.
After PR31-S:   usage recipe locked, method surface frozen.
```

The Engine remains a domain-light judgment core.

The consumer remains responsible for translating Engine signals into product, report, or remediation decisions.

Core locked statement:

```text
The canonical AI-readable usage recipes are public API call sequences.
They are recipes, not new APIs.
```

---

## Next candidates after PR31-S

The natural follow-up PR set has narrowed further. Remaining candidates:

```text
R-fpr        false_positive_rate modifier (PR29-R natural follow-up,
             requires §42.10 H invariant + §43 recipe E invariant update)
G            superseded / retracted lifecycle (Sub-decision D breaks,
             requires explicit user approval, §42.2 C + §43.5 C update)
J            multi-rule claim composition (Sub-decision D breaks,
             requires explicit user approval, §42.7 E + §43.6 D update)
Q            rule_stats outcome ratio modifier (Sub-decision AF +
             PR29-R + PR30-P + PR31-S spirit conflict, large risk)
S-extension  8th modifier (7-modifier composition shift, §42.5 B +
             §43 invariant 5 update)
V-cerberus   Cerberus-side adapter in a different repo (framework
             unchanged, exercises PR27-P + PR30-P + PR31-S in practice)
```

Sub-decision D, AF, and the §42 / §43 letter-code namespaces will continue to constrain future PRs.
