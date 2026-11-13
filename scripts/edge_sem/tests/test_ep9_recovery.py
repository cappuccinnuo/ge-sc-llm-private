"""EP9 monitor recovery: bounded queries, fresh evidence, immutable runtime."""
import copy
import json
import subprocess
import time
from pathlib import Path
import pytest
import torch
from scripts.edge_sem import execution as ex, runtime
from scripts.edge_sem.io import ref
from scripts.DFG.dfg_v2.experiment.resources import MemoryGateError
from scripts.DFG.dfg_v2.experiment.preflight import LOCAL_DEV_POLICY

def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True)+"\n", encoding="utf8")
    return ref(path)

def sealed(path, value, key):
    result = put(path, value)
    put(path.with_suffix(".seal.json"), {key:result})
    return result

def sample():
    return dict(uuid="GPU-fixture", total_mib=4096., used_mib=3000., free_mib=1000.,
        unaccounted_mib=96., unix_seconds=time.time(), monotonic_seconds=time.monotonic(),
        elapsed_seconds=0., raw="fixture", command=["nvidia-smi"])

def resource(tmp_path, monkeypatch, sequence):
    for name in ("memory_allocated","memory_reserved","max_memory_allocated","max_memory_reserved"):
        monkeypatch.setattr(torch.cuda, name, lambda *a: 0)
    monkeypatch.setattr(ex.time,"sleep", lambda t: None)
    baseline=sample()
    context=dict(baseline=baseline,after_initialization=copy.deepcopy(baseline),free_decrease_mib=0)
    calls=[]
    def query():
        calls.append(1)
        item=sequence.pop(0) if sequence else None
        if isinstance(item,Exception):raise item
        return sample() if item is None else copy.deepcopy(item)
    monitor=ex.make_retrying_resources("cuda",baseline,context,tmp_path/"memory.jsonl",
        tmp_path/"history.jsonl",LOCAL_DEV_POLICY,tmp_path/"events.jsonl",query=query)
    return monitor,calls

def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines()]

@pytest.mark.parametrize("failures",[1,2])
def test_transient_query_failures_recover_with_fresh_evidence(tmp_path,monkeypatch,failures):
    error=subprocess.TimeoutExpired(["nvidia-smi"],5,stderr=b"fixture timeout")
    monitor,calls=resource(tmp_path,monkeypatch,[error]*failures+[None])
    monitor.check()
    assert len(calls)==failures+1
    assert len(monitor.observations)==1
    events=rows(tmp_path/"events.jsonl")
    assert [e["kind"] for e in events]==["error"]*failures+["recovered"]
    assert events[0]["stderr"]=="fixture timeout"
    outcome=ex.validate_sampling_recovery(monitor.summary(),monitor.observations)
    assert outcome==dict(query_failures=failures,recovered_cycles=1)

def test_process_query_failure_keeps_returncode_and_stderr(tmp_path,monkeypatch):
    error=subprocess.CalledProcessError(1,["nvidia-smi"],stderr=b"NVML query failed")
    monitor,_=resource(tmp_path,monkeypatch,[error,None])
    monitor.check()
    event=rows(tmp_path/"events.jsonl")[0]
    assert event["returncode"]==1 and event["stderr"]=="NVML query failed"
    ex.validate_sampling_recovery(monitor.summary(),monitor.observations)

def test_exhausted_query_cannot_use_an_old_success(tmp_path,monkeypatch):
    error=subprocess.TimeoutExpired(["nvidia-smi"],5)
    monitor,calls=resource(tmp_path,monkeypatch,[None,error,error,error,None])
    monitor.check()
    with pytest.raises(MemoryGateError):monitor.check()
    assert len(calls)==4 and len(monitor.observations)==1
    # Terminal failure stays terminal even if a later query would succeed.
    with pytest.raises(MemoryGateError):monitor.check()
    assert len(calls)==4
    assert len(rows(tmp_path/"events.jsonl"))==3
    with pytest.raises(ValueError):ex.validate_sampling_recovery(monitor.summary(),monitor.observations)

@pytest.mark.parametrize("bad",[ValueError("malformed reading"),RuntimeError("CUDA allocator error")])
def test_noncommand_error_does_not_retry(tmp_path,monkeypatch,bad):
    monitor,calls=resource(tmp_path,monkeypatch,[bad,None])
    with pytest.raises(MemoryGateError):monitor.check()
    assert len(calls)==1 and not monitor.observations
    assert rows(tmp_path/"events.jsonl")[0]["retryable"] is False

def test_wrong_device_is_not_retried(tmp_path,monkeypatch):
    wrong=dict(sample(),uuid="GPU-wrong")
    monitor,calls=resource(tmp_path,monkeypatch,[wrong,None])
    with pytest.raises(MemoryGateError):monitor.check()
    assert len(calls)==1 and not monitor.observations

def test_sampling_write_error_is_fatal_not_retried(tmp_path,monkeypatch):
    monitor,calls=resource(tmp_path,monkeypatch,[None])
    (tmp_path/"memory.jsonl").unlink()
    (tmp_path/"memory.jsonl").mkdir()
    with pytest.raises(MemoryGateError):monitor.check()
    assert len(calls)==1
    assert monitor.terminal_sampling_failure["error_type"]=="IsADirectoryError"

def test_success_retains_original_sample_schema_and_no_error_records(tmp_path,monkeypatch):
    monitor,calls=resource(tmp_path,monkeypatch,[None])
    monitor.check()
    observed=monitor.observations[0]
    assert set(observed)==set(sample())|{
        "torch_allocated_mib","torch_reserved_mib","pairing_completed_unix_seconds",
        "pairing_window_seconds","non_torch_residual_estimate_mib",
        "context_adjusted_residual_estimate_mib","index"}
    assert len(calls)==1 and not rows(tmp_path/"events.jsonl")
    assert ex.validate_sampling_recovery(monitor.summary(),monitor.observations)=={
        "query_failures":0,"recovered_cycles":0}

def test_finalization_joins_then_requires_fresh_sample(tmp_path,monkeypatch):
    error=subprocess.TimeoutExpired(["nvidia-smi"],5)
    monitor,calls=resource(tmp_path,monkeypatch,[None,error,error,error])
    monitor.check()
    joined=[]
    class Thread:
        def join(self):joined.append(True)
    monitor.thread=Thread()
    with pytest.raises(MemoryGateError):monitor.__exit__(None,None,None)
    assert joined==[True] and len(calls)==4

def test_finalization_preserves_original_training_exception(tmp_path,monkeypatch):
    monitor,calls=resource(tmp_path,monkeypatch,[])
    monitor.__exit__(RuntimeError,RuntimeError("CUDA out of memory"),None)
    assert not calls

@pytest.mark.parametrize("damage",["no_recovery","stale","unknown_error","missing_error","wrong_index","extra_retry"])
def test_resource_receipt_rejects_unresolved_or_stale_evidence(tmp_path,monkeypatch,damage):
    error=subprocess.TimeoutExpired(["nvidia-smi"],5)
    monitor,_=resource(tmp_path,monkeypatch,[error,None])
    monitor.check()
    records=rows(tmp_path/"events.jsonl")
    report=monitor.summary()
    if damage=="no_recovery":records.pop()
    elif damage=="stale":records[-1]["sample_unix_seconds"]=0
    elif damage=="unknown_error":records[0]["error_type"]="ValueError"
    elif damage=="missing_error":report["sampling_errors"]=[]
    elif damage=="wrong_index":records[-1]["sample_index"]=4
    else:records[-1]["attempt"]=4
    p=tmp_path/"events.jsonl"
    p.write_text("".join(json.dumps(r)+"\n" for r in records),encoding="utf8")
    report["sampling_events"]=ref(p)
    with pytest.raises(ValueError):ex.validate_sampling_recovery(report,monitor.observations)

def revision_fixture(tmp_path,monkeypatch):
    old={};new={};old_snap={};new_snap={}
    names=runtime.REVISION_FILES|{"scripts/edge_sem/trainer.py"}
    for name in sorted(names):
        slug=name.replace("/","_")
        before=tmp_path/(slug+".before.txt");before.write_text(name)
        after=tmp_path/(slug+".after.txt")
        after.write_text(name+" revised" if name in runtime.REVISION_FILES else name)
        old[name]=ref(before)["sha256"];new[name]=ref(after)["sha256"]
        old_snap[name]=ref(before);new_snap[name]=ref(after)
    plan=dict(experiment_stage="E-B",analysis_role="primary",runtime=old,runtime_snapshots=old_snap)
    path=tmp_path/"plan.json";put(path,plan)
    failure=put(tmp_path/"failure.json",{"error":"fixture"})
    receipt=put(tmp_path/"receipt.json",{"status":"complete"})
    request=dict(execution_authorized=True,user_request="approve EP9 recovery",
        prior_plans={"primary":ref(path)},automatic_fit_retry=False,
        restart_failed_job_from_sealed_initial=True,old_runtime=old,
        failure=failure,pipeline_failure=failure,completed_receipts=[receipt])
    request_ref=sealed(tmp_path/"request.json",request,"request")
    results=[]
    for suite in ("scripts/edge_sem/tests","scripts/node_sem/tests","scripts/DFG/dfg_v2/tests"):
        log=tmp_path/(suite.replace("/","_")+".log");log.write_text("passed")
        results.append(dict(suite=suite,returncode=0,log=ref(log)))
    test_ref=sealed(tmp_path/"tests.json",dict(runtime=new,results=results),"results")
    reused_ref=sealed(tmp_path/"verified.json",dict(passed=True,receipts=[receipt]),"verification")
    data=dict(version=runtime.REVISION_VERSION,plans={"primary":ref(path)},old_runtime=old,
        sampling_policy=copy.deepcopy(runtime.SAMPLING_RETRY_POLICY),request=request_ref,
        runtime=new,runtime_snapshots=new_snap,changed_files=sorted(runtime.REVISION_FILES),
        tests=test_ref,verified_successes=reused_ref)
    revision=tmp_path/"revision.json";sealed(revision,data,"revision")
    monkeypatch.setattr(runtime,"runtime_refs",lambda:new)
    return path,plan,revision,data

def test_revision_accepts_exact_scope_without_altering_old_plan(tmp_path,monkeypatch):
    path,plan,revision,data=revision_fixture(tmp_path,monkeypatch)
    before=path.read_bytes()
    assert runtime.verify_execution_revision(path,plan,revision,True)==data
    assert path.read_bytes()==before
    with pytest.raises(ValueError,match="Sealed runtime changed"):runtime.verify_snapshot(plan,True)
    runtime.verify_snapshot(plan,False)

@pytest.mark.parametrize("damage",["seal","stage","plan","policy","source","extra_change","snapshot",
                                   "current_runtime","test_log","request","success"])
def test_revision_rejects_unapproved_changes(tmp_path,monkeypatch,damage):
    path,plan,revision,data=revision_fixture(tmp_path,monkeypatch)
    if damage=="seal":revision.write_text("{}")
    elif damage=="stage":plan["experiment_stage"]="E-A"
    elif damage=="plan":data["plans"]["primary"]["sha256"]="bad"
    elif damage=="policy":data["sampling_policy"]["max_attempts"]=4
    elif damage=="source":data["runtime"].pop("scripts/edge_sem/execution.py")
    elif damage=="extra_change":data["runtime"]["scripts/edge_sem/trainer.py"]="changed"
    elif damage=="snapshot":Path(next(iter(data["runtime_snapshots"].values()))["path"]).write_text("bad")
    elif damage=="current_runtime":monkeypatch.setattr(runtime,"runtime_refs",lambda:{})
    elif damage=="test_log":
        tests=json.loads(Path(data["tests"]["path"]).read_text())
        Path(tests["results"][0]["log"]["path"]).write_text("changed")
    elif damage=="request":Path(data["request"]["path"]).write_text("{}")
    else:Path(tmp_path/"receipt.json").write_text("{}")
    if damage not in ("seal",):
        sealed(revision,data,"revision")
    with pytest.raises((ValueError,PermissionError,KeyError)):
        runtime.verify_execution_revision(path,plan,revision,True)


def test_event_log_failure_cannot_disappear_in_background_thread(tmp_path, monkeypatch):
    error=subprocess.TimeoutExpired(["nvidia-smi"],5)
    monitor,calls=resource(tmp_path,monkeypatch,[error,None])
    (tmp_path/"events.jsonl").unlink()
    (tmp_path/"events.jsonl").mkdir()
    class Tick:
        def wait(self, seconds):return False
    monitor.done=Tick()
    monitor._watch()
    assert len(calls)==1
    assert monitor.terminal_sampling_failure["stage"]=="sampling_event_persistence"
    with pytest.raises(MemoryGateError):monitor.check()
    assert len(calls)==1
