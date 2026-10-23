"""Numerical and support semantics of the optional diagnostic reducer."""

import hashlib
from pathlib import Path

import dgl
import pytest
import torch

from sco_models.model_hgt import HGTLayer
from scripts.DFG.dfg_v2.hgt_layer import FROZEN_HGT_SHA256, HGTLayerNonEmptyMean


def _layer(graph, cls, width=4, use_norm=False):
    return cls(
        width, width,
        {name: index for index, name in enumerate(graph.ntypes)},
        {name: index for index, name in enumerate(graph.canonical_etypes)},
        n_heads=2, dropout=0.0, use_norm=use_norm,
    )


def _dense_graph():
    ids = torch.arange(3)
    return dgl.heterograph({
        ('a', 'relation_z', 'b'): (ids, ids),
        ('b', 'relation_a', 'b'): (ids, ids),
        ('b', 'relation_x', 'a'): (ids, ids),
        ('a', 'relation_q', 'a'): (ids, ids),
    }, num_nodes_dict={'a': 3, 'b': 3})


def _identity_message_layer(graph):
    layer = _layer(graph, HGTLayerNonEmptyMean, width=2)
    with torch.no_grad():
        for linear in layer.k_linears:
            linear.weight.zero_()
            linear.bias.zero_()
        for linear in layer.q_linears:
            linear.weight.zero_()
            linear.bias.zero_()
        for linear in list(layer.v_linears) + list(layer.a_linears):
            linear.weight.copy_(torch.eye(2))
            linear.bias.zero_()
        layer.relation_msg.fill_(1.0)  # two one-dimensional heads
        layer.skip.zero_()             # sigmoid = 1/2
    return layer


def test_copied_forward_source_provenance():
    root = Path(__file__).resolve().parents[4]
    assert hashlib.sha256((root / 'sco_models/model_hgt.py').read_bytes()).hexdigest() == FROZEN_HGT_SHA256


@pytest.mark.parametrize('use_norm', [False, True])
def test_dense_relations_equal_frozen_layer_and_parameter_allocation(use_norm):
    graph = _dense_graph()
    torch.manual_seed(777)
    original = _layer(graph, HGTLayer, use_norm=use_norm)
    original_next_random = torch.rand(9)
    torch.manual_seed(777)
    diagnostic = _layer(graph, HGTLayerNonEmptyMean, use_norm=use_norm)
    diagnostic_next_random = torch.rand(9)
    assert torch.equal(original_next_random, diagnostic_next_random)
    assert list(original.state_dict()) == list(diagnostic.state_dict())
    for key, tensor in original.state_dict().items():
        assert torch.equal(tensor, diagnostic.state_dict()[key]), key
    features = {name: torch.randn(3, 4) for name in graph.ntypes}
    expected = original(graph, features)
    actual = diagnostic(graph, features)
    for name in graph.ntypes:
        assert torch.allclose(actual[name], expected[name], atol=1e-6, rtol=0), name
    # In the all-supported case the backward computation must also agree.
    original_loss = sum(value.square().sum() for value in expected.values())
    diagnostic_loss = sum(value.square().sum() for value in actual.values())
    original_loss.backward()
    diagnostic_loss.backward()
    for (name, parameter), (other_name, other_parameter) in zip(
        original.named_parameters(), diagnostic.named_parameters()
    ):
        assert name == other_name
        assert (parameter.grad is None) == (other_parameter.grad is None)
        if parameter.grad is not None:
            assert torch.allclose(parameter.grad, other_parameter.grad, atol=1e-6, rtol=1e-6), name


def test_sparse_mean_ignores_absent_relations_and_zero_degree_message():
    graph = dgl.heterograph({
        ('statement', 'relation_a', 'statement'): ([0, 0], [0, 1]),
        ('statement', 'relation_b', 'statement'): ([1], [0]),
        ('statement', 'registered_empty', 'statement'): ([], []),
    }, num_nodes_dict={'statement': 3})
    diagnostic = _identity_message_layer(graph)
    original = _layer(graph, HGTLayer, width=2)
    original.load_state_dict(diagnostic.state_dict())
    features = {'statement': torch.tensor([[2., 4.], [6., 8.], [10., 12.]], requires_grad=True)}
    # Node 0 gets two relations, node 1 one, node 2 none. The third
    # registered relation has zero edges and must never enter the divisor.
    expected_message = torch.tensor([[4., 6.], [2., 4.], [0., 0.]])
    actual = diagnostic(graph, features)['statement']
    expected = .5 * expected_message + .5 * features['statement']
    assert torch.allclose(actual, expected, atol=1e-6, rtol=0)
    baseline = original(graph, features)['statement']
    assert not torch.allclose(actual[:2], baseline[:2], atol=1e-6, rtol=0)
    assert torch.equal(actual[2], .5 * features['statement'][2])
    actual.sum().backward()
    assert torch.isfinite(features['statement'].grad).all()
    for name in ('relation_a', 'relation_b'):
        index = diagnostic.edge_dict[('statement', name, 'statement')]
        assert diagnostic.relation_msg.grad[index].abs().sum().item() > 0
    # The absent relation has no supervised message path.
    empty = diagnostic.edge_dict[('statement', 'registered_empty', 'statement')]
    assert diagnostic.relation_msg.grad[empty].abs().sum().item() == 0
    assert not list(graph.nodes['statement'].data.keys())
    assert all(not list(graph.edges[e].data.keys()) for e in graph.canonical_etypes)


def test_forward_only_environment_type_has_zero_incoming_message():
    graph = dgl.heterograph({
        ('env_source', 'ENV_FLOW', 'statement'): ([0], [0]),
    }, num_nodes_dict={'env_source': 1, 'statement': 2})
    layer = _identity_message_layer(graph)
    features = {
        'env_source': torch.tensor([[4., 8.]], requires_grad=True),
        'statement': torch.tensor([[2., 6.], [10., 12.]], requires_grad=True),
    }
    actual = layer(graph, features)
    assert torch.equal(actual['env_source'], .5 * features['env_source'])
    assert torch.equal(actual['statement'][0], torch.tensor([3., 7.]))
    assert torch.equal(actual['statement'][1], torch.tensor([5., 6.]))
    # Environment sources are unsupervised but must receive gradients through
    # the supervised destination; no incoming ENV relation is needed.
    actual['statement'].square().sum().backward()
    assert features['env_source'].grad.abs().sum().item() > 0
    assert layer.relation_msg.grad.abs().sum().item() > 0
    assert all(not list(graph.nodes[t].data.keys()) for t in graph.ntypes)
