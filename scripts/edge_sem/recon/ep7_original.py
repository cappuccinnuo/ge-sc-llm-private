"""EP7 user-approved original-name primary revision; old plans stay read-only."""
import argparse
import copy
from datetime import datetime,timezone
import gc
import hashlib
from pathlib import Path
import subprocess
import traceback
import torch
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.benchmark_v2.spelling_features import assemble
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.experiment.run import _code_refs
from scripts.DFG.experiments.common import tensor_digest
from scripts.labeling_v2.safe_graph import read_graph
from .. import execution as ex
from ..io import ROOT,read,write,ref,checked
from ..checkpoint import edge_fields
from ..feature_views import source_feature
from ..protocol_p2 import registration,decisions_for_view,require_registration_commit

OUT=ROOT/"scripts/edge_sem/artifacts/ep7_original_v1"
OLD=ROOT/"scripts/edge_sem/artifacts/ep7_v1"


def frozen():
    before=read(OUT/"before.json")
    for row in before["old_artifacts"]+before["frozen_code"]+before["old_prior_artifacts"]:
        checked(row)
    checked(before["old_registration"]);checked(before["prompt"])
    if _code_refs()!=before["dfg_code_refs"]:
        raise ValueError("Frozen runtime list changed")
    for name,row in before["documents"].items():
        if hashlib.sha256((ROOT/name).read_bytes()[:row["bytes"]]).hexdigest()!=row["sha256"]:
            raise ValueError("Historical documentation prefix changed")
    return dict(passed=True,old_ep7_files=len(before["old_artifacts"]),
        frozen_sources=len(before["frozen_code"]),prior_artifacts=len(before["old_prior_artifacts"]))


def prepare():
    folder=OUT/"preparation";folder.mkdir(parents=True,exist_ok=False)
    old_index=OLD/"preparation/index.json"
    if read(old_index.with_name("index.seal.json"))["index"]!=ref(old_index):
        raise ValueError("Old zero-step index seal differs")
    old=read(old_index);source=h8.load(checked(old["source_h8_plan"]))
    jobs=[];proof=[];configs={}
    try:
        # All checks precede plan sealing. Existing initials are reused by SHA;
        # changing token values neither changes architecture nor allocates parameters.
        for item in old["jobs"]:
            prior=read(checked(item["record"]))
            if prior!=item["job"]:raise ValueError("Old prepared job identity differs")
            job=copy.deepcopy(prior)
            view,npz=source_feature(source,job["task_id"],"original")
            job.update(token_view="original",feature_view=view,feature_npz=npz)
            dest=folder/job["task_id"]/("fold_%d"%job["fold"])/job["edge_profile"]
            dest.mkdir(parents=True,exist_ok=False)
            original=read_graph(checked(job["graph"]));original_sha=graph_fingerprint(original)
            assembled=assemble(original,view)
            if graph_fingerprint(assembled)!=original_sha:
                raise ValueError("Original S0 does not reproduce frozen graph tokens")
            del original,assembled
            model=ex.assemble_model(job)
            initial=ex.load_checked(job["initial"])
            if (initial.get("kind")!="untrained_initial" or initial.get("optimizer_steps")!=0
                or any(initial.get(k)!=job[k] for k in ("task_id","fold","seed","edge_profile"))
                or initial.get("constructor_seed")!=job["seeds"]["constructor"]
                or initial.get("fit_seed")!=job["seeds"]["fit"]
                or tensor_digest(initial["state_dict"])!=job["initial"]["state_sha256"]
                or tensor_digest(model.state_dict())!=job["initial"]["state_sha256"]):
                raise ValueError("Original-view fresh construction changed the zero-step parameters")
            model.load_state_dict(initial["state_dict"],strict=True)
            if tensor_digest(model.state_dict())!=job["initial"]["state_sha256"]:
                raise ValueError("Initial reload differs")
            support=ex.model_support(model,job["split"])
            binding=edge_fields(model)
            if support!=prior["support"] or binding!=prior["edge_binding"]:
                raise ValueError("Feature-only revision changed topology/support/edge binding")
            record=dict(kind="view_revision_reusing_identical_sealed_zero_step",
                optimizer_steps=0,initial=job["initial"],previous_initialization=job["initialization"],
                user_decision=ref(OUT/"user_decision.json"),token_view="original",
                fresh_construction_parameters_bitwise_equal=True,graph_and_support_unchanged=True)
            write(dest/"initialization.json",record);job["initialization"]=ref(dest/"initialization.json")
            ex._validate_job(job)
            write(dest/"job.json",job)
            jobs.append(dict(job=job,record=ref(dest/"job.json")))
            proof.append(dict(job_id=ex.job_id(job),initial=job["initial"],
                fresh_parameters_bitwise_equal=True,strict_reload_exact=True,
                original_graph_tokens_bitwise_equal=True,support_exact=True,edge_binding_exact=True))
            configs[job["task_id"]]=dict(config=job["config"],historical_config=job["historical_config"])
            print("EP7 original prepared",ex.job_id(job),flush=True)
            del model,initial;gc.collect()
        if torch.cuda.is_initialized():raise AssertionError("CPU preparation initialized CUDA")
        revision=dict(kind="user_requested_primary_view_change",user_decision=ref(OUT/"user_decision.json"),
            previous_registration=ref(ROOT/"scripts/edge_sem/artifacts/protocol_p2/registration.json"),
            previous_plans={scope:ref(OLD/scope/"plan.json") for scope in ("gpu_probes","norm_pilot","formal")},
            changed_inputs=["feature_view","feature_npz","initialization provenance"],
            unchanged=["graph","labels","folds","split","P2 config","seeds","initial tensors","edge attributes"],
            original_view_source="8H source_preparation.tasks[task].feature_view.original",
            teacher_or_NodeSem_modalities_added=False,formal_fits=20,
            historical_comparison="8H anonymous results are descriptive; token view, stopping and initialization differ")
        write(OUT/"view_revision.json",revision)
        reg=OUT/"protocol_p2/registration.json"
        value=registration(configs,old["source_h8_plan"],read(OLD/"approved_adaptations.json"),"original")
        value["view_revision"]=ref(OUT/"view_revision.json")
        write(reg,value)
        write(folder/"index.json",dict(jobs=jobs,proof=proof,source_h8_plan=old["source_h8_plan"],
            registration=ref(reg),view_revision=ref(OUT/"view_revision.json"),
            cuda_initialized=False,optimizer_steps=0,new_weight_files=0))
        write(folder/"index.seal.json",dict(index=ref(folder/"index.json")))
    except Exception as error:
        write(folder/"failure.json",dict(error=repr(error),traceback=traceback.format_exc(),
            completed_jobs=len(jobs),automatic_retry=False))
        raise


def seal():
    index=OUT/"preparation/index.json"
    if read(index.with_name("index.seal.json"))["index"]!=ref(index):
        raise ValueError("Original preparation seal differs")
    data=read(index);jobs=[]
    for item in data["jobs"]:
        job=read(checked(item["record"]))
        if job!=item["job"]:raise ValueError("Prepared job changed")
        jobs.append(job)
    matrices={
        "formal":[j for j in jobs if j["edge_profile"]=="G3R"],
        "gpu_probes":[j for task in ex.TASKS for profile in ("G3R","G3R-T","G4R","G4R-A")
            for j in jobs if j["task_id"]==task and j["edge_profile"]==profile and j["fold"]==0],
        "norm_pilot":[j for j in jobs if j["task_id"]=="reentrancy_node" and j["edge_profile"]=="G4R-A" and j["fold"]==0],
    }
    if [len(matrices[k]) for k in ("formal","gpu_probes","norm_pilot")]!=[20,8,1]:
        raise ValueError("Original-view matrix differs")
    for scope,rows in matrices.items():
        ex.create(OUT/scope,dict(source_h8_plan=data["source_h8_plan"],jobs=rows,scope=scope,
            registration=data["registration"],token_view="original",view_revision=data["view_revision"]))
        print("EP7 original sealed",scope,len(rows),flush=True)


def authorize(commit):
    acceptance=read(OUT/"cpu_acceptance.json")
    if acceptance.get("passed") is not True or read(OUT/"cpu_acceptance.seal.json")["acceptance"]!=ref(OUT/"cpu_acceptance.json"):
        raise ValueError("CPU revision acceptance missing")
    request=read(OUT/"user_decision.json")
    if ([r["answer"] for r in request["answers"]]!=[
        "先调整主视图，再封存执行方案","授权按顺序执行上述检查与训练（推荐）"]
        or request["execution"]!={**request["execution"],"gpu_probe_jobs":8,"norm_pilot_jobs":1,"formal_G3R_jobs":20}):
        raise PermissionError("Recorded user scope differs")
    reg=OUT/"protocol_p2/registration.json"
    require_registration_commit(ref(reg),commit)
    decision=OUT/"protocol_p2/decisions.json"
    value=dict(date=datetime.now(timezone.utc).isoformat(),user_request=request["user_request"],
        approval_record=ref(OUT/"user_decision.json"),token_view="original",
        interpretation=request["interpretation"],
        decisions={k:dict(status="confirmed",value=v) for k,v in decisions_for_view("original").items()})
    write(decision,value);write(decision.with_suffix(".seal.json"),dict(decisions=ref(decision)))
    for scope,previous in (("gpu_probes",()),("norm_pilot",("gpu_probes",)),("formal",("gpu_probes","norm_pilot"))):
        path=OUT/scope/"plan.json";plan=ex.load(path)
        approval=dict(execution_authorized=True,user_request=request["user_request"],
            approval_record=ref(OUT/"user_decision.json"),date=value["date"],scope=scope,
            plan=ref(path),jobs=[ex.job_id(j) for j in plan["jobs"]],decisions=ref(decision),
            registration_commit=commit,prerequisites=[ref(OUT/name/"plan.json") for name in previous],
            cpu_acceptance=ref(OUT/"cpu_acceptance.json"),automatic_retry=False)
        dest=path.with_name("execution_authorization.json")
        write(dest,approval);write(dest.with_suffix(".seal.json"),dict(authorization=ref(dest)))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("command",choices=("prepare","seal","frozen","authorize"))
    p.add_argument("--registration-commit")
    a=p.parse_args()
    if a.command=="prepare":prepare()
    elif a.command=="seal":seal()
    elif a.command=="frozen":print(frozen())
    else:authorize(a.registration_commit)
