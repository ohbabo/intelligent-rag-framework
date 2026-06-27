# PR78-M09 — RuleStats Update Provenance

Development record for PR78-M09
(branch `docs/rule-stats-update-provenance`).

```
base:            main 31e0210998374815c90dc9671069034bf6e10d1b
                 (PR77-M08 squash-merged baseline)
branch:          docs/rule-stats-update-provenance
baseline tests:  1806 passed
current pre-dev-record HEAD:
                 4731e453eb05d042a6bd2cc7ab4396e672c2efd0
type:            consumer-owned RuleStats update-provenance contract,
                 tests, and executable example; additive only — no
                 judgment-semantics delta, no Engine API change, no
                 snapshot schema change, no new ragcore symbol
status:          LOCAL BRANCH — PR NOT OPENED, NOT PUSHED, NOT MERGED
```

PR78-M09 closes the M01 discontinuity **OC-G — RuleStats update
provenance** at the conceptual-contract layer plus an executable
consumer-owned example. As of this development record the branch is
local only.

```
Local branch existence   != GitHub PR existence.
Local commit existence   != pushed branch.
Implementation approval  != merged PR.
NOT MERGED              != OPEN.
NOT MERGED              != DRAFT.
```

The post-push state `OPEN — DRAFT, NOT MERGED` applies only after a
separately directed push and Draft PR creation. It is not the current
state.

---

## §1 Commit and no-commit event history

The actual sequence (read-only review and STOP steps are not commits
and have no SHA):

```
276차  commit 5db86f10e0d93c1a78849fc0a2e66ef3bf94d76d
       docs(architecture): define RuleStats update provenance contract

277차  read-only contract review — no commit
       findings: BLOCKER 0 / MAJOR 1 / MINOR 1
       (§16 unconditional before/after vs unknown-pair rejection;
        §22 missing M09-overall-open statement)

278차  commit 9e90d235927b338d0ba1935cb4d1d5633a96af70
       docs(architecture): correct RuleStats provenance receipt
       boundaries
       (276 contract commit preserved; no amend)

279차  corrected-contract re-review — no commit
       findings: BLOCKER 0 / MAJOR 0 / MINOR 0 — APPROVED

280차  commit 130975137949aec492a9a3dfd1deb13614d76ffb
       test(operation): lock RuleStats update provenance example
       (tests-first red gate)

281-entry  STOP-AND-REPORT — no commit
       the example was NOT created; a fresh-report equality
       contradiction in the committed test was found first

280-corr  commit 05fd59735174f06adb934dcee3bdd7d209880c82
       test(review): normalize engine_token in fresh-report equality
       check

280-corr  exact re-review — no commit
       findings: BLOCKER 0 / MAJOR 0 / MINOR 0 — APPROVED

281차  commit 4731e453eb05d042a6bd2cc7ab4396e672c2efd0
       feat(operation): add RuleStats update provenance example
       (red gate green)

282차  local exact implementation review — no commit
       findings: BLOCKER 0 / MAJOR 0 / MINOR 0 — APPROVED

283차  commit docs(dev): record PR78-M09 RuleStats update provenance
       (this commit; SHA assigned at commit time and reported after
        commit)
```

Discipline applied across the chain:

```
no prior commit was amended
no rebase
no squash
no fabricated SHA for any STOP / no-commit event
read-only review steps produced no commit
```

The numbering carries an intentional structure: 277 / 279 / 282 are
read-only reviews (no commit), 281-entry is a STOP-and-report (no
commit), and 280-corr is a correction commit between 280 and 281.

---

## §2 Purpose and scope

M09 does not judge whether a rule is true or high quality. It makes a
reviewed RuleStats update explainable: what basis and approval flow it
went through, and what actual effect it produced — all as
consumer-owned, example-local plain-dict records.

In scope (defined conceptually by the contract and demonstrated by the
example):

```
RuleStatsUpdateCandidate concept
operator decision record
Stage 5.5 / Stage 6 state revalidation
ReviewedMutationRequest concept
direct Engine.update_rule_stats invocation
successful invocation receipt
rejected / failed-attempt receipt
VALUE_CHANGED / NO_VALUE_CHANGE / REJECTED effect classification
KEEP / SET score intent (no CLEAR)
the six provenance meanings
snapshot and authority non-expansion
```

Out of scope — **by design**, not as unfinished required work:

```
an Engine-internal provenance store
snapshot provenance history
a new ragcore public type
a new Engine API
a canonical wire schema
an authentication system
a truth or rule-quality verdict
automatic RuleStats updates
automatic observation / evidence aggregation
a dispatcher / executor / scheduler
network / subprocess / LLM
any M01 / M08 retroactive modification
```

Engine-internal provenance persistence and snapshot persistence are
recorded here as **OUT OF SCOPE / NOT ENTERED BY DESIGN**, not as a
pending requirement. M09 is implemented as a consumer-owned
example-local provenance surface; runtime-core expansion is outside its
scope.

---

## §3 Approved core contract

```
rule identity:        joint (rule_id, rule_version)
count deltas:         firing_delta / true_delta / false_delta
score intent:         KEEP / SET
CLEAR:                none introduced
None argument:        means KEEP (retain the existing value)
```

The six provenance meanings, each a distinct candidate field:

```
caller_identity_reference
update_reason
source_observation_references
delta_provenance
precision_input_basis
policy_reference
```

Authority boundaries (load-bearing inequalities):

```
caller reference        != authentication proof
policy reference         != semantic correctness proof
source observation       != ragcore.Evidence
observed_precision       != ground truth
observed_precision       != probability of truth
provenance completeness  != update correctness
operator approval        != Engine truth
VALUE_CHANGED            != rule quality improvement
```

---

## §4 Receipt-boundary correction history (277 → 279)

The 277차 review found a self-contradiction in the 276차 contract:

```
§16 required EVERY provenance record to carry a RuleStats
before/after (and the pre-call get_rule_stats read), but a REJECTED
attempt on an unknown (rule_id, rule_version) pair fails at the
pre-read itself — there is no RuleStats before to record.
```

The 278차 correction split §16 into two receipt kinds:

```
successful known-pair receipt (§16.1):
  RuleStats before/after required
  identity before/after required

rejected / failed-attempt receipt (§16.2):
  available facts only
  no fabricated RuleStats before/after
  not classified as a successful update provenance
  not equated with NO_VALUE_CHANGE
```

It also added §22.1 stating that closing OC-G at the conceptual layer
is not the same as closing M09 (M09 as a whole remains STARTED / OPEN;
runtime, tests, and the dev record are not yet implemented).

The 279차 re-review on the corrected contract: BLOCKER 0 / MAJOR 0 /
MINOR 0 — APPROVED.

---

## §5 Tests-first surface (280) and the STOP-and-correction (280-corr)

The 280차 commit added `tests/test_rule_stats_update_provenance.py`
(939 lines initially), 18 classes (A–R), 61 test functions, 75 collected
(parametrized). Red phase:

```
new test file alone:   1 failed + 12 passed + 62 skipped
unique red gate:       TestImplementationSurface.
                       test_rule_stats_provenance_example_exists
existing suite:        1806 passed
full red-phase suite:  1 failed + 1818 passed + 62 skipped
unrelated failures:    0
```

What 280 locks:

```
three effects · six provenance meanings · joint pair identity ·
candidate/decision/request separation · Stage 5.5 / Stage 6 ·
direct invocation (AST) · successful/failed receipt separation ·
KEEP / SET · source observation optionality · non-authority locks ·
register_rule separation · snapshot boundary · M01/M08 history
preservation · structural invariants
```

### 281-entry STOP-AND-REPORT

Before writing the example, a contradiction was found in the committed
test:

```python
r1 = run()
r2 = run()
assert r1 == r2
assert r1 is not r2
```

Why it could not hold in green: each run constructs fresh Engines, the
Engine identity token is a per-Engine `uuid4().hex`, and the contract
requires recording the real `identity_before`/`identity_after` (token +
revision) in the receipts and using full `EngineStateIdentity` value
equality at Stage 5.5 / Stage 6. Two fresh runs therefore embed
different tokens, so whole-report equality is unsatisfiable without
either omitting/fabricating the token (contract violation) or making
the token deterministic (ragcore change). Per the tests-first STOP rule,
the example was not written:

```
no example created      no example commit
no test modification     no ragcore modification
HEAD unchanged
```

### 280-corr

The 280-corr commit (`05fd597`) added a test-only normalizer that, in a
COMPARISON COPY only, recursively replaces every `engine_token` value
with `"<opaque-engine-token>"`:

```
dict / list / tuple recursion; tuple type preserved
revision preserved; all non-token values preserved
original reports not mutated
whole-report equality retained (only the opaque token normalized)
r1 is not r2 retained
```

Post-correction red-gate shape: 12 passed / 62 skipped / 1 failed
(only the example-absence red gate). This is not a weakening of the
test; it verifies full structural/semantic determinism while excluding
one legitimately non-deterministic opaque value. The 280-corr exact
re-review: BLOCKER 0 / MAJOR 0 / MINOR 0 — APPROVED.

---

## §6 Example implementation (281)

```
file:        examples/operation/rule_stats_update_provenance_example.py
lines:       582
entry point: run_rule_stats_update_provenance_example()
             -> dict[str, Any]
top-level:   overall_status / cases / non_authority_locks /
             snapshot_boundary / historical_boundary
```

The file and its returned dict are example-local plain dicts — not a
public ragcore type, canonical schema, snapshot schema, Engine return
type, authentication record, or truth / quality verdict. Each call uses
fresh Engines and fresh records; the real Engine `engine_token` is
recorded as-is (never pre-normalized in the example itself).

### Three-case runtime meaning

VALUE_CHANGED:

```
pair (101, 1) · deltas +1 / +1 / +0
observed_precision SET ScoreValue(0.75) · false_positive_rate KEEP/None
RuleStats before != after · same engine_token · revision +1
actual_effect VALUE_CHANGED · update_invoked True · return None
```

NO_VALUE_CHANGE:

```
pair (202, 1) · deltas 0 / 0 / 0 · scores KEEP / KEEP
RuleStats before == after · identity unchanged · revision delta 0
actual_effect NO_VALUE_CHANGE · update_invoked True · return None
```

REJECTED unknown pair:

```
pair (999, 1) unregistered
pre-read engine.get_rule_stats raises KeyError
update_rule_stats NOT invoked · update_invoked False
RuleStats before/after NOT fabricated · identity unchanged
actual_effect REJECTED · failed-attempt receipt
```

Across one normal run, `Engine.update_rule_stats` is invoked **exactly
2 times** (the two successful cases); the REJECTED case invokes it 0
times.

---

## §7 Review and invocation boundary

Per-case order:

```
candidate -> operator decision -> Stage 5.5 revalidation ->
request materialization -> Stage 6 revalidation -> public pre-read ->
direct update or rejection -> public post-read -> receipt
```

Implementation facts:

```
Stage 5.5 / Stage 6:   full EngineStateIdentity value equality
direct invocation:     literal engine.update_rule_stats(...) call site
dynamic dispatch:      none
getattr / eval / exec / apply_request / auto_dispatch:  none
candidate / snapshot / request / receipt arguments:
                       four distinct deep-copied dict objects
callable / Engine instance inside records:  none
```

### Successful vs failed-attempt receipts

```
successful receipt:
  identity_before / identity_after
  rule_stats_before / rule_stats_after
  reviewed_arguments / actual_effect / update_invoked /
  engine_return_value

failed-attempt receipt:
  distinct record_kind
  rejection_cause
  available_facts_only
  update_invoked False
  no synthetic RuleStats
```

The Engine `update_rule_stats` return value (`None`) is not the basis
for the effect; the effect is classified from the public before/after
RuleStats reads and the state identity.

---

## §8 Snapshot and history preservation

```
snapshot schema_version:   2
snapshot top-level keys:   18
provenance-history key:    absent
RuleStats fields:          7
```

M01 (`examples/operation/minimal_operational_scaffold.py`): the six
"no" provenance diagnosis and `future_contract = OC-G` are unchanged;
the source file is not modified.

M08 (`examples/operation/complete_domain_neutral_reference_operation.py`):
`rule_stats_provenance_status = NOT_ENTERED_M09` is preserved as a
historical fact of M08's execution scope and is NOT retroactively
changed now that M09 exists; the source file is not modified. The M09
example's completion does not overwrite M08's historical
`NOT_ENTERED_M09`.

---

## §9 Final verification numbers

```
M09 test file:                75 passed / 0 failed / 0 skipped
existing suite (excl. M09):   1806 passed
full suite:                   1881 passed / 0 failed / 0 skipped
direct example execution:     exit 0
```

Structural invariants (unchanged):

```
Engine public / private:      42 / 20
state-mutating / read-only:   20 / 20
serialization boundary:       2
ragcore.__all__:              50
snapshot:                     v2 / 18 keys
PR51 packet:                  7 keys
RuleStats:                    7 fields
```

---

## §10 Changed-file and cumulative scope

Cumulative branch diff versus `main 31e0210` **before** this 283차
commit:

```
docs/architecture/RULE_STATS_UPDATE_PROVENANCE_CONTRACT.md   +736
examples/operation/rule_stats_update_provenance_example.py   +582
tests/test_rule_stats_update_provenance.py                   +966
                                                            ──────
3 files changed, 2284 insertions(+), 0 deletions(-)
```

After this 283차 commit the cumulative changed-file count becomes
**4** (this dev record added). The exact post-283 cumulative
additions/deletions and this commit's own SHA are recorded in the 283차
completion report, not invented inside this document.

The following remain 0 across the whole branch:

```
ragcore changes · dependency changes · config changes ·
M01 changes · M08 changes · snapshot-implementation changes
```

---

## §11 Current completion vs lifecycle

```
M09 conceptual + implementation scope:   COMPLETE AND APPROVED
  contract (276 + 278) APPROVED at 279
  tests (280) + correction (280-corr) APPROVED
  example (281) APPROVED at 282

283 dev record:                          committed by this commit

GitHub PR lifecycle:                     NOT STARTED
  push:    NOT performed
  PR:      NOT opened
  merge:   NOT performed
```

M09 overall status:

```
STARTED / OPEN
  contract / tests / correction / example:  APPROVED
  dev record:                               COMMITTED after 283
  PR lifecycle: LOCAL BRANCH — PR NOT OPENED, NOT PUSHED, NOT MERGED
```

This document does not assert that the PR is closed, that the M-series
is finished, or that M09 is merged; nor does it describe the current
state as a Draft. The runtime core and snapshot persistence are out of
scope by design (§2), not pending or unfinished work. The M-series is
not finished until M09 is actually merged.

---

## §12 Forward sequence (conditional, not part of 283)

```
284:   dev record read-only exact review
then:  full branch final audit
then (only on separate direction):
       push -> Draft PR creation -> GitHub review -> merge -> cleanup
```

Push and Draft PR creation are not part of this 283차 commit.

No automatic next PR. Framework waits for directive.

---

## Post-merge reconciliation (independent audit, 2026-06-27)

PR78-M09 was squash-merged as GitHub PR #79 (6d43cd8959fa9e37a60efe527f84b5ba60c6413e) onto 31e0210998374815c90dc9671069034bf6e10d1b, 2026-06-25 (KST 20:34). The
intermediate "Draft / OPEN — DRAFT, NOT MERGED" and "Framework
waits for directive" language, and any "(this commit)" / "(this)"
차수 self-references earlier in this record, are historical accounts
of the pre-merge correction cycle; they are superseded by this
block.

Final state: PR78-M09 CLOSED (merged). This reconciliation changes no
runtime, contract semantics, or historical metric recorded above.
Current main baseline: 1999 passed, Engine 42 / 20, ragcore.__all__
50, snapshot schema_version 2 / 18 keys, PR51 packet 7 keys.
