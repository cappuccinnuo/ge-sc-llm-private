"""Rebind existing frozen E0/K graphs and save 30 fresh paired CPU initializations."""
import copy,gc,pickle,subprocess
from pathlib import Path
import torch
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.state.stage_f.initialization import initialize_pair,INITIALIZATION_VERSION
from scripts.DFG.experiments.e23_pilot.model import make_model,assert_e2_alignment,ADAPTER_VERSION
from scripts.DFG.experiments.e23_pilot.runtime import Supervision,graph_schema_and_support
from scripts.DFG.experiments.e23_cv.prepare import seeds,select_split
from .common import *
from .checks import graph_pair,check_common
def load(path):
 with Path(path).open("rb") as f:return pickle.load(f)
def prepare(output):
 output=Path(output);dest=output/"prepared"
 if dest.exists() or (output/"plan.json").exists():raise ValueError("Preparation is immutable; no overwrite")
 dest.mkdir(parents=True);torch.set_num_threads(2);assets={};refs=[];inventory=[];reuse=[]
 def check(path,expected=None):
  p=Path(path).resolve();h=sha256(p)
  if expected is not None and h!=expected:raise ValueError("Input hash drift: "+str(p))
  assets[str(p)]=h;return p
 kdir=ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/stage_k_v1"
 kp=read_json(check(kdir/"plan.json",read_json(check(kdir/"plan.seal.json"))["sha256"]))
 # Archive verification accepts new sidecar modules, never changes the old seal.
 recorded_hashes(kp["runtime"]);recorded_hashes(kp["frozen"])
 from scripts.DFG.experiments.stage_k_pilot.control import completed as kcomplete
 if sum(kcomplete(kdir,j,kp) is not None for j in kp["jobs"])!=4:raise ValueError("K archive incomplete")
 for path,h in kp["frozen"].items():check(path,h)
 check(kdir/"delivery_manifest.json")
 delivered={x["path"]:x["sha256"] for x in read_json(kdir/"delivery_manifest.json")["files"]}
 hi=ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/stage_h1_v1/input_manifest.json"
 htasks=read_json(check(hi))["tasks"]
 if {(x["task_id"],x["fold"]) for x in htasks}!={(t,f) for t in TASKS for f in range(folds(t))} or len(htasks)!=30:raise ValueError("H1 fold inventory")
 write_json(output/"archive_audit.json",dict(k_plan_sha256=sha256(kdir/"plan.json"),recorded_runtime_unchanged=True,
             fixed_inputs_unchanged=True,old_successful_fits=4,policy="read-only recorded hashes; additions are new experiment",h1_input_sha256=sha256(hi)))
 for tid in TASKS:
  sr=next(x for x in htasks if x["task_id"]==tid and x["fold"]==0)
  info=read_json(check(sr["manifest"],sr["sha256"]));task=info["task"]
  for path,h in info["frozen_files"].items():check(path,h)
  pm=check(info["source_prepared_manifest"],info["source_prepared_manifest_sha256"]);prepared=read_json(pm)
  check(info["source_splits_path"],info["source_splits_sha256"]);check(info["labels_path"],info["labels_sha256"])
  raw=prepared["graphs"]["E0"][task];bp=check(pm.parent/raw["path"],raw["sha256"])
  ep=kdir/"prepared"/tid/"B1.gpickle";ep=check(ep,delivered[str(ep)])
  check(kdir/"prepared"/tid/"graph_audit.json",delivered[str(kdir/"prepared"/tid/"graph_audit.json")])
  graphs={"HCG":load(bp),"HCG_DDG":load(ep)};invariants=graph_pair(graphs["HCG"],graphs["HCG_DDG"])
  alignment=assert_e2_alignment(bp,task,seeds(task,0)["constructor"])
  base_graphs={v:dict(path=str(p),sha256=sha256(p),fingerprint=fingerprint(graphs[v]),
       node_attributes_sha256=invariants["node_attributes_sha256"],nodes=len(graphs[v]),edges=graphs[v].number_of_edges())
       for v,p in (("HCG",bp),("HCG_DDG",ep))}
  inventory.append(dict(task_id=tid,graphs=base_graphs,invariants=invariants,baseline_forward_alignment=alignment))
  supports={f:{v:graph_schema_and_support(g,select_split(info,f)) for v,g in graphs.items()} for f in range(folds(tid))}
  for fold in range(folds(tid)):
   href=next(x for x in htasks if x["task_id"]==tid and x["fold"]==fold)
   history=read_json(check(href["manifest"],href["sha256"]))
   if history["task_id"]!=tid or history["fold"]!=fold:raise ValueError("Historical task mismatch")
   cfg=copy.deepcopy(history["config"])
   if cfg!=info["config"]:raise ValueError("Per-fold effective config drift")
   cfgpath=check(history["source_config"],history["source_config_sha256"])
   s=seeds(task,fold);models={}
   for v in VARIANTS:
    seed_all(s["constructor"]);models[v]=make_model(task,graphs[v],"cpu")
   audit=initialize_pair(models["HCG"],models["HCG_DDG"],seed=s["pair"])
   audit.update(pair_version=PAIR_VERSION,semantic_equality=check_common(models))
   folder=dest/tid/("fold_"+str(fold));folder.mkdir(parents=True)
   ap=folder/"initialization_audit.json";write_json(ap,audit);check(ap)
   split=select_split(info,fold)
   doc=dict(task_id=tid,task=task,cohort=info["cohort"],fold=fold,config=cfg,split=split,
    graphs=base_graphs,invariants=invariants,feature=info["feature"],label_version=info["label_version"],
    labels_path=info["labels_path"],labels_sha256=info["labels_sha256"],
    source_prepared_manifest=str(pm),source_prepared_manifest_sha256=sha256(pm),
    source_splits_path=info["source_splits_path"],source_splits_sha256=info["source_splits_sha256"],
    source_task_manifest=str(href["manifest"]),source_task_sha256=href["sha256"],
    source_config=str(cfgpath),source_config_sha256=sha256(cfgpath),fit_seed=s["fit"],seeds=s,
    experiment_version=VERSION,pair_version=PAIR_VERSION,initialization_version=INITIALIZATION_VERSION,
    adapter_version=ADAPTER_VERSION,initialization_audit_path=str(ap),initialization_audit_sha256=sha256(ap),
    initialization={},support=supports[fold],supervision={})
   for v,m in models.items():
    state={k:t.detach().cpu().clone() for k,t in m.state_dict().items()}
    path=folder/(v+"_initial.pt")
    rec=dict(kind="untrained_initial",optimizer_steps=0,task_id=tid,fold=fold,variant=v,
       state_dict=state,state_sha256=tensor_digest(state),fit_seed=s["fit"],pair_version=PAIR_VERSION,
       graph_sha256=base_graphs[v]["sha256"],pairing_sha256=sha256(ap))
    torch.save(rec,str(path));check(path)
    doc["initialization"][v]=dict(path=str(path),sha256=sha256(path),state_sha256=tensor_digest(state))
    doc["supervision"][v]={n:Supervision(m,task,split[n+"_files"]).manifest for n in ("train","val")}
   if fold==0 and task=="node":
    old=read_json(kdir/"prepared"/tid/"task.json")
    oldhash=old["initialization"]["B1"]["state_sha256"];newhash=doc["initialization"]["HCG_DDG"]["state_sha256"]
    reuse.append(dict(task_id=tid,old_tensor_sha256=oldhash,new_tensor_sha256=newhash,
       equal=oldhash==newhash,reused=False,reason="new no-DDG baseline anchors pair; old E3b-anchored fit is historical"))
   manifest=folder/"task.json";write_json(manifest,doc);check(manifest)
   refs.append(dict(task_id=tid,fold=fold,manifest=str(manifest),sha256=sha256(manifest)))
   print("PREPARED",tid,"fold",fold,"fresh HCG/HCG_DDG",flush=True)
   del models,m,state,rec;gc.collect()
  del graphs;gc.collect()
 write_json(output/"input_inventory.json",inventory);write_json(output/"prior_fold0_audit.json",reuse)
 check(output/"input_inventory.json");check(output/"prior_fold0_audit.json");check(output/"archive_audit.json")
 plan=dict(version=VERSION,pair_version=PAIR_VERSION,head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip(),
   runtime=runtime_hashes(),frozen=assets,jobs=expected_jobs(),tasks=refs,device="cuda:0",threads=2,
   maximum_epochs=50,execution_authorized=True,score_role="cv_validation",protocol="paper_kfold",
   initialization_version=INITIALIZATION_VERSION,source_stage_k_plan_sha256=sha256(kdir/"plan.json"),
   policy="60 fresh paired fits; no trained initialization; first pair gate; task completeness gates; stop on error")
 write_json(output/"plan.json",plan);write_json(output/"plan.seal.json",{"sha256":sha256(output/"plan.json")})
 verify_plan(output);return plan
