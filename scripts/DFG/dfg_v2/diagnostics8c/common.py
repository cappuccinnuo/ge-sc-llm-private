"""Read-only identities and artifact verification for Prompt 8C."""
import argparse
from contextlib import contextmanager
from unittest.mock import patch
import json
from pathlib import Path
from scripts.DFG.integration.io import sha256

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")

def checked_plan(path):
    path = Path(path).resolve()
    seal = read(path.with_name("plan.seal.json"))
    if seal.get("plan_sha256") != sha256(path):
        raise ValueError("Frozen plan seal mismatch")
    return read(path)


def attempt_for(plan_path, job):
    from scripts.DFG.dfg_v2.experiment.run import _job_directory
    directory = _job_directory(Path(plan_path).parent, job)
    receipts = sorted(directory.glob("attempt_*/receipt.json"))
    if len(receipts) != 1:
        raise ValueError("Expected exactly one successful receipt: " + str(directory))
    return receipts[0].parent

def row_identity(row):
    return (row["file"], row.get("original_graph_node_id"))

def indexed(rows):
    result = {}
    for row in rows:
        identity = row_identity(row)
        if identity in result:
            raise ValueError("Duplicate prediction identity: " + repr(identity))
        result[identity] = row
    return result

@contextmanager
def historical_runtime(plan_path, plan):
    """Bind archive verification to recorded runtime, checking every live byte.

    Added diagnostic modules are outside the historical inventory. The frozen
    validator still validates the original seal/proof/authorization; only its
    inventory provider is scoped to the byte-verified historical file set.
    This context must never be used to authorize training.
    """
    from scripts.DFG.dfg_v2.experiment import amendment
    runtime = dict(plan["runtime"])
    refs = {}
    for job in plan["jobs"]:
        a = attempt_for(plan_path, job)
        start = read(a.with_suffix(".started.json"))
        ref = start.get("runtime_amendment")
        if ref:
            if sha256(ref["path"]) != ref["sha256"]:
                raise ValueError("Historical amendment changed")
            refs[ref["path"]] = ref
    if len(refs) != 1:
        raise ValueError("Expected the single frozen stage B amendment")
    amendment_path = next(iter(refs))
    record = read(amendment_path)
    for change in record["changes"]:
        if runtime.get(change["path"]) != change["old_sha256"]:
            raise ValueError("Historical amendment predecessor mismatch")
        runtime[change["path"]] = change["new_sha256"]
    for name, expected in runtime.items():
        if sha256(amendment.ROOT / name) != expected:
            raise ValueError("Historical computation bytes changed: " + name)
    amendment.validate_amendment(amendment_path, plan_path, plan, current_runtime=runtime)
    with patch.object(amendment, "_runtime_refs", return_value=runtime):
        yield dict(runtime=runtime, amendment=refs[amendment_path],
                   extra_diagnostic_files_excluded=True, execution_authorized=False)


def verify_all(plan_path, output):
    """Reuse frozen receipt verifier; no model forward/optimizer is called."""
    from scripts.DFG.dfg_v2.experiment.run import _verify_attempt, job_id
    plan_path = Path(plan_path).resolve()
    plan = checked_plan(plan_path)
    output = Path(output)
    output.mkdir(exist_ok=False, parents=True)
    identities = [job_id(j) for j in plan["jobs"]]
    if len(identities) != 150 or len(set(identities)) != 150:
        raise ValueError("Expected complete frozen 150-fit matrix")
    records = []
    for i, job in enumerate(plan["jobs"]):
        attempt = attempt_for(plan_path, job)
        with historical_runtime(plan_path, plan):
            result = _verify_attempt(attempt, plan, job, plan_path)
        receipt = read(attempt / "receipt.json")
        record = dict(job=job, attempt=str(attempt),
                      receipt_sha256=sha256(attempt / "receipt.json"),
                      artifacts=receipt["artifacts"],
                      outer_test=result["outer_test"], status="verified")
        records.append(record)
        write_new(output / ("fit_%03d.json" % i), record)
        print("verified %d/150 %s" % (i + 1, job_id(job)), flush=True)
    report = dict(plan_path=str(plan_path), plan_sha256=sha256(plan_path),
                  verified=len(records), model_forward_count=0,
                  training_count=0, fits=records)
    write_new(output / "verification.json", report)
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    verify_all(args.plan, args.out)
