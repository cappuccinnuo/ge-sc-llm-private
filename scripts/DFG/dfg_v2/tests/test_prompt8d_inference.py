"""Prompt8D prepared input failures and CPU-only intervention wiring."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
import torch
import networkx as nx
from scripts.DFG.dfg_v2.diagnostics8d import prepared as p
from scripts.DFG.dfg_v2.diagnostics8d import inference as w

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))
    return p.ref(path)

@pytest.fixture
def prepared_fixture(tmp_path):
    plan=tmp_path/"plan.json"
    graph=tmp_path/"g.gpickle";graph.write_bytes(b"frozen graph")
    source=tmp_path/"buggy_2.sol";source.write_text("contract C{}")
    feature={"scheme":"tokenizer_ids","feature_size":512}
    task={"record":{"task":"node","feature":feature,"sources":{"buggy_2.sol":p.ref(source)},
                    "original_graph":p.ref(graph)}}
    info=tmp_path/"info.json";write(info,{"profiles":{"G0":{"graph":p.ref(graph)}}})
    task["prepared"]={"0/1":p.ref(info)}
    write(plan,{"tasks":{"reentrancy_node":task}})
    write(tmp_path/"plan.seal.json",{"plan_sha256":p.ref(plan)["sha256"]})
    vector=np.arange(512,dtype=np.float32)
    row=dict(file="buggy_2.sol",original_graph_node_id=3,node_type="expression_statement",
             source_sha256=p.ref(source)["sha256"],vector_row=0,
             renamed_vector_sha256=p.vector_sha256(vector),
             original_vector_sha256=p.vector_sha256(np.zeros(512,dtype=np.float32)),
             before_token_length=7,after_token_length=7,
             position_proof={"full_token_count":7,"edited_token_positions":2,"edited_occurrences":1,
                             "unedited_token_ids_equal":True,"occurrence_token_positions_equal":True},
             replacements=1,code_before_sha256="a",code_after_sha256="b")
    data=tmp_path/"vectors.npz"
    np.savez_compressed(str(data),vectors=vector[None,:])
    view=tmp_path/"view.json"
    report=dict(task_id="reentrancy_node",mode="B_full",rows=[row],mappings={"buggy_2.sol":{"re_ent":"alpha"}},
                tokenizer=dict(feature,network_used=False,model_weights_loaded=False),source_refs=task["record"]["sources"],
                frozen_graph=p.ref(graph),full_token_lengths_preserved=True)
    write(view,report)
    manifest=tmp_path/"manifest.json"
    document=dict(source_plan=p.ref(plan),tasks={"reentrancy_node":{"views":{
        "B_full":{"manifest":p.ref(view),"data":p.ref(data),"changed_nodes":1}}}})
    write(manifest,document);write(tmp_path/"manifest.seal.json",{"sha256":p.ref(manifest)["sha256"]})
    def reseal():
        document["tasks"]["reentrancy_node"]["views"]["B_full"]["manifest"]=p.ref(view)
        document["tasks"]["reentrancy_node"]["views"]["B_full"]["data"]=p.ref(data)
        write(manifest,document);write(tmp_path/"manifest.seal.json",{"sha256":p.ref(manifest)["sha256"]})
    return SimpleNamespace(plan=plan,manifest=manifest,view=view,data=data,report=report,
                           document=document,vector=vector,reseal=reseal)

def test_prepared_valid_binding(prepared_fixture):
    f=prepared_fixture
    view,vectors,binding=p.load_view(f.manifest,"reentrancy_node","B_full",f.plan)
    assert len(view["rows"])==1 and np.array_equal(vectors[0],f.vector)
    assert binding["manifest"]==p.ref(f.manifest)

@pytest.mark.parametrize("mode",["G0","C","unknown"])
def test_prepared_unknown_mode_rejected(prepared_fixture,mode):
    f=prepared_fixture
    with pytest.raises(ValueError):
        p.load_view(f.manifest,"reentrancy_node",mode,f.plan)

def test_prepared_seal_rejected(prepared_fixture):
    f=prepared_fixture
    f.manifest.write_text(f.manifest.read_text()+" ")
    with pytest.raises(ValueError,match="seal"):
        p.load_view(f.manifest,"reentrancy_node","B_full",f.plan)

@pytest.mark.parametrize("failure",["duplicate","length","digest","task","nonfinite","dtype","shape"])
def test_prepared_rejects_corrupted_identity_vectors(prepared_fixture,failure):
    f=prepared_fixture
    report=f.report
    vector=f.vector[None,:]
    if failure=="duplicate":
        report["rows"].append(dict(report["rows"][0],vector_row=1))
        vector=np.stack((f.vector,f.vector))
    elif failure=="length":report["rows"][0]["after_token_length"]=8
    elif failure=="digest":report["rows"][0]["renamed_vector_sha256"]="0"*64
    elif failure=="task":report["task_id"]="access_control_node"
    elif failure=="nonfinite":vector=vector.copy();vector[0,0]=np.nan
    elif failure=="dtype":vector=vector.astype(np.float64)
    elif failure=="shape":vector=vector[:,:511]
    write(f.view,report);np.savez_compressed(str(f.data),vectors=vector);f.reseal()
    with pytest.raises(ValueError):
        p.load_view(f.manifest,"reentrancy_node","B_full",f.plan)

@pytest.mark.parametrize("value",[
    np.zeros(511,dtype=np.float32),np.zeros(512,dtype=np.float64),
    np.full(512,np.nan,dtype=np.float32)])
def test_vector_digest_requires_finite_exact_frozen_type(value):
    with pytest.raises(ValueError):p.vector_sha256(value)

@pytest.mark.parametrize("failure",[None,"omitted","wrong_after_code"])
def test_intervention_worker_only_changes_outer_test_rows_cpu(monkeypatch,tmp_path,failure):
    from scripts.DFG.dfg_v2.experiment import run
    from scripts.DFG.dfg_v2.experiment import checkpoint
    from scripts.DFG.dfg_v2 import model as model_module,supervision
    from scripts.DFG.integration import io
    task_id="reentrancy_node"
    job=dict(task_id=task_id,fold=0,seed=1,profile="G0",layer_impl="shared_projection")
    code="amount_re_ent = 1;"
    source=tmp_path/"buggy_2.sol";source.write_text(code)
    graphpath=tmp_path/"graph";graphpath.write_bytes(b"fixed")
    source_ref=p.ref(source);graph_ref=p.ref(graphpath)
    feature={"scheme":"tokenizer_ids","feature_size":512}
    config=dict(threads=1,hidden_size=8,layers=1,heads=1)
    task=dict(config=config,record=dict(task="node",feature=feature,
                                      sources={"buggy_2.sol":source_ref}))
    info=dict(seeds={"constructor":1},split={"outer_test_files":["buggy_2.sol"]})
    entry=dict(graph=graph_ref)
    planpath=tmp_path/"plan.json"
    plan=dict(jobs=[job],tasks={task_id:task},layer_impl="shared_projection",reducer="mean")
    write(planpath,plan)
    attempt=tmp_path/"attempt";attempt.mkdir()
    predictions=[dict(file="buggy_2.sol",original_graph_node_id=10,target=1,best=1,
                      best_positive_probability=.7)]
    write(attempt/"outer_test_predictions.json",predictions)
    write(attempt/"binding.json",{})
    (attempt/"best.pt").write_bytes(b"not loaded by fake restore")
    receipt=dict(status="complete",job=job,plan_sha256=p.ref(planpath)["sha256"],
                 artifacts={name:p.ref(attempt/name)["sha256"] for name in
                            ("outer_test_predictions.json","binding.json","best.pt")})
    write(attempt/"receipt.json",receipt)
    gate=tmp_path/"gate.json"
    write(gate,dict(gate_only=True,archive_parity={"passed":True},plan_sha256=p.ref(planpath)["sha256"]))
    graph=nx.MultiDiGraph()
    for node,file in [(0,"buggy_2.sol"),(1,"train.sol")]:
        graph.add_node(node,source_file=file,node_type="expression_statement",code=code,node_hetero_id=node)
    features=torch.zeros(2,512,dtype=torch.float32)
    aux=torch.ones(1,512,dtype=torch.float32)
    frames={"expression_statement":SimpleNamespace(data={"inp":features}),
            "env_source":SimpleNamespace(data={"inp":aux})}
    model=torch.nn.Linear(1,1)
    model.nx_graph=graph;model.original_graph_node_ids={0:10,1:11};model.device="cpu"
    model.symmetrical_global_graph=SimpleNamespace(nodes=frames,ntypes=list(frames),
        canonical_etypes=[],num_nodes=lambda typ:frames[typ].data["inp"].shape[0])
    class Part:
        full_ids=[0]
        files=["buggy_2.sol"]
        def forward(self,unused):
            v=frames["expression_statement"].data["inp"][0,0]
            return torch.stack((v,-v)).reshape(1,2)
    vector=np.ones((1,512),dtype=np.float32)
    row=dict(file="buggy_2.sol",original_graph_node_id=10,node_type="expression_statement",
             source_sha256=source_ref["sha256"],vector_row=0,replacements=1,
             code_before_sha256=hashlib.sha256(code.encode()).hexdigest(),
             code_after_sha256=hashlib.sha256(b"alpha = 1;").hexdigest(),
             original_vector_sha256=p.vector_sha256(np.zeros(512,dtype=np.float32)))
    view=dict(rows=[row],mappings={"buggy_2.sol":{"amount_re_ent":"alpha"}},
              tokenizer=feature,source_refs={"buggy_2.sol":source_ref},frozen_graph=graph_ref)
    if failure=="omitted": view["rows"]=[]
    if failure=="wrong_after_code": row["code_after_sha256"]="0"*64
    monkeypatch.setattr(w,"checked_plan",lambda path:plan)
    monkeypatch.setattr(w,"attempt_for",lambda *args:attempt)
    monkeypatch.setattr(run,"_prepared",lambda *args:(task,info,entry))
    monkeypatch.setattr(run,"_move_model",lambda *args:None)
    monkeypatch.setattr(model_module,"make_model",lambda *args,**kwargs:model)
    monkeypatch.setattr(checkpoint,"restore_checkpoint",lambda *args:{})
    monkeypatch.setattr(supervision,"DfgV2Supervision",lambda *args:Part())
    monkeypatch.setattr(p,"load_view",lambda *args:(view,vector,{"synthetic":True}))
    monkeypatch.setattr(torch.cuda,"is_available",lambda:True)
    monkeypatch.setattr(torch.cuda,"max_memory_allocated",lambda:0)
    monkeypatch.setattr(torch.cuda,"max_memory_reserved",lambda:0)
    output=tmp_path/"result.json"
    if failure:
        with pytest.raises(ValueError,match="Prepared"):
            w.run_worker(planpath,task_id,0,"G0",output,tmp_path/"prepared.json","B_full",gate)
        assert not output.exists()
        assert torch.equal(features,torch.zeros(2,512))
        return
    report=w.run_worker(planpath,task_id,0,"G0",output,tmp_path/"prepared.json","B_full",gate)
    assert torch.equal(features[0],torch.ones(512))
    assert torch.equal(features[1],torch.zeros(512))
    assert torch.equal(aux,torch.ones(1,512))
    assert report["optimizer_steps"]==0 and report["weights_unchanged"]
    assert len(report["changed_nodes"])==1
    assert report["changed_nodes"][0]["original_graph_node_id"]==10
    assert len(report["predictions"])==1
    assert report["unchanged_features_verified"] and report["graph_edges_unchanged"]


@pytest.mark.parametrize("failure",["graph","source","tokenizer","count","position_proof","mapping_scope"])
def test_prepared_binding_rejects_even_self_consistently_resealed_wrong_view(prepared_fixture,failure):
    f=prepared_fixture
    if failure=="graph": f.report["frozen_graph"]["sha256"]="0"*64
    elif failure=="source": f.report["source_refs"]["buggy_2.sol"]["sha256"]="0"*64
    elif failure=="tokenizer": f.report["tokenizer"]["feature_size"]=256
    elif failure=="count": f.document["tasks"]["reentrancy_node"]["views"]["B_full"]["changed_nodes"]=2
    elif failure=="position_proof": f.report["rows"][0]["position_proof"]["unedited_token_ids_equal"]=False
    elif failure=="mapping_scope": f.report["mappings"]["unexpected.sol"]={}
    write(f.view,f.report);f.reseal()
    with pytest.raises(ValueError): p.load_view(f.manifest,"reentrancy_node","B_full",f.plan)
