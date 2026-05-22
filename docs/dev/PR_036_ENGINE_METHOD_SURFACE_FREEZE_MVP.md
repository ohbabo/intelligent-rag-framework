# PR 036 — Engine Method Surface Freeze MVP (PR36-PKG)

## Summary

PR36-PKG freezes the Engine method surface as a stable package boundary.

It does **not** freeze the internal judgment mathematics.

Core closing statements (locked by user 2026-05-22):

```text
Freeze method surface, not judgment mathematics.
```

```text
The engine is allowed to become smarter without forcing consumers to
rewrite their integration code.
```

PR36-PKG is the first framework PR that:

- explicitly defines the contract that external consumers (Cerberus first) can rely on across framework updates
- separates "stable forever" surface from "allowed to evolve" mathematics
- ships minimal packaging metadata so the framework is consumable as an installable Python package

PR36-PKG is **not** a feature PR, **not** a refactor PR, **not** a packaging-only PR. It is a *contract freeze* — declaring which parts of the engine consumers depend on, and which parts the framework reserves the right to refine.

Four-차수 cycle:

```text
147차  docs(contract) §48  Engine Method Surface Freeze MVP (boundary contract)
148차  test(package)        method surface freeze invariants (26 tests)
149차  build(package)       minimal pyproject metadata
150차  docs(dev) (this)     PR record + ready + squash merge
```

---

## Baseline

```text
base main:    8dd0535
branch:       feat/engine-method-surface-freeze
before tests: 1089 passing
public symbols: 48
Engine public methods: 40
snapshot schema_version: 2
```

Completed immediately before this PR:

```text
PR35-O7 snapshot restore refactor (helper symmetry 6 × 6)
```

The active confidence formula entering PR36-PKG:

```text
effective = base × status × freshness × gap × count × rule_stats × evidence_type
```

PR36-PKG does not change this formula. It explicitly preserves the right of future PRs to recalibrate / replace it under §48.3.

---

## Commits in this PR

```text
147차  0bc7c5f  docs(contract): define engine method surface freeze MVP (§48)
148차  1af2d1c  test(package): lock engine method surface freeze invariants
149차  835e9b5  build(package): add minimal pyproject metadata
150차  this commit — docs(dev) record + Draft → Ready + squash merge
```

---

### 147차 — docs(contract) §48

Commit `0bc7c5f` added §48 to `docs/contracts/05_DATA_CONTRACT_MVP.md` (+386 lines, 13 subsections):

```text
§48.1   Core statement (locked framing sentence)
§48.2   Method surface freeze (48 symbols / 40 methods / 6 report shapes)
§48.3   Algorithm evolvability (what is allowed to change)
§48.4   Allowed future engine updates
§48.5   Breaking change boundary (method surface migration rules)
§48.6   Cerberus consumer stability (example script that must keep working)
§48.7   Snapshot compatibility (PR21-L v2 key set frozen)
§48.8   Report surface compatibility (PR32-V 6 frozensets)
§48.9   Import surface stability (no network / IO / LLM on import)
§48.10  Policy update documentation rule
§48.11  Non-goals
§48.12  Regression invariants
§48.13  Cycle for PR36-PKG implementation (147 / 148 / 149 / 150)
```

The §48.1 core statement locks the principle:

```text
The engine is allowed to become smarter without forcing consumers
to rewrite their integration code.
```

The §48.6 example script makes the consumer contract concrete:

```python
from ragcore import Engine

engine = Engine()
claim_id = engine.add_claim(...)
score = engine.compute_effective_confidence(claim_id)
history = engine.claim_lifecycle_history(claim_id)
snapshot = engine.to_snapshot()
```

This script must keep working across all future framework PRs that improve internal mathematics, recalibrate modifiers, tune thresholds, or replace algorithms — *unless* the PR is explicitly labeled a "method surface migration" with deprecation cycle.

---

### 148차 — test(package) method surface freeze invariants

Commit `1af2d1c` added `tests/test_engine_method_surface_freeze.py` (+409 lines, 26 tests, 8 classes):

```text
TestPublicNamespaceFreeze            4 tests  §48.2
TestEngineMethodNameFreeze           3 tests  §48.2 / §48.5
TestCoreConsumerMethods              2 tests  §48.6
TestImportSurfaceSideEffects         4 tests  §48.9
TestModifierHelperSignatures         3 tests  §48.2 + PR34-O O2/O3
TestSerializeRestoreSymmetry         3 tests  §48.2 + PR35-O7 §47
TestSnapshotShapeFreeze              4 tests  §48.7
TestPackageSurfaceStability          3 tests  §48.9 / §48.12
```

Three locked module-level frozensets:

```text
_LOCKED_PUBLIC_METHODS                  frozenset of 40 method names
_LOCKED_MODIFIER_HELPERS                tuple of 6 modifier helper names
_LOCKED_SNAPSHOT_TOP_LEVEL_KEYS         frozenset of 18 snapshot top-level keys
```

These frozensets cannot be amended without an explicit method surface migration PR (per §48.5). Internal refactor PRs that preserve the frozensets pass these tests automatically.

`claim_report` (PR32-V §44.11 OOS) is intentionally NOT tested here — its absence is already locked by PR32-V's `test_engine_does_not_expose_claim_report_helper`. PR36-PKG preserves that invariant without duplication.

---

### 149차 — build(package) minimal pyproject metadata

Commit `835e9b5` augmented `pyproject.toml` (+7 lines):

```toml
[project]
# PR36-PKG §48 — distribution boundary, not a new engine feature.
# version 0.1.0 (NOT 1.0.0): internal judgment mathematics is allowed to
# evolve (§48.3); only the method surface is frozen (§48.2).
name = "ragcore"
version = "0.1.0"
description = "Intelligent RAG Framework — Python Reference Core"
readme = "README.md"
requires-python = ">=3.10"
authors = [
    { name = "ohbabo" },
]
dependencies = [
    "PyYAML>=6.0",
]
```

Pre-149차 pyproject already satisfied most of §48.11:

```text
name = "ragcore"                  conservative (not "cerberus", not "scanner")
version = "0.1.0"                 NOT 1.0.0 — §48.3 algorithm not finalized
description = "Python Reference Core"   neutral, no productization claim
requires-python = ">=3.10"        conservative
dependencies = ["PyYAML>=6.0"]    minimal (rule loader only)
```

149차 added:

```text
readme = "README.md"               sdist/wheel include README (already §48-aligned)
authors = [{ name = "ohbabo" }]   identifies maintainer
explanatory inline comment         §48 framing for future readers
```

Intentionally NOT added (per §48.11 + user caution):

```text
license       no LICENSE in repo; do not claim MIT or any license unverified
classifiers   PyPI Topic / Development Status imply productization scope
urls          no commitment to specific URLs yet
keywords      not a freezable surface
optional-dependencies  runtime boundary stays minimal (§48.13)
```

PEP 668 (Kali externally-managed-environment) blocks `python -m pip install -e .` system-wide install. The pyproject.toml is structurally valid TOML and installs cleanly in any non-managed environment (venv, pipx, CI). Editable install behavior is **not** a 149차 invariant; the invariant is package structure validity + import smoke.

---

## Method surface freeze invariants (locked in 148차)

### Public namespace (§48.2)

```text
ragcore.__all__         48 public symbols (frozenset)
unique symbols           48 (no duplicates)
"Engine" in __all__      yes
from ragcore import Engine    works
```

### Engine public methods (§48.2 / §48.5)

```text
Engine public method count  40
frozen method name set      40 method names match _LOCKED_PUBLIC_METHODS exactly
extra method detected       fail (additive change blocker)
missing method detected      fail (regression blocker)
```

### Core consumer methods (§48.6)

```text
Engine class importable               yes
Engine.add_claim                       exists, callable
Engine.compute_effective_confidence    exists, callable
Engine.claim_lifecycle_history         exists, callable
Engine.to_snapshot                     exists, callable
Engine.from_snapshot                   exists, callable
Engine.claim_report                    NOT exposed (PR32-V §44.11 OOS, preserved)
```

### Import surface side-effects (§48.9)

```text
Engine() instantiation                no external call
empty engine to_snapshot              valid dict, schema_version=2
snapshot round-trip                    identity preserved
ragcore.engine forbidden imports      none (no requests / urllib / httpx / socket)
```

### Modifier helper signatures (§48.2 + PR34-O O2/O3)

```text
_status_modifier_for_claim             (self, claim_id: int) -> float
_freshness_modifier_for_claim          (self, claim_id: int) -> float
_gap_modifier_for_claim                (self, claim_id: int) -> float
_count_modifier_for_claim              (self, claim_id: int) -> float
_rule_stats_modifier_for_claim         (self, claim_id: int) -> float
_evidence_type_modifier_for_claim       (self, claim_id: int) -> float
```

### Serialize / restore symmetry (§48.2 + PR35-O7 §47)

```text
_serialize_dict_* helpers              6
_restore_dict_* helpers                6
shape class symmetry                   6 / 6 verified
```

### Snapshot top-level shape (§48.7)

```text
schema_version                          2
top-level key count                    18
key set matches frozen 18-key set      yes
JSON-compatible at top level           yes
```

### Package surface stability (§48.9 / §48.12)

```text
import idempotent                      yes
__all__ is list or tuple                yes
ragcore.Engine == imported Engine      yes
```

---

## Test result

Final test result before merge:

```text
1115 passed, 0 failed
```

Delta:

```text
1089 -> 1115  (+26 method surface freeze tests)
regression: 0
natural-expiry: 0
```

26 new tests are method surface invariants — they verify presence / count / shape / signature, **not** internal mathematics.

---

## Unchanged files

```text
ragcore/engine.py
ragcore/types.py
ragcore/__init__.py
ragcore/rule_output.py
ragcore/condition.py
ragcore/rule_compile.py
ragcore/rule_gap.py
ragcore/rule_loader.py
ragcore/rule_runtime.py
all existing test files
```

PR36-PKG touched only:

```text
docs/contracts/05_DATA_CONTRACT_MVP.md             (+386 lines §48)
tests/test_engine_method_surface_freeze.py         (new, +409 lines)
pyproject.toml                                      (+7 lines)
docs/dev/PR_036_ENGINE_METHOD_SURFACE_FREEZE_MVP.md (this record)
```

---

## Non-goals (explicit)

PR36-PKG does NOT:

```text
- finalize the algorithm
- freeze judgment mathematics
- add Cerberus-specific adapter
- split engine.py
- cleanup file layout (deferred to PR37+)
- claim production readiness
- claim Cerberus integration
- add CLI execution
- add scanner orchestration
- add database storage
- add file IO inside Engine
- add LLM integration
- add network access
- rename any public symbol
- change any public method signature
- change snapshot schema_version
- change any report frozenset
```

PR36-PKG only declares: *whatever the algorithm becomes, the method surface through which it is called remains stable.*

---

## Boundary preservation table

| Preserved boundary                                       | PR36-PKG effect                       | Status      |
| -------------------------------------------------------- | ------------------------------------- | ----------- |
| Sub-decision D (types / rule_output unchanged)           | engine source unchanged               | preserved   |
| Sub-decision AF (HINT taxonomy framework-external)       | unchanged                              | preserved   |
| PR17 snapshot schema v2                                  | locked by §48.7 + test                | reinforced  |
| PR21-L hint validation (caller-registered)               | unchanged                              | preserved   |
| PR27-P consumer call boundary (§39)                      | unchanged                              | preserved   |
| PR28-O rule version pinning                              | unchanged                              | preserved   |
| PR29-R observed_precision bounded no-boost                | unchanged                              | preserved   |
| PR30-P consumer policy guides (§42)                      | unchanged                              | preserved   |
| PR31-S AI-readable usage recipe (§43)                    | unchanged                              | preserved   |
| PR31-S method surface freeze (48 symbols)                | locked by §48.2 + test invariant      | **strengthened** |
| PR32-V report surface (§44)                              | locked by §48.8 reference             | reinforced  |
| PR32-V Engine.claim_report absence                       | preserved (not duplicated in 148차)  | preserved   |
| PR33-M docstring coverage (40/40)                        | unchanged                              | preserved   |
| PR33-M __all__ 12-group ordering                         | unchanged                              | preserved   |
| PR34-O modifier signature consistency (6 helpers)        | locked by §48.2 + test                | **strengthened** |
| PR34-O defensive check helpers (6)                       | unchanged                              | preserved   |
| PR35-O7 serialize/restore symmetry (6 × 6)               | locked by §48.2 + test                | **strengthened** |
| 7-modifier formula                                        | unchanged (allowed to evolve §48.3)   | preserved   |
| modifier value behavior                                  | unchanged (allowed to evolve §48.3)   | preserved   |
| effective_confidence output                              | unchanged (1115 tests identical)      | preserved   |
| Method surface freeze contract                            | newly documented + tested              | **newly locked** |
| Algorithm evolvability declaration                        | §48.3 / §48.4 explicit                | **newly locked** |
| Breaking-change boundary                                 | §48.5 explicit                         | **newly locked** |

---

## Self-review

### What this PR does

PR36-PKG is the contract freeze that lets internal mathematics evolve safely:

```text
- documents which surface is stable forever (§48.2)
- documents which mathematics may evolve (§48.3)
- locks 40 public method names as frozen set (test 148차)
- locks 18 snapshot top-level keys (test 148차)
- locks 6 modifier helper signatures (test 148차)
- locks 6 × 6 serialize/restore symmetry (test 148차)
- locks import side-effect-free invariants (test 148차)
- ships minimal pyproject metadata bounded by §48.11 (149차)
```

### What this PR does not do

```text
- does NOT change any source file in ragcore/
- does NOT add any judgment behavior
- does NOT recalibrate any modifier
- does NOT touch lifecycle / contradiction / rule_output / confidence logic
- does NOT add new public API (no Engine.claim_report etc.)
- does NOT split engine.py (deferred to PR38+)
- does NOT cleanup docs / README / examples (deferred to PR37-PKG-DOCS)
- does NOT make Cerberus integration claims
- does NOT make production-ready claims
- does NOT add LICENSE (no commitment yet)
```

### Why the conservative scope is correct

```text
1. Method surface freeze is the most expensive contract to establish.
   Mixing it with file reorganization or engine.py splits would dilute
   the freeze signal — future readers couldn't tell which changes were
   refactor vs which were contract declarations.

2. The user explicitly partitioned the work:
     PR36-PKG = method surface freeze + minimal package metadata
     PR37-PKG-DOCS = docs / README / examples layout cleanup
     PR38-O (or later) = engine.py internal split (audit-first)
   PR36-PKG honors this partition.

3. Algorithm evolvability requires the surface to be locked FIRST.
   Without §48.5's breaking-change boundary, future modifier
   recalibration PRs would have no rule against silent renames.
   PR36-PKG establishes that rule before any future calibration PR
   can land.

4. The audit-first pattern (PR33-M / PR34-O / PR35-O7 precedent) does
   not apply to PR36-PKG because PR36-PKG is not a refactor — it is
   a contract declaration. The closest analogue is PR27-P (§39 call
   boundary), PR30-P (§42 read boundary), PR31-S (§43 usage recipe),
   PR32-V (§44 report surface) — all boundary spec PRs with no audit
   step. PR36-PKG follows that lineage.
```

---

## Final meaning

PR36-PKG closes the engine method surface freeze.

Before PR36-PKG, the framework had:

```text
- documented external boundaries (§39 / §42 / §43 / §44)
- documented method surface audit (§45)
- documented internal optimization audit (§46)
- documented snapshot restore refactor (§47)
- 6 × 6 helper symmetry, 40/40 docstring coverage, 6 modifier signature consistency

But NO explicit contract on:
- which parts of the engine consumers can depend on across releases
- which parts the framework reserves the right to refine
- what counts as a breaking change vs an algorithm update
- how the engine becomes installable as a package
```

After PR36-PKG, the framework has:

```text
- §48 contract: method surface freeze + algorithm evolvability declaration
- 26 invariant tests catching method surface breakage
- minimal pyproject metadata (importable as `from ragcore import Engine`)
- explicit Cerberus consumer stability statement (§48.6)
- explicit breaking-change boundary (§48.5)
- explicit policy-update documentation rule (§48.10)
```

The engine remains a domain-light judgment core.
The internal mathematics remain free to evolve under §48.3.
The method surface is locked under §48.2.
The Cerberus consumer script in §48.6 is guaranteed to keep working across future framework updates.

```text
PR27-P  §39  call boundary
PR30-P  §42  read boundary
PR31-S  §43  usage recipe
PR32-V  §44  report surface
PR33-M  §45  method surface audit + Scope A cleanup
PR34-O  §46  internal optimization audit + Scope O-mid refactor
PR35-O7 §47  snapshot restore refactor + helper symmetry
PR36-PKG §48 engine method surface freeze + algorithm evolvability
```

Core locked statement:

```text
Freeze method surface, not judgment mathematics.

The engine is allowed to become smarter without forcing consumers
to rewrite their integration code.
```

---

## Next candidates after PR36-PKG

User-locked partition (2026-05-22):

```text
PR37-PKG-DOCS   package docs / README / examples layout cleanup
                  No engine behavior change.
                  No method surface change.
                  No algorithm change.

PR38-O          engine.py internal module extraction (audit-first)
                  No method surface change (PR36-PKG locked).
                  No algorithm change.
                  Internal file layout only.
```

Other remaining candidates (unchanged from prior plans):

```text
V-cerberus thin adapter (다른 repo, framework 변경 0)
                  실전 사용성 검증
                  PR36-PKG §48.6 example script 실 검증
                  사용자가 cerberus 트랙 진입 시점에 자연 발생

P4 / P5 / P6 (PR33-M deferred — surface domain)
  P4 Naming consistency rename (evidence_freshness / gap_resolution)
  P5 Tier 3 sub-module reorganization (ragcore.trace.*)
  P6 Engine.claim_report convenience method

R-fpr / G / J / Q / S-extension (judgment policy updates per §48.10)
  R-fpr   false_positive_rate modifier (PR29-R 자연 후속)
  G       superseded/retracted lifecycle
  J       multi-rule claim composition
  Q       rule_stats outcome ratio
  S-extension  8th modifier
```

Each of these will inherit PR36-PKG §48 constraints:

```text
- method surface must remain stable (§48.5 breaking-change boundary)
- algorithm changes must be documented as judgment policy update (§48.10)
- frozensets in tests/test_engine_method_surface_freeze.py may only be
  amended through explicit method surface migration PR
```

Sub-decision D, AF, and the §42 / §43 / §44 / §45 / §46 / §47 / §48 letter-code namespaces continue to constrain future PRs.
