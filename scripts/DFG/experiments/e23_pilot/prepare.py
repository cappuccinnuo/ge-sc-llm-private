"""Freeze input references and all untrained triplet states; CPU, no optimizer."""
import gc
from pathlib import Path
import torch
from scripts.DFG.experiments.common import write_json,read_json,sha256,digest,seed_all,tensor_digest
from .inputs import load_task,TASK_ORDER
from .model import make_model,triple_initialize,assert_e2_alignment,provenance,ADAPTER_VERSION,TRIPLE_INITIALIZATION_VERSION
from .runtime import graph_schema_and_support,Supervision
from . import VARIANTS,EXPERIMENT_VERSION
def prepare(output):
    output=Path(output);dest=output/"initialization"
    if dest.exists():raise FileExistsError("Initialization already exists; verify/reuse, do not overwrite")
    dest.mkdir()
    tasks=[]
    torch.set_num_threads(2)
    for task_id in TASK_ORDER:
        info,graphs,labels=load_task(task_id);folder=dest/task_id;folder.mkdir()
        seed=10000+(1000 if info["task"]=="contract" else 0)
        print("PREPARE",task_id,flush=True)
        alignment=assert_e2_alignment(info["graphs"]["E2"]["path"],info["task"],seed)
        write_json(folder/"e2_baseline_alignment.json",alignment)
        models={}
        for variant in VARIANTS:
            seed_all(seed);models[variant]=make_model(info["task"],graphs[variant],"cpu")
        initialization=triple_initialize(models,seed+77)
        write_json(folder/"initialization_audit.json",initialization)
        info.update(experiment_version=EXPERIMENT_VERSION,adapter_version=ADAPTER_VERSION,
                    triple_initialization_version=TRIPLE_INITIALIZATION_VERSION,
                    initialization_seed=seed+77,fit_seed=seed+1000000,
                    initialization_audit_path=str(folder/"initialization_audit.json"),
                    initialization_audit_sha256=sha256(folder/"initialization_audit.json"),
                    alignment=alignment,initialization={},support={},supervision={})
        for variant,model in models.items():
            info["support"][variant]=graph_schema_and_support(graphs[variant],info["split"])
            parts={n:Supervision(model,info["task"],info["split"][n+"_files"]) for n in ("train","val")}
            info["supervision"][variant]={n:p.manifest for n,p in parts.items()}
            path=folder/(variant+"_initial.pt")
            state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            torch.save({"kind":"untrained_initial","variant":variant,"task_id":task_id,"state_dict":state,
                        "state_sha256":tensor_digest(state),"graph_sha256":info["graphs"][variant]["sha256"],
                        "initialization_audit_sha256":info["initialization_audit_sha256"],
                        "optimizer_steps":0,"initialization":initialization},str(path))
            info["initialization"][variant]={"path":str(path),"sha256":sha256(path),"state_sha256":tensor_digest(state),
                                            "parameters":sum(p.numel() for p in model.parameters())}
        write_json(folder/"task_manifest.json",info)
        tasks.append({"id":task_id,"manifest":str(folder/"task_manifest.json"),"sha256":sha256(folder/"task_manifest.json")})
        del models,graphs,model,parts,state;gc.collect()
    write_json(output/"input_manifest.json",{"version":EXPERIMENT_VERSION,"tasks":tasks,"model_adapter_provenance":provenance()})
    return tasks
