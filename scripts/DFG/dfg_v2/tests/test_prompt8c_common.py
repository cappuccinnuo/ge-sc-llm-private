"""Read-only archive scope checks using tiny REAL sealed amendment fixtures.

The amendment validator is never mocked. Only source-root/inventory and
historical attempt locations point to isolated temporary test files.
"""
import copy
import json

import pytest

from scripts.DFG.dfg_v2.diagnostics8c import common
from scripts.DFG.dfg_v2.experiment import amendment as am
from scripts.DFG.integration.io import sha256


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf8")


@pytest.fixture
def archive(tmp_path, monkeypatch):
    source = tmp_path / "source"
    names = set(am.REQUIRED_FROZEN_FILES) | {
        "sco_models/model_hgt.py", am.EXPERIMENT + "run.py"}
    for name in names:
        file = source / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("# old " + name + "\n", encoding="utf8")
    old = {name: sha256(source / name) for name in names}
    (source / (am.EXPERIMENT + "run.py")).write_text("# amended run\n", encoding="utf8")
    current = {name: sha256(source / name) for name in names}
    monkeypatch.setattr(am, "ROOT", source)

    def real_inventory():
        return {str(p.relative_to(source)): sha256(p) for p in source.rglob("*.py")}
    monkeypatch.setattr(am, "_runtime_refs", real_inventory)
    plan_path = tmp_path / "batch" / "plan.json"
    plan = {"runtime": old, "jobs": [{"identity": "A"}, {"identity": "B"}],
            "protocol": "frozen-test-only"}
    dump(plan_path, plan)
    dump(plan_path.with_name("plan.seal.json"), {"plan_sha256": sha256(plan_path)})
    proof_path = tmp_path / "proof" / "proof.json"
    proof_evidence = tmp_path / "proof" / "evidence.json"
    dump(proof_evidence, {"synthetic": True, "exact": True})
    proof = {
        "version": am.PROOF_VERSION, "passed": True, "plan": am._ref(plan_path),
        "runtime": current,
        "jobs": [{"job_id": job, "passed": True, "exact": True,
                  "comparison_reference": "stage_A",
                  "checks": {check: True for check in am.PROOF_CHECKS},
                  "refs": {"synthetic": am._ref(proof_evidence)}}
                 for job in am.PROOF_JOBS],
    }
    dump(proof_path, proof)
    amendment_path = tmp_path / "proof" / "amendment.json"
    am.create_amendment(plan_path, amendment_path, proof_path,
                        "Fixture authorizes registration only.", "Synthetic archive fixture.")
    attempts = {}
    for identity in ("A", "B"):
        directory = tmp_path / "attempts" / identity / "attempt_001"
        directory.mkdir(parents=True)
        attempts[identity] = directory
        started = {} if identity == "A" else {"runtime_amendment": am._ref(amendment_path)}
        dump(directory.with_suffix(".started.json"), started)
    monkeypatch.setattr(common, "attempt_for",
                        lambda plan_path, job: attempts[job["identity"]])
    return dict(source=source, plan_path=plan_path, plan=plan, current=current,
                proof=proof_path, proof_evidence=proof_evidence,
                amendment=amendment_path, inventory=real_inventory, attempts=attempts)


def test_checked_plan_rejects_byte_mismatch(archive):
    a = archive
    assert common.checked_plan(a["plan_path"]) == a["plan"]
    a["plan_path"].write_bytes(a["plan_path"].read_bytes() + b" ")
    with pytest.raises(ValueError, match="seal mismatch"):
        common.checked_plan(a["plan_path"])


def test_real_amendment_verifier_still_rejects_plan_seal_mismatch(archive):
    a = archive
    a["plan_path"].write_bytes(a["plan_path"].read_bytes() + b" ")
    original_provider = am._runtime_refs
    with pytest.raises(ValueError, match="Frozen plan seal"):
        with common.historical_runtime(a["plan_path"], a["plan"]):
            pytest.fail("Unverified historical context must not yield")
    assert am._runtime_refs is original_provider


@pytest.mark.parametrize("name", ["sco_models/model_hgt.py", am.EXPERIMENT + "run.py"])
def test_changed_computation_bytes_rejected_before_inventory_patch(archive, name):
    a = archive
    target = a["source"] / name
    target.write_bytes(target.read_bytes() + b"# unapproved mutation\n")
    original_provider = am._runtime_refs
    with pytest.raises(ValueError, match="Historical computation bytes changed"):
        with common.historical_runtime(a["plan_path"], a["plan"]):
            pytest.fail("Changed calculation may never be hidden by inventory scope")
    assert am._runtime_refs is original_provider


def test_new_diagnostic_files_excluded_only_inside_verified_context(archive):
    a = archive
    diagnostic = a["source"] / "scripts/DFG/dfg_v2/diagnostics8c/new_audit.py"
    diagnostic.parent.mkdir(parents=True)
    diagnostic.write_text("# new diagnostic only\n", encoding="utf8")
    name = str(diagnostic.relative_to(a["source"]))
    assert name in am._runtime_refs()
    original_provider = am._runtime_refs
    originals = list(a["source"].rglob("*.py")) + [
        a["plan_path"], a["plan_path"].with_name("plan.seal.json"),
        a["amendment"], am.seal_path(a["amendment"]), a["proof"], a["proof_evidence"]]
    before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in originals}
    with common.historical_runtime(a["plan_path"], a["plan"]) as evidence:
        assert evidence["runtime"] == a["current"]
        assert evidence["execution_authorized"] is False
        assert evidence["extra_diagnostic_files_excluded"] is True
        assert name not in am._runtime_refs()
        # Exercise the real validator again using the context's scoped provider.
        record = am.validate_amendment(a["amendment"], a["plan_path"], a["plan"])
        assert record["execution_authorized"] is False
    assert am._runtime_refs is original_provider
    assert name in am._runtime_refs()
    assert before == {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in originals}


def test_context_restores_inventory_provider_even_when_consumer_raises(archive):
    a = archive
    original_provider = am._runtime_refs
    with pytest.raises(RuntimeError, match="consumer"):
        with common.historical_runtime(a["plan_path"], a["plan"]):
            raise RuntimeError("consumer")
    assert am._runtime_refs is original_provider


def test_proof_evidence_tampering_not_hidden_by_scoped_inventory(archive):
    a = archive
    a["proof_evidence"].write_bytes(a["proof_evidence"].read_bytes() + b" ")
    original_provider = am._runtime_refs
    with pytest.raises(ValueError, match="evidence SHA"):
        with common.historical_runtime(a["plan_path"], a["plan"]):
            pytest.fail("Proof must be validated before yielding")
    assert am._runtime_refs is original_provider


def test_caller_cannot_remove_frozen_file_from_historical_inventory(archive):
    a = archive
    changed_plan = copy.deepcopy(a["plan"])
    del changed_plan["runtime"]["sco_models/model_hgt.py"]
    with pytest.raises(ValueError, match="Caller plan differs"):
        with common.historical_runtime(a["plan_path"], changed_plan):
            pytest.fail("Caller may not weaken the sealed inventory")


def test_archive_writer_is_exclusive(archive):
    path = archive["source"] / "output.json"
    common.write_new(path, {"value": 1})
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        common.write_new(path, {"value": 2})
    assert path.read_bytes() == original
