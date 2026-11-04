"""Extend existing accepted mean initials with only a zero readout vector."""
import copy,gc,subprocess
from pathlib import Path
import torch
from .common import *
from .model import make_model,load_mean_state,semantic_state,validate_registration,ADAPTER_VERSION,INITIALIZATION_VERSION
from .runtime import Supervision,graph_schema_and_support
from scripts.DFG.experiments.guard_extension.archive import verify_archive
from scripts.DFG.experiments.guard_extension.common import verify_plan as verify_guard
from scripts.DFG.experiments.overall_cv import checks as baseline_checks
from scripts.DFG.experiments.guard_extension import checks as guard_checks

def validate_source_record(record,info,variant,plan):
    init=info["initialization"][variant]
    expected=dict(kind="untrained_initial",optimizer_steps=0,task_id=info["task_id"],fold=info["fold"],
        variant=variant,fit_seed=info["fit_seed"],pair_version=plan["pair_version"],
        graph_sha256=info["graphs"][variant]["sha256"],pairing_sha256=info["initialization_audit_sha256"])
    if any(record.get(k)!=v for k,v in expected.items()):raise ValueError("Historical initial provenance mismatch")
    if tensor_digest(record["state_dict"])!=init["state_sha256"] or record.get("state_sha256")!=init["state_sha256"]:raise ValueError("Historical initial tensor mismatch")
    if "readout_vector" in record["state_dict"]:raise ValueError("Historical mean already has attention")

def validate_mean_binding(binding,info,variant,plan):
    expected={"graph_sha256":info["graphs"][variant]["sha256"],"initial_weights_sha256":info["initialization"][variant]["sha256"],
        "initial_state_sha256":info["initialization"][variant]["state_sha256"],"graph_labels_sha256":info["labels_sha256"],
        "task_id":info["task_id"],"variant":variant,"split":info["split"],"score_role":"cv_validation","plan_sha256":digest(plan)}
    if any(binding.get(k)!=v for k,v in expected.items()):raise ValueError("Historical mean result binding mismatch")

def prepare(output=DEFAULT):
    output=Path(output)
    if output.exists():raise FileExistsError("New batch required; no overwrite")
    plans={};plans["HCG"],audit=verify_archive(SOURCES["HCG"]);plans["HCG_DDG_GUARD"]=verify_guard(SOURCES["HCG_DDG_GUARD"])
    output.mkdir(parents=True);torch.set_num_threads(2);assets={};refs=[];accepted=[]
    def freeze(path,expected=None):
        path=Path(path).resolve();h=sha256(path)
        if expected is not None and expected!=h:raise ValueError("Frozen source mismatch: "+str(path))
        assets[str(path)]=h;return path
    historical_runtime={}
    for v,plan in plans.items():
        historical_runtime.update(plan["runtime"]);historical_runtime.update(plan.get("historical_runtime",{}))
        freeze(SOURCES[v]/"plan.json");freeze(SOURCES[v]/"plan.seal.json")
    write_json(output/"historical_archive_audit.json",audit);freeze(output/"historical_archive_audit.json")
    for tid in TASKS:
        for fold in range(5):
            old_infos={};mean_refs={};models={};states={};supports={};sup={};per_audits={}
            for variant in VARIANTS:
                plan=plans[variant];ref=task_ref(plan,tid,fold);ip=freeze(ref["manifest"],ref["sha256"]);old=read_json(ip);old_infos[variant]=old
                check=baseline_checks if variant=="HCG" else guard_checks
                job=dict(task_id=tid,fold=fold,variant=variant);attempt=check.completed(SOURCES[variant],job,plan)
                if attempt is None:raise ValueError("Historical mean fit missing")
                receipt=read_json(attempt/"receipt.json");freeze(attempt/"receipt.json")
                for name,h in receipt["artifacts"].items():freeze(attempt/name,h)
                validate_mean_binding(read_json(attempt/"binding.json"),old,variant,plan)
                if read_json(attempt/"result.json")["fit_seed"]!=old["fit_seed"]:raise ValueError("Historical fit seed mismatch")
                for key,hashkey in [("labels_path","labels_sha256"),("source_prepared_manifest","source_prepared_manifest_sha256"),
                    ("source_splits_path","source_splits_sha256"),("initialization_audit_path","initialization_audit_sha256")]:freeze(old[key],old[hashkey])
                for source in read_json(old["source_prepared_manifest"])["sources"].values():freeze(source["path"],source["sha256"])
                graph=old["graphs"][variant];freeze(graph["path"],graph["sha256"])
                init=old["initialization"][variant];freeze(init["path"],init["sha256"])
                record=torch.load(init["path"],map_location="cpu");validate_source_record(record,old,variant,plan)
                cfg=old["config"]
                if cfg["hidden_size"]!=128 or cfg["feature"]!="inside_token" or cfg["maximum_training_epochs"]!=50:raise ValueError("Unexpected frozen architecture/config")
                model=make_model("contract",graph["path"],"cpu",cfg["hidden_size"],cfg["layers"],cfg["heads"],graph_kind=variant)
                rng=torch.get_rng_state().clone();load_mean_state(model,record["state_dict"])
                if not torch.equal(rng,torch.get_rng_state()):raise ValueError("Initial extension consumed RNG")
                shared={k:v.detach().cpu().clone() for k,v in model.state_dict().items() if k!="readout_vector"}
                if tensor_digest(shared)!=init["state_sha256"]:raise ValueError("Shared initial tensors changed")
                support=graph_schema_and_support(model.nx_graph,old["split"])
                if support["schema"]!=old["support"][variant]["schema"]:raise ValueError("Registered schema changed")
                validate_registration(model,support["schema"])
                supervision={phase:Supervision(model,"contract",old["split"][phase+"_files"]).manifest for phase in ("train","val")}
                if supervision!=old["supervision"][variant]:raise ValueError("Historical supervision changed")
                states[variant]={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};models[variant]=model;supports[variant]=support;sup[variant]=supervision
                mean_refs[variant]=dict(batch=str(SOURCES[variant]),manifest=str(ip),manifest_sha256=sha256(ip),
                    initial_path=init["path"],initial_sha256=init["sha256"],initial_state_sha256=init["state_sha256"],
                    receipt=str(attempt/"receipt.json"),receipt_sha256=sha256(attempt/"receipt.json"),
                    plan_sha256=sha256(SOURCES[variant]/"plan.json"),fit_seed=old["fit_seed"],graph_sha256=graph["sha256"])
                per_audits[variant]=dict(shared_initial_exact=True,shared_tensor_sha256=tensor_digest(shared),new_parameter="readout_vector",new_parameter_count=128,
                    zero_initial=True,initial_extension_rng_unchanged=True,source=mean_refs[variant])
                accepted.append(dict(job,source=mean_refs[variant]))
            a,b=old_infos["HCG"],old_infos["HCG_DDG_GUARD"]
            for key in ("config","split","fit_seed","labels_sha256","source_prepared_manifest_sha256","source_splits_sha256","label_version","cohort"):
                if a[key]!=b[key]:raise ValueError("Paired mean histories differ: "+key)
            if a["graphs"]["HCG"]["node_attributes_sha256"]!=b["graphs"]["HCG_DDG_GUARD"]["node_attributes_sha256"]:raise ValueError("Paired node labels/features differ")
            sa,sb=semantic_state(models["HCG"]),semantic_state(models["HCG_DDG_GUARD"])
            if not set(sa)<=set(sb) or any(not torch.equal(sa[k],sb[k]) for k in sa):raise ValueError("Cross-graph common semantic initial mismatch")
            folder=output/"prepared"/tid/("fold_"+str(fold));folder.mkdir(parents=True)
            ap=folder/"initialization_audit.json";write_json(ap,dict(readout=READOUT,variants=per_audits,
                common_semantic_tensors=len(sa),common_semantic_sha256=tensor_digest(sa),all_common_exact=True))
            freeze(ap);inits={}
            for variant in VARIANTS:
                state=states[variant];path=folder/(variant+"_initial.pt")
                record=dict(kind="untrained_initial",optimizer_steps=0,task_id=tid,fold=fold,variant=variant,
                    state_dict=state,state_sha256=tensor_digest(state),fit_seed=a["fit_seed"],pair_version=PAIR_VERSION,
                    graph_sha256=old_infos[variant]["graphs"][variant]["sha256"],pairing_sha256=sha256(ap),readout=READOUT)
                torch.save(record,str(path));freeze(path);inits[variant]=dict(path=str(path),sha256=sha256(path),state_sha256=record["state_sha256"])
            info=copy.deepcopy(a)
            info.update(graphs={v:old_infos[v]["graphs"][v] for v in VARIANTS},initialization=inits,support=supports,supervision=sup,
                experiment_version=VERSION,pair_version=PAIR_VERSION,initialization_version=INITIALIZATION_VERSION,
                adapter_version=ADAPTER_VERSION,initialization_audit_path=str(ap),initialization_audit_sha256=sha256(ap),mean_sources=mean_refs,readout=READOUT)
            path=folder/"task.json";write_json(path,info);freeze(path);refs.append(dict(task_id=tid,fold=fold,manifest=str(path),sha256=sha256(path)))
            print("PREPARED_ZERO_READOUT",tid,fold,flush=True)
            del models,states,model,record,sa,sb,shared;gc.collect()
    write_json(output/"mean_reuse_audit.json",dict(status="passed",fits=20,results=accepted));freeze(output/"mean_reuse_audit.json")
    plan=dict(version=VERSION,pair_version=PAIR_VERSION,head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip(),
        runtime=runtime_hashes(),historical_runtime=historical_runtime,frozen=assets,jobs=expected_jobs(),tasks=refs,
        device="cuda:0",threads=2,maximum_epochs=50,execution_authorized=True,authorization="User requested completion of next stage on 2026-10-20",
        score_role="cv_validation",protocol="paper_kfold",initialization_version=INITIALIZATION_VERSION,readout=READOUT,
        source_batches={v:str(path) for v,path in SOURCES.items()},
        policy="20 new attention fits, 20 mean read-only; no F1 gate; stop on correctness/resource errors; no automatic retry")
    write_json(output/"plan.json",plan);write_json(output/"plan.seal.json",dict(sha256=sha256(output/"plan.json")))
    verify_plan(output);return plan
