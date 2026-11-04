"""Read-only historical verification against recorded lists, not new code discovery."""
import argparse
import importlib
from pathlib import Path
from .io import checked, read_json, write_json, sha256

MODULES = ("overall_cv", "guard_extension", "readout_attention")


def verify_recorded_files(plan):
    merged = {}
    for group in ("runtime", "historical_runtime", "frozen"):
        mapping = plan.get(group, {})
        if not isinstance(mapping, dict) or (group in ("runtime", "frozen") and not mapping):
            raise ValueError("Missing historical hash mapping: " + group)
        for path, digest in mapping.items():
            if path in merged and merged[path] != digest:
                raise ValueError("Conflicting historical file identities")
            merged[path] = digest
    for path, digest in merged.items():
        checked(path, digest)
    return len(merged)


def verify(batch):
    batch = Path(batch).resolve()
    plan = read_json(batch / "plan.json")
    plan_sha = sha256(batch / "plan.json")
    if plan_sha != read_json(batch / "plan.seal.json")["sha256"]:
        raise ValueError("Historical plan seal mismatch")
    common = checks = None
    for name in MODULES:
        package = "scripts.DFG.experiments." + name
        candidate = importlib.import_module(package + ".common")
        if plan.get("version") == candidate.VERSION:
            common = candidate
            checks = importlib.import_module(package + ".checks")
            break
    if common is None or plan.get("pair_version") != common.PAIR_VERSION:
        raise ValueError("Unsupported historical plan; no generic bypass")
    if plan.get("jobs") != common.expected_jobs():
        raise ValueError("Historical matrix mismatch")
    refs = [(x["task_id"], x["fold"]) for x in plan["tasks"]]
    expected = {(j["task_id"], j["fold"]) for j in plan["jobs"]}
    if len(refs) != len(expected) or set(refs) != expected:
        raise ValueError("Historical task manifests incomplete/duplicated")
    count = verify_recorded_files(plan)
    receipts = []
    for job in plan["jobs"]:
        folder = checks.completed(batch, job, plan)
        if folder is None:
            raise ValueError("Incomplete historical fit: " + str(job))
        receipts.append(dict(job, receipt=str(folder/"receipt.json"),
                             receipt_sha256=sha256(folder/"receipt.json")))
    return {"batch":str(batch), "plan_sha256":plan_sha, "recorded_files_verified":count,
            "successful_fits":len(receipts), "receipts":receipts,
            "new_sidecars_permitted":True, "historical_recorded_files_must_match":True,
            "checkpoint_files_hashed_not_reloaded":True, "read_only":True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args();output=Path(args.output).resolve()
    if output.exists():raise FileExistsError("Refusing overwrite: "+str(output))
    batch=Path(args.batch).resolve()
    if output==batch or batch in output.parents:
        raise ValueError("Write archive audit outside the historical batch")
    result=verify(batch)
    output.parent.mkdir(parents=True,exist_ok=True)
    write_json(output,result)
    print("Verified {} historical fits; no historical file changed".format(result["successful_fits"]),flush=True)

if __name__=="__main__":main()
