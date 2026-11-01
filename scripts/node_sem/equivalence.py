"""CPU-only NS-P1 S0 construction and two-epoch equivalence acceptance.

The frozen 8H trainer is called unchanged. Only maximum_training_epochs is
overridden to two; CPU is selected through construct, not through config.
No GPU work, downloads, formal fits, or changes to historical artifacts.
"""
import argparse
import copy
import gc
import json
from pathlib import Path
import time
import traceback

import numpy as np
import torch

from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref, write
from scripts.DFG.dfg_v2.benchmark_v2.input_guard import FitInputGuard
from scripts.DFG.dfg_v2.benchmark_v2.trainer import fit
from scripts.DFG.dfg_v2.tasks import read_labels
from scripts.DFG.experiments.common import seed_all, tensor_digest
from scripts.labeling_v2.safe_graph import read_graph
from . import TOKEN_IDS, ANON
from . import execution
from .carrier import write_carrier
from .checkpoint_io import load_checked
from .feature_spec import FeatureSpec

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "scripts/node_sem/artifacts/ns_p1_equivalence"
DIGEST_AUDIT = ROOT / "scripts/node_sem/artifacts/ns_p1_initial_digests/digests.json"
TARGETS = (("reentrancy_node", "G3R"), ("access_control_contract", "G0"))
FEATURE_BINDING_FIELDS = {
    "feature_view", "feature_npz", "nodesem_version",
    "feature_spec", "feature_spec_sha256",
}


def assert_exact(left, right, path="root"):
    """No tolerances: compare tensor bits/metadata and nested optimizer state."""
    if torch.is_tensor(left):
        if (not torch.is_tensor(right) or left.dtype != right.dtype
                or left.shape != right.shape or not torch.equal(left.cpu(), right.cpu())):
            raise AssertionError("Tensor differs: " + path)
    elif isinstance(left, np.ndarray):
        if (not isinstance(right, np.ndarray) or left.dtype != right.dtype
                or left.shape != right.shape or not np.array_equal(left, right)):
            raise AssertionError("Array differs: " + path)
    elif isinstance(left, dict):
        if not isinstance(right, dict) or set(left) != set(right):
            raise AssertionError("Dictionary keys differ: " + path)
        for key in left:
            assert_exact(left[key], right[key], path + "/" + str(key))
    elif isinstance(left, (list, tuple)):
        if type(left) is not type(right) or len(left) != len(right):
            raise AssertionError("Sequence differs: " + path)
        for index, (a, b) in enumerate(zip(left, right)):
            assert_exact(a, b, path + "/" + str(index))
    elif path.endswith("/scheduler/anneal_func"):
        # PyTorch 1.8 saves a method bound to the scheduler instance. Two
        # independent runs have different instance identities. The approved
        # comparison requires the exact known implementation, never just its
        # printed name; all remaining state fields keep zero tolerance.
        from types import MethodType
        from torch.optim.lr_scheduler import OneCycleLR
        if (not isinstance(left, MethodType) or not isinstance(right, MethodType)
                or type(left.__self__) is not OneCycleLR
                or type(right.__self__) is not OneCycleLR
                or left.__func__ is not right.__func__
                or left.__func__ is not OneCycleLR._annealing_cos):
            raise AssertionError("Scheduler implementation differs: " + path)
    elif type(left) is not type(right) or left != right:
        raise AssertionError("Value differs: " + path)


def comparison_binding(binding):
    return {key: value for key, value in binding.items()
            if key not in FEATURE_BINDING_FIELDS}


def prepare(out):
    """Seal all 60 S0 historical references; only two jobs undergo CPU proofs."""
    out = Path(out)
    if out.exists():
        raise FileExistsError("Equivalence output already exists; never overwrite")
    audit = read(DIGEST_AUDIT)
    if audit.get("passed") is not True or audit.get("count") != 60:
        raise ValueError("The 60-initial digest gate has not passed")
    source_path = checked(audit["plan"])
    source = h8.load(source_path)
    out.mkdir(parents=True, exist_ok=False)
    (out / "specs").mkdir(exist_ok=False)
    cache, jobs, specifications = {}, [], {}
    for proof in audit["checks"]:
        old_job = proof["job"]
        task_id, profile = old_job["task_id"], old_job["profile"]
        task, info, entry = h8.prepared(source, old_job)
        if entry["initial"] != proof["initial"] or not proof["passed"]:
            raise ValueError("Initial audit reference changed")
        checked(proof["receipt"])
        if task_id not in specifications:
            spec = FeatureSpec("S0", ANON, [
                dict(name=TOKEN_IDS, dim=512, manifest=task["feature_view"], normalize=False)],
                "raw_linear", "raw_linear")
            spec_path = out / "specs" / (task_id + ".json")
            write(spec_path, spec.to_json())
            specifications[task_id] = (spec, ref(spec_path))
        spec, spec_ref = specifications[task_id]
        key = (task_id, profile)
        if key not in cache:
            started = time.monotonic()
            cache[key] = write_carrier(spec, task_id, read_graph(checked(entry["graph"])),
                                      out / "carriers" / task_id / profile)
            print("carrier {} {} complete {:.2f}s".format(
                task_id, profile, time.monotonic() - started), flush=True)
        carrier = cache[key]
        jobs.append(dict(task_id=task_id, granularity=task["granularity"],
            fold=old_job["fold"], seed=old_job["seed"], profile=profile,
            spec=spec_ref, spec_sha256=spec.digest(),
            graph=entry["graph"], folds=task["record"]["folds"],
            labels=task["record"]["labels"], label_view=task["label_view"],
            feature_view=carrier["manifest"], feature_npz=carrier["data"],
            source_preparation=source["source_preparation"], initial=entry["initial"],
            initialization=info["initialization"], split=info["split"],
            graph_files=task["record"]["graph_files"], support=entry["support"],
            config=task["config"], seeds=info["seeds"],
            reuse_8h=True, receipt=proof["receipt"]))
    if len(jobs) != 60:
        raise ValueError("Historical S0 matrix must have 60 unique jobs")
    plan = execution.create(out / "batch",
        dict(source_h8_plan=audit["plan"], jobs=jobs),
        dict(execution_authorized=False, scope="cpu_equivalence",
             user_request="NS-P1: read-only 60 S0 reuses and two real two-epoch CPU equivalence checks; no formal training.",
             checkpoint_load_approval=audit["authorization"]))
    write(out / "preparation.json", dict(
        plan=ref(out / "batch/plan.json"), initial_audit=ref(DIGEST_AUDIT),
        historical_reuses=len(jobs), carrier_count=len(cache), formal_execution_authorized=False))
    return plan


def snapshot(model):
    return dict(state={k: v.detach().cpu().clone() for k, v in model.state_dict().items()},
                inp={key: model.symmetrical_global_graph.nodes[key].data["inp"].detach().cpu().clone()
                     for key in model.symmetrical_global_graph.ntypes},
                etypes=copy.deepcopy(model.etypes_dict),
                ntypes=copy.deepcopy(model.ntypes_dict),
                original_ids=copy.deepcopy(model.original_graph_node_ids))


def _one_fit(side, source, plan, old_job, job, folder):
    task, info, entry = h8.prepared(source, old_job)
    cfg = copy.deepcopy(task["config"])
    cfg["maximum_training_epochs"] = 2
    changes = [key for key in cfg if cfg[key] != task["config"][key]]
    if changes != ["maximum_training_epochs"]:
        raise AssertionError("Equivalence must change only epoch cap")
    torch.set_num_threads(cfg["threads"])
    construct_started = time.monotonic()
    model = (h8.construct(source, old_job, "cpu") if side == "historical"
             else execution.construct(plan, job, "cpu"))
    construct_seconds = time.monotonic() - construct_started
    if model.device != "cpu" and str(model.device) != "cpu":
        raise AssertionError("Equivalence model must stay on CPU")
    before = snapshot(model)
    binding, parts = (h8.binding_parts(source, old_job, model, config=cfg)
                      if side == "historical"
                      else execution.binding_parts(plan, job, model, config=cfg))
    labels = read_labels(task["record"]["labels"])
    seed_all(info["seeds"]["fit"])
    started = time.monotonic()
    with FitInputGuard(model, binding, parts, labels) as guard:
        result = fit(model, guard.wrap_parts(), task["granularity"], labels, cfg, folder,
                     binding, model.original_graph_node_ids, entry["support"])
        guard.finish()
        write(folder / "validation_performance.json", guard.summary())
    fit_seconds = time.monotonic() - started
    after = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    references = {}
    for name in ("best", "last"):
        references[name] = dict(path=str(folder / (name + ".pt")),
                                sha256=result["checkpoint_sha256"][name])
        checked(references[name])
    write(folder / "cpu_acceptance.json", dict(
        kind="nonformal_cpu_equivalence", checkpoint_refs=references,
        original_config=task["config"], effective_config=cfg,
        only_config_override=changes, actual_device="cpu",
        constructor_seconds=construct_seconds, fit_seconds=fit_seconds))
    checkpoints = {name: load_checked(reference, map_location="cpu")
                   for name, reference in references.items()}
    history = [json.loads(line) for line in (folder / "history.jsonl").read_text().splitlines()]
    predictions = {role: read(folder / (role + "_predictions.json")) for role in (
        "inner_val", "outer_test", "inner_val_orig_all", "outer_test_orig_all")}
    del model, parts, labels
    gc.collect()
    return dict(before=before, after=after, binding=binding, history=history,
                checkpoints=checkpoints, predictions=predictions,
                result=result, constructor_seconds=construct_seconds,
                fit_seconds=fit_seconds, folder=str(folder))


def compare_fits(old, new):
    for field in ("before", "after", "predictions"):
        assert_exact(old[field], new[field], field)
    assert_exact(comparison_binding(old["binding"]), comparison_binding(new["binding"]), "binding")
    old_history = [{k: v for k, v in row.items() if k != "seconds"} for row in old["history"]]
    new_history = [{k: v for k, v in row.items() if k != "seconds"} for row in new["history"]]
    assert_exact(old_history, new_history, "history")
    if len(old_history) != 2:
        raise AssertionError("CPU proof did not complete exactly two epochs")
    for ck in ("best", "last"):
        for key in ("state_dict", "state_sha256", "optimizer", "scheduler", "epoch", "monitor"):
            assert_exact(old["checkpoints"][ck][key], new["checkpoints"][ck][key], ck + "/" + key)
    return dict(passed=True, tolerance=0, comparisons={
        name: True for name in ("initial_parameters", "node_features_by_type", "canonical_dictionary",
          "node_dictionary", "original_node_identity", "nonfeature_binding", "every_epoch_loss",
          "final_parameters", "best_and_last_parameters", "adam_state", "scheduler_state",
          "inner_val_predictions", "outer_test_predictions", "auxiliary_original_predictions")},
        scheduler_callable_comparison="same OneCycleLR class and exact _annealing_cos function; distinct instance identity excluded by user approval",
        history=old_history,
        initial_state_sha256=tensor_digest(old["before"]["state"]),
        final_state_sha256=tensor_digest(old["after"]),
        best_epoch=old["result"]["best_epoch"], last_epoch=old["result"]["last_epoch"],
        construction_seconds={side: value["constructor_seconds"]
                              for side, value in (("historical", old), ("nodesem", new))},
        fit_seconds={side: value["fit_seconds"] for side, value in (("historical", old), ("nodesem", new))})


def run(out):
    out = Path(out)
    plan_path = out / "batch/plan.json"
    if (out / "equivalence.json").exists() or (out / "failure.json").exists():
        raise FileExistsError("Acceptance already ran; preserve success/failure")
    plan = execution.load(plan_path)
    source = h8.load(checked(plan["source_h8_plan"]))
    started, reports = time.monotonic(), []
    try:
        for task_id, profile in TARGETS:
            matches = [j for j in plan["jobs"] if (
                j["task_id"], j["fold"], j["seed"], j["profile"]) == (task_id, 0, 1, profile)]
            if len(matches) != 1:
                raise ValueError("Required CPU proof job missing/duplicated")
            job = matches[0]
            old_job = execution.historical_job(source, job)
            task_out = out / "cpu_fits" / task_id / profile
            task_out.mkdir(parents=True, exist_ok=False)
            old = _one_fit("historical", source, plan, old_job, job, task_out / "historical")
            new = _one_fit("nodesem", source, plan, old_job, job, task_out / "nodesem")
            report = compare_fits(old, new)
            report.update(task_id=task_id, fold=0, seed=1, profile=profile)
            reports.append(report)
            print("EXACT CPU equivalence PASS " + task_id + " " + profile, flush=True)
            del old, new
            gc.collect()
        # Only read/validate historical successes. Never invoke fit_one/controller.
        reuses = []
        for index, job in enumerate(plan["jobs"], 1):
            accepted = execution.verify_one(plan_path, plan, job)
            if not accepted.get("reuse_8h") or not accepted["audit"]["passed"]:
                raise AssertionError("Historical receipt reuse failed")
            reuses.append(dict(job_id=execution.job_id(job), receipt=job["receipt"], passed=True))
            if index % 10 == 0:
                print("read-only historical acceptance {}/60".format(index), flush=True)
        if execution.runtime_refs() != plan["runtime"]:
            raise AssertionError("Runtime changed during equivalence check")
        h8.load(checked(plan["source_h8_plan"]))
        payload = dict(version="nodesem-s0-equivalence-v1", passed=True, plan=ref(plan_path),
            formal_fits=0, cpu_acceptance_fits=4, epochs_per_fit=2, actual_device="cpu",
            gpu_used=False, only_training_config_change={"maximum_training_epochs": 2},
            feature_binding_exclusions=sorted(FEATURE_BINDING_FIELDS), jobs=reports,
            historical_reuses=reuses, seconds=time.monotonic() - started)
        write(out / "equivalence.json", payload)
        write(out / "equivalence.seal.json", dict(result=ref(out / "equivalence.json"), passed=True))
        return payload
    except Exception as error:
        write(out / "failure.json", dict(error=repr(error), traceback=traceback.format_exc(),
              completed_jobs=reports, automatic_retry=False, seconds=time.monotonic() - started))
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.out)
    else:
        run(args.out)


if __name__ == "__main__":
    main()
