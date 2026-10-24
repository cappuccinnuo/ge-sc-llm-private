"""Read-only projection audit guards; fixtures have not been solc compiled."""
import copy

import networkx as nx
import pytest

from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
from scripts.DFG.dfg_v2.l2_projection_audit import (
    _bind_l1, _tasks, assert_mapping_equal, audit_file, run, summarize,
)
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.frontend import SourceView
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration.io import sha256, write_json


def test_existing_output_is_never_overwritten(tmp_path):
    target = tmp_path/"existing"
    target.mkdir()
    sentinel = target/"keep"
    sentinel.write_text("old")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        run(target, tmp_path/"missing")
    assert sentinel.read_text() == "old"


@pytest.mark.parametrize("records", [
    [], [{"task_id": "x"}, {"task_id": "x"}],
    [{"task_id": "../x"}], [{"task_id": "x/y"}], [{"task_id": "x\\\\y"}],
])
def test_unsafe_or_duplicate_tasks_rejected(records):
    with pytest.raises(ValueError):
        _tasks(records)


def test_mapping_mismatch_cannot_be_reported_as_equal():
    source = "pragma solidity ^0.5.17; contract C { uint x; }"
    original, projection = SourceView(source, "a.sol"), ProjectionView(source, "a.sol")
    assert_mapping_equal(original, projection)
    projection.compat_ids.pop(next(iter(projection.compat_ids)))
    with pytest.raises(AssertionError, match="exact AST mapping differs"):
        assert_mapping_equal(original, projection)


def test_source_scope_failure_recovers_exact_anchors_without_mutation():
    source = "contract C { uint x; function f() public { x=1; } }"
    graph = nx.MultiDiGraph(generate_cfg_from_source(source, "a.sol"))
    before = fingerprint(graph)
    record = audit_file(graph, "a.sol", source)
    result = summarize([record])
    assert record["source_view_parity"] is None
    assert result["supported_view"]["anchors"] == 0
    assert result["projection_view"]["anchors"] == result["declarations"] == 1
    assert result["recovered_from_supported_view"][0]["file"] == "a.sol"
    assert result["anchor_gate_passed"]
    assert fingerprint(graph) == before


def test_missing_declaration_node_stays_missing_without_nearest_guess():
    source = "pragma solidity ^0.5.17; contract C { uint x; function f() public { x=1; } }"
    graph = nx.MultiDiGraph(generate_cfg_from_source(source, "a.sol"))
    declaration = next(n for n, attrs in graph.nodes(data=True) if attrs["code"] == "uint x;")
    graph.remove_node(declaration)
    result = summarize([audit_file(graph, "a.sol", source)])
    assert result["source_view_parity_files"] == 1
    assert result["projection_view"]["anchors"] == 0
    assert result["projection_missing_anchors"][0]["projection_view"]["status"] == "no_exact_hcg_node"
    assert not result["anchor_gate_passed"]


def test_bad_l1_receipt_stops_before_output_creation(tmp_path):
    l1 = tmp_path/"l1"
    l1.mkdir()
    write_json(l1/"receipt.json", {"status": "failed"})
    write_json(l1/"run_inputs.json", {})
    with pytest.raises(ValueError, match="not an accepted"):
        run(tmp_path/"out", l1)
    assert not (tmp_path/"out").exists()


def test_changed_l1_summary_sha_is_rejected(tmp_path):
    write_json(tmp_path/"summary.json", {"tasks": [{"task_id": "x"}]})
    write_json(tmp_path/"receipt.json", {
        "status": "accepted", "training_executed": False,
        "summary_sha256": "0"*64})
    write_json(tmp_path/"run_inputs.json", {})
    with pytest.raises(ValueError, match="SHA256"):
        _bind_l1(tmp_path)
