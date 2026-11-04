"""Independent immutable plan, jobs, and input identities."""
from pathlib import Path
import subprocess
from scripts.DFG.experiments.common import read_json,write_json,sha256,digest,tensor_digest,seed_all
from . import VERSION,VARIANTS,PAIR_VERSION
ROOT=Path(__file__).resolve().parents[4]
DEFAULT=ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1"
TASKS=("reentrancy_author_contract","access_control_author_contract","reentrancy_author_node","access_control_author_node")
def task_kind(t):
 if t not in TASKS:raise ValueError("Unknown task")
 return "contract" if t.endswith("_contract") else "node"
def folds(t):return 5 if task_kind(t)=="contract" else 10
def expected_jobs():
 return [{"task_id":t,"fold":f,"variant":v} for t in TASKS for f in range(folds(t)) for v in VARIANTS]
def identity(j):return "{}/fold_{}/{}".format(j["task_id"],j["fold"],j["variant"])
def job_dir(output,j):return Path(output)/"runs"/j["task_id"]/("fold_"+str(j["fold"]))/j["variant"]
def runtime_hashes():
 paths=[p for p in (ROOT/"scripts/DFG").rglob("*.py") if not {"artifacts","audit","__pycache__"}&set(p.parts)]
 paths+=list((ROOT/"sco_models").glob("*.py"))
 return {str(p):sha256(p) for p in sorted(paths)}
def recorded_hashes(mapping):
 for path,h in mapping.items():
  if sha256(path)!=h:raise ValueError("Frozen input/source changed: "+str(path))
def task_ref(plan,task,fold):
 refs=[x for x in plan["tasks"] if x["task_id"]==task and x["fold"]==fold]
 if len(refs)!=1:raise ValueError("Missing/duplicate task manifest")
 return refs[0]
def verify_plan(output):
 output=Path(output);p=read_json(output/"plan.json")
 if sha256(output/"plan.json")!=read_json(output/"plan.seal.json")["sha256"]:raise ValueError("Plan seal mismatch")
 if p["version"]!=VERSION or p["pair_version"]!=PAIR_VERSION or p["jobs"]!=expected_jobs():raise ValueError("Wrong experiment/matrix")
 expected={(t,f) for t in TASKS for f in range(folds(t))}
 refs=[(t["task_id"],t["fold"]) for t in p["tasks"]]
 if len(refs)!=30 or set(refs)!=expected:raise ValueError("Wrong fold manifests")
 if p["runtime"]!=runtime_hashes():raise ValueError("Runtime drift")
 if subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip()!=p["head"]:raise ValueError("HEAD drift")
 recorded_hashes(p["frozen"])
 return p
