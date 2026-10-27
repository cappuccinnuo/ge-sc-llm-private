"""Pure, preregistered Prompt 8 statistics; no training or artifact reads.

Metrics are percentages, so paired differences and intervals are percentage
points. Cross-validation folds share training data. These descriptive fold
statistics are not independent-seed uncertainty or causal edge contributions.
"""
import math
import numbers
import statistics
import warnings

import numpy as np
import scipy
from scipy.stats import wilcoxon

VERSION = "dfg-v2-statistics-v1"
METRICS = ("buggy_f1", "macro_f1", "precision", "recall")
HOLM_PROFILES = ("G1R", "G2R", "G3R", "G3")


def specification():
    """Return the immutable statistical choices to bind into a new plan."""
    return dict(
        version=VERSION, metrics=list(METRICS), metric_units="percent",
        difference_units="percentage_points", checkpoint_primary="best",
        checkpoint_auxiliary="last", single_seed_aggregation="equal-fold mean and sample standard deviation",
        multiple_seed_aggregation="mean folds within seed, then mean and sample standard deviation across seeds",
        pair_unit="fold for one seed; (fold, seed) for multiple seeds",
        contract_inference="descriptive_only_no_p_value",
        node_wilcoxon=dict(alternative="two-sided", zero_method="zsplit", correction=False,
                           mode="auto", scipy_version=scipy.__version__, warnings="record verbatim",
                           all_zero="statistic n*(n+1)/4; p=1; no normal approximation needed"),
        a12="all cross-distribution pairs: P(profile > baseline) + 0.5*P(tie); not paired win fraction",
        bootstrap=dict(statistic="mean paired difference", repetitions=10000, seed=0,
                       rng="numpy.random.RandomState", interval="percentile 2.5 and 97.5",
                       resampling_unit="paired fold or (fold, seed) differences"),
        holm=dict(family=list(HOLM_PROFILES), baseline="G0", scope="within task, checkpoint and metric",
                  interim="raw p only; adjustment pending until full four-comparison family"),
        interpretation="folds share training data; intervals are descriptive, not independent-seed or causal evidence",
    )


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
        raise ValueError("Finite numeric value required: " + label)
    return float(value)


def _values(values, label):
    values = list(values)
    if not values:
        raise ValueError("Nonempty numeric values required: " + label)
    return [_finite(v, label) for v in values]


def record_key(row):
    return (row["task_id"], row["profile"], row["fold"], row["seed"], row["checkpoint"])


def validate_records(records, expected_keys=None):
    """Validate identities and numeric units, optionally requiring a full matrix.

    No fold counts or vulnerability names are guessed. A caller that knows the
    sealed plan supplies its expected keys to detect missing or extra jobs.
    Returned records are fresh JSON-native dictionaries.
    """
    rows, seen, kinds = [], set(), {}
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("Metric record must be a mapping")
        for field in ("task_id", "profile"):
            if not isinstance(row.get(field), str) or not row[field]:
                raise ValueError("Invalid metric identity: " + field)
        if row.get("task_kind") not in ("contract", "node"):
            raise ValueError("Unknown metric task kind")
        for field, minimum in (("fold", 0), ("seed", 1)):
            if type(row.get(field)) is not int or row[field] < minimum:
                raise ValueError("Invalid metric identity: " + field)
        if row.get("checkpoint") not in ("best", "last"):
            raise ValueError("Unknown metric checkpoint")
        if not isinstance(row.get("metrics"), dict) or not set(METRICS) <= set(row["metrics"]):
            raise ValueError("Metric record lacks required metrics")
        values = {name: _finite(row["metrics"][name], name) for name in METRICS}
        if any(v < 0 or v > 100 for v in values.values()):
            raise ValueError("Metrics must be percentages in [0, 100]")
        key = record_key(row)
        if key in seen:
            raise ValueError("Duplicate task/profile/fold/seed/checkpoint metric identity")
        seen.add(key)
        old_kind = kinds.setdefault(row["task_id"], row["task_kind"])
        if old_kind != row["task_kind"]:
            raise ValueError("Task kind differs within the same task")
        rows.append(dict(task_id=row["task_id"], task_kind=row["task_kind"], profile=row["profile"],
                         fold=row["fold"], seed=row["seed"], checkpoint=row["checkpoint"], metrics=values))
    if not rows:
        raise ValueError("No metric records")
    if expected_keys is not None:
        expected = [tuple(k) for k in expected_keys]
        if len(expected) != len(set(expected)):
            raise ValueError("Duplicate expected metric identity")
        if seen != set(expected):
            raise ValueError("Incomplete or unexpected metric matrix")
    return sorted(rows, key=record_key)


def _sample_sd(values):
    return float(statistics.stdev(values)) if len(values) > 1 else None


def aggregate_metrics(records):
    """Fold summaries for one seed; seed summaries after fold averaging otherwise."""
    rows = validate_records(records)
    groups = {}
    for row in rows:
        key = (row["task_id"], row["task_kind"], row["profile"], row["checkpoint"])
        groups.setdefault(key, {}).setdefault(row["seed"], []).append(row)
    result = []
    for (task, kind, profile, checkpoint), by_seed in sorted(groups.items()):
        fold_sets = [set(r["fold"] for r in items) for items in by_seed.values()]
        if any(folds != fold_sets[0] for folds in fold_sets):
            raise ValueError("Seed metric matrices have different fold identities")
        for metric in METRICS:
            seed_means = [dict(seed=seed, fold_mean=float(statistics.mean(r["metrics"][metric] for r in items)),
                               n_folds=len(items)) for seed, items in sorted(by_seed.items())]
            if len(by_seed) == 1:
                units = [r["metrics"][metric] for r in next(iter(by_seed.values()))]
                aggregation = "equal_fold_mean_and_sample_sd"
            else:
                units = [r["fold_mean"] for r in seed_means]
                aggregation = "fold_mean_per_seed_then_seed_mean_and_sample_sd"
            result.append(dict(task_id=task, task_kind=kind, profile=profile, checkpoint=checkpoint,
                               metric=metric, mean=float(statistics.mean(units)), sample_sd=_sample_sd(units),
                               n_seeds=len(by_seed), n_pairs=sum(len(v) for v in by_seed.values()),
                               aggregation=aggregation, seed_means=seed_means, metric_units="percent"))
    return result


def a12(left, right):
    """Vargha-Delaney A12, treating larger scores as better (marginal, not paired)."""
    left, right = _values(left, "A12 profile"), _values(right, "A12 baseline")
    favorable = sum((a > b) + .5 * (a == b) for a in left for b in right)
    return float(favorable / (len(left) * len(right)))


def paired_bootstrap_ci(differences, repetitions=10000, seed=0):
    """Percentile interval of mean paired differences; never resample model nodes."""
    differences = np.asarray(_values(differences, "paired differences"), dtype=np.float64)
    if type(repetitions) is not int or repetitions < 1 or type(seed) is not int or seed < 0:
        raise ValueError("Invalid bootstrap repetition count or seed")
    rng = np.random.RandomState(seed)
    indices = rng.randint(0, len(differences), size=(repetitions, len(differences)))
    means = differences[indices].mean(axis=1)
    return [float(v) for v in np.percentile(means, [2.5, 97.5])]


def paired_comparison(records, task_id, profile, baseline="G0", checkpoint="best", metric="buggy_f1"):
    """Align by frozen (fold, seed), then compare profile minus baseline."""
    if metric not in METRICS or checkpoint not in ("best", "last") or profile == baseline:
        raise ValueError("Invalid paired comparison request")
    rows = validate_records(records)
    left, right = {}, {}
    kind = None
    for row in rows:
        if row["task_id"] != task_id or row["checkpoint"] != checkpoint:
            continue
        kind = row["task_kind"]
        key = (row["fold"], row["seed"])
        if row["profile"] == profile:
            left[key] = row["metrics"][metric]
        elif row["profile"] == baseline:
            right[key] = row["metrics"][metric]
    if not left or set(left) != set(right):
        raise ValueError("Paired comparison requires identical nonempty fold/seed identities")
    pairs = [dict(fold=fold, seed=seed, profile_score=left[(fold, seed)],
                  baseline_score=right[(fold, seed)], difference_pp=left[(fold, seed)] - right[(fold, seed)])
             for fold, seed in sorted(left)]
    differences = [p["difference_pp"] for p in pairs]
    seeds = {p["seed"] for p in pairs}
    by_seed = [{p["fold"] for p in pairs if p["seed"] == seed} for seed in sorted(seeds)]
    if any(folds != by_seed[0] for folds in by_seed):
        raise ValueError("Paired seeds do not use the same folds")
    notes = ["Cross-validation folds share training data; fold uncertainty is descriptive."]
    if len(seeds) > 1:
        notes.append("Pairs are (fold, seed); repeated folds are not independent data replications.")
    statistic, pvalue, mode = None, None, "not_applicable"
    if kind == "contract":
        inference = "descriptive_only_no_p_value"
        notes.append("Contract tasks are descriptive only; the nonzero exact five-fold minimum .0625 does not apply to zsplit normal approximations.")
    elif all(d == 0 for d in differences):
        statistic = float(len(differences) * (len(differences) + 1) / 4)
        pvalue, mode = 1.0, "all_zero_identity"
        inference = "wilcoxon_two_sided_zsplit"
    else:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            answer = wilcoxon(differences, zero_method="zsplit", correction=False,
                               alternative="two-sided", mode="auto")
        statistic, pvalue = float(answer.statistic), float(answer.pvalue)
        notes.extend(str(w.message) for w in caught)
        # SciPy 1.7.3 auto uses exact for <=25 pairs unless any difference is zero.
        mode = "approx" if len(differences) > 25 or any(d == 0 for d in differences) else "exact"
        inference = "wilcoxon_two_sided_zsplit"
        if len(set(abs(d) for d in differences)) != len(differences):
            notes.append("Tied absolute differences are present; interpret the library's auto p-value cautiously.")
    return dict(task_id=task_id, task_kind=kind, profile=profile, baseline=baseline,
                checkpoint=checkpoint, metric=metric, n_pairs=len(pairs), n_seeds=len(seeds),
                pair_unit="fold" if len(seeds) == 1 else "(fold, seed)", pairs=pairs,
                difference_mean_pp=float(statistics.mean(differences)),
                difference_sample_sd_pp=_sample_sd(differences),
                bootstrap_ci95_pp=paired_bootstrap_ci(differences), bootstrap_repetitions=10000, bootstrap_seed=0,
                a12=a12([p["profile_score"] for p in pairs], [p["baseline_score"] for p in pairs]),
                improved=sum(d > 0 for d in differences), tied=sum(d == 0 for d in differences),
                worsened=sum(d < 0 for d in differences), wilcoxon_statistic=statistic,
                p_raw=pvalue, inference=inference, wilcoxon_requested_mode="auto",
                wilcoxon_effective_mode=mode, scipy_version=scipy.__version__, statistical_warnings=notes)


def holm_adjust(p_values, expected_profiles=HOLM_PROFILES, complete=True):
    """Adjust exactly the preregistered family; interim families remain pending."""
    expected = list(expected_profiles)
    if not expected or len(expected) != len(set(expected)) or not isinstance(p_values, dict) or not p_values:
        raise ValueError("Invalid Holm family")
    if not set(p_values) <= set(expected) or complete and set(p_values) != set(expected):
        raise ValueError("Incomplete or unexpected Holm comparison family")
    raw = {}
    for profile, value in p_values.items():
        raw[profile] = None if value is None else _finite(value, "p-value")
        if raw[profile] is not None and not 0 <= raw[profile] <= 1:
            raise ValueError("P-values must be in [0, 1]")
    result = dict(status="pending_full_family", family_size=len(expected), family=expected,
                  p_raw=raw, p_adjusted={p: None for p in raw})
    if not complete:
        return result
    if all(v is None for v in raw.values()):
        result["status"] = "not_applicable_descriptive_only"
        return result
    if any(v is None for v in raw.values()):
        raise ValueError("Holm family cannot mix inferential and non-inferential comparisons")
    ordered = sorted(raw, key=lambda p: (raw[p], p))
    largest = 0.0
    for index, profile in enumerate(ordered):
        largest = max(largest, (len(expected) - index) * raw[profile])
        result["p_adjusted"][profile] = float(min(1.0, largest))
    result["status"] = "complete_family_adjusted"
    return result
