# PR 027 — External Integration Spec MVP

## Summary

PR27-P defines the external integration boundary for consumers of the Engine.

Core proposition:

```text
External integration is a call-boundary contract, not a new engine feature.
```

This PR does not add a Cerberus-specific adapter, file IO wrapper, report schema, or new Engine behavior.

Instead, it documents and tests that the existing public Engine API surface is already sufficient for external consumers such as:

```text
product adapter
CLI wrapper
web backend
report generator
Cerberus-side integration layer
```

The Engine remains a domain-light judgment core.

External consumers remain responsible for raw data ingestion, normalization, persistence storage, reporting, and domain taxonomy ownership.

> **PR27-P did not add integration code.**
> **It locked the public call boundary that already existed.**

---

## Baseline

Before PR27-P:

```text
main:  237b0fc
tests: 969 passing, 0 fail
```

Completed immediately before this PR:

```text
PR26-R rule_stats continuous modifier MVP
```

The active confidence formula entering PR27-P:

```text
effective = base
          × status
          × freshness
          × gap
          × count
          × rule_stats
          × evidence_type
```

PR27-P does not change this formula.

---

## Commits

### 114차 — docs(contract): define external integration spec MVP (§39)

Commit:

```text
dc5883f
```

Added:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md §39
```

Section title:

```text
§39 External integration spec MVP
```

Subsections:

```text
39.1 Core proposition
39.2 Integration boundary
39.3 Recommended call order
39.4 Snapshot handoff boundary
39.5 Effective confidence consumption
39.6 Evidence.type integration boundary
39.7 Framework vs consumer responsibility
39.8 MVP invariants
39.9 Out of scope
```

Key locked proposition:

```text
External integration is a call-boundary contract, not a new engine feature.
```

Responsibility split:

```text
Framework responsibility:
  - judgment state preservation
  - lifecycle transitions
  - formula computation
  - snapshot / migration interpretation

Consumer responsibility:
  - raw data collection
  - caller-side normalization
  - persistence storage
  - report rendering
  - Evidence.type taxonomy ownership
```

PR27-P explicitly kept the following out of scope:

```text
new lifecycle state
new modifier
new formula shape
snapshot schema bump
file IO wrapper
database persistence layer
report schema
Cerberus-specific adapter
framework-owned Evidence.type taxonomy
built-in HINT enum
LLM integration
tool execution
```

---

### 115차 — test(core): lock external integration usage invariants

Commit:

```text
be91e0d
```

Added:

```text
tests/test_engine_external_integration_usage.py
```

Size:

```text
311 lines
11 tests
5 classes
```

Result:

```text
980 passing, 0 fail
```

Expected pattern:

```text
all pass
```

This was intentional.

PR27-P is not a test-first implementation PR that expects failing tests.

It is a boundary-locking PR that verifies the existing public API already supports safe external integration.

Test class distribution:

| Class                                          | Tests | Contract mapping                                             |
| ---------------------------------------------- | ----: | ------------------------------------------------------------ |
| `TestExternalConsumerRecommendedCallOrder`     |     2 | §39.3 call order + lifecycle transition                      |
| `TestExternalConsumerSnapshotBoundary`         |     3 | §39.4 round-trip / JSON / signature                          |
| `TestExternalConsumerHintEvidenceTypeBoundary` |     2 | §39.6 register / unregister / clear + caller taxonomy        |
| `TestExternalConsumerQueryBoundaries`          |     2 | §39.5 / §39.7 read-side query + lifecycle history round-trip |
| `TestNoCerberusSpecificPublicAdapter`          |     2 | §39.8 no domain-specific public symbol                       |

Total:

```text
11 tests
```

---

## 115차 locked usage patterns

### 1. Recommended call order through public APIs

The test locks that an external consumer can use this flow without touching Engine internals:

```text
Engine()
register_rule
register_hint_evidence_types
add_claim
add_gap
add_evidence
resolve_gaps_for_evidence
update_rule_stats
compute_effective_confidence
to_snapshot
```

The expected score was:

```text
0.9
```

Meaning:

```text
base = 1.0
status = 1.0
freshness = 1.0
gap = 1.0
count = 1.0
rule_stats = 1.0
evidence_type = 0.9

effective = 0.9
```

This verifies that external consumers can follow the documented call order using only public APIs.

---

### 2. Lifecycle transition before score query

The test locks this flow:

```text
register_contradiction
dispute_claim_if_ready
compute_effective_confidence
claim_lifecycle_history
```

Expected score:

```text
0.35
```

Meaning:

```text
base = 1.0
status disputed = 0.5
freshness = 1.0 - 0.6 × 0.5 = 0.7

effective = 1.0 × 0.5 × 0.7 = 0.35
```

Expected lifecycle event:

```text
from_status = CLAIM_STATUS_CONFIRMED
to_status = CLAIM_STATUS_DISPUTED
transition = "dispute_if_ready"
```

This verifies that external consumers can perform lifecycle transition first, then read the resulting confidence and audit history.

---

### 3. Snapshot handoff boundary

The tests lock:

```text
Engine.to_snapshot()
Engine.from_snapshot(snapshot)
```

as a state handoff boundary.

Verified:

```text
from_snapshot preserves compute_effective_confidence output
from_snapshot preserves full snapshot identity
snapshot is JSON-compatible
to_snapshot takes no file path
from_snapshot accepts snapshot state, not file path
```

This preserves PR17 and PR18-K:

```text
Persistence is state preservation, not re-judgment.
Migration preserves compatibility, not truth.
```

PR27-P does not introduce file IO.

---

### 4. Evidence.type taxonomy remains caller-owned

The tests lock that caller-owned taxonomy can be used like this:

```text
{
  "banner_hint": 7001,
  "cpe_mapper_hint": 7002,
  "api_enrichment_hint": 7003
}
```

The framework only receives integer IDs through:

```text
register_hint_evidence_types(...)
```

The framework does not own the meaning of those IDs.

Verified:

```text
register_hint_evidence_types
unregister_hint_evidence_types
clear_hint_evidence_types
```

all immediately affect the evidence_type modifier through the existing public boundary.

This preserves PR21-L, PR22-S, and PR25-T.

---

### 5. Effective confidence is read-side output

The test locks that repeated calls to:

```text
compute_effective_confidence(claim_id)
```

do not mutate Engine state.

Verified:

```text
snapshot before == snapshot after
first query == second query
```

This supports §39.5:

```text
effective_confidence is an Engine confidence output and report input,
not a final vulnerability verdict.
```

---

### 6. No Cerberus-specific public adapter

The tests lock that `ragcore.__all__` does not export:

```text
cerberus
cerberusclient
cerberus_client
hint
hint_evidence_type
hintevidencetype
```

Also verified:

```text
hasattr(ragcore, "CerberusClient") == False
hasattr(ragcore, "cerberus_client") == False
```

This preserves the domain-light framework boundary.

Cerberus may consume the framework.

The framework does not become Cerberus-specific.

---

## 116차 skipped intentionally

116차 implementation was skipped.

Reason:

```text
PR27-P is a boundary spec PR, not an Engine feature PR.
```

There was no missing Engine behavior to implement after 115차.

The 115차 tests passed immediately because PR1~PR26-R had already produced the required public API surface.

Skipping 116차 prevents unnecessary code churn.

---

## Implementation footprint

Changed files:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md
tests/test_engine_external_integration_usage.py
docs/dev/PR_027_EXTERNAL_INTEGRATION_SPEC_MVP.md
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
```

---

## Test result

Final test result before merge:

```text
980 passed, 0 failed
```

Delta:

```text
969 -> 980
+11 tests
```

Regression:

```text
0
```

---

## Self-review

### What this PR does

PR27-P locks the integration boundary between the Engine and external consumers.

It defines and tests how external code should safely use the Engine:

```text
caller normalization
public Engine registration APIs
lifecycle APIs
effective confidence query
snapshot handoff
caller-owned reporting
caller-owned taxonomy
```

### What this PR does not do

PR27-P does not add:

```text
Cerberus adapter
file IO
database layer
report schema
finding schema
CVSS / EPSS / KEV integration
new modifier
new lifecycle state
new snapshot schema version
public HINT enum
LLM integration
tool execution
```

### Why all tests pass immediately

All tests pass immediately because the existing public API already supports the intended external usage pattern.

The purpose of the tests is not to force a new implementation.

The purpose is to prevent future changes from accidentally breaking the public integration boundary.

---

## Final meaning

PR27-P closes the first external integration boundary layer.

Before PR27-P, the framework had a strong internal Engine.

After PR27-P, the framework has a documented and tested public usage boundary for external consumers.

The Engine remains small.

The consumer remains responsible for domain-specific integration.

Core locked statement:

```text
External integration is a call-boundary contract, not a new engine feature.
```
