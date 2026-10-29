"""CPU parser/graph structure probes; not Solidity compilation tests."""
import copy
import networkx as nx
import pytest
import torch
from scripts.DFG.dfg_v2.diagnostics8c.structure import (
    canonical_counts, path_evidence, mapped_node, invocation_identity,
    dgl_reducer_evidence, model_structure)
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.projection import Projector
from scripts.DFG.frontend import walk
from scripts.DFG.dfg_v2.tests.test_l1 import graph_for, FILE


def test_counts_include_empty_relations_without_edges():
    data = {("s", "real", "t"): (torch.tensor([0]), torch.tensor([0])),
            ("s", "empty", "t"): (torch.tensor([], dtype=torch.long), torch.tensor([], dtype=torch.long))}
    rows = {r["node_type"]: r for r in canonical_counts(data, ["s", "t"])}
    assert rows["t"]["canonical_count"] == 2
    assert rows["t"]["empty_canonical_count"] == 1
    assert rows["t"]["incoming_edges"] == 1
    assert rows["s"]["canonical_count"] == 0


def test_direct_and_twohop_are_directional_and_missing_is_not_isolated():
    graph = nx.DiGraph([(1, 2), (2, 3), (1, 3)])
    graph.add_node(4)
    assert path_evidence(graph, 1, 3) == {
        "applicable": True, "direct": True, "two_hop": True, "intermediates": [2]}
    assert not path_evidence(graph, 3, 1)["two_hop"]
    assert path_evidence(graph, None, 3)["direct"] is None
    assert path_evidence(graph, 4, 3)["direct"] is False
    with pytest.raises(ValueError):
        path_evidence(graph, 99, 3)


def test_exact_modifier_identity_missing_anchor_does_not_guess_header_node():
    source = """pragma solidity ^0.5.0;
    contract A { modifier onlyOwner() { _; }
    function f() public onlyOwner { uint x=1; } }"""
    graph = graph_for(source)
    view = ProjectionView(source, FILE)
    projector = Projector(graph, view)
    inv = next(n for n in walk(view.tree.root_node) if n.type == "modifier_invocation")
    row = invocation_identity(view, projector, inv)
    assert row["binding"] == "resolved_modifier"
    assert row["definition_node_id"] is not None
    assert row["callable_node_id"] is not None
    # If a generator later supplies a real invocation, remove only its anchor
    # from this diagnostic view to assert that no nearest/header fallback occurs.
    k = view.mapping[(inv.start_byte, inv.end_byte, inv.type)]
    projector.by_ast.pop(view.compat_ids[k], None)
    assert mapped_node(view, projector, inv) is None


def test_same_name_other_contract_is_not_resolved():
    source = """pragma solidity ^0.5.0;
    contract A { modifier guard() { _; } }
    contract B { function f() public guard { uint x=1; } }"""
    graph = graph_for(source)
    view = ProjectionView(source, FILE)
    inv = next(n for n in walk(view.tree.root_node) if n.type == "modifier_invocation")
    row = invocation_identity(view, Projector(graph, view), inv)
    assert row["binding"] == "unresolved"
    assert row["definition_node_id"] is None


def test_model_materialization_is_readonly_and_keeps_node_ids():
    source = "pragma solidity ^0.5.0; contract C { function f() public { uint x=1; x++; } }"
    graph = graph_for(source)
    before = copy.deepcopy(graph)
    data, messages = model_structure(graph, "G0")
    assert list(messages) == list(graph)
    assert data
    assert list(graph.edges(keys=True, data=True)) == list(before.edges(keys=True, data=True))
    for n in graph:
        assert "node_hetero_id" not in graph.nodes[n]
        assert torch.equal(torch.tensor(graph.nodes[n]["token"]), torch.tensor(before.nodes[n]["token"]))


def test_installed_dgl_evidence_captures_real_function():
    evidence = dgl_reducer_evidence()
    assert evidence["dgl_version"] == "0.6.1"
    assert "F.stack(flist, 0)" in evidence["source"]
    assert len(evidence["file_sha256"]) == 64
