"""Prompt 7b layer selection and immutable experiment identity on small CPU graphs."""
import copy
from pathlib import Path

import pytest
import torch

from sco_models.model_hgt import HGTLayer
from scripts.DFG.dfg_v2.hgt_layer import (
    HGTLayerNonEmptyMean, HGTLayerSharedProjection,
    HGTLayerSharedProjectionNonEmptyMean,
)
from scripts.DFG.dfg_v2.model import make_model, validate_registration
from scripts.DFG.dfg_v2.experiment import run
from scripts.DFG.dfg_v2.experiment.checkpoint import (
    StopMonitor, snapshot_input, save_checkpoint, restore_checkpoint, validate_binding,
)
from scripts.DFG.dfg_v2.experiment.init import initialize_family
from scripts.DFG.dfg_v2.tests.test_experiment_protocol import small_graph
from scripts.DFG.dfg_v2.tests.test_experiment_trainer import setup_case
from scripts.DFG.dfg_v2.tests.test_model import hcg, augment
from scripts.DFG.dfg_v2.tests.test_experiment_run import graph_store, CONFIG
from scripts.DFG.experiments.common import tensor_digest
from scripts.DFG.integration.io import read_json, write_json, sha256


LAYER_CLASSES = {
    ("original", "mean"): HGTLayer,
    ("original", "nonempty_mean"): HGTLayerNonEmptyMean,
    ("shared_projection", "mean"): HGTLayerSharedProjection,
    ("shared_projection", "nonempty_mean"): HGTLayerSharedProjectionNonEmptyMean,
}


@pytest.mark.parametrize("task", ["node", "contract"])
@pytest.mark.parametrize("reducer", ["mean", "nonempty_mean"])
def test_constructor_selection_preserves_state_and_rng(task, reducer):
    graph = small_graph("G3R")
    models, states = [], []
    for impl in ("original", "shared_projection"):
        torch.manual_seed(1907)
        model = make_model(task, graph, "G3R", hidden_size=16, heads=4,
                           reducer=reducer, layer_impl=impl)
        models.append(model)
        states.append(torch.get_rng_state().clone())
        assert model.dfg_layer_impl == impl
        assert all(type(layer) is LAYER_CLASSES[(impl, reducer)] for layer in model.gcs)
        validate_registration(model)
    assert torch.equal(states[0], states[1])
    assert list(models[0].state_dict()) == list(models[1].state_dict())
    assert all(torch.equal(value, models[1].state_dict()[name])
               for name, value in models[0].state_dict().items())


def test_default_stays_original_and_invalid_impl_is_rejected():
    graph = small_graph("G0")
    model = make_model("node", graph, "G0", hidden_size=16, heads=4)
    assert model.dfg_layer_impl == "original"
    assert all(type(layer) is HGTLayer for layer in model.gcs)
    with pytest.raises(ValueError, match="layer_impl"):
        make_model("node", graph, "G0", layer_impl="automatic")
    model.dfg_layer_impl = "shared_projection"
    with pytest.raises(ValueError, match="layer_impl"):
        validate_registration(model, deep=False)


def test_initialization_provenance_and_mixed_family_rejection(hcg):
    models = {profile: make_model("node", hcg if profile == "G0" else augment(hcg, profile), profile,
        hidden_size=16, heads=4, layer_impl="shared_projection")
        for profile in ("G0", "G3R")}
    record = initialize_family(models, 1907)
    assert record["layer_impl"] == "shared_projection"
    assert all(row["layer_impl"] == "shared_projection" for row in record["profiles"].values())
    models["G0"] = make_model("node", hcg, "G0", hidden_size=16, heads=4)
    with pytest.raises(ValueError, match="layer_impl"):
        initialize_family(models, 1907)


def _save(path, model, binding):
    optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=.005, total_steps=50)
    monitor = StopMonitor()
    monitor.step(.7)
    return save_checkpoint(path, model, snapshot_input(model, binding), binding,
                           0, monitor, optimizer, scheduler)


def test_cross_implementation_checkpoint_rejected_even_with_same_tensors(tmp_path):
    original, _, graph, binding, _, config = setup_case(tmp_path)
    path = tmp_path / "checkpoint.pt"
    checksum = _save(path, original, binding)
    shared = make_model("node", graph, "G3R", hidden_size=16, heads=4,
                        layer_impl="shared_projection")
    shared.load_state_dict(original.state_dict(), strict=True)
    assert tensor_digest(shared.state_dict()) == tensor_digest(original.state_dict())
    with pytest.raises(ValueError, match="layer_impl"):
        restore_checkpoint(path, shared, binding, checksum)
    relabeled = dict(binding, layer_impl="shared_projection")
    # Even relabeling the caller binding cannot reinterpret an original checkpoint.
    with pytest.raises(ValueError):
        restore_checkpoint(path, shared, relabeled, checksum)
    legacy_binding = dict(binding)
    del legacy_binding["layer_impl"]
    validate_binding(original, legacy_binding)
    with pytest.raises(ValueError, match="layer_impl"):
        validate_binding(shared, legacy_binding)


@pytest.fixture
def shared_plan(graph_store, tmp_path, monkeypatch):
    monkeypatch.setattr(run, "_code_refs", lambda: {"fixture": "frozen"})
    output = tmp_path / "shared"
    document = run.create_plan(graph_store, output, tasks=["synthetic_contract"],
        profiles=["G0", "G3R"], folds=[0], test_mode=True,
        test_config=CONFIG, layer_impl="shared_projection")
    return output / "plan.json", document


def test_shared_plan_initial_fit_checkpoint_and_result_binding(shared_plan):
    path, document = shared_plan
    assert document["layer_impl"] == "shared_projection"
    for job in document["jobs"]:
        task, info, entry = run._prepared(document, job)
        assert all(row["layer_impl"] == "shared_projection"
                   for row in (job, task["config"], info, entry))
        initial = run._initial(entry, info, job)
        assert initial["layer_impl"] == "shared_projection"
        assert initial["optimizer_steps"] == 0
        initialization = read_json(info["initialization"]["path"])
        assert initialization["layer_impl"] == "shared_projection"
    run.execute(path, allow_cpu_test=True)
    accepted = run.verify(path)
    assert accepted["completed_jobs"] == 2
    for result in accepted["results"].values():
        assert result["result"]["layer_impl"] == "shared_projection"
        attempt = Path(result["attempt"])
        assert read_json(attempt / "binding.json")["layer_impl"] == "shared_projection"
        for ck in ("best", "last"):
            assert read_json(attempt / (ck + ".json"))["binding"]["layer_impl"] == "shared_projection"


@pytest.mark.parametrize("damage", ["plan", "job", "config", "unknown"])
def test_consistently_resealed_plan_still_rejects_impl_disagreement(shared_plan, damage):
    path, document = shared_plan
    changed = copy.deepcopy(document)
    if damage == "plan":
        changed["layer_impl"] = "original"
    elif damage == "job":
        changed["jobs"][0]["layer_impl"] = "original"
    elif damage == "config":
        changed["tasks"]["synthetic_contract"]["config"]["layer_impl"] = "original"
    else:
        changed["layer_impl"] = "unknown"
    write_json(path, changed)
    seal_path = path.with_name("plan.seal.json")
    seal = read_json(seal_path)
    seal["plan_sha256"] = sha256(path)
    write_json(seal_path, seal)
    with pytest.raises(ValueError, match="layer_impl"):
        run._load_plan(path)


def test_initial_payload_impl_mismatch_rejected_after_outer_hash_update(shared_plan):
    _, document = shared_plan
    job = document["jobs"][0]
    _, info, entry = run._prepared(document, job)
    payload = run._initial(entry, info, job)
    payload["layer_impl"] = "original"
    torch.save(payload, entry["initial"]["path"])
    entry["initial"]["sha256"] = sha256(entry["initial"]["path"])
    with pytest.raises(ValueError, match="layer_impl"):
        run._initial(entry, info, job)


def test_result_impl_mismatch_rejected_after_receipt_hash_update(shared_plan):
    path, document = shared_plan
    job = document["jobs"][0]
    run.execute(path, only=run.job_id(job), allow_cpu_test=True)
    attempt = run._job_directory(path.parent, job) / "attempt_001"
    result = read_json(attempt / "result.json")
    result["layer_impl"] = "original"
    write_json(attempt / "result.json", result)
    receipt = read_json(attempt / "receipt.json")
    receipt["artifacts"]["result.json"] = sha256(attempt / "result.json")
    write_json(attempt / "receipt.json", receipt)
    with pytest.raises(ValueError, match="misbound"):
        run.verify(path, require_complete=False)


def test_cli_passes_explicit_layer_impl(monkeypatch, tmp_path):
    captured = {}
    def create(*args, **kwargs):
        captured.update(kwargs)
        return {"jobs": []}
    monkeypatch.setattr(run, "create_plan", create)
    run.main(["plan", "--store", "synthetic-store", "--output", str(tmp_path),
              "--layer-impl", "shared_projection"])
    assert captured["layer_impl"] == "shared_projection"
