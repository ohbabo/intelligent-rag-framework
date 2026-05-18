"""Tests for ragcore.rule_runtime — fire_rule MVP.

Coverage:
- condition true → claim 생성 + firing_count +1, 반환 claim_id
- condition false → None + 상태 변화 0
- claim 필드 매핑 검증 (subject / type / rule_id+version / reason_code /
  base_confidence / status)
- 미등록 rule → fail-fast KeyError, claim 미생성
- unknown subject_id → KeyError 전파
- 여러 번 firing → claim 누적 + firing_count 누적
- mixed true/false firing → true 횟수만 카운트
- YAML → register → compile → fire 전 체인
"""

from __future__ import annotations

from typing import Any

import pytest

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    Engine,
    FiringTrace,
    RequiredEvidenceTemplate,
    ScoreValue,
    compile_required_evidence,
    compile_rule_condition,
    compile_rule_definition,
    compile_rule_output,
    fire_rule_with_trace,
    load_rule_spec,
    load_rule_spec_from_yaml,
    register_rule_spec,
)
from ragcore.condition import (
    TRACE_REASON_MATCH,
    TRACE_REASON_MISMATCH,
    TRACE_REASON_MISSING_FIELD,
    CombinatorTrace,
    PredicateTrace,
)
from ragcore.rule_gap import (
    DEFAULT_GAP_SEVERITY,
    GAP_TYPE_MISSING_EVIDENCE,
)
from ragcore.rule_runtime import fire_rule


SSH_SPEC_DICT: dict[str, Any] = {
    "id": "RULE_DOMAIN_SSH_001",
    "version": 1,
    "maturity": "experimental",
    "reliability": {"prior_confidence": 0.5},
    "condition": {
        "all": [
            {"field": "port", "op": "eq", "value": 22},
            {"field": "banner", "op": "contains", "value": "OpenSSH_7."},
        ]
    },
    "output": {"claim": {
        "type": "outdated_ssh_candidate",
        "status": "candidate",
        "base_confidence": 0.55,
        "reason_code": "OPENSSH_7_SERIES_BANNER",
    }},
}


def _setup() -> tuple[Engine, Any, Any, Any, int]:
    """Returns (engine, definition, condition_tree, output_template, subject_id)."""
    engine = Engine()
    spec = load_rule_spec(SSH_SPEC_DICT)
    definition = register_rule_spec(engine, spec)
    condition = compile_rule_condition(spec)
    output = compile_rule_output(spec)
    subject_id = engine.add_entity(entity_type=1)
    return engine, definition, condition, output, subject_id


# =====================================================================
# condition true — claim 생성 + firing_count +1
# =====================================================================

class TestFireRuleTrue:
    CTX_MATCH = {"port": 22, "banner": "OpenSSH_7.4p1"}

    def test_returns_claim_id(self) -> None:
        engine, definition, cond, out, subject = _setup()
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        assert isinstance(claim_id, int)

    def test_claim_subject_preserved(self) -> None:
        engine, definition, cond, out, subject = _setup()
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        assert engine.get_claim(claim_id).subject_id == subject

    def test_claim_type_from_output_template(self) -> None:
        engine, definition, cond, out, subject = _setup()
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        assert engine.get_claim(claim_id).type == out.claim_type

    def test_claim_rule_id_and_version_from_definition(self) -> None:
        engine, definition, cond, out, subject = _setup()
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        claim = engine.get_claim(claim_id)
        assert claim.created_by_rule == definition.id
        assert claim.created_by_rule_version == definition.version

    def test_claim_reason_code(self) -> None:
        engine, definition, cond, out, subject = _setup()
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        assert engine.get_claim(claim_id).reason_code == out.reason_code

    def test_claim_base_confidence(self) -> None:
        engine, definition, cond, out, subject = _setup()
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        assert engine.get_claim(claim_id).base_confidence == out.base_confidence

    def test_claim_status_from_output_template(self) -> None:
        engine, definition, cond, out, subject = _setup()
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        claim = engine.get_claim(claim_id)
        assert claim.status == out.status == CLAIM_STATUS_CANDIDATE

    def test_firing_count_incremented(self) -> None:
        engine, definition, cond, out, subject = _setup()
        stats_before = engine.get_rule_stats(definition.id, definition.version)
        assert stats_before.firing_count == 0
        fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        stats_after = engine.get_rule_stats(definition.id, definition.version)
        assert stats_after.firing_count == 1


# =====================================================================
# condition false — no state change
# =====================================================================

class TestFireRuleFalse:
    def test_value_mismatch_returns_none(self) -> None:
        engine, definition, cond, out, subject = _setup()
        ctx = {"port": 80, "banner": "OpenSSH_7.4p1"}
        result = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=ctx,
        )
        assert result is None

    def test_missing_field_returns_none(self) -> None:
        engine, definition, cond, out, subject = _setup()
        ctx = {"port": 22}  # banner 누락
        result = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=ctx,
        )
        assert result is None

    def test_no_claim_created_on_false(self) -> None:
        engine, definition, cond, out, subject = _setup()
        ctx = {"port": 80}
        fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=ctx,
        )
        # claim_id 가 할당되지 않았으니 어떤 id 도 fetch 실패
        with pytest.raises(KeyError):
            engine.get_claim(1)

    def test_firing_count_unchanged_on_false(self) -> None:
        engine, definition, cond, out, subject = _setup()
        ctx = {"port": 80}
        fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=ctx,
        )
        stats = engine.get_rule_stats(definition.id, definition.version)
        assert stats.firing_count == 0

    def test_other_stats_unchanged_on_false(self) -> None:
        engine, definition, cond, out, subject = _setup()
        ctx = {"port": 80}
        fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=ctx,
        )
        stats = engine.get_rule_stats(definition.id, definition.version)
        assert stats.confirmed_true_count == 0
        assert stats.confirmed_false_count == 0
        assert stats.observed_precision is None
        assert stats.false_positive_rate is None


# =====================================================================
# error paths
# =====================================================================

class TestFireRuleErrors:
    CTX_MATCH = {"port": 22, "banner": "OpenSSH_7.4p1"}

    def test_unknown_subject_id_propagates_keyerror(self) -> None:
        engine, definition, cond, out, _ = _setup()
        with pytest.raises(KeyError):
            fire_rule(
                engine, definition, cond, out,
                subject_id=99999,  # entity 미존재
                context=self.CTX_MATCH,
            )

    def test_unregistered_rule_fail_fast(self) -> None:
        """definition 이 engine 에 등록 안 됐으면 KeyError, claim 미생성."""
        engine = Engine()
        spec = load_rule_spec(SSH_SPEC_DICT)
        definition = compile_rule_definition(spec)  # registered X
        cond = compile_rule_condition(spec)
        out = compile_rule_output(spec)
        subject_id = engine.add_entity(entity_type=1)

        with pytest.raises(KeyError):
            fire_rule(
                engine, definition, cond, out,
                subject_id=subject_id, context=self.CTX_MATCH,
            )

        # fail-fast 검증: claim 이 만들어지지 않았음
        with pytest.raises(KeyError):
            engine.get_claim(1)


# =====================================================================
# multiple firings
# =====================================================================

class TestFireRuleMultiple:
    CTX_MATCH = {"port": 22, "banner": "OpenSSH_7.4p1"}
    CTX_NO_MATCH = {"port": 80, "banner": "OpenSSH_7.4p1"}

    def test_multiple_true_firings_create_distinct_claims(self) -> None:
        engine, definition, cond, out, subject = _setup()
        ids = [
            fire_rule(
                engine, definition, cond, out,
                subject_id=subject, context=self.CTX_MATCH,
            )
            for _ in range(3)
        ]
        assert len(set(ids)) == 3
        assert all(i is not None for i in ids)

    def test_multiple_true_firings_accumulate_count(self) -> None:
        engine, definition, cond, out, subject = _setup()
        for _ in range(5):
            fire_rule(
                engine, definition, cond, out,
                subject_id=subject, context=self.CTX_MATCH,
            )
        stats = engine.get_rule_stats(definition.id, definition.version)
        assert stats.firing_count == 5

    def test_mixed_true_false_counts_only_true(self) -> None:
        engine, definition, cond, out, subject = _setup()
        ctxs = [
            self.CTX_MATCH,
            self.CTX_NO_MATCH,
            self.CTX_MATCH,
            self.CTX_NO_MATCH,
            self.CTX_MATCH,
        ]
        for ctx in ctxs:
            fire_rule(
                engine, definition, cond, out,
                subject_id=subject, context=ctx,
            )
        stats = engine.get_rule_stats(definition.id, definition.version)
        assert stats.firing_count == 3  # true 만 카운트


# =====================================================================
# YAML full chain end-to-end
# =====================================================================

class TestFireRuleYamlEndToEnd:
    YAML_TEXT = """
id: RULE_DOMAIN_SSH_001
version: 1
maturity: experimental
reliability:
  prior_confidence: 0.55
condition:
  all:
    - field: port
      op: eq
      value: 22
    - field: protocol
      op: eq
      value: tcp
    - field: service
      op: eq
      value: ssh
    - field: banner
      op: contains
      value: "OpenSSH_7."
output:
  claim:
    type: outdated_ssh_candidate
    status: candidate
    base_confidence: 0.55
    reason_code: OPENSSH_7_SERIES_BANNER
"""

    def test_yaml_to_claim_full_chain(self) -> None:
        engine = Engine()
        spec = load_rule_spec_from_yaml(self.YAML_TEXT)
        definition = register_rule_spec(engine, spec)
        condition = compile_rule_condition(spec)
        output = compile_rule_output(spec)
        subject_id = engine.add_entity(entity_type=1)

        ctx = {
            "port": 22,
            "protocol": "tcp",
            "service": "ssh",
            "banner": "OpenSSH_7.4p1",
        }
        claim_id = fire_rule(
            engine, definition, condition, output,
            subject_id=subject_id, context=ctx,
        )
        assert claim_id is not None
        claim = engine.get_claim(claim_id)
        assert claim.subject_id == subject_id
        assert claim.created_by_rule == 1
        assert claim.created_by_rule_version == 1
        assert claim.base_confidence == ScoreValue(0.55)
        assert claim.status == CLAIM_STATUS_CANDIDATE
        assert engine.get_rule_stats(1, 1).firing_count == 1

    def test_yaml_chain_no_fire_when_banner_modern(self) -> None:
        engine = Engine()
        spec = load_rule_spec_from_yaml(self.YAML_TEXT)
        definition = register_rule_spec(engine, spec)
        condition = compile_rule_condition(spec)
        output = compile_rule_output(spec)
        subject_id = engine.add_entity(entity_type=1)

        ctx = {
            "port": 22,
            "protocol": "tcp",
            "service": "ssh",
            "banner": "OpenSSH_9.0p1",  # 7.x 아님
        }
        result = fire_rule(
            engine, definition, condition, output,
            subject_id=subject_id, context=ctx,
        )
        assert result is None
        assert engine.get_rule_stats(1, 1).firing_count == 0


# =====================================================================
# 19차 — required_evidence 인자로 Gap 생성
# =====================================================================

class TestFireRuleWithRequiredEvidence:
    CTX_MATCH = {"port": 22, "banner": "OpenSSH_7.4p1"}

    def test_required_evidence_none_creates_no_gaps(self) -> None:
        """기본값 None — 16차 동작 보존 (하위 호환)."""
        engine, definition, cond, out, subject = _setup()
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=None,
        )
        assert claim_id is not None
        assert engine.gaps_for_claim(claim_id) == []

    def test_required_evidence_omitted_creates_no_gaps(self) -> None:
        """인자 생략도 None 과 동일."""
        engine, definition, cond, out, subject = _setup()
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        assert engine.gaps_for_claim(claim_id) == []

    def test_empty_template_creates_no_gaps(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=())
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        assert engine.gaps_for_claim(claim_id) == []

    def test_three_evidence_types_creates_three_gaps(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(1, 2, 3))
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        gaps = engine.gaps_for_claim(claim_id)
        assert len(gaps) == 3

    def test_gap_claim_id_links_to_created_claim(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(1,))
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        gap = engine.gaps_for_claim(claim_id)[0]
        assert gap.claim_id == claim_id

    def test_gap_type_is_missing_evidence(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(1,))
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        gap = engine.gaps_for_claim(claim_id)[0]
        assert gap.type == GAP_TYPE_MISSING_EVIDENCE

    def test_gap_required_evidence_types_preserve_order(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(3, 1, 2))
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        gaps = engine.gaps_for_claim(claim_id)
        assert [g.required_evidence_type for g in gaps] == [3, 1, 2]

    def test_gap_severity_is_default(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(1,))
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        gap = engine.gaps_for_claim(claim_id)[0]
        assert gap.severity == DEFAULT_GAP_SEVERITY

    def test_gap_created_by_rule_is_definition_id(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(1,))
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        gap = engine.gaps_for_claim(claim_id)[0]
        assert gap.created_by_rule == definition.id

    def test_duplicate_evidence_types_dedup_to_single_gap(self) -> None:
        """PR4 §16 — exact-match dedup. yaml 의 evidence_type 이 N번 같아도
        (subject, rule, gap_type, evidence_type) 동일하면 단 1개 Gap 만 생성.

        compile_required_evidence 는 여전히 중복을 tuple 에 보존하지만
        (e.g., evidence_types=(2,2,2)), Engine.add_gap 의 dedup 이 두 번째
        호출부터 기존 gap_id 를 반환한다. 따라서 engine 안의 실제 Gap 은 1개.

        FiringTrace.gap_ids 는 reuse 된 gap_id 를 N번 포함할 수 있다 (§15
        계약 — "신규 또는 재사용된 Gap id"). 다만 engine 의 set-based
        _claim_gap_refs 가 dedup 하므로 gaps_for_claim 은 1개 반환.
        """
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(2, 2, 2))
        claim_id = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        gaps = engine.gaps_for_claim(claim_id)
        assert len(gaps) == 1
        assert gaps[0].required_evidence_type == 2


class TestFireRuleFalseWithRequiredEvidence:
    def test_false_condition_creates_no_gaps_even_with_template(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(1, 2, 3))
        result = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context={"port": 80},  # banner 누락 + port 다름
            required_evidence=template,
        )
        assert result is None
        # claim_id 가 할당되지 않았음 → Gap 도 없음
        # gaps_for_claim 은 unknown claim 에 KeyError
        with pytest.raises(KeyError):
            engine.gaps_for_claim(1)

    def test_false_condition_firing_count_still_zero(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(1, 2, 3))
        fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context={"port": 80},
            required_evidence=template,
        )
        stats = engine.get_rule_stats(definition.id, definition.version)
        assert stats.firing_count == 0


class TestFireRuleYamlEndToEndWithGaps:
    YAML_TEXT = """
id: RULE_DOMAIN_SSH_001
version: 1
maturity: experimental
reliability:
  prior_confidence: 0.55
condition:
  all:
    - field: port
      op: eq
      value: 22
    - field: banner
      op: contains
      value: "OpenSSH_7."
output:
  claim:
    type: outdated_ssh_candidate
    status: candidate
    base_confidence: 0.55
    reason_code: OPENSSH_7_SERIES_BANNER
    required_evidence:
      - exact_openssh_version
      - os_family
      - package_backport_status
"""

    def test_full_chain_creates_claim_and_three_gaps(self) -> None:
        engine = Engine()
        spec = load_rule_spec_from_yaml(self.YAML_TEXT)
        definition = register_rule_spec(engine, spec)
        condition = compile_rule_condition(spec)
        output = compile_rule_output(spec)
        required = compile_required_evidence(spec)
        subject_id = engine.add_entity(entity_type=1)

        ctx = {"port": 22, "banner": "OpenSSH_7.4p1"}
        claim_id = fire_rule(
            engine, definition, condition, output,
            subject_id=subject_id, context=ctx,
            required_evidence=required,
        )
        assert claim_id is not None
        gaps = engine.gaps_for_claim(claim_id)
        assert len(gaps) == 3
        assert [g.required_evidence_type for g in gaps] == [1, 2, 3]
        for gap in gaps:
            assert gap.claim_id == claim_id
            assert gap.type == GAP_TYPE_MISSING_EVIDENCE
            assert gap.severity == DEFAULT_GAP_SEVERITY
            assert gap.created_by_rule == definition.id

    def test_full_chain_false_condition_creates_nothing(self) -> None:
        engine = Engine()
        spec = load_rule_spec_from_yaml(self.YAML_TEXT)
        definition = register_rule_spec(engine, spec)
        condition = compile_rule_condition(spec)
        output = compile_rule_output(spec)
        required = compile_required_evidence(spec)
        subject_id = engine.add_entity(entity_type=1)

        ctx = {"port": 22, "banner": "OpenSSH_9.0p1"}  # 7.x 아님
        result = fire_rule(
            engine, definition, condition, output,
            subject_id=subject_id, context=ctx,
            required_evidence=required,
        )
        assert result is None
        # claim 없음 → gap 도 없음
        with pytest.raises(KeyError):
            engine.gaps_for_claim(1)
        assert engine.get_rule_stats(1, 1).firing_count == 0


# =====================================================================
# 22차 — fire_rule_with_trace (§15)
# =====================================================================

class TestFireRuleWithTraceTrue:
    """condition true → FiringTrace.fired=True + claim/gap 생성."""

    CTX_MATCH = {"port": 22, "banner": "OpenSSH_7.4p1"}

    def test_returns_firing_trace(self) -> None:
        engine, definition, cond, out, subject = _setup()
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        assert isinstance(trace, FiringTrace)

    def test_rule_id_version_subject_preserved(self) -> None:
        engine, definition, cond, out, subject = _setup()
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        assert trace.rule_id == definition.id
        assert trace.rule_version == definition.version
        assert trace.subject_id == subject

    def test_fired_true_when_condition_matches(self) -> None:
        engine, definition, cond, out, subject = _setup()
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        assert trace.fired is True
        assert trace.claim_id is not None
        assert trace.condition_trace.result is True

    def test_claim_actually_created(self) -> None:
        engine, definition, cond, out, subject = _setup()
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        # trace.claim_id 로 실제 engine 에서 조회 가능
        claim = engine.get_claim(trace.claim_id)  # type: ignore[arg-type]
        assert claim.subject_id == subject

    def test_firing_count_incremented_via_trace_path(self) -> None:
        """trace 함수도 실제 firing 함수 — RuleStats 갱신해야 함."""
        engine, definition, cond, out, subject = _setup()
        assert engine.get_rule_stats(definition.id, definition.version).firing_count == 0
        fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        assert engine.get_rule_stats(definition.id, definition.version).firing_count == 1

    def test_condition_trace_children_all_match_for_full_match(self) -> None:
        engine, definition, cond, out, subject = _setup()
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        # SSH_SPEC_DICT 의 condition 은 all + 2 predicates
        assert isinstance(trace.condition_trace, CombinatorTrace)
        for child in trace.condition_trace.children:
            assert child.result is True
            assert child.reason == TRACE_REASON_MATCH


class TestFireRuleWithTraceFalse:
    """condition false → fired=False, claim/gap 0, condition_trace 에 이유."""

    def test_mismatch_returns_fired_false(self) -> None:
        engine, definition, cond, out, subject = _setup()
        ctx = {"port": 80, "banner": "OpenSSH_7.4p1"}
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=ctx,
        )
        assert trace.fired is False
        assert trace.claim_id is None
        assert trace.gap_ids == ()
        assert trace.condition_trace.result is False

    def test_condition_trace_shows_mismatch_reason(self) -> None:
        engine, definition, cond, out, subject = _setup()
        ctx = {"port": 80, "banner": "OpenSSH_7.4p1"}
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=ctx,
        )
        # SSH_SPEC_DICT all 의 첫 predicate (port eq 22) 가 mismatch
        assert isinstance(trace.condition_trace, CombinatorTrace)
        first_child = trace.condition_trace.children[0]
        assert isinstance(first_child, PredicateTrace)
        assert first_child.result is False
        assert first_child.reason == TRACE_REASON_MISMATCH

    def test_missing_field_reason_in_trace(self) -> None:
        engine, definition, cond, out, subject = _setup()
        ctx = {"port": 22}  # banner 누락
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=ctx,
        )
        assert trace.fired is False
        # banner predicate 에서 MISSING_FIELD 가 보여야 함
        children = trace.condition_trace.children  # type: ignore[union-attr]
        banner_predicate = next(
            c for c in children
            if isinstance(c, PredicateTrace) and c.field == "banner"
        )
        assert banner_predicate.reason == TRACE_REASON_MISSING_FIELD
        assert banner_predicate.actual_present is False

    def test_no_claim_or_gap_on_false(self) -> None:
        engine, definition, cond, out, subject = _setup()
        ctx = {"port": 80}
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=ctx,
        )
        assert trace.fired is False
        # claim_id 가 할당되지 않았으므로 engine 에 claim 도 gap 도 없음
        with pytest.raises(KeyError):
            engine.get_claim(1)
        assert engine.get_rule_stats(definition.id, definition.version).firing_count == 0


class TestFireRuleWithTraceGapIds:
    """gap_ids 필드 동작 — required_evidence 가 None / empty / 다수."""

    CTX_MATCH = {"port": 22, "banner": "OpenSSH_7.4p1"}

    def test_no_required_evidence_yields_empty_gap_ids(self) -> None:
        engine, definition, cond, out, subject = _setup()
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=None,
        )
        assert trace.fired is True
        assert trace.gap_ids == ()

    def test_empty_template_yields_empty_gap_ids(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=())
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        assert trace.fired is True
        assert trace.gap_ids == ()

    def test_three_evidence_yields_three_gap_ids(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(1, 2, 3))
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        assert trace.fired is True
        assert len(trace.gap_ids) == 3
        # 각 gap_id 로 engine 에서 조회 가능
        for gap_id, expected_ev_type in zip(trace.gap_ids, (1, 2, 3)):
            gap = engine.get_gap(gap_id)
            assert gap.claim_id == trace.claim_id
            assert gap.type == GAP_TYPE_MISSING_EVIDENCE
            assert gap.required_evidence_type == expected_ev_type
            assert gap.severity == DEFAULT_GAP_SEVERITY


class TestFireRuleWithTraceInvariants:
    """§15 의 5개 불변식 잠금."""

    CTX_MATCH = {"port": 22, "banner": "OpenSSH_7.4p1"}
    CTX_NO_MATCH = {"port": 80}

    def test_fired_iff_claim_id_not_none_when_true(self) -> None:
        engine, definition, cond, out, subject = _setup()
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        assert trace.fired == (trace.claim_id is not None)

    def test_fired_iff_claim_id_not_none_when_false(self) -> None:
        engine, definition, cond, out, subject = _setup()
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_NO_MATCH,
        )
        assert trace.fired == (trace.claim_id is not None)

    def test_false_implies_empty_gap_ids_regardless_of_template(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(1, 2, 3))
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_NO_MATCH,
            required_evidence=template,
        )
        assert trace.fired is False
        assert trace.claim_id is None
        assert trace.gap_ids == ()

    def test_condition_trace_result_equals_fired(self) -> None:
        for ctx in (self.CTX_MATCH, self.CTX_NO_MATCH):
            engine, definition, cond, out, subject = _setup()
            trace = fire_rule_with_trace(
                engine, definition, cond, out,
                subject_id=subject, context=ctx,
            )
            assert trace.condition_trace.result == trace.fired

    def test_gap_count_matches_evidence_types_when_fired(self) -> None:
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(1, 2, 3))
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        assert trace.fired is True
        assert len(trace.gap_ids) == len(template.evidence_types)

    def test_firing_trace_is_frozen(self) -> None:
        engine, definition, cond, out, subject = _setup()
        trace = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
        )
        with pytest.raises(AttributeError):
            trace.fired = False  # type: ignore[misc]


class TestFireRuleWithTraceErrors:
    """미등록 rule 은 KeyError, FiringTrace 미생성 (swallow 금지)."""

    def test_unregistered_rule_raises_keyerror(self) -> None:
        engine = Engine()
        spec = load_rule_spec(SSH_SPEC_DICT)
        definition = compile_rule_definition(spec)  # registered X
        cond = compile_rule_condition(spec)
        out = compile_rule_output(spec)
        subject_id = engine.add_entity(entity_type=1)

        with pytest.raises(KeyError):
            fire_rule_with_trace(
                engine, definition, cond, out,
                subject_id=subject_id,
                context={"port": 22, "banner": "OpenSSH_7.4p1"},
            )

        # fail-fast 보장 — claim 도 안 만들어짐
        with pytest.raises(KeyError):
            engine.get_claim(1)


class TestFireRuleEquivalence:
    """fire_rule 과 fire_rule_with_trace 의 engine 상태 변화 동등성 (§15)."""

    CTX_MATCH = {"port": 22, "banner": "OpenSSH_7.4p1"}
    CTX_NO_MATCH = {"port": 80}

    def _setup_pair(self) -> tuple[tuple[Engine, Any, Any, Any, int], tuple[Engine, Any, Any, Any, int]]:
        """동일한 spec 으로 2개 engine 을 독립적으로 setup."""
        return _setup(), _setup()

    def test_same_state_change_on_fire_true(self) -> None:
        (e_a, def_a, cond_a, out_a, subj_a), (e_b, def_b, cond_b, out_b, subj_b) = (
            self._setup_pair()
        )
        template = RequiredEvidenceTemplate(evidence_types=(1, 2, 3))

        # A: fire_rule, B: fire_rule_with_trace
        claim_id_a = fire_rule(
            e_a, def_a, cond_a, out_a,
            subject_id=subj_a, context=self.CTX_MATCH,
            required_evidence=template,
        )
        trace_b = fire_rule_with_trace(
            e_b, def_b, cond_b, out_b,
            subject_id=subj_b, context=self.CTX_MATCH,
            required_evidence=template,
        )

        # 동일한 claim_id 가 만들어졌어야 함 (각 engine 의 첫 claim 이므로 같은 id=1)
        assert claim_id_a == trace_b.claim_id

        # 동일한 firing_count
        assert e_a.get_rule_stats(1, 1).firing_count == e_b.get_rule_stats(1, 1).firing_count == 1

        # 동일한 gap 개수
        assert len(e_a.gaps_for_claim(claim_id_a)) == len(e_b.gaps_for_claim(trace_b.claim_id))  # type: ignore[arg-type]

    def test_same_state_change_on_fire_false(self) -> None:
        (e_a, def_a, cond_a, out_a, subj_a), (e_b, def_b, cond_b, out_b, subj_b) = (
            self._setup_pair()
        )

        result_a = fire_rule(
            e_a, def_a, cond_a, out_a,
            subject_id=subj_a, context=self.CTX_NO_MATCH,
        )
        trace_b = fire_rule_with_trace(
            e_b, def_b, cond_b, out_b,
            subject_id=subj_b, context=self.CTX_NO_MATCH,
        )

        # 둘 다 발화 안 함
        assert result_a is None
        assert trace_b.fired is False
        assert trace_b.claim_id is None

        # 둘 다 firing_count 0
        assert e_a.get_rule_stats(1, 1).firing_count == 0
        assert e_b.get_rule_stats(1, 1).firing_count == 0


class TestFireRuleWithTraceYamlEndToEnd:
    YAML_TEXT = """
id: RULE_DOMAIN_SSH_001
version: 1
maturity: experimental
reliability:
  prior_confidence: 0.55
condition:
  all:
    - field: port
      op: eq
      value: 22
    - field: banner
      op: contains
      value: "OpenSSH_7."
output:
  claim:
    type: outdated_ssh_candidate
    status: candidate
    base_confidence: 0.55
    reason_code: OPENSSH_7_SERIES_BANNER
    required_evidence:
      - exact_openssh_version
      - os_family
      - package_backport_status
"""

    def test_full_chain_with_trace(self) -> None:
        engine = Engine()
        spec = load_rule_spec_from_yaml(self.YAML_TEXT)
        definition = register_rule_spec(engine, spec)
        condition = compile_rule_condition(spec)
        output = compile_rule_output(spec)
        required = compile_required_evidence(spec)
        subject_id = engine.add_entity(entity_type=1)

        ctx = {"port": 22, "banner": "OpenSSH_7.4p1"}
        trace = fire_rule_with_trace(
            engine, definition, condition, output,
            subject_id=subject_id, context=ctx,
            required_evidence=required,
        )

        assert trace.fired is True
        assert trace.rule_id == 1
        assert trace.rule_version == 1
        assert trace.subject_id == subject_id
        assert trace.claim_id is not None
        assert len(trace.gap_ids) == 3
        # condition_trace 가 평가된 결과까지 보존
        assert trace.condition_trace.result is True
        # 실제 engine 상태도 일치
        assert engine.get_rule_stats(1, 1).firing_count == 1
        assert len(engine.gaps_for_claim(trace.claim_id)) == 3


# =====================================================================
# 28차 — Gap dedup invariants in fire_rule flow (§16)
# =====================================================================

class TestFireRuleDedupInvariants:
    """§16 Gap Dedup MVP 계약을 fire_rule 흐름에서 잠금.

    구현은 27차 ef16e08 에서 완료. 이번 클래스는 의미 회귀 방지용 잠금
    테스트 — engine.add_gap level 의 잠금은 test_engine_relation_gap.py
    의 TestAddGapDedup* 가 담당.
    """

    CTX_MATCH = {"port": 22, "banner": "OpenSSH_7.4p1"}

    def _setup_with_required(
        self,
    ) -> tuple[Engine, Any, Any, Any, int, RequiredEvidenceTemplate]:
        """SSH_001 setup + required_evidence (3개) template 까지."""
        engine, definition, cond, out, subject = _setup()
        template = RequiredEvidenceTemplate(evidence_types=(1, 2, 3))
        return engine, definition, cond, out, subject, template

    def test_fire_twice_same_input_creates_two_claims_but_one_gap_set(
        self,
    ) -> None:
        """같은 rule + 같은 subject 두 번 firing → Claim 2개, 실제 Gap 3개 (중복 X)."""
        engine, definition, cond, out, subject, template = self._setup_with_required()

        claim1 = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        claim2 = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )

        assert claim1 != claim2  # Claim 은 매번 생성
        # engine 의 실제 Gap 총 개수 — set 으로 모아서 보면 3개
        all_gap_ids: set[int] = set()
        for c in (claim1, claim2):
            for gap in engine.gaps_for_claim(c):
                all_gap_ids.add(gap.id)
        assert len(all_gap_ids) == 3  # 6개가 아니라 3개 (dedup)

    def test_fire_twice_returns_same_gap_ids_in_trace(self) -> None:
        """2번째 fire 의 FiringTrace.gap_ids = 1번째 fire 의 gap_ids."""
        engine, definition, cond, out, subject, template = self._setup_with_required()

        trace1 = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        trace2 = fire_rule_with_trace(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )

        assert trace1.gap_ids == trace2.gap_ids

    def test_fire_twice_both_claims_reference_same_gaps(self) -> None:
        """gaps_for_claim(Claim1) ≡ gaps_for_claim(Claim2) (같은 reused gap set)."""
        engine, definition, cond, out, subject, template = self._setup_with_required()

        claim1 = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )
        claim2 = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=template,
        )

        ids1 = {g.id for g in engine.gaps_for_claim(claim1)}
        ids2 = {g.id for g in engine.gaps_for_claim(claim2)}
        assert ids1 == ids2
        assert len(ids1) == 3

    def test_different_rule_version_reuses_gap_per_section_16(self) -> None:
        """§16 — rule_version 은 dedup key 에 포함되지 않음.

        같은 rule_id 의 다른 version 두 개를 모두 등록한 뒤 각각 firing 해도
        (subject, rule_id, gap_type, evidence_type) 가 같으면 gap reuse.
        """
        engine = Engine()
        # 두 버전 등록
        spec_v1_dict = dict(SSH_SPEC_DICT)
        spec_v1_dict["version"] = 1
        spec_v2_dict = dict(SSH_SPEC_DICT)
        spec_v2_dict["version"] = 2

        spec_v1 = load_rule_spec(spec_v1_dict)
        spec_v2 = load_rule_spec(spec_v2_dict)

        def_v1 = register_rule_spec(engine, spec_v1)
        def_v2 = register_rule_spec(engine, spec_v2)

        cond = compile_rule_condition(spec_v1)
        out = compile_rule_output(spec_v1)
        required = compile_required_evidence(spec_v1)
        subject = engine.add_entity(entity_type=1)

        claim_v1 = fire_rule(
            engine, def_v1, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=required,
        )
        claim_v2 = fire_rule(
            engine, def_v2, cond, out,
            subject_id=subject, context=self.CTX_MATCH,
            required_evidence=required,
        )

        # 두 claim 모두 같은 reused gap 참조
        ids_v1 = {g.id for g in engine.gaps_for_claim(claim_v1)}
        ids_v2 = {g.id for g in engine.gaps_for_claim(claim_v2)}
        assert ids_v1 == ids_v2

    def test_firing_count_increments_per_firing_regardless_of_dedup(
        self,
    ) -> None:
        """§16 — dedup 발생해도 firing 마다 firing_count +1."""
        engine, definition, cond, out, subject, template = self._setup_with_required()

        for _ in range(3):
            fire_rule(
                engine, definition, cond, out,
                subject_id=subject, context=self.CTX_MATCH,
                required_evidence=template,
            )

        stats = engine.get_rule_stats(definition.id, definition.version)
        assert stats.firing_count == 3  # dedup 무관 +1 누적

    def test_condition_false_creates_no_claim_no_gap_no_refs(self) -> None:
        """§16 — condition false 면 Claim/Gap/_claim_gap_refs 모두 변화 0."""
        engine, definition, cond, out, subject, template = self._setup_with_required()

        result = fire_rule(
            engine, definition, cond, out,
            subject_id=subject, context={"port": 80},  # mismatch
            required_evidence=template,
        )

        assert result is None
        # claim/gap 미생성 — id=1 도 없음
        with pytest.raises(KeyError):
            engine.get_claim(1)
        with pytest.raises(KeyError):
            engine.gaps_for_claim(1)
        # firing_count 변화 0
        assert engine.get_rule_stats(definition.id, definition.version).firing_count == 0
        # private invariant 직접 검증 — refs 도 비어있어야 함
        assert engine._claim_gap_refs == {}
