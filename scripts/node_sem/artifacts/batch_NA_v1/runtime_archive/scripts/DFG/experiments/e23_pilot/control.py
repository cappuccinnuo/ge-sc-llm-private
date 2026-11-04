"""Small sealed pilot controller: one subprocess/GPU model at a time, no auto retries."""
import argparse,json,subprocess,sys,time,os,re,fcntl
from contextlib import contextmanager
from pathlib import Path
from .inputs import ROOT,ORIGINAL,DEFAULT_OUTPUT,TASK_ORDER,check_hashes
from . import VARIANTS,EXPERIMENT_VERSION,ADAPTER_VERSION,TRIPLE_INITIALIZATION_VERSION
from scripts.DFG.experiments.common import read_json,write_json,sha256,digest,code_hashes,utc
from scripts.DFG.experiments.paper_protocol import NAME,VERSION,SCORE_ROLE,FORWARD_SCOPE
def runtime_hashes():
    hashes={str(ROOT/p):h for p,h in code_hashes().items()}
    extra=list((ROOT/"sco_models").glob("*.py"))
    extra+=list((ROOT/"scripts/DFG/state/stage_f").glob("*.py"))
    extra+=list((ROOT/"scripts/DFG/experiments/e23_pilot").rglob("*.py"))
    extra+=[ROOT/"scripts/labeling_v2/safe_graph.py"]
    for p in extra:hashes[str(p)]=sha256(p)
    return hashes

def seal(output):
    output=Path(output)
    if (output/"plan.json").exists():raise FileExistsError("Do not overwrite a pilot plan")
    review=ROOT/"scripts/DFG/experiments/e23_pilot/review/review_manifest.json";rv=read_json(review)
    if rv["review_status"]!="passed_finite_static_gate" or rv["semantic_blocker_found"]:raise ValueError("Finite relation review failed")
    check_hashes({str(review.parent/k):h for k,h in rv["files"].items()})
    inputs_path=output/"input_manifest.json";inputs=read_json(inputs_path)
    files={str(inputs_path):sha256(inputs_path),str(review):sha256(review)}
    files.update({str(review.parent/k):h for k,h in rv["files"].items()})
    jobs=[]
    if [x["id"] for x in inputs["tasks"]]!=list(TASK_ORDER):raise ValueError("Task order changed")
    for item in inputs["tasks"]:
        if sha256(item["manifest"])!=item["sha256"]:raise ValueError("Input manifest drift")
        info=read_json(item["manifest"]);files[item["manifest"]]=item["sha256"];files.update(info["frozen_files"])
        files[info["initialization_audit_path"]]=info["initialization_audit_sha256"]
        for variant in VARIANTS:
            init=info["initialization"][variant];files[init["path"]]=init["sha256"]
            jobs.append({"task_id":info["task_id"],"cohort":info["cohort"],"task":info["task"],"fold":0,
                         "variant":variant,"task_manifest":item["manifest"],"task_manifest_sha256":item["sha256"]})
    check_hashes(files)
    tests=read_json(output/"integration_tests.json")
    if tests["returncode"]!=0:raise ValueError("Integration tests not passed")
    files[str(output/"integration_tests.json")]=sha256(output/"integration_tests.json")
    plan={"format":EXPERIMENT_VERSION,"created_utc":utc(),"protocol":NAME,"protocol_version":VERSION,
          "score_role":SCORE_ROLE,"forward_scope":FORWARD_SCOPE,"adapter_version":ADAPTER_VERSION,
          "triple_initialization_version":TRIPLE_INITIALIZATION_VERSION,
          "base_git_head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip(),
          "runtime_code_sha256":runtime_hashes(),"frozen_files":files,"jobs":jobs,"seed":1,
          "schedule_epochs":50,"smoke_epochs":3,"device":"cuda:0","threads":2,
          "execution_policy":"serial single GPU variant; fresh CPU initial states; stop on any execution error",
          "full_fits_authorized":12,"remaining_kfold_fits_not_authorized":78,
          "review_identity":{"Codex_static":True,"human_approved":False,"compiled":False},
          "recovery":"verified successful fits reused; failed attempts retained; explicit retry after investigation only; no epoch resume"}
    write_json(output/"plan.json",plan);write_json(output/"plan.seal.json",{"sha256":sha256(output/"plan.json")})
    return plan
def verify_plan(output):
    output=Path(output);plan=read_json(output/"plan.json")
    if sha256(output/"plan.json")!=read_json(output/"plan.seal.json")["sha256"]:raise ValueError("Pilot plan seal changed")
    if plan["format"]!=EXPERIMENT_VERSION or plan["device"]!="cuda:0":raise ValueError("Wrong experiment/device policy")
    current=subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip()
    if current!=plan["base_git_head"]:raise ValueError("Code HEAD drift; do not rewrite plan")
    if runtime_hashes()!=plan["runtime_code_sha256"]:raise ValueError("Runtime source drift")
    check_hashes(plan["frozen_files"])
    return plan
def job_dir(output,job,mode):
    return Path(output)/("smoke" if mode=="smoke" else "runs")/job["task_id"]/"fold_0"/job["variant"]
def verify_fit(folder,job,mode,plan):
    from scripts.DFG.experiments.common import metrics
    from scripts.DFG.experiments.checkpoint import StopMonitor
    folder=Path(folder);receipt=read_json(folder/"receipt.json")
    if receipt["status"]!="complete" or receipt["job"]!=job or receipt["mode"]!=mode:
        raise ValueError("Receipt identity mismatch")
    if receipt["plan_sha256"]!=digest(plan):raise ValueError("Receipt plan differs")
    check_hashes({str(folder/k):v for k,v in receipt["artifact_sha256"].items()})
    result=read_json(folder/"result.json");binding=read_json(folder/"binding.json")
    if digest(binding)!=receipt["binding_sha256"]:raise ValueError("Binding differs")
    info=read_json(job["task_manifest"]);initial=info["initialization"][job["variant"]]
    if result["initial_sha256"]!=initial["state_sha256"] or binding["initial_weights_sha256"]!=initial["sha256"]:raise ValueError("Initial state mismatch")
    if binding["split"]!=info["split"] or binding["graph_sha256"]!=info["graphs"][job["variant"]]["sha256"]:raise ValueError("Input or split mismatch")
    history=[json.loads(x) for x in (folder/"history.jsonl").read_text().splitlines()]
    limit=3 if mode=="smoke" else 50
    if result["history_rows"]!=len(history) or not 1<=len(history)<=limit:raise ValueError("Epoch inventory differs")
    if mode=="smoke" and len(history)!=3:raise ValueError("Smoke did not complete three optimizer steps")
    stop=StopMonitor(7,0.001);best=None
    for i,row in enumerate(history):
        save,ended=stop.step(row["cv_validation_loss"])
        if save:best=i
        if row["epoch"]!=i or row["saved_best"]!=save or row["patience_counter"]!=stop.counter:raise ValueError("Selection changed")
        if ended and i!=len(history)-1:raise ValueError("Continued after early stop")
    if len(history)<limit and not ended:raise ValueError("Premature fit termination")
    if result["best_epoch"]!=best or result["last_epoch"]!=len(history)-1:raise ValueError("Checkpoint epoch differs")
    if read_json(folder/"optimizer_schedule.json")["initial_state"]["total_steps"]!=50:raise ValueError("Schedule compressed")
    predictions=read_json(folder/"cv_validation_predictions.json");truth=[r["target"] for r in predictions]
    import math
    for ck in ("best","last"):
        scores=metrics(truth,[r[ck] for r in predictions])
        if scores!=result["cv_validation"][ck]:raise ValueError("Prediction metrics do not recompute")
        if not all(math.isfinite(r[ck+"_positive_probability"]) and 0<=r[ck+"_positive_probability"]<=1 for r in predictions):raise ValueError("Invalid probabilities")
        if sha256(folder/(ck+".pt"))!=result["checkpoint_sha256"][ck] or not result["checkpoint_roundtrip_exact"][ck]:raise ValueError("Checkpoint integrity/reload failed")
        meta=read_json(folder/(ck+".json"))
        if meta["binding"]!=binding or meta["epoch"]!=(best if ck=="best" else len(history)-1):raise ValueError("Checkpoint identity mismatch")
    if set(r["file"] for r in predictions)!=set(info["split"]["val_files"]):raise ValueError("Scored files differ")
    ids=[r["original_graph_node_id"] if job["task"]=="node" else r["file"] for r in predictions]
    if len(ids)!=len(set(ids)):raise ValueError("Duplicate scored identities")
    return result
def attempt_inventory(parent):
    """Count each attempt once, including worker failures before mkdir.

    The .log is created before spawning the worker. A failed startup can leave
    only that log and .failure/.execution sidecars. Unknown sidecar extensions
    also reserve the ID; never overwrite an abandoned attempt's evidence.
    """
    parent=Path(parent);numbers=set()
    if not parent.exists():return []
    for path in parent.iterdir():
        if not path.name.startswith("attempt_"):continue
        match=re.match(r"^attempt_(\d+)(?:$|\.)",path.name)
        if not match:raise ValueError("Unrecognized attempt artifact: "+str(path))
        number=int(match.group(1));prefix="attempt_%03d"%number
        if number<1 or match.group(1)!=prefix[len("attempt_"):]:
            raise ValueError("Noncanonical attempt number: "+str(path))
        numbers.add(number)
    return [parent/("attempt_%03d"%number) for number in sorted(numbers)]

@contextmanager
def execution_lock(output):
    """One controller per canonical output path; do not unlink the lock inode."""
    output=Path(output).resolve()
    if not output.is_dir():raise FileNotFoundError("Pilot output is absent: "+str(output))
    with (output/".execution.lock").open("a+") as handle:
        try:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            handle.seek(0);owner=handle.read().strip()
            raise RuntimeError("Another controller holds the output execution lock: "+owner)
        try:
            handle.seek(0);handle.truncate()
            handle.write(json.dumps({"pid":os.getpid(),"acquired_utc":utc(),"output":str(output)})+"\n")
            handle.flush()
            yield
        finally:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)

def existing_success(output,job,mode,plan):
    attempts=attempt_inventory(job_dir(output,job,mode))
    successes=[]
    for attempt in attempts:
        if (attempt/"receipt.json").exists():
            if attempt.with_suffix(".failure.json").exists():
                raise ValueError("Conflicting success receipt and worker failure: "+str(attempt))
            execution=attempt.with_suffix(".execution.json")
            if execution.exists() and read_json(execution)["returncode"]!=0:
                raise ValueError("Conflicting success receipt and failed execution: "+str(attempt))
            verify_fit(attempt,job,mode,plan);successes.append(attempt)
    if len(successes)>1:raise ValueError("Multiple successful fits; no best-of-attempt selection")
    return successes[0] if successes else None,attempts

def execute(output,mode,retry=None):
    with execution_lock(output):
        return _execute_locked(output,mode,retry)

def _execute_locked(output,mode,retry=None):
    if mode not in ("smoke","full"):raise ValueError("Unknown execution mode")
    output=Path(output);plan=verify_plan(output)
    if retry is not None and retry not in {j["task_id"]+"/"+j["variant"] for j in plan["jobs"]}:
        raise ValueError("Retry identity is not a frozen pilot job")
    if mode=="full":
        for job in plan["jobs"]:
            ok,_=existing_success(output,job,"smoke",plan)
            if ok is None:raise ValueError("All twelve smoke checks must pass before formal fitting")
    for job in plan["jobs"]:
        verify_plan(output);success,attempts=existing_success(output,job,mode,plan)
        if success:
            print("REUSE",mode,job["task_id"],job["variant"],flush=True);continue
        identity=job["task_id"]+"/"+job["variant"]
        if attempts and retry!=identity:raise RuntimeError("Previous attempt retained. Investigate then explicitly retry "+identity)
        parent=job_dir(output,job,mode);parent.mkdir(parents=True,exist_ok=True)
        next_number=max((int(p.name.split("_")[1]) for p in attempts),default=0)+1
        attempt=parent/("attempt_%03d"%next_number)
        cmd=[sys.executable,"-B","-m","scripts.DFG.experiments.e23_pilot.worker","--output",str(output),
             "--task",job["task_id"],"--variant",job["variant"],"--mode",mode,"--attempt",str(attempt)]
        print("START",mode,identity,attempt.name,flush=True);start=time.perf_counter()
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONUNBUFFERED="1")
        with attempt.with_suffix(".log").open("x") as log:
            process=subprocess.run(cmd,cwd=str(ROOT),env=env,stdout=log,stderr=subprocess.STDOUT)
        write_json(attempt.with_suffix(".execution.json"),{"command":cmd,"returncode":process.returncode,"seconds":time.perf_counter()-start})
        if process.returncode:raise RuntimeError("Worker failed; no automatic retry: "+str(attempt.with_suffix(".log")))
        result=verify_fit(attempt,job,mode,plan)
        print("COMPLETE",mode,identity,"best",result["cv_validation"]["best"],flush=True)
    return True
def verify_all(output):
    plan=verify_plan(output);counts={}
    for mode in ("smoke","full"):
        counts[mode]=sum(existing_success(output,j,mode,plan)[0] is not None for j in plan["jobs"])
    return counts
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=("prepare","seal","smoke","run","verify","summarize"))
    p.add_argument("--output",default=str(DEFAULT_OUTPUT));p.add_argument("--retry")
    a=p.parse_args()
    if a.command=="prepare":
        from .prepare import prepare
        prepare(a.output)
    elif a.command=="seal":seal(a.output)
    elif a.command in ("smoke","run"):execute(a.output,"smoke" if a.command=="smoke" else "full",a.retry)
    elif a.command=="verify":print(json.dumps(verify_all(a.output)))
    else:
        if verify_all(a.output)!={"smoke":12,"full":12}:raise ValueError("Incomplete pilot")
        from .report import summarize
        summarize(Path(a.output))
if __name__=="__main__":main()
