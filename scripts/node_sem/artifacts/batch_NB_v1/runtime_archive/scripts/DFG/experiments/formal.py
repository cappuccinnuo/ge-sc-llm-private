"""Gated formal paper_kfold orchestration; completed folds resume, epochs do not."""
import argparse
import csv
import fcntl
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from .common import ROOT, REPO, code_hashes, sha256, digest, read_json, write_json, utc
from .paper_protocol import NAME, VERSION, SCORE_ROLE, INITIALIZATION_VERSION, protocol_output
from .formal_checks import verify_fold, metric_summary, METRICS

FORMAT = "ddg-formal-gated-v1"
TASKS = (("reentrancy_author", "contract", 5), ("access_control_author", "contract", 5),
         ("reentrancy_author", "node", 10), ("access_control_author", "node", 10))


def fingerprint_tree(path):
    path = Path(path)
    return {str(f.relative_to(path)): sha256(f) for f in sorted(path.rglob("*")) if f.is_file()}


def git_head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(REPO)).decode().strip()


def init_plan(output, resource_dir, device="cuda:0", threads=2):
    if not device.startswith("cuda") or threads < 1:
        raise ValueError("Formal CUDA batch requires valid device/threads; no automatic CPU fallback")
    output = protocol_output(output)
    jobs, inputs, resources = [], {}, {}
    for cohort, task, k in TASKS:
        prepared = ROOT/"artifacts"/"20261012_v1"/cohort/"prepared"
        splits = ROOT/"artifacts"/NAME/"20261012_v1"/cohort/"splits"/(task+"_folds.json")
        split = read_json(splits)
        if split["seed"] != 1 or [f["fold"] for f in split["folds"]] != list(range(k)):
            raise ValueError("Unexpected frozen seed/folds")
        for f in sorted(prepared.rglob("*")):
            if f.is_file():
                inputs[str(f)] = sha256(f)
        inputs[str(splits)] = sha256(splits)
        report_path = Path(resource_dir)/("resource_"+cohort+"_"+task+".json")
        report = read_json(report_path)
        if (report["device"] != device or report["task"] != task or
            report["prepared"] != str(prepared) or
            report.get("prepared_manifest_sha256") != sha256(prepared/"manifest.json") or
            report.get("split_sha256") != sha256(splits)):
            raise ValueError("Resource evidence input mismatch")
        resources[cohort+"_"+task] = {"path":str(report_path.resolve()), "sha256":sha256(report_path),
                                     "status":report["status"]}
        for fold in range(k):
            jobs.append({"id":cohort+"_"+task+"_fold"+str(fold), "cohort":cohort, "task":task,
                         "fold":fold, "prepared":str(prepared), "splits":str(splits)})
    # Freeze *all* production Python under sco_models as well as experiment/DDG modules.
    frozen = dict(inputs)
    for rel, value in code_hashes().items():
        frozen[str(REPO/rel)] = value
    for f in (REPO/"sco_models").rglob("*.py"):
        frozen[str(f)] = sha256(f)
    plan = {"format":FORMAT, "created_utc":utc(), "protocol":NAME, "protocol_version":VERSION,
            "initialization_version":INITIALIZATION_VERSION, "score_role":SCORE_ROLE,
            "base_git_head":git_head(), "device":device, "threads":threads,
            "mode":"full", "epochs":50, "seed":1, "runner_code_sha256":code_hashes(),
            "frozen_files":frozen, "resources":resources, "jobs":jobs,
            "task_order":[{"cohort":c,"task":t,"folds":k} for c,t,k in TASKS],
            "recovery":"Verified completed paired folds reused; failed attempts retained and restarted only with --retry-failed; NO epoch resume.",
            "gate":"Stage B is one paired fold (2 fits). Stage C requires --confirm-stage-c after B acceptance.",
            "scoring":"CV validation selects and scores best on the same fold. Published paper numbers are external references.",
            "ddg_support":"Registered validation-only relations remain, never invent score-time parameters or drop unsupported folds."}
    output.mkdir(parents=True)
    write_json(output/"plan.json", plan)
    write_json(output/"plan.seal.json", {"sha256":sha256(output/"plan.json")})
    write_json(output/"state.json", {"stage_b":"pending", "stage_c":"pending", "jobs":{}})
    return plan


def validate_plan(root):
    root = Path(root)
    if sha256(root/"plan.json") != read_json(root/"plan.seal.json")["sha256"]:
        raise ValueError("Formal plan changed")
    plan = read_json(root/"plan.json")
    if (plan["format"],plan["protocol"],plan["protocol_version"],plan["score_role"]) != (FORMAT,NAME,VERSION,SCORE_ROLE):
        raise ValueError("Wrong formal protocol")
    if git_head() != plan["base_git_head"] or code_hashes() != plan["runner_code_sha256"]:
        raise ValueError("Frozen code/commit changed; create an explicitly separate batch")
    for path,value in plan["frozen_files"].items():
        if sha256(path) != value:
            raise ValueError("Frozen input or code changed: "+path)
    for r in plan["resources"].values():
        if sha256(r["path"]) != r["sha256"]:
            raise ValueError("Resource evidence changed")
        if r["status"] != "passed":
            raise ValueError("Stage A blocked; no formal training")
    return plan


@contextmanager
def run_lock(root):
    with (Path(root)/".execution.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another formal controller owns this output directory")
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def verify_receipt(root, entry):
    root = Path(root)
    receipt_path = root/entry["receipt"]
    if sha256(receipt_path) != entry["receipt_sha256"]:
        raise ValueError("Completed-fold receipt changed")
    receipt = read_json(receipt_path)
    folder = root/entry["attempt"]
    if fingerprint_tree(folder) != receipt["artifacts"]:
        raise ValueError("Completed-fold artifacts changed or missing")
    return receipt


def process_identity(pid):
    try:
        text = Path("/proc")/str(pid)/"stat"
        fields = text.read_text().rsplit(")",1)[1].split()
        if fields[0] == "Z":
            return None
        return fields[19]  # Linux /proc field 22, after pid/comm.
    except (FileNotFoundError, ProcessLookupError):
        return None


def guard_live_workers(job_root):
    for marker in Path(job_root).glob("*.process.json"):
        process = read_json(marker)
        if process["start_ticks"] is not None and process_identity(process["pid"]) == process["start_ticks"]:
            raise RuntimeError("Previous worker is still alive; do not launch a duplicate: "+str(process["pid"]))


def launch(command, log_path):
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1",
               OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
               TREE_SITTER_LIB_DIR=str(REPO/"build/linux-x86_64"))
    with Path(log_path).open("xb") as log:
        child = subprocess.Popen(command, cwd=str(REPO), env=env, stdout=log, stderr=subprocess.STDOUT)
        write_json(Path(log_path).with_suffix(".process.json"),
                   {"pid":child.pid,"start_ticks":process_identity(child.pid),"created_utc":utc()})
        return child.wait()


def execute_job(root, plan, state, job, retry_failed=False):
    root = Path(root)
    validate_plan(root)
    entry = state["jobs"].get(job["id"])
    if entry and entry["status"] == "passed":
        verify_receipt(root, entry)
        print("REUSE verified "+job["id"], flush=True)
        return
    job_root = root/"jobs"/job["id"]
    old = sorted(job_root.glob("attempt_*")) if job_root.exists() else []
    guard_live_workers(job_root)
    if (entry or old) and not retry_failed:
        raise RuntimeError("Incomplete/failed attempt retained; inspect it, then explicitly use --retry-failed: "+job["id"])
    index = max([int(f.name.split("_")[1].split(".")[0]) for f in old] or [0]) + 1
    attempt = job_root/("attempt_"+str(index).zfill(3))
    if attempt.exists():
        raise FileExistsError(str(attempt))
    job_root.mkdir(parents=True, exist_ok=True)
    log = job_root/(attempt.name+".log")
    # Never reuse a log after a pre-directory crash.
    while log.exists():
        attempt = job_root/("attempt_"+str(int(attempt.name.split("_")[-1])+1).zfill(3))
        log = job_root/(attempt.name+".log")
    command = [sys.executable,"-u","-B","-m","scripts.DFG.experiments.formal_worker",
               "--prepared",job["prepared"],"--splits",job["splits"],"--task",job["task"],
               "--fold",str(job["fold"]),"--device",plan["device"],"--threads",str(plan["threads"]),
               "--output",str(attempt)]
    entry = {"status":"running","attempt":str(attempt.relative_to(root)), "log":str(log.relative_to(root)),
             "started_utc":utc(),"command":command}
    state["jobs"][job["id"]] = entry
    write_json(root/"state.json",state)
    print("START "+job["id"]+"; log="+str(log),flush=True)
    try:
        code = launch(command, log)
        entry["exit_code"] = code
        if code:
            raise RuntimeError("Worker failed (exit "+str(code)+"); see "+str(log))
        accepted = verify_fold(attempt, job, plan)
        validate_plan(root)  # fail if user changed a frozen input while training
        receipt_path = job_root/(attempt.name+".receipt.json")
        write_json(receipt_path, {"accepted_utc":utc(),"acceptance":accepted,
                                "artifacts":fingerprint_tree(attempt)})
        entry.update(status="passed",receipt=str(receipt_path.relative_to(root)),
                     receipt_sha256=sha256(receipt_path),finished_utc=utc())
        write_json(root/"state.json",state)
        print("ACCEPTED "+job["id"],flush=True)
    except Exception as error:
        entry.update(status="failed",error=type(error).__name__+": "+str(error),finished_utc=utc())
        write_json(root/"state.json",state)
        raise


def task_summary(root, plan, state, cohort, task, folds):
    rows = []
    for job in [j for j in plan["jobs"] if j["cohort"]==cohort and j["task"]==task]:
        entry = state["jobs"].get(job["id"])
        if not entry or entry["status"] != "passed":
            raise ValueError("Task incomplete: "+job["id"])
        receipt = verify_receipt(root,entry)
        result = read_json(Path(root)/entry["attempt"]/"result.json")["folds"][0]
        for ck in ("best","last"):
            for v in ("E0","E1"):
                r = result["variants"][v]
                row = {"cohort":cohort,"task":task,"fold":job["fold"],"variant":v,"checkpoint":ck,
                       "protocol":NAME,"score_role":SCORE_ROLE}
                row.update({m:r["cv_validation"][ck][m] for m in METRICS})
                row.update({m+"_E1_minus_E0":result["paired_cv_validation_delta"][ck][m] for m in METRICS})
                a = receipt["acceptance"]["variants"][v]
                row.update({k:a[k] for k in ("best_epoch","last_epoch","epochs","stop_reason","parameter_count",
                    "fit_eval_checkpoint_wall_seconds","ddg_train_edges","ddg_gradient_l1_sum","ddg_message_update_l1")})
                rows.append(row)
    summary = metric_summary(rows,folds)
    dest = Path(root)/"summaries"/(cohort+"_"+task)
    dest.mkdir(parents=True,exist_ok=True)
    write_json(dest/"summary.json",summary)
    write_json(dest/"folds.json",rows)
    with (dest/"folds.csv").open("w",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return summary


def execute_stage(root, stage, confirm_stage_c=False, retry_failed=False):
    root = Path(root).resolve()
    if stage == "stage-c" and not confirm_stage_c:
        raise ValueError("Stage C requires explicit --confirm-stage-c; no automatic 60-fit launch")
    with run_lock(root):
        plan = validate_plan(root)
        state = read_json(root/"state.json")
        first = plan["jobs"][0]
        if stage == "stage-b":
            execute_job(root,plan,state,first,retry_failed)
            state["stage_b"] = "passed"
        elif stage == "stage-c":
            if state["stage_b"] != "passed":
                raise ValueError("Stage B not accepted")
            verify_receipt(root,state["jobs"][first["id"]])
            state["stage_c"] = "running"
            write_json(root/"state.json",state)
            for t in plan["task_order"]:
                for job in [j for j in plan["jobs"] if j["cohort"]==t["cohort"] and j["task"]==t["task"]]:
                    execute_job(root,plan,state,job,retry_failed)
                task_summary(root,plan,state,t["cohort"],t["task"],t["folds"])
                print("TASK VERIFIED "+t["cohort"]+" "+t["task"],flush=True)
            state["stage_c"] = "passed"
        else:
            raise ValueError("Unknown execution stage")
        write_json(root/"state.json",state)
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command",required=True)
    init = sub.add_parser("init")
    init.add_argument("--output",required=True)
    init.add_argument("--resource-dir",required=True)
    init.add_argument("--device",default="cuda:0")
    init.add_argument("--threads",type=int,default=2)
    for name in ("stage-b","stage-c","verify"):
        p = sub.add_parser(name)
        p.add_argument("--run",required=True)
        if name != "verify":
            p.add_argument("--retry-failed",action="store_true")
        if name == "stage-c":
            p.add_argument("--confirm-stage-c",action="store_true")
    args = parser.parse_args()
    if args.command == "init":
        plan = init_plan(args.output,args.resource_dir,args.device,args.threads)
        print("PLAN "+str(Path(args.output)/"plan.json")+"; paired folds="+str(len(plan["jobs"])),flush=True)
    elif args.command == "verify":
        with run_lock(args.run):
            plan = validate_plan(args.run)
            state = read_json(Path(args.run)/"state.json")
            for e in state["jobs"].values():
                if e["status"]=="passed":
                    verify_receipt(args.run,e)
            for t in plan["task_order"]:
                jobs = [j for j in plan["jobs"] if j["cohort"]==t["cohort"] and j["task"]==t["task"]]
                if all(state["jobs"].get(j["id"],{}).get("status")=="passed" for j in jobs):
                    task_summary(args.run,plan,state,t["cohort"],t["task"],t["folds"])
            print(json.dumps({"stage_b":state["stage_b"],"stage_c":state["stage_c"],
                              "accepted_paired_folds":sum(e["status"]=="passed" for e in state["jobs"].values()),
                              "planned_paired_folds":len(plan["jobs"])}),flush=True)
    else:
        execute_stage(args.run,args.command,getattr(args,"confirm_stage_c",False),args.retry_failed)


if __name__ == "__main__":
    main()
