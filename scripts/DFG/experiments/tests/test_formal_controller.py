from pathlib import Path
import pytest
from scripts.DFG.experiments import formal
from scripts.DFG.experiments.common import read_json,write_json


def fixture_controller(tmp_path,monkeypatch):
    root=tmp_path/"formal"
    root.mkdir()
    job={"id":"reentrancy_author_contract_fold0","cohort":"reentrancy_author","task":"contract",
         "fold":0,"prepared":"fixture/prepared","splits":"fixture/splits"}
    plan={"device":"cuda:0","threads":2,"jobs":[job],
          "task_order":[{"cohort":"reentrancy_author","task":"contract","folds":5}]}
    state={"stage_b":"pending","stage_c":"pending","jobs":{}}
    write_json(root/"state.json",state)
    monkeypatch.setattr(formal,"validate_plan",lambda _:plan)
    monkeypatch.setattr(formal,"verify_fold",lambda *a:{"status":"passed","variants":{}})
    calls=[]
    def worker(command,log):
        calls.append(command)
        output=Path(command[command.index("--output")+1])
        output.mkdir()
        write_json(output/"result.json",{"fixture":True})
        log.write_text("fixture successful")
        return 0
    monkeypatch.setattr(formal,"launch",worker)
    return root,plan,state,job,calls


def test_b_accepts_only_one_pair_and_reuses_it(tmp_path,monkeypatch):
    root,plan,state,job,calls=fixture_controller(tmp_path,monkeypatch)
    result=formal.execute_stage(root,"stage-b")
    assert result["stage_b"]=="passed" and result["stage_c"]=="pending" and len(calls)==1
    formal.execute_stage(root,"stage-b")
    assert len(calls)==1
    assert "--fold" in calls[0] and calls[0][calls[0].index("--fold")+1]=="0"


def test_stage_c_requires_explicit_confirmation_even_after_b(tmp_path,monkeypatch):
    root,plan,state,job,calls=fixture_controller(tmp_path,monkeypatch)
    formal.execute_stage(root,"stage-b")
    with pytest.raises(ValueError,match="confirm-stage-c"):
        formal.execute_stage(root,"stage-c")
    assert len(calls)==1


def test_stage_c_requires_accepted_b(tmp_path,monkeypatch):
    root,plan,state,job,calls=fixture_controller(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match="Stage B"):
        formal.execute_stage(root,"stage-c",True)
    assert not calls


def test_corrupt_completed_artifact_not_retrained_or_trusted(tmp_path,monkeypatch):
    root,plan,state,job,calls=fixture_controller(tmp_path,monkeypatch)
    formal.execute_stage(root,"stage-b")
    state=read_json(root/"state.json")
    (root/state["jobs"][job["id"]]["attempt"]/"result.json").write_text("tampered")
    with pytest.raises(ValueError,match="artifacts changed"):
        formal.execute_stage(root,"stage-b",retry_failed=True)
    assert len(calls)==1


def test_failed_attempt_requires_explicit_retry_preserves_old_bytes(tmp_path,monkeypatch):
    root,plan,state,job,calls=fixture_controller(tmp_path,monkeypatch)
    real=formal.launch
    def fail(command,log):
        real(command,log)
        return 2
    monkeypatch.setattr(formal,"launch",fail)
    with pytest.raises(RuntimeError,match="Worker failed"):
        formal.execute_stage(root,"stage-b")
    first=read_json(root/"state.json")["jobs"][job["id"]]
    fingerprint=formal.fingerprint_tree(root/first["attempt"])
    monkeypatch.setattr(formal,"launch",real)
    with pytest.raises(RuntimeError,match="retry-failed"):
        formal.execute_stage(root,"stage-b")
    formal.execute_stage(root,"stage-b",retry_failed=True)
    later=read_json(root/"state.json")["jobs"][job["id"]]
    assert later["attempt"]!=first["attempt"] and later["status"]=="passed"
    assert formal.fingerprint_tree(root/first["attempt"])==fingerprint
    assert len(calls)==2


def test_task_barrier_stops_next_task(tmp_path,monkeypatch):
    root,plan,state,job,calls=fixture_controller(tmp_path,monkeypatch)
    formal.execute_stage(root,"stage-b")
    other=dict(job,id="access_control_author_contract_fold0",cohort="access_control_author")
    plan["jobs"].append(other)
    plan["task_order"].append(dict(cohort="access_control_author",task="contract",folds=5))
    def fail(*a):
        raise ValueError("Task incomplete")
    monkeypatch.setattr(formal,"task_summary",fail)
    with pytest.raises(ValueError,match="Task incomplete"):
        formal.execute_stage(root,"stage-c",True)
    assert len(calls)==1


def test_lock_prevents_two_controllers(tmp_path):
    with formal.run_lock(tmp_path):
        with pytest.raises(RuntimeError,match="Another formal"):
            with formal.run_lock(tmp_path):
                pass
    with formal.run_lock(tmp_path):
        pass


def test_live_orphan_worker_blocks_retry(tmp_path,monkeypatch):
    root,plan,state,job,calls=fixture_controller(tmp_path,monkeypatch)
    job_root=root/"jobs"/job["id"]
    write_json(job_root/"attempt_001.process.json",{"pid":12345,"start_ticks":"6789"})
    monkeypatch.setattr(formal,"process_identity",lambda pid:"6789")
    with pytest.raises(RuntimeError,match="still alive"):
        formal.execute_stage(root,"stage-b",retry_failed=True)
    assert not calls


def test_dead_worker_marker_does_not_block_explicit_retry(tmp_path,monkeypatch):
    root,plan,state,job,calls=fixture_controller(tmp_path,monkeypatch)
    job_root=root/"jobs"/job["id"]
    write_json(job_root/"attempt_001.process.json",{"pid":12345,"start_ticks":"6789"})
    monkeypatch.setattr(formal,"process_identity",lambda pid:None)
    formal.execute_stage(root,"stage-b",retry_failed=True)
    assert len(calls)==1 and "attempt_002" in calls[0][-1]


@pytest.mark.parametrize("change",["code","commit","input","resource","plan","gpu"])
def test_frozen_plan_rejects_drift(tmp_path,monkeypatch,change):
    root=tmp_path/"batch"; root.mkdir()
    data=tmp_path/"graph.gpickle";data.write_text("frozen input")
    resource=tmp_path/"gpu.json";resource.write_text("passed")
    from scripts.DFG.experiments.common import sha256
    monkeypatch.setattr(formal,"code_hashes",lambda:{"fixture.py":"frozen"})
    monkeypatch.setattr(formal,"git_head",lambda:"HEAD")
    plan={"format":formal.FORMAT,"protocol":formal.NAME,"protocol_version":formal.VERSION,
          "score_role":formal.SCORE_ROLE,"base_git_head":"HEAD","runner_code_sha256":{"fixture.py":"frozen"},
          "frozen_files":{str(data):sha256(data)},
          "resources":{"fixture":{"path":str(resource),"sha256":sha256(resource),
                                   "status":"blocked" if change=="gpu" else "passed"}}}
    write_json(root/"plan.json",plan)
    write_json(root/"plan.seal.json",{"sha256":sha256(root/"plan.json")})
    if change=="code":monkeypatch.setattr(formal,"code_hashes",lambda:{"fixture.py":"changed"})
    elif change=="commit":monkeypatch.setattr(formal,"git_head",lambda:"NEW_HEAD")
    elif change=="input":data.write_text("changed")
    elif change=="resource":resource.write_text("changed")
    elif change=="plan":(root/"plan.json").write_text("{}")
    with pytest.raises(ValueError):
        formal.validate_plan(root)


@pytest.mark.skipif(not (formal.ROOT/"audit/formal_20261012_v1/resource_reentrancy_author_contract.json").exists(), reason="local real Dataset A/resource evidence unavailable")
def test_actual_prepared_inputs_form_exactly_thirty_paired_jobs(tmp_path,monkeypatch):
    monkeypatch.setattr(formal,"protocol_output",lambda p:Path(p))
    plan=formal.init_plan(tmp_path/"plan",formal.ROOT/"audit/formal_20261012_v1")
    assert len(plan["jobs"])==30
    assert [t["folds"] for t in plan["task_order"]]==[5,5,10,10]
    assert [j["fold"] for j in plan["jobs"][:5]]==list(range(5))
    assert plan["seed"]==1 and plan["epochs"]==50 and plan["mode"]=="full"
    assert plan["jobs"][0]["id"]=="reentrancy_author_contract_fold0"
    assert all("author" in j["cohort"] for j in plan["jobs"])
    assert formal.validate_plan(tmp_path/"plan")==plan
