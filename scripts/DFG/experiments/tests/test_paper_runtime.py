"""Synthetic HGT fixtures; no Solidity compilation claim."""
import copy
import numpy as np
import pytest
import torch
from scripts.DFG.experiments.tests.test_runtime import graph_fixture, create_model
from scripts.DFG.experiments.paper_runtime import (
    Supervision, graph_schema_and_support, validate_registration, gradient_audit)
from scripts.DFG.experiments.runtime import GraphView, schema_report
from scripts.DFG.experiments.common import tensor_digest

SPLIT = {"train_files": ["train.sol"], "val_files": ["valid.sol", "test.sol"]}


@pytest.fixture(autouse=True)
def threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def rare_graph():
    graph = graph_fixture(False)
    graph.add_node("test.sol:rare", node_type="rare", source_file="test.sol",
                   token=np.zeros(512, dtype=np.float32), node_info_vulnerabilities=None)
    graph.add_edge("test.sol:0", "test.sol:rare", edge_type="rare_relation")
    graph.add_edge("test.sol:0", "test.sol:34", edge_type="DATA_DEF_USE")
    return graph


@pytest.mark.parametrize("task", ["node", "contract"])
def test_registered_rare_types_relations_allowed_no_train_ddg_support(tmp_path, task):
    graph = rare_graph()
    model = create_model(tmp_path, task, graph)
    support = graph_schema_and_support(graph, SPLIT)
    assert support["supported"]
    assert support["registered_without_train_nodes"] == ["rare"]
    assert ["expression", "DATA_DEF_USE", "expression"] in support["registered_without_train_relations"]
    assert validate_registration(model) == support["schema"]
    params_before = {n: id(p) for n, p in model.named_parameters()}
    part = Supervision(model, task, SPLIT["train_files"])
    torch.nn.functional.cross_entropy(part.forward(model), part.targets(model, {"train.sol": 1})).backward()
    audit = gradient_audit(model, support)
    assert audit["ddg_training_support"] == 0
    assert audit["ddg_relations"][0]["status"] == "no_training_ddg_support"
    assert audit["ddg_relations"][0]["message_gradient_l1"] == 0
    model.eval()
    with torch.no_grad():
        assert torch.isfinite(Supervision(model, task, SPLIT["val_files"]).forward(model)).all()
    assert params_before == {n: id(p) for n, p in model.named_parameters()}
    assert model.symmetrical_global_graph.num_nodes() == len(graph)
    # The old nested policy stays strict on exactly the same fixture.
    views = {n: GraphView(model, [f]) for n, f in (
        ("inner_train", "train.sol"), ("inner_val", "valid.sol"), ("outer_test", "test.sol"))}
    assert not schema_report(views)["supported"]


@pytest.mark.parametrize("change", ["missing_relation", "misindexed_relation", "misindexed_nodes",
                                    "layer_dictionary", "dgl_ids", "node_rows", "topology"])
def test_unregistered_or_wrong_dictionary_errors_before_forward(tmp_path, change):
    model = create_model(tmp_path)
    if change == "missing_relation":
        model.etypes_dict.pop(next(iter(model.etypes_dict)))
    elif change == "misindexed_relation":
        keys = list(model.etypes_dict)
        model.etypes_dict[keys[0]], model.etypes_dict[keys[1]] = model.etypes_dict[keys[1]], model.etypes_dict[keys[0]]
    elif change == "misindexed_nodes":
        keys = list(model.ntypes_dict)
        model.ntypes_dict[keys[0]], model.ntypes_dict[keys[1]] = model.ntypes_dict[keys[1]], model.ntypes_dict[keys[0]]
    elif change == "layer_dictionary":
        model.gcs[0].edge_dict = {}
    elif change == "dgl_ids":
        model.symmetrical_global_graph.edges[next(iter(model.etypes_dict))].data["id"][0] = 999
    elif change == "node_rows":
        key = next(iter(model.node_ids_dict))
        model.node_ids_dict[key] = list(reversed(model.node_ids_dict[key]))
    else:
        model.nx_graph.remove_edge(0, 3)
    before = tensor_digest(model.state_dict())
    with pytest.raises(ValueError):
        validate_registration(model)
    assert tensor_digest(model.state_dict()) == before


@pytest.mark.parametrize("task", ["node", "contract"])
def test_full_forward_exactly_matches_native_baseline_and_supervised_gradients(tmp_path, task):
    model = create_model(tmp_path, task, graph_fixture(False))
    model.eval()
    part = Supervision(model, task, SPLIT["train_files"])
    graph_identity = id(model.symmetrical_global_graph)
    reference = model()[part.mask] if task == "node" else model(part.files)[0]
    actual = part.forward(model)
    assert torch.equal(reference, actual)
    assert part.full_ids == [0, 3, 6, 9]
    y = part.targets(model, {"train.sol": 1})
    torch.nn.functional.cross_entropy(reference, y).backward()
    expected = {n: p.grad.clone() for n, p in model.named_parameters() if p.grad is not None}
    model.zero_grad()
    torch.nn.functional.cross_entropy(part.forward(model), y).backward()
    assert all(torch.equal(expected[n], p.grad) for n, p in model.named_parameters() if n in expected)
    assert graph_identity == id(model.symmetrical_global_graph)
    assert all(c[1] != "DATA_DEF_USE" for c in model.etypes_dict)


def test_node_mask_does_not_supervise_validation_logits(tmp_path):
    model = create_model(tmp_path)
    model.eval()
    part = Supervision(model, "node", SPLIT["train_files"])
    logits = model()
    logits.retain_grad()
    loss = torch.nn.functional.cross_entropy(logits[part.mask], part.targets(model, {}))
    loss.backward()
    assert logits.grad[~part.mask].abs().sum() == 0
    assert logits.grad[part.mask].abs().sum() > 0


@pytest.mark.parametrize("task", ["node", "contract"])
def test_validation_labels_cannot_enter_training_loss_or_gradients(tmp_path, task):
    graph = graph_fixture()
    changed = copy.deepcopy(graph)
    for _, d in changed.nodes(data=True):
        if d["source_file"] != "train.sol":
            d["node_info_vulnerabilities"] = None
    first = create_model(tmp_path, task, graph, "first")
    second = create_model(tmp_path, task, changed, "second")
    second.load_state_dict(first.state_dict())
    values = []
    for model, labels in ((first, {"train.sol": 1, "valid.sol": 0, "test.sol": 0}),
                          (second, {"train.sol": 1, "valid.sol": 1, "test.sol": 1})):
        model.eval()
        part = Supervision(model, task, SPLIT["train_files"])
        loss = torch.nn.functional.cross_entropy(part.forward(model), part.targets(model, labels))
        loss.backward()
        values.append((float(loss), {n: p.grad.clone() for n, p in model.named_parameters() if p.grad is not None}))
    assert values[0][0] == values[1][0]
    assert all(torch.equal(values[0][1][n], values[1][1][n]) for n in values[0][1])


def test_supported_ddg_has_nonzero_gradient(tmp_path):
    graph = graph_fixture()
    model = create_model(tmp_path, graph=graph)
    part = Supervision(model, "node", SPLIT["train_files"])
    torch.nn.functional.cross_entropy(part.forward(model), part.targets(model, {})).backward()
    result = gradient_audit(model, graph_schema_and_support(graph, SPLIT))
    assert result["ddg_training_support"] > 0
    assert any(r["message_gradient_l1"] > 0 for r in result["ddg_relations"])


def test_cross_file_edge_rejected_and_retained():
    graph = graph_fixture()
    graph.add_edge("train.sol:0", "test.sol:0", edge_type="next")
    with pytest.raises(ValueError, match="Cross-file"):
        graph_schema_and_support(graph, SPLIT)
    assert graph.has_edge("train.sol:0", "test.sol:0")
