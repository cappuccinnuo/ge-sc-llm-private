"""Runner preflight integration with mock GPU observations only."""
import copy
import subprocess
from pathlib import Path
import pytest
from scripts.DFG.integration.io import read_json, write_json
from scripts.DFG.dfg_v2.experiment import run, preflight


@pytest.fixture
def execution(tmp_path, monkeypatch):
    job=dict(task_id="synthetic_node",fold=0,seed=1,profile="G3R")
    doc=dict(test_mode=False,jobs=[job],resource_policy=copy.deepcopy(preflight.DEFAULT_PREFLIGHT_POLICY))
    path=tmp_path/"plan.json"
    write_json(path,doc)
    monkeypatch.setattr(run,"ROOT",tmp_path)
    monkeypatch.setattr(run,"_load_plan",lambda *a,**k:doc)
    monkeypatch.setattr(run,"_completed",lambda *a:None)
    monkeypatch.setattr(run,"_verify_attempt",lambda *a:{})
    monkeypatch.setattr(preflight,"_cuda_initialized",lambda:False)
    monkeypatch.setattr(preflight,"query_baseline",lambda:dict(
        uuid="GPU-test",total_mib=4096,used_mib=500,free_mib=3500))
    return path,doc,job


def test_low_baseline_no_attempt_and_block_retained(execution,monkeypatch):
    path,doc,job=execution
    monkeypatch.setattr(preflight,"query_baseline",lambda:dict(
        uuid="GPU-test",total_mib=4096,used_mib=2000,free_mib=2000))
    monkeypatch.setattr(run,"_run_one",lambda *a,**k:pytest.fail("Training started"))
    for unused in range(2):
        with pytest.raises(preflight.PreflightBlocked):
            run.execute(path,only=run.job_id(job))
    folder=run._job_directory(path.parent,job)
    records=sorted(folder.glob("preflight_*.json"))
    assert len(records)==2
    assert all(read_json(p)["status"]=="preflight_blocked" for p in records)
    assert not list(folder.glob("attempt_*"))


def test_query_failure_stops_without_attempt(execution,monkeypatch):
    path,doc,job=execution
    def unavailable():
        raise FileNotFoundError("nvidia-smi")
    monkeypatch.setattr(preflight,"query_baseline",unavailable)
    monkeypatch.setattr(run,"_run_one",lambda *a,**k:pytest.fail("Training started"))
    with pytest.raises(preflight.PreflightError):
        run.execute(path,only=run.job_id(job))
    folder=run._job_directory(path.parent,job)
    assert read_json(next(folder.glob("preflight_*.json")))["status"]=="preflight_error"
    assert not list(folder.glob("attempt_*"))


def test_fresh_single_job_and_context_checks(execution,monkeypatch):
    path,doc,job=execution
    with pytest.raises(ValueError,match="--only"):
        run.execute(path)
    monkeypatch.setattr(preflight,"_cuda_initialized",lambda:True)
    monkeypatch.setattr(preflight,"query_baseline",lambda:pytest.fail("Already-initialized query"))
    with pytest.raises(preflight.PreflightError):
        run.execute(path,only=run.job_id(job))
    assert not list(run._job_directory(path.parent,job).glob("attempt_*"))


def test_pass_before_start_success_reuse_no_new_preflight(execution,monkeypatch):
    path,doc,job=execution
    calls=[]
    def fit(plan, selected, attempt, plan_path, preflight=None):
        assert preflight["status"]=="passed"
        assert attempt.with_suffix(".started.json").is_file()
        assert not attempt.with_suffix(".failure.json").exists()
        calls.append(preflight)
    monkeypatch.setattr(run,"_run_one",fit)
    outcome=run.execute(path,only=run.job_id(job))
    assert outcome[0]["status"]=="complete" and len(calls)==1
    monkeypatch.setattr(run,"_completed",lambda *a:(Path(outcome[0]["attempt"]),{}))
    monkeypatch.setattr(preflight,"run_preflight",lambda *a,**k:pytest.fail("Success queried again"))
    assert run.execute(path,only=run.job_id(job))[0]["status"]=="reused"


def test_actual_fit_failure_retained_explicit_retry(execution,monkeypatch):
    path,doc,job=execution
    def broken(*a,**k):
        raise RuntimeError("fit failure")
    monkeypatch.setattr(run,"_run_one",broken)
    with pytest.raises(RuntimeError,match="fit failure"):
        run.execute(path,only=run.job_id(job))
    folder=run._job_directory(path.parent,job)
    assert (folder/"attempt_001.failure.json").is_file()
    with pytest.raises(RuntimeError,match="--retry"):
        run.execute(path,only=run.job_id(job))
    assert len(list(folder.glob("preflight_*.json")))==1
    monkeypatch.setattr(run,"_run_one",lambda *a,**k:None)
    assert run.execute(path,only=run.job_id(job),retry=True)[0]["attempt"].endswith("attempt_002")
    assert (folder/"attempt_001.failure.json").is_file()


def test_absent_policy_preserves_legacy_multi_job_path(execution,monkeypatch):
    path,doc,job=execution
    del doc["resource_policy"]
    doc["jobs"].append(dict(job,profile="G0"))
    monkeypatch.setattr(preflight,"run_preflight",lambda *a,**k:pytest.fail("Legacy preflight"))
    seen=[]
    monkeypatch.setattr(run,"_run_one",lambda *a:seen.append(a[1]))
    assert len(run.execute(path))==2 and len(seen)==2
