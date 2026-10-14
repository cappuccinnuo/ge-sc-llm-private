"""CPU integration checks for Stage G around the unchanged paper epoch loop.

Synthetic graphs only. No solc, CUDA allocation, GPU probe, or formal training.
"""
import copy
import json
import random
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from sco_models import graph_utils
from scripts.DFG.experiments import paper_run, paper_checkpoint, paper_runtime
from scripts.DFG.experiments.checkpoint import StopMonitor as FrozenStopMonitor
from scripts.DFG.experiments.common import seed_all, sha256, tensor_digest
from scripts.DFG.experiments.paper_protocol import (
    NAME, VERSION, FORWARD_SCOPE, SCORE_ROLE,
    INITIALIZATION_VERSION as OLD_INITIALIZATION_VERSION,
)
from scripts.DFG.state.stage_f.initialization import INITIALIZATION_VERSION
from scripts.DFG.experiments.e23_pilot import (
    EXPERIMENT_VERSION, ADAPTER_VERSION, TRIPLE_INITIALIZATION_VERSION,
)
from scripts.DFG.experiments.e23_pilot import checkpoint, training, runtime
from scripts.DFG.experiments.e23_pilot.model import make_model
from scripts.DFG.experiments.e23_pilot.tests.test_model import graphs


@pytest.fixture(autouse=True)
def cpu_only(monkeypatch):
    # seed_all normally seeds CUDA too if available; these are CPU-only tests.
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    before = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(before)


SPLIT = {"train_files": ["train.sol"], "val_files": ["val.sol"]}


def binding(model, graph, variant="E2"):
    return {
        "protocol": NAME, "protocol_version": VERSION,
        "forward_scope": FORWARD_SCOPE, "score_role": SCORE_ROLE,
        "experiment_version": EXPERIMENT_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "initialization_version": INITIALIZATION_VERSION,
        "triple_initialization_version": TRIPLE_INITIALIZATION_VERSION,
        "variant": variant,
        "registered_schema": runtime.graph_schema_and_support(graph, SPLIT)["schema"],
        "graph_sha256": "synthetic-frozen-input",
        "initial_weights_sha256": tensor_digest(model.state_dict()),
        "split": copy.deepcopy(SPLIT),
    }


def configuration(task="node"):
    args = SimpleNamespace(mode="smoke", seed=1, epochs=50,
                           smoke_epochs=3, device="cpu", threads=1)
    return paper_run.effective_config(task, args)


def parts(model, task="node"):
    return {phase: runtime.Supervision(model, task, SPLIT[phase + "_files"])
            for phase in ("train", "val")}


def test_fit_and_checkpoint_share_frozen_codeobjects_without_global_mutation():
    before = dict(paper_run.fit_variant.__globals__)
    old_checkpoint = dict(paper_checkpoint.save_checkpoint.__globals__)
    original_reflect = graph_utils.reflect_graph
    assert training.FIT.__code__ is paper_run.fit_variant.__code__
    assert training.FIT.__defaults__ == paper_run.fit_variant.__defaults__
    assert training.FIT.__closure__ == paper_run.fit_variant.__closure__
    expected = dict(before, gradient_audit=runtime.gradient_audit,
                    save_checkpoint=checkpoint.save_checkpoint,
                    restore_checkpoint=checkpoint.restore_checkpoint,
                    snapshot_input=checkpoint.snapshot_input)
    assert training.FIT.__globals__ == expected
    assert checkpoint.save_checkpoint.__code__ is paper_checkpoint.save_checkpoint.__code__
    assert checkpoint.restore_checkpoint.__code__ is paper_checkpoint.restore_checkpoint.__code__
    assert checkpoint.StopMonitor is FrozenStopMonitor
    assert runtime.Supervision is paper_runtime.Supervision
    assert paper_run.fit_variant.__globals__ == before
    assert paper_checkpoint.save_checkpoint.__globals__ == old_checkpoint
    assert graph_utils.reflect_graph is original_reflect


@pytest.mark.parametrize("task", ["node", "contract"])
def test_frozen_and_adapted_fit_numerically_identical_on_e2(tmp_path, task):
    graph = graphs()["E2"]
    seed_all(11000 if task == "contract" else 10000)
    reference = make_model(task, graph)
    seed_all(11000 if task == "contract" else 10000)
    adapted = make_model(task, graph)
    assert tensor_digest(reference.state_dict()) == tensor_digest(adapted.state_dict())
    cfg = configuration(task)
    support = runtime.graph_schema_and_support(graph, SPLIT)
    labels = {"train.sol": 1, "val.sol": 0}
    legacy = binding(reference, graph)
    legacy["initialization_version"] = OLD_INITIALIZATION_VERSION
    current = binding(adapted, graph)
    original_globals = dict(paper_run.fit_variant.__globals__)
    seed_all(1011000 if task == "contract" else 1010000)
    old_result = paper_run.fit_variant(reference, parts(reference, task), task,
        labels, cfg, tmp_path / "old", legacy, list(graph), support)
    seed_all(1011000 if task == "contract" else 1010000)
    new_result = training.FIT(adapted, parts(adapted, task), task,
        labels, cfg, tmp_path / "new", current, list(graph), support)
    # Compare the whole numeric path, not merely final predicted classes.
    assert tensor_digest(reference.state_dict()) == tensor_digest(adapted.state_dict())
    old_history = (tmp_path / "old/history.jsonl").read_text()
    new_history = (tmp_path / "new/history.jsonl").read_text()
    assert old_history == new_history
    assert old_result["cv_validation"] == new_result["cv_validation"]
    assert old_result["best_epoch"] == new_result["best_epoch"]
    assert old_result["last_epoch"] == new_result["last_epoch"]
    assert old_result["initial_sha256"] == new_result["initial_sha256"]
    assert old_result["checkpoint_roundtrip_exact"] == {"best": True, "last": True}
    assert new_result["checkpoint_roundtrip_exact"] == {"best": True, "last": True}
    old_rows = json.loads((tmp_path / "old/cv_validation_predictions.json").read_text())
    new_rows = json.loads((tmp_path / "new/cv_validation_predictions.json").read_text())
    assert old_rows == new_rows
    assert all("best_positive_probability" in row and "last_positive_probability" in row
               for row in new_rows)
    history = [json.loads(line) for line in new_history.splitlines()]
    assert new_result["best_cv_validation_loss"] == min(row["cv_validation_loss"] for row in history)
    assert new_result["last_epoch"] == len(history) - 1
    assert paper_run.fit_variant.__globals__ == original_globals


@pytest.mark.parametrize("task", ["node", "contract"])
def test_validation_labels_do_not_influence_train_loss_or_any_parameter_gradient(task):
    original = graphs()["E3b"]
    changed = copy.deepcopy(original)
    for _, data in changed.nodes(data=True):
        if data["source_file"] == "val.sol":
            data["node_info_vulnerabilities"] = (
                None if data["node_info_vulnerabilities"] else [{"category": "fixture"}])
    outputs = []
    for graph, validation_label in ((original, 0), (changed, 1)):
        seed_all(1729)
        model = make_model(task, graph)
        model.train()
        supervision = runtime.Supervision(model, task, ["train.sol"])
        seed_all(992)
        logits = supervision.forward(model)
        labels = supervision.targets(model, {"train.sol": 1, "val.sol": validation_label})
        loss = torch.nn.functional.cross_entropy(logits, labels)
        loss.backward()
        outputs.append((logits.detach().clone(), loss.detach().clone(),
                        {name: None if parameter.grad is None else parameter.grad.clone()
                         for name, parameter in model.named_parameters()}))
    assert torch.equal(outputs[0][0], outputs[1][0])
    assert torch.equal(outputs[0][1], outputs[1][1])
    assert outputs[0][2].keys() == outputs[1][2].keys()
    for name in outputs[0][2]:
        left, right = outputs[0][2][name], outputs[1][2][name]
        assert left is None and right is None or (
            left is not None and right is not None and torch.equal(left, right)), name


def test_validation_only_relation_is_audited_and_not_rejected_or_trained():
    graph = graphs()["E3a"]
    for source, target, key, data in list(graph.edges(keys=True, data=True)):
        if data["edge_type"] == "STATE_DEF_USE" and graph.nodes[source]["source_file"] == "train.sol":
            graph.remove_edge(source, target, key)
    model = make_model("node", graph)
    support = runtime.graph_schema_and_support(graph, SPLIT)
    train = runtime.Supervision(model, "node", ["train.sol"])
    torch.nn.functional.cross_entropy(train.forward(model), train.targets(model, {})).backward()
    report = runtime.gradient_audit(model, support)
    row = next(row for row in report["enhancement_relations"]
               if row["canonical"][1] == "STATE_DEF_USE")
    assert row["train_edges"] == 0 and row["val_edges"] == 1
    assert row["status"] == "no_training_support"
    for key in ("relation_msg_gradient_l1", "relation_att_gradient_l1", "relation_pri_gradient_l1"):
        assert row[key] == 0
    model.eval()
    with torch.no_grad():
        logits = runtime.Supervision(model, "node", ["val.sol"]).forward(model)
        assert torch.isfinite(logits).all()
    # The auditable absence of train support must not mask a real leak.
    idx = model.etypes_dict[tuple(row["canonical"])]
    model.gcs[0].relation_msg.grad[idx].fill_(1)
    with pytest.raises(AssertionError, match="val-only"):
        runtime.gradient_audit(model, support)


def test_stop_policy_saves_strict_minima_but_patience_uses_delta_reference():
    assert checkpoint.StopMonitor is FrozenStopMonitor
    stop = checkpoint.StopMonitor(patience=3, delta=0.001)
    values = [1.0, 0.9995, 0.9992, 0.9988, 0.9987, 0.9986, 0.9985]
    decisions = [stop.step(value) for value in values]
    assert [saved for saved, _ in decisions] == [True] * len(values)
    assert [stopped for _, stopped in decisions] == [False] * 6 + [True]
    assert stop.best == 0.9985
    assert stop.reference == 0.9988
    assert stop.counter == 3
    tied = checkpoint.StopMonitor(patience=2, delta=0.001)
    assert tied.step(1.0) == (True, False)
    assert tied.step(1.0) == (False, False)
    assert tied.step(1.0) == (False, True)


@pytest.mark.parametrize("field", [
    "protocol", "protocol_version", "forward_scope", "score_role",
    "experiment_version", "adapter_version", "initialization_version",
    "triple_initialization_version", "variant",
])
def test_checkpoint_rejects_protocol_initialization_and_variant_tamper(field):
    graph = graphs()["E3b"]
    model = make_model("node", graph)
    valid = binding(model, graph, "E3b")
    checkpoint.validate_binding(model, valid)
    broken = copy.deepcopy(valid)
    broken[field] = "tampered"
    with pytest.raises(ValueError):
        checkpoint.validate_binding(model, broken)


def test_checkpoint_roundtrip_and_schema_binding_input_tamper(tmp_path):
    graph = graphs()["E3b"]
    model = make_model("node", graph)
    current = binding(model, graph, "E3b")
    optimizer = torch.optim.Adam(model.parameters(), lr=0.0002)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=0.005, total_steps=50)
    stop = checkpoint.StopMonitor()
    stop.step(0.5)
    manifest = checkpoint.snapshot_input(model, current)
    path = tmp_path / "best.pt"
    initial = tensor_digest(model.state_dict())
    digest = checkpoint.save_checkpoint(path, model, manifest, current, 0, stop, optimizer, scheduler)
    with torch.no_grad():
        model.classify.weight.add_(1)
    restored = checkpoint.restore_checkpoint(path, model, current, digest)
    assert tensor_digest(model.state_dict()) == initial
    assert restored["format"] == checkpoint.FORMAT
    different_binding = copy.deepcopy(current)
    different_binding["initial_weights_sha256"] = "another-initial-state"
    with pytest.raises(ValueError, match="binding"):
        checkpoint.restore_checkpoint(path, model, different_binding, digest)
    broken = copy.deepcopy(current)
    broken["registered_schema"]["canonical_relations"][0]["index"] = 999
    with pytest.raises(ValueError):
        checkpoint.validate_binding(model, broken)
    with pytest.raises(ValueError, match="file changed"):
        checkpoint.restore_checkpoint(path, model, current, "0" * 64)
    # Re-hashing tampered bytes must not bypass the format invariant.
    payload = torch.load(str(path), map_location="cpu")
    payload["format"] = "old-checkpoint"
    alternate = tmp_path / "altered.pt"
    torch.save(payload, str(alternate))
    with pytest.raises(ValueError, match="format"):
        checkpoint.restore_checkpoint(alternate, model, current, sha256(alternate))
    typ = model.symmetrical_global_graph.ntypes[0]
    model.symmetrical_global_graph.nodes[typ].data["inp"][0, 0] += 1
    with pytest.raises(ValueError):
        checkpoint.restore_checkpoint(path, model, current, digest)


def test_fit_wrapper_resets_seed_and_refuses_trained_initial_state(tmp_path, monkeypatch):
    # The production wrapper is CUDA-only. Mock telemetry for this control-flow
    # test: no GPU commands, CUDA queries, or hardware allocations are executed.
    class NoHardwareMonitor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def report(self):
            return {"fixture": "no hardware access"}
    monkeypatch.setattr(training, "CardMonitor", NoHardwareMonitor)
    monkeypatch.setattr(torch.cuda, "max_memory_allocated", lambda *args: 0)
    monkeypatch.setattr(torch.cuda, "max_memory_reserved", lambda *args: 0)
    observed = []
    def record_random(*args):
        observed.append((random.random(), np.random.rand(), torch.rand(7)))
        (args[5] / "history.jsonl").write_text(json.dumps({"patience_counter": 0}) + "\n")
        return {"history_rows": 3}
    monkeypatch.setattr(training, "FIT", record_random)
    graph = graphs()["E2"]
    model = make_model("node", graph)
    initial = {key: value.detach().clone() for key, value in model.state_dict().items()}
    cfg = configuration()
    current = binding(model, graph)
    support = runtime.graph_schema_and_support(graph, SPLIT)
    for index in range(2):
        dest = tmp_path / str(index)
        dest.mkdir()
        random.random()
        np.random.rand(50 + index)
        torch.rand(100 + index)
        training.fit(model, parts(model), "node", {}, cfg, dest, current,
                     list(graph), support, initial, 1000061)
    assert observed[0][:2] == observed[1][:2]
    assert torch.equal(observed[0][2], observed[1][2])
    with torch.no_grad():
        model.classify.weight.add_(0.001)
    with pytest.raises(ValueError, match="sealed untrained"):
        training.fit(model, parts(model), "node", {}, cfg, tmp_path / "rejected",
                     current, list(graph), support, initial, 1000061)
    assert len(observed) == 2
