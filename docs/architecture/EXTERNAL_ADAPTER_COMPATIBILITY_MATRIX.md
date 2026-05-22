# External Adapter Compatibility Matrix

Status: audit document (PR39)
Baseline: main `4c1d485` (PR38-B merged)
Type: documentation-only compatibility audit, no implementation

## 0. Purpose

This document checks whether the current ragcore Engine public API can host **external adapters** for the integration patterns the initial philosophy documents anticipated:

```text
docs/01_CORE_PHILOSOPHY.md   "Core 는 RAG / LLM / Graph DB 에 직접 연결하지 않는다."
docs/03_RUNTIME_LOOP.md      "RAG / LLM / Graph DB 는 이후 외부 Adapter 로 붙인다."
```

PR39 does NOT implement any adapter. PR39 only verifies that the framework remains generic and that adapter outputs can be translated into Engine method calls.

The single question this document answers:

```text
Is the current ragcore.Engine compatible with future external adapters
for Vector DB / Graph DB / LLM / SQL / File Store / API Signal / Manual?
```

## 1. Locked principles (inherited from initial philosophy + §50)

```text
- Core is generic. Domain vocabulary lives in the adapter, not in ragcore.
- raw_ref_id is a caller-side identifier; ragcore does not interpret it.
- Adapter MUST translate external scores into base_confidence / strength.
  Identity mapping is forbidden.
- similarity score (any kind) is NOT engine confidence.
- LLM output is NEVER a judgment source. LLM is a summarization /
  proposal layer; rules and evidence remain the judgment authority.
- vector DB / graph DB / corpus / storage / retrieval architecture are
  consumer-owned (per §50.4 + §50.11).
- adapter MUST maintain consumer-side integer registries (per §50.6).
- adapter MUST resolve external references to int raw_ref_id (per §50.7).
- adapter MUST call only the 40 frozen public methods (per §50.13).
```

These principles are cited from:

```text
docs/01_CORE_PHILOSOPHY.md       LLM 직접 연결 금지 / RAG 직접 연결 금지
docs/03_RUNTIME_LOOP.md          외부 Adapter 로 분리
docs/contracts/05_DATA_CONTRACT_MVP.md §39 / §42 / §43 / §44 / §48 / §50
```

## 2. ragcore Engine surface reference (target of the audit)

The 40 frozen public methods (PR36-PKG `_LOCKED_PUBLIC_METHODS`):

```text
CRUD             add_entity / add_observation / add_claim / add_evidence /
                 add_relation / add_gap
Lookups          get_entity / get_observation / get_claim / get_evidence /
                 get_relation / get_gap / get_rule / get_rule_stats
Filter queries   evidences_for_claim / gaps_for_claim /
                 contradictions_for_claim / active_contradictions_for_claim /
                 resolved_contradictions_for_claim
Gap / resolve    gap_resolution / resolve_gaps_for_evidence
Contradiction    register_contradiction / register_contradiction_resolution
Lifecycle        confirm_claim_if_ready / dispute_claim_if_ready /
                 refute_claim_if_ready / resolve_disputed_claim_if_ready /
                 refute_disputed_claim_if_ready /
                 refute_disputed_claim_if_ready_by_freshness
History          claim_lifecycle_history
Freshness        evidence_freshness / active_contradictions_by_freshness
Rule registry    register_rule / update_rule_stats
Hint types       register_hint_evidence_types / unregister_hint_evidence_types /
                 clear_hint_evidence_types
Compute          compute_effective_confidence
Snapshot         to_snapshot / from_snapshot
```

The audit checks: can each of the 7 adapter candidates route its outputs through this surface, given §50 adapter responsibilities?

## 3. Adapter candidate inventory

```text
1. Vector DB Adapter
2. Graph DB Adapter
3. LLM Adapter
4. SQL / Postgres Adapter
5. File-based Knowledge Store Adapter
6. API Signal Adapter
7. Manual Analyst Note Adapter
```

These are not exhaustive. Future adapters (e.g., streaming event source, sensor feed, time-series DB) inherit the same pattern.

## 4. Compatibility matrix

### 4.1 Vector DB Adapter

| Aspect | Value |
| ------ | ----- |
| External output | list of `(chunk_id, similarity_score, text, metadata)` from any vector store |
| Adapter responsibility | resolve `chunk_id` → `raw_ref_id`; classify each chunk into `evidence_type`; translate `similarity_score` → `strength` via policy; decide which chunks become Evidence vs ignored |
| Engine method calls | `add_observation` (per query event), `add_evidence` (per promoted chunk), `add_claim` (when claim is materialized), `register_hint_evidence_types` (if chunk types are weak signals) |
| Required consumer-owned registry | `entity_type` / `evidence_type` / `observation_type` |
| raw_ref_id resolver | `chunk_id` (string / UUID) → int (consumer-side hash registry or DB key) |
| Confidence / strength translation | **REQUIRED**. similarity_score is NOT engine confidence. Adapter must define mapping (e.g., `cosine ≥ 0.8 → strength 0.9`). |
| Compatibility status | **Compatible via adapter** |
| Engine change needed? | **No** — current API + §50 obligations sufficient |

Notes:

```text
- Pinecone / Weaviate / Chroma / Qdrant / pgvector / FAISS — all equivalent
- Embedding model choice is consumer-side
- Reranking is consumer-side
- Vector score scale (cosine / dot product / L2 distance) is normalized
  in adapter, not in ragcore
```

### 4.2 Graph DB Adapter

| Aspect | Value |
| ------ | ----- |
| External output | list of `(node, edge, traversal_path, path_score)` from any graph store |
| Adapter responsibility | resolve `node` → `entity_id` (creating with `add_entity` if new); translate `edge` → `Relation` via `add_relation`; translate `path_score` → `strength` (if used as evidence weight); classify edge semantics into `relation_type` (consumer-side registry) |
| Engine method calls | `add_entity`, `add_relation`, `add_evidence`, `add_claim` |
| Required consumer-owned registry | `entity_type` / `relation_type` (NOTE: `relation_type` is NOT a ragcore type — it is the `type: int` field on `Relation`, consumer-defined) / `evidence_type` |
| raw_ref_id resolver | `node_id` → int (consumer-side registry) |
| Confidence / strength translation | **REQUIRED**. path_score is NOT engine confidence. Adapter policy translates (e.g., shortest path / centrality / weighted edges). |
| Compatibility status | **Compatible via adapter** |
| Engine change needed? | **No** — `add_relation` supports cross-kind links via `from_kind` / `to_kind` discriminators |

Notes:

```text
- Neo4j / TigerGraph / NetworkX / DuckDB graph extension — all equivalent
- Traversal depth / pruning is consumer-side
- ragcore.Relation is intentionally minimal; edge metadata lives outside
  ragcore (e.g., in consumer's graph store or in evidence payload)
```

### 4.3 LLM Adapter

| Aspect | Value |
| ------ | ----- |
| External output | natural language response, optionally structured (JSON), optionally with self-reported confidence |
| Adapter responsibility | **LLM output is never a judgment source.** Adapter validates LLM output against domain policy before promoting to Evidence. LLM may propose Claims but the adapter (not the LLM) decides whether to actually call `add_claim`. LLM self-reported confidence is ignored unless explicitly translated. |
| Engine method calls | `add_evidence` (after strict validation), `add_claim` (only when adapter policy authorizes), `register_contradiction` (when LLM identifies a refutation candidate) |
| Required consumer-owned registry | `evidence_type` (e.g., "llm_summary" / "llm_proposed_fact"), `source_type` (=LLM) |
| raw_ref_id resolver | `llm_response_id` (or composite of prompt_hash + model_version + timestamp) → int |
| Confidence / strength translation | **ABSOLUTELY REQUIRED**. LLM self-confidence is unreliable. Adapter policy must downweight (e.g., LLM-only evidence strength capped at 0.5). |
| Compatibility status | **Compatible via adapter (with strict policy)** |
| Engine change needed? | **No** — current API sufficient; the constraint is adapter discipline |

Notes:

```text
- Initial philosophy lock: "LLM 직접 연결 금지" applies here.
  The framework structure already prevents direct LLM-to-Claim path
  because Engine.add_claim requires explicit caller decision.
- LLM as Hint Evidence Type (register_hint_evidence_types) is the natural
  pattern: LLM-derived evidence flagged as "weak" via evidence_type
  modifier attenuation.
- LLM-proposed contradiction is allowed via register_contradiction, but
  adapter must verify the contradiction has a non-LLM evidence source
  before promoting to claim refutation.
```

### 4.4 SQL / Postgres Adapter

| Aspect | Value |
| ------ | ----- |
| External output | query result rows from any SQL engine (Postgres / SQLite / MySQL / DuckDB) |
| Adapter responsibility | resolve row primary key → `raw_ref_id`; classify row content into `evidence_type`; translate row's score column (if any) → `strength` |
| Engine method calls | `add_observation` (per query event), `add_evidence` (per row promoted), `add_claim` (when query represents a claim materialization) |
| Required consumer-owned registry | `evidence_type` / `source_type` (=SQL) |
| raw_ref_id resolver | row PK → int (often direct if PK is already int) |
| Confidence / strength translation | **Optional but recommended**. SQL queries are typically deterministic; if a score column exists, translate via policy. If not, use adapter-default strength. |
| Compatibility status | **Compatible via adapter** |
| Engine change needed? | **No** |

Notes:

```text
- Simplest of the 7 adapters because SQL results are well-structured
- evidence granularity decision (row vs query vs aggregate) is adapter-side
- transaction boundary belongs to consumer's storage layer, not ragcore
```

### 4.5 File-based Knowledge Store Adapter

| Aspect | Value |
| ------ | ----- |
| External output | file path + content + extracted structured facts (JSON / YAML / markdown sections) |
| Adapter responsibility | resolve file path or content hash → `raw_ref_id`; extract structured facts from raw file content; classify each fact into `evidence_type`; assign strength per extraction quality |
| Engine method calls | `add_observation` (per file read event), `add_evidence` (per extracted fact), `add_claim` (when facts collectively support a claim) |
| Required consumer-owned registry | `evidence_type` / `source_type` (=file) |
| raw_ref_id resolver | file hash (sha256) → int via consumer-side registry OR file path → int via registry |
| Confidence / strength translation | **Required for extraction quality**. Strength reflects how cleanly the fact was extracted (regex match vs LLM-extracted vs manual-tagged). |
| Compatibility status | **Compatible via adapter** |
| Engine change needed? | **No** |

Notes:

```text
- File-based knowledge is the most "static corpus" pattern
- This is the natural fit for static rule corpus, historical reports,
  domain manuals, vendor advisory dumps, etc.
- Versioning belongs to consumer (e.g., git commit hash as part of
  raw_ref_id derivation)
```

### 4.6 API Signal Adapter

| Aspect | Value |
| ------ | ----- |
| External output | external API response (typed structure, possibly with API-reported confidence) |
| Adapter responsibility | resolve API `request_id` / response identifier → `raw_ref_id`; map API response fields to `evidence_type`; translate API-reported confidence (if any) → `strength` via policy |
| Engine method calls | `add_observation` (per API call event), `add_evidence` (per API field of interest), `add_claim` (when API result represents a claim) |
| Required consumer-owned registry | `source_type` (=api), `evidence_type` |
| raw_ref_id resolver | API `request_id` or `(endpoint, params_hash, timestamp)` → int |
| Confidence / strength translation | **Required if API returns confidence**. API confidence semantics vary; adapter must normalize (e.g., NVD CVSS / EPSS / VirusTotal API confidence → adapter policy → strength). |
| Compatibility status | **Compatible via adapter** |
| Engine change needed? | **No** |

Notes:

```text
- NVD / EPSS / KEV / OSV / VirusTotal / commercial threat intelligence
  APIs all share this pattern
- Rate limiting / retry / caching belongs to consumer's API client layer
- ragcore never makes network calls (PR36-PKG §48.9 invariant)
```

### 4.7 Manual Analyst Note Adapter

| Aspect | Value |
| ------ | ----- |
| External output | human-written observation, claim proposal, or evidence note |
| Adapter responsibility | parse analyst input into structured claim / evidence; assign `evidence_type` (=manual_note); analyst sets confidence / strength explicitly |
| Engine method calls | `add_observation`, `add_claim`, `add_evidence` |
| Required consumer-owned registry | `source_type` (=manual), `evidence_type` |
| raw_ref_id resolver | note_id (or `(analyst_id, timestamp)`) → int |
| Confidence / strength translation | **Analyst-set explicitly**. No translation needed — analyst already provides confidence (e.g., "I'm 80% sure" → 0.8). |
| Compatibility status | **Compatible via adapter** |
| Engine change needed? | **No** |

Notes:

```text
- Manual analyst notes are the highest-confidence default among the 7
  (analyst is a domain expert)
- But analyst-set confidence is still subject to lifecycle attenuation
  (dispute / refute) by other evidence
- This is the simplest adapter to implement (effectively just a form input)
```

## 5. Compatibility summary

| Adapter | Compatible via adapter? | Engine change needed? |
| ------- | ----------------------- | --------------------- |
| Vector DB | yes | no |
| Graph DB | yes | no |
| LLM | yes (with strict policy) | no |
| SQL / Postgres | yes | no |
| File-based Knowledge Store | yes | no |
| API Signal | yes | no |
| Manual Analyst Note | yes | no |

**All 7 candidates are compatible without ragcore source change.**

## 6. Cross-cutting compatibility patterns

The matrix reveals 7 patterns shared across all adapter candidates:

```text
1. external_id → raw_ref_id resolution
   Every adapter needs a way to turn its external identifier (chunk_id /
   node_id / row_pk / file_hash / request_id / note_id) into ragcore's
   raw_ref_id: int.

2. external score → engine input translation
   Every adapter that has a score (similarity / path_score / API confidence /
   LLM self-confidence / extraction quality) must translate via explicit
   policy. Identity pipe is forbidden.

3. consumer-side integer registries
   Every adapter maintains entity_type / observation_type / source_type /
   claim_type / evidence_type / reason_code registries on the consumer side.

4. evidence granularity decision
   Every adapter must decide what counts as one Evidence row (per chunk /
   per row / per fact / per response field / per note).

5. evidence type classification
   Every adapter must classify its outputs into evidence_type integers
   that meaningfully drive the evidence_type modifier (or register them
   as hint types).

6. lifecycle responsibility
   ragcore handles confirm / dispute / refute / resolve_disputed /
   refute_disputed lifecycle transitions. Adapters do NOT bypass these.

7. snapshot is consumer-owned
   Every adapter's snapshot persistence is on the consumer side (per
   PR36-PKG §48.9 + PR37 README + §50.11).
```

These 7 patterns are independent of which adapter or which external system. They form the **adapter pattern** that any future external knowledge source must follow to plug into ragcore.

## 7. What MUST NOT enter the framework

Based on this audit, the following MUST stay out of ragcore source:

```text
- vector similarity = engine confidence (forbidden identity mapping)
- LLM natural language answer = confirmed Claim (forbidden direct path)
- graph path = confirmed Relation (forbidden without adapter policy)
- raw tool output = Evidence (must normalize via adapter)
- raw chunk text = Evidence (must classify + assign strength)
- scanner severity = evidence strength (must translate via policy)
- package-specific schema = ragcore type (Vector DB SDK types,
  Graph DB SDK types, LLM SDK types — none enter ragcore)
- API client / network code (ragcore makes no network calls)
- database driver code (ragcore does no DB I/O)
- file I/O (ragcore does no file operations)
- embedding model loading (ragcore does no ML inference)
- LLM API key / authentication (ragcore handles no credentials)
```

If a future PR tries to introduce any of these into ragcore source, the PR violates §50 and the initial philosophy locks.

## 8. Compatibility gaps (none found)

The audit looked for cases where adapter outputs could NOT be translated into Engine method calls. None were found.

The closest thing to a friction point (already noted in PR38-A probe and §50.7):

```text
raw_ref_id is int. External identifiers are usually strings.
The adapter MUST own the string → int resolution strategy.
```

This is an adapter responsibility, NOT a ragcore deficiency. ragcore's int raw_ref_id is intentional — it keeps the engine free of any string parsing or hashing logic. The adapter handles all stringly-typed identifiers.

Resolution strategy options (all consumer-side):

```text
- per-namespace integer registry table
- stable hash truncated to int64
- timestamp + monotonic counter
- external storage key mapping
- composite key encoding (tool + run_id + sequence) → int
```

ragcore does not specify which. Each adapter picks one consistent strategy.

## 9. Conclusion (locked)

```text
Engine should not depend on external packages.
External packages are adapter-owned.

The compatibility question is whether adapter outputs can be translated
into Engine public method calls.

The audit answers: yes, for all 7 adapter candidates examined.

Most compatibility work belongs to adapter policy, not ragcore source.
```

## 10. Non-goals (preserved)

PR39 explicitly does NOT:

```text
- implement any adapter (Vector DB / Graph DB / LLM / SQL / File / API / Manual)
- import any external package (pinecone / neo4j / openai / etc.)
- choose a vector DB / graph DB / LLM model / SQL flavor
- choose a chunking strategy
- choose an embedding model
- choose a retrieval ranking formula
- propose Engine API additions
- define CanonicalEvidenceAtom / RetrievalResult / EngineInput as dataclasses
- add any class / function / module to ragcore.__all__
- change engine.py / types.py / __init__.py / rule_output.py
- add adapter framework tests
- introduce production-readiness claims
- introduce Cerberus-specific concepts into ragcore
- propose PR40 or later
```

## 11. Followup constraints

After PR39 merges:

```text
- this document is REFERENCE, not a binding contract
  (the binding contracts are §39 ~ §50 in docs/contracts/05_DATA_CONTRACT_MVP.md)
- new adapter candidates may be appended to this matrix in future docs
  PRs (e.g., streaming event source, time-series DB, sensor feed)
- if a future adapter genuinely requires an Engine API change, it must
  enter as a "method surface migration" PR per §48.5 — not as a silent
  adapter implementation
- if a future Engine update accidentally breaks one of the 7 adapter
  patterns above, it violates §50.13 and must be rolled back or migrated
```

## 12. Pattern position

```text
docs/01_CORE_PHILOSOPHY.md       원칙 — Core 는 RAG / LLM / Graph DB 직접 연결 금지
docs/03_RUNTIME_LOOP.md          순서 — RAG / LLM / Graph DB 는 외부 Adapter 로
docs/contracts/05_DATA_CONTRACT_MVP.md §50  계약 — External Knowledge Adapter Boundary
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md  audit — 위 원칙/순서/계약이
                                                            실제 7 adapter 후보에 적용 가능한지 검증
                                                            (this PR)
```

PR39 is the audit step that confirms the architecture's initial philosophy holds against concrete adapter patterns. Nothing more, nothing less.
