"""EP3 real CPU G4R gates including exact GUARDS relations and reverse rows."""
import gc
import json
import os
import time
from pathlib import Path
import pytest
import torch
from scripts.edge_sem.tests.test_model_equivalence import real_graph,compare_models
from scripts.edge_sem.tests.test_build_f4_model import verify_banks
from scripts.edge_sem.build_f4 import load_edges,add_edges
from scripts.edge_sem.model import make_edge_model,validate_registration
from scripts.edge_sem.recon.common import ROOT,ref,checked,read
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint

OUT=ROOT/"scripts/edge_sem/artifacts/ep3_v1"

@pytest.mark.parametrize("task",["reentrancy_node","access_control_node"])
def test_ep3_real_g4r_with_complete_e1(task):
    inputs,item,original=real_graph(task)
    before=graph_fingerprint(original);checked(item["graph_refs"]["F3"])
    cfg=item["config"];kwargs=dict(fold=0,hidden_size=cfg["hidden_size"],layers=cfg["layers"],heads=cfg["heads"])
    start=time.monotonic()
    base=make_edge_model("node",original,"G3R-T",**kwargs)
    empty=make_edge_model("node",original,"G4R",**kwargs)
    compare_models(base,empty);base.eval();empty.eval()
    with torch.no_grad():a,b=base(),empty()
    assert torch.equal(a,b)
    empty_seconds=time.monotonic()-start
    del empty,a,b;gc.collect()
    manifest=OUT/task/"manifest.json";rows=load_edges(manifest)
    assert read(manifest)["task_id"]==task
    enriched=add_edges(original,rows)
    assert graph_fingerprint(original)==before
    assert enriched.number_of_nodes()==original.number_of_nodes()
    assert enriched.number_of_edges()==original.number_of_edges()+len(rows)
    start=time.monotonic()
    model=make_edge_model("node",enriched,"G4R",**kwargs)
    seconds=time.monotonic()-start
    validate_registration(model)
    new_rows=verify_banks(base,model,allowed_new=("MOD_APPLY","CALL_SITE","GUARDS"))
    repeated=make_edge_model("node",enriched,"G4R",**kwargs)
    compare_models(model,repeated)
    del repeated;gc.collect()
    model.eval();start=time.monotonic()
    output=model();objective=output.square().mean();objective.backward()
    assert bool(torch.isfinite(output).all()) and bool(torch.isfinite(objective))
    assert any(p.grad is not None and bool((p.grad!=0).any()) for p in model.parameters())
    assert all(p.grad is None or bool(torch.isfinite(p.grad).all()) for p in model.parameters())
    assert graph_fingerprint(original)==before and not torch.cuda.is_initialized()
    checked(item["graph_refs"]["F3"])
    prior=read(ROOT/"scripts/edge_sem/artifacts/ep2_v1/probes"/(task+"_G4R_fold0.json"))
    ep2_keys={tuple(r["canonical"]) for r in prior["canonical_counts"]}
    added=sorted(set(model.etypes_dict)-ep2_keys)
    assert added and all(c[1] in ("GUARDS","REV_GUARDS") for c in added)
    new_counts=[dict(canonical=list(c),edges=model.symmetrical_global_graph.num_edges(c)) for c in added]
    result=dict(task_id=task,fold=0,profile="G4R",empty_matches_typed_bitwise=True,
        schema_count=len(model.etypes_dict),base_schema_count=len(base.etypes_dict),
        added_since_ep2=new_counts,added_sparse_lt20=[r for r in new_counts if r["edges"]<20],
        new_canonical_rows=new_rows,parameter_count=sum(p.numel() for p in model.parameters()),
        empty_gate_seconds=empty_seconds,construction_seconds=seconds,
        forward_backward_seconds=time.monotonic()-start,forward_backward_finite=True,
        common_parameters_equal=True,new_rows_match_relation_seed=True,repeated_initialization_equal=True,
        graph_unchanged=True,source_file_unchanged=True,cuda_initialized=False,optimizer_steps=0,
        objective="mean squared logits, no supervision or optimizer",
        source_graph=item["graph_refs"]["F3"],historical_feature_view=item["feature_view"],
        config=cfg,edge_manifest=ref(manifest),edge_rows=len(rows),
        canonical_counts=[dict(canonical=list(c),edges=model.symmetrical_global_graph.num_edges(c)) for c in sorted(model.etypes_dict)])
    dest=os.environ.get("EDGESEM_EP3_RECEIPTS")
    if dest:
        path=Path(dest).resolve()
        assert path==OUT/"probes" and (OUT/"before.json").is_file()
        path.mkdir(exist_ok=True)
        with (path/(task+"_G4R_fold0.json")).open("x",encoding="utf8") as f:
            json.dump(result,f,sort_keys=True,indent=2);f.write("\n")
    del base,model,original,enriched,output,objective;gc.collect()
