# PR40 — Adapter Policy Guide MVP

## Scope limitation (locked, user 2026-05-22)

```text
PR40 does not implement adapter policies.
PR40 defines the policy decision surface that every external adapter
must own.

PR40 does not define concrete formulas.
PR40 does not implement vector DB, graph DB, LLM, SQL, file, API,
or manual-note adapters.
PR40 does not change ragcore source.
```

한국어:

```text
PR40 은 adapter policy 를 구현하지 않는다.
PR40 은 모든 Adapter 가 반드시 소유해야 할 정책 결정면만 문서로 닫는다.
```

PR40 records the questions every adapter must answer. It does not pick the answers — those remain consumer-side decisions.

## 1. 10 policy areas (documented in `docs/guides/ADAPTER_POLICY_GUIDE.md`)

```text
3.1   Subject granularity policy
3.2   Evidence granularity policy
3.3   raw_ref_id resolver policy
3.4   Consumer-side integer registry policy
3.5   Confidence translation policy
3.6   Evidence strength policy
3.7   Claim creation policy
3.8   Gap policy
3.9   Relation policy
3.10  Snapshot ownership policy
```

Each policy area uses uniform structure:

```text
Question        — the decision the adapter must answer
Adapter owns    — what falls on consumer/adapter side
Engine receives — the ragcore method calls that result
Must not        — anti-patterns specific to this area
Notes           — guidance / edge cases
```

## 2. §4 policy summary table essence

```text
1. Subject granularity:        unit choice — adapter decides per claim_type
2. Evidence granularity:       unit choice — recommended "one normalized signal"
3. raw_ref_id resolver:        string → int strategy — adapter consistent across runs
4. Consumer registry:           int → semantic mapping — adapter publishes its own
5. Confidence translation:      external → base_confidence — never identity-pipe
6. Evidence strength:           external → strength — never identity-pipe
7. Claim creation:              when add_claim vs add_evidence to existing
8. Gap:                          when add_gap, when resolve_gaps_for_evidence
9. Relation:                    when add_relation vs leave implicit in evidence
10. Snapshot ownership:        adapter persists; Engine never writes to disk
```

## 3. 5-layer alignment (now complete)

```text
1. Philosophy   docs/01_CORE_PHILOSOPHY.md
                Core 는 RAG / LLM / Graph DB 에 직접 연결하지 않는다.

2. Runtime      docs/03_RUNTIME_LOOP.md
                RAG / LLM / Graph DB 는 이후 외부 Adapter 로 붙인다.

3. Contract     docs/contracts/05_DATA_CONTRACT_MVP.md §50
                External Knowledge Adapter Boundary

4. Audit        docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
                7 adapter 후보 호환성 검증 (PR39)

5. Guide        docs/guides/ADAPTER_POLICY_GUIDE.md
                adapter policy decision surface (PR40 — this)
```

Five layers explain WHY → WHERE → WHAT → CAN-IT-HOST → WHICH-DECISIONS-BELONG-TO-ADAPTER.

The 5-layer alignment is now complete. None of the layers is a future commitment; all are present in the repository.

## 4. User-emphasized locks (preserved in guide)

```text
- external score is not engine confidence
- similarity / severity / LLM confidence / API score must be translated
- raw_ref_id is Engine int, external IDs are consumer-owned
- registry values are consumer-owned integers
- ragcore owns lifecycle + effective_confidence after inputs registered
```

The single non-negotiable rule across all 10 policy areas:

```text
External scores are not Engine confidence until adapter policy
converts them.
```

This holds for vector similarity, BM25 score, graph path score, LLM self-reported confidence, scanner severity, API confidence — any external "confidence-like" signal.

## 5. Engine responsibilities recap

ragcore.Engine OWNS:

```text
- 7-modifier composition (status / freshness / gap / count / rule_stats /
                          evidence_type — formula in PR36-PKG §48.7)
- lifecycle transitions (CANDIDATE / CONFIRMED / DISPUTED / REFUTED)
- snapshot serialization / migration framework
- effective_confidence computation
- claim lifecycle history (PR10-B §23 audit trail)
- contradiction state tracking (active / resolved)
- rule firing trace (when rules are registered)
- public method surface (PR36-PKG _LOCKED_PUBLIC_METHODS — 40 frozen)
- report shape (PR32-V — 6 frozen key sets)
```

ragcore.Engine does NOT OWN:

```text
- adapter policies (PR40 — this guide)
- domain vocabulary (security / medical / legal / etc.)
- storage choices (file / SQLite / Postgres / S3 / etc.)
- retrieval architecture (vector / graph / SQL / static / etc.)
- network / IO / LLM calls
- external integer semantics (registries are consumer-side)
- raw external IDs (only the int raw_ref_id)
```

This split is the foundation of every PR from PR27-P §39 onward. PR40 codifies the "what the adapter owns" side without breaking the boundary.

## 6. PR40 cycle

```text
161차  docs(guides) — Adapter Policy Guide (+564 lines)         d654e2a
162차  docs(dev) — PR40 record + ready + squash merge          this commit
```

Two-차수 cycle. No new tests. No source change. No new public API.

## 7. Pattern position recap

```text
PR39:   compatibility audit — feasibility verified
PR40:   adapter policy guide — decision surface enumerated (this PR)

Both:
  documentation-only
  ragcore source unchanged
  framework method surface frozen
  candidate areas B / C / D / E remain unscheduled
```

## 8. What this PR did NOT do (preserved)

PR40 deliberately did NOT:

```text
- provide concrete translation formulas for any policy
- pick specific integer assignments
- pick specific storage backends
- choose between vector DB / graph DB / LLM / SQL / file / API / manual
- implement any adapter class
- write Cerberus-specific code
- introduce CanonicalEvidenceAtom / RetrievalResult / EngineInput as
  ragcore types
- add to ragcore.__all__
- modify engine.py / types.py / __init__.py / rule_output.py
- introduce tests for adapter behavior
- propose PR41 or later
- trigger V-cerberus
- auto-select candidate area B / C / D / E
```

## 9. Verification

```text
pytest -q                              1115 passing (unchanged)
ragcore.__all__                         48 symbols (PR31-S baseline)
Engine public methods                    40 (PR33-M docstring 40/40)
modifier helpers                          6 with (claim_id: int) -> float (PR34-O)
serialize/restore symmetry              6 × 6 (PR35-O7)
snapshot schema_version                   2 (PR21-L)
PR36-PKG _LOCKED_* frozensets            unchanged
ragcore source change since PR36-PKG     0 lines
ragcore source cerberus mentions          0 (generic identity preserved)
```

All invariants preserved.

## 10. Implementation footprint

Changed files (161 + 162):

```text
docs/guides/ADAPTER_POLICY_GUIDE.md             +564 lines (161차)
docs/dev/PR_040_ADAPTER_POLICY_GUIDE_MVP.md     this record (162차)
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
examples/probe/external_consumer_probe.py
all test files
all other docs/
```

No source change. No test change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change.

## 11. Followup candidate areas (still NOT PR-numbered)

```text
Candidate B — Retrieval Output → Evidence Guide
Candidate C — Engine Method Call Playbook
Candidate D — Anti-patterns Guide
Candidate E — Reference Flow
```

After PR40 merges, none of these are scheduled. PR40 does NOT auto-propose any of them. User decides next direction.

## 12. Framework state (post-PR40)

```text
ragcore baseline:
  main: e2635a8 (pre-merge; new hash after squash merge)
  1115 tests passing
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  1 architecture audit (compatibility matrix)
  1 adapter policy guide (this PR)
  1 disposable probe (PR38-A)
  
5-layer adapter documentation alignment:
  philosophy + runtime + contract + audit + guide  ✓ all present
  
ragcore source change since PR36-PKG:  0 lines
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 13. Final closing meaning

```text
PR40 records the questions.
PR40 does not answer them.

The answers are domain-specific, consumer-side, adapter-owned.

The framework now waits.
```

Locked closing sentences:

```text
PR40 은 adapter policy 를 구현하지 않고,
adapter 가 반드시 소유해야 할 정책 결정면만 문서로 닫는다.

Adapter policy is consumer-owned.
ragcore does not own domain vocabulary, external IDs, retrieval scores,
storage backends, or confidence translation rules.
The adapter must translate external signals into Engine method calls.
External scores are not Engine confidence until adapter policy converts them.
PR40 defines the policy decision surface, not the policy formulas.
```

The framework has documented every layer of the adapter conversation from philosophy down to per-decision policy questions. Implementation belongs to the consumer side.

No automatic next-PR proposal. User decides direction.
