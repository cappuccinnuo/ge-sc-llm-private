"""Prompt 7b.3 subprocess RSS guard; no model/trainer arithmetic changes.

Only the three explicitly authorized remaining float64 trajectories may run.
The parent uses stdlib only while the child runs, avoiding a second Torch import.
Receipts bind the old static evidence, frozen computation files and raw samples.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCHEMA = "prompt7b3-cpu-rss-v1"
LIMIT_BYTES = 13 * 1024 ** 3 // 2
POLL_SECONDS = 2.0
ALLOWED_CASES = (
    ("access_control_node", "G0", "mean"),
    ("access_control_node", "G3R", "mean"),
    ("reentrancy_contract", "G0", "nonempty_mean"),
)
ROOT = Path(__file__).resolve().parents[4]


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=_sha(path))


def _checked(ref):
    path = Path(ref["path"])
    if not path.is_absolute() or _sha(path) != ref["sha256"]:
        raise ValueError("Receipt checksum/path mismatch: " + str(path))
    return path


def _write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")


def read_memory(path="/proc/meminfo"):
    result = {}
    for line in Path(path).read_text().splitlines():
        bits = line.split()
        if bits[0].rstrip(":") in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
            if len(bits) != 3 or bits[2] != "kB":
                raise ValueError("Unexpected proc memory units")
            result[bits[0].rstrip(":") + "_bytes"] = int(bits[1]) * 1024
    if set(result) != {"MemTotal_bytes", "MemAvailable_bytes", "SwapTotal_bytes", "SwapFree_bytes"}:
        raise ValueError("Missing proc memory evidence")
    return result


def read_rss(pid):
    for line in Path("/proc/{}/status".format(pid)).read_text().splitlines():
        if line.startswith("VmRSS:"):
            bits = line.split()
            if len(bits) != 3 or bits[2] != "kB":
                raise ValueError("Unexpected RSS units")
            return int(bits[1]) * 1024
    raise ValueError("Process has no RSS measurement")


def _stop(proc, reason, clock):
    actions = []
    actions.append(dict(signal="SIGTERM", monotonic_seconds=clock()))
    proc.terminate()
    try:
        returncode = proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        actions.append(dict(signal="SIGKILL", monotonic_seconds=clock()))
        proc.kill()
        returncode = proc.wait(timeout=10)
    return dict(reason=reason, actions=actions, returncode=returncode)


def _script_memory_stop(termination, returncode):
    signals = [row.get("signal") for row in termination.get("actions", [])]
    return (termination.get("reason") == "rss_limit_exceeded"
            and signals in (["SIGTERM"], ["SIGTERM", "SIGKILL"])
            and (returncode == -15 or (returncode == -9 and "SIGKILL" in signals)))


def monitor_process(proc, sample_sink, rss_reader=read_rss, memory_reader=read_memory,
                    clock=time.monotonic, sleep=time.sleep):
    """Sample the one child, terminate only it, preserve kernel/error exits."""
    started = clock()
    samples = []
    termination = None
    monitor_error = None
    while proc.poll() is None:
        try:
            row = dict(index=len(samples), elapsed_seconds=clock()-started, pid=proc.pid,
                       rss_bytes=rss_reader(proc.pid),
                       mem_available_bytes=memory_reader()["MemAvailable_bytes"])
        except Exception as exc:
            # A process may exit between poll and /proc reads; this is not OOM proof.
            if proc.poll() is not None:
                break
            monitor_error = dict(type=type(exc).__name__, message=str(exc))
            termination = _stop(proc, "monitor_error", clock)
            break
        samples.append(row)
        sample_sink(row)
        if row["rss_bytes"] > LIMIT_BYTES and proc.poll() is None:
            termination = _stop(proc, "rss_limit_exceeded", clock)
            termination["triggered_sample_index"] = row["index"]
            break
        sleep(POLL_SECONDS)
    return dict(returncode=proc.wait(), elapsed_seconds=clock()-started,
                samples=samples, termination=termination, monitor_error=monitor_error)


def _static_inputs(plan, static_path, task, profile, reducer):
    static = _read(static_path)
    if (task, profile, reducer) not in ALLOWED_CASES:
        raise ValueError("Trajectory case is not authorized by Prompt 7b.3")
    expected = dict(task_id=task, profile=profile, reducer=reducer, fold=0, seed=1,
                    dtype="float64", device="cpu", status="passed")
    if any(static.get(k) != v for k, v in expected.items()):
        raise ValueError("Static case identity/status mismatch")
    sources = static.get("sources", {})
    if not sources or any(_sha(ROOT/name) != value for name, value in sources.items()):
        raise ValueError("Frozen computation source mismatch")
    refs = {key: static[key] for key in ("initial", "graph", "labels_ref", "folds", "archived_plan")}
    for ref in refs.values():
        _checked(ref)
    plan_ref = _ref(plan)
    if plan_ref != static["archived_plan"]:
        raise ValueError("Archived plan does not match static case")
    return static, dict(plan=plan_ref, static_report=_ref(static_path), **refs), sources


def _argv(plan, output, task, profile, reducer, static_path):
    return [sys.executable, "-u", "-B", "-m",
            "scripts.DFG.dfg_v2.experiment.precision_real", "trajectory",
            "--plan", str(Path(plan).resolve()), "--output", str(Path(output).resolve()),
            "--task", task, "--profile", profile, "--reducer", reducer,
            "--static-report", str(Path(static_path).resolve())]


def run_guard(plan, output, task_id, profile, reducer, static_report):
    static, refs, sources = _static_inputs(plan, static_report, task_id, profile, reducer)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    trajectory_dir = output/"trajectory"
    argv = _argv(plan, trajectory_dir, task_id, profile, reducer, static_report)
    report = dict(schema=SCHEMA, status="running",
        case=dict(task_id=task_id, profile=profile, reducer=reducer),
        refs=refs, sources=sources, guard_source=_ref(__file__),
        argv=argv, cwd=str(ROOT), initial_memory=read_memory(),
        limit_bytes=LIMIT_BYTES, poll_seconds=POLL_SECONDS,
        started_unix_seconds=time.time(), parent_pid=os.getpid(),
        output=str(output), retry_count=0,
        environment={k: os.environ.get(k) for k in (
            "PYTHONDONTWRITEBYTECODE", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "TREE_SITTER_LIB_DIR")})
    _write(output/"guard.json", report)
    with (output/"stdout.log").open("wb") as stdout, (output/"stderr.log").open("wb") as stderr, \
            (output/"rss_samples.jsonl").open("w", encoding="utf-8") as sample_file:
        def sink(row):
            sample_file.write(json.dumps(row, sort_keys=True) + "\n")
            sample_file.flush()
        proc = None
        try:
            proc = subprocess.Popen(argv, cwd=str(ROOT), stdout=stdout, stderr=stderr,
                                    start_new_session=True)
            report["pid"] = proc.pid
            result = monitor_process(proc, sink)
            report.update(result)
        except Exception as exc:
            if proc is not None and proc.poll() is None:
                report["termination"] = _stop(proc, "guard_exception", time.monotonic)
            report.update(status="failed", launch_or_monitor_exception=dict(
                type=type(exc).__name__, message=str(exc)))
    report["sample_log"] = _ref(output/"rss_samples.jsonl")
    report["stdout"] = _ref(output/"stdout.log")
    report["stderr"] = _ref(output/"stderr.log")
    trajectory_file = trajectory_dir/"trajectory.json"
    if trajectory_file.exists():
        report["trajectory"] = _ref(trajectory_file)
    trajectory = _read(trajectory_file) if trajectory_file.exists() else {}
    if report["status"] != "failed":
        terminated = report.get("termination") or {}
        if trajectory.get("status") in ("failed_trajectory_gate", "execution_error"):
            report.update(status="failed", failure_reason="trajectory_reported_failure")
        elif (_script_memory_stop(terminated, report.get("returncode"))
              and trajectory.get("status") != "passed"):
            report["status"] = "skipped_cpu_memory"
        elif report.get("returncode") != 0 or report.get("monitor_error"):
            report.update(status="failed", failure_reason="child_or_monitor_failed")
        else:
            try:
                # Child has exited: importing Torch here cannot inflate its RSS.
                from .precision_real import validate_trajectory_evidence
                validate_trajectory_evidence(trajectory)
                if trajectory.get("sources") != sources:
                    raise ValueError("Trajectory computation binding differs")
                report["status"] = "passed"
            except Exception as exc:
                report.update(status="failed", failure_reason="invalid_trajectory",
                              validation_error=dict(type=type(exc).__name__, message=str(exc)))
    report["finished_unix_seconds"] = time.time()
    _write(output/"guard.json", report)
    validate_guard_evidence(report)
    return report


def validate_guard_evidence(report_or_path):
    """Recheck raw monitoring evidence; no unchecked skipped-status shortcut."""
    report = _read(report_or_path) if isinstance(report_or_path, (str, Path)) else report_or_path
    if (report.get("schema") != SCHEMA or report.get("status") not in (
            "passed", "failed", "skipped_cpu_memory")
            or report.get("limit_bytes") != LIMIT_BYTES or report.get("poll_seconds") != POLL_SECONDS
            or report.get("retry_count") != 0):
        raise ValueError("Invalid guard policy/status")
    case = report["case"]
    triple = tuple(case.get(k) for k in ("task_id", "profile", "reducer"))
    if triple not in ALLOWED_CASES:
        raise ValueError("Guard case not authorized")
    refs = report["refs"]
    for ref in refs.values():
        _checked(ref)
    static, expected_refs, sources = _static_inputs(
        refs["plan"]["path"], refs["static_report"]["path"], *triple)
    if refs != expected_refs or report["sources"] != sources:
        raise ValueError("Guard frozen input/source binding mismatch")
    if report["guard_source"] != _ref(__file__):
        raise ValueError("Guard implementation changed")
    output = Path(report["output"])
    expected_argv = _argv(refs["plan"]["path"], output/"trajectory", *triple,
                          static_path=refs["static_report"]["path"])
    if report["argv"] != expected_argv or report["cwd"] != str(ROOT):
        raise ValueError("Guard command mismatch")
    for key in ("sample_log", "stdout", "stderr"):
        _checked(report[key])
        expected_file = output/{"sample_log": "rss_samples.jsonl", "stdout": "stdout.log",
                               "stderr": "stderr.log"}[key]
        if report[key]["path"] != str(expected_file):
            raise ValueError("Guard log path mismatch")
    samples = [json.loads(line) for line in Path(report["sample_log"]["path"]).read_text().splitlines()]
    if samples != report.get("samples", []):
        raise ValueError("RSS samples changed")
    previous = -1
    for index, row in enumerate(samples):
        if (row["index"] != index or row["pid"] != report["pid"]
                or row["rss_bytes"] < 0 or row["mem_available_bytes"] < 0
                or row["elapsed_seconds"] < previous):
            raise ValueError("Invalid RSS sample identity/order")
        previous = row["elapsed_seconds"]
    memory = report.get("initial_memory", {})
    if set(memory) != {"MemTotal_bytes", "MemAvailable_bytes", "SwapTotal_bytes", "SwapFree_bytes"}:
        raise ValueError("Missing initial memory evidence")
    termination = report.get("termination") or {}
    trajectory = {}
    if report.get("trajectory"):
        _checked(report["trajectory"])
        if report["trajectory"]["path"] != str(output/"trajectory"/"trajectory.json"):
            raise ValueError("Guard trajectory path mismatch")
        trajectory = _read(report["trajectory"]["path"])
    if report["status"] == "skipped_cpu_memory":
        idx = termination.get("triggered_sample_index")
        actions = termination.get("actions", [])
        if (termination.get("reason") != "rss_limit_exceeded" or isinstance(idx, bool)
                or not isinstance(idx, int) or idx < 0 or idx >= len(samples)
                or samples[idx]["rss_bytes"] <= LIMIT_BYTES
                or [x.get("signal") for x in actions] not in (["SIGTERM"], ["SIGTERM", "SIGKILL"])
                or termination.get("returncode") != report.get("returncode")
                or not _script_memory_stop(termination, report.get("returncode"))
                or report.get("monitor_error")
                or trajectory.get("status") in ("failed_trajectory_gate", "execution_error", "passed")):
            raise ValueError("Memory skip lacks genuine script-termination evidence")
    elif report["status"] == "passed":
        if report.get("returncode") != 0 or termination or report.get("monitor_error") or not samples:
            raise ValueError("Successful trajectory has bad process/resource evidence")
        if any(row["rss_bytes"] > LIMIT_BYTES for row in samples):
            raise ValueError("Successful trajectory exceeded RSS limit")
        from .precision_real import validate_trajectory_evidence
        validate_trajectory_evidence(trajectory)
        if trajectory["static"] != refs["static_report"] or trajectory.get("sources") != sources:
            raise ValueError("Successful trajectory/static identity differs")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--reducer", required=True)
    parser.add_argument("--static-report", required=True)
    args = parser.parse_args()
    result = run_guard(args.plan, args.output, args.task, args.profile, args.reducer, args.static_report)
    print(json.dumps(dict(status=result["status"], case=result["case"],
                          returncode=result.get("returncode"))), flush=True)
    if result["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
