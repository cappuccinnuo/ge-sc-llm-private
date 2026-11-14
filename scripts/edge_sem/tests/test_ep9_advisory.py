"""Advisory monitoring cannot block training; shared validation detects changes."""
import copy
import json
import os
import subprocess
import threading
import time
import pytest
import torch
from scripts.edge_sem import execution as ex, runtime
from scripts.edge_sem.io import ref
from scripts.DFG.dfg_v2.experiment.preflight import LOCAL_DEV_POLICY
from scripts.DFG.dfg_v2.experiment.resources import MemoryGateError


def reading():
    return dict(uuid="GPU-fixture", total_mib=4096., used_mib=3000., free_mib=1000.,
        unaccounted_mib=96., unix_seconds=time.time(), monotonic_seconds=time.monotonic(),
        elapsed_seconds=0., raw="fixture", command=["nvidia-smi"])


def monitor(tmp_path, monkeypatch, sequence):
    for name in ("memory_allocated", "memory_reserved", "max_memory_allocated", "max_memory_reserved"):
        monkeypatch.setattr(torch.cuda, name, lambda *a: 0)
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda *a: None)
    base=reading()
    context=dict(baseline=base, after_initialization=copy.deepcopy(base), free_decrease_mib=0)
    calls=[]
    def query():
        calls.append(1)
        item=sequence.pop(0) if sequence else None
        if isinstance(item, Exception): raise item
        return reading() if item is None else copy.deepcopy(item)
    result=ex.make_retrying_resources("cuda", base, context, tmp_path/"memory.jsonl",
        tmp_path/"history.jsonl", LOCAL_DEV_POLICY, tmp_path/"events.jsonl",
        query=query, advisory=True)
    result.__enter__()
    result.done.set()
    result.thread.join()
    return result, calls


def test_continuous_query_timeouts_remain_visible_without_stopping_training(tmp_path, monkeypatch):
    error=subprocess.TimeoutExpired(["nvidia-smi"], 5)
    resource,calls=monitor(tmp_path,monkeypatch,[error]*5)
    for unused in range(5):
        assert resource.sample() is False
        resource.check()
    resource.__exit__(None,None,None)
    assert len(calls)==5
    summary=resource.summary()
    assert summary["monitoring_incomplete"] and summary["query_sample_count"]==0
    assert len(resource.observations)==1
    assert resource.observations[0]["sample_kind"]=="context_boundary"
    assert ex.validate_sampling_recovery(summary,resource.observations)==dict(
        query_failures=5,recorded_gaps=5,query_samples=0)


def test_epoch_checks_and_finalization_never_launch_external_queries(tmp_path,monkeypatch):
    resource,calls=monitor(tmp_path,monkeypatch,[])
    for unused in range(100):resource.check()
    resource.__exit__(None,None,None)
    assert not calls


def test_checks_do_not_wait_for_background_query_lock(tmp_path,monkeypatch):
    resource,calls=monitor(tmp_path,monkeypatch,[])
    resource.observation_lock.acquire()
    try:
        started=time.monotonic()
        resource.check()
        assert time.monotonic()-started < .2
    finally:
        resource.observation_lock.release()
    assert not calls


def test_later_success_is_a_new_sample_not_a_relabelled_gap(tmp_path,monkeypatch):
    resource,calls=monitor(tmp_path,monkeypatch,[subprocess.TimeoutExpired(["nvidia-smi"],5),None])
    resource.sample()
    resource.check()
    resource.sample()
    summary=resource.summary()
    assert len(calls)==2 and resource.observations[1]["sample_kind"]=="query"
    assert summary["monitoring_incomplete"] is True
    assert ex.validate_sampling_recovery(summary,resource.observations)["query_samples"]==1


@pytest.mark.parametrize("error",[ValueError("malformed"),RuntimeError("allocator failed")])
def test_noncommand_integrity_errors_still_stop(tmp_path,monkeypatch,error):
    resource,calls=monitor(tmp_path,monkeypatch,[error])
    assert resource.sample() is False
    with pytest.raises(MemoryGateError):resource.check()
    with pytest.raises(ValueError):ex.validate_sampling_recovery(resource.summary(),resource.observations)
    assert len(calls)==1


def test_wrong_gpu_still_stops(tmp_path,monkeypatch):
    resource,_=monitor(tmp_path,monkeypatch,[dict(reading(),uuid="wrong")])
    resource.sample()
    with pytest.raises(MemoryGateError):resource.check()


def test_sample_persistence_error_still_stops(tmp_path,monkeypatch):
    resource,_=monitor(tmp_path,monkeypatch,[None])
    (tmp_path/"memory.jsonl").unlink()
    (tmp_path/"memory.jsonl").mkdir()
    resource.sample()
    with pytest.raises(MemoryGateError):resource.check()


@pytest.mark.parametrize("damage",["missing_gap","fake_recovery","old_sample_as_query","hide_gap","wrong_count","context_changed","lost_cycle"])
def test_incomplete_monitoring_cannot_be_reported_as_complete(tmp_path,monkeypatch,damage):
    resource,_=monitor(tmp_path,monkeypatch,[subprocess.TimeoutExpired(["nvidia-smi"],5)])
    resource.sample()
    summary=resource.summary()
    samples=copy.deepcopy(resource.observations)
    events=[json.loads(x) for x in (tmp_path/"events.jsonl").read_text().splitlines()]
    if damage=="missing_gap":events.pop()
    elif damage=="fake_recovery":events[-1]["sample_index"]=0
    elif damage=="old_sample_as_query":samples[0]["sample_kind"]="query"
    elif damage=="hide_gap":summary["monitoring_incomplete"]=False
    elif damage=="wrong_count":summary["telemetry_gaps"]=0
    elif damage=="context_changed":samples[0]["free_mib"]=999.
    else:summary["sampling_cycles"]=0
    (tmp_path/"events.jsonl").write_text("".join(json.dumps(x)+"\n" for x in events))
    summary["sampling_events"]=ref(tmp_path/"events.jsonl")
    with pytest.raises(ValueError):ex.validate_sampling_recovery(summary,samples)


def test_validation_cache_reuses_only_verified_unchanged_files(tmp_path,monkeypatch):
    p=tmp_path/"input";p.write_text("initial");expected=ref(p)
    calls=[];original=ex.checked
    def checked(value):
        calls.append(value);return original(value)
    monkeypatch.setattr(ex,"checked",checked)
    cache=ex._LoadValidation()
    assert cache.checked(expected)==p
    assert cache.checked(expected)==p
    cache.finish()
    assert len(calls)==1 and cache.hits==1


def test_validation_cache_detects_same_size_content_change_with_restored_mtime(tmp_path):
    p=tmp_path/"input";p.write_text("aaaa");expected=ref(p)
    cache=ex._LoadValidation();cache.checked(expected)
    st=p.stat();p.write_text("bbbb");os.utime(str(p),ns=(st.st_atime_ns,st.st_mtime_ns))
    with pytest.raises(ValueError):cache.checked(expected)
    with pytest.raises(ValueError):cache.finish()


def test_validation_cache_rejects_conflicting_expected_sha(tmp_path):
    p=tmp_path/"input";p.write_text("initial");expected=ref(p)
    cache=ex._LoadValidation();cache.checked(expected)
    with pytest.raises(ValueError):cache.checked(dict(expected,sha256="0"*64))


def test_historical_loader_runs_at_both_cache_boundaries(tmp_path,monkeypatch):
    p=tmp_path/"plan";p.write_text("{}");expected=ref(p)
    calls=[]
    def loader(path):
        calls.append(path);return {"fixture":True}
    monkeypatch.setattr(ex.h8,"load",loader)
    cache=ex._LoadValidation()
    assert cache.historical(expected)==cache.historical(expected)
    cache.finish()
    assert len(calls)==2


def test_historical_mutation_is_detected_at_cache_exit(tmp_path,monkeypatch):
    p=tmp_path/"plan";p.write_text("{}");expected=ref(p)
    values=iter([{"fixture":True},{"fixture":False}])
    monkeypatch.setattr(ex.h8,"load",lambda path:next(values))
    cache=ex._LoadValidation();cache.historical(expected)
    with pytest.raises(ValueError):cache.finish()
