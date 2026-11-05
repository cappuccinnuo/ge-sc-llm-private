"""Read-only N-A receipt audit for N-B. No historical file is written."""
from pathlib import Path
import time
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from . import batch_na as na
from . import batch_na_worker as worker


def audit(root, destination):
    root, destination = Path(root), Path(destination)
    plan = na.load(root / "plan.json", deep=False)
    complete = read(root / "complete.json")
    revision = read(root / "execution_revision.json")
    if (not complete.get("passed") or complete.get("formal_fits") != 240
            or complete["plan"] != ref(root / "plan.json")
            or complete["execution_revision"] != ref(root / "execution_revision.json")
            or revision["plan"] != ref(root / "plan.json")
            or revision["seal"] != ref(root / "plan.seal.json")):
        raise ValueError("Incomplete or wrongly bound N-A batch")
    bykey = {na.key(j): j for j in plan["jobs"]}
    rows, seen_keys = [], set()
    for reference in complete["receipts"]:
        receipt = read(checked(reference))
        k = na.key(receipt["job"])
        if k in seen_keys or k not in bykey:
            raise ValueError("Duplicate/unexpected N-A receipt")
        seen_keys.add(k)
        if receipt["job"] != bykey[k]:
            raise ValueError("N-A receipt job differs")
        worker.verify_attempt(root, plan, bykey[k], Path(reference["path"]).parent, deep=True)
        rows.append(dict(job=bykey[k], receipt=reference,
            complete=ref(Path(reference["path"]).parent / "complete.json"),
            actual_device=receipt["actual_device"], total_seconds=receipt["total_seconds"],
            resources=receipt["resources"]))
        if len(rows) % 30 == 0:
            print("N-A readonly receipts verified %d/240" % len(rows), flush=True)
    if seen_keys != set(bykey):
        raise ValueError("Missing N-A receipts")
    na.validate_device_comparisons(plan["jobs"],
        [dict(x["job"], actual_device=x["actual_device"]) for x in rows])
    report_receipt = read(root / "reports/receipt.json")
    if report_receipt["plan"] != ref(root / "plan.json"):
        raise ValueError("Historical report plan differs")
    for item in report_receipt["artifacts"]:
        checked(item)
    parent = dict(plan=ref(root / "plan.json"), seal=ref(root / "plan.seal.json"),
        complete=ref(root / "complete.json"), revision=ref(root / "execution_revision.json"),
        report_receipt=ref(root / "reports/receipt.json"))
    value = dict(passed=True, formal_fits=240, parent=parent, records=rows,
        all_receipt_artifacts_checked=True, historical_runtime_checked="sealed and archived; no current HEAD equality",
        training_fits=0, audited_unix=time.time())
    write(destination, value)
    return plan, parent, ref(destination)


def verify_parent_index(parent, index_ref, jobs, seen=None):
    na.checked_tree(parent, seen)
    source = read(checked(parent["plan"]))
    na.validate_envelope(source, read(checked(parent["seal"])), parent["plan"])
    index = read(checked(index_ref))
    complete = read(checked(parent["complete"]))
    if (index.get("passed") is not True or index.get("formal_fits") != 240
            or index.get("parent") != parent or not index.get("all_receipt_artifacts_checked")
            or complete.get("formal_fits") != 240 or not complete.get("passed")
            or complete["plan"] != parent["plan"] or complete["execution_revision"] != parent["revision"]):
        raise ValueError("Historical verification binding differs")
    expected = {na.key(j): j for j in source["jobs"]}
    rows = index["records"]
    if (len(rows) != 240 or len({na.key(x["job"]) for x in rows}) != 240
            or {na.key(x["job"]) for x in rows} != set(expected)
            or {x["receipt"]["sha256"] for x in rows} != {x["sha256"] for x in complete["receipts"]}):
        raise ValueError("Historical result matrix differs")
    bytask = {}
    for row in rows:
        receipt = read(checked(row["receipt"]))
        j = expected[na.key(row["job"])]
        if (row["job"] != j or receipt["job"] != j or receipt["plan"] != parent["plan"]
                or receipt["execution_revision"] != parent["revision"]
                or row["actual_device"] != j["device_policy"]
                or receipt["actual_device"] != row["actual_device"]):
            raise ValueError("Historical receipt identity/device differs")
        bytask[(j["task_id"], j["fold"], j["profile"])] = j
    for j in jobs:
        old = bytask[(j["task_id"], j["fold"], j["profile"])]
        for k in ("config","split","graph","labels","folds","label_view","seeds",
                  "source_preparation","h8_initial","device_policy"):
            if j[k] != old[k]:
                raise ValueError("N-B/N-A comparison input or precision differs: " + k)
    return True
