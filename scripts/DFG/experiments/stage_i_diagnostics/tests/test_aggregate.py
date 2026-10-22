"""Synthetic CPU replay records; no training or Solidity semantics claim."""
import copy
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.DFG.experiments.audit.ddg_diagnostics_v1.diagnostic_common import compare_outputs
from scripts.DFG.experiments.stage_i_diagnostics.aggregate import summarize, CONDITIONS, sha


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf8")


def seal(directory):
    paths = [directory/checkpoint/name for checkpoint in ("best", "last")
             for name in ("scores.json", "predictions.json", "audit.json")]
    dump(directory/"receipt.json", {"status": "passed", "artifact_sha256": {
        str(p.relative_to(directory)): sha(p) for p in paths}})


def fixture(root, task="node"):
    jobs = []
    for fold in (0, 1):
        for variant in ("E3a", "E3b"):
            job = dict(task_id="synthetic_" + task, task=task, cohort="synthetic_author",
                       fold=fold, variant=variant)
            jobs.append(job)
            directory = root/"replays"/job["task_id"]/("fold_"+str(fold))/variant
            for checkpoint in ("best", "last"):
                folder = directory/checkpoint
                folder.mkdir(parents=True)
                truth = [0, 1] if fold == 0 else [0, 1, 1]
                reference = np.array([[2., 0.] if y == 0 else [0., 2.] for y in truth], dtype=np.float32)
                files = ["f%d.sol" % fold] * len(truth) if task == "node" else [
                    "f%d_%d.sol" % (fold, i) for i in range(len(truth))]
                rows = [dict(job, checkpoint=checkpoint, score_role="cv_validation",
                             file=f, original_graph_node_id=i if task == "node" else None,
                             source_sha256=hashlib.sha256(f.encode()).hexdigest(), target=y)
                        for i, (y, f) in enumerate(zip(truth, files))]
                scores = []
                for condition in CONDITIONS:
                    logits = reference.copy()
                    if condition != "N":
                        logits[0] = [0., 2.]
                    score, _, probability = compare_outputs(truth, reference, logits, files)
                    scores.append(dict(condition=condition, **score))
                    for i, row in enumerate(rows):
                        row[condition+"_pred"] = int(logits[i].argmax())
                        row[condition+"_prob"] = probability[i]
                dump(folder/"predictions.json", rows)
                dump(folder/"scores.json", scores)
                dump(folder/"audit.json", {"gates": {"normal_exact": True, "unchanged": True}})
            seal(directory)
    return jobs


def directory(root, jobs, index=0):
    j = jobs[index]
    return root/"replays"/j["task_id"]/("fold_"+str(j["fold"]))/j["variant"]


@pytest.mark.parametrize("task", ["node", "contract"])
def test_complete_identity_bound_recalculation_and_idempotent_output(tmp_path, task):
    jobs = fixture(tmp_path, task)
    report = summarize(tmp_path, jobs)
    assert report["status"] == "complete"
    assert report["jobs"] == 4 and report["checkpoint_replays"] == 8
    assert len(report["fold_statistics"]) == 2*2*6
    assert len(report["pooled_oof"]) == 2*2*6
    assert report["changed_prediction_rows"] == 4*2*5
    with (tmp_path/"changed_predictions.csv").open() as handle:
        changed = list(csv.DictReader(handle))
    assert len(changed) == 40 and all(r["status"] == "introduced" for r in changed)
    mean = next(r for r in report["fold_statistics"] if r["variant"]=="E3a" and
                r["checkpoint"]=="best" and r["condition"]=="Z_D")
    pooled = next(r for r in report["pooled_oof"] if r["variant"]=="E3a" and
                  r["checkpoint"]=="best" and r["condition"]=="Z_D")
    assert mean["buggy_f1_mean"] == pytest.approx((100*2/3 + 80)/2)
    assert pooled["buggy_f1"] == pytest.approx(75)
    assert mean["buggy_f1_mean"] != pooled["buggy_f1"]
    assert mean["buggy_f1_declined_folds"] == 2
    assert mean["delta_buggy_f1_pp_mean"] < 0
    original = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.iterdir() if p.is_file()}
    assert summarize(tmp_path, jobs) == report
    assert original == {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.iterdir() if p.is_file()}


def test_missing_and_duplicate_expected_jobs_rejected(tmp_path):
    jobs = fixture(tmp_path)
    with pytest.raises(ValueError, match="Duplicate expected"):
        summarize(tmp_path, jobs + [jobs[0]])
    with pytest.raises(ValueError, match="unexpected replay"):
        summarize(tmp_path, jobs[:-1])
    directory(tmp_path,jobs)/"receipt.json"
    (directory(tmp_path,jobs)/"receipt.json").unlink()
    with pytest.raises(ValueError, match="Missing"):
        summarize(tmp_path, jobs)


def test_artifact_hash_failure_rejected(tmp_path):
    jobs = fixture(tmp_path)
    path = directory(tmp_path,jobs)/"best/predictions.json"
    path.write_text(path.read_text()+" ")
    with pytest.raises(ValueError, match="SHA mismatch"):
        summarize(tmp_path,jobs)


@pytest.mark.parametrize("change,expected", [
    ("duplicate", "Duplicate prediction identity"),
    ("task", "Mixed prediction identity"),
    ("cohort", "Mixed prediction identity"),
    ("checkpoint", "Mixed checkpoint"),
    ("score_role", "Mixed scoring role"),
    ("source", "Mixed source SHA"),
    ("target", "Changed source/target"),
    ("probability", "Nonfinite/out-of-range"),
    ("population", "populations differ"),
])
def test_bad_prediction_identity_rejected_even_with_new_receipt(tmp_path, change, expected):
    jobs = fixture(tmp_path)
    d = directory(tmp_path,jobs,index=1)
    path = d/"best/predictions.json"
    rows = json.loads(path.read_text())
    if change == "duplicate": rows.append(copy.deepcopy(rows[0]))
    elif change == "task": rows[0]["task_id"] = "other"
    elif change == "cohort": rows[0]["cohort"] = "other"
    elif change == "checkpoint": rows[0]["checkpoint"] = "last"
    elif change == "score_role": rows[0]["score_role"] = "independent_test"
    elif change == "source": rows[0]["source_sha256"] = "0"*64
    elif change == "target": rows[0]["target"] = 1
    elif change == "probability": rows[0]["N_prob"] = float("nan")
    elif change == "population": rows.pop()
    dump(path, rows); seal(d)
    with pytest.raises(ValueError, match=expected):
        summarize(tmp_path,jobs)


def test_file_validation_overlap_rejected(tmp_path):
    jobs = fixture(tmp_path)
    d = directory(tmp_path,jobs,index=2)
    path = d/"best/predictions.json"
    rows = json.loads(path.read_text())
    for row in rows:
        row["file"] = "f0.sol"
        row["source_sha256"] = hashlib.sha256(b"f0.sol").hexdigest()
    dump(path, rows); seal(d)
    with pytest.raises(ValueError, match="multiple validation folds"):
        summarize(tmp_path,jobs)


@pytest.mark.parametrize("change,expected", [("metric", "score mismatch"),
        ("confusion", "Confusion matrix"), ("conditions", "duplicate intervention"),
        ("audit", "Failed replay audit"), ("receipt", "passed receipt")])
def test_invalid_scores_audit_or_receipt_rejected(tmp_path, change, expected):
    jobs = fixture(tmp_path)
    d = directory(tmp_path,jobs)
    if change == "audit":
        dump(d/"best/audit.json", {"gates":{"normal_exact":False}})
    elif change != "receipt":
        p = d/"best/scores.json"; rows = json.loads(p.read_text())
        if change == "metric": rows[0]["buggy_f1"] = 99
        elif change == "confusion": rows[0]["tn_fp_fn_tp"] = [0,0,0,0]
        elif change == "conditions": rows.append(rows[0])
        dump(p, rows)
    seal(d)
    if change == "receipt":
        p=d/"receipt.json"; r=json.loads(p.read_text()); r["status"]="failed"; dump(p,r)
    with pytest.raises(ValueError, match=expected):
        summarize(tmp_path,jobs)


def test_inconsistent_existing_summary_never_overwritten(tmp_path):
    jobs = fixture(tmp_path)
    summarize(tmp_path,jobs)
    path = tmp_path/"REPORT_DATA.json"
    path.write_text("original externally changed bytes")
    with pytest.raises(FileExistsError, match="inconsistent existing"):
        summarize(tmp_path,jobs)
    assert path.read_text() == "original externally changed bytes"


def test_noop_diagnostics_keep_header_and_zero_change_statistics(tmp_path):
    jobs = fixture(tmp_path)
    for j in jobs:
        d=tmp_path/"replays"/j["task_id"]/("fold_"+str(j["fold"]))/j["variant"]
        for checkpoint in ("best", "last"):
            p=d/checkpoint/"predictions.json"
            rows=json.loads(p.read_text())
            for row in rows:
                for condition in CONDITIONS:
                    row[condition+"_pred"]=row["N_pred"]
                    row[condition+"_prob"]=row["N_prob"]
            dump(p,rows)
            p=d/checkpoint/"scores.json"
            base=next(r for r in json.loads(p.read_text()) if r["condition"]=="N")
            dump(p,[dict(base,condition=c) for c in CONDITIONS])
        seal(d)
    report=summarize(tmp_path,jobs)
    assert report["changed_prediction_rows"]==0
    with (tmp_path/"changed_predictions.csv").open() as handle:
        reader=csv.DictReader(handle)
        assert reader.fieldnames and "original_graph_node_id" in reader.fieldnames
        assert list(reader)==[]
    assert all(r["prediction_flips"]==0 for r in report["pooled_oof"])


def test_archive_probability_exactness_is_descriptive_with_frozen_tolerance(tmp_path):
    jobs=fixture(tmp_path)
    d=directory(tmp_path,jobs)
    p=d/"best/audit.json"
    audit=json.loads(p.read_text())
    audit["gates"]["archive_replay"]={"predictions_exact":True,"metrics_match":True,
        "probability_exact":False,"probability_abs_max":1e-7}
    dump(p,audit);seal(d)
    assert summarize(tmp_path,jobs)["status"]=="complete"
    audit["gates"]["archive_replay"]["probability_abs_max"]=0.1
    dump(p,audit);seal(d)
    with pytest.raises(ValueError,match="archive probability difference"):
        summarize(tmp_path,jobs)
