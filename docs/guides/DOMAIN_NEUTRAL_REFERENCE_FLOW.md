# Domain-neutral Reference Flow

Status: guide (PR45-E, Candidate E)
Baseline: main `d725ff9` (PR44-D merged)
Type: documentation-only reference flow, no implementation, no new tests

## 0. Scope limitation (locked, user 2026-05-23)

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

external signal → adapter policy → Engine public method calls →
query points → snapshot checkpoint → consumer report 의 전체
흐름을 domain-neutral 하게 한 번 묶어 보여주는 closing-narrative
guide 다.

adapter 구현, Engine 동작 변경, 도메인 / 스토리지 / retrieval
시스템 / report schema 선택 — 모두 포함되지 않는다.
```

PR45-E closes Candidate E from the post-PR41 followup list. It is the binding index for the nine prior layers — philosophy through anti-patterns guide — viewed as one end-to-end story rather than as separate documents.

## 1. Layer position

```text
PR39    compatibility audit                — Engine 호환 검증
PR40    adapter policy decisions           — adapter 결정면 10 정책
PR41    simulation tests                    — fake output → Engine 흐름 executable
PR42    retrieval translation guide         — retrieval output → Evidence 의미
PR43-C  method call playbook               — Engine public method 호출 순서
PR44-D  integration anti-patterns          — misuse / boundary violation 이름
PR45-E  reference flow                     — 위 9 layer 를 한 흐름으로 연결 (this)
```

PR45-E sits at the end of the documentation stack. It does not introduce new concepts; it cross-references existing ones.

## 2. Locked principles

```text
PR45-E is a reference flow, not a reference implementation.

It does not implement adapters.
It does not add Engine behavior.
It does not choose a domain, storage backend, retrieval system,
or report schema.
```

Inherited from:

```text
docs/01_CORE_PHILOSOPHY.md
docs/03_RUNTIME_LOOP.md
docs/contracts/05_DATA_CONTRACT_MVP.md §50
docs/guides/ADAPTER_POLICY_GUIDE.md           (PR40)
tests/test_external_adapter_simulation.py    (PR41)
docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md (PR42)
docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md   (PR43-C)
tests/test_engine_method_call_playbook_usage.py (PR43-C 168차)
docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md (PR44-D)
```

## 3. Domain-neutral vocabulary (locked)

The reference flow uses domain-neutral nouns throughout. The forbidden list and the allowed list are both locked so future readers can copy this flow into any domain without inheriting Cerberus-specific or security-specific assumptions.

```text
Forbidden (do not appear in this guide):
  cerberus / vulnerability / scanner / SSH / CVE / nmap /
  host / port / service / asset

Allowed (used throughout this guide):
  DomainObject         — any object the consumer cares about
  Subject              — DomainObject's Engine-side identity
  ExternalSignal       — anything entering the consumer system from
                         outside ragcore
  ExternalObservation  — a recorded event of receiving an
                         ExternalSignal
  RawSource            — adapter-side handle for the original source
  RetrievedItem        — single output unit from a retrieval call
  AdapterPolicy        — consumer-owned interpretation rules
  EvidenceSignal       — an interpreted unit that becomes Engine
                         Evidence
  ClaimProposal        — an interpreted unit that becomes Engine
                         Claim
  MissingEvidence      — an interpreted unit that becomes Engine
                         Gap
  ConflictSignal       — an interpreted unit that becomes Engine
                         Contradiction
  ConsumerReport       — the consumer-side output, owned by the
                         report layer
```

These names belong to *this guide*. They are NOT ragcore symbols. They are NOT exported. They are descriptive labels for the reader.

## 4. Reading conventions

Each phase in §5 uses the same uniform 6-field structure:

```text
- Responsibility owner       — who runs this phase
- What happens               — what actually occurs
- Engine method surface       — which public methods (if any)
- Related 9-layer reference   — which prior document layer applies
- Related anti-pattern guard  — which AP-* names this phase risks
                                (if applicable)
- Existing test / prior guard — which existing executable guard
                                catches violations of this phase
                                (if applicable)
```

The "Responsibility owner" field is critical. The reference flow only works because Engine, Adapter, and Consumer-side report layer remain separate.

```text
Engine                 — ragcore.Engine; the frozen 40 public methods
Adapter                — consumer-side translation layer
Consumer-side report   — consumer-side output layer (NOT the adapter,
                         NOT the engine)
Consumer environment   — anything outside all three above
                         (the world where ExternalSignal originates)
```

The 10 phases (phase 0 through phase 9) are *conceptual* phases. The actual call order is given in §6 and follows PR43-C §6.

---

## 5. The 10 phases

### 5.0 phase 0 — External signal arrives

```text
Responsibility owner:
  Consumer environment (NOT Engine, NOT Adapter)

What happens:
  An ExternalSignal reaches the boundary of the consumer system.
  This may be a RetrievedItem from a retrieval call, an
  ExternalObservation captured by a polling routine, a streamed
  event, a manual analyst note, or an upstream API response.

  RawSource holds the original payload in consumer-side storage.
  Nothing has entered ragcore yet.

Engine method surface:
  none

Related 9-layer reference:
  docs/01_CORE_PHILOSOPHY.md  (Core 는 외부 RAG / LLM / Graph DB 에
                              직접 연결하지 않는다)
  docs/03_RUNTIME_LOOP.md      (외부 Adapter 분리)
  §50                          (External Knowledge Adapter Boundary)

Related anti-pattern guard:
  AP-X-6  domain vocabulary intrusion into ragcore source
            — ExternalSignal 의 도메인 어휘는 adapter 또는 consumer
              storage 에 머문다; ragcore source 에 절대 흘러들지
              않는다

Existing test / prior guard:
  PR41 simulation tests use fake payloads as ExternalSignal
  stand-ins; they confirm Engine accepts only the integer
  raw_ref_id and never the original payload.
```

### 5.1 phase 1 — Adapter policy interprets

```text
Responsibility owner:
  Adapter

What happens:
  AdapterPolicy reads the ExternalSignal and decides:
    - Subject granularity            (PR40 §3.1)
    - Evidence granularity            (PR40 §3.2)
    - raw_ref_id resolution            (PR40 §3.3)
    - consumer-side integer registry  (PR40 §3.4)
    - score → strength translation    (PR40 §3.5, §3.6)
    - claim creation policy            (PR40 §3.7)

  The signal is classified into one or more of:
    - EvidenceSignal
    - ClaimProposal
    - MissingEvidence
    - ConflictSignal

  External scores (similarity / path_score / api_score / LLM
  model_confidence / severity label) are translated via
  non-identity mapping. No external score reaches Engine
  unchanged.

Engine method surface:
  none yet (interpretation only)

Related 9-layer reference:
  PR40 ADAPTER_POLICY_GUIDE.md       (10 policy areas)
  PR42 RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md  (per-type translation)
  PR43-C §2 locked principles         (no identity-pipe)

Related anti-pattern guard:
  AP-X-1  External score identity-pipe
  AP-X-3  rule_id / rule_version tag misunderstanding
  AP-X-4  compute_effective_confidence as truth probability
            (this name is forbidden even at interpretation phase)

Existing test / prior guard:
  PR41 §50.9 / §50.10 invariants (similarity / path_score /
  api_score must not be identity-piped; LLM confidence capped
  at 0.5; severity labels require discrete mapping).
  PR43-C 168차 test_translation_function_is_not_identity.
```

### 5.2 phase 2 — Identity layer registration

```text
Responsibility owner:
  Adapter → Engine

What happens:
  The Subject for each ClaimProposal is registered with Engine
  before any Claim references it. ExternalObservation events
  are recorded so the provenance trail exists.

  If the signal expresses a relationship between two Subjects,
  Relation is registered too.

Engine method surface:
  add_entity(entity_type, flags) -> entity_id
  add_observation(entity_id, raw_ref_id, observation_type,
                  source_type) -> observation_id
  add_relation(from_kind, from_id, to_kind, to_id,
               relation_type, rule_id, reason_code) -> relation_id

Related 9-layer reference:
  PR43-C §4.1 Identity layer
  PR40 §3.1 Subject granularity policy

Related anti-pattern guard:
  AP-I-1  Claim before Entity
  AP-I-2  Observation skipped

Existing test / prior guard:
  PR43-C 168차 test_full_path_completes_through_query_and_snapshot
  (Rule-associated path 와 Direct claim path 모두 add_entity →
  add_claim 순서 사용).
```

### 5.3 phase 3 — Evidence layer registration (meaning)

```text
Responsibility owner:
  Adapter → Engine
  (execution-wise, add_evidence is invoked AFTER add_claim;
   see §6 step ordering)

What happens:
  EvidenceSignal becomes Engine Evidence. The `strength`
  passed to add_evidence is the phase-1 translation result —
  not the raw external score.

  Raw payload (chunk text, response body, row JSON, note text)
  STAYS in consumer-side storage. Only raw_ref_id (int) enters
  the Engine; reverse lookup is the adapter's responsibility.

Engine method surface:
  add_evidence(claim_id, raw_ref_id, evidence_type, strength)
    -> evidence_id

Related 9-layer reference:
  PR43-C §4.2 Evidence layer
  PR42 §6~§12 (per-retrieval-type translation, "Must remain
  outside ragcore" lock)
  PR40 §3.6 Evidence strength policy

Related anti-pattern guard:
  AP-E-1  Raw evidence content stored in Engine
  AP-E-2  Evidence before Claim
  AP-X-1  External score identity-pipe (re-applies here as the
          strength field carries the translated value)

Existing test / prior guard:
  PR43-C 168차 test_full_path_completes_through_query_and_snapshot
  / test_full_path_with_gap_resolution_completes
  PR41 simulation: 7 fake retrieval scenarios all call add_evidence
  with translated strength.
```

### 5.4 phase 4 — Claim layer registration

```text
Responsibility owner:
  Adapter → Engine

What happens:
  ClaimProposal becomes Engine Claim via add_claim. Two paths:

  Path A — Rule-associated
    1. register_rule(RuleDefinition(id, version, maturity,
                                     prior_confidence))   (once)
    2. add_claim(subject_id, claim_type, rule_id=<that id>,
                 rule_version=<that version>, reason_code, ...)
    3. (optional) update_rule_stats(rule_id, rule_version, ...)

  Path B — Direct claim
    1. register_rule(RuleDefinition(<adapter-direct id>, <ver>,
                                     maturity, prior_confidence))
                                                          (once)
    2. add_claim(subject_id, claim_type, rule_id=<that id>,
                 rule_version=<that version>, reason_code, ...)

  In both paths, rule_id and rule_version are required positional
  arguments. They are association tags — Engine does NOT fire
  rules automatically. Engine.fire_rule instance method does not
  exist. ragcore.fire_rule module-level function exists but only
  evaluates rule logic and never mutates Engine state.

Engine method surface:
  register_rule(definition)        # once per RuleDefinition
  add_claim(subject_id, claim_type, rule_id, rule_version,
            reason_code, *, base_confidence, status, flags)
            -> claim_id
  get_rule(rule_id, rule_version)
  get_rule_stats(rule_id, rule_version)
  update_rule_stats(rule_id, rule_version, *, firing_delta,
                    true_delta, false_delta, observed_precision,
                    false_positive_rate)

Related 9-layer reference:
  PR43-C §4.3 Claim layer
  PR43-C §5.1 Rule-associated path
  PR43-C §5.2 Direct claim path
  PR40 §3.7 Claim creation policy

Related anti-pattern guard:
  AP-C-1  Silent duplicate claim creation
  AP-C-2  rule_id=0 misread as "no rule association"
  AP-X-2  fire_rule misuse
  AP-X-3  rule_id / rule_version tag misunderstanding

Existing test / prior guard:
  PR43-C 168차 test_full_path_completes_through_query_and_snapshot
  (Path A).
  PR43-C 168차 test_full_path_with_gap_resolution_completes
  / test_full_path_with_contradiction_completes
  / test_snapshot_roundtrip_preserves_effective_confidence (Path B).
  PR43-C 168차 test_engine_class_has_no_fire_rule_method.
```

### 5.5 phase 5 — Gap / Contradiction attachment

```text
Responsibility owner:
  Adapter → Engine

What happens:
  MissingEvidence becomes Engine Gap via add_gap. A Gap is
  *missing information*, not refutation.

  ConflictSignal becomes (a) registered Evidence (typically with
  opposing semantic), then (b) registered as Contradiction via
  register_contradiction. Gap and Contradiction are NOT
  interchangeable.

  When a later EvidenceSignal arrives that may resolve a Gap,
  the adapter calls resolve_gaps_for_evidence(evidence_id) so
  Engine can attempt automatic resolution.

  When a previously-recorded ConflictSignal is contradicted by
  newer evidence, the adapter calls
  register_contradiction_resolution(claim_id, evidence_id).

Engine method surface:
  add_gap(claim_id, gap_type, required_evidence_type, severity,
          rule_id) -> gap_id
  resolve_gaps_for_evidence(evidence_id) -> tuple[int, ...]
  gap_resolution(gap_id) -> int | None
  gaps_for_claim(claim_id) -> list[Gap]
  get_gap(gap_id) -> Gap
  register_contradiction(claim_id, evidence_id) -> bool
  register_contradiction_resolution(claim_id, evidence_id) -> bool
  contradictions_for_claim(claim_id)
  active_contradictions_for_claim(claim_id)
  active_contradictions_by_freshness(claim_id)
  resolved_contradictions_for_claim(claim_id)

Related 9-layer reference:
  PR43-C §4.4 Gap layer
  PR43-C §4.5 Contradiction layer

Related anti-pattern guard:
  AP-G-1  Gap interpreted as refutation
  AP-G-2  Manual gap resolution that skips evidence
  AP-CT-1 Contradiction registered but no lifecycle transition
  AP-CT-2 Contradiction substituted by Gap

Existing test / prior guard:
  PR43-C 168차 test_full_path_with_gap_resolution_completes
  PR43-C 168차 test_full_path_with_contradiction_completes
  PR43-C 168차 test_gap_layer_does_not_create_contradictions
  PR43-C 168차 test_contradiction_layer_does_not_create_gaps
```

### 5.6 phase 6 — Lifecycle transition

```text
Responsibility owner:
  Adapter → Engine

What happens:
  After a registration batch is complete, the adapter calls
  the appropriate *_if_ready lifecycle helper. The `_if_ready`
  suffix is literal: if the readiness check fails, no transition
  happens and the method returns False.

  Six helpers cover the transition graph:
    candidate  → confirmed     confirm_claim_if_ready
    candidate  → refuted       refute_claim_if_ready
    confirmed  → disputed      dispute_claim_if_ready
    disputed   → confirmed     resolve_disputed_claim_if_ready
    disputed   → refuted       refute_disputed_claim_if_ready
    disputed   → refuted (by freshness)
                               refute_disputed_claim_if_ready_by_freshness

  The boolean return value and claim_lifecycle_history are how
  the adapter knows whether a transition actually fired.

Engine method surface:
  confirm_claim_if_ready(claim_id) -> bool
  dispute_claim_if_ready(claim_id) -> bool
  refute_claim_if_ready(claim_id) -> bool
  refute_disputed_claim_if_ready(claim_id) -> bool
  refute_disputed_claim_if_ready_by_freshness(claim_id) -> bool
  resolve_disputed_claim_if_ready(claim_id) -> bool
  claim_lifecycle_history(claim_id) -> tuple[ClaimLifecycleEvent, ...]

Related 9-layer reference:
  PR43-C §4.6 Lifecycle layer

Related anti-pattern guard:
  AP-L-1  Assuming Engine auto-fires lifecycle transitions
  AP-L-2  Treating _if_ready return value as transition guarantee

Existing test / prior guard:
  PR43-C 168차 test_full_path_with_contradiction_completes
  (dispute_claim_if_ready 가 explicit 하게 호출되고 lifecycle_history
  의 type 이 tuple 임을 확인).
```

### 5.7 phase 7 — Confidence query

```text
Responsibility owner:
  Adapter → Engine (read-only)

What happens:
  After lifecycle is settled, the adapter queries
  compute_effective_confidence(claim_id) and uses the result
  as a decision-support signal — never as a truth probability.

  Auxiliary read queries (evidences_for_claim,
  gaps_for_claim, active_contradictions_for_claim,
  evidence_freshness, active_contradictions_by_freshness) are
  used to assemble the data needed by the consumer-side report
  layer in phase 9.

Engine method surface:
  compute_effective_confidence(claim_id) -> ScoreValue
  evidences_for_claim(claim_id) -> list[Evidence]
  evidence_freshness(evidence_id) -> int
  gaps_for_claim(claim_id)
  active_contradictions_for_claim(claim_id)
  active_contradictions_by_freshness(claim_id)
  get_claim / get_entity / get_evidence /
  get_observation / get_relation

Related 9-layer reference:
  PR43-C §4.7 Confidence query layer

Related anti-pattern guard:
  AP-CF-1  effective_confidence read as "truth probability"
  AP-CF-2  Static threshold cutoff treated as ground truth
  AP-X-4   compute_effective_confidence as truth probability
           (cross-cutting form at consumer-code level)

Existing test / prior guard:
  PR43-C 168차 test_compute_effective_confidence_in_bounds_after_each_path
  (effective_confidence ∈ [0.0, 1.0] for both paths).
```

### 5.8 phase 8 — Snapshot checkpoint

```text
Responsibility owner:
  Adapter → Engine (to_snapshot is a read; persistence is
  adapter-owned)

What happens:
  At a checkpoint of the adapter's choosing — typically:
    - after a batch of registrations
    - after a lifecycle transition
    - before consumer report generation
  the adapter calls to_snapshot() and persists the returned
  dict into adapter-owned storage. Engine never writes to disk.

  On resume, the adapter calls Engine.from_snapshot(snapshot)
  to reconstruct state. Restore is NOT re-judgment: no rules
  are re-fired, no lifecycle methods are re-invoked, and
  compute_effective_confidence yields the same value as before.

Engine method surface:
  to_snapshot() -> dict
  Engine.from_snapshot(snapshot) -> Engine   # classmethod

Related 9-layer reference:
  PR43-C §4.8 Snapshot layer
  PR40 §3.10 Snapshot ownership policy
  PR36-PKG _LOCKED_SNAPSHOT_TOP_LEVEL_KEYS (18 keys, schema_version 2)

Related anti-pattern guard:
  AP-S-1  Treating from_snapshot as "re-judgment"
  AP-S-2  Assuming Engine persists snapshots autonomously
  AP-X-5  Snapshot re-judgment misuse (cross-cutting form)

Existing test / prior guard:
  PR43-C 168차 test_snapshot_roundtrip_preserves_effective_confidence
  (to_snapshot → from_snapshot round-trip 후 동일한
  effective_confidence 유지 — 재판단 없음을 executable 하게 확인).
```

### 5.9 phase 9 — Consumer report translation

```text
Responsibility owner:
  Consumer-side report layer
  (NOT Engine, NOT Adapter — a third zone)

What happens:
  The consumer report layer reads the phase-7 query outputs and
  translates them into a ConsumerReport. The translation MUST
  preserve the meaning of compute_effective_confidence as
  "engine confidence" / "computed signal" / "effective
  confidence" — never as "truth probability."

  This is where domain vocabulary may finally appear — but only
  on the report side, NOT inside ragcore and NOT inside the
  adapter's Engine-bound code paths.

Engine method surface:
  none (only consumes already-queried results from phase 7)

Related 9-layer reference:
  PR43-C §4.7 (confidence reading lock)
  PR44-D §4.7 (forbidden phrasing)
  PR40 §3.10 (snapshot ownership stays consumer-side)
  PR44-D §5.6 (domain vocabulary stays consumer-side)

Related anti-pattern guard:
  AP-CF-1  effective_confidence read as "truth probability"
  AP-CF-2  Static threshold cutoff treated as ground truth
  AP-X-4   compute_effective_confidence as truth probability
           (consumer-code-level form)
  AP-X-6   Domain vocabulary intrusion into ragcore source
           (this AP is most easily violated at the report layer
            if domain terms leak backward into adapter or engine
            code via shared utilities)

Existing test / prior guard:
  No test enforces report-layer phrasing (the report layer is
  outside ragcore's scope). PR43-C §4.7 lock and PR44-D AP-CF-*
  / AP-X-4 are review-time guards. PR44-D §5.6 lists the cue
  for code review of domain term leakage.
```

---

## 6. End-to-end summary (one-page reference)

The 10 phases above are *conceptual*. The actual call sequence follows PR43-C §6 — repeated here in domain-neutral form for one ClaimProposal:

```text
 1. Engine()
 2. register_rule(RuleDefinition(id, version, maturity, prior_confidence))
                                            # phase 4 setup
 3. subject_id = add_entity(...)             # phase 2
 4. add_observation(subject_id, ...)         # phase 2
 5. (optional) add_relation(...)             # phase 2
 6. claim_id = add_claim(subject_id, claim_type,
                          rule_id, rule_version, reason_code, ...)
                                            # phase 4
 7. add_evidence(claim_id, raw_ref_id,
                 evidence_type, strength=translated)
                                            # phase 3 meaning,
                                            # called after phase 4
 8. (if MissingEvidence)   add_gap(claim_id, ...)        # phase 5
 9. (if new supporting Evidence arrives later)
       resolve_gaps_for_evidence(evidence_id)            # phase 5
10. (if ConflictSignal)
       evid = add_evidence(claim_id, opposing_evidence)  # phase 3
       register_contradiction(claim_id, evid)            # phase 5
11. (optional) update_rule_stats(rule_id, rule_version, ...)  # phase 4
12. <lifecycle>_if_ready(claim_id)            # phase 6
13. effective = compute_effective_confidence(claim_id)
                                            # phase 7
14. (other read queries as needed)            # phase 7
15. ConsumerReport translation                # phase 9
                (Engine 밖, consumer-side report layer)
16. snapshot = to_snapshot()                  # phase 8
       adapter persists to its own storage
       (later) Engine.from_snapshot(snapshot) on resume
```

This is the same 15-step safe default as PR43-C §6, retold once with phase numbers attached so the conceptual mapping is visible. Batching and ordering exceptions are allowed within PR43-C §6's "safe default" framing.

## 7. Pattern position — 10-layer alignment

```text
1. Philosophy           docs/01_CORE_PHILOSOPHY.md
2. Runtime              docs/03_RUNTIME_LOOP.md
3. Contract             docs/contracts/05_DATA_CONTRACT_MVP.md §50
4. Audit                docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
5. Guide (policy)       docs/guides/ADAPTER_POLICY_GUIDE.md             (PR40)
6. Simulation            tests/test_external_adapter_simulation.py      (PR41)
7. Guide (retrieval)    docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md (PR42)
8. Guide (call order)   docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md      (PR43-C)
   + usage invariants    tests/test_engine_method_call_playbook_usage.py
9. Guide (anti-patterns) docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md (PR44-D)
10. Guide (reference flow) docs/guides/DOMAIN_NEUTRAL_REFERENCE_FLOW.md   (PR45-E — this)
```

Ten layers. PR45-E adds the tenth as a closing narrative that does not introduce new concepts — every section of this guide cross-references one or more of the prior nine layers.

## 8. What this guide does NOT do

PR45-E 는 의도적으로 다음을 하지 않는다:

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
  guide 본문에 도입
- consumer adapter implementation 자동 예약
- 새 candidate / 새 PR 자동 제안
```

## 9. Followup direction

After PR45-E merges, the 9-layer stack has a binding index. No automatic next PR is proposed.

Remaining items that may be picked up by the user, all NOT auto-scheduled:

```text
- consumer adapter implementation (별도 repo / 별도 의사결정)
- domain-specific reference implementations (별도 의사결정)
- additional executable guards over specific anti-patterns
  (사용자가 명시적으로 요청할 때만)
```

## 10. Closing meaning

```text
PR45-E does not implement.

It binds the nine prior layers — philosophy, runtime, contract,
audit, policy guide, simulation, retrieval guide, call playbook,
anti-patterns guide — into one phase-numbered narrative.

Each of the 10 phases names its Responsibility owner, the Engine
public methods it touches (if any), the prior layer it inherits
from, the anti-patterns it must avoid, and the existing
executable guard that catches violations.

The framework, viewed end-to-end, now reads as one story
without choosing a single domain to tell it through.
```

Locked closing sentences:

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

No automatic next-PR proposal. User decides direction.
