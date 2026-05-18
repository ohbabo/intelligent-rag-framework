"""Rule firing runtime — condition 평가 + (true 일 때) claim/gap 생성 + stats 갱신.

API 공개:
- ``fire_rule(...) -> int | None``         (16/19차, 변경 없음 — 하위 호환)
- ``fire_rule_with_trace(...) -> FiringTrace``  (22차 신규)
- ``FiringTrace`` (frozen dataclass, §15)

두 공개 함수는 **단일 private helper** ``_fire_rule_core`` 만 호출한다.
divergence 방지 + condition 평가 1회 보장. trade-off: fast path 도 항상
trace 를 빌드 (MVP 에서 비용 미미). 자세한 계약은 docs/contracts/05 §15.

scope (MVP):
- compile 결과들을 받아서 한 번에 firing.
- condition true → engine.add_claim + (optional) Gap 생성 + firing_count +1.
- condition false → state 변화 없음.
- subject_id 는 caller 가 제공 (entity resolver 결정점 분리).

out of scope:
- trace 영속화 (Engine 저장 / DB / 직렬화)
- trace timestamp / context snapshot
- candidate → confirmed 자동 승격
- 다중 claim 동시 생성
- batch firing
- Gap severity 차별화 / dedup / merge / 다양한 GapType
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ragcore.condition import ConditionTree, Trace, evaluate_condition_with_trace
from ragcore.engine import Engine
from ragcore.rule_gap import (
    DEFAULT_GAP_SEVERITY,
    GAP_TYPE_MISSING_EVIDENCE,
    RequiredEvidenceTemplate,
)
from ragcore.rule_output import RuleOutputTemplate
from ragcore.types import RuleDefinition


@dataclass(frozen=True)
class FiringTrace:
    """Record of one rule firing attempt (§15).

    fired=False 면 claim_id=None, gap_ids=(). fired=True 면 claim_id 값 존재.
    ``required_evidence`` 가 None 이거나 빈 template 이면 fired=True 여도
    gap_ids=().

    불변식:
        trace.fired == (trace.claim_id is not None)
        trace.condition_trace.result == trace.fired
    """

    rule_id: int
    rule_version: int
    subject_id: int
    fired: bool
    condition_trace: Trace
    claim_id: int | None
    gap_ids: tuple[int, ...]


def _fire_rule_core(
    engine: Engine,
    definition: RuleDefinition,
    condition: ConditionTree,
    output: RuleOutputTemplate,
    *,
    subject_id: int,
    context: Mapping[str, Any],
    required_evidence: RequiredEvidenceTemplate | None,
) -> FiringTrace:
    """Single source of truth for rule firing.

    ``fire_rule`` / ``fire_rule_with_trace`` 둘 다 이 함수를 호출한다.
    Condition 평가는 ``evaluate_condition_with_trace`` 만 사용해
    **정확히 한 번** 실행된다 — fast path 와 trace path 사이 로직 divergence
    방지.

    Engine state 변경 (Claim / Gap 생성, firing_count +1) 은 condition 이
    true 일 때만 발생. 미등록 rule 은 즉시 ``KeyError`` (FiringTrace 미생성).
    """
    # Fail-fast: rule must already be registered. update_rule_stats 가
    # 어차피 KeyError 를 던질 텐데, 거기서 던지면 이미 claim 이 생긴 뒤다.
    # 미리 검사해서 부분 mutation 을 막는다. fired=False trace 로 감싸지 X —
    # 미등록은 호출자 버그이므로 KeyError 가 맞다.
    engine.get_rule_stats(definition.id, definition.version)

    # Condition 평가는 한 번만. trace 가 result 도 포함하므로 별도
    # evaluate_condition 호출은 필요 없음.
    condition_trace = evaluate_condition_with_trace(condition, context)

    if not condition_trace.result:
        return FiringTrace(
            rule_id=definition.id,
            rule_version=definition.version,
            subject_id=subject_id,
            fired=False,
            condition_trace=condition_trace,
            claim_id=None,
            gap_ids=(),
        )

    claim_id = engine.add_claim(
        subject_id=subject_id,
        claim_type=output.claim_type,
        rule_id=definition.id,
        rule_version=definition.version,
        reason_code=output.reason_code,
        base_confidence=output.base_confidence.value,
        status=output.status,
    )

    gap_ids: list[int] = []
    if required_evidence is not None:
        for evidence_type in required_evidence.evidence_types:
            gap_id = engine.add_gap(
                claim_id=claim_id,
                gap_type=GAP_TYPE_MISSING_EVIDENCE,
                required_evidence_type=evidence_type,
                severity=DEFAULT_GAP_SEVERITY.value,
                rule_id=definition.id,
            )
            gap_ids.append(gap_id)

    engine.update_rule_stats(
        definition.id,
        definition.version,
        firing_delta=1,
    )

    return FiringTrace(
        rule_id=definition.id,
        rule_version=definition.version,
        subject_id=subject_id,
        fired=True,
        condition_trace=condition_trace,
        claim_id=claim_id,
        gap_ids=tuple(gap_ids),
    )


def fire_rule(
    engine: Engine,
    definition: RuleDefinition,
    condition: ConditionTree,
    output: RuleOutputTemplate,
    *,
    subject_id: int,
    context: Mapping[str, Any],
    required_evidence: RequiredEvidenceTemplate | None = None,
) -> int | None:
    """Evaluate ``condition`` and fire claim + optional gaps if true.

    Returns ``claim_id`` (int) if condition true, ``None`` otherwise.

    Side effects (only when condition true):
    - ``engine.add_claim(...)`` creates a Claim
    - 각 ``required_evidence.evidence_types`` 마다 ``engine.add_gap(...)``
      호출 (None / empty 면 skip)
    - ``engine.update_rule_stats(..., firing_delta=1)`` increments firing_count

    No state change when condition false — Claim 미생성, Gap 미생성,
    firing_count 그대로.

    Pre-checks:
    - ``definition`` 의 ``(id, version)`` 이 engine 에 등록되어 있어야 함.
      미등록이면 즉시 ``KeyError`` — claim 생성 전에 fail-fast 해서 부분
      상태가 남지 않게 한다.

    Args:
        required_evidence: ``None`` 또는 ``evidence_types=()`` 면 Gap 생성
            안 함 (16차 동작 보존). 그 외에는 condition true 시 evidence_types
            의 각 항목마다 Gap 생성.

    Raises:
        KeyError: definition 미등록, 또는 subject_id 가 engine 의 entity 아님.

    Note:
        22차에서 ``_fire_rule_core`` 를 거치는 얇은 wrapper 로 전환됨.
        시그니처 / 반환값 / side effect / 예외 동작 모두 16~19차와 동일.
        ``fire_rule_with_trace`` 와 동일한 firing 로직을 공유한다.
    """
    return _fire_rule_core(
        engine,
        definition,
        condition,
        output,
        subject_id=subject_id,
        context=context,
        required_evidence=required_evidence,
    ).claim_id


def fire_rule_with_trace(
    engine: Engine,
    definition: RuleDefinition,
    condition: ConditionTree,
    output: RuleOutputTemplate,
    *,
    subject_id: int,
    context: Mapping[str, Any],
    required_evidence: RequiredEvidenceTemplate | None = None,
) -> FiringTrace:
    """Same firing semantics as ``fire_rule`` but returns the full ``FiringTrace``.

    **중요**: 이 함수는 explain-only 가 아니다. ``fire_rule`` 과 동일하게
    Engine 상태를 변경한다 — Claim / Gap 생성, firing_count +1 모두 동일.
    같은 입력으로 두 함수를 호출하면 만들어지는 engine 상태는 일치한다.

    차이는 반환값뿐:
    - ``fire_rule`` → ``claim_id | None``
    - ``fire_rule_with_trace`` → ``FiringTrace`` (rule_id, version, subject_id,
      fired, condition_trace, claim_id, gap_ids)

    Pre-check 동작도 동일 — 미등록 rule 은 ``KeyError`` raise 하고
    ``FiringTrace`` 미생성 (fired=False 로 감싸지 않음).
    """
    return _fire_rule_core(
        engine,
        definition,
        condition,
        output,
        subject_id=subject_id,
        context=context,
        required_evidence=required_evidence,
    )
