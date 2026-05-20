"""Engine — owns ID allocation and per-kind storage.

Reference implementation. ID 발급은 kind 별 단조 증가 카운터.
참조 무결성: add_* 메서드는 참조 대상이 (kind, id) 쌍으로 정확히 존재해야 통과.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, replace
from typing import Any

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
    Entity,
    Evidence,
    Gap,
    Observation,
    Relation,
    RuleDefinition,
    RuleStats,
    ScoreValue,
)

# PR10-A §22.5 (Sub-decision G): strength-based refutation threshold for
# disputed → refuted. Engine 내부 private — public export 안 함.
# 미래 정책 (freshness / RuleStats / 가중합) 도입 시 자연스럽게 조정/대체.
_REFUTATION_STRENGTH_THRESHOLD = 0.8

# PR11-D §24.8: status-only effective confidence multipliers.
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

# PR11-C §26: freshness modifier 의 strength → penalty 가중치.
# effective = base × status_modifier × (1.0 - most_recent.strength × WEIGHT)
# Engine 내부 private — public export 안 함.
# 0.5 의 의미: "가장 최근 active contradiction 의 strength 가 1.0 이면 modifier 0.5"
_FRESHNESS_PENALTY_WEIGHT = 0.5

# PR12-D §28 + PR23-M §35: gap modifier — count-tier (was binary 0.8).
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

# PR19-E §31: count modifier — active contradiction 개수 기반 보조 감쇠.
# effective = base × status × freshness × gap × count
# active count >= 2 → 0.8 (binary, N 무관), 그 외 → 1.0
# Engine 내부 private — public export 안 함.
# 의미: active 1 은 PR11-C freshness 가 처리, active 2+ 누적 압력 추가 감쇠.
# 0.8 (PR12-D gap_modifier 와 같은 약한 보조 신호 정신 일관).
_COUNT_PENALTY_MODIFIER = 0.8

# PR20-F §32: rule_stats modifier — weak maturity signal (NOT quality verdict).
# effective = base × status × freshness × gap × count × rule_stats
# firing_count < 2 → 0.9, 그 외 → 1.0 (binary, no boost).
# Engine 내부 private — public export 안 함.
# 의미: 룰이 엔진 안에서 충분히 관측되었는지 약하게 반영. outcome ratio /
# precision / FPR / timestamp 는 OOS (별도 PR).
# 0.9 (status / freshness / gap / count 보다 가장 약함 — RuleStats 는 "증거
# 부족" 이나 "반박" 이 아니라 단순 "관측 이력 부족" 신호).
_RULE_STATS_PENALTY_MODIFIER = 0.9
_RULE_STATS_MIN_FIRING_COUNT = 2

# PR21-L §33: evidence_type modifier — caller-registered weak source-quality.
# effective = base × status × freshness × gap × count × rule_stats × evidence_type
# direct evidence 전부 caller-registered hint set 에 포함되면 0.9, 그 외 → 1.0.
# Engine 내부 private — public export 안 함.
# 의미: caller 가 "이 type 은 보조 신호" 라고 등록한 경우만 약하게 감쇠.
# framework 는 Evidence.type 정수 의미를 소유하지 않는다 (Sub-decision AF).
# 0.9 (PR20-F rule_stats 와 동일 강도 — 가장 약한 modifier 자리).
_EVIDENCE_TYPE_PENALTY_MODIFIER = 0.9

# PR18-K §30 + PR21-L §33: snapshot schema version + migration framework.
# Engine 내부 private — public export 안 함.
# PR21-L 에서 hint_evidence_types engine state 추가 → schema v1 → v2 bump.
# 미래 schema 변경 시 두 상수 업데이트 + migration step (예: _v2_to_v3) 추가.
_CURRENT_SNAPSHOT_SCHEMA_VERSION = 2
_SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS: frozenset[int] = frozenset({1, 2})


class Engine:
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

    def _allocate_id(self, kind: str) -> int:
        next_id = self._next_id.get(kind, 0) + 1
        self._next_id[kind] = next_id
        return next_id

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

    # ---- Entity / Observation / Claim / Evidence ---------------------------

    def add_entity(self, entity_type: int, flags: int = 0) -> int:
        entity_id = self._allocate_id("entity")
        self._entities[entity_id] = Entity(id=entity_id, type=entity_type, flags=flags)
        return entity_id

    def get_entity(self, entity_id: int) -> Entity:
        return self._entities[entity_id]

    def add_observation(
        self,
        entity_id: int,
        raw_ref_id: int,
        observation_type: int,
        source_type: int = 0,
    ) -> int:
        if entity_id not in self._entities:
            raise KeyError(f"unknown entity_id: {entity_id}")
        obs_id = self._allocate_id("observation")
        self._observations[obs_id] = Observation(
            id=obs_id,
            entity_id=entity_id,
            raw_ref_id=raw_ref_id,
            type=observation_type,
            source_type=source_type,
        )
        return obs_id

    def get_observation(self, observation_id: int) -> Observation:
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
            raise KeyError(f"unknown subject_id (entity): {subject_id}")
        claim_id = self._allocate_id("claim")
        self._claims[claim_id] = Claim(
            id=claim_id,
            subject_id=subject_id,
            type=claim_type,
            status=status,
            created_by_rule=rule_id,
            created_by_rule_version=rule_version,
            reason_code=reason_code,
            base_confidence=ScoreValue(base_confidence),
            flags=flags,
        )
        return claim_id

    def get_claim(self, claim_id: int) -> Claim:
        return self._claims[claim_id]

    def add_evidence(
        self,
        claim_id: int,
        raw_ref_id: int,
        evidence_type: int,
        strength: float,
    ) -> int:
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
        evidence_id = self._allocate_id("evidence")
        self._evidences[evidence_id] = Evidence(
            id=evidence_id,
            claim_id=claim_id,
            raw_ref_id=raw_ref_id,
            type=evidence_type,
            strength=ScoreValue(strength),
        )
        return evidence_id

    def get_evidence(self, evidence_id: int) -> Evidence:
        return self._evidences[evidence_id]

    def evidences_for_claim(self, claim_id: int) -> list[Evidence]:
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
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
        return relation_id

    def get_relation(self, relation_id: int) -> Relation:
        return self._relations[relation_id]

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
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")

        # severity 검증은 dedup 분기 전에 한다. severity 는 dedup key 가 아니지만,
        # 입력 검증 의미 (ScoreValue 의 [0.0, 1.0] 검증) 는 dedup hit/miss 모두에서
        # 동일하게 적용되어야 한다. dedup hit 시 검증을 건너뛰면 잘못된 severity 가
        # silent pass 됨 — PR4 이전 add_gap 의 입력 검증 의미와 충돌.
        validated_severity = ScoreValue(severity)

        subject_id = self._claims[claim_id].subject_id
        key = (subject_id, rule_id, gap_type, required_evidence_type)

        if key in self._gap_dedup_index:
            existing_gap_id = self._gap_dedup_index[key]
            self._claim_gap_refs.setdefault(claim_id, set()).add(existing_gap_id)
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
        return gap_id

    def get_gap(self, gap_id: int) -> Gap:
        return self._gaps[gap_id]

    def gaps_for_claim(self, claim_id: int) -> list[Gap]:
        """Return Gaps this claim references (PR4 §16 의미 확장).

        이전 (Phase 2): ``gap.claim_id == claim_id`` 필터.
        이후 (PR4):    ``_claim_gap_refs[claim_id]`` 기반.

        dedup 으로 reuse 된 gap 도 포함된다. 반환 순서는 gap_id 오름차순
        (결정적).
        """
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
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
        if evidence_id not in self._evidences:
            raise KeyError(f"unknown evidence_id: {evidence_id}")
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
        return tuple(newly_resolved)

    def gap_resolution(self, gap_id: int) -> int | None:
        """Return the evidence_id that resolved this gap, or None if unresolved.

        Raises:
            KeyError: unknown gap_id.
        """
        if gap_id not in self._gaps:
            raise KeyError(f"unknown gap_id: {gap_id}")
        return self._gap_resolutions.get(gap_id)

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
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
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
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
        if evidence_id not in self._evidences:
            raise KeyError(f"unknown evidence_id: {evidence_id}")
        bucket = self._contradictions.setdefault(claim_id, set())
        if evidence_id in bucket:
            return False
        bucket.add(evidence_id)
        return True

    def contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]:
        """Return contradicting evidence_ids for the claim.

        Returns:
            evidence_id 오름차순 tuple. 없으면 빈 tuple.

        Raises:
            KeyError: unknown claim_id.
        """
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
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
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
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
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
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
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
        if evidence_id not in self._evidences:
            raise KeyError(f"unknown evidence_id: {evidence_id}")
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
        return True

    def resolved_contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]:
        """Return resolved evidence_ids for the claim.

        Returns:
            evidence_id 오름차순 tuple. 없으면 빈 tuple.

        Raises:
            KeyError: unknown claim_id.
        """
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
        return tuple(sorted(self._resolved_contradictions.get(claim_id, set())))

    def active_contradictions_for_claim(self, claim_id: int) -> tuple[int, ...]:
        """Return contradicting evidence_ids that are still active (not resolved).

        = contradictions_for_claim(c) - resolved_contradictions_for_claim(c)

        Returns:
            evidence_id 오름차순 tuple. status 무관 (모든 status 에서 호출 가능).

        Raises:
            KeyError: unknown claim_id.
        """
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
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
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
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
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
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
                return True
        return False

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
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
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
        if evidence_id not in self._evidences:
            raise KeyError(f"unknown evidence_id: {evidence_id}")
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
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
        contras = self._contradictions.get(claim_id, set())
        resolved = self._resolved_contradictions.get(claim_id, set())
        return tuple(sorted(contras - resolved, reverse=True))

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
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
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
            return True
        return False

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

    def get_rule(self, rule_id: int, rule_version: int) -> RuleDefinition:
        key = (rule_id, rule_version)
        if key not in self._rule_definitions:
            raise KeyError(
                f"unknown rule: rule_id={rule_id}, version={rule_version}"
            )
        return self._rule_definitions[key]

    def get_rule_stats(self, rule_id: int, rule_version: int) -> RuleStats:
        key = (rule_id, rule_version)
        if key not in self._rule_stats:
            raise KeyError(
                f"unknown rule: rule_id={rule_id}, version={rule_version}"
            )
        return self._rule_stats[key]

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

    def _rule_stats_modifier_for_claim(self, claim: Claim) -> float:
        """PR20-F §32 — weak maturity signal (NOT rule quality verdict).

        Sub-decision V/W/X/Y:
            - V: firing_count 만 본다 (outcome ratio / precision / FPR / timestamp OOS)
            - W: binary threshold = _RULE_STATS_MIN_FIRING_COUNT (= 2)
            - X: no boost (modifier ∈ {0.9, 1.0})
            - Y: sentinel (created_by_rule == 0) / lookup miss → 1.0 (호환 보존)
        """
        if claim.created_by_rule == 0:
            return 1.0
        key = (claim.created_by_rule, claim.created_by_rule_version)
        stats = self._rule_stats.get(key)
        if stats is None:
            return 1.0
        if stats.firing_count < _RULE_STATS_MIN_FIRING_COUNT:
            return _RULE_STATS_PENALTY_MODIFIER
        return 1.0

    def register_hint_evidence_types(self, types: Iterable[int]) -> None:
        """PR21-L §33 + PR22-S §34 — register caller-defined "hint-like" evidence type ids.

        Sub-decision AF: framework 는 Evidence.type 정수 의미를 소유하지 않는다.
        caller 가 어떤 정수가 "hint" 인지 알려준다. types.py / __init__.py /
        rule_output.py 변경 없음.

        PR22-S §34 strict validation (Sub-decision AI/AJ/AK/AL/AM/AN):
            - AI: no implicit casting — int(t) cast 하지 않음
            - AJ: int 만 허용, bool 거부 (bool 검사를 int 검사 이전에 — Python
                  isinstance(True, int) == True 함정 회피)
            - AK: 값 범위 제한 없음 (음수 / 0 / 큰 정수 모두 허용 — taxonomy
                  ownership 회피)
            - AL: all-or-nothing — 임시 set 으로 검증 완료 후에만 union
            - AM: non-iterable input → TypeError. str / bytes 는 technically
                  iterable 이지만 API 입력 컨테이너로 거부
            - AN: state shape / snapshot schema 무변화

        Args:
            types: hint evidence type ids. list / tuple / set / frozenset /
                generator 등 `Iterable[int]` 허용. str / bytes 컨테이너는 거부.
                빈 iterable 은 no-op. 중복은 idempotent (set union 누적).

        Raises:
            TypeError: input 이 str/bytes 컨테이너이거나, element 가 int 가
                아닌 경우 (bool 포함). partial mutation 발생하지 않음.
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
        self._hint_evidence_types.update(validated)

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

        count_modifier (PR19-E §31.3, Sub-decision E-2 + E-4 — binary supplemental):
            active_count = len(active_contradictions_for_claim(claim_id))
            if active_count >= 2: → _COUNT_PENALTY_MODIFIER (0.8)
            else: → 1.0

        rule_stats_modifier (PR20-F §32.8, Sub-decision V + W + X + Y — weak maturity):
            if claim.created_by_rule == 0: → 1.0
            elif (rule_id, rule_version) miss: → 1.0
            elif firing_count < 2: → _RULE_STATS_PENALTY_MODIFIER (0.9)
            else: → 1.0

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
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
        claim = self._claims[claim_id]
        status_modifier = _STATUS_TO_MODIFIER[claim.status]

        active = self.active_contradictions_by_freshness(claim_id)
        if not active:
            freshness_modifier = 1.0
        else:
            most_recent_evidence = self._evidences[active[0]]
            freshness_modifier = (
                1.0
                - most_recent_evidence.strength.value * _FRESHNESS_PENALTY_WEIGHT
            )

        gap_modifier = self._gap_modifier_for_claim(claim_id)

        active_count = len(self.active_contradictions_for_claim(claim_id))
        count_modifier = (
            _COUNT_PENALTY_MODIFIER if active_count >= 2 else 1.0
        )

        rule_stats_modifier = self._rule_stats_modifier_for_claim(claim)
        evidence_type_modifier = self._evidence_type_modifier_for_claim(claim_id)

        return ScoreValue(
            claim.base_confidence.value
            * status_modifier
            * freshness_modifier
            * gap_modifier
            * count_modifier
            * rule_stats_modifier
            * evidence_type_modifier
        )

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
        key = (rule_id, rule_version)
        if key not in self._rule_stats:
            raise KeyError(
                f"unknown rule: rule_id={rule_id}, version={rule_version}"
            )
        current = self._rule_stats[key]
        self._rule_stats[key] = RuleStats(
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
        snapshot = _migrate_snapshot_to_current(snapshot)
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
        engine._gap_dedup_index = {
            tuple(item["key"]): item["value"] for item in snapshot["gap_dedup_index"]
        }
        engine._claim_gap_refs = {
            item["key"]: set(item["value"]) for item in snapshot["claim_gap_refs"]
        }
        engine._gap_resolutions = {
            item["key"]: item["value"] for item in snapshot["gap_resolutions"]
        }
        engine._contradictions = {
            item["key"]: set(item["value"]) for item in snapshot["contradictions"]
        }
        engine._resolved_contradictions = {
            item["key"]: set(item["value"])
            for item in snapshot["resolved_contradictions"]
        }
        engine._claim_lifecycle_events = {
            item["key"]: [
                ClaimLifecycleEvent(**event_dict) for event_dict in item["value"]
            ]
            for item in snapshot["claim_lifecycle_events"]
        }
        engine._hint_evidence_types = set(snapshot["hint_evidence_types"])
        return engine


# ---- Snapshot migration framework (PR18-K §30 + PR21-L §33) ---------------
# Engine 내부 private — public export 안 함.
# 미래 schema 변경 시 _SUPPORTED 확장 + migration step 추가.


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
