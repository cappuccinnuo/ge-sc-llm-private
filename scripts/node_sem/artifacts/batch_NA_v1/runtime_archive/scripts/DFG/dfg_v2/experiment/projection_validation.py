"""Prompt 7b numerical diagnostics; never efficacy or model-selection results.

Reuses trainer.fit, frozen graph/input/state manifests, and unmodified numerical
configuration. Only diagnostic duration, layer implementation and device differ.
The user approved tensor-scale rtol=1e-5 plus atol=1e-8 before real-data execution;
raw tensor and elementwise relative errors remain recorded (no epsilon hiding).
"""
import argparse
import copy
import gc
import json
import math
from pathlib import Path
import torch

from scripts.DFG.experiments.common import (read_json, write_json, sha256,
    seed_all, tensor_digest)
from scripts.DFG.experiments.paper_runtime import graph_schema_and_support
from scripts.DFG.dfg_v2.model import make_model
from scripts.DFG.dfg_v2.supervision import DfgV2Supervision
from scripts.DFG.dfg_v2.tasks import checked_ref, read_labels
from .checkpoint import build_binding
from .resources import Resources
from .support import support as graph_support
from .trainer import fit
from .equivalence import _move, _history

RTOL, ATOL = 1e-5, 1e-8
CPU_CASES = [("reentrancy_contract", p, r) for r in ("mean", "nonempty_mean")
             for p in ("G0", "G3R")] + [("access_control_node", p, "mean") for p in ("G0", "G3R")]


def gradient_difference(old, new):
    if old is None or new is None:
        return dict(none_old=old is None, none_new=new is None,
                    passed=old is None and new is None)
    if old.shape != new.shape or old.dtype != new.dtype:
        raise ValueError("Gradient shape/dtype mismatch")
    a, b = old.double(), new.double()
    if not bool(torch.isfinite(a).all() and torch.isfinite(b).all()):
        return dict(passed=False, nonfinite=True)
    diff = (a-b).abs()
    scale = torch.maximum(a.abs(), b.abs())
    absolute = float(diff.max()) if diff.numel() else 0.0
    magnitude = float(scale.max()) if scale.numel() else 0.0
    relative = absolute/magnitude if magnitude else 0.0
    nz = scale > 0
    elementwise = float((diff[nz]/scale[nz]).max()) if bool(nz.any()) else 0.0
    return dict(maximum_absolute_difference=absolute, tensor_scale=magnitude,
        tensor_relative_difference=relative, elementwise_relative_difference=elementwise,
        pure_relative_passed=relative <= RTOL, tolerance=ATOL+RTOL*magnitude,
        passed=absolute <= ATOL+RTOL*magnitude)


def compare_histories(old, new, tolerance, old_validation="inner_val_loss"):
    if len(old) != 3 or len(new) != 3:
        raise AssertionError("Expected exactly three diagnostic epochs")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Invalid comparison tolerance")
    if [r["epoch"] for r in old] != [0,1,2] or [r["epoch"] for r in new] != [0,1,2]:
        raise ValueError("Diagnostic epoch IDs must be 0,1,2")
    if not all(math.isfinite(r[k]) for seq,vkey in ((old,old_validation),(new,"inner_val_loss"))
               for r in seq for k in ("train_loss",vkey)):
        raise ValueError("Nonfinite diagnostic loss")
    rows = []
    for a, b in zip(old, new):
        if a["epoch"] != b["epoch"]:
            raise AssertionError("Epoch identity mismatch")
        rows.append(dict(epoch=a["epoch"], train=abs(a["train_loss"]-b["train_loss"]),
                         validation=abs(a[old_validation]-b["inner_val_loss"])))
    maximum = max(max(r["train"], r["validation"]) for r in rows)
    return dict(passed=maximum <= tolerance, maximum_absolute_loss_difference=maximum,
                tolerance=tolerance, differences=rows)


def _context(plan_path, task_id, profile):
    plan_path = Path(plan_path).resolve()
    seal = read_json(plan_path.with_name("plan.seal.json"))
    if sha256(plan_path) != seal["plan_sha256"]:
        raise ValueError("Archived plan seal mismatch")
    plan = read_json(plan_path)
    task = plan["tasks"][task_id]
    prep = read_json(checked_ref(task["prepared"]["0/1"]))
    entry = prep["profiles"][profile]
    state = torch.load(str(checked_ref(entry["initial"])), map_location="cpu")
    if (state["kind"] != "untrained_initial" or state["optimizer_steps"] != 0
            or state["task_id"] != task_id or state["fold"] != 0 or state["seed"] != 1
            or state["profile"] != profile or state["fit_seed"] != prep["seeds"]["fit"]
            or tensor_digest(state["state_dict"]) != entry["initial"]["state_sha256"]):
        raise ValueError("Frozen untrained initial identity differs")
    checked_ref(entry["graph"])
    record = task["record"]
    checked_ref(record["folds"])
    labels = read_labels(record["labels"])
    return dict(task_id=task_id, task=record["task"], profile=profile,
        graph=entry["graph"], initial=entry["initial"], state=state["state_dict"],
        config=copy.deepcopy(task["config"]), seeds=prep["seeds"], split=prep["split"],
        folds=record["folds"], labels_ref=record["labels"], labels=labels,
        archived_plan=dict(path=str(plan_path), sha256=sha256(plan_path)))


def _model(ctx, impl, reducer="mean", device="cpu"):
    c = ctx["config"]
    seed_all(ctx["seeds"]["constructor"])
    model = make_model(ctx["task"], checked_ref(ctx["graph"]), ctx["profile"], "cpu",
        hidden_size=c["hidden_size"], layers=c["layers"], heads=c["heads"],
        reducer=reducer, layer_impl=impl)
    model.load_state_dict(ctx["state"], strict=True)
    if tensor_digest(model.state_dict()) != ctx["initial"]["state_sha256"]:
        raise ValueError("Model did not load frozen initial exactly")
    return _move(model, device)


def _parts(model, ctx, historical=False):
    mapping = dict(inner_train="train_files", inner_val="val_files", outer_test="val_files") if historical else {
        k:k+"_files" for k in ("inner_train", "inner_val", "outer_test")}
    return {k:DfgV2Supervision(model, ctx["task"], ctx["split"][v]) for k,v in mapping.items()}


def _forward_and_gradient(ctx, impl, reducer):
    model = _model(ctx, impl, reducer)
    parts = _parts(model, ctx)
    layers, handles = [], []
    def hook(layer, args, output):
        layers.append({k:v.detach().cpu().clone() for k,v in output.items()})
    for layer in model.gcs:
        handles.append(layer.register_forward_hook(hook))
    model.eval()
    with torch.no_grad():
        all_files = sorted({d["source_file"] for _,d in model.nx_graph.nodes(data=True)})
        logits = (model() if ctx["task"] == "node" else model(all_files)[0]).cpu().clone()
    for handle in handles:
        handle.remove()
    model.train()
    model.zero_grad()
    seed_all(ctx["seeds"]["fit"])
    loss = torch.nn.CrossEntropyLoss()(parts["inner_train"].forward(model),
                                      parts["inner_train"].targets(model, ctx["labels"]))
    loss.backward()
    gradients = {k:None if v.grad is None else v.grad.detach().cpu().clone()
                 for k,v in model.named_parameters()}
    result = dict(layers=layers, logits=logits, gradients=gradients,
                  train_loss=float(loss.detach()))
    del model, parts, loss
    gc.collect()
    return result


def _fit_context(ctx, impl, reducer, device, output, historical=False):
    c = copy.deepcopy(ctx["config"])
    c.update(maximum_training_epochs=3, device=device, layer_impl=impl,
             mode="engine_equivalence" if historical else "projection_equivalence")
    if c["schedule_epochs"] != 50 or c["patience"] != 7 or c["delta"] != .001:
        raise ValueError("Frozen diagnostic configuration differs")
    torch.set_num_threads(c["threads"])
    # Includes the CPU->GPU transfer, optimizer, scoring and full checkpoint reload.
    guard = Resources(device)
    try:
        with guard:
            guard.check()
            model = _model(ctx, impl, reducer, device)
            parts = _parts(model, ctx, historical)
            if historical:
                reg = graph_schema_and_support(model.nx_graph, ctx["split"])
                audit = dict(schema=reg["schema"], profile="G0", relations=[], v2_training_edges=0,
                             purpose="engine_equivalence_only")
            else:
                audit = graph_support(model.nx_graph, ctx["profile"], ctx["split"])
            binding = build_binding(model, task_id=ctx["task_id"], fold=0, seed=1,
                profile=ctx["profile"], reducer=reducer, graph_ref=ctx["graph"],
                fold_ref=ctx["folds"], label_ref=ctx["labels_ref"],
                initial_sha256=ctx["initial"]["sha256"], config=c, split=ctx["split"], support=audit)
            binding["initial_state_sha256"] = ctx["initial"]["state_sha256"]
            if historical:
                binding["purpose"] = "engine_equivalence_only_repeated_val_export_not_outer_test"
            seed_all(ctx["seeds"]["fit"])
            result = fit(model, parts, ctx["task"], ctx["labels"], c, output, binding,
                             model.original_graph_node_ids, audit, memory_guard=guard)
        guard.check()
    finally:
        write_json(Path(output).with_suffix(".resources.json"), guard.summary())
    result["resources"] = guard.summary()
    write_json(Path(output)/"result.json", result)
    del model, parts
    gc.collect()
    if str(device).startswith("cuda"):
        torch.cuda.empty_cache()
    return result


def run_cpu_case(plan, output, task_id, profile, reducer):
    if (task_id, profile, reducer) not in CPU_CASES:
        raise ValueError("Not a Prompt 7b CPU acceptance case")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    ctx = _context(plan, task_id, profile)
    torch.set_num_threads(ctx["config"]["threads"])
    old = _forward_and_gradient(ctx, "original", reducer)
    new = _forward_and_gradient(ctx, "shared_projection", reducer)
    if set(old["gradients"]) != set(new["gradients"]) or len(old["layers"]) != len(new["layers"]):
        raise AssertionError("Model parameter/layer identity differs")
    layer_equal = [{k:torch.equal(a[k],b[k]) for k in a} for a,b in zip(old["layers"],new["layers"])]
    logits_equal = torch.equal(old["logits"],new["logits"])
    grads = {k:gradient_difference(old["gradients"][k],new["gradients"][k]) for k in old["gradients"]}
    report = dict(task_id=task_id, profile=profile, reducer=reducer, device="cpu",
        initial=ctx["initial"], graph=ctx["graph"], archived_plan=ctx["archived_plan"],
        layer_outputs_bitwise_equal=layer_equal, logits_bitwise_equal=logits_equal,
        training_forward_loss_equal=old["train_loss"]==new["train_loss"], gradients=grads,
        gradient_rule=dict(rtol=RTOL, atol=ATOL,
          formula="max_abs_difference <= atol + rtol*max(max_abs_old, max_abs_new)",
          approved_before_real_data=True), status="static_checked")
    write_json(output/"equivalence.json", report)
    del old, new
    gc.collect()
    if not logits_equal or not all(all(x.values()) for x in layer_equal) or not all(x["passed"] for x in grads.values()):
        report["status"]="failed_static_gate"
        write_json(output/"equivalence.json",report)
        raise AssertionError("CPU exact forward or approved gradient gate failed")
    for impl in ("original", "shared_projection"):
        _fit_context(ctx, impl, reducer, "cpu", output/impl)
    report["trajectory"] = compare_histories(_history(output/"original"/"history.jsonl"),
        _history(output/"shared_projection"/"history.jsonl"), 1e-6)
    report["status"]="accepted" if report["trajectory"]["passed"] else "failed_trajectory_gate"
    write_json(output/"equivalence.json", report)
    if report["status"] != "accepted":
        raise AssertionError("CPU 3-epoch loss gate failed")
    print(json.dumps({k:v for k,v in report.items() if k not in ("gradients","layer_outputs_bitwise_equal")}),flush=True)
    return report


def summarize_cpu(root):
    root=Path(root)
    reports=[]
    for task,profile,reducer in CPU_CASES:
        path=root/(task+"_"+profile+"_"+reducer)/"equivalence.json"
        r=read_json(path)
        if (r["task_id"],r["profile"],r["reducer"])!=(task,profile,reducer) or r["status"]!="accepted":
            raise ValueError("Missing/failed CPU acceptance case")
        if (not r["logits_bitwise_equal"] or not r["trajectory"]["passed"]
                or not all(all(x.values()) for x in r["layer_outputs_bitwise_equal"])
                or not all(x["passed"] for x in r["gradients"].values())):
            raise ValueError("Contradictory CPU acceptance evidence")
        actual = compare_histories(_history(path.parent/"original"/"history.jsonl"),
            _history(path.parent/"shared_projection"/"history.jsonl"),1e-6)
        if actual != r["trajectory"] or not actual["passed"]:
            raise ValueError("CPU trajectory evidence differs")
        reports.append(dict(task_id=task,profile=profile,reducer=reducer,path=str(path),
            sha256=sha256(path),maximum_absolute_loss_difference=r["trajectory"]["maximum_absolute_loss_difference"]))
    result=dict(status="accepted",cases=reports,case_count=6,diagnostic_fits=12,
        not_counted_as_pilot=True,gradient_atol=ATOL,gradient_rtol=RTOL)
    write_json(root/"acceptance.json",result)
    return result


def _historical_context(manifest, history):
    manifest=Path(manifest).resolve()
    info=read_json(manifest)
    if info["task_id"]!="access_control_author_node" or info["fold"]!=0:
        raise ValueError("GPU replay fixed to access control node fold0")
    hp=Path(history).resolve()
    receipt=read_json(hp.parent/"receipt.json")
    if (receipt.get("status"),receipt.get("task_id"),receipt.get("variant"),receipt.get("fold")) != ("complete","access_control_author_node","HCG",0):
        raise ValueError("Historical receipt identity differs")
    if receipt["artifacts"].get("history.jsonl")!=sha256(hp):
        raise ValueError("Historical history receipt mismatch")
    binding_path=hp.parent/"binding.json"
    if receipt["artifacts"].get("binding.json") != sha256(binding_path):
        raise ValueError("Historical binding receipt mismatch")
    binding=read_json(binding_path)
    initial=info["initialization"]["HCG"]
    expected={"graph_sha256":info["graphs"]["HCG"]["sha256"],
        "graph_labels_sha256":info["labels_sha256"],"source_split_sha256":info["source_splits_sha256"],
        "initial_weights_sha256":initial["sha256"],"initial_state_sha256":initial["state_sha256"],
        "split":info["split"]}
    if any(binding.get(k)!=v for k,v in expected.items()):
        raise ValueError("Historical manifest/binding input identity differs")
    payload=torch.load(str(checked_ref(initial)),map_location="cpu")
    if tensor_digest(payload["state_dict"])!=initial["state_sha256"]:
        raise ValueError("Historical initial tensor digest differs")
    labels_ref=dict(path=info["labels_path"],sha256=info["labels_sha256"])
    ctx=dict(task_id="access_control_node",task="node",profile="G0",graph=info["graphs"]["HCG"],
        initial=initial,state=payload["state_dict"],config=copy.deepcopy(info["config"]),
        seeds=dict(constructor=info["seeds"]["constructor"],fit=info["fit_seed"]),split=info["split"],
        folds=dict(path=info["source_splits_path"],sha256=info["source_splits_sha256"]),
        labels_ref=labels_ref,labels=read_labels(labels_ref))
    ctx["reference"]=dict(manifest=dict(path=str(manifest),sha256=sha256(manifest)),
        history=dict(path=str(hp),sha256=sha256(hp)),receipt=dict(path=str(hp.parent/"receipt.json"),sha256=sha256(hp.parent/"receipt.json")))
    return ctx


def run_gpu_diagnostic(manifest, history, output, impl):
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    ctx=_historical_context(manifest,history)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required; no CPU fallback")
    # Constructor digest is checked before loading history's frozen state.
    seed_all(ctx["seeds"]["constructor"])
    fresh=make_model("node",checked_ref(ctx["graph"]),"G0","cpu",layer_impl=impl)
    if tensor_digest(fresh.state_dict())!=ctx["initial"]["state_sha256"]:
        raise AssertionError("Historical initial no longer matches constructor")
    del fresh
    gc.collect()
    result=_fit_context(ctx,impl,"mean","cuda:0",output/"fit",historical=True)
    comp=compare_histories(_history(history)[:3],_history(output/"fit"/"history.jsonl"),1e-4,"cv_validation_loss")
    # Only original-vs-history is a gate; shared-vs-original is checked separately.
    passed = comp["passed"] if impl == "original" else True
    report=dict(status="accepted" if passed else "failed",layer_impl=impl,
        reference=ctx["reference"],history_comparison=comp,resources=result["resources"],
        purpose="GPU historical numeric diagnostic; repeated val export is not outer test",not_counted_as_pilot=True)
    write_json(output/"diagnostic.json",report)
    if not passed:
        raise AssertionError("GPU historical loss difference exceeds 1e-4")
    return report


def compare_gpu(root):
    root=Path(root)
    a=read_json(root/"original"/"diagnostic.json")
    b=read_json(root/"shared_projection"/"diagnostic.json")
    if (a["status"]!="accepted" or b["status"]!="accepted" or a["reference"]!=b["reference"]
            or a["layer_impl"]!="original" or b["layer_impl"]!="shared_projection"):
        raise ValueError("GPU diagnostics not both accepted with same reference")
    comparison=compare_histories(_history(root/"original"/"fit"/"history.jsonl"),
        _history(root/"shared_projection"/"fit"/"history.jsonl"),1e-4)
    report=dict(status="accepted" if comparison["passed"] else "failed",comparison=comparison,
        resources={"original":a["resources"],"shared_projection":b["resources"]},diagnostic_fits=2)
    write_json(root/"acceptance.json",report)
    if not comparison["passed"]:
        raise AssertionError("GPU implementation loss difference exceeds 1e-4")
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("cpu-case","cpu-summary","gpu-run","gpu-summary"))
    p.add_argument("--output",required=True)
    p.add_argument("--plan")
    p.add_argument("--task")
    p.add_argument("--profile",choices=("G0","G3R"))
    p.add_argument("--reducer",choices=("mean","nonempty_mean"),default="mean")
    p.add_argument("--manifest")
    p.add_argument("--history")
    p.add_argument("--layer-impl",choices=("original","shared_projection"))
    a=p.parse_args()
    if a.mode=="cpu-case": run_cpu_case(a.plan,a.output,a.task,a.profile,a.reducer)
    elif a.mode=="cpu-summary": print(summarize_cpu(a.output))
    elif a.mode=="gpu-run": print(run_gpu_diagnostic(a.manifest,a.history,a.output,a.layer_impl))
    else: print(compare_gpu(a.output))


if __name__=="__main__":
    main()
