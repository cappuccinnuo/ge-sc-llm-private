"""Prompt 8B.0 amendment tests: registration is not execution approval."""
import copy
import hashlib

import pytest

from scripts.DFG.dfg_v2.experiment import amendment as am
from scripts.DFG.integration.io import read_json, write_json, sha256


def _hash(text):
    return hashlib.sha256(text.encode("utf8")).hexdigest()


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    old = {name: _hash(name) for name in am.REQUIRED_FROZEN_FILES}
    old.update({"sco_models/model_hgt.py": _hash("HGT"),
        "scripts/DFG/access_extractor.py": _hash("frozen DDG"),
        am.EXPERIMENT + "run.py": _hash("old run"),
        am.EXPERIMENT + "checkpoint.py": _hash("old checkpoint"),
        am.EXPERIMENT + "batch.py": _hash("old batch")})
    source_root = tmp_path / "active_source"
    reporting = source_root / am.REPORTING_PATH
    reporting.parent.mkdir(parents=True)
    reporting.write_bytes(
        b'def build_report(plan_path, stage="A", verified_results=None, output=None):\n'
        b'    plan = run._load_plan(plan_path)\n'
        b'    statistic = sum(plan["scores"]) / len(plan["scores"])\n'
        b'    return statistic\n')
    old[am.REPORTING_PATH] = sha256(reporting)
    monkeypatch.setattr(am, "ROOT", source_root)
    current = dict(old)
    current[am.EXPERIMENT + "run.py"] = _hash("new run")
    current[am.EXPERIMENT + "amendment.py"] = _hash("new amendment")
    monkeypatch.setattr(am, "_runtime_refs", lambda: copy.deepcopy(current))
    batch = tmp_path / "old_batch"
    batch.mkdir()
    plan_path = batch / "plan.json"
    plan = {"runtime": old, "jobs": ["frozen-150-matrix"],
            "selection_rule": "frozen", "initialization_version": "frozen"}
    write_json(plan_path, plan)
    write_json(batch / "plan.seal.json", {"plan_sha256": sha256(plan_path)})
    proof_path = tmp_path / "proof" / "equivalence.json"
    proof_path.parent.mkdir()
    artifact = proof_path.parent / "evidence.json"
    write_json(artifact, {"exact": True, "synthetic": True})
    proof = {"version": am.PROOF_VERSION, "passed": True,
        "plan": am._ref(plan_path), "runtime": copy.deepcopy(current), "jobs": []}
    for identity in am.PROOF_JOBS:
        proof["jobs"].append({"job_id": identity, "passed": True, "exact": True,
            "comparison_reference": "stage_A",
            "checks": {name: True for name in am.PROOF_CHECKS},
            "refs": {"synthetic_evidence": am._ref(artifact)}})
    write_json(proof_path, proof)
    return {"plan_path": plan_path, "plan": plan, "proof_path": proof_path,
            "proof": proof, "artifact": artifact, "current": current,
            "reporting": reporting, "output": tmp_path / "proof" / "stage_B_amendment.json"}


def create(e):
    return am.create_amendment(e["plan_path"], e["output"], e["proof_path"],
                               "Implement Prompt 8B.0, no formal B training.", "Avoid repeated verification.")


def _rewrite_and_seal(e, record):
    write_json(e["output"], record)
    seal = read_json(am.seal_path(e["output"]))
    seal["amendment_sha256"] = sha256(e["output"])
    write_json(am.seal_path(e["output"]), seal)


def test_exclusive_registration_preserves_plan_and_never_authorizes(evidence):
    e = evidence
    original = {p.name: p.read_bytes() for p in e["plan_path"].parent.iterdir()}
    record = create(e)
    assert record == am.validate_amendment(e["output"], e["plan_path"], e["plan"])
    assert record["stage"] == "B" and record["execution_authorized"] is False
    assert record["stage_A_policy"] == "historical_read_only_no_new_training"
    assert record["proof_jobs"] == list(am.PROOF_JOBS)
    assert record["computation_byte_identity"]["byte_identical"] is True
    frozen = record["computation_byte_identity"]["files"]
    assert all(frozen[k] == e["plan"]["runtime"][k] for k in am.REQUIRED_FROZEN_FILES)
    assert frozen["sco_models/model_hgt.py"] == e["plan"]["runtime"]["sco_models/model_hgt.py"]
    assert {p.name: p.read_bytes() for p in e["plan_path"].parent.iterdir()} == original
    assert {row["path"] for row in record["changes"]} == {
        am.EXPERIMENT + "run.py", am.EXPERIMENT + "amendment.py"}
    assert next(row for row in record["changes"] if row["kind"] == "added")["old_sha256"] is None
    written = e["output"].read_bytes()
    with pytest.raises(FileExistsError):
        create(e)
    assert e["output"].read_bytes() == written


@pytest.mark.parametrize("filename", sorted(am.REQUIRED_FROZEN_FILES) + [
    "sco_models/model_hgt.py", "scripts/DFG/access_extractor.py",
    am.EXPERIMENT + "new_trainer.py", "scripts/DFG/dfg_v2/new_model.py"])
def test_only_explicit_orchestration_files_can_differ(evidence, filename):
    e = evidence
    e["current"][filename] = _hash("changed computation")
    with pytest.raises(ValueError, match="Unapproved runtime"):
        create(e)
    assert not e["output"].exists()


def test_all_eight_reviewed_paths_are_allowed_but_no_others(evidence):
    e = evidence
    for name in am.ALLOWED_RUNTIME_CHANGES:
        if name != am.REPORTING_PATH:
            e["current"][name] = _hash("new " + name)
    source = e["reporting"].read_bytes()
    for old, new in am.REPORTING_REPLACEMENTS:
        source = source.replace(old, new, 1)
    e["reporting"].write_bytes(source)
    e["current"][am.REPORTING_PATH] = sha256(e["reporting"])
    proof = read_json(e["proof_path"])
    proof["runtime"] = copy.deepcopy(e["current"])
    write_json(e["proof_path"], proof)
    record = create(e)
    assert len(record["changes"]) == 8
    assert record["reporting_interface_only"]["statistics_bytes_unchanged"] is True
    assert record["reporting_interface_only"]["restored_source_sha256"] == e["plan"]["runtime"][am.REPORTING_PATH]


def test_missing_runtime_file_not_silently_allowed(evidence):
    e = evidence
    del e["current"][am.EXPERIMENT + "checkpoint.py"]
    with pytest.raises(ValueError, match="deletion"):
        create(e)


@pytest.mark.parametrize("field", ["jobs", "selection_rule", "initialization_version"])
def test_plan_bytes_and_caller_plan_are_checked(evidence, field):
    e = evidence
    create(e)
    copied = copy.deepcopy(e["plan"])
    copied[field] = "different"
    with pytest.raises(ValueError, match="Caller plan"):
        am.validate_amendment(e["output"], e["plan_path"], copied)
    write_json(e["plan_path"], copied)
    with pytest.raises(ValueError, match="Frozen plan seal"):
        am.validate_amendment(e["output"], e["plan_path"])


def test_resealed_plan_also_rejected_by_original_reference(evidence):
    e = evidence
    create(e)
    changed = copy.deepcopy(e["plan"])
    changed["selection_rule"] = "choose highest outer F1"
    write_json(e["plan_path"], changed)
    write_json(e["plan_path"].with_name("plan.seal.json"), {"plan_sha256": sha256(e["plan_path"])})
    with pytest.raises(ValueError, match="seal mismatch"):
        am.validate_amendment(e["output"], e["plan_path"])


def test_amendment_tamper_is_rejected(evidence):
    e = evidence
    record = create(e)
    record["reason"] = "modified without resealing"
    write_json(e["output"], record)
    with pytest.raises(ValueError, match="seal mismatch"):
        am.validate_amendment(e["output"], e["plan_path"])


@pytest.mark.parametrize("field,value", [
    ("execution_authorized", True), ("stage", "A"), ("scope", "any_runtime"),
    ("stage_A_policy", "allow_retraining"), ("user_approval_verbatim", ""),
    ("proof_jobs", ["access_control_node/0/1/G0"]), ("recorded_at", ""),
    ("reason", ""), ("changes", []), ("runtime_after_sha256", "wrong"),
    ("computation_byte_identity", {"byte_identical": True})])
def test_resealed_scope_or_inventory_changes_are_rejected(evidence, field, value):
    e = evidence
    record = create(e)
    record[field] = value
    _rewrite_and_seal(e, record)
    with pytest.raises(ValueError):
        am.validate_amendment(e["output"], e["plan_path"])


def test_even_allowed_unlisted_later_runtime_change_is_rejected(evidence):
    e = evidence
    create(e)
    e["current"][am.EXPERIMENT + "checkpoint.py"] = _hash("later mutation")
    with pytest.raises(ValueError, match="runtime inventory"):
        am.validate_amendment(e["output"], e["plan_path"])


@pytest.mark.parametrize("mutation", ["missing_job", "duplicate_job", "wrong_job", "failed",
                                    "nonexact", "missing_check", "failed_check", "no_refs"])
def test_only_complete_exact_two_job_proof_can_register(evidence, mutation):
    e = evidence
    proof = copy.deepcopy(e["proof"])
    if mutation == "missing_job":
        proof["jobs"].pop()
    elif mutation == "duplicate_job":
        proof["jobs"][1] = proof["jobs"][0]
    elif mutation == "wrong_job":
        proof["jobs"][0]["job_id"] = "access_control_node/1/1/G0"
    elif mutation == "failed":
        proof["passed"] = False
    elif mutation == "nonexact":
        proof["jobs"][0]["exact"] = False
    elif mutation == "missing_check":
        del proof["jobs"][0]["checks"]["epochs"]
    elif mutation == "failed_check":
        proof["jobs"][0]["checks"]["best_state"] = False
    else:
        proof["jobs"][0]["refs"] = {}
    write_json(e["proof_path"], proof)
    with pytest.raises(ValueError):
        create(e)
    assert not e["output"].exists()


def test_old_rerun_reference_allowed_only_with_all_exact_checks(evidence):
    e = evidence
    proof = copy.deepcopy(e["proof"])
    for row in proof["jobs"]:
        row["comparison_reference"] = "rerun_old"
    write_json(e["proof_path"], proof)
    assert create(e)["execution_authorized"] is False


@pytest.mark.parametrize("which", ["proof", "artifact"])
def test_proof_or_linked_artifact_tampering_is_rejected(evidence, which):
    e = evidence
    create(e)
    target = e["proof_path"] if which == "proof" else e["artifact"]
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError, match="evidence SHA"):
        am.validate_amendment(e["output"], e["plan_path"])


def test_output_inside_original_batch_is_forbidden(evidence):
    e = evidence
    e["output"] = e["plan_path"].parent / "stage_B_amendment.json"
    with pytest.raises(ValueError, match="inside the frozen batch"):
        create(e)


def test_runtime_must_remain_stable_during_registration(evidence, monkeypatch):
    e = evidence
    current = copy.deepcopy(e["current"])
    calls = []
    def changing():
        calls.append(1)
        result = copy.deepcopy(current)
        if len(calls) > 1:
            result[am.EXPERIMENT + "run.py"] = _hash("edited while hashing")
        return result
    monkeypatch.setattr(am, "_runtime_refs", changing)
    with pytest.raises(ValueError, match="changed while registering"):
        create(e)
    assert not e["output"].exists()


def test_validate_is_read_only(evidence):
    e = evidence
    create(e)
    files = list(e["output"].parent.iterdir()) + list(e["plan_path"].parent.iterdir())
    before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
    am.validate_amendment(e["output"], e["plan_path"])
    assert before == {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in files}


def test_exact_proof_from_different_runtime_cannot_register(evidence):
    e = evidence
    e["current"][am.EXPERIMENT + "run.py"] = _hash("code changed after proof")
    with pytest.raises(ValueError, match="not bound/passed"):
        create(e)
    assert not e["output"].exists()



@pytest.mark.parametrize("extra", [
    b'    statistic = sum(plan["scores"])',
    b'    statistic = max(plan["scores"])',
])
def test_reporting_extra_computation_change_is_rejected_even_if_declared(evidence, extra):
    e = evidence
    source = e["reporting"].read_bytes()
    for old, new in am.REPORTING_REPLACEMENTS:
        source = source.replace(old, new, 1)
    source = source.replace(
        b'    statistic = sum(plan["scores"]) / len(plan["scores"])', extra)
    e["reporting"].write_bytes(source)
    e["current"][am.REPORTING_PATH] = sha256(e["reporting"])
    with pytest.raises(ValueError, match="computation changed beyond"):
        create(e)
    assert not e["output"].exists()


def test_reporting_unchanged_calculation_but_arbitrary_comment_is_rejected(evidence):
    e = evidence
    source = e["reporting"].read_bytes()
    for old, new in am.REPORTING_REPLACEMENTS:
        source = source.replace(old, new, 1)
    e["reporting"].write_bytes(source + b"# an unrelated edit\n")
    e["current"][am.REPORTING_PATH] = sha256(e["reporting"])
    with pytest.raises(ValueError, match="computation changed beyond"):
        create(e)


def test_reporting_source_must_match_runtime_hash(evidence):
    e = evidence
    e["current"][am.REPORTING_PATH] = _hash("forged current reporting SHA")
    with pytest.raises(ValueError, match="Reporting source differs"):
        create(e)


def test_reporting_cannot_be_registered_as_new_file(evidence):
    e = evidence
    del e["plan"]["runtime"][am.REPORTING_PATH]
    write_json(e["plan_path"], e["plan"])
    write_json(e["plan_path"].with_name("plan.seal.json"), {"plan_sha256": sha256(e["plan_path"])})
    with pytest.raises(ValueError, match="requires the original sealed file"):
        create(e)
