"""One explicitly authorized fresh retry; preserve every previous attempt."""
from pathlib import Path
from .prepare import read, ref, checked

NAME = "runtime_resume_v2.json"
VERSION = "prompt8h-explicit-resume-v1"
PREFIX = "scripts/DFG/dfg_v2/benchmark_v2/"
CHANGED = {PREFIX + n for n in (
    "execution.py", "runtime_amendment.py", "reporting.py", "acceptance_cache.py")}
ADDED = {PREFIX + "retry.py"}


def successful_attempt(folder):
    folder = Path(folder)
    found = list(folder.glob("attempt_*/receipt.json"))
    if len(found) > 1:
        raise ValueError("Duplicate successful attempt")
    if not found:
        return None
    attempt = found[0].parent
    if any(p.name.split(".")[0] > attempt.name for p in folder.glob("attempt_*.started.json")):
        raise RuntimeError("A newer incomplete attempt follows success")
    return attempt


def next_attempt(plan_path, job, folder):
    """Return 001 normally, or exactly the approved 002 before it is started."""
    folder = Path(folder)
    starts = sorted(folder.glob("attempt_*.started.json"))
    if not starts:
        if (folder / "attempt_001").exists():
            raise RuntimeError("Untracked existing attempt; review required")
        return folder / "attempt_001"
    patch = Path(plan_path).parent / NAME
    if not patch.is_file():
        raise RuntimeError("Prior incomplete/failed fit: explicit user review required")
    doc = read(patch)
    if read(patch.with_name(patch.stem + ".seal.json")).get("amendment") != ref(patch):
        raise ValueError("Retry approval seal differs")
    approval = read(checked(doc["approval"]))
    if (approval.get("approved") is not True or approval.get("retry_job") != job
            or approval.get("plan") != ref(plan_path)
            or approval.get("retry_attempt") != "attempt_002"
            or approval.get("restart_from_sealed_initial") is not True
            or approval.get("automatic_retry") is not False):
        raise RuntimeError("Prior incomplete fit is not the authorized retry")
    if [p.name for p in starts] != ["attempt_001.started.json"]:
        raise RuntimeError("Authorized retry already started; no automatic retry")
    incident = read(checked(approval["interruption"]))
    if incident["job"] != job or Path(incident["old_attempt"]) != folder / "attempt_001":
        raise ValueError("Interrupted attempt identity differs")
    for entry in incident["files"]:
        checked(entry)
    target = folder / "attempt_002"
    if target.exists() or list(folder.glob("attempt_002.*")):
        raise RuntimeError("Authorized retry already has evidence; review required")
    return target


def verify_resume(plan_path, plan, actual, cache_validator):
    """Extend the prior sealed runtime, never rewrite it or its old proof."""
    path = Path(plan_path).parent / NAME
    doc = read(path)
    if read(path.with_name(path.stem + ".seal.json")).get("amendment") != ref(path):
        raise ValueError("Resume seal differs")
    if (doc.get("version") != VERSION or doc.get("plan") != ref(plan_path)
            or doc.get("plan_seal") != ref(Path(plan_path).with_name("plan.seal.json"))
            or doc.get("runtime") != actual):
        raise ValueError("Resume runtime/plan differs")
    parent = read(checked(doc["parent_amendment"]))
    if cache_validator(plan_path, plan, parent["runtime"]) != doc["parent_amendment"]:
        raise ValueError("Parent cache amendment differs")
    old = parent["runtime"]
    if ({n for n in old if actual.get(n) != old[n]} != CHANGED
            or set(actual) - set(old) != ADDED):
        raise ValueError("Resume cannot change numerical/unrelated source")
    if set(doc["before_sources"]) != CHANGED:
        raise ValueError("Resume source snapshots missing")
    for name, entry in doc["before_sources"].items():
        checked(entry)
        if entry["sha256"] != old[name]:
            raise ValueError("Resume original source differs")
    approval = read(checked(doc["approval"]))
    if (approval.get("approved") is not True or approval.get("plan") != ref(plan_path)
            or approval.get("reuse_successes") != 71 or approval.get("new_fits") != 99
            or approval.get("automatic_retry") is not False
            or approval.get("restart_from_sealed_initial") is not True):
        raise ValueError("Resume authorization differs")
    successes = read(checked(doc["prior_successes"]))
    if successes.get("passed") is not True or successes.get("count") != 71 or len(successes["receipts"]) != 71:
        raise ValueError("Resume prior successes differ")
    if len({r["path"] for r in successes["receipts"]}) != 71:
        raise ValueError("Duplicate prior success")
    for entry in successes["receipts"]:
        checked(entry)
    proof = read(checked(doc["proof"]))
    if (proof.get("passed") is not True or proof.get("runtime") != actual
            or proof.get("numeric_functions_unchanged") is not True):
        raise ValueError("Resume regression proof differs")
    checked(approval["interruption"])
    return ref(path)


def validate_retry_receipt(plan_path, job, attempt):
    attempt = Path(attempt)
    if attempt.name == "attempt_001":
        return
    if attempt.name != "attempt_002":
        raise ValueError("Unapproved attempt number")
    doc = read(Path(plan_path).parent / NAME)
    approval = read(checked(doc["approval"]))
    if approval.get("retry_job") != job or approval.get("retry_attempt") != attempt.name:
        raise ValueError("Retry receipt is not authorized for this job")
    incident = read(checked(approval["interruption"]))
    if Path(incident["old_attempt"]) != attempt.parent / "attempt_001":
        raise ValueError("Retry previous attempt differs")
    if (attempt.parent / "attempt_001/receipt.json").exists():
        raise ValueError("Cannot retry a successful attempt")
    for entry in incident["files"]:
        checked(entry)
