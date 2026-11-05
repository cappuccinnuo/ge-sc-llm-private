"""Read-only H1/G archive and reserved-initial verification. No initialization."""
import subprocess
from pathlib import Path
import torch
from scripts.DFG.experiments.common import read_json, sha256, digest, tensor_digest
from scripts.DFG.experiments.e23_cv import control as h1
from scripts.DFG.experiments.e23_pilot import control as g
from scripts.DFG.experiments.e23_pilot.inputs import ROOT, check_hashes, DEFAULT_OUTPUT as STAGE_G
from scripts.verify_h1_archive import verify as verify_h1
from . import H1

def load_initial(info, variant="E3a"):
    spec = info["initialization"][variant]
    check_hashes({spec["path"]: spec["sha256"],
                  info["initialization_audit_path"]: info["initialization_audit_sha256"]})
    record = torch.load(spec["path"], map_location="cpu")
    for key, value in (("kind", "untrained_initial"), ("optimizer_steps", 0),
                       ("variant", variant), ("task_id", info["task_id"])):
        if record.get(key) != value:
            raise ValueError("Initial identity mismatch: " + key)
    # Stage G records predate explicit fold metadata; their sealed manifest binds fold 0.
    if record.get("fold", 0) != info["fold"]:
        raise ValueError("Initial fold mismatch")
    if tensor_digest(record["state_dict"]) != spec["state_sha256"]:
        raise ValueError("Initial tensor digest mismatch")
    if record.get("state_sha256") != spec["state_sha256"]:
        raise ValueError("Initial stored tensor digest mismatch")
    if record.get("graph_sha256") != info["graphs"][variant]["sha256"]:
        raise ValueError("Initial graph mismatch")
    if record.get("initialization_audit_sha256") != info["initialization_audit_sha256"]:
        raise ValueError("Initial audit mismatch")
    audit = read_json(info["initialization_audit_path"])
    if ("initialization" in record and record["initialization"] != audit) or (info["fold"] != 0 and "initialization" not in record):
        raise ValueError("Embedded alignment audit mismatch")
    if not audit["state_def_use_E3a_E3b_equal"] or not all(
            x["equal"] for x in audit["common_parameters"].values()):
        raise ValueError("Shared initial parameters not aligned")
    if audit["state_sha256"] != {v: s["state_sha256"] for v, s in info["initialization"].items()}:
        raise ValueError("Triple state digest mismatch")
    if info["fit_seed"] != 1000000 + 10000 + info["fold"] + (1000 if info["task"] == "contract" else 0):
        raise ValueError("Frozen fit seed mismatch")
    return record

def add_receipt(files, path):
    path = Path(path); receipt = read_json(path)
    files[str(path)] = sha256(path)
    for name, value in receipt["artifact_sha256"].items():
        asset = (path.parent / name).resolve()
        if path.parent.resolve() not in asset.parents:
            raise ValueError("Receipt path escapes attempt")
        files[str(asset)] = value

def audit():
    counts = verify_h1(H1)  # H1-specific archive verification; not Stage G-only checker.
    plan = read_json(H1 / "plan.json"); reserved = read_json(H1 / "h2_plan.json")
    gp = read_json(STAGE_G / "plan.json")
    if sha256(STAGE_G / "plan.json") != read_json(STAGE_G / "plan.seal.json")["sha256"]:
        raise ValueError("Stage G seal drift")
    check_hashes(gp["runtime_code_sha256"]); check_hashes(gp["frozen_files"])
    files = dict(plan["frozen_files"])
    for name in ("plan.json", "plan.seal.json", "h2_plan.json", "h2_plan.seal.json",
                 "input_manifest.json", "fold0_reuse_audit.json", "H1_RESULT_REPORT.md",
                 "H2_EXECUTION_PLAN.md", "baseline_inventory.json", "baseline_hashes.json"):
        files[str(H1 / name)] = sha256(H1 / name)
    checks = []; reuse = []
    for job in reserved["jobs"]:
        check_hashes({job["task_manifest"]:job["task_manifest_sha256"]})
        info = read_json(job["task_manifest"])
        for key in ("task_id", "fold", "task", "cohort"):
            if info[key] != job[key]: raise ValueError("Manifest job identity mismatch")
        record = load_initial(info)
        checks.append({"task_id":job["task_id"], "fold":job["fold"], "variant":"E3a",
                       "initial":info["initialization"]["E3a"], "optimizer_steps":0,
                       "fit_seed":info["fit_seed"], "common_parameters":read_json(info["initialization_audit_path"])["common_parameters"],
                       "state_def_use_E3a_E3b_equal":True})
        del record
        if job["fold"] == 0:
            path = Path(job["stage_g_receipt"])
            check_hashes({str(path):job["stage_g_receipt_sha256"]})
            g.verify_fit(path.parent, job["stage_g_job"], "full", gp)
            add_receipt(files, path)
            reuse.append({"task_id":job["task_id"], "receipt":str(path), "sha256":sha256(path), "not_retrained":True})
    for job in plan["jobs"]:
        folder, _ = h1.locate(H1, job, plan)
        if folder is None: raise ValueError("Missing accepted H1 fit")
        add_receipt(files, folder / "receipt.json")
    check_hashes(files)
    return {"status":"passed", "h1_counts":counts, "reserved_authorization_unchanged":reserved["execution_authorized"],
            "h1_training_head":plan["base_git_head"],
            "current_head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip(),
            "historical_runtime_identical":True, "initial_checks":checks, "fold0_reuse":reuse}, files
