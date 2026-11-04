"""Small CPU-only gates/statistics regression tests for diagnostic replay."""
import ast
import importlib
import json
from pathlib import Path
import numpy as np
import pytest
import torch

PREFIX = "scripts.DFG.experiments.audit.ddg_diagnostics_v1."
common = importlib.import_module(PREFIX + "diagnostic_common")
validator = importlib.import_module(PREFIX + "validate_runner_inputs")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


@pytest.fixture
def protected_fixture(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    root, run = repo / "diagnostics", repo / "run"
    root.mkdir(parents=True); run.mkdir()
    code = repo / "production.py"; code.write_text("original source\n")
    frozen = repo / "frozen.json"; frozen.write_text("{}")
    plan = {"base_git_head": "training", "protocol": "paper_kfold", "score_role": "cv_validation",
            "runner_code_sha256": {"production.py": validator._sha(code)},
            "frozen_files": {str(frozen): validator._sha(frozen)}, "jobs": []}
    state = {"stage_b": "passed", "stage_c": "passed", "jobs": {}}
    inventory = {"accepted_pairs": 30, "best_checkpoints": 60, "pilot_pairs": 7, "jobs": []}
    for cohort, task, count in (("reentrancy_author", "contract", 5),
                                ("access_control_author", "contract", 5),
                                ("reentrancy_author", "node", 10),
                                ("access_control_author", "node", 10)):
        for fold in range(count):
            name = "{}_{}_fold{}".format(cohort, task, fold)
            attempt = run / "jobs" / name / "attempt_001"
            variants, receipt = {}, {"acceptance": {"status": "passed", "job": name}, "artifacts": {}}
            for variant in ("E0", "E1"):
                paths, hashes = {}, {}
                for key in ("best.pt", "initial.pt", "last.pt", "binding.json",
                            "model_input.json", "cv_validation_predictions.json"):
                    p = write(attempt / ("fold_" + str(fold)) / variant / key, {"placeholder": key})
                    paths[key] = str(p); hashes[key] = validator._sha(p)
                    receipt["artifacts"][str(p.relative_to(attempt))] = hashes[key]
                variants[variant] = {"paths": paths, "hashes_from_receipt": hashes}
            receipt_path = write(attempt.with_suffix(".receipt.json"), receipt)
            job = {"id": name, "cohort": cohort, "task": task, "fold": fold,
                   "prepared": str(repo / "prepared" / cohort),
                   "splits": str(repo / "splits" / (cohort + "_" + task + ".json"))}
            plan["jobs"].append(job)
            state["jobs"][name] = {"status": "passed", "exit_code": 0,
                                   "attempt": str(attempt.relative_to(run)),
                                   "receipt": str(receipt_path.relative_to(run)),
                                   "receipt_sha256": validator._sha(receipt_path)}
            inventory["jobs"].append(dict(job, accepted_attempt=str(attempt), receipt=str(receipt_path),
                                           variants=variants))
    write(run / "plan.json", plan); write(run / "plan.seal.json", {"sealed": True})
    write(run / "state.json", state)
    snapshot = {str(p): {"exists": True, "size": p.stat().st_size, "sha256": validator._sha(p)}
                for p in repo.rglob("*") if p.is_file()}
    write(root / "archive" / "before.json", {"head": "archive", "snapshot": snapshot})
    write(root / "archive" / "asset_inventory.json", inventory)
    tasks = {cohort + "_" + task: {"status": "passed"}
             for cohort in ("reentrancy_author", "access_control_author")
             for task in ("node", "contract")}
    write(root / "static" / "summary.json", {"status": "passed", "complete_tasks": 4, "tasks": tasks})
    write(root / "static" / "edge_functions.json", {"tasks": tasks})
    write(root / "static" / "input_invariants.json", {
        "input_drift": [], "graph_fingerprints_preserved": True,
        "input_hashes": {str(frozen): validator._sha(frozen)},
        "frozen_code_before": plan["runner_code_sha256"],
        "frozen_code_after": plan["runner_code_sha256"]})
    audit = {"status": "passed", "missing_or_changed_assets": [],
             "post_archive_readonly_check": {"unchanged": True},
             "archive_report": {"returncode": 0},
             "archive_report_summary": {"complete_tasks": 4, "pending_tasks": 0, "score_role": "cv_validation"},
             "archive_descends_from_training_base": True, "frozen_scan_excludes_diagnostic_directory": True,
             "sealed_run": str(run), "diagnostic_directory": str(root), "repository": str(repo),
             "before_snapshot": str(root / "archive" / "before.json"),
             "archive_head": "archive", "sealed_training_base": "training"}
    write(root / "input_audit.json", audit)
    monkeypatch.setattr(validator, "_git_head", lambda path: "archive")
    return root, run, repo


def test_preflight_passes_complete_tiny_archive_without_loading_checkpoints(protected_fixture, monkeypatch):
    monkeypatch.setattr(torch, "load", lambda *a, **kw: pytest.fail("preflight must never load weights"))
    root, run, _ = protected_fixture
    evidence = validator.validate_preflight(root, run)
    assert evidence["status"] == "passed"
    assert evidence["accepted_pairs"] == 30 and evidence["best_checkpoints"] == 60
    assert evidence["no_model_loaded"] is True


@pytest.mark.parametrize("field,value", [
    ("status", "blocked"), ("missing_or_changed_assets", [{"changed": True}]),
    ("post_archive_readonly_check", {"unchanged": False}),
    ("archive_report", {"returncode": 1}),
    ("archive_report_summary", {"complete_tasks": 3, "pending_tasks": 1, "score_role": "cv_validation"}),
    ("archive_report_summary", {"complete_tasks": 4, "pending_tasks": 0, "score_role": "independent_test"}),
    ("archive_descends_from_training_base", False),
    ("frozen_scan_excludes_diagnostic_directory", False)])
def test_preflight_rejects_failed_audit_even_if_asset_files_exist(protected_fixture, field, value):
    root, run, _ = protected_fixture
    audit = validator._read(root / "input_audit.json"); audit[field] = value
    write(root / "input_audit.json", audit)
    with pytest.raises(ValueError, match="Diagnostic preflight"):
        validator.validate_preflight(root, run)


@pytest.mark.parametrize("name", ["production.py", "frozen.json", "run/plan.json", "run/state.json"])
def test_preflight_rejects_original_byte_drift(protected_fixture, name):
    root, run, repo = protected_fixture
    p = repo / name
    p.write_bytes(p.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="changed"):
        validator.validate_preflight(root, run)


def test_preflight_rejects_forged_inventory_checkpoint_hash(protected_fixture):
    root, run, _ = protected_fixture
    p = root / "archive" / "asset_inventory.json"; doc = validator._read(p)
    doc["jobs"][0]["variants"]["E1"]["hashes_from_receipt"]["best.pt"] = "forged"
    write(p, doc)
    with pytest.raises(ValueError, match="digest mismatch"):
        validator.validate_preflight(root, run)


def test_preflight_rejects_changed_head(protected_fixture, monkeypatch):
    root, run, _ = protected_fixture
    monkeypatch.setattr(validator, "_git_head", lambda path: "other")
    with pytest.raises(ValueError, match="HEAD changed"):
        validator.validate_preflight(root, run)


@pytest.mark.parametrize("patch", [{"status": "running"}, {"complete_tasks": 3}, {"tasks": {}}])
def test_preflight_rejects_incomplete_static_summary(protected_fixture, patch):
    root, run, _ = protected_fixture
    p = root / "static" / "summary.json"; doc = validator._read(p); doc.update(patch); write(p, doc)
    with pytest.raises(ValueError, match="static"):
        validator.validate_preflight(root, run)


def test_identity_alignment_uses_file_and_original_id_not_position():
    expected = [{"file": "a.sol", "original_graph_node_id": 7, "target": 1},
                {"file": "b.sol", "original_graph_node_id": 7, "target": 0}]
    assert common.align_records(expected[::-1], expected, "node") == expected
    changed = [dict(expected[0], original_graph_node_id="7"), expected[1]]
    with pytest.raises(ValueError, match="identity mismatch"):
        common.align_records(changed, expected, "node")
    with pytest.raises(ValueError, match="Duplicate"):
        common.align_records([expected[0], expected[0]], expected, "node")
    with pytest.raises(ValueError, match="target mismatch"):
        common.align_records([dict(expected[0], target=0), expected[1]], expected, "node")


def test_logits_probability_predictions_are_distinguished():
    y = [0, 1]; a = np.asarray([[2., 0.], [0., 2.]], dtype=np.float32)
    b = a + np.float32(1)
    score, _, _ = common.compare_outputs(y, a, b, ["a.sol", "b.sol"])
    assert score["predictions_exact"] and score["probabilities_exact"] and not score["logits_exact"]
    assert score["prediction_flips"] == 0 and score["buggy_f1"] == 100.
    c = np.asarray([[0., 2.], [2., 0.]], dtype=np.float32)
    score, _, _ = common.compare_outputs(y, a, c, ["a.sol", "b.sol"])
    assert score["prediction_flips"] == 2 and score["introduced"] == 2 and score["corrected"] == 0


def test_output_export_refuses_overwrite(tmp_path):
    p = tmp_path / "diagnosis.json"
    common.write_json(p, {"original": True})
    with pytest.raises(FileExistsError):
        common.write_json(p, {"replacement": True})
    assert common.read_json(p) == {"original": True}


def test_summary_nonfinite_rejected_and_empty_explicit():
    with pytest.raises(ValueError, match="Nonfinite"):
        common.summary([float("nan")])
    assert common.summary([])["n"] == 0 and common.summary([])["mean"] is None


def test_runner_contains_no_training_optimizer_or_backward_calls():
    module = ast.parse((Path(__file__).parent / "run_diagnostics.py").read_text())
    forbidden = []
    for node in ast.walk(module):
        if isinstance(node, ast.Call):
            text = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if text in ("backward", "step", "zero_grad", "train", "Adam", "AdamW", "SGD", "fit"):
                forbidden.append(text)
    assert forbidden == []


@pytest.mark.parametrize("field,value", [
    ("input_drift", ["changed"]), ("graph_fingerprints_preserved", False),
    ("frozen_code_before", {}), ("frozen_code_after", {}), ("input_hashes", {})])
def test_preflight_rejects_static_invariant_failure(protected_fixture, field, value):
    root, run, _ = protected_fixture
    p = root / "static" / "input_invariants.json"; doc = validator._read(p)
    doc[field] = value; write(p, doc)
    with pytest.raises(ValueError, match="static"):
        validator.validate_preflight(root, run)


def test_preflight_rejects_incomplete_function_metadata(protected_fixture):
    root, run, _ = protected_fixture
    write(root / "static" / "edge_functions.json", {"tasks": {}})
    with pytest.raises(ValueError, match="function metadata"):
        validator.validate_preflight(root, run)


@pytest.fixture
def replay_gate_data():
    runner = importlib.import_module(PREFIX + "run_diagnostics")
    logits = torch.tensor([[2., 0.], [0., 2.]], dtype=torch.float32)
    probabilities = logits.softmax(1)[:, 1].tolist()
    records = [{"file": "a.sol", "original_graph_node_id": 7, "target": 0},
               {"file": "b.sol", "original_graph_node_id": 7, "target": 1}]
    archived = [dict(r, best=int(logits[i].argmax()), best_positive_probability=probabilities[i])
                for i, r in enumerate(records)]
    return runner, records, archived, logits, probabilities, runner.metrics([0, 1], [0, 1])


def test_native_archive_gate_aligns_original_identities(replay_gate_data):
    runner, records, archived, logits, probabilities, score = replay_gate_data
    result = runner.archived_gate(archived[::-1], records, "node", "best", logits, probabilities, score)
    assert result["predictions_exact"] and result["metrics_match"] and result["probability_exact"]


def test_native_archive_gate_rejects_prediction_difference(replay_gate_data):
    runner, records, archived, logits, probabilities, score = replay_gate_data
    archived[0]["best"] = 1
    with pytest.raises(AssertionError, match="discrete predictions"):
        runner.archived_gate(archived, records, "node", "best", logits, probabilities, score)


def test_native_archive_gate_rejects_probability_tolerance_failure(replay_gate_data):
    runner, records, archived, logits, probabilities, score = replay_gate_data
    archived[0]["best_positive_probability"] += .001
    with pytest.raises(AssertionError, match="predeclared probability tolerance"):
        runner.archived_gate(archived, records, "node", "best", logits, probabilities, score)


@pytest.mark.parametrize("field", ["buggy_f1", "macro_f1", "precision", "recall", "tn_fp_fn_tp"])
def test_native_archive_gate_rejects_metric_disagreement(replay_gate_data, field):
    runner, records, archived, logits, probabilities, score = replay_gate_data
    score[field] = [0, 1, 1, 0] if field == "tn_fp_fn_tp" else score[field] - 1
    with pytest.raises(AssertionError, match="mismatch"):
        runner.archived_gate(archived, records, "node", "best", logits, probabilities, score)
