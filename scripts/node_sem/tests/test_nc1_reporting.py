"""N-C1 report correctness at the boundaries that can silently bias comparisons."""
import copy
import pytest
from scripts.node_sem.nc1_reporting import (changes,change_summary,oof,check_scores,
    continuation_from_tables,result_matrix)
from scripts.DFG.dfg_v2.benchmark_v2.reporting import scored

def row(node=1,pred=0,prob=.2):
    return dict(file="same.sol",original_graph_node_id=node,target=1,fold=0,
        source_sha256="a"*64,source_id="source",cohort="nonSolidiFI",
        best=pred,last=pred,best_positive_probability=prob,last_positive_probability=prob)

def test_pair_by_identity_not_position():
    right=[row(1),row(2)]
    left=[row(2,1,.8),row(1,0,.3)]
    out=changes(left,right,"node","best")
    assert [r["original_graph_node_id"] for r in out]==[1,2]
    counts=change_summary(out)
    assert counts["corrected"]==1 and counts["class_changed"]==1
    assert counts["probability_only"]==1 and counts["new_error"]==0

@pytest.mark.parametrize("field,value",[("source_sha256","b"*64),("target",0),
    ("source_id","other"),("cohort","SolidiFI"),("fold",1)])
def test_changed_identity_rejected(field,value):
    a=row();b=row();a[field]=value
    with pytest.raises(ValueError):changes([a],[b],"node","best")

@pytest.mark.parametrize("which",["missing","duplicate","oof_repeat"])
def test_missing_duplicates_rejected(which):
    if which=="oof_repeat":
        with pytest.raises(ValueError):oof([row(),row()],"node")
    else:
        with pytest.raises(ValueError):changes([row()],[] if which=="missing" else [row(),row()],"node","best")

@pytest.mark.parametrize("p",[float("nan"),float("inf"),-0.1,1.1])
def test_nonfinite_probability_rejected(p):
    with pytest.raises(ValueError):changes([row(prob=p)],[row()],"node","best")

def test_score_recomputed():
    rows=[row(1,1,.8),row(2,0,.2)]
    result={"outer_test":{ck:scored(rows,ck) for ck in ("best","last")}}
    check_scores(rows,result)
    result["outer_test"]["best"]["buggy_f1"]+=1
    with pytest.raises(ValueError):check_scores(rows,result)

def inputs(delta=0,left=20,right=20):
    pair=[dict(task_id="reentrancy_node",checkpoint="best",metric="buggy_f1",mean_delta_pp=delta)]
    pool=[dict(task_id="reentrancy_node",checkpoint="best",cohort="nonSolidiFI",name=n,buggy_f1=v)
          for n,v in (("S6",left),("S4",right))]
    return pair,pool

@pytest.mark.parametrize("delta,left,right,expected",[(0,20,20,False),(-1,21,20,True),(1,19,20,True),(-1,19,20,False)])
def test_exact_registered_continuation(delta,left,right,expected):
    pair,pool=inputs(delta,left,right)
    pair.append(dict(task_id="access_control_node",checkpoint="best",metric="buggy_f1",mean_delta_pp=100))
    pair.append(dict(task_id="reentrancy_node",checkpoint="last",metric="buggy_f1",mean_delta_pp=100))
    decision=continuation_from_tables(pair,pool)
    assert decision["continue_student"] is expected
    assert decision["automatic_execution"] is False

@pytest.mark.parametrize("mode",["missing","duplicate_pair","duplicate_pool","none_score"])
def test_continuation_rejects_incomplete(mode):
    p,q=inputs()
    if mode=="missing":q.pop()
    if mode=="duplicate_pair":p.append(copy.deepcopy(p[0]))
    if mode=="duplicate_pool":q.append(copy.deepcopy(q[0]))
    if mode=="none_score":q[0]["buggy_f1"]=None
    with pytest.raises(ValueError):continuation_from_tables(p,q)

def test_matrix_requires_both_checkpoints_and_models():
    jobs=[dict(task_id="t",fold=0,seed=1)]
    rows=[dict(task_id="t",task_kind="node",profile="G3R/"+name,fold=0,seed=1,
               checkpoint=ck,metrics={m:50. for m in ("buggy_f1","macro_f1","precision","recall")})
          for name in ("S4","S6") for ck in ("best","last")]
    assert len(result_matrix(rows,jobs))==4
    with pytest.raises(ValueError):result_matrix(rows[:-1],jobs)
    with pytest.raises(ValueError):result_matrix(rows+[rows[0]],jobs)

def test_empty_change_summary_does_not_invent_scores():
    assert change_summary([])["mean_abs_probability_delta"] is None
