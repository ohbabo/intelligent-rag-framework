"""C5 lifecycle-transition + contradiction-state mixin.

Behaviour-preserving extraction from ragcore.engine.Engine (Phase 3B-8 of the
Engine v1 refactoring; ADR docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md).
The twelve method bodies, signatures, method-body ASTs, and method docstring
texts are moved verbatim; the function-object identities and declaring locations
intentionally change to LifecycleMixin (__module__ / __qualname__ / declaring
class). The private refutation-strength threshold moves here with the two refute
APIs that use it: its name (_REFUTATION_STRENGTH_THRESHOLD), value (0.8), private
status, and >= comparison are preserved; only its declaring module changes (it is
the single threshold authority, reused by both PR10-A and PR11-B refute APIs and
never exported).

The four operational stores (self._claims / self._evidences / self._contradictions
/ self._resolved_contradictions) stay on Engine. The C1 seams
(self._assert_claim_exists / self._assert_evidence_exists /
self._advance_state_revision), the C4 queries (self.gaps_for_claim /
self.gap_resolution), and the C6 recorder (self._record_claim_lifecycle_transition)
are all resolved through self/MRO. _claims is the one operational shared-write
store: CrudMixin (C2) inserts new Claims, these transitions replace their status on
the SAME dict, and CrudMixin.get_claim observes the replacement. Every successful
transition keeps the load-bearing order status-replace -> lifecycle-record ->
revision-advance; no-op/failure paths mutate nothing, record nothing, and advance
no revision. This mixin contributes methods only — no __init__, no state, no
Engine back-reference, no super(), no inter-mixin import.
"""

from __future__ import annotations

from dataclasses import replace

from ragcore.types import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
)


_REFUTATION_STRENGTH_THRESHOLD = 0.8


class LifecycleMixin:
    """C5 cluster: claim status transitions (confirm / refute / dispute / resolve-
    disputed / refute-disputed / refute-disputed-by-freshness) plus contradiction
    registration, resolution, and active / resolved / freshness queries. All state
    lives in the Engine-owned _claims / _evidences / _contradictions /
    _resolved_contradictions dicts and is reached through ``self`` (Engine MRO);
    the C1 guards/revision seam, the C4 gap queries, and the C6 lifecycle recorder
    are likewise resolved through ``self``."""

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

    # ---- Freshness queries (PR9-A §21 active-set, freshness ordering) -----

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
