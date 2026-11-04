"""Separate plan and immutable manifests; original batches remain read-only."""
from pathlib import Path
from scripts.DFG.experiments.common import read_json,write_json,sha256,digest,tensor_digest,seed_all
from scripts.DFG.experiments.overall_cv.common import ROOT,TASKS,task_kind,folds,identity,job_dir,task_ref,recorded_hashes
from . import VERSION,PAIR_VERSION,VARIANT,VARIANTS
DEFAULT = ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/guard_extension_v1"
SOURCE = ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1"
def expected_jobs():
    return [dict(task_id=t,fold=f,variant=VARIANT) for t in TASKS for f in range(folds(t))]
def runtime_hashes():
    roots = [ROOT/"scripts/DFG/control_dependency", Path(__file__).resolve().parent]
    return {str(p):sha256(p) for root in roots for p in sorted(root.rglob("*.py"))
            if not {"__pycache__","artifacts"}&set(p.parts)}
def verify_plan(output):
    output=Path(output);p=read_json(output/"plan.json")
    if sha256(output/"plan.json")!=read_json(output/"plan.seal.json")["sha256"]:
        raise ValueError("Plan seal mismatch")
    if p["version"]!=VERSION or p["pair_version"]!=PAIR_VERSION or p["jobs"]!=expected_jobs():
        raise ValueError("Wrong guard experiment matrix")
    refs=[(x["task_id"],x["fold"]) for x in p["tasks"]]
    if len(refs)!=30 or set(refs)!={(t,f) for t in TASKS for f in range(folds(t))}:
        raise ValueError("Wrong fold manifests")
    if p["runtime"]!=runtime_hashes():
        raise ValueError("New experiment runtime drift")
    recorded_hashes(p["frozen"])
    recorded_hashes(p["historical_runtime"])
    return p
