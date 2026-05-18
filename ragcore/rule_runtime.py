"""Rule firing runtime — condition 평가 + (true 일 때) claim/gap 생성 + stats 갱신.

scope (MVP):
- compile 결과들을 받아서 한 번에 firing.
- condition true → engine.add_claim + (optional) Gap 생성 + firing_count +1.
- condition false → state 변화 없음.
- subject_id 는 caller 가 제공 (entity resolver 결정점 분리).
- required_evidence 는 optional — None / empty 면 16차 동작과 동일 (하위 호환).

out of scope:
- trace 반환 (별도 helper)
- candidate → confirmed 자동 승격
- 다중 claim 동시 생성
- batch firing
- Gap severity 차별화 / dedup / merge / 다양한 GapType (별도 결정점)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ragcore.condition import ConditionTree, evaluate_condition
from ragcore.engine import Engine
from ragcore.rule_gap import (
    DEFAULT_GAP_SEVERITY,
    GAP_TYPE_MISSING_EVIDENCE,
    RequiredEvidenceTemplate,
)
from ragcore.rule_output import RuleOutputTemplate
from ragcore.types import RuleDefinition


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
    """
    # Fail-fast: rule must already be registered. update_rule_stats 가
    # 어차피 KeyError 를 던질 텐데, 거기서 던지면 이미 claim 이 생긴 뒤다.
    # 미리 검사해서 부분 mutation 을 막는다.
    engine.get_rule_stats(definition.id, definition.version)

    if not evaluate_condition(condition, context):
        return None

    claim_id = engine.add_claim(
        subject_id=subject_id,
        claim_type=output.claim_type,
        rule_id=definition.id,
        rule_version=definition.version,
        reason_code=output.reason_code,
        base_confidence=output.base_confidence.value,
        status=output.status,
    )

    if required_evidence is not None:
        for evidence_type in required_evidence.evidence_types:
            engine.add_gap(
                claim_id=claim_id,
                gap_type=GAP_TYPE_MISSING_EVIDENCE,
                required_evidence_type=evidence_type,
                severity=DEFAULT_GAP_SEVERITY.value,
                rule_id=definition.id,
            )

    engine.update_rule_stats(
        definition.id,
        definition.version,
        firing_delta=1,
    )

    return claim_id
