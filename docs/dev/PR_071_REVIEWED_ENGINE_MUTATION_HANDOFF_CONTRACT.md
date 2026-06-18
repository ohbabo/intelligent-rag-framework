# PR71-M02 — Reviewed Engine Mutation Handoff Contract

Development record for the architecture contract landed by
PR71-M02 (branch `docs/reviewed-engine-mutation-handoff`).

```
base:            main 896e01e (PR70-M01: Minimal Operational
                                Scaffold)
branch:          docs/reviewed-engine-mutation-handoff
233차 commit:    cf129e2   docs(architecture)
234차 commit:    (this record, docs/dev)
type:            framework-level architecture contract,
                  documentation only
```

This record captures the M-series investigation context, the
M01 OC-A evidence that motivates M02, the four-layer model M02
fixes, each section's locked content, the repository-wide
contradiction scan, the structural invariants, and the closing
position of PR71-M02.

PR71-M02 does **not** implement, execute, or schedule any
runtime change. It defines the conceptual boundary that
separates a consumer-side `RoleAssignment` from a consumer-side
`EngineInputCandidate`, from a consumer-side
`ReviewedMutationRequest`, from the single Engine mutation
event — the caller's explicit invocation of one existing Engine
public method.

---

## §1 Investigation origin

The P-series (PR65 – PR69) closed five framework-level
boundaries. PR70-M01 then composed the existing example
components into a three-lane scaffold and exposed seven
operational discontinuities (OC-A through OC-G). OC-A is the
missing handoff sequence between context interpretation and
actual Engine mutation:

```
RoleAssignment
    ↓
EngineInputCandidate
    ↓
ReviewedMutationRequest
    ↓
explicit Engine public API call
```

M01 surfaced OC-A at three scaffold stages:

```
A5  RoleAssignment -> EngineInputCandidate          UNDEFINED
A6  EngineInputCandidate -> ReviewedMutationRequest  UNDEFINED
A7  ReviewedMutationRequest -> Engine mutation      BLOCKED
```

PR71-M02 closes the **conceptual** boundary for A5 / A6 / A7.

PR71-M02 does **not** close A2:

```
A2  AdapterTrace -> RoleAssignment                  UNDEFINED
```

PR64's adapter trace representation and PR61's role-assignment
representation remain intentionally independent, as locked by
the PR64 dev record. M02 explicitly preserves that
independence; it does not introduce a mapping, parser, helper,
or schema between them.

M02's input is therefore an **already-authored, context-
specific, consumer-side RoleAssignment**.

---

## §2 P-series frozen baseline

```
main at PR70-M01 close:     896e01ea3142e17a591a3054963d498744709e2e
tests:                       1423 passing (P-series 1364 + 59 M01)
Engine public methods:       40
Engine private methods:      18
ragcore.__all__:             48
snapshot schema_version:     2
snapshot top-level keys:     18
contract last section:       §54
```

M-series state at PR71-M02 start:

```
P-series  CLOSED
PR70-M01  CLOSED
PR71-M02  CURRENT (this PR)
PR72-M03  NOT STARTED
PR73-M04  CONDITIONAL / NOT STARTED
PR74-M05  NOT STARTED
PR75-M06  NOT STARTED
PR76-M07  NOT STARTED
PR77-M08  NOT STARTED
PR78-M09  NOT STARTED
```

---

## §3 Files Changed

```
docs/architecture/REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md
                                              +1049 lines  (233차, new)
docs/dev/PR_071_REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md
                                              this record  (234차, new)

ragcore source delta:         0 bytes
examples files changed:       0
tests changed:                0
dependencies changed:         0
framework public symbols:     0 added
new exception classes:        0
new dependencies:             0
```

No `ragcore/` file is touched. No example file is touched. No
test is touched.

---

## §4 Layer Position

```
PR60 Role Assignment Policy
  consumer-side contextual interpretation boundary
              │
              │  (M02 lives here)
              ▼
M02 Reviewed Engine Mutation Handoff
  candidate / review / explicit-call boundary
              │
              │  (existing layer)
              ▼
PR43 Engine Method Call Playbook
  existing call-order guide for the caller after review ends
```

M02 does not deprecate or replace PR43. It sits one layer
above PR43 as the explicit gate that precedes the order PR43
documents. M02 does not deprecate PR57 (proposal acceptance is
a separate, prior workflow gate) and does not modify PR58 /
PR60 / PR70.

---

## §5 Four-Layer Model

```
Layer 1   RoleAssignment
            consumer-side contextual interpretation
            (PR60 / PR61)
Layer 2   EngineInputCandidate
            consumer-side, non-executable description of one
            proposed Engine public API invocation
Layer 3   ReviewedMutationRequest
            an EngineInputCandidate that received an explicit
            consumer-side mutation review decision
Layer 4   Explicit Engine public API invocation
            the actual mutation event; a Python caller
            invokes one existing Engine public method
```

Layer 1 → Layer 2: §5 admission (§5 of contract)
Layer 2 → Layer 3: §9 review boundary
Layer 3 → Layer 4: §12 caller responsibility and explicit
invocation only.

Engine state changes only at Layer 4.

---

## §6 Core Boundary Statement

The contract's §3 lists eight load-bearing locks:

```
RoleAssignment validator pass != candidate materialization
RoleAssignment                != Engine truth
RoleAssignment                != EngineInputCandidate
EngineInputCandidate          != accepted mutation
candidate validation          != review approval
ReviewedMutationRequest       != automatic execution
proposal operator acceptance  != mutation review approval
actual Engine mutation        =  caller explicitly invokes
                                  one existing Engine public API
```

Each subsequent contract section refines one of these.

---

## §7 RoleAssignment Admission (contract §5)

A consumer **may** consider materializing a candidate only
when ten conditions hold:

```
1.  RoleAssignment exists on the consumer side
2.  Interpretation context recorded explicitly
3.  Assignment target identifiable
4.  Provenance and traceability recorded
5.  Primary role ambiguity resolved
6.  AllowedUse and ForbiddenUse do not conflict
7.  Assignment is not in unresolved state
8.  Consumer policy does not forbid materialization
9.  If a representational validator was used, its result
    is recorded with its meaning
10. Even when (9) returns [], the consumer makes the
    materialization decision separately
```

Validator output `[]` means **"selected representational
boundary violations not detected"** — nothing more. It is not
consent, approval, certification, or authorization.

Unresolved RoleAssignment:

```
unresolved
  -> preserve ambiguity
  -> stop
```

Convenience selection of a primary role and direct candidate
materialization from an unresolved assignment is forbidden.

---

## §8 EngineInputCandidate Conceptual Content (contract §6 / §7)

A candidate describes exactly one proposed Engine public API
invocation. It is inspectable in full before review, carries
no callable / lambda / method object / arbitrary code, and
references a public method only as inspection metadata.

Minimum conceptual content (contract §7):

```
- candidate identity (opaque, consumer-assigned)
- source RoleAssignment reference
- assignment context reference
- source provenance / traceability reference
- intended Engine public API target (label only)
- explicit proposed arguments
- argument translation basis
- expected preconditions
- expected Engine mutation effect
- explicit non-effects
- known unresolved assumptions
- consumer policy basis
```

### §8.1 Argument translation lock (contract §7.1)

External signals must not be silently identified with Engine
signals. None of:

```
retrieval score / severity label / LLM confidence /
similarity / ranking / external probability
```

may be silently treated as:

```
base_confidence / Evidence.strength / Gap.severity / Claim.status
```

Any derivation must be recorded explicitly under "argument
translation basis"; the reviewer inspects that basis.

### §8.2 Expected-effect / non-effect lock (contract §7.2)

A candidate with expected effect "create one Evidence" must
also enumerate non-effects:

```
does not confirm the Claim
does not refute the Claim
does not execute a tool
does not update RuleStats
does not resolve every Gap
does not produce a final verdict
```

Non-effects are review-critical, not editorial.

---

## §9 Candidate Atomicity and Ordering (contract §8)

```
one EngineInputCandidate
  =  one proposed Engine public API invocation
```

Multi-call operations become sequences of separate candidates.
Example:

```
candidate 1   add_entity(entity_type=...)
candidate 2   add_claim(subject_id=...)
candidate 3   add_evidence(claim_id=...)
candidate 4   add_gap(claim_id=...)
candidate 5   confirm_claim_if_ready(claim_id=...)
```

M02 does not define a batch executor, transaction manager,
rollback, all-or-nothing semantics, dependency resolver, or
automatic call sequencing. The call order followed after review
is PR43 (`docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md`),
unchanged.

---

## §10 Review Boundary (contract §9)

### §10.1 Pre-review state

A candidate is review-eligible only when it is non-executable,
complete enough to inspect, targeted at a current public Engine
method, inspectable in its exact proposed arguments, traceable
to its source RoleAssignment and translation basis, explicit
about preconditions / expected effect / non-effects, not
produced from an unresolved RoleAssignment, and not targeted at
a private or nonexistent method.

### §10.2 Review questions (contract §9.2)

Ten review questions are enumerated (§9.2.1 – §9.2.10):

```
1.  Does the source RoleAssignment support this candidate?
2.  Does it conflict with AllowedUse / ForbiddenUse?
3.  Is the target an existing public Engine method?
4.  Do arguments match the target signature meaningfully?
5.  Has any external score been silently substituted for an
    Engine signal?
6.  Do referenced Engine IDs identify the intended kinds?
7.  Is a lifecycle mutation hidden inside a data-registration
    candidate?
8.  Is a RuleStats update silently appended?
9.  Is the expected effect overstated?
10. Are non-effects explicit and complete?
```

### §10.3 Review is not proposal acceptance (contract §9.3)

PR57 operator acceptance is the workflow gate that admits a
proposal into a downstream consumer layer. M02 mutation review
is a separate gate for exact Engine mutation candidates. A
consumer must not collapse the two into a single boolean (such
as `accepted=True`).

---

## §11 ReviewedMutationRequest Definition (contract §10)

A reviewed request carries: request identity, reviewed
candidate identity, reviewed target API, reviewed exact
arguments, review decision, review basis / rationale, review
actor reference, review time reference, and an explicit
execution boundary statement.

M02 does NOT freeze: Python field names, timestamp format,
actor identity scheme, database storage, signing,
cryptographic digest, state revision, packet revision, stale
revalidation algorithm, retention period, or audit log schema.

---

## §12 Exact-Content Review Binding (contract §11)

```
A review applies only to the exact target and exact arguments
that were reviewed.
```

If any of `target Engine method`, `argument value`, `referenced
Engine object ID`, `translation basis`, `expected effect`,
`source RoleAssignment`, or `policy-sensitive assumption`
changes, the prior review must not be reused. The changed
candidate is a new candidate requiring a new review.

M02 does NOT require a hash, digest, signature, or revision
field. Mechanical detection is consumer implementation choice
and is not the same as the OC-C `state_revision` /
`packet_revision` (Engine-state identity) which remains
PR72-M03 work.

---

## §13 Explicit Engine Public API Invocation (contract §12)

### §13.1 Execution boundary

```
ReviewedMutationRequest does not call Engine.
```

A `ReviewedMutationRequest` is consumer-side handoff data.
Engine state changes only when a Python caller, at Layer 4,
explicitly invokes one existing public method.

Allowed forms (illustrative only — M02 does not implement
them):

```python
engine.add_claim(
    subject_id, claim_type, rule_id, rule_version, reason_code,
    base_confidence=base_confidence, status=status, flags=flags,
)
engine.add_evidence(claim_id, raw_ref_id, evidence_type, strength)
engine.add_gap(
    claim_id, gap_type, required_evidence_type, severity, rule_id,
)
engine.register_contradiction(claim_id, evidence_id)
```

### §13.2 Forbidden invocation forms (contract §12.2)

```
execute_mutation_request(request)
request.execute(engine)
engine.apply_request(request)
auto_dispatch(request)
getattr(engine, request.method)(*request.args)
getattr(engine, name)(**args)
dispatch[method_name](engine, args)
eval(request.code)
exec(request.code)
```

Also forbidden: storing callables, lambdas, method objects, or
arbitrary code in the request; using a method-name string as
the execution token; targeting a private attribute or method;
targeting a method that does not exist; reflection-based
execution. The reviewer may inspect a method-name string as
metadata; the caller invokes the method by name in source
code, not by reflection on the request.

### §13.3 Caller responsibility (contract §12.3)

Immediately before invocation, the caller verifies:

```
1. The request is one the caller's own workflow approved.
2. Target and arguments in source code match what was
   reviewed.
3. The target method exists in the current Engine public API.
4. Referenced Engine IDs identify the objects the caller
   intends.
5. The intended call order is consistent with PR43.
6. If the operation requires a lifecycle transition, a
   separate candidate / review / call sequence is followed.
```

§13.3 does NOT guarantee freshness, currentness, or state-
binding. Mechanical stale checks are OC-C / PR72-M03 and
OC-B / PR74-M05. Documents must not claim an `M02-reviewed`
request is "fresh", "current", or "state-bound" as a
mechanical guarantee.

---

## §14 Call Success Semantics (contract §13)

```
Engine public method invocation success
  = Engine accepted that method's arguments and applied the
    method's existing runtime behavior.
```

Call success does NOT mean: the source RoleAssignment is
objectively correct; the Claim is true; the Evidence is
strong; an operator's final judgment is recorded; a lifecycle
transition completed; the downstream report is final; the rule
is verified; the proposal is correct.

Expansion examples:

```
add_claim success            != Claim confirmed
add_evidence success         != Claim confirmed
register_contradiction success != Claim automatically disputed
                                  or refuted
```

Lifecycle transitions require explicit `_if_ready` calls
reviewed separately (§15).

---

## §15 Lifecycle Separation (contract §14)

Lifecycle mutation is NEVER bundled inside a data registration
candidate. A candidate targeting `add_evidence(...)` does NOT
authorize:

```
confirm_claim_if_ready / refute_claim_if_ready /
dispute_claim_if_ready / resolve_disputed_claim_if_ready /
refute_disputed_claim_if_ready /
refute_disputed_claim_if_ready_by_freshness /
register_contradiction_resolution
```

Each lifecycle call is its own candidate with its own review.
One candidate's review never authorizes another candidate's
call.

---

## §16 Rule / RuleStats Separation (contract §15)

M02 does NOT auto-derive `update_rule_stats(...)`,
`register_rule(...)`, RuleDefinition creation, or any rule-
quality verdict from a RoleAssignment, candidate, or reviewed
request.

Side-effect `update_rule_stats` on the back of a data
registration call is forbidden.

`RuleStats` update provenance — caller identity, update reason,
source observation reference, delta provenance, precision
input basis, policy reference — is OC-G / PR78-M09 and is not
specified by M02.

---

## §17 Rejection / Hold Conditions (contract §16)

A candidate or reviewed request never silently advances. A
consumer must not auto-rewrite a rejected candidate and re-
submit it. Refusal and hold leave Engine state unchanged.

Materialization is refused on: unresolved RoleAssignment,
missing context / provenance / traceability,
AllowedUse / ForbiddenUse conflict, non-existent public target,
private target, unclear argument derivation, direct external
score pipe, hidden lifecycle effect, hidden RuleStats side
effect.

Review rejects or holds on: uninspectable arguments, target /
signature mismatch, overstated expected effect, missing or
incomplete non-effects, candidate divergence from source
RoleAssignment, ambiguous referenced IDs, additional context
required, current Engine state suitability unclear.

---

## §18 A2 Remains Undefined (contract §17)

M02's closure of A5 / A6 / A7 does NOT close A2:

```
A2  AdapterTrace -> RoleAssignment    remains UNDEFINED
```

M02 forbids: a PR64-to-PR61 converter; automatic key-name
matching; automatic `contextual_primary_role` copy; automatic
allowed / forbidden use synthesis from adapter output; direct
candidate materialization from an adapter trace; skipping the
RoleAssignment stage.

M02's input is an already-authored consumer-side RoleAssignment.
A2 is left as a future consumer-policy or future PR concern
that M02 does not schedule.

---

## §19 Future M-series Boundaries (contract §19)

```
PR72-M03 (OC-C)   Engine state identity / read consistency
                  M02 does NOT define state revision, packet
                  revision, capture atomicity, snapshot digest,
                  or decision-time state identity. M02 does NOT
                  claim mechanical stale detection.

PR73-M04          conditional slot, not pre-defined.

PR74-M05 (OC-B)   Operator decision record persistence and
                  stale revalidation rule.
                  M02 does NOT define a persistent shape.

PR75-M06 (OC-E)   Downstream re-entry semantics.
                  M02 does NOT define external result re-entry.

PR76-M07 (OC-D)   Effective-confidence trace. Out of scope.

PR77-M08 (OC-F)   Complete reference operation. Out of scope.

PR78-M09 (OC-G)   RuleStats provenance. Out of scope.
```

M02 does NOT auto-start PR72-M03 or any later M-series PR.

---

## §20 Repository-Wide Contradiction Scan

### §20.1 Corrected (in-place edits)

```
(none)
```

The current normative / guide documents already align with
M02. No in-place edit was required.

### §20.2 Aligned (cross-references kept)

```
docs/architecture/ROLE_ASSIGNMENT_POLICY_SPEC.md
  Multiple "does not introduce ... RoleAssignment dataclass"
  disclaimers — already aligns with M02 §4.1 / §6 / §10.

docs/architecture/DATA_ACCESS_PROFILE_CONTRACT.md
  AllowedUse / ForbiddenUse axes used by §5 / §9 review
  questions. Already aligned.

docs/architecture/OPERATOR_DECISION_BOUNDARY_SPEC.md (PR57)
  "operator acceptance is the workflow gate" already isolated
  from Engine mutation execution. M02 §9.3 makes the
  separation between proposal acceptance and mutation review
  explicit; PR57 wording itself is not changed.

docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md (PR54)
  "Human / operator acceptance is the gating event for any
   downstream layer." Aligned with M02 §9.3.

docs/guides/PROPOSAL_USAGE_PLAYBOOK.md (PR58)
  Already notes that operator acceptance does not directly
  cause Engine mutation and lists the same anti-patterns M02
  generalizes.

docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md (PR43)
  Call-order guide. M02 §8 / §13 / §15 cite PR43 as the layer
  the caller follows AFTER review ends.

docs/dev/PR_070_MINIMAL_OPERATIONAL_SCAFFOLD.md
examples/operation/minimal_operational_scaffold.py
  M01 dev record and scaffold. M02 §1 / §17 cite M01 as the
  executable evidence of OC-A and as the source of the A2
  preservation requirement.
```

### §20.3 No contradiction found

Repository-wide search returned zero matches for normative
phrasings forbidden by M02:

```
"pipeline complete"
"end-to-end complete"
"operation complete" (as a normative claim)
"validator approved"
"trusted proposal"
"verified role"
"atomic packet"
"revision-bound packet"
"automatic re-entry"
"getattr(engine," in any current normative or guide doc
```

Two historical mentions exist:

```
docs/dev/PR_018_SNAPSHOT_MIGRATION_MVP.md
  single "getattr(engine_module, ..., None)" string from
  2026-04 era describing dynamic module attribute access in
  the snapshot migration helper. Historical context only;
  M02 does not modify it.
```

### §20.4 Historical records intentionally unchanged

No historical dev record is rewritten by M02. PR60 / PR61 /
PR62 / PR63 / PR64 / PR65 – PR69 / PR70 records remain as
written.

### §20.5 Future PR candidates (recorded only)

```
A2 bridging (AdapterTrace -> RoleAssignment)
  may be addressed by a separate consumer-policy spec or a
  future PR; M02 explicitly does NOT schedule it.

Persistent operator decision record (OC-B)
  PR74-M05 candidate.

State identity / read consistency (OC-C)
  PR72-M03 candidate.

Downstream re-entry (OC-E)
  PR75-M06 candidate.

RuleStats provenance (OC-G)
  PR78-M09 candidate.
```

---

## §21 Structural Invariants

```
Engine public methods                40         (unchanged)
Engine private methods               18         (unchanged)
ragcore.__all__                      48         (unchanged)
snapshot schema_version              2          (unchanged)
snapshot top-level keys              18         (unchanged)

ragcore files changed                0
examples files changed               0
tests changed                        0
dependencies changed                 0
new public symbol                    0
new Engine method                    0
new dependency                       0
new exception class                  0
new snapshot key                     0

runtime behavior delta               0
judgment semantics delta             0
lifecycle delta                      0
confidence formula delta             0
snapshot delta                       0
```

---

## §22 Regression Result

`pytest -q` on 233차 commit `cf129e2`:

```
1423 passed
```

Identical to the baseline at `main` `896e01e`. PR71-M02 is
documentation only.

---

## §23 Self-Review

```
[x] M02 is NOT described as an implementation PR. Every section
    explicitly limits itself to conceptual boundary definition.

[x] A2 (AdapterTrace -> RoleAssignment) is NOT solved. §17
    explicitly preserves the UNDEFINED status.

[x] RoleAssignment is NOT promoted to Engine object. §4.1 and §5
    keep it as consumer-side contextual interpretation.

[x] Validator pass is NOT promoted to candidate approval. §5.9 /
    §5.10 explicitly state the anti-claim.

[x] EngineInputCandidate is NOT materialized as a Python type.
    §6 enumerates non-types; §20 Non-goals reaffirms.

[x] Candidate is NOT called an executable command. §6 / §12.2
    forbid callables, lambdas, method objects, dispatch tokens,
    reflection-based execution.

[x] ReviewedMutationRequest is NOT called an Engine call.
    §12.1 explicit "does not call Engine".

[x] Proposal acceptance and mutation review are NOT collapsed.
    §9.3 explicitly forbids a single boolean (such as
    accepted=True) that simultaneously means both.

[x] Method-name string is NOT used as an execution token.
    §12.2 explicitly forbids getattr(engine, name)(...) and
    reflection-based execution.

[x] No dynamic dispatcher is proposed. §12.2 enumerates
    forbidden forms; §20 reaffirms.

[x] No candidate carries hidden multi-effects. §7.2 / §8 / §14
    enforce expected-effect / non-effect locks and one-call /
    one-candidate atomicity.

[x] Lifecycle is separated. §14 explicit "lifecycle mutation
    is never bundled".

[x] RuleStats update is NOT auto-connected. §15 explicit
    "M02 does NOT auto-derive".

[x] Call success is NOT described as truth judgment. §13
    enumerates anti-claims.

[x] State freshness is NOT mechanically guaranteed. §12.3 last
    paragraph explicit.

[x] M03 / M05 / M06 / M09 responsibilities are NOT pre-empted.
    §19 explicit boundary list.

[x] Domain-specific vocabulary is NOT in the normative body.
    The repository-standard forbidden-domain list and the
    related two-word "security-verdict" phrase return 0
    word-boundary matches on the contract and dev record
    (audit-list quotation excluded from the normative count,
    matching the PR59 §17 / PR63 / PR68 convention).

[x] PR72-M03 is NOT auto-started.

[x] No runtime / examples / test / dependency file modified.
```

---

## §24 Closing Position

PR71-M02 is closed when:

- 233차 `docs(architecture)` adds the contract.
- 234차 `docs(dev)` records this development record.

This PR is opened as draft; merge is not part of PR71-M02 per
the directive.

After merge, M-series state advances by one step:

```
P-series   CLOSED
PR70-M01   CLOSED
PR71-M02   ready (this PR — draft)
PR72-M03   NOT STARTED
PR73-M04   CONDITIONAL / NOT STARTED
PR74-M05   NOT STARTED
PR75-M06   NOT STARTED
PR76-M07   NOT STARTED
PR77-M08   NOT STARTED
PR78-M09   NOT STARTED
```

No follow-up PR is auto-scheduled by PR71-M02.

RoleAssignment에서 Engine mutation까지의 중간 handoff를
consumer-side candidate와 explicit review request로 분리하되,
실제 mutation은 caller가 기존 Engine public API를 직접 호출할
때에만 발생하도록 계약을 잠갔으며, 자동 dispatch와 Engine의
judgment semantics 변경은 도입하지 않았다.

---

## Post-review correction — 235차

After the initial 233차 / 234차 commits, a final audit of the
contract found six internal contract defects (not runtime
defects). The defects were corrected on the same branch
without amending or squashing the existing two commits; a
single post-review commit (235차) updates both the architecture
contract and this dev record.

The corrections do not change M02's direction. The OC-A
investigation, the four-layer model, the explicit-invocation
boundary, the A2 preservation, the M03 / M05 / M06 / M09
separations, and the docs-only scope are all preserved.

### Corrections applied

**C1 — Mutation target restricted to state-mutating public methods.**
The initial wording "one existing Engine public API" / "one
existing Engine public method" / "method that exists in the
current Engine public API" left the door open for read-only
public methods to be treated as mutation candidates. The
contract now requires the target to be an existing
**state-mutating** Engine public method. §12.1 carries a full
classification of the 40 public methods observed on `main`
`896e01e`:

```
state-mutating public methods (20)
  add_entity / add_observation / add_claim / add_evidence /
  add_relation / add_gap
  resolve_gaps_for_evidence
  register_contradiction / register_contradiction_resolution
  confirm_claim_if_ready / refute_claim_if_ready /
  dispute_claim_if_ready / resolve_disputed_claim_if_ready /
  refute_disputed_claim_if_ready /
  refute_disputed_claim_if_ready_by_freshness
  register_rule / update_rule_stats
  register_hint_evidence_types /
  unregister_hint_evidence_types / clear_hint_evidence_types

read-only public methods (18)           NOT M02 candidate targets
serialization boundary (2)               NOT M02 mutation targets
                                         (to_snapshot / from_snapshot)
```

The §3 core boundary now includes `public != state-mutating`
and `read-only public method != mutation candidate target`,
plus the §4.4 / §13 wording aligned to "state-mutating Engine
public method".

**C2 — Approved-only ReviewedMutationRequest.**
The initial §10 carried `review decision (approved / rejected
/ hold)` inside the request. The contract now distinguishes a
**review disposition** (any of the three outcomes, §9.4) from
a **`ReviewedMutationRequest`** (only an approved exact
candidate yields one). Rejected and held dispositions are
consumer-side artifacts that never enter Layer 3. §10 now
carries "approved review disposition reference" instead of a
three-way decision field.

**C3 — Source-basis scope.**
The initial §6 / §7 required every candidate to carry a
"source RoleAssignment reference". The contract now scopes
this requirement to the **OC-A role-derived ingress path** and
introduces a per-class source-basis rule in the candidate
content list:

```
OC-A role-derived       admitted RoleAssignment + context
lifecycle transition    target Claim's current status + readiness
                         signal (M02 fixes only the separation
                         principle, not a full source-basis contract)
contradiction-resolution
                        the contradiction set entry to be marked
                         resolved (separation principle only)
Rule / RuleStats         consumer policy basis; OC-G / PR78-M09
                         completes RuleStats provenance
```

The four-layer model is now explicitly labeled as the OC-A
role-derived ingress path.

**C4 — Generated-ID handling and sequential materialization.**
The initial §8 showed five candidates as a list, implying they
could all be pre-materialized. The contract now adds §8.2
(generated-ID dependency rule), §8.3 (sequential
materialization), and §8.4 (consumer-side grouping). Dependent
candidates are not exact and review-eligible until every
required Engine ID has been produced; placeholders are
explicitly excluded from review-eligibility. §16.1 / §16.2 add
placeholder rejection conditions.

**C5 — Contradiction-resolution classification.**
The initial §14 listed `register_contradiction_resolution` as
a lifecycle method. The contract now classifies it as a
separate mutation class:

```
§14.1   Lifecycle transition separation
        (six _if_ready methods only)
§14.2   Contradiction-resolution separation
        (register_contradiction_resolution; not lifecycle)
§14.3   Gap resolution separation
        (resolve_gaps_for_evidence)
```

**C6 — add_evidence / Gap resolution.**
The initial §7.2 example non-effect `does not resolve every
Gap` was imprecise. The contract now reads
`does not itself resolve any Gap` and adds explicit pointers
to §14.2 (contradiction resolution) and §14.3 (Gap resolution),
with `resolve_gaps_for_evidence` named as the existing
state-mutating method that performs Gap resolution.

### Minor wording / grammar corrections

- Dev record opening: `does not implement, executes, or
  schedules` → `does not implement, execute, or schedule`.
- Contract §3: `These eight equivalences` (originally seven
  inequalities plus one equality, mis-counted) →
  `These twelve load-bearing boundary statements` after the
  C1 / C2 / new-lock additions.
- Contract §12 title:
  `Explicit Engine public API invocation` →
  `Explicit invocation of one existing state-mutating Engine
   public method`.
- Contract §4.2 Layer 2 short definition aligned to
  `state-mutating Engine public method invocation, supported
   by an explicit consumer-side source basis appropriate to
   its mutation class`.
- Contract §22 closing position rewritten so the OC-A path
  and the separation principles for the other mutation
  classes are both visible.

### Defect counts

```
Pre-existing repository normative contradictions found:    0
M02 internal contract defects found during post-review:    6
M02 internal contract defects remaining after 235차:        0
Minor wording / grammar corrections:                        5
```

The "0 contradictions found" line in §20 of the prior
revision referred to **pre-existing repository normative
contradictions** — none were introduced by other documents
and no in-place edits were required outside M02's own files.
The six post-review corrections are entirely **internal to
M02** and were caught by the final audit of M02's own
contract.

### Files changed by 235차

```
docs/architecture/REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md
docs/dev/PR_071_REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md
```

No `ragcore/` file is touched. No example file is touched. No
test is touched. No dependency is added.

### Re-measured invariants on 235차

```
Engine public methods                40         (unchanged)
Engine private methods               18         (unchanged)
ragcore.__all__                      48         (unchanged)
snapshot schema_version              2          (unchanged)
snapshot top-level keys              18         (unchanged)

ragcore files changed                0
examples files changed               0
tests changed                        0
dependencies changed                 0
new public symbol                    0
new Engine method                    0
new dependency                       0
new exception class                  0
new snapshot key                     0

runtime behavior delta               0
judgment semantics delta             0
lifecycle delta                      0
confidence formula delta             0
snapshot delta                       0
```

`pytest -q` on 235차: `1423 passed`.

### Commit history after 235차

```
233차  cf129e2  docs(architecture): define reviewed Engine
                  mutation handoff
234차  47b7aa3  docs(dev): record PR71-M02
235차  cb2006b  docs(architecture): correct reviewed mutation
                  handoff boundaries
236차  (this commit)  docs(architecture): finalize reviewed
                       mutation handoff audit
```

The 236차 commit performs the final audit cleanup before
merge: replaces the 235차 placeholder, normalizes the
§14b / §14c lowercase-suffix subsection headers to the
repository-standard dot-numbering convention (§14.2 / §14.3),
and updates all cross-references accordingly. No semantic
change to the contract.

### State after 235차

```
P-series  CLOSED
PR70-M01  CLOSED
PR71-M02  CORRECTED — DRAFT, NOT MERGED
PR72-M03  NOT STARTED
PR73-M04  CONDITIONAL / NOT STARTED
PR74-M05  NOT STARTED
PR75-M06  NOT STARTED
PR76-M07  NOT STARTED
PR77-M08  NOT STARTED
PR78-M09  NOT STARTED
```

PR72-M03 has not been started. No new files, branches, or
commits beyond 235차 are created by this correction.

M02의 reviewed mutation handoff를 실제 state-mutating Engine
public method로 한정하고, approved review만
ReviewedMutationRequest를 생성하도록 교정했으며, OC-A
RoleAssignment 경계와 lifecycle·contradiction resolution·
RuleStats의 별도 책임을 혼동하지 않도록 잠갔다. 또한
generated ID에 의존하는 candidate는 실제 ID가 생성된 뒤
순차적으로 materialize·review되도록 정정했고, runtime behavior와
Engine judgment semantics는 변경하지 않았다.
