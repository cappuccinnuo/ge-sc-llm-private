"""Serial 20-fit readout experiment; resource preflight and four fit gate."""
import argparse,subprocess,sys,os,re
from pathlib import Path
from .common import *
from .checks import completed

def verify(output,task=None,fold0=False):
    plan=verify_plan(output)
    jobs=[j for j in plan["jobs"] if (task is None or j["task_id"]==task) and (not fold0 or j["fold"]==0)]
    if not jobs:raise ValueError("No requested jobs")
    count=sum(completed(output,j,plan) is not None for j in jobs)
    if count!=len(jobs):raise ValueError("Incomplete candidate results: {}/{}".format(count,len(jobs)))
    return dict(complete_fits=count,score_role="cv_validation",task=task,fold0=fold0)

def run(output=DEFAULT,retry=None,fold0=False):
    output=Path(output);plan=verify_plan(output)
    if retry and retry not in [identity(j) for j in plan["jobs"]]:raise ValueError("Unknown retry identity")
    gate=read_json(output/"preflight.json")
    if gate.get("status")!="passed" or gate.get("plan_sha256")!=digest(plan):raise ValueError("Missing resource/interface preflight")
    import fcntl
    # The shared lock location matches previous controllers, protecting old/new batches.
    lockpath=ROOT/"scripts/DFG/experiments/overall_cv/.execution.lock"
    with lockpath.open("a") as global_lock,(output/".execution.lock").open("a") as lock:
        fcntl.flock(global_lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if not fold0:
            gate=read_json(output/"fold0_acceptance.json")
            if gate.get("plan_sha256")!=digest(plan) or gate.get("status")!="passed":raise ValueError("Missing valid fold0 gate")
            verify(output,fold0=True)
        jobs=[j for j in plan["jobs"] if not fold0 or j["fold"]==0]
        for i,job in enumerate(jobs):
            if completed(output,job,plan):
                print("REUSE",identity(job),flush=True)
            else:
                parent=job_dir(output,job);parent.mkdir(parents=True,exist_ok=True)
                prior=list(parent.glob("attempt_*"))
                if prior and retry!=identity(job):raise RuntimeError("Previous attempt preserved; explicit retry required: "+identity(job))
                numbers=[int(re.match(r"attempt_(\d+)",p.name).group(1)) for p in prior]
                attempt=parent/("attempt_%03d"%(max(numbers,default=0)+1))
                print("START",identity(job),attempt.name,flush=True)
                env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE="1",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",
                         TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64")
                with attempt.with_suffix(".log").open("w") as log:
                    code=subprocess.run([sys.executable,"-B","-m","scripts.DFG.experiments.readout_attention.worker",
                        "--output",str(output),"--task",job["task_id"],"--fold",str(job["fold"]),
                        "--variant",job["variant"],"--attempt",str(attempt)],cwd=str(ROOT),env=env,
                        stdout=log,stderr=subprocess.STDOUT).returncode
                if code:raise RuntimeError("Worker failed; no automatic retry: "+identity(job))
                verify_plan(output)
                if not completed(output,job,plan):raise ValueError("Missing complete receipt")
                print("VERIFIED",identity(job),flush=True)
            if not fold0 and (i==len(jobs)-1 or jobs[i+1]["task_id"]!=job["task_id"]):
                verify(output,job["task_id"])
                from .report import summarize
                summarize(output,(job["task_id"],))
                print("TASK_ACCEPTED",job["task_id"],flush=True)
        if fold0:
            verify(output,fold0=True)
            write_json(output/"fold0_acceptance.json",dict(status="passed",jobs=jobs,plan_sha256=digest(plan),
                complete_checkpoints=8,gate="finite losses, input/gradient/checkpoint/prediction checks; no F1 threshold"))
    return dict(completed_requested=len(jobs),fold0_only=fold0)

def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=("prepare","preflight","run","verify","summarize"))
    p.add_argument("--output",default=str(DEFAULT));p.add_argument("--retry");p.add_argument("--fold0",action="store_true")
    p.add_argument("--task",choices=TASKS);a=p.parse_args()
    if a.command=="prepare":
        from .prepare import prepare
        prepare(a.output)
    elif a.command=="preflight":
        from .preflight import run as preflight
        print(preflight(a.output))
    elif a.command=="run":print(run(a.output,a.retry,a.fold0))
    elif a.command=="verify":print(verify(a.output,a.task,a.fold0))
    else:
        from .report import summarize
        print(summarize(a.output,(a.task,) if a.task else TASKS))
if __name__=="__main__":main()
