"""Minimal consumer-side role assignment example.

This module is an illustrative consumer-side example. It does not
define a canonical schema, assign roles automatically, validate
semantic correctness, or create Engine truth.

The dictionaries below are local example data. Their keys, nesting,
and labels are not framework contracts.

A consumer may represent the same policy differently as long as the
PR59 and PR60 boundaries are preserved.

No role label in this example authorizes execution, Engine mutation,
lifecycle transition, or final judgment.

All role labels in this module use the ``example:`` prefix to mark
them as illustrative local values. They are not enum members, a
registered role inventory, or part of any framework public surface.
"""

from pprint import pprint


# The same data_item_id is reused across the two examples below to
# show that a single fragment may be read differently in different
# interpretation contexts. The two assignment dictionaries are
# independent objects; neither mutates the other.


RESOLVED_EXAMPLE = {
    "data_item": {
        "data_item_id": "example-item-0001",
        "fragment_locator": "record:0007#field:body",
        "content_summary": (
            "a short narrative entry referring to a previously "
            "recorded direct observation"
        ),
    },
    "provenance": {
        "source_type": "example:external_document_collection",
        "trace_id": "trace-2026-06-16-0001",
    },
    "record_shape": "example:document_record",
    "interpretation_context": {
        "context_id": "ctx-review-0001",
        "question": (
            "Does this fragment describe an event that was directly "
            "recorded in this consumer's own observation log?"
        ),
        "intended_consumer": "operator_review_panel",
    },
    "assignment_basis": (
        "The fragment refers to a directly recorded event, the "
        "context_id is a review panel reading the fragment as a "
        "first-hand observation, the provenance is traceable, and "
        "the record shape supports a single primary interpretation."
    ),
    "primary_role": "example:observation",
    "secondary_roles": [
        {
            "label": "example:knowledge-reference",
            "justification": (
                "The fragment also mentions a related prior note "
                "and the review panel benefits from seeing it "
                "alongside the primary reading."
            ),
            "meaning_distinct_from_primary": (
                "the prior note is background reference, not a "
                "first-hand observation"
            ),
            "allowed_uses": [
                "display the linked prior note during operator review",
            ],
            "forbidden_uses": [
                "use the linked prior note to confirm the observation",
                "merge the linked prior note into the primary fragment",
            ],
            "non_contradiction_with_primary": (
                "the secondary role describes a reference role on "
                "different content and does not compete with the "
                "primary reading"
            ),
            "no_downstream_authorization": (
                "the secondary role does not enable any action; it "
                "only adds reading context"
            ),
        },
    ],
    "allowed_uses": [
        "display this fragment during operator review",
        "compare this fragment with another traceable item under "
        "the same context_id",
        "include this fragment in a consumer-side explanation",
        "use this fragment as input when identifying missing "
        "information for follow-up review",
    ],
    "forbidden_uses": [
        "register this fragment as Engine evidence automatically",
        "create a registered Claim from this fragment automatically",
        "resolve a Gap using this fragment automatically",
        "change Claim lifecycle state as a side effect of reading "
        "this fragment",
        "execute a tool because this fragment was assigned a role",
        "publish a final verdict from this assignment",
        "bypass operator review on the basis of this assignment",
    ],
    "traceability": {
        "source_id": "example:source/external_document_collection",
        "fragment_locator": "record:0007#field:body",
        "context_id": "ctx-review-0001",
        "assignment_basis_summary": (
            "single primary reading under a review panel context "
            "with traceable provenance"
        ),
    },
}


UNRESOLVED_EXAMPLE = {
    "data_item": {
        "data_item_id": "example-item-0001",
        "fragment_locator": "record:0007#field:body",
        "content_summary": (
            "a short narrative entry referring to a previously "
            "recorded direct observation"
        ),
    },
    "provenance": {
        "source_type": "example:external_document_collection",
        "trace_id": "trace-2026-06-16-0002",
    },
    "record_shape": "example:document_record",
    "interpretation_context": {
        "context_id": "ctx-investigation-0002",
        "question": (
            "Is this fragment an external knowledge reference, or "
            "a candidate statement still awaiting independent "
            "confirmation?"
        ),
        "intended_consumer": "consumer_side_review_logic",
    },
    "assignment_basis": (
        "The fragment supports more than one plausible reading. "
        "The provenance is traceable but the surrounding context "
        "does not narrow interpretation to a single primary role. "
        "Selecting one candidate for convenience would fabricate "
        "certainty that the available evidence does not support."
    ),
    "primary_role": None,
    "candidate_roles": [
        "example:knowledge-reference",
        "example:candidate-statement",
    ],
    "candidate_roles_note": (
        "candidate_roles is illustrative local data. It is not a "
        "registry of permitted roles, an enum, or a framework "
        "vocabulary. The consumer holds the assignment as "
        "unresolved until additional context is available."
    ),
    "secondary_roles": [],
    "allowed_uses": [
        "display this fragment during operator review as an "
        "unresolved item",
        "request additional context that could resolve the "
        "interpretation ambiguity",
    ],
    "forbidden_uses": [
        "select one candidate role for convenience",
        "broaden the allowed uses while the assignment is unresolved",
        "convert the ambiguity into a numerical confidence value",
        "treat any natural-language rationale about the fragment "
        "as proof of a role",
        "register this fragment as Engine evidence automatically",
        "create a registered Claim from this fragment automatically",
        "resolve a Gap using this fragment automatically",
        "change Claim lifecycle state because the fragment has "
        "been read",
        "execute a tool while the assignment is unresolved",
        "publish a final verdict from an unresolved assignment",
        "advance any downstream transition while the assignment "
        "is unresolved",
    ],
    "resolution_note": (
        "Additional context is required before a primary role may "
        "be assigned. While the assignment remains unresolved, the "
        "allowed_uses list is narrow, the forbidden_uses list "
        "remains explicit, and downstream transitions stay blocked."
    ),
    "traceability": {
        "source_id": "example:source/external_document_collection",
        "fragment_locator": "record:0007#field:body",
        "context_id": "ctx-investigation-0002",
        "assignment_basis_summary": (
            "unresolved reading; primary role is withheld pending "
            "additional context"
        ),
    },
}


if __name__ == "__main__":
    print("=== Resolved contextual assignment example ===")
    pprint(RESOLVED_EXAMPLE, sort_dicts=False, width=88)
    print()
    print("=== Unresolved contextual assignment example ===")
    pprint(UNRESOLVED_EXAMPLE, sort_dicts=False, width=88)
