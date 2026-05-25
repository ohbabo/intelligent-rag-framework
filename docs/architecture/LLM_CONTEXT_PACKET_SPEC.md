# LLM Context Packet Spec

Status: spec document (PR52)
Baseline: main `8eaec55` (PR51 merged)
Type: doc-only spec, consumer-side concept, no source change, no test change, no public symbol change

## 0. Scope limitation (locked, user 2026-05-25)

```text
PR52 is not a packet implementation PR.

PR52 defines how the PR51 7-key packet may be consumed by
LLM-facing or external consumer layers without turning it into
a new judgment engine.
```

한국어:

```text
PR52 는 packet 구현 PR 이 아니다.

PR52 는 PR51 의 7-key packet 을 LLM-facing / external consumer
layer 가 어떻게 소비해야 하는지 정의하되, 그 packet 이 새로운
판단 엔진이 되지 않도록 경계를 잠그는 spec PR 이다.
```

PR52 is the fourth (and final) PR in the PR49-PR52 read-surface roadmap. It writes consumer-side consumption rules for the 7 keys already produced by `examples/inspector/engine_inspector.py` (PR51). PR52 does NOT add packet keys, does NOT modify the wrapper, does NOT introduce a ragcore symbol, and does NOT auto-schedule any further PR.

---

## 1. Core statement

```text
The packet informs the consumer.
It does not replace Engine judgment.

packet 은 consumer 에게 정보를 제공한다.
Engine 판단을 대체하지 않는다.
```

This is the single sentence that governs every consumption rule in this spec. Each key-level rule (§4) and each forbidden reading (§5) must be readable as an expression of this sentence.

---

## 2. Source baseline

```text
PR49 Engine Read Surface Thaw Policy
  → freeze of judgment semantics holds;
    read surface may be thawed under §5 read-only definition.

PR50 Engine Read Surface Audit
  → 40 public methods classified; 19 read-only verified;
    Conclusion A: external wrapper sufficient.

PR51 Minimal Claim Read Query MVP
  → examples/inspector/engine_inspector.py:
       build_engine_context_packet(engine, claim_id) -> dict
     7-key packet produced from 8 of 19 read-only public methods;
     6 invariant tests lock read-only/public-only/domain-neutral.

PR52 (this) LLM Context Packet Spec
  → consumer-side consumption rules for the 7 keys;
    forbidden readings; LLM-facing translation boundary;
    ragcore symbol non-promotion lock.
```

Reference documents this spec inherits from:

```text
direction_rag_framework_proposal_layer  (memory direction §10 Context Packet)
docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md  (PR43-C §4.7 confidence)
docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md  (PR44-D AP-CF-* / AP-X-*)
docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md  (PR42 §4)
tests/test_external_adapter_simulation.py  (PR41 §50.9/10 invariants)
tests/test_engine_method_call_playbook_usage.py  (PR43-C 168차)
tests/test_external_engine_inspector.py  (PR51 185차)
```

---

## 3. Packet shape (locked from PR51)

The packet is a plain Python dict with exactly 7 string keys. The shape is inherited from `build_engine_context_packet` in PR51; PR52 does NOT change it.

```text
{
  "claim":                  Claim,
  "effective_confidence":   ScoreValue,
  "supporting_evidence":    tuple[Evidence, ...],
  "contradictions":         tuple[int, ...],     # evidence_ids
  "active_contradictions":  tuple[int, ...],     # evidence_ids
  "unresolved_gaps":        tuple[Gap, ...],
  "lifecycle_history":      tuple[ClaimLifecycleEvent, ...],
}
```

Locks on shape:

```text
- no key may be added or removed by this spec
- no key may be renamed by this spec
- no key may be re-typed by this spec
- this dict is NOT a ragcore type
- this dict shape is NOT in ragcore.__all__
- this dict shape is NOT exported as a public symbol anywhere
  in ragcore source
```

---

## 4. Key semantics (uniform 6-field structure)

Each of the 7 keys uses the same 6-field structure:

```text
Source method               — Engine public method that produced the value
What it represents          — meaning at Engine level
Consumer-side allowed       — readings that preserve §1
Consumer-side forbidden     — readings that violate §1
LLM-facing translation hint — how to surface this value to an LLM safely
Related prior guard         — PR41/PR42/PR43-C/PR44-D references
```

### 4.1 `claim`

```text
Source method:
  engine.get_claim(claim_id)

What it represents:
  the Engine-owned Claim dataclass instance for this claim_id.
  fields include subject_id, type, status (PR21-L lifecycle
  integer), base_confidence (ScoreValue), rule_id, rule_version,
  reason_code, flags.

Consumer-side allowed reading:
  - identify the subject (subject_id) the claim refers to
  - read claim_type as a consumer-domain integer
  - read status as the current lifecycle state
    (CANDIDATE / CONFIRMED / DISPUTED / REFUTED)
  - read base_confidence as the adapter-policy-translated
    prior (NOT a posterior)
  - read rule_id / rule_version as the audit-trail tag

Consumer-side forbidden reading:
  - rename Claim.status into a consumer "verdict label"
    (e.g., "vulnerable" / "exploited" / "secure")
  - treat status alone as the final decision
  - treat base_confidence as truth probability or as a calibrated
    risk score
  - assume Engine "auto-confirmed" or "auto-rejected" anything
    based on the claim object alone

LLM-facing translation hint:
  - present status as an opaque lifecycle phase
    ("currently CANDIDATE", not "verified vulnerable")
  - present base_confidence as "engine prior signal"
  - never present rule_id alone as evidence of correctness

Related prior guard:
  - PR43-C §4.3 Claim layer
  - PR44-D AP-C-1 (silent duplicate) / AP-C-2 (rule_id misread)
  - PR44-D AP-L-1 (no auto-fire of lifecycle)
```

### 4.2 `effective_confidence`

```text
Source method:
  engine.compute_effective_confidence(claim_id)

What it represents:
  ScoreValue produced by the 7-modifier composition
    base × status × freshness × gap × count × rule_stats ×
    evidence_type
  (PR12 ~ PR21, PR23, PR24, PR26, PR29, PR34-O §46,
   PR36-PKG §48.7).
  a decision-support signal, NOT a probability.

Consumer-side allowed reading:
  - use as relative ordering signal across claims
  - present as "engine confidence", "computed signal", or
    "effective confidence"
  - serialize ScoreValue.value (float in [0.0, 1.0]) into JSON
    when sending to LLM

Consumer-side forbidden reading:
  - call it "truth probability", "verified probability",
    "absolute risk probability", "P(true)", or any probabilistic
    phrasing
  - call it "verdict" or "decision"
  - treat it as an Engine judgment replacement
  - use a hardcoded threshold (e.g., `>= 0.7`) as if the
    threshold were blessed by ragcore
  - cache the value separately from Engine state and feed the
    cache to the LLM after Engine state has changed

LLM-facing translation hint:
  - prefix with a neutral label: "engine_confidence: 0.87"
  - explicitly disclaim probability semantics in the prompt
    template (e.g., "this is a decision-support signal, not a
    calibrated probability")
  - never present without the value's units; do NOT show "0.87"
    next to a "%" symbol

Related prior guard:
  - PR43-C §4.7 Confidence query layer (allowed/forbidden phrasing)
  - PR44-D AP-CF-1 (truth probability)
  - PR44-D AP-CF-2 (static threshold cutoff)
  - PR44-D AP-X-4 (cross-cutting truth-probability form)
```

### 4.3 `supporting_evidence`

```text
Source method:
  engine.evidences_for_claim(claim_id)

What it represents:
  tuple of Evidence dataclass instances supporting the claim.
  each Evidence has id, claim_id, raw_ref_id, type
  (consumer-domain integer), strength (ScoreValue in [0.0, 1.0]).

Consumer-side allowed reading:
  - list evidence ids and types as supporting facts
  - present strength as adapter-translated evidence weight
  - resolve raw_ref_id back to consumer-side raw content
    (the consumer owns the raw store; ragcore only stores the int)

Consumer-side forbidden reading:
  - pipe Evidence.strength directly into an LLM prompt as
    "probability" or "confidence percentage"
  - average / sum / multiply strength values to derive a
    "claim probability" inside the consumer layer
    (the only sanctioned composition is
     compute_effective_confidence)
  - treat presence of evidence as automatic claim confirmation
    (lifecycle transition requires the appropriate *_if_ready
     helper)
  - inject the raw payload from raw_ref_id into Engine
    (raw content stays consumer-side per PR42 §13 / PR44-D AP-E-1)

LLM-facing translation hint:
  - present per-evidence: "{type: <int>, strength: <float>,
    ref: <opaque_id>}"
  - do NOT include translated probability phrasing
  - do NOT include LLM-derived strength scoring

Related prior guard:
  - PR43-C §4.2 Evidence layer
  - PR42 §6~§12 (per-retrieval-type translation,
                  "Must remain outside ragcore" lock)
  - PR41 §50.9 / §50.10 (non-identity translation invariant)
  - PR44-D AP-E-1 (raw content in Engine)
  - PR44-D AP-E-2 (Evidence before Claim)
  - PR44-D AP-X-1 (external score identity-pipe)
```

### 4.4 `contradictions`

```text
Source method:
  engine.contradictions_for_claim(claim_id)

What it represents:
  tuple of evidence_id ints for ALL contradictions registered
  against this claim (active + resolved).

Consumer-side allowed reading:
  - list ids as a historical conflict trail
  - resolve each evidence_id via engine.get_evidence(id) to
    inspect the contradicting evidence
  - present as "this claim has N total recorded conflicts"

Consumer-side forbidden reading:
  - treat any non-empty contradictions tuple as automatic
    claim refutation
  - present "contradictions exist" as equivalent to "claim is
    false"
  - use the length of the tuple as a "conflict probability"
  - mix active vs resolved counts as if equivalent (use
    active_contradictions or resolved_contradictions_for_claim
    explicitly)

LLM-facing translation hint:
  - present as a count and a list of opaque ids; require LLM
    to call out which contradictions are still active before
    drawing any inference

Related prior guard:
  - PR43-C §4.5 Contradiction layer
  - PR44-D AP-CT-1 (no auto-lifecycle on contradiction registration)
  - PR44-D AP-CT-2 (Gap-Contradiction substitution)
```

### 4.5 `active_contradictions`

```text
Source method:
  engine.active_contradictions_for_claim(claim_id)

What it represents:
  tuple of evidence_id ints for contradictions that are NOT yet
  resolved (i.e., contradictions minus resolved_contradictions).

Consumer-side allowed reading:
  - present as "currently unresolved conflicts against this claim"
  - feed each id into get_evidence to retrieve details
  - use to prompt the LLM to inspect or propose resolution
    candidates

Consumer-side forbidden reading:
  - treat a non-empty tuple as automatic dispute/refutation of
    the claim (lifecycle transitions require an explicit
    dispute_claim_if_ready / refute_claim_if_ready call by the
    consumer, not by reading this tuple)
  - treat an empty tuple as "claim is true" or "no problems"
  - use the count to compute a "risk score" inside the LLM
    layer

LLM-facing translation hint:
  - present as a list of opaque ids and instruct the LLM that
    these are unresolved conflicts to consider, NOT decisions

Related prior guard:
  - PR43-C §4.5 Contradiction layer
  - PR43-C §4.6 Lifecycle layer (transitions require explicit
                                  helper invocation)
  - PR44-D AP-CT-1 (no auto-lifecycle on contradiction)
  - PR44-D AP-L-1 (Engine does not auto-fire lifecycle)
```

### 4.6 `unresolved_gaps`

```text
Source method:
  engine.gaps_for_claim(claim_id)
  filtered by engine.gap_resolution(gap.id) is None

What it represents:
  tuple of Gap dataclass instances for gaps that the Engine
  considers unresolved (no resolving evidence yet linked via
  resolve_gaps_for_evidence).

Consumer-side allowed reading:
  - list gap_type / required_evidence_type as "what is missing"
  - read severity as adapter-translated severity float
  - use to drive LLM proposals for additional evidence collection
    (proposal layer, NOT a ragcore concern)

Consumer-side forbidden reading:
  - interpret an unresolved gap as refutation of the claim
    (gap = missing info, NOT counter-evidence)
  - use gap.severity as a probability or as a final "risk"
  - present empty unresolved_gaps as "claim fully verified"

LLM-facing translation hint:
  - present as "missing information items"; phrase prompts as
    "what evidence would resolve this gap?" not "is this claim
    refuted?"
  - severity should be labeled as "adapter-side severity weight",
    not as probability

Related prior guard:
  - PR43-C §4.4 Gap layer
  - PR44-D AP-G-1 (Gap interpreted as refutation)
  - PR44-D AP-G-2 (manual gap resolution skipping evidence)
  - judgment triangle direction:
      unresolved gap ≠ contradiction
      unresolved gap ≠ refutation
```

### 4.7 `lifecycle_history`

```text
Source method:
  engine.claim_lifecycle_history(claim_id)

What it represents:
  tuple of ClaimLifecycleEvent dataclass instances, one per
  transition that has actually fired for this claim
  (PR10-B §23 audit trail).
  EMPTY tuple means no transition has fired yet (the claim is
  still in its initial status).

Consumer-side allowed reading:
  - render as a chronological lifecycle timeline
  - cross-reference each event's from_status / to_status / seq
  - use to explain to the LLM what state changes occurred and
    in what order

Consumer-side forbidden reading:
  - interpret empty lifecycle_history as "claim is not verified"
    or "claim is invalid"
    (an unverified claim simply has no transitions yet; the
     interpretation belongs to the consumer's policy, not to the
     Engine reading)
  - over-read the order/length as a "confidence score"
  - treat the most recent event as the only meaningful one
    (the entire trail is the audit surface)
  - cite a lifecycle event as evidence of correctness on its own
    (events record transitions; supporting evidence and gaps are
     elsewhere in the packet)

LLM-facing translation hint:
  - present as a list of (seq, from_status, to_status,
    transition_name) tuples
  - explicitly note when the list is empty: "no lifecycle
    transitions have fired yet" — NOT "no verification done"

Related prior guard:
  - PR43-C §4.6 Lifecycle layer
  - PR44-D AP-L-1 (Engine does not auto-fire transitions)
  - PR44-D AP-L-2 (treating _if_ready return as guarantee)
  - PR43-C 168차 test_full_path_with_contradiction_completes
    (history may legitimately be empty when readiness check fails;
     consumer must NOT over-read empty history)
```

---

## 5. Forbidden readings (cross-cutting summary)

A consolidated list of forbidden readings the consumer layer must NOT perform when consuming the packet. Each item maps to an existing AP-* anti-pattern lock.

```text
F1   effective_confidence as truth / verified / absolute probability
       → PR44-D AP-CF-1 / AP-X-4

F2   effective_confidence as Engine judgment replacement
       → PR43-C §4.7 ("decision-support signal", NOT verdict)

F3   evidence.strength piped directly into LLM as probability
       → PR41 §50.9/10 / PR44-D AP-X-1

F4   evidence.strength composed (sum / avg / multiply) into a
     consumer-side "claim probability"
       → PR43-C §4.7 (only compute_effective_confidence is the
                       sanctioned composition)

F5   contradictions or active_contradictions non-empty
     treated as automatic claim refutation
       → PR44-D AP-CT-1

F6   contradictions empty treated as "claim is true"
       → PR43-C §4.6 (lifecycle transitions require explicit
                       helper invocation)

F7   unresolved_gaps treated as refutation
       → PR44-D AP-G-1

F8   unresolved_gaps empty treated as "claim fully verified"
       → PR43-C §4.4 (gap = information incomplete, NOT verdict)

F9   lifecycle_history empty treated as "unverified" or
     "meaningless"
       → PR43-C §4.6 ("readiness check may fail and that is a
                       valid state")

F10  Claim.status renamed into consumer "verdict label"
       → PR43-C §4.3 ("status is opaque lifecycle phase")

F11  base_confidence treated as truth probability
       → PR43-C §4.3 ("adapter policy decides base; consumer
                       does NOT recompute")

F12  static threshold (e.g., >= 0.7) on effective_confidence
     presented as if blessed by ragcore
       → PR44-D AP-CF-2

F13  raw_ref_id resolved INTO Engine (e.g., adapter pushes the
     raw payload back as add_evidence content)
       → PR42 §13 / PR44-D AP-E-1
```

---

## 6. LLM-facing translation boundary

Allowed phrasings (consumer report layer + LLM prompt):

```text
- "engine_confidence: 0.87"
- "computed signal: 0.87"
- "effective_confidence (decision-support): 0.87"
- "Claim currently in lifecycle phase: CANDIDATE"
- "supporting evidence list (opaque ids and adapter strengths)"
- "unresolved gaps requiring more information"
- "active conflicts not yet resolved"
- "lifecycle transition trail (audit only)"
```

Forbidden phrasings (consumer report layer + LLM prompt):

```text
- "P(true) = 0.87"
- "probability of vulnerability: 87%"
- "verified true with 0.87 confidence"
- "this is the engine's verdict"
- "score above threshold → automatically true"
- "no contradictions → claim is verified"
- "no gaps → claim is fully proven"
- "no lifecycle events → claim is invalid"
- any framing that suggests the packet IS the decision rather
  than informing one
```

LLM prompt template guidance:

```text
- always include the disclaimer that effective_confidence is a
  decision-support signal, not a probability
- always present opaque ids as opaque
- never ask the LLM to compute a "final probability" or "final
  verdict" from the packet — ask for proposals (evidence to
  collect, gaps to fill, contradictions to investigate) instead
- proposals from the LLM must then pass through the Validator
  layer (direction_rag_framework_proposal_layer §16 #8/#9)
  before any Engine public API is called
```

---

## 7. Consumer responsibility

The consumer is responsible for the following — none of these are Engine concerns and none are ragcore symbols:

```text
- serialization of the packet into JSON / protobuf / msgpack
  for transport to the LLM
- summarization or truncation of large evidence lists
- localization of labels (the consumer may translate "CANDIDATE"
  into a domain phrase for end-user display, but MUST NOT change
  the Engine semantics)
- mapping consumer-domain integer types (entity_type / claim_type
  / evidence_type / observation_type / source_type / reason_code
  / gap_type / relation_type) into domain vocabulary at the
  report layer
- defining the consumer's threshold policy and explicitly
  documenting it as adapter policy
- caching the packet for one LLM turn (must invalidate when
  Engine state changes; never present stale cached values as
  current Engine state)
- enforcing the proposal-layer Validator that filters LLM
  output before Engine public API is invoked
  (direction_rag_framework_proposal_layer §16 #8/#9)
```

The consumer is NOT responsible for:

```text
- redefining Engine semantics
- adding to ragcore.__all__
- creating a ragcore type to hold the packet
- bypassing PR44-D anti-patterns under any consumer-side
  rationale
```

---

## 8. Ragcore symbol boundary

```text
"LLM Context Packet" is a CONSUMER-SIDE concept.
"LLM Context Packet" is NOT a ragcore symbol.
"LLM Context Packet" must NOT appear in ragcore.__all__.
"LLM Context Packet" must NOT appear as a class, dataclass,
TypedDict, or type alias inside ragcore source.

The packet is a plain dict shape returned by
examples/inspector/engine_inspector.py (a consumer-side example).
PR52 does NOT promote the shape into a ragcore type.
```

Cross-references:

```text
direction_rag_framework_proposal_layer §16 #2
  ("LLMProposal / RAGContext / ToolPlan / EngineContextPacket
    등을 ragcore public API 또는 ragcore.__all__ 에 추가하지
    마라")

PR44-D AP-X-7 (adapter-specific symbol promoted into
                ragcore.__all__)
PR44-D AP-X-6 (domain vocabulary intrusion into ragcore source)
PR50 §7 R1 (ragcore.__all__ promotion risk)
PR50 §7 R3 (domain bias risk)
```

If a future PR proposes a `LLMContextPacket` class/dataclass/
TypedDict inside `ragcore`, that PR must first revoke this
section's lock with explicit user authorization, and must satisfy
all of PR50 §8.3 conditions (α/β/γ/δ/ε).

---

## 9. PR52 Exit criteria

PR52 closes when ALL of the following hold:

```text
[ ] docs/architecture/LLM_CONTEXT_PACKET_SPEC.md added
[ ] pytest 1151 passing (unchanged from PR51 baseline)
[ ] ragcore.__all__ 48 symbols (unchanged)
[ ] Engine public methods 40 (unchanged)
[ ] snapshot schema_version 2 (unchanged)
[ ] snapshot top-level keys 18 (unchanged)
[ ] ragcore source change 0 bytes
[ ] test change 0
[ ] new public symbol 0
[ ] new engine behavior 0
[ ] contract §51 not added
[ ] packet shape NOT expanded (still 7 keys from PR51)
[ ] examples/inspector/engine_inspector.py NOT modified
[ ] tests/test_external_engine_inspector.py NOT modified
[ ] PR52 does not auto-schedule any next PR
[ ] LLMContextPacket NOT promoted into ragcore.__all__ or
    ragcore source
```

PR52 's job is to write the spec and close. It does not perform
any implementation, packet shape change, or surface promotion.

---

## 10. Closing meaning

```text
PR52 is not a packet implementation PR.

PR52 defines how the PR51 7-key packet may be consumed by
LLM-facing or external consumer layers without turning it into
a new judgment engine.

The packet informs the consumer.
It does not replace Engine judgment.

LLM Context Packet is a consumer-side concept.
It is not a ragcore symbol.
```

Locked closing sentences:

```text
PR52 는 packet 구현 PR 이 아니다.

PR52 는 PR51 의 7-key packet 을 LLM-facing / external consumer
layer 가 어떻게 소비해야 하는지 정의하되, 그 packet 이 새로운
판단 엔진이 되지 않도록 경계를 잠그는 spec PR 이다.

packet 은 consumer 에게 정보를 제공한다.
Engine 판단을 대체하지 않는다.

LLM Context Packet 은 consumer-side 개념이다.
ragcore symbol 이 아니다.

PR52 closes the PR49 ~ PR52 read-surface roadmap.
No automatic next PR.
```
