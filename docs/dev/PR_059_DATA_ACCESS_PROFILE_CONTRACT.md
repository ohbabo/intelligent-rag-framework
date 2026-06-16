# PR59 — Data Access Profile Contract

Development record for the Data Access Profile Contract introduced
in PR #60 (branch `docs/data-access-profile-contract`).

```
base:           main d5496ea
branch:         docs/data-access-profile-contract
204차 commit:    ead11d9
205차 commit:    (this record, docs/dev)
PR:             #60
type:           framework-level architecture contract, doc-only
```

This record captures the intent, the boundary, the six-axis model,
the relationship to the existing proposal pipeline (PR49–PR58), and
the verification results that closed PR59.

---

## §1 PR Purpose

PR59 defines a domain-neutral, consumer-side data access metadata
contract.

It separates:

```
provenance
record shape
contextual semantic role
retrieval behavior
permitted use
forbidden interpretation
```

PR59 is not:

```
an Engine feature
an RAG implementation
a role classifier
an adapter implementation
a proposal pipeline decision layer
a domain-specific contract
```

PR59 lives on the consumer / adapter side. Knowledge of a data
item's provenance does not by itself authorize an Engine mutation,
a Claim transition, a tool execution, or a downstream gate decision.

---

## §2 Baseline

```
base:                       main d5496ea
baseline tests:             1183 passing
immediate predecessor:      README evidence-centric RAG philosophy
                            clarification
```

PR59 attributable diff is measured from `d5496ea`. The README
predecessor commit is doc-only and orthogonal to PR59; it is not
modified, reverted, or referenced by the contract.

204차 added `docs/architecture/DATA_ACCESS_PROFILE_CONTRACT.md`
(`+818` lines). 205차 adds this record. No other files are touched.

---

## §3 Core Boundary Statements

The contract is governed by three primary locks:

```
1. Data source is not semantic role.
2. Semantic role is not retrieval behavior.
3. Allowed use is not unlimited trust.
```

Two supporting locks reinforce contextual scope:

```
4. A semantic role is assigned to a data item in context.
   It is not permanently owned by a source or record type.

5. A particular consuming domain is only a possible case,
   not the contract. Domain examples must not define
   framework vocabulary.
```

Additional generality lock recorded in §18 of the contract:

```
No particular domain defines this contract.
A domain may consume the contract only through external
interpretation.
```

These statements are not abstract — they are referenced and applied
in every later section of the contract. Where a section seems to
allow a shortcut (such as inferring role from source, or use from
access profile), that shortcut is explicitly forbidden.

---

## §4 Six-Axis Contract

Each axis is independent and answers a single question.

```
SourceType
  = provenance, not authority

BaseRecordType
  = shape, not semantic role

SemanticRole
  = contextual interpretation, not source ownership

DataAccessProfile
  = access and retrieval behavior, not truth

AllowedUse
  = explicit permitted scope, not unlimited authorization

ForbiddenUse
  = consumer interpretation constraint, not Engine mutation
```

Forbidden automatic equivalences:

```
SourceType        == SemanticRole               forbidden
BaseRecordType    == SemanticRole               forbidden
retrieval success == verified evidence          forbidden
semantic search   == truth                      forbidden
DataAccessProfile == AllowedUse                 forbidden
AllowedUse        == automatic execution        forbidden
```

The contract does not define a canonical projection or mapping
between axes. Any such mapping belongs to consumer policy and
remains subject to `AllowedUse` and `ForbiddenUse` constraints.

This PR introduces no `dataclass`, no `enum`, no `TypedDict`, no
JSON schema, and no serialization format for any axis. Field names
and storage forms are not frozen.

---

## §5 Contextual Role Assignment

A role assignment is the act of attaching a `SemanticRole`, together
with the associated `AllowedUse` and `ForbiddenUse` constraints, to
a data item or fragment within a specific judgment context.

The contract records the following critical non-equivalences:

```
role assignment ≠ Engine mutation
role assignment ≠ evidence registration
role assignment ≠ Claim creation
role assignment ≠ Gap resolution
role assignment ≠ Rule registration
role assignment ≠ final finding publication
```

Adjacent role-name non-equivalences:

```
claim_candidate          ≠ a registered Claim
rule_candidate           ≠ a registered Rule
finding                  ≠ a final verdict
required_evidence_spec   ≠ a satisfied requirement
observation_evidence     ≠ a verified observation
```

Role composition per assignment context:

```
primary role:
  exactly one SemanticRole per data item

secondary roles:
  zero or more
  each explicitly justified
  each bounded by its own AllowedUse
  each bounded by its own ForbiddenUse
```

A secondary role is not a free-form tag, an annotation, or an open
list. Collecting secondary roles does not produce multiple truths,
multiple Engine states, unlimited tagging, downstream authorization,
or precedence over the primary role.

The same data item may carry different role assignments in different
judgment contexts. Role assignment is local to a context and is not
a global property of a record type or a source.

---

## §6 Existing PR Boundary Preservation

The following PRs are unchanged by PR59:

```
PR49 read surface thaw policy           unchanged
PR50 audit                              unchanged
PR51 read wrapper                       unchanged
PR52 context packet spec                unchanged
PR53 packet validator                   unchanged
PR54 proposal layer bridge              unchanged
PR55 proposal shape validator           unchanged
PR56 proposal safety validator          unchanged
PR57 operator decision boundary         unchanged
PR58 proposal usage playbook            unchanged
```

In particular, the following surfaces are unchanged:

```
context packet schema           unchanged
proposal shape validator        unchanged
proposal safety validator       unchanged
operator decision boundary      unchanged
Engine judgment semantics       unchanged
snapshot schema_version (2)     unchanged
snapshot top-level keys (18)    unchanged
Claim lifecycle states          unchanged
effective confidence formula    unchanged
rule judgment semantics         unchanged
```

PR59 is not the next serial decision layer after the proposal
pipeline. It is a parallel adapter-side metadata path.

```
proposal pipeline:
  packet → proposal → validators → operator gate

parallel data-access path:
  external data
    → source / record interpretation
    → contextual role assignment
    → access / use constraints
    → consumer-side use
```

If a future adapter wishes to enrich a context packet with metadata
described by this contract, or annotate a retrieval result with a
semantic role, that integration belongs to a separate PR. It is not
included here.

---

## §7 Domain-Neutrality Result

Audited vocabulary (word-boundary, case-insensitive) over the
normative body of the contract:

```
cerberus / cve / cpe / kev / nvd / epss / openssh
vulnerability / exploit / scanner / nmap
host / port / service / asset / forensic
```

Result:

```
normative domain-specific vocabulary count: 0
```

The contract also does not contain:

```
domain-specific appendix
domain-specific case study
domain-specific record class promoted into core vocabulary
domain-specific public symbol
```

A domain may consume this contract through external interpretation.
A domain does not define the contract.

The §18 narrative references the audit list maintained by prior
contracts (PR45-E §3 and PR44-D §5.6); that reference is quotation
of the policy, not normative use of the vocabulary.

---

## §8 Ragcore Symbol Boundary

The following identifiers exist only as conceptual consumer-side
vocabulary in this contract:

```
SourceType
BaseRecordType
SemanticRole
DataAccessProfile
RAGProfile
AllowedUse
ForbiddenUse
RoleAssignment
RoleAssignmentPolicy
```

For all of the above, after PR59:

```
NOT a ragcore type
NOT in ragcore.__all__
NOT in ragcore/types.py
NOT Engine state
NOT a snapshot schema field
NOT a lifecycle state
NOT a confidence modifier
NOT rule judgment semantics
```

If a future PR wishes to promote any of these names into ragcore as
code, that promotion requires its own sequence:

```
thaw policy
→ audit
→ contract revision
→ tests
→ implementation
```

PR59 does not authorize such promotion. Each follow-up requires its
own explicit entry directive.

---

## §9 Implementation Footprint

```
docs/architecture/DATA_ACCESS_PROFILE_CONTRACT.md   +818 lines  (204차)
docs/dev/PR_059_DATA_ACCESS_PROFILE_CONTRACT.md     this record   (205차)

ragcore source:                  0 bytes changed
tests:                           0 added
public symbols:                  0 added
Engine behavior:                 0 added
Engine public method count:      40 (unchanged)
Engine private method count:     18 (unchanged)
ragcore.__all__:                 48 (unchanged)
snapshot schema_version:         2 (unchanged)
snapshot top-level keys:         18 (unchanged)
```

Single staged file per cycle. `ragcore.egg-info/` excluded as an
untracked build artifact.

204차 commit: `ead11d9 docs(architecture): define data access profile
contract`.
205차 commit: this record.

---

## §10 Self-Review Checklist

```
[✓] architecture contract file exists
[✓] docs/dev PR59 record added
[✓] pytest 1183 passing
[✓] ragcore source change 0 bytes
[✓] new tests 0
[✓] new public symbols 0
[✓] new Engine behavior 0
[✓] Engine public methods remain 40
[✓] Engine private methods remain 18
[✓] ragcore.__all__ remains 48
[✓] no new contract §51 entry
[✓] snapshot schema unchanged
[✓] Claim lifecycle unchanged
[✓] effective confidence unchanged
[✓] rule judgment semantics unchanged
[✓] PR51–PR58 unchanged
[✓] six independent axes documented
[✓] contextual role assignment documented
[✓] primary / secondary role boundary documented
[✓] AllowedUse / ForbiddenUse documented
[✓] normative domain-specific vocabulary count = 0
[✓] conceptual vocabulary not promoted into ragcore
[✓] no adapter implementation
[✓] no role classifier implementation
[✓] PR60 / PR61 / PR62 not auto-entered
[✓] external adapter not auto-entered
```

---

## §11 Closing Meaning

```
PR59 closes the Data Access Profile Contract.

A source does not own a semantic role.
A record shape does not determine truth.
A retrieval method does not authorize interpretation.
An allowed use does not grant unlimited trust.

The contract remains domain-neutral, consumer-side, and outside
Engine judgment semantics.
```

After merge, the framework re-enters a waits state. PR60, PR61,
PR62, and any external adapter application require their own
explicit entry directives.
