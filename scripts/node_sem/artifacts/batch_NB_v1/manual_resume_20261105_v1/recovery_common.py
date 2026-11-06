"""Manual one-time retry authorization for one confirmed GPU telemetry timeout."""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent
BATCH=HERE.parent
JOB="access_control_node__G3R__S4m__fold_8"
ERROR="MemoryGateError('Current whole-card memory measurement failed; refusing stale sample')"

def read_json(path):
    return json.loads(Path(path).read_text())

def checked(reference):
    path=Path(reference["path"])
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1048576),b""):
            digest.update(block)
    if digest.hexdigest()!=reference["sha256"]:
        raise ValueError("Recovery-bound file changed: "+str(path))
    return path

def validate_failure(failure, resource):
    if (failure.get("error")!=ERROR or failure.get("cuda_oom") is not False
            or failure.get("phase")!="train_and_score"
            or failure.get("automatic_retry") is not False):
        raise PermissionError("This manual retry covers only the inspected telemetry failure")
    errors=resource.get("sampling_errors",[])
    if (not errors or not all("nvidia-smi" in e and "timed out after 5 seconds" in e for e in errors)
            or resource.get("minimum_free_mib",0)<100
            or resource.get("epoch_timing",{}).get("completed_epochs")!=15):
        raise PermissionError("Telemetry evidence differs from the inspected failure")

def validate_scope(root, job, old, auth):
    expected=(BATCH/"runs"/JOB/"attempt_001").resolve()
    if (Path(root).resolve()!=BATCH.resolve() or job!=auth["failed_job"]
            or len(old)!=1 or Path(old[0]).resolve()!=expected
            or (expected/"complete.json").exists()
            or (expected.parent/"attempt_002").exists()):
        raise PermissionError("Manual retry is limited to the failed job's second attempt")

def load_authorization():
    auth=read_json(HERE/"authorization.json")
    if (auth.get("manual_resume_authorized") is not True
            or auth.get("user_request")!="从中断启动后面的"
            or auth.get("maximum_manual_retries")!=1
            or auth.get("failed_job_id")!=JOB
            or auth.get("recovery_mode")!="same_initial_restart_failed_fit_only"):
        raise PermissionError("Manual resume authorization differs")
    for reference in auth["protected_bindings"]+auth["recovery_sources"]+auth["failed_attempt_files"]:
        checked(reference)
    evidence=BATCH/"runs"/JOB/"attempt_001"
    validate_failure(read_json(evidence/"failure.json"),read_json(evidence/"resources/resource_summary.json"))
    return auth

def validate_manual_retry(root, plan, job, old):
    auth=load_authorization()
    validate_scope(root,job,old,auth)
    if auth["plan"]["sha256"]!=hashlib.sha256((Path(root)/"plan.json").read_bytes()).hexdigest():
        raise PermissionError("Manual retry plan differs")
    if job not in plan["jobs"]:
        raise PermissionError("Retry job absent from original sealed plan")
