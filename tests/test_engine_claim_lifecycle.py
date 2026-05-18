"""Tests for PR6 — Claim lifecycle (MVP).

Invariants of ``Engine.confirm_claim_if_ready(claim_id) -> bool``.

**31차 (test-first) 상태**:
이 메서드는 아직 구현되지 않았다. 따라서 ``confirm_claim_if_ready`` 를 호출하는
모든 테스트는 ``AttributeError`` 로 fail 한다. **그게 정상.** 32차에서 메서드를
구현하면 전부 통과로 전환된다.

§18.7 의 10 개 invariant 매핑:
1. candidate + gap 0 개 → False, candidate 유지
2. candidate + 모든 gap resolved → True, confirmed
3. candidate + 일부 gap unresolved → False, candidate 유지
4. confirmed 재호출 → False, confirmed 유지 (idempotent)
5. refuted → False, refuted 유지 (복구 금지)
6. 두 번째 호출 idempotent (전이 후 재호출 = no-op)
7. unknown claim_id → KeyError
8. confirm 발생해도 gap state 무변화
9. confirm 발생해도 base_confidence 무변화
10. 기존 425 tests 회귀 없음 (전체 통과로 입증)
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_REFUTED,
    Engine,
)


def _candidate_claim(engine: Engine) -> tuple[int, int]:
    """entity + candidate claim helper. PR5 테스트와 동일 패턴."""
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=1,
        rule_version=1,
        reason_code=0,
    )
    return entity_id, claim_id


class TestConfirmClaimIfReady:
    """§18.7 invariants 1~9. invariant 10 은 전체 회귀로 입증."""

    # ---- Invariant 1: candidate + gap 0 개 ---------------------------------

    def test_candidate_with_zero_gaps_returns_false_and_keeps_status(self) -> None:
        """Gap 이 0 개인 candidate Claim 은 자동 confirm 금지 (§18.4).

        "검증 끝" 이 아니라 "확인 근거 없음" 으로 해석.
        """
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CANDIDATE
        assert engine.gaps_for_claim(claim_id) == []

        result = engine.confirm_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CANDIDATE

    # ---- Invariant 2: candidate + 모든 gap resolved ------------------------

    def test_candidate_with_all_gaps_resolved_promotes_to_confirmed(self) -> None:
        """모든 referenced gap 이 resolved 인 candidate Claim 은 confirmed 로 전이."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        # 다른 rule_id 로 2 개 gap (PR4 dedup 회피), 같은 required_evidence_type
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=2,
        )
        ev = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0, evidence_type=42, strength=0.8,
        )
        resolved = engine.resolve_gaps_for_evidence(ev)
        assert len(resolved) == 2  # 두 gap 모두 resolved

        result = engine.confirm_claim_if_ready(claim_id)

        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    # ---- Invariant 3: candidate + 일부 unresolved --------------------------

    def test_candidate_with_partial_resolution_returns_false(self) -> None:
        """matching gap 만 resolved 되고 다른 type gap 이 unresolved 면 confirm 안 됨."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=99,
            severity=0.5, rule_id=1,
        )
        ev = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0, evidence_type=42, strength=0.8,
        )
        resolved = engine.resolve_gaps_for_evidence(ev)
        assert len(resolved) == 1  # type=42 gap 만 닫힘, type=99 gap 은 unresolved

        result = engine.confirm_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CANDIDATE

    def test_candidate_with_no_evidence_returns_false(self) -> None:
        """Gap 만 있고 evidence 가 전혀 없으면 confirm 안 됨 (모든 gap unresolved)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )

        result = engine.confirm_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CANDIDATE

    # ---- Invariant 4 + 6: confirmed 재호출 idempotent ----------------------

    def test_confirmed_reinvocation_is_noop(self) -> None:
        """이미 confirmed 인 Claim 재호출은 False + 상태 유지 (§18.5)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        # 외부에서 직접 confirmed 상태로 만든다 (white-box — PR6 에는 다른 confirm 경로 없음)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )

        result = engine.confirm_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    def test_second_call_after_promotion_is_idempotent(self) -> None:
        """첫 호출 True, 두 번째 호출 False, 상태 confirmed 유지."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0, evidence_type=42, strength=0.8,
        )
        engine.resolve_gaps_for_evidence(ev)

        first = engine.confirm_claim_if_ready(claim_id)
        second = engine.confirm_claim_if_ready(claim_id)

        assert first is True
        assert second is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_CONFIRMED

    # ---- Invariant 5: refuted 복구 금지 ------------------------------------

    def test_refuted_claim_is_not_revived(self) -> None:
        """refuted 상태 Claim 에 confirm 호출해도 변화 없음 (PR6 범위: 복구 금지)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        # gap 다 resolved 시나리오 — 그래도 refuted 면 confirm 안 됨
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0, evidence_type=42, strength=0.8,
        )
        engine.resolve_gaps_for_evidence(ev)
        # 외부에서 직접 refuted 로 (white-box)
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )

        result = engine.confirm_claim_if_ready(claim_id)

        assert result is False
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # ---- Invariant 7: unknown claim_id → KeyError --------------------------

    def test_unknown_claim_id_raises_key_error(self) -> None:
        """fail-fast: 존재하지 않는 claim_id 는 KeyError (PR1~PR5 패턴과 일관)."""
        engine = Engine()
        with pytest.raises(KeyError):
            engine.confirm_claim_if_ready(999)

    # ---- Invariant 8: confirm 호출이 gap state 무변화 ----------------------

    def test_confirm_does_not_mutate_gap_state(self) -> None:
        """confirm 전이가 발생해도 _gap_resolutions / gap fields 변경 없음."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        gap_id = engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0, evidence_type=42, strength=0.8,
        )
        engine.resolve_gaps_for_evidence(ev)

        before_resolutions = dict(engine._gap_resolutions)
        before_gap = engine.get_gap(gap_id)
        before_gaps_for_claim = engine.gaps_for_claim(claim_id)

        engine.confirm_claim_if_ready(claim_id)

        assert engine._gap_resolutions == before_resolutions
        assert engine.get_gap(gap_id) == before_gap
        assert engine.gaps_for_claim(claim_id) == before_gaps_for_claim
        assert engine.gap_resolution(gap_id) == ev  # 여전히 resolved

    # ---- Invariant 9: confirm 호출이 base_confidence 무변화 ----------------

    def test_confirm_does_not_change_base_confidence(self) -> None:
        """scoring 변경 금지 (§18.6) — base_confidence 보존."""
        engine = Engine()
        entity_id = engine.add_entity(entity_type=1)
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=1,
            rule_id=1,
            rule_version=1,
            reason_code=0,
            base_confidence=0.42,  # add_claim 가 내부에서 ScoreValue 로 감싼다
        )
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )
        ev = engine.add_evidence(
            claim_id=claim_id, raw_ref_id=0, evidence_type=42, strength=0.8,
        )
        engine.resolve_gaps_for_evidence(ev)
        before_base = engine.get_claim(claim_id).base_confidence

        engine.confirm_claim_if_ready(claim_id)

        after_base = engine.get_claim(claim_id).base_confidence
        assert after_base == before_base
        assert float(after_base) == pytest.approx(0.42)
