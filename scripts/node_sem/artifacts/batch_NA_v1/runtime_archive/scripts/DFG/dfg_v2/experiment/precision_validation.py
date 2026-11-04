"""Prompt 7b.1 strict float64 gate, independent of frozen fitting code.

This small-graph preflight is a numerical diagnostic, not a proof of mathematical
equivalence. A failed relative check at near-zero gradients is retained as a
failure, even when the absolute difference is tiny. No atol is added, no bias is
excluded, and a failure blocks all real-data/GPU stages.

The fixture exercises multiple canonicals sharing projections, an empty relation,
source-only/sink-only types, edge_softmax, v_dot_u, u_mul_e/sum and multi_update_all.
Fault injection is confined to this disposable graph, never the HGT implementation.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import dgl
import torch

from sco_models.model_hgt import HGTLayer
from scripts.DFG.dfg_v2.hgt_layer import (
    HGTLayerNonEmptyMean, HGTLayerSharedProjection,
    HGTLayerSharedProjectionNonEmptyMean,
)
from scripts.DFG.experiments.common import write_json, tensor_digest

FORWARD_ATOL = 1e-12
GRADIENT_RTOL = 1e-10
GRADIENT_FLOOR = 1e-30
TRAJECTORY_ATOL = 1e-9
DROP_RELATION = ("a", "other_relation", "b")


def _check_pair(old, new):
    if old.shape != new.shape or old.dtype != torch.float64 or new.dtype != torch.float64:
        raise ValueError("Float64 tensor shape/dtype mismatch")
    if old.device.type != "cpu" or new.device.type != "cpu":
        raise ValueError("Prompt 7b.1 float64 gate is CPU-only")


def _maxabs(value):
    return float(value.detach().abs().max()) if value.numel() else 0.0


def forward_difference(old, new):
    _check_pair(old, new)
    if not bool(torch.isfinite(old).all() and torch.isfinite(new).all()):
        return dict(passed=False, nonfinite=True, bitwise_equal=False)
    difference = _maxabs(old - new)
    return dict(maximum_absolute_difference=difference,
                bitwise_equal=bool(torch.equal(old, new)),
                tolerance=FORWARD_ATOL, passed=difference <= FORWARD_ATOL)


def strict_gradient_difference(old, new):
    if old is None or new is None:
        return dict(none_old=old is None, none_new=new is None,
                    passed=old is None and new is None)
    _check_pair(old, new)
    if not bool(torch.isfinite(old).all() and torch.isfinite(new).all()):
        return dict(passed=False, nonfinite=True)
    difference = _maxabs(old - new)
    scale = _maxabs(old)
    denominator = max(scale, GRADIENT_FLOOR)
    relative = difference / denominator
    return dict(maximum_absolute_difference=difference, reference_scale=scale,
                candidate_scale=_maxabs(new), denominator=denominator,
                relative_difference=relative, tolerance=GRADIENT_RTOL,
                passed=relative <= GRADIENT_RTOL)


def _graph():
    return dgl.heterograph({
        ("a", "same_relation", "b"): ([0, 0, 1, 2], [0, 1, 1, 0]),
        DROP_RELATION: ([2, 0, 1], [0, 0, 1]),
        ("b", "same_relation", "a"): ([0, 1, 1], [0, 0, 1]),
        ("a", "registered_empty", "b"): ([], []),
        ("source_only", "SOURCE", "a"): ([0, 1], [0, 1]),
        ("a", "TO_SINK", "sink_only"): ([0, 1], [0, 0]),
    }, num_nodes_dict={"a": 3, "b": 3, "source_only": 2, "sink_only": 2})


def _layer(graph, cls, use_norm):
    # Construct under the ordinary float32 default, then cast the same weights.
    return cls(8, 8, {t: i for i, t in enumerate(graph.ntypes)},
               {c: i for i, c in enumerate(graph.canonical_etypes)},
               n_heads=2, dropout=0.0, use_norm=use_norm).double()


def _loss(outputs):
    return sum((value * torch.arange(1, 9, dtype=value.dtype)).square().mean()
               for value in outputs.values())


@contextmanager
def _cpu_context():
    # No CUDA RNG calls, no global dtype or production numerical changes.
    rng = torch.get_rng_state().clone()
    threads = torch.get_num_threads()
    try:
        if torch.get_default_dtype() != torch.float32:
            raise ValueError("Construct frozen float32 weights before diagnostic casting")
        torch.set_num_threads(2)
        torch.manual_seed(114)
        yield
    finally:
        torch.set_rng_state(rng)
        torch.set_num_threads(threads)


def small_case(reducer="mean", use_norm=True, drop_relation=False):
    if reducer not in ("mean", "nonempty_mean"):
        raise ValueError("Unknown reducer")
    classes = {
        "mean": (HGTLayer, HGTLayerSharedProjection),
        "nonempty_mean": (HGTLayerNonEmptyMean, HGTLayerSharedProjectionNonEmptyMean),
    }[reducer]
    with _cpu_context():
        graph = _graph()
        old, new = [_layer(graph, cls, use_norm) for cls in classes]
        new.load_state_dict(old.state_dict(), strict=True)
        initial_digest = tensor_digest(old.state_dict())
        if tensor_digest(new.state_dict()) != initial_digest:
            raise AssertionError("Diagnostic initial weights differ")
        features = {t: torch.randn(graph.num_nodes(t), 8, dtype=torch.float64)
                    for t in graph.ntypes}
        original_update = graph.multi_update_all
        dropped = []

        def faulty_update(functions, *args, **kwargs):
            functions = dict(functions)
            if DROP_RELATION not in functions:
                raise AssertionError("Fault-injection relation is missing")
            # Suppress just this canonical's message, retaining reducer slots.
            # Removing a stack entry would change the nonempty_mean mask shape
            # and test an interface error instead of a missing contribution.
            key = "v_%d" % new.edge_dict[DROP_RELATION]
            data = graph.nodes[DROP_RELATION[0]].data
            data[key] = data[key] * 0.0
            dropped.append(DROP_RELATION)
            return original_update(functions, *args, **kwargs)

        def candidate_forward():
            if drop_relation:
                with patch.object(graph, "multi_update_all", side_effect=faulty_update):
                    return new(graph, features)
            return new(graph, features)

        old.eval()
        new.eval()
        with torch.no_grad():
            before = old(graph, features)
            after = candidate_forward()
        if set(before) != set(after):
            raise AssertionError("Output type identity mismatch")
        forwards = {t: forward_difference(before[t], after[t]) for t in before}
        old.train()
        new.train()
        old_loss = _loss(old(graph, features))
        new_loss = _loss(candidate_forward())
        old_loss.backward()
        new_loss.backward()
        old_parameters, new_parameters = dict(old.named_parameters()), dict(new.named_parameters())
        if set(old_parameters) != set(new_parameters):
            raise AssertionError("Parameter identity mismatch")
        gradients = {n: strict_gradient_difference(old_parameters[n].grad, new_parameters[n].grad)
                     for n in old_parameters}
        required64 = all(t.dtype == torch.float64 for outputs in (before, after)
                         for t in outputs.values()) and all(
            p.grad is None or p.grad.dtype == torch.float64
            for params in (old_parameters, new_parameters) for p in params.values())
        if not required64:
            raise AssertionError("DGL silently changed floating dtype")
        if any(list(graph.nodes[t].data) for t in graph.ntypes) or any(
                list(graph.edges[c].data) for c in graph.canonical_etypes):
            raise AssertionError("Graph local_scope leaked diagnostic tensors")
        forward_passed = all(r["passed"] for r in forwards.values())
        gradient_passed = all(r["passed"] for r in gradients.values())
        return dict(
            status="passed" if forward_passed and gradient_passed else "failed_static_gate",
            device="cpu", dtype="float64", seed=114, threads=2,
            reducer=reducer, use_norm=bool(use_norm), dropout=0.0,
            scope="one small HGT layer; not real-data classifier or fit",
            all_required_ops_float64=required64, forward_passed=forward_passed,
            gradient_passed=gradient_passed, forwards=forwards, gradients=gradients,
            missing_parameter_gradients=[n for n, r in gradients.items()
                if r.get("none_old") != r.get("none_new")],
            maximum_absolute_gradient_difference=max(
                r.get("maximum_absolute_difference", 0.0) for r in gradients.values()),
            training_loss_original=float(old_loss.detach()),
            training_loss_shared=float(new_loss.detach()),
            initial_state_sha256=initial_digest,
            negative_control=bool(drop_relation),
            deliberately_dropped_relation=list(DROP_RELATION) if drop_relation else None,
            deliberately_dropped_calls=len(dropped),
            gradient_rule="maxabs(new-old)/max(maxabs(old),1e-30) <= 1e-10",
            forward_tolerance=FORWARD_ATOL, gradient_tolerance=GRADIENT_RTOL,
        )


def run_preflight(output):
    """Persist the unmodified gate; stop at its first failure without any fit."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[4]
    refs = ["sco_models/model_hgt.py", "scripts/DFG/dfg_v2/hgt_layer.py",
            "scripts/DFG/dfg_v2/experiment/trainer.py",
            "scripts/DFG/dfg_v2/experiment/precision_validation.py",
            "scripts/DFG/dfg_v2/PROMPTS.md"]
    source = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in refs}
    report = dict(status="running", stage="float64_small_preflight", sources=source,
                  torch_version=torch.__version__, dgl_version=dgl.__version__,
                  cases=[], not_counted_as_pilot=True, fits=0,
                  real_data_cases=0, gpu_runs=0)
    write_json(output/"acceptance.json", report)
    for reducer in ("mean", "nonempty_mean"):
        try:
            case = small_case(reducer=reducer, use_norm=True)
        except Exception as exc:
            report.update(status="execution_error", error_type=type(exc).__name__, error=str(exc))
            write_json(output/"acceptance.json", report)
            raise
        write_json(output/(reducer+".json"), case)
        report["cases"].append(dict(reducer=reducer, status=case["status"]))
        if case["status"] != "passed":
            report.update(status="failed_static_gate",
                          stopped_before="real_data_float64_and_all_gpu_stages")
            write_json(output/"acceptance.json", report)
            raise AssertionError("Prompt 7b.1 strict float64 small-graph gate failed; see " + str(output))
    report["status"] = "small_preflight_passed_not_full_acceptance"
    write_json(output/"acceptance.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(run_preflight(args.output)), flush=True)


if __name__ == "__main__":
    main()
