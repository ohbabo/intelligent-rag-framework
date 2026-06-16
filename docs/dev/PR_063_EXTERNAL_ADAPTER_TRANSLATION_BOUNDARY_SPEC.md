# PR63 — External Adapter Translation Boundary Spec

Development record for the external adapter translation boundary
introduced in PR #64 (branch
`docs/external-adapter-translation-boundary`).

```
base:            main c1529e5 (PR62: Role Assignment Boundary
                                Validator MVP)
branch:          docs/external-adapter-translation-boundary
212차 commit:     25b951e
213차 commit:     (this record, docs/dev)
PR:              #64
type:            framework-level architecture boundary, doc-only
```

This record captures the boundary that an external adapter
follows when carrying an external representation toward
consumer-side review, the relationship to PR59 – PR62, the six
governing locks, the ten translation stages, the verification
results, and the closing position that ended PR63. This record
does not redesign PR63.

---

## §1 Purpose

PR59 separated the six independent interpretation axes. PR60
defined the policy a consumer follows when assigning a role
within a context. PR61 demonstrated one local consumer
representation. PR62 added a boundary validator over that local
representation.

PR63 records the boundary an adapter follows when carrying an
external representation toward this consumer-side workflow.
Without that boundary, a single source's structure may silently
solidify into framework structure, source-local vocabulary may
be treated as framework semantics, lossy steps may be hidden
behind normalization, and structurally valid output may be
treated as authoritative truth.

PR63 is doc-only. It introduces no adapter implementation, no
adapter base class, no adapter Protocol, no adapter registry, no
canonical adapter schema, no public framework symbol, and no
ragcore change.

---

## §2 Baseline

```
base:                       main c1529e5
                              (PR62: Role Assignment Boundary
                               Validator MVP)
baseline tests:             1202 passing
predecessor stack:          PR49 – PR62
```

212차 added `docs/architecture/EXTERNAL_ADAPTER_TRANSLATION_
BOUNDARY_SPEC.md` (`+1324` lines). 213차 adds this record. No
other files are touched.

---

## §3 Files Changed

```
docs/architecture/EXTERNAL_ADAPTER_TRANSLATION_BOUNDARY_SPEC.md
                                            +1324 lines   (212차)
docs/dev/PR_063_EXTERNAL_ADAPTER_TRANSLATION_BOUNDARY_SPEC.md
                                            this record   (213차)

ragcore source:               0 bytes changed
tests:                        0 added
framework public symbols:     0 added
Engine behavior:              0 added
example source files:         0 added
```

Single staged file per cycle. `ragcore.egg-info/` excluded as an
untracked build artifact.

212차 commit: `25b951e docs(architecture): define external
adapter translation boundary`.
213차 commit: this record.

---

## §4 Core Boundary Locks

The spec is governed by five primary locks plus one generality
lock:

```
1. An adapter translates external representation.
   It does not translate uncertainty into truth.

2. Adapter-local mappings remain adapter-owned.
   They do not become framework semantics merely because the
   framework consumes their output.

3. Every lossy transformation must be explicit and traceable.

4. A structurally valid adapter output does not authorize
   Engine mutation, lifecycle transition, tool execution, or
   final judgment.

5. When external context is insufficient, the adapter must
   preserve unresolved interpretation rather than manufacture
   a complete assignment.

Generality:
   No external source or domain defines the framework adapter
   boundary.
```

These six locks govern every section of the spec. The dev
record honors the same locks; it does not soften them via
phrasing such as "adapter validates external truth", "adapter
produces verified evidence", "adapter decides SemanticRole",
"adapter prepares Engine-ready truth", or "adapter output is
accepted after validation".

Lock honored throughout the spec and this record:

```
Translation authority is not mutation authority.
```

---

## §5 PR59 – PR63 Layering

```
PR59  separated the interpretation axes
PR60  defined contextual role-assignment policy
PR61  demonstrated one local consumer representation
PR62  added a boundary validator over that representation
PR63  recorded the boundary an adapter follows when translating
      external representation into a consumer-side handoff
```

PR63 sits **parallel** to PR59 – PR62, not as a serial layer
over them. The proposal pipeline (PR51 – PR58), the data-access
contract (PR59), the role-assignment policy (PR60), the local
example (PR61), and the local validator (PR62) are all unchanged.

Forbidden automatic equivalences (PR63 does not relax):

```
adapter mapping              =  SemanticRole truth        forbidden
adapter output               =  verified evidence         forbidden
validator pass               =  accepted interpretation   forbidden
consumer representation      =  Engine object             forbidden
source-local record type     =  framework BaseRecordType  forbidden
source-local field name      =  framework required field  forbidden
```

A consumer may use adapter output as one input among many. The
adapter does not produce truth.

---

## §6 Adapter Input / Output Boundary

Adapter input may arrive in many illustrative forms (document /
record / field collection / event stream item / API response /
file fragment / operator-provided item / derived external
artifact). The spec freezes no input type or schema. In
particular, no `AdapterInput` dataclass, `TypedDict`, JSON
Schema, Protocol, abstract base class, or framework adapter
registry is introduced.

Adapter output may conceptually include normalized consumer
data, provenance record, record-shape description,
interpretation-context input, candidate contextual assignment,
unresolved assignment representation, translation notes, loss
notes, or traceability links. The spec freezes no output schema.
No `AdapterOutput` class, canonical dictionary keys, official
serialization format, required framework payload, or Engine
ingestion payload is defined.

Lock:

```
Adapter output is a handoff artifact, not an Engine-owned object.
```

---

## §7 Ten Translation Stages

The spec records ten translation stages as a sequence of
responsibilities (not as a serialization format). The dev record
preserves the order and the boundary at each stage.

```
Stage 1   Identify the external item
            target must be identifiable; whole-source default
            role is rejected
Stage 2   Preserve source provenance
            conceptual presence required (where / locator /
            when / adapter identity); field names not frozen
Stage 3   Preserve source-local representation
            at least one of: reference / stable locator /
            content digest / source-owned id / immutable
            snapshot reference; otherwise the loss is disclosed
Stage 4   Describe record shape separately
            record shape constrains translation, not role
Stage 5   Normalize without semantic promotion
            shape work only; normalization does not promote
            to verified fact / Engine evidence / registered
            Claim / final finding
Stage 6   Record translation decisions
            conceptual basis required (what / why / retained /
            dropped / ambiguity); explanation schema not frozen
Stage 7   State interpretation context
            no context means no completed role; the adapter
            does not invent a context
Stage 8   Produce resolved or unresolved handoff
            with sufficient context, one contextual primary role
            may be represented; with insufficient context,
            primary remains withheld and allowed use is reduced
Stage 9   Validate mechanically observable boundaries
            validation pass  !=  semantic correctness
            validation pass  !=  source truth
            validation pass  !=  Engine acceptance
Stage 10  Hand off for consumer review
            Engine writes go through the existing official API
            and pre-existing contracts; the adapter does not
            perform the write
```

Boundary notes per stage:

```
Stage 4 boundary:   record shape does not determine role
Stage 5 boundary:   normalization does not promote truth
Stage 8 boundary:   insufficient context does not force a primary
Stage 9 boundary:   validation pass does not establish correctness
Stage 10 boundary:  handoff does not perform Engine mutation
```

---

## §8 Source-Local Mapping Ownership

The adapter may map source-local labels onto consumer-side
terms. The mappings remain adapter-owned.

```
source-local field          ->  normalized local field
source-local record label   ->  local record-shape descriptor
source-local relation       ->  local traceable relation
```

Forbidden promotions:

```
source field name           ->  framework required field
source record type          ->  BaseRecordType definition
source category             ->  SemanticRole enum
adapter mapping table       ->  ragcore registry
```

The dev record refers to these mappings as **adapter-owned
source-local mappings**, not "framework mappings".

---

## §9 Provenance and Source Retention

Conceptual provenance metadata (no schema freeze):

```
source identifier
locator within the source
acquisition reference (time / retrieval context)
adapter identity
adapter revision
```

No `ProvenanceRecord` dataclass, public schema, or ragcore
provenance API is introduced.

Source retention forms (at least one must remain available):

```
direct retention of the original item
stable locator that resolves to the original
content digest that allows comparison
identifier that the source still honors
immutable snapshot reference
```

Forbidden retention behavior:

```
silent loss of the original
normalized output presented as the only surviving form without
   disclosure
retention removed across adapter revisions without traceability
```

Retention is a property of the translation, not a feature of
framework code.

---

## §10 Translation Decisions and Ledger Boundary

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

The spec mentions a **translation ledger** as a conceptual
summary (input ref / output ref / transformation desc /
retained / dropped / derived / unresolved / adapter identity or
revision). PR63 does NOT introduce a `TranslationLedger` class,
ledger schema, ledger database table, ledger serialization
format, or ledger public API.

Allowed phrasing about the ledger:

```
conceptual ledger
reviewable translation record
traceability property
```

Forbidden phrasing about the ledger:

```
ledger object
ledger schema
required ledger payload
framework ledger API
TranslationLedger instance
```

Lock:

```
Traceability is required as a property.
A specific traceability schema is not frozen.
```

---

## §11 Loss and Derivation Boundary

Loss policy:

```
explicit
reviewable
not hidden behind normalization
does not silently broaden semantic meaning
```

Forbidden loss behavior:

```
dropped field treated as if it had never existed
aggregation followed by erased source boundaries
derived value displayed as a direct source value
normalization used to remove uncertainty
```

Derivation boundary:

```
retained
normalized
derived
unresolved
```

is conceptual only. PR63 does NOT introduce an enum, status
type, confidence type, framework field, or ragcore type for
these categories.

```
Derived information remains distinguishable from directly
retained source information.
```

Forbidden derivation phrasing:

```
derived output presented as source fact
derived relation presented as a directly observed relation
calculated label presented as a source-owned label
```

---

## §12 Ambiguity Preservation

When the adapter encounters missing source field, ambiguous
source field, conflicting records, incomplete provenance,
unsupported record variant, multiple plausible interpretations,
or unknown transformation loss, the response is one or more of:

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

PR63 does NOT introduce:

```
a new confidence or probability system
an UNRESOLVED enum
an UNRESOLVED status type or schema
```

Conceptual preservation of the unresolved state is required;
storage form is adapter-side and consumer-side.

---

## §13 Allowed and Forbidden Behavior

Allowed (11):

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

Forbidden (12):

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

---

## §14 Consumer Handoff

```
adapter output
  -> consumer parses what it understands
  -> consumer-side structural validator (optional)
  -> consumer-side review or operator review
```

The handoff is **not**:

```
an Engine write
a Claim registration
a Rule registration
a downstream execution
a final verdict
a confidence assignment
```

If a consumer chooses to escalate adapter output into Engine
state, the escalation goes through the existing official Engine
API subject to all preexisting contracts.

---

## §15 Engine Non-Mutation Boundary

Four boundary statements from §20 of the spec:

```
adapter output does not enter Engine merely by existing
adapter output does not enter Engine merely by passing validation
adapter role label does not equal Engine status
adapter finding does not equal a registered Claim
```

Engine state changes are:

```
separate
deliberate
official-API calls
subject to preexisting contracts and gates
```

PR63 does NOT design that call path.

---

## §16 Proposal-Pipeline Relationship

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

PR63 does NOT define:

```
adapter-to-packet converter
packet field mapping
proposal input mapping
prompt construction
operator workflow extension
```

---

## §17 PR62 Local-Validator Relationship

```
PR62 validates the PR61 local representation.
PR62 is not a universal adapter validator.
```

An adapter whose output happens to follow the PR61
representation may invoke a PR62-style local validator. A
different adapter following a different representation uses a
different local validator. Neither situation makes the chosen
local representation authoritative for all adapters.

Forbidden phrasing:

```
all adapters must output PR61 dictionaries
all adapter outputs must pass PR62
PR62 defines the framework adapter schema
```

Lock:

```
A local validator follows a local representation.
It does not make that representation canonical.
```

---

## §18 Revision and Determinism Boundary

Adapter revision (conceptual identifiers, no format freeze):

```
adapter identity
adapter version or revision
mapping revision
translation time or run reference
```

Forbidden:

```
unversioned semantic mapping change
mapping behavior change without traceability
old and new translations treated as identical without review
```

Determinism boundary:

```
non-deterministic translation behavior must be disclosed
external dependencies must be traceable
different outputs must remain attributable
```

PR63 does NOT impose universal determinism. PR63 does NOT
authorize an LLM-based adapter. Any future adapter using an
LLM-like component would be subject to the same locks, with
LLM output treated as a proposal or interpretation artifact and
not as proof of semantic correctness.

The dev record does not overstate the requirement:

```
not   "all adapters must be deterministic"
not   "same source must always create identical output"
```

---

## §19 Failure vs Ambiguity Boundary

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

They are NOT collapsed into a single `invalid` category by
default.

PR63 does NOT introduce:

```
an error enum
an error code family
an exception hierarchy
a failure result schema
```

Lock:

```
Operational failure and semantic ambiguity must not be
represented as the same condition by default.
```

---

## §20 Domain-Neutrality Audit

Audited vocabulary (word-boundary, case-insensitive) over both
files:

```
cerberus / cve / cpe / kev / nvd / epss / openssh
vulnerability / exploit / scanner / nmap
host / port / service / asset / forensic
```

Audit method (per PR63 entry directive §3 boundary):

```
audit target:
  normative prose excluding the quoted audit vocabulary list

expected:
  unintended normative occurrences = 0 / 16

excluded from normative count:
  the explicit forbidden-vocabulary quotation in §26 of the
    architecture spec
  the same quotation in this dev record §20
```

Audit applies to:

```
section titles
general prose
normative statements
stage descriptions
anti-pattern descriptions
future handoff text
closing meaning
```

Result for the architecture spec:

```
whole-file hits                     16 / 16
§26 quoted-audit-list occurrences   16 / 16  (excluded)
normative prose unintended          0  / 16  PASS
```

No domain-specific appendix, no domain-specific mapping table,
no domain-specific record preset, no domain-specific role
preset, no domain-specific public symbol.

A domain may own its own external adapter; that adapter does
not redefine framework policy.

---

## §21 Conceptual Vocabulary Boundary

Eight conceptual names introduced as discussion vocabulary
only:

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

Promotion of any of these names into ragcore or into a public
adapter API requires a separate sequence:

```
thaw policy
  -> audit
  -> contract revision
  -> tests
  -> implementation
```

PR63 does NOT authorize promotion.

---

## §22 Anti-Pattern Summary

The spec records AP1 – AP18. The dev record summarizes the
risk groups covered:

```
source-field   ->  SemanticRole truth                   AP1
source record  ->  framework BaseRecordType definition  AP2
adapter output ->  verified evidence                    AP3
validator pass ->  semantic acceptance                  AP4
hidden loss                                             AP5
derived         /  direct retained confusion            AP6
multi-source merge without traceable boundaries          AP7
missing context filled with fabricated values            AP8
ambiguity        ->  numerical confidence                AP9
local vocabulary ->  ragcore promotion                   AP10
adapter directly mutates Engine state                    AP11
adapter output triggers tool execution                   AP12
adapter bypasses operator review                         AP13
one domain adapter used as universal adapter contract    AP14
PR61 local dictionary treated as mandatory output        AP15
adapter mapping changed without revision traceability    AP16
operational failure collapsed into semantic ambiguity    AP17
LLM explanation treated as translation proof             AP18
```

The anti-patterns describe failure modes the spec prevents;
they do not introduce new implementation requirements.

---

## §23 Out-of-Scope Confirmation

PR63 does NOT perform:

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
AdapterInput / AdapterOutput / TranslationLedger types
JSON Schema / dataclass / Enum / TypedDict / Pydantic
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

## §24 Future Handoff Boundary

PR63 may enable later work but does not schedule any.

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

None of the above are auto-entered by the merging of this
spec.

---

## §25 Final Result

```
PR59 separated interpretation axes.
PR60 defined contextual role assignment.
PR61 demonstrated one local consumer representation.
PR62 validated mechanically observable boundaries of that
     local representation.
PR63 defined how external representations may be translated
     toward consumer review without turning source-local
     mappings, normalization, or validation into framework
     truth or Engine authority.
```

Verification (213차):

```
pytest                                  1202 passing (unchanged)
ragcore source delta vs c1529e5         0 bytes (sha256)
Engine public methods                   40 (AST, unchanged)
Engine private methods                  18 (AST, unchanged)
ragcore.__all__                         48 (unchanged)
snapshot schema_version                 2 (unchanged)
snapshot top-level keys                 18 (unchanged)
new tests this cycle                    0
new framework public symbols            0
six core locks present in spec          PASS
ten stage headers present in spec       PASS
key boundary phrases present            PASS
                                          (translation authority
                                           is not mutation
                                           authority / local
                                           validator follows local
                                           representation /
                                           operational failure
                                           and semantic ambiguity
                                           must not be represented
                                           as the same condition /
                                           adapter output does not
                                           enter Engine merely by
                                           existing)
PR49 - PR62 files                       unchanged
PR59 contract / PR60 policy /
  PR61 example / PR62 validator + tests 0 diff lines vs c1529e5
domain-neutral normative prose          0 / 16 unintended
                                          occurrences
quoted audit-list occurrences           excluded from normative
                                          count (§26 of spec
                                          and §20 of this record)
```

No architecture spec polish commit was added in 213차. The
spec passed the six-axis review without modification.

After merge, the framework re-enters a waits state. PR64, PR65,
any domain-owned external adapter application, and any Engine
integration path require their own explicit entry directives.
