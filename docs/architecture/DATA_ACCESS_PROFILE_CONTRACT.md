# Data Access Profile Contract

Framework-level architecture contract for consumer- and adapter-side
data interpretation along six independent axes.

This contract is doc-only. It introduces no public symbols, no ragcore
changes, no Engine behavior, no tests, and no example source files.

---

## §0 Scope Limitation

This document is a framework architecture contract. It describes how a
consumer or adapter should describe data flowing into a judgment
system before that data reaches any judgment, action, or downstream
gate.

This contract does not implement, schedule, or authorize any of:

- ragcore source modification
- new public symbol in `ragcore.__all__`
- snapshot schema change
- Claim lifecycle change
- proposal pipeline modification
- context packet schema modification
- validator behavior change
- adapter implementation
- retrieval implementation
- role classifier implementation
- new contract §51 entry

This contract is consumer-side and domain-neutral. A particular
consuming domain is one possible case among many; it does not define
the contract.

---

## §1 Purpose

External data entering a judgment system arrives from heterogeneous
sources, in heterogeneous shapes, and is used for heterogeneous
purposes. When provenance, shape, semantic role, retrieval behavior,
and authorized use are conflated, consumer code becomes fragile and
handoffs into the judgment core become unsafe.

The purpose of this contract is to keep these dimensions separate as
six independent axes:

- where the data came from (source)
- what shape the data has (record type)
- what role it plays in the current judgment context (semantic role)
- how it is reached or retrieved (access profile)
- what it is explicitly permitted to be used for (allowed use)
- what it is explicitly forbidden from being used for (forbidden use)

This contract is a metadata contract. It does not assign trust, truth,
confidence, or final verdict to any data item.

---

## §2 Baseline

```
main:                       d5496ea
tests:                      1183 passing
immediate predecessor:      README evidence-centric RAG philosophy
                            clarification
```

PR49 through PR58 (proposal pipeline read surface, validators,
operator boundary, and usage playbook) remains unchanged by this
contract.

```
ragcore source:             unchanged
Engine public methods:      40
ragcore.__all__:            48
snapshot schema_version:    2
snapshot top-level keys:    18
```

---

## §3 Core Boundary Statements

Three primary locks govern every section of this document.

```
1. Data source is not semantic role.
2. Semantic role is not retrieval behavior.
3. Allowed use is not unlimited trust.
```

Two supporting locks reinforce contextual scope.

```
4. A semantic role is assigned to a data item in context.
   It is not permanently owned by a source or record type.

5. A particular consuming domain is only a possible case,
   not the contract. Domain examples must not define
   framework vocabulary.
```

Where a later section seems to allow a shortcut (such as inferring
role from source, or use from access profile), that shortcut is
explicitly forbidden by these locks.

---

## §4 Position Relative to PR49–PR58

The proposal pipeline established by PR49 through PR58 describes how a
consumer reads Engine state, presents it to an LLM, validates the
proposal, and routes operator review:

```
packet → proposal → shape validator → safety validator → operator gate
```

This contract describes a parallel adapter-side metadata path:

```
external data
  → source / record interpretation
  → contextual role assignment
  → access / use constraints
  → consumer-side use
```

The two paths may eventually meet inside a consumer or adapter, but
this contract does not couple them. In particular:

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

If a future adapter wishes to enrich a context packet with metadata
described by this contract, or annotate a retrieval result with a
semantic role, that integration is the subject of a separate PR. It
is not included here. The context packet schema is unchanged.

---

## §5 Six-Axis Model Overview

A data item entering a consumer or adapter can be described along six
independent axes.

```
Axis                  Question
--------------------  --------------------------------------------
SourceType            Where did this come from?
BaseRecordType        What shape does it have?
SemanticRole          What role does it play in this context?
DataAccessProfile     How is it reached?
AllowedUse            What may it explicitly be used for?
ForbiddenUse          What may it never be used for?
```

These axes are independent. Knowing one does not determine another.

```
SourceType        does not imply  SemanticRole
BaseRecordType    does not imply  SemanticRole
DataAccessProfile does not imply  truth
AllowedUse        does not imply  unspecified additional use
ForbiddenUse      does not imply  Engine state change
```

This contract does not define a canonical mapping or projection
between axes. Any such mapping belongs to consumer policy and remains
subject to AllowedUse and ForbiddenUse constraints.

---

## §6 SourceType

Question: Where did this data come from?

Illustrative examples (not a closed enumeration):

```
api
tool
file
log
operator
engine
retrieval_system
external_system
```

Lock:

```
SourceType describes provenance.
It does not grant semantic authority.
```

Knowing that a data item came from a particular origin does not by
itself make it evidence, knowledge, or a verified observation. It
does not by itself authorize any consumer action. It does not by
itself satisfy any AllowedUse precondition.

This contract does not freeze a closed enumeration of source kinds,
and it does not assign default trust levels to particular origins.
Such choices are consumer-side policy and remain subject to §10 and
§11.

---

## §7 BaseRecordType

Question: What shape or schema does this data take?

Illustrative examples (not a closed enumeration):

```
ObservationRecord
EventRecord
DocumentRecord
MetricRecord
PolicyRecord
KnowledgeRecord
OperatorNoteRecord
RetrievalResultRecord
```

Lock:

```
BaseRecordType describes shape.
It does not determine semantic role or truth.
```

A record shape may suggest what kinds of fields are present, but it
does not by itself authorize how those fields are interpreted. A
`KnowledgeRecord` is not automatically evidence. An
`ObservationRecord` is not automatically a verified observation. A
`RetrievalResultRecord` is not automatically truth.

This contract does not freeze field names, schemas, or serialization
formats for any record type. No dataclass, enum, `TypedDict`, or JSON
schema is introduced.

---

## §8 SemanticRole

Question: In the current judgment context, what role does this data
item play?

Illustrative examples (not a closed enumeration):

```
raw_data
parsed_record
canonical_atom
knowledge_node
knowledge_relation
observation_evidence
verification_evidence
evidence_knowledge_link
claim_candidate
gap_candidate
rule_candidate
required_evidence_spec
finding
recommendation
recheck_record
```

Lock:

```
SemanticRole is contextual.
It is not inferred solely from SourceType or BaseRecordType.
```

A SemanticRole is assigned to a data item by a consumer or adapter
within a specific judgment context. The same data item may carry
different SemanticRoles in different contexts. SourceType and
BaseRecordType are signals; they are not sufficient determinants.

Critical non-equivalences:

```
claim_candidate          ≠ a registered Claim
rule_candidate           ≠ a registered Rule
finding                  ≠ a final verdict
required_evidence_spec   ≠ a satisfied requirement
observation_evidence     ≠ a verified observation
```

Assigning a SemanticRole does not by itself mutate Engine state,
create a Claim, resolve a Gap, register a Rule, or publish a final
finding. SemanticRole is a consumer-side label that determines how
subsequent consumer logic reads the data item. It is not what the
Engine accepts as truth.

---

## §9 DataAccessProfile

Question: How is this data reached, selected, read, or surfaced?

Illustrative examples (not a closed enumeration):

```
exact_lookup
semantic_search
graph_traversal
contextual_retrieval
case_memory
policy_lookup
hybrid
```

Lock:

```
DataAccessProfile describes access behavior.
It does not describe truth, confidence, status, or semantic role.
```

A `semantic_search` result is not evidence. An `exact_lookup` success
is not verification. A `graph_traversal` connection is not a Claim
confirmation. A `policy_lookup` match is not a final verdict.

The access profile tells a consumer only how the data was reached. It
does not authorize any interpretation, mutation, or action.

Whether a consumer uses a vector store, a graph store, a relational
store, a static file, manual lookup, or no retrieval at all is
entirely a consumer choice. This contract neither requires nor
prefers any particular retrieval implementation.

---

## §10 AllowedUse

Question: Under this role assignment, what is this data item
explicitly permitted to support?

Illustrative examples:

```
provide context
support manual comparison
suggest further inspection
enrich an explanation
identify missing information
support operator review
```

Lock:

```
AllowedUse defines an explicit permitted scope.
It does not authorize unspecified uses.
```

If a use is not explicitly within an AllowedUse declaration, it is
not permitted. Uses are not inferred from absence in a ForbiddenUse
list.

AllowedUse does not authorize:

```
tool execution
Engine state mutation
Claim lifecycle transition
Rule registration
final verdict publication
bypassing operator review
bypassing downstream gating
```

AllowedUse is a positive permission with explicit scope. It is not a
residual permission filled by default.

---

## §11 ForbiddenUse

Question: Under this role assignment, what interpretations or uses
are explicitly forbidden?

Illustrative examples:

```
treat retrieved content as verified fact
replace direct observation
create final verdict automatically
change Engine state
trigger tool execution
bypass operator review
```

Lock:

```
ForbiddenUse constrains consumer interpretation and use.
It does not modify Engine truth.
```

ForbiddenUse is a negative constraint applied to consumer logic. It
prevents a consumer from acting on a data item in particular ways
under a given role assignment.

If AllowedUse and ForbiddenUse conflict, the role assignment must be
treated as invalid or unresolved. Downstream consumer logic must not
proceed by silently choosing one side. The conflict must be surfaced
and resolved before further consumer use.

---

## §12 Context-Specific Role Assignment

A role assignment is the act of attaching a SemanticRole, together
with the associated AllowedUse and ForbiddenUse constraints, to a
data item or fragment within a specific judgment context.

Conceptual flow:

```
raw source data
  → parsed record
  → field / relation extraction
  → context-specific SemanticRole assignment
  → DataAccessProfile selection
  → AllowedUse / ForbiddenUse evaluation
  → consumer-side use
```

Critical non-equivalences:

```
role assignment ≠ Engine mutation
role assignment ≠ evidence registration
role assignment ≠ Claim creation
role assignment ≠ Gap resolution
role assignment ≠ Rule registration
role assignment ≠ final finding publication
```

The same data item may carry different role assignments in different
judgment contexts. This is intentional. A document field that
functions as `observation_evidence` in one context may function as
`required_evidence_spec` in another, with different AllowedUse scopes
in each.

A role assignment is local to a context. It is not a global property
of a record type or a source.

---

## §13 Primary and Secondary Role Boundary

Within a single role assignment context:

```
primary role:
  exactly one SemanticRole assigned per data item

secondary roles:
  zero or more
  each requires an explicit justification
  each remains bounded by its own AllowedUse / ForbiddenUse
```

A secondary role is not a free-form tag, an annotation, or an open
list. Each secondary role is a deliberate, justified interpretation
that carries its own use constraints.

Collecting secondary roles does not produce:

```
multiple truths
multiple Engine states
unlimited tagging
downstream authorization
precedence over the primary role
```

This contract does not freeze field names, storage form, or schema
for primary / secondary role tracking. Those choices are
consumer-side policy.

---

## §14 Traceability Boundary

Each role assignment should, in principle, be traceable to:

```
source identity
record or fragment location
interpretation context
assignment basis
allowed use
forbidden use
```

This contract does not freeze field names, identifiers, or storage
form for traceability metadata. In particular, this contract does
not introduce:

```
RoleAssignment dataclass
database table
JSON schema
serialization format
snapshot field
Engine registry
```

What this contract requires is conceptual traceability, not a
particular implementation. Consumers and adapters are expected to
record enough metadata in their own form to make a role assignment
auditable later.

---

## §15 Consumer / Adapter Boundary

This contract lives on the consumer / adapter side. It does not
describe how the judgment Engine internally represents Claims,
Evidence, Gaps, or Rules. It does not describe how the Engine
computes effective confidence or fires rules.

In particular, this contract does not:

```
speak about Engine internal representations
define new Engine inputs or outputs
modify Engine public method surface
interact with snapshot schema
interact with Claim lifecycle
modify any modifier in the composition formula
```

If a future consumer or adapter wishes to use metadata described by
this contract to drive its own decisions, it does so within consumer
code. The Engine is unaware of and unaffected by this contract.

---

## §16 Relationship to Engine and Existing Contracts

This contract does not alter:

```
ragcore source
Engine public method count   (remains 40)
ragcore.__all__ symbol count (remains 48)
ragcore/types.py contents
snapshot schema_version      (remains 2)
snapshot top-level key count (remains 18)
Claim lifecycle states or transitions
effective confidence formula
rule judgment semantics
```

This contract is also outside the existing proposal pipeline:

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

Metadata described by this contract may be referenced by future
packet construction or prompt construction work. This contract does
not perform that integration. No packet schema is changed.

---

## §17 Ragcore Symbol Boundary

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

All of the above are:

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
code, that promotion requires a separate sequence:

```
thaw policy
→ audit
→ contract revision
→ tests
→ implementation
```

This contract does not authorize such promotion.

---

## §18 Domain-Neutrality Policy

This contract is domain-neutral. Its normative body does not depend
on, name, or privilege any particular consuming domain.

No particular domain defines this contract. A domain may consume this
contract only through external interpretation. Domain-specific record
names are not promoted into framework core vocabulary. Generic record
names are used throughout to illustrate the contract.

This contract has no domain-specific appendix and no domain-specific
case study. Such material, if needed, belongs in a separate
non-normative consumer document or in a separate external adapter
document, not in this contract.

The domain-neutral audit list applied to the normative body of this
contract is defined by prior policy (see PR45-E §3 and PR44-D §5.6).
References to that list from within this contract are quotation,
not normative use.

---

## §19 Anti-Patterns

The following patterns are explicitly forbidden by this contract.

```
AP1.  source_type == semantic_role
      Treating provenance as if it determined role.
      A source does not own a semantic role.

AP2.  base_record_type == semantic_role
      Treating record shape as if it determined role.
      A schema does not own a semantic role.

AP3.  retrieval success == verified evidence
      Treating the fact that a retrieval returned a match
      as a verification outcome.

AP4.  semantic search result == truth
      Treating a similarity match as if it produced truth.

AP5.  access profile == allowed use
      Treating how the data was reached as if it authorized
      what may be done with it.

AP6.  allowed use == automatic action authorization
      Treating a permitted scope as a green light to execute
      tools, mutate Engine state, or bypass operator review.

AP7.  role assignment == Engine mutation
      Treating a consumer-side label as a change to Engine
      truth.

AP8.  claim_candidate == registered Claim
      Treating a proposed claim as if it were a registered
      Claim in the Engine.

AP9.  finding == final verdict
      Treating a draft consumer finding as a final verdict.

AP10. unlimited secondary roles
      Tagging a data item with arbitrary additional roles
      without justification or use constraints.

AP11. domain-specific vocabulary promoted into framework core
      Importing domain-specific terms into the normative body,
      into framework public symbols, or into ragcore.

AP12. one source assigned one permanent semantic role
      Treating an api, tool, or record source as if it
      eternally and globally produced a single role.
```

Each anti-pattern names a real failure mode that this contract is
designed to prevent. A consumer or adapter implementation that
violates any of the above is not aligned with this contract.

---

## §20 Future Handoff Boundary

This contract may enable later work but does not schedule any.

Possible follow-ups, each requiring its own explicit entry directive:

```
PR60 — Role Assignment Policy Spec
PR61 — Minimal Consumer-Side Data Access Profile Example
PR62 — Data Access Profile Validator MVP
external adapter application
```

Conditions on any such follow-up:

```
remain consumer-side
remain domain-neutral in framework normative body
do not mutate Engine
do not add judgment semantics
do not promote conceptual vocabulary without explicit thaw
do not add domain-specific public symbols
```

None of the above are auto-entered by the merging of this contract.

---

## §21 Non-Goals

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
role classifier implementation
automatic role assignment
domain-specific examples
new tests
new example source files
new contract §51 entry
```

---

## §22 Exit Criteria

A merged form of this contract must satisfy:

```
DATA_ACCESS_PROFILE_CONTRACT.md added
doc-only
pytest remains 1183 passing
ragcore source change 0 bytes
new tests 0
new public symbols 0
new Engine behavior 0
Engine public methods remain 40
ragcore.__all__ remains 48
new contract §51 entry not added
snapshot schema unchanged
Claim lifecycle unchanged
effective confidence unchanged
PR49–PR58 unchanged
six independent axes documented
contextual role assignment documented
primary / secondary role boundary documented
AllowedUse / ForbiddenUse safety boundary documented
domain-neutral vocabulary audit passed
domain-specific normative vocabulary count = 0
conceptual names not promoted into ragcore
PR60 / PR61 / PR62 / external adapter not auto-entered
```

---

## Closing Meaning

PR59 defines how external data may be described before consumer use.

```
A source does not own a semantic role.
A record shape does not determine truth.
A retrieval method does not authorize interpretation.
An allowed use does not grant unlimited trust.
```

The contract remains domain-neutral and outside Engine judgment
semantics.
