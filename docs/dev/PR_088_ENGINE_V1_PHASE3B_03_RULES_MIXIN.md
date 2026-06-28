# PR_088 — Engine v1 Phase 3B-3: Extract C7 Rules Mixin (development record)

GitHub PR **#89** (internal dev-record number = GitHub number − 1 = 088;
confirmed by creating the Draft PR first).

## Identity / purpose
Third production-code decomposition under the approved Phase 3A ADR. A
behaviour-preserving move of the four C7 rule methods from the `Engine` class
body into a private `RulesMixin`. No change to rule semantics, the
definition/stats independence contract, duplicate handling, stats replacement,
the revision gate, signatures, snapshot/restore, or public API.

## Baseline
```
baseline main   3d7f3e8b7353b25df77d96285a67d7c8c8610da8 (Phase 3B-2 merged)
baseline tests  2088 passed (local; no GitHub Actions on this repo)
guard           HEAD == 3d7f3e8 verified; tracked working tree clean before start
```

## Why C7 third
Per the Phase 3A 3B sequence: two stores (`_rule_definitions`, `_rule_stats`),
one mutating registrar (`register_rule`) + one stats updater + two readers, only
C1 calls. Next-lowest coupling after C8 and C3.

## Exact methods moved (4)
```
register_rule       (public, mutator: definitions A, stats A/W)
get_rule            (public, read-only; _assert_rule_pair_exists guard)
get_rule_stats      (public, read-only; _assert_rule_stats_pair_exists guard)
update_rule_stats   (public, mutator: stats W, revision conditional)
```
**Not moved:** the two stores (`_rule_definitions`, `_rule_stats` stay in
`Engine.__init__`), the C1 guards `_assert_rule_pair_exists` /
`_assert_rule_stats_pair_exists`, `_advance_state_revision`, the confidence
adapter `_rule_stats_modifier_for_claim` / `compute_effective_confidence`, the
snapshot/install methods, and the `RuleDefinition` / `RuleStats` / `ScoreValue`
types (`ragcore.types`).

## Preserved C7 asymmetry (the load-bearing contract)
- **register_rule** guards only `_rule_definitions` (`if key in self._rule_definitions: raise ValueError`)
  then assigns `self._rule_stats[key] = RuleStats(...)` **unconditionally** → an
  INSERT (`A`) for a fresh key, a REPLACE (`W`) for an orphan-restored stats key.
  No `_rule_stats` membership check; no definition↔stats co-existence assertion.
- **get_rule** / **get_rule_stats** use **independent** guards, so each succeeds
  or fails on its own store. Allowed restored states preserved: definition-only,
  stats-only, both, neither.
- **update_rule_stats** always builds a new `RuleStats` and replaces the slot
  (`W`), but advances the revision **only when `new_stats != current`**. A no-op
  (default args) still re-assigns an equal object and does NOT advance; the
  assignment is not optimised away; no new delta validation added.

## Behavioural probes (all pass)
```
11.1 fresh registration : definition stored; default stats (firing 0 / true 0 /
                          false 0 / precision None / fpr None); revision +1.
11.2 duplicate          : ValueError; definitions/stats/revision/snapshot unchanged
                          (no auto-recovery of missing stats via re-register).
11.3 orphan RuleStats    : snapshot with rule_definitions=[] restored ->
   (stats-only)            get_rule_stats OK; get_rule KeyError; update_rule_stats
                          works WITHOUT a definition (+1 rev); register_rule then
                          inserts the definition AND replaces the orphan stats with
                          defaults (A/W), each change +1 rev.
11.4 definition-only     : snapshot with rule_stats=[] restored -> get_rule OK;
                          get_rule_stats KeyError; update_rule_stats KeyError;
                          duplicate register ValueError; NO auto-created stats;
                          revision unchanged.
11.5 changed update      : old frozen RuleStats unchanged; new fields exact; +1 rev.
11.6 no-op update        : stored value equal; revision + snapshot unchanged.
11.7 missing pair        : get_rule / get_rule_stats / update_rule_stats -> KeyError,
                          stores/revision unchanged.
```

## C1 seam call counts (spies installed after setup)
```
register_rule (fresh) : _advance_state_revision ×1
get_rule              : _assert_rule_pair_exists ×1
get_rule_stats        : _assert_rule_stats_pair_exists ×1
update_rule_stats (changed) : _assert_rule_stats_pair_exists ×1, _advance_state_revision ×1
update_rule_stats (no-op)   : _assert_rule_stats_pair_exists ×1, _advance_state_revision ×0
```

## Before → after ownership / accumulated MRO
`class Engine(HintEvidenceMixin, RelationsMixin):` →
`class Engine(HintEvidenceMixin, RelationsMixin, RulesMixin):` (new mixin
appended, existing prefix preserved). All three mixins in `Engine.__mro__`; the
four methods resolve via the MRO (no forwarding wrapper). engine.py 1439 → 1345.

## Engine state did NOT move (proof)
`Engine.__init__` still owns `self._rule_definitions: dict[...] = {}` and
`self._rule_stats: dict[...] = {}`, with `RuleDefinition`/`RuleStats` imports
retained for those annotations. The mixin has no `__init__`/state/back-reference;
it reaches the stores via `self._rule_definitions` / `self._rule_stats` and the C1
seams via `self._assert_*` / `self._advance_state_revision()`. Snapshot still
serialises both stores; restore round-trips; 18 top-level keys.

## Import graph
```
ragcore.engine -> ragcore._engine.rules            (added)
ragcore._engine.rules imports: {__future__, ragcore.types}  (RuleDefinition, RuleStats, ScoreValue)
ragcore._engine.rules -> ragcore.engine            : NONE
ragcore._engine.rules -> hint_evidence / relations : NONE   (no cycle, no inter-mixin coupling)
hint_evidence.py / relations.py / confidence.py / serialization.py / types.py / ragcore/__init__.py : unchanged
```

## AST equivalence
`ast.dump(..., include_attributes=False)` baseline `3d7f3e8:ragcore/engine.py`
(Engine) vs `ragcore/_engine/rules.py` (RulesMixin): **4/4 identical**; all four
methods absent from the current Engine class body.

## Accepted introspection deltas (Phase 3A-approved) / preserved surface
```
the four methods: __module__ -> ragcore._engine.rules; __qualname__ -> RulesMixin.*;
declaring class -> RulesMixin; inherited (not in Engine.__dict__); Engine.__mro__ + RulesMixin.
Preserved: from ragcore import Engine; Engine.__module__ == "ragcore.engine";
runtime public 42; ragcore.__all__ 50; exact signatures; getattr/setattr/monkeypatch on
Engine; inspect.getsource(Engine.<C7>) returns real body; no extra traceback frame;
HintEvidenceMixin + RelationsMixin unchanged and in the MRO.
```

## Exact signatures (unchanged)
```
register_rule(self, definition: 'RuleDefinition') -> 'None'
get_rule(self, rule_id: 'int', rule_version: 'int') -> 'RuleDefinition'
get_rule_stats(self, rule_id: 'int', rule_version: 'int') -> 'RuleStats'
update_rule_stats(self, rule_id: 'int', rule_version: 'int', *, firing_delta: 'int' = 0,
  true_delta: 'int' = 0, false_delta: 'int' = 0, observed_precision: 'ScoreValue | None' = None,
  false_positive_rate: 'ScoreValue | None' = None) -> 'None'
```

## Tests
```
new: tests/test_engine_phase3b_rules_mixin.py (10 runtime, location-agnostic locks;
     incl. the update_rule_stats revision gate changed/no-op)
targeted: phase0 + phase3b hint + phase3b relations + the rg-discovered rule /
          stats / confidence / snapshot tests -> 1447 passed
full suite: 2088 -> 2098 passed (+10 new; no existing test weakened or changed)
```

## Files changed / line delta
```
production/test: 3 files, +243/-97
  ragcore/_engine/rules.py                          +114 (new)
  ragcore/engine.py                                 +3/-97
  tests/test_engine_phase3b_rules_mixin.py          +126 (new)
+ docs/dev/PR_088_…                                 (this file)
NOT changed: ragcore/_engine/{hint_evidence,relations,confidence,serialization}.py,
ragcore/_engine/__init__.py, ragcore/types.py, ragcore/__init__.py, snapshot
schema, examples/**, config/deps, any other cluster, Phase 3A docs.
```

## Commit chronology
```
d0aa329 refactor(engine): extract C7 rules mixin
e1b0bf6 test(engine): lock inherited C7 runtime contracts
<this>  docs(dev): record Phase 3B-3 rules mixin extraction
```
No commit amended, rebased, or squashed.

## STOP-AND-REPORT review
None triggered: AST 4/4 identical; no Engine wrapper; no public-signature /
`Engine.__module__` / public-count / `__all__` change; both stores stay on Engine;
no C1 guard/revision method moved; no confidence change; no snapshot/restore change;
definition↔stats independence preserved (orphan stats and definition-only states
both honoured; no forced co-existence); register_rule A/W and update_rule_stats
unconditional-W + conditional-revision preserved; the two prior mixins unchanged;
`rules.py` imports neither `ragcore.engine` nor another mixin; no import cycle; no
test weakened; no source-location lock added.

## Lifecycle
OPEN — Draft. Recommendation on completion: **READY FOR GPT INDEPENDENT REVIEW**
(not self-merged). **Phase 3B-4 (C4 gaps) remains prohibited** until this PR
passes independent review (APPROVE), squash merge, branch cleanup, and post-merge
`main` verification.
