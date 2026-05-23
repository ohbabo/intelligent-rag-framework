# PR45-E — Domain-neutral Reference Flow MVP

## Scope limitation (locked, user 2026-05-23)

```text
PR45-E is a reference flow, not a reference implementation.

It connects external signal, adapter policy, Engine public method
calls, query points, snapshot checkpoint, and consumer report
translation without implementing a consumer adapter.

It does not implement adapters.
It does not add Engine behavior.
It does not choose a domain, storage backend, retrieval system,
or report schema.
```

한국어:

```text
PR45-E 는 reference flow 이지 reference implementation 이 아니다.

PR45-E 는 "구현 전 마지막 연결 문서" 가 아니라
framework-side documentation stack 완성 기록 이다.

adapter 구현, Engine 동작 변경, 도메인 / 스토리지 / retrieval
시스템 / report schema 선택 — 모두 포함되지 않는다.
```

PR45-E closes Candidate E from the post-PR41 followup list. It is the binding index for the nine prior layers viewed as one end-to-end story. With PR45-E merged, the framework-side adapter documentation stack reads as one closing narrative without choosing a single domain to tell it through.

## 1. Baseline

```text
main:    d725ff9  (PR44-D merged)
tests:   1145 passing
branch:  docs/domain-neutral-reference-flow
commit:  eb0ed4a docs(guides): add domain-neutral reference flow

172차:
  branch:  docs/domain-neutral-reference-flow
  commit:  eb0ed4a
  file:    docs/guides/DOMAIN_NEUTRAL_REFERENCE_FLOW.md (+717 lines)
  pytest:  1145 passing (unchanged)
  ragcore source change: 0 lines
  Draft PR: #46 PR45-E: Domain-neutral Reference Flow (Candidate E)

173차 (this):
  docs(dev): record PR45-E closing + ready + squash merge
  file:    docs/dev/PR_045_DOMAIN_NEUTRAL_REFERENCE_FLOW_MVP.md
```

## 2. PR45-E 핵심 정의

```text
PR45-E = Domain-neutral Reference Flow
성격     = reference flow / closing-narrative guide
아님     = reference implementation /
           adapter 구현 /
           test PR /
           contract §51 /
           "구현 전 마지막 연결 문서" 류 implementation bridge

한 줄 정의:
  PR45-E connects the existing adapter boundary stack into one
  neutral flow — external signal → adapter policy → Engine public
  method calls → query / snapshot → consumer-side report
  translation — without implementing a consumer adapter.
```

PR45-E does NOT mark the start of implementation. It marks the completion of the framework-side documentation stack.

## 3. 10-phase flow

```text
phase 0  External signal arrives
phase 1  Adapter policy interprets
phase 2  Identity layer registration
phase 3  Evidence layer registration (meaning)
phase 4  Claim layer registration
           - Rule-associated path
           - Direct claim path
phase 5  Gap / Contradiction attachment
phase 6  Lifecycle transition
phase 7  Confidence query
phase 8  Snapshot checkpoint
phase 9  Consumer report translation
```

Each phase carries uniform 6-field structure:

```text
- Responsibility owner
- What happens
- Engine method surface, if applicable
- Related 9-layer reference
- Related anti-pattern guard, if applicable
- Existing test / prior guard, if applicable
```

Three responsibility zones are explicit (§4 of the guide):

```text
Engine                — ragcore.Engine, frozen 40 methods
Adapter               — consumer-side translation layer
Consumer-side report  — output layer, third zone
```

The 10 phases are *conceptual*. The actual call sequence (PR43-C §6 15-step safe default order, re-told with phase mapping) appears in §6 of the guide.

## 4. 10-layer adapter documentation alignment

```text
1.  Philosophy            docs/01_CORE_PHILOSOPHY.md
2.  Runtime               docs/03_RUNTIME_LOOP.md
3.  Contract              docs/contracts/05_DATA_CONTRACT_MVP.md §50
4.  Audit                 docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
5.  Guide (policy)        docs/guides/ADAPTER_POLICY_GUIDE.md            (PR40)
6.  Simulation             tests/test_external_adapter_simulation.py     (PR41)
7.  Guide (retrieval)     docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md (PR42)
8.  Guide (call order)    docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md     (PR43-C)
     + usage invariants    tests/test_engine_method_call_playbook_usage.py
9.  Guide (anti-patterns) docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md (PR44-D)
10. Guide (reference flow) docs/guides/DOMAIN_NEUTRAL_REFERENCE_FLOW.md   (PR45-E — this)
```

Ten layers complete. PR45-E adds the tenth as a closing narrative that does not introduce new concepts; every section of the guide cross-references one or more of the prior nine layers.

## 5. Domain-neutral lock

```text
Forbidden vocabulary (does not appear in narrative):
  cerberus / vulnerability / scanner / SSH / CVE / nmap /
  host / port / service / asset

Allowed vocabulary (used throughout):
  DomainObject / Subject / ExternalSignal /
  ExternalObservation / RawSource / RetrievedItem /
  AdapterPolicy / EvidenceSignal / ClaimProposal /
  MissingEvidence / ConflictSignal / ConsumerReport
```

Forbidden-vocabulary audit (172차):

```text
The ten forbidden words appear ONLY inside:
  - §3 forbidden-list lock
  - §8 "What this guide does NOT do" lock
They appear ZERO times in narrative phase descriptions.
```

The allowed names belong to the guide; they are NOT ragcore symbols, NOT exported, NOT a new public type. They are descriptive labels for the reader.

## 6. No-change verification

```text
pytest -q                                1145 passing (unchanged from PR44-D)
ragcore.__all__                          48 symbols (PR31-S baseline)
unique symbols                           48
Engine public methods                    40 (PR33-M docstring 40/40)
modifier helpers                          6 with (self, claim_id: int) -> float
                                          (PR34-O signature preserved)
serialize/restore symmetry              6 × 6 (PR35-O7 preserved)
snapshot schema_version                   2 (PR21-L preserved)
snapshot top-level keys                  18 (PR36-PKG _LOCKED frozenset)
report shape                              6 frozen key sets (PR32-V)

ragcore source change since PR36-PKG     0 lines
ragcore source cerberus mentions          0 (generic identity preserved)
external package imports in ragcore       0

adapter-specific symbols in ragcore.__all__:  none
ragcore type added in PR45-E:                  none
ragcore method surface change:                  none
new tests:                                       0 (default lock honored)
new public symbol:                               0
new engine behavior:                             0
contract §51:                                    not added
runtime enforcement:                             0
adapter implementation:                          0
```

All framework invariants preserved.

## 7. What PR45-E closed

```text
- 10 conceptual phase (phase 0 ~ phase 9) 로 9-layer stack 의
  의미를 한 줄기로 연결
- 각 phase 의 uniform 6-field 구조 (Responsibility owner / What
  happens / Engine method surface / Related 9-layer reference /
  Related anti-pattern guard / Existing test or prior guard)
- 세 responsibility zone 명시: Engine / Adapter / Consumer-side
  report
- domain-neutral vocabulary lock (forbidden 10 + allowed 12)
- §6 end-to-end summary: PR43-C §6 15-step safe default order 를
  domain-neutral 형태로 재서술하며 phase 매핑 부여
- 10-layer adapter documentation alignment 완성
- framework-side documentation stack 의 closing-narrative 등록
```

PR45-E does not add new framework capability. It closes the documentation reading order.

## 8. What PR45-E deliberately did NOT do

PR45-E did NOT:

```text
- adapter 구현
- Engine 동작 변경
- 새 Engine method 추가
- 기존 Engine method signature 변경
- modifier 7종 공식 변경
- threshold / scoring calibration 변경
- 도메인 / storage backend / retrieval system / report schema 선택
- 새 test 추가
- contract §51 신설
- ragcore.__all__ 추가
- engine.py / types.py / __init__.py / rule_output.py 수정
- 새 snapshot schema version
- 새 public API
- runtime enforcement 추가
- 도메인 어휘 (cerberus / vulnerability / scanner / SSH / CVE /
  nmap / host / port / service / asset 등) ragcore source 또는
  guide narrative 에 도입
- consumer adapter implementation 자동 예약
- 새 candidate / 새 PR 자동 제안
- "이제 구현 시작 가능" 류 implementation-bridge 의미 부여
```

Particularly important: PR45-E is NOT an implementation bridge. It is the documentation stack's closing layer.

## 9. Implementation footprint

Changed files (172 + 173):

```text
docs/guides/DOMAIN_NEUTRAL_REFERENCE_FLOW.md             +717 lines (172차)
docs/dev/PR_045_DOMAIN_NEUTRAL_REFERENCE_FLOW_MVP.md     this record (173차)
```

Unchanged:

```text
ragcore/engine.py
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
pyproject.toml
README.md
docs/contracts/05_DATA_CONTRACT_MVP.md       (no §51 added)
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
docs/guides/ADAPTER_POLICY_GUIDE.md
docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md
docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md
docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md
tests/test_external_adapter_simulation.py
tests/test_engine_method_call_playbook_usage.py
examples/probe/external_consumer_probe.py
all other tests
all other docs/
```

No source change. No test change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change.

## 10. PR45-E cycle

```text
172차  docs(guides) — Domain-neutral Reference Flow (+717 lines)   eb0ed4a
173차  docs(dev) — PR45-E record + ready + squash merge             this commit
```

Two-차수 cycle. No new tests. No source change. No new public API. No automatic next PR.

## 11. Pattern position recap

```text
PR39    compatibility audit                documentation-only, no source change
PR40    adapter policy guide               documentation-only, no source change
PR41    external adapter simulation        tests-only, no source change
PR42    retrieval translation guide        documentation-only, no source change
PR43-C  engine method call playbook        guide + tests, no source change
PR44-D  integration anti-patterns          documentation-only, no source change
PR45-E  domain-neutral reference flow      documentation-only, no source change (this)

All seven:
  ragcore source unchanged
  framework method surface frozen
  consumer adapter implementation remains separate, not automatic
```

## 12. Followup

```text
consumer adapter implementation remains separate, not automatic.
domain-specific reference implementations remain separate, not automatic.
additional executable guards over specific anti-patterns remain
NOT auto-scheduled (사용자가 명시적으로 요청할 때만).
```

After PR45-E merges, NO automatic next PR is proposed. The framework's documentation stack is closed; further direction is user-decided.

## 13. Framework state (post-PR45-E)

```text
ragcore baseline:
  main:    d725ff9 (pre-merge; new hash after squash merge)
  1145 tests passing (unchanged from PR43-C / PR44-D)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  1 architecture audit (compatibility matrix)
  5 adapter guides (policy + retrieval + call playbook +
                     anti-patterns + reference flow)
  1 disposable probe (PR38-A)
  2 executable simulation/usage test suites
    (test_external_adapter_simulation.py — PR41, 18 tests)
    (test_engine_method_call_playbook_usage.py — PR43-C, 12 tests)

10-layer adapter documentation alignment:
  philosophy + runtime + contract + audit + policy guide +
  simulation + retrieval guide + call playbook + anti-patterns
  guide + reference flow
  ✓ all ten layers present

ragcore source change since PR36-PKG:  0 lines
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 14. Closing meaning

```text
PR45-E closes the domain-neutral reference flow layer.

It connects the existing adapter boundary stack into one neutral
flow: external signal → adapter policy → Engine public method
calls → query / snapshot → consumer-side report translation.

It remains a reference flow, not a reference implementation.
No consumer adapter is implemented.
Framework waits after merge.
```

Locked closing sentences:

```text
PR45-E does not implement.

It binds the nine prior layers — philosophy, runtime, contract,
audit, policy guide, simulation, retrieval guide, call playbook,
anti-patterns guide — into one phase-numbered narrative.

PR45-E is a reference flow, not a reference implementation.
It does not implement adapters.
It does not add Engine behavior.
It does not choose a domain, storage backend, retrieval system,
or report schema.

reference flow complete.
documentation stack complete.
consumer implementation remains separate.
framework waits.
```

No automatic next-PR proposal. User decides direction.
