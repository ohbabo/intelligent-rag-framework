# PR57 — Operator Decision Boundary Spec

## Scope limitation (locked, user 2026-05-25)

```text
PR57 closes the operator decision boundary after PR55 and PR56.

PR55 validates proposal shape.
PR56 validates proposal safety.
PR57 defines what operator acceptance means after validators
pass.

Operator acceptance is a gate, not Engine truth.
```

한국어:

```text
validator 통과는 수락이 아니다.
operator 수락도 Engine 진실이 아니다.
operator 수락은 downstream layer 로 넘기는 외부 게이트다.
```

PR57 closes the conceptual last layer of the PR49 ~ PR57 stack: what happens after both PR55 (shape) and PR56 (safety) validators return `[]`. It documents the operator's allowed and forbidden actions, locks the gating-event semantics, and writes entry conditions for PR58 / PR59 / a future Cerberus adapter. PR57 itself adds no code, no tests, no ragcore symbols.

## 1. Baseline + cycle record

```text
main:    3661c59  (PR56 merged)
tests:   1183 passing

200차:
  branch:  docs/operator-decision-boundary-spec
  commit:  b091f84 docs(architecture): define operator decision
                                       boundary
  file:    docs/architecture/OPERATOR_DECISION_BOUNDARY_SPEC.md
           (+702 lines, NEW)
  pytest:  1183 passing (unchanged)
  ragcore source change: 0 bytes

201차 (this):
  docs(dev): record PR57 closing + ready + squash merge
  file:    docs/dev/PR_057_OPERATOR_DECISION_BOUNDARY_SPEC.md
```

## 2. What PR57 is / is not

```text
PR57 = Operator Decision Boundary Spec
성격   = doc-only architecture spec
         PR55 (shape validator) / PR56 (safety validator) 가
         모두 [] 를 return 했을 때 operator acceptance 가
         무엇을 의미하는지 spec
         PR58 / PR59 / Cerberus adapter handoff entry
         conditions 박음
         operator-* 류 모두 NOT ragcore symbol 명시

성격 아님:
  - operator UI 구현
  - approval mechanism 구현
  - workflow engine 구현
  - Cerberus pipeline 구현
  - ragcore 확장
  - PR58 / PR59 / Cerberus adapter 자동 진입
  - 새 test / 새 source / 새 public symbol
```

## 3. Spec document structure (19 sections)

`docs/architecture/OPERATOR_DECISION_BOUNDARY_SPEC.md` — 702 lines, 19 sections:

```text
§0   Scope limitation
§1   Purpose
§2   Baseline
§3   Core boundary statement + 6 supporting locks
§4   Position in the PR49 ~ PR56 flow
§5   Validator pass is NOT acceptance
§6   Operator acceptance IS a gate
§7   What an operator CAN do                (8 actions)
§8   What an operator CANNOT do             (7 prohibitions)
§9   Relationship to Engine state           (20 mutation entry points)
§10  Relationship to PR55 / PR56 validators (3 sequential boundaries)
§11  Consumer-side audit record boundary
§12  Downstream tool execution boundary
§13  Ragcore symbol boundary                (operator-* NOT ragcore)
§14  PR58 Usage Playbook handoff            (5 must-hold)
§15  PR59 Violation Collector handoff       (5 must-hold + naming)
§16  Cerberus adapter handoff               (6 must-hold)
§17  Non-goals
§18  Exit criteria                          (24-item checklist)
     Closing meaning
```

19 sections. 702 lines. Zero ragcore source change. Zero new tests.

## 4. Core boundary statement + 6 supporting locks

Core sentence:

```text
Operator acceptance is a gate, not Engine truth.

operator 의 수락은 게이트이지, Engine 의 진실이 아니다.
```

6 supporting locks:

```text
validators pass            ≠   accepted
accepted                    ≠   Engine state mutation
accepted                    ≠   tool execution
accepted                    ≠   final report verdict
operator decision           =   gating event for downstream layers
operator decision           ∉   Engine state graph
                                 (consumer-side event)
```

These six locks together define operator decisions as something that lives outside the Engine and outside ragcore — a workflow event the consumer's process owns.

## 5. Operator can / cannot lists (§7 / §8)

### 5.1 What an operator CAN do (8 actions)

```text
1. Accept the proposal for further review
2. Reject the proposal
3. Rewrite the proposal into a safer or clearer consumer-side
   note (the rewrite remains a proposal; validators must
   re-run on it)
4. Request more evidence
   (the request itself does NOT mutate Engine)
5. Schedule a manual inspection
   (creates a consumer-side task; does NOT invoke Engine)
6. Create a consumer-side task referencing this proposal
7. Archive the proposal as a consumer-side audit record
8. Cite the proposal in a consumer-side dashboard EXPLICITLY
   as "a proposal" and NEVER as "Engine truth"
```

All of the above are workflow gates. None is a truth assertion.

### 5.2 What an operator CANNOT do (7 prohibitions)

```text
1. Bypass PR55 / PR56 validator failures
2. Mutate Engine state from a proposal alone
3. Mark a Claim true / false / refuted / confirmed from a
   proposal alone
4. Execute tools without a separate safety gate
5. Publish a final report verdict from a proposal alone
6. Auto-trigger a downstream Cerberus / domain-specific
   pipeline from proposal acceptance
7. Re-classify a Claim's status through proposal acceptance
   (NOT a substitute for confirm_claim_if_ready /
    refute_claim_if_ready / dispute_claim_if_ready / etc.)
```

These prohibitions preserve the separation between Engine judgment (inside ragcore) and consumer-side workflow decisions (outside ragcore).

## 6. PR55 / PR56 / PR57 3 sequential boundaries (§10)

```text
proposal draft
  → PR55 shape boundary    (must pass)
  → PR56 safety boundary    (must pass)
  → PR57 operator gate      (must be granted)  ←── this spec
  → downstream layer        (must have its own gate; OOS)

Each boundary is independent.
Earlier ones do NOT bless later ones.
Later ones do NOT bypass earlier ones.

If any boundary fails:
  PR55 fail   → proposal is not even safety-checked
  PR56 fail   → proposal is not presented to operator
  PR57 reject → no downstream layer is invoked

If all three pass:
  the proposal becomes one INPUT to a downstream consumer-side
  layer. That layer has its own boundaries and its own gates.
```

PR57 explicitly does NOT define the downstream layer's gates. Those are out of scope.

## 7. PR58 / PR59 / Cerberus adapter handoff

### 7.1 PR58 Usage Playbook handoff (§14, 5 must-hold)

```text
PR58 may define a consumer-side usage playbook for invoking
PR55 + PR56 validators and presenting their output to operators,
only if ALL of the following hold:

  1. PR58 treats validator pass as REVIEWABLE, not ACCEPTED.
  2. PR58 keeps operator acceptance OUTSIDE ragcore.
  3. PR58 does NOT add Engine behavior.
  4. PR58 does NOT define a Cerberus-specific workflow inside
     the framework.
  5. PR58 does NOT turn a proposal into an execution command.

PR58 must additionally honor:
  - PR47 §3 / PR49 §5 / PR52 §5 / PR52 §8 / PR54 §10 / PR54 §12
  - PR55 / PR56 validator separation
  - PR57 §7 / §8 (operator can / cannot)
  - PR57 §13 (ragcore symbol boundary)
```

### 7.2 PR59 Violation Collector handoff (§15, 5 must-hold + naming)

```text
PR59 may define a small helper that combines PR55 + PR56 outputs
into a single violations list, only if ALL of the following hold:

  1. PR59 is named for VIOLATION COLLECTION, not approval.
       safe:      collect_proposal_violations /
                  gather_proposal_violations /
                  join_proposal_violations
       forbidden: approve_proposal / authorize_proposal /
                  validate_and_accept_proposal /
                  accept_proposal / finalize_proposal
  2. PR59 preserves PR55 / PR56 separate meanings.
  3. PR59 does NOT authorize proposal acceptance.
       (Return type stays list[tuple[str, str]];
        no "accepted: bool" / "passed: bool" field;
        no auto-pipe to downstream.)
  4. PR59 does NOT execute tools.
  5. PR59 does NOT mutate Engine state.

PR59 must additionally honor:
  - PR47 §3 / PR49 §5 / PR52 §5 / PR52 §8 / PR54 §10 / PR54 §12
  - PR55 / PR56 ragcore-free invariant
```

### 7.3 Cerberus adapter handoff (§16, 6 must-hold)

```text
A Cerberus adapter may map this PR49 ~ PR57 stack into a real
domain workflow, only if ALL of the following hold:

  1. Lives OUTSIDE the intelligent-rag-framework repo.
  2. Does NOT add Cerberus-specific types to ragcore.
  3. Treats every proposal as an OPERATOR-REVIEW CANDIDATE,
     NOT as an Engine truth or as a tool-execution license.
  4. Uses SEPARATE safety gates for tool execution.
  5. Does NOT map operator acceptance directly to Engine truth.
  6. Must honor all of:
     - PR44-D AP-X-6 (no domain vocabulary intrusion)
     - PR44-D AP-X-7 (no adapter-specific symbol promotion)
     - PR52 §8 (LLM Context Packet boundary)
     - PR54 §8 (LLM Proposal boundary)
     - PR57 §7 / §8 / §9 / §11 / §12 / §13
```

PR58 / PR59 / Cerberus adapter are NOT auto-scheduled. Each requires explicit user decision.

## 8. Ragcore symbol boundary (§13, mirror PR52 §8 / PR54 §8)

```text
"Operator decision" / "operator acceptance" / "operator review"
are CONSUMER-SIDE concepts.

They are NOT ragcore symbols.

Forbidden in ragcore source as class / dataclass / TypedDict /
type alias:
  OperatorDecision
  OperatorReview
  OperatorApproval
  OperatorAction
  OperatorTask
  OperatorEvent
  OperatorAuditRecord

Forbidden in ragcore.__all__:
  any operator-* / approval-* / acceptance-* / gate-* symbol

If a future PR proposes an operator-related ragcore type, that
PR must:
  - first revoke §13 lock with explicit user authorization
  - additionally satisfy PR50 §8.3 conditions (α/β/γ/δ/ε)
  - honor PR44-D AP-X-7 (no adapter-specific symbol promotion)
  - honor PR44-D AP-X-6 (no domain vocabulary intrusion)
  - honor PR49 §8 PR51 Guard (a) / (b) / (c)
```

This mirrors PR52 §8 (LLMContextPacket) and PR54 §8 (LLMProposal): all consumer-side workflow concepts stay outside ragcore by default.

## 9. Self-review checklist (18/18)

```text
[x] docs/architecture/OPERATOR_DECISION_BOUNDARY_SPEC.md added
[x] docs/dev/PR_057_OPERATOR_DECISION_BOUNDARY_SPEC.md added
[x] pytest 1183 passing
[x] ragcore source change 0 bytes
[x] new tests 0
[x] new public symbol 0
[x] new Engine behavior 0
[x] Engine public methods unchanged (40)
[x] ragcore.__all__ unchanged (48)
[x] no operator-related ragcore symbols
[x] no Engine calls
[x] no tool execution
[x] no Engine mutation
[x] no Cerberus-specific adapter workflow
[x] PR58 handoff defined (spec §14)
[x] PR59 handoff defined (spec §15)
[x] Cerberus adapter handoff defined (spec §16)
[x] PR58 / PR59 / Cerberus adapter NOT auto-entered
```

## 10. No-change verification

```text
pytest -q                                1183 passing (unchanged from PR56)
ragcore.__all__                          48 symbols (PR31-S baseline)
unique symbols                           48
Engine public methods                    40 (PR33-M docstring 40/40)
modifier helpers                          6 with (self, claim_id: int) -> float
                                          (PR34-O signature preserved)
serialize/restore symmetry              6 × 6 (PR35-O7 preserved)
snapshot schema_version                   2 (PR21-L preserved)
snapshot top-level keys                  18 (PR36-PKG _LOCKED frozenset)
report shape                              6 frozen key sets (PR32-V)

ragcore source change since PR36-PKG     +66 lines (PR48-A banners only)
                                          PR57 itself contributes 0 lines
                                          to ragcore source
ragcore source cerberus mentions          0 (generic identity preserved)
external package imports in ragcore       0

adapter-specific symbols in ragcore.__all__:  none
ragcore type added in PR57:                    none
ragcore method surface change:                  none
new public symbol:                               0
new engine behavior:                             0
contract §51:                                    not added
runtime enforcement:                             0
adapter implementation:                          not included

PR51 wrapper unchanged
PR53 validator unchanged
PR55 validator unchanged
PR56 validator unchanged
PR52 / PR54 spec unchanged

operator-* symbol in ragcore source              0 (NOT promoted)
```

All framework invariants preserved.

## 11. What PR57 closed

```text
- operator decision boundary 명문화: "acceptance is a gate,
  not Engine truth"
- 6 supporting locks 박음 (validators pass / accepted /
  mutation / tool execution / final verdict / gating event /
  consumer-side event)
- operator can 8 actions list (§7)
- operator cannot 7 prohibitions list (§8)
- Engine state mutation 20 entry points 명시 (§9) —
  operator acceptance 는 그 list 에 없음
- PR55 / PR56 / PR57 3 sequential boundaries 정의 (§10)
- consumer-side audit record boundary (§11) — record 가
  consumer-side 임을 명시; 금지 표현 (truth / verified /
  mutation / execution / final report) 포함
- downstream tool execution boundary (§12) — tool 실행은
  PR57 scope 밖, 별도 layer 가 own gate 가짐
- ragcore symbol boundary (§13, PR52 §8 / PR54 §8 mirror)
- PR58 / PR59 / Cerberus adapter handoff entry conditions
  (§14 / §15 / §16) — 모두 자동 진입 금지
- PR59 naming policy (safe vs forbidden 명시)
- PR49 ~ PR57 stack 의 마지막 conceptual layer 닫음
```

## 12. What PR57 deliberately did NOT do

PR57 did NOT:

```text
- implement operator UI / approval mechanism / workflow engine
- specify operator authentication / authorization
- specify operator audit log shape
  (consumer's choice; §11 only lists what is and is not allowed)
- specify dashboard rendering or report layer
- modify any ragcore source file
- add any public symbol to ragcore.__all__
- add OperatorDecision / OperatorReview / OperatorApproval /
  OperatorAction / OperatorTask / OperatorEvent /
  OperatorAuditRecord as a ragcore type
- modify PR51 wrapper / PR53 validator / PR55 validator /
  PR56 validator
- modify PR52 spec / PR54 spec
- modify any other architecture / guide / contract document
- expand into RAG Context Builder / Tool Plan Validator /
  Adapter Translation Policy / Engine Call Plan /
  Report Wording Guard / Cerberus-specific implementation
- authorize tool execution
- mutate Engine state in any documented flow
- reinterpret effective_confidence as truth probability
- produce a final report verdict
- auto-schedule PR58 / PR59 / Cerberus adapter / any later PR
- introduce contract §51
- introduce domain vocabulary
  (cerberus / vulnerability / scanner / exploit / ssh / cve /
   nmap / host / port / service / asset)
```

## 13. Implementation footprint

Changed files (200 + 201):

```text
docs/architecture/OPERATOR_DECISION_BOUNDARY_SPEC.md   +702 lines (200차, NEW)
docs/dev/PR_057_OPERATOR_DECISION_BOUNDARY_SPEC.md     this record (201차)
```

Unchanged:

```text
ragcore/engine.py                                       (no PR57-attributable change)
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
pyproject.toml
README.md
docs/README.md
docs/contracts/05_DATA_CONTRACT_MVP.md                  (no §51 added)
docs/architecture/ENGINE_INTERNAL_MAP.md                 (PR47)
docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md    (PR49)
docs/architecture/ENGINE_READ_SURFACE_AUDIT.md          (PR50)
docs/architecture/LLM_CONTEXT_PACKET_SPEC.md            (PR52)
docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md          (PR54)
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
docs/guides/*
examples/probe/external_consumer_probe.py               (PR38-A)
examples/inspector/engine_inspector.py                  (PR51, UNCHANGED)
examples/inspector/packet_validator.py                  (PR53, UNCHANGED)
examples/proposal/proposal_schema.py                    (PR55, UNCHANGED)
examples/proposal/proposal_validator.py                 (PR56, UNCHANGED)
tests/* (no PR57-attributable change)
all other tests / docs
```

Note on `ragcore.egg-info/`:

```text
ragcore.egg-info/ is an untracked build artifact present at the
PR57 baseline; it was NOT added to either 200차 or 201차 commit.
It is not part of the PR57 footprint.
```

No ragcore source change. No test change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change. All prior PR artifacts (PR51 / PR53 / PR55 / PR56 / PR52 / PR54) preserved.

## 14. PR57 cycle

```text
200차  docs(architecture) — Operator Decision Boundary Spec (+702 lines)   b091f84
201차  docs(dev) — PR57 record + ready + squash merge                       this commit
```

Two-차수 cycle. No new tests. No source change. No new public API. No automatic next PR.

## 15. Pattern position recap

```text
PR39    compatibility audit                documentation-only
PR40    adapter policy guide               documentation-only
PR41    external adapter simulation        tests-only
PR42    retrieval translation guide        documentation-only
PR43-C  engine method call playbook        guide + tests
PR44-D  integration anti-patterns          documentation-only
PR45-E  domain-neutral reference flow      documentation-only
PR46-B  documentation map / reader entry   documentation-only
PR47    frozen engine internal refactor    documentation-only (audit)
            audit
PR48-A  engine section banners              src (comment-only)
PR49    engine read surface thaw policy    documentation-only (policy)
PR50    engine read surface audit          documentation-only (audit)
PR51    minimal claim read query MVP       examples + tests
PR52    LLM context packet spec            documentation-only (spec)
PR53    consumer packet validator MVP      examples + tests
PR54    proposal layer bridge spec         documentation-only (spec)
PR55    minimal LLM proposal schema MVP    examples + tests
PR56    proposal safety validator MVP      examples + tests
PR57    operator decision boundary spec    documentation-only (spec, this)

All nineteen (post-PR36-PKG):
  framework method surface frozen          ✓
  public observable behavior preserved      ✓
  no automatic next PR                      ✓
```

## 16. PR49 ~ PR57 layered stack (updated)

```text
PR49 — Engine Read Surface Thaw Policy
PR50 — Engine Read Surface Audit (Conclusion A)
PR51 — Minimal Claim Read Query MVP (wrapper + 6 invariant tests)
PR52 — LLM Context Packet Spec
PR53 — Consumer Packet Validator MVP (validator + 7 invariant tests)
PR54 — Proposal Layer Bridge Spec
PR55 — Minimal LLM Proposal Schema MVP (validator + 11 invariant tests)
PR56 — Proposal Safety Validator MVP (validator + 14 invariant tests)
PR57 — Operator Decision Boundary Spec (this PR)

stack:
  policy (PR49) → audit (PR50)
                → executable wrapper + tests (PR51)
                → consumer-side packet spec (PR52)
                → consumer-side packet validator + tests (PR53)
                → proposal layer bridge spec (PR54)
                → consumer-side proposal schema validator + tests (PR55)
                → consumer-side proposal safety validator + tests (PR56)
                → operator decision boundary spec (PR57, this)
                → [PR58 / PR59 / Cerberus adapter — NOT entered]

Proposal pipeline boundaries fully written:
  packet validation (PR53)
    → proposal shape (PR55)
    → proposal safety (PR56)
    → operator gate (PR57)
    → downstream layer (own gate, OOS)
```

PR57 is the final spec layer of the read / consumer-safety / proposal / operator-decision stack. With PR57 merged, every conceptual boundary from Engine state to operator gate is named, locked, and (where applicable) executable.

## 17. Followup

```text
Possible follow-up directions (NOT auto-scheduled):

A. PR58 — Usage Playbook
   consumer-side how-to-call playbook
   must honor PR57 §14 5 must-hold

B. PR59 — Violation Collector
   small helper combining PR55 + PR56 outputs
   must honor PR57 §15 5 must-hold + naming policy
   safe names: collect_/gather_/join_proposal_violations
   forbidden names: approve_/authorize_/accept_proposal

C. Cerberus adapter (separate repo)
   must honor PR57 §16 6 must-hold
   lives OUTSIDE intelligent-rag-framework

D. Extend PR56 with free-text semantic detection
   (high false-positive risk; intentionally not entered in PR56)

E. Stop here and let the framework wait

Each requires explicit user decision. PR57 does NOT
auto-schedule any of them.
```

## 18. Framework state (post-PR57)

```text
ragcore baseline:
  main:    3661c59 (pre-merge; new hash after squash merge)
  1183 tests passing (unchanged from PR56)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  3 architecture audits
    - compatibility matrix (PR39)
    - engine internal map (PR47)
    - engine read surface audit (PR50)
  4 architecture policy / spec
    - engine read surface thaw policy (PR49)
    - LLM context packet spec (PR52)
    - proposal layer bridge spec (PR54)
    - operator decision boundary spec (PR57 — this)
  5 adapter guides
  1 documentation map / reader entry point
  4 external examples
    - examples/probe/external_consumer_probe.py     (PR38-A)
    - examples/inspector/engine_inspector.py        (PR51)
    - examples/inspector/packet_validator.py        (PR53)
    - examples/proposal/proposal_schema.py          (PR55)
    - examples/proposal/proposal_validator.py       (PR56)
  6 executable test suites
    - test_external_adapter_simulation.py           (PR41, 18 tests)
    - test_engine_method_call_playbook_usage.py     (PR43-C 168차, 12 tests)
    - test_external_engine_inspector.py             (PR51 185차, 6 tests)
    - test_packet_validator.py                       (PR53 190차, 7 tests)
    - test_proposal_schema.py                        (PR55 195차, 11 tests)
    - test_proposal_validator.py                     (PR56 198차, 14 tests)
  1 behavior-preserving refactor commit on engine.py
    (PR48-A comment-only banners)

PR49 ~ PR57 layered stack status:
  judgment semantics                         frozen ✓
  read surface policy                        defined ✓ (PR49)
  read surface audit                         complete ✓ (PR50)
  executable wrapper + invariant lock        complete ✓ (PR51)
  consumer-side packet spec                  complete ✓ (PR52)
  consumer-side packet validator + tests     complete ✓ (PR53)
  proposal layer bridge spec                 complete ✓ (PR54)
  consumer-side proposal schema + tests      complete ✓ (PR55)
  consumer-side proposal safety + tests      complete ✓ (PR56)
  operator decision boundary spec            complete ✓ (PR57, this)
  PR58 / PR59 / Cerberus adapter             NOT entered

ragcore source change since PR36-PKG:  +66 lines (PR48-A banners only)
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 19. Closing meaning

```text
PR57 closes the operator decision boundary.

Validators passing means the proposal may be reviewed.
Operator acceptance means the proposal may pass through a
consumer-side gate.
Neither validator pass nor operator acceptance is Engine truth.

The proposal layer is now bounded through:
  packet validation → proposal shape → proposal safety
                                       → operator gate
```

Locked closing sentences:

```text
PR57 closes the operator decision boundary after PR55 and PR56.

PR55 validates proposal shape.
PR56 validates proposal safety.
PR57 defines what operator acceptance means after validators
pass.

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

No automatic next-PR proposal. User decides direction.
