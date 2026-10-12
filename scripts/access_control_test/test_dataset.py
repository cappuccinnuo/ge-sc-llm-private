"""Regression tests for categories, multi-line labels and source provenance."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_dataset import attach_labels, CATEGORY
from label_rules import verified_annotations
import networkx as nx


class SourceRangeTests(unittest.TestCase):
    def test_middle_line_is_labeled_and_other_category_is_filtered(self):
        source = "contract T {\nfunction f() {\nx();\n}\n}\n"
        g = nx.MultiDiGraph()
        g.add_node(0, code="function f() { x(); }", node_source_code_lines=[2, 3, 4])
        g.add_node(1, code="contract T {", node_source_code_lines=[1])
        rs = [{"category": CATEGORY, "lines": [3]},
              {"category": "reentrancy", "lines": [1]}]
        attach_labels(g, "T.sol", source, rs)
        self.assertEqual(g.nodes[0]["node_info_vulnerabilities"], [rs[0]])
        self.assertIsNone(g.nodes[1]["node_info_vulnerabilities"])

    def test_blank_comment_preprocessing_maps_to_original_line(self):
        source = "// header\n\ncontract T {\n    x(); // comment\n}\n"
        g = nx.MultiDiGraph()
        g.add_node(0, code="x();", node_source_code_lines=[2])
        rs = [{"category": CATEGORY, "lines": [4]}]
        attach_labels(g, "T.sol", source, rs)
        self.assertEqual(g.nodes[0]["node_source_code_lines_original"], [4])
        self.assertEqual(g.nodes[0]["node_info_vulnerabilities"], rs)

    def test_out_of_bounds_is_rejected(self):
        g = nx.MultiDiGraph()
        g.add_node(0, code="x", node_source_code_lines=[9])
        with self.assertRaises(ValueError):
            attach_labels(g, "T.sol", "x;\n", [])

    def test_same_filename_categories_do_not_overwrite_and_source_change_rejected(self):
        with tempfile.TemporaryDirectory(dir=str(HERE)) as tmp:
            base = Path(tmp)
            source, data, injection = base / "source", base / "smartbugs", base / "injection"
            for directory in [source, data / "dataset/access_control",
                              data / "dataset/reentrancy", injection]:
                directory.mkdir(parents=True, exist_ok=True)
            content = "a;\nb;\nc;\n"
            (source / "T.sol").write_text(content)
            for category in ["access_control", "reentrancy"]:
                (data / "dataset" / category / "T.sol").write_text(content)
            records = [
                {"name": "T.sol", "path": "dataset/access_control/T.sol",
                 "vulnerabilities": [{"category": CATEGORY, "lines": [2]}]},
                {"name": "T.sol", "path": "dataset/reentrancy/T.sol",
                 "vulnerabilities": [{"category": "reentrancy", "lines": [3]}]},
            ]
            meta = data / "vulnerabilities.json"
            meta.write_text(json.dumps(records))
            reader = lambda path: json.loads(path.read_text())
            annotations, _, _ = verified_annotations(
                source, ["T.sol"], meta, injection, CATEGORY, reader)
            self.assertEqual(annotations["T.sol"], records[0]["vulnerabilities"])
            (source / "T.sol").write_text("a;\nCHANGED;\nc;\n")
            with self.assertRaises(ValueError):
                verified_annotations(source, ["T.sol"], meta, injection, CATEGORY, reader)


if __name__ == "__main__":
    unittest.main()
