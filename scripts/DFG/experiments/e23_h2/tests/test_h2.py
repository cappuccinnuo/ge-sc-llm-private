"""Necessary H2 scheduling, saved-state and identity regression tests."""
import copy, json
from pathlib import Path
import pytest, torch
from contextlib import contextmanager
from types import SimpleNamespace
from scripts.DFG.experiments.e23_h2 import control, worker, archive, report, H1
from scripts.DFG.experiments.e23_pilot import control as gc, training as gt
from scripts.DFG.experiments.e23_cv import control as hc, worker as hw
from scripts.DFG.experiments.common import read_json,write_json,sha256,tensor_digest
from scripts.DFG.experiments.e23_pilot.inputs import TASK_ORDER

def matrix():
    return {"jobs":[{"task_id":t,"fold":f,"variant":"E3a",
        "source":"stage_g_reuse" if f==0 else "stage_h_fresh"}
        for t,f,v in hc.expected_jobs(("E3a",))]}

def test_exact_h2_matrix_and_no_h1_whitelist_change():
    p=matrix();control.validate_jobs(p)
    assert len(p["jobs"])==30 and sum(j["fold"]>0 for j in p["jobs"])==26
    for changed in [p["jobs"][:-1],p["jobs"]+[p["jobs"][0]],list(reversed(p["jobs"]))]:
        with pytest.raises(ValueError):control.validate_jobs({"jobs":changed})
    p["jobs"][0]["variant"]="E2"
    with pytest.raises(ValueError):control.validate_jobs(p)
    with pytest.raises(ValueError):hw.run("/missing","x","E3a","full","/missing/run",1)

@pytest.mark.parametrize("variant,mode,fold",[("E2","full",1),("E3b","full",1),("E3a","smoke",1),("E3a","full",0)])
def test_worker_rejects_unapproved_fits_before_io(variant,mode,fold):
    with pytest.raises(ValueError):worker.run("/missing","x",variant,mode,"/missing/run",fold)

def test_exact_numerical_functions_reused():
    assert worker.fit is gt.fit
    assert worker.make_model is hw.make_model
    assert worker.Supervision is hw.Supervision
    assert control.verify_fit is gc.verify_fit
    assert control.existing_success.__code__ is gc.existing_success.__code__

@pytest.mark.parametrize("task",TASK_ORDER)
@pytest.mark.parametrize("fold",[0,1])
def test_actual_reserved_initial_and_fold0_no_mutation(task,fold):
    jobs=read_json(H1/"h2_plan.json")["jobs"]
    j=next(j for j in jobs if j["task_id"]==task and j["fold"]==fold)
    info=read_json(j["task_manifest"]);p=info["initialization"]["E3a"]["path"];before=sha256(p)
    record=archive.load_initial(info)
    assert record["optimizer_steps"]==0 and record["kind"]=="untrained_initial"
    assert tensor_digest(record["state_dict"])==info["initialization"]["E3a"]["state_sha256"]
    assert before==sha256(p)
    assert read_json(H1/"h2_plan.json")["execution_authorized"] is False

@pytest.mark.parametrize("mutation",["bytes","tensor","graph","audit","trained","task","fold","fit_seed"])
def test_reserved_initial_tamper_rejected(tmp_path,mutation):
    job=next(j for j in read_json(H1/"h2_plan.json")["jobs"] if j["fold"]==1)
    info=read_json(job["task_manifest"]);record=archive.load_initial(info)
    info=copy.deepcopy(info);spec=info["initialization"]["E3a"]
    path=tmp_path/"initial.pt";spec["path"]=str(path)
    if mutation=="tensor":
        key=next(iter(record["state_dict"]));record["state_dict"][key]=record["state_dict"][key]+1
    elif mutation=="graph":record["graph_sha256"]="wrong"
    elif mutation=="audit":record["initialization_audit_sha256"]="wrong"
    elif mutation=="trained":record["optimizer_steps"]=1
    elif mutation=="task":record["task_id"]="wrong"
    elif mutation=="fold":record["fold"]=2
    elif mutation=="fit_seed":info["fit_seed"]+=1
    torch.save(record,str(path));spec["sha256"]=sha256(path)
    if mutation=="bytes":spec["sha256"]="wrong"
    with pytest.raises(ValueError):archive.load_initial(info)

@pytest.mark.parametrize("name",["graph.gpickle","labels.json","features.json","schema.json","initial.pt"])
def test_frozen_file_drift_rejected(name,tmp_path):
    p=tmp_path/name;p.write_text("frozen");f={str(p):sha256(p)}
    archive.check_hashes(f);p.write_text("changed")
    with pytest.raises(ValueError):archive.check_hashes(f)

def test_no_existing_plan_overwrite(tmp_path):
    write_json(tmp_path/"plan.json",{"untouched":True});before=(tmp_path/"plan.json").read_bytes()
    with pytest.raises(FileExistsError):control.seal(tmp_path)
    assert (tmp_path/"plan.json").read_bytes()==before

def pred(name,node,target):
    return {"file":name,"original_graph_node_id":node,"target":target,"score_role":"cv_validation"}
def test_alignment_is_identity_keyed_not_csv_order():
    rows=[pred("a",1,0),pred("b",2,1)]
    expected=[{"file":"a","original_graph_node_id":1,"target":0},{"file":"b","original_graph_node_id":2,"target":1}]
    assert report.align(list(reversed(rows)),expected)==rows
    for altered in [rows[:1],rows+[rows[0]], [dict(rows[0],target=1),rows[1]],
                    [dict(rows[0],score_role="independent_test"),rows[1]]]:
        with pytest.raises(ValueError):report.align(altered,expected)

def test_three_variant_population_and_output_immutable(tmp_path):
    fits=[{"job":{"task_id":t,"fold":f,"variant":v}} for t,f,v in hc.expected_jobs(("E2","E3a","E3b"))]
    report.validate_matrix(fits)
    for bad in [fits[:-1],fits+[fits[0]],fits[:-1]+[fits[0]]]:
        with pytest.raises(ValueError):report.validate_matrix(bad)
    report.store_outputs(tmp_path,{"a.csv":"a"})
    report.store_outputs(tmp_path,{"a.csv":"a"})
    with pytest.raises(FileExistsError):report.store_outputs(tmp_path,{"a.csv":"b"})
    assert (tmp_path/"a.csv").read_text()=="a"

def test_failure_retained_explicit_retry_success_reused(tmp_path,monkeypatch):
    job={"task_id":TASK_ORDER[0],"fold":1,"variant":"E3a","source":"stage_h_fresh"};plan={"jobs":[job]}
    monkeypatch.setattr(control,"TASK_ORDER",(TASK_ORDER[0],))
    monkeypatch.setattr(control,"verify_plan",lambda _:plan)
    @contextmanager
    def lock(_): yield
    monkeypatch.setattr(gc,"execution_lock",lock)
    def locate(output,job,plan):
        attempts=gc.attempt_inventory(control.job_dir(output,job))
        complete=[a for a in attempts if (a/"receipt.json").exists()]
        return (complete[0] if complete else None),attempts
    monkeypatch.setattr(control,"locate",locate)
    monkeypatch.setattr(control,"verify_fit",lambda *a:{"cv_validation":{"best":{}}})
    calls=[]
    def fake(cmd,**kw):
        path=Path(cmd[cmd.index("--attempt")+1]);calls.append(path)
        assert cmd[cmd.index("--variant")+1]=="E3a"
        if len(calls)==1:return SimpleNamespace(returncode=1)
        path.mkdir();(path/"receipt.json").write_text("{}")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(control.subprocess,"run",fake)
    with pytest.raises(RuntimeError,match="STOP"):control.execute(tmp_path)
    evidence=calls[0].with_suffix(".execution.json").read_bytes()
    with pytest.raises(RuntimeError,match="explicit retry"):control.execute(tmp_path)
    assert len(calls)==1
    control.execute(tmp_path,retry=control.identity(job))
    assert calls[0].with_suffix(".execution.json").read_bytes()==evidence
    assert [p.name for p in calls]==["attempt_001","attempt_002"]
    control.execute(tmp_path);assert len(calls)==2
    with pytest.raises(ValueError):control.execute(tmp_path,retry=TASK_ORDER[0]+"/fold_1/E2")
