"""Boundary tests for final N-C2 reporting and its conditional comparison family."""
import copy
import pytest
from scripts.node_sem.nc2_reporting import (
    receipt_matrix, result_matrix, changes, inference, retention)
from scripts.node_sem.tests.test_nc1_reporting import row


def jobs():
    return [dict(task_id="reentrancy_node", name=n, profile="G3R", fold=0, seed=1)
            for n in ("S5", "S8")]


@pytest.mark.parametrize("damage", ["missing", "duplicate", "unexpected", "changed_job", "duplicate_plan"])
def test_receipt_matrix_rejects_damage(damage):
    j=jobs(); r=[dict(job=copy.deepcopy(x)) for x in j]
    if damage=="missing":r.pop()
    if damage=="duplicate":r.append(copy.deepcopy(r[0]))
    if damage=="unexpected":r[0]["job"]["name"]="S6"
    if damage=="changed_job":r[0]["job"]["seed"]=2
    if damage=="duplicate_plan":j.append(copy.deepcopy(j[0]))
    with pytest.raises(ValueError):receipt_matrix(j,r)


def test_receipt_order_independent():
    j=jobs()
    assert len(receipt_matrix(j,[dict(job=x) for x in reversed(j)]))==2


def metrics(names=("S4","S5","S6","S8")):
    return [dict(task_id="reentrancy_node",task_kind="node",profile="G3R/"+n,
                 fold=f,seed=1,checkpoint=c,
                 metrics={m:50.+(1 if n=="S5" else 0) for m in
                          ("buggy_f1","macro_f1","precision","recall")})
            for n in names for f in range(10) for c in ("best","last")]


@pytest.mark.parametrize("damage", ["missing", "duplicate", "wrong_score_role", "wrong_task_kind"])
def test_complete_metric_matrix(damage):
    r=metrics();j=[dict(task_id="reentrancy_node",fold=f,seed=1) for f in range(10)]
    names=["S4","S5","S6","S8"]
    assert len(result_matrix(r,j,names))==80
    if damage=="missing":r.pop()
    if damage=="duplicate":r.append(copy.deepcopy(r[0]))
    if damage=="wrong_score_role":r[0]["checkpoint"]="inner_val"
    if damage=="wrong_task_kind":r[0]["task_kind"]="contract"
    with pytest.raises(ValueError):result_matrix(r,j,names)


def test_change_pairing_direction_and_names():
    a=[row(2,0,.3),row(1,1,.8)]
    b=[row(1,0,.2),row(2,1,.9)]
    r=changes(a,b,"node","best")
    assert r[0]["corrected"] and r[1]["new_error"]
    assert r[0]["probability_delta"]==pytest.approx(.6)
    assert not any("S6" in k or "S4" in k for x in r for k in x)


@pytest.mark.parametrize("field,value",[("fold",1),("source_sha256","b"*64),
    ("target",0),("source_id","other"),("cohort","SolidiFI")])
def test_change_identity_mismatch_rejected(field,value):
    a=row();a[field]=value
    with pytest.raises(ValueError):changes([a],[row()],"node","best")


@pytest.mark.parametrize("teacher",[-1.,0.,1.])
def test_retention_has_no_nonpositive_denominator(teacher):
    r=retention(.5,teacher)
    assert r["ratio"]==(.5 if teacher>0 else None)


@pytest.mark.parametrize("include", [False,True])
def test_inference_exact_family_and_endpoint(include):
    r=metrics()
    tests,h=inference(r,include)
    assert [t["name"] for t in tests]==(["S5-S4","S5-S8"] if include else ["S5-S4"])
    assert all(t["checkpoint"]=="best" and t["task_id"]=="reentrancy_node"
               and t["metric"]=="buggy_f1" for t in tests)
    altered=copy.deepcopy(r)
    for x in altered:
        if x["checkpoint"]=="last" or x["profile"]=="G3R/S6":
            x["metrics"]["buggy_f1"]=99.
    assert inference(altered,include)==(tests,h)
    assert h["family_size"]==(2 if include else 1)
