"""Independently validate all twelve accepted fold-0 fits before reporting.

This module neither loads model weights nor trains models. Checkpoint reload
correctness is separately required in each accepted fit result.
"""
import csv
import io
import json
import math
from collections import Counter
from pathlib import Path

from scripts.DFG.experiments.common import read_json, sha256, digest
from scripts.labeling_v2.safe_graph import read_graph

VARIANTS = ("E2", "E3a", "E3b")
TASKS = ("reentrancy_author_contract", "access_control_author_contract",
         "reentrancy_author_node", "access_control_author_node")
RELATIONS = ("DATA_DEF_USE", "STATE_DEF_USE", "STATE_ACCESS_ORDER",
             "EXTERNAL_CALL_BEFORE_STATE_WRITE")
METRICS = ("buggy_f1", "macro_f1", "precision", "recall")
CONTRASTS = (("E2", "E3a"), ("E2", "E3b"), ("E3a", "E3b"))


def _metrics(truth, prediction):
    if not truth or len(truth) != len(prediction):
        raise ValueError("Empty/mismatched prediction population")
    if any(value not in (0, 1) for value in truth + prediction):
        raise ValueError("Nonbinary prediction/target")
    tn = sum(y == 0 and p == 0 for y, p in zip(truth, prediction))
    fp = sum(y == 0 and p == 1 for y, p in zip(truth, prediction))
    fn = sum(y == 1 and p == 0 for y, p in zip(truth, prediction))
    tp = sum(y == 1 and p == 1 for y, p in zip(truth, prediction))
    divide = lambda a, b: a / b if b else 0.0
    positive_f1 = divide(2.0 * tp, 2 * tp + fp + fn)
    negative_f1 = divide(2.0 * tn, 2 * tn + fp + fn)
    return {"n": len(truth), "positive": sum(truth),
            "buggy_f1": 100 * positive_f1,
            "macro_f1": 50 * (positive_f1 + negative_f1),
            "precision": 100 * divide(tp, tp + fp),
            "recall": 100 * divide(tp, tp + fn),
            "tn_fp_fn_tp": [tn, fp, fn, tp]}


def _assert_metrics(actual, expected, context):
    for key in ("n", "positive", "tn_fp_fn_tp"):
        if actual.get(key) != expected[key]:
            raise ValueError("Metric count mismatch " + context + ": " + key)
    for key in METRICS:
        if not math.isclose(float(actual[key]), expected[key], rel_tol=1e-10, abs_tol=1e-8):
            raise ValueError("Metric mismatch " + context + ": " + key)


def _checked(path, expected):
    path = Path(path)
    if sha256(path) != expected:
        raise ValueError("Artifact SHA mismatch: " + str(path))
    return path


def _task_info(job):
    path = _checked(job["task_manifest"], job["task_manifest_sha256"])
    info = read_json(path)
    for key in ("task_id", "cohort", "task", "fold"):
        if info[key] != job[key]:
            raise ValueError("Task-manifest/job mismatch: " + key)
    if info["fold"] != 0:
        raise ValueError("Only prespecified fold 0 is reportable")
    return info


def _expected_population(info):
    record = info["graphs"]["E2"]
    graph = read_graph(_checked(record["path"], record["sha256"]))
    files = sorted(info["split"]["val_files"])
    if not files or len(files) != len(set(files)):
        raise ValueError("Invalid frozen validation files")
    if info["task"] == "contract":
        records = read_json(_checked(info["labels_path"], info["labels_sha256"]))
        labels = {record["contract_name"]: int(record["targets"]) for record in records}
        if len(labels) != len(records):
            raise ValueError("Duplicate graph-label records")
        return [{"file": file, "target": labels[file]} for file in files]
    result = []
    for model_id, (original_id, data) in enumerate(graph.nodes(data=True)):
        if data["source_file"] in files:
            result.append({"file": data["source_file"], "model_node_id": model_id,
                           "original_graph_node_id": original_id,
                           "node_type": data["node_type"],
                           "target": 0 if data["node_info_vulnerabilities"] is None else 1})
    if not result or {row["file"] for row in result} != set(files):
        raise ValueError("Frozen node validation population incomplete")
    return result


def _accepted_attempt(output, job):
    folder = output / "runs" / job["task_id"] / "fold_0" / job["variant"]
    receipts = sorted(folder.glob("attempt_*/receipt.json"))
    accepted, all_attempts = [], []
    for failure in sorted(folder.glob("attempt_*.failure.json")):
        value = read_json(failure)
        all_attempts.append({"path": str(failure), "status": value.get("status"),
                             "reason": value.get("exception", value.get("reason"))})
    for path in receipts:
        value = read_json(path)
        all_attempts.append({"path": str(path), "status": value.get("status")})
        if value.get("status") == "complete":
            accepted.append((path, value))
    if len(accepted) != 1:
        raise ValueError("Expected exactly one accepted attempt, never select by score: " + str(folder))
    receipt_path, receipt = accepted[0]
    if receipt.get("mode") != "full" or receipt.get("job") != job:
        raise ValueError("Receipt is not the requested formal fit")
    plan_digest = digest(read_json(output / "plan.json"))
    if receipt.get("plan_sha256") != plan_digest:
        raise ValueError("Receipt plan binding mismatch")
    attempt = receipt_path.parent.resolve()
    artifacts = receipt["artifact_sha256"]
    required = {"result.json", "binding.json", "history.jsonl",
                "cv_validation_predictions.json", "best.pt", "last.pt", "effective_config.json", "schema_support_audit.json"}
    if not required <= set(artifacts):
        raise ValueError("Receipt does not cover required artifacts")
    for name, expected in artifacts.items():
        path = (attempt / name).resolve()
        if attempt not in path.parents:
            raise ValueError("Receipt artifact escapes attempt directory")
        _checked(path, expected)
    _checked(attempt / "result.json", receipt["result_sha256"])
    binding = read_json(attempt / "binding.json")
    if digest(binding) != receipt["binding_sha256"]:
        raise ValueError("Receipt binding digest mismatch")
    for key in ("variant", "task", "cohort"):
        if binding.get(key) != job[key]:
            raise ValueError("Prediction binding/job mismatch: " + key)
    if binding.get("mode") != "full" or binding.get("pilot_plan_sha256") != plan_digest:
        raise ValueError("Binding is not the sealed formal plan")
    if binding.get("score_role") != "cv_validation" or binding.get("protocol") != "paper_kfold":
        raise ValueError("Wrong scoring protocol/role")
    return attempt, receipt, all_attempts


def _read_fit(output, job, info, expected):
    attempt, receipt, attempts = _accepted_attempt(output, job)
    result = read_json(attempt / "result.json")
    config = read_json(attempt / "effective_config.json")
    binding = read_json(attempt / "binding.json")
    if config.get("mode") != "full" or config.get("maximum_training_epochs") != 50 or config.get("schedule_epochs") != 50:
        raise ValueError("Smoke or altered epoch budget cannot enter formal report")
    if any(config.get(k) != v for k, v in info["config"].items()):
        raise ValueError("Effective configuration changed from frozen task")
    if binding.get("effective_config_sha256") != digest(config):
        raise ValueError("Effective configuration binding mismatch")
    if read_json(attempt / "schema_support_audit.json") != info["support"][job["variant"]]:
        raise ValueError("Training support differs from frozen task")
    if result.get("status") != "complete" or result.get("score_role") != "cv_validation":
        raise ValueError("Incomplete or incorrectly named fit result")
    if result.get("variant") != job["variant"]:
        raise ValueError("Result variant mismatch")
    if result.get("checkpoint_roundtrip_exact") != {"best": True, "last": True}:
        raise ValueError("Checkpoint roundtrip not accepted")
    rows = read_json(attempt / "cv_validation_predictions.json")
    if len(rows) != len(expected):
        raise ValueError("Validation prediction population count mismatch")
    seen = set()
    for row, frozen in zip(rows, expected):
        for key, value in frozen.items():
            if row.get(key) != value:
                raise ValueError("Prediction identity/target differs from frozen graph: " + key)
        if row.get("score_role") != "cv_validation":
            raise ValueError("Prediction row score role mismatch")
        identity = (row["file"], json.dumps(row.get("original_graph_node_id"), sort_keys=True))
        if identity in seen:
            raise ValueError("Duplicate scored prediction identity")
        seen.add(identity)
        for checkpoint in ("best", "last"):
            probability = float(row[checkpoint + "_positive_probability"])
            if not math.isfinite(probability) or not 0 <= probability <= 1:
                raise ValueError("Invalid prediction probability")
    scores = {}
    for checkpoint in ("best", "last"):
        scores[checkpoint] = _metrics([r["target"] for r in rows], [r[checkpoint] for r in rows])
        _assert_metrics(result["cv_validation"][checkpoint], scores[checkpoint],
                        job["task_id"] + "/" + job["variant"] + "/" + checkpoint)
    history = [json.loads(line) for line in (attempt / "history.jsonl").read_text().splitlines() if line]
    if not history or len(history) != result["history_rows"]:
        raise ValueError("Incomplete training history")
    if [r["epoch"] for r in history] != list(range(len(history))):
        raise ValueError("Noncontiguous epoch history")
    losses = [float(r["cv_validation_loss"]) for r in history]
    if not all(math.isfinite(loss) for loss in losses):
        raise ValueError("Nonfinite validation loss")
    best_epoch = min(range(len(losses)), key=lambda index: losses[index])
    if result["best_epoch"] != best_epoch or result["last_epoch"] != len(history) - 1:
        raise ValueError("Best/last selection differs from frozen strict minimum rule")
    if float(result["best_cv_validation_loss"]) != losses[best_epoch]:
        raise ValueError("Best validation loss mismatch")
    best_so_far = float("inf")
    for row, loss in zip(history, losses):
        if bool(row["saved_best"]) != (loss < best_so_far):
            raise ValueError("History saved_best does not reflect strict minimum")
        best_so_far = min(loss, best_so_far)
    _assert_metrics(history[best_epoch]["cv_validation"], scores["best"], "best history")
    _assert_metrics(history[-1]["cv_validation"], scores["last"], "last history")
    return {"job": job, "info": info, "result": result, "predictions": rows,
            "scores": scores, "attempt": str(attempt), "attempts": attempts,
            "receipt_sha256": sha256(attempt / "receipt.json")}


def _summary_row(fit, checkpoint):
    job, result = fit["job"], fit["result"]
    row = {key: job[key] for key in ("task_id", "cohort", "task", "fold", "variant")}
    row.update(score_role="cv_validation", checkpoint=checkpoint, **fit["scores"][checkpoint])
    row["tn_fp_fn_tp"] = json.dumps(row["tn_fp_fn_tp"])
    for key in ("best_epoch", "last_epoch", "parameters", "wall_seconds_monotonic", "stop_reason"):
        row[key] = result[key]
    row["epoch_indexing"] = "zero_based"
    for key in ("peak_allocated_bytes", "peak_reserved_bytes"):
        row[key] = result["resource"][key]
    row["minimum_whole_card_free_mib"] = result["resource"]["card"].get("minimum_whole_card_free_mib")
    row["accepted_attempt"] = fit["attempt"]
    row["train_unseen_registered_relations"] = len(
        fit["info"]["support"][job["variant"]]["registered_without_train_relations"])
    epochs = result["gradient_audit"]["epochs"]
    for relation in RELATIONS:
        support = fit["info"]["support"][job["variant"]]["enhancement_support"][relation]
        row[relation + "_train_edges"] = support["train"]
        row[relation + "_val_edges"] = support["val"]
        for bank in ("relation_msg", "relation_att", "relation_pri"):
            row[relation + "_" + bank + "_gradient_l1_sum"] = sum(
                item[bank + "_gradient_l1"] for epoch in epochs
                for item in epoch["enhancement_relations"] if item["canonical"][1] == relation)
        row[relation + "_last_message_update_l1"] = result["enhancement_last_message_update_l1"][relation]
    return row


def _contrasts(fits):
    deltas, errors, counts = [], [], []
    for task_id in TASKS:
        variants = {fit["job"]["variant"]: fit for fit in fits if fit["job"]["task_id"] == task_id}
        for before, after in CONTRASTS:
            left, right = variants[before], variants[after]
            for checkpoint in ("best", "last"):
                prefix = {"task_id": task_id, "cohort": left["job"]["cohort"],
                          "task": left["job"]["task"], "fold": 0, "checkpoint": checkpoint,
                          "contrast": after + "-" + before, "score_role": "cv_validation"}
                delta = dict(prefix)
                delta.update({metric + "_delta_pp":
                              right["scores"][checkpoint][metric] - left["scores"][checkpoint][metric]
                              for metric in METRICS})
                deltas.append(delta)
                counter = Counter()
                for a, b in zip(left["predictions"], right["predictions"]):
                    good_a, good_b = a[checkpoint] == a["target"], b[checkpoint] == b["target"]
                    transition = ("both_correct" if good_a and good_b else
                                  "fixed" if not good_a and good_b else
                                  "regressed" if good_a and not good_b else "both_wrong")
                    counter[transition] += 1
                    pa, pb = a[checkpoint + "_positive_probability"], b[checkpoint + "_positive_probability"]
                    if a[checkpoint] == b[checkpoint] and pa == pb:
                        continue
                    row = dict(prefix, file=a["file"], target=a["target"],
                               original_graph_node_id=a.get("original_graph_node_id"),
                               node_type=a.get("node_type"), before_prediction=a[checkpoint],
                               after_prediction=b[checkpoint], before_positive_probability=pa,
                               after_positive_probability=pb, probability_delta=pb - pa,
                               prediction_changed=a[checkpoint] != b[checkpoint],
                               transition=transition if a[checkpoint] != b[checkpoint] else
                                          "probability_only_" + ("correct" if good_a else "wrong"))
                    errors.append(row)
                counts.append(dict(prefix, **{k: counter[k] for k in
                    ("both_correct", "both_wrong", "fixed", "regressed")}))
    return deltas, errors, counts


def _csv(rows, columns=None):
    if columns is None:
        columns = list(rows[0]) if rows else []
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def summarize(output):
    output = Path(output).resolve()
    plan_path = output / "plan.json"
    plan = read_json(plan_path)
    jobs = plan["jobs"]
    expected = [(task, variant) for task in TASKS for variant in VARIANTS]
    if [(job["task_id"], job["variant"]) for job in jobs] != expected:
        raise ValueError("Plan must contain the twelve prespecified ordered task/variant fits")
    if any(job["fold"] != 0 for job in jobs):
        raise ValueError("Cannot merge additional folds into the pilot")
    seal = output / "plan.seal.json"
    if seal.exists() and read_json(seal)["sha256"] != sha256(plan_path):
        raise ValueError("Plan seal mismatch")
    cache, fits = {}, []
    for job in jobs:
        info = _task_info(job)
        key = job["task_id"]
        if key not in cache:
            cache[key] = (_expected_population(info), job["task_manifest_sha256"])
        if cache[key][1] != job["task_manifest_sha256"]:
            raise ValueError("Variant task manifests differ")
        fits.append(_read_fit(output, job, info, cache[key][0]))
    best = [_summary_row(fit, "best") for fit in fits]
    last = [_summary_row(fit, "last") for fit in fits]
    deltas, errors, counts = _contrasts(fits)
    result = {"status": "complete", "protocol": "paper_kfold", "score_role": "cv_validation",
              "scope": "four tasks, prespecified fold 0 only; not full K-fold or independent test",
              "accepted_fits": len(fits), "plan_sha256": sha256(plan_path),
              "primary_checkpoint": "best", "secondary_checkpoint": "last",
              "metrics_independently_recomputed": True, "targets_and_ids_match_frozen_E2": True,
              "paired_counts": counts,
              "accepted": [{"task_id": fit["job"]["task_id"], "variant": fit["job"]["variant"],
                            "attempt": fit["attempt"], "receipt_sha256": fit["receipt_sha256"],
                            "attempt_records": fit["attempts"]} for fit in fits],
              "limitations": ["Same validation fold selects and scores best.",
                              "No mean across tasks, no single-fold standard deviation or significance claim.",
                              "Node metrics use HCG nodes, not deduplicated source lines.",
                              "Report verifies checkpoint bytes and accepted roundtrip records; it does not rerun models."]}
    text = ["# Stage G fold-0 pilot results", "",
            "All primary values are **CV validation**, selected by minimum validation loss and scored on the same fold.",
            "These are four separate tasks, not an independent test or a complete K-fold experiment.", "",
            "| Task | Variant | Best Buggy-F1 | Best Macro-F1 | Precision | Recall | Best epoch (0-based) |",
            "|---|---|---:|---:|---:|---:|---:|"]
    for row in best:
        text.append("| {task_id} | {variant} | {buggy_f1:.4f} | {macro_f1:.4f} | {precision:.4f} | {recall:.4f} | {best_epoch} |".format(**row))
    text += ["", "Last checkpoints are auxiliary and appear separately in last_summary.csv.",
             "paired_deltas.csv reports percentage-point differences; error_changes.csv includes prediction flips and probability-only changes.",
             "No task-average, standard deviation, significance, or generalization claim is computed.", ""]
    error_columns = ["task_id", "cohort", "task", "fold", "checkpoint", "contrast", "score_role",
                     "file", "target", "original_graph_node_id", "node_type", "before_prediction",
                     "after_prediction", "before_positive_probability", "after_positive_probability",
                     "probability_delta", "prediction_changed", "transition"]
    outputs = {"summary.csv": _csv(best), "last_summary.csv": _csv(last),
               "paired_deltas.csv": _csv(deltas), "error_changes.csv": _csv(errors, error_columns),
               "report.json": json.dumps(result, indent=2, ensure_ascii=False) + "\n",
               "report.md": "\n".join(text)}
    # Validate all fits before writing anything; never replace a differing report.
    for name, contents in outputs.items():
        path = output / name
        if path.exists() and path.read_text(encoding="utf8") != contents:
            raise FileExistsError("Refusing to overwrite differing report: " + str(path))
    for name, contents in outputs.items():
        path = output / name
        if not path.exists():
            path.write_text(contents, encoding="utf8")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    summarize(parser.parse_args().output)
