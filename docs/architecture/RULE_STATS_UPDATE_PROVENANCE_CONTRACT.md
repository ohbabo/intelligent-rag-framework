# RuleStats Update Provenance Contract

PR78-M09 — RuleStats Update Provenance Contract
type:    docs-only architecture contract
status:  normative
date:    2026-06-25
baseline main: 31e0210998374815c90dc9671069034bf6e10d1b

self-SHA: intentionally omitted (this contract's own commit SHA is
not known at authoring time and is recorded only in the completion
report)

This contract closes the M01 discontinuity **OC-G — RuleStats update
provenance** at the conceptual layer. It defines what must remain
inspectable around an explicit `RuleStats` update, and which authority
boundaries must not collapse. It does **not** change how any
`RuleStats` value is computed or evaluated, does not add a Python type
or Engine capability, and does not connect `update_rule_stats` to any
automatic operational flow. The 276차 commit that introduces this
document is docs-only.

---

## Core proposition

> A RuleStats update is an explicit, separately reviewed Engine
> mutation whose numeric update intent and provenance basis remain
> distinct, inspectable facts.
>
> Provenance explains the basis and execution history of an update.
> It does not prove that a rule is correct, mature, trustworthy, or
> high quality.

In Korean terms: RuleStats update provenance is the boundary that lets
a consumer answer *"why did this aggregate value change the way it
did?"* The record itself is not a rule-quality verdict, a truth
verdict, a correctness certification, or an automatic grant of
authority.

The eight questions this contract scopes:

```
who requested the update
why the update was requested
which source observations it was based on
how each delta was derived
what the precision inputs were based on
under which consumer policy it was made
against which Engine state it was reviewed / revalidated / called
what the RuleStats and state identity were immediately before and
  after the actual call
```

This step locks the meaning of those questions. It does not implement
them as Python types or Engine features.

---

## §0 Scope lock

### §0.1 In scope (conceptual definitions only)

```
- one update_rule_stats update intent
- the consumer-side provenance basis of that update
- the exact reviewed arguments
- the joint (rule_id, rule_version) identity
- a caller identity reference
- an update reason
- source observation references
- delta derivation basis
- precision input basis
- policy reference
- decision / revalidation references
- pre-call and post-call RuleStats reads
- pre-call and post-call EngineStateIdentity
- a call receipt and an actual-effect classification
```

### §0.2 Out of scope (not defined, not implemented here)

```
- any change to the RuleStats calculation
- any change to the effective-confidence modifier
- any change to maturity / precision multipliers
- promoting RuleStats to a rule-quality verdict
- automatic precision calculation
- automatic true / false determination
- automatic stats update from Claim lifecycle outcomes
- automatic stats update from Evidence / Gap / contradiction
- automatic stats update from proposal acceptance
- automatic update following register_rule
- any new database / UI / scheduler / worker / queue
- any cryptographic signature
- any identity provider or authentication system
- any wall-clock ordering contract
- any snapshot schema change
- any change to existing RuleStats fields
- any change to the update_rule_stats signature
- any new public Engine method
- any new ragcore type or export
```

276차 implements none of the runtime items above. They are named only
to fix the boundary of what M09 is and is not.

---

## §1 Investigation origin — OC-G

M01 (`examples/operation/minimal_operational_scaffold.py`,
`_rule_stats_provenance_diagnosis()`) recorded six provenance gaps,
each presently `"no"`:

```
caller_identity_recorded                 no
update_reason_recorded                   no
source_observation_reference_recorded    no
delta_provenance_recorded                no
precision_input_basis_recorded           no
policy_reference_recorded                no
```

The M01 OC-G entry labels this discontinuity "RuleStats update
provenance" and points its `future_contract` field at OC-G. M09
defines the meaning and boundary of these six questions.

The M01 diagnosis dict is itself a local illustrative scaffold record.
This contract does **not** promote that dict to a canonical schema,
and does not require the six keys to appear verbatim in any future
provenance record.

---

## §2 Existing runtime baseline

Recorded as fact, not as defect. Observed on main
`31e0210` (`ragcore/types.py`, `ragcore/engine.py`):

```
RuleStats fields (frozen dataclass, 7):
  rule_id
  rule_version
  firing_count
  confirmed_true_count
  confirmed_false_count
  observed_precision           (ScoreValue | None)
  false_positive_rate          (ScoreValue | None)

register_rule(definition):
  registers a RuleDefinition
  creates an initial zero RuleStats slot for the same
    (rule_id, rule_version) pair
  re-registering the same pair raises ValueError
  advances the Engine state revision

update_rule_stats(rule_id, rule_version, *,
                  firing_delta=0, true_delta=0, false_delta=0,
                  observed_precision=None, false_positive_rate=None)
                  -> None:
  reads the current stored RuleStats for the pair
  builds a NEW frozen RuleStats with the deltas applied
  observed_precision / false_positive_rate of None mean
    "keep the existing value" (NOT clear / NOT nullify)
  replaces the stored instance
  advances the Engine state revision ONLY when the new RuleStats
    value differs from the current one (value equality on a frozen
    dataclass)

get_rule_stats(rule_id, rule_version) -> RuleStats:
  returns the current aggregate RuleStats for the pair
  raises KeyError on an unknown pair

snapshot:
  serializes the current aggregate RuleStats state only
  carries NO per-update provenance history
```

The current behavior is not exaggerated into a flaw. M09 is the
contract that keeps the existing aggregate state and the new
provenance concept distinct.

---

## §3 Core distinctions (load-bearing inequality locks)

```
RuleDefinition                 != RuleStats
RuleStats aggregate            != update provenance
register_rule initialization   != RuleStats update event
update intent                  != reviewed update
reviewed update request        != Engine invocation
Engine invocation              != value change
successful no-op call          != applied value change
source observation             != ground truth
confirmed_true_count           != globally proven truth count
confirmed_false_count          != globally proven falsehood count
observed_precision             != rule quality verdict
false_positive_rate            != automatic rejection verdict
caller identity reference      != authenticated identity proof
policy reference               != semantic policy proof
provenance completeness        != update correctness
operator approval              != Engine truth
RuleStats update               != automatic confidence verdict
```

---

## §4 Conceptual layers

Six layers, kept distinct:

```
Layer 1  consumer-owned source observations / outcome records
Layer 2  RuleStatsUpdateCandidate
         exact rule pair, exact proposed arguments,
         exact derivation and policy basis
Layer 3  operator decision record
         exact candidate review + decision-state identity
Layer 4  revalidated ReviewedMutationRequest
         passing Stage 5.5 and Stage 6
Layer 5  direct caller-written invocation
         engine.update_rule_stats(...)
Layer 6  call receipt + provenance record
         pre/post RuleStats, pre/post state identity,
         actual effect classification
```

Every name above is a **conceptual term** in 276차. This contract does
not create any of the following for them:

```
Python class      dataclass        TypedDict        Protocol
JSON Schema       Pydantic model   ragcore symbol   Engine-owned
                                                    audit collection
```

---

## §5 RuleStatsUpdateCandidate — minimum conceptual content

```
candidate identity
rule_id
rule_version
exact update arguments
update intent per field
caller identity reference
update reason
source observation references
delta derivation basis
precision input basis
policy reference
expected effect
explicit non-effects
candidate materialization state identity
```

`rule_id` alone is insufficient. Rule identity is the joint pair:

```
Rule identity = (rule_id, rule_version)
```

Provenance for one version must not be merged into, or substituted
for, the provenance of another version — consistent with the Engine's
own per-`(rule_id, rule_version)` slotting (§2).

---

## §6 Exact update intent

The three deltas each carry a distinct meaning:

```
firing_delta
true_delta
false_delta
```

This contract introduces no new arithmetic validation of these values;
it leaves the Engine's current admission semantics unchanged.
Provenance must, however, record for each delta:

```
the exact numeric value
which source observations contributed
how the value was derived
which policy authorized that derivation
```

The following automatic inferences are forbidden:

```
Claim confirmed  -> automatic true_delta increment
Claim refuted    -> automatic false_delta increment
Evidence added   -> automatic firing_delta increment
proposal accept  -> automatic precision calculation
```

If such a relationship is desired, the consumer decides it under an
explicit policy, records the basis, and routes it through a separate
review.

---

## §7 Optional score intent

In the current Engine API, `observed_precision=None` and
`false_positive_rate=None` mean **keep the existing value**, not delete
it (§2). The consumer-side candidate makes this semantically explicit:

```
observed_precision action:
  KEEP
  SET(ScoreValue)

false_positive_rate action:
  KEEP
  SET(ScoreValue)
```

M09 introduces no `CLEAR` action. It also distinguishes:

```
KEEP   !=   SET(ScoreValue(0.0))
```

A precision input basis (§12) is required only when the corresponding
action is `SET`. When the action is `KEEP`, the candidate states
explicitly that the existing value is retained.

---

## §8 Caller identity reference

The caller identity is a consumer-owned opaque reference.

Required meaning:

```
a reference that distinguishes who created or submitted the update
candidate
```

It is NOT:

```
an authentication proof
an authorization token
a cryptographic identity
a framework-owned user account
a value restricted to a human person
```

A caller may be a person, a service, a batch process, or a consumer
component; the concrete taxonomy is not fixed here.

---

## §9 Update reason

A single free-text string alone does not complete provenance. The
update reason must at minimum explain:

```
why this rule pair is being updated
why these fields were selected
why these delta or score values were selected
what is NOT changed by this update
```

The reason is a basis for judgment, not a proof of truth.

---

## §10 Source observation references

A source observation reference is a consumer-side opaque reference. It
may point at:

```
an external outcome record
a manual review result
an evaluation batch result
a consumer inspection record
another consumer-owned observation artifact
```

It does not define a canonical domain schema. The following are
forbidden:

```
source observation reference   -> automatic promotion to ragcore.Evidence
external metric                 -> direct identity with observed_precision
tool output                     -> direct identity with confirmed_true_count
                                   / confirmed_false_count
```

If any translation or aggregation occurred, its basis is recorded.

---

## §11 Delta provenance

The provenance of each delta separates:

```
source records
selection rule
aggregation rule
dedup rule
counting window or observation-set boundary
excluded records
consumer policy reference
```

276차 standardizes no concrete algorithm. The point is to preserve not
only the number but the **basis on which the number was produced**, as
a separate fact.

---

## §12 Precision input basis

When `observed_precision` or `false_positive_rate` is `SET`, the
provenance records:

```
the source observation set
the numerator meaning
the denominator meaning
the inclusion / exclusion rule
the aggregation or translation method
the consumer policy reference
```

M09 does not define these values as ground truth, probability, or rule
certification. It preserves the existing conservative reading:

```
Observed precision is optional evidence for rule maturity,
not ground truth.
```

---

## §13 Policy reference

The policy reference is a consumer-side reference identifying which
policy (or policy version) governed:

```
observation selection
delta derivation
precision derivation
update approval
```

It is NOT:

```
a module hash
a source-code hash
a snapshot schema_version
an Engine revision
an automatic semantic-identity proof
```

Its representation is consumer-owned; 276차 fixes no format.

---

## §14 Review and state binding

Every RuleStats update follows the M02 / M05 / M08 authority sequence:

```
candidate materialization
-> exact operator review
-> decision record
-> Stage 5.5 revalidation
-> ReviewedMutationRequest materialization
-> Stage 6 revalidation
-> direct update_rule_stats call
-> receipt
```

A decision applies to the exact candidate only. A new review is
required if any of the following changes:

```
rule_id
rule_version
any delta value
the score action or score value
a source observation reference
the delta derivation basis
the precision input basis
the caller identity reference
the update reason
the policy reference
the expected effect
```

If, at Stage 5.5 or Stage 6, the decision-state identity differs from
the current Engine identity, the invocation is suppressed.

---

## §15 Direct invocation boundary

The actual call is written directly in the caller's source:

```python
engine.update_rule_stats(
    rule_id,
    rule_version,
    firing_delta=...,
    true_delta=...,
    false_delta=...,
    observed_precision=...,
    false_positive_rate=...,
)
```

Forbidden:

```
getattr(engine, method_name)
a dispatch table
request.execute()
engine.apply_request()
eval
exec
a callable-bearing request
storing a method object
using a target_method string as an execution token
```

The target name on a candidate or request is inspection metadata only.

---

## §16 Before / after reads and receipt

The before/after read requirement below applies to a **successful
invocation receipt** — a receipt for a direct `update_rule_stats`
call performed against a known `(rule_id, rule_version)` pair, where
the pre-call read succeeds, the call completes, and the post-call read
succeeds. A rejected / failed-attempt receipt is governed separately
by §17 and is **not** required to carry a RuleStats before/after.

### §16.1 Successful invocation receipt

A successful-invocation provenance record must be bound to at least
these actual public reads:

```
pre-call:
  engine.state_identity()
  engine.get_rule_stats(rule_id, rule_version)

post-call:
  engine.state_identity()
  engine.get_rule_stats(rule_id, rule_version)
```

Minimum successful-receipt meaning:

```
the reviewed exact arguments
the decision reference
the identity before the call
the identity after the call
the RuleStats before
the RuleStats after
the actual effect classification (VALUE_CHANGED or NO_VALUE_CHANGE)
```

### §16.2 Rejected / failed-attempt receipt

A rejected / failed-attempt receipt records only the facts that are
actually available. For an unknown `(rule_id, rule_version)` pair the
pre-call `engine.get_rule_stats(rule_id, rule_version)` itself raises
(it asserts the pair exists, per §2), so there is no RuleStats before
to read. Such a receipt therefore:

```
- does NOT require a RuleStats before or a RuleStats after
- does NOT fabricate a RuleStats before/after for an absent pair
- records the rejection / failure cause
- may record a pre-attempt state_identity() if one was read before
  the attempt
- is NOT a successful update provenance (see §17 REJECTED)
- is NOT equated with NO_VALUE_CHANGE
```

Provenance — successful or failed-attempt — must not be constructed by
reading private Engine state.

---

## §17 Actual effect classification

Three outcomes are distinguished:

```
VALUE_CHANGED
  the call succeeded
  RuleStats before != after
  the Engine revision advanced

NO_VALUE_CHANGE
  the call succeeded
  RuleStats before == after
  the Engine revision is unchanged
  an invocation occurred but is NOT called an applied value change

REJECTED
  the Engine call was refused by an exception
  it is NOT called a successful update provenance
  it may be recorded only as a separate failed-attempt receipt
```

The fact that `update_rule_stats()` returns `None` does not by itself
determine the effect. The actual before/after read and the state
identity determine it (consistent with §2: the Engine advances the
revision only when the value actually changes).

---

## §18 register_rule separation

`register_rule()` performs:

```
RuleDefinition registration
creation of an initial zero RuleStats slot
```

This initial creation is **not** an `update_rule_stats` provenance
event:

```
register_rule review          !=  update_rule_stats review
RuleStats initialization      !=  stats update based on observations
```

M09 does not define RuleDefinition creation provenance. (That both
operations advance the Engine revision per §2 does not make them the
same event class.)

---

## §19 Snapshot boundary

The current snapshot preserves aggregate RuleStats state only. 276차
does NOT:

```
add provenance history to the snapshot
increment schema_version
add a top-level key
add a RuleStats field
change restore rules
```

It locks only the fact that aggregate state and event provenance are
separate. Any future provenance persistence is a separate scope.

---

## §20 Non-authority locks

```
provenance present       !=  update correct
operator approval         !=  rule correct
VALUE_CHANGED            !=  rule quality improved
NO_VALUE_CHANGE          !=  review unnecessary
observed_precision        !=  probability of truth
RuleStats modifier        !=  verdict
source observation        !=  ragcore Evidence
RuleStats update          !=  Claim lifecycle transition
RuleStats update          !=  automatic effective-confidence recommendation
```

---

## §21 M08 relation

M08's reported field:

```
rule_stats_provenance_status = NOT_ENTERED_M09
```

is not retroactively changed to a value such as `PROVENANCE_COMPLETE`.
M08 is a historical reference operation that closed before M09. This
M09 contract does not modify M08's existing example, report shape, or
test surface.

---

## §22 OC-G closure statement

```
M09 closes OC-G at the conceptual provenance-contract layer.

It defines what must remain inspectable around an explicit
RuleStats update and which authority boundaries must not collapse.

276차 does not implement a provenance record, change the Engine,
or connect update_rule_stats to an automatic operational flow.
```

The provenance record type, an Engine-owned store, snapshot
persistence, and any API are out of scope until this contract is
approved and a later step is separately directed.

### §22.1 M09 overall status

Closing OC-G at the conceptual contract layer is not the same as
closing M09. As of this contract, M09 as a whole remains STARTED /
OPEN. 276차 is the contract-only step; the following are NOT yet
created or implemented:

```
runtime provenance implementation
tests
dev record
```

Consequently this document does NOT claim that the Engine records
provenance, does NOT claim OC-G operational completion, does NOT
claim M09 CLOSED, and does NOT claim M-series completion.
