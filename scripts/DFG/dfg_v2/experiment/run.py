"""Sealed nested DFG v2 plan, serial execution and verified reporting.

Production CLI uses CUDA. CPU execution requires a separately sealed synthetic
programmatic test plan. Historical graphs, folds and results are read-only.
"""
import argparse
import copy
import gc
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import time
import traceback
import torch

from scripts.DFG.experiments.common import digest, seed_all, tensor_digest
from scripts.DFG.integration.io import checked, read_json, sha256, write_json
from scripts.labeling_v2.safe_graph import read_graph
from .. import PROFILES, AUX_NODE_TYPES
from ..inputs import load_manifest
from ..model import make_model, validate_registration, LAYER_IMPLEMENTATIONS
from ..pipeline import key_for_profile
from ..store import verify_store
from ..supervision import DfgV2Supervision
from ..tasks import checked_ref, read_labels
from .init import initialize_family, seeds as derived_seeds, INITIALIZATION_VERSION
from .protocol import (PARTS, PROTOCOL_NAME, PROTOCOL_VERSION, FORWARD_SCOPE,
                       SCORE_ROLE, SELECTION_ROLE, load_folds, validate_parts)
from .support import support as graph_support

VERSION = "dfg-v2-execution-v1"
ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PROFILES = ("G0", "G1R", "G2R", "G3R", "G3")
SELECTION_RULE = dict(candidates=["G1R", "G2R", "G3R", "G3"],
    metric="inner_val.best.buggy_f1", task_weight="equal; folds equal within task",
    tie_margin_percentage_points=.1, tie_break="fewer canonical relations; then profile name",
    additional_seed_absolute_delta_percentage_points=.2, outer_test_used=False)


def _ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha256(path))


def _code_refs():
    paths = []
    for directory in (ROOT / "scripts/DFG", ROOT / "sco_models"):
        paths.extend(p for p in directory.rglob("*.py")
                     if "artifacts" not in p.parts and "tests" not in p.parts)
    paths.append(ROOT / "scripts/labeling_v2/safe_graph.py")
    return {str(p.relative_to(ROOT)): sha256(p) for p in sorted(set(paths))}


def _git_head():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)
    return result.stdout.strip()


def _select(values, allowed, default, name):
    values = default if values is None else values.split(",") if isinstance(values, str) else list(values)
    if not values or len(values) != len(set(values)) or any(v not in allowed for v in values):
        raise ValueError("Empty, duplicate or unknown " + name)
    return list(values)


def _effective_config(record, test_mode, test_config, layer_impl="original"):
    source = read_json(checked_ref(record["provenance"]["source_task_manifest"]))
    if test_mode:
        if record.get("label_version") != "synthetic_only" or not test_config:
            raise ValueError("CPU test plans require synthetic labels and explicit test configuration")
        config = copy.deepcopy(test_config)
    else:
        if test_config is not None:
            raise ValueError("Production config overrides are forbidden")
        config = copy.deepcopy(source["config"])
        if (config["maximum_training_epochs"] != 50 or config["schedule_epochs"] != 50
                or config["patience"] != 7 or config["delta"] != .001
                or config["feature"] != "inside_token"):
            raise ValueError("Frozen task training configuration differs")
    config.update(layer_impl=layer_impl, protocol=PROTOCOL_NAME, protocol_version=PROTOCOL_VERSION,
        forward_scope=FORWARD_SCOPE, score_role=SCORE_ROLE, selection_role=SELECTION_ROLE,
        selection="strict minimum inner validation loss; post-update eval forward",
        partition_policy="fixed_graph_nested_file_supervision",
        batch="inner_train node mask or file batch; one optimizer step per epoch",
        device="cpu" if test_mode else "cuda:0", mode="synthetic_test" if test_mode else "full")
    return config


def create_plan(store, output, tasks=None, profiles=None, seeds=(1,), folds=None,
                reducer="mean", test_mode=False, test_config=None, layer_impl="original",
                _batch_registration=None):
    """Seal inputs, untrained initial states and the complete requested matrix."""
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing experiment directory: " + str(output))
    if reducer not in ("mean", "nonempty_mean"):
        raise ValueError("Unknown reducer")
    if layer_impl not in LAYER_IMPLEMENTATIONS:
        raise ValueError("Unknown layer_impl")
    store = Path(store).resolve()
    accepted = verify_store(store)
    document = read_json(store)
    inputs = load_manifest(checked_ref(document["input_manifest"]), check_files=True)
    task_ids = _select(tasks, document["tasks"], sorted(document["tasks"]), "tasks")
    profiles = _select(profiles, PROFILES, DEFAULT_PROFILES, "profiles")
    seed_values = [int(v) for v in seeds.split(",")] if isinstance(seeds, str) else list(seeds)
    if (not seed_values or len(seed_values) != len(set(seed_values))
            or any(type(v) is not int or v < 1 for v in seed_values)):
        raise ValueError("Seeds must be distinct positive integers")
    wanted_folds = ([int(v) for v in folds.split(",")] if isinstance(folds, str)
                    else None if folds is None else list(folds))
    if wanted_folds is not None and (not wanted_folds or len(wanted_folds) != len(set(wanted_folds))):
        raise ValueError("Empty/duplicate fold selection")
    runtime = _code_refs()
    plan = dict(version=VERSION, protocol=PROTOCOL_NAME, protocol_version=PROTOCOL_VERSION,
        score_role=SCORE_ROLE, selection_role=SELECTION_ROLE, forward_scope=FORWARD_SCOPE,
        test_mode=bool(test_mode), git_head=_git_head(), runtime=runtime,
        store=_ref(store), store_seal=_ref(store.with_name("store.seal.json")),
        store_verification=accepted, input_manifest=document["input_manifest"],
        reducer=reducer, layer_impl=layer_impl, profiles=profiles, seeds=seed_values, requested_folds=wanted_folds,
        initialization_version=INITIALIZATION_VERSION, selection_rule=SELECTION_RULE,
        seed_rule="10000+fold+(1000 if contract else 0)+100000*(seed-1); fit=constructor+1000000",
        execution_policy="serial one model; failed attempts retained; explicit whole-fit retry",
        tasks={}, jobs=[])
    if _batch_registration is not None:
        if test_mode:
            raise ValueError("Production batch registration cannot wrap a synthetic test")
        from .batch_plan import attach_registration
        attach_registration(plan, _batch_registration)
    output.mkdir(parents=True)
    for task_id in task_ids:
        record = inputs["tasks"][task_id]
        folded = load_folds(record)
        selected = list(range(folded["k_folds"])) if wanted_folds is None else wanted_folds
        if any(type(f) is not int or not 0 <= f < folded["k_folds"] for f in selected):
            raise ValueError("Unknown frozen fold")
        config = _effective_config(record, test_mode, test_config, layer_impl)
        task_info = dict(record=record, config=config, folds=selected, prepared={})
        plan["tasks"][task_id] = task_info
        family_profiles = ["G0"] + [p for p in profiles if p != "G0"]
        for fold in selected:
            split = folded["folds"][fold]
            validate_parts(split, record["graph_files"])
            for seed in seed_values:
                seed_record = derived_seeds(record["task"], fold, seed)
                models, graphs, supports, entries = {}, {}, {}, {}
                for profile in family_profiles:
                    entry = document["tasks"][task_id]["graphs"][key_for_profile(profile)]
                    graph = read_graph(checked_ref(entry["graph"]))
                    graphs[profile] = entry["graph"]
                    supports[profile] = graph_support(graph, profile, split)
                    if supports[profile]["schema"] != entry["profiles"][profile]["schema"]:
                        raise ValueError("Stored and materialized schema differ")
                    seed_all(seed_record["constructor"])
                    models[profile] = make_model(record["task"], graph, profile, "cpu",
                        hidden_size=config["hidden_size"], layers=config["layers"],
                        heads=config["heads"], reducer=reducer, layer_impl=layer_impl)
                    del graph
                pairing = initialize_family(models, seed_record["constructor"])
                folder = output / "prepared" / task_id / ("fold_%d" % fold) / ("seed_%d" % seed)
                folder.mkdir(parents=True)
                write_json(folder / "initialization.json", pairing)
                for profile, model in models.items():
                    state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
                    state_sha = tensor_digest(state)
                    if state_sha != pairing["profiles"][profile]["state_sha256"]:
                        raise ValueError("Initialization digest differs")
                    path = folder / (profile + "_initial.pt")
                    torch.save(dict(kind="untrained_initial", optimizer_steps=0,
                        task_id=task_id, fold=fold, seed=seed, profile=profile,
                        fit_seed=seed_record["fit"], state_dict=state, state_sha256=state_sha,
                        initialization_version=INITIALIZATION_VERSION, layer_impl=layer_impl), str(path))
                    entries[profile] = dict(layer_impl=layer_impl, graph=graphs[profile], support=supports[profile],
                        initial=dict(_ref(path), state_sha256=state_sha),
                        parameter_count=sum(p.numel() for p in model.parameters()))
                    if profile in profiles:
                        plan["jobs"].append(dict(task_id=task_id, fold=fold, seed=seed, profile=profile,
                                                 layer_impl=layer_impl))
                info = dict(layer_impl=layer_impl, task_id=task_id, fold=fold, seed=seed, seeds=seed_record, split=split,
                    initialization=_ref(folder / "initialization.json"), profiles=entries)
                write_json(folder / "task.json", info)
                task_info["prepared"]["%d/%d" % (fold, seed)] = _ref(folder / "task.json")
                del models, supports, entries, state, model
                gc.collect()
    if _code_refs() != runtime:
        raise ValueError("Runtime changed while preparing experiment")
    path = output / "plan.json"
    write_json(path, plan)
    write_json(output / "plan.seal.json", dict(version=VERSION, plan_sha256=sha256(path),
        jobs=len(plan["jobs"]), protocol_version=PROTOCOL_VERSION, test_mode=bool(test_mode)))
    _load_plan(path)
    return plan


def _load_plan(path, check_code=True):
    path = Path(path).resolve()
    seal = read_json(path.with_name("plan.seal.json"))
    checked(path, seal["plan_sha256"])
    plan = read_json(path)
    if (plan.get("version") != VERSION or seal.get("version") != VERSION
            or plan.get("protocol_version") != PROTOCOL_VERSION
            or plan.get("score_role") != SCORE_ROLE or plan.get("selection_role") != SELECTION_ROLE
            or seal["jobs"] != len(plan["jobs"]) or seal["test_mode"] != plan["test_mode"]):
        raise ValueError("Experiment protocol/seal mismatch")
    if "resource_policy" in plan:
        from .preflight import validate_policy
        from .resource_plan import validate_resource_origin
        validate_policy(plan["resource_policy"])
        if plan.get("resource_origin", {}).get("version") == "prompt8-fresh-batch-resource-v1":
            from .batch_plan import validate_batch_plan
            validate_batch_plan(plan, path)
        else:
            if "batch_registration" in plan:
                raise ValueError("Batch registration requires its own resource origin")
            validate_resource_origin(plan)
    elif "resource_origin" in plan or "batch_registration" in plan:
        raise ValueError("Resource origin requires registered resource policy")
    layer_impl = plan.get("layer_impl", "original")
    if (layer_impl not in LAYER_IMPLEMENTATIONS
            or any(job.get("layer_impl", "original") != layer_impl for job in plan["jobs"])):
        raise ValueError("Plan/job layer_impl mismatch")
    identities = [job_id(job) for job in plan["jobs"]]
    if not identities or len(identities) != len(set(identities)):
        raise ValueError("Missing or duplicate execution jobs")
    if check_code and plan["runtime"] != _code_refs():
        raise ValueError("Training computation changed since plan seal")
    checked_ref(plan["store"])
    checked_ref(plan["store_seal"])
    inputs = plan["input_manifest"]
    checked_ref(inputs)
    checked(inputs["seal_path"], inputs["seal_sha256"])
    for task_id, task in plan["tasks"].items():
        if task["config"].get("layer_impl", "original") != layer_impl:
            raise ValueError("Plan/config layer_impl mismatch")
        record = task["record"]
        for key in ("folds", "labels", "original_graph"):
            checked_ref(record[key])
        for asset_path, asset_sha in record["feature"]["asset_hashes"].items():
            checked(asset_path, asset_sha)
        for ref in record["sources"].values():
            checked_ref(ref)
        for ref in record["provenance"].values():
            checked_ref(ref)
        for ref in task["prepared"].values():
            info = read_json(checked_ref(ref))
            initialization = read_json(checked_ref(info["initialization"]))
            if (info.get("layer_impl", "original") != layer_impl
                    or initialization.get("layer_impl", "original") != layer_impl
                    or any(row.get("layer_impl", "original") != layer_impl
                           for row in initialization["profiles"].values())):
                raise ValueError("Prepared/initialization layer_impl mismatch")
            for entry in info["profiles"].values():
                if entry.get("layer_impl", "original") != layer_impl:
                    raise ValueError("Prepared profile layer_impl mismatch")
                checked_ref(entry["graph"])
                checked_ref(entry["initial"])
    return plan


def job_id(job):
    return "{task_id}/{fold}/{seed}/{profile}".format(**job)


def _job_directory(output, job):
    return output / "runs" / job["task_id"] / ("fold_%d" % job["fold"]) / ("seed_%d" % job["seed"]) / job["profile"]


def _prepared(plan, job):
    task = plan["tasks"][job["task_id"]]
    info = read_json(checked_ref(task["prepared"]["%d/%d" % (job["fold"], job["seed"])]))
    if (info["task_id"], info["fold"], info["seed"]) != (job["task_id"], job["fold"], job["seed"]):
        raise ValueError("Prepared task identity differs")
    entry = info["profiles"][job["profile"]]
    layer_impl = plan.get("layer_impl", "original")
    if (layer_impl not in LAYER_IMPLEMENTATIONS
            or any(record.get("layer_impl", "original") != layer_impl
                   for record in (job, task["config"], info, entry))):
        raise ValueError("Prepared job/config layer_impl mismatch")
    return task, info, entry


def _initial(entry, info, job):
    record = torch.load(str(checked_ref(entry["initial"])), map_location="cpu")
    layer_impl = job.get("layer_impl", "original")
    if (layer_impl not in LAYER_IMPLEMENTATIONS
            or any(row.get("layer_impl", "original") != layer_impl
                   for row in (record, info, entry))):
        raise ValueError("Untrained initial layer_impl mismatch")
    if (record.get("kind") != "untrained_initial" or record.get("optimizer_steps") != 0
            or any(record.get(k) != job[k] for k in ("task_id", "fold", "seed", "profile"))
            or record.get("fit_seed") != info["seeds"]["fit"]
            or record.get("state_sha256") != entry["initial"]["state_sha256"]
            or tensor_digest(record["state_dict"]) != entry["initial"]["state_sha256"]
            or record.get("initialization_version") != INITIALIZATION_VERSION):
        raise ValueError("Untrained initial identity/digest mismatch")
    return record


class _Lock:
    def __init__(self, path):
        self.path = Path(path)
    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+")
        import fcntl
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.handle.close()
            raise RuntimeError("Another DFG v2 training worker holds the execution lock")
        return self
    def __exit__(self, *args):
        import fcntl
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()


def _move_model(model, device):
    model.to(device)
    model.symmetrical_global_graph = model.symmetrical_global_graph.to(device)
    model.supervised_node_mask = model.supervised_node_mask.to(device)
    model.device = str(device)
    return model


def _run_one(plan, job, attempt, plan_path, preflight=None):
    from .checkpoint import build_binding
    from .trainer import fit
    from .resources import Resources
    task, info, entry = _prepared(plan, job)
    config = copy.deepcopy(task["config"])
    initial = _initial(entry, info, job)
    device = config["device"]
    context = None
    if "resource_policy" in plan:
        from .preflight import initialize_context
        if device == "cpu" or preflight is None or preflight.get("status") != "passed":
            raise ValueError("Resource policy requires a passed fresh-process CUDA preflight")
        preflight_body = read_json(checked_ref(preflight["receipt_ref"]))
        if (dict(preflight_body, receipt_ref=preflight["receipt_ref"]) != preflight
                or preflight_body.get("job") != job
                or preflight_body.get("plan_sha256") != sha256(plan_path)
                or preflight_body.get("policy") != plan["resource_policy"]
                or preflight_body.get("pid") != os.getpid()
                or preflight_body.get("cuda_initialized_before") is not False
                or preflight_body.get("cuda_initialized_after") is not False):
            raise ValueError("Preflight observation differs from its sealed receipt")
    torch.set_num_threads(config.get("threads", 2))
    if device != "cpu":
        import sys, dgl, sklearn, numpy, networkx
        observed = dict(python=sys.version, torch=torch.__version__, dgl=dgl.__version__,
                        sklearn=sklearn.__version__, numpy=numpy.__version__, networkx=networkx.__version__)
        if observed != config["environment"]:
            raise ValueError("Frozen training package environment differs")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable; CPU fallback forbidden")
        if preflight is not None:
            context = initialize_context(preflight["baseline"], device)
            write_json(attempt.with_suffix(".context.json"), context)
        torch.cuda.set_device(device)
    seed_all(info["seeds"]["constructor"])
    model = make_model(task["record"]["task"], checked_ref(entry["graph"]), job["profile"], "cpu",
        hidden_size=config["hidden_size"], layers=config["layers"], heads=config["heads"], reducer=plan["reducer"],
        layer_impl=plan.get("layer_impl", "original"))
    model.load_state_dict(initial["state_dict"], strict=True)
    if tensor_digest(model.state_dict()) != entry["initial"]["state_sha256"]:
        raise ValueError("Loaded initial state differs")
    observed_support = graph_support(model.nx_graph, job["profile"], info["split"])
    if observed_support != entry["support"]:
        raise ValueError("Prepared support/schema differs")
    validate_registration(model, entry["support"]["schema"])
    if context is None:
        guard = Resources(device)
    else:
        from .preflight import make_observed_resources
        resource_options = {}
        if plan["resource_policy"]["version"] == "local_dev_v1":
            resource_options = dict(policy=plan["resource_policy"],
                                    history_path=attempt / "history.jsonl")
        guard = make_observed_resources(device, preflight["baseline"], context,
            attempt.with_suffix(".memory_samples.jsonl"),
            minimum_free_mib=plan["resource_policy"]["running_minimum_free_mib"],
            **resource_options)
    def resource_summary():
        observed = guard.summary()
        if preflight is not None:
            observed["preflight"] = preflight["receipt_ref"]
            observed["resource_policy"] = plan["resource_policy"]
            observed["training_pid"] = os.getpid()
            observed["context_ref"] = _ref(attempt.with_suffix(".context.json"))
        return observed

    try:
        with guard:
            guard.check()
            _move_model(model, device)
            guard.check()
            split = validate_parts(info["split"], task["record"]["graph_files"])
            parts = {role: DfgV2Supervision(model, task["record"]["task"], split[role]) for role in PARTS}
            labels = read_labels(task["record"]["labels"])
            binding = build_binding(model, task_id=job["task_id"], fold=job["fold"], seed=job["seed"],
                profile=job["profile"], reducer=plan["reducer"], graph_ref=entry["graph"],
                fold_ref=task["record"]["folds"], label_ref=task["record"]["labels"],
                initial_sha256=entry["initial"]["sha256"], config=config, split=info["split"],
                support=entry["support"], initialization_record=info["initialization"])
            binding["initial_state_sha256"] = entry["initial"]["state_sha256"]
            seed_all(info["seeds"]["fit"])
            result = fit(model, parts, task["record"]["task"], labels, config, attempt,
                binding, model.original_graph_node_ids, entry["support"], memory_guard=guard)
        guard.check()
    finally:
        write_json(attempt.with_suffix(".resources.json"), resource_summary())
    if result.get("status") != "complete":
        raise ValueError("Trainer did not complete")
    result["resources"] = resource_summary()
    if plan.get("resource_policy", {}).get("version") == "local_dev_v1":
        result["memory_tight"] = result["resources"]["memory_tight"]
        result["possible_memory_spill"] = result["resources"]["epoch_timing"]["possible_memory_spill"]
    write_json(attempt / "result.json", result)
    write_json(attempt / "effective_config.json", config)
    write_json(attempt / "schema_support_audit.json", entry["support"])
    write_json(attempt / "initialization_ref.json", entry["initial"])
    receipt = dict(status="complete", job=job, plan_sha256=sha256(plan_path),
        score_role=SCORE_ROLE, selection_role=SELECTION_ROLE, binding_sha256=digest(binding),
        artifacts={str(p.relative_to(attempt)): sha256(p) for p in sorted(attempt.rglob("*")) if p.is_file()})
    if plan.get("resource_policy", {}).get("version") == "local_dev_v1":
        receipt.update(memory_tight=result["memory_tight"],
                       possible_memory_spill=result["possible_memory_spill"])
    if "batch_registration" in plan:
        receipt["execution_start"] = _ref(attempt.with_suffix(".started.json"))
    write_json(attempt / "receipt.json", receipt)
    del model, parts, initial
    gc.collect()
    if device != "cpu":
        torch.cuda.empty_cache()
    return receipt


def _validate_predictions(rows, role, task, info, entry):
    """Every original identity and frozen target must occur exactly once."""
    import sco_models.graph_utils as gu
    selected = set(info["split"][role + "_files"])
    graph = read_graph(checked_ref(entry["graph"]))
    original = [n for n,d in graph.nodes(data=True) if d["node_type"] not in AUX_NODE_TYPES]
    if task["record"]["task"] == "node":
        supervised = graph.subgraph(original)
        labels = gu.get_node_label(supervised)[0]
        truth = {n:int(y) for n,y in zip(supervised, labels)}
        expected = {(graph.nodes[n]["source_file"], n): truth[n]
                    for n in original if graph.nodes[n]["source_file"] in selected}
    else:
        labels = read_labels(task["record"]["labels"])
        expected = {(f,None): labels[f] for f in selected}
    observed = {}
    original_to_model = {n:i for i,n in enumerate(graph)}
    for row in rows:
        identity = (row["file"], row.get("original_graph_node_id"))
        if identity in observed or identity not in expected or row.get("target") != expected[identity]:
            raise ValueError("Prediction original identity/target differs")
        if row.get("score_role") != role or row.get("node_type") in AUX_NODE_TYPES:
            raise ValueError("Prediction scoring role/auxiliary row differs")
        if task["record"]["task"] == "node":
            if (row.get("node_type") != graph.nodes[identity[1]]["node_type"]
                    or row.get("model_node_id") != original_to_model[identity[1]]):
                raise ValueError("Prediction original node type differs")
        for ck in ("best","last"):
            probability = row.get(ck + "_positive_probability")
            if (row.get(ck) not in (0,1) or not isinstance(probability,(int,float))
                    or not math.isfinite(probability) or not 0 <= probability <= 1):
                raise ValueError("Invalid prediction/probability")
        observed[identity] = row["target"]
    if observed != expected:
        raise ValueError("Missing original prediction identities")

def _verify_execution_authorization(attempt, plan, job, plan_path, receipt):
    """Archive-safe authorization proof; do not re-run live retry/failure gates."""
    if "batch_registration" not in plan:
        return
    from .batch import stage_jobs, validate_authorization
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
        from .resource_plan import validate_resource_result
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


def _completed(output, plan, job, plan_path):
    folder = _job_directory(output, job)
    successes = sorted(folder.glob("attempt_*/receipt.json")) if folder.exists() else []
    if len(successes) > 1:
        raise ValueError("Duplicate successful job results")
    if successes:
        result = _verify_attempt(successes[0].parent, plan, job, plan_path)
        return successes[0].parent, result
    return None


def execute(plan_path, only=None, retry=False, allow_cpu_test=False, execution_authorization=None):
    plan_path = Path(plan_path).resolve()
    output, plan = plan_path.parent, _load_plan(plan_path)
    if plan["test_mode"] and not allow_cpu_test:
        raise ValueError("Synthetic CPU execution requires explicit programmatic test allowance")
    if not plan["test_mode"] and allow_cpu_test:
        raise ValueError("Cannot run production plan as a CPU test")
    if "resource_policy" in plan and only is None:
        raise ValueError("Resource policy requires --only and one fresh process per job")
    jobs = [j for j in plan["jobs"] if only is None or job_id(j) == only]
    if not jobs:
        raise ValueError("Unknown requested job")
    authorizations = {}
    if "batch_registration" in plan:
        from .batch import authorize_job
        for job in jobs:
            authorizations[job_id(job)] = authorize_job(
                plan_path, plan, job, execution_authorization, retry=retry)
    elif execution_authorization is not None:
        raise ValueError("Execution authorization is only valid for a registered batch")
    outcomes = []
    lock = (output / ".synthetic.lock" if plan["test_mode"] else
            ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/.training.lock")
    with _Lock(lock):
        if plan.get("resource_policy", {}).get("version") == "local_dev_v1":
            # A fresh process must not silently skip a prior failed job and
            # continue the batch. Explicit retry remains whole-fit only.
            for prior in plan["jobs"]:
                folder = _job_directory(output, prior)
                started = list(folder.glob("attempt_*.started.json")) if folder.exists() else []
                if started and _completed(output, plan, prior, plan_path) is None:
                    if not (retry and job_id(prior) == only):
                        raise RuntimeError("Local batch stopped by failed/incomplete job " +
                                           job_id(prior) + "; user-confirmed explicit --retry required")
        for job in jobs:
            _load_plan(plan_path)
            existing = _completed(output, plan, job, plan_path)
            if existing:
                outcomes.append(dict(job=job, status="reused", attempt=str(existing[0])))
                continue
            folder = _job_directory(output, job)
            old = sorted(folder.glob("attempt_*.started.json")) if folder.exists() else []
            if old and not retry:
                raise RuntimeError("Previous failed/incomplete attempt retained; explicit --retry required")
            folder.mkdir(parents=True, exist_ok=True)
            preflight = None
            if "resource_policy" in plan:
                from .preflight import run_preflight
                preflight = run_preflight(job, sha256(plan_path), folder, plan["resource_policy"])
            previous_indices = [int(p.name.split(".")[0].split("_")[1]) for p in old]
            attempt = folder / ("attempt_%03d" % (max(previous_indices, default=0) + 1))
            if attempt.exists() or attempt.with_suffix(".started.json").exists():
                raise FileExistsError("Refusing to overwrite an existing attempt")
            started_record = dict(job=job, plan_sha256=sha256(plan_path),
                started_unix=time.time(), pid=os.getpid(), retry_of=[str(p) for p in old],
                resume_epoch=False, retry_from_same_untrained_initial=True)
            if authorizations:
                started_record["execution_authorization"] = authorizations[job_id(job)]
            write_json(attempt.with_suffix(".started.json"), started_record)
            try:
                if preflight is None:
                    _run_one(plan, job, attempt, plan_path)
                else:
                    _run_one(plan, job, attempt, plan_path, preflight=preflight)
                _verify_attempt(attempt, plan, job, plan_path)
            except Exception as exc:
                failure = dict(job=job, exception=repr(exc),
                               traceback=traceback.format_exc(), automatic_retry=False)
                if plan.get("resource_policy", {}).get("version") == "local_dev_v1":
                    failure.update(batch_must_stop=True, resume_epoch=False,
                        retry_requires_user_confirmation=True,
                        retry_from_same_untrained_initial=True,
                        cuda_oom=("out of memory" in str(exc).lower() and
                                  "cuda" in str(exc).lower()))
                write_json(attempt.with_suffix(".failure.json"), failure)
                raise
            outcomes.append(dict(job=job, status="complete", attempt=str(attempt)))
    return outcomes


def verify(plan_path, require_complete=True):
    plan_path = Path(plan_path).resolve()
    plan = _load_plan(plan_path)
    results, missing = {}, []
    for job in plan["jobs"]:
        completed = _completed(plan_path.parent, plan, job, plan_path)
        if completed:
            results[job_id(job)] = dict(job=job, attempt=str(completed[0]), result=completed[1])
        else:
            missing.append(job_id(job))
    if require_complete and missing:
        raise ValueError("Incomplete experiment matrix: " + ", ".join(missing))
    return dict(version=VERSION, complete=not missing, expected_jobs=len(plan["jobs"]),
                completed_jobs=len(results), missing=missing, results=results)


def _selection(plan, root):
    """Read dedicated inner scores, never result.json or outer predictions."""
    values, receipts = {}, {}
    from scripts.DFG.experiments.common import metrics
    for job in plan["jobs"]:
        folder = _job_directory(root, job)
        matches = sorted(folder.glob("attempt_*/receipt.json"))
        if len(matches) != 1:
            raise ValueError("Selection needs exactly one successful receipt per job")
        receipt = read_json(matches[0])
        if (receipt.get("status") != "complete" or receipt.get("job") != job
                or receipt.get("score_role") != SCORE_ROLE or receipt.get("selection_role") != SELECTION_ROLE
                or receipt.get("plan_sha256") != sha256(root / "plan.json")):
            raise ValueError("Selection receipt binding differs")
        path = matches[0].parent / "inner_val_predictions.json"
        checked(path, receipt["artifacts"]["inner_val_predictions.json"])
        rows = read_json(path)
        task, info, entry = _prepared(plan, job)
        _validate_predictions(rows, "inner_val", task, info, entry)
        score = metrics([r["target"] for r in rows], [r["best"] for r in rows])["buggy_f1"]
        values.setdefault(job["profile"], {}).setdefault(job["task_id"], []).append(score)
        receipts[job_id(job)] = _ref(matches[0])
    means = {p: statistics.mean([statistics.mean(scores) for scores in by_task.values()])
             for p, by_task in values.items()}
    candidates = [p for p in plan["selection_rule"]["candidates"] if p in means]
    if "G0" not in means or not candidates:
        raise ValueError("Selection needs G0 and at least one preregistered candidate")
    rank = sorted(candidates, key=lambda p: (-means[p], p))
    best = rank[0]
    tied = [p for p in rank if means[best] - means[p] < plan["selection_rule"]["tie_margin_percentage_points"]]
    relations = {}
    for p in tied:
        counts = []
        for job in plan["jobs"]:
            if job["profile"] == p:
                _, _, entry = _prepared(plan, job)
                counts.append(len(entry["support"]["schema"]["canonical_relations"]))
        relations[p] = sum(counts)
    best = min(tied, key=lambda p: (relations[p], p))
    delta = means[best] - means["G0"]
    complete_matrix = (set(candidates) == set(plan["selection_rule"]["candidates"])
        and all(len(t["folds"]) == load_folds(t["record"])["k_folds"] for t in plan["tasks"].values()))
    return dict(version=VERSION, plan_sha256=sha256(root / "plan.json"), rule=plan["selection_rule"],
        selected_profile=best, inner_val_task_equal_mean=means, selected_minus_G0=delta,
        additional_seed_condition_met=(complete_matrix and not plan["test_mode"] and
            abs(delta) >= plan["selection_rule"]["additional_seed_absolute_delta_percentage_points"]),
        complete_matrix=complete_matrix, efficacy_conclusion_allowed=complete_matrix and not plan["test_mode"],
        additional_seed_execution_authorized=False, receipts=receipts, outer_test_used=False,
        candidate_set_complete=set(candidates) == set(plan["selection_rule"]["candidates"]),
        scope="synthetic test" if plan["test_mode"] else "requested matrix; fold0 alone is not efficacy evidence")


def select(plan_path):
    plan_path = Path(plan_path).resolve()
    plan = _load_plan(plan_path)
    path = plan_path.parent / "selection.json"
    if path.exists():
        raise FileExistsError("Selection is already sealed")
    selection = _selection(plan, plan_path.parent)
    if "batch_registration" in plan:
        registered = plan["batch_registration"]["jobs"]
        if (selection.get("complete_matrix") is not True
                or selection.get("candidate_set_complete") is not True
                or selection.get("outer_test_used") is not False
                or set(selection.get("receipts", {})) != set(registered)
                or len(registered) != len(plan["jobs"])
                or registered != [job_id(job) for job in plan["jobs"]]):
            raise ValueError("Registered batch selection requires every frozen job and candidate")
    write_json(path, selection)
    write_json(path.with_name("selection.seal.json"), dict(version=VERSION,
        selection_sha256=sha256(path), plan_sha256=sha256(plan_path)))
    return selection


def summarize(plan_path):
    plan_path = Path(plan_path).resolve()
    path = plan_path.parent / "selection.json"
    if not path.exists():
        raise ValueError("Selection must be sealed before outer-test summary")
    seal = read_json(path.with_name("selection.seal.json"))
    checked(path, seal["selection_sha256"])
    if seal["plan_sha256"] != sha256(plan_path):
        raise ValueError("Selection plan differs")
    acceptance = verify(plan_path)
    selection = read_json(path)
    for ref in selection["receipts"].values():
        checked_ref(ref)
    report = dict(version=VERSION, protocol=PROTOCOL_NAME, score_role=SCORE_ROLE,
        selection_role=SELECTION_ROLE, selection_sha256=sha256(path),
        interpretation="nested outer-test results; pilot single-fold results are not efficacy conclusions",
        completed_jobs=acceptance["completed_jobs"], results=acceptance["results"])
    dest = plan_path.parent / "summary.json"
    if dest.exists():
        raise FileExistsError("Refusing existing summary")
    plan = _load_plan(plan_path)
    if "batch_registration" in plan:
        from .reporting import build_report
        report["report_artifacts"] = build_report(
            plan_path, stage="complete",
            verified_results={identity: item["result"]
                              for identity, item in acceptance["results"].items()})
        report["interpretation"] = (
            "Complete registered nested outer-test matrix; profile selection uses inner validation only")
    write_json(dest, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("plan")
    source = command.add_mutually_exclusive_group(required=True)
    source.add_argument("--store")
    source.add_argument("--from-plan", help="Reuse a sealed pilot and its exact frozen initial files")
    command.add_argument("--baseline-min-free-mib", type=float, default=None,
                         help="Fresh-process CUDA baseline; --from-plan only, default 3000")
    command.add_argument("--resource-policy", choices=("local_dev_v1",), default=None,
                         help="Approved local policy; inherited pilot or independently authorized fresh batch")
    command.add_argument("--approval-record",
                         help="Bound explicit user approval JSON; required for local_dev_v1")
    command.add_argument("--authorization-record",
                         help="New preparation-only authorization for a fresh Prompt 8 batch")
    command.add_argument("--report-spec",
                         help="Frozen Prompt 8 reporting/statistics specification")
    command.add_argument("--tasks")
    command.add_argument("--profiles", default=",".join(DEFAULT_PROFILES))
    command.add_argument("--seeds", default="1")
    command.add_argument("--folds")
    command.add_argument("--reducer", choices=("mean", "nonempty_mean"), default="mean")
    command.add_argument("--layer-impl", choices=LAYER_IMPLEMENTATIONS, default="original")
    command.add_argument("--output", required=True)
    for name in ("execute", "verify", "select", "summarize"):
        command = commands.add_parser(name)
        command.add_argument("--plan", required=True)
        if name == "execute":
            command.add_argument("--only", help="task/fold/seed/profile")
            command.add_argument("--retry", action="store_true")
            command.add_argument("--execution-authorization",
                                 help="Separate stage execution approval bound to the sealed batch")
    args = parser.parse_args(argv)
    if args.command == "plan":
        if args.from_plan:
            if (args.tasks is not None or args.folds is not None
                    or args.authorization_record is not None or args.report_spec is not None
                    or args.profiles != ",".join(DEFAULT_PROFILES) or args.seeds != "1"
                    or args.reducer != "mean" or args.layer_impl != "original"):
                raise ValueError("--from-plan preserves the source matrix/config; selector overrides forbidden")
            from .resource_plan import create_resource_plan
            extra = {}
            if args.resource_policy is not None or args.approval_record is not None:
                extra = dict(resource_policy=args.resource_policy, approval_record=args.approval_record)
            result = create_resource_plan(args.from_plan, args.output,
                baseline_minimum_free_mib=3000 if args.baseline_min_free_mib is None else args.baseline_min_free_mib,
                **extra)
        else:
            if args.resource_policy == "local_dev_v1":
                if args.baseline_min_free_mib is not None:
                    raise ValueError("Fresh local batch preserves the registered baseline threshold")
                from .batch_plan import create_batch_plan
                result = create_batch_plan(args.store, args.output, args.tasks, args.profiles,
                    args.seeds, args.folds, args.reducer, layer_impl=args.layer_impl,
                    approval_record=args.approval_record,
                    authorization_record=args.authorization_record, report_spec=args.report_spec)
            else:
                if (args.baseline_min_free_mib is not None or args.approval_record is not None
                        or args.authorization_record is not None or args.report_spec is not None):
                    raise ValueError("Resource policy, approval and --baseline-min-free-mib requires --from-plan")
                result = create_plan(args.store, args.output, args.tasks, args.profiles,
                                     args.seeds, args.folds, args.reducer, layer_impl=args.layer_impl)
        answer = dict(plan=str(Path(args.output).resolve() / "plan.json"), jobs=len(result["jobs"]))
    elif args.command == "execute":
        answer = execute(args.plan, args.only, args.retry,
                         execution_authorization=args.execution_authorization)
    elif args.command == "verify":
        result = verify(args.plan)
        answer = {k: v for k, v in result.items() if k != "results"}
    elif args.command == "select":
        answer = select(args.plan)
    else:
        result = summarize(args.plan)
        answer = dict(completed_jobs=result["completed_jobs"], score_role=SCORE_ROLE)
    print(json.dumps(answer, ensure_ascii=False, sort_keys=True), flush=True)
    return answer


if __name__ == "__main__":
    main()
