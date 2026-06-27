# Merged PR-body reconstruction audit (#75–#84)

Phase 2C of the Engine v1 refactoring plan. This file is an **audit index** for
the GitHub PR-body reconstruction — not a copy of the bodies. Its purpose is to
let a future reader (GPT / Claude / a retrieval system) recover, for each merged
PR, *what it intended, what review found, how it was corrected, and what its
authoritative final state is*, without mistaking stale draft language for
current status.

## Purpose
Several merged PR bodies still carried pre-merge draft lifecycle language
("OPEN / DRAFT / NOT MERGED / Ready for review / Framework waits"). That language
is historically true but, left unqualified on a merged PR, misleads. More
importantly, the merged bodies described the *final* state but did not preserve
the **review -> correction history** (which defect was found, in which commit it
was fixed). Each target PR body was rewritten to add a **"Post-merge audit
reconstruction"** section that (a) historicizes the pre-merge draft language,
(b) lists the pre-squash commit history with full SHAs, (c) maps each review
finding to the correction commit that resolved it, (d) states the authoritative
final reading and forward boundary, and (e) records verified merge facts. No
prior body content was deleted.

## Reference baseline
PR #74 (and the earlier detailed Draft PRs) is the quality/audit baseline. #74's
own body was not rewritten — it was not found factually wrong.

## Source evidence (per PR, cross-checked — not from memory)
For each PR: `gh pr view <n> --json body,mergeCommit,mergedAt,commits,changedFiles,additions,deletions,state`
(full 40-char merge SHA + full pre-squash commit list) plus the commit messages
and local git history. No remote-branch deletion state was independently
verifiable, so it is recorded as "not independently verified".

| PR | state | merge commit (full 40-char) | merged at (UTC) | commits | files | +/− |
|----|-------|------------------------------|-----------------|---------|-------|-----|
| #75 operator decision record revalidation (M05) | MERGED | `80759048e98d9255596a8aa56bf4ea94cd9d1250` | 2026-06-19T03:02:41Z | 4 | 6 | +2037/-0 |
| #76 downstream result re-entry contract (M06) | MERGED | `9f576a5b072f4d194083d9b4c20d997d78c4b787` | 2026-06-19T05:51:12Z | 4 | 6 | +2490/-0 |
| #77 effective confidence calculation trace (M07) | MERGED | `f57cd5da1fd4ab09d93b89bbf3d7bd08b22192be` | 2026-06-24T10:11:47Z | 8 | 16 | +4364/-30 |
| #78 complete domain-neutral reference operation (M08) | MERGED | `31e0210998374815c90dc9671069034bf6e10d1b` | 2026-06-25T01:21:58Z | 13 | 4 | +6992/-0 |
| #79 RuleStats update provenance (M09) | MERGED | `6d43cd8959fa9e37a60efe527f84b5ba60c6413e` | 2026-06-25T11:34:04Z | 7 | 4 | +2796/-0 |
| #81 post-merge audit reconciliation (P01–P05 + M01–M09) | MERGED | `aaa80242101f3ef44ba43c11a1c54e282aa21611` | 2026-06-27T07:35:17Z | 23 | 26 | +2450/-264 |
| #82 Engine v1 refactoring plan (revised) | MERGED | `dc942a1d9ca58c7755e21c7fdbecaacb46de671c` | 2026-06-27T07:59:26Z | 1 | 1 | +370/-0 |
| #83 Phase 0 — test-taxonomy migration | MERGED | `0c27ad3f81e785f742b7c324a5e590f770cafebe` | 2026-06-27T08:44:44Z | 2 | 3 | +346/-100 |
| #84 Phase 1 — serialization extraction + decode/install boundary | MERGED | `88edc18dfdb97460add4feac1eea09fcfb4ee536` | 2026-06-27T10:35:35Z | 3 | 8 | +1010/-802 |

`#80 does not exist` and is excluded.

> Correction note (this audit's own earlier draft): the first version of this
> table abbreviated merge SHAs with ellipses and miscopied two values — #81's
> SHA prefix was wrong (`aaa8024218…` vs the real `aaa80242101f…`) and #84's
> commit count was listed as 8 (the changed-files value) instead of 3. Both are
> fixed above; all SHAs are now full 40-char and the whole table was
> re-machine-checked against GitHub metadata.

## What each reconstruction recovered (per PR)
- **#75 (M05)** / **#76 (M06)** — 4 commits each: contract -> dev record -> two
  review-correction commits. Recovered the specific findings (M05
  reuse-eligibility wording + record counts; M06 references + handoff sequence /
  stage 5.5) mapped to their correction commits.
- **#77 (M07)** — 8 commits. Recovered the 258차 review's C1/C2/C3 groups,
  including the C1 miscitation (`state_identity()` basis is M04 §1.2, not §2.6)
  and the later exact-composition-expression lock.
- **#78 (M08)** — 13 commits (heaviest M-series review). Recovered the authority-
  gate review chain ending in the runtime call-count proof and the example fix
  that actually enforces the gates (`be9940ec88`).
- **#79 (M09)** — 7 commits. Recovered the **STOP-AND-REPORT** event and its
  cause: a test asserted invalid raw cross-run equality of fresh reports; fixed
  by comparison-only `engine_token` normalization (`05fd597351`).
- **#81** — 23 commits. Recovered the per-item correction groups (P01–P05,
  M01–M09) and pinpointed the only two runtime-touching commits: the engine fix
  `c99df50c81` (P03 restore-integrity, malformed-snapshot admission strengthened)
  and the example fix `006cb3fa17` (M01 scaffold).
- **#82** — 1 commit, but a *revision*: recovered the initial-plan measurement
  errors (surface-freeze mischaracterized as behavioral; engine.py / from_snapshot
  line counts) corrected by `0647139b60`.
- **#83** — 2 commits. Recovered the forbidden-import re-review blocker
  (substring scan missed from-imports / bare imports; dead `loaded_after_import`;
  `ModuleNotFoundError` masking) and the AST-filesystem-scan fix (`72f6ca4406`).
- **#84** — 3 commits, two REQUEST CHANGES rounds. Recovered round 1
  (Phase-1A-only relocation; missing decode/install boundary; over-broad
  deferral) and round 2 (egg-info; broad TypeError->ValueError §52.7 break; 3
  public AST locks; stale docstring), each mapped to its correction commit.

## Final lifecycle
All nine target PRs are **MERGED**. The M-series dev records (#75–#79 ↔ M05–M09)
were additionally reconciled to CLOSED in the post-merge audit cycle merged as
**PR #81** (commit `c17b833695`); the M01–M04 and P01–P05 dev records were
reconciled in the same PR #81 batch.

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
On merge, add a "Post-merge audit reconstruction" block: pre-squash commit
history (full SHAs), review -> correction mapping, authoritative final reading,
and verified merge facts. Historicize — never delete — the draft state.
