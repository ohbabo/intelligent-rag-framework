# PR76-M07 — Effective Confidence Calculation Trace

Development record for the runtime feature landed by PR76-M07
(branch `feat/effective-confidence-calculation-trace`).

```
base:            main 9f576a5 (PR75-M06 — Downstream Result
                                Re-entry Contract)
branch:          feat/effective-confidence-calculation-trace
255차 commit:    058756e   docs(contract): define effective
                            confidence calculation trace
256차 commit:    ffa4345   test(core): lock effective confidence
                            trace invariants
257차 commit:    c29a6c8   feat(engine): add effective confidence
                            calculation trace
258차 commit:    (this record, docs/dev)
type:            framework-level runtime change, additive only;
                  no judgment-semantics delta, no formula
                  delta, no snapshot schema change, no PR51
                  packet shape change
status:          normative
```

PR76-M07 is the first M-series PR that adds a new public
runtime surface since PR73-M04. It introduces one frozen
public value type (`EffectiveConfidenceTrace`), one read-only
public Engine method
(`compute_effective_confidence_with_trace`), one private
calculation core (`_compute_effective_confidence_core`), and
one module-private policy-identity constant
(`_EFFECTIVE_CONFIDENCE_POLICY_ID`). The existing
`compute_effective_confidence` method retains its signature,
return type, exception type, and byte-identical return value;
its body is reduced to a single delegating expression so the
formula has exactly one site.

---

## §1 Investigation origin

M01 (PR70-M01) Lane B surfaced the
`effective_confidence_trace_diagnosis` discontinuity as `OC-D`:

```
B (engine_read_and_proposal):
  effective_confidence_trace_diagnosis  ->  OC-D
```

Today's Engine computes a single `ScoreValue` via
`compute_effective_confidence(claim_id)`. The composition uses
six private modifier helpers, but the modifier values, the
composition policy identity, and the Engine state identity at
calculation time are not surfaced through any public API. OC-D
is the conceptual discontinuity between **the calculation
result** and **the explanation of how that result was
produced**.

PR74-M05 closed OC-B at the operator-decision-record /
revalidation layer. PR75-M06 closed OC-E at the downstream
result re-entry layer. PR76-M07 picks up OC-D and closes it by
adding a read-only typed trace that exposes the inputs, the
six modifier components, the policy identity, and the source
Engine state identity of the same calculation.

PR76-M07 does NOT change the formula. M07 surfaces what is
already computed.

---

## §2 Base state

```
main at PR76-M07 start:    9f576a5b072f4d194083d9b4c20d997d78c4b787
tests:                      1517 passing
Engine public methods:      41 (post-M04)
Engine private methods:     19 (post-M04)
state-mutating public:      20 (set unchanged from M02 §12.1)
read-only public:           19 (includes state_identity)
serialization boundary:      2 (to_snapshot, from_snapshot)
ragcore.__all__:            49 (includes EngineStateIdentity)
snapshot schema_version:     2
snapshot top-level keys:    18
PR51 packet keys:            7
```

PR51 packet keys (M03-locked names):

```
claim
effective_confidence
supporting_evidence
contradictions
active_contradictions
unresolved_gaps
lifecycle_history
```

M-series state at PR76-M07 start:

```
P-series   CLOSED
PR70-M01   CLOSED
PR71-M02   CLOSED
PR72-M03   CLOSED
PR73-M04   CLOSED
PR74-M05   CLOSED
PR75-M06   CLOSED
PR76-M07   IN PROGRESS (this PR, Draft)
PR77-M08   NOT STARTED
PR78-M09   NOT STARTED
```

---

## §3 Why M07 is a runtime feature (not docs-only)

M05 and M06 were docs-only because the obligations they fixed
sat on the **consumer-side** of the framework boundary (record
shape, reuse policy, re-entry chain). M07 is different: the
obligation it fixes lives **on the Engine side** of that
boundary. The calculation already happens inside the Engine;
the question OC-D asks is whether an external caller can
observe the calculation's components, policy identity, and
state basis through a public read-only surface.

A docs-only resolution would have either:

```
- failed to expose the modifier values (callers cannot use
  PR51 packet alone to identify which modifier drove a
  particular score)
- forced callers to reach into private helpers (violating
  M02 / PR32 read-surface locks)
- conflated the result with the calculation policy identity
  (every future modifier rework would silently invalidate
  external interpretations)
```

The contract therefore introduces:

```
- a frozen typed return value (EffectiveConfidenceTrace)
- a read-only public method that produces it
- a single private calculation core that both APIs delegate
  to (so the formula cannot drift between the legacy API
  and the trace API)
- a module-private semantic policy identity that callers can
  observe through the trace
```

and NOTHING else. The formula, modifier helpers, snapshot
schema, PR51 packet shape, and lifecycle conditions are all
preserved verbatim.

---

## §4 OC-D scope

M07 owns:

```
- public EffectiveConfidenceTrace value type
- public Engine.compute_effective_confidence_with_trace
  method
- private _compute_effective_confidence_core single-site
  calculation
- module-private _EFFECTIVE_CONFIDENCE_POLICY_ID constant
- equality between the legacy and trace APIs
- modifier breakdown semantics (mirror of existing helpers)
- failure semantics (KeyError, unchanged)
- read-only / no-revision-advance classification (M04 §1.2
  for state_identity-style read-only methods; the §2 advance
  discipline covers only the 20 state-mutating methods)
- relationship with M03 packet boundary (preserved)
- relationship with M04 EngineStateIdentity primitive (reuse)
- relationship with PR32 consumer-report surface (separate)
- relationship with PR51 packet (unchanged)
- relationship with the snapshot (excluded; not serialized)
```

M07 does NOT own:

```
- a complete domain-neutral end-to-end reference operation
  (M08 — PR77 territory)
- RuleStats provenance (M09 — PR78 territory)
- CAPTURE_BOUND packet binding (OC-C closure follow-up)
- CURRENTLY_MATCHED comparison helper
- mechanical packet STALE detector
- probability conversion
- verdict / lifecycle recommendation
- automatic revalidation
- automatic mutation
- network / LLM / adapter / executor
```

---

## §5 4-commit cycle

```
255차  058756e  docs(contract): define effective confidence
                  calculation trace
                  (new contract §0~§20 + M03 §21 + M04 §12
                   addenda; runtime/tests untouched;
                   1517 passing)

256차  ffa4345  test(core): lock effective confidence trace
                  invariants
                  (new tests/test_effective_confidence_trace.py
                   with 61 test methods across 13 classes;
                   7 surface-lock test files bumped 41→42 / 19→20
                   / 49→50; 1503 passed + 75 expected failures =
                   1578 total; zero unrelated regression)

257차  c29a6c8  feat(engine): add effective confidence
                  calculation trace
                  (ragcore/types.py + ragcore/engine.py +
                   ragcore/__init__.py; one test calibrated
                   to match contract §9.5 reading;
                   1578 passing)

258차  (this)   docs(dev): record PR76-M07 effective confidence
                  trace
```

The 255차 / 256차 / 257차 commits are NOT amended by 258차.

---

## §6 Public surface delta

### §6.1 New public value type

```
@dataclass(frozen=True)
class EffectiveConfidenceTrace:
    claim_id: int
    source_state_identity: EngineStateIdentity
    calculation_policy_id: str
    base_confidence: ScoreValue
    status_modifier: float
    freshness_modifier: float
    gap_modifier: float
    count_modifier: float
    rule_stats_modifier: float
    evidence_type_modifier: float
    effective_confidence: ScoreValue
```

Field order is part of the contract (§4.1). Forbidden fields
include `probability`, `verdict`, `risk_label`,
`lifecycle_recommendation`, `wall_clock_timestamp`,
`packet_identity`, `snapshot_digest`, etc. — see contract §4.3.

### §6.2 New public Engine method

```
def compute_effective_confidence_with_trace(
    self, claim_id: int,
) -> EffectiveConfidenceTrace
```

Read-only. KeyError on unknown `claim_id`. Deterministic for
unchanged Engine state.

### §6.3 Existing public method (unchanged surface)

```
def compute_effective_confidence(
    self, claim_id: int,
) -> ScoreValue
```

Signature, return type, exception type, and docstring all
preserved. Body reduced to one delegating expression returning
`core.effective_confidence` (§6.4).

### §6.4 New private calculation core

```
def _compute_effective_confidence_core(
    self, claim_id: int,
) -> EffectiveConfidenceTrace
```

Single multiplication site. Calls each of the six modifier
helpers exactly once into local variables. Captures
`self.state_identity()` at construction. Returns a frozen
`EffectiveConfidenceTrace`.

### §6.5 Module-private policy constant

```
_EFFECTIVE_CONFIDENCE_POLICY_ID = "ragcore.effective-confidence.v1"
```

NOT re-exported in `ragcore.__all__`. Observable only via
`EffectiveConfidenceTrace.calculation_policy_id`.

### §6.6 Surface counts

```
Engine public methods:    41 -> 42
                          (+compute_effective_confidence_with_trace)
Engine private methods:   19 -> 20
                          (+_compute_effective_confidence_core)
state-mutating public:    20 -> 20  (unchanged set)
read-only public:         19 -> 20
                          (+compute_effective_confidence_with_trace)
serialization boundary:    2 ->  2  (unchanged set)
ragcore.__all__:          49 -> 50
                          (+EffectiveConfidenceTrace)
```

---

## §7 Single calculation core

The directive §4 forbids two different multiplication sites
for the same formula. M07 enforces this by:

```
- introducing _compute_effective_confidence_core as the only
  site that multiplies base × the six modifier floats
- reducing compute_effective_confidence's body to a single
  delegating expression: return self._compute_effective_
  confidence_core(claim_id).effective_confidence
- making compute_effective_confidence_with_trace a direct
  pass-through to the core
```

Equality invariant (enforced by
`TestSingleCalculationSource`):

```
engine.compute_effective_confidence(claim_id)
  == engine.compute_effective_confidence_with_trace(
       claim_id
     ).effective_confidence
```

The trace's `effective_confidence` is constructed from the
same `ScoreValue` that the legacy API returns, by construction
in the core method.

---

## §8 Modifier-helper preservation

M07 does NOT modify the body of any of:

```
_status_modifier_for_claim
_freshness_modifier_for_claim
_gap_modifier_for_claim
_count_modifier_for_claim
_rule_stats_modifier_for_claim
_evidence_type_modifier_for_claim
```

The trace's six modifier float fields equal the corresponding
helper return values for the same `claim_id`. Tests
(`TestStatusModifier` / `TestFreshnessModifier` /
`TestGapModifier` / `TestCountModifier` /
`TestRuleStatsModifier` / `TestEvidenceTypeModifier`) lock the
existing tier semantics:

```
status:     candidate/confirmed 1.0, disputed 0.5, refuted 0.0
freshness:  no contradiction 1.0; one+ active uses most-recent
            strength penalty; resolved excluded
gap:        0/1/2/3+ unresolved -> 1.0/0.9/0.8/0.7
count:      0/1 active -> 1.0; 2+ -> avg-strength penalty;
            resolved excluded
rule stats: sentinel rule 0 -> 1.0; lookup miss -> 1.0;
            observed_precision None -> precision_modifier 1.0
            (maturity floor still applies);
            false_positive_rate ignored
evidence:   empty hint set -> 1.0; no direct -> 1.0;
            all direct hint -> 0.9; mixed -> 1.0;
            contradiction evidence excluded
```

---

## §9 Calculation policy identity

`_EFFECTIVE_CONFIDENCE_POLICY_ID = "ragcore.effective-confidence.v1"`

Bump conditions (contract §7.4) — a future PR MUST bump this
when ANY of:

```
- modifier component added / removed
- modifier composition rule (multiplication, ordering) changed
- modifier value table or tier changed
- modifier input-set semantics changed
- fallback / sentinel semantics changed
```

Non-bump conditions (§7.5) — the id MUST NOT be bumped for:

```
- documentation rewording
- new tests
- internal variable renaming
- performance-only refactor that preserves observed semantics
- equivalent-meaning code reorganization
```

Forbidden equivalences (§7.6):

```
calculation_policy_id
  != snapshot schema_version (or its stringification)
  != ragcore package version
  != module hash
  != commit SHA
  != EngineStateIdentity.engine_token
  != EngineStateIdentity.revision
```

`TestPolicyIdentity` locks the exact string, the type
(`str`), stability across reads, and the negative test against
schema_version stringification.

---

## §10 Source Engine state identity

`trace.source_state_identity = self.state_identity()` at
construction.

```
- captured via a read-only state_identity() call (M04 §1.2
  public method; not in the §2 state-mutating set);
  revision unchanged.
- value-equality is the only supported comparison.
- NOT a packet capture identity, NOT CAPTURE_BOUND /
  CURRENTLY_MATCHED / STALE, NOT atomic capture, NOT a
  snapshot digest, NOT cross-process continuity.
- After Engine.from_snapshot(...), the prior trace's
  source_state_identity cannot be value-equal to the
  restored Engine's state_identity() (fresh lineage per
  M04 §4.4).
```

`TestSourceStateIdentity` covers:

```
- trace.source_state_identity == engine.state_identity()
- type is EngineStateIdentity
- read leaves revision unchanged
- mutation produces a different subsequent
  trace.source_state_identity.revision
- from_snapshot produces a fresh lineage token
```

---

## §11 Read-only and failure semantics

```
compute_effective_confidence_with_trace
  - does not advance Engine state revision (M04 §2 advance
    discipline covers only the 20 state-mutating public
    methods; read-only methods such as state_identity()
    under §1.2 and the new
    compute_effective_confidence_with_trace are explicitly
    out of that set)
  - does not modify snapshot-visible state
  - does not introduce any new exception type
  - unknown claim_id -> KeyError (same surface as the
    existing API)
```

`TestPublicMethod` enforces revision-unchanged and
snapshot-unchanged invariants per call.

---

## §12 Boundary preservation

### §12.1 PR51 packet

`examples/inspector/engine_inspector.py` is NOT modified by
M07. The packet's 7 keys are preserved exactly, in the same
order. The packet does NOT gain any of:

```
effective_confidence_trace
calculation_policy_id
source_state_identity
modifier_breakdown
```

PR51 packets remain `UNBOUND + UNKNOWN` (M03 §7.1 / §7.2; M06
§10). `TestPreservedBoundaries.test_pr51_packet_still_7_keys`
locks this with both length and forbidden-key checks against
the actual builder output.

### §12.2 Snapshot

`snapshot_schema_version` stays at 2. The 18 top-level keys
are unchanged. The trace is NOT serialized into any snapshot
field. M07 does NOT introduce any of:

```
effective_confidence_trace
trace_log
calculation_policy_id
last_traced_at
```

### §12.3 PR32 consumer report surface

The consumer-assembled PR32 report dict is NOT extended. M07
adds a separate typed surface (`EffectiveConfidenceTrace`
value), not a report mutation. No new `Engine.claim_report(...)`
/ `Engine.effective_confidence_report(...)` / dict-shaped
helper is introduced.

### §12.4 M03 / M04 contracts

M03 `ENGINE_READ_CONSISTENCY_CONTRACT.md` gains §21 Post-M07
addendum. M04 `ENGINE_STATE_IDENTITY_PRIMITIVE_CONTRACT.md`
gains §12 Post-M07 addendum. Historical body of both
contracts is preserved verbatim; addenda are append-only.

### §12.5 M01 / M05 / M06 contracts and the M01 scaffold

`examples/operation/minimal_operational_scaffold.py` and
`tests/test_minimal_operational_scaffold.py` are NOT modified.
M05 / M06 contracts and their dev records are NOT modified
(M07 does not overlap them).

---

## §13 Files Changed

### §13.1 New (3)

```
docs/architecture/EFFECTIVE_CONFIDENCE_CALCULATION_TRACE_CONTRACT.md
  255차, +1029 lines (§0~§20)
tests/test_effective_confidence_trace.py
  256차, +703 lines (61 test methods across 13 classes;
                      259차 audit-closure later appends an
                      additional ~22 test methods across 7
                      classes — see §20)
docs/dev/PR_076_EFFECTIVE_CONFIDENCE_CALCULATION_TRACE.md
  258차, this file
```

### §13.2 Modified runtime (3)

```
ragcore/types.py
  +EffectiveConfidenceTrace dataclass

ragcore/__init__.py
  +EffectiveConfidenceTrace import
  +EffectiveConfidenceTrace in __all__ (under Core
   dataclasses; size 49 -> 50)
  Public API surface comment updated to "50 symbols" +
  PR76-M07 reference

ragcore/engine.py
  +EffectiveConfidenceTrace import
  +_EFFECTIVE_CONFIDENCE_POLICY_ID module constant
  +_compute_effective_confidence_core private method
  +compute_effective_confidence_with_trace public method
  compute_effective_confidence body reduced to a single
  delegating expression returning core.effective_confidence
```

### §13.3 Normative addenda (2)

```
docs/architecture/ENGINE_READ_CONSISTENCY_CONTRACT.md
  + §21 Post-M07 addendum
  (trace.source_state_identity != packet capture identity;
   PR51 remains UNBOUND + UNKNOWN; M03 §7 forbidden two-axis
   combinations preserved; M07 does NOT introduce
   CAPTURE_BOUND / CURRENTLY_MATCHED / STALE; trace NOT
   persisted; trace NOT in PR51 packet)

docs/architecture/ENGINE_STATE_IDENTITY_PRIMITIVE_CONTRACT.md
  + §12 Post-M07 addendum
  (trace reuses EngineStateIdentity shape verbatim; captured
   via read-only state_identity(); revision unchanged; new
   method added to read-only set as the 20th read-only
   method; value-equality only; snapshot exclusion preserved;
   from_snapshot -> fresh lineage)
```

### §13.4 Modified surface-lock tests (8)

```
tests/test_engine_method_surface_freeze.py
  _LOCKED_PUBLIC_METHODS adds
    compute_effective_confidence_with_trace;
  method count 41 -> 42; __all__ size 49 -> 50

tests/test_engine_method_call_playbook_usage.py
  public method count 41 -> 42; __all__ size 49 -> 50

tests/test_engine_ai_readable_usage_recipe.py
  _PR30_BASELINE_PUBLIC_SYMBOLS adds EffectiveConfidenceTrace

tests/test_engine_report_surface.py
  _PR30_BASELINE_PUBLIC_SYMBOLS adds EffectiveConfidenceTrace

tests/test_external_adapter_simulation.py
  public method count 41 -> 42; __all__ size 49 -> 50

tests/test_external_engine_inspector.py
  __all__ size 49 -> 50

tests/test_snapshot_restore_integrity.py
  public 41 -> 42; private 19 -> 20; __all__ 49 -> 50

tests/test_engine_state_identity.py
  public 41 -> 42; private 19 -> 20; __all__ 49 -> 50
```

No PR32 frozen report key set is changed. No M01 scaffold
test is modified. No other test file's expectations are
modified.

### §13.5 Files explicitly NOT modified by M07

```
ragcore/condition.py
ragcore/rule_compile.py
ragcore/rule_gap.py
ragcore/rule_loader.py
ragcore/rule_output.py
ragcore/rule_runtime.py
examples/inspector/engine_inspector.py
examples/operation/minimal_operational_scaffold.py
tests/test_minimal_operational_scaffold.py
pyproject.toml
snapshot migration files
all M05 / M06 / PR57 / PR59 / PR60 / PR61 / PR63 historical
   body and addenda (other than the M03 / M04 additions
   listed in §13.3)
historical dev records
```

---

## §14 Structural and behavioral invariants

### §14.1 Structural counts

```
Engine public methods            42   (+1 vs PR75-M06)
Engine private methods           20   (+1 vs PR75-M06)
state-mutating public methods    20   (unchanged set)
read-only public methods         20   (+1 vs PR75-M06)
serialization boundary            2   (unchanged set)
ragcore.__all__                  50   (+1 vs PR75-M06)
snapshot schema_version           2   (unchanged)
snapshot top-level keys          18   (unchanged set)
PR51 packet keys                  7   (unchanged set, same order)
tests                          1578   (= 1517 baseline + 61 new)
```

### §14.2 Behavioral invariants (delta = 0)

```
runtime behavior                    delta = 0
                                     (existing
                                      compute_effective_confidence
                                      returns byte-identical
                                      ScoreValue)
judgment semantics                  delta = 0
claim lifecycle condition           delta = 0
effective-confidence formula        delta = 0
modifier value table                delta = 0
modifier input-set semantics        delta = 0
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

Per commit:

```
255차  python -m pytest -q  ->  1517 passed in 1.32s
                                (docs-only; baseline preserved)

256차  python -m pytest -q  ->  75 failed, 1503 passed in 1.85s
                                (expected: 61 target-API
                                 failures + 14 surface-lock
                                 count failures; zero
                                 unrelated regression)

257차  python -m pytest -q  ->  1578 passed in 1.14s
                                (= 1517 baseline + 61 new
                                 tests from test_effective_
                                 confidence_trace.py)

258차  python -m pytest -q  ->  1578 passed
                                (docs-only; baseline preserved;
                                 elapsed-time value from the
                                 258차 run was not retained in
                                 the source record. 259차
                                 records the final post-audit
                                 run separately at §20.)
```

All baseline tests continue to pass with no edit to their
expectations except for the eight surface-lock files listed
at §13.4.

---

## §16 Forbidden-conclusion scan

The M07 contract §16 lists 22 anti-pattern phrases that M07
is normative against. After 258차, repository scan returns 0
positive assertions outside §16's anti-pattern lock list and
the dev record's reference to it.

Categories of forbidden interpretations preserved as
non-claims:

```
effective_confidence != probability / truth likelihood /
                       verdict / lifecycle readiness
calculation_policy_id != snapshot schema_version / package
                         version / module hash / commit SHA /
                         EngineStateIdentity
source_state_identity != packet capture identity /
                         CAPTURE_BOUND / CURRENTLY_MATCHED /
                         STALE / atomic capture / cross-
                         process continuity / cryptographic
                         state proof
trace != Engine truth record / mutation receipt /
        ReviewedMutationRequest / lifecycle decision /
        mutation authority / automatic revalidation outcome
```

---

## §17 Self-review

```
[x]  1. M07 introduces no state-mutating public method.
[x]  2. M07 introduces no new exception type.
[x]  3. ragcore/condition.py / ragcore/rule_*.py not touched.
[x]  4. examples/inspector/engine_inspector.py not touched.
[x]  5. examples/operation/minimal_operational_scaffold.py
        not touched.
[x]  6. tests/test_minimal_operational_scaffold.py not
        touched.
[x]  7. pyproject.toml not touched.
[x]  8. snapshot migration files not touched.
[x]  9. All six modifier helper bodies unchanged.
[x] 10. compute_effective_confidence retains signature,
        return type, exception type, and byte-identical
        return value via single-core delegation.
[x] 11. _compute_effective_confidence_core is the only
        multiplication site for the formula.
[x] 12. _EFFECTIVE_CONFIDENCE_POLICY_ID is module-private
        (no re-export in ragcore.__all__).
[x] 13. EffectiveConfidenceTrace field order matches §4.1
        verbatim (11 fields, fixed order).
[x] 14. No forbidden trace field (probability / verdict /
        timestamp / packet identity / etc.).
[x] 15. compute_effective_confidence_with_trace is
        classified as read-only (revision unchanged across
        call; snapshot unchanged).
[x] 16. Unknown claim_id -> KeyError (same as legacy API).
[x] 17. trace.source_state_identity == self.state_identity()
        at trace construction.
[x] 18. snapshot schema_version unchanged (= 2).
[x] 19. snapshot top-level key set unchanged (18).
[x] 20. PR51 packet 7-key shape unchanged.
[x] 21. PR32 frozen report key set unchanged.
[x] 22. M03 / M04 historical body untouched; only addenda
        appended.
[x] 23. M01 / M05 / M06 / PR57 / PR59 / PR60 / PR61 / PR63
        historical body and existing addenda untouched.
[x] 24. M07 does NOT pre-define M08 / M09 scope.
[x] 25. M07 does NOT introduce CAPTURE_BOUND / CURRENTLY_
        MATCHED / STALE / packet binding / probability /
        verdict / automatic revalidation / automatic
        mutation.
[x] 26. PR is opened as Draft and is not merged.
```

---

## §18 M-series forward boundary

M07 closes OC-D at the calculation-trace layer. The remaining
M-series scope is M01-locked and unchanged:

```
PR77-M08   Complete Domain-Neutral Reference Operation (OC-F)  NOT STARTED
PR78-M09   RuleStats Update Provenance                 (OC-G)  NOT STARTED
```

Separate, explicitly-directed future work — NOT assigned to
any M08 / M09 slot, NOT auto-scheduled by M07:

```
- CAPTURE_BOUND PR51 packet binding (OC-C closure follow-up)
- CURRENTLY_MATCHED comparison helper
- mechanical packet STALE detector
- effective_confidence -> probability conversion
- automatic lifecycle decision based on trace
- automatic RuleStats update based on trace
- automatic revalidation worker
```

---

## §19 Closing position

> *PR76-M07 closes OC-D at the layer where it actually lives:
> an explanation of an existing Engine calculation, surfaced
> as one frozen read-only value type and one read-only public
> method. The calculation itself is unchanged. The six
> modifier helpers are unchanged. The PR51 packet is
> unchanged. The snapshot schema is unchanged. RuleStats
> semantics are unchanged. Lifecycle conditions are
> unchanged. trace.effective_confidence ==
> Engine.compute_effective_confidence(claim_id) by
> construction. trace.calculation_policy_id identifies
> semantics, not state. trace.source_state_identity
> identifies state, not freshness or packet binding.
> Everything else — a probability conversion, a verdict, a
> lifecycle recommendation, a packet-binding helper, a stale
> detector, an automatic RuleStats update — remains separate
> explicitly-directed future work or M08 / M09 responsibility
> and is NOT auto-scheduled by M07.*

PR76-M07 is opened as **Draft** and is not merged. Closure
language (`CLOSED`) is reserved for the post-squash-merge
state. The M-series sequence after PR76-M07:

```
PR76-M07   Effective Confidence Calculation Trace
                                       (OC-D) OPEN — DRAFT,
                                              NOT MERGED
PR77-M08   Complete Domain-Neutral
           Reference Operation         (OC-F) NOT STARTED
PR78-M09   RuleStats Update Provenance (OC-G) NOT STARTED
```

No automatic next PR. Framework waits for directive.

---

## §20 Audit-closure summary — 259차

PR76-M07 is held in Draft for a docs + tests audit-closure
correction. The 259차 commit `test(review): close M07 trace
audit gaps` resolves three blocking defects (C1 ~ C3) raised
during 258차 review. The 255차 / 256차 / 257차 / 258차 commits
are NOT amended.

### §20.1 Five-commit history

```
255차  058756e   docs(contract): define effective confidence
                  calculation trace
256차  ffa4345   test(core): lock effective confidence trace
                  invariants  (61 test methods)
257차  c29a6c8   feat(engine): add effective confidence
                  calculation trace
258차  ffd4685   docs(dev): record PR76-M07 effective
                  confidence trace (initial pre-review
                  checkpoint — §1 ~ §19)
259차  (this)    test(review): close M07 trace audit gaps
                  (C1 R1 R2 R3 / dev current-record alignment;
                   ~22 audit-closure tests appended)
```

### §20.2 C1 corrections — M04 §2.6 → §1.2

The 255차 ~ 258차 documents cited `M04 §2.6` as the basis for
`state_identity()` being read-only. M04 §2.6 is the
hint-evidence-type-set revision-advance rule; the actual
read-only contract for `state_identity()` is M04 §1.2 (and the
broader §2 advance discipline applies only to the 20
state-mutating public methods, of which `state_identity()` is
not one).

Corrected sites:

```
docs/architecture/
  EFFECTIVE_CONFIDENCE_CALCULATION_TRACE_CONTRACT.md
    §8.2  state_identity() is M04 §1.2 read-only; the §2
          advance discipline covers only state-mutating
          methods.
    §11.1 advance-discipline reference rewritten:
          read-only methods (state_identity() under §1.2 and
          the new compute_effective_confidence_with_trace)
          are explicitly out of the §2 set.

docs/architecture/
  ENGINE_READ_CONSISTENCY_CONTRACT.md  §21
    addendum's state_identity() reference corrected to
    M04 §1.2.

docs/architecture/
  ENGINE_STATE_IDENTITY_PRIMITIVE_CONTRACT.md  §12
    addendum's state_identity() reference corrected to
    §1.2 (the M04 self-reference); §2 is mentioned only as
    the state-mutating-method advance discipline.

docs/dev/PR_076_EFFECTIVE_CONFIDENCE_CALCULATION_TRACE.md
  §4   OC-D scope's "read-only / no-revision-advance
       classification" rewritten to reference §1.2 + §2.
  §10  source_state_identity capture reference corrected to
       §1.2.
  §11  read-only / failure semantics reference rewritten to
       cite §2 advance discipline correctly (covers only the
       20 state-mutating methods; state_identity() under
       §1.2 and the new
       compute_effective_confidence_with_trace are out of
       that set).
```

M05 addendum's prior §2.6 reference (M04 §11, landed under
PR74-M05) is preserved unchanged — it is outside M07 scope and
would otherwise expand 259차's footprint into already-merged
M05 normative text.

### §20.3 C2 corrections — audit-closure test locks

The 256차 test file covered the 6 modifier breakdowns at a
class level but did not enforce the contract's structural
invariants. 259차 appends seven new test classes covering 22
test methods:

```
TestExactSignatureLock                          (3 tests)
  inspect.signature lock on the new public method,
  the new private core, and the legacy public method
  (signature preservation).

TestModifierHelperCallCount                     (3 tests)
  Wrap each of the six modifier helpers; assert call_count
  == 1 per core invocation, per
  compute_effective_confidence_with_trace invocation, and
  per legacy compute_effective_confidence invocation.

TestSingleMultiplicationSite                    (3 tests)
  AST scan over ragcore/engine.py:
    - exactly one Engine method body references all six
      modifier helpers (the private core)
    - compute_effective_confidence does NOT reference any
      modifier helper directly (it delegates)
    - compute_effective_confidence_with_trace does NOT
      reference any modifier helper directly

TestFreshnessMultiActiveMostRecent              (2 tests)
  With two active contradictions of differing strength, the
  freshness_modifier equals the value computed from the
  most-recent (highest evidence_id) contradiction. Negative
  test: not equal to the weak-only baseline.

TestCountModifierExactStrengthPenalty           (3 tests)
  Exact value at avg strength 0.0, 0.6, and 1.0:
    avg 0.0 -> 1.0
    avg 0.6 -> 1.0 - 0.6 * 0.25 = 0.85
    avg 1.0 -> 0.75

TestRuleStatsModifierTiers                      (6 tests)
  Maturity × precision exact product across the full matrix:
    firing 0, precision None -> 0.80
    firing 1, precision None -> 0.90
    firing 2, precision 0.0  -> 0.90
    firing 2, precision 0.5  -> 0.95
    firing 2, precision 1.0  -> 1.00
    firing 0, precision 0.5  -> 0.76

TestEvidenceTypeResolvedContradictionExcluded   (1 test)
  Resolved contradiction evidence is excluded from the
  direct supporting evidence set (separate scenario from the
  existing contradiction-evidence exclusion).

TestGapSharedReferenceSemantics                 (1 test)
  Shared Gap (dedup-hit across two Claims) contributes one
  unresolved-gap reference per Claim; both traces report
  gap_modifier = 0.9.
```

The 259차 audit-closure tests pass without any runtime
correction; they expose no implementation defect.

### §20.4 C3 corrections — dev current-record accuracy

```
C3.1  Test file line count corrected:
        +730 lines -> +703 lines (actual wc -l of the 256차
        file; was a transcription error in 258차 — verified
        independently by base→HEAD diff in the GitHub PR
        compare view).

C3.2  258차 pytest elapsed-time placeholder `<time>` removed.
        The 258차 elapsed-time value was not retained in the
        source record. The new §20 records the final
        post-audit-closure run separately.

C3.3  29 deletions breakdown — the 258차 summary attributed
        all 29 deletions to the legacy compute_effective_
        confidence body reduction. Actual distribution is:

           ragcore/engine.py             -7
             (compute_effective_confidence body reduction)
           ragcore/__init__.py           -3
             (`Public API surface — 49 symbols, grouped by
              purpose (§45.5 + PR73-M04)` comment replaced
              with `50 symbols`; 49 inline references replaced)
           surface-lock test files       -19
             (old `assert count == 41` / `assert ... == 49` /
              `assert ... == 19` lines replaced; not all such
              lines are pure deletions — most are replaced
              by new assertions with adjusted constants, which
              registers as `-N + N+1` in the diff)

        These are mechanical surface-count adjustments, not
        semantic changes. The contract delta-zero invariants
        are preserved unchanged.
```

### §20.5 259차 file footprint (docs + tests only)

```
docs/architecture/
  EFFECTIVE_CONFIDENCE_CALCULATION_TRACE_CONTRACT.md
    §8.2 / §11.1 — M04 §2.6 → §1.2 + §2 advance discipline
                     clarification (C1)

  ENGINE_READ_CONSISTENCY_CONTRACT.md  §21
    M04 §2.6 → §1.2 (C1)

  ENGINE_STATE_IDENTITY_PRIMITIVE_CONTRACT.md  §12
    §2.6 → §1.2 (C1)

docs/dev/PR_076_EFFECTIVE_CONFIDENCE_CALCULATION_TRACE.md
  §4 / §10 / §11 — M04 §2.6 → §1.2 (C1)
  §13.1 — +730 → +703 (C3.1)
  §15 — 258차 `<time>` placeholder removed (C3.2)
  §20 — new audit-closure summary

tests/test_effective_confidence_trace.py
  + 22 audit-closure test methods across 7 new classes (C2):
    TestExactSignatureLock                  (3)
    TestModifierHelperCallCount             (3)
    TestSingleMultiplicationSite            (3)
    TestFreshnessMultiActiveMostRecent      (2)
    TestCountModifierExactStrengthPenalty   (3)
    TestRuleStatsModifierTiers              (6)
    TestEvidenceTypeResolvedContradictionExcluded (1)
    TestGapSharedReferenceSemantics         (1)
```

No `ragcore/*` runtime change. No `examples/*` change. No
other test file change. No `pyproject.toml` change. No M05
addendum or any other already-merged normative text change.

### §20.6 259차 invariants

```
tests                          1517 + 83 = 1600
                                (was 1578 at 258차; +22 from
                                 the 259차 audit-closure tests)
runtime delta from 258차        0
examples/* delta               0
pyproject.toml delta           0
judgment semantics delta       0
formula delta                  0
modifier value delta           0
modifier helper body delta     0
PR51 packet shape delta        0
snapshot schema delta          0
dependency delta               0
automatic execution delta      0
```

### §20.7 259차 regression result

```
$ python -m pytest -q
[...]
1600 passed in 1.41s
$ git diff --check
(clean)
```

### §20.8 Final M-series state

```
P-series   CLOSED
PR70-M01   CLOSED
PR71-M02   CLOSED
PR72-M03   CLOSED
PR73-M04   CLOSED
PR74-M05   CLOSED
PR75-M06   CLOSED
PR76-M07   OPEN — DRAFT, NOT MERGED (this PR)
PR77-M08   NOT STARTED
PR78-M09   NOT STARTED
```

No automatic next PR. PR remains Draft. Framework waits for
directive.
