"""S1 exact pooling and once-only shared-parameter registration."""
import pytest
import torch
from torch import nn

from scripts.node_sem import ANON, CODE, TOKEN_IDS
from scripts.node_sem.adapter import NodeSemAdapter
from scripts.node_sem.feature_spec import FeatureSpec


def spec(**changes):
    values = dict(name="S1", view=ANON, modalities=[
        dict(name=TOKEN_IDS, dim=512, manifest=None, normalize=False)],
        token_mode="embed_pool", fusion="concat", modality_dropout=0.0,
        layers=None)
    values.update(changes)
    return FeatureSpec(**values)


def shared(vocab=13):
    result = nn.ModuleDict({"token_bag": nn.EmbeddingBag(vocab, 64, mode="mean"), "token_norm": nn.LayerNorm(64)})
    with torch.no_grad():
        result["token_bag"].weight.copy_(
            torch.arange(vocab * 64, dtype=torch.float32).reshape(vocab, 64) / 16)
    return result


def carrier(rows):
    inp = torch.zeros(len(rows), 513)
    for index, ids in enumerate(rows):
        inp[index, 0] = int(bool(ids))
        inp[index, 1:1+len(ids)] = torch.tensor(ids, dtype=torch.float32)
    return inp


def test_pooling_matches_hand_calculated_mean_and_empty_rows():
    table = shared()
    adapter = NodeSemAdapter(spec(), "expression_statement", table)
    rows = [[], [1], [2, 3, 2], [], [12, 5], []]
    inp = carrier(rows)
    actual = adapter.pooled_tokens(inp)
    expected = torch.stack([
        table["token_bag"].weight[ids].mean(0) if ids else torch.zeros(64)
        for ids in rows
    ])
    assert torch.allclose(actual, expected, atol=1e-6, rtol=0)
    assert torch.equal(adapter.pooled_tokens(carrier([[], []])), torch.zeros(2, 64))
    assert adapter.pooled_tokens(carrier([])).shape == (0, 64)
    # Only the owning frozen forward applies GELU; adapter returns Linear.
    normalized = torch.zeros_like(expected)
    active = inp[:, 0] == 1
    normalized[active] = table["token_norm"](expected[active])
    assert torch.equal(adapter(inp), adapter.token_projection(normalized))
    assert torch.equal(adapter(inp)[0], adapter.token_projection.bias)


def test_bag_receives_flat_nonpadding_ids_and_offsets_only():
    adapter = NodeSemAdapter(spec(), "return", shared())
    observed = []
    hook = adapter.token_bag.register_forward_pre_hook(
        lambda module, args: observed.append(tuple(arg.clone() for arg in args)))
    inp = carrier([[], [1, 2], [], [3], []])
    adapter(inp)
    hook.remove()
    assert len(observed) == 1
    ids, offsets = observed[0]
    assert ids.ndim == offsets.ndim == 1
    assert ids.dtype == offsets.dtype == torch.long
    assert ids.tolist() == [1, 2, 3]
    assert offsets.tolist() == [0, 0, 2, 2, 3]
    # Pooling is recalculated from inp; there is no detached cached token path.
    inp[1, 1] = 5
    assert not torch.equal(adapter.pooled_tokens(inp)[1],
                           adapter.pooled_tokens(carrier([[], [1, 2], [], [3], []]))[1])


@pytest.mark.parametrize("damage", [
    "fraction", "negative", "beyond_vocab", "nan", "inf", "leading_padding",
    "middle_padding", "missing_presence", "fraction_presence", "false_presence",
    "wrong_width", "wrong_rank", "wrong_dtype",
])
def test_token_validation_before_integer_conversion(damage):
    adapter = NodeSemAdapter(spec(), "if", shared())
    inp = carrier([[1, 2]])
    if damage == "fraction":
        inp[0, 1] = 1.5
    elif damage == "negative":
        inp[0, 1] = -1
    elif damage == "beyond_vocab":
        inp[0, 1] = 13
    elif damage == "nan":
        inp[0, 1] = float("nan")
    elif damage == "inf":
        inp[0, 1] = float("inf")
    elif damage == "leading_padding":
        inp[0, 1] = 0
    elif damage == "middle_padding":
        inp[0, 2:4] = torch.tensor([0., 3.])
    elif damage == "missing_presence":
        inp[0, 0] = 0
    elif damage == "fraction_presence":
        inp[0, 0] = 0.5
    elif damage == "false_presence":
        inp = carrier([[]])
        inp[0, 0] = 1
    elif damage == "wrong_width":
        inp = inp[:, :-1]
    elif damage == "wrong_rank":
        inp = inp[0]
    elif damage == "wrong_dtype":
        inp = inp.double()
    with pytest.raises(ValueError):
        adapter(inp)


def test_seventeen_adapters_register_one_table_and_exact_parameter_count():
    owner = nn.Module()
    vocab, hidden, types = 32100, 128, 17
    owner.nodesem_shared = shared(vocab)
    owner.adapt_ws = nn.ModuleList([
        NodeSemAdapter(spec(), "type_" + str(i), owner.nodesem_shared, hidden)
        for i in range(types)
    ])
    weights = [name for name, _ in owner.named_parameters()
               if "token_bag" in name]
    assert weights == ["nodesem_shared.token_bag.weight"]
    assert [key for key in owner.state_dict() if "token_bag" in key] == weights
    assert all(adapter.token_bag is owner.nodesem_shared["token_bag"]
               for adapter in owner.adapt_ws)
    expected = vocab * 64 + 128 + types * (64 * hidden + hidden)
    actual = sum(parameter.numel() for parameter in owner.parameters())
    assert actual == expected
    baseline_adapters = types * (512 * hidden + hidden)
    assert actual - baseline_adapters == vocab * 64 + 128 - types * (512 - 64) * hidden
    norm_keys = ["nodesem_shared.token_norm.weight", "nodesem_shared.token_norm.bias"]
    assert [k for k in owner.state_dict() if "token_norm" in k] == norm_keys
    assert [k for k, _ in owner.named_parameters() if "token_norm" in k] == norm_keys
    assert all(a.token_norm is owner.nodesem_shared["token_norm"] for a in owner.adapt_ws)
    loss = sum(adapter(carrier([[1, 2], []])).sum() for adapter in owner.adapt_ws)
    loss.backward()
    grad = owner.nodesem_shared["token_bag"].weight.grad
    assert grad is not None and bool(torch.isfinite(grad).all())
    assert float(grad[1:3].abs().sum()) > 0
    assert float(grad[0].abs().sum()) == 0
    assert all(adapter.token_projection.weight.grad is not None for adapter in owner.adapt_ws)


def test_adapter_rejects_raw_and_supports_new_fusion():
    with pytest.raises(ValueError, match="original"):
        NodeSemAdapter(spec(name="S0", token_mode="raw_linear", fusion="raw_linear"),
                       "return", shared())
    for current in (
            spec(fusion="gated"), spec(modality_dropout=0.1),
            spec(modalities=[
                dict(name=TOKEN_IDS, dim=512, manifest=None, normalize=False),
                dict(name=CODE, dim=256, manifest=None, normalize=True)])):
        adapter = NodeSemAdapter(current, "return", shared())
        assert adapter.spec_digest == current.digest()


@pytest.mark.parametrize("table", [
    nn.ModuleDict(),
    nn.ModuleDict({"token_bag": nn.Embedding(13, 64)}),
    nn.ModuleDict({"token_bag": nn.EmbeddingBag(13, 128, mode="mean")}),
    nn.ModuleDict({"token_bag": nn.EmbeddingBag(13, 64, mode="sum")}),
])
def test_invalid_shared_embedding_rejected(table):
    with pytest.raises(ValueError):
        NodeSemAdapter(spec(), "return", table)


def test_norm_excludes_empty_rows_even_with_nonzero_affine_bias():
    table = shared()
    adapter = NodeSemAdapter(spec(), "return", table)
    with torch.no_grad():
        table["token_norm"].bias.fill_(3)
    seen = []
    hook = table["token_norm"].register_forward_pre_hook(
        lambda module, args: seen.append(args[0].detach().clone()))
    inp = carrier([[], [1, 2], []])
    actual = adapter(inp)
    hook.remove()
    assert len(seen) == 1 and seen[0].shape == (1, 64)
    assert torch.equal(actual[0], adapter.token_projection.bias)
    assert torch.equal(actual[2], adapter.token_projection.bias)
    # Match the batch shape: matrix-vector and matrix-matrix kernels need
    # not round identically even when the mathematical row is the same.
    expected = torch.zeros(3, 64)
    expected[1:2] = table["token_norm"](adapter.pooled_tokens(inp)[1:2])
    assert torch.equal(actual, adapter.token_projection(expected))
    adapter(carrier([[], []])).sum().backward()
    assert table["token_norm"].bias.grad is None
