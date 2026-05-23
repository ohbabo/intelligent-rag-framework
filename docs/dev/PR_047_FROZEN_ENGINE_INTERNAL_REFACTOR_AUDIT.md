# PR47 — Frozen Engine Internal Refactor Audit

## Scope limitation (locked, user 2026-05-23)

```text
PR47 is an audit-first documentation PR, not a refactor PR.

It preserves the frozen engine baseline by changing no ragcore source,
adding no tests, adding no public symbols, and changing no engine
behavior.

The only new artifact is an internal map for future behavior-preserving
refactor review.

PR48 is not automatically entered.
```

한국어:

```text
PR47 은 리팩토링 PR 이 아니라 audit-first documentation PR 이다.

ragcore 소스 / test / public symbol / engine 동작 — 모두 변경 없음.
유일한 산출물은 향후 behavior-preserving refactor review 용
internal map 이다.

PR48 은 자동 진입하지 않는다.
```

PR47 opens the "Engine freeze ≠ no-touch" distinction by producing one architecture-level map. PR47 itself performs zero refactor. PR48, if it ever enters, must honor the do-not-touch boundary that PR47 locked.

## 1. Baseline + cycle record

```text
main:    5bb360f (PR46-B merged)
tests:   1145 passing

176차:
  branch:  docs/frozen-engine-internal-refactor-audit
  commit:  b6f0e38 docs(architecture): add engine internal map
                                       (frozen refactor audit)
  file:    docs/architecture/ENGINE_INTERNAL_MAP.md (+557 lines, NEW)
  pytest:  1145 passing (unchanged)
  ragcore source change: 0 lines (engine.py 0 bytes)
  Draft PR: #48 PR47: Frozen Engine Internal Refactor Audit

177차 (this):
  docs(dev): record PR47 closing + ready + squash merge
  file:    docs/dev/PR_047_FROZEN_ENGINE_INTERNAL_REFACTOR_AUDIT.md
```

## 2. Engine freeze distinction (lock)

```text
Engine freeze
≠ 아무 코드도 절대 안 건드림

Engine freeze
= public behavior / public method surface /
  snapshot contract / judgment semantics 안 바꿈
```

PR47 honors the second definition. ragcore source bytes did not change; the audit lives in `docs/architecture/`.

## 3. What PR47 is

```text
PR47 = Frozen Engine Internal Refactor Audit
성격   = audit-first documentation PR
        - reads ragcore/engine.py at baseline 5bb360f
        - emits one architecture map document
        - identifies safe-to-touch and do-not-touch regions
        - hands those findings to a future, separately-decided PR48

성격 아님:
  - refactor PR
  - implementation bridge
  - "engine 개선 PR"
  - new public API PR
  - new contract section PR
  - adapter implementation PR
  - test addition PR
```

## 4. PR47 internal map structure (13 sections)

`docs/architecture/ENGINE_INTERNAL_MAP.md` — 557 lines, 13 sections:

```text
§0   Scope limitation                  doc-only audit; refactor 금지
§1   Status                             audit phase, source 0
§2   ragcore/engine.py overview         1800 lines / 1 class / 61 methods /
                                         19 module consts / 24 module helpers /
                                         14 logical regions (A ~ N) with line ranges
§3   Do-not-touch boundary             10 freeze items
§4   Category 1 — internal function split candidates    5 candidates
§5   Category 2 — duplicate logic candidates            2 candidates
§6   Category 3 — section boundaries (comments only)   13 insertion lines
§7   Category 4 — private helper relocation candidates  1 candidate
§8   Category 5 — private / helper docstring          ~25 helpers
§9   Category 6 — import cleanup                        0 actionable
§10  Summary table                      ~46 candidates / 11 freeze items
§11  What PR47 does NOT do
§12  PR48 entry conditions              5 must-hold rules
§13  Closing meaning
```

Each safe-to-touch candidate carries its own do-not-touch boundary referencing §3 item numbers.

## 5. 10 do-not-touch items (recorded for future PR48)

```text
1.  7-modifier composition formula
2.  6 lifecycle helper internal decision logic
3.  snapshot serialize/restore symmetry  (6 × 6, PR35-O7)
4.  40 public method signatures
5.  public observable behavior of every Engine.method(*args)
6.  18 snapshot top-level keys
7.  effective_confidence modifier call chain
8.  report / read-surface 6 frozen key sets
9.  ragcore.__all__ 48 symbols
10. adapter / Cerberus integration code (absent, must stay absent)
```

These ten items are the **freeze surface.** PR47 names them; PR48 (if it enters) must preserve them by-construction.

## 6. PR48 entry conditions (recorded for future decision)

```text
PR48 (if ever entered) must satisfy all five:

  1. PR48 selects ONE category from §4 ~ §9 of the audit doc.
     (Do not bundle multiple categories in a single PR.)

  2. PR48 selects a subset of "safe-to-touch candidates" inside
     that category. Do not claim to address all candidates at
     once.

  3. PR48 demonstrates:
       - pytest -q still returns 1145 passing
       - ragcore.__all__ still has 48 symbols
       - Engine public method count still 40
       - snapshot schema_version still 2
       - 18 snapshot top-level keys unchanged
       - to_snapshot() / from_snapshot() round-trip preserves
         compute_effective_confidence for the same claim_ids
       - PR41 simulation tests + PR43-C 168차 invariant tests
         still pass with zero changes

  4. PR48 cycle follows the 2-차수 pattern:
       N차      src refactor commit (engine.py only, minimal diff)
       N+1차    docs(dev) record + ready + squash merge

  5. PR48 cycle does NOT touch any of the 10 do-not-touch items
     listed in §5 above.
```

PR48 is **not auto-scheduled.** It is a separate, optional decision.

## 7. self-review checklist (177차 close-out)

```text
[x] ragcore source diff 0
        ragcore/engine.py        0 bytes changed
        ragcore/types.py         0 bytes changed
        ragcore/__init__.py      0 bytes changed
        ragcore/rule_output.py   0 bytes changed

[x] tests diff 0
        no test added, removed, renamed, or modified
        pytest -q still 1145 passing

[x] public symbol diff 0
        ragcore.__all__   still 48 symbols
        Engine            still 40 public methods

[x] engine behavior diff 0
        compute_effective_confidence  unchanged
        lifecycle transitions          unchanged
        snapshot to_snapshot/from_snapshot  unchanged
        snapshot schema_version        still 2
        snapshot top-level keys        still 18

[x] docs/architecture/ENGINE_INTERNAL_MAP.md  is the only
    architecture artifact added (557 lines, 176차)

[x] docs/dev/PR_047_FROZEN_ENGINE_INTERNAL_REFACTOR_AUDIT.md
    is added (this file, 177차)

[x] PR48 entry is explicitly not automatic
        recorded in §6 above and §12 of ENGINE_INTERNAL_MAP.md

[x] PR title and body say "audit", not "refactor"
        PR #48 title: PR47: Frozen Engine Internal Refactor Audit
        PR #48 body: starts with "PR47 is a doc-only audit"
```

## 8. No-change verification

```text
pytest -q                                1145 passing (unchanged from PR46-B)
ragcore.__all__                          48 symbols (PR31-S baseline)
unique symbols                           48
Engine public methods                    40 (PR33-M docstring 40/40)
modifier helpers                          6 with (self, claim_id: int) -> float
                                          (PR34-O signature preserved)
serialize/restore symmetry              6 × 6 (PR35-O7 preserved)
snapshot schema_version                   2 (PR21-L preserved)
snapshot top-level keys                  18 (PR36-PKG _LOCKED frozenset)
report shape                              6 frozen key sets (PR32-V)

ragcore source change since PR36-PKG     0 lines
ragcore source cerberus mentions          0 (generic identity preserved)
external package imports in ragcore       0
engine.py source bytes                    0 changed

adapter-specific symbols in ragcore.__all__:  none
ragcore type added in PR47:                    none
ragcore method surface change:                  none
new tests:                                       0 (default lock honored)
new public symbol:                               0
new engine behavior:                             0
contract §51:                                    not added
runtime enforcement:                             0
adapter implementation:                          not included
```

All framework invariants preserved.

## 9. What PR47 closed

```text
- engine.py 1800 lines 의 internal structure 를 14 logical regions
  로 grouping 한 architecture map 등록
- 10 do-not-touch freeze items 의 명문화
- 6 category 별 safe-to-touch candidates ~46 개 식별
- 각 candidate 별 do-not-touch boundary cross-reference
- PR48 entry conditions 5 must-hold rules 박음
- "Engine freeze ≠ no-touch" distinction 의 문서적 기반
- 향후 behavior-preserving refactor review 의 reviewable scope
```

## 10. What PR47 deliberately did NOT do

PR47 did NOT:

```text
- perform any refactor
- move any function inside engine.py
- rename any symbol
- add or remove any comment or docstring inside ragcore/
- touch engine.py source bytes
- touch ragcore/types.py / ragcore/__init__.py / ragcore/rule_output.py
- add or change any test
- add new public API
- add or remove ragcore.__all__ entries
- propose new contract section (§51 or beyond)
- propose runtime enforcement
- propose adapter implementation
- propose Cerberus-specific code
- propose modifier formula adjustments
- propose snapshot schema changes
- propose report key changes
- schedule PR48 automatically
```

## 11. Implementation footprint

Changed files (176 + 177):

```text
docs/architecture/ENGINE_INTERNAL_MAP.md                       +557 lines (176차, NEW)
docs/dev/PR_047_FROZEN_ENGINE_INTERNAL_REFACTOR_AUDIT.md       this record (177차)
```

Unchanged:

```text
ragcore/engine.py          (source bytes:   0 changed)
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
pyproject.toml
README.md  (top-level project README untouched)
docs/README.md
docs/contracts/05_DATA_CONTRACT_MVP.md       (no §51 added)
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
docs/guides/ADAPTER_POLICY_GUIDE.md
docs/guides/RETRIEVAL_OUTPUT_TO_EVIDENCE_GUIDE.md
docs/guides/ENGINE_METHOD_CALL_PLAYBOOK.md
docs/guides/ENGINE_INTEGRATION_ANTI_PATTERNS.md
docs/guides/DOMAIN_NEUTRAL_REFERENCE_FLOW.md
tests/test_external_adapter_simulation.py
tests/test_engine_method_call_playbook_usage.py
examples/probe/external_consumer_probe.py
all other tests
all other docs/
```

No source change. No test change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change.

## 12. PR47 cycle

```text
176차  docs(architecture) — ENGINE_INTERNAL_MAP.md (+557 lines)   b6f0e38
177차  docs(dev) — PR47 record + ready + squash merge              this commit
```

Two-차수 cycle. No new tests. No source change. No new public API. No automatic next PR.

## 13. Pattern position recap

```text
PR39    compatibility audit                documentation-only
PR40    adapter policy guide               documentation-only
PR41    external adapter simulation        tests-only
PR42    retrieval translation guide        documentation-only
PR43-C  engine method call playbook        guide + tests
PR44-D  integration anti-patterns          documentation-only
PR45-E  domain-neutral reference flow      documentation-only
PR46-B  documentation map / reader entry   documentation-only
PR47    frozen engine internal refactor    documentation-only (this)
            audit

All nine (post-PR36-PKG):
  ragcore source unchanged
  framework method surface frozen
  PR48 (if entered) remains separate, behavior-preserving by-construction
```

## 14. Followup

```text
PR48 — Behavior-preserving refactor (one category from §4 ~ §9 of
       the audit doc)
       NOT auto-scheduled
       NOT entered by PR47
       requires explicit user decision and the 5 entry conditions
       in §6 above

Tracks that remain user-decided (no auto entry):
  Track A — Framework freeze / maintenance
  Track B2 — top-level README integration index
  Track C — Additional executable guards (doc-stack integrity etc.)
  Track D — Consumer adapter implementation (separate repo)
  Track E — Engine evolution from real feedback (real case required)
```

## 15. Framework state (post-PR47)

```text
ragcore baseline:
  main:    5bb360f (pre-merge; new hash after squash merge)
  1145 tests passing (unchanged from PR46-B)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  1 architecture audit (compatibility matrix)
  1 architecture audit (engine internal map — this PR)
  5 adapter guides (policy + retrieval + call playbook +
                     anti-patterns + reference flow)
  1 documentation map / reader entry point
  1 disposable probe (PR38-A)
  2 executable simulation/usage test suites
    (test_external_adapter_simulation.py — PR41, 18 tests)
    (test_engine_method_call_playbook_usage.py — PR43-C, 12 tests)

10-layer adapter documentation stack: complete
  philosophy + runtime + contract + audit + policy guide +
  simulation + retrieval guide + call playbook + anti-patterns
  guide + reference flow
  ✓ all ten layers present

Reader entry point (PR46-B): docs/README.md ✓
Internal refactor audit (PR47): docs/architecture/ENGINE_INTERNAL_MAP.md ✓

ragcore source change since PR36-PKG:  0 lines
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 16. Closing meaning

```text
PR47 maps the inside of frozen engine.py.

It does not refactor.
It identifies what can be safely moved and what must not be touched.

The freeze surface is unchanged.
PR48 is not scheduled. It is a separate, optional decision.

frozen baseline preserved.
internal map drawn.
framework waits.
```

Locked closing sentences:

```text
PR47 is an audit-first documentation PR, not a refactor PR.

It preserves the frozen engine baseline by changing no ragcore
source, adding no tests, adding no public symbols, and changing
no engine behavior.

The only new artifact is an internal map for future
behavior-preserving refactor review.

PR48 is not automatically entered.
```

No automatic next-PR proposal. User decides direction.
