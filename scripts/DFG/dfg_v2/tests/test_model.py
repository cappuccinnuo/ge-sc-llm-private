"""Prompt 1 fixed-graph model/auxiliary supervision acceptance (no training)."""
import copy
import hashlib
from pathlib import Path

import networkx as nx
import numpy as np
import pytest
import torch
from torch.nn import functional as F

from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
from sco_models.model_hgt import HGTVulNodeClassifier, HGTVulGraphClassifier, HGTLayer
from scripts.DFG.experiments.e23_pilot.model import make_model as stage_g_model
from scripts.DFG.experiments.paper_runtime import Supervision
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.dfg_v2 import DATA_DEF_USE, WRITES_STATE, READS_STATE, ENV_FLOW, ENV_SOURCE, FORWARD_RELATIONS
from scripts.DFG.dfg_v2.hgt_layer import HGTLayerNonEmptyMean
from scripts.DFG.dfg_v2.model import (
    DfgV2NodeClassifier, DfgV2GraphClassifier, make_model, validate_registration,
)
from scripts.DFG.dfg_v2.supervision import DfgV2Supervision


@pytest.fixture
def hcg():
    path = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "minimal.sol"
    graph = nx.MultiDiGraph()
    for filename in ("minimal.sol", "second.sol"):
        part = nx.MultiDiGraph(generate_cfg_from_source(path.read_text(), filename))
        for i, (_, attrs) in enumerate(part.nodes(data=True)):
            attrs["token"] = np.zeros(512, dtype=np.float32)
            attrs["node_info_vulnerabilities"] = [{"category": "synthetic", "lines": [1]}] if i % 3 == 1 else None
        graph = nx.disjoint_union(graph, part)
    return nx.relabel_nodes(graph, {n: 100 + 7 * n for n in graph})


def augment(graph, profile, environment_first=False):
    graph = copy.deepcopy(graph)
    expr = [n for n, d in graph.nodes(data=True)
            if d["source_file"] == "minimal.sol" and d["node_type"] == "expression_statement"]
    var = next(n for n, d in graph.nodes(data=True)
               if d["source_file"] == "minimal.sol" and d["node_type"] == "new_variable")
    if profile != "G0":
        graph.add_edge(expr[0], expr[1], edge_type=DATA_DEF_USE)
        graph.add_edge(var, expr[0], edge_type=DATA_DEF_USE)
    if profile in ("G2", "G3", "G3R"):
        graph.add_edge(expr[0], var, edge_type=WRITES_STATE)
        graph.add_edge(var, expr[1], edge_type=READS_STATE)
    if profile in ("G3", "G3R"):
        env = dict(node_type=ENV_SOURCE, source_file="minimal.sol",
                   token=np.zeros(512, dtype=np.float32), code="msg.sender")
        # No label is supplied for an auxiliary node.
        if environment_first:
            reordered = nx.MultiDiGraph()
            reordered.add_node("env", **env)
            reordered.add_nodes_from(graph.nodes(data=True))
            reordered.add_edges_from(graph.edges(keys=True, data=True))
            graph = reordered
        else:
            graph.add_node("env", **env)
        graph.add_edge("env", expr[0], edge_type=ENV_FLOW)
    return graph


def assert_state_equal(a, b):
    assert list(a.state_dict()) == list(b.state_dict())
    for name, tensor in a.state_dict().items():
        assert torch.equal(tensor, b.state_dict()[name]), name


@pytest.mark.parametrize("task", ["node", "contract"])
def test_g0_stage_g_initialization_forward_supervision_and_original_graph_equal(hcg, task):
    before = fingerprint(hcg)
    torch.manual_seed(17)
    old = stage_g_model(task, hcg)
    old_rng = torch.get_rng_state().clone()
    torch.manual_seed(17)
    new = make_model(task, hcg, "G0")
    assert torch.equal(old_rng, torch.get_rng_state())
    assert_state_equal(old, new)
    assert new.original_graph_node_ids == list(hcg)
    assert old.node_ids_dict == new.node_ids_dict
    assert old.etypes_dict == new.etypes_dict
    assert new.in_size == 512
    assert all(type(layer) is HGTLayer for layer in new.gcs)
    assert DfgV2NodeClassifier.forward is HGTVulNodeClassifier.forward
    assert DfgV2GraphClassifier.forward is HGTVulGraphClassifier.forward
    old.eval()
    new.eval()
    a = Supervision(old, task, ["minimal.sol"])
    b = DfgV2Supervision(new, task, ["minimal.sol"])
    labels = {"minimal.sol": 1, "second.sol": 0}
    assert a.full_ids == b.full_ids
    assert a.manifest == b.manifest
    assert torch.equal(a.mask, b.mask)
    assert torch.equal(a.targets(old, labels), b.targets(new, labels))
    with torch.no_grad():
        assert torch.equal(a.forward(old), b.forward(new))
    # Also preserve dropout/RNG behavior on the baseline training forward.
    old.train()
    new.train()
    torch.manual_seed(81)
    first = a.forward(old)
    torch.manual_seed(81)
    second = b.forward(new)
    assert torch.equal(first, second)
    assert fingerprint(hcg) == before


@pytest.mark.parametrize("task", ["node", "contract"])
def test_g0_nodetype_matches_production_constructor(hcg, task, tmp_path):
    path = tmp_path / "baseline.gpickle"
    nx.write_gpickle(hcg, path)
    cls = HGTVulNodeClassifier if task == "node" else HGTVulGraphClassifier
    torch.manual_seed(23)
    old = cls(str(path), node_feature="nodetype", device="cpu")
    old_rng = torch.get_rng_state().clone()
    torch.manual_seed(23)
    new = make_model(task, path, "G0", node_feature="nodetype")
    assert_state_equal(old, new)
    assert torch.equal(old_rng, torch.get_rng_state())
    old.eval()
    new.eval()
    files = ["minimal.sol", "second.sol"]
    with torch.no_grad():
        a = old() if task == "node" else old(files)[0]
        b = new() if task == "node" else new(files)[0]
    assert torch.equal(a, b)


@pytest.mark.parametrize("profile", ["G1", "G2", "G3", "G3R"])
@pytest.mark.parametrize("task", ["node", "contract"])
def test_v2_registered_relations_used_by_original_forward_and_backward(hcg, profile, task):
    graph = augment(hcg, profile)
    before = fingerprint(graph)
    torch.manual_seed(37)
    model = make_model(task, graph, profile)
    schema = validate_registration(model)
    supervision = DfgV2Supervision(model, task, ["minimal.sol"])
    logits = supervision.forward(model)
    targets = supervision.targets(model, {"minimal.sol": 1})
    loss = F.cross_entropy(logits, targets)
    assert torch.isfinite(loss)
    loss.backward()
    assert all(p.grad is None or bool(torch.isfinite(p.grad).all()) for p in model.parameters())
    relations = [c for c in model.etypes_dict if c[1] in FORWARD_RELATIONS or c[1].startswith("REV_")]
    assert relations
    # Even zero input features have trainable projection biases. Every manual
    # relation here has a path to supervised HCG nodes in the two-layer model.
    for canonical in relations:
        idx = model.etypes_dict[canonical]
        magnitude = sum(float(layer.relation_msg.grad[idx].abs().sum())
                        for layer in model.gcs if layer.relation_msg.grad is not None)
        assert magnitude > 0, canonical
    assert schema == validate_registration(model)
    assert fingerprint(graph) == before
    assert all(not model.symmetrical_global_graph.nodes[t].data["inp"].requires_grad
               for t in model.node_types)


@pytest.mark.parametrize("task", ["node", "contract"])
@pytest.mark.parametrize("node_feature", ["inside_token", "nodetype"])
def test_environment_is_unsupervised_and_unpooled_even_when_first(hcg, task, node_feature):
    graph = augment(hcg, "G3", environment_first=True)
    before = fingerprint(graph)
    torch.manual_seed(39)
    model = make_model(task, graph, "G3", node_feature=node_feature)
    assert model.original_graph_node_ids[0] == "env"
    assert not bool(model.supervised_node_mask[0])
    env_idx = model.ntypes_dict[ENV_SOURCE]
    assert model.adapt_ws[env_idx] is not model.adapt_ws[(env_idx + 1) % len(model.adapt_ws)]
    supervision = DfgV2Supervision(model, task, ["minimal.sol"])
    model.eval()
    if task == "node":
        assert model.node_labels[0] == -1
        assert not bool(supervision.mask[0])
        assert 0 not in supervision.full_ids
        assert all(0 not in ids for ids in model.labeled_node_ids.values())
        # Original labels still align despite an auxiliary row before them.
        for n in supervision.full_ids:
            assert model.node_labels[n] == int(model.nx_graph.nodes[n]["node_info_vulnerabilities"] is not None)
        expected = model()[supervision.mask]
        assert torch.equal(supervision.forward(model), expected)
        assert len(supervision.targets(model, {})) == len(supervision.full_ids)
    else:
        assert 0 not in model.node_ids_by_filename["minimal.sol"]
        expected_rows = [n for n, d in model.nx_graph.nodes(data=True)
                         if d["source_file"] == "minimal.sol" and d["node_type"] != ENV_SOURCE]
        assert model.node_ids_by_filename["minimal.sol"] == expected_rows
        # Capture the final unchanged HGT output and independently check pooling.
        captured = {}
        hook = model.gcs[-1].register_forward_hook(lambda layer, args, out: captured.update(out))
        logits, pooled = model(["minimal.sol"])
        hook.remove()
        hidden = torch.zeros(model.total_nodes, model.hidden_size)
        for typ, rows in model.node_ids_dict.items():
            hidden[rows] = captured[typ]
        assert torch.equal(pooled[0], hidden[expected_rows].mean(0))
        assert torch.equal(logits, model.classify(pooled))
        assert torch.equal(supervision.forward(model), logits)
        assert supervision.targets(model, {"minimal.sol": 1}).tolist() == [1]
    assert fingerprint(graph) == before
    assert validate_registration(model)


@pytest.mark.parametrize("task", ["node", "contract"])
def test_diagnostic_reducer_is_opt_in_and_has_same_initial_state(hcg, task):
    graph = augment(hcg, "G3")
    torch.manual_seed(7)
    standard = make_model(task, graph, "G3")
    standard_rng = torch.get_rng_state().clone()
    torch.manual_seed(7)
    diagnostic = make_model(task, graph, "G3", reducer="nonempty_mean")
    assert_state_equal(standard, diagnostic)
    assert torch.equal(standard_rng, torch.get_rng_state())
    assert all(type(layer) is HGTLayerNonEmptyMean for layer in diagnostic.gcs)
    sup = DfgV2Supervision(diagnostic, task, ["minimal.sol"])
    loss = F.cross_entropy(sup.forward(diagnostic), sup.targets(diagnostic, {"minimal.sol": 1}))
    assert torch.isfinite(loss)
    loss.backward()
    assert sum(float(layer.relation_msg.grad.abs().sum()) for layer in diagnostic.gcs) > 0


@pytest.mark.parametrize("damage", ["dictionary", "features", "labels", "mask", "pool"])
def test_registration_rejects_misaligned_inputs(hcg, damage):
    task = "contract" if damage == "pool" else "node"
    model = make_model(task, augment(hcg, "G3"), "G3")
    if damage == "dictionary":
        c = next(iter(model.etypes_dict))
        model.etypes_dict[c] += 1
    elif damage == "features":
        typ = model.node_types[0]
        model.symmetrical_global_graph.nodes[typ].data["inp"][0, 0] += 1
    elif damage == "labels":
        model.node_labels[1] = 1 - model.node_labels[1]
    elif damage == "mask":
        model.supervised_node_mask[-1] = True
    else:
        model.node_ids_by_filename["minimal.sol"].append(model.total_nodes - 1)
    with pytest.raises(ValueError):
        validate_registration(model)


@pytest.mark.parametrize("files", [[], ["absent.sol"], ["minimal.sol", "minimal.sol"]])
def test_supervision_rejects_invalid_file_lists(hcg, files):
    model = make_model("node", hcg, "G0")
    with pytest.raises(ValueError):
        DfgV2Supervision(model, "node", files)
    with pytest.raises(ValueError, match="task"):
        DfgV2Supervision(model, "contract", ["minimal.sol"])


def test_invalid_options_and_cross_file_edges_fail(hcg):
    for kwargs in ({"task": "invalid"}, {"node_feature": "random"}, {"reducer": "sum"}, {"profile": "typo"}):
        options = dict(task="node", graph_or_path=hcg, profile="G0")
        options.update(kwargs)
        with pytest.raises(ValueError):
            make_model(**options)
    files = {}
    for n, d in hcg.nodes(data=True):
        files.setdefault(d["source_file"], n)
    hcg.add_edge(files["minimal.sol"], files["second.sol"], edge_type="next")
    with pytest.raises(ValueError, match="Cross-file"):
        make_model("node", hcg, "G0")


def test_copy_provenance_matches_frozen_constructor_and_supervision():
    root = Path(__file__).resolve().parents[4]
    expected = {
        "scripts/DFG/experiments/e23_pilot/model.py": "00472900d131fe9cfc20db09ff20d910edde7ebdc82b59b100bdb2282610f141",
        "scripts/DFG/experiments/paper_runtime.py": "319159bec961320307083f63dea2f4fb5eed3559db401c542bcd0af6eca6218e",
    }
    for filename, sha in expected.items():
        assert hashlib.sha256((root / filename).read_bytes()).hexdigest() == sha
