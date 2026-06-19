# Downstream Result Re-entry Contract

```text
PR75-M06
type:    docs-only architecture contract
status:  normative
date:    2026-06-19
base:    main 80759048 (PR74-M05 — Operator Decision Record /
                        Decision-State Revalidation Contract)
```

## Core sentences

```text
A downstream result enters the consumer-side re-entry chain
only as a NEW external source artifact.

It reaches Engine state ONLY after separate translation,
contextual role assignment, optional candidate
materialization, exact-content mutation review, decision
recording and revalidation, separate ReviewedMutationRequest
materialization, and an explicit caller-written invocation of
one existing state-mutating Engine public method.

consumer workflow re-entry
  != Engine state entry

The result does not become Engine evidence, Engine truth,
execution authority, or lifecycle-transition authority merely
because it exists or because an investigation produced it.
The chain may legitimately terminate at any stage with no
Engine mutation (§4.4 / §10).
```

---

## §0 Scope limitation

PR75-M06 fixes the conceptual obligations of **downstream
result re-entry** at the layer between an investigation that a
consumer chose to run and the point at which an existing
state-mutating Engine public method may be invoked. The
contract is normative for consumer-side adapters and **does
not** introduce any runtime code, ragcore symbol, Engine
method, snapshot field, packet field, database table, JSON
schema, serialization format, tool runner, network call,
adapter executor, role-assignment executor, candidate
materializer, mutation-review executor, decision-record
executor, or any automated dispatcher.

### §0.1 In scope

```
- consumer-side investigation initiation boundary
- downstream result trace obligations (as a new external artifact)
- operational failure vs semantic ambiguity separation
- contextual role assignment of result items / fragments
- EngineInputCandidate materialization admission
- M02 mutation-review handoff for result-derived candidates
- M05 decision record + state revalidation for the
  mutation-review-family record
- explicit Engine invocation boundary
- lifecycle / Gap / contradiction separation
- RuleStats separation
- multiple-result / aggregation policy
- process-restart and restore behavior
- PR51 packet preservation through re-entry
```

### §0.2 Out of scope

```
- a complete end-to-end reference operation
  (M08 — PR77 territory)
- runtime tool execution / network IO / orchestrator
- adapter executor / role-assignment executor / candidate
  materializer / mutation-review executor /
  decision-record executor
- automated investigation launcher
- automated Evidence registration
- automated Claim confirmation / refutation / disputation
- automated Gap resolution / contradiction resolution
- automated RuleStats update
- automated revalidation
- packet capture identity
- packet binding / CAPTURE_BOUND / CURRENTLY_MATCHED /
  mechanical packet STALE
- M03 packet STALE re-interpretation
- domain-specific tool / vulnerability / scanner / data
  vocabulary in normative text
```

### §0.3 Things PR75-M06 explicitly does not implement

```
- Python ResultTrace / InvestigationRun / DownstreamResult
  dataclass, TypedDict, NamedTuple, Pydantic model, or
  Protocol
- JSON Schema for result traces or candidates
- database schema or audit-log backend for results
- automatic Engine method
- dispatcher / executor / scheduler / queue
- packet-binding helper
- CURRENTLY_MATCHED helper
- packet STALE detector
- automatic revalidation worker
- automatic downstream execution
- end-to-end reference operation example
```

---

## §1 Investigation origin

The M-series M01 scaffold (PR70-M01) surfaces a seven-stage
Lane C `downstream_reentry` whose middle stages are
`UNDEFINED`:

```
C1  operator decision record                UNDEFINED  (OC-B)
C2  consumer-side investigation             TODO
C3  new external result trace               TODO
C4  result role assignment                  TODO
C5  EngineInputCandidate                    UNDEFINED  (OC-E)
C6  ReviewedMutationRequest                 UNDEFINED  (OC-E)
C7  explicit re-entry authorization         BLOCKED    (OC-E)
```

C2 ~ C7 together carry the `OC-E` label. M02 closed the OC-A
ingress handoff; M03 fixed the read-consistency vocabulary;
M04 added the minimum identity primitive; M05 closed OC-B at
the operator-decision-record + revalidation policy layer.
PR75-M06 closes OC-E at the **conceptual re-entry boundary**:
how a downstream result, once it exists, must be treated to
become eligible for an explicit Engine state-mutating
invocation.

M06 stops at the conceptual chain. A complete
domain-neutral reference operation that exercises the chain
end-to-end is M08 (PR77) territory and is explicitly NOT
in M06's scope.

---

## §2 Empirical baseline

```
main at PR75-M06 start:    80759048e98d9255596a8aa56bf4ea94cd9d1250
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

PR51 packet keys (M03-locked names, unchanged by M04 / M05):

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
PR57   OPERATOR_DECISION_BOUNDARY_SPEC         §19 Post-M05
PR60   ROLE_ASSIGNMENT_POLICY_SPEC             §1 ~ §24
PR63   EXTERNAL_ADAPTER_TRANSLATION_BOUNDARY   §1 ~ §31
M02    REVIEWED_ENGINE_MUTATION_HANDOFF        §23 Post-M04 /
                                                §24 Post-M05
M03    ENGINE_READ_CONSISTENCY_CONTRACT        §19 Post-M04 /
                                                §20 Post-M05
M04    ENGINE_STATE_IDENTITY_PRIMITIVE         §11 Post-M05
M05    OPERATOR_DECISION_RECORD_REVALIDATION   §0 ~ §20
```

(PR59 = Data Access Profile Contract, separated the six
independent interpretation axes. PR60 = Role Assignment
Policy Spec, defines contextual role assignment over those
axes. PR61 = Minimal Consumer-Side Role Assignment Example,
demonstrates one local consumer representation. PR63 =
External Adapter Translation Boundary Spec, records the
boundary an adapter follows when translating an external
source artifact. M06 reuses PR60 + PR63 normative content;
PR59 axes and PR61 example are unchanged.)

M06 normative addenda land at:

```
PR63 external adapter spec  §32  Post-M06 addendum
PR60 role assignment spec   §25  Post-M06 addendum
M02 handoff contract        §25  Post-M06 addendum
M05 decision contract       §21  Post-M06 addendum
```

---

## §3 Core boundary statements

### §3.1 Re-entry is consumer-driven new external work

```
A downstream result does NOT continue a prior decision or
proposal automatically.

A downstream result does NOT become an Engine fact merely by
existing.

A downstream result enters the consumer-side re-entry chain
only by being treated as a NEW external source artifact. It
reaches Engine state only by being run through the
seven-stage chain in §4 / §3.2.
```

### §3.2 The chain is seven explicitly separate stages

```
1.   consumer investigation initiation
2.   downstream result trace
3.   contextual result role assignment
4.   EngineInputCandidate materialization consideration
5.   M02 mutation review and M05 decision record
5.5  separate ReviewedMutationRequest materialization
     (M02 §10 / §11)
6.   explicit invocation of one existing state-mutating
     Engine public method
```

Stage 5.5 is the M02 four-layer model's `EngineInputCandidate
-> ReviewedMutationRequest` step. M05 mutation-review-family
record (Stage 5) and ReviewedMutationRequest (Stage 5.5) are
distinct artifacts. The `ReviewedMutationRequest` is
materialized only when the M05 §7.3 A revalidation + M02 §10
exact-content checks all pass at the materialization moment.

A success at stage N does NOT authorize stage N+1.

### §3.3 The chain may legitimately terminate at any stage

A downstream investigation may complete with no Engine
mutation. See §7.

### §3.4 Each Engine API call is its own decision

Even if multiple Engine state-mutating public methods would
plausibly be called in sequence as a result of one
investigation, each call requires its own candidate, its own
review, its own decision record, and its own explicit
invocation.

### §3.5 Domain neutrality

M06 normative text uses only the domain-neutral vocabulary
listed in §15. Specific tool names, scanner output schemas,
vulnerability identifiers, or product-specific identifiers
are NOT load-bearing M06 terms.

---

## §4 Re-entry stage model

### §4.1 Stage 1 — Investigation initiation

```
consumer explicitly decides to initiate an investigation
```

Permitted bases for the decision:

```
- a prior operator decision record (M05 family A or B) as
  PROVENANCE for the choice to investigate
- a Gap (ragcore.Gap) as PROVENANCE for what to look for
- a Claim status / lifecycle history as PROVENANCE for which
  investigation may be useful
- consumer-side policy (e.g., maintenance schedule, escalation
  rule, manual operator request) as PROVENANCE
```

Forbidden:

```
- automatic tool execution because Gap exists
- automatic tool execution because Claim status is candidate
- automatic tool execution because operator wrote
  schedule-manual-inspection / request-evidence on a M05
  record
- treating M05 disposition records as tool execution
  authorization
```

`request-evidence` and `schedule-manual-inspection` from M05
§4.1 are dispositions, NOT permissions. The consumer separately
decides whether and how to launch an investigation.

### §4.2 Stage 2 — Downstream result trace

```
investigation output
  -> traceable external result artifact
```

The result trace is a **new external source artifact** in the
sense of PR63 (External Adapter Translation Boundary). The
trace must preserve the obligations of PR63 §3 ~ §9 unchanged:

```
- preserve source representation
- distinguish retained / normalized / derived / unresolved
- record translation decisions
- record translation loss explicitly (no hidden loss)
- preserve provenance (producer, adapter, raw-result reference,
  acquisition / run reference, revision)
- preserve unresolved ambiguity
- preserve operational failure when applicable
```

Conceptual minimum content for one downstream result trace
(field names not mandated):

```
 1. originating investigation reference
 2. originating decision reference, when applicable
 3. producer / adapter identity
 4. producer or adapter revision
 5. raw result reference
 6. result item or fragment identity
 7. acquisition / run reference
 8. retained source representation
 9. normalized content, when present
10. derived content, when present
11. translation decisions
12. translation loss
13. provenance
14. unresolved ambiguity
15. operational failure, when applicable
```

The trace itself is NOT a `ragcore.Evidence`, NOT a `Claim`,
NOT a `Gap`, NOT a `Relation`, and NOT an Engine object.

### §4.3 Stage 3 — Contextual result role assignment

```
result item or fragment
  + current interpretation context
  + provenance
  + intended use
  -> consumer-side role assignment
```

Role-assignment targets are at the **result-item / result-
fragment** level, not at the source / adapter / tool / run
level. A single investigation run that produced several
result fragments produces several independent role-assignment
decisions.

Per PR60 (Role Assignment Policy Spec), assignment considers
at least:

```
SourceType
BaseRecordType
SemanticRole
DataAccessProfile
AllowedUse
ForbiddenUse
```

Forbidden automatic mappings:

```
tool output type      -> SemanticRole
result source         -> SemanticRole
result field name     -> Evidence
retrieval method      -> truth
result ranking        -> Evidence.strength
severity label        -> Gap.severity
external status       -> Claim.status
```

`SemanticRole` continues to be a contextual interpretation
decision; M06 does NOT make it a property of the tool, the
adapter, the source, or the investigation as a whole.

### §4.4 Stage 4 — EngineInputCandidate consideration

```
admitted result role assignment
  -> consumer MAY consider materializing ONE
     non-executable EngineInputCandidate
```

Candidate materialization is **NOT automatic** and **NOT
required** even after a successful role assignment. The
consumer may legitimately decide that the role-assigned
result is sufficient for an archive / cite / observation
purpose without producing a candidate.

When materialized, the candidate must satisfy M02's §7
conceptual minimum content, plus the M06-specific extensions:

```
- candidate identity
- mutation class
- exact source-basis reference
- exact result trace or fragment reference   (M06 addition)
- role-assignment context reference          (M06 addition)
- provenance / traceability
- intended existing state-mutating Engine public method
- explicit proposed arguments
- argument translation basis                 (M06 emphasis)
- referenced Engine IDs
- expected preconditions
- expected effect
- explicit non-effects
- unresolved assumptions
- consumer policy basis
```

A candidate is non-executable in the M02 §6 sense: it is a
record of what could be invoked, not the invocation itself.

### §4.5 Stage 5 — Mutation review and M05 decision record

```
EngineInputCandidate
  -> explicit M02 §9 exact-content mutation review
  -> approved / rejected / hold disposition
  -> M05 mutation-review-family decision record
```

The M05 mutation-review-family record holds the disposition.
It does NOT itself carry invocation authority. The
proposal-gate family (M05 §4.1) cannot serve in this role at
all.

Hard locks:

```
proposal acceptance              != mutation review approval
result role assignment           != candidate approval
candidate validator pass         != mutation review approval
approved disposition record      != ReviewedMutationRequest
ReviewedMutationRequest          != Engine invocation
```

The mutation-review-family is the only M05 record family that
may participate in determining whether a separately
materialized `ReviewedMutationRequest` (Stage 5.5) remains
eligible for downstream invocation consideration. The record
itself carries no invocation authority.

### §4.5.5 Stage 5.5 — Separate `ReviewedMutationRequest` materialization

The M02 four-layer model from §4 is

```
RoleAssignment
  -> EngineInputCandidate
  -> ReviewedMutationRequest
  -> explicit invocation
```

Stage 5 produces an approved (or rejected / hold)
mutation-review-family decision record. It does NOT produce a
`ReviewedMutationRequest`. The `ReviewedMutationRequest`, when
created, is a separate consumer-side artifact under M02 §10 /
§11.

```
approved exact review
  + exact-content checks
  + EngineStateIdentity revalidation
  -> MAY permit separate ReviewedMutationRequest
     materialization under M02

ReviewedMutationRequest
  != invocation
```

Hard locks:

```
approved disposition record            != ReviewedMutationRequest
M05 mutation-review-family record      != ReviewedMutationRequest
materialized ReviewedMutationRequest   != Engine invocation
```

A `ReviewedMutationRequest` is materialized only when the
consumer has verified, immediately before materialization
(M05 §7.3 A + M02 §10 + M06 §12):

```
- exact candidate content unchanged
- reviewed method name unchanged
- reviewed exact arguments unchanged
- referenced Engine IDs unchanged
- result trace reference unchanged
- role-assignment context reference unchanged
- decision-time EngineStateIdentity equals
  Engine.state_identity() at this moment
- M02 §12.3 caller checks still pass at this moment
```

If any check fails, no `ReviewedMutationRequest` is
materialized. The consumer follows M05 §12.2: re-inspect,
reconstruct candidate if appropriate, perform a new mutation
review, create a new decision record. The cycle restarts at
Stage 5 (or earlier, at Stages 2 / 3 / 4 depending on which
input changed).

### §4.6 Stage 6 — Explicit Engine invocation

Stage 6 takes the Stage 5.5 `ReviewedMutationRequest` as
input. The only way an Engine state-mutating public method
runs is that the caller explicitly writes and invokes that
method against the current Engine.

Forbidden execution mechanisms (carried forward from M02
§12.3):

```
- getattr-based dispatch
- method-name lookup execution
- request.execute(engine)
- engine.apply_request(request)
- automatic dispatcher
- queue / worker / scheduler invocation
- stored decision auto-execution
- reflection of the candidate.intended_method string into a
  method object
```

Stage 6 carries M02's §13 call-success semantics unchanged:
the call succeeds in the sense that the existing Engine
method's existing runtime behavior was applied to the given
arguments. It does NOT prove the external result is true.

---

## §5 Investigation initiation boundary

§4.1 above is the load-bearing rule. Additional locks:

```
- the framework provides no tool runner, no network IO, no
  process orchestrator, no scheduler, and no worker pool

- a downstream investigation may use any consumer-side
  mechanism (manual inspection, command-line tool,
  long-running daemon, external service, automated pipeline,
  human review) — the choice is consumer policy

- whether an investigation is consumed in foreground,
  background, or asynchronously is consumer policy

- when an investigation completes, the consumer separately
  decides whether to enter Stage 2 with its result

- a M05 proposal-family `schedule-manual-inspection` or
  `request-evidence` disposition does NOT mean that an
  investigation has been scheduled, that any inspection
  will run, or that any tool has received execution
  authority. The seven proposal-family dispositions
  (`accept` / `reject` / `rewrite` / `request-evidence` /
  `schedule-manual-inspection` / `archive` / `cite`) per
  M05 §4.1 are sibling outcomes; they are not nested.
```

---

## §6 Downstream result trace obligations

### §6.1 Trace integrity

A trace must be:

```
- attributable to a producer (or adapter) and a revision
- attributable to an investigation run
- referenceable as a stable artifact (consumer-defined)
- self-describing about its shape (source vs normalized vs
  derived vs unresolved)
- explicit about translation losses
- explicit about provenance
```

### §6.2 Trace immutability for the prior record

A trace, once produced, is the artifact a downstream Stage 3
or Stage 4 consumer operates on. If the trace later changes:

```
- the changed trace is a NEW external source artifact
- a previously admitted role assignment cannot be reused
- any candidate built on the prior trace is no longer
  current
- a new chain begins at Stage 2
```

### §6.3 Trace is not Engine state

```
trace identity       != Engine object identity
trace producer       != Engine
trace acquisition    != Engine mutation
trace existence      != Engine truth
trace existence      != Claim status change
trace existence      != Gap resolution
trace identity       != EngineStateIdentity
trace identity       != PR51 packet capture identity
```

---

## §7 Operational failure vs semantic ambiguity

The following are distinct conditions and MUST NOT be
collapsed into a single `invalid` / `unresolved` label:

```
- tool or source read failure
- parse failure
- unsupported result shape
- translation failure
- incomplete provenance
- semantic ambiguity
- role ambiguity
```

Hard lock:

```
operational failure  != semantic ambiguity
```

Each condition carries different consumer implications:

```
operational failure
  -> the investigation did not produce a usable trace;
     the chain terminates with NO candidate, NO review,
     NO invocation; the failure is itself a traceable fact
     for the originating decision record

semantic ambiguity
  -> the trace exists; role assignment is ambiguous;
     the chain terminates at Stage 3 with ambiguity
     preserved; per §4.3 and §10, no candidate is
     materialized
```

---

## §8 External adapter translation boundary

A downstream result adapter is a consumer-side adapter under
PR63. The PR63 boundary applies in full to the result trace,
unchanged:

```
- adapter translates representation, not uncertainty into
  truth
- adapter-local mappings remain adapter-owned
- lossy transformation is explicit and traceable
- structural validity creates no Engine authority
- insufficient context preserves unresolved
- no domain defines the framework adapter boundary
```

M06 adds:

```
- a downstream result adapter is NOT a "canonical adapter".
  The framework does not declare any one adapter privileged.
- a downstream result adapter does NOT bypass Stage 3
  role assignment, Stage 4 candidate consideration, Stage 5
  review, or Stage 6 explicit invocation.
- a downstream result adapter does NOT call any Engine
  state-mutating public method.
- a downstream result adapter's output is not a `Claim`,
  not an `Evidence`, not a `Gap`, not a `Relation`, and not
  a `ReviewedMutationRequest`.
```

---

## §9 Contextual result role assignment

### §9.1 Targets

Role assignment operates on **result-level** units, not on
source-level / adapter-level / tool-level units:

```
- result record
- result field
- result fragment
- result relation
- derived fragment
```

A single investigation may produce several role-assignment
units. Each is assigned independently.

### §9.2 Inputs to one assignment

```
- the result unit's retained source representation
- the result unit's normalized / derived content, where present
- the unit's provenance
- the current interpretation context
  (NOT the producer's claimed context)
- the intended use (consumer-declared)
- applicable AllowedUse / ForbiddenUse rules
- traceability completeness
```

### §9.3 Forbidden inferences

```
tool output type            -> SemanticRole
result source               -> SemanticRole
result field name           -> Evidence
retrieval method            -> truth
result ranking              -> Evidence.strength
severity label              -> Gap.severity
external status             -> Claim.status
result similarity           -> Evidence.strength
operator-set tool category  -> SemanticRole
adapter category            -> AllowedUse
```

### §9.4 Unresolved assignment terminates the chain

When any of the following holds, Stage 3 terminates with an
explicitly unresolved assignment:

```
- interpretation context absent
- assignment target ambiguous
- provenance incomplete
- primary role unresolved
- AllowedUse / ForbiddenUse conflict
- intended use not authorized
- traceability insufficient
```

Termination is a normal consumer-side conclusion (see §10).

---

## §10 Candidate materialization admission

A consumer **MAY** materialize a candidate from a Stage 3
result + admitted role assignment.

A consumer **MUST NOT** materialize a candidate when:

```
- the role assignment is unresolved
- AllowedUse prohibits the intended Engine usage
- the trace's operational failure prevents content from being
  used as the candidate's source basis
- the trace's translation loss exceeds the candidate's
  declared argument basis (no hidden loss carried into the
  candidate)
- the intended Engine method's existing M02 §7 conceptual
  obligations cannot be filled
- the intended argument translation has no documented basis
```

A consumer **MAY** legitimately decide not to materialize a
candidate even when materialization would be permitted —
archiving or citing the result is a valid terminal state.

```
result accepted for archive / cite only
  -> no candidate
  -> no review
  -> no invocation
  -> chain complete
```

---

## §11 M02 mutation-review handoff

A candidate produced under M06 is reviewed under M02 §9
exact-content review semantics, unchanged.

M06 adds the following result-derived candidate obligations
at review time:

```
- the candidate's exact result trace reference is unchanged
  vs the trace under review
- the candidate's role-assignment context reference is
  unchanged vs the assignment under review
- the candidate's argument translation basis is documented
  and traceable to the trace + assignment
- the candidate's referenced Engine IDs exist at review time
```

The mutation-review disposition (`approved` / `rejected` /
`hold`) is recorded as an M05 mutation-review-family decision
record (M05 §4.2 / §5).

Hard locks (carried forward from M02 §24 + M05 §4.3):

```
approved disposition record  != ReviewedMutationRequest
approved disposition record  != Engine invocation
proposal accept              != mutation review approval
```

M06 does NOT introduce a separate "re-entry executor", a
separate "re-entry request type", or a separate dispatcher.
The M02 four-layer model is reused verbatim.

---

## §12 M05 decision record and state revalidation

The mutation-review record is created and persisted under M05
unchanged.

Before the consumer **materializes** a `ReviewedMutationRequest`
at Stage 5.5, AND again **at the invocation moment** at Stage 6,
the consumer must verify (M05 §12.1 + M06 §11 extension):

```
- exact candidate content unchanged                    (M02 §10)
- reviewed method name unchanged                       (M02 §10)
- reviewed exact arguments unchanged                   (M02 §10)
- referenced Engine IDs unchanged                      (M02 §10)
- result trace reference unchanged                     (M06 §11)
- role-assignment context reference unchanged          (M06 §11)
- decision-time EngineStateIdentity equals
  Engine.state_identity() at this moment               (M05 §7.3 A)
- M02 §12.3 caller checks still pass at this moment
```

The two verification moments are distinct in time. A check that
passed at Stage 5.5 materialization does NOT remain proven at
Stage 6 invocation; the consumer re-verifies (M05 §9
moment-scoped comparison).

If any of the above fails:

```
- prior approval cannot be reused
- current Engine objects are re-inspected
- exact candidate is reconstructed if still appropriate
- new mutation review is performed
- new M05 mutation-review-family decision record is
  created
```

The result trace identity is NOT a PR51 packet capture
identity. Decision-state revalidation operates on
`EngineStateIdentity` only, per M05 §7.

---

## §13 Explicit invocation boundary

Stage 6 takes the Stage 5.5 `ReviewedMutationRequest` as input.
The only Engine state-mutating event in M06's chain is at
Stage 6: a caller explicitly invokes one existing
state-mutating Engine public method (one of the 20 listed at
M02 §12.1).

Forbidden (carried forward + M06-specific):

```
- getattr-based dispatch
- method-name lookup execution
- request.execute(engine)
- engine.apply_request(request)
- automatic dispatcher
- queue / worker / scheduler invocation
- stored decision auto-execution
- reflection of candidate.intended_method into a method
  object
- chaining one Stage 6 invocation into a subsequent Stage 6
  invocation without a new candidate / review / decision /
  revalidation cycle
- treating a successful Stage 6 invocation as authorization
  for further Stage 6 invocations
```

Call success semantics from M02 §13 are unchanged: the call
proves the Engine accepted the supplied arguments and applied
that method's existing runtime behavior. It does NOT prove
the external result is true.

---

## §14 Lifecycle / Gap / contradiction separation

`add_evidence` is one M02 candidate target; `confirm_claim_if
_ready` / `refute_claim_if_ready` / `dispute_claim_if_ready`
/ `resolve_gaps_for_evidence` / `register_contradiction` /
`register_contradiction_resolution` are separate M02
candidate targets.

```
add_evidence success
  != Claim confirmed
  != Claim refuted
  != Claim disputed
  != Gap automatically resolved
  != contradiction automatically resolved
```

M06 explicitly forbids chaining these in one automatic
pipeline. Each transition requires its own:

```
- candidate
- exact-content review
- M05 mutation-review-family decision record
- decision-state revalidation
- explicit invocation
```

In particular, the pattern

```
downstream result
  -> add_evidence
  -> confirm_claim_if_ready
```

as a single automatic pipeline is FORBIDDEN. The consumer
must produce, review, decide, revalidate, and invoke each
step separately.

The 6 lifecycle `*_if_ready` methods continue to evaluate
their existing pre-conditions; M06 does NOT relax any
condition.

---

## §15 RuleStats separation

M06 does NOT introduce automatic `update_rule_stats` calls in
response to:

```
- a downstream result being produced
- a Claim being confirmed / refuted / disputed
- an Evidence being registered
- a Gap being resolved
- a contradiction being resolved
- an investigation succeeding or failing
- an operator disposition being recorded
```

`update_rule_stats` remains one of the 20 M02 candidate
targets. Whether and when to invoke it is a separate
candidate / review / decision-record cycle. RuleStats
provenance semantics are M09 (PR78) territory; M06 does NOT
pre-define them.

---

## §16 Multiple results / aggregation / duplicate policy

A single investigation may produce 0, 1, or N result fragments
or records.

### §16.1 Boundary preservation

```
- each source / result boundary is preserved
- aggregation MUST NOT erase provenance
- multiple results MUST NOT be auto-merged into one Evidence
- "looks-like-the-same-result" is NOT a basis for automatic
  deduplication
- one role assignment MUST NOT be inherited by all results
  in the same run
- one candidate review MUST NOT approve multiple Engine
  invocations
```

### §16.2 Per-fragment continuation

Each fragment may produce:

```
- zero candidates                (terminate at Stage 3 or §10)
- one candidate                  (Stage 4 once, Stage 5 once,
                                   Stage 6 once)
- multiple separately-reviewed
  candidates                     (Stage 4 / 5 / 6 once each)
```

### §16.3 Operational and semantic dedup

A consumer-side adapter MAY apply operational dedup (e.g.,
same exact serialized fragment received twice) — that is
adapter-internal policy. Operational dedup MUST NOT silently
drop fragments that differ in provenance, retained source
content, normalized content, or interpretation context.

### §16.4 Semantic dedup forbidden by default

Treating two fragments as "the same finding" because they
share a label, severity, source pointer, or normalized
field value is NOT M06 dedup; it is a Stage 3 + Stage 4
consumer judgment that requires explicit role assignment
and candidate materialization for the resulting consolidated
claim, if any.

---

## §17 Process restart and restore

A persisted result trace, a persisted role-assignment record,
and a persisted M05 decision record may all carry their
historical `EngineStateIdentity` pair. After process restart
or `Engine.from_snapshot(...)`:

```
current Engine receives a FRESH engine_token         (M04 §4.5)
current Engine starts at revision = 0                (M04 §4.4)
recorded_engine_token != current_engine_token        -> M05 §7.3 C
```

Therefore:

```
- prior approval cannot be mechanically reused
- revision values MUST NOT be ordered across lineages
- equivalent snapshot content does NOT restore
  comparability
- a new mutation review cycle is required
```

The result trace itself may continue to be available as a
historical artifact, but the chain that would have led to a
mutation must start a new candidate / review / decision /
revalidation / invocation cycle.

Persistence vocabulary:

```
persistent result trace
  != persistent Engine runtime lineage

persistent decision record
  != persistent Engine runtime lineage

persistent role assignment
  != persistent Engine runtime lineage
```

---

## §18 Relationship to earlier contracts and M-series

### §18.1 PR63 (External Adapter Translation Boundary)

Preserved. A result adapter is one external adapter under
PR63. M06 §32 addendum (in the PR63 spec) restates the lock.
PR59 (Data Access Profile Contract) axes are reused unchanged
through PR60 / PR63; PR59 itself is not modified by M06.

### §18.2 PR60 (Role Assignment Policy)

Preserved. Result-level role assignment uses PR60's
`SourceType` / `BaseRecordType` / `SemanticRole` /
`DataAccessProfile` / `AllowedUse` / `ForbiddenUse` axes
unchanged. M06 §25 addendum (in the PR60 spec) restates
target granularity (result record / field / fragment).
PR61 (Minimal Consumer-Side Role Assignment Example) is
unchanged.

### §18.3 PR57 / M05 (Operator Decision Records)

Preserved. M05 mutation-review-family records continue to be
the consumer-side persistence layer for Stage 5
dispositions. M06 §21 addendum restates that proposal-family
dispositions do not authorize tool execution or Engine
invocation.

### §18.4 M02 (Reviewed Engine Mutation Handoff)

Preserved verbatim. Result-derived candidates use the same
four-layer model, the same §7 conceptual obligations, the
same §10 / §11 exact-content review binding, the same §12
explicit invocation, and the same §12.3 forbidden mechanisms.
M06 §25 addendum restates that no separate re-entry executor
is introduced.

### §18.5 M03 (Engine Read Consistency)

Preserved verbatim. The result trace is NOT a packet capture
identity; re-entry does NOT lift packets out of
`UNBOUND + UNKNOWN`; M03 §7 forbidden two-axis combinations
remain forbidden.

### §18.6 M04 (Engine State Identity Primitive)

Used unchanged at Stage 5 / Stage 6 revalidation. M06 does
NOT modify the M04 public contract, the advance discipline,
or the snapshot exclusion.

### §18.7 M-series responsibility map (M01-locked)

```
PR74-M05  Operator Decision Record / stale revalidation  (OC-B)  CLOSED
PR75-M06  Downstream Result Re-entry                     (OC-E)  this PR
PR76-M07  Effective Confidence Calculation Trace         (OC-D)  NOT STARTED
PR77-M08  Complete Domain-Neutral Reference Operation    (OC-F)  NOT STARTED
PR78-M09  RuleStats Update Provenance                    (OC-G)  NOT STARTED
```

M06 does NOT redefine, expand, or auto-schedule M07 / M08 /
M09. In particular:

```
- a complete domain-neutral end-to-end reference operation
  is M08 territory and is NOT in M06's scope
- effective-confidence trace is M07 territory; M06 does NOT
  modify the §52 / §53 / §54 confidence semantics
- RuleStats provenance is M09 territory; M06 does NOT
  introduce automatic update_rule_stats
```

---

## §19 Files locked, invariants, and non-goals

### §19.1 Files locked

PR75-M06 must not modify any of:

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
tests/test_minimal_operational_scaffold.py
M01 historical body text
M02 §1 ~ §22 historical body
M03 §1 ~ §18 historical body
M04 §1 ~ §10 historical body
M05 §1 ~ §20 historical body
PR57 §1 ~ §18 historical body
PR59 historical body (Data Access Profile Contract)
PR60 §1 ~ §24 historical body
PR61 historical body (Minimal Consumer-Side Role
                       Assignment Example)
PR63 §1 ~ §31 historical body
M02 §23 / §24 historical addenda
M03 §19 / §20 historical addenda
M04 §11 historical addendum
```

M01's C2 ~ C7 statuses are historical scaffold observations.
M06 closes the conceptual boundary; it does NOT rewrite the
M01 scaffold report or its `TODO` / `UNDEFINED` / `BLOCKED`
statuses to reflect M06's closure.

### §19.2 Invariants (delta = 0)

```
Engine public methods            41   (unchanged from main 80759048)
Engine private methods           19   (unchanged)
state-mutating public methods    20   (unchanged set)
read-only public methods         19   (unchanged set)
serialization boundary            2   (unchanged set)
ragcore.__all__                  49   (unchanged)
snapshot schema_version           2   (unchanged)
snapshot top-level keys          18   (unchanged set)
PR51 packet keys                  7   (unchanged set, same order)
tests                          1517   (unchanged; M06 adds 0 tests)
```

Behavioral invariants:

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

### §19.3 Non-goals

PR75-M06 deliberately does NOT define:

```
- any Python class, dataclass, TypedDict, NamedTuple, Pydantic
  model, or Protocol
- any ragcore symbol, Engine method, or snapshot field
- any database table, JSON schema, file format, or wire format
  for result traces or candidates
- a tool runner / network IO / orchestrator
- a canonical result-adapter
- an investigation launcher
- an automatic role-assignment executor
- an automatic candidate materializer
- an automatic review executor
- an automatic decision-record executor
- an automatic invocation dispatcher
- a packet-binding helper / CURRENTLY_MATCHED helper /
  STALE detector
- an automatic RuleStats updater
- M07 effective-confidence trace
- M08 complete domain-neutral reference operation
- M09 RuleStats provenance
```

---

## §20 Forbidden conclusions (anti-pattern lock)

The contract is normative against every conclusion in this
list. Consumer documentation, dev records, and adapter code
must avoid asserting any of them.

```
request-evidence == tool execution authority
schedule-manual-inspection == automatic tool execution
investigation success == result truth
external result == ragcore.Evidence
tool output == Evidence
result score == Evidence.strength
external probability == base_confidence
severity label == Gap.severity
external status == Claim.status
result role assignment == mutation approval
valid role assignment == candidate required
candidate == accepted mutation
approved disposition == ReviewedMutationRequest
ReviewedMutationRequest == invocation
operator proposal acceptance == mutation review approval
add_evidence == lifecycle transition
Evidence registration == Claim confirmation
downstream result == automatic Gap resolution
downstream result == automatic contradiction resolution
downstream result == automatic RuleStats update
result trace == PR51 capture identity
re-entry packet == CAPTURE_BOUND
re-entry packet == CURRENTLY_MATCHED
re-entry packet == STALE
persistent result trace == persistent Engine lineage
```

---

## §21 Consumer implementation freedom

A consumer-side adapter chain may choose:

```
- the storage substrate for traces, role assignments,
  candidates, and decision records
- the serialization format
- the identifier scheme for trace / fragment / candidate ids
- the actor identity scheme
- the timestamp scheme (per M05 §19)
- the content-equivalence mechanism (per M05 §19)
- the supersession-link representation
- the retention and deletion policy
- the orchestrator / scheduler / worker shape
- whether the chain runs foreground / background / async
- whether multiple chains run concurrently (subject to M03
  single-thread-per-Engine §7)
- the operator / review UI
```

Provided that:

```
- §4 stage separation is preserved
- §6 trace integrity is preserved
- §7 operational vs semantic distinction is preserved
- §9 role-assignment locks are preserved
- §10 candidate admission is preserved
- §11 / §12 review + revalidation cycle is preserved
- §13 explicit invocation is preserved
- §14 lifecycle / Gap / contradiction separation is preserved
- §15 RuleStats separation is preserved
- §16 multi-result discipline is preserved
- §17 process-restart discipline is preserved
- §20 forbidden conclusions are not asserted
```

---

## §22 Closing position

```
M06 closes the conceptual boundary for OC-E at the layer
where it actually lives: the consumer-side chain that
re-translates a downstream result into a NEW external source
artifact, contextually role-assigns each result item,
considers materializing a NON-EXECUTABLE candidate, runs an
M02 exact-content mutation review, persists the disposition
as an M05 mutation-review-family record, revalidates the
decision-time identity against the current Engine identity,
and explicitly invokes one existing state-mutating Engine
public method.

It does NOT introduce a tool runner, an investigation
launcher, an adapter executor, a role-assignment executor, a
candidate materializer, a review executor, a decision-record
executor, a dispatcher, a packet binding, a stale detector,
an automatic RuleStats update, or any lifecycle chaining.

M06 does NOT close OC-D (M07), OC-F (M08), or OC-G (M09).
A complete domain-neutral end-to-end reference operation
remains M08 territory and is NOT in scope here.
```

PR75-M06 is opened as **Draft** and is not merged. Closure
language (`CLOSED`) is reserved for the post-squash-merge
state. The M-series sequence after PR75-M06:

```
PR75-M06   Downstream Result Re-entry
                                       (OC-E) OPEN — DRAFT,
                                              NOT MERGED
PR76-M07   Effective Confidence Trace  (OC-D) NOT STARTED
PR77-M08   Complete Domain-Neutral
           Reference Operation         (OC-F) NOT STARTED
PR78-M09   RuleStats Update Provenance (OC-G) NOT STARTED
```

No automatic next PR. Framework waits for directive.
