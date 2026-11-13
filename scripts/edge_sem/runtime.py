"""Explicit EP7 training source set; diagnostics/tests are excluded."""
from pathlib import Path
from .io import ROOT,ref,checked,read,write
from scripts.DFG.dfg_v2.experiment.run import _code_refs

MODULES=(
 "__init__.py","materialize.py","init.py","model.py","model_relations.py",
 "model_attrs.py","hgt_edge.py","forward.py","placebo.py","attrs.py","attr_sources.py",
 "attr_batch.py","attr_stats.py","build_f4.py","call_resolve.py","guard_edges.py","guard_source.py",
 "io.py","support.py","checkpoint.py","input_guard.py","supervision.py","trainer.py",
 "execution.py","runtime.py","protocol_p2.py","pilot.py","feature_views.py",
 "analysis_ea.py","recon/ep8_run.py",
 "analysis_eb.py","recon/ep9_run.py",
)

def runtime_refs():
    result=dict(_code_refs())
    for name in MODULES:
        path=ROOT/"scripts/edge_sem"/name
        result[str(path.relative_to(ROOT))]=ref(path)["sha256"]
    return result

def snapshot_runtime(folder):
    versions=runtime_refs();snapshots={}
    for name,sha in versions.items():
        if not name.startswith("scripts/edge_sem/"):continue
        dest=Path(folder)/(name.replace("/","__")+".txt")
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open("xb") as f:f.write((ROOT/name).read_bytes())
        snapshots[name]=ref(dest)
        if snapshots[name]["sha256"]!=sha:raise ValueError("Runtime changed during snapshot")
    return versions,snapshots

def verify_snapshot(plan,execute):
    if execute and plan["runtime"]!=runtime_refs():raise ValueError("Sealed runtime changed")
    expected={n:v for n,v in plan["runtime"].items() if n.startswith("scripts/edge_sem/")}
    if set(expected)!=set(plan["runtime_snapshots"]):raise ValueError("Missing EdgeSem runtime snapshot")
    for name,row in plan["runtime_snapshots"].items():
        checked(row)
        if row["sha256"]!=expected[name]:raise ValueError("Archived runtime source differs")


REVISION_VERSION = "edgesem-ep9-sampling-recovery-v1"
SAMPLING_RETRY_POLICY = dict(version="bounded-whole-card-query-v1", max_attempts=3,
    per_query_timeout_seconds=5, backoff_seconds=[0.5, 1.0],
    retry_exceptions=["TimeoutExpired", "CalledProcessError"],
    stale_samples_allowed=False, automatic_fit_retry=False)
REVISION_FILES = {
    "scripts/edge_sem/execution.py",
    "scripts/edge_sem/runtime.py",
    "scripts/edge_sem/recon/ep9_run.py",
}


def verify_execution_revision(path, plan, revision, execute=False):
    """Explicit EP9-only overlay; old plans, snapshots and approvals stay intact."""
    path, revision = Path(path), Path(revision)
    data = read(revision)
    if read(revision.with_suffix(".seal.json")).get("revision") != ref(revision):
        raise ValueError("Execution revision seal differs")
    if (data.get("version") != REVISION_VERSION or plan.get("experiment_stage") != "E-B"
            or data.get("plans", {}).get(plan.get("analysis_role")) != ref(path)
            or data.get("old_runtime") != plan["runtime"]
            or data.get("sampling_policy") != SAMPLING_RETRY_POLICY):
        raise ValueError("Execution revision identity/policy differs")
    request_path = checked(data["request"])
    request = read(request_path)
    if read(request_path.with_suffix(".seal.json")).get("request") != ref(request_path):
        raise ValueError("Recovery user request seal differs")
    if (request.get("execution_authorized") is not True or not request.get("user_request")
            or request.get("prior_plans") != data["plans"]
            or request.get("automatic_fit_retry") is not False
            or request.get("restart_failed_job_from_sealed_initial") is not True
            or request.get("old_runtime") != data["old_runtime"]):
        raise PermissionError("Explicit EP9 recovery approval required")
    for name in ("failure", "pipeline_failure"):
        checked(request[name])
    verify_snapshot(plan, False)
    changed = {name for name in set(data["runtime"]) | set(plan["runtime"])
               if data["runtime"].get(name) != plan["runtime"].get(name)}
    if changed != REVISION_FILES or set(data.get("changed_files", [])) != changed:
        raise ValueError("Recovery changed an unapproved runtime module")
    verify_snapshot(dict(runtime=data["runtime"], runtime_snapshots=data["runtime_snapshots"]), execute)
    tests_path = checked(data["tests"])
    tests = read(tests_path)
    if read(tests_path.with_suffix(".seal.json")).get("results") != ref(tests_path):
        raise ValueError("Recovery regression seal differs")
    expected = {"scripts/edge_sem/tests", "scripts/node_sem/tests", "scripts/DFG/dfg_v2/tests"}
    if (tests.get("runtime") != data["runtime"]
            or {r["suite"] for r in tests["results"]} != expected
            or len(tests["results"]) != 3
            or any(r["returncode"] != 0 for r in tests["results"])):
        raise ValueError("Recovery regression acceptance differs")
    for result in tests["results"]:
        checked(result["log"])
    reused_path = checked(data["verified_successes"])
    reused = read(reused_path)
    if read(reused_path.with_suffix(".seal.json")).get("verification") != ref(reused_path):
        raise ValueError("Recovery successes verification seal differs")
    if (reused.get("passed") is not True or reused.get("receipts") != request["completed_receipts"]):
        raise ValueError("Recovered success population differs")
    for item in reused["receipts"]:
        checked(item)
    return data
