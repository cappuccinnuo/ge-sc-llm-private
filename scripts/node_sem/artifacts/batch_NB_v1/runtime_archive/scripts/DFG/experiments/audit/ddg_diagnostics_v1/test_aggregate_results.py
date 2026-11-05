import copy
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from scripts.DFG.experiments.audit.ddg_diagnostics_v1.aggregate_results import (
    classification_metrics, independently_compare, align_prediction_rows,
    assert_same_statistics, validate_job_set, weighted_norm_summary,
    summarize_conditions, _merge_csv, _validate_checks, validation_rewiring_scope)
from scripts.DFG.experiments.audit.ddg_diagnostics_v1.diagnostic_common import (
    SCORE_ROLE, PILOTS, compare_outputs)


def records(logits, targets=(0, 1, 1), ids=(11, 14, 20)):
    a = np.asarray(logits, dtype=np.float32)
    probs = torch.from_numpy(a).softmax(1)[:, 1].tolist()
    return [dict(file="a.sol" if i < 2 else "b.sol", original_graph_node_id=ids[i],
                 target=targets[i], prediction=int(a[i].argmax()),
                 logits=a[i].tolist(), positive_probability=probs[i], score_role=SCORE_ROLE)
            for i in range(len(a))]


def test_metrics_formula_matches_explicit_confusion_and_absent_class():
    assert classification_metrics([0, 0, 1, 1], [0, 1, 0, 1]) == dict(
        n=4, positive=2, buggy_f1=50, macro_f1=50, precision=50, recall=50,
        tn_fp_fn_tp=[1, 1, 1, 1])
    value = classification_metrics([0, 0], [0, 0])
    assert value["macro_f1"] == 50
    assert value["buggy_f1"] == 0


def test_independent_recomputation_matches_runner_and_original_id_alignment():
    normal = records([[1, 0], [1, 0], [0, 1]])
    change = records([[0, 1], [0, 1], [0, 1]])
    expected, files, _ = compare_outputs([0, 1, 1],
        np.asarray([r["logits"] for r in normal], dtype=np.float32),
        np.asarray([r["logits"] for r in change], dtype=np.float32),
        [r["file"] for r in normal])
    actual, independently_by_file = independently_compare(change[::-1], normal, "node")
    assert_same_statistics(actual, expected)
    for a, b in zip(independently_by_file, files):
        assert_same_statistics(a, b)
    assert actual["prediction_flips"] == 2
    assert actual["corrected"] == 1 and actual["introduced"] == 1
    assert actual["tn_fp_fn_tp"] == [0, 1, 0, 2]


def test_duplicate_target_identity_and_tampered_probability_rejected():
    normal = records([[1, 0], [1, 0], [0, 1]])
    with pytest.raises(ValueError, match="Duplicate"):
        align_prediction_rows([normal[0], normal[0], normal[2]], normal, "node")
    wrong = copy.deepcopy(normal)
    wrong[1]["target"] = 0
    with pytest.raises(ValueError, match="targets"):
        independently_compare(wrong, normal, "node")
    wrong = copy.deepcopy(normal)
    wrong[1]["original_graph_node_id"] = 99
    with pytest.raises(ValueError, match="identities"):
        independently_compare(wrong, normal, "node")
    wrong = copy.deepcopy(normal)
    wrong[1]["positive_probability"] += 0.1
    with pytest.raises(ValueError, match="probabilities"):
        independently_compare(wrong, normal, "node")


def test_metric_or_flip_corruption_rejected():
    with pytest.raises(ValueError, match="Count"):
        assert_same_statistics({"prediction_flips": 2}, {"prediction_flips": "1"})
    with pytest.raises(ValueError, match="Numerical"):
        assert_same_statistics({"buggy_f1": 98.0}, {"buggy_f1": "99"})
    assert_same_statistics({"logits_exact": True, "tn_fp_fn_tp": [1, 2, 3, 4]},
                           {"logits_exact": "True", "tn_fp_fn_tp": "[1, 2, 3, 4]"})


def planned_jobs():
    return [dict(id=c+"_"+t+"_fold"+str(f), cohort=c, task=t, fold=f)
            for c in ("reentrancy_author", "access_control_author")
            for t in ("contract", "node") for f in range(5 if t == "contract" else 10)]


def test_completeness_requires_30_unique_best_pairs_and_exact_7_pilots():
    jobs = planned_jobs()
    pilot = [j["id"] for j in jobs if (j["cohort"], j["task"], j["fold"]) in PILOTS]
    rest = [j["id"] for j in jobs if j["id"] not in pilot]
    assert len(validate_job_set(jobs, pilot, rest)) == 30
    with pytest.raises(ValueError, match="Incomplete"):
        validate_job_set(jobs, pilot, rest[:-1])
    with pytest.raises(ValueError, match="double-counted"):
        validate_job_set(jobs, pilot, rest + pilot[:1])
    with pytest.raises(ValueError, match="Duplicate completed"):
        validate_job_set(jobs, pilot+pilot[:1], rest)


def norm_row(ntype, count, mean, file="__all__"):
    return dict(cohort="reentrancy_author", task="node", fold="0", variant="E1",
                checkpoint="best", condition="N", layer="0", node_type=ntype,
                file=file, branch="ddg_sum", count=count, population_count=count,
                mean=mean, max=mean, zero_count=0, near_zero_count=0,
                denominator_near_zero_count=0)


def test_norms_node_weighted_without_duplicate_file_or_false_quantiles():
    rows = [norm_row("a", 1, 10), norm_row("b", 9, 0),
            norm_row("a", 1, 10, "one.sol"), norm_row("b", 9, 0, "two.sol")]
    result = weighted_norm_summary(rows)[0]
    assert result["count"] == 10
    assert result["node_weighted_mean"] == 1  # not type average 5
    assert result["global_median"] is None and result["global_p95"] is None
    with pytest.raises(ValueError, match="Duplicate type"):
        weighted_norm_summary(rows + [rows[0]])


def test_ratio_near_zero_denominators_excluded_not_diluted():
    one = norm_row("a", 1, 2)
    one.update(branch="ddg_to_base_ratio", population_count=5,
               denominator_near_zero_count=4)
    two = norm_row("b", 0, "")
    two.update(branch="ddg_to_base_ratio", population_count=2,
               denominator_near_zero_count=2, max="")
    value = weighted_norm_summary([one, two])[0]
    assert value["count"] == 1
    assert value["population_count"] == 7
    assert value["excluded_near_zero_denominator"] == 6
    assert value["node_weighted_mean"] == 2


def scored_row(fold, condition="N", variant="E1"):
    rows = records([[1, 0], [1, 0], [0, 1]])
    comparison, _ = independently_compare(rows, rows, "node")
    return dict(comparison, cohort="reentrancy_author", task="node", fold=fold,
                checkpoint="best", variant=variant, condition=condition)


def test_comparison_rows_are_not_second_normal_observation():
    row = scored_row(0)
    comparison = dict(row, condition="E1_N_vs_E0_N")
    result = summarize_conditions([row, comparison],
                                 expected_counts={("reentrancy_author", "node"): 1})
    assert len(result) == 1 and result[0]["folds"] == [0]
    with pytest.raises(ValueError, match="Duplicate"):
        summarize_conditions([row, row])
    with pytest.raises(ValueError, match="Incomplete"):
        summarize_conditions([row], expected_counts={("reentrancy_author", "node"): 10})


def test_merge_exclusive_and_checks_fail_closed(tmp_path):
    source = tmp_path/"source.csv"
    source.write_text("a,b\n1,2\n")
    output = tmp_path/"merged.csv"
    _merge_csv([source], output)
    assert output.read_text().splitlines() == ["a,b", "1,2"]
    with pytest.raises(FileExistsError):
        _merge_csv([source], output)
    with pytest.raises(ValueError, match="missing/failed"):
        _validate_checks({}, "best")


def rewiring_fixture():
    def group(file, edges, replaced, eids):
        return dict(file=file, edge_count=edges, replaced_semantic_edges=replaced,
                    changed_eid_endpoints=eids,
                    effective_semantic_perturbation=bool(replaced))
    return dict(ddg_edges=30, replaced_semantic_edges=8, changed_eid_endpoints=12,
                group_details=[group("train.sol",20,8,12), group("val.sol",10,0,0)])


def test_rewiring_validation_scope_does_not_mistake_train_changes_for_scored_changes():
    result = validation_rewiring_scope(rewiring_fixture(), ["val.sol", "no_ddg.sol"], ["train.sol"])
    assert result["validation_ddg_edges"] == 10
    assert result["validation_replaced_semantic_edges"] == 0
    assert result["validation_semantic_perturbation_fraction"] == 0
    assert result["validation_effective_groups"] == 0
    assert result["validation_files"] == 2
    assert result["validation_unchanged_files"] == 2
    assert result["training_replaced_semantic_edges"] == 8


def test_validation_semantic_edge_changes_are_distinct_from_eid_permutations():
    audit = rewiring_fixture()
    audit.update(replaced_semantic_edges=10, changed_eid_endpoints=16)
    audit["group_details"][1].update(replaced_semantic_edges=2,
        changed_eid_endpoints=4, effective_semantic_perturbation=True)
    result = validation_rewiring_scope(audit, ["val.sol"], ["train.sol"])
    assert result["validation_semantic_perturbation_fraction"] == .2
    assert result["validation_changed_eid_endpoints"] == 4
    assert result["validation_effective_files"] == ["val.sol"]
    assert result["validation_effective_groups"] == 1


def test_validation_scope_rejects_wrong_partition_and_inconsistent_group_totals():
    audit = rewiring_fixture()
    with pytest.raises(ValueError, match="partition"):
        validation_rewiring_scope(audit, ["val.sol"], ["val.sol", "train.sol"])
    with pytest.raises(ValueError, match="outside"):
        validation_rewiring_scope(audit, ["another.sol"], ["train.sol"])
    audit["ddg_edges"] += 1
    with pytest.raises(ValueError, match="edge count"):
        validation_rewiring_scope(audit, ["val.sol"], ["train.sol"])
