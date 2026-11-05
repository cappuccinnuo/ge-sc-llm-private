"""Unit tests for D1 bookkeeping, not new DDG semantics."""
import importlib.util
from pathlib import Path
import networkx as nx
import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("ddg_static", str(Path(__file__).with_name("static_analysis.py")))
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def graph():
    g = nx.MultiDiGraph()
    for n in range(5):
        g.add_node(n, node_type="statement", source_file="a.sol" if n < 3 else "b.sol",
                   code="a" if n in (0, 3) else "b", token=np.zeros(512, dtype=np.float32),
                   node_info_vulnerabilities=None)
    return g


def test_actual_reflector_and_forward_ddg_preserve_input():
    g = graph()
    g.add_edge(0, 1, edge_type="next")
    g.add_edge(1, 2, edge_type=m.DDG)
    before = m.fingerprint(g)
    adj, pred, counts = m.model_adjacency(g)
    assert adj[0] == {1}
    assert adj[1] == {0, 2}
    assert adj[2] == set()
    assert pred[2] == {1}
    assert m.fingerprint(g) == before
    assert counts[("statement", "next", "statement")] == 2


def test_distance_zero_one_two_long_unreachable():
    adj = {0: {1}, 1: {2}, 2: {3}, 3: set(), 4: set()}
    d = m.distances(adj, 0)
    assert d == {0: 0, 1: 1, 2: 2, 3: 3}
    assert 4 not in d
    assert m.neighborhood_two(adj, 0) == {0, 1, 2}


def test_exact_duplicates_index_train_only():
    g = graph()
    matches = dict(m.exact_duplicate_groups(g, ["a.sol"], ["b.sol"], m.code_key))
    assert matches == {3: (0,), 4: (1, 2)}
    g.nodes[3]["code"] = "val_only"
    assert dict(m.exact_duplicate_groups(g, ["a.sol"], ["b.sol"], m.code_key))[3] == ()


def test_labels_cannot_change_duplicate_lookup():
    g = graph()
    before = m.exact_duplicate_groups(g, ["a.sol"], ["b.sol"], m.feature_key)
    for n in g:
        g.nodes[n]["node_info_vulnerabilities"] = [{"category": "random"}]
    assert before == m.exact_duplicate_groups(g, ["a.sol"], ["b.sol"], m.feature_key)


def test_float_dtype_shape_checked_and_content_exact():
    g = graph()
    g.nodes[1]["token"][20] = 1
    assert m.feature_key(g.nodes[1]) != m.feature_key(g.nodes[0])
    g.nodes[1]["token"] = np.zeros(512, dtype=np.float64)
    with pytest.raises(ValueError):
        m.feature_key(g.nodes[1])


def test_overlap_is_error():
    with pytest.raises(ValueError):
        m.exact_duplicate_groups(graph(), ["a.sol"], ["a.sol"], m.code_key)


def test_edge_functions_keep_original_type_no_labels():
    g = nx.MultiDiGraph()
    g.add_node(1, source_file="a.sol", node_type="function")
    g.add_node("1", source_file="a.sol", node_type="statement")
    g.add_edge(1, "1", edge_type=m.DDG, ddg_fact_indices=[0])
    ev = [{"source": 1, "target": "1", "function": "a.sol:10"}]
    r = m.edge_functions(g, ev)
    assert r["nodes"][0]["node_id"] == 1
    assert r["nodes"][1]["node_id"] == "1"
    assert r["edges"][0]["function"] == "a.sol:10"
    g.nodes[1]["node_info_vulnerabilities"] = ["changed"]
    assert m.edge_functions(g, ev) == r


def test_edge_function_ambiguity_is_explicit():
    g = graph()
    g.add_edge(0, 1, edge_type=m.DDG, ddg_fact_indices=[0, 1])
    ev = [{"source": 0, "target": 1, "function": f} for f in ("a.sol:0", "a.sol:10")]
    r = m.edge_functions(g, ev)
    assert r["edges"][0]["function"] is None
    assert r["ambiguous_edges"] == 1
    assert r["ambiguous_nodes"] == 2


def test_inconsistent_frozen_evidence_rejected():
    g = graph()
    g.add_edge(0, 1, edge_type=m.DDG, ddg_fact_indices=[0])
    with pytest.raises(ValueError):
        m.edge_functions(g, [{"source": 1, "target": 0, "function": "a.sol:0"}])


@pytest.mark.parametrize("a,b,y,status", [(0,0,0,"both_correct"),(0,1,1,"E1_corrects"),
                                         (1,0,1,"E1_new_error"),(0,0,1,"both_wrong")])
def test_posthoc_error_classes(a,b,y,status):
    assert m.compare_status(a,b,y) == status


def test_two_layer_new_context_and_input_immutable(tmp_path):
    g = graph()
    g.add_edge(0, 1, edge_type="next")
    e = g.copy()
    e.add_edge(0, 2, edge_type=m.DDG)
    before = m.fingerprint(g)
    stats, node = m.edge_increment(g, e, "synthetic", tmp_path)
    assert stats["distance_buckets"] == {"unreachable": 1}
    assert node[2]["new_upstream_count_two"] == 2
    assert node[1]["ddg_affected_within_two"] == 0
    assert node[2]["ddg_affected_within_two"] == 1
    assert m.fingerprint(g) == before


def test_coverage_summary_csv_null_fields_not_counted_as_fallback():
    rows = [{"functions_total": 3, "functions_analyzed": 1, "functions_fallback": 2,
             "projection_fallback_reason": None, "actual_unique_ddg_edges": 2},
            {"functions_total": 1, "functions_analyzed": 1, "functions_fallback": 0,
             "projection_fallback_reason": "strict anchor rejection", "actual_unique_ddg_edges": 0}]
    result = m.coverage_summary(rows, [], [])
    assert result["counts"]["files_projection_rejected"] == 1
    assert result["counts"]["functions_fallback"] == 2
