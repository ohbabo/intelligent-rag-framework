# PR46-B — Documentation Map / Reader Entry Point MVP

## Scope limitation (locked, user 2026-05-23)

```text
PR46-B makes the completed documentation stack discoverable.

It does not add framework behavior.
It does not add tests.
It does not implement an adapter.
It does not add contract §51.
It does not change the Engine public surface.
```

한국어:

```text
PR46-B 는 PR45-E 시점에 이미 닫힌 10-layer adapter documentation
stack 에 reader entry point 하나만 추가한다.

framework 동작 / test / adapter / contract §51 / Engine public
surface — 모두 변경 없음.
```

PR46-B opens Track B (Documentation discoverability polish) from the post-PR45 roadmap. It is the framework repo's last housekeeping PR after the documentation stack closed at PR45-E. It introduces a single reader-facing file, `docs/README.md`, that maps the existing tree.

## 1. Baseline + cycle record

```text
main:    1d11077  (PR45-E merged)
tests:   1145 passing

174차:
  branch:  docs/documentation-map-entry-point
  commit:  d3d63d4 docs(docs): add documentation map / reader entry point
  file:    docs/README.md (+340 lines, NEW)
  pytest:  1145 passing (unchanged)
  ragcore source change: 0 lines
  Draft PR: #47 PR46-B: Documentation Map / Reader Entry Point

175차 (this):
  docs(dev): record PR46-B closing + ready + squash merge
  file:    docs/dev/PR_046_DOCUMENTATION_MAP_ENTRY_POINT_MVP.md
```

## 2. What PR46-B is / is not

```text
PR46-B = Documentation Map / Reader Entry Point
성격     = docs discoverability polish
           record-and-close work after PR45-E
아님     = 새 framework 작업
           새 Engine behavior
           새 contract section
           새 test 추가
           새 adapter 구현
           implementation bridge
           "구현 시작 직전 마지막 연결 문서" 류 신호
```

PR46-B does not add any capability. It exposes the already-complete stack to first-time readers.

## 3. docs/README.md structure (11 sections)

```text
§0   Current baseline                       main / tests / state / locks
§1   What this framework is / is not
§2   Start here — shortest reading path     three documents
§3   Reader path A — Consumer integrating against framework
§4   Reader path B — Framework contributor / reviewer
§5   Reader path C — Future AI assistant / code reviewer
§6   10-layer adapter documentation stack
§7   Positive / negative / reference triad  (PR43-C / PR44-D / PR45-E)
§8   What is implemented vs not implemented
§9   Hard stop rules                        cite AP-* IDs
§10  Current next-step options              5 options, no auto entry
Closing meaning
```

11 sections. 340 lines. Zero ragcore source change. Zero new tests.

## 4. Three reader audiences

```text
Audience A — Consumer integrating against framework
  reading order:
    philosophy → runtime → §50 contract → policy guide →
    retrieval guide → call playbook → anti-patterns →
    reference flow

Audience B — Framework contributor / reviewer
  reading order:
    identity → layer model → contracts → audit →
    engine source → executable invariants →
    dev records (post-PR36-PKG) → git workflow →
    earlier roadmap

Audience C — Future AI assistant / code reviewer
  goal: recover baseline + forbidden assumptions across sessions
        without proposing a forbidden next step
  reading order:
    baseline (§0) → forbidden next steps (§9) →
    four lock sentences (PR43-C §2 / PR44-D §2 / PR45-E §2) →
    frozen public surface (ragcore/__init__.py / engine.py /
                            PR_036 record) →
    executable invariants (PR41 / PR43-C 168차 tests) →
    most recent dev records (PR_043 / PR_044 / PR_045)
```

Three audiences are explicit so the map does not collapse into one undifferentiated reading order.

## 5. File location choice

```text
chosen:      docs/README.md
not chosen:  docs/guides/README.md
             - the stack spans docs/01_*, docs/03_*,
               docs/contracts/, docs/architecture/,
               docs/guides/, docs/dev/
             - guide-only README would not cover the full stack
not changed: top-level README.md
             - project/package-facing
             - already contains quickstart from PR37 D-mid
             - intentionally left untouched
```

If a separate top-level README integration index is desired (Track B2 from the roadmap), it is a future PR — not bundled here.

## 6. No-change verification

```text
pytest -q                                1145 passing (unchanged from PR45-E)
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

adapter-specific symbols in ragcore.__all__:  none
ragcore type added in PR46-B:                  none
ragcore method surface change:                  none
new tests:                                       0 (default lock honored)
new public symbol:                               0
new engine behavior:                             0
contract §51:                                    not added
runtime enforcement:                             0
adapter implementation:                          not included
top-level README:                                unchanged
```

All framework invariants preserved.

## 7. What PR46-B closed

```text
- 10-layer stack 의 reader entry point 부재 문제
- 세 reader audience (Consumer / Contributor / Future AI assistant)
  의 진입 순서 명시
- "어떤 파일부터 읽어야 하는가" 질문에 대한 답
- 차후 세션에서 baseline 회복을 위한 §5 Audience C reading order
- §9 hard stop rules — AP-* ID 로 boundary 인용 가능하게 정리
- §10 next-step options 5종 명시 — 어느 track 으로도 강제 안 함
```

PR46-B is the closing housekeeping artifact for the framework-side documentation stack.

## 8. What PR46-B deliberately did NOT do

PR46-B did NOT:

```text
- adapter 구현
- Engine 동작 변경
- 새 Engine method 추가
- 기존 Engine method signature 변경
- modifier 7종 공식 변경
- threshold / scoring calibration 변경
- 새 test 추가
- contract §51 신설
- ragcore.__all__ 추가
- engine.py / types.py / __init__.py / rule_output.py 수정
- 새 snapshot schema version
- 새 public API
- runtime enforcement 추가
- top-level README.md 수정
- 도메인 어휘 도입
- 새 candidate / 새 PR 자동 제안
- "이제 구현 시작 가능" 류 implementation-bridge 의미 부여
```

## 9. Implementation footprint

Changed files (174 + 175):

```text
docs/README.md                                       +340 lines (174차, NEW)
docs/dev/PR_046_DOCUMENTATION_MAP_ENTRY_POINT_MVP.md this record (175차)
```

Unchanged:

```text
ragcore/engine.py
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
pyproject.toml
README.md  (top-level project README untouched)
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

No source change. No test change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change. Top-level README untouched.

## 10. PR46-B cycle

```text
174차  docs(docs) — Documentation Map / Reader Entry Point (+340 lines)   d3d63d4
175차  docs(dev) — PR46-B record + ready + squash merge                    this commit
```

Two-차수 cycle. No new tests. No source change. No new public API. No automatic next PR.

## 11. Pattern position recap

```text
PR39    compatibility audit                documentation-only
PR40    adapter policy guide               documentation-only
PR41    external adapter simulation        tests-only
PR42    retrieval translation guide        documentation-only
PR43-C  engine method call playbook        guide + tests
PR44-D  integration anti-patterns          documentation-only
PR45-E  domain-neutral reference flow      documentation-only
PR46-B  documentation map / reader entry   documentation-only (this)

All eight (post-PR36-PKG):
  ragcore source unchanged
  framework method surface frozen
  consumer adapter implementation remains separate, not automatic
```

## 12. Followup (track-by-track, no auto entry)

```text
Track A — Framework freeze / maintenance
  Optional: PR46-A baseline freeze record
            (file not present; would be created by an explicit
             Track A decision)
  Optional: PR46-A2 changelog / release notes

Track B — Documentation discoverability polish
  Done   : PR46-B (this) — docs/README.md reader entry point
  Optional next:
            PR46-B2 README integration index at top-level README.md
            (file edit, not creation)

Track C — Additional executable guards
  Optional, not recommended unless real drift risk identified:
            tests/test_documentation_stack_integrity.py
            tests/test_anti_pattern_guide_integrity.py

Track D — Consumer adapter implementation
  Separate repo / separate decision. NOT a framework PR.

Track E — Engine evolution based on real feedback
  Requires real-case evidence. Migration plan + backward
  compatibility discussion required.
```

After PR46-B merges, NO automatic next PR is proposed. All tracks above remain user-decided.

## 13. Framework state (post-PR46-B)

```text
ragcore baseline:
  main:    1d11077 (pre-merge; new hash after squash merge)
  1145 tests passing (unchanged from PR43-C through PR45-E)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  1 architecture audit (compatibility matrix)
  5 adapter guides (policy + retrieval + call playbook +
                     anti-patterns + reference flow)
  1 documentation map / reader entry point (this)
  1 disposable probe (PR38-A)
  2 executable simulation/usage test suites
    (test_external_adapter_simulation.py — PR41, 18 tests)
    (test_engine_method_call_playbook_usage.py — PR43-C, 12 tests)

10-layer adapter documentation stack:
  philosophy + runtime + contract + audit + policy guide +
  simulation + retrieval guide + call playbook + anti-patterns
  guide + reference flow
  ✓ all ten layers present

Reader entry point:
  docs/README.md ✓
  three reader audiences (A / B / C) ✓
  five next-step options listed without auto entry ✓

ragcore source change since PR36-PKG:  0 lines
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 14. Closing meaning

```text
PR46-B closes the documentation discoverability gap.

The 10-layer adapter documentation stack was already complete
after PR45-E. PR46-B makes that stack navigable through one
docs/README.md entry point.

It does not add framework behavior.
It does not add tests.
It does not implement an adapter.
It does not add contract §51.
It does not change the Engine public surface.

The framework reads as a stack now.
The framework waits.
```

Locked closing sentences:

```text
PR46-B 는 PR45-E 시점에 이미 닫힌 10-layer adapter documentation
stack 에 reader entry point 하나만 추가했다.

framework 동작 / test / adapter / contract §51 / Engine public
surface — 모두 변경 없음.

documentation discoverability gap closed.
documentation stack navigable.
framework waits.
```

No automatic next-PR proposal. User decides direction.
