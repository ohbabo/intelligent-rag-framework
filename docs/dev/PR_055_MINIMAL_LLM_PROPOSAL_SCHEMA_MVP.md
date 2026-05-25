# PR55 — Minimal LLM Proposal Schema MVP

## Scope limitation (locked, user 2026-05-25)

```text
PR55 adds a consumer-side proposal shape validator.

It validates the minimum structure of LLM proposal drafts.
It does not validate truth.
It does not authorize tool execution.
It does not mutate Engine state.
It does not add ragcore symbols.
```

한국어:

```text
PR55 는 LLM proposal draft 를 실행 가능한 계획으로 만들지 않는다.
proposal 의 최소 구조와 금지 top-level key 만 검사한다.
```

PR55 is the first executable enforcement layer on top of PR54's proposal layer bridge spec. The validator lives entirely outside ragcore (in `examples/proposal/`), uses zero ragcore imports at runtime, and locks its behavior with 11 invariant tests. PR54 §12 5 must-hold and PR47 / PR49 / PR52 / PR53 locks are all preserved.

## 1. Baseline + cycle record

```text
main:    5141da8  (PR54 merged)
tests:   1158 passing

194차:
  branch:  feat/minimal-llm-proposal-schema
  commit:  c00c4ee feat(example): add minimal proposal
                                   schema validator
  file:    examples/proposal/proposal_schema.py
           (+396 lines, NEW)
  pytest:  1158 passing (unchanged)
  ragcore source change: 0 bytes

195차:
  commit:  423583e test(example): lock proposal schema invariants
  file:    tests/test_proposal_schema.py
           (+387 lines, NEW)
  pytest:  1169 passing (1158 + 11 new tests)
  ragcore source change: 0 bytes

196차 (this):
  docs(dev): record PR55 closing + ready + squash merge
  file:    docs/dev/PR_055_MINIMAL_LLM_PROPOSAL_SCHEMA_MVP.md
```

## 2. What PR55 is / is not

```text
PR55 = Minimal LLM Proposal Schema MVP
성격   = consumer-side shape validator
         PR54 §10 forbidden proposal readings 중 6 개
         (P1/P3/P4/P5/P6/P7) 를 structural top-level key
         detect 로 잠금
         + 7 shape error codes (S1~S7)
         executable proof that PR54 spec is partially enforceable

성격 아님:
  - executable plan builder
  - normalizer (normalize_llm_proposal 은 OOS)
  - judgment validator
  - tool execution authorizer
  - final report writer
  - semantic / LLM-phrasing validator
  - nested-structure walker (top-level only)
  - ragcore extension
  - LLMProposal / ProposalSchema 등 ragcore symbol 추가
  - PR56 자동 진입
```

## 3. Validator implementation summary (194차)

`examples/proposal/proposal_schema.py` — single function, 396 lines:

```python
def validate_llm_proposal_shape(
    proposal: dict,
    source_packet: dict,
) -> list[tuple[str, str]]
```

Returns:

```text
[]                                  no violation
[(code, message), ...]              violations found
                                    caller decides; NEVER raises
                                    NEVER mutates proposal or source_packet
```

Minimal allowed proposal shape:

```text
required (3):
  category               : str    (one of 5 allowed categories)
  target_claim_id        : int    (must match source_packet claim.id)
  note                   : str

optional (3):
  target_evidence_id     : int
  target_gap_id          : int
  supporting_packet_ref  : str
```

Allowed categories (PR54 §5):

```text
uncertainty_note
evidence_gap_question
next_inspection_question
packet_summary_note
report_note_candidate
```

Internal structure:

```text
shape constants (frozensets):
  _REQUIRED_FIELDS           3
  _OPTIONAL_FIELDS           3
  _ALLOWED_TOP_LEVEL_FIELDS  6 (required ∪ optional)
  _ALLOWED_CATEGORIES        5

forbidden key vocabularies (frozensets):
  _P1_VERDICT_KEYS           5
  _P3_STATUS_MUTATION_KEYS   5
  _P4_TOOL_EXECUTION_KEYS    7
  _P4_TOOL_EXECUTION_PREFIXES ("execute_",)
                              ("run_" prefix intentionally NOT used —
                               false-positive prevention on legit
                               names like "run_id" / "runs_count";
                               run_* forms caught via explicit set)
  _P5_ENGINE_MUTATION_KEYS   11
  _P6_FINAL_REPORT_KEYS      6
  _P7_THRESHOLD_VERDICT_KEYS 4

classification helper:
  _classify_unknown_key(key) → P_id or None
                                order: P1 → P3 → P4 (exact)
                                       → P4 (prefix) → P5 → P6 → P7
```

Cross-check semantics:

```text
S5 (target_claim_id ≠ source_packet claim.id) uses getattr
duck-typing on source_packet["claim"]. If source_packet has no
"claim" key, or "claim" object has no .id, the S5 cross-check
is silently skipped (not a failure mode in itself).

This duck-typing approach is what allows the validator to remain
ragcore-free at runtime — no Claim / Engine import is needed.
```

Each violation message references both the PR55 detect code and the upstream PR54 §10 / PR52 §5 / PR43-C / PR44-D anti-pattern, e.g.:

```text
("P1", "verdict/label/judgment/decision/ruling key not allowed:
        ['verdict'] (PR54 §10 P1 / PR44-D AP-CF-1 / PR52 §5 F10)")
("P5", "engine mutation payload key not allowed:
        ['add_evidence_args']
        (PR54 §10 P5 / PR52 §5 F13 / PR44-D AP-E-1)")
```

## 4. Test invariant summary (195차)

`tests/test_proposal_schema.py` — class TestProposalSchema, 11 test methods, 387 lines.

```text
1.  test_valid_required_only_proposal_returns_no_violations
2.  test_valid_proposal_with_optional_refs_returns_no_violations
3.  test_non_dict_proposal_returns_S1_and_does_not_raise
       covers 5 non-dict inputs: "string", None, [], 42, 3.14
4.  test_missing_required_fields_are_reported_deterministically
       empty dict → all 3 missing in S2 message
       partial dict → 2 missing in S2 message
5.  test_invalid_category_is_rejected
       unknown string + non-string int both trigger S3
6.  test_bool_target_claim_id_is_rejected_even_though_bool_is_int_subclass
       True / False both trigger S4
       (Python's bool subclass of int 함정 잡음)
7.  test_target_claim_id_mismatch_with_source_packet_is_rejected
       mismatch → S5
       empty source_packet → S5 skip
8.  test_forbidden_top_level_keys_are_classified
       38 sub-scenarios across P1/P3/P4/P5/P6/P7:
         P1 — 5 verdict keys
         P3 — 5 status mutation keys
         P4 — 7 exact + 1 "execute_" prefix variant
         P5 — 11 engine mutation keys
         P6 — 6 final report keys
         P7 — 4 threshold verdict keys
9.  test_unknown_random_top_level_key_is_rejected_as_S7
       random unknown alone → S7 (no P_id misclassification)
       random unknown + P_id → both reported
10. test_inputs_are_not_mutated
       proposal identity / keys / values preserved
       packet keys preserved
11. test_validator_remains_ragcore_free
       AST-based static check on examples/proposal/proposal_schema.py
       rejects any ast.Import / ast.ImportFrom whose module
       name starts with "ragcore"
```

Test loading:

```text
both examples/proposal/proposal_schema.py and
examples/inspector/engine_inspector.py loaded via importlib.util
(no sys.path pollution; no examples/__init__.py required)
```

Test-local helpers (NOT exported):

```text
_make_engine_and_packet()  → (engine, claim_id, packet)
_codes(violations)         → list[str] of violation codes
```

## 5. Detect codes coverage matrix

```text
Code   Type         Detection mechanism
─────────────────────────────────────────────────────────────────────
S1     shape        isinstance(proposal, dict)
S2     shape        _REQUIRED_FIELDS - set(proposal.keys())
S3     shape        category in _ALLOWED_CATEGORIES + isinstance str
S4     shape        isinstance(target_claim_id, int) AND not bool
S5     shape        getattr(source_packet.claim, "id") ==
                    target_claim_id  (skipped if no claim)
S6     shape        isinstance(note, str)
S7     shape        unknown top-level key not in _ALLOWED ∪ any P_id
─────────────────────────────────────────────────────────────────────
P1     forbidden    key naming (5 exact)               PR54 §10 P1
P3     forbidden    key naming (5 exact)               PR54 §10 P3
P4     forbidden    key naming (7 exact + "execute_"   PR54 §10 P4
                    prefix)
P5     forbidden    key naming (11 exact)              PR54 §10 P5
P6     forbidden    key naming (6 exact)               PR54 §10 P6
P7     forbidden    key naming (4 exact)               PR54 §10 P7
─────────────────────────────────────────────────────────────────────
TOTAL  13 codes     7 shape + 6 forbidden = 13
```

Out-of-PR55-scope (deferred to PR56 Proposal Safety Validator):

```text
P2   probability translation of effective_confidence
     (semantic / text inference; not pure key naming)
P8   domain vocabulary on ragcore-side identifiers
     (semantic; overlaps with PR53 scope)
```

## 6. Self-review checklist (15/15)

```text
[x] examples/proposal/proposal_schema.py added
[x] tests/test_proposal_schema.py added
[x] pytest 1169 passing
[x] ragcore source change 0 bytes
[x] ragcore import 0
    (validator module ragcore-free at runtime;
     AST-based test 11 enforces this)
[x] new public symbol 0
[x] new Engine behavior 0
[x] Engine method call 0
[x] input mutation 0
    (test 10 asserts proposal identity / keys / values and
     packet keys preserved)
[x] normalize function 0
    (normalize_llm_proposal explicitly OOS per PR55 design)
[x] tool execution authorization 0
    (P4 detect catches authorization structure)
[x] final report verdict generation 0
    (P6 detect catches publication structure)
[x] proposal schema remains consumer-side example
    (lives in examples/proposal/, not in ragcore)
[x] LLMProposal / ProposalSchema / ProposalValidator NOT
    promoted into ragcore
[x] PR56 NOT auto-entered
```

## 7. No-change verification

```text
pytest -q                                1169 passing (1158 + 11 new)
ragcore.__all__                          48 symbols (PR31-S baseline)
unique symbols                           48
Engine public methods                    40 (PR33-M docstring 40/40)
modifier helpers                          6 with (self, claim_id: int) -> float
                                          (PR34-O signature preserved)
serialize/restore symmetry              6 × 6 (PR35-O7 preserved)
snapshot schema_version                   2 (PR21-L preserved)
snapshot top-level keys                  18 (PR36-PKG _LOCKED frozenset)
report shape                              6 frozen key sets (PR32-V)

ragcore source change since PR36-PKG     +66 lines (PR48-A banners only)
                                          PR55 itself contributes 0 lines
                                          to ragcore source
ragcore source cerberus mentions          0 (generic identity preserved)
external package imports in ragcore       0

adapter-specific symbols in ragcore.__all__:  none
ragcore type added in PR55:                    none
ragcore method surface change:                  none
new public symbol:                               0
new engine behavior:                             0
contract §51:                                    not added
runtime enforcement:                             0
adapter implementation:                          not included

PR51 wrapper unchanged:
  examples/inspector/engine_inspector.py  unchanged
  tests/test_external_engine_inspector.py  unchanged
PR53 validator unchanged:
  examples/inspector/packet_validator.py  unchanged
  tests/test_packet_validator.py           unchanged
PR52 / PR54 spec unchanged:
  docs/architecture/LLM_CONTEXT_PACKET_SPEC.md   unchanged
  docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md unchanged

LLMProposal / ProposalSchema / ProposalDraft / ProposalValidator
  in ragcore source:                              0 (NOT promoted)
```

All framework invariants preserved.

## 8. What PR55 closed

```text
- PR54 §10 8 forbidden proposal readings 중 6 개 (P1/P3/P4/P5/P6/P7)
  의 structural top-level key detect 를 executable code 로 구현
- 7 shape error codes (S1~S7) 로 minimal proposal shape 잠금
- 11 invariant test 로 detection coverage 와 ragcore-free 보장 잠금
- validator entry function (validate_llm_proposal_shape) 단일 함수
  pattern 등록 (PR51 / PR53 pattern 일관)
- raise 안 함 / 입력 mutate 안 함 / Engine 호출 0
- ragcore import 0 — duck-typing 으로 source_packet["claim"].id
  cross-check (test 11 AST 검증으로 잠금)
- 각 violation message 가 PR55 code + PR54 §10 P_id + 상위 anti-pattern
  (PR52 §5 / PR44-D AP-*) 모두 cross-reference
- PR54 spec 의 일부가 executable enforceable 로 격상
- PR54 §12 5 must-hold + PR47 §3 / PR49 §5 / PR52 §5 / PR52 §8 /
  PR53 false-positive prevention 모두 honor
```

## 9. What PR55 deliberately did NOT do

PR55 did NOT:

```text
- normalize proposal into an executable object
  (normalize_llm_proposal explicitly OOS)
- walk nested proposal structure
  (top-level keys only; nested forbidden keys would need
   future expansion in PR56 or similar)
- enter semantic / text inference territory
  (P2 / P8 left for PR56 Proposal Safety Validator)
- detect proposals that misuse evidence_strength as probability
  in free text (semantic; P2)
- detect domain vocabulary on ragcore-side identifiers
  (semantic; P8)
- inspect actual LLM response text
- authorize tool execution or any downstream layer
- mutate Engine state or any input
- modify any ragcore source file
- add any public symbol to ragcore.__all__
- introduce LLMProposal / ProposalSchema / ProposalDraft /
  ProposalValidator as a ragcore type
- modify PR51 wrapper / PR53 validator / PR52 spec / PR54 spec
- introduce contract §51
- introduce domain vocabulary
  (cerberus / vulnerability / scanner / exploit / ssh / cve /
   nmap / host / port / service / asset)
- raise exceptions (returns list; caller decides)
- import ragcore at runtime (test 11 enforces)
- auto-schedule any PR56+
```

## 10. Implementation footprint

Changed files (194 + 195 + 196):

```text
examples/proposal/proposal_schema.py                  +396 lines (194차, NEW)
tests/test_proposal_schema.py                         +387 lines (195차, NEW)
docs/dev/PR_055_MINIMAL_LLM_PROPOSAL_SCHEMA_MVP.md    this record (196차)
```

Unchanged:

```text
ragcore/engine.py                                      (no PR55-attributable change)
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
pyproject.toml
README.md
docs/README.md
docs/contracts/05_DATA_CONTRACT_MVP.md                 (no §51 added)
docs/architecture/ENGINE_INTERNAL_MAP.md                (PR47)
docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md   (PR49)
docs/architecture/ENGINE_READ_SURFACE_AUDIT.md          (PR50)
docs/architecture/LLM_CONTEXT_PACKET_SPEC.md           (PR52)
docs/architecture/PROPOSAL_LAYER_BRIDGE_SPEC.md         (PR54)
docs/architecture/EXTERNAL_ADAPTER_COMPATIBILITY_MATRIX.md
docs/guides/*
examples/probe/external_consumer_probe.py              (PR38-A)
examples/inspector/engine_inspector.py                 (PR51, UNCHANGED)
examples/inspector/packet_validator.py                 (PR53, UNCHANGED)
tests/test_external_adapter_simulation.py              (PR41)
tests/test_engine_method_call_playbook_usage.py        (PR43-C 168차)
tests/test_external_engine_inspector.py                (PR51, UNCHANGED)
tests/test_packet_validator.py                          (PR53, UNCHANGED)
all other tests / docs
```

Note on `ragcore.egg-info/`:

```text
ragcore.egg-info/ is an untracked build artifact present at the
PR55 baseline; it was NOT added to any 194/195/196 commit.
It is not part of the PR55 footprint.
```

No ragcore source change. No `ragcore.__all__` change. No method surface change. No snapshot schema change. No report frozenset change. PR51 wrapper / PR53 validator / PR52 spec / PR54 spec all unchanged.

## 11. PR55 cycle

```text
194차  feat(example)  — proposal schema validator     (c00c4ee, +396)
195차  test(example)  — 11 proposal schema invariants  (423583e, +387)
196차  docs(dev)      — PR55 record + ready + squash merge (this commit)
```

Three-차수 cycle (src + test + record), consistent with PR51 / PR53 pattern.

## 12. Pattern position recap

```text
PR39    compatibility audit                documentation-only
PR40    adapter policy guide               documentation-only
PR41    external adapter simulation        tests-only
PR42    retrieval translation guide        documentation-only
PR43-C  engine method call playbook        guide + tests
PR44-D  integration anti-patterns          documentation-only
PR45-E  domain-neutral reference flow      documentation-only
PR46-B  documentation map / reader entry   documentation-only
PR47    frozen engine internal refactor    documentation-only (audit)
            audit
PR48-A  engine section banners              src (comment-only)
PR49    engine read surface thaw policy    documentation-only (policy)
PR50    engine read surface audit          documentation-only (audit)
PR51    minimal claim read query MVP       examples + tests
PR52    LLM context packet spec            documentation-only (spec)
PR53    consumer packet validator MVP      examples + tests
PR54    proposal layer bridge spec         documentation-only (spec)
PR55    minimal LLM proposal schema MVP    examples + tests (this)

All seventeen (post-PR36-PKG):
  framework method surface frozen          ✓
  public observable behavior preserved      ✓
  no automatic next PR                      ✓
```

## 13. PR49 ~ PR55 layered stack (updated)

```text
PR49 — Engine Read Surface Thaw Policy
PR50 — Engine Read Surface Audit (Conclusion A)
PR51 — Minimal Claim Read Query MVP (wrapper + 6 invariant tests)
PR52 — LLM Context Packet Spec
PR53 — Consumer Packet Validator MVP (validator + 7 invariant tests)
PR54 — Proposal Layer Bridge Spec
PR55 — Minimal LLM Proposal Schema MVP (validator + 11 invariant tests, this)

stack:
  policy (PR49) → audit (PR50)
                → executable wrapper + tests (PR51)
                → consumer-side packet spec (PR52)
                → consumer-side packet validator + tests (PR53)
                → proposal layer bridge spec (PR54)
                → consumer-side proposal schema validator + tests (PR55, this)
                → [PR56 proposal safety validator — NOT entered]
```

PR55 is the second executable enforcement layer (after PR53). PR53 enforces packet consumption boundary; PR55 enforces proposal shape boundary. Both ragcore-free; both raise-free; both validation-only.

## 14. Followup — PR56 (NOT auto-scheduled)

```text
PR56 — Proposal Safety Validator
       type:   consumer-side example or doc-only (separately decided)
       scope:  cover the remaining forbidden readings deferred
               by PR55:
                 P2   probability translation of effective_confidence
                 P8   domain vocabulary on ragcore-side identifiers
               plus optionally:
                 - nested-structure walker
                 - semantic / phrasing detection
                 - LLM prompt template lint
       requires (PR54 §12 entry conditions, ALL must hold):
         1. PR56 must not modify ragcore source
         2. PR56 must not add ragcore public symbols
         3. PR56 must not turn proposals into Engine judgments
         4. PR56 must not authorize tool execution
         5. PR56 must keep human / operator decision as final
            boundary
       additional honor:
         - PR47 §3 do-not-touch boundary
         - PR49 §5 read-only definition
         - PR52 §5 forbidden readings (F1 ~ F13)
         - PR52 §8 ragcore symbol boundary
         - PR53 false-positive prevention philosophy

Alternative directions (also NOT auto-scheduled):
  - extend PR53 packet validator coverage to additional F_ids
  - extend PR55 proposal schema with nested-key check
  - Cerberus-side adapter implementation (separate repo)
  - human / operator UI / approval mechanism spec
  - stop here and let the framework wait
```

PR55 explicitly does not schedule any of the above. Each requires explicit user decision.

## 15. Framework state (post-PR55)

```text
ragcore baseline:
  main:    5141da8 (pre-merge; new hash after squash merge)
  1169 tests passing (1158 + 11 new from this PR)
  48 public symbols
  40 public methods
  10 layered §-boundaries (§39 ~ §50)
  3 architecture audits
    - compatibility matrix (PR39)
    - engine internal map (PR47)
    - engine read surface audit (PR50)
  3 architecture policy / spec
    - engine read surface thaw policy (PR49)
    - LLM context packet spec (PR52)
    - proposal layer bridge spec (PR54)
  5 adapter guides
  1 documentation map / reader entry point
  4 external examples
    - examples/probe/external_consumer_probe.py     (PR38-A)
    - examples/inspector/engine_inspector.py        (PR51)
    - examples/inspector/packet_validator.py        (PR53)
    - examples/proposal/proposal_schema.py          (PR55 — this)
  5 executable simulation / usage / validator test suites
    - test_external_adapter_simulation.py           (PR41, 18 tests)
    - test_engine_method_call_playbook_usage.py     (PR43-C 168차, 12 tests)
    - test_external_engine_inspector.py             (PR51 185차, 6 tests)
    - test_packet_validator.py                       (PR53 190차, 7 tests)
    - test_proposal_schema.py                        (PR55 195차, 11 tests)
  1 behavior-preserving refactor commit on engine.py
    (PR48-A comment-only banners)

PR49 ~ PR55 layered stack status:
  judgment semantics                         frozen ✓
  read surface policy                        defined ✓ (PR49)
  read surface audit                         complete ✓ (PR50)
  executable wrapper + invariant lock        complete ✓ (PR51)
  consumer-side packet spec                  complete ✓ (PR52)
  consumer-side packet validator + tests     complete ✓ (PR53)
  proposal layer bridge spec                 complete ✓ (PR54)
  consumer-side proposal schema + tests      complete ✓ (PR55, this)
  PR56 proposal safety validator             NOT entered

ragcore source change since PR36-PKG:  +66 lines (PR48-A banners only)
ragcore source cerberus mentions:       0 (generic identity preserved)

NEXT AUTOMATIC PR: NONE
```

## 16. Closing meaning

```text
PR55 locks the minimal consumer-side shape of LLM proposal drafts.

The validator detects invalid or unsafe top-level proposal
structure. It does not judge claims, execute tools, or mutate
Engine state.

PR56, if entered, may focus on proposal safety interpretation
(P2 / P8) and nested-structure walking. It is not entered
automatically.
```

Locked closing sentences:

```text
PR55 locks the minimal consumer-side shape of LLM proposal drafts.

It validates structure, not truth or execution authority.

LLMProposal / ProposalSchema / ProposalDraft / ProposalValidator
remain NOT ragcore symbols.

PR56 (semantic safety validator covering P2 / P8) is NOT
automatically entered.
```

No automatic next-PR proposal. User decides direction.
