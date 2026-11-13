"""EP6 numerical and identity gates; no fitting or GPU."""
import copy
from pathlib import Path
import dgl
import networkx as nx
import numpy as np
import pytest
import torch
from sco_models import graph_utils as gu
from scripts.DFG.dfg_v2.hgt_layer import HGTLayerSharedProjection
from scripts.edge_sem.hgt_edge import EdgeAwareHGTLayer,EdgeAttrEncoder,verify_frozen_sources,FROZEN_SOURCES
from scripts.edge_sem.model_attrs import typed_attributes
from scripts.edge_sem.attrs import edge_rows


def sample(empty=False):
    data={("a","next_line","b"):(torch.tensor([0,1,2]),torch.tensor([0,0,1])),
          ("b","DATA_DEF_USE","a"):(torch.tensor([0,1]),torch.tensor([1,2]))}
    if empty:data[("a","GUARDS","b")]=(torch.empty(0,dtype=torch.long),torch.empty(0,dtype=torch.long))
    g=dgl.heterograph(data,num_nodes_dict={"a":3,"b":2})
    nodes={t:i for i,t in enumerate(g.ntypes)};edges={c:i for i,c in enumerate(g.canonical_etypes)}
    torch.manual_seed(7);h={t:torch.randn(g.num_nodes(t),8) for t in g.ntypes}
    torch.manual_seed(11);parent=HGTLayerSharedProjection(8,8,nodes,edges,2,dropout=.2,use_norm=True)
    rng=torch.get_rng_state().clone()
    torch.manual_seed(11);new=EdgeAwareHGTLayer(8,8,nodes,edges,2,dropout=.2,use_norm=True)
    assert torch.equal(torch.get_rng_state(),rng)
    assert all(torch.equal(v,new.state_dict()[k]) for k,v in parent.state_dict().items())
    return g,h,parent,new


@pytest.mark.parametrize("training",[False,True])
def test_no_psi_is_bitwise_parent(training):
    g,h,parent,new=sample();parent.train(training);new.train(training)
    torch.manual_seed(13);a=parent(g,h)
    torch.manual_seed(13);b=new(g,h)
    assert all(torch.equal(a[t],b[t]) for t in a)


@pytest.mark.parametrize("empty",[False,True])
def test_zero_initialized_corrections_match_parent(empty):
    g,h,parent,new=sample(empty);parent.eval();new.eval()
    encoder=EdgeAttrEncoder(9,dropout=0)
    psi={c:encoder(torch.randint(0,2,(g.num_edges(c),9),dtype=torch.uint8)) for c in g.canonical_etypes}
    a,b=parent(g,h),new(g,h,psi)
    assert max((a[t]-b[t]).abs().max().item() for t in a)<=1e-6
    assert all(torch.isfinite(v).all() for v in b.values())


def test_nonzero_corrections_change_output_and_reach_encoder():
    g,h,parent,new=sample();parent.eval();new.eval()
    enc=EdgeAttrEncoder(9,dropout=0)
    psi={c:enc(torch.randint(0,2,(g.num_edges(c),9),dtype=torch.uint8)) for c in g.canonical_etypes}
    with torch.no_grad():
        new.u.normal_(0,.4)
        for p in new.U.values():p.normal_(0,.4)
    a,b=parent(g,h),new(g,h,psi)
    assert max((a[t]-b[t]).abs().max().item() for t in a)>1e-5
    loss=sum((v*torch.randn_like(v)).sum() for v in b.values());loss.backward()
    assert new.u.grad is not None and new.u.grad.abs().sum()>0
    assert sum(p.grad.abs().sum() for p in new.U.values() if p.grad is not None)>0
    assert all(p.grad is not None and torch.isfinite(p.grad).all() and p.grad.abs().sum()>0 for p in enc.parameters())


def test_sha_guard_rejects_modified_parent(tmp_path):
    root=Path(__file__).resolve().parents[3]
    for name in FROZEN_SOURCES:
        dest=tmp_path/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((root/name).read_bytes())
    verify_frozen_sources(tmp_path)
    p=tmp_path/next(iter(FROZEN_SOURCES));p.write_bytes(p.read_bytes()+b"\n")
    with pytest.raises(ValueError,match="SHA mismatch"):verify_frozen_sources(tmp_path)


def test_typed_attributes_keep_parallel_edge_keys_and_reverse_values():
    g=nx.MultiDiGraph()
    for n,t in ((70,"a"),("node","a"),(3,"b")):g.add_node(n,node_type=t,source_file="fixture.sol")
    g.add_edge(70,3,key=9,edge_type="next_line")
    g.add_edge(70,3,key=3,edge_type="next_line")
    g.add_edge("node",3,key=0,edge_type="DATA_DEF_USE")
    g.add_edge(3,70,key=0,edge_type="READS_STATE")
    rows=edge_rows(g,[])
    values={r["key"]:np.array([(i+1)>>j&1 for j in range(74)],dtype=np.uint8) for i,r in enumerate(rows)}
    model_graph=gu.add_hetero_ids(nx.convert_node_labels_to_integers(copy.deepcopy(g)))
    matrices,keys,pairs=typed_attributes(g,model_graph,rows,values)
    c=("a","next_line","b")
    row9=next(r for r in rows if r["relation"]=="next_line" and r["nx_key"]==9)
    assert keys[c][0]==row9["key"]
    for c in [c for c in keys if not c[1].startswith("REV_")]:
        rev=(c[2],"REV_"+c[1],c[0])
        assert keys[c]==keys[rev] and torch.equal(matrices[c],matrices[rev])
        assert torch.equal(pairs[c][0],pairs[rev][1]) and torch.equal(pairs[c][1],pairs[rev][0])
        for i,key in enumerate(keys[c]):assert np.array_equal(matrices[c][i].numpy(),values[key])


@pytest.fixture(scope="module")
def real_inputs():
    from scripts.node_sem.facts_io import load_context
    from scripts.edge_sem.io import ROOT,read
    context=load_context("reentrancy_node")
    item=read(ROOT/"scripts/edge_sem/artifacts/ep0_v1/inputs.json")["tasks"]["reentrancy_node"]
    path=ROOT/"scripts/edge_sem/artifacts/ep6_v1/attributes/reentrancy_node/manifest.json"
    return context["graphs"]["F3"],item["config"],path


@pytest.mark.parametrize("profile",["G4R-Api","G4R-AC","G3R-TA"])
def test_attribute_profile_construction_and_validation(real_inputs,profile):
    from scripts.edge_sem.model import make_edge_model,validate_registration
    g,cfg,path=real_inputs
    model=make_edge_model("node",g,profile,hidden_size=16,layers=1,heads=2,attributes_manifest=path)
    validate_registration(model)
    expected=73 if profile=="G4R-AC" else 50
    assert len(model.edge_indices)==expected
    assert all(type(layer) is EdgeAwareHGTLayer for layer in model.gcs)
    assert bool(model.edge_attribute_binding["permutation"])==(profile=="G4R-Api")
    if profile=="G3R-TA":
        assert all(c[1] not in ("MOD_APPLY","CALL_SITE","GUARDS","REV_MOD_APPLY","REV_CALL_SITE","REV_GUARDS")
                   for c in model.etypes_dict)
    model.eval()
    with torch.no_grad():assert torch.isfinite(model()).all()


def test_real_registration_rejects_edge_attribute_tampering(real_inputs):
    from scripts.edge_sem.model import make_edge_model,validate_registration
    g,cfg,path=real_inputs
    model=make_edge_model("node",g,"G4R-A",hidden_size=16,layers=1,heads=2,attributes_manifest=path)
    c=next(c for c in model.etypes_dict if model.symmetrical_global_graph.num_edges(c))
    ea=model.symmetrical_global_graph.edges[c].data["ea"]
    ea[0,0]^=1
    with pytest.raises(ValueError,match="sealed NPZ"):validate_registration(model)
    ea[0,0]^=1
    original=model.edge_indices;model.edge_indices=tuple(reversed(original))
    with pytest.raises(ValueError,match="selection"):validate_registration(model)
    model.edge_indices=original
    keys=model.edge_attribute_keys[c];model.edge_attribute_keys[c]=keys+keys[:1]
    with pytest.raises(ValueError,match="row identity"):validate_registration(model)
    model.edge_attribute_keys[c]=keys
    model.symmetrical_global_graph.edges[c].data["ea"]=ea.float()
    with pytest.raises(ValueError,match="Invalid frozen"):validate_registration(model)


def test_real_reentrancy_fold0_cpu_probe(real_inputs):
    import os,time,resource,gc
    from scripts.edge_sem.model import make_edge_model,validate_registration
    from scripts.edge_sem.io import ROOT,ref,write
    from scripts.edge_sem.build_f4 import load_edges,add_edges
    from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
    from scripts.edge_sem.io import read,checked
    g,cfg,path=real_inputs;fp=graph_fingerprint(g)
    kwargs=dict(hidden_size=cfg["hidden_size"],layers=cfg["layers"],heads=cfg["heads"],fold=0)
    base=make_edge_model("node",add_edges(g,load_edges(checked(read(path)["f4_manifest"]))),"G4R",**kwargs)
    base.eval()
    with torch.no_grad():reference=base()
    base_count=sum(p.numel() for p in base.parameters())
    start=time.monotonic()
    model=make_edge_model("node",g,"G4R-A",attributes_manifest=path,**kwargs)
    construction=time.monotonic()-start;validate_registration(model)
    assert all(torch.equal(v,model.state_dict()[k]) for k,v in base.state_dict().items())
    del base;gc.collect()
    # One encoder invocation per relation, shared across all HGT layers.
    calls=[];handle=model.edge_encoder.register_forward_hook(lambda module,args,out:calls.append(len(args[0])))
    model.eval();start=time.monotonic();output=model();forward=time.monotonic()-start
    handle.remove()
    assert len(calls)==len(model.etypes_dict)
    maximum=(reference-output.detach()).abs().max().item()
    assert maximum<=1e-6
    loss=output.square().mean();start=time.monotonic();loss.backward();backward=time.monotonic()-start
    assert torch.isfinite(output).all() and torch.isfinite(loss)
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())
    assert any(layer.u.grad is not None and layer.u.grad.abs().sum()>0 for layer in model.gcs)
    assert any(p.grad is not None and p.grad.abs().sum()>0 for layer in model.gcs for p in layer.U.values())
    assert graph_fingerprint(g)==fp and not torch.cuda.is_initialized()
    result=dict(task_id="reentrancy_node",fold=0,profile="G4R-A",config=cfg,
        attrs_manifest=ref(path),source_view="original frozen F3 graph; structural CPU acceptance only",
        structural_parameters=base_count,parameters=sum(p.numel() for p in model.parameters()),
        added_parameters=sum(p.numel() for p in model.parameters())-base_count,
        construction_seconds=construction,forward_seconds=forward,backward_seconds=backward,
        peak_process_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.,
        zero_initial_max_abs=maximum,common_parameters_bitwise_equal=True,
        encoder_calls=len(calls),canonical_relations=len(model.etypes_dict),original_graph_unchanged=True,
        backward_finite=True,optimizer_steps=0,training_executed=False,cuda_initialized=False,
        objective="mean squared logits, no supervision, no optimizer",
        encoder_initial_gradient="Zero at u=U=0 by design; nonzero-gradient gate tested with nonzero u/U")
    target=os.environ.get("EDGESEM_EP6_PROBE")
    if target:
        expected=ROOT/"scripts/edge_sem/artifacts/ep6_v1/real_cpu.json"
        if Path(target).resolve()!=expected:raise ValueError("Unexpected EP6 probe output")
        write(expected,result)
