"""Prompt 7b.3 CPU release policy; raw numerical criteria remain frozen.

The two R/G3R trajectories are policy omissions with retained prior OOM
evidence, never successful trajectories. Only prescribed attempted cases may
be resource-skipped by the independently checked RSS guard.
"""
from pathlib import Path

from scripts.DFG.experiments.common import digest, read_json, sha256, write_json
from scripts.DFG.dfg_v2.tasks import checked_ref
from .projection_validation import CPU_CASES

SCHEMA = "prompt7b3-cpu-release-v1"
SKIP_SCHEMA = "prompt7b3-policy-skip-v1"
REUSED = ("reentrancy_contract", "G0", "mean")
POLICY_SKIPS = {
    ("reentrancy_contract", "G3R", "mean"): "policy_prior_oom",
    ("reentrancy_contract", "G3R", "nonempty_mean"): "policy_not_run",
}
GUARDED = {
    ("access_control_node", "G0", "mean"),
    ("access_control_node", "G3R", "mean"),
    ("reentrancy_contract", "G0", "nonempty_mean"),
}
COVERAGE = {
    ("access_control_node", "G3R", "mean"),
    ("reentrancy_contract", "G0", "nonempty_mean"),
}
SKIP_REASONS = {
    "policy_prior_oom": "Prompt 7b.3 excludes another R/G3R mean trajectory after the retained Prompt 7b.2 kernel OOM.",
    "policy_not_run": "Prompt 7b.3 excludes R/G3R nonempty_mean by CPU memory policy; this case was not attempted.",
}


def reference(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha256(path))


def _identity(row):
    return tuple(row.get(k) for k in ("task_id", "profile", "reducer"))


def policy_spec():
    return dict(
        schema=SCHEMA, static_cases=[list(c) for c in CPU_CASES],
        reused_trajectory=list(REUSED),
        policy_skips=[dict(case=list(c), kind=k) for c, k in sorted(POLICY_SKIPS.items())],
        guarded_trajectories=[list(c) for c in sorted(GUARDED)],
        at_least_one_completed=[list(c) for c in sorted(COVERAGE)],
        trajectory_loss_tolerance=1e-9, rss_limit_bytes=6979321856,
        actual_execution_or_numerical_failure_blocks=True,
    )


def policy_sources():
    root = Path(__file__).resolve().parents[4]
    return {name: sha256(root/name) for name in (
        "scripts/DFG/dfg_v2/experiment/precision_policy.py",
        "scripts/DFG/dfg_v2/experiment/precision_guard.py",
        "scripts/DFG/dfg_v2/experiment/precision_gpu.py",
    )}


def _new_output(path):
    path = Path(path).resolve()
    if "prompt7b3_v1" not in [p.name for p in path.parents]:
        raise ValueError("New CPU policy artifacts must live under prompt7b3_v1")
    if path.exists():
        raise FileExistsError(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def validate_frozen_static(static):
    """Check metadata against archived preparation without loading a model."""
    from .precision_real import validate_static_evidence, _source_identity
    from .precision_gpu import CASE_FIELDS
    validate_static_evidence(static)
    if static.get("sources") != _source_identity():
        raise ValueError("Frozen CPU computation sources changed")
    for field in ("graph", "initial", "labels_ref", "folds", "archived_plan"):
        checked_ref(static[field])
    plan_path = Path(checked_ref(static["archived_plan"]))
    seal = read_json(plan_path.with_name("plan.seal.json"))
    if seal.get("plan_sha256") != static["archived_plan"]["sha256"]:
        raise ValueError("Archived plan seal mismatch")
    plan = read_json(plan_path)
    task = plan["tasks"][static["task_id"]]
    prepared = read_json(checked_ref(task["prepared"]["0/1"]))
    entry = prepared["profiles"][static["profile"]]
    record = task["record"]
    expected = dict(task_id=static["task_id"], task=record["task"],
        profile=static["profile"], reducer=static["reducer"], fold=0, seed=1,
        device="cpu", dtype="float64", graph=entry["graph"], initial=entry["initial"],
        labels_ref=record["labels"], folds=record["folds"],
        archived_plan=reference(plan_path), config=task["config"],
        seeds=prepared["seeds"], split_sha256=digest(prepared["split"]))
    if any(static.get(k) != expected[k] for k in CASE_FIELDS):
        raise ValueError("CPU static identity differs from frozen preparation")
    return static


def _same_case(static, evidence):
    from .precision_gpu import CASE_FIELDS
    if any(static.get(k) != evidence.get(k) for k in CASE_FIELDS):
        raise ValueError("Trajectory evidence frozen input/case mismatch")
    if evidence.get("sources") != static["sources"]:
        raise ValueError("Trajectory evidence computation sources differ")


def _validate_reused(static, static_ref, evidence_ref):
    from .precision_real import validate_trajectory_evidence
    evidence = read_json(checked_ref(evidence_ref))
    _same_case(static, evidence)
    if evidence.get("static") != static_ref:
        raise ValueError("Trajectory references a different static case")
    validate_trajectory_evidence(evidence)
    return "passed"


def _validate_prior_oom(failure_ref, commands_ref, static):
    """Retain failure as failure; verify the external terminal receipt."""
    failure = read_json(checked_ref(failure_ref))
    if (failure.get("status") != "stopped_resource_error"
            or failure.get("case") != "reentrancy_contract_G3R_mean"
            or failure.get("returncode") != -9
            or failure.get("signal") != "SIGKILL"
            or failure.get("kernel_oom_confirmed") is not True):
        raise ValueError("Missing retained prior R/G3R kernel OOM evidence")
    partial = read_json(checked_ref(failure["partial_report"]))
    from .precision_gpu import CASE_FIELDS
    for key in CASE_FIELDS:
        if key != "reducer" and partial.get(key) != static.get(key):
            raise ValueError("Prior OOM frozen input differs")
    if (partial.get("reducer") != "mean" or partial.get("status") != "running"
            or partial.get("sources") != static["sources"]):
        raise ValueError("Prior OOM partial trajectory identity differs")
    state = read_json(checked_ref(failure["coordinator_state"]))
    if (state.get("stage") != "trajectory" or state.get("case") != failure["case"]
            or state.get("returncode") != -9):
        raise ValueError("Prior OOM coordinator evidence differs")
    kernel = Path(checked_ref(failure["kernel_evidence"])).read_text()
    if not failure.get("kernel_line") or failure["kernel_line"] not in kernel:
        raise ValueError("Kernel OOM log does not contain retained evidence")
    commands = read_json(checked_ref(commands_ref))
    matching = []
    for command in commands:
        if not isinstance(command, list):
            raise ValueError("Malformed prior command list")
        def option(name):
            return command[command.index(name)+1] if name in command and command.index(name)+1 < len(command) else None
        if (option("--task"), option("--profile"), option("--reducer")) == ("reentrancy_contract", "G3R", "mean"):
            matching.append(command)
            if (option("--plan") != static["archived_plan"]["path"]
                    or option("--static-report") != partial["static"]["path"]
                    or Path(option("--output") or "")/"trajectory.json" != Path(failure["partial_report"]["path"])
                    or "scripts.DFG.dfg_v2.experiment.precision_real" not in command
                    or "trajectory" not in command):
                raise ValueError("Prior OOM command differs from retained case")
    if len(matching) != 1:
        raise ValueError("Missing/duplicate prior OOM command")
    return failure


def validate_policy_skip(receipt, static, static_ref):
    identity = _identity(static)
    kind = POLICY_SKIPS.get(identity)
    if (receipt.get("schema") != SKIP_SCHEMA or kind is None
            or receipt.get("status") != "skipped_cpu_memory"
            or receipt.get("skip_kind") != kind
            or receipt.get("reason") != SKIP_REASONS[kind]
            or receipt.get("executed_this_batch") is not False
            or receipt.get("argv", "missing") is not None
            or receipt.get("samples") != []
            or receipt.get("static") != static_ref
            or receipt.get("policy") != policy_spec()
            or receipt.get("policy_sources") != policy_sources()):
        raise ValueError("Invalid or unprescribed CPU memory policy skip")
    _same_case(static, receipt)
    _validate_prior_oom(receipt["prior_failure"], receipt["prior_commands"], static)
    return "skipped_cpu_memory"


def write_policy_skip(path, static_path, prior_failure_path, prior_commands_path):
    path = _new_output(path)
    static_ref = reference(static_path)
    static = validate_frozen_static(read_json(checked_ref(static_ref)))
    identity = _identity(static)
    if identity not in POLICY_SKIPS:
        raise ValueError("This case cannot be skipped by policy")
    from .precision_gpu import CASE_FIELDS
    kind = POLICY_SKIPS[identity]
    receipt = {k: static[k] for k in CASE_FIELDS}
    receipt.update(schema=SKIP_SCHEMA, status="skipped_cpu_memory",
        skip_kind=kind, reason=SKIP_REASONS[kind], executed_this_batch=False,
        argv=None, samples=[], static=static_ref, sources=static["sources"],
        policy=policy_spec(), policy_sources=policy_sources(),
        prior_failure=reference(prior_failure_path),
        prior_commands=reference(prior_commands_path))
    validate_policy_skip(receipt, static, static_ref)
    write_json(path, receipt)
    return reference(path)


def _validate_guard(static, static_ref, receipt_ref):
    from .precision_guard import validate_guard_evidence
    receipt = validate_guard_evidence(checked_ref(receipt_ref))
    if (tuple(receipt.get("case", {}).get(k) for k in ("task_id", "profile", "reducer"))
            != _identity(static)):
        raise ValueError("Guard case differs from CPU release row")
    # Guard validates raw samples, command, current source and numerical output.
    if receipt.get("refs", {}).get("static_report") != static_ref or receipt.get("refs", {}).get("plan") != static["archived_plan"]:
        raise ValueError("Guard inputs differ from static evidence")
    status = receipt.get("status")
    if status == "passed":
        _validate_reused(static, static_ref, receipt["trajectory"])
    elif status != "skipped_cpu_memory":
        raise ValueError("Actual CPU failure blocks GPU release")
    return status


def validate_document(report):
    if (report.get("schema") != SCHEMA or report.get("status") != "accepted"
            or report.get("policy") != policy_spec()
            or report.get("policy_sources") != policy_sources()
            or not isinstance(report.get("cases"), list)):
        raise ValueError("CPU release policy identity/status differs")
    rows = report["cases"]
    identities = [_identity(row) for row in rows]
    if len(rows) != 6 or len(set(identities)) != 6 or set(identities) != set(CPU_CASES):
        raise ValueError("CPU policy requires all six distinct cases")
    completed, plans = set(), []
    for row, identity in zip(rows, identities):
        static_ref = row["static"]
        static = validate_frozen_static(read_json(checked_ref(static_ref)))
        if _identity(static) != identity:
            raise ValueError("Static case differs from CPU release row")
        plans.append(static["archived_plan"])
        evidence = row.get("trajectory_evidence")
        if not isinstance(evidence, dict) or set(evidence) != {"kind", "ref"}:
            raise ValueError("Missing explicit trajectory or skipped record")
        if identity == REUSED:
            if evidence["kind"] != "reused_trajectory":
                raise ValueError("R/G0 mean must retain its completed trajectory")
            status = _validate_reused(static, static_ref, evidence["ref"])
        elif identity in POLICY_SKIPS:
            if evidence["kind"] != "policy_skip":
                raise ValueError("R/G3R requires its explicit policy skip")
            status = validate_policy_skip(read_json(checked_ref(evidence["ref"])), static, static_ref)
        elif identity in GUARDED:
            if evidence["kind"] != "rss_guard":
                raise ValueError("Prescribed trajectory requires RSS guard evidence")
            status = _validate_guard(static, static_ref, evidence["ref"])
        else:
            raise ValueError("Unprescribed CPU case")
        if status == "passed":
            completed.add(identity)
    if any(plan != plans[0] for plan in plans) or report.get("archived_plan") != plans[0]:
        raise ValueError("CPU release does not share one frozen archived plan")
    if not completed.intersection(COVERAGE):
        raise ValueError("No completed G3R or nonempty_mean trajectory coverage")
    return report


def build_acceptance(path, rows):
    path = _new_output(path)
    if path.name != "acceptance.json":
        raise ValueError("Expected acceptance.json")
    seal_path = path.with_name("acceptance.seal.json")
    if seal_path.exists():
        raise FileExistsError(str(seal_path))
    first = read_json(checked_ref(rows[0]["static"]))
    report = dict(schema=SCHEMA, status="accepted", policy=policy_spec(),
        policy_sources=policy_sources(), archived_plan=first["archived_plan"], cases=rows)
    validate_document(report)
    write_json(path, report)
    write_json(seal_path, dict(schema=SCHEMA, acceptance_sha256=sha256(path),
        policy_sha256=digest(policy_spec()), policy_sources=policy_sources()))
    return report


def validate_release(path):
    path = Path(path).resolve()
    seal = read_json(path.with_name("acceptance.seal.json"))
    if (seal.get("schema") != SCHEMA or seal.get("acceptance_sha256") != sha256(path)
            or seal.get("policy_sha256") != digest(policy_spec())
            or seal.get("policy_sources") != policy_sources()):
        raise ValueError("CPU release seal/policy source mismatch")
    report = validate_document(read_json(path))
    if seal["acceptance_sha256"] != sha256(path):
        raise ValueError("CPU release changed during verification")
    return report
