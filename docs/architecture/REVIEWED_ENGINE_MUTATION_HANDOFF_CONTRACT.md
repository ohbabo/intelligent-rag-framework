# Reviewed Engine Mutation Handoff Contract

```
PR71-M02 — Reviewed Engine Mutation Handoff Contract
type:    docs-only architecture contract
status:  normative
date:    2026-06-18
```

> **A reviewed mutation request permits a caller to consider an explicit Engine public API invocation. It is not the invocation itself.**

This document defines the **conceptual boundary** between a
consumer-side `RoleAssignment`, a consumer-side
`EngineInputCandidate`, a consumer-side `ReviewedMutationRequest`,
and the **single Engine mutation event** — the caller's explicit
invocation of one existing Engine public method.

This document is a documentation contract. It does **not**
introduce any Python class, dataclass, TypedDict, JSON Schema,
Pydantic model, framework type, `ragcore` symbol, Engine
method, dispatcher, executor, queue, transaction manager, or
runtime behavior change. Every term it names is conceptual; the
storage form is consumer-side policy.

---

## §0 Scope limitation

§0 is a hard scope lock. Everything else in this document
respects it.

§0.1 **In scope.** The conceptual boundary that separates
`RoleAssignment`, `EngineInputCandidate`, `ReviewedMutationRequest`,
and the actual explicit Engine public API invocation.

§0.2 **Out of scope.** Any executable form of the above
boundary. M02 does **not**:

```
- materialize EngineInputCandidate or ReviewedMutationRequest
  as Python classes / dataclasses / TypedDicts / NamedTuples
- introduce a dispatcher, executor, queue, or router
- introduce a JSON Schema, Pydantic model, or serialization
  format
- introduce a `ragcore` public symbol
- add a new Engine public or private method
- change runtime behavior, judgment semantics, lifecycle
  semantics, the effective-confidence formula, any modifier
  value, snapshot schema, or snapshot top-level keys
- define operator UI, approval persistence, signing,
  cryptographic digest, audit log schema, or stale revalidation
  algorithm
- define state revision, packet revision, or capture atomicity
  (those are OC-C / PR72-M03)
- define operator decision record persistence
  (that is OC-B / PR74-M05)
- define downstream re-entry semantics
  (that is OC-E / PR75-M06)
- define an `AdapterTrace -> RoleAssignment` mapping
  (the A2 discontinuity from M01 remains UNDEFINED)
```

---

## §1 Investigation origin — OC-A from M01

PR70-M01 (`docs/dev/PR_070_MINIMAL_OPERATIONAL_SCAFFOLD.md`)
exposed seven operational discontinuities (OC-A through OC-G).
OC-A is the missing handoff sequence:

```
RoleAssignment
    ↓
EngineInputCandidate
    ↓
ReviewedMutationRequest
    ↓
explicit Engine public API call
```

M01 surfaced OC-A at three scaffold stages:

```
A5  RoleAssignment -> EngineInputCandidate         UNDEFINED
A6  EngineInputCandidate -> ReviewedMutationRequest UNDEFINED
A7  ReviewedMutationRequest -> Engine mutation     BLOCKED
```

M02 closes the **conceptual** boundary for A5 / A6 / A7. It
does **not** close A2:

```
A2  AdapterTrace -> RoleAssignment                  UNDEFINED
```

PR64's adapter trace representation and PR61's role-assignment
representation remain intentionally independent; M02 does not
introduce any mapping, parser, helper, or schema between them.

M02's input is therefore a **consumer-side, context-specific,
already-authored RoleAssignment**.

---

## §2 Layer position

M02 sits between PR60 (`ROLE_ASSIGNMENT_POLICY_SPEC.md`) and
PR43 (`docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md`).

```
PR60 Role Assignment Policy
  consumer-side contextual interpretation boundary
  (what a context-specific role assignment is, what it is not)
                    │
                    │   (M02 layer)
                    ▼
M02 Reviewed Engine Mutation Handoff
  candidate / review / explicit-call boundary
                    │
                    │   (existing layer)
                    ▼
PR43 Engine Method Call Playbook
  existing call-order guide for the caller after review ends
```

M02 does not deprecate, replace, or rewrite any of:

```
PR43  Engine Method Call Playbook
PR57  Operator Decision Boundary Spec
PR58  Proposal Usage Playbook
PR60  Role Assignment Policy Spec
PR70  Minimal Operational Scaffold (M01)
```

It cites them as the layers above and below.

---

## §3 Core boundary statement

```
RoleAssignment validator pass != candidate materialization
RoleAssignment                != Engine truth
RoleAssignment                != EngineInputCandidate
EngineInputCandidate          != accepted mutation
candidate validation          != review approval
ReviewedMutationRequest       != automatic execution
proposal operator acceptance  != mutation review approval
actual Engine mutation        =  caller explicitly invokes one
                                  existing Engine public API
```

These eight equivalences are the load-bearing locks of M02.
Every other section refines one of them.

---

## §4 Four-layer model

Four conceptual layers separate context interpretation from
runtime mutation. The boundaries between them must not be
collapsed.

### §4.1 Layer 1 — RoleAssignment

```
A consumer-side contextual interpretation of an item under a
specific interpretation context.
```

A `RoleAssignment` carries:

```
- assignment target
- provenance
- interpretation context
- primary role
- secondary roles
- allowed uses
- forbidden uses
- assignment basis
- traceability
- explicit resolved / unresolved state
```

A `RoleAssignment` is **not** an Engine object, a Claim, an
Evidence, a Gap, a Relation, a RuleDefinition, an Engine
method argument, an accepted mutation, an operator truth
judgment, or a final verdict.

If the consumer happens to use the PR61 illustrative
representation, the result of `validate_role_assignment_boundaries(...)`
returning `[]` means **"selected representational boundary
violations not detected"**. It does **not** mean role
semantically correct, mutation suitable, candidate approved,
or Engine call authorized.

### §4.2 Layer 2 — EngineInputCandidate

```
A consumer-side, non-executable description of one proposed
Engine public API invocation.
```

A candidate is **not** a `ragcore` type, not an Engine method
argument accepted by Engine, not callable, not a command, not
a mutation, not an approved request, not a dispatch instruction,
not a serialized Engine object.

The name `EngineInput` means **"a candidate the consumer is
considering for an Engine call"**, not "an input Engine has
already accepted." Engine has no public API that receives a
candidate.

### §4.3 Layer 3 — ReviewedMutationRequest

```
An EngineInputCandidate whose exact proposed invocation has
received an explicit consumer-side mutation review decision.
```

A reviewed request is **not** Engine truth, not an executed
call, not a mutation receipt, not a lifecycle transition, not
callable, not an Engine-owned record, not an automatic license
to invoke arbitrary methods.

A reviewed request is the consumer-side handoff **directly
before** the explicit invocation in Layer 4. It does not
perform the invocation.

### §4.4 Layer 4 — Explicit Engine public API invocation

The actual mutation event:

```python
engine.add_claim(
    subject_id, claim_type, rule_id, rule_version, reason_code,
    base_confidence=..., status=..., flags=...,
)
engine.add_evidence(claim_id, raw_ref_id, evidence_type, strength)
engine.add_gap(
    claim_id, gap_type, required_evidence_type, severity, rule_id,
)
engine.register_contradiction(claim_id, evidence_id)
```

Engine state does not change until a Python caller actually
executes one of these existing public method calls. Reaching
Layer 3 does **not** call Engine; reaching Layer 4 **is** the
call.

---

## §5 RoleAssignment admission boundary

A consumer **may** consider materializing a candidate only
when every one of the following is true. (Materializing the
candidate is still a separate consumer decision.)

```
§5.1   RoleAssignment exists on the consumer side.
§5.2   Interpretation context is recorded explicitly.
§5.3   Assignment target is identifiable.
§5.4   Provenance and traceability are recorded.
§5.5   Primary role ambiguity is resolved.
§5.6   AllowedUse and ForbiddenUse do not conflict.
§5.7   The assignment is not in the unresolved state.
§5.8   The consumer's own policy does not forbid candidate
        materialization in this context.
§5.9   If a representational validator was used, its result
        is recorded together with its meaning.
§5.10  Even when §5.9 returned [], the consumer makes the
        candidate materialization decision separately.
```

Validator output `[]` means **"selected representational
boundary violations not detected"** and nothing more. It is
not consent, approval, certification, or authorization.

An **unresolved** RoleAssignment never advances:

```
unresolved
  -> preserve ambiguity
  -> stop
```

Convenience selection of a primary role and direct candidate
materialization from an unresolved assignment are forbidden.

---

## §6 EngineInputCandidate definition

```
A consumer-side, non-executable description of one proposed
Engine public API invocation, materialized from a single
admitted RoleAssignment.
```

A candidate:

```
- describes exactly one proposed invocation
- is inspectable in full before any review
- carries no callable, no method object, no lambda, no
  evaluatable code
- references an existing Engine public method only as
  inspection metadata (the method name string is a label,
  not an execution token)
- does not authorize any Engine call by its existence
```

A candidate is not Engine input until and unless a caller, at
Layer 4, explicitly invokes that exact public method with
those exact arguments.

---

## §7 Candidate minimum conceptual content

M02 does **not** freeze Python field names, JSON keys,
serialization format, or storage shape. M02 records the
information a candidate must conceptually carry so that
inspection and review can be meaningful.

```
- candidate identity
    (consumer-assigned opaque identity; not a ragcore ID,
     not Engine._next_id)

- source RoleAssignment reference
    (which RoleAssignment supports this candidate)

- assignment context reference
    (under which interpretation context the candidate was
     considered)

- source provenance / traceability reference

- intended existing Engine public API target
    (the method name as inspectable metadata only)

- explicit proposed arguments
    (each policy-sensitive argument shown literally,
     with hidden defaults made explicit)

- argument translation basis
    (which consumer interpretation produced each argument)

- expected preconditions
    (what must already be present in the Engine for the
     call to be meaningful — referenced IDs, prior state)

- expected Engine mutation effect
    (what registration the call performs if it succeeds)

- explicit non-effects
    (what the call does NOT do)

- known unresolved assumptions
    (anything the consumer could not determine and is
     leaving to the reviewer)

- consumer policy basis
    (which consumer policy authorized this materialization)
```

### §7.1 Argument translation lock

External signals **must not** be auto-identified with Engine
signals. None of:

```
retrieval score
severity label
LLM confidence
similarity
ranking
external probability
```

may be silently treated as:

```
base_confidence
Evidence.strength
Gap.severity
Claim.status
```

If the consumer chooses to derive an Engine argument from an
external signal, the candidate must record the derivation
explicitly under "argument translation basis", and the
reviewer must inspect that basis.

### §7.2 Expected-effect / non-effect lock

A candidate that says:

```
expected effect:   create one Evidence attached to an existing Claim
```

must also enumerate non-effects such as:

```
- does not confirm the Claim
- does not refute the Claim
- does not execute a tool
- does not update RuleStats
- does not resolve every Gap
- does not produce a final verdict
```

Non-effects are not editorial. They are review-critical
content.

---

## §8 Candidate atomicity and ordering

```
one EngineInputCandidate
  =  one proposed Engine public API invocation
```

A multi-call operation is expressed as a sequence of separate
candidates, each describing exactly one invocation. Example:

```
candidate 1  add_entity(entity_type=...)
candidate 2  add_claim(subject_id=...)
candidate 3  add_evidence(claim_id=..., evidence_type=...)
candidate 4  add_gap(claim_id=..., required_evidence_type=...)
candidate 5  confirm_claim_if_ready(claim_id=...)
```

Consumers may group candidates into an **ordered batch** on
their own side. M02 does **not** define:

```
- a batch executor
- a transaction manager
- rollback
- all-or-nothing semantics
- a dependency resolver
- automatic call sequencing
```

The call order followed once review ends is the existing
`docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md` (PR43). M02 does
not invent a new call order; it sits one layer above PR43 as
the explicit gate that precedes following PR43.

---

## §9 Mutation review boundary

Mutation review is the consumer-side gate that turns a
candidate into a reviewed request.

### §9.1 Pre-review state of a candidate

A candidate is review-eligible only when it is:

```
- non-executable (no callable / lambda / method object)
- complete enough to inspect
- targeted at a method that exists in the current Engine
  public API
- inspectable in its exact proposed arguments
- traceable to its source RoleAssignment and translation
  basis
- explicit about preconditions, expected effect, and
  non-effects
- not produced from an unresolved RoleAssignment
- not targeted at a private Engine attribute or method
- not targeted at a method that does not yet exist
```

### §9.2 Review questions

A reviewer inspects, at minimum:

```
§9.2.1  Does the source RoleAssignment actually support this
         candidate?
§9.2.2  Does the candidate conflict with AllowedUse / ForbiddenUse?
§9.2.3  Is the target method an existing public Engine method?
§9.2.4  Do the arguments match the target signature in meaning,
         not just in shape?
§9.2.5  Has any external score been silently substituted for an
         Engine signal (§7.1)?
§9.2.6  Do the referenced Engine IDs refer to objects of the
         intended kind?
§9.2.7  Is a lifecycle mutation hidden inside what appears to
         be a data registration candidate?
§9.2.8  Is a RuleStats update appended as a silent side effect?
§9.2.9  Is the expected effect overstated relative to the
         method's actual behavior?
§9.2.10 Are the non-effects explicit and complete enough to
         prevent misreading?
```

### §9.3 Review is not proposal acceptance

PR57 operator acceptance is the workflow gate that allows a
proposal to flow to a downstream consumer layer.

Mutation review is a **separate** gate that decides whether an
exact Engine mutation candidate may become a reviewed request.

```
proposal validators pass
  != proposal accepted
proposal accepted
  != EngineInputCandidate created
proposal accepted
  != ReviewedMutationRequest
mutation candidate reviewed
  != proposal accepted
```

A consumer **must not** collapse the two decisions into a
single boolean (for example, a single `accepted=True` field
that simultaneously means "proposal accepted" and "mutation
approved"). M02 does not specify the persistent storage shape
of either decision; the persistent operator decision record is
OC-B / PR74-M05.

---

## §10 ReviewedMutationRequest definition

```
An EngineInputCandidate whose exact proposed invocation has
received an explicit consumer-side mutation review decision.
```

A reviewed request:

```
- has a request identity (consumer-assigned, opaque)
- references exactly one reviewed candidate identity
- carries the reviewed target API and reviewed exact
  arguments
- carries the review decision (approved / rejected /
  hold), the review basis / rationale, a review actor
  reference, and a review time reference (the
  representation of "time" is consumer-side; M02 does not
  freeze a timestamp format)
- carries an explicit execution boundary statement that
  reaffirms §12.1
```

M02 does **not** require, mandate, or freeze any of:

```
- Python field names
- timestamp format
- actor identity scheme
- database storage
- signing
- cryptographic digest
- state revision
- packet revision
- stale revalidation algorithm
- retention period
- audit log schema
```

Each of these is a consumer implementation choice or a
later-M-series concern.

---

## §11 Exact-content review binding

```
A review applies only to the exact target and exact arguments
that were reviewed.
```

If, after review, **any** of the following changes, the prior
review **must not** be reused for the new candidate state:

```
- target Engine method
- argument value
- referenced Engine object ID
- translation basis
- expected effect
- source RoleAssignment
- policy-sensitive assumption
```

A changed candidate is a new candidate and requires a new
review. M02 does not require a hash, digest, signature, or
revision field. How a consumer mechanically detects "the
candidate is unchanged" is a consumer implementation choice.
This is **not** the same as M03's `state_revision` /
`packet_revision`; those are Engine-state identity, not
candidate-content identity.

---

## §12 Explicit Engine public API invocation

### §12.1 The execution boundary

```
ReviewedMutationRequest does not call Engine.
```

A `ReviewedMutationRequest` is consumer-side handoff data. The
Engine call is a separate step taken by a Python caller in
Layer 4.

Allowed forms of the actual invocation (illustrative only;
M02 does not implement these):

```python
engine.add_claim(
    subject_id, claim_type, rule_id, rule_version, reason_code,
    base_confidence=base_confidence, status=status, flags=flags,
)

engine.add_evidence(
    claim_id, raw_ref_id, evidence_type, strength,
)

engine.add_gap(
    claim_id, gap_type, required_evidence_type, severity, rule_id,
)

engine.register_contradiction(claim_id, evidence_id)
```

### §12.2 Forbidden invocation forms

The following are forbidden as ways to convert a
`ReviewedMutationRequest` into an Engine call:

```python
execute_mutation_request(request)
request.execute(engine)
engine.apply_request(request)
auto_dispatch(request)
getattr(engine, request.method)(*request.args)
getattr(engine, name)(**args)
dispatch[method_name](engine, args)
eval(request.code)
exec(request.code)
```

Also forbidden as stored or referenced in the request:

```
- callables
- lambdas
- method objects
- arbitrary code
- a method-name string used as the execution token
- a target referring to a private Engine attribute or method
- a target referring to a method that does not exist in
  the current Engine public API
- a reflection-based execution path
```

The mutation review may inspect a method-name string as
metadata; the caller in Layer 4 invokes the method **by
name in source code**, not by reflection on the request.

### §12.3 Caller responsibility immediately before invocation

Immediately before invoking the Engine method, the caller
verifies, at minimum:

```
§12.3.1  The request is one the caller's own consumer workflow
          approved.
§12.3.2  The target and arguments in the source code match the
          target and arguments that were reviewed.
§12.3.3  The target method exists in the current Engine public
          API.
§12.3.4  The referenced Engine IDs identify the objects the
          caller intends.
§12.3.5  The intended call order is consistent with PR43.
§12.3.6  If the operation requires a lifecycle transition, a
          separate candidate / review / call sequence is
          followed (§14), not bundled into a data-registration
          candidate.
```

§12.3 does **not** guarantee freshness, currentness, or
state-binding. M02 does not define a mechanical stale check.
That is OC-C / PR72-M03 and OC-B / PR74-M05.

A document **must not** claim that an `M02-reviewed` request
is "fresh", "current", or "state-bound" as a mechanical
guarantee.

---

## §13 Call success semantics

```
Engine public method invocation success
  = Engine accepted that method's arguments and applied the
    method's existing runtime behavior.
```

Call success does **not** mean:

```
- the source RoleAssignment is objectively correct
- the Claim is true
- the Evidence is strong
- the operator's final judgment has been recorded
- a lifecycle transition has completed
- the downstream report is final
- the rule has been verified
- the proposal was correct
```

Example expansions:

```
add_claim success
  != Claim confirmed
add_evidence success
  != Claim confirmed
register_contradiction success
  != Claim automatically disputed or refuted
```

Lifecycle transitions occur only when the caller explicitly
invokes the corresponding `_if_ready` method, separately
reviewed under §14.

---

## §14 Lifecycle separation

Lifecycle mutation is **never** bundled inside a data
registration candidate.

A candidate whose target is `add_evidence(...)` is reviewed
only as an `add_evidence` candidate. It does **not** authorize:

```
confirm_claim_if_ready(claim_id)
refute_claim_if_ready(claim_id)
dispute_claim_if_ready(claim_id)
resolve_disputed_claim_if_ready(claim_id)
refute_disputed_claim_if_ready(claim_id)
refute_disputed_claim_if_ready_by_freshness(claim_id)
register_contradiction_resolution(claim_id, evidence_id)
```

If a lifecycle call is needed, it is a **separate** candidate
with its own review:

```
candidate A   add_evidence(...)
candidate B   confirm_claim_if_ready(claim_id)
```

Each candidate carries its own expected effect, non-effects,
and review. One candidate's review never authorizes another
candidate's call.

---

## §15 Rule / RuleStats separation

M02 does **not** auto-derive any of the following from a
RoleAssignment, a candidate, or a reviewed request:

```
update_rule_stats(...)
register_rule(...)
RuleDefinition creation
rule quality verdict
```

If `register_rule` or `update_rule_stats` is needed, the
consumer creates a separate candidate / review / call sequence
for that call. Side-effect `update_rule_stats` on the back of a
data registration call is forbidden.

`RuleStats` update provenance — caller identity, update
reason, source observation reference, delta provenance,
precision input basis, policy reference — is **OC-G /
PR78-M09** and is not specified by M02. M02 only states what
M02 does not do.

---

## §16 Rejection and hold conditions

A candidate or a reviewed request never silently advances. A
consumer **must not** auto-rewrite a rejected candidate and
re-submit it.

### §16.1 Candidate materialization is refused when

```
- the source RoleAssignment is unresolved
- the interpretation context is absent
- provenance is absent
- traceability is absent
- AllowedUse / ForbiddenUse conflict
- the proposed target is not an existing public Engine method
- the proposed target is a private Engine attribute or method
- argument derivation is unclear
- an external score is piped directly into an Engine signal
  (§7.1)
- a lifecycle effect is hidden inside what looks like a data
  registration
- a RuleStats side effect is hidden inside the call
```

### §16.2 Review rejects or holds when

```
- the exact arguments cannot be inspected
- the target signature does not match the reviewed arguments
- the expected effect is overstated
- the non-effects are missing or incomplete
- the candidate diverges from its source RoleAssignment
- referenced Engine IDs are ambiguous
- the reviewer requires additional context
- the reviewer cannot determine whether the current Engine
  state makes the call meaningful
```

Refusal and hold leave Engine state **unchanged**. They do not
create a partial mutation, a partial record, or any Engine
write.

---

## §17 A2 remains undefined

M02's closure of A5 / A6 / A7 **does not** close A2:

```
A2  AdapterTrace -> RoleAssignment    remains UNDEFINED
```

M02 explicitly forbids:

```
- a PR64 dict to PR61 dict converter
- automatic key-name matching between an adapter trace and a
  role-assignment representation
- automatic copy of `contextual_primary_role` into `primary_role`
- automatic synthesis of allowed / forbidden uses from
  adapter output
- direct materialization of a candidate from an adapter trace
- skipping the RoleAssignment stage
```

M02's input is an **already-authored consumer-side
RoleAssignment**. The bridging of A2 is left as a future
consumer-policy or future PR concern that M02 does not
schedule.

---

## §18 Relationship to existing layers

```
PR60 Role Assignment Policy (ROLE_ASSIGNMENT_POLICY_SPEC.md)
  = the candidate-precedent interpretation boundary.
    M02 starts where PR60 ends.

PR43 Engine Method Call Playbook
     (docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md)
  = the call-order guide the caller follows after review.
    M02 sits one layer above PR43 as the explicit gate that
    precedes following PR43.

PR57 Operator Decision Boundary
     (OPERATOR_DECISION_BOUNDARY_SPEC.md)
  = the proposal-accepted workflow gate.
    M02 mutation review is a SEPARATE gate. The two are not
    one boolean.

PR58 Proposal Usage Playbook
     (docs/guides/PROPOSAL_USAGE_PLAYBOOK.md)
  = aligned: it already states that operator acceptance does
    not directly cause Engine mutation. M02 makes the
    intermediate handoff explicit.

PR59 Data Access Profile Contract
     (DATA_ACCESS_PROFILE_CONTRACT.md)
  = aligned: AllowedUse / ForbiddenUse are consumer policy
    axes that feed §5 admission and §9 review.

PR70 / M01 Minimal Operational Scaffold
     (PR_070_MINIMAL_OPERATIONAL_SCAFFOLD.md /
      examples/operation/minimal_operational_scaffold.py)
  = the executable evidence of OC-A. M02 makes A5 / A6 / A7
    handoff conceptual, not executable.
```

M02 does **not** deprecate or replace any of these.

---

## §19 Relationship to future M-series

```
PR72-M03  Engine read consistency  (OC-C)
  M02 does NOT define state identity, packet-to-state binding,
  capture atomicity, snapshot digest, packet revision, or
  decision-time state identity. M02 does NOT claim mechanical
  stale detection.

PR73-M04  (conditional)
  M02 does not pre-define the slot.

PR74-M05  Operator decision record  (OC-B)
  M02 does NOT define a persistent operator decision record
  shape or a stale revalidation rule.

PR75-M06  Downstream re-entry  (OC-E)
  M02 does NOT define how external results re-enter the
  consumer workflow.

PR76-M07  Effective confidence trace  (OC-D)
  Out of scope.

PR77-M08  Complete reference operation  (OC-F)
  Out of scope.

PR78-M09  RuleStats update provenance  (OC-G)
  M02 explicitly defers caller identity, update reason,
  source observation reference, delta provenance, precision
  input basis, and policy reference.
```

M02 does **not** auto-start PR72-M03 or any later M-series PR.

---

## §20 Non-goals

§20 enumerates what M02 deliberately does not introduce. None
of these are scheduled by M02.

```
- EngineInputCandidate class / dataclass / TypedDict /
  NamedTuple / Pydantic model
- ReviewedMutationRequest class / dataclass / TypedDict /
  NamedTuple / Pydantic model
- OperatorDecisionRecord class
- PacketRevision class
- StateRevision class
- JSON Schema for any of the above
- ragcore symbol
- Engine method (public or private)
- request executor / dispatcher / router / queue
- transaction manager / rollback / retry system
- stale detector / state revision / packet revision
- signature / cryptographic digest standard
- operator authentication / operator UI
- approval database / audit log schema
- automatic API invocation
- automatic lifecycle invocation
- automatic RuleStats update
- adapter-to-role mapping (A2)
- downstream tool execution
- domain-specific pipeline
- network call
- LLM call
- runtime behavior change
- judgment semantics change
- snapshot schema change
- snapshot top-level keys change
- modifier value change
- effective-confidence formula change
```

---

## §21 Consumer implementation freedom

Within the boundary M02 fixes, consumers are free to choose:

```
- how a candidate is stored (in-memory object, dict, JSON,
  database row)
- how a reviewed request is stored
- how review actors and review times are represented
- how non-mechanical stale judgments are made
- how candidates are batched on the consumer side (without
  inventing a batch executor)
- how the consumer surfaces a review to a human
- how the consumer surfaces a rejected candidate to the
  author
- which subset of the §7 conceptual content is materialized
  as fields versus represented in a free-text rationale
- which review actor model fits the consumer organization
- how the consumer connects review approval to the caller in
  Layer 4 without inventing a dispatcher
```

These choices are explicitly out of M02's scope and remain
consumer policy.

---

## §22 Closing position

M02 closes the **conceptual** boundary between context
interpretation and Engine mutation:

```
M02 closes the conceptual handoff
  RoleAssignment
    -> EngineInputCandidate
      -> ReviewedMutationRequest
        -> explicit Engine public API call

M02 does NOT close
  A2  AdapterTrace -> RoleAssignment
  OC-B  Operator decision record persistence
  OC-C  Engine read consistency
  OC-D  Effective-confidence trace
  OC-E  Downstream re-entry
  OC-F  Complete reference operation
  OC-G  RuleStats provenance

M02 does NOT add
  Python types  /  dispatcher  /  executor  /  queue
  schema       /  serialization format
  ragcore symbol  /  Engine method  /  snapshot key
  runtime behavior change  /  judgment semantics change
```

The actual Engine mutation event is, and remains, a Python
caller explicitly invoking one existing Engine public method.
M02 does not introduce a faster path, an automatic path, a
reflective path, or any alternative path to that invocation.
