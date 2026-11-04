"""Pair invariants and complete-fit verification, independent of F1 direction."""
from collections import Counter
import math
from pathlib import Path
import torch
from scripts.DFG.graph_audit import frozen
from scripts.DFG.state.stage_f import FORWARD_RELATIONS
from scripts.DFG.experiments.runtime import assert_disconnected_files
from scripts.DFG.experiments.e23_pilot.model import semantic_state,_independent_storage
from .common import *
def graph_pair(base,enhanced):
 assert_disconnected_files(base);assert_disconnected_files(enhanced)
 if frozen(list(base.nodes(data=True)))!=frozen(list(enhanced.nodes(data=True))):raise ValueError("Nodes/features/labels differ")
 if any(a["edge_type"] in FORWARD_RELATIONS for _,_,a in base.edges(data=True)):raise ValueError("HCG baseline contains DDG")
 before=Counter((u,v,k,frozen(a)) for u,v,k,a in base.edges(keys=True,data=True))
 after=Counter((u,v,k,frozen(a)) for u,v,k,a in enhanced.edges(keys=True,data=True) if a["edge_type"] not in FORWARD_RELATIONS)
 if before!=after:raise ValueError("Base CFG/CG edge attributes or IDs changed")
 added=Counter(a["edge_type"] for _,_,a in enhanced.edges(data=True) if a["edge_type"] in FORWARD_RELATIONS)
 if not added or not added["DATA_DEF_USE"]:raise ValueError("Missing frozen scalar intervention")
 return dict(nodes=len(base),base_edges=base.number_of_edges(),enhanced_edges=enhanced.number_of_edges(),
             added_relations=dict(added),node_attributes_sha256=digest(frozen(list(base.nodes(data=True)))),base_preserved=True)
def check_common(models):
 a,b=semantic_state(models["HCG"]),semantic_state(models["HCG_DDG"])
 if not set(a)<=set(b) or any(not torch.equal(a[k],b[k]) for k in a):raise ValueError("Common initial weights differ")
 _independent_storage(models)
 return dict(shared_tensor_count=len(a),shared_semantic_sha256=tensor_digest(a),exact=True,independent_storage=True)
def check_initial(record,info,variant):
 init=info["initialization"][variant]
 expected=dict(kind="untrained_initial",optimizer_steps=0,task_id=info["task_id"],fold=info["fold"],
               variant=variant,fit_seed=info["fit_seed"],pair_version=PAIR_VERSION,
               graph_sha256=info["graphs"][variant]["sha256"],pairing_sha256=info["initialization_audit_sha256"])
 if any(record.get(k)!=v for k,v in expected.items()):raise ValueError("Initial identity/binding drift")
 if tensor_digest(record["state_dict"])!=init["state_sha256"]:raise ValueError("Initial tensor drift")
def completed(output,job,plan):
 found=[]
 for p in sorted(job_dir(output,job).glob("attempt_*/receipt.json")):
  rec=read_json(p)
  if any(rec.get(k)!=v for k,v in dict(job,status="complete",plan_sha256=digest(plan)).items()):raise ValueError("Receipt identity drift")
  for name,h in rec["artifacts"].items():
   if sha256(p.parent/name)!=h:raise ValueError("Result artifact changed")
  d=read_json(p.parent/"result.json");binding=read_json(p.parent/"binding.json")
  if d["status"]!="complete" or d["score_role"]!="cv_validation":raise ValueError("Invalid result role")
  if d["checkpoint_roundtrip_exact"]!={"best":True,"last":True}:raise ValueError("Reload mismatch")
  if not d["no_parameters_created_during_training_or_scoring"]:raise ValueError("Parameter drift")
  if not 1<=d["history_rows"]<=50:raise ValueError("Epoch range mismatch")
  if binding["plan_sha256"]!=digest(plan) or binding["task_id"]!=job["task_id"] or binding["variant"]!=job["variant"] or binding["split"]["fold"]!=job["fold"]:raise ValueError("Checkpoint batch binding mismatch")
  hist=[__import__("json").loads(x) for x in (p.parent/"history.jsonl").read_text().splitlines()]
  if len(hist)!=d["history_rows"] or any(not math.isfinite(x[k]) for x in hist for k in ("train_loss","cv_validation_loss")):raise ValueError("Nonfinite/incomplete history")
  found.append(p.parent)
 if len(found)>1:raise ValueError("Duplicate successful fit")
 return found[0] if found else None
