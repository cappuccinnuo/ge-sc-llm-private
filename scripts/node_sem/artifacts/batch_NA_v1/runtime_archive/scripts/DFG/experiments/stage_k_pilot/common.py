"""Independent batch identities and immutable dependencies."""
from pathlib import Path
import subprocess
from scripts.DFG.experiments.common import read_json,write_json,sha256,digest,tensor_digest,seed_all
from . import VERSION,VARIANTS
ROOT=Path(__file__).resolve().parents[4]
DEFAULT=ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/stage_k_v1"
TASKS=("reentrancy_author_node","access_control_author_node")
def expected_jobs():
 return [{"task_id":t,"variant":v,"fold":0} for t in TASKS for v in VARIANTS]
def runtime_hashes():
 paths=[p for p in (ROOT/"scripts/DFG").rglob("*.py") if "artifacts" not in p.parts and "audit" not in p.parts and "__pycache__" not in p.parts]
 paths += list((ROOT/"sco_models").glob("*.py"))
 return {str(p):sha256(p) for p in sorted(paths)}
def verify_plan(output):
 p=read_json(Path(output)/"plan.json")
 if sha256(Path(output)/"plan.json")!=read_json(Path(output)/"plan.seal.json")["sha256"]:raise ValueError("Plan seal mismatch")
 if p["version"]!=VERSION or p["jobs"]!=expected_jobs():raise ValueError("Wrong job matrix")
 if p["runtime"]!=runtime_hashes():raise ValueError("Runtime drift")
 if subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip()!=p["head"]:raise ValueError("HEAD drift")
 for name,h in p["frozen"].items():
  if sha256(name)!=h:raise ValueError("Frozen input changed: "+name)
 return p
