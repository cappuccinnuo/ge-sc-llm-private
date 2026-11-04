"""Aggregate Prompt 8C D fixed-checkpoint identifier interventions.

Requires the complete 100-job node matrix and the completed 150-fit archive
verification. No forward, training, checkpoint deserialization or selection.
Every row is matched by task + file + original node ID and raw-source SHA.
"""
import argparse
import collections
import math
from pathlib import Path
import statistics

from . import scoring as s

VERSION = "prompt8c-inference-summary-v1"
MODES = ("original", "renamed")
VIEWS = ("orig", "C1")
FLAGS = ("unchanged_features_verified", "graph_edges_unchanged",
         "frozen_nx_attributes_untouched", "weights_unchanged")
TOKEN_KEYS = ("scheme", "node_feature", "feature_size", "dtype", "add_special_tokens",
              "padding_id", "model", "revision", "tokenizer_class", "asset_hashes",
              "tokenization_truncation", "vector_truncation", "padding",
              "container")


def validate_report(report, job, plan_sha, task, entry, archived_rows, views):
    if (report.get("job") != job or report.get("plan_sha256") != plan_sha
            or report.get("gate_only") is not False or report.get("optimizer_steps") != 0):
        raise ValueError("Intervention job/plan/mode differs")
    if report.get("graph") != entry["graph"]:
        raise ValueError("Intervention graph differs")
    if not all(report.get(flag) is True for flag in FLAGS):
        raise ValueError("Intervention invariant check failed")
    expected = s.index_rows(archived_rows)
    observed = s.index_rows(report["predictions"])
    selected_views = {key: value for key, value in views.items() if value["fold"] == job["fold"]}
    if set(observed) != set(expected) or set(observed) != set(selected_views):
        raise ValueError("Intervention prediction/view identities differ")
    files = {key[0] for key in observed}
    source_refs = {name: task["record"]["sources"][name] for name in files}
    if report["source_refs"] != source_refs or set(report["mappings"]) != files:
        raise ValueError("Intervention source/mapping scope differs")
    changes, probability_changes = 0, 0
    for key, row in observed.items():
        original, view = expected[key], selected_views[key]
        if (row["source_sha256"] != source_refs[row["file"]]["sha256"]
                or view["source_sha256"] != row["source_sha256"]
                or row["target"] != original["target"] or row["target"] != view["orig"]
                or row["original_best"] != original["best"]
                or row["original_probability"] != original["best_positive_probability"]):
            raise ValueError("Intervention row source/target/archive differs")
        if row["renamed_best"] not in (0, 1):
            raise ValueError("Invalid renamed prediction")
        for field in ("original_probability", "renamed_probability"):
            if not isinstance(row[field], (int, float)) or not math.isfinite(row[field]) or not 0 <= row[field] <= 1:
                raise ValueError("Invalid intervention probability")
        changes += row["original_best"] != row["renamed_best"]
        probability_changes += row["original_probability"] != row["renamed_probability"]
    if report["changed_predictions"] != changes or report["changed_probabilities"] != probability_changes:
        raise ValueError("Reported intervention changes differ")
    changed_nodes = report["changed_nodes"]
    changed_index = s.index_rows(changed_nodes)
    if not set(changed_index) <= set(observed):
        raise ValueError("Changed features escape outer-test original nodes")
    for key, row in changed_index.items():
        if row["source_sha256"] != source_refs[key[0]]["sha256"]:
            raise ValueError("Changed feature source identity differs")
        if (row["replacements"] <= 0 or row["code_before_sha256"] == row["code_after_sha256"]
                or type(row["feature_changed"]) is not bool):
            raise ValueError("Invalid code/feature intervention record")
    if (report["changed_code_count"] != len(changed_index)
            or report["changed_feature_count"] != sum(row["feature_changed"] for row in changed_nodes)):
        raise ValueError("Changed code/feature count differs")
    tokenizer = report["tokenizer"]
    feature = task["record"]["feature"]
    for key in TOKEN_KEYS:
        if key in feature and tokenizer.get(key) != feature[key]:
            raise ValueError("Frozen tokenizer recipe differs: " + key)
    # Frozen manifest and TokenEncoder use different exact explanatory strings.
    # Bind the known pair; do not reject unchanged execution due to prose alone.
    if "input_text" in feature and (
            feature["input_text"] != "node.code exactly as stored, including serialization if present"
            or tokenizer.get("input_text") != "code exactly as supplied; no unquoting or normalization"):
        raise ValueError("Tokenizer input text policy differs")
    if tokenizer.get("network_used") is not False or tokenizer.get("model_weights_loaded") is not False:
        raise ValueError("Unexpected tokenizer weights/network usage")
    return list(observed.values())


def metrics_for(rows, views, view, mode):
    return s.metric_counts(s.confusion(
        (views[s.identity(row)][view], row[mode + "_best"]) for row in rows))


def changes_for(rows, views, view):
    absolute = [abs(row["renamed_probability"] - row["original_probability"]) for row in rows]
    corrected, introduced = 0, 0
    for row in rows:
        target = views[s.identity(row)][view]
        old_correct = row["original_best"] == target
        new_correct = row["renamed_best"] == target
        corrected += not old_correct and new_correct
        introduced += old_correct and not new_correct
    return {
        "n": len(rows), "changed_predictions": sum(row["original_best"] != row["renamed_best"] for row in rows),
        "changed_probabilities": sum(row["original_probability"] != row["renamed_probability"] for row in rows),
        "mean_absolute_probability_change": statistics.mean(absolute) if absolute else None,
        "maximum_absolute_probability_change": max(absolute) if absolute else None,
        "corrected_errors": corrected, "introduced_errors": introduced,
        "net_errors_removed": corrected - introduced,
    }


def aggregate(task_id, profile, fold_reports, views):
    """Pure aggregation of one task/profile's complete outer-fold predictions."""
    folds = sorted(fold_reports)
    all_rows, seen = [], set()
    fold_rows, pooled, means, changes, file_changes = [], [], [], [], []
    for fold in folds:
        rows = fold_reports[fold]["predictions"]
        for row in rows:
            key = s.identity(row)
            if key in seen or key not in views or views[key]["fold"] != fold:
                raise ValueError("Repeated/misplaced OOF intervention node")
            seen.add(key)
        all_rows.extend(rows)
        by_file = collections.defaultdict(list)
        for row in rows:
            by_file[row["file"]].append(row)
        for view in VIEWS:
            old = metrics_for(rows, views, view, "original")
            new = metrics_for(rows, views, view, "renamed")
            for mode, metrics in (("original", old), ("renamed", new)):
                fold_rows.append(dict(task=task_id, profile=profile, fold=fold,
                                      view=view, mode=mode, checkpoint="best",
                                      score_role="outer_test", **metrics))
            changes.append(dict(task=task_id, profile=profile, fold=fold, view=view,
                                buggy_f1_delta_pp=new["buggy_f1"] - old["buggy_f1"],
                                precision_delta_pp=new["precision"] - old["precision"],
                                recall_delta_pp=new["recall"] - old["recall"],
                                **changes_for(rows, views, view)))
            for file, subset in sorted(by_file.items()):
                file_changes.append(dict(task=task_id, profile=profile, fold=fold,
                    file=file, source_sha256=subset[0]["source_sha256"], view=view,
                    **changes_for(subset, views, view)))
    if seen != set(views):
        raise ValueError("Incomplete OOF intervention population")
    pooled_changes = []
    for view in VIEWS:
        for mode in MODES:
            pooled.append(dict(task=task_id, profile=profile, view=view, mode=mode,
                checkpoint="best", score_role="outer_test", aggregation="pooled_OOF",
                **metrics_for(all_rows, views, view, mode)))
            matching = [row for row in fold_rows if row["view"] == view and row["mode"] == mode]
            mean = dict(task=task_id, profile=profile, view=view, mode=mode,
                        checkpoint="best", score_role="outer_test", n_folds=len(folds))
            for name in s.SCORE_NAMES:
                mean[name] = s._mean_sd(row[name] for row in matching)
            means.append(mean)
        pooled_changes.append(dict(task=task_id, profile=profile, view=view,
                                   **changes_for(all_rows, views, view)))
    resources = [{
        "task": task_id, "profile": profile, "fold": fold,
        "changed_code_count": fold_reports[fold]["changed_code_count"],
        "changed_feature_count": fold_reports[fold]["changed_feature_count"],
        "seconds": fold_reports[fold]["seconds"],
        "peak_allocated_bytes": fold_reports[fold]["peak_allocated_bytes"],
        "peak_reserved_bytes": fold_reports[fold]["peak_reserved_bytes"],
    } for fold in folds]
    return dict(fold_metrics=fold_rows, pooled_metrics=pooled, fold_means=means,
                fold_changes=changes, pooled_changes=pooled_changes,
                file_changes=file_changes, resources=resources)


def summarize(plan_path, views_path, output_dir_D, verification_path=None):
    plan_path, views_path, output_dir_D = map(
        lambda p: Path(p).resolve(), (plan_path, views_path, output_dir_D))
    verification_path = (Path(verification_path).resolve() if verification_path else
                         output_dir_D.parent / "verification_v2/verification.json")
    plan, verification = s.read(plan_path), s.read(verification_path)
    plan_sha = s.sha(plan_path)
    if s.read(plan_path.with_name("plan.seal.json"))["plan_sha256"] != plan_sha:
        raise ValueError("Frozen plan seal differs")
    if verification["plan_sha256"] != plan_sha or verification["verified"] != 150:
        raise ValueError("Complete 150-fit verification required")
    planned = {s.job_key(job): job for job in plan["jobs"] if
               plan["tasks"][job["task_id"]]["record"]["task"] == "node"}
    if len(planned) != 100:
        raise ValueError("Expected the complete 100-fit node intervention matrix")
    verified = {}
    for item in verification["fits"]:
        key = s.job_key(item["job"])
        if key in verified or item["status"] != "verified":
            raise ValueError("Invalid verification inventory")
        verified[key] = item
    if (len(verified) != 150 or set(verified) != {s.job_key(j) for j in plan["jobs"]}
            or not set(planned) <= set(verified)):
        raise ValueError("Missing verified node fits")
    reports = {}
    for path in sorted((output_dir_D / "jobs").glob("*.json")):
        report = s.read(path)
        key = s.job_key(report["job"])
        if key not in planned or key in reports:
            raise ValueError("Unexpected or duplicate D job")
        reports[key] = (path, report)
    if set(reports) != set(planned):
        raise ValueError("Incomplete D matrix: %d/100; summary not written" % len(reports))
    out = output_dir_D / "summary"
    if out.exists():
        raise FileExistsError(str(out))
    raw_views = s.read(views_path)
    audit = s.read(views_path.parent / "audit.json")
    if audit["node_views"] != s.ref(views_path) or audit["provenance"]["plan"]["sha256"] != plan_sha:
        raise ValueError("Label audit/view identity differs")
    views = {task_id: s.validate_views(task_id, plan["tasks"][task_id], value)
             for task_id, value in raw_views.items()}
    node_tasks = {key[0] for key in planned}
    if set(views) != node_tasks:
        raise ValueError("View task identity differs")
    gate_path = output_dir_D / "gate.json"
    gate = s.read(gate_path)
    if (gate.get("gate_only") is not True or gate.get("plan_sha256") != plan_sha
            or gate.get("archive_parity", {}).get("passed") is not True):
        raise ValueError("Unmodified archived parity gate is missing or failed")
    if s.job_key(gate["job"]) not in planned:
        raise ValueError("Gate does not belong to the fixed matrix")
    grouped = collections.defaultdict(dict)
    input_records = []
    for key, (path, report) in sorted(reports.items()):
        job, verified_fit = planned[key], verified[key]
        task = plan["tasks"][job["task_id"]]
        info = s.checked_json(task["prepared"]["%d/%d" % (job["fold"], job["seed"])])
        entry = info["profiles"][job["profile"]]
        attempt = Path(verified_fit["attempt"])
        if s.sha(attempt / "receipt.json") != verified_fit["receipt_sha256"]:
            raise ValueError("Verified receipt changed")
        receipt = s.read(attempt / "receipt.json")
        if receipt.get("job") != job or receipt["artifacts"] != verified_fit["artifacts"]:
            raise ValueError("Verified receipt identity changed")
        prediction_path = attempt / "outer_test_predictions.json"
        if s.sha(prediction_path) != receipt["artifacts"]["outer_test_predictions.json"]:
            raise ValueError("Verified predictions changed")
        sidecar_path = attempt / "best.json"
        if s.sha(sidecar_path) != receipt["artifacts"]["best.json"]:
            raise ValueError("Verified checkpoint sidecar changed")
        sidecar = s.read(sidecar_path)
        if (report["checkpoint_sha256"] != receipt["artifacts"]["best.pt"]
                or report["checkpoint_state_sha256"] != sidecar["state_sha256"]):
            raise ValueError("Intervention checkpoint differs")
        archived = s.read(prediction_path)
        validate_report(report, job, plan_sha, task, entry, archived, views[job["task_id"]])
        grouped[(job["task_id"], job["profile"])][job["fold"]] = report
        input_records.append(dict(job=job, intervention=s.ref(path),
                                  original_predictions=s.ref(prediction_path),
                                  receipt_sha256=verified_fit["receipt_sha256"]))
    result = dict(
        version=VERSION, status="complete", interventions=100,
        training_count=0, optimizer_steps=0, summary_forward_count=0,
        score_role="outer_test", checkpoint="best", views=list(VIEWS),
        inference_mode="held-out identifier feature intervention on frozen checkpoints; not retraining",
        hypothesis_tests_performed=False, model_selection_changed=False,
        bindings=dict(plan=s.ref(plan_path), views=s.ref(views_path),
                      label_audit=s.ref(views_path.parent / "audit.json"),
                      verification=s.ref(verification_path), gate=s.ref(gate_path)),
        inputs=input_records,
        fold_metrics=[], pooled_metrics=[], fold_means=[], fold_changes=[],
        pooled_changes=[], file_changes=[], resources=[])
    for (task_id, profile), fold_reports in sorted(grouped.items()):
        if set(fold_reports) != set(plan["tasks"][task_id]["folds"]):
            raise ValueError("Profile fold population differs")
        tables = aggregate(task_id, profile, fold_reports, views[task_id])
        for name, rows in tables.items():
            result[name].extend(rows)
    result["notes"] = [
        "orig and C1 use the same frozen predictions/identities; C1 is a diagnostic label view.",
        "No checkpoint selection, hyperparameter update, new p-value or Holm family.",
        "Identifier intervention is a test-time distribution shift, not a causal proof of identifier-only learning.",
        "Environment-source features and original node labels were not rewritten.",
        "Probability changes and discrete prediction changes are reported separately.",
        "Complete-case summaries are written only after all 100 planned interventions pass identity checks.",
    ]
    out.mkdir(exist_ok=False)
    for name in ("fold_metrics", "pooled_metrics", "fold_means", "fold_changes",
                 "pooled_changes", "file_changes", "resources"):
        s._csv(out / (name + ".csv"), result[name])
    s.write(out / "summary.json", result)
    s.write(out / "receipt.json", dict(
        status="complete", version=VERSION, jobs=100, bindings=result["bindings"],
        artifacts={path.name: s.ref(path) for path in sorted(out.iterdir()) if path.is_file()}))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--views", required=True)
    parser.add_argument("--output-dir-D", required=True)
    parser.add_argument("--verification")
    args = parser.parse_args()
    result = summarize(args.plan, args.views, args.output_dir_D, args.verification)
    print("Summarized %d fixed-checkpoint interventions" % result["interventions"])


if __name__ == "__main__":
    main()
