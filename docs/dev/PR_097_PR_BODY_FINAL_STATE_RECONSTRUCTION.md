# PR_097 — Phase 5B-R1: PR #74–#96 Final-State Body Reconstruction (development record)

GitHub PR **#98** (internal dev-record number = GitHub number − 1 = 097). If the actual
GitHub number differs, this filename is adjusted to match the established rule.

## 1. Identity / scope
A corrective pass over the GitHub PR **bodies** of #74–#96 (#80 absent). Phase 5B had
appended a canonical-status *card* but kept each historical Draft body verbatim, so the
PR bodies still opened with stale "Draft / not for merge" language and showed the final
state only in a bottom card (sometimes with duplicate closure blocks). This pass
**rewrites each body final-state-first**. GitHub PR-body metadata only — `runtime / git
production / test / public contract / v2 / Cerberus` change all 0. The single git change
is this audit record.

## 2. Baseline
```
main             95d08268c68f8df03ff40d8f321edb0f175af744
Phase 5 PR       #97 MERGED (head 51f3a8969…); Engine v1 COMPLETE
full suite       2204 passed (local; no CI)
Engine v2 / Cerberus integration : NOT STARTED
```

## 3. Why Phase 5B's append-only approach was insufficient
Phase 5B preserved each body byte-for-byte and appended a card. Result: the body's first
screen still read as a pre-merge Draft, several PRs carried 2–3 closure blocks
("Post-merge audit reconstruction" + "Final merge closure" + the card) repeating the same
merge facts, and the current status was only discoverable at the bottom. This pass adopts a
**final-state-first** body: a single `## Final status` block at the top, then Summary /
Delivered / Final verified result / Review findings and corrections / Files changed /
Current project context, with the pre-merge commit/review chronology folded into a bottom
`<details>`. Each PR's own final test/surface numbers are preserved (NOT overwritten with the
current 2204).

## 4. Target body structure (applied)
`## Final status` (state, final head, squash SHA, merged-at UTC, commits, files +A/-D) →
`## Summary` → `## Delivered` → `## Final verified result (at this PR)` → `## Review findings
and corrections` (table) → `## Files changed` → `## Current project context` →
`<details>Historical branch chronology (pre-merge)</details>`. Merge facts appear exactly
once; no canonical card; no duplicate closure; Draft/OPEN/NOT-MERGED language only inside the
historical `<details>`.

## 5. PR → authoritative source map (for the reconstructed text)
Each body's facts are taken from GitHub PR metadata (state / mergeCommit / mergedAt / commits
/ changedFiles / additions / deletions) + the repository dev records. No fact is invented; the
per-PR final test/surface counts come from the PR's own merged dev record.

## 6. Batch plan
- **Batch 1 (this commit, applied + reported for format approval):** #74 (runtime feature) ·
  #75 (docs contract) · #77 (large reviewed feature) · #87 (refactor cluster) · #96 (closure) —
  one representative of each type.
- **Batch 2 (after Batch-1 format approval):** #76 #78 #79 #81 #82 #83 #84 #85 #86 #88 #89 #90
  #91 #92 #93 #94 #95.
- **#80:** absent (N/A).

## 7. Batch 1 result (applied)
Metadata mutation 0 (state MERGED + mergeCommit + title unchanged for all 5). Each body:
final-status-top ✓ / MERGED in first 40 lines ✓ / no canonical card ✓ / no duplicate
closure ✓ / merge facts once ✓ / no Draft language outside `<details>` ✓.
```
PR   type             before→after lines   removed duplicate blocks
#74  runtime feature  136 → 76             (test-plan checklist + C/R correction lists condensed to a table)
#75  docs contract    199 → 64             Post-merge audit reconstruction + canonical card → one Final status
#77  large feature    233 → 72             Post-merge audit reconstruction + canonical card → one Final status
#87  refactor cluster 142 → 64             Final merge closure + Lifecycle + canonical card → one Final status
#96  closure          83 → 71              Review-posture(Draft) + canonical card → one Final status
```

### Batch 1 body SHA-256 (before → after, raw GitHub body)
```
#74  (before backup 99eaa11badfa)  → after recorded in Batch-2 follow-up after format approval
#75  (before backup 54d3c7a9875b)  → "
#77  (before backup acf0be495dba)  → "
#87  (before backup d494ee198df3)  → "
#96  (before backup 2f7f42501469)  → "
```
(Before-hashes are the Phase-5B post-card bodies in /tmp/phase5b-r1-before; per-PR after-hashes
+ the full Batch-2 matrix are recorded in the follow-up commit so the chronology is not
collapsed.)

## 8. Preserved unique facts (not deleted, only relocated/condensed)
Per-PR final test counts (#74 1517 / #75 1517 / #77 1607 / #87 2079 / #96 2204), final surface
counts at that PR (e.g. #74 public 41 / __all__ 49; #77 41→42 / 49→50), the real review
defect→correction pairs, the pre-squash commit SHAs, and each PR's forward boundary at the time
are all retained (review tables + the `<details>` chronology). Repeated boilerplate ("Test
plan" checkboxes, multi-paragraph "does NOT do" lists, duplicate merge-fact blocks) was
condensed; no unique fact absent elsewhere in the repo was dropped.

## 9. STOP conditions checked (none triggered)
base SHA / baseline 2204 match; all 22 bodies backed up with hashes; #80 confirmed absent; no
title/state/base/merge metadata mutated; no runtime/test/README change; Batch 2 NOT applied
before Batch-1 format approval; no force-push / history rewrite; v2 + Cerberus integration
recorded as NOT STARTED.

## 10. Full suite
`python -m pytest -q` → **2204 passed** (no git source change beyond this record; runtime delta 0).

## 11. Batch 1 format approval + #77 precision correction (follow-up)
The Batch-1 body format was approved by the user and by GPT independent review
(**review id 4587550278**). **Batch 1 precision correction:** PR #77's `Current project context`
previously read "the effective-confidence logic now lives in the C9 ConfidenceAdaptersMixin",
which conflated the two ownership layers. Corrected to: the **fixed numeric policy** lives in
the pure `ragcore._engine.confidence` kernel, while the **Engine-facing fact collection +
trace/adaptation methods** live in C9 `ConfidenceAdaptersMixin` (and `Engine.__init__` owns the
state). Only #77's `Current project context` paragraph changed; its merge facts / test count /
review table / chronology are unchanged.

## 12. Batch 2 applied (17 PRs)
Reconstructed final-state-first and applied to GitHub PR bodies: #76 #78 #79 #81 #82 #83 #84 #85
#86 #88 #89 #90 #91 #92 #93 #94 #95. Each PR's own merged test/surface numbers are preserved
(NOT overwritten with the current 2204). Notable precision points held: **#81** separates the
docs/test corrections from the single P03 production fix (malformed-snapshot admission
strengthened — *not* "runtime delta 0"); **#85** states the pure-kernel (`confidence`) vs C9
adapter ownership split; **#82/#86** carry "ACCEPTED AND IMPLEMENTED" with the historical
PROPOSAL/decision-gate framing only in `<details>`; **#88–#95** carry the exact cluster owner +
method count from `ENGINE_V1_FINAL_BOUNDARY.md` (C3 2 / C7 4 / C4 5 / C9 10 / C6 2 / C2 9 / C5 12
/ C10 4) and AST 2·2 / 4·4 / 5·5 / 10·10 / 2·2 / 9·9 / 12·12 / 4·4.

## 13. Full validation (22/22, Batch 1 + Batch 2)
```
final-state-first (## Final status at top)        22/22
MERGED/CLOSED within first 40 lines               22/22
canonical card removed                            22/22
duplicate closure (Post-merge / Final merge) 0    22/22
merge facts appear exactly once                   22/22
no Draft/OPEN/NOT-MERGED outside <details>        22/22
metadata mutation (state/title/base/mergeCommit)   0  (gh pr edit is body-only; all 22 remain MERGED)
content census: each PR's own final test count present, no current-2204 except #96   PASS
#80                                               absent (N/A)
```

### Before → after (lines) + body SHA-256 (12)
```
#74  136 -> 76   99eaa11badfa -> 2640d77b81d0      #86  278 -> 59   04febf928ec8 -> cf35ef05a1e4
#75  199 -> 64   54d3c7a9875b -> 73ab71a79272      #87  142 -> 64   d494ee198df3 -> fe06c2edf79f
#76  211 -> 63   6290722558b7 -> e63e1bd81dd3      #88  144 -> 56   5d81ee7bd6da -> 9856dfbfd86d
#77  233 -> 74   acf0be495dba -> 83b2a9c1ae14      #89  174 -> 56   2ddec6673039 -> abd2103b9861
#78  304 -> 63   be977fddf009 -> 6203494d47fb      #90  193 -> 56   6e2beb83379f -> 568b4d45641a
#79  237 -> 58   fe5e11df52ad -> c14584c027fe      #91  189 -> 57   06d18d197233 -> 8b1a8b6ab209
#81  132 -> 68   ee9f754c3ab7 -> f29681e0ed71      #92  165 -> 57   49eda66be79a -> 858a7e3a4101
#82  105 -> 55   ffd80ef53f5d -> 633ac028ceba      #93   84 -> 56   1514a172170f -> 0a7041e404cd
#83  104 -> 54   75bb8ec307a6 -> cce1ee5fa598      #94   84 -> 56   82d32437c425 -> f09a21d7f704
#84  127 -> 60   8307247d3ab5 -> 932cc86aeef6      #95   79 -> 56   35530b5fc5f6 -> 7630ac17d74f
#85  179 -> 60   8ccd0822f821 -> 2f34f0f0c27d      #96   83 -> 71   2f7f42501469 -> eff527f39d62
```
(The Batch-2 before-hashes here are the fresh re-backup taken immediately before Batch 2, so the
#88–#95 before-hashes differ from §8's earlier snapshot by the Phase-5B card already present.)

### Removed duplicate sections (inventory)
Across the 22: the Phase-5B `## Phase 5 — Canonical final status` card (22), `## Post-merge audit
reconstruction` (#75 #76 #77 #78 #79 #81 #82 #83 #84 #85 #86), `## Final merge closure` (#88–#92),
duplicate `## Lifecycle` / `## Review posture` / top `DRAFT — NOT MERGED` (the Phase-3B + closure
PRs). All folded into one `## Final status` + the historical `<details>`.

### Preserved unique facts
Each PR's final test count (#74 1517 … #96 2204), at-PR surface counts, real review
defect→correction pairs, pre-squash commit SHAs, cluster owner + method count, and the P03
production-fix vs docs-correction distinction (#81) are all retained.

## 14. Full suite
`python -m pytest -q` → **2204 passed** (the only git change is this audit record; runtime delta 0).

## Lifecycle
OPEN — Draft. Status: **READY FOR GPT FINAL INDEPENDENT REVIEW** (Batch 1 + Batch 2 complete;
22/22). Not self-merged; PR #98 stays Draft until APPROVE. Engine v2 NOT STARTED; Cerberus
integration NOT STARTED. This record does not self-pin the SHA of the commit that adds it.
