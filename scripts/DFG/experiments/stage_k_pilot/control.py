"""Serial two-task paired pilot; no per-detail ablations or automatic retry."""
import argparse,subprocess,sys,os,re
from pathlib import Path
from .common import *
def completed(output,job,plan):
 parent=Path(output)/"runs"/job["task_id"]/job["variant"]
 found=[]
 for p in sorted(parent.glob("attempt_*/receipt.json")):
  receipt=read_json(p)
  if any(receipt.get(k)!=v for k,v in dict(job,status="complete",plan_sha256=digest(plan)).items()):
   raise ValueError("Receipt identity drift")
  for name,h in receipt["artifacts"].items():
   if sha256(p.parent/name)!=h:raise ValueError("Result artifact changed")
  found.append(p.parent)
 if len(found)>1:raise ValueError("Duplicate successful fit")
 return found[0] if found else None
def run(output,retry=None):
 output=Path(output);plan=verify_plan(output)
 import fcntl
 with (output/".execution.lock").open("a") as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for job in plan["jobs"]:
   if completed(output,job,plan):
    print("REUSE successful current-batch",job,flush=True);continue
   parent=output/"runs"/job["task_id"]/job["variant"];parent.mkdir(parents=True,exist_ok=True)
   prior=list(parent.glob("attempt_*"))
   identity=job["task_id"]+"/"+job["variant"]
   if prior and retry!=identity:raise RuntimeError("Previous attempt preserved; explicit retry required: "+identity)
   numbers=[int(re.match(r"attempt_(\d+)",p.name).group(1)) for p in prior]
   attempt=parent/("attempt_%03d"%(max(numbers,default=0)+1))
   print("START",identity,attempt.name,flush=True)
   env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE="1",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",
            TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64")
   with attempt.with_suffix(".log").open("w") as log:
    rc=subprocess.run([sys.executable,"-B","-m","scripts.DFG.experiments.stage_k_pilot.worker",
       "--output",str(output),"--task",job["task_id"],"--variant",job["variant"],"--attempt",str(attempt)],
       cwd=str(ROOT),env=env,stdout=log,stderr=subprocess.STDOUT).returncode
   if rc:raise RuntimeError("Worker failed; no automatic retry: "+identity)
   verify_plan(output)
   if not completed(output,job,plan):raise ValueError("Worker missing complete receipt")
   print("VERIFIED",identity,flush=True)
 return True
def main():
 p=argparse.ArgumentParser();p.add_argument("command",choices=("prepare","run","verify","summarize"))
 p.add_argument("--output",default=str(DEFAULT));p.add_argument("--retry");a=p.parse_args()
 if a.command=="prepare":
  from .prepare import prepare
  prepare(a.output)
 elif a.command=="run":run(a.output,a.retry)
 elif a.command=="verify":
  plan=verify_plan(a.output)
  count=sum(completed(a.output,j,plan) is not None for j in plan["jobs"])
  if count!=4:raise ValueError("Incomplete: "+str(count))
  print({"complete_fits":count,"score_role":"cv_validation"})
 else:
  from .report import summarize
  summarize(a.output)
if __name__=="__main__":main()
