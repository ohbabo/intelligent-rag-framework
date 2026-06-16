# PR60 — Role Assignment Policy Spec

Development record for the Role Assignment Policy introduced in
PR #61 (branch `docs/role-assignment-policy-spec`).

```
base:            main 30b71bc (PR59: Data Access Profile Contract)
branch:          docs/role-assignment-policy-spec
206차 commit:     664968b
207차 commit:     (this record, docs/dev)
PR:              #61
type:            framework-level architecture policy, doc-only
```

This record captures the intent, the interpretation procedure, the
relationship to PR59, the safety boundaries (`AllowedUse` /
`ForbiddenUse` / ambiguity), and the verification results that
closed PR60. This record does not redesign PR60.

---

## §1 Purpose

PR60 defines the interpretation procedure a consumer or adapter
follows when assigning a `SemanticRole`, an `AllowedUse` scope, and
a `ForbiddenUse` boundary to a data item or fragment within a
specific judgment context.

PR59 separated six independent axes (`SourceType`, `BaseRecordType`,
`SemanticRole`, `DataAccessProfile`, `AllowedUse`, `ForbiddenUse`).
PR60 records how a consumer should arrive at a valid combination
without merging the six axes and without producing a role
automatically.

PR60 is not:

```
an Engine feature
an RAG implementation
a role classifier
an automatic LLM classifier prompt
an adapter implementation
a proposal pipeline decision layer
a domain-specific contract
```

PR60 lives on the consumer / adapter side. A role assignment
constrains consumer use; it does not create Engine truth.

---

## §2 Baseline

```
base:                       main 30b71bc
                              (PR59: Data Access Profile Contract)
baseline tests:             1183 passing
```

PR59 (#60) and the README evidence-centric philosophy clarification
(`d5496ea`) are the immediate predecessors. PR60 attributable diff
is measured from `30b71bc`.

206차 added
`docs/architecture/ROLE_ASSIGNMENT_POLICY_SPEC.md` (`+873` lines).
207차 adds this record. No other files are touched.

---

## §3 Files Changed

```
docs/architecture/ROLE_ASSIGNMENT_POLICY_SPEC.md   +873 lines  (206차)
docs/dev/PR_060_ROLE_ASSIGNMENT_POLICY_SPEC.md     this record   (207차)

ragcore source:        0 bytes changed
tests:                 0 added
public symbols:        0 added
Engine behavior:       0 added
```

Single staged file per cycle. `ragcore.egg-info/` excluded as an
untracked build artifact.

206차 commit: `664968b docs(architecture): define role assignment
policy`.
207차 commit: this record.

---

## §4 Core Boundary Locks

PR60 is governed by five primary locks:

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

These five locks govern every section of the policy. Where a later
section seems to allow a shortcut (provenance-as-role,
retrieval-as-truth, missing-prohibition-as-permission,
ambiguity-as-certainty), that shortcut is explicitly forbidden by
these locks.

Forbidden automatic mappings (PR60 does not relax):

```
SourceType         -> SemanticRole               forbidden
BaseRecordType     -> SemanticRole               forbidden
DataAccessProfile  -> SemanticRole               forbidden
SemanticRole       -> Engine state               forbidden
SemanticRole       -> automatic action           forbidden
AllowedUse         -> unrestricted permission    forbidden
```

---

## §5 10-Step Interpretation Procedure

The policy records a ten-step procedure that a consumer follows when
assigning a role within a context.

```
Step 1   Identify the data item            (fragment, not whole source)
Step 2   Establish provenance              (informs, not determines)
Step 3   Establish record shape            (limits, not proves)
Step 4   State current interpretation context
Step 5   Propose ONE primary SemanticRole
Step 6   Evaluate optional secondary roles (6 conditions all required)
Step 7   Derive AllowedUse                 (positive allowlist)
Step 8   Derive ForbiddenUse               (7 baseline risks)
Step 9   Check conflicts                   (5 conflict types)
Step 10  Preserve unresolved assignments   (no enum / status freeze)
```

The procedure is normative as a *sequence of considerations*, not as
a serialization format. The policy does not freeze field names or
data types for any step. Storage form is consumer-side policy.

Step 6 (secondary role evaluation) and Step 8 (`ForbiddenUse`
derivation) carry the most safety weight and are recorded explicitly
in §6 and §8 below.

---

## §6 Primary / Secondary Role Boundary

Within a single assignment context:

```
primary role:    exactly one SemanticRole per data item
secondary roles: zero or more
```

A primary role is the most directly relevant interpretation under
the stated context. If multiple candidate primaries compete, the
consumer must not silently select one for convenience; the conflict
is surfaced and resolved via the ambiguity policy (see §8).

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

Forbidden secondary-role uses:

```
tagging everything that might be useful
adding roles without justification
using secondary roles to bypass primary-role ambiguity
using secondary roles to expand permissions silently
using secondary roles as hidden downstream commands
```

Lock:

```
Secondary roles extend interpretation, not authority.
```

---

## §7 AllowedUse / ForbiddenUse Boundary

`AllowedUse` and `ForbiddenUse` are derived jointly with the role
assignment, not after the fact.

`AllowedUse` derivation principles:

```
AllowedUse must be explicit.
AllowedUse must be narrow.
AllowedUse must be reviewable.
AllowedUse must not imply Engine mutation or execution.
```

Unspecified use is not automatically permitted. `AllowedUse` is a
positive permission with explicit scope; absence of a forbidden
listing does not constitute permission.

`ForbiddenUse` derivation: seven baseline risks must be reviewed for
every role assignment.

```
1. misrepresenting retrieved content as verified fact
2. replacing stronger evidence
3. creating a registered Claim from a candidate
4. treating a finding as final verdict
5. changing lifecycle state
6. executing tools
7. publishing downstream conclusions or bypassing operator review
```

For each baseline risk, the consumer answers permit / forbid /
silent. A silent answer is not a permissive answer.

Lock:

```
A missing prohibition must not be interpreted as permission.
```

The policy does not freeze field names or schemas for individual
allowed-use or forbidden-use entries.

---

## §8 Ambiguity Preservation

When evidence or context is insufficient to support a single primary
role with explicit `AllowedUse` and `ForbiddenUse`, the consumer
preserves ambiguity rather than fabricating certainty.

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

PR60 does not introduce a new confidence or probability system. PR60
does not introduce an `UNRESOLVED` enum, status type, or schema.
Conceptual preservation of the unresolved state is required; storage
form is consumer-side policy.

---

## §9 Engine Non-Mutation Boundary

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

A consumer that wishes to act on a role assignment routes the action
through the appropriate Engine public API and remains subject to
operator review, validator gates, and all prior locks established
in PR49 through PR59.

This boundary is the reason PR60 introduces no public symbol and no
ragcore change.

---

## §10 Domain-Neutrality Audit

Audited vocabulary (word-boundary, case-insensitive) over the
normative body of the policy:

```
cerberus / cve / cpe / kev / nvd / epss / openssh
vulnerability / exploit / scanner / nmap
host / port / service / asset / forensic
```

Result:

```
normative-body forbidden vocabulary count: 0
```

The policy also does not contain:

```
domain-specific appendix
domain-specific mapping table
domain-specific role preset
domain-specific BaseRecordType
domain-specific public symbol
```

The §19 narrative references the audit list maintained by prior
contracts (PR45-E §3 and PR44-D §5.6); that reference is quotation
of the policy, not normative use of the vocabulary.

A domain may provide external examples or mappings; those materials
remain outside the normative framework policy.

---

## §11 Ragcore Symbol Non-Promotion

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

For all of the above, after PR60:

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

Promotion of any of the above into ragcore code requires a separate
sequence:

```
thaw policy
→ audit
→ contract revision
→ tests
→ implementation
```

PR60 does not authorize such promotion. Each follow-up requires its
own explicit entry directive.

---

## §12 Verification

### 12.1 Test and structural verification

```
pytest                          1183 passing (unchanged)
ragcore source delta            0 bytes
                                  (sha256-verified vs 30b71bc)
Engine public methods           40 (AST, unchanged)
Engine private methods          18 (AST, unchanged)
ragcore.__all__                 48 (unchanged)
snapshot schema_version         2 (unchanged)
snapshot top-level keys         18 (unchanged)
new tests                       0
new public symbols              0
new Engine behavior             0
new example source files        0
```

### 12.2 Self-review audit

Four-axis audit applied to
`docs/architecture/ROLE_ASSIGNMENT_POLICY_SPEC.md`:

```
semantic locks present              9 / 9    PASS
over-promotion phrasing             0        PASS
verbatim-repeated sentences (>= 3x) 0        PASS
§22 future-handoff normative leak   0        PASS
```

Semantic locks audited:

```
SourceType alone cannot determine SemanticRole
BaseRecordType alone cannot determine SemanticRole
retrieval mode cannot establish truth
exactly one primary role per assignment context
secondary roles do not expand authority
AllowedUse is explicit and narrow
missing prohibition is not permission
ambiguity is preserved
role assignment does not create Engine truth
```

Closing Meaning verified as paraphrastic restatement of §3 (Core
Boundary Statements) and §17 (Relationship to Engine). It introduces
no new normative content.

### 12.3 PR51 – PR59 unchanged

```
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

In particular:

```
context packet schema           unchanged
proposal shape validator        unchanged
proposal safety validator       unchanged
operator gate                   unchanged
Engine judgment semantics       unchanged
```

---

## §13 Out-of-Scope Confirmation

PR60 does not perform any of the following:

```
ragcore source modification
Engine method addition
public symbol addition
snapshot schema change
Claim lifecycle change
effective-confidence change
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
role registry or mapping database
JSON Schema / dataclass / enum / TypedDict
domain-specific example
new tests
new example source files
new contract §51 entry
```

---

## §14 Future Handoff Boundary

PR60 may enable later work but does not schedule any.

Follow-ups, each requiring its own explicit entry directive:

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

## §15 Final Result

```
PR59 separated the data-access interpretation axes.

PR60 defined how a consumer may connect those axes
within a specific interpretation context,
while preserving ambiguity and preventing the assignment
from becoming Engine truth or downstream authority.
```

After merge, the framework re-enters a waits state. PR61, PR62, and
any external adapter application require their own explicit entry
directives.
