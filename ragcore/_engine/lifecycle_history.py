"""C6 claim-lifecycle-history mixin.

Behaviour-preserving extraction from ragcore.engine.Engine (Phase 3B-6 of the
Engine v1 refactoring; ADR docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md).
The two method bodies are moved verbatim (AST-identical), INCLUDING the
pre-existing "5 lifecycle API" docstring wording (see the dev record: the
measured self-call fan-in into _record_claim_lifecycle_transition is 6 after the
freshness-based refutation path was added; this extraction preserves the original
function object and docstring verbatim and does NOT reinterpret the contract).
The two stores (self._lifecycle_seq, self._claim_lifecycle_events) stay on Engine
and the C1 guard (self._assert_claim_exists) stays on the Engine base. The six C5
lifecycle transitions keep calling self._record_claim_lifecycle_transition via the
MRO (no C6 import). This mixin contributes methods only — no __init__, no state,
no Engine back-reference.
"""

from __future__ import annotations

from ragcore.types import ClaimLifecycleEvent


class LifecycleHistoryMixin:
    """C6 cluster: the private lifecycle-transition recorder + the public
    per-claim history reader. The recorder writes self._lifecycle_seq /
    self._claim_lifecycle_events (Engine-owned) and the reader uses the C1
    self._assert_claim_exists guard, all through ``self`` (Engine MRO)."""

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
