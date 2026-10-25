"""Prompt 5.0 probe tests on synthetic graphs only; no training."""
import copy

import dgl
import numpy as np
import pytest
import torch

from sco_models.model_hgt import HGTLayer
from scripts.DFG.dfg_v2.attention_probe import (
    CONTROLS, _attention_summary, assert_reconstruction, compare_pair, recompute)


def example(incoming=True, empty_relation=False):
    data = {
        ("statement", "next_line", "statement"): ([0, 1, 2], [1, 2, 3]),
        ("state", "READS_STATE", "statement"): ([0, 0, 1], [0, 1, 3]),
        ("env_source", "ENV_FLOW", "statement"): ([0, 0, 1], [0, 1, 2]),
    }
    if incoming:
        data[("statement", "REV_ENV_FLOW", "env_source")] = ([0, 1, 2], [0, 0, 1])
        data[("condition", "REV_ENV_FLOW", "env_source")] = ([0], [1])
    if empty_relation:
        data[("state", "REV_ENV_FLOW", "env_source")] = ([], [])
    tensors = {k: (torch.tensor(v[0], dtype=torch.long),
                   torch.tensor(v[1], dtype=torch.long)) for k, v in data.items()}
    return dgl.heterograph(tensors, num_nodes_dict={
        "statement": 4, "state": 2, "condition": 1, "env_source": 3})


def layer_for(graph, norm=True):
    types = {name: i for i, name in enumerate(graph.ntypes)}
    relations = {name: i for i, name in enumerate(graph.canonical_etypes)}
    return HGTLayer(8, 8, types, relations, 2, use_norm=norm).eval()


@pytest.mark.parametrize("scale", [1., 10000.])
@pytest.mark.parametrize("norm", [False, True])
@pytest.mark.parametrize("seed", [1, 3])
def test_recompute_matches_frozen_forward_all_operations(scale, norm, seed):
    torch.manual_seed(seed)
    graph = example(empty_relation=True)
    layer = layer_for(graph, norm)
    h = {typ: torch.randn(graph.num_nodes(typ), 8) * scale for typ in graph.ntypes}
    with torch.no_grad():
        actual = layer(graph, h)
        reconstructed, traces = recompute(layer, graph, h)
    assert assert_reconstruction(reconstructed, actual["env_source"]) <= 1e-5
    assert {c[1] for c in traces} >= CONTROLS | {"REV_ENV_FLOW"}
    # Row 2 has no incoming support under any relation, exercising zero mean.
    assert torch.isfinite(reconstructed[2]).all()


def test_no_incoming_relation_uses_original_zero_message_residual():
    torch.manual_seed(4)
    graph = example(incoming=False)
    layer = layer_for(graph)
    h = {typ: torch.randn(graph.num_nodes(typ), 8) for typ in graph.ntypes}
    with torch.no_grad():
        actual = layer(graph, h)
        reconstructed, traces = recompute(layer, graph, h)
    assert not any(c[2] == "env_source" for c in traces)
    assert_reconstruction(reconstructed, actual["env_source"])


def test_recompute_does_not_modify_graph_inputs_or_parameters():
    torch.manual_seed(8)
    graph = example()
    layer = layer_for(graph)
    h = {typ: torch.randn(graph.num_nodes(typ), 8) for typ in graph.ntypes}
    graph.nodes["statement"].data["existing"] = torch.arange(4.)
    graph.edges[("state", "READS_STATE", "statement")].data["existing"] = torch.arange(3.)
    before_h = {k: v.clone() for k, v in h.items()}
    parameters = {k: v.clone() for k, v in layer.state_dict().items()}
    node_fields = {typ: {k: v.clone() for k, v in graph.nodes[typ].data.items()} for typ in graph.ntypes}
    edge_fields = {c: {k: v.clone() for k, v in graph.edges[c].data.items()} for c in graph.canonical_etypes}
    with torch.no_grad():
        recompute(layer, graph, h)
    assert all(torch.equal(before_h[k], v) for k, v in h.items())
    assert all(torch.equal(parameters[k], v) for k, v in layer.state_dict().items())
    for typ, fields in node_fields.items():
        assert set(graph.nodes[typ].data) == set(fields)
        assert all(torch.equal(graph.nodes[typ].data[k], v) for k, v in fields.items())
    for canonical, fields in edge_fields.items():
        assert set(graph.edges[canonical].data) == set(fields)
        assert all(torch.equal(graph.edges[canonical].data[k], v) for k, v in fields.items())
    assert all(p.grad is None for p in layer.parameters())


def test_probe_requires_eval_and_no_grad():
    graph = example()
    layer = layer_for(graph)
    h = {typ: torch.zeros(graph.num_nodes(typ), 8) for typ in graph.ntypes}
    with pytest.raises(ValueError, match="eval and torch.no_grad"):
        recompute(layer, graph, h)
    with torch.no_grad():
        layer.train()
        with pytest.raises(ValueError, match="eval and torch.no_grad"):
            recompute(layer, graph, h)


def test_reconstruction_guard_rejects_discrepancy_and_nonfinite():
    actual = torch.zeros(2, 4)
    with pytest.raises(AssertionError, match="differs"):
        assert_reconstruction(actual + 1e-3, actual)
    with pytest.raises(AssertionError, match="Invalid"):
        assert_reconstruction(actual + float("nan"), actual)


def test_attention_summary_separates_trivial_degree_one():
    trace = dict(canonical=("x", "REV_ENV_FLOW", "env_source"),
        source_rows=torch.tensor([0, 1, 2]), target_rows=torch.tensor([0, 0, 1]),
        attention=torch.tensor([[.999, .5], [.001, .5], [1., 1.]]),
        logits=torch.tensor([[10., 0.], [0., 0.], [2., 2.]]))
    result = _attention_summary(trace, [{"file": "a"}, {"file": "b"}])
    assert result["active_targets"] == 2
    assert result["max_weight_distribution"]["samples"] == 4
    assert result["max_weight_distribution"]["fraction_ge_099"] == .75
    assert result["multi_neighbor_max_weight_distribution"]["samples"] == 2
    assert result["multi_neighbor_max_weight_distribution"]["fraction_ge_099"] == .5
    assert result["targets"][1]["file"] == "b"


def pair_fixture():
    pair = dict(layer_index=0, key="msg.sender", files=["a", "b"], measured_max_abs_diff=0.)
    h = {"env_source": torch.zeros(2, 4), "statement": torch.tensor([
        [1., 2., 3., 4.], [9., 8., 7., 6.], [1., 2., 3., 4.], [0., 0., 0., 0.]])}
    trace = dict(canonical=("statement", "REV_ENV_FLOW", "env_source"),
        source_rows=torch.tensor([0, 1, 2, 3]), target_rows=torch.tensor([0, 0, 1, 1]),
        attention=torch.tensor([[1., 1.], [0., 0.], [1., 1.], [0., 0.]]),
        values=h["statement"].view(4, 2, 2),
        messages=torch.tensor([[[1., 2.], [3., 4.]], [[1., 2.], [3., 4.]]]))
    return pair, h, {trace["canonical"]: trace}, {
        ("a", "msg.sender"): 0, ("b", "msg.sender"): 1}, {
        "statement": [{"node": i} for i in range(4)]}


def test_pair_reports_headwise_highest_neighbor_and_actual_messages():
    pair, h, traces, hubs, nodes = pair_fixture()
    result = compare_pair(pair, traces, h, torch.ones(2, 4), hubs, nodes, 2)
    assert result["original_zero_reproduced"]
    assert result["every_supported_head_highest_neighbor_h_exact"]
    assert result["every_supported_head_highest_value_exact"]
    assert result["every_supported_head_both_max_weight_ge_099"]
    assert result["relations"][0]["heads"][0]["actual_relation_message_max_abs_diff"] == 0
    assert result["relations"][0]["heads"][0]["winners"][1]["source_identity"] == {"node": 2}


def test_unreproduced_pair_cannot_support_previous_causal_attribution():
    pair, h, traces, hubs, nodes = pair_fixture()
    actual = torch.zeros(2, 4)
    actual[1] = 1e-3
    result = compare_pair(pair, traces, h, actual, hubs, nodes, 2)
    assert not result["original_zero_reproduced"]
    assert not result["analysis_valid_for_original_pair"]
    assert "do_not_attribute" in result["interpretation"]


def test_exact_max_ties_not_silently_claimed_same_representation():
    pair, h, traces, hubs, nodes = pair_fixture()
    trace = next(iter(traces.values()))
    trace["attention"][:] = .5
    result = compare_pair(pair, traces, h, torch.ones(2, 4), hubs, nodes, 2)
    winner = result["relations"][0]["heads"][0]["winners"][0]
    assert winner["tied_edges"] == 2
    assert not winner["all_tie_source_h_identical"]
    assert not result["every_supported_head_both_max_weight_ge_099"]

def test_identical_neighbor_group_can_concentrate_without_single_edge_saturation():
    pair, h, traces, hubs, nodes = pair_fixture()
    trace = next(iter(traces.values()))
    h["statement"][1] = h["statement"][0]
    h["statement"][3] = h["statement"][2]
    trace["values"] = h["statement"].view(4, 2, 2)
    trace["attention"][:] = .5
    result = compare_pair(pair, traces, h, torch.ones(2, 4), hubs, nodes, 2)
    assert result["every_supported_head_highest_neighbor_h_exact"]
    assert not result["every_supported_head_both_max_weight_ge_099"]
    assert result["every_supported_head_equivalent_h_group_mass_ge_099"]
    assert result["every_supported_head_equivalent_value_group_mass_ge_099"]
    winner = result["relations"][0]["heads"][0]["winners"][0]
    assert winner["top_equivalent_h_group_edges"] == 2
    assert winner["top_equivalent_h_group_attention_mass"] == 1.
