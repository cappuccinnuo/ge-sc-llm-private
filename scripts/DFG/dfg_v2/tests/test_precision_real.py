"""Float64 diagnostic isolation and fixed-loop tests; synthetic graphs only."""
import copy
import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from scripts.DFG.experiments.common import tensor_digest, sha256, write_json
from scripts.DFG.dfg_v2.model import make_model, validate_registration
from scripts.DFG.dfg_v2.supervision import DfgV2Supervision
from scripts.DFG.dfg_v2.experiment.precision_gate import compare_gradients
from scripts.DFG.dfg_v2.experiment.precision_real import (
    diagnostic_default_dtype, make_diagnostic_copy, checked_diagnostic_inputs,
    input_identity, supervised_forward, diagnostic_config, trajectory_for_model,
    explain_zero_tensors, validate_static_evidence, validate_trajectory_evidence,
)
from scripts.DFG.dfg_v2.tests.test_model import hcg, augment


def config():
    return dict(initial_lr=.0002, max_lr=.005, weight_decay=0,
                schedule_epochs=50, div_factor=25, final_div_factor=10000,
                cycle_momentum=True, patience=7, delta=.001)


@pytest.mark.parametrize("fail", [False, True])
def test_dtype_context_restores_default_even_on_error(fail):
    assert torch.get_default_dtype() == torch.float32
    try:
        with diagnostic_default_dtype():
            assert torch.get_default_dtype() == torch.float64
            assert torch.zeros(2).dtype == torch.float64
            if fail:
                raise RuntimeError("deliberate")
    except RuntimeError:
        assert fail
    assert torch.get_default_dtype() == torch.float32


def test_nested_or_foreign_default_not_silently_overridden():
    with diagnostic_default_dtype():
        with pytest.raises(ValueError, match="float32"):
            with diagnostic_default_dtype():
                pass
        assert torch.get_default_dtype() == torch.float64
    assert torch.get_default_dtype() == torch.float32


@pytest.mark.parametrize("task", ["node", "contract"])
@pytest.mark.parametrize("profile", ["G0", "G3R"])
@pytest.mark.parametrize("impl", ["original", "shared_projection"])
def test_lossless_cast_preserves_source_and_production_rejects_double(hcg, task, profile, impl):
    graph = hcg if profile == "G0" else augment(hcg, profile)
    for _, row in graph.nodes(data=True):
        row["token"] = np.linspace(-.33, .42, 512).astype(np.float32)
    model = make_model(task, graph, profile, hidden_size=8, layers=2, heads=2, layer_impl=impl)
    before = input_identity(model)
    weights = tensor_digest(model.state_dict())
    converted, identity = make_diagnostic_copy(model)
    assert input_identity(model) == before
    assert tensor_digest(model.state_dict()) == weights
    assert identity["source_state_sha256"] == weights
    assert identity["source_input"]["features_sha256"] != identity["diagnostic_input"]["features_sha256"]
    assert identity["source_input"]["nx_graph_sha256"] == identity["diagnostic_input"]["nx_graph_sha256"]
    assert identity["diagnostic_state_sha256"] != weights
    assert validate_registration(model)
    with pytest.raises(ValueError, match="features"):
        validate_registration(converted)
    checked_diagnostic_inputs(converted, identity)
    part = DfgV2Supervision(converted, task, ["minimal.sol"])
    targets = part.targets(converted, {"minimal.sol": 1})
    assert targets.dtype == torch.long
    model.eval()
    converted.eval()
    with diagnostic_default_dtype(), torch.no_grad():
        logits = supervised_forward(converted, part)
        assert logits.dtype == torch.float64
        assert bool(torch.isfinite(logits).all())
    assert torch.get_default_dtype() == torch.float32
    assert input_identity(model) == before


@pytest.mark.parametrize("damage", ["feature", "label", "mask", "initial", "dtype"])
def test_diagnostic_identity_rejects_corruption(hcg, damage):
    source = make_model("node", hcg, "G0", hidden_size=8, layers=2, heads=2)
    model, identity = make_diagnostic_copy(source)
    if damage == "feature":
        typ = model.node_types[0]
        model.symmetrical_global_graph.nodes[typ].data["inp"][0, 0] += 1
    elif damage == "label":
        model.node_labels[0] = 1 - model.node_labels[0]
    elif damage == "mask":
        model.supervised_node_mask[0] = not model.supervised_node_mask[0]
    elif damage == "initial":
        with torch.no_grad():
            next(model.parameters()).add_(1)
    else:
        model.float()
    with pytest.raises(ValueError):
        checked_diagnostic_inputs(model, identity)
    assert validate_registration(source)


@pytest.mark.parametrize("field,bad", [("schedule_epochs", 3), ("patience", 3), ("delta", 0),
                                      ("initial_lr", -1), ("max_lr", float("nan")),
                                      ("weight_decay", -1), ("div_factor", 0)])
def test_freeze_numeric_rules(field, bad):
    c = config()
    c[field] = bad
    with pytest.raises(ValueError):
        diagnostic_config(c)


@pytest.mark.parametrize("task", ["node", "contract"])
def test_three_step_loop_same_seed_and_identity_no_outer_targets(hcg, task):
    outputs = []
    for impl in ("original", "shared_projection"):
        torch.manual_seed(7)
        source = make_model(task, hcg, "G0", hidden_size=8, layers=2, heads=2, layer_impl=impl)
        model, identity = make_diagnostic_copy(source)
        parts = dict(inner_train=DfgV2Supervision(model, task, ["minimal.sol"]),
                     inner_val=DfgV2Supervision(model, task, ["second.sol"]))
        class Forbidden:
            def targets(self, *args):
                raise AssertionError("Outer target accessed")
        parts["outer_test"] = Forbidden()
        with diagnostic_default_dtype():
            result = trajectory_for_model(model, parts, {"minimal.sol": 1, "second.sol": 0}, config(), 31)
        checked_diagnostic_inputs(model, identity, require_initial=False)
        outputs.append(result)
        assert result["optimizer_steps"] == 3
        assert result["schedule_steps"] == 3
        assert result["optimizer_schedule"]["initial_state"]["total_steps"] == 50
        assert len(result["history"]) == 3
        assert result["target_dtypes"] == {"train": "torch.int64", "inner_val": "torch.int64"}
        assert result["checkpoints_written"] is False and result["outer_targets_accessed"] is False
    assert outputs[0]["optimizer_schedule"] == outputs[1]["optimizer_schedule"]
    for a, b in zip(outputs[0]["history"], outputs[1]["history"]):
        assert a["lr"] == b["lr"]
        assert a["adam_beta1"] == b["adam_beta1"]
        assert abs(a["train_loss"] - b["train_loss"]) <= 1e-9
        assert abs(a["inner_val_loss"] - b["inner_val_loss"]) <= 1e-9
    assert torch.get_default_dtype() == torch.float32


def static_report():
    forward = dict(maximum_absolute_difference=0., bitwise_equal=True, tolerance=1e-12, passed=True)
    gradient = compare_gradients({"p": torch.ones(1, dtype=torch.float64)},
                                 {"p": torch.ones(1, dtype=torch.float64)})
    return dict(status="passed", device="cpu", dtype="float64", fold=0, seed=1,
                layers=[{"t": forward}], logits=forward, forward_passed=True,
                gradient_comparison=gradient,
                identity=dict(source_dtype="float32", diagnostic_dtype="float64",
                              lossless_state_and_features=True, original_unchanged=True))


def test_static_record_recomputes_gradient_decision():
    report = static_report()
    assert validate_static_evidence(report) is report
    report["gradient_comparison"]["gradients"]["p"]["tolerance"] = 1.
    with pytest.raises(ValueError):
        validate_static_evidence(report)


@pytest.mark.parametrize("damage", ["gradient", "forward", "dtype", "lossless", "missing_layer"])
def test_static_evidence_does_not_trust_passed_flag(damage):
    report = static_report()
    if damage == "gradient":
        report["gradient_comparison"]["passed"] = False
    elif damage == "forward":
        report["logits"]["maximum_absolute_difference"] = 1e-4
    elif damage == "dtype":
        report["identity"]["diagnostic_dtype"] = "float32"
    elif damage == "lossless":
        report["identity"]["lossless_state_and_features"] = False
    else:
        report["layers"] = []
    with pytest.raises(ValueError):
        validate_static_evidence(report)


def test_zero_gradient_explanation_uses_reachable_training_support():
    support = dict(node_type_names_by_index=["a", "b"],
        output_nodes_reaching_train_by_layer=[{"a": 0, "b": 2}],
        canonical_training_path_support=[[dict(canonical=["a", "r", "b"],
            reachable_edges=2, reachable_destinations_with_multiple_edges=0)]])
    rows = explain_zero_tensors(["gcs.0.k_linears.0.bias", "gcs.0.q_linears.0.weight",
        "gcs.0.q_linears.1.weight", "arbitrary.weight"], support)
    assert "softmax" in rows[0]["reason"]
    assert "No node" in rows[1]["reason"]
    assert "at most one" in rows[2]["reason"]
    assert rows[3]["mathematical_claim"] is False
