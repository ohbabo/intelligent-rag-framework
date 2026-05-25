# PR49 — Engine Read Surface Thaw Policy

## Scope limitation (locked, user 2026-05-25)

```text
PR49 is a policy PR, not an implementation PR.

It does not thaw the Engine judgment semantics.
It defines the conditions under which read-only inspection surface
may be thawed later.
```

한국어:

```text
PR49 는 구현 PR 이 아니라 정책 PR 이다.

Engine 판단 의미를 해제하지 않는다.
나중에 read-only inspection surface 를 열 수 있는 조건만 정의한다.
```

PR49 is the first PR in the PR49-PR52 read-surface roadmap. Its only artifact is the policy document at `docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md`. No source file in `ragcore/` is modified; no test is added; no public symbol is added.

## 1. Baseline + cycle record

```text
main:    96fd0df  (PR48-A merged)
tests:   1145 passing

180차:
  branch:  docs/engine-read-surface-thaw-policy
  commit:  7b34464 docs(architecture): define engine read surface
                                       thaw policy
  file:    docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md
           (+351 lines, NEW)
  pytest:  1145 passing (unchanged)
  ragcore source change: 0 bytes
  Draft PR: #50 PR49: Engine Read Surface Thaw Policy

181차 (this):
  docs(dev): record PR49 closing + ready + squash merge
  file:    docs/dev/PR_049_ENGINE_READ_SURFACE_THAW_POLICY.md
```

## 2. What PR49 is / is not

```text
PR49 = Engine Read Surface Thaw Policy
성격   = doc-only policy PR
         freeze 의 두 의미 (Sense A judgment / Sense B total) 분리
         judgment semantics 는 유지
         read surface 는 향후 조건부 해제 가능 — 단 본 PR 은 해제 아님

성격 아님:
  - thaw implementation
  - new read method addition
  - LLMContextPacket / RAGContext public symbol 추가
  - 외부 LLM 판단 엔진 설계
  - PR50 / PR51 / PR52 자동 진입
  - contract §51 신설
  - source / test 변경
```

## 3. Policy document structure (11 sections)

`docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md` — 351 lines, 11 sections:

```text
§0   Scope limitation                       locked 2026-05-25
§1   Core Statement                          single governing sentence
§2   Why This Policy Exists                  freeze Sense A vs Sense B
§3   Frozen Judgment Semantics              10 items (PR47 §3 mirror)
§4   Thawed Read Surface                    potentially openable areas
§5   Read-only Definition                   6 must-hold conditions
§6   LLM / Consumer Boundary                proposal layer inheritance
§7   PR49 ~ PR52 Roadmap                     4 PR sequence
§8   PR51 Guard                              3 conditions (a/b/c)
§9   Out of Scope                            16 OOS items
§10  Exit Criteria                           12-item checklist
§11  Closing meaning
```

11 sections. 351 lines. Zero ragcore source change. Zero new tests.

## 4. The four key locks

### 4.1 Core Statement (§1)

```text
We thaw the read surface, not the judgment semantics.
우리는 판단 의미를 푸는 것이 아니라, 읽기 표면만 푼다.
```

The single sentence that governs every PR in the PR49-PR52 sequence.

### 4.2 Frozen Judgment Semantics (§3, 10 items)

Mirror of PR47 §3 do-not-touch boundary, re-asserted in the read-surface context:

```text
1.  Lifecycle transition rules
2.  effective_confidence formula
3.  Modifier meaning / order / saturation
4.  Contradiction / refutation semantics
5.  Snapshot schema_version + 18 top-level keys
6.  to_snapshot / from_snapshot symmetry
7.  Domain-neutral judgment boundary
8.  40 public method signatures + observable behavior
9.  48 ragcore.__all__ symbols
10. 6 frozen report / read-surface key sets
```

### 4.3 Read-only Definition (§5, 6 must-hold conditions)

A change is "read-only" only if ALL hold:

```text
- no state mutation
- no lifecycle transition
- no recomputation different from formula
- no schema migration
- no new judgment creation
- no domain vocabulary injected
```

### 4.4 PR51 Guard (§8, 3 conditions)

Default is external EngineInspector wrapper (ragcore source change 0). ragcore public method addition allowed only if ALL of:

```text
(a) PR50 audit concludes existing 40 methods insufficient
(b) user issues separate authorization lock
(c) addition honors PR47 §3 + §12 + §5 + PR44-D AP-* set
```

## 5. Self-review checklist (13/13)

```text
[x] ragcore/engine.py 변경 0
[x] ragcore/types.py 변경 0
[x] ragcore/__init__.py 변경 0
[x] ragcore/rule_output.py 변경 0
[x] ragcore.__all__ 변경 0          (48 symbols preserved)
[x] Engine public method 추가 0     (40 methods preserved)
[x] snapshot schema_version 변경 0  (2 preserved)
[x] lifecycle transition 변경 0
[x] effective_confidence formula 변경 0
[x] modifier 의미 / 값 / 순서 변경 0
[x] LLMContextPacket / RAGContext / ToolPlan / LLMProposal 류
    public symbol 추가 0
[x] tests 1145 passing
[x] PR50 / PR51 / PR52 자동 진입 없음
```

## 6. No-change verification

```text
pytest -q                                1145 passing (unchanged from PR48-A)
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
                                          PR49 itself contributes 0 lines
ragcore source cerberus mentions          0 (generic identity preserved)
external package imports in ragcore       0

adapter-specific symbols in ragcore.__all__:  none
ragcore type added in PR49:                    none
ragcore method surface change:                  none
new tests:                                       0
new public symbol:                               0
new engine behavior:                             0
contract §51:                                    not added
runtime enforcement:                             0
adapter implementation:                          not included
```

All framework invariants preserved.

## 7. What PR49 closed

```text
- "freeze" 단어의 두 의미 (Sense A judgment / Sense B total) 의
  written distinction 등록
- judgment semantics freeze 의 10 items 가 read-surface context
  에서도 유지됨을 명문화 (PR47 §3 mirror)
- read-only 의 6 must-hold 조건 정의
- PR49 ~ PR52 4-PR roadmap 의 entry sequence 잠금
- PR51 Guard 3 conditions (a/b/c) 박음
- LLM / Consumer Boundary 의 proposal layer inheritance 명시
  (direction_rag_framework_proposal_layer 와 정합)
- 16 OOS items 명시
- 12-item exit criteria 잠금
```

PR49 names the boundary so that PR50 audit, PR51 minimal read query, and PR52 context packet spec each have a written reference to honor.

## 8. What PR49 deliberately did NOT do

PR49 did NOT:

```text
- thaw any read surface
- add any read method
- add any public symbol
- modify any ragcore source file
- modify any test
- introduce LLMContextPacket / RAGContext / ToolPlan /
  EngineContextPacket / LLMProposal as a ragcore type
- modify snapshot schema_version
- modify any of the 18 snapshot top-level keys
- modify lifecycle transition rules
- modify effective_confidence formula
- modify modifier value / order / saturation
- introduce contract §51 (policy lives in docs/architecture/,
  not in contract surface)
- auto-schedule PR50 / PR51 / PR52
- specify any Cerberus-side proposal layer implementation
  (only references it via direction_rag_framework_proposal_layer)
- introduce domain vocabulary
  (cerberus / vulnerability / scanner / SSH / CVE / nmap /
   host / port / service / asset)
- introduce runtime enforcement
- introduce adapter implementation
```

## 9. Implementation footprint

Changed files (180 + 181):

```text
docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md     +351 lines (180차, NEW)
docs/dev/PR_049_ENGINE_READ_SURFACE_THAW_POLICY.md       this record (181차)
```

Unchanged:

```text
ragcore/engine.py                  (no PR49-attributable change)
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
pyproject.toml
README.md
docs/README.md
docs/contracts/05_DATA_CONTRACT_MVP.md       (no §51 added)
docs/architecture/ENGINE_INTERNAL_MAP.md      (PR47 artifact preserved)
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
docs/guides/ADAPTER_POLICY_GUIDE.md
docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md
docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md
docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md
docs/guides/DOMAIN_NEUTRAL_REFERENCE_FLOW.md
tests/test_external_adapter_simulation.py
tests/test_engine_method_call_playbook_usage.py
examples/probe/external_consumer_probe.py
all other tests
all other docs/
```

Note on `ragcore.egg-info/`:

```text
ragcore.egg-info/ is an untracked build artifact present at the
PR49 baseline; it was NOT added to either 180차 or 181차 commit.
It is not part of the PR49 footprint.
```

No source change. No test change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change.

## 10. PR49 cycle

```text
180차  docs(architecture) — Engine Read Surface Thaw Policy (+351 lines)   7b34464
181차  docs(dev) — PR49 record + ready + squash merge                       this commit
```

Two-차수 cycle. No new tests. No source change. No new public API. No automatic next PR.

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
PR49    engine read surface thaw policy    documentation-only (policy) (this)

All eleven (post-PR36-PKG):
  framework method surface frozen          ✓
  public observable behavior preserved      ✓
  PR50 / PR51 / PR52 remain separate decisions  ✓
```

PR49 is the first policy-track PR after the documentation stack closed at PR46-B and the first refactor PR48-A landed. It does not touch source; it establishes the lock for the read-surface sequence that follows.

## 12. Followup — PR50 / PR51 / PR52 (NOT auto-scheduled)

```text
PR50 — Engine Read Surface Audit
       type:   doc-only audit
       scope:  which of the 40 public methods already satisfy
               §5 read-only definition; which gaps remain;
               whether any minimal new read method is justified
       source change: 0 expected
       test change:   0 expected
       requires: explicit user decision before entry

PR51 — Minimal Claim Read Query MVP
       type:   MVP (Cerberus-side EngineInspector wrapper preferred)
       1순위:  Cerberus-side / external consumer-side wrapper
               (ragcore source change 0)
       2순위:  ragcore public read method addition
               — only if PR51 Guard 3 conditions (a/b/c) all met
       requires: explicit user decision before entry

PR52 — LLM Context Packet Spec
       type:   doc-only spec
       location: Cerberus-side spec (per
                 direction_rag_framework_proposal_layer §10)
                 NOT a ragcore public symbol; NOT in ragcore.__all__
       requires: explicit user decision before entry
```

Each PR is independent. Entering PRn does NOT auto-schedule PRn+1. PR49 explicitly does not schedule any of the above.

## 13. Framework state (post-PR49)

```text
ragcore baseline:
  main:    96fd0df (pre-merge; new hash after squash merge)
  1145 tests passing (unchanged from PR43-C through PR48-A)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  2 architecture audits
    - compatibility matrix (PR39)
    - engine internal map (PR47)
  1 architecture policy
    - engine read surface thaw policy (PR49 — this)
  5 adapter guides
  1 documentation map / reader entry point
  1 disposable probe (PR38-A)
  2 executable simulation/usage test suites
  1 behavior-preserving refactor commit on engine.py
    (PR48-A comment-only banners)

Read surface status:
  judgment semantics                       frozen ✓
  read surface                             policy defined ✓
                                            (PR49, not yet thawed)
  PR50 audit                                 NOT entered
  PR51 minimal read query                   NOT entered
  PR52 LLM context packet spec               NOT entered

ragcore source change since PR36-PKG:  +66 lines (PR48-A banners only)
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 14. Closing meaning

```text
PR49 closes as a doc-only policy PR.

The frozen Engine judgment semantics remain unchanged.
Only the future conditions for read-only surface thaw are now
defined.
```

Locked closing sentences:

```text
PR49 는 doc-only 정책 PR 로 종료한다.

Engine judgment semantics 는 변경되지 않았다.
이번 PR 은 향후 read-only surface 를 해제할 수 있는 조건만 정의했다.

We thaw the read surface, not the judgment semantics.
우리는 판단 의미를 푸는 것이 아니라, 읽기 표면만 푼다.

PR50 / PR51 / PR52 are NOT automatically entered.
```

No automatic next-PR proposal. User decides direction.
