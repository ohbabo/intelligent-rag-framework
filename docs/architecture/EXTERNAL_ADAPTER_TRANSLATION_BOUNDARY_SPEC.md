# External Adapter Translation Boundary Spec

Framework-level architecture boundary defining how an external
adapter should translate an external representation into a
consumer-side handoff artifact without promoting source-local
structure to framework semantics, hiding translation loss, or
creating Engine authority.

This document is doc-only. It introduces no public symbols, no
ragcore changes, no Engine behavior, no tests, no example source
files, no adapter base class, no adapter Protocol, and no canonical
adapter schema.

---

## §0 Scope Limitation

This spec describes a translation boundary that an external adapter
follows when carrying data toward a consumer-side judgment
workflow. It records what an adapter may do, what an adapter must
not do, how source-local structure remains owned by the adapter,
and how the resulting handoff arrives at consumer review without
creating Engine truth.

This spec does not implement, schedule, or authorize any of:

- ragcore source modification
- new public symbol in `ragcore.__all__`
- adapter base class or Protocol definition
- adapter registry or factory
- canonical adapter input / output schema
- packet schema or proposal schema change
- existing validator modification
- PR61 example or PR62 validator modification
- external adapter implementation
- source connector
- network access
- file reader / database integration
- retrieval implementation
- LLM adapter
- role classifier
- semantic correctness validator
- numerical confidence or probability
- Engine integration path

This spec is adapter-side and domain-neutral. Any particular
external source or consuming domain is one possible case among
many; it does not define the boundary.

---

## §1 Purpose

PR59 separated the six independent interpretation axes. PR60
defined the policy a consumer follows when assigning a role within
a specific judgment context. PR61 demonstrated one local consumer
representation. PR62 added a boundary validator over that local
representation.

What remained unlocked was the boundary that an adapter follows
when carrying an external representation toward this consumer
side. Without that boundary, a single source's structure may
silently solidify into framework structure, source-local
vocabulary may be treated as framework semantics, lossy steps may
be hidden behind normalization, and validated output may be
treated as authoritative truth.

PR63 records those boundaries before any particular adapter is
built. Implementation of any external adapter remains out of
scope.

---

## §2 Baseline

```
main:                       c1529e5
tests:                      1202 passing
predecessor stack:          PR49 – PR62
```

PR49 through PR62 remain unchanged by this spec:

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
PR60 role assignment policy spec        unchanged
PR61 minimal consumer example           unchanged
PR62 boundary validator + tests         unchanged
```

```
ragcore source:             unchanged
Engine public methods:      40
Engine private methods:     18
ragcore.__all__:            48
snapshot schema_version:    2
snapshot top-level keys:    18
```

---

## §3 Core Boundary Statements

The spec is governed by five primary locks and one generality
lock.

```
1. An adapter translates external representation.
   It does not translate uncertainty into truth.

2. Adapter-local mappings remain adapter-owned.
   They do not become framework semantics merely because
   the framework consumes their output.

3. Every lossy transformation must be explicit and traceable.

4. A structurally valid adapter output does not authorize
   Engine mutation, lifecycle transition, tool execution,
   or final judgment.

5. When external context is insufficient, the adapter must
   preserve unresolved interpretation rather than manufacture
   a complete assignment.
```

Generality lock:

```
No external source or domain defines the framework adapter
boundary.
```

Where a later section seems to allow a shortcut (such as treating
adapter mapping as semantic truth, validation pass as acceptance,
or normalization as a license to drop uncertainty), that shortcut
is explicitly forbidden by these locks.

---

## §4 Relationship to PR59 – PR62

```
PR59  separated the interpretation axes
PR60  defined contextual role-assignment policy
PR61  demonstrated one local consumer representation
PR62  added a boundary validator over that representation
PR63  records the boundary an adapter follows when translating
      external representation into a consumer-side handoff
```

PR63 does not merge prior contracts. The following automatic
equivalences remain forbidden after PR63:

```
adapter mapping               =  SemanticRole truth        forbidden
adapter output                =  verified evidence         forbidden
validator pass                =  accepted interpretation   forbidden
consumer representation       =  Engine object             forbidden
source-local record type      =  framework BaseRecordType  forbidden
source-local field name       =  framework required field  forbidden
```

A consumer may use adapter output as one input among many. The
adapter does not produce truth.

---

## §5 Adapter Definition

In this spec, an adapter is conceptually an external component
that performs the following:

```
read an external representation
identify source-local structure
preserve provenance
normalize selected data
record translation decisions
surface unresolved information
produce a consumer-side handoff artifact
```

An adapter is not:

```
a truth engine
a semantic authority
a Claim lifecycle controller
a rule evaluator
an operator replacement
a tool executor
a final report publisher
```

Lock:

```
An adapter owns translation mechanics.
It does not own framework truth.
```

This spec does not freeze a particular adapter interface. It
records the responsibility an adapter carries; the shape an
adapter takes is implementation-side.

---

## §6 Input Boundary

Adapter input may arrive in many forms. Illustrative shapes:

```
document
record
field collection
event stream item
API response
file fragment
operator-provided item
derived external artifact
```

This spec does not freeze input types or schemas. In particular,
this spec does not introduce:

```
AdapterInput dataclass
AdapterInput TypedDict
JSON Schema for input
Protocol declaration
abstract base class
required constructor signature
framework adapter registry
```

Source structure is adapter-local. The adapter understands its
source. The framework does not.

---

## §7 Output Boundary

Adapter output may, conceptually, include one or more of:

```
normalized consumer data
provenance record
record-shape description
interpretation-context input
candidate contextual assignment
unresolved assignment representation
translation notes
loss notes
traceability links
```

This spec does not freeze output schemas. In particular, this
spec does not define:

```
AdapterOutput class
canonical dictionary keys
official serialization format
required framework payload
Engine ingestion payload
```

Lock:

```
Adapter output is a handoff artifact, not an Engine-owned object.
```

The adapter delivers material that consumer code reads and
reviews. Engine state is not changed by the act of receiving
adapter output.

---

## §8 Translation Stages

The spec records ten conceptual translation stages. The stages are
normative as a *sequence of responsibilities*, not as a
serialization format. No field names or data types are frozen.

### Stage 1 — Identify the external item

Before attaching meaning or role, the adapter identifies the
translation target. The target may be:

```
source
record
field
fragment
relation
derived item
```

Lock:

```
The translation target must be identifiable.
```

A whole source receiving one permanent role by default is rejected
by the lock on Stage 4 (record shape) and the lock on Stage 5
(no semantic promotion).

### Stage 2 — Preserve source provenance

At minimum, the adapter must be able to support the following
trace:

```
where the item came from
which source-local identifier located it
when or under which retrieval context it was obtained
which adapter handled it
```

Field names are not frozen. What matters is conceptual presence.

### Stage 3 — Preserve the source-local representation

Full copies of the source are not always required. At least one
of the following must remain available:

```
reference to the original item
stable locator
content digest
source-owned identifier
immutable snapshot reference
```

Lock:

```
A normalized output must not become
the only unexplained surviving representation.
```

If the normalized output is the only surviving form and the
original is unrecoverable, the loss must be disclosed (see §14).

### Stage 4 — Describe record shape separately

The adapter records the source-local structural type of the
record alongside any normalized record-shape description.

Examples (illustrative, not normative names):

```
source-local record type
normalized record-shape description
field-level shape information
```

Lock:

```
Record shape constrains translation.
It does not determine semantic role.
```

### Stage 5 — Normalize without semantic promotion

The adapter may perform structural normalization:

```
rename fields
convert encodings
normalize timestamps
split compound records
combine explicitly related fields
normalize identifiers
extract a selected fragment
```

The adapter does not, via normalization, promote a result to:

```
verified fact
Engine evidence
registered Claim
final finding
```

Normalization is shape work. Semantic promotion is not shape work.

### Stage 6 — Record translation decisions

Each explainable translation has a conceptual basis:

```
what changed
why it changed
what source information was retained
what information was dropped
what ambiguity remains
```

The exact explanation field is not frozen.

### Stage 7 — State interpretation context

Any output that participates in role assignment is bound to a
context. Without a context, role is not completed.

Conceptual context inputs:

```
current question
current consumer
current review purpose
known restrictions
```

If the adapter cannot determine the context, it does not invent
one.

### Stage 8 — Produce resolved or unresolved handoff

With sufficient context:

```
one contextual primary role may be represented
```

With insufficient context:

```
primary role remains withheld
candidate interpretations may remain local
allowed use is reduced
downstream transition remains blocked
```

The adapter does not fill a withheld primary with the most
convenient candidate.

### Stage 9 — Validate mechanically observable boundaries

A consumer-side validator may inspect the adapter output for
structural and exact-conflict boundaries.

```
validation pass  !=  semantic correctness
validation pass  !=  source truth
validation pass  !=  Engine acceptance
```

The validator at this stage is a boundary check, not a verdict.

### Stage 10 — Hand off for review

The adapter's normal terminal point is a consumer-side handoff.

```
adapter output
  -> consumer validation
  -> operator or consumer review
```

If Engine state is to change, that change goes through the
existing official API and all prior contracts. The adapter does
not perform the change.

---

## §9 Source-Local Mapping Ownership

The adapter may map source-local labels onto consumer-side terms.

Illustrative directional mappings:

```
source-local field           -> normalized local field
source-local record label    -> local record-shape descriptor
source-local relation        -> local traceable relation
```

Lock:

```
A source-local mapping does not become a framework-level ontology.
```

Forbidden promotions:

```
source field name promoted as a framework required field
source record type promoted as a BaseRecordType definition
source category used in place of a SemanticRole enum
adapter mapping table promoted into a ragcore registry
```

Adapter mappings remain adapter-owned. They do not appear in
ragcore. They do not appear in PR59, PR60, or PR62. They do not
appear in `ragcore.__all__` or in framework public surface.

---

## §10 Provenance Preservation

Conceptual provenance metadata for every translated item:

```
source identifier
locator within the source
acquisition reference (time / retrieval context)
adapter identity
adapter revision
```

This spec does not freeze field names, identifiers, or storage
form for provenance metadata. In particular, this spec does not
introduce:

```
ProvenanceRecord dataclass
provenance schema
provenance public symbol
ragcore provenance API
```

What is required is conceptual presence. The shape is
adapter-side and consumer-side, not framework-side.

---

## §11 Source Representation Retention

Source retention exists to make the translation reviewable later.
Acceptable retention forms:

```
direct retention of the original item
stable locator that resolves to the original
content digest that allows comparison
identifier that the source still honors
immutable snapshot reference
```

Forbidden behavior:

```
silent loss of the original
normalized output presented as the only surviving form without
   disclosure
retention removed across adapter revisions without traceability
```

Retention is a property of the translation, not a feature of
framework code.

---

## §12 Translation Decision Boundary

Each translation decision conceptually answers:

```
why this fragment
why this normalization
why this candidate label (if any)
why this loss is acceptable
why this ambiguity is preserved
```

Lock:

```
An unexplained translation is not a valid translation.
```

This spec does not freeze a particular explanation schema. What
is required is conceptual auditability.

---

## §13 Translation Ledger Boundary

Each adapter translation may be conceptually summarized as a
ledger entry containing:

```
input reference
output reference
transformation description
retained information
dropped information
derived information
unresolved information
adapter identity or revision
```

This spec does not introduce:

```
TranslationLedger class
ledger schema
ledger database table
ledger serialization format
ledger public API
```

Lock:

```
Traceability is required as a property.
A specific traceability schema is not frozen.
```

---

## §14 Loss Policy

Translation may be lossless or lossy. Possible loss shapes:

```
field omission
format conversion
record splitting
record aggregation
text extraction
normalization of source identifiers
removal of source-only decoration
```

Policy:

```
loss must be explicit
loss must be reviewable
loss must not be hidden behind normalization
loss must not silently broaden semantic meaning
```

Forbidden:

```
dropped field treated as if it had never existed
aggregation followed by erased source boundaries
derived value displayed as a direct source value
normalization used to remove uncertainty
```

This spec does not freeze a particular loss-disclosure schema.
What is required is that the loss is reviewable later.

---

## §15 Derivation Boundary

When the adapter computes or combines a new value from source
inputs:

```
the derived information must remain distinguishable from
directly retained source information
```

Conceptual distinction:

```
retained
normalized
derived
unresolved
```

This spec does not introduce an enum or status type for these
categories. The distinction is conceptual.

Forbidden:

```
derived output presented as source fact
derived relation presented as a directly observed relation
calculated label presented as a source-owned label
```

---

## §16 Ambiguity Preservation

The adapter may encounter:

```
missing source field
ambiguous source field
conflicting records
incomplete provenance
unsupported record variant
multiple plausible interpretations
unknown transformation loss
```

Required responses (one or more):

```
preserve unresolved state
reduce allowed use
record missing information
request more context
block downstream transition
retain competing local candidates
```

Forbidden responses:

```
choose the most convenient interpretation
fill missing fields with invented values
convert ambiguity into numerical confidence
use source popularity as semantic proof
use LLM wording as source evidence
```

PR63 does not introduce a new confidence or probability system. It
does not introduce an `UNRESOLVED` enum, status type, or schema.
Conceptual preservation of the unresolved state is required;
storage form is adapter-side and consumer-side.

---

## §17 Allowed Adapter Behavior

The adapter may perform:

```
parse source-local formats
normalize source-local encodings
identify fragments
preserve provenance
create stable trace references
describe record shape
construct interpretation context
represent local candidate roles
preserve unresolved output
emit translation and loss notes
invoke a consumer-side structural validator
```

Each allowed behavior stays inside the adapter-side translation
range. None of them, individually or in combination, transition
into Engine authority.

---

## §18 Forbidden Adapter Behavior

The adapter must not, directly or transitively, perform:

```
create Engine truth
register a Claim automatically
add Engine evidence automatically
resolve a Gap automatically
register a Rule automatically
change Claim lifecycle status
change effective confidence
modify snapshot
execute tools because of a role assignment
publish a final verdict
bypass operator review
promote local mapping into ragcore
```

Lock:

```
Translation authority is not mutation authority.
```

---

## §19 Consumer Handoff Boundary

The adapter's normal end state is a handoff to consumer code.

```
adapter output
  -> consumer parses what it understands
  -> consumer-side structural validator (optional)
  -> consumer-side review or operator review
```

What this handoff is not:

```
not an Engine write
not a Claim registration
not a Rule registration
not a downstream execution
not a final verdict
not a confidence assignment
```

The adapter does not invoke Engine state-mutating methods. If a
consumer chooses to escalate adapter output into Engine state,
that escalation follows the existing public API and the
preexisting contracts.

---

## §20 Relationship to Engine

```
External adapter
  -> consumer-side translation
  -> consumer-side validation
  -> review
```

Engine boundary:

```
adapter output does not enter Engine merely by existing
adapter output does not enter Engine merely by passing validation
adapter role label does not equal Engine status
adapter finding does not equal a registered Claim
```

Changes to Engine state require a separate, deliberate call into
the Engine's existing official API, subject to all preexisting
contracts and gates.

PR63 does not design that call.

---

## §21 Relationship to Proposal Pipeline

The proposal pipeline established in PR49 through PR58 is
unchanged by this spec.

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

If a later PR wishes to use adapter output as part of packet
construction or as a proposal input, that integration belongs to
that later PR. PR63 does not perform the integration. No packet
schema and no proposal schema is changed.

PR63 does not define:

```
adapter-to-packet converter
packet field mapping
proposal input mapping
prompt construction
operator workflow extension
```

---

## §22 Relationship to PR62 Validator

PR62 added a validator over the PR61 local representation. PR63
does not redefine, replace, or extend that validator.

```
PR62 validator inspects the PR61 representation shape and exact
  contradictions only.

PR62 is not a universal framework adapter validator.

Other adapter outputs may have other local validators.
```

Lock:

```
A local validator follows a local representation.
It does not make that representation canonical.
```

An adapter may invoke a PR62-style local validator if its output
happens to follow the PR61 representation. If the adapter follows
a different representation, a different local validator applies.
Neither situation makes the chosen local representation
authoritative for all adapters.

---

## §23 Adapter Revision Boundary

Adapter behavior may evolve. Conceptual identifiers:

```
adapter identity
adapter version or revision
mapping revision
translation time or run reference
```

This spec does not freeze a version format. It does require
traceability across revisions.

Forbidden:

```
unversioned semantic mapping change
mapping behavior change without traceability
old and new translations treated as identical without review
```

When the adapter behavior changes such that the same source now
translates to a different output, the change must be locatable
later.

---

## §24 Determinism Boundary

This spec does not impose universal determinism on adapters. Some
adapter implementations may be deterministic; others may not.

What is required:

```
non-deterministic translation behavior must be disclosed
external dependencies must be traceable
different outputs must remain attributable
```

If a future adapter uses an LLM or a similar non-deterministic
component:

```
LLM output is a proposal or interpretation artifact
not proof of semantic correctness
```

PR63 does not authorize an LLM-based adapter. PR63 records the
boundary that any such future adapter would be subject to.

---

## §25 Failure Boundary

The following failure shapes are conceptually distinct:

```
source read failure
parse failure
unsupported source shape
translation failure
incomplete provenance
unresolved interpretation
consumer validation failure
```

They are not collapsed into a single `invalid` category by
default.

This spec does not introduce an error code taxonomy or an
exception hierarchy. What is required is that operational failure
and semantic ambiguity are not represented as the same condition.

Lock:

```
Operational failure and semantic ambiguity must not be
represented as the same condition by default.
```

---

## §26 Domain-Neutrality Policy

This spec is domain-neutral. Its normative body does not depend
on, name, or privilege any particular external source or
consuming domain.

The normative body must contain zero unintended occurrences of
the following audit list (the list itself is quoted here as
reference, not used as content):

```
cerberus / cve / cpe / kev / nvd / epss / openssh
vulnerability / exploit / scanner / nmap
host / port / service / asset / forensic
```

The audit list is inherited from PR45-E §3 and PR44-D §5.6.
References to it from this section, and from any dev record
quoting it, are quotation, not normative use. The audit applies
to:

```
section titles
general prose
normative sentences
stage descriptions
anti-pattern descriptions
future handoff text
closing meaning
```

It excludes the explicit forbidden-vocabulary quotation in this
§26 itself and the same quotation in the dev record.

This spec contains no domain-specific appendix, no
domain-specific mapping table, no domain-specific record preset,
no domain-specific role preset, and no domain-specific public
symbol.

A particular domain may own its own external adapter; that
adapter does not redefine framework policy.

---

## §27 Conceptual Vocabulary Boundary

The following identifiers exist only as conceptual vocabulary in
this spec:

```
ExternalAdapter
TranslationBoundary
TranslationDecision
TranslationLedger
TranslationLoss
SourceLocalMapping
ConsumerHandoff
AdapterRevision
```

For all of the above:

```
NOT a ragcore type
NOT in ragcore.__all__
NOT in ragcore/types.py
NOT Engine state
NOT a lifecycle state
NOT a snapshot schema field
NOT a public adapter interface
NOT a frozen serialization schema
```

If a future PR wishes to promote any of these names into ragcore
or into a public adapter API, that promotion requires its own
sequence:

```
thaw policy
  -> audit
  -> contract revision
  -> tests
  -> implementation
```

PR63 does not authorize such promotion.

---

## §28 Anti-Patterns

The following patterns are explicitly forbidden by this spec.

```
AP1.  Source field mapped directly to SemanticRole truth
      A field name from a source becomes a role label and is
      treated as verified.

AP2.  Source record type treated as framework BaseRecordType
      definition
      A source-local record category is promoted into framework
      shape ontology.

AP3.  Adapter output treated as verified evidence
      Existence of adapter output is treated as semantic
      verification.

AP4.  Validator pass treated as semantic acceptance
      A structural validator pass is treated as an interpretation
      verdict.

AP5.  Lossy transformation performed without disclosure
      Loss is folded into normalization and disappears from the
      record.

AP6.  Derived value presented as directly retained source data
      Computed values appear indistinguishable from source values.

AP7.  Multiple source items merged without traceable boundaries
      Aggregation erases per-source identity.

AP8.  Missing context filled with fabricated values
      Gaps are closed by invention instead of by ambiguity
      preservation.

AP9.  Ambiguity converted into numerical confidence
      Unresolved interpretation is hidden behind a confidence
      figure.

AP10. Adapter-local vocabulary promoted into ragcore
      Local labels become framework-level public names.

AP11. Adapter directly mutates Engine state
      The adapter calls Engine state-changing methods.

AP12. Adapter output triggers tool execution
      The adapter chains its output into an action runner.

AP13. Adapter bypasses operator review
      The adapter routes around the review boundary established
      in PR57.

AP14. One domain adapter used as the universal adapter contract
      A single domain adapter is treated as if it defined the
      adapter boundary for all domains.

AP15. PR61 local dictionary treated as mandatory adapter output
      The PR61 illustrative representation is treated as
      canonical adapter output structure.

AP16. Adapter mapping changed without revision traceability
      Behavior changes silently across adapter versions.

AP17. Operational failure collapsed into semantic ambiguity
      A read or parse failure is reported as if it were an
      interpretation gap.

AP18. LLM explanation treated as translation proof
      Natural-language rationale from an LLM is treated as
      evidence of correct translation.
```

Each anti-pattern names a real failure mode this spec prevents.

---

## §29 Future Handoff Boundary

This spec may enable later work but does not schedule any.

Possible follow-ups, each requiring its own explicit entry
directive:

```
PR64 — Minimal Domain-Neutral External Adapter Example
PR65 — Adapter Translation Boundary Validator MVP
domain-owned external adapter
Engine integration path
```

PR64 candidate entry conditions:

```
consumer-side only
domain-neutral synthetic source
plain dict / list representation
no base class
no Protocol
no ragcore import
no Engine calls
explicit provenance
explicit translation notes
explicit loss notes
resolved or unresolved handoff
```

PR65 candidate entry conditions:

```
checks local adapter example shape only
checks missing traceability and exact contradictions only
does not verify source truth
does not judge semantic role correctness
does not create a canonical adapter schema
remains ragcore-free
```

Domain-owned adapter conditions:

```
lives outside normative framework policy
owns its source vocabulary
preserves source-to-output traceability
does not promote local terms into ragcore
does not mutate Engine automatically
```

None of the above are auto-entered by the merging of this spec.

---

## §30 Non-Goals

This PR does not perform:

```
ragcore source modification
Engine method addition
public framework symbol addition
snapshot modification
lifecycle modification
effective-confidence modification
rule-semantic modification
adapter base class
adapter Protocol
adapter registry
adapter factory
canonical adapter schema
AdapterInput type
AdapterOutput type
TranslationLedger type
JSON Schema
dataclass
Enum
TypedDict
Pydantic
source connector
network access
file reader
database integration
retrieval implementation
LLM adapter
role classifier
semantic correctness validator
numerical confidence
probability
packet schema change
proposal schema change
PR61 modification
PR62 modification
domain-specific example
new tests
new example source file
external adapter implementation
Engine integration
```

---

## §31 Exit Criteria

A merged form of this spec must satisfy:

```
EXTERNAL_ADAPTER_TRANSLATION_BOUNDARY_SPEC.md added
doc-only
exactly one tracked file changed
pytest remains 1202 passing
ragcore source delta 0 bytes
new tests 0
new framework public symbols 0
new Engine behavior 0
Engine public methods remain 40
Engine private methods remain 18
ragcore.__all__ remains 48
snapshot schema unchanged
Claim lifecycle unchanged
effective confidence unchanged
rule judgment semantics unchanged
PR51 – PR62 unchanged
adapter input boundary documented
adapter output boundary documented
ten translation stages documented
source-local mapping ownership documented
provenance preservation documented
source representation retention documented
translation decision boundary documented
translation ledger remains conceptual
loss policy documented
retained / normalized / derived distinction documented
ambiguity preservation documented
consumer handoff boundary documented
validation-pass non-authority documented
Engine non-mutation boundary documented
proposal pipeline unchanged
adapter revision boundary documented
determinism disclosure boundary documented
failure vs ambiguity distinction documented
domain-specific normative vocabulary count 0 unintended
  occurrences
conceptual vocabulary not promoted into ragcore
no adapter interface or schema frozen
PR64 / PR65 not auto-entered
domain-owned adapter not auto-entered
Engine integration not auto-entered
```

---

## Closing Meaning

PR63 records the boundary that an external adapter follows when
carrying an external representation toward consumer review.

```
An adapter may translate representation.

It may not translate uncertainty into truth,
local vocabulary into framework semantics,
or validated output into Engine authority.
```

The boundary remains domain-neutral, adapter-side, and outside
Engine judgment semantics.

---

## §32 Post-M06 addendum (PR75-M06, 2026-06-19)

PR75-M06 (`DOWNSTREAM_RESULT_REENTRY_CONTRACT.md`) closes the
conceptual boundary for OC-E (M01 Lane C, stages C2 ~ C7) by
defining how a downstream investigation result becomes
eligible for an explicit Engine state-mutating invocation. The
result trace from such an investigation is, in PR59 / PR63
terms, **a new external source artifact**.

```
- A downstream investigation result re-enters the framework
  as a NEW external source artifact. The PR63 §3 ~ §9
  obligations (provenance / retention / loss / derivation /
  unresolved ambiguity / failure) apply to that artifact
  unchanged. The downstream result does NOT continue a prior
  proposal subject or a prior decision subject; it is its own
  source.

- An investigation result adapter (consumer-side adapter that
  ingests a downstream tool's or process's output) is one
  adapter under PR63. It is NOT a "canonical adapter" — PR59 /
  PR63 declare no canonical adapter, and PR75-M06 does not
  add one.

- The adapter's output is NOT a `ragcore.Evidence`, NOT a
  `ragcore.Claim`, NOT a `ragcore.Gap`, NOT a
  `ragcore.Relation`, and NOT a `ReviewedMutationRequest`.
  This restates PR59 / PR63's locks for the result-adapter
  case.

- The adapter does NOT call any Engine state-mutating public
  method. Re-entry into Engine state is governed by
  PR75-M06 §4.4 / §4.5 / §4.6: candidate materialization
  consideration -> M02 §9 mutation review -> M05 mutation-
  review-family decision record -> M05 §7 state revalidation
  -> M02 §12 explicit invocation. The adapter participates
  only at the trace-translation layer.

- Operational failure (tool failed to run, parse failed,
  unsupported shape, translation failed) and semantic
  ambiguity (role unresolved, intended use unclear) are
  distinct PR63 conditions and PR75-M06 §7 preserves the
  distinction. They MUST NOT be collapsed into a single
  `invalid` / `unresolved` label.
```

PR75-M06 does not modify any of §1 ~ §31 of this spec, the
PR63 boundary, or the §28 anti-patterns. §28 ~ §31 historical
body and §0 ~ §27 normative body remain unchanged.
