# PR43-C — Engine Method Call Playbook MVP

## Scope limitation (locked, user 2026-05-22)

```text
PR43-C does not add new Engine behavior.
PR43-C is a method-call ordering guide for external consumers.

It explains in what order ragcore.Engine public methods should be
called by an adapter to register external interpretation results
into Engine state safely.

It does not add new methods, change signatures, change formulas,
or introduce a consumer adapter.

It does not promote the guide into contract §51.
```

한국어:

```text
PR43-C 는 새 Engine 동작을 추가하는 PR 이 아니다.
PR43-C 는 외부 consumer 가 ragcore.Engine public method 를 어떤
순서로 호출하면 안전하게 상태를 등록할 수 있는지 설명하는
call-order guide 다.

새 method, signature 변경, modifier 공식 변경, consumer adapter
구현, contract §51 승격 — 모두 포함되지 않는다.
```

PR43-C closes Candidate C from the post-PR41 followup list. PR42 explained what each external retrieval output BECOMES inside ragcore. PR43-C explains in what ORDER those translated units should be passed to Engine public methods, and locks a minimal executable usage invariant set.

## 1. Guide structure (12 sections)

`docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md` — 671 lines, 12 sections:

```text
§0   Scope limitation                    locked 2026-05-22
§1   Layer position                      PR39 / PR40 / PR41 / PR42 / PR43-C
§2   Locked principles                   public-method-only / non-identity /
                                          no auto rule firing /
                                          confidence ≠ truth probability /
                                          snapshot ≠ re-judgment
§3   Engine public method surface (40)   bcc2c7e baseline mapping
§4   Eight playbook layers
       4.1 Identity        add_entity / add_observation / add_relation
       4.2 Evidence        add_evidence
       4.3 Claim           add_claim (rule_id/rule_version required tag)
       4.4 Gap             add_gap / resolve_gaps_for_evidence / ...
       4.5 Contradiction   register_contradiction / *_contradiction* / ...
       4.6 Lifecycle       6 *_if_ready helpers (PR34-O 동결)
       4.7 Confidence      compute_effective_confidence
       4.8 Snapshot        to_snapshot / from_snapshot
§5   Two-path model
       5.1 Rule-associated path
       5.2 Direct claim path
§6   Recommended call order              15-step safe default
§7   Layer ↔ method mapping              one-page reference
§8   10 invariants implied by playbook
§9   Pattern position                    8-layer alignment
§10  What this PR does NOT do
§11  Followup candidates (D / E)
§12  Closing meaning
```

12 sections. 671 lines. Zero ragcore source change.

## 2. 168차 executable usage invariants (12 tests)

`tests/test_engine_method_call_playbook_usage.py` — 355 lines, 3 test classes, 12 tests:

```text
TestRuleAssociatedPath               1 test
  - test_full_path_completes_through_query_and_snapshot

TestDirectClaimPath                  3 tests
  - test_full_path_with_gap_resolution_completes
  - test_full_path_with_contradiction_completes
  - test_snapshot_roundtrip_preserves_effective_confidence

TestPlaybookGuards                   8 tests
  - test_engine_class_has_no_fire_rule_method
  - test_engine_public_method_surface_is_40
  - test_ragcore_all_remains_48_symbols
  - test_translation_function_is_not_identity
  - test_gap_layer_does_not_create_contradictions
  - test_contradiction_layer_does_not_create_gaps
  - test_compute_effective_confidence_in_bounds_after_each_path
  - test_playbook_uses_only_existing_engine_public_methods
```

Total: 12 tests, 3 classes.

The test scope is locked tight:

```text
검증 대상:
  - 기존 public methods 조합으로 두 path 가 끝까지 통과한다
  - formula / modifier / threshold / engine behavior 를 변경하지 않는다
  - retrieval score identity-pipe 예제를 만들지 않는다
  - Gap layer 와 Contradiction layer 가 서로의 state 를 만들지 않는다
  - to_snapshot / from_snapshot round-trip 후 동일 effective_confidence

비검증 대상:
  - modifier 7종의 수학 결과 자체
  - scoring calibration
  - 새로운 lifecycle semantics
  - 새 rule firing engine
  - 특정 lifecycle transition 의 실제 발생 여부
    (modifier/threshold 의 결과이므로 playbook 의 검증 범위 아님)
```

## 3. 168차 inspection fact (critical clarification)

While writing test_engine_class_has_no_fire_rule_method, inspection revealed two facts that must be recorded together:

```text
Engine.fire_rule instance method:
  존재하지 않음
  → 사용자의 "fire_rule public method 없음" lock 은 정확

ragcore.fire_rule module-level function:
  존재 (rule_output.py 의 rule evaluator)
  → 이는 standalone function 이며 Engine state 를 변경하지 않음
  → playbook 은 이를 호출하지 않음
  → consumer 가 직접 rule logic 을 실행할 때 도구로 쓸 수 있음
  → 그 결과는 여전히 add_claim 으로 Engine 에 등록되어야 함
```

Guide §4.3 와 §5.1 에 이 distinction 을 명문화한 small clarification 이 168차 commit 에 포함되어 있다.

이 사실은 두 path 의 명명에도 반영되었다:

```text
이전 표현 (drafted):   "Rule path"
정정 표현 (locked):    "Rule-associated path"
이유:
  fire_rule 이 Engine method 처럼 자동 호출되는 mechanism 이 아님.
  모든 Claim 은 add_claim signature 상 rule_id / rule_version tag 를
  required 로 받지만, 이는 association tag 이지 firing trigger 가
  아님.
```

## 4. Two-path model verification

Both paths verified by 168차 tests:

```text
Path A — Rule-associated path
  flow:
    register_rule(RuleDefinition(id, version, maturity, prior_confidence))
    add_entity / add_observation
    add_claim(subject_id, claim_type, rule_id, rule_version, reason_code, ...)
    add_evidence(claim_id, raw_ref_id, evidence_type, strength=translated)
    update_rule_stats(rule_id, rule_version, firing_delta, true_delta)
    confirm_claim_if_ready(claim_id)
    compute_effective_confidence(claim_id)
    to_snapshot() → from_snapshot()
  invariant covered:
    effective_confidence ∈ [0.0, 1.0]
    round-trip preserves effective_confidence
    rule registry remains queryable via get_rule

Path B — Direct claim path
  flow:
    add_entity / add_observation
    add_claim(subject_id, claim_type, rule_id=0, rule_version=0, reason_code, ...)
    add_evidence
    add_gap → resolve_gaps_for_evidence
    register_contradiction (separate scenario)
    dispute_claim_if_ready
    claim_lifecycle_history (well-typed tuple)
    compute_effective_confidence
    to_snapshot() → from_snapshot()
  invariant covered:
    gap layer does NOT create contradictions
    contradiction layer does NOT create gaps
    effective_confidence ∈ [0.0, 1.0]
    snapshot round-trip preserves effective_confidence
```

Both paths reach query / snapshot points without modifying Engine source.

## 5. 8-layer adapter documentation alignment

```text
1. Philosophy           docs/01_CORE_PHILOSOPHY.md
2. Runtime              docs/03_RUNTIME_LOOP.md
3. Contract             docs/contracts/05_DATA_CONTRACT_MVP.md §50
4. Audit                docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
5. Guide                docs/guides/ADAPTER_POLICY_GUIDE.md (PR40)
6. Simulation           tests/test_external_adapter_simulation.py (PR41)
7. Retrieval Guide      docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md (PR42)
8. Call Playbook        docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md (PR43-C — this)
                        + tests/test_engine_method_call_playbook_usage.py
```

Eight layers present. PR40·PR42·PR43-C are guide-track. PR41·PR43-C(test commit) are simulation/usage track. PR39 is audit. §50 is contract. philosophy/runtime are origin.

## 6. What PR43-C closed

```text
- Engine 공개 method 40 개의 호출 순서 명문화 (§3 / §4 / §6 / §7)
- 두 consumer path (Rule-associated / Direct claim) 분리 명문화 (§5)
- 8 playbook layer 별 의도 / 금지 / 노트 정리 (§4)
- 15-step safe default call order + 7 invariant 유지 규칙 (§6)
- 10 invariant 후보 list → 그 중 12 test 로 executable 잠금 (§8 + 168차 test)
- Engine.fire_rule 부재 ↔ ragcore.fire_rule 존재 의 distinction 명문화
- Two-path 명명 정정 ("Rule path" → "Rule-associated path")
- compute_effective_confidence 는 decision-support signal 임 (§4.7 lock)
- snapshot ≠ re-judgment 의미 (§4.8 lock)
- contract §51 진입 없이 guide-only 로 닫힘 (§9 / 162차 cycle pattern 보존)
```

## 7. What PR43-C deliberately did NOT do

PR43-C did NOT:

```text
- 새 Engine method 추가
- 기존 Engine method signature 변경
- modifier 7종 공식 변경
- threshold / scoring calibration 변경
- 도메인 taxonomy 정의
- vector DB / graph DB / LLM / SQL / file / API 구현
- adapter 구현
- Cerberus 또는 V-cerberus 진입
- contract §51 신설
- ragcore.__all__ 추가
- engine.py / types.py / __init__.py / rule_output.py 수정
- 새 snapshot schema version
- 새 public API
- modifier 수학 결과 직접 검증
- 특정 lifecycle transition 의 실제 발생 여부 강제
- PR44-D / PR44-E 자동 제안
```

## 8. Confirmed invariants

```text
pytest -q                                1145 passing (1133 + 12 new)
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
external package imports in ragcore       0 (chromadb / qdrant_client /
                                           pinecone / weaviate / faiss /
                                           neo4j / openai / anthropic /
                                           psycopg / sqlalchemy — all absent)

adapter-specific symbols in ragcore.__all__:  none
ragcore type added in PR43-C:                 none
ragcore method surface change:                 none
Engine.fire_rule:                              not present (verified)
```

All framework invariants preserved.

## 9. Implementation footprint

Changed files (167 + 168 + 169):

```text
docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md             +671 / +small (167+168)
tests/test_engine_method_call_playbook_usage.py        +355 lines (168차)
docs/dev/PR_043_ENGINE_METHOD_CALL_PLAYBOOK_MVP.md     this record (169차)
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
tests/test_external_adapter_simulation.py
examples/probe/external_consumer_probe.py
all other tests
all other docs/
```

No source change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change.

## 10. PR43-C cycle

```text
167차  docs(guides) — Engine Method Call Playbook (+671 lines)             2d0dbd1
168차  test(core) — playbook usage invariants (+355 lines, +small guide)   2bbdc09
169차  docs(dev) — PR43-C record + ready + squash merge                    this commit
```

Three-차수 cycle: guide → test → record. No new tests beyond 168차 12 cases. No source change. No new public API.

## 11. Pattern position recap

```text
PR39    compatibility audit               documentation-only, no source change
PR40    adapter policy guide              documentation-only, no source change
PR41    external adapter simulation       tests-only, no source change
PR42    retrieval translation guide       documentation-only, no source change
PR43-C  engine method call playbook       guide + tests, no source change (this)

All five:
  ragcore source unchanged
  framework method surface frozen
  candidate areas D / E remain unscheduled
```

## 12. Followup candidate areas (still NOT PR-numbered)

```text
PR44-D Anti-patterns Guide              (Candidate D)
PR44-E Domain-neutral Reference Flow    (Candidate E)
consumer adapter implementation          (별도, 자동 진입 아님)
```

After PR43-C merges, none of these are scheduled. PR43-C does NOT auto-propose any of them. User decides next direction.

## 13. Framework state (post-PR43-C)

```text
ragcore baseline:
  main:    bcc2c7e (pre-merge; new hash after squash merge)
  1145 tests passing (PR42 1133 + PR43-C 12)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  1 architecture audit (compatibility matrix)
  3 adapter guides (policy + retrieval translation + call playbook)
  1 disposable probe (PR38-A)
  2 executable simulation/usage test suites
    (test_external_adapter_simulation.py — PR41, 18 tests)
    (test_engine_method_call_playbook_usage.py — PR43-C, 12 tests)

8-layer adapter documentation alignment:
  philosophy + runtime + contract + audit + guide + simulation +
  retrieval guide + call playbook
  ✓ all eight layers present

ragcore source change since PR36-PKG:  0 lines
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 14. Final closing meaning

```text
PR43-C closes the Engine Method Call Playbook layer.

It turns PR42's retrieval translation semantics into safe
public-method call order examples and executable usage guards.

It does not add Engine behavior.
It does not add a consumer adapter.
It does not promote the guide into contract §51.
```

Locked closing sentences:

```text
PR43-C 는 새 Engine 동작을 추가하는 PR 이 아니다.
PR43-C 는 외부 consumer 가 기존 ragcore.Engine public method 40 개를
어떤 순서로 호출하면 안전하게 상태를 등록할 수 있는지 정리한 call-order
guide 와, 그 사용 방식이 frozen public surface 위에서 깨지지 않음을
잠그는 12 개의 executable invariant 다.

Engine 은 rule 을 자동으로 firing 하지 않는다.
Engine.fire_rule instance method 는 존재하지 않는다.
(ragcore.fire_rule module-level function 은 별개 rule evaluator 이며
playbook 은 호출하지 않는다.)
모든 Claim 은 rule association tag 를 가진다.
compute_effective_confidence 는 truth probability 가 아니라
decision-support signal 이다.
Snapshot 은 state preservation 이지 재판단이 아니다.
```

No automatic next-PR proposal. User decides direction.
