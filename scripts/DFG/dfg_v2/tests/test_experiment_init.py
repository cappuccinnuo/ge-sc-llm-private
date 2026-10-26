"""Prompt 7 semantic-family tests on small CPU HCGs; no optimizer steps."""
import math
import pytest
import torch

from scripts.DFG.dfg_v2.tests.test_model import hcg, augment
from scripts.DFG.dfg_v2.model import make_model
from scripts.DFG.dfg_v2.experiment.init import (
    INITIALIZATION_VERSION, NEW_RELATION_POLICY, seeds, initialize_family,
    semantic_state, full_bank_bound, parameter_seed,
)
from scripts.DFG.experiments.protocol import _state_digest

PROFILES = ("G0", "G1R", "G2R", "G3R", "G3")


def family(hcg, profiles=PROFILES, task="node", anchor_seed=10000, reducer="mean"):
    result = {}
    for profile in profiles:
        torch.manual_seed(anchor_seed if profile == "G0" else 99)
        graph = hcg if profile == "G0" else augment(hcg, profile)
        result[profile] = make_model(task, graph, profile, hidden_size=16,
                                     layers=2, heads=4, reducer=reducer)
    return result


@pytest.mark.parametrize("task", ["node", "contract"])
def test_anchor_shared_parameters_semantic_not_integer_rows(hcg, task):
    models = family(hcg, task=task)
    before = _state_digest(models["G0"].state_dict())
    versions = {n: p._version for n, p in models["G0"].named_parameters()}
    rng = torch.get_rng_state().clone()
    record = initialize_family(models, 10000)
    assert record["initialization_version"] == INITIALIZATION_VERSION
    assert record["new_relation_policy"] == NEW_RELATION_POLICY
    anchor = semantic_state(models["G0"])
    assert any(models["G0"].ntypes_dict[t] != models["G3R"].ntypes_dict[t]
               for t in models["G0"].ntypes_dict)
    assert any(models["G0"].etypes_dict[c] != models["G3R"].etypes_dict[c]
               for c in models["G0"].etypes_dict)
    for profile, model in models.items():
        values = semantic_state(model)
        for key, tensor in anchor.items():
            assert torch.equal(tensor, values[key]), (profile, key)
        assert record["profiles"][profile]["shared_semantic_sha256"] == _state_digest(anchor)
        assert record["profiles"][profile]["state_sha256"] == _state_digest(model.state_dict())
    assert _state_digest(models["G0"].state_dict()) == before
    assert {n: p._version for n, p in models["G0"].named_parameters()} == versions
    assert torch.equal(rng, torch.get_rng_state())


@pytest.mark.parametrize("profiles", [
    ("G0", "G3"), ("G0", "G1R"), ("G0", "G2R", "G3R"),
    ("G3R", "G2R", "G1R", "G3", "G0"),
])
def test_repeat_and_family_composition_independence(hcg, profiles):
    all_models = family(hcg)
    all_record = initialize_family(all_models, 10000)
    subset = family(hcg, profiles)
    subset_record = initialize_family(subset, 10000)
    for profile in profiles:
        assert subset_record["profiles"][profile] == all_record["profiles"][profile]
        assert _state_digest(subset[profile].state_dict()) == _state_digest(all_models[profile].state_dict())
    repeat = initialize_family(subset, 10000)
    assert repeat == subset_record


def test_new_relation_draws_respect_profile_full_bank_bounds(hcg):
    models = family(hcg)
    initialize_family(models, 10000)
    for profile in PROFILES[1:]:
        model = models[profile]
        for layer_idx, layer in enumerate(model.gcs):
            for attr in ("relation_att", "relation_msg"):
                bank = getattr(layer, attr).detach()
                bound = full_bank_bound(bank)
                assert bound == math.sqrt(6.0 / ((bank.shape[0] + bank.shape[1]) *
                                                bank.shape[2] * bank.shape[3]))
                for canonical, index in model.etypes_dict.items():
                    if canonical in models["G0"].etypes_dict:
                        continue
                    generator = torch.Generator(device="cpu")
                    generator.manual_seed(parameter_seed(10000, "gcs.%d.%s" % (layer_idx, attr), canonical))
                    expected = torch.empty_like(bank[index]).uniform_(-bound, bound, generator=generator)
                    assert torch.equal(expected, bank[index])
                    assert float(bank[index].abs().max()) <= bound
                    assert torch.equal(layer.relation_pri[index], torch.ones_like(layer.relation_pri[index]))
    # The user-approved policy deliberately does NOT promise exact new rows
    # across unequal banks, while their isolated normalized draws are aligned.
    first, last = models["G1R"], models["G3R"]
    canonical = next(c for c in first.etypes_dict if c[1] == "DATA_DEF_USE")
    a = first.gcs[0].relation_msg[first.etypes_dict[canonical]]
    b = last.gcs[0].relation_msg[last.etypes_dict[canonical]]
    assert not torch.equal(a, b)
    assert torch.allclose(a / full_bank_bound(first.gcs[0].relation_msg),
                          b / full_bank_bound(last.gcs[0].relation_msg), atol=1e-7, rtol=1e-6)


def test_auxiliary_node_parameters_exact_across_g3_and_g3r(hcg):
    models = family(hcg)
    initialize_family(models, 10000)
    a, b = semantic_state(models["G3"]), semantic_state(models["G3R"])
    keys = [key for key in a if "|env_source" in key and "relation_" not in key]
    assert keys
    for key in keys:
        assert torch.equal(a[key], b[key]), key
    model = models["G3"]
    index = model.ntypes_dict["env_source"]
    for prefix, module in [("adapt_ws", model.adapt_ws[index])] + [
            ("gcs.%d.%s" % (i, name), getattr(layer, name)[index])
            for i, layer in enumerate(model.gcs)
            for name in ("k_linears", "q_linears", "v_linears", "a_linears")]:
        for suffix in ("weight", "bias"):
            tensor = getattr(module, suffix).detach()
            generator = torch.Generator(device="cpu")
            generator.manual_seed(parameter_seed(10000, prefix + "." + suffix, "env_source"))
            bound = 1 / math.sqrt(module.in_features)
            expected = torch.empty_like(tensor).uniform_(-bound, bound, generator=generator)
            assert torch.equal(tensor, expected)
    for layer in model.gcs:
        assert torch.equal(layer.norms[index].weight, torch.ones_like(layer.norms[index].weight))
        assert torch.equal(layer.norms[index].bias, torch.zeros_like(layer.norms[index].bias))
        assert float(layer.skip[index]) == 1


def test_seed_one_and_multiseed_rules():
    for task, count, offset in [("node", 10, 0), ("contract", 5, 1000)]:
        for fold in range(count):
            expected = 10000 + offset + fold
            assert seeds(task, fold) == {"constructor": expected, "fit": expected + 1000000}
            for seed in (2, 3):
                assert seeds(task, fold, seed)["constructor"] == expected + 100000 * (seed - 1)


@pytest.mark.parametrize("task,fold,seed", [
    ("other", 0, 1), ("node", -1, 1), ("node", 10, 1),
    ("contract", 5, 1), ("contract", True, 1), ("node", 0, 0),
    ("node", 0, True), ("node", 0, 1.0),
])
def test_invalid_seed_identity_rejected(task, fold, seed):
    with pytest.raises(ValueError):
        seeds(task, fold, seed)


@pytest.mark.parametrize("damage", ["gradient", "steps", "profile", "schema", "shape", "missing", "duplicate"])
def test_nonfresh_or_mismatched_family_rejected_without_mutating_anchor(hcg, damage):
    models = family(hcg, ("G0", "G3R"))
    anchor_sha = _state_digest(models["G0"].state_dict())
    if damage == "gradient":
        next(models["G3R"].parameters()).grad = torch.zeros_like(next(models["G3R"].parameters()))
    elif damage == "steps":
        models["G3R"]._dfg_optimizer_steps = 1
    elif damage == "profile":
        models["G3R"].dfg_profile = "G3"
    elif damage == "schema":
        models["G3R"].etypes_dict[next(iter(models["G3R"].etypes_dict))] += 50
    elif damage == "shape":
        torch.manual_seed(33)
        models["G3R"] = make_model("node", augment(hcg, "G3R"), "G3R",
                                   hidden_size=8, heads=4, layers=2)
    elif damage == "missing":
        models = {"G3R": models["G3R"]}
    elif damage == "duplicate":
        models["G3R"] = models["G0"]
    with pytest.raises((ValueError, AssertionError)):
        initialize_family(models, 10000)
    if "G0" in models:
        assert _state_digest(models["G0"].state_dict()) == anchor_sha


def test_diagnostic_reducer_changes_no_initial_parameters(hcg):
    a, b = family(hcg), family(hcg, reducer="nonempty_mean")
    ar, br = initialize_family(a, 10000), initialize_family(b, 10000)
    assert ar == br
