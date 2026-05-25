# PR52 — LLM Context Packet Spec

## Scope limitation (locked, user 2026-05-25)

```text
PR52 is a doc-only consumer-side packet specification.

It defines how the PR51 7-key packet may be consumed by
LLM-facing or external consumer layers without replacing
Engine judgment.
```

한국어:

```text
PR52 는 doc-only consumer-side packet spec 이다.

PR51 의 7-key packet 을 LLM-facing / external consumer layer
가 어떻게 소비해야 하는지 정의하되, Engine 판단을 대체하지
않도록 경계를 잠근다.
```

PR52 is the fourth (and final) PR in the PR49-PR52 read-surface roadmap. It writes consumer-side consumption rules for the 7 keys produced by the PR51 wrapper. PR52 does NOT add packet keys, does NOT modify the wrapper, does NOT introduce a ragcore symbol, and does NOT auto-schedule any further PR.

## 1. Baseline + cycle record

```text
main:    8eaec55  (PR51 merged)
tests:   1151 passing

187차:
  branch:  docs/llm-context-packet-spec
  commit:  97a3d83 docs(architecture): define LLM context packet spec
  file:    docs/architecture/LLM_CONTEXT_PACKET_SPEC.md
           (+660 lines, NEW)
  pytest:  1151 passing (unchanged)
  ragcore source change: 0 bytes
  Draft PR: #53 PR52: LLM Context Packet Spec

  Note: 187차 push was delayed by a transient SSH agent state
        (ssh-agent process alive but key dropped). User restored
        via `ssh-add ~/.ssh/id_ed25519` and push completed.
        The 187차 commit itself was unaffected.

188차 (this):
  docs(dev): record PR52 closing + ready + squash merge
  file:    docs/dev/PR_052_LLM_CONTEXT_PACKET_SPEC.md
```

## 2. What PR52 is / is not

```text
PR52 = LLM Context Packet Spec
성격   = doc-only consumer-side spec PR
         PR51 wrapper 의 7 packet keys 에 대한 consumer-side
         consumption 규칙 명문화
         packet 이 새 judgment engine 이 되지 않도록 경계 잠금
         PR49 ~ PR52 read-surface roadmap 의 closing 단계

성격 아님:
  - packet implementation
  - PR51 wrapper 수정
  - 새 packet key 추가
  - LLMContextPacket 등 ragcore type 추가
  - 외부 LLM 판단 엔진 설계
  - PR53+ 자동 진입
  - contract §51 신설
  - source / test 변경
```

## 3. Spec document structure (10 sections)

`docs/architecture/LLM_CONTEXT_PACKET_SPEC.md` — 660 lines, 10 sections:

```text
§0   Scope limitation                       doc-only, consumer-side
§1   Core statement                          "The packet informs the
                                              consumer. It does not
                                              replace Engine judgment."
§2   Source baseline                         PR49 / PR50 / PR51 inheritance
§3   Packet shape                            7 keys locked from PR51
§4   Key semantics                            uniform 6-field per key (7 keys)
       4.1 claim
       4.2 effective_confidence
       4.3 supporting_evidence
       4.4 contradictions
       4.5 active_contradictions
       4.6 unresolved_gaps
       4.7 lifecycle_history
§5   Forbidden readings                      F1 ~ F13 cross-cutting summary
§6   LLM-facing translation boundary        allowed / forbidden phrasings +
                                              proposal-layer flow
§7   Consumer responsibility                 serialization / cache /
                                              Validator
§8   Ragcore symbol boundary                LLMContextPacket NOT ragcore
                                              symbol
§9   PR52 Exit criteria                      15-item checklist
§10  Closing meaning
```

10 sections. 660 lines. Zero ragcore source change. Zero new tests.

## 4. Per-key uniform 6-field structure (§4)

Each of the 7 packet keys uses the same 6-field structure:

```text
- Source method               — Engine public method that produced the value
- What it represents          — meaning at Engine level
- Consumer-side allowed       — readings that preserve §1
- Consumer-side forbidden     — readings that violate §1
- LLM-facing translation hint — how to surface the value safely
- Related prior guard         — PR41 / PR42 / PR43-C / PR44-D references
```

Per-key Source method mapping (1:1 with PR51 wrapper):

```text
claim                  ← engine.get_claim(claim_id)
effective_confidence    ← engine.compute_effective_confidence(claim_id)
supporting_evidence    ← engine.evidences_for_claim(claim_id)
contradictions         ← engine.contradictions_for_claim(claim_id)
active_contradictions  ← engine.active_contradictions_for_claim(claim_id)
unresolved_gaps        ← engine.gaps_for_claim(claim_id)
                         filtered by gap_resolution(gap.id) is None
lifecycle_history      ← engine.claim_lifecycle_history(claim_id)
```

## 5. 13 forbidden readings (§5)

All mapped to existing anti-pattern locks:

```text
F1   effective_confidence as truth probability        AP-CF-1 / AP-X-4
F2   effective_confidence as judgment replacement     PR43-C §4.7
F3   evidence.strength piped to LLM as probability    AP-X-1
F4   evidence.strength composed into "claim prob"     PR43-C §4.7
F5   contradictions non-empty → auto refutation       AP-CT-1
F6   contradictions empty → "claim is true"           PR43-C §4.6
F7   unresolved_gaps → refutation                     AP-G-1
F8   unresolved_gaps empty → "fully verified"         PR43-C §4.4
F9   empty lifecycle_history → "unverified"           PR43-C §4.6
F10  Claim.status renamed to verdict label            PR43-C §4.3
F11  base_confidence as truth probability             PR43-C §4.3
F12  static threshold as if blessed by ragcore        AP-CF-2
F13  raw_ref_id resolved INTO Engine                  PR42 §13 / AP-E-1
```

## 6. LLM-facing translation boundary (§6)

```text
Allowed phrasings:
  - "engine_confidence: 0.87"
  - "computed signal: 0.87"
  - "effective_confidence (decision-support): 0.87"
  - lifecycle phase as opaque label
  - opaque ids for evidence / gap / contradiction

Forbidden phrasings:
  - "P(true) = 0.87"
  - "probability of X: 87%"
  - "verified true with 0.87 confidence"
  - "the engine's verdict"
  - any framing where packet IS decision rather than informing one

Prompt template rule:
  - always include decision-support disclaimer
  - never ask LLM to compute "final probability" or "final verdict"
  - LLM produces proposals (evidence / gap / contradiction / tool)
  - proposals flow: LLM → Validator → Adapter → Engine public API
    (per direction_rag_framework_proposal_layer §16 #8 / #9)
```

## 7. Ragcore symbol boundary (§8)

```text
"LLM Context Packet" is a consumer-side concept.
"LLM Context Packet" is NOT a ragcore symbol.
"LLM Context Packet" must NOT appear in ragcore.__all__.
"LLM Context Packet" must NOT appear as a class / dataclass /
TypedDict / type alias inside ragcore source.

If a future PR proposes LLMContextPacket as a ragcore type:
  - it must first revoke §8 lock with explicit user authorization
  - it must satisfy PR50 §8.3 conditions (α/β/γ/δ/ε) in full
  - it must honor PR44-D AP-X-7 (adapter-specific symbol
    promotion) and AP-X-6 (domain vocabulary intrusion)
  - it must clear PR49 §8 PR51 Guard (a) (b) (c)
```

## 8. Self-review checklist (15/15)

```text
[x] ragcore/engine.py 변경 0
[x] ragcore/types.py 변경 0
[x] ragcore/__init__.py 변경 0
[x] ragcore/rule_output.py 변경 0
[x] ragcore.__all__ 48 symbols 유지
[x] Engine public methods 40 유지
[x] new public symbol 0
[x] new engine behavior 0
[x] contract §51 추가 0
[x] LLMContextPacket ragcore symbol 추가 0
[x] PR51 wrapper 수정 0
[x] packet key 추가 0
[x] test change 0
[x] pytest 1151 passing
[x] PR49 ~ PR52 roadmap closed; automatic next PR 없음
```

## 9. No-change verification

```text
pytest -q                                1151 passing (unchanged from PR51)
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
                                          PR52 itself contributes 0 lines
                                          to ragcore source
ragcore source cerberus mentions          0 (generic identity preserved)
external package imports in ragcore       0

adapter-specific symbols in ragcore.__all__:  none
ragcore type added in PR52:                    none
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

LLMContextPacket in ragcore source:              0 (NOT promoted)
```

All framework invariants preserved.

## 10. What PR52 closed

```text
- PR51 의 7 packet keys 에 대한 consumer-side consumption 규칙
  명문화 (per-key 6-field uniform structure)
- 13 forbidden readings (F1 ~ F13) 의 cross-cutting summary 박음
  모두 기존 anti-pattern (PR41 §50.9/10 / PR42 §13 /
  PR43-C §4.x / PR44-D AP-* / direction_proposal_layer §16) 와
  cross-reference
- LLM-facing translation boundary (allowed vs forbidden phrasings,
  prompt template rule, proposal-layer flow) 박음
- Consumer responsibility 명문화 (serialization / cache /
  Validator layer / 도메인 라벨 매핑)
- Ragcore symbol boundary (LLMContextPacket NOT ragcore symbol)
  의 명시 lock — 향후 promotion 시도의 진입 조건 박음
- PR49 § 8 PR51 Guard (a) (b) (c) 가 read-surface roadmap 의
  symbol boundary 에도 적용됨을 명시
- PR49 ~ PR52 read-surface roadmap 의 closing 단계 완료
```

## 11. What PR52 deliberately did NOT do

PR52 did NOT:

```text
- add any read method
- add any public symbol to ragcore.__all__
- modify any ragcore source file
- modify the PR51 wrapper
  (examples/inspector/engine_inspector.py 미수정)
- modify the PR51 invariant tests
  (tests/test_external_engine_inspector.py 미수정)
- expand the packet shape beyond PR51's 7 keys
- introduce LLMContextPacket / RAGContext / ToolPlan /
  EngineContextPacket / LLMProposal as a ragcore type
- introduce a packet dataclass / TypedDict / type alias
- modify snapshot schema_version
- modify any of the 18 snapshot top-level keys
- modify lifecycle transition rules
- modify effective_confidence formula
- modify modifier value / order / saturation
- introduce contract §51
- auto-schedule any PR53+
- introduce domain vocabulary
  (cerberus / vulnerability / scanner / SSH / CVE / nmap /
   host / port / service / asset)
- introduce runtime enforcement
- introduce adapter implementation
```

## 12. Implementation footprint

Changed files (187 + 188):

```text
docs/architecture/LLM_CONTEXT_PACKET_SPEC.md     +660 lines (187차, NEW)
docs/dev/PR_052_LLM_CONTEXT_PACKET_SPEC.md       this record (188차)
```

Unchanged:

```text
ragcore/engine.py                                (no PR52-attributable change)
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
pyproject.toml
README.md
docs/README.md
docs/contracts/05_DATA_CONTRACT_MVP.md           (no §51 added)
docs/architecture/ENGINE_INTERNAL_MAP.md          (PR47 artifact)
docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md   (PR49 artifact)
docs/architecture/ENGINE_READ_SURFACE_AUDIT.md         (PR50 artifact)
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
docs/guides/ADAPTER_POLICY_GUIDE.md
docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md
docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md
docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md
docs/guides/DOMAIN_NEUTRAL_REFERENCE_FLOW.md
examples/probe/external_consumer_probe.py        (PR38-A artifact)
examples/inspector/engine_inspector.py           (PR51 artifact, UNCHANGED)
tests/test_external_adapter_simulation.py        (PR41 artifact)
tests/test_engine_method_call_playbook_usage.py  (PR43-C 168차 artifact)
tests/test_external_engine_inspector.py          (PR51 artifact, UNCHANGED)
all other tests / docs
```

Note on `ragcore.egg-info/`:

```text
ragcore.egg-info/ is an untracked build artifact present at the
PR52 baseline; it was NOT added to either 187차 or 188차 commit.
It is not part of the PR52 footprint.
```

No ragcore source change. No test change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change. No PR51 wrapper/test change.

## 13. PR52 cycle

```text
187차  docs(architecture) — LLM Context Packet Spec (+660 lines)   97a3d83
188차  docs(dev) — PR52 record + ready + squash merge               this commit
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
PR52    LLM context packet spec            documentation-only (spec, this)

All fourteen (post-PR36-PKG):
  framework method surface frozen          ✓
  public observable behavior preserved      ✓
  no automatic next PR                      ✓
```

## 15. PR49 ~ PR52 read-surface roadmap closure

```text
PR49 — Engine Read Surface Thaw Policy
       defined freeze Sense A (judgment semantics) vs
       Sense B (total Engine) distinction; locked Sense A only.
       Established §5 read-only definition (6 must-hold) and
       §8 PR51 Guard (3 conditions a/b/c).

PR50 — Engine Read Surface Audit
       Classified 40 public methods (read-only 19 / mutation 14 /
       lifecycle 6 / rule-meta 5 / restore 1). Verified all 19
       read-only candidates pass PR49 §5 6 must-hold.
       Concluded "Conclusion A: external wrapper sufficient",
       no ragcore source change required.

PR51 — Minimal Claim Read Query MVP
       Implemented examples/inspector/engine_inspector.py
       (single function, 7-key packet, uses 8 of 19 read-only
       methods). Added 6 invariant tests with AST-based source
       check pattern. ragcore source change 0. 1145 → 1151 tests.

PR52 — LLM Context Packet Spec  (this)
       Wrote consumer-side consumption rules: per-key 6-field
       semantics, 13 forbidden readings, LLM-facing translation
       boundary, ragcore symbol boundary lock. No source change.
       Packet shape unchanged from PR51.

Roadmap closure:
  policy (PR49) → audit (PR50) → executable wrapper + tests (PR51)
                                 → consumer-side spec (PR52)
                                 → CLOSED

No automatic next PR. User decides direction.
```

## 16. Framework state (post-PR52)

```text
ragcore baseline:
  main:    8eaec55 (pre-merge; new hash after squash merge)
  1151 tests passing (unchanged from PR51)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  3 architecture audits
    - compatibility matrix (PR39)
    - engine internal map (PR47)
    - engine read surface audit (PR50)
  2 architecture policy/spec
    - engine read surface thaw policy (PR49)
    - LLM context packet spec (PR52 — this)
  5 adapter guides
  1 documentation map / reader entry point
  2 external examples
    - examples/probe/external_consumer_probe.py (PR38-A)
    - examples/inspector/engine_inspector.py    (PR51)
  3 executable simulation/usage test suites
    - test_external_adapter_simulation.py       (PR41, 18 tests)
    - test_engine_method_call_playbook_usage.py (PR43-C 168차, 12 tests)
    - test_external_engine_inspector.py         (PR51 185차, 6 tests)
  1 behavior-preserving refactor commit on engine.py
    (PR48-A comment-only banners)

Read surface roadmap status:
  judgment semantics                         frozen ✓
  read surface policy                        defined ✓ (PR49)
  read surface audit                         complete ✓ (PR50)
  executable wrapper + invariant lock        complete ✓ (PR51)
  consumer-side packet spec                  complete ✓ (PR52, this)
  PR49 ~ PR52 roadmap                        CLOSED ✓

ragcore source change since PR36-PKG:  +66 lines (PR48-A banners only)
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 17. Closing meaning

```text
PR52 closes as a doc-only LLM Context Packet Spec.

The packet informs the consumer.
It does not replace Engine judgment.

LLM Context Packet remains a consumer-side concept,
not a ragcore symbol.
```

Locked closing sentences:

```text
PR52 는 doc-only LLM Context Packet Spec 으로 종료한다.

packet 은 consumer 에게 정보를 제공한다.
Engine 판단을 대체하지 않는다.

LLM Context Packet 은 consumer-side 개념이며 ragcore symbol 이
아니다.

PR49 ~ PR52 read-surface roadmap 이 닫혔다.
다음 PR 은 자동 진입 없음.
```

No automatic next-PR proposal. User decides direction.
