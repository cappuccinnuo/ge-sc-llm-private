import torch
from scripts.node_sem.p1b_acceptance import probe, R4Adapter
from scripts.node_sem import model as module
from scripts.node_sem.tests.carrier_fixtures import make_spelling_fixture, token_spec, FixtureTokenEncoder
from scripts.node_sem.tests.test_model import CONFIG
from scripts.node_sem.tests.test_adapter import carrier, shared, spec


def test_scale_probe_preserves_parameters_and_reports_first_layer(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "TokenEncoder", FixtureTokenEncoder)
    fixture = make_spelling_fixture(tmp_path, True)
    model = module.make_nodesem_model("node", fixture["graph"], "G3R",
                                     token_spec(fixture, "S1"), CONFIG)
    before = {k: v.clone() for k, v in model.state_dict().items()}
    observed = probe(model)
    assert observed["score_or_label_access"] is False
    assert observed["no_optimizer"] and observed["actual_device"] == "cpu"
    assert set(observed["h0"]) == set(model.ntypes_dict)
    assert set(observed["first_layer_before_norm"]) == set(model.ntypes_dict)
    assert set(observed["first_layer_after_norm"]) == set(model.ntypes_dict)
    assert len(observed["attention"]) == len(model.symmetrical_global_graph.canonical_etypes)
    assert all(torch.equal(value, before[key]) for key, value in model.state_dict().items())
    assert all(p.grad is None for p in model.parameters())


def test_r4_diagnostic_uses_original_pooled_linear_without_norm():
    owner = shared()
    adapter = R4Adapter(spec(), "return", owner)
    inp = carrier([[], [1, 2]])
    with torch.no_grad():
        owner["token_norm"].weight.fill_(20)
        owner["token_norm"].bias.fill_(3)
    expected = adapter.token_projection(adapter.pooled_tokens(inp))
    assert torch.equal(adapter(inp), expected)
    del owner["token_norm"]
    assert torch.equal(adapter(inp), expected)
