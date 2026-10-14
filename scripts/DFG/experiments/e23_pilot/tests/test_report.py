"""Synthetic accepted receipts: report integrity, no training or model loading."""
import copy
import csv
import json
import pickle
from pathlib import Path

import networkx as nx
import pytest

from scripts.DFG.experiments.common import sha256, digest
from scripts.DFG.experiments.e23_pilot import report


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def reseal(attempt):
    old = json.loads((attempt / "receipt.json").read_text()) if (attempt / "receipt.json").exists() else {}
    receipt = {"status": "complete",
               "artifact_sha256": {path.name: sha256(path) for path in attempt.iterdir()
                                   if path.is_file() and path.name != "receipt.json"},
               "result_sha256": sha256(attempt / "result.json"),
               "binding_sha256": digest(json.loads((attempt / "binding.json").read_text()))}
    receipt.update({k: old[k] for k in ("mode", "job", "plan_sha256") if k in old})
    write_json(attempt / "receipt.json", receipt)
    return receipt


def fixture_run(output):
    jobs = []
    for task_id in report.TASKS:
        task = task_id.rsplit("_", 1)[1]
        cohort = task_id[:-(len(task) + 1)]
        graph = nx.MultiDiGraph()
        for idx, filename in enumerate(("train.sol", "a.sol", "b.sol")):
            graph.add_node("n" + str(idx), source_file=filename, node_type="statement",
                           node_info_vulnerabilities=[{"category": "fixture"}] if idx == 1 else None)
        folder = output / "inputs" / task_id
        folder.mkdir(parents=True)
        path = folder / "E2.gpickle"
        with path.open("wb") as stream:
            pickle.dump(graph, stream)
        label_path = folder / "labels.json"
        write_json(label_path, [{"contract_name": name, "targets": int(name == "a.sol")}
                                for name in ("train.sol", "a.sol", "b.sol")])
        info = {"task_id": task_id, "task": task, "cohort": cohort, "fold": 0,
                "graphs": {"E2": {"path": str(path), "sha256": sha256(path)}},
                "labels_path": str(label_path), "labels_sha256": sha256(label_path),
                "split": {"train_files": ["train.sol"], "val_files": ["a.sol", "b.sol"]},
                "config": {"mode": "full", "maximum_training_epochs": 50, "schedule_epochs": 50, "seed": 1},
                "support": {variant: {"registered_without_train_relations": [],
                    "enhancement_support": {rel: {"train": 1 if rel == "DATA_DEF_USE" else 0,
                                                "val": 0} for rel in report.RELATIONS}}
                            for variant in report.VARIANTS}}
        manifest = folder / "task_manifest.json"
        write_json(manifest, info)
        for variant in report.VARIANTS:
            job = {"task_id": task_id, "cohort": cohort, "task": task,
                   "fold": 0, "variant": variant,
                   "task_manifest": str(manifest), "task_manifest_sha256": sha256(manifest)}
            jobs.append(job)
            attempt = output / "runs" / task_id / "fold_0" / variant / "attempt_001"
            attempt.mkdir(parents=True)
            pred = {"E2": [0, 0], "E3a": [1, 0], "E3b": [0, 1]}[variant]
            last = [1, 1]
            rows = []
            for index, file in enumerate(("a.sol", "b.sol")):
                row = {"file": file, "target": int(file == "a.sol"), "score_role": "cv_validation",
                       "best": pred[index], "last": last[index],
                       "best_positive_probability": 0.9 if pred[index] else 0.1,
                       "last_positive_probability": 0.8}
                if task == "node":
                    row.update(model_node_id=index + 1, original_graph_node_id="n" + str(index + 1),
                               node_type="statement")
                rows.append(row)
            scores = {ck: report._metrics([1, 0], [row[ck] for row in rows]) for ck in ("best", "last")}
            gradient = {"enhancement_relations": [{
                "canonical": ["statement", "DATA_DEF_USE", "statement"], "train_edges": 1,
                "val_edges": 0, "relation_msg_gradient_l1": 1.5,
                "relation_att_gradient_l1": 0.5, "relation_pri_gradient_l1": 0.1}]}
            result = {"status": "complete", "variant": variant, "score_role": "cv_validation",
                      "protocol": "paper_kfold", "checkpoint_roundtrip_exact": {"best": True, "last": True},
                      "best_epoch": 0, "last_epoch": 1, "best_cv_validation_loss": 0.4, "history_rows": 2,
                      "cv_validation": scores, "parameters": 1200, "wall_seconds_monotonic": 3.2,
                      "stop_reason": "early_stopping",
                      "gradient_audit": {"epochs": [gradient, gradient]},
                      "enhancement_last_message_update_l1": {rel: 0.2 for rel in report.RELATIONS},
                      "resource": {"peak_allocated_bytes": 1000, "peak_reserved_bytes": 2000,
                                   "card": {"minimum_whole_card_free_mib": 200}}}
            write_json(attempt / "result.json", result)
            write_json(attempt / "effective_config.json", info["config"])
            write_json(attempt / "schema_support_audit.json", info["support"][variant])
            write_json(attempt / "cv_validation_predictions.json", rows)
            write_json(attempt / "binding.json", {"variant": variant, "task": task, "cohort": cohort,
                       "protocol": "paper_kfold", "score_role": "cv_validation", "mode": "full",
                       "effective_config_sha256": digest(info["config"])})
            history = [
                {"epoch": 0, "cv_validation_loss": 0.4, "cv_validation": scores["best"], "saved_best": True},
                {"epoch": 1, "cv_validation_loss": 0.6, "cv_validation": scores["last"], "saved_best": False}]
            (attempt / "history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in history))
            (attempt / "best.pt").write_bytes(b"fixture: no model deserialization")
            (attempt / "last.pt").write_bytes(b"fixture: last checkpoint")
            reseal(attempt)
    write_json(output / "plan.json", {"jobs": jobs})
    write_json(output / "plan.seal.json", {"sha256": sha256(output / "plan.json")})
    for job in jobs:
        attempt = output / "runs" / job["task_id"] / "fold_0" / job["variant"] / "attempt_001"
        binding = json.loads((attempt / "binding.json").read_text())
        binding["pilot_plan_sha256"] = digest({"jobs": jobs})
        write_json(attempt / "binding.json", binding)
        receipt = reseal(attempt)
        receipt.update(mode="full", job=job, plan_sha256=digest({"jobs": jobs}))
        write_json(attempt / "receipt.json", receipt)
    return jobs


def first_attempt(output):
    return output / "runs" / report.TASKS[0] / "fold_0/E2/attempt_001"


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def test_all_twelve_required_metrics_recomputed_and_best_last_separate(tmp_path):
    fixture_run(tmp_path)
    result = report.summarize(tmp_path)
    assert result["accepted_fits"] == 12
    assert result["metrics_independently_recomputed"]
    assert result["targets_and_ids_match_frozen_E2"]
    best = read_csv(tmp_path / "summary.csv")
    last = read_csv(tmp_path / "last_summary.csv")
    deltas = read_csv(tmp_path / "paired_deltas.csv")
    assert len(best) == len(last) == 12 and len(deltas) == 24
    assert {row["checkpoint"] for row in best} == {"best"}
    assert {row["checkpoint"] for row in last} == {"last"}
    assert best[0]["buggy_f1"] == "0.0"
    assert float(last[0]["buggy_f1"]) == pytest.approx(200 / 3)
    assert float(best[1]["buggy_f1"]) == 100
    assert float(deltas[0]["buggy_f1_delta_pp"]) == 100
    assert best[0]["DATA_DEF_USE_relation_msg_gradient_l1_sum"] == "3.0"
    errors = read_csv(tmp_path / "error_changes.csv")
    assert any(row["transition"] == "fixed" for row in errors)
    assert any(row["transition"] == "regressed" for row in errors)
    assert all(row["score_role"] == "cv_validation" for row in best + last + deltas + errors)
    before = {name: (tmp_path / name).read_bytes() for name in
              ("summary.csv", "last_summary.csv", "paired_deltas.csv", "error_changes.csv", "report.json", "report.md")}
    assert report.summarize(tmp_path) == result
    assert all((tmp_path / name).read_bytes() == content for name, content in before.items())


@pytest.mark.parametrize("case", ["missing_fit", "multiple_complete", "bad_hash", "bad_counts",
    "bad_metric", "wrong_target", "wrong_node_id", "wrong_best", "wrong_saved_best", "bad_probability",
    "wrong_role", "binding_digest", "wrong_schema_population", "manifest_sha", "checkpoint_roundtrip",
    "fewer_jobs", "extra_fold", "plan_seal", "artifact_escape", "bad_history", "smoke_mode", "wrong_plan", "changed_config"])
def test_invalid_receipts_predictions_and_fold_coverage_fail_closed_without_report(tmp_path, case):
    jobs = fixture_run(tmp_path)
    attempt = first_attempt(tmp_path)
    receipt = json.loads((attempt / "receipt.json").read_text())
    if case == "smoke_mode":
        receipt["mode"] = "smoke"
        write_json(attempt / "receipt.json", receipt)
    elif case == "wrong_plan":
        receipt["plan_sha256"] = "0" * 64
        write_json(attempt / "receipt.json", receipt)
    elif case == "changed_config":
        cfg = json.loads((attempt / "effective_config.json").read_text())
        cfg["seed"] = 123
        write_json(attempt / "effective_config.json", cfg)
        reseal(attempt)
    elif case == "missing_fit":
        receipt["status"] = "failed"
        write_json(attempt / "receipt.json", receipt)
    elif case == "multiple_complete":
        import shutil
        shutil.copytree(str(attempt), str(attempt.with_name("attempt_002")))
    elif case == "bad_hash":
        (attempt / "best.pt").write_bytes(b"changed")
    elif case in ("bad_counts", "bad_metric", "wrong_best", "checkpoint_roundtrip"):
        result = json.loads((attempt / "result.json").read_text())
        if case == "bad_counts":
            result["cv_validation"]["best"]["n"] += 1
        elif case == "bad_metric":
            result["cv_validation"]["best"]["buggy_f1"] = 99
        elif case == "wrong_best":
            result["best_epoch"] = 1
        else:
            result["checkpoint_roundtrip_exact"]["last"] = False
        write_json(attempt / "result.json", result)
        reseal(attempt)
    elif case in ("wrong_target", "wrong_node_id", "bad_probability", "wrong_role", "wrong_schema_population"):
        if case == "wrong_node_id":
            attempt = tmp_path / "runs" / report.TASKS[2] / "fold_0/E2/attempt_001"
        rows = json.loads((attempt / "cv_validation_predictions.json").read_text())
        if case == "wrong_target":
            rows[0]["target"] = 0
        elif case == "wrong_node_id":
            rows[0]["original_graph_node_id"] = "wrong"
        elif case == "bad_probability":
            rows[0]["best_positive_probability"] = float("nan")
        elif case == "wrong_role":
            rows[0]["score_role"] = "independent_test"
        else:
            rows.pop()
        write_json(attempt / "cv_validation_predictions.json", rows)
        reseal(attempt)
    elif case in ("wrong_saved_best", "bad_history"):
        history = [json.loads(line) for line in (attempt / "history.jsonl").read_text().splitlines()]
        if case == "wrong_saved_best":
            history[1]["saved_best"] = True
        else:
            history[1]["epoch"] = 4
        (attempt / "history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in history))
        reseal(attempt)
    elif case == "binding_digest":
        receipt["binding_sha256"] = "0" * 64
        write_json(attempt / "receipt.json", receipt)
    elif case == "manifest_sha":
        Path(jobs[0]["task_manifest"]).write_text("{}")
    elif case in ("fewer_jobs", "extra_fold", "plan_seal"):
        if case == "fewer_jobs":
            jobs.pop()
        elif case == "extra_fold":
            jobs[0]["fold"] = 1
        write_json(tmp_path / "plan.json", {"jobs": jobs, "changed": True})
        if case != "plan_seal":
            write_json(tmp_path / "plan.seal.json", {"sha256": sha256(tmp_path / "plan.json")})
    elif case == "artifact_escape":
        receipt["artifact_sha256"]["../outside.json"] = "x"
        write_json(attempt / "receipt.json", receipt)
    with pytest.raises((ValueError, KeyError)):
        report.summarize(tmp_path)
    assert not (tmp_path / "summary.csv").exists()
    assert not (tmp_path / "report.json").exists()


def test_failed_attempt_retained_but_never_scored(tmp_path):
    fixture_run(tmp_path)
    failed = first_attempt(tmp_path).with_name("attempt_000")
    write_json(failed / "receipt.json", {"status": "failed", "reason": "fixture failed, not scored"})
    result = report.summarize(tmp_path)
    assert len(result["accepted"][0]["attempt_records"]) == 2
    assert result["accepted_fits"] == 12


def test_existing_different_report_is_not_overwritten(tmp_path):
    fixture_run(tmp_path)
    (tmp_path / "summary.csv").write_text("existing report, preserve")
    with pytest.raises(FileExistsError, match="overwrite"):
        report.summarize(tmp_path)
    assert (tmp_path / "summary.csv").read_text() == "existing report, preserve"
    assert not (tmp_path / "report.json").exists()
