# Operator Decision Boundary Spec

Status: spec document (PR57)
Baseline: main `3661c59` (PR56 merged)
Type: doc-only architecture spec; no source change, no test change, no public symbol change

## 0. Scope limitation (locked, user 2026-05-25)

```text
PR57 defines what operator acceptance means after PR55 / PR56
validators pass.

It does NOT implement an operator UI, an approval mechanism,
a workflow engine, a Cerberus-specific pipeline, or a ragcore
extension.

It does NOT auto-schedule PR58 / PR59 or any consumer-side
adapter.
```

한국어:

```text
PR57 은 PR55 / PR56 validator 가 통과한 뒤 operator acceptance 가
무엇을 의미하는지 문서로 잠그는 spec 이다.

operator UI / 승인 mechanism / workflow engine / Cerberus
pipeline / ragcore 확장 — 모두 구현하지 않는다.
```

PR57 closes the last conceptual gap in the PR49 ~ PR56 stack: the meaning of "operator acceptance" once both validators (PR55 shape + PR56 safety) return `[]`. It documents what the operator can and cannot do from that point on; it does NOT add code.

---

## 1. Purpose

```text
After PR49 ~ PR56, the framework has:
  - a policy for what can be read from the Engine                  (PR49)
  - an audit of what is already readable                           (PR50)
  - an executable read wrapper                                      (PR51)
  - a consumer-side packet consumption spec                         (PR52)
  - a consumer-side packet validator                                (PR53)
  - a proposal layer bridge spec                                    (PR54)
  - a consumer-side proposal shape validator                        (PR55)
  - a consumer-side proposal safety validator                       (PR56)

What remained undefined:
  - what does it mean when both validators return [] ?
  - what is the operator allowed to do with that proposal ?
  - what is the operator NOT allowed to do ?
  - where does the operator decision sit relative to Engine state ?

PR57 defines those boundaries as written spec.
It does NOT add any code.
```

The purpose of PR57 is to name and locate operator decisions so that no future PR treats a validator-passed proposal as an automatic license to mutate the Engine, execute a tool, or publish a final verdict.

---

## 2. Baseline

```text
main:    3661c59 (PR56 merged)
tests:   1183 passing
ragcore.__all__:            48 symbols
Engine public methods:      40
snapshot schema_version:    2
snapshot top-level keys:    18

Reference documents this spec inherits from:
  docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md       (PR49)
  docs/architecture/ENGINE_READ_SURFACE_AUDIT.md              (PR50)
  docs/architecture/LLM_CONTEXT_PACKET_SPEC.md                (PR52)
  docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md             (PR54)
  examples/inspector/engine_inspector.py                     (PR51)
  examples/inspector/packet_validator.py                     (PR53)
  examples/proposal/proposal_schema.py                       (PR55)
  examples/proposal/proposal_validator.py                    (PR56)
  docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md            (PR44-D)
  direction_rag_framework_proposal_layer                      (memory)
```

---

## 3. Core boundary statement

```text
Operator acceptance is a gate, not Engine truth.

operator 의 수락은 게이트이지, Engine 의 진실이 아니다.
```

This is the single sentence that governs every per-layer rule in this spec. Every other section (§4 ~ §17) must be readable as an expression of this sentence.

Supporting locks (all of these must hold):

```text
validators pass            ≠   accepted
accepted                    ≠   Engine state mutation
accepted                    ≠   tool execution
accepted                    ≠   final report verdict
operator decision           =   gating event for downstream layers
operator decision           ∉   Engine state graph
                                 (it is a consumer-side event)
```

---

## 4. Position in the PR49 ~ PR56 flow

```text
Engine
  ↓ read-only public methods
external inspector                                              (PR51)
  ↓ 7-key packet
packet validator                                                (PR53)
  ↓ validated packet
LLM proposal draft
  ↓
proposal shape validator                                        (PR55)
  ↓ shape-pass
proposal safety validator                                       (PR56)
  ↓ safety-pass
operator review                              ←── PR57 spec area (this doc)
  ↓
operator decision (accept / reject / rewrite / request-evidence /
                    schedule-manual-inspection / archive / cite)
  ↓
[any downstream layer]                       ←── OUT OF PR57 SCOPE
  (tool execution gate / consumer task tracker /
   audit log / dashboard / report system —
   all are consumer-side concerns)
```

PR57 owns the transition from "both validators returned `[]`" to "an operator now reviews this proposal" and the subsequent gating event.

PR57 does NOT own:

```text
- the operator UI itself
- the operator authentication / authorization mechanism
- the consumer task tracker
- the audit log shape
- the dashboard rendering
- the report system
- the downstream tool execution gate
```

Those are consumer-side concerns and are intentionally left undefined here so that consumers can pick their own implementation while honoring PR57 boundaries.

---

## 5. Validator pass is NOT acceptance

```text
A proposal is "validator-passed" iff:

  validate_llm_proposal_shape(proposal, source_packet)  ==  []
  validate_proposal_safety(proposal, source_packet)     ==  []

This state means:

  - the proposal's top-level shape conforms to PR55 minimal shape
  - the proposal's nested structure contains no forbidden semantic
    identifier per PR56

It does NOT mean:

  - the proposal is correct
  - the claim referenced is true / verified / refuted
  - the suggested next inspection is the right one
  - any downstream layer is authorized to act
  - the operator has read or approved it

Validator-passed is a *necessary* precondition for operator
review, not a sufficient one. An operator may still reject a
validator-passed proposal for any consumer-side reason
(domain context, scope, freshness, cost, redundancy, etc.).
```

---

## 6. Operator acceptance IS a gate

```text
"Operator acceptance" means:

  the consumer-side operator has read a validator-passed
  proposal and explicitly signaled "this candidate may move
  forward to the next consumer-side layer."

It is a gating event:

  - it unlocks downstream consumer-side processes
    (e.g., create-task / schedule-inspection / draft-report-note)
  - it does NOT itself perform those downstream processes
  - it does NOT modify Engine state
  - it does NOT execute tools
  - it does NOT publish a final verdict
  - it does NOT confirm or refute any Claim

"Operator acceptance" is recorded on the consumer side as a
consumer-side event (e.g., dashboard log, ticket comment, audit
trail entry). The Engine itself does not know about operator
acceptance and does not need to.
```

---

## 7. What an operator CAN do

After both validators return `[]`, the operator MAY (consumer-side):

```text
1. Accept the proposal for further review or downstream gating.
2. Reject the proposal for any consumer-side reason.
3. Rewrite the proposal into a safer or clearer consumer-side
   note (the rewrite remains a proposal until both validators
   are re-run on it).
4. Request more evidence
   (the request itself does NOT mutate Engine; the consumer
    must gather evidence by separate means and feed it through
    the normal add_evidence path).
5. Schedule a manual inspection
   (creates a consumer-side task; does NOT invoke Engine).
6. Create a consumer-side task referencing this proposal.
7. Archive the proposal as a consumer-side audit record.
8. Cite the proposal in a consumer-side dashboard EXPLICITLY as
   "a proposal" and NEVER as "Engine truth" or "verified fact".
```

In all of the above, the proposal remains a suggestion. Acceptance is a workflow gate, not a truth assertion.

---

## 8. What an operator CANNOT do

After both validators return `[]`, the operator MUST NOT (regardless of any consumer-side workflow):

```text
1. Bypass PR55 / PR56 validator failures.
   (If a validator returned a violation, that violation must be
    addressed before any operator review begins.)

2. Mutate Engine state from a proposal alone.
   (Engine state mutation must go through the normal Engine
    public API path: add_evidence / add_claim / add_gap /
    register_contradiction / *_if_ready lifecycle helpers.
    A proposal acceptance is NOT a substitute for any of those.)

3. Mark a Claim true / false / refuted / confirmed from a
   proposal alone.
   (Claim status transitions must come from
    confirm_claim_if_ready / refute_claim_if_ready /
    dispute_claim_if_ready / refute_disputed_claim_if_ready /
    refute_disputed_claim_if_ready_by_freshness /
    resolve_disputed_claim_if_ready, each driven by registered
    evidence and lifecycle conditions — not by operator clicks.)

4. Execute tools without a separate safety gate.
   (Tool execution belongs to a downstream layer that PR57 does
    not define. That layer must have its own authorization,
    scope, and audit. A validator-passed proposal is NOT a
    tool-execution license.)

5. Publish a final report verdict from a proposal alone.
   (Final reports are consumer-side artifacts that go through
    their own publication workflow. A proposal is at most an
    input to a draft.)

6. Auto-trigger a downstream Cerberus / domain-specific pipeline
   from proposal acceptance.
   (Even if the consumer wires acceptance to a downstream
    pipeline, that wiring must be an explicit consumer-side
    decision documented separately, NOT an implicit consequence
    of operator acceptance.)

7. Re-classify a Claim's status through proposal acceptance.
   (Operator acceptance writes a consumer-side acceptance record;
    it does NOT call any Engine method. To change Claim status,
    the consumer must run the normal Engine lifecycle flow.)
```

These prohibitions are non-negotiable. They preserve the separation between Engine judgment (which lives inside ragcore) and consumer-side decisions (which live everywhere else).

---

## 9. Relationship to Engine state

```text
Engine state is mutated ONLY through the 40 public Engine methods.

The complete list of mutation entry points:
  add_entity                                  identity mutation
  add_observation                              identity mutation
  add_relation                                 identity mutation
  add_claim                                    claim creation
  add_evidence                                 evidence creation
  add_gap                                      gap creation
  register_contradiction                       contradiction registration
  register_contradiction_resolution            contradiction resolution
  resolve_gaps_for_evidence                    gap auto-resolution
  confirm_claim_if_ready                       lifecycle transition
  dispute_claim_if_ready                       lifecycle transition
  refute_claim_if_ready                        lifecycle transition
  resolve_disputed_claim_if_ready              lifecycle transition
  refute_disputed_claim_if_ready               lifecycle transition
  refute_disputed_claim_if_ready_by_freshness  lifecycle transition
  register_rule                                rule registration
  update_rule_stats                            rule stats mutation
  register_hint_evidence_types                 hint registration
  unregister_hint_evidence_types               hint deregistration
  clear_hint_evidence_types                    hint clear
  from_snapshot (classmethod)                  state restoration

Operator acceptance is NOT in this list. It is a consumer-side
event that may TRIGGER a downstream layer to call one of these
methods — but the call is made by that layer, with its own
arguments and its own evidence, NOT directly by acceptance.

In particular:

  operator accepted proposal P referencing claim C
    ≠  confirm_claim_if_ready(C)
    ≠  refute_claim_if_ready(C)
    ≠  dispute_claim_if_ready(C)
    ≠  any Engine lifecycle transition on C
    ≠  any add_evidence / add_gap on C

Engine truth flows from evidence + rules + lifecycle conditions.
Operator acceptance is a separate signal that lives entirely
outside the Engine.
```

---

## 10. Relationship to PR55 / PR56 validators

```text
PR55  validate_llm_proposal_shape    →  shape boundary
PR56  validate_proposal_safety        →  safety boundary
PR57  operator decision               →  acceptance boundary

These three boundaries are sequential:

  proposal draft
    → PR55 shape boundary  (must pass)
    → PR56 safety boundary (must pass)
    → PR57 operator gate    (must be granted)
    → downstream layer      (must have its own gate)

Each boundary is independent. The earlier ones do NOT bless the
later ones, and the later ones do NOT bypass the earlier ones.

If any boundary fails:
  - PR55 fail → proposal is not even safety-checked
  - PR56 fail → proposal is not presented to operator
  - PR57 reject → no downstream layer is invoked

If all three pass:
  - the proposal becomes one input to a downstream consumer-side
    layer. That layer has its own boundaries and its own gates.
```

PR57 explicitly does NOT define the downstream layer's gates. Those are out of scope.

---

## 11. Consumer-side audit record boundary

```text
Operator acceptance, rejection, rewrite, request-for-evidence,
schedule-manual-inspection, archival, and citation MAY be
recorded on the consumer side as audit events.

The audit record is a CONSUMER-SIDE artifact. It is NOT a
ragcore type. It is NOT stored in the Engine. It is NOT
returned by any ragcore public method.

A reasonable audit record might capture:

  - proposal id (consumer-assigned opaque id)
  - PR55 validator result (the list, including [] for pass)
  - PR56 validator result (the list, including [] for pass)
  - operator id (consumer-assigned opaque id)
  - operator decision (accept / reject / rewrite /
                        request-evidence / schedule-inspection /
                        archive / cite)
  - timestamp
  - free-form operator note

But the exact shape of this record is consumer's choice. PR57
does not freeze it.

What PR57 forbids in audit records:

  - claiming the proposal is "true" / "verified" / "refuted"
  - claiming Engine state was changed by acceptance alone
  - claiming the proposal authorized execution
  - claiming the proposal generated a final report
```

---

## 12. Downstream tool execution boundary

```text
Tool execution belongs to a downstream layer that PR57 does NOT
define. That layer MUST:

  - have its own authorization gate
  - have its own scope check
  - have its own audit
  - have its own rate-limit / safety mechanism (timeouts,
    blast-radius limits, dry-run mode, etc.)
  - NOT treat a validator-passed proposal as a tool-execution
    license
  - NOT treat operator acceptance as a tool-execution license
  - NOT bypass any PR55 / PR56 / PR57 boundary

The chain is:

  proposal validator-pass
    → operator review
    → operator acceptance (workflow gate)
    → downstream tool-execution layer (own gates)
    → optional tool run
    → tool output captured as raw_ref (consumer-side store)
    → optional add_evidence (normal Engine path)

Each "→" is a separate authorization point. PR57 only owns the
"operator acceptance" step. Everything before and after is
either earlier-stack (PR49 ~ PR56) or downstream (out of scope).
```

---

## 13. Ragcore symbol boundary

```text
"Operator decision" / "operator acceptance" / "operator review"
are CONSUMER-SIDE concepts.

They are NOT ragcore symbols.

The following names MUST NOT appear in ragcore source as a
class / dataclass / TypedDict / type alias:

  OperatorDecision
  OperatorReview
  OperatorApproval
  OperatorAction
  OperatorTask
  OperatorEvent
  OperatorAuditRecord

The following names MUST NOT appear in ragcore.__all__:

  any operator-* symbol
  any approval-* symbol
  any acceptance-* symbol
  any gate-* symbol

If a future PR proposes any operator-related ragcore type,
that PR must:

  - first revoke this section's lock with explicit user
    authorization
  - additionally satisfy PR50 §8.3 conditions (α/β/γ/δ/ε)
  - honor PR44-D AP-X-7 (no adapter-specific symbol promotion)
  - honor PR44-D AP-X-6 (no domain vocabulary intrusion)
  - honor PR49 §8 PR51 Guard (a) / (b) / (c)
```

This section mirrors PR52 §8 (LLMContextPacket) and PR54 §8 (LLMProposal): operator-related concepts stay outside ragcore by default.

---

## 14. PR58 Usage Playbook handoff

```text
PR58 may define a consumer-side usage playbook for invoking
PR55 + PR56 validators and presenting their output to operators,
only if ALL of the following hold:

1. PR58 treats validator pass as REVIEWABLE, not ACCEPTED.
   (A clear distinction between "can be shown to an operator"
    and "has been accepted by an operator.")

2. PR58 keeps operator acceptance OUTSIDE ragcore.
   (No operator-* symbol added to ragcore.__all__ or ragcore
    source.)

3. PR58 does NOT add Engine behavior.

4. PR58 does NOT define a Cerberus-specific workflow inside the
   framework.

5. PR58 does NOT turn a proposal into an execution command.

PR58 must additionally honor:
  - PR47 §3 / PR49 §5 / PR52 §5 / PR52 §8 / PR54 §10 / PR54 §12
  - PR55 / PR56 validator separation
  - This spec's §7 / §8 (operator can / cannot)
  - This spec's §13 (ragcore symbol boundary)

PR58 is NOT auto-entered. User decides.
```

---

## 15. PR59 Violation Collector handoff

```text
PR59 may define a small helper that combines PR55 + PR56 outputs
into a single violations list, only if ALL of the following hold:

1. PR59 is named for VIOLATION COLLECTION, not approval.
   Safe names:
     collect_proposal_violations
     gather_proposal_violations
     join_proposal_violations
   Forbidden names:
     approve_proposal
     authorize_proposal
     validate_and_accept_proposal
     accept_proposal
     finalize_proposal

2. PR59 preserves PR55 / PR56 separate meanings.
   (Each violation in the combined list retains its origin
    validator's code and message format.)

3. PR59 does NOT authorize proposal acceptance.
   (Return type stays list[tuple[str, str]];
    no "accepted: bool" field;
    no "passed: bool" field;
    no auto-pipe to downstream.)

4. PR59 does NOT execute tools.

5. PR59 does NOT mutate Engine state.

PR59 must additionally honor:
  - PR47 §3 / PR49 §5 / PR52 §5 / PR52 §8 / PR54 §10 / PR54 §12
  - PR55 / PR56 validator outputs as inputs only
  - PR55 / PR56 ragcore-free invariant

PR59 is NOT auto-entered. User decides.
```

---

## 16. Cerberus adapter handoff

```text
A Cerberus adapter may map this PR49 ~ PR57 stack into a real
domain workflow, only if ALL of the following hold:

1. The adapter lives OUTSIDE the intelligent-rag-framework repo
   (a separate Cerberus repo, or a separate consumer example
    if and only if it remains domain-neutral in name).

2. The adapter does NOT add Cerberus-specific types to ragcore.

3. The adapter treats every proposal as an OPERATOR-REVIEW
   CANDIDATE, NOT as an Engine truth or as a tool-execution
   license.

4. The adapter uses SEPARATE safety gates for tool execution.
   (Tool runs require their own authorization, scope check,
    audit, dry-run mode, blast-radius limits, etc., wholly
    independent of operator acceptance of a proposal.)

5. The adapter does NOT map operator acceptance directly to
   Engine truth.
   (Acceptance triggers downstream layers; those layers, if
    they invoke Engine, do so via the normal 40-method public
    API with their own evidence and lifecycle conditions.)

6. The adapter must honor all of:
   - PR44-D AP-X-6 (no domain vocabulary intrusion)
   - PR44-D AP-X-7 (no adapter-specific symbol promotion)
   - PR52 §8 (LLM Context Packet boundary)
   - PR54 §8 (LLM Proposal boundary)
   - This spec's §7 / §8 / §9 / §11 / §12 / §13

A Cerberus adapter is NOT auto-entered from PR57. It is a
separate user decision, taken in a separate repo or workspace.
```

---

## 17. Non-goals

PR57 does NOT do any of the following. Each is an explicit OOS lock.

```text
- modify ragcore source
- add any ragcore public symbol
- add OperatorDecision / OperatorReview / OperatorApproval /
  OperatorAction / OperatorTask / OperatorEvent /
  OperatorAuditRecord as a ragcore type
- add any test
- add any code (no helper, no schema, no validator, no UI stub)
- modify PR51 wrapper / PR53 validator / PR55 validator /
  PR56 validator
- modify PR52 spec / PR54 spec
- modify any other architecture / guide / contract document
- define an operator UI / approval mechanism / workflow engine
- specify operator authentication / authorization
- specify operator audit log shape
  (consumer's choice; §11 only lists what is and is not allowed)
- specify dashboard rendering or report layer
- expand into RAG Context Builder
- expand into Tool Plan Validator
- expand into Adapter Translation Policy
- expand into Engine Call Plan
- expand into Report Wording Guard
- expand into a Cerberus-specific implementation
- authorize tool execution
- mutate Engine state in any documented flow
- reinterpret effective_confidence as truth probability
- produce a final report verdict
- auto-schedule PR58 / PR59 or any later PR
- introduce contract §51
- introduce domain vocabulary
  (cerberus / vulnerability / scanner / exploit / ssh / cve /
   nmap / host / port / service / asset — all forbidden in
   this spec body)
```

---

## 18. Exit criteria

PR57 closes when ALL of the following hold:

```text
[ ] docs/architecture/OPERATOR_DECISION_BOUNDARY_SPEC.md added
[ ] pytest 1183 passing (unchanged from PR56 baseline)
[ ] ragcore.__all__ 48 symbols (unchanged)
[ ] Engine public methods 40 (unchanged)
[ ] snapshot schema_version 2 (unchanged)
[ ] snapshot top-level keys 18 (unchanged)
[ ] ragcore source change 0 bytes
[ ] test change 0
[ ] new public symbol 0
[ ] new engine behavior 0
[ ] contract §51 not added
[ ] PR51 wrapper unchanged
[ ] PR53 validator unchanged
[ ] PR55 validator unchanged
[ ] PR56 validator unchanged
[ ] PR52 spec unchanged
[ ] PR54 spec unchanged
[ ] no operator-related code introduced
[ ] PR58 handoff boundary defined (§14)
[ ] PR59 handoff boundary defined (§15)
[ ] Cerberus adapter handoff boundary defined (§16)
[ ] PR58 / PR59 / Cerberus adapter NOT auto-entered
[ ] ragcore symbol boundary mirror (PR52 §8 / PR54 §8) preserved
```

PR57 's job is to define operator-decision boundaries and to write the §14 / §15 / §16 handoff checklists. It does not perform any implementation, schema freeze, or downstream-layer wiring.

---

## Closing meaning

```text
PR57 closes the operator decision boundary.

The operator's role in the PR49 ~ PR57 stack is now written:
  the operator REVIEWS a validator-passed proposal,
  the operator's ACCEPTANCE is a workflow gate,
  the operator's DECISION is a consumer-side event,
  the Engine itself remains untouched by acceptance.

A proposal becoming an action requires more than acceptance —
it requires whatever downstream gates the consumer-side adapter
chooses to define.
```

Locked closing sentences:

```text
Operator acceptance is a gate, not Engine truth.

validators pass ≠ accepted.
accepted ≠ Engine state mutation.
operator decision is the gating event for downstream layers.
operator decision lives outside the Engine.

OperatorDecision / OperatorReview / OperatorApproval /
OperatorAction / OperatorTask / OperatorEvent /
OperatorAuditRecord remain NOT ragcore symbols.

PR58 / PR59 / Cerberus adapter NOT automatically entered.
```

---

## 19. Post-M05 addendum (PR74-M05, 2026-06-19)

PR74-M05 (`OPERATOR_DECISION_RECORD_REVALIDATION_CONTRACT.md`)
adds **consumer-side persistence and reuse obligations** for
operator decisions.

```
- M05 defines a conceptual record shape that preserves the
  proposal-gate disposition, the exact decision subject content
  reference, the decision-time EngineStateIdentity, and a
  family identifier.
- M05 keeps the PR57 ragcore-symbol lock: none of
  OperatorDecision / OperatorReview / OperatorApproval /
  OperatorAction / OperatorTask / OperatorEvent /
  OperatorAuditRecord becomes a ragcore symbol under M05.
- M05 keeps `operator acceptance is a gate, not Engine truth`
  intact. A persisted accept record is not an Engine mutation,
  not a ReviewedMutationRequest, and not a downstream execution
  license.
- M05 adds decision-state revalidation policy (M05 §7) for
  proposal-family records: when the recorded
  EngineStateIdentity no longer equals
  Engine.state_identity() at the reuse moment, the prior accept
  record cannot be reused, the proposal is reconsidered against
  current consumer inputs, PR55 and PR56 are rerun, and a new
  operator decision record is required (M05 §11.1).
- M05 keeps PR57 historical scope intact: §1 ~ §18 and the
  Closing meaning section are not rewritten by M05.
```

M05 does **not** modify the PR57 §13 ragcore-symbol lock, the
PR57 §10 PR55 / PR56 boundary, or the PR57 §12 downstream
execution boundary.
