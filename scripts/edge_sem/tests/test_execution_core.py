"""EP7 small CPU numerical parity and strict input/binding gates."""
import ast
import copy
import json
from pathlib import Path
import pytest
import torch
from scripts.DFG.dfg_v2.tests.test_experiment_protocol import small_graph,PARTITION
from scripts.DFG.dfg_v2.benchmark_v2 import trainer as old_trainer,checkpoint as old_checkpoint,support as old_support
from scripts.DFG.dfg_v2.benchmark_v2.audit_supervision import make_part as old_part
from scripts.DFG.dfg_v2.benchmark_v2.input_guard import FitInputGuard as OldGuard
from scripts.DFG.dfg_v2 import AUX_NODE_TYPES
from scripts.DFG.experiments.common import write_json,tensor_digest,seed_all,digest,scheduler_metadata
from scripts.labeling_v2.safe_graph import write_graph
from scripts.edge_sem import trainer,checkpoint,support
from scripts.edge_sem.supervision import make_part
from scripts.edge_sem.model import make_edge_model
from scripts.edge_sem.input_guard import FitInputGuard
from scripts.edge_sem.io import ROOT,ref,read

LABELS={"train.sol":1,"val.sol":0,"test.sol":1}
CONFIG=dict(initial_lr=.001,max_lr=.005,weight_decay=.0001,
    schedule_epochs=50,div_factor=25,final_div_factor=10000,cycle_momentum=True,
    patience=51,delta=.001,maximum_training_epochs=3,mode="cpu_equivalence",layer_impl="shared_projection")


def setup_case(tmp_path,profile="G3R"):
    tmp_path.mkdir(parents=True,exist_ok=True)
    graph=small_graph("G3R")
    if profile=="G4R":
        # Synthetic E1 endpoint for registration, not a semantic builder proof.
        for file in LABELS:
            nodes=[n for n,a in graph.nodes(data=True) if a["source_file"]==file and a["node_type"] not in AUX_NODE_TYPES]
            graph.add_edge(nodes[0],nodes[-1],edge_type="CALL_SITE")
    write_graph(graph,tmp_path/"graph.gpickle")
    write_json(tmp_path/"labels.json",[dict(contract_name=f,targets=y) for f,y in LABELS.items()])
    write_json(tmp_path/"folds.json",PARTITION)
    model=make_edge_model("node",graph,profile,hidden_size=16,heads=4)
    rows=[]
    for i,a in model.nx_graph.nodes(data=True):
        if a["node_type"] in AUX_NODE_TYPES:continue
        y=model.node_labels[i]
        rows.append(dict(file=a["source_file"],original_graph_node_id=model.original_graph_node_ids[i],
            node_type=a["node_type"],orig=y,**{"L-orig_include":True,"L-orig_target":y,
            "L-audit_include":True,"L-audit_target":y}))
    write_json(tmp_path/"label_view.json",{"fixture_node":rows})
    write_json(tmp_path/"feature_view.json",{"purpose":"synthetic"})
    (tmp_path/"feature.npz").write_bytes(b"synthetic binding only")
    torch.save(model.state_dict(),str(tmp_path/"initial.pt"))
    counts=support.model_support(model,PARTITION)
    binding=checkpoint.build_binding(model,task_id="fixture_node",fold=0,seed=1,profile="G3R",reducer="mean",
        graph_ref=ref(tmp_path/"graph.gpickle"),fold_ref=ref(tmp_path/"folds.json"),
        label_ref=ref(tmp_path/"labels.json"),initial_sha256=ref(tmp_path/"initial.pt")["sha256"],
        config=CONFIG,split=PARTITION,support=counts)
    binding.update(initial_state_sha256=tensor_digest(model.state_dict()),label_policy="L-audit",
        label_view=ref(tmp_path/"label_view.json"),feature_view=ref(tmp_path/"feature_view.json"),
        feature_npz=ref(tmp_path/"feature.npz"),training_protocol="P2")
    parts={role:make_part(model,"node",PARTITION[role+"_files"],binding)
           for role in ("inner_train","inner_val","outer_test")}
    return graph,model,binding,parts,counts


def equal_nested(a,b):
    if isinstance(a,torch.Tensor):assert torch.equal(a,b)
    elif isinstance(a,dict):
        assert set(a)==set(b)
        for k in a:equal_nested(a[k],b[k])
    elif isinstance(a,(list,tuple)):
        assert len(a)==len(b)
        for x,y in zip(a,b):equal_nested(x,y)
    elif callable(a):
        assert a.__func__ is b.__func__ and type(a.__self__) is type(b.__self__)
    else:assert a==b


def test_frozen_numeric_functions_unchanged():
    for name in ("_fit","fit"):
        bodies=[]
        for module in (old_trainer,trainer):
            tree=ast.parse(Path(module.__file__).read_text())
            f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            bodies.append(ast.dump(f,include_attributes=False))
        assert bodies[0]==bodies[1]


def test_cpu_three_epoch_exact_parity(tmp_path):
    graph,model,binding,parts,counts=setup_case(tmp_path/"inputs")
    assert support.support(graph,"G3R",PARTITION)==old_support.support(graph,"G3R",PARTITION)
    assert counts==old_support.model_support(model,PARTITION)
    reference=copy.deepcopy(model)
    old_parts={r:old_part(reference,"node",PARTITION[r+"_files"],binding) for r in parts}
    old_checkpoint.validate_binding(reference,binding)
    checkpoint.validate_binding(model,binding)
    for engine,m,ps,guard_type,dest in (
        (old_trainer,reference,old_parts,OldGuard,tmp_path/"old"),
        (trainer,model,parts,FitInputGuard,tmp_path/"new")):
        seed_all(1010000)
        with guard_type(m,binding,ps,LABELS) as guard:
            result=engine.fit(m,guard.wrap_parts(),"node",LABELS,CONFIG,dest,binding,m.original_graph_node_ids,counts)
            guard.finish()
        assert result["history_rows"]==3 and guard.summary()["deep_boundaries"]==["start","after_training","after_evaluation"]
    equal_nested(reference.state_dict(),model.state_dict())
    for name in ("inner_val_predictions.json","outer_test_predictions.json","gradient_audit.json"):
        assert read(tmp_path/"old"/name)==read(tmp_path/"new"/name)
    for name in ("best","last"):
        a=torch.load(str(tmp_path/"old"/(name+".pt")),map_location="cpu")
        b=torch.load(str(tmp_path/"new"/(name+".pt")),map_location="cpu")
        for key in ("state_dict","optimizer","scheduler"):
            if key in a:equal_nested(a[key],b[key])
    old=[json.loads(x) for x in (tmp_path/"old/history.jsonl").read_text().splitlines()]
    new=[json.loads(x) for x in (tmp_path/"new/history.jsonl").read_text().splitlines()]
    assert [{k:v for k,v in r.items() if k!="seconds"} for r in old]==[{k:v for k,v in r.items() if k!="seconds"} for r in new]


@pytest.mark.parametrize("profile",["G3R","G3R-T","G4R"])
def test_bindings_accept_typed_and_reject_every_bound_field(tmp_path,profile):
    _,model,binding,_,_=setup_case(tmp_path,profile)
    checkpoint.freeze_binding(model,binding)
    for key in binding:
        changed=copy.deepcopy(binding)
        changed[key]="tampered" if binding[key] is None else None
        with pytest.raises((ValueError,KeyError,TypeError)):checkpoint.validate_binding(model,changed)
    checkpoint.validate_binding(model,binding)
    if profile=="G3R":
        old_checkpoint.validate_binding(model,binding)
        changed=copy.deepcopy(binding);changed["score_role"]="train"
        for f in (checkpoint.validate_binding,old_checkpoint.validate_binding):
            with pytest.raises(ValueError):f(model,changed)


@pytest.mark.parametrize("damage",["edge","feature","label","mask"])
def test_input_guard_rejects_mutation_before_checkpoint(tmp_path,damage):
    _,model,binding,parts,_=setup_case(tmp_path)
    with pytest.raises(ValueError):
        with FitInputGuard(model,binding,parts,LABELS) as guard:
            guard.start(binding)
            g=model.symmetrical_global_graph
            if damage=="edge":
                c=next(c for c in g.canonical_etypes if g.num_edges(c) and g.num_nodes(c[0])>1)
                ss,_=g.edges(etype=c,order="eid");ss[0]=(ss[0]+1)%g.num_nodes(c[0])
            elif damage=="feature":g.nodes[g.ntypes[0]].data["inp"][0,0]+=1
            elif damage=="label":model.node_labels[0]=1-model.node_labels[0]
            else:parts["inner_train"].mask[0]=~parts["inner_train"].mask[0]
            guard.fast_check(binding,"test")
