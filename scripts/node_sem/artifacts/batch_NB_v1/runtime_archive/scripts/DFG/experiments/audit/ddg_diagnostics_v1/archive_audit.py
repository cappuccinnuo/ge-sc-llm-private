"""Read-only accepted archive inventory and byte-drift guard for DDG diagnosis.

No formal verify, migration, checkpoint deserialization, training, or model loading.
The new diagnosis directory is intentionally outside the frozen code scan.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid

REPO = Path("/home/zhao/SmartContract/ge-sc-llm")
HERE = Path(__file__).resolve().parent
RUN = REPO / "scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c"
FINAL = REPO / "scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/reports/final_v1"
TRAINING_HEAD = "646e9b3495c0fe7f2c4a6e4b72d0bab64d6ee2fc"
ARCHIVE_HEAD = "3fb3fbcaed34c5c97976b570aac484935aa81484"
PILOTS = {
    "reentrancy_author_contract_fold0", "access_control_author_contract_fold0",
    "reentrancy_author_node_fold0", "access_control_author_node_fold0",
    "reentrancy_author_node_fold8", "access_control_author_node_fold7",
    "access_control_author_node_fold8",
}

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write_new(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as out:
        json.dump(obj, out, ensure_ascii=True, indent=2, sort_keys=True)
        out.write("\n")

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def file_record(path):
    p = Path(path)
    return {"exists": p.is_file(), "size": p.stat().st_size if p.is_file() else None,
            "sha256": sha256(p) if p.is_file() else None}

def collect_snapshot(paths):
    return {str(Path(p).absolute()): file_record(p) for p in sorted(set(map(str, paths)))}

def compare_snapshot(before):
    changes = []
    for path, value in before.items():
        actual = file_record(path)
        if actual != value:
            changes.append({"path": path, "before": value, "after": actual})
    return {"checked": len(before), "unchanged": not changes, "changes": changes}

def checked_relative(base, item):
    base = Path(base).resolve()
    path = (base / item).resolve()
    if path != base and base not in path.parents:
        raise ValueError("Archive path escapes its declared root: " + str(item))
    return path

def command(argv, cwd=REPO):
    started = time.perf_counter()
    proc = subprocess.run(argv, cwd=str(cwd), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True)
    return {"command": argv, "returncode": proc.returncode, "stdout": proc.stdout,
            "stderr": proc.stderr, "elapsed_seconds": time.perf_counter() - started}

def manifest_assets(value, base, label="", found=None):
    found = {} if found is None else found
    if isinstance(value, dict):
        if "path" in value and "sha256" in value and isinstance(value["path"], str):
            path = Path(value["path"])
            path = path if path.is_absolute() else Path(base) / path
            found[str(path.absolute())] = {"expected_sha256": value["sha256"], "source": label}
        for key, child in value.items():
            if key == "asset_hashes" and isinstance(child, dict):
                for path, expected in child.items():
                    found[str(Path(path).absolute())] = {
                        "expected_sha256": expected, "source": label + ".asset_hashes"}
            else:
                manifest_assets(child, base, label + "." + key, found)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            manifest_assets(child, base, label + "[{}]".format(index), found)
    return found

def inventory():
    plan, state = read_json(RUN / "plan.json"), read_json(RUN / "state.json")
    if plan["base_git_head"] != TRAINING_HEAD:
        raise ValueError("Unexpected sealed training base")
    if state.get("stage_c") != "passed":
        raise ValueError("Stage C has not been accepted")
    result, assets, expected = [], {}, {}
    for name, expected_hash in plan["runner_code_sha256"].items():
        expected[str(REPO / name)] = expected_hash
    expected.update(plan["frozen_files"])
    for job in plan["jobs"]:
        entry = state["jobs"][job["id"]]
        if entry["status"] != "passed":
            raise ValueError("Unaccepted job: " + job["id"])
        attempt = checked_relative(RUN, entry["attempt"])
        receipt_path = checked_relative(RUN, entry["receipt"])
        if sha256(receipt_path) != entry["receipt_sha256"]:
            raise ValueError("Receipt hash mismatch: " + job["id"])
        receipt = read_json(receipt_path)
        if receipt["acceptance"]["job"] != job["id"] or receipt["acceptance"]["status"] != "passed":
            raise ValueError("Receipt identity mismatch: " + job["id"])
        for rel, expected_hash in receipt["artifacts"].items():
            expected[str(checked_relative(attempt, rel))] = expected_hash
        prepared = Path(job["prepared"])
        manifest = read_json(prepared / "manifest.json")
        manifest_assets(manifest, prepared, job["cohort"] + ".manifest", assets)
        fold_dir = attempt / ("fold_" + str(job["fold"]))
        variants = {}
        for variant in ("E0", "E1"):
            vd = fold_dir / variant
            needed = ["best.pt", "best.json", "binding.json", "model_input.json",
                      "cv_validation_predictions.json", "result.json", "telemetry.json",
                      "gradient_audit.json", "train_supervision.json", "val_supervision.json",
                      "history.jsonl"]
            paths = {n: str(vd / n) for n in needed}
            paths["initial.pt"] = str(fold_dir / (variant + "_initial.pt"))
            paths["last.pt"] = str(vd / "last.pt")
            variants[variant] = {
                "paths": paths,
                "hashes_from_receipt": {key: receipt["artifacts"].get(str(Path(value).relative_to(attempt)))
                                       for key, value in paths.items()},
                "registered_schema_sha256": read_json(vd / "binding.json")["registered_schema"]["sha256"],
            }
        result.append(dict(job, accepted_attempt=str(attempt), receipt=str(receipt_path),
                           effective_config=str(attempt / "effective_config.json"),
                           fold_dir=str(fold_dir), variants=variants, pilot=job["id"] in PILOTS,
                           prepared_manifest=str(prepared / "manifest.json"),
                           graph_labels=str(prepared / "graph_labels.json")))
    for path, spec in assets.items():
        if path in expected and expected[path] != spec["expected_sha256"]:
            raise ValueError("Conflicting frozen expectations: " + path)
        expected[path] = spec["expected_sha256"]
    return (plan, {"jobs": result, "manifest_assets": assets,
                  "accepted_pairs": len(result), "best_checkpoints": len(result) * 2,
                  "pilot_pairs": sum(int(j["pilot"]) for j in result),
                  "asset_discovery": "sealed plan -> accepted state attempt -> receipt; prepared manifest sources"},
            expected)

def gather_paths(expected):
    tracked = command(["git", "ls-files", "-z"])
    if tracked["returncode"]:
        raise RuntimeError(tracked["stderr"])
    paths = {str(REPO / p) for p in tracked["stdout"].split("\0") if p}
    paths.update(expected)
    # Preserve existing untracked executable project sources, too.
    for dirname in ("sco_models", "process_graphs", "scripts", "tests"):
        for p in (REPO / dirname).rglob("*"):
            if p.is_file() and p.suffix in (".py", ".sh", ".js", ".toml", ".yaml", ".yml"):
                if HERE != p and HERE not in p.parents and "__pycache__" not in p.parts:
                    paths.add(str(p))
    for folder in (RUN, RUN.with_name("formal_20261012_v1"), FINAL):
        for p in folder.rglob("*"):
            if p.is_file():
                paths.add(str(p))
    return sorted(p for p in paths if Path(p) != HERE and HERE not in Path(p).parents)

def get_environment():
    # Import installed libraries; never construct a model, optimizer or graph.
    import torch
    import dgl
    import numpy
    import networkx
    import sklearn
    versions = dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                    torch=torch.__version__, dgl=dgl.__version__, numpy=numpy.__version__,
                    networkx=networkx.__version__, sklearn=sklearn.__version__,
                    cuda_build=torch.version.cuda, cuda_available=torch.cuda.is_available())
    versions["nvidia_smi"] = command([
        "nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,memory.free,utilization.gpu",
        "--format=csv,noheader,nounits"])
    versions["no_model_loaded"] = True
    versions["timestamp_utc"] = utc()
    return versions

def begin_audit():
    target = HERE / "input_audit.json"
    if target.exists():
        raise ValueError("Diagnostic audit already exists; refusing overwrite")
    archive = HERE / "archive"
    archive.mkdir(exist_ok=True)
    head = command(["git", "rev-parse", "HEAD"])
    ancestry = command(["git", "merge-base", "--is-ancestor", TRAINING_HEAD, "HEAD"])
    if head["stdout"].strip() != ARCHIVE_HEAD or ancestry["returncode"] != 0:
        raise ValueError("Archive provenance unexpected; stop without changing repository")
    plan, assets, expected = inventory()
    snapshot = collect_snapshot(gather_paths(expected))
    mismatches = [{"path": p, "expected_sha256": e, "actual": snapshot.get(p)}
                  for p, e in expected.items()
                  if not snapshot.get(p, {}).get("exists") or snapshot[p]["sha256"] != e]
    before = {"timestamp_utc": utc(), "head": head["stdout"].strip(),
              "git_status": command(["git", "status", "--porcelain=v1"])["stdout"],
              "snapshot": snapshot}
    write_new(archive / "before.json", before)
    write_new(archive / "asset_inventory.json", assets)
    write_new(HERE / "environment.json", get_environment())
    output = "/tmp/ge-sc-llm-ddg-diagnostic-archive-check-" + uuid.uuid4().hex[:12]
    cmd = [sys.executable, "-B",
           str(REPO / "scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/report_stage_c.py"),
           "--run", str(RUN), "--output", output]
    run_report = command(cmd) if not mismatches else {
        "command": cmd, "returncode": None, "stdout": "", "stderr": "Skipped: frozen asset mismatch"}
    with (HERE / "archive_check.log").open("x", encoding="utf-8") as out:
        out.write(run_report["stdout"] + run_report["stderr"])
    summary = {}
    if run_report["returncode"] == 0:
        summary = json.loads(run_report["stdout"].strip().splitlines()[-1])
    write_new(archive / "reporter_command.json", run_report)
    write_new(archive / "reporter_summary.json", summary)
    digest_check = compare_snapshot(snapshot)
    audit = {
        "schema": "ddg-diagnostic-input-audit-v1", "created_utc": utc(), "modified_by": "Codex",
        "repository": str(REPO), "diagnostic_directory": str(HERE), "sealed_run": str(RUN),
        "archive_head": head["stdout"].strip(), "sealed_training_base": plan["base_git_head"],
        "archive_descends_from_training_base": ancestry["returncode"] == 0,
        "frozen_scan_excludes_diagnostic_directory": True,
        "frozen_scan_rule": "common.code_hashes: experiments/*.py, DFG/*.py and 3 explicit paths only",
        "tracked_and_existing_code_and_sealed_asset_files": len(snapshot),
        "runner_code_files": len(plan["runner_code_sha256"]), "plan_frozen_files": len(plan["frozen_files"]),
        "expected_asset_hashes": len(expected), "missing_or_changed_assets": mismatches,
        "asset_inventory": str(archive / "asset_inventory.json"),
        "before_snapshot": str(archive / "before.json"),
        "archive_report": run_report, "archive_report_summary": summary,
        "post_archive_readonly_check": digest_check,
        "accepted_pairs": assets["accepted_pairs"], "best_checkpoints": assets["best_checkpoints"],
        "pilot_pairs": assets["pilot_pairs"], "final_drift_check": "pending",
        "status": "passed" if not mismatches and digest_check["unchanged"]
                  and summary.get("complete_tasks") == 4 and summary.get("pending_tasks") == 0 else "blocked",
        "limits": ["No checkpoint torch.load or model forward in this asset audit",
                   "Git archive alone does not include all .pt/prepared assets",
                   "Environment reports available installed runtime; no dependency changes",
                   "Final drift verification must run after all diagnostics"],
    }
    write_new(target, audit)
    print(json.dumps({k: audit[k] for k in (
        "status", "accepted_pairs", "best_checkpoints", "pilot_pairs",
        "runner_code_files", "plan_frozen_files", "expected_asset_hashes",
        "tracked_and_existing_code_and_sealed_asset_files")}))
    return audit

def finalize_audit():
    audit = read_json(HERE / "input_audit.json")
    if audit["final_drift_check"] != "pending":
        raise ValueError("Final audit already recorded; no overwrite")
    before = read_json(audit["before_snapshot"])
    result = compare_snapshot(before["snapshot"])
    result["timestamp_utc"] = utc()
    result["head_unchanged"] = command(["git", "rev-parse", "HEAD"])["stdout"].strip() == before["head"]
    current_paths = gather_paths({})
    result["unexpected_new_protected_files"] = sorted(set(current_paths) - set(before["snapshot"]))
    result["diagnostic_code_hashes"] = {
        str(p.relative_to(HERE)): sha256(p) for p in HERE.rglob("*.py")
        if "__pycache__" not in p.parts}
    result["passed"] = result["unchanged"] and result["head_unchanged"] and not result["unexpected_new_protected_files"]
    write_new(HERE / "archive" / "final_drift.json", result)
    audit["final_drift_check"] = result
    audit["status"] = "passed" if audit["status"] == "passed" and result["passed"] else "blocked"
    # This is the new diagnostic audit only; no archived files are written.
    (HERE / "input_audit.json").write_text(json.dumps(audit, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.finalize:
        print(json.dumps(finalize_audit()))
    else:
        begin_audit()
