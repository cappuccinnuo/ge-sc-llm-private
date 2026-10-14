"""Actual original classifiers; synthetic HCGs, no Solidity/solc claim."""
import copy
import pickle
import networkx as nx
import numpy as np
import pytest
import torch
from sco_models.model_hgt import HGTVulNodeClassifier, HGTVulGraphClassifier, HGTLayer
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.experiments.common import tensor_digest
from scripts.DFG.experiments.paper_runtime import Supervision
from scripts.DFG.experiments.e23_pilot.model import (
    make_model, validate_registration, triple_initialize, semantic_state,
    assert_e2_alignment, move_to_device, provenance, StageGNodeClassifier, StageGGraphClassifier)
from scripts.DFG.state.stage_f.initialization import initialize_pair


@pytest.fixture(autouse=True)
def one_thread():
    old = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


def graphs():
    base = nx.MultiDiGraph()
    for f in ("train.sol", "val.sol"):
        for i, typ in enumerate(("z", "a", "z")):
            base.add_node(f + ":" + str(i), node_type=typ, source_file=f,
                          token=np.linspace(i + 0.1, i + 1.1, 512, dtype=np.float32),
                          node_info_vulnerabilities=[{"category": "fixture"}] if i == 2 else None,
                          node_source_code_lines=[i + 1], label="statement")
        base.add_edge(f + ":0", f + ":1", edge_type="next")
        base.add_edge(f + ":1", f + ":2", edge_type="next")
        base.add_edge(f + ":0", f + ":2", edge_type="DATA_DEF_USE")
    a = copy.deepcopy(base)
    b = copy.deepcopy(base)
    for f in ("train.sol", "val.sol"):
        a.add_edge(f + ":0", f + ":1", edge_type="STATE_DEF_USE")
        b.add_edge(f + ":0", f + ":1", edge_type="STATE_DEF_USE")
        b.add_edge(f + ":1", f + ":2", edge_type="STATE_ACCESS_ORDER")
        b.add_edge(f + ":0", f + ":2", edge_type="EXTERNAL_CALL_BEFORE_STATE_WRITE")
    return {"E2": base, "E3a": a, "E3b": b}


def models(task="node"):
    result = {}
    for v, graph in graphs().items():
        torch.manual_seed(123)
        result[v] = make_model(task, graph)
    return result


@pytest.mark.parametrize("task", ["node", "contract"])
def test_actual_forward_and_hgt_are_inherited_unchanged(task):
    cls = StageGNodeClassifier if task == "node" else StageGGraphClassifier
    original = HGTVulNodeClassifier if task == "node" else HGTVulGraphClassifier
    assert cls.forward is original.forward
    model = make_model(task, graphs()["E3b"])
    assert all(type(layer) is HGTLayer for layer in model.gcs)
    assert model.hidden_size == 128 and model.num_heads == 8 and model.num_layers == 2
    assert all(layer.drop.p == 0.2 and layer.use_norm for layer in model.gcs)


@pytest.mark.parametrize("task", ["node", "contract"])
def test_e2_original_full_graph_forward_and_initialization_match(tmp_path, task):
    path = tmp_path / "E2.gpickle"
    with path.open("wb") as stream:
        pickle.dump(graphs()["E2"], stream)
    report = assert_e2_alignment(path, task, seed=10001)
    assert report["eval_forward_bitwise_equal"] and report["state_equal"]


def test_direction_parallel_relations_and_original_graph_preserved():
    graph = graphs()["E3b"]
    before = fingerprint(graph)
    model = make_model("node", graph)
    assert before == fingerprint(graph)
    assert model.original_graph_node_ids == list(graph)
    assert model.node_ids_dict == {"z": [0, 2, 3, 5], "a": [1, 4]}
    dgl = model.symmetrical_global_graph
    assert dgl.num_nodes() == len(graph)
    assert ("z", "next", "a") in model.etypes_dict
    assert ("a", "next", "z") in model.etypes_dict
    assert ("z", "STATE_DEF_USE", "a") in model.etypes_dict
    assert ("a", "STATE_DEF_USE", "z") not in model.etypes_dict
    for rel in ("DATA_DEF_USE", "STATE_DEF_USE", "STATE_ACCESS_ORDER", "EXTERNAL_CALL_BEFORE_STATE_WRITE"):
        assert sum(dgl.num_edges(c) for c in dgl.canonical_etypes if c[1] == rel) == 2
    assert dgl.num_edges() == 16  # four base CFG edges reflected, eight forward edges


@pytest.mark.parametrize("task", ["node", "contract"])
def test_triple_common_parameters_all_shared_state_slices_and_independent_storage(task):
    ms = models(task)
    before = tensor_digest(ms["E2"].state_dict())
    report = triple_initialize(ms, seed=10078)
    assert report["state_def_use_shared_slices"] == 6
    assert report["state_def_use_E3a_E3b_equal"]
    assert before == tensor_digest(ms["E2"].state_dict())
    assert all(row["equal"] for row in report["common_parameters"].values())
    for a, b in (("E2", "E3a"), ("E3a", "E3b")):
        s0, s1 = semantic_state(ms[a]), semantic_state(ms[b])
        assert set(s0) <= set(s1)
        assert all(torch.equal(s0[k], s1[k]) for k in s0)
    original = ms["E2"].classify.weight.detach().clone()
    with torch.no_grad():
        ms["E3a"].classify.weight.add_(1)
    assert torch.equal(original, ms["E2"].classify.weight)
    with pytest.raises(ValueError, match="fresh constructors"):
        triple_initialize(ms)


def test_triple_uses_unchanged_stage_f_numeric_initializer():
    actual, expected = models(), models()
    triple_initialize(actual, seed=443)
    initialize_pair(expected["E2"], expected["E3a"], seed=443)
    initialize_pair(expected["E3a"], expected["E3b"], seed=443)
    assert all(tensor_digest(actual[v].state_dict()) == tensor_digest(expected[v].state_dict()) for v in actual)


@pytest.mark.parametrize("change", ["features", "labels", "rows", "relation_id", "relation_dict", "layer_dict", "base_edge"])
def test_deep_registration_rejects_input_or_dictionary_drift(change):
    model = make_model("node", graphs()["E3b"])
    if change == "features":
        model.symmetrical_global_graph.nodes["z"].data["inp"][0, 0] += 1
    elif change == "labels":
        model.node_labels[0] = 1 - model.node_labels[0]
    elif change == "rows":
        model.node_ids_dict["z"].reverse()
    elif change == "relation_id":
        c = next(iter(model.etypes_dict))
        model.symmetrical_global_graph.edges[c].data["id"][0] = 999
    elif change == "relation_dict":
        model.etypes_dict.pop(next(iter(model.etypes_dict)))
    elif change == "layer_dict":
        model.gcs[0].edge_dict = {}
    else:
        model.nx_graph.remove_edge(0, 1, 0)
    with pytest.raises(ValueError):
        validate_registration(model)


def test_triple_rejects_label_feature_and_original_row_differences():
    ms = models()
    ms["E3a"].original_graph_node_ids.reverse()
    with pytest.raises(ValueError, match="node IDs"):
        triple_initialize(ms)
    ms = models()
    ms["E3a"].nx_graph.nodes[0]["label"] = "changed"
    with pytest.raises(ValueError, match="attributes/features/labels"):
        triple_initialize(ms)


@pytest.mark.parametrize("task", ["node", "contract"])
def test_real_hgt_gradients_for_all_added_relations_and_mask_supervision(task):
    model = make_model(task, graphs()["E3b"])
    model.eval()
    sup = Supervision(model, task, ["train.sol"])
    logits = sup.forward(model)
    torch.nn.functional.cross_entropy(logits, sup.targets(model, {"train.sol": 1})).backward()
    for rel in ("STATE_DEF_USE", "STATE_ACCESS_ORDER", "EXTERNAL_CALL_BEFORE_STATE_WRITE"):
        total = sum(float(layer.relation_msg.grad[idx].abs().sum()) for layer in model.gcs
                    for c, idx in model.etypes_dict.items() if c[1] == rel)
        assert total > 0
    assert sum(float(p.grad.abs().sum()) for p in model.adapt_ws.parameters() if p.grad is not None) > 0
    assert sup.full_ids == [0, 1, 2]


def test_validation_only_registered_relation_forward_allowed_no_training_gradient():
    graph = graphs()["E3a"]
    graph.remove_edge("train.sol:0", "train.sol:1", 1)
    model = make_model("node", graph)
    c = ("z", "STATE_DEF_USE", "a")
    assert c in model.etypes_dict
    sup = Supervision(model, "node", ["train.sol"])
    torch.nn.functional.cross_entropy(sup.forward(model), sup.targets(model, {})).backward()
    assert sum(float(layer.relation_msg.grad[model.etypes_dict[c]].abs().sum()) for layer in model.gcs) == 0
    model.eval()
    with torch.no_grad():
        assert torch.isfinite(Supervision(model, "node", ["val.sol"]).forward(model)).all()


def test_device_move_keeps_features_frozen_and_parameters_registered():
    model = make_model("node", graphs()["E3b"])
    before = {n: id(p) for n, p in model.named_parameters()}
    move_to_device(model, "cpu")
    validate_registration(model)
    assert model.device == "cpu"
    assert before == {n: id(p) for n, p in model.named_parameters()}


def test_cross_file_edges_rejected_not_deleted():
    graph = graphs()["E2"]
    graph.add_edge("train.sol:0", "val.sol:0", edge_type="STATE_DEF_USE")
    with pytest.raises(ValueError, match="Cross-file"):
        make_model("node", graph)
    assert graph.has_edge("train.sol:0", "val.sol:0")


def test_source_provenance_contains_unchanged_forward_and_stage_f_adapter():
    report = provenance()
    assert report["forward_reused_without_override"]
    assert len(report["source_sha256"]) == 6
    assert all(len(v) == 64 for v in report["source_sha256"].values())
