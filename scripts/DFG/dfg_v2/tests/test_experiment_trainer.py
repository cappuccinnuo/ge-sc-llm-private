"""Prompt 7 CPU trainer/checkpoint integration; all graphs are synthetic.

The engine parity test deliberately uses the same train/val rows as the frozen
paper runner. Its duplicate outer evaluation alias is ONLY an engine test, never
a nested-protocol result; actual disjointness is tested separately.
"""
import copy
import json
from pathlib import Path

import pytest
import torch
from torch.nn import functional as F

from scripts.DFG.dfg_v2 import ENV_SOURCE, REVERSE_OF
from scripts.DFG.dfg_v2.experiment import trainer
from scripts.DFG.dfg_v2.experiment.checkpoint import (
    StopMonitor, build_binding, snapshot_input, save_checkpoint,
    restore_checkpoint, validate_binding,
)
from scripts.DFG.dfg_v2.experiment.support import support
from scripts.DFG.dfg_v2.model import make_model, validate_registration
from scripts.DFG.dfg_v2.supervision import DfgV2Supervision
from scripts.DFG.dfg_v2.tests.test_experiment_protocol import small_graph, PARTITION
from scripts.DFG.experiments import paper_run, paper_protocol
from scripts.DFG.experiments.common import (
    digest, metrics, read_json, seed_all, sha256, tensor_digest, write_json,
)
from scripts.DFG.experiments.paper_runtime import Supervision, graph_schema_and_support
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.model_validation import capture_model_input
from scripts.labeling_v2.safe_graph import write_graph


CONFIG = dict(initial_lr=.001, max_lr=.005, weight_decay=.0001,
              schedule_epochs=50, div_factor=25, final_div_factor=10000,
              cycle_momentum=True, patience=7, delta=.001,
              maximum_training_epochs=3, mode="smoke")
LABELS = {"train.sol": 1, "val.sol": 0, "test.sol": 1}


def setup_case(tmp_path, task="node", profile="G3R", config=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    config = dict(CONFIG if config is None else config)
    graph = small_graph(profile)
    graph_path = tmp_path / "input.gpickle"
    write_graph(graph, graph_path)
    labels_path, folds_path = tmp_path / "labels.json", tmp_path / "folds.json"
    write_json(labels_path, [{"contract_name": f, "targets": y} for f, y in LABELS.items()])
    write_json(folds_path, PARTITION)
    seed_all(73)
    model = make_model(task, graph, profile, hidden_size=16, heads=4)
    initial_path = tmp_path / "untrained.pt"
    torch.save(model.state_dict(), str(initial_path))
    counts = support(graph, profile, PARTITION)
    parts = {role: DfgV2Supervision(model, task, PARTITION[role + "_files"])
             for role in ("inner_train", "inner_val", "outer_test")}
    ref = lambda p: dict(path=str(p), sha256=sha256(p))
    binding = build_binding(model, task_id="synthetic_" + task, fold=0, seed=1,
        profile=profile, reducer="mean",
        graph_ref=dict(ref(graph_path), fingerprint=fingerprint(graph)),
        fold_ref=ref(folds_path), label_ref=ref(labels_path),
        initial_sha256=sha256(initial_path), config=config, split=copy.deepcopy(PARTITION),
        support=counts, initialization_record={"kind": "synthetic test only"})
    binding["initial_state_sha256"] = tensor_digest(model.state_dict())
    return model, parts, graph, binding, counts, config


class GuardedOuter:
    """Fail if either outer-target materialization or scoring occurs mid-fit."""
    def __init__(self, wrapped, destination):
        self.wrapped, self.destination = wrapped, destination
        self.calls = []
    def __getattr__(self, name):
        return getattr(self.wrapped, name)
    def targets(self, model, labels):
        assert (self.destination / "last.pt").is_file(), "outer targets accessed before fitting ended"
        self.calls.append("targets")
        return self.wrapped.targets(model, labels)
    def forward(self, model):
        assert (self.destination / "last.pt").is_file(), "outer scored before fitting ended"
        assert not model.training, "outer scored in training mode"
        self.calls.append("forward")
        return self.wrapped.forward(model)


@pytest.mark.parametrize("task", ["node", "contract"])
def test_nested_fit_gates_outer_masks_auxiliary_and_bitwise_reload(tmp_path, task):
    model, parts, graph, binding, counts, config = setup_case(tmp_path, task)
    destination = tmp_path / "fit"
    outer = GuardedOuter(parts["outer_test"], destination)
    parts["outer_test"] = outer
    seed_all(1000073)
    result = trainer.fit(model, parts, task, LABELS, config, destination,
                         binding, list(graph), counts)
    assert result["status"] == "complete"
    assert result["score_role"] == "outer_test" and result["selection_role"] == "inner_val"
    assert result["outer_supervision_used_in_optimization"] is False
    assert outer.calls == ["targets", "forward", "forward", "forward", "forward"]
    assert result["history_rows"] == 3
    assert all(v for roles in result["checkpoint_roundtrip_exact"].values() for v in roles.values())
    assert result["initial_sha256"] != tensor_digest(model.state_dict())
    history = [json.loads(line) for line in (destination / "history.jsonl").read_text().splitlines()]
    assert all("inner_val_loss" in row and "outer_test" not in row for row in history)
    assert min(r["inner_val_loss"] for r in history) == result["best_inner_val_loss"]
    assert min(range(len(history)), key=lambda i: history[i]["inner_val_loss"]) == result["best_epoch"]
    updates = result["gradient_audit"]["v2_message_update_l1"]
    assert set(REVERSE_OF.values()) <= {key.split("|")[1] for key in updates}
    for role, filename in (("inner_val", "val.sol"), ("outer_test", "test.sol")):
        predictions = read_json(destination / (role + "_predictions.json"))
        assert predictions and {r["file"] for r in predictions} == {filename}
        for row in predictions:
            assert row["score_role"] == role
            if task == "node":
                assert row["node_type"] != ENV_SOURCE
                original = graph.nodes[row["original_graph_node_id"]]
                assert original["source_file"] == row["file"]
                assert original["node_type"] == row["node_type"]
                assert row["target"] == int(original["node_info_vulnerabilities"] is not None)
        for checkpoint in ("best", "last"):
            recalculated = metrics([r["target"] for r in predictions],
                                   [r[checkpoint] for r in predictions])
            assert recalculated == result[role][checkpoint]
            assert sha256(destination / (checkpoint + ".pt")) == result["checkpoint_sha256"][checkpoint]


@pytest.mark.parametrize("task", ["node", "contract"])
def test_snapshot_deterministic_with_environment_and_explicit_reverse(tmp_path, task):
    model, _, _, binding, _, _ = setup_case(tmp_path, task)
    first = snapshot_input(model, binding)
    assert first == capture_model_input(model, external_inputs=binding)
    assert first == snapshot_input(model, copy.deepcopy(binding))
    assert ENV_SOURCE in dict(first["schema"]["node_types"])
    assert any(row[0][1].startswith("REV_") for row in first["schema"]["edge_types"])
    model.eval()
    assert snapshot_input(model, binding) == first
    with torch.no_grad():
        next(model.parameters()).add_(.1)
    # Fingerprints bind model input, not trainable weight values.
    assert snapshot_input(model, binding) == first


def checkpoint_fixture(tmp_path):
    model, parts, _, binding, counts, config = setup_case(tmp_path)
    expected = snapshot_input(model, binding)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["initial_lr"])
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=.005, total_steps=50)
    monitor = StopMonitor()
    monitor.step(.7)
    path = tmp_path / "checkpoint.pt"
    checksum = save_checkpoint(path, model, expected, binding, 0, monitor, optimizer, scheduler)
    return model, binding, expected, path, checksum, monitor, optimizer, scheduler


@pytest.mark.parametrize("damage", ["role", "profile", "schema", "auxiliary",
                                    "graph_bytes", "labels_bytes", "fold_bytes",
                                    "features", "labels", "mask", "dictionary",
                                    "checkpoint_bytes", "weights", "checkpoint_binding"])
def test_checkpoint_rejects_binding_input_or_weight_tampering(tmp_path, damage):
    model, binding, expected, path, checksum, _, _, _ = checkpoint_fixture(tmp_path)
    if damage == "role":
        binding["score_role"] = "cv_validation"
    elif damage == "profile":
        binding["profile"] = "G3"
    elif damage == "schema":
        binding["registered_schema"]["canonical_relations"][0]["index"] += 1
    elif damage == "auxiliary":
        binding["auxiliary_node_types"] = []
    elif damage.endswith("_bytes") and damage != "checkpoint_bytes":
        key = {"graph_bytes": "graph", "labels_bytes": "labels", "fold_bytes": "folds"}[damage]
        with open(binding[key]["path"], "ab") as handle:
            handle.write(b"changed")
    elif damage == "features":
        model.symmetrical_global_graph.nodes[ENV_SOURCE].data["inp"][0, 0] += 1
    elif damage == "labels":
        model.node_labels[0] = 1 - model.node_labels[0]
    elif damage == "mask":
        model.supervised_node_mask[:] = True
    elif damage == "dictionary":
        canonical = next(iter(model.etypes_dict))
        model.etypes_dict[canonical] += 1
    elif damage == "checkpoint_bytes":
        with path.open("ab") as handle:
            handle.write(b"changed")
    else:
        obj = torch.load(str(path), map_location="cpu")
        if damage == "weights":
            next(iter(obj["state_dict"].values())).add_(1)
        else:
            obj["binding"]["seed"] = 999
            obj["binding_sha256"] = digest(obj["binding"])
        torch.save(obj, str(path))
        checksum = sha256(path)
    with pytest.raises((ValueError, AssertionError)):
        restore_checkpoint(path, model, binding, checksum)


def test_checkpoint_save_rejects_stale_snapshot_and_reload_restores_logits(tmp_path):
    model, binding, expected, path, checksum, monitor, optimizer, scheduler = checkpoint_fixture(tmp_path)
    original = {k: v.detach().clone() for k, v in model.state_dict().items()}
    selected = DfgV2Supervision(model, "node", ["val.sol"])
    model.eval()
    with torch.no_grad():
        expected_logits = selected.forward(model).clone()
        for param in model.parameters():
            param.add_(.1)
    restore_checkpoint(path, model, binding, checksum)
    assert all(torch.equal(v, model.state_dict()[k]) for k, v in original.items())
    with torch.no_grad():
        assert torch.equal(expected_logits, selected.forward(model))
    drifted_binding = copy.deepcopy(binding)
    drifted_binding["seed"] = 2
    with pytest.raises(ValueError, match="input changed"):
        save_checkpoint(tmp_path / "changed.pt", model, expected, drifted_binding,
                        0, monitor, optimizer, scheduler)


@pytest.mark.parametrize("task", ["node", "contract"])
def test_cpu_three_epoch_frozen_engine_parity_identical_supervision(tmp_path, task):
    model, _, graph, binding, counts, config = setup_case(tmp_path / "new", task, "G0", dict(CONFIG, mode="engine_equivalence"))
    seed_all(73)
    old = make_model(task, graph, "G0", hidden_size=16, heads=4)
    assert tensor_digest(model.state_dict()) == tensor_digest(old.state_dict())
    engine_split = dict(train_files=["train.sol"], val_files=["val.sol", "test.sol"])
    old_parts = {name: Supervision(old, task, files)
                 for name, files in (("train", engine_split["train_files"]),
                                     ("val", engine_split["val_files"]))}
    old_support = graph_schema_and_support(graph, engine_split)
    old_binding = dict(protocol=paper_protocol.NAME, protocol_version=paper_protocol.VERSION,
        initialization_version=paper_protocol.INITIALIZATION_VERSION,
        forward_scope=paper_protocol.FORWARD_SCOPE, score_role=paper_protocol.SCORE_ROLE,
        registered_schema=validate_registration(old))
    # Intentionally duplicate only the post-fit evaluation alias. This test
    # compares engines under identical rows; it is not a nested CV execution.
    new_parts = dict(inner_train=DfgV2Supervision(model, task, ["train.sol"]),
                    inner_val=DfgV2Supervision(model, task, ["val.sol", "test.sol"]),
                    outer_test=DfgV2Supervision(model, task, ["val.sol", "test.sol"]))
    binding["purpose"] = "engine_equivalence_only_repeated_val_export_not_outer_test"
    binding["split"] = engine_split
    counts = dict(schema=counts["schema"], profile="G0", relations=[],
                  v2_training_edges=0, purpose="engine_equivalence_only")
    binding["support_sha256"] = digest(counts)
    seed_all(1000073)
    paper_run.fit_variant(old, old_parts, task, LABELS, config, tmp_path / "old_fit",
                          old_binding, list(graph), old_support)
    seed_all(1000073)
    trainer.fit(model, new_parts, task, LABELS, config, tmp_path / "new_fit",
                binding, list(graph), counts)
    old_history = [json.loads(x) for x in (tmp_path / "old_fit/history.jsonl").read_text().splitlines()]
    new_history = [json.loads(x) for x in (tmp_path / "new_fit/history.jsonl").read_text().splitlines()]
    assert len(old_history) == len(new_history) == 3
    for before, after in zip(old_history, new_history):
        assert abs(before["train_loss"] - after["train_loss"]) <= 1e-6
        assert abs(before["cv_validation_loss"] - after["inner_val_loss"]) <= 1e-6
        for key in ("epoch", "lr", "adam_beta1", "saved_best", "patience_counter"):
            assert before[key] == after[key]
        assert before["cv_validation"] == after["inner_val"]
    assert all(torch.equal(v, model.state_dict()[k]) for k, v in old.state_dict().items())


@pytest.mark.parametrize("failure", ["nonfinite_train", "nonfinite_val", "binding"])
def test_resource_watcher_always_closed_on_failure(tmp_path, monkeypatch, failure):
    model, parts, graph, binding, counts, config = setup_case(tmp_path)
    guards = []
    class TrackingResources:
        def __init__(self, device):
            self.entered, self.exited, self.error_type = False, False, None
            guards.append(self)
        def __enter__(self):
            self.entered = True
            return self
        def __exit__(self, error_type, *args):
            self.exited, self.error_type = True, error_type
        def check(self):
            pass
        def summary(self):
            return {"synthetic": True}
    monkeypatch.setattr(trainer, "Resources", TrackingResources)
    if failure == "binding":
        binding["score_role"] = "cv_validation"
    else:
        part = parts["inner_train" if failure == "nonfinite_train" else "inner_val"]
        normal_forward = part.forward
        monkeypatch.setattr(part, "forward", lambda m: normal_forward(m) * float("nan"))
    with pytest.raises(ValueError):
        trainer.fit(model, parts, "node", LABELS, config, tmp_path / "fit",
                    binding, list(graph), counts)
    assert len(guards) == 1 and guards[0].entered and guards[0].exited
    assert guards[0].error_type is ValueError
    assert not (tmp_path / "fit/result.json").exists()
    assert not (tmp_path / "fit/last.pt").exists()


@pytest.mark.parametrize("damage", ["config", "support", "parts", "mask", "initial",
                                    "role_missing", "unapproved_overlap", "fake_diagnostic"])
def test_fit_rejects_drift_before_optimizer_or_outer_scoring(tmp_path, damage):
    model, parts, graph, binding, counts, config = setup_case(tmp_path)
    if damage == "config":
        config["initial_lr"] *= 2
    elif damage == "support":
        counts["v2_training_edges"] += 1
    elif damage == "parts":
        parts["inner_train"] = DfgV2Supervision(model, "node", ["test.sol"])
    elif damage == "mask":
        parts["inner_train"].mask[:] = True
    elif damage == "initial":
        with torch.no_grad():
            next(model.parameters()).add_(.01)
    elif damage == "role_missing":
        parts.pop("outer_test")
    elif damage == "unapproved_overlap":
        binding["split"]["outer_test_files"] = ["val.sol"]
        parts["outer_test"] = DfgV2Supervision(model, "node", ["val.sol"])
    else:
        binding["purpose"] = "engine_equivalence_only_repeated_val_export_not_outer_test"
    destination = tmp_path / "fit"
    with pytest.raises(ValueError):
        trainer.fit(model, parts, "node", LABELS, config, destination, binding, list(graph), counts)
    assert not (destination / "history.jsonl").exists()
    assert not (destination / "last.pt").exists()
    assert not (destination / "outer_test_predictions.json").exists()


@pytest.mark.parametrize("damage", ["wrong_target", "missing_target", "unknown_target",
                                    "noninteger_target", "wrong_export_ids"])
def test_fit_rejects_wrong_targets_or_original_export_identity(tmp_path, damage):
    model, parts, graph, binding, counts, config = setup_case(tmp_path)
    labels, ids = dict(LABELS), list(graph)
    if damage == "wrong_target":
        labels["train.sol"] = 0
    elif damage == "missing_target":
        labels.pop("test.sol")
    elif damage == "unknown_target":
        labels["unbound.sol"] = 1
    elif damage == "noninteger_target":
        labels["train.sol"] = True
    else:
        ids[0], ids[1] = ids[1], ids[0]
    destination = tmp_path / "fit"
    with pytest.raises(ValueError):
        trainer.fit(model, parts, "node", labels, config, destination, binding, ids, counts)
    assert not (destination / "history.jsonl").exists()
    assert not (destination / "last.pt").exists()
