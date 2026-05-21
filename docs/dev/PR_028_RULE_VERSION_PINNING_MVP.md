# PR 028 — Rule Version Pinning MVP

## Summary

PR28-O defines rule version pinning as an integration stability boundary.

Core proposition:

```text
Rule version pinning is integration stability, not rule quality judgment.
```

This PR does not introduce a new RuleStats quality model, new lifecycle transition, new modifier, or rule migration policy.

Instead, it documents and tests the existing behavior that rule identity is the pair:

```text
(rule_id, rule_version)
```

not `rule_id` alone.

A Claim remains tied to the exact rule version that created it through:

```text
Claim.created_by_rule
Claim.created_by_rule_version
```

External consumers and reports should preserve both values for reproducibility.

---

## Baseline

Before PR28-O:

```text
main:  b1b914a
tests: 980 passing, 0 fail
```

Completed immediately before this PR:

```text
PR27-P external integration spec MVP
```

Active formula entering PR28-O:

```text
effective = base
          × status
          × freshness
          × gap
          × count
          × rule_stats
          × evidence_type
```

PR28-O does not change this formula.

---

## Commits

### 118차 — docs(contract): define rule version pinning MVP (§40)

Commit:

```text
cfb1545
```

Added:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md §40
```

Section title:

```text
§40 Rule version pinning MVP
```

Subsections:

```text
40.1 Core proposition
40.2 Why rule version pinning exists
40.3 Rule identity boundary
40.4 Claim pinning rule
40.5 RuleStats pinning
40.6 Snapshot and report boundary
40.7 External consumer responsibility
40.8 What PR28-O does not mean
40.9 MVP invariants
40.10 Out of scope
40.11 Final statement
```

Key locked proposition:

```text
Rule version pinning is integration stability, not rule quality judgment.
```

PR28-O clarified that:

```text
rule_id alone is not enough
(rule_id, rule_version) is the reproducibility key
Claim.created_by_rule_version is pinned at creation time
later rule versions must not silently reinterpret existing Claims
```

---

### 119차 — test(core): lock rule version pinning invariants

Commit:

```text
4bc66ce
```

Added:

```text
tests/test_engine_rule_version_pinning.py
```

Size:

```text
316 lines
17 tests
5 classes
```

Result:

```text
997 passing, 0 fail
```

Expected pattern:

```text
all pass
```

This was intentional.

PR28-O is a boundary-locking PR, not a new Engine feature PR.

The tests pass immediately because PR1~PR27-P had already produced the required rule identity structure.

---

## 119차 test distribution

| Class                            | Tests | Contract mapping                                  |
| -------------------------------- | ----: | ------------------------------------------------- |
| `TestRuleVersionIdentity`        |     3 | §40.3 `(rule_id, rule_version)` pair              |
| `TestClaimRuleVersionPinning`    |     3 | §40.4 Claim pinning + snapshot                    |
| `TestRuleStatsVersionIsolation`  |     5 | §40.5 version isolation + pinned lookup           |
| `TestSnapshotRuleVersionPinning` |     3 | §40.6 round-trip + no schema bump                 |
| `TestNoRuleMigrationPolicy`      |     3 | §40.7 / §40.10 no latest-version or migration API |

Total:

```text
17 tests
```

---

## Locked behavior

### 1. Rule identity is a pair

The tests lock that these are distinct rule identities:

```text
(100, 1)
(100, 2)
```

Same `rule_id` with different `rule_version` can coexist.

Duplicate registration of the same pair is rejected.

```text
same rule_id + same rule_version -> duplicate
same rule_id + different rule_version -> allowed
```

---

### 2. Claim pins rule version at creation time

The tests lock that a Claim stores:

```text
created_by_rule
created_by_rule_version
```

at creation time.

Later registration of a newer rule version does not rewrite existing Claims.

Example:

```text
register rule (100, 1)
create Claim pinned to (100, 1)
register rule (100, 2)

Claim remains pinned to (100, 1)
```

No automatic migration occurs.

---

### 3. RuleStats are version-isolated

The tests lock that:

```text
update_rule_stats(100, 1, ...)
```

affects only:

```text
RuleStats(rule_id=100, rule_version=1)
```

and does not affect:

```text
RuleStats(rule_id=100, rule_version=2)
```

The reverse direction is also locked.

---

### 4. Effective confidence uses the pinned pair

The most important numeric lock:

```text
claim pinned to (100, 1)
rule (100, 2) has firing_count >= 2
rule (100, 1) has firing_count == 0
```

Expected score:

```text
0.8
```

Reason:

```text
PR26-R rule_stats modifier:
firing_count == 0 -> 0.8
firing_count == 1 -> 0.9
firing_count >= 2 -> 1.0
```

If the Engine incorrectly searched for the latest version `(100, 2)`, the score would become:

```text
1.0
```

The test confirms the Engine does not do latest-version lookup.

It uses:

```text
(claim.created_by_rule, claim.created_by_rule_version)
```

---

### 5. Separate pinned Claims get separate scores

The tests lock:

```text
claim_v1 pinned to (100, 1)
claim_v2 pinned to (100, 2)
```

with stats:

```text
(100, 1) firing_count = 1  -> score 0.9
(100, 2) firing_count = 2  -> score 1.0
```

This confirms rule version pinning is not just storage-level.

It affects effective confidence through the pinned RuleStats lookup.

---

### 6. Missing pinned stats preserve existing fallback

The tests lock the existing fallback:

```text
claim pinned to (100, 1)
only rule_stats for (100, 2) exists
```

Expected score:

```text
1.0
```

Meaning:

```text
missing exact pinned RuleStats -> fallback 1.0
```

The Engine must not search for latest registered version.

This preserves PR20-F / PR26-R fallback behavior.

---

### 7. Snapshot preserves pinned rule identity

The tests lock that snapshot round-trip preserves:

```text
Claim.created_by_rule
Claim.created_by_rule_version
RuleStats(rule_id, rule_version)
version-specific confidence output
```

Also locked:

```text
snapshot schema_version remains 2
```

PR28-O does not require a schema bump.

---

### 8. No rule migration policy

The tests lock absence of public latest-version and migration APIs.

No public Engine methods such as:

```text
latest_rule_version
get_latest_rule
resolve_latest_rule_version
migrate_claim_to_rule_version
upgrade_claim_rule_version
reassign_claim_rule
```

No public `ragcore.__all__` exports for migration APIs.

This confirms PR28-O does not create a framework-owned rule migration policy.

---

## 120차 skipped intentionally

120차 implementation was skipped.

Reason:

```text
PR28-O is a boundary-locking PR.
The existing Engine already satisfies the rule version pinning contract.
```

There was no missing Engine behavior after 119차.

The 17 all-pass tests confirm that:

```text
RuleDefinition / RuleStats already use (rule_id, rule_version)
Claim already stores created_by_rule_version
compute_effective_confidence already uses the Claim's pinned pair
snapshot already preserves version-specific state
```

Skipping implementation prevents unnecessary code churn.

---

## Implementation footprint

Changed files:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md
tests/test_engine_rule_version_pinning.py
docs/dev/PR_028_RULE_VERSION_PINNING_MVP.md
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

No rule migration policy:

```text
no latest-version lookup
no automatic claim migration
no superseded/retracted state
```

---

## Test result

Final test result before merge:

```text
997 passed, 0 failed
```

Delta:

```text
980 -> 997
+17 tests
```

Regression:

```text
0
```

---

## Self-review

### What this PR does

PR28-O locks that rule identity is versioned.

The framework preserves the exact rule version that produced a Claim.

External consumers can safely use:

```text
rule_id + rule_version
```

as the report and reproducibility key.

### What this PR does not do

PR28-O does not add:

```text
rule quality verdict
observed_precision modifier
false_positive_rate modifier
latest-version policy
automatic rule migration
claim supersession
new lifecycle state
new modifier
snapshot schema bump
Cerberus-specific rule adapter
```

### Why all tests pass immediately

All tests pass immediately because the existing Engine structure already had the required rule version pinning behavior.

The purpose of the tests is to prevent future changes from weakening this boundary.

---

## Relationship to PR27-P

PR27-P locked the external consumer call boundary.

PR28-O locks one of the most important reproducibility boundaries for that consumer:

```text
which exact rule version produced this Claim?
```

Together:

```text
PR27-P -> how external consumers call the Engine
PR28-O -> how external consumers preserve rule-version identity
```

Both PRs intentionally avoid making the Engine larger.

---

## Final meaning

PR28-O closes the rule version reproducibility boundary.

Before PR28-O, rule version behavior existed in code.

After PR28-O, that behavior is documented and protected by tests.

Core locked statement:

```text
Rule version pinning is integration stability, not rule quality judgment.
```
