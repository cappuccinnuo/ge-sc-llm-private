"""Fail-closed diagnostic preflight, before any model construction or loading.

Reads accepted artifacts and the diagnosis's byte snapshot. Does not deserialize
checkpoints, call formal verify, modify archived inputs, or finalize the audit.
"""
import hashlib
import json
from pathlib import Path
import subprocess


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _require(value, reason):
    if not value:
        raise ValueError("Diagnostic preflight: " + reason)


def _under(base, relative):
    base = Path(base).resolve()
    path = (base / relative).resolve()
    _require(path == base or base in path.parents, "archive path escapes accepted directory")
    return path


def _git_head(repo):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo),
                                   universal_newlines=True).strip()


def validate_static_summary(summary):
    """Four expected tasks must all complete; no partial static output qualifies."""
    expected = {
        "reentrancy_author_contract", "access_control_author_contract",
        "reentrancy_author_node", "access_control_author_node"}
    _require(summary.get("status") == "passed", "static analysis not passed")
    _require(summary.get("complete_tasks") == 4, "static analysis task count incomplete")
    tasks = summary.get("tasks")
    _require(isinstance(tasks, dict) and set(tasks) == expected, "static task identities mismatch")
    for key, value in tasks.items():
        _require(isinstance(value, dict) and bool(value),
                 "static task statistics missing: " + key)
    return {"tasks": sorted(expected), "complete_tasks": 4}


def validate_preflight(root, run):
    root, run = Path(root).resolve(), Path(run).resolve()
    audit = _read(root / "input_audit.json")
    _require(audit.get("status") == "passed", "archive input audit not passed")
    _require(audit.get("missing_or_changed_assets") == [], "archive asset mismatches present")
    _require(audit.get("post_archive_readonly_check", {}).get("unchanged") is True,
             "post-archive byte check not passed")
    _require(audit.get("archive_report", {}).get("returncode") == 0, "archive reporter failed")
    report = audit.get("archive_report_summary", {})
    _require(report.get("complete_tasks") == 4 and report.get("pending_tasks") == 0,
             "archive reporter not complete")
    _require(report.get("score_role") == "cv_validation", "unexpected archived scoring role")
    _require(audit.get("archive_descends_from_training_base") is True,
             "archive ancestry not verified")
    _require(audit.get("frozen_scan_excludes_diagnostic_directory") is True,
             "diagnostic code changes frozen scanner")
    _require(Path(audit["sealed_run"]).resolve() == run, "run differs from audited source")
    _require(Path(audit["diagnostic_directory"]).resolve() == root, "diagnostic root mismatch")
    before_path = root / "archive" / "before.json"
    _require(Path(audit["before_snapshot"]).resolve() == before_path, "before snapshot not local")
    before = _read(before_path)
    repo = Path(audit["repository"]).resolve()
    _require(_git_head(repo) == before["head"] == audit["archive_head"], "HEAD changed after archive audit")
    snapshot = before["snapshot"]
    _require(isinstance(snapshot, dict) and len(snapshot) > 0, "missing protected byte snapshot")
    checked = {}
    for name, record in snapshot.items():
        path = Path(name)
        _require(path.is_file() == record["exists"], "asset presence changed: " + name)
        if record["exists"]:
            _require(path.stat().st_size == record["size"], "asset size changed: " + name)
            actual = _sha(path)
            _require(actual == record["sha256"], "asset bytes changed: " + name)
            checked[str(path)] = actual
    def check_expected(path, expected):
        path = Path(path).resolve()
        _require(str(path) in checked, "asset absent from protected snapshot: " + str(path))
        _require(checked[str(path)] == expected, "binding digest mismatch: " + str(path))
    for filename in ("plan.json", "plan.seal.json", "state.json"):
        _require(str(run / filename) in checked, "unprotected archive control file: " + filename)
    plan, state = _read(run / "plan.json"), _read(run / "state.json")
    _require(plan["base_git_head"] == audit["sealed_training_base"], "sealed training base mismatch")
    _require(plan.get("protocol") == "paper_kfold" and plan.get("score_role") == "cv_validation",
             "unexpected frozen protocol")
    _require(state.get("stage_b") == "passed" and state.get("stage_c") == "passed",
             "formal archive incomplete")
    for path, expected in plan["runner_code_sha256"].items():
        check_expected(repo / path, expected)
    for path, expected in plan["frozen_files"].items():
        check_expected(path, expected)
    inventory = _read(root / "archive" / "asset_inventory.json")
    _require(inventory.get("accepted_pairs") == 30 and inventory.get("best_checkpoints") == 60
             and inventory.get("pilot_pairs") == 7, "asset inventory counts mismatch")
    job_ids = [job["id"] for job in plan["jobs"]]
    inventories = inventory["jobs"]
    _require(len(job_ids) == len(set(job_ids)) == 30, "expected 30 unique sealed jobs")
    _require(len(inventories) == 30 and {job["id"] for job in inventories} == set(job_ids),
             "asset inventory job identities mismatch")
    inventory_by_id = {item["id"]: item for item in inventories}
    best_count = 0
    for job in plan["jobs"]:
        identifier = job["id"]
        entry = state["jobs"][identifier]
        _require(entry.get("status") == "passed" and entry.get("exit_code") == 0,
                 "job unaccepted: " + identifier)
        attempt = _under(run, entry["attempt"])
        receipt_path = _under(run, entry["receipt"])
        check_expected(receipt_path, entry["receipt_sha256"])
        receipt = _read(receipt_path)
        _require(receipt["acceptance"].get("status") == "passed"
                 and receipt["acceptance"].get("job") == identifier,
                 "receipt job acceptance mismatch")
        for relative, expected in receipt["artifacts"].items():
            check_expected(_under(attempt, relative), expected)
        item = inventory_by_id[identifier]
        _require(Path(item["accepted_attempt"]).resolve() == attempt,
                 "inventory accepted attempt mismatch")
        _require(Path(item["receipt"]).resolve() == receipt_path, "inventory receipt mismatch")
        for key in ("cohort", "task", "fold", "prepared", "splits"):
            _require(item[key] == job[key], "inventory plan field mismatch: " + key)
        for variant in ("E0", "E1"):
            files = item["variants"][variant]
            for key, path in files["paths"].items():
                path = Path(path).resolve()
                _require(attempt in path.parents, "inventory model asset escapes accepted attempt")
                relative = str(path.relative_to(attempt))
                expected = receipt["artifacts"].get(relative)
                _require(expected is not None and files["hashes_from_receipt"].get(key) == expected,
                         "inventory receipt artifact digest mismatch: " + key)
                check_expected(path, expected)
            _require(all(k in files["paths"] for k in ("best.pt", "initial.pt", "last.pt",
                                                       "binding.json", "model_input.json",
                                                       "cv_validation_predictions.json")),
                     "required diagnostic checkpoint assets missing")
            best_count += 1
    static = validate_static_summary(_read(root / "static" / "summary.json"))
    invariants = _read(root / "static" / "input_invariants.json")
    _require(invariants.get("input_drift") == [], "static analysis observed original input drift")
    _require(invariants.get("graph_fingerprints_preserved") is True,
             "static analysis graph preservation not verified")
    _require(invariants.get("frozen_code_before") == plan["runner_code_sha256"]
             and invariants.get("frozen_code_after") == plan["runner_code_sha256"],
             "static analysis frozen code differs from sealed code")
    _require(isinstance(invariants.get("input_hashes"), dict) and bool(invariants["input_hashes"]),
             "static input hashes missing")
    for path, expected in invariants["input_hashes"].items():
        check_expected(path, expected)
    functions = _read(root / "static" / "edge_functions.json")
    _require(isinstance(functions.get("tasks"), dict)
             and set(functions["tasks"]) == set(static["tasks"]),
             "confirmed function metadata task identities mismatch")
    return {"status": "passed", "protected_files_checked": len(snapshot), "accepted_pairs": 30,
            "best_checkpoints": best_count, "static": static,
            "archive_head": before["head"], "sealed_training_base": plan["base_git_head"],
            "original_score_role": "cv_validation", "no_model_loaded": True,
            "original_run": str(run)}
