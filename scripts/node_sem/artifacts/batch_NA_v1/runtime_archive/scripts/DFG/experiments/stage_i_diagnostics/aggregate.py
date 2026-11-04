"""Read-only fixed-checkpoint intervention summary, never a retraining ablation.

Reads the original compare_outputs metric contract and independently recomputes
all class metrics from identity-bound predictions. Fold means and pooled CV
validation are deliberately separate. Output is immutable except exact reruns.
"""
import csv
import hashlib
import io
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from scripts.DFG.experiments.common import metrics

CONDITIONS = ("N", "Z_D", "Z_S", "Z_C", "Z_SC", "Z_ALL")
METRICS = ("buggy_f1", "macro_f1", "precision", "recall")
VERSION = "stage-i-intervention-summary-v1"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(row, task):
    if task == "node":
        if "original_graph_node_id" not in row:
            raise ValueError("Missing node identity")
        value = row["original_graph_node_id"]
        return row["file"], type(value).__name__, json.dumps(value, sort_keys=True)
    return (row["file"],)


def _close(actual, expected, field, probability=False):
    if not isinstance(actual, (int, float)) or not math.isfinite(actual):
        raise ValueError("Nonfinite or invalid score: " + field)
    if not math.isclose(actual, expected, rel_tol=1e-6 if probability else 1e-10,
                        abs_tol=1e-7 if probability else 1e-9):
        raise ValueError("Prediction/score mismatch: " + field)


def _compare(rows, condition):
    truth = [r["target"] for r in rows]
    pred = [r[condition + "_pred"] for r in rows]
    original = [r["N_pred"] for r in rows]
    result = metrics(truth, pred)
    result["prediction_flips"] = sum(p != q for p, q in zip(pred, original))
    result["prediction_flip_fraction"] = result["prediction_flips"] / len(rows)
    result["corrected"] = sum(p == y and q != y for p, q, y in zip(pred, original, truth))
    result["introduced"] = sum(p != y and q == y for p, q, y in zip(pred, original, truth))
    differences = [abs(r[condition + "_prob"] - r["N_prob"]) for r in rows]
    result["probability_abs_mean"] = statistics.mean(differences)
    result["probability_abs_max"] = max(differences)
    result["probability_changed_count"] = sum(d > 1e-8 for d in differences)
    result["probability_change_threshold"] = 1e-8
    return result


def _check_gates(value, path=()):
    # Audit structure is owned by the replay runner. Never turn an explicit
    # failed gate into an accepted observation.
    if path == ("archive_replay", "probability_exact"):
        # Old archived_gate permits floating-point differences within its
        # predeclared tolerance. Exactness is descriptive, not a pass criterion.
        if not isinstance(value, bool):
            raise ValueError("Invalid archive probability exactness field")
        return
    if path == ("archive_replay",):
        from scripts.DFG.experiments.audit.ddg_diagnostics_v1.diagnostic_common import TOLERANCES
        if (not isinstance(value, dict) or value.get("predictions_exact") is not True or
                value.get("metrics_match") is not True):
            raise ValueError("Failed archive replay audit gate")
        difference = value.get("probability_abs_max")
        bound = TOLERANCES["archive_probability_atol"] + TOLERANCES["archive_probability_rtol"]
        if (not isinstance(difference, (int, float)) or not math.isfinite(difference) or
                difference < 0 or difference > bound):
            raise ValueError("Invalid archive probability difference")
    if value is False:
        raise ValueError("Failed replay audit gate")
    if isinstance(value, str) and value.lower() in ("failed", "fail", "error"):
        raise ValueError("Failed replay audit gate")
    if isinstance(value, dict):
        for name, child in value.items():
            _check_gates(child, path + (name,))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _check_gates(child, path + (i,))


def _receipt(job_dir, inputs):
    path = job_dir / "receipt.json"
    receipt = read(path)
    if receipt.get("status") != "passed":
        raise ValueError("Replay job has no passed receipt: " + str(job_dir))
    inputs[str(path)] = sha(path)
    artifacts = receipt.get("artifact_sha256")
    if not isinstance(artifacts, dict):
        raise ValueError("Receipt artifact SHA map missing")
    required = {checkpoint + "/" + name for checkpoint in ("best", "last")
                for name in ("scores.json", "predictions.json", "audit.json")}
    if not required <= set(artifacts):
        raise ValueError("Incomplete receipt artifact set")
    for relative, expected in artifacts.items():
        artifact = (job_dir / relative).resolve()
        try:
            artifact.relative_to(job_dir.resolve())
        except ValueError:
            raise ValueError("Receipt artifact outside replay job")
        if sha(artifact) != expected:
            raise ValueError("Replay artifact SHA mismatch: " + relative)
        inputs[str(artifact)] = expected
    return receipt


def _csv_bytes(rows, default_fields=()):
    stream = io.StringIO(newline="")
    fields = list(dict.fromkeys(k for row in rows for k in row)) or list(default_fields)
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (list, dict, tuple)) else v
                         for k, v in row.items()})
    return stream.getvalue().encode("utf8")


def _mean_sd(values):
    return statistics.mean(values), statistics.stdev(values) if len(values) > 1 else None


def summarize(output, expected_jobs):
    output = Path(output)
    jobs = list(expected_jobs)
    if not jobs:
        raise ValueError("No expected replay jobs")
    job_keys = [(j["task_id"], int(j["fold"]), j["variant"]) for j in jobs]
    if len(set(job_keys)) != len(job_keys):
        raise ValueError("Duplicate expected replay job")
    task_meta = {}
    for j in jobs:
        if j["variant"] not in ("E3a", "E3b") or j["task"] not in ("node", "contract"):
            raise ValueError("Unknown variant/task")
        if int(j["fold"]) < 0:
            raise ValueError("Invalid fold")
        meta = (j["task"], j["cohort"])
        if j["task_id"] in task_meta and task_meta[j["task_id"]] != meta:
            raise ValueError("Mixed task/cohort metadata")
        task_meta[j["task_id"]] = meta
    # The caller's frozen list defines coverage. Reject stray replay receipts.
    actual = {str(p.parent.relative_to(output / "replays"))
              for p in (output / "replays").glob("*/fold_*/*/receipt.json")}
    expected = {"{}/fold_{}/{}".format(*item) for item in job_keys}
    # Correct tuple ordering: task_id, fold, variant.
    if actual != expected:
        raise ValueError("Missing or unexpected replay jobs")
    inputs, folds, changed, file_rows = {}, [], [], []
    pooled_rows, pool_seen = defaultdict(list), defaultdict(set)
    identities, sources, validation_files = {}, {}, {}
    populations = {}
    for job in sorted(jobs, key=lambda j: (j["task_id"], int(j["fold"]), j["variant"])):
        directory = output / "replays" / job["task_id"] / ("fold_" + str(job["fold"])) / job["variant"]
        _receipt(directory, inputs)
        for checkpoint in ("best", "last"):
            folder = directory / checkpoint
            audit = read(folder / "audit.json")
            if "gates" not in audit:
                raise ValueError("Missing replay audit gates")
            _check_gates(audit["gates"])
            scores = read(folder / "scores.json")
            by_condition = {r["condition"]: r for r in scores}
            if len(by_condition) != len(scores) or set(by_condition) != set(CONDITIONS):
                raise ValueError("Missing or duplicate intervention condition")
            rows = read(folder / "predictions.json")
            if not rows:
                raise ValueError("Empty prediction population")
            seen = set()
            for row in rows:
                for field in ("task_id", "cohort", "fold", "variant"):
                    if row.get(field) != job[field]:
                        raise ValueError("Mixed prediction identity: " + field)
                if row.get("checkpoint") != checkpoint:
                    raise ValueError("Mixed checkpoint")
                if row.get("score_role", "cv_validation") != "cv_validation":
                    raise ValueError("Mixed scoring role")
                identity = key(row, job["task"])
                if identity in seen:
                    raise ValueError("Duplicate prediction identity")
                seen.add(identity)
                source = row.get("source_sha256")
                if not isinstance(source, str) or len(source) != 64 or any(x not in "0123456789abcdef" for x in source):
                    raise ValueError("Invalid source SHA")
                source_key = (job["cohort"], row["file"])
                if source_key in sources and sources[source_key] != source:
                    raise ValueError("Mixed source SHA")
                sources[source_key] = source
                file_key = (job["task_id"], row["file"])
                if file_key in validation_files and validation_files[file_key] != job["fold"]:
                    raise ValueError("File occurs in multiple validation folds")
                validation_files[file_key] = job["fold"]
                if row["target"] not in (0, 1):
                    raise ValueError("Nonbinary target")
                identity_key = (job["task_id"], identity)
                bound = (source, row["target"], job["fold"])
                if identity_key in identities and identities[identity_key] != bound:
                    raise ValueError("Changed source/target/fold identity")
                identities[identity_key] = bound
                for condition in CONDITIONS:
                    prediction, probability = row[condition + "_pred"], row[condition + "_prob"]
                    if prediction not in (0, 1) or not isinstance(probability, (int, float)):
                        raise ValueError("Invalid prediction/probability")
                    if not math.isfinite(probability) or not 0 <= probability <= 1:
                        raise ValueError("Nonfinite/out-of-range probability")
            population_key = (job["task_id"], job["fold"])
            if population_key in populations and populations[population_key] != seen:
                raise ValueError("Variant/checkpoint prediction populations differ")
            populations[population_key] = seen
            group = (job["task_id"], job["variant"], checkpoint)
            if pool_seen[group] & seen:
                raise ValueError("Duplicate pooled identity across folds")
            pool_seen[group].update(seen)
            pooled_rows[group].extend(rows)
            metadata = {k: job[k] for k in ("task_id", "task", "cohort", "fold", "variant")}
            metadata.update(checkpoint=checkpoint, score_role="cv_validation")
            baseline = _compare(rows, "N")
            files = defaultdict(list)
            for row in rows:
                files[row["file"]].append(row)
            for condition in CONDITIONS:
                value = _compare(rows, condition)
                reported = by_condition[condition]
                for field in ("n", "positive", "prediction_flips", "corrected", "introduced"):
                    if reported[field] != value[field]:
                        raise ValueError("Prediction/score mismatch: " + field)
                if reported["tn_fp_fn_tp"] != value["tn_fp_fn_tp"]:
                    raise ValueError("Confusion matrix mismatch")
                for field in METRICS + ("prediction_flip_fraction", "probability_abs_mean", "probability_abs_max"):
                    _close(reported[field], value[field], field, probability=field.startswith("probability_"))
                fold_row = dict(metadata, condition=condition, **value)
                fold_row.update({"delta_" + field + "_pp": value[field] - baseline[field] for field in METRICS})
                folds.append(fold_row)
                for file, subset in sorted(files.items()):
                    file_rows.append(dict(metadata, condition=condition, file=file,
                                          source_sha256=subset[0]["source_sha256"], **_compare(subset, condition)))
                if condition != "N":
                    for row in rows:
                        if row[condition + "_pred"] != row["N_pred"]:
                            changed.append(dict(metadata, condition=condition, file=row["file"],
                                original_graph_node_id=row.get("original_graph_node_id"),
                                source_sha256=row["source_sha256"], target=row["target"],
                                before_pred=row["N_pred"], after_pred=row[condition + "_pred"],
                                before_probability=row["N_prob"], after_probability=row[condition + "_prob"],
                                probability_delta=row[condition + "_prob"] - row["N_prob"],
                                status="corrected" if row[condition + "_pred"] == row["target"] else "introduced"))
    statistics_rows, pooled = [], []
    grouped = defaultdict(list)
    for row in folds:
        grouped[(row["task_id"], row["variant"], row["checkpoint"], row["condition"])].append(row)
    for (task_id, variant, checkpoint, condition), members in sorted(grouped.items()):
        task, cohort = task_meta[task_id]
        row = dict(task_id=task_id, task=task, cohort=cohort, variant=variant,
                   checkpoint=checkpoint, condition=condition, folds=len(members),
                   score_role="cv_validation", statistic="equal_weight_fold_mean_and_sample_sd")
        fields = list(METRICS) + ["delta_" + field + "_pp" for field in METRICS]
        fields += ["prediction_flips", "corrected", "introduced", "probability_abs_mean"]
        for field in fields:
            row[field + "_mean"], row[field + "_sd"] = _mean_sd([r[field] for r in members])
        for field in ("buggy_f1", "macro_f1"):
            ds = [r["delta_" + field + "_pp"] for r in members]
            row[field + "_improved_folds"] = sum(d > 1e-9 for d in ds)
            row[field + "_tied_folds"] = sum(abs(d) <= 1e-9 for d in ds)
            row[field + "_declined_folds"] = sum(d < -1e-9 for d in ds)
        statistics_rows.append(row)
    for (task_id, variant, checkpoint), rows in sorted(pooled_rows.items()):
        task, cohort = task_meta[task_id]
        baseline = _compare(rows, "N")
        for condition in CONDITIONS:
            value = _compare(rows, condition)
            row = dict(task_id=task_id, task=task, cohort=cohort, variant=variant,
                       checkpoint=checkpoint, condition=condition, score_role="cv_validation",
                       statistic="pooled_oof_not_independent_test", **value)
            row.update({"delta_" + field + "_pp": value[field] - baseline[field] for field in METRICS})
            pooled.append(row)
    report = {
        "version": VERSION, "status": "complete", "jobs": len(jobs),
        "checkpoint_replays": len(jobs) * 2, "conditions": list(CONDITIONS),
        "score_role": "cv_validation", "node_unit": "HCG_node_not_deduplicated_source_line",
        "metric_unit": "percent; contrasts are percentage points versus N at the same checkpoint",
        "interpretation": "fixed_checkpoint_message_zero_sensitivity_not_retraining_or_pure_semantic_causality",
        "independent_seed_repeats": False, "probability_change_threshold": 1e-8,
        "fold_statistics": statistics_rows, "pooled_oof": pooled,
        "changed_prediction_rows": len(changed), "per_file_rows": len(file_rows),
        "input_artifact_sha256": inputs,
        "files": {"folds": "intervention_fold_metrics.csv", "statistics": "intervention_statistics.csv",
                  "pooled": "intervention_pooled.csv", "per_file": "intervention_file_changes.csv",
                  "changed_predictions": "changed_predictions.csv"},
    }
    outputs = {
        "intervention_fold_metrics.csv": _csv_bytes(folds),
        "intervention_statistics.csv": _csv_bytes(statistics_rows),
        "intervention_pooled.csv": _csv_bytes(pooled),
        "intervention_file_changes.csv": _csv_bytes(file_rows),
        "changed_predictions.csv": _csv_bytes(changed, ("task_id", "task", "cohort", "fold", "variant",
            "checkpoint", "score_role", "condition", "file", "original_graph_node_id", "source_sha256",
            "target", "before_pred", "after_pred", "before_probability", "after_probability",
            "probability_delta", "status")),
        "REPORT_DATA.json": (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf8"),
    }
    for name, content in outputs.items():
        if (output / name).exists() and (output / name).read_bytes() != content:
            raise FileExistsError("Refuse inconsistent existing summary: " + name)
    for name, content in outputs.items():
        if not (output / name).exists():
            with (output / name).open("xb") as stream:
                stream.write(content)
    return report
