"""Minimal domain-neutral external adapter translation traces.

This module contains hand-authored, consumer-side translation
traces. It does not implement an external adapter, define a
canonical adapter schema, or create Engine truth.

The dictionaries, keys, labels, and nesting in this module are
local illustrative data, not framework contracts.

The examples intentionally remain independent of the PR61
dictionary representation and the PR62 local validator. A
different external adapter may carry external data through a
different consumer-side representation while preserving the
PR59, PR60, and PR63 boundaries.

A structurally complete example does not authorize execution,
Engine mutation, lifecycle transition, or final judgment.

The same external item may produce a resolved or unresolved
consumer handoff under different interpretation contexts. In
this module both traces share an identical source snapshot
(same collection identifier, item identifier, source revision,
record kind, source field values, stable locator, and
acquisition reference). The differences between the two traces
are interpretation-side, not source-side.

All role-bearing labels in this module use the ``example:``
prefix to mark them as illustrative local values. They are not
enum members, registered role identifiers, or framework
vocabulary.
"""

from pprint import pprint


# Both traces describe the same synthetic external item. They are
# defined as two independent dict literals; neither is an alias,
# copy, or in-place mutation of the other.


RESOLVED_TRANSLATION_TRACE = {
    "external_item": {
        "collection_identifier": "synthetic-reference-collection-01",
        "item_identifier": "item-0007",
        "source_revision": "r3",
    },
    "adapter_context": {
        "adapter_identity": "synthetic-reference-adapter-example",
        "adapter_revision": "example-r1",
        "run_reference": "translation-run-resolved-0001",
    },
    "provenance": {
        "source_collection_identifier": (
            "synthetic-reference-collection-01"
        ),
        "source_item_identifier": "item-0007",
        "source_revision": "r3",
        "stable_locator": (
            "synthetic://reference-collection-01/item-0007@r3"
        ),
        "acquisition_reference": "synthetic-acquisition-0001",
        "adapter_identity": "synthetic-reference-adapter-example",
        "adapter_revision": "example-r1",
    },
    "source_retention": {
        "stable_locator": (
            "synthetic://reference-collection-01/item-0007@r3"
        ),
        "locator_scope": "local illustrative data",
        "externally_retrievable": False,
        "source_revision": "r3",
        "retained_source_fields": {
            "heading": "Review date update",
            "review_date": "2026-06-20",
            "layout_hint": "compact",
        },
    },
    "source_shape": {
        "source_record_kind": "reference_note_record",
        "source_field_names": [
            "heading",
            "review_date",
            "layout_hint",
        ],
    },
    "normalized_view": {
        "title": "Review date update",
        "stated_date": "2026-06-20",
    },
    "translation_decisions": [
        {
            "source_location": "external_item",
            "consumer_location": "provenance + source_retention",
            "transformation": (
                "retain the source item and revision through "
                "provenance and source-retention entries"
            ),
            "reason": (
                "preserve a reviewable trace path back to the "
                "synthetic source item"
            ),
        },
        {
            "source_location": "external_item.heading",
            "consumer_location": "normalized_view.title",
            "transformation": "rename heading to title",
            "reason": (
                "consumer-side review uses the term title; "
                "the source value is unchanged"
            ),
        },
        {
            "source_location": "external_item.review_date",
            "consumer_location": "normalized_view.stated_date",
            "transformation": "rename review_date to stated_date",
            "reason": (
                "consumer-side review uses the term stated_date "
                "to mark this as a date explicitly stated by the "
                "source, not a derived value"
            ),
        },
        {
            "source_location": "external_item.layout_hint",
            "consumer_location": "normalized_view (absent)",
            "transformation": (
                "omit layout_hint from normalized_view; preserve "
                "it inside source_retention.retained_source_fields"
            ),
            "reason": (
                "layout_hint is a source-only presentation hint; "
                "it is not part of the normalized consumer view, "
                "but its source value remains preserved"
            ),
        },
    ],
    "loss_notes": [
        {
            "kind": "normalized-view omission",
            "source_field": "layout_hint",
            "normalized_treatment": "omitted from normalized_view",
            "source_retention": (
                "preserved in source_retention.retained_source_fields"
            ),
            "reason": "source-only presentation hint",
        },
    ],
    "derivation_notes": {
        "derived_values_created": False,
        "note": (
            "stated_date is a renamed retained value, not a "
            "calculated or inferred value"
        ),
    },
    "interpretation_context": {
        "question": (
            "Which review date is explicitly stated by the "
            "external item?"
        ),
        "intended_consumer": "operator review panel",
        "review_purpose": (
            "confirm a single date that the source explicitly "
            "states"
        ),
    },
    "consumer_handoff": {
        "contextual_primary_role": "example:observation",
        "local_candidate_roles": [],
        "permitted_consumer_uses": [
            "display the stated date during review",
            "compare the stated date with another traceable item",
            "include the stated date in a consumer-side explanation",
        ],
        "blocked_consumer_uses": [
            "promote the normalized date as verified Engine truth",
            "add Engine evidence automatically",
            "register a Claim automatically",
            "change lifecycle state",
            "execute a tool",
            "publish a final judgment",
            "bypass consumer or operator review",
        ],
    },
    "traceability": {
        "translation_run_reference": (
            "translation-run-resolved-0001"
        ),
        "provenance_summary": (
            "synthetic-reference-collection-01 / item-0007 @ r3 / "
            "via synthetic-reference-adapter-example example-r1"
        ),
        "interpretation_summary": (
            "single explicit stated date under a review-panel "
            "context"
        ),
    },
}


UNRESOLVED_TRANSLATION_TRACE = {
    "external_item": {
        "collection_identifier": "synthetic-reference-collection-01",
        "item_identifier": "item-0007",
        "source_revision": "r3",
    },
    "adapter_context": {
        "adapter_identity": "synthetic-reference-adapter-example",
        "adapter_revision": "example-r1",
        "run_reference": "translation-run-unresolved-0002",
    },
    "provenance": {
        "source_collection_identifier": (
            "synthetic-reference-collection-01"
        ),
        "source_item_identifier": "item-0007",
        "source_revision": "r3",
        "stable_locator": (
            "synthetic://reference-collection-01/item-0007@r3"
        ),
        "acquisition_reference": "synthetic-acquisition-0001",
        "adapter_identity": "synthetic-reference-adapter-example",
        "adapter_revision": "example-r1",
    },
    "source_retention": {
        "stable_locator": (
            "synthetic://reference-collection-01/item-0007@r3"
        ),
        "locator_scope": "local illustrative data",
        "externally_retrievable": False,
        "source_revision": "r3",
        "retained_source_fields": {
            "heading": "Review date update",
            "review_date": "2026-06-20",
            "layout_hint": "compact",
        },
    },
    "source_shape": {
        "source_record_kind": "reference_note_record",
        "source_field_names": [
            "heading",
            "review_date",
            "layout_hint",
        ],
    },
    "normalized_view": {
        "title": "Review date update",
        "stated_date": "2026-06-20",
    },
    "translation_decisions": [
        {
            "source_location": "external_item",
            "consumer_location": "provenance + source_retention",
            "transformation": (
                "retain the source item and revision through "
                "provenance and source-retention entries"
            ),
            "reason": (
                "preserve a reviewable trace path back to the "
                "synthetic source item"
            ),
        },
        {
            "source_location": "external_item.heading",
            "consumer_location": "normalized_view.title",
            "transformation": "rename heading to title",
            "reason": (
                "consumer-side review uses the term title; "
                "the source value is unchanged"
            ),
        },
        {
            "source_location": "external_item.review_date",
            "consumer_location": "normalized_view.stated_date",
            "transformation": "rename review_date to stated_date",
            "reason": (
                "consumer-side review uses the term stated_date "
                "to mark this as a date explicitly stated by the "
                "source, not a derived value"
            ),
        },
        {
            "source_location": "external_item.layout_hint",
            "consumer_location": "normalized_view (absent)",
            "transformation": (
                "omit layout_hint from normalized_view; preserve "
                "it inside source_retention.retained_source_fields"
            ),
            "reason": (
                "layout_hint is a source-only presentation hint; "
                "it is not part of the normalized consumer view, "
                "but its source value remains preserved"
            ),
        },
        {
            "source_location": "interpretation_context.question",
            "consumer_location": "consumer_handoff",
            "transformation": (
                "treat the assignment as unresolved because the "
                "source does not state a reason for the changed "
                "date"
            ),
            "reason": (
                "ambiguity must be preserved rather than filled "
                "with a fabricated reason"
            ),
        },
    ],
    "loss_notes": [
        {
            "kind": "normalized-view omission",
            "source_field": "layout_hint",
            "normalized_treatment": "omitted from normalized_view",
            "source_retention": (
                "preserved in source_retention.retained_source_fields"
            ),
            "reason": "source-only presentation hint",
        },
    ],
    "derivation_notes": {
        "derived_values_created": False,
        "note": (
            "stated_date is a renamed retained value, not a "
            "calculated or inferred value; no reason for the "
            "date change is invented"
        ),
    },
    "interpretation_context": {
        "question": "Why was the review date changed?",
        "intended_consumer": "consumer-side review logic",
        "review_purpose": (
            "decide whether additional context is needed before "
            "the changed date can be interpreted"
        ),
    },
    "consumer_handoff": {
        "contextual_primary_role": None,
        "local_candidate_roles": [
            "example:knowledge-reference",
            "example:missing-information-signal",
        ],
        "local_candidate_roles_note": (
            "local_candidate_roles is illustrative local data. "
            "It is not a framework registry, an enum, or a "
            "framework role vocabulary. The candidates are not "
            "automatically selected. The handoff remains "
            "unresolved until additional context arrives."
        ),
        "permitted_consumer_uses": [
            "display the explicitly stated date as background "
            "context during review",
            "request an additional source that states the reason",
        ],
        "blocked_consumer_uses": [
            "promote the normalized date as verified Engine truth",
            "add Engine evidence automatically",
            "register a Claim automatically",
            "change lifecycle state",
            "execute a tool",
            "publish a final judgment",
            "bypass consumer or operator review",
            "infer the unstated reason for the changed date",
            "select a candidate role automatically",
            "convert ambiguity into numerical confidence",
            "treat LLM wording as source evidence",
        ],
    },
    "unresolved_information": (
        "The external item states a date but does not state why "
        "it changed. The reason cannot be derived from the "
        "retained source fields, and no surrounding interpretation "
        "context provides one."
    ),
    "traceability": {
        "translation_run_reference": (
            "translation-run-unresolved-0002"
        ),
        "provenance_summary": (
            "synthetic-reference-collection-01 / item-0007 @ r3 / "
            "via synthetic-reference-adapter-example example-r1"
        ),
        "interpretation_summary": (
            "unresolved reading; contextual primary role is "
            "withheld pending additional context"
        ),
    },
}


if __name__ == "__main__":
    print("=== Resolved external-adapter translation trace ===")
    pprint(RESOLVED_TRANSLATION_TRACE, sort_dicts=False, width=88)
    print()
    print("=== Unresolved external-adapter translation trace ===")
    pprint(UNRESOLVED_TRANSLATION_TRACE, sort_dicts=False, width=88)
