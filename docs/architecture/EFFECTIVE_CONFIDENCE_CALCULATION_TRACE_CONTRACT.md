# Effective Confidence Calculation Trace Contract

```
PR76-M07
type:    runtime feature contract (read-only)
status:  normative
date:    2026-06-19
base:    main 9f576a5 (PR75-M06 — Downstream Result Re-entry
                       Contract)
```

## Core sentences

```
An EffectiveConfidenceTrace explains how one existing Engine
effective-confidence value was composed.

It does not change the value, judge the Claim, or convert
effective confidence into probability.

  trace.effective_confidence
    == Engine.compute_effective_confidence(claim_id)

  trace.calculation_policy_id
    identifies calculation semantics

  trace.source_state_identity
    identifies the observed Engine runtime state basis

  calculation policy identity
    != Engine state identity
    != snapshot schema identity
    != packet identity
```

---

## §0 Scope limitation

PR76-M07 introduces ONE frozen read-only value type
(`EffectiveConfidenceTrace`) and ONE read-only public Engine
method (`Engine.compute_effective_confidence_with_trace`) that
return a typed breakdown of an existing Engine
effective-confidence calculation. The contract is normative
for the new public surface and **does not** introduce any
state-mutating method, snapshot field, PR51 packet field,
database backing, dispatcher, executor, RuleStats provenance,
probability claim, verdict, or lifecycle recommendation.

### §0.1 In scope

```
- public value type EffectiveConfidenceTrace
- public method Engine.compute_effective_confidence_with_trace
- private calculation core shared with the existing API
- module-private policy identity constant
- equality with the existing compute_effective_confidence
- modifier breakdown semantics (6 modifiers, unchanged values)
- failure semantics (unknown claim_id -> KeyError)
- relationship to M03 read-consistency vocabulary
- relationship to M04 EngineStateIdentity primitive
- relationship to PR32 consumer-side report shape
- relationship to PR51 packet (unchanged)
```

### §0.2 Out of scope

```
- effective-confidence formula change
- modifier value change
- modifier applicability condition change
- modifier ordering change
- Claim.base_confidence semantics change
- Evidence.strength semantics change
- RuleStats calculation / update semantics change
- lifecycle transition condition change
- Gap / contradiction semantics change
- PR51 packet key addition
- packet binding / CAPTURE_BOUND / CURRENTLY_MATCHED /
  packet STALE
- snapshot schema_version change
- snapshot top-level key change
- trace snapshot persistence
- automatic revalidation
- automatic mutation
- report / verdict / probability API
- M08 reference operation
- M09 RuleStats update provenance
- network / LLM / adapter / executor
```

### §0.3 Hard locks

```
calculation_policy_id
  != snapshot schema_version
  != package version
  != module hash
  != commit SHA
  != EngineStateIdentity

effective_confidence
  != probability
  != truth likelihood
  != Claim verdict
  != lifecycle readiness

EffectiveConfidenceTrace
  != Engine truth record
  != mutation receipt
  != ReviewedMutationRequest
  != lifecycle decision
```

---

## §1 Investigation origin — M01 OC-D

M01 (PR70-M01) Lane B surfaced the `effective-confidence
trace diagnosis` discontinuity:

```
B (engine_read_and_proposal):
  effective_confidence_trace_diagnosis  ->  OC-D
```

Today's Engine computes one final `ScoreValue` via
`compute_effective_confidence(claim_id)`. The composition uses
six private modifier helpers, but the modifier values, the
composition policy identity, and the Engine state identity at
calculation time are not surfaced through any public API.

OC-D is the conceptual discontinuity between **the
calculation result** and **the explanation of how that result
was produced**. M07 closes OC-D by adding a read-only typed
trace that exposes the inputs, the components, the policy
identity, and the source-state identity of the same
calculation, without altering it.

---

## §2 Empirical baseline

```
main at PR76-M07 start:    9f576a5b072f4d194083d9b4c20d997d78c4b787
tests:                      1517 passing
Engine public methods:      41
Engine private methods:     19
state-mutating public:      20
read-only public:           19
serialization boundary:      2
ragcore.__all__:            49
snapshot schema_version:     2
snapshot top-level keys:    18
PR51 packet keys:            7
```

PR51 packet keys (M03-locked names, unchanged):

```
claim
effective_confidence
supporting_evidence
contradictions
active_contradictions
unresolved_gaps
lifecycle_history
```

After M07 lands:

```
Engine public methods:      42  (+compute_effective_confidence_with_trace)
Engine private methods:     20  (+_compute_effective_confidence_core)
state-mutating public:      20  (set unchanged)
read-only public:           20  (+compute_effective_confidence_with_trace)
serialization boundary:      2  (set unchanged)
ragcore.__all__:            50  (+EffectiveConfidenceTrace)
snapshot schema_version:     2  (unchanged)
snapshot top-level keys:    18  (set unchanged)
PR51 packet keys:            7  (set unchanged, same order)
```

---

## §3 Existing calculation semantics (unchanged by M07)

The existing public method retains its signature, docstring,
exception type, and return-value semantics verbatim:

```
def compute_effective_confidence(self, claim_id: int)
    -> ScoreValue
```

The calculation is:

```
effective
  = base_confidence
  × status_modifier
  × freshness_modifier
  × gap_modifier
  × count_modifier
  × rule_stats_modifier
  × evidence_type_modifier
```

Modifier helpers (private):

```
_status_modifier_for_claim
_freshness_modifier_for_claim
_gap_modifier_for_claim
_count_modifier_for_claim
_rule_stats_modifier_for_claim
_evidence_type_modifier_for_claim
```

M07 does NOT modify any modifier helper's body, value table,
input set, or applicability condition.

---

## §4 Public trace type

```
@dataclass(frozen=True)
class EffectiveConfidenceTrace:
    claim_id: int
    source_state_identity: EngineStateIdentity
    calculation_policy_id: str
    base_confidence: ScoreValue
    status_modifier: float
    freshness_modifier: float
    gap_modifier: float
    count_modifier: float
    rule_stats_modifier: float
    evidence_type_modifier: float
    effective_confidence: ScoreValue
```

### §4.1 Field-order lock

The field order above is part of the contract. Reordering is a
breaking change.

### §4.2 Field semantics

```
claim_id                  the Claim whose effective confidence
                          was computed
source_state_identity     value-equal to Engine.state_identity()
                          at trace construction
calculation_policy_id     stable string identifier (see §7)
base_confidence           the Claim's base_confidence at
                          calculation time (already a
                          ScoreValue snapshot per §13.x of
                          DATA_CONTRACT)
status_modifier           float from _status_modifier_for_claim
freshness_modifier        float from _freshness_modifier_for_claim
gap_modifier              float from _gap_modifier_for_claim
count_modifier            float from _count_modifier_for_claim
rule_stats_modifier       float from _rule_stats_modifier_for_claim
evidence_type_modifier    float from _evidence_type_modifier_for_claim
effective_confidence      ScoreValue == base_confidence ×
                          (the six modifier floats)
```

### §4.3 Forbidden fields

The trace MUST NOT carry any of:

```
probability
verdict
risk label
lifecycle recommendation
Claim status recommendation
modifier reason prose
wall-clock timestamp
packet identity
snapshot digest
automatic stale flag
caller identity
RuleStats update provenance
freshness comparison verdict
```

### §4.4 Storage

The trace is a read-only return value. Engine MUST NOT store
it in any internal field. It is NOT persisted in any
snapshot field, M01 scaffold report field, or PR51 packet
field.

---

## §5 Public Engine method

```
def compute_effective_confidence_with_trace(
    self,
    claim_id: int,
) -> EffectiveConfidenceTrace
```

### §5.1 Read-only

`compute_effective_confidence_with_trace` is a read-only
public method. Calling it MUST NOT advance the M04 revision
counter, mutate `_claims` / `_evidences` / `_gaps` / etc., or
modify any snapshot-visible state.

### §5.2 Exception semantics

```
unknown claim_id  -> KeyError
```

The exception type and the timing (raised before any
modifier helper is called) match the existing
`compute_effective_confidence` semantics.

### §5.3 Determinism

For an unchanged Engine state, repeated calls return
EffectiveConfidenceTrace values that compare equal under
value equality of all 11 fields.

---

## §6 Single calculation core

The two public methods MUST share one private calculation
core. M07 introduces:

```
def _compute_effective_confidence_core(
    self,
    claim_id: int,
) -> EffectiveConfidenceTrace
```

`_compute_effective_confidence_core` is the sole source of:

```
- the claim-existence check (mirroring the existing API)
- the six modifier helper calls (each called exactly once
  per core invocation)
- the local-variable capture of each modifier float
- the multiplication that yields effective_confidence
- the construction of EffectiveConfidenceTrace
```

Both public methods delegate:

```
compute_effective_confidence(claim_id)
  = _compute_effective_confidence_core(claim_id).effective_confidence

compute_effective_confidence_with_trace(claim_id)
  = _compute_effective_confidence_core(claim_id)
```

Forbidden: two different multiplication sites for the same
formula. M07 explicitly forbids retaining the historical
inline multiplication in `compute_effective_confidence` while
adding a second multiplication site in
`compute_effective_confidence_with_trace`. The historical
inline multiplication is replaced by a delegation to the
core; the resulting `ScoreValue` is byte-identical to the
prior return value.

---

## §7 Calculation policy identity

### §7.1 Constant

A module-private constant is added:

```
_EFFECTIVE_CONFIDENCE_POLICY_ID = "ragcore.effective-confidence.v1"
```

### §7.2 Visibility

The constant is NOT re-exported via `ragcore.__all__`. The
only observable surface is `EffectiveConfidenceTrace
.calculation_policy_id`.

### §7.3 Meaning

`calculation_policy_id` identifies the **semantic policy**
under which the trace was produced — i.e., which composition
of modifier helpers, in which order, with which value tables,
was applied.

### §7.4 Bump conditions

A future PR MUST bump `_EFFECTIVE_CONFIDENCE_POLICY_ID` when
ANY of the following changes:

```
- modifier component added / removed
- modifier composition rule (multiplication, ordering)
  changed
- modifier value table or tier changed
- modifier input-set semantics changed
- fallback / sentinel semantics changed
```

### §7.5 Non-bump conditions

The id MUST NOT be bumped for any of:

```
- documentation rewording
- new tests
- internal variable renaming
- performance-only refactor that preserves observed semantics
- equivalent-meaning code reorganization
```

### §7.6 Forbidden equivalences

```
calculation_policy_id
  != snapshot schema_version (or its stringification)
  != ragcore package version
  != module hash
  != commit SHA
  != EngineStateIdentity.engine_token
  != EngineStateIdentity.revision
```

---

## §8 Source Engine state identity

### §8.1 Field

`EffectiveConfidenceTrace.source_state_identity` is a
`EngineStateIdentity` value obtained at trace construction:

```
source_state_identity = self.state_identity()
```

### §8.2 Read-only call

`state_identity()` is a M04 read-only public method (M04
§1.2). Calling it does not mutate Engine state and does not
advance the revision (M04 §2 — the advance discipline applies
only to the 20 state-mutating methods, of which
`state_identity()` is not one). The trace call therefore
leaves the revision unchanged.

### §8.3 Supported comparison

The only supported comparison is value equality:

```
trace.source_state_identity == engine.state_identity()
```

A consumer may use this comparison to determine whether the
Engine state visible at calculation time is value-equal to the
Engine state visible later. The result of that comparison is
scoped to the comparison moment; it is NOT a freshness
guarantee or a transaction window (M05 §9; M04 §6 / §7).

### §8.4 Not promoted to packet semantics

```
source_state_identity
  != PR51 packet capture identity
  != CAPTURE_BOUND
  != CURRENTLY_MATCHED
  != STALE
  != cross-process continuity
  != atomic capture
  != snapshot digest
  != cryptographic state proof
```

M07 does NOT extend M03 §7 packet-binding vocabulary, M03 §8
CAPTURE_BOUND requirements, M03 §9 CURRENTLY_MATCHED
requirements, or M03 §10 STALE boundary.

### §8.5 Restore behavior

A trace's `source_state_identity` corresponds to a specific
`engine_token` and `revision` pair. After
`Engine.from_snapshot(...)`, the restored Engine receives a
fresh `engine_token` (M04 §4.4). Therefore the prior trace's
`source_state_identity` cannot be value-equal to the restored
Engine's `state_identity()`. This is intentional and matches
the M05 §13 / M04 §11 process-restart / restore discipline.

---

## §9 Modifier breakdown semantics

The six modifiers exposed in the trace mirror the existing
private helper return values exactly. M07 does NOT change any
helper's body.

### §9.1 status_modifier

```
candidate  -> 1.0
confirmed  -> 1.0
disputed   -> 0.5
refuted    -> 0.0
```

### §9.2 freshness_modifier

```
no active contradiction
  -> 1.0

one or more active contradictions
  -> 1.0 − most_recent.strength × WEIGHT
  (resolved contradictions excluded;
   "most recent" = highest evidence_id among active
   contradictions; see PR11-B / §27)
```

### §9.3 gap_modifier

```
0 unresolved gaps   -> 1.0
1 unresolved gap    -> 0.9
2 unresolved gaps   -> 0.8
3+ unresolved gaps  -> 0.7
```

Resolved gaps are excluded; shared-gap reference semantics
are preserved (PR4-PR4S / §16).

### §9.4 count_modifier

```
0 or 1 active contradiction
  -> 1.0

2+ active contradictions
  -> penalty based on the average strength of active
     contradictions (resolved contradictions excluded;
     unchanged from existing helper)
```

### §9.5 rule_stats_modifier

```
sentinel rule id 0       -> 1.0
RuleStats lookup miss    -> 1.0
observed_precision None  -> precision modifier 1.0
otherwise                 -> existing maturity × observed-
                            precision composition (unchanged)
```

`false_positive_rate` is NOT used by the existing helper and
is NOT used by M07.

### §9.6 evidence_type_modifier

```
hint set empty                    -> 1.0
no direct supporting evidence     -> 1.0
all direct evidence in hint set   -> 0.9
mixed / non-hint included         -> 1.0
```

Contradiction evidence and resolved contradiction evidence
are excluded from the "direct supporting evidence" set
(PR21-L Sub-decision AA / §33).

---

## §10 Equality with compute_effective_confidence

For every admissible Engine state and every existing
`claim_id`:

```
engine.compute_effective_confidence(claim_id)
  ==
engine.compute_effective_confidence_with_trace(
    claim_id
).effective_confidence
```

The equality holds because both methods delegate to the same
private core (§6). M07 enforces this invariant by test.

`compute_effective_confidence` retains its public signature,
return type, exception type, and docstring meaning. Existing
consumers do not need to migrate.

---

## §11 Read-only and failure semantics

### §11.1 Read-only

Both `compute_effective_confidence` and
`compute_effective_confidence_with_trace` are read-only:

```
Engine.state_identity() unchanged before vs. after the call
to_snapshot() unchanged before vs. after the call
Claim unchanged
RuleStats unchanged
lifecycle history unchanged
```

The M04 advance discipline (M04 §2) applies only to the 20
state-mutating public methods. The two confidence APIs are
read-only and are not in that set; the new
`compute_effective_confidence_with_trace` joins the read-only
group documented at M04 §1.2 alongside `state_identity()`.

### §11.2 KeyError on unknown claim

```
unknown claim_id  -> KeyError
```

The KeyError type, the error label format, and the raise
timing are preserved. The trace method does NOT wrap the
failure into an `EffectiveConfidenceTrace` with an `error`
field; failure is signaled by exception only.

### §11.3 Other exceptions are not introduced

M07 introduces NO new exception type. M07 does NOT raise
`ValueError`, `TypeError`, or any other exception that the
existing `compute_effective_confidence` does not already
raise.

---

## §12 PR51 packet relationship

The PR51 packet builder (`examples/inspector/engine_inspector
.py`) is NOT modified by M07. The packet's 7 keys (M03 §13,
M06 §10) remain exactly as recorded:

```
claim
effective_confidence
supporting_evidence
contradictions
active_contradictions
unresolved_gaps
lifecycle_history
```

The packet's `effective_confidence` value remains a
`ScoreValue`. The packet does NOT gain:

```
effective_confidence_trace
calculation_policy_id
source_state_identity
modifier_breakdown
```

A consumer that wants the trace MUST call
`compute_effective_confidence_with_trace` separately. The
packet remains `UNBOUND + UNKNOWN` (M03 §7.1 / §7.2; M06
§10).

---

## §13 PR32 report-surface relationship

The consumer-assembled report shape established by PR32 is
NOT modified by M07. In particular, the PR32 report dict
exposes a Boolean "pressure" summary, NOT modifier values.
M07 does NOT introduce:

```
Engine.claim_report(...)
Engine.effective_confidence_report(...)
any new dict-shaped helper
```

The PR32 frozen report key set is preserved. The new typed
trace API is a separate surface (`EffectiveConfidenceTrace`
value type), not a report mutation.

```
PR32 report shape   = consumer-assembled boolean pressure summary
                      (unchanged)
M07 trace shape     = Engine-produced typed calculation artifact
                      (new)
```

---

## §14 M03 / M04 relationship

### §14.1 M03 (Engine Read Consistency)

M07 consumes M04's `EngineStateIdentity` value equality as
the only mechanical comparison basis for
`trace.source_state_identity`. M07 does NOT change M03's
packet-binding vocabulary, the §7 two-axis matrix, the §8
CAPTURE_BOUND requirements, the §9 CURRENTLY_MATCHED
requirements, the §10 STALE boundary, or the §13 PR51 / PR53
relationship.

PR51 packets remain `UNBOUND + UNKNOWN`. M07 does NOT lift
them out of that combination.

### §14.2 M04 (Engine State Identity Primitive)

M07's trace exposes the M04 value type (`EngineStateIdentity`)
as a trace field. M07 does NOT modify:

```
- the EngineStateIdentity value type shape (§1)
- the M04 admission discipline (§3 C5)
- the revision advance discipline across the 20 state-
  mutating methods (§2.1 ~ §2.6)
- the snapshot exclusion (§5)
- the from_snapshot() fresh-lineage behavior (§4.4)
```

`compute_effective_confidence_with_trace` is classified as
read-only and does NOT advance the revision (§11.1).

---

## §15 Snapshot / restore / process restart

### §15.1 Snapshot

The snapshot's 18 top-level keys are unchanged. M07 does NOT
add any of:

```
effective_confidence_trace
trace_log
calculation_policy_id
last_traced_at
```

### §15.2 Restore

`Engine.from_snapshot(...)` continues to allocate a fresh
`engine_token` and `revision = 0`. A previously-issued
`EffectiveConfidenceTrace` therefore cannot be reused to
make claims about the restored Engine's state; its
`source_state_identity` will NOT be value-equal to the
restored `state_identity()` (M04 §4.4; M05 §13).

### §15.3 Process restart

A persisted trace (if a consumer chooses to persist it
outside the framework) carries the historical `engine_token`
and `revision`. After process restart, the new Engine
instance is a fresh runtime lineage. The historical trace's
`source_state_identity` is NOT comparable to the new
Engine's `state_identity()` (M04 §4.5).

### §15.4 No persistence path

M07 does NOT introduce any persistence API for the trace.
Whether a consumer persists the trace, and in what
representation, is consumer policy (M05 §6.1).

---

## §16 Forbidden interpretations

The contract is normative against every interpretation in
this list:

```
effective_confidence == probability
effective_confidence == truth likelihood
effective_confidence == Claim verdict
effective_confidence == lifecycle readiness
calculation_policy_id == snapshot schema_version
calculation_policy_id == package version
calculation_policy_id == module hash
calculation_policy_id == commit SHA
calculation_policy_id == EngineStateIdentity
source_state_identity == packet capture identity
source_state_identity == CAPTURE_BOUND
source_state_identity == CURRENTLY_MATCHED
source_state_identity == STALE
source_state_identity == atomic capture
source_state_identity == cross-process continuity
source_state_identity == cryptographic state proof
trace == Engine truth record
trace == mutation receipt
trace == ReviewedMutationRequest
trace == lifecycle decision
trace == mutation authority
trace == automatic revalidation outcome
```

---

## §17 Public surface migration

### §17.1 ragcore.__all__

Before: 49 symbols (including `EngineStateIdentity` from
PR73-M04). After: 50 symbols. The added symbol is:

```
EffectiveConfidenceTrace
```

It is appended to the Core dataclasses group in
`ragcore/__init__.py` (after `EngineStateIdentity`).

### §17.2 Engine public methods

Before: 41 methods. After: 42 methods. The added method is:

```
compute_effective_confidence_with_trace
```

### §17.3 Engine private methods

Before: 19 methods. After: 20 methods. The added method is:

```
_compute_effective_confidence_core
```

### §17.4 Method classification (M02 §12.1 + §23)

```
state-mutating public methods       20  (set unchanged)
read-only public methods            20  (+ compute_effective_
                                           confidence_with_trace)
serialization boundary               2  (set unchanged)
total                               42
```

`compute_effective_confidence_with_trace` is **read-only / NOT
a M02 mutation candidate target / NOT eligible to appear in a
ReviewedMutationRequest / NOT instrumented to advance the
revision**.

### §17.5 Module-private constant

```
ragcore.engine._EFFECTIVE_CONFIDENCE_POLICY_ID
  = "ragcore.effective-confidence.v1"
```

NOT re-exported. The only observable surface is the trace
field `calculation_policy_id`.

---

## §18 Files locked and invariants

### §18.1 Files M07 may modify

```
ragcore/types.py                (+EffectiveConfidenceTrace)
ragcore/engine.py               (+_EFFECTIVE_CONFIDENCE_POLICY_ID,
                                 +_compute_effective_confidence_core,
                                 +compute_effective_confidence_with_trace,
                                 compute_effective_confidence body
                                 reduced to a delegating one-liner
                                 returning core.effective_confidence)
ragcore/__init__.py             (+EffectiveConfidenceTrace import,
                                 +EffectiveConfidenceTrace in __all__)
docs/architecture/EFFECTIVE_CONFIDENCE_CALCULATION_TRACE_CONTRACT.md
                                (new, this file)
docs/architecture/ENGINE_READ_CONSISTENCY_CONTRACT.md
                                (+§21 Post-M07 addendum)
docs/architecture/ENGINE_STATE_IDENTITY_PRIMITIVE_CONTRACT.md
                                (+§12 Post-M07 addendum)
docs/dev/PR_076_EFFECTIVE_CONFIDENCE_CALCULATION_TRACE.md
                                (new, dev record)
tests/test_effective_confidence_trace.py
                                (new, M07 tests)
tests/test_engine_method_surface_freeze.py
tests/test_engine_ai_readable_usage_recipe.py
tests/test_engine_method_call_playbook_usage.py
tests/test_engine_report_surface.py
tests/test_external_adapter_simulation.py
tests/test_external_engine_inspector.py
tests/test_snapshot_restore_integrity.py
tests/test_engine_state_identity.py
                                (surface-lock count bumps only;
                                 41 -> 42 public,
                                 19 -> 20 private,
                                 49 -> 50 __all__;
                                 + locked symbol set updates)
```

### §18.2 Files M07 must NOT modify

```
examples/inspector/engine_inspector.py
examples/operation/minimal_operational_scaffold.py
tests/test_minimal_operational_scaffold.py
docs/architecture/DOWNSTREAM_RESULT_REENTRY_CONTRACT.md
docs/dev/PR_075_DOWNSTREAM_RESULT_REENTRY_CONTRACT.md
snapshot migration files
pyproject.toml
```

Runtime semantics M07 must NOT modify:

```
Claim
Evidence
Gap
Relation
RuleDefinition
RuleStats
ClaimLifecycleEvent
EngineStateIdentity
```

Modifier helpers M07 must NOT modify the body of:

```
_status_modifier_for_claim
_freshness_modifier_for_claim
_gap_modifier_for_claim
_count_modifier_for_claim
_rule_stats_modifier_for_claim
_evidence_type_modifier_for_claim
```

### §18.3 Behavioral invariants (delta = 0)

```
effective-confidence formula        delta = 0
modifier value table                delta = 0
modifier input set semantics        delta = 0
Claim lifecycle condition           delta = 0
Gap matching / resolution semantics delta = 0
contradiction semantics             delta = 0
RuleStats calculation               delta = 0
PR51 packet shape                   delta = 0
snapshot schema                     delta = 0
dependency surface                  delta = 0
automatic execution                 delta = 0
```

---

## §19 M08 / M09 forward boundary

M07 does NOT close OC-F (M08 complete domain-neutral
reference operation) or OC-G (M09 RuleStats update
provenance). M07 does NOT pre-define M08's reference shape
or M09's provenance vocabulary. M07 does NOT auto-schedule
M08 or M09.

```
PR75-M06   Downstream Result Re-entry                     (OC-E)  CLOSED
PR76-M07   Effective Confidence Calculation Trace        (OC-D)  this PR
PR77-M08   Complete Domain-Neutral Reference Operation   (OC-F)  NOT STARTED
PR78-M09   RuleStats Update Provenance                   (OC-G)  NOT STARTED
```

Separate, explicitly-directed future work NOT auto-scheduled
by M07:

```
- CAPTURE_BOUND PR51 packet binding (OC-C closure follow-up)
- CURRENTLY_MATCHED comparison helper
- mechanical packet STALE detector
- effective_confidence -> probability conversion
- automatic lifecycle decision based on trace
- automatic RuleStats update based on trace
- automatic revalidation worker
```

---

## §20 Closing position

```
M07 closes OC-D at the layer where it actually lives: an
explanation of an existing Engine calculation, surfaced as
one frozen read-only value type and one read-only public
method.

The calculation itself is unchanged. The six modifier
helpers are unchanged. The PR51 packet is unchanged. The
snapshot schema is unchanged. RuleStats semantics are
unchanged. Lifecycle conditions are unchanged.

trace.effective_confidence
  == Engine.compute_effective_confidence(claim_id)
  by construction.

trace.calculation_policy_id
  identifies semantics, not state.

trace.source_state_identity
  identifies state, not freshness or packet binding.

Everything else — a probability conversion, a verdict, a
lifecycle recommendation, a packet-binding helper, a stale
detector, an automatic RuleStats update — remains separate
explicitly-directed future work or M08 / M09 responsibility
and is NOT auto-scheduled by M07.
```

PR76-M07 is opened as **Draft** and is not merged. Closure
language (`CLOSED`) is reserved for the post-squash-merge
state. The M-series sequence after PR76-M07:

```
PR76-M07   Effective Confidence Calculation Trace
                                        (OC-D) OPEN — DRAFT,
                                               NOT MERGED
PR77-M08   Complete Domain-Neutral
           Reference Operation          (OC-F) NOT STARTED
PR78-M09   RuleStats Update Provenance  (OC-G) NOT STARTED
```

No automatic next PR. Framework waits for directive.

---

**Post-merge note (independent audit, 2026-06-27):** PR76-M07 was
squash-merged as GitHub PR #77 (f57cd5da1fd4ab09d93b89bbf3d7bd08b22192be, 2026-06-24) and is CLOSED (merged). The
"opened as Draft / OPEN — DRAFT, NOT MERGED / Framework waits for
directive" closing above is a historical pre-merge process note,
superseded here. No normative content change.
