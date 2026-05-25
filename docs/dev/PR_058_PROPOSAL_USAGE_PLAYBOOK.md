# PR58 — Proposal Usage Playbook

## Scope limitation (locked, user 2026-05-25)

```text
PR58 documents the consumer-side proposal pipeline.

It shows how to use:
  PR51 read wrapper
  PR53 packet validator
  PR52 packet phrasing
  PR55 proposal shape validator
  PR56 proposal safety validator
  PR57 operator gate

It does not create a new decision layer.
```

한국어:

```text
PR58 은 새 기능이 아니라 사용 흐름 문서다.

validator pass 는 reviewable 이다.
operator acceptance 는 gated 이다.
둘 다 Engine truth 가 아니다.
```

PR58 narrates the PR49 ~ PR57 stack as a single consumer-side end-to-end pipeline. No new code, no new examples, no new ragcore symbols, no new decision layer.

## 1. Baseline + cycle record

```text
main:    5039e86  (PR57 merged)
tests:   1183 passing

202차:
  branch:  docs/proposal-usage-playbook
  commit:  5e55875 docs(guides): add proposal usage playbook
  file:    docs/guides/PROPOSAL_USAGE_PLAYBOOK.md
           (+628 lines, NEW)
  pytest:  1183 passing (unchanged)
  ragcore source change: 0 bytes

203차 (this):
  docs(dev): record PR58 closing + ready + squash merge
  file:    docs/dev/PR_058_PROPOSAL_USAGE_PLAYBOOK.md
```

## 2. What PR58 is / is not

```text
PR58 = Proposal Usage Playbook
성격   = doc-only consumer-side usage guide
         PR49 ~ PR57 stack 의 end-to-end 호출 흐름을 narrative
         로 정리
         PR43-C ENGINE_METHOD_CALL_PLAYBOOK 의 자매 문서
         (engine method call playbook ↔ proposal usage playbook)

성격 아님:
  - new feature / new code / new abstraction
  - new decision layer
  - new example file
  - new class / dataclass / TypedDict / type alias
  - new ragcore symbol
  - Engine mutation flow
  - tool execution authorization
  - Cerberus-specific workflow
  - PR59 / Cerberus adapter 자동 진입
```

## 3. Playbook document structure (13 sections)

`docs/guides/PROPOSAL_USAGE_PLAYBOOK.md` — 628 lines, 13 sections:

```text
§0   Scope Limitation
§1   Purpose / Position
§2   Baseline
§3   Locked Principles                    (5 inherited sentences)
§4   Step-by-step usage                   (4.1 ~ 4.9, 9 steps)
§5   End-to-end pseudocode                (inline Python)
§6   Common mistakes and cross-references (10 mistakes mapped)
§7   PR57 §14 must-hold cross-check       (5/5 verified)
§8   What this playbook does NOT do
§9   Exit criteria                         (19-item)
Closing meaning
```

13 sections. 628 lines. Zero ragcore source change. Zero new tests. Zero new examples.

## 4. 9-step pipeline (§4 summary)

```text
4.1  build_engine_context_packet(engine, claim_id)              (PR51)
        → packet (7-key dict)

4.2  (optional) validate_consumer_packet_interpretation(
         consumer_output, packet)                                (PR53)
        → packet_violations

4.3  build LLM prompt with packet                               (PR52 §6)
        consumer-side; allowed phrasings only

4.4  call LLM for proposal
        consumer-side; LLM owns the call

4.5  validate_llm_proposal_shape(proposal, packet)              (PR55)
        → shape_violations; reject if non-empty

4.6  validate_proposal_safety(proposal, packet)                 (PR56)
        → safety_violations; reject if non-empty

4.7  display proposal to operator                                (PR57 §6)
        label: "proposal, not truth"

4.8  handle operator decision                                    (PR57 §7/§8)
        operator ∈ {accept / reject / rewrite /
                     request_more_evidence /
                     schedule_manual_inspection /
                     create_task / archive / cite}
        record consumer-side audit                               (PR57 §11)

4.9  downstream layer requires its own gate                     (PR57 §12)
        PR58 ENDS here.
```

Each step is read-only or consumer-side; no Engine mutation API is invoked beyond the PR51 read wrapper.

## 5. PR57 §14 must-hold cross-check (5/5 verified)

```text
(1) Validator pass = REVIEWABLE, not ACCEPTED.
    Verified in playbook §4.6 ("validator pass is a necessary
    precondition for operator review, not a sufficient one")
    and §4.7 (forbids "accepted" / "verified" / "approved"
    framings).

(2) Operator acceptance lives OUTSIDE ragcore.
    Verified in playbook §4.8 ("acceptance writes a
    consumer-side audit record; acceptance does NOT call any
    Engine method") and §5 pseudocode's
    record_operator_decision_audit() is consumer-side.

(3) Playbook adds NO Engine behavior.
    Verified in playbook §5 pseudocode: the only Engine-touching
    call is build_engine_context_packet (PR51 read wrapper);
    no add_* / register_* / *_if_ready / update_* appears.

(4) Playbook defines NO Cerberus-specific workflow inside the
    framework.
    Verified in playbook narrative — domain-neutral nouns only.
    "Cerberus adapter" appears solely as OOS reference per
    PR57 §16 handoff.

(5) Proposal NEVER becomes execution command.
    Verified in playbook §4.9 (explicit "playbook ENDS at
    downstream gate") and §5 pseudocode final 'return decision'
    returns operator decision label only — no tool run, no
    Engine mutation, no auto-trigger.

All 5 conditions explicitly satisfied.
```

Additionally honored:

```text
PR47 §3 / PR49 §5 / PR52 §5 / PR52 §8 /
PR54 §10 / PR54 §12 /
PR55 / PR56 validator separation /
PR57 §7 / §8 / §13
```

## 6. 10 common mistakes cross-reference (§6 summary)

```text
Mistake 1   packet as "truth"                  PR44-D AP-CF-1 / PR52 §5 / PR57 §6
Mistake 2   evidence.strength as probability   PR41 §50.9/10 / PR55 P2 / PR56 P2
Mistake 3   contradictions as auto-refutation  PR44-D AP-CT-1 / PR53 F5
Mistake 4   unresolved_gaps as refutation       PR44-D AP-G-1 / PR53 F7
Mistake 5   Claim.status as verdict             PR44-D AP-X-4 / PR53 F10 / PR55 P1
Mistake 6   threshold as auto-verified         PR44-D AP-CF-2 / PR53 F12 / PR55 P7
Mistake 7   add_evidence args in proposal      PR44-D AP-E-1 / PR55 P5 / PR56 P5
Mistake 8   tool execution from acceptance     PR55 P4 / PR56 P4 / PR57 §8
Mistake 9   Claim status via acceptance         PR57 §8 / PR43-C §4.6
Mistake 10  domain vocab in identifiers        PR44-D AP-X-6 / PR56 P8
```

In all 10 cases the existing validators or anti-pattern locks catch the mistake; PR58 only points to them. No new detector is added.

## 7. Domain-neutral vocabulary audit

```text
Narrative body:    0 forbidden vocab.

Allowed reference appearances (sanctioned by PR58 entry decision §7):
  - PR52 §6 forbidden phrasing quotation                 (§4.3)
  - PR45-E §3 / PR44-D §5.6 forbidden vocab list
    quotation                                            (§6 Mistake 10,
                                                          §8 OOS list)
  - PR57 §16 Cerberus adapter handoff OOS reference      (§7 must-hold #4,
                                                          §8 OOS list)

All forbidden vocab appearances are explicit references to
existing locks, NOT narrative use.
```

## 8. Self-review checklist (17/17)

```text
[x] docs/guides/PROPOSAL_USAGE_PLAYBOOK.md added
[x] docs/dev/PR_058_PROPOSAL_USAGE_PLAYBOOK.md added
[x] pytest 1183 passing
[x] ragcore source change 0 bytes
[x] new tests 0
[x] new example file 0
[x] new class / dataclass 0
[x] new public symbol 0
[x] new Engine behavior 0
[x] no Engine mutation flow in pseudocode
[x] no tool execution authorization in pseudocode
[x] no new decision layer
[x] PR57 §14 5 must-hold all honored (§5 cross-check)
[x] domain-neutral vocabulary honored
    (forbidden vocab appears only as explicit lock reference)
[x] LLMContextPacket / LLMProposal / ProposalSchema /
    ProposalValidator / OperatorDecision NOT promoted into
    ragcore
[x] PR59 NOT auto-entered
[x] external adapter NOT auto-entered
```

## 9. No-change verification

```text
pytest -q                                1183 passing (unchanged from PR57)
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
                                          PR58 itself contributes 0 lines
                                          to ragcore source
ragcore source cerberus mentions          0 (generic identity preserved)
external package imports in ragcore       0

adapter-specific symbols in ragcore.__all__:  none
ragcore type added in PR58:                    none
ragcore method surface change:                  none
new public symbol:                               0
new engine behavior:                             0
contract §51:                                    not added
runtime enforcement:                             0
adapter implementation:                          not included
new example file:                                0
new class / dataclass / TypedDict / type alias:  0

PR51 wrapper unchanged
PR53 validator unchanged
PR55 validator unchanged
PR56 validator unchanged
PR52 / PR54 / PR57 spec unchanged
all 6 existing test suites unchanged

operator-* / LLM*-Proposal* / Packet* symbol in ragcore source:  0
```

All framework invariants preserved.

## 10. What PR58 closed

```text
- PR49 ~ PR57 9-PR stack 의 end-to-end consumer 호출 흐름을
  단일 narrative 문서로 정리
- 9-step pipeline 명문화 (§4.1 ~ §4.9)
- inline Python pseudocode 로 호출 순서 demonstration
  (dict-only, 새 class/dataclass 0, 기존 4 example function
   재사용만)
- 10 common mistakes 모두 기존 anti-pattern lock 과
  cross-reference
- PR57 §14 5 must-hold 모두 §7 에 explicit cross-check
- domain-neutral 어휘 lock 엄격 honor
  (narrative 0 forbidden vocab; 허용 reference 만 OOS / 인용
   문맥에서)
- PR43-C ENGINE_METHOD_CALL_PLAYBOOK 의 자매 문서로 등록
  (engine method call playbook ↔ proposal usage playbook
   두 playbook 이 framework 의 read / write 양쪽 흐름 가이드)
```

## 11. What PR58 deliberately did NOT do

PR58 did NOT:

```text
- add any ragcore source / public symbol / Engine method
- add any test
- add any new example file
  (PR51 / PR53 / PR55 / PR56 의 4 example 모듈은 citation 만)
- define any new class / dataclass / TypedDict / type alias
- introduce LLMContextPacket / LLMProposal / ProposalSchema /
  ProposalValidator / OperatorDecision as a ragcore type
- modify PR51 wrapper / PR53 validator / PR55 validator /
  PR56 validator
- modify PR49 / PR50 / PR52 / PR54 / PR57 specs
- modify any other architecture / guide / contract document
- define an operator UI / approval mechanism / workflow engine
- specify operator authentication / authorization
- specify audit log shape (consumer's choice; only references
  PR57 §11 boundary)
- specify dashboard rendering or report layer
- specify a tool execution gate
- specify any downstream layer
- specify a RAG Context Builder / Tool Plan Validator /
  Adapter Translation Policy / Engine Call Plan /
  Report Wording Guard
- specify a Cerberus-side adapter implementation
- authorize tool execution
- mutate Engine state in any documented flow
- reinterpret effective_confidence as truth probability
- produce a final report verdict
- auto-schedule PR59 (violation collector) or any later PR
- auto-schedule a Cerberus adapter
- introduce contract §51
- introduce domain vocabulary into narrative
  (cerberus / vulnerability / scanner / exploit / ssh / cve /
   nmap / host / port / service / asset)
- add any new validator / decision layer
- create any new abstraction
```

## 12. Implementation footprint

Changed files (202 + 203):

```text
docs/guides/PROPOSAL_USAGE_PLAYBOOK.md              +628 lines (202차, NEW)
docs/dev/PR_058_PROPOSAL_USAGE_PLAYBOOK.md          this record (203차)
```

Unchanged:

```text
ragcore/engine.py                                    (no PR58-attributable change)
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
pyproject.toml
README.md
docs/README.md
docs/contracts/05_DATA_CONTRACT_MVP.md               (no §51 added)
docs/architecture/ENGINE_INTERNAL_MAP.md              (PR47)
docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md (PR49)
docs/architecture/ENGINE_READ_SURFACE_AUDIT.md       (PR50)
docs/architecture/LLM_CONTEXT_PACKET_SPEC.md         (PR52)
docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md       (PR54)
docs/architecture/OPERATOR_DECISION_BOUNDARY_SPEC.md (PR57)
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
docs/guides/* (existing guides untouched)
examples/probe/external_consumer_probe.py            (PR38-A)
examples/inspector/engine_inspector.py               (PR51, UNCHANGED)
examples/inspector/packet_validator.py               (PR53, UNCHANGED)
examples/proposal/proposal_schema.py                 (PR55, UNCHANGED)
examples/proposal/proposal_validator.py              (PR56, UNCHANGED)
tests/* (no PR58-attributable change)
all other tests / docs
```

Note on `ragcore.egg-info/`:

```text
ragcore.egg-info/ is an untracked build artifact present at the
PR58 baseline; it was NOT added to either 202차 or 203차 commit.
It is not part of the PR58 footprint.
```

No ragcore source change. No test change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change. All prior artifacts (PR47/49/50/51/52/53/54/55/56/57) preserved.

## 13. PR58 cycle

```text
202차  docs(guides) — Proposal Usage Playbook (+628 lines)    5e55875
203차  docs(dev) — PR58 record + ready + squash merge          this commit
```

Two-차수 cycle. No new tests. No source change. No new public API. No automatic next PR.

## 14. Pattern position recap

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
PR57    operator decision boundary spec    documentation-only (spec)
PR58    proposal usage playbook            documentation-only (guide, this)

All twenty (post-PR36-PKG):
  framework method surface frozen          ✓
  public observable behavior preserved      ✓
  no automatic next PR                      ✓
```

PR58 is the seventh doc-only artifact since PR48-A and the second playbook (after PR43-C).

## 15. PR49 ~ PR58 layered stack (updated)

```text
PR49 — Engine Read Surface Thaw Policy
PR50 — Engine Read Surface Audit (Conclusion A)
PR51 — Minimal Claim Read Query MVP (wrapper + 6 invariant tests)
PR52 — LLM Context Packet Spec
PR53 — Consumer Packet Validator MVP (validator + 7 invariant tests)
PR54 — Proposal Layer Bridge Spec
PR55 — Minimal LLM Proposal Schema MVP (validator + 11 invariant tests)
PR56 — Proposal Safety Validator MVP (validator + 14 invariant tests)
PR57 — Operator Decision Boundary Spec
PR58 — Proposal Usage Playbook (this PR)

stack:
  policy (PR49) → audit (PR50)
                → executable wrapper + tests (PR51)
                → consumer-side packet spec (PR52)
                → consumer-side packet validator + tests (PR53)
                → proposal layer bridge spec (PR54)
                → consumer-side proposal schema validator + tests (PR55)
                → consumer-side proposal safety validator + tests (PR56)
                → operator decision boundary spec (PR57)
                → consumer-side usage playbook (PR58, this)
                → [PR59 / Cerberus adapter — NOT entered]

The PR49 ~ PR58 stack now reads as:
  spec → spec → wrapper → spec → validator → spec → validator →
  validator → spec → playbook
```

PR58 closes the narrative gap — every prior layer's documentation is now stitched into one consumer-side call order.

## 16. Followup

```text
Possible follow-up directions (NOT auto-scheduled):

A. PR59 — Violation Collector
   small helper combining PR55 + PR56 outputs
   must honor PR57 §15 5 must-hold + naming policy
     safe:      collect_proposal_violations /
                gather_proposal_violations /
                join_proposal_violations
     forbidden: approve_proposal / authorize_proposal /
                validate_and_accept_proposal /
                accept_proposal / finalize_proposal

B. Cerberus adapter (separate repo)
   must honor PR57 §16 6 must-hold
   lives OUTSIDE intelligent-rag-framework repo

C. Extend PR56 with free-text semantic detection
   (high false-positive risk; intentionally not entered)

D. Stop here and let the framework wait

Each requires explicit user decision. PR58 does NOT
auto-schedule any of them.
```

## 17. Framework state (post-PR58)

```text
ragcore baseline:
  main:    5039e86 (pre-merge; new hash after squash merge)
  1183 tests passing (unchanged from PR57)
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
    - operator decision boundary spec (PR57)
  5 adapter guides
    - adapter policy guide (PR40)
    - retrieval translation guide (PR42)
    - engine method call playbook (PR43-C)
    - integration anti-patterns (PR44-D)
    - domain-neutral reference flow (PR45-E)
  1 proposal usage playbook
    - proposal usage playbook (PR58 — this)
  1 documentation map / reader entry point (PR46-B)
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

PR49 ~ PR58 layered stack status:
  judgment semantics                         frozen ✓
  read surface policy                        defined ✓ (PR49)
  read surface audit                         complete ✓ (PR50)
  executable wrapper + invariant lock        complete ✓ (PR51)
  consumer-side packet spec                  complete ✓ (PR52)
  consumer-side packet validator + tests     complete ✓ (PR53)
  proposal layer bridge spec                 complete ✓ (PR54)
  consumer-side proposal schema + tests      complete ✓ (PR55)
  consumer-side proposal safety + tests      complete ✓ (PR56)
  operator decision boundary spec            complete ✓ (PR57)
  consumer-side usage playbook                complete ✓ (PR58, this)
  PR59 / Cerberus adapter                     NOT entered

ragcore source change since PR36-PKG:  +66 lines (PR48-A banners only)
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 18. Closing meaning

```text
PR58 closes the proposal usage playbook.

The framework now has:
  read wrapper
  packet spec
  packet validator
  proposal bridge
  proposal shape validator
  proposal safety validator
  operator gate
  usage playbook

The playbook explains the flow.
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

The playbook shows how to use the proposal pipeline.
It does not create a new decision layer.

Validator pass means reviewable.
Operator acceptance means gated.
Neither means Engine truth.

LLMContextPacket / LLMProposal / ProposalSchema /
ProposalValidator / OperatorDecision remain NOT ragcore symbols.

PR59 (violation collector) and any external adapter remain
NOT automatically entered.
```

No automatic next-PR proposal. User decides direction.
