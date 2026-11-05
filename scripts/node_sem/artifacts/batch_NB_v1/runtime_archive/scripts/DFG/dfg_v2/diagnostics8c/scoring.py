"""Prompt 8C B: independent descriptive rescoring of frozen predictions.

No checkpoint loading, model forward, optimization or label-file mutation.
C1/C2 are diagnostic views from A, not new ground truth. Node identity is
task-scoped (file, original_graph_node_id); source SHA and frozen fold are checked.
Non-SolidiFI strata have pooled counts and Wilson precision/recall intervals only,
never fold averages. No new hypothesis tests or Holm family are introduced.
"""
import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

VERSION = "prompt8c-sensitive-rescore-v1"
VIEWS = ("orig", "C1", "C2")
STRATA = ("all", "SolidiFI", "nonSolidiFI")
SCORE_NAMES = ("buggy_f1", "macro_f1", "precision", "recall")
LEXICAL = "lexical_identifier_rule"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def write(path, value):
    with Path(path).open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def ref(path):
    return {"path": str(Path(path).resolve()), "sha256": sha(path)}


def checked_json(reference):
    if sha(reference["path"]) != reference["sha256"]:
        raise ValueError("Input SHA differs: " + reference["path"])
    return read(reference["path"])


def identity(row):
    return row["file"], row.get("original_graph_node_id")


def job_key(job):
    return job["task_id"], job["fold"], job["seed"], job["profile"]


def index_rows(rows):
    result = {}
    for row in rows:
        key = identity(row)
        if key in result:
            raise ValueError("Duplicate prediction identity")
        result[key] = row
    return result


def confusion(pairs):
    counts = dict(tn=0, fp=0, fn=0, tp=0)
    for target, prediction in pairs:
        if target not in (0, 1) or prediction not in (0, 1):
            raise ValueError("Binary labels and predictions required")
        key = (("tn", "fp"), ("fn", "tp"))[target][prediction]
        counts[key] += 1
    return counts


def metric_counts(counts):
    tn, fp, fn, tp = (counts[key] for key in ("tn", "fp", "fn", "tp"))
    n = tn + fp + fn + tp
    if not n:
        return dict(counts, n=0, positive=0, buggy_f1=None, macro_f1=None,
                    precision=None, recall=None, tn_fp_fn_tp=[tn, fp, fn, tp])
    positive_f1 = 2.0 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    negative_f1 = 2.0 * tn / (2 * tn + fp + fn) if 2 * tn + fp + fn else 0.0
    return dict(counts, n=n, positive=tp + fn, buggy_f1=100 * positive_f1,
                macro_f1=50 * (positive_f1 + negative_f1),
                precision=100.0 * tp / (tp + fp) if tp + fp else 0.0,
                recall=100.0 * tp / (tp + fn) if tp + fn else 0.0,
                tn_fp_fn_tp=[tn, fp, fn, tp])


def wilson(successes, trials):
    if trials == 0:
        return None
    if not 0 <= successes <= trials:
        raise ValueError("Invalid binomial count")
    z = 1.959963984540054
    p = float(successes) / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return [100 * max(0.0, center - half), 100 * min(1.0, center + half)]


def scored_pairs(rows, node_views, view, stratum):
    for row in rows:
        node = node_views.get(identity(row)) if node_views is not None else None
        solidifi = bool(node["solidifi"]) if node is not None else bool(
            re.fullmatch(r"buggy_\d+\.sol", row["file"]))
        if stratum == "SolidiFI" and not solidifi:
            continue
        if stratum == "nonSolidiFI" and solidifi:
            continue
        if view == "C2" and not node["C2_include"]:
            continue
        target = node[view] if node is not None else row["target"]
        yield int(target), int(row["best"])


def _mean_sd(values):
    values = list(values)
    return {"mean": statistics.mean(values) if values else None,
            "sample_sd": statistics.stdev(values) if len(values) > 1 else None,
            "n_folds": len(values)}


def summarize_task(task_id, granularity, profiles, node_views):
    """Pure task-scoped scoring. Profiles map profile -> fold -> prediction rows."""
    views = VIEWS if granularity == "node" else ("orig",)
    if granularity == "node" and node_views is None:
        raise ValueError("Node views required")
    expected_folds = sorted(profiles["G0"])
    if any(sorted(folds) != expected_folds for folds in profiles.values()):
        raise ValueError("Inconsistent profile fold inventories")
    if granularity == "node":
        lexical = {}
        for fold, rows in profiles["G0"].items():
            lexical[fold] = [dict(row, best=node_views[identity(row)]["lexical_prediction"])
                             for row in rows]
        profiles = dict(profiles, **{LEXICAL: lexical})
    fold_metrics, pooled_metrics, fold_means, paired, paired_folds = [], [], [], [], []
    for view in views:
        for stratum in STRATA:
            per_profile = {}
            for profile, folds in sorted(profiles.items()):
                all_counts = dict(tn=0, fp=0, fn=0, tp=0)
                values = {}
                for fold in expected_folds:
                    counts = confusion(scored_pairs(folds[fold], node_views, view, stratum))
                    metrics = metric_counts(counts)
                    values[fold] = metrics
                    for name in all_counts:
                        all_counts[name] += counts[name]
                    if stratum != "nonSolidiFI":
                        fold_metrics.append(dict(
                            task=task_id, profile=profile, fold=fold, view=view,
                            stratum=stratum, checkpoint="best", score_role="outer_test",
                            **metrics))
                pmetrics = metric_counts(all_counts)
                pooled_metrics.append(dict(
                    task=task_id, profile=profile, view=view, stratum=stratum,
                    checkpoint="best", score_role="outer_test", aggregation="pooled_OOF",
                    precision_wilson_95=wilson(all_counts["tp"], all_counts["tp"] + all_counts["fp"]),
                    recall_wilson_95=wilson(all_counts["tp"], all_counts["tp"] + all_counts["fn"]),
                    interval_unit="percent; Wilson applied to P/R counts, not F1",
                    interval_caveat="descriptive node-count interval; ignores file/clone correlation",
                    **pmetrics))
                per_profile[profile] = values
                if stratum != "nonSolidiFI":
                    row = dict(task=task_id, profile=profile, view=view, stratum=stratum,
                               checkpoint="best", score_role="outer_test",
                               expected_folds=len(expected_folds),
                               empty_fold_ids=[f for f in expected_folds if not values[f]["n"]])
                    for score in SCORE_NAMES:
                        row[score] = _mean_sd(values[f][score] for f in expected_folds
                                             if values[f][score] is not None)
                    fold_means.append(row)
            if stratum == "nonSolidiFI":
                continue
            for profile in sorted(set(per_profile) - {"G0"}):
                for score in SCORE_NAMES:
                    changes = []
                    empty_folds = []
                    for fold in expected_folds:
                        a = per_profile["G0"][fold][score]
                        b = per_profile[profile][fold][score]
                        delta = None if a is None or b is None else b - a
                        paired_folds.append(dict(
                            task=task_id, profile=profile, baseline="G0",
                            view=view, stratum=stratum, metric=score, fold=fold,
                            baseline_value=a, profile_value=b, delta_pp=delta))
                        if delta is None:
                            empty_folds.append(fold)
                        else:
                            changes.append(delta)
                    paired.append(dict(
                        task=task_id, profile=profile, baseline="G0", view=view,
                        stratum=stratum, checkpoint="best", metric=score,
                        expected_folds=len(expected_folds), empty_fold_ids=empty_folds,
                        improved=sum(x > 1e-12 for x in changes),
                        tied=sum(abs(x) <= 1e-12 for x in changes),
                        declined=sum(x < -1e-12 for x in changes),
                        test_performed=False, **_mean_sd(changes)))
    return dict(fold_metrics=fold_metrics, pooled_metrics=pooled_metrics,
                fold_means=fold_means, paired=paired, paired_folds=paired_folds)


def validate_views(task_id, task, raw_views):
    indexed = {}
    sources = task["record"]["sources"]
    expected_folds = set(task["folds"])
    for view in raw_views:
        key = identity(view)
        if key in indexed:
            raise ValueError("Duplicate label-view identity")
        if view["file"] not in sources or view["source_sha256"] != sources[view["file"]]["sha256"]:
            raise ValueError("Label view source SHA differs: " + task_id)
        if view["fold"] not in expected_folds:
            raise ValueError("Label view fold differs")
        if view.get("node_id") != view["original_graph_node_id"]:
            raise ValueError("Label view node identity differs")
        if (any(view[k] not in (0, 1) for k in ("orig", "C1", "C2", "lexical_prediction"))
                or type(view["C2_include"]) is not bool or type(view["solidifi"]) is not bool):
            raise ValueError("Invalid binary/include label view")
        if view["solidifi"] != bool(re.fullmatch(r"buggy_\d+\.sol", view["file"])):
            raise ValueError("Cohort diagnostic classification differs")
        if view["C1"] != view["C2"]:
            raise ValueError("C2 must exclude, not flip labels")
        if view["node_type"] == "env_source":
            raise ValueError("Auxiliary environment node cannot be scored")
        indexed[key] = view
    return indexed


def validate_task_predictions(task, profiles, views):
    """Check fold/source identity alignment independent of CSV/JSON row order."""
    files = set(task["record"]["graph_files"])
    expected_folds = set(task["folds"])
    if any(set(folds) != expected_folds for folds in profiles.values()):
        raise ValueError("Missing/duplicate fold population")
    granularity = task["record"]["task"]
    expected_views = set(views) if views is not None else None
    g0 = {}
    outer_files = set()
    for fold, rows in profiles["G0"].items():
        indexed = index_rows(rows)
        current_files = {r["file"] for r in rows}
        if outer_files & current_files:
            raise ValueError("File appears in multiple outer folds")
        outer_files |= current_files
        for key, row in indexed.items():
            if row.get("score_role") != "outer_test" or row["target"] not in (0, 1):
                raise ValueError("Prediction role/target differs")
            if row["best"] not in (0, 1):
                raise ValueError("Invalid prediction")
            if granularity == "node":
                if key not in views:
                    raise ValueError("Missing node label view")
                view = views[key]
                if (view["fold"] != fold or view["orig"] != row["target"]
                        or view["node_type"] != row["node_type"]):
                    raise ValueError("Node fold/type/original label differs")
            elif row.get("original_graph_node_id") is not None:
                raise ValueError("Unexpected graph prediction node ID")
            g0[key] = (fold, row)
    if outer_files != files:
        raise ValueError("Prediction file population differs")
    if expected_views is not None and set(g0) != expected_views:
        raise ValueError("Missing or extra label-view nodes")
    for profile, folds in profiles.items():
        seen = set()
        for fold, rows in folds.items():
            for key, row in index_rows(rows).items():
                if key in seen or key not in g0:
                    raise ValueError("Profile node identities differ")
                seen.add(key)
                old_fold, baseline = g0[key]
                if fold != old_fold:
                    raise ValueError("Profile file-fold assignment differs")
                for name in ("target", "score_role", "node_type"):
                    if row.get(name) != baseline.get(name):
                        raise ValueError("Profile frozen identity field differs: " + name)
                if row["best"] not in (0, 1):
                    raise ValueError("Invalid profile prediction")
        if seen != set(g0):
            raise ValueError("Profile population differs")


def _csv(path, rows):
    if not rows:
        return
    fields = sorted(set().union(*(set(row) for row in rows)))
    with Path(path).open("x", encoding="utf8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True)
                             if isinstance(v, (dict, list)) else v for k, v in row.items()})


def run_scoring(plan_path, views_path, verification_path, output_dir):
    plan_path, views_path = Path(plan_path).resolve(), Path(views_path).resolve()
    verification_path = Path(verification_path).resolve()
    plan = read(plan_path)
    if read(plan_path.with_name("plan.seal.json"))["plan_sha256"] != sha(plan_path):
        raise ValueError("Plan seal differs")
    verification = read(verification_path)
    if verification["plan_sha256"] != sha(plan_path) or verification["verified"] != len(plan["jobs"]):
        raise ValueError("Verification binding/count differs")
    jobs = {job_key(job): job for job in plan["jobs"]}
    if len(jobs) != len(plan["jobs"]):
        raise ValueError("Repeated planned job")
    verified = {}
    for item in verification["fits"]:
        key = job_key(item["job"])
        if key in verified or key not in jobs or item["status"] != "verified":
            raise ValueError("Incomplete or repeated verified job")
        if item["job"] != jobs[key]:
            raise ValueError("Verified job differs")
        verified[key] = item
    if set(verified) != set(jobs):
        raise ValueError("Missing verified jobs")
    node_views = read(views_path)
    view_audit = read(views_path.parent / "audit.json")
    if (view_audit["node_views"] != ref(views_path)
            or view_audit["provenance"]["plan"]["sha256"] != sha(plan_path)):
        raise ValueError("Label audit/view binding differs")
    expected_node_tasks = {t for t, task in plan["tasks"].items() if task["record"]["task"] == "node"}
    if set(node_views) != expected_node_tasks:
        raise ValueError("Label-view task population differs")
    out = Path(output_dir)
    if not out.parent.is_dir():
        raise ValueError("Artifact parent required")
    out.mkdir(exist_ok=False)
    result = dict(version=VERSION, score_role="outer_test", checkpoint="best",
                  sensitivity_only=True, training_count=0, model_forward_count=0,
                  Holm_performed=False, frozen_labels_changed=False,
                  bindings={"plan": ref(plan_path), "views": ref(views_path),
                            "label_audit": ref(views_path.parent / "audit.json"),
                            "verification": ref(verification_path)},
                  fold_metrics=[], pooled_metrics=[], fold_means=[], paired=[], paired_folds=[],
                  source_identity={}, prediction_inputs=[], original_metric_checks=[])
    for task_id, task in sorted(plan["tasks"].items()):
        profiles = {}
        source_refs = task["record"]["sources"]
        for name, reference in source_refs.items():
            if sha(reference["path"]) != reference["sha256"]:
                raise ValueError("Frozen source changed: " + name)
        result["source_identity"][task_id] = source_refs
        views = validate_views(task_id, task, node_views[task_id]) if task_id in node_views else None
        expected_profiles = set(plan["profiles"])
        for key, job in sorted(jobs.items()):
            if key[0] != task_id:
                continue
            item = verified[key]
            attempt = Path(item["attempt"])
            receipt_path = attempt / "receipt.json"
            if sha(receipt_path) != item["receipt_sha256"]:
                raise ValueError("Verified receipt changed")
            receipt = read(receipt_path)
            if receipt.get("job") != job or receipt["artifacts"] != item["artifacts"]:
                raise ValueError("Receipt job/artifacts changed")
            prediction_path = attempt / "outer_test_predictions.json"
            if sha(prediction_path) != item["artifacts"]["outer_test_predictions.json"]:
                raise ValueError("Verified predictions changed")
            rows = read(prediction_path)
            if job["fold"] in profiles.setdefault(job["profile"], {}):
                raise ValueError("Multiple seeds/fits must not be silently mixed")
            # Retain fields needed for identity/sensitivity, no model reload.
            profiles[job["profile"]][job["fold"]] = rows
            result["prediction_inputs"].append(dict(job=job, **ref(prediction_path)))
            observed = metric_counts(confusion((int(r["target"]), int(r["best"])) for r in rows))
            expected = item["outer_test"]["best"]
            for name in ("n", "positive", "tn_fp_fn_tp"):
                if observed[name] != expected[name]:
                    raise ValueError("Original metric count differs: " + name)
            maximum = max(abs(observed[name] - expected[name]) for name in SCORE_NAMES)
            if maximum > 1e-10:
                raise ValueError("Original metrics differ")
            result["original_metric_checks"].append(dict(job=job, max_abs_difference=maximum))
        if set(profiles) != expected_profiles:
            raise ValueError("Profile population differs")
        validate_task_predictions(task, profiles, views)
        tables = summarize_task(task_id, task["record"]["task"], profiles, views)
        for name, rows in tables.items():
            result[name].extend(rows)
    result["notes"] = [
        "orig retains frozen labels. C1/C2 are audit sensitivity views, not verified replacement ground truth.",
        "Contract labels have no node-level C1/C2 transformation; contract results use orig only.",
        "Lexical baseline is node-level only; no unrequested file-level aggregation rule is invented.",
        "All means weight available folds equally; empty fold IDs are explicit, never assigned artificial zero F1.",
        "nonSolidiFI strata use pooled counts and Wilson P/R intervals only, with no fold means or paired fold claims.",
        "Wilson intervals are descriptive binomial count intervals and ignore node/file/clone dependence.",
        "No new p-values or Holm family; these reports never replace the sealed primary results.",
        "No learning or checkpoint forward was performed in B.",
    ]
    for name in ("fold_metrics", "pooled_metrics", "fold_means", "paired", "paired_folds"):
        _csv(out / (name + ".csv"), result[name])
    write(out / "scores.json", result)
    write(out / "receipt.json", {
        "status": "complete", "version": VERSION, "bindings": result["bindings"],
        "fits": len(result["original_metric_checks"]),
        "original_max_abs_difference": max(x["max_abs_difference"] for x in result["original_metric_checks"]),
        "training_count": 0, "model_forward_count": 0,
        "artifacts": {p.name: ref(p) for p in sorted(out.iterdir()) if p.is_file()},
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--views", required=True)
    parser.add_argument("--verification", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run_scoring(args.plan, args.views, args.verification, args.output)
    print(json.dumps({name: len(result[name]) for name in
                      ("fold_metrics", "pooled_metrics", "fold_means", "paired", "paired_folds")}, indent=2))


if __name__ == "__main__":
    main()
