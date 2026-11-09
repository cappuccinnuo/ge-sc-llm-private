"""NS-P8a N-C1 plan admission; no training and no mutation of historical batches."""
import math
from pathlib import Path
import torch
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref
from scripts.DFG.dfg_v2.benchmark_v2.protocol import PROTOCOL_NAME, PROTOCOL_VERSION, validate_parts
from scripts.DFG.dfg_v2.experiment.preflight import LOCAL_DEV_POLICY
from scripts.DFG.experiments.common import digest, tensor_digest
from . import batch_na as na
from .feature_spec import FeatureSpec
from .init import checked_initial
from .nc1_init import baseline_state, VERSION as INIT_VERSION
from .nc1_history import verify_index

ROOT = na.ROOT
DEFAULT = na.ARTIFACTS / "batch_NC1_v1"
VERSION = "nodesem-nc1-plan-v1"
TASK_FOLDS = (("reentrancy_node", 10), ("access_control_node", 10),
              ("access_control_contract", 5), ("reentrancy_contract", 5))
MODULES = ("batch_nc1.py", "nc1_init.py", "nc1_history.py", "p8a_prepare.py",
           "batch_nc1_worker.py", "batch_nc1_controller.py", "batch_na_worker.py",
           "batch_na_controller.py", "na_carrier.py", "nb_finalize.py", "p6_prepare.py")


def runtime():
    result = na.runtime()
    for name in MODULES:
        p = ROOT / "scripts/node_sem" / name
        result[str(p.relative_to(ROOT))] = ref(p)["sha256"]
    return result


def key(job):
    return na.key(job)


def matrix():
    return [dict(task_id=t, granularity=t.rsplit("_", 1)[-1], fold=f, seed=1,
                 profile="G3R", name="S6", view="original", reuse_8h=False)
            for t, n in TASK_FOLDS for f in range(n)]


def validate_matrix(jobs):
    if len(jobs) != 30 or [key(j) for j in jobs] != [key(j) for j in matrix()]:
        raise ValueError("N-C1 needs exactly 30 ordered S6/G3R jobs")
    for j in jobs:
        if (type(j["fold"]) is not int or type(j["seed"]) is not int
                or j.get("view") != "original" or j.get("reuse_8h") is not False
                or j["granularity"] != j["task_id"].rsplit("_", 1)[-1]):
            raise ValueError("Wrong N-C1 identity")


def statistics_spec():
    from scripts.DFG.dfg_v2.experiment.stats import specification
    return dict(primary=dict(task_id="reentrancy_node", profile="G3R", comparison=["S6", "S4"],
        label_policy="L-audit", checkpoint="best", score_role="outer_test", metric="buggy_f1",
        folds=10, wilcoxon=specification()["node_wilcoxon"], number_of_tests=1),
        descriptive=dict(tasks=[t for t, _ in TASK_FOLDS], checkpoints=["best", "last"],
            aggregate="equal-fold mean and sample SD; tasks separate",
            strata=["SolidiFI", "non-SolidiFI"], pooled=["TP", "FP", "FN", "buggy_f1"],
            non_solidiFI_positive_rows=dict(reentrancy_node=32, access_control_node=20),
            positive_comparison="S4/S6 probability by source SHA, file and original node identity"),
        continuation=dict(task_id="reentrancy_node", checkpoint="best", label_policy="L-audit",
            inputs=["fold_mean_BF1_delta", "non_solidiFI_pooled_BF1_delta"], operator="either strictly > 0",
            missing="not evaluable; never treat missing as zero",
            interpretation="resource decision only; does not prove a student cannot improve",
            execution="NS-P8b requires a separate sealed plan and user authorization"),
        limitations=["CV folds share training data; not independent seeds",
            "outer results guide this exploratory continuation decision, not independent confirmation",
            "same common initial tensors; modality-dropout streams depend on S6 spec and differ from S4",
            "teacher inference is an empirical reference, not a mathematical upper bound"])


def continuation(fold_mean_BF1_delta, non_solidiFI_pooled_BF1_delta):
    values = (fold_mean_BF1_delta, non_solidiFI_pooled_BF1_delta)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError("Both preregistered deltas must be finite")
    return dict(continue_student=any(v > 0 for v in values),
                fold_mean_BF1_delta=values[0], non_solidiFI_pooled_BF1_delta=values[1],
                automatic_execution=False)


def execution_order(jobs):
    validate_matrix(jobs)
    from .batch_na_worker import job_id
    return [job_id(j) for j in jobs]


def validate_device_comparisons(jobs, records=None):
    na.validate_device_comparisons(jobs, records)


def make_spec(s4, teacher):
    if s4.name != "S4" or s4.view != "original" or s4.fusion != "concat":
        raise ValueError("Expected original concat S4")
    value = s4.to_json(); value["name"] = "S6"
    value["modalities"].append(dict(name="teacher", dim=384, normalize=True, manifest=teacher))
    return FeatureSpec.from_json(value)


def validate_envelope(plan, seal, reference):
    if (plan.get("version") != VERSION or seal.get("version") != VERSION
            or seal.get("plan") != reference or seal.get("jobs") != 30
            or seal.get("matrix_sha256") != digest(plan["jobs"])):
        raise ValueError("N-C1 plan/seal differs")
    if (plan.get("execution_authorized") is not False or plan.get("view") != "original"
            or plan.get("label_policy") != "L-audit" or plan.get("protocol") != PROTOCOL_NAME
            or plan.get("protocol_version") != PROTOCOL_VERSION
            or plan.get("statistics") != statistics_spec()
            or plan.get("resource_policy") != LOCAL_DEV_POLICY or plan.get("initialization_version") != INIT_VERSION):
        raise ValueError("N-C1 protocol, statistics or authorization differs")
    validate_matrix(plan["jobs"]); validate_device_comparisons(plan["jobs"])
    if plan["device_families"] != {j["task_id"]:j["device_policy"] for j in plan["jobs"]}:
        raise ValueError("Device family differs")
    return True


def load(path, mode="verify", deep=False):
    if mode not in ("verify", "launch"): raise ValueError("Unknown mode")
    path = Path(path); plan = read(path)
    validate_envelope(plan, read(path.with_name("plan.seal.json")), ref(path))
    for name, value in plan["runtime"].items():
        checked(dict(path=str(ROOT / name), sha256=value))
        if plan["runtime_archive"][name]["sha256"] != value:
            raise ValueError("Runtime archive differs")
        checked(plan["runtime_archive"][name])
    parents = verify_index(plan["na_result_index"])
    checked(plan["teacher_index"]); teacher = read(checked(plan["teacher_index"]))["tasks"]
    for k in ("decisions", "prompt", "experiment_policy", "preparation_audit", "resource_estimate", "power_check"):
        checked(plan[k])
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load as load_h8
    historical = load_h8(checked(plan["source_h8_plan"]))
    if historical["source_preparation"] != plan["source_preparation"]:
        raise ValueError("8H source preparation differs")
    seen = set()
    for j in plan["jobs"]:
        baseline_id = j["baseline_job_id"]
        row = parents[baseline_id]; old = row["job"]
        for k in ("config", "graph", "labels", "folds", "label_view", "split", "graph_files",
                  "h8_initial", "initialization", "seeds", "source_preparation", "support",
                  "device_policy", "registered_node_types", "original_graph_fingerprint", "node_count"):
            if j[k] != old[k]: raise ValueError("Frozen S4/S6 input differs: " + k)
        if j["baseline_receipt"] != row["receipt"]: raise ValueError("S4 receipt differs")
        validate_parts(j["split"], j["graph_files"])
        for k in ("spec", "feature_view", "feature_npz", "initial", "preparation_evidence"):
            checked(j[k])
            if path.parent.resolve() not in Path(j[k]["path"]).resolve().parents:
                raise ValueError("New artifact outside N-C1")
        want = make_spec(FeatureSpec.from_json(read(checked(old["spec"]))), teacher[j["task_id"]])
        spec = FeatureSpec.from_json(read(checked(j["spec"])))
        if spec.to_json() != want.to_json() or spec.digest() != j["spec_sha256"]:
            raise ValueError("S6 must add only the bound TEACHER modality to S4")
        for m in spec.modalities:
            na.checked_tree(read(checked(m["manifest"])), seen)
        carrier = read(checked(j["feature_view"]))
        if (carrier["data"] != j["feature_npz"] or carrier["spec"] != spec.to_json()
                or carrier["spec_sha256"] != spec.digest() or carrier["task_id"] != j["task_id"]
                or carrier["feature_shape"] != [j["node_count"], spec.carrier_dim()]
                or carrier["original_graph_fingerprint"] != j["original_graph_fingerprint"]
                or not carrier["original_inputs_unchanged"]):
            raise ValueError("Carrier binding differs")
        proof = read(checked(j["preparation_evidence"]))
        if (proof["initial"] != j["initial"] or not proof["common_bitwise_equal"]
                or proof["baseline_state_sha256"] != old["initial"]["state_sha256"]
                or proof["dropout"] != j["dropout"] or proof["optimizer_steps"] != 0):
            raise ValueError("S4 common-state proof differs")
        # Check seed identity using the same semantic rule, without constructing or forwarding.
        from scripts.DFG.dfg_v2.experiment.init import parameter_seed
        expected = {n:parameter_seed(j["seeds"]["fit"], "modality_dropout",
                    [j["task_id"], j["fold"], j["profile"], spec.digest(), n])
                    for n in j["registered_node_types"]}
        if (j["dropout"]["seeds"] != expected or j["dropout"]["probability"] != spec.modality_dropout
                or j["dropout"]["spec_digest"] != spec.digest()):
            raise ValueError("Dropout binding differs")
        if deep:
            payload = checked_initial(j["initial"], j["task_id"], j["fold"], "G3R", spec_digest=spec.digest())
            if (payload.get("baseline_state_sha256") != old["initial"]["state_sha256"]
                    or payload.get("source") != j["h8_initial"] or payload.get("formal_training") is not False
                    or payload.get("initialization_version") != INIT_VERSION):
                raise ValueError("Baseline initial fingerprint differs")
            if proof["baseline_mode"] == "existing_NA_initial":
                base, _ = baseline_state(old)
            else:
                base = checked_initial(proof["reconstructed_initial"], j["task_id"], j["fold"],
                                       "G3R", spec_digest=old["spec_sha256"])["state_dict"]
                if tensor_digest(base) != old["initial"]["state_sha256"]: raise ValueError("Reconstruction mismatch")
            if any(k not in payload["state_dict"] or not torch.equal(v, payload["state_dict"][k]) for k,v in base.items()):
                raise ValueError("S4/S6 common initial tensors differ")
    auth = read(checked(plan["authorization_template"]))
    if (auth.get("execution_authorized") is not False or auth.get("jobs") != 30
            or auth.get("matrix_sha256") != digest(plan["jobs"]) or auth.get("scope") != "formal_NC1"):
        raise ValueError("Authorization template differs")
    return plan
