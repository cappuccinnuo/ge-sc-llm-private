"""Codex 2026-10-08: regression checks for label semantics and protected inputs."""
import sys
sys.dont_write_bytecode = True
import json
import pickle
import tempfile
import unittest
from pathlib import Path
import networkx as nx
import numpy as np
from label_rules import (
    align_graphs, author_replay, endpoints, hit_records, parse_records,
    source_replay, verify_source_pair,
)
from safe_graph import loads_graph, read_graph, write_graph, pickle as graph_pickle
from build import invariant_digest, build_line_map, preprocessed_to_original

HERE = Path(__file__).resolve().parent

def fixture_node(ast_id, line, label=None):
    return {
        "source_file": "x.sol", "node_type": "expression_statement",
        "code": "x = 1;", "label": "1_ x = 1;\n{}-expression_statement-{}-{}".format(ast_id, line, line),
        "node_source_code_lines": [[line, line]], "node_info_vulnerabilities": label,
        "token": np.array([1., 2.], dtype=np.float32),
    }

class LabelTests(unittest.TestCase):
    def test_interior_bug_matches_range_but_not_endpoints(self):
        records = [{"category": "reentrancy", "lines": [15]}]
        self.assertTrue(hit_records(list(range(10, 21)), records))
        self.assertIsNone(hit_records(endpoints([[10, 20]]), records))

    def test_author_singleton_and_pair_coordinates(self):
        self.assertEqual(endpoints([[15], [20, 23]]), [15, 20, 23])
        with self.assertRaises(ValueError):
            endpoints([[10, 11, 12]])

    def test_source_category_filter_prevents_other_bug_positive(self):
        records = [{"category": "unchecked_low_level_calls", "lines": [15]}]
        self.assertIsNone(hit_records([15], records, "reentrancy"))
        self.assertTrue(hit_records([15], records))  # deliberate author compatibility

    def test_double_quoted_author_records(self):
        records = [{"category": "reentrancy", "lines": [3]}]
        self.assertEqual(parse_records(repr(repr(records))), records)
        with self.assertRaises(ValueError):
            parse_records([{"category": "reentrancy", "lines": [-1]}])

    def test_alignment_does_not_depend_on_node_iteration_order(self):
        left, right = nx.MultiDiGraph(), nx.MultiDiGraph()
        left.add_node(0, **fixture_node(11, 1))
        left.add_node(1, **fixture_node(12, 2))
        right.add_node(91, **fixture_node(12, 2))
        right.add_node(90, **fixture_node(11, 1))
        left.add_edge(0, 1, edge_type="next")
        right.add_edge(90, 91, edge_type="next_line")
        self.assertEqual(align_graphs(left, right), {0: 90, 1: 91})
        right.add_edge(91, 90, edge_type="next_line")
        with self.assertRaises(ValueError):
            align_graphs(left, right)

    def test_ambiguous_identity_is_rejected(self):
        left, right = nx.MultiDiGraph(), nx.MultiDiGraph()
        for n in [0, 1]:
            left.add_node(n, **fixture_node(11, 1))
            right.add_node(n, **fixture_node(11, 1))
        with self.assertRaises(ValueError):
            align_graphs(left, right)

    def test_author_replay_preserves_other_category_and_checks_saved_targets(self):
        records = [{"category": "unchecked_low_level_calls", "lines": [3]}]
        left, right = nx.MultiDiGraph(), nx.MultiDiGraph()
        left.add_node(0, **fixture_node(11, 3))
        right.add_node(10, **fixture_node(11, 3, records))
        targets, _, _ = author_replay(left, right)
        self.assertEqual(targets[0], records)
        left.add_node(1, **fixture_node(12, 3))
        right.add_node(11, **fixture_node(12, 3, None))
        with self.assertRaises(ValueError):
            author_replay(left, right)

    def test_source_line_mapping_and_stale_metadata(self):
        with tempfile.TemporaryDirectory(dir=str(HERE)) as td:
            source = Path(td) / "x.sol"
            source.write_text("pragma solidity ^0.4.0;\n\n// comment\nuint x;\n")
            graph = nx.MultiDiGraph()
            data = fixture_node(11, 2)
            data["node_source_code_lines"] = [2]
            data["node_source_code_lines_original"] = [4]
            graph.add_node(0, **data)
            ann = {"x.sol": [{"category": "reentrancy", "lines": [4]}]}
            targets, _ = source_replay(graph, ann, Path(td), build_line_map, preprocessed_to_original)
            self.assertTrue(targets[0])
            graph.nodes[0]["node_source_code_lines_original"] = [3]
            with self.assertRaises(ValueError):
                source_replay(graph, ann, Path(td), build_line_map, preprocessed_to_original)

    def test_pragma_only_edits_allowed_but_annotated_edits_rejected(self):
        with tempfile.TemporaryDirectory(dir=str(HERE)) as td:
            a, b = Path(td) / "local.sol", Path(td) / "dataset.sol"
            a.write_text("pragma solidity ^0.4.0;\nx=1;\n")
            b.write_text("pragma solidity ^0.4.24;\nx=1;\n")
            self.assertEqual(verify_source_pair(a, b, {2})["comparison"], "pragma_only_same_line")
            with self.assertRaises(ValueError):
                verify_source_pair(a, b, {1})
            b.write_text("pragma solidity ^0.4.0;\nx=2;\n")
            with self.assertRaises(ValueError):
                verify_source_pair(a, b, {2})

    def test_non_label_digest_detects_feature_and_edge_changes(self):
        graph = nx.MultiDiGraph()
        graph.add_node(0, **fixture_node(11, 3))
        initial = invariant_digest(graph)
        graph.nodes[0]["node_info_vulnerabilities"] = [{"category": "reentrancy", "lines": [3]}]
        self.assertEqual(invariant_digest(graph), initial)
        graph.nodes[0]["token"] = np.array([9., 2.], dtype=np.float32)
        self.assertNotEqual(invariant_digest(graph), initial)

    def test_restricted_pickle_roundtrip_numeric_features(self):
        with tempfile.TemporaryDirectory(dir=str(HERE)) as td:
            graph = nx.MultiDiGraph()
            graph.add_node(0, **fixture_node(11, 3))
            path = Path(td) / "graph.gpickle"
            write_graph(graph, path)
            self.assertEqual(invariant_digest(graph), invariant_digest(read_graph(path)))
            with self.assertRaises(FileExistsError):
                write_graph(graph, path)

    def test_unapproved_pickle_callable_is_rejected(self):
        class Unapproved:
            def __reduce__(self):
                return eval, ("1+1",)
        with self.assertRaises(graph_pickle.UnpicklingError):
            loads_graph(pickle.dumps(Unapproved(), protocol=4))

if __name__ == "__main__":
    unittest.main()
