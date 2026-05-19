"""Tests for PR11-A — Evidence freshness query (MVP, query only).

Invariants of ``evidence_freshness`` + ``active_contradictions_by_freshness``.

**59차 (test-first) 상태**: 2 query 메서드 미구현. 호출 테스트는
``AttributeError`` 로 fail. 단, Sub-decision B (query only — engine 동작
변경 0) 검증 invariant 들은 **이미 pass** (현재 코드 상태가 정합).

§25.8 의 14 invariant 매핑:
1.  unknown evidence_id → KeyError                            [AttrErr fail]
2.  unknown claim_id → KeyError                                [AttrErr fail]
3.  evidence_freshness(ev) == ev (primitive)                  [AttrErr fail]
4.  나중 등록 → 더 큰 freshness                                [AttrErr fail]
5.  active_contradictions_by_freshness desc order             [AttrErr fail]
6.  same set as active_contradictions_for_claim               [AttrErr fail]
7.  resolved contradiction 제외                                [AttrErr fail]
8.  PR10-A refute_disputed_claim_if_ready 무변화 ★             [이미 pass]
9.  PR11-D compute_effective_confidence 무변화 ★               [이미 pass]
10. PR9-A active_contradictions_for_claim asc 무변화           [이미 pass]
11. query is read-only                                         [AttrErr fail]
12. 빈 active → ()                                             [AttrErr fail]
13. freshness 등록 시점 고정 (시간 무관)                       [AttrErr fail]
14. 기존 534 회귀 없음 — 전체 통과로 입증
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    Engine,
    ScoreValue,
)


def _candidate_claim(engine: Engine, *, base_confidence: float = 0.5) -> tuple[int, int]:
    entity_id = engine.add_entity(entity_type=1)
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=1,
        rule_id=1,
        rule_version=1,
        reason_code=0,
        base_confidence=base_confidence,
    )
    return entity_id, claim_id


def _evidence(
    engine: Engine, claim_id: int, *, evidence_type: int = 42, strength: float = 0.5,
) -> int:
    return engine.add_evidence(
        claim_id=claim_id,
        raw_ref_id=0,
        evidence_type=evidence_type,
        strength=strength,
    )


class TestEvidenceFreshness:
    """§25.8 invariants 1, 3, 4, 13 — primitive freshness query."""

    # invariant 1
    def test_unknown_evidence_id_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.evidence_freshness(999)

    # invariant 3
    def test_freshness_equals_evidence_id(self) -> None:
        """Sub-decision A — freshness = evidence.id (primitive)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        assert engine.evidence_freshness(ev) == ev

    # invariant 4
    def test_later_evidence_has_higher_freshness(self) -> None:
        """더 최근 등록된 evidence 가 더 큰 freshness 를 가진다."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_first = _evidence(engine, claim_id)
        ev_second = _evidence(engine, claim_id)
        ev_third = _evidence(engine, claim_id)
        assert (
            engine.evidence_freshness(ev_first)
            < engine.evidence_freshness(ev_second)
            < engine.evidence_freshness(ev_third)
        )

    # invariant 13
    def test_freshness_is_fixed_at_registration(self) -> None:
        """등록 후 다른 작업이 일어나도 freshness 는 고정 (시간 무관)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev = _evidence(engine, claim_id)
        snapshot = engine.evidence_freshness(ev)

        # 다른 evidence 등록, contradiction 등록, lifecycle transition 일으켜도
        # 기존 ev 의 freshness 는 그대로
        ev2 = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev2)
        engine.add_gap(
            claim_id=claim_id, gap_type=1, required_evidence_type=42,
            severity=0.5, rule_id=1,
        )

        assert engine.evidence_freshness(ev) == snapshot


class TestActiveContradictionsByFreshness:
    """§25.8 invariants 2, 5, 6, 7, 12 — active 차집합 + desc 정렬."""

    # invariant 2
    def test_unknown_claim_id_raises_key_error(self) -> None:
        engine = Engine()
        with pytest.raises(KeyError):
            engine.active_contradictions_by_freshness(999)

    # invariant 5
    def test_desc_order_by_freshness(self) -> None:
        """가장 최근 (큰 evidence.id) 먼저."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_a = _evidence(engine, claim_id)
        ev_b = _evidence(engine, claim_id)
        ev_c = _evidence(engine, claim_id)
        # 의도적으로 등록 순서와 다른 순서로 contradiction 등록
        engine.register_contradiction(claim_id, ev_b)
        engine.register_contradiction(claim_id, ev_a)
        engine.register_contradiction(claim_id, ev_c)

        result = engine.active_contradictions_by_freshness(claim_id)

        # desc — ev_c (id=3), ev_b (id=2), ev_a (id=1)
        assert result == (ev_c, ev_b, ev_a)
        assert list(result) == sorted(result, reverse=True)

    # invariant 6
    def test_same_set_as_active_contradictions_for_claim(self) -> None:
        """PR9-A 와 같은 set, 정렬 키만 다름."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_a = _evidence(engine, claim_id)
        ev_b = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev_a)
        engine.register_contradiction(claim_id, ev_b)

        asc = engine.active_contradictions_for_claim(claim_id)
        desc = engine.active_contradictions_by_freshness(claim_id)

        assert set(asc) == set(desc)
        # asc 와 desc 는 서로 reverse 관계
        assert list(asc) == list(reversed(desc))

    # invariant 7 — resolved 제외 (PR9-A 차집합 정합)
    def test_resolved_contradiction_excluded(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_a = _evidence(engine, claim_id)
        ev_b = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev_a)
        engine.register_contradiction(claim_id, ev_b)
        engine.register_contradiction_resolution(claim_id, ev_b)  # ev_b resolved

        result = engine.active_contradictions_by_freshness(claim_id)

        # ev_b 빠짐, ev_a 만 남음
        assert result == (ev_a,)

    # invariant 12
    def test_empty_active_returns_empty_tuple(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        # contradiction 등록 0 → 빈 tuple
        assert engine.active_contradictions_by_freshness(claim_id) == ()


class TestQueriesAreReadOnly:
    """§25.8 invariant 11 — query 가 state 무변화."""

    def test_queries_do_not_mutate_engine_state(self) -> None:
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_a = _evidence(engine, claim_id)
        ev_b = _evidence(engine, claim_id)
        engine.register_contradiction(claim_id, ev_a)
        engine.register_contradiction(claim_id, ev_b)
        engine.register_contradiction_resolution(claim_id, ev_b)

        before_contras = engine.contradictions_for_claim(claim_id)
        before_resolved = engine.resolved_contradictions_for_claim(claim_id)
        before_active = engine.active_contradictions_for_claim(claim_id)
        before_status = engine.get_claim(claim_id).status
        before_history = engine.claim_lifecycle_history(claim_id)

        # 여러 번 query
        engine.evidence_freshness(ev_a)
        engine.evidence_freshness(ev_b)
        engine.active_contradictions_by_freshness(claim_id)
        engine.active_contradictions_by_freshness(claim_id)

        assert engine.contradictions_for_claim(claim_id) == before_contras
        assert engine.resolved_contradictions_for_claim(claim_id) == before_resolved
        assert engine.active_contradictions_for_claim(claim_id) == before_active
        assert engine.get_claim(claim_id).status == before_status
        assert engine.claim_lifecycle_history(claim_id) == before_history


class TestPriorPolicyUnchanged:
    """§25.8 invariants 8, 9, 10 — Sub-decision B: 기존 정책 무변화 (이미 pass)."""

    # invariant 8 ★ — PR10-A refute_disputed_claim_if_ready 무변화
    def test_pr10a_refute_disputed_unchanged(self) -> None:
        """PR10-A: active 중 strength >= 0.8 → refuted (freshness 무관)."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        # 두 evidence: 첫째 strong (0.9), 둘째 weak (0.3)
        ev_strong = _evidence(engine, claim_id, strength=0.9)
        ev_weak = _evidence(engine, claim_id, strength=0.3)
        engine.register_contradiction(claim_id, ev_strong)
        engine.register_contradiction(claim_id, ev_weak)
        # disputed 로 setup
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_CONFIRMED,
        )
        engine.dispute_claim_if_ready(claim_id)

        # PR10-A: ev_strong 이 0.9 >= 0.8 이므로 refute True
        # PR11-A 의 freshness desc 정렬 (ev_weak first) 은 영향 없어야 함
        result = engine.refute_disputed_claim_if_ready(claim_id)
        assert result is True
        assert engine.get_claim(claim_id).status == CLAIM_STATUS_REFUTED

    # invariant 9 ★ — PR11-D compute_effective_confidence 무변화
    def test_pr11d_compute_effective_confidence_unchanged(self) -> None:
        """PR11-D: effective = base × status_modifier. freshness 가 들어가면 안 됨."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine, base_confidence=0.8)
        # 여러 evidence 등록 (freshness 다양화 — 영향 없어야 함)
        for _ in range(5):
            _evidence(engine, claim_id)

        # candidate → 1.0
        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(0.8)

        # disputed → 0.5
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_DISPUTED,
        )
        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(0.4)

        # refuted → 0.0
        engine._claims[claim_id] = replace(
            engine._claims[claim_id], status=CLAIM_STATUS_REFUTED,
        )
        assert engine.compute_effective_confidence(claim_id).value == pytest.approx(0.0)

    # invariant 10 — PR9-A active_contradictions_for_claim asc 무변화
    def test_pr9a_active_contradictions_asc_unchanged(self) -> None:
        """PR9-A: active_contradictions_for_claim 는 여전히 evidence_id asc."""
        engine = Engine()
        _, claim_id = _candidate_claim(engine)
        ev_a = _evidence(engine, claim_id)
        ev_b = _evidence(engine, claim_id)
        ev_c = _evidence(engine, claim_id)
        # 의도적으로 desc 순서로 등록
        engine.register_contradiction(claim_id, ev_c)
        engine.register_contradiction(claim_id, ev_b)
        engine.register_contradiction(claim_id, ev_a)

        # PR9-A asc — 작은 id 부터
        result = engine.active_contradictions_for_claim(claim_id)
        assert result == (ev_a, ev_b, ev_c)
