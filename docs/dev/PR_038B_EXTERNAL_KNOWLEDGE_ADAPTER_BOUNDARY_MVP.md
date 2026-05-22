# PR38-B — External Knowledge Adapter Boundary MVP

## Lock sentences (user 2026-05-22)

```text
PR38-B defines an External Knowledge Adapter Boundary,
not a RAG implementation.

ragcore remains RAG-agnostic and domain-neutral.

External consumers own retrieval, storage, domain vocabulary,
registries, raw reference resolution, and confidence translation policy.

Engine confidence is not vector similarity, scanner severity,
or domain score.

Cerberus is the first concrete consumer case,
not the framework contract.
```

## 1. Purpose

PR38-B adds §50 to `docs/contracts/05_DATA_CONTRACT_MVP.md` to freeze the boundary between external knowledge systems and ragcore Engine method calls.

§50 is a contract document. It does not implement a RAG architecture. It does not introduce new ragcore types or methods.

## 2. Two-차수 cycle (157차 skipped)

```text
156차  docs(contract): define external knowledge adapter boundary (§50)
       commit 8419c51 (+595 lines, 17 subsections)

157차  SKIPPED (확정)
       reason recorded below

158차  this commit — docs(dev) record + ready + squash merge
```

## 3. 157차 skip reason

```text
§50 invariants 1~6:
  already tested by tests/test_engine_method_surface_freeze.py
  (PR36-PKG 148차 — 48 symbols / 40 methods / 18 snapshot keys /
   modifier signatures / serialize-restore symmetry / import side-effect)

§50 invariants 7~12:
  consumer-side obligations
  (adapter responsibilities — translation policy / registry / resolver /
   storage / no-bypass-of-public-API / consumer-owned domain vocabulary)

Risk of adding framework-side test for invariants 7~12:
  any test that exercises adapter behavior requires a fake "Cerberus"
  or fake "vector DB" inside the framework repo. Both pull domain or
  retrieval concepts INTO ragcore — exactly what §50.3 forbids.

Decision:
  Framework-side tests for consumer obligations are NOT added in PR38-B.
  Consumer-side integration tests (e.g., V-cerberus PR in
  cerberus_client repo) validate invariants 7~12.

  PR38-B is docs-only — single §50 contract addition, no source change,
  no test change.
```

## 4. §50 key decisions (frozen by 156차)

### Framework neutrality

```text
- ragcore does not require vector DB, embedding, retrieval pipeline,
  domain vocabulary, scanner output format, or storage backend
- External consumers may use vector / graph / SQL / static / hybrid /
  manual / API / no-retrieval — all equivalent from ragcore's perspective
- The "Intelligent RAG Framework" name means RAG-friendly, not RAG-implementing
```

### Adapter responsibility (consumer-side)

```text
Adapter MUST:
  1. maintain consumer-side integer registries
     (entity_type / claim_type / evidence_type / observation_type /
      source_type / reason_code)
  2. maintain raw_ref_id resolution strategy
     (external string identifier → ragcore int)
  3. translate external knowledge results into Engine inputs
     (retrieval result → Evidence; similarity → strength via policy;
      severity/score → base_confidence via policy)
  4. decide granularity per finding type
     (subject granularity / evidence granularity)
  5. own consumer-side storage of snapshot dicts
  6. own domain vocabulary
  7. call only ragcore public methods (the 40 frozen methods)

Adapter MUST NOT:
  - import ragcore private helpers
  - mutate ragcore internal state directly
  - pass external scores as Engine confidence
  - pass raw retrieval results as Evidence without translation
  - store ragcore snapshot dicts inside ragcore
  - introduce domain vocabulary into ragcore types
```

### Single non-negotiable retrieval rule (§50.10)

```text
similarity score (any kind: vector / BM25 / fuzzy / lexical / hybrid /
                   graph / SQL match score)
is NOT engine confidence.

Adapter MUST translate retrieval output via evidence-atom step before
passing into Engine. Identity mapping is forbidden.
```

### Conceptual labels — NOT ragcore types

```text
§50 mentions:
  - CanonicalEvidenceAtom
  - RetrievalResult
  - EngineInput

These are CONCEPTUAL LABELS for adapter-side data shapes used by the
discussion in §50. They are:
  - never imported from ragcore
  - never added to ragcore.__all__
  - never frozen as dataclass fields here
  - consumer-side concerns

If a future adapter implements them, it does so on the CONSUMER side
(e.g., cerberus_client adapter module). ragcore stays clean.
```

### Cerberus is sample, not contract (§50.14)

```text
What §50 inherits from Cerberus pressure (via PR38-A probe):
  - subject granularity question
  - claim_type encoding question
  - raw_ref string-to-int friction
  - banner/tool output evidence granularity question
  - snapshot consumer-side storage requirement
  - retrieval translation requirement (if Cerberus uses RAG)

What §50 does NOT inherit:
  - security domain vocabulary
  - CVE / vulnerability concepts
  - scanner-specific output formats
  - nmap / nuclei / NSE pipeline stages
  - Cerberus severity model
  - Cerberus integer registry values
  - Cerberus storage choices
```

## 5. Why PR38-A probe was necessary

§50 could not be written as pure speculation. The audit-first pattern (PR33-M / PR34-O / PR35-O7 precedent) requires existing code to audit.

PR38-A produced the audit target:

```text
examples/probe/external_consumer_probe.py
  - 1 sample external observation (Cerberus SSH finding from nmap)
  - 6 ragcore.Engine public-API calls
  - 8 generic reality-question answers
  - §50 implication summary (domain-neutral)
  - 479 lines, disposable
```

PR38-B (this PR) audited PR38-A probe and derived §50 from observed pressure, not from spec-first speculation.

If §50 had been written before PR38-A:

```text
- CanonicalEvidenceAtom fields would have been guessed
- raw_ref string-to-int friction would have been missed
- retrieval translation rule would have been ambiguous
- §50 would have required amendment within first integration cycle
```

The audit-first pattern that protected PR33-M / PR34-O / PR35-O7 from premature abstraction is preserved through the PR38-A → PR38-B sequence.

## 6. Framework-side boundary completion

After PR38-B merges, the framework-side boundary stack is complete:

```text
PR27-P   §39  call boundary           how to call the Engine
PR30-P   §42  read boundary            how to read Engine outputs
PR31-S   §43  usage recipe             what order to call methods in
PR32-V   §44  report surface           what shape the result should take
PR33-M   §45  method surface audit     surface domain cleanup
PR34-O   §46  internal opt audit       internal domain refactor
PR35-O7  §47  snapshot restore         restore symmetry
PR36-PKG §48  method surface freeze    public API stability lock
PR37     §49  integration readiness    discoverability gap closure
PR38-A   ---  external consumer probe   disposable audit target
PR38-B   §50  external knowledge       adapter boundary contract
              adapter boundary         (this PR)
```

10 layered boundaries. 8 audit/spec PRs (§39 ~ §49) and 1 probe-based contract (§50).

## 7. Cerberus engine frame — completion criteria

User-locked criteria (2026-05-22):

```text
1. Cerberus does not know ragcore internals
2. Cerberus calls only public methods
3. Cerberus finding is translated by adapter into Claim/Evidence/Gap/Relation
4. RAG / vector DB / corpus / storage are Cerberus-owned
5. ragcore provides judgment state + snapshot only
6. mathematics / algorithm replaceable later
7. Engine method surface remains frozen
```

Framework-side enforcement after PR38-B:

```text
1.  enforced by §50.13 (only public methods)
2.  enforced by §50.13 (40 frozen methods)
3.  enforced by §50.5 ~ §50.10 (adapter responsibility + translation)
4.  enforced by §50.4 + §50.11 (consumer-owned sources + storage)
5.  enforced by §50.13 + PR36-PKG §48.9 (no side effects, snapshot only)
6.  already enforced by PR36-PKG §48.3 + §48.10 (algorithm evolvable)
7.  already enforced by PR36-PKG _LOCKED_PUBLIC_METHODS
```

All 7 criteria addressable from framework side. Consumer-side validation happens when V-cerberus (or any future consumer adapter) actually exercises §50.

## 8. V-cerberus and other consumer-side work

V-cerberus is NOT an automatic next step. It is a consumer-side option.

```text
V-cerberus location:
  cerberus_client repo (DIFFERENT repo from this one)

V-cerberus scope:
  Cerberus finding → consumer-side adapter → ragcore public API
  framework repo unchanged

V-cerberus constraints (per §50):
  - no ragcore source change
  - no Engine method addition
  - no security-specific type in ragcore
  - no vector DB structure in ragcore
  - consumer-side registry / resolver / storage / vocabulary
  - similarity score → strength via adapter policy
  - 40 public method surface only
```

PR38-B does NOT trigger V-cerberus. PR38-B does NOT propose V-cerberus as the next framework PR.

After PR38-B merges, the framework has a clean baseline. The next decision is the user's:

```text
Option A — framework repo maintenance
  No new structure. No new spec. Baseline freeze.

Option B — V-cerberus consumer-side work
  Different repo (cerberus_client). Framework unchanged.
```

These two options are mutually exclusive in any single iteration.

## 9. Verification

```text
pytest -q                          1115 passing (unchanged)
ragcore.__all__                    48 symbols (PR31-S baseline)
Engine public methods               40 (PR33-M docstring 40/40)
modifier helpers                    6 with (self, claim_id: int) -> float (PR34-O)
serialize/restore symmetry          6 × 6 (PR35-O7)
snapshot schema_version              2 (PR21-L)
report key frozensets                6 (PR32-V)
PR36-PKG _LOCKED_PUBLIC_METHODS     unchanged
PR36-PKG _LOCKED_MODIFIER_HELPERS    unchanged
PR36-PKG _LOCKED_SNAPSHOT_TOP_LEVEL_KEYS  unchanged
ragcore source change since PR36-PKG     0 lines
ragcore source cerberus mentions          0 (generic identity preserved)
```

All invariants from PR31-S / PR32-V / PR33-M / PR34-O / PR35-O7 / PR36-PKG / PR37 / PR38-A preserved.

## 10. Implementation footprint

Changed files (156 + 158):

```text
docs/contracts/05_DATA_CONTRACT_MVP.md  +595 lines (§50)
docs/dev/PR_038B_EXTERNAL_KNOWLEDGE_ADAPTER_BOUNDARY_MVP.md  this record
```

Unchanged:

```text
ragcore/engine.py
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
pyproject.toml
README.md
examples/probe/external_consumer_probe.py  (PR38-A)
all test files
all other docs/contracts/
```

No source change. No test change. No snapshot schema change. No method surface change. No frozenset shift.

## 11. Non-goals (preserved across PR38-B)

```text
- did NOT extend §50 further
- did NOT propose PR39
- did NOT auto-enter V-cerberus
- did NOT define CanonicalEvidenceAtom as a dataclass
- did NOT implement RetrievalResult / EngineInput
- did NOT add to ragcore.__all__
- did NOT modify engine.py / types.py / __init__.py
- did NOT add adapter framework test
- did NOT introduce production-readiness claim
- did NOT introduce Cerberus-specific identity into ragcore
```

## 12. Final closing meaning

```text
Framework-side External Knowledge Adapter Boundary is complete.

Consumer-side application remains a separate decision.
```

PR38-B ends the framework-side boundary stack for the "Cerberus engine frame" question (user 2026-05-22). All 7 completion criteria are addressable from framework contracts:

```text
1. Cerberus does not know ragcore internals       §50.13
2. Cerberus calls only public methods             §50.13
3. Cerberus finding translated by adapter         §50.5 ~ §50.10
4. RAG / vector DB / corpus / storage Cerberus-owned   §50.4 + §50.11
5. ragcore provides judgment state + snapshot only    §50.13 + §48.9
6. mathematics / algorithm replaceable later          §48.3 + §48.10
7. Engine method surface frozen                       _LOCKED_*
```

The framework now waits. No automatic next-PR proposal. The next decision is the user's.

Locked closing sentences (recorded for future readers):

```text
지금은 PR38-B 를 닫고, 지능형 RAG 프레임워크의 범용 boundary baseline 을
고정하는 단계다.

Framework-side External Knowledge Adapter Boundary is complete.
Consumer-side application remains a separate decision.
```
