# Adapter Policy Guide

Status: guide (PR40)
Baseline: main `e2635a8` (PR39 merged)
Type: documentation-only policy decision surface, no implementation

## 0. Scope limitation (locked, user 2026-05-22)

```text
PR40 does not implement adapter policies.

PR40 defines the policy decision surface that every external adapter
must own.
```

한국어:

```text
PR40 은 adapter policy 를 구현하는 PR 이 아니다.
PR40 은 모든 Adapter 가 반드시 소유해야 할 정책 결정면을 문서화하는 PR 이다.
```

PR39 confirmed that the seven external adapter candidates (Vector DB / Graph DB / LLM / SQL / File / API / Manual) are compatible with the frozen Engine method surface without ragcore source change.

PR40 turns to the next question:

```text
"If Engine does not need to change, what policy choices MUST each
adapter own?"
```

This guide enumerates those policy choices. It does NOT pick the answers.

## 1. Locked principles (inherited)

```text
Adapter policy is consumer-owned.

ragcore does not own domain vocabulary, external IDs, retrieval scores,
storage backends, or confidence translation rules.

The adapter must translate external signals into Engine method calls.

External scores are not Engine confidence until adapter policy converts them.

PR40 defines the policy decision surface, not the policy formulas.
```

These principles are inherited from:

```text
docs/01_CORE_PHILOSOPHY.md       initial framework identity
docs/03_RUNTIME_LOOP.md           initial runtime layering
docs/contracts/05_DATA_CONTRACT_MVP.md §50  external knowledge adapter boundary
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md  PR39 audit
```

## 2. Reading this guide

Each section below describes ONE policy area. The structure is uniform:

```text
Question        — the decision the adapter must answer
Adapter owns    — what falls on the consumer/adapter side
Engine receives — the ragcore public method calls that result
Must not        — anti-patterns specific to this policy area
Notes           — guidance, edge cases, hints
```

The guide does not provide formulas. Formulas are domain-specific and
remain consumer-side decisions.

---

## 3. Policy areas

### 3.1 Subject granularity policy

```text
Question:
  What unit of the external domain becomes the Entity (subject of claims)?

Adapter owns:
  - choosing the granularity (host / service / endpoint / document /
    case / user / sensor / asset class / concept / etc.)
  - keeping the choice consistent per claim_type
  - linking multi-granularity subjects via Relation when needed

Engine receives:
  add_entity(entity_type=int)
  add_relation(from_kind=int, from_id=int, to_kind=int, to_id=int,
               relation_type=int, ...)

Must not:
  - pick a granularity that erases the claim's meaning
  - switch granularity mid-stream within the same claim_type
  - assume Engine knows what "host" / "service" / "user" mean

Notes:
  Different claim_types may require different granularities.
  A finding about "the host runs SSH" is a host-level claim.
  A finding about "service on port 22 is OpenSSH 7.4" is a service-level claim.
  Either way the choice is adapter responsibility, recorded in the
  consumer-side entity_type integer registry.
```

### 3.2 Evidence granularity policy

```text
Question:
  At what unit of granularity does the adapter emit Evidence?

Adapter owns:
  - choosing one of:
      one tool run → one Evidence (coarse)
      one extracted field → one Evidence (fine)
      one normalized signal → one Evidence (recommended default)
  - documenting the choice per evidence_type
  - keeping granularity stable across runs

Engine receives:
  add_evidence(claim_id=int, raw_ref_id=int, evidence_type=int,
               strength=float)

Must not:
  - pass raw tool output (bytes / full JSON dump) as Evidence
  - emit one Evidence per raw_byte
  - mix granularities within the same evidence_type

Notes:
  Granularity directly affects the count modifier (PR24-N) and the
  freshness modifier (PR11-C). Too coarse = single Evidence cannot
  carry multiple signals. Too fine = noise. "One normalized signal"
  is the safe default.
```

### 3.3 raw_ref_id resolver policy

```text
Question:
  How does the adapter translate external string / composite identifiers
  into ragcore's `raw_ref_id: int`?

Adapter owns:
  - resolver strategy choice (one of):
      consumer-side integer registry table
      stable hash truncated to int64
      timestamp + monotonic counter
      external storage key mapping
      composite key encoding (tool + run_id + sequence) → int
  - consistency across runs and storage handoffs
  - collision detection (if hashing)

Engine receives:
  raw_ref_id: int (used in add_observation / add_evidence)

Must not:
  - leak the raw_ref_id meaning into ragcore code or types
  - assume Engine will recover the original external identifier
    (Engine only stores the int; reverse lookup is consumer-side)
  - reuse a raw_ref_id across different external references
  - change strategy mid-stream without snapshot migration plan

Notes:
  PR38-A probe identified this as the single clearest adapter
  friction point. It is intentional: the framework's int requirement
  forces the adapter to own the resolution boundary.
  Consumer must keep a reverse lookup if it wants to recover external
  identifiers from snapshots.
```

### 3.4 Consumer-side integer registry policy

```text
Question:
  Which integer registries must the adapter maintain, and what are the
  consequences of changing them?

Adapter owns:
  - entity_type registry        (1 = host, 2 = service, ...)
  - observation_type registry    (10 = banner, 11 = api_response, ...)
  - source_type registry         (1 = tool_output, 2 = api, 3 = manual, ...)
  - claim_type registry          (100 = host_runs_software, ...)
  - evidence_type registry       (20 = banner_text, 21 = api_field, ...)
  - reason_code registry         (per claim_type semantics)
  - registry versioning + migration plan when assignments change

Engine receives:
  these ints as parameters to add_entity / add_observation / add_claim /
  add_evidence / add_relation / add_gap

Must not:
  - reuse an integer for two different semantic meanings
  - change assignment without migrating existing snapshots
  - assume Engine will validate the integer's semantic meaning
    (Engine only stores; semantics are consumer-owned)
  - publish the registry as a ragcore artifact

Notes:
  Two adapters may use different integer assignments — that is allowed.
  The registry is part of the adapter's contract with itself, not part
  of the ragcore contract. Changing a registry value mid-stream
  effectively invalidates existing snapshots unless the adapter
  provides a migration step.
```

### 3.5 Confidence translation policy

```text
Question:
  How does the adapter translate an external "confidence-like" signal
  into `base_confidence` for Engine.add_claim?

Adapter owns:
  - explicit translation policy for each external source:
      scanner severity (low/med/high/crit) → base_confidence
      LLM self-reported confidence (0~1)   → base_confidence
      API confidence field                  → base_confidence
      domain risk score (CVSS / EPSS)      → base_confidence
      analyst-set confidence (0~1)         → base_confidence
      default for direct observation       → base_confidence
  - policy documentation
  - per-claim_type default values
  - clamping to [0.0, 1.0]

Engine receives:
  add_claim(... base_confidence=float ...)

Must not:
  - identity-pipe: external_score → base_confidence directly
  - use vector similarity as confidence
  - use LLM natural-language hedge as confidence (e.g., "very confident"
    → 0.95)
  - exceed [0.0, 1.0]
  - downgrade silently when LLM hedges (must be explicit policy)

Notes:
  Engine's effective_confidence = base × 6 modifiers. base_confidence
  is the adapter's starting point. Modifier composition is engine-internal.
  An adapter that sets base = external_score blindly will produce
  Effective scores that drift with retrieval scoring changes —
  exactly the failure mode the framework was designed to prevent.
```

### 3.6 Evidence strength policy

```text
Question:
  How does the adapter translate an external "score" into `strength`
  for Engine.add_evidence?

Adapter owns:
  - per-evidence_type strength policy:
      similarity score      → strength
      severity              → strength
      retrieval rank        → strength
      domain trust signal   → strength
      analyst-assigned (0~1) → strength
      default for hard fact → strength = 1.0 (or close to it)
  - clamping to [0.0, 1.0]
  - documenting how each external score maps

Engine receives:
  add_evidence(... strength=float ...)

Must not:
  - identity-pipe: similarity → strength
  - use raw cosine distance / dot product without normalization
  - exceed [0.0, 1.0]
  - assume Engine will dedupe duplicate evidence (the count modifier
    treats two strengths as two separate signals)

Notes:
  Strength affects the count modifier (PR24-N) and freshness modifier
  (PR11-C) via active contradiction strength. Setting strength = 0.999
  for everything wastes the count modifier's resolution.
```

### 3.7 Claim creation policy

```text
Question:
  When does the adapter call `Engine.add_claim`, vs when does it only
  add evidence to an existing claim?

Adapter owns:
  - claim identification logic:
      same (subject, claim_type) → reuse existing claim_id, add evidence
      new (subject, claim_type)   → add_claim
  - dedup strategy when multiple adapters / runs touch the same claim
  - lifecycle trigger conditions (when to call confirm_claim_if_ready
    etc.)

Engine receives:
  add_claim(...)  for new claims
  add_evidence(...) and/or register_contradiction(...) for existing

Must not:
  - add_claim for every observation (creates redundant claims)
  - assume Engine dedupes claims (it does not — same subject + claim_type
    can have multiple separate claims if the adapter calls add_claim
    multiple times)
  - bypass confirm_claim_if_ready / dispute_claim_if_ready /
    refute_claim_if_ready boundary
  - mutate claim base_confidence after creation (it is set at
    creation only)

Notes:
  The framework's lifecycle (PR6 / PR7 / PR8 / PR9-A / PR10-A) is
  responsibility-allocated. Adapter decides claim creation. Engine
  decides lifecycle transitions when the adapter calls *_if_ready
  methods. After creation, base_confidence is fixed; modifier strength
  affects effective_confidence over time.
```

### 3.8 Gap policy

```text
Question:
  When does the adapter create a Gap, and which gap_resolution policy
  does it follow?

Adapter owns:
  - identifying when a claim is missing evidence (information deficit)
  - choosing required_evidence_type per gap
  - severity assignment per gap
  - resolution strategy (when adapter knows an evidence satisfies a gap,
    call resolve_gaps_for_evidence)

Engine receives:
  add_gap(claim_id, gap_type, required_evidence_type, severity, rule_id)
  resolve_gaps_for_evidence(evidence_id)

Must not:
  - emit a Gap for every missing field (noise floods count modifier)
  - assume Engine will infer gap resolution from evidence content
    (Engine matches by required_evidence_type only)
  - leave gaps unresolved forever without surfacing to consumer report
    layer

Notes:
  Gaps participate in the gap modifier (PR12-D / PR23-M tier).
  Unresolved gaps attenuate effective_confidence. Resolved gaps return
  the modifier to 1.0 for that gap. The adapter decides which gaps
  matter and which are noise.
```

### 3.9 Relation policy

```text
Question:
  When does the adapter create a Relation, vs when does it embed the
  relationship in Evidence content?

Adapter owns:
  - choosing when cross-kind links matter enough to materialize as
    Relation (vs leaving the relationship implicit in evidence text)
  - relation_type assignment (consumer-side integer)
  - rule_id attribution when the relation is rule-derived
  - reason_code per relation_type

Engine receives:
  add_relation(from_kind, from_id, to_kind, to_id, relation_type,
               rule_id, reason_code)

Must not:
  - materialize every observed adjacency as a Relation (state bloat)
  - use Relation to encode evidence (use Evidence for evidence)
  - rely on Engine to traverse Relations for reasoning (Relations are
    static records, not queryable graphs — that is consumer-side)

Notes:
  Relation is the framework's cross-kind link record. It is intentionally
  minimal (from_kind, from_id, to_kind, to_id, type, rule_id, reason_code).
  Adapter consumers needing rich graph queries should maintain their
  own graph store on the consumer side and use Relation only for the
  links that affect judgment.
```

### 3.10 Snapshot ownership policy

```text
Question:
  Where and when does the adapter persist `Engine.to_snapshot()` output?

Adapter owns:
  - storage backend choice (JSON file / SQLite / Postgres JSONB / S3 /
    Redis / in-memory)
  - persistence timing (per-claim / per-transaction / periodic)
  - concurrency control (locking, optimistic concurrency, etc.)
  - backup / retention policy
  - snapshot migration when schema_version increments
  - reverse lookup tables (if needed to recover external identifiers
    from raw_ref_id ints)

Engine receives:
  to_snapshot() → dict
  from_snapshot(dict) → Engine

Must not:
  - ask ragcore to persist (Engine never writes to disk)
  - assume Engine will reconstruct external state from snapshot
    (Engine only restores its own state)
  - store snapshots inside ragcore source tree
  - serialize Engine's internal Python objects (use to_snapshot, not
    pickle)

Notes:
  Snapshot is the canonical handoff format. It is JSON-compatible and
  versioned (schema_version 2 at this baseline). Adapter is responsible
  for migration when ragcore bumps schema_version — though the framework
  provides _migrate_snapshot_to_current() to chain migration steps.
```

---

## 4. Policy decision summary table

| # | Policy area | Adapter owns | Engine method | Must NOT |
| - | ----------- | ------------ | ------------- | -------- |
| 1 | Subject granularity | unit choice (host / service / etc.) | add_entity | erase claim meaning |
| 2 | Evidence granularity | unit choice (run / field / signal) | add_evidence | pass raw bytes |
| 3 | raw_ref_id resolver | string → int strategy | (param to multiple methods) | leak meaning into ragcore |
| 4 | Consumer registry | int → semantic mapping | (params throughout) | reuse int meaning |
| 5 | Confidence translation | external → base_confidence | add_claim base_confidence | identity-pipe |
| 6 | Evidence strength | external → strength | add_evidence strength | identity-pipe |
| 7 | Claim creation | when add_claim vs add_evidence | add_claim / add_evidence | dup claims |
| 8 | Gap | when add_gap, when resolve_gaps_for_evidence | add_gap / resolve_gaps_for_evidence | noise floods modifier |
| 9 | Relation | when add_relation vs leave implicit | add_relation | state bloat |
| 10 | Snapshot ownership | where / when to persist | to_snapshot / from_snapshot | ask Engine to persist |

---

## 5. What this guide does NOT do

PR40 deliberately does NOT:

```text
- provide concrete translation formulas for any policy
- pick specific integer assignments
- pick specific storage backends
- choose between vector DB / graph DB / LLM / SQL / file / API / manual
- implement any adapter class
- write Cerberus-specific code
- introduce CanonicalEvidenceAtom / RetrievalResult / EngineInput as
  ragcore types
- add to ragcore.__all__
- modify engine.py / types.py / __init__.py / rule_output.py
- introduce tests for adapter behavior (adapter behavior is
  consumer-side)
- propose PR41 or later
- trigger V-cerberus
```

PR40 leaves these to:

```text
- consumer-side adapter implementations
- future documentation if/when user decides to write any of the
  remaining candidate areas (Retrieval-to-Evidence Guide /
  Engine Method Call Playbook / Anti-patterns Guide / Reference Flow)
- the user's decision (no auto-scheduling)
```

---

## 6. Engine responsibilities (recap, NOT changed by PR40)

For symmetry, here is what the Engine itself owns. These are NOT adapter responsibilities:

```text
ragcore.Engine owns:
  - 7-modifier composition formula
  - lifecycle state transitions
  - snapshot serialization / migration framework
  - effective_confidence computation
  - claim lifecycle history audit trail
  - contradiction registration / resolution state tracking
  - rule firing trace (when rules are registered)
  - method surface (frozen by PR36-PKG _LOCKED_PUBLIC_METHODS)
  - report shape (frozen by PR32-V *_KEYS frozensets)
```

The Engine does NOT own:

```text
- adapter policies (covered by PR40)
- domain vocabulary
- storage choices
- retrieval architecture
- network / IO / LLM calls
- external integer semantics
```

---

## 7. Pattern position

```text
docs/01_CORE_PHILOSOPHY.md            원칙
docs/03_RUNTIME_LOOP.md                순서
docs/contracts/05_DATA_CONTRACT_MVP.md §50  계약 (External Knowledge Adapter Boundary)
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
                                       audit (PR39 — Engine 변경 불필요 확인)
docs/guides/ADAPTER_POLICY_GUIDE.md    guide (PR40 — adapter 가 소유할 정책면, this guide)
```

Five layers:

```text
1. Philosophy   why
2. Runtime      where (loop position)
3. Contract     what (boundary obligations)
4. Audit         feasibility (can it host adapters?)
5. Guide         which decisions belong to the adapter
```

PR40 is layer 5. It informs adapter implementers WITHOUT writing the implementation.

---

## 8. Followup candidate areas (NOT PR-numbered)

The remaining four candidate areas (from PR39 record §4) are unchanged:

```text
Candidate B — Retrieval Output → Evidence Guide
Candidate C — Engine Method Call Playbook
Candidate D — Anti-patterns Guide
Candidate E — Reference Flow
```

Each remains a candidate. None auto-scheduled. PR numbers and scope locks happen at user decision time.

---

## 9. Closing meaning

```text
PR40 is not the end of the adapter conversation.

PR40 records the policy decisions that any adapter must own, so that
when a real adapter is built (Cerberus or otherwise), there is a clear
list of "did you decide this?" questions to check.

The Engine remains generic.
The adapter is consumer-side.
The policy decisions belong to the adapter, not to ragcore.
```

Locked closing sentences:

```text
Adapter policy is consumer-owned.

ragcore does not own domain vocabulary, external IDs, retrieval scores,
storage backends, or confidence translation rules.

The adapter must translate external signals into Engine method calls.

External scores are not Engine confidence until adapter policy converts them.

PR40 defines the policy decision surface, not the policy formulas.
```
