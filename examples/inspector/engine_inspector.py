"""External Engine Inspector — PR51 minimal claim read query MVP.

PR51 proves that a minimal claim read query can be assembled
outside ragcore using only existing public read-only methods.

Scope limitation (locked, user 2026-05-25)
------------------------------------------
PR51 is not a ragcore read API PR.
PR51 reads Engine state through an external inspector, without
changing Engine state.

This module:
  - lives outside ragcore (examples/inspector/, consumer-side example)
  - uses ONLY the 19 read-only public methods listed in
    docs/architecture/ENGINE_READ_SURFACE_AUDIT.md §3.1
  - does NOT access any private attribute (engine._claims,
    engine._evidence, engine._gaps, etc.)
  - does NOT add any public symbol to ragcore.__all__
  - does NOT freeze a packet shape (that is PR52 LLM Context
    Packet Spec, separately decided)
  - does NOT introduce domain vocabulary
    (cerberus / vulnerability / scanner / exploit / risk label /
     verdict / tool plan / LLM proposal — all forbidden here)
  - does NOT compute LLM-facing verdicts, probabilities, or
    risk labels (PR44-D AP-CF-1 / AP-X-4 honor)

What PR51 demonstrates
----------------------
A consumer that wants to feed Engine state to an LLM (or to any
external proposal layer) does NOT need ragcore source changes.
The 19 read-only methods are sufficient.

PR50 §6 audit pseudocode is hereby executable.

References
----------
- docs/architecture/ENGINE_READ_SURFACE_THAW_POLICY.md  (PR49)
- docs/architecture/ENGINE_READ_SURFACE_AUDIT.md         (PR50)
- direction_rag_framework_proposal_layer (memory direction §10)
"""

from __future__ import annotations

from typing import Any

from ragcore import Engine


def build_engine_context_packet(engine: Engine, claim_id: int) -> dict[str, Any]:
    """Assemble a minimal Engine Context Packet for a single Claim.

    Uses only the read-only public methods of ragcore.Engine. The
    return value is a plain dict whose entries are Engine-owned
    objects (Claim, Evidence, Gap, ClaimLifecycleEvent) and
    integer ids. The caller is responsible for any further
    serialization or shape transformation.

    Args:
        engine:    a ragcore.Engine instance whose state is being
                   inspected. The engine is NOT mutated.
        claim_id:  integer id of the Claim to inspect.

    Returns:
        A dict with the following keys:
            "claim"                  — Claim object
            "effective_confidence"   — ScoreValue from
                                       compute_effective_confidence
            "supporting_evidence"   — tuple of Evidence objects
                                       returned by
                                       evidences_for_claim
            "contradictions"        — tuple of evidence_id ints
                                       (all contradictions,
                                        active + resolved)
            "active_contradictions" — tuple of evidence_id ints
                                       (active only)
            "unresolved_gaps"       — tuple of Gap objects whose
                                       gap_resolution is None
            "lifecycle_history"     — tuple of
                                       ClaimLifecycleEvent objects

    Notes:
        - Packet shape is NOT a contract. PR52 LLM Context Packet
          Spec (separately decided) may define a stable shape.
          PR51 leaves the shape minimal and unfrozen.
        - The packet contains NO derived verdict, probability,
          or risk label. It is raw Engine-owned state only.
        - The function reads N + 1 times per claim
          (1 evidences_for_claim + N gap_resolution lookups for
           unresolved-gap filtering). This is intentional;
           per PR50 §5.2 the N+1 is wrapper composition cost,
           not an Engine deficiency.
    """
    claim = engine.get_claim(claim_id)
    effective_confidence = engine.compute_effective_confidence(claim_id)

    supporting_evidence = tuple(engine.evidences_for_claim(claim_id))

    contradictions = engine.contradictions_for_claim(claim_id)
    active_contradictions = engine.active_contradictions_for_claim(claim_id)

    gaps = engine.gaps_for_claim(claim_id)
    unresolved_gaps = tuple(
        gap for gap in gaps if engine.gap_resolution(gap.id) is None
    )

    lifecycle_history = engine.claim_lifecycle_history(claim_id)

    return {
        "claim": claim,
        "effective_confidence": effective_confidence,
        "supporting_evidence": supporting_evidence,
        "contradictions": contradictions,
        "active_contradictions": active_contradictions,
        "unresolved_gaps": unresolved_gaps,
        "lifecycle_history": lifecycle_history,
    }
