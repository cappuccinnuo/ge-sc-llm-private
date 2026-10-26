"""Prompt 7b.2 CPU float64 diagnostics, separate from production fitting.

Numerical loop reference: experiment/trainer.py::_fit. The diagnostic loop uses
its Adam/OneCycle/single-step/eval/CE rules, but no production checkpoint or
float32 input validation is bypassed in production. Both implementations use
this same isolated loop: equivalence here does not prove equivalence of two
separate trainers. No efficacy scores or outer-test targets are computed.
"""
import argparse
import copy
import gc
import json
import math
import time
from contextlib import contextmanager
from pathlib import Path

import torch

from scripts.DFG.experiments.common import (
    digest, read_json, write_json, sha256, seed_all, tensor_digest, scheduler_metadata,
)
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.dfg_v2.model import validate_registration
from scripts.DFG.dfg_v2.supervision import DfgV2Supervision
from .checkpoint import StopMonitor
from .projection_validation import _context, _model, _parts, compare_histories, CPU_CASES
from .precision_validation import forward_difference, TRAJECTORY_ATOL
from .precision_gate import compare_gradients, compare_gradient_records
from .protocol import validate_parts


@contextmanager
def diagnostic_default_dtype():
    """Scope untyped zero allocations in inherited forward; always restore."""
    previous = torch.get_default_dtype()
    if previous != torch.float32:
        raise ValueError("Diagnostic casting must start from production float32 default")
    try:
        torch.set_default_dtype(torch.float64)
        yield
    finally:
        torch.set_default_dtype(previous)


def _features(model):
    graph = model.symmetrical_global_graph
    return {t: graph.nodes[t].data["inp"] for t in graph.ntypes}


def input_identity(model):
    """Exact diagnostic input identity; no production dtype validator invoked."""
    graph = model.symmetrical_global_graph
    edges = {}
    for canonical in graph.canonical_etypes:
        key = "|".join(canonical)
        for role, value in zip(("source", "target"), graph.edges(etype=canonical, order="eid")):
            edges[key + ":" + role] = value
        for name, value in graph.edges[canonical].data.items():
            edges[key + ":data:" + name] = value
    return dict(
        nx_graph_sha256=fingerprint(model.nx_graph),
        original_node_ids_sha256=digest(model.original_graph_node_ids),
        nodes_per_type={t: graph.num_nodes(t) for t in graph.ntypes},
        dgl_edges_sha256=tensor_digest(edges),
        node_dictionary=dict(model.ntypes_dict),
        relation_dictionary={"|".join(c): i for c, i in model.etypes_dict.items()},
        node_ids_sha256=digest(model.node_ids_dict),
        node_labels_sha256=digest(getattr(model, "node_labels", None)),
        pool_rows_sha256=digest(getattr(model, "node_ids_by_filename", None)),
        supervised_mask_sha256=tensor_digest({"mask": model.supervised_node_mask}),
        features_sha256=tensor_digest(_features(model)),
        feature_dtypes={t: str(v.dtype) for t, v in _features(model).items()},
    )


def make_diagnostic_copy(source):
    """Validate ordinary model, then losslessly cast only its deep copy."""
    validate_registration(source)
    if torch.get_default_dtype() != torch.float32:
        raise ValueError("Construct source under float32 default")
    if any(v.is_floating_point() and v.dtype != torch.float32
           for v in source.state_dict().values()):
        raise ValueError("Source state is not float32")
    if any(v.dtype != torch.float32 for v in _features(source).values()):
        raise ValueError("Source features are not float32")
    source_state = tensor_digest(source.state_dict())
    before = input_identity(source)
    result = copy.deepcopy(source).double()
    for typ, value in _features(source).items():
        result.symmetrical_global_graph.nodes[typ].data["inp"] = value.detach().clone().double()
    for name, value in source.state_dict().items():
        actual = result.state_dict()[name]
        expected = value.double() if value.is_floating_point() else value
        if (actual.dtype != expected.dtype or not torch.equal(actual, expected)
                or not torch.equal(actual.to(value.dtype), value)):
            raise AssertionError("State conversion is not lossless: " + name)
    for typ, value in _features(source).items():
        actual = _features(result)[typ]
        if actual.requires_grad or actual.dtype != torch.float64 or not torch.equal(actual, value.double()):
            raise AssertionError("Feature conversion is not lossless: " + typ)
        if not torch.equal(actual.float(), value):
            raise AssertionError("Feature roundtrip differs: " + typ)
    after = input_identity(result)
    structural_keys = set(before) - {"features_sha256", "feature_dtypes"}
    if any(before[k] != after[k] for k in structural_keys):
        raise AssertionError("Float64 conversion changed graph/labels/masks/schema")
    if input_identity(source) != before or tensor_digest(source.state_dict()) != source_state:
        raise AssertionError("Diagnostic deep copy mutated source")
    identity = dict(source_state_sha256=source_state,
                    diagnostic_state_sha256=tensor_digest(result.state_dict()),
                    source_input=before, diagnostic_input=after,
                    source_dtype="float32", diagnostic_dtype="float64",
                    conversion="exact widening of frozen float32 values",
                    lossless_state_and_features=True, original_unchanged=True)
    return result, identity


def checked_diagnostic_inputs(model, identity, require_initial=True):
    if input_identity(model) != identity["diagnostic_input"]:
        raise ValueError("Diagnostic input graph/labels/features/schema changed")
    for name, value in model.state_dict().items():
        if value.is_floating_point() and (value.dtype != torch.float64 or not bool(torch.isfinite(value).all())):
            raise ValueError("Nonfinite or non-float64 diagnostic state: " + name)
    if require_initial and tensor_digest(model.state_dict()) != identity["diagnostic_state_sha256"]:
        raise ValueError("Diagnostic initial state changed")


def supervised_forward(model, part):
    # Production DfgV2Supervision.forward intentionally retains registration.
    # This isolated diagnostic already checked exact graph and mask identities.
    return model()[part.mask] if part.task == "node" else model(part.files)[0]


def _check_parts(model, ctx, parts):
    population = sorted({d["source_file"] for _, d in model.nx_graph.nodes(data=True)})
    expected = validate_parts(ctx["split"], population)
    if set(parts) != set(expected):
        raise ValueError("Diagnostic needs all three fixed supervision identities")
    for role in parts:
        reference = DfgV2Supervision(model, ctx["task"], expected[role])
        part = parts[role]
        if (part.manifest != reference.manifest or part.full_ids != reference.full_ids
                or not torch.equal(part.mask, reference.mask)):
            raise ValueError("Diagnostic supervision differs: " + role)
    if ctx["task"] == "contract" and not set(population) <= set(ctx["labels"]):
        raise ValueError("Frozen contract labels do not cover population")


def _diagnostic_model(ctx, impl, reducer):
    source = _model(ctx, impl, reducer)
    model, identity = make_diagnostic_copy(source)
    del source
    gc.collect()
    parts = _parts(model, ctx)
    _check_parts(model, ctx, parts)
    checked_diagnostic_inputs(model, identity)
    return model, identity, parts


def _support(model, part):
    """Observed training reachability, not a claim about semantic relevance."""
    graph = model.symmetrical_global_graph
    active = {typ: set() for typ in graph.ntypes}
    for node in part.full_ids:
        row = model.nx_graph.nodes[node]
        # Contract pool excludes auxiliary rows even when full_ids includes them.
        if model.dfg_task == "contract" and node not in model.node_ids_by_filename[row["source_file"]]:
            continue
        active[row["node_type"]].add(row["node_hetero_id"])
    output_support = [None] * len(model.gcs)
    canonical_support = [None] * len(model.gcs)
    for layer in reversed(range(len(model.gcs))):
        output_support[layer] = {t: len(v) for t, v in active.items()}
        previous = {t: set(v) for t, v in active.items()}
        relations = []
        for c in graph.canonical_etypes:
            src, dst = graph.edges(etype=c, order="eid")
            targets = active[c[2]]
            selected = [(s, d) for s, d in zip(src.tolist(), dst.tolist()) if d in targets]
            degrees = graph.in_degrees(etype=c)
            relations.append(dict(canonical=list(c), reachable_edges=len(selected),
                reachable_destinations_with_multiple_edges=sum(int(degrees[d]) > 1 for d in targets)))
            previous[c[0]].update(s for s, d in selected)
        canonical_support[layer] = relations
        active = previous
    return dict(input_nodes_reaching_train={t: len(v) for t, v in active.items()},
                output_nodes_reaching_train_by_layer=output_support,
                canonical_training_path_support=canonical_support,
                node_type_names_by_index=list(model.node_types),
                meaning="Topology support through remaining HGT layers plus residuals; not nonzero-gradient guarantee")


def explain_zero_tensors(names, support):
    rows = []
    types = support["node_type_names_by_index"]
    for name in names:
        reason = "Observed numerical zero; topology alone does not establish a structural zero"
        evidence = {}
        fields = name.split(".")
        if name.startswith("gcs.") and len(fields) >= 4:
            layer = int(fields[1])
            relations = support["canonical_training_path_support"][layer]
            if fields[2] == "k_linears" and fields[-1] == "bias":
                reason = "Key bias adds a constant to each canonical/destination/head softmax; exact derivative cancels"
            elif fields[2] in ("q_linears", "k_linears", "v_linears", "a_linears", "norms"):
                typ = types[int(fields[3])]
                evidence["node_type"] = typ
                incoming = [r for r in relations if r["canonical"][2] == typ]
                outgoing = [r for r in relations if r["canonical"][0] == typ]
                if fields[2] in ("a_linears", "norms", "q_linears") and not support["output_nodes_reaching_train_by_layer"][layer][typ]:
                    reason = "No node of this target type reaches supervised rows through remaining layers"
                elif fields[2] == "a_linears" and fields[-1] == "weight" and not sum(r["reachable_edges"] for r in incoming):
                    reason = "No incoming message reaches this projection; a_linear input is zero, so its weight gradient is zero"
                elif fields[2] in ("k_linears", "v_linears") and not sum(r["reachable_edges"] for r in outgoing):
                    reason = "No outgoing message of this source type reaches supervised rows at this layer"
                elif fields[2] in ("q_linears", "k_linears") and not sum(
                        r["reachable_destinations_with_multiple_edges"] for r in
                        (incoming if fields[2] == "q_linears" else outgoing)):
                    reason = "All supported attention destinations have at most one incoming edge within each canonical; softmax derivative is zero"
                evidence["reachable_output_nodes"] = support["output_nodes_reaching_train_by_layer"][layer][typ]
                evidence["incoming"] = incoming
                evidence["outgoing"] = outgoing
        elif name.startswith("adapt_ws."):
            typ = types[int(fields[1])]
            evidence["node_type"] = typ
            evidence["reachable_input_nodes"] = support.get("input_nodes_reaching_train", {}).get(typ)
            if evidence["reachable_input_nodes"] == 0:
                reason = "No input node of this type reaches supervised rows through HGT layers and residuals"
        rows.append(dict(parameter=name, reason=reason, evidence=evidence,
                         mathematical_claim=not reason.startswith("Observed")))
    return rows


def _capture(ctx, impl, reducer):
    model, identity, parts = _diagnostic_model(ctx, impl, reducer)
    captured, handles = [], []
    def hook(layer, args, output):
        captured.append({k: v.detach().cpu().clone() for k, v in output.items()})
    handles = [layer.register_forward_hook(hook) for layer in model.gcs]
    started = time.monotonic()
    try:
        with diagnostic_default_dtype():
            model.eval()
            with torch.no_grad():
                files = sorted({d["source_file"] for _, d in model.nx_graph.nodes(data=True)})
                logits = (model() if ctx["task"] == "node" else model(files)[0]).detach().cpu().clone()
            for handle in handles:
                handle.remove()
            handles = []
            model.train()
            model.zero_grad()
            seed_all(ctx["seeds"]["fit"])
            rng_before = tensor_digest({"cpu_rng": torch.get_rng_state()})
            targets = parts["inner_train"].targets(model, ctx["labels"])
            if targets.dtype != torch.long:
                raise AssertionError("Diagnostic classification targets must stay int64")
            loss = torch.nn.CrossEntropyLoss()(supervised_forward(model, parts["inner_train"]), targets)
            if not bool(torch.isfinite(loss)):
                raise ValueError("Nonfinite float64 static loss")
            loss.backward()
            rng_after = tensor_digest({"cpu_rng": torch.get_rng_state()})
        gradients = {k: None if p.grad is None else p.grad.detach().cpu().clone()
                     for k, p in model.named_parameters()}
        checked_diagnostic_inputs(model, identity)
        result = dict(layers=captured, logits=logits, gradients=gradients,
            train_loss=float(loss.detach()), identity=identity,
            support=_support(model, parts["inner_train"]),
            parts={k: p.manifest for k, p in parts.items()},
            target_dtype=str(targets.dtype), target_sha256=tensor_digest({"targets": targets}),
            rng_before=rng_before, rng_after=rng_after, seconds=time.monotonic()-started)
    finally:
        for handle in handles:
            handle.remove()
        del model, parts
        gc.collect()
    return result


def _case(ctx, reducer):
    return dict(task_id=ctx["task_id"], task=ctx["task"], profile=ctx["profile"], reducer=reducer,
        fold=0, seed=1, device="cpu", dtype="float64", initial=ctx["initial"],
        graph=ctx["graph"], labels_ref=ctx["labels_ref"], folds=ctx["folds"],
        archived_plan=ctx["archived_plan"], config=ctx["config"], seeds=ctx["seeds"],
        split_sha256=digest(ctx["split"]))


def _prepare(plan, output, task, profile, reducer):
    if (task, profile, reducer) not in CPU_CASES:
        raise ValueError("Not one of the six frozen float64 cases")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    ctx = _context(plan, task, profile)
    torch.set_num_threads(ctx["config"]["threads"])
    return ctx, output


def _source_identity():
    root = Path(__file__).resolve().parents[4]
    files = ["scripts/DFG/dfg_v2/experiment/precision_real.py",
             "scripts/DFG/dfg_v2/experiment/precision_gate.py",
             "scripts/DFG/dfg_v2/experiment/projection_validation.py",
             "scripts/DFG/dfg_v2/experiment/trainer.py",
             "scripts/DFG/dfg_v2/model.py", "scripts/DFG/dfg_v2/hgt_layer.py",
             "sco_models/model_hgt.py"]
    return {p: sha256(root/p) for p in files}


def _require_pair_identity(old, new):
    for field in ("identity", "parts", "target_dtype", "target_sha256", "rng_before", "rng_after", "support"):
        if old[field] != new[field]:
            raise ValueError("Float64 pair identity differs: " + field)
    if set(old["gradients"]) != set(new["gradients"]):
        raise ValueError("Float64 gradient names differ")
    if len(old["layers"]) != len(new["layers"]):
        raise ValueError("Float64 layer counts differ")


def run_static(plan, output, task_id, profile, reducer="mean"):
    ctx, output = _prepare(plan, output, task_id, profile, reducer)
    report = dict(_case(ctx, reducer), status="running", sources=_source_identity())
    write_json(output/"static.json", report)
    try:
        old = _capture(ctx, "original", reducer)
        new = _capture(ctx, "shared_projection", reducer)
        _require_pair_identity(old, new)
        layers = []
        for a, b in zip(old["layers"], new["layers"]):
            if set(a) != set(b):
                raise ValueError("Float64 layer node types differ")
            layers.append({k: forward_difference(a[k], b[k]) for k in a})
        final = forward_difference(old["logits"], new["logits"])
        gradient = compare_gradients(old["gradients"], new["gradients"])
        forward_passed = final["passed"] and all(all(r["passed"] for r in layer.values()) for layer in layers)
        report.update(identity=old["identity"], supervision=old["parts"],
            training_target_dtype=old["target_dtype"], training_target_sha256=old["target_sha256"],
            rng_before=old["rng_before"], rng_after=old["rng_after"],
            layers=layers, logits=final, forward_passed=forward_passed,
            gradient_comparison=gradient, support=old["support"],
            numerical_zero_explanations=explain_zero_tensors(gradient["zero_tensors"], old["support"]),
            training_loss_original=old["train_loss"], training_loss_shared=new["train_loss"],
            seconds_original=old["seconds"], seconds_shared=new["seconds"],
            status="passed" if forward_passed and gradient["passed"] else "failed_static_gate")
        write_json(output/"static.json", report)
        if report["status"] != "passed":
            raise AssertionError("Float64 real static gate failed")
        return report
    except Exception as exc:
        if report["status"] == "running":
            report.update(status="execution_error", error_type=type(exc).__name__, error=str(exc))
            write_json(output/"static.json", report)
        raise


def diagnostic_config(config):
    if (config["schedule_epochs"] != 50 or config["patience"] != 7 or config["delta"] != .001):
        raise ValueError("Frozen diagnostic schedule or stopping configuration differs")
    for key in ("initial_lr", "max_lr", "div_factor", "final_div_factor"):
        if not math.isfinite(config[key]) or config[key] <= 0:
            raise ValueError("Invalid frozen numeric configuration: " + key)
    if not math.isfinite(config["weight_decay"]) or config["weight_decay"] < 0:
        raise ValueError("Invalid frozen weight decay")
    return copy.deepcopy(config)


def trajectory_for_model(model, parts, labels, config, fit_seed):
    """Three diagnostic steps; no checkpoint, metrics, or outer-test access."""
    c = diagnostic_config(config)
    ytrain = parts["inner_train"].targets(model, labels)
    yvalid = parts["inner_val"].targets(model, labels)
    if ytrain.dtype != torch.long or yvalid.dtype != torch.long:
        raise ValueError("CrossEntropy targets must remain int64")
    optimizer = torch.optim.Adam(model.parameters(), lr=c["initial_lr"], weight_decay=c["weight_decay"])
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=c["max_lr"],
        total_steps=c["schedule_epochs"], div_factor=c["div_factor"],
        final_div_factor=c["final_div_factor"], cycle_momentum=c["cycle_momentum"])
    metadata = dict(optimizer=optimizer.__class__.__name__, defaults=optimizer.defaults,
        initial_groups=[{k: v for k, v in g.items() if k != "params"} for g in optimizer.param_groups],
        scheduler=scheduler.__class__.__name__, initial_state=scheduler_metadata(scheduler.state_dict()))
    stop = StopMonitor(c["patience"], c["delta"])
    criterion = torch.nn.CrossEntropyLoss()
    history = []
    seed_all(fit_seed)
    for epoch in range(3):
        model.train()
        optimizer.zero_grad()
        loss = criterion(supervised_forward(model, parts["inner_train"]), ytrain)
        if not bool(torch.isfinite(loss)):
            raise ValueError("Nonfinite float64 training loss")
        loss.backward()
        if any(p.grad is not None and not bool(torch.isfinite(p.grad).all()) for p in model.parameters()):
            raise ValueError("Nonfinite float64 training gradient")
        lr, beta1 = optimizer.param_groups[0]["lr"], optimizer.param_groups[0]["betas"][0]
        optimizer.step()
        scheduler.step()
        model.eval()
        with torch.no_grad():
            valid_loss = float(criterion(supervised_forward(model, parts["inner_val"]), yvalid))
        if not math.isfinite(valid_loss):
            raise ValueError("Nonfinite float64 validation loss")
        save_best, stop_now = stop.step(valid_loss)
        history.append(dict(epoch=epoch, train_loss=float(loss.detach()), inner_val_loss=valid_loss,
            lr=lr, adam_beta1=beta1, saved_best=save_best, patience_counter=stop.counter))
        if stop_now:
            raise AssertionError("Frozen patience=7 cannot stop a three-step diagnostic")
    return dict(history=history, optimizer_schedule=metadata,
        final_state_sha256=tensor_digest(model.state_dict()),
        target_dtypes=dict(train=str(ytrain.dtype), inner_val=str(yvalid.dtype)),
        target_sha256=dict(train=tensor_digest({"target": ytrain}), inner_val=tensor_digest({"target": yvalid})),
        optimizer_steps=3, schedule_steps=scheduler.last_epoch,
        checkpoints_written=False, outer_targets_accessed=False)


def _trajectory(ctx, impl, reducer):
    model, identity, parts = _diagnostic_model(ctx, impl, reducer)
    started = time.monotonic()
    try:
        with diagnostic_default_dtype():
            result = trajectory_for_model(model, parts, ctx["labels"], ctx["config"], ctx["seeds"]["fit"])
        checked_diagnostic_inputs(model, identity, require_initial=False)
        result.update(identity=identity, layer_impl=impl, seconds=time.monotonic()-started)
        return result
    finally:
        del model, parts
        gc.collect()


def validate_static_evidence(report):
    """Recompute numeric decisions; do not trust a top-level passed flag."""
    if (report.get("status") != "passed" or report.get("device") != "cpu"
            or report.get("dtype") != "float64" or report.get("fold") != 0
            or report.get("seed") != 1):
        raise ValueError("Expected passed CPU float64 fold0/seed1 static report")
    layers = report.get("layers")
    if not isinstance(layers, list) or not layers or any(not isinstance(x, dict) or not x for x in layers):
        raise ValueError("Missing per-layer forward evidence")
    records = [row for layer in layers for row in layer.values()] + [report.get("logits", {})]
    for row in records:
        value = row.get("maximum_absolute_difference")
        if (row.get("nonfinite", False) or not isinstance(value, (float, int))
                or isinstance(value, bool) or not math.isfinite(value) or value < 0
                or row.get("tolerance") != 1e-12 or value > 1e-12 or row.get("passed") is not True):
            raise ValueError("Forward evidence fails fixed float64 gate")
    if report.get("forward_passed") is not True:
        raise ValueError("Forward summary contradicts evidence")
    gate = report.get("gradient_comparison", {})
    raw = {}
    for name, row in gate.get("gradients", {}).items():
        raw[name] = {k: row[k] for k in ("passed", "none_old", "none_new", "nonfinite",
            "maximum_absolute_difference", "reference_scale", "candidate_scale", "denominator",
            "relative_difference") if k in row}
        if "original_tolerance" in row:
            raw[name]["tolerance"] = row["original_tolerance"]
    recomputed = compare_gradient_records(raw)
    if recomputed != gate or not recomputed["passed"]:
        raise ValueError("Gradient evidence contradicts fixed float64 gate")
    identity = report.get("identity", {})
    if (identity.get("source_dtype") != "float32" or identity.get("diagnostic_dtype") != "float64"
            or identity.get("lossless_state_and_features") is not True
            or identity.get("original_unchanged") is not True):
        raise ValueError("Missing lossless-cast identity")
    return report


def validate_trajectory_evidence(report):
    """Reload checksummed diagnostic histories and recompute the fixed gate."""
    if (report.get("status") != "passed" or report.get("device") != "cpu"
            or report.get("dtype") != "float64"):
        raise ValueError("Expected passed CPU float64 trajectory report")
    outputs = report.get("outputs", {})
    if set(outputs) != {"original", "shared_projection"}:
        raise ValueError("Missing paired trajectory outputs")
    results = {}
    for impl, ref in outputs.items():
        path = Path(ref["path"])
        if sha256(path) != ref["sha256"]:
            raise ValueError("Trajectory output checksum mismatch")
        result = read_json(path)
        if (result.get("layer_impl") != impl or result.get("optimizer_steps") != 3
                or result.get("checkpoints_written") is not False
                or result.get("outer_targets_accessed") is not False):
            raise ValueError("Trajectory output identity/count mismatch")
        results[impl] = result
    a, b = results["original"], results["shared_projection"]
    for field in ("optimizer_schedule", "target_dtypes", "target_sha256", "identity"):
        if a[field] != b[field]:
            raise ValueError("Trajectory paired input differs: " + field)
    comparison = compare_histories(a["history"], b["history"], TRAJECTORY_ATOL)
    if comparison != report.get("comparison") or not comparison["passed"]:
        raise ValueError("Trajectory summary contradicts fixed numeric gate")
    static_ref = report["static"]
    if sha256(static_ref["path"]) != static_ref["sha256"]:
        raise ValueError("Static report checksum mismatch")
    static = validate_static_evidence(read_json(static_ref["path"]))
    for key in ("task_id", "task", "profile", "reducer", "fold", "seed", "initial", "graph",
                "labels_ref", "folds", "archived_plan", "config", "seeds", "split_sha256", "sources"):
        if static.get(key) != report.get(key):
            raise ValueError("Trajectory/static binding differs: " + key)
    if a["identity"] != static["identity"]:
        raise ValueError("Trajectory/static cast identity differs")
    return report


def _validate_static_report(path, ctx, reducer):
    path = Path(path).resolve()
    report = validate_static_evidence(read_json(path))
    for key, value in _case(ctx, reducer).items():
        if report.get(key) != value:
            raise ValueError("Static evidence identity differs: " + key)
    if report.get("sources") != _source_identity():
        raise ValueError("Computation sources changed since static diagnosis")
    return report, dict(path=str(path), sha256=sha256(path))


def run_trajectory(plan, output, task_id, profile, reducer="mean", static_report_path=None):
    ctx, output = _prepare(plan, output, task_id, profile, reducer)
    static, static_ref = _validate_static_report(static_report_path, ctx, reducer)
    report = dict(_case(ctx, reducer), status="running", sources=_source_identity(), static=static_ref,
                  diagnostic_only=True, no_production_checkpoints=True)
    write_json(output/"trajectory.json", report)
    try:
        results = {}
        for impl in ("original", "shared_projection"):
            result = _trajectory(ctx, impl, reducer)
            if result["identity"] != static["identity"]:
                raise ValueError("Trajectory source/cast differs from static case")
            write_json(output/(impl+".json"), result)
            results[impl] = result
        a, b = results["original"], results["shared_projection"]
        for field in ("optimizer_schedule", "target_dtypes", "target_sha256", "identity"):
            if a[field] != b[field]:
                raise ValueError("Trajectory pair identity differs: " + field)
        comparison = compare_histories(a["history"], b["history"], TRAJECTORY_ATOL)
        report.update(comparison=comparison, status="passed" if comparison["passed"] else "failed_trajectory_gate",
            outputs={impl: dict(path=str(output/(impl+".json")), sha256=sha256(output/(impl+".json"))) for impl in results})
        write_json(output/"trajectory.json", report)
        if not comparison["passed"]:
            raise AssertionError("Float64 three-step trajectory gate failed")
        return report
    except Exception as exc:
        if report["status"] == "running":
            report.update(status="execution_error", error_type=type(exc).__name__, error=str(exc))
            write_json(output/"trajectory.json", report)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("static", "trajectory"))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--profile", choices=("G0", "G3R"), required=True)
    parser.add_argument("--reducer", choices=("mean", "nonempty_mean"), default="mean")
    parser.add_argument("--static-report")
    args = parser.parse_args()
    if args.mode == "trajectory" and not args.static_report:
        parser.error("trajectory requires --static-report")
    kwargs = dict(plan=args.plan, output=args.output, task_id=args.task,
                  profile=args.profile, reducer=args.reducer)
    if args.mode == "trajectory":
        kwargs["static_report_path"] = args.static_report
    result = (run_static if args.mode == "static" else run_trajectory)(**kwargs)
    print(json.dumps({k: result[k] for k in ("status", "task_id", "profile", "reducer")}), flush=True)


if __name__ == "__main__":
    main()
