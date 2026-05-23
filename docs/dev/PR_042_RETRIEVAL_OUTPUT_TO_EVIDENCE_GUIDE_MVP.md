# PR42 — Retrieval Output → Evidence Guide MVP

## Scope limitation (locked, user 2026-05-22)

```text
PR42 does not implement retrieval adapters.

PR42 explains how retrieval outputs should be translated into
Engine-compatible evidence structures by adapter-owned policy.

Retrieval output is not Engine input.
Normalized evidence unit is a conceptual adapter-owned shape,
not a ragcore public type.
```

한국어:

```text
PR42 는 retrieval output 을 구현하지 않는다.

PR42 는 retrieval output 이 adapter translation 을 거쳐 어떤
Engine-compatible evidence structure 로 읽혀야 하는지 문서화하는 PR 이다.

Retrieval output 은 Engine input 이 아니며,
normalized evidence unit 은 conceptual adapter-owned shape 이지
ragcore public type 이 아니다.
```

PR42 closes Candidate B from the post-PR41 followup list. PR40 enumerated the policy *questions* every adapter must answer. PR41 made those questions *executable* through fake-output simulation. PR42 explains the translation *semantics* — what each external retrieval output IS, and what it BECOMES inside ragcore — without picking adapter formulas.

## 1. Guide structure (17 sections)

```text
§0   Scope limitation                    locked 2026-05-22
§1   Layer position                      PR39 / PR40 / PR41 / PR42
§2   Locked principles                   retrieval output ≠ Engine input
§3   Eight central questions             Q1 ~ Q8
§4   Why retrieval score ≠ Engine confidence (Q7)
§5   Common reading                      7-field uniform structure
§6   Type 1 — Vector search result
§7   Type 2 — Graph path
§8   Type 3 — LLM extraction
§9   Type 4 — SQL row
§10  Type 5 — File chunk
§11  Type 6 — API signal
§12  Type 7 — Manual analyst note
§13  Normalized evidence unit conditions (Q8)
§14  Pattern position                    7 layers now
§15  What this PR does NOT do
§16  Followup candidates                 C / D / E still unscheduled
§17  Closing meaning
```

17 sections. 752 lines. Zero ragcore source change.

## 2. 7 retrieval output types — uniform 7-field structure

Every retrieval type section answers the same 7 fields:

```text
- What the external output contains
- What must remain outside ragcore
- What adapter must translate
- Possible Engine target
- What must not be identity-piped
- raw_ref_id expectation
- Notes
```

Type-specific essence:

```text
Vector search result   chunk_id + similarity_score
                        adapter translates similarity → strength
                        (non-identity)

Graph path             node_id chain + path_score
                        adapter translates path_score → strength
                        adapter chooses 1 Relation per edge OR
                        1 path summary Relation (granularity is
                        adapter-owned)

LLM extraction         model_self_confidence + extracted_text
                        adapter caps strength heavily (e.g., ≤ 0.5)
                        claim ALWAYS CLAIM_STATUS_CANDIDATE
                        (LLM never auto-confirms)

SQL row                primary_key + column values
                        adapter strength near 1.0 for exact match
                        (SQL is deterministic)

File chunk             file_path + byte_range + chunk_hash
                        adapter strength varies by extraction quality
                        (regex high, LLM-on-chunk lower)

API signal             request_id + api_score + response fields
                        adapter classifies API into trust tiers and
                        applies different dampening per tier

Manual analyst note    analyst_id + note + confidence_label
                        discrete label → base_confidence mapping
                        analyst trust → strength dampening
```

Each type uses the same 7-field reading so future adapters can be audited against the same checklist.

## 3. PR41 executable invariants extended into PR42 natural-language guide

PR41 made the following 5 invariants executable:

```text
similarity 0.85   → strength != 0.85    (Vector)
path_score 0.75   → strength != 0.75    (Graph)
api_score 0.88    → strength != 0.88    (API)
LLM model_conf    → strength ≤ 0.5      (LLM, capped)
severity labels   → discrete mapping     (Manual)
```

PR42 explains the meaning of each invariant in plain text:

```text
- similarity score must not be identity-piped
  (relevance to query ≠ claim influence on downstream judgment)

- graph path_score must not be identity-piped
  (path weight ≠ claim confidence)

- API score must not be identity-piped
  (api-self-reported confidence semantics vary by provider)

- LLM model confidence is capped and candidate-only
  (LLM is a proposal source, not a judgment source)

- severity labels require discrete mapping
  (analyst label is not a continuous score)
```

The simulation tests enforce the rule. The guide explains why the rule exists. Together they form executable + readable invariant coverage.

## 4. §13 Normalized evidence unit conditions

PR42 §13 introduces the term *normalized evidence unit* — a conceptual list of fields an adapter SHOULD attach to translated output before calling Engine methods:

```text
- subject context
- claim target OR evidence target
- raw_ref_id (int)
- evidence_type (int from consumer registry)
- translated strength (non-identity, in [0.0, 1.0])
- reason_code or adapter reason
- enough provenance to resolve back to raw source
```

Critical lock (preserved in §13):

```text
This is conceptual.
This is adapter-owned.
This is not a ragcore type.
This must not be exported through ragcore.__all__.

Conceptual labels like CanonicalEvidenceAtom or EvidenceAtom may
be used on the consumer side, but they are NOT ragcore symbols.
```

The unit shape lives on the adapter side. ragcore receives only the resulting method call arguments.

## 5. 7-layer adapter documentation alignment (now complete)

```text
1. Philosophy           docs/01_CORE_PHILOSOPHY.md
                        Core 는 RAG / LLM / Graph DB 에 직접 연결하지 않는다

2. Runtime              docs/03_RUNTIME_LOOP.md
                        RAG / LLM / Graph DB 는 외부 Adapter 로 분리

3. Contract             docs/contracts/05_DATA_CONTRACT_MVP.md §50
                        External Knowledge Adapter Boundary

4. Audit                docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
                        7 adapter 후보 호환성 검증 (PR39)

5. Guide                docs/guides/ADAPTER_POLICY_GUIDE.md
                        Adapter policy decision surface (PR40)

6. Simulation           tests/test_external_adapter_simulation.py
                        Executable invariants (PR41)

7. Retrieval Translation Guide
                        docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md
                        Retrieval output → Evidence translation semantics
                        (PR42 — this)
```

Seven layers. Each present in the repository. PR42 adds the seventh by closing the documentation gap between "what to decide" (PR40) and "what works" (PR41) — namely, "what each retrieval output means inside ragcore".

## 6. What PR42 closed

```text
- retrieval output 이 Engine input 이 아니라는 의미를 7 type 별로 풀어 기록
- 7 output type 별 adapter translation 원칙 균일 구조로 명문화
- retrieval score ≠ Engine confidence 원칙 자연어 보강
- raw retrieved content 은 ragcore 밖에 남고 raw_ref_id 로 참조됨을 명시
- normalized evidence unit 은 conceptual adapter shape 이지 ragcore type 아님을 §13 잠금
- PR41 executable invariant 5 종과 1:1 대응되는 자연어 설명 제공
```

## 7. What PR42 deliberately did NOT do

PR42 did NOT:

```text
- pick concrete score formulas (similarity → strength functions)
- implement any actual retrieval adapter
- import vector DB / graph DB / LLM / SQL / file / API packages
- pick storage backends
- pick chunking / embedding / corpus strategies
- pick LLM models / API providers
- introduce domain vocabulary (security / medical / legal / etc.)
- implement Cerberus adapter
- add CanonicalEvidenceAtom / RetrievalResult / EngineInput
  as ragcore public types
- add to ragcore.__all__
- modify engine.py / types.py / __init__.py / rule_output.py
- add new tests (PR41 simulation already covers invariants)
- introduce new snapshot schema version
- introduce new public API
- propose PR43 or later
- trigger V-cerberus
- auto-select candidate area C / D / E
```

## 8. Confirmed invariants

```text
pytest -q                                1133 passing (unchanged from PR41)
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
external package imports in ragcore       0 (pinecone / weaviate /
                                           chromadb / qdrant_client /
                                           faiss / neo4j / openai /
                                           anthropic / psycopg /
                                           sqlalchemy — all absent)

adapter-specific symbols in ragcore.__all__:  none
ragcore type added in PR42:                 none
ragcore method surface change:               none
```

All framework invariants preserved.

## 9. Implementation footprint

Changed files (165 + 166):

```text
docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md    +752 lines (165차)
docs/dev/PR_042_RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE_MVP.md  this record (166차)
```

Unchanged:

```text
ragcore/engine.py
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
pyproject.toml
README.md
docs/contracts/05_DATA_CONTRACT_MVP.md
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
docs/guides/ADAPTER_POLICY_GUIDE.md
tests/test_external_adapter_simulation.py
examples/probe/external_consumer_probe.py
all other tests
all other docs/
```

No source change. No test change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change.

## 10. PR42 cycle

```text
165차  docs(guides) — Retrieval Output → Evidence Guide (+752 lines)   b3abd1f
166차  docs(dev) — PR42 record + ready + squash merge                  this commit
```

Two-차수 cycle. No new tests. No source change. No new public API.

## 11. Pattern position recap

```text
PR39  compatibility audit              — documentation-only, no source change
PR40  adapter policy guide             — documentation-only, no source change
PR41  external adapter simulation       — tests-only, no source change
PR42  retrieval translation guide      — documentation-only, no source change (this)

All four:
  ragcore source unchanged
  framework method surface frozen
  candidate areas C / D / E remain unscheduled
```

## 12. Followup candidate areas (still NOT PR-numbered)

```text
Candidate C — Engine Method Call Playbook
Candidate D — Anti-patterns Guide
Candidate E — Reference Flow
```

After PR42 merges, none of these are scheduled. PR42 does NOT auto-propose any of them. User decides next direction.

## 13. Framework state (post-PR42)

```text
ragcore baseline:
  main:    d853e9c (pre-merge; new hash after squash merge)
  1133 tests passing (unchanged from PR41)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  1 architecture audit (compatibility matrix)
  2 adapter guides (policy + retrieval translation)
  1 disposable probe (PR38-A)
  1 executable simulation test suite (PR41)

7-layer adapter documentation alignment:
  philosophy + runtime + contract + audit + guide + simulation + retrieval translation
  ✓ all seven layers present

ragcore source change since PR36-PKG:  0 lines
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 14. Final closing meaning

```text
PR42 maps each external retrieval output type to its possible Engine
targets without picking adapter formulas.

It answers WHAT each retrieval output BECOMES inside ragcore, while
keeping HOW it is translated as adapter responsibility.

Six prior layers (philosophy / runtime / contract / audit / guide /
simulation) answer different questions. PR42 adds a seventh layer
alongside Guide:

  PR40 = policy decisions       (what to decide)
  PR42 = translation semantics  (what becomes what)

Both are adapter-side concerns. ragcore stays generic.
```

Locked closing sentences:

```text
PR42 는 retrieval output 을 구현하지 않고,
retrieval output 이 adapter translation 을 거쳐 어떤 Engine-compatible
evidence structure 로 읽혀야 하는지 문서화하는 PR 이다.

Retrieval output is not Engine input.
Retrieval score is not Engine confidence.
Raw retrieved content must remain outside ragcore and be referenced
through raw_ref_id.
Normalized evidence unit is conceptual adapter-owned shape, not a
ragcore public type.
```

No automatic next-PR proposal. User decides direction.
