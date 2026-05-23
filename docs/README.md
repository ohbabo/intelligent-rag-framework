# Intelligent RAG Framework Documentation Map

Status: documentation map (PR46-B)
Baseline: main `1d11077` (PR45-E merged)
Type: reader entry point, no framework behavior change

## 0. Current baseline

```text
main:    1d11077
tests:   1145 passing
state:   Domain-neutral Reference Flow complete (PR45-E)
next:    NONE 자동 진입 없음 — framework waits

ragcore.__all__:            48 symbols
Engine public methods:      40
ragcore source change since PR36-PKG:   0 lines
ragcore source cerberus mentions:        0
external package imports in ragcore:     0
contract §51:                            not added
runtime enforcement:                     0
adapter implementation:                  0
```

`ragcore` is a generic judgment engine. The framework-side adapter boundary documentation stack is closed at ten layers. No consumer adapter is implemented in this repository.

## 1. What this framework is / is not

```text
ragcore IS:
  - a generic judgment engine
  - the owner of Engine state, lifecycle, confidence, snapshot
  - a frozen public surface of 40 methods / 48 __all__ symbols
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
       40 public methods, 8 layers, two-path model, 15-step safe
       default call order.

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

B.5  Engine source surface
     ragcore/engine.py
     ragcore/types.py
     ragcore/__init__.py
     ragcore/rule_output.py

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

C.4  Frozen public surface
     ragcore/__init__.py  (48 __all__ symbols)
     ragcore/engine.py    (40 public methods)
     docs/dev/PR_036_ENGINE_METHOD_SURFACE_FREEZE_MVP.md

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
- ragcore.Engine and its 40 public methods
- 48 __all__ symbols
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
- additional public Engine API beyond the 40
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

## 10. Current next-step options

The framework has no automatic next PR. Open options at this point:

```text
Option 1 — Stop and freeze
  Optional: add a freeze record at a path such as
  docs/dev/PR_046_FRAMEWORK_BASELINE_FREEZE.md  (file not present;
  would be created by an explicit Track A decision). No code
  change. Pure record.

Option 2 — Continue documentation polish
  Already chosen for PR46-B (this file).
  Possible micro-additions (NOT auto-scheduled, files not present):
    - PR46-B2: README integration index (top-level README.md edit)
    - CHANGELOG.md  or  docs/RELEASE_NOTES.md

Option 3 — Additional executable guards
  Possible, but easy to make brittle. Not recommended unless a
  specific drift risk is identified. Examples:
    - tests/test_documentation_stack_integrity.py
    - tests/test_anti_pattern_guide_integrity.py

Option 4 — Consumer adapter implementation
  Happens in a SEPARATE repo / SEPARATE decision.
  Not a framework PR by default.
  See PR44-D §5.6 (domain vocab intrusion guard) and §5.7
  (__all__ promotion guard) before starting.

Option 5 — Engine evolution from real feedback
  Only after real consumer usage exposes a missing public method,
  a snapshot field gap, or a systematic confidence miscalibration.
  Do not evolve from theory alone. Each change requires migration
  plan + backward compatibility discussion.
```

The recommended default is to wait. No automatic next PR.

---

## Closing meaning

```text
PR46-B makes the completed documentation stack discoverable.

It does not add framework behavior.
It does not add tests.
It does not implement an adapter.
It does not add contract §51.
It does not change the Engine public surface.

The framework reads as a stack now.
The framework waits.
```
