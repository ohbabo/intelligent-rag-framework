# PR44-D — Engine Integration Anti-patterns Guide MVP

## Scope limitation (locked, user 2026-05-23)

```text
PR44-D names unsafe integration patterns.
It does not add runtime enforcement.
It does not implement adapters.
It does not change Engine judgment semantics.
```

한국어:

```text
PR44-D 는 Engine 통합 시 절대 하면 안 되는 misuse / boundary
violation 24 개에 stable ID 를 부여하고, 각각의 원인 / 올바른 대안 /
탐지 단서 / 기존 가드 를 정리한 negative boundary guide 다.

새 runtime enforcement, 새 test, adapter 구현, contract §51 신설,
Engine 판단 의미론 변경 — 모두 포함되지 않는다.
```

PR44-D closes Candidate D from the post-PR41 followup list. PR43-C documented the positive call-order playbook ("do this"). PR44-D documents the *negative* boundary ("do not do these, here is why") so each anti-pattern can be referenced by stable ID in code review and post-mortems.

## 1. Why PR44-D is the companion to PR43-C

```text
PR43-C  positive playbook
  - 8 layer 별 어떤 Engine public method 를 어떻게 호출하는가
  - 2 path (Rule-associated / Direct claim) 흐름
  - 15-step safe default call order
  - 12 executable usage invariants

PR44-D  negative boundary
  - 8 layer 별 misuse 16 개
  - cross-cutting misuse 8 개
  - 24 anti-pattern 각각 stable ID + uniform 6-field 구조
  - 각각의 "Related test or prior guard" 가
    PR41 / PR42 / PR43-C / PR40 / §50 의 기존 guardrail 을 가리킴
```

PR43-C 가 "do this" 를 말한 위치에서, PR44-D 는 "do not do these, here is why, here is how to detect them, here is the prior guard that already enforces them at the executable layer." 를 말한다.

## 2. Guide structure (11 sections)

`docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md` — 968 lines, 11 sections:

```text
§0   Scope limitation                       locked 2026-05-23
§1   Layer position                         PR39 ~ PR44-D
§2   Locked principles                      the 4-sentence lock
§3   Reading conventions                    uniform 6-field structure +
                                             AP-* stable ID scheme
§4   Layer-based anti-patterns (16)
       §4.1 Identity         AP-I-1 / AP-I-2
       §4.2 Evidence         AP-E-1 / AP-E-2
       §4.3 Claim            AP-C-1 / AP-C-2
       §4.4 Gap              AP-G-1 / AP-G-2
       §4.5 Contradiction    AP-CT-1 / AP-CT-2
       §4.6 Lifecycle        AP-L-1 / AP-L-2
       §4.7 Confidence       AP-CF-1 / AP-CF-2
       §4.8 Snapshot         AP-S-1 / AP-S-2
§5   Cross-cutting anti-patterns (8)
       §5.1 AP-X-1   External score identity-pipe
       §5.2 AP-X-2   fire_rule misuse
       §5.3 AP-X-3   rule_id / rule_version tag misunderstanding
       §5.4 AP-X-4   compute_effective_confidence as truth probability
       §5.5 AP-X-5   Snapshot re-judgment misuse
       §5.6 AP-X-6   Domain vocabulary intrusion into ragcore source
       §5.7 AP-X-7   adapter-specific symbol promoted into ragcore.__all__
       §5.8 AP-X-8   Private state / helper / constant dependence
§6   Anti-pattern index                     one-page reference (24 items)
§7   Pattern position                       9-layer adapter alignment
§8   What this guide does NOT do
§9   Followup candidates (E only)
§10  Closing meaning
```

11 sections. 968 lines. Zero ragcore source change. Zero new tests.

## 3. 24 named anti-patterns

```text
Layer-based (16)
  Identity        AP-I-1   Claim before Entity
                  AP-I-2   Observation skipped
  Evidence        AP-E-1   Raw evidence content stored in Engine
                  AP-E-2   Evidence before Claim
  Claim           AP-C-1   Silent duplicate claim creation
                  AP-C-2   rule_id=0 misread as "no rule association"
  Gap             AP-G-1   Gap interpreted as refutation
                  AP-G-2   Manual gap resolution that skips evidence
  Contradiction   AP-CT-1  Contradiction registered but no lifecycle
                  AP-CT-2  Contradiction substituted by Gap
  Lifecycle       AP-L-1   Assuming Engine auto-fires transitions
                  AP-L-2   Treating _if_ready return value as guarantee
  Confidence      AP-CF-1  effective_confidence read as truth probability
                  AP-CF-2  Static threshold cutoff treated as ground truth
  Snapshot        AP-S-1   from_snapshot as "re-judgment"
                  AP-S-2   Assuming Engine persists snapshots autonomously

Cross-cutting (8)
  AP-X-1   External score identity-pipe
  AP-X-2   fire_rule misuse
  AP-X-3   rule_id / rule_version tag misunderstanding
  AP-X-4   compute_effective_confidence as truth probability
  AP-X-5   Snapshot re-judgment misuse
  AP-X-6   Domain vocabulary intrusion into ragcore source
  AP-X-7   adapter-specific symbol promoted into ragcore.__all__
  AP-X-8   Private state / helper / constant dependence
```

24 total. Each uses uniform 6-field structure:

```text
- Name                — short stable ID
- Symptom             — how the misuse looks in code or behavior
- Why it is wrong     — which locked framework principle it breaks
- Correct alternative — pointer to PR43-C / PR42 / §50 / PR40 / PR41
- Detection cue       — what to look for in code review
- Related test or prior guard
                      — which existing test / contract / guide already
                        catches or names this
```

## 4. Test policy lock (default no new tests)

```text
PR44-D adds 0 tests.

Reason:
  PR41 simulation tests (18) + PR43-C 168차 invariants (12) already
  provide executable guards that catch most of these anti-patterns
  at the test layer.

Each anti-pattern's "Related test or prior guard" field cites the
exact prior guard:

  - AP-X-1 (identity-pipe)          → PR41 §50.9/10 + PR43-C #4
  - AP-X-2 (fire_rule misuse)       → PR43-C 168차 test_engine_class_has_no_fire_rule_method
  - AP-X-7 (__all__ promotion)      → PR43-C 168차 test_ragcore_all_remains_48_symbols
  - AP-X-8 (private state)          → PR43-C 168차 test_playbook_uses_only_existing_engine_public_methods
                                      / test_engine_public_method_surface_is_40
  - AP-G-1 / AP-CT-2 (Gap vs Contradiction confusion)
                                    → PR43-C 168차 test_gap_layer_does_not_create_contradictions
                                      / test_contradiction_layer_does_not_create_gaps
  - AP-S-1 / AP-X-5 (snapshot re-judgment)
                                    → PR43-C 168차 test_snapshot_roundtrip_preserves_effective_confidence
  - AP-E-1 (raw content in Engine)   → PR42 RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md §6~§12 +
                                       PR40 §3.10
  - AP-CF-* (truth probability)      → PR43-C §4.7 forbidden phrasing lock
  - AP-X-6 (domain vocab intrusion)  → §50 contract +
                                       direction_rag_framework_rag_agnostic
```

PR44-D is naming + review material. No executable layer added.

## 5. 9-layer adapter documentation alignment

```text
1. Philosophy           docs/01_CORE_PHILOSOPHY.md
2. Runtime              docs/03_RUNTIME_LOOP.md
3. Contract             docs/contracts/05_DATA_CONTRACT_MVP.md §50
4. Audit                docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
5. Guide (policy)       docs/guides/ADAPTER_POLICY_GUIDE.md           (PR40)
6. Simulation            tests/test_external_adapter_simulation.py    (PR41)
7. Guide (retrieval)    docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md (PR42)
8. Guide (call order)   docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md    (PR43-C)
   + usage invariants    tests/test_engine_method_call_playbook_usage.py
9. Guide (anti-patterns) docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md (PR44-D — this)
```

Nine layers. PR40·PR42·PR43-C·PR44-D form a guide track; PR41·PR43-C(test commit) form a simulation/usage track; PR39 is audit; §50 is contract; philosophy/runtime are origin.

PR44-D is the negative counterpart sitting beside PR43-C — positive playbook (PR43-C) and negative boundary (PR44-D) form a matched pair.

## 6. What PR44-D closed

```text
- 8 playbook layer 별 misuse 16 개에 stable ID (AP-I-* / AP-E-* /
  AP-C-* / AP-G-* / AP-CT-* / AP-L-* / AP-CF-* / AP-S-*) 부여
- cross-cutting misuse 8 개에 stable ID (AP-X-*) 부여
- 24 anti-pattern 모두 uniform 6-field 구조로 정리
- 각 anti-pattern 의 "Related test or prior guard" 가
  PR41 / PR42 / PR43-C / PR40 / §50 의 기존 guardrail 을 가리킴
- code review / post-mortem 에서 stable ID 로 즉시 참조 가능
- PR43-C positive ↔ PR44-D negative 쌍 완성
```

## 7. What PR44-D deliberately did NOT do

PR44-D did NOT:

```text
- Engine 에 새 runtime enforcement / runtime reject 추가
- 새 Engine method 추가
- 기존 Engine method signature 변경
- modifier 7종 공식 변경
- threshold / scoring calibration 변경
- 새 test 추가 (PR41 + PR43-C 168차 가 이미 실행 가드 제공)
- contract §51 신설
- ragcore.__all__ 추가
- engine.py / types.py / __init__.py / rule_output.py 수정
- 새 snapshot schema version
- 새 public API
- 도메인 taxonomy 정의
- vector DB / graph DB / LLM / SQL / file / API 구현
- adapter 구현
- Cerberus 또는 V-cerberus 진입
- Candidate E (Domain-neutral Reference Flow) 자동 예약
- consumer adapter implementation 진입
```

## 8. Confirmed invariants

```text
pytest -q                                1145 passing (unchanged from PR43-C)
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
ragcore type added in PR44-D:                 none
ragcore method surface change:                 none
new tests:                                     0 (default lock honored)
new public symbol:                             0
new engine behavior:                           0
contract §51:                                  not added
```

All framework invariants preserved.

## 9. Implementation footprint

Changed files (170 + 171):

```text
docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md            +968 lines (170차)
docs/dev/PR_044_ENGINE_INTEGRATION_ANTI_PATTERNS_MVP.md    this record (171차)
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
tests/test_external_adapter_simulation.py
tests/test_engine_method_call_playbook_usage.py
examples/probe/external_consumer_probe.py
all other tests
all other docs/
```

No source change. No test change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change.

## 10. PR44-D cycle

```text
170차  docs(guides) — Engine Integration Anti-patterns (+968 lines)   9cfc77c
171차  docs(dev) — PR44-D record + ready + squash merge                this commit
```

Two-차수 cycle. No new tests. No source change. No new public API.

## 11. Pattern position recap

```text
PR39    compatibility audit                documentation-only, no source change
PR40    adapter policy guide               documentation-only, no source change
PR41    external adapter simulation        tests-only, no source change
PR42    retrieval translation guide        documentation-only, no source change
PR43-C  engine method call playbook        guide + tests, no source change
PR44-D  integration anti-patterns          documentation-only, no source change (this)

All six:
  ragcore source unchanged
  framework method surface frozen
  candidate area E remains unscheduled
```

## 12. Followup candidate areas (still NOT PR-numbered)

```text
PR45-E Domain-neutral Reference Flow      (Candidate E)
consumer adapter implementation            (별도, 자동 진입 아님)
```

After PR44-D merges, neither is scheduled. PR44-D does NOT auto-propose them. User decides next direction.

## 13. Framework state (post-PR44-D)

```text
ragcore baseline:
  main:    f9fbed8 (pre-merge; new hash after squash merge)
  1145 tests passing (unchanged from PR43-C)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  1 architecture audit (compatibility matrix)
  4 adapter guides (policy + retrieval + call playbook + anti-patterns)
  1 disposable probe (PR38-A)
  2 executable simulation/usage test suites
    (test_external_adapter_simulation.py — PR41, 18 tests)
    (test_engine_method_call_playbook_usage.py — PR43-C, 12 tests)

9-layer adapter documentation alignment:
  philosophy + runtime + contract + audit + policy guide + simulation +
  retrieval guide + call playbook + anti-patterns guide
  ✓ all nine layers present

ragcore source change since PR36-PKG:  0 lines
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 14. Final closing meaning

```text
PR44-D names misuse patterns.

Each named anti-pattern can now be referenced by stable ID
(AP-I-1, AP-X-5, ...) in code review, post-mortems, and PR
discussion — without re-quoting the whole passage.

PR43-C said "do this."
PR44-D says "do not do these, here is why, here is how to detect
them, and here is the prior guard that already enforces them at
the executable layer."

It does not implement a consumer adapter.
It does not add runtime enforcement.
It does not change Engine judgment semantics.
```

Locked closing sentences:

```text
PR44-D 는 Engine 통합 시 절대 하면 안 되는 misuse / boundary
violation 24 개에 stable ID 를 부여하고, 각각의 원인 / 올바른 대안 /
탐지 단서 / 기존 가드 를 정리한 negative boundary guide 다.

PR44-D 는 runtime enforcement PR 이 아니다.
PR44-D 는 unsafe integration pattern 을 이름 붙이는 guide PR 이다.

24 anti-pattern 모두 기존 guard 와 연결된다.
새 테스트 없이도 PR41 / PR42 / PR43-C / PR40 / §50 의 기존 guardrail
위에 놓인다.
```

No automatic next-PR proposal. User decides direction.
