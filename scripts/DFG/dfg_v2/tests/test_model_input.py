"""Prompt 1/1b graph adapter acceptance; no source-analysis algorithms added."""
from collections import OrderedDict
import importlib.util
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
    READS_STATE, REVERSE_OF, WRITES_STATE, forward_relations, has_reverse,
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


def test_g3_same_and_different_type_def_use_remain_forward(hcg):
    _add_scalar_edges(hcg)
    before = fingerprint(hcg)
    raw = edge_data(hcg)
    out = materialize(raw, "G3")
    assert _endpoints(out, DATA_DEF_USE) == _endpoints(raw, DATA_DEF_USE)
    assert sum(len(pair[0]) for c, pair in out.items() if c[1] == DATA_DEF_USE) == 2
    assert ("expression_statement", DATA_DEF_USE, "new_variable") not in out
    ordinary = {c: values for c, values in raw.items() if c[1] != DATA_DEF_USE}
    reflected = gu.reflect_graph(ordinary)
    _same_tensors({c: values for c, values in out.items() if c[1] != DATA_DEF_USE}, reflected)
    build_dgl(hcg, "G3")
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
    ("G0", DATA_DEF_USE), ("G0", WRITES_STATE), ("G1R", READS_STATE),
    ("G1R", WRITES_STATE), ("G2R", ENV_FLOW),
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
        materialize({canonical: values}, "G1R")


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


@pytest.mark.parametrize("profile", ["G0", "G1R", "G2R"])
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
        materialize({("statement", DATA_DEF_USE, "statement"): endpoints}, "G1R")


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
    v2 = materialize(data, "G3")
    _same_tensors(v2, actual)
    reverse = materialize(data, "G3R")[("statement", REVERSE_OF[DATA_DEF_USE], "statement")]
    assert torch.equal(reverse[0], torch.tensor([1]))
    assert torch.equal(reverse[1], torch.tensor([0]))


@pytest.mark.parametrize("profile", ["G1R", "G2R", "G3R"])
def test_profile_declaration_adds_every_explicit_reverse(profile):
    raw = OrderedDict()
    # Include same-type, different-type, and real opposite-direction facts.
    # No artificial reverse may merge into one of these forward canonicals.
    for relation in sorted(forward_relations(profile)):
        raw[("statement", relation, "statement")] = (torch.tensor([0, 2]), torch.tensor([1, 3]))
        raw[("statement", relation, "declaration")] = (torch.tensor([2]), torch.tensor([0]))
        raw[("declaration", relation, "statement")] = (torch.tensor([1]), torch.tensor([3]))
    out = materialize(raw, profile)
    assert len(out) == 2 * len(raw)
    for canonical, endpoints in raw.items():
        reverse = (canonical[2], REVERSE_OF[canonical[1]], canonical[0])
        assert has_reverse(profile, canonical[1])
        assert all(torch.equal(a, b) for a, b in zip(out[canonical], endpoints))
        assert all(torch.equal(a, b) for a, b in zip(out[reverse], endpoints[::-1]))
        assert out[reverse][0].numel() == endpoints[0].numel()


def test_g3_and_g3r_build_from_identical_networkx_graph(hcg):
    exprs, var = _add_scalar_edges(hcg)
    hcg.add_edge(exprs[0], var, edge_type=WRITES_STATE)
    hcg.add_edge(var, exprs[1], edge_type=READS_STATE)
    hcg.add_node("environment", node_type=ENV_SOURCE, node_hetero_id=0)
    hcg.add_edge("environment", exprs[0], edge_type=ENV_FLOW)
    before = fingerprint(hcg)
    direct, ids = build_dgl(hcg, "G3")
    reverse, reverse_ids = build_dgl(hcg, "G3R")
    assert ids == reverse_ids
    assert direct.ntypes == reverse.ntypes
    for typ in direct.ntypes:
        assert direct.num_nodes(typ) == reverse.num_nodes(typ)
    assert set(reverse.canonical_etypes) - set(direct.canonical_etypes) == {
        (c[2], REVERSE_OF[c[1]], c[0]) for c in direct.canonical_etypes
        if c[1] in FORWARD_RELATIONS}
    for canonical in direct.canonical_etypes:
        assert all(torch.equal(a, b) for a, b in zip(
            direct.edges(etype=canonical, order="eid"), reverse.edges(etype=canonical, order="eid")))
    assert fingerprint(hcg) == before


def test_frozen_reflector_merges_same_type_writes_state_directions():
    canonical = ("statement", WRITES_STATE, "statement")
    endpoints = (torch.tensor([0]), torch.tensor([1]))
    reflected = gu.reflect_graph({canonical: endpoints})
    assert list(reflected) == [canonical]
    assert torch.equal(reflected[canonical][0], torch.tensor([0, 1]))
    assert torch.equal(reflected[canonical][1], torch.tensor([1, 0]))
    # v2 retains the directed semantic fact and gives reverse messages a name.
    out = materialize({canonical: endpoints}, "G2R")
    assert torch.equal(out[canonical][0], torch.tensor([0]))
    assert torch.equal(out[canonical][1], torch.tensor([1]))
    reverse = ("statement", REVERSE_OF[WRITES_STATE], "statement")
    assert torch.equal(out[reverse][0], torch.tensor([1]))
    assert torch.equal(out[reverse][1], torch.tensor([0]))


def test_frozen_reflector_cannot_distinguish_reverse_from_real_opposite_fact():
    canonical = ("statement", WRITES_STATE, "declaration")
    opposite = ("declaration", WRITES_STATE, "statement")
    forward = (torch.tensor([0]), torch.tensor([1]))
    real_opposite = (torch.tensor([2]), torch.tensor([3]))
    reflected_one = gu.reflect_graph({canonical: forward})
    assert opposite in reflected_one
    assert torch.equal(reflected_one[opposite][0], torch.tensor([1]))
    assert torch.equal(reflected_one[opposite][1], torch.tensor([0]))
    raw = OrderedDict([(canonical, forward), (opposite, real_opposite)])
    reflected_both = gu.reflect_graph(raw)
    assert set(reflected_both) == {canonical, opposite}
    assert torch.equal(reflected_both[opposite][0], torch.tensor([1, 2]))
    assert torch.equal(reflected_both[opposite][1], torch.tensor([0, 3]))
    out = materialize(raw, "G2R")
    assert len(out) == 4
    assert all(torch.equal(a, b) for a, b in zip(out[opposite], real_opposite))
    reverse = ("declaration", REVERSE_OF[WRITES_STATE], "statement")
    assert all(torch.equal(a, b) for a, b in zip(out[reverse], forward[::-1]))


def test_profile_names_and_helpers_are_declarative(monkeypatch):
    assert list(PROFILES) == ["G0", "G1R", "G2R", "G3R", "G3"]
    assert forward_relations("G0") == frozenset()
    assert forward_relations("G1R") == frozenset({DATA_DEF_USE})
    assert forward_relations("G2R") == frozenset({DATA_DEF_USE, WRITES_STATE, READS_STATE})
    assert forward_relations("G3") == forward_relations("G3R") == FORWARD_RELATIONS
    for relation in FORWARD_RELATIONS:
        assert not has_reverse("G3", relation)
        assert has_reverse("G3R", relation)
    monkeypatch.setitem(PROFILES, "G1", frozenset({DATA_DEF_USE}))
    assert forward_relations("G1") == frozenset({DATA_DEF_USE})
    assert not has_reverse("G1", DATA_DEF_USE)
    raw = {("a", DATA_DEF_USE, "b"): (torch.tensor([0]), torch.tensor([1]))}
    _same_tensors(materialize(raw, "G1"), raw)


def test_auxiliary_permission_comes_from_env_flow_not_profile_spelling(hcg, monkeypatch):
    monkeypatch.setitem(PROFILES, "custom_environment", frozenset({ENV_FLOW}))
    hcg.add_node("environment", node_type=ENV_SOURCE, node_hetero_id=0)
    target = next(n for n in hcg if n != "environment")
    hcg.add_edge("environment", target, edge_type=ENV_FLOW)
    graph, ids = build_dgl(hcg, "custom_environment")
    assert graph.num_nodes(ENV_SOURCE) == 1
    assert ids["environment"] == 0
    assert not any(c[1].startswith("REV_") for c in graph.canonical_etypes)
    monkeypatch.setitem(PROFILES, "G3R", frozenset({DATA_DEF_USE}))
    with pytest.raises(ValueError, match="Auxiliary nodes"):
        build_dgl(hcg, "G3R")


def test_import_rejects_reverse_without_forward(tmp_path):
    # A fresh temporary module simulates an invalid declared configuration.
    # The tracked source and already-imported registry remain untouched.
    original = Path(__file__).resolve().parents[1] / "__init__.py"
    source = original.read_text()
    needle = '"G0": frozenset(),'
    assert source.count(needle) == 1
    broken = source.replace(needle, '"G0": frozenset({REV_DATA_DEF_USE}),')
    copied = tmp_path / "invalid_profiles.py"
    copied.write_text(broken)
    spec = importlib.util.spec_from_file_location("invalid_dfg_v2_profiles", str(copied))
    module = importlib.util.module_from_spec(spec)
    with pytest.raises(ValueError, match="declares REV_DATA_DEF_USE without DATA_DEF_USE"):
        spec.loader.exec_module(module)
    assert PROFILES["G0"] == frozenset()
    assert original.read_text() == source


def test_runtime_custom_profile_also_rejects_unpaired_reverse(monkeypatch):
    monkeypatch.setitem(PROFILES, "invalid", frozenset({REVERSE_OF[DATA_DEF_USE]}))
    for read in (lambda: forward_relations("invalid"),
                 lambda: has_reverse("invalid", DATA_DEF_USE),
                 lambda: materialize({}, "invalid")):
        with pytest.raises(ValueError, match="without DATA_DEF_USE"):
            read()


def test_has_reverse_rejects_nonforward_query():
    with pytest.raises(ValueError, match="Not a forward"):
        has_reverse("G3R", REVERSE_OF[DATA_DEF_USE])
