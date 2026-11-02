import copy
import numpy as np
import pytest
import torch
from torch import nn

from scripts.DFG.dfg_v2.model import make_model, validate_registration
from scripts.DFG.dfg_v2.benchmark_v2.spelling_features import assemble
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.support import model_support, gradient_audit
from scripts.node_sem.model import make_nodesem_model, validate
from scripts.node_sem.tests.carrier_fixtures import (
    make_spelling_fixture, token_spec, FixtureTokenEncoder,
)

CONFIG = dict(hidden_size=128, layers=2, heads=8, reducer="mean", layer_impl="shared_projection")


@pytest.mark.parametrize("task", ["node", "contract"])
@pytest.mark.parametrize("profile", ["G0", "G3R"])
def test_s0_preserves_original_parameters_features_forward_and_rng(tmp_path, task, profile):
    fixture = make_spelling_fixture(tmp_path, profile == "G3R")
    graph = fixture["graph"]
    before = graph_fingerprint(graph)
    torch.manual_seed(411)
    old = make_model(task, assemble(graph, fixture["view_ref"]), profile,
                     hidden_size=128, layers=2, heads=8, reducer="mean", layer_impl="shared_projection")
    old_rng = torch.get_rng_state().clone()
    torch.manual_seed(411)
    model = make_nodesem_model(task, graph, profile, token_spec(fixture), CONFIG)
    assert torch.equal(old_rng, torch.get_rng_state())
    assert list(old.state_dict()) == list(model.state_dict())
    assert all(torch.equal(value, model.state_dict()[key]) for key, value in old.state_dict().items())
    assert all(type(a) is nn.Linear and a.in_features == 512 for a in model.adapt_ws)
    old.eval()
    model.eval()
    with torch.no_grad():
        expected = old() if task == "node" else old(["train.sol", "val.sol", "test.sol"])[0]
        actual = model() if task == "node" else model(["train.sol", "val.sol", "test.sol"])[0]
    assert torch.equal(expected, actual)
    assert validate(model, token_spec(fixture)) == validate_registration(model)
    assert graph_fingerprint(graph) == before


@pytest.mark.parametrize("task", ["node", "contract"])
def test_s1_shared_embedding_parameter_count_forward_backward_and_registration(tmp_path, monkeypatch, task):
    from scripts.node_sem import model as module
    monkeypatch.setattr(module, "TokenEncoder", FixtureTokenEncoder)
    fixture = make_spelling_fixture(tmp_path, True)
    baseline = make_nodesem_model(task, fixture["graph"], "G3R", token_spec(fixture), CONFIG)
    spec = token_spec(fixture, "S1")
    model = make_nodesem_model(task, fixture["graph"], "G3R", spec, CONFIG)
    assert len(model.adapt_ws) == len(baseline.adapt_ws)
    assert model.in_size == 513
    assert all(a.token_bag is model.nodesem_shared["token_bag"] for a in model.adapt_ws)
    assert [k for k in model.state_dict() if "token_bag" in k] == ["nodesem_shared.token_bag.weight"]
    expected_delta = 32 * 64 + 128 + len(model.adapt_ws) * (64 - 512) * 128
    assert sum(p.numel() for p in model.parameters()) - sum(p.numel() for p in baseline.parameters()) == expected_delta
    output = model() if task == "node" else model(["train.sol", "val.sol"])[0]
    output.square().mean().backward()
    assert model.nodesem_shared["token_bag"].weight.grad is not None
    assert torch.isfinite(model.nodesem_shared["token_bag"].weight.grad).all()
    assert all(a.token_projection.weight.grad is not None for a in model.adapt_ws)
    validate(model, spec)
    model.adapt_ws = nn.ModuleList(list(model.adapt_ws)[:-1])
    with pytest.raises(ValueError, match="count"):
        validate(model, spec)


@pytest.mark.parametrize("task", ["node", "contract"])
@pytest.mark.parametrize("layers", [None, 0])
def test_explicit_zero_layers_is_not_replaced_by_configuration(tmp_path, task, layers):
    fixture = make_spelling_fixture(tmp_path)
    spec = token_spec(fixture, layers=layers)
    model = make_nodesem_model(task, fixture["graph"], "G0", spec, CONFIG)
    assert model.num_layers == (2 if layers is None else 0)
    assert len(model.gcs) == model.num_layers
    output = model() if task == "node" else model(["train.sol", "val.sol"])[0]
    output.square().mean().backward()
    support = model_support(model, dict(inner_train=["train.sol"], inner_val=["val.sol"], outer_test=["test.sol"]))
    audit = gradient_audit(model, support)
    assert audit is not None
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())


def test_zero_layers_rejected_for_ddg_profile(tmp_path):
    fixture = make_spelling_fixture(tmp_path, True)
    with pytest.raises(ValueError, match="Zero-layer"):
        make_nodesem_model("node", fixture["graph"], "G3R", token_spec(fixture, layers=0), CONFIG)


@pytest.mark.parametrize("field", ["spec_digest", "carrier_shape", "wrong_adapter", "wrong_shared", "wrong_offsets", "wrong_layer_count"])
def test_model_validation_rejects_registration_corruption(tmp_path, monkeypatch, field):
    from scripts.node_sem import model as module
    monkeypatch.setattr(module, "TokenEncoder", FixtureTokenEncoder)
    fixture = make_spelling_fixture(tmp_path, True)
    spec = token_spec(fixture, "S1")
    model = make_nodesem_model("node", fixture["graph"], "G3R", spec, CONFIG)
    if field == "spec_digest":
        model.nodesem_spec_sha256 = "0" * 64
    elif field == "carrier_shape":
        model.nodesem_carrier_record["feature_shape"][1] += 1
    elif field == "wrong_adapter":
        model.adapt_ws[0] = nn.Linear(513, 128)
    elif field == "wrong_offsets":
        model.nodesem_shared["token_bag"] = nn.EmbeddingBag(32, 64, include_last_offset=True)
    elif field == "wrong_layer_count":
        model.num_layers = 0
    else:
        model.nodesem_shared["token_bag"] = nn.EmbeddingBag(31, 64)
    with pytest.raises(ValueError):
        validate(model, spec)
