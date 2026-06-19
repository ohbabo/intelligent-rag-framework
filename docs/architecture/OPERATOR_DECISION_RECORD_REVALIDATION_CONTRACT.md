# Operator Decision Record and Decision-State Revalidation Contract

```text
PR74-M05
type:    docs-only architecture contract
status:  normative
date:    2026-06-19
base:    main 04f591b (PR73-M04 — Engine State Identity
                       Primitive MVP)
```

## Core sentences

```text
An operator decision record preserves a consumer-side decision
and the Engine state identity observed when that decision was
made.

It does not turn the decision into Engine truth, execution
authority, or a state-bound PR51 packet.
```

---

## §0 Scope limitation

PR74-M05 fixes the conceptual obligations of an **operator
decision record** and the policy for **decision-state
revalidation** at the moment a previously recorded decision is
reconsidered. The contract is normative for consumer-side
adapters and **does not** introduce any runtime code, ragcore
symbol, Engine method, snapshot field, packet field, database
table, JSON schema, or serialization format.

### §0.1 In scope

```
- consumer-side operator decision record obligations
- proposal-gate decision persistence
- mutation-review disposition persistence
- decision-time EngineStateIdentity reference
- decision-subject exact-content binding
- decision-state revalidation policy
- stale-for-reuse policy
- supersession / new-review boundary
- process-restart and restore behavior
```

### §0.2 Out of scope

```
- operator decision as ragcore type
- operator decision stored in Engine
- exact database / JSON / timestamp / actor-id format
- canonical content digest
- packet capture identity
- packet atomicity
- packet freshness
- M03 CAPTURE_BOUND implementation
- M03 CURRENTLY_MATCHED / STALE runtime vocabulary
- tool execution
- Engine mutation
- downstream result re-entry
- effective-confidence trace
- RuleStats provenance
```

### §0.3 Things PR74-M05 explicitly does not implement

```
- Python OperatorDecisionRecord dataclass
- TypedDict / NamedTuple / Pydantic model
- JSON Schema
- database schema
- audit-log storage backend
- operator UI
- authentication / authorization
- signature / digest
- Engine method
- dispatcher / executor
- packet-binding helper
- CURRENTLY_MATCHED helper
- packet STALE detector
- automatic revalidation
- automatic downstream execution
```

---

## §1 Investigation origin

The M-series M01 scaffold (PR70-M01) surfaces two stages whose
status is `UNDEFINED`:

```
B8  operator decision record                UNDEFINED
C1  operator decision record                UNDEFINED
```

These stages are labelled `OC-B`. OC-B is the conceptual
boundary between:

```
(a) a consumer-side adapter holding a decision about a
    PR55/PR56-validated proposal (PR57), or
(b) a consumer-side adapter holding a disposition about a
    reviewed EngineInputCandidate (M02 §9),

and the subsequent question of whether that decision is still
valid against the current Engine state at the moment it would
be reused.
```

M02 (PR71-M02) closed the mutation-review handoff up to the
point of explicit invocation. M03 (PR72-M03) declined to
mechanize read consistency. M04 (PR73-M04) introduced the
minimum read-consistency primitive — `EngineStateIdentity` —
that makes mechanical decision-state revalidation possible
without claiming packet capture identity or packet freshness.

PR74-M05 closes the OC-B conceptual boundary at the record
shape and revalidation-policy layer. It does not introduce
storage, schema, or runtime machinery.

---

## §2 Empirical baseline

```
main at PR74-M05 start:   04f591b14b9156bb7b17089ded2670d84745fdd2
tests:                     1517 passing
Engine public methods:     41 (post-M04)
Engine private methods:    19 (post-M04)
state-mutating public:     20 (set unchanged from M02 §12.1)
read-only public:          19 (includes state_identity)
serialization boundary:     2 (to_snapshot, from_snapshot)
ragcore.__all__:           49
snapshot schema_version:    2
snapshot top-level keys:   18
PR51 packet keys:           7
```

PR51 packet keys (M03-locked names, unchanged by M04):

```
claim
effective_confidence
supporting_evidence
contradictions
active_contradictions
unresolved_gaps
lifecycle_history
```

Existing addendum coverage:

```
PR57   OPERATOR_DECISION_BOUNDARY_SPEC          §1 ~ §18
                                                 + closing
M02    REVIEWED_ENGINE_MUTATION_HANDOFF         §1 ~ §22
                                                 + §23 post-M04
M03    ENGINE_READ_CONSISTENCY_CONTRACT         §1 ~ §18
                                                 + §19 post-M04
M04    ENGINE_STATE_IDENTITY_PRIMITIVE          §1 ~ §10
                                                 (no addendum yet)
```

M05 normative addenda land at:

```
PR57  §19  Post-M05 addendum
M02   §24  Post-M05 addendum
M03   §20  Post-M05 addendum
M04   §11  Post-M05 addendum
```

---

## §3 Core boundary statement

```
A consumer-side operator decision record is a persistent
consumer-owned fact about a past consumer-side decision.

It records what was decided, against what subject content, by
whom, on what basis, at what consumer-defined time, and against
which EngineStateIdentity value.

It does not mutate the Engine.
It does not produce a ReviewedMutationRequest.
It does not execute a tool.
It does not bind the PR51 packet to a capture identity.
It does not assert the packet is CURRENTLY_MATCHED or STALE.
It does not authorize automatic revalidation.
```

---

## §4 Two distinct decision families

PR74-M05 freezes two **separate** decision families. A single
record must declare which family it belongs to and must not
carry semantics from the other family.

### §4.1 Family A — PR57 proposal gate

A proposal decision is the operator's disposition of a
proposal that has cleared PR55 (proposal shape) and PR56
(proposal safety) validators.

Permitted conceptual dispositions:

```
accept
reject
rewrite
request-evidence
schedule-manual-inspection
archive
cite
```

### §4.2 Family B — M02 mutation review

A mutation-review decision is the operator's disposition of an
exact-content review of one `EngineInputCandidate` per M02 §9.

Permitted conceptual dispositions:

```
approved
rejected
hold
```

### §4.3 Hard locks between families

```
proposal acceptance
  != mutation review approval

proposal rejection
  != mutation candidate rejection

operator decision record
  != ReviewedMutationRequest

approved mutation review
  -> may permit separate ReviewedMutationRequest materialization
  != automatic request creation
  != Engine invocation

a single `accepted: bool` field
  MUST NOT represent both decision families
```

A record must identify its family. A disposition from one
family must not be interpreted using the other family's
semantics.

---

## §5 Conceptual minimum record content

PR74-M05 freezes **conceptual obligations**, not Python field
names or serialization keys. Every record must conceptually
preserve every item in this list.

```
 1. record identity
    - consumer-assigned opaque identity
    - record-scoped, not Engine-scoped

 2. decision family
    - proposal gate  (PR57 / §4.1)
    - mutation review (M02 / §4.2)

 3. exact decision subject identity
    - proposal identity, or
    - EngineInputCandidate identity

 4. exact decision subject content reference
    - enough to determine whether the reviewed subject changed
    - mechanism remains consumer-defined
      (e.g., content hash, snapshot copy, content store key,
       structured fingerprint, or any consumer scheme)
    - PR74-M05 does NOT mandate a canonical hash

 5. family-scoped disposition
    - from §4.1 (proposal) or §4.2 (mutation review)

 6. decision actor reference
    - consumer-defined identity scheme

 7. decision-time reference
    - representation remains consumer-defined
    - may be wall-clock timestamp, logical sequence, or other
      consumer scheme
    - format is not part of this contract

 8. rationale / decision basis
    - free-form consumer record

 9. source validation or review evidence

    proposal family:
      PR55 (proposal shape) result, exact
      PR56 (proposal safety) result, exact

    mutation-review family:
      exact candidate review disposition
      reviewed target (Engine method name)
      reviewed exact arguments
      source-basis reference (M02 §7)

10. decision-time EngineStateIdentity
    - engine_token   (from Engine.state_identity().engine_token)
    - revision       (from Engine.state_identity().revision)

11. explicit state-basis limitation
    - the identity was observed at OPERATOR DECISION TIME
    - it is NOT the PR51 packet's capture identity
    - it does NOT prove packet atomicity (M03 §6)
    - it does NOT prove packet currentness (M03 §9)

12. downstream intent or gate reference
    - consumer-side metadata only
    - NOT an execution command

13. supersession reference when a later record replaces it
    - id of the prior record that this record supersedes,
      when applicable (§6)
```

### §5.1 Forbidden conflations

```
record identity            != Engine object identity
record identity            != EngineStateIdentity
decision subject identity  != EngineStateIdentity
decision-time              != Engine wall-clock state
EngineStateIdentity        != PR51 packet capture identity
decision record            != Engine truth record
decision record            != mutation receipt
decision record            != ReviewedMutationRequest
decision record            != execution command
```

---

## §6 Persistence and immutability

Decision facts are **append-only in meaning**.

```
existing decision record
  MUST NOT be silently rewritten

changed proposal
  -> new proposal subject
  -> PR55 / PR56 validators rerun
  -> new operator decision record

changed mutation candidate
  -> new EngineInputCandidate
  -> new mutation review per M02 §9
  -> new decision record

changed rationale / disposition / actor
  -> new decision record (NOT in-place edit)

later decision
  -> may reference prior record as superseded
  -> does NOT erase prior record
```

### §6.1 Non-mandated mechanisms

```
PR74-M05 does NOT mandate:
  - database table
  - JSON document shape
  - event store
  - file format
  - retention period
  - deletion policy
  - timestamp format
  - id allocator
```

Consumers choose. The contract only requires that the
append-only / supersession discipline is preserved.

---

## §7 Decision-state revalidation policy

PR74-M05 revalidates **decision reuse**, not PR51 packet
freshness.

### §7.1 Inputs

```
recorded_identity
  EngineStateIdentity stored with the decision record
  (engine_token, revision)

current_identity
  Engine.state_identity() obtained at the revalidation moment
  (engine_token, revision)
```

### §7.2 Comparison rule

```
recorded_identity == current_identity
```

Only value equality is meaningful. The comparison MUST be
performed via `EngineStateIdentity` value equality (which is
`engine_token == engine_token` AND `revision == revision`).

Forbidden:

```
- parsing engine_token
- ordering different engine_tokens
- ordering revisions across different engine_tokens
- substituting wall-clock timestamps for engine_token
- substituting Engine object count for revision
- substituting snapshot top-level key value for revision
```

### §7.3 Four cases

The four cases below are exhaustive in pairwise comparison of
the recorded and current `EngineStateIdentity` values.

#### §7.3 Case A — identity equal

```
recorded.engine_token == current.engine_token
recorded.revision     == current.revision
```

Meaning:

```
The current Engine identity equals the identity observed when
the operator decision was recorded.
```

Policy:

```
- the decision MAY remain eligible for immediate downstream
  gate consideration
- exact decision subject content MUST also be unchanged (§8)
- ALL downstream-specific gates still apply
- NO automatic action
- NO Engine mutation
- NO tool execution
```

Forbidden conclusions:

```
- PR51 packet is fresh
- PR51 packet is CAPTURE_BOUND
- PR51 packet is CURRENTLY_MATCHED
- packet capture was atomic
- proposal is correct
- mutation is authorized automatically
- a stored EngineInputCandidate may be re-invoked without
  re-checking M02 §12.3
```

#### §7.3 Case B — same token, revision differs

```
recorded.engine_token == current.engine_token
recorded.revision     != current.revision
```

Meaning:

```
The Engine lineage is the same, but Engine state changed after
the recorded decision identity.
```

Policy:

```
- prior decision MUST NOT be reused for downstream progression
- record remains preserved as historical audit
- obtain current consumer inputs
- repeat the applicable validation / review path
  (PR55 + PR56 for proposal family,
   M02 §9 for mutation-review family)
- create a new operator decision record
- new record MAY supersede the prior record (§5 item 13)
```

This may be described as:

```
stale for decision reuse
```

It MUST NOT be described as:

```
M03 packet STALE
```

because current PR51 packets remain `UNBOUND` (M03 §5.5 /
§7.3) — they have no capture identity to compare against, so
they cannot be `STALE` in M03's mechanical sense.

#### §7.3 Case C — token differs

```
recorded.engine_token != current.engine_token
```

Meaning:

```
The current Engine belongs to a different runtime lineage.
This includes process restart and from_snapshot() restore
(per M04 §4.4, §4.5).
```

Policy:

```
- revisions are NOT ordered or compared across lineages
- prior decision MUST NOT be reused
- snapshot content equivalence does NOT restore comparability
- a new validation / review / decision cycle is required
```

#### §7.3 Case D — identity missing or malformed

The recorded identity is absent, or the value cannot be
admitted under M04 §1 (e.g., empty `engine_token`, negative
`revision`, wrong type — all rejected by M04 C5 admission).

Policy:

```
- mechanical decision-state revalidation is UNAVAILABLE
- decision reuse is BLOCKED
- a new decision record is REQUIRED
- the historical record (if any) is preserved unchanged
```

---

## §8 Subject-content and state checks are independent

A reusable decision requires **both** of:

```
A. exact decision subject content unchanged
B. current Engine identity equal to recorded decision identity
```

### §8.1 Matrix

```
subject same    + identity same
  -> eligible for immediate downstream gate consideration
     (all §7.3 Case A forbidden conclusions still apply)

subject changed + identity same
  -> new review required

subject same    + identity changed
  -> new review required

subject changed + identity changed
  -> new review required

either comparison unavailable
  -> new review required
```

### §8.2 Hard locks

```
same candidate content
  != same Engine state

same Engine identity
  != same candidate content

content equality
  != decision-state equality

state-identity equality
  != content equality
```

---

## §9 Comparison moment and check-then-act boundary

The equality result is scoped to the revalidation **moment**.

```
identity comparison result
  != persistent freshness guarantee

identity check
  != lock

identity check
  != transaction

identity check followed by action
  != atomic check-and-act
```

### §9.1 Consumer-side obligation

M05 requires the consumer to perform decision-state
revalidation **immediately before** the next downstream gate
consideration or explicit M02 invocation consideration.

### §9.2 Non-claims

M05 does **not** claim that:

```
- no concurrent mutation can occur between the comparison and
  a later action
- the Engine cannot advance between revalidation and use
- the comparison creates a hold or reservation
- the comparison creates a transaction window
```

No lock, transaction, retry loop, or seqlock is introduced by
M05.

---

## §10 PR51 packet boundary

Current PR51 packets remain:

```
binding status:             UNBOUND
use-time comparison status: UNKNOWN
```

per M03 §5.5 / §7.3 / §13.

M05 must explicitly preserve these locks:

```
decision-time EngineStateIdentity
  != PR51 packet capture identity

decision-state match
  != PR51 packet CURRENTLY_MATCHED

decision-state mismatch
  != PR51 packet STALE
```

### §10.1 Rebuild guidance

When a prior decision cannot be reused and the consumer
rebuilds a PR51 packet:

```
- rebuild the packet from current reads
- rerun applicable validators (PR53 / PR55 / PR56)
- continue to label the new packet's mechanical status
    UNBOUND + UNKNOWN
- do NOT claim the new packet is CAPTURE_BOUND
- do NOT claim packet freshness
- do NOT carry the new decision-time EngineStateIdentity
  forward as a packet capture field
```

M05 does **not** close OC-C (PR51 packet binding). A future
CAPTURE_BOUND packet binding remains separate,
explicitly-directed future work, not auto-scheduled.

---

## §11 Proposal-gate policy

For PR57 proposal-family decisions (§4.1):

```
PR55 / PR56 validator pass
  != accepted

accepted decision record
  != downstream execution license

rewrite
  -> rewritten proposal is a NEW subject
  -> rerun PR55
  -> rerun PR56
  -> new operator decision record

request-evidence
  != add_evidence authorization

schedule-manual-inspection
  != tool execution

archive / cite
  != Engine truth assertion
```

### §11.1 Decision-state revalidation failure for proposals

```
- prior accept decision CANNOT be reused
- proposal MUST be reconsidered against current consumer
  inputs (re-fetch / re-derive as the consumer requires)
- PR55 / PR56 validators are rerun against the reconsidered
  subject
- a new operator decision record is REQUIRED
```

The historical accept record remains preserved unchanged.

---

## §12 Mutation-review policy

For M02 mutation-review-family decisions (§4.2):

```
approved disposition record
  != ReviewedMutationRequest

approved disposition record
  != Engine invocation

same decision identity
  != target unchanged
  != arguments unchanged
  != referenced IDs unchanged
```

### §12.1 Eligibility preconditions

Before a reviewed mutation request may **remain eligible** for
explicit invocation per M02 §12:

```
- exact candidate content unchanged                  (§8 A)
- reviewed method name unchanged                     (M02 §10)
- reviewed exact arguments unchanged                 (M02 §10)
- referenced IDs unchanged                           (M02 §10)
- decision-time identity equals current identity     (§7.3 A)
- M02 §12.3 caller checks still pass at invocation
  time
```

### §12.2 On identity mismatch

```
- existing approval MUST NOT be reused
- re-inspect current Engine objects
- reconstruct the exact candidate if still appropriate
- perform a new mutation review per M02 §9
- create a new decision record
```

### §12.3 Forbidden mechanisms

```
- reflection-based dispatch
- automatic request materialization
- automatic Engine call
- name-based string -> method lookup at runtime
- queue / scheduler / worker invocation of a stored approval
```

---

## §13 Process restart and restore

A persisted decision record may retain the historical pair:

```
engine_token
revision
```

But:

```
persistent operator decision record
  != persistent Engine runtime lineage
```

After process restart or `Engine.from_snapshot(...)`:

```
the current Engine receives a FRESH engine_token (M04 §4.5)
the current Engine starts at revision = 0
recorded_engine_token != current_engine_token
```

Therefore (per §7.3 Case C):

```
- prior decision CANNOT be mechanically reused
- revision values MUST NOT be ordered across the lineages
- equivalent snapshot content does NOT restore comparability
- a new decision cycle is REQUIRED
```

This is intentional: M05 separates **persistence of the
decision fact** from **continuity of the runtime lineage**.
The fact persists; the comparability does not.

---

## §14 Relationship to earlier contracts

### §14.1 PR57

Preserve:

```
Operator acceptance is a gate, not Engine truth.
Operator decisions remain consumer-side.
No operator-related ragcore symbol.
```

M05 adds conceptual persistence and revalidation obligations.
It does NOT revoke PR57's ragcore symbol lock — none of
`OperatorDecision` / `OperatorReview` / `OperatorApproval` /
`OperatorAction` / `OperatorTask` / `OperatorEvent` /
`OperatorAuditRecord` becomes a ragcore symbol under M05.

### §14.2 M02

Preserve:

```
proposal decision    != mutation review disposition
ReviewedMutationRequest != Engine invocation
exact-content review binding remains mandatory
```

M05 persists dispositions and adds decision-state reuse
policy. M05 does not modify the M02 four-layer model, the
M02 §11 exact-content binding, or the M02 §12 invocation
boundary.

### §14.3 M03

Preserve:

```
PR51 packet remains UNBOUND + UNKNOWN
CAPTURE_BOUND is not implemented
CURRENTLY_MATCHED / STALE packet claims remain unavailable
```

M05's `stale for decision reuse` (§7.3 Case B) is decision-
record reuse policy, not packet binding. It does NOT
re-classify the packet's two-axis status (M03 §7).

### §14.4 M04

Use:

```
EngineStateIdentity value equality
```

Do NOT infer from equality:

```
- atomic packet capture
- persistent Engine lineage across processes
- cross-lineage revision ordering
- packet binding
- packet freshness
```

The 245차 / 246차 corrections in M04 are preserved verbatim:

```
- M04 instruments 20 state-mutating methods
- read-only / no-op / failed mutation -> revision unchanged
- from_snapshot() returns a fresh lineage with revision = 0
- engine_token is not persisted in any snapshot field
```

### §14.5 M-series responsibility map (M01-locked)

```
PR74-M05  Operator Decision Record / stale revalidation  (OC-B)
PR75-M06  Downstream Result Re-entry                     (OC-E)
PR76-M07  Effective Confidence Calculation Trace         (OC-D)
PR77-M08  Complete Domain-Neutral Reference Operation    (OC-F)
PR78-M09  RuleStats Update Provenance                    (OC-G)
```

M05 does NOT redefine, expand, or auto-schedule any of
M06-M09. CAPTURE_BOUND packet binding, CURRENTLY_MATCHED
helpers, and mechanical packet STALE detection remain
separate, explicitly-directed future work.

---

## §15 Files locked

PR74-M05 must not modify any of:

```
ragcore/*
examples/*
tests/*
pyproject.toml
snapshot migration files
PR51 inspector (examples/inspector/engine_inspector.py)
PR53 validator
PR55 / PR56 validators
M01 scaffold (examples/operation/minimal_operational_scaffold.py)
historical dev records
M01 historical body text
M02 §1 ~ §22 historical body text
M03 §1 ~ §18 historical body text
M04 §1 ~ §10 historical body text
PR57 §1 ~ §18 historical body text
M02 §23 (post-M04 addendum) historical body text
M03 §19 (post-M04 addendum) historical body text
```

PR74-M05 may add only:

```
docs/architecture/
  OPERATOR_DECISION_RECORD_REVALIDATION_CONTRACT.md   (new)
docs/architecture/
  OPERATOR_DECISION_BOUNDARY_SPEC.md          + §19 addendum
docs/architecture/
  REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md + §24 addendum
docs/architecture/
  ENGINE_READ_CONSISTENCY_CONTRACT.md          + §20 addendum
docs/architecture/
  ENGINE_STATE_IDENTITY_PRIMITIVE_CONTRACT.md  + §11 addendum
docs/dev/
  PR_074_OPERATOR_DECISION_RECORD_REVALIDATION_CONTRACT.md
                                              (new, 248차)
```

---

## §16 Structural and behavioral invariants

### §16.1 Structural counts (delta = 0 from main 04f591b)

```
Engine public methods            41   (unchanged from PR73-M04)
Engine private methods           19   (unchanged from PR73-M04)
state-mutating public methods    20   (unchanged set)
read-only public methods         19   (unchanged set)
serialization boundary            2   (unchanged set)
ragcore.__all__                  49   (unchanged from PR73-M04)
snapshot schema_version           2   (unchanged)
snapshot top-level keys          18   (unchanged set)
PR51 packet keys                  7   (unchanged set, same order)
tests                          1517   (unchanged; M05 adds 0 tests)
```

### §16.2 Behavioral invariants (delta = 0)

```
runtime behavior                    delta = 0
judgment semantics                  delta = 0
claim lifecycle condition           delta = 0
effective-confidence formula        delta = 0
modifier value table                delta = 0
Gap matching / resolution semantics delta = 0
contradiction semantics             delta = 0
RuleStats calculation               delta = 0
PR51 packet shape                   delta = 0
snapshot schema                     delta = 0
dependency surface                  delta = 0
automatic execution                 delta = 0
```

---

## §17 Forbidden conclusions (anti-pattern lock)

The contract is normative against every conclusion in this
list. Consumer documentation, dev records, and adapter code
must avoid asserting any of them.

```
operator accepted == Engine truth
operator accepted == Engine mutation
decision record == ReviewedMutationRequest
decision record == execution command
decision identity == packet capture identity
decision-state match == packet CURRENTLY_MATCHED
decision-state mismatch == packet STALE
UNBOUND + STALE (a forbidden two-axis combination per M03 §7.3)
UNBOUND + CURRENTLY_MATCHED
                 (a forbidden two-axis combination per M03 §7.3)
persistent decision record == persistent Engine lineage
different engine_token revisions are ordered
validator pass == accepted
a single `accepted` bool covers both proposal and mutation
  review families
```

---

## §18 Non-goals

PR74-M05 deliberately does **not** define:

```
- any Python class, dataclass, TypedDict, NamedTuple, Pydantic
  model, or Protocol
- any ragcore symbol, Engine method, or snapshot field
- any database table, JSON schema, file format, or wire format
- canonical content hash / digest / signature scheme
- timestamp representation
- actor-id representation
- decision id allocator
- packet capture identity
- packet atomicity mechanism
- CURRENTLY_MATCHED helper
- packet STALE detector
- automatic revalidation worker
- automatic downstream execution
- automatic Engine mutation
- tool execution semantics
- effective-confidence trace
- RuleStats provenance
- M06 / M07 / M08 / M09 scope
```

---

## §19 Consumer implementation freedom

A consumer-side adapter may choose:

```
- the storage substrate (file / sqlite / postgres / s3 / event
  store / append-only log / kv / in-memory replay buffer)
- the serialization format (json / proto / msgpack / parquet /
  yaml / custom)
- the timestamp scheme (wall clock / logical clock / hybrid)
- the actor identity scheme
- the content-equivalence mechanism (hash / structural
  fingerprint / content snapshot / external pointer)
- the supersession-link representation
- the retention and deletion policy
- the UI and review workflow
```

Provided that:

```
- the conceptual obligations in §5 are preserved
- the persistence discipline in §6 is preserved
- decision-state revalidation in §7 is performed per §9.1
- the §8 two-check matrix is enforced
- §10 / §17 forbidden conclusions are not asserted
- §14 boundary preservations are honored
```

---

## §20 Closing position

```
M05 closes the conceptual boundary for OC-B at the decision-
record shape and reuse-policy layer.

It preserves operator decisions as consumer-side facts and
adds the minimum two-check basis (exact subject content +
EngineStateIdentity equality) for determining whether a prior
decision may remain eligible for immediate downstream gate
consideration. The two-check basis does NOT replace any
downstream gate, does NOT establish check-and-act atomicity,
and does NOT establish reuse safety. Its identity-comparison
result is scoped only to the revalidation moment.

It does NOT close OC-C, OC-D, OC-E, OC-F, or OC-G.
It does NOT promote any decision into Engine truth.
It does NOT bind the PR51 packet.
It does NOT introduce a runtime mechanism for stale detection
on packets.
```

PR74-M05 is opened as **Draft** and is not merged. Closure
language (`CLOSED`) is reserved for the post-squash-merge
state. The M-series sequence after PR74-M05:

```
PR74-M05   Operator Decision Record /
           stale revalidation             (OC-B) OPEN — DRAFT,
                                                  NOT MERGED
PR75-M06   Downstream Result Re-entry     (OC-E) NOT STARTED
PR76-M07   Effective Confidence Trace     (OC-D) NOT STARTED
PR77-M08   Complete Domain-Neutral
           Reference Operation            (OC-F) NOT STARTED
PR78-M09   RuleStats Update Provenance    (OC-G) NOT STARTED
```

No automatic next PR. Framework waits for directive.
