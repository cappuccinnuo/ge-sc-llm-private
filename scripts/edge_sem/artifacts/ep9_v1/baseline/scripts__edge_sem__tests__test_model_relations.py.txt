"""EP7 degree-placebo construction and registration gates."""
import copy
from collections import Counter
import gc
import os
from pathlib import Path
import pytest
import torch
from scripts.edge_sem.placebo import randomize_edges,add_placebo_edges,degree_signature
from scripts.edge_sem.tests.test_placebo import fixture
from scripts.edge_sem.tests.test_model_equivalence import real_graph
from scripts.edge_sem.build_f4 import load_edges,add_edges
from scripts.edge_sem.model import make_edge_model,validate_registration
from scripts.edge_sem.io import ROOT,read,checked,ref,write
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.experiments.common import tensor_digest


def test_placebo_materialization_is_strict_and_independent():
    graph,real=fixture()
    rows,_=randomize_edges(graph,real,10000)
    before=copy.deepcopy(graph)
    result=add_placebo_edges(graph,rows,real)
    assert graph.number_of_edges()==0 and result.number_of_edges()==len(rows)
    result.nodes[next(iter(result))]["node_type"]="changed"
    assert graph.nodes[next(iter(graph))]==before.nodes[next(iter(before))]
    with pytest.raises(ValueError):add_placebo_edges(graph,real,real)
    for mutation in ("degree","duplicate","self","file","evidence"):
        bad=copy.deepcopy(rows)
        if mutation=="degree":bad[0]["dst"]=next(n for n in graph if n[0]=="a.sol" and n[1]=="t" and n!=bad[0]["dst"] and n!=bad[1]["dst"])
        if mutation=="duplicate":bad[1]=copy.deepcopy(bad[0])
        if mutation=="self":bad[0]["dst"]=bad[0]["src"]
        if mutation=="file":bad[0]["file"]="b.sol"
        if mutation=="evidence":bad[0]["semantic_evidence"]=True
        with pytest.raises(ValueError):add_placebo_edges(graph,bad,real)
    graph.add_edge(rows[0]["src"],rows[0]["dst"],edge_type=rows[0]["relation"])
    with pytest.raises(ValueError):add_placebo_edges(graph,rows,real)


@pytest.mark.parametrize("task",["reentrancy_node","access_control_node"])
def test_real_placebo_model_gate(task):
    _,item,graph=real_graph(task)
    manifest=ROOT/"scripts/edge_sem/artifacts/ep6_v1/attributes"/task/"manifest.json"
    f4=checked(read(manifest)["f4_manifest"])
    real=load_edges(f4);before=graph_fingerprint(graph);cfg=item["config"]
    kwargs=dict(fold=0,hidden_size=cfg["hidden_size"],layers=cfg["layers"],heads=cfg["heads"])
    control=make_edge_model("node",add_edges(graph,real),"G4R",**kwargs)
    initial=tensor_digest(control.state_dict())
    counts={c:control.symmetrical_global_graph.num_edges(c) for c in control.etypes_dict}
    order=list(control.etypes_dict)
    parameters=sum(p.numel() for p in control.parameters())
    # Store only hashes/canonical metadata before building additional real models.
    del control;gc.collect()
    model=make_edge_model("node",graph,"G4R-P",f4_manifest=f4,**kwargs)
    assert tensor_digest(model.state_dict())==initial
    assert list(model.etypes_dict)==order
    assert {c:model.symmetrical_global_graph.num_edges(c) for c in order}==counts
    assert sum(p.numel() for p in model.parameters())==parameters
    binding=copy.deepcopy(model.edge_placebo_binding)
    expected_rows,audit=randomize_edges(graph,real,10000)
    assert degree_signature(graph,expected_rows)==degree_signature(graph,real)
    assert audit==binding["audit"]
    validate_registration(model)
    for what in ("seed","fold","audit","edge"):
        if what=="seed":
            old=copy.deepcopy(model.edge_seeds);model.edge_seeds["constructor"]+=1
        elif what=="fold":
            old=model.edge_placebo_fold;model.edge_placebo_fold+=1
        elif what=="audit":
            old=copy.deepcopy(model.edge_placebo_binding);model.edge_placebo_binding["audit"]["changed_edges"]+=1
        else:
            g=model.symmetrical_global_graph
            canonical=next(c for c in g.canonical_etypes if c[1]=="CALL_SITE" and g.num_edges(c) and g.num_nodes(c[0])>1)
            ss,tt=g.edges(etype=canonical,order="eid");old=int(ss[0]);ss[0]=(old+1)%g.num_nodes(canonical[0])
        with pytest.raises(ValueError):validate_registration(model)
        if what=="seed":model.edge_seeds=old
        elif what=="fold":model.edge_placebo_fold=old
        elif what=="audit":model.edge_placebo_binding=old
        else:ss[0]=old
    validate_registration(model)
    del model;gc.collect()
    repeat=make_edge_model("node",graph,"G4R-P",f4_manifest=f4,**kwargs)
    assert repeat.edge_placebo_binding==binding and tensor_digest(repeat.state_dict())==initial
    del repeat;gc.collect()
    kwargs["fold"]=1
    other=make_edge_model("node",graph,"G4R-P",f4_manifest=f4,**kwargs)
    assert other.edge_placebo_binding["rows_sha256"]!=binding["rows_sha256"]
    assert graph_fingerprint(graph)==before and not torch.cuda.is_initialized()
    target=os.environ.get("EDGESEM_EP7_PLACEBO_PROBES")
    if target:
        expected=ROOT/"scripts/edge_sem/artifacts/ep7_v1/placebo_probes"
        if Path(target).resolve()!=expected:raise ValueError("Unexpected receipt destination")
        write(expected/(task+".json"),dict(task_id=task,fold=0,initial_state_sha256=initial,
            parameter_count=parameters,canonical_order=[list(c) for c in order],
            edge_counts=[dict(canonical=list(c),count=counts[c]) for c in order],
            binding=binding,changed_fraction=audit["changed_edges"]/len(real),
            parameters_bitwise_equal=True,repeated_construct_equal=True,different_fold_changes_edges=True,
            degree_signature_equal=True,graph_unchanged=True,tamper_rejected=True,cuda_initialized=False))
