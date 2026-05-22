# PR38-RAG-BOUNDARY Plan — RAG Operational Boundary / Evidence Adapter Contract

Status: planned after PR37-PKG-DOCS
Branch context: `feat/integration-readiness-boundary`
Baseline before this plan: PR36-PKG `main = 41298f1`, PR37-PKG-DOCS in progress

## 1. Why this document exists

During PR37-PKG-DOCS, one boundary became clear:

```text
PR36-PKG §48 freezes the Engine method surface.
PR37-PKG §49 makes the integration boundary discoverable.

But neither one fully defines how Cerberus RAG operations feed the Engine.
```

This document prevents a wrong next step.

The risk is not the Engine method surface anymore.
The risk is building Cerberus directly on the current Engine structure before the RAG operational layer is defined.

If Cerberus directly knows too much about Engine claim/evidence/gap internals, then a later update to corpus, vector DB, retrieval policy, embedding version, or evidence mapping can force Cerberus integration code to be rewritten.

Therefore PR38 should define a RAG Operational Boundary before Cerberus thin adapter work goes deep.

## 2. Corrected layer map

The project now has four distinct layers:

```text
Layer A. Engine Core
  - ragcore.Engine
  - Claim / Evidence / Gap / Rule / RuleStats
  - lifecycle
  - effective confidence
  - snapshot / migration
  - method surface freeze

Layer B. Integration Discoverability
  - README quickstart
  - Project Status
  - Persistence Boundary
  - §43 / §44 / §48 / §49 documentation map

Layer C. RAG Operational Boundary
  - CanonicalEvidenceAtom
  - RetrievalResult
  - EngineInput
  - adapter responsibility
  - corpus/vectorstore/embedding independence
  - mapping from retrieved evidence to Engine calls

Layer D. Cerberus Product Integration
  - Cerberus scanner/check outputs
  - Cerberus evidence ingestion
  - Cerberus UI/report flow
  - Cerberus-specific storage
  - Cerberus thin adapter
```

Completed:

```text
Layer A: mostly complete through PR36-PKG
Layer B: in progress through PR37-PKG-DOCS
```

Not yet complete:

```text
Layer C: RAG Operational Boundary
Layer D: Cerberus Product Integration
```

## 3. Core correction

Do not treat "V-cerberus thin adapter can start" as "RAG operations are complete."

Correct meaning:

```text
V-cerberus thin adapter can start
= Cerberus can begin a shallow integration check against the stable Engine package surface.

It does NOT mean
= Cerberus should deeply encode current Engine internals before the RAG operational adapter contract exists.
```

## 4. Main risk

Bad structure:

```text
Cerberus
  -> directly calls many Engine methods
  -> directly knows Claim/Evidence/Gap construction details
  -> directly couples scan output to Engine internals
  -> later RAG corpus/vector DB/retrieval changes break Cerberus code
```

Better structure:

```text
Cerberus
  -> CerberusRagAdapter
  -> CanonicalEvidenceAtom / RetrievalResult / EngineInput
  -> ragcore.Engine
```

Cerberus should depend on the adapter contract, not on raw Engine internals or future RAG storage structure.

## 5. PR38 purpose

PR38-RAG-BOUNDARY should define the operational boundary between Cerberus RAG data flow and the generic Engine.

It should answer:

```text
1. What is the canonical evidence unit before it enters Engine?
2. What does retrieval return?
3. What is the minimal EngineInput produced by the adapter?
4. Which layer owns vector DB, corpus, chunking, and embedding version?
5. Which layer owns snapshot persistence?
6. Which layer is allowed to call ragcore.Engine directly?
7. Which changes are algorithm updates and which changes are integration-breaking changes?
```

## 6. Proposed contract objects

PR38 should not immediately implement heavy code.
It should first document the minimum contract objects.

### 6.1 CanonicalEvidenceAtom

Purpose:

```text
A normalized evidence unit produced from raw Cerberus/tool/API observations before Engine-specific mapping.
```

Candidate fields:

```text
atom_id
source_kind
source_name
asset_id
subject
predicate
object
observed_at
confidence
strength
raw_ref
correlation_key
independence_class
evidence_role
metadata
```

Notes:

```text
- This is not an Engine Evidence object yet.
- It is the stable bridge between Cerberus observations and Engine inputs.
- The field set may be refined, but Cerberus should not bypass this layer.
```

### 6.2 RetrievalResult

Purpose:

```text
A RAG retrieval output that returns context and candidate evidence without deciding truth.
```

Candidate fields:

```text
query_id
asset_id
retrieval_scope
matched_atoms
matched_documents
retrieval_policy
embedding_version
corpus_version
score_metadata
```

Notes:

```text
- RetrievalResult is not a judgment.
- Vector score is not Engine confidence.
- Retrieval explains what was found, not what is true.
```

### 6.3 EngineInput

Purpose:

```text
The adapter-produced input bundle that translates canonical evidence and retrieval output into Engine calls.
```

Candidate fields:

```text
claims_to_add
evidence_to_add
gaps_to_add
rules_to_fire
contradictions_to_register
resolution_candidates
snapshot_context
```

Notes:

```text
- EngineInput is adapter-facing, not product-facing.
- Cerberus should not manually assemble low-level Engine calls throughout product code.
- EngineInput lets future RAG mapping change without rewriting Cerberus flow.
```

## 7. Ownership boundaries

### 7.1 Engine owns

```text
- Claim lifecycle
- Evidence/gap/contradiction state
- effective confidence computation
- snapshot dict structure
- snapshot migration
- public method surface
```

### 7.2 RAG operational layer owns

```text
- corpus construction
- chunk schema
- embedding version
- retrieval policy
- canonical evidence extraction
- retrieved context packaging
- evidence-to-Engine mapping
```

### 7.3 Cerberus owns

```text
- raw scanner/tool/API outputs
- asset/session context
- user workflow
- product UI/report orchestration
- where snapshots are stored
- when the adapter is invoked
```

## 8. What is allowed to evolve later

Allowed:

```text
- vector DB implementation
- corpus chunk format
- embedding model/version
- retrieval scoring
- evidence mapping heuristics
- modifier strength
- threshold policy
- effective confidence calibration
```

Required to remain stable:

```text
- Cerberus calling the adapter, not raw Engine internals
- adapter contract shape or migration path
- Engine public method surface from PR36-PKG
- snapshot migration boundary
- consumer-owned persistence rule
```

## 9. PR38 non-goals

PR38 should not do the following:

```text
- Do not implement a vector DB.
- Do not choose a final embedding model.
- Do not build the full Cerberus adapter.
- Do not change ragcore.Engine method surface.
- Do not change judgment mathematics.
- Do not change snapshot schema unless a separate migration PR requires it.
- Do not add Cerberus-specific product code to ragcore.
```

## 10. Recommended PR38 cycle

Recommended sequence:

```text
154차 docs(contract): define RAG operational boundary (§50)
155차 test/docs or type-stub audit: lock adapter contract names/shapes only if needed
156차 docs(readme/dev): add PR38 record and next V-cerberus constraints
157차 ready + squash merge
```

If implementation is needed, it should be minimal and adapter-facing only.
The first PR should preferably be contract-first, not vectorstore-first.

## 11. Updated next-step order

Previous order considered:

```text
PR37 -> V-cerberus thin adapter -> PR38-O engine.py refactor
```

Corrected order:

```text
PR37 -> PR38-RAG-BOUNDARY -> V-cerberus thin adapter -> engine.py internal refactor later
```

Reason:

```text
engine.py internal refactor cleans the framework internals.
RAG Operational Boundary protects Cerberus from future RAG structure changes.

The second is more urgent before product integration.
```

## 12. Final locked sentence

```text
Engine boundary is frozen.
Integration discoverability is being closed.
RAG operations are not yet frozen.

Before Cerberus depends deeply on the framework, PR38 must define the RAG Operational Boundary so future corpus, vector DB, embedding, retrieval, and evidence mapping changes do not break Cerberus engine structure.
```
