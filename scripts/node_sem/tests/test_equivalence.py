import copy
from types import SimpleNamespace
import pytest
import torch

from scripts.node_sem.equivalence import assert_exact, comparison_binding, snapshot, compare_fits


def test_exact_nested_comparison_rejects_tiny_optimizer_difference():
    left = {"state": {0: {"exp_avg": torch.tensor([1e-7])}}, "groups": [{"lr": 0.01}]}
    right = copy.deepcopy(left)
    assert_exact(left, right)
    right["state"][0]["exp_avg"][0] += 1e-10
    with pytest.raises(AssertionError, match="Tensor differs"):
        assert_exact(left, right)


def test_nonfeature_binding_comparison_does_not_hide_labels_or_initialization():
    original = {"labels": {"sha256": "a"}, "initial_state_sha256": "b", "feature_npz": "old"}
    new = dict(original, feature_npz="new", nodesem_version="v1", feature_spec={"name": "S0"})
    assert_exact(comparison_binding(original), comparison_binding(new))
    new["labels"] = {"sha256": "changed"}
    with pytest.raises(AssertionError):
        assert_exact(comparison_binding(original), comparison_binding(new))


def test_snapshot_uses_the_actual_heterograph_input():
    import dgl
    graph = dgl.heterograph({("stmt", "next", "stmt"): ([0], [1])}, num_nodes_dict={"stmt": 2})
    graph.nodes["stmt"].data["inp"] = torch.ones(2, 3)
    model = SimpleNamespace(state_dict=lambda: {"weight": torch.ones(2)},
        symmetrical_global_graph=graph, etypes_dict={("stmt", "next", "stmt"): 0},
        ntypes_dict={"stmt": 0}, original_graph_node_ids=["original_a", "original_b"])
    value = snapshot(model)
    assert torch.equal(value["inp"]["stmt"], torch.ones(2, 3))
    graph.nodes["stmt"].data["inp"].zero_()
    assert torch.equal(value["inp"]["stmt"], torch.ones(2, 3))
    assert value["original_ids"] == ["original_a", "original_b"]


def test_compare_fits_checks_best_and_last_optimizer_and_predictions():
    state = {"weight": torch.tensor([0.25])}
    checkpoint = dict(state_dict=state, state_sha256="digest", optimizer={"step": 2},
                      scheduler={"last_epoch": 2}, epoch=1, monitor={"counter": 0})
    old = dict(before={"state": state}, after=state, binding={"labels": "frozen"},
        history=[{"epoch": 0, "train_loss": 0.8, "seconds": 1.2},
                 {"epoch": 1, "train_loss": 0.7, "seconds": 1.3}],
        checkpoints={"best": copy.deepcopy(checkpoint), "last": copy.deepcopy(checkpoint)},
        predictions={"outer_test": [{"file": "f.sol", "best": 1, "prob": 0.6}]},
        result={"best_epoch": 1, "last_epoch": 1}, constructor_seconds=1.0, fit_seconds=2.0)
    new = copy.deepcopy(old)
    new["history"][0]["seconds"] = 50.0
    assert compare_fits(old, new)["passed"]
    new["checkpoints"]["best"]["optimizer"]["step"] = 1
    with pytest.raises(AssertionError):
        compare_fits(old, new)
    new = copy.deepcopy(old)
    new["predictions"]["outer_test"][0]["prob"] = 0.60000000001
    with pytest.raises(AssertionError):
        compare_fits(old, new)


def test_prepare_creates_spec_parent_before_materializing_carrier(tmp_path, monkeypatch):
    import json
    import scripts.node_sem.equivalence as module
    from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
    audit_path = tmp_path / "audit.json"
    input_path = tmp_path / "input.json"
    input_path.write_text("{}")
    source_ref = ref(input_path)
    proof = dict(job=dict(task_id="example_node", profile="G0", fold=0, seed=1),
                 initial=source_ref, receipt=source_ref, passed=True)
    audit_path.write_text(json.dumps(dict(passed=True, count=60, plan=source_ref, checks=[proof])))
    monkeypatch.setattr(module, "DIGEST_AUDIT", audit_path)
    monkeypatch.setattr(module, "h8", SimpleNamespace(
        load=lambda path: {}, prepared=lambda plan, job: (
            {"feature_view": source_ref}, {}, {"initial": source_ref, "graph": source_ref})))
    monkeypatch.setattr(module, "read_graph", lambda path: object())
    out = tmp_path / "new_nested" / "acceptance"
    class MaterializationBoundary(Exception):
        pass
    def carrier(*args):
        assert (out / "specs" / "example_node.json").is_file()
        raise MaterializationBoundary()
    monkeypatch.setattr(module, "write_carrier", carrier)
    with pytest.raises(MaterializationBoundary):
        module.prepare(out)


def test_run_creates_fit_parent_before_frozen_trainer_entry(tmp_path, monkeypatch):
    import scripts.node_sem.equivalence as module
    job = dict(task_id="reentrancy_node", profile="G3R", fold=0, seed=1)
    monkeypatch.setattr(module, "execution", SimpleNamespace(
        load=lambda path: {"source_h8_plan": {}, "jobs": [job]},
        historical_job=lambda plan, target: target))
    monkeypatch.setattr(module, "checked", lambda ref: tmp_path)
    monkeypatch.setattr(module, "h8", SimpleNamespace(load=lambda path: {}))
    class FitBoundary(Exception):
        pass
    def fit(*args):
        folder = args[-1]
        assert folder.parent.is_dir()
        assert not folder.exists()
        raise FitBoundary()
    monkeypatch.setattr(module, "_one_fit", fit)
    with pytest.raises(FitBoundary):
        module.run(tmp_path)
    assert (tmp_path / "failure.json").is_file()
