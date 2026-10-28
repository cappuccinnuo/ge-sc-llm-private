"""Prompt 8B.0 guards: input integrity and frozen-trainer numerical parity."""
import copy
import json
from pathlib import Path

import dgl
import pytest
import torch

from scripts.DFG.dfg_v2.experiment import checkpoint, trainer
from scripts.DFG.dfg_v2.experiment.input_guard import FitInputGuard, active_guard
from scripts.DFG.dfg_v2.tests.test_experiment_trainer import setup_case, LABELS, GuardedOuter
from scripts.DFG.experiments.common import seed_all, tensor_digest, read_json, sha256, digest


@pytest.mark.parametrize("task", ["node", "contract"])
@pytest.mark.parametrize("profile", ["G0", "G3R"])
def test_guard_keeps_three_epoch_fit_exact_and_has_three_deep_boundaries(tmp_path, monkeypatch, task, profile):
    model, parts, graph, binding, support, config = setup_case(tmp_path, task, profile)
    initial = copy.deepcopy(model.state_dict())
    seed_all(1000073)
    baseline = trainer.fit(model, parts, task, LABELS, config, tmp_path / "baseline",
                           binding, list(graph), support)
    model.load_state_dict(initial)
    calls, hashes = [], []
    native_snapshot, normal_sha = checkpoint.native.snapshot_input, checkpoint.sha256
    def counted_snapshot(*args, **kwargs):
        calls.append(True)
        return native_snapshot(*args, **kwargs)
    def counted_sha(path):
        hashes.append(str(path))
        return normal_sha(path)
    monkeypatch.setattr(checkpoint.native, "snapshot_input", counted_snapshot)
    monkeypatch.setattr(checkpoint, "sha256", counted_sha)
    destination = tmp_path / "guarded"
    outer = GuardedOuter(parts["outer_test"], destination)
    parts["outer_test"] = outer
    seed_all(1000073)
    with FitInputGuard(model, binding, parts, LABELS) as guard:
        observed = trainer.fit(model, guard.wrap_parts(), task, LABELS, config,
                               destination, binding, list(graph), support)
        guard.finish()
    assert active_guard(model) is None
    summary = guard.summary()
    assert summary["complete"] and summary["deep_checks"] == 3
    assert summary["deep_boundaries"] == ["start", "after_training", "after_evaluation"]
    assert len(calls) == 3
    assert summary["file_hash_rounds"] == 1
    for name in ("graph", "folds", "labels"):
        assert hashes.count(binding[name]["path"]) == 1
    assert summary["restore_calls"] == 8
    assert summary["save_calls"] >= 2
    assert summary["observed_target_tensors"] == 4
    assert outer.calls == ["targets", "forward", "forward", "forward", "forward"]
    old_history = [json.loads(x) for x in (tmp_path / "baseline/history.jsonl").read_text().splitlines()]
    new_history = [json.loads(x) for x in (destination / "history.jsonl").read_text().splitlines()]
    assert len(old_history) == len(new_history) == 3
    for old, new in zip(old_history, new_history):
        assert {k:v for k,v in old.items() if k != "seconds"} == {k:v for k,v in new.items() if k != "seconds"}
    for key in ("best_epoch", "last_epoch", "inner_val", "outer_test", "gradient_audit"):
        assert baseline[key] == observed[key]
    for name in ("best", "last"):
        old = torch.load(str(tmp_path / "baseline" / (name + ".pt")), map_location="cpu")
        new = torch.load(str(destination / (name + ".pt")), map_location="cpu")
        assert old["state_sha256"] == new["state_sha256"]
        assert old["model_input"] == new["model_input"]
        assert old["binding"] == new["binding"]
        assert all(torch.equal(v, new["state_dict"][k]) for k,v in old["state_dict"].items())
    for name in ("inner_val_predictions.json", "outer_test_predictions.json"):
        assert read_json(tmp_path / "baseline" / name) == read_json(destination / name)


@pytest.mark.parametrize("damage", [
    "feature_version", "feature_replacement", "supervised_mask", "part_mask", "target_version",
    "labels", "part_manifest", "binding", "dictionary", "edge_content", "relation_id", "input_file",
])
def test_fast_guard_detects_mutation_and_runs_full_diagnostic(tmp_path, damage):
    model, parts, graph, binding, support, config = setup_case(tmp_path)
    guard = FitInputGuard(model, binding, parts, LABELS)
    with pytest.raises(ValueError, match="Frozen fit input changed"):
        with guard:
            checkpoint.snapshot_input(model, binding)
            wrapped = guard.wrap_parts()
            target = wrapped["inner_train"].targets(model, LABELS)
            dgraph = model.symmetrical_global_graph
            typ = dgraph.ntypes[0]
            canonical = next(c for c in dgraph.canonical_etypes if dgraph.num_edges(c))
            if damage == "feature_version":
                # Even a numerical no-op increments version and must reject.
                dgraph.nodes[typ].data["inp"].add_(0)
            elif damage == "feature_replacement":
                dgraph.nodes[typ].data["inp"] = dgraph.nodes[typ].data["inp"].clone()
            elif damage == "supervised_mask":
                model.supervised_node_mask[:] = False
            elif damage == "part_mask":
                parts["inner_train"].mask[:] = False
            elif damage == "target_version":
                target.add_(0)
            elif damage == "labels":
                model.node_labels[0] = 1 - model.node_labels[0]
            elif damage == "part_manifest":
                parts["inner_train"].manifest["files"].append("bad.sol")
            elif damage == "binding":
                binding["seed"] += 1
            elif damage == "dictionary":
                model.etypes_dict[canonical] += 1
            elif damage == "edge_content":
                source, unused = dgraph.edges(etype=canonical, order="eid")
                source[0] = (source[0] + 1) % dgraph.num_nodes(canonical[0])
            elif damage == "relation_id":
                dgraph.edges[canonical].data["id"].add_(0)
            else:
                path = Path(binding["labels"]["path"])
                path.write_text(path.read_text() + " ")
            guard.fast_check(binding, "regression")
    assert active_guard(model) is None
    assert guard.summary()["events"][-1]["kind"] == "rejection_deep"


def test_dgl_shared_storage_without_shared_version_needs_endpoint_contents():
    graph = dgl.heterograph({("n", "r", "n"): (torch.tensor([0, 1]), torch.tensor([1, 0]))})
    held, unused = graph.edges(etype=("n", "r", "n"), order="eid")
    expected = held.clone()
    other, unused = graph.edges(etype=("n", "r", "n"), order="eid")
    assert held is not other and held.data_ptr() == other.data_ptr()
    version = held._version
    other[0] = 1
    fresh, unused = graph.edges(etype=("n", "r", "n"), order="eid")
    assert held._version == fresh._version == version
    assert held.data_ptr() == fresh.data_ptr()
    assert not torch.equal(fresh, expected)


@pytest.mark.parametrize("damage", ["file", "binding", "snapshot", "state", "format"])
def test_guarded_restore_retains_native_payload_validation(tmp_path, damage):
    model, parts, graph, binding, support, config = setup_case(tmp_path)
    guard = FitInputGuard(model, binding, parts, LABELS)
    with pytest.raises(ValueError):
        with guard:
            expected = checkpoint.snapshot_input(model, binding)
            optimizer = torch.optim.Adam(model.parameters(), lr=.001)
            scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=.005, total_steps=50)
            monitor = checkpoint.StopMonitor()
            monitor.step(.7)
            path = tmp_path / "test.pt"
            checksum = checkpoint.save_checkpoint(path, model, expected, binding, 0, monitor, optimizer, scheduler)
            if damage == "file":
                with path.open("ab") as handle:
                    handle.write(b"tampered")
            else:
                payload = torch.load(str(path), map_location="cpu")
                if damage == "binding":
                    payload["binding"]["seed"] = 999
                    payload["binding_sha256"] = digest(payload["binding"])
                elif damage == "snapshot":
                    payload["model_input"]["input_sha256"] = "0" * 64
                elif damage == "state":
                    next(iter(payload["state_dict"].values())).add_(1)
                else:
                    payload["format"] = "bad"
                torch.save(payload, str(path))
                checksum = sha256(path)
            checkpoint.restore_checkpoint(path, model, binding, checksum)
    assert active_guard(model) is None


def test_guard_context_does_not_allow_unaccepted_success_or_reuse(tmp_path):
    model, parts, graph, binding, support, config = setup_case(tmp_path)
    guard = FitInputGuard(model, binding, parts, LABELS)
    with pytest.raises(ValueError, match="without final deep acceptance"):
        with guard:
            checkpoint.snapshot_input(model, binding)
    assert active_guard(model) is None
    with pytest.raises(ValueError, match="reused"):
        with guard:
            pass
