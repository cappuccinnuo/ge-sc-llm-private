"""H1 orchestration/analysis regressions: no CUDA, no training budget changes."""
import copy
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
import pytest
from scripts.DFG.experiments.e23_cv import control,prepare,report,worker
from scripts.DFG.experiments.e23_pilot import control as gc, training as gt
from scripts.DFG.experiments.common import read_json,sha256
from scripts.DFG.experiments.e23_pilot.inputs import TASK_ORDER,DEFAULT_OUTPUT as STAGE_G

def matrix():
    return {"jobs":[{"task_id":t,"fold":f,"variant":v,
        "source":"stage_g_reuse" if f==0 else "stage_h_fresh"}
        for t,f,v in control.expected_jobs(("E2","E3b"))]}

def test_complete_matrix_no_h2_or_selected_folds():
    p=matrix();control.validate_jobs(p)
    assert len(p["jobs"])==60
    assert sum(j["fold"]>0 for j in p["jobs"])==52
    assert len(control.expected_jobs(("E3a",),False))==26
    for altered in (p["jobs"][:-1],list(reversed(p["jobs"])),p["jobs"]+[p["jobs"][0]]):
        with pytest.raises(ValueError):control.validate_jobs({"jobs":altered})
    p["jobs"][0]["source"]="stage_h_fresh"
    with pytest.raises(ValueError,match="reuse"):control.validate_jobs(p)

@pytest.mark.parametrize("task,k,base",[("contract",5,11000),("node",10,10000)])
def test_seed_formula_is_existing_fold_formula(task,k,base):
    for f in range(k):
        assert prepare.seeds(task,f)=={"constructor":base+f,"pair":base+f+77,"fit":base+f+1000000}

@pytest.mark.parametrize("task_id",TASK_ORDER)
def test_all_real_splits_are_unmodified_complete_disjoint(task_id):
    info=read_json(STAGE_G/"initialization"/task_id/"task_manifest.json")
    source=read_json(info["source_splits_path"])
    seen=set()
    for f in range(source["k_folds"]):
        split=prepare.select_split(info,f)
        assert split==source["folds"][f]
        assert not set(split["train_files"])&set(split["val_files"])
        assert set(split["train_files"])|set(split["val_files"])==set(source["files"])
        assert not seen&set(split["val_files"])
        seen.update(split["val_files"])
        split["val_files"].append("fixture")
        assert "fixture" not in source["folds"][f]["val_files"]
    assert seen==set(source["files"])
    with pytest.raises(ValueError):prepare.select_split(info,-1)
    with pytest.raises(ValueError):prepare.select_split(info,source["k_folds"])

def test_stage_g_functions_not_mutated_and_fit_is_same_object():
    assert worker.fit is gt.fit
    assert control.verify_fit is gc.verify_fit
    assert control.existing_success.__code__ is gc.existing_success.__code__
    assert gc.existing_success.__globals__["job_dir"] is gc.job_dir
    assert control.existing_success.__globals__["job_dir"] is control.job_dir
    job={"task_id":"x","fold":7,"variant":"E3b"}
    assert str(control.job_dir("/tmp/a",job)).endswith("/x/fold_7/E3b")
    with pytest.raises(ValueError):control.job_dir("/tmp/a",job,"smoke")

@pytest.mark.parametrize("variant,mode,fold",[("E3a","full",1),("E2","smoke",1),("E2","full",0)])
def test_worker_rejects_h2_smoke_and_retraining_zero_before_io(variant,mode,fold):
    with pytest.raises(ValueError,match="fresh"):
        worker.run("/nonexistent","x",variant,mode,"/nonexistent/run",fold)

def pred(file,target,best,prob):
    return {"file":file,"target":target,"best":best,"last":best,
            "best_positive_probability":prob,"last_positive_probability":prob}

def test_statistics_sample_std_and_equal_fold_not_pooled():
    rows=[{"task_id":"x","variant":"E2","buggy_f1":0.},{"task_id":"x","variant":"E2","buggy_f1":100.}]
    a=report.aggregate(rows,("task_id","variant"),("buggy_f1",))[0]
    assert a["buggy_f1_mean"]==50
    assert a["buggy_f1_sample_std"]==pytest.approx(70.71067811865476)
    with pytest.raises(ValueError):report.aggregate(rows[:1],("task_id",),("buggy_f1",))
    metrics,all_rows=report.pooled({0:[pred("a",1,0,.1)],1:[pred("b",1,1,.9),pred("c",1,1,.9)]},2)
    assert metrics["best"]["buggy_f1"]==80
    assert len(all_rows)==3

def test_oof_rejects_missing_fold_and_repeated_files():
    with pytest.raises(ValueError,match="Incomplete"):report.pooled({0:[pred("a",1,1,.9)]},2)
    with pytest.raises(ValueError,match="multiple"):report.pooled({0:[pred("a",1,1,.9)],1:[pred("a",1,0,.1)]},2)

def test_prediction_vs_probability_change_and_negative_identity():
    a=[pred("a",1,0,.1),pred("b",0,0,.2),pred("c",1,1,.9)]
    b=[pred("a",1,1,.8),pred("b",0,1,.7),pred("c",1,1,.8)]
    counts,details=report.compare_rows(a,b,{"checkpoint":"best"})
    assert counts=={"both_correct":1,"both_wrong":0,"fixed":1,"regressed":1,"probability_changed":3,"prediction_changed":2}
    assert len(details)==3
    b[0]["target"]=0
    with pytest.raises(ValueError,match="identity"):report.compare_rows(a,b,{"checkpoint":"best"})

def test_failed_worker_stops_and_requires_explicit_retry(tmp_path,monkeypatch):
    job={"task_id":TASK_ORDER[0],"fold":1,"variant":"E2","source":"stage_h_fresh"}
    plan={"jobs":[job]}
    monkeypatch.setattr(control,"TASK_ORDER",(TASK_ORDER[0],))
    monkeypatch.setattr(control,"verify_plan",lambda _:plan)
    @contextmanager
    def lock(_):yield
    monkeypatch.setattr(gc,"execution_lock",lock)
    def locate(output,job,plan):
        root=control.job_dir(output,job)
        attempts=gc.attempt_inventory(root) if root.exists() else []
        complete=[a for a in attempts if (a/"receipt.json").exists()]
        return (complete[0] if complete else None),attempts
    monkeypatch.setattr(control,"locate",locate)
    monkeypatch.setattr(control,"verify_fit",lambda *a:{"cv_validation":{"best":{}}})
    calls=[]
    def fake(cmd,**kw):
        a=Path(cmd[cmd.index("--attempt")+1]);calls.append(a)
        if len(calls)==1:return SimpleNamespace(returncode=1)
        a.mkdir();(a/"receipt.json").write_text("{}")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(control.subprocess,"run",fake)
    with pytest.raises(RuntimeError,match="STOP"):control.execute(tmp_path)
    before=calls[0].with_suffix(".execution.json").read_bytes()
    with pytest.raises(RuntimeError,match="explicit retry"):control.execute(tmp_path)
    assert len(calls)==1
    control.execute(tmp_path,retry=control.identity(job))
    assert [a.name for a in calls]==["attempt_001","attempt_002"]
    assert calls[0].with_suffix(".execution.json").read_bytes()==before
    control.execute(tmp_path)
    assert len(calls)==2
    with pytest.raises(ValueError):control.execute(tmp_path,retry=TASK_ORDER[0]+"/fold_1/E3a")

def test_h1_runtime_contains_unchanged_stage_g_and_new_controller():
    old=read_json(STAGE_G/"plan.json")["runtime_code_sha256"]
    now=control.runtime_hashes()
    assert all(now[p]==h and sha256(p)==h for p,h in old.items())
    assert str(Path(control.__file__).resolve()) in now
    assert str(Path(worker.__file__).resolve()) in now
