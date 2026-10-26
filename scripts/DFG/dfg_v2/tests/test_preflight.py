"""Preflight tests use synthetic readings and mocked CUDA, never real fits."""
import copy
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

from scripts.DFG.dfg_v2.experiment import preflight as p


def reading(free=3500., used=476., total=4096., uuid="GPU-test"):
    return dict(uuid=uuid, total_mib=total, free_mib=free, used_mib=used,
                unaccounted_mib=total-free-used, raw="synthetic",
                command=list(p.QUERY_ARGV), unix_seconds=1.,
                monotonic_seconds=p.time.monotonic(), elapsed_seconds=0.)


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(p, "_cuda_initialized", lambda: False)
    monkeypatch.setattr(p, "query_baseline", lambda: reading())


def test_default_policy_exact_and_configurable_baseline_only():
    assert p.validate_policy(p.DEFAULT_PREFLIGHT_POLICY) == p.DEFAULT_PREFLIGHT_POLICY
    override = dict(p.DEFAULT_PREFLIGHT_POLICY, baseline_minimum_free_mib=3100)
    assert p.validate_policy(override) == override
    assert p.validate_policy(override) is not override


@pytest.mark.parametrize("damage", [
    {"baseline_minimum_free_mib": 0}, {"baseline_minimum_free_mib": float("nan")},
    {"baseline_minimum_free_mib": float("inf")}, {"baseline_minimum_free_mib": True},
    {"baseline_minimum_free_mib": "3000"}, {"running_minimum_free_mib": 99},
    {"sampling_seconds": 2}, {"process_scope": "reused"}, {"version": "other"},
    {"extra": 1},
])
def test_policy_rejects_unregistered_changes(damage):
    with pytest.raises(ValueError):
        p.validate_policy(dict(p.DEFAULT_PREFLIGHT_POLICY, **damage))


def test_query_raw_fields_retained_and_no_torch_import(monkeypatch):
    commands = []
    def command(argv, **kwargs):
        commands.append((argv, kwargs))
        return b"GPU-1234, 4096, 464, 3512\n"
    monkeypatch.setattr(p.subprocess, "check_output", command)
    result = p.query_baseline()
    assert (result["total_mib"], result["used_mib"], result["free_mib"]) == (4096, 464, 3512)
    assert result["unaccounted_mib"] == 120
    assert commands[0][0] == p.QUERY_ARGV
    assert commands[0][1]["timeout"] == 5
    assert result["raw"] == "GPU-1234, 4096, 464, 3512"


@pytest.mark.parametrize("raw", [
    b"", b"GPU-1,4096,5,4091\nGPU-2,4096,5,4091\n",
    b"GPU-1,4096,5", b"GPU-1,N/A,5,6", b"GPU-1,4096,nan,6",
    b"GPU-1,4096,5,inf", b"GPU-1,4096,-1,6", b"GPU-1,4096,1,5000",
    b"GPU-1,0,0,0", b"N/A,4096,1,4000",
])
def test_query_rejects_unavailable_multi_gpu_nonfinite_or_invalid(monkeypatch, raw):
    monkeypatch.setattr(p.subprocess, "check_output", lambda *a, **kw: raw)
    with pytest.raises(ValueError):
        p.query_baseline()


def test_module_import_and_baseline_never_import_torch_or_dgl():
    script = """
import builtins
real_import = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in ('torch', 'dgl'):
        raise AssertionError('CUDA framework import forbidden')
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded
from scripts.DFG.dfg_v2.experiment import preflight
preflight.subprocess.check_output=lambda *a, **kw: b'GPU-test,4096,464,3512'
assert preflight.query_baseline()['free_mib']==3512
assert not preflight._cuda_initialized()
"""
    completed = subprocess.run([sys.executable, "-B", "-c", script],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert completed.returncode == 0, completed.stderr.decode()


def test_passed_receipt_bound_to_job_plan_pid_argv_and_no_self_hash(tmp_path, quiet):
    result = p.run_preflight({"id": "task/0/1/G0"}, "a"*64, tmp_path,
                             p.DEFAULT_PREFLIGHT_POLICY, argv=["run", "--only", "task"])
    assert result["status"] == "passed"
    assert result["cuda_initialized_before"] is False
    assert result["cuda_initialized_after"] is False
    saved = Path(result["receipt_ref"]["path"])
    assert saved.name == "preflight_001.json"
    assert result["receipt_ref"]["sha256"] == hashlib.sha256(saved.read_bytes()).hexdigest()
    body = json.loads(saved.read_text())
    assert "receipt_ref" not in body
    assert body["argv"] == ["run", "--only", "task"]
    assert body["job"] == {"id": "task/0/1/G0"}
    assert body["plan_sha256"] == "a"*64
    assert body["pid"] > 0
    before = saved.read_bytes()
    again = p.run_preflight({}, "a"*64, tmp_path, p.DEFAULT_PREFLIGHT_POLICY)
    assert again["receipt_ref"]["path"].endswith("preflight_002.json")
    assert saved.read_bytes() == before


def test_exact_baseline_threshold_passes(tmp_path, quiet, monkeypatch):
    monkeypatch.setattr(p, "query_baseline", lambda: reading(free=3000))
    assert p.run_preflight({}, "a"*64, tmp_path,
                           p.DEFAULT_PREFLIGHT_POLICY)["status"] == "passed"


def test_insufficient_memory_receipt_blocks_without_attempt(tmp_path, quiet, monkeypatch):
    monkeypatch.setattr(p, "query_baseline", lambda: reading(free=2999))
    with pytest.raises(p.PreflightBlocked) as caught:
        p.run_preflight({}, "a"*64, tmp_path, p.DEFAULT_PREFLIGHT_POLICY)
    assert caught.value.receipt["status"] == "preflight_blocked"
    assert sorted(x.name for x in tmp_path.iterdir()) == ["preflight_001.json"]


@pytest.mark.parametrize("failure", [FileNotFoundError("nvidia-smi"),
                                    subprocess.TimeoutExpired("nvidia-smi", 5),
                                    ValueError("bad reading")])
def test_query_error_receipt_fail_closed(tmp_path, quiet, monkeypatch, failure):
    def broken():
        raise failure
    monkeypatch.setattr(p, "query_baseline", broken)
    with pytest.raises(p.PreflightError) as caught:
        p.run_preflight({}, "a"*64, tmp_path, p.DEFAULT_PREFLIGHT_POLICY)
    assert caught.value.receipt["status"] == "preflight_error"
    assert caught.value.receipt["baseline"] is None
    assert caught.value.receipt["error_type"] == type(failure).__name__


def test_reused_cuda_process_rejected_before_query(tmp_path, quiet, monkeypatch):
    monkeypatch.setattr(p, "_cuda_initialized", lambda: True)
    monkeypatch.setattr(p, "query_baseline", lambda: pytest.fail("must not query"))
    with pytest.raises(p.PreflightError, match="already initialized"):
        p.run_preflight({}, "a"*64, tmp_path, p.DEFAULT_PREFLIGHT_POLICY)


def test_unexpected_cuda_initialization_during_preflight_rejected(tmp_path, quiet, monkeypatch):
    states = iter([False, True])
    monkeypatch.setattr(p, "_cuda_initialized", lambda: next(states))
    with pytest.raises(p.PreflightError, match="during preflight"):
        p.run_preflight({}, "a"*64, tmp_path, p.DEFAULT_PREFLIGHT_POLICY)


def test_invalid_plan_identity_writes_error(tmp_path, quiet):
    with pytest.raises(p.PreflightError, match="SHA256"):
        p.run_preflight({}, "wrong", tmp_path, p.DEFAULT_PREFLIGHT_POLICY)


def fake_context_frameworks(monkeypatch):
    actions = []
    class FakeGraph:
        def to(self, device):
            actions.append(("dgl.to", device))
            return self
    cuda = types.SimpleNamespace(
        set_device=lambda device: actions.append(("set_device", device)),
        init=lambda: actions.append(("init",)),
        synchronize=lambda device: actions.append(("sync", device)),
        empty_cache=lambda: actions.append(("empty_cache",)),
        memory_allocated=lambda device: 0,
        memory_reserved=lambda device: 0,
    )
    fake_torch = types.SimpleNamespace(
        cuda=cuda, float32="float32",
        empty=lambda *a, **kw: actions.append(("empty", a, kw)),
    )
    fake_dgl = types.SimpleNamespace(
        graph=lambda edges, num_nodes: (actions.append(("graph", edges, num_nodes)) or FakeGraph()))
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "dgl", fake_dgl)
    monkeypatch.setattr(p, "_cuda_initialized", lambda: False)
    return actions


def test_context_warmup_no_random_draws_and_preserves_raw_differences(monkeypatch):
    actions = fake_context_frameworks(monkeypatch)
    monkeypatch.setattr(p, "query_baseline", lambda: reading(free=3100, used=876))
    result = p.initialize_context(reading(), "cuda:0")
    assert result["free_decrease_mib"] == 400
    assert result["used_increase_mib"] == 400
    assert result["torch_reserved_mib"] == 0
    assert [item[0] for item in actions] == [
        "set_device", "init", "empty", "graph", "dgl.to", "sync", "empty_cache"]
    assert actions[2][1] == (1,)
    assert actions[3] == ("graph", ([0], [0]), 1)
    assert result["caveats"] == p.CAVEATS


def test_context_rejects_changed_device(monkeypatch):
    fake_context_frameworks(monkeypatch)
    monkeypatch.setattr(p, "query_baseline", lambda: reading(uuid="GPU-other"))
    with pytest.raises(ValueError, match="identity"):
        p.initialize_context(reading())


def test_context_rejects_preexisting_cuda(monkeypatch):
    monkeypatch.setattr(p, "_cuda_initialized", lambda: True)
    with pytest.raises(ValueError, match="boundary"):
        p.initialize_context(reading())


def make_resource(tmp_path, monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda, "memory_allocated", lambda *a: 1024**2*200)
    monkeypatch.setattr(torch.cuda, "memory_reserved", lambda *a: 1024**2*256)
    monkeypatch.setattr(torch.cuda, "max_memory_allocated", lambda *a: 1024**2*220)
    monkeypatch.setattr(torch.cuda, "max_memory_reserved", lambda *a: 1024**2*300)
    baseline = reading()
    context = dict(baseline=baseline, after_initialization=reading(free=3100),
                   free_decrease_mib=400, used_increase_mib=400, caveats=list(p.CAVEATS))
    return p.make_observed_resources("cuda:0", baseline, context, tmp_path/"samples.jsonl")


def test_sample_pairing_summary_and_old_gate_preserved(tmp_path, monkeypatch):
    resource = make_resource(tmp_path, monkeypatch)
    monkeypatch.setattr(p, "query_baseline", lambda: reading(free=500))
    resource.check()
    result = resource.summary()
    assert result["minimum_free_mib"] == 500
    assert result["peak_reserved_mib"] == 300
    assert result["non_torch_residual_estimate_mib"] == 4096-500-300
    assert result["context_adjusted_residual_estimate_mib"] == 4096-500-300-400
    assert result["whole_card_sampling_seconds"] == .5
    row = json.loads((tmp_path/"samples.jsonl").read_text())
    assert row["non_torch_residual_estimate_mib"] == 4096-500-256
    assert row["torch_allocated_mib"] == 200
    assert row["pairing_window_seconds"] >= 0
    assert result["paired_sample_count"] == 1
    assert "unattributed" in result["residual_attribution"]
    assert result["raw_samples_sha256"] == hashlib.sha256(
        (tmp_path/"samples.jsonl").read_bytes()).hexdigest()


def test_running_memory_below100_stops_exact100_passes(tmp_path, monkeypatch):
    from scripts.DFG.dfg_v2.experiment.resources import MemoryGateError
    resource = make_resource(tmp_path, monkeypatch)
    monkeypatch.setattr(p, "query_baseline", lambda: reading(free=100))
    resource.check()
    monkeypatch.setattr(p, "query_baseline", lambda: reading(free=99))
    with pytest.raises(MemoryGateError, match="below"):
        resource.check()
    assert resource.summary()["minimum_free_mib"] == 99


def test_sampling_error_fails_closed_and_is_recorded(tmp_path, monkeypatch):
    from scripts.DFG.dfg_v2.experiment.resources import MemoryGateError
    resource = make_resource(tmp_path, monkeypatch)
    def broken():
        raise ValueError("probe unavailable")
    monkeypatch.setattr(p, "query_baseline", broken)
    with pytest.raises(MemoryGateError, match="measurement failed"):
        resource.check()
    assert resource.summary()["sampling_errors"] == ["probe unavailable"]
    assert resource.summary()["non_torch_residual_estimate_mib"] is None


def test_sampling_changed_gpu_fails_closed(tmp_path, monkeypatch):
    from scripts.DFG.dfg_v2.experiment.resources import MemoryGateError
    resource = make_resource(tmp_path, monkeypatch)
    monkeypatch.setattr(p, "query_baseline", lambda: reading(uuid="GPU-other"))
    with pytest.raises(MemoryGateError):
        resource.check()
    assert "identity" in resource.errors[0]


def test_raw_sample_file_cannot_be_overwritten(tmp_path, monkeypatch):
    make_resource(tmp_path, monkeypatch)
    with pytest.raises(FileExistsError):
        make_resource(tmp_path, monkeypatch)


def test_negative_residual_estimate_not_hidden(tmp_path, monkeypatch):
    resource = make_resource(tmp_path, monkeypatch)
    monkeypatch.setattr(p, "query_baseline", lambda: reading(free=3900))
    resource.check()
    assert resource.summary()["non_torch_residual_estimate_mib"] == -104
