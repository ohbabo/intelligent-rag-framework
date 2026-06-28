# PR_096 — Phase 5: Repository Documentation & PR-History Reconciliation (development record)

GitHub PR **#97** (internal dev-record number = GitHub number − 1 = 096).

## 1. Identity / scope
Documentation + GitHub-PR-body reconciliation only. No new feature. Two parts in
one Draft PR: **5A** brings the two public entry-point READMEs to the current
post-Phase-4 state; **5B** appends a single uniform "Phase 5 — Canonical final
status" card to every merged PR #74~#96 (except the nonexistent #80), without
rewriting any historical body. No ragcore / tests / examples / pyproject / contract
/ architecture / guide change. Version stays `0.1.0` (matches pyproject).

## 2. Baseline
```
main                d14c0892ce16f5dd25795bcf947fd1bbaad9cf6f
Phase 4 PR          #96 — MERGED (mergedAt 2026-06-28T11:30:14Z; mergeCommit d14c089)
baseline tests      2204 passed (local; no CI / GitHub Actions)
public 42 / __all__ 50 / snapshot 2·18 / packet 7 / pyproject version 0.1.0
HEAD == d14c089, working tree clean, main == origin/main (0 divergence) — all verified
```

## 3. Root README stale-state audit (README.md)
```
A current-facing (corrected):
  "Method surface frozen (PR36-PKG §48)" / "Integration readiness ... D-mid completion in progress"
  -> Project Status replaced with the current baseline (v1 COMPLETE; 42/50/2·18/packet 7; v2 NOT STARTED)
  "Allowed to evolve: modifier strength/composition/threshold ... add additively"
  -> "may change only through an explicit, versioned judgment-policy update" (v1 policy fixed)
  Documentation Map "PR_001 ~ PR_037" -> docs/dev/ described as the growing history/audit area
Additions:
  "Current Architecture (Engine v1)" summary + "Start here" path + "Current Roadmap" (links FINAL_BOUNDARY)
Preserved: Core Thesis / Origin / What / RAG Model / Design Principles / Quickstart /
  Persistence Boundary / version 0.1.0.
```

## 4. docs/README.md stale-state audit
```
A current-facing (corrected):
  header "documentation map (PR46-B)" + "Baseline: main 1d11077 (PR45-E)"  -> current map header
  §0 baseline 1d11077 / 1145 / 40 / 48 / "contract §51 not added"  -> d14c089 / 2204 / 42 / 50 /
       snapshot 2·18 / packet 7 / thin-core+9-mixins (old numbers kept as an explicit historical note)
  §1 "40 methods / 48 __all__" -> 42 / 50
  §4 B.5 engine source surface (single engine.py) -> thin C1 core + 9 mixins + 2 kernels
  §5 C.4 "48 __all__ / 40 public" -> 50 / 42 (+ FINAL_BOUNDARY)
  §8 "40 public methods / 48 __all__ / beyond the 40" -> 42 / 50 / beyond the 42
  §10 PR46-era "Option 1–5" -> current roadmap (v2 + Cerberus NOT STARTED)
  A.6 Playbook "40 public methods" -> count dropped (guide is class-B, not edited; §0 carries 42)
Additions: §0a document taxonomy (A current-authoritative / B consumer guides / C historical / D future).
Preserved: §2/§3/§4/§5 reader paths, §6 10-layer stack, §7 triad, §9 hard-stop rules.
```

## 5. Document taxonomy (recorded in docs/README §0a)
```
A. Current authoritative   README · docs/README · 05_DATA_CONTRACT_MVP ·
                           ENGINE_V1_FINAL_BOUNDARY · REFACTORING_PLAN · PHASE3A ADR
B. Consumer guides         docs/guides/** (10-layer adapter stack)
C. Historical / audit      docs/dev/** · docs/archive/** · superseded docs (ENGINE_INTERNAL_MAP)
D. Future / not started    Engine v2 · Cerberus integration · production consumer adapter
```

## 6. Tracked files changed (Phase 5)
```
README.md
docs/README.md
docs/dev/PR_096_PHASE5_DOCUMENTATION_RECONCILIATION.md  (this record)
0 changes under ragcore/ tests/ examples/ pyproject.toml docs/contracts/ docs/architecture/ docs/guides/
```

## 7. Link validation
Both READMEs' relative links / `docs/...` references all resolve (verified by a
throwaway script, not committed). No link to a nonexistent file or PR.

## 8. PR #74~#96 body reconciliation (5B)
Method: **append-only**. Each merged PR keeps its existing body, headings,
review/correction history, and any existing closure/reconstruction section
byte-for-byte. A single uniform card is appended exactly once. The historical body
becomes a byte-prefix of the new body. `#80` does not exist (N/A). The four
historical body templates and the ~4.7× size spread (3,540–16,671 chars) are
**intentionally left** — this normalizes the *current-status surface*, not the
historical bodies.

### Appended section heading (identical on all 22)
`## Phase 5 — Canonical final status`  + the historical-language disclaimer line.
Only the `current reading:` field varies per PR.

### Metadata matrix (mechanically verified) + before-hashes
```
PR   state   head(full prefix)  squash(merge)   mergedAt(UTC Z)        cmts files  +add  -del  beforeSHA256(12)  existingClosure
#74  MERGED  c3cf7dc327          04f591b14b      2026-06-19T00:18:04Z   6    15     2889   30   3b7e01073313       no
#75  MERGED  b7d57d42de          80759048e9      2026-06-19T03:02:41Z   4     6     2037    0   3b7c89edd0be       yes
#76  MERGED  4c21518f04          9f576a5b07      2026-06-19T05:51:12Z   4     6     2490    0   0777d6b7e0a2       yes
#77  MERGED  0fbc80bbb3          f57cd5da1f      2026-06-24T10:11:47Z   8    16     4364   30   ecf2453d88ce       yes
#78  MERGED  b2c0524d70          31e0210998      2026-06-25T01:21:58Z  13     4     6992    0   d90f4384475a       yes
#79  MERGED  9e53ad17aa          6d43cd8959      2026-06-25T11:34:04Z   7     4     2796    0   31e9e8001a7e       yes
#80  ABSENT — no such PR (N/A; skipped)
#81  MERGED  c17b833695          aaa8024210      2026-06-27T07:35:17Z  23    26     2450  264   bf2063362ee7       yes
#82  MERGED  0647139b60          dc942a1d9c      2026-06-27T07:59:26Z   1     1      370    0   5ad7f3ddee0a       yes
#83  MERGED  72f6ca4406          0c27ad3f81      2026-06-27T08:44:44Z   2     3      346  100   2d753cf226ca       yes
#84  MERGED  8ee18afbea          88edc18dfd      2026-06-27T10:35:35Z   3     8     1010  802   c0240a6a4ff2       yes
#85  MERGED  d59f3e68c4          6f4f8e06c3      2026-06-27T12:15:46Z   6    10      809  530   c018365acfb4       yes
#86  MERGED  9e97c798aa          65ee71b207      2026-06-28T00:12:55Z   8     4      911    0   2c65d276a299       yes
#87  MERGED  61c75a1d99          3526c39ef1      2026-06-28T01:40:19Z   3     4      375  107   e597f54caf16       yes
#88  MERGED  84137c035f          3d7f3e8b73      2026-06-28T02:19:16Z   3     4      324   54   db01842ebc84       yes
#89  MERGED  ddd232dfb1          275676bd2a      2026-06-28T03:27:46Z   3     4      416   97   5529937a8bfd       yes
#90  MERGED  7d13ad0721          69a8838822      2026-06-28T04:45:03Z   4     4      507  128   859b36437a20       yes
#91  MERGED  757de63f2a          1fedf50e6a      2026-06-28T06:20:59Z   7     6      738  287   a57aaf7993e1       yes
#92  MERGED  0c81b9e9af          628fc68afa      2026-06-28T07:28:48Z   5     4      443   46   bebf10340a1f       yes
#93  MERGED  f973375b7c          acb041b844      2026-06-28T08:31:23Z   4     5      799  187   4ac75a2d332b       yes
#94  MERGED  0fb1045206          5ac28babb8      2026-06-28T09:42:15Z   4     4     1139  405   dae798790570       yes
#95  MERGED  76f4aa5ead          1e89a428ee      2026-06-28T10:30:35Z   3     4      835   93   1965d19c48e0       yes
#96  MERGED  2b0a19c9d7          d14c0892ce      2026-06-28T11:30:14Z   5     9      759   67   75cc6170797b       yes
```
(Full 40-char head/squash SHAs are written into each card.) The card is appended to
**all 22**; #74 is the only PR with no prior closure section, so its card's
`current reading` carries the status. No body is rewritten; no existing closure is
duplicated in detail.

### Per-PR `current reading` (the only varying field)
```
#74  PR73-M04 (state-identity primitive) CLOSED; later M05–M09 audit work was handled in subsequent PRs.
#75  Operator-decision revalidation contract (docs) CLOSED; current structure authority is ENGINE_V1_FINAL_BOUNDARY.md.
#76  Downstream re-entry contract (docs) CLOSED; current structure authority is ENGINE_V1_FINAL_BOUNDARY.md.
#77  Effective-confidence trace feature CLOSED; preserved in the current Engine (C9 confidence adapters).
#78  Domain-neutral reference-operation example CLOSED; still present and exercised by the suite.
#79  RuleStats update-provenance example CLOSED; still present and exercised by the suite.
#81  P/M post-merge audit reconciliation CLOSED; the audited engine was then refactored in Phases 0–4 with 0 contract change.
#82  Refactoring plan ACCEPTED and implemented across Phases 0–4 (all CLOSED); the plan doc is now marked COMPLETE.
#83  Phase 0 CLOSED; the later Engine v1 phases (1–4) subsequently completed.
#84  Phase 1 CLOSED; the later Engine v1 phases (2–4) subsequently completed.
#85  Phase 2 CLOSED; the later Engine v1 phases (3A–4) subsequently completed.
#86  Phase 3A ACCEPTED AND IMPLEMENTED; Phase 3B (#87–#95) implemented it and Phase 4 closed v1.
#87  Phase 3B-1 CLOSED; the full Phase 3B series (#87–#95) and Phase 4 subsequently completed.
#88  Phase 3B-2 CLOSED; the full Phase 3B series and Phase 4 subsequently completed.
#89  Phase 3B-3 CLOSED; the full Phase 3B series and Phase 4 subsequently completed.
#90  Phase 3B-4 CLOSED; the full Phase 3B series and Phase 4 subsequently completed.
#91  Phase 3B-5 CLOSED; the full Phase 3B series and Phase 4 subsequently completed.
#92  Phase 3B-6 CLOSED; the full Phase 3B series and Phase 4 subsequently completed.
#93  Phase 3B-7 CLOSED; the "Phase 3B-8 prohibited" note is historical pre-merge gating; 3B-8/3B-9 and Phase 4 subsequently completed.
#94  Phase 3B-8 CLOSED; Phase 3B-9 and Phase 4 subsequently completed.
#95  Phase 3B-9 and Phase 3B CLOSED; Phase 4 later completed in PR #96.
#96  Engine v1 refactoring COMPLETE; Phase 4 CLOSED; Engine v2 NOT STARTED.
```

### Application status (this commit)
**Before application.** At this commit the 22 cards are NOT yet applied; the
before-hashes above are the live remote bodies. The applied confirmation + each
PR's after-SHA-256 (and the byte-prefix verification) are recorded in the
follow-up commit (chronology intentionally not collapsed).

### 8a. Application result (follow-up commit)
All 22 cards applied (body-only edit; no title/state/base/merge mutation).
**Append-only proof:** for every PR the new remote body `.startswith(old body)` is
True and the card heading appears exactly once (independently re-verified: 22/22;
each body ends with the disclaimer line). The card was appended to all 22; #74 (the
only PR without a prior closure section) carries its status in the card's
`current reading`.

Hash note: the §8 matrix before-hashes were computed over the `gh pr view --json
body --jq .body > file` **backup files**, which carry a trailing newline from the
shell redirect; the pairs below are SHA-256 of the **raw JSON body string** (the
exact value the new body extends), so they are self-consistent before→after and
differ from the §8 column by that one trailing byte. The authoritative append-only
guarantee is the byte-prefix check, not hash equality.
```
PR   before(raw body, 12)  ->  after(raw body, 12)   prefix card×1
#74  8198a692915a          ->  99eaa11badfa          OK    1
#75  ab594e60be19          ->  54d3c7a9875b          OK    1
#76  6ecaceabc3ca          ->  63542e3c020e          OK    1
#77  8c2258e1d93c          ->  acf0be495dba          OK    1
#78  722a0cbc75ae          ->  58002e990316          OK    1
#79  85f3e2c714e0          ->  6d891c7800eb          OK    1
#81  1b98f324a25d          ->  0dc8a691454e          OK    1
#82  13857621be6d          ->  968e1bcc4a2b          OK    1
#83  ef62294578c7          ->  16a2a89a300e          OK    1
#84  748c5728b12d          ->  8d00c4f8df82          OK    1
#85  4ed112e16529          ->  58e854853cee          OK    1
#86  6e9e4db00cfa          ->  4547c6dcc18f          OK    1
#87  bf3168cbba86          ->  d494ee198df3          OK    1
#88  a412583e4be2          ->  5014cbfb78b1          OK    1
#89  4961cb4cd456          ->  0bfb608471e0          OK    1
#90  ee012115747d          ->  129b7bd9e2eb          OK    1
#91  a4f714b9405c          ->  41ab3373ee2f          OK    1
#92  03e4eb0124ad          ->  ce01d5daa5b2          OK    1
#93  15cff756a8dc          ->  7a4dca65499a          OK    1
#94  5d41dbbb42ca          ->  826e3ddd39ee          OK    1
#95  649d26f5d2f9          ->  63417cd5fea8          OK    1
#96  e0eeadd16f60          ->  2f7f42501469          OK    1
```
Updated PR list (22): #74 #75 #76 #77 #78 #79 #81 #82 #83 #84 #85 #86 #87 #88 #89
#90 #91 #92 #93 #94 #95 #96. NO-OP list: none (the user-chosen approach applies the
card to all). #80: absent (N/A).

## 9. STOP conditions checked (none triggered)
base SHA / baseline 2204 match; every README claim verified against code/metadata;
no current-authoritative docs conflict; no historical text required deletion; all 22
bodies backed up (before-hashes above); #80 confirmed absent; no PR already had the
card (idempotent); no runtime/test/pyproject change; version 0.1.0 kept;
v2 + Cerberus integration recorded as NOT STARTED.

## 10. Full suite
`python -m pytest -q` → **2204 passed** (docs-only; runtime/public/snapshot/packet
delta 0).

## 11. Current negative boundary
```
Engine v1 refactoring   COMPLETE (Phase 0–4 CLOSED)
Engine v2               NOT STARTED — separate GPT + user directive
Cerberus integration    NOT STARTED — later roadmap
```

## Commit chronology
```
861118b  docs: reconcile repository entry points (README.md + docs/README.md)        [5A]
e5ff8c3  docs(audit): record Phase 5 document + PR-body inventory (before-hashes)     [5B plan]
<this>   docs(audit): record applied PR-body reconciliations (after-hashes + verify)  [5B result]
```
The 22 PR-body cards were applied between e5ff8c3 and this commit (GitHub body-only
edits, not git commits). This record does not self-pin the SHA of the commit that
adds it. No commit amended / rebased /
force-pushed; PR bodies edited body-only (no title/state/base/merge mutation).

## Lifecycle
OPEN — Draft. Recommendation on completion: **READY FOR GPT INDEPENDENT REVIEW**
(not self-merged). This Phase makes the current state discoverable and the merged
PR histories self-consistent at the surface; it starts no implementation.
**Engine v2 NOT STARTED; Cerberus integration NOT STARTED.**
