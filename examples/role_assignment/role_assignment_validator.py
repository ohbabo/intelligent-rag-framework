"""Role assignment boundary validator (MVP).

This validator targets the local illustrative representation
introduced by PR61. Its required keys are local validation inputs,
not canonical framework fields. Other consumers may use different
representations while preserving the PR59 and PR60 policy
boundaries.

The validator accepts additional consumer-defined keys. It does not
require an exact closed dictionary shape.

The validator checks representational boundaries. It does not
determine whether a semantic role is correct.

Passing validation means structurally non-contradictory under this
local example representation. It does not mean true, verified, safe
for execution, or accepted by the Engine.
"""


_CODE_ORDER = (
    "RA1", "RA2", "RA3", "RA4", "RA5",
    "RA6", "RA7", "RA8", "RA9", "RA10",
)

_LOCAL_REQUIRED_KEYS = (
    "data_item",
    "provenance",
    "record_shape",
    "interpretation_context",
    "assignment_basis",
    "primary_role",
    "secondary_roles",
    "allowed_uses",
    "forbidden_uses",
    "traceability",
)

_DICT_FIELDS = (
    "data_item",
    "provenance",
    "interpretation_context",
    "traceability",
)

_NON_EMPTY_STR_FIELDS = (
    "record_shape",
    "assignment_basis",
)

_LIST_FIELDS = (
    "secondary_roles",
)

_SECONDARY_REQUIRED_FIELDS = (
    "label",
    "justification",
    "meaning_distinct_from_primary",
    "allowed_uses",
    "forbidden_uses",
    "non_contradiction_with_primary",
    "no_downstream_authorization",
)

_SECONDARY_EXPLANATORY_FIELDS = (
    "justification",
    "meaning_distinct_from_primary",
    "non_contradiction_with_primary",
    "no_downstream_authorization",
)

_EXAMPLE_PREFIX = "example:"


def _is_non_empty_string(value):
    return isinstance(value, str) and value.strip() != ""


def _has_example_prefix(value):
    return (
        value.startswith(_EXAMPLE_PREFIX)
        and value[len(_EXAMPLE_PREFIX):].strip() != ""
    )


def _normalize_use_text(value):
    return " ".join(value.split()).casefold()


def _check_use_list(value, label, require_non_empty, buckets):
    if not isinstance(value, list):
        buckets["RA7"].append(("RA7", f"{label} must be a list"))
        return
    if require_non_empty and len(value) == 0:
        buckets["RA7"].append(
            ("RA7", f"{label} must contain at least one non-empty string")
        )
        return
    for idx, item in enumerate(value):
        if not isinstance(item, str) or item.strip() == "":
            buckets["RA7"].append(
                ("RA7", f"{label}[{idx}] must be a non-empty string")
            )


def _check_use_overlap(allowed, forbidden, scope, buckets):
    if not isinstance(allowed, list) or not isinstance(forbidden, list):
        return
    allowed_norms = set()
    for item in allowed:
        if isinstance(item, str) and item.strip() != "":
            allowed_norms.add(_normalize_use_text(item))
    forbidden_norms = set()
    for item in forbidden:
        if isinstance(item, str) and item.strip() != "":
            forbidden_norms.add(_normalize_use_text(item))
    overlap = sorted(allowed_norms & forbidden_norms)
    for normalized in overlap:
        buckets["RA8"].append(
            (
                "RA8",
                f"{scope} allowed_uses and forbidden_uses overlap on "
                f"normalized text: {normalized!r}",
            )
        )


def _assemble(buckets):
    out = []
    for code in _CODE_ORDER:
        out.extend(buckets[code])
    return out


def validate_role_assignment_boundaries(
    assignment: object,
) -> list[tuple[str, str]]:
    buckets = {code: [] for code in _CODE_ORDER}

    # RA1 — top-level shape
    if not isinstance(assignment, dict):
        buckets["RA1"].append(("RA1", "assignment is not a plain dict"))
        return _assemble(buckets)

    # RA2 — required local field missing
    for key in _LOCAL_REQUIRED_KEYS:
        if key not in assignment:
            buckets["RA2"].append(
                ("RA2", f"required local field missing: {key}")
            )

    # RA3 — container / scalar shape (only for present required fields)
    for field in _DICT_FIELDS:
        if field in assignment and not isinstance(assignment[field], dict):
            buckets["RA3"].append(("RA3", f"{field} must be a dict"))
    for field in _NON_EMPTY_STR_FIELDS:
        if field in assignment and not _is_non_empty_string(assignment[field]):
            buckets["RA3"].append(
                ("RA3", f"{field} must be a non-empty string")
            )
    for field in _LIST_FIELDS:
        if field in assignment and not isinstance(assignment[field], list):
            buckets["RA3"].append(("RA3", f"{field} must be a list"))

    # RA4 — primary_role shape (None or non-empty string)
    if "primary_role" in assignment:
        pr = assignment["primary_role"]
        if pr is None:
            pass
        elif isinstance(pr, str):
            if pr.strip() == "":
                buckets["RA4"].append(
                    ("RA4", "primary_role must be None or a non-empty string")
                )
        else:
            buckets["RA4"].append(
                ("RA4", "primary_role must be None or a non-empty string")
            )

    # RA5 — role-bearing label shape and 'example:' prefix
    # Targets: primary_role / secondary_roles[*].label / candidate_roles[*]
    if "primary_role" in assignment:
        pr = assignment["primary_role"]
        # primary_role None is valid; non-string/empty shape is RA4 territory.
        # RA5 fires only on shape-valid strings that lack a non-empty
        # 'example:' suffix.
        if (
            isinstance(pr, str)
            and pr.strip() != ""
            and not _has_example_prefix(pr)
        ):
            buckets["RA5"].append(
                (
                    "RA5",
                    "primary_role must use 'example:' prefix with a "
                    "non-empty suffix",
                )
            )

    if "secondary_roles" in assignment and isinstance(
        assignment["secondary_roles"], list
    ):
        for idx, entry in enumerate(assignment["secondary_roles"]):
            if isinstance(entry, dict) and "label" in entry:
                label = entry["label"]
                if not isinstance(label, str) or label.strip() == "":
                    buckets["RA5"].append(
                        (
                            "RA5",
                            f"secondary_roles[{idx}].label must be a "
                            f"non-empty string",
                        )
                    )
                elif not _has_example_prefix(label):
                    buckets["RA5"].append(
                        (
                            "RA5",
                            f"secondary_roles[{idx}].label must use "
                            f"'example:' prefix with a non-empty suffix",
                        )
                    )

    if "candidate_roles" in assignment and isinstance(
        assignment["candidate_roles"], list
    ):
        for idx, item in enumerate(assignment["candidate_roles"]):
            if not isinstance(item, str) or item.strip() == "":
                buckets["RA5"].append(
                    (
                        "RA5",
                        f"candidate_roles[{idx}] must be a non-empty string",
                    )
                )
            elif not _has_example_prefix(item):
                buckets["RA5"].append(
                    (
                        "RA5",
                        f"candidate_roles[{idx}] must use 'example:' prefix "
                        f"with a non-empty suffix",
                    )
                )

    # RA6 — secondary role boundary entry malformed
    if "secondary_roles" in assignment and isinstance(
        assignment["secondary_roles"], list
    ):
        for idx, entry in enumerate(assignment["secondary_roles"]):
            if not isinstance(entry, dict):
                buckets["RA6"].append(
                    ("RA6", f"secondary_roles[{idx}] must be a dict")
                )
                continue
            for field in _SECONDARY_REQUIRED_FIELDS:
                if field not in entry:
                    buckets["RA6"].append(
                        (
                            "RA6",
                            f"secondary_roles[{idx}] missing field: {field}",
                        )
                    )
            for field in _SECONDARY_EXPLANATORY_FIELDS:
                if field in entry and not _is_non_empty_string(entry[field]):
                    buckets["RA6"].append(
                        (
                            "RA6",
                            f"secondary_roles[{idx}].{field} must be a "
                            f"non-empty string",
                        )
                    )

    # RA7 — use list shape + ForbiddenUse non-empty
    if "allowed_uses" in assignment:
        _check_use_list(
            assignment["allowed_uses"],
            label="allowed_uses",
            require_non_empty=False,
            buckets=buckets,
        )
    if "forbidden_uses" in assignment:
        _check_use_list(
            assignment["forbidden_uses"],
            label="forbidden_uses",
            require_non_empty=True,
            buckets=buckets,
        )
    if "secondary_roles" in assignment and isinstance(
        assignment["secondary_roles"], list
    ):
        for idx, entry in enumerate(assignment["secondary_roles"]):
            if not isinstance(entry, dict):
                continue
            if "allowed_uses" in entry:
                _check_use_list(
                    entry["allowed_uses"],
                    label=f"secondary_roles[{idx}].allowed_uses",
                    require_non_empty=False,
                    buckets=buckets,
                )
            if "forbidden_uses" in entry:
                _check_use_list(
                    entry["forbidden_uses"],
                    label=f"secondary_roles[{idx}].forbidden_uses",
                    require_non_empty=True,
                    buckets=buckets,
                )

    # RA8 — exact normalized use conflict
    if "allowed_uses" in assignment and "forbidden_uses" in assignment:
        _check_use_overlap(
            assignment["allowed_uses"],
            assignment["forbidden_uses"],
            scope="top-level",
            buckets=buckets,
        )
    if "secondary_roles" in assignment and isinstance(
        assignment["secondary_roles"], list
    ):
        for idx, entry in enumerate(assignment["secondary_roles"]):
            if not isinstance(entry, dict):
                continue
            au = entry.get("allowed_uses")
            fu = entry.get("forbidden_uses")
            if au is not None and fu is not None:
                _check_use_overlap(
                    au,
                    fu,
                    scope=f"secondary_roles[{idx}]",
                    buckets=buckets,
                )

    # RA9 — resolved / unresolved structural conflicts
    pr = assignment.get("primary_role")
    cr = assignment.get("candidate_roles")
    sr = assignment.get("secondary_roles")

    # Conflict A
    if (
        isinstance(pr, str)
        and pr.strip() != ""
        and isinstance(cr, list)
        and len(cr) > 0
    ):
        buckets["RA9"].append(
            (
                "RA9",
                "primary_role coexists with non-empty candidate_roles",
            )
        )

    # Conflict B
    if pr is None and isinstance(sr, list) and len(sr) > 0:
        buckets["RA9"].append(
            (
                "RA9",
                "primary_role is None but secondary_roles is non-empty",
            )
        )

    # Conflict C
    if isinstance(pr, str) and pr.strip() != "" and isinstance(sr, list):
        for idx, entry in enumerate(sr):
            if isinstance(entry, dict):
                lbl = entry.get("label")
                if isinstance(lbl, str) and lbl == pr:
                    buckets["RA9"].append(
                        (
                            "RA9",
                            f"secondary_roles[{idx}].label equals primary_role",
                        )
                    )

    # Conflict D
    if isinstance(sr, list):
        seen = {}
        for idx, entry in enumerate(sr):
            if isinstance(entry, dict):
                lbl = entry.get("label")
                if isinstance(lbl, str) and lbl.strip() != "":
                    if lbl in seen:
                        buckets["RA9"].append(
                            (
                                "RA9",
                                f"secondary_roles[{idx}].label duplicates "
                                f"secondary_roles[{seen[lbl]}].label",
                            )
                        )
                    else:
                        seen[lbl] = idx

    # RA10 — candidate_roles container + duplicates
    if "candidate_roles" in assignment:
        cr_field = assignment["candidate_roles"]
        if not isinstance(cr_field, list):
            buckets["RA10"].append(
                ("RA10", "candidate_roles must be a list")
            )
        else:
            seen = {}
            for idx, item in enumerate(cr_field):
                if isinstance(item, str) and item.strip() != "":
                    if item in seen:
                        buckets["RA10"].append(
                            (
                                "RA10",
                                f"candidate_roles[{idx}] duplicates "
                                f"candidate_roles[{seen[item]}]",
                            )
                        )
                    else:
                        seen[item] = idx

    return _assemble(buckets)
