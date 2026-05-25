# PR51 — Minimal Claim Read Query MVP

## Scope limitation (locked, user 2026-05-25)

```text
PR51 is not a ragcore read API PR.

It proves that a minimal claim read query can be assembled
outside ragcore through an external inspector using only existing
public Engine read methods.
```

한국어:

```text
PR51 은 ragcore read API PR 이 아니다.

기존 public Engine read method 만 사용해 ragcore 밖의 external
inspector 에서 최소 claim read query 를 조립할 수 있음을 증명한
PR 이다.
```

PR51 is the third PR in the PR49-PR52 read-surface roadmap. It honors PR49 §8 PR51 Guard 1순위 path (external EngineInspector wrapper, ragcore source change 0). PR50 §6 audit pseudocode is now executable and lock-tested.

## 1. Baseline + cycle record

```text
main:    d1e4975  (PR50 merged)
tests:   1145 passing

184차:
  branch:  feat/external-engine-inspector
  commit:  513a3c1 feat(examples): add external engine inspector
  file:    examples/inspector/engine_inspector.py (+116 lines, NEW)
  pytest:  1145 passing (unchanged)
  ragcore source change: 0 bytes

185차:
  commit:  52d2ef2 test(examples): lock external inspector
                                    read-only behavior
  file:    tests/test_external_engine_inspector.py (+255 lines, NEW)
  pytest:  1151 passing (1145 + 6 new tests)
  ragcore source change: 0 bytes

186차 (this):
  docs(dev): record PR51 closing + ready + squash merge
  file:    docs/dev/PR_051_MINIMAL_CLAIM_READ_QUERY_MVP.md
```

## 2. What PR51 is / is not

```text
PR51 = Minimal Claim Read Query MVP (external engine inspector)
성격   = executable proof PR
         PR50 §6 audit pseudocode → executable wrapper
         PR49 §8 PR51 Guard 1순위 path honored
         consumer-side example, NOT a ragcore feature

성격 아님:
  - ragcore read API addition
  - new Engine public method
  - LLMContextPacket / RAGContext / ToolPlan / LLMProposal
    public symbol 추가
  - packet shape contract (PR52 책임)
  - adapter implementation
  - Cerberus integration
  - LLM-facing verdict / risk / probability generation
  - PR52 자동 진입
```

## 3. Wrapper implementation summary (184차)

`examples/inspector/engine_inspector.py` — single function, 116 lines.

```python
def build_engine_context_packet(engine: Engine, claim_id: int) -> dict[str, Any]
```

Returns a dict with 7 minimal fields (user lock):

```text
claim                  → Claim object              (get_claim)
effective_confidence    → ScoreValue                (compute_effective_confidence)
supporting_evidence    → tuple of Evidence         (evidences_for_claim)
contradictions         → tuple of evidence_id ints (contradictions_for_claim)
active_contradictions  → tuple of evidence_id ints (active_contradictions_for_claim)
unresolved_gaps        → tuple of Gap              (gaps_for_claim
                                                     filtered by gap_resolution is None)
lifecycle_history      → tuple of ClaimLifecycleEvent (claim_lifecycle_history)
```

Public methods used (8 of 19 read-only — minimal subset):

```text
get_claim
compute_effective_confidence
evidences_for_claim
contradictions_for_claim
active_contradictions_for_claim
gaps_for_claim
gap_resolution
claim_lifecycle_history
```

Other 11 read-only methods (get_entity / get_observation / get_evidence / get_gap / get_relation / get_rule / get_rule_stats / evidence_freshness / active_contradictions_by_freshness / resolved_contradictions_for_claim / to_snapshot) are not used by this MVP — future expansion is possible without touching ragcore.

## 4. Test invariant summary (185차)

`tests/test_external_engine_inspector.py` — class TestExternalEngineInspector, 6 test methods, 255 lines.

```text
1. test_packet_returns_exactly_seven_expected_keys
   asserts frozenset(packet.keys()) == 7 expected keys

2. test_packet_contains_no_llm_facing_or_forbidden_keys
   9 forbidden keys checked absent:
     verdict / risk / probability / proposal / tool_plan /
     tool_recommendation / summary_score / risk_label /
     vulnerability_probability

3. test_engine_state_unchanged_after_inspection
   to_snapshot() before == to_snapshot() after
   compute_effective_confidence(claim_id) before == after

4. test_ragcore_all_unchanged_at_48_symbols
   PR43-C 168차 invariant re-asserted from inspector test
   boundary

5. test_inspector_source_uses_no_private_attribute_access
   AST-based check on examples/inspector/engine_inspector.py
   excludes docstring / comment / string literal
   catches real obj._attr patterns in code only

6. test_inspector_source_has_no_forbidden_domain_vocabulary
   AST-based identifier collection
   11 forbidden domain words checked absent from identifiers:
     cerberus / vulnerability / scanner / exploit / ssh /
     cve / nmap / host / port / service / asset
   (PR44-D §5.6 / PR45-E §3 mirror)
```

AST-based source check rationale:

```text
The inspector module docstring intentionally lists forbidden
words (cerberus / vulnerability / scanner / exploit) and forbidden
private attribute patterns (engine._claims / engine._evidence /
engine._gaps) as reader-facing reference material — explaining
what the wrapper deliberately avoids.

A naive substring grep would flag these intended reference
mentions as violations. The AST-based check restricts itself to
actual Python identifiers and attribute accesses, leaving
docstring / comment content untouched.

This mirrors the test-local helper pattern from PR41 simulation
and PR43-C 168차 invariant tests.
```

Test loading:

```text
examples/inspector/engine_inspector.py loaded via importlib
no sys.path pollution
no examples/__init__.py required
```

## 5. Self-review checklist (16/16)

```text
[x] ragcore/engine.py 변경 0
[x] ragcore/types.py 변경 0
[x] ragcore/__init__.py 변경 0
[x] ragcore/rule_output.py 변경 0
[x] ragcore.__all__ 48 symbols 유지
[x] Engine public methods 40 유지
[x] new public symbol 0
[x] new engine behavior 0
[x] snapshot schema_version 변경 0
[x] lifecycle transition 변경 0
[x] effective_confidence formula 변경 0
[x] modifier 의미 / 값 / 순서 변경 0
[x] private attribute access 0
       (test #5 AST-based check passes)
[x] forbidden domain vocabulary 0 in identifiers
       (test #6 AST-based check passes)
[x] LLM-facing verdict / risk / probability 가공 0
       (test #2 forbidden-key check passes;
        packet contains raw Engine-owned state only)
[x] packet shape freeze 0 — PR52 책임
[x] pytest 1151 passing  (note: 16th item per directive list)
```

## 6. No-change verification

```text
pytest -q                                1151 passing (1145 + 6 new)
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
                                          PR51 itself contributes 0 lines
                                          to ragcore source
ragcore source cerberus mentions          0 (generic identity preserved)
external package imports in ragcore       0

adapter-specific symbols in ragcore.__all__:  none
ragcore type added in PR51:                    none
ragcore method surface change:                  none
new public symbol:                               0
new engine behavior:                             0
contract §51:                                    not added
runtime enforcement:                             0
adapter implementation:                          not included
                                                  (PR51 is external example,
                                                   not adapter)
```

All framework invariants preserved.

## 7. What PR51 closed

```text
- PR50 §6 audit pseudocode 가 이제 executable 코드로 존재
- 7-key minimal Engine Context Packet 의 reference 구현체 등록
- 6 invariant test 로 wrapper 의 read-only / public-only /
  domain-neutral 보장 잠금
- PR49 §8 PR51 Guard 1순위 path 통과 (external wrapper,
  ragcore source change 0)
- AST-based source check 패턴 등록 (docstring 안의 의도된
  reference 와 actual code 의 invariant 검사 분리)
- 19 read-only public methods 중 8 개를 minimal 조합으로 사용 —
  나머지 11 개도 future expansion 가능 demonstration
- "wrapper 가 새 Engine surface 가 아니다" 라는 원칙의 executable
  proof
```

## 8. What PR51 deliberately did NOT do

PR51 did NOT:

```text
- add any read method to ragcore
- add any public symbol to ragcore.__all__
- modify any ragcore source file
- introduce LLMContextPacket / RAGContext / ToolPlan /
  EngineContextPacket / LLMProposal as a ragcore type
- modify snapshot schema_version
- modify any of the 18 snapshot top-level keys
- modify lifecycle transition rules
- modify effective_confidence formula
- modify modifier value / order / saturation
- introduce contract §51
- freeze the packet shape (PR52 책임)
- create an EngineInspector class
- create a ClaimContextPacket / EvidenceSummary dataclass
- create domain-specific labels or naming
- compute LLM-facing verdicts / risk / probability / score
- introduce private attribute access from the wrapper
- introduce 3rd-party external package import
- auto-schedule PR52 (LLM Context Packet Spec separately decided)
```

## 9. Implementation footprint

Changed files (184 + 185 + 186):

```text
examples/inspector/engine_inspector.py             +116 lines (184차, NEW)
tests/test_external_engine_inspector.py            +255 lines (185차, NEW)
docs/dev/PR_051_MINIMAL_CLAIM_READ_QUERY_MVP.md    this record (186차)
```

Unchanged:

```text
ragcore/engine.py                                   (no PR51-attributable change)
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
pyproject.toml
README.md
docs/README.md
docs/contracts/05_DATA_CONTRACT_MVP.md              (no §51 added)
docs/architecture/ENGINE_INTERNAL_MAP.md             (PR47 artifact)
docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md (PR49 artifact)
docs/architecture/ENGINE_READ_SURFACE_AUDIT.md       (PR50 artifact)
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
docs/guides/ADAPTER_POLICY_GUIDE.md
docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md
docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md
docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md
docs/guides/DOMAIN_NEUTRAL_REFERENCE_FLOW.md
examples/probe/external_consumer_probe.py            (PR38-A artifact)
tests/test_external_adapter_simulation.py            (PR41 artifact)
tests/test_engine_method_call_playbook_usage.py      (PR43-C 168차 artifact)
all other tests / docs
```

Note on `ragcore.egg-info/`:

```text
ragcore.egg-info/ is an untracked build artifact present at the
PR51 baseline; it was NOT added to any 184/185/186 commit.
It is not part of the PR51 footprint.
```

No ragcore source change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change. Two new artifacts (consumer-side example + its lock test).

## 10. PR51 cycle

```text
184차  src(examples)  — external engine inspector wrapper
                        (513a3c1, +116 lines)
185차  test(examples) — wrapper read-only invariant test
                        (52d2ef2, +255 lines)
186차  docs(dev)      — PR51 record + ready + squash merge
                        (this commit)
```

Three-차수 cycle (src + test + record). Consistent with PR47 §12 entry conditions #4 ("PR48 cycle follows 2-차수 pattern" — extended here to 3-차수 because test addition is present).

## 11. Pattern position recap

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
PR51    minimal claim read query MVP       examples + tests (this)

All thirteen (post-PR36-PKG):
  framework method surface frozen          ✓
  public observable behavior preserved      ✓
  PR52 remains a separate decision          ✓
```

PR51 is the first PR after PR41 simulation to add new test files (`tests/test_external_engine_inspector.py`). The wrapper and the test together form the executable proof that PR50 §8 Conclusion A is achievable in practice.

## 12. Followup — PR52 (NOT auto-scheduled)

```text
PR52 — LLM Context Packet Spec
       type:     doc-only spec
       location: Cerberus-side spec (per
                 direction_rag_framework_proposal_layer §10)
                 NOT a ragcore public symbol
                 NOT in ragcore.__all__
       scope:    name the packet shape that PR51 wrapper produces;
                 define field semantics; describe what consumers
                 should and should not derive from each field;
                 honor PR44-D AP-CF-* (no "probability" / "truth"
                 reading of effective_confidence)
       requires: explicit user decision before entry
```

PR51 does NOT auto-schedule PR52. If the user enters PR52, the packet shape defined there should align with the 7 keys actually emitted by `build_engine_context_packet` in PR51 — but PR52 is free to add framing, semantics, and consumer-side derivation rules beyond what PR51's MVP needs.

## 13. Framework state (post-PR51)

```text
ragcore baseline:
  main:    d1e4975 (pre-merge; new hash after squash merge)
  1151 tests passing (1145 + 6 new from this PR)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  3 architecture documents
    - compatibility matrix (PR39)
    - engine internal map (PR47)
    - engine read surface audit (PR50)
  1 architecture policy
    - engine read surface thaw policy (PR49)
  5 adapter guides
  1 documentation map / reader entry point
  2 disposable / external examples
    - examples/probe/external_consumer_probe.py (PR38-A)
    - examples/inspector/engine_inspector.py    (PR51 — this)
  3 executable simulation/usage test suites
    - test_external_adapter_simulation.py       (PR41, 18 tests)
    - test_engine_method_call_playbook_usage.py (PR43-C 168차, 12 tests)
    - test_external_engine_inspector.py         (PR51 185차, 6 tests)

Read surface status:
  judgment semantics                         frozen ✓
  read surface policy                        defined ✓ (PR49)
  read surface audit                         complete ✓ (PR50)
  PR51 executable wrapper                    complete ✓ (this PR)
  PR51 invariant lock                        complete ✓ (this PR)
  PR52 LLM Context Packet Spec               NOT entered

ragcore source change since PR36-PKG:  +66 lines (PR48-A banners only)
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 14. Closing meaning

```text
PR51 closes as an external inspector MVP.

The inspector reads Engine state through public methods only.
It does not become a new Engine surface.
```

Locked closing sentences:

```text
PR51 은 external inspector MVP 로 종료한다.

inspector 는 public method 를 통해 Engine 상태를 읽을 뿐이다.
inspector 는 새로운 Engine surface 가 아니다.

We read Engine state through an external inspector, without
changing Engine state.
우리는 Engine 상태를 바꾸지 않고, 외부 inspector 를 통해
Engine 상태를 읽는다.

PR50 §6 audit pseudocode is hereby executable and lock-tested.
PR52 (LLM Context Packet Spec) is NOT automatically entered.
```

No automatic next-PR proposal. User decides direction.
