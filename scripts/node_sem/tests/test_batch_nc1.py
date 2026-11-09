"""N-C1 scope, provenance, paired initialization and authorization regression tests."""
import ast
import copy
import inspect
import json
from pathlib import Path
import pytest
import torch
from torch import nn
from scripts.node_sem import batch_nc1 as nc, batch_na as na
from scripts.node_sem import batch_nc1_worker as worker, batch_na_worker as old
from scripts.node_sem import batch_nc1_controller as controller
from scripts.node_sem.nc1_init import merge_common, validate_rebuilt, baseline_state, paired_state
from scripts.node_sem.feature_spec import FeatureSpec
from scripts.node_sem.adapter import NodeSemAdapter
from scripts.node_sem.tests.test_batch_na import policy
from scripts.node_sem.tests.test_init import sealed, model
from scripts.node_sem.init import initial_state
from scripts.DFG.experiments.common import tensor_digest, digest
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref, checked


def jobs():
    return [dict(j,device_policy=policy()) for j in nc.matrix()]


def envelope():
    p=dict(version=nc.VERSION,protocol=nc.PROTOCOL_NAME,protocol_version=nc.PROTOCOL_VERSION,
        view="original",label_policy="L-audit",execution_authorized=False,jobs=jobs(),
        device_families={t:policy() for t,_ in nc.TASK_FOLDS},statistics=nc.statistics_spec(),
        resource_policy=nc.LOCAL_DEV_POLICY,initialization_version=nc.INIT_VERSION)
    r=dict(path="/plan.json",sha256="a"*64)
    return p,dict(version=nc.VERSION,plan=r,jobs=30,matrix_sha256=digest(p["jobs"])),r


def spec():
    return FeatureSpec.from_json(json.loads((Path(nc.ROOT)/"scripts/node_sem/configs/S4.json").read_text()))


def test_exact_matrix_order_and_teacher_extension():
    js=jobs();nc.validate_matrix(js)
    assert len(set(nc.execution_order(js)))==30
    assert [js[i]["task_id"] for i in (0,10,20,25)]==[t for t,_ in nc.TASK_FOLDS]
    s4=spec();s6=nc.make_spec(s4,dict(path="/teacher",sha256="a"*64))
    assert s6.carrier_dim()==1145 and s4.carrier_dim()==760
    assert s6.modalities[:-1]==s4.modalities
    for k in ("view","token_mode","fusion","modality_dropout","layers"):
        assert getattr(s4,k)==getattr(s6,k)


@pytest.mark.parametrize("damage",["missing","duplicate","order","seed","name","profile","view","granularity","boolean"])
def test_wrong_matrix_rejected(damage):
    js=jobs()
    if damage=="missing":js.pop()
    elif damage=="duplicate":js[1]=copy.deepcopy(js[0])
    elif damage=="order":js[0],js[1]=js[1],js[0]
    elif damage=="boolean":js[0]["fold"]=False
    else:js[0][damage]=dict(seed=2,name="S4",profile="G0",view="anonymous",granularity="contract")[damage]
    with pytest.raises(ValueError):nc.validate_matrix(js)


@pytest.mark.parametrize("damage",["sha","version","count","matrix","statistics","authorization","protocol","initialization","resource","device"])
def test_plan_seal_tampering(damage):
    p,s,r=envelope();assert nc.validate_envelope(p,s,r)
    if damage=="sha":s["plan"]=dict(r,sha256="b"*64)
    elif damage=="version":s["version"]="old"
    elif damage=="count":s["jobs"]=29
    elif damage=="matrix":s["matrix_sha256"]="c"*64
    elif damage=="statistics":p["statistics"]["primary"]["checkpoint"]="last"
    elif damage=="authorization":p["execution_authorized"]=True
    elif damage=="protocol":p["protocol"]="paper_kfold"
    elif damage=="initialization":p["initialization_version"]="random"
    elif damage=="resource":p["resource_policy"]=dict(p["resource_policy"],running_minimum_free_mib=0)
    else:p["device_families"]["reentrancy_node"]["allow_tf32"]["matmul"]=False
    with pytest.raises(ValueError):nc.validate_envelope(p,s,r)


@pytest.mark.parametrize("field",["location","gpu_model","torch_version","cuda_build_version","matmul","cudnn"])
def test_device_and_tf32_comparison_rejected(field):
    js=jobs();nc.validate_device_comparisons(js)
    changed=copy.deepcopy(js);p=changed[1]["device_policy"]
    if field in ("matmul","cudnn"):p["allow_tf32"][field]=False
    else:p[field]="different"
    with pytest.raises(ValueError):nc.validate_device_comparisons(changed)
    records=[dict(j,actual_device=copy.deepcopy(j["device_policy"])) for j in js]
    records[0]["actual_device"]["allow_tf32"]["matmul"]=False
    with pytest.raises(ValueError):nc.validate_device_comparisons(js,records)


@pytest.mark.parametrize("a,b,want",[(0,0,False),(-1,-2,False),(0.01,0,True),(0,0.01,True),(-2,1,True)])
def test_continuation_only_two_registered_numbers(a,b,want):
    value=nc.continuation(a,b)
    assert value["continue_student"]==want and not value["automatic_execution"]
    assert len(inspect.signature(nc.continuation).parameters)==2
    assert nc.statistics_spec()["primary"]["number_of_tests"]==1


@pytest.mark.parametrize("v",[None,True,float("nan"),float("inf"),"1"])
def test_missing_or_invalid_continuation_not_zero(v):
    with pytest.raises(ValueError):nc.continuation(v,0)
    with pytest.raises(ValueError):nc.continuation(0,v)


def test_formal_core_alias_config_and_old_admission_unchanged():
    assert worker.construct is old.construct and worker.run_core is old.run_core
    assert worker.formal_config is old.formal_config
    j=dict(jobs()[0],config=dict(maximum_training_epochs=50,patience=7,initial_lr=0.001))
    assert worker.formal_config(dict(jobs=[j]),j)==j["config"]
    with pytest.raises(ValueError):worker.formal_config(dict(jobs=[j]),dict(j,config={"maximum_training_epochs":1}))
    p,s,r=envelope()
    with pytest.raises(ValueError):na.validate_envelope(p,s,r)
    assert "maximum_training_epochs" not in inspect.getsource(worker.run_formal)


def test_no_authorization_means_no_launch(tmp_path,monkeypatch):
    p,_,_=envelope()
    monkeypatch.setattr(nc,"load",lambda *a,**k:p)
    (tmp_path/"plan.json").write_text(json.dumps(p))
    (tmp_path/"execution_decisions.json").write_text(json.dumps(dict(execution_authorized=False)))
    with pytest.raises(PermissionError):controller.seal(tmp_path)


@pytest.mark.parametrize("kind",["receipt","graph","labels","carrier","teacher","initial"])
def test_bound_files_reject_changed_bytes(tmp_path,kind):
    f=tmp_path/kind;f.write_bytes(b"original")
    r=ref(f);assert checked(r)==f.resolve()
    f.write_bytes(b"tampered")
    with pytest.raises(ValueError):checked(r)


def test_common_tensors_exact_new_only_teacher_no_alias():
    base={"gcs.weight":torch.ones(2),"adapt_ws.0.proj.code.weight":torch.ones(2,3)}
    candidate={k:torch.zeros_like(v) for k,v in base.items()}
    candidate["adapt_ws.0.proj.teacher.weight"]=torch.randn(2,4)
    original={k:v.clone() for k,v in candidate.items()}
    result,proof=merge_common(candidate,base)
    assert proof["common_bitwise_equal"] and proof["common_keys"]==2
    assert all(torch.equal(result[k],v) for k,v in base.items())
    assert torch.equal(result["adapt_ws.0.proj.teacher.weight"],candidate["adapt_ws.0.proj.teacher.weight"])
    result["gcs.weight"].zero_()
    assert torch.all(base["gcs.weight"]==1)
    assert all(torch.equal(candidate[k],v) for k,v in original.items())
    candidate["rogue"]=torch.zeros(1)
    with pytest.raises(ValueError):merge_common(candidate,base)


def test_rebuild_digest_must_match_not_shape_only():
    state={"p":torch.arange(4.)};job={"initial":{"state_sha256":tensor_digest(state)}}
    assert validate_rebuilt(state,job) is state
    with pytest.raises(ValueError):validate_rebuilt({"p":state["p"]+1},job)


def test_actual_init_rule_rebuild_and_shared_parameters(tmp_path,monkeypatch):
    reference,_=sealed(tmp_path,monkeypatch)
    s4=spec();s6=nc.make_spec(s4,dict(path="/teacher",sha256="a"*64))
    m4=model("S0");m4.adapt_ws=nn.ModuleList([NodeSemAdapter(s4,str(i)) for i in range(2)])
    m6=model("S0");m6.adapt_ws=nn.ModuleList([NodeSemAdapter(s6,str(i)) for i in range(2)])
    s4state,s4sha=initial_state(m4,s4,"fixture_node",0,"G0",reference)
    path=tmp_path/"s4spec.json";path.write_text(json.dumps(s4.to_json()))
    j=dict(task_id="fixture_node",fold=0,profile="G0",h8_initial=reference,spec=ref(path),
        spec_sha256=s4.digest(),initial=dict(path=str(tmp_path/"missing.pt"),sha256="a"*64,state_sha256=s4sha))
    base,mode=baseline_state(j,m4)
    assert mode=="reconstructed_exact_NA_digest" and tensor_digest(base)==s4sha
    state,proof=paired_state(m6,s6,j,base)
    assert all(torch.equal(state[k],v) for k,v in s4state.items())
    again,_=paired_state(m6,s6,j,base)
    assert tensor_digest(state)==tensor_digest(again)
    j["initial"]["state_sha256"]="f"*64
    with pytest.raises(ValueError):baseline_state(j,m4)


def test_teacher_missing_keeps_s4_eval_adapter_output():
    torch.manual_seed(1);s4=spec();s6=nc.make_spec(s4,dict(path="/teacher",sha256="a"*64))
    a=NodeSemAdapter(s4,"statement");b=NodeSemAdapter(s6,"statement")
    base={"adapt_ws.0."+k:v for k,v in a.state_dict().items()}
    candidate={"adapt_ws.0."+k:v for k,v in b.state_dict().items()}
    merged,_=merge_common(candidate,base)
    b.load_state_dict({k[len("adapt_ws.0."):]:v for k,v in merged.items()})
    x=torch.randn(5,s4.carrier_dim());x[:,:3]=1
    y=torch.zeros(5,s6.carrier_dim());y[:,:3]=1
    for name,part in s4.layout().items():
        new=s6.layout()[name];y[:,new["start"]:new["stop"]]=x[:,part["start"]:part["stop"]]
    a.eval();b.eval()
    assert torch.allclose(a(x),b(y),atol=1e-6,rtol=1e-6)
    # The frozen carrier contract is float32; a float64 oracle uses functional
    # operations, without relaxing or changing the production adapter.
    def reference(adapter, values):
        out = torch.zeros(values.shape[0],128,dtype=torch.float64)
        for m in adapter.spec.modalities:
            part=adapter.spec.layout()[m["name"]]
            v=values[:,part["start"]:part["stop"]].double().contiguous()
            if m["name"] in adapter.norm:
                norm=adapter.norm[m["name"]]
                v=torch.nn.functional.layer_norm(v,norm.normalized_shape,
                    norm.weight.double(),norm.bias.double(),norm.eps)
            out += torch.nn.functional.linear(v,adapter.proj[m["name"]].weight.double()) * values[:,part["presence"]:part["presence"]+1].double()
        return out+adapter.bias.double()
    assert torch.allclose(reference(a,x),reference(b,y),atol=1e-12,rtol=1e-12)


def test_worker_compute_body_only_changes_purpose():
    from scripts.node_sem import batch_nb_worker as nb
    def body(fn):
        tree=ast.parse(inspect.getsource(fn))
        node=tree.body[0]
        at=next(i for i,n in enumerate(node.body) if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=="attempt" for t in n.targets))
        return ast.dump(ast.Module(body=node.body[at:]),include_attributes=False)
    assert body(worker.run_formal).replace("formal_NC1","formal_NB")==body(nb.run_formal)
