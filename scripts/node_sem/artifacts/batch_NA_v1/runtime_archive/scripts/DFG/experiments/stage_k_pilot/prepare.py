"""Build one overall candidate, then seal only two node fold-0 paired tasks."""
import copy,pickle,subprocess
from collections import Counter
from pathlib import Path
import torch
from scripts.DFG.graph_audit import fingerprint,frozen
from scripts.DFG.state.stage_k.pipeline import prepare_graph
from scripts.DFG.state.stage_j.configuration import DDGConfig
from scripts.DFG.state.stage_f.model_adapter import build_dgl
from scripts.DFG.state.stage_f.initialization import initialize_pair,INITIALIZATION_VERSION
from scripts.DFG.experiments.e23_pilot.model import make_model,semantic_state
from scripts.DFG.experiments.e23_pilot.runtime import graph_schema_and_support,Supervision
from .common import *
def load(path):
 with Path(path).open("rb") as f:return pickle.load(f)
def typed(g):return Counter((s,t,d["edge_type"]) for s,t,d in g.edges(data=True))
def prepare(output):
 output=Path(output);target=output/"prepared"
 if target.exists() or (output/"plan.json").exists():raise ValueError("No overwrite")
 target.mkdir(parents=True)
 inputs={};summaries=[];jobs=[];taskrefs=[]
 def check(path,expected=None):
  path=Path(path).resolve();h=sha256(path)
  if expected is not None and h!=expected:raise ValueError("Input drift: "+str(path))
  inputs[str(path)]=h;return path
 src=check(ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/e23_pilot_v1/input_manifest.json")
 prior=ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build"
 prior_receipt=read_json(check(prior/"receipt.json"))
 torch.set_num_threads(2)
 for task in read_json(src)["tasks"]:
  info=read_json(check(task["manifest"],task["sha256"]));tid=info["task_id"]
  for path,h in info["frozen_files"].items():check(path,h)
  for k in ("source_prepared_manifest","source_splits_path","labels_path"):check(info[k])
  source_manifest=prior/tid/"sources.json"
  check(source_manifest,prior_receipt["files"][str(source_manifest.relative_to(prior))])
  records=read_json(source_manifest)["sources"];sources={};metadata={}
  for name,rec in records.items():
   sources[name]=check(rec["path"],rec["sha256"]).read_bytes().decode("utf8")
   metadata[name]=rec.get("metadata")
  base=load(check(info["graphs"]["E2"]["path"],info["graphs"]["E2"]["sha256"]))
  old=load(check(info["graphs"]["E3b"]["path"],info["graphs"]["E3b"]["sha256"]))
  jpath=prior/tid/"modifiers/enhanced.gpickle"
  jgraph=load(check(jpath,prior_receipt["files"][str(jpath.relative_to(prior))]))
  print(tid,"building overall candidate",flush=True)
  enhanced,audit=prepare_graph(base,sources,DDGConfig(recovery="modifiers"),metadata)
  if typed(jgraph)-typed(enhanced):raise ValueError("Supported profile removed old J relation")
  if frozen(list(old.nodes(data=True)))!=frozen(list(enhanced.nodes(data=True))):raise ValueError("Nodes/features/labels drift")
  dg,_=build_dgl(enhanced)
  for rel in ("DATA_DEF_USE","STATE_DEF_USE","STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE"):
   assert sum(dg.num_edges(c) for c in dg.canonical_etypes if c[1]==rel)==sum(d["edge_type"]==rel for _,_,d in enhanced.edges(data=True))
  folder=target/tid;folder.mkdir()
  graphpath=folder/"B1.gpickle"
  with graphpath.open("wb") as f:pickle.dump(enhanced,f,pickle.HIGHEST_PROTOCOL)
  write_json(folder/"graph_audit.json",audit);check(graphpath);check(folder/"graph_audit.json")
  funcs=[x for v in audit["files"].values() for x in v["functions"]]
  summary={"task_id":tid,"files":len(records),"nodes":len(enhanced),"edges":enhanced.number_of_edges(),
           "domain_restricted_files":sum(v.get("version_evidence",{}).get("domain_restricted",False) for v in audit["files"].values()),
           "analyzed_functions":len(funcs),"supported_functions":sum(x["after"]!="function_fallback" for x in funcs),
           "added_relations_vs_J":sum((typed(enhanced)-typed(jgraph)).values()),
           "added_relations_vs_E3b":sum((typed(enhanced)-typed(old)).values()),
           "relations":dict(Counter(d["edge_type"] for _,_,d in enhanced.edges(data=True)))}
  summaries.append(summary);print(summary,flush=True)
  if tid not in TASKS:continue
  assert info["task"]=="node" and info["fold"]==0 and info["config"]["seed"]==1
  newinfo=copy.deepcopy(info);newinfo["graphs"]={
   "B0":copy.deepcopy(info["graphs"]["E3b"]),
   "B1":{"path":str(graphpath),"sha256":sha256(graphpath),"fingerprint":fingerprint(enhanced),
         "node_attributes_sha256":digest(frozen(list(enhanced.nodes(data=True))))}}
  newinfo.update(experiment_version=VERSION,overall_comparison="old E3b graph versus combined coverage/profile upgrade",
                 source_task_manifest=str(task["manifest"]),source_task_sha256=task["sha256"])
  models={}
  for v in VARIANTS:
   seed_all(info["initialization_seed"]-77)
   models[v]=make_model("node",newinfo["graphs"][v]["path"],"cpu")
  pairing=initialize_pair(models["B0"],models["B1"],seed=info["initialization_seed"])
  a,b=semantic_state(models["B0"]),semantic_state(models["B1"])
  assert set(a)<=set(b) and all(torch.equal(a[k],b[k]) for k in a)
  write_json(folder/"initialization_audit.json",pairing);check(folder/"initialization_audit.json")
  newinfo["initialization_audit_sha256"]=sha256(folder/"initialization_audit.json")
  newinfo["initialization"]={};newinfo["support"]={};newinfo["supervision"]={}
  for v,m in models.items():
   state={k:t.detach().cpu().clone() for k,t in m.state_dict().items()}
   path=folder/(v+"_initial.pt")
   torch.save({"kind":"untrained_initial","optimizer_steps":0,"task_id":tid,"fold":0,"variant":v,
               "state_dict":state,"state_sha256":tensor_digest(state),"fit_seed":info["fit_seed"]},str(path))
   check(path)
   newinfo["initialization"][v]={"path":str(path),"sha256":sha256(path),"state_sha256":tensor_digest(state)}
   newinfo["support"][v]=graph_schema_and_support(m.nx_graph,info["split"])
   newinfo["supervision"][v]={n:Supervision(m,"node",info["split"][n+"_files"]).manifest for n in ("train","val")}
  write_json(folder/"task.json",newinfo);check(folder/"task.json")
  taskrefs.append({"task_id":tid,"manifest":str(folder/"task.json"),"sha256":sha256(folder/"task.json")})
  del models
 plan={"version":VERSION,"head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip(),
       "runtime":runtime_hashes(),"frozen":inputs,"jobs":expected_jobs(),"tasks":taskrefs,
       "device":"cuda:0","threads":2,"max_epochs":50,"execution_authorized":True,
       "score_role":"cv_validation","initialization_version":INITIALIZATION_VERSION,
       "policy":"fresh paired overall comparison; no per-detail ablations; stop on failure"}
 write_json(output/"graph_summary.json",summaries)
 write_json(output/"plan.json",plan);write_json(output/"plan.seal.json",{"sha256":sha256(output/"plan.json")})
 verify_plan(output)
 return summaries
