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

## Lifecycle
OPEN — Draft. **Batch 1 only.** Status: **BATCH 1 READY FOR GPT / USER FORMAT REVIEW.** Batch 2
(17 PRs) is NOT applied until the Batch-1 body format is approved. Engine v2 NOT STARTED;
Cerberus integration NOT STARTED. This record does not self-pin the SHA of the commit that adds
it; the Batch-2 application + after-hashes are recorded in a follow-up commit.
