"""Separate diagnostic plan; historical plans are only read and hashed."""
import json
from pathlib import Path
from scripts.DFG.experiments.audit.ddg_diagnostics_v1.diagnostic_common import (
    read_json, write_json, file_sha, TOLERANCES)
from scripts.DFG.experiments.e23_pilot.inputs import TASK_ORDER
from . import VERSION

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
H2 = REPO / "scripts/DFG/experiments/artifacts/paper_kfold/stage_h2_v1"
DEFAULT_OUTPUT = REPO / "scripts/DFG/experiments/artifacts/paper_kfold/stage_i_v1"
CONDITIONS = {
    "N": (),
    "Z_D": ("STATE_DEF_USE",),
    "Z_S": ("STATE_ACCESS_ORDER",),
    "Z_C": ("EXTERNAL_CALL_BEFORE_STATE_WRITE",),
    "Z_SC": ("STATE_ACCESS_ORDER", "EXTERNAL_CALL_BEFORE_STATE_WRITE"),
    "Z_ALL": ("STATE_DEF_USE", "STATE_ACCESS_ORDER", "EXTERNAL_CALL_BEFORE_STATE_WRITE"),
}
ROLE = "exploratory_cv_validation_fixed_checkpoint_sensitivity"


def key(job):
    return (job["task_id"], int(job["fold"]), job["variant"])


def validate_jobs(jobs):
    actual = [key(j) for j in jobs]
    expected = {(t, f, v) for t in TASK_ORDER
                for f in range(5 if t.endswith("_contract") else 10)
                for v in ("E3a", "E3b")}
    if len(actual) != 60 or len(set(actual)) != 60 or set(actual) != expected:
        raise ValueError("Expected exactly all 60 E3a/E3b task folds")
    for j in jobs:
        if j["task"] != ("contract" if j["task_id"].endswith("_contract") else "node"):
            raise ValueError("Task unit mismatch")


def build_plan(output):
    output = Path(output)
    if output.exists() and {p.name for p in output.iterdir()} != {"static"}:
        raise FileExistsError("Only a precomputed static evidence directory may precede this plan")
    h2 = read_json(H2 / "plan.json")
    h1path = Path(h2["historical_h1_plan"])
    h1 = read_json(h1path)
    from scripts.verify_h1_archive import verify as verify_h1
    from scripts.verify_h2_archive import verify as verify_h2
    archive_checks = {"H1": verify_h1(h1path.parent), "H2": verify_h2(H2)}
    accepted = {key(x): x for x in read_json(H2 / "report.json")["accepted"]}
    jobs = []
    for parent_path, parent in ((H2 / "plan.json", h2), (h1path, h1)):
        for job in parent["jobs"]:
            if job["variant"] not in ("E3a", "E3b"):
                continue
            found = accepted[key(job)]
            attempt = Path(found["attempt"])
            if file_sha(attempt / "receipt.json") != found["receipt_sha256"]:
                raise ValueError("Accepted receipt changed")
            jobs.append(dict(job, historical_plan=str(parent_path),
                historical_plan_sha256=file_sha(parent_path),
                historical_output=str(parent_path.parent), attempt=str(attempt),
                receipt_sha256=found["receipt_sha256"]))
    jobs.sort(key=lambda j: (TASK_ORDER.index(j["task_id"]), j["fold"], j["variant"]))
    validate_jobs(jobs)
    import subprocess
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(REPO)).decode().strip()
    runtime = {str(p): file_sha(p) for p in HERE.rglob("*.py")}
    old = REPO / "scripts/DFG/experiments/audit/ddg_diagnostics_v1"
    runtime.update({str(p): file_sha(p) for p in old.glob("*.py")})
    for prior in (h1, h2):
        for path, value in prior["runtime_code_sha256"].items():
            if file_sha(path) != value:
                raise ValueError("Historical computation changed: " + path)
            runtime[path] = value
    historical = {}
    for directory in (H2, h1path.parent):
        for name in ("plan.json", "plan.seal.json", "report.json"):
            p = directory / name
            historical[str(p)] = file_sha(p)
    plan = dict(version=VERSION, git_head=head, score_role=ROLE, source_score_role="cv_validation",
        inference_only=True, optimizer_steps=0, retraining=False, jobs=jobs,
        checkpoints=["best", "last"], conditions=CONDITIONS, tolerances=TOLERANCES,
        direction="existing forward adapter", cross_mean_denominator="unchanged",
        runtime_sha256=runtime, historical_sha256=historical,
        unsupported_modifier="unchanged function-level fallback",
        record_messages="N and Z_ALL only; others sensitivity-only to avoid redundant reductions",
        device="cuda:0", sequential_models=True, archive_checks=archive_checks)
    static = output / "static"
    if not static.exists() and output != DEFAULT_OUTPUT:
        static = DEFAULT_OUTPUT / "static"
    plan["observed_static_sha256"] = {str(p): file_sha(p) for p in static.rglob("*") if p.is_file()} if static.exists() else {}
    plan["static_provenance"] = "Observed Stage F sidecars; not retrospectively certified by H2 seal"
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "plan.json", plan)
    write_json(output / "plan.seal.json", {"plan_sha256": file_sha(output / "plan.json")})
    return plan


def verify_plan(output):
    output = Path(output)
    if file_sha(output / "plan.json") != read_json(output / "plan.seal.json")["plan_sha256"]:
        raise ValueError("Diagnostic plan seal differs")
    plan = read_json(output / "plan.json")
    validate_jobs(plan["jobs"])
    if plan["version"] != VERSION or plan["score_role"] != ROLE or not plan["inference_only"]:
        raise ValueError("Wrong diagnostic protocol")
    for section in ("runtime_sha256", "historical_sha256", "observed_static_sha256"):
        for path, expected in plan[section].items():
            if file_sha(path) != expected:
                raise ValueError("Frozen diagnostic dependency changed: " + path)
    return plan


def job_output(output, job):
    return Path(output) / "replays" / job["task_id"] / ("fold_" + str(job["fold"])) / job["variant"]


def verified_success(dest, expected_plan_sha256=None, expected_job=None):
    dest = Path(dest)
    if not (dest / "receipt.json").exists():
        if dest.exists():
            raise ValueError("Incomplete/failed replay preserved; explicit investigation required: " + str(dest))
        return False
    receipt = read_json(dest / "receipt.json")
    if receipt["status"] != "passed":
        raise ValueError("Unaccepted replay")
    if expected_plan_sha256 is not None and receipt.get("plan_sha256") != expected_plan_sha256:
        raise ValueError("Replay belongs to another plan")
    if expected_job is not None:
        required = {ck + "/" + name for ck in ("best", "last")
                    for name in ("scores.json", "predictions.json", "audit.json")}
        required.add("metadata.json")
        if not required <= set(receipt["artifact_sha256"]):
            raise ValueError("Incomplete diagnostic receipt")
        if receipt.get("source_receipt_sha256") != expected_job["receipt_sha256"]:
            raise ValueError("Replay references another fit")
        if read_json(dest / "metadata.json")["job"] != expected_job:
            raise ValueError("Replay job identity differs")
    for name, value in receipt["artifact_sha256"].items():
        if file_sha(dest / name) != value:
            raise ValueError("Diagnostic artifact changed: " + name)
    return True
