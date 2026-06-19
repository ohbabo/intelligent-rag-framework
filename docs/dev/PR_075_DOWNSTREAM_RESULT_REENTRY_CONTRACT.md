# PR75-M06 — Downstream Result Re-entry Contract

Development record for the architecture contract landed by
PR75-M06 (branch `docs/downstream-result-reentry`).

```
base:            main 80759048 (PR74-M05 — Operator Decision
                                Record / Decision-State
                                Revalidation Contract)
branch:          docs/downstream-result-reentry
251차 commit:    1cf934f   docs(architecture): define downstream
                            result re-entry contract
252차 commit:    (this record, docs/dev)
type:            framework-level architecture contract,
                  documentation only
status:          normative
```

This record captures the M-series investigation context, the
OC-E / C2~C7 origin, the empirical baseline observed on `main`
`80759048`, the rationale for keeping M06 docs-only, the six
re-entry stages that M06 fixes, the boundary preservations
inherited from PR59 / PR61 / PR57 / M02 / M03 / M04 / M05, the
files changed, the structural invariants, the pytest result,
and the repository-wide forbidden-conclusion scan.

PR75-M06 does **not** implement, execute, or schedule any
runtime change. It defines the conceptual boundary between an
investigation result that a consumer chose to run and the
explicit invocation of one existing state-mutating Engine
public method that may follow from that result.

---

## §1 Investigation origin

The M-series M01 scaffold (PR70-M01) labels Lane C as
`downstream_reentry`. M01 left six of its seven stages as
`TODO` / `UNDEFINED` / `BLOCKED`:

```
C1  operator decision record                UNDEFINED  (OC-B)
C2  consumer-side investigation             TODO
C3  new external result trace               TODO
C4  result role assignment                  TODO
C5  EngineInputCandidate                    UNDEFINED  (OC-E)
C6  ReviewedMutationRequest                 UNDEFINED  (OC-E)
C7  explicit re-entry authorization         BLOCKED    (OC-E)
```

C2 ~ C7 together carry the `OC-E` label. M02 (PR71-M02) closed
the conceptual boundary for OC-A (Lane A external ingress).
M03 (PR72-M03) closed the read-consistency vocabulary for the
PR51 packet. M04 (PR73-M04) added the minimum identity
primitive. M05 (PR74-M05) closed OC-B at the operator-decision-
record persistence + revalidation policy layer.

PR75-M06 picks up OC-E at the **conceptual re-entry boundary**:
the question of how a downstream result, once it exists,
becomes eligible for an explicit Engine state-mutating
invocation. M06 stops at the conceptual chain. A complete
domain-neutral reference operation that exercises the chain
end-to-end is M08 (PR77) territory and is explicitly NOT in
M06's scope.

---

## §2 Base state

```
main at PR75-M06 start:     80759048e98d9255596a8aa56bf4ea94cd9d1250
tests:                       1517 passing
Engine public methods:       41
Engine private methods:      19
state-mutating public:       20
read-only public:            19
serialization boundary:       2
ragcore.__all__:             49
snapshot schema_version:      2
snapshot top-level keys:     18
PR51 packet keys:             7
```

M-series state at PR75-M06 start:

```
P-series   CLOSED
PR70-M01   CLOSED
PR71-M02   CLOSED
PR72-M03   CLOSED
PR73-M04   CLOSED
PR74-M05   CLOSED
PR75-M06   IN PROGRESS (this PR, Draft)
PR76-M07   NOT STARTED
PR77-M08   NOT STARTED
PR78-M09   NOT STARTED
```

---

## §3 Why M06 is docs-only

M06 is docs-only by deliberate design.

```
- M06 owns conceptual obligations: how a downstream result
  is re-translated, role-assigned, considered for candidate
  materialization, reviewed, recorded, revalidated, and
  invoked. None of those obligations requires a Python class
  to exist.

- A consumer-side adapter chain chooses its storage
  substrate, serialization format, identifier scheme, actor-
  id scheme, timestamp scheme, orchestrator shape, and
  foreground / background / async mode. Pinning any of those
  at the framework level would prematurely close consumer
  freedom.

- The framework already partitions Engine behavior into a
  fact layer (PR59 / PR61 / M02 / M03 / M04 / M05). Each of
  those contracts is reused unchanged. M06 does not
  introduce a new layer; it documents how the existing
  layers compose in the re-entry direction.

- The M01-locked M-series responsibility map already
  accounts for downstream re-entry (M06 — this PR),
  effective-confidence trace (M07), complete reference
  operation (M08), and RuleStats provenance (M09). A
  framework-level result type would either pre-empt M08 or
  freeze a domain-specific representation. M06 does
  neither.

- M06 does NOT pre-define a CAPTURE_BOUND packet binding, a
  CURRENTLY_MATCHED helper, or a mechanical packet STALE
  detector. Those would extend M03's vocabulary into runtime
  mechanism, which is outside M06's scope and reserved as
  separate explicitly-directed future work that is not
  auto-scheduled by M06.
```

The contract therefore introduces no Python class, no
TypedDict, no NamedTuple, no Pydantic model, no JSON schema,
no database schema, no tool runner, no network IO, no
orchestrator, no canonical result-adapter, no investigation
launcher, no automatic role-assignment executor, no automatic
candidate materializer, no automatic review executor, no
automatic decision-record executor, no automatic invocation
dispatcher, and no automatic RuleStats updater.

---

## §4 OC-E scope

OC-E is the discontinuity between:

```
(a) the existence of a downstream result that originated from
    an investigation a consumer chose to run, and

(b) an Engine state mutation that may follow from that result
    via the existing state-mutating Engine public API.
```

M06 closes (a) -> (b) at the conceptual chain layer. M06 does
NOT close the runtime implementation of (a) -> (b); that
implementation is consumer-side and is exercised end-to-end
in M08.

M06 owns:

```
- investigation initiation as a consumer-side decision
- result trace as a NEW external source artifact (PR63 reuse)
- result-level role assignment (PR61 reuse, target granularity)
- candidate materialization admission criteria
- M02 mutation review handoff for result-derived candidates
- M05 mutation-review-family decision record reuse
- M05 §7 decision-state revalidation at invocation
- M02 §12 explicit invocation reuse
- lifecycle / Gap / contradiction separation through re-entry
- RuleStats separation through re-entry
- multi-result discipline
- process-restart and restore behavior
```

M06 does NOT own:

```
- a tool runner / network IO / orchestrator
- automatic investigation launch
- automatic adapter / role-assignment / candidate / review /
  decision-record / invocation
- a packet capture identity
- a runtime CAPTURE_BOUND / CURRENTLY_MATCHED / STALE
  mechanism
- M07 effective-confidence trace
- M08 complete domain-neutral reference operation
- M09 RuleStats provenance
```

---

## §5 M01 C2 ~ C7 mapping

M01's Lane C scaffold labels each stage with a status. M06
fixes the **conceptual** content of each stage; it does NOT
modify M01's recorded statuses (which remain historical
observations).

```
Stage in PR75-M06           M01 scaffold stage / status
---------------------------------------------------------
Stage 1 — investigation     C2 consumer-side investigation
        initiation             TODO
                            (M06 §4.1 + §5)

Stage 2 — downstream        C3 new external result trace
        result trace           TODO
                            (M06 §4.2 + §6)

Stage 3 — contextual        C4 result role assignment
        result role            TODO
        assignment          (M06 §4.3 + §9)

Stage 4 — candidate         C5 EngineInputCandidate
        materialization        UNDEFINED
        consideration       (M06 §4.4 + §10)

Stage 5 — mutation          C6 ReviewedMutationRequest
        review +               UNDEFINED
        M05 record          (M06 §4.5 + §11 + §12)

Stage 6 — explicit          C7 explicit re-entry
        Engine invocation      authorization  BLOCKED
                            (M06 §4.6 + §13)
```

C1 (operator decision record, UNDEFINED → CLOSED by M05) is
already owned by M05 and remains M05 territory after M06.
M06 references the M05 record at Stages 5 and 12 but does not
re-define the M05 contract.

---

## §6 Core boundary statements

```
A downstream result re-enters the framework only as a new
consumer-side source artifact that is separately translated,
contextually role-assigned, considered for candidate
materialization, mutation-reviewed, and explicitly invoked
through an existing Engine public API.

The result does not become Engine evidence, Engine truth,
execution authority, or lifecycle-transition authority merely
because it exists or because an investigation produced it.
```

The chain is six explicitly separate stages (§4). A success
at stage N does NOT authorize stage N+1. The chain may
legitimately terminate at any stage; see §7. Each Engine API
call is its own decision; even when multiple state-mutating
methods would plausibly be called for one investigation, each
call requires its own candidate / review / decision record /
revalidation / invocation cycle.

---

## §7 Investigation initiation

§4.1 — the consumer explicitly decides to initiate an
investigation. Permitted bases for the decision:

```
- a prior operator decision record (M05 family A or B) as
  PROVENANCE for the choice to investigate
- a Gap (ragcore.Gap) as PROVENANCE for what to look for
- a Claim status / lifecycle history as PROVENANCE for which
  investigation may be useful
- consumer-side policy as PROVENANCE
```

`request-evidence` and `schedule-manual-inspection` from M05
§4.1 are dispositions, NOT permissions. The framework provides
no tool runner, no network IO, no scheduler, and no worker
pool. Whether an investigation runs is a consumer-side
decision that is recorded outside the M05 record itself
(M06 §5).

---

## §8 Result trace

§4.2 + §6 — the result trace is a **new external source
artifact** in the PR63 sense. The PR63 §3 ~ §9 obligations
(provenance / retention / loss / derivation / unresolved
ambiguity / failure) apply unchanged. Conceptual minimum
content is 15 items at §4.2 (field names not mandated).

```
trace identity       != Engine object identity
trace producer       != Engine
trace acquisition    != Engine mutation
trace existence      != Engine truth
trace existence      != Claim status change
trace existence      != Gap resolution
trace identity       != EngineStateIdentity
trace identity       != PR51 packet capture identity
```

A trace that later changes is a NEW external source artifact
(§6.2). A previously admitted role assignment cannot be
reused; a candidate built on the prior trace is no longer
current; a new chain begins at Stage 2.

§7 fixes the operational-failure vs semantic-ambiguity
distinction; M06 explicitly forbids collapsing the two into a
single `invalid` / `unresolved` label.

---

## §9 Result role assignment

§4.3 + §9 — role assignment is at the result-item /
result-fragment level, not at the source / adapter / tool /
run level. PR61's `SourceType` / `BaseRecordType` /
`SemanticRole` / `DataAccessProfile` / `AllowedUse` /
`ForbiddenUse` axes apply unchanged.

Forbidden automatic mappings:

```
tool output type            -> SemanticRole
result source               -> SemanticRole
result field name           -> Evidence
retrieval method            -> truth
result ranking              -> Evidence.strength
severity label              -> Gap.severity
external status             -> Claim.status
result similarity           -> Evidence.strength
operator-set tool category  -> SemanticRole
adapter category            -> AllowedUse
```

§9.4 — unresolved assignment terminates the chain at Stage 3.
Termination is a normal consumer-side conclusion.

---

## §10 Candidate / review / invocation chain

§4.4 + §10 — candidate materialization is NOT automatic and
NOT required. The consumer MAY materialize a candidate, but
MUST NOT in the 6 listed conditions (unresolved assignment;
AllowedUse prohibits; operational failure prevents content
use; translation loss exceeds declared argument basis;
candidate's M02 §7 obligations cannot be filled; argument
translation has no documented basis). Archive / cite is a
valid terminal state.

§4.5 + §11 — review uses M02 §9 exact-content semantics
unchanged. The disposition is recorded as an M05
mutation-review-family record. Hard locks (M02 §24 + M05
§4.3) carry forward:

```
proposal acceptance              != mutation review approval
result role assignment           != candidate approval
candidate validator pass         != mutation review approval
approved disposition record      != ReviewedMutationRequest
ReviewedMutationRequest          != Engine invocation
```

§12 — at Stage 6, the consumer verifies M02 §10 + M06 §8
+ M05 §7.3 A conditions. Any mismatch triggers M05 §12.2: new
review cycle. The result trace is NOT a PR51 packet capture
identity; revalidation operates on `EngineStateIdentity`
only.

§4.6 + §13 — the only Engine state-mutating event is an
explicit caller-written invocation of one of the 20
state-mutating Engine public methods. M02 §12.3 forbidden
mechanisms are preserved verbatim. M06 additionally forbids
chaining one Stage 6 invocation into a subsequent Stage 6
invocation without a new candidate / review / decision /
revalidation cycle.

M02 §13 call-success semantics are unchanged: the call proves
the Engine accepted the supplied arguments and applied that
method's existing runtime behavior. It does NOT prove the
external result is true.

---

## §11 Lifecycle and RuleStats separation

§14 — `add_evidence` is one M02 candidate target;
`confirm_claim_if_ready` / `refute_claim_if_ready` /
`dispute_claim_if_ready` / `resolve_gaps_for_evidence` /
`register_contradiction` / `register_contradiction_resolution`
are separate candidate targets. The pattern

```
downstream result
  -> add_evidence
  -> confirm_claim_if_ready
```

as a single automatic pipeline is FORBIDDEN. Each transition
requires its own candidate / review / decision / revalidation
/ invocation cycle. The 6 lifecycle `*_if_ready` methods
continue to evaluate their existing pre-conditions; M06 does
NOT relax any condition.

§15 — `update_rule_stats` is one M02 candidate target. M06
does NOT introduce automatic `update_rule_stats` calls in
response to result production, Claim transitions, Evidence
registration, Gap resolution, contradiction resolution, or
investigation success / failure. RuleStats provenance
semantics are M09 (PR78) territory.

---

## §12 Earlier-contract relationships

```
PR57   operator decision boundary       preserved (M06 §18.3)
                                         + §21 addendum
PR59   external adapter translation     preserved (M06 §18.1)
       boundary                          + §32 addendum
PR61   role assignment policy           preserved (M06 §18.2)
                                         + §25 addendum
M02    reviewed mutation handoff        preserved (M06 §18.4)
                                         + §25 addendum
M03    engine read consistency          preserved (M06 §18.5)
M04    engine state identity            preserved (M06 §18.6)
M05    operator decision record /       preserved (M06 §18.3)
       revalidation                      + §21 addendum
```

M-series responsibility map (M01-locked, preserved):

```
PR74-M05  Operator Decision Record / stale revalidation  (OC-B)  CLOSED
PR75-M06  Downstream Result Re-entry                     (OC-E)  this PR
PR76-M07  Effective Confidence Calculation Trace         (OC-D)  NOT STARTED
PR77-M08  Complete Domain-Neutral Reference Operation    (OC-F)  NOT STARTED
PR78-M09  RuleStats Update Provenance                    (OC-G)  NOT STARTED
```

M06 does NOT redefine, expand, or auto-schedule M07 / M08 /
M09. A complete domain-neutral end-to-end reference operation
is M08 territory and is NOT in M06's scope.

---

## §13 Files Changed

### §13.1 New architecture contract (251차, 1cf934f)

```
docs/architecture/
  DOWNSTREAM_RESULT_REENTRY_CONTRACT.md            +1245 (new)
```

Sections §0 ~ §22 + core sentences. Authoritative for the M06
conceptual surface.

### §13.2 Normative addenda (251차, 1cf934f)

```
docs/architecture/
  EXTERNAL_ADAPTER_TRANSLATION_BOUNDARY_SPEC.md
    + §32 Post-M06 addendum                          +52
  ROLE_ASSIGNMENT_POLICY_SPEC.md
    + §25 Post-M06 addendum                          +56
  REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md
    + §25 Post-M06 addendum                          +66
  OPERATOR_DECISION_RECORD_REVALIDATION_CONTRACT.md
    + §21 Post-M06 addendum                          +53
```

Historical body text of each target file is preserved
verbatim. Each addendum appends below the file's previous
content; no prior section is rewritten.

251차 total: +1472 / -0 across 5 files.

### §13.3 Dev record (252차, this commit)

```
docs/dev/
  PR_075_DOWNSTREAM_RESULT_REENTRY_CONTRACT.md
                                                     +new
```

This file. No other file is touched by 252차.

### §13.4 Files explicitly NOT modified

```
ragcore/*
examples/*
tests/*
pyproject.toml
snapshot migration files
PR51 inspector
PR53 validator
PR55 / PR56 validators
M01 scaffold (examples/operation/minimal_operational_scaffold.py)
tests/test_minimal_operational_scaffold.py
M01 historical body
M02 §1 ~ §22 historical body
M03 §1 ~ §18 historical body
M04 §1 ~ §10 historical body
M05 §1 ~ §20 historical body
PR57 §1 ~ §18 historical body
PR59 §1 ~ §31 historical body
PR61 §1 ~ §24 historical body
M02 §23 / §24 historical addenda
M03 §19 / §20 historical addenda
M04 §11 historical addendum
historical dev records
```

M01 scaffold's C2 ~ C7 statuses are historical observations.
M06 does NOT rewrite the scaffold report or its TODO /
UNDEFINED / BLOCKED labels to reflect M06's conceptual
closure.

---

## §14 Structural and behavioral invariants

### §14.1 Structural counts (delta = 0)

```
Engine public methods            41   (unchanged from main 80759048)
Engine private methods           19   (unchanged from main 80759048)
state-mutating public methods    20   (unchanged set)
read-only public methods         19   (unchanged set)
serialization boundary            2   (unchanged set)
ragcore.__all__                  49   (unchanged from main 80759048)
snapshot schema_version           2   (unchanged)
snapshot top-level keys          18   (unchanged set)
PR51 packet keys                  7   (unchanged set, same order)
tests                          1517   (unchanged; M06 adds 0 tests)
```

PR51 packet keys (locked names):

```
claim
effective_confidence
supporting_evidence
contradictions
active_contradictions
unresolved_gaps
lifecycle_history
```

### §14.2 Behavioral invariants (delta = 0)

```
runtime behavior                    delta = 0
judgment semantics                  delta = 0
claim lifecycle condition           delta = 0
effective-confidence formula        delta = 0
modifier value table                delta = 0
Gap matching / resolution semantics delta = 0
contradiction semantics             delta = 0
RuleStats calculation               delta = 0
PR51 packet shape                   delta = 0
snapshot schema                     delta = 0
dependency surface                  delta = 0
automatic execution                 delta = 0
```

---

## §15 Regression result

```
$ python -m pytest -q
[...]
1517 passed in 1.27s
$ git diff --check
(clean)
```

No test added. No test removed. No test expectation modified.

---

## §16 Forbidden-conclusion scan

The M06 contract §20 lists 25 anti-pattern phrases that the
contract is normative against. Repository-wide scan after the
251차 commit:

```
request-evidence == tool execution authority                 0 positive
schedule-manual-inspection == automatic tool execution       0 positive
investigation success == result truth                        0 positive
external result == ragcore.Evidence                          0 positive
tool output == Evidence                                       0 positive
result score == Evidence.strength                            0 positive
external probability == base_confidence                      0 positive
severity label == Gap.severity                               0 positive
external status == Claim.status                              0 positive
result role assignment == mutation approval                  0 positive
valid role assignment == candidate required                  0 positive
candidate == accepted mutation                                0 positive
approved disposition == ReviewedMutationRequest              0 positive
ReviewedMutationRequest == invocation                        0 positive
operator proposal acceptance == mutation review approval     0 positive
add_evidence == lifecycle transition                         0 positive
Evidence registration == Claim confirmation                  0 positive
downstream result == automatic Gap resolution                0 positive
downstream result == automatic contradiction resolution      0 positive
downstream result == automatic RuleStats update              0 positive
result trace == PR51 capture identity                         0 positive
re-entry packet == CAPTURE_BOUND                              0 positive
re-entry packet == CURRENTLY_MATCHED                          0 positive
re-entry packet == STALE                                      0 positive
persistent result trace == persistent Engine lineage         0 positive
```

All 25 phrases match exactly one file each — the new
contract's own §20 anti-pattern lock list. Zero positive
assertions in normative text outside §20.

M-series drift scan also clean:

```
PR76-M07 + automatic / runtime          0
PR77-M08 + executor / runner            0
PR78-M09 + automatic RuleStats          0
```

---

## §17 M-series forward boundary

M06 closes OC-E at the conceptual chain layer. The remaining
M-series scope is M01-locked and unchanged:

```
PR76-M07   Effective Confidence Calculation Trace     (OC-D)  NOT STARTED
PR77-M08   Complete Domain-Neutral Reference Operation (OC-F)  NOT STARTED
PR78-M09   RuleStats Update Provenance                (OC-G)  NOT STARTED
```

Separate, explicitly-directed future work, NOT assigned to
any M07 / M08 / M09 slot, NOT automatically scheduled:

```
- CAPTURE_BOUND PR51 packet binding (OC-C closure follow-up)
- CURRENTLY_MATCHED comparison helper
- mechanical packet STALE detector
- automatic revalidation worker
- automatic Engine mutation worker
```

---

## §18 Closing position

> *PR75-M06 closes OC-E at the conceptual layer where it
> actually lives: the consumer-side chain that re-translates
> a downstream investigation result into a NEW external source
> artifact, contextually role-assigns each result item,
> considers materializing a NON-EXECUTABLE candidate, runs an
> M02 exact-content mutation review, persists the disposition
> as an M05 mutation-review-family record, revalidates the
> decision-time identity against the current Engine identity,
> and explicitly invokes one existing state-mutating Engine
> public method. It introduces no tool runner, no
> investigation launcher, no adapter / role-assignment /
> candidate / review / decision-record executor, no
> dispatcher, no packet binding, no stale detector, no
> automatic RuleStats update, and no lifecycle chaining.
> Everything else — a complete domain-neutral reference
> operation, effective-confidence trace, RuleStats
> provenance — remains M07 / M08 / M09 responsibility and is
> NOT auto-scheduled by M06.*

PR75-M06 is opened as **Draft** and is not merged. Closure
language (`CLOSED`) is reserved for the post-squash-merge
state. The M-series sequence after PR75-M06:

```
PR75-M06   Downstream Result Re-entry
                                       (OC-E) OPEN — DRAFT,
                                              NOT MERGED
PR76-M07   Effective Confidence Trace  (OC-D) NOT STARTED
PR77-M08   Complete Domain-Neutral
           Reference Operation         (OC-F) NOT STARTED
PR78-M09   RuleStats Update Provenance (OC-G) NOT STARTED
```

No automatic next PR. Framework waits for directive.
