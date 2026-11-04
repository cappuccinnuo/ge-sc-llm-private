"""Prompt 7b.2 global-scale float64 gradient acceptance.

Diagnostic-only replacement criterion. Prompt 7b.1 and its historical failures
remain unchanged. Pure relative errors and old decisions are retained; None
gradients denote unused parameters and are never interpreted as numeric zeros.
"""
from copy import deepcopy
import math
from numbers import Real

from scripts.DFG.dfg_v2.experiment.precision_validation import (
    FORWARD_ATOL, GRADIENT_FLOOR, strict_gradient_difference,
)

GLOBAL_ATOL_FACTOR = 1e-12
GRADIENT_RTOL = 1e-10
GRADIENT_RULE = (
    "maxabs(shared-original) <= 1e-12*global_maxabs(original) "
    "+ 1e-10*maxabs(original); reference-zero tensors require "
    "maxabs(shared) <= 1e-12*global_maxabs(original)"
)


def _named_records(records):
    if not isinstance(records, dict) or not records:
        raise ValueError("Expected nonempty named parameter records")
    if any(not isinstance(name, str) or not name for name in records):
        raise ValueError("Parameter identities must be nonempty strings")
    if any(not isinstance(record, dict) for record in records.values()):
        raise ValueError("Each parameter requires its own comparison record")


def _number(record, field):
    if field not in record:
        raise ValueError("Missing gradient comparison field: " + field)
    value = record[field]
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("Gradient comparison fields must be numeric: " + field)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Gradient comparison fields must be finite/nonnegative: " + field)
    return float(value)


def _numeric_record(record):
    diff = _number(record, "maximum_absolute_difference")
    reference = _number(record, "reference_scale")
    candidate = _number(record, "candidate_scale")
    relative = _number(record, "relative_difference")
    denominator = max(reference, GRADIENT_FLOOR)
    if "denominator" in record and _number(record, "denominator") != denominator:
        raise ValueError("Pure relative gradient denominator is inconsistent")
    if "tolerance" in record and _number(record, "tolerance") != GRADIENT_RTOL:
        raise ValueError("Original relative tolerance is inconsistent")
    if record["passed"] != (relative <= GRADIENT_RTOL):
        raise ValueError("Original relative decision is inconsistent")
    expected_relative = diff / denominator
    if not math.isfinite(expected_relative) or not math.isclose(
            relative, expected_relative, rel_tol=1e-12, abs_tol=0.0):
        raise ValueError("Pure relative gradient diagnostic is inconsistent")
    # Max norms obey triangle inequalities; this slack only validates summary
    # arithmetic and never enters the gradient acceptance formula.
    rounding = 16 * 2.220446049250313e-16 * max(reference, candidate, diff)
    if diff + rounding < abs(reference - candidate) or diff > reference + candidate + rounding:
        raise ValueError("Gradient norm/difference records are inconsistent")
    return diff, reference, candidate


def compare_gradient_records(records):
    """Rejudge P7b.1 summaries without modifying their old decision fields.

    Malformed records raise ValueError. Explicit nonfinite gradients and
    one-sided None gradients return failure. Two-sided None is listed as unused.
    """
    _named_records(records)
    gradients = deepcopy(records)
    numeric = {}
    unused, missing, nonfinite = [], [], []
    for name, record in gradients.items():
        if "nonfinite" in record and not isinstance(record["nonfinite"], bool):
            raise ValueError("Nonfinite status must be boolean: " + name)
        if "tolerance" in record:
            record["original_tolerance"] = record["tolerance"]
        if not isinstance(record.get("passed"), bool):
            raise ValueError("Original gradient decision is missing: " + name)
        if "none_old" in record or "none_new" in record:
            if (not isinstance(record.get("none_old"), bool)
                    or not isinstance(record.get("none_new"), bool)):
                raise ValueError("Incomplete None gradient identity: " + name)
            if not record["none_old"] and not record["none_new"]:
                raise ValueError("Neither gradient is None in a None record: " + name)
            if any(field in record for field in (
                    "reference_scale", "candidate_scale", "maximum_absolute_difference")):
                raise ValueError("None gradients cannot carry numeric norms: " + name)
            both_none = record["none_old"] and record["none_new"]
            if record["passed"] != both_none or record.get("nonfinite", False):
                raise ValueError("Contradictory None gradient record: " + name)
            record.update(mixed_passed=both_none, tolerance=None,
                          zero_in_reference=None, zero_in_candidate=None,
                          unused_in_both=both_none)
            (unused if both_none else missing).append(name)
        elif record.get("nonfinite", False):
            if record["passed"]:
                raise ValueError("Nonfinite gradient cannot have passed: " + name)
            record.update(mixed_passed=False, tolerance=None,
                          zero_in_reference=None, zero_in_candidate=None)
            nonfinite.append(name)
        else:
            numeric[name] = _numeric_record(record)

    global_scale = max((item[1] for item in numeric.values()), default=0.0)
    absolute_term = GLOBAL_ATOL_FACTOR * global_scale
    reference_zeros, candidate_zeros, unpaired_zeros = [], [], []
    for name, (diff, reference, candidate) in numeric.items():
        tolerance = absolute_term + GRADIENT_RTOL * reference
        zero_reference = reference <= absolute_term
        zero_candidate = candidate <= absolute_term
        zero_pair_passed = not zero_reference or zero_candidate
        gradients[name].update(
            mixed_passed=diff <= tolerance and zero_pair_passed,
            tolerance=tolerance, global_absolute_term=absolute_term,
            zero_in_reference=zero_reference, zero_in_candidate=zero_candidate,
            zero_pair_passed=zero_pair_passed,
        )
        if zero_reference:
            reference_zeros.append(name)
        if zero_candidate:
            candidate_zeros.append(name)
        if not zero_pair_passed:
            unpaired_zeros.append(name)
    return dict(
        passed=all(record["mixed_passed"] for record in gradients.values()),
        global_reference_scale=global_scale, absolute_term=absolute_term,
        gradient_rule=GRADIENT_RULE, gradients=gradients,
        zero_tensors=sorted(reference_zeros),
        candidate_zero_tensors=sorted(candidate_zeros),
        unpaired_zero_tensors=sorted(unpaired_zeros),
        unused_tensors=sorted(unused), missing_gradients=sorted(missing),
        nonfinite_gradients=sorted(nonfinite),
    )


def compare_gradients(original, shared):
    """Compare complete named CPU float64 gradient dictionaries."""
    if not isinstance(original, dict) or not isinstance(shared, dict):
        raise ValueError("Named gradient dictionaries required")
    if set(original) != set(shared):
        raise ValueError("Parameter identity mismatch")
    records = {name: strict_gradient_difference(value, shared[name])
               for name, value in original.items()}
    return compare_gradient_records(records)


def rejudge_small(report):
    """Rejudge an old CPU small case, preserving its original decision.

    No file is opened or written. The caller owns the new output directory.
    Forward tolerance remains exactly the original 1e-12.
    """
    if (not isinstance(report, dict) or report.get("dtype") != "float64"
            or report.get("device") != "cpu"
            or report.get("all_required_ops_float64") is not True):
        raise ValueError("Expected a verified CPU float64 small-case report")
    forwards = report.get("forwards")
    if not isinstance(forwards, dict) or not forwards:
        raise ValueError("Forward records are missing")
    forward_flags = []
    for name, record in forwards.items():
        if not isinstance(name, str) or not name or not isinstance(record, dict):
            raise ValueError("Invalid forward identity/record")
        if record.get("nonfinite", False):
            accepted = False
        else:
            if _number(record, "tolerance") != FORWARD_ATOL:
                raise ValueError("Original forward tolerance has changed")
            accepted = _number(record, "maximum_absolute_difference") <= FORWARD_ATOL
        if record.get("passed") is not accepted:
            raise ValueError("Forward record contradicts its decision")
        forward_flags.append(accepted)
    forward_passed = all(forward_flags)
    if report.get("forward_passed") is not forward_passed:
        raise ValueError("Forward summary contradicts its records")
    gate = compare_gradient_records(report.get("gradients"))
    original_gradient_passed = all(row["passed"] for row in report["gradients"].values())
    if report.get("gradient_passed") is not original_gradient_passed:
        raise ValueError("Original gradient summary contradicts its records")
    original_status = "passed" if forward_passed and original_gradient_passed else "failed_static_gate"
    if report.get("status") != original_status:
        raise ValueError("Original static-gate status contradicts its records")
    result = deepcopy(report)
    result.update(
        original_status=report["status"],
        original_gradient_passed=report["gradient_passed"],
        original_gradient_rule=report.get("gradient_rule"),
        original_gradient_tolerance=report.get("gradient_tolerance"),
        gradient_gate=gate, gradients=gate["gradients"],
        gradient_passed=gate["passed"], gradient_rule=GRADIENT_RULE,
        gradient_tolerance=dict(global_absolute_factor=GLOBAL_ATOL_FACTOR,
                                relative_factor=GRADIENT_RTOL),
        status="passed" if forward_passed and gate["passed"] else "failed_static_gate",
    )
    return result
