"""Prompt 1 graph adapter acceptance; no source-analysis algorithms added."""
from collections import OrderedDict
from pathlib import Path

import networkx as nx
import numpy as np
import pytest
import torch

from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
from sco_models import graph_utils as gu
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.state.stage_f.model_adapter import build_dgl as frozen_build_dgl
from scripts.DFG.dfg_v2 import (
    DATA_DEF_USE, ENV_FLOW, ENV_SOURCE, FORWARD_RELATIONS, PROFILES,
    READS_STATE, REVERSE_OF, WRITES_STATE,
)
from scripts.DFG.dfg_v2.model_input import build_dgl, edge_data, materialize


@pytest.fixture
def hcg():
    source = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "minimal.sol"
    graph = nx.MultiDiGraph(generate_cfg_from_source(source.read_text(), "minimal.sol"))
    for _, attrs in graph.nodes(data=True):
        attrs["token"] = np.zeros(512, dtype=np.float32)
        attrs["node_info_vulnerabilities"] = None
    return gu.add_hetero_ids(graph)


def _same_tensors(first, second):
    assert list(first) == list(second)
    for canonical in first:
        assert len(first[canonical]) == len(second[canonical]) == 2
        assert all(torch.equal(a, b) for a, b in zip(first[canonical], second[canonical]))


def _endpoints(graph, relation):
    return {c: tuple(t.tolist() for t in pair)
            for c, pair in graph.items() if c[1] == relation}


def _add_scalar_edges(graph):
    exprs = [n for n, d in graph.nodes(data=True) if d["node_type"] == "expression_statement"]
    variable = next(n for n, d in graph.nodes(data=True) if d["node_type"] == "new_variable")
    assert len(exprs) >= 2
    graph.add_edge(exprs[0], exprs[1], edge_type=DATA_DEF_USE)
    graph.add_edge(variable, exprs[0], edge_type=DATA_DEF_USE)
    return exprs, variable


def test_g0_preserves_original_canonical_order_tensors_and_graph(hcg):
    before = fingerprint(hcg)
    direct = gu.generate_hetero_graph_data(hcg)
    _same_tensors(edge_data(hcg), direct)
    _same_tensors(materialize(edge_data(hcg), "G0"), gu.reflect_graph(direct))
    actual, ids = build_dgl(hcg, "G0")
    frozen, frozen_ids = frozen_build_dgl(hcg)
    assert actual.canonical_etypes == frozen.canonical_etypes
    assert actual.ntypes == frozen.ntypes
    assert ids == frozen_ids
    for typ in actual.ntypes:
        assert actual.num_nodes(typ) == frozen.num_nodes(typ)
    for canonical in actual.canonical_etypes:
        assert all(torch.equal(a, b) for a, b in zip(
            actual.edges(etype=canonical, order="eid"), frozen.edges(etype=canonical, order="eid")))
    assert fingerprint(hcg) == before


def test_g1_same_and_different_type_def_use_remain_forward(hcg):
    _add_scalar_edges(hcg)
    before = fingerprint(hcg)
    raw = edge_data(hcg)
    out = materialize(raw, "G1")
    assert _endpoints(out, DATA_DEF_USE) == _endpoints(raw, DATA_DEF_USE)
    assert sum(len(pair[0]) for c, pair in out.items() if c[1] == DATA_DEF_USE) == 2
    assert ("expression_statement", DATA_DEF_USE, "new_variable") not in out
    ordinary = {c: values for c, values in raw.items() if c[1] != DATA_DEF_USE}
    reflected = gu.reflect_graph(ordinary)
    _same_tensors({c: values for c, values in out.items() if c[1] != DATA_DEF_USE}, reflected)
    build_dgl(hcg, "G1")
    assert fingerprint(hcg) == before


def test_g3r_explicit_reverse_for_each_forward_canonical_without_source_edits(hcg):
    exprs, var = _add_scalar_edges(hcg)
    hcg.add_edge(exprs[0], var, edge_type=WRITES_STATE)
    hcg.add_edge(var, exprs[1], edge_type=READS_STATE)
    hcg.add_node("environment", node_type=ENV_SOURCE, node_hetero_id=0,
                 token=np.zeros(512, dtype=np.float32), source_file="minimal.sol",
                 node_info_vulnerabilities=None)
    hcg.add_edge("environment", exprs[0], edge_type=ENV_FLOW)
    before = fingerprint(hcg)
    forward = materialize(edge_data(hcg), "G3")
    reversed_data = materialize(edge_data(hcg), "G3R")
    assert {c[1] for c in forward if c[1] in FORWARD_RELATIONS} == FORWARD_RELATIONS
    assert not any(c[1].startswith("REV_") for c in forward)
    for canonical, pair in forward.items():
        assert all(torch.equal(a, b) for a, b in zip(pair, reversed_data[canonical]))
        if canonical[1] in FORWARD_RELATIONS:
            reverse = (canonical[2], REVERSE_OF[canonical[1]], canonical[0])
            assert all(torch.equal(a, b) for a, b in zip(
                reversed_data[reverse], (pair[1], pair[0])))
    model_graph, local_ids = build_dgl(hcg, "G3R")
    assert model_graph.num_nodes(ENV_SOURCE) == 1
    assert local_ids["environment"] == 0
    assert len(model_graph.canonical_etypes) == len(reversed_data)
    assert fingerprint(hcg) == before


@pytest.mark.parametrize("profile,relation", [
    ("G0", DATA_DEF_USE), ("G0", WRITES_STATE), ("G1", READS_STATE),
    ("G1", WRITES_STATE), ("G2", ENV_FLOW),
])
def test_relation_disallowed_by_profile_is_rejected(profile, relation):
    with pytest.raises(ValueError, match="not allowed"):
        materialize({("statement", relation, "statement"): (torch.tensor([0]), torch.tensor([1]))}, profile)


@pytest.mark.parametrize("profile", list(PROFILES))
def test_networkx_cannot_supply_explicit_reverse(profile):
    for reverse in REVERSE_OF.values():
        with pytest.raises(ValueError, match="Input REV"):
            materialize({("statement", reverse, "statement"): (torch.tensor([0]), torch.tensor([1]))}, profile)


def test_canonical_collision_refuses_to_overwrite(monkeypatch):
    canonical = ("statement", DATA_DEF_USE, "statement")
    values = (torch.tensor([0]), torch.tensor([1]))
    monkeypatch.setattr(gu, "reflect_graph", lambda ordinary: {canonical: values})
    with pytest.raises(ValueError, match="Canonical collision"):
        materialize({canonical: values}, "G1")


def test_reverse_canonical_collision_refuses_to_overwrite(monkeypatch):
    canonical = ("statement", DATA_DEF_USE, "statement")
    values = (torch.tensor([0]), torch.tensor([1]))
    reverse = ("statement", REVERSE_OF[DATA_DEF_USE], "statement")
    monkeypatch.setattr(gu, "reflect_graph", lambda ordinary: {reverse: values})
    with pytest.raises(ValueError, match="Canonical collision"):
        materialize({canonical: values}, "G3R")


@pytest.mark.parametrize("profile", ["unknown", "g0", None, []])
def test_invalid_profile_fails_before_materialization(hcg, profile):
    with pytest.raises(ValueError, match="Unknown DFG"):
        materialize({}, profile)
    with pytest.raises(ValueError, match="Unknown DFG"):
        build_dgl(hcg, profile)


@pytest.mark.parametrize("profile", ["G0", "G1", "G2"])
def test_auxiliary_nodes_rejected_outside_environment_profiles(hcg, profile):
    hcg.add_node("environment", node_type=ENV_SOURCE, node_hetero_id=0)
    with pytest.raises(ValueError, match="Auxiliary nodes"):
        build_dgl(hcg, profile)


@pytest.mark.parametrize("wrong", [-1, 10, None, True])
def test_node_type_local_alignment_cannot_be_silently_repaired(hcg, wrong):
    node = next(iter(hcg))
    hcg.nodes[node]["node_hetero_id"] = wrong
    before = fingerprint(hcg)
    with pytest.raises(AssertionError, match="type-local row"):
        build_dgl(hcg, "G0")
    assert fingerprint(hcg) == before


def test_isolated_nodes_count_and_parallel_base_edges_remain(hcg):
    src, dst, data = next(iter(hcg.edges(data=True)))
    hcg.add_edge(src, dst, key="another-base", **data)
    hcg.add_node("isolated", node_type="new_variable")
    gu.add_hetero_ids(hcg)
    before = fingerprint(hcg)
    graph, ids = build_dgl(hcg, "G0")
    assert sum(graph.num_nodes(typ) for typ in graph.ntypes) == len(hcg)
    assert ids["isolated"] == hcg.nodes["isolated"]["node_hetero_id"]
    expected = gu.reflect_graph(edge_data(hcg))
    for canonical, pair in expected.items():
        assert graph.num_edges(canonical) == pair[0].numel()
    assert fingerprint(hcg) == before


@pytest.mark.parametrize("endpoints", [
    (torch.tensor([0]), torch.tensor([0, 1])),
    (torch.tensor([0.0]), torch.tensor([1.0])),
    (torch.tensor([-1]), torch.tensor([0])),
    (torch.tensor([[0]]), torch.tensor([[1]])),
])
def test_malformed_endpoints_rejected(endpoints):
    with pytest.raises(ValueError, match="Canonical"):
        materialize({("statement", DATA_DEF_USE, "statement"): endpoints}, "G1")


def test_frozen_reflector_keeps_ddg_forward_but_reflects_ordinary_same_type():
    # Approved Prompt 1 correction: the repository already contains the
    # 2026-10-12 DATA_DEF_USE exception; do not assert the pre-fix behavior.
    endpoints = (torch.tensor([0]), torch.tensor([1]))
    data = OrderedDict([
        (("statement", "next_line", "statement"), endpoints),
        (("statement", DATA_DEF_USE, "statement"), endpoints),
    ])
    actual = gu.reflect_graph(data)
    assert list(actual) == list(data)
    ordinary = actual[("statement", "next_line", "statement")]
    assert torch.equal(ordinary[0], torch.tensor([0, 1]))
    assert torch.equal(ordinary[1], torch.tensor([1, 0]))
    ddg = actual[("statement", DATA_DEF_USE, "statement")]
    assert torch.equal(ddg[0], torch.tensor([0]))
    assert torch.equal(ddg[1], torch.tensor([1]))
    # The v2 adapter preserves that fact and makes the reverse opt-in explicit.
    v2 = materialize(data, "G1")
    _same_tensors(v2, actual)
    reverse = materialize(data, "G3R")[("statement", REVERSE_OF[DATA_DEF_USE], "statement")]
    assert torch.equal(reverse[0], torch.tensor([1]))
    assert torch.equal(reverse[1], torch.tensor([0]))
