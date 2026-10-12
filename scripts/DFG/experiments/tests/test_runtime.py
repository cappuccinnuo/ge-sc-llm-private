"""Actual unchanged HGT tests for the isolated experiment runtime.

Synthetic graph/feature fixtures: these are not Solidity compiler fixtures.
Codex 2026-10-12. No learned dataset weights or external downloads required.
"""
import copy
from collections import Counter

import networkx as nx
import numpy as np
import pytest
import torch

from scripts.labeling_v2.safe_graph import write_graph
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.experiments.common import seed_all, tensor_digest
from scripts.DFG.experiments.runtime import (
    GraphView, make_model, schema_report, assert_disconnected_files,
)
from scripts.DFG.experiments.checkpoint import (
    StopMonitor, snapshot_input, save_checkpoint, restore_checkpoint,
)

DDG = "DATA_DEF_USE"


@pytest.fixture(autouse=True)
def bounded_torch_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def graph_fixture(ddg=True):
    graph = nx.MultiDiGraph()
    rng = np.random.RandomState(735)
    # Interleave files and use arbitrary original IDs, so accidental ordinal/
    # original-ID confusion cannot pass this fixture.
    for statement in range(4):
        for file_index, filename in enumerate(("train.sol", "valid.sol", "test.sol")):
            graph.add_node(
                filename + ":" + str(statement * 17),
                node_type="condition" if statement == 3 else "expression",
                source_file=filename,
                code="statement_%s_%s" % (file_index, statement),
                node_source_code_lines=[statement + 1],
                node_info_vulnerabilities=(
                    [{"category": "reentrancy", "lines": [statement + 1]}]
                    if statement in (1, 3) else None),
                token=rng.normal(size=512).astype(np.float32),
            )
    for filename in ("train.sol", "valid.sol", "test.sol"):
        ids = [filename + ":" + str(i * 17) for i in range(4)]
        for left, right in zip(ids, ids[1:]):
            graph.add_edge(left, right, edge_type="next")
        graph.add_edge(ids[0], ids[1], edge_type="next")  # parallel edge retained
        if ddg:
            graph.add_edge(ids[0], ids[2], edge_type=DDG)
            graph.add_edge(ids[1], ids[2], edge_type=DDG)
            graph.add_edge(ids[2], ids[3], edge_type=DDG)
    return graph


def create_model(tmp_path, task="node", graph=None, name="fixture"):
    path = tmp_path / (name + ".gpickle")
    write_graph(graph if graph is not None else graph_fixture(), path)
    seed_all(745)
    return make_model(task, path, "cpu", hidden_size=16, layers=2, heads=4)


def forward(model, view, task):
    with view.bind(model):
        return model() if task == "node" else model(view.files)[0]


def targets(model, view, task):
    return torch.tensor(
        [model.node_labels[n] for n in view.full_ids] if task == "node" else [1] * len(view.files),
        dtype=torch.long,
    )


@pytest.mark.parametrize("task", ["node", "contract"])
def test_view_isolates_nodes_preserves_original_order_edges_tokens_and_restores_context(tmp_path, task):
    graph = graph_fixture()
    model = create_model(tmp_path, task, graph)
    original_ids = list(graph)
    before = snapshot_input(model, {"fixture": "original"})
    graph_obj, id_obj = model.symmetrical_global_graph, model.node_ids_dict
    filename_obj = getattr(model, "node_ids_by_filename", None)
    model.train()
    view = GraphView(model, ["test.sol"])
    assert view.full_ids == [2, 5, 8, 11]
    assert [original_ids[i] for i in view.full_ids] == ["test.sol:" + str(i * 17) for i in range(4)]
    assert list(view.nx) == list(range(4))
    assert {d["source_file"] for _, d in view.nx.nodes(data=True)} == {"test.sol"}
    assert Counter(d["edge_type"] for _, _, d in view.nx.edges(data=True)) == Counter(next=4, DATA_DEF_USE=3)
    for ordinal, full_id in enumerate(view.full_ids):
        np.testing.assert_array_equal(view.nx.nodes[ordinal]["token"], model.nx_graph.nodes[full_id]["token"])
        assert view.nx.nodes[ordinal]["node_info_vulnerabilities"] == model.nx_graph.nodes[full_id]["node_info_vulnerabilities"]
    assert sum(view.graph.num_edges(c) for c in view.graph.canonical_etypes if c[1] == DDG) == 3
    assert ("condition", DDG, "expression") not in view.graph.canonical_etypes
    assert all(c[1] != "REV_DATA_DEF_USE" for c in view.graph.canonical_etypes)
    with pytest.raises(RuntimeError, match="context test"):
        with view.bind(model):
            assert model.symmetrical_global_graph is view.graph
            assert model.training is True
            raise RuntimeError("context test")
    assert model.symmetrical_global_graph is graph_obj
    assert model.node_ids_dict is id_obj
    if filename_obj is not None:
        assert model.node_ids_by_filename is filename_obj
    assert model.training is True
    assert snapshot_input(model, {"fixture": "original"}) == before
    model.eval()
    with torch.no_grad():
        result = forward(model, view, task)
    assert result.shape == ((4, 2) if task == "node" else (1, 2))
    assert not model.training
    assert snapshot_input(model, {"fixture": "original"}) == before


@pytest.mark.parametrize("task", ["node", "contract"])
def test_heldout_feature_and_label_mutation_cannot_change_training_logits_or_gradients(tmp_path, task):
    baseline = graph_fixture()
    changed = copy.deepcopy(baseline)
    for _, node in changed.nodes(data=True):
        if node["source_file"] != "train.sol":
            node["token"] = np.full(512, 777, dtype=np.float32)
            node["node_info_vulnerabilities"] = None
    first = create_model(tmp_path, task, baseline, "first")
    second = create_model(tmp_path, task, changed, "second")
    # Same exact weights, independent of construction RNG.
    second.load_state_dict(first.state_dict())
    train_views = [GraphView(m, ["train.sol"]) for m in (first, second)]
    assert train_views[0].manifest == train_views[1].manifest
    output, gradients = [], []
    for model, view in zip((first, second), train_views):
        model.eval()  # deterministic gradients, no dropout confound
        model.zero_grad()
        logits = forward(model, view, task)
        torch.nn.functional.cross_entropy(logits, targets(model, view, task)).backward()
        output.append(logits.detach().clone())
        gradients.append({name: p.grad.detach().clone() for name, p in model.named_parameters() if p.grad is not None})
    assert torch.equal(*output)
    assert gradients[0].keys() == gradients[1].keys()
    for name in gradients[0]:
        assert torch.equal(gradients[0][name], gradients[1][name]), name


@pytest.mark.parametrize("task", ["node", "contract"])
def test_ddg_relations_really_receive_gradient_and_update_in_training_view(tmp_path, task):
    enhanced = create_model(tmp_path, task)
    baseline = create_model(tmp_path, task, graph_fixture(False), "baseline")
    assert all(c[1] != DDG for c in baseline.etypes_dict)
    view = GraphView(enhanced, ["train.sol"])
    enhanced.train()
    optimizer = torch.optim.Adam(enhanced.parameters(), lr=0.001)
    optimizer.zero_grad()
    logits = forward(enhanced, view, task)
    torch.nn.functional.cross_entropy(logits, targets(enhanced, view, task)).backward()
    relation = ("expression", DDG, "expression")
    index = enhanced.etypes_dict[relation]
    parameter = enhanced.gcs[0].relation_msg
    assert parameter.grad[index].abs().sum().item() > 0
    assert enhanced.adapt_ws[enhanced.ntypes_dict["expression"]].weight.grad.abs().sum().item() > 0
    previous = parameter[index].detach().clone()
    optimizer.step()
    assert not torch.equal(previous, parameter[index].detach())
    base_view = GraphView(baseline, ["train.sol"])
    for canonical in base_view.graph.canonical_etypes:
        assert canonical in view.graph.canonical_etypes
        assert all(torch.equal(a, b) for a, b in zip(
            base_view.graph.edges(etype=canonical, order="eid"),
            view.graph.edges(etype=canonical, order="eid"),
        ))


@pytest.mark.parametrize("change", ["relation", "node_type"])
def test_unseen_schema_fails_closed_without_dropping_test_edges(tmp_path, change):
    graph = graph_fixture()
    if change == "relation":
        graph.add_edge("test.sol:0", "test.sol:51", edge_type="rare_call")
    else:
        graph.add_node("test.sol:isolated", node_type="rare_type", source_file="test.sol",
                       token=np.zeros(512, dtype=np.float32), node_info_vulnerabilities=None)
    model = create_model(tmp_path, graph=graph)
    views = {phase: GraphView(model, [filename]) for phase, filename in [
        ("inner_train", "train.sol"), ("inner_val", "valid.sol"), ("outer_test", "test.sol")]}
    report = schema_report(views)
    assert report["supported"] is False
    detail = report["phases"]["outer_test"]
    if change == "relation":
        assert ["expression", "rare_call", "condition"] in detail["unseen_relations"]
        assert views["outer_test"].nx.number_of_edges() == 8
    else:
        assert detail["unseen_node_types"] == ["rare_type"]
        assert len(views["outer_test"].nx) == 5
    assert report["phases"]["inner_val"] == {"unseen_node_types": [], "unseen_relations": []}


def test_cross_file_edges_are_rejected_without_silently_filtering_them():
    graph = graph_fixture()
    before = fingerprint(graph)
    assert_disconnected_files(graph)
    assert fingerprint(graph) == before
    graph.add_edge("train.sol:0", "test.sol:0", edge_type="next")
    with pytest.raises(ValueError, match="Cross-file edges"):
        assert_disconnected_files(graph)
    assert graph.has_edge("train.sol:0", "test.sol:0")


def save_fixture_checkpoint(tmp_path, task):
    model = create_model(tmp_path, task)
    binding = {"graph_labels_sha256": "label-hash", "split": {"fold": 0},
               "initial_weights_sha256": "init-hash", "features_sha256": "feature-hash"}
    manifest = snapshot_input(model, binding)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1)
    monitor = StopMonitor()
    monitor.step(0.7)
    path = tmp_path / "best.pt"
    file_hash = save_checkpoint(path, model, manifest, binding, 0, monitor, optimizer, scheduler)
    return model, path, file_hash, binding, manifest


@pytest.mark.parametrize("task", ["node", "contract"])
def test_checkpoint_reloads_exact_logits_after_real_view_forward_and_input_restoration(tmp_path, task):
    model, path, file_hash, binding, manifest = save_fixture_checkpoint(tmp_path, task)
    view = GraphView(model, ["test.sol"])
    model.eval()
    with torch.no_grad():
        expected = forward(model, view, task).clone()
        model.classify.weight.add_(3)
    obj = restore_checkpoint(path, model, binding, file_hash)
    assert obj["epoch"] == 0
    assert snapshot_input(model, binding) == manifest
    with torch.no_grad():
        assert torch.equal(expected, forward(model, view, task))
    assert snapshot_input(model, binding) == manifest


@pytest.mark.parametrize("change", ["feature", "node_label", "fold", "initialization", "external_labels", "feature_binding"])
def test_checkpoint_rejects_input_or_protocol_drift_before_loading_weights(tmp_path, monkeypatch, change):
    model, path, file_hash, binding, manifest = save_fixture_checkpoint(tmp_path, "node")
    if change == "feature":
        model.nx_graph.nodes[0]["token"][0] += np.float32(1)
        model.symmetrical_global_graph.nodes["expression"].data["inp"][0, 0] += 1
    elif change == "node_label":
        model.node_labels[0] = 1 - model.node_labels[0]
    elif change == "fold":
        binding = dict(binding, split={"fold": 1})
    elif change == "initialization":
        binding = dict(binding, initial_weights_sha256="different-init")
    elif change == "external_labels":
        binding = dict(binding, graph_labels_sha256="different-labels")
    else:
        binding = dict(binding, features_sha256="different-feature-version")
    before_weights = tensor_digest(model.state_dict())
    def forbidden_load(*args, **kwargs):
        pytest.fail("state_dict was loaded before input/protocol validation")
    monkeypatch.setattr(model, "load_state_dict", forbidden_load)
    with pytest.raises(ValueError, match="fingerprint mismatch|binding mismatch"):
        restore_checkpoint(path, model, binding, file_hash)
    assert tensor_digest(model.state_dict()) == before_weights


def test_checkpoint_rejects_swapped_live_partition_view(tmp_path, monkeypatch):
    model, path, file_hash, binding, _ = save_fixture_checkpoint(tmp_path, "node")
    view = GraphView(model, ["train.sol"])
    monkeypatch.setattr(model, "load_state_dict", lambda *a, **k: pytest.fail("loaded into bound subset"))
    with view.bind(model):
        with pytest.raises(ValueError):
            restore_checkpoint(path, model, binding, file_hash)
    # The base input, not a transient subset, remains checkpoint-bound.
    assert snapshot_input(model, binding)["node_count"] == 12


@pytest.mark.parametrize("task", ["node", "contract"])
def test_real_runner_scores_outer_only_after_checkpoint_selection_and_preserves_prediction_ids(tmp_path, monkeypatch, task):
    from argparse import Namespace
    from scripts.DFG.experiments import run_pair
    from scripts.DFG.experiments.common import read_json

    graph = graph_fixture()
    model = create_model(tmp_path, task, graph)
    views = {phase: GraphView(model, [filename]) for phase, filename in [
        ("inner_train", "train.sol"), ("inner_val", "valid.sol"), ("outer_test", "test.sol")]}
    config = run_pair.effective_config(task, Namespace(
        mode="smoke", seed=1, epochs=10, smoke_epochs=2, device="cpu", threads=1))
    config.update(hidden_size=16, heads=4)
    events = []
    actual_target, actual_forward = run_pair.target_for, run_pair.forward
    actual_save = run_pair.save_checkpoint

    def watched_target(model, view, task, labels):
        if view is views["outer_test"]:
            assert ("save", "best.pt") in events
            assert ("save", "last.pt") in events
        events.append(("target", view.files[0]))
        return actual_target(model, view, task, labels)

    def watched_forward(model, view, task):
        if view is views["outer_test"]:
            assert ("save", "last.pt") in events
            assert model.training is False
        events.append(("forward", view.files[0], model.training))
        return actual_forward(model, view, task)

    def watched_save(path, *args, **kwargs):
        events.append(("save", path.name))
        return actual_save(path, *args, **kwargs)

    monkeypatch.setattr(run_pair, "target_for", watched_target)
    monkeypatch.setattr(run_pair, "forward", watched_forward)
    monkeypatch.setattr(run_pair, "save_checkpoint", watched_save)
    dest = tmp_path / "E1"
    result = run_pair.fit_variant(
        model, views, task, {f: 1 for f in ("train.sol", "valid.sol", "test.sol")},
        config, dest, {"fixture": "nested-three-files"}, list(graph))
    assert result["history_rows"] == 2
    assert result["last_epoch"] == 1
    assert result["checkpoint_roundtrip_exact"] == {"best": True, "last": True}
    assert "smoke only" in result["interpretation"]
    assert events.count(("target", "test.sol")) == 1
    assert sum(e == ("forward", "train.sol", True) for e in events) == 2
    assert sum(e == ("forward", "valid.sol", False) for e in events) == 2
    predictions = read_json(dest / "outer_predictions.json")
    if task == "node":
        assert [row["model_node_id"] for row in predictions] == [2, 5, 8, 11]
        assert [row["original_graph_node_id"] for row in predictions] == [
            "test.sol:" + str(i * 17) for i in range(4)]
        assert [row["target"] for row in predictions] == [0, 1, 0, 1]
    else:
        assert len(predictions) == 1 and predictions[0]["target"] == 1
    assert all(row["file"] == "test.sol" for row in predictions)
    assert all("best" in row and "last" in row for row in predictions)
    assert (dest / "best.pt").exists() and (dest / "last.pt").exists()
    assert read_json(dest / "model_input.json")["node_count"] == 12
