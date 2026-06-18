# PR66-P02 — Snapshot Restore Integrity Contract

Development record for §52, the snapshot restore integrity
boundary introduced in PR66-P02 (branch
`docs/snapshot-restore-integrity-contract`).

```
base:            main 9926049 (PR65-P01: Claim Status Admission
                                Fail-Fast)
branch:          docs/snapshot-restore-integrity-contract
220차 commit:    4f2d524   docs(contract)
221차 commit:    (this record, docs/dev)
type:            framework-level contract boundary, doc-only
```

This record captures the snapshot structure investigation,
the cross-reference / set / index / RuleStats / counter
invariants locked in §52, the four restore-policy decisions
(final defender / failure mode / exception types / validation
timing), the conceptual violation label catalogue, the
preservation contract, the prohibited-repair list, the PR67-P03
entry conditions, the verification results, and the closing
position of PR66-P02.

PR66-P02 is documentation only. It introduces no runtime
change, no test, no schema change, no public symbol, and no
dependency.

---

## §1 Purpose

PR65-P01 §51 closed the admission gate for `Claim.status` and
explicitly excluded "orphan reference checks, set-inclusion
checks, counter integrity" from its scope. PR66-P02 picks up
that boundary.

PR66-P02 answers five framing questions before any enforcement
PR is written:

```
1. Which snapshots are invalid?
2. How must an invalid snapshot fail?
3. Which layer owns the final defense?
4. What is the minimum scope PR67-P03 must enforce?
5. Which automatic repair behaviors are forbidden?
```

PR66-P02 does not implement a check, does not add a test, and
does not advance the snapshot schema. PR67-P03 will enforce
§52 in `Engine.from_snapshot()`; this record fixes what PR67-P03
is allowed to do and what it is forbidden to do.

---

## §2 Baseline

```
base:                       main 9926049
                              (PR65-P01: Claim Status Admission
                               Fail-Fast)
baseline tests:             1270 passing
predecessor stack:          PR49 – PR65-P01
Engine public methods:      40
Engine private methods:     18
ragcore.__all__:            48
snapshot schema_version:    2
snapshot top-level keys:    18
```

220차 added §52 to `docs/contracts/05_DATA_CONTRACT_MVP.md`
(`+464` lines). 221차 adds this record. No other files are
touched.

---

## §3 Files Changed

```
docs/contracts/05_DATA_CONTRACT_MVP.md
                                              +464 lines    (220차)
docs/dev/PR_066_SNAPSHOT_RESTORE_INTEGRITY_CONTRACT.md
                                              this record   (221차)

ragcore source delta:         0 bytes
tests added:                  0
framework public symbols:     0 added
Engine behavior:              0 added
example source files:         0 added
```

---

## §4 Snapshot Structure Investigation

The contract is anchored on the actual storage shapes at
`main` `9926049`. The investigation captured the 18 top-level
keys, the internal attribute mapping, the allocator semantics,
and the existing migration path. Everything in §52 cites the
real names, not invented names.

### §4.1 Top-level keys (18, schema_version = 2)

```
schema_version                     entities
next_id                            observations
lifecycle_seq                      claims
hint_evidence_types                evidences
rule_definitions                   relations
rule_stats                         gaps
gap_dedup_index                    gap_resolutions
claim_gap_refs                     contradictions
resolved_contradictions            claim_lifecycle_events
```

### §4.2 Internal attribute shapes

```
self._entities                : dict[int, Entity]
self._observations            : dict[int, Observation]
self._claims                  : dict[int, Claim]
self._evidences               : dict[int, Evidence]   (has claim_id)
self._relations               : dict[int, Relation]
self._gaps                    : dict[int, Gap]        (has claim_id)
self._rule_definitions        : dict[tuple[int, int], RuleDefinition]
self._rule_stats              : dict[tuple[int, int], RuleStats]
self._gap_dedup_index         : dict[tuple[int, int, int, int], int]
self._claim_gap_refs          : dict[int, set[int]]
self._gap_resolutions         : dict[int, int]
self._contradictions          : dict[int, set[int]]
self._resolved_contradictions : dict[int, set[int]]
self._claim_lifecycle_events  : dict[int, list[ClaimLifecycleEvent]]
self._hint_evidence_types     : set[int]
self._next_id                 : dict[str, int]
```

### §4.3 Allocator semantics

```
Engine._allocate_id(kind):
    next_id = self._next_id.get(kind, 0) + 1
    self._next_id[kind] = next_id
    return next_id
```

`self._next_id[kind]` stores the **last issued ID** for `kind`;
the next issued ID is `last + 1`. Collision is possible if a
snapshot restores `next_id[kind] < max(restored ID set for kind)`.
That condition is the basis of `COUNTER_COLLISION_RISK` in §52.5.

Allocator kinds observed in `Engine._allocate_id` call sites:

```
"entity" / "observation" / "claim" / "evidence" /
"relation" / "gap"
```

### §4.4 Migration path

```
_CURRENT_SNAPSHOT_SCHEMA_VERSION         = 2
_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS      = frozenset({1, 2})
_migrate_snapshot_v1_to_v2(snapshot)     adds hint_evidence_types = []
_migrate_snapshot_to_current(snapshot)   raises ValueError for missing
                                          or unsupported schema_version
```

`from_snapshot` runs `_migrate_snapshot_to_current` first and
then performs the §51 status admission pass on the migrated
dict before constructing the throwaway Engine instance (PR65-P01
218차). §52 reuses the same "before any state population" timing
slot for the new cross-reference / set / index / counter checks.

### §4.5 Existing exception sites (relevant to §52.7)

Inside `Engine.from_snapshot` and its helpers today:

```
_migrate_snapshot_to_current        ValueError (missing /
                                                unsupported schema)
_validate_claim_status_admission    TypeError or ValueError (§51)
_restore_dict_int and friends       KeyError if "key"/"value" missing,
                                    TypeError if a non-dict is passed
ScoreValue.__post_init__            ValueError if out of [0.0, 1.0]
```

The §52.7 policy converts lookup misses (`KeyError`) into the
contract surface (`TypeError` / `ValueError`) at PR67 enforcement
time. §52 does not require a new exception class.

### §4.6 Cross-claim contradiction freedom (preserved)

`register_contradiction` runtime docstring states:

```
Cross-claim 허용: evidence.claim_id == claim_id 강제 안 함.
```

§52.2.2 deliberately preserves this. The contract requires only
that `evidence_id` resolves in the restored Evidence set and
`claim_id` resolves in the restored Claim set; it does **not**
introduce an additional `evidence.claim_id == claim_id`
requirement.

### §4.7 Gap.claim_id semantics (preserved)

`add_gap` runtime comment states:

```
claim_id=claim_id,  # first registering claim — §16 의미 약화
```

§52.2.3 preserves this. `Gap.claim_id` is informational about
which Claim first triggered the Gap; the many-to-many fan-out
is in `claim_gap_refs`. §52 does not require Gap.claim_id to
appear in `claim_gap_refs[Gap.claim_id]`.

### §4.8 No existing snapshot validator

No consumer-side snapshot integrity validator exists at `main`
`9926049`. `examples/inspector/engine_inspector.py` and
`examples/inspector/packet_validator.py` cover read-only Engine
inspection and packet validation respectively, not snapshot
restore. `tests/test_engine_snapshot_migration.py` covers
schema_version error paths but not cross-reference integrity.

---

## §5 Locked Invariants

`docs/contracts/05_DATA_CONTRACT_MVP.md` §52 sub-sections:

```
§52.1   Scope and terminology (18 keys, internal shapes,
          allocator semantics)
§52.2   Reference integrity (Evidence → Claim;
          Contradiction → Claim/Evidence; Claim-gap → Claim/Gap;
          Gap resolution → Gap/Evidence)
§52.3   Set and index integrity (gap dedup target;
          resolved ⊆ contradictions for same claim)
§52.4   RuleStats identity integrity (int x int, bool excluded;
          rule_definitions match NOT required)
§52.5   Counter integrity (type-precise int; non-negative;
          ≥ max restored ID; sparse IDs permitted)
§52.6   Claim status linkage to §51 (unchanged; cross-reference
          only)
§52.7   Failure semantics (fail-fast; TypeError / ValueError;
          KeyError not in contract surface)
§52.8   Validation responsibility (Engine.from_snapshot final
          defender; consumer validator permitted but not framework
          public)
§52.9   Valid migration and round-trip preservation
§52.10  Prohibited automatic repair
§52.11  PR67-P03 entry conditions
§52.12  Non-goals
```

---

## §6 Restore Policy Decisions

Each decision is recorded with the considered options, the
selection, and the reason.

### §6.1 Final defender (§52.8)

```
A. consumer-side validator only          -> rejected (bypassable)
B. Engine.from_snapshot() only            -> selected
C. consumer-side validator + Engine       -> permitted as future
                                              optional expansion
```

Engine is selected because no caller can build an invalid Engine
through the public API, and consumer validators (if added later)
cannot substitute for Engine acceptance.

### §6.2 Failure mode (§52.7)

```
A. fail-fast on first violation          -> selected
B. collect all violations and return     -> rejected
C. validation result object              -> rejected
                                            (would add public type)
```

Selected because §52 explicitly forbids introducing a new public
result object or aggregating exceptions. PR67-P03 enforcement
must raise on the first violation.

### §6.3 Exception types (§52.7)

```
wrong Python type for a structural slot  -> TypeError
broken reference / subset / index /
  identity tuple shape / counter relation -> ValueError
unsupported / missing schema_version     -> ValueError (already
                                              established by
                                              _migrate_snapshot_to_current)
raw KeyError                             -> NOT part of contract
                                              surface
```

PR67-P03 must convert dict-lookup misses into the contract
surface before exiting `Engine.from_snapshot`. No new exception
class.

### §6.4 Validation timing (§52.8)

The contract requires:

```
- invalid snapshot never produces an observable Engine
- input snapshot dict not mutated
- pre-existing caller Engine not mutated
- restore failure does not expose partial state
```

Implementation freedom:

```
- pre-validate as much as possible before engine = cls() (PR65 pattern)
- where pre-validation is infeasible, perform validation inside
  a throwaway Engine instance that is never returned on failure
```

Either of the two implementation patterns satisfies §52.8 as long
as the four observable conditions above hold.

---

## §7 Conceptual Violation Label Catalogue

The labels below are **conceptual**. They are not runtime error
codes, not a public enum, and not part of `ragcore.__all__`. PR67
may reuse them as test method names or as exception message text
fragments, but it must not declare them as public symbols.

```
SNAPSHOT_TYPE_INVALID                     §52.7 (TypeError)
SNAPSHOT_VERSION_UNSUPPORTED              §52.7 (ValueError, existing)
SNAPSHOT_COLLECTION_INVALID               §52.7 (TypeError or ValueError)
CLAIM_STATUS_INVALID                      §52.6 (delegates to §51)
EVIDENCE_CLAIM_ORPHAN                     §52.2.1 (ValueError)
CONTRADICTION_CLAIM_ORPHAN                §52.2.2 (ValueError)
CONTRADICTION_EVIDENCE_ORPHAN             §52.2.2 (ValueError)
CLAIM_GAP_CLAIM_ORPHAN                    §52.2.3 (ValueError)
CLAIM_GAP_GAP_ORPHAN                      §52.2.3 (ValueError)
GAP_RESOLUTION_GAP_ORPHAN                 §52.2.4 (ValueError)
GAP_RESOLUTION_EVIDENCE_ORPHAN            §52.2.4 (ValueError)
GAP_DEDUP_TARGET_ORPHAN                   §52.3.1 (ValueError)
RESOLVED_CONTRADICTION_CLAIM_ORPHAN       §52.3.2 (ValueError)
RESOLVED_CONTRADICTION_NOT_SUBSET         §52.3.2 (ValueError)
RULE_STATS_IDENTITY_INVALID               §52.4   (TypeError /
                                                    ValueError)
COUNTER_TYPE_INVALID                      §52.5 (TypeError)
COUNTER_VALUE_INVALID                     §52.5 (ValueError)
COUNTER_COLLISION_RISK                    §52.5 (ValueError)
```

---

## §8 Preservation Contract

`§52.9` locks the following positive properties:

```
schema_version 2                             unchanged
snapshot top-level key set (18)              unchanged
v1 -> v2 migration (_migrate_snapshot_v1_to_v2)  unchanged
deterministic to_snapshot ordering           unchanged
restored Claim.status                        per §51 (unchanged)
restored lifecycle_seq                       preserved
restored Claim.base_confidence               preserved
restored Evidence.strength                   preserved
restored Gap.severity                        preserved
restored RuleStats.*                         preserved
```

PR67-P03 must not run Rule firing, recompute Evidence strength,
re-infer lifecycle, or recompute effective confidence during
restore. This reaffirms the PR47 §39 frozen-internal posture.

§52 does not propose `schema_version 3` and does not reserve a
v2 → v3 migration slot.

---

## §9 Prohibited Automatic Repair

`§52.10` lists the forbidden behaviors. Highlights:

```
- no missing Claim / Evidence / Gap / Contradiction / Relation /
  Entity / Observation synthesis
- no orphan reference deletion to make the snapshot consistent
- no orphan index entry deletion
- no orphan resolved-contradiction deletion
- no orphan gap_resolutions deletion
- no Claim.status coercion
- no "1" / 1.0 / True / False / None counter coercion
- no negative-counter clamping to 0
- no silent counter increase to max(restored ID set)
- no counter reset to zero
- no input snapshot mutation
- no pre-existing Engine mutation
- no Rule firing during restore
- no Claim lifecycle re-inference
- no Evidence.strength / Gap.severity / effective confidence
  recomputation
- no partial restore + skipped invalid portion
- no exception-replaced-by-warning success path
```

---

## §10 PR67-P03 Entry Conditions

```
official title:           Snapshot Restore Integrity Enforcement
minimum scope:            Engine.from_snapshot() rejects every
                          §52.2 ~ §52.5 violation, plus §52.6
                          (§51 delegation), per §52.7 exception
                          policy, while preserving §52.9.
prohibited scope:         schema bump / new key / new public
                          symbol / new exception / new Engine
                          method (cap 40/18) / consumer validator
                          as framework public API / multi-violation
                          result object / silent KeyError leak /
                          lifecycle re-inference / Rule re-execution
counter integrity:        sub-clause of PR67-P03, not a separate
                          PR. PR67 keeps the name above.
closing condition:        every §52 invariant has a failing test
                          first, then passes; existing baseline
                          tests remain green; Engine 40 / 18,
                          ragcore.__all__ 48, snapshot v2, 18
                          top-level keys all unchanged; judgment
                          semantics delta = 0.
```

---

## §11 Structural and Behavior Invariants

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
```

### runtime behavior delta

```
0
```

### judgment semantics delta

```
0
```

### documentation contract delta

```
+ snapshot restore reference integrity defined
+ snapshot restore set / index integrity defined
+ RuleStats identity integrity defined
+ counter integrity defined
+ restore failure semantics defined
+ validation responsibility fixed at Engine.from_snapshot()
+ PR67-P03 entry conditions defined
+ valid migration / round-trip preservation explicit
+ prohibited automatic repair list explicit
+ conceptual violation label catalogue recorded
```

---

## §12 Regression Result

`pytest -q` on 220차 commit `4f2d524`:

```
1270 passed
```

Identical to the baseline at `main` `9926049`. Documentation-only
addition; no test was modified, no runtime file was modified.

---

## §13 Self-Review

```
[x] §52.1 ~ §52.6 use real snapshot key names and real internal
    attribute shapes (verified against ragcore/engine.py at
    main 9926049).
[x] §52 does NOT introduce an evidence.claim_id == claim_id
    requirement for contradictions (preserves runtime cross-claim
    freedom).
[x] §52 does NOT require Gap.claim_id ∈ claim_gap_refs[Gap.claim_id]
    (preserves PR4 §16 "first registering claim" meaning).
[x] §52 does NOT require rule_stats key ∈ rule_definitions keys
    (preserves advisory unregistered references).
[x] §52 declares Engine.from_snapshot() the final defender; no
    new public consumer-side validator API is introduced.
[x] §52 uses fail-fast with TypeError / ValueError; no new
    exception class; raw KeyError not part of contract surface.
[x] §52 does NOT propose schema_version 3.
[x] §52 preserves v1 -> v2 migration and v2 round-trip exactly.
[x] §52 prohibits all coercion (no string / float / bool -> int
    automatic conversion for status or counter).
[x] §52 prohibits Rule re-execution, Evidence re-evaluation,
    lifecycle re-inference, effective confidence recomputation.
[x] §52 conceptual violation labels are NOT declared as public
    symbols or runtime error codes.
[x] §52 explicitly excludes entities / observations / relations /
    claim_lifecycle_events cross-reference auditing from scope.
[x] PR66-P02 runtime behavior delta = 0; judgment semantics
    delta = 0; structural counts (Engine 40 / 18, ragcore.__all__
    48, snapshot v2, 18 top-level keys) all unchanged.
[x] PR67-P03 minimum scope and prohibited scope are unambiguous
    from §52.11.
```

---

## §14 Closing Position

PR66-P02 is closed when:

- 220차 `docs(contract)` adds §52.
- 221차 `docs(dev)` records this development record.

This PR is opened as draft; merge is part of the standard
closing sequence (review → ready → squash merge → main re-measure
→ branch cleanup). PR67-P03 enforcement is **not** auto-scheduled
by this PR and requires a separate directive entry.
