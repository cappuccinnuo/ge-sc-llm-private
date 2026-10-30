"""Seal the unchanged 170-job matrix with accepted N-anon-s feature views.

This is a preparation plan, never an execution authorization. Existing training
CLIs do not accept this new feature-view/label/grouped-split contract implicitly.
"""
import argparse
import copy
import subprocess
from pathlib import Path

from .prepare import read, write, ref, checked, verify_prepared
from .spelling_features import probe_gate

VERSION = "prompt8g-spelling-benchmark-preparation-v1"


def assert_frozen_matrix(old, new):
    for key in ("jobs","fit_count","protocol","protocol_version","split_seed",
                "proposed_training_seeds","label_policies","statistics","statistical_label_scope",
                "selection_rule","initialization","G0P","scoring"):
        if new[key] != old[key]:
            raise ValueError("Frozen experiment rule differs: " + key)
    if set(new["tasks"]) != set(old["tasks"]):
        raise ValueError("Frozen task matrix differs")
    for tid, task in old["tasks"].items():
        for key, value in task.items():
            if key != "feature_view" and new["tasks"][tid].get(key) != value:
                raise ValueError("Frozen task input differs: " + tid + "/" + key)
    if new["execution_authorized"] or any(j["execution_authorized"] for j in new["jobs"]):
        raise ValueError("Preparation cannot authorize fits")
    if any(new[k] is not None for k in
           ("selected_training_seeds","selected_label_policy","selected_execution_location")):
        raise ValueError("User execution choices have not been provided")


def verify_plan(path):
    path=Path(path);plan=read(path)
    if plan["version"]!=VERSION or read(path.with_name("plan.seal.json"))["plan"]!=ref(path):
        raise ValueError("New plan version/seal differs")
    old=read(checked(plan["supersedes_plan"]))
    assert_frozen_matrix(old,plan)
    for r in plan["bound_artifacts"].values():
        checked(r)
    for tid,task in plan["tasks"].items():
        for key in ("population","folds"):
            checked(task[key])
        for view in ("original","anonymous"):
            detail=read(checked(task["feature_view"][view]))
            checked(detail["data"])
            if detail["task_id"]!=tid:
                raise ValueError("Feature view task differs")
        for profile,p in task["profiles"].items():
            checked(p["graph"])
    features=read(checked(plan["bound_artifacts"]["feature_views"]))
    proof=read(checked(plan["bound_artifacts"]["feature_equivalence"]))
    if proof["features"]!=plan["bound_artifacts"]["feature_views"] or not proof["passed"]:
        raise ValueError("Model acceptance refers to different feature view")
    if set(features["task_views"])!=set(plan["tasks"]):
        raise ValueError("Feature task population differs")
    if proof["profile_checks"]!=20 or proof["G0_identity_tasks"]!=4 or proof["optimizer_steps"]!=0:
        raise ValueError("Incomplete model proof or unintended optimizer updates")
    for r in proof["artifacts"].values():
        checked(r)
    if plan["fit_count"]!=170 or len(plan["jobs"])!=170:
        raise ValueError("Expected unchanged 170-fit proposal")
    return dict(passed=True,plan=ref(path),fit_count=170,frozen_matrix_exact=True,
        new_features_bound=True,execution_authorized=False,formal_fits=0,
        selected_label_policy=None,selected_training_seeds=None,selected_location=None,
        existing_training_cli_accepts_plan=False)


def prepare(naming, semantic, probes, features, model_proof, output):
    manifest,_,probe_result=probe_gate(naming,semantic,probes)
    old_path=checked(manifest["old_plan"])
    verify_prepared(old_path)
    old=read(old_path)
    feature_path=Path(features)/"manifest.json"
    feature=read(feature_path)
    if read(Path(features)/"manifest.seal.json")["manifest"]!=ref(feature_path):
        raise ValueError("Feature manifest seal differs")
    proof_path=Path(model_proof)/"summary.json"
    proof=read(proof_path)
    if read(Path(model_proof)/"summary.seal.json")["summary"]!=ref(proof_path):
        raise ValueError("Model proof seal differs")
    if feature["naming"]!=ref(Path(naming)/"manifest.json") or feature["probes"]!=ref(Path(probes)/"summary.json"):
        raise ValueError("Accepted naming/probe identity differs")
    if proof["features"]!=ref(feature_path) or not proof["passed"]:
        raise ValueError("Model proof belongs to another feature view")
    output=Path(output);output.mkdir(exist_ok=False)
    plan=copy.deepcopy(old)
    plan.update(version=VERSION,feature_policy="N-anon-s AST identifier spelling bijection",
        status="prepared_awaiting_label_seed_location_and_executor_binding",
        supersedes_plan=ref(old_path),execution_authorized=False,training_executed=0,
        git_head_at_preparation=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        input_mapping_used_for_features_only=True,original_DFG_graph_used=True)
    bound=plan["bound_artifacts"]
    for key in ("feature_views","feature_equivalence","keyword_baselines"):
        if key in bound:
            bound["historical_"+key]=bound[key]
    bound.update(feature_views=ref(feature_path),feature_equivalence=ref(proof_path),
        keyword_baselines=ref(Path(probes)/"summary.json"),
        spelling_naming=ref(Path(naming)/"manifest.json"),
        spelling_semantics=ref(Path(semantic)/"summary.json"),
        spelling_probes=ref(Path(probes)/"summary.json"))
    for tid,task in plan["tasks"].items():
        task["feature_view"]=feature["task_views"][tid]
    plan["interpretation"]=dict(access_control_node="descriptive only",
        primary_DFG_tasks=["reentrancy_node","reentrancy_contract","access_control_contract"],
        nonSolidiFI="pooled counts; no strong small-sample inference",
        anonymity="Only selected identifier spellings; not full Solidity semantic equivalence or absence of all shortcuts",
        final_device="Sufficient-VRAM server planned; local 4GiB is development constraint; server not measured")
    plan["preparation_code"]=[ref(Path(__file__)),
        ref(Path(__file__).with_name("spelling_features.py")),
        ref(Path(__file__).with_name("spelling_probes.py")),
        ref(Path(__file__).with_name("spelling_names.py")),
        ref(Path(__file__).with_name("spelling_parity.py")),
        ref(Path(__file__).with_name("prepare_spelling.py"))]
    plan["execution_gate"].update(existing_cli_supports_this_plan=False,
        keyword_baseline_binding_pending=False,
        executor_integration_required="Explicit N-anon-s feature, selected label mask and grouped-fold binding; G0P uses G0 token view with archived empty schema. Validate executor before any fit.")
    plan["limitations"] += [
        "Frozen grammar enum_value/yul_identifier nodes are not identifier nodes and remain unchanged.",
        "String/comment content is preserved; passing P2/P3 does not eliminate all source/template cues.",
        "Spelling bijection includes unknown external members, so transformed source is a feature view, not promised deployable Solidity.",
        "Model proof uses CPU eval forwards with saved zero-step initials; no training trajectories measured."]
    assert_frozen_matrix(old,plan)
    write(output/"plan.json",plan)
    write(output/"plan.seal.json",dict(plan=ref(output/"plan.json")))
    write(output/"authorization_template.json",dict(version=VERSION,plan=ref(output/"plan.json"),
        execution_authorized=False,label_policy=None,label_policy_default="L-audit",
        training_seeds=None,training_seeds_default=[1],execution_location=None,
        authorized_by=None,estimated_default_fit_count=170,
        prerequisite="New execution plan/runtime binding after explicit user choices; do not pass this plan to an old CLI"))
    result=verify_plan(output/"plan.json")
    write(output/"verification.json",result)
    write(output/"acceptance_decision.json",dict(status=plan["status"],execution_authorized=False,
        feature_and_probe_gates_passed=True,plan=ref(output/"plan.json"),formal_fit_count=0,
        diagnostic_classifier_fits=probe_result["classifier_fits"],optimizer_steps=0,
        user_choices_required=["label_policy","seed_count","execution_location"],
        executor_binding_not_yet_authorized=True))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("naming","semantic","probes","features","model-proof","output"):
        p.add_argument("--"+name,required=True)
    a=p.parse_args()
    print(prepare(a.naming,a.semantic,a.probes,a.features,a.model_proof,a.output))
