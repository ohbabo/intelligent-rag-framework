"""ragcore._engine.serialization — pure snapshot encode / decode / migration.

Phase 1 of the Engine v1 refactoring plan: the snapshot serialization helpers
(already module-level in engine.py) are relocated here so Engine is a thinner
orchestrator. PURE functions only — imports ragcore.types + stdlib and MUST
NOT import ragcore.engine (no import cycle). Validators and claim-status
admission stay in engine.py (entangled with the Phase-2 confidence constants).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ragcore.types import (
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
