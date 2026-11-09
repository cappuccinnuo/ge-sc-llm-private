"""Read-only S4 result reuse; deleted best/last are disclosed, never claimed reloadable."""
from pathlib import Path
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref, write
from . import batch_na as na
from .batch_na_worker import job_id
from .nb_finalize import verify_historical_exports


def audit(root, destination):
    root = Path(root)
    source = read(root / "plan.json")
    na.validate_envelope(source, read(root / "plan.seal.json"), ref(root / "plan.json"))
    for name, reference in source["runtime_archive"].items():
        checked(reference)
        if reference["sha256"] != source["runtime"][name]:
            raise ValueError("Historical archived source differs")
    complete = read(root / "complete.json")
    revision = read(root / "execution_revision.json")
    if (not complete.get("passed") or complete.get("formal_fits") != 240
            or complete["plan"] != ref(root / "plan.json")
            or complete["execution_revision"] != ref(root / "execution_revision.json")
            or revision["plan"] != complete["plan"] or revision["seal"] != ref(root / "plan.seal.json")):
        raise ValueError("N-A completion or revision differs")
    expected = {job_id(j): j for j in source["jobs"]}
    seen, rows = set(), []
    for reference in complete["receipts"]:
        r = read(checked(reference)); j = r["job"]; key = job_id(j)
        if key in seen or j != expected.get(key) or r["plan"] != complete["plan"]:
            raise ValueError("Historical receipt identity differs")
        seen.add(key)
        if j["name"] != "S4" or j["profile"] != "G3R":
            continue
        if r["execution_revision"] != complete["execution_revision"] or r["actual_device"] != j["device_policy"]:
            raise ValueError("Historical device or revision differs")
        availability = verify_historical_exports(r)
        directory = Path(reference["path"]).parent
        if read(directory / "complete.json")["receipt"] != reference:
            raise ValueError("Historical completion receipt differs")
        rows.append(dict(job=j, receipt=reference, availability=availability,
            actual_device=r["actual_device"], total_seconds=r["total_seconds"], resources=r["resources"]))
    if seen != set(expected) or len(rows) != 30:
        raise ValueError("Missing historical matrix or S4 results")
    parent = {k: ref(root / f) for k, f in (
        ("plan", "plan.json"), ("seal", "plan.seal.json"),
        ("complete", "complete.json"), ("revision", "execution_revision.json"))}
    value = dict(passed=True, parent=parent, records=rows, selected_results=30,
        metric_reuse_only=True, missing_checkpoints=sum(len(r["availability"]["missing_checkpoints"]) for r in rows),
        no_historical_files_changed=True)
    write(destination, value)
    return source, value


def verify_index(reference):
    index = read(checked(reference))
    for r in index["parent"].values(): checked(r)
    source = read(checked(index["parent"]["plan"]))
    na.validate_envelope(source, read(checked(index["parent"]["seal"])), index["parent"]["plan"])
    expected = {job_id(j): j for j in source["jobs"] if j["name"] == "S4" and j["profile"] == "G3R"}
    if not index.get("passed") or index.get("selected_results") != 30 or len(index["records"]) != 30:
        raise ValueError("Historical S4 index incomplete")
    rows = {}
    for row in index["records"]:
        r = read(checked(row["receipt"])); j = row["job"]; key = job_id(j)
        if key in rows or j != expected.get(key) or r["job"] != j:
            raise ValueError("Historical S4 index identity differs")
        if r["plan"] != index["parent"]["plan"] or r["execution_revision"] != index["parent"]["revision"]:
            raise ValueError("Historical S4 provenance differs")
        if row["actual_device"] != j["device_policy"] or r["actual_device"] != row["actual_device"]:
            raise ValueError("Historical S4 device/TF32 differs")
        verify_historical_exports(r)
        rows[key] = row
    if set(rows) != set(expected): raise ValueError("Historical S4 fold missing")
    return rows
