"""RSS guard tests use fake processes or a tiny sleeping subprocess, not fits."""
import copy
import json
import subprocess
import sys

import pytest

from scripts.DFG.dfg_v2.experiment import precision_guard as guard

MEMORY = dict(MemTotal_bytes=8*1024**3, MemAvailable_bytes=7*1024**3,
              SwapTotal_bytes=2*1024**3, SwapFree_bytes=2*1024**3)


class Clock:
    def __init__(self):
        self.value = 0.

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class Process:
    pid = 456

    def __init__(self, exit_code=None, kill_needed=False):
        self.returncode = exit_code
        self.actions = []
        self.kill_needed = kill_needed

    def poll(self):
        return self.returncode

    def terminate(self):
        self.actions.append("terminate")
        if not self.kill_needed:
            self.returncode = -15

    def kill(self):
        self.actions.append("kill")
        self.returncode = -9

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("fake", timeout)
        return self.returncode


@pytest.mark.parametrize("kill_needed", [False, True])
def test_rss_over_limit_terminates_and_has_auditable_sample(kill_needed):
    proc, clock, rows = Process(kill_needed=kill_needed), Clock(), []
    result = guard.monitor_process(proc, rows.append,
        rss_reader=lambda pid: guard.LIMIT_BYTES+1,
        memory_reader=lambda: MEMORY, clock=clock, sleep=clock.sleep)
    assert result["samples"] == rows
    assert rows[0]["rss_bytes"] == guard.LIMIT_BYTES+1
    assert result["termination"]["triggered_sample_index"] == 0
    assert result["termination"]["reason"] == "rss_limit_exceeded"
    assert result["returncode"] == (-9 if kill_needed else -15)
    assert proc.actions == (["terminate", "kill"] if kill_needed else ["terminate"])


def test_exact_limit_is_allowed_and_poll_interval_two_seconds():
    proc, clock, rows = Process(), Clock(), []
    def sleeping(seconds):
        assert seconds == 2.
        clock.sleep(seconds)
        proc.returncode = 0
    result = guard.monitor_process(proc, rows.append, rss_reader=lambda pid: guard.LIMIT_BYTES,
        memory_reader=lambda: MEMORY, clock=clock, sleep=sleeping)
    assert result["returncode"] == 0 and result["termination"] is None
    assert result["elapsed_seconds"] == 2. and not proc.actions


@pytest.mark.parametrize("code", [-9, 1, 0])
def test_external_exit_is_not_script_memory_stop(code):
    result = guard.monitor_process(Process(exit_code=code), lambda _: None)
    assert result["returncode"] == code
    assert result["termination"] is None and result["samples"] == []


def test_monitor_error_stops_child_and_is_not_memory_skip():
    def broken(_):
        raise OSError("unreadable proc")
    proc = Process()
    result = guard.monitor_process(proc, lambda _: None, rss_reader=broken)
    assert result["termination"]["reason"] == "monitor_error"
    assert result["monitor_error"]["type"] == "OSError"
    assert proc.actions == ["terminate"]


def test_proc_disappearing_after_poll_is_a_normal_exit_race():
    proc = Process()
    def exited(_):
        proc.returncode = 1
        raise FileNotFoundError("exited")
    result = guard.monitor_process(proc, lambda _: None, rss_reader=exited)
    assert result["returncode"] == 1
    assert result["termination"] is None and result["monitor_error"] is None


def test_real_tiny_subprocess_is_terminated_not_left_running():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    result = guard.monitor_process(proc, lambda _: None,
        rss_reader=lambda _: guard.LIMIT_BYTES+1, memory_reader=lambda: MEMORY)
    assert result["returncode"] == -15 and proc.poll() == -15


def test_proc_memory_parser(tmp_path):
    path = tmp_path/"meminfo"
    path.write_text("MemTotal: 100 kB\nMemAvailable: 50 kB\nSwapTotal: 20 kB\nSwapFree: 10 kB\n")
    assert guard.read_memory(path)["MemAvailable_bytes"] == 51200
    path.write_text("MemTotal: 100 kB\n")
    with pytest.raises(ValueError, match="Missing"):
        guard.read_memory(path)


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "ROOT", tmp_path)
    monkeypatch.setattr(guard, "read_memory", lambda: MEMORY.copy())
    source = tmp_path/"old.py"
    source.write_text("# old computation")
    refs = {}
    for key in ("initial", "graph", "labels_ref", "folds", "archived_plan"):
        path = tmp_path/(key+".json")
        path.write_text("{}")
        refs[key] = guard._ref(path)
    static = dict(task_id="access_control_node", profile="G0", reducer="mean",
        fold=0, seed=1, dtype="float64", device="cpu", status="passed",
        sources={"old.py": guard._sha(source)}, **refs)
    path = tmp_path/"static.json"
    guard._write(path, static)
    return dict(plan=refs["archived_plan"]["path"], static_report=str(path),
                output=str(tmp_path/"run"), task_id="access_control_node",
                profile="G0", reducer="mean")


def fake_monitor(status="memory", trajectory_status=None):
    def monitor(proc, sink):
        rows = []
        termination = None
        code = -9
        if status == "memory":
            rows = [dict(index=0, elapsed_seconds=0., pid=proc.pid,
                         rss_bytes=guard.LIMIT_BYTES+1, mem_available_bytes=123)]
            sink(rows[0])
            termination = dict(reason="rss_limit_exceeded", triggered_sample_index=0,
                actions=[dict(signal="SIGTERM", monotonic_seconds=1.)], returncode=-15)
            code = -15
        return dict(returncode=code, samples=rows, termination=termination,
                    monitor_error=None, elapsed_seconds=1.)
    return monitor


def execute_memory_receipt(fixture, monkeypatch, trajectory_status=None):
    def popen(argv, **kwargs):
        if trajectory_status:
            folder = guard.Path(argv[argv.index("--output")+1])
            folder.mkdir()
            guard._write(folder/"trajectory.json", dict(status=trajectory_status))
        return Process(exit_code=-15)
    monkeypatch.setattr(guard.subprocess, "Popen", popen)
    monkeypatch.setattr(guard, "monitor_process", fake_monitor())
    return guard.run_guard(**fixture)


def test_memory_receipt_written_and_rechecked(fixture, monkeypatch):
    report = execute_memory_receipt(fixture, monkeypatch)
    assert report["status"] == "skipped_cpu_memory"
    assert guard.validate_guard_evidence(guard.Path(fixture["output"])/"guard.json") == report
    assert report["initial_memory"] == MEMORY and report["retry_count"] == 0
    assert report["refs"]["static_report"] == guard._ref(fixture["static_report"])


@pytest.mark.parametrize("damage", [
    "threshold", "poll", "trigger", "signal", "kernel", "returncode", "rss",
    "argv", "source", "static", "retry", "case", "sample_log", "monitor_error",
])
def test_skip_tampering_rejected(fixture, monkeypatch, damage):
    report = execute_memory_receipt(fixture, monkeypatch)
    changed = copy.deepcopy(report)
    if damage == "threshold":
        changed["limit_bytes"] += 1
    elif damage == "poll":
        changed["poll_seconds"] = 3
    elif damage == "trigger":
        changed["termination"]["triggered_sample_index"] = 100
    elif damage == "signal":
        changed["termination"]["actions"] = []
    elif damage == "kernel":
        changed["termination"]["reason"] = "unknown_sigkill"
    elif damage == "returncode":
        changed["returncode"] = 1
    elif damage == "rss":
        changed["samples"][0]["rss_bytes"] = guard.LIMIT_BYTES
    elif damage == "argv":
        changed["argv"][0] = "/fake/python"
    elif damage == "source":
        changed["sources"]["old.py"] = "wrong"
    elif damage == "static":
        changed["refs"]["static_report"]["sha256"] = "wrong"
    elif damage == "retry":
        changed["retry_count"] = 1
    elif damage == "case":
        changed["case"]["task_id"] = "reentrancy_contract"
    elif damage == "sample_log":
        guard.Path(changed["sample_log"]["path"]).write_text("{}\n")
    elif damage == "monitor_error":
        changed["monitor_error"] = {"type": "OSError"}
    with pytest.raises((ValueError, KeyError, FileNotFoundError)):
        guard.validate_guard_evidence(changed)


@pytest.mark.parametrize("trajectory_status", ["failed_trajectory_gate", "execution_error", "passed"])
def test_memory_trigger_does_not_hide_numeric_error_or_completed_report(fixture, monkeypatch, trajectory_status):
    report = execute_memory_receipt(fixture, monkeypatch, trajectory_status)
    assert report["status"] == "failed"


def test_nonmemory_sigkill_is_failure_not_skip(fixture, monkeypatch):
    monkeypatch.setattr(guard.subprocess, "Popen", lambda *a, **k: Process(exit_code=-9))
    monkeypatch.setattr(guard, "monitor_process", fake_monitor(status="kernel"))
    assert guard.run_guard(**fixture)["status"] == "failed"


def test_launch_error_keeps_failure_receipt(fixture, monkeypatch):
    def launch(*_, **__):
        raise OSError("launch failed")
    monkeypatch.setattr(guard.subprocess, "Popen", launch)
    assert guard.run_guard(**fixture)["status"] == "failed"
    assert (guard.Path(fixture["output"])/"guard.json").exists()


def test_existing_output_is_not_overwritten(fixture, monkeypatch):
    path = guard.Path(fixture["output"])
    path.mkdir()
    marker = path/"old"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        guard.run_guard(**fixture)
    assert marker.read_text() == "keep"


@pytest.mark.parametrize("case", [
    ("reentrancy_contract", "G3R", "mean"),
    ("reentrancy_contract", "G3R", "nonempty_mean"),
    ("access_control_node", "G0", "nonempty_mean"),
])
def test_guard_refuses_unplanned_cases(fixture, case):
    fixture.update(zip(("task_id", "profile", "reducer"), case))
    with pytest.raises(ValueError, match="not authorized"):
        guard.run_guard(**fixture)
    assert not guard.Path(fixture["output"]).exists()


def test_success_binds_actual_trajectory_and_static_receipt(fixture, monkeypatch):
    from scripts.DFG.dfg_v2.experiment import precision_real
    monkeypatch.setattr(precision_real, "validate_trajectory_evidence", lambda report: report)
    def launch(argv, **kwargs):
        folder = guard.Path(argv[argv.index("--output")+1])
        folder.mkdir()
        static = guard._read(fixture["static_report"])
        guard._write(folder/"trajectory.json", dict(
            status="passed", static=guard._ref(fixture["static_report"]), sources=static["sources"]))
        return Process(exit_code=0)
    def monitor(proc, sink):
        row = dict(index=0, elapsed_seconds=0., pid=proc.pid, rss_bytes=123,
                   mem_available_bytes=456)
        sink(row)
        return dict(returncode=0, samples=[row], termination=None,
                    monitor_error=None, elapsed_seconds=2.)
    monkeypatch.setattr(guard.subprocess, "Popen", launch)
    monkeypatch.setattr(guard, "monitor_process", monitor)
    report = guard.run_guard(**fixture)
    assert report["status"] == "passed"
    assert guard.validate_guard_evidence(report) == report
    changed = copy.deepcopy(report)
    changed["trajectory"]["sha256"] = "wrong"
    with pytest.raises(ValueError, match="checksum"):
        guard.validate_guard_evidence(changed)


def test_frozen_source_change_rejected_before_launch(fixture):
    source = guard.ROOT/"old.py"
    source.write_text("# changed")
    with pytest.raises(ValueError, match="source mismatch"):
        guard.run_guard(**fixture)
    assert not guard.Path(fixture["output"]).exists()


def test_guard_module_has_no_top_level_torch_or_model_import():
    import ast
    tree = ast.parse(guard.Path(guard.__file__).read_text())
    modules = [node.module for node in tree.body if isinstance(node, ast.ImportFrom)]
    modules.extend(alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names)
    assert not any(name and ("torch" in name or "precision_real" in name or "model" in name)
                   for name in modules)


def test_concurrent_kernel_sigkill_after_guard_term_is_not_memory_skip(fixture, monkeypatch):
    monkeypatch.setattr(guard.subprocess, "Popen", lambda *a, **k: Process(exit_code=-9))
    def monitor(proc, sink):
        result = fake_monitor()(proc, sink)
        result["returncode"] = -9
        result["termination"]["returncode"] = -9
        return result
    monkeypatch.setattr(guard, "monitor_process", monitor)
    report = guard.run_guard(**fixture)
    assert report["status"] == "failed"
    report["status"] = "skipped_cpu_memory"
    with pytest.raises(ValueError, match="genuine"):
        guard.validate_guard_evidence(report)


@pytest.mark.parametrize("actions,code,expected", [
    (["SIGTERM"], -15, True),
    (["SIGTERM"], -9, False),
    (["SIGTERM", "SIGKILL"], -9, True),
    (["SIGTERM", "SIGKILL"], -15, True),
    ([], -9, False),
    (["SIGTERM"], 0, False),
])
def test_only_script_recorded_kill_is_accepted(actions, code, expected):
    termination = dict(reason="rss_limit_exceeded", actions=[dict(signal=x) for x in actions])
    assert guard._script_memory_stop(termination, code) is expected
