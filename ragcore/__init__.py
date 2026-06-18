from ragcore.condition import (
    TRACE_REASON_MATCH,
    TRACE_REASON_MISMATCH,
    TRACE_REASON_MISSING_FIELD,
    TRACE_REASON_TYPE_MISMATCH,
    Combinator,
    CombinatorTrace,
    Predicate,
    PredicateTrace,
    evaluate_condition,
    evaluate_condition_with_trace,
    load_condition_tree,
)
from ragcore.engine import Engine
from ragcore.rule_compile import compile_rule_definition, register_rule_spec
from ragcore.rule_loader import (
    RuleSpec,
    compile_rule_condition,
    load_rule_spec,
    load_rule_spec_from_yaml,
)
from ragcore.rule_gap import RequiredEvidenceTemplate, compile_required_evidence
from ragcore.rule_output import RuleOutputTemplate, compile_rule_output
from ragcore.rule_runtime import FiringTrace, fire_rule, fire_rule_with_trace
from ragcore.types import (
    CLAIM_STATUS_CANDIDATE,
    CLAIM_STATUS_CONFIRMED,
    CLAIM_STATUS_DISPUTED,
    CLAIM_STATUS_REFUTED,
    KIND_CLAIM,
    KIND_ENTITY,
    KIND_EVIDENCE,
    KIND_GAP,
    KIND_OBSERVATION,
    KIND_RELATION,
    RULE_MATURITY_DEPRECATED,
    RULE_MATURITY_EXPERIMENTAL,
    RULE_MATURITY_STABLE,
    Claim,
    ClaimLifecycleEvent,
    EngineStateIdentity,
    Entity,
    Evidence,
    Gap,
    Observation,
    Relation,
    RuleDefinition,
    RuleStats,
    ScoreValue,
)

# Public API surface — 49 symbols, grouped by purpose (§45.5 + PR73-M04).
# Order is documentation, not behavior: tests use frozenset equality.
__all__ = [
    # Lifecycle status enum (4) — §18 / §42.2 / §43.3-5
    "CLAIM_STATUS_CANDIDATE",
    "CLAIM_STATUS_CONFIRMED",
    "CLAIM_STATUS_DISPUTED",
    "CLAIM_STATUS_REFUTED",
    # Rule maturity enum (3) — §27 RuleDefinition.maturity
    "RULE_MATURITY_DEPRECATED",
    "RULE_MATURITY_EXPERIMENTAL",
    "RULE_MATURITY_STABLE",
    # Kind enum (6) — §13 Relation cross-kind discriminator
    "KIND_CLAIM",
    "KIND_ENTITY",
    "KIND_EVIDENCE",
    "KIND_GAP",
    "KIND_OBSERVATION",
    "KIND_RELATION",
    # Trace reason enum (4) — condition evaluation trace
    "TRACE_REASON_MATCH",
    "TRACE_REASON_MISMATCH",
    "TRACE_REASON_MISSING_FIELD",
    "TRACE_REASON_TYPE_MISMATCH",
    # Core dataclasses (8) — §11~§16, §23 lifecycle event,
    # PR73-M04 Engine state identity
    "Claim",
    "ClaimLifecycleEvent",
    "EngineStateIdentity",
    "Entity",
    "Evidence",
    "Gap",
    "Observation",
    "Relation",
    # Rule dataclasses (5) — §27 rule definition / stats / spec / templates
    "RequiredEvidenceTemplate",
    "RuleDefinition",
    "RuleOutputTemplate",
    "RuleSpec",
    "RuleStats",
    # Trace dataclasses (5) — rule firing / condition trace structures
    "Combinator",
    "CombinatorTrace",
    "FiringTrace",
    "Predicate",
    "PredicateTrace",
    # Value type (1) — §10 ScoreValue [0.0, 1.0]
    "ScoreValue",
    # Engine class (1) — judgment core
    "Engine",
    # Compile functions (4) — rule definition / output / required evidence
    "compile_required_evidence",
    "compile_rule_condition",
    "compile_rule_definition",
    "compile_rule_output",
    # Evaluate functions (2) — condition evaluation (with optional trace)
    "evaluate_condition",
    "evaluate_condition_with_trace",
    # Fire functions (2) — rule firing (with optional trace)
    "fire_rule",
    "fire_rule_with_trace",
    # Load functions (3) — condition tree / rule spec loading
    "load_condition_tree",
    "load_rule_spec",
    "load_rule_spec_from_yaml",
    # Register functions (1) — rule spec registration
    "register_rule_spec",
]
