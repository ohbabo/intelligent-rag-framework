# PR68-P04 — Evidence / Confidence / Source / Freshness Semantics Alignment

Development record for the §53 terminology alignment landed by
PR68-P04 (branch `docs/evidence-semantics-alignment`).

```
base:            main db5a405 (PR67-P03: Snapshot Restore
                                Integrity Enforcement)
branch:          docs/evidence-semantics-alignment
226차 commit:    a934be6   docs (§53 + 2 architecture clarifications)
227차 commit:    (this record, docs/dev)
type:            framework-level documentation alignment,
                  doc-only (no runtime change, no test, no
                  Python file modified)
```

This record captures the actual runtime meaning of each of the
five terms (cross-referenced against the live code), the §53
sub-sections that lock those meanings, the repository-wide
contradiction scan with classifications (corrected / historical
/ no contradiction / deferred), the structural invariants, and
the closing position of PR68-P04.

---

## §1 Purpose

Five existing terms in the codebase carry meanings that are
easy to misread:

```
1. Evidence            — risks conflating raw external item,
                          consumer-side interpreted item, and
                          ragcore.Evidence record
2. evidences_for_claim — name suggests "evidence that supports
                          claim_id", but the return is polarity-
                          neutral
3. effective_confidence — looks like a probability, but is a
                          policy-composed score
4. Observation.source_type / PR59 SourceType
                        — superficially related but distinct
                          concepts
5. freshness           — looks like a wall-clock recency signal,
                          but is in fact the evidence ingestion
                          order (evidence.id)
```

PR68-P04 locks the **existing** meaning of each in
`docs/contracts/05_DATA_CONTRACT_MVP.md` §53 and adds minimal
in-place clarifications to two architecture documents that
directly mapped `evidences_for_claim` to "supporting evidence".

PR68-P04 introduces no new dataclass, enum, public symbol,
exception class, validator, migration, or dependency. The
five terms keep their current code-level behavior.

---

## §2 Baseline

```
base:                       main db5a405
                              (PR67-P03: Snapshot Restore
                               Integrity Enforcement)
baseline tests:             1364 passing
predecessor stack:          PR49 – PR67-P03
Engine public methods:      40
Engine private methods:     18
ragcore.__all__:            48
snapshot schema_version:    2
snapshot top-level keys:    18
```

226차 added `§53. Evidence, Confidence, Source, and Freshness
Terminology` (`+465` lines) to `docs/contracts/
05_DATA_CONTRACT_MVP.md` and made two in-place clarifications
in `docs/architecture/`. 227차 adds this record. No `ragcore/`
file is touched. No test is touched.

---

## §3 Files Changed

```
docs/contracts/05_DATA_CONTRACT_MVP.md                  +465 lines    (226차)
docs/architecture/ENGINE_READ_SURFACE_AUDIT.md           +4 / -3      (226차)
docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md     +1 / -1      (226차)
docs/dev/PR_068_EVIDENCE_CONFIDENCE_SOURCE_FRESHNESS_ALIGNMENT.md
                                                        this record   (227차)

ragcore source delta:         0 bytes
tests added:                  0
Python files changed:         0
framework public symbols:     0 added
new exception classes:        0
new dependencies:             0
```

---

## §4 Investigated Code and Documents

### §4.1 Evidence layers — confirmed against runtime

```
ragcore/types.py        Evidence dataclass shape
                          (id, claim_id, raw_ref_id, type,
                           strength). No polarity field.
ragcore/engine.py       add_evidence(claim_id, raw_ref_id,
                          evidence_type, strength) - the live
                          promotion path for a NEW Layer-3
                          Evidence from consumer input. NOT the
                          only path into Engine._evidences:
                          from_snapshot RESTORES already-
                          serialized Layer-3 state (not a
                          Layer-1/2 promotion). [post-audit]
docs/architecture/
  EXTERNAL_ADAPTER_TRANSLATION_BOUNDARY_SPEC.md
                        PR63 "external item" / "interpreted
                          item" stages — Layer 1 / Layer 2
                          provenance.
docs/architecture/
  ROLE_ASSIGNMENT_POLICY_SPEC.md
                        PR60 role assignment — consumer-side
                          interpretation, NOT Engine truth.
docs/architecture/
  PROPOSAL_LAYER_BRIDGE_SPEC.md
                        PR54 proposal layer — caller-side
                          candidate, NOT Engine acceptance.
docs/architecture/
  OPERATOR_DECISION_BOUNDARY_SPEC.md
                        PR57 §3 "Operator acceptance is a gate,
                          not Engine truth".
```

### §4.2 evidences_for_claim — runtime cross-check

```
ragcore/engine.py:823   def evidences_for_claim(self, claim_id):
                          return [ev for ev in self._evidences.values()
                                   if ev.claim_id == claim_id]
docstring says "supporting" (historical wording);
behavior is purely "Evidence records whose claim_id field
equals the argument", which is polarity-neutral.
The same evidence_id may simultaneously appear in
self._contradictions[claim_id] (see register_contradiction
at line 1051 — explicit cross-claim freedom note).
```

### §4.3 effective_confidence — runtime cross-check

```
ragcore/engine.py:1779   def compute_effective_confidence(...)
Composition formula (PR11-D + PR11-C + PR12-D + PR19-E +
PR20-F + PR21-L):

  effective = base
            × _status_modifier_for_claim
            × _freshness_modifier_for_claim
            × _gap_modifier_for_claim
            × _count_modifier_for_claim
            × _rule_stats_modifier_for_claim
            × _evidence_type_modifier_for_claim
```

No probabilistic interpretation anywhere. PR44-D
AP-CF-1 / AP-X-4 anti-patterns already documented at
`docs/architecture/ENGINE_READ_SURFACE_AUDIT.md` lines 634-638
and at the LLM packet boundary
(`docs/architecture/LLM_CONTEXT_PACKET_SPEC.md` lines 150-211).

### §4.4 Observation.source_type / PR59 SourceType — concept comparison

```
ragcore/types.py:64-70   Observation dataclass:
                           id / entity_id / raw_ref_id / type /
                           source_type: int = 0
ragcore/engine.py:707     add_observation(... source_type: int = 0)
                          — `: int` is an annotation/default only;
                          NO runtime type validation in
                          add_observation OR from_snapshot (value
                          retained as provided). P04 adds none.
                          [post-audit: corrected from "no
                          validation beyond int type"]

docs/architecture/DATA_ACCESS_PROFILE_CONTRACT.md §6
                          PR59 SourceType: conceptual axis
                          ("Where did this data come from?")
                          Illustrative examples: api / tool /
                          file / log / operator / engine /
                          retrieval_system / external_system.
                          NOT a ragcore registry.
                          NOT an enum.
                          Anti-pattern AP1 already forbids
                          treating source_type as semantic_role.
```

Conclusion: same word root, two abstractions. §53.5 locks the
non-equivalence and forbids documents from claiming an
automatic mapping or shared registry.

### §4.5 freshness — runtime cross-check

```
ragcore/engine.py:1343   def evidence_freshness(self, evidence_id):
                           return evidence_id
docstring: "freshness = evidence.id ... wall-clock 안 봄 ...
engine-local 의미만 가짐"
ragcore/engine.py:1362   active_contradictions_by_freshness:
                           sorted evidence_id desc.
ragcore/engine.py:443    _FRESHNESS_PENALTY_WEIGHT = 0.5
ragcore/engine.py:573    "Evidence freshness (PR11-A §25)"
docs/dev/PR_013_EVIDENCE_FRESHNESS_MVP.md
                          Historical record already stating:
                          "Freshness is evidence-registration
                           order, not wall-clock time."
docs/dev/PR_015_FRESHNESS_REFUTE_MVP.md
                          "Wall-clock timestamp — PR10-A/B /
                           PR11-A/C/D 일관 영구 OOS"
```

No code or document needs algorithmic change. §53.6 only adds
a normative English clarification.

[post-audit] Live vs restored distinction (G-P04-09): the
runtime returns `evidence_id` unchanged. For LIVE evidence the id
is allocated monotonically by `_allocate_id("evidence")`, so it
is a registration-order proxy within that Engine's history. For
RESTORED evidence, `evidence_freshness` returns the serialized id
verbatim; it does not independently prove the original
registration order or wall-clock time of an arbitrary
contract-admissible snapshot (sparse IDs remain admissible per
§52.5). The corrected §53.6 records this distinction; the
algorithm is unchanged.

---

## §5 Locked Meanings

`docs/contracts/05_DATA_CONTRACT_MVP.md §53` sub-sections:

```
§53.1   Scope
§53.2   Evidence representation layers (Layer 1 / 2 / 3)
§53.3   evidences_for_claim polarity neutrality
§53.4   effective_confidence as policy signal
§53.5   Observation.source_type vs PR59 SourceType
§53.6   Freshness as ingestion-order policy
§53.7   Cross-section non-goals
```

---

## §6 Repository-Wide Contradiction Scan

### §6.1 Corrected (in-place edits)

```
docs/architecture/ENGINE_READ_SURFACE_AUDIT.md:308-310
  before: "supporting evidence summaries"
  after:  "evidence summaries (polarity-neutral; see
            DATA_CONTRACT §53.3)"

docs/architecture/ENGINE_READ_SURFACE_AUDIT.md:359-361
  before: "supporting evidence summaries → 1 evidences_for_claim
            + N evidence_freshness"
  after:  "evidence summaries → 1 evidences_for_claim
            + N evidence_freshness
            (polarity-neutral; see DATA_CONTRACT §53.3)"

docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md:116
  before: "- supporting evidence summaries (id, type, strength,
            freshness)"
  after:  "- evidence summaries (id, type, strength, freshness)
            — polarity-neutral, per DATA_CONTRACT §53.3"
```

These three lines directly mapped `evidences_for_claim` to
"supporting evidence summaries" inside current normative or
auditing documents. §53.3 is now the cross-reference for the
polarity-neutral reading.

### §6.2 Historical records intentionally unchanged

```
docs/dev/PR_021_EVIDENCE_TYPE_MODIFIER_MVP.md
  Uses "direct supporting evidence" as a defined term scoped to
  the evidence_type modifier calculation (Evidence whose
  claim_id matches, that is not in contradictions, that is not
  resolved). Historical artifact; the term is internally
  consistent within that PR's scope.

docs/dev/PR_010_DISPUTED_REFUTATION_MVP.md
  Mentions "Freshness / timestamp" as an open question at that
  PR's date. Historical context; the open question was later
  resolved against timestamps in PR11-A and PR13.

docs/dev/PR_013_EVIDENCE_FRESHNESS_MVP.md
  Already states "Freshness is evidence-registration order,
  not wall-clock time." Aligned; no change.

docs/dev/PR_015_FRESHNESS_REFUTE_MVP.md
  "Wall-clock timestamp — 영구 OOS." Aligned; no change.

docs/contracts/05_DATA_CONTRACT_MVP.md:7131
  Historical changelog item "PR21-L `Evidence.claim_id ==
  claim_id` direct supporting evidence 정의 보존". Historical
  reference scope; preserved.

docs/dev/PR_063_*.md
  Stage-1 "external item" phrasing — aligned with §53.2 Layer 1.
```

### §6.3 No contradiction (already disclaimed)

```
docs/architecture/LLM_CONTEXT_PACKET_SPEC.md
  Lines 150-211 already forbid probability phrasings around
  base_confidence / effective_confidence at the LLM boundary.
  §53.4 generalizes that rule beyond the LLM packet.

docs/architecture/LLM_CONTEXT_PACKET_SPEC.md:488
  "supporting evidence list (opaque ids and adapter strengths)"
  — appears inside an allowed-phrasings template that itself
  already isolates "opaque ids and adapter strengths" from
  polarity verdict. Kept as is; §53.3 is the cross-reference.

docs/architecture/LLM_CONTEXT_PACKET_SPEC.md:403
  "supporting evidence and gaps are elsewhere in the packet"
  — locative phrase, not a polarity claim.

docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md:201-345
  Already enumerates probability translation as an anti-pattern
  (P2 in §3.3 / forbidden phrasings list). Aligned.

docs/architecture/ROLE_ASSIGNMENT_POLICY_SPEC.md:510-513
  Already states "It must not be silently converted into
  certainty." and "This policy does not introduce a new
  confidence or probability system." Aligned.

docs/architecture/EXTERNAL_ADAPTER_TRANSLATION_BOUNDARY_SPEC.md:43
  "numerical confidence or probability" listed as a forbidden
  forced translation. Aligned with §53.4.

docs/architecture/DATA_ACCESS_PROFILE_CONTRACT.md §6
  PR59 SourceType already locked as a conceptual axis distinct
  from any ragcore-stored field. Aligned with §53.5.

docs/architecture/DATA_ACCESS_PROFILE_CONTRACT.md:666
  Anti-pattern AP1 "source_type == semantic_role" already
  blocks the most extreme conflation. §53.5 sharpens the
  ragcore-side wording but introduces no new lock.
```

### §6.4 Documents with "supporting" wording in narrative context (kept)

```
docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md:332
  "새 supporting evidence 가 들어왔다면 confirm_claim_if_ready
   새 contradicting evidence 가 들어왔다면 dispute / refute"
  — informal call-order narration that EXPLICITLY contrasts
  "supporting" against "contradicting"; the dichotomy is the
  whole point of the paragraph. Edit would obscure the
  narration without removing any concrete inaccuracy.
  Classified as "narrative juxtaposition, kept; §53.3 is the
  precision cross-reference".

docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md:505
  Step 6 "Evidence 등록 add_evidence (supporting evidence 모두
  batch)" / Step 8 "Contradiction 등록 add_evidence +
  register_contradiction (반대 증거가 있을 때)" — same
  juxtaposition pattern as line 332. Kept for the same reason.

docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md:318
  "adapter has high-confidence supporting evidence elsewhere"
  — adapter-side decision criterion in a Layer 1 / Layer 2
  context. §53.2 cross-reference suffices.

docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md:318
  "is contradiction evidence E sufficient to refute, or do we
   need supporting evidence first?" — explicit dichotomy
  question inside an LLM-input template. §53.3 cross-reference
  suffices.
```

### §6.5 Out-of-scope — PR69-P05 candidates (recorded only)

```
sentinel rule reference                 PR69 candidate
unregistered advisory rule references   PR69 candidate
Gap.claim_id ownership semantics        PR69 candidate
claim_gap_refs as the official Claim-Gap relation
                                        PR69 candidate
shared Gap reference via dedup index    PR69 candidate
```

§53 does not touch any of these. PR68-P04 only records that
they exist as PR69 work.

### §6.6 Runtime docstring deliberately preserved

```
ragcore/engine.py:824
  def evidences_for_claim(self, claim_id: int) -> list[Evidence]:
      """Return all Evidences supporting ``claim_id`` ..."""

  The word "supporting" inside this runtime docstring is the
  historical artifact §53.3 references. The PR68-P04 directive
  §12 forbids ragcore/ edits, so the docstring is intentionally
  left as is. §53.3 is the authoritative reading; the docstring
  is a historical layer that may be aligned in a separate later
  PR when the runtime-edit ban is lifted.
```

---

## §7 Structural and Behavior Invariants

```
Engine public methods                40         (unchanged)
Engine private methods               18         (unchanged)
ragcore.__all__                      48         (unchanged)
snapshot schema_version              2          (unchanged)
snapshot top-level keys              18         (unchanged)

new public symbol                    0
new Engine method                    0
new dependency                       0
new test                             0
new exception class                  0

Python files changed                 0
runtime files changed                0
```

### runtime behavior delta

```
0
```

### judgment semantics delta

```
0
```

### documentation interpretation delta

```
+ Evidence external / interpreted / Engine record layer
  separation locked (§53.2)
+ evidences_for_claim polarity-neutral semantics locked (§53.3)
+ effective_confidence non-probabilistic policy meaning locked
  (§53.4)
+ Observation.source_type and PR59 SourceType non-equivalence
  locked (§53.5)
+ freshness as evidence-registration order locked (§53.6)
+ "supporting evidence summaries" replaced with polarity-
  neutral phrasing in two architecture documents (§6.1)
```

---

## §8 Regression Result

`pytest -q` on 226차 commit `a934be6`:

```
1364 passed
```

Identical to the baseline at `main` `db5a405`. PR68-P04 is
documentation only; no runtime file or test was modified.

---

## §9 Self-Review

```
[x] Evidence 3-layer separation explicit (§53.2).
[x] Raw item NOT auto-promoted to ragcore.Evidence in any
    sentence introduced by PR68.
[x] Interpreted item NOT auto-promoted to ragcore.Evidence.
[x] evidences_for_claim wording NOT given polarity in any
    sentence introduced by PR68.
[x] contradiction relation kept structurally distinct from any
    Evidence polarity claim (§53.3 explicitly notes the same
    evidence_id may live in both views).
[x] effective_confidence wording NOT given probabilistic
    semantics; existing anti-patterns generalized (§53.4).
[x] RuleStats wording NOT given truth-likelihood semantics in
    §53.4 forbidden-phrasings list.
[x] Observation.source_type and PR59 SourceType locked as
    distinct (§53.5); no automatic mapping introduced.
[x] freshness phrased as evidence-registration order; runtime
    docstring at engine.py:1346 already states the same
    (§53.6).
[x] No sentence introduced by PR68 strengthens the existing
    runtime contract.
[x] PR69 rule / gap concerns recorded as deferred (§6.5),
    NOT introduced into §53.
[x] Runtime files NOT modified.
[x] Tests NOT modified.
[x] Examples Python source NOT modified.
[x] historical dev records NOT rewritten beyond cross-
    reference notes in this dev record.
[x] domain-specific vocabulary (cerberus / cve / scanner /
    nmap / etc.) NOT present in §53 normative body.
[x] Engine 40 / 18 unchanged (AST measured).
[x] ragcore.__all__ 48 unchanged.
[x] schema_version 2 / 18 top-level keys unchanged.
```

---

## §10 Closing Position

PR68-P04 is closed when:

- 226차 `docs` adds §53 and the two architecture clarifications.
- 227차 `docs(dev)` records this development record.

This PR is opened as draft; merge is not part of PR68-P04 per
the directive. PR69-P05 (rule reference / shared gap alignment)
is **not** auto-scheduled by this PR and requires a separate
directive entry.

After merge, the P-series progresses by one step:

```
PR65-P01  Claim Status Admission Fail-Fast                CLOSED
PR66-P02  Snapshot Restore Integrity Contract             CLOSED
PR67-P03  Snapshot Restore Integrity Enforcement          CLOSED
PR68-P04  Evidence / Confidence / Source / Freshness      ready
PR69-P05  Rule Reference / Shared Gap                     NOT scheduled
```

---

## §11 Post-Audit Correction (independent audit, 2026-06-25)

PR68-P04 received an independent post-merge audit on the current
`main` baseline. The §53 text was verified byte-identical between
the P04 squash (`0fae073`) and current `main`, so every finding
was present at merge and at audit time. The correction is
documentation-only and lands on a fresh branch as two commits
(contract+architecture, then this record); it does not amend the
historical merge.

Corrected findings (documentation only):

- **G-P04-01** — §53.2 and §4.1 of this record overstated
  `add_evidence` as "the only path that materializes a Layer-3
  Evidence into Engine state." `from_snapshot` also materializes
  Layer-3 Evidence (restoration of already-serialized state, not
  a Layer-1/2 promotion). §53.2 now distinguishes the live
  promotion path from the restoration path.
- **G-P04-07** — §53.5 and §4.4 claimed source_type "no
  validation beyond int type," implying a runtime int gate.
  Empirically `add_observation` and `from_snapshot` accept any
  value (str / float / None / bool / IntEnum / list) and store it
  verbatim: the `: int` is a type annotation only, with NO runtime
  validation. Corrected to record the actual absence of a gate;
  no validator added.
- **G-P04-09** — §53.6 framed freshness as ingestion order
  "allocated by `_allocate_id`" without a restore qualifier.
  `evidence_freshness` returns the serialized `evidence_id`
  verbatim for restored snapshots (ordinal proxy, not proven
  chronology). The live/restored distinction is now recorded.
  Algorithm unchanged.
- **G-P04-11** — §53.3's terminology closure was incomplete. The
  original repository-wide scan missed two active "supporting"
  surfaces:

```text
ragcore/engine.py  Engine.add_evidence active docstring
                     ("Add an Evidence supporting ``claim_id``")
docs/architecture/LLM_CONTEXT_PACKET_SPEC.md §4.3
                     value description "supporting the claim" /
                     "supporting facts"
```

  Final disposition:

```text
LLM_CONTEXT_PACKET_SPEC §4.3 value description
                     CORRECTED (polarity-neutral) in this
                     post-audit correction
supporting_evidence packet key
                     RETAINED as a rename-locked compatibility
                     label; its value is defined polarity-neutral
Engine.add_evidence docstring
                     DEFERRED (active runtime docstring,
                     runtime-edit boundary)
Engine.evidences_for_claim docstring
                     DEFERRED (active runtime docstring,
                     runtime-edit boundary)
```

  The two active runtime docstrings are NOT reclassified as
  resolved; §53.3's active-wording ledger records them as
  explicitly deferred.

Findings requiring no change (audit accepted):

```text
G-P04-02  Layer-1 "no polarity"      NOT_A_DEFECT (contextually safe)
G-P04-03  polarity-neutral read       NOT_A_DEFECT (cross-claim freedom kept)
G-P04-04  docstring deferral          ACCEPTABLE (subsumed by G-P04-11)
G-P04-05  "7-modifier"                NOT_A_DEFECT (§53.4 = base × 6)
G-P04-06  non-probability             NOT_A_DEFECT ("not truth probability")
G-P04-08  PR59 SourceType            NOT_A_DEFECT (no enum; §6 conceptual)
G-P04-12  cross-references            NOT_A_DEFECT (all accurate)
G-P04-13  historical accounting       accurate (content issues = 01/07)
```

Unchanged behavior (this correction):

```text
runtime code delta:                0
test delta:                        0
public API delta:                  0
snapshot schema delta:             0
effective-confidence formula delta: 0
freshness algorithm delta:         0
SourceType registry delta:         0
```

### Historical vs post-audit accounting

Historical P04 facts (preserved, NOT rewritten):

```text
base tests:                1364
P04 tests:                 1364
Engine public / private:   40 / 18
ragcore.__all__:           48
snapshot schema_version:   2
top-level snapshot keys:   18
P04 changed files:         4 (docs only)
```

Measured current `main` values at this post-audit correction
(distinct from the historical P04 values above):

```text
full suite:                1987 passed
Engine public / private:   42 / 20
ragcore.__all__:           50
snapshot schema_version:   2
top-level snapshot keys:   18
```
