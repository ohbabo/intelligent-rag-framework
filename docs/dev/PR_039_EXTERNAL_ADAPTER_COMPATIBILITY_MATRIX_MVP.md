# PR39 — External Adapter Compatibility Matrix MVP

## Scope limitation (locked, user 2026-05-22)

```text
PR39 does not complete the adapter layer.

PR39 only verifies that external adapter outputs can be translated
into the frozen Engine public method surface without changing
ragcore source.
```

한국어:

```text
PR39 는 adapter layer 를 완성하지 않는다.
PR39 는 외부 Adapter 출력이 ragcore source 변경 없이
Engine public method surface 로 번역 가능한지만 검증한다.
```

PR39 closes a single, narrow question:

```text
"Does the current ragcore.Engine public API need to change to host
the future external adapters anticipated in the initial philosophy?"

Answer: NO. Engine change is not needed. Adapter policy is.
```

## 1. What PR39 confirmed

### 1.1 Seven adapter candidates — all compatible without Engine change

```text
1. Vector DB Adapter              compatible via adapter,     Engine change: no
2. Graph DB Adapter               compatible via adapter,     Engine change: no
3. LLM Adapter                    compatible (strict policy), Engine change: no
4. SQL / Postgres Adapter         compatible via adapter,     Engine change: no
5. File-based Knowledge Store     compatible via adapter,     Engine change: no
6. API Signal Adapter             compatible via adapter,     Engine change: no
7. Manual Analyst Note Adapter    compatible via adapter,     Engine change: no
```

### 1.2 Seven universal adapter patterns

```text
1. external_id → raw_ref_id resolution
2. external score → engine input translation
3. consumer-side integer registries
4. evidence granularity decision
5. evidence type classification
6. lifecycle responsibility (ragcore-owned)
7. snapshot is consumer-owned
```

### 1.3 Twelve anti-patterns locked (MUST NOT enter framework)

```text
- vector similarity = engine confidence
- LLM natural language answer = confirmed Claim
- graph path = confirmed Relation
- raw tool output = Evidence
- raw chunk text = Evidence
- scanner severity = evidence strength
- package-specific schema = ragcore type
- API client / network code in ragcore
- DB driver code in ragcore
- file I/O in ragcore
- embedding model loading in ragcore
- LLM API key / authentication in ragcore
```

### 1.4 Compatibility gap

```text
NONE FOUND.

Closest friction: raw_ref_id int vs external string id.
This is adapter responsibility, NOT ragcore deficiency.
Five resolution strategies (registry / hash / timestamp / external map /
composite encoding) all consumer-side.
```

## 2. What PR39 did NOT do (deliberately)

PR39 deliberately did NOT close the following — they remain open territory:

```text
- detailed adapter policy design per knowledge layer
- specific score → strength translation functions
- specific raw_ref_id resolver designs
- end-to-end reference flow for any single adapter
- consumer implementation of any adapter
- vector DB / graph DB / LLM / SQL / file / API / manual implementation
- choice of vector DB vendor
- choice of embedding model
- choice of chunking strategy
- choice of LLM provider
- choice of storage backend
- domain vocabulary
- security / medical / legal / financial / research vocabulary
```

If any of these had been included, PR39 would have grown beyond a compatibility audit into adapter design — which is explicitly out of scope.

## 3. Why PR39 stayed audit-only

```text
audit-first pattern (PR33-M / PR34-O / PR35-O7 / PR38-B precedent):
  - existing code/contract is the audit target
  - findings inform the next PR
  - no premature design

PR39 audit target:
  - the 10 layered §-boundaries (§39 ~ §50)
  - PR38-A probe code (examples/probe/external_consumer_probe.py)
  - initial philosophy locks (docs/01_CORE_PHILOSOPHY.md +
    docs/03_RUNTIME_LOOP.md)

PR39 finding:
  - 7 adapter candidates can plug into the frozen Engine method surface
    without ragcore source change
  - 7 universal patterns explain HOW to plug
  - 12 anti-patterns explain WHAT NOT to do
  - 0 Engine API changes required

PR39 did not extend further into:
  - per-adapter detailed policy (each would be its own design PR)
  - reference implementation (would violate "no Cerberus-specific in
    ragcore" rule)
  - domain vocabulary (consumer-side)
```

This is the audit boundary. Beyond it lies adapter design territory that PR39 explicitly leaves to future, separate documentation work.

## 4. Future documentation candidate areas (NOT PR-numbered)

The following areas remain open after PR39. Each is a candidate documentation area, NOT a confirmed PR. PR numbers and scope locks happen at user decision time, not in this PR.

### Candidate A — Adapter Policy Guide

```text
Possible content:
  - confidence / strength translation policy patterns
  - raw_ref_id resolver pattern catalog
  - integer registry naming conventions
  - granularity decision rules of thumb

Status: candidate area, not scoped
```

### Candidate B — Retrieval Output → Evidence Guide

```text
Possible content:
  - similarity score → strength translation patterns
  - chunk / graph path / LLM answer → normalized evidence
  - score-floor / score-ceiling policy examples

Status: candidate area, not scoped
```

### Candidate C — Engine Method Call Playbook

```text
Possible content:
  - when to call add_claim vs add_evidence vs add_gap vs add_relation
  - lifecycle transition trigger conditions
  - common multi-step call sequences

Status: candidate area, not scoped
```

### Candidate D — Anti-patterns Guide

```text
Possible content:
  - expanded forms of PR39 §7 (12 anti-patterns)
  - real-world examples of each forbidden pattern
  - how to detect / refactor anti-patterns

Status: candidate area, not scoped
```

### Candidate E — Reference Flow

```text
Possible content:
  - domain-neutral end-to-end example
  - one observation → one claim → one decision lifecycle
  - documentation-only walkthrough (no Cerberus-specific code)

Status: candidate area, not scoped
```

These five remain CANDIDATE areas. None are auto-scheduled. None are PR-numbered. None proposes a next-PR entry.

The decision of whether and when to write each belongs to the user, not to PR39.

## 5. Two-차수 cycle

```text
159차  da4de6d  docs(architecture): add external adapter compatibility matrix
       commit added docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
       (+418 lines)
       
160차  this commit — docs(dev) PR_039 record + ready + squash merge
       includes scope limitation lock (this record's §1 limitation)
```

## 6. Pattern position

```text
docs/01_CORE_PHILOSOPHY.md           원칙 — Core 는 RAG / LLM / Graph DB 에
                                            직접 연결하지 않는다
docs/03_RUNTIME_LOOP.md               순서 — RAG / LLM / Graph DB 는 외부
                                            Adapter 로 분리
docs/contracts/05_DATA_CONTRACT_MVP.md §50  계약 — External Knowledge Adapter
                                            Boundary
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
                                       audit — 위 원칙/순서/계약이 7 adapter
                                            후보에 적용 가능한지 검증 (PR39)
```

PR39 verifies the philosophy → runtime → contract chain holds against concrete adapter patterns. Verification only — no implementation.

## 7. Implementation footprint

Changed files (159 + 160):

```text
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md  +418 lines (159차)
docs/dev/PR_039_EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX_MVP.md  this record (160차)
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
examples/probe/external_consumer_probe.py
all test files
```

No source change. No test change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change.

## 8. Verification

```text
pytest -q                          1115 passing (unchanged)
ragcore.__all__                    48 symbols (PR31-S baseline)
Engine public methods               40 (PR33-M docstring 40/40)
modifier helpers                    6 with (claim_id: int) -> float (PR34-O)
serialize/restore symmetry          6 × 6 (PR35-O7)
snapshot schema_version              2 (PR21-L)
PR36-PKG _LOCKED_* frozensets        unchanged
ragcore source change since PR36-PKG   0 lines
ragcore source cerberus mentions      0 (generic identity preserved)
```

All invariants preserved.

## 9. Non-goals (preserved across PR39)

```text
- did NOT implement any adapter
- did NOT import external packages
- did NOT choose vector DB / graph DB / LLM / SQL / embedding / chunking
- did NOT propose Engine API additions
- did NOT define CanonicalEvidenceAtom / RetrievalResult / EngineInput
  as ragcore types
- did NOT add to ragcore.__all__
- did NOT modify engine.py / types.py / __init__.py / rule_output.py
- did NOT add adapter framework tests
- did NOT introduce production-readiness claim
- did NOT introduce Cerberus-specific identity into ragcore
- did NOT propose PR40 or later
- did NOT trigger V-cerberus
- did NOT close future candidate areas A~E
```

## 10. Final closing meaning

```text
PR39 closed the compatibility audit question.

It did not close adapter design.
It did not close RAG layer design.
It did not close any specific adapter's implementation policy.

Five candidate documentation areas (A ~ E) remain open as candidate
areas — not as scheduled PRs.

Framework-side compatibility for external adapters is confirmed at the
Engine boundary. Implementation belongs to adapters (consumer-side),
not to ragcore source.
```

Locked closing sentences:

```text
PR39 하나로 되는 건 "Engine boundary compatibility 확인" 까지고,
RAG / Adapter 문서층 전체는 PR39 이후에도 계속 나눠서 가야 한다.

External adapter compatibility is confirmed at the Engine boundary.
Engine should not depend on external packages.
External packages are adapter-owned.
The compatibility question is whether adapter outputs can be translated
into Engine public method calls.
Most compatibility work belongs to adapter policy, not ragcore source.
```

The framework now holds at:

```text
- 10 layered §-boundaries (§39 ~ §50)
- 1 architecture audit (this PR's matrix)
- 1115 tests passing
- 0 ragcore source change since PR36-PKG
- 0 Cerberus-specific concept in ragcore
- NEXT AUTOMATIC PR: NONE

The framework waits. User decides next direction.
```
