"""Fresh Prompt 8 plan registration; historical pilot authorization stays read-only.

This module prepares new initial states through the existing runner. It never
fits a model, reads pilot F1, or grants permission to execute a stage.
"""
import copy
import shutil
import time
from pathlib import Path

from scripts.DFG.integration.io import checked, read_json, sha256
from ..inputs import load_manifest
from ..tasks import checked_ref
from .preflight import LOCAL_DEV_POLICY
from .protocol import load_folds
from .init import INITIALIZATION_VERSION

VERSION = "dfg-v2-batch1-v1"
ORIGIN_VERSION = "prompt8-fresh-batch-resource-v1"
AUTHORIZATION_VERSION = "prompt8-batch-authorization-v1"
REPORT_VERSION = "prompt8-report-spec-v1"
DEFAULT_TASKS = ("reentrancy_contract", "reentrancy_node",
                 "access_control_contract", "access_control_node")
PROFILES = ("G0", "G1R", "G2R", "G3R", "G3")
STAGE_PROFILES = {"A": ("G0", "G3R"), "B": ("G1R", "G2R", "G3")}
PRIMARY_ENDPOINT = {
    "contrast": ["G3R", "G0"], "checkpoint": "best", "role": "outer_test",
    "metric": "buggy_f1", "aggregation": "equal folds within each task",
    "node_tasks": "paired two-sided Wilcoxon with zsplit",
    "contract_tasks": "descriptive only; five folds",
    "independent_new_graph_test": False,
}


def _ref(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha256(path)}


def _job_id(job):
    return "{task_id}/{fold}/{seed}/{profile}".format(**job)


def _stages(jobs):
    return {stage: {"profiles": list(profiles),
                    "jobs": [_job_id(j) for j in jobs if j["profile"] in profiles],
                    "execution_authorized": False,
                    "requires_separate_user_confirmation": True}
            for stage, profiles in STAGE_PROFILES.items()}


def _matrix(task_order, records, profiles=PROFILES):
    jobs = []
    for task_id in task_order:
        count = 5 if records[task_id]["task"] == "contract" else 10
        jobs.extend({"task_id": task_id, "fold": fold, "seed": 1,
                     "profile": profile, "layer_impl": "shared_projection"}
                    for fold in range(count) for profile in profiles)
    return jobs


def _load_authorization(path, store_ref, approval_ref, task_ids):
    record = read_json(path)
    if (record.get("version") != AUTHORIZATION_VERSION
            or record.get("approved") is not True
            or record.get("policy") != "local_dev_v1"
            or record.get("authorized_scope") != "prepare_batch1_150_only"
            or record.get("execution_authorized") is not False
            or record.get("store") != store_ref
            or record.get("historical_policy_approval") != approval_ref
            or record.get("task_ids") != list(task_ids)
            or record.get("profiles") != list(PROFILES)
            or record.get("seeds") != [1]
            or not isinstance(record.get("user_answer"), str)
            or not record["user_answer"].strip()
            or not isinstance(record.get("recorded_at"), str)
            or not record["recorded_at"].strip()):
        raise ValueError("Fresh batch requires its own preparation-only authorization")
    pilot_ref = record.get("pilot_plan", {})
    pilot_path = checked_ref(pilot_ref)
    pilot = read_json(pilot_path)
    seal_path = pilot_path.with_name("plan.seal.json")
    seal = read_json(seal_path)
    if (seal.get("plan_sha256") != pilot_ref["sha256"]
            or pilot.get("resource_policy") != LOCAL_DEV_POLICY
            or pilot.get("resource_origin", {}).get("version") != "prompt7c-local-resource-plan-v1"
            or pilot["resource_origin"].get("approval") != approval_ref
            or len(pilot.get("jobs", [])) != 8
            or pilot.get("store") != store_ref):
        raise ValueError("Historical local-policy pilot binding differs")
    approval = read_json(checked_ref(approval_ref))
    expected = sorted(_job_id(j) for j in pilot["jobs"])
    if (approval.get("version") != "prompt7c-local-dev-approval-v1"
            or approval.get("approved") is not True
            or approval.get("policy") != "local_dev_v1"
            or approval.get("source_plan") != pilot["resource_origin"].get("plan")
            or sorted(approval.get("authorized_jobs", [])) != expected):
        raise ValueError("Historical eight-job approval is not the frozen pilot approval")
    return record, pilot, _ref(seal_path)


def _pilot_sizes(pilot, pilot_ref):
    """Use receipt-bound file sizes only, never pilot predictions or metrics."""
    from . import run
    root = Path(pilot_ref["path"]).parent
    rows = []
    for job in pilot["jobs"]:
        matches = sorted(run._job_directory(root, job).glob("attempt_*/receipt.json"))
        if len(matches) != 1:
            raise ValueError("Disk estimate requires one completed pilot receipt per job")
        receipt_path = matches[0]
        receipt = read_json(receipt_path)
        if (receipt.get("status") != "complete" or receipt.get("job") != job
                or receipt.get("plan_sha256") != pilot_ref["sha256"]):
            raise ValueError("Pilot size evidence receipt binding differs")
        checkpoints = {}
        for name in ("best.pt", "last.pt"):
            path = checked(receipt_path.parent / name, receipt["artifacts"][name])
            checkpoints[name] = dict(path=str(path.resolve()), sha256=receipt["artifacts"][name],
                                     bytes=path.stat().st_size)
        _, _, entry = run._prepared(pilot, job)
        initial_path = checked_ref(entry["initial"])
        rows.append({"job": copy.deepcopy(job), "receipt": _ref(receipt_path),
                     "checkpoints": checkpoints,
                     "initial": dict(_ref(initial_path), bytes=initial_path.stat().st_size)})
    return rows


def estimate_storage(size_rows, jobs):
    """Conservative per-task observed maximum for all five profile sizes."""
    estimates, checkpoint_total, initial_total = {}, 0, 0
    for task_id in dict.fromkeys(j["task_id"] for j in jobs):
        measured = [row for row in size_rows if row["job"]["task_id"] == task_id]
        if {row["job"]["profile"] for row in measured} != {"G0", "G3R"}:
            raise ValueError("Need both G0 and G3R pilot sizes for every task")
        pair = max(sum(r["checkpoints"][name]["bytes"] for name in ("best.pt", "last.pt"))
                   for r in measured)
        initial = max(r["initial"]["bytes"] for r in measured)
        if pair <= 0 or initial <= 0:
            raise ValueError("Checkpoint/initial byte sizes must be positive")
        fits = sum(j["task_id"] == task_id for j in jobs)
        estimates[task_id] = {"fits": fits, "max_checkpoint_pair_bytes": pair,
                             "max_initial_bytes": initial,
                             "checkpoint_bytes": pair * fits, "initial_bytes": initial * fits}
        checkpoint_total += pair * fits
        initial_total += initial * fits
    total = checkpoint_total + initial_total
    return {"method": "per-task maximum measured G0/G3R best+last and initial sizes",
            "tasks": estimates, "estimated_checkpoint_bytes": checkpoint_total,
            "estimated_initial_bytes": initial_total, "estimated_total_bytes": total,
            "required_free_bytes": 2 * total, "headroom_multiplier": 2,
            "headroom_use": "JSON, predictions, logs and transient writes; failed retries not budgeted"}


def _nearest_existing(path):
    path = Path(path).resolve()
    while not path.exists():
        path = path.parent
    return path


def _available_memory():
    result = {"source": "/proc/meminfo", "available_bytes": None}
    path = Path("/proc/meminfo")
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.startswith("MemAvailable:"):
                result["available_bytes"] = int(line.split()[1]) * 1024
    return result


def _storage_evidence(size_rows, jobs, output):
    estimate = estimate_storage(size_rows, jobs)
    volume = _nearest_existing(Path(output).parent)
    usage = shutil.disk_usage(str(volume))
    if usage.free < estimate["required_free_bytes"]:
        raise ValueError("Insufficient disk: need twice estimated checkpoints plus fresh initial states")
    memory = _available_memory()
    memory.update(five_model_serialized_initial_upper_bound_bytes=max(
        v["max_initial_bytes"] for v in estimate["tasks"].values()) * len(PROFILES),
        interpretation="Serialized weights only; graph storage, cloned tensors and allocator overhead "
                       "are additional. No unsupported CPU memory multiplier or automatic model change.")
    return dict(estimate, checked_unix=time.time(), filesystem_path=str(volume),
                available_bytes_at_preparation=usage.free, total_bytes=usage.total,
                cpu_preparation_observation=memory)


def _check_report(ref, plan):
    from . import stats, reporting
    spec = read_json(checked_ref(ref))
    if spec.get("version") != REPORT_VERSION or spec.get("statistics") != stats.specification():
        raise ValueError("Reporting/statistics preregistration differs")
    reporting.validate_reporting_metadata(spec, plan)
    return spec


def attach_registration(plan, registration):
    """Called exactly once before create_plan writes any output or initial."""
    if (plan.get("test_mode") or registration.get("version") != VERSION
            or plan.get("reducer") != "mean" or plan.get("layer_impl") != "shared_projection"):
        raise ValueError("Invalid production batch registration")
    plan["resource_policy"] = copy.deepcopy(LOCAL_DEV_POLICY)
    plan["resource_origin"] = {"version": ORIGIN_VERSION,
        "historical_policy_approval": copy.deepcopy(registration["historical_policy_approval"]),
        "authorization": copy.deepcopy(registration["authorization"]),
        "pilot_plan": copy.deepcopy(registration["pilot_plan"])}
    plan["batch_registration"] = copy.deepcopy(registration)


def create_batch_plan(store, output, tasks=None, profiles=None, seeds=(1,), folds=None,
                      reducer="mean", layer_impl="shared_projection",
                      approval_record=None, authorization_record=None, report_spec=None):
    from . import run
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing experiment directory: " + str(output))
    if approval_record is None or authorization_record is None or report_spec is None:
        raise ValueError("Local policy without independent batch records requires --from-plan; "
                         "fresh batch requires approval, authorization and report specification")
    store_ref = _ref(store)
    document = read_json(checked_ref(store_ref))
    task_ids = run._select(tasks, document["tasks"], DEFAULT_TASKS, "tasks")
    selected_profiles = run._select(profiles, PROFILES, PROFILES, "profiles")
    selected_seeds = [int(x) for x in seeds.split(",")] if isinstance(seeds, str) else list(seeds)
    if (set(task_ids) != set(DEFAULT_TASKS) or selected_profiles != list(PROFILES)
            or selected_seeds != [1] or folds is not None or reducer != "mean"
            or layer_impl != "shared_projection"):
        raise ValueError("Batch 1 freezes four tasks, all folds, five profiles, seed 1 and shared mean")
    inputs = load_manifest(checked_ref(document["input_manifest"]), check_files=True)
    records = {task: inputs["tasks"][task] for task in task_ids}
    for task, record in records.items():
        frozen = load_folds(record)
        if frozen["k_folds"] != (5 if record["task"] == "contract" else 10):
            raise ValueError("Frozen 5/10-fold protocol differs")
    approval_ref = _ref(approval_record)
    auth_ref = _ref(authorization_record)
    authorization, pilot, pilot_seal = _load_authorization(
        checked_ref(auth_ref), store_ref, approval_ref, task_ids)
    jobs = _matrix(task_ids, records)
    if len(jobs) != 150:
        raise ValueError("Batch 1 must contain exactly 150 fresh fits")
    sizes = _pilot_sizes(pilot, authorization["pilot_plan"])
    storage = _storage_evidence(sizes, jobs, output)
    registration = {
        "version": VERSION, "task_order": task_ids, "profiles": list(PROFILES),
        "jobs": [_job_id(j) for j in jobs], "stages": _stages(jobs),
        "job_order": "task, fold, seed, profile (filtered by stage)",
        "primary_endpoint": copy.deepcopy(PRIMARY_ENDPOINT),
        "selection_rule": copy.deepcopy(run.SELECTION_RULE),
        "authorization": auth_ref, "historical_policy_approval": approval_ref,
        "pilot_plan": authorization["pilot_plan"], "pilot_seal": pilot_seal,
        "pilot_results_reused": False, "fresh_initial_states": True,
        "initialization_algorithm_changed": False,
        "execution_authorized": False, "report_spec": _ref(report_spec),
        "pilot_size_evidence": sizes, "storage_preflight": storage,
        "execution_rules": {"separate_process_per_job": True, "serial_single_gpu": True,
            "stop_after_stage_A_interim": True, "stop_after_stage_B_report": True,
            "automatic_retry": False, "retry_same_untrained_initial": True},
    }
    # Reject malformed analysis metadata before constructing any model.
    _check_report(registration["report_spec"],
                  {"tasks": {t: {"record": records[t]} for t in task_ids}})
    return run.create_plan(store, output, task_ids, selected_profiles, selected_seeds,
        None, reducer, layer_impl=layer_impl, _batch_registration=registration)


def validate_batch_plan(plan, plan_path):
    """Validate the fresh registration without relaxing historical plan checks."""
    from . import run
    reg = plan.get("batch_registration", {})
    if (reg.get("version") != VERSION or plan.get("test_mode")
            or plan.get("resource_policy") != LOCAL_DEV_POLICY
            or plan.get("reducer") != "mean" or plan.get("layer_impl") != "shared_projection"
            or plan.get("profiles") != list(PROFILES) or plan.get("seeds") != [1]
            or plan.get("requested_folds") is not None
            or plan.get("initialization_version") != INITIALIZATION_VERSION):
        raise ValueError("Fresh batch protocol/resource/profile registration differs")
    task_ids = reg.get("task_order", [])
    if set(task_ids) != set(DEFAULT_TASKS) or len(task_ids) != len(DEFAULT_TASKS):
        raise ValueError("Batch task order/matrix differs")
    authorization, pilot, pilot_seal = _load_authorization(
        checked_ref(reg["authorization"]), plan["store"], reg["historical_policy_approval"], task_ids)
    origin = {"version": ORIGIN_VERSION,
              "historical_policy_approval": reg["historical_policy_approval"],
              "authorization": reg["authorization"], "pilot_plan": authorization["pilot_plan"]}
    if (plan.get("resource_origin") != origin or reg.get("pilot_plan") != authorization["pilot_plan"]
            or reg.get("pilot_seal") != pilot_seal):
        raise ValueError("Fresh origin does not match independent preparation authorization")
    if set(plan["tasks"]) != set(task_ids):
        raise ValueError("Batch task population differs")
    records = {t: plan["tasks"][t]["record"] for t in task_ids}
    jobs = _matrix(task_ids, records)
    if (len(jobs) != 150 or plan["jobs"] != jobs or reg.get("jobs") != [_job_id(j) for j in jobs]
            or reg.get("stages") != _stages(jobs)
            or reg.get("profiles") != list(PROFILES)
            or reg.get("primary_endpoint") != PRIMARY_ENDPOINT
            or plan.get("selection_rule") != run.SELECTION_RULE
            or reg.get("selection_rule") != run.SELECTION_RULE
            or reg.get("execution_authorized") is not False
            or reg.get("pilot_results_reused") is not False
            or reg.get("fresh_initial_states") is not True
            or reg.get("initialization_algorithm_changed") is not False):
        raise ValueError("Preregistered matrix/stages/endpoints/selection differs")
    if reg.get("execution_rules") != {
            "separate_process_per_job": True, "serial_single_gpu": True,
            "stop_after_stage_A_interim": True, "stop_after_stage_B_report": True,
            "automatic_retry": False, "retry_same_untrained_initial": True}:
        raise ValueError("Registered execution/stop rules differ")
    _check_report(reg["report_spec"], plan)
    store = read_json(checked_ref(plan["store"]))
    if plan.get("input_manifest") != store["input_manifest"]:
        raise ValueError("Fresh batch input manifest differs from the frozen graph store")
    prepared_root = Path(plan_path).resolve().parent / "prepared"
    for task_id in task_ids:
        task = plan["tasks"][task_id]
        expected_folds = list(range(5 if task["record"]["task"] == "contract" else 10))
        if (task["folds"] != expected_folds
                or task["record"] != pilot["tasks"][task_id]["record"]
                or task["config"] != pilot["tasks"][task_id]["config"]
                or set(task["prepared"]) != {"%d/1" % f for f in expected_folds}):
            raise ValueError("Fresh task config/input/fold differs from frozen pilot task")
        for ref in task["prepared"].values():
            info = read_json(checked_ref(ref))
            if set(info["profiles"]) != set(PROFILES):
                raise ValueError("Fresh initialization family is incomplete")
            for profile, entry in info["profiles"].items():
                initial = Path(entry["initial"]["path"]).resolve()
                if prepared_root not in initial.parents:
                    raise ValueError("Batch must use its own fresh initial files, not pilot artifacts")
                expected = store["tasks"][task_id]["graphs"][run.key_for_profile(profile)]
                if (entry["graph"] != expected["graph"]
                        or entry["support"]["schema"] != expected["profiles"][profile]["schema"]):
                    raise ValueError("Fresh batch graph/profile schema differs from frozen store")
    sizes = reg.get("pilot_size_evidence", [])
    if len(sizes) != 8:
        raise ValueError("Incomplete pilot size evidence")
    for row in sizes:
        receipt = read_json(checked_ref(row["receipt"]))
        if (row["job"] not in pilot["jobs"] or receipt.get("job") != row["job"]
                or receipt.get("status") != "complete"
                or receipt.get("plan_sha256") != reg["pilot_plan"]["sha256"]):
            raise ValueError("Pilot size evidence receipt identity differs")
        for name in ("best.pt", "last.pt"):
            item = row["checkpoints"][name]
            checkpoint_path = Path(item["path"]).resolve()
            if (item["sha256"] != receipt["artifacts"][name] or item["bytes"] <= 0
                    or checkpoint_path != Path(row["receipt"]["path"]).parent / name
                    or checkpoint_path.stat().st_size != item["bytes"]):
                raise ValueError("Pilot checkpoint size evidence differs")
        _, _, entry = run._prepared(pilot, row["job"])
        initial = row["initial"]
        if (initial["path"] != entry["initial"]["path"]
                or initial["sha256"] != entry["initial"]["sha256"]
                or Path(initial["path"]).stat().st_size != initial["bytes"]):
            raise ValueError("Pilot initial size evidence differs")
    estimate = estimate_storage(sizes, jobs)
    storage = reg.get("storage_preflight", {})
    if (any(storage.get(k) != v for k, v in estimate.items())
            or storage.get("available_bytes_at_preparation", -1) < estimate["required_free_bytes"]):
        raise ValueError("Registered two-times disk preflight differs")
    return reg
