import copy
import pytest
import torch
from torch import nn

from scripts.node_sem import TOKEN_IDS
from scripts.node_sem.feature_spec import FeatureSpec
from scripts.node_sem.adapter import NodeSemAdapter
from scripts.node_sem import checkpoint_io
from scripts.node_sem.init import initial_state, checked_initial
from scripts.DFG.dfg_v2.experiment.init import seeds
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
from scripts.DFG.experiments.common import tensor_digest


def specification(name):
    return FeatureSpec(name, "anonymous",
        [dict(name=TOKEN_IDS, dim=512, manifest=None, normalize=False)],
        "raw_linear" if name == "S0" else "embed_pool",
        "raw_linear" if name == "S0" else "concat")


def model(name):
    value = nn.Module()
    value.dfg_task, value.dfg_profile = "node", "G0"
    value.gcs = nn.ModuleList([nn.Linear(128, 128)])
    value.classify = nn.Linear(128, 2)
    if name == "S0":
        value.adapt_ws = nn.ModuleList([nn.Linear(512, 128) for _ in range(2)])
    else:
        value.nodesem_shared = nn.ModuleDict(dict(token_bag=nn.EmbeddingBag(32, 64, mode="mean")))
        value.adapt_ws = nn.ModuleList([NodeSemAdapter(specification(name), str(i),
            value.nodesem_shared) for i in range(2)])
    return value


def sealed(tmp_path, monkeypatch, changes=None):
    monkeypatch.setattr(checkpoint_io, "GENERATED_ROOT", tmp_path)
    old = model("S0")
    state = {k: v.clone() for k, v in old.state_dict().items()}
    sf = seeds("node", 0, 1)
    payload = dict(kind="untrained_initial", optimizer_steps=0, task_id="fixture_node",
        fold=0, seed=1, profile="G0", constructor_seed=sf["constructor"],
        fit_seed=sf["fit"], state_dict=state, state_sha256=tensor_digest(state))
    if changes:
        payload.update(changes)
    path = tmp_path / "initial.pt"
    torch.save(payload, str(path))
    return dict(ref(path), state_sha256=payload["state_sha256"]), payload


def test_s0_exact_historical_all_parameters(tmp_path, monkeypatch):
    reference, payload = sealed(tmp_path, monkeypatch)
    receiving = model("S0")
    state, sha = initial_state(receiving, specification("S0"), "fixture_node", 0, "G0", reference)
    assert sha == payload["state_sha256"]
    assert state.keys() == payload["state_dict"].keys()
    assert all(torch.equal(value, payload["state_dict"][key]) for key, value in state.items())


def test_s1_shared_copy_new_parameters_deterministic_global_rng_unchanged(tmp_path, monkeypatch):
    reference, payload = sealed(tmp_path, monkeypatch)
    receiver = model("S1")
    before = {k: v.clone() for k, v in receiver.state_dict().items()}
    rng = torch.random.get_rng_state().clone()
    first, digest1 = initial_state(receiver, specification("S1"), "fixture_node", 0, "G0", reference)
    second, digest2 = initial_state(model("S1"), specification("S1"), "fixture_node", 0, "G0", reference)
    assert digest1 == digest2
    assert all(torch.equal(first[k], second[k]) for k in first)
    # Initial-state computation itself does not mutate its receiver.
    assert all(torch.equal(v, before[k]) for k, v in receiver.state_dict().items())
    for key in first:
        if key.startswith(("gcs.", "classify.")):
            assert torch.equal(first[key], payload["state_dict"][key])
    assert torch.count_nonzero(first["nodesem_shared.token_bag.weight"][0]) == 0
    assert [k for k in first if k.startswith("nodesem_shared.")] == ["nodesem_shared.token_bag.weight"]
    torch.random.set_rng_state(rng)
    initial_state(receiver, specification("S1"), "fixture_node", 0, "G0", reference)
    assert torch.equal(rng, torch.random.get_rng_state())


@pytest.mark.parametrize("changes", [
    {"kind": "best"}, {"optimizer_steps": 1}, {"fold": 1}, {"seed": 2},
    {"profile": "G3R"}, {"task_id": "other_node"}, {"fit_seed": 9},
    {"constructor_seed": 9}, {"state_sha256": "a" * 64},
])
def test_initial_identity_and_digest_rejected(tmp_path, monkeypatch, changes):
    reference, _ = sealed(tmp_path, monkeypatch, changes)
    with pytest.raises(ValueError):
        checked_initial(reference, "fixture_node", 0, "G0")


def test_file_digest_checked_before_deserialization(tmp_path, monkeypatch):
    reference, _ = sealed(tmp_path, monkeypatch)
    with open(reference["path"], "ab") as stream:
        stream.write(b"tamper")
    with pytest.raises(ValueError):
        checked_initial(reference, "fixture_node", 0, "G0")


def test_parameter_dictionary_and_shape_fail_closed(tmp_path, monkeypatch):
    reference, _ = sealed(tmp_path, monkeypatch)
    receiver = model("S1")
    receiver.classify = nn.Linear(64, 2)
    with pytest.raises(ValueError, match="shape"):
        initial_state(receiver, specification("S1"), "fixture_node", 0, "G0", reference)
    receiver = model("S1")
    receiver.extra = nn.Parameter(torch.zeros(1))
    with pytest.raises(ValueError, match="Unexpected"):
        initial_state(receiver, specification("S1"), "fixture_node", 0, "G0", reference)


def test_trained_receiver_gradients_rejected(tmp_path, monkeypatch):
    reference, _ = sealed(tmp_path, monkeypatch)
    receiver = model("S1")
    next(receiver.parameters()).grad = torch.zeros_like(next(receiver.parameters()))
    with pytest.raises(ValueError, match="untrained"):
        initial_state(receiver, specification("S1"), "fixture_node", 0, "G0", reference)
