"""Explicitly approved NS-P1 acceptance revision; never restart a completed fit.

Only the scheduler callable comparison changed. Original plans, seals, failure
and both completed reentrancy runs remain read-only. A new plan binds the new
acceptance code; execution.load and all frozen computational code stay intact.
"""
import argparse
import copy
import gc
from pathlib import Path
import time
import traceback

from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, checked, ref
from scripts.DFG.model_validation import assert_model_input
from scripts.DFG.experiments.common import tensor_digest
from . import execution
from .checkpoint_io import load_checked
from .equivalence import (
    DEFAULT_OUT, FEATURE_BINDING_FIELDS, _one_fit, snapshot, compare_fits, assert_exact,
)

CHANGED = {"scripts/node_sem/equivalence.py"}
ADDED = {"scripts/node_sem/equivalence_resume.py"}


def _archive(approval):
    if (approval.get("approved") is not True or not approval.get("user_answer")
            or approval.get("retrain_reentrancy") is not False
            or approval.get("formal_training") is not False):
        raise PermissionError("Explicit bounded acceptance revision approval is required")
    old_path = checked(approval["old_plan"])
    seal = read(checked(approval["old_seal"]))
    if seal["plan"] != approval["old_plan"]:
        raise ValueError("Original plan/seal changed")
    checked(approval["failure"])
    checked(approval["previous_source"])
    for path, sha in approval["retained_files"].items():
        checked(dict(path=path, sha256=sha))
    old = read(old_path)
    if old["runtime"]["scripts/node_sem/equivalence.py"] != approval["previous_source"]["sha256"]:
        raise ValueError("Archived previous acceptance source differs")
    current = execution.runtime_refs()
    if set(current) - set(old["runtime"]) != ADDED or set(old["runtime"]) - set(current):
        raise ValueError("Unexpected acceptance runtime file changes")
    differences = {name for name in old["runtime"] if current[name] != old["runtime"][name]}
    if differences != CHANGED:
        raise ValueError("Only the approved equivalence source may change")
    h8.load(checked(old["source_h8_plan"]))
    return old


def prepare(out=DEFAULT_OUT):
    out = Path(out)
    revision = out / "acceptance_revision1"
    approval_ref = ref(revision / "approval.json")
    approval = read(checked(approval_ref))
    old = _archive(approval)
    matrix = dict(source_h8_plan=old["source_h8_plan"], jobs=old["jobs"],
                  final_server_intent=old["final_server_intent"])
    plan = execution.create(revision / "batch", matrix, dict(
        execution_authorized=False, scope="cpu_equivalence",
        user_request=approval["user_answer"], acceptance_revision=approval_ref,
        original_plan=approval["old_plan"], original_seal=approval["old_seal"],
        stopped_acceptance=approval["failure"], retained_completed_fits=2,
        remaining_cpu_fits=2, no_reentrancy_retraining=True))
    write(revision / "runtime_delta.json", dict(
        approval=approval_ref, old_plan=approval["old_plan"],
        new_plan=ref(revision / "batch/plan.json"),
        changed={k: {"old": old["runtime"][k], "new": plan["runtime"][k]} for k in CHANGED},
        added={k: plan["runtime"][k] for k in ADDED}, computational_code_unchanged=True))
    return plan


def _retained_fit(side, source, plan, old_job, job, folder):
    """Reconstruct initial inputs, read completed weights; no optimizer/fit."""
    cfg = copy.deepcopy(job["config"])
    cfg["maximum_training_epochs"] = 2
    acceptance = read(folder / "cpu_acceptance.json")
    if (acceptance["kind"] != "nonformal_cpu_equivalence"
            or acceptance["original_config"] != job["config"]
            or acceptance["effective_config"] != cfg
            or acceptance["only_config_override"] != ["maximum_training_epochs"]
            or acceptance["actual_device"] != "cpu"):
        raise ValueError("Retained CPU fit configuration differs")
    start = time.monotonic()
    model = (h8.construct(source, old_job, "cpu") if side == "historical"
             else execution.construct(plan, job, "cpu"))
    before = snapshot(model)
    binding, _ = (h8.binding_parts(source, old_job, model, cfg) if side == "historical"
                  else execution.binding_parts(plan, job, model, cfg))
    assert_exact(read(folder / "binding.json"), binding, "retained_binding")
    if tensor_digest(before["state"]) != binding["initial_state_sha256"]:
        raise ValueError("Reconstructed initial does not match retained fit binding")
    checkpoints = {}
    for name in ("best", "last"):
        reference = acceptance["checkpoint_refs"][name]
        if Path(reference["path"]).resolve() != (folder / (name + ".pt")).resolve():
            raise ValueError("Retained checkpoint reference leaves its fit")
        payload = load_checked(reference, map_location="cpu")
        assert_exact(payload["binding"], binding, "retained_checkpoint_binding")
        assert_model_input(model, payload["model_input"], external_inputs=binding)
        checkpoints[name] = payload
    result = read(folder / "result.json")
    if any(result["checkpoint_sha256"][name] != acceptance["checkpoint_refs"][name]["sha256"]
           for name in ("best", "last")):
        raise ValueError("Retained result/checkpoint SHA differs")
    import json
    history = [json.loads(x) for x in (folder / "history.jsonl").read_text().splitlines()]
    predictions = {role: read(folder / (role + "_predictions.json")) for role in (
        "inner_val", "outer_test", "inner_val_orig_all", "outer_test_orig_all")}
    value = dict(before=before,
        # Frozen fit ends its final scoring pass with last.pt restored.
        after=checkpoints["last"]["state_dict"], binding=binding, history=history,
        checkpoints=checkpoints, predictions=predictions, result=result,
        constructor_seconds=acceptance["constructor_seconds"],
        fit_seconds=acceptance["fit_seconds"], folder=str(folder),
        reconstructed_initial_seconds=time.monotonic() - start,
        retained_fit=True, initial_snapshot_reconstructed=True)
    del model
    gc.collect()
    return value


def run(out=DEFAULT_OUT):
    out = Path(out)
    revision = out / "acceptance_revision1"
    if (out / "equivalence.json").exists() or (revision / "failure.json").exists():
        raise FileExistsError("Preserve the completed or failed acceptance revision")
    plan_path = revision / "batch/plan.json"
    plan = execution.load(plan_path)
    authorization = read(checked(plan["authorization"]))
    approval = read(checked(authorization["acceptance_revision"]))
    old = _archive(approval)
    assert_exact(plan["jobs"], old["jobs"], "unchanged_matrix")
    source = h8.load(checked(plan["source_h8_plan"]))
    started, reports = time.monotonic(), []
    try:
        def selected(task_id, profile):
            rows = [j for j in plan["jobs"] if (j["task_id"], j["fold"], j["seed"], j["profile"])
                    == (task_id, 0, 1, profile)]
            if len(rows) != 1:
                raise ValueError("Required equivalence job absent/duplicated")
            return rows[0]
        job = selected("reentrancy_node", "G3R")
        old_job = execution.historical_job(source, job)
        folder = out / "cpu_fits/reentrancy_node/G3R"
        a = _retained_fit("historical", source, plan, old_job, job, folder / "historical")
        b = _retained_fit("nodesem", source, plan, old_job, job, folder / "nodesem")
        record = compare_fits(a, b)
        record.update(task_id=job["task_id"], fold=0, seed=1, profile=job["profile"],
            retained_completed_cpu_fits=2, new_cpu_fits=0,
            initial_snapshot="Fresh zero-step reconstruction matched retained checkpoint input/binding; original in-memory snapshot was not persisted.",
            final_state="Retained last.pt, restored at the end of the unchanged trainer scoring loop.",
            reconstruction_seconds={"historical": a["reconstructed_initial_seconds"],
                                    "nodesem": b["reconstructed_initial_seconds"]})
        reports.append(record)
        print("Retained reentrancy CPU equivalence PASS; zero retraining", flush=True)
        del a, b
        gc.collect()

        job = selected("access_control_contract", "G0")
        old_job = execution.historical_job(source, job)
        folder = revision / "cpu_fits/access_control_contract/G0"
        folder.mkdir(parents=True, exist_ok=False)
        a = _one_fit("historical", source, plan, old_job, job, folder / "historical")
        b = _one_fit("nodesem", source, plan, old_job, job, folder / "nodesem")
        record = compare_fits(a, b)
        record.update(task_id=job["task_id"], fold=0, seed=1, profile=job["profile"],
                      retained_completed_cpu_fits=0, new_cpu_fits=2)
        reports.append(record)
        print("Access control CPU equivalence PASS", flush=True)
        del a, b
        gc.collect()

        reuses = read(checked(approval["historical_reuses"]))
        if reuses.get("passed") is not True or reuses.get("count") != 60:
            raise ValueError("60 historical receipts were not fully accepted")
        # Verify the already accepted receipt bytes again; no additional fits.
        for job in plan["jobs"]:
            checked(job["receipt"])
        _archive(approval)
        execution.load(plan_path)
        payload = dict(version="nodesem-s0-equivalence-v1", passed=True,
            plan=ref(plan_path), original_plan=approval["old_plan"],
            acceptance_revision=authorization["acceptance_revision"],
            retained_failure=approval["failure"], historical_reuse_proof=approval["historical_reuses"],
            formal_fits=0, cpu_acceptance_fits=4, new_cpu_fits_this_revision=2,
            retained_cpu_fits=2, epochs_per_fit=2, actual_device="cpu", gpu_used=False,
            only_training_config_change={"maximum_training_epochs": 2},
            feature_binding_exclusions=sorted(FEATURE_BINDING_FIELDS),
            jobs=reports, historical_reuses_count=60, seconds=time.monotonic() - started,
            original_artifacts_unchanged=True)
        write(out / "equivalence.json", payload)
        write(out / "equivalence.seal.json", dict(result=ref(out / "equivalence.json"), passed=True))
        return payload
    except Exception as error:
        write(revision / "failure.json", dict(error=repr(error), traceback=traceback.format_exc(),
              completed_jobs=reports, automatic_retry=False, seconds=time.monotonic() - started))
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    (prepare if args.command == "prepare" else run)(args.out)


if __name__ == "__main__":
    main()
