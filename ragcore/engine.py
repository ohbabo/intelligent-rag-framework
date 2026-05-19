"""Engine — owns ID allocation and per-kind storage.

Reference implementation. ID 발급은 kind 별 단조 증가 카운터.
참조 무결성: add_* 메서드는 참조 대상이 (kind, id) 쌍으로 정확히 존재해야 통과.
"""

from __future__ import annotations

from dataclasses import replace

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
    Entity,
    Evidence,
    Gap,
    Observation,
    Relation,
    RuleDefinition,
    RuleStats,
    ScoreValue,
)


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
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_CONFIRMED)
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
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_REFUTED)
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
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_DISPUTED)
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
        self._claims[claim_id] = replace(claim, status=CLAIM_STATUS_CONFIRMED)
        return True

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

    def compute_effective_confidence(self, claim_id: int) -> ScoreValue:
        """Current effective confidence for a claim.

        **MVP stub**: returns `base_confidence` unchanged. Phase 2+에서
        evidence_strength 와 RuleStats(observed_precision / false_positive_rate)
        를 조합한다. 이 자리는 의도된 stub이므로 무심코 "고치지" 말 것 —
        scoring 로직은 별도 PR에서 명시적으로 들어온다.
        """
        if claim_id not in self._claims:
            raise KeyError(f"unknown claim_id: {claim_id}")
        return self._claims[claim_id].base_confidence

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
