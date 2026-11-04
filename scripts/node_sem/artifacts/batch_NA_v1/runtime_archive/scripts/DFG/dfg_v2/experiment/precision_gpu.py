"""Prompt 7b.2 GPU noise diagnostics and pilot acceptance, never efficacy claims.

Each CLI fit is a fresh process/model using the archived untrained initial state.
GPU runs require all six sealed float64 static and trajectory cases to pass.
The frozen trainer, optimizer, layers and numerical configurations are reused.
"""
import argparse
import copy
import json
import math
import sys
import traceback
from pathlib import Path

import torch

from scripts.DFG.experiments.common import digest, read_json, sha256, write_json
from scripts.DFG.dfg_v2.tasks import checked_ref
from .projection_validation import (
    CPU_CASES, _context, _fit_context, _history, compare_histories,
)

REPEATS = ("original_1", "original_2", "shared")
IMPLEMENTATIONS = dict(original_1="original", original_2="original",
                       shared="shared_projection")
CASE_FIELDS = (
    "task_id", "task", "profile", "reducer", "fold", "seed", "device", "dtype",
    "initial", "graph", "labels_ref", "folds", "archived_plan", "config", "seeds",
    "split_sha256",
)


def _ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha256(path))


def validate_cpu_acceptance(path):
    """Verify the sealed aggregate and independently recheck its raw evidence."""
    from .precision_real import (
        validate_static_evidence, validate_trajectory_evidence, _source_identity,
    )
    path = Path(path).resolve()
    schema = read_json(path).get("schema")
    if schema is not None:
        from .precision_policy import SCHEMA, validate_release
        if schema != SCHEMA:
            raise ValueError("Unknown CPU acceptance policy schema")
        return validate_release(path)
    seal = read_json(path.with_name("acceptance.seal.json"))
    reference = _ref(path)
    if seal.get("acceptance_sha256") != reference["sha256"]:
        raise ValueError("CPU acceptance seal mismatch")
    report = read_json(path)
    if report.get("status") != "accepted" or not isinstance(report.get("cases"), list):
        raise ValueError("All CPU cases must be accepted before GPU execution")
    cases = report["cases"]
    expected = set(CPU_CASES)
    identities = [(r.get("task_id"), r.get("profile"), r.get("reducer")) for r in cases]
    if len(identities) != 6 or len(set(identities)) != 6 or set(identities) != expected:
        raise ValueError("CPU acceptance requires the six distinct prescribed cases")
    sources = _source_identity()
    plans = []
    for row in cases:
        static = read_json(checked_ref(row["static"]))
        trajectory = read_json(checked_ref(row["trajectory"]))
        identity = (row["task_id"], row["profile"], row["reducer"])
        if any((r.get("task_id"), r.get("profile"), r.get("reducer")) != identity
               for r in (static, trajectory)):
            raise ValueError("CPU evidence case identity differs")
        if any(static.get(k) != trajectory.get(k) for k in CASE_FIELDS):
            raise ValueError("Static and trajectory inputs differ")
        if trajectory.get("static") != row["static"]:
            raise ValueError("Trajectory references a different static case")
        if (static.get("sources") != sources or trajectory.get("sources") != sources):
            raise ValueError("CPU diagnostic computation changed")
        validate_static_evidence(static)
        validate_trajectory_evidence(trajectory)
        for field in ("graph", "initial", "labels_ref", "folds", "archived_plan"):
            checked_ref(static[field])
        plans.append(static["archived_plan"])
    if any(value != plans[0] for value in plans):
        raise ValueError("CPU cases do not share the same frozen plan")
    checked_ref(reference)
    return report


def compute_noise(original_1, original_2, shared):
    """Use both original runs; the reference spread is not a universal bound."""
    noise = compare_histories(original_1, original_2, 0.0)
    tolerance = max(1e-4, 3.0 * noise["maximum_absolute_loss_difference"])
    first = compare_histories(original_1, shared, tolerance)
    second = compare_histories(original_2, shared, tolerance)
    passed = first["passed"] and second["passed"]
    return dict(
        status="accepted" if passed else "failed_noise_gate",
        passed=passed, original_repeat_difference=noise,
        original_repeats_loss_bitwise_equal=(
            noise["maximum_absolute_loss_difference"] == 0.0),
        shared_vs_original_1=first, shared_vs_original_2=second,
        tolerance=tolerance, rule="max(1e-4, 3 * original_repeat_maximum_loss_difference)",
        diagnostic_fits=3, not_counted_as_pilot=True,
    )


def _environment():
    import dgl
    import networkx
    import numpy
    import sklearn
    return dict(python=sys.version, torch=torch.__version__, dgl=dgl.__version__,
                sklearn=sklearn.__version__, numpy=numpy.__version__,
                networkx=networkx.__version__)


def _identity(ctx):
    return dict(task_id=ctx["task_id"], task=ctx["task"], profile=ctx["profile"],
        graph=copy.deepcopy(ctx["graph"]), initial=copy.deepcopy(ctx["initial"]),
        config=copy.deepcopy(ctx["config"]), seeds=copy.deepcopy(ctx["seeds"]),
        split=copy.deepcopy(ctx["split"]), folds=copy.deepcopy(ctx["folds"]),
        labels_ref=copy.deepcopy(ctx["labels_ref"]),
        archived_plan=copy.deepcopy(ctx["archived_plan"]), fold=0, seed=1, reducer="mean")


def _cpu_case_matches(report, ctx):
    from .precision_real import _case
    selected = [r for r in report["cases"]
                if (r["task_id"], r["profile"], r["reducer"]) ==
                   (ctx["task_id"], ctx["profile"], "mean")]
    if len(selected) != 1:
        raise ValueError("Missing matching CPU evidence for GPU noise profile")
    static = read_json(checked_ref(selected[0]["static"]))
    if any(static.get(k) != value for k, value in _case(ctx, "mean").items()):
        raise ValueError("GPU inputs differ from accepted CPU inputs")


def _resource_check(resources, resource_policy=None):
    if resource_policy is not None:
        from .preflight import validate_policy
        registered = validate_policy(resource_policy)
        if registered["version"] == "local_dev_v1":
            from .local_dev import audit_local_resources
            return audit_local_resources(resources, registered)
    if resources.get("device") != "cuda":
        raise ValueError("GPU resources must describe CUDA execution")
    for key in ("minimum_free_mib", "peak_allocated_mib", "peak_reserved_mib", "seconds"):
        value = resources.get(key)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise ValueError("Missing/nonfinite GPU resource measurement: " + key)
    if resources["minimum_free_mib"] < 100 or resources.get("memory_samples", 0) < 1:
        raise ValueError("GPU minimum-free-memory gate did not pass")
    return dict(minimum_free_mib=resources["minimum_free_mib"],
                below_300_mib_warning=resources["minimum_free_mib"] < 300)


def run_noise_fit(plan, profile, repeat, output, cpu_acceptance):
    if profile not in ("G0", "G3R") or repeat not in REPEATS:
        raise ValueError("Unknown GPU noise profile/repeat")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    record = dict(status="running", profile=profile, repeat=repeat,
        layer_impl=IMPLEMENTATIONS[repeat], device="cuda:0", dtype="float32",
        diagnostic_fits=1, not_counted_as_pilot=True,
        purpose="same frozen nested split; GPU numerical-noise diagnostic")
    write_json(output/"run.json", record)
    try:
        accepted = validate_cpu_acceptance(cpu_acceptance)
        record["cpu_acceptance"] = _ref(cpu_acceptance)
        ctx = _context(plan, "access_control_node", profile)
        _cpu_case_matches(accepted, ctx)
        record["identity"] = _identity(ctx)
        observed = _environment()
        record["environment"] = observed
        if observed != ctx["config"]["environment"]:
            raise ValueError("Frozen package environment differs")
        if torch.get_default_dtype() != torch.float32:
            raise ValueError("GPU diagnostic must use production float32 default")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA required; CPU fallback forbidden")
        from .run import _code_refs
        record["runtime"] = _code_refs()
        write_json(output/"run.json", record)
        result = _fit_context(ctx, IMPLEMENTATIONS[repeat], "mean", "cuda:0", output/"fit")
        _resource_check(result["resources"])
        if (result.get("status") != "complete" or result.get("history_rows") != 3
                or result.get("layer_impl") != IMPLEMENTATIONS[repeat]
                or result.get("initial_sha256") != ctx["initial"]["state_sha256"]):
            raise ValueError("Incomplete or misbound GPU diagnostic fit")
        if record["runtime"] != _code_refs():
            raise ValueError("Computation changed during GPU diagnostic")
        record.update(status="complete", resources=result["resources"],
            artifacts={name: _ref(output/"fit"/name)
                       for name in ("result.json", "history.jsonl", "binding.json", "model_input.json",
                                    "best.pt", "last.pt", "best.json", "last.json")})
        write_json(output/"run.json", record)
        return record
    except Exception as exc:
        record.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        write_json(output/"run.json", record)
        write_json(output/"failure.json", dict(exception=repr(exc),
            traceback=traceback.format_exc(), automatic_retry=False,
            retained_partial_outputs=True))
        raise


def _verify_checkpoint_artifacts(fit_dir, result, binding):
    """Rehash both weight files and verify their readable metadata bindings.

    The fit already performed exact model reloads. This lightweight post-fit
    check catches removed/tampered artifacts without allocating another model
    or loading optimizer tensors merely to seal the numerical diagnostic.
    """
    fit_dir = Path(fit_dir)
    expected = result.get("checkpoint_sha256", {})
    if set(expected) != {"best", "last"}:
        raise ValueError("Both best/last checkpoint digests are required")
    model_input = read_json(fit_dir/"model_input.json")
    verified = {}
    for name in ("best", "last"):
        weight = fit_dir/(name+".pt")
        if not weight.is_file() or sha256(weight) != expected[name]:
            raise ValueError("Checkpoint missing or changed: " + name)
        metadata_path = fit_dir/(name+".json")
        if not metadata_path.is_file():
            raise ValueError("Checkpoint sidecar missing: " + name)
        metadata = read_json(metadata_path)
        if (metadata.get("format") != "ddg-controlled-v1"
                or metadata.get("binding") != binding
                or metadata.get("binding_sha256") != digest(binding)
                or metadata.get("epoch") != result.get(name+"_epoch")
                or metadata.get("model_input") != model_input
                or not isinstance(metadata.get("state_sha256"), str)
                or len(metadata["state_sha256"]) != 64):
            raise ValueError("Checkpoint sidecar identity differs: " + name)
        verified[name] = dict(weights=_ref(weight), metadata=_ref(metadata_path))
    return verified

def summarize_noise(output):
    """Summarize exactly three complete diagnostic fits for one profile."""
    output = Path(output).resolve()
    destination = output/"acceptance.json"
    if destination.exists() or destination.with_name("acceptance.seal.json").exists():
        raise FileExistsError("Refusing existing GPU noise acceptance")
    records, histories = [], []
    for repeat in REPEATS:
        path = output/repeat/"run.json"
        record = read_json(path)
        if (record.get("status") != "complete" or record.get("repeat") != repeat
                or record.get("layer_impl") != IMPLEMENTATIONS[repeat]
                or record.get("profile") not in ("G0", "G3R")
                or record.get("device") != "cuda:0" or record.get("dtype") != "float32"):
            raise ValueError("GPU noise fit identity/status differs")
        checked_ref(record["cpu_acceptance"])
        _resource_check(record["resources"])
        artifacts = record["artifacts"]
        for ref in artifacts.values():
            checked_ref(ref)
        result = read_json(checked_ref(artifacts["result.json"]))
        binding = read_json(checked_ref(artifacts["binding.json"]))
        identity = record["identity"]
        if (result.get("status") != "complete" or result.get("history_rows") != 3
                or result.get("layer_impl") != record["layer_impl"]
                or result.get("initial_sha256") != identity["initial"]["state_sha256"]
                or result.get("resources") != record["resources"]
                or binding.get("layer_impl") != record["layer_impl"]):
            raise ValueError("GPU noise result/binding differs from run record")
        for key, expected in (
                ("graph", identity["graph"]), ("labels", identity["labels_ref"]),
                ("folds", identity["folds"]), ("split", identity["split"]),
                ("initial_state_sha256", identity["initial"]["state_sha256"])):
            if binding.get(key) != expected:
                raise ValueError("GPU noise frozen input binding differs: " + key)
        expected_config = copy.deepcopy(identity["config"])
        expected_config.update(maximum_training_epochs=3, device="cuda:0",
            layer_impl=record["layer_impl"], mode="projection_equivalence")
        if binding.get("effective_config_sha256") != digest(expected_config):
            raise ValueError("GPU noise effective numerical configuration differs")
        if result.get("checkpoint_roundtrip_exact") != {
                role:{ck:True for ck in ("best", "last")}
                for role in ("inner_val", "outer_test")}:
            raise ValueError("GPU diagnostic checkpoint reload failed")
        _verify_checkpoint_artifacts(Path(artifacts["result.json"]["path"]).parent, result, binding)
        records.append(record)
        histories.append(_history(checked_ref(artifacts["history.jsonl"])))
    for key in ("profile", "identity", "environment", "runtime", "cpu_acceptance"):
        if any(r.get(key) != records[0].get(key) for r in records[1:]):
            raise ValueError("GPU noise runs do not share " + key)
    result = compute_noise(*histories)
    result.update(profile=records[0]["profile"], identity=records[0]["identity"],
        cpu_acceptance=records[0]["cpu_acceptance"],
        runs={repeat:_ref(output/repeat/"run.json") for repeat in REPEATS},
        resources={r["repeat"]:r["resources"] for r in records})
    write_json(destination, result)
    write_json(destination.with_name("acceptance.seal.json"),
               dict(acceptance_sha256=sha256(destination)))
    if not result["passed"]:
        raise AssertionError("GPU shared-vs-original difference exceeds noise gate")
    return result


def audit_pilot_result(result, resource_policy=None):
    """Extra Prompt 7 acceptance; the caller still verifies the formal receipt."""
    problems = []
    try:
        resource_audit = _resource_check(result.get("resources", {}), resource_policy)
    except ValueError as exc:
        resource_audit = {}
        problems.append(str(exc))
    if result.get("status") != "complete" or result.get("layer_impl") != "shared_projection":
        problems.append("Pilot must be a complete shared_projection fit")
    if result.get("checkpoint_roundtrip_exact") != {
            role:{ck:True for ck in ("best", "last")}
            for role in ("inner_val", "outer_test")}:
        problems.append("Best/last checkpoint logits did not reload exactly")
    if result.get("outer_supervision_used_in_optimization") is not False:
        problems.append("Outer supervision must not enter optimization")
    epochs = result.get("gradient_audit", {}).get("epochs", [])
    if not epochs or epochs[0].get("epoch") != 0:
        problems.append("First-epoch gradient audit missing")
        relations = []
    else:
        relations = epochs[0].get("v2_relations", [])
    supported, heldout, zero = [], [], []
    if epochs:
        declared = epochs[0].get("v2_training_support")
        counted = sum(r.get("inner_train_edges", 0) for r in relations)
        if not isinstance(declared, int) or declared != counted:
            problems.append("First-epoch canonical support list is missing/inconsistent")
    canonicals = [tuple(r.get("canonical", [])) for r in relations]
    if len(canonicals) != len(set(canonicals)) or any(
            len(c) != 3 or not all(isinstance(v, str) and v for v in c) for c in canonicals):
        problems.append("First-epoch canonical identities are invalid or duplicated")
    for relation in relations:
        canonical = relation.get("canonical")
        value = relation.get("message_gradient_l1")
        if (not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
            problems.append("Invalid message gradient: " + str(canonical))
            continue
        if relation.get("inner_train_edges", 0):
            supported.append(canonical)
            if value <= 0:
                zero.append(canonical)
        else:
            heldout.append(canonical)
            if value != 0:
                problems.append("Heldout-only relation has supervised gradient: " + str(canonical))
    if zero:
        problems.append("Training-supported relation has zero first-epoch message gradient")
    return dict(passed=not problems, problems=problems,
        training_supported_canonical_count=len(supported),
        heldout_only_canonical_count=len(heldout),
        supported_zero_message_gradients=zero,
        heldout_only_canonicals=heldout, resources=resource_audit,
        formal_prediction_and_env_exclusion_verification_required=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fit_parser = commands.add_parser("noise-fit")
    fit_parser.add_argument("--plan", required=True)
    fit_parser.add_argument("--profile", choices=("G0", "G3R"), required=True)
    fit_parser.add_argument("--repeat", choices=REPEATS, required=True)
    fit_parser.add_argument("--output", required=True)
    fit_parser.add_argument("--cpu-acceptance", required=True)
    summary_parser = commands.add_parser("noise-summary")
    summary_parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "noise-fit":
        result = run_noise_fit(args.plan, args.profile, args.repeat, args.output, args.cpu_acceptance)
    else:
        result = summarize_noise(args.output)
    print(json.dumps({k:result[k] for k in ("status", "profile")}), flush=True)


if __name__ == "__main__":
    main()
