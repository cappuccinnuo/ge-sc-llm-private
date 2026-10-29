"""Prompt 8C D summary checks: no checkpoint loading or GPU."""
import copy
import json

import pytest

from scripts.DFG.dfg_v2.diagnostics8c import inference_summary as d
from scripts.DFG.dfg_v2.diagnostics8c import scoring as s


def case(fold=0, filename="buggy_1.sol", node=4):
    job = dict(task_id="r_node", fold=fold, seed=1, profile="G0", layer_impl="shared_projection")
    source = {"path": "/sources/" + filename, "sha256": "abc"}
    original = dict(file=filename, original_graph_node_id=node, target=0,
                    best=1, best_positive_probability=.8)
    view = dict(file=filename, original_graph_node_id=node, source_sha256="abc",
                orig=0, C1=1, fold=fold)
    row = dict(file=filename, original_graph_node_id=node, source_sha256="abc",
               target=0, original_best=1, original_probability=.8,
               renamed_best=0, renamed_probability=.3)
    report = dict(
        job=job, plan_sha256="plan", gate_only=False, optimizer_steps=0,
        graph={"path": "/graph", "sha256": "graph"}, source_refs={filename: source},
        mappings={filename: {"re_ent": "id0"}}, predictions=[row],
        changed_predictions=1, changed_probabilities=1,
        changed_nodes=[dict(file=filename, original_graph_node_id=node, source_sha256="abc",
                            replacements=1, code_before_sha256="before", code_after_sha256="after",
                            feature_changed=True)], changed_code_count=1, changed_feature_count=1,
        tokenizer={"model": "frozen", "network_used": False, "model_weights_loaded": False},
        seconds=2, peak_allocated_bytes=5, peak_reserved_bytes=7)
    report.update({flag: True for flag in d.FLAGS})
    task = {"record": {"sources": {filename: source}, "feature": {"model": "frozen"}}}
    return report, task, [original], {(filename, node): view}


def validate(report, task, original, views):
    return d.validate_report(report, report["job"], "plan", task, {"graph": {"path": "/graph", "sha256": "graph"}},
                             original, views)


def test_valid_job_is_identity_aligned_without_row_order():
    report, task, original, views = case()
    before = copy.deepcopy((report, task, original, views))
    assert validate(report, task, original, views) == report["predictions"]
    assert (report, task, original, views) == before


@pytest.mark.parametrize("field,value", [
    ("source_sha256", "wrong"), ("target", 1), ("original_best", 0),
    ("original_probability", .7), ("renamed_best", 2),
    ("renamed_probability", float("nan")), ("renamed_probability", -1),
    ("original_graph_node_id", 99)])
def test_row_corruption_rejected(field, value):
    report, task, original, views = case()
    report["predictions"][0][field] = value
    with pytest.raises(ValueError):
        validate(report, task, original, views)


def test_same_basename_other_cohort_sha_rejected():
    report, task, original, views = case()
    views[("buggy_1.sol", 4)]["source_sha256"] = "other_cohort_sha"
    with pytest.raises(ValueError, match="source"):
        validate(report, task, original, views)


@pytest.mark.parametrize("field", d.FLAGS)
def test_invariant_flag_required(field):
    report, task, original, views = case()
    report[field] = False
    with pytest.raises(ValueError, match="invariant"):
        validate(report, task, original, views)


def test_duplicate_prediction_refused():
    report, task, original, views = case()
    report["predictions"].append(copy.deepcopy(report["predictions"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        validate(report, task, original, views)


def test_reported_counts_recomputed():
    report, task, original, views = case()
    report["changed_predictions"] = 0
    with pytest.raises(ValueError, match="changes differ"):
        validate(report, task, original, views)


def test_feature_changes_cannot_escape_outer_nodes():
    report, task, original, views = case()
    report["changed_nodes"][0]["original_graph_node_id"] = 99
    with pytest.raises(ValueError, match="escape"):
        validate(report, task, original, views)


def test_tokenizer_recipe_must_remain_frozen():
    report, task, original, views = case()
    report["tokenizer"]["model"] = "new model"
    with pytest.raises(ValueError, match="recipe"):
        validate(report, task, original, views)


def test_probability_change_without_class_change_is_distinct():
    report, _, _, views = case()
    report["predictions"][0]["renamed_best"] = 1
    changes = d.changes_for(report["predictions"], views, "orig")
    assert changes["changed_predictions"] == 0
    assert changes["changed_probabilities"] == 1
    assert changes["mean_absolute_probability_change"] == .5
    assert changes["corrected_errors"] == changes["introduced_errors"] == 0


def test_C1_same_prediction_can_reverse_error_interpretation():
    report, _, _, views = case()
    old = d.changes_for(report["predictions"], views, "orig")
    sensitivity = d.changes_for(report["predictions"], views, "C1")
    assert (old["corrected_errors"], old["introduced_errors"]) == (1, 0)
    assert (sensitivity["corrected_errors"], sensitivity["introduced_errors"]) == (0, 1)


def test_aggregate_equal_fold_means_pooled_and_complete_identity():
    first, _, _, v1 = case(0)
    second, _, _, v2 = case(1, "other.sol", 5)
    views = dict(v1, **{})  # tuple identity keys deliberately retained
    views.update(v2)
    tables = d.aggregate("r_node", "G0", {0: first, 1: second}, views)
    assert len(tables["fold_metrics"]) == 8
    assert len(tables["pooled_metrics"]) == 4
    assert len(tables["fold_means"]) == 4
    assert len(tables["pooled_changes"]) == 2
    c1_old = next(r for r in tables["pooled_metrics"] if r["view"] == "C1" and r["mode"] == "original")
    c1_new = next(r for r in tables["pooled_metrics"] if r["view"] == "C1" and r["mode"] == "renamed")
    assert c1_old["buggy_f1"] == 100
    assert c1_new["buggy_f1"] == 0
    with pytest.raises(ValueError, match="Incomplete"):
        d.aggregate("r_node", "G0", {0: first}, views)


def test_aggregate_rejects_same_node_in_two_folds():
    first, _, _, views = case()
    with pytest.raises(ValueError, match="Repeated"):
        d.aggregate("r_node", "G0", {0: first, 1: first}, views)


def test_partial_matrix_writes_no_summary(tmp_path):
    jobs = []
    tasks = {}
    for task in ("r_node", "ac_node"):
        tasks[task] = {"record": {"task": "node"}}
        for fold in range(10):
            for profile in ("G0", "G1R", "G2R", "G3R", "G3"):
                jobs.append(dict(task_id=task, fold=fold, seed=1, profile=profile))
    for task in ("r_contract", "ac_contract"):
        tasks[task] = {"record": {"task": "contract"}}
        for fold in range(5):
            for profile in ("G0", "G1R", "G2R", "G3R", "G3"):
                jobs.append(dict(task_id=task, fold=fold, seed=1, profile=profile))
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(dict(tasks=tasks, jobs=jobs)), encoding="utf8")
    (tmp_path / "plan.seal.json").write_text(json.dumps({"plan_sha256": s.sha(plan)}), encoding="utf8")
    verification = tmp_path / "verification.json"
    verification.write_text(json.dumps(dict(plan_sha256=s.sha(plan), verified=150,
        fits=[dict(job=j, status="verified") for j in jobs])), encoding="utf8")
    output = tmp_path / "D"
    (output / "jobs").mkdir(parents=True)
    with pytest.raises(ValueError, match="Incomplete D matrix: 0/100"):
        d.summarize(plan, tmp_path / "views.json", output, verification)
    assert not (output / "summary").exists()


def test_frozen_encoder_provenance_description_pair_is_explicit():
    report, task, original, views = case()
    task["record"]["feature"]["input_text"] = "node.code exactly as stored, including serialization if present"
    report["tokenizer"]["input_text"] = "code exactly as supplied; no unquoting or normalization"
    validate(report, task, original, views)
    report["tokenizer"]["input_text"] = "normalized code"
    with pytest.raises(ValueError, match="input text policy"):
        validate(report, task, original, views)
