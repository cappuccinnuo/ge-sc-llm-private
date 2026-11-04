"""Read-only, receipt-verified formal CV reporting. No models, training or GPU imports."""
import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

NAME = "paper_kfold"
VERSION = "ddg-paper-kfold-v1"
ROLE = "cv_validation"
METRICS = ("buggy_f1", "macro_f1", "precision", "recall")
TASKS = (("reentrancy_author", "contract", 5),
         ("access_control_author", "contract", 5),
         ("reentrancy_author", "node", 10),
         ("access_control_author", "node", 10))
TIE_TOLERANCE_PP = 1e-10


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                    allow_nan=False) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def within(root, name):
    root, path = Path(root).resolve(), (Path(root) / name).resolve()
    require(path != root and root in path.parents, "Artifact path escapes its run")
    return path


def current_code_hashes(repo):
    repo = Path(repo)
    root = repo / "scripts/DFG/experiments"
    paths = list(root.glob("*.py")) + list(root.parent.glob("*.py"))
    paths += [repo / p for p in ("sco_models/model_hgt.py", "sco_models/graph_utils.py",
                                 "scripts/encode_tokenizer_features.py")]
    return {str(p.relative_to(repo)): sha256(p) for p in sorted(paths)}


def tree_hashes(folder):
    return {str(p.relative_to(folder)): sha256(p)
            for p in sorted(Path(folder).rglob("*")) if p.is_file()}


def verified_receipt(root, entry):
    require(entry["status"] == "passed", "Only accepted attempts can be scored")
    path = within(root, entry["receipt"])
    require(sha256(path) == entry["receipt_sha256"], "Receipt digest mismatch")
    receipt = read_json(path)
    require(receipt["acceptance"]["status"] == "passed", "Receipt is not accepted")
    require(receipt["acceptance"]["score_role"] == ROLE, "Wrong receipt score role")
    attempt = within(root, entry["attempt"])
    require(attempt.is_dir(), "Accepted attempt is missing")
    require(tree_hashes(attempt) == receipt["artifacts"], "Accepted artifact digest mismatch")
    return receipt, attempt


def metrics_from_predictions(rows, checkpoint):
    require(bool(rows), "No scored samples")
    counts = [0, 0, 0, 0]  # TN, FP, FN, TP
    for row in rows:
        target, prediction = row["target"], row[checkpoint]
        require(target in (0, 1) and prediction in (0, 1), "Nonbinary prediction")
        counts[target * 2 + prediction] += 1
    tn, fp, fn, tp = counts
    def ratio(numerator, denominator):
        return numerator / denominator if denominator else 0.0
    pos = ratio(2 * tp, 2 * tp + fp + fn)
    neg = ratio(2 * tn, 2 * tn + fp + fn)
    return {"n": len(rows), "positive": tp + fn,
            "buggy_f1": 100 * pos, "macro_f1": 50 * (pos + neg),
            "precision": 100 * ratio(tp, tp + fp),
            "recall": 100 * ratio(tp, tp + fn), "tn_fp_fn_tp": counts}


def close(left, right):
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-10)


def sample_key(row, task):
    return (row["file"], json.dumps(row.get("original_graph_node_id"),
                                    ensure_ascii=True, sort_keys=True) if task == "node" else None)


def paired_errors(left, right, checkpoint, task):
    require(all(row.get("score_role") == ROLE for row in left + right), "Wrong prediction score role")
    a = {sample_key(row, task): row for row in left}
    b = {sample_key(row, task): row for row in right}
    require(len(a) == len(left) and len(b) == len(right), "Duplicate scored identity")
    require(set(a) == set(b), "E0/E1 sample identities differ")
    counts = dict(both_correct=0, e0_wrong_e1_correct=0,
                  e0_correct_e1_wrong=0, both_wrong=0)
    error_types = dict(corrected_fp=0, corrected_fn=0, introduced_fp=0, introduced_fn=0)
    changed = []
    for key in a:
        x, y = a[key], b[key]
        require(x["target"] == y["target"], "E0/E1 ground truths differ")
        c0, c1 = x[checkpoint] == x["target"], y[checkpoint] == y["target"]
        category = ("both_correct" if c0 and c1 else "e0_wrong_e1_correct" if c1
                    else "e0_correct_e1_wrong" if c0 else "both_wrong")
        counts[category] += 1
        if x[checkpoint] != y[checkpoint]:
            kind = (("corrected_" if c1 else "introduced_") + ("fn" if x["target"] else "fp"))
            error_types[kind] += 1
            changed.append({"file": x["file"], "original_graph_node_id": x.get("original_graph_node_id"),
                            "node_type": x.get("node_type"), "target": x["target"],
                            "E0": x[checkpoint], "E1": y[checkpoint],
                            "transition": category, "error_change": kind})
    return {"counts": counts, "error_types": error_types, "changed": changed}


def distribution(values):
    require(len(values) >= 2, "Sample standard deviation needs at least two complete folds")
    require(all(math.isfinite(v) for v in values), "Nonfinite metric")
    return {"mean": statistics.mean(values), "sample_std": statistics.stdev(values),
            "fold_values": values}


def metric_summary(rows, expected_folds):
    require(len(rows) == expected_folds * 4, "Incomplete task; partial-fold means are forbidden")
    by = {(r["fold"], r["variant"], r["checkpoint"]): r for r in rows}
    expected = {(f, v, ck) for f in range(expected_folds) for v in ("E0", "E1")
                for ck in ("best", "last")}
    require(set(by) == expected and len(by) == len(rows), "Missing or duplicate fold/variant/checkpoint")
    output = {}
    for checkpoint in ("best", "last"):
        output[checkpoint] = {}
        for variant in ("E0", "E1", "E1-E0"):
            output[checkpoint][variant] = {}
            for metric in METRICS:
                values = [(by[f, "E1", checkpoint][metric] - by[f, "E0", checkpoint][metric])
                          if variant == "E1-E0" else by[f, variant, checkpoint][metric]
                          for f in range(expected_folds)]
                item = distribution(values)
                if variant == "E1-E0":
                    item["fold_direction_counts"] = {
                        "improved": sum(v > TIE_TOLERANCE_PP for v in values),
                        "tied": sum(abs(v) <= TIE_TOLERANCE_PP for v in values),
                        "declined": sum(v < -TIE_TOLERANCE_PP for v in values)}
                output[checkpoint][variant][metric] = item
    return output


def attempt_inventory(root, plan, state):
    """Never infer a historical failure merely from an incomplete/missing result."""
    records = []
    for job in plan["jobs"]:
        current = state["jobs"].get(job["id"], {})
        job_root = Path(root) / "jobs" / job["id"]
        names = set()
        for path in job_root.glob("attempt_*"):
            found = re.match(r"^(attempt_[0-9]+)(?:\..*)?$", path.name)
            if found:
                names.add(found.group(1))
        current_attempt = current.get("attempt")
        if current_attempt:
            names.add(Path(current_attempt).name)
        for ordinal, name in enumerate(sorted(names), 1):
            relative = str((job_root / name).relative_to(root))
            is_current = current_attempt == relative
            entry = current if is_current else {}
            log = job_root / (name + ".log")
            receipt = job_root / (name + ".receipt.json")
            status = entry.get("status", "historical_accepted" if receipt.is_file() else "unaccepted_history_unknown")
            # Reading a bounded text log does not read unfinished JSON as truth.
            error_excerpt = None
            if log.is_file():
                with log.open("rb") as stream:
                    stream.seek(max(0, log.stat().st_size - 16384))
                    tail = stream.read().decode("utf-8", errors="replace").splitlines()
                lines = [line for line in tail if ("Error:" in line or "Exception:" in line or
                                                   "out of memory" in line.lower())]
                if lines:
                    error_excerpt = "\n".join(lines[-5:])
            records.append({"job": job["id"], "cohort": job["cohort"], "task": job["task"],
                "fold": job["fold"], "attempt": relative, "ordinal": ordinal, "retry": ordinal > 1,
                "status": status, "is_current_state_entry": is_current,
                "exit_code": entry.get("exit_code"), "error": entry.get("error"),
                "error_log_excerpt": error_excerpt,
                "started_utc": entry.get("started_utc"), "finished_utc": entry.get("finished_utc"),
                "log": str(log.relative_to(root)) if log.is_file() else None,
                "receipt": str(receipt.relative_to(root)) if receipt.is_file() else None,
                "history_note": ("Current state evidence" if is_current else
                    "Historical receipt exists; this row alone is not a new artifact acceptance"
                    if receipt.is_file() else
                    "Prior state may have been overwritten; no fabricated exit code or failure reason")})
    return records


def read_complete_task(root, plan, state, cohort, task, folds):
    jobs = sorted([j for j in plan["jobs"] if (j["cohort"], j["task"]) == (cohort, task)],
                  key=lambda j: j["fold"])
    require([j["fold"] for j in jobs] == list(range(folds)), "Unexpected task fold plan")
    pending = [j["id"] for j in jobs if state["jobs"].get(j["id"], {}).get("status") != "passed"]
    if pending:
        return {"cohort": cohort, "task": task, "status": "pending", "expected_folds": folds,
                "pending_jobs": pending, "accepted_entries_in_snapshot": folds - len(pending),
                "reason": "No task performance mean computed until every planned paired fold is accepted"}
    rows, telemetry_rows, error_rows, changed_rows = [], [], [], []
    seen_validation_files = set()
    for job in jobs:
        entry = state["jobs"][job["id"]]
        receipt, attempt = verified_receipt(root, entry)
        accepted = receipt["acceptance"]
        require(accepted["job"] == job["id"], "Receipt belongs to another job")
        result = read_json(attempt / "result.json")
        require((result.get("protocol"), result.get("protocol_version"), result.get("score_role"),
                 result.get("mode")) == (NAME, VERSION, ROLE, "full"), "Mixed protocol or smoke result")
        require(result["cohort"] == cohort and result["task"] == task and
                result["completed_folds"] == result["requested_folds"] == 1, "Wrong task result")
        require(len(result["folds"]) == 1, "Multiple fold records inside one paired job")
        fold = result["folds"][0]
        require(fold["fold"] == job["fold"] and fold["status"] == "complete", "Incomplete or wrong fold")
        require(set(fold["variants"]) == {"E0", "E1"}, "Missing paired variant")
        fold_dir = attempt / ("fold_" + str(job["fold"]))
        require(read_json(fold_dir / "result.json") == fold, "Nested fold result mismatch")
        splitdoc = read_json(job["splits"])
        require(read_json(attempt / "splits.json") == splitdoc, "Run split differs from frozen split")
        split = next(f for f in splitdoc["folds"] if f["fold"] == job["fold"])
        expected_files = set(split["val_files"])
        require(not seen_validation_files.intersection(expected_files), "Files repeat across validation folds")
        seen_validation_files.update(expected_files)
        predictions = {}
        for variant in ("E0", "E1"):
            dest = fold_dir / variant
            r = fold["variants"][variant]
            require(r["status"] == "complete" and r["score_role"] == ROLE, "Wrong variant scoring status")
            require(read_json(dest / "result.json") == r, "Variant result mismatch")
            require(r["checkpoint_roundtrip_exact"] == {"best": True, "last": True},
                    "Checkpoint roundtrip was not accepted")
            predictions[variant] = read_json(dest / "cv_validation_predictions.json")
            require({p["file"] for p in predictions[variant]} == expected_files, "Validation file coverage mismatch")
            a = accepted["variants"][variant]
            telemetry = read_json(dest / "telemetry.json")
            require(telemetry["parameters"]["total"] == a["parameter_count"], "Parameter count mismatch")
            require(telemetry["fit_eval_checkpoint_wall_seconds"] == a["fit_eval_checkpoint_wall_seconds"],
                    "Timing telemetry mismatch")
            require(telemetry["simultaneously_loaded_model_count"] == 2, "Missing simultaneous pair telemetry")
            memory = telemetry["memory_after"]
            require(memory.get("cuda") and str(memory["device"]).startswith("cuda"), "Non-CUDA formal telemetry")
            telemetry_row = dict(cohort=cohort, task=task, fold=job["fold"], variant=variant)
            telemetry_row.update({k: a[k] for k in (
                "best_epoch", "last_epoch", "epochs", "stop_reason", "parameter_count",
                "fit_eval_checkpoint_wall_seconds", "ddg_train_edges", "ddg_gradient_l1_sum",
                "ddg_message_update_l1", "validation_only_relations")})
            telemetry_row.update(best_epoch_human=a["best_epoch"] + 1, last_epoch_human=a["last_epoch"] + 1,
                peak_allocated_mib=memory["peak_allocated_bytes"] / (2 ** 20),
                peak_reserved_mib=memory["peak_reserved_bytes"] / (2 ** 20))
            telemetry_rows.append(telemetry_row)
            for ck in ("best", "last"):
                calculated = metrics_from_predictions(predictions[variant], ck)
                scores = r["cv_validation"][ck]
                require(all(close(calculated[m], scores[m]) for m in METRICS) and
                        all(calculated[m] == scores[m] for m in ("n", "positive", "tn_fp_fn_tp")),
                        "Prediction metrics differ from accepted score")
                row = dict(cohort=cohort, task=task, fold=job["fold"], variant=variant,
                           checkpoint=ck, score_role=ROLE, **scores)
                row.update({m + "_E1_minus_E0": fold["paired_cv_validation_delta"][ck][m] for m in METRICS})
                rows.append(row)
        for ck in ("best", "last"):
            error = paired_errors(predictions["E0"], predictions["E1"], ck, task)
            accepted_error = accepted["paired_errors"][ck]
            require(error["counts"] == accepted_error["counts"], "Error transitions differ from receipt")
            def plain_changes(items):
                return sorted([{k: v for k, v in x.items() if k != "error_change"} for x in items],
                              key=lambda x: json.dumps(x, sort_keys=True))
            require(plain_changes(error["changed"]) == plain_changes(accepted_error["changed"]),
                    "Changed predictions differ from receipt")
            erow = dict(cohort=cohort, task=task, fold=job["fold"], checkpoint=ck)
            erow.update(error["counts"])
            erow.update(error["error_types"])
            error_rows.append(erow)
            changed_rows += [dict(cohort=cohort, task=task, fold=job["fold"], checkpoint=ck, **r)
                             for r in error["changed"]]
            for m in METRICS:
                actual = fold["variants"]["E1"]["cv_validation"][ck][m] - fold["variants"]["E0"]["cv_validation"][ck][m]
                require(close(actual, fold["paired_cv_validation_delta"][ck][m]), "Paired metric delta mismatch")
    aggregate = {}
    for variant in ("E0", "E1"):
        selected = [r for r in telemetry_rows if r["variant"] == variant]
        aggregate[variant] = {
            "fits": len(selected),
            "fit_eval_checkpoint_wall_seconds_total": sum(r["fit_eval_checkpoint_wall_seconds"] for r in selected),
            "fit_eval_checkpoint_wall_seconds_mean": statistics.mean(r["fit_eval_checkpoint_wall_seconds"] for r in selected),
            "peak_allocated_mib_max": max(r["peak_allocated_mib"] for r in selected),
            "peak_reserved_mib_max": max(r["peak_reserved_mib"] for r in selected),
            "parameter_counts": sorted({r["parameter_count"] for r in selected}),
            "ddg_train_edges_min": min(r["ddg_train_edges"] for r in selected),
            "ddg_train_edges_max": max(r["ddg_train_edges"] for r in selected),
            "ddg_gradient_l1_sum_across_fits": sum(r["ddg_gradient_l1_sum"] for r in selected),
            "folds_with_registered_relations_absent_from_train": sum(bool(r["validation_only_relations"]) for r in selected)}
    error_totals = {}
    for ck in ("best", "last"):
        selected = [r for r in error_rows if r["checkpoint"] == ck]
        names = ("both_correct", "e0_wrong_e1_correct", "e0_correct_e1_wrong", "both_wrong",
                 "corrected_fp", "corrected_fn", "introduced_fp", "introduced_fn")
        error_totals[ck] = {k: sum(r[k] for r in selected) for k in names}
    return {"cohort": cohort, "task": task, "status": "complete", "expected_folds": folds,
            "receipt_verified_folds": folds, "score_role": ROLE,
            "validation_file_count": len(seen_validation_files), "metrics": metric_summary(rows, folds),
            "fold_metrics": rows, "fit_telemetry": telemetry_rows, "telemetry_summary": aggregate,
            "error_transitions_by_fold": error_rows, "error_transition_totals": error_totals,
            "changed_predictions": changed_rows}


def verify_plan(root):
    root = Path(root)
    path = root / "plan.json"
    require(sha256(path) == read_json(root / "plan.seal.json")["sha256"], "Plan seal mismatch")
    plan = read_json(path)
    require((plan.get("protocol"), plan.get("protocol_version"), plan.get("score_role")) ==
            (NAME, VERSION, ROLE), "Only paper_kfold CV validation may enter this report")
    require(plan.get("format") == "ddg-formal-gated-v1" and plan.get("mode") == "full"
            and plan.get("seed") == 1 and plan.get("epochs") == 50, "Wrong formal plan")
    require([(t["cohort"], t["task"], t["folds"]) for t in plan["task_order"]] == list(TASKS),
            "Unexpected formal task order")
    require(len(plan["jobs"]) == 30 and len({j["id"] for j in plan["jobs"]}) == 30,
            "Unexpected number of formal paired jobs")
    for path, expected in plan["frozen_files"].items():
        require(sha256(path) == expected, "Frozen file mismatch: " + path)
    return plan


def build_report(root):
    root = Path(root).resolve()
    plan = verify_plan(root)
    state_path = root / "state.json"
    state_bytes = state_path.read_bytes()
    state_sha = hashlib.sha256(state_bytes).hexdigest()
    state = json.loads(state_bytes.decode("utf-8"))
    tasks = [read_complete_task(root, plan, state, *spec) for spec in TASKS]
    attempts = attempt_inventory(root, plan, state)
    return {"format": "ddg-stage-c-derived-report-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "run": str(root), "protocol": NAME, "protocol_version": VERSION, "score_role": ROLE,
        "base_git_head": plan.get("base_git_head"),
        "initialization_version": plan.get("initialization_version"),
        "import_provenance": state.get("import_provenance"),
        "plan_sha256": sha256(root / "plan.json"), "state_snapshot_sha256": state_sha,
        "state_changed_during_report": sha256(state_path) != state_sha,
        "stage_b": state["stage_b"], "stage_c": state["stage_c"],
        "scoring_notes": [
            "All main results are CV validation: the same fold validation set selects best and is scored.",
            "Best uses the lowest validation loss, not the highest F1; last is a separate auxiliary result.",
            "Metrics are percentages; E1 minus E0 is in percentage points.",
            "Unweighted fold mean and sample standard deviation (ddof=1); not a confidence interval.",
            "Node scores use HCG node identities (file + original node id), not deduplicated source-line F1.",
            "Fit time includes fitting, validation, checkpoint IO and reload scoring; count each fit once.",
            "GPU peaks are PyTorch process peaks with both models resident, not standalone model or whole-card memory.",
            "Cumulative DDG gradient depends on epoch count; parameter changes may include weight decay.",
            "No partial-fold task mean; no nested/narrow/multi-seed mixing; no graph, label or model changes.",
            "Historical unaccepted attempts without state evidence have unknown status, not invented failure reasons."],
        "tie_tolerance_percentage_points": TIE_TOLERANCE_PP,
        "tasks": tasks, "attempts": attempts,
        "attempt_summary": {
            "attempts_discovered": len(attempts),
            "current_state_failed": sum(a["is_current_state_entry"] and a["status"] == "failed" for a in attempts),
            "retry_attempts": sum(a["retry"] for a in attempts),
            "historical_unaccepted_unknown": sum(a["status"] == "unaccepted_history_unknown" for a in attempts)},
        "complete_tasks": sum(t["status"] == "complete" for t in tasks)}


def csv_write(path, rows):
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                             for k, v in row.items()})


def markdown(report):
    lines = ["# Dataset A formal CV validation report", "",
             "- Protocol: paper_kfold / ddg-paper-kfold-v1.",
             "- Best: minimum validation loss. Last: auxiliary, reported separately.",
             "- Node metrics count HCG nodes; they are not deduplicated source-line metrics.",
             "- Metrics: percent. Delta: E1-E0 percentage points. Std: sample, ddof=1.", ""]
    for task in report["tasks"]:
        lines += ["## " + task["cohort"] + " / " + task["task"], ""]
        if task["status"] != "complete":
            lines += ["PENDING: no task mean; accepted entries in snapshot = "
                      + str(task["accepted_entries_in_snapshot"]) + "/" + str(task["expected_folds"]), ""]
            continue
        for ck in ("best", "last"):
            lines += ["### " + ck, "",
                      "| Fold | Model | Buggy-F1 | Macro-F1 | Precision | Recall |",
                      "|---:|---|---:|---:|---:|---:|"]
            for fold in range(task["expected_folds"]):
                selected = [r for r in task["fold_metrics"] if r["fold"] == fold and r["checkpoint"] == ck]
                for row in selected:
                    lines.append("| {} | {} | {} |".format(fold, row["variant"],
                                 " | ".join("{:.4f}".format(row[m]) for m in METRICS)))
                delta = {m: selected[0][m + "_E1_minus_E0"] for m in METRICS}
                lines.append("| {} | E1-E0 pp | {} |".format(fold,
                             " | ".join("{:+.4f}".format(delta[m]) for m in METRICS)))
            lines += ["", "| Model | Buggy-F1 mean +/- std | Macro-F1 mean +/- std | Precision mean +/- std | Recall mean +/- std |",
                      "|---|---:|---:|---:|---:|"]
            for variant in ("E0", "E1", "E1-E0"):
                stats = task["metrics"][ck][variant]
                lines.append("| {} | {} |".format(variant, " | ".join(
                    "{:.4f} +/- {:.4f}".format(stats[m]["mean"], stats[m]["sample_std"]) for m in METRICS)))
            lines += ["", "| Metric | Improved | Tied | Declined |", "|---|---:|---:|---:|"]
            for m in METRICS:
                c = task["metrics"][ck]["E1-E0"][m]["fold_direction_counts"]
                lines.append("| {} | {} | {} | {} |".format(m, c["improved"], c["tied"], c["declined"]))
            e = task["error_transition_totals"][ck]
            lines += ["", "Error changes: " + ", ".join(k + "=" + str(v) for k, v in e.items()) + ".", ""]
        lines += ["### Fit telemetry (not counted twice for best/last)", "",
                  "| Model | Fits | Seconds total | Peak allocated MiB | Peak reserved MiB | Parameters | DDG train edges min-max | DDG gradient sum | Train-unseen relation folds |",
                  "|---|---:|---:|---:|---:|---|---|---:|---:|"]
        for v in ("E0", "E1"):
            a = task["telemetry_summary"][v]
            lines.append("| {} | {} | {:.3f} | {:.2f} | {:.2f} | {} | {}-{} | {:.6f} | {} |".format(
                v, a["fits"], a["fit_eval_checkpoint_wall_seconds_total"], a["peak_allocated_mib_max"],
                a["peak_reserved_mib_max"], a["parameter_counts"], a["ddg_train_edges_min"],
                a["ddg_train_edges_max"], a["ddg_gradient_l1_sum_across_fits"],
                a["folds_with_registered_relations_absent_from_train"]))
        lines += ["", "All {} paired receipts and their artifact fingerprints verified.".format(task["receipt_verified_folds"]), "",
                  "Per-fold epochs, telemetry and error identities are in CSV/JSON.", ""]
    lines += ["## Attempts and scope", "", json.dumps(report["attempt_summary"], ensure_ascii=False), "",
              "All discovered attempts and available error evidence are listed in attempts.csv/report.json.",
              "Pending/unknown historical attempts are not reported as successful or fabricated failures.", ""]
    lines += ["- " + note for note in report["scoring_notes"]]
    return "\n".join(lines) + "\n"


def emit_report(report, output, run):
    output, run = Path(output).resolve(), Path(run).resolve()
    require(output != run and run not in output.parents, "Derived outputs must be outside the frozen run")
    require(not output.exists(), "Output directory exists; refusing overwrite")
    output.mkdir(parents=True)
    write_json(output / "report.json", report)
    complete = [t for t in report["tasks"] if t["status"] == "complete"]
    for name, field in (("fold_metrics.csv", "fold_metrics"), ("fit_telemetry.csv", "fit_telemetry"),
                        ("error_transitions.csv", "error_transitions_by_fold"),
                        ("changed_predictions.csv", "changed_predictions")):
        csv_write(output / name, [row for t in complete for row in t[field]])
    csv_write(output / "attempts.csv", report["attempts"])
    summaries = []
    for task in complete:
        for ck in ("best", "last"):
            for v in ("E0", "E1", "E1-E0"):
                for m in METRICS:
                    stat = task["metrics"][ck][v][m]
                    row = dict(cohort=task["cohort"], task=task["task"], checkpoint=ck,
                               variant=v, metric=m, mean=stat["mean"], sample_std=stat["sample_std"])
                    row.update(stat.get("fold_direction_counts", {}))
                    summaries.append(row)
    csv_write(output / "metric_summary.csv", summaries)
    (output / "REPORT.md").write_text(markdown(report), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[6]
    before = current_code_hashes(repo)
    report = build_report(args.run)
    require(before == read_json(Path(args.run) / "plan.json")["runner_code_sha256"],
            "Current runner code differs from the sealed plan")
    after = current_code_hashes(repo)
    require(before == after, "Runner code changed during read-only reporting")
    report["read_only_code_hash_check"] = {"before_equals_after": True, "files": len(before)}
    emit_report(report, args.output, args.run)
    require(before == current_code_hashes(repo), "Runner code changed while writing derived outputs")
    print(json.dumps({"output": str(Path(args.output).resolve()), "complete_tasks": report["complete_tasks"],
                      "pending_tasks": 4 - report["complete_tasks"], "score_role": ROLE}))


if __name__ == "__main__":
    main()
