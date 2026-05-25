# Proposal Layer Bridge Spec

Status: spec document (PR54)
Baseline: main `e4aad04` (PR53 merged)
Type: doc-only architecture spec; no source change, no test change, no public symbol change

## 0. Scope limitation (locked, user 2026-05-25)

```text
PR54 is a doc-only spec for the proposal layer bridge.

It defines where an LLM proposal sits between the validated
packet (PR53 output domain) and a human / operator decision.

It does NOT implement a proposal schema, a proposal validator,
a tool plan, an adapter call, a report template, or a ragcore
extension.
```

한국어:

```text
PR54 는 proposal layer bridge 의 doc-only spec 이다.

validated packet (PR53 output 영역) 과 human / operator
decision 사이에 LLM proposal 이 어디에 위치하는지 정의한다.

proposal schema / proposal validator / tool plan / adapter call
/ report template / ragcore 확장 — 모두 구현하지 않는다.
```

PR54 closes the conceptual gap between PR53 (consumer-side packet validator) and any future proposal-related work. It is the fifth doc-only spec on top of the PR49 ~ PR53 read / consumer-safety stack.

---

## 1. Purpose

```text
After PR49 ~ PR53, the framework has:
  - a policy for what can be read from the Engine (PR49)
  - an audit of what is already readable (PR50)
  - an executable wrapper that reads it (PR51)
  - a consumer-side packet consumption spec (PR52)
  - a consumer-side structural validator (PR53)

What is still undefined:
  - what an LLM is allowed to "say" about the validated packet
  - where the LLM output sits relative to the Engine
  - what the boundary is between LLM output and a human /
    operator decision

PR54 defines that boundary as a written spec.
It does NOT add any code.
```

The purpose of PR54 is to name and locate the proposal layer so that no future PR accidentally treats an LLM proposal as an Engine judgment, a tool execution authorization, a Claim status mutation, or a final report verdict.

---

## 2. Baseline

```text
main:    e4aad04 (PR53 merged)
tests:   1158 passing
ragcore.__all__:            48 symbols
Engine public methods:      40
snapshot schema_version:    2
snapshot top-level keys:    18

Reference documents this spec inherits from:
  docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md     (PR49)
  docs/architecture/ENGINE_READ_SURFACE_AUDIT.md           (PR50)
  docs/architecture/LLM_CONTEXT_PACKET_SPEC.md             (PR52)
  examples/inspector/engine_inspector.py                   (PR51)
  examples/inspector/packet_validator.py                   (PR53)
  tests/test_external_engine_inspector.py                  (PR51 185차)
  tests/test_packet_validator.py                            (PR53 190차)
  docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md          (PR44-D)
  direction_rag_framework_proposal_layer                    (memory direction)
```

---

## 3. Core boundary statement

```text
The proposal layer suggests what to inspect next.
It does not decide Engine truth.

proposal layer 는 다음에 무엇을 살펴볼지 제안한다.
Engine 의 진실을 결정하지 않는다.
```

This is the single sentence that governs every per-layer rule in this spec. Every other section (§4 ~ §14) must be readable as an expression of this sentence.

---

## 4. End-to-end flow

The PR49 ~ PR54 layered flow:

```text
Engine
  ↓ existing public read-only methods
external inspector  (PR51)
  ↓ 7-key packet
packet validator  (PR53, optional but recommended)
  ↓ validated packet
LLM proposal draft         ←── PR54 spec area (this document)
  ↓
proposal validator         ←── PR54 spec area
                                (implementation deferred to a
                                 future, separately decided PR)
  ↓ validated proposal
human / operator decision  ←── PR54 spec area
  ↓
[any downstream action]    ←── OUT OF PR54 SCOPE
  (RAG context build / tool plan / adapter call /
   Engine state change / report wording — all separate)
```

Cardinality:

```text
- one Engine instance → many packets per claim_id
- one packet            → zero or more LLM proposal drafts
- one proposal draft   → must pass proposal validator before
                          escalation
- validated proposal   → human / operator decides whether to act
- human decision       → may trigger downstream layers, but those
                          downstream layers are NOT part of PR54
```

---

## 5. What a proposal IS

A proposal is a structured suggestion produced by an LLM (or any external suggestion source) about *what to inspect next*. Conceptually, a proposal may carry items such as:

```text
- uncertainty notes
    "the packet's effective_confidence is low and there are 2
     active contradictions — worth a closer look"

- evidence gap questions
    "what additional evidence would resolve gap_id=N?"

- next inspection questions
    "should we query the source behind raw_ref_id=M
     before concluding anything?"

- packet summary notes
    "neutral textual summary of the packet, with engine-
     confidence presented as a decision-support signal"

- report note candidates
    "draft phrasing for a human-facing summary;
     subject to human edit before publication"
```

These are conceptual categories only. PR54 does NOT freeze a field set, an enum, or a schema. PR55 (if entered) may define a minimal consumer-side schema subject to §12 conditions.

Notes on language:

```text
- the word "action" is intentionally avoided.
  any future schema name should prefer:
    "proposal item" / "proposal note" / "inspection question"
    / "candidate follow-up"
  over "proposed_action" or similar wording that suggests
  execution authority.

- proposals MAY reference packet ids (claim_id / evidence_id /
  gap_id / opaque ref ids) as inspection targets.
  these references are read-only pointers; they are NOT
  mutation arguments.
```

---

## 6. What a proposal IS NOT

A proposal is NOT any of the following:

```text
- an Engine judgment
    proposals do not change Claim status, do not register
    Evidence, do not register Contradictions, do not create
    Gaps, do not call any add_* / register_* / *_if_ready
    Engine method on their own.

- an execution command
    proposals do not authorize a tool run, an external API
    call, a scanner invocation, or any side-effecting action.

- a final report verdict
    proposals are NOT the consumer's published output.
    they are intermediate candidates that a human / operator
    edits, approves, or discards before any external delivery.

- a probability statement
    proposals MUST NOT translate effective_confidence into
    "probability of X", "P(true) = Y", or any phrasing that
    PR52 §6 forbids.

- a policy decision
    proposals do not set thresholds, do not enforce SLAs,
    do not pick risk tiers. those belong to consumer-side
    policy / adapter / report layers.

- a packet mutation
    proposals do not modify the PR51 packet in place.
    they describe candidate follow-ups; the packet remains
    the original snapshot view of Engine state.

- a ragcore type
    no proposal-related class / dataclass / TypedDict / type
    alias may live inside ragcore source.
    see §13 for the symbol boundary.
```

---

## 7. Relationship to PR51 packet

```text
PR51 packet:
  the input domain to the proposal layer.
  shape: 7-key dict from build_engine_context_packet.
  produced by reading the Engine via 8 of 19 read-only methods.
  PR54 does NOT change the packet shape.

PR54 proposal:
  generated AFTER reading the packet.
  may reference the packet's ids (claim_id / evidence_id /
  gap_id / opaque contradiction id / lifecycle event seq).
  may include a textual summary that re-presents packet fields
  using the PR52 §6 allowed phrasings.
  MUST NOT re-encode packet values as probability / verdict /
  truth label.

Information flow:
  packet  → (LLM reads packet via PR52 spec) → proposal
  proposal → (validator + human review) → decision
  decision → (if any) → downstream layers
                         (those downstream layers are
                          OUT of PR54 scope)
```

---

## 8. Relationship to PR53 packet validator

PR53 and PR54's "proposal validator" share the word "validator" but operate on different inputs and at different times.

```text
PR53 packet validator  (already implemented in PR53)
  input:   consumer_output dict
            (the consumer's derived form of the packet —
             e.g., the LLM-facing payload, the report layer
             input)
  source:  source_packet (PR51 raw packet)
  detects: unsafe consumer interpretations of the packet
            (PR52 §5 F3 / F5 / F7 / F10 / F12 / F13)
  output:  list[tuple[F_id, message]]
  raises:  never
  scope:   structural pattern detection only;
            no LLM phrasing inference

PR54 proposal validator  (conceptual; NOT implemented in PR54)
  input:   LLM proposal draft structure
            (the structured suggestion the LLM produces about
             "what to inspect next")
  source:  the validated packet that the proposal references
  detects: unsafe proposal escalation into judgment,
            execution, mutation, final verdict
  output:  list of violations (shape deferred to PR55)
  raises:  never
  scope:   structural check of the proposal's claims
            (e.g., "does this proposal claim Engine state
             change?", "does this proposal authorize a tool
             run?"); no LLM prompt-content inference
```

Distinction summary:

```text
PR53 validator   = "did the consumer misread the packet?"
PR54 validator   = "did the proposal cross out of the
                    suggestion-only role?"
```

Both are structural. Neither inspects LLM phrasing. Neither monitors actual Engine mutation calls.

---

## 9. Allowed proposal categories

The following categories are allowed inside a proposal. This is a conceptual list; PR54 does NOT name fields or freeze a schema.

```text
A. Uncertainty notes
   - which claims have low engine_confidence
   - which claims have active contradictions
   - which claims have unresolved gaps
   - which lifecycle transitions have not fired and why
     (from claim_lifecycle_history empty / partial reading)

B. Evidence gap questions
   - "what evidence type would resolve gap_id=N?"
   - "is there a raw source (raw_ref_id=M) that has not been
      inspected yet?"
   - "which retrieval channel has not been queried?"

C. Next inspection questions
   - "should we look at the source behind raw_ref_id=K?"
   - "is contradiction evidence E sufficient to refute, or do
      we need supporting evidence first?"

D. Packet summary notes
   - neutral textual summary of the packet for a human reviewer
   - engine_confidence presented as decision-support signal
     (PR52 §6 allowed phrasings)
   - opaque ids stay opaque

E. Report note candidates
   - draft phrasing for a human-facing summary
   - explicitly marked as DRAFT until human edit / approval
   - MUST NOT include forbidden phrasings (PR52 §6)
```

The categories above are reader guidance, not a contract. A consumer may choose to support a subset.

---

## 10. Forbidden proposal readings

A proposal MUST NOT contain any of the following. Each item maps to existing PR44-D anti-pattern or PR52 §5 forbidden reading.

```text
P1   "verdict" / "label" / "judgment" / "decision" / "ruling"
     for a Claim
       → PR44-D AP-CF-1 / AP-CT-1 / PR52 §5 F10

P2   probability translation of effective_confidence
       → PR44-D AP-CF-1 / AP-X-4 / PR52 §5 F1 / F2

P3   automatic Claim status change suggestion treated as
     a state change
     (e.g., "set claim X to REFUTED" presented as an outcome
      rather than a question for the operator)
       → PR43-C §4.6 / PR44-D AP-L-1

P4   tool execution authorization
     (e.g., "run scanner Y on host Z" presented as approved
      rather than as a suggestion for operator review)
       → no Engine method exists for this; it is a downstream
          layer concern entirely outside PR54

P5   raw payload injection back into Engine
     (e.g., "add this raw_ref_id payload as new add_evidence
      content")
       → PR52 §5 F13 / PR44-D AP-E-1

P6   final report wording presented as already-published
       → PR54 §11; all report wording from a proposal is a
          draft until human edit / approval

P7   threshold-based binary verdict
     ("effective_confidence >= 0.7 ⇒ verified TRUE")
       → PR52 §5 F12 / PR44-D AP-CF-2

P8   domain vocabulary attached to ragcore-side identifiers
       → PR44-D AP-X-6
       → PR45-E §3 forbidden vocabulary
```

These forbidden readings define the boundary that a future proposal validator (PR55 or later) may structurally enforce.

---

## 11. Human / operator decision boundary

The human / operator is the final boundary in the PR54 flow.

```text
A validated proposal MAY:
  - be presented to a human reviewer in a UI / report draft
  - be cited in an operator dashboard as a follow-up candidate
  - be archived as a record of what the LLM suggested

A validated proposal MAY NOT (without human / operator
acceptance):
  - trigger any downstream layer
  - cause any tool execution
  - mutate any Engine state
  - update any report visible to end users
  - be re-presented as if it were the operator's decision

Human / operator acceptance is the gating event for any
downstream layer. PR54 does NOT specify the UI / approval
mechanism; that is consumer-side responsibility.

The human / operator decision itself is NOT a proposal. It is
the consumer-side authoritative event that turns suggestions
into action.
```

---

## 12. PR55 handoff boundary

PR55, if ever entered, would define a minimal consumer-side proposal schema and (optionally) a structural proposal validator.

PR55 entry is NOT automatic. PR55 may be entered only if ALL of the following 5 conditions hold:

```text
1. PR55 must not modify ragcore source.

2. PR55 must not add ragcore public symbols.
   (No LLMProposal / ProposalSchema / ProposalDraft /
    ProposalValidator into ragcore.__all__ or ragcore source.)

3. PR55 must not turn proposals into Engine judgments.
   (No mechanism by which a proposal — validated or not —
    auto-mutates Engine state.)

4. PR55 must not authorize tool execution.
   (No mechanism by which a proposal becomes an execution
    command without a separate human / operator gate.)

5. PR55 must keep human / operator decision as the final
   boundary.
   (The §11 boundary is preserved; PR55 may make the boundary
    more inspectable but must not bypass it.)
```

PR55 must additionally honor:

```text
- PR47 §3 do-not-touch boundary (10 items)
- PR49 §5 read-only definition (6 must-hold)
- PR52 §5 forbidden readings (F1 ~ F13)
- PR52 §8 ragcore symbol boundary
- PR53 false-positive prevention philosophy
  (validators must not re-judge what the Engine has decided)
```

PR54 itself does NOT enter PR55. The handoff boundary above is a written checklist for a future, separately decided PR.

---

## 13. Non-goals

PR54 does NOT do any of the following. Each is an explicit OOS lock.

```text
- modify ragcore source
- add any ragcore public symbol
- add LLMProposal / ProposalSchema / ProposalDraft /
  ProposalValidator as a ragcore type
- add any test
- add any code (no schema code, no validator code, no
  bridge runtime, no adapter helper)
- modify PR51 wrapper (examples/inspector/engine_inspector.py)
- modify PR53 validator (examples/inspector/packet_validator.py)
- modify PR51 / PR53 test files
- modify PR52 spec (docs/architecture/LLM_CONTEXT_PACKET_SPEC.md)
- modify any other architecture / guide / contract document
- expand into RAG Context Builder
- expand into Tool Plan Validator
- expand into Adapter Translation Policy
- expand into Engine Call Plan
- expand into Report Wording Guard
- expand into a Cerberus-side implementation
- authorize tool execution
- mutate Engine state in any documented flow
- reinterpret effective_confidence as truth probability
- produce a final report verdict
- auto-schedule PR55 or any later PR
- introduce contract §51
- introduce domain vocabulary
  (cerberus / vulnerability / scanner / exploit / ssh / cve /
   nmap / host / port / service / asset — all forbidden in
   this spec body)
```

---

## 14. Exit criteria

PR54 closes when ALL of the following hold:

```text
[ ] docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md added
[ ] pytest 1158 passing (unchanged from PR53 baseline)
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
[ ] PR52 spec unchanged
[ ] no proposal schema code introduced
[ ] no proposal validator code introduced
[ ] PR55 handoff boundary defined (§12)
[ ] PR55 NOT auto-entered
```

PR54's job is to define the proposal layer's location and boundary, and to write the §12 handoff checklist. It does not perform any implementation, schema freeze, or downstream-layer wiring.

---

## Closing meaning

```text
PR54 closes as a doc-only proposal layer bridge spec.

The proposal layer suggests what to inspect next.
It does not decide Engine truth.

A proposal is a structured suggestion about what to inspect
next. It is not an Engine judgment, not an execution command,
not a final report verdict, not a probability statement, not
a policy decision, not a packet mutation, and not a ragcore
type.

Validated proposals reach a human / operator who decides
whether to act. That human decision — not the proposal — is
the gating event for any downstream layer.

PR55 may define a minimal consumer-side proposal schema only
if it honors the 5 §12 entry conditions. PR55 is NOT
automatically entered.
```

Locked closing sentences:

```text
proposal layer 는 다음에 무엇을 살펴볼지 제안한다.
Engine 의 진실을 결정하지 않는다.

proposal 은 판단도 실행도 변조도 아니다.
proposal 은 다음 조사 후보를 구조화한다.

human / operator 의 결정이 downstream 의 게이트다.
PR55 는 자동 진입하지 않는다.
```
