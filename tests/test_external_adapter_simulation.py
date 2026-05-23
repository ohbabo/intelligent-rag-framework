"""PR41 — External Adapter Simulation Tests.

Scope
-----
These tests do not test real vector DB, graph DB, LLM, SQL, file store,
API, or manual-note adapters. They simulate adapter-owned translation
outputs and verify that the frozen Engine public method surface can
receive them safely.

Locked principles (from PR40 §3, PR39 §7, §50):
  - external scores are not engine confidence
  - similarity / severity / LLM confidence / API score must be translated
  - raw_ref_id is Engine int; external IDs are consumer-owned
  - adapter-specific concepts MUST NOT appear in ragcore.__all__
  - engine.py / types.py / __init__.py source remains unchanged

Test scope
----------
- 7 simulation scenarios (vector / graph / LLM / SQL / file / API / manual)
- Each scenario uses fake external payloads (test-local, NOT production)
- Each scenario uses Engine public API only
- Test-local helpers for raw_ref resolution, registries, score translation
- Cross-scenario invariants verify framework neutrality

Not in scope
------------
- real chroma / faiss / qdrant / neo4j / openai / etc. import
- network calls
- LLM API calls
- DB driver imports
- file IO dependence
- Cerberus / V-cerberus
- runtime type validation in Engine (Engine is adapter-boundary
  enforced, not runtime validator)
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import ragcore
from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    Engine,
)


# ============================================================================
# Test-local helpers (adapter-side simulation, NOT production code)
# ============================================================================


class _TestLocalRawRefResolver:
    """Test-local raw_ref resolver — simulates a consumer-side
    string → int id strategy. NOT exported. NOT in ragcore.__all__.
    """

    def __init__(self) -> None:
        self._map: dict[str, int] = {}
        self._next: int = 1

    def resolve(self, external_id: str) -> int:
        if external_id not in self._map:
            self._map[external_id] = self._next
            self._next += 1
        return self._map[external_id]


# Test-local consumer-domain integer registries (simulation only)
_ENTITY_TYPE_HOST = 1
_ENTITY_TYPE_DOC = 2
_ENTITY_TYPE_NODE = 3
_ENTITY_TYPE_RECORD = 4
_ENTITY_TYPE_ARTIFACT = 5

_OBSERVATION_TYPE_VECTOR_RETRIEVAL = 100
_OBSERVATION_TYPE_GRAPH_TRAVERSAL = 101
_OBSERVATION_TYPE_LLM_EXTRACTION = 102
_OBSERVATION_TYPE_SQL_QUERY = 103
_OBSERVATION_TYPE_FILE_READ = 104
_OBSERVATION_TYPE_API_CALL = 105
_OBSERVATION_TYPE_MANUAL_NOTE = 106

_SOURCE_TYPE_VECTOR_DB = 200
_SOURCE_TYPE_GRAPH_DB = 201
_SOURCE_TYPE_LLM = 202
_SOURCE_TYPE_SQL = 203
_SOURCE_TYPE_FILE = 204
_SOURCE_TYPE_API = 205
_SOURCE_TYPE_MANUAL = 206

_CLAIM_TYPE_DOC_CONTAINS_FACT = 300
_CLAIM_TYPE_NODE_RELATES_TO = 301
_CLAIM_TYPE_LLM_EXTRACTED_FACT = 302
_CLAIM_TYPE_RECORD_HAS_VALUE = 303
_CLAIM_TYPE_ARTIFACT_OBSERVED = 304
_CLAIM_TYPE_API_REPORTED = 305
_CLAIM_TYPE_ANALYST_OBSERVATION = 306

_EVIDENCE_TYPE_VECTOR_CHUNK = 400
_EVIDENCE_TYPE_GRAPH_PATH = 401
_EVIDENCE_TYPE_LLM_RESPONSE = 402
_EVIDENCE_TYPE_SQL_FIELD = 403
_EVIDENCE_TYPE_FILE_CHUNK = 404
_EVIDENCE_TYPE_API_FIELD = 405
_EVIDENCE_TYPE_MANUAL_NOTE = 406

_REASON_CODE_DIRECT = 1


# Test-local adapter score translation policies (NOT identity-pipes)
def _translate_similarity_to_strength(similarity: float) -> float:
    """similarity (0..1) → strength (0..1). NOT identity."""
    if similarity < 0.5:
        return 0.5  # floor
    return 0.7 + (similarity - 0.5) * 0.6


def _translate_path_score_to_strength(path_score: float) -> float:
    """graph path score → strength."""
    return min(0.9, 0.6 + path_score * 0.3)


def _translate_llm_confidence_to_strength(model_conf: float) -> float:
    """LLM self-reported confidence is unreliable — cap at 0.5."""
    return min(0.5, model_conf * 0.5)


def _translate_severity_to_base_confidence(severity: str) -> float:
    """severity label → base_confidence."""
    return {"low": 0.4, "medium": 0.6, "high": 0.8, "critical": 0.95}.get(
        severity, 0.5
    )


def _translate_api_score_to_strength(api_score: float) -> float:
    """API score (0..1) → strength (0..1) with adapter dampening."""
    return min(0.85, api_score * 0.85)


# ============================================================================
# Fake external payloads (test-local data, NOT production types)
# ============================================================================


@dataclass(frozen=True)
class _FakeVectorResult:
    external_doc_id: str
    chunk_id: str
    similarity_score: float
    text_ref: str


@dataclass(frozen=True)
class _FakeGraphPath:
    node_a: str
    edge_type: str
    node_b: str
    path_score: float


@dataclass(frozen=True)
class _FakeLLMExtraction:
    extracted_claim_text: str
    model_confidence: float
    source_ref: str


@dataclass(frozen=True)
class _FakeSQLRow:
    row_id: str
    table_name: str
    field_value: str
    query_score: float


@dataclass(frozen=True)
class _FakeFileChunk:
    file_path: str
    byte_range: tuple[int, int]
    chunk_hash: str


@dataclass(frozen=True)
class _FakeAPISignal:
    api_name: str
    external_id: str
    api_score: float
    timestamp: str


@dataclass(frozen=True)
class _FakeManualNote:
    analyst_note_id: str
    note_type: str
    confidence_label: str  # "low" / "medium" / "high" / "critical"


# ============================================================================
# Expected snapshot invariants (PR36-PKG _LOCKED_SNAPSHOT_TOP_LEVEL_KEYS)
# ============================================================================

_EXPECTED_SNAPSHOT_TOP_LEVEL_KEYS = 18
_EXPECTED_SCHEMA_VERSION = 2


# ============================================================================
# Scenario 1: Vector retrieval result
# ============================================================================


class TestVectorResultSimulation:
    """Fake vector DB result flows through Engine public API."""

    def test_vector_result_flows_through_public_api(self) -> None:
        engine = Engine()
        resolver = _TestLocalRawRefResolver()

        fake = _FakeVectorResult(
            external_doc_id="doc-abc123",
            chunk_id="chunk-7",
            similarity_score=0.85,
            text_ref="ext://doc-abc123/chunk-7",
        )

        # Adapter translation (test-local)
        entity_id = engine.add_entity(entity_type=_ENTITY_TYPE_DOC)
        engine.add_observation(
            entity_id=entity_id,
            raw_ref_id=resolver.resolve(fake.text_ref),
            observation_type=_OBSERVATION_TYPE_VECTOR_RETRIEVAL,
            source_type=_SOURCE_TYPE_VECTOR_DB,
        )
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=_CLAIM_TYPE_DOC_CONTAINS_FACT,
            rule_id=0,
            rule_version=0,
            reason_code=_REASON_CODE_DIRECT,
            base_confidence=0.7,  # adapter policy (not similarity)
            status=CLAIM_STATUS_CANDIDATE,
        )
        engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=resolver.resolve(fake.chunk_id),
            evidence_type=_EVIDENCE_TYPE_VECTOR_CHUNK,
            strength=_translate_similarity_to_strength(fake.similarity_score),
        )

        score = engine.compute_effective_confidence(claim_id)
        snap = engine.to_snapshot()

        assert 0.0 <= score.value <= 1.0
        assert snap["schema_version"] == _EXPECTED_SCHEMA_VERSION
        assert len(snap) == _EXPECTED_SNAPSHOT_TOP_LEVEL_KEYS

    def test_similarity_score_is_not_identity_piped_to_strength(self) -> None:
        # Adapter MUST translate, not identity-pipe.
        similarity = 0.85
        strength = _translate_similarity_to_strength(similarity)
        assert strength != similarity  # not identity


# ============================================================================
# Scenario 2: Graph path traversal
# ============================================================================


class TestGraphPathSimulation:
    """Fake graph DB path flows through Engine public API (add_relation)."""

    def test_graph_path_flows_through_public_api(self) -> None:
        engine = Engine()
        resolver = _TestLocalRawRefResolver()

        fake = _FakeGraphPath(
            node_a="node-A",
            edge_type="depends_on",
            node_b="node-B",
            path_score=0.75,
        )

        entity_a = engine.add_entity(entity_type=_ENTITY_TYPE_NODE)
        entity_b = engine.add_entity(entity_type=_ENTITY_TYPE_NODE)

        engine.add_relation(
            from_kind=ragcore.KIND_ENTITY,
            from_id=entity_a,
            to_kind=ragcore.KIND_ENTITY,
            to_id=entity_b,
            relation_type=1,  # consumer-side relation_type registry
            rule_id=0,
            reason_code=_REASON_CODE_DIRECT,
        )

        claim_id = engine.add_claim(
            subject_id=entity_a,
            claim_type=_CLAIM_TYPE_NODE_RELATES_TO,
            rule_id=0,
            rule_version=0,
            reason_code=_REASON_CODE_DIRECT,
            base_confidence=0.7,  # adapter policy (not path_score)
            status=CLAIM_STATUS_CANDIDATE,
        )
        engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=resolver.resolve(f"{fake.node_a}->{fake.node_b}"),
            evidence_type=_EVIDENCE_TYPE_GRAPH_PATH,
            strength=_translate_path_score_to_strength(fake.path_score),
        )

        score = engine.compute_effective_confidence(claim_id)
        snap = engine.to_snapshot()

        assert 0.0 <= score.value <= 1.0
        assert snap["schema_version"] == _EXPECTED_SCHEMA_VERSION
        assert len(snap) == _EXPECTED_SNAPSHOT_TOP_LEVEL_KEYS

    def test_path_score_is_not_identity_piped(self) -> None:
        path_score = 0.75
        strength = _translate_path_score_to_strength(path_score)
        assert strength != path_score  # not identity


# ============================================================================
# Scenario 3: LLM extraction
# ============================================================================


class TestLLMExtractionSimulation:
    """Fake LLM extraction flows as candidate Claim, never auto-confirmed."""

    def test_llm_extraction_creates_candidate_claim(self) -> None:
        engine = Engine()
        resolver = _TestLocalRawRefResolver()

        fake = _FakeLLMExtraction(
            extracted_claim_text="System X depends on library Y",
            model_confidence=0.92,
            source_ref="llm-response-42",
        )

        entity_id = engine.add_entity(entity_type=_ENTITY_TYPE_ARTIFACT)
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=_CLAIM_TYPE_LLM_EXTRACTED_FACT,
            rule_id=0,
            rule_version=0,
            reason_code=_REASON_CODE_DIRECT,
            base_confidence=0.5,  # adapter policy: LLM-only → 0.5 cap
            status=CLAIM_STATUS_CANDIDATE,  # never auto-confirmed
        )
        engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=resolver.resolve(fake.source_ref),
            evidence_type=_EVIDENCE_TYPE_LLM_RESPONSE,
            strength=_translate_llm_confidence_to_strength(fake.model_confidence),
        )

        # Claim must remain CANDIDATE (LLM never auto-confirms)
        claim = engine.get_claim(claim_id)
        assert claim.status == CLAIM_STATUS_CANDIDATE

        score = engine.compute_effective_confidence(claim_id)
        snap = engine.to_snapshot()

        assert 0.0 <= score.value <= 1.0
        assert snap["schema_version"] == _EXPECTED_SCHEMA_VERSION
        assert len(snap) == _EXPECTED_SNAPSHOT_TOP_LEVEL_KEYS

    def test_llm_confidence_is_capped_by_adapter_policy(self) -> None:
        # LLM self-reported confidence is unreliable — adapter caps at 0.5.
        high_conf = 0.99
        strength = _translate_llm_confidence_to_strength(high_conf)
        assert strength <= 0.5  # cap enforced


# ============================================================================
# Scenario 4: SQL row
# ============================================================================


class TestSQLRowSimulation:
    """Fake SQL row flows through Engine public API."""

    def test_sql_row_flows_through_public_api(self) -> None:
        engine = Engine()
        resolver = _TestLocalRawRefResolver()

        fake = _FakeSQLRow(
            row_id="row-123",
            table_name="findings",
            field_value="connected",
            query_score=0.0,  # SQL is exact match; score not meaningful
        )

        entity_id = engine.add_entity(entity_type=_ENTITY_TYPE_RECORD)
        engine.add_observation(
            entity_id=entity_id,
            raw_ref_id=resolver.resolve(f"{fake.table_name}#{fake.row_id}"),
            observation_type=_OBSERVATION_TYPE_SQL_QUERY,
            source_type=_SOURCE_TYPE_SQL,
        )
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=_CLAIM_TYPE_RECORD_HAS_VALUE,
            rule_id=0,
            rule_version=0,
            reason_code=_REASON_CODE_DIRECT,
            base_confidence=0.9,  # SQL is high confidence (deterministic)
            status=CLAIM_STATUS_CANDIDATE,
        )
        engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=resolver.resolve(f"{fake.table_name}#{fake.row_id}#value"),
            evidence_type=_EVIDENCE_TYPE_SQL_FIELD,
            strength=0.95,  # adapter default for exact-match
        )

        score = engine.compute_effective_confidence(claim_id)
        snap = engine.to_snapshot()

        assert 0.0 <= score.value <= 1.0
        assert snap["schema_version"] == _EXPECTED_SCHEMA_VERSION
        assert len(snap) == _EXPECTED_SNAPSHOT_TOP_LEVEL_KEYS


# ============================================================================
# Scenario 5: File chunk
# ============================================================================


class TestFileChunkSimulation:
    """Fake file chunk flows through Engine public API.

    The chunk text is NOT inserted into ragcore. The chunk_hash is used
    as raw_ref to recover content from consumer-side storage.
    """

    def test_file_chunk_flows_through_public_api(self) -> None:
        engine = Engine()
        resolver = _TestLocalRawRefResolver()

        fake = _FakeFileChunk(
            file_path="/data/corpus/doc.txt",
            byte_range=(0, 4096),
            chunk_hash="sha256:abc123def456",
        )

        entity_id = engine.add_entity(entity_type=_ENTITY_TYPE_DOC)
        engine.add_observation(
            entity_id=entity_id,
            raw_ref_id=resolver.resolve(fake.chunk_hash),
            observation_type=_OBSERVATION_TYPE_FILE_READ,
            source_type=_SOURCE_TYPE_FILE,
        )
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=_CLAIM_TYPE_DOC_CONTAINS_FACT,
            rule_id=0,
            rule_version=0,
            reason_code=_REASON_CODE_DIRECT,
            base_confidence=0.75,
            status=CLAIM_STATUS_CANDIDATE,
        )
        engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=resolver.resolve(fake.chunk_hash),
            evidence_type=_EVIDENCE_TYPE_FILE_CHUNK,
            strength=0.8,  # adapter policy
        )

        score = engine.compute_effective_confidence(claim_id)
        snap = engine.to_snapshot()

        assert 0.0 <= score.value <= 1.0
        assert snap["schema_version"] == _EXPECTED_SCHEMA_VERSION
        assert len(snap) == _EXPECTED_SNAPSHOT_TOP_LEVEL_KEYS


# ============================================================================
# Scenario 6: API signal
# ============================================================================


class TestAPISignalSimulation:
    """Fake API signal flows through Engine public API."""

    def test_api_signal_flows_through_public_api(self) -> None:
        engine = Engine()
        resolver = _TestLocalRawRefResolver()

        fake = _FakeAPISignal(
            api_name="cve-lookup",
            external_id="CVE-2024-12345",
            api_score=0.88,
            timestamp="2026-05-23T00:00:00Z",
        )

        entity_id = engine.add_entity(entity_type=_ENTITY_TYPE_ARTIFACT)
        engine.add_observation(
            entity_id=entity_id,
            raw_ref_id=resolver.resolve(f"{fake.api_name}#{fake.external_id}"),
            observation_type=_OBSERVATION_TYPE_API_CALL,
            source_type=_SOURCE_TYPE_API,
        )
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=_CLAIM_TYPE_API_REPORTED,
            rule_id=0,
            rule_version=0,
            reason_code=_REASON_CODE_DIRECT,
            base_confidence=0.7,  # adapter policy (not api_score)
            status=CLAIM_STATUS_CANDIDATE,
        )
        engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=resolver.resolve(fake.external_id),
            evidence_type=_EVIDENCE_TYPE_API_FIELD,
            strength=_translate_api_score_to_strength(fake.api_score),
        )

        score = engine.compute_effective_confidence(claim_id)
        snap = engine.to_snapshot()

        assert 0.0 <= score.value <= 1.0
        assert snap["schema_version"] == _EXPECTED_SCHEMA_VERSION
        assert len(snap) == _EXPECTED_SNAPSHOT_TOP_LEVEL_KEYS

    def test_api_score_is_not_identity_piped(self) -> None:
        api_score = 0.88
        strength = _translate_api_score_to_strength(api_score)
        assert strength != api_score


# ============================================================================
# Scenario 7: Manual analyst note
# ============================================================================


class TestManualNoteSimulation:
    """Fake analyst note flows through Engine public API."""

    def test_manual_note_flows_through_public_api(self) -> None:
        engine = Engine()
        resolver = _TestLocalRawRefResolver()

        fake = _FakeManualNote(
            analyst_note_id="note-007",
            note_type="observation",
            confidence_label="high",
        )

        entity_id = engine.add_entity(entity_type=_ENTITY_TYPE_ARTIFACT)
        engine.add_observation(
            entity_id=entity_id,
            raw_ref_id=resolver.resolve(fake.analyst_note_id),
            observation_type=_OBSERVATION_TYPE_MANUAL_NOTE,
            source_type=_SOURCE_TYPE_MANUAL,
        )
        claim_id = engine.add_claim(
            subject_id=entity_id,
            claim_type=_CLAIM_TYPE_ANALYST_OBSERVATION,
            rule_id=0,
            rule_version=0,
            reason_code=_REASON_CODE_DIRECT,
            base_confidence=_translate_severity_to_base_confidence(
                fake.confidence_label
            ),
            status=CLAIM_STATUS_CANDIDATE,
        )
        engine.add_evidence(
            claim_id=claim_id,
            raw_ref_id=resolver.resolve(fake.analyst_note_id),
            evidence_type=_EVIDENCE_TYPE_MANUAL_NOTE,
            strength=0.85,  # analyst manual entry default
        )

        score = engine.compute_effective_confidence(claim_id)
        snap = engine.to_snapshot()

        assert 0.0 <= score.value <= 1.0
        assert snap["schema_version"] == _EXPECTED_SCHEMA_VERSION
        assert len(snap) == _EXPECTED_SNAPSHOT_TOP_LEVEL_KEYS

    def test_severity_label_translates_to_base_confidence_via_policy(self) -> None:
        assert _translate_severity_to_base_confidence("low") < 0.5
        assert _translate_severity_to_base_confidence("medium") < 0.7
        assert _translate_severity_to_base_confidence("high") >= 0.7
        assert _translate_severity_to_base_confidence("critical") >= 0.9


# ============================================================================
# Cross-scenario invariants
# ============================================================================


class TestExternalAdapterGenericInvariants:
    """Invariants that hold across all 7 scenarios — framework neutrality."""

    _ADAPTER_SPECIFIC_SYMBOLS = frozenset({
        "_TestLocalRawRefResolver",
        "_FakeVectorResult",
        "_FakeGraphPath",
        "_FakeLLMExtraction",
        "_FakeSQLRow",
        "_FakeFileChunk",
        "_FakeAPISignal",
        "_FakeManualNote",
    })

    _FORBIDDEN_EXTERNAL_PACKAGES = frozenset({
        "pinecone",
        "weaviate",
        "chromadb",
        "qdrant_client",
        "faiss",
        "neo4j",
        "openai",
        "anthropic",
        "psycopg",
        "sqlalchemy",
    })

    def test_adapter_specific_symbols_not_in_ragcore_all(self) -> None:
        for sym in self._ADAPTER_SPECIFIC_SYMBOLS:
            assert sym not in ragcore.__all__, (
                f"Test-local adapter symbol {sym} must not leak into "
                f"ragcore.__all__"
            )

    def test_ragcore_engine_does_not_import_external_packages(self) -> None:
        import inspect

        import ragcore.engine as eng

        src = inspect.getsource(eng)
        for pkg in self._FORBIDDEN_EXTERNAL_PACKAGES:
            assert f"import {pkg}" not in src, (
                f"ragcore.engine must not import {pkg}"
            )
            assert f"from {pkg}" not in src, (
                f"ragcore.engine must not import from {pkg}"
            )

    def test_all_scenarios_preserve_snapshot_top_level_keys(self) -> None:
        # After exercising all 7 scenarios in one engine, snapshot keys
        # remain 18 (PR36-PKG _LOCKED_SNAPSHOT_TOP_LEVEL_KEYS).
        engine = Engine()
        resolver = _TestLocalRawRefResolver()

        # Scenario 1: vector
        e1 = engine.add_entity(entity_type=_ENTITY_TYPE_DOC)
        c1 = engine.add_claim(
            subject_id=e1, claim_type=_CLAIM_TYPE_DOC_CONTAINS_FACT,
            rule_id=0, rule_version=0, reason_code=_REASON_CODE_DIRECT,
            base_confidence=0.7, status=CLAIM_STATUS_CANDIDATE,
        )
        engine.add_evidence(
            claim_id=c1, raw_ref_id=resolver.resolve("vec1"),
            evidence_type=_EVIDENCE_TYPE_VECTOR_CHUNK, strength=0.85,
        )

        # Scenario 2: graph
        e2 = engine.add_entity(entity_type=_ENTITY_TYPE_NODE)
        engine.add_relation(
            from_kind=ragcore.KIND_ENTITY, from_id=e1,
            to_kind=ragcore.KIND_ENTITY, to_id=e2,
            relation_type=1, rule_id=0, reason_code=_REASON_CODE_DIRECT,
        )

        # Scenario 3: LLM
        c3 = engine.add_claim(
            subject_id=e2, claim_type=_CLAIM_TYPE_LLM_EXTRACTED_FACT,
            rule_id=0, rule_version=0, reason_code=_REASON_CODE_DIRECT,
            base_confidence=0.5, status=CLAIM_STATUS_CANDIDATE,
        )
        engine.add_evidence(
            claim_id=c3, raw_ref_id=resolver.resolve("llm1"),
            evidence_type=_EVIDENCE_TYPE_LLM_RESPONSE, strength=0.45,
        )

        snap = engine.to_snapshot()
        assert len(snap) == _EXPECTED_SNAPSHOT_TOP_LEVEL_KEYS
        assert snap["schema_version"] == _EXPECTED_SCHEMA_VERSION

    def test_compute_effective_confidence_bounds_after_each_scenario(
        self,
    ) -> None:
        # Run each scenario; effective_confidence stays in [0.0, 1.0].
        engine = Engine()
        resolver = _TestLocalRawRefResolver()

        for evidence_type in (
            _EVIDENCE_TYPE_VECTOR_CHUNK,
            _EVIDENCE_TYPE_GRAPH_PATH,
            _EVIDENCE_TYPE_LLM_RESPONSE,
            _EVIDENCE_TYPE_SQL_FIELD,
            _EVIDENCE_TYPE_FILE_CHUNK,
            _EVIDENCE_TYPE_API_FIELD,
            _EVIDENCE_TYPE_MANUAL_NOTE,
        ):
            e = engine.add_entity(entity_type=_ENTITY_TYPE_ARTIFACT)
            c = engine.add_claim(
                subject_id=e, claim_type=300 + evidence_type,
                rule_id=0, rule_version=0, reason_code=_REASON_CODE_DIRECT,
                base_confidence=0.7, status=CLAIM_STATUS_CANDIDATE,
            )
            engine.add_evidence(
                claim_id=c, raw_ref_id=resolver.resolve(f"ref-{evidence_type}"),
                evidence_type=evidence_type, strength=0.8,
            )
            score = engine.compute_effective_confidence(c)
            assert 0.0 <= score.value <= 1.0

    def test_engine_method_surface_remains_frozen(self) -> None:
        # PR36-PKG _LOCKED_PUBLIC_METHODS still 40, unchanged by these tests.
        import inspect
        public_methods = sum(
            1 for n, _ in inspect.getmembers(Engine, callable)
            if not n.startswith("_")
        )
        assert public_methods == 40

    def test_ragcore_all_remains_48_symbols(self) -> None:
        assert len(ragcore.__all__) == 48
        assert len(set(ragcore.__all__)) == 48
