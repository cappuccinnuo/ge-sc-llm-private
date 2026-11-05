"""Read-only verification of the recorded overall_cv files, not directory equality."""
from pathlib import Path
from scripts.DFG.experiments.overall_cv import checks as prior_checks
from scripts.DFG.experiments.overall_cv import VERSION as OLD_VERSION,PAIR_VERSION as OLD_PAIR
from scripts.DFG.experiments.overall_cv.common import expected_jobs as old_jobs
from .common import read_json,sha256,recorded_hashes,SOURCE

def verify_archive(source=SOURCE):
    source=Path(source)
    plan=read_json(source/"plan.json")
    if sha256(source/"plan.json")!=read_json(source/"plan.seal.json")["sha256"]:
        raise ValueError("Historical seal mismatch")
    if plan.get("version")!=OLD_VERSION or plan.get("pair_version")!=OLD_PAIR or plan["jobs"]!=old_jobs():
        raise ValueError("Wrong historical batch")
    # Newly added sidecar files and documentation/HEAD changes do not alter old computation.
    recorded_hashes(plan["runtime"])
    recorded_hashes(plan["frozen"])
    accepted=[]
    for job in plan["jobs"]:
        folder=prior_checks.completed(source,job,plan)
        if folder is None:
            raise ValueError("Missing historical completed fit: "+str(job))
        accepted.append(dict(job,attempt=str(folder),receipt=str(folder/"receipt.json"),
                             receipt_sha256=sha256(folder/"receipt.json")))
    return plan,dict(source=str(source),plan_sha256=sha256(source/"plan.json"),
        seal_sha256=sha256(source/"plan.seal.json"),recorded_runtime_unchanged=True,
        frozen_inputs_unchanged=True,successful_fits=len(accepted),results=accepted,
        policy="read-only recorded hash list; added sidecar code is separately frozen; no seal rewrite")
