# Engine State Identity Primitive Contract

```
PR73-M04 — Engine State Identity Primitive MVP
type:    feature contract (implementation in 243차)
status:  normative
date:    2026-06-18
```

> **A state identity primitive provides a per-Engine basis for comparing whether two reads originated from the same logical Engine state. It is not atomic packet capture, not packet binding, and not a stale-decision policy.**

This document defines the contract for the
`EngineStateIdentity` value type and the
`Engine.state_identity()` read-only public method introduced
by PR73-M04. The implementation in 243차 satisfies this
contract.

---

## §0 Scope limitation

§0 is a hard scope lock.

§0.1 **In scope.** A read-only public method that returns an
opaque, comparable identity for the current Engine logical
state, advancing once per completed logical mutation across
the existing 20 state-mutating public methods.

§0.2 **Out of scope.** PR73-M04 does **not**:

```
- modify the PR51 7-key context-packet shape
- add an identity field to PR51 packets
- wrap multiple read calls in a capture-time boundary
- introduce a lock, transaction, snapshot isolation, retry,
  or atomic-batch primitive
- implement a stale detector or a stale-rejection policy
- implement operator decision record persistence
- implement automatic revalidation or automatic mutation
- introduce a canonical-JSON, hash, digest, or signing scheme
- persist identity into the snapshot
- carry identity across to_snapshot / from_snapshot
- modify any of the 20 state-mutating methods' existing
  judgment behavior, validation order, return shape, or
  exception type
- modify any of the 18 read-only methods' return shape or
  contents
- modify lifecycle transition conditions or modifier values
- introduce a domain-specific workflow, network call, or LLM
  call
```

M03's §6 atomic-capture boundary remains in force. The
primitive added here is a comparison basis, not a capture
guarantee.

---

## §1 Public contract

### §1.1 Value type

```python
@dataclass(frozen=True)
class EngineStateIdentity:
    engine_token: str
    revision: int
```

Exported from `ragcore` (added to `ragcore.__all__`).

`engine_token` is a process-local opaque string identifying
one Engine runtime lineage. `revision` is a non-negative
integer that advances exactly once per completed logical
state change inside that lineage.

### §1.2 Public method

```python
class Engine:
    def state_identity(self) -> EngineStateIdentity: ...
```

Read-only. Returns the current Engine state identity. Does
not mutate Engine state, does not advance `revision`, and
does not expose any internal mutable object.

### §1.3 Comparison rules

```
Supported comparison:    value equality (==).
Supported on tokens:     equality only. Tokens are not
                          interpreted, sorted, or pattern-matched.
Supported on revisions:  equality only.

Within the same lineage (same engine_token):
  ordered comparison of revision is consistent with mutation
  order. Earlier mutations have strictly smaller revision
  values.

Across different lineages (different engine_token):
  ordered comparison of revision has no defined meaning.
```

Identity is **not** a truth verdict, lifecycle status,
timestamp, cryptographic proof, hash of state, or transaction
identifier. M03's §10 forbidden-phrasings list continues to
apply to packets; the existence of this primitive does not
lift a PR51 packet out of UNBOUND on its own (see §6).

---

## §2 Revision advance semantics

```
A revision advance is one +1 step applied exactly once when a
public state-mutating method completes a logical state change.
```

### §2.1 Always-changing methods (6)

```
add_entity         success -> +1
add_observation    success -> +1
add_claim          success -> +1
add_evidence       success -> +1
add_relation       success -> +1
register_rule      success -> +1   (single advance covers both
                                     RuleDefinition registration
                                     and the initialized RuleStats
                                     slot)
```

Documented validation errors (e.g. `KeyError` on unknown
subject_id, `ValueError` on duplicate `register_rule`,
PR65-P01 `Claim.status` admission failures, PR67-P03 restore
admission failures elsewhere) leave the revision unchanged.

### §2.2 Gap registration (1)

```
add_gap
  dedup miss (new Gap created)                      -> +1
  dedup hit + current Claim references the Gap for
    the first time                                  -> +1
  dedup hit + current Claim already has
    gap_id in _claim_gap_refs[claim_id]             -> +0
  validation error                                  -> +0
```

The advance criterion is "did any tracked relation change",
not "was a new Gap created".

### §2.3 Resolution / contradiction (3)

```
resolve_gaps_for_evidence
  returned tuple non-empty                          -> +1
  returned tuple empty                              -> +0
  (advance happens once regardless of how many gaps
   were resolved in that call)

register_contradiction
  returned True                                     -> +1
  returned False (idempotent no-op)                 -> +0

register_contradiction_resolution
  returned True                                     -> +1
  returned False (already-resolved idempotent no-op) -> +0
  ValueError (evidence not in contradictions)       -> +0
```

### §2.4 Lifecycle transitions (6)

```
confirm_claim_if_ready
refute_claim_if_ready
dispute_claim_if_ready
resolve_disputed_claim_if_ready
refute_disputed_claim_if_ready
refute_disputed_claim_if_ready_by_freshness
                              returned True  -> +1
                              returned False -> +0
                              KeyError      -> +0
```

A successful lifecycle transition writes both a new `Claim`
status and a new `ClaimLifecycleEvent`; the advance is **+1**
not +N. The two updates form one logical mutation.

### §2.5 RuleStats update (1)

```
update_rule_stats
  next RuleStats != previous RuleStats              -> +1
  next RuleStats == previous RuleStats              -> +0
  documented error (unknown rule pair etc.)         -> +0
```

A no-op update (all deltas zero, all overrides equal to the
prior values) is a logical no-op even though the method body
replaces the slot value. The advance criterion is whether the
resulting `RuleStats` value differs from the prior one.

### §2.6 Hint evidence type set (3)

```
register_hint_evidence_types
  set was actually extended (a value not previously
    in the set was added)                            -> +1
  no new value was added                             -> +0
  TypeError validation failure                       -> +0

unregister_hint_evidence_types
  set was actually shrunk (a value previously in the
    set was removed)                                 -> +1
  no removal happened                                -> +0
  TypeError validation failure                       -> +0

clear_hint_evidence_types
  non-empty set cleared                              -> +1
  already empty                                      -> +0
```

The advance criterion is "did the stored set change", not "was
a method called". A generator input is materialized into the
validated set exactly once and the resulting set is compared
to the prior state at most once; the input is not iterated
again purely to compute the advance.

---

## §3 Failure and partial-mutation semantics

PR73-M04 does not introduce a transaction, rollback, or
exception-recovery framework. The advance is sequenced **after**
the existing validation order and after the state update
completes. Specifically:

```
- A revision advance never happens before a documented
  validation error. The validation error path returns the
  same exception type, with the same wording, and with no
  revision change.

- A revision advance never happens before the mutation is
  committed to the underlying private state. If a mutation
  would partially execute today, the present PR does not
  attempt to recover or roll back.
```

The directive's instruction "state revision은 먼저 올린 뒤
mutation을 시도하면 안 된다" is honored: in every method, the
advance call site is placed after the success-determining
state write.

---

## §4 Token allocation, lineage, and restore

### §4.1 Token allocation

```
Engine.__init__ allocates a fresh engine_token using only the
Python standard library (uuid.uuid4().hex by current
implementation).

The token format, length, and character set are
implementation details and are NOT part of the public
contract beyond being a non-empty str.
```

### §4.2 New Engine instance

```
After Engine.__init__:
  state_identity().engine_token  is non-empty str
  state_identity().revision      == 0
```

### §4.3 Lineage scope

```
The lineage is per-Engine-instance. Two Engine objects
constructed independently in the same process get distinct
tokens.

Re-running state_identity() in succession without an
intervening mutation returns equal values.
```

### §4.4 Restore semantics

```
to_snapshot()
  Identity is NOT persisted. Snapshot top-level keys remain
  exactly the 18 documented at §52.1 of PR66-P02.

from_snapshot(snapshot)
  The returned Engine starts a fresh lineage:
    engine_token is freshly allocated.
    revision == 0.

  source_engine.state_identity() != restored_engine.state_identity()
  even if the snapshot content is byte-equal to the source.
```

This is the conservative semantics. Snapshot content
equivalence does not imply runtime lineage identity.

### §4.5 Process restart

```
A new process produces a new lineage with a fresh token,
even when the same Engine code path is replayed.

PR73-M04 does NOT continue an Engine runtime lineage across
process restart or `from_snapshot()` restore. The
engine_token and revision counter are per-process / per-
instance, allocated fresh on `Engine()` and on
`Engine.from_snapshot(...)`.

M05 (PR74-M05, OC-B) may persist an operator decision record
that references an `EngineStateIdentity` value observed at
decision time. That persisted reference does NOT mean that a
restored Engine, or a new Engine instance, inherits or
resumes the same `engine_token` / revision lineage. The two
concepts are explicitly separated:

  persistent operator decision record
    ≠
  persistent Engine runtime lineage
```

---

## §5 Snapshot persistence non-claim

```
Snapshot schema_version              remains 2
Snapshot top-level keys              remains 18
No new top-level key is added.
No new value is included in any existing snapshot field.
```

The identity primitive is **runtime-only**. The snapshot
boundary continues to be a persistence-shape contract; it
does not gain a state-instance identity field.

This is intentional and aligns with M03 §14
(`snapshot schema validity != identity of the logical Engine
state represented by the snapshot`).

---

## §6 Atomicity and packet-binding non-claim

```
state_identity() returns the lineage-and-revision pair at the
moment of the call.

It does NOT thereby make any later read atomic.
It does NOT bind a PR51 context packet to a source state.
It does NOT make the packet's seven keys "all from one
  logical state".
```

A consumer that wants `CAPTURE_BOUND` per M03 §7 must still
satisfy M03 §8.1 / §8.2 / §8.3 (identity basis, packet records
its capture identity, all state-derived fields covered
atomically per M03 §6) and §15 (semantic requirements). The
identity primitive added here is a candidate building block;
it is not, on its own, an §8 satisfaction.

In particular, today's `build_engine_context_packet` (M03
§2.1) remains a sequence of 7 + N public reads with no
wrapping consistency boundary. A consumer that calls
`state_identity()` before and after `build_engine_context_packet`
and observes the same identity has **not** thereby proven the
packet is atomic; identity equality before/after a sequence of
read-only calls is necessary but not sufficient (M03 §6
forbids "Python execution is fast" / "the GIL prevents
interleaving" justifications).

---

## §7 Concurrency non-claim

```
PR73-M04 is not a thread-safety PR.

The revision counter is a plain Python int.
The token is set once at __init__ and otherwise never
  mutated.
The state_identity() reader does not lock.
```

The contract does not assert any concurrency property beyond
the single-thread sequential semantics that the rest of
`ragcore.Engine` already documents.

---

## §8 Relationship to M03 and M05

### §8.1 M03

M03 (`ENGINE_READ_CONSISTENCY_CONTRACT.md`) records that:

```
Engine state identity = named but NOT mechanized; future
                        implementation may realize as int
                        revision / opaque token / canonical
                        digest / immutable snapshot ref / other.
```

PR73-M04 implements one such mechanization. M03's §3 boundary
locks, §6 atomic-capture requirements, §7 two-axis vocabulary,
and §15 semantic-requirements list (§15.1 – §15.6) remain in
force unchanged.

M04 does **not** retroactively lift today's PR51 packet out of
`UNBOUND + UNKNOWN`. A separate PR (not auto-scheduled by M04)
would be required to wire `state_identity()` into the packet
builder under the M03 §6 conditions.

### §8.2 M05

OC-B / PR74-M05 (operator decision record + stale revalidation
policy) is the layer that would use M04's identity as the
mechanical comparison basis. M04 deliberately stops at the
fact-and-basis layer and does **not**:

```
- define a stale-rejection rule
- define a revalidation rule
- define what an operator decision record looks like
- define how M04 identity is to be persisted in any operator
  audit
```

M05 may record the captured `EngineStateIdentity` value as
part of an operator audit. M05 does NOT automatically make
that captured value comparable to a fresh Engine lineage
created after process restart or `from_snapshot()` restore.
The two concepts are kept distinct by M04:

```
persistent operator decision record
  ≠
persistent Engine runtime lineage
```

The 243차 implementation purposely emits a fresh lineage on
restore (§4.4) so that an M05-style consumer cannot mistake
snapshot content equivalence for state-instance identity.

### §8.3 M02

M02's four-layer model, §11 exact-content review binding,
§12.1 state-mutating / read-only / serialization
classification, §14.1 / §14.2 / §14.3 separation principles,
and §17 A2 UNDEFINED are unchanged. The M04 addition shifts
the post-M04 public surface as follows:

```
state-mutating public methods       20  (unchanged set)
read-only public methods            19  (was 18; +state_identity)
serialization boundary               2  (unchanged)
total                               41
```

M02 §12.1's historical baseline of 40 methods on `main`
`896e01e` is a snapshot in time; documents that cite that
count must note "post-M04 on main <new SHA>: 41".

`state_identity` is a **read-only** method. It is **not** an
M02 mutation candidate target, and the contract explicitly
forbids any future candidate from targeting `state_identity`
as a mutation.

---

## §9 Non-goals

```
- atomic packet capture
- PR51 packet shape change
- packet identity field
- capture-before/after wrapper API
- lock / transaction / snapshot isolation
- retry loop
- stale detector
- stale rejection policy
- operator decision record persistence
- automatic revalidation
- automatic mutation
- automatic dispatch
- snapshot digest
- canonical JSON / canonicalization rule
- hash function / signing scheme
- domain-specific vocabulary
- network / LLM call
```

---

## §10 Closing position

```
PR73-M04 adds a per-Engine opaque token and a completed-mutation
revision, surfaced through a single read-only public method
state_identity() and one exported frozen value type
EngineStateIdentity.

It advances exactly once per logical state change across the 20
state-mutating public methods, does not advance on documented
no-ops or documented failures, does not appear in the snapshot,
and starts a fresh lineage on Engine() / from_snapshot().

PR73-M04 does NOT make today's PR51 packet state-bound, does
NOT make sequential reads atomic, and does NOT implement any
stale-decision policy.
```
