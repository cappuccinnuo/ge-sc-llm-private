"""Regression tests for annotation-independent node targets; Codex 2026-10-10."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import networkx as nx
from build_dataset import node_targets, structural_digest, validate_labels


class LabelPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mando_label_pipeline_test_")
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "sample.sol"
        self.source.write_text(
            "contract C {\n  uint x;\n  uint y;\n}\n", encoding="utf8")
        self.sources = {"sample.sol": self.source}
        self.annotations = {"sample.sol": [
            {"category": "access_control", "lines": [2]},
            {"category": "access_control", "lines": [3]},
        ]}

    def graph(self):
        graph = nx.MultiDiGraph()
        graph.graph["provenance"] = "fixture"
        graph.add_node(10, source_file="sample.sol",
                       node_type="new_variable",
                       label="1_ uint x;\n11-new_variable-2-2",
                       code="uint x;", node_source_code_lines=[2],
                       node_info_vulnerabilities=None,
                       preserved_metadata={"values": [1, 2, 3]})
        graph.add_node(20, source_file="sample.sol",
                       node_type="contract_declaration",
                       label="0_ contract C\n1-contract_declaration-1-4",
                       code="contract C {\n  uint x;\n  uint y;\n}",
                       node_source_code_lines=[1, 2, 3, 4],
                       node_info_vulnerabilities=[{"category": "wrong", "lines": [999]}])
        graph.add_edge(20, 10, edge_type="next", other="unchanged")
        return graph

    def targets(self, graph, annotations=None, policy="author-endpoints"):
        return node_targets(graph, self.annotations if annotations is None else annotations,
                            self.sources, "access_control", policy)

    def test_old_labels_reversed_or_malformed_do_not_change_targets_or_evidence(self):
        graph = self.graph()
        expected = self.targets(graph)
        self.assertIsNotNone(expected[0][10])
        self.assertIsNone(expected[0][20])
        reversed_graph = copy.deepcopy(graph)
        reversed_graph.nodes[10]["node_info_vulnerabilities"] = None
        reversed_graph.nodes[20]["node_info_vulnerabilities"] = [
            {"category": "access_control", "lines": [1]}]
        self.assertEqual(self.targets(reversed_graph), expected)
        malformed_graph = copy.deepcopy(graph)
        malformed_graph.nodes[10]["node_info_vulnerabilities"] = "not a Python/JSON value"
        malformed_graph.nodes[20]["node_info_vulnerabilities"] = {"garbage": object()}
        self.assertEqual(self.targets(malformed_graph), expected)

    def test_all_smartbugs_records_attached_but_evidence_lists_only_hits(self):
        targets, projected, evidence, _ = self.targets(self.graph())
        self.assertEqual(targets[10], projected["sample.sol"])
        self.assertEqual(len(targets[10]), 2)
        node_evidence = next(row for row in evidence if row["node_id"] == 10)
        self.assertEqual(node_evidence["matched_record_indices"], [0])
        self.assertEqual(node_evidence["label"], 1)
        targets[10][0]["lines"].append(999)
        self.assertEqual(projected["sample.sol"][0]["lines"], [2])
        self.assertEqual(self.annotations["sample.sol"][0]["lines"], [2])

    def test_positive_contract_without_positive_nodes_keeps_independent_label(self):
        graph = self.graph()
        graph.remove_node(10)
        entries = [{"contract_name": "sample.sol", "targets": 1}]
        frozen_entries = copy.deepcopy(entries)
        labels = validate_labels(entries, {"sample.sol"})
        targets, _, _, _ = self.targets(graph)
        self.assertFalse(any(targets.values()))
        self.assertEqual(labels, {"sample.sol": 1})
        keep = [n for n, data in graph.nodes(data=True)
                if labels[data["source_file"]] == 1]
        self.assertEqual(keep, [20])
        self.assertEqual(entries, frozen_entries)

    def test_targets_do_not_mutate_input_graph_or_other_attributes(self):
        graph = self.graph()
        before = copy.deepcopy(graph)
        frozen = structural_digest(graph)
        targets, _, _, _ = self.targets(graph)
        self.assertEqual(dict(graph.nodes(data=True)), dict(before.nodes(data=True)))
        self.assertEqual(list(graph.edges(keys=True, data=True)),
                         list(before.edges(keys=True, data=True)))
        result = graph.copy()
        for node, records in targets.items():
            result.nodes[node]["node_info_vulnerabilities"] = records
        self.assertEqual(structural_digest(result), frozen)
        self.assertIsNone(graph.nodes[10]["node_info_vulnerabilities"])

    def test_invalid_source_coordinates_raise(self):
        for label in ["1_ uint x;\n11-new_variable-2-20",
                      "1_ uint x;\n11-new_variable-0-2"]:
            graph = self.graph()
            graph.nodes[10]["label"] = label
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    self.targets(graph)
        for lines in [[], [0], [5], [[3, 2]], [True]]:
            graph = self.graph()
            graph.nodes[10]["node_source_code_lines"] = lines
            with self.subTest(lines=lines):
                with self.assertRaises(ValueError):
                    self.targets(graph, policy="source-range")

    def test_contract_label_validation_rejects_ambiguous_manifest(self):
        for entries in [
                [{"contract_name": "sample.sol", "targets": True}],
                [{"contract_name": "sample.sol", "targets": 2}],
                [{"contract_name": "other.sol", "targets": 1}],
                [{"contract_name": "sample.sol", "targets": 1},
                 {"contract_name": "sample.sol", "targets": 0}]]:
            with self.subTest(entries=entries):
                with self.assertRaises(ValueError):
                    validate_labels(entries, {"sample.sol"})


if __name__ == "__main__":
    unittest.main()
