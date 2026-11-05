"""Read-only archive verification copied from experiment/run.py.
SHA256 3670d4e6b7e953ec705e9863e5011b518a111bf74007be2a3a4e5833a3e5da2c
User-approved difference: validate the hash-bound historical runtime, not newly added source files.
No old seal or execution permission is changed.
"""
import json
from pathlib import Path
import torch
from ..experiment.run import _ref, job_id, _prepared, _validate_predictions
from ..experiment.protocol import PROTOCOL_NAME, PROTOCOL_VERSION, SCORE_ROLE, SELECTION_ROLE, FORWARD_SCOPE
from ..tasks import checked_ref
from scripts.DFG.integration.io import read_json, checked, sha256
from scripts.DFG.experiments.common import digest, tensor_digest

def validate_archived_amendment(path,plan_path,plan=None):
    from ..experiment.amendment import validate_amendment
    r=read_json(path);proof=read_json(checked_ref(r["equivalence_proof"]))
    root=Path(__file__).resolve().parents[4]
    actual={name:sha256(root/name) for name in proof["runtime"]}
    if actual != proof["runtime"]:raise ValueError("Historical runtime bytes differ")
    return validate_amendment(path,plan_path,plan,current_runtime=actual)
def _verify_execution_authorization(attempt, plan, job, plan_path, receipt):
    """Archive-safe authorization proof; do not re-run live retry/failure gates."""
    if "batch_registration" not in plan:
        return
    from ..experiment.batch import stage_jobs, validate_authorization
    started_path = attempt.with_suffix(".started.json")
    start_ref = receipt.get("execution_start", {})
    if start_ref != _ref(started_path):
        raise ValueError("Successful batch receipt execution-start binding differs")
    started = read_json(checked_ref(start_ref))
    if (started.get("job") != job or started.get("plan_sha256") != sha256(plan_path)
            or started.get("resume_epoch") is not False
            or started.get("retry_from_same_untrained_initial") is not True):
        raise ValueError("Successful batch start identity/plan/restart policy differs")
    authorization = started.get("execution_authorization", {})
    authorization_path = checked_ref(authorization)
    stages = [stage for stage in ("A", "B")
              if job_id(job) in [job_id(j) for j in stage_jobs(plan, stage)]]
    if len(stages) != 1:
        raise ValueError("Successful job must belong to exactly one approved stage")
    verified, unused = validate_authorization(plan_path, plan, stages[0], authorization_path)
    if verified != authorization:
        raise ValueError("Successful batch stage authorization changed")
    if "runtime_amendment" in started or "amendment" in unused:
        amendment_ref = started.get("runtime_amendment")
        if stages[0] != "B" or amendment_ref != unused.get("amendment"):
            raise ValueError("Successful fit runtime amendment is not the authorized stage B revision")
        from .archive import validate_archived_amendment as validate_amendment
        validate_amendment(checked_ref(amendment_ref), plan_path, plan)
        ticket = read_json(checked_ref(started.get("execution_ticket", {})))
        if (ticket.get("plan") != _ref(plan_path) or ticket.get("job") != job_id(job)
                or ticket.get("authorization") != authorization
                or ticket.get("amendment") != amendment_ref):
            raise ValueError("Successful fit controller ticket identity differs")



def _verify_attempt(attempt, plan, job, plan_path):
    receipt = read_json(attempt / "receipt.json")
    _verify_execution_authorization(attempt, plan, job, plan_path, receipt)
    if (receipt.get("status") != "complete" or receipt.get("job") != job
            or receipt.get("plan_sha256") != sha256(plan_path)
            or receipt.get("score_role") != SCORE_ROLE or receipt.get("selection_role") != SELECTION_ROLE):
        raise ValueError("Receipt identity/protocol mismatch")
    required = {"result.json", "history.jsonl", "best.pt", "last.pt", "best.json", "last.json",
        "binding.json", "inner_val_predictions.json", "outer_test_predictions.json",
        "effective_config.json", "schema_support_audit.json", "initialization_ref.json", "model_input.json"}
    if not required <= set(receipt.get("artifacts", {})):
        raise ValueError("Receipt missing required artifacts")
    for name, checksum in receipt["artifacts"].items():
        path = (attempt / name).resolve()
        if attempt.resolve() not in path.parents:
            raise ValueError("Receipt path escapes attempt")
        checked(path, checksum)
    task, info, entry = _prepared(plan, job)
    binding = read_json(attempt / "binding.json")
    expected_binding = dict(protocol=PROTOCOL_NAME, protocol_version=PROTOCOL_VERSION,
        task_id=job["task_id"], task=task["record"]["task"], fold=job["fold"], seed=job["seed"],
        profile=job["profile"], reducer=plan["reducer"], score_role=SCORE_ROLE,
        layer_impl=plan.get("layer_impl", "original"),
        selection_role=SELECTION_ROLE, forward_scope=FORWARD_SCOPE,
        graph=entry["graph"], folds=task["record"]["folds"], labels=task["record"]["labels"],
        initial_weights_sha256=entry["initial"]["sha256"], split=info["split"],
        initial_state_sha256=entry["initial"]["state_sha256"],
        effective_config_sha256=digest(task["config"]), support_sha256=digest(entry["support"]),
        registered_schema=entry["support"]["schema"], initialization=info["initialization"])
    observed_binding = dict(binding)
    # Historical Prompt 7 bindings predate this field; their missing value means
    # original only. Preserve their serialized bytes and receipt digest.
    if "layer_impl" not in plan:
        observed_binding.setdefault("layer_impl", "original")
    if digest(binding) != receipt["binding_sha256"] or any(observed_binding.get(k) != v for k,v in expected_binding.items()):
        raise ValueError("Binding differs from sealed plan")
    if read_json(attempt / "initialization_ref.json") != entry["initial"]:
        raise ValueError("Initial state reference differs")
    if read_json(attempt / "schema_support_audit.json") != entry["support"]:
        raise ValueError("Runtime support differs")
    if read_json(attempt / "effective_config.json") != task["config"]:
        raise ValueError("Effective config differs")
    result = read_json(attempt / "result.json")
    if (result.get("status") != "complete" or result.get("score_role") != SCORE_ROLE
            or result.get("selection_role") != SELECTION_ROLE
            or result.get("initial_sha256") != entry["initial"]["state_sha256"]
            or result.get("layer_impl", "original") != plan.get("layer_impl", "original")):
        raise ValueError("Incomplete/misbound fit result")
    if "resource_policy" in plan:
        from ..experiment.resource_plan import validate_resource_result
        validate_resource_result(result, plan, job, plan_path,
                                 history_path=attempt / "history.jsonl")
        if plan["resource_policy"]["version"] == "local_dev_v1":
            if any(receipt.get(key) != result[key] for key in ("memory_tight", "possible_memory_spill")):
                raise ValueError("Receipt local memory flags differ from verified evidence")
    history = [json.loads(line) for line in (attempt / "history.jsonl").read_text().splitlines()]
    if (not history or [r["epoch"] for r in history] != list(range(len(history)))
            or result["last_epoch"] != len(history)-1 or result["history_rows"] != len(history)
            or result["best_epoch"] != min(range(len(history)), key=lambda i: history[i]["inner_val_loss"])
            or result.get("checkpoint_roundtrip_exact") != {
                role: {ck:True for ck in ("best","last")} for role in ("inner_val","outer_test")}
            or result.get("outer_supervision_used_in_optimization") is not False):
        raise ValueError("History/selection/roundtrip acceptance differs")
    for ck in ("best", "last"):
        sidecar = read_json(attempt / (ck + ".json"))
        payload = torch.load(str(attempt / (ck + ".pt")), map_location="cpu")
        if (any(payload.get(k) != sidecar.get(k) for k in
                ("format","state_sha256","model_input","binding","binding_sha256","epoch","monitor"))
                or tensor_digest(payload["state_dict"]) != payload["state_sha256"]
                or sidecar["model_input"] != read_json(attempt / "model_input.json")
                or sidecar["epoch"] != result[ck + "_epoch"]):
            raise ValueError("Checkpoint payload/sidecar/epoch differs")
        del payload
        if (sidecar.get("format") != "ddg-controlled-v1" or sidecar.get("binding") != binding
                or sidecar.get("binding_sha256") != digest(binding)
                or result["checkpoint_sha256"][ck] != receipt["artifacts"][ck + ".pt"]):
            raise ValueError("Checkpoint/binding differs")
    from scripts.DFG.experiments.common import metrics
    for role in ("inner_val", "outer_test"):
        rows = read_json(attempt / (role + "_predictions.json"))
        _validate_predictions(rows, role, task, info, entry)
        for ck in ("best", "last"):
            recomputed = metrics([r["target"] for r in rows], [r[ck] for r in rows])
            if recomputed != result[role][ck]:
                raise ValueError("Exported prediction metrics differ")
    return result

