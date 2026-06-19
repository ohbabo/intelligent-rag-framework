# PR74-M05 — Operator Decision Record and Decision-State Revalidation Contract

Development record for the architecture contract landed by
PR74-M05 (branch `docs/operator-decision-record-revalidation`).

```
base:            main 04f591b (PR73-M04 — Engine State Identity
                                Primitive MVP)
branch:          docs/operator-decision-record-revalidation
247차 commit:    d1635fa   docs(architecture): define operator
                            decision revalidation contract
248차 commit:    (this record, docs/dev)
type:            framework-level architecture contract,
                  documentation only
status:          normative
```

This record captures the M-series investigation context, the
OC-B / B8 / C1 origin, the empirical baseline observed on
`main` `04f591b`, the rationale for keeping M05 docs-only, the
two decision families M05 keeps separate, the conceptual
record obligations, the append-only / supersession discipline,
the four identity-comparison cases of decision-state
revalidation, the subject-content + Engine-state two-check
matrix, the moment-scoped comparison limitation, the PR51
`UNBOUND + UNKNOWN` preservation, the process-restart / restore
behavior, the M01-locked M06-M09 boundary, the files changed,
the structural invariants, the pytest result, and the
repository-wide forbidden-conclusion scan.

PR74-M05 does **not** implement, execute, or schedule any
runtime change. It defines the conceptual boundary between
the proposal-gate decision (PR57), the mutation-review
disposition (M02), the per-Engine identity primitive (M04),
and the consumer-side record persistence + reuse policy that
sits across all three.

---

## §1 Investigation origin

The M-series began with M01 (PR70-M01) composing existing
components into a three-lane scaffold and exposing seven
operational discontinuities (OC-A through OC-G). M01 left two
stages explicitly UNDEFINED:

```
B8  operator decision record                UNDEFINED
C1  operator decision record                UNDEFINED
```

Both stages carry the `OC-B` label. M02 closed the conceptual
boundary for OC-A. M03 closed the conceptual boundary for OC-C
at the read-consistency vocabulary layer. M04 implemented the
minimal read-consistency primitive (`EngineStateIdentity`) on
top of which OC-B's decision-state revalidation can be defined
mechanically.

PR74-M05 picks up OC-B at the **record shape + reuse-policy**
layer. The M01 dev record explicitly disclaims fabricating a
`OperatorDecisionRecord` Python class; M05 keeps the same
posture and adds the normative boundary that makes the
disclaimer load-bearing rather than stylistic.

---

## §2 P-series + M-series frozen baseline

```
main at PR74-M05 start:     04f591b14b9156bb7b17089ded2670d84745fdd2
tests:                       1517 passing
Engine public methods:       41 (post-M04)
Engine private methods:      19 (post-M04)
state-mutating public:       20 (set unchanged from M02 §12.1)
read-only public:            19 (includes state_identity)
serialization boundary:       2 (to_snapshot, from_snapshot)
ragcore.__all__:             49 (includes EngineStateIdentity)
snapshot schema_version:      2
snapshot top-level keys:     18
PR51 packet keys:             7
```

M-series state at PR74-M05 start:

```
P-series   CLOSED
PR70-M01   CLOSED
PR71-M02   CLOSED
PR72-M03   CLOSED
PR73-M04   CLOSED
PR74-M05   IN PROGRESS (this PR, Draft)
PR75-M06   NOT STARTED
PR76-M07   NOT STARTED
PR77-M08   NOT STARTED
PR78-M09   NOT STARTED
```

---

## §3 Why M05 is docs-only

M05 is docs-only by deliberate design.

```
- M05 owns conceptual obligations: record shape, persistence
  discipline, and reuse policy. None of those obligations
  requires a Python class to exist.

- A consumer-side adapter chooses the storage substrate, the
  serialization format, the timestamp scheme, the actor-id
  scheme, and the content-equivalence mechanism. Pinning any
  of those at the framework level would prematurely close
  consumer freedom.

- M02 / M03 / M04 already partition Engine behavior into a
  fact layer. The decision record is a consumer-side audit
  fact, not an Engine fact. Putting it under ragcore would
  conflate the two.

- The M01-locked M06-M09 responsibility map already accounts
  for downstream re-entry (M06), effective-confidence trace
  (M07), complete reference operation (M08), and RuleStats
  provenance (M09). None of those benefits from a
  framework-level decision-record type.

- M05 does NOT pre-define a CAPTURE_BOUND packet binding,
  CURRENTLY_MATCHED helper, or mechanical packet STALE
  detector. Those would extend M03's vocabulary into runtime
  mechanism, which is outside M05's scope. M05 stops at
  decision-record reuse policy.
```

The contract therefore introduces no Python class, no
TypedDict, no Pydantic model, no JSON schema, no database
schema, no audit-log backend, no operator UI, no
authentication / authorization, no signature / digest, no
Engine method, no dispatcher / executor, no packet-binding
helper, and no automatic revalidation worker.

---

## §4 Two distinct decision families

M05 freezes two **separate** decision families. A record must
declare which family it belongs to and must not carry
semantics from the other family.

```
Family A — PR57 proposal gate
  permitted dispositions:
    accept / reject / rewrite / request-evidence /
    schedule-manual-inspection / archive / cite

Family B — M02 mutation review
  permitted dispositions:
    approved / rejected / hold
```

Hard locks:

```
proposal acceptance     != mutation review approval
proposal rejection      != mutation candidate rejection
operator decision record != ReviewedMutationRequest
approved mutation review
  -> may PERMIT separate ReviewedMutationRequest materialization
  != automatic request creation
  != Engine invocation
a single `accepted: bool` field MUST NOT represent both
  decision families
```

A disposition from one family must not be interpreted under
the other family's semantics.

---

## §5 Conceptual minimum record content

The contract freezes conceptual obligations, not Python field
names or serialization keys. Every record must conceptually
preserve:

```
 1. record identity                          (opaque, consumer-assigned)
 2. decision family                          (proposal-gate or mutation-review)
 3. exact decision subject identity          (proposal / candidate id)
 4. exact decision subject content reference (consumer mechanism)
 5. family-scoped disposition
 6. decision actor reference                 (consumer scheme)
 7. decision-time reference                  (consumer scheme)
 8. rationale / decision basis
 9. source validation or review evidence
      proposal family:    PR55 result, PR56 result
      mutation-review:    exact candidate disposition,
                          reviewed target / arguments / IDs,
                          source-basis reference (M02 §7)
10. decision-time EngineStateIdentity        (engine_token, revision)
11. explicit state-basis limitation          (not packet capture identity)
12. downstream intent / gate reference       (consumer metadata only)
13. supersession reference                   (when applicable)
```

Forbidden conflations:

```
record identity            != Engine object identity
record identity            != EngineStateIdentity
decision subject identity  != EngineStateIdentity
decision-time              != Engine wall-clock state
EngineStateIdentity        != PR51 packet capture identity
decision record            != Engine truth record
decision record            != mutation receipt
decision record            != ReviewedMutationRequest
decision record            != execution command
```

---

## §6 Append-only persistence + supersession

Decision facts are append-only in meaning.

```
existing decision record
  MUST NOT be silently rewritten

changed proposal
  -> new proposal subject
  -> PR55 / PR56 validators rerun
  -> new operator decision record

changed mutation candidate
  -> new EngineInputCandidate
  -> new mutation review per M02 §9
  -> new decision record

changed rationale / disposition / actor
  -> new decision record (NOT in-place edit)

later decision
  -> may reference prior record as superseded
  -> does NOT erase prior record
```

Non-mandated mechanisms: storage substrate, serialization
format, retention period, deletion policy, id allocator. The
contract requires only the append-only / supersession
discipline.

---

## §7 Four identity-comparison cases

Decision-state revalidation operates on `EngineStateIdentity`
value equality between a recorded identity and a current
identity obtained from `Engine.state_identity()` at the
revalidation moment.

```
Case A — recorded.token == current.token
       AND recorded.revision == current.revision
  -> decision MAY remain eligible for immediate downstream
     gate consideration; exact subject content must also be
     unchanged; all downstream-specific gates still apply;
     NO automatic action; NO Engine mutation; NO tool exec

Case B — recorded.token == current.token
       AND recorded.revision != current.revision
  -> prior decision MUST NOT be reused; record preserved as
     historical audit; rerun applicable validation/review
     path; new decision record; new record may supersede
     prior. May be described as "stale for decision reuse";
     MUST NOT be described as "M03 packet STALE"

Case C — recorded.token != current.token
  -> different runtime lineage; revisions NOT ordered across
     lineages; prior decision MUST NOT be reused; snapshot
     equivalence does NOT restore comparability; new cycle
     required

Case D — identity missing or malformed
  -> mechanical revalidation UNAVAILABLE; reuse BLOCKED;
     new decision required; historical record preserved
```

Forbidden conclusions from Case A:

```
- PR51 packet is fresh
- PR51 packet is CAPTURE_BOUND
- PR51 packet is CURRENTLY_MATCHED
- packet capture was atomic
- proposal is correct
- mutation is authorized automatically
```

---

## §8 Subject-content + Engine-state two-check matrix

```
subject same    + identity same
  -> eligible for immediate downstream gate consideration
     (Case A forbidden conclusions still apply)

subject changed + identity same
  -> new review required

subject same    + identity changed
  -> new review required

subject changed + identity changed
  -> new review required

either comparison unavailable
  -> new review required
```

Hard locks:

```
same candidate content  != same Engine state
same Engine identity    != same candidate content
content equality        != decision-state equality
state-identity equality != content equality
```

---

## §9 Moment-scoped comparison

```
identity comparison result
  != persistent freshness guarantee

identity check
  != lock

identity check
  != transaction

identity check followed by action
  != atomic check-and-act
```

The consumer must perform decision-state revalidation
**immediately before** the next downstream gate consideration
or explicit M02 invocation consideration. M05 does NOT claim
that no concurrent mutation can occur between the comparison
and a later action; M05 does NOT introduce locks,
transactions, retry loops, or seqlocks.

---

## §10 PR51 packet boundary preservation

```
binding status (M03 §7.1):             UNBOUND
use-time comparison status (M03 §7.2): UNKNOWN
```

M05 explicitly preserves the M03 §7 locks:

```
decision-time EngineStateIdentity != PR51 packet capture identity
decision-state match               != PR51 packet CURRENTLY_MATCHED
decision-state mismatch            != PR51 packet STALE
```

When the consumer rebuilds a PR51 packet after a failed
decision-state revalidation, the rebuilt packet remains
`UNBOUND + UNKNOWN`. The new decision-time
`EngineStateIdentity` is NOT carried as a packet capture
field.

M05 does NOT close OC-C (PR51 packet binding). A future
CAPTURE_BOUND packet binding remains separate,
explicitly-directed future work, not auto-scheduled.

---

## §11 Process restart and restore

```
persistent operator decision record
  != persistent Engine runtime lineage
```

After process restart or `Engine.from_snapshot(...)`:

```
current Engine receives a FRESH engine_token         (M04 §4.5)
current Engine starts at revision = 0                (M04 §4.4)
recorded_engine_token != current_engine_token        -> §7 Case C
```

Therefore: prior decision cannot be mechanically reused;
revisions must not be ordered across the lineages; equivalent
snapshot content does not restore comparability; a new
decision cycle is required.

This intentional separation between **persistence of the
decision fact** and **continuity of the runtime lineage** is
the load-bearing distinction that M04's §4.5 / §8.2 already
established and that M05 inherits.

---

## §12 M06-M09 responsibility preservation

The M01-locked M-series plan is preserved verbatim.

```
PR74-M05  Operator Decision Record / stale revalidation  (OC-B)
PR75-M06  Downstream Result Re-entry                     (OC-E)
PR76-M07  Effective Confidence Calculation Trace         (OC-D)
PR77-M08  Complete Domain-Neutral Reference Operation    (OC-F)
PR78-M09  RuleStats Update Provenance                    (OC-G)
```

M05 does NOT redefine, expand, or auto-schedule M06 ~ M09.
The following items remain **separate, explicitly-directed
future work, NOT assigned to any M06-M09 slot, NOT
automatically scheduled**:

```
- CAPTURE_BOUND PR51 packet binding (OC-C closure)
- CURRENTLY_MATCHED comparison helper
- mechanical packet STALE detector
- automatic revalidation worker
- automatic Engine mutation after a passed revalidation
```

---

## §13 Files Changed

### §13.1 New architecture contract (247차, d1635fa)

```
docs/architecture/
  OPERATOR_DECISION_RECORD_REVALIDATION_CONTRACT.md    +1119 (new)
```

Sections §0 ~ §20 + core sentences. Authoritative for the
M05 conceptual surface.

### §13.2 Normative addenda (247차, d1635fa)

```
docs/architecture/
  OPERATOR_DECISION_BOUNDARY_SPEC.md
    + §19 Post-M05 addendum                              +36
  REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md
    + §24 Post-M05 addendum                              +57
  ENGINE_READ_CONSISTENCY_CONTRACT.md
    + §20 Post-M05 addendum                              +55
  ENGINE_STATE_IDENTITY_PRIMITIVE_CONTRACT.md
    + §11 Post-M05 addendum                              +68
```

Historical body text of each target file is preserved
verbatim. Each addendum appends below the file's previous
content; no prior section is rewritten.

### §13.3 Dev record (248차, this commit)

```
docs/dev/
  PR_074_OPERATOR_DECISION_RECORD_REVALIDATION_CONTRACT.md
                                                         +new
```

This file. No other file is touched by 248차.

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
M01 scaffold
M01 historical body
M02 §1 ~ §22 historical body
M03 §1 ~ §18 historical body
M04 §1 ~ §10 historical body
PR57 §1 ~ §18 historical body
M02 §23 historical body (existing post-M04 addendum)
M03 §19 historical body (existing post-M04 addendum)
historical dev records
```

---

## §14 Structural and behavioral invariants

### §14.1 Structural counts (delta = 0)

```
Engine public methods            41   (unchanged from main 04f591b)
Engine private methods           19   (unchanged from main 04f591b)
state-mutating public methods    20   (unchanged set)
read-only public methods         19   (unchanged set)
serialization boundary            2   (unchanged set)
ragcore.__all__                  49   (unchanged from main 04f591b)
snapshot schema_version           2   (unchanged)
snapshot top-level keys          18   (unchanged set)
PR51 packet keys                  7   (unchanged set, same order)
tests                          1517   (unchanged; M05 adds 0 tests)
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
1517 passed
$ git diff --check
(clean)
```

No test added. No test removed. No test expectation modified.

---

## §16 Repository-wide forbidden-conclusion scan

The M05 contract §17 lists 13 anti-pattern conclusions that
the contract is normative against. Repository-wide scan after
the 247차 commit:

```
operator accepted == Engine truth                       0 positive
operator accepted == Engine mutation                    0 positive
decision record == ReviewedMutationRequest              0 positive
decision record == execution command                    0 positive
decision identity == packet capture identity            0 positive
decision-state match == packet CURRENTLY_MATCHED        0 positive
decision-state mismatch == packet STALE                 0 positive
UNBOUND + STALE                                          0 positive
UNBOUND + CURRENTLY_MATCHED                              0 positive
persistent decision record == persistent Engine lineage 0 positive
different engine_token revisions are ordered            0 positive
validator pass == accepted                               0 positive
single accepted bool covers both families                0 positive
```

All raw grep hits for these phrases appear inside the M05
contract §17 anti-pattern lock list, inside M03 §20's
explicit "remain forbidden" statement that references M03
§7.3, or inside the PR_072 dev record's existing reference to
the M03 §7.3 forbidden two-axis combinations. Zero positive
assertions of any forbidden conclusion in normative text.

Repository-wide M-series drift scan also clean:

```
PR75-M06 + CAPTURE_BOUND       0
PR76-M07 + CURRENTLY_MATCHED   0
PR77-M08 + stale               0
PR78-M09 + reserved            0
```

---

## §17 Self-review

```
[x]  1. M05 is docs-only at the runtime layer.
[x]  2. ragcore/* not touched.
[x]  3. examples/* not touched.
[x]  4. tests/* not touched.
[x]  5. pyproject.toml not touched.
[x]  6. snapshot migration files not touched.
[x]  7. PR51 inspector not touched.
[x]  8. PR53 / PR55 / PR56 validators not touched.
[x]  9. M01 scaffold not touched.
[x] 10. Historical body of M02 / M03 / M04 / PR57 not rewritten.
[x] 11. Each addendum appears at the end of its target file
        (M02 §24, M03 §20, M04 §11, PR57 §19), below all
        prior content.
[x] 12. M05 contract §0 lists in-scope, out-of-scope, and
        explicitly-unimplemented items separately.
[x] 13. Two decision families are kept separate at §4 with
        hard locks at §4.3.
[x] 14. Record content obligations are conceptual only (§5),
        with no Python field-name mandate.
[x] 15. Append-only / supersession discipline at §6.
[x] 16. Decision-state revalidation operates on
        EngineStateIdentity value equality only (§7.2).
[x] 17. Four cases at §7.3 exhaust pairwise comparison.
[x] 18. Subject-content and Engine-state checks are
        independent (§8); 4-case matrix; hard locks.
[x] 19. Comparison is moment-scoped; no lock /
        transaction / retry / seqlock claim (§9).
[x] 20. PR51 packet preserved as UNBOUND + UNKNOWN (§10);
        rebuild guidance preserved.
[x] 21. Proposal-gate policy (§11) keeps rewrite as a new
        subject, request-evidence != add_evidence
        authorization, schedule-manual-inspection != tool
        execution.
[x] 22. Mutation-review policy (§12) preserves M02 §11 /
        §12 / §12.3.
[x] 23. Process restart / restore behavior (§13) keeps
        persistent decision record != persistent Engine
        runtime lineage.
[x] 24. PR57 ragcore-symbol lock preserved (§14.1).
[x] 25. M02 four-layer model preserved (§14.2).
[x] 26. M03 UNBOUND + UNKNOWN preserved (§14.3).
[x] 27. M04 public contract + 245차/246차 corrections
        preserved verbatim (§14.4).
[x] 28. M01-locked M-series plan preserved (§14.5).
[x] 29. M06-M09 not auto-scheduled.
[x] 30. PR is opened as Draft and is not merged.
[x] 31. Forbidden-conclusion repo scan returns 0 positive
        assertions for every phrase in §17 (§16 of this
        record).
[x] 32. M-series drift scan (PR75-M06 / PR76-M07 / PR77-M08
        / PR78-M09 + identity-mechanism follow-ups) returns 0.
[x] 33. pytest 1517 passed; git diff --check clean.
```

---

## §18 Closing position

> *PR74-M05 closes OC-B at the conceptual layer where it
> actually lives: the consumer-side record persistence and
> reuse policy. It does not promote the operator decision
> into Engine truth, into a `ReviewedMutationRequest`, or
> into a state-bound PR51 packet. It uses M04's
> `EngineStateIdentity` equality as the mechanical comparison
> basis for decision reuse and adds the minimum two-check
> basis (exact subject content + Engine-state identity) for
> determining whether a prior decision may remain eligible
> for immediate downstream gate consideration. The two-check
> basis does NOT replace any downstream gate, does NOT
> establish check-and-act atomicity, and does NOT establish
> reuse safety. Its identity-comparison result is scoped only
> to the revalidation moment. Everything else — packet
> binding, mechanical stale detection, automatic
> revalidation, automatic execution — remains separate,
> explicitly-directed future work or M01-locked M06-M09
> responsibility.*

PR74-M05 is opened as **Draft** and is not merged. Closure
language (`CLOSED`) is reserved for the post-squash-merge
state. The M-series sequence after PR74-M05:

```
PR74-M05   Operator Decision Record /
           stale revalidation             (OC-B) OPEN — DRAFT,
                                                  NOT MERGED
PR75-M06   Downstream Result Re-entry     (OC-E) NOT STARTED
PR76-M07   Effective Confidence Trace     (OC-D) NOT STARTED
PR77-M08   Complete Domain-Neutral
           Reference Operation            (OC-F) NOT STARTED
PR78-M09   RuleStats Update Provenance    (OC-G) NOT STARTED
```

No automatic next PR. Framework waits for directive.
