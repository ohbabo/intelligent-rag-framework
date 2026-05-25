# Engine Read Surface Thaw Policy

Status: policy document (PR49)
Baseline: main `96fd0df` (PR48-A merged)
Type: doc-only policy, no source change, no test change, no public symbol change

## 0. Scope limitation (locked, user 2026-05-25)

```text
PR49 is not a thaw implementation PR.
PR49 is the policy that defines how read surface may be thawed
later without thawing Engine judgment semantics.
```

한국어:

```text
PR49 는 해제 구현 PR 이 아니다.
PR49 는 Engine 판단 의미를 풀지 않으면서, 읽기 표면만 나중에
안전하게 열 수 있는 기준을 잠그는 정책 PR 이다.
```

PR49 is the first PR in the PR49-PR52 read-surface roadmap. It only writes the policy; it does not add a read method, define a packet, or modify any source file in `ragcore/`.

---

## 1. Core Statement

```text
We thaw the read surface, not the judgment semantics.

우리는 판단 의미를 푸는 것이 아니라, 읽기 표면만 푼다.
```

This is the single sentence that governs every PR in the PR49-PR52 sequence. Each subsequent PR (policy → audit → minimal read query → context packet spec) must be readable as an expression of this sentence.

---

## 2. Why This Policy Exists

Through PR36-PKG (method surface freeze) and PR47 (frozen engine internal refactor audit), the word "freeze" had been used in two different senses without a written distinction:

```text
Sense A — judgment semantics freeze
  Engine 의 lifecycle / effective_confidence / modifier / contradiction /
  snapshot semantics 는 변경 금지.

Sense B — total Engine freeze
  Engine 자체에 어떤 추가도 영구 금지 (해석 가능)
```

PR48-A already disproved a strict reading of Sense B by demonstrating that a behavior-preserving comment-only change is compatible with "freeze" (AST equivalence True). PR49 makes the distinction explicit and durable.

```text
freeze 가 의미하는 것:
  judgment semantics freeze (Sense A) 만이다.

freeze 가 의미하지 않는 것:
  read-only inspection 까지 영구히 막는 freeze (Sense B) 가 아니다.
```

This policy does not authorize any source change. It only documents the allowed boundary of future read-only work.

---

## 3. Frozen Judgment Semantics

The following remain frozen and are NOT touched by any PR in the PR49-PR52 sequence:

```text
1.  Lifecycle transition rules
    (6 *_if_ready helpers; PR6 ~ PR10, PR15)

2.  effective_confidence formula
    (7-modifier composition: base × status × freshness × gap ×
     count × rule_stats × evidence_type; PR12 ~ PR21, PR23, PR24,
     PR26, PR29, PR34-O §46, PR36-PKG §48.7)

3.  Modifier meaning, order, and saturation behavior
    (6 private *_modifier_for_claim helpers; PR34-O signatures)

4.  Contradiction / refutation semantics
    (register_contradiction / register_contradiction_resolution /
     dispute / refute / refute_disputed / refute_disputed_by_freshness)

5.  Snapshot schema_version (2) and the 18 top-level snapshot keys
    (PR21-L / PR36-PKG _LOCKED_SNAPSHOT_TOP_LEVEL_KEYS)

6.  to_snapshot / from_snapshot serialize-restore symmetry
    (PR35-O7, 6 × 6)

7.  Domain-neutral judgment boundary
    (§50 External Knowledge Adapter Boundary; no domain vocabulary
     enters ragcore source)

8.  40 public method signatures and their public observable behavior
    (PR33-M 40/40; PR36-PKG _LOCKED_PUBLIC_METHODS)

9.  48 ragcore.__all__ symbols
    (PR31-S; PR36-PKG _LOCKED frozensets)

10. 6 frozen report / read-surface key sets
    (PR32-V)
```

These ten items are the same do-not-touch boundary recorded in PR47 audit § 3. PR49 re-asserts them so the boundary is referenced from both the internal refactor audit and the read-surface policy.

---

## 4. Thawed Read Surface

Subject to PR49 policy, the *read surface* of the Engine may be opened in a controlled sequence. "Read surface" means the ability to inspect Engine state without mutating it. Areas potentially openable:

```text
- claim summary (current status, base_confidence, effective_confidence)
- supporting evidence summaries (id, type, strength, freshness)
- unresolved gaps (id, type, required_evidence_type, severity)
- active and resolved contradictions
- claim lifecycle history (PR10-B §23 audit trail)
- rule binding (rule_id / rule_version) and rule maturity context
```

Opening any of the above is NOT authorized by PR49 itself. PR49 only defines the criteria. The actual opening, if any, happens under PR50 audit + PR51 minimal claim read query + PR52 LLM context packet spec — each separately gated.

Even when thawed, the read surface stays under the read-only definition in § 5.

---

## 5. Read-only Definition

A change is "read-only" only if all of the following hold:

```text
- no state mutation
    (no add_entity / add_observation / add_claim / add_evidence /
     add_gap / add_relation / register_contradiction* invoked
     internally)

- no lifecycle transition
    (no confirm_claim_if_ready / refute_claim_if_ready /
     dispute_claim_if_ready / resolve_disputed_claim_if_ready /
     refute_disputed_claim_if_ready[_by_freshness] invoked
     internally)

- no recomputation that produces a different value for the same
  Engine state
    (compute_effective_confidence is read-only by definition; any
     thawed read method must not bypass or shortcut its formula)

- no schema migration
    (Engine.from_snapshot remains the only entry that may run
     _migrate_snapshot_* helpers)

- no new judgment creation
    (no derived "summary verdict" / "risk score" / "vulnerability
     probability" / "policy decision" produced by the read method
     itself; the read method may only assemble fields the Engine
     already owns)

- no domain vocabulary injected
    (PR44-D AP-X-6 — read methods must remain domain-neutral)
```

If any of these conditions is not met, the change is no longer read-only and falls under judgment semantics — PR49 does NOT authorize it.

---

## 6. LLM / Consumer Boundary

```text
LLM 은 Engine 을 조사할 수 있다.
LLM 은 Engine judgment semantics 를 대체하지 않는다.

LLM 의 출력은 proposal 이다.
proposal 은 Validator 와 Adapter 를 통과한 뒤에만 Engine public
API 로 commit 된다.
```

PR49 inherits the layering from `direction_rag_framework_proposal_layer.md`:

```text
Engine Context Packet (Cerberus-side read model)
  ← built from Engine public read methods only
  → fed to LLM Proposal Core

LLM Proposal Core (Cerberus-side)
  → emits proposals (claim / evidence / gap / contradiction / tool)

Proposal Validator (Cerberus-side)
  → hallucination filter; rejects no-evidence-binding proposals

Adapter Translation Policy (Cerberus-side)
  → maps validated proposals to Engine public method calls

Engine public API
  → records state; computes effective_confidence; transitions
    lifecycle; persists snapshot
```

PR49 does NOT specify any of the Cerberus-side layers. It only states that the Engine read surface may be opened *for* those layers, under the conditions of § 5.

---

## 7. PR49 ~ PR52 Roadmap

```text
PR49 — Engine Read Surface Thaw Policy            (this PR)
       type: doc-only policy
       file: docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md
       source change: 0
       test change: 0

PR50 — Engine Read Surface Audit
       type: doc-only audit
       scope: which existing public methods already satisfy the
              § 5 read-only definition; which gaps remain;
              whether any minimal new read method is justified
       source change: 0 expected
       test change: 0 expected

PR51 — Minimal Claim Read Query MVP
       type: MVP (Cerberus-side EngineInspector wrapper preferred)
       scope: smallest read query that lets a consumer assemble
              an Engine Context Packet
       1순위: Cerberus-side / external consumer-side wrapper
              (ragcore source change 0)
       2순위: ragcore public read method addition
              — only if PR50 audit concludes that the existing
                40 public methods cannot assemble the minimal
                packet
              — requires separate user lock before entry
       test change: depends on choice (1순위 0, 2순위 일부)

PR52 — LLM Context Packet Spec
       type: doc-only spec
       location: Cerberus-side spec (per direction_rag_framework_proposal_layer §10)
                 NOT a ragcore public symbol; NOT in ragcore.__all__
       source change: 0
       test change: 0
```

Each PR in the sequence is independent. Entering PRn does NOT auto-schedule PRn+1.

---

## 8. PR51 Guard

```text
Default: external EngineInspector (Cerberus-side or external
         consumer wrapper)

ragcore public method addition is allowed only if:
  (a) PR50 audit explicitly concludes the existing 40 public
      methods cannot assemble the minimal Engine Context Packet
      under the § 5 read-only definition; AND
  (b) the user issues a separate lock authorizing the addition; AND
  (c) the addition honors all of:
      - PR47 § 3 do-not-touch boundary (10 items)
      - PR47 § 12 entry conditions (5 must-hold)
      - § 5 read-only definition (this document)
      - PR44-D anti-patterns
        (especially AP-X-7 __all__ promotion warning)
```

If any of (a) / (b) / (c) is not met, PR51 stays at 1순위 (external wrapper). The default is "do not touch ragcore source."

---

## 9. Out of Scope (PR49)

PR49 does NOT do any of the following. Each is an explicit OOS lock:

```text
- ragcore/engine.py 변경
- ragcore/types.py 변경
- ragcore/__init__.py 변경
- ragcore/rule_output.py 변경
- ragcore.__all__ 변경
- Engine public method 추가
- snapshot schema_version 변경
- lifecycle transition 변경
- effective_confidence formula 변경
- modifier value / modifier order / modifier saturation 변경
- LLMContextPacket / RAGContext / ToolPlan / EngineContextPacket /
  LLMProposal 류 public symbol 추가
- 외부 LLM 판단 엔진 설계
- contract §51 신설 (read surface policy 는 architecture doc 으로 둠)
- PR50 / PR51 / PR52 자동 진입
- test 추가
- runtime enforcement 추가
- adapter 구현
- 도메인 어휘 (cerberus / vulnerability / scanner / SSH / CVE /
  nmap / host / port / service / asset) 도입
```

---

## 10. Exit Criteria

PR49 closes when ALL of the following hold:

```text
[ ] docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md added
[ ] pytest 1145 passing (unchanged from PR48-A baseline)
[ ] ragcore.__all__ 48 symbols (unchanged)
[ ] Engine public methods 40 (unchanged)
[ ] snapshot schema_version 2 (unchanged)
[ ] snapshot top-level keys 18 (unchanged)
[ ] ragcore source change 0 bytes
[ ] test change 0
[ ] new public symbol 0
[ ] new engine behavior 0
[ ] contract §51 not added
[ ] PR50 / PR51 / PR52 not auto-scheduled
```

PR49 's job is to write the policy and close. It does not perform any thaw.

---

## 11. Closing meaning

```text
PR49 is not a thaw implementation PR.

PR49 distinguishes:
  - judgment semantics freeze  → remains permanent
  - read surface                → may be thawed only under § 5
                                  read-only definition

PR49 names the boundary so that PR50 audit, PR51 minimal read
query, and PR52 context packet spec each have a written reference
to honor.

Policy drawn.
Source unchanged.
Framework waits.
```

Locked closing sentences:

```text
We thaw the read surface, not the judgment semantics.

우리는 판단 의미를 푸는 것이 아니라, 읽기 표면만 푼다.

PR49 is the policy that defines how read surface may be thawed
later without thawing Engine judgment semantics.

PR50 / PR51 / PR52 are NOT automatically entered.
```
