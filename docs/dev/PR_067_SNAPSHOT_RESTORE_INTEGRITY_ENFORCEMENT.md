# PR67-P03 — Snapshot Restore Integrity Enforcement

Development record for the §52 enforcement landed by PR67-P03
(branch `fix/snapshot-restore-integrity`).

```
base:            main 6da2095 (PR66-P02: Snapshot Restore
                                Integrity Contract)
branch:          fix/snapshot-restore-integrity
222차 commit:    f9a9810   test(core)
223차 commit:    f2c569b   fix(engine)
224차 commit:    (this record, docs/dev)
type:            framework-level runtime invariant enforcement,
                  test + minimal engine change + dev record
```

This record captures the runtime gap that §52 left enforceable,
the §52 sub-section ↔ test class mapping, the pre-implementation
measurement, the minimal implementation (single pre-validator +
two small helpers), the validation timing, the exception
taxonomy, the raw-`KeyError` conversion path, the four
intentional semantic preservations, the structural invariants,
and the closing position of PR67-P03.

---

## §1 Purpose

PR65-P01 §51 closed `Claim.status` admission. PR66-P02 §52 then
defined every cross-reference / set / index / RuleStats identity
/ counter invariant the Engine must defend at restore time, but
explicitly deferred implementation to PR67-P03.

PR67-P03 closes that gap. After this PR:

- `Engine.from_snapshot()` is the **final** invariant defender
  (§52.8).
- An invalid snapshot raises before any Engine state is created.
- The input snapshot is never mutated; the caller never sees a
  partial Engine.
- A bare `KeyError` from a private restore helper is no longer
  part of the contract surface (§52.7).
- The four intentional semantic preservations from §52 (cross-
  claim contradiction freedom; gap dedup component back-
  validation deliberately omitted; advisory unregistered
  RuleStats identity; `Gap.claim_id` as "first registering
  claim") all hold.

PR67-P03 does not change snapshot schema, does not add a public
symbol, does not add an Engine method, does not add a new
exception class, and does not introduce a domain vocabulary.

---

## §2 Baseline

```
base:                       main 6da2095
                              (PR66-P02: Snapshot Restore
                               Integrity Contract)
baseline tests:             1270 passing
predecessor stack:          PR49 – PR66-P02
Engine public methods:      40
Engine private methods:     18
ragcore.__all__:            48
snapshot schema_version:    2
snapshot top-level keys:    18
```

222차 added `tests/test_snapshot_restore_integrity.py` (`+630`
lines, 94 test methods). 223차 added the minimal pre-validator
in `ragcore/engine.py` (`+343` lines, 0 removed). 224차 adds
this record.

---

## §3 Files Changed

```
tests/test_snapshot_restore_integrity.py
                                              +630 lines   (222차, new)
ragcore/engine.py
                                              +343 / -1 lines   (223차)
docs/dev/PR_067_SNAPSHOT_RESTORE_INTEGRITY_ENFORCEMENT.md
                                              this record  (224차, new)

framework public symbols:     0 added
Engine public methods:        unchanged at 40
Engine private methods:       unchanged at 18
new dependencies:             0
new exception classes:        0
example source files:         0 added
```

---

## §4 Pre-Implementation Probe

The current Engine at `main` `6da2095` was probed directly
against §52 invariants to confirm the gap. Empirical results:

```
ORPHAN evidence claim_id                  silently accepted
ORPHAN contradiction claim_id             silently accepted
counter below max restored                silently accepted
RuleStats key with bool                   silently accepted
missing top-level key 'evidences'         raw KeyError('evidences')
```

The first four cases match §52.2 ~ §52.5 invariants; the fifth
is the §52.7 raw-`KeyError` contract surface gap. PR67-P03
closes all five.

---

## §5 §52 Contract Mapping

`tests/test_snapshot_restore_integrity.py` test classes ↔ §52
sub-sections:

```
§52.2.1  Evidence -> Claim            TestEvidenceClaimOrphan
§52.2.2  Contradiction -> Claim       TestContradictionClaimOrphan
         Contradiction -> Evidence    TestContradictionEvidenceOrphan
         cross-claim freedom          TestContradictionCrossClaimFreedom
                                        Preserved
§52.2.3  Claim-gap -> Claim           TestClaimGapClaimOrphan
         Claim-gap -> Gap             TestClaimGapGapOrphan
         Gap.claim_id first-reg       TestGapClaimIdFirstRegistering
                                        Preserved
§52.2.4  Gap resolution refs          TestGapResolutionGapOrphan
                                      TestGapResolutionEvidenceOrphan
§52.3.1  gap_dedup key shape          TestGapDedupKeyShape
         gap_dedup target              TestGapDedupTargetOrphan
§52.3.2  resolved subset rule          TestResolvedContradictionSubset
§52.4    RuleStats identity shape      TestRuleStatsIdentityShape
         advisory unregistered         TestRuleStatsAdvisoryUnregistered
                                        Preserved
§52.5    counter type                  TestCounterType
         counter value (negative)      TestCounterValue
         counter collision relation    TestCounterCollisionRelation
         missing kind rule             TestCounterMissingKind
         sparse IDs admitted           TestCounterSparseIdsAdmitted
§52.6    Claim.status (§51)            TestClaimStatusLinkageUnchanged
§52.7    raw KeyError forbidden        TestNoRawKeyErrorOnContractSurface
§52.9    v2 round-trip                 TestValidRoundTripPreserved
         v1 migration                  TestV1MigrationPreserved
structural smoke                       TestStructuralInvariantsUnchanged
```

Total new tests: **94**.

---

## §6 Pre-Implementation Test Result

Measured on 222차 commit `f9a9810` (test-only):

```
total new test cases             94
expected failures (§52 absent)   57
already passing                  37
unexpected failures               0
raw KeyError surfacing           16 (matches §52.7 gap exactly)
wrong-exception failures          0
silent-acceptance failures        0
```

Existing 1270 tests remained green throughout the test-only
commit.

Already-passing positive cases on 222차:

```
contradiction cross-claim freedom round-trip
shared Gap dedup hit (Gap.claim_id != claim_gap_refs key)
advisory unregistered RuleStats round-trip
empty resolved set admitted
counter == max restored
counter > max restored
sparse IDs round-trip
all four CLAIM_STATUS_* round-trip
empty engine round-trip
v1 -> v2 migration round-trip
missing / unsupported schema_version (PR21-L preserved)
Claim.status invalid cases (PR65-P01 already enforces)
Engine 40 / 18, __all__ 48, schema v2, 18 keys
```

---

## §7 Implementation

`ragcore/engine.py` (`+343` lines, 0 removed; module-level
additions only):

```
_SNAPSHOT_REQUIRED_KEYS         tuple[str, ...] of 18 keys
_COUNTER_KIND_TO_COLLECTION     dict (kept for clarity; the active
                                  cross-check uses an inline mapping
                                  inside the validator)

_exact_int(value)                     gate consistent with §51.2
                                       (rejects bool via isinstance
                                        + type(value) is int)
_collect_id_set(snapshot, name)       returns the key set after
                                       structural type/shape checks
                                       (TypeError for non-list /
                                        non-dict; ValueError for
                                        missing 'key'/'value')
_validate_snapshot_restore_integrity(snapshot)
                                      single fail-fast pass over
                                       §52.1 ~ §52.5 / §52.7
                                       contract surface
```

No new Engine method (public or private). The Engine class body
is unchanged. The `_SNAPSHOT_REQUIRED_KEYS` constant and the
three helpers live at module level and are NOT exported.

### §7.1 Validation timing

`Engine.from_snapshot()` body order:

```
1. isinstance(snapshot, dict) guard       (§52.7 — prevents
                                              AttributeError from
                                              _migrate_snapshot_to_current
                                              when caller passes a non-dict)
2. _migrate_snapshot_to_current(snapshot) (PR18-K §30 unchanged —
                                              raises ValueError for
                                              missing / unsupported
                                              schema_version)
3. _validate_snapshot_restore_integrity   (§52.1 ~ §52.5 / §52.7)
4. _validate_claim_status_admission       (§51 / PR65-P01 unchanged)
5. engine = cls() + state population      (existing restore path
                                              unchanged)
```

Steps 1 – 4 run **before** `engine = cls()`, so a rejected
snapshot never produces an observable Engine.

Snapshot mutation is impossible because the validator only
reads via `__getitem__` / iteration; no assignment, `pop`, or
`del` is performed on `snapshot` or any of its nested values.
`_migrate_snapshot_to_current` already returns a shallow copy
(PR21-L §33).

### §7.2 Exception taxonomy

```
isinstance(snapshot, dict) failure         TypeError
missing required top-level key             ValueError
collection not a list                      TypeError
item not a dict                            TypeError
item missing 'key' or 'value'              ValueError
Evidence.claim_id orphan                   ValueError
contradiction.claim orphan                 ValueError
contradiction.evidence orphan              ValueError
contradiction bucket wrong type            TypeError
claim_gap_refs.claim orphan                ValueError
claim_gap_refs.gap orphan                  ValueError
claim_gap_refs bucket wrong type           TypeError
gap_resolutions.gap orphan                 ValueError
gap_resolutions.evidence orphan            ValueError
gap_dedup_index key not a 4-list           TypeError
gap_dedup_index key component non-int      TypeError
gap_dedup_index target orphan              ValueError
resolved_contradictions.claim orphan       ValueError
resolved_contradictions.claim not in       ValueError
  contradictions (bucket non-empty)
resolved_contradictions bucket wrong type  TypeError
resolved_contradictions value not in       ValueError
  contradictions[claim]
rule_stats key not a 2-list                TypeError
rule_stats key component non-int           TypeError
next_id not a dict                         TypeError
next_id[kind] non-int (bool/float/str/None) TypeError
next_id[kind] < 0                          ValueError
next_id[kind] < max restored               ValueError
next_id[kind] missing with restored > 0    ValueError
Claim.status delegated to §51              §51 policy (TypeError /
                                              ValueError)
unsupported / missing schema_version       ValueError (PR21-L §33
                                              unchanged)
```

No new exception class is introduced.

### §7.3 Raw KeyError conversion

Five known raw-`KeyError` surfaces are covered by the validator:

```
snapshot[<missing top-level key>]         ValueError
                                           (16 missing-key cases
                                            in TestNoRawKeyError...)
item["key"] / item["value"] missing       ValueError
item["value"]["claim_id"] missing         ValueError (for Evidence
                                                       entries; other
                                                       value dicts
                                                       fall through to
                                                       dataclass restorer
                                                       which already
                                                       raises TypeError)
non-dict item                             TypeError
non-list collection                       TypeError
```

The `TestNoRawKeyErrorOnContractSurface` test class asserts
`not isinstance(excinfo.value, KeyError)` for every missing-key
case, so any future regression on this surface is caught.

### §7.4 Validation timing — input snapshot immutability

`_assert_raises_and_input_unchanged` in the test file:

```python
def _assert_raises_and_input_unchanged(snapshot, expected_exc):
    before = copy.deepcopy(snapshot)
    with pytest.raises(expected_exc) as excinfo:
        Engine.from_snapshot(snapshot)
    assert snapshot == before, "input snapshot was mutated on rejection"
    return excinfo.value
```

Applied to every invalid-category test. All 57 §52 invariant
tests + 17 §52.7 raw-KeyError tests pass this immutability
assertion.

---

## §8 Intentional Semantic Preservation

The PR66-P02 directive flagged four semantic boundaries that
**must** survive the enforcement. All four are confirmed by
positive tests:

```
1. contradiction cross-claim freedom
   TestContradictionCrossClaimFreedomPreserved.
     test_cross_claim_contradiction_round_trip
   A contradiction whose evidence_id has a different Evidence.claim_id
   than the contradiction key claim_id round-trips successfully.

2. gap_dedup key component back-validation NOT introduced
   §7 validator only enforces (a) 4-element list, (b) each
   component is a built-in int (bool excluded), (c) target gap_id
   resolves. It does not require key components to match any
   other collection (e.g. subject_id and rule_id remain
   caller-domain integers).

3. advisory unregistered RuleStats identity
   TestRuleStatsAdvisoryUnregisteredPreserved.
     test_rule_stats_without_matching_rule_definition_admitted
   A RuleStats key (777, 1) with no matching rule_definitions
   entry round-trips successfully.

4. Gap.claim_id "first registering claim" meaning
   TestGapClaimIdFirstRegisteringPreserved.
     test_shared_gap_dedup_creates_cross_claim_ref
   When two add_gap calls share the same dedup key, c2 obtains
   a reference to the existing gap; Gap.claim_id stays at c1
   (the first registering claim); restore preserves this.
```

---

## §9 Final Test Result

`pytest -q` on 223차 commit `f2c569b`:

```
1364 passed
```

```
existing tests          1270   passing  (unchanged from PR66 baseline)
new tests                 94   passing
total                   1364   passing
```

`pytest tests/test_snapshot_restore_integrity.py -q`:

```
94 passed
```

No existing test was modified. No fixture was modified.

---

## §10 Structural Invariants

```
Engine public methods            40   (unchanged, AST measured)
Engine private methods           18   (unchanged, AST measured)
ragcore.__all__                  48   (unchanged)
snapshot schema_version          2    (unchanged)
snapshot top-level keys          18   (unchanged)

new public symbol                0
new Engine method                0    (public or private)
new dependency                   0
new exception class              0

module-level additions (private only):
  _SNAPSHOT_REQUIRED_KEYS
  _COUNTER_KIND_TO_COLLECTION
  _exact_int
  _collect_id_set
  _validate_snapshot_restore_integrity
```

### runtime invariant delta

```
+ invalid snapshot references rejected (§52.2 / §52.3 / §52.4)
+ invalid counter type/value/collision rejected (§52.5)
+ invalid rule_stats identity shape rejected (§52.4)
+ invalid gap_dedup index shape / target rejected (§52.3.1)
+ resolved_contradictions ⊆ contradictions enforced (§52.3.2)
+ raw KeyError converted to TypeError / ValueError (§52.7)
+ non-dict snapshot rejected before migration (§52.7)
+ input snapshot mutation prohibited and verified (§52.10)
```

### judgment semantics delta

```
0
```

### snapshot schema delta

```
0
```

### lifecycle semantics delta

```
0
```

### effective confidence formula delta

```
0
```

---

## §11 §52 Prohibited-Scope Review

Each PR67 prohibition from §52.11 / §52.10 verified against the
final commit:

```
[x] no new snapshot schema_version            (still 2)
[x] no new top-level snapshot key             (still 18)
[x] no new ragcore public symbol              (__all__ still 48)
[x] no new public Engine method               (still 40)
[x] no new private Engine method              (still 18; additions
                                                 are module-level)
[x] no new dependency                         (imports unchanged)
[x] no new exception class                    (TypeError / ValueError
                                                 only)
[x] no domain-specific vocabulary             (validator messages
                                                 reference snapshot
                                                 keys and "Claim /
                                                 Evidence / Gap"
                                                 framework nouns only)
[x] no consumer-side validator declared as
    framework public API                      (zero added)
[x] no multi-violation result object          (fail-fast on first
                                                 violation)
[x] no silent dependency on dict[...]
    raising bare KeyError                     (TestNoRawKeyError
                                                 OnContractSurface
                                                 covers 16 missing-
                                                 key cases + non-dict
                                                 + non-list)
[x] no lifecycle re-inference                 (validator does not
                                                 touch ClaimLifecycleEvent
                                                 or status transitions)
[x] no Rule re-execution                      (validator does not call
                                                 fire_rule or compile_*)
[x] no change to Gap.claim_id meaning         (TestGapClaimIdFirstReg-
                                                 isteringPreserved)
[x] no removal of contradiction cross-claim
    freedom                                   (TestContradictionCross-
                                                 ClaimFreedomPreserved)
[x] no introduction of gap_dedup key
    component back-validation                 (validator only checks
                                                 4-list of ints; no
                                                 cross-collection check)
[x] no requirement that RuleStats keys match
    rule_definitions                          (TestRuleStatsAdvisory-
                                                 UnregisteredPreserved)
```

---

## §12 Self-Review

```
[x] §52 invariants and tests have 1:1 mapping (see §5).
[x] No test introduces a constraint stronger than §52.
[x] cross-claim contradiction NOT rejected.
[x] gap dedup key component back-validation NOT added.
[x] RuleStats key NOT restricted to registered rule_definitions.
[x] Gap.claim_id NOT reinterpreted as unique-owner Claim.
[x] missing-counter rule applied per §52.5:
      restored ID set empty  -> missing counter admitted.
      restored ID set > 0    -> missing counter raises ValueError.
[x] bool not accepted as counter int.
[x] raw KeyError never surfaces; TestNoRawKeyError... covers 16
    missing-key + non-dict + non-list cases.
[x] no automatic repair anywhere in the validator.
[x] input snapshot immutability asserted on every rejection path.
[x] no new Engine method (public or private).
[x] Engine 40 / 18 unchanged (AST measured).
[x] ragcore.__all__ 48 unchanged.
[x] schema_version 2 / 18 top-level keys unchanged.
[x] lifecycle, effective confidence formula, status modifiers all
    untouched.
[x] no consumer-side validator declared as a framework public
    symbol.
[x] no new exception class.
```

---

## §13 Closing Position

PR67-P03 is closed when:

- 222차 `test(core)` adds the 94 invariant tests.
- 223차 `fix(engine)` adds the minimal pre-validator.
- 224차 `docs(dev)` records this development record.

This PR is opened as draft; merge is not part of PR67-P03 per
the directive. Subsequent work (e.g. consumer-side validator,
multi-violation report) is **not** auto-scheduled by this PR and
requires a separate directive entry.

After merge, the P-series stack closes:

```
PR65-P01  Claim Status Admission Fail-Fast              CLOSED
PR66-P02  Snapshot Restore Integrity Contract           CLOSED
PR67-P03  Snapshot Restore Integrity Enforcement        ready
```
