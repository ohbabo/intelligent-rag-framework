# Role Assignment Policy Spec

Framework-level architecture policy for consumer- and adapter-side
semantic role assignment over data items along the six axes defined
by PR59 (Data Access Profile Contract).

This document is doc-only. It introduces no public symbols, no
ragcore changes, no Engine behavior, no tests, and no example source
files.

---

## §0 Scope Limitation

This document is a framework architecture policy. It describes the
interpretation procedure a consumer or adapter should follow when
assigning a `SemanticRole`, an `AllowedUse` scope, and a
`ForbiddenUse` boundary to a data item or fragment within a specific
judgment context.

This policy does not implement, schedule, or authorize any of:

- ragcore source modification
- new public symbol in `ragcore.__all__`
- snapshot schema change
- Claim lifecycle change
- proposal pipeline modification
- packet schema change
- validator behavior change
- adapter implementation
- retrieval implementation
- automatic role classifier
- LLM classifier prompt
- numerical role assignment confidence
- role registry or mapping database
- new contract §51 entry

This policy is consumer-side and domain-neutral. A particular
consuming domain is one possible case among many; it does not define
the policy.

---

## §1 Purpose

PR59 (Data Access Profile Contract) separated six independent axes:

```
SourceType
BaseRecordType
SemanticRole
DataAccessProfile
AllowedUse
ForbiddenUse
```

PR59 defined what must be kept apart. It did not describe how a
consumer should arrive at a `SemanticRole`, an `AllowedUse`, and a
`ForbiddenUse` for a specific data item in a specific judgment
context.

The purpose of this policy is to record that interpretation
procedure as a domain-neutral framework policy.

Wrong-shaped reasoning:

```
SourceType is api,  therefore the item is a knowledge_node.
BaseRecordType is ObservationRecord,  therefore evidence.
Found via semantic_search,  therefore true.
```

Right-shaped reasoning:

```
What item is being assigned a role?
Where did it come from?
What shape does it have?
In what judgment context is the item being read?
What role does the context most directly require?
Under that role, what is explicitly allowed?
What is explicitly forbidden?
If context or evidence is insufficient, what must be preserved?
```

This policy does not produce a role automatically. It records the
constraints under which a role assignment becomes valid.

---

## §2 Baseline

```
main:                       30b71bc
tests:                      1183 passing
predecessor:                PR59 Data Access Profile Contract (#60)
```

PR49 through PR59 remain unchanged by this policy:

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
PR59 data access profile contract       unchanged
```

```
ragcore source:             unchanged
Engine public methods:      40
ragcore.__all__:            48
snapshot schema_version:    2
snapshot top-level keys:    18
```

---

## §3 Core Boundary Statements

The policy is governed by five locks.

```
1. Role assignment is a contextual interpretation,
   not a source-derived fact.

2. When context is insufficient, the policy must
   preserve ambiguity rather than fabricate a role.

3. A role assignment constrains consumer use.
   It does not create Engine truth.

4. Role assignment must be justified by the data item,
   the interpretation context, and the intended use together.

5. No particular domain defines the assignment policy.
   Domain-specific mappings must remain outside the
   normative framework policy.
```

Where a later section seems to allow a shortcut (such as inferring
a role directly from `SourceType`, treating retrieval success as
truth, or interpreting absence in a `ForbiddenUse` list as
permission), that shortcut is explicitly forbidden by these locks.

---

## §4 Relationship to PR59

PR59 defined six independent axes and forbade their conflation.
This policy extends PR59 by describing how a consumer arrives at a
valid combination of `SemanticRole`, `AllowedUse`, and
`ForbiddenUse` for a data item in context.

The boundary between PR59 and PR60:

```
PR59:  what axes must remain separate
PR60:  how the axes are interpreted and combined in context
```

PR60 does not merge the six axes. In particular, the following
automatic mappings remain forbidden after PR60:

```
SourceType         → SemanticRole
BaseRecordType     → SemanticRole
DataAccessProfile  → SemanticRole
SemanticRole       → Engine state
SemanticRole       → automatic action
AllowedUse         → unrestricted permission
```

A consumer may use these signals as inputs to interpretation. A
consumer may not promote any signal to an automatic determinant.

---

## §5 Policy Inputs

A role assignment considers, conceptually, the following inputs.

```
data item or fragment
source provenance
base record shape
current interpretation context
current question or decision need
available supporting relations
traceability information
intended consumer use
existing use restrictions
```

This policy does not freeze field names, identifiers, or schemas
for any of the above. In particular, this policy does not introduce:

```
RoleAssignmentInput dataclass
TypedDict
JSON Schema
enum
serialization format
database table
Engine registry
```

What is required is conceptual presence of these inputs. The
storage form is consumer-side policy.

---

## §6 Assignment Target Boundary

A role is assigned to a specific data item or fragment, not to a
whole source.

Assignment targets may include:

```
record
field
relation
derived fragment
retrieved passage
operator-provided item
```

Lock:

```
The assignment target must be identifiable.
A whole source must not receive one permanent role by default.
```

A single source may produce multiple data items, each with its own
role assignment, possibly different from one another. A single data
item may receive different role assignments in different
interpretation contexts.

---

## §7 Provenance and Record Shape

`SourceType` and `BaseRecordType` are policy inputs, not policy
outputs.

Lock for provenance:

```
Provenance informs interpretation.
It does not determine semantic role.
```

Lock for record shape:

```
Record shape limits possible interpretation.
It does not prove semantic meaning.
```

A consumer should record provenance and shape when assigning a
role. A consumer must not derive the role solely from provenance,
solely from shape, or solely from the access mechanism that
surfaced the data.

---

## §8 Interpretation Context

A role assignment without an interpretation context is not a valid
role assignment.

A consumer should state the current question or decision need
before proposing a role. Generic illustrative contexts:

```
understanding an observation
comparing external knowledge
identifying missing information
forming a candidate statement
supporting operator review
preparing a recheck
```

Lock:

```
Role assignment context must be stated.
A role detached from a question is not a role.
```

This policy does not freeze field names or schemas for context
identifiers.

---

## §9 Primary Role Policy

Within a single assignment context:

```
primary role:  exactly one SemanticRole per data item
```

A primary role is the most directly relevant interpretation of the
data item under the stated context. If multiple candidate primary
roles compete, the consumer must not silently select one for
convenience. The conflict must be surfaced and resolved (see §15).

A primary role is not:

```
a global role
a permanent role
a source-owned role
a record-type-owned role
an Engine status
a truth label
a confidence score
```

The same data item may carry different primary roles in different
contexts. Each context's assignment must be traceable to its own
basis (see §11).

---

## §10 Secondary Role Policy

Secondary roles are auxiliary interpretations attached to a data
item alongside the primary role within the same assignment context.

A secondary role is permitted only when **all** of the following
hold:

```
explicit justification exists
it adds meaning distinct from the primary role
its AllowedUse is stated
its ForbiddenUse is stated
it does not contradict the primary role
it does not authorize downstream action
```

A secondary role is not a free-form tag, a placeholder, or an open
list. Forbidden secondary-role uses:

```
tagging everything that might be useful
adding roles without justification
using secondary roles to bypass primary-role ambiguity
using secondary roles to expand permissions silently
using secondary roles as hidden downstream commands
```

Lock:

```
Secondary roles extend interpretation,
not authority.
```

---

## §11 Assignment Basis

Each role assignment requires a conceptual, explainable basis. A
consumer should be able to answer, for each assignment:

```
why this data item
why this context
why this primary role
why each secondary role
why these allowed uses
why these forbidden uses
```

Lock:

```
An unexplained role label is not a valid role assignment.
```

This policy does not freeze a field name, length limit, or schema
for explanation text. What is required is the conceptual presence
of an explainable basis, not a particular storage form.

---

## §12 AllowedUse Derivation

`AllowedUse` is not generated from a role name alone. A consumer
derives `AllowedUse` by considering, jointly:

```
the assigned semantic role
the interpretation context
the data provenance
the traceability quality
the intended consumer of the assignment
known restrictions on the data
```

Baseline principles:

```
AllowedUse must be explicit.
AllowedUse must be narrow.
AllowedUse must be reviewable.
AllowedUse must not imply Engine mutation or execution.
```

Unspecified use is not automatically permitted. `AllowedUse` is a
positive permission with explicit scope. Convenience-driven
broadening of `AllowedUse` is forbidden.

---

## §13 ForbiddenUse Derivation

`ForbiddenUse` is not an appendix to a documentation entry. It is
the safety boundary of the role assignment.

Seven baseline risks must be reviewed for every role assignment:

```
1. misrepresenting retrieved content as verified fact
2. replacing stronger evidence
3. creating a registered Claim from a candidate
4. treating a finding as final verdict
5. changing lifecycle state
6. executing tools
7. publishing downstream conclusions or bypassing operator review
```

For each baseline risk, the consumer states whether the role
assignment permits that risk, forbids that risk, or remains silent.
A silent answer is not a permissive answer.

Lock:

```
A missing prohibition must not be interpreted as permission.
```

This policy does not freeze field names or schemas for individual
prohibition entries.

---

## §14 Conflict Detection

Before a role assignment is treated as valid, a consumer should
check for the following conflicts:

```
primary role vs secondary role
AllowedUse vs ForbiddenUse
role vs provenance
role vs interpretation context
role vs intended use
```

If any of the above conflict, the role assignment is treated as
unresolved (see §15). Downstream consumer logic must not proceed
on a role assignment that contains an unresolved conflict.

This policy does not introduce a conflict resolution algorithm. The
required behavior is to detect the conflict and to halt downstream
progression until it is resolved.

---

## §15 Ambiguity and Unresolved Policy

When evidence or context is insufficient to support a single
primary role with explicit `AllowedUse` and `ForbiddenUse`, the
consumer must preserve ambiguity.

Required behaviors on insufficient context:

```
preserve ambiguity
request more context
reduce allowed use
prevent downstream transition
```

Forbidden behaviors on insufficient context:

```
guess a role
assign a broader role for convenience
convert ambiguity into numerical confidence
use LLM phrasing as proof
```

Lock:

```
Ambiguity is information.
It must not be silently converted into certainty.
```

This policy does not introduce a new confidence or probability
system. It does not introduce an `UNRESOLVED` enum, status type, or
schema. What is required is the conceptual preservation of the
unresolved state; the storage form is consumer-side policy.

---

## §16 Traceability Boundary

Each role assignment should, in principle, be traceable to:

```
source identity
record or fragment location
interpretation context
assignment basis
primary role and any secondary roles
allowed uses and forbidden uses
unresolved or conflict markers, if any
```

This policy does not freeze field names, identifiers, or storage
forms for traceability metadata. In particular, this policy does
not introduce:

```
RoleAssignment dataclass
RoleAssignmentPolicy dataclass
database table
JSON schema
serialization format
snapshot field
Engine registry
```

Conceptual auditability is required. Implementation form is
consumer-side.

---

## §17 Relationship to Engine

```
Role assignment lives outside the Engine.
```

A role assignment does not, by itself, perform any of the
following:

```
add evidence
create Claim
resolve Gap
register Rule
change Claim status
change effective confidence
change snapshot
create final finding
```

Any change to Engine state must follow the existing Engine public
API and contracts. A consumer that wishes to act on a role
assignment must route that action through the appropriate Engine
method and remains subject to operator review, validator gates, and
all prior locks established in PR49 through PR59.

---

## §18 Relationship to PR51–PR58

The proposal pipeline established in PR49 through PR58 is
unchanged by this policy.

```
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
context packet schema
proposal shape validator
proposal safety validator
operator gate
operator workflow
```

If a future PR wishes to use role assignment metadata in a context
packet or in a proposal input, that integration belongs to that
later PR. This policy does not perform the integration. No packet
schema is changed.

---

## §19 Domain-Neutrality Policy

This policy is domain-neutral. Its normative body does not depend
on, name, or privilege any particular consuming domain.

A particular consuming domain may provide external examples,
mappings, or presets that consumers use locally. Those external
materials remain outside the normative framework policy. A
consumer who wishes to apply a domain-specific mapping does so on
its own side, subject to all locks in this policy and in PR59.

This policy contains:

```
no domain-specific appendix
no domain-specific mapping table
no domain-specific role preset
no domain-specific BaseRecordType
no domain-specific public symbol
```

The domain-neutral audit list applied to the normative body of
this policy is defined by prior policy (see PR45-E §3 and PR44-D
§5.6). References to that list from within this policy are
quotation, not normative use.

---

## §20 Ragcore Symbol Boundary

The following identifiers exist only as conceptual consumer-side
vocabulary in this policy:

```
RoleAssignmentPolicy
RoleAssignment
AssignmentContext
AssignmentBasis
PrimaryRole
SecondaryRole
AllowedUse
ForbiddenUse
UnresolvedAssignment
```

For all of the above:

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

If a future PR wishes to promote any of these names into ragcore
as code, that promotion requires a separate sequence:

```
thaw policy
→ audit
→ contract revision
→ tests
→ implementation
```

This policy does not authorize such promotion.

---

## §21 Anti-Patterns

The following patterns are explicitly forbidden by this policy.

```
AP1.  Assigning role from SourceType alone
      Provenance is an input. It is not a determinant.

AP2.  Assigning role from BaseRecordType alone
      Shape is an input. It does not prove meaning.

AP3.  Assigning role from retrieval mode alone
      DataAccessProfile is access behavior, not truth.

AP4.  Omitting interpretation context
      A role detached from a question is not a role.

AP5.  Multiple primary roles in one context
      Convenience-driven role multiplication hides ambiguity.

AP6.  Unlimited secondary-role tagging
      Secondary roles require justification, not free tagging.

AP7.  Secondary role used to broaden authority
      Secondary roles extend interpretation, not authority.

AP8.  AllowedUse inferred as unlimited permission
      Unspecified use is not automatically permitted.

AP9.  Missing ForbiddenUse treated as permission
      A missing prohibition is not consent.

AP10. Ambiguity converted into fabricated certainty
      Insufficient context demands preservation, not invention.

AP11. Role assignment treated as Engine mutation
      A consumer-side label is not Engine state.

AP12. Candidate role treated as registered Engine object
      `claim_candidate` is not a registered Claim;
      `finding` is not a final verdict;
      `rule_candidate` is not a registered Rule.

AP13. Domain-specific mapping promoted into framework policy
      Domain mappings remain external to the normative policy.

AP14. LLM explanation treated as assignment proof
      Natural-language rationale is not, by itself, a basis.
```

Each anti-pattern names a real failure mode this policy prevents.

---

## §22 Future Handoff Boundary

This policy may enable later work but does not schedule any.

Possible follow-ups, each requiring its own explicit entry
directive:

```
PR61 — Minimal Consumer-Side Role Assignment Example
PR62 — Role Assignment Validator MVP
external adapter application
```

PR61 candidate entry conditions:

```
consumer-side only
dict-based example
no ragcore imports
domain-neutral records only
no automatic classifier
no Engine calls
```

PR62 candidate entry conditions:

```
validate shape and contradictions only
do not judge the correct semantic role
do not infer a role automatically
do not mutate Engine
remain ragcore-free
```

External adapter candidate conditions:

```
domain mappings remain outside framework normative policy
adapter role assignments remain traceable
adapter cannot promote local vocabulary into ragcore
```

None of the above are auto-entered by the merging of this policy.

---

## §23 Non-Goals

This PR does not perform:

```
ragcore source modification
Engine method addition
public symbol addition
snapshot schema change
Claim lifecycle change
effective confidence change
modifier change
rule judgment change
packet schema change
proposal schema change
validator code change
adapter implementation
retrieval implementation
automatic role classifier
LLM classifier prompt
role-ranking algorithm
numerical assignment confidence
role registry
mapping database
JSON Schema
dataclass / enum / TypedDict
domain-specific example
new tests
new example source files
new contract §51 entry
```

---

## §24 Exit Criteria

A merged form of this policy must satisfy:

```
ROLE_ASSIGNMENT_POLICY_SPEC.md added
doc-only
pytest remains 1183 passing
ragcore source change 0 bytes
new tests 0
new public symbols 0
new Engine behavior 0
Engine public methods remain 40
Engine private methods remain 18
ragcore.__all__ remains 48
no new contract §51 entry
snapshot schema unchanged
Claim lifecycle unchanged
effective confidence unchanged
rule judgment semantics unchanged
PR51–PR59 unchanged
contextual assignment procedure documented
primary-role policy documented
secondary-role constraints documented
AllowedUse derivation policy documented
ForbiddenUse derivation policy documented
ambiguity preservation policy documented
traceability boundary documented
domain-specific normative vocabulary count = 0
conceptual symbols not promoted into ragcore
PR61 / PR62 / external adapter not auto-entered
```

(26 items)

---

## Closing Meaning

PR60 defines how a consumer may assign semantic roles in context.

```
A source does not dictate a role.
A record shape does not prove meaning.
A retrieval method does not establish truth.
Ambiguity must be preserved when interpretation is insufficient.

Role assignment constrains consumer use.
It does not create Engine truth.
```

The policy remains domain-neutral, consumer-side, and outside
Engine judgment semantics.

---

## §25 Post-M06 addendum (PR75-M06, 2026-06-19)

PR75-M06 (`DOWNSTREAM_RESULT_REENTRY_CONTRACT.md`) applies
this policy unchanged to result-level role assignment for
downstream investigation results re-entering the framework.

```
- Assignment targets at the re-entry layer are
  result-level units: result record, result field, result
  fragment, result relation, derived fragment. The
  source / adapter / tool / run as a whole is NOT an
  assignment target.

- A producer or adapter does NOT carry a permanent
  SemanticRole. Each result item is interpreted in the
  current re-entry context. A subsequent investigation that
  reuses the same producer / adapter does NOT inherit a
  prior role assignment.

- Each assignment considers PR61's axes unchanged:
  SourceType / BaseRecordType / SemanticRole /
  DataAccessProfile / AllowedUse / ForbiddenUse.

- AllowedUse / ForbiddenUse are re-evaluated for each
  result. An AllowedUse value from a prior re-entry context
  does NOT bind a new re-entry context.

- Unresolved role assignment terminates the re-entry chain
  at PR75-M06 Stage 3 (M06 §4.3 / §9.4). No candidate is
  materialized. The result may still be archived or cited
  by the consumer; archiving / citing is a valid terminal
  state.

- Role assignment is NEVER a mutation authority. An admitted
  role assignment does NOT authorize a candidate; a
  materialized candidate does NOT authorize a review
  outcome; an approved review does NOT authorize an Engine
  invocation. Each step requires its own consumer-side
  action under M06 §4.

- Forbidden mappings (per M06 §4.3 / §9.3):
    tool output type      -> SemanticRole
    result source         -> SemanticRole
    result field name     -> Evidence
    retrieval method      -> truth
    result ranking        -> Evidence.strength
    severity label        -> Gap.severity
    external status       -> Claim.status
```

PR75-M06 does not modify any of §1 ~ §24 of this spec, the
PR61 axes, or the §21 anti-patterns. §0 ~ §24 normative body
remains unchanged.
