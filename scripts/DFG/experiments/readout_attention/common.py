"""New batch, exact prior input references, no old seal changes."""
from pathlib import Path
from scripts.DFG.experiments.common import read_json,write_json,sha256,digest,tensor_digest,seed_all
from scripts.DFG.experiments.overall_cv.common import ROOT,identity,job_dir,task_ref,recorded_hashes
from . import VERSION,PAIR_VERSION,VARIANTS,READOUT
DEFAULT=ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/readout_attention_v1"
SOURCES={"HCG":ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1",
         "HCG_DDG_GUARD":ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/guard_extension_v1"}
TASKS=("reentrancy_author_contract","access_control_author_contract")
def task_kind(t):
    if t not in TASKS:raise ValueError("Unknown contract task")
    return "contract"
def folds(t):
    task_kind(t);return 5

def expected_jobs():return [dict(task_id=t,fold=f,variant=v) for t in TASKS for f in range(5) for v in VARIANTS]
def runtime_hashes():
    return {str(p):sha256(p) for p in sorted(Path(__file__).parent.rglob("*.py")) if "__pycache__" not in p.parts}
def verify_plan(output):
    output=Path(output);p=read_json(output/"plan.json")
    if sha256(output/"plan.json")!=read_json(output/"plan.seal.json")["sha256"]:raise ValueError("Plan seal mismatch")
    if p["version"]!=VERSION or p["pair_version"]!=PAIR_VERSION or p["jobs"]!=expected_jobs():raise ValueError("Wrong readout matrix")
    refs=[(x["task_id"],x["fold"]) for x in p["tasks"]]
    if len(refs)!=10 or set(refs)!={(t,f) for t in TASKS for f in range(5)}:raise ValueError("Wrong fold manifests")
    if p.get("readout")!=READOUT or not p.get("execution_authorized"):raise ValueError("Wrong readout specification/authorization")
    if p["runtime"]!=runtime_hashes():raise ValueError("Attention runtime drift")
    recorded_hashes(p["historical_runtime"]);recorded_hashes(p["frozen"])
    return p
