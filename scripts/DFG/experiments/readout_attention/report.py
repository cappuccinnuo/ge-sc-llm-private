"""Frozen-prediction 2x2 contract readout report, reusing accepted CV metrics."""
import math
from collections import defaultdict
from pathlib import Path
from scripts.DFG.experiments.common import read_json, write_json, sha256, metrics
from scripts.DFG.experiments.e23_cv.report import aggregate, pooled, compare_rows, METRICS
from scripts.DFG.experiments.overall_cv.report import expected_population, checked_predictions, csv_write

GRAPHS = ("HCG", "HCG_DDG_GUARD")
READOUTS = ("mean", "attention")
CHECKPOINTS = ("best", "last")
CELLS = tuple((graph, readout) for graph in GRAPHS for readout in READOUTS)
CONTRASTS = (
    (("HCG", "mean"), ("HCG", "attention")),
    (("HCG_DDG_GUARD", "mean"), ("HCG_DDG_GUARD", "attention")),
    (("HCG", "mean"), ("HCG_DDG_GUARD", "mean")),
    (("HCG", "attention"), ("HCG_DDG_GUARD", "attention")),
)


def cell_name(cell):
    return cell[0] + ":" + cell[1]


def assert_comparable(current, historical, variant):
    """Reject data or numeric-training changes hidden by a new readout name."""
    fields = ("task_id", "task", "cohort", "fold", "split", "fit_seed",
              "labels_sha256", "feature", "source_prepared_manifest_sha256",
              "source_splits_sha256")
    for key in fields:
        if current[key] != historical[key]:
            raise ValueError("Historical comparison differs: " + key)
    # A readout description is bookkeeping, not a training hyperparameter.
    a = {k: v for k, v in current["config"].items() if k != "readout"}
    b = {k: v for k, v in historical["config"].items() if k != "readout"}
    if a != b:
        raise ValueError("Historical numeric/evaluation configuration differs")
    if current["graphs"][variant]["sha256"] != historical["graphs"][variant]["sha256"]:
        raise ValueError("Historical graph differs")
    if current["task"] != "contract":
        raise ValueError("This experiment reports contract tasks only")


def _checked_manifest(plan, task_id, fold):
    matches = [r for r in plan["tasks"] if r["task_id"] == task_id and r["fold"] == fold]
    if len(matches) != 1:
        raise ValueError("Missing or duplicate task manifest")
    ref = matches[0]
    if sha256(ref["manifest"]) != ref["sha256"]:
        raise ValueError("Manifest digest mismatch")
    info = read_json(ref["manifest"])
    if info["task_id"] != task_id or info["fold"] != fold or info["task"] != "contract":
        raise ValueError("Manifest identity/task mismatch")
    return info


def _validate_fit(fit):
    info, job, result = fit["info"], fit["job"], fit["result"]
    if info["task"] != "contract" or fit["readout"] not in READOUTS or job["variant"] not in GRAPHS:
        raise ValueError("Unexpected task, readout or graph")
    if any(job[k] != info[k] for k in ("task_id", "fold")):
        raise ValueError("Fit manifest identity mismatch")
    if result["status"] != "complete" or result["score_role"] != "cv_validation":
        raise ValueError("Unfinished fit or mixed score role")
    if result["checkpoint_roundtrip_exact"] != {"best": True, "last": True}:
        raise ValueError("Checkpoint reload verification failed")
    if not 1 <= result["history_rows"] <= 50:
        raise ValueError("Invalid epoch count")
    if not 0 <= result["best_epoch"] <= result["last_epoch"] < result["history_rows"]:
        raise ValueError("Invalid best/last epoch identity")
    if set(info["split"]["train_files"]) & set(info["split"]["val_files"]):
        raise ValueError("Training/validation overlap")
    pred = checked_predictions(fit["predictions"], fit["expected"])
    if any(r.get("original_graph_node_id") is not None for r in pred):
        raise ValueError("Node predictions cannot be reported as contracts")
    scores = {}
    for checkpoint in CHECKPOINTS:
        scores[checkpoint] = metrics([r["target"] for r in pred], [r[checkpoint] for r in pred])
        if scores[checkpoint] != result["cv_validation"][checkpoint]:
            raise ValueError("Independent metric mismatch")
    for row in pred:
        source = fit["sources"].get(row["file"])
        if not source or not source.get("sha256"):
            raise ValueError("Source identity is missing")
    return pred, scores


def _trend_counts(statistics, rows, group_keys, metrics_to_count):
    for summary in statistics:
        group = [r for r in rows if all(r[k] == summary[k] for k in group_keys)]
        for metric in metrics_to_count:
            values = [r[metric + "_delta_pp"] for r in group]
            summary[metric + "_improved"] = sum(v > 1e-10 for v in values)
            summary[metric + "_tied"] = sum(abs(v) <= 1e-10 for v in values)
            summary[metric + "_declined"] = sum(v < -1e-10 for v in values)


def build_tables(fits, tasks, expected_files):
    """Validate a complete 5-fold 2x2 population before producing any table."""
    if not tasks or len(set(tasks)) != len(tasks):
        raise ValueError("Empty or duplicate tasks")
    index = {}
    for fit in fits:
        job = fit["job"]
        key = (job["task_id"], job["fold"], job["variant"], fit["readout"])
        if key in index:
            raise ValueError("Duplicate fit")
        index[key] = fit
    expected = {(task, fold, graph, readout) for task in tasks for fold in range(5)
                for graph, readout in CELLS}
    if set(index) != expected:
        raise ValueError("Incomplete or unexpected 2x2 fit matrix")
    rows, deltas, changes, interactions, pools, oof = [], [], [], [], [], []
    resources, relation_rows, file_rows, readout_rows = [], [], [], []
    for task in tasks:
        all_predictions = {cell: {} for cell in CELLS}
        for fold in range(5):
            scores, predictions = {}, {}
            reference_sources = None
            for cell in CELLS:
                graph, readout = cell
                fit = index[(task, fold, graph, readout)]
                pred, score = _validate_fit(fit)
                sources = {r["file"]: fit["sources"][r["file"]]["sha256"] for r in pred}
                if reference_sources is None:
                    reference_sources = sources
                elif sources != reference_sources:
                    raise ValueError("Paired source identity mismatch")
                all_predictions[cell][fold] = pred
                predictions[cell], scores[cell] = pred, score
                result, info = fit["result"], fit["info"]
                identity = dict(task_id=task, cohort=info["cohort"], task="contract", fold=fold,
                                variant=graph, readout=readout, cell=cell_name(cell))
                for checkpoint in CHECKPOINTS:
                    rows.append(dict(identity, checkpoint=checkpoint, score_role="cv_validation",
                                     historical_reuse=readout == "mean", **score[checkpoint],
                                     best_epoch=result["best_epoch"], last_epoch=result["last_epoch"]))
                    for row in pred:
                        file_rows.append(dict(identity, checkpoint=checkpoint, file=row["file"],
                            source_sha256=sources[row["file"]], target=row["target"], prediction=row[checkpoint],
                            error=row[checkpoint] != row["target"],
                            false_positive=int(row[checkpoint] == 1 and row["target"] == 0),
                            false_negative=int(row[checkpoint] == 0 and row["target"] == 1)))
                oof.extend(dict(identity, source_sha256=sources[r["file"]], **r) for r in pred)
                resource = result["resource"]
                resources.append(dict(identity, historical_reuse=readout == "mean", parameters=result["parameters"],
                    epochs=result["history_rows"], best_epoch=result["best_epoch"], last_epoch=result["last_epoch"],
                    seconds=result["wall_seconds_monotonic"],
                    peak_allocated_mib=resource["peak_allocated_bytes"] / 1048576,
                    peak_reserved_mib=resource["peak_reserved_bytes"] / 1048576,
                    minimum_card_free_mib=resource["card"]["minimum_whole_card_free_mib"],
                    checkpoint_roundtrip_exact=True, accepted_attempt=fit["folder"]))
                by_relation = defaultdict(list)
                for epoch in result["gradient_audit"]["epochs"]:
                    for item in epoch["enhancement_relations"]:
                        by_relation[tuple(item["canonical"])].append(item)
                    # Preserve the worker's actual audit, not an invented mean-model zero.
                    if "readout" in epoch:
                        readout_rows.append(dict(identity, epoch=epoch["epoch"], audit=epoch["readout"]))
                for canonical, sequence in sorted(by_relation.items()):
                    if any(not math.isfinite(r["message_gradient_l1"]) for r in sequence):
                        raise ValueError("Nonfinite relation gradient")
                    if len({(r["train_edges"], r["val_edges"]) for r in sequence}) != 1:
                        raise ValueError("Relation support changed during training")
                    relation_rows.append(dict(identity, canonical=list(canonical), relation=canonical[1],
                        train_edges=sequence[0]["train_edges"], val_edges=sequence[0]["val_edges"],
                        max_message_gradient_l1=max(r["message_gradient_l1"] for r in sequence),
                        observed_nonzero_gradient=any(r["message_gradient_l1"] > 0 for r in sequence),
                        has_training_support=sequence[0]["train_edges"] > 0))
            for before, after in CONTRASTS:
                for checkpoint in CHECKPOINTS:
                    prefix = dict(task_id=task, fold=fold, checkpoint=checkpoint,
                                  contrast=cell_name(after) + "-" + cell_name(before), score_role="cv_validation")
                    counts, details = compare_rows(predictions[before], predictions[after], prefix)
                    deltas.append(dict(prefix, **counts, **{m + "_delta_pp": scores[after][checkpoint][m] -
                                  scores[before][checkpoint][m] for m in METRICS}))
                    changes.extend(dict(r, source_sha256=reference_sources[r["file"]]) for r in details)
            for checkpoint in CHECKPOINTS:
                interactions.append(dict(task_id=task, fold=fold, checkpoint=checkpoint, score_role="cv_validation",
                    contrast="(GUARD_attention-HCG_attention)-(GUARD_mean-HCG_mean)",
                    **{m + "_delta_pp": (scores[(GRAPHS[1], "attention")][checkpoint][m] -
                                         scores[(GRAPHS[0], "attention")][checkpoint][m]) -
                                        (scores[(GRAPHS[1], "mean")][checkpoint][m] -
                                         scores[(GRAPHS[0], "mean")][checkpoint][m]) for m in METRICS}))
        for cell, fold_rows in all_predictions.items():
            score, joined = pooled(fold_rows, 5)
            if {r["file"] for r in joined} != set(expected_files[task]) or len(joined) != len(expected_files[task]):
                raise ValueError("Incomplete OOF file coverage")
            for checkpoint in CHECKPOINTS:
                pools.append(dict(task_id=task, variant=cell[0], readout=cell[1], cell=cell_name(cell),
                    checkpoint=checkpoint, score_role="pooled_cv_validation_oof", **score[checkpoint]))
    stats = aggregate(rows, ("task_id", "variant", "readout", "cell", "checkpoint"))
    keys = ("task_id", "checkpoint", "contrast")
    delta_metrics = tuple(m + "_delta_pp" for m in METRICS)
    paired = aggregate(deltas, keys, delta_metrics)
    interaction_stats = aggregate(interactions, keys, delta_metrics)
    _trend_counts(paired, deltas, keys, ("buggy_f1", "macro_f1"))
    _trend_counts(interaction_stats, interactions, keys, ("buggy_f1", "macro_f1"))
    return {"fold_results.csv": rows, "best_fold_results.csv": [r for r in rows if r["checkpoint"] == "best"],
            "last_fold_results.csv": [r for r in rows if r["checkpoint"] == "last"],
            "fold_statistics.csv": stats, "paired_deltas.csv": deltas, "paired_statistics.csv": paired,
            "interaction_deltas.csv": interactions, "interaction_statistics.csv": interaction_stats,
            "pooled_oof.csv": pools, "oof_predictions.csv": oof, "prediction_changes.csv": changes,
            "file_error_analysis.csv": file_rows, "resources.csv": resources,
            "relation_support_gradients.csv": relation_rows, "readout_gradients.csv": readout_rows}


def summarize(output, tasks=None):
    from .common import verify_plan, TASKS
    from .checks import completed
    from scripts.DFG.experiments.guard_extension.common import verify_plan as guard_verify
    from scripts.DFG.experiments.guard_extension.archive import verify_archive
    from scripts.DFG.experiments.guard_extension.checks import completed as guard_completed
    from scripts.DFG.experiments.overall_cv.checks import completed as old_completed
    output = Path(output)
    plan = verify_plan(output)
    tasks = tuple(TASKS if tasks is None else tasks)
    if not tasks or len(set(tasks)) != len(tasks) or any(t not in TASKS for t in tasks):
        raise ValueError("Unknown or duplicate summary tasks")
    old_batch = Path(plan["source_batches"]["HCG"])
    guard_batch = Path(plan["source_batches"]["HCG_DDG_GUARD"])
    old_plan, archive = verify_archive(old_batch)
    guard_plan = guard_verify(guard_batch)
    if Path(guard_plan["source_batch"]).resolve() != old_batch.resolve():
        raise ValueError("Historical guard source batch differs")
    if guard_plan["source_plan_sha256"] != sha256(old_batch / "plan.json"):
        raise ValueError("Historical guard baseline plan differs")
    source = {"HCG": (old_batch, old_plan, old_completed),
              "HCG_DDG_GUARD": (guard_batch, guard_plan, guard_completed)}
    fits, expected_files, checked = [], {}, set()
    def checked_hash(path, expected):
        pair = (str(path), expected)
        if pair not in checked:
            if sha256(path) != expected:
                raise ValueError("Input digest differs: " + str(path))
            checked.add(pair)
    for task in tasks:
        for fold in range(5):
            info = _checked_manifest(plan, task, fold)
            checked_hash(info["labels_path"], info["labels_sha256"])
            checked_hash(info["source_prepared_manifest"], info["source_prepared_manifest_sha256"])
            checked_hash(info["source_splits_path"], info["source_splits_sha256"])
            sources = read_json(info["source_prepared_manifest"])["sources"]
            files = read_json(info["source_splits_path"])["files"]
            if len(set(files)) != len(files) or (task in expected_files and set(files) != set(expected_files[task])):
                raise ValueError("Split-file population changed")
            expected_files[task] = files
            expected = expected_population(info, None)
            for filename in info["split"]["val_files"]:
                checked_hash(sources[filename]["path"], sources[filename]["sha256"])
            for variant in GRAPHS:
                checked_hash(info["graphs"][variant]["path"], info["graphs"][variant]["sha256"])
                historical_batch, historical_plan, historical_completed = source[variant]
                historical_info = _checked_manifest(historical_plan, task, fold)
                assert_comparable(info, historical_info, variant)
                job = dict(task_id=task, fold=fold, variant=variant)
                for readout in READOUTS:
                    folder = (historical_completed(historical_batch, job, historical_plan) if readout == "mean"
                              else completed(output, job, plan))
                    if folder is None:
                        raise ValueError("Missing accepted fit: " + repr((task, fold, variant, readout)))
                    fits.append(dict(job=job, readout=readout, info=info, expected=expected, sources=sources,
                        folder=str(folder), result=read_json(folder / "result.json"),
                        predictions=read_json(folder / "cv_validation_predictions.json")))
    tables = build_tables(fits, tasks, expected_files)
    destination = output if tasks == tuple(TASKS) else output / "reports" / ("__".join(tasks))
    destination.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        csv_write(destination / name, rows)
    report = dict(status="complete", tasks=list(tasks), new_fits=len(tasks) * 10,
        reused_fits=len(tasks) * 10, formal_results=len(tasks) * 20,
        score_role="cv_validation", independent_test=False,
        statistics=tables["fold_statistics.csv"], paired=tables["paired_statistics.csv"],
        interaction=tables["interaction_statistics.csv"], pooled_oof=tables["pooled_oof.csv"],
        historical_archive_plan_sha256=archive["plan_sha256"], plan_sha256=sha256(output / "plan.json"),
        interpretation="Equal-fold means and sample SD; best selected and scored on the same validation fold; source-file unit.",
        causal_limit="Readout changes pooling, added parameters and optimization trajectories; interaction is descriptive, not isolated semantic causality.",
        limitations=["One frozen seed; fold SD is not repeated-seed variance.",
                     "Pooled CV OOF is not independent test performance.",
                     "No node-level training or source-line evaluation in this batch."],
        failures=[str(p.relative_to(output)) for p in (output / "runs").rglob("*.failure.json")])
    write_json(destination / "report.json", report)
    print("SUMMARY_ACCEPTED", list(tasks), report["new_fits"], "new", report["reused_fits"], "reused", flush=True)
    return dict(tasks=list(tasks), new_fits=report["new_fits"], reused_fits=report["reused_fits"], output=str(destination))
