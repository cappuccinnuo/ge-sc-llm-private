from argparse import Namespace
import copy
import json
import pytest
import torch
from scripts.DFG.experiments.tests.test_runtime import graph_fixture, create_model
from scripts.DFG.experiments.tests.test_paper_runtime import rare_graph, SPLIT
from scripts.DFG.experiments.paper_protocol import NAME, VERSION, INITIALIZATION_VERSION, FORWARD_SCOPE, SCORE_ROLE
from scripts.DFG.experiments.paper_runtime import Supervision, graph_schema_and_support, validate_registration
from scripts.DFG.experiments import paper_run, paper_checkpoint, run_experiment
from scripts.DFG.experiments.common import read_json, tensor_digest, ROOT


@pytest.fixture(autouse=True)
def threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def binding_for(model):
    return {"protocol": NAME, "protocol_version": VERSION, "initialization_version": INITIALIZATION_VERSION,
            "forward_scope": FORWARD_SCOPE, "score_role": SCORE_ROLE,
            "registered_schema": validate_registration(model)}


def fit(tmp_path, task, graph, monkeypatch=None):
    model = create_model(tmp_path, task, graph)
    config = paper_run.effective_config(task, Namespace(mode="smoke", seed=1, epochs=50,
                                                        smoke_epochs=3, device="cpu", threads=1))
    config.update(hidden_size=16, heads=4)
    parts = {name: Supervision(model, task, SPLIT[name + "_files"]) for name in ("train", "val")}
    binding = binding_for(model)
    result = paper_run.fit_variant(model, parts, task, {f: 1 for f in (
        "train.sol", "valid.sol", "test.sol")}, config, tmp_path / "E1", binding,
        list(graph), graph_schema_and_support(graph, SPLIT))
    return model, binding, result


@pytest.mark.parametrize("task", ["node", "contract"])
@pytest.mark.parametrize("validation_only_ddg", [False, True])
def test_real_training_cv_naming_checkpoints_predictions_and_no_ddg_support(tmp_path, task, validation_only_ddg):
    graph = rare_graph() if validation_only_ddg else graph_fixture()
    model, binding, result = fit(tmp_path, task, graph)
    assert result["history_rows"] == 3
    assert result["score_role"] == "cv_validation"
    assert "outer_test" not in result
    assert result["checkpoint_roundtrip_exact"] == {"best": True, "last": True}
    assert result["no_parameters_created_during_training_or_scoring"]
    dest = tmp_path / "E1"
    history = [json.loads(s) for s in (dest / "history.jsonl").read_text().splitlines()]
    assert result["best_cv_validation_loss"] == min(r["cv_validation_loss"] for r in history)
    assert result["best_epoch"] == min(range(3), key=lambda i: history[i]["cv_validation_loss"])
    predictions = read_json(dest / "cv_validation_predictions.json")
    assert not (dest / "outer_predictions.json").exists()
    assert {p["file"] for p in predictions} == {"valid.sol", "test.sol"}
    if task == "node":
        expected_ids = [n for n, d in graph.nodes(data=True) if d["source_file"] != "train.sol"]
        assert [p["original_graph_node_id"] for p in predictions] == expected_ids
        assert len(predictions) == (9 if validation_only_ddg else 8)
    else:
        assert len(predictions) == 2
    assert read_json(dest / "model_input.json")["node_count"] == len(graph)
    for ck in ("best", "last"):
        obj = torch.load(str(dest / (ck + ".pt")), map_location="cpu")
        assert obj["binding"]["registered_schema"] == binding["registered_schema"]
        assert obj["monitor"]["best_cv_validation_loss"] == result["best_cv_validation_loss"] or ck == "best"
    relations = result["gradient_audit"]["epochs"][0]["ddg_relations"]
    if validation_only_ddg:
        assert all(r["status"] == "no_training_ddg_support" and r["message_gradient_l1"] == 0 for r in relations)
        if task == "node":
            assert result["gradient_audit"]["ddg_message_update_l1"] == 0
    else:
        assert any(r["message_gradient_l1"] > 0 for r in relations)


@pytest.mark.parametrize("change", ["protocol", "scope", "role", "schema", "feature", "label", "dictionary"])
def test_checkpoint_rejects_binding_input_and_schema_changes_before_loading(tmp_path, monkeypatch, change):
    model, binding, result = fit(tmp_path, "node", graph_fixture())
    path = tmp_path / "E1" / "best.pt"
    altered = copy.deepcopy(binding)
    if change == "protocol":
        altered["protocol_version"] = "ddg-nested-paired-v1"
    elif change == "scope":
        altered["forward_scope"] = "isolated_file_subgraphs"
    elif change == "role":
        altered["score_role"] = "independent_outer_test"
    elif change == "schema":
        altered["registered_schema"]["canonical_relations"][0]["index"] = 999
    elif change == "feature":
        model.nx_graph.nodes[0]["token"][0] += 1
    elif change == "label":
        model.node_labels[0] = 1 - model.node_labels[0]
    else:
        model.etypes_dict.pop(next(iter(model.etypes_dict)))
    previous = tensor_digest(model.state_dict())
    monkeypatch.setattr(model, "load_state_dict", lambda *a, **k: pytest.fail("Loaded before validation"))
    with pytest.raises(ValueError):
        paper_checkpoint.restore_checkpoint(path, model, altered, result["checkpoint_sha256"]["best"])
    assert tensor_digest(model.state_dict()) == previous


def test_nested_alias_delegates_without_reinterpreting_existing_runner(tmp_path, monkeypatch):
    from scripts.DFG.experiments import run_pair
    sentinel = {"status": "blocked_unseen_training_schema"}
    seen = []
    monkeypatch.setattr(run_experiment, "protocol_output", lambda path, name: tmp_path)
    def legacy(args):
        seen.append(args)
        return sentinel
    monkeypatch.setattr(run_pair, "run", legacy)
    args = Namespace(protocol="nested_strict", output=str(tmp_path))
    assert run_experiment.run(args) is sentinel
    assert seen == [args]
    assert read_json(tmp_path / "protocol_alias.json")["legacy_runner_unmodified"]


def test_paper_dispatch_never_uses_graphview_runner(monkeypatch):
    args = Namespace(protocol="paper_kfold")
    monkeypatch.setattr(paper_run, "run", lambda supplied: supplied)
    assert run_experiment.run(args) is args
