"""FULL against the G0 baseline over several seeds of the grouped benchmark.

Each seed is one ``python -m benchmark run --protocols grouped --profiles G0 FULL``
directory. Every metric is computed per (seed, fold) from the fits' held-out
predictions, so FULL and G0 are paired on the same files; the paired difference is
tested with a two-sided Wilcoxon signed-rank test (zsplit, as ``dfg.train.report``)
and Holm-adjusted over the categories of one metric. Pooled scores (all held-out
folds of a seed together, the benchmark's by-source view) are reported as the mean
and standard deviation over seeds.

Metrics (best checkpoint):

    line_dappscan     line track, nodes of DAppSCAN contracts        (the main metric)
    line_all          line track, every held-out node
    contract_dappscan contract track, DAppSCAN files and their DAppSCAN-clean counterparts
    contract_all      contract track, every held-out contract

A fold without a vulnerable node (or contract) of a metric's population is left out
of that metric's pairs.
"""
import json
import statistics
import warnings
from pathlib import Path

from benchmark.evaluate import CLEAN, CategoryRefs, fold_outputs
from combined import PROFILE
from dfg.train.report import holm
from dfg.utils import metrics

BASELINE = "G0"
PROTOCOL = "grouped"
METRICS = {"line_dappscan": ("line", "DAppSCAN"), "line_all": ("line", None),
           "contract_dappscan": ("contract", "DAppSCAN"), "contract_all": ("contract", None)}
MAIN = "line_dappscan"


def population(rows, refs, source):
    """Rows of one source's files (with its paired clean files), or all rows."""
    if source is None:
        return rows
    return [r for r in rows if refs.source[r["file"]] == source or
            (refs.source[r["file"]] == CLEAN and refs.pairs.get(r["file"], source) == source)]


def _score(rows):
    if not rows or not any(r["target"] for r in rows):
        return None
    return metrics([r["target"] for r in rows], [r["best"] for r in rows])["buggy_f1"]


def category_scores(runs, refs):
    """{metric: {"pairs": [(seed, fold, full, g0)], "pooled": {seed: (full, g0)}}} of a category."""
    out = {name: dict(pairs=[], pooled={}) for name in METRICS}
    for seed, run in runs.items():
        for name, (track, source) in METRICS.items():
            task_dir = Path(run) / PROTOCOL / ("%s_%s" % (refs.category, track))
            full, base = fold_outputs(task_dir, PROFILE), fold_outputs(task_dir, BASELINE)
            pooled = {PROFILE: [], BASELINE: []}
            for fold in sorted(set(full) & set(base)):
                left = population(full[fold][1]["outer_test"], refs, source)
                right = population(base[fold][1]["outer_test"], refs, source)
                pooled[PROFILE] += left
                pooled[BASELINE] += right
                a, b = _score(left), _score(right)
                if a is not None and b is not None:
                    out[name]["pairs"].append((seed, fold, a, b))
            a, b = _score(pooled[PROFILE]), _score(pooled[BASELINE])
            if a is not None and b is not None:
                out[name]["pooled"][seed] = (a, b)
    return out


def test(pairs):
    """Paired summary and Wilcoxon p of FULL - G0 over (seed, fold) pairs."""
    from scipy.stats import wilcoxon
    diffs = [a - b for _, _, a, b in pairs]
    result = dict(pairs=len(diffs), improved=sum(d > 0 for d in diffs), tied=sum(d == 0 for d in diffs),
                  worsened=sum(d < 0 for d in diffs), difference_mean_pp=statistics.mean(diffs) if diffs else None,
                  p_raw=None)
    if len(diffs) > 1:
        if all(d == 0 for d in diffs):
            result["p_raw"] = 1.0
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result["p_raw"] = float(wilcoxon(diffs, zero_method="zsplit", correction=False,
                                                 alternative="two-sided", mode="auto").pvalue)
    return result


def _mean_sd(values):
    return (statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0.0) if values else (None, None)


def compare(runs, hcg_root, dataset, categories):
    """The comparison document; ``runs`` maps seed -> run directory."""
    table = {}
    for category in categories:
        if not any((Path(r) / PROTOCOL / ("%s_line" % category)).is_dir() for r in runs.values()):
            continue
        scores = category_scores(runs, CategoryRefs(hcg_root, dataset, category))
        table[category] = {}
        for name, part in scores.items():
            pooled = part["pooled"].values()
            full, base = _mean_sd([a for a, _ in pooled]), _mean_sd([b for _, b in pooled])
            table[category][name] = dict(test(part["pairs"]), full_pooled=full[0], full_pooled_sd=full[1],
                                         g0_pooled=base[0], g0_pooled_sd=base[1], seeds=sorted(part["pooled"]))
    for name in METRICS:
        adjusted = holm({c: table[c][name]["p_raw"] for c in table})
        for category, p in adjusted.items():
            table[category][name]["p_holm"] = p
    return dict(dataset=dataset, protocol=PROTOCOL, profile=PROFILE, baseline=BASELINE, main_metric=MAIN,
                runs={str(k): str(v) for k, v in runs.items()}, categories=table)


def _cell(value, sd=None):
    if value is None:
        return "-"
    return "%.2f" % value if sd is None else "%.2f ± %.2f" % (value, sd)


def render(document):
    lines = ["# FULL vs G0 (%s protocol, Dataset %s, seeds %s)" % (
        document["protocol"], document["dataset"], ", ".join(document["runs"])), ""]
    lines.append("Buggy-F1, best checkpoint. *Pooled*: all held-out folds of a seed together, mean ± sd over "
                 "seeds. *Δ*: mean of FULL − G0 over (seed, fold) pairs; p: Wilcoxon signed-rank, Holm over "
                 "categories. Main metric: `%s`." % document["main_metric"])
    for name in METRICS:
        lines += ["", "## %s" % name, "", "| category | G0 pooled | FULL pooled | Δ (pp) | +/=/− | p | p (Holm) |",
                  "|---|---|---|---|---|---|---|"]
        for category, part in document["categories"].items():
            row = part[name]
            lines.append("| %s | %s | %s | %s | %d/%d/%d | %s | %s |" % (
                category, _cell(row["g0_pooled"], row["g0_pooled_sd"]), _cell(row["full_pooled"], row["full_pooled_sd"]),
                _cell(row["difference_mean_pp"]), row["improved"], row["tied"], row["worsened"],
                "-" if row["p_raw"] is None else "%.4f" % row["p_raw"],
                "-" if row["p_holm"] is None else "%.4f" % row["p_holm"]))
    return "\n".join(lines) + "\n"


def write(document, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "compare.json").write_text(json.dumps(document, indent=1) + "\n")
    text = render(document)
    (out / "compare.md").write_text(text)
    return text
