"""PR38-A External Consumer Probe — observe ragcore.Engine public API
under external-consumer pressure (case: Cerberus SSH finding).

================================================================================
Invariant (locked by user 2026-05-22)
================================================================================

ragcore is a generic judgment engine.
Cerberus is the first concrete external consumer case.
RAG is the operational knowledge layer that helps consumers use the
engine and map their domain evidence.

This probe is NOT a Cerberus optimization layer.
This probe is a pressure test for the GENERIC Engine API against the
first concrete external-consumer case.

Any Cerberus-specific concept discovered here MUST NOT be promoted
into ragcore core types or methods. Cerberus naming inside this file
is only a sample-data label — not a contract.

================================================================================
Status
================================================================================

- disposable, non-contract, non-production
- public API only (no _private access)
- no ragcore source change
- no snapshot schema change
- no judgment mathematics change
- file SHOULD be deleted (or moved to docs/archive/) after PR38-B
  freezes §50

================================================================================
Purpose
================================================================================

Observe what fields are actually required when an external consumer
domain object crosses the ragcore Engine boundary. The output of this
probe is a list of generic adapter pressures and field requirements
that should inform §50 RAG Operational Boundary in PR38-B.

The Cerberus SSH finding below is one realistic example. The pressures
it surfaces apply to ANY external domain consumer (medical / legal /
financial / research) that needs to translate domain observations into
ragcore Claim / Evidence / Gap / Relation.

================================================================================
Run
================================================================================

From the framework repo root:

    PYTHONPATH=. python examples/probe/external_consumer_probe.py

The `PYTHONPATH=.` prefix is needed because the framework is not
installed in the current environment (PEP 668 on Kali blocks system
pip install; use a venv for `pip install -e .` if preferred).
Alternatively, set up a virtualenv and `pip install -e .` once.

Reality questions at the bottom of this file (after `if __name__`).
"""

from __future__ import annotations

from ragcore import (
    CLAIM_STATUS_CANDIDATE,
    Engine,
)


# ============================================================================
# 1. Sample external-consumer observation (pre-adapter form)
# ============================================================================
#
# This is what an external consumer (here: Cerberus, a security domain
# consumer) might produce. The point is NOT to encode Cerberus structure
# into the framework — it is to use a realistic external observation as
# pressure on the GENERIC Engine API.
#
# Other external consumers (medical / legal / financial / research)
# would have analogous domain-specific structures that face the same
# adapter pressures.

# Sample data: a Cerberus SSH finding (one concrete external observation).
domain_observation = {
    # ---- consumer-domain identifiers ----
    "asset_id":      "10.0.1.42",                   # consumer-side host identifier
    "service_id":    "ssh-22",                       # consumer-side service identifier
    "endpoint":      "10.0.1.42:22",                 # tuple form
    # ---- raw provenance ----
    "tool":          "nmap",
    "tool_run_id":   "scan-20260522T100000Z",        # consumer-side scan run id (string)
    "raw_output":    "Server response: SSH-2.0-OpenSSH_7.4",
    # ---- extracted domain fields ----
    "extracted": {
        "service":   "ssh",
        "product":   "OpenSSH",
        "version":   "7.4",
        "port":      22,
        "protocol":  "tcp",
    },
    "observed_at":   "2026-05-22T10:00:00Z",
}


# ============================================================================
# 2. Disposable manual mapping into ragcore.Engine public API
# ============================================================================
#
# This mapping is intentionally ad hoc. PR38-A's purpose is to observe
# WHICH mapping choices feel arbitrary vs natural for a GENERIC consumer.
#
# Domain integer constants used here would come from a consumer-side
# registry in a real adapter. They are made up here for the probe:
#
#   DOMAIN_ENTITY_TYPE_HOST                  = 1
#   DOMAIN_OBSERVATION_TYPE_SERVICE_BANNER   = 10
#   DOMAIN_SOURCE_TYPE_TOOL_OUTPUT             = 1
#   DOMAIN_CLAIM_TYPE_RUNS_SOFTWARE            = 100
#   DOMAIN_EVIDENCE_TYPE_SERVICE_BANNER_TEXT   = 20
#   DOMAIN_REASON_CODE_DIRECT_OBSERVATION       = 1


def probe() -> None:
    engine = Engine()

    # -----------------------------------------------------------------------
    # 2a. Entity = the subject of the claim
    # -----------------------------------------------------------------------
    # Q1 observation: subject granularity choice. Could have been
    #                  service_id ("ssh-22") or endpoint ("10.0.1.42:22").
    #                  All three are reasonable subjects depending on
    #                  what the claim asserts. Adapter must pick
    #                  consistently per claim_type semantics.
    # -----------------------------------------------------------------------
    entity_id = engine.add_entity(entity_type=1)  # 1 = host (consumer-domain enum)

    # -----------------------------------------------------------------------
    # 2b. Observation = the raw observation event
    # -----------------------------------------------------------------------
    # Q3 observation: raw_ref_id here is an int placeholder. The
    #                  consumer's natural identifier is a string
    #                  ("scan-20260522T100000Z"). Adapter must maintain
    #                  a consumer-side int registry OR introduce a
    #                  hash-to-int resolver. This is THE clearest
    #                  generic adapter friction point.
    # -----------------------------------------------------------------------
    observation_id = engine.add_observation(
        entity_id=entity_id,
        raw_ref_id=1,  # PLACEHOLDER — adapter must resolve string → int
        observation_type=10,  # 10 = service_banner (consumer-domain enum)
        source_type=1,  # 1 = tool_output (consumer-domain enum)
    )

    # -----------------------------------------------------------------------
    # 2c. Claim = a structured judgment about the subject
    # -----------------------------------------------------------------------
    # Q2 observation: ragcore.Claim has only (subject_id, claim_type, ...).
    #                  No `predicate` or `object` fields. Consumer must
    #                  ENCODE the predicate into the claim_type integer
    #                  and maintain a consumer-side claim_type registry.
    # Q6 observation: base_confidence is decided by the adapter, not by
    #                  a rule. This split (adapter sets inputs, engine
    #                  composes 7 modifiers) feels natural.
    # -----------------------------------------------------------------------
    claim_id = engine.add_claim(
        subject_id=entity_id,
        claim_type=100,  # 100 = runs_software (consumer-domain enum)
        rule_id=0,       # no rule firing in this probe
        rule_version=0,
        reason_code=1,
        base_confidence=0.9,  # adapter policy: direct observation → high
        status=CLAIM_STATUS_CANDIDATE,
    )

    # -----------------------------------------------------------------------
    # 2d. Evidence = a normalized signal supporting the claim
    # -----------------------------------------------------------------------
    # Q4 observation: ragcore.Evidence is one (raw_ref_id, evidence_type,
    #                  strength) row. Adapter must DECIDE granularity:
    #                  - one tool run → one evidence?
    #                  - one extracted field → one evidence?
    #                  - one normalized signal → one evidence?
    #                  Chose "one normalized signal" (the observation event).
    # Q6 observation continued: strength is also adapter-set policy.
    # -----------------------------------------------------------------------
    evidence_id = engine.add_evidence(
        claim_id=claim_id,
        raw_ref_id=1,
        evidence_type=20,  # 20 = service_banner_text (consumer-domain enum)
        strength=0.85,     # adapter policy: direct observation strength
    )

    # -----------------------------------------------------------------------
    # 2e. Read effective confidence
    # -----------------------------------------------------------------------
    # Q6 observation continued: adapter sets inputs (base_confidence,
    #                  evidence.strength). Engine multiplies through 7
    #                  modifiers (status / freshness / gap / count /
    #                  rule_stats / evidence_type). Engine owns the
    #                  composition; adapter owns the inputs.
    #                  ✓ This split is engine-domain-light and feels
    #                  correct for ANY external consumer, not just
    #                  Cerberus.
    # -----------------------------------------------------------------------
    score = engine.compute_effective_confidence(claim_id)

    # -----------------------------------------------------------------------
    # 2f. Snapshot for state handoff
    # -----------------------------------------------------------------------
    # Q7 observation: to_snapshot() returns a JSON-compatible dict.
    #                  Engine never writes to disk. The adapter (and
    #                  ultimately the consumer's storage layer) is
    #                  responsible for where this dict lives.
    #                  ✓ Matches PR36-PKG §48.9 (import side-effect-free).
    # -----------------------------------------------------------------------
    snapshot = engine.to_snapshot()

    # =======================================================================
    # 3. Output
    # =======================================================================

    print("=== PR38-A External Consumer Probe ===")
    print()
    print("Sample external observation (case: Cerberus SSH finding):")
    print(f"  asset_id:    {domain_observation['asset_id']}")
    print(f"  service:     {domain_observation['extracted']['service']}")
    print(f"  product:     {domain_observation['extracted']['product']}")
    print(f"  version:     {domain_observation['extracted']['version']}")
    print(f"  port:        {domain_observation['extracted']['port']}")
    print()
    print("ragcore.Engine state (after adapter-side mapping):")
    print(f"  entity_id:                {entity_id}")
    print(f"  observation_id:           {observation_id}")
    print(f"  claim_id:                 {claim_id}")
    print(f"  evidence_id:              {evidence_id}")
    print()
    print("Engine output:")
    print(f"  effective_confidence:     {score.value}")
    print()
    print("Snapshot:")
    print(f"  top-level keys:           {len(snapshot)}")
    print(f"  schema_version:           {snapshot['schema_version']}")
    print(f"  claims_count:             {len(snapshot['claims'])}")
    print(f"  evidences_count:          {len(snapshot['evidences'])}")
    print(f"  observations_count:       {len(snapshot['observations'])}")
    print(f"  entities_count:           {len(snapshot['entities'])}")
    print()
    print("ragcore source files used: ragcore (public API only)")
    print("No ragcore source change. No snapshot schema change.")
    print("Cerberus naming present only in sample-data labels.")


if __name__ == "__main__":
    probe()


# ============================================================================
# 4. Reality questions — generic form (case: Cerberus SSH finding)
# ============================================================================
#
# These 8 questions are the explicit deliverable of PR38-A. Each question
# is phrased GENERICALLY (about any external consumer), with the Cerberus
# case noted only as the first concrete example.
#
# The §50 contract derived from these answers must remain domain-neutral.
#
# ----------------------------------------------------------------------------
# Q1. external consumer 의 domain finding 이 Engine 에 들어갈 때,
#     subject 는 어떤 domain unit 에 매핑되어야 하는가?
# ----------------------------------------------------------------------------
# OBSERVED (generic): subject granularity depends on the claim's semantics.
#   A consumer may have multiple valid subject candidates per finding.
#
#   case: Cerberus SSH finding
#     - "host runs OpenSSH 7.4"           → asset_id (host) as subject
#     - "service listens on port 22"      → service_id as subject
#     - "endpoint accepts TCP"             → endpoint as subject
#
# IMPLICATION FOR §50:
#   The adapter MUST pick subject granularity per claim_type.
#   §50 should not freeze a single subject convention; it should require
#   each adapter to declare its choice per claim_type.
#
# ----------------------------------------------------------------------------
# Q2. ragcore.Claim 의 (subject_id, claim_type) 구조가
#     외부 도메인의 predicate-rich finding 과 어떻게 정합하는가?
# ----------------------------------------------------------------------------
# OBSERVED (generic): ragcore.Claim has no explicit predicate or object
#   field. The predicate IS the claim_type integer. Adapter must
#   maintain a consumer-side claim_type integer registry mapping
#   semantic predicates → integers.
#
#   case: Cerberus → "host_runs_software" = 100, "service_listens_on_port" = 101, etc.
#
# IMPLICATION FOR §50:
#   §50 should require "consumer-side claim_type registry."
#   Engine does NOT own the predicate vocabulary.
#
# ----------------------------------------------------------------------------
# Q3. external consumer 의 raw reference (file path / tool run id /
#     log span / hash) 가 ragcore 의 raw_ref_id: int 와 어떻게 정합하는가?
# ----------------------------------------------------------------------------
# OBSERVED (generic, FRICTION POINT): ragcore expects raw_ref_id: int.
#   External consumers naturally have strings, composite keys, or
#   external storage identifiers. The adapter MUST maintain a stable
#   int allocation strategy (registry, hash-to-int, or external mapping).
#
#   case: Cerberus → "scan-20260522T100000Z" → int registry lookup
#
# IMPLICATION FOR §50:
#   §50 should require "adapter owns raw_ref_id allocation strategy."
#   This is the SINGLE CLEAREST adapter responsibility discovered by
#   this probe. Engine never interprets raw_ref_id beyond storing it.
#
# ----------------------------------------------------------------------------
# Q4. external consumer 가 raw observation 을 ragcore.Evidence 로 변환할 때,
#     granularity 단위는 어떻게 결정하는가?
# ----------------------------------------------------------------------------
# OBSERVED (generic): adapter must decide:
#   - one tool run → one Evidence? (coarse — loses sub-signal nuance)
#   - one extracted field → one Evidence? (fine — many small evidences)
#   - one normalized signal → one Evidence? (medium — recommended default)
#
#   case: Cerberus nmap result produces extracted={service, product,
#         version, port, protocol}. Probe chose "one normalized signal".
#
# IMPLICATION FOR §50:
#   §50 should specify "Evidence granularity is adapter-decided."
#   Probably "one normalized signal" is the default recommendation
#   across domains; medical / legal / financial / research consumers
#   would arrive at similar granularity for similar reasons.
#
# ----------------------------------------------------------------------------
# Q5. external consumer 의 finding-level / asset-level / claim-level
#     bundle 중 ragcore 호출 단위로 자연스러운 것은 무엇인가?
# ----------------------------------------------------------------------------
# OBSERVED (generic): both ingest and read directions exist:
#   - ingest: finding-level bundle (one finding → entity + claims + evidence)
#   - read:   asset-level bundle (asset rollup of all related claims)
#
#   case: Cerberus → ingest per-finding, read per-asset.
#
# IMPLICATION FOR §50:
#   §50 should distinguish "EngineInput" (ingest direction, finding-bundle)
#   from "EngineQuery" (read direction, asset-bundle). Both are adapter
#   concepts. Engine sees neither — Engine only sees individual public
#   method calls.
#
# ----------------------------------------------------------------------------
# Q6. base_confidence + evidence.strength 는 adapter 가 정하고,
#     7-modifier 합성은 engine 이 책임지는 분리가 자연스러운가?
# ----------------------------------------------------------------------------
# OBSERVED (generic): ✓ this split feels natural.
#   - Adapter sets per-evidence-class defaults (banner=0.9, api=0.95, etc.)
#   - Engine composes effective = base × status × freshness × gap × count ×
#                                  rule_stats × evidence_type
#   - Rules (when present) influence rule_stats modifier.
#   - Adapter never computes the final score — only inputs.
#
#   case: Cerberus → banner clarity policy = adapter; modifier composition = engine.
#
# IMPLICATION FOR §50:
#   §50 should clarify "adapter sets inputs (base + strength).
#   engine composes 7-modifier formula. consumer never computes the
#   final score." This split is engine-domain-light.
#
# ----------------------------------------------------------------------------
# Q7. snapshot 저장은 consumer-side 책임 (PR36-PKG §48.9) 이
#     외부 도메인에 일관되게 적용되는가?
# ----------------------------------------------------------------------------
# OBSERVED (generic): ✓ CONFIRMED.
#   - Engine returns JSON-compatible dict from to_snapshot()
#   - Engine never writes to disk (PR36-PKG §48.9 invariant)
#   - Consumer decides storage backend (JSON / SQLite / S3 / RDB / etc.)
#   - This applies identically across all external domains.
#
#   case: Cerberus → Cerberus storage layer holds the dict.
#         medical / legal / financial / research consumers → their
#         storage layers hold the dict.
#
# IMPLICATION FOR §50:
#   §50 should REFERENCE PR36-PKG §48.9 + PR37 README persistence
#   boundary rather than re-document. The rule is already stable.
#
# ----------------------------------------------------------------------------
# Q8. retrieval / vector DB 결과는 raw 로 Engine 에 들어갈 수 없고
#     adapter 에서 evidence atom 으로 변환되어야 하는가?
# ----------------------------------------------------------------------------
# OBSERVED (generic): ✓ CONFIRMED (without exercising retrieval in this
#   probe — the conclusion is forced by Evidence shape).
#
#   ragcore.Evidence requires (raw_ref_id: int, evidence_type: int,
#   strength: float). A vector DB search result (text + similarity score
#   + metadata) does NOT fit directly. Adapter MUST:
#     1. decide which retrieved item is worth promoting to Evidence
#     2. assign an evidence_type integer
#     3. translate similarity score → strength (NOT identity mapping;
#        cosine similarity is not engine confidence)
#     4. allocate raw_ref_id for the retrieved chunk
#
#   case: Cerberus RAG retrieval (or any future consumer's retrieval).
#
# IMPLICATION FOR §50:
#   §50 should specify "retrieval results MUST pass through the adapter's
#   evidence-atom translation step. Vector similarity is NOT engine
#   confidence." This is the strongest single rule the probe reveals.
#
# ============================================================================
# 5. Probe summary for PR38-B §50 (domain-neutral)
# ============================================================================
#
# Likely §50 contract objects (informed by this probe, all domain-neutral):
#
#   ADAPTER MUST MAINTAIN (consumer-side, integer registries):
#     - entity_type registry              (domain-specific subjects)
#     - observation_type registry          (domain-specific event kinds)
#     - source_type registry               (domain-specific provenance)
#     - claim_type registry                (domain-specific predicates)
#     - evidence_type registry             (domain-specific signal kinds)
#     - reason_code registry               (per claim_type semantics)
#     - raw_ref_id resolution strategy     (string → int OR hash-to-int)
#
#   ADAPTER MUST DECIDE (per finding type):
#     - subject granularity                (entity vs sub-entity vs endpoint)
#     - evidence granularity                (tool-run vs field vs signal)
#     - base_confidence policy              (per evidence-class default)
#     - strength policy                     (per evidence-class default)
#     - similarity → strength mapping       (when retrieval is active)
#
#   ADAPTER MUST PROVIDE (interface direction):
#     - EngineInput  (ingest)               finding-bundle granularity
#     - EngineQuery  (read)                 entity-bundle granularity
#
#   §50 SHOULD NOT FREEZE:
#     - specific integer assignments        (consumer-side, may evolve)
#     - specific storage backend            (consumer-side, may evolve)
#     - specific vector DB / retrieval      (consumer-side, may evolve)
#     - specific embedding version          (consumer-side, may evolve)
#     - specific domain vocabulary          (consumer-side, may evolve)
#
#   §50 SHOULD FREEZE (domain-neutral rules):
#     - adapter MUST have claim_type / evidence_type / etc. registries
#     - adapter MUST have raw_ref resolver
#     - adapter MUST translate retrieval, not pipe through
#     - storage is consumer-side (reference PR36-PKG §48.9)
#     - base_confidence + strength are adapter-set
#     - 7-modifier composition is engine-internal
#     - similarity score is NOT engine confidence
#
# ============================================================================
# 6. Followup actions before PR38-B
# ============================================================================
#
# 1. Run this probe (`python examples/probe/external_consumer_probe.py`)
#    and observe the printed result.
# 2. Review whether the 8 answers feel correct against actual Cerberus
#    integration patterns (cerberus_client repo). The Cerberus case is
#    the first concrete external consumer; future consumers (medical,
#    legal, financial, research domains) will face the same questions.
# 3. If a new question emerges from any consumer's integration thinking,
#    append it here as Q9 / Q10 / ... before writing §50.
# 4. Once Q1~Q8 (and any additions) feel stable, proceed to PR38-B §50.
# 5. After PR38-B merges, this file (external_consumer_probe.py) should
#    be deleted or moved to docs/archive/ — it is disposable by design.
#
# ============================================================================
# 7. Locked invariants for any future Cerberus-related work
# ============================================================================
#
# (Repeated from header for visibility at end of file.)
#
#   ragcore is a generic judgment engine.
#   Cerberus is the first concrete external consumer case.
#   This probe is NOT a Cerberus optimization layer.
#   Any Cerberus-specific concept here MUST NOT be promoted into ragcore
#   core types or methods.
#   Cerberus naming in this file is only a sample-data label —
#   not a contract.
