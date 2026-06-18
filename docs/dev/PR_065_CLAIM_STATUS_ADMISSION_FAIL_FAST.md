# PR65-P01 — Claim Status Admission Fail-Fast

Development record for the Claim.status admission gate
introduced in PR65-P01 (branch `fix/claim-status-admission`).

```
base:            main 965b6f7 (PR64: Minimal Domain-Neutral
                                External Adapter Example)
branch:          fix/claim-status-admission
216차 commit:    23a0d7c   docs(contract)
217차 commit:    1f90c5f   test(core)
218차 commit:    df9845b   fix(engine)
219차 commit:    (this record, docs/dev)
type:            framework-level runtime invariant correction,
                  doc + test + minimal engine change
```

This record captures the admission gate the Engine enforces for
`Claim.status`, the relationship to the existing status modifier
dict, the four-commit cycle, the verification results, and the
closing position of PR65-P01. It does not redesign §51.

---

## §1 Purpose

`Claim.status` is one of the four fields whose meaning is locked
by `_STATUS_TO_MODIFIER` (PR11-D §24): each of the four registered
constants maps to a status modifier used inside effective
confidence. Before PR65-P01, an invalid status entered Engine
state silently and surfaced only at status-modifier lookup time
(KeyError from `_STATUS_TO_MODIFIER[claim.status]`). Two
admission paths were affected:

- `Engine.add_claim(status=...)` accepted any integer (and any
  bool, since `bool` is an int subclass).
- `Engine.from_snapshot(snapshot)` accepted a `claims` entry
  with any value in its `status` field.

PR65-P01 closes both admission paths so that an invalid
`Claim.status` never enters Engine state. The failure surfaces at
the admission boundary rather than at a later computation that
expected a registered status.

PR65-P01 introduces no Engine method, no public symbol, no new
dependency, no schema change, and no judgment semantics change.

---

## §2 Baseline

```
base:                       main 965b6f7 (PR64)
baseline tests:             1202 passing
predecessor stack:          PR49 – PR64
Engine public methods:      40
Engine private methods:     18
ragcore.__all__:            48
snapshot schema_version:    2
```

216차 added §51 to `docs/contracts/05_DATA_CONTRACT_MVP.md`
(`+208` lines). 217차 added the test module. 218차 added the
minimal Engine validator. 219차 adds this record. No other files
are touched.

---

## §3 Files Changed

```
docs/contracts/05_DATA_CONTRACT_MVP.md
                                            +208 lines    (216차)
tests/test_engine_claim_status_admission.py
                                            +310 lines    (217차)
ragcore/engine.py
                                             +37 lines    (218차)
docs/dev/PR_065_CLAIM_STATUS_ADMISSION_FAIL_FAST.md
                                            this record   (219차)

ragcore source delta:         +37 lines, 0 removed
tests added:                  68
framework public symbols:     0 added
Engine behavior:              admission gate only (no semantics
                                change downstream)
example source files:         0 added
```

---

## §4 Contract — §51 added

§51 closes the admission domain for `Claim.status`. Key clauses:

```
§51.1   admissible set is the four registered status constants
§51.2   exact-int requirement; bool and float are rejected
§51.3   add_claim rejects before any state mutation
§51.4   from_snapshot rejects an invalid claim entry
§51.5   error type convention follows PR21-L §33 / PR34-O §46:
          TypeError for non-int / bool / None / str / float
          ValueError for out-of-range int
§51.6   explicit non-goals (lifecycle / modifiers / formula /
          schema / public surface / cross-reference checks)
§51.7   test expectation table
```

§51 does not change the integer values of the four constants
and does not change their lifecycle semantics. §51 does not
introduce a new exception class.

---

## §5 Tests Added

`tests/test_engine_claim_status_admission.py` (310 lines, 68
test methods, all parametrized over two invalid catalogues plus
the four valid constants).

```
TestAddClaimRejectsInvalidStatusType            9   (TypeError)
TestAddClaimRejectsInvalidStatusValue           3   (ValueError)
TestAddClaimRejectionDoesNotMutateState
  test_snapshot_unchanged                      12
  test_next_claim_id_not_consumed              12
TestAddClaimAdmitsValidStatuses                 4
TestFromSnapshotRejectsInvalidStatusType        9   (TypeError)
TestFromSnapshotRejectsInvalidStatusValue       3   (ValueError)
TestFromSnapshotDoesNotMutateInput             12
TestFromSnapshotValidRoundTrip                  4
                                              ---
                                               68
```

Invalid-status catalogues:

```
INVALID_STATUS_TYPE_VALUES                (TypeError)
  True / False / "candidate" / "1" / None /
  0.0 / 1.0 / 3.0 / 999.0

INVALID_STATUS_VALUE_INTS                 (ValueError)
  -1 / 4 / 999
```

Mutation safety asserted by comparing `engine.to_snapshot()`
before and after the rejected call, and by registering a valid
claim before the rejection and another after — the second valid
claim must receive the next sequential ID (rejection does not
consume the claim counter).

Snapshot restore tests deep-copy the input dictionary, mutate
the single claim's status, deep-copy the mutated snapshot once
more, attempt `Engine.from_snapshot`, and assert the snapshot
that was passed to the call remains structurally equal to the
pre-call copy.

Expected state before 218차 implementation landed:

```
60 invalid-status tests   FAIL  (no admission gate)
 8 valid-status tests     PASS  (already supported)
```

Verification on 217차 commit `1f90c5f` confirmed the exact split
above before 218차 was added.

---

## §6 Implementation

`ragcore/engine.py` changes (`+37` lines, 0 removed):

```
+ _VALID_CLAIM_STATUSES = frozenset(_STATUS_TO_MODIFIER)
+ def _validate_claim_status_admission(value: object) -> None:
      ...

  def add_claim(self, ..., status=CLAIM_STATUS_CANDIDATE, ...):
      ...
      if subject_id not in self._entities:
          raise KeyError(...)
+     _validate_claim_status_admission(status)
      claim_id = self._allocate_id("claim")
      ...

  @classmethod
  def from_snapshot(cls, snapshot):
      ...
      snapshot = _migrate_snapshot_to_current(snapshot)
+     for _item in snapshot.get("claims", []):
+         _validate_claim_status_admission(_item["value"]["status"])
      engine = cls()
      ...
```

### bool rejection

```python
if isinstance(value, bool) or type(value) is not int:
    raise TypeError(...)
```

`isinstance(True, int)` is `True` in Python (bool is an int
subclass). The explicit `isinstance(value, bool)` guard rejects
both `True` and `False`. `type(value) is not int` rejects float,
str, None, and any other non-int type without admitting any
non-bool int subclass.

### float rejection

`type(value) is not int` is `True` for any float, including
floats that compare equal to a status constant (`1.0 == 1`). No
silent coercion is performed.

### value range

After the type check, `value not in _VALID_CLAIM_STATUSES`
raises `ValueError`. The valid set is derived from
`_STATUS_TO_MODIFIER` so the two cannot drift apart in the
future.

### fail-before-mutation guarantee

In `add_claim` the validator runs after the (read-only)
`subject_id` membership check and before `_allocate_id("claim")`
and the `self._claims[...]` insertion. A rejected call performs
no Engine state mutation.

In `from_snapshot` the validator iterates `snapshot["claims"]`
after `_migrate_snapshot_to_current` returns its (shallow-copied)
migrated dict and before `engine = cls()` is constructed. An
invalid snapshot never produces a partially restored Engine.

### no new method

Both the constant and the helper live at module level. No new
Engine method (public or private). No new entry in
`ragcore.__all__`.

---

## §7 Structural and Behavior Invariants

```
Engine public methods                40         (unchanged)
Engine private methods               18         (unchanged)
ragcore.__all__                      48         (unchanged)
snapshot schema_version              2          (unchanged)
snapshot top-level keys              identical  (unchanged)

new public symbol                    0
new Engine method                    0
new dependency                       0

CLAIM_STATUS_CANDIDATE value         0          (unchanged)
CLAIM_STATUS_CONFIRMED value         1          (unchanged)
CLAIM_STATUS_REFUTED  value          2          (unchanged)
CLAIM_STATUS_DISPUTED value          3          (unchanged)

status modifier values               unchanged
freshness modifier                   unchanged
gap modifier                         unchanged
count modifier                       unchanged
rule_stats modifier                  unchanged
evidence_type modifier               unchanged
effective confidence formula         unchanged

Claim dataclass shape                unchanged
public Engine method signatures      unchanged
```

### judgment semantics delta

```
0
```

### runtime invariant delta

```
- invalid Claim.status admission via Engine.add_claim() blocked
- invalid Claim.status restore via Engine.from_snapshot() blocked
- bool / float / None / str / out-of-range int coercion blocked
- failure-before-mutation guaranteed (counter not consumed,
  Engine state unchanged on rejection)
```

---

## §8 Regression Result

```
existing tests       1202   passing  (unchanged)
new tests              68   passing
total                1270   passing
```

`pytest -q` on 218차 commit `df9845b`:

```
1270 passed
```

`pytest -q` on the prior 217차 commit `1f90c5f` (tests-only,
before implementation):

```
60 failed, 8 passed   (in the new test module)
1202 passed elsewhere
```

The 60 / 8 split matches the §51.7 test expectation. No existing
test was modified.

---

## §9 Self-Review

```
[x] contract / test / implementation match
    §51.1 .. §51.5 each have a corresponding test class and
    each test class is satisfied by the 218차 implementation.

[x] no scope creep
    No change to lifecycle, modifiers, confidence formula,
    snapshot schema, public surface, or any vocabulary
    outside Claim.status admission.

[x] no automatic coercion
    "1" -> 1, 1.0 -> 1, True -> 1, False -> 0 all rejected.

[x] no automatic recovery
    Invalid snapshot claim entries are not dropped, replaced,
    or rewritten; from_snapshot raises before any state is
    restored.

[x] docs match runtime
    Error types in §51.5 match the runtime raises
    (TypeError for non-int / bool; ValueError for
    out-of-range int).

[x] no new public surface
    ragcore.__all__ length unchanged at 48; no new Engine
    method (public or private); Engine 40 / 18 unchanged.

[x] snapshot shape unchanged
    schema_version still 2; top-level keys identical.

[x] non-goals preserved
    no orphan-reference check, no set-inclusion check, no
    counter integrity check at restore (out of scope; tracked
    for PR66-P02 / PR67-P03 if pursued).
```

---

## §10 Closing Position

PR65-P01 is closed when:

- 216차 `docs(contract)` adds §51.
- 217차 `test(core)` adds the 68 test methods.
- 218차 `fix(engine)` adds the minimal admission validator.
- 219차 `docs(dev)` records this development record.

This PR is opened as draft; merge is not part of PR65-P01. The
follow-up PRs (PR66-P02 orphan reference and PR67-P03 counter
integrity) are NOT auto-scheduled by this PR and require
separate directive entry.
