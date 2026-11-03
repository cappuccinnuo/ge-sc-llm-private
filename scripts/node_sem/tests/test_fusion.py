"""NS-P4 fusion, local RNG, zero-layer and exact initialization checks."""
import copy
import json
from pathlib import Path
import pytest
import numpy as np
import torch
from torch import nn
from scripts.node_sem import CODE, CTX, STATIC
from scripts.node_sem.adapter import NodeSemAdapter, reset_modality_dropout
from scripts.node_sem.feature_spec import FeatureSpec
from scripts.node_sem.model import make_nodesem_model, validate
from scripts.node_sem.init import initial_state
from scripts.node_sem.tests.test_init import sealed
from scripts.node_sem.tests.test_carrier import _generic
from scripts.node_sem.tests.carrier_fixtures import make_spelling_fixture, token_spec, dump
from scripts.node_sem.tests.test_model import CONFIG
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.support import model_support, gradient_audit


def spec(fusion="concat", dropout=0, normalize=True):
    return FeatureSpec("fusion-fixture", "original", [
        dict(name=n, dim=d, manifest=None, normalize=normalize and n != STATIC)
        for n,d in [(CODE,7),(CTX,5),(STATIC,4)]], "none", fusion, dropout)


def inputs(s, n=15):
    g=torch.Generator().manual_seed(83)
    x=torch.randn(n,s.carrier_dim(),generator=g)
    x[:,:3]=torch.tensor([[1.,1.,1.],[1.,0.,1.],[0.,0.,0.]])[(torch.arange(n)%3)]
    return x


@pytest.mark.parametrize("fusion",["concat","gated"])
def test_missing_mask_and_bias_forward_backward(fusion):
    s=spec(fusion); a=NodeSemAdapter(s,"if")
    x=inputs(s)
    with torch.no_grad(): a.bias.fill_(.13)
    y=a(x)
    assert torch.equal(y[2::3],a.bias.expand_as(y[2::3]))
    changed=x.clone(); changed[1::3,s.layout()[CTX]["start"]:s.layout()[CTX]["stop"]]+=130
    assert torch.equal(a(changed),y)
    y.square().sum().backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in a.parameters())
    if fusion=="gated":
        gates=a.last_gates
        assert gates.device.type=="cpu" and not gates.requires_grad
        assert torch.equal(gates[2::3],torch.zeros_like(gates[2::3]))
        assert torch.allclose(gates.sum(1),(x[:,:3].sum(1)>0).float(),atol=1e-6,rtol=0)
        assert torch.count_nonzero(gates[1::3,1])==0
    assert STATIC not in a.norm and set(a.norm)=={CODE,CTX}
    assert all(p.bias is None for p in a.proj.values())


@pytest.mark.parametrize("fusion",["concat","gated"])
@pytest.mark.parametrize("p",[0.,.1,1.])
def test_dropout_local_rng_repeatability_eval_and_all_missing(fusion,p):
    s=spec(fusion,p);a=NodeSemAdapter(s,"return");b=copy.deepcopy(a);x=inputs(s,99)
    a.reset_dropout(1000001,"fixture_node",0,"G3R")
    b.reset_dropout(1000001,"fixture_node",0,"G3R")
    state=torch.get_rng_state().clone()
    for i in range(3):
        y=a(x);other=b(x)
        assert torch.equal(y,other)
        assert torch.equal(state,torch.get_rng_state())
        if p==1: assert torch.equal(y,a.bias.expand_as(y))
    counter=a.forward_count
    a.eval(); y=a(x);assert a.forward_count==counter
    a.eval(); assert torch.equal(y,a(x))
    a.train()
    if p==0: assert torch.equal(a(x),y)
    else:
        a.reset_dropout(1000001,"fixture_node",0,"G3R")
        b.reset_dropout(1000001,"fixture_node",0,"G3R")
        assert torch.equal(a(x),b(x))


def test_dropout_requires_identity_and_does_not_mutate_carrier():
    a=NodeSemAdapter(spec(dropout=.1),"if");x=inputs(a.spec);before=x.clone()
    with pytest.raises(RuntimeError,match="fit identity"): a(x)
    a.reset_dropout(1,"fixture_node",0,"G0");a(x)
    assert torch.equal(x,before)


def test_zero_rows_and_invalid_presence():
    for fusion in ["concat","gated"]:
        a=NodeSemAdapter(spec(fusion),"return")
        assert a(inputs(a.spec,0)).shape==(0,128)
        x=inputs(a.spec);x[0,0]=.5
        with pytest.raises(ValueError,match="presence"): a(x)


@pytest.mark.parametrize("task",["node","contract"])
@pytest.mark.parametrize("layers",[0,2])
@pytest.mark.parametrize("fusion",["concat","gated"])
def test_continuous_model_frozen_forward_backward_and_zero_layers(tmp_path,task,layers,fusion):
    f=make_spelling_fixture(tmp_path)
    s,_,_,_,_=_generic(f,tmp_path)
    values=s.to_json();values.update(layers=layers,fusion=fusion)
    s=FeatureSpec.from_json(values)
    before=graph_fingerprint(f["graph"])
    model=make_nodesem_model(task,f["graph"],"G0",s,CONFIG,task_id="fixture_node")
    # The fixture modality task ID remains fixture_node even for the contract readout.
    assert model.num_layers==layers and len(model.gcs)==layers
    assert not hasattr(model,"nodesem_shared")
    out=model() if task=="node" else model(["train.sol","val.sol"])[0]
    out.square().mean().backward()
    support=model_support(model,dict(inner_train=["train.sol"],inner_val=["val.sol"],outer_test=["test.sol"]))
    assert gradient_audit(model,support) is not None
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())
    assert any(p.grad is not None and p.grad.abs().sum()>0 for a in model.adapt_ws for p in a.parameters())
    validate(model,s)
    assert graph_fingerprint(f["graph"])==before
    assert any(k.startswith("adapt_ws.0.proj.code.weight") for k in model.state_dict())


@pytest.mark.parametrize("fusion",["concat","gated"])
def test_fusion_initialization_copies_hgt_and_is_deterministic(tmp_path,monkeypatch,fusion):
    reference,payload=sealed(tmp_path,monkeypatch)
    s=spec(fusion)
    def make():
        m=nn.Module();m.dfg_task="node";m.dfg_profile="G0"
        m.gcs=nn.ModuleList([nn.Linear(128,128)]);m.classify=nn.Linear(128,2)
        m.adapt_ws=nn.ModuleList([NodeSemAdapter(s,str(i)) for i in range(2)])
        return m
    model=make();rng=torch.get_rng_state().clone()
    first,sha=initial_state(model,s,"fixture_node",0,"G0",reference)
    assert torch.equal(rng,torch.get_rng_state())
    second,sha2=initial_state(make(),s,"fixture_node",0,"G0",reference)
    assert sha==sha2 and all(torch.equal(v,second[k]) for k,v in first.items())
    assert all(torch.equal(v,payload["state_dict"][k]) for k,v in first.items() if k.startswith(("gcs.","classify.")))
    assert torch.count_nonzero(first["adapt_ws.0.bias"])==0
    assert torch.equal(first["adapt_ws.0.norm.code.weight"],torch.ones(7))
    assert torch.count_nonzero(first["adapt_ws.0.norm.code.bias"])==0
    if fusion=="gated": assert torch.count_nonzero(first["adapt_ws.0.gate.bias"])==0


@pytest.mark.parametrize("field",["norm","bias","proj_bias","gate"])
def test_fusion_registration_rejects_corruption(tmp_path,field):
    f=make_spelling_fixture(tmp_path);s,_,_,_,_=_generic(f,tmp_path)
    v=s.to_json();v["fusion"]="gated";s=FeatureSpec.from_json(v)
    m=make_nodesem_model("node",f["graph"],"G0",s,CONFIG)
    a=m.adapt_ws[0]
    if field=="norm": a.norm[CODE]=nn.Identity()
    elif field=="bias": a.bias=nn.Parameter(torch.zeros(1))
    elif field=="proj_bias": a.proj[CODE]=nn.Linear(3,128)
    else: a.gate=nn.Linear(128,2)
    with pytest.raises(ValueError): validate(m,s)


def test_original_raw_alias_initial_copies_all_historical_parameters(tmp_path,monkeypatch):
    from scripts.node_sem.tests.test_init import model,specification
    reference,payload=sealed(tmp_path,monkeypatch)
    data=specification("S0").to_json();data.update(name="S0o",view="original")
    s=FeatureSpec.from_json(data)
    actual,sha=initial_state(model("S0"),s,"fixture_node",0,"G0",reference)
    assert sha==payload["state_sha256"]
    assert all(torch.equal(v,payload["state_dict"][k]) for k,v in actual.items())


def test_concat_linear_equivalence_with_float64_reference():
    s=spec(normalize=False);a=NodeSemAdapter(s,"if");x=inputs(s)
    parts=[x[:,s.layout()[m["name"]]["start"]:s.layout()[m["name"]]["stop"]]*x[:,i:i+1]
           for i,m in enumerate(s.modalities)]
    joined=torch.cat(parts,1);weights=torch.cat([a.proj[n].weight for n in a.names],1)
    reference=torch.nn.functional.linear(joined.double(),weights.double(),a.bias.double())
    split=a(x);single=torch.nn.functional.linear(joined,weights,a.bias)
    assert torch.allclose(split.double(),reference,atol=1e-6,rtol=1e-5)
    assert torch.allclose(single.double(),reference,atol=1e-6,rtol=1e-5)
    assert torch.equal(split,a(x))
    x.requires_grad_(True);split=a(x);split.square().sum().backward()
    assert torch.isfinite(x.grad).all()


def test_configurations_derive_dimensions_and_original_views():
    root=Path(__file__).resolve().parents[1]
    index=json.loads((root/"configs/NS_P4_INDEX.json").read_text())
    for name,meta in index["configurations"].items():
        s=FeatureSpec.from_json(json.loads((root/"configs"/(name+".json")).read_text()))
        assert s.view=="original" and s.carrier_dim()==meta["carrier_dim"]
        assert meta["ctx_names"]==("masked" if name in ["S3m","S4m"] else "original")
        if name.startswith("S4"): assert s.carrier_dim()==760
        if name.startswith("S3"): assert s.carrier_dim()==514
        if name=="S4-noG": assert s.layers==0 and meta["allowed_profiles"]==["G0"]


def test_mixed_token_continuous_model_shared_registration(tmp_path,monkeypatch):
    from scripts.node_sem import model as module,TOKEN_IDS
    from scripts.node_sem.tests.carrier_fixtures import FixtureTokenEncoder
    monkeypatch.setattr(module,"TokenEncoder",FixtureTokenEncoder)
    f=make_spelling_fixture(tmp_path);continuous,_,_,_,_=_generic(f,tmp_path)
    token=token_spec(f,"S1").modalities[0]
    s=FeatureSpec("mixed","anonymous",[token]+list(continuous.modalities),"embed_pool","gated",.1)
    m=make_nodesem_model("node",f["graph"],"G0",s,CONFIG)
    reset_modality_dropout(m,1000001,"fixture_node",0,"G0")
    m().square().mean().backward();validate(m,s)
    assert [k for k in m.state_dict() if "token_bag" in k]==["nodesem_shared.token_bag.weight"]
    assert all(a.token_bag is m.nodesem_shared["token_bag"] for a in m.adapt_ws)
