"""N-A original-view plan contract. No training, optimization or GPU work here.

Uses existing NodeSem feature/initialization validation and frozen 8H inputs.
The legacy S0/S1 executor remains untouched. NS-P5A must bind its actual worker
code separately if it differs from this preparation-time runtime; never reseal
this plan or silently use the old anonymous-only executor.
"""
from pathlib import Path

import torch
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.benchmark_v2.protocol import (
    PROTOCOL_NAME, PROTOCOL_VERSION, SCORE_ROLE, SELECTION_ROLE, FORWARD_SCOPE,
    validate_parts,
)
from scripts.DFG.dfg_v2.experiment.init import parameter_seed, seeds
from scripts.DFG.experiments.common import digest, tensor_digest
from .execution import runtime_refs, ROOT, _validate_carrier
from .feature_spec import FeatureSpec
from .init import checked_initial
from .adapter import NodeSemAdapter

VERSION = "nodesem-na-plan-v1"
NAMES = ("S0o", "S1o", "S2", "S4")
PROFILES = ("G0", "G3R")
TASK_FOLDS = (("reentrancy_contract", 5), ("access_control_contract", 5),
              ("reentrancy_node", 10), ("access_control_node", 10))
ARTIFACTS = ROOT / "scripts/node_sem/artifacts"
DEFAULT = ARTIFACTS / "batch_NA_v1"
PLAN_MODULES = ("batch_na.py", "p5_prepare.py")


def runtime():
    result = runtime_refs()
    for name in PLAN_MODULES:
        p = ROOT / "scripts/node_sem" / name
        result[str(p.relative_to(ROOT))] = ref(p)["sha256"]
    return result


def key(job):
    return (job["task_id"], job["fold"], job["seed"], job["profile"], job["name"])


def matrix():
    return [dict(task_id=t, granularity=t.rsplit("_", 1)[-1], fold=f, seed=1,
                 profile=p, name=n)
            for t, folds in TASK_FOLDS for f in range(folds)
            for p in PROFILES for n in NAMES]


def validate_matrix(jobs):
    if (len(jobs) != 240 or len({key(j) for j in jobs}) != 240
            or {key(j) for j in jobs} != {key(j) for j in matrix()}):
        raise ValueError("N-A requires all 240 original-view jobs exactly once")
    for j in jobs:
        if type(j["fold"]) is not int or type(j["seed"]) is not int:
            raise ValueError("Fold and seed must be integer identities")
        if j["granularity"] != j["task_id"].rsplit("_", 1)[-1]:
            raise ValueError("Task granularity differs")
        if j.get("reuse_8h") is not False or j.get("view") != "original":
            raise ValueError("Historical anonymous scores cannot be reused as N-A baselines")
    return True


def statistics_spec():
    return dict(
        primary=dict(task_id="reentrancy_node", profile="G3R", comparison=["S4", "S0o"],
                     label_policy="L-audit", checkpoint="best", score_role=SCORE_ROLE,
                     metric="buggy_f1", pairs="10 frozen folds, seed 1"),
        holm_family=[["S4", "S0o"], ["S1o", "S0o"], ["S2", "S0o"], ["S4", "S2"]],
        wilcoxon=dict(alternative="two-sided", zero_method="zsplit", correction=False,
                      mode="auto", all_zero_p=1.0, warnings="retain verbatim"),
        uncertainty="folds share training data; no independent-seed or node-level replication claim",
        other_tasks="descriptive_only", metric_units="percent", difference_units="percentage_points",
        interaction=dict(expression="(S4-S0o)_G3R - (S4-S0o)_G0", inferential=False,
            interpretation="feature-by-graph interaction, not pure dependence-semantic causality; schemas and parameters differ"),
        s_star=dict(candidates=["S1o", "S2", "S4"], profile="G3R", role=SELECTION_ROLE,
            checkpoint="strict minimum inner_val loss checkpoint", metric="buggy_f1",
            aggregation="equal mean over folds per task, then equal mean of four tasks",
            tie_break="smaller carrier dimension; then lexicographic name if still tied",
            outer_test_used=False, interpretation="reference only; never replace preregistered S4"),
        strata=dict(membership="basename(file).startswith('buggy_')", membership_uses_labels=False,
            aggregate="pooled counts reported separately from equal-fold means",
            metrics=["buggy_f1", "precision", "recall", "TP", "FP", "FN", "TN"],
            wilson95=["precision TP/(TP+FP)", "recall TP/(TP+FN)"],
            bf1_interval=None, zero_denominator="undefined/null interval; preserve frozen metric convention",
            interpretation="filename provenance proxy; dependent nodes; intervals descriptive only"),
        special_tables=dict(reentrancy_node="all included non-SolidiFI positives and all non-SolidiFI false positives",
            access_control_node="all included non-SolidiFI positives",
            expected_positive_counts=dict(reentrancy_node=32, access_control_node=20),
            counts="derive from frozen L-audit; audit discrepancy, never drop rows to match expectation"),
        required_reports=["best and last separately", "original labels on all original HCG nodes",
            "per-fold errors FP+FN", "relative error reduction 1-err(S4)/err(S0o), null if baseline errors=0",
            "equal-fold means and sample SD", "pooled OOF separately", "prediction changes by identity",
            "keyword baseline as external reference", "anonymous 8H historical reference only, never paired",
            "first-layer eval attention distribution", "applicable gate distributions",
            "actual device and TF32", "parameters, relation support, memory and elapsed time"],
        score_interpretation="nested group-disjoint outer folds; full fixed graph transductive forward; no independent external-test claim",
        main_view="original", masked_ctx="not in N-A; S4m preregistered in later N-B, CODE stays original",
        label_caveat="L-audit diagnostic view is not a proven gold standard")


def validate_device_comparisons(jobs, records=None):
    """Every task is a comparison family including both graph profiles/all folds."""
    expected = {key(j): j for j in jobs}
    policy = {}
    for j in jobs:
        d = j["device_policy"]
        if (d.get("location") not in ("local_RTX3050", "server") or d.get("device_type") != "cuda"
                or not all(d.get(k) for k in ("gpu_model", "torch_version", "cuda_build_version")) or set(d.get("allow_tf32", {})) != {"matmul", "cudnn"}
                or any(type(v) is not bool for v in d["allow_tf32"].values())):
            raise ValueError("Explicit device type/model/TF32 policy required")
        identity = (d["location"], d["device_type"], d["gpu_model"], d["allow_tf32"]["matmul"], d["allow_tf32"]["cudnn"], d["torch_version"], d["cuda_build_version"])
        previous = policy.setdefault(j["task_id"], identity)
        if previous != identity:
            raise ValueError("Mixed device or TF32 within comparison family")
    if records is not None:
        if len(records) != len(expected) or {key(r) for r in records} != set(expected):
            raise ValueError("Missing/duplicate/unexpected result identities")
        for r in records:
            if r.get("actual_device") != expected[key(r)]["device_policy"]:
                raise ValueError("Receipt device/TF32 differs from planned comparison")
    return True


def dropout_identity(model, job, spec):
    return dict(fit_seed=job["seeds"]["fit"], task_id=job["task_id"], fold=job["fold"],
        profile=job["profile"], spec_digest=spec.digest(), probability=spec.modality_dropout,
        seeds={a.ntype: parameter_seed(job["seeds"]["fit"], "modality_dropout",
               [job["task_id"], job["fold"], job["profile"], spec.digest(), a.ntype])
               for a in model.adapt_ws if isinstance(a, NodeSemAdapter)},
        reset="immediately before each fresh fit, counters zero; eval does not advance",
        cuda_determinism="EmbeddingBag/scatter backward atomic additions may be nondeterministic")


def validate_initial(job, spec):
    p = checked_initial(job["initial"], job["task_id"], job["fold"], job["profile"], spec_digest=spec.digest())
    old = checked_initial(job["h8_initial"], job["task_id"], job["fold"], job["profile"])
    if (p.get("source") != job["h8_initial"] or p.get("formal_training") is not False
            or p.get("optimizer_steps") != 0):
        raise ValueError("Initial source/zero-step provenance differs")
    selected = set(p["state_dict"]) if spec.token_mode == "raw_linear" else {
        k for k in p["state_dict"] if k.startswith(("gcs.", "classify."))}
    want = set(old["state_dict"]) if spec.token_mode == "raw_linear" else {
        k for k in old["state_dict"] if k.startswith(("gcs.", "classify."))}
    if selected != want or any(not torch.equal(p["state_dict"][k], old["state_dict"][k]) for k in selected):
        raise ValueError("Historical common initialization differs")
    return dict(passed=True,all_parameters_exact=spec.token_mode == "raw_linear",
                common_parameter_keys=len(selected),state_sha256=tensor_digest(p["state_dict"]))


def checked_tree(value, seen=None):
    """Hash all referenced files once per verification; no persistent cache."""
    seen = set() if seen is None else seen
    if isinstance(value, dict):
        if "path" in value and "sha256" in value:
            pair = (value["path"], value["sha256"])
            if pair not in seen:
                checked(value); seen.add(pair)
        for v in value.values():
            checked_tree(v, seen)
    elif isinstance(value, list):
        for v in value:
            checked_tree(v, seen)
    return seen


def _historical_table(source):
    result = {}
    for t, n in TASK_FOLDS:
        for f in range(n):
            for p in PROFILES:
                j = dict(task_id=t, fold=f, seed=1, profile=p)
                result[(t, f, p)] = h8.prepared(source, j)
    return result


def validate_job(job, sources, feature_tasks, tokens, base, deep=False, seen=None):
    checked_tree(job, seen)
    spec = FeatureSpec.from_json(read(checked(job["spec"])))
    template = read(checked(job["config_template"]))
    for m in template["modalities"]:
        name = m["name"]
        m["manifest"] = (tokens[job["task_id"]]["original"] if name == "token_ids"
                         else feature_tasks[job["task_id"]]["ctx"]["original"] if name == "ctx"
                         else feature_tasks[job["task_id"]][name])
    if (spec.to_json() != template or spec.digest() != job["spec_sha256"]
            or spec.name != job["name"] or spec.view != "original" or spec.layers is not None):
        raise ValueError("Original feature specification differs")
    task, info, entry = sources[(job["task_id"], job["fold"], job["profile"])]
    expected = dict(graph=entry["graph"], h8_initial=entry["initial"],
        labels=task["record"]["labels"], folds=task["record"]["folds"], label_view=task["label_view"],
        config=task["config"], split=info["split"], graph_files=task["record"]["graph_files"],
        initialization=info["initialization"], seeds=info["seeds"], support=entry["support"])
    if any(job.get(k) != v for k, v in expected.items()):
        raise ValueError("Frozen task/config/schema/support/initial identity differs")
    if job["seeds"] != seeds(job["granularity"], job["fold"], 1):
        raise ValueError("Random seeds differ")
    validate_parts(job["split"], job["graph_files"])
    for name in ("initial", "feature_view", "feature_npz", "spec"):
        if Path(base).resolve() not in Path(checked(job[name])).resolve().parents:
            raise ValueError("N-A generated input is outside this exclusive batch")
    carrier = read(checked(job["feature_view"]))
    if (carrier.get("data") != job["feature_npz"] or carrier.get("spec_sha256") != spec.digest()
            or carrier.get("view") != "original" or carrier.get("task_id") != job["task_id"]
            or carrier.get("spec") != spec.to_json()
            or carrier.get("original_inputs_unchanged") is not True
            or carrier.get("original_graph_fingerprint") != job["original_graph_fingerprint"]
            or carrier.get("feature_shape") != [job["node_count"], spec.carrier_dim()]):
        raise ValueError("Carrier input binding differs")
    evidence = read(checked(job["preparation_evidence"]))
    if (evidence.get("initial") != job["initial"] or evidence.get("identity") != list(key(job))
            or evidence.get("cpu_loaded_digest_exact") is not True
            or evidence.get("common_initial_exact") is not True
            or evidence.get("dropout") != job["dropout"]):
        raise ValueError("Preparation evidence differs")
    d = job["dropout"]
    if job["registered_node_types"] != [r["name"] for r in entry["support"]["schema"]["node_types"]]:
        raise ValueError("Registered node-type identities differ")
    expected_seeds = {ntype: parameter_seed(job["seeds"]["fit"], "modality_dropout",
         [job["task_id"], job["fold"], job["profile"], spec.digest(), ntype])
         for ntype in job["registered_node_types"]} if spec.name != "S0o" else {}
    if (d.get("seeds") != expected_seeds or d.get("fit_seed") != job["seeds"]["fit"]
            or d.get("task_id") != job["task_id"] or d.get("fold") != job["fold"]
            or d.get("profile") != job["profile"] or d.get("spec_digest") != spec.digest()
            or d.get("probability") != spec.modality_dropout):
        raise ValueError("Dropout seed identity differs")
    if deep:
        return validate_initial(job, spec)
    return dict(passed=True)


def validate_envelope(plan, seal, reference):
    if (plan.get("version") != VERSION or seal.get("version") != VERSION or seal.get("plan") != reference
            or seal.get("matrix_sha256") != digest(plan["jobs"]) or seal.get("jobs") != 240):
        raise ValueError("N-A plan/seal differs")
    if (plan.get("view") != "original" or plan.get("label_policy") != "L-audit"
            or plan.get("protocol") != PROTOCOL_NAME or plan.get("protocol_version") != PROTOCOL_VERSION
            or plan.get("statistics") != statistics_spec() or plan.get("execution_authorized") is not False
            or plan.get("source_preparation") is None):
        raise ValueError("N-A protocol/endpoint/authorization differs")
    validate_matrix(plan["jobs"]); validate_device_comparisons(plan["jobs"])
    families = {j["task_id"]: j["device_policy"] for j in plan["jobs"]}
    if plan.get("device_families") != families:
        raise ValueError("Device-family declaration differs from jobs")
    return True


def validate_execution_runtime(plan):
    if plan["runtime"] != runtime():
        raise ValueError("N-A runtime differs; explicit execution revision required")
    return True


def load(path, mode="verify", deep=False):
    if mode not in ("verify", "launch"):
        raise ValueError("Invalid verification mode")
    path = Path(path)
    plan = read(path); seal = read(path.with_name("plan.seal.json"))
    validate_envelope(plan, seal, ref(path))
    if mode == "launch":
        validate_execution_runtime(plan)
    seen = checked_tree(plan)
    for archived in plan["runtime_archive"].values():
        checked(archived)
    if {k: v["sha256"] for k, v in plan["runtime_archive"].items()} != plan["runtime"]:
        raise ValueError("Archived runtime does not match seal")
    source = h8.load(checked(plan["source_h8_plan"]))
    if source["source_preparation"] != plan["source_preparation"]:
        raise ValueError("Historical source preparation differs")
    current = read(checked(plan["feature_source"]))
    accepted = read(checked(current["validation"]))
    if (read(checked(current["seal"]))["validation"] != current["validation"]
            or not accepted["passed"] or accepted["static_dimension"] != 245):
        raise ValueError("Accepted modalities gate differs")
    source_prep = read(checked(plan["source_preparation"]))
    tokens = read(checked(source_prep["bound_artifacts"]["feature_views"]))["task_views"]
    table = _historical_table(source)
    modality_refs = {}
    for j in plan["jobs"]:
        for m in read(checked(j["spec"]))["modalities"]:
            modality_refs[(m["manifest"]["path"], m["manifest"]["sha256"])] = m["manifest"]
    for reference in modality_refs.values():
        view = read(checked(reference))
        checked_tree(view, seen)
    if deep:
        from .carrier import load_modality
        for reference in modality_refs.values():
            load_modality(reference)
    for j in plan["jobs"]:
        if j.get("source_preparation") != plan["source_preparation"]:
            raise ValueError("Job source preparation differs")
        validate_job(j, table, accepted["tasks"], tokens, path.parent, deep=deep, seen=seen)
    auth = read(checked(plan["authorization_template"]))
    if (auth.get("execution_authorized") is not False or auth.get("matrix_sha256") != digest(plan["jobs"])
            or auth.get("jobs") != 240 or auth.get("view") != "original"
            or auth.get("seeds") != [1] or auth.get("label_policy") != "L-audit"):
        raise ValueError("Non-authorized execution template differs")
    return plan


def require_launch_authorization(path, authorization_ref=None):
    plan = load(path, mode="launch")
    if authorization_ref is None:
        raise PermissionError("N-A training is not authorized; NS-P5 is preparation only")
    authorization = read(checked(authorization_ref))
    if (authorization.get("execution_authorized") is not True
            or not authorization.get("user_request") or authorization.get("plan") != ref(path)
            or authorization.get("matrix_sha256") != digest(plan["jobs"])
            or authorization.get("device_families") != plan["device_families"]):
        raise PermissionError("A separately sealed explicit batch approval is required")
    raise PermissionError("NS-P5 contains no training worker; use reviewed NS-P5A execution binding")
