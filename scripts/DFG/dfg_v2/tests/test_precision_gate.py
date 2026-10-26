"""Prompt 7b.2 pure gradient gate: boundaries, failures, preserved evidence."""
from copy import deepcopy

import pytest
import torch

from scripts.DFG.dfg_v2.experiment.precision_gate import (
    compare_gradients, compare_gradient_records, rejudge_small,
)
from scripts.DFG.dfg_v2.experiment.precision_validation import (
    small_case, strict_gradient_difference,
)


def tensor(values):
    return torch.tensor(values, dtype=torch.float64)


def test_near_zero_residuals_use_global_scale_without_excluding_bias():
    old = {"weight": tensor([2., -1.]), "key.bias": tensor([2e-17])}
    new = {"weight": tensor([2., -1.]), "key.bias": tensor([-1e-17])}
    result = compare_gradients(old, new)
    assert result["passed"]
    assert result["global_reference_scale"] == 2.
    assert result["absolute_term"] == 2e-12
    assert result["zero_tensors"] == ["key.bias"]
    assert result["unpaired_zero_tensors"] == []
    bias = result["gradients"]["key.bias"]
    assert not bias["passed"]  # old P7b.1 decision remains visible
    assert bias["relative_difference"] > 1.
    assert bias["original_tolerance"] == 1e-10
    assert bias["mixed_passed"]
    assert bias["zero_in_reference"] and bias["zero_in_candidate"]


def test_nonzero_gradient_scaled_by_one_plus_1e8_is_rejected():
    old = {"w": tensor([1., -2.]), "key.bias": tensor([0.])}
    new = {"w": old["w"] * (1. + 1e-8), "key.bias": tensor([0.])}
    result = compare_gradients(old, new)
    assert not result["passed"]
    assert not result["gradients"]["w"]["mixed_passed"]


@pytest.mark.parametrize("scale", [1e-12, 1., 1e12])
def test_rule_scales_with_gradient_units(scale):
    old = {"w": tensor([1.]) * scale, "b": tensor([0.])}
    new = {"w": tensor([1.]) * scale, "b": tensor([5e-13]) * scale}
    result = compare_gradients(old, new)
    assert result["passed"]
    assert result["absolute_term"] == pytest.approx(1e-12 * scale, rel=1e-15, abs=0.)


def test_exact_mixed_threshold_is_inclusive():
    # Orthogonal scalar entries produce exactly representable norm summaries.
    records = {"w": dict(passed=False, maximum_absolute_difference=1.01,
                        reference_scale=1e10, candidate_scale=1e10,
                        relative_difference=1.01e-10, denominator=1e10)}
    result = compare_gradient_records(records)
    assert result["gradients"]["w"]["tolerance"] == 1.01
    assert result["passed"]
    outside = deepcopy(records)
    outside["w"]["maximum_absolute_difference"] = 1.01001
    outside["w"]["relative_difference"] = 1.01001e-10
    assert not compare_gradient_records(outside)["passed"]


def test_reference_zero_extra_requirement_is_not_hidden_by_mixed_tolerance():
    old = {"w": tensor([1.]), "b": tensor([1e-12])}
    new = {"w": tensor([1.]), "b": tensor([1.00000000001e-12])}
    result = compare_gradients(old, new)
    b = result["gradients"]["b"]
    assert b["maximum_absolute_difference"] < b["tolerance"]
    assert not b["zero_pair_passed"]
    assert not result["passed"]
    assert result["unpaired_zero_tensors"] == ["b"]


def test_all_exact_zero_gradients_have_no_artificial_absolute_floor():
    old = {"a": tensor([0.]), "b": tensor([0.])}
    result = compare_gradients(old, deepcopy(old))
    assert result["passed"]
    assert result["global_reference_scale"] == result["absolute_term"] == 0.
    assert result["zero_tensors"] == ["a", "b"]
    new = deepcopy(old)
    new["b"] = tensor([1e-40])
    assert not compare_gradients(old, new)["passed"]


def test_all_unused_gradients_are_separate_from_structural_zero():
    result = compare_gradients({"unused": None}, {"unused": None})
    assert result["passed"]
    assert result["unused_tensors"] == ["unused"]
    assert result["zero_tensors"] == []
    assert result["global_reference_scale"] == 0.
    record = result["gradients"]["unused"]
    assert record["zero_in_reference"] is record["zero_in_candidate"] is None


@pytest.mark.parametrize("missing_old", [False, True])
def test_one_sided_missing_gradient_is_rejected_even_for_zero(missing_old):
    pair = (None, tensor([0.])) if missing_old else (tensor([0.]), None)
    result = compare_gradients({"w": pair[0]}, {"w": pair[1]})
    assert not result["passed"]
    assert result["missing_gradients"] == ["w"]
    assert result["zero_tensors"] == []


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_tensor_always_fails(value):
    result = compare_gradients({"w": tensor([1.])}, {"w": tensor([value])})
    assert not result["passed"]
    assert result["nonfinite_gradients"] == ["w"]


@pytest.mark.parametrize("old,new", [
    ({"a": tensor([1.])}, {"b": tensor([1.])}),
    ({}, {}),
    ({"": tensor([1.])}, {"": tensor([1.])}),
    ([], []),
])
def test_parameter_identity_or_empty_record_is_rejected(old, new):
    with pytest.raises(ValueError):
        compare_gradients(old, new)


def test_dtype_and_shape_are_not_coerced():
    with pytest.raises(ValueError):
        compare_gradients({"w": torch.ones(1)}, {"w": tensor([1.])})
    with pytest.raises(ValueError):
        compare_gradients({"w": tensor([[1.]])}, {"w": tensor([1.])})


@pytest.mark.parametrize("field,value", [
    ("maximum_absolute_difference", -1.),
    ("reference_scale", float("nan")),
    ("candidate_scale", float("inf")),
    ("relative_difference", -1.),
    ("reference_scale", True),
    ("reference_scale", "1"),
    ("denominator", 3.),
    ("relative_difference", 9.),
    ("maximum_absolute_difference", 5.),
    ("tolerance", 1e-6),
    ("passed", False),
    ("nonfinite", "true"),
])
def test_malformed_or_inconsistent_numeric_summaries_are_rejected(field, value):
    record = strict_gradient_difference(tensor([1.]), tensor([1.]))
    record[field] = value
    with pytest.raises(ValueError):
        compare_gradient_records({"w": record})


@pytest.mark.parametrize("record", [
    {},
    {"passed": True, "none_old": True},
    {"passed": True, "none_old": False, "none_new": False},
    {"passed": True, "none_old": True, "none_new": False},
    {"passed": True, "none_old": True, "none_new": True, "reference_scale": 0.},
    {"passed": True, "nonfinite": True},
])
def test_malformed_special_records_are_rejected(record):
    with pytest.raises(ValueError):
        compare_gradient_records({"w": record})


@pytest.mark.parametrize("reducer", ["mean", "nonempty_mean"])
@pytest.mark.parametrize("use_norm", [False, True])
def test_real_small_case_passes_new_gate_but_old_failure_is_preserved(reducer, use_norm):
    report = small_case(reducer=reducer, use_norm=use_norm)
    saved = deepcopy(report)
    result = rejudge_small(report)
    assert report == saved
    assert report["status"] == result["original_status"] == "failed_static_gate"
    assert result["original_gradient_rule"] == report["gradient_rule"]
    assert result["original_gradient_tolerance"] == report["gradient_tolerance"]
    assert result["status"] == "passed"
    assert result["forward_passed"] and result["gradient_passed"]
    assert result["gradient_gate"]["unpaired_zero_tensors"] == []
    assert not result["gradients"]["k_linears.0.bias"]["passed"]
    assert result["gradients"]["k_linears.0.bias"]["mixed_passed"]


@pytest.mark.parametrize("reducer", ["mean", "nonempty_mean"])
def test_missing_relation_fault_still_fails_forward_and_gradient(reducer):
    report = small_case(reducer=reducer, drop_relation=True)
    result = rejudge_small(report)
    assert result["negative_control"]
    assert result["status"] == "failed_static_gate"
    assert not result["forward_passed"] and not result["gradient_passed"]
    assert any(not r["mixed_passed"] and not n.endswith(".bias")
               for n, r in result["gradients"].items())


@pytest.mark.parametrize("tamper", [
    "dtype", "device", "ops", "forwards", "forward_flag", "gradient_flag",
    "status", "forward_tolerance", "forward_detail",
])
def test_rejudge_rejects_contradictory_identity_and_decisions(tamper):
    report = small_case()
    if tamper == "dtype":
        report["dtype"] = "float32"
    elif tamper == "device":
        report["device"] = "cuda"
    elif tamper == "ops":
        report["all_required_ops_float64"] = False
    elif tamper == "forwards":
        report["forwards"] = {}
    elif tamper == "forward_flag":
        report["forward_passed"] = False
    elif tamper == "gradient_flag":
        report["gradient_passed"] = True
    elif tamper == "status":
        report["status"] = "passed"
    else:
        detail = next(iter(report["forwards"].values()))
        if tamper == "forward_tolerance":
            detail["tolerance"] = 1e-6
        elif tamper == "forward_detail":
            detail["passed"] = False
    with pytest.raises(ValueError):
        rejudge_small(report)


def test_record_rejudgment_does_not_mutate_input():
    original = {"w": strict_gradient_difference(tensor([2e-17]), tensor([1e-17])),
                "scale": strict_gradient_difference(tensor([1.]), tensor([1.]))}
    frozen = deepcopy(original)
    result = compare_gradient_records(original)
    assert original == frozen
    assert result["gradients"]["w"] is not original["w"]
