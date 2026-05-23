# PR41 — External Adapter Simulation Tests MVP

## Scope limitation (locked, user 2026-05-22)

```text
PR41 does not implement external adapters.

PR41 does not import real vector DB, graph DB, LLM, SQL, file store,
API, or manual-note systems.

PR41 only simulates adapter-owned translations and verifies that the
frozen Engine public method surface can receive them safely.
```

한국어:

```text
PR41 은 실제 외부 Adapter 구현이 아니다.

PR41 은 여러 RAG 타입의 fake output 이 adapter translation 을 거치면
현재 Engine public API 로 안전하게 들어갈 수 있음을
executable simulation 으로 검증한 PR 이다.
```

PR41 makes the documented adapter boundary (PR38-B §50 / PR39 / PR40) executable for the first time. Until PR41, the boundary lived only in documentation. After PR41, the test suite enforces it.

## 1. 7 simulation scenarios

```text
1. Vector result simulation              fake vector DB result + similarity
                                          translation
2. Graph path simulation                  fake graph DB path + path_score
                                          translation + add_relation
3. LLM extraction simulation              fake LLM output + 0.5 cap +
                                          CANDIDATE-only claim
4. SQL row simulation                     fake SQL row + adapter
                                          default strength
5. File chunk simulation                  fake file chunk + hash-based
                                          raw_ref resolution
6. API signal simulation                  fake API signal + score
                                          dampening translation
7. Manual analyst note simulation         fake analyst note + severity
                                          label mapping
```

Each scenario uses only ragcore public API. Each scenario uses test-local fake payloads. No real external packages.

## 2. 18 new tests breakdown

```text
TestVectorResultSimulation              2 tests
  - test_vector_result_flows_through_public_api
  - test_similarity_score_is_not_identity_piped_to_strength

TestGraphPathSimulation                  2 tests
  - test_graph_path_flows_through_public_api
  - test_path_score_is_not_identity_piped

TestLLMExtractionSimulation              2 tests
  - test_llm_extraction_creates_candidate_claim
  - test_llm_confidence_is_capped_by_adapter_policy

TestSQLRowSimulation                     1 test
  - test_sql_row_flows_through_public_api

TestFileChunkSimulation                   1 test
  - test_file_chunk_flows_through_public_api

TestAPISignalSimulation                  2 tests
  - test_api_signal_flows_through_public_api
  - test_api_score_is_not_identity_piped

TestManualNoteSimulation                 2 tests
  - test_manual_note_flows_through_public_api
  - test_severity_label_translates_to_base_confidence_via_policy

TestExternalAdapterGenericInvariants     6 tests
  - test_adapter_specific_symbols_not_in_ragcore_all
  - test_ragcore_engine_does_not_import_external_packages
  - test_all_scenarios_preserve_snapshot_top_level_keys
  - test_compute_effective_confidence_bounds_after_each_scenario
  - test_engine_method_surface_remains_frozen
  - test_ragcore_all_remains_48_symbols
```

Total: 18 tests, 8 classes.

## 3. Test-local helper boundary

```text
Test-local helpers (consumer/adapter-side simulation):

  _TestLocalRawRefResolver                external string → int resolver
                                           (test-local class)
  _FakeVectorResult / _FakeGraphPath /
  _FakeLLMExtraction / _FakeSQLRow /
  _FakeFileChunk / _FakeAPISignal /
  _FakeManualNote                          7 fake payload dataclasses
                                           (test-local @dataclass(frozen=True))

  _translate_similarity_to_strength        non-identity policy
  _translate_path_score_to_strength       non-identity policy
  _translate_llm_confidence_to_strength    non-identity, capped at 0.5
  _translate_severity_to_base_confidence    labeled discrete mapping
  _translate_api_score_to_strength         non-identity dampening

  Test-local integer registries:
    _ENTITY_TYPE_*          5 values
    _OBSERVATION_TYPE_*     7 values
    _SOURCE_TYPE_*           7 values
    _CLAIM_TYPE_*           7 values
    _EVIDENCE_TYPE_*        7 values
    _REASON_CODE_DIRECT     1 value
```

```text
These helpers are test-local.

They are NOT production adapters.
They are NOT exported through ragcore.__all__.
They do NOT define the framework contract.

All helper symbols use underscore prefix. They cannot be imported via
`from ragcore import ...`. They cannot be accessed outside the test
module.
```

## 4. Non-identity translation invariant

For the first time, the "identity mapping forbidden" rule (PR38-B §50.9 / §50.10) is enforced by executable assertions:

```text
similarity 0.85    → strength != 0.85    (Vector)
path_score 0.75    → strength != 0.75    (Graph)
api_score 0.88     → strength != 0.88    (API)
LLM model_conf 0.92 → strength <= 0.5    (LLM, capped)
severity labels    → discrete mapping     (Manual)
                     "low" < 0.5
                     "medium" < 0.7
                     "high" >= 0.7
                     "critical" >= 0.9
```

Meaning:

```text
§50.9 / §50.10 identity-mapping-forbidden rule is now executable.

Any future PR that proposes a direct external-score → confidence
pipe will fail one of these test assertions. The rule is no longer
just a documentation guideline; it is enforced.
```

## 5. 6-layer adapter documentation alignment

```text
1. Philosophy   docs/01_CORE_PHILOSOPHY.md
                Core 는 RAG / LLM / Graph DB 에 직접 연결하지 않는다

2. Runtime      docs/03_RUNTIME_LOOP.md
                RAG / LLM / Graph DB 는 외부 Adapter 로 분리

3. Contract     docs/contracts/05_DATA_CONTRACT_MVP.md §50
                External Knowledge Adapter Boundary

4. Audit        docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
                7 adapter 후보 호환성 검증 (PR39)

5. Guide        docs/guides/ADAPTER_POLICY_GUIDE.md
                Adapter policy decision surface (PR40)

6. Simulation   tests/test_external_adapter_simulation.py
                Executable invariants for adapter boundary (PR41 — this)
```

Six layers. Each present in the repository. PR41 closes the last layer — moving from documentation to enforcement.

## 6. Confirmed invariants

```text
pytest -q                          1133 passing
  (was 1115 at PR40 baseline, +18 from PR41)
  
ragcore.__all__                    48 symbols (PR31-S baseline preserved)
unique symbols                      48
Engine public methods               40 (PR33-M docstring 40/40 preserved)
modifier helpers                     6 with (self, claim_id: int) -> float
                                    (PR34-O signature preserved)
serialize/restore symmetry          6 × 6 (PR35-O7 preserved)
snapshot schema_version              2 (PR21-L preserved)
snapshot top-level keys             18 (PR36-PKG _LOCKED_SNAPSHOT_TOP_LEVEL_KEYS)

effective_confidence after each scenario:  in [0.0, 1.0]

adapter-specific symbols in ragcore.__all__:  none
                                              (all underscore-prefixed,
                                               none promoted)

external package imports in ragcore.engine:  none
                                              (pinecone / weaviate /
                                               chromadb / qdrant_client /
                                               faiss / neo4j / openai /
                                               anthropic / psycopg /
                                               sqlalchemy — all absent)

LLM scenario:
  claim status remains CLAIM_STATUS_CANDIDATE
  model_confidence capped at 0.5 via adapter policy
  (LLM never auto-confirms a claim)

ragcore source change since PR36-PKG:  0 lines
ragcore source cerberus mentions:       0 (generic identity preserved)
Cerberus / V-cerberus entered:          no
```

All framework invariants preserved across PR41.

## 7. Implementation footprint

Changed files (163 + 164):

```text
tests/test_external_adapter_simulation.py                  +729 lines (163차)
docs/dev/PR_041_EXTERNAL_ADAPTER_SIMULATION_TESTS_MVP.md   this record (164차)
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
examples/probe/external_consumer_probe.py
all other test files
```

No source change. No external dependency added. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change.

## 8. Non-goals (preserved across PR41)

PR41 deliberately did NOT:

```text
- import real external packages (chromadb / qdrant_client / faiss /
  neo4j / openai / anthropic / psycopg / sqlalchemy / etc.)
- make any network call
- perform any DB or file IO
- modify engine.py / types.py / __init__.py / rule_output.py
- add to ragcore.__all__
- add production adapter classes
- add runtime type validation in Engine
- add Cerberus-specific terms
- propose PR42 or later
- trigger V-cerberus
- auto-select candidate area B / C / D / E
- introduce new snapshot schema version
- introduce new public API
- introduce CanonicalEvidenceAtom / RetrievalResult / EngineInput
  as ragcore types
```

## 9. Followup candidate areas (still NOT PR-numbered)

```text
Candidate B — Retrieval Output → Evidence Guide
Candidate C — Engine Method Call Playbook
Candidate D — Anti-patterns Guide
Candidate E — Reference Flow
```

After PR41 merges, none are scheduled. PR41 does NOT auto-propose any of them.

## 10. Framework state (post-PR41)

```text
ragcore baseline:
  main:    c83e83e (pre-merge; new hash after squash merge)
  1133 tests passing (1115 pre-PR41 + 18 simulation tests)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  1 architecture audit (compatibility matrix)
  1 adapter policy guide
  1 disposable probe (PR38-A)
  1 executable simulation test suite (this PR)
  
6-layer adapter documentation alignment:
  philosophy + runtime + contract + audit + guide + simulation
  ✓ all six layers present and enforced

ragcore source change since PR36-PKG:  0 lines
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 11. Final closing meaning

```text
PR41 is the first PR to make the adapter boundary executable.

PR38-B / PR39 / PR40 documented the boundary.
PR41 made it enforceable.

If any future PR proposes adapter behavior that violates the locked
principles (identity-piping similarity, importing external packages
into ragcore, promoting adapter-specific symbols, etc.), one of the
18 simulation tests will fail.

The framework now waits.
```

Locked closing sentences:

```text
PR41 은 실제 외부 Adapter 구현이 아니라,
여러 RAG 타입의 fake output 이 adapter translation 을 거치면
현재 Engine public API 로 안전하게 들어갈 수 있음을
executable simulation 으로 검증한 PR 이다.

§50.9 / §50.10 identity mapping forbidden rule is now executable.

No automatic next-PR proposal. User decides direction.
```
