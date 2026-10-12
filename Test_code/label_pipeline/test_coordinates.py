"""Focused provenance/coordinate regressions. Run with python -B -m unittest discover."""
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from coordinates import coordinates_for_node, graph_endpoints, preprocess_with_map

spec = importlib.util.spec_from_file_location(
    "legacy_preprocessor_for_coordinate_tests",
    str(REPO / "process_graphs/tree_sitter_codeviews/utils/preprocessor.py"))
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


class CoordinateTests(unittest.TestCase):
    def assert_legacy_text(self, source):
        actual, mapping = preprocess_with_map(source)
        expected = legacy.remove_comments("solidity", legacy.remove_empty_lines(source))
        self.assertEqual(actual, expected)
        self.assertEqual(len(mapping), len(actual.split("\n")) if actual else 0)
        return actual, mapping

    def test_comment_only_start_line_does_not_label_following_code(self):
        _, mapping = self.assert_legacy_text("/* header\n tail */ uint x;\n")
        self.assertEqual(mapping, [[2]])

    def test_block_comment_merges_only_real_code_origins(self):
        text, mapping = self.assert_legacy_text(
            "uint a; /* first\n comment only\n */ uint b;\n")
        self.assertEqual(text, "uint a;   uint b;")
        self.assertEqual(mapping, [[1, 3]])

    def test_inline_comment_keeps_code_not_comment_provenance(self):
        _, mapping = self.assert_legacy_text(
            "// comment only\nuint x; // inline\n\nuint y;\n")
        self.assertEqual(mapping, [[2], [4]])

    def test_url_and_comment_markers_inside_strings_survive(self):
        source = 'string x = "https://a/b/*x*/";\nstring y = \'// retained\';\n'
        text, mapping = self.assert_legacy_text(source)
        self.assertIn("https://a/b/*x*/", text)
        self.assertIn("// retained", text)
        self.assertEqual(mapping, [[1], [2]])

    def test_unicode_crlf_tabs_escaped_strings_and_blank_source(self):
        samples = ["", " \t\n", "//a\n/*b\nc*/\n",
                   "uint x;\r\n\r\nuint y;\r\n",
                   '\tstring s = "??\\\"//"; // comment\n',
                   'string s = "first\nsecond";\n']
        for source in samples:
            with self.subTest(source=source):
                self.assert_legacy_text(source)

    def test_ordinary_endpoint_rules_and_serialized_label(self):
        data = {"node_type": "function_definition",
                "label": "4_ function f() {}\n12-function_definition-5-20"}
        self.assertEqual(graph_endpoints(data), [5, 20])
        data["label"] = repr(data["label"])
        self.assertEqual(graph_endpoints(data), [5, 20])

    def test_synthetic_marker_is_independent_of_local_narrow_suffix(self):
        for kind in ["end_if", "end_loop"]:
            for label in ["119_ " + kind, "119_ " + kind + "-122-122"]:
                data = {"node_type": kind, "label": label,
                        "node_source_code_lines": [122],
                        "node_info_vulnerabilities": [{"lines": [999]}]}
                self.assertEqual(graph_endpoints(data), [119])
                self.assertEqual(coordinates_for_node(data, "source-range"), [122])

    def test_zero_synthetic_marker_is_explicit_legacy_coordinate(self):
        self.assertEqual(graph_endpoints({"node_type": "end_if",
                                          "label": "0_ end_if-2-2"}), [0])

    def test_source_range_flat_membership_and_nested_spans(self):
        self.assertEqual(coordinates_for_node(
            {"node_source_code_lines": [3, 5]}, "source-range"), [3, 5])
        self.assertEqual(coordinates_for_node(
            {"node_source_code_lines": "[[3, 5], [8]]"}, "source-range"), [3, 4, 5, 8])

    def test_missing_or_bad_coordinates_raise_instead_of_guessing(self):
        for value in [None, [], [0], [True], [[3, 2]], [1, [2]], [[1, 2, 3]]]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    coordinates_for_node({"node_source_code_lines": value}, "source-range")
        for data in [
                {"node_type": "if", "label": "missing suffix"},
                {"node_type": "if", "label": "1_ if\n2-if-4-3"},
                {"node_type": "if", "label": "1_ if\n2-if-0-3"},
                {"node_type": "if", "label": "1_ if\n2-return-2-3"},
                {"node_type": "end_if", "label": "end_if-2-2"},
                {"node_type": "end_if", "label": "1_ end_loop"},
                {"node_type": "end_loop", "label": "1_ end_loop-3-2"}]:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    graph_endpoints(data)
        with self.assertRaises(ValueError):
            coordinates_for_node({}, "inferred")
        with self.assertRaises(TypeError):
            preprocess_with_map(b"not decoded")
        with self.assertRaises(UnicodeEncodeError):
            preprocess_with_map("\ud800")


if __name__ == "__main__":
    unittest.main()
