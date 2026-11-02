"""Runtime separation and archived evidence, using disposable local fixtures."""
import copy
import json
from pathlib import Path
import pytest
from scripts.node_sem import execution as ns, RUNTIME_MODULES
from scripts.node_sem.tests.test_execution import inputs
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, ref, write
REAL_RUNTIME_REFS = ns.runtime_refs


def complete(tmp_path, monkeypatch, legacy=False):
    matrix, auth = inputs(tmp_path, monkeypatch, "S1")
    path = tmp_path / "batch" / "plan.json"
    plan = ns.create(path.parent, matrix, auth)
    if legacy:
        plan["version"] = ns.LEGACY_VERSION
        authorization = read(path.parent / "authorization.json")
        authorization["version"] = ns.LEGACY_VERSION
        (path.parent / "authorization.json").write_text(json.dumps(authorization))
        plan["authorization"] = ref(path.parent / "authorization.json")
        path.write_text(json.dumps(plan))
        seal = read(path.parent / "plan.seal.json")
        seal.update(version=ns.LEGACY_VERSION, plan=ref(path))
        (path.parent / "plan.seal.json").write_text(json.dumps(seal))
    job = plan["jobs"][0]
    attempt = ns.job_directory(path.parent, job) / "attempt_001"
    attempt.mkdir(parents=True)
    start = attempt.with_suffix(".started.json")
    write(start, dict(job=job, plan=ref(path), execution_authorization=plan["authorization"],
                      runtime=copy.deepcopy(plan["runtime"])))
    artifact = attempt / "evidence.json"
    write(artifact, dict(value=1))
    receipt = dict(version=plan["version"], status="complete", job=job, plan=ref(path),
                   execution_start=ref(start), artifacts={"evidence.json": ref(artifact)["sha256"]})
    write(attempt / "receipt.json", receipt)
    if not legacy:
        write(attempt / "receipt.seal.json", dict(
            version=ns.VERSION, plan=ref(path), receipt=ref(attempt / "receipt.json")))
    return path, plan, job, attempt


def test_runtime_module_list_ignores_feature_producer_and_requires_files(tmp_path, monkeypatch):
    monkeypatch.setattr(ns, "ROOT", tmp_path)
    monkeypatch.setattr(ns, "_code_refs", lambda: {"frozen.py": "a" * 64})
    base = tmp_path / "scripts/node_sem"
    base.mkdir(parents=True)
    for name in RUNTIME_MODULES:
        (base / name).write_text("# training")
    before = ns.runtime_refs()
    (base / "text_view.py").write_text("# unrelated feature producer")
    assert ns.runtime_refs() == before
    (base / "adapter.py").write_text("# changed")
    assert ns.runtime_refs() != before
    (base / "model.py").unlink()
    with pytest.raises(FileNotFoundError, match="training runtime"):
        ns.runtime_refs()


def test_new_producer_keeps_execute_and_verify_working(tmp_path, monkeypatch):
    matrix, auth = inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(ns, "ROOT", tmp_path)
    monkeypatch.setattr(ns, "_code_refs", lambda: {})
    base = tmp_path / "scripts/node_sem"
    base.mkdir(parents=True)
    for name in RUNTIME_MODULES:
        (base / name).write_text("# training")
    monkeypatch.setattr(ns, "runtime_refs", REAL_RUNTIME_REFS)
    path = tmp_path / "batch/plan.json"
    plan = ns.create(path.parent, matrix, auth)
    (base / "text_view.py").write_text("# future producer")
    assert ns.load(path, "execute") == ns.load(path, "verify") == plan


@pytest.mark.parametrize("legacy", [False, True])
def test_archive_works_after_runtime_change_but_cannot_execute(tmp_path, monkeypatch, legacy):
    path, plan, job, attempt = complete(tmp_path, monkeypatch, legacy)
    monkeypatch.setattr(ns, "runtime_refs", lambda: {"runtime.py": "b" * 64})
    assert ns.load(path, mode="verify") == plan
    assert ns._verify_execution_records(path, plan, job, attempt) == {
        "current_code_equality": "not_required", "started_runtime_matches_plan": True}
    with pytest.raises(ValueError, match="runtime|verify-only"):
        ns.load(path, mode="execute")


def test_v1_rejects_execute_even_when_current_runtime_equals_old(tmp_path, monkeypatch):
    path, plan, job, attempt = complete(tmp_path, monkeypatch, True)
    assert ns.load(path, "verify") == plan
    with pytest.raises(ValueError, match="verify-only"):
        ns.load(path)


@pytest.mark.parametrize("target", ["receipt", "artifact", "start", "start_runtime_resealed"])
def test_verify_rejects_altered_execution_evidence(tmp_path, monkeypatch, target):
    path, plan, job, attempt = complete(tmp_path, monkeypatch)
    start = attempt.with_suffix(".started.json")
    if target == "receipt":
        receipt = read(attempt / "receipt.json")
        receipt["extra"] = "tampered"
        (attempt / "receipt.json").write_text(json.dumps(receipt))
    elif target == "artifact":
        (attempt / "evidence.json").write_text("{}")
    else:
        value = read(start)
        value["runtime"]["runtime.py"] = "c" * 64
        start.write_text(json.dumps(value))
        if target == "start_runtime_resealed":
            receipt = read(attempt / "receipt.json")
            receipt["execution_start"] = ref(start)
            (attempt / "receipt.json").write_text(json.dumps(receipt))
            anchor = read(attempt / "receipt.seal.json")
            anchor["receipt"] = ref(attempt / "receipt.json")
            (attempt / "receipt.seal.json").write_text(json.dumps(anchor))
    with pytest.raises(ValueError):
        ns.load(path, "verify")


def test_legacy_checks_all_recorded_runtime_not_current_module_subset(tmp_path, monkeypatch):
    path, plan, job, attempt = complete(tmp_path, monkeypatch, True)
    value = read(attempt.with_suffix(".started.json"))
    value["runtime"]["scripts/node_sem/recon/probe.py"] = "d" * 64
    attempt.with_suffix(".started.json").write_text(json.dumps(value))
    receipt = read(attempt / "receipt.json")
    receipt["execution_start"] = ref(attempt.with_suffix(".started.json"))
    (attempt / "receipt.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="runtime"):
        ns.load(path, "verify")


def test_invalid_mode_rejected(tmp_path):
    with pytest.raises(ValueError, match="mode"):
        ns.load(tmp_path / "absent", mode="skip")
