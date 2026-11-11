"""Read-only EP3 comparison, deliberately outside production construction."""
import argparse
import json
from pathlib import Path
from .common import ROOT, ref, read, checked, write
from .ep4_common import OUT, TASKS
from scripts.edge_sem.build_f4 import load_edges

F4 = ROOT / "scripts/edge_sem/artifacts/f4_v1"


def load_ep3_manifest(task):
    if task not in TASKS:
        raise ValueError("Only recorded EP3 node tasks may be archived")
    before = read(OUT/"before.json")
    verification = read(checked(before["historical_verification"]))
    if not verification["passed"]:
        raise ValueError("EP3 verification failed")
    summary = read(checked(verification["summary"]))
    checked(verification["report"])
    snapshots = {r["original"]["path"]:r["snapshot"]
                 for r in before["authorized_source_changes"]}
    for record in summary["source_refs"]:
        replacement = snapshots.get(record["path"], record)
        if replacement["sha256"] != record["sha256"]:
            raise ValueError("Archived EP3 source identity differs")
        checked(replacement)
    for record in summary["evidence_refs"]:
        checked(record)
    manifest = read(checked(summary["tasks"][task]["manifest"]))
    if manifest["task_id"] != task or manifest["version"] != "edgesem-f4-ep3-v1":
        raise ValueError("Historical EP3 identity differs")
    for record in manifest["implementation"]:
        replacement = snapshots.get(record["path"], record)
        if replacement["sha256"] != record["sha256"]:
            raise ValueError("Archived EP3 implementation identity differs")
        checked(replacement)
    for record in list(manifest["source_refs"].values()) + list(manifest["inputs"]["graphs"].values()):
        checked(record)
    for name in ("plan", "store", "audit"):
        checked(manifest["inputs"][name])
    checked(manifest["audit"])
    checked(manifest["edges"])
    return manifest


def compare_edge_files(old, new):
    a, b = ref(old), ref(new)
    if a["sha256"] != b["sha256"] or Path(old).read_bytes() != Path(new).read_bytes():
        raise ValueError("F4 rebuild differs byte-for-byte from EP3")
    return dict(old=a, new=b, byte_identical=True)


def verify_task(task):
    new_path = F4/task/"manifest.json"
    rows = load_edges(new_path)
    new = read(new_path)
    audit = read(checked(new["audit"]))
    result = dict(task_id=task, manifest=ref(new_path), edges=len(rows),
                  counts_by_relation=new["counts_by_relation"],
                  counts=audit["counts"], statuses=audit["statuses"],
                  guards={k:audit["guards"][k] for k in
                          ("counts","kind_records","kind_mapped","nonmodifier_mapping_pass")})
    if task in TASKS:
        old = load_ep3_manifest(task)
        result["ep3"] = compare_edge_files(checked(old["edges"]), checked(new["edges"]))
        original = read(checked(old["audit"]))
        for field in ("counts","kind_records","kind_mapped"):
            if original["guards"][field] != audit["guards"][field]:
                raise ValueError("Rebuilt guard census differs from EP3: "+field)
        result["ep3_guard_census_equal"] = True
    else:
        reference = ROOT/"scripts/edge_sem/artifacts/ep0_v1"/(task+".json")
        census = read(reference)
        expected = sum(sum(v["records"] for v in f["guards"].values())
                       for f in census["files"])
        result["contract_descriptive_only"] = True
        result["ep0_reference"] = ref(reference)
        result["ep0_guard_records"] = expected
        result["guard_record_delta"] = audit["guards"]["counts"]["records"]-expected
        result["ep0_modifier_bindings"] = sum(f["modifiers"].get("unique_definition",0) for f in census["files"])
        result["ep0_modifier_endpoints"] = sum(f["modifiers"].get("both_endpoints",0) for f in census["files"])
    write(OUT/"rebuild"/(task+".json"), result)
    print(task, result["counts_by_relation"], "rebuild verified", flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    verify_task(parser.parse_args().task)
