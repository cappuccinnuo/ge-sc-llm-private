"""Approved local policy tests: mocked CUDA only, no fitting or allocation."""
import copy
import json

import pytest

from scripts.DFG.dfg_v2.experiment import local_dev as local
from scripts.DFG.dfg_v2.experiment import preflight as p
from scripts.DFG.dfg_v2.experiment import precision_gpu as pg
from scripts.DFG.dfg_v2.experiment.resources import MemoryGateError
from scripts.DFG.dfg_v2.tests.test_preflight import reading
from scripts.DFG.dfg_v2.tests.test_precision_gpu import _pilot_result


def write_history(path, seconds):
    path.write_text("".join(json.dumps(dict(epoch=i, seconds=v))+"\n"
                            for i, v in enumerate(seconds)), encoding="utf8")


def resource(tmp_path, monkeypatch, local_mode=True):
    import torch
    for name, value in (("memory_allocated", 200), ("memory_reserved", 256),
                        ("max_memory_allocated", 220), ("max_memory_reserved", 300)):
        monkeypatch.setattr(torch.cuda, name, lambda *a, v=value: v*1024**2)
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda *a: None)
    baseline = reading()
    context = dict(baseline=baseline, after_initialization=reading(free=3100),
                   free_decrease_mib=400, used_increase_mib=400)
    extra = (dict(policy=p.LOCAL_DEV_POLICY, history_path=tmp_path/"history.jsonl")
             if local_mode else {})
    return p.make_observed_resources("cuda:0", baseline, context,
                                     tmp_path/"samples.jsonl", **extra)


def test_local_policy_registered_separately_with_fixed_baseline_and_warning():
    assert p.validate_policy(p.LOCAL_DEV_POLICY) == p.LOCAL_DEV_POLICY
    assert p.DEFAULT_PREFLIGHT_POLICY["version"] == "dfg-v2-vram-preflight-v1"
    assert p.DEFAULT_PREFLIGHT_POLICY["running_minimum_free_mib"] == 100
    assert dict(p.LOCAL_DEV_POLICY, version=p.DEFAULT_PREFLIGHT_POLICY["version"]) == p.DEFAULT_PREFLIGHT_POLICY


@pytest.mark.parametrize("damage", [
    {"baseline_minimum_free_mib": 2999}, {"baseline_minimum_free_mib": 3001},
    {"running_minimum_free_mib": 0}, {"running_minimum_free_mib": 99},
    {"baseline_minimum_free_mib": True}, {"sampling_seconds": 1},
    {"process_scope": "multiple_jobs"}, {"version": "local_dev_v2"}, {"extra": 1},
])
def test_local_policy_rejects_unregistered_relaxation(damage):
    with pytest.raises(ValueError):
        p.validate_policy(dict(p.LOCAL_DEV_POLICY, **damage))


@pytest.mark.parametrize("free,passes", [(2999,False),(3000,True),(3500,True)])
def test_local_preflight_keeps_3000_baseline(tmp_path,monkeypatch,free,passes):
    monkeypatch.setattr(p,"_cuda_initialized",lambda:False)
    monkeypatch.setattr(p,"query_baseline",lambda:reading(free=free))
    if passes:
        receipt=p.run_preflight({},"a"*64,tmp_path,p.LOCAL_DEV_POLICY)
        assert receipt["status"]=="passed" and receipt["version"]=="local_dev_v1"
    else:
        with pytest.raises(p.PreflightBlocked):
            p.run_preflight({},"a"*64,tmp_path,p.LOCAL_DEV_POLICY)
        assert not list(tmp_path.glob("attempt*"))


@pytest.mark.parametrize("free,tight", [(0,True),(76,True),(99,True),(100,False),(500,False)])
def test_local_low_free_is_advisory_with_raw_readings(tmp_path,monkeypatch,capsys,free,tight):
    guard=resource(tmp_path,monkeypatch)
    monkeypatch.setattr(p,"query_baseline",lambda:reading(free=free))
    guard.check()
    summary=guard.summary()
    assert summary["minimum_free_mib"]==free
    assert summary["memory_tight"] is tight
    assert summary["epoch_timing"]["status"]=="insufficient_first_three_epochs"
    assert summary["epoch_timing"]["epoch_seconds"]==[]
    assert ("memory_tight=true" in capsys.readouterr().out) is tight


def test_old_gate_unchanged_and_local_does_not_hide_transient_minimum(tmp_path,monkeypatch,capsys):
    (tmp_path/"old").mkdir();(tmp_path/"local").mkdir()
    old=resource(tmp_path/"old",monkeypatch,False)
    new=resource(tmp_path/"local",monkeypatch)
    monkeypatch.setattr(p,"query_baseline",lambda:reading(free=76))
    with pytest.raises(MemoryGateError):
        old.check()
    new.sample()  # Background sample saw a low point before the next check.
    monkeypatch.setattr(p,"query_baseline",lambda:reading(free=500))
    new.check();new.check()
    assert new.summary()["memory_tight"] is True
    assert capsys.readouterr().out.count("memory_tight=true")==1


def test_local_measurement_failure_still_stops_with_evidence(tmp_path,monkeypatch):
    guard=resource(tmp_path,monkeypatch)
    def fail():
        raise ValueError("synthetic telemetry error")
    monkeypatch.setattr(p,"query_baseline",fail)
    with pytest.raises(MemoryGateError,match="measurement failed"):
        guard.check()
    assert guard.summary()["sampling_errors"]==["synthetic telemetry error"]


def test_local_does_not_swallow_oom_and_preserves_partial_history(tmp_path,monkeypatch):
    guard=resource(tmp_path,monkeypatch)
    monkeypatch.setattr(p,"query_baseline",lambda:reading(free=50))
    write_history(tmp_path/"history.jsonl",[10,12])
    with pytest.raises(RuntimeError,match="CUDA out of memory"):
        with guard:
            guard.check()
            raise RuntimeError("CUDA out of memory: synthetic")
    summary=guard.summary()
    assert summary["memory_tight"]
    assert summary["epoch_timing"]["epoch_seconds"]==[10,12]
    assert summary["epoch_timing"]["status"]=="insufficient_first_three_epochs"


@pytest.mark.parametrize("durations,status,baseline,warnings",[
    ([], "insufficient_first_three_epochs", None, []),
    ([10], "insufficient_first_three_epochs", None, []),
    ([100,1], "insufficient_first_three_epochs", None, []),
    ([100,10,11], "baseline_ready_no_later_epochs", 11, []),
    ([10,11,12,22], "evaluated", 11, []),  # strict greater than, not >=
    ([10,11,12,22.1,8,23], "evaluated", 11, [3,5]),
])
def test_fixed_first_three_median_and_later_epochs_only(durations,status,baseline,warnings):
    summary=local.timing_summary([dict(epoch=i,seconds=v) for i,v in enumerate(durations)])
    assert summary["status"]==status
    assert summary["baseline_first_three_median_seconds"]==baseline
    assert summary["possible_memory_spill_epochs"]==warnings
    assert summary["possible_memory_spill"] is bool(warnings)


@pytest.mark.parametrize("rows",[
    [{"epoch":0,"seconds":float("nan")}], [{"epoch":0,"seconds":-1}],
    [{"epoch":0,"seconds":float("inf")}], [{"epoch":0,"seconds":True}],
    [{"epoch":1,"seconds":10}], [{"epoch":False,"seconds":10}],
])
def test_timing_rejects_corrupt_history(rows):
    with pytest.raises(ValueError):
        local.timing_summary(rows)


def test_live_timing_alert_once_and_does_not_claim_paging(tmp_path,monkeypatch,capsys):
    guard=resource(tmp_path,monkeypatch)
    monkeypatch.setattr(p,"query_baseline",lambda:reading(free=200))
    write_history(tmp_path/"history.jsonl",[10,11,12])
    guard.check()
    assert not guard.summary()["possible_memory_spill"]
    write_history(tmp_path/"history.jsonl",[10,11,12,25])
    guard.check();guard.check()
    output=capsys.readouterr().out
    assert output.count("possible_memory_spill")==1
    assert "does not prove paging" in output
    assert guard.summary()["epoch_timing"]["possible_memory_spill_epochs"]==[3]


def test_raw_history_and_samples_independently_reconstruct_flags(tmp_path,monkeypatch):
    guard=resource(tmp_path,monkeypatch)
    monkeypatch.setattr(p,"query_baseline",lambda:reading(free=76))
    write_history(tmp_path/"history.jsonl",[10,11,12,25])
    guard.check()
    summary=dict(guard.summary(),resource_policy=copy.deepcopy(p.LOCAL_DEV_POLICY))
    samples=[json.loads(line) for line in (tmp_path/"samples.jsonl").read_text().splitlines()]
    local.validate_local_resource_summary(summary,p.LOCAL_DEV_POLICY,tmp_path/"history.jsonl",samples)
    for key,value in (("memory_tight",False),("possible_memory_spill",False),
                      ("minimum_free_mib",100)):
        bad=dict(summary);bad[key]=value
        with pytest.raises(ValueError):
            local.validate_local_resource_summary(bad,p.LOCAL_DEV_POLICY,tmp_path/"history.jsonl",samples)
    write_history(tmp_path/"history.jsonl",[10,11,12,24])
    with pytest.raises(ValueError,match="timing"):
        local.validate_local_resource_summary(summary,p.LOCAL_DEV_POLICY,tmp_path/"history.jsonl",samples)


def pilot_local():
    result=_pilot_result()
    result["resources"].update(resource_policy=copy.deepcopy(p.LOCAL_DEV_POLICY),
        minimum_free_mib=76,memory_tight=True,possible_memory_spill=False,
        epoch_timing=local.timing_summary([dict(epoch=i,seconds=10) for i in range(4)]))
    return result


def test_pilot_local_requires_explicit_policy_and_preserves_old_gate():
    result=pilot_local()
    assert not pg.audit_pilot_result(result)["passed"]
    audit=pg.audit_pilot_result(result,resource_policy=p.LOCAL_DEV_POLICY)
    assert audit["passed"] and audit["resources"]["memory_tight"]
    assert audit["training_supported_canonical_count"]==1
    assert audit["heldout_only_canonical_count"]==1


@pytest.mark.parametrize("issue",["reload","outer","gradient","heldout","missing_epoch","policy","timing","flag"])
def test_local_pilot_keeps_all_numerical_and_semantic_acceptance(issue):
    result=pilot_local()
    if issue=="reload":result["checkpoint_roundtrip_exact"]["outer_test"]["last"]=False
    elif issue=="outer":result["outer_supervision_used_in_optimization"]=True
    elif issue=="gradient":result["gradient_audit"]["epochs"][0]["v2_relations"][0]["message_gradient_l1"]=0
    elif issue=="heldout":result["gradient_audit"]["epochs"][0]["v2_relations"][1]["message_gradient_l1"]=.2
    elif issue=="missing_epoch":result["gradient_audit"]["epochs"]=[]
    elif issue=="policy":result["resources"]["resource_policy"]=p.DEFAULT_PREFLIGHT_POLICY
    elif issue=="timing":result["resources"]["epoch_timing"]["baseline_first_three_median_seconds"]=3
    else:result["resources"]["memory_tight"]=False
    assert not pg.audit_pilot_result(result,p.LOCAL_DEV_POLICY)["passed"]


def test_local_factory_requires_history_and_original_threshold(tmp_path,monkeypatch):
    baseline=reading()
    context=dict(baseline=baseline,after_initialization=reading(free=3100))
    with pytest.raises(ValueError,match="history"):
        p.make_observed_resources("cuda:0",baseline,context,tmp_path/"raw",
                                  policy=p.LOCAL_DEV_POLICY)
    with pytest.raises(ValueError,match="100"):
        p.make_observed_resources("cuda:0",baseline,context,tmp_path/"raw",
                                  policy=p.LOCAL_DEV_POLICY,history_path=tmp_path/"h",minimum_free_mib=0)
