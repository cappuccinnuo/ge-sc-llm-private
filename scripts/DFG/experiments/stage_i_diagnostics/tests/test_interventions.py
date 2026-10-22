"""CPU-only synthetic HCG tests of the exact production Stage G adapter."""
import copy
import json
import types

import pytest
import torch

from scripts.DFG.experiments.common import tensor_digest
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.experiments.e23_pilot.model import make_model, validate_registration
from scripts.DFG.experiments.e23_pilot.tests.test_model import graphs
from scripts.DFG.experiments.audit.ddg_diagnostics_v1.test_interventions import (
    snapshot, unchanged,
)
from scripts.DFG.experiments.stage_i_diagnostics.interventions import (
    intervention, RELATIONS,
)


@pytest.fixture(autouse=True)
def cpu_threads():
    before = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(before)


def toy(task="node", variant="E3b"):
    torch.manual_seed(77)
    return make_model(task, graphs()[variant], hidden_size=8, layers=2, heads=2).eval()


def forward(model):
    return model() if model._stage_g_task == "node" else model(["train.sol", "val.sol"])[0]


@pytest.mark.parametrize("task", ["node", "contract"])
@pytest.mark.parametrize("record", [False, True])
def test_normal_bitwise_native_and_preserves_all_inputs(task, record):
    model = toy(task)
    graph = model.symmetrical_global_graph
    before = snapshot(model, graph)
    nx_before = fingerprint(model.nx_graph)
    ids = list(model.original_graph_node_ids)
    with torch.no_grad():
        expected = forward(model)
        with intervention(model, record=record) as ctx:
            actual = forward(model)
        assert torch.equal(expected, actual)
        assert torch.equal(expected, forward(model))
    assert bool(ctx.audit["layers"]) == record
    json.dumps(ctx.audit, allow_nan=False)
    assert nx_before == fingerprint(model.nx_graph)
    assert ids == model.original_graph_node_ids
    unchanged(model, graph, before)
    validate_registration(model)
    assert all("forward" not in layer.__dict__ for layer in model.gcs)
    assert "multi_update_all" not in graph.__dict__


@pytest.mark.parametrize("relations", [
    ("STATE_DEF_USE",), ("STATE_ACCESS_ORDER",),
    ("EXTERNAL_CALL_BEFORE_STATE_WRITE",),
    ("STATE_ACCESS_ORDER", "EXTERNAL_CALL_BEFORE_STATE_WRITE"),
    tuple(sorted(RELATIONS)),
])
def test_targeted_zero_equals_independent_relation_msg_zero(relations):
    model = toy()
    expected = copy.deepcopy(model)
    graph = model.symmetrical_global_graph
    before = snapshot(model, graph)
    with torch.no_grad():
        for layer in expected.gcs:
            for canonical, eid in layer.edge_dict.items():
                if canonical[1] in relations:
                    layer.relation_msg[eid].zero_()
        with intervention(model, relations) as ctx:
            actual = forward(model)
        assert torch.equal(actual, forward(expected))
        assert not torch.equal(actual, forward(model))
    for layer in ctx.audit["layers"].values():
        selected = [r for r in layer["canonical"].values() if r["masked"]]
        assert selected and all(r["effective_aggregate_l2_sum"] == 0 for r in selected)
        assert all(r["zeroed_aggregate_l2_sum"] > 0 for r in selected)
        ddg = [r for r in layer["canonical"].values() if r["canonical"][1] == "DATA_DEF_USE"]
        assert ddg and all(not r["masked"] and r["zeroed_aggregate_l2_sum"] == 0 for r in ddg)
    unchanged(model, graph, before)
    validate_registration(model)


def test_first_layer_base_messages_and_cross_mean_divisor_unchanged():
    model = toy()
    with torch.no_grad():
        with intervention(model) as normal:
            forward(model)
        with intervention(model, tuple(RELATIONS)) as zero:
            forward(model)
    normal_layer, zero_layer = normal.audit["layers"]["0"], zero.audit["layers"]["0"]
    for key, row in normal_layer["canonical"].items():
        other = zero_layer["canonical"][key]
        assert row["cross_mean_relation_count"] == other["cross_mean_relation_count"]
        assert row["original_aggregate_l2_sum"] == other["original_aggregate_l2_sum"]
        if row["canonical"][1] not in RELATIONS:
            assert row == other
    assert {k: r["cross_mean_relation_count"] for k,r in normal_layer["cross_mean"].items()} == {
        k: r["cross_mean_relation_count"] for k,r in zero_layer["cross_mean"].items()}


@pytest.mark.parametrize("task", ["node", "contract"])
def test_absent_requested_relation_is_bitwise_noop(task):
    model = toy(task, "E3a")
    with torch.no_grad():
        expected = forward(model)
        with intervention(model, ("EXTERNAL_CALL_BEFORE_STATE_WRITE",)) as ctx:
            assert torch.equal(expected, forward(model))
    for layer in ctx.audit["layers"].values():
        assert layer["present_requested_relations"] == []
        assert layer["absent_requested_relations"] == ["EXTERNAL_CALL_BEFORE_STATE_WRITE"]


def test_exception_restores_graph_frames_parameters_hooks_and_forward():
    model = toy()
    graph = model.symmetrical_global_graph
    before = snapshot(model, graph)
    def fail(*args):
        raise RuntimeError("injected failure")
    handle = model.gcs[0].a_linears[0].register_forward_hook(fail)
    hooks = {id(m): len(m._forward_hooks) for m in model.modules()}
    with pytest.raises(RuntimeError, match="injected failure"):
        with torch.no_grad(), intervention(model, tuple(RELATIONS)):
            forward(model)
    assert hooks == {id(m): len(m._forward_hooks) for m in model.modules()}
    assert all("forward" not in layer.__dict__ for layer in model.gcs)
    assert all("_ddg_diagnostic_owner" not in layer.__dict__ for layer in model.gcs)
    assert "multi_update_all" not in graph.__dict__
    unchanged(model, graph, before)
    handle.remove()
    validate_registration(model)
    with torch.no_grad():
        assert torch.isfinite(forward(model)).all()


def test_preexisting_instance_attributes_restore_exact_identity():
    model = toy()
    graph = model.symmetrical_global_graph
    layer = model.gcs[0]
    original = layer.forward
    def custom(this, graph, hidden):
        return original(graph, hidden)
    layer.forward = types.MethodType(custom, layer)
    previous_forward = layer.forward
    native_multi = graph.multi_update_all
    def custom_multi(this, *args, **kwargs):
        return native_multi(*args, **kwargs)
    graph.multi_update_all = types.MethodType(custom_multi, graph)
    previous_multi = graph.multi_update_all
    with torch.no_grad(), intervention(model, ("STATE_DEF_USE",)):
        forward(model)
    assert layer.forward is previous_forward
    assert graph.multi_update_all is previous_multi


def test_context_cannot_change_other_model_instance_or_global_methods():
    model, other = toy(), toy()
    layer_class = type(model.gcs[0])
    original_class_forward = layer_class.forward
    original_other_forward = other.gcs[0].forward
    before = tensor_digest(other.state_dict())
    with torch.no_grad():
        native = forward(other)
        with intervention(model, tuple(RELATIONS)):
            forward(model)
            assert torch.equal(native, forward(other))
            assert other.gcs[0].forward == original_other_forward
            assert layer_class.forward is original_class_forward
    assert before == tensor_digest(other.state_dict())


def test_repeated_forwards_aggregate_scalars_not_node_arrays():
    model = toy()
    with torch.no_grad(), intervention(model, ("STATE_DEF_USE",)) as ctx:
        first = forward(model)
        assert torch.equal(first, forward(model))
    for layer in ctx.audit["layers"].values():
        assert layer["forward_calls"] == 2
        assert all(r["observations"] == 2 for r in layer["canonical"].values())
    assert not ctx.rows and not ctx.representations
    json.dumps(ctx.audit, allow_nan=False)


def test_invalid_modes_training_grad_enabled_and_nested_rejected():
    model = toy()
    with pytest.raises(ValueError, match="Only state/order"):
        intervention(model, ("DATA_DEF_USE",))
    with pytest.raises(TypeError, match="sequence"):
        intervention(model, "STATE_DEF_USE")
    model.train()
    with pytest.raises(ValueError, match="eval"):
        with intervention(model):
            pass
    model.eval()
    with pytest.raises(ValueError, match="no_grad"):
        with intervention(model):
            forward(model)
    assert all("forward" not in layer.__dict__ for layer in model.gcs)
    with torch.no_grad(), intervention(model):
        with pytest.raises(RuntimeError, match="Nested"):
            with intervention(model):
                pass
        assert torch.isfinite(forward(model)).all()
