"""Prompt 8H supervision and frozen-engine regression acceptance."""
import copy
import json
from pathlib import Path
import pytest
import torch
from torch.nn import functional as F
from scripts.DFG.dfg_v2.tests.test_experiment_trainer import setup_case, LABELS
from scripts.DFG.dfg_v2.tests.test_model import hcg, augment
from scripts.DFG.dfg_v2.benchmark_v2.audit_supervision import AuditSupervision, bind_rows, make_part
from scripts.DFG.dfg_v2.benchmark_v2 import checkpoint, trainer
from scripts.DFG.dfg_v2.benchmark_v2.input_guard import FitInputGuard
from scripts.DFG.dfg_v2.benchmark_v2.protocol import PROTOCOL_NAME,PROTOCOL_VERSION
from scripts.DFG.experiments.common import digest,sha256,seed_all,read_json

def audit_case(path,task="node",profile="G3R",flip_excluded=False):
    model,oldparts,graph,binding,support,config=setup_case(path,task,profile)
    rows=[]
    for i,d in model.nx_graph.nodes(data=True):
        if d["node_type"]=="env_source":continue
        if task=="node":
            included=(i % 3 != 0)
            rows.append(dict(file=d["source_file"],original_graph_node_id=model.original_graph_node_ids[i],
                node_type=d["node_type"],orig=model.node_labels[i],
                **{"L-orig_target":model.node_labels[i],"L-orig_include":True,
                   "L-audit_target":(1-model.node_labels[i]) if not included and flip_excluded else model.node_labels[i],
                   "L-audit_include":included}))
    if task=="contract":
        rows=[dict(file=f,orig=y,**{"L-orig_target":y,"L-orig_include":True,
            "L-audit_target":y,"L-audit_include":True}) for f,y in LABELS.items()]
    view=path/"label_view.json";view.write_text(json.dumps({"synthetic_"+task:rows}))
    ref=lambda p:dict(path=str(p),sha256=sha256(p))
    # Small synthetic fixture uses an opaque feature manifest/payload; production
    # feature assembly is independently checked by spelling_features.
    feature=path/"feature_manifest.json";feature.write_text("{}")
    npz=path/"feature_payload";npz.write_bytes(b"synthetic")
    binding.update(protocol=PROTOCOL_NAME,protocol_version=PROTOCOL_VERSION,label_policy="L-audit",
        label_view=ref(view),feature_view=ref(feature),feature_npz=ref(npz))
    parts={role:make_part(model,task,part.files,binding) for role,part in oldparts.items()}
    return model,parts,graph,binding,support,config

@pytest.mark.parametrize("profile",["G0","G3R"])
def test_masked_logits_have_no_direct_loss_gradient(tmp_path,profile):
    m,parts,g,b,s,c=audit_case(tmp_path,profile=profile)
    p=parts["inner_train"]
    logits=m().detach().requires_grad_(True)
    F.cross_entropy(logits[p.mask],p.targets(m,LABELS)).backward()
    assert not logits.grad[~p.mask].count_nonzero()
    assert logits.grad[p.mask].abs().sum()>0
    assert len(m.nx_graph)==len(g)
    assert len(p.full_ids)<len(p.all_full_ids)
    # Exclusion concerns direct supervised loss, not graph message propagation.

@pytest.mark.parametrize("task",["node","contract"])
def test_full_audit_fit_primary_and_orig_all_exports(tmp_path,task):
    m,p,g,b,s,c=audit_case(tmp_path,task)
    dest=tmp_path/"fit";seed_all(1000073)
    with FitInputGuard(m,b,p,LABELS) as guard:
        r=trainer.fit(m,guard.wrap_parts(),task,LABELS,c,dest,b,list(g),s)
        guard.finish()
    assert guard.summary()["deep_boundaries"]==["start","after_training","after_evaluation"]
    assert r["label_policy"]=="L-audit" and r["protocol"]==PROTOCOL_NAME
    for role in ("inner_val","outer_test"):
        main=read_json(dest/(role+"_predictions.json"))
        aux=read_json(dest/(role+"_orig_all_predictions.json"))
        if task=="node":
            assert len(main)==len(p[role].full_ids)
            assert len(aux)==len(p[role].all_full_ids)
            assert all(row["node_type"]!="env_source" for row in aux)
            assert any(not row["primary_include"] for row in aux)
        else:assert main==aux
    assert all(x for row in r["checkpoint_roundtrip_exact"].values() for x in row.values())

def test_changing_excluded_labels_does_not_change_loss_best_or_parameters(tmp_path):
    results=[]
    for changed in (False,True):
        root=tmp_path/str(changed)
        m,p,g,b,s,c=audit_case(root,flip_excluded=changed)
        seed_all(1000073)
        with FitInputGuard(m,b,p,LABELS) as guard:
            r=trainer.fit(m,guard.wrap_parts(),"node",LABELS,c,root/"fit",b,list(g),s)
            guard.finish()
        ck=torch.load(str(root/"fit/last.pt"),map_location="cpu")
        h=[json.loads(line) for line in (root/"fit/history.jsonl").read_text().splitlines()]
        results.append((r,ck,h))
    a,b=results
    assert a[0]["best_epoch"]==b[0]["best_epoch"]
    assert a[0]["inner_val"]==b[0]["inner_val"] and a[0]["outer_test"]==b[0]["outer_test"]
    for x,y in zip(a[2],b[2]):
        assert x["train_loss"]==y["train_loss"] and x["inner_val_loss"]==y["inner_val_loss"]
    assert all(torch.equal(v,b[1]["state_dict"][k]) for k,v in a[1]["state_dict"].items())

@pytest.mark.parametrize("field",["audit_targets","audit_include","mask"])
def test_audit_tensor_tamper_rejected_by_fit_and_fast_guard(tmp_path,field):
    m,p,g,b,s,c=audit_case(tmp_path)
    with pytest.raises(ValueError,match="Frozen fit input"):
        with FitInputGuard(m,b,p,LABELS) as guard:
            checkpoint.snapshot_input(m,b)
            value=getattr(p["inner_train"],field)
            value[0]=value[0]
            guard.fast_check(b,"test")

@pytest.mark.parametrize("damage",["duplicate","file","original_graph_node_id","orig","node_type","include_type"])
def test_wrong_label_view_identity_rejected(tmp_path,damage):
    m,p,g,b,s,c=audit_case(tmp_path)
    path=Path(b["label_view"]["path"]);d=read_json(path);rows=d[b["task_id"]]
    if damage=="duplicate":rows.append(copy.deepcopy(rows[0]))
    elif damage=="orig":rows[0]["orig"]=1-rows[0]["orig"]
    elif damage=="include_type":rows[0]["L-audit_include"]=1
    else:rows[0][damage]="wrong"
    path.write_text(json.dumps(d));b["label_view"]["sha256"]=sha256(path)
    with pytest.raises(ValueError):bind_rows(m,b["task_id"],b["label_view"])

@pytest.mark.parametrize("key",["graph","folds","labels","label_view","feature_view","feature_npz"])
def test_bound_file_change_rejected(tmp_path,key):
    m,p,g,b,s,c=audit_case(tmp_path)
    with Path(b[key]["path"]).open("ab") as handle:handle.write(b"changed")
    with pytest.raises(ValueError):checkpoint.validate_binding(m,b)

@pytest.mark.parametrize("damage",["none","endpoints","schema","features"])
def test_placebo_preserves_G0_and_rejects_drift(tmp_path,damage):
    from scripts.DFG.dfg_v2.benchmark_v2.runtime_model import make_placebo,validate_registration
    from scripts.DFG.dfg_v2.diagnostics8c.placebo import EMPTY_PREFIX
    from scripts.DFG.dfg_v2.experiment.init import semantic_state
    m,p,g,b,s,c=setup_case(tmp_path,profile="G0")
    target={t:sum(x[2]==t for x in m.etypes_dict)+2 for t in m.ntypes_dict}
    before=semantic_state(m);placebo=make_placebo(m,target);after=semantic_state(placebo)
    assert all(torch.equal(v,after[k]) for k,v in before.items())
    assert placebo.original_graph_node_ids==m.original_graph_node_ids
    assert placebo.node_labels==m.node_labels
    assert all(placebo.symmetrical_global_graph.num_edges(x)==0 for x in placebo.etypes_dict if x[1].startswith(EMPTY_PREFIX))
    if damage=="none":
        validate_registration(placebo)
        return
    if damage=="schema":
        key=next(iter(placebo.etypes_dict));placebo.etypes_dict[key]+=1
    elif damage=="features":
        t=placebo.symmetrical_global_graph.ntypes[0];placebo.symmetrical_global_graph.nodes[t].data["inp"].add_(1)
    else:
        key=next(x for x in placebo.etypes_dict if placebo.symmetrical_global_graph.num_edges(x)>0)
        src,dst=placebo.symmetrical_global_graph.edges(etype=key);src[0]=(src[0]+1)%placebo.symmetrical_global_graph.num_nodes(key[0])
    with pytest.raises(ValueError):validate_registration(placebo)

def test_changed_audit_target_rejected_before_first_step(tmp_path):
    m,p,g,b,s,c=audit_case(tmp_path)
    i=p["inner_train"].full_ids[0]
    p["inner_train"].audit_targets[i]=1-p["inner_train"].audit_targets[i]
    with pytest.raises(ValueError,match="Supervision mask"):
        trainer._validate_fit_inputs(m,p,"node",LABELS,c,b,list(g),s)

def test_old_protocol_dispatch_uses_old_executor(tmp_path,monkeypatch):
    from scripts.DFG.dfg_v2.benchmark_v2.execution import execute
    from scripts.DFG.dfg_v2.experiment import run as old
    p=tmp_path/"plan.json";p.write_text(json.dumps({"protocol":"dfg-v2-nested"}))
    seen=[]
    monkeypatch.setattr(old,"execute",lambda path,only:seen.append((path,only)))
    execute(p,"task/0/1/G0")
    assert seen==[(p,"task/0/1/G0")]

def test_missing_gate_refuses_execution_preparation(tmp_path,monkeypatch):
    from scripts.DFG.dfg_v2.benchmark_v2 import execution
    monkeypatch.setattr(execution,"DEFAULT",tmp_path)
    with pytest.raises(ValueError,match="Mandatory acceptance"):execution.gate("missing.json")

def test_controller_stops_on_prior_failure_without_launch(tmp_path,monkeypatch):
    from scripts.DFG.dfg_v2.benchmark_v2 import execution
    job=dict(task_id="synthetic_node",fold=0,seed=1,profile="G0")
    plan=dict(jobs=[job])
    monkeypatch.setattr(execution,"load",lambda p:plan)
    monkeypatch.setattr(execution,"gate",lambda n:None)
    folder=execution._job_directory(tmp_path,job);folder.mkdir(parents=True)
    (folder/"attempt_001.started.json").write_text("{}")
    monkeypatch.setattr(execution.subprocess,"run",lambda *a,**k:pytest.fail("A failed batch must not launch a worker"))
    with pytest.raises(RuntimeError,match="Prior incomplete"):execution.controller(tmp_path/"plan.json")

def test_non_solidifi_only_counts_and_proportion_intervals():
    from scripts.DFG.dfg_v2.benchmark_v2.reporting import stratified_score
    result=stratified_score([{"target":1,"best":1},{"target":0,"best":1}],"best","nonSolidiFI")
    assert "buggy_f1" not in result and result["tp"]==1 and result["fp"]==1
    assert result["precision_wilson95"] and result["recall_wilson95"]

def test_new_worker_uses_same_cross_protocol_gpu_lock(tmp_path,monkeypatch):
    from scripts.DFG.dfg_v2.benchmark_v2 import execution
    from scripts.DFG.dfg_v2.experiment.run import _Lock
    job=dict(task_id="synthetic_node",fold=0,seed=1,profile="G0")
    path=tmp_path/"plan.json";path.write_text(json.dumps({"protocol":PROTOCOL_NAME}))
    monkeypatch.setattr(execution,"ROOT",tmp_path)
    monkeypatch.setattr(execution,"load",lambda p:dict(jobs=[job]))
    held=[]
    def worker(p,j):
        with pytest.raises(RuntimeError,match="Another"):
            with _Lock(tmp_path/"scripts/DFG/experiments/artifacts/dfg_v2/.training.lock"):
                pytest.fail("Old and new workers must share the same GPU lock")
        held.append(True)
    monkeypatch.setattr(execution,"fit_one",worker)
    execution.execute(path,execution.job_id(job))
    assert held==[True]

@pytest.mark.parametrize("task",["node","contract"])
@pytest.mark.parametrize("profile",["G1R","G2R","G3R","G3"])
def test_untrained_structure_reuse_exactly_matches_fresh(hcg,task,profile):
    from scripts.DFG.dfg_v2.benchmark_v2.initial_preparation import UntrainedStructures
    from scripts.DFG.dfg_v2.model import make_model
    from scripts.DFG.dfg_v2.tests.test_experiment_protocol import small_graph
    from scripts.DFG.dfg_v2.experiment.init import initialize_family,seeds
    graphs={"G0":hcg,profile:augment(hcg,profile)}
    config=dict(hidden_size=16,layers=2,heads=4)
    cache=UntrainedStructures(task,graphs,config)
    prior=None
    for fold in (0,1):
        seed=seeds(task,fold)["constructor"]
        seed_all(seed)
        anchor=make_model(task,graphs["G0"],"G0","cpu",reducer="mean",layer_impl="shared_projection",**config)
        seed_all(seed)
        fresh=make_model(task,graphs[profile],profile,"cpu",reducer="mean",layer_impl="shared_projection",**config)
        initialize_family({"G0":anchor,profile:fresh},seed)
        seed_all(seed)
        reused=cache.get(profile)
        if prior is not None:
            assert reused is prior
            with torch.no_grad():
                for param in reused.parameters():param.fill_(123)
        initialize_family({"G0":anchor,profile:reused},seed)
        assert set(fresh.state_dict())==set(reused.state_dict())
        assert all(torch.equal(v,reused.state_dict()[k]) for k,v in fresh.state_dict().items())
        assert all(p.grad is None for p in reused.parameters())
        prior=reused

@pytest.mark.parametrize("damage",["steps","grad","profile"])
def test_structure_cache_refuses_training_or_invalid_profile(damage):
    from scripts.DFG.dfg_v2.benchmark_v2.initial_preparation import UntrainedStructures
    from scripts.DFG.dfg_v2.tests.test_experiment_protocol import small_graph
    cache=UntrainedStructures("node",{"G3R":small_graph("G3R")},dict(hidden_size=16,layers=2,heads=4))
    if damage=="profile":
        with pytest.raises(ValueError):cache.get("G0")
        return
    m=cache.get("G3R")
    if damage=="steps":m.optimizer_steps=1
    else:next(m.parameters()).grad=torch.zeros_like(next(m.parameters()))
    with pytest.raises(ValueError):cache.get("G3R")
