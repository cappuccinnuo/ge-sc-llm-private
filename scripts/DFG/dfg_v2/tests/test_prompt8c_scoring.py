"""Independent formula, role, identity and sensitivity checks for Prompt 8C B."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.DFG.dfg_v2.diagnostics8c import scoring as s


def pred(filename, node, target, best):
    return dict(file=filename, original_graph_node_id=node, node_type="expression_statement",
                target=target, best=best, score_role="outer_test")


def view(row, fold, sha="abc", c1=None, include=True):
    return dict(file=row["file"], original_graph_node_id=row["original_graph_node_id"],
                node_id=row["original_graph_node_id"], node_type=row["node_type"],
                orig=row["target"], C1=row["target"] if c1 is None else c1,
                C2=row["target"] if c1 is None else c1, C2_include=include,
                lexical_prediction=int(row["file"].startswith("buggy_")),
                solidifi=row["file"].startswith("buggy_"), fold=fold, source_sha256=sha)


def small_inputs():
    a, b = pred("buggy_1.sol", 0, 0, 1), pred("real.sol", 1, 1, 0)
    profiles = {"G0": {0: [a], 1: [b]},
                "G2R": {0: [copy.deepcopy(a)], 1: [dict(b, best=1)]}}
    views = {s.identity(a): view(a, 0, c1=1),
             s.identity(b): view(b, 1)}
    task = dict(record=dict(task="node", graph_files=["buggy_1.sol", "real.sol"],
                            sources={"buggy_1.sol": {"sha256": "abc"},
                                     "real.sol": {"sha256": "abc"}}), folds=[0, 1])
    return task, profiles, views


def test_metrics_independently_match_hand_counts():
    metrics = s.metric_counts(s.confusion([(0, 0), (0, 1), (1, 0), (1, 1)]))
    assert metrics["tn_fp_fn_tp"] == [1, 1, 1, 1]
    assert all(metrics[k] == 50 for k in s.SCORE_NAMES)
    only_positive = s.metric_counts(s.confusion([(1, 1)]))
    assert only_positive["macro_f1"] == 50  # frozen labels=[0,1]
    assert only_positive["buggy_f1"] == 100


def test_empty_stratum_not_fabricated_zero_score():
    m = s.metric_counts(s.confusion([]))
    assert m["n"] == 0
    assert all(m[k] is None for k in s.SCORE_NAMES)
    assert s.wilson(0, 0) is None


def test_wilson_zero_hits_has_nonzero_upper_bound():
    lo, hi = s.wilson(0, 20)
    assert lo == pytest.approx(0)
    assert hi == pytest.approx(16.11251580528194)
    assert s.wilson(10, 10)[1] == pytest.approx(100)


def test_C1_changes_only_diagnostic_targets_and_C2_excludes():
    task, profiles, views = small_inputs()
    before = copy.deepcopy((profiles, views))
    scores = s.summarize_task("r_node", "node", profiles, views)
    def pooled(profile, view, stratum="all"):
        return next(row for row in scores["pooled_metrics"]
                    if row["profile"] == profile and row["view"] == view and row["stratum"] == stratum)
    assert pooled("G0", "orig")["fp"] == 1
    assert pooled("G0", "orig")["fn"] == 1
    assert pooled("G0", "C1")["tp"] == 1
    assert pooled("G0", "C1")["fp"] == 0
    assert (profiles, views) == before
    views[("buggy_1.sol", 0)]["C2_include"] = False
    newer = s.summarize_task("r_node", "node", profiles, views)
    empty = next(row for row in newer["fold_means"]
                 if row["profile"] == "G0" and row["view"] == "C2" and row["stratum"] == "all")
    assert empty["empty_fold_ids"] == [0]
    assert empty["expected_folds"] == 2


def test_non_solidifi_has_only_pooled_intervals_not_fold_means():
    _, profiles, views = small_inputs()
    scores = s.summarize_task("r_node", "node", profiles, views)
    for table in ("fold_metrics", "fold_means", "paired", "paired_folds"):
        assert all(row["stratum"] != "nonSolidiFI" for row in scores[table])
    pooled = [row for row in scores["pooled_metrics"] if row["stratum"] == "nonSolidiFI"]
    assert len(pooled) == 9
    assert all("recall_wilson_95" in row for row in pooled)
    assert all(row["n"] == 1 for row in pooled)


def test_lexical_baseline_same_nodes_views_and_strata():
    _, profiles, views = small_inputs()
    scores = s.summarize_task("r_node", "node", profiles, views)
    lexical = [r for r in scores["pooled_metrics"] if r["profile"] == s.LEXICAL]
    assert len(lexical) == 9
    c1 = next(row for row in lexical if row["view"] == "C1" and row["stratum"] == "all")
    assert (c1["tp"], c1["fp"], c1["fn"]) == (1, 0, 1)


def test_paired_difference_and_ties_are_fold_aligned():
    _, profiles, views = small_inputs()
    scores = s.summarize_task("r_node", "node", profiles, views)
    pair = next(row for row in scores["paired"]
                if row["profile"] == "G2R" and row["view"] == "orig"
                and row["stratum"] == "all" and row["metric"] == "buggy_f1")
    assert pair["mean"] == 50
    assert (pair["improved"], pair["tied"], pair["declined"]) == (1, 1, 0)
    assert pair["test_performed"] is False


def test_contract_has_orig_only_and_no_invented_lexical_rule():
    a = dict(pred("a.sol", None, 1, 1), node_type=None)
    tables = s.summarize_task("r_contract", "contract", {"G0": {0: [a]}}, None)
    assert {r["view"] for r in tables["pooled_metrics"]} == {"orig"}
    assert {r["profile"] for r in tables["pooled_metrics"]} == {"G0"}


def test_node_identity_not_prediction_row_order():
    task, profiles, views = small_inputs()
    s.validate_task_predictions(task, profiles, views)
    profiles["G2R"][1][0]["original_graph_node_id"] = 99
    with pytest.raises(ValueError, match="identities"):
        s.validate_task_predictions(task, profiles, views)


@pytest.mark.parametrize("change", ["source", "fold", "target", "exclude_flip", "duplicate"])
def test_invalid_label_views_rejected(change):
    task, profiles, views = small_inputs()
    raw = list(copy.deepcopy(views).values())
    if change == "source":
        raw[0]["source_sha256"] = "wrong"
    elif change == "fold":
        raw[0]["fold"] = 9
    elif change == "target":
        raw[0]["orig"] = 2
    elif change == "exclude_flip":
        raw[0]["C2"] = 0
    else:
        raw.append(copy.deepcopy(raw[0]))
    with pytest.raises(ValueError):
        s.validate_views("r_node", task, raw)


def test_mixed_fold_assignment_rejected():
    task, profiles, views = small_inputs()
    profiles["G2R"][0], profiles["G2R"][1] = profiles["G2R"][1], profiles["G2R"][0]
    with pytest.raises(ValueError, match="fold"):
        s.validate_task_predictions(task, profiles, views)


def write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf8")
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def fixture(tmp_path):
    task, profiles, views = small_inputs()
    for name in task["record"]["graph_files"]:
        source = tmp_path / name
        source.write_text("contract A{}", encoding="utf8")
        source_ref = s.ref(source)
        task["record"]["sources"][name] = source_ref
        for v in views.values():
            if v["file"] == name:
                v["source_sha256"] = source_ref["sha256"]
    jobs, verification = [], []
    for profile, folds in profiles.items():
        for fold, rows in folds.items():
            job = dict(task_id="r_node", fold=fold, seed=1, profile=profile)
            jobs.append(job)
            attempt = tmp_path / "runs" / profile / str(fold)
            pp = attempt / "outer_test_predictions.json"
            pred_ref = write_json(pp, rows)
            artifacts = {"outer_test_predictions.json": pred_ref["sha256"]}
            rr = write_json(attempt / "receipt.json", dict(job=job, artifacts=artifacts))
            metrics = s.metric_counts(s.confusion((r["target"], r["best"]) for r in rows))
            verification.append(dict(job=job, attempt=str(attempt), status="verified",
                                     receipt_sha256=rr["sha256"], artifacts=artifacts,
                                     outer_test={"best": metrics}))
    plan = tmp_path / "plan.json"
    plan_ref = write_json(plan, dict(tasks={"r_node": task}, jobs=jobs, profiles=list(profiles)))
    write_json(tmp_path / "plan.seal.json", {"plan_sha256": plan_ref["sha256"]})
    vp = tmp_path / "verification.json"
    write_json(vp, dict(plan_sha256=plan_ref["sha256"], verified=len(jobs), fits=verification))
    views_path = tmp_path / "A/node_views.json"
    view_ref = write_json(views_path, {"r_node": list(views.values())})
    write_json(views_path.parent / "audit.json", dict(node_views=view_ref,
                                                    provenance={"plan": plan_ref}))
    return plan, views_path, vp


def test_complete_runner_reads_only_and_refuses_overwrite(tmp_path):
    plan, views, verification = fixture(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = s.run_scoring(plan, views, verification, tmp_path / "B")
    assert len(result["original_metric_checks"]) == 4
    assert result["training_count"] == result["model_forward_count"] == 0
    assert result["Holm_performed"] is False
    assert all(path.read_bytes() == data for path, data in before.items())
    with pytest.raises(FileExistsError):
        s.run_scoring(plan, views, verification, tmp_path / "B")


def test_modified_verified_prediction_refused(tmp_path):
    plan, views, verification = fixture(tmp_path)
    pred_path = tmp_path / "runs/G0/0/outer_test_predictions.json"
    pred_path.write_text(pred_path.read_text() + "\n", encoding="utf8")
    with pytest.raises(ValueError, match="predictions changed"):
        s.run_scoring(plan, views, verification, tmp_path / "B")


def test_missing_verification_refused(tmp_path):
    plan, views, verification = fixture(tmp_path)
    doc = json.loads(verification.read_text())
    doc["fits"].pop()
    write_json(verification, doc)
    with pytest.raises(ValueError, match="Missing verified"):
        s.run_scoring(plan, views, verification, tmp_path / "B")
