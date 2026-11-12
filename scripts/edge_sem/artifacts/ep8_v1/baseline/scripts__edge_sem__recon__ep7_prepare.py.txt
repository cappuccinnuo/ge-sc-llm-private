"""EP7 deterministic CPU preparation; no CUDA initialization or fitting."""
import argparse
import copy
from datetime import datetime,timezone
import gc
from pathlib import Path
import traceback
import torch
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.experiments.common import tensor_digest
from .. import execution as ex
from ..checkpoint import edge_fields
from ..io import ROOT,ref,read,write,checked
from ..protocol_p2 import registration
from .ep7_common import OUT,TASKS
from .common import PLAN

ADAPTATIONS=[
 dict(id="call_fa9553b4bee0410b8b1dfa2fcc7c490b/0",approved=True,
      choice="EdgeSem provenance-headed trainer copy; only validation/audit imports change; CPU numerical parity required"),
 dict(id="call_fa9553b4bee0410b8b1dfa2fcc7c490b/1",approved=True,
      choice="Separate train-only norm pilot; same Adam/OneCycle/train masks and 50 steps; no validation/test scoring or best selection"),
]

def source_job(source,tid,fold,profile):
    task,info,entry=h8.prepared(source,dict(task_id=tid,fold=fold,seed=1,profile="G3R"))
    attrs=ref(ROOT/"scripts/edge_sem/artifacts/ep6_v1/attributes"/tid/"manifest.json")
    manifest=read(checked(attrs))
    return dict(task_id=tid,granularity="node",fold=fold,seed=1,profile="G3R",edge_profile=profile,
        graph=entry["graph"],folds=task["record"]["folds"],labels=task["record"]["labels"],
        label_view=task["label_view"],feature_view=task["feature_view"],feature_npz=task["feature_npz"],
        source_preparation=source["source_preparation"],split=info["split"],
        graph_files=task["record"]["graph_files"],historical_config=task["config"],config=ex.p2_config(task["config"]),
        seeds=info["seeds"],f4_manifest=manifest["f4_manifest"],attrs_manifest=attrs,
        historical_initial=entry["initial"],historical_initialization=info["initialization"])


def prepare():
    folder=OUT/"preparation";folder.mkdir(parents=True,exist_ok=False)
    source=h8.load(PLAN);jobs=[];configs={}
    try:
        for tid in TASKS:
            for profile in ("G3R","G3R-T","G4R","G4R-A"):
                for fold in (range(10) if profile=="G3R" else (0,)):
                    job=source_job(source,tid,fold,profile)
                    dest=folder/tid/("fold_%d"%fold)/profile;dest.mkdir(parents=True,exist_ok=False)
                    model=ex.assemble_model(job)
                    state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                    state_sha=tensor_digest(state)
                    payload=dict(kind="untrained_initial",optimizer_steps=0,task_id=tid,fold=fold,seed=1,
                        edge_profile=profile,fit_seed=job["seeds"]["fit"],
                        constructor_seed=job["seeds"]["constructor"],state_dict=state,state_sha256=state_sha)
                    path=dest/"initial.pt";torch.save(payload,str(path))
                    job["initial"]=dict(ref(path),state_sha256=state_sha)
                    actual=ex.load_checked(job["initial"])
                    model.load_state_dict(actual["state_dict"],strict=True)
                    if tensor_digest(model.state_dict())!=state_sha:raise ValueError("Initial strict reload differs")
                    record=dict(kind="fresh_G3R_anchor_semantic_copy",optimizer_steps=0,seeds=job["seeds"],
                        shared_copy=model.edge_initialization,initial=job["initial"],
                        historical_initial=job["historical_initial"],
                        matches_historical_8H_initial=(profile=="G3R" and state_sha==job["historical_initial"]["state_sha256"]),
                        historical_comparison="descriptive; no claim that stopping is the only computation difference")
                    write(dest/"initialization.json",record);job["initialization"]=ref(dest/"initialization.json")
                    job["support"]=ex.model_support(model,job["split"])
                    job["edge_binding"]=edge_fields(model)
                    ex._validate_job(job)
                    write(dest/"job.json",job);jobs.append(dict(job=job,record=ref(dest/"job.json")))
                    configs[tid]=dict(config=job["config"],historical_config=job["historical_config"])
                    print("EP7 prepared",ex.job_id(job),flush=True)
                    del model,state,payload,actual;gc.collect()
        if torch.cuda.is_initialized():raise AssertionError("CPU preparation initialized CUDA")
        reg=ROOT/"scripts/edge_sem/artifacts/protocol_p2/registration.json"
        write(reg,registration(configs,ref(PLAN),ADAPTATIONS))
        write(folder/"index.json",dict(jobs=jobs,source_h8_plan=ref(PLAN),registration=ref(reg),
            generated_utc=datetime.now(timezone.utc).isoformat(),cuda_initialized=False,optimizer_steps=0))
        write(folder/"index.seal.json",dict(index=ref(folder/"index.json")))
    except Exception as error:
        write(folder/"failure.json",dict(error=repr(error),traceback=traceback.format_exc(),
            completed_jobs=len(jobs),automatic_retry=False))
        raise


def seal():
    index=OUT/"preparation/index.json"
    if read(index.with_name("index.seal.json"))["index"]!=ref(index):raise ValueError("Preparation seal differs")
    data=read(index);jobs=[]
    for item in data["jobs"]:
        job=read(checked(item["record"]))
        if job!=item["job"]:raise ValueError("Prepared job differs")
        jobs.append(job)
    matrices={
        "formal":[j for j in jobs if j["edge_profile"]=="G3R"],
        "gpu_probes":[j for tid in TASKS for profile in ("G3R","G3R-T","G4R","G4R-A")
            for j in jobs if j["task_id"]==tid and j["edge_profile"]==profile and j["fold"]==0],
        "norm_pilot":[j for j in jobs if j["task_id"]=="reentrancy_node" and j["edge_profile"]=="G4R-A" and j["fold"]==0],
    }
    if [len(matrices[k]) for k in ("formal","gpu_probes","norm_pilot")]!=[20,8,1]:raise ValueError("EP7 matrix differs")
    for scope,rows in matrices.items():
        ex.create(OUT/scope,dict(source_h8_plan=data["source_h8_plan"],jobs=rows,scope=scope,registration=data["registration"]))
        print("EP7 sealed",scope,len(rows),flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=("prepare","seal"))
    if parser.parse_args().command=="prepare":prepare()
    else:seal()
