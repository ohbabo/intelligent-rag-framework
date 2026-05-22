# PR38-A — External Consumer Probe MVP

Lock sentences (user 2026-05-22):

```text
PR38-A is a disposable external-consumer pressure test,
not a Cerberus optimization layer.

Cerberus is the first concrete sample case,
not the framework contract.

ragcore remains a generic judgment engine.

No Cerberus-specific concept discovered by this probe may be
promoted into ragcore core types or methods.

PR38-B may freeze §50 only after auditing the PR38-A probe results.
```

## 1. Purpose

PR38-A passes one realistic external-consumer observation through `ragcore.Engine`'s GENERIC public API to observe what fields are actually required when crossing the boundary between a domain consumer and the generic judgment engine.

The probe is **not** a Cerberus adapter. It is **not** a RAG implementation. It is a pressure test for the engine's generic method surface against the first concrete external-consumer case.

## 2. Scope

Single file added:

```text
examples/probe/external_consumer_probe.py    (+479 lines, disposable)
```

Probe contents:
- 1 sample external observation (Cerberus SSH finding from nmap)
- 6 ragcore.Engine public-API calls (`add_entity` / `add_observation` / `add_claim` / `add_evidence` / `compute_effective_confidence` / `to_snapshot`)
- 8 reality questions answered generically with "case: Cerberus..." footnotes
- §50 implication summary (all domain-neutral)
- Invariant lock sentences at file header

Branch: `feat/pr38a-disposable-probe`
Baseline: main `287eed5` (PR37 merged)

## 3. Non-goals

PR38-A explicitly does NOT:

```text
- change ragcore/ source code
- change tests
- change Engine method surface (PR36-PKG _LOCKED_* preserved)
- change snapshot schema
- change report frozensets
- write §50
- define CanonicalEvidenceAtom as a final type
- define RetrievalResult as a final type
- define EngineInput as a final type
- promote any Cerberus-specific concept into ragcore core
- choose a vector DB / embedding model / corpus format
- claim production readiness
- claim Cerberus integration is implemented
```

## 4. Probe execution result

Verified output (run via `PYTHONPATH=. python examples/probe/external_consumer_probe.py`):

```text
=== PR38-A External Consumer Probe ===

Sample external observation (case: Cerberus SSH finding):
  asset_id:    10.0.1.42
  service:     ssh
  product:     OpenSSH
  version:     7.4
  port:        22

ragcore.Engine state (after adapter-side mapping):
  entity_id:                1
  observation_id:           1
  claim_id:                 1
  evidence_id:              1

Engine output:
  effective_confidence:     0.9

Snapshot:
  top-level keys:           18
  schema_version:           2
  claims_count:             1
  evidences_count:          1
  observations_count:       1
  entities_count:           1
```

Engine accepted all calls with no surface adjustment. The probe successfully crossed the boundary using **public API only**.

## 5. Generic identity preservation

Diagnostic counts after PR38-A:

```text
ragcore/ source cerberus mentions:       0   (clean — generic engine identity preserved)
examples/probe/ cerberus mentions:       29  (all "case:" / "sample" framing only)
ragcore source change:                    0 lines
test change:                               0 lines (1115 passing unchanged)
PR31-S _PR30_BASELINE_PUBLIC_SYMBOLS:     unchanged
PR32-V *_KEYS frozensets:                 unchanged
PR36-PKG _LOCKED_* frozensets:            unchanged
schema_version:                            2 (unchanged)
```

ragcore source code contains zero references to "cerberus", "ssh", "security", "vulnerability", "scanner", or any domain-specific term. The framework remains a generic judgment engine.

All Cerberus references live inside `examples/probe/` — explicitly labeled "case:" / "sample" — and inside `docs/dev/` PR records (historical motivation).

## 6. Reality questions answered

The 8 reality questions (from PR_037 + PR_038 plan) were rephrased generically with Cerberus as the sample case. Generic answers:

| # | Question (generic) | Answer (generic) |
| - | ------------------ | ---------------- |
| Q1 | Subject granularity | **adapter decides** per domain. Engine does not know if subject is asset/service/endpoint. |
| Q2 | Evidence granularity | **normalized evidence unit**, not raw tool output. |
| Q3 | raw_ref interpretation | **consumer-side resolver key**, not engine-interpreted value. |
| Q4 | confidence source | **adapter policy** translates raw signal (vector similarity, scanner severity, retrieval score) → base_confidence + strength. Engine never accepts raw signal as confidence. |
| Q5 | integer registries | **consumer-side responsibility**: entity_type / claim_type / evidence_type / observation_type / source_type / reason_code registries are all maintained by the consumer. |
| Q6 | snapshot storage | **consumer-owned storage**. Engine returns a dict; the consumer holds it. (References PR36-PKG §48.9 + PR37 README persistence boundary.) |
| Q7 | retrieval / vector DB results | **MUST pass through adapter's evidence-atom translation**. Vector similarity is NOT engine confidence. (Forced by Evidence shape: int / int / float row.) |
| Q8 | §50 contract scope | **adapter boundary only**, not domain vocabulary or specific RAG implementation. |

## 7. §50 implications

The next contract (PR38-B) should define an **adapter boundary**, not a RAG implementation.

It should explain how external knowledge outputs become Engine method calls, without freezing:

- vector DB choice
- embedding model
- storage backend
- domain vocabulary
- consumer-side integer assignments
- retrieval ranking
- RAG architecture (vector / graph / SQL / static / hybrid / manual)

The §50 contract SHOULD freeze (all domain-neutral, all RAG-agnostic):

```text
- adapter MUST maintain type registries (consumer-side integers)
- adapter MUST maintain raw_ref_id resolution strategy
- adapter MUST translate retrieval, not pipe through
- storage is consumer-side (reference PR36-PKG §48.9)
- base_confidence + strength are adapter-set
- 7-modifier composition is engine-internal
- similarity score (vector / fuzzy / lexical / any) is NOT engine confidence
- snapshot dict is consumer-owned after to_snapshot() returns
```

## 8. What §50 must not freeze

The probe explicitly identifies what §50 must NOT include:

```text
NOT in §50:
  - Cerberus-specific type / method / enum
  - SSH / security / vulnerability / scanner naming
  - vector DB schema requirement
  - embedding model version requirement
  - retrieval architecture requirement
  - chunking strategy requirement
  - corpus format requirement
  - storage backend choice
  - domain-specific severity enum
  - product-specific pipeline stages
```

These are all consumer-side / adapter-side concerns. ragcore does not own them.

The framework supports **any external knowledge layer** — vector DB, graph DB, SQL evidence store, API signal aggregator, static rule corpus, manual analyst notes, local file corpus, hybrid retrieval, no retrieval at all — as long as the consumer translates inputs into Engine method calls.

## 9. Regression check

```text
pytest -q:                    1115 passed (unchanged from PR37)
ragcore.__all__:              48 symbols (PR31-S baseline preserved)
unique symbols:                48
Engine public methods:        40 (PR33-M docstring coverage preserved)
modifier helpers:              6 with (self, claim_id: int) -> float (PR34-O)
serialize/restore symmetry:   6 × 6 (PR35-O7)
snapshot schema_version:      2 (PR21-L)
Engine method surface:         frozen (PR36-PKG _LOCKED_PUBLIC_METHODS)
Snapshot top-level keys:      18 (PR36-PKG _LOCKED_SNAPSHOT_TOP_LEVEL_KEYS)
Report key frozensets:        6 sets (PR32-V)
README.md:                    unchanged from PR37 (252 lines)
pyproject.toml:                unchanged from PR36-PKG 149차
```

All invariants from PR31-S / PR32-V / PR33-M / PR34-O / PR35-O7 / PR36-PKG / PR37 preserved.

## 10. PR38-B entry condition

PR38-B can start only after PR38-A merges.

PR38-B inputs:

```text
- examples/probe/external_consumer_probe.py        (this PR's probe code)
- this dev record (PR_038A_EXTERNAL_CONSUMER_PROBE_MVP.md)
- 8 generic reality-question answers (§6 above)
- §50 domain-neutral implications (§7 + §8 above)
```

PR38-B output:

```text
§50 External Knowledge Adapter Boundary
  (NOT "RAG Operational Boundary" — too narrow, biased toward
   one knowledge-layer architecture)
```

PR38-B must not:

```text
- optimize for Cerberus
- define security-specific core types
- require vector DB
- require one RAG architecture
- write Cerberus pipeline rules
- choose embedding model / chunking / corpus format
- introduce domain vocabulary
```

PR38-B audit target: this probe file (`external_consumer_probe.py`) is the existing code that PR38-B's audit-first cycle will inspect to derive §50. This restores the audit-first pattern that worked for PR33-M / PR34-O / PR35-O7.

After PR38-B merges, this probe file may be:
- deleted (clean removal — disposable by design)
- OR moved to `docs/archive/` (kept as historical reference)

The decision is left to PR38-B record.

---

## Project status snapshot (post-PR38-A)

Cerberus engine frame completion estimate (user 2026-05-22):

```text
Already complete:
  ragcore generic Engine                       (PR1~PR36)
  method surface freeze                         (PR36-PKG §48)
  package / import boundary                     (PR36-PKG)
  snapshot persistence + migration              (PR17 / PR18-K / PR21-L)
  report surface                                 (PR32-V §44)
  consumer interpretation policy                 (PR30-P §42)
  README quickstart + persistence + stability   (PR37 §49 + README)
  integration discoverability                    (PR37 §49)
  external-consumer probe                        (PR38-A — this PR)

Remaining for "Cerberus engine frame":
  PR38-B     External Knowledge Adapter Boundary §50  (audit this probe → contract)
  V-cerberus thin adapter                              (cerberus_client repo)

Order:
  PR38-A complete → PR38-B contract → V-cerberus implementation

Remaining categorical work:
  structural connection boundary (NOT research)
  no new algorithm, no new mathematics, no new judgment policy
  algorithm refinement deferred to post-V-cerberus (driven by real usage)

Completion criteria for "Cerberus engine frame":
  1. Cerberus does not know ragcore internals
  2. Cerberus calls only public methods
  3. Cerberus finding is translated by adapter into Claim/Evidence/Gap/Relation
  4. RAG / vector DB / corpus / storage are Cerberus-owned
  5. ragcore provides judgment state + snapshot only
  6. mathematics / algorithm is replaceable later
  7. Engine method surface remains frozen
```

PR38-A satisfies criteria 1 / 2 / 5 / 6 / 7 already. PR38-B + V-cerberus address 3 / 4.

---

## Final meaning

PR38-A is the moment the framework demonstrated its own generic-ness against a concrete external consumer without absorbing the consumer's domain into core types.

```text
Before PR38-A:
  ragcore generic-ness was asserted in contract (§48, §49)
  but never tested with real external-consumer pressure.

After PR38-A:
  ragcore generic-ness is observed with one external-consumer sample.
  ragcore source code remains free of Cerberus-specific concepts.
  examples/probe/ holds the disposable evidence.
  PR38-B can now derive §50 from real probe data, not speculation.
```

Locked closing sentences (user 2026-05-22):

```text
켈베로스는 첫 사용 사례일 뿐이고,
프레임워크의 기준이 되면 안 된다.

지능형 RAG 프레임워크는 특정 RAG 구현을 강제하지 않는다.
사용자는 어떤 RAG / 지식층 형태든 자유롭게 사용할 수 있다.

ragcore 의 책임은 RAG 를 만드는 것이 아니라,
외부 지식층이 가져온 신호를 Claim / Evidence / Gap / Relation 단위로
판단할 수 있는 안정적인 method surface 를 제공하는 것이다.
```
