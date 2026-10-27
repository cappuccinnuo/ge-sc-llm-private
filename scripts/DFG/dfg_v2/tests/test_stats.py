"""Prompt 8 statistical units, complete pairing and preregistered inference."""
import copy
import json
import math

import numpy as np
import pytest

from scripts.DFG.dfg_v2.experiment import stats


def record(profile, fold, value, seed=1, task="arbitrary_node", kind="node", checkpoint="best"):
    return dict(task_id=task, task_kind=kind, profile=profile, fold=fold, seed=seed,
                checkpoint=checkpoint, metrics={name: value for name in stats.METRICS})


def paired(left, right, kind="node", seeds=(1,)):
    return [record(profile, fold, value, seed=seed, kind=kind)
            for seed in seeds for profile, values in (("G0", right), ("G3R", left))
            for fold, value in enumerate(values)]


def test_specification_is_fresh_json_native_and_contains_approved_rules():
    spec = stats.specification()
    assert spec["contract_inference"] == "descriptive_only_no_p_value"
    assert spec["node_wilcoxon"]["zero_method"] == "zsplit"
    assert spec["bootstrap"]["repetitions"] == 10000
    assert spec["bootstrap"]["seed"] == 0
    assert len(spec["holm"]["family"]) == 4
    spec["holm"]["family"].append("bad")
    assert len(stats.specification()["holm"]["family"]) == 4
    json.dumps(stats.specification(), allow_nan=False)


def test_records_are_identity_sorted_independent_copies_and_percentage_native():
    rows = [record("G3R", 1, np.float64(80)), record("G0", 0, 70)]
    before = copy.deepcopy(rows)
    valid = stats.validate_records(rows, expected_keys=[stats.record_key(r) for r in rows])
    assert rows == before
    assert valid[0]["profile"] == "G0"
    assert type(valid[1]["metrics"]["buggy_f1"]) is float
    valid[0]["metrics"]["buggy_f1"] = 100
    assert rows[1]["metrics"]["buggy_f1"] == 70


@pytest.mark.parametrize("damage", ["missing", "extra", "duplicate", "expected_duplicate"])
def test_expected_matrix_rejects_missing_extra_duplicate_fold_seed(damage):
    rows = [record("G0", fold, 50) for fold in range(3)]
    expected = [stats.record_key(r) for r in rows]
    if damage == "missing":
        rows.pop()
    elif damage == "extra":
        rows.append(record("G0", 3, 60))
    elif damage == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    else:
        expected.append(expected[0])
    with pytest.raises(ValueError):
        stats.validate_records(rows, expected_keys=expected)


@pytest.mark.parametrize("field,value", [
    ("task_id", ""), ("profile", ""), ("fold", -1), ("fold", True),
    ("fold", 0.0), ("seed", 0), ("seed", True), ("checkpoint", "picked"),
    ("task_kind", "source_line"),
])
def test_invalid_metric_identity_rejected(field, value):
    row = record("G0", 0, 50)
    row[field] = value
    with pytest.raises(ValueError):
        stats.validate_records([row])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 101, True, "50"])
def test_invalid_numeric_metrics_rejected(value):
    row = record("G0", 0, 50)
    row["metrics"]["buggy_f1"] = value
    with pytest.raises(ValueError):
        stats.validate_records([row])


def test_missing_metric_and_mixed_task_kind_rejected():
    row = record("G0", 0, 50)
    del row["metrics"]["recall"]
    with pytest.raises(ValueError, match="required metrics"):
        stats.validate_records([row])
    with pytest.raises(ValueError, match="Task kind"):
        stats.validate_records([record("G0", 0, 50), record("G0", 1, 50, kind="contract")])


def test_single_seed_aggregation_is_equal_fold_not_sample_weighted():
    rows = [record("G0", i, value) for i, value in enumerate([20, 40, 60])]
    rows[0]["n"] = 100000
    answer = stats.aggregate_metrics(rows)[0]
    assert answer["mean"] == 40
    assert answer["sample_sd"] == 20
    assert answer["n_seeds"] == 1
    assert answer["n_pairs"] == 3
    assert answer["aggregation"] == "equal_fold_mean_and_sample_sd"


def test_best_last_and_tasks_remain_separate():
    rows = [record("G0", 0, 50), record("G0", 0, 80, checkpoint="last"),
            record("G0", 0, 30, task="another_node")]
    result = stats.aggregate_metrics(rows)
    assert len(result) == 12
    values = {(r["task_id"], r["checkpoint"]): r["mean"] for r in result}
    assert values[("arbitrary_node", "best")] == 50
    assert values[("arbitrary_node", "last")] == 80
    assert values[("another_node", "best")] == 30
    assert all(r["sample_sd"] is None for r in result)


def test_multiseed_aggregation_uses_sample_sd_of_seed_means():
    rows = [record("G0", fold, value, seed=seed)
            for seed, values in ((1, [0, 20]), (2, [40, 60]))
            for fold, value in enumerate(values)]
    answer = stats.aggregate_metrics(rows)[0]
    assert answer["mean"] == 30
    assert answer["sample_sd"] == pytest.approx(math.sqrt(800))
    assert answer["seed_means"] == [dict(seed=1, fold_mean=10, n_folds=2),
                                     dict(seed=2, fold_mean=50, n_folds=2)]
    assert answer["aggregation"].startswith("fold_mean_per_seed")
    with pytest.raises(ValueError, match="different fold"):
        stats.aggregate_metrics(rows[:-1])


def test_pair_alignment_uses_fold_and_seed_not_input_row_order():
    rows = paired([60, 50, 40], [50, 50, 50])
    answer = stats.paired_comparison(list(reversed(rows)), "arbitrary_node", "G3R")
    assert [r["difference_pp"] for r in answer["pairs"]] == [10, 0, -10]
    assert answer["difference_mean_pp"] == 0
    assert answer["difference_sample_sd_pp"] == 10
    assert (answer["improved"], answer["tied"], answer["worsened"]) == (1, 1, 1)
    assert answer["pair_unit"] == "fold"
    json.dumps(answer, allow_nan=False)


@pytest.mark.parametrize("damage", ["missing", "wrong_fold", "wrong_seed", "wrong_checkpoint", "duplicate"])
def test_pairing_rejects_missing_or_unmatched_identities(damage):
    rows = paired([60, 70, 80], [50, 60, 70])
    if damage == "missing":
        rows.pop()
    elif damage == "wrong_fold":
        rows[-1]["fold"] = 4
    elif damage == "wrong_seed":
        rows[-1]["seed"] = 2
    elif damage == "wrong_checkpoint":
        rows[-1]["checkpoint"] = "last"
    else:
        rows.append(copy.deepcopy(rows[-1]))
    with pytest.raises(ValueError):
        stats.paired_comparison(rows, "arbitrary_node", "G3R")


def test_contract_inference_never_calls_wilcoxon_even_for_zero_ties(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("Contract inference must be descriptive")
    monkeypatch.setattr(stats, "wilcoxon", prohibited)
    answer = stats.paired_comparison(paired([50, 51, 51, 51, 51], [50] * 5, kind="contract"),
                                     "arbitrary_node", "G3R")
    assert answer["p_raw"] is None and answer["wilcoxon_statistic"] is None
    assert answer["inference"] == "descriptive_only_no_p_value"
    assert answer["difference_mean_pp"] == .8
    assert answer["wilcoxon_effective_mode"] == "not_applicable"


def test_all_zero_node_differences_are_identity_p_one_not_exception(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("No approximate test required for all-zero differences")
    monkeypatch.setattr(stats, "wilcoxon", prohibited)
    answer = stats.paired_comparison(paired([50] * 10, [50] * 10), "arbitrary_node", "G3R")
    assert answer["p_raw"] == 1
    assert answer["wilcoxon_statistic"] == 27.5
    assert answer["wilcoxon_effective_mode"] == "all_zero_identity"
    assert answer["bootstrap_ci95_pp"] == [0, 0]
    assert answer["a12"] == .5


def test_ten_positive_node_differences_reproduce_exact_library_value():
    answer = stats.paired_comparison(paired([51] * 10, [50] * 10), "arbitrary_node", "G3R")
    assert answer["p_raw"] == .001953125
    assert answer["wilcoxon_effective_mode"] == "exact"
    assert answer["bootstrap_ci95_pp"] == [1, 1]
    assert answer["improved"] == 10


def test_node_zeros_record_normal_approximation_and_library_warnings():
    answer = stats.paired_comparison(paired([50, 51, 51, 51, 51], [50] * 5), "arbitrary_node", "G3R")
    assert answer["p_raw"] == pytest.approx(.04771488023735121)
    assert answer["wilcoxon_effective_mode"] == "approx"
    assert any("normal approximation" in w for w in answer["statistical_warnings"])


def test_multiseed_pair_unit_and_warning_are_explicit():
    answer = stats.paired_comparison(paired([60, 50], [50, 50], seeds=(1, 2)),
                                     "arbitrary_node", "G3R")
    assert answer["n_pairs"] == 4 and answer["n_seeds"] == 2
    assert answer["pair_unit"] == "(fold, seed)"
    assert any("not independent" in w for w in answer["statistical_warnings"])
    assert [(p["fold"], p["seed"]) for p in answer["pairs"]] == [(0, 1), (0, 2), (1, 1), (1, 2)]


def test_pairs_reject_unequal_fold_sets_across_seeds():
    rows = paired([60, 50], [50, 50], seeds=(1, 2))
    rows = [r for r in rows if not (r["fold"] == 1 and r["seed"] == 2)]
    with pytest.raises(ValueError, match="same folds"):
        stats.paired_comparison(rows, "arbitrary_node", "G3R")


@pytest.mark.parametrize("left,right,expected", [
    ([2, 3], [0, 1], 1), ([0, 1], [2, 3], 0),
    ([1, 2], [1, 2], .5), ([2, 2], [1, 2], .75),
])
def test_a12_matches_explicit_cross_pair_probabilities(left, right, expected):
    assert stats.a12(left, right) == expected
    assert stats.a12(right, left) == 1 - expected


def test_a12_is_not_substituted_with_paired_wins():
    # Both aligned differences are positive, but one cross pair is unfavorable.
    answer = stats.paired_comparison(paired([1, 11], [0, 10]), "arbitrary_node", "G3R")
    assert answer["improved"] == 2
    assert answer["a12"] == .75


def test_bootstrap_uses_paired_differences_and_does_not_touch_global_rng():
    np.random.seed(43)
    before = np.random.get_state()
    first = stats.paired_bootstrap_ci([-2, 0, 1, 5])
    after = np.random.get_state()
    assert all(np.array_equal(a, b) for a, b in zip(before, after))
    assert first == stats.paired_bootstrap_ci([-2, 0, 1, 5])
    # Independent construction of the fixed percentile bootstrap.
    rng = np.random.RandomState(0)
    draws = rng.randint(0, 4, size=(10000, 4))
    expected = np.percentile(np.asarray([-2, 0, 1, 5])[draws].mean(1), [2.5, 97.5]).tolist()
    assert first == expected
    assert stats.paired_bootstrap_ci([7, 7]) == [7, 7]


@pytest.mark.parametrize("values", [[], [float("nan")], [True]])
def test_empty_or_invalid_statistical_vectors_rejected(values):
    with pytest.raises(ValueError):
        stats.a12(values, [1])
    with pytest.raises(ValueError):
        stats.paired_bootstrap_ci(values)


def test_holm_four_family_uses_stepdown_monotonic_adjustment():
    p = dict(G1R=.01, G2R=.03, G3R=.04, G3=.20)
    answer = stats.holm_adjust(p)
    assert answer["status"] == "complete_family_adjusted"
    assert answer["family_size"] == 4
    assert answer["p_adjusted"] == dict(G1R=.04, G2R=.09, G3R=.09, G3=.20)
    assert p == dict(G1R=.01, G2R=.03, G3R=.04, G3=.20)


def test_interim_raw_p_does_not_fake_a_complete_adjustment():
    answer = stats.holm_adjust({"G3R": .01}, complete=False)
    assert answer["status"] == "pending_full_family"
    assert answer["family_size"] == 4
    assert answer["p_raw"] == {"G3R": .01}
    assert answer["p_adjusted"] == {"G3R": None}
    with pytest.raises(ValueError, match="family"):
        stats.holm_adjust({"G3R": .01})


def test_contract_holm_remains_not_applicable_and_mixed_none_rejected():
    answer = stats.holm_adjust(dict.fromkeys(stats.HOLM_PROFILES))
    assert answer["status"] == "not_applicable_descriptive_only"
    assert all(v is None for v in answer["p_adjusted"].values())
    mixed = dict.fromkeys(stats.HOLM_PROFILES)
    mixed["G3R"] = .01
    with pytest.raises(ValueError, match="mix"):
        stats.holm_adjust(mixed)


@pytest.mark.parametrize("damage", ["unknown", "nan", "negative", "large", "boolean"])
def test_holm_rejects_invalid_family_and_p_values(damage):
    p = dict.fromkeys(stats.HOLM_PROFILES, .1)
    if damage == "unknown":
        p["G3R_vs_G3"] = .1
    else:
        p["G3R"] = {"nan": float("nan"), "negative": -.1, "large": 1.1, "boolean": True}[damage]
    with pytest.raises(ValueError):
        stats.holm_adjust(p)
