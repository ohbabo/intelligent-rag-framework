# PR61 — Minimal Consumer-Side Role Assignment Example

Development record for the single-file consumer-side example
introduced in PR #62 (branch
`examples/minimal-role-assignment`).

```
base:            main d8d1450 (PR60: Role Assignment Policy Spec)
branch:          examples/minimal-role-assignment
208차 commit:     fab3924
209차 commit:     (this record, docs/dev)
PR:              #62
type:            consumer-side illustrative example, doc-only intent
```

This record captures the intent, the boundary, the two example
shapes, the semantic-role vs local-descriptor distinction, the
audit results, and the closing position that ended PR61. This
record does not redesign PR61.

---

## §1 Purpose

PR61 provides one local consumer representation of a role
assignment under the PR60 policy and the PR59 six axes. The
example shows the *result shape* of the PR60 procedure, not an
implementation.

PR61 is not:

```
a representation contract
a canonical dictionary shape
a required-keys list
a valid-role vocabulary
an automatic role assignment
a semantic-role correctness checker
a validator input schema
a framework public API
Engine state
```

Lock:

```
The example demonstrates policy boundaries.

It does not implement the policy as an authoritative
classification or validation system.
```

---

## §2 Baseline

```
base:                       main d8d1450
                              (PR60: Role Assignment Policy Spec)
baseline tests:             1183 passing
predecessor stack:          PR49–PR60 (proposal pipeline + data
                            access profile contract + role
                            assignment policy)
```

208차 added
`examples/role_assignment/minimal_consumer_example.py`
(`+206` lines). 209차 adds this record. No other files are
touched.

---

## §3 Files Changed

```
examples/role_assignment/minimal_consumer_example.py     +206  (208차)
docs/dev/PR_061_MINIMAL_CONSUMER_ROLE_ASSIGNMENT_EXAMPLE.md
                                                         this  (209차)

ragcore source:               0 bytes changed
tests:                        0 added
framework public symbols:     0 added
Engine behavior:              0 added
```

No `__init__.py`, no README, no JSON schema, no JSON fixtures, no
test files, no ragcore files were added or modified.

208차 commit: `fab3924 docs(examples): add minimal role assignment
example`.
209차 commit: this record.

---

## §4 Non-Normative Example Boundary

The example is a single Python file containing two module-level
dictionaries and one `__main__` block that prints them.

```
RESOLVED_EXAMPLE
UNRESOLVED_EXAMPLE
```

Both are local example data. They are not:

```
framework constants
a public role registry
canonical fixtures
validator payload definitions
a stable import API
```

Boundary check:

```
no __init__.py
no __all__
no package export
no ragcore re-export
no stable-import claim
```

The clause "new public symbols: 0" in PR61's verification refers to
*framework / ragcore public symbols*. Two Python module-level
variables exist inside the example file. They are local example
data and are not exposed to the framework surface.

---

## §5 Resolved Example

`RESOLVED_EXAMPLE` shows one possible representation of an
assignment whose context supports a single primary role.

Structural audit:

```
top-level keys (10):
  data_item / provenance / record_shape /
  interpretation_context / assignment_basis /
  primary_role / secondary_roles /
  allowed_uses / forbidden_uses / traceability

interpretation_context.question:                  present
primary_role:                                     "example:observation"
secondary_roles[0] PR60 6-condition coverage:
  justification                                   present
  meaning_distinct_from_primary                   present
  allowed_uses                                    present
  forbidden_uses                                  present
  non_contradiction_with_primary                  present
  no_downstream_authorization                     present
allowed_uses count:                               4  (narrow,
                                                     non-executable)
forbidden_uses count:                             7  (all PR60
                                                     baseline risks)
traceability:                                     present
assignment_basis:                                 present
```

Read from this:

```
primary role is contextual          (ctx-review-0001)
primary role uses example: prefix   (example:observation)
secondary role is justified         (6 conditions present)
AllowedUse is narrow                (4 items, display / compare /
                                     explain / identify-missing)
ForbiddenUse covers baseline risks
  1. register as Engine evidence automatically
  2. create a registered Claim automatically
  3. resolve a Gap automatically
  4. change Claim lifecycle state as side effect
  5. execute a tool because role was assigned
  6. publish a final verdict from this assignment
  7. bypass operator review on this assignment
```

---

## §6 Unresolved Example

`UNRESOLVED_EXAMPLE` shows the same fragment (same
`data_item_id`) read in a different context where evidence does
not support a single primary role.

Structural audit:

```
top-level keys (13):
  data_item / provenance / record_shape /
  interpretation_context / assignment_basis /
  primary_role / candidate_roles / candidate_roles_note /
  secondary_roles / allowed_uses / forbidden_uses /
  resolution_note / traceability

primary_role:                                     None
candidate_roles count:                            2
                                                  (example:knowledge-
                                                   reference,
                                                   example:candidate-
                                                   statement)
candidate_roles_note:                             explicit local-data
                                                  caveat
secondary_roles:                                  []  (empty, no
                                                       forced add)
allowed_uses count:                               2  (narrower than
                                                     resolved)
forbidden_uses count:                             11 (resolved 7
                                                     baseline +
                                                     4 ambiguity
                                                     prohibitions)
resolution_note:                                  present (additional
                                                  context required)
```

Width relationship to resolved:

```
resolved.allowed_uses (4) > unresolved.allowed_uses (2)
unresolved.forbidden_uses (11) >= resolved.forbidden_uses (7)
```

Ambiguity policy items added in the unresolved `forbidden_uses`:

```
select one candidate role for convenience
broaden the allowed uses while unresolved
convert the ambiguity into a numerical confidence value
treat any natural-language rationale as proof of a role
```

Independence from the resolved dictionary:

```
RESOLVED_EXAMPLE   defined at line 30 as an ast.Dict literal
UNRESOLVED_EXAMPLE defined at line 119 as an ast.Dict literal
UNRESOLVED_EXAMPLE = RESOLVED_EXAMPLE         not present
.update( occurrences in file                  0
.copy() occurrences in file                   0
```

The same fragment id is reused; the assignment dictionaries are
not.

---

## §7 Semantic-Role vs Local-Descriptor Distinction

PR61 uses the `example:` prefix on all illustrative labels.
Position-wise, only some of them are interpreted as semantic roles.

Semantic-role-bearing positions:

```
RESOLVED.primary_role                    "example:observation"
RESOLVED.secondary_roles[0].label        "example:knowledge-reference"
UNRESOLVED.primary_role                  None
UNRESOLVED.candidate_roles[0]            "example:knowledge-reference"
UNRESOLVED.candidate_roles[1]            "example:candidate-statement"
```

Local non-role descriptors (not semantic roles):

```
record_shape                             "example:document_record"
provenance.source_type                   "example:external_document_collection"
```

The two categories must remain conceptually distinct. The five
distinct `example:*` strings are not "five semantic roles" and are
not "five framework role labels." They are illustrative local
labels in two different conceptual positions.

---

## §8 AllowedUse / ForbiddenUse Boundary

`AllowedUse` in the resolved example contains four uses, all of
which read or display the fragment without executing anything.

`ForbiddenUse` in the resolved example contains seven items, one
per PR60 baseline risk.

`AllowedUse` in the unresolved example is reduced to two uses
(display-as-unresolved, request-additional-context).

`ForbiddenUse` in the unresolved example is expanded to eleven
items, adding four ambiguity prohibitions on top of the seven
baseline.

Lock honored:

```
A missing prohibition must not be interpreted as permission.
```

The unresolved example does not omit a baseline; it carries the
seven baseline risks *and* the four ambiguity prohibitions
together.

---

## §9 Ambiguity Preservation

Behavior demonstrated by `UNRESOLVED_EXAMPLE`:

```
primary_role               None
candidate_roles            two illustrative locals
candidate_roles_note       "not a framework registry"
secondary_roles            empty (no forced add)
allowed_uses               reduced
forbidden_uses             expanded with 4 ambiguity items
resolution_note            explicit "additional context required"
forbidden_uses last item   downstream transition blockade
```

Behavior explicitly absent:

```
no numerical confidence
no probability field
no convenience selection of a candidate role
no LLM-rationale-as-proof
no silent broadening of allowed uses
```

---

## §10 Execution Boundary

Direct execution behavior:

```
construct two local dictionaries
format both dictionaries with stdlib pprint
print both dictionaries to stdout
exit normally
```

Behavior explicitly absent:

```
file read or write
environment-variable read
network access
database access
subprocess execution
Engine construction
tool execution
external mutation
role inference
validation result production
```

Import audit:

```
from pprint import pprint
```

Standard library only. No `ragcore` imports, no third-party
imports.

---

## §11 Ragcore / Engine Non-Integration

The example file does not import `ragcore` and does not interact
with Engine state.

```
ragcore import audit                              0 hits
classifier / validator def audit                  0 hits
forbidden type construct audit                    0 hits
  (dataclass / Enum / TypedDict / NamedTuple /
   Protocol / Pydantic / BaseModel)
helper function defs                              0
```

Engine non-mutation enumerated in the `forbidden_uses` of both
example dictionaries:

```
add evidence
create Claim
resolve Gap
register Rule
change Claim lifecycle state
change effective confidence
modify snapshot
create final finding
```

Lock honored:

```
This example ends at consumer interpretation.
```

---

## §12 Domain-Neutrality Audit

Audited vocabulary over the entire file (module docstring,
comments, dictionary keys, dictionary values, executable
statements):

```
cerberus / cve / cpe / kev / nvd / epss / openssh
vulnerability / exploit / scanner / nmap
host / port / service / asset / forensic
```

Result:

```
hits: 0 / 16
```

Bare PR59 / PR60 role-label audit (per PR61 entry directive
§1):

```
raw_data
parsed_record
observation_evidence
claim_candidate
finding
gap_candidate
```

Result:

```
bare-quoted hits: NONE
```

All role-bearing labels use the `example:` prefix.

---

## §13 Structural Verification

```
py_compile                              OK
python execution                        OK (pprint output)
pytest                                  1183 passing (unchanged)
ragcore source delta                    0 bytes
                                          (sha256-verified vs d8d1450)
Engine public methods                   40 (AST, unchanged)
Engine private methods                  18 (AST, unchanged)
ragcore.__all__                         48 (unchanged)
snapshot schema_version                 2 (unchanged)
snapshot top-level keys                 18 (unchanged)
new tests                               0
new framework public symbols            0
new example source files                1 (the example itself)
PR49 – PR60 files                       unchanged
context packet schema                   unchanged
proposal pipeline                       unchanged
operator gate                           unchanged
Engine judgment semantics               unchanged
```

Self-review audit (six axes applied to the example file):

```
non-normative phrasing                  PASS  (only negative
                                              uses of "canonical
                                              schema": "does not
                                              define a canonical
                                              schema")
import audit                            PASS  (pprint only)
function definitions                    PASS  (0)
prohibited type constructs              PASS  (0)
domain-neutral vocabulary               PASS  (0 / 16)
semantic-role vs local-descriptor       PASS  (2 categories,
                                              distinct positions)
```

---

## §14 Out-of-Scope Confirmation

PR61 does not perform any of the following:

```
ragcore source modification
Engine modification
framework public symbol addition
package export
snapshot modification
Claim lifecycle modification
effective-confidence modification
rule semantic modification
automatic classifier
role inference
role ranking
role validator
numerical role confidence
role registry
canonical schema
JSON Schema / dataclass / Enum / TypedDict / Pydantic
adapter implementation
retrieval implementation
LLM prompt
proposal schema change
packet schema change
new tests
domain-specific example
PR62 implementation
external adapter application
```

---

## §15 Future Handoff Boundary

PR61 may enable later work but does not schedule any.

Possible follow-ups, each requiring its own explicit entry
directive:

```
PR62 — Role Assignment Validator MVP
external adapter application
```

PR62 candidate entry conditions (recorded in PR60 §22, repeated
here as quotation):

```
validate shape and contradictions only
do not judge the correct semantic role
do not infer a role automatically
do not mutate Engine
remain ragcore-free
```

The example dictionaries in PR61 are not described as PR62
validator input. If PR62 is entered later, that PR will define
its own validation scope and may use, ignore, or replace the PR61
example shape.

None of the above are auto-entered by the merging of PR61.

---

## §16 Final Result

```
PR59 separated the interpretation axes.

PR60 defined how a consumer may assign roles in context
without creating Engine truth.

PR61 demonstrated one local consumer representation
of both a resolved and unresolved assignment.

The example does not become a schema,
a classifier, a validator, or downstream authority.
```

After merge, the framework re-enters a waits state. PR62 and any
external adapter application require their own explicit entry
directives.
