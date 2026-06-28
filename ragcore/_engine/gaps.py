"""C4 gap creation, lookup, reference, and resolution mixin.

Behaviour-preserving extraction from ragcore.engine.Engine (Phase 3B-4 of the
Engine v1 refactoring; ADR docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md).
The five method bodies are moved verbatim (AST-identical). The four C4 stores
(``self._gaps``, ``self._gap_dedup_index``, ``self._claim_gap_refs``,
``self._gap_resolutions``) stay on Engine, as do the C2 stores this cluster
reads (``self._claims``, ``self._evidences``) and the C1 seams
(``self._assert_claim_exists`` / ``self._assert_evidence_exists`` /
``self._assert_gap_exists`` / ``self._allocate_id`` /
``self._advance_state_revision``). The load-bearing C4 contracts are preserved
unchanged: severity is admitted BEFORE the dedup decision; the dedup key is
(subject_id, rule_id, gap_type, required_evidence_type) so the same subject's
distinct claims can share a Gap with the first registrant's claim_id/severity;
a dedup hit advances the revision only when a NEW claim->gap reference is added;
``resolve_gaps_for_evidence`` is first-evidence-wins (no overwrite) and advances
the revision once per logical call. ``resolve_gaps_for_evidence`` keeps calling
the inherited ``self.gaps_for_claim``. This mixin contributes methods only — no
__init__, no state, no Engine back-reference.
"""

from __future__ import annotations

from ragcore.types import Gap, ScoreValue


class GapsMixin:
    """C4 cluster: gap creation (dedup), lookup, per-claim references, and
    evidence-driven resolution. Methods reach the Engine-owned gap stores, the
    C2 claim/evidence stores (read-only), and the C1 guard/id/revision seams
    through ``self`` (resolved via the Engine MRO)."""

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
