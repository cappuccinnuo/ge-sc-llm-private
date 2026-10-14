"""Independently validate/aggregate frozen-checkpoint diagnostics; no model loads.

This module never imports the runner or HGT, loads checkpoints, or performs a
graph forward. Only small prediction arrays are used for independent statistics.
All final outputs are exclusive-create and cannot overwrite prior diagnostics.
"""
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

from .diagnostic_common import (ROOT, RUN, PILOTS, REWIRING_SEEDS, PROTOCOL,
                                SCORE_ROLE, read_json, write_json, write_csv, file_sha)

METRICS = ("buggy_f1", "macro_f1", "precision", "recall")
KEYS = ("cohort", "task", "fold", "variant", "checkpoint", "condition")
NUMERIC_TOLERANCE = 1e-8


def read_csv(path):
    with Path(path).open(encoding="utf8", newline="") as handle:
        return list(csv.DictReader(handle))


def identity(row, task):
    if task == "node":
        value = row["original_graph_node_id"]
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            raise ValueError("Unsupported original node identity")
        return (row["file"], type(value).__name__, value)
    return (row["file"],)


def align_prediction_rows(rows, expected, task):
    lookup = {}
    for row in rows:
        key = identity(row, task)
        if key in lookup:
            raise ValueError("Duplicate prediction identity")
        lookup[key] = row
    keys = [identity(row, task) for row in expected]
    if len(set(keys)) != len(keys) or set(keys) != set(lookup):
        raise ValueError("Prediction identities differ")
    ordered = [lookup[key] for key in keys]
    if [r["target"] for r in ordered] != [r["target"] for r in expected]:
        raise ValueError("Prediction targets differ")
    return ordered


def classification_metrics(truth, predicted):
    if not truth or len(truth) != len(predicted):
        raise ValueError("Empty or misaligned prediction population")
    if set(truth) - {0, 1} or set(predicted) - {0, 1}:
        raise ValueError("Binary labels required")
    tn = sum(y == 0 and p == 0 for y, p in zip(truth, predicted))
    fp = sum(y == 0 and p == 1 for y, p in zip(truth, predicted))
    fn = sum(y == 1 and p == 0 for y, p in zip(truth, predicted))
    tp = sum(y == 1 and p == 1 for y, p in zip(truth, predicted))
    div = lambda n, d: n / d if d else 0.0
    f1 = div(2 * tp, 2 * tp + fp + fn)
    clean_f1 = div(2 * tn, 2 * tn + fp + fn)
    return dict(n=len(truth), positive=sum(truth),
                buggy_f1=100 * f1, macro_f1=50 * (f1 + clean_f1),
                precision=100 * div(tp, tp + fp), recall=100 * div(tp, tp + fn),
                tn_fp_fn_tp=[tn, fp, fn, tp])


def describe(values):
    a = np.asarray(values, dtype=np.float64).reshape(-1)
    if not len(a) or not np.isfinite(a).all():
        raise ValueError("Empty/nonfinite diagnostic comparison")
    return dict(n=int(len(a)), mean=float(a.mean()), median=float(np.median(a)),
                p95=float(np.percentile(a, 95)), max=float(a.max()),
                zero_fraction=float(np.mean(a == 0)))


def _validated_arrays(rows):
    a = np.asarray([row["logits"] for row in rows], dtype=np.float32)
    if a.shape != (len(rows), 2) or not np.isfinite(a).all():
        raise ValueError("Invalid exported logits")
    pred = a.argmax(axis=1)
    if pred.tolist() != [row["prediction"] for row in rows]:
        raise ValueError("Exported prediction differs from argmax")
    probability = torch.from_numpy(a).softmax(1)[:, 1].numpy()
    supplied = np.asarray([row["positive_probability"] for row in rows])
    if not np.allclose(probability, supplied, rtol=0, atol=1e-7):
        raise ValueError("Exported probabilities differ from logits")
    if any(row.get("score_role") != SCORE_ROLE for row in rows):
        raise ValueError("Unexpected prediction score role")
    return a, pred, probability


def independently_compare(rows, reference_rows, task):
    """Formula implementation independent of runner/common.compare_outputs."""
    rows = align_prediction_rows(rows, reference_rows, task)
    logits, pred, probability = _validated_arrays(rows)
    ref_logits, ref_pred, ref_probability = _validated_arrays(reference_rows)
    truth = np.asarray([row["target"] for row in rows], dtype=np.int64)
    flips = pred != ref_pred
    corrected = (ref_pred != truth) & (pred == truth)
    introduced = (ref_pred == truth) & (pred != truth)
    out = classification_metrics(truth.tolist(), pred.tolist())
    out.update(prediction_flips=int(flips.sum()),
               prediction_flip_fraction=float(flips.mean()),
               corrected=int(corrected.sum()), introduced=int(introduced.sum()),
               logits_exact=bool(np.array_equal(logits, ref_logits)),
               probabilities_exact=bool(np.array_equal(probability, ref_probability)),
               predictions_exact=bool(np.array_equal(pred, ref_pred)))
    for prefix, values in (("logit_abs", np.abs(logits-ref_logits)),
                           ("probability_abs", np.abs(probability-ref_probability))):
        out.update({prefix+"_"+k: v for k, v in describe(values).items()})
    by_file = []
    files = [row["file"] for row in rows]
    for file in sorted(set(files)):
        mask = np.asarray([f == file for f in files])
        by_file.append(dict(file=file, n=int(mask.sum()), flips=int(flips[mask].sum()),
                            corrected=int(corrected[mask].sum()),
                            introduced=int(introduced[mask].sum()),
                            probability_abs_mean=float(
                                np.abs(probability-ref_probability)[mask].mean())))
    return out, by_file


def _decode(raw):
    if not isinstance(raw, str):
        return raw
    if raw in ("True", "False"):
        return raw == "True"
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


def assert_same_statistics(actual, recorded):
    for key, value in actual.items():
        if key not in recorded:
            raise ValueError("Missing exported statistic: " + key)
        old = _decode(recorded[key])
        if isinstance(value, bool):
            if old is not value:
                raise ValueError("Boolean statistic differs: " + key)
        elif isinstance(value, list) or isinstance(value, int):
            if value != old:
                raise ValueError("Count/confusion differs: " + key)
        elif value is None:
            if old not in (None, ""):
                raise ValueError("Unexpected nonempty statistic: " + key)
        elif isinstance(value, float):
            if not isinstance(old, (float, int)) or not math.isclose(
                    value, old, rel_tol=NUMERIC_TOLERANCE, abs_tol=NUMERIC_TOLERANCE):
                raise ValueError("Numerical statistic differs: %s actual=%r stored=%r" %
                                 (key, value, old))
        elif value != old:
            raise ValueError("Statistic differs: " + key)


def validate_job_set(planned, pilot_found, remaining_found):
    """Completeness checks cannot silently drop missing or duplicated folds."""
    expected = {j["id"]: (j["cohort"], j["task"], int(j["fold"])) for j in planned}
    if len(expected) != 30:
        raise ValueError("Main diagnostic plan must contain 30 unique paired folds")
    counts = defaultdict(set)
    for _, (cohort, task, fold) in expected.items():
        counts[(cohort, task)].add(fold)
    required = {(c, t) for c in ("reentrancy_author", "access_control_author")
                for t in ("contract", "node")}
    if set(counts) != required:
        raise ValueError("Unexpected diagnostic task set")
    for key, folds in counts.items():
        if folds != set(range(5 if key[1] == "contract" else 10)):
            raise ValueError("Missing or duplicated planned fold")
    if len(set(pilot_found)) != len(pilot_found) or len(set(remaining_found)) != len(remaining_found):
        raise ValueError("Duplicate completed job")
    if set(pilot_found) & set(remaining_found):
        raise ValueError("Pilot best was recomputed or double-counted")
    if set(pilot_found) | set(remaining_found) != set(expected):
        raise ValueError("Incomplete or extra diagnostic folds")
    if {expected[j] for j in pilot_found} != set(PILOTS):
        raise ValueError("Predeclared seven pilot folds differ")
    return expected



def validation_rewiring_scope(audit, val_files, train_files):
    """Separate semantic changes in scored files from whole-forward changes.

    A replaced semantic edge is an old endpoint pair absent after rewiring.
    changed_eid_endpoints also includes EID permutations and is kept separate.
    No labels are read; only frozen file membership and rewiring group counts.
    """
    val = set(val_files)
    train = set(train_files)
    if len(val) != len(val_files) or len(train) != len(train_files) or val & train:
        raise ValueError("Invalid frozen train/val file partition")
    groups = audit["group_details"]
    if any(g["file"] not in val | train for g in groups):
        raise ValueError("Rewiring group outside frozen task files")
    for g in groups:
        if g["effective_semantic_perturbation"] != bool(g["replaced_semantic_edges"]):
            raise ValueError("Rewiring effective flag/count mismatch")
    for key in ("changed_eid_endpoints", "replaced_semantic_edges"):
        if sum(g[key] for g in groups) != audit[key]:
            raise ValueError("Rewiring total/group count mismatch")
    if sum(g["edge_count"] for g in groups) != audit["ddg_edges"]:
        raise ValueError("Rewiring total/group edge count mismatch")
    selected = [g for g in groups if g["file"] in val]
    changed = [g for g in selected if g["replaced_semantic_edges"] > 0]
    edges = sum(g["edge_count"] for g in selected)
    replaced = sum(g["replaced_semantic_edges"] for g in selected)
    changed_files = sorted({g["file"] for g in changed})
    all_ddg_files = sorted({g["file"] for g in selected})
    return dict(
        validation_files=len(val), validation_files_with_ddg=len(all_ddg_files),
        validation_files_with_semantic_perturbation=len(changed_files),
        validation_unchanged_files=len(val) - len(changed_files),
        validation_ddg_edges=edges, validation_replaced_semantic_edges=replaced,
        validation_changed_eid_endpoints=sum(g["changed_eid_endpoints"] for g in selected),
        validation_semantic_perturbation_fraction=replaced/edges if edges else 0.0,
        validation_groups=len(selected), validation_effective_groups=len(changed),
        validation_unchanged_groups=len(selected)-len(changed),
        validation_effective_files=changed_files,
        validation_ddg_files=all_ddg_files,
        training_ddg_edges=audit["ddg_edges"]-edges,
        training_replaced_semantic_edges=audit["replaced_semantic_edges"]-replaced,
        scope="frozen validation-file DDG edges only; whole-graph changes are reported separately",
        interpretation="Zero or tiny scored-file perturbation cannot establish semantic DDG irrelevance.")


def weighted_norm_summary(rows):
    """Node-weighted means ONLY from disjoint type rows, never pooled quantiles."""
    selected = [r for r in rows if r["file"] == "__all__" and
                r["branch"] != "canonical_relation_aggregate"]
    groups = defaultdict(list)
    for row in selected:
        key = tuple(row.get(k, "") for k in KEYS) + (str(row["layer"]), row["branch"])
        groups[key].append(row)
    result = []
    for key, values in sorted(groups.items()):
        types = [r["node_type"] for r in values]
        if len(types) != len(set(types)):
            raise ValueError("Duplicate type summary; refusing double-counted norms")
        count = sum(int(r["count"]) for r in values)
        population = sum(int(r["population_count"]) for r in values)
        zero = sum(int(r["zero_count"]) for r in values)
        near = sum(int(r["near_zero_count"]) for r in values)
        excluded = sum(int(r.get("denominator_near_zero_count", 0)) for r in values)
        valid = [r for r in values if int(r["count"]) > 0]
        mean = sum(float(r["mean"]) * int(r["count"]) for r in valid) / count if count else None
        maximum = max(float(r["max"]) for r in valid) if valid else None
        out = dict(zip(KEYS, key[:len(KEYS)]))
        out.update(layer=int(key[-2]), branch=key[-1], node_types=len(values),
                   count=count, population_count=population,
                   node_weighted_mean=mean, max=maximum, zero_count=zero,
                   zero_fraction=zero/count if count else None,
                   near_zero_fraction=near/count if count else None,
                   excluded_near_zero_denominator=excluded,
                   scope="all fixed task-graph nodes, train and validation",
                   global_median=None, global_p95=None,
                   quantile_note="Not reconstructible from per-type scalar summaries; see per-type CSV.")
        result.append(out)
    return result


def mean_sd(values):
    vals = [float(v) for v in values]
    return dict(n=len(vals), mean=statistics.mean(vals) if vals else None,
                sample_sd=statistics.stdev(vals) if len(vals) > 1 else None,
                min=min(vals) if vals else None, max=max(vals) if vals else None)


def summarize_conditions(rows, checkpoint="best", expected_counts=None):
    selected = [r for r in rows if r["checkpoint"] == checkpoint and
                r["condition"] != "E1_N_vs_E0_N"]
    grouped = defaultdict(list)
    for row in selected:
        grouped[(row["cohort"], row["task"], row["variant"], row["condition"])].append(row)
    output = []
    normals = {(r["cohort"], r["task"], int(r["fold"])): r for r in selected
               if r["variant"] == "E1" and r["condition"] == "N"}
    for key, group in sorted(grouped.items()):
        cohort, task, variant, condition = key
        folds = [int(r["fold"]) for r in group]
        if len(set(folds)) != len(folds):
            raise ValueError("Duplicate scored condition/fold")
        if expected_counts is not None and len(group) != expected_counts[(cohort, task)]:
            raise ValueError("Incomplete condition group")
        n = sum(r["n"] for r in group)
        row = dict(cohort=cohort, task=task, variant=variant, condition=condition,
                   checkpoint=checkpoint, folds=sorted(folds), equal_fold_metrics={},
                   pooled_count=n, pooled_confusion=[sum(r["tn_fp_fn_tp"][i] for r in group)
                                                    for i in range(4)],
                   prediction_flips=sum(r["prediction_flips"] for r in group),
                   prediction_flip_fraction_pooled=sum(r["prediction_flips"] for r in group)/n,
                   corrected=sum(r["corrected"] for r in group), introduced=sum(r["introduced"] for r in group),
                   probability_abs_mean_equal_fold=mean_sd([r["probability_abs_mean"] for r in group]),
                   probability_abs_mean_pooled=sum(r["probability_abs_mean"]*r["n"] for r in group)/n,
                   probability_changed_fraction_pooled=sum(
                       (1-r["probability_abs_zero_fraction"])*r["n"] for r in group)/n,
                   logit_abs_mean_equal_fold=mean_sd([r["logit_abs_mean"] for r in group]),
                   logit_abs_max=max(r["logit_abs_max"] for r in group),
                   folds_with_prediction_change=sum(not r["predictions_exact"] for r in group),
                   folds_with_probability_change=sum(not r["probabilities_exact"] for r in group),
                   folds_with_logit_change=sum(not r["logits_exact"] for r in group))
        for metric in METRICS:
            row["equal_fold_metrics"][metric] = mean_sd([r[metric] for r in group])
        if variant == "E1":
            row["paired_metric_delta_vs_E1_N_pp"] = {
                metric: mean_sd([r[metric] - normals[(cohort, task, int(r["fold"]))][metric]
                                 for r in group]) for metric in METRICS}
        output.append(row)
    return output


def _merge_csv(paths, output):
    fields = []
    for path in paths:
        with Path(path).open(encoding="utf8", newline="") as handle:
            for field in (csv.DictReader(handle).fieldnames or []):
                if field not in fields:
                    fields.append(field)
    with Path(output).open("x", encoding="utf8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for path in paths:
            with Path(path).open(encoding="utf8", newline="") as source:
                for row in csv.DictReader(source):
                    writer.writerow(row)


def _validate_checks(checks, checkpoint):
    for field in ("native_wrapper_exact", "restored_native_exact",
                  "original_input_restored", "parameter_identities_preserved"):
        if checks.get(field) is not True:
            raise ValueError("Checkpoint diagnostic check missing/failed: " + field)
    if checks["weights_sha256_before"] != checks["weights_sha256_after"]:
        raise ValueError("Diagnostic weights changed")
    if checkpoint != "initial":
        gate = checks.get("native_replay_gate") or {}
        if gate.get("predictions_exact") is not True or gate.get("metrics_match") is not True:
            raise ValueError("Native archive gate missing")


def aggregate(root=ROOT, run=RUN, write=True, pilot_output="pilot", remaining_output="remaining"):
    root, run = Path(root), Path(run)
    plan = read_json(run/"plan.json")
    for name in (pilot_output, remaining_output):
        if Path(name).name != name or name in (".", ".."):
            raise ValueError("Explicit stage output must be a directory basename")
    pilot = read_json(root/"forward"/pilot_output/"completion.json")
    remaining = read_json(root/"forward"/remaining_output/"completion.json")
    if pilot.get("status") != "passed" or remaining.get("status") != "passed":
        raise ValueError("Both diagnostic stages must complete before aggregation")
    expected = validate_job_set(plan["jobs"], pilot["jobs"], remaining["jobs"])
    planned_by_id = {j["id"]: j for j in plan["jobs"]}
    original_state = read_json(run/"state.json")
    source_paths = []
    split_scope_sources = []
    rewiring_validation_rows = []
    scored_rows, file_rows, message_global, parameters, rewiring = [], [], [], [], []
    csv_paths = defaultdict(list)
    checkpoint_count = 0
    for stage, directory_name, completed in (("pilot", pilot_output, pilot),
                                               ("remaining", remaining_output, remaining)):
        for job_id in completed["jobs"]:
            job_dir = root/"forward"/directory_name/job_id
            result = read_json(job_dir/"result.json")
            if result.get("status") != "passed" or (
                    result["job"]["cohort"], result["job"]["task"], result["job"]["fold"]) != expected[job_id]:
                raise ValueError("Result job binding/status mismatch")
            cohort, task, fold = expected[job_id]
            planned_job = planned_by_id[job_id]
            split_path = Path(planned_job["splits"])
            split_document = read_json(split_path)
            matching = [f for f in split_document["folds"] if f["fold"] == fold]
            if len(matching) != 1:
                raise ValueError("Frozen fold scope missing/duplicated")
            split = matching[0]
            source_attempt = run/original_state["jobs"][job_id]["attempt"]
            source_binding = read_json(source_attempt/("fold_"+str(fold))/"E1/binding.json")
            if file_sha(split_path) != source_binding["split_manifest_sha256"] or split != source_binding["split"]:
                raise ValueError("Validation perturbation split binding mismatch")
            split_scope_sources.append(dict(job=job_id, path=str(split_path), sha256=file_sha(split_path)))
            e0_best = None
            for variant in ("E0", "E1"):
                checkpoints = ("best", "initial", "last") if stage == "pilot" else ("best",)
                for ck in checkpoints:
                    checkpoint_count += 1
                    directory = job_dir/variant/ck
                    check = read_json(directory/"checks.json")
                    _validate_checks(check, ck)
                    prediction = read_json(directory/"predictions.json")
                    conditions = defaultdict(list)
                    for row in prediction:
                        conditions[row["condition"]].append(row)
                    wanted = {"N", "Z"} | {"R"+str(s) for s in REWIRING_SEEDS} if (
                        variant == "E1" and ck == "best") else {"N"}
                    if set(conditions) != wanted:
                        raise ValueError("Wrong prediction conditions: " + str(directory))
                    if {r["file"] for r in conditions["N"]} != set(split["val_files"]):
                        raise ValueError("Scored files differ from frozen validation partition")
                    if variant == "E0" and ck == "best":
                        e0_best = conditions["N"]
                    table = read_csv(directory/"sensitivity.csv")
                    table_conditions = {r["condition"]: r for r in table}
                    expected_table = wanted | ({"E1_N_vs_E0_N"} if variant == "E1" and ck == "best" else set())
                    if len(table_conditions) != len(table) or set(table_conditions) != expected_table:
                        raise ValueError("Wrong/double-counted sensitivity conditions")
                    tags = dict(cohort=cohort, task=task, fold=fold, variant=variant,
                                checkpoint=ck, score_role=SCORE_ROLE)
                    calculated_files = []
                    for condition, stored in table_conditions.items():
                        for tag, value in tags.items():
                            if _decode(stored.get(tag)) != value:
                                raise ValueError("Sensitivity binding differs: " + tag)
                        current = conditions["N"] if condition == "E1_N_vs_E0_N" else conditions[condition]
                        reference = e0_best if condition == "E1_N_vs_E0_N" else conditions["N"]
                        compared, by_file = independently_compare(current, reference, task)
                        assert_same_statistics(compared, stored)
                        reference_name = "E0_N" if condition == "E1_N_vs_E0_N" else variant+"_N"
                        if stored["reference"] != reference_name:
                            raise ValueError("Wrong intervention reference")
                        scored_rows.append(dict(tags, condition=condition,
                                                reference=reference_name, **compared))
                        calculated_files.extend(dict(tags, condition=condition, reference=reference_name, **r)
                                                for r in by_file)
                    exported_files = read_csv(directory/"file_changes.csv")
                    key = lambda r: (r["condition"], r["file"])
                    exported_map = {key(r): r for r in exported_files}
                    if len(exported_map) != len(exported_files) or set(exported_map) != {key(r) for r in calculated_files}:
                        raise ValueError("Per-file change population mismatch")
                    for row in calculated_files:
                        assert_same_statistics({k: row[k] for k in
                                                ("n", "flips", "corrected", "introduced", "probability_abs_mean")},
                                               exported_map[key(row)])
                    file_rows.extend(calculated_files)
                    message_paths = [directory/"message_norms.csv"]
                    if variant == "E1" and ck == "best":
                        message_paths.append(directory/"zero_message_norms.csv")
                    for path in message_paths:
                        rows = read_csv(path)
                        message_global.extend(weighted_norm_summary(rows))
                        csv_paths["message_norms.csv"].append(path)
                    for name in ("representation_changes.csv", "parameter_scales.csv"):
                        path = directory/name
                        if path.exists():
                            csv_paths[name].append(path)
                            if name == "parameter_scales.csv":
                                parameters.extend(read_csv(path))
                    audits = read_json(directory/"rewiring_audit.json")
                    if variant == "E1" and ck == "best":
                        if sorted(a["seed"] for a in audits) != REWIRING_SEEDS:
                            raise ValueError("Missing/duplicated rewiring seed")
                        for a in audits:
                            if (a["cohort"], a["task"], a["fold"]) != (cohort, task, fold):
                                raise ValueError("Rewiring task binding mismatch")
                            if a["labels_read"] is not False or a["graph_persisted"] is not False:
                                raise ValueError("Invalid rewiring policy")
                        for a in audits:
                            scoped = validation_rewiring_scope(a, split["val_files"], split["train_files"])
                            annotated = dict(a, validation_scope=scoped)
                            rewiring.append(annotated)
                            rewiring_validation_rows.append(dict(cohort=cohort, task=task, fold=fold,
                                seed=a["seed"], full_graph_ddg_edges=a["ddg_edges"],
                                full_graph_replaced_semantic_edges=a["replaced_semantic_edges"],
                                full_graph_semantic_perturbation_fraction=a["semantic_perturbation_fraction"],
                                **scoped))
                    elif audits:
                        raise ValueError("Unexpected pilot last/initial rewiring")
                    source_paths.extend(p for p in directory.iterdir() if p.is_file())
    counts = {(c, t): 5 if t == "contract" else 10 for c in
              ("reentrancy_author", "access_control_author") for t in ("contract", "node")}
    best = summarize_conditions(scored_rows, expected_counts=counts)
    # Paired E1 vs E0 is separate, never another N observation.
    comparisons = []
    groups = defaultdict(list)
    for row in scored_rows:
        if row["condition"] == "E1_N_vs_E0_N":
            groups[(row["cohort"], row["task"])].append(row)
    normal_e0 = {(r["cohort"], r["task"], r["fold"]): r for r in scored_rows
                 if r["variant"] == "E0" and r["checkpoint"] == "best"}
    for key, rows in sorted(groups.items()):
        comparisons.append(dict(cohort=key[0], task=key[1], folds=len(rows),
            metric_delta_E1_minus_E0_pp={m: mean_sd([r[m]-normal_e0[key+(r["fold"],)][m] for r in rows])
                                       for m in METRICS},
            prediction_flips=sum(r["prediction_flips"] for r in rows),
            corrected=sum(r["corrected"] for r in rows), introduced=sum(r["introduced"] for r in rows),
            probability_abs_mean_pooled=sum(r["probability_abs_mean"]*r["n"] for r in rows)/sum(r["n"] for r in rows)))
    parameter_summary = []
    grouped_parameters = defaultdict(list)
    for row in parameters:
        canonical = _decode(row["canonical"])
        relation_kind = "ddg" if canonical[1] == "DATA_DEF_USE" else "base"
        key = (row["cohort"], row["task"], row["variant"], row["checkpoint"],
               row["layer"], row["parameter"], relation_kind)
        grouped_parameters[key].append(row)
    for key, rows in sorted(grouped_parameters.items()):
        item = dict(zip(("cohort", "task", "variant", "checkpoint", "layer", "parameter", "relation_kind"), key))
        item.update(canonical_matrix_observations=len(rows),
                    scope="pilot only; equal canonical-matrix observations, not a pooled 4D bank std",
                    std_population_across_canonical=describe([float(r["std_population"]) for r in rows]),
                    frobenius_norm_across_canonical=describe([float(r["frobenius_norm"]) for r in rows]))
        for optional in ("source_to_matrix_std_ratio", "bank_to_matrix_std_ratio"):
            if optional in rows[0]:
                item[optional] = describe([float(r[optional]) for r in rows])
        parameter_summary.append(item)
    message_summary = []
    grouped_messages = defaultdict(list)
    for row in message_global:
        key = tuple(row[k] for k in ("cohort", "task", "variant", "checkpoint", "condition", "layer", "branch"))
        grouped_messages[key].append(row)
    for key, rows in sorted(grouped_messages.items()):
        item = dict(zip(("cohort", "task", "variant", "checkpoint", "condition", "layer", "branch"), key))
        valid = [r for r in rows if r["node_weighted_mean"] is not None]
        item.update(forwards=len(rows),
                    node_weighted_mean_across_forwards=mean_sd([r["node_weighted_mean"] for r in valid]),
                    zero_fraction_across_forwards=mean_sd([r["zero_fraction"] for r in valid]),
                    excluded_near_zero_denominator=sum(r["excluded_near_zero_denominator"] for r in rows),
                    population_count_per_forward=sorted(set(r["population_count"] for r in rows)),
                    quantile_note="Global median/p95 are not reconstructed; per-node-type quantiles stay in message_norms.csv.",
                    scope="all graph nodes, including train/validation; equal forward means after node weighting within each forward")
        message_summary.append(item)
    rewiring_summary = []
    grouped_rewiring = defaultdict(list)
    for a in rewiring:
        grouped_rewiring[(a["cohort"], a["task"], a["seed"])].append(a)
    for key, rows in sorted(grouped_rewiring.items()):
        rewiring_summary.append(dict(cohort=key[0], task=key[1], seed=key[2], folds=len(rows),
            semantic_perturbation_fraction=mean_sd([r["semantic_perturbation_fraction"] for r in rows]),
            replaced_semantic_edges=mean_sd([r["replaced_semantic_edges"] for r in rows]),
            ddg_edges=sorted(set(r["ddg_edges"] for r in rows)),
            unchanged_groups=mean_sd([r["unchanged_groups"] for r in rows]),
            validation_ddg_edges_total=sum(r["validation_scope"]["validation_ddg_edges"] for r in rows),
            validation_replaced_semantic_edges_total=sum(r["validation_scope"]["validation_replaced_semantic_edges"] for r in rows),
            validation_semantic_perturbation_fraction_equal_fold=mean_sd([
                r["validation_scope"]["validation_semantic_perturbation_fraction"] for r in rows]),
            validation_semantic_perturbation_fraction_pooled=(
                sum(r["validation_scope"]["validation_replaced_semantic_edges"] for r in rows) /
                sum(r["validation_scope"]["validation_ddg_edges"] for r in rows)
                if sum(r["validation_scope"]["validation_ddg_edges"] for r in rows) else 0.0),
            folds_without_validation_semantic_perturbation=sum(
                r["validation_scope"]["validation_replaced_semantic_edges"] == 0 for r in rows),
            validation_effective_file_appearances=sum(
                r["validation_scope"]["validation_files_with_semantic_perturbation"] for r in rows),
            interpretation="Same frozen task graph; whole-graph perturbation is not scored-file perturbation. Repeated folds are not independent rewiring samples."))
    summary_doc = dict(protocol=PROTOCOL, score_role=SCORE_ROLE,
        selected_pilot_output=pilot_output, selected_remaining_output=remaining_output,
        paired_best_folds=len(expected), pilot_paired_folds=len(pilot["jobs"]),
        checkpoint_evaluations=checkpoint_count, model_forward_performed=False,
        independent_prediction_recomputation="passed",
        main_best=best, E1_vs_E0= comparisons,
        pilot_only_initial=summarize_conditions(scored_rows, "initial"),
        pilot_only_last=summarize_conditions(scored_rows, "last"),
        parameter_summary=parameter_summary, message_summary=message_summary,
        rewiring_summary=rewiring_summary,
        interpretation_notes=[
            "Main metrics are equal-fold CV validation statistics, not independent test results.",
            "Only best is the main result; the seven predeclared pilot folds alone provide initial/last measurements.",
            "Z and R reuse E1 weights; they are fixed-checkpoint sensitivity tests, not retrained ablations.",
            "E1_N_vs_E0_N is a comparison, never counted as a second E1 N condition.",
            "Full-forward message norms include train and validation nodes; scored prediction metrics cover validation only.",
            "Messages are node-count-weighted across disjoint types; global medians/p95 are unavailable from scalar summaries.",
            "Three rewiring seeds remain separate; low/no semantic perturbation is not evidence of insensitivity."])
    if write:
        outputs = ["sensitivity.csv", "file_changes.csv", "message_norms.csv",
                   "representation_changes.csv", "parameter_scales.csv",
                   "message_global_by_fold.csv", "rewiring_validation.csv", "rewiring_audit.json",
                   "aggregate_summary.json", "aggregation_inputs.json"]
        if any((root/name).exists() for name in outputs):
            raise FileExistsError("An aggregate output exists; refusing to overwrite")
        write_csv(root/"sensitivity.csv", scored_rows)
        write_csv(root/"file_changes.csv", file_rows)
        write_csv(root/"message_global_by_fold.csv", message_global)
        write_csv(root/"rewiring_validation.csv", rewiring_validation_rows)
        for name in ("message_norms.csv", "representation_changes.csv", "parameter_scales.csv"):
            _merge_csv(csv_paths[name], root/name)
        write_json(root/"rewiring_audit.json", rewiring)
        write_json(root/"aggregate_summary.json", summary_doc)
        write_json(root/"aggregation_inputs.json", dict(
            score_role=SCORE_ROLE, independent_prediction_recomputation=True,
            source_files={str(p.relative_to(root)): file_sha(p) for p in sorted(set(source_paths))},
            validation_tolerance=NUMERIC_TOLERANCE,
            frozen_split_scope_sources=split_scope_sources,
            module_source_sha256=file_sha(Path(__file__))))
    return summary_doc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--run", type=Path, default=RUN)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--pilot-output", default="pilot")
    parser.add_argument("--remaining-output", default="remaining")
    args = parser.parse_args()
    result = aggregate(args.root, args.run, write=not args.validate_only,
                       pilot_output=args.pilot_output, remaining_output=args.remaining_output)
    print(json.dumps({k: result[k] for k in ("paired_best_folds", "pilot_paired_folds",
                                            "checkpoint_evaluations",
                                            "independent_prediction_recomputation")}, indent=2))


if __name__ == "__main__":
    main()
