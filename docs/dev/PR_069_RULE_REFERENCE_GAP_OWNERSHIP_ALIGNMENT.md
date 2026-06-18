# PR69-P05 — Rule Reference / Gap Ownership / Shared Gap Semantics Alignment

Development record for the §54 alignment landed by PR69-P05
(branch `docs/rule-gap-semantics-alignment`).

```
base:            main 0fae073 (PR68-P04: Evidence / Confidence
                                / Source / Freshness Semantics
                                Alignment)
branch:          docs/rule-gap-semantics-alignment
228차 commit:    d5ab534   docs (§54)
229차 commit:    (this record, docs/dev)
type:            framework-level documentation alignment,
                  doc-only (no runtime change, no test, no
                  Python file modified)
```

This record captures the runtime cross-check for each of the
PR69-scope terms, the §54 sub-section ↔ runtime mapping, the
repository-wide contradiction scan classification, the
structural invariants, and the closing position of PR69-P05.

---

## §1 Purpose

Three rule-reference layers and three Gap-relation layers exist
in the codebase but were not previously consolidated in a single
normative section:

```
Rule references:
  1. Stored rule reference  (Claim/Gap/Relation field)
  2. Registered RuleDefinition (Engine._rule_definitions)
  3. RuleStats state (Engine._rule_stats)

Gap relation:
  4. Gap.claim_id            (first-registration provenance)
  5. _claim_gap_refs /        (Claim-to-Gap membership)
     claim_gap_refs
  6. gaps_for_claim          (authoritative public read)
```

PR69-P05 locks the **existing** meaning of each in
`docs/contracts/05_DATA_CONTRACT_MVP.md` §54. PR69 introduces no
new dataclass, enum, public symbol, exception class, validator,
range check, migration, or dependency. Every term keeps its
current code-level behavior.

---

## §2 Baseline

```
base:                       main 0fae073
                              (PR68-P04: Evidence / Confidence
                               / Source / Freshness Semantics
                               Alignment)
baseline tests:             1364 passing
predecessor stack:          PR49 – PR68-P04
Engine public methods:      40
Engine private methods:     18
ragcore.__all__:            48
snapshot schema_version:    2
snapshot top-level keys:    18
```

228차 added `§54. Rule Reference and Gap Ownership Semantics`
(`+793` lines) to `docs/contracts/05_DATA_CONTRACT_MVP.md`. 229차
adds this record. No `ragcore/` file is touched. No test is
touched. No in-place edits to other documents were required —
existing PR4 / PR20-F / PR26-R / PR29-R / §52 / §53 phrasings
already align with §54 (see §6 scan).

---

## §3 Files Changed

```
docs/contracts/05_DATA_CONTRACT_MVP.md
                                              +793 lines    (228차)
docs/dev/PR_069_RULE_REFERENCE_GAP_OWNERSHIP_ALIGNMENT.md
                                              this record   (229차)

ragcore source delta:         0 bytes
tests added:                  0
Python files changed:         0
framework public symbols:     0 added
new exception classes:        0
new dependencies:             0
```

---

## §4 Runtime Cross-Check (empirical probe on `main` 0fae073)

### §4.1 Stored rule references and registered definitions

```
ragcore/types.py:74-90      Claim dataclass:
                              created_by_rule + created_by_rule_version
ragcore/types.py:121-128     Gap dataclass:
                              created_by_rule (no version)
ragcore/types.py:103-118     Relation dataclass:
                              rule_id (no version)
ragcore/engine.py:1448-1463  register_rule:
                              raises ValueError on duplicate
                              allocates a RuleStats slot
ragcore/engine.py:1465-1476  get_rule:
                              strict; raises KeyError on miss
                              (PR28-O §40 joint identity lock)
ragcore/engine.py:1478-1490  get_rule_stats:
                              strict; raises KeyError on miss
                              (PR29-R §41)
ragcore/engine.py:736-760    add_claim:
                              admits any int for created_by_rule
                              and created_by_rule_version
                              (no registry validation)
ragcore/engine.py:837-880    add_relation:
                              admits any int for rule_id
                              (no registry validation)
ragcore/engine.py:892-955    add_gap:
                              admits any int for rule_id;
                              first-severity policy preserved
                              on dedup hit
```

### §4.2 Rule-stats modifier behavior

```
ragcore/engine.py:1573-1649  _rule_stats_modifier_for_claim:
  line 1625    claim = self._claims[claim_id]
  line 1626    if claim.created_by_rule == 0:
  line 1627        return 1.0
  line 1628    key = (claim.created_by_rule,
                      claim.created_by_rule_version)
  line 1629    stats = self._rule_stats.get(key)
  line 1630    if stats is None:
  line 1631        return 1.0
  line 1632+   ... maturity + precision composition
```

Two early-return conditions return `1.0`:

```
(a) claim.created_by_rule == 0   (sentinel; version irrelevant)
(b) self._rule_stats.get(key) is None  (lookup miss)
```

Both branches leave the Claim record unchanged and raise no
exception.

### §4.3 Empirical probes (executed on main 0fae073)

```
Probe A — Unregistered Claim rule pair admitted
  add_claim(rule_id=999, rule_version=42, base=0.5)
    Claim.created_by_rule == 999
    Claim.created_by_rule_version == 42
    get_rule(999, 42)         -> KeyError('unknown rule: rule_id=999, version=42')
    get_rule_stats(999, 42)   -> KeyError(same)
    effective_confidence       == 0.5  (rule-stats modifier 1.0)

Probe B — Sentinel ignores version
  add_claim(rule_id=0, rule_version=5, base=0.5)
    Claim.created_by_rule == 0
    effective_confidence       == 0.5

Probe C — Late registration changes modifier without rewriting Claim
  add_claim(rule_id=7, rule_version=1, base=0.5)
    effective_confidence       == 0.5
  register_rule(RuleDefinition(7, 1, EXPERIMENTAL, prior=0.5))
                                  (slot init: firing_count=0)
    effective_confidence       == 0.4
                                  (rule-stats modifier 0.8 under
                                   firing_count=0 maturity)
    Claim.created_by_rule       == 7   (unchanged)
    Claim.created_by_rule_version == 1 (unchanged)

Probe D — Shared Gap via dedup
  add_gap(claim=A, gap_type=5, required_evidence_type=42,
          severity=0.5, rule_id=1)                  -> gap_id 1
  add_gap(claim=B, gap_type=5, required_evidence_type=42,
          severity=0.7, rule_id=1)                  -> gap_id 1 (same)
  Gap.claim_id                                       == A (unchanged)
  Gap.severity                                       == 0.5 (first kept)
  gaps_for_claim(A) ids                              == [1]
  gaps_for_claim(B) ids                              == [1]

Probe E — Gap-scoped resolution
  add_evidence(claim=A, type=42, strength=0.6)      -> ev_A
  resolve_gaps_for_evidence(ev_A)                    -> writes
                                                       _gap_resolutions[1] = ev_A
  gap_resolution(1)            == ev_A
  Evidence(ev_A).claim_id      == A   (NOT re-parented)
  Gap.claim_id                 == A   (unchanged)

Probe F — Shared resolution does NOT auto-confirm
  Claim A.status before confirm   CANDIDATE
  Claim B.status before confirm   CANDIDATE
  confirm_claim_if_ready(A)        True; A.status -> CONFIRMED
  confirm_claim_if_ready(B)        True; B.status -> CONFIRMED
                                   (each call required;
                                    resolution alone did NOT
                                    auto-transition either Claim)

Probe G — PR67 restore-integrity admits advisory rule reference
  add_claim(rule_id=999, rule_version=99) -> snapshot -> restore
  restored.get_claim(1).created_by_rule == 999
  restored.get_claim(1).created_by_rule_version == 99
  no ValueError, no TypeError, no rejection
```

All seven probes match the §54 normative locks. No probe
contradicted any §54 sentence.

---

## §5 §54 Contract Mapping

`docs/contracts/05_DATA_CONTRACT_MVP.md §54` sub-sections:

```
§54.1   Scope
§54.2   Stored rule references and registered definitions
§54.3   Claim advisory rule pair
§54.4   Strict reads and RuleStats lookup miss
§54.5   Late rule registration
§54.6   created_by_rule == 0 sentinel scope
§54.7   Rule ID convention vs runtime enforcement
§54.8   Claim, Gap, and Relation rule fields
§54.9   Gap.claim_id is first-registration provenance
§54.10  Claim-to-Gap reference relation
§54.11  Shared Gap dedup semantics
§54.12  Gap-scoped resolution
§54.13  Lifecycle interaction
§54.14  Snapshot and restore implications
§54.15  Non-goals
```

---

## §6 Repository-Wide Contradiction Scan

### §6.1 Corrected (in-place edits)

```
(none)
```

The current normative and guide documents already align with
§54. No in-place edits were required. PR4 §16 (Gap dedup
weakening), PR20-F §32 + PR26-R §38 (rule-stats sentinel +
lookup miss), PR28-O §40 (joint identity), PR29-R §41 (maturity
+ precision), §52 (cross-reference integrity), and §53
(terminology alignment) collectively cover the same boundaries;
§54 consolidates them into a single consumer-facing normative
section.

### §6.2 Already aligned (cross-references kept)

```
docs/contracts/05_DATA_CONTRACT_MVP.md:1242, 1314, 1562
                          PR4 contract entry establishing
                          Gap.claim_id 의미 약화 ("first
                          registering"). Aligned with §54.9.

docs/contracts/05_DATA_CONTRACT_MVP.md:5183, 5203, 5261,
                          5318, 7327, 7394, 7411, 7463, 7464,
                          7556, 7563, 10059, 10062, 10070
                          PR20-F / PR26-R / PR29-R contract
                          entries describing the rule-stats
                          modifier sentinel + lookup-miss
                          neutral path. All explicitly scope
                          the sentinel to Claim.created_by_rule
                          in the rule-stats-modifier context.
                          Aligned with §54.4 and §54.6.

docs/contracts/05_DATA_CONTRACT_MVP.md:13822
                          §52.2.3 entry stating Gap.claim_id is
                          informational about origin only;
                          many-to-many lives in claim_gap_refs.
                          Aligned with §54.9 / §54.10.

docs/contracts/05_DATA_CONTRACT_MVP.md:14123
                          §52.12 non-goal preserving the
                          first-registering meaning. Aligned
                          with §54.9.

docs/dev/PR_004_GAP_DEDUP_MVP.md:95
                          "이전: gap.claim_id == claim_id
                           필터". Historical note; aligned
                          with §54.9 / §54.10.

docs/dev/PR_066_SNAPSHOT_RESTORE_INTEGRITY_CONTRACT.md
                          §4.7 + §52.2.3 entries already
                          state Gap.claim_id is informational
                          and claim_gap_refs is the
                          many-to-many fan-out. Aligned.

docs/dev/PR_067_SNAPSHOT_RESTORE_INTEGRITY_ENFORCEMENT.md
                          §8 lists "Gap.claim_id 'first
                          registering claim' meaning preserved"
                          as an intentional preservation, with
                          a positive round-trip test
                          (TestGapClaimIdFirstRegisteringPreserved).
                          Aligned.

docs/dev/PR_020_RULE_STATS_MODIFIER_MVP.md
docs/dev/PR_026_RULE_STATS_CONTINUOUS_MODIFIER_MVP.md
                          Historical dev records describing
                          the sentinel + lookup-miss neutral
                          policy at their respective PR dates.
                          Aligned with §54.4 / §54.6.
```

### §6.3 No contradiction found

A repository-wide grep for the following phrasings returned **no
matches** in normative or guide documents:

```
"every rule_id ... registered"
"every Claim ... registered"
"register_rule mandatory"
"registry foreign key"
"Gap belongs only"
"Gap.claim_id is the owner"
"exclusive owner"
"gaps_for_claim filters Gap.claim_id"
"every rule_id field uses sentinel 0"
"shared Gap is copied"
"resolution belongs to one Claim"
"resolve confirms every Claim"
"modifier 1.0 means perfect"
"unregistered rule means corrupt"
```

The codebase did not have an existing misuse of these terms in
normative documents.

### §6.4 Historical records intentionally unchanged

```
docs/dev/PR_020 / PR_026 / PR_028 / PR_029 records
                          state the rule-stats modifier
                          sentinel + lookup-miss policy at
                          their respective PR dates. Wording
                          is internally consistent and aligns
                          with §54. Preserved as historical
                          snapshots.

ragcore/engine.py:1346 / 824 / 1448 / 1465 / 1478 / 1573
                          runtime docstrings predating §54.
                          The directive forbids ragcore/ edits;
                          §54 becomes the authoritative read.
                          The docstrings already align with
                          §54 (e.g. 1452: "같은 rule_id 라도
                          version 이 다르면 별개 룰로 취급한다"
                          matches §54.2 Layer 2).
```

### §6.5 Future PR candidates (recorded only)

```
Numeric-range validation for rule_id / rule_version
  Loader documents discuss 1..65535 mapping with 0 reserved,
  but Engine admission does NOT enforce a range at the public
  API surface (§54.7). A future PR may either widen the loader
  contract or add runtime validation; §54 records the gap but
  does not schedule the work.

Optional consumer-side rule-registry validator
  A consumer that wants stricter discipline may want a
  validator that flags advisory references in a snapshot. §54
  records that PR67 §52 deliberately does NOT enforce this
  (§54.14); a future PR may introduce an optional validator
  separately.

PR21-L "direct supporting evidence" terminology
  PR53 (§53.3) noted this as a scoped term in the
  evidence_type_modifier calculation. §54 does not touch the
  modifier behavior; no follow-up required.
```

§54 does not schedule any of the above. PR69-P05 only records
that they exist as potential future work.

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
+ Stored rule reference / registered RuleDefinition /
  RuleStats state three-layer model locked (§54.2)
+ Claim advisory rule pair admission semantics locked (§54.3)
+ Strict-read vs advisory-write split locked (§54.4)
+ RuleStats lookup miss neutral policy locked (§54.4)
+ Late rule registration behavior locked: registry-state
  change may affect modifier lookup without changing Claim
  record (§54.5)
+ Claim.created_by_rule == 0 sentinel scope-limited to
  _rule_stats_modifier_for_claim (§54.6)
+ Loader convention vs runtime enforcement distinguished
  (§54.7)
+ Claim / Gap / Relation rule field non-equivalence locked
  (§54.8)
+ Gap.claim_id first-registration provenance locked (§54.9)
+ _claim_gap_refs internal source of truth + gaps_for_claim
  authoritative public read locked (§54.10)
+ Shared Gap dedup key + first-severity preservation locked
  (§54.11)
+ Gap-scoped resolution semantics locked (§54.12)
+ Shared resolution vs explicit lifecycle call separation
  locked (§54.13)
+ §52 enforced vs not-enforced split recorded (§54.14):
  advisory rule references are not §52 violations
```

---

## §8 Regression Result

`pytest -q` on 228차 commit `d5ab534`:

```
1364 passed
```

Identical to the baseline at `main` `0fae073`. PR69-P05 is
documentation only; no runtime file or test was modified.

---

## §9 Self-Review

```
[x] Stored reference NOT equated with registry membership in
    any §54 sentence.
[x] RuleDefinition NOT equated with RuleStats state.
[x] Advisory write NOT equated with strict read.
[x] Unregistered Claim NOT described as invalid in §54.
[x] modifier 1.0 NOT described as perfect quality.
[x] Late registration phrased as registry-state change
    affecting modifier lookup, NOT as Claim provenance
    rewrite.
[x] created_by_rule == 0 sentinel scoped to
    _rule_stats_modifier_for_claim; NOT lifted into a
    framework-wide marker.
[x] Cross-field sentinel disequality explicit
    (Claim.created_by_rule == 0 ≠ Gap.created_by_rule == 0
     ≠ Relation.rule_id == 0).
[x] Convention vs runtime enforcement explicitly separated.
[x] Claim / Gap / Relation rule fields described as three
    distinct shapes with different versioning capacity.
[x] Gap.claim_id NOT described as owner; first-registration
    provenance explicitly used.
[x] _claim_gap_refs NOT promoted to a public API; called
    "internal source of truth" only.
[x] gaps_for_claim used as the single authoritative public
    read.
[x] Shared Gap NOT described as copied; dedup hit shown to
    preserve first severity.
[x] Resolution described as gap-scoped; Evidence.claim_id
    and Gap.claim_id explicitly NOT rewritten.
[x] Shared resolution and explicit lifecycle call kept
    distinct; "automatic Claim confirmation" listed as a
    non-equivalence.
[x] §52 enforcement boundary respected; advisory rule
    references NOT promoted to mandatory foreign keys.
[x] PR67 restore-integrity admission behavior cited (Probe G).
[x] No runtime / test / examples Python source modified.
[x] No new dataclass / enum / public symbol / exception class /
    dependency.
[x] No in-place historical rewrite.
[x] Domain-specific vocabulary (cerberus / cve / scanner /
    etc.) NOT present in §54 normative body.
[x] Engine 40 / 18, ragcore.__all__ 48, schema_version 2,
    18 top-level keys — all unchanged (AST measured).
[x] runtime behavior delta = 0; judgment semantics delta = 0.
```

---

## §10 Closing Position

PR69-P05 is closed when:

- 228차 `docs` adds §54.
- 229차 `docs(dev)` records this development record.

This PR is opened as draft; merge is not part of PR69-P05 per
the directive.

After merge, the P-series progresses by one step:

```
PR65-P01  Claim Status Admission Fail-Fast                CLOSED
PR66-P02  Snapshot Restore Integrity Contract             CLOSED
PR67-P03  Snapshot Restore Integrity Enforcement          CLOSED
PR68-P04  Evidence / Confidence / Source / Freshness      CLOSED
PR69-P05  Rule Reference / Gap Ownership / Shared Gap     ready
```

No follow-up PR is auto-scheduled by PR69-P05.
