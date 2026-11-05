"""Stage H1 serial controller; immutable plans, audited reuse, no H2 execution."""
import argparse,json,subprocess,sys,time,os
from pathlib import Path
from types import FunctionType
from scripts.DFG.experiments.common import read_json,write_json,sha256,digest,utc
from scripts.DFG.experiments.e23_pilot import control as g
from scripts.DFG.experiments.e23_pilot.inputs import ROOT,TASK_ORDER,check_hashes,DEFAULT_OUTPUT as STAGE_G
from .prepare import DEFAULT_OUTPUT
from . import BATCH_VERSION,H1_VARIANTS

def runtime_hashes():
    hashes=g.runtime_hashes()
    for p in Path(__file__).parent.rglob("*.py"):hashes[str(p)]=sha256(p)
    hashes[str(ROOT/"scripts/verify_e23_archive.py")]=sha256(ROOT/"scripts/verify_e23_archive.py")
    return hashes
def identity(job):return job["task_id"]+"/fold_"+str(job["fold"])+"/"+job["variant"]
def job_dir(output,job,mode="full"):
    if mode!="full":raise ValueError("H1 accepts full fits only; no new smoke reuse as fit")
    return Path(output)/"runs"/job["task_id"]/("fold_"+str(job["fold"]))/job["variant"]
existing_success=FunctionType(g.existing_success.__code__,dict(g.existing_success.__globals__,job_dir=job_dir),g.existing_success.__name__)
verify_fit=g.verify_fit
def expected_jobs(variants,include_zero=True):
    return [(t,f,v) for t in TASK_ORDER for f in range(0 if include_zero else 1,5 if t.endswith("_contract") else 10) for v in variants]
def validate_jobs(plan):
    actual=[(j["task_id"],j["fold"],j["variant"]) for j in plan["jobs"]]
    if actual!=expected_jobs(H1_VARIANTS):raise ValueError("H1 matrix/order changed")
    if sum(j["fold"]>0 for j in plan["jobs"])!=52:raise ValueError("Expected 52 new fits")
    for j in plan["jobs"]:
        if j.get("source")!=("stage_g_reuse" if j["fold"]==0 else "stage_h_fresh"):raise ValueError("Illegal reuse identity")

def seal(output):
    output=Path(output)
    if (output/"plan.json").exists():raise FileExistsError("Do not overwrite plan/seal")
    inputs=read_json(output/"input_manifest.json");reuse=read_json(output/"fold0_reuse_audit.json")
    if reuse["status"]!="passed" or len(reuse["fold0_initial_state_checks"])!=12:raise ValueError("Reuse gate failed")
    tests=read_json(output/"integration_tests.json")
    if tests["returncode"]!=0 or read_json(output/"original_resource_test.json")["returncode"]!=0:raise ValueError("Regression gate failed")
    if read_json(output/"baseline_preflight.json")["status"]!="passed":raise ValueError("Baseline comparison gate failed")
    files={str(output/n):sha256(output/n) for n in ("input_manifest.json","fold0_reuse_audit.json","baseline_inventory.json","baseline_hashes.json","integration_tests.json","original_resource_test.json","baseline_preflight.json","github_check.json","gpu_preflight.json")}
    gp=read_json(STAGE_G/"plan.json");files[str(STAGE_G/"plan.json")]=sha256(STAGE_G/"plan.json")
    files[str(STAGE_G/"plan.seal.json")]=sha256(STAGE_G/"plan.seal.json")
    files.update(gp["frozen_files"])
    jobs=[];h2=[]
    for item in inputs["tasks"]:
        info=read_json(item["manifest"])
        if sha256(item["manifest"])!=item["sha256"]:raise ValueError("Input-manifest drift")
        files[item["manifest"]]=item["sha256"];files.update(info["frozen_files"])
        files[info["initialization_audit_path"]]=info["initialization_audit_sha256"]
        for v in ("E2","E3a","E3b"):
            initial=info["initialization"][v];files[initial["path"]]=initial["sha256"]
            j={"task_id":item["task_id"],"cohort":info["cohort"],"task":info["task"],"fold":item["fold"],
               "variant":v,"task_manifest":item["manifest"],"task_manifest_sha256":item["sha256"],"source":item["source"]}
            if item["fold"]==0:
                rr=next(r for r in reuse["reused"] if r["task_id"]==item["task_id"] and r["variant"]==v)
                j["stage_g_job"]=rr["job"];j["stage_g_receipt"]=rr["receipt"];j["stage_g_receipt_sha256"]=rr["sha256"]
                receipt=read_json(rr["receipt"]);parent=Path(rr["receipt"]).parent
                files[rr["receipt"]]=rr["sha256"]
                files.update({str(parent/n):h for n,h in receipt["artifact_sha256"].items()})
            (h2 if v=="E3a" else jobs).append(j)
    check_hashes(files)
    plan={"format":BATCH_VERSION,"created_utc":utc(),"protocol":"paper_kfold","protocol_version":"ddg-paper-kfold-v1",
          "score_role":"cv_validation","forward_scope":"complete_fixed_task_graph","jobs":jobs,
          "runtime_code_sha256":runtime_hashes(),"frozen_files":files,"base_git_head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip(),
          "seed":1,"schedule_epochs":50,"device":"cuda:0","threads":2,"new_fits_authorized":52,"reused_fits":8,
          "h2_execution_authorized":False,"execution_policy":"one GPU worker; stop on error; explicit retry only",
          "computation_version":"unchanged Stage G model/runtime/training/checkpoint; new scheduling and metadata only"}
    validate_jobs(plan)
    h2plan={"format":"stage-h2-reserved-v1","execution_authorized":False,"new_fits":26,"reused_fits":4,"jobs":h2,
            "h1_plan_sha256":digest(plan),"initialization":"same already sealed untrained E3a states; never E2 trained weights",
            "rules":"same frozen paper_kfold and numerical configuration; no selected-fold subset"}
    write_json(output/"plan.json",plan);write_json(output/"plan.seal.json",{"sha256":sha256(output/"plan.json")})
    write_json(output/"h2_plan.json",h2plan);write_json(output/"h2_plan.seal.json",{"sha256":sha256(output/"h2_plan.json")})
    return plan

def verify_plan(output):
    output=Path(output);p=read_json(output/"plan.json")
    if sha256(output/"plan.json")!=read_json(output/"plan.seal.json")["sha256"]:raise ValueError("H1 seal drift")
    if p["format"]!=BATCH_VERSION or p["h2_execution_authorized"] or p["device"]!="cuda:0":raise ValueError("Wrong batch policy")
    if p["base_git_head"]!=subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip():raise ValueError("HEAD drift")
    if p["runtime_code_sha256"]!=runtime_hashes():raise ValueError("Runtime source drift")
    validate_jobs(p);check_hashes(p["frozen_files"])
    if sha256(output/"h2_plan.json")!=read_json(output/"h2_plan.seal.json")["sha256"]:raise ValueError("Reserved H2 plan drift")
    h2=read_json(output/"h2_plan.json")
    if h2["execution_authorized"] or h2["h1_plan_sha256"]!=digest(p):raise ValueError("H2 binding drift")
    if [(j["task_id"],j["fold"],j["variant"]) for j in h2["jobs"]]!=expected_jobs(("E3a",)):raise ValueError("H2 incomplete")
    return p

def locate(output,job,plan):
    if job["source"]=="stage_g_reuse":
        path=Path(job["stage_g_receipt"])
        if sha256(path)!=job["stage_g_receipt_sha256"]:raise ValueError("Reused receipt drift")
        gplan=read_json(STAGE_G/"plan.json")
        verify_fit(path.parent,job["stage_g_job"],"full",gplan)
        return path.parent,[path.parent]
    return existing_success(output,job,"full",plan)

def verify(output):
    plan=verify_plan(output);new=reused=0
    for job in plan["jobs"]:
        ok,_=locate(output,job,plan)
        if ok:
            if job["fold"]==0:reused+=1
            else:new+=1
    return {"new_complete":new,"stage_g_reused":reused,"total_complete":new+reused,"expected_total":60}

def execute(output,retry=None):
    output=Path(output)
    with g.execution_lock(Path(__file__).parent), g.execution_lock(output):
        plan=verify_plan(output)
        allowed={identity(j) for j in plan["jobs"] if j["fold"]>0}
        if retry is not None and retry not in allowed:raise ValueError("Retry is not an authorized H1 job")
        for task_id in TASK_ORDER:
            task_jobs=[j for j in plan["jobs"] if j["task_id"]==task_id]
            for job in task_jobs:
                verify_plan(output);ok,attempts=locate(output,job,plan)
                if ok:print("REUSE",identity(job),flush=True);continue
                if attempts and retry!=identity(job):raise RuntimeError("Failed/partial attempt retained; investigate before explicit retry: "+identity(job))
                parent=job_dir(output,job);parent.mkdir(parents=True,exist_ok=True)
                number=max((int(a.name.split("_")[1]) for a in attempts),default=0)+1
                attempt=parent/("attempt_%03d"%number)
                cmd=[sys.executable,"-B","-m","scripts.DFG.experiments.e23_cv.worker","--output",str(output),"--task",task_id,"--fold",str(job["fold"]),"--variant",job["variant"],"--attempt",str(attempt)]
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
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("command",choices=("prepare","seal","run","verify","summarize"))
    p.add_argument("--output",default=str(DEFAULT_OUTPUT));p.add_argument("--retry");a=p.parse_args()
    if a.command=="prepare":
        from .prepare import prepare
        prepare(a.output)
    elif a.command=="seal":seal(a.output)
    elif a.command=="run":execute(a.output,a.retry)
    elif a.command=="verify":print(json.dumps(verify(a.output)))
    else:
        if verify(a.output)["total_complete"]!=60:raise ValueError("H1 incomplete")
        from .report import summarize
        summarize(a.output)
if __name__=="__main__":main()
