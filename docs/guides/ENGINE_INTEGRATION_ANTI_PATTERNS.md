# Engine Integration Anti-patterns

Status: guide (PR44-D, Candidate D)
Baseline: main `f9fbed8` (PR43-C merged)
Type: documentation-only negative-boundary guide, no implementation, no runtime enforcement, no new tests

## 0. Scope limitation (locked, user 2026-05-23)

```text
PR44-D names unsafe integration patterns.
It does not add runtime enforcement.
It does not implement adapters.
It does not change Engine judgment semantics.
```

한국어:

```text
PR44-D 는 Engine 통합 시 절대 하면 안 되는 misuse / boundary
violation 에 이름을 붙여 정리한다.

Engine 에 새 runtime check 를 추가하지 않는다.
새 test 를 추가하지 않는다 (PR41 simulation 과 PR43-C 168차 12
invariant 가 이미 실행 시점 가드를 제공한다).
adapter 를 구현하지 않는다.
contract §51 을 만들지 않는다.
Engine 판단 의미론을 바꾸지 않는다.
```

PR44-D closes Candidate D from the post-PR41 followup list. PR43-C documented the positive call-order playbook. PR44-D documents the *negative* boundary — what NOT to do when integrating against the Engine, named so each anti-pattern can be referenced in code review and post-mortems.

## 1. Layer position

```text
PR39    compatibility audit                — Engine 호환 검증
PR40    adapter policy decisions           — adapter 결정면 10 정책
PR41    simulation tests                    — fake output → Engine 흐름 executable
PR42    retrieval translation guide         — retrieval output → Evidence 의미
PR43-C  method call playbook               — Engine public method 호출 순서
PR44-D  integration anti-patterns          — misuse / boundary violation 이름 (this)
```

PR44-D is the **negative** counterpart to PR43-C. PR43-C says "do this." PR44-D says "do not do these, and here is why."

## 2. Locked principles (the four)

```text
PR44-D names unsafe integration patterns.
It does not add runtime enforcement.
It does not implement adapters.
It does not change Engine judgment semantics.
```

These four sentences are the §0 lock. Every anti-pattern in this guide must be readable as a naming claim, not as a future Engine guard.

Inherited from:

```text
docs/01_CORE_PHILOSOPHY.md
docs/03_RUNTIME_LOOP.md
docs/contracts/05_DATA_CONTRACT_MVP.md §50
docs/guides/ADAPTER_POLICY_GUIDE.md         (PR40)
tests/test_external_adapter_simulation.py   (PR41)
docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md (PR42)
docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md  (PR43-C)
tests/test_engine_method_call_playbook_usage.py (PR43-C 168차)
```

## 3. Reading conventions

Every anti-pattern in §4 and §5 uses the same 6-field structure:

```text
Name                — short stable ID (e.g., AP-I-1, AP-X-3)
Symptom             — how the misuse looks in code or behavior
Why it is wrong     — which locked framework principle it breaks
Correct alternative — pointer to PR43-C / PR42 / §50 / PR40 / PR41
Detection cue       — what to look for in code review
Related test or prior guard
                    — which existing test / contract / guide would
                      already catch this (or has already named it)
```

Anti-pattern IDs follow a stable scheme:

```text
AP-I-*    Identity layer
AP-E-*    Evidence layer
AP-C-*    Claim layer
AP-G-*    Gap layer
AP-CT-*   Contradiction layer
AP-L-*    Lifecycle layer
AP-CF-*   Confidence layer
AP-S-*    Snapshot layer
AP-X-*    Cross-cutting
```

IDs are stable so external reviewers can reference them in PR comments without re-quoting the whole anti-pattern.

---

## 4. Layer-based anti-patterns

### 4.1 Identity layer

#### AP-I-1 — Claim before Entity

```text
Symptom:
  add_claim(subject_id=<some int>, ...) is called with a subject_id
  that was never returned by add_entity. The integer was made up,
  copied from an external DB key, or pulled from a registry that
  the Engine does not know about.

Why it is wrong:
  Claim.subject_id is expected to refer to an Engine-resident
  Entity. A snapshot of this state will reference a phantom
  entity_id; downstream queries (get_entity / get_claim joined
  reads) will be incoherent.

Correct alternative:
  PR43-C §4.1 / §6 step 3 — call add_entity first, store the
  returned id, then use it as subject_id.

Detection cue:
  subject_id 인자에 magic number / 외부 DB key / 외부 string id 의
  hash 가 직접 들어감. 같은 메서드 안에서 add_entity 호출이 없음.

Related test or prior guard:
  PR43-C 168차 test_full_path_completes_through_query_and_snapshot
  (Rule-associated path 와 Direct claim path 모두 add_entity →
  add_claim 순서를 사용).
```

#### AP-I-2 — Observation skipped

```text
Symptom:
  External output is converted directly into Claim + Evidence with
  no add_observation call. There is no record of which observation
  event produced this evidence.

Why it is wrong:
  Engine cannot reconstruct provenance. PR40 §3.1 requires the
  adapter to register an Observation per retrieval / call / read
  event so the trail from external source → Claim is auditable.

Correct alternative:
  PR43-C §4.1 — add_observation(entity_id, raw_ref_id,
  observation_type, source_type) before promoting to Claim /
  Evidence.

Detection cue:
  add_claim / add_evidence 가 같은 함수에 있는데 add_observation
  은 없음. external API response 가 add_evidence 인자로 즉시 흘러감.

Related test or prior guard:
  PR40 ADAPTER_POLICY_GUIDE.md §3.1 (Subject granularity policy)
  PR42 RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md §6~§12
  (each retrieval type lists Observation as a possible Engine
   target).
```

### 4.2 Evidence layer

#### AP-E-1 — Raw evidence content stored in Engine

```text
Symptom:
  Chunk text, SQL row JSON, API response body, or LLM output
  text is somehow attached to an Evidence (or persisted alongside
  Engine state) instead of being kept in consumer-side storage.

Why it is wrong:
  ragcore is not a content store. PR42 §13 and §50 require raw
  retrieved content to remain outside ragcore; the Engine holds
  only raw_ref_id (int). PR40 §3.10 places snapshot ownership
  on the consumer.

Correct alternative:
  PR42 §13 — adapter keeps raw content in its own store;
  raw_ref_id is the only bridge into Engine state.

Detection cue:
  add_evidence 호출 주변에 text / blob / json.dumps 같은 변수가
  Engine 으로 흘러들어가는 흔적. raw_ref_id 가 외부 string 그대로
  쓰여 후에 reverse-resolve 가 불가능한 모양.

Related test or prior guard:
  PR42 RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md
  §6~§12 "Must remain outside ragcore" 항목.
  PR40 §3.10 Snapshot ownership policy.
```

#### AP-E-2 — Evidence before Claim

```text
Symptom:
  add_evidence is called with a claim_id that has not yet been
  returned by add_claim — for example with a placeholder integer,
  with the value 0, or with an id from a different Engine
  instance.

Why it is wrong:
  add_evidence(claim_id, raw_ref_id, evidence_type, strength)
  expects claim_id to be a live Claim in this Engine. The
  playbook (PR43-C §6) is ordered add_claim → add_evidence for
  this reason.

Correct alternative:
  PR43-C §6 step 5 then step 6 — register Claim first; use the
  returned claim_id for every Evidence registration.

Detection cue:
  add_evidence 호출에 claim_id 가 변수로 들어가는데 그 변수가
  add_claim 결과가 아닌 placeholder / 0 / 외부 id.

Related test or prior guard:
  PR43-C 168차 test_full_path_completes_through_query_and_snapshot
  (Engine raises if claim_id is unknown; the playbook examples
  never depend on this error path but rely on the ordering).
```

### 4.3 Claim layer

#### AP-C-1 — Silent duplicate claim creation

```text
Symptom:
  The same (subject_id, claim_type) pair is added by add_claim
  multiple times — once per external observation — without
  consumer-side dedup. Each call creates a new Claim row.

Why it is wrong:
  Engine does NOT dedup claims; that policy lives in PR40 §3.7
  (Claim creation policy) on the adapter side. Silent duplicates
  pollute lifecycle history, double-count evidence, and confuse
  RuleStats.

Correct alternative:
  PR40 §3.7 — adapter decides "new claim vs. add_evidence to
  existing claim" before calling Engine. Dedup index lives in
  consumer storage, not Engine.

Detection cue:
  add_claim 가 retrieval 루프 안에서 무조건 호출됨. 같은
  (subject_id, claim_type) 에 대한 사전 조회 없음.

Related test or prior guard:
  PR40 ADAPTER_POLICY_GUIDE.md §3.7.
  PR43-C §4.3 ("Claim 은 final verdict 가 아니라 Engine state 의
  판단 단위").
```

#### AP-C-2 — rule_id=0 misread as "no rule association"

```text
Symptom:
  Code or documentation interprets rule_id=0 as "this claim is
  unrelated to any rule" and uses it without registering any
  RuleDefinition that the sentinel refers to.

Why it is wrong:
  rule_id and rule_version are required positional fields on
  add_claim (no default). They are association tags, not opt-out
  flags. PR43-C §5 Direct claim path explicitly requires the
  adapter to register an "adapter-direct" RuleDefinition (or to
  reuse a documented sentinel) so the tag has a known meaning.

Correct alternative:
  PR43-C §5.2 — register a single intentional RuleDefinition
  (e.g., maturity=EXPERIMENTAL, prior_confidence chosen by
  policy) and use its id/version as the tag for direct claims.

Detection cue:
  rule_id=0, rule_version=0 가 코드 곳곳에 magic number 처럼
  흩어져 있고 register_rule 호출이 한 번도 없음.

Related test or prior guard:
  PR43-C §5.1 / §5.2 / §4.3 (signature lock).
  PR40 §3.7 Claim creation policy.
```

### 4.4 Gap layer

#### AP-G-1 — Gap interpreted as refutation

```text
Symptom:
  Consumer code or report text treats an unresolved Gap as
  "the claim is disproven" — for example by flipping a Claim to
  REFUTED whenever a Gap is open.

Why it is wrong:
  PR43-C §4.4 / PR8 lifecycle 판단 삼각형 / §50.x:
    unresolved gap = information incomplete
    unresolved gap ≠ contradiction
    unresolved gap ≠ refutation
  A Gap is a *missing input*, not a counter-claim.

Correct alternative:
  Treat Gap as "needs more evidence." Refutation requires
  registered contradicting Evidence and an explicit
  refute_*_if_ready call (PR43-C §4.5 / §4.6).

Detection cue:
  gaps_for_claim 결과를 보고 refute_claim_if_ready 를 호출하는
  코드. 보고서 텍스트에 "gap 발견 → 취약점 부재 확정" 같은 표현.

Related test or prior guard:
  PR43-C 168차 test_gap_layer_does_not_create_contradictions.
  PR43-C 168차 test_contradiction_layer_does_not_create_gaps.
```

#### AP-G-2 — Manual gap resolution that skips evidence

```text
Symptom:
  Consumer attempts to "close" a Gap by directly mutating Engine
  state or by calling lifecycle methods without first registering
  the supporting Evidence that ought to resolve the Gap.

Why it is wrong:
  Engine resolves Gaps through resolve_gaps_for_evidence
  (PR43-C §4.4), which requires a registered Evidence. Bypassing
  this leaves the Gap visible but without the evidence trail that
  justified its resolution.

Correct alternative:
  PR43-C §6 step 9 — register the resolving Evidence first;
  call resolve_gaps_for_evidence(evidence_id); then proceed with
  lifecycle transitions.

Detection cue:
  gap_resolution(...) 결과를 무시한 채 confirm_claim_if_ready 가
  호출되는 코드. resolve_gaps_for_evidence 호출이 누락.

Related test or prior guard:
  PR43-C 168차 test_full_path_with_gap_resolution_completes.
```

### 4.5 Contradiction layer

#### AP-CT-1 — Contradiction registered but no lifecycle transition

```text
Symptom:
  register_contradiction is called; the consumer assumes the
  Claim is automatically demoted (CONFIRMED → DISPUTED, or
  CANDIDATE → REFUTED). No lifecycle method is invoked.

Why it is wrong:
  PR43-C §4.5 / §4.6 — register_contradiction records the
  conflict but Engine does NOT auto-transition. The consumer must
  explicitly call dispute_claim_if_ready / refute_claim_if_ready
  (or the disputed-state variants) after the contradiction is
  registered.

Correct alternative:
  PR43-C §6 step 8 → step 11 — add_evidence + register_contradiction,
  then call the appropriate *_if_ready method for the target
  transition.

Detection cue:
  register_contradiction 직후 compute_effective_confidence 만
  바로 호출되고 lifecycle 호출이 없음. 보고서에서 "contradiction
  detected = vulnerability cleared" 같은 표현.

Related test or prior guard:
  PR43-C 168차 test_full_path_with_contradiction_completes
  (dispute_claim_if_ready 가 명시적으로 호출됨).
```

#### AP-CT-2 — Contradiction substituted by Gap

```text
Symptom:
  When evidence directly conflicts with a Claim, the consumer
  records a Gap ("we're missing something") instead of registering
  the conflict as a Contradiction.

Why it is wrong:
  Gap and Contradiction are not interchangeable (PR43-C §4.4 /
  §4.5). A Gap weakens confidence as "missing info"; a
  Contradiction triggers lifecycle paths via the dispute / refute
  helpers. Misclassification distorts both effective_confidence
  and claim_lifecycle_history.

Correct alternative:
  If there is registered Evidence that contradicts the Claim, use
  register_contradiction + a lifecycle helper. Reserve add_gap
  for genuinely *missing* required_evidence_type.

Detection cue:
  add_gap 호출 직전에 명백히 "opposing" semantics 의 add_evidence
  가 있음. require evidence_type 이 실제 "missing" 이 아니라
  "found but opposing".

Related test or prior guard:
  PR43-C §4.4 / §4.5.
  PR43-C 168차 test_gap_layer_does_not_create_contradictions /
  test_contradiction_layer_does_not_create_gaps.
```

### 4.6 Lifecycle layer

#### AP-L-1 — Assuming Engine auto-fires lifecycle transitions

```text
Symptom:
  Consumer assumes that registering Evidence (or Contradiction,
  or Gap) automatically transitions the Claim status. No
  lifecycle method is called.

Why it is wrong:
  PR43-C §4.6 — Engine is explicit. Status transitions happen
  ONLY when one of the six *_if_ready helpers is invoked AND its
  internal readiness check returns True.

Correct alternative:
  PR43-C §6 step 11 — after evidence / contradiction batches,
  call the appropriate *_if_ready helper(s) explicitly.

Detection cue:
  add_evidence / register_contradiction 직후 compute_effective_confidence
  만 호출하고, *_if_ready 호출이 코드 어디에도 없음. lifecycle
  history 가 비어 있는데 보고서가 "confirmed" 라고 적힘.

Related test or prior guard:
  PR43-C 168차 test_full_path_with_contradiction_completes 가
  dispute_claim_if_ready 를 explicit 하게 호출.
```

#### AP-L-2 — Treating `_if_ready` return value as transition guarantee

```text
Symptom:
  Consumer calls confirm_claim_if_ready and assumes True was
  returned, or ignores the return value entirely and treats the
  Claim as confirmed regardless of whether the transition
  actually fired.

Why it is wrong:
  PR43-C §4.6 — the `_if_ready` suffix is literal. If the
  readiness check fails, the method returns False and no
  transition happens. Lifecycle history will not contain the
  expected event.

Correct alternative:
  Either check the boolean return and branch on it, or query
  claim_lifecycle_history to confirm the transition actually
  occurred before downstream reporting.

Detection cue:
  `confirm_claim_if_ready(...)` 의 반환값을 `_` 로 받거나 그냥
  버림. 그 직후 "claim confirmed" 가정.

Related test or prior guard:
  PR43-C §4.6.
  PR43-C 168차 tests are deliberately lenient on return values
  (they verify the method does not raise, not whether transition
  fired) — consumers must enforce their own check.
```

### 4.7 Confidence layer

#### AP-CF-1 — effective_confidence read as "truth probability"

```text
Symptom:
  Reports or UI labels read like "this finding is 87% likely to
  be true" / "87% verified" / "probability of vulnerability:
  0.87." The number being shown is compute_effective_confidence.

Why it is wrong:
  PR43-C §4.7 / §2 / §50 — compute_effective_confidence is a
  decision-support signal composed of seven modifiers. It is not
  a calibrated probability, not a Bayesian posterior, not a
  verified-vulnerability rate.

Correct alternative:
  Use neutral phrasing:
    "engine confidence 0.87"
    "computed signal 0.87"
    "effective confidence 0.87"
  Translate to domain language only with explicit qualifiers
  ("internal score," "support signal," etc.).

Detection cue:
  보고서 / UI 에서 effective_confidence 값 뒤에 "%", "확률",
  "verified", "absolute", "posterior" 같은 단어가 따라옴.

Related test or prior guard:
  PR43-C §4.7 (the lock-list of allowed and forbidden phrasings).
```

#### AP-CF-2 — Static threshold cutoff treated as ground truth

```text
Symptom:
  Consumer hardcodes a threshold (e.g., `if effective >= 0.7:
  mark_vulnerable()`) without exposing it as configurable policy,
  and treats the cutoff as if it were the framework's decision.

Why it is wrong:
  PR40 §3.5 / §3.6 — confidence-to-decision policy lives on the
  consumer side. The Engine does not bless any threshold.
  Hardcoding the cutoff in adapter code hides a policy choice
  that belongs in adapter configuration / documentation.

Correct alternative:
  Move thresholds to adapter policy (config file, registry,
  policy module). Document why the cutoff exists; allow callers
  to override.

Detection cue:
  `>= 0.7`, `> 0.85` 등 literal float 가 adapter 의 hot path 에
  magic number 로 박혀 있고 config / docs 에 설명이 없음.

Related test or prior guard:
  PR40 §3.5 Confidence translation policy /
  §3.6 Evidence strength policy.
```

### 4.8 Snapshot layer

#### AP-S-1 — Treating from_snapshot as "re-judgment"

```text
Symptom:
  After Engine.from_snapshot(snapshot), the consumer re-fires
  rules, re-calls lifecycle methods, or re-computes
  effective_confidence under the assumption that restore is a
  recomputation step.

Why it is wrong:
  PR43-C §4.8 / §2 — restore is state reconstruction. Snapshot
  preserves the exact Engine state at the time of capture;
  reading it back does not re-evaluate anything, and the consumer
  should not pretend it does.

Correct alternative:
  Use from_snapshot to *resume* from a captured state. If
  re-judgment is desired, rebuild from raw inputs through the
  full PR43-C call order — do not piggyback on restore.

Detection cue:
  from_snapshot 직후 confirm_claim_if_ready / 다른 lifecycle
  helpers 가 일제히 호출됨. snapshot restore 가 "trigger" 처럼
  쓰이는 코드.

Related test or prior guard:
  PR43-C 168차 test_snapshot_roundtrip_preserves_effective_confidence
  (round-trip 후 동일한 effective_confidence 가 유지됨 — 재판단
  없음을 executable 하게 확인).
```

#### AP-S-2 — Assuming Engine persists snapshots autonomously

```text
Symptom:
  Consumer code expects Engine to write snapshots to disk, S3,
  or any storage of its own. There is no explicit to_snapshot()
  call and no consumer-side persistence routine.

Why it is wrong:
  PR40 §3.10 / PR43-C §4.8 — snapshot ownership is consumer-side.
  to_snapshot() returns a dict; the Engine never touches a file
  system, network, or database.

Correct alternative:
  Adapter explicitly calls to_snapshot(), serializes the dict
  (JSON / pickle / blob storage / etc.) into adapter-owned
  storage, and recalls it via from_snapshot(snapshot).

Detection cue:
  코드에 to_snapshot 호출이 없는데 "engine state 가 어디에 저장된다"
  는 가정. ragcore source 에 file IO 추가 PR 요청.

Related test or prior guard:
  PR40 §3.10 Snapshot ownership policy.
  168차 test_snapshot_roundtrip_preserves_effective_confidence
  (snapshot is a value, not a side effect).
```

---

## 5. Cross-cutting anti-patterns

### 5.1 AP-X-1 — External score identity-pipe

```text
Symptom:
  add_evidence(..., strength=similarity_score) where
  similarity_score is a raw retrieval relevance value. Or
  add_claim(..., base_confidence=severity_value) where severity_value
  is a scanner-reported severity (CVSS, custom 0~1, etc.) passed
  through unchanged.

Why it is wrong:
  PR41 §50.9 / §50.10 / PR42 §4 — retrieval relevance and
  external scoring are not Engine confidence. Identity-piping
  fails the executable invariant locked in PR41 simulation tests
  and PR43-C 168차 test_translation_function_is_not_identity.

Correct alternative:
  Adapter applies a documented non-identity translation. PR40
  §3.5 / §3.6 — confidence translation policy is consumer-owned;
  the function MUST be non-identity for any of: similarity,
  path_score, api_score, LLM model confidence, severity label.

Detection cue:
  retrieval API result 변수가 그대로 strength / base_confidence
  인자에 흘러들어감. 변환 함수가 존재하지 않거나, 존재하더라도
  `return score` 같은 identity 형태.

Related test or prior guard:
  PR41 simulation §50.9 / §50.10 enforce non-identity for 5
  translation types.
  PR43-C 168차 test_translation_function_is_not_identity
  enforces it for the playbook example.
```

### 5.2 AP-X-2 — fire_rule misuse

```text
Symptom:
  Consumer code attempts `engine.fire_rule(...)` (does not exist),
  or calls `ragcore.fire_rule(...)` (a module-level rule
  evaluator) and treats its return value as if it mutated Engine
  state.

Why it is wrong:
  PR43-C §4.3 / §5.1 / 168차 test_engine_class_has_no_fire_rule_method:
    Engine.fire_rule instance method:        does not exist
    ragcore.fire_rule module-level function: exists but only
        evaluates rule logic; it does not mutate Engine state.
  Consumers that rely on either misread the boundary.

Correct alternative:
  PR43-C §5.1 Rule-associated path — consumer runs rule logic on
  its own side (optionally using ragcore.fire_rule as a helper),
  and registers the result via add_claim with rule_id / rule_version.

Detection cue:
  `engine.fire_rule(...)` 호출. ragcore.fire_rule 결과를 그대로
  Claim "확정" 으로 처리. test 가 `hasattr(Engine, "fire_rule")`
  를 가정.

Related test or prior guard:
  PR43-C 168차 test_engine_class_has_no_fire_rule_method.
```

### 5.3 AP-X-3 — rule_id / rule_version tag misunderstanding

```text
Symptom:
  Adapter treats rule_id and rule_version as optional, random,
  or as a "tracking field" with no semantic discipline. Different
  values used for the same Claim semantics in different runs.

Why it is wrong:
  PR43-C §4.3 — rule_id and rule_version are required positional
  arguments and the basis for audit trail, RuleStats aggregation,
  and reproducibility. Inconsistent tagging silently breaks all
  three.

Correct alternative:
  PR40 §3.7 Claim creation policy — adapter publishes a stable
  catalog of RuleDefinition (id, version, maturity,
  prior_confidence). Every Claim uses an entry from that catalog.
  Direct-claim path uses a documented "adapter-direct" entry.

Detection cue:
  rule_id 값이 random / time-based / `uuid.uuid4().int` 같은
  형태. 같은 의미의 Claim 이 매번 다른 rule_id 로 등록됨. register_rule
  호출이 한 번도 없음.

Related test or prior guard:
  PR40 §3.7.
  PR43-C §4.3 (signature lock).
```

### 5.4 AP-X-4 — compute_effective_confidence as truth probability

```text
Symptom:
  Same shape as AP-CF-1 but escaping the confidence-layer naming
  into general consumer code: e.g., a function literally named
  `vulnerability_probability(engine, claim_id)` that returns
  compute_effective_confidence directly.

Why it is wrong:
  PR43-C §4.7 / §2 — naming the value "probability" promotes the
  decision-support signal into a calibrated probability claim,
  which it is not. The misuse spreads through the report layer
  and out to end users / customers.

Correct alternative:
  Name the return value neutrally (engine_confidence,
  computed_signal, effective_confidence). Translate to domain
  phrasing only with explicit qualifier text.

Detection cue:
  함수 / 변수 / column 이름에 "probability", "probability_of_*",
  "verified", "truth", "absolute" 가 effective_confidence 값과
  직접 결합되어 있음.

Related test or prior guard:
  PR43-C §4.7 (forbidden phrasing list).
  See also AP-CF-1 (same misuse at the consumer code level).
```

### 5.5 AP-X-5 — Snapshot re-judgment misuse

```text
Symptom:
  Cross-cutting form of AP-S-1: snapshot files are used as a
  *trigger* for re-running judgment pipelines elsewhere in the
  consumer system. "Restore the snapshot, then re-fire all
  rules" is documented as a recovery procedure.

Why it is wrong:
  PR43-C §4.8 / §2 — snapshot is state preservation. Restore
  yields the same Engine state, including the same lifecycle
  history and the same effective_confidence values, without
  recomputing anything. Treating restore as a trigger erases the
  audit trail.

Correct alternative:
  Snapshot for resume. For re-judgment, replay raw inputs
  through PR43-C §6 from scratch into a fresh Engine.

Detection cue:
  Runbook 에 "snapshot 로드 후 confirm 다시 호출" 같은 절차.
  CI 에서 snapshot 을 매번 from_snapshot → re-fire-loop 으로
  돌리는 패턴.

Related test or prior guard:
  PR43-C 168차 test_snapshot_roundtrip_preserves_effective_confidence.
  See also AP-S-1 (snapshot-layer form).
```

### 5.6 AP-X-6 — Domain vocabulary intrusion into ragcore source

```text
Symptom:
  A PR proposes adding domain-specific names into ragcore source —
  CerberusFinding, SSHFinding, NmapResult, CVERecord, AssetIP,
  ServicePort, or any other vocabulary tied to a single consumer's
  problem domain.

Why it is wrong:
  ragcore is a generic judgment engine (direction_rag_framework_rag_agnostic).
  Cerberus is the first consumer, not the framework's baseline.
  Naming a domain concept inside ragcore silently makes that
  domain the framework's reference point and breaks RAG-agnostic
  identity.

Correct alternative:
  Domain vocabulary lives on the adapter side. Use integer
  registries (entity_type / claim_type / evidence_type /
  observation_type / source_type / reason_code / gap_type /
  relation_type) — the integers themselves are consumer-owned;
  ragcore never knows what they mean.

Detection cue:
  ragcore/ 안의 코드에 cerberus / ssh / cve / nmap / port / scan
  / asset 같은 단어. ragcore/ 안에서 enum / dataclass 이름이
  도메인 어휘.

Related test or prior guard:
  §50 External Knowledge Adapter Boundary.
  PR38-A external_consumer_probe (domain-neutral framing).
  Memory: direction_rag_framework_rag_agnostic.md /
  direction_rag_framework_adapter_contract.md.
```

### 5.7 AP-X-7 — adapter-specific symbol promoted into ragcore.__all__

```text
Symptom:
  A PR attempts to add adapter-bound symbols — chroma_client,
  open_ai_provider, vector_db_engine, scanner_runner,
  cerberus_finding_loader — to ragcore.__all__.

Why it is wrong:
  PR31-S froze ragcore.__all__ at 48 symbols. PR36-PKG locked
  this via _LOCKED frozensets. PR43-C 168차
  test_ragcore_all_remains_48_symbols enforces the count and
  uniqueness. Promoting adapter symbols would silently expand
  the contract surface.

Correct alternative:
  Consumer exports its own symbols from its own package. The
  Engine surface stays at 40 methods / 48 public symbols.

Detection cue:
  ragcore/__init__.py 수정 PR. ragcore.__all__ 에 외부 라이브러리
  이름 추가 시도. 168차 test 실행 시 48 카운트 실패.

Related test or prior guard:
  PR43-C 168차 test_ragcore_all_remains_48_symbols.
  PR36-PKG _LOCKED_* frozensets.
```

### 5.8 AP-X-8 — Private state / helper / constant dependence

```text
Symptom:
  Consumer code reads engine._claims, engine._rule_definitions,
  engine._compute_*_modifier, ragcore.engine._SOME_INTERNAL_CONST,
  or any other underscore-prefixed identifier. Maybe via
  monkeypatching, maybe via direct attribute access in a hot path.

Why it is wrong:
  PR36-PKG locked the public method surface at 40. Anything
  beginning with _ is implementation detail and may change in
  any PR without notice. Depending on private state breaks the
  contract surface and freezes ragcore's internal evolution.

Correct alternative:
  Use only the 40 public methods documented in PR43-C §3 / §7.
  If a query is missing, raise it as a feature request — do not
  reach into private state.

Detection cue:
  코드 grep 에서 `engine\._`, `ragcore\.engine\._`, `Engine\.\w*\._`
  패턴이 잡힘. test 가 private attribute 의 존재 / 값에 의존.

Related test or prior guard:
  PR43-C 168차 test_playbook_uses_only_existing_engine_public_methods.
  PR43-C 168차 test_engine_public_method_surface_is_40.
```

---

## 6. Anti-pattern index (one-page reference)

```text
Identity layer
  AP-I-1   Claim before Entity
  AP-I-2   Observation skipped

Evidence layer
  AP-E-1   Raw evidence content stored in Engine
  AP-E-2   Evidence before Claim

Claim layer
  AP-C-1   Silent duplicate claim creation
  AP-C-2   rule_id=0 misread as "no rule association"

Gap layer
  AP-G-1   Gap interpreted as refutation
  AP-G-2   Manual gap resolution that skips evidence

Contradiction layer
  AP-CT-1  Contradiction registered but no lifecycle transition
  AP-CT-2  Contradiction substituted by Gap

Lifecycle layer
  AP-L-1   Assuming Engine auto-fires lifecycle transitions
  AP-L-2   Treating _if_ready return value as transition guarantee

Confidence layer
  AP-CF-1  effective_confidence read as "truth probability"
  AP-CF-2  Static threshold cutoff treated as ground truth

Snapshot layer
  AP-S-1   Treating from_snapshot as "re-judgment"
  AP-S-2   Assuming Engine persists snapshots autonomously

Cross-cutting
  AP-X-1   External score identity-pipe
  AP-X-2   fire_rule misuse
  AP-X-3   rule_id / rule_version tag misunderstanding
  AP-X-4   compute_effective_confidence as truth probability
  AP-X-5   Snapshot re-judgment misuse
  AP-X-6   Domain vocabulary intrusion into ragcore source
  AP-X-7   adapter-specific symbol promoted into ragcore.__all__
  AP-X-8   Private state / helper / constant dependence
```

24 named anti-patterns. 16 layer-based + 8 cross-cutting.

## 7. Pattern position

```text
1. Philosophy           docs/01_CORE_PHILOSOPHY.md
2. Runtime              docs/03_RUNTIME_LOOP.md
3. Contract             docs/contracts/05_DATA_CONTRACT_MVP.md §50
4. Audit                docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
5. Guide (policy)       docs/guides/ADAPTER_POLICY_GUIDE.md            (PR40)
6. Simulation            tests/test_external_adapter_simulation.py     (PR41)
7. Guide (retrieval)    docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md  (PR42)
8. Guide (call order)   docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md     (PR43-C)
   + usage invariants    tests/test_engine_method_call_playbook_usage.py
9. Guide (anti-patterns) docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md (PR44-D, this)
```

PR44-D is the ninth document layer, sitting alongside PR43-C — positive playbook (PR43-C) and negative boundary (PR44-D) form a matched pair.

## 8. What this guide does NOT do

PR44-D 는 의도적으로 다음을 하지 않는다:

```text
- 새 Engine method 추가
- 기존 Engine method signature 변경
- modifier 7종 공식 변경
- threshold / scoring calibration 변경
- runtime validation / runtime reject 추가 (Engine 은 여전히
  adapter-boundary 가 enforce; 런타임 enforcement 없음)
- 도메인 taxonomy 정의
- vector DB / graph DB / LLM / SQL / file / API 구현
- adapter 구현
- Cerberus 또는 V-cerberus 진입
- contract §51 신설
- ragcore.__all__ 추가
- engine.py / types.py / __init__.py / rule_output.py 수정
- 새 snapshot schema version
- 새 public API
- 새 tests 추가 (PR41 + PR43-C 168차 가 이미 실행 시점 가드 제공)
- PR45-E 자동 제안
```

## 9. Followup candidates (still NOT PR-numbered)

```text
PR45-E Domain-neutral Reference Flow    (Candidate E)
consumer adapter implementation          (별도, 자동 진입 아님)
```

After PR44-D merges, neither is scheduled. PR44-D does NOT auto-propose them. User decides next direction.

## 10. Closing meaning

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

Engine 에 새 runtime enforcement 를 추가하지 않는다.
새 test 를 추가하지 않는다.
adapter 를 구현하지 않는다.
Engine 판단 의미론을 바꾸지 않는다.
```

No automatic next-PR proposal. User decides direction.
