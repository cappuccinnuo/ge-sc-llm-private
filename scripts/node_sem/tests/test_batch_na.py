"""N-A plan integrity, independent zero-step initialization, and device contracts."""
import copy
from pathlib import Path
import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from scripts.node_sem import batch_na as na
from scripts.node_sem.p5_prepare import bind_spec
from scripts.node_sem.init import initial_state
from scripts.node_sem.tests.test_init import sealed, model, specification
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
from scripts.DFG.experiments.common import digest, tensor_digest


def policy():
    return dict(location="local_RTX3050", device_type="cuda", gpu_model="RTX3050",
                torch_version="1.8.1+cu111", cuda_build_version="11.1",
                allow_tf32=dict(matmul=True, cudnn=True))


def jobs():
    return [dict(j, reuse_8h=False, view="original", device_policy=policy()) for j in na.matrix()]


def envelope():
    plan = dict(version=na.VERSION, protocol=na.PROTOCOL_NAME, protocol_version=na.PROTOCOL_VERSION,
        view="original", label_policy="L-audit", execution_authorized=False, source_preparation={"source": "frozen"},
        statistics=na.statistics_spec(), jobs=jobs(), device_families={t:policy() for t,_ in na.TASK_FOLDS}, runtime={"runtime.py":"f"*64})
    reference = dict(path="/plan.json", sha256="a"*64)
    seal = dict(version=na.VERSION, plan=reference, jobs=240, matrix_sha256=digest(plan["jobs"]))
    return plan, seal, reference


def test_exact_240_original_jobs_and_counts():
    j = jobs(); assert na.validate_matrix(j)
    assert {name:sum(x["name"] == name for x in j) for name in na.NAMES} == dict(S0o=60,S1o=60,S2=60,S4=60)
    assert sum(x["granularity"] == "contract" for x in j) == 80
    assert sum(x["granularity"] == "node" for x in j) == 160
    assert all(x["seed"] == 1 and not x["reuse_8h"] for x in j)


@pytest.mark.parametrize("damage", ["missing", "duplicate", "fold", "seed", "profile", "name", "view", "reuse", "granularity"])
def test_matrix_drift_rejected(damage):
    j = jobs()
    if damage == "missing": j.pop()
    elif damage == "duplicate": j[1] = copy.deepcopy(j[0])
    elif damage == "reuse": j[0]["reuse_8h"] = True
    else: j[0][damage] = dict(fold=100,seed=2,profile="G3",name="S4m",view="anonymous",granularity="node")[damage]
    with pytest.raises(ValueError): na.validate_matrix(j)


@pytest.mark.parametrize("damage", ["sha", "matrix_sha", "version", "count", "endpoint", "view", "authorization", "protocol", "labels"])
def test_plan_and_seal_tampering_rejected(damage):
    p, s, r = envelope(); assert na.validate_envelope(p,s,r)
    if damage == "sha": s["plan"] = dict(r,sha256="b"*64)
    elif damage == "matrix_sha": s["matrix_sha256"]="c"*64
    elif damage == "version": p["version"]="old"
    elif damage == "count": s["jobs"]=239
    elif damage == "endpoint": p["statistics"]["primary"]["metric"]="macro_f1"
    elif damage == "view": p["view"]="anonymous"
    elif damage == "authorization": p["execution_authorized"]=True
    elif damage == "protocol": p["protocol"]="paper_kfold"
    else: p["label_policy"]="orig"
    with pytest.raises(ValueError): na.validate_envelope(p,s,r)


@pytest.mark.parametrize("field,value", [("location","server"),("device_type","cpu"),("gpu_model","A100"),
    ("torch_version","2.0"),("cuda_build_version","12.0"),("matmul",False),("cudnn",False)])
def test_mixed_device_or_precision_comparisons_rejected(field,value):
    j=jobs(); assert na.validate_device_comparisons(j)
    if field in ("matmul","cudnn"):j[-1]["device_policy"]["allow_tf32"][field]=value
    else:j[-1]["device_policy"][field]=value
    with pytest.raises(ValueError):na.validate_device_comparisons(j)


def test_receipts_require_full_identity_and_actual_device():
    j=jobs();r=[dict(x,actual_device=copy.deepcopy(x["device_policy"])) for x in j]
    assert na.validate_device_comparisons(j,r)
    r[0]["actual_device"]["allow_tf32"]["matmul"]=False
    with pytest.raises(ValueError):na.validate_device_comparisons(j,r)
    with pytest.raises(ValueError):na.validate_device_comparisons(j,r[:-1])
    r[1]=copy.deepcopy(r[0])
    with pytest.raises(ValueError):na.validate_device_comparisons(j,r)


def test_changed_runtime_rejected_before_launch(monkeypatch):
    p,_,_=envelope();monkeypatch.setattr(na,"runtime",lambda:copy.deepcopy(p["runtime"]))
    assert na.validate_execution_runtime(p)
    monkeypatch.setattr(na,"runtime",lambda:{"runtime.py":"0"*64})
    with pytest.raises(ValueError,match="runtime"):na.validate_execution_runtime(p)


@pytest.mark.parametrize("kind", ["carrier.npz","initial.pt","labels.json","graph.gpickle","spec.json"])
def test_changed_bound_input_bytes_rejected(tmp_path,kind):
    p=tmp_path/kind;p.write_bytes(b"sealed input");r=ref(p)
    assert na.checked_tree(dict(nested=[dict(value=r)]))
    p.write_bytes(b"modified input")
    with pytest.raises((ValueError,RuntimeError)):na.checked_tree(dict(nested=[dict(value=r)]))


def test_no_launch_from_template_or_without_worker(tmp_path,monkeypatch):
    p,_,_=envelope();plan_path=tmp_path/"plan.json";plan_path.write_text(json.dumps(p))
    p["device_families"]={t:policy() for t,_ in na.TASK_FOLDS}
    monkeypatch.setattr(na,"load",lambda *a,**kw:p)
    with pytest.raises(PermissionError,match="not authorized"):na.require_launch_authorization(plan_path)
    a=tmp_path/"authorization.json";a.write_text(json.dumps(dict(execution_authorized=False)))
    with pytest.raises(PermissionError):na.require_launch_authorization(plan_path,ref(a))
    a.write_text(json.dumps(dict(execution_authorized=True,user_request="explicit",plan=ref(plan_path),
        matrix_sha256=digest(p["jobs"]),device_families=p["device_families"])))
    with pytest.raises(PermissionError,match="no training worker"):na.require_launch_authorization(plan_path,ref(a))


def test_selection_and_stratification_do_not_select_on_outer_test():
    s=na.statistics_spec()
    assert s["primary"]["comparison"]==["S4","S0o"]
    assert s["primary"]["score_role"]=="outer_test"
    assert s["s_star"]["role"]=="inner_val" and not s["s_star"]["outer_test_used"]
    assert "minimum inner_val loss" in s["s_star"]["checkpoint"]
    assert len(s["holm_family"])==4
    assert not s["strata"]["membership_uses_labels"]
    assert s["strata"]["bf1_interval"] is None and len(s["strata"]["wilson95"])==2


@pytest.mark.parametrize("name", ["S0","S1"])
def test_previously_loaded_untrained_structure_reinitialized_exactly(tmp_path,monkeypatch,name):
    reference,_=sealed(tmp_path,monkeypatch)
    receiving=model(name);spec=specification(name)
    a,asha=initial_state(receiving,spec,"fixture_node",0,"G0",reference)
    receiving.load_state_dict(a)
    # Change all existing parameter values to prove the computation overwrites,
    # rather than relying on the previously loaded constructor state.
    with torch.no_grad():
        for p in receiving.parameters():p.add_(7)
    b,bsha=initial_state(receiving,spec,"fixture_node",0,"G0",reference)
    fresh=model(name);c,csha=initial_state(fresh,spec,"fixture_node",0,"G0",reference)
    assert asha==bsha==csha and all(torch.equal(a[k],b[k]) and torch.equal(b[k],c[k]) for k in a)
    assert all(p.grad is None for p in receiving.parameters())


def test_static_original_features_not_masked_or_anonymous():
    r=lambda n:dict(path="/"+n,sha256="a"*64)
    refs=dict(code=r("code"),ctx=dict(original=r("ctx"),masked=r("masked")),static=r("static"))
    for name in na.NAMES:
        spec=bind_spec(name,refs,r("tokens"));assert spec.view=="original"
        if name=="S4":
            assert next(m for m in spec.modalities if m["name"]=="ctx")["manifest"]==r("ctx")
            assert spec.carrier_dim()==760
        if name=="S0o":assert spec.token_mode=="raw_linear"


@pytest.mark.parametrize("field", ["seed", "fold"])
def test_boolean_job_identity_rejected(field):
    j=jobs();j[0][field]=True if field=="seed" else False
    with pytest.raises(ValueError):na.validate_matrix(j)


def test_seal_version_and_device_family_mismatch():
    p,s,r=envelope();s["version"]="wrong"
    with pytest.raises(ValueError):na.validate_envelope(p,s,r)
    p,s,r=envelope();p["device_families"]["reentrancy_node"]["location"]="server"
    with pytest.raises(ValueError):na.validate_envelope(p,s,r)
