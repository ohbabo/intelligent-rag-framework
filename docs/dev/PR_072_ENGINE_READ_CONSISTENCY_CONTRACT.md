# PR72-M03 — Engine Read Consistency Contract

Development record for the architecture contract landed by
PR72-M03 (branch `docs/engine-read-consistency-contract`).

```
base:            main f40b811 (PR71-M02: Reviewed Engine
                                Mutation Handoff Contract)
branch:          docs/engine-read-consistency-contract
237차 commit:    1d514d0   docs(architecture)
238차 commit:    (this record, docs/dev)
type:            framework-level architecture contract,
                  documentation only
```

This record captures the M-series investigation context, the
M01 B3 / OC-C evidence that motivates M03, the empirical
baseline observed on `main` `f40b811`, the four identity
concepts M03 separates, the two-axis conceptual claim
vocabulary, the §8 / §9 / §10 capture / use / stale layers,
the relationship to PR71-M02 and the future OC-B / PR74-M05
boundary, the repository-wide contradiction scan, the
structural invariants, and the closing position of PR72-M03.

PR72-M03 does **not** implement, execute, or schedule any
runtime change. It defines the conceptual boundary between
snapshot schema identity, Engine state identity, packet
identity, capture-time consistency, use-time consistency, and
mechanical stale determination.

---

## §1 Investigation origin

The M-series began with M01 composing existing components into
a three-lane scaffold and exposing seven operational
discontinuities (OC-A through OC-G). M02 closed the conceptual
boundary for OC-A. M03 picks up OC-C, surfaced at scaffold
stage B3 as:

```
B3  packet state binding                    UNDEFINED
```

The M01 dev record explicitly disclaims fabricating
`packet_revision`, `state_revision`, `engine_revision`,
`snapshot_digest`, or `capture_token`. M03 keeps the same
posture and adds the normative boundary that makes the
disclaimer load-bearing rather than stylistic.

M02 (`REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md`) closes
the OC-A handoff up to the explicit invocation in Layer 4.
M02 §12.3 explicitly does **not** guarantee freshness,
currentness, or state-binding at the immediate-pre-invocation
caller checks. M03 picks up exactly that boundary on the read
side.

---

## §2 P-series + M-series frozen baseline

```
main at PR72-M03 start:     f40b811d93b166a20f395218ffa54042000131be
tests:                       1423 passing
Engine public methods:       40
Engine private methods:      18
ragcore.__all__:             48
snapshot schema_version:     2
snapshot top-level keys:     18
contract last section:       §54 in DATA_CONTRACT, plus M-series
                              architecture contracts:
                              REVIEWED_ENGINE_MUTATION_HANDOFF
                              (PR71-M02) §0..§22
PR51 packet keys:            7
```

M-series state at PR72-M03 start:

```
P-series  CLOSED
PR70-M01  CLOSED
PR71-M02  CLOSED
PR72-M03  CURRENT (this PR)
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
docs/architecture/ENGINE_READ_CONSISTENCY_CONTRACT.md
                                              +965 lines    (237차, new)
docs/dev/PR_072_ENGINE_READ_CONSISTENCY_CONTRACT.md
                                              this record   (238차, new)

ragcore source delta:         0 bytes
examples files changed:       0
tests changed:                0
dependencies changed:         0
framework public symbols:     0 added
new exception classes:        0
new dependencies:             0
new snapshot keys:            0
new packet keys:              0
```

No `ragcore/` file is touched. No example file is touched. No
test is touched.

---

## §4 Empirical Cross-Check on main f40b811

### §4.1 PR51 packet shape

`examples/inspector/engine_inspector.py:49` defines:

```python
def build_engine_context_packet(engine: Engine, claim_id: int)
                                  -> dict[str, Any]:
```

It calls 7 + N public read-only methods in sequence and
returns a plain dict with exactly seven keys:

```
"claim"                  -> engine.get_claim(claim_id)
"effective_confidence"   -> engine.compute_effective_confidence(...)
"supporting_evidence"   -> engine.evidences_for_claim(...)
"contradictions"        -> engine.contradictions_for_claim(...)
"active_contradictions" -> engine.active_contradictions_for_claim(...)
"unresolved_gaps"       -> filtered engine.gaps_for_claim(...)
                           + N engine.gap_resolution(gap.id)
"lifecycle_history"     -> engine.claim_lifecycle_history(...)
```

### §4.2 Absent state-binding mechanisms

Repository-wide search across `ragcore/` and `examples/`
returns zero occurrences of every one of:

```
packet_revision        state_revision
engine_revision        snapshot_digest
capture_token          state_identity
state_token            capture_time
capture_revision       packet_state_binding
```

The only mentions are the **disclaimer** strings in
`examples/operation/minimal_operational_scaffold.py:370-372`
which explicitly state the scaffold does NOT fabricate them.

### §4.3 Absent revision counters

```
Engine._lifecycle_seq   per-Claim lifecycle audit sequence;
                        advances only on lifecycle transitions;
                        NOT an Engine-wide state revision.

Engine._next_id         per-kind ID allocator; advances only on
                        _allocate_id(kind) calls; NOT a state
                        revision.

(no other per-Engine counter for general mutations)
```

### §4.4 PR53 validator scope

`examples/inspector/packet_validator.py:311`
`validate_consumer_packet_interpretation(consumer_output,
                                          source_packet)`
detects structurally unsafe consumer interpretations
(F-codes for probability misuse, contradiction
auto-refutation, gap auto-refutation, lifecycle verdict
relabel, threshold auto-verification, engine mutation intent).

It does **not** detect: staleness, capture inconsistency,
source-state divergence, packet-to-state mismatch, digest
mismatch.

### §4.5 Snapshot boundary

`to_snapshot` produces a JSON-compatible dict with
`schema_version=2` and 18 top-level keys; `from_snapshot`
restores Engine state (with PR65 §51 + PR67 §52 admission
and integrity checks). The serialization is a persistence
boundary, not a state-instance identity.

---

## §5 Contract Locked

The contract document
`docs/architecture/ENGINE_READ_CONSISTENCY_CONTRACT.md`
contains 19 top-level sections (§0..§18) and 19 subsections.

### §5.1 Identity separation (§4 of contract)

Three identity concepts and one temporal consistency
distinction kept distinct:

```
§4.1   Snapshot schema identity
        (schema_version = serialized snapshot shape only;
         NOT Engine state revision / Engine state identity /
         packet revision / capture token / confidence policy
         revision)

§4.2   Engine state identity
        (named but NOT mechanized; future implementation may
         realize as int revision / opaque token / canonical
         digest / immutable snapshot ref / other)

§4.3   Packet identity
        (the dict / serialized object's own identity;
         packet identity != source Engine state identity)

§4.4   Capture-time vs use-time consistency distinction
        (distinct and must not be treated as interchangeable;
         a valid use-time consistency claim requires a valid
         capture-bound basis; a consistent capture can become
         stale; a stale packet can still pass a non-state-aware
         validator; an unbound packet admits no mechanical
         use-time consistency claim at all)
```

### §5.2 Today's PR51 packet classification (§5 of contract)

```
Permitted reading:
  Each builder line called a public read-only method and
  stored its return value into a known dict key. Each value is
  what that method returned at the moment it was called.

Forbidden readings (the packet is NOT):
  an atomic Engine snapshot
  a state-bound capture
  a self-revisioned read
  a state-identified projection
  a packet whose freshness can be mechanically verified
  a packet whose all-fields-from-one-state property is proven
    by construction
  a packet whose source Engine state can be re-identified
    without an external comparison basis
  "the Engine at time T"

Classification under §7 two-axis vocabulary:
  binding status              UNBOUND
  use-time comparison status  UNKNOWN (mechanically unavailable)

  This is one of the four valid combinations enumerated in
  §7.3. UNBOUND + CURRENTLY_MATCHED and UNBOUND + STALE are
  invalid; today's packet cannot be promoted out of UNBOUND
  without infrastructure that the repository does not
  provide.
```

### §5.3 Atomicity boundary (§6 of contract)

Sequential public read calls are NOT atomic capture. The
atomic claim requires at least one of:

```
(a) immutable snapshot derivation
(b) Engine-supported consistency boundary (lock /
    transaction / snapshot isolation / equivalent)
(c) bracketed revision checks with explicit retry/fail
(d) semantically equivalent mechanism with verification path
```

M03 does NOT select among (a)/(b)/(c)/(d).

The contract explicitly forbids justifying the atomic claim
on the basis of: "Python execution is fast", "the GIL
prevents interleaving", "the test is single-threaded", "no
mutation happened in the test", "the sequence is short", "the
reads are read-only", or "the example does not race".

### §5.4 Conceptual consistency vocabulary — two axes (§7 of contract)

§7 organizes the vocabulary as two **independent axes**, not a
single five-level list.

```
Binding axis:
  UNBOUND        no source-state identity binding
  CAPTURE_BOUND  bound to one source-state identity through
                  a capture satisfying §8

Use-time comparison axis:
  UNKNOWN            no valid current comparison result
  CURRENTLY_MATCHED  fresh comparison: capture identity
                      == current identity
  STALE              fresh comparison: capture identity
                      != current identity

Valid combinations:
  UNBOUND        + UNKNOWN
  CAPTURE_BOUND  + UNKNOWN
  CAPTURE_BOUND  + CURRENTLY_MATCHED
  CAPTURE_BOUND  + STALE

Invalid combinations:
  UNBOUND        + CURRENTLY_MATCHED
  UNBOUND        + STALE
```

These are **vocabulary**, not a runtime enum. They are not a
ragcore symbol, not a packet field value, not a snapshot
value, not a lifecycle status.

### §5.5 Capture-bound minimum requirements (§8 of contract)

```
§8.1   State-identity basis exists.
§8.2   Packet records its capture identity.
§8.3   All state-derived fields are part of the capture per §6.
§8.4   Construction and comparison rules explicit and
        deterministic.
§8.5   Identity not silently reused across a mutation.
```

The following are listed as INSUFFICIENT on their own:

```
Python object id / process id / wall-clock timestamp /
module hash / git commit SHA / snapshot schema_version /
packet dict hash / non-canonical JSON hash / repr(packet) /
claim_id / largest object id / count of objects in Engine
```

### §5.6 Currently-matched requires comparison (§9 of contract)

```
§9.1   Obtain current Engine state identity using §8.4 rule.
§9.2   Compare against packet's capture identity using §8.4
        rule; result must be "same state".
§9.3   The claim is scoped to that moment only.
```

### §5.7 Mechanical stale boundary (§10 of contract)

```
Today, with no §8.1 identity basis available:
  mechanical stale determination = not available

Documents MUST NOT write:
  "this packet is fresh"
  "this packet is current"
  "this packet is unchanged"
  "this packet still represents the Engine"
  "the packet validator confirms freshness"
  "the packet validator confirms staleness"

Stale-decision policy is OC-B / PR74-M05. M03 is the
fact-and-basis layer; M05 is the decision-policy layer.
```

### §5.8 Relationship to PR71-M02 (§11 of contract)

```
M02's four-layer model / §11 exact-content review binding /
§12.1-§12.2 invocation boundary / §14.1-§14.3 separation
principles / §17 A2 UNDEFINED — all unchanged.

M03 does NOT:
  - add a state-identity / capture-token field to
    ReviewedMutationRequest
  - modify M02 §10 (request content)
  - modify M02 §11 (exact-content review binding)
  - retroactively alter any M02 contract
  - require M02 records to carry an OC-C identity

Cross-cutting boundary:
  exact candidate content binding != source Engine state binding
  candidate arguments unchanged   != Engine state unchanged
  approved exact candidate review != decision-time state
                                     consistency verified
```

### §5.9 Future mechanism semantic requirements (§15 of contract)

If a future PR introduces an Engine-state-identity mechanism,
M03 records the semantic requirements it must satisfy:

```
§15.1   Connected to every state-changing public method
         (M02 §12.1 enumerates 20 state-mutating public
         methods on main f40b811).
§15.2   Read-only public methods (18 at M02 §12.1) must
         remain pure observation.
§15.3   Failed/no-op mutation identity semantics defined.
§15.4   Post-restore identity semantics defined.
§15.5   Wraparound / persistence / process-restart semantics
         defined.
§15.6   Comparison rule deterministic and decidable.
```

M03 does NOT introduce the mechanism, does NOT add a revision
field, does NOT modify any of the 20 mutating or 18 read-only
methods, and does NOT add a snapshot or packet key.

---

## §6 Repository-Wide Contradiction Scan

### §6.1 Corrected (in-place edits)

```
(none)
```

The current normative and guide documents already align with
M03. PR51 / PR53 / PR70 / PR71 phrasings already avoid the
forbidden authority promotions.

### §6.2 Aligned (cross-references kept)

```
docs/architecture/REVIEWED_ENGINE_MUTATION_HANDOFF_CONTRACT.md
  M02 §12.3 last paragraph explicitly disclaims mechanical
  freshness. M03 picks up exactly this boundary.

examples/operation/minimal_operational_scaffold.py
  Stage B3 records UNDEFINED with the explicit disclaimer
  list (packet_revision / state_revision / engine_revision /
  snapshot_digest / capture_token). M03 makes the disclaimer
  load-bearing.

docs/dev/PR_070_MINIMAL_OPERATIONAL_SCAFFOLD.md
  §8.3 "Packet state binding is absent (B3)". Aligned with
  §10 / §11 of M03 contract.

docs/architecture/ENGINE_READ_SURFACE_AUDIT.md (PR50)
docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md (PR49)
  Read surface defined as pure observation; aligned with
  §15.2.

docs/architecture/LLM_CONTEXT_PACKET_SPEC.md (PR52)
  Packet shape is decision-support signal; freshness is not
  asserted. Aligned with §13 of M03 contract.

examples/inspector/engine_inspector.py (PR51)
examples/inspector/packet_validator.py (PR53)
  Docstrings already note "Packet shape is NOT a contract"
  and "validator blocks unsafe packet interpretations". M03
  preserves both shapes exactly.
```

### §6.3 No contradiction found

Repository-wide search returned zero matches for normative
phrasings forbidden by M03:

```
"schema_version == state revision"
"packet hash == Engine state identity"
"packet validator pass == fresh state"
"sequential read == atomic snapshot"
"approved review == current state verified"
"same packet content == same Engine state"
"timestamp == capture token"
"packet is fresh" / "packet is current" / "packet is unchanged"
(as normative claims, not negations)
```

### §6.4 Historical records intentionally unchanged

No historical dev record is rewritten. PR_049 / PR_050 /
PR_051 / PR_052 / PR_053 / PR_070 / PR_071 records remain as
written.

### §6.5 Future PR candidates (recorded only)

```
State-identity mechanism implementation
  Could realize §15 semantic requirements via int revision,
  opaque token, canonical digest, immutable snapshot ref,
  or other. M03 explicitly defers the choice.

OC-B / PR74-M05  Operator decision record + stale revalidation
  Will choose a stale-decision rule on top of M03 facts.

OC-E / PR75-M06  Downstream re-entry
  Will reference OC-A handoff + OC-C state binding facts.

OC-D / PR76-M07  Effective-confidence trace
  May reference source-state identity; M03 records the
  semantic boundary but does not specify the trace mechanism.

OC-G / PR78-M09  RuleStats provenance
  Independent of M03 facts.
```

PR72-M03 does NOT auto-schedule any of the above.

---

## §7 Structural and Behavior Invariants

```
Engine public methods                40         (unchanged)
Engine private methods               18         (unchanged)
ragcore.__all__                      48         (unchanged)
snapshot schema_version              2          (unchanged)
snapshot top-level keys              18         (unchanged)
PR51 packet keys                     7          (unchanged)

ragcore files changed                0
examples files changed               0
tests changed                        0
dependencies                         0
new public symbol                    0
new Engine method                    0
new dependency                       0
new exception class                  0
new snapshot key                     0
new packet key                       0
```

### runtime behavior delta

```
0
```

### judgment semantics delta

```
0
```

### lifecycle delta

```
0
```

### confidence formula delta

```
0
```

### snapshot delta

```
0
```

### documentation interpretation delta

```
+ snapshot schema_version != Engine state revision (locked)
+ snapshot schema_version != Engine state identity (locked)
+ packet identity != source Engine state identity (locked)
+ sequential reads != atomic capture (locked)
+ capture-time consistency != use-time freshness (locked)
+ packet validator pass != source-state freshness (locked)
+ today's PR51 packet classified as UNBOUND + UNKNOWN under
  the two-axis vocabulary (§5.5 / §7.3)
+ §6 atomic-capture (a)/(b)/(c)/(d) requirement list
+ §7 two-axis consistency vocabulary (binding axis +
  use-time comparison axis)
+ §8 five capture-bound minimum requirements + insufficient
  identity basis enumeration
+ §9 currently-matched comparison requirements
+ §10 mechanical stale = not available (today)
+ §11 M02 boundary preserved; cross-cutting candidate-vs-state
  binding distinction
+ §12 M03 = fact layer, M05 = decision layer
+ §15 future mechanism semantic requirements §15.1..§15.6
```

---

## §8 Regression Result

`pytest -q` on 237차 commit `1d514d0`:

```
1423 passed
```

Identical to the baseline at `main` `f40b811`. PR72-M03 is
documentation only.

---

## §9 Self-Review

```
[x] M03 is documentation only. No ragcore/, examples/,
    tests/, or dependency file modified.

[x] Current PR51 packet is NOT called "atomic", "state-bound",
    "self-revisioned", or "state-identified". §5.2 enumerates
    the forbidden readings.

[x] No revision / token / digest field is fabricated. §2.2 /
    §2.3 / §17 (Non-goals) all reaffirm.

[x] PR53 validator is NOT promoted to a freshness or
    state-identity validator (§5.4 / §13.2).

[x] schema_version and Engine state revision are explicitly
    distinct (§3 / §4.1 / §14).

[x] Packet identity and Engine state identity are explicitly
    distinct (§3 / §4.3).

[x] Capture-time and use-time consistency are explicitly
    separated (§3 / §4.4).

[x] Sequential reads are NOT called atomic; §6 enumerates the
    forbidden justifications (GIL / Python speed / short
    sequence / read-only / single-threaded / example does
    not race).

[x] Mechanical staleness is NOT claimed without comparison
    basis (§10).

[x] Stale-decision policy is deferred to OC-B / PR74-M05.

[x] M03 does NOT modify M02 records (§11.2). M02's four-layer
    model, exact-content review binding, invocation boundary,
    separation principles, and A2 status all preserved.

[x] PR51 7-key packet shape NOT modified (§13.1).
[x] PR53 F-code inventory NOT modified (§13.2).
[x] Snapshot schema NOT modified (§14).

[x] No canonicalization / hash / digest / signing scheme is
    specified (§14).

[x] Future mechanism semantic requirements (§15.1..§15.6)
    recorded, mechanism itself NOT introduced.

[x] OC-B / OC-D / OC-E / OC-G responsibilities preserved (§16).

[x] Domain-specific vocabulary NOT in the normative body
    (word-boundary scan: 0 matches for the standard
    forbidden-domain word list and the related two-word
    safety-verdict phrase across both contract and dev record,
    audit-list quotation excluded per PR59 §17 / PR63 / PR68
    convention).

[x] PR73-M04 / PR74-M05 / PR75-M06 / PR76-M07 / PR77-M08 /
    PR78-M09 NOT auto-started.

[x] Engine 40 / 18, ragcore.__all__ 48, schema_version 2,
    18 top-level keys, PR51 7-key packet shape all
    unchanged (AST + literal grep verification).
```

---

## §10 Closing Position

PR72-M03 is a draft PR with three commits (237차 / 238차 /
239차) at the time of this record. PR72-M03 is **not** CLOSED
at this point; the directive explicitly excludes merge from
this work item, and an internal-contract correction (235차/
239차 pattern) is part of the draft phase rather than a
closing event.

Until a separate final-audit-and-merge directive is issued,
the M-series state is:

```
P-series   CLOSED
PR70-M01   CLOSED
PR71-M02   CLOSED
PR72-M03   CORRECTED — OPEN, DRAFT, NOT MERGED
PR73-M04   CONDITIONAL / NOT STARTED
PR74-M05   NOT STARTED
PR75-M06   NOT STARTED
PR76-M07   NOT STARTED
PR77-M08   NOT STARTED
PR78-M09   NOT STARTED
```

After that separate directive squash-merges this PR, and only
then, the M-series state becomes:

```
P-series   CLOSED
PR70-M01   CLOSED
PR71-M02   CLOSED
PR72-M03   CLOSED
PR73-M04   CONDITIONAL / NOT STARTED
PR74-M05   NOT STARTED
PR75-M06   NOT STARTED
PR76-M07   NOT STARTED
PR77-M08   NOT STARTED
PR78-M09   NOT STARTED
```

PR72-M03 does not auto-schedule any follow-up PR.

PR72-M03는 현재 Engine context packet이 제공하는 read projection과
제공하지 않는 state-binding·atomicity·freshness 보장을 분리하고,
snapshot schema identity, packet identity, Engine state identity를
서로 동일시하지 않도록 잠갔다. 또한 capture-time consistency와
use-time consistency를 구분하고, mechanical stale 판단에는 명시적인
comparison basis가 필요함을 정의했으며, stale 처리 정책과 persistent
operator decision record는 PR74-M05 책임으로 남겼다. runtime behavior,
Engine judgment semantics, packet shape, snapshot schema는 변경하지
않았다.

---

## Post-review correction — 239차

After the initial 237차 / 238차 commits, a final audit of the
contract found six internal contract defects (not runtime
defects). The corrections are made on the same branch as a
single post-review commit; the prior two commits are not
amended, rebased, or squashed.

These corrections do not change M03's direction. The OC-C
investigation, the fact-and-basis layer scope, the §2
empirical baseline observations, the M02 boundary
preservation, the M05 deferral, and the docs-only scope are
all preserved.

**C1 — Actual read-call count corrected to 7 + N.**
The initial wording counted `6 + N` sequential public read
calls. The actual call path of `build_engine_context_packet`
(verified at `examples/inspector/engine_inspector.py:49`)
contains seven distinct named public reads in addition to
the N `gap_resolution(gap.id)` lookups:

```
1   get_claim
2   compute_effective_confidence
3   evidences_for_claim
4   contradictions_for_claim
5   active_contradictions_for_claim
6   gaps_for_claim
N   gap_resolution (one per gap returned by gaps_for_claim)
7   claim_lifecycle_history
```

The contract §2.1 list is now annotated `7 + N sequential
public read calls total` with each call labeled. §6 atomic
capture boundary reads `7 + N`. The packet's seven keys and
the seven + N read calls are explicitly noted as
**independent counts**; one does not imply the other.

**C2 — Two-axis vocabulary in place of a five-level list.**
The initial §7 organized `UNBOUND / CAPTURE_BOUND /
CURRENTLY_MATCHED / STALE / UNKNOWN` as a single list. That
collapsed a binding-axis classification (UNBOUND /
CAPTURE_BOUND) with a use-time comparison-axis classification
(UNKNOWN / CURRENTLY_MATCHED / STALE).

§7 is now split into:

```
§7.1   Binding axis        UNBOUND / CAPTURE_BOUND
§7.2   Use-time comparison axis
                            UNKNOWN / CURRENTLY_MATCHED / STALE
§7.3   Valid and invalid combinations
        valid:    UNBOUND       + UNKNOWN
                  CAPTURE_BOUND + UNKNOWN
                  CAPTURE_BOUND + CURRENTLY_MATCHED
                  CAPTURE_BOUND + STALE
        invalid:  UNBOUND       + CURRENTLY_MATCHED
                  UNBOUND       + STALE
```

§3 core boundary now includes
`A CURRENTLY_MATCHED or STALE claim requires CAPTURE_BOUND`.
§5.5 (today's PR51 packet classification) is now stated as
the combination `UNBOUND + UNKNOWN (mechanically
unavailable)`, citing §7.3 explicitly. The §18 closing
position reflects the same combination.

**C3 — Expired CURRENTLY_MATCHED separated from lost capture
binding.**
The initial §9.3 read "re-using a CURRENTLY_MATCHED claim
after a later mutation is equivalent to dropping back to
UNKNOWN", which collapsed the binding and comparison axes
again.

§9.3 now reads "the CURRENTLY_MATCHED comparison result is
scoped to the comparison moment ... an expired comparison
result leaves the packet's binding status unchanged
(CAPTURE_BOUND) and resets the comparison status to UNKNOWN.
The packet does NOT drop back to UNBOUND."

A new §9.4 "Expiry locks" enumerates:

```
expired comparison result        != lost capture binding
CAPTURE_BOUND + comparison UNKNOWN is a valid combination
                                    (§7.3)
re-obtaining CURRENTLY_MATCHED /
  STALE                          requires a fresh §9.1 / §9.2
                                    comparison; the prior result
                                    cannot be reused
```

**C4 — Identity terminology and identity count corrected.**
The initial §4 prologue read "Four identity concepts must not
be collapsed", and the §3 core boundary list referenced an
undefined "snapshot instance identity" / "state instance
identity".

The contract now:

- §4 prologue reads "Three identity concepts and one temporal
  consistency distinction must not be collapsed" with an
  explicit list of (§4.1 / §4.2 / §4.3 / §4.4).
- §4.2 is titled "Engine state identity" (not "Engine state
  instance identity").
- §3 / §4.1 / §14 use `Engine state identity` as the
  identity-axis term; `snapshot schema validity != identity
  of the logical Engine state represented by the snapshot`
  replaces the ambiguous `snapshot instance identity` phrase.
- `state instance identity` is removed everywhere from the
  contract and dev record normative bodies.

**C5 — `independent` wording replaced with `distinct +
prerequisite`.**
The initial §4.4 ended with "The two are independent." This
overstated the relationship: use-time consistency cannot stand
alone without a capture-bound basis.

§4.4 now reads:

```
Capture-time consistency and use-time consistency are
distinct and must not be treated as interchangeable. They
are not unconditionally independent either: a valid use-time
consistency claim requires a valid capture-bound basis, so
the use-time axis presupposes the capture axis.
```

with an explicit note that an unbound packet admits no
mechanical use-time consistency claim at all (cross-reference
to §7.2 / §7.3).

**C6 — Draft / merge / CLOSED lifecycle corrected.**
The initial §10 closing position simultaneously asserted:

```
"PR72-M03 is closed when 237 / 238 exist"
"this PR is draft and merge is not part of the directive"
"After merge: PR72-M03 ready (this PR — draft)"
```

These three statements form a contradiction: a draft cannot
be CLOSED, and "ready" describes the pre-merge moment, not
the after-merge moment.

§10 now distinguishes two states:

```
- During the draft phase (including 237 / 238 / 239차 and any
  further post-review corrections), PR72-M03 is
  CORRECTED — OPEN, DRAFT, NOT MERGED.

- Only after a separate final-audit-and-merge directive
  squash-merges this PR does PR72-M03 become CLOSED.
```

The two corresponding M-series state tables are recorded
explicitly so neither state can be claimed by accident.

### Minor consistency adjustments

- The dev record opening note ("M-series investigation
  context") aligns "five-level conceptual claim concepts"
  to "two-axis conceptual claim concepts".
- The §5.4 description and §7 cross-references inside the
  dev record now match the two-axis structure of the contract.
- The Documentation interpretation delta list entry
  ("today's PR51 packet classified as UNBOUND / UNKNOWN")
  reads "UNBOUND + UNKNOWN under the two-axis vocabulary
  (§5.5 / §7.3)".
- The Documentation interpretation delta list entry
  ("§7 five-level consistency claim vocabulary") reads
  "§7 two-axis consistency vocabulary (binding axis +
  use-time comparison axis)".

### Defect counts

```
Pre-existing repository normative contradictions found:    0
M03 internal contract defects found during post-review:    6
M03 internal contract defects remaining after 239차:        0
```

### Files changed by 239차

```
docs/architecture/ENGINE_READ_CONSISTENCY_CONTRACT.md
docs/dev/PR_072_ENGINE_READ_CONSISTENCY_CONTRACT.md
```

No `ragcore/` file is touched. No example file is touched. No
test is touched. No dependency change.

### Re-measured invariants on 239차

```
Engine public methods                40         (unchanged)
Engine private methods               18         (unchanged)
ragcore.__all__                      48         (unchanged)
snapshot schema_version              2          (unchanged)
snapshot top-level keys              18         (unchanged)
PR51 packet keys                     7          (unchanged)

ragcore files changed                0
examples files changed               0
tests changed                        0
dependencies changed                 0
new public symbol                    0
new Engine method                    0
new dependency                       0
new exception class                  0
new snapshot key                     0
new packet key                       0

runtime behavior delta               0
judgment semantics delta             0
lifecycle delta                      0
confidence formula delta             0
snapshot delta                       0
```

`pytest -q` on 239차: `1423 passed`.

PR72-M03 remains DRAFT, NOT MERGED. PR73-M04 is NOT
auto-started by this correction.
