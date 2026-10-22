import copy
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1]/"join_prediction_context.py"
SPEC = importlib.util.spec_from_file_location("stage_i_join_context_postprocess", PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def row():
    r = {"file": "same.sol", "original_graph_node_id": 2, "node_type": "stmt",
         "target": 1, "task_id": "reentrancy_author_node", "task": "node",
         "cohort": "reentrancy_author", "fold": 0, "variant": "E3b",
         "checkpoint": "best", "score_role": M.ROLE, "source_sha256": "shaA",
         "N_pred": 0, "N_prob": .4}
    for condition in M.CONDITIONS:
        r[condition+"_pred"] = 0
        r[condition+"_prob"] = .4
    return r


def context():
    r = row()
    return {"file": r["file"], "original_graph_node_id": "2", "node_type": "stmt",
            "target": "1", "task_id": r["task_id"], "cohort": r["cohort"],
            "fold": "0", "source_sha256": "shaA", "contrast": "E3b-E2",
            "potential_influence_within_two": "True", "new_upstream_count_two": "0"}


def job():
    return {k: row()[k] for k in ("task_id", "task", "cohort", "fold", "variant")}


def test_requires_all_60_jobs_and_all_receipts(tmp_path):
    jobs = [{"task_id": t, "fold": f, "variant": v}
            for t in M.TASKS for f in range(5 if t.endswith("_contract") else 10)
            for v in ("E3a", "E3b")]
    receipts = [tmp_path/"replays"/j["task_id"]/("fold_"+str(j["fold"]))/j["variant"]/"receipt.json"
                for j in jobs]
    M.require_matrix(jobs, receipts, tmp_path)
    with pytest.raises(ValueError):
        M.require_matrix(jobs, receipts[:-1], tmp_path)
    with pytest.raises(ValueError):
        M.require_matrix(jobs[:-1], receipts, tmp_path)
    with pytest.raises(ValueError):
        M.require_matrix(jobs, receipts+[tmp_path/"unexpected/receipt.json"], tmp_path)


@pytest.mark.parametrize("field,value", [("cohort", "other"), ("source_sha256", "shaB"),
    ("original_graph_node_id", 3), ("target", 0), ("node_type", "other"), ("fold", 1),
    ("checkpoint", "last"), ("score_role", "independent_test")])
def test_same_name_does_not_bypass_source_node_or_protocol_identity(field, value):
    r = row()
    M.validate_prediction(r, job(), "best", context())
    r[field] = value
    with pytest.raises(ValueError):
        M.validate_prediction(r, job(), "best", context())


def test_threshold_and_class_changes_are_separate():
    r = row()
    r["Z_D_prob"] = .4 + 1e-9
    result = M.intervention(r, context(), "Z_D")
    assert not result["probability_changed"] and not result["class_changed"]
    r["Z_D_prob"] = .6
    r["Z_D_pred"] = 1
    result = M.intervention(r, context(), "Z_D")
    assert result["corrected"] and result["class_changed"] and result["probability_changed"]
    assert result["potential_scope"] and not result["new_context_scope"]


def test_outside_scope_is_recorded_without_causal_claim():
    r = row()
    r["Z_ALL_prob"] = .6
    r["Z_ALL_pred"] = 1
    c = dict(context(), potential_influence_within_two="False")
    result = M.intervention(r, c, "Z_ALL")
    assert result["class_changed_outside_potential"]
    assert result["probability_changed_outside_potential"]
    stats = M.summarize_group([result])
    assert stats["potential_scope_outside_nodes"] == 1
    assert stats["potential_scope_outside_class_changed"] == 1


def test_contract_has_no_node_scope_claim():
    r = dict(row(), task="contract")
    r["Z_ALL_prob"] = .7
    r["Z_ALL_pred"] = 1
    result = M.intervention(r, context(), "Z_ALL")
    assert result["potential_scope"] is None
    assert not result["class_changed_outside_potential"]
    stats = M.summarize_group([result])
    assert stats["local_scope_applicable"] == 0
    assert stats["potential_scope_inside_nodes"] == stats["potential_scope_outside_nodes"] == 0
    assert stats["corrected"] == 1


def test_static_duplicate_identity_rejected():
    c = context()
    assert len(M.static_index([c])) == 1
    with pytest.raises(ValueError):
        M.static_index([c, copy.deepcopy(c)])


def test_output_is_never_overwritten(tmp_path):
    with pytest.raises(FileExistsError):
        M.process(tmp_path/"no-plan", tmp_path)


def test_csv_no_overwrite(tmp_path):
    p = tmp_path/"file.csv"
    M.write_csv(p, [{"n": 1}])
    with pytest.raises(FileExistsError):
        M.write_csv(p, [{"n": 2}])
