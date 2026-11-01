"""NodeSem sealed executor, preserving the frozen benchmark training functions.

Adapted source: scripts/DFG/dfg_v2/benchmark_v2/execution.py
Source SHA256: 356265898ae2ba17c82f6873112f6e1c70a5a63ec97730f9518d99a2976be9db
Training, supervision, checkpoint serialization and resource observation are
imported unchanged. Only plan preparation, feature construction and binding differ.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
import torch
import numpy as np

from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.dfg_v2.benchmark_v2.checkpoint import build_binding, validate_binding
from scripts.DFG.dfg_v2.benchmark_v2.audit_supervision import make_part
from scripts.DFG.dfg_v2.benchmark_v2.input_guard import FitInputGuard
from scripts.DFG.dfg_v2.benchmark_v2.protocol import PROTOCOL_NAME, PROTOCOL_VERSION, PARTS, validate_parts, FORWARD_SCOPE, SCORE_ROLE, SELECTION_ROLE
from scripts.DFG.dfg_v2.benchmark_v2.support import model_support
from scripts.DFG.dfg_v2.benchmark_v2.trainer import fit
from scripts.DFG.dfg_v2.experiment.init import seeds
from scripts.DFG.dfg_v2.experiment.run import _Lock, _move_model, _code_refs
from scripts.DFG.dfg_v2.experiment.preflight import LOCAL_DEV_POLICY, run_preflight, initialize_context, make_observed_resources
from scripts.DFG.dfg_v2.tasks import read_labels
from scripts.DFG.experiments.common import seed_all, tensor_digest, digest, metrics
from . import VERSION as NODESEM_VERSION
from .feature_spec import FeatureSpec
from .init import checked_initial
from .checkpoint_io import load_checked
from .model import make_nodesem_model, validate

VERSION = "nodesem-execution-v1"
ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "scripts/node_sem/artifacts"
GPU_LOCK = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/.training.lock"


def runtime_refs():
    result = dict(_code_refs())
    for path in sorted((ROOT / "scripts/node_sem").rglob("*.py")):
        if "tests" not in path.parts and "artifacts" not in path.parts:
            result[str(path.relative_to(ROOT))] = ref(path)["sha256"]
    return result


def job_id(job):
    return "{task_id}/{fold}/{seed}/{profile}/{spec_sha256}".format(**job)


def job_directory(root, job):
    return (Path(root) / "runs" / job["task_id"] / ("fold_%d" % job["fold"])
            / ("seed_%d" % job["seed"]) / job["profile"] / job["spec_sha256"])


def _spec(job):
    value = FeatureSpec.from_json(read(checked(job["spec"])))
    if value.digest() != job["spec_sha256"]:
        raise ValueError("Feature specification digest differs")
    return value


def _validate_job(job, plan=None):
    if not re.match(r"^[A-Za-z0-9_]+$", job["task_id"]):
        raise ValueError("Unsafe task identity")
    if job["granularity"] not in ("node", "contract") or not job["task_id"].endswith("_" + job["granularity"]):
        raise ValueError("Task granularity differs")
    if job["profile"] not in ("G0", "G3R") or job["seed"] != 1:
        raise ValueError("NS-P1 only supports frozen seed 1 and G0/G3R")
    if job["seeds"] != seeds(job["granularity"], job["fold"], job["seed"]):
        raise ValueError("Frozen random seeds differ")
    spec = _spec(job)
    if spec.name not in ("S0", "S1"):
        raise ValueError("Only implemented NS-P1 specifications may execute")
    if job["reuse_8h"] is not (spec.name == "S0"):
        raise ValueError("S0 must use read-only historical reuse")
    for name in ("graph", "folds", "labels", "label_view", "feature_view",
                 "feature_npz", "source_preparation", "initial", "initialization"):
        checked(job[name])
    for modality in spec.modalities:
        checked(modality["manifest"])
    if not job["initial"].get("state_sha256"):
        raise ValueError("Missing sealed initial tensor digest")
    validate_parts(job["split"], job["graph_files"])
    if job["config"].get("layer_impl") != "shared_projection":
        raise ValueError("Frozen layer implementation differs")
    if job["reuse_8h"]:
        checked(job["receipt"])
    if plan is not None:
        source = _source_plan(plan["source_h8_plan"])
        historical = historical_job(source, job)
        task, info, entry = h8.prepared(source, historical)
        if (job["graph"] != entry["graph"] or job["config"] != task["config"]
                or job["split"] != info["split"] or job["labels"] != task["record"]["labels"]
                or job["folds"] != task["record"]["folds"]
                or job["label_view"] != task["label_view"]
                or job["graph_files"] != task["record"]["graph_files"]
                or job["support"] != entry["support"]
                or job["initialization"] != info["initialization"]
                or job["source_preparation"] != source["source_preparation"]
                or job["seeds"] != info["seeds"]):
            raise ValueError("Frozen 8H task inputs or configuration differ")
        if spec.view != "anonymous" or spec.modalities[0]["manifest"] != task["feature_view"]:
            raise ValueError("NS-P1 uses the frozen anonymous token view")
        if job["reuse_8h"]:
            if job["initial"] != entry["initial"]:
                raise ValueError("Historical S0 initial differs")
        elif job.get("h8_initial") != entry["initial"]:
            raise ValueError("New initialization must bind the same 8H zero-step source")
    return spec


def _source_plan(reference):
    return h8.load(checked(reference))


def historical_job(source, job):
    matched = [x for x in source["jobs"] if all(x[k] == job[k]
               for k in ("task_id", "fold", "seed", "profile"))]
    if len(matched) != 1:
        raise ValueError("Historical job is missing or ambiguous")
    return matched[0]


def create(batch_dir, matrix, authorization_template):
    """Seal caller-prepared inputs; never initialize or fit a model."""
    batch = Path(batch_dir).resolve()
    if ARTIFACT_ROOT.resolve() not in batch.parents:
        raise ValueError("NodeSem batches must live under NodeSem artifacts")
    if batch.exists():
        raise FileExistsError("Never overwrite a NodeSem batch")
    jobs = copy.deepcopy(matrix["jobs"])
    if not jobs or len({job_id(j) for j in jobs}) != len(jobs):
        raise ValueError("Empty or duplicate execution matrix")
    source_ref = matrix["source_h8_plan"]
    _source_plan(source_ref)
    authorization = copy.deepcopy(authorization_template)
    if type(authorization.get("execution_authorized")) is not bool:
        raise ValueError("Explicit execution_authorized boolean required")
    if authorization.get("scope") not in ("cpu_equivalence", "formal"):
        raise ValueError("Unknown authorization scope")
    if authorization["scope"] == "cpu_equivalence" and authorization["execution_authorized"]:
        raise ValueError("Equivalence preparation cannot authorize formal fits")
    if authorization["execution_authorized"] and not authorization.get("user_request"):
        raise ValueError("Formal execution requires an explicit user request record")
    authorization.update(version=VERSION, jobs=[job_id(j) for j in jobs],
                         matrix_sha256=digest(jobs), source_h8_plan=source_ref)
    plan = dict(version=VERSION, nodesem_version=NODESEM_VERSION,
        protocol=PROTOCOL_NAME, protocol_version=PROTOCOL_VERSION,
        source_h8_plan=source_ref, jobs=jobs, label_policy="L-audit",
        reducer="mean", layer_impl="shared_projection", seeds=[1],
        resource_policy=LOCAL_DEV_POLICY, runtime=runtime_refs(),
        execution_policy="serial fresh process; failure retained; explicit retry authorization",
        final_server_intent=matrix.get("final_server_intent",
            "Final experiments will use a server with sufficient VRAM; local limitations are developmental."))
    for job in jobs:
        _validate_job(job, plan)
    batch.mkdir(parents=True, exist_ok=False)
    write(batch / "authorization.json", authorization)
    plan["authorization"] = ref(batch / "authorization.json")
    write(batch / "plan.json", plan)
    write(batch / "plan.seal.json", dict(version=VERSION, plan=ref(batch / "plan.json"),
                                       jobs=len(jobs), matrix_sha256=digest(jobs)))
    return plan


def load(path):
    path = Path(path)
    plan = read(path)
    seal = read(path.with_name("plan.seal.json"))
    if (plan.get("version") != VERSION or plan.get("nodesem_version") != NODESEM_VERSION
            or plan.get("protocol") != PROTOCOL_NAME
            or plan.get("protocol_version") != PROTOCOL_VERSION
            or seal.get("version") != VERSION or seal.get("plan") != ref(path)
            or seal.get("jobs") != len(plan["jobs"])
            or seal.get("matrix_sha256") != digest(plan["jobs"])):
        raise ValueError("NodeSem plan/seal mismatch")
    if plan["runtime"] != runtime_refs():
        raise ValueError("NodeSem runtime changed after sealing")
    if (plan.get("label_policy") != "L-audit" or plan.get("reducer") != "mean"
            or plan.get("layer_impl") != "shared_projection" or plan.get("seeds") != [1]
            or plan.get("resource_policy") != LOCAL_DEV_POLICY):
        raise ValueError("Frozen protocol/resource configuration differs")
    authorization = read(checked(plan["authorization"]))
    if (type(authorization.get("execution_authorized")) is not bool
            or authorization.get("scope") not in ("cpu_equivalence", "formal")
            or (authorization["scope"] == "cpu_equivalence" and authorization["execution_authorized"])
            or (authorization["execution_authorized"] and not authorization.get("user_request"))):
        raise ValueError("Explicit execution authorization is invalid")
    if (authorization.get("version") != VERSION
            or authorization.get("source_h8_plan") != plan["source_h8_plan"]
            or authorization.get("jobs") != [job_id(j) for j in plan["jobs"]]
            or authorization.get("matrix_sha256") != digest(plan["jobs"])):
        raise ValueError("NodeSem authorization binding differs")
    if len({job_id(j) for j in plan["jobs"]}) != len(plan["jobs"]):
        raise ValueError("Duplicate NodeSem job")
    for job in plan["jobs"]:
        _validate_job(job, plan)
    return plan


def _member(plan, job):
    if sum(j == job for j in plan["jobs"]) != 1:
        raise ValueError("Job is not the exact sealed matrix entry")


def construct(plan, job, device="cpu"):
    _member(plan, job)
    spec = _validate_job(job)
    payload = checked_initial(job["initial"], job["task_id"], job["fold"], job["profile"],
                              job["seed"], None if spec.name == "S0" else spec.digest())
    if spec.name != "S0":
        anchor = checked_initial(job["h8_initial"], job["task_id"], job["fold"],
                                 job["profile"], job["seed"])
        shared = {k for k in payload["state_dict"] if k.startswith(("gcs.", "classify."))}
        expected = {k for k in anchor["state_dict"] if k.startswith(("gcs.", "classify."))}
        if spec.layers == 0:
            expected = {k for k in expected if k.startswith("classify.")}
        if shared != expected or any(
                not torch.equal(payload["state_dict"][k], anchor["state_dict"][k]) for k in shared):
            raise ValueError("New zero-step state does not preserve the bound 8H common parameters")
        del anchor
    seed_all(job["seeds"]["constructor"])
    model = make_nodesem_model(job["granularity"], job["graph"], job["profile"], spec,
                               job["config"], device="cpu", task_id=job["task_id"])
    model.load_state_dict(payload["state_dict"], strict=True)
    if tensor_digest(model.state_dict()) != job["initial"]["state_sha256"]:
        raise ValueError("Loaded NodeSem state differs")
    validate(model, spec)
    _validate_carrier(model, job)
    if model_support(model, job["split"]) != job["support"]:
        raise ValueError("Prepared relation support differs")
    return _move_model(model, device)



def _validate_carrier(model, job):
    manifest = read(checked(job["feature_view"]))
    if manifest.get("data") != job["feature_npz"]:
        raise ValueError("Carrier NPZ binding differs")
    record = dict(manifest)
    record.pop("data")
    if record != model.nodesem_carrier_record:
        raise ValueError("Carrier manifest differs from the constructed input")
    with np.load(str(checked(job["feature_npz"])), allow_pickle=False) as arrays:
        if arrays.files != ["features"]:
            raise ValueError("Carrier NPZ array dictionary differs")
        values = arrays["features"]
    observed = np.stack([model.nx_graph.nodes[index]["token"]
                         for index in range(len(model.original_graph_node_ids))])
    if (values.dtype != np.float32 or values.shape != observed.shape
            or not np.isfinite(values).all() or not np.array_equal(values, observed)):
        raise ValueError("Carrier NPZ differs from constructed node features")


def _validate_nodesem_binding(binding, plan, job, config=None):
    """Explicit identities complement receipt/checkpoint byte integrity."""
    spec = _spec(job)
    cfg = job["config"] if config is None else config
    expected = dict(
        protocol=PROTOCOL_NAME, protocol_version=PROTOCOL_VERSION,
        score_role=SCORE_ROLE, selection_role=SELECTION_ROLE, forward_scope=FORWARD_SCOPE,
        task_id=job["task_id"], task=job["granularity"], fold=job["fold"], seed=job["seed"],
        profile=job["profile"], reducer=plan["reducer"], layer_impl=plan["layer_impl"],
        initial_weights_sha256=job["initial"]["sha256"],
        initial_state_sha256=job["initial"]["state_sha256"],
        support_sha256=digest(job["support"]), effective_config_sha256=digest(cfg),
        initialization=job["initialization"], source_preparation=job["source_preparation"],
        label_policy=plan["label_policy"], label_view=job["label_view"],
        feature_view=job["feature_view"], feature_npz=job["feature_npz"],
        graph=job["graph"], folds=job["folds"], labels=job["labels"], split=job["split"],
        registered_schema=job["support"]["schema"],
        nodesem_version=NODESEM_VERSION, feature_spec=spec.to_json(),
        feature_spec_sha256=spec.digest())
    for key, value in expected.items():
        if binding.get(key) != value:
            raise ValueError("NodeSem binding identity differs: " + key)
    return binding

def binding_parts(plan, job, model, config=None):
    _member(plan, job)
    spec = _spec(job)
    _validate_carrier(model, job)
    cfg = job["config"] if config is None else config
    binding = build_binding(model, task_id=job["task_id"], fold=job["fold"], seed=job["seed"],
        profile=job["profile"], reducer=plan["reducer"], graph_ref=job["graph"],
        fold_ref=job["folds"], label_ref=job["labels"], initial_sha256=job["initial"]["sha256"],
        config=cfg, split=job["split"], support=job["support"],
        initialization_record=job["initialization"])
    binding.update(initial_state_sha256=job["initial"]["state_sha256"],
        label_policy=plan["label_policy"], label_view=job["label_view"],
        feature_view=job["feature_view"], feature_npz=job["feature_npz"],
        source_preparation=job["source_preparation"], nodesem_version=NODESEM_VERSION,
        feature_spec=spec.to_json(), feature_spec_sha256=spec.digest())
    _validate_nodesem_binding(binding, plan, job, cfg)
    validate_binding(model, binding)
    groups = validate_parts(job["split"], job["graph_files"])
    parts = {role: make_part(model, job["granularity"], groups[role], binding) for role in PARTS}
    return binding, parts


def _successful(folder):
    results = list(Path(folder).glob("attempt_*/receipt.json"))
    if len(results) > 1:
        raise ValueError("Duplicate successful NodeSem fits")
    return results[0].parent if results else None


def _next_attempt(path, job, folder):
    """A failed attempt cannot restart without a new independently sealed approval."""
    folder = Path(folder)
    prior = sorted(p for p in folder.glob("attempt_*")
                   if p.is_dir() or p.name.endswith((".started.json", ".failure.json")))
    if not prior:
        return folder / "attempt_001"
    approval_path = Path(path).parent / ("retry_" + digest(job) + ".json")
    if not approval_path.is_file():
        raise RuntimeError("Retained failed/incomplete attempt; explicit retry approval required")
    approval = read(approval_path)
    if read(approval_path.with_suffix(".seal.json")).get("approval") != ref(approval_path):
        raise ValueError("Retry approval seal differs")
    if (approval.get("approved") is not True or approval.get("plan") != ref(path)
            or approval.get("job") != job or not approval.get("user_request")
            or approval.get("automatic_retry") is not False
            or approval.get("restart_from_sealed_initial") is not True):
        raise ValueError("Retry approval identity/policy differs")
    name = approval.get("attempt", "")
    if not re.match(r"^attempt_[0-9]{3}$", name):
        raise ValueError("Invalid retry attempt name")
    number = max(int(p.name[8:11]) for p in prior)
    if name != "attempt_%03d" % (number + 1):
        raise ValueError("Retry attempt is not the next retained generation")
    checked(approval["failure"])
    if Path(approval["failure"]["path"]).resolve().parent != folder.resolve():
        raise ValueError("Retry failure belongs to another job")
    return folder / name


def fit_one(path, job):
    plan = load(path)
    _member(plan, job)
    if job["reuse_8h"]:
        return verify_one(path, plan, job)
    authorization = read(checked(plan["authorization"]))
    if (authorization.get("scope") != "formal"
            or authorization.get("execution_authorized") is not True
            or not authorization.get("user_request")):
        raise PermissionError("Formal training has not been authorized")
    folder = job_directory(Path(path).parent, job)
    existing = _successful(folder)
    if existing:
        verify_one(path, plan, job, existing)
        return "reused"
    attempt = _next_attempt(path, job, folder)
    folder.mkdir(parents=True, exist_ok=True)
    start = dict(job=job, plan=ref(path), execution_authorization=plan["authorization"],
                 runtime=plan["runtime"], started_unix=time.time(), pid=os.getpid(),
                 automatic_retry=False)
    write(attempt.with_suffix(".started.json"), start)
    cfg = job["config"]
    try:
        # Preserve the historical environment and resource gates.
        import dgl, sklearn, numpy, networkx
        environment = dict(python=sys.version, torch=torch.__version__, dgl=dgl.__version__,
            sklearn=sklearn.__version__, numpy=numpy.__version__, networkx=networkx.__version__)
        if environment != cfg["environment"]:
            raise ValueError("Frozen package environment differs")
        pre = run_preflight(job, ref(path)["sha256"], folder, plan["resource_policy"])
        context = initialize_context(pre["baseline"], cfg["device"])
        write(attempt.with_suffix(".context.json"), context)
        resources = make_observed_resources(cfg["device"], pre["baseline"], context,
            attempt.with_suffix(".memory_samples.jsonl"), minimum_free_mib=100,
            policy=plan["resource_policy"], history_path=attempt / "history.jsonl")
        torch.set_num_threads(cfg["threads"])
        with resources:
            model = construct(plan, job, cfg["device"])
            resources.check()
            binding, parts = binding_parts(plan, job, model)
            labels = read_labels(job["labels"])
            seed_all(job["seeds"]["fit"])
            with FitInputGuard(model, binding, parts, labels) as guard:
                result = fit(model, guard.wrap_parts(), job["granularity"], labels, cfg, attempt,
                    binding, model.original_graph_node_ids, job["support"], memory_guard=resources)
                guard.finish()
                write(attempt / "validation_performance.json", guard.summary())
        result["resources"] = dict(resources.summary(), preflight=pre["receipt_ref"],
            resource_policy=plan["resource_policy"], context_ref=ref(attempt.with_suffix(".context.json")),
            training_pid=os.getpid())
        write(attempt / "final_result.json", result)
        write(attempt / "effective_config.json", cfg)
        write(attempt / "schema_support_audit.json", job["support"])
        write(attempt / "initialization_ref.json", job["initial"])
        write(attempt / "receipt.json", dict(version=VERSION, status="complete", job=job, plan=ref(path),
            execution_start=ref(attempt.with_suffix(".started.json")), binding_sha256=digest(binding),
            artifacts={str(p.relative_to(attempt)): ref(p)["sha256"]
                       for p in sorted(attempt.rglob("*")) if p.is_file()}))
    except Exception as error:
        write(attempt.with_suffix(".failure.json"), dict(job=job, error=repr(error),
            traceback=traceback.format_exc(), automatic_retry=False, stop_batch=True))
        raise
    verify_one(path, plan, job, attempt)
    return "complete"

def _result_inputs(plan, job, historical):
    if historical:
        task, info, entry = h8.prepared(plan, job)
        return task, info, entry
    task = dict(granularity=job["granularity"], config=job["config"],
        record=dict(labels=job["labels"], folds=job["folds"], graph_files=job["graph_files"]),
        label_view=job["label_view"], feature_view=job["feature_view"], feature_npz=job["feature_npz"])
    info = dict(split=job["split"], initialization=job["initialization"], seeds=job["seeds"])
    entry = dict(graph=job["graph"], initial=job["initial"], support=job["support"])
    return task, info, entry


def _verify_result(path, plan, job, attempt, historical=False):
    """Read-only adaptation of 8H verify_one; every deserialization is SHA guarded."""
    attempt = Path(attempt)
    receipt = read(attempt / "receipt.json")
    if (receipt["job"] != job or receipt["plan"] != ref(path)
            or receipt["status"] != "complete"):
        raise ValueError("Receipt identity differs")
    start = read(checked(receipt["execution_start"]))
    if (start["job"] != job or start["plan"] != ref(path)
            or start["execution_authorization"] != plan["authorization"]):
        raise ValueError("Start authorization differs")
    if historical:
        h8.verify_start(path, plan, start, attempt / "receipt.json")
        h8.validate_retry_receipt(path, job, attempt)
    elif receipt.get("version") != VERSION or start.get("runtime") != plan["runtime"]:
        raise ValueError("NodeSem execution version differs")
    required = {"best.pt", "last.pt", "best.json", "last.json", "binding.json",
        "final_result.json", "history.jsonl", "inner_val_predictions.json",
        "outer_test_predictions.json", "inner_val_orig_all_predictions.json",
        "outer_test_orig_all_predictions.json", "validation_performance.json",
        "effective_config.json", "schema_support_audit.json", "initialization_ref.json"}
    if not required <= set(receipt["artifacts"]):
        raise ValueError("Missing fit artifacts")
    for name, sha in receipt["artifacts"].items():
        target = (attempt / name).resolve()
        if attempt.resolve() not in target.parents:
            raise ValueError("Receipt path escapes fit")
        checked(dict(path=str(target), sha256=sha))
    task, info, entry = _result_inputs(plan, job, historical)
    binding = read(attempt / "binding.json")
    if (receipt["binding_sha256"] != digest(binding) or binding["protocol"] != PROTOCOL_NAME
            or binding["label_policy"] != plan["label_policy"]
            or binding["label_view"] != task["label_view"]
            or binding["feature_view"] != task["feature_view"]
            or binding["feature_npz"] != task["feature_npz"]
            or binding["graph"] != entry["graph"] or binding["folds"] != task["record"]["folds"]
            or binding["labels"] != task["record"]["labels"] or binding["split"] != info["split"]
            or binding["initial_state_sha256"] != entry["initial"]["state_sha256"]
            or binding["effective_config_sha256"] != digest(task["config"])
            or binding["registered_schema"] != entry["support"]["schema"]):
        raise ValueError("Fit binding differs from sealed execution plan")
    if not historical:
        _validate_nodesem_binding(binding, plan, job)
    for name in ("graph", "folds", "labels", "label_view", "feature_view", "feature_npz"):
        checked(binding[name])
    checked(entry["initial"])
    if (read(attempt / "effective_config.json") != task["config"]
            or read(attempt / "schema_support_audit.json") != entry["support"]
            or read(attempt / "initialization_ref.json") != entry["initial"]):
        raise ValueError("Effective inputs differ")
    result = read(attempt / "final_result.json")
    history = [json.loads(x) for x in (attempt / "history.jsonl").read_text().splitlines()]
    if (not history or len(history) > 50
            or [x["epoch"] for x in history] != list(range(len(history)))
            or result["best_epoch"] != min(range(len(history)), key=lambda i: history[i]["inner_val_loss"])):
        raise ValueError("Best/history selection differs")
    if (result["last_epoch"] != len(history) - 1
            or result["outer_supervision_used_in_optimization"] is not False):
        raise ValueError("Training boundary differs")
    if result["checkpoint_roundtrip_exact"] != {
            role: {ck: True for ck in ("best", "last")} for role in ("inner_val", "outer_test")}:
        raise ValueError("Checkpoint reload was not exact")
    for ck in ("best", "last"):
        payload = load_checked(dict(path=str(attempt / (ck + ".pt")),
                                   sha256=receipt["artifacts"][ck + ".pt"]), map_location="cpu")
        if (payload["binding"] != binding
                or tensor_digest(payload["state_dict"]) != payload["state_sha256"]
                or payload["epoch"] != result[ck + "_epoch"]
                or result["checkpoint_sha256"][ck] != receipt["artifacts"][ck + ".pt"]):
            raise ValueError("Checkpoint differs")
        side = read(attempt / (ck + ".json"))
        if any(payload[k] != side[k] for k in ("state_sha256", "binding", "model_input", "epoch", "monitor")):
            raise ValueError("Checkpoint sidecar differs")
        del payload
    if read(attempt / "validation_performance.json")["deep_boundaries"] != [
            "start", "after_training", "after_evaluation"]:
        raise ValueError("Three deep boundaries absent")
    from scripts.DFG.dfg_v2.experiment.local_dev import validate_local_resource_summary
    resources = result["resources"]
    checked(dict(path=resources["raw_samples_path"], sha256=resources["raw_samples_sha256"]))
    pre = read(checked(resources["preflight"]))
    read(checked(resources["context_ref"]))
    if (pre["job"] != job or pre["plan_sha256"] != ref(path)["sha256"]
            or pre["policy"] != plan["resource_policy"] or pre["pid"] != resources["training_pid"]):
        raise ValueError("Fresh-process preflight differs")
    if pre["cuda_initialized_before"] is not False or pre["cuda_initialized_after"] is not False:
        raise ValueError("Preflight occurred after CUDA initialization")
    samples = [json.loads(x) for x in Path(resources["raw_samples_path"]).read_text().splitlines()]
    validate_local_resource_summary(resources, plan["resource_policy"], attempt / "history.jsonl", samples)
    rows = read(checked(task["label_view"]))[job["task_id"]]
    node = task["granularity"] == "node"
    key = lambda x: (x["file"], x["original_graph_node_id"]) if node else x["file"]
    for role in ("inner_val", "outer_test"):
        candidates = [x for x in rows if x["file"] in info["split"][role + "_files"]]
        for aux in (False, True):
            table = {key(x): x for x in candidates if aux or x["L-audit_include"]}
            pred = read(attempt / (role + ("_orig_all" if aux else "") + "_predictions.json"))
            if len(pred) != len(table) or {key(x) for x in pred} != set(table):
                raise ValueError("Prediction identity/population differs")
            field = "orig" if aux else "L-audit_target"
            if any(x["target"] != table[key(x)][field] for x in pred):
                raise ValueError("Prediction truth differs")
            for ck in ("best", "last"):
                observed = metrics([x["target"] for x in pred], [x[ck] for x in pred])
                expected = result["orig_all_auxiliary"][role][ck] if aux else result[role][ck]
                if observed != expected:
                    raise ValueError("Independent metric recalculation differs")
    return dict(job=job, attempt=str(attempt.resolve()), audit=dict(passed=True), result=result)


def verify_one(path, plan, job, attempt=None):
    _member(plan, job)
    if job["reuse_8h"]:
        source_path = checked(plan["source_h8_plan"])
        source = h8.load(source_path)
        historical = historical_job(source, job)
        expected = checked(job["receipt"])
        value = _verify_result(source_path, source, historical, expected.parent, historical=True)
        value.update(reuse_8h=True, source_receipt=job["receipt"], nodesem_job=job)
        return value
    if attempt is None:
        attempt = _successful(job_directory(Path(path).parent, job))
    if attempt is None:
        raise ValueError("No successful NodeSem attempt")
    return _verify_result(path, plan, job, attempt)


def execute(path, only):
    plan = load(path)
    selected = [j for j in plan["jobs"] if job_id(j) == only]
    if len(selected) != 1:
        raise ValueError("Select exactly one sealed NodeSem job")
    with _Lock(GPU_LOCK):
        return fit_one(path, selected[0])


def controller(path):
    """One worker per job, in order; never silently restart a failed attempt."""
    plan = load(path)
    root = Path(path).parent
    accepted = []
    with _Lock(root / ".controller.lock"):
        for job in plan["jobs"]:
            if job["reuse_8h"]:
                result = verify_one(path, plan, job)
                accepted.append(dict(job=job, receipt=job["receipt"], reuse_8h=True))
                continue
            folder = job_directory(root, job)
            found = _successful(folder)
            if found is None:
                candidate = _next_attempt(path, job, folder)
                log = folder / (candidate.name + ".worker.log")
                folder.mkdir(parents=True, exist_ok=True)
                # Exclusive mode keeps prior failures and their logs intact.
                with log.open("x", encoding="utf8") as stream:
                    subprocess.run([sys.executable, "-B", "-m", "scripts.node_sem.execution",
                        "worker", "--plan", str(path), "--only", job_id(job)],
                        check=True, stdout=stream, stderr=subprocess.STDOUT, cwd=str(ROOT))
                found = _successful(folder)
            if found is None:
                raise RuntimeError("Worker produced no success receipt")
            verify_one(path, plan, job, found)
            accepted.append(dict(job=job, receipt=ref(found / "receipt.json"), reuse_8h=False))
        complete = root / "complete.json"
        payload = dict(version=VERSION, plan=ref(path), passed=True, receipts=accepted)
        if complete.exists():
            if read(complete) != payload:
                raise ValueError("Existing completion differs")
        else:
            write(complete, payload)
    return accepted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("worker", "all", "verify"))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--only")
    args = parser.parse_args()
    if args.command == "worker":
        execute(args.plan, args.only)
    elif args.command == "all":
        controller(args.plan)
    else:
        plan = load(args.plan)
        for job in plan["jobs"]:
            verify_one(args.plan, plan, job)


if __name__ == "__main__":
    main()
