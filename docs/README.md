# Intelligent RAG Framework Documentation Map

Status: reader entry point / current navigation map
Type: reader entry point, no framework behavior change

## 0. Current baseline

```text
main:    d14c0892ce16f5dd25795bcf947fd1bbaad9cf6f
verified: 2026-06-28 (local; no CI / GitHub Actions configured)
tests:   2204 passing (local)
state:   Engine v1 refactoring COMPLETE — Phase 0–4 CLOSED

ragcore.__all__:            50 symbols
Engine public methods:      42
snapshot:                   schema_version 2 / 18 top-level keys
PR51 context packet:        7 keys
Engine structure:           thin C1 core + 9 private mixins + 2 pure kernels
authoritative boundary:     docs/architecture/ENGINE_V1_FINAL_BOUNDARY.md
external package imports in ragcore:     0
Engine v2:                  NOT STARTED  (separate GPT + user directive)
Cerberus integration:       NOT STARTED  (later roadmap)
```

`ragcore` is a generic judgment engine. The framework-side adapter boundary documentation stack is closed at ten layers. No consumer adapter is implemented in this repository.

> Historical note: this map was first authored at PR46-B (baseline `1d11077`, 1145
> tests, 40 public / 48 `__all__`). Those PR45-E/PR46-era numbers are superseded by
> the current baseline above; the per-PR review history is preserved in `docs/dev/`.

## 0a. Document taxonomy

```text
A. Current authoritative   README.md · docs/README.md ·
                           docs/contracts/05_DATA_CONTRACT_MVP.md ·
                           docs/architecture/ENGINE_V1_FINAL_BOUNDARY.md ·
                           ENGINE_V1_REFACTORING_PLAN.md (completed) ·
                           ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md (accepted)
B. Consumer guides         docs/guides/** — the 10-layer adapter/integration stack
                           (consumer integration docs, NOT the current impl-state map)
C. Historical / audit      docs/dev/** · docs/archive/** · superseded architecture docs
                           (e.g. ENGINE_INTERNAL_MAP.md) · PR-body reconstruction records
D. Future / not started    Engine v2 (physics / projection / identity / materialization) ·
                           Cerberus integration · production consumer adapter
```

## 1. What this framework is / is not

```text
ragcore IS:
  - a generic judgment engine
  - the owner of Engine state, lifecycle, confidence, snapshot
  - a frozen public surface of 42 methods / 50 __all__ symbols
  - RAG-agnostic (any vector / graph / SQL / file / API / manual
    retrieval is consumer-side; ragcore does not require any)

ragcore IS NOT:
  - a retrieval system
  - a vector database
  - a content store
  - a domain-specific scanner / analyzer / report renderer
  - a Cerberus-specific module
  - a runtime enforcer of adapter policies
```

If you need retrieval, storage, domain vocabulary, scoring calibration, or report rendering, those are consumer responsibilities and live outside this repository.

## 2. Start here — shortest reading path

If you read only three documents:

```text
1. docs/01_CORE_PHILOSOPHY.md
     - what ragcore is, what it is not, and why

2. docs/contracts/05_DATA_CONTRACT_MVP.md  (§50 in particular)
     - the external adapter boundary contract

3. docs/guides/DOMAIN_NEUTRAL_REFERENCE_FLOW.md   (PR45-E)
     - the 10-phase domain-neutral flow that binds the rest
```

After these three, the rest of the stack reads as elaboration.

## 3. Reader path A — Consumer integrating against the framework

Audience: you are building a consumer system that will call `ragcore.Engine` public methods. You write the adapter; ragcore stays generic.

Recommended order:

```text
A.1  Philosophy
     docs/01_CORE_PHILOSOPHY.md
       Core 는 외부 RAG / LLM / Graph DB 에 직접 연결하지 않는다.

A.2  Runtime
     docs/03_RUNTIME_LOOP.md
       외부 Adapter 분리.

A.3  External Adapter Boundary Contract
     docs/contracts/05_DATA_CONTRACT_MVP.md §50
       External Knowledge Adapter Boundary.

A.4  Adapter Policy Guide                                          (PR40)
     docs/guides/ADAPTER_POLICY_GUIDE.md
       10 policy decisions every adapter must answer.

A.5  Retrieval Output → Evidence Guide                             (PR42)
     docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md
       7 retrieval output types and their translation semantics.

A.6  Engine Method Call Playbook                                   (PR43-C)
     docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md
       public method surface, 8 layers, two-path model, 15-step safe
       default call order. (Guide authored at the 40-method surface; the
       current public surface is 42 — see §0. The added methods are
       additive; the documented call order is unchanged.)

A.7  Engine Integration Anti-patterns                              (PR44-D)
     docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md
       24 stable-ID misuse patterns to avoid (AP-I-*, AP-X-*, ...).

A.8  Domain-neutral Reference Flow                                 (PR45-E)
     docs/guides/DOMAIN_NEUTRAL_REFERENCE_FLOW.md
       10 conceptual phases, one end-to-end story.
```

You can stop reading at any point and you will still have a coherent picture; the documents are layered, not cumulative.

## 4. Reader path B — Framework contributor / reviewer

Audience: you are reading, reviewing, or proposing changes to `ragcore` itself (not building a consumer adapter).

Recommended order:

```text
B.1  Identity
     docs/00_PROJECT_IDENTITY.md
     docs/01_CORE_PHILOSOPHY.md

B.2  Architectural layers
     docs/02_LAYER_MODEL.md
     docs/03_RUNTIME_LOOP.md

B.3  Contract surface
     docs/contracts/05_DATA_CONTRACT_MVP.md
     docs/contracts/04_C_CORE_BOUNDARY.md
     docs/contracts/06_MEMORY_RAG_GATE.md

B.4  Compatibility audit
     docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md     (PR39)

B.5  Engine source surface (thin C1 core + 9 mixins — not one file)
     ragcore/engine.py            thin C1 core + the 9-mixin composition
     ragcore/_engine/*.py         the 9 private mixins + the 2 pure kernels
                                  (serialization, confidence)
     ragcore/types.py
     ragcore/__init__.py
     ragcore/rule_output.py
     docs/architecture/ENGINE_V1_FINAL_BOUNDARY.md   (read this first for structure)

B.6  Executable invariants
     tests/test_external_adapter_simulation.py                      (PR41,  18 tests)
     tests/test_engine_method_call_playbook_usage.py                (PR43-C, 12 tests)

B.7  Recent dev records (post-PR36-PKG, no source change)
     docs/dev/PR_037_INTEGRATION_READINESS_BOUNDARY_MVP.md
     docs/dev/PR_038A_EXTERNAL_CONSUMER_PROBE_MVP.md
     docs/dev/PR_038B_EXTERNAL_KNOWLEDGE_ADAPTER_BOUNDARY_MVP.md
     docs/dev/PR_039_EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX_MVP.md
     docs/dev/PR_040_ADAPTER_POLICY_GUIDE_MVP.md
     docs/dev/PR_041_EXTERNAL_ADAPTER_SIMULATION_TESTS_MVP.md
     docs/dev/PR_042_RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE_MVP.md
     docs/dev/PR_043_ENGINE_METHOD_CALL_PLAYBOOK_MVP.md
     docs/dev/PR_044_ENGINE_INTEGRATION_ANTI_PATTERNS_MVP.md
     docs/dev/PR_045_DOMAIN_NEUTRAL_REFERENCE_FLOW_MVP.md

B.8  Git workflow
     docs/09_GIT_WORKFLOW.md

B.9  Earlier roadmap (historical context, may differ from current state)
     docs/roadmap/07_IMPLEMENTATION_ROADMAP.md
     docs/agent/08_CLAUDE_IMPLEMENTATION_BRIEF.md
```

Older dev records (PR_001 … PR_036) cover modifier composition, snapshot evolution, lifecycle, and method-surface freezing. Read them when reviewing the matching layer of `engine.py`.

## 5. Reader path C — Future AI assistant / code reviewer

Audience: you are an AI assistant continuing this project across sessions, or a code reviewer needing fast context recovery.

Goal: quickly recover baseline, frozen boundaries, and forbidden next-step assumptions.

Recommended order:

```text
C.1  Current baseline
     This file (docs/README.md), §0.

C.2  Forbidden next steps
     This file, §9 "Hard stop rules."

C.3  The four lock sentences (do not paraphrase, do not weaken)
     docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md §2
     docs/guides/DOMAIN_NEUTRAL_REFERENCE_FLOW.md §2
     docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md §2

C.4  Frozen public surface + final structure
     ragcore/__init__.py  (50 __all__ symbols)
     ragcore/engine.py    (42 public methods; thin C1 core + 9 mixins)
     docs/architecture/ENGINE_V1_FINAL_BOUNDARY.md  (authoritative structure)
     docs/dev/PR_036_ENGINE_METHOD_SURFACE_FREEZE_MVP.md  (historical freeze record)

C.5  Executable invariants
     tests/test_external_adapter_simulation.py
     tests/test_engine_method_call_playbook_usage.py

C.6  Most recent dev record (current state of the world)
     docs/dev/PR_045_DOMAIN_NEUTRAL_REFERENCE_FLOW_MVP.md
     docs/dev/PR_044_ENGINE_INTEGRATION_ANTI_PATTERNS_MVP.md
     docs/dev/PR_043_ENGINE_METHOD_CALL_PLAYBOOK_MVP.md
```

If a session begins with no other context, reading these six items in order recovers enough to continue safely without proposing a forbidden next step.

## 6. The 10-layer adapter documentation stack

```text
 1. Philosophy            docs/01_CORE_PHILOSOPHY.md
 2. Runtime               docs/03_RUNTIME_LOOP.md
 3. Contract              docs/contracts/05_DATA_CONTRACT_MVP.md §50
 4. Audit                 docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
                                                                   (PR39)
 5. Guide (policy)        docs/guides/ADAPTER_POLICY_GUIDE.md       (PR40)
 6. Simulation             tests/test_external_adapter_simulation.py
                                                                   (PR41, 18 tests)
 7. Guide (retrieval)     docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md
                                                                   (PR42)
 8. Guide (call order)    docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md (PR43-C)
    + usage invariants     tests/test_engine_method_call_playbook_usage.py
                                                                   (PR43-C 168차, 12 tests)
 9. Guide (anti-patterns) docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md
                                                                   (PR44-D)
10. Guide (reference flow) docs/guides/DOMAIN_NEUTRAL_REFERENCE_FLOW.md
                                                                   (PR45-E)
```

Each higher-numbered layer assumes the lower ones. Layers 6 and 8's usage invariants are executable; the rest are documentation.

## 7. Positive / negative / reference triad

```text
PR43-C  positive path        how to call Engine public methods safely
PR44-D  negative boundary    what NOT to do (24 named anti-patterns)
PR45-E  reference flow       how the full external-consumer flow connects
```

This triad is complete. New documentation about how to integrate against `ragcore` should fit into one of these three modes, not invent a fourth.

## 8. What is implemented vs not implemented

Implemented (inside this repository):

```text
- ragcore.Engine and its 42 public methods (thin C1 core + 9 private mixins)
- 50 __all__ symbols
- 2 pure kernels (serialization, confidence) + Engine v1 refactoring (Phase 0–4)
- 7 modifier composition (PR12 ~ PR21, PR23, PR24, PR26)
- Lifecycle helpers (PR6 ~ PR10, PR15)
- Snapshot v2 with migration framework (PR17, PR18, PR21-L)
- 18 simulation tests covering 7 fake retrieval scenarios (PR41)
- 12 playbook usage invariants (PR43-C 168차)
- 10-layer adapter documentation stack (PR39 ~ PR45-E)
```

NOT implemented (intentionally):

```text
- actual consumer adapter
- production adapter package
- real vector DB / graph DB / SQL / LLM integration
- domain-specific reference implementation
- Cerberus adapter
- runtime enforcement for anti-patterns
- contract §51 expansion
- additional public Engine API beyond the 42
- new scoring / modifier calibration
- README / package release polish beyond current state
```

These are not failures. They are separate decision branches.

## 9. Hard stop rules

The following must NOT start automatically. Each requires an explicit user decision:

```text
- Cerberus adapter inside ragcore
- production consumer adapter inside ragcore
- domain-specific reference implementation inside ragcore
- new Engine API
- modifier / scoring recalibration without real evidence
- contract §51 (or any new contract section)
- runtime enforcement layer
- domain vocabulary (vulnerability / scanner / host / port / etc.)
  in ragcore source or in guide narrative
- adapter-specific symbols added to ragcore.__all__
- private state / helper / constant exposed as part of the contract
  (see PR44-D AP-X-8)
```

Most of these are anti-patterns named in `docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md`. Cite the AP-* ID rather than re-arguing the boundary.

## 10. Current roadmap / next-step options

Engine v1 refactoring is COMPLETE (Phase 0–4 CLOSED). There is no automatic next
implementation PR. Every track below requires an explicit user / GPT directive:

```text
1. Engine v2 — physics / math model / projection / state-identity /
   materialization boundary. NOT STARTED. Designed by GPT + user; ragcore
   contributors implement only after that directive exists.
2. Cerberus + Engine integration. NOT STARTED. Separate repo / decision.
3. Consumer feedback-driven compatibility evolution — only after real usage
   exposes a missing public method, a snapshot gap, or a confidence
   miscalibration. Requires a migration plan, not a theory-driven edit.
4. Additional documentation / release work.
```

The recommended default is to wait for an explicit directive. Updating this map does
not start v2 or any integration.

---

## Closing meaning

```text
Engine v1 refactoring is complete; this map is the current navigation entry point.

It does not add framework behavior.
It does not add tests.
It does not implement an adapter.
It does not change the Engine public surface (still 42 / 50 / snapshot 2·18 / packet 7).

The current structure is authoritative in docs/architecture/ENGINE_V1_FINAL_BOUNDARY.md.
The framework waits for an explicit next directive.
```
