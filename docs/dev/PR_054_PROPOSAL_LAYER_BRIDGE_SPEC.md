# PR54 — Proposal Layer Bridge Spec

## Scope limitation (locked, user 2026-05-25)

```text
PR54 is a doc-only proposal layer bridge spec.

It defines the boundary after PR51 packet inspection and PR53
packet validation, before any PR55 proposal schema code.

The proposal layer suggests what to inspect next.
It does not decide Engine truth.
```

한국어:

```text
PR54 는 proposal layer 의 책임 경계를 문서로 잠근 PR 이다.

proposal 은 다음 조사 후보를 구조화하지만, Engine 판단, tool
실행, Engine 변조, final report verdict 로 넘어가지 않는다.
```

PR54 is the sixth PR after PR48-A and the seventh doc-only contribution since PR47. It writes the bridge between PR53 (consumer-side packet validator) and any future proposal-related work. No ragcore source byte changes. No tests. No public symbols. PR55 (proposal schema MVP) is NOT auto-entered.

## 1. Baseline + cycle record

```text
main:    e4aad04  (PR53 merged)
tests:   1158 passing

192차:
  branch:  docs/proposal-layer-bridge-spec
  commit:  47df3b8 docs(architecture): define proposal layer
                                       bridge spec
  file:    docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md
           (+553 lines, NEW)
  pytest:  1158 passing (unchanged)
  ragcore source change: 0 bytes
  Draft PR: #55 PR54: Proposal Layer Bridge Spec

193차 (this):
  docs(dev): record PR54 closing + ready + squash merge
  file:    docs/dev/PR_054_PROPOSAL_LAYER_BRIDGE_SPEC.md
```

## 2. What PR54 is / is not

```text
PR54 = Proposal Layer Bridge Spec
성격   = doc-only architecture spec
         PR53 (validated packet) 와 human / operator decision
         사이의 proposal layer 위치 / 책임 / 경계 정의
         PR55 handoff boundary (5 must-hold) 박음
         PR55 자동 진입 없음

성격 아님:
  - proposal schema implementation
  - proposal validator implementation
  - tool plan / RAG context builder / adapter call
  - report wording layer
  - ragcore extension
  - LLMProposal / ProposalSchema 등 ragcore symbol 추가
  - PR55 자동 진입
  - human / operator decision UI 정의
  - 새 test 또는 새 source
```

## 3. Spec document structure (15 sections)

`docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md` — 553 lines, 15 sections:

```text
§0   Scope limitation                       doc-only spec
§1   Purpose                                 PR49 ~ PR53 위에서 빠진
                                              layer 정의
§2   Baseline                                main e4aad04 / 1158 passing
§3   Core boundary statement                 "The proposal layer
                                              suggests what to inspect
                                              next. It does not decide
                                              Engine truth."
§4   End-to-end flow                         7-step layered flow,
                                              downstream OOS
§5   What a proposal IS                      5 conceptual categories (A~E)
                                              no field freeze
                                              "action" wording 피함
§6   What a proposal IS NOT                  7 explicit exclusions
§7   Relationship to PR51 packet             packet 은 input domain;
                                              proposal 은 read-only
                                              pointer 만
§8   Relationship to PR53 packet validator   PR53 vs PR54 validator
                                              분리 명문화
§9   Allowed proposal categories             reader guidance, not contract
§10  Forbidden proposal readings             P1~P8 (all mapped to
                                              PR44-D / PR52 / PR43-C)
§11  Human / operator decision boundary      human acceptance = gating
                                              event for any downstream
§12  PR55 handoff boundary                   5 must-hold entry conditions
§13  Non-goals                                explicit OOS list
§14  Exit criteria                            18-item checklist
     Closing meaning
```

15 sections. 553 lines. Zero ragcore source change. Zero new tests.

## 4. Core boundary statement

```text
The proposal layer suggests what to inspect next.
It does not decide Engine truth.

proposal layer 는 다음에 무엇을 살펴볼지 제안한다.
Engine 의 진실을 결정하지 않는다.
```

The single sentence governing every per-layer rule in the spec.

## 5. 6 user-lock decisions recorded

User 2026-05-25 locked 6 entry decisions; PR54 spec implements each:

```text
1. PR54 cover range
   → proposal boundary only
   → RAG Context Builder / Tool Plan Validator / Adapter
     Translation Policy / Engine Call Plan / Report Wording
     Guard / Cerberus implementation 모두 OOS
   → spec §13 Non-goals 에 명시

2. proposal schema 언급 깊이
   → conceptual list만 (5 categories A~E)
   → PR55 schema field freeze 금지
   → "action" wording 피함; "proposal item / proposal note /
     inspection question / candidate follow-up" 추천
   → spec §5 / §9 에 반영

3. PR55 handoff boundary
   → 옵션 A: 5 must-hold entry conditions 박음
       (1) no ragcore source modification
       (2) no ragcore public symbol addition
       (3) no proposal → Engine judgment auto-mutation
       (4) no proposal → tool execution authorization
       (5) human / operator decision boundary preserved
   → 추가 honor: PR47 §3 / PR49 §5 / PR52 §5 / PR52 §8 /
                  PR53 false-positive prevention
   → spec §12 에 반영

4. ragcore symbol boundary
   → LLMProposal / ProposalSchema / ProposalDraft /
     ProposalValidator 모두 NOT ragcore type
   → NOT in ragcore.__all__ / NOT inside ragcore source
   → Future promotion default-forbidden;
     baseline thaw 절차 필요
   → spec §6 / §13 에 반영

5. proposal validator vs packet validator (PR53) 분리
   → PR53 = "did consumer misread packet?"
   → PR54 proposal validator (conceptual) =
     "did proposal cross out of suggestion-only role?"
   → 둘 다 structural; neither LLM phrasing inference;
     neither Engine mutation monitor
   → spec §8 에 반영

6. cycle
   → 옵션 A: 192 docs(architecture) + 193 docs(dev)
   → PR42 / PR49 / PR52 pattern 과 일관
```

## 6. Self-review checklist (15/15)

```text
[x] docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md added
[x] docs/dev/PR_054_PROPOSAL_LAYER_BRIDGE_SPEC.md added
[x] ragcore source change 0 bytes
[x] tests remain 1158 passing
[x] new tests 0
[x] new public symbol 0
[x] Engine public method addition 0
[x] proposal schema code 0
[x] proposal validator code 0
[x] LLMProposal not promoted into ragcore
[x] ProposalSchema not promoted into ragcore
[x] ProposalValidator not promoted into ragcore
[x] PR55 handoff boundary defined (spec §12)
[x] PR55 not auto-entered
[x] human / operator decision remains final gate (spec §11)
```

## 7. No-change verification

```text
pytest -q                                1158 passing (unchanged from PR53)
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
                                          PR54 itself contributes 0 lines
                                          to ragcore source
ragcore source cerberus mentions          0 (generic identity preserved)
external package imports in ragcore       0

adapter-specific symbols in ragcore.__all__:  none
ragcore type added in PR54:                    none
ragcore method surface change:                  none
new tests:                                       0
new public symbol:                               0
new engine behavior:                             0
contract §51:                                    not added
runtime enforcement:                             0
adapter implementation:                          not included

PR51 wrapper unchanged:
  examples/inspector/engine_inspector.py  unchanged
  tests/test_external_engine_inspector.py  unchanged
PR53 validator unchanged:
  examples/inspector/packet_validator.py  unchanged
  tests/test_packet_validator.py           unchanged
PR52 spec unchanged:
  docs/architecture/LLM_CONTEXT_PACKET_SPEC.md  unchanged

LLMProposal / ProposalSchema / ProposalDraft / ProposalValidator
  in ragcore source:                              0 (NOT promoted)
```

All framework invariants preserved.

## 8. What PR54 closed

```text
- PR53 (validated packet) 과 human / operator decision 사이의
  proposal layer 위치 명문화
- proposal 의 정의 (§5) — 5 conceptual categories
- proposal 의 반정의 (§6) — 7 explicit exclusions
- PR51 packet 과의 관계 (§7) — packet 은 input domain,
  proposal 은 read-only pointer
- PR53 packet validator 와 PR54 conceptual proposal validator
  의 명확한 분리 (§8)
- 8 forbidden proposal readings (§10) 모두 기존 anti-pattern
  (PR44-D AP-CF-1 / AP-CT-1 / AP-X-4 / AP-L-1 / AP-E-1 / AP-CF-2
   / AP-X-6 / PR52 §5 F1 / F2 / F10 / F12 / F13 / PR43-C §4.6 /
   PR45-E §3) 와 cross-reference
- human / operator decision boundary (§11) — gating event
  정의
- PR55 handoff boundary (§12) — 5 must-hold entry conditions
  + PR47 §3 / PR49 §5 / PR52 §5 / PR52 §8 / PR53 false-positive
  prevention 추가 honor 요구
- PR55 자동 진입 없음 lock
- Ragcore symbol boundary lock 재확인 (PR52 §8 mirror)
- proposal-related code (schema / validator / tool plan /
  adapter / report) 모두 PR54 OOS
```

## 9. What PR54 deliberately did NOT do

PR54 did NOT:

```text
- implement proposal schema (PR55 책임)
- implement proposal validator (PR55 또는 별도 PR)
- modify any ragcore source file
- add any public symbol to ragcore.__all__
- add LLMProposal / ProposalSchema / ProposalDraft /
  ProposalValidator as a ragcore type
- modify PR51 wrapper (examples/inspector/engine_inspector.py)
- modify PR53 validator (examples/inspector/packet_validator.py)
- modify PR51 / PR53 test files
- modify PR52 spec (docs/architecture/LLM_CONTEXT_PACKET_SPEC.md)
- modify any other architecture / guide / contract document
- extend into RAG Context Builder
- extend into Tool Plan Validator
- extend into Adapter Translation Policy
- extend into Engine Call Plan
- extend into Report Wording Guard
- extend into Cerberus-side implementation
- introduce contract §51
- introduce domain vocabulary
  (cerberus / vulnerability / scanner / exploit / ssh / cve /
   nmap / host / port / service / asset)
- introduce runtime enforcement
- introduce adapter implementation
- auto-schedule PR55 or any later PR
- define human / operator UI or approval mechanism
- specify report wording or report templates
```

## 10. Implementation footprint

Changed files (192 + 193):

```text
docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md     +553 lines (192차, NEW)
docs/dev/PR_054_PROPOSAL_LAYER_BRIDGE_SPEC.md       this record (193차)
```

Unchanged:

```text
ragcore/engine.py                                    (no PR54-attributable change)
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
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
docs/guides/*
examples/probe/external_consumer_probe.py            (PR38-A)
examples/inspector/engine_inspector.py               (PR51, UNCHANGED)
examples/inspector/packet_validator.py               (PR53, UNCHANGED)
tests/*                                               (no PR54-attributable change)
all other tests / docs
```

Note on `ragcore.egg-info/`:

```text
ragcore.egg-info/ is an untracked build artifact present at the
PR54 baseline; it was NOT added to either 192차 or 193차 commit.
It is not part of the PR54 footprint.
```

No ragcore source change. No test change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change. PR51 wrapper / PR53 validator / PR52 spec all unchanged.

## 11. PR54 cycle

```text
192차  docs(architecture) — Proposal Layer Bridge Spec (+553 lines)   47df3b8
193차  docs(dev) — PR54 record + ready + squash merge                  this commit
```

Two-차수 cycle. No new tests. No source change. No new public API. No automatic next PR.

## 12. Pattern position recap

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
PR54    proposal layer bridge spec         documentation-only (spec, this)

All sixteen (post-PR36-PKG):
  framework method surface frozen          ✓
  public observable behavior preserved      ✓
  no automatic next PR                      ✓
```

## 13. PR49 ~ PR54 layered stack (updated)

```text
PR49 — Engine Read Surface Thaw Policy
       freeze Sense A only; §5 read-only 6 must-hold;
       §8 PR51 Guard 3 conditions

PR50 — Engine Read Surface Audit
       40 methods 분류; Conclusion A: external wrapper sufficient

PR51 — Minimal Claim Read Query MVP
       examples/inspector/engine_inspector.py + 6 invariant tests
       7-key packet via 8 of 19 read-only methods

PR52 — LLM Context Packet Spec
       per-key 6-field × 7 keys + 13 forbidden readings (F1~F13)
       LLM-facing translation boundary + ragcore symbol boundary lock

PR53 — Consumer Packet Validator MVP
       examples/inspector/packet_validator.py + 7 invariant tests
       6 of 13 forbidden readings structurally detected
       F5/F7 REFUTED-skip false-positive prevention

PR54 — Proposal Layer Bridge Spec  (this PR)
       proposal layer 위치 / 책임 / 경계 정의
       proposal validator conceptual; PR55 handoff 5 must-hold

Stack status:
  policy (PR49) → audit (PR50)
                → executable wrapper + tests (PR51)
                → consumer-side spec (PR52)
                → consumer-side validator + tests (PR53)
                → proposal layer bridge spec (PR54, this)
                → [PR55 proposal schema MVP — NOT auto-entered]
```

## 14. Followup — PR55 (NOT auto-scheduled)

```text
PR55 — Consumer-side proposal schema MVP
       type:   consumer-side example or spec (separately decided)
       scope:  smallest schema that lets consumers structure
               LLM proposal drafts; optionally a structural
               proposal validator paralleling PR53's pattern
       location: examples/inspector/ or examples/proposal/ or
                 separate consumer repo
       requires (PR54 §12 entry conditions, ALL must hold):
         1. PR55 must not modify ragcore source
         2. PR55 must not add ragcore public symbols
         3. PR55 must not turn proposals into Engine judgments
         4. PR55 must not authorize tool execution
         5. PR55 must keep human / operator decision as final
            boundary
       additional honor:
         - PR47 §3 do-not-touch boundary
         - PR49 §5 read-only definition
         - PR52 §5 forbidden readings
         - PR52 §8 ragcore symbol boundary
         - PR53 false-positive prevention philosophy

Alternative directions (also NOT auto-scheduled):
  - extend PR53 packet validator coverage to additional F_ids
  - Cerberus-side adapter implementation (separate repo)
  - human / operator UI / approval mechanism spec
  - stop here and let the framework wait
```

PR54 explicitly does not schedule any of the above. Each requires explicit user decision.

## 15. Framework state (post-PR54)

```text
ragcore baseline:
  main:    e4aad04 (pre-merge; new hash after squash merge)
  1158 tests passing (unchanged from PR53)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  3 architecture audits
    - compatibility matrix (PR39)
    - engine internal map (PR47)
    - engine read surface audit (PR50)
  3 architecture policy / spec
    - engine read surface thaw policy (PR49)
    - LLM context packet spec (PR52)
    - proposal layer bridge spec (PR54 — this)
  5 adapter guides
  1 documentation map / reader entry point
  3 external examples
    - examples/probe/external_consumer_probe.py     (PR38-A)
    - examples/inspector/engine_inspector.py        (PR51)
    - examples/inspector/packet_validator.py        (PR53)
  4 executable simulation / usage / validator test suites
    - test_external_adapter_simulation.py           (PR41, 18 tests)
    - test_engine_method_call_playbook_usage.py     (PR43-C 168차, 12 tests)
    - test_external_engine_inspector.py             (PR51 185차, 6 tests)
    - test_packet_validator.py                       (PR53 190차, 7 tests)
  1 behavior-preserving refactor commit on engine.py
    (PR48-A comment-only banners)

PR49 ~ PR54 layered stack status:
  judgment semantics                         frozen ✓
  read surface policy                        defined ✓ (PR49)
  read surface audit                         complete ✓ (PR50)
  executable wrapper + invariant lock        complete ✓ (PR51)
  consumer-side packet spec                  complete ✓ (PR52)
  consumer-side validator + tests            complete ✓ (PR53)
  proposal layer bridge spec                 complete ✓ (PR54, this)
  PR55 proposal schema MVP                   NOT entered

ragcore source change since PR36-PKG:  +66 lines (PR48-A banners only)
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 16. Closing meaning

```text
PR54 closes the proposal layer bridge boundary.

The proposal layer is now positioned between validated packet
reading and future consumer-side proposal schema work.

It remains suggestion-only.
It does not decide Engine truth.
```

Locked closing sentences:

```text
PR54 는 doc-only proposal layer bridge spec 으로 종료한다.

proposal layer 는 다음에 무엇을 살펴볼지 제안한다.
Engine 의 진실을 결정하지 않는다.

proposal 은 판단도 실행도 변조도 아니다.
proposal 은 다음 조사 후보를 구조화한다.

human / operator 의 결정이 downstream 의 게이트다.
PR55 는 자동 진입하지 않는다.
```

No automatic next-PR proposal. User decides direction.
