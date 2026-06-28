"""C8 hint-evidence registration and deregistration mixin.

Behaviour-preserving extraction from ragcore.engine.Engine (Phase 3B-1 of the
Engine v1 refactoring; ADR docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md).
The four method bodies are moved verbatim (AST-identical); the state
(``self._hint_evidence_types``) stays on Engine and the revision seam
(``self._advance_state_revision``) stays on the Engine base (C1). This mixin
contributes methods only — no __init__, no state, no Engine back-reference.
"""

from __future__ import annotations

from collections.abc import Iterable


class HintEvidenceMixin:
    """C8 cluster: caller-registered hint evidence type ids (register /
    unregister / clear) + their shared strict validator. Methods access the
    Engine-owned ``self._hint_evidence_types`` set and the C1
    ``self._advance_state_revision`` seam through ``self`` (resolved via the
    Engine MRO)."""

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
