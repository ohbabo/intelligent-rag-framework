# Engine v1 Refactoring Plan

```
status:   PROPOSAL — revised after two independent review rounds (not yet normative)
type:     docs-only architecture plan
base:     main aaa8024 (post-#81 squash; "Post-merge audit reconciliation")
scope:    ragcore/engine.py internal structure only
```

> **Goal: finalize the internal structure of the v1 Engine so that v2
> (physics-engine extension) can build on a clean, modular core —
> without changing the *defined external contract*. "Algorithm can
> evolve; the integration boundary must be complete."**

This is a **plan**, not an implementation. It was revised across two
independent review rounds (§0). The corrected plan separates the
**defined external contract** (frozen) from **implementation-location
test locks** (intentionally migrated) and from **contract items the
current tests do not yet cover** (added as Phase-0 characterization),
grounds every measurement in AST, and defers the decomposition shape
to a separate decision-gate PR.

---

## §0 Review-round corrections

### Round 1 (baseline / measurement / pure-extraction)
```
R1  Baseline re-measured on main aaa8024 (was mislabelled c17b833 over
    a 6d43cd8 base; #81 now merged).
R2  Engine.from_snapshot is 72 lines (AST), not 296; the 269-line
    _validate_snapshot_restore_integrity is already module-level.
R3  The freeze tests lock implementation LOCATION (in-source helper
    regex counts; AST class-body 42/20), not 42 signatures.
R4  from_snapshot and the confidence cluster are not pure; only the
    decode step and the arithmetic kernel are.
R5  Supersedes ENGINE_INTERNAL_MAP §3 implementation-location locks
    (§8.5), preserving every externally-observable guarantee.
```

### Round 2 (precise test-coverage taxonomy)
```
G2  Snapshot KEY ORDER is NOT currently enforced. The test asserts
    frozenset(keys) == locked set + len == 18 only. Key order is a
    contract item with NO current test → Phase-0 characterization to
    ADD (not "already locked").
G3  The forbidden-import test scans ragcore.engine SOURCE only. After
    code moves to ragcore/_engine/, that scope misses the private
    package → Phase 0 must enforce the import policy PACKAGE-WIDE.
G4  private == 20 is NOT an external contract and the plan itself adds
    a new private (_install). Do NOT re-lock a private total count at
    runtime; delete the total-count assertion and keep only NAMED
    private seams (the 6 modifier helpers).
G5  "1999 passed" must not be frozen per phase: Phase 0 adds/rewrites
    tests. Use "all passing; behavioral baseline preserved; per-PR
    count recorded".
G6  Phase 3A (decision) and 3B (implementation) are SEPARATE PR gates;
    3B is entered only after 3A is reviewed and approved.
G7  Non-goals limited to the DEFINED external contract; non-contract
    introspection deltas are measured at 3A, not assumed zero.
G8  to_snapshot returns a dict, not bytes — a byte claim needs an
    explicit canonical JSON encoding rule (no sort_keys).
G9  The 6 serialization shape families must be exercised by a POPULATED
    fixture; an empty round-trip cannot replace the location regex.
```

---

## §1 Current state (measured on `main` aaa8024, AST-grounded)

```
ragcore/ package          ~4080 lines
  engine.py               2479   ← the refactor target
    = Engine class        1574 lines / 62 methods (42 public / 20 private*)
    + module-level funcs    551 lines / 29 functions (ALREADY outside the class)
    + module scaffolding   ~354 lines (imports, constants, docstrings, blanks)
  condition.py             373   (already modular)
  types.py                 283   (11 frozen dataclasses — clean)
  rule_runtime/output/loader/gap/compile   821   (rule subsystem — already modular)
  __init__.py              122   (public API; __all__ = 50)
  (* private count includes __init__; it is NOT an external contract — see §3.2/§5)

tests/                    52 files / 1999 passing on aaa8024 (baseline, not a frozen total)
```

### §1.1 The Engine class is large but NOT one giant method
Longest Engine *methods*: compute_effective_confidence 82,
_rule_stats_modifier_for_claim 77, from_snapshot 72, add_gap 57,
refute_disputed_claim_if_ready_by_freshness 48, add_claim 45. The size
is **breadth** — 62 methods across ten clusters.

### §1.2 Serialization is ALREADY mostly module-level
551 lines / 29 functions already live outside the class, including
_validate_snapshot_restore_integrity (269), _validate_identity_collection
(54), _collect_id_set (42), the 6+6 _serialize_dict_* / _restore_dict_*
helpers, and the _*_from_dict reconstruction helpers. The blocker to
decomposition is the location-lock tests (§3.2), not the code.

---

## §2 Goals and non-goals

### §2.1 Goals
1. Move `ragcore/engine.py` to a thin public façade plus a private
   `ragcore/_engine/` package, organized by the ten clusters.
2. Relocate the already-module-level serialization helpers and the
   confidence arithmetic kernel into dedicated modules.
3. Leave the v1 Engine's defined external contract identical and the
   structure ready for v2 physics extension.

### §2.2 Non-goals
- **No change to the defined external contract** (§3.1): public method
  surface, snapshot schema/keys/order/values, PR51 packet, `__all__`,
  state-identity and trace semantics, admission/round-trip/lifecycle
  results.
- **Non-contract introspection deltas are NOT assumed zero** (G7).
  `Engine.__dict__` membership, `__qualname__`, `inspect.getsource`,
  `help()` ownership, and declaring class may change under some
  decomposition shapes; these are measured, documented, and explicitly
  accepted or rejected at Phase 3A (§7) — not silently claimed unchanged.
- No new public symbol, dependency, or confidence policy.
- No change to `rule_*.py`, `condition.py`, `types.py`. No v2 physics.

---

## §3 What the tests actually lock (precise taxonomy)

### §3.1 Defined external contract — KEEP frozen
```
public method NAME SET + COUNT (==42)             surface-freeze
6 modifier-helper signatures (named seams)         surface-freeze
ragcore.__all__ == 50                              surface-freeze
snapshot schema_version == 2                        surface-freeze
snapshot top-level key COUNT == 18                  surface-freeze
snapshot top-level key SET (frozenset)              surface-freeze
snapshot top-level is JSON-compatible               surface-freeze
PR51 packet 7 keys                                  inspector tests
state-identity semantics (fresh lineage)            state-identity tests
confidence trace shape + policy id                  trace tests
admission / round-trip / lifecycle RESULTS          integrity + behavioral
no forbidden runtime modules in sys.modules         surface-freeze (runtime half)
```

### §3.2 Implementation-LOCATION assertions — MIGRATE in Phase 0
```
in-source regex count of _serialize_dict_* (==6) and
  _restore_dict_* (==6) in ragcore.engine SOURCE     surface-freeze
AST count of methods DIRECTLY DEFINED in the Engine
  class body: public==42  AND  private==20           integrity test
forbidden-import SOURCE scan covers ragcore.engine
  ONLY (getsource(ragcore.engine))                    surface-freeze (source half)
```
These encode *where code lives*, not what it does. Relocating a helper
or moving a method onto a different unit keeps the runtime contract but
breaks these — so "tests unchanged" is the wrong invariant.

### §3.3 Contract items with NO current test — ADD in Phase 0
```
snapshot top-level key ORDER (G2) — required by contract, frozenset
  test does not check it
canonical JSON byte image of the snapshot (G8) — to_snapshot returns a
  dict; no byte-level test exists
full 42 public-method signatures — only names + count are checked today
import/dependency policy across ragcore._engine (G3) — no test will see
  the private package after Phase 1
```

### §3.4 Required reframing
```
❌ "test assertions unchanged / tests unchanged"
✅ "defined-contract and behavioral expectations preserved;
    §3.2 location assertions are migrated to location-agnostic form in
    Phase 0; §3.3 missing-coverage items are added in Phase 0; each
    migrated/added assertion carries an explicit mapping."
```

---

## §4 Proposed architecture

### §4.1 Pure extraction — limited to the genuinely-pure parts
```
ragcore/_engine/serialization.py
  encode_snapshot(state_view) -> dict               # pure
  validate_and_decode_snapshot(snapshot)
      -> DecodedEngineState                          # pure
  Engine.from_snapshot(snapshot):
      decoded = validate_and_decode_snapshot(snapshot)
      engine  = cls()            # fresh state-identity lineage stays in Engine
      engine._install(decoded)   # only persisted state is applied (new private seam)
      return engine
  => serialization.py imports types/stdlib only; never imports Engine.

ragcore/_engine/confidence.py
  status_modifier(...) / freshness_modifier(...) / gap_modifier(...) /
  count_modifier(...) / rule_stats_modifier(...) / evidence_type_modifier(...) /
  compose_effective_confidence(...)                  # pure arithmetic kernel
  Engine._*_modifier_for_claim(claim_id)             # STAY on Engine — thin
                                                     #  state-reading wrappers (named seams)
  hint-evidence-type API                             # STAYS on Engine (mutates + advances revision)
```

`Engine._install` is a deliberately-introduced private seam (G4); it is
preserved by NAME + signature, not by a private total count.

### §4.2 File/module layout (per §8.1)
```
ragcore/
  engine.py            # public Engine façade (from ragcore.engine import Engine
                       #  unchanged; Engine.__module__ unchanged)
  _engine/
    __init__.py
    serialization.py  confidence.py  lifecycle.py  gaps.py  rules.py  ...
```
`ragcore/engine.py` is NOT replaced by a package directory.

---

## §5 Phased plan (five logical stages, materialized as multiple PRs)

```
Phase 0  Contract-test taxonomy migration   (no production change)
  A. Keep §3.1 external-contract assertions exactly.
  B. Migrate §3.2 location assertions to location-agnostic form:
     - replace in-source _serialize/_restore regex counts with a
       BEHAVIORAL test: one POPULATED Engine fixture that exercises all
       SIX serialization shape families
         (int_dataclass, tuple_dataclass, tuple4_int, int_set, int_int,
          int_list_dataclass)
       via full round-trip, plus focused per-family round-trips where a
       single fixture cannot localize failure (G9). Location-agnostic:
       passes regardless of which module the helpers live in.
     - replace the AST class-body 42/20 count:
         * public  -> runtime contract test: exact count 42 + exact
                      names + exact FULL signatures
         * private -> DELETE the total-private-count assertion; do NOT
                      replace it with another total count. Preserve only
                      NAMED private seams by name + signature: the six
                      _*_modifier_for_claim helpers (and any future seam
                      named explicitly, e.g. _install) (G4).
     - widen the forbidden-import SOURCE scan to a PACKAGE-WIDE
       import/dependency policy over ragcore.engine AND the whole
       ragcore._engine package (string scan or AST/import-graph — chosen
       in the Phase-0 PR — but scope MUST be package-wide) (G3).
  C. Add §3.3 missing characterization tests:
     - exact snapshot top-level KEY ORDER
     - canonical JSON byte image (see §6.4 encoding rule) (G8)
     - full 42 public-signature snapshot
  D. Semantic expectations (values, admission, lifecycle, round-trip,
     malformed-input rejection) UNCHANGED. Existing admission tests
     unchanged (G9).

Phase 1  Extract serialization  -> ragcore/_engine/serialization.py
Phase 2  Extract confidence kernel -> ragcore/_engine/confidence.py

Phase 3A  Architecture decision PR   (docs/audit only, no code move)
  cluster self-call graph; store read/write matrix; introspection delta
  (__dict__/__qualname__/getsource/declaring class); circular-dependency
  analysis; v2 extension seam; SELECTED architecture (mixin vs delegation
  vs module functions on a thin class); explicit Phase-3B entry conditions.

Phase 3B  Implementation PR series   (entered ONLY after 3A approval)
  the selected decomposition, one cluster per PR (or a separately
  justified limited group); full contract suite green after each.

Phase 4  Boundary re-verification + docs
```

Phase numbering: `0 / 1 / 2 / 3A / 3B-1 … 3B-N / 4`. Phases 1–2 may
start once the Phase-0 taxonomy is approved; **3B does not begin before
3A is approved.**

---

## §6 Verification (every phase boundary)

```
1. pytest -q            -> all tests passed (NOT a frozen 1999; the total
                           changes in Phase 0 and is recorded per PR)
2. no behavioral / defined-contract coverage removed; every migrated or
   added assertion has an explicit before→after mapping
3. runtime public surface -> 42 methods, exact names + FULL signatures
4. snapshot                -> see §6.4
5. from_snapshot round-trip -> identical restored state
6. PR51 packet             -> 7 keys, same order
7. ragcore.__all__         -> 50
8. state_identity          -> fresh lineage on Engine() and from_snapshot()
9. git diff                -> only intended files
```

### §6.4 Snapshot characterization (value + order + canonical bytes)
`to_snapshot()` returns a dict, so a byte claim needs an explicit
encoding rule (G8). Three SEPARATE assertions:
```python
assert list(snapshot.keys()) == EXPECTED_TOP_LEVEL_KEY_ORDER     # order
assert snapshot == EXPECTED_SNAPSHOT                              # value
encoded = json.dumps(
    snapshot, ensure_ascii=False, separators=(",", ":"),
).encode("utf-8")
assert encoded == EXPECTED_CANONICAL_BYTES                        # bytes
# sort_keys=True is FORBIDDEN — it would hide a real emission-order change.
```

A phase that cannot keep §6 green is reverted (new corrective commits only).

---

## §7 Why Phase 3 is a decision gate, not a mixin commitment

Mixins preserve `Engine.add_claim` at runtime but change observable
introspection (`Engine.__dict__`, `__qualname__`, `getsource`, `help()`
ownership, AST direct-method count, doc-tool declaring class). "Exact
runtime surface unchanged" is necessary but NOT sufficient. Phase 3A
measures these deltas + the cluster dependency graph and chooses between
(a) mixins, (b) delegation, (c) module functions on a thin class, then
records the decision and explicit 3B entry conditions. Implementation
(3B) is a separate, post-approval PR series (G6).

---

## §8 Decisions (locked with the philosophy track)

```
§8.1 Module layout    engine.py public façade + private ragcore/_engine/
                      package (NOT a ragcore/engine/ package replacement).
§8.2 Confidence       FIXED v1 7-modifier policy. No runtime registry.
                      Order fixed. policy_id = _EFFECTIVE_CONFIDENCE_POLICY_ID.
                      A registry = new order/dup/failure/identity/trace
                      contract = v2, not a refactor.
§8.3 Stores           Keep per-kind dict stores. Generic store = a v2
                      contract once v2 state kinds exist.
§8.4 State identity   Engine revision = count of authoritative COMMITTED
                      logical mutations. Ephemeral/derived physics
                      calculation MUST NOT advance it; only materializing a
                      physics result into authoritative state does (+1 per
                      commit). A future physics trace gets its own identity
                      (source EngineStateIdentity + policy id/version +
                      input identity + derived-result identity).
§8.5 Prior-audit      ENGINE_INTERNAL_MAP.md §3 do-not-touch (a conservative
     supersession     result at 1145 tests) is re-evaluated against today's
                      1999-test surface. This plan SUPERSEDES its
                      implementation-LOCATION locks (snapshot helper
                      placement; key-emission order as a CODE-LAYOUT
                      constraint; method declaration order). Every
                      externally-observable guarantee it protected is
                      preserved by §3.1 + §6; snapshot key ORDER is
                      preserved as a golden-output assertion (§6.4), not a
                      code-layout one.
```

---

## §9 Summary

On `main` aaa8024, `engine.py` is 2479 lines: a 1574-line / 62-method
`Engine` class plus 551 lines of already-module-level serialization
helpers. The real blocker is two **implementation-location** test locks
(in-source helper-count regex; AST class-body 42/20) plus a
**source-scoped** import scan, while some genuine contract items
(snapshot key order, canonical bytes, full signatures, package-wide
import policy) have **no** test today. Phase 0 migrates the location
locks to location-agnostic/behavioral forms, adds the missing
characterization, and — critically — deletes the private total-count
lock rather than recreating it. Phases 1–2 extract only the genuinely-
pure decode and arithmetic kernel; Phase 3A decides the decomposition
shape (separate approval) before any 3B implementation; §8 locks the
façade + private `_engine/` package, fixed v1 confidence policy,
per-kind stores, and committed-mutation revision. The defined external
contract stays provably intact; non-contract introspection deltas are
measured and accepted explicitly, not assumed away.
