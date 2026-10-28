"""Regression tests for staged orchestration; never starts a CUDA process."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from scripts.DFG.dfg_v2.experiment import batch


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


@pytest.fixture
def setup(tmp_path, monkeypatch):
    jobs = [dict(task_id="synthetic_node", fold=0, seed=1, profile=p,
                 layer_impl="shared_projection") for p in ("G0","G1R","G2R","G3R","G3")]
    plan = dict(jobs=jobs, resource_policy={"version":"local_dev_v1"},
        batch_registration=dict(stages={
            "A":dict(profiles=["G0","G3R"],jobs=[batch.run.job_id(j) for j in jobs if j["profile"] in ("G0","G3R")]),
            "B":dict(profiles=["G1R","G2R","G3"],jobs=[batch.run.job_id(j) for j in jobs if j["profile"] in ("G1R","G2R","G3")])}))
    path = dump(tmp_path/"plan.json",plan)
    monkeypatch.setattr(batch.run,"_load_plan",lambda p,**kwargs:plan)
    return path,plan


def auth(path,plan,stage="A",**extra):
    record=dict(version=batch.AUTH_VERSION,approved=True,stage=stage,plan=batch._ref(path),
        authorized_jobs=[batch.run.job_id(j) for j in batch.stage_jobs(plan,stage)],
        user_answer="explicit synthetic test approval",recorded_at="2026-10-26T00:00:00Z")
    record.update(extra)
    return dump(path.parent/("authorization_"+stage+".json"),record)


@pytest.mark.parametrize("stage,profiles",[("A",["G0","G3R"]),("B",["G1R","G2R","G3"])])
def test_stage_order(setup,stage,profiles):
    _,plan=setup
    assert [j["profile"] for j in batch.stage_jobs(plan,stage)]==profiles


@pytest.mark.parametrize("mutation",["missing","duplicate","unknown","overlap","wrong_profile"])
def test_invalid_stage_partition(setup,mutation):
    _,p=setup;s=p["batch_registration"]["stages"]
    if mutation=="missing":s["B"]["jobs"].pop()
    elif mutation=="duplicate":s["A"]["jobs"].append(s["A"]["jobs"][0])
    elif mutation=="unknown":s["A"]["jobs"][0]="absent"
    elif mutation=="overlap":s["B"]["jobs"].append(s["A"]["jobs"][0])
    else:s["A"]["profiles"]=["G0"]
    with pytest.raises(ValueError):batch.stage_jobs(p,"A")


@pytest.mark.parametrize("field,value",[("approved",False),("stage","B"),("user_answer",""),
    ("recorded_at",""),("authorized_jobs",[]),("version","legacy"),("plan",{})])
def test_authorization_is_bound(setup,field,value):
    path,p=setup;a=auth(path,p)
    r=json.loads(a.read_text());r[field]=value;dump(a,r)
    with pytest.raises(ValueError):batch.validate_authorization(path,p,"A",a)


def test_direct_job_needs_authorization(setup):
    path,p=setup
    with pytest.raises(ValueError):batch.authorize_job(path,p,p["jobs"][0],None)
    a=auth(path,p)
    assert batch.authorize_job(path,p,p["jobs"][0],a)==batch._ref(a)
    with pytest.raises(ValueError):batch.authorize_job(path,p,p["jobs"][1],a)


def test_b_needs_exact_interim_report(setup):
    path,p=setup
    a=auth(path,p,"B")
    with pytest.raises(FileNotFoundError):batch.validate_authorization(path,p,"B",a)
    report=path.parent/"reports"/"interim_A"/"REPORT_INTERIM_A.md"
    report.parent.mkdir(parents=True);report.write_text("synthetic interim")
    receipt=dump(path.parent/"batch_records"/"interim_A.json",
        dict(version=batch.VERSION,stage="A",status="complete",plan_sha256=batch.sha256(path),
             report_files={"REPORT_INTERIM_A.md":batch._ref(report)}))
    a=auth(path,p,"B",interim_receipt=batch._ref(receipt))
    batch.validate_authorization(path,p,"B",a)
    report.write_text("tampered")
    with pytest.raises(ValueError):batch.validate_authorization(path,p,"B",a)


def install_fake_execution(monkeypatch,path,completed=None,fail=False):
    completed={} if completed is None else completed
    calls=[];started={}
    monkeypatch.setattr(batch,"_attempts",lambda p,j:started.get(batch.run.job_id(j),[]))
    monkeypatch.setattr(batch,"_accept",lambda p,plan,j:completed.get(batch.run.job_id(j)))
    def child(argv,**kwargs):
        identity=argv[argv.index("--only")+1];calls.append(identity)
        kwargs["stdout"].write("synthetic process")
        if fail:return SimpleNamespace(returncode=1)
        attempt=path.parent/"fake"/identity
        dump(attempt/"receipt.json",{"synthetic":True,"job":identity})
        started[identity]=[dump(attempt.parent/(attempt.name+".started.json"),{"job":identity})]
        row=dict(attempt=str(attempt),result={},audit={"passed":True})
        completed[identity]=row
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(batch.subprocess,"run",child)
    return calls,completed,started


def test_serial_success_and_resume_skip(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    calls,completed,started=install_fake_execution(monkeypatch,path)
    result=batch.execute(path,"A",a)
    assert result["complete"] and result["jobs"]==2
    assert calls==p["batch_registration"]["stages"]["A"]["jobs"]
    for identity in calls:
        started[identity]=[dump(path.parent/(identity.replace("/","_")+".started.json"),{})]
    calls.clear()
    result2=batch.execute(path,"A",a)
    assert result2["complete"] and calls==[]
    assert result["invocation"]!=result2["invocation"]
    assert len(list((path.parent/"batch_records"/"executions"/"A").glob("invocation_*")))==2


def test_child_failure_stops_no_retry_and_keeps_log(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    calls,_,_=install_fake_execution(monkeypatch,path,fail=True)
    with pytest.raises(RuntimeError):batch.execute(path,"A",a)
    assert calls==[p["batch_registration"]["stages"]["A"]["jobs"][0]]
    failures=list((path.parent/"batch_records").rglob("failure.json"))
    assert len(failures)==1
    record=json.loads(failures[0].read_text())
    assert record["automatic_retry"] is False
    logs=list((path.parent/"batch_records").rglob("*.log"))
    assert len(logs)==1 and logs[0].read_text()=="synthetic process"


def test_old_failure_cannot_be_skipped_and_retry_needs_identity(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    calls,_,started=install_fake_execution(monkeypatch,path)
    identity=batch.run.job_id(p["jobs"][0])
    old=dump(path.parent/"retained"/"attempt_001.started.json",{"old":True})
    failure=dump(old.with_name("attempt_001.failure.json"),{"cuda_oom":True})
    started[identity]=[old]
    with pytest.raises(RuntimeError):batch.execute(path,"A",a)
    with pytest.raises(ValueError):batch.execute(path,"A",a,retry_job=identity)
    assert calls==[] and json.loads(failure.read_text())=={"cuda_oom":True}
    a=auth(path,p,retry_job=identity,retry_evidence=batch._ref(failure))
    result=batch.execute(path,"A",a,retry_job=identity)
    assert result["complete"] and calls[0]==identity
    assert json.loads(old.read_text())=={"old":True}


def test_verify_requires_all_stage_results(setup,monkeypatch):
    path,p=setup
    monkeypatch.setattr(batch,"_accept",lambda *a:None)
    with pytest.raises(ValueError,match="Incomplete stage"):batch.verify_stage(path,"A")


def test_interim_is_exclusive_and_sha_bound(setup,monkeypatch):
    from scripts.DFG.dfg_v2.experiment import reporting
    path,p=setup
    monkeypatch.setattr(batch,"verify_stage",lambda *a:{"completed_jobs":2,"results":{}})
    def fake_report(*args,**kwargs):
        folder=path.parent/"reports"/"interim_A";folder.mkdir(parents=True)
        (folder/"REPORT_INTERIM_A.md").write_text("中间结果")
        return {"output":str(folder)}
    monkeypatch.setattr(reporting,"build_report",fake_report)
    result=batch.interim(path,"A")
    assert result["stop_for_user_review"] is True
    record=json.loads(Path(result["receipt"]).read_text())
    assert record["selected_profile"] is None
    assert record["next_stage_execution_authorized"] is False
    report=path.parent/"reports"/"interim_A"/"REPORT_INTERIM_A.md"
    assert record["report_files"]["REPORT_INTERIM_A.md"]==batch._ref(report)
    with pytest.raises(FileExistsError):batch.interim(path,"A")


def test_interim_does_not_allow_selection(setup):
    path,p=setup;dump(path.parent/"selection.json",{})
    with pytest.raises(ValueError,match="selected profile"):batch.interim(path,"A")


def test_bad_completed_semantics_rejected(setup,monkeypatch):
    path,p=setup
    monkeypatch.setattr(batch.run,"_completed",lambda *a:(path.parent,{"resources":{}}))
    monkeypatch.setattr(batch,"audit_pilot_result",lambda *a,**k:{"passed":False,"problems":["zero gradient"]})
    with pytest.raises(ValueError,match="gradient"):batch._accept(path,p,p["jobs"][0])


def test_measurement_errors_are_not_accepted(setup,monkeypatch):
    path,p=setup
    monkeypatch.setattr(batch.run,"_completed",lambda *a:(path.parent,{"resources":{"sampling_errors":["lost"]}}))
    monkeypatch.setattr(batch,"audit_pilot_result",lambda *a,**k:{"passed":True})
    with pytest.raises(ValueError,match="sampling"):batch._accept(path,p,p["jobs"][0])


def test_preflight_failure_without_fit_cannot_resume_old_approval(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    calls,_,started=install_fake_execution(monkeypatch,path,fail=True)
    with pytest.raises(RuntimeError):batch.execute(path,"A",a)
    assert started=={}
    first=list((path.parent/"batch_records").rglob("failure.json"))[0]
    before=first.read_bytes()
    assert json.loads(before)["active_job"]==calls[0]
    with pytest.raises(RuntimeError,match="preserved"):
        batch.execute(path,"A",a)
    assert len(calls)==1 and first.read_bytes()==before
    assert len(list((path.parent/"batch_records"/"executions"/"A").glob("invocation_*")))==1


def test_explicit_retry_of_preflight_failure_is_bound_and_resolves_only_after_acceptance(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    calls,completed,started=install_fake_execution(monkeypatch,path,fail=True)
    with pytest.raises(RuntimeError):batch.execute(path,"A",a)
    failure=list((path.parent/"batch_records").rglob("failure.json"))[0]
    identity=calls[0]
    a=auth(path,p,retry_job=identity,retry_evidence=batch._ref(failure))
    calls,completed,started=install_fake_execution(monkeypatch,path,completed=completed)
    result=batch.execute(path,"A",a,retry_job=identity)
    assert result["complete"] and calls[0]==identity
    resolution=Path(result["invocation"])/"retry_resolution.json"
    doc=json.loads(resolution.read_text())
    assert doc["resolved_evidence"]==[batch._ref(failure)]
    assert batch._controller_failures(path)==[]
    assert failure.exists()


def test_failed_retry_remains_latched_and_old_evidence_cannot_skip_other_failure(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    calls,_,_=install_fake_execution(monkeypatch,path,fail=True)
    with pytest.raises(RuntimeError):batch.execute(path,"A",a)
    first=list((path.parent/"batch_records").rglob("failure.json"))[0]
    first_identity=calls[0]
    a=auth(path,p,retry_job=first_identity,retry_evidence=batch._ref(first))
    with pytest.raises(RuntimeError):batch.execute(path,"A",a,retry_job=first_identity)
    assert len(batch._controller_failures(path))==2
    assert not list((path.parent/"batch_records").rglob("retry_resolution.json"))
    # A distinct job's retained controller failure cannot be waived by this approval.
    other=batch.stage_jobs(p,"A")[1]
    folder=batch._next_invocation(path,"A")
    dump(folder/"started.json",dict(plan=batch._ref(path),pid=0,authorization=batch._ref(a)))
    dump(folder/"failure.json",dict(plan=batch._ref(path),active_job=batch.run.job_id(other)))
    previous=len(calls)
    with pytest.raises(RuntimeError,match="Other unresolved"):
        batch.execute(path,"A",a,retry_job=first_identity)
    assert len(calls)==previous


def test_interrupted_controller_before_child_is_not_silent_resume(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    calls,_,_=install_fake_execution(monkeypatch,path)
    folder=batch._next_invocation(path,"A")
    started=dump(folder/"started.json",dict(plan=batch._ref(path),pid=0,authorization=batch._ref(a)))
    with pytest.raises(RuntimeError,match="preserved"):
        batch.execute(path,"A",a)
    assert calls==[]
    identity=batch.run.job_id(batch.stage_jobs(p,"A")[0])
    a=auth(path,p,retry_job=identity,retry_evidence=batch._ref(started))
    assert batch.execute(path,"A",a,retry_job=identity)["complete"]
    assert batch._controller_failures(path)==[]


def test_retry_does_not_train_earlier_new_job(setup,monkeypatch):
    path,p=setup
    calls,_,started=install_fake_execution(monkeypatch,path)
    identity=batch.run.job_id(batch.stage_jobs(p,"A")[1])
    old=dump(path.parent/"retained"/"attempt_001.started.json",{})
    failure=dump(old.with_name("attempt_001.failure.json"),{"failed":True})
    started[identity]=[old]
    a=auth(path,p,retry_job=identity,retry_evidence=batch._ref(failure))
    with pytest.raises(RuntimeError,match="earlier jobs"):
        batch.execute(path,"A",a,retry_job=identity)
    assert calls==[]


def test_direct_retry_requires_new_decision_and_preserved_evidence(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    job=batch.stage_jobs(p,"A")[0];identity=batch.run.job_id(job)
    old=dump(path.parent/"retained"/"attempt_001.started.json",{})
    failure=dump(old.with_name("attempt_001.failure.json"),{"failed":True})
    monkeypatch.setattr(batch,"_attempts",lambda p,j:[old] if j==job else [])
    monkeypatch.setattr(batch.run,"_completed",lambda *args:None)
    with pytest.raises(ValueError,match="new user decision"):
        batch.authorize_job(path,p,job,a,retry=True)
    a=auth(path,p,retry_job=identity,retry_evidence=batch._ref(failure))
    assert batch.authorize_job(path,p,job,a,retry=True)==batch._ref(a)


def test_direct_run_cannot_bypass_preflight_failure_latch(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    calls,_,_=install_fake_execution(monkeypatch,path,fail=True)
    with pytest.raises(RuntimeError):batch.execute(path,"A",a)
    job=batch.stage_jobs(p,"A")[0]
    with pytest.raises(RuntimeError,match="explicit"):
        batch.authorize_job(path,p,job,a)


def test_child_ignores_only_bound_active_parent_controller(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    job=batch.stage_jobs(p,"A")[0];identity=batch.run.job_id(job)
    folder=batch._next_invocation(path,"A")
    dump(folder/"started.json",dict(plan=batch._ref(path),pid=123,authorization=batch._ref(a)))
    dump(folder/"001.active_job.json",dict(job=identity,plan=batch._ref(path)))
    monkeypatch.setattr(batch.os,"getppid",lambda:123)
    assert batch.authorize_job(path,p,job,a)==batch._ref(a)
    monkeypatch.setattr(batch.os,"getppid",lambda:124)
    with pytest.raises(RuntimeError,match="explicit"):
        batch.authorize_job(path,p,job,a)


def test_a_new_failed_retry_requires_a_new_evidence_bound_decision(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    calls,_,_=install_fake_execution(monkeypatch,path,fail=True)
    with pytest.raises(RuntimeError):batch.execute(path,"A",a)
    first=list((path.parent/"batch_records").rglob("failure.json"))[0]
    identity=calls[0]
    a=auth(path,p,retry_job=identity,retry_evidence=batch._ref(first))
    with pytest.raises(RuntimeError):batch.execute(path,"A",a,retry_job=identity)
    count=len(calls)
    with pytest.raises(ValueError,match="latest preserved"):
        batch.execute(path,"A",a,retry_job=identity)
    assert len(calls)==count


def test_direct_new_fit_cannot_skip_registered_prior_job_but_success_reuse_can(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    first,last=batch.stage_jobs(p,"A")
    monkeypatch.setattr(batch,"_accept",lambda *args:None)
    with pytest.raises(RuntimeError,match="Earlier stage"):
        batch.authorize_job(path,p,last,a)
    # A validated existing result needs no new execution or reordering.
    monkeypatch.setattr(batch.run,"_completed",lambda *args:(path.parent,{"verified":True}))
    monkeypatch.setattr(batch,"_attempts",lambda p,j:[path.parent/"synthetic.started.json"] if j==last else [])
    assert batch.authorize_job(path,p,last,a)==batch._ref(a)


def test_direct_new_fit_allowed_after_prior_job_verified(setup,monkeypatch):
    path,p=setup;a=auth(path,p)
    first,last=batch.stage_jobs(p,"A")
    monkeypatch.setattr(batch,"_attempts",lambda p,j:[path.parent/"synthetic.started.json"] if j==first else [])
    monkeypatch.setattr(batch.run,"_completed",lambda *args:(path.parent,{"verified":True}))
    assert batch.authorize_job(path,p,last,a)==batch._ref(a)
