"""Tests for the PR62 role assignment boundary validator MVP.

The validator targets the PR61 local illustrative representation.
These tests load both modules dynamically via importlib.util so that
no package promotion or sys.path mutation occurs. The validator
itself does not import the PR61 example module at runtime.

All tests in this file are inside a single class to keep the new
test count exactly 19 (no pytest parameterization is used).
"""

import ast
import importlib.util
from copy import deepcopy
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent
_VALIDATOR_PATH = (
    _REPO_ROOT / "examples" / "role_assignment" / "role_assignment_validator.py"
)
_EXAMPLE_PATH = (
    _REPO_ROOT / "examples" / "role_assignment" / "minimal_consumer_example.py"
)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_validator_mod = _load("pr62_validator", _VALIDATOR_PATH)
_example_mod = _load("pr61_example", _EXAMPLE_PATH)

validate = _validator_mod.validate_role_assignment_boundaries
RESOLVED = _example_mod.RESOLVED_EXAMPLE
UNRESOLVED = _example_mod.UNRESOLVED_EXAMPLE


def _codes(result):
    return [code for code, _ in result]


class TestRoleAssignmentBoundaryValidator:

    def test_01_resolved_example_returns_empty(self):
        assert validate(deepcopy(RESOLVED)) == []

    def test_02_unresolved_example_returns_empty(self):
        assert validate(deepcopy(UNRESOLVED)) == []

    def test_03_non_dict_inputs_never_raise_and_return_ra1(self):
        non_dict_inputs = [
            None,
            0,
            1,
            1.5,
            "string",
            b"bytes",
            [1, 2],
            (1, 2),
            True,
            False,
            set(),
            frozenset(),
        ]
        for inp in non_dict_inputs:
            result = validate(inp)
            assert result == [("RA1", "assignment is not a plain dict")], (
                f"unexpected result for input {inp!r}: {result!r}"
            )

    def test_04_missing_required_keys_return_ra2(self):
        required = [
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
        ]
        for key in required:
            d = deepcopy(RESOLVED)
            del d[key]
            result = validate(d)
            codes = _codes(result)
            assert codes.count("RA2") >= 1, (
                f"missing {key} did not trigger RA2"
            )
            ra2_msgs = [m for c, m in result if c == "RA2"]
            assert any(key in m for m in ra2_msgs), (
                f"RA2 messages did not mention {key}"
            )

    def test_05_invalid_container_or_scalar_shapes_return_ra3(self):
        # dict-shaped fields: non-dict value triggers RA3
        for field in (
            "data_item",
            "provenance",
            "interpretation_context",
            "traceability",
        ):
            d = deepcopy(RESOLVED)
            d[field] = "not-a-dict"
            assert "RA3" in _codes(validate(d))

        # non-empty string fields: empty/whitespace/None/wrong-type triggers RA3
        for field in ("record_shape", "assignment_basis"):
            for bad in ("", "   ", None, 0, [], {}):
                d = deepcopy(RESOLVED)
                d[field] = bad
                assert "RA3" in _codes(validate(d)), (
                    f"{field} = {bad!r} did not trigger RA3"
                )

        # list field: non-list triggers RA3
        d = deepcopy(RESOLVED)
        d["secondary_roles"] = "not-a-list"
        assert "RA3" in _codes(validate(d))

    def test_06_invalid_primary_role_shapes_return_ra4(self):
        for bad in (
            "",
            "   ",
            0,
            1,
            1.5,
            True,
            False,
            [],
            {},
            ["x"],
            ("a",),
            b"bytes",
        ):
            d = deepcopy(RESOLVED)
            d["primary_role"] = bad
            assert "RA4" in _codes(validate(d)), (
                f"primary_role = {bad!r} did not trigger RA4"
            )

    def test_07_role_bearing_labels_require_example_prefix(self):
        # primary_role without prefix
        d = deepcopy(RESOLVED)
        d["primary_role"] = "observation"
        assert "RA5" in _codes(validate(d))

        # secondary_roles[0].label without prefix
        d = deepcopy(RESOLVED)
        d["secondary_roles"][0]["label"] = "knowledge-reference"
        assert "RA5" in _codes(validate(d))

        # candidate_roles[0] without prefix
        d = deepcopy(UNRESOLVED)
        d["candidate_roles"][0] = "knowledge-reference"
        assert "RA5" in _codes(validate(d))

    def test_08_record_shape_and_source_type_are_not_role_labels(self):
        d = deepcopy(RESOLVED)
        d["record_shape"] = "document_record"
        d["provenance"]["source_type"] = "external_document_collection"
        # Non-role-bearing fields without example: prefix must NOT fire RA5.
        # All other fields remain valid, so the full result is [].
        assert validate(d) == []

    def test_09_malformed_candidate_roles_container_returns_ra10(self):
        d = deepcopy(UNRESOLVED)
        d["candidate_roles"] = "not-a-list"
        codes = _codes(validate(d))
        assert "RA10" in codes
        # cascade suppression: per-item label / duplicate checks must not fire
        ra5_msgs = [m for c, m in validate(d) if c == "RA5"]
        assert all("candidate_roles" not in m for m in ra5_msgs)

    def test_10_duplicate_candidate_labels_return_ra10(self):
        d = deepcopy(UNRESOLVED)
        d["candidate_roles"] = ["example:foo", "example:foo"]
        assert "RA10" in _codes(validate(d))

    def test_11_missing_secondary_boundary_fields_return_ra6(self):
        required_secondary = [
            "label",
            "justification",
            "meaning_distinct_from_primary",
            "allowed_uses",
            "forbidden_uses",
            "non_contradiction_with_primary",
            "no_downstream_authorization",
        ]
        for field in required_secondary:
            d = deepcopy(RESOLVED)
            del d["secondary_roles"][0][field]
            codes = _codes(validate(d))
            assert "RA6" in codes, (
                f"missing secondary field {field!r} did not trigger RA6"
            )

    def test_12_invalid_secondary_explanatory_fields_return_ra6(self):
        explanatory = [
            "justification",
            "meaning_distinct_from_primary",
            "non_contradiction_with_primary",
            "no_downstream_authorization",
        ]
        for field in explanatory:
            for bad in ("", "   ", None, 0, [], {}, 1.5):
                d = deepcopy(RESOLVED)
                d["secondary_roles"][0][field] = bad
                codes = _codes(validate(d))
                assert "RA6" in codes, (
                    f"secondary {field} = {bad!r} did not trigger RA6"
                )

    def test_13_top_level_use_lists_return_ra7(self):
        # allowed_uses not a list
        d = deepcopy(RESOLVED)
        d["allowed_uses"] = "not-a-list"
        assert "RA7" in _codes(validate(d))

        # allowed_uses contains non-string
        d = deepcopy(RESOLVED)
        d["allowed_uses"] = [1, 2]
        assert "RA7" in _codes(validate(d))

        # allowed_uses contains empty string
        d = deepcopy(RESOLVED)
        d["allowed_uses"] = ["", "valid"]
        assert "RA7" in _codes(validate(d))

        # allowed_uses empty list is allowed (consumer may permit nothing)
        d = deepcopy(RESOLVED)
        d["allowed_uses"] = []
        assert validate(d) == []

        # forbidden_uses not a list
        d = deepcopy(RESOLVED)
        d["forbidden_uses"] = "not-a-list"
        assert "RA7" in _codes(validate(d))

        # forbidden_uses empty list violates the explicit-prohibition rule
        d = deepcopy(RESOLVED)
        d["forbidden_uses"] = []
        assert "RA7" in _codes(validate(d))

        # forbidden_uses with empty string item
        d = deepcopy(RESOLVED)
        d["forbidden_uses"] = ["", "real"]
        assert "RA7" in _codes(validate(d))

    def test_14_secondary_use_lists_return_ra7(self):
        # secondary allowed_uses not a list
        d = deepcopy(RESOLVED)
        d["secondary_roles"][0]["allowed_uses"] = "not-a-list"
        assert "RA7" in _codes(validate(d))

        # secondary forbidden_uses empty list
        d = deepcopy(RESOLVED)
        d["secondary_roles"][0]["forbidden_uses"] = []
        assert "RA7" in _codes(validate(d))

        # secondary forbidden_uses contains non-string
        d = deepcopy(RESOLVED)
        d["secondary_roles"][0]["forbidden_uses"] = [123]
        assert "RA7" in _codes(validate(d))

        # secondary allowed_uses contains empty whitespace string
        d = deepcopy(RESOLVED)
        d["secondary_roles"][0]["allowed_uses"] = ["   "]
        assert "RA7" in _codes(validate(d))

    def test_15_top_level_use_overlap_returns_ra8(self):
        d = deepcopy(RESOLVED)
        d["allowed_uses"] = ["display review"]
        d["forbidden_uses"] = [
            "Display   Review",
            "another forbidden item",
        ]
        codes = _codes(validate(d))
        assert "RA8" in codes
        # cascade-aware: when allowed_uses is not a list, RA8 must NOT fire
        d2 = deepcopy(RESOLVED)
        d2["allowed_uses"] = "not-a-list"
        assert "RA8" not in _codes(validate(d2))

    def test_16_secondary_use_overlap_returns_ra8(self):
        d = deepcopy(RESOLVED)
        d["secondary_roles"][0]["allowed_uses"] = ["display note"]
        d["secondary_roles"][0]["forbidden_uses"] = [
            "display   note",
            "another item",
        ]
        codes = _codes(validate(d))
        assert "RA8" in codes
        # cascade-aware: when secondary allowed_uses is missing, secondary RA8
        # must not fire for that entry.
        d2 = deepcopy(RESOLVED)
        del d2["secondary_roles"][0]["allowed_uses"]
        codes2 = _codes(validate(d2))
        # RA6 may fire (missing required field), but no secondary RA8 message
        ra8_msgs = [m for c, m in validate(d2) if c == "RA8"]
        assert all("secondary_roles[0]" not in m for m in ra8_msgs)

    def test_17_resolved_unresolved_structural_conflicts_return_ra9(self):
        # Conflict A — primary_role string coexists with non-empty candidate_roles
        d_a = deepcopy(RESOLVED)
        d_a["candidate_roles"] = ["example:foo"]
        assert "RA9" in _codes(validate(d_a))

        # Conflict B — primary_role is None but secondary_roles non-empty
        d_b = deepcopy(UNRESOLVED)
        d_b["secondary_roles"] = [{
            "label": "example:foo",
            "justification": "x",
            "meaning_distinct_from_primary": "x",
            "allowed_uses": ["a single allowed item"],
            "forbidden_uses": ["a single forbidden item"],
            "non_contradiction_with_primary": "x",
            "no_downstream_authorization": "x",
        }]
        assert "RA9" in _codes(validate(d_b))

        # Conflict C — primary_role label equals a secondary role label
        d_c = deepcopy(RESOLVED)
        d_c["secondary_roles"][0]["label"] = d_c["primary_role"]
        assert "RA9" in _codes(validate(d_c))

        # Conflict D — duplicate secondary role labels
        d_d = deepcopy(RESOLVED)
        d_d["secondary_roles"].append(deepcopy(d_d["secondary_roles"][0]))
        assert "RA9" in _codes(validate(d_d))

    def test_18_extra_keys_free_text_no_mutation_deterministic(self):
        # Extra top-level keys are accepted
        d_extra = deepcopy(RESOLVED)
        d_extra["extra_consumer_field"] = "anything"
        d_extra["another_extra"] = {"nested": "data"}
        d_extra["yet_another"] = [1, 2, 3]
        assert validate(d_extra) == []

        # Arbitrary free-text replacement in free-text positions
        # remains structurally valid (no semantic analysis)
        d_text = deepcopy(RESOLVED)
        d_text["assignment_basis"] = "completely different free text"
        d_text["interpretation_context"]["question"] = (
            "another free-text question"
        )
        d_text["data_item"]["content_summary"] = "alternate summary"
        d_text["secondary_roles"][0]["justification"] = "alt"
        d_text["secondary_roles"][0]["meaning_distinct_from_primary"] = "alt"
        d_text["secondary_roles"][0]["non_contradiction_with_primary"] = "alt"
        d_text["secondary_roles"][0]["no_downstream_authorization"] = "alt"
        d_text["traceability"]["assignment_basis_summary"] = "alt summary"
        d_text["resolution_note"] = "alt resolution note"
        assert validate(d_text) == []

        # Input is not mutated by the validator
        snapshot = deepcopy(RESOLVED)
        original = deepcopy(RESOLVED)
        _ = validate(original)
        assert original == snapshot

        snapshot_u = deepcopy(UNRESOLVED)
        original_u = deepcopy(UNRESOLVED)
        _ = validate(original_u)
        assert original_u == snapshot_u

        # Repeated calls return identical results (both pass and failure)
        r1 = validate(deepcopy(RESOLVED))
        r2 = validate(deepcopy(RESOLVED))
        assert r1 == r2

        d_bad = deepcopy(RESOLVED)
        del d_bad["primary_role"]
        r1b = validate(deepcopy(d_bad))
        r2b = validate(deepcopy(d_bad))
        assert r1b == r2b

    def test_19_ast_boundary_audit(self):
        src = _VALIDATOR_PATH.read_text()
        tree = ast.parse(src)

        # No ragcore imports anywhere
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "ragcore"
                    assert not alias.name.startswith("ragcore.")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert module != "ragcore"
                assert not module.startswith("ragcore.")

        # No runtime import of the PR61 example module
        forbidden_modules = {
            "minimal_consumer_example",
            "examples.role_assignment.minimal_consumer_example",
            "role_assignment.minimal_consumer_example",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden_modules
            elif isinstance(node, ast.ImportFrom):
                assert node.module not in forbidden_modules

        # No class definitions at all (excludes dataclass-class / Enum / etc.)
        for node in ast.walk(tree):
            assert not isinstance(node, ast.ClassDef)

        # Forbidden identifiers must not appear as Name or Attribute access
        forbidden_names = {
            "dataclass",
            "Enum",
            "TypedDict",
            "NamedTuple",
            "Protocol",
            "BaseModel",
            "pydantic",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                raise AssertionError(
                    f"forbidden identifier in validator: {node.id}"
                )
            if isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                raise AssertionError(
                    f"forbidden attribute in validator: {node.attr}"
                )

        # Exactly one non-private top-level function
        public_funcs = [
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]
        assert public_funcs == ["validate_role_assignment_boundaries"], (
            f"unexpected public function set: {public_funcs!r}"
        )
