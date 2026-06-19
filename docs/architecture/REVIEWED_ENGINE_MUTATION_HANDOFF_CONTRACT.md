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
public                        != state-mutating
read-only public method       != mutation candidate target
review disposition            != ReviewedMutationRequest
placeholder-bearing planned
  step                        != review-eligible exact candidate
approved exact candidate
  review                      -> may materialize a
                                  ReviewedMutationRequest
actual Engine mutation        =  caller explicitly invokes one
                                  existing state-mutating
                                  Engine public method
```

These twelve load-bearing boundary statements (eleven
inequalities, one implication, one equality) are the locks of
M02. Every other section refines one of them.

---

## §4 Four-layer model

For the **OC-A role-derived ingress path** — the path M01
labeled A5 / A6 / A7 — four conceptual layers separate context
interpretation from runtime mutation:

```
Layer 1   admitted RoleAssignment
Layer 2   non-executable EngineInputCandidate
Layer 3   ReviewedMutationRequest created only from an
            approved exact candidate review
Layer 4   explicit invocation of one existing state-mutating
            Engine public method
```

The boundaries between layers must not be collapsed.

§4 describes the OC-A role-derived path. Lifecycle transitions
(§14.1), contradiction-resolution (§14.2), Gap resolution
(§14.3), and Rule / RuleStats (§15) are separately reviewed,
separately invoked operations whose source-basis contracts M02
does not over-fix; see those sections for the per-class
admission rules.

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
state-mutating Engine public method invocation, supported by
an explicit consumer-side source basis appropriate to its
mutation class.
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

### §4.4 Layer 4 — Explicit invocation of one existing state-mutating Engine public method

Layer 4 is the only event that changes Engine state. The
caller writes the invocation in source code by name. The target
must be an existing **state-mutating** Engine public method.

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

A target being public is **necessary but not sufficient**. The
target must also be an existing state-mutating Engine public
method whose existing effect matches the proposed mutation.

§12.1 enumerates the public Engine method classification by
state-mutation behavior. A read-only public method is **not** a
valid M02 mutation candidate target; invoking a read-only
method successfully is not "an Engine mutation".

Reaching Layer 3 does **not** call Engine; reaching Layer 4
**is** the call.

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
state-mutating Engine public method invocation, supported by
an explicit consumer-side source basis.
```

For the **OC-A role-derived ingress path** that source basis
is an admitted RoleAssignment (§5). Other mutation classes
have their own source basis as defined by their per-class
sections:

```
lifecycle transition                  see §14.1
contradiction resolution               see §14.2
Rule / RuleStats                       see §15
```

M02 does not declare a single universal source-basis rule that
applies to every mutation class. The OC-A admission contract
(§5) applies only to OC-A role-derived candidates.

A candidate:

```
- describes exactly one proposed invocation
- targets an existing state-mutating Engine public method
- is inspectable in full before any review
- carries no callable, no method object, no lambda, no
  evaluatable code
- references the target method only as inspection metadata
  (the method name string is a label, not an execution token)
- does not authorize any Engine call by its existence
- carries an explicit source-basis reference appropriate to
  its mutation class
```

A candidate is not Engine input until and unless a caller, at
Layer 4, explicitly invokes that exact state-mutating public
method with those exact arguments.

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

- mutation class
    (OC-A role-derived / lifecycle transition / contradiction
     resolution / Rule / RuleStats — selects which source-basis
     rule applies)

- source basis reference
    (for an OC-A role-derived candidate: the admitted
     RoleAssignment;
     for a lifecycle transition: an explicit statement of the
     target Claim's current status and the readiness signal
     the consumer is relying on;
     for a contradiction resolution: the contradiction set
     entry to be marked resolved;
     for a Rule / RuleStats candidate: the consumer policy
     basis — M02 does not freeze its shape; OC-G / PR78-M09
     completes RuleStats provenance)

- assignment context reference
    (OC-A only; under which interpretation context the
     RoleAssignment was made)

- source provenance / traceability reference

- intended existing state-mutating Engine public method
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
- does not itself resolve any Gap (Gap resolution requires a
  separate resolve_gaps_for_evidence candidate, §14.3)
- does not register or resolve any contradiction (those are
  separate candidates, §14.2)
- does not produce a final verdict
```

Non-effects are not editorial. They are review-critical
content.

---

## §8 Candidate atomicity, sequencing, and generated IDs

### §8.1 One candidate, one call

```
one EngineInputCandidate
  =  one proposed state-mutating Engine public method invocation
```

A multi-call operation is expressed as a sequence of separate
candidates, each describing exactly one invocation.

### §8.2 Generated-ID dependency rule

Engine object IDs (`entity_id`, `claim_id`, `evidence_id`,
`gap_id`, `relation_id`) come into existence only when the
preceding state-mutating call returns. Therefore:

```
A dependent candidate is not exact and review-eligible until
every required Engine object ID has been produced and inserted
as the actual argument value.
```

Specifically:

```
planned step with placeholder ID
  != exact EngineInputCandidate

placeholder-bearing draft
  != review-eligible candidate
```

If a placeholder is later replaced by an actual ID, the
candidate content has changed; the prior review (if any) does
not apply to the new exact content, and §11 (exact-content
review binding) requires a new review of the now-exact
candidate.

### §8.3 Sequential materialization

For multi-step OC-A operations, candidates are materialized,
reviewed, approved, and invoked **one at a time**, in order.
The IDs returned by each invocation are inserted into the next
candidate as it is materialized:

```
materialize candidate 1 from RoleAssignment
  -> review
  -> approve
  -> invoke   engine.add_entity(entity_type=...)
                          -> returns actual entity_id

materialize candidate 2 using the actual entity_id
  -> review
  -> approve
  -> invoke   engine.add_claim(subject_id=entity_id, ...)
                          -> returns actual claim_id

materialize candidate 3 using the actual claim_id
  -> review
  -> approve
  -> invoke   engine.add_evidence(claim_id=claim_id, ...)
                          -> returns actual evidence_id

(separate candidates / reviews / invocations for any further
 steps, including any lifecycle transition, contradiction
 resolution, or Gap resolution)
```

### §8.4 Consumer-side grouping

Consumers may keep a higher-level **plan** that groups multiple
intended candidates as a conceptual operation. The plan is a
planning artifact, not an exact candidate. M02 does **not**
define:

```
- a batch executor
- a transaction manager
- rollback
- all-or-nothing semantics
- a dependency resolver
- automatic call sequencing
- pre-materialization of all candidates with placeholder IDs
- pre-binding of all arguments before any call returns
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
- targeted at an existing state-mutating Engine public
  method per §12.1 (read-only methods and the serialization
  boundary are not M02 candidate targets)
- inspectable in its exact proposed arguments (no placeholder
  IDs; §8.2)
- traceable to its source basis appropriate to its mutation
  class (an admitted RoleAssignment for OC-A role-derived
  candidates; the per-class source basis declared in §6)
- explicit about preconditions, expected effect, and
  non-effects
- not produced from an unresolved RoleAssignment (OC-A only)
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

### §9.4 Review disposition is not a ReviewedMutationRequest

A consumer-side mutation review yields a **review disposition**,
which may be one of:

```
approved
rejected
hold
```

These three are review outcomes. They are **not** themselves
`ReviewedMutationRequest` instances.

```
candidate reviewed
  != ReviewedMutationRequest automatically created

approved exact candidate review
  -> may materialize a ReviewedMutationRequest

rejected candidate review
  -> remains a rejected consumer-side review disposition
  -> never enters Layer 3
  -> no invocation
  -> no Engine state change

held candidate review
  -> remains a held consumer-side review disposition
  -> never enters Layer 3
  -> no invocation
  -> no Engine state change
```

Only the **approved** disposition may materialize a Layer 3
`ReviewedMutationRequest`. Rejected and held dispositions are
recorded on the consumer side as their own artifacts; their
persistent storage shape is OC-B / PR74-M05 and is not
specified by M02.

---

## §10 ReviewedMutationRequest definition

```
An EngineInputCandidate whose exact proposed invocation has
received an explicit consumer-side mutation review approval.
```

A `ReviewedMutationRequest` exists only for an approved
disposition (§9.4). Rejected and held dispositions are
recorded on the consumer side as their own non-Layer-3
artifacts.

A reviewed request:

```
- has a request identity (consumer-assigned, opaque)
- references exactly one reviewed candidate identity
- carries the reviewed target state-mutating method name and
  the reviewed exact arguments
- carries an approved review disposition reference, the
  approval basis / rationale, a review actor reference, and
  a review time reference (the representation of "time" is
  consumer-side; M02 does not freeze a timestamp format)
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

## §12 Explicit invocation of one existing state-mutating Engine public method

### §12.1 The execution boundary and target classification

```
ReviewedMutationRequest does not call Engine.
```

A `ReviewedMutationRequest` is consumer-side handoff data. The
Engine call is a separate step taken by a Python caller in
Layer 4.

**Target classification.** The target of an M02 candidate must
be a **state-mutating Engine public method**. The current
Engine public surface (40 public methods) classifies as
follows (observed against `ragcore/engine.py` on the M02
baseline `main` `896e01e`):

```
state-mutating public methods (20)
  add_entity / add_observation / add_claim / add_evidence /
  add_relation / add_gap
  resolve_gaps_for_evidence
  register_contradiction / register_contradiction_resolution
  confirm_claim_if_ready / refute_claim_if_ready /
  dispute_claim_if_ready / resolve_disputed_claim_if_ready /
  refute_disputed_claim_if_ready /
  refute_disputed_claim_if_ready_by_freshness
  register_rule / update_rule_stats
  register_hint_evidence_types /
  unregister_hint_evidence_types / clear_hint_evidence_types

read-only public methods (18) — NOT M02 candidate targets
  get_entity / get_observation / get_claim / get_evidence /
  get_relation / get_gap
  evidences_for_claim / gaps_for_claim / gap_resolution
  contradictions_for_claim /
  resolved_contradictions_for_claim /
  active_contradictions_for_claim /
  active_contradictions_by_freshness
  claim_lifecycle_history / evidence_freshness
  get_rule / get_rule_stats
  compute_effective_confidence

serialization boundary (2) — NOT M02 mutation targets
  to_snapshot / from_snapshot
```

Invoking a read-only public method successfully is **not** an
Engine mutation under M02. A candidate that targets a read-only
method is structurally invalid as an M02 mutation candidate.
The serialization boundary (`to_snapshot` / `from_snapshot`) is
outside the M02 mutation contract; M02 does not classify it as
a mutation target.

If the public Engine surface gains a new state-mutating public
method in a future PR, that method becomes eligible as an M02
candidate target. If it gains a new read-only method, the same
exclusion in this section applies.

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
          API and is a state-mutating method per §12.1.
§12.3.4  The referenced Engine IDs identify the objects the
          caller intends.
§12.3.5  The intended call order is consistent with PR43.
§12.3.6  If the operation requires a lifecycle transition or
          a contradiction resolution or a Gap resolution, a
          separate candidate / review / call sequence is
          followed (§14.1 / §14.2 / §14.3), not bundled into a
          data-registration candidate.
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
State-mutating Engine public method invocation success
  = Engine accepted that method's arguments and applied the
    method's existing runtime behavior.
```

Read-only public method invocation success is not an Engine
mutation under M02; §13 covers only the Layer 4 mutation
event.

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
reviewed under §14.1. Contradiction resolution requires a
separate `register_contradiction_resolution` candidate (§14.2).
Gap resolution requires a separate `resolve_gaps_for_evidence`
candidate (§14.3).

---

## §14 Lifecycle separation

### §14.1 Lifecycle transition separation

Lifecycle mutation is **never** bundled inside a data
registration candidate.

The lifecycle-transition state-mutating public methods are:

```
confirm_claim_if_ready(claim_id)
refute_claim_if_ready(claim_id)
dispute_claim_if_ready(claim_id)
resolve_disputed_claim_if_ready(claim_id)
refute_disputed_claim_if_ready(claim_id)
refute_disputed_claim_if_ready_by_freshness(claim_id)
```

A candidate whose target is `add_evidence(...)` is reviewed
only as an `add_evidence` candidate. It does **not** authorize
any of the lifecycle-transition methods above.

If a lifecycle call is needed, it is a **separate** candidate
with its own review:

```
candidate A   add_evidence(...)
candidate B   confirm_claim_if_ready(claim_id)
```

Each candidate carries its own expected effect, non-effects,
and review. One candidate's review never authorizes another
candidate's call.

M02 does not over-fix the source-basis contract for lifecycle
transition candidates beyond requiring that the candidate be
separately inspectable, separately reviewed, separately
approved, and separately invoked.

### §14.2 Contradiction-resolution separation

`register_contradiction_resolution(claim_id, evidence_id)` is a
**contradiction-resolution mutation**, not a lifecycle
transition. It is classified separately from §14.1 to avoid
mis-labeling.

It is also **never** bundled inside a data registration
candidate.

```
add_evidence candidate
  != register_contradiction_resolution authorization

register_contradiction candidate
  != register_contradiction_resolution authorization
```

`register_contradiction_resolution` requires its own
inspectable, reviewed, approved, and explicitly invoked
operation, with its own expected effect and non-effects.

M02 does not over-fix the source-basis contract for
contradiction-resolution candidates beyond the same separation
requirement.

### §14.3 Gap resolution separation

`resolve_gaps_for_evidence(evidence_id)` is the existing
state-mutating Engine public method that performs Gap
resolution.

```
add_evidence candidate
  != resolve_gaps_for_evidence candidate

add_evidence review
  != Gap resolution authorization
```

`add_evidence` does not itself resolve any Gap. Gap resolution
requires a separate explicit `resolve_gaps_for_evidence`
candidate with its own review.

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
- (OC-A role-derived only) the source RoleAssignment is
  unresolved; the interpretation context is absent;
  provenance is absent; traceability is absent;
  AllowedUse / ForbiddenUse conflict
- the proposed target is not an existing public Engine method
- the proposed target is a public method that is not
  state-mutating (§12.1) — read-only methods and the
  serialization boundary are not M02 candidate targets
- the proposed target is a private Engine attribute or method
- a placeholder ID stands in for an Engine object ID that has
  not yet been produced (§8.2)
- argument derivation is unclear
- an external score is piped directly into an Engine signal
  (§7.1)
- a lifecycle effect is hidden inside what looks like a data
  registration (§14.1)
- a contradiction-resolution effect is hidden inside what
  looks like a data registration (§14.2)
- a Gap resolution effect is hidden inside what looks like a
  data registration (§14.3)
- a RuleStats side effect is hidden inside the call (§15)
```

### §16.2 Review rejects or holds when

```
- the exact arguments cannot be inspected
- the target signature does not match the reviewed arguments
- the expected effect is overstated
- the non-effects are missing or incomplete
- (OC-A role-derived only) the candidate diverges from its
  source RoleAssignment
- referenced Engine IDs are ambiguous or are placeholders
- the reviewer requires additional context
- the reviewer cannot determine whether the current Engine
  state makes the call meaningful
```

Refusal and hold leave Engine state **unchanged**. They do not
create a partial mutation, a partial record, or any Engine
write.

A rejected or held review yields a rejected or held **review
disposition** (§9.4). Such a disposition is **not** a
`ReviewedMutationRequest` and does not enter Layer 3. The
consumer-side persistent storage of rejected and held
dispositions is OC-B / PR74-M05.

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
M02 closes the conceptual handoff for the OC-A role-derived
ingress path:
  admitted RoleAssignment
    -> non-executable EngineInputCandidate
      -> approved exact candidate review
        -> ReviewedMutationRequest
          -> explicit invocation of one existing
              state-mutating Engine public method

M02 also fixes the separation principle for:
  lifecycle transitions          (§14.1)
  contradiction resolution       (§14.2)
  Gap resolution                  (§14.3)
  Rule / RuleStats                (§15)
without over-fixing their per-class source-basis contracts.

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
caller explicitly invoking one existing **state-mutating**
Engine public method. M02 does not introduce a faster path, an
automatic path, a reflective path, or any alternative path to
that invocation.

---

## §23 Post-M04 public surface addendum (PR73-M04, 245차)

This section is a current-state addendum. M02's historical
baseline of 40 public methods / 18 read-only / 20 state-mutating
/ 2 serialization on `main` `896e01e` is preserved unchanged in
§12.1.

After PR73-M04, the post-M04 public surface counts are:

```
state-mutating public methods   20  (unchanged set; PR73-M04
                                     instruments each with a
                                     revision advance call on
                                     the success path)
read-only public methods        19  (was 18; +state_identity)
serialization boundary           2  (unchanged set: to_snapshot,
                                     from_snapshot)
total public methods            41
```

Explicit classification of the new entry:

```
state_identity
  = read-only
  = NOT a M02 mutation candidate target
  = NOT eligible to appear in a ReviewedMutationRequest
  = NOT instrumented to advance the revision
```

No method was re-classified from read-only to state-mutating or
vice versa. The 20 state-mutating set in §12.1 remains the
exhaustive list of M02 candidate targets.

---

## §24 Post-M05 addendum (PR74-M05, 2026-06-19)

PR74-M05 (`OPERATOR_DECISION_RECORD_REVALIDATION_CONTRACT.md`)
adds **consumer-side persistence and reuse policy** for the
mutation-review disposition produced by M02 §9.

```
- M05 records the exact candidate review disposition
  (approved / rejected / hold), the reviewed target Engine
  method name, the reviewed exact arguments, the referenced
  IDs, the source-basis reference, and the decision-time
  EngineStateIdentity.

- A persisted approved disposition record is NOT a
  ReviewedMutationRequest. ReviewedMutationRequest
  materialization remains §10 / §11's exact-content review
  binding step, performed against the reviewed candidate at
  the materialization moment.

- A persisted approved disposition record is NOT an Engine
  invocation. §12 explicit invocation remains the only path
  by which an Engine state-mutating public method is called.

- Before a reviewed mutation request remains eligible for
  explicit invocation per §12, the consumer MUST verify
  (M05 §12.1):
    * exact candidate content unchanged                 (§10)
    * reviewed method name unchanged                    (§10)
    * reviewed exact arguments unchanged                (§10)
    * referenced IDs unchanged                          (§10)
    * decision-time EngineStateIdentity equals current
      Engine.state_identity()                           (M05 §7.3 A)
    * §12.3 caller checks still pass at invocation time

- If the decision-time identity differs from the current
  identity (M05 §7.3 B or C), the existing approval cannot
  be reused. The consumer must re-inspect current Engine
  objects, reconstruct the exact candidate if still
  appropriate, perform a new mutation review per §9, and
  create a new decision record (M05 §12.2).

- §12.3 forbidden mechanisms remain forbidden: no
  reflection-based dispatch, no automatic request
  materialization, no automatic Engine call, no name-based
  string -> method lookup, no queue / scheduler / worker
  invocation of a stored approval.
```

M05 does not modify the M02 four-layer model, the §11
exact-content review binding, the §12 explicit invocation
boundary, or the §15 Rule / RuleStats separation. The §12.1
historical baseline of 40 methods on `main` `896e01e` and the
§23 post-M04 counts (20 state-mutating / 19 read-only / 2
serialization = 41 total) are preserved unchanged.

---

## §25 Post-M06 addendum (PR75-M06, 2026-06-19)

PR75-M06 (`DOWNSTREAM_RESULT_REENTRY_CONTRACT.md`) consumes
the M02 four-layer model unchanged for the special case where
the candidate is derived from a downstream investigation
result.

```
- A result-derived EngineInputCandidate uses the same
  four-layer model from §4: RoleAssignment ->
  EngineInputCandidate -> ReviewedMutationRequest ->
  explicit invocation of one existing state-mutating Engine
  public method.

- PR75-M06 does NOT introduce a separate "re-entry
  executor", a separate "re-entry request type", a separate
  "result request" dispatcher, or any alternative
  materialization path. The existing four-layer model is
  reused verbatim.

- A result-derived candidate must record, in addition to the
  §7 minimum content:
    * the exact result trace or fragment reference
    * the role-assignment context reference
    * the argument translation basis (how the candidate's
      proposed arguments were derived from the result trace +
      role assignment)
  These are M06 source-basis fields. They do NOT modify §7's
  conceptual obligations.

- Direct substitutions remain forbidden (M06 §4.3 / §9.3 /
  §20):
    external result   != Evidence
    tool output       != Evidence
    result score      != Evidence.strength
    severity label    != Gap.severity
    external status   != Claim.status

- Lifecycle / Gap / contradiction separation (§14.1 / §14.2 /
  §14.3) and Rule / RuleStats separation (§15) are preserved.
  M06 explicitly forbids automatic chaining of, e.g.,
  add_evidence -> confirm_claim_if_ready into one pipeline.
  Each transition is its own candidate / review / decision /
  revalidation / invocation cycle.

- The §12.3 forbidden execution mechanisms (reflection,
  name-string dispatch, request.execute(engine),
  engine.apply_request(request), queue / scheduler / worker
  invocation, stored decision auto-execution) remain
  forbidden for result-derived candidates.

- The §13 call-success semantics are unchanged: a successful
  Stage 6 invocation under M06 proves the Engine accepted
  the supplied arguments and applied that method's existing
  runtime behavior. It does NOT prove that the external
  result is true.
```

PR75-M06 does not modify the four-layer model, the §11
exact-content review binding, the §12 / §12.3 invocation
boundary, the §15 separation principles, or the §23 / §24
historical addenda. §1 ~ §22 historical body and §23 / §24
addenda remain unchanged.
