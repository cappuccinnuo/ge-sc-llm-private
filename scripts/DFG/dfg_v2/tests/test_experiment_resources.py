"""Memory gate never changes the frozen numerical setup."""
import subprocess
import pytest
from scripts.DFG.dfg_v2.experiment.resources import Resources, MemoryGateError

def test_cpu_resource_monitor_never_queries_gpu(monkeypatch):
    monkeypatch.setattr(subprocess,"check_output",lambda *a,**k: pytest.fail("GPU query on CPU"))
    with Resources("cpu") as guard:
        guard.check()
        assert guard.summary()["minimum_free_mib"] is None

def test_low_gpu_free_memory_stops_and_retains_minimum(monkeypatch):
    readings=iter([b"90",b"200"])
    monkeypatch.setattr(subprocess,"check_output",lambda *a,**k: next(readings))
    guard=Resources("cuda:0")
    with pytest.raises(MemoryGateError,match="below"):
        guard.check()
    with pytest.raises(MemoryGateError,match="below"):
        guard.check()
    assert min(guard.samples)==90

def test_failed_current_read_does_not_reuse_stale_value(monkeypatch):
    guard=Resources("cuda:0")
    guard.samples=[1000]
    def failed(*a,**k):
        raise subprocess.TimeoutExpired("nvidia-smi",3)
    monkeypatch.setattr(subprocess,"check_output",failed)
    with pytest.raises(MemoryGateError,match="stale"):
        guard.check()
    assert guard.errors

def test_multiple_gpu_readings_cannot_silently_monitor_wrong_card(monkeypatch):
    monkeypatch.setattr(subprocess,"check_output",lambda *a,**k:b"900\n2000")
    with pytest.raises(MemoryGateError,match="measurement failed"):
        Resources("cuda:0").check()
