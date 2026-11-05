import copy
import inspect
import json
import signal
from pathlib import Path
import numpy as np
import pytest
from scripts.node_sem import batch_na as na, batch_na_worker as w, batch_na_controller as c
from scripts.node_sem.na_carrier import load_carrier
from scripts.node_sem.feature_spec import FeatureSpec
from scripts.node_sem import TOKEN_IDS
from scripts.node_sem.carrier import row_key, vector_sha
from scripts.node_sem.tests.carrier_fixtures import make_spelling_fixture, dump
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
from scripts.labeling_v2.safe_graph import write_graph


def bound(tmp_path):
    fixture=make_spelling_fixture(tmp_path,True);g=fixture["graph"]
    spec=FeatureSpec("S0o","original",[dict(name=TOKEN_IDS,dim=512,
        manifest=fixture["view_ref"],normalize=False)],"raw_linear","raw_linear")
    gp=tmp_path/"g.gpickle";write_graph(g,gp)
    data=tmp_path/"carrier.npz";matrix=np.stack([d["token"] for _,d in g.nodes(data=True)])
    np.savez_compressed(str(data),features=matrix)
    rows=[dict(original_graph_node_id=n,row_key=row_key(n,d),file=d["source_file"],
        node_type=d["node_type"],vector_sha256=vector_sha(d["token"])) for n,d in g.nodes(data=True)]
    record=dict(data=ref(data),task_id="fixture_node",view="original",spec=spec.to_json(),
        spec_sha256=spec.digest(),rows=rows,original_graph_fingerprint=graph_fingerprint(g),
        feature_shape=list(matrix.shape))
    job=dict(spec=dump(tmp_path/"spec.json",spec.to_json()),spec_sha256=spec.digest(),
        feature_view=dump(tmp_path/"manifest.json",record),feature_npz=ref(data),graph=ref(gp),
        task_id="fixture_node",original_graph_fingerprint=graph_fingerprint(g))
    return job,g,record


def test_direct_carrier_preserves_graph_and_exact_rows(tmp_path):
    job,g,r=bound(tmp_path);before=graph_fingerprint(g)
    result,record,spec=load_carrier(job)
    assert graph_fingerprint(g)==before and list(result)==list(g)
    assert all(np.array_equal(result.nodes[n]["token"],g.nodes[n]["token"]) for n in g)
    assert record=={k:v for k,v in r.items() if k!="data"}


@pytest.mark.parametrize("damage",["npz_sha","manifest_sha","graph_sha","spec_sha","row_order",
    "node_id","type","file","task","view","spec_digest","graph_fingerprint","nan","dimension","npz_binding"])
def test_bad_carrier_rejected(tmp_path,damage):
    job,g,r=bound(tmp_path)
    if damage.endswith("_sha"):
        field=dict(npz_sha="feature_npz",manifest_sha="feature_view",graph_sha="graph",spec_sha="spec")[damage]
        Path(job[field]["path"]).write_bytes(b"corrupt")
    elif damage in ("nan","dimension"):
        matrix=np.stack([d["token"] for _,d in g.nodes(data=True)])
        if damage=="nan":matrix[0,0]=np.nan
        else:matrix=matrix[:,:511]
        np.savez_compressed(job["feature_npz"]["path"],features=matrix)
        job["feature_npz"]=ref(job["feature_npz"]["path"]);r["data"]=job["feature_npz"]
    elif damage=="row_order":r["rows"].reverse()
    elif damage=="node_id":r["rows"][0]["original_graph_node_id"]="bogus"
    elif damage=="type":r["rows"][0]["node_type"]="bogus"
    elif damage=="file":r["rows"][0]["file"]="bogus.sol"
    elif damage=="task":r["task_id"]="wrong"
    elif damage=="view":r["view"]="anonymous"
    elif damage=="spec_digest":r["spec_sha256"]="f"*64
    elif damage=="graph_fingerprint":r["original_graph_fingerprint"]="f"*64
    else:r["data"]=dict(job["feature_npz"],sha256="f"*64)
    if not damage.endswith("_sha"):job["feature_view"]=dump(Path(job["feature_view"]["path"]),r)
    with pytest.raises((ValueError,RuntimeError)):load_carrier(job)


def test_formal_config_has_no_smoke_override_and_refuses_drift():
    job=dict(na.matrix()[0],config=dict(maximum_training_epochs=50,patience=7,initial_lr=.0002))
    plan=dict(jobs=[job])
    assert w.formal_config(plan,job)==job["config"]
    changed=copy.deepcopy(job);changed["config"]["maximum_training_epochs"]=1
    with pytest.raises(ValueError):w.formal_config(plan,changed)
    assert "maximum_training_epochs" not in inspect.getsource(w.run_formal)
    assert "register_hook" not in inspect.getsource(w.run_core)
    assert w.fit.__module__=="scripts.DFG.dfg_v2.benchmark_v2.trainer"


def test_order_two_pilots_then_all_primary_without_drops():
    jobs=na.matrix();order=c.ordered(jobs)
    assert len(order)==len(set(order))==240
    assert order[:2]==["reentrancy_node__G3R__S4__fold_0","reentrancy_contract__G3R__S4__fold_0"]
    assert all(x.startswith("reentrancy_node__G3R__") for x in order[2:41])
    assert set(order[:1]+order[2:41])=={w.job_id(j) for j in jobs if j["task_id"]=="reentrancy_node" and j["profile"]=="G3R"}


@pytest.mark.parametrize("code,failure,authorized,expected",[
    (-signal.SIGTERM,False,True,True),(-signal.SIGHUP,False,True,True),
    (-signal.SIGKILL,False,True,False),(1,False,True,False),
    (-signal.SIGTERM,True,True,False),(-signal.SIGTERM,False,False,False)])
def test_only_confirmed_external_termination_may_retry(tmp_path,code,failure,authorized,expected):
    j=dict(na.matrix()[0],initial=dict(path="sealed",sha256="a"*64))
    d=tmp_path/"runs"/w.job_id(j)/"attempt_001";d.mkdir(parents=True)
    if failure:(d/"failure.json").write_text("{}")
    assert c.retry_external(tmp_path,j,code,dict(external_interrupt_retry_once=authorized)) is expected
    assert json.loads((d/"external_interruption.json").read_text())["retry_authorized"] is expected


def test_external_retry_is_not_unbounded(tmp_path):
    j=dict(na.matrix()[0],initial={})
    for n in (1,2):(tmp_path/"runs"/w.job_id(j)/("attempt_%03d"%n)).mkdir(parents=True)
    assert not c.retry_external(tmp_path,j,-signal.SIGTERM,dict(external_interrupt_retry_once=True))


def test_atomic_status_keeps_last_complete_record(tmp_path):
    p=tmp_path/"status.json";c.atomic(p,dict(completed=1));c.atomic(p,dict(completed=2))
    assert json.loads(p.read_text())==dict(completed=2)
    assert not list(tmp_path.glob("*.tmp.*"))


def test_no_early_eta_and_no_metric_summary(tmp_path):
    c.progress(tmp_path,[],[])
    assert json.loads((tmp_path/"progress.json").read_text())["estimate"] is None
    assert not json.loads((tmp_path/"progress.json").read_text())["metrics_summarized"]
