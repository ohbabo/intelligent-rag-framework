# Engine Read Surface Audit

Status: audit document (PR50)
Baseline: main `b247d7e` (PR49 merged)
Type: doc-only audit, no source change, no test change, no public symbol change

## 0. Scope limitation (locked, user 2026-05-25)

```text
PR50 is not a read API implementation PR.

PR50 is the audit that decides whether PR51 can be external-wrapper-only
or needs separately locked ragcore read method candidates.
```

한국어:

```text
PR50 은 read API 구현 PR 이 아니다.

PR50 은 PR51 이 외부 wrapper 만으로 가능한지, 아니면 별도 잠금이
필요한 ragcore read method 후보가 필요한지 판단하는 audit PR 이다.
```

PR50 reads the existing `ragcore.Engine` public surface, classifies each of the 40 methods by mutation/read semantics, checks the read-only candidates against PR49 §5 (the 6 must-hold conditions), maps the LLM Context Packet field requirements against existing-method composition, and concludes whether PR51 can stay at 1순위 (external EngineInspector) or requires a separately authorized ragcore read method addition.

---

## 1. Core statement

```text
We audit the readable surface before adding any read surface.
읽기 표면을 추가하기 전에, 먼저 현재 읽을 수 있는 표면을 감사한다.
```

---

## 2. Audit input baseline

```text
main:                              b247d7e (PR49 merged)
tests:                             1145 passing
ragcore.__all__:                   48 symbols
Engine public methods:             40
snapshot schema_version:           2
snapshot top-level keys:           18

Reference documents consumed by this audit:
  docs/architecture/ENGINE_INTERNAL_MAP.md          (PR47, §2 regions)
  docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md (PR49,
                                                     §3 / §5 / §8)
  docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md         (PR43-C, §3 / §4)
  docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md    (PR44-D, AP-* set)
  direction_rag_framework_proposal_layer (memory direction,
                                          §10 Context Packet)
```

---

## 3. Public method classification

The 40 public methods at baseline `b247d7e` partition cleanly into six classes by mutation/read semantics. Source-method counts cross-check to 40.

### 3.1 Read-only (19)

```text
get_entity(entity_id)                           → Entity
get_observation(observation_id)                  → Observation
get_claim(claim_id)                              → Claim
get_evidence(evidence_id)                        → Evidence
get_gap(gap_id)                                  → Gap
get_relation(relation_id)                        → Relation
get_rule(rule_id, rule_version)                  → RuleDefinition
get_rule_stats(rule_id, rule_version)            → RuleStats
evidences_for_claim(claim_id)                    → list[Evidence]
gaps_for_claim(claim_id)                         → list[Gap]
contradictions_for_claim(claim_id)               → tuple[int, ...]
active_contradictions_for_claim(claim_id)        → tuple[int, ...]
active_contradictions_by_freshness(claim_id)     → tuple[int, ...]
resolved_contradictions_for_claim(claim_id)      → tuple[int, ...]
claim_lifecycle_history(claim_id)                → tuple[ClaimLifecycleEvent, ...]
evidence_freshness(evidence_id)                  → int
gap_resolution(gap_id)                           → int | None
compute_effective_confidence(claim_id)           → ScoreValue
to_snapshot()                                    → dict[str, Any]
```

### 3.2 Mutation add (6)

```text
add_entity(entity_type, flags)                    → entity_id
add_observation(entity_id, raw_ref_id,
                observation_type, source_type)     → observation_id
add_claim(subject_id, claim_type, rule_id,
          rule_version, reason_code, *,
          base_confidence, status, flags)          → claim_id
add_evidence(claim_id, raw_ref_id, evidence_type,
             strength)                             → evidence_id
add_relation(from_kind, from_id, to_kind, to_id,
             relation_type, rule_id, reason_code)  → relation_id
add_gap(claim_id, gap_type, required_evidence_type,
        severity, rule_id)                         → gap_id
```

### 3.3 Mutation register (3)

```text
register_contradiction(claim_id, evidence_id)              → bool
register_contradiction_resolution(claim_id, evidence_id)   → bool
resolve_gaps_for_evidence(evidence_id)                     → tuple[int, ...]
```

### 3.4 Lifecycle transition (6)

```text
confirm_claim_if_ready(claim_id)                          → bool
dispute_claim_if_ready(claim_id)                          → bool
refute_claim_if_ready(claim_id)                           → bool
refute_disputed_claim_if_ready(claim_id)                  → bool
refute_disputed_claim_if_ready_by_freshness(claim_id)     → bool
resolve_disputed_claim_if_ready(claim_id)                 → bool
```

### 3.5 Rule meta mutation (5)

```text
register_rule(definition)                                  → None
update_rule_stats(rule_id, rule_version, *,
                  firing_delta, true_delta, false_delta,
                  observed_precision, false_positive_rate) → None
register_hint_evidence_types(types)                        → None
unregister_hint_evidence_types(types)                      → None
clear_hint_evidence_types()                                → None
```

### 3.6 Restore boundary (1)

```text
from_snapshot(snapshot)                                    → Engine  (classmethod)
```

### 3.7 Cross-check

```text
read-only             19
mutation add           6
mutation register      3
lifecycle transition   6
rule meta mutation     5
restore                1
                     ----
total                 40   ✓
```

Note on `from_snapshot`: it constructs a new Engine and may invoke `_migrate_snapshot_*` helpers internally (snapshot schema migration). It is therefore NOT classified as read-only despite returning a new object rather than mutating an existing one — PR49 §5 explicitly excludes schema migration from the read-only definition.

---

## 4. Read-only method check against PR49 §5

PR49 §5 defines "read-only" by 6 must-hold conditions. Each of the 19 read-only candidates is verified below.

```text
PR49 §5 must-hold conditions:
  C1  no state mutation
  C2  no lifecycle transition
  C3  no recomputation different from formula
  C4  no schema migration
  C5  no new judgment creation
  C6  no domain vocabulary injected
```

### 4.1 Simple object getters (8)

```text
get_entity / get_observation / get_claim / get_evidence /
get_gap / get_relation / get_rule / get_rule_stats

C1  ✓ pure dict lookup; no _next_id mutation
C2  ✓ no *_if_ready invoked
C3  ✓ returns the stored dataclass; no recomputation
C4  ✓ no migration touched
C5  ✓ returns the stored object only
C6  ✓ integer types only (entity_type / claim_type / ...);
       no domain string surfaces
verdict: read-only ✓ (all 6 conditions)
```

### 4.2 List / tuple per-claim queries (6)

```text
evidences_for_claim(claim_id)             → list[Evidence]
gaps_for_claim(claim_id)                  → list[Gap]
contradictions_for_claim(claim_id)        → tuple[int, ...]
active_contradictions_for_claim(claim_id) → tuple[int, ...]
resolved_contradictions_for_claim(claim_id) → tuple[int, ...]
active_contradictions_by_freshness(claim_id) → tuple[int, ...]

C1  ✓ pure read from internal index dicts
C2  ✓ no transition
C3  ✓ no recomputation; reads stored set/list
C4  ✓ no migration
C5  ✓ no new judgment produced
C6  ✓ integer / dataclass only
verdict: read-only ✓ (all 6 conditions)
```

### 4.3 History / freshness / resolution queries (3)

```text
claim_lifecycle_history(claim_id)  → tuple[ClaimLifecycleEvent, ...]
evidence_freshness(evidence_id)    → int
gap_resolution(gap_id)             → int | None

C1  ✓ reads from _claim_lifecycle_events / freshness counter /
       _gap_resolutions
C2  ✓ no transition
C3  ✓ freshness is an integer counter read; no recomputation
       beyond a stored difference
C4  ✓ no migration
C5  ✓ no new judgment
C6  ✓ integers only
verdict: read-only ✓ (all 6 conditions)
```

### 4.4 Effective confidence query (1)

```text
compute_effective_confidence(claim_id) → ScoreValue

C1  ✓ no mutation; pure composition of 7 modifiers
C2  ✓ no transition; reads current status only
C3  conditional discussion:
       the formula recomputes effective confidence each call,
       but always from the SAME stored modifier formula
       (PR12~PR21 / PR23/24/26/29/34-O §46 / PR36-PKG §48.7).
       PR49 §5 forbids "recomputation different from formula",
       NOT formula execution itself. Returning the formula's
       output for current Engine state is the intended
       read-only behavior.
       verdict: ✓
C4  ✓ no migration
C5  conditional discussion:
       the returned ScoreValue is a derived decision-support
       signal, NOT a new "judgment" in the lifecycle sense.
       PR43-C §4.7 and PR44-D AP-CF-1 already lock this as
       a signal, not a probability or verdict.
       verdict: ✓
C6  ✓ integer claim_id only; no domain vocabulary
verdict: read-only ✓ (all 6 conditions)

The audit notes that `compute_effective_confidence` sits closest to
the formula boundary among the 19 candidates. Any future wrapping
must NOT introduce caching that diverges from the formula's
computed value, NOT introduce alternate "summary scores", and
NOT rename the return type to suggest probability.
```

### 4.5 Snapshot read (1)

```text
to_snapshot() → dict[str, Any]

C1  ✓ pure read across all internal storages; no mutation
C2  ✓ no transition
C3  ✓ no recomputation; serializes current state per
       PR35-O7 6×6 symmetry
C4  ✓ no migration (migration only happens on from_snapshot)
C5  ✓ no new judgment; the dict mirrors current state
C6  ✓ integer registries / serialized dataclasses only;
       no domain vocabulary
verdict: read-only ✓ (all 6 conditions)

Note: to_snapshot is "read-only" in the sense of PR49 §5, but
the resulting dict is the FULL Engine state with 18 top-level
keys (PR36-PKG _LOCKED frozenset). For LLM Context Packet use,
the dict is typically TOO LARGE / TOO LOW-LEVEL; a wrapper that
extracts only the Context Packet fields below is preferable
(see §6).
```

### 4.6 Verdict summary (4.1 ~ 4.5)

```text
19 read-only candidates checked.
All 19 pass all 6 must-hold conditions of PR49 §5.

No candidate is rejected.
No candidate is borderline (compute_effective_confidence and
to_snapshot received discussion notes but pass).
```

---

## 5. Context packet field gap analysis

The LLM Context Packet field list (`direction_rag_framework_proposal_layer.md §10`) is mapped against the 19 read-only methods.

```text
Required field                       Source                           Status
─────────────────────────────────────────────────────────────────────────────
claim summary
  subject_id / claim_type            get_claim(claim_id)               ✓
  status                              get_claim(claim_id).status        ✓
  base_confidence                     get_claim(claim_id).base_confidence ✓
  effective_confidence                compute_effective_confidence(...)  ✓

supporting evidence summaries
  per-evidence (id, type, strength)   evidences_for_claim(claim_id)     ✓
  freshness per evidence              evidence_freshness(evidence_id)    ✓ (N+1)

unresolved gaps
  per-gap (id, gap_type,              gaps_for_claim(claim_id)           ✓
            required_evidence_type,
            severity)
  resolution status                   gap_resolution(gap_id)             ✓ (N+1)

active contradictions
  evidence_ids                        active_contradictions_for_claim    ✓
                                       or
                                       active_contradictions_by_freshness ✓
  Evidence objects per id              get_evidence(evidence_id)          ✓ (N+1)

resolved contradictions
  evidence_ids                        resolved_contradictions_for_claim  ✓
  Evidence objects per id              get_evidence(evidence_id)          ✓ (N+1)

lifecycle history
  events                               claim_lifecycle_history(claim_id) ✓

rule binding
  rule_id / rule_version              get_claim(claim_id).rule_id /
                                       .rule_version                     ✓
  rule maturity / prior_confidence    get_rule(rule_id, rule_version)    ✓
  rule_stats                           get_rule_stats(rule_id, version)  ✓

allowed proposal types                consumer-side policy                N/A
forbidden conclusions                 consumer-side policy                N/A
```

### 5.1 Coverage summary

```text
Engine-owned packet fields covered by existing public methods:  100 %
Consumer-side policy fields (out of Engine scope):              2 fields
  - allowed proposal types
  - forbidden conclusions

These two fields are intentionally NOT Engine-owned; they belong
to the Cerberus-side proposal layer (direction_rag_framework_proposal_layer
§ 6 / § 8).
```

### 5.2 N+1 query observation

Several composite fields require N additional get_* calls per parent claim:

```text
supporting evidence summaries  → 1 evidences_for_claim
                                 + N evidence_freshness
unresolved gaps                 → 1 gaps_for_claim
                                 + N gap_resolution
active contradictions          → 1 active_contradictions_for_claim
                                 + N get_evidence
resolved contradictions         → 1 resolved_contradictions_for_claim
                                 + N get_evidence
```

This N+1 pattern is a *composition cost* for the external wrapper, not a *missing capability* of the Engine. The wrapper absorbs it as a per-claim assembly loop.

The audit deliberately does NOT propose a new "claim_context_packet" or "claim_view" public method to fold the N+1 — see § 7 for the source-change risk analysis.

---

## 6. Existing-method composition candidates

A reference Engine Context Packet assembly using only the 19 read-only methods (no new method, no source change):

```text
def build_engine_context_packet(engine, claim_id) -> dict:
    claim = engine.get_claim(claim_id)
    effective = engine.compute_effective_confidence(claim_id)

    rule = engine.get_rule(claim.rule_id, claim.rule_version)
    rule_stats = engine.get_rule_stats(claim.rule_id, claim.rule_version)

    evidences = engine.evidences_for_claim(claim_id)
    evidence_summaries = [
        {
            "evidence_id": ev.id,
            "evidence_type": ev.type,
            "strength": ev.strength,
            "freshness": engine.evidence_freshness(ev.id),
        }
        for ev in evidences
    ]

    gaps = engine.gaps_for_claim(claim_id)
    gap_summaries = [
        {
            "gap_id": g.id,
            "gap_type": g.gap_type,
            "required_evidence_type": g.required_evidence_type,
            "severity": g.severity,
            "resolution": engine.gap_resolution(g.id),
        }
        for g in gaps
    ]

    active_contras = engine.active_contradictions_for_claim(claim_id)
    resolved_contras = engine.resolved_contradictions_for_claim(claim_id)

    active_contra_summaries = [
        engine.get_evidence(eid) for eid in active_contras
    ]
    resolved_contra_summaries = [
        engine.get_evidence(eid) for eid in resolved_contras
    ]

    history = engine.claim_lifecycle_history(claim_id)

    return {
        "claim": {
            "claim_id": claim_id,
            "subject_id": claim.subject_id,
            "claim_type": claim.claim_type,
            "status": claim.status,
            "base_confidence": claim.base_confidence,
            "effective_confidence": effective,
        },
        "rule": {
            "rule_id": claim.rule_id,
            "rule_version": claim.rule_version,
            "maturity": rule.maturity,
            "prior_confidence": rule.prior_confidence,
            "rule_stats": rule_stats,
        },
        "evidences": evidence_summaries,
        "gaps": gap_summaries,
        "active_contradictions": active_contra_summaries,
        "resolved_contradictions": resolved_contra_summaries,
        "lifecycle_history": history,
    }
```

This pseudocode is **NOT** a proposed addition to `ragcore`. It is an audit artifact showing that the composition is achievable on the consumer side without any Engine change.

The function:

```text
- uses only the 19 read-only methods listed in §3.1
- introduces no new public symbol on Engine
- does not access any private attribute
- does not import any external package
- does not introduce domain vocabulary
- satisfies all 6 must-hold conditions of PR49 §5
```

---

## 7. Ragcore source-change risk analysis

This section evaluates the alternative of adding new ragcore read methods (e.g., a hypothetical `claim_context_packet(claim_id)`) instead of letting the wrapper compose existing methods.

### 7.1 Apparent benefit

```text
- single-call API for consumers
- reduces N+1 by 1 round-trip per claim
- denser type contract (one return shape)
```

### 7.2 Concrete risks

```text
R1  ragcore.__all__ promotion
    A new public packet method must be added to the frozen
    48-symbol export set or to the 40 Engine public methods.
    PR44-D AP-X-7 names this as "adapter-specific symbol
    promoted into ragcore.__all__" anti-pattern.

R2  Return type lock-in
    Any new packet method defines a public shape (dict keys
    and types). The shape becomes part of the contract surface
    (parallel to PR32-V 6 frozen key sets and PR36-PKG 18
    snapshot top-level keys). Future Cerberus / external
    consumers may shape Context Packets differently; locking
    one shape inside ragcore eliminates that freedom.

R3  Domain bias
    "Context Packet" naming originates from
    direction_rag_framework_proposal_layer §10, which is a
    Cerberus-side / LLM-side concept. Embedding it into
    ragcore would inject a usage-pattern bias into the
    framework, partially violating
    direction_rag_framework_rag_agnostic and PR44-D AP-X-6
    (domain vocabulary intrusion).

R4  Future evolution friction
    PR49 explicitly locks judgment semantics as frozen and read
    surface as "thawable only under §5 read-only definition".
    Adding new ragcore read methods now would re-freeze a wider
    surface than necessary; consumers may later need different
    shapes.

R5  N+1 is not a correctness issue
    Composite packet building is per-claim and small
    (typically O(evidence_count + gap_count + contradiction_count)
    per claim). The N+1 cost is a consumer-side optimization
    concern, NOT a framework correctness issue.

R6  PR48-A AST equivalence pattern
    PR48-A demonstrated that comment-only changes preserve AST
    equivalence True. Adding a new method breaks AST equivalence
    even though the new method may be behavior-preserving. The
    bar for any new public method must be very high.
```

### 7.3 Risk verdict

```text
Risks R1 ~ R4 are structural: adding a new ragcore read method
locks a shape and a name in the framework's public surface that
should belong to the consumer side.

R5 is a quantitative observation: N+1 is bounded by per-claim
collection sizes and is absorbed by the wrapper.

R6 is a pattern-preservation observation: the framework has
maintained AST-level discipline; widening the public surface
should not be the first move.

Risk verdict: ragcore source change is NOT justified by the
current audit findings. The composition in §6 satisfies every
documented Context Packet need without any of R1 ~ R6.
```

---

## 8. PR51 entry conclusion

```text
Conclusion A — external wrapper sufficient

PR51 should start as an external EngineInspector wrapper.
ragcore source change is not required for the Minimal Claim
Read Query MVP.
```

### 8.1 Justification

```text
- All 19 read-only methods pass PR49 §5 6 must-hold (§4).
- All Engine-owned Context Packet fields are obtainable via
  existing-method composition (§5, §6).
- Adding a new ragcore read method would incur risks R1 ~ R6
  with no offsetting correctness benefit (§7).
- The composition wrapper assembles a Context Packet without
  any private-attribute access, any new public symbol, or any
  domain vocabulary injection.
```

### 8.2 What this conclusion means for PR51

```text
PR51 should:
  - implement the wrapper on the Cerberus-side
    (or in a future external consumer repository)
  - call only the 19 read-only public methods listed in §3.1
  - return a Context Packet shaped to that consumer's needs
  - NOT propose any ragcore source change
  - NOT propose adding to ragcore.__all__
  - NOT define a "canonical packet" shape inside ragcore

PR51 should NOT:
  - enter the 2순위 (ragcore public method addition) path
  - assume the audit authorized any source change
  - treat the §6 pseudocode as a ragcore patch
```

### 8.3 What would change this conclusion

The audit's Conclusion A may be revisited only if all of the following hold:

```text
(α) a concrete consumer attempt demonstrates that the
    composition pattern in §6 cannot assemble a needed packet
    field, AND
(β) the missing capability is NOT a consumer-side policy
    (allowed proposal types / forbidden conclusions / domain
     vocabulary), AND
(γ) the missing capability requires private-attribute access
    or violates PR49 §5 6 must-hold from the consumer side,
    AND
(δ) user issues a separate authorization lock per PR49 §8 (b),
    AND
(ε) the proposed addition honors PR47 §3 + §12 + PR49 §5 +
    PR44-D AP-* set per PR49 §8 (c).
```

If any of (α) ~ (ε) is missing, PR51 stays at 1순위 (external wrapper) and the audit's Conclusion A holds.

---

## 9. Do-not-touch boundary cross-check

PR50 audit itself touches no source. Any future PR51 (1순위 or, hypothetically, 2순위) must cross-check the following:

```text
PR47 §3 (10 do-not-touch items, internal refactor audit):
  1.  7-modifier composition formula
  2.  6 lifecycle helper internal decision logic
  3.  snapshot serialize/restore symmetry  (6 × 6, PR35-O7)
  4.  40 public method signatures
  5.  public observable behavior of every method
  6.  18 snapshot top-level keys
  7.  effective_confidence modifier call chain
  8.  report / read-surface 6 frozen key sets
  9.  ragcore.__all__ 48 symbols
  10. adapter / Cerberus integration code (absent must stay absent)

PR49 §3 (10 frozen judgment semantics, read-surface mirror):
  same 10 items, re-asserted in the read-surface context.

PR49 §5 (6 read-only must-hold conditions):
  C1 no state mutation
  C2 no lifecycle transition
  C3 no recomputation different from formula
  C4 no schema migration
  C5 no new judgment creation
  C6 no domain vocabulary injected

PR44-D AP-* (selected for read-surface relevance):
  AP-X-4  compute_effective_confidence as truth probability
  AP-X-6  domain vocabulary intrusion into ragcore source
  AP-X-7  adapter-specific symbol promoted into ragcore.__all__
  AP-X-8  private state / helper / constant dependence
  AP-CF-1 effective_confidence read as "truth probability"
  AP-CF-2 static threshold cutoff treated as ground truth
```

PR50 audit itself violates none of the above. The Conclusion A path (external wrapper) also violates none of the above by construction (consumer-side code is outside ragcore).

---

## 10. Exit criteria

PR50 closes when ALL of the following hold:

```text
[ ] docs/architecture/ENGINE_READ_SURFACE_AUDIT.md added
[ ] pytest 1145 passing (unchanged from PR49 baseline)
[ ] ragcore.__all__ 48 symbols (unchanged)
[ ] Engine public methods 40 (unchanged)
[ ] snapshot schema_version 2 (unchanged)
[ ] snapshot top-level keys 18 (unchanged)
[ ] ragcore source change 0 bytes
[ ] test change 0
[ ] new public symbol 0
[ ] new engine behavior 0
[ ] contract §51 not added
[ ] all 40 public methods classified (19 + 6 + 3 + 6 + 5 + 1 = 40)
[ ] all 19 read-only candidates checked against PR49 §5 6 conditions
[ ] all Engine-owned Context Packet fields mapped to existing methods
[ ] §6 composition pseudocode uses zero private attributes
[ ] PR51 entry conclusion stated explicitly (Conclusion A or B)
[ ] PR51 / PR52 not auto-scheduled
```

PR50 's job is to write the audit and conclude. It does not perform any thaw, add any method, or schedule PR51.

---

## 11. Closing meaning

```text
PR50 audits what is already readable.

It does not add a read method.
It does not authorize PR51 source change.
It concludes that the existing 19 read-only public methods
satisfy all documented Context Packet needs through
consumer-side composition.

PR51 enters as an external EngineInspector wrapper.
ragcore source remains unchanged.

The freeze of judgment semantics is intact.
The thaw policy of the read surface is intact.
The wrapper-first conclusion is recorded for PR51.
```

Locked closing sentences:

```text
We audit the readable surface before adding any read surface.
읽기 표면을 추가하기 전에, 먼저 현재 읽을 수 있는 표면을 감사한다.

PR50 conclusion: external wrapper sufficient.
PR51 enters at 1순위 (external EngineInspector).
ragcore source change is not authorized by this audit.

PR51 / PR52 are NOT automatically entered.
```
