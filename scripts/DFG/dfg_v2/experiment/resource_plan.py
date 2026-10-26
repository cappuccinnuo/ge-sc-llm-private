"""New resource-only plans referencing historical frozen inputs and initial states.

No model construction or initialization is performed here. Historical seals are
read-only; only the explicitly listed orchestration files may differ.
"""
import copy
import json
import math
from pathlib import Path

from scripts.DFG.integration.io import checked, read_json, sha256, write_json
from .preflight import DEFAULT_PREFLIGHT_POLICY, validate_policy

ALLOWED_RUNTIME_CHANGES = {
    "scripts/DFG/dfg_v2/experiment/run.py",
    "scripts/DFG/dfg_v2/experiment/preflight.py",
    "scripts/DFG/dfg_v2/experiment/resource_plan.py",
}
ALLOWED_PLAN_CHANGES = {"runtime", "git_head", "resource_policy", "resource_origin"}
ORIGIN_VERSION = "prompt7b4-resource-only-plan-v1"


def _ref(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha256(path)}


def runtime_difference(before, after):
    deleted = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    if deleted or set(changed) - ALLOWED_RUNTIME_CHANGES:
        raise ValueError("Frozen computation changed beyond approved resource integration: " +
                         repr({"deleted": deleted, "changed": changed}))
    return {k: {"before": before.get(k), "after": after.get(k)} for k in changed}


def _source(origin):
    from . import run
    if origin.get("version") != ORIGIN_VERSION:
        raise ValueError("Unknown resource plan origin")
    source_path = checked(origin["plan"]["path"], origin["plan"]["sha256"])
    seal_path = checked(origin["seal"]["path"], origin["seal"]["sha256"])
    if seal_path != source_path.with_name("plan.seal.json"):
        raise ValueError("Resource origin seal identity mismatch")
    source = run._load_plan(source_path, check_code=False)
    if "resource_policy" in source or "resource_origin" in source:
        raise ValueError("Resource-only plan must reference the original sealed pilot")
    return source


def validate_resource_origin(plan):
    """Compare every frozen source field, including exact prepared file refs."""
    origin = plan.get("resource_origin", {})
    source = _source(origin)
    if plan.get("test_mode") or source.get("test_mode"):
        raise ValueError("Resource policy plans require a production CUDA pilot")
    changed = sorted(k for k in set(source) | set(plan) if source.get(k) != plan.get(k))
    if set(changed) - ALLOWED_PLAN_CHANGES:
        raise ValueError("Resource-only plan changed frozen experimental fields")
    runtime = runtime_difference(source["runtime"], plan["runtime"])
    comparison = read_json(checked(origin["comparison"]["path"], origin["comparison"]["sha256"]))
    if (comparison.get("version") != ORIGIN_VERSION
            or comparison.get("source_plan") != origin["plan"]
            or comparison.get("changed_top_level_fields") != changed
            or comparison.get("runtime_changes") != runtime
            or comparison.get("frozen_fields_identical") is not True
            or comparison.get("untrained_initials_reused") is not True):
        raise ValueError("Resource plan comparison record differs")
    return comparison


def create_resource_plan(source_plan, output, baseline_minimum_free_mib=3000):
    """Seal a new batch while referencing exact existing prepared/initial bytes."""
    from . import run
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing resource experiment directory: " + str(output))
    policy = copy.deepcopy(DEFAULT_PREFLIGHT_POLICY)
    policy["baseline_minimum_free_mib"] = baseline_minimum_free_mib
    validate_policy(policy)
    source_plan = Path(source_plan).resolve()
    source = run._load_plan(source_plan, check_code=False)
    if source.get("test_mode") or "resource_policy" in source or "resource_origin" in source:
        raise ValueError("Resource plan source must be an original production pilot")
    if source.get("layer_impl") != "shared_projection":
        raise ValueError("Prompt 7b.4 requires the validated shared_projection pilot")
    runtime = run._code_refs()
    difference = runtime_difference(source["runtime"], runtime)
    initial_audit = []
    for job in source["jobs"]:
        task, info, entry = run._prepared(source, job)
        initial = run._initial(entry, info, job)
        initial_audit.append({"job": job, "initial": entry["initial"],
                              "optimizer_steps": initial["optimizer_steps"],
                              "fit_seed": initial["fit_seed"],
                              "state_sha256": initial["state_sha256"]})
        del initial
    plan = copy.deepcopy(source)
    plan["runtime"] = runtime
    plan["git_head"] = run._git_head()
    plan["resource_policy"] = policy
    origin = {"version": ORIGIN_VERSION, "plan": _ref(source_plan),
              "seal": _ref(source_plan.with_name("plan.seal.json"))}
    plan["resource_origin"] = origin
    changed = sorted(k for k in set(source) | set(plan) if source.get(k) != plan.get(k))
    if set(changed) - ALLOWED_PLAN_CHANGES:
        raise AssertionError("Unexpected resource plan field change")
    output.mkdir(parents=True)
    comparison_path = output / "source_plan_comparison.json"
    write_json(comparison_path, {
        "version": ORIGIN_VERSION, "source_plan": origin["plan"],
        "changed_top_level_fields": changed, "runtime_changes": difference,
        "frozen_fields_identical": True, "untrained_initials_reused": True,
        "initials": initial_audit,
        "note": "Prepared/input/initial references and all numerical configuration remain exact. "
                "Only resource orchestration, Git provenance and new plan provenance differ.",
    })
    origin["comparison"] = _ref(comparison_path)
    path = output / "plan.json"
    write_json(path, plan)
    write_json(output / "plan.seal.json", {
        "version": run.VERSION, "plan_sha256": sha256(path),
        "jobs": len(plan["jobs"]), "protocol_version": run.PROTOCOL_VERSION,
        "test_mode": False,
    })
    if run._code_refs() != runtime:
        raise ValueError("Runtime changed while sealing resource plan")
    run._load_plan(path)
    return plan


def validate_resource_result(result, plan, job, plan_path):
    """Bind a successful fit to its fresh-process, resource-only start receipt."""
    resources = result.get("resources", {})
    if resources.get("resource_policy") != plan["resource_policy"]:
        raise ValueError("Result resource policy differs")
    ref = resources.get("preflight", {})
    preflight = read_json(checked(ref.get("path", ""), ref.get("sha256")))
    if (preflight.get("status") != "passed" or preflight.get("job") != job
            or preflight.get("plan_sha256") != sha256(plan_path)
            or preflight.get("policy") != plan["resource_policy"]
            or preflight.get("cuda_initialized_before") is not False
            or preflight.get("cuda_initialized_after") is not False
            or preflight.get("process_scope") != "fresh_process_one_job"
            or type(preflight.get("pid")) is not int or preflight["pid"] <= 0
            or resources.get("training_pid") != preflight["pid"]):
        raise ValueError("Preflight receipt does not match the successful fit")
    if (resources.get("baseline") != preflight.get("baseline")
            or preflight["baseline"]["free_mib"] < plan["resource_policy"]["baseline_minimum_free_mib"]):
        raise ValueError("Result baseline differs from passed preflight")
    raw_path = checked(resources.get("raw_samples_path", ""), resources.get("raw_samples_sha256"))
    context_ref = resources.get("context_ref", {})
    context = read_json(checked(context_ref.get("path", ""), context_ref.get("sha256")))
    if (context != resources.get("context_observation")
            or context.get("baseline") != preflight["baseline"]):
        raise ValueError("Result context observation differs from original record")

    after = context["after_initialization"]
    baseline = preflight["baseline"]
    if (after.get("uuid") != baseline["uuid"] or after.get("total_mib") != baseline["total_mib"]
            or context["free_decrease_mib"] != baseline["free_mib"]-after["free_mib"]
            or context["used_increase_mib"] != after["used_mib"]-baseline["used_mib"]):
        raise ValueError("Context measurement identity/difference differs")
    samples = [json.loads(line) for line in raw_path.read_text().splitlines()]
    if (not samples or len(samples) != resources.get("paired_sample_count")
            or len(samples) != resources.get("memory_samples")
            or [row.get("index") for row in samples] != list(range(len(samples)))):
        raise ValueError("Raw resource sample count/index differs")
    for row in samples:
        if (row.get("uuid") != baseline["uuid"] or row.get("total_mib") != baseline["total_mib"]
                or any(not isinstance(row.get(key), (int, float)) or not math.isfinite(row[key])
                       for key in ("free_mib", "used_mib", "torch_allocated_mib", "torch_reserved_mib"))
                or any(row[key] < 0 or row[key] > baseline["total_mib"]
                       for key in ("free_mib", "used_mib", "torch_allocated_mib", "torch_reserved_mib"))):
            raise ValueError("Raw resource sample identity/readings differ")
        residual = row["total_mib"]-row["free_mib"]-row["torch_reserved_mib"]
        if (row.get("non_torch_residual_estimate_mib") != residual
                or row.get("context_adjusted_residual_estimate_mib") != residual-context["free_decrease_mib"]):
            raise ValueError("Raw resource residual calculation differs")
    minimum = min(row["free_mib"] for row in samples)
    if (resources.get("minimum_free_mib") != minimum
            or minimum < plan["resource_policy"]["running_minimum_free_mib"]
            or resources.get("total_mib") != baseline["total_mib"]
            or resources["peak_allocated_mib"] < max(row["torch_allocated_mib"] for row in samples)
            or resources["peak_reserved_mib"] < max(row["torch_reserved_mib"] for row in samples)):
        raise ValueError("Resource gate/minimum/peak summary differs")
    residual = baseline["total_mib"]-minimum-resources["peak_reserved_mib"]
    if (resources.get("non_torch_residual_estimate_mib") != residual
            or resources.get("context_adjusted_residual_estimate_mib") != residual-context["free_decrease_mib"]):
        raise ValueError("Resource residual summary differs")
