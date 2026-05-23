# Retrieval Output → Evidence Guide

Status: guide (PR42, Candidate B)
Baseline: main `d853e9c` (PR41 merged)
Type: documentation-only translation semantics, no implementation

## 0. Scope limitation (locked, user 2026-05-22)

```text
PR42 does not implement retrieval adapters.

PR42 explains how retrieval outputs should be translated into
Engine-compatible evidence structures by adapter-owned policy.
```

한국어:

```text
PR42 는 실제 retrieval adapter 를 만드는 PR 이 아니다.

PR42 는 retrieval output 이 adapter translation 을 거쳐 어떤 Engine
입력 단위로 바뀌어야 하는지 문서화하는 PR 이다.
```

## 1. Layer position

```text
PR39   compatibility audit         — 7 adapter 후보가 Engine 과 호환되는지 확인
PR40   adapter policy decisions    — adapter 가 결정해야 할 10 정책 질문 정리
PR41   simulation tests             — fake external output → Engine 흐름 executable
                                       enforcement
PR42   retrieval translation        — retrieval output → Evidence translation semantics
                                       (this guide)
```

PR42 fills the gap between "policy decisions exist" (PR40) and "fake outputs work in simulation" (PR41) by explaining the **translation semantics** — what each external output IS, and what it BECOMES inside ragcore.

This guide does NOT pick formulas. It explains meaning.

## 2. Locked principles

```text
Retrieval output is not Engine input.

A retrieved chunk, graph path, LLM answer, SQL row, API response,
or analyst note must pass through adapter-owned translation before it
becomes an Observation, Claim, Evidence, Gap, or Relation.

Retrieval score is not Engine confidence.

Raw retrieved content must remain outside ragcore and be referenced
through raw_ref_id.
```

These are inherited from:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md §50         External Knowledge Adapter Boundary
docs/guides/ADAPTER_POLICY_GUIDE.md                Adapter Policy Guide (PR40)
tests/test_external_adapter_simulation.py          Simulation tests (PR41)
```

## 3. Eight central questions

PR42 answers these (per-retrieval-type sections below):

```text
1. retrieval output은 언제 Observation인가?
2. retrieval output은 언제 Evidence인가?
3. retrieval output은 언제 Claim 후보인가?
4. retrieval output은 언제 Gap을 만든 원인인가?
5. retrieval output은 언제 Relation으로 표현되는가?
6. raw text / chunk / path / row / note는 어디에 보관되는가?
7. retrieval score는 왜 Engine confidence가 아닌가?
8. adapter는 어떤 normalized evidence unit을 만들어야 하는가?
```

The 7 retrieval-type sections below answer Q1 ~ Q6 per type. Q7 is answered cross-cuttingly in §4. Q8 is answered in §11.

## 4. Why retrieval score is not Engine confidence (Q7)

```text
Retrieval score answers:
  "How relevant is this item to my query?"

Engine confidence answers:
  "How much should this claim influence downstream decisions?"

These are different questions.

A document with cosine similarity 0.95 to "OpenSSH 7.4 vulnerable"
does NOT mean the asset is 95% likely vulnerable. It means the
retrieval found a relevant document.

Adapter must translate retrieval relevance into engine inputs
(base_confidence + strength) using explicit policy — never identity.
```

This is the §50.10 single non-negotiable rule, expanded per type below.

## 5. Common reading

Each retrieval-type section uses the same 7 fields:

```text
What the external output contains
What must remain outside ragcore
What adapter must translate
Possible Engine target
What must not be identity-piped
raw_ref_id expectation
Notes
```

The fields are intentionally domain-neutral. Security examples are NOT given to keep the guide RAG-agnostic.

---

## 6. Type 1 — Vector search result

**What the external output contains:**

```text
- chunk_id / document_id (consumer-side string identifier)
- chunk text (the raw retrieved content)
- similarity_score (cosine / dot product / L2 / etc.)
- chunk metadata (source, position, embedding model version)
- embedding vector (usually not used post-retrieval)
```

**What must remain outside ragcore:**

```text
- chunk text (full or partial)
- embedding vector
- similarity score (any kind)
- vector DB client objects
- embedding model identifiers
- consumer-side chunk store
```

**What adapter must translate:**

```text
- chunk_id (string) → raw_ref_id (int) via consumer-side resolver
- similarity_score → strength via non-identity policy
  (e.g., similarity >= 0.8 → strength 0.9, else strength 0.5)
- chunk semantics → evidence_type (consumer-side integer registry)
- chunk relevance threshold → "promote to Evidence" vs "ignore"
```

**Possible Engine target:**

```text
- Observation: per retrieval query event (one Observation per query)
- Evidence: per chunk that the adapter promotes
            (strength = translated similarity)
- Claim: if the chunk represents a new fact, adapter may create
         a candidate Claim with status=CLAIM_STATUS_CANDIDATE
- Gap: if a retrieval returned 0 chunks for a required_evidence_type,
       a Gap may be added
- Relation: usually NOT — vector retrieval is point-similarity,
            not relationship
```

**What must not be identity-piped:**

```text
- similarity_score → strength (forbidden direct copy)
- chunk text → Evidence content (chunk text never enters ragcore)
- embedding vector → any Engine input
- top-1 = highest confidence (top-1 is just top-1; confidence is separate)
```

**raw_ref_id expectation:**

```text
raw_ref_id resolves chunk_id (consumer string) to ragcore int.
Consumer can later fetch chunk text from its own store using
reverse lookup (raw_ref_id int → chunk_id string → chunk text).
ragcore stores only the int.
```

**Notes:**

```text
Vector retrieval often returns many chunks. Adapter decides:
  - which chunks promote to Evidence
  - how to combine multiple chunks for the same claim
  - whether top-K vs threshold cutoff is the right strategy

Defaults are domain-specific. PR42 does not pick.
```

---

## 7. Type 2 — Graph path / graph query result

**What the external output contains:**

```text
- starting node_id
- ending node_id
- intermediate node_ids (path)
- edge labels / edge types
- path_score (shortest-path / weighted / random walk / etc.)
- path metadata
```

**What must remain outside ragcore:**

```text
- graph DB client objects
- node labels / property bags
- traversal algorithm parameters
- consumer-side graph store
```

**What adapter must translate:**

```text
- node_id (string) → entity_id (int) via add_entity or registry lookup
- edge label / edge type → relation_type (consumer-side integer)
- path_score → strength via non-identity policy
- path semantics → claim_type (if path represents a claim)
- path provenance → raw_ref_id
```

**Possible Engine target:**

```text
- Observation: per traversal query
- Relation: per edge in the path (add_relation per edge OR one
            Relation summarizing the path — adapter decides)
- Claim: if the path represents a fact (e.g., "node A relates to node B"),
         adapter creates a candidate Claim
- Evidence: the path itself can be Evidence for the claim
            (strength = translated path_score)
- Gap: if a query found no path for a required relation,
       a Gap may be added
```

**What must not be identity-piped:**

```text
- path_score → strength (forbidden direct copy)
- raw graph node properties → ragcore fields
  (consumer-side graph store holds node properties; ragcore stores
   only entity_id + entity_type)
- edge type label string → ragcore (relation_type is int only)
```

**raw_ref_id expectation:**

```text
raw_ref_id may resolve to a path identifier like
"<from_node>--<edge>--<to_node>" or a graph query result id.
Consumer reverse-resolves to the original graph traversal.
```

**Notes:**

```text
Graph results have two valid Engine mappings:
  (a) one Relation per edge — fine-grained
  (b) one Relation + one Evidence — path summary

Adapter chooses based on domain semantics. Both are valid.
ragcore does not own this granularity.
```

---

## 8. Type 3 — LLM extraction result

**What the external output contains:**

```text
- extracted_text (natural language fact / claim / observation)
- model_self_confidence (sometimes; often unreliable)
- prompt context
- model identifier + version
- source_ref (what the LLM was reasoning about)
- structured fields (when LLM returns JSON)
```

**What must remain outside ragcore:**

```text
- LLM API client objects
- prompt content
- raw natural language text
- model API keys
- model_self_confidence as a direct number
```

**What adapter must translate:**

```text
- extracted_text → structured claim proposal (NOT auto-confirmed)
- model_self_confidence → strength via heavy adapter policy
  (LLM confidence is unreliable; cap aggressively, e.g., cap at 0.5)
- model identifier + version → raw_ref_id component
- structured fields → claim_type / evidence_type via consumer registry
```

**Possible Engine target:**

```text
- Observation: per LLM call
- Claim: ALWAYS as CLAIM_STATUS_CANDIDATE — never confirmed
         (LLM is a proposal source, not a judgment source)
- Evidence: as evidence_type=hint (often registered via
            register_hint_evidence_types so the evidence_type
            modifier attenuates strength)
- Gap: if LLM identifies missing information, a Gap may be added
- Relation: only when LLM extracts a structured relationship AND
            adapter has high-confidence supporting evidence elsewhere
```

**What must not be identity-piped:**

```text
- extracted_text → Evidence content (text never enters ragcore)
- model_self_confidence → base_confidence directly (cap heavily)
- LLM proposal → CLAIM_STATUS_CONFIRMED (NEVER auto-confirm)
- LLM hedge ("I am very confident") → numerical confidence
```

**raw_ref_id expectation:**

```text
raw_ref_id resolves to an LLM response identifier composite:
(model_name, prompt_hash, timestamp) → int via consumer registry.
Consumer reverse-resolves to recover the original LLM output for
audit / human review.
```

**Notes:**

```text
LLM is the most aggressively-attenuated source.
Adapter policy MUST:
  - cap strength below 0.5 for LLM-only evidence
  - never auto-confirm a claim based solely on LLM
  - prefer LLM as hint evidence (register_hint_evidence_types)
  - require human-in-the-loop OR corroborating non-LLM evidence
    before promoting a claim to CONFIRMED

PR41 simulation enforces the strength cap (≤ 0.5).
This guide explains why.
```

---

## 9. Type 4 — SQL / structured row result

**What the external output contains:**

```text
- row_id / primary_key (consumer-side)
- table_name + column values
- query metadata (filters, joins)
- optional query_score (when ranking is used)
```

**What must remain outside ragcore:**

```text
- DB client objects / connection pools
- raw column values
- table schema
- SQL query text
- consumer-side row store
```

**What adapter must translate:**

```text
- row_id → raw_ref_id (often direct if PK is already int)
- column semantics → claim_type / evidence_type
- column value → evidence content (kept outside ragcore via raw_ref)
- presence/absence → strength
  (SQL is deterministic; strength near 1.0 if exact match)
```

**Possible Engine target:**

```text
- Observation: per query event
- Evidence: per row promoted (strength near 1.0 for exact-match)
- Claim: if the row represents a claim assertion
- Gap: if a query returned 0 rows where one was required
- Relation: when row represents a relationship between entities
            (e.g., foreign key linkage)
```

**What must not be identity-piped:**

```text
- query_score → strength (if SQL ranking is used, still translate)
- row content → Evidence content (only the int raw_ref_id)
- column type names → ragcore vocabulary
```

**raw_ref_id expectation:**

```text
raw_ref_id resolves to (table_name, primary_key) composite.
This is the cleanest translation among the 7 types because SQL is
already structured.
```

**Notes:**

```text
SQL is the simplest source. Most adapter friction goes to claim_type
classification (which row means which claim semantic).

Strength is usually near 1.0 because SQL queries are deterministic.
The count modifier and freshness modifier still apply if multiple
rows support the same claim or if contradictions appear later.
```

---

## 10. Type 5 — File chunk / document span result

**What the external output contains:**

```text
- file_path or document_id
- byte_range or paragraph index
- chunk_hash (content fingerprint)
- chunk text (raw content)
- chunk metadata (encoding, format, version)
```

**What must remain outside ragcore:**

```text
- file content
- chunk text
- file system handle
- consumer-side file store
```

**What adapter must translate:**

```text
- file_path / chunk_hash → raw_ref_id
  (recommended: stable hash → int registry)
- chunk semantics → evidence_type
- extraction quality → strength
  (regex extraction = high strength; LLM extraction from chunk = lower)
```

**Possible Engine target:**

```text
- Observation: per file read event
- Evidence: per fact extracted from chunk
- Claim: if a chunk supports a claim, adapter promotes
- Gap: if a required document/section is missing
- Relation: usually NOT (file chunks are document fragments, not
            relationships)
```

**What must not be identity-piped:**

```text
- chunk text → Evidence content (use raw_ref_id only)
- file path string → ragcore
- file modification timestamp → claim_confidence
```

**raw_ref_id expectation:**

```text
raw_ref_id resolves to chunk_hash (sha256 truncated to int64) OR
a (file_path, byte_range) composite registered to int.
Consumer reverse-resolves to recover the chunk text from its
file store.
```

**Notes:**

```text
File chunks are the natural source for static corpus knowledge
(documentation, manuals, advisory dumps).

If the consumer uses chunking strategies (fixed-size vs semantic),
the choice is consumer-side. ragcore is unaware of chunk size.
```

---

## 11. Type 6 — API signal result

**What the external output contains:**

```text
- API endpoint name
- request_id / call_id
- response fields (typed structure)
- api_score (when API returns confidence/score)
- timestamp + API version
- caching metadata
```

**What must remain outside ragcore:**

```text
- HTTP client
- API credentials
- response body (large payloads)
- consumer-side API cache
```

**What adapter must translate:**

```text
- request_id → raw_ref_id (often a composite of endpoint + params)
- api_score → strength via adapter policy
  (some APIs return reliable scores; others don't)
- response fields → claim_type / evidence_type
- API trust level → adapter-applied dampening
```

**Possible Engine target:**

```text
- Observation: per API call
- Evidence: per response field of interest
- Claim: when API result represents a claim
- Gap: if an API expected to return data returned empty
- Relation: when API describes inter-entity relationships
```

**What must not be identity-piped:**

```text
- api_score → strength directly
- API self-reported confidence → base_confidence
  (different APIs have different confidence semantics)
- HTTP status code → claim status (200 OK is not "claim confirmed")
- response body → Evidence content
```

**raw_ref_id expectation:**

```text
raw_ref_id resolves to (api_name, request_id, timestamp) composite.
Consumer reverse-resolves to recover the original API response from
its cache or by re-issuing the request.
```

**Notes:**

```text
APIs vary widely. Some provide reliable structured data (CVE/NVD-like).
Some provide unreliable LLM-style responses. Adapter MUST classify
each API by trust tier and apply different policies.

Example tiers (adapter-side):
  tier 1: deterministic API (e.g., government registry)  → strength 0.9
  tier 2: curated commercial API                         → strength 0.7
  tier 3: ML-driven API                                  → strength 0.5
  tier 4: experimental                                    → strength 0.3
```

---

## 12. Type 7 — Manual analyst note

**What the external output contains:**

```text
- analyst_id / author
- note_id
- free-text note content
- analyst-set confidence (label or numerical)
- timestamp
- note classification (observation / claim / refutation)
```

**What must remain outside ragcore:**

```text
- note text content
- analyst PII
- consumer-side note store / forum / ticket system
```

**What adapter must translate:**

```text
- note_id → raw_ref_id
- analyst-set confidence_label → base_confidence
  ("low" / "medium" / "high" / "critical" → discrete mapping)
- note classification → claim_type or evidence_type
- analyst trust → strength dampening (junior vs senior analyst)
```

**Possible Engine target:**

```text
- Observation: per note submission event
- Claim: if note proposes a claim
- Evidence: if note supports an existing claim
- Refutation candidate: register_contradiction if note disagrees
- Gap: if note flags missing information
- Relation: if note describes inter-entity link
```

**What must not be identity-piped:**

```text
- note text → Evidence content
- analyst confidence_label string → ragcore field
- "I think it might be" → high confidence
- analyst trust level → final score (adapter applies dampening, not Engine)
```

**raw_ref_id expectation:**

```text
raw_ref_id resolves to note_id or (analyst_id, timestamp) composite.
Consumer reverse-resolves to recover the original note text from
its note store.
```

**Notes:**

```text
Manual analyst notes are the highest-default-confidence source
because the analyst is a domain expert. But analyst notes are still
subject to:
  - lifecycle attenuation (other evidence can dispute / refute)
  - count modifier (multiple analysts = repeated pressure)
  - freshness modifier (recent contradictions matter)

A senior analyst marking a claim "critical" does NOT bypass the
framework's lifecycle and modifier composition. It just sets a high
base_confidence and strength.
```

---

## 13. Normalized evidence unit conditions (Q8)

After translation, the adapter produces a normalized evidence unit (conceptual; not a ragcore type) suitable for passing to Engine method calls.

A normalized evidence unit SHOULD have:

```text
- subject context             (which Entity this evidence refers to)
- claim target OR evidence target
                              (which Claim this Evidence supports
                               OR which Claim this contradicts)
- raw_ref_id                  (int, resolved from external identifier)
- evidence_type                (int, from consumer-side registry)
- translated strength          (float in [0.0, 1.0], NOT identity-piped)
- reason_code or adapter reason
- enough provenance to resolve back to raw source
                              (reverse lookup capability)
```

This list is conceptual guidance. It is NOT a ragcore type. It is NOT exported. It is NOT frozen as a dataclass here.

If the adapter chooses to materialize this as a Python class on the consumer side, the class name and field set are consumer's choice. Conceptual labels like `CanonicalEvidenceAtom` or `EvidenceAtom` may be used, but they are NOT ragcore symbols.

## 14. Pattern position

```text
docs/01_CORE_PHILOSOPHY.md            원칙
docs/03_RUNTIME_LOOP.md                순서
docs/contracts/05_DATA_CONTRACT_MVP.md §50              계약
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md   audit (PR39)
docs/guides/ADAPTER_POLICY_GUIDE.md   guide (PR40, decision surface)
tests/test_external_adapter_simulation.py  simulation (PR41, executable)
docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md  guide (PR42, translation semantics, this)
```

PR42 sits in layer 5 (alongside PR40), but extends in a different direction: PR40 lists policy *questions* (what to decide), PR42 lists translation *semantics* (what each retrieval output means inside ragcore).

## 15. What this PR does NOT do

PR42 deliberately does NOT:

```text
- implement any retrieval adapter
- import any external package (chromadb / qdrant / neo4j / openai / etc.)
- pick concrete score formulas (similarity → strength functions etc.)
- pick specific evidence_type integer assignments
- pick storage backends
- pick chunking / embedding / corpus strategies
- pick LLM models / API providers
- define CanonicalEvidenceAtom / RetrievalResult / EngineInput
  as ragcore public types
- add to ragcore.__all__
- modify engine.py / types.py / __init__.py / rule_output.py
- add new tests (PR41 simulation tests already cover invariants)
- introduce Cerberus-specific concepts
- propose PR43 or later
- trigger V-cerberus
- auto-select remaining candidate areas C / D / E
```

## 16. Followup candidate areas (still NOT PR-numbered)

```text
Candidate C — Engine Method Call Playbook
Candidate D — Anti-patterns Guide
Candidate E — Reference Flow
```

PR42 closes Candidate B from the PR39 followup list. The remaining three candidates remain UNSCHEDULED. PR-numbers are not assigned in this PR.

## 17. Closing meaning

```text
PR42 maps each external retrieval output type to its possible Engine
targets without picking adapter formulas.

It answers WHAT each retrieval output BECOMES inside ragcore, while
keeping HOW it is translated as adapter responsibility.

Six layers (philosophy / runtime / contract / audit / guide /
simulation) now answer different questions. PR42 adds a
seventh-direction layer alongside Guide:

  - PR40 = policy decisions (what to decide)
  - PR42 = translation semantics (what becomes what)

Both are adapter-side concerns. ragcore stays generic.
```

Locked closing sentences:

```text
Retrieval output is not Engine input.

A retrieved chunk, graph path, LLM answer, SQL row, API response,
or analyst note must pass through adapter-owned translation before it
becomes an Observation, Claim, Evidence, Gap, or Relation.

Retrieval score is not Engine confidence.

Raw retrieved content must remain outside ragcore and be referenced
through raw_ref_id.
```
