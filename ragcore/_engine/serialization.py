"""ragcore._engine.serialization — snapshot encode / decode / migration / validation.

Phase 1 of the Engine v1 refactoring plan. This module owns the low-level
serialization helpers, snapshot migration, restore-integrity validation, and
reconstruction into a DecodedEngineState (the decode/install boundary).

It imports ragcore.types + stdlib only and never imports ragcore.engine (no
import cycle). Claim-status admission remains in Engine because it belongs to
the confidence status domain (it depends on _VALID_CLAIM_STATUSES, derived from
the confidence _STATUS_TO_MODIFIER); the integrity validators here are
confidence-free.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ragcore.types import (
    ClaimLifecycleEvent,
    Claim,
    Entity,
    Evidence,
    Gap,
    Observation,
    Relation,
    RuleDefinition,
    RuleStats,
    ScoreValue,
)


# ---- Snapshot schema version + migration framework (PR18-K §30 / PR21-L §33) ----
_CURRENT_SNAPSHOT_SCHEMA_VERSION = 2
_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS: frozenset[int] = frozenset({1, 2})


def _migrate_snapshot_v1_to_v2(snapshot: dict[str, Any]) -> dict[str, Any]:
    """PR21-L §33 — v1 snapshot 을 v2 로 승격.

    Sub-decision AH: hint_evidence_types 기본값 = 빈 list.
    input snapshot 은 mutate 하지 않음 (얕은 사본).

    v1 snapshot 은 hint_evidence_types 키를 가지지 않는다 → 빈 list 로 채움.
    schema_version 도 2 로 갱신.
    """
    out = dict(snapshot)
    out["schema_version"] = 2
    out["hint_evidence_types"] = []
    return out


def _migrate_snapshot_to_current(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Bring a snapshot up to the current schema version.

    Chain (PR21-L §33):
        v1 → v2 (PR21-L step: add hint_evidence_types default)
        v2 → CURRENT: identity

    Returns:
        Snapshot dict at current schema version. Input dict 는 mutate 하지 않음.

    Raises:
        ValueError: missing schema_version, unsupported version.
    """
    version = snapshot.get("schema_version")
    if version is None:
        raise ValueError("Snapshot schema_version is required")
    if version not in _SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS:
        raise ValueError(
            f"Unsupported snapshot schema_version: {version}; "
            f"supported: {sorted(_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS)}"
        )
    if version == 1:
        snapshot = _migrate_snapshot_v1_to_v2(snapshot)
        version = snapshot["schema_version"]
    if version == _CURRENT_SNAPSHOT_SCHEMA_VERSION:
        return dict(snapshot)  # identity (shallow copy)
    # 미래 자리: 중간 버전 → CURRENT 변환 chain (예: v2 → v3)
    raise ValueError(
        f"Unsupported snapshot schema_version: {version}"
    )


# ============================================================================
# Region M  —  Dataclass restore from dict (module-level)
# See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region M
# ============================================================================

# ---- Persistence serialization helpers (PR17 §29) -------------------------
# PR12-D 다음 / Persistence (PR17 §29) 직렬화 보조. 결정성 (sorted) 보장.

def _sv_to_dict(sv: ScoreValue | None) -> dict[str, float] | None:
    """ScoreValue or None → dict or None."""
    if sv is None:
        return None
    return {"value": sv.value}


def _sv_from_dict(d: dict[str, float] | None) -> ScoreValue | None:
    """dict or None → ScoreValue or None."""
    if d is None:
        return None
    return ScoreValue(value=d["value"])


def _entity_from_dict(d: dict[str, Any]) -> Entity:
    return Entity(**d)


def _observation_from_dict(d: dict[str, Any]) -> Observation:
    return Observation(**d)


def _claim_from_dict(d: dict[str, Any]) -> Claim:
    d = dict(d)
    d["base_confidence"] = _sv_from_dict(d["base_confidence"])
    return Claim(**d)


def _evidence_from_dict(d: dict[str, Any]) -> Evidence:
    d = dict(d)
    d["strength"] = _sv_from_dict(d["strength"])
    return Evidence(**d)


def _relation_from_dict(d: dict[str, Any]) -> Relation:
    return Relation(**d)


def _gap_from_dict(d: dict[str, Any]) -> Gap:
    d = dict(d)
    d["severity"] = _sv_from_dict(d["severity"])
    return Gap(**d)


def _rule_def_from_dict(d: dict[str, Any]) -> RuleDefinition:
    d = dict(d)
    d["prior_confidence"] = _sv_from_dict(d["prior_confidence"])
    return RuleDefinition(**d)


def _rule_stats_from_dict(d: dict[str, Any]) -> RuleStats:
    d = dict(d)
    d["observed_precision"] = _sv_from_dict(d.get("observed_precision"))
    d["false_positive_rate"] = _sv_from_dict(d.get("false_positive_rate"))
    return RuleStats(**d)


# ============================================================================
# Region N  —  Dict serialize / restore helpers (module-level)
# See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region N
# ============================================================================


def _serialize_dict_int_dataclass(d: dict[int, Any]) -> list[dict[str, Any]]:
    """dict[int, dataclass] → sorted list of {key: int, value: asdict}."""
    return [{"key": k, "value": asdict(v)} for k, v in sorted(d.items())]


def _serialize_dict_tuple_dataclass(
    d: dict[tuple[int, int], Any],
) -> list[dict[str, Any]]:
    """dict[tuple[int, int], dataclass] → sorted list of {key: list, value: asdict}."""
    return [
        {"key": list(k), "value": asdict(v)}
        for k, v in sorted(d.items())
    ]


def _serialize_dict_tuple4_int(
    d: dict[tuple[int, int, int, int], int],
) -> list[dict[str, Any]]:
    """dict[tuple4, int] → sorted list of {key: list[4], value: int}."""
    return [
        {"key": list(k), "value": v}
        for k, v in sorted(d.items())
    ]


def _serialize_dict_int_set(d: dict[int, set[int]]) -> list[dict[str, Any]]:
    """dict[int, set[int]] → sorted list of {key: int, value: sorted list}."""
    return [
        {"key": k, "value": sorted(v)}
        for k, v in sorted(d.items())
    ]


def _serialize_dict_int_int(d: dict[int, int]) -> list[dict[str, int]]:
    """dict[int, int] → sorted list of {key: int, value: int}."""
    return [{"key": k, "value": v} for k, v in sorted(d.items())]


def _serialize_dict_int_list_dataclass(
    d: dict[int, list[Any]],
) -> list[dict[str, Any]]:
    """dict[int, list[dataclass]] → sorted list of {key: int, value: list of asdict}."""
    return [
        {"key": k, "value": [asdict(item) for item in v]}
        for k, v in sorted(d.items())
    ]


def _restore_dict_int(
    items: list[dict[str, Any]], from_dict: Any,
) -> dict[int, Any]:
    """list of {key: int, value: dict} → dict[int, dataclass]."""
    return {item["key"]: from_dict(item["value"]) for item in items}


def _restore_dict_tuple(
    items: list[dict[str, Any]], from_dict: Any,
) -> dict[tuple[int, int], Any]:
    """list of {key: list[2], value: dict} → dict[tuple[int,int], dataclass]."""
    return {tuple(item["key"]): from_dict(item["value"]) for item in items}


# PR35-O7 §47 S1 — restore helper symmetry completion.
# Each helper below mirrors a _serialize_dict_* helper above.

def _restore_dict_tuple4_int(
    items: list[dict[str, Any]],
) -> dict[tuple[int, int, int, int], int]:
    """list of {key: list[4], value: int} → dict[tuple4, int].

    Mirrors _serialize_dict_tuple4_int.
    """
    return {tuple(item["key"]): item["value"] for item in items}


def _restore_dict_int_set(
    items: list[dict[str, Any]],
) -> dict[int, set[int]]:
    """list of {key: int, value: list[int]} → dict[int, set[int]].

    Mirrors _serialize_dict_int_set.
    """
    return {item["key"]: set(item["value"]) for item in items}


def _restore_dict_int_int(
    items: list[dict[str, int]],
) -> dict[int, int]:
    """list of {key: int, value: int} → dict[int, int].

    Mirrors _serialize_dict_int_int.
    """
    return {item["key"]: item["value"] for item in items}


def _restore_dict_int_list_dataclass(
    items: list[dict[str, Any]], from_dict: Any,
) -> dict[int, list[Any]]:
    """list of {key: int, value: list[dict]} → dict[int, list[dataclass]].

    Mirrors _serialize_dict_int_list_dataclass.
    """
    return {
        item["key"]: [from_dict(d) for d in item["value"]]
        for item in items
    }


# ============================================================================
# Restore-integrity validators (Phase 1: relocated from engine.py; pure —
# snapshot structure / reference / counter checks, no confidence dependency)
# ============================================================================

# ---- Snapshot restore integrity (PR67-P03 §52) ----
# Engine 내부 private — public export 안 함.
# §52 — pre-validate cross-reference, set/index, identity, and counter
# integrity. Runs after _migrate_snapshot_to_current and before the §51
# Claim.status admission pass and engine state population, so a rejected
# snapshot never produces an observable Engine. (§52.6/§52.11 leave the
# relative §51/§52 order to the implementation.)

_SNAPSHOT_REQUIRED_KEYS: tuple[str, ...] = (
    "schema_version", "next_id", "lifecycle_seq",
    "entities", "observations", "claims", "evidences", "relations", "gaps",
    "rule_definitions", "rule_stats", "gap_dedup_index",
    "claim_gap_refs", "gap_resolutions",
    "contradictions", "resolved_contradictions",
    "claim_lifecycle_events", "hint_evidence_types",
)

# Mapping from _allocate_id(kind) name -> snapshot top-level collection
# whose ID set bounds the counter. See §52.5.
_COUNTER_KIND_TO_COLLECTION: dict[str, str] = {
    "entity": "entities",
    "observation": "observations",
    "claim": "claims",
    "evidence": "evidences",
    "relation": "relations",
    "gap": "gaps",
}


def _exact_int(value: object) -> bool:
    """True iff ``value`` is a built-in int and not a bool (§51.2 rule)."""
    return type(value) is int and not isinstance(value, bool)


def _collect_id_set(snapshot: dict, name: str) -> set:
    """Validate a scalar int-keyed serialized collection and return its key
    set.

    §52.7 / §52.1.3 / §52.7.2:
        TypeError  — non-list collection, non-dict entry, or a non-exact-int
                     entry key (bool / float / str / None / int subclass /
                     IntEnum, no coercion).
        ValueError — missing 'key'/'value', or a duplicate entry key.

    Exact-int validation runs before the key is used downstream so ``"1"`` /
    ``None`` are rejected here rather than failing through an incidental
    comparison in a later counter check (§52.5).
    """
    items = snapshot[name]
    if not isinstance(items, list):
        raise TypeError(
            f"snapshot[{name!r}] must be a list, got {type(items).__name__}"
        )
    ids: set = set()
    for item in items:
        if not isinstance(item, dict):
            raise TypeError(
                f"snapshot[{name!r}] entry must be a dict, got "
                f"{type(item).__name__}"
            )
        if "key" not in item or "value" not in item:
            raise ValueError(
                f"snapshot[{name!r}] entry must carry 'key' and 'value'"
            )
        key = item["key"]
        if not _exact_int(key):
            raise TypeError(
                f"snapshot[{name!r}] entry key must be a built-in int "
                f"(bool excluded), got {type(key).__name__}"
            )
        if key in ids:
            raise ValueError(
                f"snapshot[{name!r}] has a duplicate entry key {key}"
            )
        ids.add(key)
    return ids


def _validate_identity_collection(
    snapshot: dict, name: str, arity: int,
) -> list:
    """Validate a serialized logical-identity collection (``rule_definitions``
    / ``rule_stats`` / ``gap_dedup_index``) and return ``[(logical_key,
    value), ...]``.

    §52.7.1 exception taxonomy:
        TypeError  — non-list collection, a key that is not a list, or a key
                     component that is not an exact built-in int.
        ValueError — missing 'key'/'value', a key whose length != ``arity``,
                     or a duplicate logical key (§52.7.2).
    """
    items = snapshot[name]
    if not isinstance(items, list):
        raise TypeError(
            f"snapshot[{name!r}] must be a list, got {type(items).__name__}"
        )
    seen: set = set()
    result: list = []
    for item in items:
        if (
            not isinstance(item, dict)
            or "key" not in item
            or "value" not in item
        ):
            raise ValueError(
                f"snapshot[{name!r}] entries must carry 'key' and 'value'"
            )
        key = item["key"]
        if not isinstance(key, list):
            raise TypeError(
                f"{name} key must be a {arity}-element list, got "
                f"{type(key).__name__}"
            )
        if len(key) != arity:
            raise ValueError(
                f"{name} key must be a {arity}-element list, got length "
                f"{len(key)}"
            )
        for component in key:
            if not _exact_int(component):
                raise TypeError(
                    f"{name} key component must be a built-in int "
                    f"(bool excluded), got {type(component).__name__}"
                )
        logical = tuple(key)
        if logical in seen:
            raise ValueError(
                f"{name} has a duplicate logical key {list(logical)}"
            )
        seen.add(logical)
        result.append((logical, item["value"]))
    return result


def _validate_snapshot_restore_integrity(snapshot: dict) -> None:
    """§52 — fail-fast snapshot restore integrity check.

    Runs after ``_migrate_snapshot_to_current`` (so ``snapshot`` is at
    the current schema_version) and before the §51 Claim.status admission
    pass and before any Engine state is populated (§52.6/§52.11 leave the
    relative §51/§52 order to the implementation).

    Raises:
        TypeError: structural type violation (snapshot not a dict; a
            required collection not a list; an item not a dict;
            gap_dedup_index key not a 4-list of ints; rule_stats key not
            a 2-list of ints; next_id value not a built-in int).
        ValueError: broken reference / subset / index target relation,
            invalid counter value, missing required top-level key, or
            missing 'key'/'value' inside a collection item.

    Never raises a bare ``KeyError`` from snapshot lookups (§52.7).
    """
    if not isinstance(snapshot, dict):
        raise TypeError(
            f"snapshot must be a dict, got {type(snapshot).__name__}"
        )
    for required in _SNAPSHOT_REQUIRED_KEYS:
        if required not in snapshot:
            raise ValueError(
                f"snapshot is missing required top-level key {required!r}"
            )

    # §52.1 / §52.1.3 / §52.7.2 — structural + exact-int key + duplicate-key
    # validation for every scalar int-keyed collection. Runs before any
    # cross-reference, counter, or value-restoration step so a malformed key
    # never fails through an incidental comparison.
    id_sets = {
        name: _collect_id_set(snapshot, name)
        for name in (
            "entities", "observations", "claims", "evidences", "relations",
            "gaps", "claim_gap_refs", "gap_resolutions", "contradictions",
            "resolved_contradictions", "claim_lifecycle_events",
        )
    }
    claim_ids = id_sets["claims"]
    evidence_ids = id_sets["evidences"]
    gap_ids = id_sets["gaps"]
    entity_ids = id_sets["entities"]
    observation_ids = id_sets["observations"]
    relation_ids = id_sets["relations"]

    # §52 (G-P02-06) — for claims/evidences/gaps the surrounding serialized
    # ``key`` must equal ``value['id']`` (not extended to other collections).
    for _name in ("claims", "evidences", "gaps"):
        for item in snapshot[_name]:
            value = item["value"]
            if not isinstance(value, dict):
                raise TypeError(
                    f"snapshot[{_name!r}] entry value must be a dict, got "
                    f"{type(value).__name__}"
                )
            if "id" not in value:
                raise ValueError(
                    f"snapshot[{_name!r}] entry value is missing 'id'"
                )
            if value["id"] != item["key"]:
                raise ValueError(
                    f"snapshot[{_name!r}] entry key {item['key']!r} does not "
                    f"match value id {value['id']!r}"
                )

    # §52.2.1 Evidence -> Claim
    for item in snapshot["evidences"]:
        value = item["value"]
        if not isinstance(value, dict) or "claim_id" not in value:
            raise ValueError(
                f"Evidence entry {item.get('key')!r} must carry a value "
                "dict with 'claim_id'"
            )
        ev_claim_id = value["claim_id"]
        if ev_claim_id not in claim_ids:
            raise ValueError(
                f"Evidence {item['key']} references unknown Claim "
                f"{ev_claim_id}"
            )

    # §52.2.2 Contradiction -> Claim and Evidence
    contradictions_collection = snapshot["contradictions"]
    if not isinstance(contradictions_collection, list):
        raise TypeError(
            "snapshot['contradictions'] must be a list, got "
            f"{type(contradictions_collection).__name__}"
        )
    contradictions_index: dict = {}
    for item in contradictions_collection:
        if not isinstance(item, dict) or "key" not in item or "value" not in item:
            raise ValueError(
                "snapshot['contradictions'] entries must carry 'key' and 'value'"
            )
        c_claim = item["key"]
        if c_claim not in claim_ids:
            raise ValueError(
                f"contradiction references unknown Claim {c_claim}"
            )
        bucket = item["value"]
        if not isinstance(bucket, (list, set, tuple)):
            raise TypeError(
                f"contradiction[{c_claim}] value must be a list/set/tuple, "
                f"got {type(bucket).__name__}"
            )
        for ev_id in bucket:
            if ev_id not in evidence_ids:
                raise ValueError(
                    f"contradiction[{c_claim}] references unknown Evidence "
                    f"{ev_id}"
                )
        contradictions_index[c_claim] = set(bucket)

    # §52.2.3 Claim-gap reference integrity
    cgr_collection = snapshot["claim_gap_refs"]
    if not isinstance(cgr_collection, list):
        raise TypeError(
            "snapshot['claim_gap_refs'] must be a list, got "
            f"{type(cgr_collection).__name__}"
        )
    for item in cgr_collection:
        if not isinstance(item, dict) or "key" not in item or "value" not in item:
            raise ValueError(
                "snapshot['claim_gap_refs'] entries must carry 'key' and 'value'"
            )
        cg_claim = item["key"]
        if cg_claim not in claim_ids:
            raise ValueError(
                f"claim_gap_refs references unknown Claim {cg_claim}"
            )
        bucket = item["value"]
        if not isinstance(bucket, (list, set, tuple)):
            raise TypeError(
                f"claim_gap_refs[{cg_claim}] value must be a list/set/tuple, "
                f"got {type(bucket).__name__}"
            )
        for gap_id in bucket:
            if gap_id not in gap_ids:
                raise ValueError(
                    f"claim_gap_refs[{cg_claim}] references unknown Gap "
                    f"{gap_id}"
                )

    # §52.2.4 Gap resolution reference integrity
    resolutions = snapshot["gap_resolutions"]
    if not isinstance(resolutions, list):
        raise TypeError(
            "snapshot['gap_resolutions'] must be a list, got "
            f"{type(resolutions).__name__}"
        )
    for item in resolutions:
        if not isinstance(item, dict) or "key" not in item or "value" not in item:
            raise ValueError(
                "snapshot['gap_resolutions'] entries must carry 'key' and 'value'"
            )
        gap_id = item["key"]
        if gap_id not in gap_ids:
            raise ValueError(
                f"gap_resolutions references unknown Gap {gap_id}"
            )
        ev_id = item["value"]
        if ev_id not in evidence_ids:
            raise ValueError(
                f"gap_resolutions[{gap_id}] references unknown Evidence "
                f"{ev_id}"
            )

    # §52.3.1 Gap dedup index — §52.7.1 identity-key taxonomy (wrong container
    # / component type -> TypeError; wrong length -> ValueError; duplicate
    # logical key -> ValueError) + target gap_id resolves to a restored Gap.
    for _key, target in _validate_identity_collection(
        snapshot, "gap_dedup_index", 4,
    ):
        if target not in gap_ids:
            raise ValueError(
                f"gap_dedup_index target references unknown Gap {target}"
            )

    # §52.3.2 resolved_contradictions ⊆ contradictions[claim_id]
    resolved = snapshot["resolved_contradictions"]
    if not isinstance(resolved, list):
        raise TypeError(
            "snapshot['resolved_contradictions'] must be a list, got "
            f"{type(resolved).__name__}"
        )
    for item in resolved:
        if not isinstance(item, dict) or "key" not in item or "value" not in item:
            raise ValueError(
                "snapshot['resolved_contradictions'] entries must carry "
                "'key' and 'value'"
            )
        rc_claim = item["key"]
        if rc_claim not in claim_ids:
            raise ValueError(
                f"resolved_contradictions references unknown Claim {rc_claim}"
            )
        bucket = item["value"]
        if not isinstance(bucket, (list, set, tuple)):
            raise TypeError(
                f"resolved_contradictions[{rc_claim}] value must be a "
                f"list/set/tuple, got {type(bucket).__name__}"
            )
        # §52.3.2 (G-P03-RESOLVED-EMPTY) — the contradictions key is required
        # for every entry, including an empty resolved bucket.
        if rc_claim not in contradictions_index:
            raise ValueError(
                f"resolved_contradictions[{rc_claim}] has no matching "
                "contradictions entry"
            )
        registered = contradictions_index.get(rc_claim, set())
        for ev_id in bucket:
            if ev_id not in registered:
                raise ValueError(
                    f"resolved_contradictions[{rc_claim}] includes Evidence "
                    f"{ev_id} not registered in contradictions"
                )

    # §52.4 RuleStats identity shape — §52.7.1 taxonomy + duplicate logical
    # key. Identity is NOT required to match a registered rule_definitions
    # entry (advisory unregistered references preserved).
    _validate_identity_collection(snapshot, "rule_stats", 2)
    # rule_definitions serialized identity key shape (same taxonomy). This is
    # structural only and does not require a matching rule_stats entry.
    _validate_identity_collection(snapshot, "rule_definitions", 2)

    # §52.7 — hint_evidence_types must be a list (deliberate structural check
    # so a non-list does not fall through to an incidental set() error).
    hint_types = snapshot["hint_evidence_types"]
    if not isinstance(hint_types, list):
        raise TypeError(
            "snapshot['hint_evidence_types'] must be a list, got "
            f"{type(hint_types).__name__}"
        )

    # §52.5 Counter integrity
    next_id = snapshot["next_id"]
    if not isinstance(next_id, dict):
        raise TypeError(
            f"snapshot['next_id'] must be a dict, got {type(next_id).__name__}"
        )
    for kind, collection_name in _COUNTER_KIND_TO_COLLECTION.items():
        restored_ids = id_sets[collection_name]
        max_restored = max(restored_ids) if restored_ids else 0
        if kind in next_id:
            counter = next_id[kind]
            if not _exact_int(counter):
                raise TypeError(
                    f"next_id[{kind!r}] must be a built-in int (bool "
                    f"excluded), got {type(counter).__name__}"
                )
            if counter < 0:
                raise ValueError(
                    f"next_id[{kind!r}] must be >= 0, got {counter}"
                )
            if counter < max_restored:
                raise ValueError(
                    f"next_id[{kind!r}]={counter} is below max restored "
                    f"ID {max_restored}; collision risk"
                )
        else:
            # §52.5 — a missing kind is treated as zero; valid only if no
            # restored IDs exist for that kind.
            if max_restored > 0:
                raise ValueError(
                    f"next_id[{kind!r}] is missing but max restored ID "
                    f"is {max_restored}; collision risk"
                )


# ============================================================================
# Decode / install boundary (Phase 1) — explicit state-projection between the
# Engine and snapshot persistence. encode_snapshot serializes a state view;
# validate_and_decode_snapshot migrates + validates + reconstructs into a
# DecodedEngineState. Engine-specific claim-status admission and lineage stay
# in Engine; this module performs neither.
# ============================================================================

from dataclasses import dataclass


@dataclass
class DecodedEngineState:
    """Validated, reconstructed PERSISTED Engine state. Holds only persisted
    state; the runtime state-identity lineage is NOT part of this and is
    freshly allocated by Engine on install."""
    next_id: dict
    lifecycle_seq: int
    entities: dict
    observations: dict
    claims: dict
    evidences: dict
    relations: dict
    gaps: dict
    rule_definitions: dict
    rule_stats: dict
    gap_dedup_index: dict
    claim_gap_refs: dict
    gap_resolutions: dict
    contradictions: dict
    resolved_contradictions: dict
    claim_lifecycle_events: dict
    hint_evidence_types: set


def encode_snapshot(state: DecodedEngineState) -> dict[str, Any]:
    """Serialize a persisted-state view to a JSON-compatible snapshot dict.
    Deterministic — all set/dict iteration is sorted."""
    return {
        "schema_version": _CURRENT_SNAPSHOT_SCHEMA_VERSION,
        "next_id": dict(sorted(state.next_id.items())),
        "lifecycle_seq": state.lifecycle_seq,
        "entities": _serialize_dict_int_dataclass(state.entities),
        "observations": _serialize_dict_int_dataclass(state.observations),
        "claims": _serialize_dict_int_dataclass(state.claims),
        "evidences": _serialize_dict_int_dataclass(state.evidences),
        "relations": _serialize_dict_int_dataclass(state.relations),
        "gaps": _serialize_dict_int_dataclass(state.gaps),
        "rule_definitions": _serialize_dict_tuple_dataclass(state.rule_definitions),
        "rule_stats": _serialize_dict_tuple_dataclass(state.rule_stats),
        "gap_dedup_index": _serialize_dict_tuple4_int(state.gap_dedup_index),
        "claim_gap_refs": _serialize_dict_int_set(state.claim_gap_refs),
        "gap_resolutions": _serialize_dict_int_int(state.gap_resolutions),
        "contradictions": _serialize_dict_int_set(state.contradictions),
        "resolved_contradictions": _serialize_dict_int_set(state.resolved_contradictions),
        "claim_lifecycle_events": _serialize_dict_int_list_dataclass(
            state.claim_lifecycle_events,
        ),
        "hint_evidence_types": sorted(state.hint_evidence_types),
    }


def validate_and_decode_snapshot(snapshot: dict[str, Any]) -> DecodedEngineState:
    """Migrate + integrity-validate + reconstruct a snapshot into a
    DecodedEngineState. Performs NO Engine-specific claim-status admission
    (that stays in Engine) and constructs no Engine. Raises TypeError /
    ValueError per the §52.7 contract surface."""
    if not isinstance(snapshot, dict):
        raise TypeError(
            f"snapshot must be a dict, got {type(snapshot).__name__}"
        )
    snapshot = _migrate_snapshot_to_current(snapshot)
    _validate_snapshot_restore_integrity(snapshot)
    try:
        # A claim "status" field is REQUIRED. A MISSING status is a ValueError
        # (preserving the pre-refactor behavior where claim-status admission
        # ran on the raw snapshot). A wrong-TYPE field stays a TypeError per
        # the §52.7 surface — the integrity validator above already checked
        # container types, so we do NOT broadly convert reconstruct TypeErrors.
        for _item in snapshot["claims"]:
            if "status" not in _item["value"]:
                raise ValueError(
                    "snapshot restore failed: missing required nested field "
                    "'status'"
                )
        return DecodedEngineState(
            next_id=dict(snapshot.get("next_id", {})),
            lifecycle_seq=snapshot.get("lifecycle_seq", 0),
            entities=_restore_dict_int(snapshot["entities"], _entity_from_dict),
            observations=_restore_dict_int(snapshot["observations"], _observation_from_dict),
            claims=_restore_dict_int(snapshot["claims"], _claim_from_dict),
            evidences=_restore_dict_int(snapshot["evidences"], _evidence_from_dict),
            relations=_restore_dict_int(snapshot["relations"], _relation_from_dict),
            gaps=_restore_dict_int(snapshot["gaps"], _gap_from_dict),
            rule_definitions=_restore_dict_tuple(snapshot["rule_definitions"], _rule_def_from_dict),
            rule_stats=_restore_dict_tuple(snapshot["rule_stats"], _rule_stats_from_dict),
            gap_dedup_index=_restore_dict_tuple4_int(snapshot["gap_dedup_index"]),
            claim_gap_refs=_restore_dict_int_set(snapshot["claim_gap_refs"]),
            gap_resolutions=_restore_dict_int_int(snapshot["gap_resolutions"]),
            contradictions=_restore_dict_int_set(snapshot["contradictions"]),
            resolved_contradictions=_restore_dict_int_set(snapshot["resolved_contradictions"]),
            claim_lifecycle_events=_restore_dict_int_list_dataclass(
                snapshot["claim_lifecycle_events"],
                lambda d: ClaimLifecycleEvent(**d),
            ),
            hint_evidence_types=set(snapshot["hint_evidence_types"]),
        )
    except KeyError as exc:
        missing = exc.args[0] if exc.args else None
        raise ValueError(
            "snapshot restore failed: missing required nested field "
            f"{missing!r}"
        ) from exc
