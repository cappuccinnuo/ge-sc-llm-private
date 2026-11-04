import copy
import types

import dgl
import dgl.function as fn
import pytest
import torch

from sco_models.model_hgt import HGT
from scripts.DFG.experiments.audit.ddg_diagnostics_v1.interventions import DiagnosticContext

torch.set_num_threads(2)


def toy(with_ddg=True):
    torch.manual_seed(77)
    data = {("s", "next", "s"): ([0, 1, 2, 3], [1, 2, 3, 0]),
            ("p", "arg", "s"): ([0, 1], [0, 2])}
    if with_ddg:
        data[("s", "DATA_DEF_USE", "s")] = ([0, 2], [2, 1])
    graph = dgl.heterograph(data, num_nodes_dict={"s": 4, "p": 2})
    for t in graph.ntypes:
        graph.nodes[t].data["inp"] = torch.randn(graph.num_nodes(t), 4)
        graph.nodes[t].data["label"] = torch.arange(graph.num_nodes(t)) % 2
    edge_dict = {c: i for i, c in enumerate(graph.canonical_etypes)}
    for c, i in edge_dict.items():
        graph.edges[c].data["id"] = torch.full((graph.num_edges(c),), i, dtype=torch.long)
    model = HGT(graph, {t: i for i, t in enumerate(graph.ntypes)}, edge_dict,
                4, 4, 2, 2, 2).eval()
    return model, graph


def snapshot(model, graph):
    return (copy.deepcopy(model.state_dict()), [id(p) for p in model.parameters()],
            {t: {k: v.clone() for k, v in graph.nodes[t].data.items()} for t in graph.ntypes},
            {c: (tuple(t.clone() for t in graph.edges(etype=c, order="eid")),
                 {k: v.clone() for k, v in graph.edges[c].data.items()})
             for c in graph.canonical_etypes})


def unchanged(model, graph, before):
    state, identities, nodes, edges = before
    assert identities == [id(p) for p in model.parameters()]
    assert state.keys() == model.state_dict().keys()
    assert all(torch.equal(v, model.state_dict()[k]) for k, v in state.items())
    for t, fields in nodes.items():
        assert fields.keys() == graph.nodes[t].data.keys()
        assert all(torch.equal(v, graph.nodes[t].data[k]) for k, v in fields.items())
    for c, (endpoints, fields) in edges.items():
        assert all(torch.equal(a, b) for a, b in zip(endpoints, graph.edges(etype=c)))
        assert fields.keys() == graph.edges[c].data.keys()
        assert all(torch.equal(v, graph.edges[c].data[k]) for k, v in fields.items())


@pytest.mark.parametrize("record", [False, True])
def test_normal_wrapper_is_bit_exact_native_and_restores(record):
    model, graph = toy()
    before = snapshot(model, graph)
    with torch.no_grad():
        native = model(graph, "s")
        with DiagnosticContext(model, record=record,
                               node_files_by_type={"s": ["a"]*2+["b"]*2, "p": ["a", "b"]}) as ctx:
            wrapped = model(graph, "s")
        assert torch.equal(native, wrapped)
        assert torch.equal(native, model(graph, "s"))
    assert bool(ctx.rows) == record
    assert all("forward" not in layer.__dict__ for layer in model.gcs)
    assert "multi_update_all" not in graph.__dict__
    unchanged(model, graph, before)


def test_zero_is_actual_two_layer_message_zero_not_attention_only():
    model, graph = toy()
    before = snapshot(model, graph)
    with torch.no_grad():
        with DiagnosticContext(model, mode="zero", record=True) as ctx:
            zero = model(graph, "s")
        expected_model = copy.deepcopy(model)
        for layer in expected_model.gcs:
            for canonical, eid in layer.edge_dict.items():
                if canonical[1] == "DATA_DEF_USE":
                    layer.relation_msg[eid].zero_()
        assert torch.equal(zero, expected_model(graph, "s"))
        assert not torch.equal(zero, model(graph, "s"))
    for layer_index in (0, 1):
        ddg = [r for r in ctx.rows if r["layer"] == layer_index and
               r["branch"] == "ddg_sum" and r["node_type"] == "s"]
        assert ddg and all(r["max"] == 0 for r in ddg)
    unchanged(model, graph, before)


def test_first_layer_base_messages_and_cross_mean_divisor_unchanged_in_zero():
    model, graph = toy()
    with torch.no_grad():
        with DiagnosticContext(model, record=True) as normal:
            model(graph, "s")
        with DiagnosticContext(model, mode="zero", record=True) as zero:
            model(graph, "s")
    def get(ctx, branch):
        return [r for r in ctx.rows if r["layer"] == 0 and r["branch"] == branch]
    assert get(normal, "base_sum") == get(zero, "base_sum")
    assert [r["cross_mean_relation_count"] for r in get(normal, "total_cross_mean")] == [
        r["cross_mean_relation_count"] for r in get(zero, "total_cross_mean")]


def test_zero_without_ddg_is_exact_noop():
    model, graph = toy(False)
    with torch.no_grad():
        native = model(graph, "s")
        with DiagnosticContext(model, mode="zero", record=True):
            assert torch.equal(native, model(graph, "s"))


def test_exception_restores_graph_features_hooks_parameters_and_forward():
    model, graph = toy()
    before = snapshot(model, graph)
    def fail(*args):
        raise RuntimeError("injected failure after message passing")
    handle = model.gcs[0].a_linears[0].register_forward_hook(fail)
    hooks_before = {id(m): len(m._forward_hooks) for m in model.modules()}
    with pytest.raises(RuntimeError, match="injected failure"):
        with DiagnosticContext(model, mode="zero", record=True):
            model(graph, "s")
    assert hooks_before == {id(m): len(m._forward_hooks) for m in model.modules()}
    assert all("forward" not in layer.__dict__ for layer in model.gcs)
    assert all("_ddg_diagnostic_owner" not in layer.__dict__ for layer in model.gcs)
    assert "multi_update_all" not in graph.__dict__
    unchanged(model, graph, before)
    handle.remove()
    with torch.no_grad():
        model(graph, "s")


def test_preexisting_instance_forward_and_graph_method_restored_by_identity():
    model, graph = toy()
    layer = model.gcs[0]
    original = layer.forward
    def custom(this, g, h):
        return original(g, h)
    layer.forward = types.MethodType(custom, layer)
    custom_bound = layer.forward
    native_multi = graph.multi_update_all
    def graph_custom(this, *args, **kwargs):
        return native_multi(*args, **kwargs)
    graph.multi_update_all = types.MethodType(graph_custom, graph)
    graph_bound = graph.multi_update_all
    with torch.no_grad(), DiagnosticContext(model):
        model(graph, "s")
    assert layer.forward is custom_bound
    assert graph.multi_update_all is graph_bound


def test_capture_is_opt_in_cpu_and_record_switch_does_not_change_output():
    model, graph = toy()
    with torch.no_grad():
        with DiagnosticContext(model, capture_representations=True) as first:
            out1 = model(graph, "s")
        with DiagnosticContext(model, record=True, capture_representations=True) as second:
            out2 = model(graph, "s")
    assert torch.equal(out1, out2)
    assert first.rows == []
    assert len(first.representations) == 8
    assert first.representations.keys() == second.representations.keys()
    assert all(x.device.type == "cpu" for x in first.representations.values())
    assert all(torch.equal(v, second.representations[k]) for k, v in first.representations.items())


def test_dgl_mean_includes_zero_message_at_node_without_ddg_incoming():
    graph = dgl.heterograph({("s", "next", "s"): ([0, 0], [0, 1]),
                            ("s", "DATA_DEF_USE", "s"): ([0], [0])})
    graph.nodes["s"].data["v"] = torch.ones(2, 1)
    graph.multi_update_all({c: (fn.copy_u("v", "m"), fn.sum("m", "t"))
                            for c in graph.canonical_etypes}, cross_reducer="mean")
    assert torch.equal(graph.nodes["s"].data["t"], torch.tensor([[1.], [.5]]))


def test_no_labels_read_and_near_zero_denominators_are_separate():
    model, graph = toy()
    for layer in model.gcs:
        with torch.no_grad():
            layer.relation_msg.zero_()
    with torch.no_grad():
        with DiagnosticContext(model, record=True) as ctx:
            before = model(graph, "s")
        for t in graph.ntypes:
            graph.nodes[t].data["label"] = 1 - graph.nodes[t].data["label"]
        with DiagnosticContext(model, record=True):
            after = model(graph, "s")
    assert torch.equal(before, after)
    ratio = [r for r in ctx.rows if r["branch"] == "ddg_to_base_ratio"]
    assert ratio and all(r["count"] == 0 and r["denominator_near_zero_count"] > 0 for r in ratio)
