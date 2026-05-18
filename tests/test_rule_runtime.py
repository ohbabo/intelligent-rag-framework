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
    ScoreValue,
    compile_rule_condition,
    compile_rule_definition,
    compile_rule_output,
    load_rule_spec,
    load_rule_spec_from_yaml,
    register_rule_spec,
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
