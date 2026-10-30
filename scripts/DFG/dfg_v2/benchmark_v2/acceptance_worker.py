"""Old-input acceptance worker, not a new training authorization.
Adapted experiment/run.py::_run_one SHA256 3670d4e6b7e953ec705e9863e5011b518a111bf74007be2a3a4e5833a3e5da2c.
Only trainer/checkpoint/input-guard imports select the new execution adapter.
"""
import copy, gc, os
import torch
from ..experiment.run import _prepared, _initial, _move_model, _ref
from ..experiment.support import support as graph_support
from ..experiment.protocol import PARTS, SCORE_ROLE, SELECTION_ROLE, validate_parts
from ..model import make_model, validate_registration
from ..tasks import checked_ref, read_labels
from ..supervision import DfgV2Supervision
from scripts.DFG.experiments.common import digest, seed_all, tensor_digest
from scripts.DFG.integration.io import sha256, read_json, write_json
def _run_one(plan, job, attempt, plan_path, preflight=None, optimize_validation=False):
    from ..experiment.checkpoint import build_binding
    from .trainer import fit
    from ..experiment.resources import Resources
    task, info, entry = _prepared(plan, job)
    config = copy.deepcopy(task["config"])
    initial = _initial(entry, info, job)
    device = config["device"]
    context = None
    if "resource_policy" in plan:
        from ..experiment.preflight import initialize_context
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
        from ..experiment.preflight import make_observed_resources
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
            if optimize_validation:
                from .input_guard import FitInputGuard
                with FitInputGuard(model, binding, parts, labels) as input_guard:
                    result = fit(model, input_guard.wrap_parts(), task["record"]["task"],
                        labels, config, attempt, binding, model.original_graph_node_ids,
                        entry["support"], memory_guard=guard)
                    input_guard.finish()
                    write_json(attempt / "validation_performance.json", input_guard.summary())
            else:
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


