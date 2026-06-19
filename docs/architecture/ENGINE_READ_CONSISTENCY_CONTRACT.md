# Engine Read Consistency Contract

```
PR72-M03 — Engine Read Consistency Contract
type:    docs-only architecture contract
status:  normative
date:    2026-06-18
```

> **A consumer-side read projection is not a state-bound capture. A capture-time fact is not a use-time fact. A snapshot-schema identity is not a state-instance identity.**

This document defines the **conceptual boundary** between what
the current `Engine` read surface actually guarantees, what it
does not guarantee, and what a future consistency mechanism
would need to provide in order to support the claims a
consumer might want to make about an Engine read.

This document is a documentation contract. It does **not**
introduce any Python class, dataclass, TypedDict, JSON Schema,
Pydantic model, framework type, `ragcore` symbol, Engine
field, Engine method, snapshot key, packet key, revision
counter, capture token, digest algorithm, lock, transaction,
retry policy, stale detector, or runtime behavior change.

---

## §0 Scope limitation

§0 is a hard scope lock. Every other section respects it.

§0.1 **In scope.** The conceptual boundary that separates:

```
- snapshot schema identity
- Engine state identity
- packet identity
- capture-time consistency
- use-time consistency
- mechanical stale determination
- the minimum requirements a state-bound capture would have
  to satisfy
- the relationship between this boundary and PR71-M02
  (Reviewed Engine Mutation Handoff)
- the relationship between this boundary and PR74-M05
  (Operator Decision Record / stale revalidation)
```

§0.2 **Out of scope.** M03 does **not**:

```
- modify ragcore/ source files
- modify any examples/ Python source
- modify any tests/ file
- modify any dependency
- modify the PR51 7-key context-packet shape
- modify the PR53 packet-validator behavior
- modify snapshot schema_version or top-level keys
- modify runtime behavior, judgment semantics, lifecycle
  semantics, the effective-confidence formula, any modifier
  value, modifier behavior, RuleStats behavior, or Gap
  dedup/resolution behavior
- add a new public symbol
- add a private Engine method
- add a state_revision / packet_revision / engine_revision /
  capture_token / snapshot_digest field anywhere
- define a canonical-JSON / digest / hashing / signing scheme
- define a lock / transaction / retry / rollback / atomic batch
- define a stale detector or revalidation algorithm
- define operator decision record persistence
  (that is OC-B / PR74-M05)
- define downstream re-entry semantics
  (that is OC-E / PR75-M06)
- define an effective-confidence trace
  (that is OC-D / PR76-M07)
- define RuleStats provenance
  (that is OC-G / PR78-M09)
- introduce a stale-policy decision rule
- introduce automatic revalidation or automatic mutation
- modify the M02 ReviewedMutationRequest contract or schema
- retroactively add a state token to M02 records
```

---

## §1 Investigation origin — OC-C from M01

PR70-M01 (`docs/dev/PR_070_MINIMAL_OPERATIONAL_SCAFFOLD.md`)
recorded seven operational discontinuities. OC-C is the
missing Engine read consistency boundary surfaced at scaffold
stage B3:

```
B3  packet state binding                    UNDEFINED
```

The M01 report explicitly disclaims fabricating
`packet_revision`, `state_revision`, `engine_revision`,
`snapshot_digest`, or `capture_token`. M03 keeps the same
posture and adds the normative boundary that makes the
disclaimer load-bearing instead of stylistic.

M02 (`REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md`) closes
the OC-A handoff up to the explicit invocation in Layer 4. It
deliberately does **not** mechanize stale detection (M02 §12.3
last paragraph); M03 picks up that boundary on the read side.

---

## §2 Empirical baseline (observed on `main` `f40b811`)

The contract below is anchored on the live state of the
repository at `main` `f40b811`. Every claim about "what
current code does" or "what current code does not provide" was
checked against the source listed here.

### §2.1 PR51 context packet (read projection)

```
examples/inspector/engine_inspector.py:49
  def build_engine_context_packet(engine: Engine, claim_id: int)
                                    -> dict[str, Any]:

  Reads (in order; 7 + N sequential public read calls total):
    1   engine.get_claim(claim_id)
    2   engine.compute_effective_confidence(claim_id)
    3   engine.evidences_for_claim(claim_id)
    4   engine.contradictions_for_claim(claim_id)
    5   engine.active_contradictions_for_claim(claim_id)
    6   engine.gaps_for_claim(claim_id)
    N   engine.gap_resolution(gap.id)          [N times — one
                                                 per gap returned
                                                 by gaps_for_claim]
    7   engine.claim_lifecycle_history(claim_id)

  The packet's seven keys (§13.1) and the seven + N read calls
  are independent counts; one does not imply the other.

  Returns a plain dict with exactly seven keys:
    "claim"
    "effective_confidence"
    "supporting_evidence"
    "contradictions"
    "active_contradictions"
    "unresolved_gaps"
    "lifecycle_history"
```

### §2.2 What the current packet does not carry

A direct read of `examples/inspector/engine_inspector.py` and
of `ragcore/engine.py` confirms zero occurrences of every one
of:

```
packet_revision        state_revision
engine_revision        snapshot_digest
capture_token          state_identity
state_token            capture_time
capture_revision       packet_state_binding
```

No public Engine method, no private Engine attribute, no
snapshot top-level key, and no PR51 packet key carries any of
these.

### §2.3 What the current Engine does not provide

```
- a process-wide or per-Engine mutation revision counter
- a digest of the in-memory Engine state
- an atomic capture API that returns "all read state at
  one logical point in time"
- a lock or transaction boundary that wraps multiple read
  calls
- a versioning of caller-supplied identifiers
- a Stale exception class or any sentinel value indicating
  staleness
```

`Engine._lifecycle_seq` is **per-Claim lifecycle audit
sequence**, not an Engine-wide state revision; it advances
only on lifecycle transitions and not on data registration,
contradiction, RuleStats, or Hint mutations.

`Engine._next_id` is a **per-kind ID allocator**, not a state
revision; it advances only on `_allocate_id(kind)` calls and
does not register lifecycle, contradiction, RuleStats, or
hint changes.

### §2.4 What the current PR53 packet validator does not do

```
examples/inspector/packet_validator.py
  validate_consumer_packet_interpretation(consumer_output,
                                           source_packet)

  Detects: structurally unsafe consumer interpretations
           (F-codes for probability misuse, contradiction
            auto-refutation, gap auto-refutation, lifecycle
            verdict relabel, threshold auto-verification,
            engine mutation intent in consumer output).

  Does NOT detect: staleness, capture inconsistency,
                    source-state divergence, packet-to-state
                    mismatch, digest mismatch.
```

### §2.5 What `to_snapshot` / `from_snapshot` provide

```
to_snapshot()      serializes current Engine state to a
                    JSON-compatible dict (PR17 §29; PR21-L §33
                    schema_version=2; 18 top-level keys;
                    deterministic ordering).

from_snapshot(s)   restores Engine state from a snapshot dict
                    (PR65 §51 + PR67 §52 admission + integrity
                    checks).
```

Snapshot serialization is a **persistence boundary**. It is
not the same as Engine state identity, and the
`schema_version` integer is not the same as a state-instance
identity (§4.1).

---

## §3 Core boundary statement

Twelve load-bearing boundary statements:

```
snapshot schema_version          != Engine state revision
snapshot schema_version          != Engine state identity
snapshot schema_version          != packet revision
snapshot schema_version          != capture token
snapshot schema_version          != confidence policy revision
snapshot schema validity          != identity of the logical
                                     Engine state represented
                                     by the snapshot
Engine state identity             != packet identity
packet identity                   != source Engine state identity
sequential reads                  != atomic capture
capture-time consistency          != use-time freshness
packet validator pass             != source-state freshness
packet construction success       != all-fields-from-one-state
                                     proof
packet contents structurally
  valid at use time               != source Engine state still
                                     current
```

Every other section of this contract refines one of these.

---

## §4 Identity separation

Three identity concepts and one temporal consistency
distinction must not be collapsed:

```
§4.1   snapshot schema identity
§4.2   Engine state identity
§4.3   packet identity
§4.4   capture-time vs use-time consistency distinction
```

### §4.1 Snapshot schema identity

```
schema_version
  = serialized snapshot shape / version identity
```

`schema_version == 2` says "this snapshot dict conforms to the
v2 serialized shape". It says nothing about which Engine state
instance produced the snapshot.

```
schema_version       != Engine state identity
schema_version       != Engine state revision
schema_version       != packet revision
schema_version       != capture token
schema_version       != confidence policy revision
                       (also locked at §53.4 of PR68)
```

Two Engines that differ in claim count, lifecycle history,
RuleStats, or any other state field still produce snapshots
that report `schema_version == 2`.

### §4.2 Engine state identity

```
A way to determine whether two reads originated from the same
logical Engine state.
```

M03 names this concept; M03 does **not** mechanize it. A
future implementation could realize it as any of:

```
- an integer mutation revision counter
- an opaque capture token
- a canonical content digest
- an immutable snapshot reference
- something else
```

The implementation choice is left open. M03 only fixes the
semantic requirements: §8 (minimum requirements for a
CAPTURE_BOUND claim), §9 (use-time comparison rules for
CURRENTLY_MATCHED and STALE), and §15 (semantic requirements
that a future mutation-revision mechanism must satisfy).

### §4.3 Packet identity

```
The identity of the packet object (its dict identity, or its
serialized form's identity).
```

```
packet identity      != source Engine state identity
```

Two packets that report equal contents are not, on that basis
alone, evidence that they were captured from the same Engine
state.

### §4.4 Capture-vs-use-time distinction

```
capture-time consistency
  = at the moment the packet was assembled, all fields can be
    explained as derived from one logical Engine state

use-time consistency
  = at the moment the packet is being inspected / reviewed /
    used to decide, the source Engine state is unchanged from
    capture time
```

Capture-time consistency and use-time consistency are
distinct and must not be treated as interchangeable. They are
not unconditionally independent either: a valid use-time
consistency claim requires a valid capture-bound basis, so
the use-time axis presupposes the capture axis.

A consistent capture can become stale; a stale packet can
still pass a non-state-aware structural validator. A packet
that lacks a capture-bound basis admits no mechanical
use-time consistency claim at all (§7.2 / §7.3).

---

## §5 What today's PR51 packet does and does not assert

### §5.1 Permitted reading of the current packet

```
"At each line of the builder, that line called a public
read-only Engine method and stored its return value into a
known dict key. Each individual return value is the value that
method returned at the moment that method was called."
```

That is the **maximum** claim the current packet supports
without additional infrastructure.

### §5.2 Forbidden readings of the current packet

A document MUST NOT describe the current packet as any of:

```
- an atomic Engine snapshot
- a state-bound capture
- a self-revisioned read
- a state-identified projection
- a packet whose freshness can be mechanically verified
- a packet whose all-fields-from-one-state property is
  proven by construction
- a packet whose source Engine state can be re-identified
  without an external comparison basis
- "the Engine at time T"
```

### §5.3 Permitted reading of PR53 validator output

```
"The validator did not detect a selected structural unsafe
consumer interpretation of the packet."
```

### §5.4 Forbidden readings of PR53 validator output

```
- "the packet is fresh"
- "the source Engine state is current"
- "the source Engine state is identified"
- "the capture is atomic"
- "the packet still represents the Engine"
- "the packet validator confirms staleness"
- "the packet validator confirms binding"
```

### §5.5 Empirical classification of today's packet

Under the two-axis vocabulary of §7, today's PR51 packet sits
at the combination:

```
binding status:                UNBOUND
use-time comparison status:    UNKNOWN  (mechanically unavailable)
```

This is one of the four valid combinations enumerated at
§7.3. Because the binding status is UNBOUND, the use-time
comparison status is mechanically UNKNOWN by §7.3:
`CURRENTLY_MATCHED` and `STALE` both require CAPTURE_BOUND as
a prerequisite, and the repository provides no infrastructure
that would lift today's packet out of UNBOUND.

---

## §6 Capture atomicity boundary

```
"Sequential public read calls" is not "atomic capture".
```

The current `build_engine_context_packet` issues 7 + N
sequential public read calls (§2.1). A document MUST NOT
describe that sequence as atomic, transactional, or
state-bound on the basis of any of:

```
- "Python execution is fast"
- "the GIL prevents interleaving"
- "the test exercises a single-threaded example"
- "no mutation happened in the test"
- "the sequence is short"
- "the reads are read-only"
- "the example does not race"
```

The atomic-capture claim requires at least one of:

```
(a) all packet fields are read from one immutable state
    snapshot produced by a single Engine call

(b) the read sequence is wrapped in an Engine-supported
    consistency boundary (lock, transaction, snapshot
    isolation, or equivalent) whose semantics are documented

(c) the read sequence is bracketed by capture-before /
    capture-after revision checks with an explicit
    retry-or-fail rule

(d) a mechanism semantically equivalent to (a) / (b) / (c)
    with an explicit verification path
```

M03 does **not** select among (a) / (b) / (c) / (d). The
choice is a future-implementation concern. M03 only fixes
that, without one of (a) / (b) / (c) / (d), the atomic claim
must not be made.

---

## §7 Conceptual consistency vocabulary — two distinct axes with a dependency constraint

The following names are **conceptual vocabulary** used by this
document to talk about a packet's relationship to its source
Engine state. They are organized as **two distinct axes that
are not unconditionally independent**: a binding axis and a
use-time comparison axis. Per §4.4 / §7.3, the use-time axis
presupposes the binding axis, so the two axes are separate
but not unconditionally independent.

A document MUST NOT collapse the two axes into a single
five-level list, and MUST NOT lift these strings into a
runtime field name, an enum value, a packet field value, a
snapshot value, or a lifecycle status.

### §7.1 Binding axis

```
UNBOUND
  The packet has no source-state identity binding at all.
  No comparison basis is recorded with the packet.

CAPTURE_BOUND
  The packet is bound to one source-state identity through a
  capture that satisfies the §8 minimum requirements. The
  binding establishes the capture-time consistency basis.
```

### §7.2 Use-time comparison axis

```
UNKNOWN
  No valid current comparison result is available — either
  because no capture identity exists (UNBOUND), or because
  no current comparison has been performed, or because a
  prior comparison's validity moment (§9.3) has elapsed.

CURRENTLY_MATCHED
  A valid use-time comparison has just found the packet's
  capture identity equal to the current Engine state
  identity.

STALE
  A valid use-time comparison has just found the packet's
  capture identity different from the current Engine state
  identity.
```

### §7.3 Valid and invalid combinations

```
Valid:
  UNBOUND        + UNKNOWN
  CAPTURE_BOUND  + UNKNOWN
  CAPTURE_BOUND  + CURRENTLY_MATCHED
  CAPTURE_BOUND  + STALE

Invalid (CURRENTLY_MATCHED / STALE require CAPTURE_BOUND):
  UNBOUND        + CURRENTLY_MATCHED
  UNBOUND        + STALE
```

A `CURRENTLY_MATCHED` or `STALE` claim requires CAPTURE_BOUND
as a prerequisite; an `UNBOUND` packet cannot be mechanically
classified as CURRENTLY_MATCHED or STALE.

---

## §8 Minimum requirements for a `CAPTURE_BOUND` claim

To make a `CAPTURE_BOUND` claim about a packet, all five
requirements below must hold simultaneously:

```
§8.1   A state-identity basis exists by which two reads can
        be classified as "same state" or "different state".

§8.2   The packet records which source-state identity it was
        captured against.

§8.3   The packet's every state-derived field is part of the
        capture covered by that identity. In particular, the
        capture is atomic in the sense of §6.

§8.4   The construction rule for the identity and the
        comparison rule for two identities are explicitly
        defined. Two callers comparing the same pair of
        identities must reach the same result.

§8.5   The identity is not silently reused across a mutation.
        If the source Engine state changes, the identity must
        either change or be explicitly invalidated under a
        documented rule.
```

The following values, on their own, are **not** sufficient
state-identity bases under §8.1:

```
- a Python object id
- a process id
- a wall-clock timestamp
- a module / repo / git commit SHA
- the snapshot schema_version
- a hash of the packet dict
- a non-canonical JSON hash of the packet
- repr(packet) or any pretty-printed serialization
- the largest object id in the Engine
- a single claim_id
- a count of objects in the Engine
```

Each of these is either irrelevant to logical state, or
sensitive to mutations the consumer does not consider
material, or trivially fooled by a mutation that adjusts a
later, unrelated object.

---

## §9 Minimum requirements for a `CURRENTLY_MATCHED` claim

Beyond the `CAPTURE_BOUND` requirements (§8), a
`CURRENTLY_MATCHED` claim further requires:

```
§9.1   At the moment of the claim, the consumer obtains the
        current Engine state identity using the same identity
        construction rule as §8.4.

§9.2   The consumer compares the packet's capture identity
        against that current identity using the comparison
        rule of §8.4 and obtains "same state".

§9.3   The CURRENTLY_MATCHED comparison result is scoped to
        the comparison moment. After that moment the
        comparison result has expired, even if no mutation
        has been observed. An expired comparison result
        leaves the packet's binding status unchanged
        (CAPTURE_BOUND) and resets the comparison status to
        UNKNOWN. The packet does NOT drop back to UNBOUND.
```

#### §9.4 Expiry locks

```
expired comparison result
  != lost capture binding

CAPTURE_BOUND + comparison UNKNOWN
  is a valid combination (§7.3); a CAPTURE_BOUND packet whose
  prior CURRENTLY_MATCHED moment has expired sits here.

re-obtaining CURRENTLY_MATCHED / STALE
  requires a fresh §9.1 / §9.2 comparison; the prior result
  cannot be reused.
```

`CURRENTLY_MATCHED` is **not** persistent on its own. M03
does not specify how a consumer chooses to persist either the
capture binding or the comparison result; consumer-side
persistence is OC-B / PR74-M05.

---

## §10 `STALE` claim and the limits of mechanical staleness

A `STALE` claim under §7 is the inverse comparison outcome of
§9.2 — capture identity differs from current identity using
the §8.4 comparison rule.

Today, with no §8.1 identity basis, the contract is:

```
mechanical stale determination
  = not available
```

A document MUST NOT write any of:

```
- "this packet is fresh"
- "this packet is current"
- "this packet is unchanged"
- "this packet still represents the Engine"
- "the packet validator confirms freshness"
- "the packet validator confirms staleness"
```

without a comparison basis that satisfies §8 and a comparison
moment that satisfies §9.

M03 does **not** define:

```
- a stale-packet rejection rule
- a re-review rule
- an automatic discard rule
- a permissible mutation list
- a permissible time interval
- a quorum or tolerance
- a retry-after-mutation rule
```

Those are stale-decision policy choices and belong to
**OC-B / PR74-M05**. M03's role is to fix the fact-and-basis
layer; M05's role is to define the decision policy on top of
that fact-and-basis layer.

---

## §11 Relationship to PR71-M02

M02 (`docs/architecture/REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md`)
fixes the conceptual boundary for the OC-A role-derived
ingress path:

```
admitted RoleAssignment
  -> non-executable EngineInputCandidate
    -> approved exact candidate review
      -> ReviewedMutationRequest
        -> explicit invocation of one existing state-mutating
            Engine public method
```

M02 §12.3 explicitly states that the immediate-pre-invocation
caller checks **do not** guarantee freshness, currentness, or
state-binding. M03 picks up exactly that boundary on the read
side.

### §11.1 What M03 preserves about M02

```
- M02's four-layer model is unchanged.
- M02's §11 exact-content review binding is unchanged.
- M02's §12.1 / §12.2 invocation boundary is unchanged.
- M02's §14.1 / §14.2 / §14.3 separation principles for
  lifecycle / contradiction-resolution / Gap resolution are
  unchanged.
- M02's §17 A2 (AdapterTrace -> RoleAssignment) UNDEFINED
  status is unchanged.
```

### §11.2 What M03 explicitly does not do to M02

```
- M03 does NOT add a state-identity / capture-token field
  to ReviewedMutationRequest.
- M03 does NOT modify M02 §10 (request content).
- M03 does NOT modify M02 §11 (exact-content review binding).
- M03 does NOT retroactively alter any M02 contract.
- M03 does NOT require M02 records to carry an OC-C
  identity.
```

### §11.3 Cross-cutting boundary

```
exact candidate content binding
  != source Engine state binding

candidate arguments unchanged at use time
  != Engine state unchanged at use time

approved exact candidate review
  != decision-time state consistency verified
```

The relationship between M02 records and M03 facts is left as
a future-implementation concern, plausibly to be addressed by
**OC-B / PR74-M05** through an operator decision record that
references both.

---

## §12 Relationship to OC-B / PR74-M05

PR74-M05 (OC-B) will define the persistent operator decision
record and the stale revalidation rule. M03 is the
fact-and-basis layer; M05 is the decision-policy layer.

```
M03   defines the boundary between
        - snapshot schema identity
        - Engine state identity
        - packet identity
        - capture-time consistency
        - use-time consistency
        - mechanical stale determination availability

M05   defines the policy that uses the M03 facts to decide
        - whether a packet may still ground an operator
          decision
        - whether a prior review is still applicable
        - whether revalidation or re-capture is required
        - how the decision record persists across process
          boundaries
```

A document MUST NOT pre-bake an M05-style decision rule
("reject stale packets", "auto-revalidate within N seconds",
etc.) inside an M03-style fact statement.

---

## §13 Relationship to PR51 and PR53

### §13.1 PR51 inspector

```
build_engine_context_packet
  = a read projection assembled from existing read-only
    public Engine methods, returning a plain dict.

It is NOT:
  - a snapshot
  - a transaction
  - a state-bound capture
  - an audit record
  - a decision record
  - a freshness oracle
```

M03 does **not** modify the PR51 7-key shape. M03 does **not**
add a key. The packet's seven keys remain exactly:

```
claim
effective_confidence
supporting_evidence
contradictions
active_contradictions
unresolved_gaps
lifecycle_history
```

### §13.2 PR53 validator

```
validate_consumer_packet_interpretation
  = a consumer-interpretation safety validator that returns
    a list of (F_id, message) tuples.

It is NOT:
  - a state-identity validator
  - a freshness validator
  - a capture-atomicity validator
  - a stale detector
```

M03 does **not** modify PR53 behavior, return shape, or F-code
inventory.

---

## §14 Snapshot boundary

The existing `to_snapshot` / `from_snapshot` boundary is
**not** the M03 boundary. Specifically:

```
snapshot serialization
  != context packet construction

snapshot schema validity
  != identity of the logical Engine state represented
     by the snapshot

restorable snapshot
  != decision-time current state

same schema_version (== 2)
  != same Engine state instance
```

A future implementation could, in principle, choose to derive
a state-identity basis from a canonical snapshot digest, but
M03 does **not**:

```
- specify a canonicalization rule
  (key ordering, list ordering, tuple-vs-list normalization
   for tuple keys, NaN handling, etc.)
- specify a hash function
- specify a digest encoding
- specify a signing scheme
- specify a secret key model
- specify a collision policy
- specify cross-runtime digest compatibility
- require that a future implementation actually use a
  snapshot-derived digest at all
```

Using a snapshot digest as a state-identity basis is one of
several future implementation options and is not endorsed or
required by M03.

---

## §15 Future mutation-revision mechanism — semantic requirements

If a future PR introduces a mechanism that supports §8 / §9,
M03 records the semantic requirements it must satisfy. M03
does **not** introduce the mechanism itself.

```
§15.1   The mechanism must be consistently connected to every
         state-changing public Engine method (M02 §12.1 lists
         twenty state-mutating public methods on `main`
         `f40b811`).

§15.2   Read-only public methods must not change the state
         identity. The eighteen read-only public methods at
         M02 §12.1 must remain pure observation under the
         §15.1 mechanism.

§15.3   A failed or no-op mutation's state-identity semantics
         must be explicitly defined (does the identity advance,
         and if not, what indicates the failure to the
         consumer?).

§15.4   The state-identity semantics after `from_snapshot`
         restore must be explicitly defined (is the restored
         identity reset, continued, or invalidated?).

§15.5   The mechanism's wraparound, persistence, and
         process-restart semantics must be explicitly defined.

§15.6   The comparison rule between two identities must be
         deterministic and decidable: two callers with the
         same pair of identities must reach the same
         "same / different" verdict.
```

M03 does **not**:

```
- add a revision field to any dataclass
- modify any of the 20 state-mutating public methods
- modify any of the 18 read-only public methods
- modify `to_snapshot` or `from_snapshot`
- add a snapshot top-level key
- add a packet key
- introduce a new ragcore.__all__ entry
```

The above is the **scope of M03**. Introducing a concrete
mechanism is left to a separate, explicitly-directed
implementation PR.

---

## §16 Relationship to other future M-series

```
PR73-M04   Conditional slot; M03 does NOT pre-define.

PR74-M05   Operator decision record + stale revalidation
            policy. M05 will choose a stale-decision rule on
            top of M03 facts. M03 does NOT pre-bake that rule.

PR75-M06   Downstream re-entry. M03 does NOT define how
            external results re-enter the consumer workflow.

PR76-M07   Effective-confidence trace. M07 may need source-
            state references; M03 does NOT define the trace
            mechanism or the policy identity (§53 / PR68).

PR77-M08   Complete reference operation. M03 does NOT compose
            the operation.

PR78-M09   RuleStats provenance. M03 does NOT define caller
            identity, update reason, source observation
            reference, delta provenance, precision input
            basis, or policy reference.
```

PR72-M03 does NOT auto-start PR73-M04 or any later M-series PR.

---

## §17 Non-goals

§17 enumerates what M03 deliberately does **not** introduce.

```
- runtime behavior change
- judgment semantics change
- lifecycle semantics change
- effective-confidence formula change
- modifier value change
- modifier behavior change
- RuleStats behavior change
- Gap dedup behavior change
- Gap resolution behavior change
- snapshot schema_version change
- snapshot top-level key addition or removal
- PR51 context-packet shape change
- PR53 packet validator behavior change
- new public ragcore symbol
- new private Engine method
- new Engine public or private field
- StateRevision class / dataclass / TypedDict / NamedTuple /
  Pydantic model
- PacketRevision class / dataclass / TypedDict / NamedTuple
- CaptureToken class
- SnapshotDigest class
- mutation revision counter
- canonical digest specification
- canonical JSON specification
- hash function specification
- signing scheme
- lock / transaction / retry / rollback
- automatic revalidation
- automatic mutation
- automatic dispatch
- stale-decision policy
- operator decision record persistence
- downstream re-entry workflow
- domain-specific operation
- network call
- LLM call
- modification of M02 records to carry an M03 identity
```

---

## §18 Closing position

M03 fixes the conceptual boundary between:

```
- snapshot schema identity (the v2 serialized shape contract)
- Engine state identity     (a comparison basis that does not
                              exist in ragcore today)
- packet identity           (the dict / serialized object's
                              own identity)
- capture-time consistency  (a fact about how the packet was
                              assembled)
- use-time consistency      (a fact about whether the source
                              state is unchanged at the moment
                              the packet is used)
- mechanical stale          (only possible when an Engine state
   determination              identity comparison basis exists)
```

The current PR51 packet is a consumer-side read projection.
With no §8 identity basis available today, it sits at the
two-axis combination `UNBOUND` + `UNKNOWN` (§5.5 / §7.3). A
document MUST NOT promote it above that combination.

M03 does **not** introduce the mechanism that would lift the
classification. M03 records the semantic requirements (§15)
that a future implementation would have to satisfy if and when
such a mechanism is added.

Stale-decision policy is **not** in scope for M03. That layer
is OC-B / PR74-M05, which M03 does **not** pre-define.

The boundary that M03 closes is purely **fact-and-basis**:
what a packet does and does not testify to about its source
Engine state. The decisions a consumer or operator might make
on top of those facts remain consumer and operator policy.

---

## §19 Post-M04 addendum (PR73-M04, 245차)

This section is a current-state addendum. It does **not**
rewrite the M03 baseline investigation above (§1 ~ §18). M03's
empirical observations on `main` `f40b811` and its semantic
requirements (§15) remain the historical baseline.

```
- M03 baseline state had no mechanized Engine state identity.
- After PR73-M04 merges, ragcore exposes
  EngineStateIdentity (engine_token: str, revision: int) and
  Engine.state_identity().
- That mechanism alone does NOT lift today's PR51 packet out
  of UNBOUND + UNKNOWN.
- The current PR51 packet remains UNBOUND + UNKNOWN; the
  builder does not call state_identity() and the packet does
  not carry an engine_token / revision field.
- atomic capture (§6) and packet binding (§8) are NOT
  provided by PR73-M04.
- CURRENTLY_MATCHED (§9), STALE (§10), and stale-rejection
  policy remain out of scope.
```

PR73-M04 satisfies the §15 semantic requirements as a primitive,
but does not by itself produce a CAPTURE_BOUND packet, a
CURRENTLY_MATCHED claim, or a stale determination. Any of those
would be **separate, explicitly-directed future work**, and is
**not** automatically scheduled by M04.

---

## §20 Post-M05 addendum (PR74-M05, 2026-06-19)

PR74-M05 (`OPERATOR_DECISION_RECORD_REVALIDATION_CONTRACT.md`)
defines **consumer-side decision-state revalidation** on top of
M04's `EngineStateIdentity` primitive. M05 does **not** change
M03's reading of the PR51 packet.

```
- M05 decision-state revalidation operates on
  EngineStateIdentity value equality between
  a recorded decision identity and a current
  Engine.state_identity() value.

- M05 decision-state revalidation is NOT packet-level
  binding. It does NOT lift PR51 packets out of
  UNBOUND + UNKNOWN.

- M05 "stale for decision reuse" (M05 §7.3 Case B) is a
  property of a stored consumer-side decision record, not a
  property of a PR51 packet. It MUST NOT be described as
  M03 packet STALE.

- M05 does NOT introduce CURRENTLY_MATCHED or STALE for the
  PR51 packet. The forbidden two-axis combinations from
  §7.3 (UNBOUND + STALE, UNBOUND + CURRENTLY_MATCHED) remain
  forbidden.

- M05 does NOT introduce atomic capture (§6), packet binding
  (§8), or mechanical packet staleness (§10).

- When a consumer rebuilds a PR51 packet after a failed
  decision-state revalidation, the rebuilt packet remains
  UNBOUND + UNKNOWN. The new decision-time
  EngineStateIdentity is NOT carried as a packet capture
  field.

- M05 honors §11 / §12 distinctions: M02 owns the mutation
  candidate handoff up to explicit invocation; M03 owns the
  packet read-consistency vocabulary; M05 owns the
  consumer-side decision-record reuse policy. The three
  layers do not overlap.

- M05 honors §15 future-mechanism semantic requirements
  exactly as M04 implements them. M05 does not introduce or
  pre-define §15.x extensions.
```

M05 does not modify M03's empirical baseline (§2), the
four identity concepts (§4), the two-axis vocabulary (§7),
the §8 CAPTURE_BOUND requirements, the §9 CURRENTLY_MATCHED
requirements, the §10 STALE boundary, the §13 PR51 / PR53
relationship, or the §14 snapshot boundary.
