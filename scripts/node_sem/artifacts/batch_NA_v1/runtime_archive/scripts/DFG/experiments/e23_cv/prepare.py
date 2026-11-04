"""Prepare all 30 triplets on CPU before H1; preserve Stage G and H2 states."""
import copy, gc, subprocess
from pathlib import Path
import torch
from scripts.DFG.experiments.common import read_json,write_json,sha256,digest,seed_all,tensor_digest
from scripts.DFG.experiments.e23_pilot.inputs import ROOT,OLD_RUN,DEFAULT_OUTPUT as STAGE_G,TASK_ORDER,NUMERIC_KEYS,load_task,check_hashes
from scripts.DFG.experiments.e23_pilot import VARIANTS
from scripts.DFG.experiments.e23_pilot.model import make_model,triple_initialize
from scripts.DFG.experiments.e23_pilot.runtime import graph_schema_and_support,Supervision
from scripts.DFG.experiments.paper_protocol import validate_document
from scripts.verify_e23_archive import verify as verify_archive
from . import BATCH_VERSION

DEFAULT_OUTPUT=ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/stage_h1_v1"
def seeds(task,fold):
    base=10000+fold+(1000 if task=="contract" else 0)
    return {"constructor":base,"pair":base+77,"fit":base+1000000}

def select_split(info,fold):
    document=read_json(info["source_splits_path"])
    if sha256(info["source_splits_path"])!=info["source_splits_sha256"]:raise ValueError("Split bytes changed")
    validate_document(document)
    k=5 if info["task"]=="contract" else 10
    if document["seed"]!=1 or document["k_folds"]!=k or not 0<=fold<k:raise ValueError("Invalid frozen fold")
    if [f["fold"] for f in document["folds"]]!=list(range(k)):raise ValueError("Fold inventory changed")
    return copy.deepcopy(document["folds"][fold])

def prepare(output):
    output=Path(output); dest=output/"initialization"
    if dest.exists():raise FileExistsError("Preparation is immutable; do not overwrite partial states")
    counts=verify_archive(STAGE_G)
    gplan=read_json(STAGE_G/"plan.json")
    from scripts.DFG.experiments.e23_pilot.control import runtime_hashes
    assert runtime_hashes()==gplan["runtime_code_sha256"]
    audit={"status":"passed","archive_counts":counts,"stage_g_plan":str(STAGE_G/"plan.json"),
           "stage_g_plan_sha256":sha256(STAGE_G/"plan.json"),"training_head":gplan["base_git_head"],
           "current_head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip(),
           "runtime_code_identical":True,"fold0_initial_state_checks":[],"reused":[]}
    from scripts.DFG.experiments.audit.ddg_diagnostics_v1.archive_audit import inventory
    _,baseline,expected=inventory()
    check_hashes(expected)
    write_json(output/"baseline_inventory.json",baseline)
    write_json(output/"baseline_hashes.json",expected)
    dest.mkdir(); tasks=[];torch.set_num_threads(2)
    oldplan=read_json(OLD_RUN/"plan.json")
    for task_id in TASK_ORDER:
        base,graphs,labels=load_task(task_id)
        ginfo=read_json(STAGE_G/"initialization"/task_id/"task_manifest.json")
        k=5 if base["task"]=="contract" else 10
        for fold in range(k):
            folder=dest/task_id/("fold_"+str(fold));folder.mkdir(parents=True)
            info=copy.deepcopy(base);info.update(fold=fold,split=select_split(base,fold))
            cfg_path=OLD_RUN/"jobs"/(task_id+"_fold"+str(fold))/"attempt_001/effective_config.json"
            cfg=read_json(cfg_path)
            for key in NUMERIC_KEYS+("environment",):
                if cfg[key]!=base["config"][key]:raise ValueError("Historical per-fold config drift: "+key)
            info.update(source_config=str(cfg_path),source_config_sha256=sha256(cfg_path))
            info["frozen_files"][str(cfg_path)]=sha256(cfg_path)
            state_seeds=seeds(info["task"],fold)
            models={}
            for variant in VARIANTS:
                seed_all(state_seeds["constructor"])
                models[variant]=make_model(info["task"],graphs[variant],"cpu")
            init_audit=triple_initialize(models,state_seeds["pair"])
            if fold==0:
                for variant,model in models.items():
                    actual=tensor_digest(model.state_dict())
                    if actual!=ginfo["initialization"][variant]["state_sha256"]:raise ValueError("Stage G fold0 initial mismatch")
                    support=graph_schema_and_support(graphs[variant],info["split"])
                    if support!=ginfo["support"][variant]:raise ValueError("Stage G fold0 support mismatch")
                    parts={n:Supervision(model,info["task"],info["split"][n+"_files"]) for n in ("train","val")}
                    if {n:p.manifest for n,p in parts.items()}!=ginfo["supervision"][variant]:raise ValueError("Stage G fold0 supervision mismatch")
                    audit["fold0_initial_state_checks"].append({"task_id":task_id,"variant":variant,"tensor_sha256":actual,"passed":True})
                    gjob=next(j for j in gplan["jobs"] if j["task_id"]==task_id and j["variant"]==variant)
                    receipt=STAGE_G/"runs"/task_id/"fold_0"/variant/"attempt_001/receipt.json"
                    audit["reused"].append({"task_id":task_id,"variant":variant,"job":gjob,"receipt":str(receipt),"sha256":sha256(receipt),"not_retrained":True})
                manifest=STAGE_G/"initialization"/task_id/"task_manifest.json"
            else:
                from scripts.DFG.experiments.e23_pilot import EXPERIMENT_VERSION,ADAPTER_VERSION,TRIPLE_INITIALIZATION_VERSION
                ap=folder/"initialization_audit.json";write_json(ap,init_audit)
                info.update(experiment_version=EXPERIMENT_VERSION,adapter_version=ADAPTER_VERSION,
                    triple_initialization_version=TRIPLE_INITIALIZATION_VERSION,initialization_seed=state_seeds["pair"],
                    fit_seed=state_seeds["fit"],initialization_audit_path=str(ap),initialization_audit_sha256=sha256(ap),
                    initialization={},support={},supervision={},execution_batch_version=BATCH_VERSION)
                for variant,model in models.items():
                    state={key:value.detach().cpu().clone() for key,value in model.state_dict().items()}
                    path=folder/(variant+"_initial.pt")
                    torch.save({"kind":"untrained_initial","variant":variant,"task_id":task_id,"fold":fold,"state_dict":state,
                        "state_sha256":tensor_digest(state),"graph_sha256":info["graphs"][variant]["sha256"],
                        "initialization_audit_sha256":sha256(ap),"optimizer_steps":0,"initialization":init_audit},str(path))
                    info["initialization"][variant]={"path":str(path),"sha256":sha256(path),"state_sha256":tensor_digest(state),
                        "parameters":sum(p.numel() for p in model.parameters())}
                    info["support"][variant]=graph_schema_and_support(graphs[variant],info["split"])
                    parts={n:Supervision(model,info["task"],info["split"][n+"_files"]) for n in ("train","val")}
                    info["supervision"][variant]={n:p.manifest for n,p in parts.items()}
                manifest=folder/"task_manifest.json";write_json(manifest,info)
                del state
            tasks.append({"task_id":task_id,"fold":fold,"manifest":str(manifest),"sha256":sha256(manifest),
                          "source":"stage_g_reuse" if fold==0 else "stage_h_fresh","seeds":state_seeds})
            print("PREPARED",task_id,"fold",fold,"fresh triplet verified",flush=True)
            del models,model,parts;gc.collect()
        del graphs;gc.collect()
    write_json(output/"fold0_reuse_audit.json",audit)
    write_json(output/"input_manifest.json",{"batch_version":BATCH_VERSION,"tasks":tasks,
        "stage_g_plan_sha256":sha256(STAGE_G/"plan.json"),"seed_formula":"10000 + fold + (1000 if contract else 0); pair +77; fit +1000000",
        "baseline_inventory_sha256":sha256(output/"baseline_inventory.json")})
    return tasks
