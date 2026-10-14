"""Recovery/locking only; fake workers do not create a model or use CUDA."""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts.DFG.experiments.e23_pilot import control

JOB={"task_id":"reentrancy_author_contract","variant":"E2"}
PLAN={"jobs":[JOB]}
SCORES={"cv_validation":{"best":{"buggy_f1":50.0}}}


@pytest.fixture
def fake_plan(monkeypatch):
    monkeypatch.setattr(control,"verify_plan",lambda output:PLAN)
    monkeypatch.setattr(control,"verify_fit",lambda folder,job,mode,plan:SCORES)


def parent(output):
    path=control.job_dir(output,JOB,"smoke")
    path.mkdir(parents=True,exist_ok=True)
    return path


@pytest.mark.parametrize("suffix",[".log",".failure.json",".execution.json",".unknown.partial"])
def test_attempt_before_directory_exists_is_counted_once(tmp_path,fake_plan,suffix):
    base=parent(tmp_path)/"attempt_001"
    base.with_suffix(suffix).write_text("evidence")
    assert not base.exists()
    success,attempts=control.existing_success(tmp_path,JOB,"smoke",PLAN)
    assert success is None and attempts==[base]


def test_directory_and_all_sidecars_share_one_number_and_gaps_are_retained(tmp_path):
    root=parent(tmp_path)
    (root/"attempt_002").mkdir()
    for name in ("attempt_002.log","attempt_002.failure.json","attempt_002.execution.json","attempt_009.log"):
        (root/name).write_text("evidence")
    assert control.attempt_inventory(root)==[root/"attempt_002",root/"attempt_009"]


@pytest.mark.parametrize("name",["attempt_bad.log","attempt_000.log","attempt_01.log","attempt_001oops.log"])
def test_ambiguous_attempt_names_fail_closed(tmp_path,name):
    (tmp_path/name).write_text("evidence")
    with pytest.raises(ValueError):control.attempt_inventory(tmp_path)


def test_previous_predirectory_failure_blocks_auto_retry_then_explicit_retry_preserves_evidence(tmp_path,fake_plan,monkeypatch):
    called=[]
    def fake_worker(cmd,**kwargs):
        attempt=Path(cmd[cmd.index("--attempt")+1]);called.append(attempt.name)
        if len(called)==1:
            attempt.with_suffix(".failure.json").write_text(json.dumps({"exception":"CUDA unavailable"}))
            return SimpleNamespace(returncode=1)
        attempt.mkdir();(attempt/"receipt.json").write_text("{}")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(control.subprocess,"run",fake_worker)
    with pytest.raises(RuntimeError,match="Worker failed"):
        control.execute(tmp_path,"smoke")
    root=parent(tmp_path);attempt=root/"attempt_001"
    assert not attempt.exists()
    before={p.name:p.read_bytes() for p in root.iterdir()}
    with pytest.raises(RuntimeError,match="explicitly retry"):
        control.execute(tmp_path,"smoke")
    assert called==["attempt_001"]
    assert control.execute(tmp_path,"smoke",retry=JOB["task_id"]+"/E2")
    assert called==["attempt_001","attempt_002"]
    assert all((root/name).read_bytes()==content for name,content in before.items())
    assert json.loads((root/"attempt_001.execution.json").read_text())["returncode"]==1
    assert json.loads((root/"attempt_002.execution.json").read_text())["returncode"]==0
    assert control.execute(tmp_path,"smoke")
    assert len(called)==2  # successful attempt is verified/reused, not trained again


def test_retry_uses_maximum_attempt_number_not_attempt_count(tmp_path,fake_plan,monkeypatch):
    root=parent(tmp_path)
    (root/"attempt_007.log").write_text("interrupted")
    calls=[]
    def fake_worker(cmd,**kwargs):
        attempt=Path(cmd[cmd.index("--attempt")+1]);calls.append(attempt.name)
        attempt.mkdir();(attempt/"receipt.json").write_text("{}")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(control.subprocess,"run",fake_worker)
    control.execute(tmp_path,"smoke",retry=JOB["task_id"]+"/E2")
    assert calls==["attempt_008"]
    assert (root/"attempt_007.log").read_text()=="interrupted"


def test_success_is_verified_before_reuse_and_multiple_successes_rejected(tmp_path,fake_plan,monkeypatch):
    root=parent(tmp_path);verified=[]
    monkeypatch.setattr(control,"verify_fit",lambda folder,*args:verified.append(folder))
    for n in (1,2):
        path=root/("attempt_%03d"%n);path.mkdir();(path/"receipt.json").write_text("{}")
    with pytest.raises(ValueError,match="Multiple successful fits"):
        control.existing_success(tmp_path,JOB,"smoke",PLAN)
    assert verified==[root/"attempt_001",root/"attempt_002"]


@pytest.mark.parametrize("sidecar",["failure","execution"])
def test_conflicting_success_and_failed_execution_not_accepted(tmp_path,fake_plan,sidecar):
    path=parent(tmp_path)/"attempt_001";path.mkdir();(path/"receipt.json").write_text("{}")
    path.with_suffix("."+sidecar+".json").write_text(json.dumps({"returncode":1}))
    with pytest.raises(ValueError,match="Conflicting success"):
        control.existing_success(tmp_path,JOB,"smoke",PLAN)


def test_corrupt_success_receipt_is_not_reused(tmp_path,fake_plan,monkeypatch):
    path=parent(tmp_path)/"attempt_001";path.mkdir();(path/"receipt.json").write_text("{}")
    def invalid(*args):raise ValueError("Checkpoint integrity failed")
    monkeypatch.setattr(control,"verify_fit",invalid)
    with pytest.raises(ValueError,match="Checkpoint integrity"):
        control.execute(tmp_path,"smoke")


def test_full_fit_requires_smoke_success_and_retry_identity_must_exist(tmp_path,fake_plan,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError("Must not launch a worker")
    monkeypatch.setattr(control.subprocess,"run",forbidden)
    with pytest.raises(ValueError,match="smoke checks"):
        control.execute(tmp_path,"full")
    with pytest.raises(ValueError,match="Retry identity"):
        control.execute(tmp_path,"smoke",retry="unknown/E2")


def test_real_flock_excludes_another_process_and_keeps_stable_inode(tmp_path):
    # Minimal child probes the OS lock only; imports neither torch nor the project.
    script="""import fcntl,sys
f=open(sys.argv[1],'a+')
try: fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError: sys.exit(7)
sys.exit(0)
"""
    lock=tmp_path/".execution.lock"
    with control.execution_lock(tmp_path):
        inode=lock.stat().st_ino
        result=subprocess.run([sys.executable,"-B","-c",script,str(lock)])
        assert result.returncode==7
        with pytest.raises(RuntimeError,match="Another controller"):
            with control.execution_lock(tmp_path):pass
    assert lock.exists() and lock.stat().st_ino==inode
    assert subprocess.run([sys.executable,"-B","-c",script,str(lock)]).returncode==0
    with control.execution_lock(tmp_path):assert lock.stat().st_ino==inode


def test_execute_holds_lock_for_entire_workflow_and_releases_on_exception(tmp_path,monkeypatch):
    def body(*args):
        with pytest.raises(RuntimeError,match="Another controller"):
            with control.execution_lock(tmp_path):pass
        raise ValueError("worker failed")
    monkeypatch.setattr(control,"_execute_locked",body)
    with pytest.raises(ValueError,match="worker failed"):
        control.execute(tmp_path,"smoke")
    with control.execution_lock(tmp_path):pass
