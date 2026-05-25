# Proposal Usage Playbook

Status: guide (PR58)
Baseline: main `5039e86` (PR57 merged)
Type: doc-only consumer-side usage guide; no source change, no test change, no public symbol change

## 0. Scope limitation (locked, user 2026-05-25)

```text
PR58 documents how a consumer-side caller should invoke the
PR49 ~ PR57 stack end-to-end, from Engine read packet through
proposal validation to operator review.

It does NOT add ragcore behavior.
It does NOT add Engine method calls beyond the existing 40.
It does NOT add new example files.
It does NOT define new classes or dataclasses.
It does NOT authorize tool execution.
It does NOT auto-schedule PR59 or any downstream adapter.
```

한국어:

```text
PR58 은 PR49 ~ PR57 stack 을 consumer 가 end-to-end 로 어떻게
호출하는지 정리한 사용 가이드 다.

ragcore 동작 추가 / 새 Engine method / 새 example file / 새
class·dataclass / tool 실행 승인 / PR59·downstream adapter
자동 진입 — 모두 포함되지 않는다.
```

PR58 turns the previously documented stack into a single, readable end-to-end story for consumers. It is the playbook companion to the PR49 ~ PR57 boundary specs.

---

## 1. Purpose / Position

```text
After PR49 ~ PR57, the framework has:
  - a read surface thaw policy and audit                  (PR49 / PR50)
  - an executable read wrapper                            (PR51)
  - a packet consumption spec and validator               (PR52 / PR53)
  - a proposal layer bridge spec                           (PR54)
  - a proposal shape validator                             (PR55)
  - a proposal safety validator                            (PR56)
  - an operator decision boundary spec                    (PR57)

What remained un-narrated:
  - what does a consumer actually call, in what order, to use
    all of the above safely?

PR58 answers that question as a playbook.

It does NOT add code.
It does NOT add tests.
It does NOT introduce any new abstraction.
```

PR58 is the seventh doc-only artifact in the PR49 ~ PR57 stack and the first PR after PR57 to be reader-facing.

---

## 2. Baseline

```text
main:    5039e86 (PR57 merged)
tests:   1183 passing
ragcore.__all__:            48 symbols
Engine public methods:      40
snapshot schema_version:    2
snapshot top-level keys:    18

Reference artifacts this playbook uses:
  examples/inspector/engine_inspector.py                  (PR51)
  examples/inspector/packet_validator.py                  (PR53)
  examples/proposal/proposal_schema.py                    (PR55)
  examples/proposal/proposal_validator.py                 (PR56)
  docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md    (PR49)
  docs/architecture/ENGINE_READ_SURFACE_AUDIT.md          (PR50)
  docs/architecture/LLM_CONTEXT_PACKET_SPEC.md            (PR52)
  docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md         (PR54)
  docs/architecture/OPERATOR_DECISION_BOUNDARY_SPEC.md    (PR57)
  docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md              (PR43-C)
  docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md         (PR44-D)
```

No new file is referenced.

---

## 3. Locked principles

The PR58 playbook is governed by these inherited locks. The playbook adds no new locks; it only puts existing ones into a call-order narrative.

```text
PR49: We thaw the read surface, not the judgment semantics.
PR52: The packet informs the consumer.
       It does not replace Engine judgment.
PR54: The proposal layer suggests what to inspect next.
       It does not decide Engine truth.
PR57: Operator acceptance is a gate, not Engine truth.

Composed reading:
  Validator pass means reviewable.
  Operator acceptance means gated.
  Neither means Engine truth.
```

These five sentences govern every step in §4 below.

---

## 4. Step-by-step usage

The full consumer-side pipeline for one Claim is nine steps. Each step references the artifact that owns it and the inputs / outputs that flow.

### 4.1 Build Engine context packet

```text
Source:  examples/inspector/engine_inspector.py            (PR51)
Method:  build_engine_context_packet(engine, claim_id)
Output:  packet — a plain dict with 7 keys

Allowed:
  - call the wrapper with an existing Engine instance and a
    valid claim_id
  - read returned packet fields per PR52 §4 semantics

Forbidden:
  - inspect Engine private attributes
  - rebuild the packet from a different reading method
  - mutate the returned packet before validation
```

### 4.2 Validate / inspect packet (optional but recommended)

```text
Source:  examples/inspector/packet_validator.py           (PR53)
Method:  validate_consumer_packet_interpretation(
             consumer_output, source_packet)
Output:  list[tuple[F_id, message]] — empty means safe

Purpose:
  Guard against consumer-side misreads of the packet
  (e.g., piping evidence.strength as probability,
   treating contradictions as auto-refutation, etc.)

Note:
  The "consumer_output" passed here is the consumer's derived
  dict (e.g., the dict you will hand to the LLM prompt or the
  report layer). NOT the packet itself.
```

### 4.3 Build LLM prompt with packet

```text
Source:  docs/architecture/LLM_CONTEXT_PACKET_SPEC.md     (PR52)
Owner:   consumer-side (no ragcore code involved)

Allowed phrasings (PR52 §6):
  "engine_confidence: 0.87"
  "computed signal: 0.87"
  "effective_confidence (decision-support): 0.87"
  "lifecycle phase: CANDIDATE" / etc.
  opaque ids for evidence / gap / contradiction / lifecycle event

Forbidden phrasings (PR52 §6):
  "P(true) = 0.87"
  "probability of vulnerability: 87%"
  "verified true with 0.87 confidence"
  "the engine's verdict"
  any framing that treats packet AS decision rather than informing one

Prompt template rule:
  - include the decision-support disclaimer
  - never ask the LLM to compute "final probability" or
    "final verdict" from the packet
  - ask only for proposals (evidence to collect, gaps to fill,
    contradictions to investigate)
```

### 4.4 Receive LLM proposal draft

```text
Source:  consumer-side LLM call (NOT ragcore)
Output:  proposal — a plain dict

Expected minimal shape (per PR55):
  {
      "category": <one of 5 allowed strings>,
      "target_claim_id": <int>,
      "note": <str>,
      // optional:
      "target_evidence_id": <int>,
      "target_gap_id": <int>,
      "supporting_packet_ref": <str>,
  }

The proposal MUST NOT carry verdicts, probabilities, tool plans,
Engine mutation args, or final report text. Validators in 4.5 /
4.6 will catch any of those structurally.
```

### 4.5 Validate proposal shape

```text
Source:  examples/proposal/proposal_schema.py             (PR55)
Method:  validate_llm_proposal_shape(proposal, source_packet)
Output:  shape_violations: list[tuple[code, message]]

Action:
  if shape_violations:
      reject the proposal; do not pass to operator
      consumer may retry the LLM with a corrected prompt
```

### 4.6 Validate proposal safety

```text
Source:  examples/proposal/proposal_validator.py          (PR56)
Method:  validate_proposal_safety(proposal, source_packet)
Output:  safety_violations: list[tuple[code, message]]

Action:
  if safety_violations:
      reject the proposal; do not pass to operator
      consumer may retry the LLM with a corrected prompt

Both validators are independent. Composing them gives strictest
safety. Validator pass is a *necessary precondition* for operator
review, not a sufficient one.
```

### 4.7 Present to operator

```text
Source:  docs/architecture/OPERATOR_DECISION_BOUNDARY_SPEC.md (PR57)
Owner:   consumer-side UI / ticket / dashboard

Allowed framing (PR57 §6):
  "this is a validator-passed proposal; please review"

Forbidden framing:
  "this is a verified claim"
  "this is approved"
  "this is the Engine's decision"
  "this requires action"  (without explicit gate)

The operator sees:
  - the validator-passed proposal
  - a clear "proposal, not truth" label
  - the source_packet's relevant context (optional)
```

### 4.8 Handle operator decision

```text
Source:  PR57 §7 (operator CAN) and §8 (operator CANNOT)
Owner:   consumer-side workflow

Operator CAN:
  accept / reject / rewrite / request more evidence /
  schedule manual inspection / create consumer-side task /
  archive as audit record / cite as proposal (not truth)

Operator CANNOT:
  bypass validator failures /
  mutate Engine from proposal alone /
  mark Claim true/false/refuted/confirmed from proposal /
  execute tools without separate safety gate /
  publish final verdict from proposal alone /
  auto-trigger downstream pipeline /
  re-classify Claim status through acceptance

Acceptance writes a consumer-side audit record (PR57 §11).
Acceptance does NOT call any Engine method.
```

### 4.9 Downstream layer requires its own gate

```text
Source:  PR57 §12, PR57 §16
Owner:   consumer-side downstream system (out of PR58 scope)

If acceptance triggers a downstream layer (tool execution,
ticketing, report draft, Engine state change via separate
evidence collection, etc.), that downstream layer MUST have
its own authorization gate.

PR58 does NOT define the downstream layer.
PR58 does NOT define the gate.
PR58 only states the boundary: the playbook ENDS here.

Any Engine state change that follows must go through the
normal 40-method Engine public API with its own evidence,
its own rule association, and its own *_if_ready lifecycle
helper invocation — NOT directly from operator acceptance.
```

---

## 5. End-to-end pseudocode

```python
# CONSUMER-SIDE PSEUDOCODE
# This is illustrative. No new files / classes are introduced
# by PR58. All names below are dict shapes or function pointers
# that already exist in PR51 / PR53 / PR55 / PR56.


# Step 4.1 — Build packet
packet: dict = build_engine_context_packet(engine, claim_id)


# Step 4.2 — (optional) check that the consumer's derived form
# of the packet does not misread it.
# 'consumer_output' is your derived dict, NOT the packet itself.
consumer_output: dict = build_consumer_output_from_packet(packet)
packet_violations: list[tuple[str, str]] = (
    validate_consumer_packet_interpretation(consumer_output, packet)
)
if packet_violations:
    # Consumer-side misread; fix and rebuild before LLM.
    return advise_consumer_to_rebuild(packet_violations)


# Step 4.3 — Build the LLM prompt using PR52 §6 allowed phrasings.
# (Function definition is consumer-side; not part of PR58.)
prompt: str = build_safe_prompt_for_llm(consumer_output)


# Step 4.4 — Receive proposal draft from the LLM.
# (LLM call mechanism is consumer-side.)
proposal: dict = call_llm_for_proposal(prompt)


# Step 4.5 — Shape validate.
shape_violations: list[tuple[str, str]] = (
    validate_llm_proposal_shape(proposal, packet)
)


# Step 4.6 — Safety validate.
safety_violations: list[tuple[str, str]] = (
    validate_proposal_safety(proposal, packet)
)


# Combine for presentation; both must be empty to proceed.
all_violations = shape_violations + safety_violations
if all_violations:
    return reject_proposal(proposal, all_violations)


# Step 4.7 — Present to operator.
# The operator UI is consumer-side; PR58 does not specify it.
display_proposal_to_operator(
    proposal=proposal,
    source_packet=packet,
    label="proposal, not truth",
)


# Step 4.8 — Handle operator decision.
decision: str = wait_for_operator_decision()
# decision ∈ {accept / reject / rewrite / request_more_evidence /
#             schedule_manual_inspection / create_task /
#             archive / cite_as_proposal}

# Write consumer-side audit record. PR57 §11 — outside ragcore.
record_operator_decision_audit(
    proposal=proposal,
    shape_violations=shape_violations,   # ([] here, by precondition)
    safety_violations=safety_violations, # ([] here, by precondition)
    decision=decision,
)


# Step 4.9 — Downstream layer (own gate).
# PR58 ends here. Any downstream layer (tool run, report draft,
# Engine state change via separate evidence) is OUT OF SCOPE.
# That layer must invoke its own authorization, scope, and audit
# mechanisms and, if it touches the Engine, must do so through
# the normal 40-method public API with its own evidence.
return decision
```

This pseudocode uses only:

```text
- the 4 already-existing example functions
  (build_engine_context_packet,
   validate_consumer_packet_interpretation,
   validate_llm_proposal_shape,
   validate_proposal_safety)
- consumer-side function names that the consumer defines
  themselves (build_consumer_output_from_packet,
  build_safe_prompt_for_llm, call_llm_for_proposal,
  display_proposal_to_operator, wait_for_operator_decision,
  record_operator_decision_audit, reject_proposal,
  advise_consumer_to_rebuild)

It defines no new class, no new dataclass, no new ragcore symbol.
```

---

## 6. Common mistakes and cross-references

This section names the most common misuse patterns a new consumer might fall into. Each maps to an existing anti-pattern lock.

```text
Mistake 1: presenting the packet to the operator as "truth"
  → PR44-D AP-CF-1
  → PR52 §5 F1 / F2
  → PR57 §6 forbidden framing

Mistake 2: piping evidence.strength as probability
  → PR41 §50.9 / §50.10
  → PR44-D AP-X-1
  → PR52 §5 F3
  → PR55 P2 detect / PR56 P2 detect

Mistake 3: treating contradictions as auto-refutation
  → PR43-C §4.5
  → PR44-D AP-CT-1
  → PR53 F5 detect

Mistake 4: treating unresolved_gaps as refutation
  → PR43-C §4.4
  → PR44-D AP-G-1
  → PR53 F7 detect

Mistake 5: relabeling Claim.status as a verdict
  → PR43-C §4.3
  → PR44-D AP-X-4
  → PR53 F10 detect / PR55 P1 detect (top-level) /
    PR56 P1 detect (nested)

Mistake 6: hardcoding effective_confidence threshold as
            auto-verified
  → PR43-C §4.7
  → PR44-D AP-CF-2
  → PR53 F12 detect / PR55 P7 detect / PR56 P7 detect

Mistake 7: stuffing add_evidence args into a proposal
  → PR42 §13
  → PR44-D AP-E-1
  → PR53 F13 detect / PR55 P5 detect / PR56 P5 detect

Mistake 8: authorizing tool execution from proposal acceptance
  → PR54 §10 P4
  → PR55 P4 detect / PR56 P4 detect
  → PR57 §8 (operator cannot)

Mistake 9: marking Claim status via operator acceptance
  → PR57 §8 (operator cannot)
  → PR43-C §4.6 (lifecycle helpers must be invoked explicitly)

Mistake 10: introducing domain vocabulary
            (cerberus / vulnerability / scanner / exploit / ssh /
             cve / nmap / host / port / service / asset)
            inside identifiers
  → PR44-D AP-X-6
  → PR45-E §3 forbidden vocabulary
  → PR56 P8 detect

In all ten cases the existing validators or anti-pattern locks
catch the mistake; the playbook only points to them.
```

---

## 7. PR57 §14 must-hold cross-check

PR57 §14 lists 5 must-hold entry conditions for any Usage Playbook PR. PR58 satisfies all five:

```text
(1) Validator pass = REVIEWABLE, not ACCEPTED.
    → §4.6 explicitly states that validator pass is a
      "necessary precondition for operator review, not a
      sufficient one."
    → §4.7 forbids any framing that suggests "accepted" /
      "verified" / "approved."
    → §3 "Composed reading" sentence: Validator pass means
      reviewable. Operator acceptance means gated. Neither
      means Engine truth.

(2) Operator acceptance lives OUTSIDE ragcore.
    → §4.8 records acceptance as a consumer-side audit record
      (PR57 §11), with NO Engine method invocation.
    → §5 pseudocode's record_operator_decision_audit() is
      consumer-side; it is not a ragcore call.

(3) Playbook adds NO Engine behavior.
    → §5 pseudocode invokes Engine ONLY through PR51's
      build_engine_context_packet (a read-only wrapper).
    → No add_*, register_*, *_if_ready, update_* call appears.

(4) Playbook defines NO Cerberus-specific workflow inside the
    framework.
    → §4 / §5 narratives use domain-neutral nouns
      (consumer / operator / packet / proposal / claim /
       evidence / gap / contradiction).
    → §8 / §13 of OPERATOR_DECISION_BOUNDARY_SPEC.md (PR57)
      Cerberus adapter handoff is referenced only as OOS
      (§9 below).

(5) Proposal NEVER becomes an execution command.
    → §4.9 explicitly states the playbook ENDS at "downstream
      layer requires its own gate."
    → §5 pseudocode's final 'return decision' returns only an
      operator decision label; no tool run / no Engine mutation
      / no auto-trigger happens.

Additionally honored:
  PR47 §3 / PR49 §5 / PR52 §5 / PR52 §8 / PR54 §10 / PR54 §12 /
  PR55 / PR56 validator separation / PR57 §7 / §8 / §13.
```

---

## 8. What this playbook does NOT do

PR58 does NOT do any of the following.

```text
- modify ragcore source
- add any ragcore public symbol
- add any test
- add any new example file
  (the 4 already-existing example modules are referenced as-is)
- define any new class, dataclass, TypedDict, or type alias
- introduce LLMContextPacket / LLMProposal / ProposalSchema /
  ProposalValidator / OperatorDecision / OperatorReview as a
  ragcore type
- modify PR51 wrapper / PR53 validator / PR55 validator /
  PR56 validator
- modify PR49 / PR50 / PR52 / PR54 / PR57 specs
- define an operator UI / approval mechanism / workflow engine
- specify operator authentication / authorization
- specify audit log shape (consumer's choice)
- specify dashboard rendering or report layer
- specify a tool execution gate
- specify a RAG Context Builder / Tool Plan Validator /
  Adapter Translation Policy / Engine Call Plan /
  Report Wording Guard
- specify a Cerberus-side adapter implementation
  (Cerberus adapter handoff is PR57 §16; it lives OUTSIDE
   the intelligent-rag-framework repo)
- authorize tool execution
- mutate Engine state in any documented flow
- reinterpret effective_confidence as truth probability
- produce a final report verdict
- auto-schedule PR59 (violation collector) or any later PR
- introduce contract §51
- introduce domain vocabulary
  (cerberus / vulnerability / scanner / exploit / ssh / cve /
   nmap / host / port / service / asset) into narrative
```

---

## 9. Exit criteria

PR58 closes when ALL of the following hold:

```text
[ ] docs/guides/PROPOSAL_USAGE_PLAYBOOK.md added
[ ] pytest 1183 passing (unchanged from PR57 baseline)
[ ] ragcore.__all__ 48 symbols (unchanged)
[ ] Engine public methods 40 (unchanged)
[ ] snapshot schema_version 2 (unchanged)
[ ] snapshot top-level keys 18 (unchanged)
[ ] ragcore source change 0 bytes
[ ] test change 0
[ ] new public symbol 0
[ ] new engine behavior 0
[ ] no new example file
[ ] no new class / dataclass / TypedDict / type alias
[ ] PR57 §14 5 must-hold cross-check section present (§7 above)
[ ] PR51 wrapper / PR53 validator / PR55 validator /
    PR56 validator unchanged
[ ] PR49 / PR50 / PR52 / PR54 / PR57 specs unchanged
[ ] no operator-* symbol in ragcore source
[ ] PR59 NOT auto-entered
[ ] Cerberus adapter NOT auto-entered
[ ] contract §51 not added
```

PR58 's job is to narrate the consumer-side call sequence. It does not perform any implementation, schema freeze, or downstream-layer wiring.

---

## Closing meaning

```text
The playbook shows how to use the proposal pipeline.
It does not create a new decision layer.

Validator pass means reviewable.
Operator acceptance means gated.
Neither means Engine truth.
```

Locked closing sentences:

```text
PR58 closes the proposal usage playbook.

The pipeline reads as:
  build packet (PR51)
    → (optional) inspect packet consumption (PR53)
    → build safe LLM prompt (PR52 §6)
    → receive LLM proposal
    → validate proposal shape (PR55)
    → validate proposal safety (PR56)
    → present to operator (PR57 §6)
    → handle operator decision (PR57 §7 / §8)
    → downstream layer requires its own gate (PR57 §12)

LLMContextPacket / LLMProposal / ProposalSchema /
ProposalValidator / OperatorDecision remain NOT ragcore symbols.

PR59 (violation collector) and any external adapter remain
NOT automatically entered.
```
