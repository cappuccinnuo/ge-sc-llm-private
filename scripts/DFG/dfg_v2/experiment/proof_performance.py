"""Prompt 8B.0 proof-only replays, never a formal batch execution.

Uses the existing frozen initial state/config/fit seed. No plan is rewritten.
The only new trainer path is the checkpoint/input validation guard.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from scripts.DFG.integration.io import read_json, checked, sha256
from scripts.DFG.experiments.common import tensor_digest
from . import run, batch
from .amendment import _changes, _outside_batch

VERSION = "prompt8b0-exact-equivalence-v1"
JOBS = ("access_control_node/0/1/G0", "access_control_node/0/1/G3R")


def _exclusive(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _ref(path):
    return dict(path=str(Path(path).resolve()), sha256=sha256(path))


def load_proof_plan(path):
    # This diagnostic has no amendment yet: compare the entire runtime against
    # the explicit orchestration-only allowlist before bypassing that one gate.
    plan = run._load_plan(path, check_code=False)
    current = run._code_refs()
    differences = _changes(plan["runtime"], current)
    return plan, {row["path"]: {"old_sha256": row["old_sha256"],
                               "new_sha256": row["new_sha256"]} for row in differences}


def worker(plan_path, output, identity, legacy=False):
    started = time.time()
    path, output = Path(plan_path).resolve(), Path(output).resolve()
    if identity not in JOBS:
        raise ValueError("Proof scope is exactly the two registered AC node fold0 jobs")
    _outside_batch(output, path)
    output.mkdir(parents=True, exist_ok=False)
    plan, differences = load_proof_plan(path)
    job = next(j for j in plan["jobs"] if run.job_id(j) == identity)
    old_attempt = run._job_directory(path.parent, job) / "attempt_001"
    # The old reference is independently fully accepted before starting CUDA.
    old_row = batch._accept(path, plan, job)
    if old_row is None or Path(old_row["attempt"]) != old_attempt:
        raise ValueError("Missing unique accepted stage A reference")
    _exclusive(output / "proof_start.json", dict(version=VERSION, proof_only=True,
        formal_result=False, job=job, plan=_ref(path), stage_A_receipt=_ref(old_attempt/"receipt.json"),
        mode="legacy_validation" if legacy else "optimized_validation",
        runtime=run._code_refs(), changed_validation_files=differences,
        started_unix=started, original_plan_unmodified=True))
    attempt = output / "attempt_001"
    from .preflight import run_preflight
    lock = run.ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/.training.lock"
    with run._Lock(lock):
        preflight = run_preflight(job, sha256(path), output, plan["resource_policy"])
        _exclusive(attempt.with_suffix(".started.json"), dict(
            proof_only=True, formal_result=False, job=job, plan_sha256=sha256(path),
            started_unix=time.time(), resume_epoch=False,
            retry_from_same_untrained_initial=True))
        before_fit = time.time()
        try:
            run._run_one(plan, job, attempt, path, preflight=preflight,
                         optimize_validation=not legacy)
        except BaseException as exc:
            _exclusive(output/"failure.json", dict(exception=repr(exc),
                automatic_retry=False, formal_result=False))
            raise
    receipt = read_json(attempt/"receipt.json")
    for name, digest in receipt["artifacts"].items():
        checked(attempt/name, digest)
    result = read_json(attempt/"result.json")
    audit = batch.audit_pilot_result(result, resource_policy=plan["resource_policy"])
    if not audit["passed"] or result["resources"].get("sampling_errors"):
        raise ValueError("Proof fit failed resource/gradient/checkpoint audit")
    task, info, entry = run._prepared(plan, job)
    for role in ("inner_val", "outer_test"):
        run._validate_predictions(read_json(attempt/(role+"_predictions.json")),
                                  role, task, info, entry)
    answer = dict(version=VERSION, proof_only=True, formal_result=False,
        job_id=identity, attempt=str(attempt), original_attempt=str(old_attempt),
        before_fit_seconds=before_fit-started, total_seconds=time.time()-started,
        fit_and_exports_seconds=time.time()-before_fit,
        receipt=_ref(attempt/"receipt.json"), audit=audit)
    _exclusive(output/"worker_result.json", answer)
    return answer


def compare_attempts(new, old):
    import torch
    new, old = Path(new), Path(old)
    histories = [[json.loads(line) for line in (p/"history.jsonl").read_text().splitlines()]
                 for p in (new, old)]
    results = [read_json(p/"result.json") for p in (new, old)]
    keys = ("epoch","train_loss","inner_val_loss","lr","adam_beta1","patience_counter","saved_best")
    checks = dict(history_losses=([{k:r[k] for k in keys} for r in histories[0]] ==
                                  [{k:r[k] for k in keys} for r in histories[1]]),
                  epochs=all(results[0][k] == results[1][k] for k in ("best_epoch","last_epoch")))
    detail = dict(history_rows=[len(h) for h in histories])
    detail["maximum_loss_absolute_difference"] = max(
        [abs(a[k]-b[k]) for a,b in zip(*histories) for k in ("train_loss","inner_val_loss")] or [0])
    refs = {}
    for ck in ("best", "last"):
        states = []
        for label,p in (("new",new),("reference",old)):
            payload = torch.load(str(p/(ck+".pt")),map_location="cpu")
            observed = tensor_digest(payload["state_dict"])
            if observed != payload["state_sha256"]:
                raise ValueError("Checkpoint tensor digest corrupted")
            states.append(observed)
            refs[label+"_"+ck] = _ref(p/(ck+".pt"))
            del payload
        checks[ck+"_state"] = states[0] == states[1]
        detail[ck+"_state_sha256"] = states
    for role in ("inner_val","outer_test"):
        checks[role+"_predictions"] = read_json(new/(role+"_predictions.json")) == read_json(old/(role+"_predictions.json"))
    for label,p in (("new",new),("reference",old)):
        for name in ("history.jsonl","result.json","inner_val_predictions.json",
                     "outer_test_predictions.json","binding.json","initialization_ref.json"):
            refs[label+"_"+name] = _ref(p/name)
    detail["binding_and_initialization"] = all(
        read_json(new/name) == read_json(old/name)
        for name in ("binding.json","initialization_ref.json","effective_config.json","model_input.json"))
    if not detail["binding_and_initialization"]:
        raise ValueError("Proof inputs/config/initialization differ")
    return dict(checks=checks, passed=all(checks.values()), exact=all(checks.values()),
                refs=refs, differences=detail)


def summarize(plan_path, output):
    output, path = Path(output).resolve(), Path(plan_path).resolve()
    plan, changes = load_proof_plan(path)
    jobs = []
    for identity in JOBS:
        name = identity.replace("/", "_")
        worker_result = read_json(output/name/"worker_result.json")
        if read_json(output/name/"proof_start.json")["runtime"] != run._code_refs():
            raise ValueError("Runtime changed since proof execution")
        new, old = Path(worker_result["attempt"]), Path(worker_result["original_attempt"])
        row = compare_attempts(new, old)
        row.update(job_id=identity, comparison_reference="stage_A",
                   timings=dict(optimized=worker_result,
                                historical_result_seconds=read_json(old/"result.json")["seconds"]))
        row["refs"]["worker_result"] = _ref(output/name/"worker_result.json")
        legacy = output/(name+"_legacy")/"worker_result.json"
        if not row["passed"] and legacy.exists():
            old_worker = read_json(legacy)
            if read_json(legacy.parent/"proof_start.json")["runtime"] != run._code_refs():
                raise ValueError("Runtime changed since legacy proof execution")
            historical = dict(checks=row["checks"], differences=row["differences"])
            row = dict(compare_attempts(new,old_worker["attempt"]),job_id=identity,
                       comparison_reference="rerun_old", stage_A_comparison=historical,
                       timings=dict(optimized=worker_result,legacy=old_worker))
            row["refs"]["legacy_worker"] = _ref(legacy)
        jobs.append(row)
    answer = dict(version=VERSION, plan=_ref(path), passed=all(r["passed"] for r in jobs),
        jobs=jobs, proof_only=True, formal_result=False, stage_B_execution_authorized=False,
        runtime=run._code_refs(), changed_validation_files=changes)
    _exclusive(output/"equivalence_result.json",answer)
    return answer


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    worker_parser=sub.add_parser("worker")
    worker_parser.add_argument("--job",choices=JOBS,required=True)
    worker_parser.add_argument("--legacy",action="store_true")
    for command in (worker_parser,sub.add_parser("summarize")):
        command.add_argument("--plan",required=True)
        command.add_argument("--output",required=True)
    args=parser.parse_args(argv)
    answer=(worker(args.plan,args.output,args.job,args.legacy) if args.command=="worker"
            else summarize(args.plan,args.output))
    print(json.dumps({k:v for k,v in answer.items() if k not in ("jobs","runtime")},ensure_ascii=False))
    return answer


if __name__=="__main__":
    main()
