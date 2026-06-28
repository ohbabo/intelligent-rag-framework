"""C7 rule definition and operational-statistics mixin.

Behaviour-preserving extraction from ragcore.engine.Engine (Phase 3B-3 of the
Engine v1 refactoring; ADR docs/architecture/ENGINE_V1_PHASE3A_ARCHITECTURE_DECISION.md).
The four method bodies are moved verbatim (AST-identical). Both stores
(``self._rule_definitions``, ``self._rule_stats``) stay on Engine and the C1
seams (``self._assert_rule_pair_exists``, ``self._assert_rule_stats_pair_exists``,
``self._advance_state_revision``) stay on the Engine base. The C7 asymmetry is
preserved unchanged: ``register_rule`` guards only ``_rule_definitions`` (insert)
and assigns ``_rule_stats`` unconditionally (insert for a fresh key, replace for
an orphan-restored stats key); ``get_rule`` / ``get_rule_stats`` use independent
guards so a definition-only or stats-only restored state is each handled on its
own store. This mixin contributes methods only — no __init__, no state, no
Engine back-reference, no definition/stats consistency layer.
"""

from __future__ import annotations

from ragcore.types import RuleDefinition, RuleStats, ScoreValue


class RulesMixin:
    """C7 cluster: rule registration + definition/stats lookup + stats update.
    Methods reach the Engine-owned ``self._rule_definitions`` /
    ``self._rule_stats`` stores and the C1 guard/revision seams through ``self``
    (resolved via the Engine MRO)."""

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
