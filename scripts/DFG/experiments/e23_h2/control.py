"""H2 serial E3a scheduling. Historical plans/seals are read-only."""
import argparse, json, subprocess, sys, time, os
from pathlib import Path
from types import FunctionType
from scripts.DFG.experiments.common import read_json, write_json, sha256, digest, utc
from scripts.DFG.experiments.e23_pilot import control as g
from scripts.DFG.experiments.e23_cv import control as h1
from scripts.DFG.experiments.e23_pilot.inputs import ROOT, TASK_ORDER, check_hashes, DEFAULT_OUTPUT as STAGE_G
from . import H1, DEFAULT_OUTPUT, BATCH_VERSION
from .archive import audit

identity = h1.identity
job_dir = h1.job_dir
verify_fit = g.verify_fit
existing_success = h1.existing_success
locate = h1.locate

def runtime_hashes():
    hashes = h1.runtime_hashes()
    hashes[str(ROOT / "scripts/verify_h1_archive.py")] = sha256(ROOT / "scripts/verify_h1_archive.py")
    for p in Path(__file__).parent.rglob("*.py"): hashes[str(p)] = sha256(p)
    return hashes

def validate_jobs(plan):
    actual = [(j["task_id"], j["fold"], j["variant"]) for j in plan["jobs"]]
    if actual != h1.expected_jobs(("E3a",)):
        raise ValueError("H2 must contain exactly 30 ordered E3a jobs")
    if sum(j["fold"] > 0 for j in plan["jobs"]) != 26:
        raise ValueError("Expected exactly 26 new fits")
    for j in plan["jobs"]:
        if j["source"] != ("stage_g_reuse" if j["fold"] == 0 else "stage_h_fresh"):
            raise ValueError("Wrong reuse source")

def seal(output):
    output = Path(output)
    if (output / "plan.json").exists() or (output / "plan.seal.json").exists():
        raise FileExistsError("Never overwrite a plan/seal")
    tests = read_json(output / "integration_tests.json")
    if tests["returncode"] != 0: raise ValueError("H2 tests failed")
    archive, files = audit()
    write_json(output / "archive_audit.json", archive)
    write_json(output / "fold0_reuse_audit.json", archive["fold0_reuse"])
    for name in ("archive_audit.json", "fold0_reuse_audit.json", "integration_tests.json"):
        files[str(output / name)] = sha256(output / name)
    previous = read_json(H1 / "plan.json"); reserved = read_json(H1 / "h2_plan.json")
    plan = {"format":BATCH_VERSION, "created_utc":utc(), "protocol":"paper_kfold",
        "protocol_version":previous["protocol_version"], "score_role":"cv_validation",
        "forward_scope":"complete_fixed_task_graph", "jobs":reserved["jobs"],
        "base_git_head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip(),
        "runtime_code_sha256":runtime_hashes(), "frozen_files":files,
        "historical_h1_plan":str(H1/"plan.json"), "historical_h1_plan_sha256":sha256(H1/"plan.json"),
        "reserved_h2_plan":str(H1/"h2_plan.json"), "reserved_h2_plan_sha256":sha256(H1/"h2_plan.json"),
        "execution_authorized":True, "authorization":"User Stage H2 request: 26 new E3a fits, 4 fold0 reuse, stop at complete ablation",
        "new_fits_authorized":26, "reused_fits":4, "seed":previous["seed"],
        "schedule_epochs":previous["schedule_epochs"], "device":previous["device"], "threads":previous["threads"],
        "computation_version":"exact e23_pilot model/Supervision/fit/checkpoint; frozen per-task config; saved E3a initial only",
        "execution_policy":"single GPU; stop on failure; no auto retry; no E2/E3b training"}
    validate_jobs(plan)
    write_json(output/"plan.json",plan); write_json(output/"plan.seal.json",{"sha256":sha256(output/"plan.json")})
    return plan

def verify_plan(output):
    output=Path(output); plan=read_json(output/"plan.json")
    if sha256(output/"plan.json") != read_json(output/"plan.seal.json")["sha256"]: raise ValueError("H2 seal drift")
    if plan["format"] != BATCH_VERSION or not plan["execution_authorized"] or plan["device"] != "cuda:0":
        raise ValueError("Wrong H2 execution policy")
    if plan["base_git_head"] != subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip():
        raise ValueError("H2 execution HEAD drift")
    if plan["runtime_code_sha256"] != runtime_hashes(): raise ValueError("Runtime source drift")
    validate_jobs(plan); check_hashes(plan["frozen_files"])
    reserved=read_json(plan["reserved_h2_plan"])
    if reserved["execution_authorized"] or reserved["jobs"] != plan["jobs"]:
        raise ValueError("Historical reserved plan changed")
    return plan

def verify(output):
    plan=verify_plan(output); new=reused=0
    for job in plan["jobs"]:
        folder,_=locate(output,job,plan)
        if folder:
            if job["fold"]==0: reused+=1
            else: new+=1
    return {"new_complete":new,"stage_g_reused":reused,"total_complete":new+reused,"expected_total":30}

def execute(output,retry=None):
    output=Path(output)
    with g.execution_lock(Path(__file__).parent), g.execution_lock(output):
        plan=verify_plan(output)
        allowed={identity(j) for j in plan["jobs"] if j["fold"]>0}
        if retry is not None and retry not in allowed:raise ValueError("Retry is not an authorized H2 job")
        for task_id in TASK_ORDER:
            task_jobs=[j for j in plan["jobs"] if j["task_id"]==task_id]
            for job in task_jobs:
                verify_plan(output);ok,attempts=locate(output,job,plan)
                if ok:print("REUSE",identity(job),flush=True);continue
                if attempts and retry!=identity(job):raise RuntimeError("Failed/partial attempt retained; investigate before explicit retry: "+identity(job))
                parent=job_dir(output,job);parent.mkdir(parents=True,exist_ok=True)
                number=max((int(a.name.split("_")[1]) for a in attempts),default=0)+1
                attempt=parent/("attempt_%03d"%number)
                cmd=[sys.executable,"-B","-m","scripts.DFG.experiments.e23_h2.worker","--output",str(output),"--task",task_id,"--fold",str(job["fold"]),"--variant",job["variant"],"--attempt",str(attempt)]
                print("START",identity(job),attempt.name,flush=True);started=time.perf_counter()
                with attempt.with_suffix(".log").open("x") as log:
                    proc=subprocess.run(cmd,cwd=str(ROOT),env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONUNBUFFERED="1"),stdout=log,stderr=subprocess.STDOUT)
                write_json(attempt.with_suffix(".execution.json"),{"command":cmd,"returncode":proc.returncode,"seconds":time.perf_counter()-started})
                if proc.returncode:raise RuntimeError("Worker failed; STOP, no automatic retry: "+str(attempt))
                result=verify_fit(attempt,job,"full",plan)
                print("COMPLETE",identity(job),json.dumps(result["cv_validation"]["best"]),flush=True)
            for job in task_jobs:
                if locate(output,job,plan)[0] is None:raise ValueError("Task incomplete")
            write_json(output/(task_id+"_complete.json"),{"status":"passed","fits":len(task_jobs),"plan_sha256":digest(plan),"utc":utc()})
            print("TASK_ACCEPTED",task_id,flush=True)
    return True

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("command",choices=("seal","run","verify","summarize"))
    p.add_argument("--output",default=str(DEFAULT_OUTPUT));p.add_argument("--retry");a=p.parse_args()
    if a.command=="seal": seal(a.output)
    elif a.command=="run": execute(a.output,a.retry)
    elif a.command=="verify": print(json.dumps(verify(a.output)))
    else:
        from .report import summarize
        summarize(a.output)
if __name__=="__main__": main()
