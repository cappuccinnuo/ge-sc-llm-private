"""Reject changed references before starting a new graph build."""
import json
import networkx as nx
import pytest
from scripts.DFG.integration.io import sha256
from scripts.DFG.integration.rebuild import rebuild, model_edges_equal


def test_rebuild_rejects_changed_reference(tmp_path):
    source = tmp_path / "manifest.json"
    source.write_text(json.dumps({"version": "author-hcg-ddg-guard-build-v1", "tasks": []}))
    (tmp_path / "manifest.seal.json").write_text(json.dumps({"sha256": sha256(source)}))
    source.write_text(source.read_text() + " ")
    with pytest.raises(ValueError, match="SHA256"):
        rebuild(source, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_rebuild_rejects_missing_seal(tmp_path):
    source = tmp_path / "manifest.json"
    source.write_text("{}")
    with pytest.raises(FileNotFoundError):
        rebuild(source, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_rebuild_rejects_missing_matrix_before_output(tmp_path):
    source = tmp_path / "manifest.json"
    source.write_text(json.dumps({"version": "author-hcg-ddg-guard-build-v1", "tasks": []}))
    (tmp_path / "manifest.seal.json").write_text(json.dumps({"sha256": sha256(source)}))
    with pytest.raises(ValueError, match="matrix"):
        rebuild(source, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_actual_adapter_edge_order_compared():
    a, b = nx.MultiDiGraph(), nx.MultiDiGraph()
    for g in (a, b):
        for node in (0, 1, 2):
            g.add_node(node, node_type="expression_statement", source_file="x.sol")
    a.add_edge(0, 1, edge_type="DATA_DEF_USE")
    a.add_edge(0, 2, edge_type="DATA_DEF_USE")
    b.add_edge(0, 2, edge_type="DATA_DEF_USE")
    b.add_edge(0, 1, edge_type="DATA_DEF_USE")
    assert model_edges_equal(a, a)
    assert not model_edges_equal(a, b)
