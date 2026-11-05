"""N-B matrix, provenance, no-G/masked semantics and unchanged training core."""
import copy
import json
from pathlib import Path
import pytest
import torch
from torch import nn
from scripts.node_sem import batch_nb as nb, batch_na as na
from scripts.node_sem import batch_nb_worker as worker, batch_na_worker as old_worker
from scripts.node_sem import batch_nb_controller as controller
from scripts.node_sem.p6_prepare import bind_spec
from scripts.node_sem.feature_spec import FeatureSpec
from scripts.node_sem.adapter import NodeSemAdapter
from scripts.node_sem.init import initial_state
from scripts.node_sem.tests.test_batch_na import policy
from scripts.node_sem.tests.test_init import sealed, model
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
from scripts.DFG.experiments.common import digest


def jobs():
    return [dict(j, reuse_8h=False, view="original", device_policy=policy()) for j in nb.matrix()]


def envelope():
    plan = dict(version=nb.VERSION, protocol=nb.PROTOCOL_NAME, protocol_version=nb.PROTOCOL_VERSION,
        view="original", label_policy="L-audit", execution_authorized=False,
        source_preparation={"source":"frozen"}, statistics=nb.statistics_spec(),
        jobs=jobs(), device_families={t:policy() for t,_ in nb.TASK_FOLDS}, runtime={"r.py":"a"*64})
    reference = dict(path="/plan.json",sha256="a"*64)
    seal = dict(version=nb.VERSION,plan=reference,jobs=120,matrix_sha256=digest(plan["jobs"]))
    return plan,seal,reference


def refs():
    r=lambda n:dict(path="/"+n,sha256="a"*64)
    return dict(code=r("code"),static=r("static"),ctx=dict(original=r("ctx"),masked=r("masked")))


def test_exact_matrix_and_priority_no_pilot_duplicates():
    js=jobs(); assert nb.validate_matrix(js)
    assert {n:sum(j["name"]==n for j in js) for n in nb.NAMES} == {n:30 for n in nb.NAMES}
    assert sum(j["granularity"]=="contract" for j in js)==40
    order=controller.ordered(js);byid={worker.job_id(j):j for j in js}
    assert len(order)==len(set(order))==120
    assert all(byid[k]["task_id"]=="reentrancy_node" for k in order[:40])
    assert all(j["profile"]==("G0" if j["name"]=="S4-noG" else "G3R") for j in js)


@pytest.mark.parametrize("damage",["missing","duplicate","fold","seed","profile","name","view","reuse_8h","granularity","boolean"])
def test_matrix_changes_rejected(damage):
    js=jobs()
    if damage=="missing":js.pop()
    elif damage=="duplicate":js[1]=copy.deepcopy(js[0])
    elif damage=="boolean":js[0]["fold"]=False
    else:js[0][damage]=dict(fold=100,seed=2,profile="G0",name="S4",view="anonymous",
                            reuse_8h=True,granularity="node")[damage]
    with pytest.raises(ValueError):nb.validate_matrix(js)


@pytest.mark.parametrize("damage",["sha","count","version","stats","protocol","labels","authorization","device"])
def test_envelope_changes_rejected(damage):
    p,s,r=envelope();assert nb.validate_envelope(p,s,r)
    if damage=="sha":s["plan"]["sha256"]="f"*64;r=dict(r,sha256="a"*64)
    elif damage=="count":s["jobs"]=119
    elif damage=="version":p["version"]=na.VERSION
    elif damage=="stats":p["statistics"]["inferential_tests"]=True
    elif damage=="protocol":p["protocol"]="paper_kfold"
    elif damage=="labels":p["label_policy"]="orig"
    elif damage=="authorization":p["execution_authorized"]=True
    else:p["device_families"]["reentrancy_node"]["allow_tf32"]["matmul"]=False
    with pytest.raises(ValueError):nb.validate_envelope(p,s,r)


def test_masked_only_ctx_and_exact_zero_layer():
    data=refs()
    for n in nb.NAMES:
        sp=bind_spec(n,data,None)
        assert sp.view=="original"
        assert sp.layers==(0 if n=="S4-noG" else None)
        assert sp.fusion==("gated" if n=="S4g" else "concat")
        assert sp.carrier_dim()==(514 if n=="S3" else 760)
        assert sp.modalities[0]["manifest"]==data["code"]
        assert sp.modalities[1]["manifest"]==data["ctx"]["masked" if n=="S4m" else "original"]


def test_predeclared_and_posthoc_no_double_counting():
    s=nb.statistics_spec()
    assert s["primary"] is None and not s["holm_family"] and not s["inferential_tests"]
    assert s["planned_comparisons"].count(["S3","G3R","S2","G3R"])==1
    assert ["S3","S2"] not in s["posthoc_comparisons"]
    assert ["S3","S2"] in s["posthoc_stratification_comparisons"]
    assert s["strata"]["bf1_interval"] is None
    assert "no learned gate" in s["gate_report"]["S2"]


def test_formal_training_core_is_same_function_and_config_unmodified():
    assert worker.run_core is old_worker.run_core
    assert worker.construct is old_worker.construct
    assert worker.formal_config is old_worker.formal_config
    job=dict(jobs()[0],config=dict(maximum_training_epochs=50,patience=7,lr=0.001))
    p=dict(jobs=[job])
    got=worker.formal_config(p,job)
    assert got==job["config"] and got is not job["config"]
    assert got["maximum_training_epochs"]==50
    with pytest.raises(ValueError):worker.formal_config(p,dict(job,config=dict(lr=1)))


def test_na_refuses_nb_and_nb_refuses_na():
    p,s,r=envelope()
    with pytest.raises(ValueError):na.validate_envelope(p,s,r)
    from scripts.node_sem.tests.test_batch_na import envelope as ae
    p,s,r=ae()
    with pytest.raises(ValueError):nb.validate_envelope(p,s,r)


@pytest.mark.parametrize("kind",["graph","labels","folds","feature_npz","initial","receipt"])
def test_bound_bytes_tampering_rejected(tmp_path,kind):
    p=tmp_path/kind;p.write_bytes(b"immutable");reference=ref(p)
    nb.checked_tree({"r":reference})
    p.write_bytes(b"changed")
    with pytest.raises(ValueError):nb.checked_tree({"r":reference})


def test_runtime_changed_rejected(monkeypatch):
    p,_,_=envelope()
    monkeypatch.setattr(nb,"runtime",lambda:p["runtime"])
    assert nb.validate_execution_runtime(p)
    monkeypatch.setattr(nb,"runtime",lambda:{"other":"b"*64})
    with pytest.raises(ValueError):nb.validate_execution_runtime(p)


def test_unapproved_plan_cannot_start(tmp_path,monkeypatch):
    p,_,_=envelope();target=tmp_path/"plan.json";target.write_text(json.dumps(p))
    monkeypatch.setattr(nb,"load",lambda *a,**k:p)
    with pytest.raises(PermissionError):nb.require_launch_authorization(target)
    (tmp_path/"execution_decisions.json").write_text(json.dumps(dict(execution_authorized=False)))
    with pytest.raises(PermissionError):controller.seal(tmp_path)


def test_zero_layer_initial_uses_classifier_only(tmp_path,monkeypatch):
    reference,old=sealed(tmp_path,monkeypatch)
    spec=bind_spec("S4-noG",refs(),None)
    receiver=model("S0")
    receiver.gcs=nn.ModuleList()
    receiver.adapt_ws=nn.ModuleList([NodeSemAdapter(spec,str(i)) for i in range(2)])
    state,sha=initial_state(receiver,spec,"fixture_node",0,"G0",reference)
    assert not any(k.startswith("gcs.") for k in state)
    assert all(torch.equal(state[k],v) for k,v in old["state_dict"].items() if k.startswith("classify."))
    from scripts.DFG.dfg_v2.experiment.init import seeds
    sf=seeds("node",0,1);path=tmp_path/"nb.pt"
    payload=dict(kind="untrained_initial",optimizer_steps=0,task_id="fixture_node",
        fold=0,seed=1,profile="G0",constructor_seed=sf["constructor"],fit_seed=sf["fit"],
        state_dict=state,state_sha256=sha,feature_spec_sha256=spec.digest(),
        source=reference,formal_training=False)
    torch.save(payload,str(path))
    job=dict(task_id="fixture_node",fold=0,profile="G0",initial=dict(ref(path),state_sha256=sha),h8_initial=reference)
    assert nb.validate_initial(job,spec)["passed"]


@pytest.mark.parametrize("field",["config","split","graph","labels","folds","label_view","seeds","source_preparation","h8_initial","device_policy"])
def test_cross_batch_comparison_must_match_na_identity(tmp_path,field):
    from scripts.node_sem.nb_history import verify_parent_index
    from scripts.node_sem.tests.test_batch_na import envelope as make_na
    def save(name,value):
        p=tmp_path/name;p.write_text(json.dumps(value));return ref(p)
    plan,_,_=make_na()
    for j in plan["jobs"]:
        j.update({k:{"frozen":k} for k in ("config","split","graph","labels","folds","label_view","seeds","source_preparation","h8_initial")})
    pref=save("plan.json",plan)
    seal=dict(version=na.VERSION,plan=pref,jobs=240,matrix_sha256=digest(plan["jobs"]))
    sref=save("plan.seal.json",seal)
    rev=save("revision.json",dict(plan=pref,seal=sref))
    rows=[]
    for i,j in enumerate(plan["jobs"]):
        receipt=dict(job=j,plan=pref,execution_revision=rev,actual_device=j["device_policy"])
        rr=save("receipt%d.json"%i,receipt)
        rows.append(dict(job=j,receipt=rr,actual_device=j["device_policy"]))
    complete=save("complete.json",dict(passed=True,formal_fits=240,plan=pref,execution_revision=rev,receipts=[x["receipt"] for x in rows]))
    parent=dict(plan=pref,seal=sref,revision=rev,complete=complete)
    idx=save("index.json",dict(passed=True,formal_fits=240,parent=parent,records=rows,all_receipt_artifacts_checked=True))
    target=copy.deepcopy(plan["jobs"][0])
    assert verify_parent_index(parent,idx,[target])
    target[field]={"altered":True}
    with pytest.raises(ValueError,match="comparison input"):verify_parent_index(parent,idx,[target])
