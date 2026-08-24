"""
Tests for Agent 4 (Target-Fit Analyzer): .claude/target_fit/project_tree.py
and .claude/target_fit/target_fit.py.

Standard library only (unittest), matching this repo's air-gapped-client
convention. Run with:

    python -m unittest discover -s tests -p "test_target_fit.py" -v

from the repository root.
"""
import copy
import importlib.util
import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_FIT_DIR = os.path.join(REPO_ROOT, ".claude", "target_fit")
LANGUAGES_DIR = os.path.join(TARGET_FIT_DIR, "languages")
JAVA_BANK_TREE = os.path.join(REPO_ROOT, "outputs", "java_bank", "normalized_tree.json")


def _load(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, os.path.join(REPO_ROOT, ".claude", "complexities"))
sys.path.insert(0, TARGET_FIT_DIR)
project_tree_mod = _load("project_tree", os.path.join(TARGET_FIT_DIR, "project_tree.py"))
target_fit = _load("target_fit", os.path.join(TARGET_FIT_DIR, "target_fit.py"))


def make_descriptor(**overrides):
    base = {
        "id": "testtarget", "display_name": "TestTarget",
        "supports_goto": False, "supports_alter_style_dynamic_jump": False,
        "multiple_inheritance": True, "reviewed": True, "source": "hand-authored",
    }
    base.update(overrides)
    return base


def make_unit(unit_id, cfg=None, loc=10, extra=None):
    unit = {
        "id": unit_id, "name": unit_id, "owner_type": "M",
        "loc": loc, "cfg": cfg or {"node_type": "SEQUENCE", "children": []},
    }
    if extra:
        unit.update(extra)
    return unit


class TestProjectTreeJumpConstructs(unittest.TestCase):
    def test_unit_with_unsupported_goto_is_dropped(self):
        tree = {
            "language": "cobol",
            "units": [make_unit("A", cfg={
                "node_type": "SEQUENCE",
                "children": [{"node_type": "GOTO", "line": 5, "children": []}],
            })],
        }
        descriptor = make_descriptor(supports_goto=False)
        projected, log = project_tree_mod.project_tree(tree, descriptor)
        self.assertEqual(projected["units"], [])
        self.assertEqual(len(log["units_dropped"]), 1)
        self.assertEqual(log["units_dropped"][0]["unit"], "A")
        self.assertIn("GOTO", log["units_dropped"][0]["reason"])

    def test_unit_with_goto_kept_when_target_supports_it(self):
        tree = {
            "language": "cobol",
            "units": [make_unit("A", cfg={
                "node_type": "SEQUENCE",
                "children": [{"node_type": "GOTO", "line": 5, "children": []}],
            })],
        }
        descriptor = make_descriptor(supports_goto=True)
        projected, log = project_tree_mod.project_tree(tree, descriptor)
        self.assertEqual(len(projected["units"]), 1)
        self.assertEqual(log["units_dropped"], [])

    def test_unit_with_alter_dropped_even_if_goto_supported(self):
        """ALTER is gated by its own descriptor flag, independent of goto."""
        tree = {
            "language": "cobol",
            "units": [make_unit("A", cfg={
                "node_type": "SEQUENCE",
                "children": [{"node_type": "ALTER", "line": 5, "children": []}],
            })],
        }
        descriptor = make_descriptor(supports_goto=True, supports_alter_style_dynamic_jump=False)
        projected, log = project_tree_mod.project_tree(tree, descriptor)
        self.assertEqual(projected["units"], [])
        self.assertIn("ALTER", log["units_dropped"][0]["reason"])

    def test_unit_with_no_jump_constructs_is_kept(self):
        tree = {"language": "java", "units": [make_unit("A")]}
        descriptor = make_descriptor()
        projected, log = project_tree_mod.project_tree(tree, descriptor)
        self.assertEqual(len(projected["units"]), 1)
        self.assertEqual(log["units_dropped"], [])


class TestProjectTreeVolumeFieldsStripped(unittest.TestCase):
    def test_loc_comment_lines_halstead_always_stripped(self):
        tree = {
            "language": "java",
            "units": [make_unit("A", extra={
                "comment_lines": 3, "halstead": {"volume": 100.0},
            })],
        }
        descriptor = make_descriptor()
        projected, log = project_tree_mod.project_tree(tree, descriptor)
        unit = projected["units"][0]
        self.assertNotIn("loc", unit)
        self.assertNotIn("comment_lines", unit)
        self.assertNotIn("halstead", unit)
        self.assertEqual(set(log["fields_stripped_every_unit"]), {"loc", "comment_lines", "halstead"})

    def test_no_verbosity_ratio_field_ever_applied(self):
        """The log's own KEYS must never carry a multiplier/ratio field - this
        design explicitly refuses to invent one. (The word may legitimately
        appear in prose explaining that refusal, so check key names, not
        the serialized text.)"""
        tree = {"language": "java", "units": [make_unit("A")]}
        descriptor = make_descriptor()
        _, log = project_tree_mod.project_tree(tree, descriptor)
        for key in log:
            for banned in ("ratio", "multiplier", "factor"):
                self.assertNotIn(banned, key.lower(), f"log key {key!r} suggests an invented conversion value")


class TestProjectTreeObjectModelGate(unittest.TestCase):
    def test_types_dropped_for_target_with_no_object_model(self):
        tree = {
            "language": "java",
            "units": [make_unit("A")],
            "types": [{"id": "T", "name": "T", "kind": "class", "fields": [], "methods": []}],
        }
        descriptor = make_descriptor(multiple_inheritance=None)  # e.g. COBOL
        projected, log = project_tree_mod.project_tree(tree, descriptor)
        self.assertEqual(projected["types"], [])
        self.assertTrue(log["object_model_dropped"])

    def test_types_kept_for_target_with_object_model(self):
        tree = {
            "language": "java",
            "units": [make_unit("A")],
            "types": [{"id": "T", "name": "T", "kind": "class", "fields": [], "methods": []}],
        }
        descriptor = make_descriptor(multiple_inheritance=True)
        projected, log = project_tree_mod.project_tree(tree, descriptor)
        self.assertEqual(projected["types"], tree["types"])
        self.assertFalse(log["object_model_dropped"])


class TestProjectTreeDeterminism(unittest.TestCase):
    def test_same_input_same_output(self):
        tree = {
            "language": "java",
            "units": [make_unit("A"), make_unit("B", cfg={
                "node_type": "SEQUENCE",
                "children": [{"node_type": "GOTO", "line": 1, "children": []}],
            })],
            "types": [{"id": "T", "name": "T"}],
        }
        descriptor = make_descriptor()
        p1, l1 = project_tree_mod.project_tree(copy.deepcopy(tree), descriptor)
        p2, l2 = project_tree_mod.project_tree(copy.deepcopy(tree), descriptor)
        self.assertEqual(json.dumps(p1, sort_keys=True), json.dumps(p2, sort_keys=True))
        self.assertEqual(json.dumps(l1, sort_keys=True), json.dumps(l2, sort_keys=True))

    def test_source_tree_is_never_mutated(self):
        tree = {"language": "java", "units": [make_unit("A")]}
        original = copy.deepcopy(tree)
        project_tree_mod.project_tree(tree, make_descriptor())
        self.assertEqual(tree, original)


@unittest.skipUnless(os.path.isfile(JAVA_BANK_TREE), "outputs/java_bank/normalized_tree.json not present")
class TestEndToEndJavaBank(unittest.TestCase):
    """Real run against the actual java_bank tree - the same one Agent 3 has
    already measured - via the real 20 analyzers, not a copy of their logic."""

    @classmethod
    def setUpClass(cls):
        cls.artifact, cls.results = target_fit.analyze(JAVA_BANK_TREE, "python", LANGUAGES_DIR)

    def test_twenty_analyzers_actually_ran(self):
        self.assertEqual(len(self.results), 20)
        self.assertEqual(len(self.artifact["reports"]), 20)

    def test_structural_complexity_only_needs_optional_loc_so_it_still_runs(self):
        row = next(r for r in self.artifact["reports"] if r["sno"] == 7)
        self.assertEqual(row["status"], "ok")

    def test_maintainability_requires_loc_so_it_gates_to_insufficient_input(self):
        row = next(r for r in self.artifact["reports"] if r["sno"] == 11)
        self.assertEqual(row["status"], "insufficient_input")

    def test_database_and_configuration_still_gate_same_as_source(self):
        for sno in (15, 18):
            row = next(r for r in self.artifact["reports"] if r["sno"] == sno)
            self.assertEqual(row["status"], "insufficient_input")

    def test_comparison_section_pairs_source_and_target_for_every_sno(self):
        comparison = self.artifact["comparison"]
        self.assertEqual(len(comparison), 20)
        snos = sorted(c["sno"] for c in comparison)
        self.assertEqual(snos, list(range(1, 21)))

    def test_source_baseline_auto_discovered_next_to_tree(self):
        self.assertTrue(self.artifact["source_baseline"]["available"])

    def test_cyclomatic_target_score_matches_source_baseline(self):
        """No jump constructs anywhere in java_bank, so this is a case where
        independently re-running the real analyzer against the projected
        tree should reproduce the source number - confirming the projection
        didn't corrupt anything for a clean codebase."""
        row = next(c for c in self.artifact["comparison"] if c["sno"] == 1)
        self.assertEqual(row["target_score"], row["source_score"])

    def test_no_units_dropped_for_a_fully_structured_codebase(self):
        self.assertEqual(self.artifact["projection"]["units_dropped"], [])
        self.assertEqual(
            self.artifact["projection"]["units_projected"],
            self.artifact["projection"]["units_total_source"],
        )

    def test_confidence_reduced_for_unreviewed_descriptor(self):
        if not self.artifact["descriptor_reviewed"]:
            self.assertLess(self.artifact["confidence"]["score"], 1.0)


class TestObjectModelGateEndToEnd(unittest.TestCase):
    """A target descriptor with no object model must cause Cohesion (#8) and
    Inheritance (#13) to gate to insufficient_input for real, via the
    central _core mechanism - not via a special-cased rule in Agent 4."""

    @unittest.skipUnless(os.path.isfile(JAVA_BANK_TREE), "outputs/java_bank/normalized_tree.json not present")
    def test_cobol_target_drops_types_and_gates_cohesion_and_inheritance(self):
        artifact, _ = target_fit.analyze(JAVA_BANK_TREE, "cobol", LANGUAGES_DIR)
        for sno in (8, 13):
            row = next(r for r in artifact["reports"] if r["sno"] == sno)
            self.assertEqual(row["status"], "insufficient_input")


class TestUnknownTarget(unittest.TestCase):
    def test_unknown_target_raises_system_exit_naming_available_targets(self):
        with self.assertRaises(SystemExit) as ctx:
            target_fit.find_descriptor(LANGUAGES_DIR, "ruby")
        message = str(ctx.exception)
        self.assertIn("insufficient_input", message)
        self.assertIn("ruby", message)


if __name__ == "__main__":
    unittest.main()
