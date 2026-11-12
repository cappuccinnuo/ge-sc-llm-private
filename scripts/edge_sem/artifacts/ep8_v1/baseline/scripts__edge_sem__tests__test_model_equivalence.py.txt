"""EP1 CPU model gates. No optimizer, historical weight load, or GPU run."""
import copy
import gc
import json
import os
import time
from pathlib import Path
import pytest
import torch
from scripts.DFG.dfg_v2.model import make_model,validate_registration as frozen_validate
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.experiment.init import seeds
from scripts.DFG.experiments.common import tensor_digest
from scripts.DFG.dfg_v2.tests.test_model import hcg,augment
from scripts.edge_sem.model import make_edge_model,validate_registration
from scripts.edge_sem.recon.common import ROOT,read,checked,ref


def compare_models(anchor,model):
    assert anchor.etypes_dict==model.etypes_dict and anchor.ntypes_dict==model.ntypes_dict
    assert list(anchor.state_dict())==list(model.state_dict())
    assert all(torch.equal(v,model.state_dict()[k]) for k,v in anchor.state_dict().items())
    assert list(anchor.symmetrical_global_graph_data)==list(model.symmetrical_global_graph_data)
    for c in anchor.etypes_dict:
        assert all(torch.equal(x,y) for x,y in zip(
            anchor.symmetrical_global_graph.edges(etype=c,order="eid"),
            model.symmetrical_global_graph.edges(etype=c,order="eid")))
    for t in anchor.ntypes_dict:
        assert torch.equal(anchor.symmetrical_global_graph.nodes[t].data["inp"],
                           model.symmetrical_global_graph.nodes[t].data["inp"])


@pytest.mark.parametrize("task",["node","contract"])
def test_small_merge_model_parity(hcg,task):
    graph=augment(hcg,"G3R")
    before=graph_fingerprint(graph)
    torch.manual_seed(seeds(task,0)["constructor"])
    anchor=make_model(task,graph,"G3R",hidden_size=16,layers=2,heads=2,layer_impl="shared_projection")
    model=make_edge_model(task,graph,fold=0,hidden_size=16,layers=2,heads=2)
    compare_models(anchor,model)
    anchor.eval();model.eval()
    with torch.no_grad():
        a=anchor() if task=="node" else anchor(["minimal.sol","second.sol"])[0]
        b=model() if task=="node" else model(["minimal.sol","second.sol"])[0]
    assert torch.equal(a,b)
    assert graph_fingerprint(graph)==before


@pytest.fixture
def typed(hcg):
    return make_edge_model("node",augment(hcg,"G3R"),"G3R-T",hidden_size=16,layers=1,heads=2)


@pytest.mark.parametrize("what",["edge_id","endpoint","features","mask","row_map","metadata","cached_data","layer"])
def test_typed_registration_rejects_tamper(typed,what):
    model=typed;graph=model.symmetrical_global_graph
    c=next(c for c in graph.canonical_etypes if graph.num_edges(c)>0 and graph.num_nodes(c[0])>1)
    t=next(t for t in graph.ntypes if graph.num_nodes(t)>0)
    if what=="edge_id":graph.edges[c].data["id"][0]+=1
    elif what=="endpoint":
        ss,_=graph.edges(etype=c,order="eid");ss[0]=(ss[0]+1)%graph.num_nodes(c[0])
    elif what=="features":graph.nodes[t].data["inp"][0,0]+=1
    elif what=="mask":model.supervised_node_mask[0]=~model.supervised_node_mask[0]
    elif what=="row_map":model.node_ids_dict[t]=list(reversed(model.node_ids_dict[t]))+[999]
    elif what=="metadata":model.edge_rel_meta[c]["reverse"]=not model.edge_rel_meta[c]["reverse"]
    elif what=="cached_data":
        pair=model.symmetrical_global_graph_data[c]
        model.symmetrical_global_graph_data[c]=(pair[0]+1,pair[1])
    else:model.dfg_layer_impl="original"
    with pytest.raises(ValueError):validate_registration(model)


def test_typed_does_not_bypass_frozen_deep_validator(typed):
    validate_registration(typed)
    with pytest.raises(ValueError,match="Graph/schema"):frozen_validate(typed)


@pytest.mark.parametrize("profile",["G4R-P","G4R-A","G4R-Api","G4R-AC","G3R-TA"])
def test_future_model_profiles_fail_explicitly(hcg,profile):
    with pytest.raises(NotImplementedError):make_edge_model("node",hcg,profile)


def save_probe(result):
    dest=os.environ.get("EDGESEM_EP1_RECEIPTS")
    if dest:
        path=Path(dest).resolve()
        expected=ROOT/"scripts/edge_sem/artifacts/ep1_v1/probes"
        if path!=expected or not (path.parent/"before.json").exists():
            raise ValueError("Probe receipt destination outside new EP1 batch")
        path.mkdir(exist_ok=True)
        name=result["task_id"]+"_"+result["profile"]+"_fold"+str(result["fold"])+".json"
        with (path/name).open("x",encoding="utf-8") as stream:
            json.dump(result,stream,ensure_ascii=False,sort_keys=True,indent=2)
            stream.write("\n")


def real_graph(task):
    inputs=read(ROOT/"scripts/edge_sem/artifacts/ep0_v1/inputs.json")
    item=inputs["tasks"][task]
    from scripts.DFG.dfg_v2.benchmark_v2.spelling_features import assemble
    graph=assemble(checked(item["graph_refs"]["F3"]),item["feature_view"])
    return inputs,item,graph


@pytest.mark.parametrize("fold",[0,9])
def test_real_reentrancy_merge_gate(fold):
    inputs,item,graph=real_graph("reentrancy_node")
    before=graph_fingerprint(graph)
    cfg=item["config"];seed=seeds("node",fold)["constructor"]
    kwargs=dict(hidden_size=cfg["hidden_size"],layers=cfg["layers"],heads=cfg["heads"])
    torch.manual_seed(seed)
    start=time.monotonic()
    anchor=make_model("node",graph,"G3R",layer_impl="shared_projection",reducer="mean",**kwargs)
    anchor_seconds=time.monotonic()-start
    start=time.monotonic()
    model=make_edge_model("node",graph,"G3R",fold=fold,**kwargs)
    seconds=time.monotonic()-start
    compare_models(anchor,model)
    anchor.eval();model.eval()
    with torch.no_grad():a,b=anchor(),model()
    assert torch.equal(a,b) and graph_fingerprint(graph)==before
    assert not torch.cuda.is_initialized()
    save_probe(dict(task_id="reentrancy_node",fold=fold,profile="G3R",canonical_count=len(model.etypes_dict),
        parameter_count=sum(p.numel() for p in model.parameters()),anchor_seconds=anchor_seconds,
        construction_seconds=seconds,state_digest=tensor_digest(model.state_dict()),seed=seed,
        forward_bitwise_equal=True,all_parameters_equal=True,endpoints_equal=True,max_abs=0.0,
        graph_unchanged=True,cuda_initialized=False,optimizer_steps=0,source_graph=item["graph_refs"]["F3"],
        feature_view=item["feature_view"],config=cfg))
    del anchor,model,graph;gc.collect()


@pytest.mark.parametrize("task",["reentrancy_node","access_control_node"])
def test_real_typed_forward_backward(task):
    inputs,item,graph=real_graph(task)
    before=graph_fingerprint(graph);cfg=item["config"]
    start=time.monotonic()
    model=make_edge_model("node",graph,"G3R-T",fold=0,
        hidden_size=cfg["hidden_size"],layers=cfg["layers"],heads=cfg["heads"])
    seconds=time.monotonic()-start
    counts=[dict(canonical=list(c),edges=model.symmetrical_global_graph.num_edges(c))
            for c in model.symmetrical_global_graph.canonical_etypes]
    ep0=read(ROOT/("scripts/edge_sem/artifacts/ep0_v1/"+task+".json"))
    assert counts==ep0["graph_counts"]["typed"]
    validate_registration(model)
    model.eval();start=time.monotonic()
    output=model()
    # Structural gradient probe, not supervised fitting or a scored experiment.
    loss=output.square().mean();loss.backward()
    assert bool(torch.isfinite(output).all()) and bool(torch.isfinite(loss))
    assert any(p.grad is not None and bool((p.grad!=0).any()) for p in model.parameters())
    assert all(p.grad is None or bool(torch.isfinite(p.grad).all()) for p in model.parameters())
    assert graph_fingerprint(graph)==before and not torch.cuda.is_initialized()
    save_probe(dict(task_id=task,fold=0,profile="G3R-T",canonical_count=len(counts),
        parameter_count=sum(p.numel() for p in model.parameters()),construction_seconds=seconds,
        forward_backward_seconds=time.monotonic()-start,forward_backward_finite=True,
        sparse_relations=[r for r in counts if r["edges"]<20],relations=counts,
        copied_rows=[r["copied_rows"] for r in model.edge_initialization],
        graph_unchanged=True,cuda_initialized=False,optimizer_steps=0,
        objective="mean squared logits; structural probe, no labels or optimizer",
        source_graph=item["graph_refs"]["F3"],feature_view=item["feature_view"],config=cfg))
    del model,output,loss,graph;gc.collect()
