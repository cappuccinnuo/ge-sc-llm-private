import numpy as np
import pytest
import torch
from scripts.node_sem.adapter import NodeSemAdapter
from scripts.node_sem.feature_spec import FeatureSpec
from scripts.node_sem.p6c_core import (removed_input, contribution_arrays, logistic_probe,
    split_indices, choose_threshold)
from scripts.node_sem.p6c_report import changes


def spec(fusion):
    return FeatureSpec("diagnostic","original",
        [dict(name=n,dim=2,manifest=None,normalize=False) for n in ("code","ctx","static")],
        "none",fusion,modality_dropout=.5)


@pytest.mark.parametrize("fusion",["concat","gated"])
def test_presence_removal_is_actual_training_dropout_behavior(fusion):
    torch.manual_seed(12)
    adapter=NodeSemAdapter(spec(fusion),"expression_statement",hidden_size=4)
    inp=torch.randn(20,9);inp[:,:3]=1
    adapter.reset_dropout(1,"task",0,"G3R")
    adapter.train()
    mask=adapter._drop_presence(inp[:,:3])
    assert (mask==0).any() and (mask==1).any()
    adapter.forward_count=0
    training=adapter(inp)
    changed=inp.clone();changed[:,:3]=mask
    adapter.eval()
    assert torch.equal(training,adapter(changed))
    assert adapter.forward_count==1


@pytest.mark.parametrize("fusion",["concat","gated"])
def test_removal_only_presence_no_mutation(fusion):
    s=spec(fusion);x=torch.randn(3,9);x[:,:3]=1;before=x.clone()
    y=removed_input(x,s,("ctx","static"))
    assert torch.equal(x,before)
    assert torch.equal(x[:,3:],y[:,3:])
    assert torch.equal(y[:,:3],torch.tensor([[1.,0,0]]*3))
    with pytest.raises(ValueError):removed_input(x,s,("invalid",))


def test_contribution_hand_calculation_and_zero_rows():
    p=torch.tensor([[[3.,4.],[0.,2.],[0.,0.]],[[0.,0.],[0.,0.],[0.,0.]]])
    g=torch.tensor([[.2,.3,.5],[0.,0.,0.]])
    a=torch.tensor([[1.,1.,1.],[0.,0.,0.]])
    eff,share,valid=contribution_arrays(p,g,a)
    assert torch.allclose(eff,torch.tensor([[1.,.6,0.],[0.,0.,0.]]))
    assert torch.allclose(share,torch.tensor([[.625,.375,0.],[0.,0.,0.]]))
    assert valid.tolist()==[True,False]
    assert share[0].argmax()!=g[0].argmax()
    with pytest.raises(ValueError):contribution_arrays(p,g,torch.zeros_like(a))


def example():
    rng=np.random.RandomState(19)
    x=rng.normal(size=(120,4));y=(x[:,0]+x[:,1]>.15).astype(int)
    ix=dict(inner_train=np.arange(80),inner_val=np.arange(80,100),outer_test=np.arange(100,120))
    return x,y,ix


def test_probe_outer_data_cannot_change_fit_selection_or_threshold():
    x,y,ix=example()
    a=logistic_probe(x,y,ix,True)
    x2=x.copy();x2[100:]*=100
    y2=y.copy();y2[100:]=1-y2[100:]
    b=logistic_probe(x2,y2,ix,True)
    assert a["selected_C"]==b["selected_C"]
    assert a["threshold"]==b["threshold"]
    assert a["inner_val_auc"]==b["inner_val_auc"]
    assert a["candidates"]==b["candidates"]
    assert not a["outer_used_in_selection"]


@pytest.mark.parametrize("role",["inner_train","inner_val"])
def test_single_class_does_not_borrow_other_fold(role):
    x,y,ix=example();y[ix[role]]=0
    r=logistic_probe(x,y,ix,True)
    assert r["status"]=="not_estimable_"+role+"_single_or_empty"
    assert "selected_C" not in r and "probabilities" not in r


def test_single_class_test_keeps_bf1_not_auc():
    x,y,ix=example();y[ix["outer_test"]]=0
    r=logistic_probe(x,y,ix)
    assert r["auc"] is None and r["balanced_accuracy"] is None
    assert r["buggy_f1"] is not None


def test_overlap_and_file_mismatch_rejected():
    x,y,ix=example();ix["inner_val"]=np.arange(79,100)
    with pytest.raises(ValueError):logistic_probe(x,y,ix)
    split=dict(inner_train_files=["a"],inner_val_files=["b"],outer_test_files=["c"])
    idx=split_indices(["a","b","c","a"],split)
    assert idx["inner_train"].tolist()==[0,3]
    with pytest.raises(ValueError):split_indices(["d"],split)
    split["inner_val_files"]=["a"]
    with pytest.raises(ValueError):split_indices(["a","c"],split)


def test_threshold_uses_validation_targets():
    y=np.array([0,0,1,1])
    assert choose_threshold(y,np.array([.1,.2,.3,.4]))==pytest.approx(.3)


def test_removal_changes_identity_and_probability():
    a=[dict(file="x",original_graph_node_id=2,target=1,source_sha256="s",cohort="nonSolidiFI",
            prediction=0,probability=.2)]
    b=[dict(a[0],prediction=1,probability=.8)]
    v=changes(a,b,"node")
    assert v["changed"]==1 and v["corrected"]==1 and v["nonSolidifi_positive_changed"]==1
    assert v["probability_MAE"]==pytest.approx(.6)
    with pytest.raises(ValueError):changes(a,[dict(b[0],source_sha256="different")],"node")

def test_cpu_fold_dispatch_preserves_exact_probe_numbers(tmp_path):
    from scripts.node_sem.p6c_parallel import compute_fold
    x,y,ix=example()
    rows=[dict(file=("train" if i<80 else "val" if i<100 else "test"),row_key=i) for i in range(120)]
    job=dict(task_id="test_node",fold=3,split=dict(inner_train_files=["train"],
        inner_val_files=["val"],outer_test_files=["test"]),folds=dict(path="sealed",sha256="s"))
    meta=dict(rows=rows,jobs=[job])
    parts=dict(code=x,ctx=x*.5,static=y[:,None].astype(float))
    presence={n:np.ones(120,dtype=bool) for n in parts}
    pop=dict(eligible=[dict(index=0,group="B")])
    got=compute_fold(meta,parts,presence,pop,3)
    for source,row in zip(("code","ctx"),got["results"]):
        wanted=logistic_probe(parts[source],y,ix)
        wanted.pop("probabilities");wanted.pop("predictions")
        assert {k:row[k] for k in wanted}==wanted
    for name,a in parts.items():
        np.save(str(tmp_path/(name+".npy")),a,allow_pickle=False)
    cached={n:np.load(str(tmp_path/(n+".npy")),allow_pickle=False,mmap_mode="r") for n in parts}
    assert compute_fold(meta,cached,presence,pop,3)==got


def test_report_sample_count_merge():
    from scripts.node_sem.p6c_report_v2 import merged_fold_row
    job=dict(task_id="task",fold=0,name="S4g")
    score=dict(n=2,buggy_f1=50.0);delta=dict(n=2,changed=1)
    result=merged_fold_row(job,"full",score,delta)
    assert result["n"]==2 and result["buggy_f1"]==50 and result["changed"]==1
    assert score==dict(n=2,buggy_f1=50.0) and delta==dict(n=2,changed=1)


def test_report_rejects_conflicting_count():
    from scripts.node_sem.p6c_report_v2 import merged_fold_row
    with pytest.raises(ValueError,match="sample counts"):
        merged_fold_row({},"full",dict(n=2),dict(n=3))


def test_report_rejects_unexpected_overlapping_key():
    from scripts.node_sem.p6c_report_v2 import merged_fold_row
    with pytest.raises(ValueError,match="overlapping"):
        merged_fold_row({},"full",dict(n=2,changed=1),dict(n=2,changed=1))
