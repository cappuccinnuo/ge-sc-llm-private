"""Synthetic interface tests; no Solidity compilation or formal-training claims."""
import copy,json
from pathlib import Path
from types import SimpleNamespace
import pytest
import torch
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.experiments.common import tensor_digest,write_json,sha256,digest
from scripts.DFG.experiments.e23_pilot.tests.test_model import graphs
from scripts.DFG.experiments.e23_pilot import model as old_model,training as old_training
from scripts.DFG.experiments.paper_protocol import NAME,VERSION as PV,FORWARD_SCOPE,SCORE_ROLE
from scripts.DFG.experiments.guard_extension import model,runtime,training,checkpoint,checks,common,control,archive,report
from scripts.DFG.experiments.guard_extension import VERSION,PAIR_VERSION,VARIANT

@pytest.fixture(autouse=True)
def cpu_threads():
    previous=torch.get_num_threads();torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)

def pair(task="node",val_only=False):
    base=graphs()["E3b"];candidate=copy.deepcopy(base)
    for file in (("val.sol",) if val_only else ("train.sol","val.sol")):
        candidate.add_edge(file+":0",file+":1",edge_type="CONTROL_DEPENDENCE")
    torch.manual_seed(12);a=old_model.make_model(task,base,hidden_size=8,layers=1,heads=2)
    torch.manual_seed(12);b=model.make_model(task,candidate,hidden_size=8,layers=1,heads=2)
    expected=dict(task_id="reentrancy_author_"+task,fold=0,variant="HCG_DDG",fit_seed=1000012,
                  pair_version="prior",graph_sha256="graph",pairing_sha256="pair")
    state={k:v.detach().clone() for k,v in a.state_dict().items()}
    rec=dict(expected,kind="untrained_initial",optimizer_steps=0,state_dict=state,state_sha256=tensor_digest(state))
    return a,b,rec,expected

def binding(m,task,split):
    return dict(protocol=NAME,protocol_version=PV,forward_scope=FORWARD_SCOPE,score_role=SCORE_ROLE,
        experiment_version=VERSION,pair_version=PAIR_VERSION,initialization_version=model.INITIALIZATION_VERSION,
        adapter_version=model.ADAPTER_VERSION,task_id="reentrancy_author_"+task,task=task,variant=VARIANT,
        split=split,registered_schema=model.validate_registration(m),
        forward_only_enhancement_relations=sorted(model.FORWARD_RELATIONS))

def test_matrix_and_frozen_training_functions():
    jobs=common.expected_jobs()
    assert len(jobs)==30 and len({common.identity(j) for j in jobs})==30
    assert [sum(j["task_id"]==t for j in jobs) for t in common.TASKS]==[5,5,10,10]
    assert {j["variant"] for j in jobs}=={VARIANT}
    assert training.FIT.__code__ is old_training.FIT.__code__
    assert training.fit.__code__ is old_training.fit.__code__
    assert old_training.FIT.__globals__["save_checkpoint"] is not checkpoint.save_checkpoint
    assert model._construct.__code__ is old_model._construct.__code__

@pytest.mark.parametrize("task",["node","contract"])
def test_old_model_forward_unchanged_when_no_guard(task):
    source=graphs()["E3b"]
    torch.manual_seed(5);old=old_model.make_model(task,source,hidden_size=8,layers=1,heads=2)
    torch.manual_seed(5);new=model.make_model(task,source,hidden_size=8,layers=1,heads=2)
    assert tensor_digest(old.state_dict())==tensor_digest(new.state_dict())
    assert new.etypes_dict==old.etypes_dict
    assert new.forward.__func__ is old.forward.__func__
    old.eval();new.eval()
    with torch.no_grad():
        a=old() if task=="node" else old(["train.sol","val.sol"])[0]
        b=new() if task=="node" else new(["train.sol","val.sol"])[0]
        assert torch.equal(a,b)

@pytest.mark.parametrize("task",["node","contract"])
def test_common_initials_equal_all_canonical_slices_and_reproducible_new(task):
    a,b,rec,expected=pair(task);before=tensor_digest(a.state_dict())
    audit=model.extend_saved_initial(a,b,rec,expected,seed=89)
    assert audit["all_common_semantic_tensors_equal"]
    assert before==tensor_digest(a.state_dict())
    sa,sb=model.semantic_state(a),model.semantic_state(b)
    assert set(sa)<=set(sb) and all(torch.equal(sa[k],sb[k]) for k in sa)
    a2,b2,r2,e2=pair(task);model.extend_saved_initial(a2,b2,r2,e2,seed=89)
    assert tensor_digest(b.state_dict())==tensor_digest(b2.state_dict())
    a3,b3,r3,e3=pair(task);model.extend_saved_initial(a3,b3,r3,e3,seed=90)
    s3=model.semantic_state(b3)
    assert all(torch.equal(sa[k],s3[k]) for k in sa)
    assert any(not torch.equal(sb[k],s3[k]) for k in set(sb)-set(sa))

@pytest.mark.parametrize("change",["steps","kind","fold","state","variant"])
def test_trained_or_mismatched_initial_rejected(change):
    a,b,r,e=pair()
    if change=="steps":r["optimizer_steps"]=1
    elif change=="kind":r["kind"]="best"
    elif change=="fold":r["fold"]=1
    elif change=="state":r["state_dict"]["classify.bias"][0]+=1
    else:r["variant"]="HCG"
    with pytest.raises(ValueError):model.extend_saved_initial(a,b,r,e,89)

def test_guard_direction_parallel_edges_and_frozen_nodes():
    a,b,r,e=pair();source=graphs()["E3b"];original=fingerprint(source)
    graph=copy.deepcopy(source);graph.add_edge("train.sol:0","train.sol:1",edge_type="CONTROL_DEPENDENCE")
    before=fingerprint(graph);m=model.make_model("node",graph,hidden_size=8,layers=1,heads=2)
    assert fingerprint(graph)==before and fingerprint(source)==original
    assert ("z","CONTROL_DEPENDENCE","a") in m.etypes_dict
    assert ("a","CONTROL_DEPENDENCE","z") not in m.etypes_dict
    assert ("z","next","a") in m.etypes_dict and ("a","next","z") in m.etypes_dict
    assert ("z","STATE_DEF_USE","a") in m.etypes_dict
    assert sum(m.symmetrical_global_graph.num_edges(c) for c in m.etypes_dict if c[1]=="CONTROL_DEPENDENCE")==1
    assert m.original_graph_node_ids==list(source)

@pytest.mark.parametrize("task",["node","contract"])
def test_supported_guard_gradient_and_validation_only_registered_relation(task):
    for val_only in (False,True):
        a,b,r,e=pair(task,val_only);model.extend_saved_initial(a,b,r,e,89)
        split=dict(fold=0,train_files=["train.sol"],val_files=["val.sol"])
        support=runtime.graph_schema_and_support(b.nx_graph,split)
        train=runtime.Supervision(b,task,["train.sol"])
        loss=torch.nn.functional.cross_entropy(train.forward(b),train.targets(b,{"train.sol":1}))
        loss.backward();audit=runtime.gradient_audit(b,support)
        rows=[x for x in audit["enhancement_relations"] if x["canonical"][1]=="CONTROL_DEPENDENCE"]
        assert len(rows)==1
        assert rows[0]["train_edges"]==(0 if val_only else 1)
        assert rows[0]["message_gradient_l1"]==0 if val_only else rows[0]["message_gradient_l1"]>0
        before={k:id(v) for k,v in b.named_parameters()}
        b.eval()
        with torch.no_grad():assert torch.isfinite(runtime.Supervision(b,task,["val.sol"]).forward(b)).all()
        assert before=={k:id(v) for k,v in b.named_parameters()}

@pytest.mark.parametrize("change",["token","label","schema","edge_id","edge"])
def test_registration_rejects_input_drift(change):
    _,b,_,_=pair()
    if change=="token":b.symmetrical_global_graph.nodes["z"].data["inp"][0,0]+=1
    elif change=="label":b.node_labels[0]=1-b.node_labels[0]
    elif change=="schema":b.etypes_dict.pop(next(iter(b.etypes_dict)))
    elif change=="edge_id":b.symmetrical_global_graph.edges[next(iter(b.etypes_dict))].data["id"][0]=999
    else:b.nx_graph.remove_edge(0,1,0)
    with pytest.raises((ValueError,AssertionError)):model.validate_registration(b)

@pytest.mark.parametrize("task",["node","contract"])
def test_cpu_fit_best_last_roundtrip_and_population(tmp_path,task):
    a,b,r,e=pair(task);model.extend_saved_initial(a,b,r,e,89)
    split=dict(fold=0,train_files=["train.sol"],val_files=["val.sol"])
    parts={n:runtime.Supervision(b,task,split[n+"_files"]) for n in ("train","val")}
    support=runtime.graph_schema_and_support(b.nx_graph,split);bind=binding(b,task,split)
    cfg=dict(initial_lr=.0002,weight_decay=0.,max_lr=.005,schedule_epochs=50,div_factor=25,
        final_div_factor=1,cycle_momentum=True,patience=7,delta=.001,maximum_training_epochs=2,mode="full")
    dest=tmp_path/task
    result=training.FIT(b,parts,task,{"train.sol":1,"val.sol":0},cfg,dest,bind,b.original_graph_node_ids,support)
    assert result["history_rows"]==2 and all(result["checkpoint_roundtrip_exact"].values())
    assert result["no_parameters_created_during_training_or_scoring"]
    assert result["gradient_audit"]["backbone_update_l1"]>0
    pred=json.loads((dest/"cv_validation_predictions.json").read_text())
    assert len(pred)==(3 if task=="node" else 1)
    assert all(x["file"]=="val.sol" for x in pred)
    bad=copy.deepcopy(bind);bad["score_role"]="independent_test"
    with pytest.raises(ValueError):checkpoint.restore_checkpoint(dest/"best.pt",b,bad,result["checkpoint_sha256"]["best"])


def test_readonly_archive_accepts_additions_rejects_changed_recorded_source(tmp_path,monkeypatch):
    source=tmp_path/"archive";source.mkdir();oldcode=tmp_path/"old.py";oldcode.write_text("original")
    job=dict(task_id=common.TASKS[0],fold=0,variant="HCG")
    plan=dict(version=archive.OLD_VERSION,pair_version=archive.OLD_PAIR,jobs=[job],
              runtime={str(oldcode):sha256(oldcode)},frozen={})
    write_json(source/"plan.json",plan);write_json(source/"plan.seal.json",dict(sha256=sha256(source/"plan.json")))
    result=tmp_path/"result";result.mkdir();write_json(result/"receipt.json",{})
    monkeypatch.setattr(archive,"old_jobs",lambda:[job])
    monkeypatch.setattr(archive.prior_checks,"completed",lambda *args:result)
    oldseal=(source/"plan.seal.json").read_bytes()
    (tmp_path/"new_sidecar.py").write_text("new")
    _,audit=archive.verify_archive(source)
    assert audit["successful_fits"]==1 and (source/"plan.seal.json").read_bytes()==oldseal
    oldcode.write_text("changed")
    with pytest.raises(ValueError,match="changed"):archive.verify_archive(source)


def test_controller_serial_reuse_and_explicit_failure_retry(tmp_path,monkeypatch):
    jobs=[j for j in common.expected_jobs() if j["fold"]==0];plan={"jobs":jobs}
    success=set();calls=[]
    monkeypatch.setattr(control,"verify_plan",lambda _:plan)
    monkeypatch.setattr(control,"completed",lambda output,j,p:Path("ok") if common.identity(j) in success else None)
    def fake(command,**kwargs):
        task=command[command.index("--task")+1];fold=int(command[command.index("--fold")+1]);variant=command[command.index("--variant")+1]
        job=dict(task_id=task,fold=fold,variant=variant);calls.append(common.identity(job))
        if len(calls)==1:return SimpleNamespace(returncode=1)
        success.add(common.identity(job));return SimpleNamespace(returncode=0)
    monkeypatch.setattr(control.subprocess,"run",fake)
    with pytest.raises(RuntimeError,match="Worker failed"):control.run(tmp_path,fold0=True)
    with pytest.raises(RuntimeError,match="explicit retry"):control.run(tmp_path,fold0=True)
    assert len(calls)==1
    control.run(tmp_path,retry=common.identity(jobs[0]),fold0=True)
    assert len(calls)==5
    control.run(tmp_path,fold0=True);assert len(calls)==5
    assert json.loads((tmp_path/"fold0_acceptance.json").read_text())["status"]=="passed"


def test_immutable_result_receipt_and_scoring_population(tmp_path):
    job=common.expected_jobs()[0];plan={"version":"synthetic"};dest=common.job_dir(tmp_path,job)/"attempt_001"
    dest.mkdir(parents=True)
    write_json(dest/"result.json",{})
    receipt=dict(job,status="complete",plan_sha256=digest(plan),artifacts={"result.json":sha256(dest/"result.json")})
    write_json(dest/"receipt.json",receipt)
    write_json(dest/"result.json",{"changed":True})
    with pytest.raises(ValueError,match="artifact changed"):checks.completed(tmp_path,job,plan)
    row=dict(file="f.sol",original_graph_node_id=3,target=1,best=1,last=0,
        best_positive_probability=.8,last_positive_probability=.3,score_role="cv_validation")
    expected={("f.sol","3"):1}
    assert report.checked_predictions([row],expected)==[row]
    for bad in ([row,row],[],[dict(row,target=0)],[dict(row,score_role="test")]):
        with pytest.raises(ValueError):report.checked_predictions(bad,expected)


def test_three_variant_summary_recomputes_frozen_labels_and_rejects_tamper(tmp_path,monkeypatch):
    import networkx as nx
    from scripts.labeling_v2.safe_graph import write_graph
    from scripts.DFG.experiments.common import metrics
    tid=common.TASKS[0];files=["file%d.sol"%i for i in range(5)]
    labels={f:int(i%2==0) for i,f in enumerate(files)}
    graph=nx.MultiDiGraph()
    for i,f in enumerate(files):graph.add_node(i,source_file=f,node_info_vulnerabilities=[{}] if labels[f] else None)
    gp=tmp_path/"graph.gpickle";write_graph(graph,gp)
    lp=tmp_path/"labels.json";write_json(lp,[dict(contract_name=f,targets=y) for f,y in labels.items()])
    pm=tmp_path/"prepared.json";write_json(pm,dict(sources={f:dict(sha256="source-"+f) for f in files}))
    sp=tmp_path/"splits.json";write_json(sp,dict(files=files))
    taskrefs=[];locations={}
    for fold,file in enumerate(files):
        info=dict(task_id=tid,fold=fold,task="contract",cohort="reentrancy_author",graphs={VARIANT:dict(path=str(gp))},
            split=dict(fold=fold,train_files=[f for f in files if f!=file],val_files=[file]),labels_path=str(lp),
            source_prepared_manifest=str(pm),source_splits_path=str(sp))
        ip=tmp_path/("task%d.json"%fold);write_json(ip,info)
        taskrefs.append(dict(task_id=tid,fold=fold,manifest=str(ip),sha256=sha256(ip)))
        for variant in ("HCG","HCG_DDG",VARIANT):
            target=labels[file];prediction=target if variant==VARIANT or fold!=0 else 1-target
            row=dict(file=file,target=target,best=prediction,last=prediction,
                best_positive_probability=.9 if prediction else .1,last_positive_probability=.8 if prediction else .2,
                score_role="cv_validation")
            folder=tmp_path/(variant+str(fold));folder.mkdir();locations[(fold,variant)]=folder
            write_json(folder/"cv_validation_predictions.json",[row])
            m=metrics([target],[prediction])
            write_json(folder/"result.json",dict(cv_validation=dict(best=m,last=m),best_epoch=0,last_epoch=1,
                history_rows=2,parameters=3,wall_seconds_monotonic=.1,checkpoint_roundtrip_exact=dict(best=True,last=True),
                resource=dict(peak_allocated_bytes=0,peak_reserved_bytes=0,card=dict(minimum_whole_card_free_mib=100)),
                gradient_audit=dict(epochs=[dict(enhancement_relations=[])])))
    plan=dict(tasks=taskrefs,source_batch=str(tmp_path/"old"),source_plan_sha256="oldhash")
    monkeypatch.setattr(report,"verify_plan",lambda _:plan)
    monkeypatch.setattr(report,"verify_archive",lambda _:(dict(),dict(plan_sha256="oldhash")))
    finder=lambda output,job,plan:locations[(job["fold"],job["variant"])]
    monkeypatch.setattr(report,"completed",finder);monkeypatch.setattr(report,"old_completed",finder)
    answer=report.summarize(tmp_path,(tid,))
    result=json.loads((Path(answer["output"])/"report.json").read_text())
    assert result["new_fits"]==5 and result["reused_fits"]==10
    assert len(result["statistics"])==6 and len(result["paired"])==6 and len(result["pooled_oof"])==6
    assert not result["independent_test"]
    candidate=locations[(0,VARIANT)]/"cv_validation_predictions.json"
    rows=json.loads(candidate.read_text());rows[0]["target"]=1-rows[0]["target"];write_json(candidate,rows)
    with pytest.raises(ValueError,match="label mismatch"):report.summarize(tmp_path,(tid,))
