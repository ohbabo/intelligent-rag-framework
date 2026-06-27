"""Engine — owns ID allocation and per-kind storage.

Reference implementation. ID 발급은 kind 별 단조 증가 카운터.
참조 무결성: add_* 메서드는 참조 대상이 (kind, id) 쌍으로 정확히 존재해야 통과.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, replace
from typing import Any
from uuid import uuid4

from ragcore.types import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    KIND_CLAIM,
    KIND_ENTITY,
    KIND_EVIDENCE,
    KIND_GAP,
    KIND_OBSERVATION,
    KIND_RELATION,
    Claim,
    ClaimLifecycleEvent,
    EffectiveConfidenceTrace,
    EngineStateIdentity,
    Entity,
    Evidence,
    Gap,
    Observation,
    Relation,
    RuleDefinition,
    RuleStats,
    ScoreValue,
)

from ragcore._engine.serialization import (
    _CURRENT_SNAPSHOT_SCHEMA_VERSION,
    _claim_from_dict,
    _entity_from_dict,
    _evidence_from_dict,
    _gap_from_dict,
    _migrate_snapshot_to_current,
    _observation_from_dict,
    _relation_from_dict,
    _restore_dict_int,
    _restore_dict_int_int,
    _restore_dict_int_list_dataclass,
    _restore_dict_int_set,
    _restore_dict_tuple,
    _restore_dict_tuple4_int,
    _rule_def_from_dict,
    _rule_stats_from_dict,
    _serialize_dict_int_dataclass,
    _serialize_dict_int_int,
    _serialize_dict_int_list_dataclass,
    _serialize_dict_int_set,
    _serialize_dict_tuple4_int,
    _serialize_dict_tuple_dataclass,
)

# Re-export of relocated serialization internals (Phase 1): their definitions
# now live in ragcore._engine.serialization, but they remain reachable as
# ragcore.engine attributes for the existing internal test surface (e.g.
# ragcore.engine._migrate_snapshot_v1_to_v2 / _SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS).
from ragcore._engine.serialization import (  # noqa: F401
    _SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS,
    _migrate_snapshot_v1_to_v2,
    _sv_from_dict,
    _sv_to_dict,
)

# ============================================================================
# Module-level private constants
# ----------------------------------------------------------------------------
# Order follows the 7-modifier composition formula:
#
#   effective = base
#             × status        (4-state modifier)
#             × freshness     (most-recent contradiction strength weight)
#             × gap           (unresolved gap count tier)
#             × count         (repeated-pressure strength averaging)
#             × rule_stats    (maturity × observed_precision)
#             × evidence_type (caller-registered hint set)
#
# Bookended by the refutation-helper threshold (top) and snapshot schema
# version (bottom). All constants are Engine-internal — never exported via
# __all__, never part of the public API surface (PR31-S frozenset).
# ============================================================================

# ---- Refutation helper ----
# PR10-A §22.5 (Sub-decision G): strength-based refutation threshold for
# disputed → refuted. Engine 내부 private — public export 안 함.
# 미래 정책 (freshness / RuleStats / 가중합) 도입 시 자연스럽게 조정/대체.
_REFUTATION_STRENGTH_THRESHOLD = 0.8

# ---- Status modifier (PR11-D §24.8) ----
# Status-only effective confidence multipliers.
# Engine 내부 private — public export 안 함.
# 미래 정책 (gap / contradiction / freshness / RuleStats) 도입 시
# modifier 분해 가능 (예: status × gap × contradiction).
_STATUS_MODIFIER_CANDIDATE = 1.0
_STATUS_MODIFIER_CONFIRMED = 1.0
_STATUS_MODIFIER_DISPUTED = 0.5
_STATUS_MODIFIER_REFUTED = 0.0

_STATUS_TO_MODIFIER: dict[int, float] = {
    CLAIM_STATUS_CANDIDATE: _STATUS_MODIFIER_CANDIDATE,
    CLAIM_STATUS_CONFIRMED: _STATUS_MODIFIER_CONFIRMED,
    CLAIM_STATUS_DISPUTED: _STATUS_MODIFIER_DISPUTED,
    CLAIM_STATUS_REFUTED: _STATUS_MODIFIER_REFUTED,
}

# ---- Effective-confidence calculation policy id (PR76-M07 §7) ----
# Module-private — observable only via
# EffectiveConfidenceTrace.calculation_policy_id. Not re-exported in
# ragcore.__all__. Bump under §7.4 conditions only.
_EFFECTIVE_CONFIDENCE_POLICY_ID = "ragcore.effective-confidence.v1"

# ---- Claim status admission domain (PR65-P01 §51) ----
# Engine 내부 private — public export 안 함.
# Admission gate for Claim.status: only the four registered constants
# are admissible. bool / float / None / str / out-of-range int are rejected
# before any state mutation. See §51.1 / §51.2 / §51.5.
_VALID_CLAIM_STATUSES: frozenset[int] = frozenset(_STATUS_TO_MODIFIER)


def _validate_claim_status_admission(value: object) -> None:
    """§51.2/§51.5 — fail-fast Claim.status admission check.

    Raises:
        TypeError: ``value`` is not a built-in int (includes bool, which
            is an int subclass but rejected for Claim.status).
        ValueError: ``value`` is an int but not one of the four
            admissible status constants.
    """
    # bool is an int subclass; reject explicitly per §51.2.
    if isinstance(value, bool) or type(value) is not int:
        raise TypeError(
            "Claim.status must be a built-in int and one of "
            "CLAIM_STATUS_CANDIDATE / CLAIM_STATUS_CONFIRMED / "
            "CLAIM_STATUS_REFUTED / CLAIM_STATUS_DISPUTED, "
            f"not {type(value).__name__}"
        )
    if value not in _VALID_CLAIM_STATUSES:
        raise ValueError(
            f"Claim.status {value} is not admissible; "
            f"admissible values: {sorted(_VALID_CLAIM_STATUSES)}"
        )


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


# ---- Freshness modifier (PR11-C §26) ----
# freshness modifier 의 strength → penalty 가중치.
# effective = base × status_modifier × (1.0 - most_recent.strength × WEIGHT)
# Engine 내부 private — public export 안 함.
# 0.5 의 의미: "가장 최근 active contradiction 의 strength 가 1.0 이면 modifier 0.5"
_FRESHNESS_PENALTY_WEIGHT = 0.5

# ---- Gap modifier (PR12-D §28 + PR23-M §35) ----
# gap modifier — count-tier (was binary 0.8).
# effective = base × status × freshness × gap × count × rule_stats × evidence_type
# unresolved gap count → tier:
#   0 → 1.0 (gap 없음 또는 모두 resolved, PR12-D Sub-decision T 정신 보존)
#   1 → 0.9 (가장 약한 정보 부족)
#   2 → 0.8 (PR12-D binary 와 동일 지점)
#   3+ → 0.7 (누적 불확실성, hard floor)
# Engine 내부 private — public export 안 함.
# 의미: "정보 부족" 의 약한 신호. lifecycle / contradiction 보다 약함.
# (PR11-D status disputed=0.5 보다 항상 약함 — 0.7 floor > 0.5)
# Sub-decision AS: 구 _GAP_PENALTY_MODIFIER 제거, 4 개 tier 상수로 교체.
_GAP_TIER_ZERO_UNRESOLVED_MODIFIER = 1.0
_GAP_TIER_ONE_UNRESOLVED_MODIFIER = 0.9
_GAP_TIER_TWO_UNRESOLVED_MODIFIER = 0.8
_GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER = 0.7

# ---- Count modifier (PR19-E §31 + PR24-N §36) ----
# count modifier — strength averaging (was binary 0.8).
# effective = base × status × freshness × gap × count × rule_stats × evidence_type
#
# PR19-E (binary, 제거됨):
#   active count >= 2 → 0.8 (repeated-pressure attenuation)
#
# PR24-N (continuous):
#   active count >= 2 → 1.0 - average_active_strength × 0.25
#   active count < 2  → 1.0 (PR11-C freshness 영역 보존)
#
# 핵심 명제 (§36.2):
#   빈 강도의 contradiction 은 repeated pressure 가 아니다.
#
# Center preservation (Sub-decision AY):
#   avg strength 0.8 → 1.0 - 0.8 × 0.25 = 0.8
#   PR19-E binary 0.8 중심점이 자연 재현된다.
#
# Range: count_modifier ∈ [0.75, 1.0] (max 25% attenuation, hard floor 0.75)
# Engine 내부 private — public export 안 함.
# Sub-decision AZ: 구 _COUNT_PENALTY_MODIFIER 제거, 신규 weight 도입.
_COUNT_STRENGTH_PENALTY_WEIGHT = 0.25

# ---- Rule_stats modifier — maturity part (PR20-F §32 + PR26-R §38) ----
# rule_stats modifier — continuous maturity signal.
# effective = base × status × freshness × gap × count × rule_stats × evidence_type
#
# PR20-F (binary, 제거됨):
#   firing_count < 2 → 0.9, 그 외 → 1.0
#
# PR26-R (continuous, Sub-decision BK/BL/BM/BN):
#   clamped = min(max(firing_count, 0), 2)         (Sub-decision BQ defensive clamp)
#   maturity_ratio = clamped / 2
#   modifier = 1.0 - (1.0 - maturity_ratio) × 0.2  (Sub-decision BM)
#
# 핵심 명제 (§38.2):
#   RuleStats modifier is a weak maturity signal, not a rule quality verdict.
#   Continuous refinement separates zero-observation from one-observation
#   without introducing quality judgment.
#
# Mapping:
#   firing_count == 0 → 0.8 (신규, PR20-F 0.9 자연 만료)
#   firing_count == 1 → 0.9 (PR20-F 중심점 자연 재현)
#   firing_count >= 2 → 1.0 (saturated)
#
# Range: rule_stats_modifier ∈ [0.8, 1.0] (max 20% attenuation, floor 0.8)
# 의미: outcome ratio / precision / FPR / timestamp / rule quality verdict 모두 OOS.
# Engine 내부 private — public export 안 함.
# Sub-decision BS: 구 _RULE_STATS_PENALTY_MODIFIER / _MIN_FIRING_COUNT 제거,
#                  신규 weight + saturation 상수 도입.
_RULE_STATS_MATURITY_PENALTY_WEIGHT = 0.2
_RULE_STATS_MATURITY_SATURATION_COUNT = 2

# ---- Rule_stats modifier — precision part (PR29-R §41) ----
# observed_precision modifier — bounded no-boost adjustment signal.
#
# rule_stats_modifier = maturity_modifier × precision_modifier
#
# precision_modifier:
#   observed_precision is None → 1.0
#   observed_precision value p → _RULE_STATS_PRECISION_BASE + p × _RULE_STATS_PRECISION_RANGE
#                              = 0.9 + p × 0.1
#
# Range: [0.9, 1.0], no boost.
#
# 핵심 명제 (§41.1):
#   Observed precision is a bounded adjustment signal, not a rule quality verdict.
#
# 보수적 명제:
#   Observed precision is optional evidence for rule maturity, not ground truth.
#
# Engine 내부 private — public export 안 함.
# Sub-decision J: types.py / __init__.py / rule_output.py 변경 없음.
# Sub-decision H: false_positive_rate 는 PR29-R 에서 사용하지 않음 (OOS).
_RULE_STATS_PRECISION_BASE = 0.9
_RULE_STATS_PRECISION_RANGE = 0.1

# ---- Evidence_type modifier (PR21-L §33) ----
# evidence_type modifier — caller-registered weak source-quality.
# effective = base × status × freshness × gap × count × rule_stats × evidence_type
# direct evidence 전부 caller-registered hint set 에 포함되면 0.9, 그 외 → 1.0.
# Engine 내부 private — public export 안 함.
# 의미: caller 가 "이 type 은 보조 신호" 라고 등록한 경우만 약하게 감쇠.
# framework 는 Evidence.type 정수 의미를 소유하지 않는다 (Sub-decision AF).
# 0.9 (PR20-F rule_stats 와 동일 강도 — 가장 약한 modifier 자리).
_EVIDENCE_TYPE_PENALTY_MODIFIER = 0.9



# ============================================================================
# class Engine — judgment core (domain-light)
# ----------------------------------------------------------------------------
# Public method layout (section markers below match this order):
#
#   Defensive existence checks (private)
#   Entity / Observation / Claim / Evidence
#   Relation / Gap
#   Gap resolution                       (PR5 §17)
#   Claim lifecycle                      (PR6 §18)
#   Claim refutation                     (PR7 §19)
#   Disputed lifecycle                   (PR8 §20)
#   Disputed resolution                  (PR9-A §21)
#   Disputed refutation                  (PR10-A §22)
#   Lifecycle history                    (PR10-B §23)
#   Evidence freshness                   (PR11-A §25)
#   Freshness-aware refutation           (PR11-B §27)
#   Rule registry
#   Modifier helpers (private)           (PR34-O §46 O2 + O3)
#   Persistence snapshot                 (PR17 §29)
#
# All public methods are part of the PR31-S frozen API surface
# (ragcore.__all__ baseline). Private helpers (_*) may be reorganized
# under PR34-O §46 internal optimization constraints — they do not
# affect the public surface or judgment semantics.
# ============================================================================

class Engine:
    # ============================================================================
    # Region B  —  __init__ + private guards
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region B
    # ============================================================================

    def __init__(self) -> None:
        self._next_id: dict[str, int] = {}
        self._entities: dict[int, Entity] = {}
        self._observations: dict[int, Observation] = {}
        self._claims: dict[int, Claim] = {}
        self._evidences: dict[int, Evidence] = {}
        self._relations: dict[int, Relation] = {}
        self._gaps: dict[int, Gap] = {}
        self._rule_definitions: dict[tuple[int, int], RuleDefinition] = {}
        self._rule_stats: dict[tuple[int, int], RuleStats] = {}
        # PR4 §16 — Gap dedup index + claim↔gap reference index.
        # key = (subject_id, created_by_rule, gap_type, required_evidence_type)
        self._gap_dedup_index: dict[tuple[int, int, int, int], int] = {}
        self._claim_gap_refs: dict[int, set[int]] = {}
        # PR5 §17: gap_id -> evidence_id (first registering, no overwrite).
        self._gap_resolutions: dict[int, int] = {}
        # PR7 §19: claim_id -> set of contradicting evidence_ids.
        self._contradictions: dict[int, set[int]] = {}
        # PR9-A §21: claim_id -> set of resolved evidence_ids (subset of contradictions).
        self._resolved_contradictions: dict[int, set[int]] = {}
        # PR10-B §23: lifecycle history (audit trail of status transitions only).
        # per-engine monotonic counter (NOT timestamp, NOT per-claim).
        self._lifecycle_seq: int = 0
        self._claim_lifecycle_events: dict[int, list[ClaimLifecycleEvent]] = {}
        # PR21-L §33: caller-registered hint evidence type ids.
        # framework 는 Evidence.type 정수 의미를 소유하지 않는다 — caller 가
        # register_hint_evidence_types 로 등록한 set 만 modifier 계산에 사용.
        self._hint_evidence_types: set[int] = set()
        # PR73-M04 §1.1 / §4.1 / §4.2 — per-Engine opaque lineage token + a
        # completed-mutation revision counter. NOT persisted to snapshot
        # (§5); a fresh lineage is allocated on Engine() and on
        # from_snapshot() (§4.4). Public surface: state_identity().
        self._state_identity_token: str = uuid4().hex
        self._state_revision: int = 0

    def _allocate_id(self, kind: str) -> int:
        next_id = self._next_id.get(kind, 0) + 1
        self._next_id[kind] = next_id
        return next_id

    def _advance_state_revision(self) -> None:
        """PR73-M04 §2 — advance the completed-mutation revision counter.

        Called from each state-mutating public method **once** at the
        end of its success path (after the underlying state write).
        Never called from a documented no-op or failure path. Read-only
        public methods (including state_identity itself) never call it.
        """
        self._state_revision += 1

    def state_identity(self) -> EngineStateIdentity:
        """PR73-M04 §1.2 — return the current Engine state identity.

        Read-only. Does not mutate Engine state and does not advance
        ``revision``. The returned value carries this Engine's
        process-local lineage token and the count of completed logical
        state changes that have happened within that lineage.

        Comparison is by value equality. The token is opaque; only
        equality is meaningful for callers. Ordered comparison of
        ``revision`` is consistent with mutation order within the same
        lineage and undefined across lineages. See
        ``docs/architecture/ENGINE_STATE_IDENTITY_PRIMITIVE_CONTRACT.md``.
        """
        return EngineStateIdentity(
            engine_token=self._state_identity_token,
            revision=self._state_revision,
        )

    def _storage_for_kind(self, kind: int) -> dict[int, object]:
        mapping: dict[int, dict[int, object]] = {
            KIND_ENTITY: self._entities,  # type: ignore[dict-item]
            KIND_OBSERVATION: self._observations,  # type: ignore[dict-item]
            KIND_CLAIM: self._claims,  # type: ignore[dict-item]
            KIND_EVIDENCE: self._evidences,  # type: ignore[dict-item]
            KIND_RELATION: self._relations,  # type: ignore[dict-item]
            KIND_GAP: self._gaps,  # type: ignore[dict-item]
        }
        if kind not in mapping:
            raise ValueError(f"unknown kind: {kind}")
        return mapping[kind]

    def _id_exists(self, kind: int, target_id: int) -> bool:
        return target_id in self._storage_for_kind(kind)

    # ---- Defensive existence checks (private — PR34-O §46 O1) -------------
    #
    # Centralize the `if X not in self._storage: raise KeyError(...)` pattern
    # so individual public methods don't repeat it. Each helper preserves the
    # exact error message format the original inline check produced. No
    # behavior change — these are dedup helpers only.

    def _assert_entity_exists(self, entity_id: int) -> None:
        if entity_id not in self._entities:
            raise KeyError(f"unknown entity_id: {entity_id}")

    def _assert_claim_exists(self, claim_id: int) -> None:
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")

    def _assert_evidence_exists(self, evidence_id: int) -> None:
        if evidence_id not in self._evidences:
            raise KeyError(f"unknown evidence_id: {evidence_id}")

    def _assert_gap_exists(self, gap_id: int) -> None:
        if gap_id not in self._gaps:
            raise KeyError(f"unknown gap_id: {gap_id}")

    def _assert_rule_pair_exists(self, rule_id: int, rule_version: int) -> None:
        key = (rule_id, rule_version)
        if key not in self._rule_definitions:
            raise KeyError(
                f"unknown rule: rule_id={rule_id}, version={rule_version}"
            )

    def _assert_rule_stats_pair_exists(self, rule_id: int, rule_version: int) -> None:
        key = (rule_id, rule_version)
        if key not in self._rule_stats:
            raise KeyError(
                f"unknown rule: rule_id={rule_id}, version={rule_version}"
            )

    # ============================================================================
    # Region C  —  CRUD layer (Identity + Evidence + Relation)
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region C
    # ============================================================================

    # ---- Entity / Observation / Claim / Evidence ---------------------------

    def add_entity(self, entity_type: int, flags: int = 0) -> int:
        """Add an Entity (subject of claims) and return its assigned entity_id.

        ``entity_type`` 은 caller-domain 정수. framework 가 의미 미소유.
        """
        entity_id = self._allocate_id("entity")
        self._entities[entity_id] = Entity(id=entity_id, type=entity_type, flags=flags)
        self._advance_state_revision()  # PR73-M04 §2.1
        return entity_id

    def get_entity(self, entity_id: int) -> Entity:
        """Return the Entity for ``entity_id``.

        Raises:
            KeyError: unknown entity_id.
        """
        return self._entities[entity_id]

    def add_observation(
        self,
        entity_id: int,
        raw_ref_id: int,
        observation_type: int,
        source_type: int = 0,
    ) -> int:
        """Add an Observation tied to ``entity_id`` and return its observation_id.

        ``raw_ref_id`` 는 caller-side raw data store 의 식별자. framework 는
        raw 데이터를 들고 있지 않다 (외부 통합 경계 §39).

        Raises:
            KeyError: unknown entity_id.
        """
        self._assert_entity_exists(entity_id)
        obs_id = self._allocate_id("observation")
        self._observations[obs_id] = Observation(
            id=obs_id,
            entity_id=entity_id,
            raw_ref_id=raw_ref_id,
            type=observation_type,
            source_type=source_type,
        )
        self._advance_state_revision()  # PR73-M04 §2.1
        return obs_id

    def get_observation(self, observation_id: int) -> Observation:
        """Return the Observation for ``observation_id``.

        Raises:
            KeyError: unknown observation_id.
        """
        return self._observations[observation_id]

    def add_claim(
        self,
        subject_id: int,
        claim_type: int,
        rule_id: int,
        rule_version: int,
        reason_code: int,
        *,
        base_confidence: float = 0.5,
        status: int = CLAIM_STATUS_CANDIDATE,
        flags: int = 0,
    ) -> int:
        """Add a Claim.

        `base_confidence`는 룰 firing 시점의 초기 확신도 (0.0~1.0). 시점
        스냅샷이며 이후 evidence가 들어와도 이 값은 변하지 않는다. 종합
        확신도는 향후 compute_effective_confidence(claim_id) 가 담당.

        `rule_id`/`rule_version`이 등록된 룰을 가리켜야 하는지는 MVP에서
        강제하지 않는다 (advisory). Rule Engine 단계에서 strict 옵션 도입.
        """
        if subject_id not in self._entities:
            # subject_id uses a distinct error label vs add_evidence/add_observation
            # entity_id callers, so keep this inline (helper handles entity_id label).
            raise KeyError(f"unknown subject_id (entity): {subject_id}")
        # §51.3 — reject invalid status before any state mutation.
        _validate_claim_status_admission(status)
        # PR73-M04 §3 C1 — validate base_confidence BEFORE allocating an
        # id so a failed ScoreValue admission cannot consume _next_id
        # while leaving the revision and snapshot unchanged.
        validated_base_confidence = ScoreValue(base_confidence)
        claim_id = self._allocate_id("claim")
        self._claims[claim_id] = Claim(
            id=claim_id,
            subject_id=subject_id,
            type=claim_type,
            status=status,
            created_by_rule=rule_id,
            created_by_rule_version=rule_version,
            reason_code=reason_code,
            base_confidence=validated_base_confidence,
            flags=flags,
        )
        self._advance_state_revision()  # PR73-M04 §2.1
        return claim_id

    def get_claim(self, claim_id: int) -> Claim:
        """Return the Claim for ``claim_id``.

        Read-only: lifecycle 전이를 일으키지 않는다 (§42.3 / §43.9).

        Raises:
            KeyError: unknown claim_id.
        """
        return self._claims[claim_id]

    def add_evidence(
        self,
        claim_id: int,
        raw_ref_id: int,
        evidence_type: int,
        strength: float,
    ) -> int:
        """Add an Evidence supporting ``claim_id`` and return its evidence_id.

        ``evidence_type`` 은 caller-domain 정수 — framework 는 Evidence.type
        의 의미를 소유하지 않는다 (Sub-decision AF). hint 인지 여부는
        ``register_hint_evidence_types`` 로 caller 가 등록한 set 에 의해
        결정 (PR21-L / PR22-S / PR25-T).

        Raises:
            KeyError: unknown claim_id.
        """
        self._assert_claim_exists(claim_id)
        # PR73-M04 §3 C1 — validate strength BEFORE allocating an id so
        # a failed ScoreValue admission cannot consume _next_id while
        # leaving the revision and snapshot unchanged.
        validated_strength = ScoreValue(strength)
        evidence_id = self._allocate_id("evidence")
        self._evidences[evidence_id] = Evidence(
            id=evidence_id,
            claim_id=claim_id,
            raw_ref_id=raw_ref_id,
            type=evidence_type,
            strength=validated_strength,
        )
        self._advance_state_revision()  # PR73-M04 §2.1
        return evidence_id

    def get_evidence(self, evidence_id: int) -> Evidence:
        """Return the Evidence for ``evidence_id``.

        Raises:
            KeyError: unknown evidence_id.
        """
        return self._evidences[evidence_id]

    def evidences_for_claim(self, claim_id: int) -> list[Evidence]:
        """Return all Evidences supporting ``claim_id`` in insertion order.

        contradiction 으로 등록된 evidence 는 별도 ``contradictions_for_claim``
        으로 조회한다 — 같은 evidence_id 가 양쪽에 등록될 수 있다 (PR19 §31).

        Raises:
            KeyError: unknown claim_id.
        """
        self._assert_claim_exists(claim_id)
        return [ev for ev in self._evidences.values() if ev.claim_id == claim_id]

    # ---- Relation / Gap ----------------------------------------------------

    def add_relation(
        self,
        from_kind: int,
        from_id: int,
        to_kind: int,
        to_id: int,
        relation_type: int,
        rule_id: int,
        reason_code: int,
    ) -> int:
        """Add a cross-kind Relation linking ``(from_kind, from_id)`` -> ``(to_kind, to_id)``.

        IDs are kind-independent in this framework (entity:1 and claim:1
        are distinct), so a Relation carries both kind discriminators to
        remain unambiguous about what it connects.

        Raises:
            KeyError: unknown from-side or to-side reference.
            ValueError: unknown kind constant (from ``_storage_for_kind``).
        """
        # _storage_for_kind raises ValueError on unknown kind.
        if not self._id_exists(from_kind, from_id):
            raise KeyError(
                f"unknown from reference: kind={from_kind}, id={from_id}"
            )
        if not self._id_exists(to_kind, to_id):
            raise KeyError(
                f"unknown to reference: kind={to_kind}, id={to_id}"
            )
        relation_id = self._allocate_id("relation")
        self._relations[relation_id] = Relation(
            id=relation_id,
            from_kind=from_kind,
            from_id=from_id,
            to_kind=to_kind,
            to_id=to_id,
            type=relation_type,
            rule_id=rule_id,
            reason_code=reason_code,
        )
        self._advance_state_revision()  # PR73-M04 §2.1
        return relation_id

    def get_relation(self, relation_id: int) -> Relation:
        """Return the Relation for ``relation_id``.

        Raises:
            KeyError: unknown relation_id.
        """
        return self._relations[relation_id]

    # ============================================================================
    # Region D  —  Gap layer
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region D
    # ============================================================================

    def add_gap(
        self,
        claim_id: int,
        gap_type: int,
        required_evidence_type: int,
        severity: float,
        rule_id: int,
    ) -> int:
        """Add a Gap or reuse existing one (PR4 §16 dedup).

        dedup key = ``(subject_id, rule_id, gap_type, required_evidence_type)``.

        Dedup hit:
            기존 Gap 의 ``gap_id`` 반환, 새 Gap 생성 안 함.
            ``Gap.claim_id`` / ``severity`` 도 변경 안 함 (최초 등록 시 값 유지).
            현재 호출의 ``claim_id`` 가 그 gap 을 참조하도록 ``_claim_gap_refs`` 갱신.

        Dedup miss:
            기존처럼 새 Gap 생성, ``_gap_dedup_index`` 등록, ``_claim_gap_refs`` 등록.

        Raises:
            KeyError: ``claim_id`` 가 engine 에 없음.
        """
        self._assert_claim_exists(claim_id)

        # severity 검증은 dedup 분기 전에 한다. severity 는 dedup key 가 아니지만,
        # 입력 검증 의미 (ScoreValue 의 [0.0, 1.0] 검증) 는 dedup hit/miss 모두에서
        # 동일하게 적용되어야 한다. dedup hit 시 검증을 건너뛰면 잘못된 severity 가
        # silent pass 됨 — PR4 이전 add_gap 의 입력 검증 의미와 충돌.
        validated_severity = ScoreValue(severity)

        subject_id = self._claims[claim_id].subject_id
        key = (subject_id, rule_id, gap_type, required_evidence_type)

        if key in self._gap_dedup_index:
            existing_gap_id = self._gap_dedup_index[key]
            # PR73-M04 §2.2 — dedup hit advances revision only when
            # the current Claim's _claim_gap_refs entry actually changes.
            refs = self._claim_gap_refs.setdefault(claim_id, set())
            if existing_gap_id not in refs:
                refs.add(existing_gap_id)
                self._advance_state_revision()
            return existing_gap_id

        gap_id = self._allocate_id("gap")
        self._gaps[gap_id] = Gap(
            id=gap_id,
            claim_id=claim_id,  # first registering claim — §16 의미 약화
            type=gap_type,
            required_evidence_type=required_evidence_type,
            severity=validated_severity,
            created_by_rule=rule_id,
        )
        self._gap_dedup_index[key] = gap_id
        self._claim_gap_refs.setdefault(claim_id, set()).add(gap_id)
        self._advance_state_revision()  # PR73-M04 §2.2 (dedup miss)
        return gap_id

    def get_gap(self, gap_id: int) -> Gap:
        """Return the Gap for ``gap_id``.

        Raises:
            KeyError: unknown gap_id.
        """
        return self._gaps[gap_id]

    def gaps_for_claim(self, claim_id: int) -> list[Gap]:
        """Return Gaps this claim references (PR4 §16 의미 확장).

        이전 (Phase 2): ``gap.claim_id == claim_id`` 필터.
        이후 (PR4):    ``_claim_gap_refs[claim_id]`` 기반.

        dedup 으로 reuse 된 gap 도 포함된다. 반환 순서는 gap_id 오름차순
        (결정적).
        """
        self._assert_claim_exists(claim_id)
        gap_ids = self._claim_gap_refs.get(claim_id, set())
        return sorted(
            (self._gaps[gid] for gid in gap_ids),
            key=lambda g: g.id,
        )

    # ---- Gap resolution (PR5 §17) -----------------------------------------

    def resolve_gaps_for_evidence(self, evidence_id: int) -> tuple[int, ...]:
        """Close matching unresolved gaps using the given evidence.

        매칭 규칙: ``gap.required_evidence_type == evidence.type``.
        검사 범위: ``gaps_for_claim(evidence.claim_id)`` — 이 evidence 가 속한
        claim 이 참조하는 gap 들만. created_by_rule 은 매칭 조건에 포함하지 않는다.

        이미 ``_gap_resolutions`` 에 등록된 gap 은 건너뛴다 (first evidence 유지,
        overwrite 금지). 이번 호출에서 새로 resolved 된 gap_id 들만
        gap_id 오름차순 tuple 로 반환한다.

        Raises:
            KeyError: unknown evidence_id.
        """
        self._assert_evidence_exists(evidence_id)
        evidence = self._evidences[evidence_id]
        newly_resolved: list[int] = []
        for gap in self.gaps_for_claim(evidence.claim_id):
            if gap.required_evidence_type != evidence.type:
                continue
            if gap.id in self._gap_resolutions:
                continue
            self._gap_resolutions[gap.id] = evidence_id
            newly_resolved.append(gap.id)
        newly_resolved.sort()
        if newly_resolved:
            self._advance_state_revision()  # PR73-M04 §2.3
        return tuple(newly_resolved)

    def gap_resolution(self, gap_id: int) -> int | None:
        """Return the evidence_id that resolved this gap, or None if unresolved.

        Raises:
            KeyError: unknown gap_id.
        """
        self._assert_gap_exists(gap_id)
        return self._gap_resolutions.get(gap_id)

    # ============================================================================
    # Region E  —  Lifecycle layer (transitions + contradictions)
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region E
    # ============================================================================

    # ---- Claim lifecycle (PR6 §18) ----------------------------------------

    def confirm_claim_if_ready(self, claim_id: int) -> bool:
        """Promote candidate Claim → confirmed if every referenced Gap is resolved.

        전이 조건 (§18.4):
            - ``claim.status == CLAIM_STATUS_CANDIDATE``
            - ``len(gaps_for_claim(claim_id)) >= 1``
            - 모든 gap 에 ``gap_resolution(gap.id) is not None``

        Returns:
            True  — 이번 호출로 candidate → confirmed 전이 발생.
            False — 전이 없음 (조건 불충족 / 이미 confirmed / refuted / Gap 0개).
                    False 는 실패가 아니다 (no-op 도 False).

        Raises:
            KeyError: unknown claim_id.

        Note:
            Resolved 의 truth-source 는 PR5 §17 의 ``_gap_resolutions`` (gap_id →
            evidence_id). Gap dataclass 에는 status 필드가 없다.
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        if claim.status != CLAIM_STATUS_CANDIDATE:
            return False
        gaps = self.gaps_for_claim(claim_id)
        if not gaps:
            return False
        if not all(self.gap_resolution(g.id) is not None for g in gaps):
            return False
        old_status = claim.status
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_CONFIRMED)
        self._record_claim_lifecycle_transition(
            claim_id, old_status, CLAIM_STATUS_CONFIRMED, "confirm_if_ready",
        )
        self._advance_state_revision()  # PR73-M04 §2.4
        return True

    # ---- Claim refutation (PR7 §19) ---------------------------------------

    def register_contradiction(self, claim_id: int, evidence_id: int) -> bool:
        """Register an explicit contradiction relation: evidence contradicts claim.

        Returns:
            True  — 이번 호출로 새로 등록됨.
            False — (claim_id, evidence_id) 가 이미 등록돼 있음 (idempotent no-op).

        Raises:
            KeyError: unknown claim_id or unknown evidence_id.

        Notes (§19.4):
            - Cross-claim 허용: ``evidence.claim_id == claim_id`` 강제 안 함.
            - Target status 무관: confirmed / refuted claim 에도 등록 가능
              (데이터 등록과 lifecycle 결정은 분리).
            - No semantic inference — 호출자 책임.
        """
        self._assert_claim_exists(claim_id)
        self._assert_evidence_exists(evidence_id)
        bucket = self._contradictions.setdefault(claim_id, set())
        if evidence_id in bucket:
            return False
        bucket.add(evidence_id)
        self._advance_state_revision()  # PR73-M04 §2.3
        return True

    def contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]:
        """Return contradicting evidence_ids for the claim.

        Returns:
            evidence_id 오름차순 tuple. 없으면 빈 tuple.

        Raises:
            KeyError: unknown claim_id.
        """
        self._assert_claim_exists(claim_id)
        return tuple(sorted(self._contradictions.get(claim_id, set())))

    def refute_claim_if_ready(self, claim_id: int) -> bool:
        """Transition candidate → refuted if at least one contradiction is registered.

        전이 조건 (§19.5):
            - ``claim.status == CLAIM_STATUS_CANDIDATE``
            - ``len(contradictions_for_claim(claim_id)) >= 1``

        Returns:
            True  — 이번 호출로 candidate → refuted 전이.
            False — 전이 없음 (조건 불충족 / 이미 confirmed / 이미 refuted).

        Raises:
            KeyError: unknown claim_id.

        Note:
            Gap 상태 (unresolved / resolved) 는 이 결정에 영향 없음 — §19.2 핵심
            명제: "증거 부족 ≠ 반박, 반박은 명시적 contradiction 만이 trigger".
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        if claim.status != CLAIM_STATUS_CANDIDATE:
            return False
        if not self._contradictions.get(claim_id):
            return False
        old_status = claim.status
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_REFUTED)
        self._record_claim_lifecycle_transition(
            claim_id, old_status, CLAIM_STATUS_REFUTED, "refute_if_ready",
        )
        self._advance_state_revision()  # PR73-M04 §2.4
        return True

    # ---- Disputed lifecycle (PR8 §20) -------------------------------------

    def dispute_claim_if_ready(self, claim_id: int) -> bool:
        """Transition confirmed → disputed if at least one contradiction is registered.

        전이 조건 (§20.7):
            - ``claim.status == CLAIM_STATUS_CONFIRMED``
            - ``len(contradictions_for_claim(claim_id)) >= 1``

        Returns:
            True  — 이번 호출로 confirmed → disputed 전이.
            False — 전이 없음 (조건 불충족 / 이미 disputed / candidate / refuted).

        Raises:
            KeyError: unknown claim_id.

        Note:
            Disputed 는 confirmed 위에 얹는 격리 상태 (§20.3). candidate /
            refuted 에서 직접 진입 불가. confirmed → refuted 직접 전이 (PR7
            금지) 의 대안 — contradiction 으로 confirmed 가 흔들릴 때 별도
            상태로 격리.
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        if claim.status != CLAIM_STATUS_CONFIRMED:
            return False
        if not self._contradictions.get(claim_id):
            return False
        old_status = claim.status
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_DISPUTED)
        self._record_claim_lifecycle_transition(
            claim_id, old_status, CLAIM_STATUS_DISPUTED, "dispute_if_ready",
        )
        self._advance_state_revision()  # PR73-M04 §2.4
        return True

    # ---- Disputed resolution (PR9-A §21) ----------------------------------

    def register_contradiction_resolution(
        self, claim_id: int, evidence_id: int,
    ) -> bool:
        """Register that this evidence is no longer an active contradiction for this claim.

        Returns:
            True  — 새로 resolved 로 등록됨.
            False — (claim_id, evidence_id) 가 이미 resolved (idempotent no-op).

        Raises:
            KeyError:  unknown claim_id or unknown evidence_id.
            ValueError: (claim_id, evidence_id) 가 ``_contradictions[claim_id]`` 에
                        등록돼 있지 않음 — §21.2 relationship-bound 명제 위반.

        Notes:
            - PR5 first-keep 정신과 일관: 한 번 resolved 면 영구.
            - ``_contradictions`` 원본 entry 는 **삭제하지 않는다** (audit 보존).
            - Target claim status 무관 (데이터 등록, PR7 §19.6 일관).
        """
        self._assert_claim_exists(claim_id)
        self._assert_evidence_exists(evidence_id)
        contras = self._contradictions.get(claim_id, set())
        if evidence_id not in contras:
            raise ValueError(
                f"evidence {evidence_id} is not registered as a contradiction "
                f"for claim {claim_id}"
            )
        resolved = self._resolved_contradictions.setdefault(claim_id, set())
        if evidence_id in resolved:
            return False
        resolved.add(evidence_id)
        self._advance_state_revision()  # PR73-M04 §2.3
        return True

    def resolved_contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]:
        """Return resolved evidence_ids for the claim.

        Returns:
            evidence_id 오름차순 tuple. 없으면 빈 tuple.

        Raises:
            KeyError: unknown claim_id.
        """
        self._assert_claim_exists(claim_id)
        return tuple(sorted(self._resolved_contradictions.get(claim_id, set())))

    def active_contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]:
        """Return contradicting evidence_ids that are still active (not resolved).

        = contradictions_for_claim(c) - resolved_contradictions_for_claim(c)

        Returns:
            evidence_id 오름차순 tuple. status 무관 (모든 status 에서 호출 가능).

        Raises:
            KeyError: unknown claim_id.
        """
        self._assert_claim_exists(claim_id)
        contras = self._contradictions.get(claim_id, set())
        resolved = self._resolved_contradictions.get(claim_id, set())
        return tuple(sorted(contras - resolved))

    def resolve_disputed_claim_if_ready(self, claim_id: int) -> bool:
        """Transition disputed → confirmed if every contradiction is resolved.

        전이 조건 (§21.8):
            - ``claim.status == CLAIM_STATUS_DISPUTED``
            - ``len(active_contradictions_for_claim(claim_id)) == 0``

        Returns:
            True  — 이번 호출로 disputed → confirmed 복귀.
            False — 전이 없음 (status 불일치 / active contradiction 잔존 / no-op).

        Raises:
            KeyError: unknown claim_id.

        Note:
            API 이름 ``resolve_*`` 는 PR10+ 에서 ``disputed → refuted`` 같은
            확장이 들어올 수 있는 자리를 남겨둔 것 (§21.6 Notes).
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        if claim.status != CLAIM_STATUS_DISPUTED:
            return False
        if self.active_contradictions_for_claim(claim_id):
            return False
        old_status = claim.status
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_CONFIRMED)
        self._record_claim_lifecycle_transition(
            claim_id, old_status, CLAIM_STATUS_CONFIRMED, "resolve_disputed_if_ready",
        )
        self._advance_state_revision()  # PR73-M04 §2.4
        return True

    # ---- Disputed refutation (PR10-A §22) ---------------------------------

    def refute_disputed_claim_if_ready(self, claim_id: int) -> bool:
        """Transition disputed → refuted if any active contradiction is strong enough.

        전이 조건 (§22.7):
            - ``claim.status == CLAIM_STATUS_DISPUTED``
            - ``len(active_contradictions_for_claim(claim_id)) >= 1``
            - active contradiction 중 **단 하나라도**
              ``evidence.strength.value >= _REFUTATION_STRENGTH_THRESHOLD`` (= 0.8)

        Returns:
            True  — 이번 호출로 disputed → refuted 전이.
            False — 전이 없음 (status 불일치 / active 없음 / 모두 strength 부족 / no-op).

        Raises:
            KeyError: unknown claim_id.

        Notes:
            - PR9-A 의 ``resolve_disputed_claim_if_ready`` 와 sibling API.
            - **Resolved contradiction 은 판정에서 제외** (§22.7) —
              ``active_contradictions_for_claim`` 만 본다. ``contradictions_for_claim``
              을 직접 보면 안 됨 (PR9-A 의 차집합 의미 정합).
            - PR7 ``refute_claim_if_ready`` (candidate origin) 와는 status guard
              만 다른 sibling. 결과 status 는 같은 ``CLAIM_STATUS_REFUTED``.
              path 구분은 lifecycle history 영역 (PR10-B+).
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        if claim.status != CLAIM_STATUS_DISPUTED:
            return False
        for evidence_id in self.active_contradictions_for_claim(claim_id):
            evidence = self._evidences[evidence_id]
            if evidence.strength.value >= _REFUTATION_STRENGTH_THRESHOLD:
                old_status = claim.status
                self._claims[claim_id] = replace(
                    claim, status=CLAIM_STATUS_REFUTED,
                )
                self._record_claim_lifecycle_transition(
                    claim_id, old_status, CLAIM_STATUS_REFUTED,
                    "refute_disputed_if_ready",
                )
                self._advance_state_revision()  # PR73-M04 §2.4
                return True
        return False

    # ============================================================================
    # Region F  —  Lifecycle history + freshness queries
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region F
    # ============================================================================

    # ---- Lifecycle history (PR10-B §23) -----------------------------------

    def _record_claim_lifecycle_transition(
        self,
        claim_id: int,
        from_status: int,
        to_status: int,
        transition: str,
    ) -> None:
        """Append a lifecycle event. Called by 5 transition APIs on actual transition.

        Public 노출 안 됨 — caller 가 직접 history 를 mutate 할 수 없음 (§23.9
        audit 무결성). 5 lifecycle API 의 ``True`` 반환 직전에만 호출되므로
        no-op (False) 은 절대 기록되지 않음 (§23.5 Sub-decision J).
        """
        self._lifecycle_seq += 1
        event = ClaimLifecycleEvent(
            seq=self._lifecycle_seq,
            claim_id=claim_id,
            from_status=from_status,
            to_status=to_status,
            transition=transition,
        )
        self._claim_lifecycle_events.setdefault(claim_id, []).append(event)

    def claim_lifecycle_history(
        self, claim_id: int,
    ) -> tuple[ClaimLifecycleEvent, ...]:
        """Return lifecycle events for the claim in insertion order.

        Returns:
            ClaimLifecycleEvent 들의 tuple, 발생 순서 (= seq 오름차순).
            Status 변경이 한 번도 없었으면 빈 tuple.

        Raises:
            KeyError: unknown claim_id.

        Note:
            seq 는 engine-local monotonic. 서로 다른 claim 의 history 를 합쳐서
            정렬해도 의미가 있다 (cross-claim 순서 표현).
        """
        self._assert_claim_exists(claim_id)
        return tuple(self._claim_lifecycle_events.get(claim_id, ()))

    # ---- Evidence freshness (PR11-A §25) ----------------------------------

    def evidence_freshness(self, evidence_id: int) -> int:
        """Return the freshness signal of the evidence.

        PR11-A §25.3 — freshness = evidence.id (PR1 _next_id 기반 등록 순서).
        더 큰 값일수록 더 최근 등록.

        Returns:
            evidence.id (= evidence_id 자체).

        Raises:
            KeyError: unknown evidence_id.

        Note:
            wall-clock 안 봄 (PR10-A / PR10-B 정신 일관). engine-local 의미만
            가짐 (cross-engine 비교 무의미).
        """
        self._assert_evidence_exists(evidence_id)
        return evidence_id

    def active_contradictions_by_freshness(
        self, claim_id: int,
    ) -> tuple[int, ...]:
        """Return active contradicting evidence_ids ordered by freshness (most recent first).

        ``active_contradictions_for_claim`` (PR9-A) 와 **같은 set** 이지만
        정렬 키가 다름:
            active_contradictions_for_claim       → evidence_id asc
            active_contradictions_by_freshness    → evidence_id desc (most recent first)

        PR9-A 의 차집합 의미는 그대로 보존 — resolved contradiction 제외.

        Returns:
            active contradicting evidence_ids, evidence_id desc tuple.
            없으면 빈 tuple.

        Raises:
            KeyError: unknown claim_id.
        """
        self._assert_claim_exists(claim_id)
        contras = self._contradictions.get(claim_id, set())
        resolved = self._resolved_contradictions.get(claim_id, set())
        return tuple(sorted(contras - resolved, reverse=True))

    # ============================================================================
    # Region G  —  Freshness-based refute
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region G
    # ============================================================================

    # ---- Freshness-aware refutation (PR11-B §27) --------------------------

    def refute_disputed_claim_if_ready_by_freshness(
        self, claim_id: int,
    ) -> bool:
        """Sibling refute API — inspects most recent active contradiction only.

        PR10-A 의 ``refute_disputed_claim_if_ready`` 와 sibling:

        | API           | inspects                | trigger              |
        |---------------|-------------------------|----------------------|
        | PR10-A refute | ANY active              | any strength >= 0.8  |
        | PR11-B refute | FIRST by freshness only | first strength >= 0.8 |

        같은 status target (REFUTED), 같은 threshold
        (``_REFUTATION_STRENGTH_THRESHOLD = 0.8``, Sub-decision R 재사용),
        다른 input set.

        Returns:
            True  — most_recent active.strength.value >= 0.8 → REFUTED 전이.
            False — 전이 없음.

        Raises:
            KeyError: unknown claim_id.

        Notes:
            - ``active_contradictions_by_freshness(c)[0]`` 만 본다 (Sub-decision Q).
            - True 반환 시 lifecycle event 기록 (transition label
              ``"refute_disputed_by_freshness_if_ready"`` — Sub-decision S).
            - PR10-A ``refute_disputed_claim_if_ready`` 의 의미 / 시그니처
              변경 없음.
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        if claim.status != CLAIM_STATUS_DISPUTED:
            return False
        active = self.active_contradictions_by_freshness(claim_id)
        if not active:
            return False
        most_recent_evidence = self._evidences[active[0]]
        if most_recent_evidence.strength.value >= _REFUTATION_STRENGTH_THRESHOLD:
            old_status = claim.status
            self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_REFUTED)
            self._record_claim_lifecycle_transition(
                claim_id, old_status, CLAIM_STATUS_REFUTED,
                "refute_disputed_by_freshness_if_ready",
            )
            self._advance_state_revision()  # PR73-M04 §2.4
            return True
        return False

    # ============================================================================
    # Region H  —  Rule meta
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region H
    # ============================================================================

    # ---- Rule registry -----------------------------------------------------

    def register_rule(self, definition: RuleDefinition) -> None:
        """Register a rule and initialize its stats slot.

        같은 (rule_id, rule_version) 이 두 번 등록되면 ValueError.
        같은 rule_id 라도 version 이 다르면 별개 룰로 취급한다.
        """
        key = (definition.id, definition.version)
        if key in self._rule_definitions:
            raise ValueError(
                f"rule already registered: rule_id={definition.id}, "
                f"version={definition.version}"
            )
        self._rule_definitions[key] = definition
        self._rule_stats[key] = RuleStats(
            rule_id=definition.id, rule_version=definition.version
        )
        self._advance_state_revision()  # PR73-M04 §2.1

    def get_rule(self, rule_id: int, rule_version: int) -> RuleDefinition:
        """Return the RuleDefinition for the ``(rule_id, rule_version)`` pair.

        PR28-O §40 — ``rule_id`` and ``rule_version`` 은 joint identity.
        ``(R, 1)`` 로 핀된 claim 은 v1 RuleDefinition 으로 계속 resolve 되어야
        하며 나중에 등록된 v2 로 silently 갈아탈 수 없다.

        Raises:
            KeyError: unknown ``(rule_id, rule_version)`` pair.
        """
        self._assert_rule_pair_exists(rule_id, rule_version)
        return self._rule_definitions[(rule_id, rule_version)]

    def get_rule_stats(self, rule_id: int, rule_version: int) -> RuleStats:
        """Return the RuleStats for the ``(rule_id, rule_version)`` pair.

        PR29-R §41 — RuleStats 는 ``firing_count`` 와 (옵션) ``observed_precision``
        을 누적한다. pair 가 없으면 KeyError. consumer 는 "stats 미등록" 상태를
        ``firing_count=0`` / ``observed_precision=None`` 으로 해석해야 한다
        (§44.7 rule_pinning shape 가 이 분기를 명시).

        Raises:
            KeyError: unknown ``(rule_id, rule_version)`` pair.
        """
        self._assert_rule_stats_pair_exists(rule_id, rule_version)
        return self._rule_stats[(rule_id, rule_version)]

    # ============================================================================
    # Region I  —  7-modifier helper layer
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region I
    # ============================================================================

    # ---- Modifier helpers (private — PR34-O §46 O2 + O3) -----------------
    #
    # All 6 modifier helpers share the same signature:
    #     _<name>_modifier_for_claim(self, claim_id: int) -> float
    #
    # status / freshness were inlined in compute_effective_confidence before
    # PR34-O §46 O3 extracted them for symmetry with the existing four
    # (gap / count / rule_stats / evidence_type).

    def _status_modifier_for_claim(self, claim_id: int) -> float:
        """PR11-D §24.8 — status-only effective confidence multiplier.

        4-state mapping (status modifier 강 — 0.0 / 0.5 / 1.0).
        """
        return _STATUS_TO_MODIFIER[self._claims[claim_id].status]

    def _freshness_modifier_for_claim(self, claim_id: int) -> float:
        """PR11-C §26 — most-recent active contradiction strength weight.

        active contradictions 없으면 1.0. 있으면
        ``1.0 - most_recent.strength × _FRESHNESS_PENALTY_WEIGHT``
        (Sub-decision O — 가장 최근 1개만 사용).
        """
        active = self.active_contradictions_by_freshness(claim_id)
        if not active:
            return 1.0
        most_recent_evidence = self._evidences[active[0]]
        return 1.0 - most_recent_evidence.strength.value * _FRESHNESS_PENALTY_WEIGHT

    def _gap_modifier_for_claim(self, claim_id: int) -> float:
        """PR12-D §28 + PR23-M §35 — count-tier weak attenuation.

        Sub-decision AO/AP/AQ/AR/AS:
            - AO: severity source = unresolved gap count only (no new taxonomy)
            - AP: tier table 0→1.0 / 1→0.9 / 2→0.8 / 3+→0.7
            - AQ: information shortage remains weak (never 0.0)
            - AR: formula shape unchanged (gap 항 내부 계산만 변경)
            - AS: 4 개 private tier 상수 사용
        """
        unresolved_gap_count = sum(
            1
            for gap_id in self._claim_gap_refs.get(claim_id, ())
            if gap_id not in self._gap_resolutions
        )
        if unresolved_gap_count == 0:
            return _GAP_TIER_ZERO_UNRESOLVED_MODIFIER
        if unresolved_gap_count == 1:
            return _GAP_TIER_ONE_UNRESOLVED_MODIFIER
        if unresolved_gap_count == 2:
            return _GAP_TIER_TWO_UNRESOLVED_MODIFIER
        return _GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER

    def _count_modifier_for_claim(self, claim_id: int) -> float:
        """PR19-E §31 + PR24-N §36 — count modifier as continuous repeated pressure.

        Sub-decision AV~BB:
            - AV: name/source/threshold=2 preserved from PR19-E
            - AW: active count < 2 → 1.0, preserving PR11-C freshness role
            - AX: active count >= 2 → 1.0 - avg_strength × 0.25
            - AY: center preservation, avg 0.8 → 0.8 (PR19-E binary 재현)
            - AZ: _COUNT_STRENGTH_PENALTY_WEIGHT private, old binary constant removed
            - BA: no snapshot schema bump (state shape 무변화)
            - BB: PR19-E binary expectations naturally expire

        핵심 문장:
            빈 강도의 contradiction 은 repeated pressure 가 아니다.
        """
        active = self.active_contradictions_for_claim(claim_id)
        if len(active) < 2:
            return 1.0
        average_strength = sum(
            self._evidences[evidence_id].strength.value
            for evidence_id in active
        ) / len(active)
        return 1.0 - average_strength * _COUNT_STRENGTH_PENALTY_WEIGHT

    def _rule_stats_modifier_for_claim(self, claim_id: int) -> float:
        """PR20-F §32 + PR26-R §38 + PR29-R §41 — continuous maturity × bounded precision.

        PR29-R refines rule_stats_modifier internally:
            rule_stats_modifier = maturity_modifier × precision_modifier

        Sub-decision BK/BL/BM/BN/BO/BQ (PR26-R §38, maturity 부분):
            - BK: source = firing_count only for maturity
            - BL: saturation count = 2 (PR20-F threshold 보존)
            - BM: penalty weight = 0.2 (maturity max 20% attenuation)
            - BN: no boost — maturity_modifier ∈ [0.8, 1.0]
            - BO: sentinel (created_by_rule == 0) / lookup miss → 1.0
            - BQ: defensive clamp min(max(firing_count, 0), saturation_count)

        Sub-decision A~J (PR29-R §41, precision 부분):
            - A: observed_precision is None → precision_modifier = 1.0 (PR26-R 보존)
            - B: precision_modifier = _RULE_STATS_PRECISION_BASE + p × _RULE_STATS_PRECISION_RANGE
                                    = 0.9 + p × 0.1, range [0.9, 1.0]
            - C: rule_stats_modifier = maturity_modifier × precision_modifier
            - D: no boost — rule_stats_modifier ∈ [0.72, 1.0]
                 (maturity floor 0.8 × precision floor 0.9 = 0.72)
            - E/F: status (refuted/disputed) dominance is preserved at compose level
            - G: other modifiers unchanged
            - H: false_positive_rate ignored (PR29-R OOS)
            - I: snapshot round-trip preserves observed_precision + computed confidence
            - J: types.py / __init__.py / rule_output.py unchanged

        Maturity mapping (PR26-R):
            firing_count == 0 → 0.8
            firing_count == 1 → 0.9
            firing_count >= 2 → 1.0

        Precision mapping (PR29-R):
            observed_precision is None → 1.0
            observed_precision p=0.0 → 0.9
            observed_precision p=0.5 → 0.95
            observed_precision p=1.0 → 1.0

        Composition examples (§41.11 C):
            firing 0 + p None → 0.8 × 1.0 = 0.8 (PR26-R 보존)
            firing 0 + p 0.0 → 0.8 × 0.9 = 0.72
            firing 1 + p 0.5 → 0.9 × 0.95 = 0.855
            firing 2 + p 1.0 → 1.0 × 1.0 = 1.0

        핵심 명제 (§41.1):
            Observed precision is a bounded adjustment signal,
            not a rule quality verdict.

        보수적 명제:
            Observed precision is optional evidence for rule maturity,
            not ground truth.
        """
        claim = self._claims[claim_id]
        if claim.created_by_rule == 0:
            return 1.0
        key = (claim.created_by_rule, claim.created_by_rule_version)
        stats = self._rule_stats.get(key)
        if stats is None:
            return 1.0
        clamped_count = min(
            max(stats.firing_count, 0),
            _RULE_STATS_MATURITY_SATURATION_COUNT,
        )
        maturity_ratio = clamped_count / _RULE_STATS_MATURITY_SATURATION_COUNT
        maturity_modifier = 1.0 - (
            (1.0 - maturity_ratio) * _RULE_STATS_MATURITY_PENALTY_WEIGHT
        )

        if stats.observed_precision is None:
            precision_modifier = 1.0
        else:
            precision_modifier = (
                _RULE_STATS_PRECISION_BASE
                + stats.observed_precision.value * _RULE_STATS_PRECISION_RANGE
            )

        return maturity_modifier * precision_modifier

    def _validate_hint_evidence_type_values(
        self, types: Iterable[int],
    ) -> set[int]:
        """PR22-S §34 strict validation — shared by register / unregister.

        Sub-decision BD (PR25-T §37): register / unregister 가 같은 validation
        helper 를 공유 — strict 동일성이 코드 차원에서 보장됨.

        Sub-decision AI/AJ/AK/AL/AM (PR22-S §34):
            - AI: no implicit casting — int(t) cast 안 함
            - AJ: int 만 허용, bool 거부 (bool 검사 이전에 별도 — isinstance(True, int) 함정)
            - AK: 값 범위 제한 없음 (음수 / 0 / 큰 정수 모두 허용)
            - AL: all-or-nothing — 모든 검증 통과 후 validated set 반환, 호출자가 mutate
            - AM: non-iterable + str / bytes 컨테이너 거부

        Returns:
            검증된 int 값들의 set (caller 가 `update` / `difference_update` 등 사용).

        Raises:
            TypeError: input 이 str/bytes 컨테이너이거나, element 가 int 가
                아닌 경우 (bool 포함). 본 helper 는 mutate 없음 — caller 의
                state mutation 도 검증 완료 후에만 일어남 (Sub-decision AL/BF).
        """
        if isinstance(types, (str, bytes)):
            raise TypeError(
                "hint evidence types must be an iterable of int values, "
                f"not {type(types).__name__}"
            )
        validated: set[int] = set()
        for value in types:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(
                    "hint evidence type values must be int values, "
                    f"not {type(value).__name__}"
                )
            validated.add(value)
        return validated

    def register_hint_evidence_types(self, types: Iterable[int]) -> None:
        """PR21-L §33 + PR22-S §34 — register caller-defined "hint-like" evidence type ids.

        PR25-T §37 Sub-decision BJ: 본문은 helper 호출로 교체되었으나 외부
        관찰 가능한 동작은 PR22-S 와 완전히 동일. PR22-S 의 38 invariants
        모두 회귀 없음.

        Sub-decision AF: framework 는 Evidence.type 정수 의미를 소유하지 않는다.
        caller 가 어떤 정수가 "hint" 인지 알려준다.

        Args:
            types: hint evidence type ids. list / tuple / set / frozenset /
                generator 등 `Iterable[int]` 허용. str / bytes 컨테이너는 거부.
                빈 iterable 은 no-op. 중복은 idempotent (set union 누적).

        Raises:
            TypeError: input 이 str/bytes 컨테이너이거나, element 가 int 가
                아닌 경우 (bool 포함). partial mutation 발생하지 않음.
        """
        validated = self._validate_hint_evidence_type_values(types)
        # PR73-M04 §2.5 — advance only on actual set growth.
        before_size = len(self._hint_evidence_types)
        self._hint_evidence_types.update(validated)
        if len(self._hint_evidence_types) != before_size:
            self._advance_state_revision()

    def unregister_hint_evidence_types(self, types: Iterable[int]) -> None:
        """PR25-T §37 — register 의 역연산 (set difference).

        Sub-decision BC/BD/BE/BF:
            - BC: API surface 2 개 중 하나 (clear 와 함께)
            - BD: register 와 동일 strict validation (_validate_hint_evidence_type_values 공유)
            - BE: hint set 에 없는 type 제거 시 no-op (set difference 의 자연 의미)
            - BF: all-or-nothing — validation 실패 시 hint set mutation 0

        Args:
            types: 제거할 hint evidence type ids. register 와 동일한 iterable 규칙.
                빈 iterable 은 no-op. 중복은 idempotent. 미등록 type 도 no-op (KeyError 없음).

        Raises:
            TypeError: register 와 동일한 strict validation. partial mutation 없음.
        """
        validated = self._validate_hint_evidence_type_values(types)
        # PR73-M04 §2.5 — advance only on actual set shrink.
        before_size = len(self._hint_evidence_types)
        self._hint_evidence_types.difference_update(validated)
        if len(self._hint_evidence_types) != before_size:
            self._advance_state_revision()

    def clear_hint_evidence_types(self) -> None:
        """PR25-T §37 — hint evidence type set 초기화.

        Sub-decision BG: 항상 no-op safe.
            - input 없음 → validation 불필요
            - 빈 set 에서도 정상 (set.clear 동작)
            - 반복 호출 가능
            - TypeError 절대 raise 안 함

        Sub-decision BI: `_evidence_type_modifier_for_claim` 본문 변경 없음 —
        clear 후 첫 호출 시 `if not self._hint_evidence_types: return 1.0`
        가드 (PR21-L Sub-decision AE) 가 자연 적용되어 modifier 1.0.
        """
        # PR73-M04 §2.5 — advance only if set was non-empty.
        if self._hint_evidence_types:
            self._hint_evidence_types.clear()
            self._advance_state_revision()

    def _evidence_type_modifier_for_claim(self, claim_id: int) -> float:
        """PR21-L §33 — weak source-quality signal (NOT truth verdict).

        Sub-decision AA/AB/AC/AD/AE:
            - AA: direct evidence only (Evidence.claim_id == claim_id),
                  contradiction / resolved contradiction evidence 제외
            - AB: direct evidence 0 개 → 1.0
            - AC: direct evidence 1+ 개이고 전부 hint set 에 포함 → 0.9
            - AD: no boost (modifier ∈ {0.9, 1.0})
            - AE: hint set empty → 항상 1.0 (vacuous truth 함정 회피)
        """
        if not self._hint_evidence_types:
            return 1.0
        contradicting = self._contradictions.get(claim_id, set())
        resolved = self._resolved_contradictions.get(claim_id, set())
        excluded = contradicting | resolved
        direct = [
            ev
            for ev in self._evidences.values()
            if ev.claim_id == claim_id and ev.id not in excluded
        ]
        if not direct:
            return 1.0
        if all(ev.type in self._hint_evidence_types for ev in direct):
            return _EVIDENCE_TYPE_PENALTY_MODIFIER
        return 1.0

    # ============================================================================
    # Region J  —  Effective confidence + rule stats update
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region J
    # ============================================================================

    def compute_effective_confidence(self, claim_id: int) -> ScoreValue:
        """Effective confidence as base × status × freshness × gap × count × rule_stats × evidence_type.

        Composition (PR11-D §24 + PR11-C §26 + PR12-D §28 + PR19-E §31 + PR20-F §32 + PR21-L §33):
            effective = base
                      × status_modifier(claim.status)         # PR11-D
                      × freshness_modifier(claim_id)           # PR11-C
                      × gap_modifier(claim_id)                 # PR12-D
                      × count_modifier(claim_id)               # PR19-E
                      × rule_stats_modifier(claim)             # PR20-F
                      × evidence_type_modifier(claim_id)       # PR21-L

        status_modifier (PR11-D §24.3, unchanged):
            candidate / confirmed → 1.0
            disputed → 0.5
            refuted → 0.0

        freshness_modifier (PR11-C §26.3, Sub-decision O — 최신 1개만):
            active = active_contradictions_by_freshness(claim_id)
            if not active: → 1.0
            else: → 1.0 - most_recent.strength.value × _FRESHNESS_PENALTY_WEIGHT

        gap_modifier (PR12-D §28.3 + PR23-M §35.5, Sub-decision AP — count-tier):
            unresolved_count = #{gap in _claim_gap_refs[claim_id] : not in _gap_resolutions}
            0   → _GAP_TIER_ZERO_UNRESOLVED_MODIFIER (1.0)
            1   → _GAP_TIER_ONE_UNRESOLVED_MODIFIER (0.9)
            2   → _GAP_TIER_TWO_UNRESOLVED_MODIFIER (0.8)
            3+  → _GAP_TIER_THREE_OR_MORE_UNRESOLVED_MODIFIER (0.7)

        count_modifier (PR19-E §31.3 + PR24-N §36, Sub-decision AV~BB — strength averaging):
            active = active_contradictions_for_claim(claim_id)
            if len(active) < 2: → 1.0 (PR11-C freshness 영역)
            else:
                avg_strength = average(_evidences[ev].strength.value for ev in active)
                → 1.0 - avg_strength × _COUNT_STRENGTH_PENALTY_WEIGHT (0.25)
            # avg 0.0 → 1.0 / avg 0.4 → 0.9 / avg 0.8 → 0.8 (PR19-E 중심점) / avg 1.0 → 0.75
            # 핵심: 빈 강도의 contradiction 은 repeated pressure 가 아니다.

        rule_stats_modifier (PR20-F §32 + PR26-R §38 + PR29-R §41, Sub-decision BK~BQ + A~J):
            if claim.created_by_rule == 0: → 1.0
            elif (rule_id, rule_version) miss: → 1.0
            else:
                # maturity (PR26-R)
                clamped = min(max(firing_count, 0), 2)
                maturity_ratio = clamped / 2
                maturity_modifier = 1.0 - (1.0 - maturity_ratio) × 0.2
                # precision (PR29-R)
                if observed_precision is None:
                    precision_modifier = 1.0
                else:
                    precision_modifier = 0.9 + observed_precision.value × 0.1
                → maturity_modifier × precision_modifier
            # PR26-R maturity: firing 0 → 0.8 / 1 → 0.9 / 2+ → 1.0
            # PR29-R precision: None → 1.0 / p=0.0 → 0.9 / p=0.5 → 0.95 / p=1.0 → 1.0
            # 핵심 (§41.1): Observed precision is a bounded adjustment signal,
            #               not a rule quality verdict.
            # range: [0.72, 1.0] (maturity floor 0.8 × precision floor 0.9)

        evidence_type_modifier (PR21-L §33.13, Sub-decision AA~AE — caller-registered):
            if not self._hint_evidence_types: → 1.0
            direct = [ev for ev in self._evidences if ev.claim_id == claim_id
                      and ev.id not in (_contradictions | _resolved_contradictions)]
            if not direct: → 1.0
            elif all ev.type in self._hint_evidence_types for ev in direct:
                → _EVIDENCE_TYPE_PENALTY_MODIFIER (0.9)
            else: → 1.0

        의미 분리:
            PR11-C: most recent active contradiction strength (1 개 시 단독)
            PR19-E: active contradiction count pressure (2 개 이상 시 추가)
            PR20-F: rule maturity (rule-global 신호)
            PR21-L: direct supporting evidence source-quality (claim-local, caller-registered)

        Returns:
            ScoreValue (effective ≤ base, no boost — §24.5 N / §32.6 X / §33.7 AD).

        Raises:
            KeyError: unknown claim_id.
        """
        # PR76-M07 §6 — delegate to the single private calculation core
        # so the typed-trace API and the legacy API share one formula.
        return self._compute_effective_confidence_core(claim_id).effective_confidence

    def _compute_effective_confidence_core(
        self, claim_id: int,
    ) -> EffectiveConfidenceTrace:
        """PR76-M07 §6 — single calculation core for both confidence APIs.

        Computes each modifier once into a local variable, multiplies them
        together to produce the effective confidence, and packages the
        components into a frozen EffectiveConfidenceTrace value. Both
        ``compute_effective_confidence`` and
        ``compute_effective_confidence_with_trace`` delegate here so the
        composition formula has exactly one site (§6).

        Raises:
            KeyError: unknown claim_id (same surface as the legacy API).
        """
        self._assert_claim_exists(claim_id)
        claim = self._claims[claim_id]
        status_modifier = self._status_modifier_for_claim(claim_id)
        freshness_modifier = self._freshness_modifier_for_claim(claim_id)
        gap_modifier = self._gap_modifier_for_claim(claim_id)
        count_modifier = self._count_modifier_for_claim(claim_id)
        rule_stats_modifier = self._rule_stats_modifier_for_claim(claim_id)
        evidence_type_modifier = self._evidence_type_modifier_for_claim(claim_id)
        effective_confidence = ScoreValue(
            claim.base_confidence.value
            * status_modifier
            * freshness_modifier
            * gap_modifier
            * count_modifier
            * rule_stats_modifier
            * evidence_type_modifier
        )
        return EffectiveConfidenceTrace(
            claim_id=claim_id,
            source_state_identity=self.state_identity(),
            calculation_policy_id=_EFFECTIVE_CONFIDENCE_POLICY_ID,
            base_confidence=claim.base_confidence,
            status_modifier=status_modifier,
            freshness_modifier=freshness_modifier,
            gap_modifier=gap_modifier,
            count_modifier=count_modifier,
            rule_stats_modifier=rule_stats_modifier,
            evidence_type_modifier=evidence_type_modifier,
            effective_confidence=effective_confidence,
        )

    def compute_effective_confidence_with_trace(
        self, claim_id: int,
    ) -> EffectiveConfidenceTrace:
        """PR76-M07 §5 — return a typed breakdown of the same calculation.

        Returns the EffectiveConfidenceTrace value produced by the single
        private calculation core. By construction:

            self.compute_effective_confidence_with_trace(claim_id)
                .effective_confidence
              == self.compute_effective_confidence(claim_id)

        Read-only: does not advance the M04 revision (§5.1 / §11.1) and
        does not mutate snapshot-visible state.

        Raises:
            KeyError: unknown claim_id (same surface as
                ``compute_effective_confidence``).
        """
        return self._compute_effective_confidence_core(claim_id)

    def update_rule_stats(
        self,
        rule_id: int,
        rule_version: int,
        *,
        firing_delta: int = 0,
        true_delta: int = 0,
        false_delta: int = 0,
        observed_precision: ScoreValue | None = None,
        false_positive_rate: ScoreValue | None = None,
    ) -> None:
        """Replace the stored RuleStats with a new instance reflecting deltas.

        기존 객체는 mutate 하지 않는다. 새 RuleStats를 만들어 dict에 교체한다.
        precision/fpr 인자가 None이면 "변경 안 함" (기존 값 유지). 명시적으로
        nullify 하려면 별도 API가 필요 (MVP 미포함).
        """
        self._assert_rule_stats_pair_exists(rule_id, rule_version)
        key = (rule_id, rule_version)
        current = self._rule_stats[key]
        new_stats = RuleStats(
            rule_id=current.rule_id,
            rule_version=current.rule_version,
            firing_count=current.firing_count + firing_delta,
            confirmed_true_count=current.confirmed_true_count + true_delta,
            confirmed_false_count=current.confirmed_false_count + false_delta,
            observed_precision=(
                observed_precision
                if observed_precision is not None
                else current.observed_precision
            ),
            false_positive_rate=(
                false_positive_rate
                if false_positive_rate is not None
                else current.false_positive_rate
            ),
        )
        self._rule_stats[key] = new_stats
        # PR73-M04 §2.6 — advance only if RuleStats value actually changed.
        # RuleStats is a frozen dataclass; value equality is well-defined.
        if new_stats != current:
            self._advance_state_revision()

    # ============================================================================
    # Region K  —  Snapshot serialize / restore (on Engine)
    # See: docs/architecture/ENGINE_INTERNAL_MAP.md  §2 Region K
    # ============================================================================

    # ---- Persistence snapshot (PR17 §29) ----------------------------------

    def to_snapshot(self) -> dict[str, Any]:
        """Serialize engine state to JSON-compatible dict (PR17 §29).

        결정성 보장 — 같은 engine state → 같은 dict (모든 set/dict iteration
        은 sorted). caller 가 ``json.dumps`` 등으로 영속화 자유.

        Returns:
            JSON-compatible dict with ``schema_version`` + all engine state.
        """
        return {
            "schema_version": _CURRENT_SNAPSHOT_SCHEMA_VERSION,
            "next_id": dict(sorted(self._next_id.items())),
            "lifecycle_seq": self._lifecycle_seq,
            "entities": _serialize_dict_int_dataclass(self._entities),
            "observations": _serialize_dict_int_dataclass(self._observations),
            "claims": _serialize_dict_int_dataclass(self._claims),
            "evidences": _serialize_dict_int_dataclass(self._evidences),
            "relations": _serialize_dict_int_dataclass(self._relations),
            "gaps": _serialize_dict_int_dataclass(self._gaps),
            "rule_definitions": _serialize_dict_tuple_dataclass(self._rule_definitions),
            "rule_stats": _serialize_dict_tuple_dataclass(self._rule_stats),
            "gap_dedup_index": _serialize_dict_tuple4_int(self._gap_dedup_index),
            "claim_gap_refs": _serialize_dict_int_set(self._claim_gap_refs),
            "gap_resolutions": _serialize_dict_int_int(self._gap_resolutions),
            "contradictions": _serialize_dict_int_set(self._contradictions),
            "resolved_contradictions": _serialize_dict_int_set(self._resolved_contradictions),
            "claim_lifecycle_events": _serialize_dict_int_list_dataclass(
                self._claim_lifecycle_events,
            ),
            # PR21-L §33 — sorted list for deterministic round-trip (Sub-decision AG).
            "hint_evidence_types": sorted(self._hint_evidence_types),
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> "Engine":
        """Restore engine from snapshot dict (PR17 §29).

        rule 재실행 / evidence 재평가 / lifecycle 재추론 절대 안 함. 내부
        state 만 그대로 복원.

        Returns:
            New Engine instance with all state restored.

        Raises:
            ValueError: missing or unknown schema_version.
        """
        # §52.7 — reject non-dict snapshot before the migration helper
        # touches it (the helper would otherwise raise AttributeError,
        # which is not part of the §52 contract surface).
        if not isinstance(snapshot, dict):
            raise TypeError(
                f"snapshot must be a dict, got {type(snapshot).__name__}"
            )
        snapshot = _migrate_snapshot_to_current(snapshot)
        # §52 — fail-fast cross-reference / set / index / identity /
        # counter integrity check. Also converts raw-KeyError surfaces
        # (missing required top-level keys, malformed item shapes) into
        # the §52.7 contract surface (TypeError / ValueError).
        _validate_snapshot_restore_integrity(snapshot)
        try:
            # §51.4 — reject snapshots whose claim entries carry an invalid
            # status before constructing or populating any Engine state.
            for _item in snapshot["claims"]:
                _validate_claim_status_admission(_item["value"]["status"])
            engine = cls()
            engine._next_id = dict(snapshot.get("next_id", {}))
            engine._lifecycle_seq = snapshot.get("lifecycle_seq", 0)
            engine._entities = _restore_dict_int(snapshot["entities"], _entity_from_dict)
            engine._observations = _restore_dict_int(
                snapshot["observations"], _observation_from_dict,
            )
            engine._claims = _restore_dict_int(snapshot["claims"], _claim_from_dict)
            engine._evidences = _restore_dict_int(
                snapshot["evidences"], _evidence_from_dict,
            )
            engine._relations = _restore_dict_int(snapshot["relations"], _relation_from_dict)
            engine._gaps = _restore_dict_int(snapshot["gaps"], _gap_from_dict)
            engine._rule_definitions = _restore_dict_tuple(
                snapshot["rule_definitions"], _rule_def_from_dict,
            )
            engine._rule_stats = _restore_dict_tuple(
                snapshot["rule_stats"], _rule_stats_from_dict,
            )
            engine._gap_dedup_index = _restore_dict_tuple4_int(snapshot["gap_dedup_index"])
            engine._claim_gap_refs = _restore_dict_int_set(snapshot["claim_gap_refs"])
            engine._gap_resolutions = _restore_dict_int_int(snapshot["gap_resolutions"])
            engine._contradictions = _restore_dict_int_set(snapshot["contradictions"])
            engine._resolved_contradictions = _restore_dict_int_set(
                snapshot["resolved_contradictions"],
            )
            engine._claim_lifecycle_events = _restore_dict_int_list_dataclass(
                snapshot["claim_lifecycle_events"],
                lambda d: ClaimLifecycleEvent(**d),
            )
            engine._hint_evidence_types = set(snapshot["hint_evidence_types"])
        except KeyError as exc:
            # §52.7 — a missing required nested snapshot field must surface as
            # the ValueError contract class, never a raw KeyError. Narrowly
            # scoped to KeyError so unrelated errors are not masked; the
            # original lookup miss is preserved as __cause__.
            missing = exc.args[0] if exc.args else None
            raise ValueError(
                "snapshot restore failed: missing required nested field "
                f"{missing!r}"
            ) from exc
        return engine
