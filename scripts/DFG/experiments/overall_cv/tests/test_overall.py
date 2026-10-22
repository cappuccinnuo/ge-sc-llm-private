import copy,json
from pathlib import Path
from types import SimpleNamespace
import networkx as nx
import numpy as np
import pytest
import torch
from scripts.DFG.experiments.overall_cv import common,checks,checkpoint,training,control,report
from scripts.DFG.experiments.overall_cv.common import *
from scripts.DFG.experiments.e23_pilot import training as old
from scripts.DFG.experiments.e23_pilot.model import make_model,validate_registration,ADAPTER_VERSION
from scripts.DFG.experiments.e23_pilot.runtime import graph_schema_and_support,Supervision
from scripts.DFG.state.stage_f.initialization import initialize_pair,INITIALIZATION_VERSION
from scripts.DFG.experiments.paper_protocol import NAME,VERSION as PV,FORWARD_SCOPE,SCORE_ROLE
from scripts.DFG.experiments.e23_cv.prepare import select_split,seeds

def graphs():
 g=nx.MultiDiGraph()
 for n in range(6):
  g.add_node(n,node_type="expression_statement",source_file="a.sol" if n<3 else "b.sol",
    code="statement"+str(n%3),label="statement",node_source_code_lines=[n%3+1],
    node_info_vulnerabilities=None if n%2==0 else [{"category":"reentrancy","lines":[2]}],token=np.arange(8,dtype=np.float32)+n)
 for u,v in [(0,1),(1,2),(3,4),(4,5)]:g.add_edge(u,v,edge_type="next_line")
 h=copy.deepcopy(g);h.add_edge(0,2,edge_type="DATA_DEF_USE");h.add_edge(3,5,edge_type="DATA_DEF_USE")
 return g,h

def binding(m,task,variant,split):
 return dict(protocol=NAME,protocol_version=PV,forward_scope=FORWARD_SCOPE,score_role=SCORE_ROLE,
  experiment_version=VERSION,pair_version=PAIR_VERSION,initialization_version=INITIALIZATION_VERSION,
  adapter_version=ADAPTER_VERSION,task_id="reentrancy_author_"+task,task=task,variant=variant,
  split=split,registered_schema=validate_registration(m))

def test_matrix_and_seeds():
 jobs=expected_jobs()
 assert len(jobs)==60 and len({identity(j) for j in jobs})==60
 assert [sum(j["task_id"]==t for j in jobs) for t in TASKS]==[10,10,20,20]
 assert jobs[0]==dict(task_id=TASKS[0],fold=0,variant="HCG")
 assert jobs[1]["variant"]=="HCG_DDG" and jobs[-1]["fold"]==9
 for task,k in [("node",10),("contract",5)]:
  for f in range(k):assert seeds(task,f)["fit"]==1000000+seeds(task,f)["constructor"]

@pytest.mark.parametrize("tid",TASKS)
def test_original_all_frozen_splits(tid):
 p=ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/e23_pilot_v1/initialization"/tid/"task_manifest.json"
 info=read_json(p);doc=read_json(info["source_splits_path"]);seen=set()
 for f in range(folds(tid)):
  split=select_split(info,f)
  assert split==doc["folds"][f] and not set(split["train_files"])&set(split["val_files"])
  assert not seen&set(split["val_files"]);seen.update(split["val_files"])
 assert seen==set(doc["files"])

def test_pair_invariants_and_semantic_initialization():
 g,h=graphs();a=checks.graph_pair(g,h);assert a["added_relations"]=={"DATA_DEF_USE":2}
 models={}
 for v,graph in zip(VARIANTS,(g,h)):
  seed_all(1);models[v]=make_model("node",graph,"cpu",hidden_size=8,layers=1,heads=2)
 initialize_pair(models["HCG"],models["HCG_DDG"],77)
 assert checks.check_common(models)["exact"]
 assert not any(c[1]=="DATA_DEF_USE" for c in models["HCG"].etypes_dict)
 assert any(c[1]=="DATA_DEF_USE" for c in models["HCG_DDG"].etypes_dict)

@pytest.mark.parametrize("what",["label","token","node","base_edge","baseline_ddg","cross_file"])
def test_bad_pair_rejected(what):
 g,h=graphs()
 if what=="label":h.nodes[0]["node_info_vulnerabilities"]=[{}]
 elif what=="token":h.nodes[0]["token"][0]+=1
 elif what=="node":h.remove_node(0)
 elif what=="base_edge":h.remove_edge(0,1)
 elif what=="baseline_ddg":g.add_edge(0,2,edge_type="DATA_DEF_USE")
 else:h.add_edge(0,4,edge_type="DATA_DEF_USE")
 with pytest.raises((ValueError,AssertionError)):checks.graph_pair(g,h)

def test_old_training_functions_are_not_mutated():
 assert training.FIT.__code__ is old.FIT.__code__
 assert training.fit.__code__ is old.fit.__code__
 assert old.fit.__globals__["FIT"] is old.FIT
 assert old.FIT.__globals__["save_checkpoint"] is not checkpoint.save_checkpoint

@pytest.mark.parametrize("task",["node","contract"])
def test_actual_cpu_fit_gradient_checkpoint_and_shared_loop(tmp_path,task):
 torch.set_num_threads(2);g,h=graphs();split=dict(fold=0,train_files=["a.sol"],val_files=["b.sol"])
 models={}
 for v,gr in zip(VARIANTS,(g,h)):
  seed_all(10);models[v]=make_model(task,gr,"cpu",hidden_size=8,layers=1,heads=2)
 initialize_pair(models["HCG"],models["HCG_DDG"],87)
 cfg=dict(initial_lr=.0002,weight_decay=0.,max_lr=.005,schedule_epochs=50,div_factor=25,final_div_factor=1,
          cycle_momentum=True,patience=7,delta=.001,maximum_training_epochs=2,mode="full")
 for v,m in models.items():
  seed_all(1000010);parts={n:Supervision(m,task,split[n+"_files"]) for n in ("train","val")}
  s=graph_schema_and_support(m.nx_graph,split);b=binding(m,task,v,split)
  d=training.FIT(m,parts,task,{"a.sol":0,"b.sol":1},cfg,tmp_path/v,b,m.original_graph_node_ids,s)
  assert d["history_rows"]==2 and all(d["checkpoint_roundtrip_exact"].values())
  assert d["gradient_audit"]["backbone_update_l1"]>0
  assert d["no_parameters_created_during_training_or_scoring"]
  assert len(read_json(tmp_path/v/"cv_validation_predictions.json"))==(3 if task=="node" else 1)
  if v=="HCG":assert d["gradient_audit"]["epochs"][0]["enhancement_relations"]==[]
  else:assert d["gradient_audit"]["epochs"][0]["enhancement_relations"][0]["message_gradient_l1"]>0
  wrong=copy.deepcopy(b);wrong["split"]["fold"]=1
  with pytest.raises(ValueError):checkpoint.restore_checkpoint(tmp_path/v/"best.pt",m,wrong,d["checkpoint_sha256"]["best"])

@pytest.mark.parametrize("field,value",[("variant","B1"),("task_id","unknown"),("score_role","independent_test"),("pair_version","old")])
def test_wrong_bindings_rejected(field,value):
 m=make_model("node",graphs()[0],"cpu",hidden_size=8,layers=1,heads=2)
 b=binding(m,"node","HCG",dict(fold=0));b[field]=value
 with pytest.raises(ValueError):checkpoint.validate_binding(m,b)

def test_unregistered_schema_rejected():
 m=make_model("node",graphs()[0],"cpu",hidden_size=8,layers=1,heads=2)
 b=binding(m,"node","HCG",dict(fold=0))
 c=next(iter(m.etypes_dict));m.etypes_dict[c]=100
 with pytest.raises((ValueError,AssertionError)):checkpoint.validate_binding(m,b)

def test_initial_binding():
 state={"weight":torch.ones(3)}
 info=dict(task_id=TASKS[0],fold=2,fit_seed=1011002,graphs={"HCG":{"sha256":"g"}},initialization_audit_sha256="p",
   initialization={"HCG":{"state_sha256":tensor_digest(state)}})
 record=dict(kind="untrained_initial",optimizer_steps=0,task_id=TASKS[0],fold=2,variant="HCG",
   fit_seed=1011002,pair_version=PAIR_VERSION,graph_sha256="g",pairing_sha256="p",state_dict=state)
 checks.check_initial(record,info,"HCG")
 for k,v in [("optimizer_steps",1),("fold",3),("graph_sha256","wrong"),("pairing_sha256","wrong"),("fit_seed",1)]:
  with pytest.raises(ValueError):checks.check_initial(dict(record,**{k:v}),info,"HCG")
 with pytest.raises(ValueError):checks.check_initial(dict(record,state_dict={"weight":torch.zeros(3)}),info,"HCG")

def pred(file,node,target=1):
 return dict(file=file,original_graph_node_id=node,target=target,best=target,last=target,
             best_positive_probability=.8,last_positive_probability=.7,score_role="cv_validation")
def test_summary_identity_role_completeness():
 a,b=pred("a",1),pred("b",2,0);expected={report.key(a):1,report.key(b):0}
 assert report.checked_predictions([b,a],expected)==[a,b]
 for bad in [[a,a],[a],[dict(a,target=0),b],[dict(a,score_role="test"),b]]:
  with pytest.raises(ValueError):report.checked_predictions(bad,expected)
 with pytest.raises(ValueError):report.pooled({0:[a]},2)
 with pytest.raises(ValueError):report.pooled({0:[a],1:[a]},2)
 stat=report.aggregate([dict(t="x",buggy_f1=0),dict(t="x",buggy_f1=100)],("t",),("buggy_f1",))[0]
 assert stat["buggy_f1_mean"]==50 and stat["buggy_f1_sample_std"]==pytest.approx(70.710678)

def test_success_reuse_and_failure_requires_explicit_retry(tmp_path,monkeypatch):
 jobs=expected_jobs()[:2];plan={"jobs":jobs};success=set();calls=[]
 monkeypatch.setattr(control,"verify_plan",lambda _:plan)
 monkeypatch.setattr(control,"completed",lambda output,job,plan:Path("accepted") if identity(job) in success else None)
 def fake(cmd,**kw):
  task=cmd[cmd.index("--task")+1];fold=int(cmd[cmd.index("--fold")+1]);variant=cmd[cmd.index("--variant")+1]
  j=dict(task_id=task,fold=fold,variant=variant);calls.append(identity(j))
  if len(calls)==1:return SimpleNamespace(returncode=1)
  success.add(identity(j));return SimpleNamespace(returncode=0)
 monkeypatch.setattr(control.subprocess,"run",fake)
 with pytest.raises(RuntimeError,match="Worker failed"):control.run(tmp_path,first_pair=True)
 with pytest.raises(RuntimeError,match="explicit retry"):control.run(tmp_path,first_pair=True)
 assert len(calls)==1
 control.run(tmp_path,retry=identity(jobs[0]),first_pair=True);assert len(calls)==3
 control.run(tmp_path,first_pair=True);assert len(calls)==3
 assert read_json(tmp_path/"first_pair_acceptance.json")["status"]=="passed"
