import ast
from pathlib import Path
import numpy as np
import pytest
import torch
from scripts.node_sem import student

def sample(fold=0):
    rng=np.random.RandomState(91)
    files=np.repeat(["a","b","c"],4)
    split=dict(inner_train_files=[["a","b"][fold]],inner_val_files=[["b","a"][fold]],outer_test_files=["c"])
    ctx=rng.randn(12,4).astype("float32");static=rng.randn(12,3).astype("float32")
    teacher=rng.randn(12,384).astype("float32")
    teacher/=np.linalg.norm(teacher,axis=1,keepdims=True)
    present=np.ones(12,dtype=bool);present[[2,7,11]]=False;teacher[~present]=0
    return ctx,static,teacher,present,files,split

@pytest.mark.parametrize("fold",[0,1])
def test_fit_exports_all_deterministic_and_train_only_scaler(fold):
    a=sample(fold);torch.set_num_threads(2)
    seed=student.student_seed(1010000,"toy",fold)
    before=torch.get_rng_state().clone()
    first=student.fit_student(*a,seed=seed,max_epochs=2)
    second=student.fit_student(*a,seed=seed,max_epochs=2)
    assert torch.equal(before,torch.get_rng_state())
    assert np.array_equal(first["values"],second["values"])
    assert all(np.array_equal(first["state"][k],second["state"][k]) for k in first["state"])
    assert first["values"].shape==(12,384)
    assert first["diagnostics"]["teacher_missing_exported"]==3
    tr=first["indices"]["inner_train"]
    assert np.array_equal(first["mean"],a[0][tr].astype("float64").mean(0))

def test_outer_teacher_never_changes_selection_or_model():
    a=list(sample());first=student.fit_student(*a,seed=8,max_epochs=2)
    a[2]=a[2].copy();a[2][8:]*=-1
    second=student.fit_student(*a,seed=8,max_epochs=2)
    assert np.array_equal(first["values"],second["values"])
    assert first["diagnostics"]["history"]==second["diagnostics"]["history"]
    assert first["diagnostics"]["outer_test_mean_cosine"]==-second["diagnostics"]["outer_test_mean_cosine"]

def test_outer_feature_does_not_change_fit_or_standardizer():
    a=list(sample());first=student.fit_student(*a,seed=8,max_epochs=2)
    a[0]=a[0].copy();a[0][8:]+=100
    second=student.fit_student(*a,seed=8,max_epochs=2)
    assert np.array_equal(first["mean"],second["mean"])
    assert all(np.array_equal(first["state"][k],second["state"][k]) for k in first["state"])

def test_outer_injection_rejected():
    a=sample();ix=student.split_indices(a[4],a[5],a[3])
    ix["inner_train"]=np.append(ix["inner_train"],8)
    with pytest.raises(ValueError,match="leakage"):
        student.fit_student(*a,seed=8,indices=ix,max_epochs=1)

def test_file_overlap_and_empty_validation_rejected():
    a=list(sample());a[5]["inner_val_files"]=["a"]
    with pytest.raises(ValueError,match="leakage"):student.fit_student(*a,seed=8,max_epochs=1)
    a=list(sample());a[3][4:8]=False
    with pytest.raises(ValueError,match="Empty"):student.fit_student(*a,seed=8,max_epochs=1)

def test_labels_cannot_enter_api_or_imports():
    a=sample()
    with pytest.raises(TypeError):student.fit_student(*a,seed=8,labels=np.ones(12))
    tree=ast.parse(Path(student.__file__).read_text())
    allowed={"copy","math","numpy","torch","torch.nn","scripts.DFG.dfg_v2.experiment.init"}
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):assert all(n.name in allowed for n in node.names)
        if isinstance(node,ast.ImportFrom):assert node.module in allowed
    assert not any(isinstance(n,ast.Name) and n.id in {"open","read","read_labels","load","label","labels","predictions"} for n in ast.walk(tree))

def test_type_local_task_fold_permutation():
    x=np.arange(300,dtype="float32").reshape(30,10);types=["expr"]*10+["env_source"]*10+["function"]*10
    v,m=student.permute(x,types,"task",0,1)
    v2,m2=student.permute(x,types,"task",0,1)
    assert np.array_equal(v,v2) and np.array_equal(m,m2)
    assert np.array_equal(v,x[m])
    assert all(types[i]==types[j] for i,j in enumerate(m))
    assert not np.array_equal(m,student.permute(x,types,"other",0,1)[1])
    assert not np.array_equal(m,student.permute(x,types,"task",1,1)[1])

@pytest.mark.parametrize("delta,expected",[(0,False),(-1,False),(1e-12,True),(2,True)])
def test_s8_gate(delta,expected):assert student.s8_gate(delta) is expected

@pytest.mark.parametrize("delta",[float("nan"),float("inf"),None,True,"1"])
def test_s8_rejects_nonfinite(delta):
    with pytest.raises(ValueError):student.s8_gate(delta)
