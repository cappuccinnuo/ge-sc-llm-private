"""Summaries of a training run: fold means, paired comparisons with G0, profile selection.

Statistics follow the Prompt 8H plan: per task and profile the equal-weight fold
mean (and sample SD) of the best checkpoint's outer-test scores; each enhanced
profile is compared with G0 fold by fold. Node tasks get a two-sided Wilcoxon
(zsplit) with Holm adjustment over the enhanced profiles present; contract tasks
(5 folds) are descriptive only. G* is chosen on inner validation only.
"""
import json
import statistics
import warnings
from collections import defaultdict
from pathlib import Path

from dfg.schema import PROFILES

METRICS = ("buggy_f1", "macro_f1", "precision", "recall")
SELECTION = dict(candidates=("G1R", "G2R", "G3R", "G3"), metric="buggy_f1", role="inner_val",
                 checkpoint="best", tie_margin_pp=0.1)


def load(run_dir):
    return [json.loads(p.read_text()) for p in sorted(Path(run_dir).glob("*/fold_*/*/result.json"))]


def _sd(values):
    return statistics.stdev(values) if len(values) > 1 else None


def summarize(records, role="outer_test", checkpoint="best"):
    table = defaultdict(list)
    for r in records:
        table[(r["task_id"], r["profile"])].append(r)
    rows = []
    for (task_id, profile), items in sorted(table.items()):
        row = dict(task_id=task_id, profile=profile, folds=sorted(r["fold"] for r in items))
        for metric in METRICS:
            values = [r[role][checkpoint][metric] for r in items]
            row[metric] = statistics.mean(values)
            row[metric + "_sd"] = _sd(values)
        rows.append(row)
    return rows


def paired(records, task_id, profile, baseline="G0", metric="buggy_f1", checkpoint="best"):
    from scipy.stats import wilcoxon
    left = {r["fold"]: r["outer_test"][checkpoint][metric] for r in records
            if r["task_id"] == task_id and r["profile"] == profile}
    right = {r["fold"]: r["outer_test"][checkpoint][metric] for r in records
             if r["task_id"] == task_id and r["profile"] == baseline}
    folds = sorted(set(left) & set(right))
    if not folds:
        return None
    diffs = [left[f] - right[f] for f in folds]
    kind = next(r["task"] for r in records if r["task_id"] == task_id)
    result = dict(task_id=task_id, profile=profile, baseline=baseline, metric=metric, folds=folds,
                  difference_mean_pp=statistics.mean(diffs), improved=sum(d > 0 for d in diffs),
                  tied=sum(d == 0 for d in diffs), worsened=sum(d < 0 for d in diffs), p_raw=None)
    if kind == "node" and len(diffs) > 1:
        if all(d == 0 for d in diffs):
            result["p_raw"] = 1.0
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result["p_raw"] = float(wilcoxon(diffs, zero_method="zsplit", correction=False,
                                                 alternative="two-sided", mode="auto").pvalue)
    return result


def holm(p_values):
    """Holm step-down over {profile: p}; None stays None."""
    present = {k: v for k, v in p_values.items() if v is not None}
    ordered = sorted(present, key=lambda p: (present[p], p))
    adjusted, largest = {k: None for k in p_values}, 0.0
    for index, profile in enumerate(ordered):
        largest = max(largest, (len(ordered) - index) * present[profile])
        adjusted[profile] = min(1.0, largest)
    return adjusted


def select(records):
    """G*: highest equal-task-weight inner-validation score; ties -> fewer relations, then name."""
    by_profile = defaultdict(lambda: defaultdict(list))
    relations = {}
    for r in records:
        if r["profile"] in SELECTION["candidates"]:
            by_profile[r["profile"]][r["task_id"]].append(
                r[SELECTION["role"]][SELECTION["checkpoint"]][SELECTION["metric"]])
            relations[r["profile"]] = len(PROFILES[r["profile"]])
    if not by_profile:
        return None
    tasks = set.intersection(*(set(v) for v in by_profile.values()))
    score = {p: statistics.mean(statistics.mean(v[t]) for t in tasks) for p, v in by_profile.items()}
    top = max(score.values())
    tied = [p for p in score if top - score[p] <= SELECTION["tie_margin_pp"]]
    chosen = sorted(tied, key=lambda p: (relations[p], p))[0]
    return dict(rule=SELECTION, tasks=sorted(tasks), inner_val_scores=score, selected=chosen)


def report(run_dir, baseline="G0"):
    records = load(run_dir)
    if not records:
        raise SystemExit("no results under " + str(run_dir))
    summary = summarize(records)
    comparisons = []
    for task_id in sorted({r["task_id"] for r in records}):
        family = {}
        for profile in sorted({r["profile"] for r in records if r["task_id"] == task_id} - {baseline}):
            c = paired(records, task_id, profile, baseline=baseline)
            if c is not None:
                comparisons.append(c)
                family[profile] = c["p_raw"]
        adjusted = holm(family)
        for c in comparisons:
            if c["task_id"] == task_id:
                c["p_holm"] = adjusted.get(c["profile"])
    result = dict(fits=len(records), summary=summary, comparisons=comparisons, selection=select(records))
    run_dir = Path(run_dir)
    (run_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# DFG run report", "", "Outer-test, best checkpoint, fold mean (SD), percent.", "",
             "| task | profile | folds | buggy F1 | macro F1 | precision | recall |",
             "|---|---|---|---|---|---|---|"]
    fmt = lambda m, s: "%.2f" % m + ("" if s is None else " (%.2f)" % s)  # noqa: E731
    for row in summary:
        lines.append("| %s | %s | %d | %s |" % (row["task_id"], row["profile"], len(row["folds"]), " | ".join(
            fmt(row[m], row[m + "_sd"]) for m in METRICS)))
    if comparisons:
        lines += ["", "Paired with %s (buggy F1, best checkpoint):" % baseline, "",
                  "| task | profile | mean diff (pp) | improved/tied/worse | p | p Holm |", "|---|---|---|---|---|---|"]
        for c in comparisons:
            p = "-" if c["p_raw"] is None else "%.4f" % c["p_raw"]
            ph = "-" if c.get("p_holm") is None else "%.4f" % c["p_holm"]
            lines.append("| %s | %s | %+.2f | %d/%d/%d | %s | %s |" % (
                c["task_id"], c["profile"], c["difference_mean_pp"], c["improved"], c["tied"], c["worsened"], p, ph))
    if result["selection"]:
        lines += ["", "Selected profile (inner validation only): **%s**" % result["selection"]["selected"]]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n")
    return result
