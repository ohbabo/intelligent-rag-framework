# Engine Method Call Playbook

Status: guide (PR43-C, Candidate C)
Baseline: main `bcc2c7e` (PR42 merged)
Type: documentation-only call-order guide, no implementation, no new behavior

## 0. Scope limitation (locked, user 2026-05-22)

```text
PR43-C does not add new Engine behavior.
PR43-C is a method-call ordering guide for external consumers.

It explains in what order ragcore.Engine public methods should be
called by an adapter to register external interpretation results
into Engine state safely.

It does not add new methods, change signatures, change formulas,
or introduce a consumer adapter.
```

한국어:

```text
PR43-C 는 새 Engine 동작을 추가하는 PR 이 아니다.
PR43-C 는 외부 consumer 가 ragcore.Engine public method 를 어떤
순서로 호출하면 안전하게 상태를 등록할 수 있는지 설명하는
call-order guide 다.

새 method, signature 변경, modifier 공식 변경, consumer adapter
구현은 포함되지 않는다.
```

PR43-C closes Candidate C from the post-PR41 followup list. PR42 explained what each external retrieval output BECOMES inside ragcore. PR43-C explains in what ORDER those translated units should be passed to Engine public methods.

## 1. Layer position

```text
PR39   compatibility audit              — Engine 호환 검증
PR40   adapter policy decisions         — adapter 결정면 10 정책
PR41   simulation tests                  — fake output → Engine 흐름 executable
PR42   retrieval translation guide       — retrieval output → Evidence 의미
PR43-C method call playbook             — Engine public method 호출 순서 (this)
```

PR43-C fills the gap between "what each retrieval output means" (PR42) and "how an adapter would actually use it" by stating the safe default call order.

This guide does NOT pick storage. It does NOT pick rule logic. It explains call sequencing.

## 2. Locked principles

```text
Engine public methods are the only contract surface.
PR43-C never references private symbols, never references future
Engine APIs, and never proposes new methods.

External output never enters Engine directly.
External output is interpreted by adapter policy first, and then
passed to Engine via add_observation / add_evidence / add_claim /
add_gap / add_relation / register_contradiction.

Engine does not fire rules automatically.
register_rule records a RuleDefinition. add_claim attaches a
rule_id / rule_version association to a Claim. The decision to
fire a rule, evaluate it, or use a "direct" claim path belongs to
the consumer side.

compute_effective_confidence is a decision-support signal.
It is not a truth probability and not a verified-vulnerability
probability.

Snapshot is state preservation.
to_snapshot / from_snapshot persist Engine state. They do not
re-judge claims, do not re-fire rules, and do not re-evaluate
lifecycle transitions.
```

Inherited from:

```text
docs/01_CORE_PHILOSOPHY.md
docs/03_RUNTIME_LOOP.md
docs/contracts/05_DATA_CONTRACT_MVP.md §50
docs/guides/ADAPTER_POLICY_GUIDE.md
tests/test_external_adapter_simulation.py
docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md
```

## 3. Engine public method surface (40 methods, PR33-M docstring 40/40 preserved)

PR43-C groups the 40 public methods by playbook layer. Method names below match `ragcore.Engine` exactly at baseline `bcc2c7e`. Adapter code MUST use these names verbatim; future renames would change the contract surface.

```text
Identity layer:
  add_entity(entity_type, flags)
  add_observation(entity_id, raw_ref_id, observation_type, source_type)
  add_relation(from_kind, from_id, to_kind, to_id, relation_type,
               rule_id, reason_code)

Evidence layer:
  add_evidence(claim_id, raw_ref_id, evidence_type, strength)

Claim layer:
  add_claim(subject_id, claim_type, rule_id, rule_version,
            reason_code, *, base_confidence, status, flags)

Gap layer:
  add_gap(claim_id, gap_type, required_evidence_type, severity, rule_id)
  resolve_gaps_for_evidence(evidence_id)
  gap_resolution(gap_id)
  gaps_for_claim(claim_id)
  get_gap(gap_id)

Contradiction layer:
  register_contradiction(claim_id, evidence_id)
  register_contradiction_resolution(claim_id, evidence_id)
  contradictions_for_claim(claim_id)
  active_contradictions_for_claim(claim_id)
  active_contradictions_by_freshness(claim_id)
  resolved_contradictions_for_claim(claim_id)

Lifecycle layer (6 helpers, PR34-O signature preserved):
  confirm_claim_if_ready(claim_id)
  dispute_claim_if_ready(claim_id)
  refute_claim_if_ready(claim_id)
  refute_disputed_claim_if_ready(claim_id)
  refute_disputed_claim_if_ready_by_freshness(claim_id)
  resolve_disputed_claim_if_ready(claim_id)

Confidence query layer:
  compute_effective_confidence(claim_id)

Snapshot layer:
  to_snapshot()
  from_snapshot(snapshot)        # classmethod

Read / query layer:
  get_claim(claim_id)
  get_entity(entity_id)
  get_evidence(evidence_id)
  get_observation(observation_id)
  get_relation(relation_id)
  evidences_for_claim(claim_id)
  evidence_freshness(evidence_id)
  claim_lifecycle_history(claim_id)

Rule meta layer:
  register_rule(definition)
  get_rule(rule_id, rule_version)
  get_rule_stats(rule_id, rule_version)
  update_rule_stats(rule_id, rule_version, *, firing_delta,
                    true_delta, false_delta, observed_precision,
                    false_positive_rate)

Hint evidence type modifier:
  register_hint_evidence_types(types)
  unregister_hint_evidence_types(types)
  clear_hint_evidence_types()
```

Total: 40 public methods. No method outside this set is required by the playbook.

## 4. Eight playbook layers

Each layer answers ONE question. Layers may be skipped if the adapter has no input for them, but the order between layers should be preserved.

### 4.1 Identity layer

Question: 무엇에 대한 주장인가?

```text
- add_entity         claim subject 의 정체성 등록
- add_observation    어떤 관찰 사건에서 왔는지 등록
- add_relation       entity 간 관계 등록 (relation 단독 또는 evidence 와 함께)
```

Adapter must register identity objects BEFORE any Claim that references them. `subject_id` passed to `add_claim` must be an `entity_id` already returned by `add_entity`.

Notes:

```text
- add_observation 의 raw_ref_id 는 consumer-side resolver 결과 (int).
- add_observation 의 source_type 는 consumer-side registry 정수.
- add_relation 의 rule_id 와 reason_code 도 consumer-side integer.
  Relation 도 rule association tag 를 가진다.
```

### 4.2 Evidence layer

Question: 무엇을 근거로 삼는가?

```text
- add_evidence(claim_id, raw_ref_id, evidence_type, strength)
```

`strength` 는 adapter policy 가 translation 한 결과여야 한다. external retrieval similarity / scanner severity / LLM self-confidence / API score 를 그대로 넘기지 않는다 (PR42 §4, PR41 simulation).

순서 주의:

```text
add_evidence 는 add_claim 보다 *뒤* 에 호출된다.
이유: add_evidence 의 첫 인자가 claim_id 이기 때문.

따라서 evidence 가 "먼저 도착했더라도" Engine 에 넣을 때는
add_claim → add_evidence 순서로 호출한다.
```

Evidence 의미와 Claim 의미를 섞지 않는다. Evidence 는 Claim 을 지지하거나 반박하는 *근거 단위* 일 뿐, 그 자체가 판단 결과가 아니다.

### 4.3 Claim layer

Question: 어떤 판단 단위를 등록할 것인가?

```text
- add_claim(subject_id, claim_type, rule_id, rule_version,
            reason_code, *, base_confidence=0.5, status=0, flags=0)
```

매우 중요한 signature 사실:

```text
rule_id 와 rule_version 은 required (default 없음).
즉 모든 Claim 은 rule association tag 를 가진다.

"rule association" 은 "rule firing" 이 아니다.
ragcore.Engine 은 rule 을 자동으로 firing 하지 않는다.
fire_rule public method 는 존재하지 않는다.

rule_id / rule_version 의 역할은 audit trail / reproducibility /
RuleStats 집계 / rule version pinning 이다.
```

`base_confidence` 도 adapter policy 가 결정한다. PR41 LLM 시나리오에서 본 cap (≤ 0.5), severity-label 매핑, deterministic-source 의 ~1.0 등은 모두 adapter 측 정책의 결과이지 Engine 의 자동 보정이 아니다.

`status` 는 PR21-L lifecycle status integer. 기본 0 (`CLAIM_STATUS_CANDIDATE`) 로 시작하는 것이 안전한 default. CONFIRMED / REFUTED / DISPUTED 로의 진입은 lifecycle layer 에서 명시적 method 호출로 일어난다.

### 4.4 Gap layer

Question: 부족한 정보는 무엇인가?

```text
- add_gap(claim_id, gap_type, required_evidence_type, severity, rule_id)
- resolve_gaps_for_evidence(evidence_id)
- gap_resolution(gap_id)
- gaps_for_claim(claim_id) / get_gap(gap_id)
```

Gap 은 Claim 생성 이후에 attach 한다. 같은 evidence 가 등록되면 `resolve_gaps_for_evidence(evidence_id)` 로 자동 해소 시도된다.

```text
unresolved gap = information incomplete
unresolved gap ≠ contradiction
unresolved gap ≠ refutation
```

Gap 의 `severity` 는 0~1 사이 float. count modifier / gap modifier 와 함께 `compute_effective_confidence` 계산에 들어가므로, severity 가 1.0 에 가까울수록 더 강하게 confidence 를 attenuate 한다.

### 4.5 Contradiction layer

Question: 명시적으로 반대되는 증거가 있는가?

```text
- register_contradiction(claim_id, evidence_id)
- register_contradiction_resolution(claim_id, evidence_id)
- contradictions_for_claim(claim_id)
- active_contradictions_for_claim(claim_id)
- active_contradictions_by_freshness(claim_id)
- resolved_contradictions_for_claim(claim_id)
```

Contradiction 등록은 Evidence 등록의 *후행 단계* 다:

```text
1. add_evidence  -- 반대 증거를 일반 Evidence 로 등록
2. register_contradiction(claim_id, evidence_id)
                  -- 그 evidence_id 를 contradiction 으로 표시
```

Contradiction 등록 직후 lifecycle method 가 자동 호출되지 않는다. 다음 layer 에서 명시적으로 호출해야 한다.

Gap 과 Contradiction 의 분리는 §50.x / PR8 의 lifecycle 판단 삼각형과 일치한다 (unresolved gap 은 refuted 가 아니다).

### 4.6 Lifecycle layer

Question: 이미 등록된 상태를 바탕으로 lifecycle 을 전이시킬 수 있는가?

```text
- confirm_claim_if_ready(claim_id)
- dispute_claim_if_ready(claim_id)
- refute_claim_if_ready(claim_id)
- refute_disputed_claim_if_ready(claim_id)
- refute_disputed_claim_if_ready_by_freshness(claim_id)
- resolve_disputed_claim_if_ready(claim_id)
```

여섯 lifecycle method 는 모두 `_if_ready` 접미사를 가진다:

```text
의미:
  "ready 면 transition, 아니면 변화 없음"

따라서 lifecycle method 는 "판단 실행 버튼" 이 아니다.
adapter 가 자신의 등록 단계가 끝났다고 판단하는 시점에 호출하면,
Engine 이 현재 등록된 evidence / gap / contradiction 상태를 읽어
전이 조건을 적용한다.
```

대표 전이 흐름:

```text
candidate → confirmed              confirm_claim_if_ready
candidate → refuted                refute_claim_if_ready
confirmed → disputed               dispute_claim_if_ready
disputed → confirmed               resolve_disputed_claim_if_ready
disputed → refuted                 refute_disputed_claim_if_ready
disputed → refuted (freshness 기반) refute_disputed_claim_if_ready_by_freshness
```

호출 순서 권고:

```text
한 batch 의 evidence/gap/contradiction 등록이 끝난 뒤,
"가장 forward 방향" 전이 method 부터 호출한다.

예:
  새 supporting evidence 가 들어왔다면
    confirm_claim_if_ready
  새 contradicting evidence 가 들어왔다면
    dispute_claim_if_ready 또는 refute_claim_if_ready
  이미 disputed 상태에서 추가 evidence 가 들어왔다면
    resolve_disputed_claim_if_ready 또는
    refute_disputed_claim_if_ready[_by_freshness]
```

여러 lifecycle method 를 순서대로 호출해도 `_if_ready` 가드가 있어서 부적격 전이는 무시된다. 다만 의미가 헷갈리므로 adapter 는 한 batch 당 1~2개 정도만 호출하는 게 명확하다.

### 4.7 Confidence query layer

Question: 지금 등록된 상태 아래서 이 Claim 의 effective confidence 는?

```text
- compute_effective_confidence(claim_id) -> ScoreValue
```

해석 lock:

```text
허용 표현:
  engine confidence
  computed signal
  effective confidence
  decision-support signal

금지 표현:
  truth probability
  verified probability
  absolute risk probability
  "확률"
  "X% 확실"
```

값 구성 (PR36-PKG §48.7):

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
             ↑     ↑       ↑           ↑     ↑       ↑           ↑
             adapter PR21-L PR15 등    PR    PR     PR        PR (hint
             정책 결과                                          modifier 등)
```

modifier 7종은 PR34-O 이후 동결되었다. adapter 는 base × status × freshness × gap × count × rule_stats × evidence_type 의 *계산식* 을 가정하면 안 된다. 단지 "여러 modifier 가 곱해진 [0.0, 1.0] 값" 으로 사용한다.

### 4.8 Snapshot layer

Question: 지금 상태를 보존하거나 복원할 것인가?

```text
- to_snapshot() -> dict
- Engine.from_snapshot(snapshot) -> Engine     # classmethod
```

snapshot 의미:

```text
snapshot = state preservation
restore  = state reconstruction
restore ≠ rule re-run
restore ≠ lifecycle re-judgment
restore ≠ recompute effective_confidence from scratch
```

snapshot 의 top-level keys 18개는 PR36-PKG `_LOCKED_SNAPSHOT_TOP_LEVEL_KEYS` 로 잠겨 있다. schema_version 은 2 (PR21-L).

snapshot checkpoint 권장 시점:

```text
- 외부 output ingestion 직후
- claim/evidence/gap/relation 등록 직후
- lifecycle transition 직후
- consumer report 생성 직전
```

snapshot 은 adapter-owned storage 에 저장된다. ragcore 는 어떤 파일에도, 어떤 DB 에도 직접 쓰지 않는다 (PR40 §3.10 snapshot ownership policy).

## 5. Two-path model

PR43-C 는 consumer 가 사용할 수 있는 두 가지 path 를 명확히 나눈다.

### 5.1 Rule-associated path

```text
external output
→ adapter interpretation
→ register_rule(RuleDefinition)              # 한 번만 (재사용)
→ add_entity / add_observation / add_relation
→ add_claim(subject_id, claim_type,
            rule_id=<that rule>,
            rule_version=<that version>,
            reason_code, ...)
→ add_evidence(claim_id, raw_ref_id, evidence_type, strength)
→ add_gap / register_contradiction (필요 시)
→ resolve_gaps_for_evidence(evidence_id)     (자동 해소 시도)
→ <lifecycle>_if_ready(claim_id)
→ update_rule_stats(rule_id, rule_version, ...)  (재현성/통계)
→ compute_effective_confidence(claim_id)
→ to_snapshot()
```

특징:

```text
- consumer 가 rule logic 을 자체적으로 실행한 뒤 그 결과를 Claim 으로 등록
- Engine 은 rule "firing" 을 trigger 하지 않음 (fire_rule public method 없음)
- rule_id / rule_version 은 audit trail / RuleStats 집계 / reproducibility 용도
- 같은 rule 로 만들어진 Claim 들이 통계적으로 추적 가능
```

### 5.2 Direct claim path

```text
external output
→ adapter interpretation
→ register_rule(RuleDefinition)              # "manual" or "adapter-direct"
                                              # 라는 의도의 RuleDefinition 을
                                              # 한 번 등록
→ add_entity / add_observation / add_relation
→ add_claim(subject_id, claim_type,
            rule_id=<adapter-direct rule>,
            rule_version=<that version>,
            reason_code, ...)
→ add_evidence
→ add_gap / register_contradiction (필요 시)
→ <lifecycle>_if_ready(claim_id)
→ compute_effective_confidence(claim_id)
→ to_snapshot()
```

특징:

```text
- consumer 가 rule logic 을 실행하지 않고 adapter interpretation 결과를
  바로 Claim 으로 등록
- rule_id / rule_version 은 add_claim signature 의 required 인자이므로
  여전히 의미 있는 RuleDefinition 에 attach
  (예: "manual-analyst" 또는 "adapter-direct" 라는 의도의 rule)
- RuleStats 집계는 사용해도 되고 안 해도 됨
```

두 path 의 공통 제약:

```text
어느 path 든
  external output 을 곧바로 final verdict 로 쓰지 않는다.
  retrieval similarity 를 confidence 로 쓰지 않는다.
  scanner severity 를 Engine judgment 로 쓰지 않는다.
  LLM summary 를 evidence strength 로 자동 치환하지 않는다.
  Engine 이 자동으로 rule 을 firing 한다고 가정하지 않는다.
```

PR41 simulation tests 의 18 케이스는 두 path 모두를 cover 한다 (대부분 Direct claim path 형태, LLM 시나리오는 CANDIDATE-only cap 으로 자연스럽게 path 무관 invariant).

## 6. Recommended call order

기본 안전 default 호출 순서:

```text
 1. Engine 생성                 Engine()
 2. RuleDefinition 등록          register_rule(...)
    (Rule-associated 든 Direct 든 한 번씩 등록)
 3. Identity 등록                add_entity / add_observation
 4. Relation 등록                add_relation
                                  (Identity 와 Claim 사이; relation 자체에도
                                   rule_id 가 attach 됨)
 5. Claim 등록                   add_claim(subject_id, claim_type,
                                           rule_id, rule_version, ...)
 6. Evidence 등록                add_evidence(claim_id, ...)
                                  (supporting evidence 모두 batch)
 7. Gap 등록                     add_gap(claim_id, ...)
                                  (정보 부족 시)
 8. Contradiction 등록            add_evidence + register_contradiction
                                  (반대 증거가 있을 때)
 9. Gap 해소 시도                 resolve_gaps_for_evidence(evidence_id)
                                  (새 evidence 가 들어올 때마다)
10. Lifecycle 전이               <lifecycle>_if_ready(claim_id)
                                  (등록 단계가 끝났다고 판단되는 시점에)
11. RuleStats 갱신                update_rule_stats(...)
                                  (Rule-associated path 에서 필요 시)
12. Effective confidence 조회     compute_effective_confidence(claim_id)
13. 부가 query                    claim_lifecycle_history /
                                  gaps_for_claim /
                                  active_contradictions_for_claim 등
14. consumer 보고서 생성           (Engine 밖, adapter 책임)
15. Snapshot 저장                 to_snapshot()  →  adapter storage
```

이 순서는 strict global order 가 아니라 **safe default order** 다. 다음 invariant 만 깨지지 않으면 batch / 재정렬 가능:

```text
- add_claim 은 referenced subject (add_entity 결과) 이후에 호출된다.
- add_evidence 는 claim_id (add_claim 결과) 이후에 호출된다.
- add_gap 은 claim_id 이후에 호출된다.
- register_contradiction 은 claim_id + evidence_id 둘 다 이후에 호출된다.
- lifecycle method 는 의미 있는 등록이 끝난 뒤에 호출된다.
- compute_effective_confidence 는 final query layer 이며,
  그 결과를 다시 Engine 에 입력하지 않는다.
- snapshot 은 보존이지 재판단이 아니다.
```

## 7. Layer ↔ method mapping (one-page reference)

```text
Identity        add_entity / add_observation / add_relation
Evidence        add_evidence
Claim           add_claim
Gap             add_gap / resolve_gaps_for_evidence /
                gap_resolution / gaps_for_claim / get_gap
Contradiction   register_contradiction /
                register_contradiction_resolution /
                contradictions_for_claim /
                active_contradictions_for_claim /
                active_contradictions_by_freshness /
                resolved_contradictions_for_claim
Lifecycle       confirm_claim_if_ready /
                dispute_claim_if_ready /
                refute_claim_if_ready /
                refute_disputed_claim_if_ready /
                refute_disputed_claim_if_ready_by_freshness /
                resolve_disputed_claim_if_ready
Confidence      compute_effective_confidence
Snapshot        to_snapshot / from_snapshot (classmethod)
Read            get_claim / get_entity / get_evidence /
                get_observation / get_relation /
                evidences_for_claim / evidence_freshness /
                claim_lifecycle_history
Rule meta       register_rule / get_rule / get_rule_stats /
                update_rule_stats
Hint modifier   register_hint_evidence_types /
                unregister_hint_evidence_types /
                clear_hint_evidence_types
```

총 40 method. 모두 baseline `bcc2c7e` 의 `ragcore.Engine` 에 그대로 존재한다.

## 8. Invariants the playbook implies

168차에서 optional test 가 만들어진다면, 다음 중 일부를 잠그면 된다. 모두 "기존 public method 조합으로 끝까지 통과한다" 형태의 usage-level invariant 이지, modifier 결과 자체를 검사하지 않는다.

```text
1. Playbook examples use only existing Engine public methods.
2. No new ragcore public symbol is required by the playbook.
3. No engine source change is required by the playbook.
4. Rule-associated path: register_rule → add_entity → add_claim →
    add_evidence → <lifecycle>_if_ready → compute_effective_confidence
    sequence completes without engine modification.
5. Direct claim path: register_rule (adapter-direct) → add_entity →
    add_claim → add_evidence → <lifecycle>_if_ready →
    compute_effective_confidence sequence completes without engine
    modification.
6. Gap remains information incomplete, not contradiction
    (resolve_gaps_for_evidence does not raise nor toggle
     contradiction state).
7. Contradiction remains explicit conflict, not unresolved gap
    (register_contradiction does not create a Gap).
8. compute_effective_confidence remains in [0.0, 1.0] across both
    paths.
9. to_snapshot() → from_snapshot(snapshot) round-trip preserves
    compute_effective_confidence values for the same claim_ids.
10. Retrieval similarity / scanner severity / LLM self-confidence /
    API score is never used as add_evidence strength directly in
    any playbook example.
```

168차 test 작성 여부와 형태는 별도 결정. 본 guide 자체는 invariant 목록을 제시만 한다.

## 9. Pattern position

```text
1. Philosophy         docs/01_CORE_PHILOSOPHY.md
2. Runtime            docs/03_RUNTIME_LOOP.md
3. Contract           docs/contracts/05_DATA_CONTRACT_MVP.md §50
4. Audit              docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
5. Guide              docs/guides/ADAPTER_POLICY_GUIDE.md
6. Simulation         tests/test_external_adapter_simulation.py
7. Retrieval Guide    docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md
8. Call Playbook      docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md  (this)
```

8개 layer. PR40·PR42·PR43-C 가 guide 계열, PR41 이 simulation 계열, PR39 가 audit 계열, §50 이 contract 계열, philosophy/runtime 이 원칙/순서 계열.

## 10. What this guide does NOT do

PR43-C 는 의도적으로 다음을 하지 않는다:

```text
- 새 Engine method 추가
- 기존 Engine method signature 변경
- modifier 공식 변경
- threshold / scoring calibration 변경
- 도메인 taxonomy 정의 (entity_type / claim_type / evidence_type /
  observation_type / source_type / reason_code / gap_type /
  relation_type 정수 의미는 consumer-side)
- vector DB / graph DB / LLM / SQL / file / API 구현
- adapter 구현
- Cerberus 또는 V-cerberus 진입
- contract §51 신설 (guide-first cycle; contract 승격은 별도 결정)
- ragcore.__all__ 추가
- engine.py / types.py / __init__.py / rule_output.py 수정
- 새 snapshot schema version
- 새 public API
- PR44-D / PR44-E 자동 제안
```

## 11. Followup candidates (still NOT PR-numbered)

```text
PR44-D Anti-patterns Guide               (Candidate D)
PR44-E Domain-neutral Reference Flow     (Candidate E)
consumer adapter implementation          (별도, 자동 진입 아님)
```

PR43-C merge 이후 위 세 가지는 자동 예약되지 않는다. 사용자 결정.

## 12. Closing meaning

```text
PR43-C turns PR42's retrieval interpretation guide into a safe
Engine public-method call order for external consumers.

It describes WHEN to call which of the 40 public methods, without
adding a single new one.

PR43-C closes the method-call playbook layer.
It does not implement a consumer adapter.
It does not change Engine judgment semantics.
```

Locked closing sentences:

```text
PR43-C 는 새 Engine 동작을 추가하는 PR 이 아니다.
PR43-C 는 외부 consumer 가 기존 ragcore.Engine public method 40 개를
어떤 순서로 호출하면 안전하게 상태를 등록할 수 있는지 정리한 call-order
guide 다.

Engine 은 rule 을 자동으로 firing 하지 않는다.
모든 Claim 은 rule association tag 를 가진다.
compute_effective_confidence 는 truth probability 가 아니라
decision-support signal 이다.
Snapshot 은 state preservation 이지 재판단이 아니다.
```

No automatic next-PR proposal. User decides direction.
