"""Read-only N-C2 final reporting; no training, feature extraction or selection.
Reuse frozen N-C1 alignment, metric and resource reporting helpers.
"""
import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.dfg_v2.benchmark_v2.reporting import scored, csv_write
from scripts.DFG.dfg_v2.experiment.stats import (
    aggregate_metrics, validate_records, paired_comparison, holm_adjust, METRICS)
from . import batch_nc2 as batch, batch_nc2_worker as worker
from . import batch_nc1, nc1_reporting
from .nc1_history import verify_index
from .nc2_gate import verify as verify_gate
from .reporting import aligned_rows, read_artifact, identity
from .nb_reporting import paired_descriptive, score_or_empty
from .nc1_reporting import check_scores, oof, change_summary


def receipt_matrix(jobs, receipts):
    expected = {worker.job_id(j): j for j in jobs}
    if len(expected) != len(jobs):
        raise ValueError("Duplicate planned identity")
    found = {}
    for r in receipts:
        key = worker.job_id(r["job"])
        if key in found or r["job"] != expected.get(key):
            raise ValueError("Duplicate or unexpected receipt identity")
        found[key] = r
    if set(found) != set(expected):
        raise ValueError("Incomplete accepted receipt matrix")
    return found


def complete_entries(root, plan):
    included = verify_gate(root, plan)
    jobs = plan["jobs"] if included else [j for j in plan["jobs"] if j["name"] == "S5"]
    done = read(root / "complete.json")
    if (done.get("passed") is not True or done.get("formal_fits") != len(jobs)
            or done.get("S8_executed") is not included
            or done["plan"] != ref(root / "plan.json")
            or done["execution_revision"] != ref(root / "execution_revision.json")):
        raise ValueError("N-C2 completion binding differs")
    receipts = [read(checked(r)) for r in done["receipts"]]
    receipt_matrix(jobs, receipts)
    entries = {}
    for r, reference in zip(receipts, done["receipts"]):
        directory = Path(reference["path"]).parent
        worker.verify_attempt(root, plan, r["job"], directory, deep=True)
        entries[worker.job_id(r["job"])] = (directory, r)
    batch.validate_device_comparisons(jobs, [
        dict(r["job"], actual_device=r["actual_device"]) for r in receipts])
    return jobs, entries, included


def result_matrix(records, base_jobs, names):
    expected = [(j["task_id"], "G3R/" + n, j["fold"], j["seed"], ck)
                for j in base_jobs for n in names for ck in ("best", "last")]
    return validate_records(records, expected_keys=expected)


def changes(left, right, kind, ck):
    # Reuse the existing strict pairing and probability checks, rename its
    # historical S6/S4 output fields without changing the comparison algorithm.
    out = nc1_reporting.changes(left, right, kind, ck)
    for r in out:
        for old, new in (("S6_prediction", "prediction"),
                         ("S4_prediction", "baseline_prediction"),
                         ("S6_probability", "probability"),
                         ("S4_probability", "baseline_probability")):
            r[new] = r.pop(old)
    return out


def inference(records, included_s8):
    family = ["S4", "S8"] if included_s8 else ["S4"]
    comparisons = [dict(name="S5-" + b, **paired_comparison(
        records, "reentrancy_node", "G3R/S5", "G3R/" + b, "best", "buggy_f1"))
        for b in family]
    adjusted = holm_adjust({c["name"]: c["p_raw"] for c in comparisons},
                           expected_profiles=["S5-" + b for b in family])
    return comparisons, adjusted


def retention(student_delta, teacher_delta):
    return dict(S5_minus_S4_pp=student_delta, S6_minus_S4_pp=teacher_delta,
                ratio=student_delta / teacher_delta if teacher_delta > 0 else None,
                status="descriptive_only_coverage_and_optimization_differ" if teacher_delta > 0
                else "undefined_nonpositive_teacher_increment")


def build(root=batch.DEFAULT):
    root = Path(root)
    plan = batch.load(root / "plan.json", deep=False)
    worker.validate_execution(root, plan)
    checks = read(root / "report_checks.json")
    if checks.get("passed") is not True:
        raise ValueError("Reporting regression gate absent")
    out = root / "reports"
    if out.exists():
        raise FileExistsError("Preserve previous report attempt")
    sources = [ref(Path(__file__)), ref(batch.ROOT / "scripts/node_sem/tests/test_nc2_reporting.py")]
    sources += [ref(batch.ROOT / p) for p in (
        "scripts/node_sem/nc1_reporting.py", "scripts/node_sem/reporting.py",
        "scripts/node_sem/nb_reporting.py", "scripts/DFG/dfg_v2/benchmark_v2/reporting.py",
        "scripts/DFG/dfg_v2/experiment/stats.py")]
    write(root / "reporting_revision.json", dict(
        plan=ref(root / "plan.json"), execution_revision=ref(root / "execution_revision.json"),
        complete=ref(root / "complete.json"), sources=sources,
        tests=ref(root / "report_checks.json"), statistics=plan["statistics"],
        formal_fits_added=0, model_evals_added=0, no_new_selection=True, created_unix=time.time()))
    out.mkdir()
    try:
        jobs, entries, included = complete_entries(root, plan)
        parents = verify_index(plan["na_result_index"])
        n1root = Path(checked(plan["nc1_plan"])).parent
        n1plan = batch_nc1.load(n1root / "plan.json", deep=False)
        checked(plan["nc1_report"])
        n1entries = nc1_reporting.complete_entries(n1root, n1plan)
        n1jobs = {(j["task_id"], j["fold"]): j for j in n1plan["jobs"]}
        base_jobs = [j for j in jobs if j["name"] == "S5"]
        names = ["S4", "S5", "S6"] + (["S8"] if included else [])
        by_id = {worker.job_id(j): j for j in jobs}
        labels = read(checked(jobs[0]["label_view"]))
        records, orig_records, counts, resources, support, tables = [], [], [], [], [], {}
        source_receipts = []
        for job in base_jobs:
            old = parents[job["baseline_job_id"]]
            n1 = n1jobs[(job["task_id"], job["fold"])]
            candidates = [
                (old["job"], (Path(old["receipt"]["path"]).parent, read(checked(old["receipt"])))),
                (job, entries[worker.job_id(job)]),
                (n1, n1entries[worker.job_id(n1)])]
            if included:
                key = worker.job_id(dict(job, name="S8"))
                candidates.append((by_id[key], entries[key]))
            for j, entry in candidates:
                source_receipts.append(ref(entry[0] / "receipt.json"))
                if entry[1]["actual_device"] != job["device_policy"]:
                    raise ValueError("Historical/new device or TF32 differs")
                if j["split"] != job["split"] or j["label_view"] != job["label_view"]:
                    raise ValueError("Historical/new fold or label view differs")
                main = [dict(r, fold=j["fold"]) for r in aligned_rows(
                    read_artifact(entry, "outer_test_predictions.json"), j, labels)]
                original = aligned_rows(read_artifact(entry, "outer_test_orig_all_predictions.json"),
                                        j, labels, original=True)
                result = read_artifact(entry, "result.json")
                check_scores(main, result)
                tables[(j["task_id"], j["name"], j["fold"])] = main
                for ck in ("best", "last"):
                    ident = dict(task_id=j["task_id"], task_kind=j["granularity"],
                                 profile="G3R/" + j["name"], fold=j["fold"], seed=j["seed"], checkpoint=ck)
                    m = scored(main, ck)
                    records.append(dict(ident, metrics={k: m[k] for k in METRICS}))
                    counts.append(dict(ident, **m))
                    orig_records.append(dict(ident, metrics={k: scored(original, ck)[k] for k in METRICS}))
                rc = entry[1]
                resources.append(dict(
                    task_id=j["task_id"], name=j["name"], fold=j["fold"],
                    best_epoch=result["best_epoch"], last_epoch=result["last_epoch"],
                    epochs=result["history_rows"], parameters=result["parameter_count"],
                    fit_seconds=result["seconds"], total_seconds=rc["total_seconds"],
                    peak_allocated_mib=rc["resources"]["peak_allocated_mib"],
                    peak_reserved_mib=rc["resources"]["peak_reserved_mib"],
                    minimum_free_mib=rc["resources"]["minimum_free_mib"],
                    actual_device=rc["actual_device"],
                    checkpoint_roundtrip_exact=result["checkpoint_roundtrip_exact"]))
                gradient = read_artifact(entry, "gradient_audit.json")
                relations = {}
                for epoch in gradient["epochs"]:
                    for g in epoch["v2_relations"]:
                        v = relations.setdefault(tuple(g["canonical"]), dict(
                            canonical=g["canonical"], inner_train_edges=g["inner_train_edges"],
                            inner_val_edges=g["inner_val_edges"], outer_test_edges=g["outer_test_edges"],
                            max_message_gradient_l1=0., max_attention_gradient_l1=0.,
                            nonzero_message_epochs=0))
                        v["max_message_gradient_l1"] = max(v["max_message_gradient_l1"], g["message_gradient_l1"])
                        v["max_attention_gradient_l1"] = max(v["max_attention_gradient_l1"], g["attention_gradient_l1"])
                        v["nonzero_message_epochs"] += g["message_gradient_l1"] > 0
                support.append(dict(task_id=j["task_id"], name=j["name"], fold=j["fold"],
                    support=j["support"], relations=list(relations.values()),
                    message_update_l1=gradient["v2_message_update_l1"],
                    original_gradient_ref=ref(entry[0] / "fit/gradient_audit.json")))
            print("scored " + worker.job_id(job), flush=True)
        records = result_matrix(records, base_jobs, names)
        orig_records = result_matrix(orig_records, base_jobs, names)
        aggregates = aggregate_metrics(records)
        paired, pooled, positives, summaries, files, count_audit, teacher_gap = [], [], [], [], [], {}, []
        bases = ["S4", "S6"] + (["S8"] if included else [])
        with (out / "prediction_changes.jsonl").open("x", encoding="utf8") as stream:
            for task, folds in batch.TASK_FOLDS:
                kind = task.rsplit("_", 1)[-1]
                groups = {n: oof([r for f in range(folds) for r in tables[(task, n, f)]], kind) for n in names}
                for ck in ("best", "last"):
                    for name, rows in groups.items():
                        for cohort in ("all", "SolidiFI", "nonSolidiFI"):
                            selected = [r for r in rows if cohort == "all" or r["cohort"] == cohort]
                            pooled.append(dict(task_id=task, name=name, checkpoint=ck, cohort=cohort,
                                               **score_or_empty(selected, ck)))
                    for base in bases:
                        comp = "S5-" + base
                        paired.extend(dict(r, comparison=comp) for r in paired_descriptive(
                            records, task, "G3R/S5", "G3R/" + base, ck))
                        pairs = changes(groups["S5"], groups[base], kind, ck)
                        for cohort in ("all", "SolidiFI", "nonSolidiFI"):
                            selected = [r for r in pairs if cohort == "all" or r["cohort"] == cohort]
                            summaries.append(dict(task_id=task, checkpoint=ck, comparison=comp,
                                                  cohort=cohort, **change_summary(selected)))
                        byfile = defaultdict(list)
                        for r in pairs:
                            byfile[(r["file"], r["source_sha256"], r["cohort"])].append(r)
                            if r["probability_delta"] or r["class_changed"]:
                                stream.write(json.dumps(dict(task_id=task, checkpoint=ck,
                                                             comparison=comp, **r)) + "\n")
                            if kind == "node" and r["cohort"] == "nonSolidiFI" and r["target"] == 1:
                                positives.append(dict(task_id=task, checkpoint=ck, comparison=comp, **r))
                        for (file, sha, cohort), rows in byfile.items():
                            files.append(dict(task_id=task, checkpoint=ck, comparison=comp,
                                file=file, source_sha256=sha, cohort=cohort, **change_summary(rows)))
                    means = {n: statistics.mean(scored(tables[(task, n, f)], ck)["buggy_f1"]
                                                for f in range(folds)) for n in names}
                    teacher_gap.append(dict(task_id=task, checkpoint=ck, **retention(
                        means["S5"] - means["S4"], means["S6"] - means["S4"])))
                if kind == "node":
                    expected = plan["statistics"]["descriptive"]["non_solidiFI_positive_rows"][task]
                    actual = sum(r["target"] == 1 and r["cohort"] == "nonSolidiFI" for r in groups["S5"])
                    if actual != expected:
                        raise ValueError("NonSolidiFI positive population differs")
                    count_audit[task] = dict(actual=actual, expected=expected, passed=True)
        tests, holm = inference(records, included)
        gate = read(root / "s8_decision.json")
        if abs(tests[0]["difference_mean_pp"] - gate["mean_delta_pp"]) > 1e-12:
            raise ValueError("Independent report disagrees with registered S8 decision")
        flat = [dict(task_id=r["task_id"], checkpoint=r["checkpoint"], metric=r["metric"],
                     comparison=r["comparison"], **f) for r in paired for f in r["folds"]]
        for filename, rows in (
            ("fold_counts.csv", counts), ("paired_folds.csv", flat),
            ("best_fold_means.csv", [r for r in aggregates if r["checkpoint"] == "best"]),
            ("last_fold_means.csv", [r for r in aggregates if r["checkpoint"] == "last"]),
            ("orig_all_fold_means.csv", aggregate_metrics(orig_records)), ("pooled_oof.csv", pooled),
            ("nonSolidiFI_positive_pairs.csv", positives), ("prediction_change_summary.csv", summaries),
            ("file_error_changes.csv", files), ("resources.csv", resources), ("teacher_gap.csv", teacher_gap)):
            csv_write(out / filename, rows)
        write(out / "fold_metrics.json", records)
        write(out / "orig_all_fold_metrics.json", orig_records)
        write(out / "relation_support_gradients.json", support)
        write(out / "source_receipts.json", source_receipts)
        result = dict(passed=True, new_fits=len(jobs), S4_reference_fits=30, S6_reference_fits=30,
            formal_fits_added=0, model_evals_added=0, checkpoint="best_primary_last_auxiliary",
            view="original", label_policy="L-audit", protocol=plan["protocol"], score_role="outer_test",
            selection_role="inner_val", aggregates=aggregates, paired=paired, pooled=pooled,
            prediction_changes=summaries, primary=tests, holm=holm,
            S8_executed=included, gate=ref(root / "s8_decision.json"), teacher_gap=teacher_gap,
            nonSolidiFI_positive_audit=count_audit, limitations=plan["statistics"]["limitations"])
        write(out / "report.json", result)
        failures = list((root / "runs").glob("*/attempt_*/failure.json"))
        attempts = list((root / "runs").glob("*/attempt_*"))
        write(out / "integrity.json", dict(passed=True, successful_receipts=len(jobs),
            S4_metric_references=30, S6_metric_references=30,
            new_checkpoint_files_checked=len(jobs)*2, S6_checkpoint_files_checked=60,
            S4_missing_best_last=read(checked(plan["na_result_index"]))["missing_checkpoints"],
            failures=len(failures), attempts=len(attempts), runtime_unchanged=True,
            device_tf32_consistent=True, original_and_Laudit_scores_recomputed=True,
            identity_aligned=True, no_new_model_load_or_forward=True))
        for r in sources:
            checked(r)
        write(out / "receipt.json", dict(plan=ref(root / "plan.json"),
            reporting_revision=ref(root / "reporting_revision.json"),
            artifacts=[ref(p) for p in sorted(out.iterdir()) if p.is_file()]))
        write(root / "report_complete.json", dict(passed=True, report=ref(out / "report.json"),
            receipt=ref(out / "receipt.json"), formal_fits=len(jobs), next_phase_authorized=False))
        print(json.dumps(dict(tests=tests, holm=holm)), flush=True)
        return result
    except BaseException:
        import traceback
        write(out / "failure.json", dict(traceback=traceback.format_exc(), automatic_retry=False))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(batch.DEFAULT))
    build(parser.parse_args().root)
