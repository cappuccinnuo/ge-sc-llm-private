"""Exclusive Stage B runtime amendment, without changing the frozen plan.

Only the eight reviewed Prompt 8B.0 orchestration/validation files may differ.
This record proves code/input provenance; it never authorizes a training job.
Accepting it for historical Stage A verification does not permit new Stage A
fits. The caller must still enforce the stage execution approval.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from scripts.DFG.integration.io import read_json, sha256

VERSION = "prompt8b0-stage-B-amendment-v1"
PROOF_VERSION = "prompt8b0-exact-equivalence-v1"
SCOPE = "stage_B_orchestration_validation_only"
STAGE_A_POLICY = "historical_read_only_no_new_training"
EXPERIMENT = "scripts/DFG/dfg_v2/experiment/"
ALLOWED_RUNTIME_CHANGES = frozenset(EXPERIMENT + name for name in (
    "run.py", "batch.py", "checkpoint.py", "acceptance_cache.py",
    "input_guard.py", "amendment.py", "proof_performance.py", "reporting.py"))
REQUIRED_FROZEN_FILES = frozenset((
    EXPERIMENT + "trainer.py", EXPERIMENT + "init.py",
    EXPERIMENT + "protocol.py", EXPERIMENT + "support.py",
    "scripts/DFG/dfg_v2/model.py", "scripts/DFG/dfg_v2/hgt_layer.py",
    "scripts/DFG/dfg_v2/model_input.py", "scripts/DFG/dfg_v2/supervision.py"))
ROOT = Path(__file__).resolve().parents[4]
REPORTING_PATH = EXPERIMENT + "reporting.py"
REPORTING_REPLACEMENTS = (
    (b'def build_report(plan_path, stage="A", verified_results=None, output=None):',
     b'def build_report(plan_path, stage="A", verified_results=None, output=None, amendment_path=None):'),
    (b"    plan = run._load_plan(plan_path)",
     b"    plan = (run._load_plan(plan_path) if amendment_path is None else\n"
     b"            run._load_plan(plan_path, amendment_path=amendment_path))"),
)
PROOF_JOBS = ("access_control_node/0/1/G0", "access_control_node/0/1/G3R")
PROOF_CHECKS = frozenset(("history_losses", "epochs", "best_state", "last_state",
                          "inner_val_predictions", "outer_test_predictions"))


def _digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf8")
    return hashlib.sha256(raw).hexdigest()


def _runtime_refs():
    # Lazy import avoids a run -> amendment -> run initialization cycle.
    from .run import _code_refs
    return _code_refs()


def _ref(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha256(path)}


def _checked_ref(ref):
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
        raise ValueError("Missing amendment evidence reference")
    path = Path(ref["path"]).resolve()
    if not path.is_file() or sha256(path) != ref["sha256"]:
        raise ValueError("Amendment evidence SHA mismatch: " + str(path))
    return path


def _outside_batch(path, plan_path):
    try:
        Path(path).resolve().relative_to(Path(plan_path).resolve().parent)
    except ValueError:
        return
    raise ValueError("Amendment/proof must not write inside the frozen batch")


def seal_path(path):
    path = Path(path)
    return path.with_name(path.stem + ".seal.json")


def _load_frozen_plan(path, plan=None):
    path = Path(path).resolve()
    seal = read_json(path.with_name("plan.seal.json"))
    if seal.get("plan_sha256") != sha256(path):
        raise ValueError("Frozen plan seal SHA mismatch")
    document = read_json(path)
    if plan is not None and plan != document:
        raise ValueError("Caller plan differs from sealed plan")
    return document


def _valid_runtime(runtime):
    if not isinstance(runtime, dict) or not runtime:
        raise ValueError("Missing runtime hash inventory")
    for name, value in runtime.items():
        if not isinstance(name, str):
            raise ValueError("Invalid runtime path/SHA inventory")
        pure = PurePosixPath(name)
        if (pure.is_absolute() or ".." in pure.parts or str(pure) != name
                or not isinstance(value, str) or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)):
            raise ValueError("Invalid runtime path/SHA inventory")


def _reporting_interface_only(before, after):
    """Restore exactly two loader-interface edits and compare the entire file.

    The original hash comes from the sealed plan, so no Git checkout or history
    access is needed. Any extra edit, even outside the report calculation,
    changes the restored hash and is rejected.
    """
    old, new = before.get(REPORTING_PATH), after.get(REPORTING_PATH)
    if old == new:
        return None
    if old is None or new is None:
        raise ValueError("Reporting interface exception requires the original sealed file")
    source = (ROOT / REPORTING_PATH).read_bytes()
    if hashlib.sha256(source).hexdigest() != new:
        raise ValueError("Reporting source differs from current runtime inventory")
    restored = source
    for original, replacement in REPORTING_REPLACEMENTS:
        if restored.count(replacement) != 1:
            raise ValueError("Reporting may change only the two explicit amendment passthrough expressions")
        restored = restored.replace(replacement, original, 1)
    restored_sha = hashlib.sha256(restored).hexdigest()
    if restored_sha != old:
        raise ValueError("Reporting computation changed beyond amendment passthrough")
    return {"path": REPORTING_PATH, "old_sha256": old, "new_sha256": new,
            "restored_source_sha256": restored_sha,
            "allowed_replacements": 2, "statistics_bytes_unchanged": True}


def _changes(before, after):
    _valid_runtime(before)
    _valid_runtime(after)
    if not REQUIRED_FROZEN_FILES.issubset(before):
        raise ValueError("Plan lacks required frozen computation files")
    if not any(name.startswith("sco_models/") for name in before):
        raise ValueError("Plan lacks frozen sco_models computation inventory")
    if set(before) - set(after):
        raise ValueError("Runtime file deletion is forbidden")
    changes = []
    for name in sorted(after):
        old, new = before.get(name), after[name]
        if old != new:
            if name not in ALLOWED_RUNTIME_CHANGES:
                raise ValueError("Unapproved runtime computation drift: " + name)
            changes.append({"path": name, "old_sha256": old, "new_sha256": new,
                            "kind": "added" if old is None else "modified"})
    _reporting_interface_only(before, after)
    if not changes:
        raise ValueError("Stage B amendment requires explicit runtime changes")
    return changes


def _check_proof(path, plan_path, current_runtime):
    path = Path(path).resolve()
    _outside_batch(path, plan_path)
    record = read_json(path)
    if (record.get("version") != PROOF_VERSION or record.get("passed") is not True
            or record.get("plan") != _ref(plan_path)
            or record.get("runtime") != current_runtime):
        raise ValueError("Exact-equivalence proof is not bound/passed")
    jobs = record.get("jobs")
    if (not isinstance(jobs, list) or len(jobs) != len(PROOF_JOBS)
            or not all(isinstance(row, dict) for row in jobs)
            or sorted(row.get("job_id", "") for row in jobs) != sorted(PROOF_JOBS)):
        raise ValueError("Exact proof must cover both fixed access-control jobs")
    for row in jobs:
        checks = row.get("checks", {})
        if (row.get("passed") is not True or row.get("exact") is not True
                or row.get("comparison_reference") not in ("stage_A", "rerun_old")
                or not isinstance(checks, dict) or set(checks) != PROOF_CHECKS
                or any(value is not True for value in checks.values())):
            raise ValueError("Every frozen loss/state/prediction proof must be exact")
        refs = row.get("refs")
        if not isinstance(refs, dict) or not refs:
            raise ValueError("Exact-equivalence proof lacks evidence references")
        for ref in refs.values():
            _checked_ref(ref)
    return record


def _computation_identity(before, after):
    # Include every protected file, not just named neural-network modules.
    # This covers all sco_models files in the sealed original inventory too.
    frozen = {name: value for name, value in before.items()
              if name not in ALLOWED_RUNTIME_CHANGES}
    if any(after.get(name) != value for name, value in frozen.items()):
        raise ValueError("Frozen computation bytes changed")
    return {"byte_identical": True, "files": frozen,
            "inventory_sha256": _digest(frozen)}


def _exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def create_amendment(plan_path, output, proof_path, user_approval, reason):
    """Register validated proof and exact runtime delta; never authorize B."""
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    _outside_batch(output, plan_path)
    if output.exists() or seal_path(output).exists():
        raise FileExistsError("Refusing existing amendment or seal: " + str(output))
    if not isinstance(user_approval, str) or not user_approval.strip():
        raise ValueError("User approval verbatim is required")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Amendment reason is required")
    plan = _load_frozen_plan(plan_path)
    before, current = plan["runtime"], _runtime_refs()
    changes = _changes(before, current)
    _check_proof(proof_path, plan_path, current)
    record = {
        "version": VERSION, "stage": "B", "scope": SCOPE,
        "execution_authorized": False, "stage_A_policy": STAGE_A_POLICY,
        "plan": _ref(plan_path), "plan_seal": _ref(plan_path.with_name("plan.seal.json")),
        "runtime_before_sha256": _digest(before), "runtime_after_sha256": _digest(current),
        "changes": changes, "computation_byte_identity": _computation_identity(before, current),
        "reporting_interface_only": _reporting_interface_only(before, current),
        "equivalence_proof": _ref(proof_path), "proof_jobs": list(PROOF_JOBS),
        "reason": reason, "user_approval_verbatim": user_approval,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    # Check again after evidence hashing; a changing tree must not be sealed.
    if _runtime_refs() != current:
        raise ValueError("Runtime changed while registering Stage B amendment")
    _exclusive_json(output, record)
    _exclusive_json(seal_path(output), {"version": VERSION,
        "amendment_sha256": sha256(output), "plan_sha256": sha256(plan_path),
        "execution_authorized": False})
    return validate_amendment(output, plan_path, plan)


def validate_amendment(path, plan_path, plan=None, current_runtime=None):
    """Read-only full validation; caller must separately authorize stage/job."""
    path, plan_path = Path(path).resolve(), Path(plan_path).resolve()
    _outside_batch(path, plan_path)
    plan = _load_frozen_plan(plan_path, plan)
    seal = read_json(seal_path(path))
    if (seal.get("version") != VERSION or seal.get("amendment_sha256") != sha256(path)
            or seal.get("plan_sha256") != sha256(plan_path)
            or seal.get("execution_authorized") is not False):
        raise ValueError("Stage B amendment seal mismatch")
    record = read_json(path)
    if (record.get("version") != VERSION or record.get("stage") != "B"
            or record.get("scope") != SCOPE or record.get("execution_authorized") is not False
            or record.get("stage_A_policy") != STAGE_A_POLICY
            or record.get("plan") != _ref(plan_path)
            or record.get("plan_seal") != _ref(plan_path.with_name("plan.seal.json"))
            or record.get("proof_jobs") != list(PROOF_JOBS)
            or not isinstance(record.get("reason"), str) or not record["reason"].strip()
            or not isinstance(record.get("user_approval_verbatim"), str)
            or not record["user_approval_verbatim"].strip()
            or not isinstance(record.get("recorded_at"), str) or not record["recorded_at"].strip()):
        raise ValueError("Stage B amendment scope/provenance mismatch")
    before = plan["runtime"]
    current = _runtime_refs() if current_runtime is None else current_runtime
    changes = _changes(before, current)
    if (record.get("changes") != changes
            or record.get("runtime_before_sha256") != _digest(before)
            or record.get("runtime_after_sha256") != _digest(current)
            or record.get("computation_byte_identity") != _computation_identity(before, current)
            or record.get("reporting_interface_only") != _reporting_interface_only(before, current)):
        raise ValueError("Stage B amendment runtime inventory mismatch")
    proof_path = _checked_ref(record.get("equivalence_proof"))
    _check_proof(proof_path, plan_path, current)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--plan", required=True)
    create.add_argument("--output", required=True)
    create.add_argument("--proof", required=True)
    create.add_argument("--approval-file", required=True,
                        help="UTF-8 verbatim user request; registration only")
    create.add_argument("--reason-file", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--plan", required=True)
    verify.add_argument("--amendment", required=True)
    args = parser.parse_args(argv)
    if args.command == "create":
        result = create_amendment(args.plan, args.output, args.proof,
            Path(args.approval_file).read_text(encoding="utf8"),
            Path(args.reason_file).read_text(encoding="utf8"))
    else:
        result = validate_amendment(args.amendment, args.plan)
    print(json.dumps({"version": VERSION, "valid": True,
        "stage": result["stage"], "execution_authorized": result["execution_authorized"],
        "changed_files": len(result["changes"])}, sort_keys=True))


if __name__ == "__main__":
    main()
