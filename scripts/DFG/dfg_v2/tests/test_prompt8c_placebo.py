"""CPU-only dilution proof; no model fit or production profile mutation."""
import copy
import pytest
import torch
from scripts.DFG.dfg_v2 import PROFILES
from scripts.DFG.dfg_v2.diagnostics8c.placebo import (
    placeholder_canonicals, make_placebo_data, numerical_denominator_proof)


def test_placebo_preserves_original_types_and_exact_counts():
    base = [("a", "real", "b"), ("b", "base", "a")]
    extra = placeholder_canonicals(base, {"a": 3, "b": 5}, ["a", "b"])
    assert len(extra) == 6
    assert sum(c[2] == "a" for c in base + extra) == 3
    assert sum(c[2] == "b" for c in base + extra) == 5
    assert all(c[0] == c[2] and c[0] in ("a", "b") for c in extra)
    assert "G0P" not in PROFILES


@pytest.mark.parametrize("targets", [{"a": 0, "b": 3}, {"a": 2}, {"a": 2, "b": 3, "env_source": 1}])
def test_refuse_deleted_or_auxiliary_target_schema(targets):
    with pytest.raises(ValueError):
        placeholder_canonicals([("a", "x", "b"), ("b", "y", "a")], targets, ["a", "b"])


def test_placeholder_edges_empty_original_endpoints_untouched():
    base = {("a", "x", "a"): (torch.tensor([0, 1]), torch.tensor([1, 0]))}
    saved = copy.deepcopy(base)
    expanded = make_placebo_data(base, {"a": 4}, ["a"])
    assert len(expanded) == 4
    for c in base:
        assert all(torch.equal(x, y) for x, y in zip(base[c], saved[c]))
        assert all(torch.equal(x, y) for x, y in zip(base[c], expanded[c]))
    assert all(len(s) == len(t) == 0 for c, (s, t) in expanded.items() if c not in base)


def test_cpu_numerical_proof_preserves_rng_and_nontrivial_dilution():
    rng = torch.random.get_rng_state().clone()
    proof = numerical_denominator_proof()
    assert torch.equal(rng, torch.random.get_rng_state())
    assert proof["status"] == "passed" and proof["fits_executed"] == 0
    for row in proof["records"]:
        assert row["max_abs_message_formula_error"] <= 1e-6
        assert row["max_abs_layer_output_formula_error"] <= 1e-6
        assert row["max_abs_actual_output_change"] > 0
