import copy
import hashlib
import numpy as np
import pytest
from scripts.node_sem.teacher_diagnostics import ridge_probe,cosine,align_teacher
from scripts.node_sem.teacher_vectors import scatter
from scripts.node_sem.feature_spec import FeatureSpec
from scripts.node_sem import TEACHER


def data():
    rng=np.random.RandomState(1)
    x=rng.randn(30,4);y=x.dot(rng.randn(4,8));y/=np.linalg.norm(y,axis=1)[:,None]
    ix=dict(inner_train=np.arange(18),inner_val=np.arange(18,24),outer_test=np.arange(24,30))
    return x,y,["type"]*30,ix


def test_ridge_outer_targets_do_not_select_or_fit():
    x,y,k,ix=data()
    a=ridge_probe(x,y,k,ix)
    yy=y.copy();yy[ix["outer_test"]]*=-1
    b=ridge_probe(x,yy,k,ix)
    assert a["selected_alpha"]==b["selected_alpha"] and a["candidates"]==b["candidates"]
    assert a["outer_mean_cosine"]==pytest.approx(-b["outer_mean_cosine"])
    assert a["baseline_mean_cosine"]==pytest.approx(-b["baseline_mean_cosine"])


def test_ridge_outer_inputs_do_not_fit_scaler():
    x,y,k,ix=data();a=ridge_probe(x,y,k,ix)
    xx=x.copy();xx[ix["outer_test"]]*=1000
    b=ridge_probe(xx,y,k,ix)
    assert a["candidates"]==b["candidates"]


def test_unseen_type_baseline_is_not_fitted_on_test():
    x,y,k,ix=data()
    for i in ix["outer_test"]:k[i]="unseen"
    r=ridge_probe(x,y,k,ix)
    assert r["baseline_n"]==0 and r["baseline_mean_cosine"] is None
    assert r["baseline_unseen_rows"]==6


def test_empty_or_leaking_split():
    x,y,k,ix=data()
    ix["inner_val"]=np.asarray([],dtype=int)
    assert ridge_probe(x,y,k,ix)["status"]=="not_estimable_inner_val_empty"
    ix["inner_val"]=np.array([0])
    with pytest.raises(ValueError,match="leakage"):ridge_probe(x,y,k,ix)


def teacher_rows():
    result=[]
    for i,p in enumerate((True,False,True)):
        text="text" if p else ""
        result.append(dict(row_key=i,file="x.sol",node_type="statement",source_sha256="a"*64,
            code_sha256="b"*64,present=p,unverified=p,text=text,
            text_sha256=hashlib.sha256(text.encode()).hexdigest()))
    return result


def test_vectors_presence_zero_and_spec():
    rows=teacher_rows();v=np.zeros((1,384),np.float32);v[0,0]=1
    matrix,identities=scatter(rows,["text"],v)
    assert not matrix[1].any() and np.array_equal(matrix[0],matrix[2])
    assert identities[1]["present"] is False
    spec=FeatureSpec("teacher_check","original",[dict(name=TEACHER,dim=384,manifest=None,normalize=True)],"none","concat")
    assert spec.carrier_dim()==385 and spec.layout()[TEACHER]["presence"]==0
    aligned,p=align_teacher(rows,dict(rows=identities[::-1]),matrix[::-1])
    assert np.array_equal(aligned,matrix) and p.tolist()==[True,False,True]


@pytest.mark.parametrize("change",["duplicate","sha","presence"])
def test_scatter_rejects_bad_identity(change):
    rows=teacher_rows();v=np.zeros((1,384),np.float32);v[0,0]=1
    if change=="duplicate":rows[1]["row_key"]=0
    if change=="sha":rows[0]["text_sha256"]="f"*64
    if change=="presence":rows[0]["present"]=False
    with pytest.raises(ValueError):scatter(rows,["text"],v)


def test_teacher_manifest_loads_in_existing_carrier(tmp_path):
    from scripts.node_sem.tests.carrier_fixtures import make_spelling_fixture,dump
    from scripts.node_sem.tests.test_carrier import _generic
    from scripts.node_sem.carrier import _load
    from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
    fixture=make_spelling_fixture(tmp_path)
    spec,view,path,npz,matrix=_generic(fixture,tmp_path)
    view["modality"]=TEACHER
    matrix=np.pad(matrix,((0,0),(0,381))).astype(np.float32)
    np.savez_compressed(str(npz),features=matrix)
    view["data"]=ref(npz);view["feature_shape"]=list(matrix.shape)
    for row,v in zip(view["rows"],matrix):row["vector_sha256"]=hashlib.sha256(v.tobytes()).hexdigest()
    bound=dump(path,view);loaded,values=_load(bound)
    assert values.shape[1]==384 and loaded["modality"]==TEACHER
