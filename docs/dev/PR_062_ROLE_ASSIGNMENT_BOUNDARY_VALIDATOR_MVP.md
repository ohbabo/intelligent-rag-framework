# PR62 — Role Assignment Boundary Validator MVP

Development record for the consumer-side boundary validator
introduced in PR #63 (branch
`feat/role-assignment-boundary-validator`).

```
base:                main 869ae24
                       (PR61: Minimal Consumer-Side Role
                        Assignment Example)
branch:              feat/role-assignment-boundary-validator
210차 commit:         bd2b86b
210-A commit:        bf117be
211차 commit:         (this record, docs/dev)
PR:                  #63
type:                consumer-side boundary validator + tests,
                     framework state doc-only
```

This record captures what the validator was locked to check,
what it was deliberately locked NOT to check, what boundary
gaps 210-A corrected after 210차, and the final verification
results that closed PR62. This record does not redesign PR62.

---

## §1 Purpose

PR62 adds a consumer-side boundary validator over the PR61
local illustrative role-assignment representation, plus 19
tests that lock the validator's scope.

Locks (verbatim):

```
The validator checks representational boundaries.
It does not determine whether a semantic role is correct.

Passing validation means structurally non-contradictory under
the PR61 local illustrative representation. It does not mean
true, verified, safe for execution, accepted by the Engine,
or suitable as a canonical schema.

The validator's minimum fields are local validation inputs.
They are not required framework fields for all consumers.
```

PR62 is not:

```
a semantic role correctness validator
an automatic role classifier
a role inference system
an adapter contract
an Engine integration
an LLM evaluator
a downstream authorization
a canonical framework schema
```

---

## §2 Baseline

```
base:                main 869ae24
baseline tests:      1183 passing
PR62 final tests:    1202 passing  (1183 + 19)
predecessor stack:   PR49 – PR61
```

210차 added the validator and 19 tests (commit bd2b86b). 210-A
corrected three boundary gaps (commit bf117be) without
introducing a new test method or a new violation code. 211차
adds this record. No other files are touched.

---

## §3 Files Changed

```
examples/role_assignment/role_assignment_validator.py
                                       +391 lines    (210차 add)
                                       +/- ~47 lines (210-A fix)
tests/test_role_assignment_validator.py
                                       +444 lines    (210차 add)
                                       +/- ~113 lines (210-A fix)
docs/dev/PR_062_ROLE_ASSIGNMENT_BOUNDARY_VALIDATOR_MVP.md
                                       this record   (211차)

ragcore source:                   0 bytes changed
PR61 example file:                unchanged
new tests:                        19  (test_01 ~ test_19)
new framework public symbols:     0
new Engine behavior:              0
```

Single new local public entry point inside the validator file.
No new framework or `ragcore` public symbol.

210차 commit: `bd2b86b feat(examples): add role assignment
boundary validator`.
210-A commit: `bf117be fix(examples): enforce role label
boundaries`.
211차 commit: this record.

---

## §4 Local Representation Boundary

The validator targets the local PR61 illustrative
representation. Its required keys are local validation inputs,
not framework-required fields.

Local minimum top-level fields (checked for presence and
shape):

```
data_item / provenance / record_shape /
interpretation_context / assignment_basis /
primary_role / secondary_roles /
allowed_uses / forbidden_uses / traceability
```

Properties of this list:

```
local validation input only
unknown additional top-level keys are accepted
no exact closed-key schema is enforced
no canonical framework payload is defined
other consumers may represent the policy differently
```

The private constant is named `_LOCAL_REQUIRED_KEYS` to mark
its scope. It is not exposed and is not named "framework
required fields" or "canonical schema".

---

## §5 Public Entry Point

Exactly one local public function:

```python
def validate_role_assignment_boundaries(
    assignment: object,
) -> list[tuple[str, str]]:
    ...
```

Contract:

```
returns []                                no detected violation
returns [(code, message), ...]            one or more findings
```

Invariants:

```
NEVER raises (as a code contract; see §11 for the verified
                                    scope of this property)
NEVER mutates the input
deterministic ordering
returns ALL independently-detected violations
```

The signature itself is locked by AST inspection in test 19
(see §17): arg name `assignment`, annotation `object`, return
`list[tuple[str, str]]`, exactly one positional argument, no
posonly / kwonly / vararg / kwarg / defaults.

Module-level surface:

```
local public entry points:             1
framework / ragcore public symbols:    0
package exports:                       0
ragcore.__all__ additions:             0
__all__:                               not defined
__init__.py:                           not added
```

---

## §6 Violation Codes RA1 – RA10

```
RA1   top-level assignment is not a plain dict
RA2   required local boundary field is missing
RA3   container/scalar shape for present required fields
        dict      data_item / provenance /
                  interpretation_context / traceability
        non-empty string
                  record_shape / assignment_basis
        list      secondary_roles
RA4   primary_role must be None or a non-empty string
        (empty string included as RA4)
RA5   role-bearing label shape / prefix / suffix
        primary_role prefix gap
        secondary_roles[i].label non-string / empty /
                                  prefix gap / whitespace suffix
        candidate_roles[i] non-string / empty /
                            prefix gap / whitespace suffix
RA6   secondary boundary entry malformed
        entry not dict
        secondary required field missing
        explanatory field malformed
RA7   AllowedUse / ForbiddenUse list shape
        list-of-non-empty-string check
        ForbiddenUse explicit non-empty list
        scope: top-level and each secondary entry
RA8   exact normalized AllowedUse / ForbiddenUse overlap
        normalization: strip / collapse whitespace / casefold
        scope: top-level and each secondary entry
RA9   resolved / unresolved structural conflicts
        A   primary_role string + candidate_roles non-empty
        B   primary_role None + secondary_roles non-empty
        C   primary_role label == secondary_roles[i].label
        D   duplicate secondary role labels
RA10  candidate_roles container malformed or duplicates
```

`_CODE_ORDER = ("RA1","RA2","RA3","RA4","RA5","RA6","RA7","RA8","RA9","RA10")`
is a tuple so that bucket assembly preserves RA1 < RA2 < ... <
RA10 without depending on string sort (which would order
`"RA10"` before `"RA2"`).

---

## §7 Code Ownership and Cascade Suppression

Code ownership (no single defect produces duplicate codes):

```
secondary entry non-dict                  RA6
secondary label missing                   RA6
secondary label present-but-invalid       RA5
secondary explanatory invalid             RA6
secondary use-list invalid                RA7
candidate_roles non-list                  RA10
candidate item non-string / empty         RA5
candidate item missing 'example:' prefix  RA5
```

Cascade suppression (parent failure does not synthesize
descendant findings):

```
missing top-level field           -> RA2 only
secondary_roles non-list          -> RA3 only
                                     (child secondary checks
                                      skipped)
secondary entry non-dict          -> RA6 only
                                     (label / use checks on
                                      that entry skipped)
use-list non-list                 -> RA7 only
                                     (RA8 overlap skipped)
candidate_roles non-list          -> RA10 only
                                     (per-item / duplicate
                                      checks skipped)
```

Single-defect ownership control verified in test 7:

```
secondary_roles[0].label = 123
-> validate(...) returns exactly [("RA5", ...)]
```

When a structure carries multiple independent defects, the
result contains one finding per independent defect, ordered
by `_CODE_ORDER` and then by fixed-tuple field order and list
index.

---

## §8 Role-Bearing Field Boundary

Role-bearing positions (exactly three):

```
primary_role
secondary_roles[*].label
candidate_roles[*]
```

Local validity rules:

```
non-empty string
starts with "example:"
the substring after "example:" strips to a non-empty suffix
```

Valid local labels:

```
example:x
example:observation
example:knowledge-reference
example:candidate-statement
```

Rejected by RA5:

```
empty string / whitespace-only string
non-string values (None / int / bool / list / dict / ...)
"observation"   (no prefix)
"example:"      (prefix-only)
"example: "     (prefix + whitespace suffix)
"example:     " (prefix + whitespace suffix)
```

Non-role-bearing positions (the example: prefix is NOT
enforced):

```
record_shape
provenance.source_type
traceability values
data_item identifiers
```

Test 8 locks this asymmetry: when `record_shape` and
`provenance.source_type` are set to bare strings without the
`example:` prefix, validation returns `[]` (no RA5 emitted).

---

## §9 Resolved / Unresolved Structural Conflicts

`RA9` is reserved for mechanically observable conflicts.
Test 17 covers all four:

```
Conflict A  primary_role string + candidate_roles non-empty
            "resolved primary choice coexists with competing
             candidate slate"

Conflict B  primary_role None + secondary_roles non-empty
            "primary ambiguity routed around via secondary
             roles"

Conflict C  primary_role label == any secondary role label
            "primary and secondary not distinguished even at
             label level"

Conflict D  duplicate secondary role labels
            "same secondary interpretation appears more than
             once"
```

`RA9` is not used for semantic disagreement, paraphrased
contradiction, or natural-language inconsistency.

---

## §10 AllowedUse / ForbiddenUse Exact-Conflict Boundary

`RA8` is exact normalized string overlap.

Normalization:

```
strip leading/trailing whitespace
collapse repeated whitespace
casefold
```

Scope:

```
top-level allowed_uses vs forbidden_uses
each secondary entry's allowed_uses vs forbidden_uses
```

`RA8` does NOT detect:

```
synonyms
paraphrases
logical implication
natural-language contradiction
```

`RA8` is intentionally not labeled "semantic conflict
detection". The exact term is "exact normalized string
overlap".

---

## §11 Free-Text Non-Semantic Boundary

Several fields carry free-text local content that the
validator does not interpret:

```
data_item.content_summary
interpretation_context.question
assignment_basis
secondary explanatory fields
resolution_note
traceability summaries
each entry inside allowed_uses / forbidden_uses
```

The validator checks only that these fields are present in
the expected container shape and are non-empty strings where
required. It performs no meaning analysis.

Test 18 locks this by replacing the free-text payloads on a
valid resolved example with arbitrary alternative strings and
asserting that validation still returns `[]`.

Verification phrasing:

```
The entry point is designed not to raise and returns RA1 for
the tested non-dict input shapes. Malformed structures
covered by the PR62 test matrix return findings rather than
raising.
```

The code-contract phrase `NEVER raises` documents intent; the
verified behavior is bounded by the test matrix in §13.

---

## §12 Never-Raise / Non-Mutation / Deterministic Ordering

Test 3 covers 12 non-dict input shapes:

```
None / 0 / 1 / 1.5 / "string" / b"bytes" /
[1, 2] / (1, 2) / True / False / set() / frozenset()
```

For each tested shape, `validate(...)` returns
`[("RA1", "assignment is not a plain dict")]` without raising.

Test 18 covers non-mutation and determinism:

```
snapshot = deepcopy(RESOLVED)
original = deepcopy(RESOLVED)
_ = validate(original)
assert original == snapshot              # no mutation

r1 = validate(deepcopy(RESOLVED))
r2 = validate(deepcopy(RESOLVED))
assert r1 == r2                          # deterministic

d_bad = deepcopy(RESOLVED); del d_bad["primary_role"]
r1b = validate(deepcopy(d_bad))
r2b = validate(deepcopy(d_bad))
assert r1b == r2b                        # deterministic
                                          # for failing case
```

Ordering is guaranteed by:

```
_CODE_ORDER as a tuple (not sorted strings)
fixed-tuple field iteration order
list index iteration
sorted(...) applied to overlap set output before emission
```

---

## §13 210-A Correction Record

210-A (commit `bf117be`) closed three boundary gaps that the
210차 implementation left open:

```
Gap 1  Public entry-point signature was unannotated.

        Before: def validate_role_assignment_boundaries(assignment):
        After:  def validate_role_assignment_boundaries(
                    assignment: object,
                ) -> list[tuple[str, str]]:

Gap 2  secondary_roles[*].label shape was not enforced when
        the value was non-string or empty. Such labels passed
        through RA5 silently, and the missing-field-only RA6
        path did not catch them either.

        After: present-but-invalid secondary label triggers
        RA5 only (no RA5/RA6 duplicate). Test 7 verifies
        secondary label = 123 -> codes == ["RA5"].

Gap 3  _has_example_prefix() accepted prefix-only strings
        whose local suffix was whitespace.

        Before: return value.startswith(PREFIX) and
                len(value) > len(PREFIX)
        After:  return (
                    value.startswith(PREFIX)
                    and value[len(PREFIX):].strip() != ""
                )

        Cases now rejected: "example:" / "example: " /
        "example:   " / "example:        ".
```

No new test method, no new violation code, no new public
symbol. Test 7 was extended in-place; test 19 added an AST
signature lock. PR61 example and `ragcore/*` were not
modified.

Manual verification of Gap 2 ownership (recorded inline):

```
deepcopy(RESOLVED)["secondary_roles"][0]["label"] = 123
-> codes == ["RA5"]
```

Manual verification of Gap 3 across all three role-bearing
positions (recorded inline):

```
primary_role  = "example:   " -> codes includes "RA5"
secondary lbl = "example:   " -> codes includes "RA5"
candidate[0]  = "example:   " -> codes includes "RA5"
```

---

## §14 Runtime Dependency Boundary

The validator file does not import the PR61 example module
at runtime.

```
ragcore imports                       0
PR61 example runtime imports          0
  (no "minimal_consumer_example" name reference)
total imports in validator            0
```

The tests load both files via `importlib.util` with absolute
paths. No package is promoted. No `__init__.py` is added. No
`sys.path` mutation occurs.

`examples/role_assignment/` remains a plain directory with
two files plus the auto-generated `__pycache__/` (gitignored)
and no `__init__.py`.

---

## §15 Ragcore / Engine Non-Integration

The validator does not perform any of the following:

```
add evidence
create Claim
resolve Gap
register Rule
change Claim status
change effective confidence
modify snapshot
create final finding
execute tools
authorize downstream transition
```

Boundary audits (post-211 record):

```
ragcore source delta (vs 869ae24)        0 bytes
Engine public methods                    40 (AST)
Engine private methods                   18 (AST)
ragcore.__all__                          48
snapshot schema_version                  2
snapshot top-level keys                  18
proposal pipeline (PR51 – PR58)          unchanged
operator gate (PR57)                     unchanged
Engine judgment semantics                unchanged
```

Lock honored:

```
The validator returns consumer-side structural findings only.
```

---

## §16 Tests and Verification

Test method count: exactly 19 (no pytest parameterization,
no dynamic test generation).

```
test_01_resolved_example_returns_empty
test_02_unresolved_example_returns_empty
test_03_non_dict_inputs_never_raise_and_return_ra1
test_04_missing_required_keys_return_ra2
test_05_invalid_container_or_scalar_shapes_return_ra3
test_06_invalid_primary_role_shapes_return_ra4
test_07_role_bearing_labels_require_example_prefix
test_08_record_shape_and_source_type_are_not_role_labels
test_09_malformed_candidate_roles_container_returns_ra10
test_10_duplicate_candidate_labels_return_ra10
test_11_missing_secondary_boundary_fields_return_ra6
test_12_invalid_secondary_explanatory_fields_return_ra6
test_13_top_level_use_lists_return_ra7
test_14_secondary_use_lists_return_ra7
test_15_top_level_use_overlap_returns_ra8
test_16_secondary_use_overlap_returns_ra8
test_17_resolved_unresolved_structural_conflicts_return_ra9
test_18_extra_keys_free_text_no_mutation_deterministic
test_19_ast_boundary_audit
```

Final results:

```
py_compile                              OK
targeted pytest                         19 passing in 0.03s
full pytest                             1202 passing in 0.81s
                                          (= 1183 baseline + 19)
```

---

## §17 AST Boundary Audit (Test 19)

Test 19 parses the validator source and asserts:

```
no `import ragcore` / `from ragcore`
no runtime import of the PR61 example module
no class definitions
no forbidden type-construct names anywhere in AST
  (dataclass / Enum / TypedDict / NamedTuple /
   Protocol / BaseModel / pydantic)
exactly one non-private function definition:
  validate_role_assignment_boundaries

public function signature:
  exactly one positional argument named "assignment"
  argument annotation `object`
  return annotation `list[tuple[str, str]]`
  no posonly / kwonly / vararg / kwarg / defaults
```

This lock prevents future drift such as silent return-type
widening, hidden positional parameters, or implicit kwargs.

---

## §18 Domain-Neutrality Audit

Audited vocabulary, word-boundary, case-insensitive, over the
entire file content (module docstrings, comments,
identifiers, string literals, test data, test docstrings):

```
cerberus / cve / cpe / kev / nvd / epss / openssh
vulnerability / exploit / scanner / nmap
host / port / service / asset / forensic
```

Result:

```
examples/role_assignment/role_assignment_validator.py     0 / 16
tests/test_role_assignment_validator.py                   0 / 16
docs/dev/PR_062_ROLE_ASSIGNMENT_BOUNDARY_VALIDATOR_MVP.md  0 / 16
```

The validator does not test domain-specific positive or
negative cases. PR62 is a generic local-representation
boundary validator.

---

## §19 Out-of-Scope Confirmation

PR62 does not perform:

```
ragcore source modification
Engine modification
framework public symbol addition
package export
__init__.py addition
PR61 example modification
architecture spec modification
canonical schema definition
closed exact-key schema
automatic role classifier
role inference
role ranking
candidate selection
semantic role correctness judgment
provenance verification
assignment-basis truth verification
free-text semantic analysis
LLM evaluation
numerical confidence
probability
role registry
domain mapping
adapter implementation
retrieval implementation
packet schema change
proposal schema change
existing validator modification
external adapter application
```

---

## §20 Future Handoff Boundary

PR62 may enable later work but does not schedule any.

Possible follow-ups, each requiring its own explicit entry
directive:

```
external adapter application
additional consumer-side guidance or examples
deeper validator scope extension (NOT auto-entered;
  semantic checks remain out of scope by current locks)
Engine integration path (NOT auto-entered; depends on
  cerberus-side adapter contract, not on PR62)
```

None of the above are auto-entered by the merging of PR62.

---

## §21 Final Result

```
PR59 separated the interpretation axes.

PR60 defined contextual role-assignment policy.

PR61 demonstrated one local resolved and unresolved consumer
representation.

PR62 added a local boundary validator that rejects
mechanically malformed or exactly contradictory
representations.

It does not determine semantic truth, choose a role,
or create downstream authority.
```

After merge, the framework re-enters a waits state. External
adapter application, any deeper validator extension, and any
Engine integration path each require their own explicit
entry directives.
