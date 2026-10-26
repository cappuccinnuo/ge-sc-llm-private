"""Prompt 7b: cached type projections preserve the frozen layer computation.

The user approved the explicit mixed gradient gate after pure relative checks
failed on mathematically zero key-bias gradients: max(abs(a-b)) <= 1e-8 +
1e-5 * max(max(abs(a)), max(abs(b))). Tensor and elementwise relative diagnostics
are retained without epsilon floors or exclusion of near-zero entries. Original
failing evidence is preserved in prompt7b_v1/shared_projection_original_gate.log.
"""

import hashlib
import inspect
from pathlib import Path

import dgl
import pytest
import torch

from sco_models.model_hgt import HGTLayer
from scripts.DFG.dfg_v2.hgt_layer import (
    FROZEN_HGT_SHA256, HGTLayerNonEmptyMean,
    HGTLayerSharedProjection, HGTLayerSharedProjectionNonEmptyMean,
)

GRADIENT_ATOL = 1e-8
GRADIENT_RTOL = 1e-5

PAIRS = [
    (HGTLayer, HGTLayerSharedProjection),
    (HGTLayerNonEmptyMean, HGTLayerSharedProjectionNonEmptyMean),
]


def _graph(kind='mixed'):
    if kind == 'source_only':
        return dgl.heterograph({
            ('env_source', 'ENV_FLOW', 'statement'): ([0, 1], [0, 0]),
        }, num_nodes_dict={'env_source': 2, 'statement': 3})
    if kind == 'empty':
        return dgl.heterograph({
            ('a', 'registered_empty', 'b'): ([], []),
        }, num_nodes_dict={'a': 2, 'b': 3})
    return dgl.heterograph({
        ('a', 'same_relation', 'b'): ([0, 0, 1, 2], [0, 1, 1, 0]),
        ('a', 'other_relation', 'b'): ([2, 0, 1], [0, 0, 1]),
        # Relation string alone cannot identify a canonical relation.
        ('b', 'same_relation', 'a'): ([0, 1, 1], [0, 0, 1]),
        ('a', 'registered_empty', 'b'): ([], []),
        ('source_only', 'SOURCE', 'a'): ([0, 1], [0, 1]),
        ('a', 'TO_SINK', 'sink_only'): ([0, 1], [0, 0]),
    }, num_nodes_dict={
        'a': 3, 'b': 3, 'source_only': 2, 'sink_only': 2,
    })


def _layer(graph, cls, use_norm=False, dropout=0.2):
    return cls(
        8, 8,
        {name: i for i, name in enumerate(graph.ntypes)},
        {name: i for i, name in enumerate(graph.canonical_etypes)},
        n_heads=2, dropout=dropout, use_norm=use_norm,
    )


def _features(graph, dtype=torch.float32):
    return {name: torch.randn(graph.num_nodes(name), 8, dtype=dtype)
            for name in graph.ntypes}


def _loss(outputs):
    # Nonuniform readout avoids the exact cancellation of LayerNorm sums.
    return sum((value * torch.arange(1, 9, dtype=value.dtype)).square().mean()
               for value in outputs.values())


def _gradient_errors(left, right):
    absolute_tensor = (left - right).abs()
    absolute = absolute_tensor.max().item()
    denominator = torch.max(left.abs(), right.abs())
    scale = denominator.max().item()
    relative_elements = torch.where(denominator > 0, absolute_tensor / denominator, absolute_tensor)
    return {
        'max_absolute': absolute,
        'tensor_scale': scale,
        'relative_infinity': absolute / scale if scale else 0.0,
        'max_elementwise_relative': relative_elements.max().item(),
        'allowed_absolute': GRADIENT_ATOL + GRADIENT_RTOL * scale,
    }


def _assert_gradient_equal(left, right, identity):
    assert torch.isfinite(left).all() and torch.isfinite(right).all(), identity
    errors = _gradient_errors(left, right)
    assert errors['max_absolute'] <= errors['allowed_absolute'], (identity, errors)
    return errors


@pytest.mark.parametrize('original_cls,shared_cls', PAIRS)
@pytest.mark.parametrize('use_norm', [False, True])
def test_constructor_state_shapes_and_random_consumption(original_cls, shared_cls, use_norm):
    graph = _graph()
    torch.manual_seed(903)
    old = _layer(graph, original_cls, use_norm)
    next_old = torch.rand(13)
    torch.manual_seed(903)
    new = _layer(graph, shared_cls, use_norm)
    next_new = torch.rand(13)
    assert shared_cls.__init__ is original_cls.__init__
    assert list(old.state_dict()) == list(new.state_dict())
    for key, tensor in old.state_dict().items():
        assert tensor.shape == new.state_dict()[key].shape
        assert torch.equal(tensor, new.state_dict()[key]), key
    assert torch.equal(next_old, next_new)


@pytest.mark.parametrize('original_cls,shared_cls', PAIRS)
@pytest.mark.parametrize('use_norm', [False, True])
@pytest.mark.parametrize('kind', ['mixed', 'source_only', 'empty'])
def test_two_layers_eval_and_seeded_dropout_are_bitwise_equal(
        original_cls, shared_cls, use_norm, kind):
    graph = _graph(kind)
    torch.manual_seed(191)
    old_layers = [_layer(graph, original_cls, use_norm) for _ in range(2)]
    new_layers = [_layer(graph, shared_cls, use_norm) for _ in range(2)]
    for old, new in zip(old_layers, new_layers):
        new.load_state_dict(old.state_dict())
    features = _features(graph)
    for training in (False, True):
        old_h = dict(features)
        new_h = dict(features)
        for index, (old, new) in enumerate(zip(old_layers, new_layers)):
            old.train(training)
            new.train(training)
            torch.manual_seed(301 + index)
            old_h = old(graph, old_h)
            old_rng = torch.get_rng_state().clone()
            torch.manual_seed(301 + index)
            new_h = new(graph, new_h)
            assert torch.equal(old_rng, torch.get_rng_state())
            for ntype in graph.ntypes:
                assert torch.equal(old_h[ntype], new_h[ntype]), (training, index, ntype)
                assert torch.isfinite(new_h[ntype]).all()
    assert all(not list(graph.nodes[t].data) for t in graph.ntypes)
    assert all(not list(graph.edges[e].data) for e in graph.canonical_etypes)


@pytest.mark.parametrize('original_cls,shared_cls', PAIRS)
@pytest.mark.parametrize('use_norm', [False, True])
@pytest.mark.parametrize('seed', [1, 109, 512])
def test_float32_gradients_user_approved_mixed_gate(
        original_cls, shared_cls, use_norm, seed):
    graph = _graph()
    torch.manual_seed(seed)
    old = _layer(graph, original_cls, use_norm, dropout=0.0)
    new = _layer(graph, shared_cls, use_norm, dropout=0.0)
    new.load_state_dict(old.state_dict())
    old.eval()
    new.eval()
    old_h = {key: value.requires_grad_() for key, value in _features(graph).items()}
    new_h = {key: value.detach().clone().requires_grad_() for key, value in old_h.items()}
    old_out = old(graph, old_h)
    new_out = new(graph, new_h)
    assert all(torch.equal(old_out[key], new_out[key]) for key in old_out)
    _loss(old_out).backward()
    _loss(new_out).backward()
    for (name, a), (other_name, b) in zip(old.named_parameters(), new.named_parameters()):
        assert name == other_name
        assert (a.grad is None) == (b.grad is None), name
        if a.grad is not None:
            assert torch.isfinite(a.grad).all() and torch.isfinite(b.grad).all(), name
            _assert_gradient_equal(a.grad, b.grad, name)
    for name in old_h:
        _assert_gradient_equal(old_h[name].grad, new_h[name].grad, name)
    # Separate canonicals sharing a string must each participate in training.
    for canonical in [('a', 'same_relation', 'b'), ('b', 'same_relation', 'a')]:
        edge_id = new.edge_dict[canonical]
        assert new.relation_msg.grad[edge_id].abs().max().item() > 0
    empty_id = new.edge_dict[('a', 'registered_empty', 'b')]
    assert new.relation_msg.grad[empty_id].abs().max().item() == 0


@pytest.mark.parametrize('original_cls,shared_cls', PAIRS)
@pytest.mark.parametrize('use_norm', [False, True])
def test_float64_gradients_same_gate_with_elementwise_diagnostics(original_cls, shared_cls, use_norm):
    graph = _graph()
    torch.manual_seed(114)
    old = _layer(graph, original_cls, use_norm, dropout=0.0).double()
    new = _layer(graph, shared_cls, use_norm, dropout=0.0).double()
    new.load_state_dict(old.state_dict())
    features = _features(graph, dtype=torch.float64)
    _loss(old(graph, features)).backward()
    _loss(new(graph, features)).backward()
    for (name, a), (_, b) in zip(old.named_parameters(), new.named_parameters()):
        assert (a.grad is None) == (b.grad is None), name
        if a.grad is None:
            continue
        _assert_gradient_equal(a.grad, b.grad, name)


@pytest.mark.parametrize('original_cls,shared_cls', PAIRS)
def test_cached_projections_execute_once_per_type(original_cls, shared_cls):
    graph = _graph()
    old = _layer(graph, original_cls)
    new = _layer(graph, shared_cls)
    features = _features(graph)
    all_counts = []
    for layer in (old, new):
        calls = {}
        handles = []
        for kind in ('k', 'v', 'q'):
            for ntype, index in layer.node_dict.items():
                key = (kind, ntype)
                calls[key] = 0
                def count(module, inputs, output, key=key):
                    calls[key] += 1
                handles.append(getattr(layer, kind + '_linears')[index].register_forward_hook(count))
        layer.eval()
        layer(graph, features)
        for handle in handles:
            handle.remove()
        all_counts.append(calls)
    assert all(count == 1 for count in all_counts[1].values())
    assert all_counts[0][('k', 'a')] > 1
    assert all_counts[0][('q', 'b')] > 1
    assert all_counts[0][('q', 'source_only')] == 0


@pytest.mark.parametrize('original_cls,shared_cls', PAIRS)
def test_forward_only_changes_projection_placement(original_cls, shared_cls):
    """Guard against accidental reducer, dropout, residual or message changes."""
    before = inspect.getsource(original_cls.forward)
    after = inspect.getsource(shared_cls.forward)
    begin = after.index('            # These type-specific projections')
    end = after.index('            for srctype, etype, dsttype', begin)
    after = after[:begin] + after[end:]
    before_begin = before.index('                k_linear =')
    before_end = before.index('                e_id =', before_begin)
    after_begin = after.index('                k = projected_k')
    after_end = after.index('                e_id =', after_begin)
    assert before[:before_begin] + before[before_end:] == after[:after_begin] + after[after_end:]
    root = Path(__file__).resolve().parents[4]
    assert hashlib.sha256((root / 'sco_models/model_hgt.py').read_bytes()).hexdigest() == FROZEN_HGT_SHA256


@pytest.mark.parametrize('dtype', [torch.float32, torch.float64])
def test_mixed_gate_retains_near_zero_relative_evidence_and_rejects_larger_error(dtype):
    zeros = torch.zeros(3, dtype=dtype)
    identical = _assert_gradient_equal(zeros, zeros, 'both_zero')
    assert identical['relative_infinity'] == 0
    assert identical['max_elementwise_relative'] == 0
    tiny = torch.tensor([0., 1e-9, 0.], dtype=dtype)
    errors = _assert_gradient_equal(zeros, tiny, 'near_zero_cancellation')
    assert errors['relative_infinity'] == 1.0
    assert errors['max_elementwise_relative'] == 1.0
    with pytest.raises(AssertionError):
        _assert_gradient_equal(zeros, 100 * tiny, 'non_negligible_zero_mismatch')
    reference = torch.full((3,), 1e-3, dtype=dtype)
    with pytest.raises(AssertionError):
        _assert_gradient_equal(reference, reference + 1e-6, 'wrong_nonzero_gradient')
