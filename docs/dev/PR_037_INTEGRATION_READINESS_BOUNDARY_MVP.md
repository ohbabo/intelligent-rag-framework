# PR 037 — Integration Readiness Boundary (PR37-PKG-DOCS)

## Summary

PR37-PKG-DOCS closes the **integration discoverability** gap that PR36-PKG §48 left open. It does NOT close the RAG operational structure.

Core locked statements (user-locked 2026-05-22):

```text
PR37 closes integration discoverability, not RAG operational structure.
PR38-RAG-BOUNDARY should be informed by a disposable adapter probe
before freezing §50.
```

Locked record paragraph (verbatim, included for future readers):

```text
PR37 did not define the RAG operational adapter contract.

It closed the integration discoverability gap by making the existing
ragcore Engine usage, persistence boundary, stability/evolvability
boundary, and documentation entry points visible from README.

However, Cerberus-to-ragcore operational structure is intentionally not
frozen in PR37.

The next step is not to immediately write §50 from speculation.
Before freezing the RAG Operational Boundary, a disposable adapter probe
should pass one realistic Cerberus finding into ragcore.Engine and reveal
the minimum adapter contract fields.
```

Three-차수 cycle:

```text
151차  docs(contract) §49  Integration Readiness Boundary + audit + D1~D8 proposal
152차  docs(readme)         Scope D-mid execution (D1+D4+D5+D6+D7+D8)
153차  docs(dev) (this)     PR record + ready + squash merge
```

> **PR37 makes Engine usage discoverable from README.**
> **PR37 does NOT define the RAG operational adapter contract — that is PR38-A probe + PR38-B §50.**

---

## Baseline

```text
base main:    41298f1
branch:       feat/integration-readiness-boundary
before tests: 1115 passing
public symbols: 48 (PR36-PKG locked)
Engine public methods: 40 (PR36-PKG locked)
snapshot schema_version: 2
```

Completed immediately before this PR:

```text
PR36-PKG §48 — engine method surface freeze
```

PR37 builds directly on PR36-PKG: §48 froze the method surface (necessary condition); §49 verifies that surrounding documentation makes the surface *discoverable* (sufficient condition for shallow integration check, NOT for deep Cerberus product integration).

---

## Commits in this PR

```text
151차  c1079c4  docs(contract): define integration readiness boundary (§49)
152차  3205b10  docs(readme): add integration quickstart and persistence boundary
PR38   59b2cd9  docs(dev): plan PR38 RAG operational boundary
153차  this commit — docs(dev) record + Draft → Ready + squash merge
```

The PR38 plan file (`docs/dev/PR_038_RAG_OPERATIONAL_BOUNDARY_PLAN.md`) was added to this PR's branch as a forward-reference for the next PR's scope.

---

### 151차 — docs(contract) §49

Commit `c1079c4` added §49 to `docs/contracts/05_DATA_CONTRACT_MVP.md` (+478 lines, 12 subsections):

```text
§49.1   Core statement (locked framing)
§49.2   Integration Readiness vs Method Surface Freeze (§48 ⊆ §49)
§49.3   151차 audit scope
§49.4   Current docs / README / examples inventory
§49.5   V-cerberus pre-integration checklist (10 items)
§49.6   Audit findings — gap analysis (8 gap / 1 partial / 1 documented)
§49.7   Gap candidates D1~D8 (proposal only)
§49.8   Scope selection framework (D-low / D-mid / D-full / D-only)
§49.9   Audit-only invariants
§49.10  Non-goals
§49.11  Future PR constraints + V-cerberus prerequisites
§49.12  Cycle for PR37-PKG-DOCS
```

Key audit findings:

```text
examples/ directory                              DOES NOT EXIST
README.md (pre-152차)                             88 lines, architecture only
"from ragcore import" in non-contract docs        0 occurrences

Insight (recorded at the time):
  Most gaps are NOT content gaps but DISCOVERABILITY gaps.
  The content exists in well-written contract subsections — it's just
  not findable by a new consumer browsing README.
```

V-cerberus pre-integration checklist gap analysis:

```text
documented (no gap):       1 item   (P6 decision — Engine.claim_report OOS)
partial discoverability:   1 item   (§48.5)
gap (discoverability):     8 items  (README usage, examples/, adapter docs,
                                     persistence docs, §43/§44/§48 cross-link,
                                     migration guide, storage responsibility)
```

---

### 152차 — docs(readme) Scope D-mid execution

Commit `3205b10` executed 6 of 8 candidates (Scope D-mid):

```text
Executed:
  D1  README integration quickstart section
  D4  README Project Status section
  D5  README persistence boundary example (consumer-owned storage)
  D6  §49 itself (from 151차)
  D7  Cross-links from §43 / §44 / §48 / §49 to README
  D8  README documentation map updated

Deferred (Scope D-full):
  D2  examples/ directory                           (defer to PR39+ if needed)
  D3  docs/usage/ directory (6 guides)              (defer to PR39+ if needed)
```

README.md changes (88 → 252 lines, +164):

```text
+ "Project Status" section
  - Version 0.1.0, ragcore import name
  - Method surface frozen (PR36-PKG §48)
  - Algorithm allowed to evolve (PR36-PKG §48.3)
  - Integration readiness audited in §49
  - "Freeze method surface, not judgment mathematics."
  - "Algorithm can evolve. Integration boundary must be complete."

+ "Quickstart" section
  - Minimal `from ragcore import Engine` example
  - 6-step usage script
  - Cross-references to §43 / §44

+ "Persistence Boundary" section
  - Engine returns dict; consumer chooses storage
  - JSON save/load example
  - Framework / Consumer responsibility separation
  - Cross-references to §39.4 / §42.6 / §44.8

+ "Stability & Evolvability" section
  - Stable forever list (8 items)
  - Allowed to evolve list (5 items)
  - Breaking change rule (§48.5) summary

+ Restructured "Documentation Map"
  - Project foundation / Consumer contracts / Consumer entry points /
    Per-PR records / Other
  - Explicit §43 / §44 / §48 / §49 entry points
```

Contract doc changes (12,864 → 12,872 lines, +8):

```text
+ "Quick entry point" cross-link at top of:
  §43.1 — points to README Quickstart
  §44.1 — points to README Quickstart
  §48.1 — points to README Stability & Evolvability
  §49.1 — points to README Stability & Evolvability + Persistence Boundary
```

Bidirectional discoverability achieved.

---

## §49 V-cerberus checklist gap status (post-152차)

```text
Before PR37:
  documented (no gap):       1 item   (P6 decision)
  partial discoverability:   1 item   (§48.5)
  gap (discoverability):     8 items
  total gap:                 9 items

After PR37 D-mid:
  documented (no gap):       1 item   (P6, preserved)
  documented in README:      6 items  (closed by D1+D4+D5+D8)
  closed (D7):               1 item   (§48.5 cross-link)
  remaining gap:             2 items  (D2 examples/, D3 docs/usage/ — deferred)
  total gap:                 2 items
```

V-cerberus [required] prerequisites (§49.11):

```text
[required] D1 OR D2  →  D1 closed ✓
[required] D5         →  closed ✓
[recommended] D3      →  deferred (V-cerberus may drive what gets documented)
[recommended] D4      →  closed ✓
[optional] D7, D8     →  closed ✓
```

All [required] gaps closed. **A shallow Engine package import check is now feasible from README alone.**

---

## What PR37 did

```text
- Added §49 Integration Readiness Boundary to the contract (151차)
- Audited current docs / README / examples against V-cerberus checklist
- Identified 8 D-candidates (D1~D8)
- Executed Scope D-mid (6 candidates: D1+D4+D5+D6+D7+D8)
- Closed all [required] V-cerberus prerequisites
- Made README discoverable for new consumers
- Created PR_038 forward-plan document
```

## What PR37 did NOT do

```text
- Did NOT define the RAG operational adapter contract
- Did NOT freeze CanonicalEvidenceAtom / RetrievalResult / EngineInput
- Did NOT lock Cerberus-to-ragcore mapping rules
- Did NOT write §50
- Did NOT add examples/ directory (D2 deferred)
- Did NOT add docs/usage/ directory (D3 deferred)
- Did NOT change framework source code
- Did NOT change tests
- Did NOT change method surface (PR36-PKG §48 frozensets preserved)
- Did NOT change algorithm
- Did NOT change snapshot schema
- Did NOT change report frozensets
- Did NOT make Cerberus integration decisions
- Did NOT reactivate P6 (Engine.claim_report — PR32-V §44.11 OOS preserved)
```

---

## Critical scope clarification: discoverability ≠ operational readiness

PR37 closes **integration discoverability**.

PR37 does NOT close **RAG operational structure**.

```text
"V-cerberus thin adapter can start" after PR37 means:
  ✓ Cerberus can begin a shallow integration check against the stable
    Engine package surface
  ✓ A new consumer can find `from ragcore import Engine` in README
  ✓ A new consumer can read about persistence responsibility

It does NOT mean:
  ✗ Cerberus should deeply encode current Engine internals
  ✗ Cerberus should commit to a specific evidence mapping
  ✗ Cerberus should bypass an adapter layer
  ✗ The RAG operational layer (corpus / vector DB / retrieval / embedding)
    is contracted
```

If Cerberus directly knows too much about Engine claim/evidence/gap internals before §50 is written, then a later update to corpus, vector DB, retrieval policy, embedding version, or evidence mapping will force Cerberus integration code to be rewritten.

---

## Next: PR38-A probe before PR38-B spec

PR38 is split (user-locked 2026-05-22):

```text
PR38-A — disposable Cerberus-to-ragcore adapter probe
  Purpose: pass one realistic Cerberus finding (e.g., SSH finding) into
           ragcore.Engine and observe what minimum adapter contract
           fields actually emerge.
  Size:    ~100-200 LOC, intentionally disposable
  Output:  reality-checked field requirements for §50
  Status:  spec-driven design (without probe) is REJECTED — premature
           abstraction risk

PR38-B — RAG Operational Boundary / Evidence Adapter Contract §50
  Purpose: freeze the contract that PR38-A revealed
  Input:   PR38-A probe findings, NOT speculation
  Cycle:   audit-first (using probe as the "existing code" to audit —
           the audit-first pattern that worked in PR33-M / PR34-O /
           PR35-O7 then applies properly)
```

Rationale (recorded for future readers):

```text
audit-first pattern succeeded in PR33-M / PR34-O / PR35-O7 because each
PR had EXISTING CODE to audit:

  PR33-M: 48 symbols + 40 methods + 12 group structure (existing)
  PR34-O: engine.py 1696 LOC with 28 KeyError patterns (existing)
  PR35-O7: from_snapshot 45 LOC with 4 inline comprehensions (existing)

PR38-RAG-BOUNDARY has no existing audit target unless PR38-A creates
one. A spec-only §50 written before any adapter exists will likely:
  - encode wrong fields
  - miss real-world coupling needs
  - require amendment within the first Cerberus integration cycle
  - re-create the premature-abstraction trap audit-first was meant to
    prevent

PR38-A solves this by making the probe code itself the audit target
for PR38-B.
```

PR38-A non-goals (locked 2026-05-22):

```text
- 정식 adapter 구조 만들기                 (probe is disposable)
- CanonicalEvidenceAtom 최종 설계 고정      (probe reveals, doesn't decide)
- DB/vectorstore/storage 붙이기              (no infrastructure)
- Cerberus 전체 pipeline 연결                (one finding only)
- §50 먼저 쓰기                              (probe → §50, not §50 → probe)
- snapshot schema 변경
- ragcore Engine surface 변경
- judgment mathematics 변경
```

PR38-A scope (locked 2026-05-22):

```text
- SSH finding 1건 정도를 임시 dict / dataclass 로 표현
- ragcore.Engine 생성
- add_claim
- add_evidence
- 필요하면 add_gap / register_contradiction 최소 사용
- compute_effective_confidence 호출
- to_snapshot 호출
- print 로 결과 확인
- 어떤 field 가 진짜 필요했는지 기록
```

PR38-A questions to be answered (locked 2026-05-22, 8 items):

```text
1. Cerberus finding 의 주어는 asset_id / service_id / endpoint 중 무엇인가?
2. Claim subject/predicate/object 구조가 실제 finding 에 맞는가?
3. raw_ref 는 파일 경로 / tool_run_id / log span / evidence hash 중 무엇이어야 하는가?
4. Evidence 는 tool output 단위인가, normalized signal 단위인가?
5. EngineInput 은 단일 claim bundle 인가, finding bundle 인가, asset bundle 인가?
6. adapter 가 confidence 를 계산해야 하는가, rule 이 계산해야 하는가?
7. snapshot 저장 책임은 ragcore 가 아니라 Cerberus storage layer 가 맞는가?
8. retrieval / vector DB 결과는 Engine 에 직접 들어가면 안 되고,
   adapter 에서 evidence atom 으로 변환되어야 하는가?
```

These 8 questions are the explicit output target of PR38-A. §50 in PR38-B is the freeze of what PR38-A discovers.

---

## Verification

```text
pytest -q                  1115 passing (unchanged from PR36-PKG)
ragcore.__all__            48 symbols (PR31-S baseline preserved)
Engine public methods       40 (PR33-M baseline preserved)
no-docstring methods         0 (PR33-M coverage preserved)
modifier helpers             6 with (claim_id: int) -> float (PR34-O)
serialize/restore symmetry   6 × 6 (PR35-O7)
snapshot schema_version       2 (PR21-L)
PR31-S frozenset              unchanged (PR36-PKG _LOCKED_PUBLIC_METHODS)
PR32-V *_KEYS                 unchanged
PR36-PKG _LOCKED_* frozensets unchanged
```

---

## Boundary preservation table

| Preserved boundary                                       | PR37 effect                       | Status      |
| -------------------------------------------------------- | --------------------------------- | ----------- |
| Sub-decision D (types / rule_output unchanged)           | docs only                          | preserved   |
| Sub-decision AF (HINT taxonomy framework-external)       | unchanged                          | preserved   |
| PR17 snapshot schema v2                                  | locked in README persistence       | reinforced  |
| PR21-L hint validation                                   | unchanged                          | preserved   |
| PR27-P §39 call boundary                                 | cross-link to README               | reinforced  |
| PR28-O §40 rule version pinning                          | unchanged                          | preserved   |
| PR29-R §41 observed_precision                            | unchanged                          | preserved   |
| PR30-P §42 read boundary                                 | unchanged                          | preserved   |
| PR31-S §43 usage recipe                                  | README cross-link added            | reinforced (discoverability) |
| PR31-S method surface freeze (48 symbols)                | unchanged                          | preserved   |
| PR32-V §44 report surface                                | README cross-link added            | reinforced (discoverability) |
| PR32-V Engine.claim_report absence                       | preserved + documented in §49 (P6) | preserved   |
| PR33-M §45 method surface audit                          | unchanged                          | preserved   |
| PR33-M docstring coverage (40/40)                        | unchanged                          | preserved   |
| PR34-O §46 internal optimization                          | unchanged                          | preserved   |
| PR34-O modifier signature consistency                    | unchanged                          | preserved   |
| PR35-O7 §47 snapshot restore refactor                    | unchanged                          | preserved   |
| PR35-O7 serialize/restore symmetry (6 × 6)                | unchanged                          | preserved   |
| PR36-PKG §48 method surface freeze                       | README "Stability & Evolvability"  | reinforced (discoverability) |
| §48.6 Cerberus consumer example script                   | mirrored in README Quickstart      | reinforced |
| Method surface freeze frozensets (3 locked sets)         | unchanged                          | preserved   |
| Integration discoverability                              | §49 + D-mid execution              | **newly locked** |
| RAG operational structure                                | NOT locked (intentional)           | **deferred** |

---

## Implementation footprint

Changed files (151 + 152 + 153 + PR38 plan):

```text
docs/contracts/05_DATA_CONTRACT_MVP.md                +478 + 8 (§49 + cross-links)
README.md                                              +164 (Project Status / Quickstart /
                                                              Persistence / Stability /
                                                              Documentation Map)
docs/dev/PR_037_INTEGRATION_READINESS_BOUNDARY_MVP.md  this record
docs/dev/PR_038_RAG_OPERATIONAL_BOUNDARY_PLAN.md       PR38 forward-plan
```

Unchanged:

```text
ragcore/engine.py
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
ragcore/condition.py
ragcore/rule_compile.py
ragcore/rule_gap.py
ragcore/rule_loader.py
ragcore/rule_runtime.py
pyproject.toml (unchanged in PR37 — already finalized in PR36-PKG 149차)
all test files
```

No snapshot schema change. No formula change. No public API change. No frozenset shift.

---

## Self-review

### What PR37 does well

```text
- Closes integration discoverability gap (8 → 2 remaining, both deferred)
- All V-cerberus [required] prerequisites met
- README is now a real entry point (was architecture-only)
- Bidirectional cross-links between contract and README
- Documents the scope distinction (discoverability ≠ operational)
- Explicitly defers spec-first §50 in favor of probe-first PR38-A
```

### What PR37 does NOT do (deliberately)

```text
- Does not write §50
- Does not design CanonicalEvidenceAtom / RetrievalResult / EngineInput
- Does not commit to a specific Cerberus finding format
- Does not pre-decide adapter responsibility boundaries
- Does not implement examples/
- Does not implement docs/usage/
```

### Why the deliberate non-closure is correct

```text
The risk recognized during PR37 progress:

  spec-first §50 written from speculation
    → wrong fields locked
    → first real Cerberus integration breaks the spec
    → §50 amendment PR needed (mini method-surface-migration)
    → audit-first benefit lost

The correction (user-locked 2026-05-22):

  PR38-A reality probe → PR38-B spec freeze
    → §50 is written FROM observed reality, not toward it
    → first real adapter informs the contract
    → audit-first pattern applies properly (probe code is audit target)
    → premature-abstraction trap avoided
```

---

## Final meaning

PR37 closes the integration discoverability layer.

```text
Layer A. Engine Core                       ✓ PR1~PR36
Layer B. Integration Discoverability       ✓ PR37 (this PR)
Layer C. RAG Operational Boundary           pending  PR38-A probe → PR38-B §50
Layer D. Cerberus Product Integration       pending  V-cerberus, post-PR38
```

The framework is now:

```text
- importable as `from ragcore import Engine` ✓
- documented for new consumers in README ✓
- explicitly bounded by Stability & Evolvability principle ✓
- linked bidirectionally between contract and README ✓
- ready for shallow integration probe (PR38-A) ✓
- NOT ready for deep Cerberus product integration (pending PR38-B) ✓
```

```text
PR27-P   §39  call boundary
PR30-P   §42  read boundary
PR31-S   §43  usage recipe
PR32-V   §44  report surface
PR33-M   §45  method surface audit
PR34-O   §46  internal optimization audit
PR35-O7  §47  snapshot restore refactor
PR36-PKG §48  method surface freeze (locking)
PR37     §49  integration readiness boundary (discoverability + V-cerberus prerequisites)
```

Locked closing sentences (user 2026-05-22):

```text
PR37 closes integration discoverability, not RAG operational structure.

PR38-RAG-BOUNDARY should be informed by a disposable adapter probe
before freezing §50.
```

---

## Next steps

```text
PR38-A   disposable Cerberus-to-ragcore adapter probe
         - one realistic Cerberus finding (SSH finding recommended)
         - Engine.add_claim + add_evidence (+ minimal gap / contradiction)
         - compute_effective_confidence + to_snapshot
         - print results
         - answer 8 questions from PR_038 plan
         - intentionally disposable code (will not be kept after PR38-B)

PR38-B   RAG Operational Boundary / Evidence Adapter Contract §50
         - audit PR38-A probe code
         - freeze CanonicalEvidenceAtom / RetrievalResult / EngineInput
           from reality-checked field requirements
         - lock adapter responsibility boundaries
         - lock vector DB / corpus / embedding independence
         - lock storage responsibility

V-cerberus  thin adapter in cerberus_client repo
            - follows PR38-B §50 contract
            - cerberus body only calls adapter API, not raw Engine

PR39+      remaining deferred candidates:
           - D2 examples/ directory (if needed)
           - D3 docs/usage/ extracted guides (if needed)
           - engine.py internal module extraction (former PR38-O)
           - P4 / P5 / P6 surface migration (if justified)
           - R-fpr / G / J / Q / S-extension judgment policy updates
```
