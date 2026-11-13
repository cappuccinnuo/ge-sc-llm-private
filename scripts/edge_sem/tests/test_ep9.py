"""EP9 identity, paired-initial, hypothesis-family and destination-only gates."""
import ast
import copy
import json
from pathlib import Path
import networkx as nx
import numpy as np
import pytest
import torch
from torch import nn

from scripts.edge_sem import execution as ex, feature_views as fv, protocol_p2 as p2
from scripts.edge_sem import analysis_eb as eb
from scripts.edge_sem.recon import ep9_run as driver
from scripts.edge_sem.tests.test_ep8 import put,examples
from scripts.edge_sem.tests.test_hgt_edge import sample
from scripts.DFG.dfg_v2.experiment import stats


def eb_plan(tmp_path,role="primary"):
    reg=put(tmp_path/"reg.json",dict(experiment_stage="E-B",primary_endpoint=dict(view="original"),
        batches={r:dict(view=v,profiles=list(eb.PROFILES),holm_member=r=="primary")
                 for r,v in (("primary","original"),("sensitivity","anonymous"))}))
    return dict(experiment_stage="E-B",analysis_role=role,registration=reg,scope="formal",
        token_view="original" if role=="primary" else "anonymous",
        baseline_plan={"path":"EA"},
        prior_main_plan={"path":"primary"} if role=="sensitivity" else None,
        jobs=[dict(task_id=t,fold=f,edge_profile=p,seed=1) for t in ex.TASKS for f in range(10) for p in eb.PROFILES])


@pytest.mark.parametrize("role",["primary","sensitivity"])
def test_eb_matrix_is_exact_60_with_one_primary(tmp_path,role):
    p=eb_plan(tmp_path,role)
    assert len(p["jobs"])==60
    assert fv.validate_plan_view(p)==p["token_view"]


@pytest.mark.parametrize("damage",["missing","duplicate","extra","profile","view","prior","stage","holm","checkpoint_scope"])
def test_eb_refuses_wrong_matrix_roles_or_registration(tmp_path,damage):
    p=eb_plan(tmp_path,"sensitivity")
    if damage=="missing":p["jobs"].pop()
    elif damage=="duplicate":p["jobs"][1]=p["jobs"][0]
    elif damage=="extra":p["jobs"].append(dict(p["jobs"][0],fold=10))
    elif damage=="profile":p["jobs"][0]["edge_profile"]="G4R-AC"
    elif damage=="view":p["token_view"]="original"
    elif damage=="prior":p["prior_main_plan"]=None
    elif damage=="stage":p["experiment_stage"]="E-A"
    elif damage=="checkpoint_scope":p["scope"]="norm_pilot"
    else:
        r=json.loads(Path(p["registration"]["path"]).read_text())
        r["batches"]["sensitivity"]["holm_member"]=True
        p["registration"]=put(Path(p["registration"]["path"]),r)
    with pytest.raises(ValueError):fv.validate_plan_view(p)


def test_eb_decision_does_not_authorize_ea_or_legacy(tmp_path):
    path=tmp_path/"decisions.json"
    put(path,dict(experiment_stage="E-B",user_request="complete EP9",date="2026-11-12",
        decisions={k:dict(status="confirmed",value=p2.EA_D1 if k=="D1" else v) for k,v in p2.DECISIONS.items()}))
    put(path.with_suffix(".seal.json"),dict(decisions=put(path,json.loads(path.read_text()))))
    p2.require_decisions(path,"original","E-B")
    p2.require_decisions(path,"anonymous","E-B")
    with pytest.raises(ValueError):p2.require_decisions(path,"original","E-A")
    with pytest.raises(ValueError):p2.require_decisions(path,"original")


def parts(original=(.01,.02),anonymous=(.00001,.00002),negative=False):
    result=[]
    for view,ps in (("original",original),("anonymous",anonymous)):
        for i,(profile,base) in enumerate(eb.CONTRASTS[:2]):
            result.append(dict(view=view,task_id="reentrancy_node",checkpoint="best",metric="buggy_f1",
                profile=profile,baseline=base,p_raw=ps[i],difference_mean_pp=-1 if negative and i==0 else 1))
    return result


def h1():
    return dict(hypotheses={"original":dict(H1_raw_p=.19967679150643913,both_mean_differences_positive=True)})


def test_holm_uses_max_component_and_only_original_two_hypotheses():
    hypotheses,adjustment=eb.h2_family(parts(),h1())
    assert hypotheses["original"]["H2_raw_p"]==.02
    assert adjustment["p_adjusted"]["H2"]==.04
    assert adjustment["p_adjusted"]["H1"]==.19967679150643913
    assert adjustment["supported"]=={"H1":False,"H2":True}
    assert adjustment["anonymous_in_family"] is False
    _,other=eb.h2_family(parts(anonymous=(.9,.9)),h1())
    assert adjustment==other


def test_small_p_with_nonpositive_gain_cannot_support_h2():
    _,v=eb.h2_family(parts(negative=True),h1())
    assert v["p_adjusted"]["H2"]==.04 and v["supported"]["H2"] is False
    with pytest.raises(ValueError):eb.h2_family(parts()[:-1],h1())
    with pytest.raises(ValueError):eb.h2_family(parts()+parts()[:1],h1())


def test_zero_difference_and_node_identity_alignment():
    rows,labels=examples()
    inventory={p:{f:list(reversed(rows)) if p=="G4R-Api" else rows for f in range(10)}
               for p in eb.PROFILES+eb.BASELINES}
    records=[]
    for p in inventory:
        for f in range(10):
            for ck in ("best","last"):
                records.append(dict(task_id="reentrancy_node",task_kind="node",profile=p,fold=f,seed=1,
                    checkpoint=ck,metrics={m:eb.score(rows,ck)[m] for m in stats.METRICS}))
    paired,errors,changed=eb.compare_profiles(records,inventory,"anonymous","reentrancy_node",labels)
    assert len(paired)==24 and len(errors)==60 and not changed
    assert all(r["p_raw"]==1 and r["tied"]==10 and not r["confirmatory_component"] for r in paired)
    assert all(r["relative_error_reduction_pct"]==0 for r in errors)


class Initial(nn.Module):
    def __init__(self):
        super().__init__()
        self.shared=nn.Linear(2,2)
        self.edge_encoder=nn.Linear(2,16)
        self.gcs=nn.ModuleList([nn.Module()])
        self.gcs[0].u=nn.Parameter(torch.zeros(2,16,2))
        self.gcs[0].U=nn.ParameterDict({"data":nn.Parameter(torch.zeros(16,2))})


def test_initial_gate_rejects_shared_zero_and_placebo_drift():
    a=Initial()
    state=a.state_dict()
    base={"state_dict":{k:v.clone() for k,v in state.items() if k.startswith("shared.")}}
    gate=driver.check_initial(a,base,copy.deepcopy(state))
    assert gate["u_U_exact_zero"] and gate["A_Api_entire_state_bitwise_equal"]
    with torch.no_grad():a.shared.weight[0,0]+=1
    with pytest.raises(ValueError,match="Common"):driver.check_initial(a,base)
    a.load_state_dict(state)  # state tensors share storage; restore explicitly below.
    with torch.no_grad():a.shared.weight.copy_(base["state_dict"]["shared.weight"]);a.gcs[0].u[0,0,0]=1
    with pytest.raises(ValueError,match="exactly zero"):driver.check_initial(a,base)
    with torch.no_grad():a.gcs[0].u.zero_()
    pair=copy.deepcopy(a.state_dict());pair["edge_encoder.bias"][0]+=1
    with pytest.raises(ValueError,match="full zero-step"):driver.check_initial(a,base,pair)


def test_logits_gate_requires_exact_equality_not_tolerance():
    layer=nn.Linear(2,2)
    class Wrapper(nn.Module):
        def forward(self):return layer(torch.ones(1,2))
    m=Wrapper()
    with torch.no_grad():out=m()
    assert driver.check_logits(m,out)["bitwise_equal"]
    changed=out.clone();changed[0,0]+=1e-6
    assert driver.check_logits(m,changed)["bitwise_equal"] is False


class MechanismModel(nn.Module):
    def __init__(self):
        super().__init__()
        g,h,old,new=sample()
        self.gcs=nn.ModuleList([new])
        self.symmetrical_global_graph=g
        self.node_ids_dict={"a":[0,1,2],"b":[3,4]}
        self.original_graph_node_ids=[10,20,30,40,50]
        self.nx_graph=nx.MultiDiGraph()
        for n in range(5):self.nx_graph.add_node(n,source_file="case.sol")
        with torch.no_grad():new.u.fill_(1)
    def edge_embeddings(self):
        return {c:torch.ones(self.symmetrical_global_graph.num_edges(c),16)
                for c in self.symmetrical_global_graph.canonical_etypes}


def test_bias_distribution_uses_only_outer_test_destination_inedges():
    model=MechanismModel()
    # a2 receives one DATA edge; b0 receives two control edges.
    predictions=[dict(file="case.sol",original_graph_node_id=30,node_type="a",target=0),
                 dict(file="case.sol",original_graph_node_id=40,node_type="b",target=1)]
    result=eb.mechanism(model,predictions)
    observed={(r["family"],r["target"],r["head"]):r for r in result["bias"]}
    for head in (0,1):
        assert observed[("control",1,head)]["edge_count"]==2
        assert observed[("data",0,head)]["edge_count"]==1
        assert observed[("control",0,head)]["n"]==0
        assert observed[("data",1,head)]["n"]==0
    assert all(r["mean"]==16 for r in result["bias"] if r["n"])
    assert result["destinations"]==2 and result["statistical_test"] is False
    predictions[0]["original_graph_node_id"]=999
    with pytest.raises(ValueError,match="missed"):eb.mechanism(model,predictions)


def test_summary_statistics_refuse_nan():
    assert eb.distribution([])["n"]==0
    assert eb.distribution([1,2,3])["median"]==2
    with pytest.raises(ValueError):eb.distribution([float("nan")])


def test_numeric_training_and_ep8_sources_unchanged():
    root=Path(__file__).resolve().parents[1]
    before=root/"artifacts/ep9_v1/before.json"
    if not before.exists():pytest.skip("No local EP9 snapshot")
    from scripts.edge_sem.io import checked,read
    data=read(before)
    for name in ("analysis_ea.py","recon/ep8_run.py"):
        row=next(r["source"] for r in data["edge_sources"] if r["source"]["path"].endswith("/"+name))
        checked(row)
    snapshot=next(r["snapshot"] for r in data["edge_sources"] if r["source"]["path"].endswith("/execution.py")
                  and "/recon/" not in r["source"]["path"])
    old={n.name:ast.dump(n) for n in ast.parse(checked(snapshot).read_text()).body if isinstance(n,ast.FunctionDef)}
    new={n.name:ast.dump(n) for n in ast.parse(Path(ex.__file__).read_text()).body if isinstance(n,ast.FunctionDef)}
    for name in ("assemble_model","construct","binding_parts","fit_one","_verify_result"):
        assert new[name]==old[name]

def test_followup_never_runs_tests_or_training_after_retained_preparation_failure(tmp_path,monkeypatch):
    put(tmp_path/"preparation_process.json",{"pid":2147483647})
    put(tmp_path/"preparation/failure.json",{"error":"fixture"})
    request=tmp_path/"request.json";put(request,{"user_request":"fixture"})
    monkeypatch.setattr(driver,"write",lambda path,value:put(path,value))
    calls=[]
    monkeypatch.setattr(driver,"tests",lambda root:calls.append("tests"))
    monkeypatch.setattr(driver,"run",lambda root:calls.append("run"))
    with pytest.raises(RuntimeError,match="CPU preparation failed"):
        driver.finish_preparation(tmp_path,request)
    assert not calls
    assert (tmp_path/"followup_failure.json").exists()
    with pytest.raises(FileExistsError):driver.finish_preparation(tmp_path,request)


def test_authorization_rejects_wrong_matrix_before_accessing_weights(tmp_path):
    path=tmp_path/"request.json"
    put(path,dict(user_request="fixture",execution_authorized=True,primary_fits=60,sensitivity_fits=80,
                  order=["primary","sensitivity"],automatic_retry=False))
    with pytest.raises(PermissionError,match="60\\+60"):
        driver.authorize(tmp_path,"uncommitted",path)


def test_freeze_requires_completed_120_new_results(tmp_path,monkeypatch):
    monkeypatch.setattr(eb,"sealed_summary",lambda root:(tmp_path/"summary.json",{"new_fits":119}))
    with pytest.raises(ValueError,match="Incomplete E-B"):driver.freeze_schema(tmp_path)
