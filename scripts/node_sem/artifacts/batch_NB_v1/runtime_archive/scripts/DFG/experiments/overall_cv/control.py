"""Serial 60-fit controller with first-pair and complete-task acceptance gates."""
import argparse,subprocess,sys,os,re
from pathlib import Path
from .common import *
from .checks import completed
def verify(output,task=None):
 plan=verify_plan(output);jobs=[j for j in plan["jobs"] if task is None or j["task_id"]==task]
 if task is not None and task not in TASKS:raise ValueError("Unknown task")
 count=sum(completed(output,j,plan) is not None for j in jobs)
 if count!=len(jobs):raise ValueError("Incomplete result matrix: {}/{}".format(count,len(jobs)))
 return {"complete_fits":count,"score_role":"cv_validation","task":task}
def run(output,retry=None,first_pair=False):
 output=Path(output);plan=verify_plan(output)
 if retry and retry not in [identity(j) for j in plan["jobs"]]:raise ValueError("Unknown retry identity")
 import fcntl
 with (Path(__file__).resolve().parent/".execution.lock").open("a") as global_lock, (output/".execution.lock").open("a") as lock:
  fcntl.flock(global_lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  jobs=plan["jobs"][:2] if first_pair else plan["jobs"]
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
     rc=subprocess.run([sys.executable,"-B","-m","scripts.DFG.experiments.overall_cv.worker",
       "--output",str(output),"--task",job["task_id"],"--fold",str(job["fold"]),"--variant",job["variant"],"--attempt",str(attempt)],
       cwd=str(ROOT),env=env,stdout=log,stderr=subprocess.STDOUT).returncode
    if rc:raise RuntimeError("Worker failed; no automatic retry: "+identity(job))
    verify_plan(output)
    if not completed(output,job,plan):raise ValueError("Missing complete receipt")
    print("VERIFIED",identity(job),flush=True)
   if i==1:
    write_json(output/"first_pair_acceptance.json",dict(status="passed",jobs=jobs[:2],plan_sha256=digest(plan),
       complete_checkpoints=4,old_training_loop_unchanged=True,gate="input, gradients, finite losses, checkpoint and predictions; no F1 threshold"))
   if not first_pair and (i==len(jobs)-1 or jobs[i+1]["task_id"]!=job["task_id"]):
    verify(output,job["task_id"])
    from .report import summarize
    summarize(output,(job["task_id"],))
    print("TASK_ACCEPTED",job["task_id"],flush=True)
 return {"completed_requested":len(jobs),"first_pair_only":first_pair}
def main():
 p=argparse.ArgumentParser();p.add_argument("command",choices=("prepare","run","verify","summarize"))
 p.add_argument("--output",default=str(DEFAULT));p.add_argument("--retry");p.add_argument("--first-pair",action="store_true");p.add_argument("--task",choices=TASKS);a=p.parse_args()
 if a.command=="prepare":
  from .prepare import prepare
  prepare(a.output)
 elif a.command=="run":print(run(a.output,a.retry,a.first_pair))
 elif a.command=="verify":print(verify(a.output,a.task))
 else:
  from .report import summarize
  print(summarize(a.output,(a.task,) if a.task else TASKS))
if __name__=="__main__":main()
