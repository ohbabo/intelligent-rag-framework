# Merged PR-body reconstruction audit (#75–#84)

Phase 2C of the Engine v1 refactoring plan. This file is an **audit index** for
the GitHub PR-body reconstruction — not a copy of the bodies. Its purpose is to
let a future reader (GPT / Claude / a retrieval system) recover, for each merged
PR, *what it intended, what its draft state was, and what its authoritative final
state is*, without mistaking stale draft language for current status.

## Purpose
Several merged PR bodies still carried their pre-merge draft lifecycle language
("OPEN / DRAFT / NOT MERGED / Ready for review / Framework waits"). That language
is historically true but, left unqualified on a merged PR, misleads. Each target
PR body was given a **"Final closure (post-merge audit reconstruction)"** section
that (a) marks the earlier draft language as historical, (b) records the verified
final merge facts, and (c) preserves all existing detail (no detail was deleted,
no review history compressed, no SHA guessed).

## Reference baseline
PR #74 (and the earlier detailed Draft PRs) is the quality/audit baseline. #74's
own body was not rewritten — it was not found factually wrong.

## Source evidence (per PR, cross-checked — not from memory)
For each PR: `gh pr view <n> --json body,mergeCommit,mergedAt,commits,changedFiles,additions,deletions,state` plus local git history. No remote-branch deletion state was independently verifiable, so it is recorded as "not independently verified".

| PR | state | merge commit | merged at (UTC) | commits | files | +/− |
|----|-------|--------------|-----------------|---------|-------|-----|
| #75 operator decision record revalidation | MERGED | `80759048e98d9255596a8aa56bf4ea94cd9d1250` | 2026-06-19T03:02:41Z | 4 | 6 | +2037/-0 |
| #76 downstream result re-entry contract | MERGED | `9f576a5b072f4d194083d9b4c20d997d78c4b787` | 2026-06-19T05:51:12Z | 4 | 6 | +2490/-0 |
| #77 effective confidence calculation trace | MERGED | `f57cd5da1fd4ab09d93b89bbf3d7bd08b22192be` | 2026-06-24T10:11:47Z | 8 | 16 | +4364/-30 |
| #78 complete domain-neutral reference operation | MERGED | `31e0210998374815c90dc9671069034bf6e10d1b` | 2026-06-25T01:21:58Z | 13 | 4 | +6992/-0 |
| #79 RuleStats update provenance | MERGED | `6d43cd8959fa9e37a60efe527f84b5ba60c6413e` | 2026-06-25T11:34:04Z | 7 | 4 | +2796/-0 |
| #81 post-merge audit reconciliation (P01/P02/P03 + M01–M09) | MERGED | `aaa8024218...` (`aaa802421`) | 2026-06-27T07:35:17Z | 23 | 26 | +2450/-264 |
| #82 Engine v1 refactoring plan (revised) | MERGED | `dc942a1d9...` (`dc942a1`) | 2026-06-27T07:59:26Z | 1 | 1 | +370/-0 |
| #83 Phase 0 — test-taxonomy migration | MERGED | `0c27ad3f8...` (`0c27ad3`) | 2026-06-27T08:44:44Z | 2 | 3 | +346/-100 |
| #84 Phase 1 — serialization extraction + decode/install boundary | MERGED | `88edc18df...` (`88edc18`) | 2026-06-27T10:35:35Z | 8 | 8 | +1010/-802 |

`#80 does not exist` and is excluded.

## What was missing from the existing bodies
- #75–#79: their own pre-merge "OPEN/DRAFT/NOT MERGED" lifecycle was never
  historicized after squash-merge; the detailed body content was otherwise
  intact and is preserved.
- #81–#84 (audit/plan/phase PRs authored in this cycle): the stale words present
  were mostly **quotations** describing the M-series corrections (e.g. DRAFT→CLOSED),
  not the PR's own status; a closure section was still added for a uniform,
  unambiguous final state.

## Sections applied
Each target PR body now ends with a "Final closure (post-merge audit
reconstruction, 2026-06-27)" section: final state (MERGED, squash), merge
commit, merged-at, commits squashed, changed files, a not-verified note for
remote-branch deletion, and a pointer that later-PR audit corrections are the
authoritative reading where they touched an earlier description. No prior
content was removed or summarized away.

## Final lifecycle
All nine target PRs are **MERGED**. The M-series dev records (#75–#79 ↔ M05–M09)
were additionally reconciled to CLOSED in the post-merge audit cycle merged as
**PR #81**; the M01–M04 dev records were reconciled in the same PR #81 batch.

## Not independently verifiable (recorded, not asserted)
- Remote feature-branch deletion state per PR (GitHub `--delete-branch` history
  not queried here).
- CI status: there are no GitHub Actions runs on these heads; all `pytest`
  numbers in the bodies are **local runs**, not CI-verified.

## Future PR-body minimum template
New PRs (especially Draft-then-merge work) should keep, from the start and
cumulatively (never overwriting review history, never amending it away):

```
## Identity and purpose
## Starting baseline (base SHA + measured tests)
## Scope / explicit non-scope
## Commit history (차수/SHA — never synthesised)
## Initial implementation
## Review findings  (each defect, who found it)
## Post-review corrections  (per correction commit)
## Final authoritative state  (which description is authoritative)
## Files changed (exact totals)
## Behavioral & structural invariants (measured)
## Verification (local vs CI explicitly)
## Deferred work / forward boundary
## Forbidden conclusions
## Lifecycle / merge closure  (Draft state separated from final merge SHA/timestamp)
```
On merge, add a "Final closure" block (merge SHA, merged-at, squash, changed
files); historicize — never delete — the draft state.
