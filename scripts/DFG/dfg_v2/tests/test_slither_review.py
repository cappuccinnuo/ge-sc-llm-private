import copy
import json
from pathlib import Path

import pytest

from scripts.DFG.dfg_v2.slither_review import (
    prepare, sample_other, sha256, validate,
)


def row(i, task="R", layer="L1", direction="FP"):
    return dict(difference_id="%s-%s-%s-%04d" % (task, layer, direction, i),
                task=task, layer=layer, direction=direction, category="other")


def test_fixed_seed_all_small_and_thirty_large_groups():
    rows = [row(i) for i in range(55)] + [row(i, task="A") for i in range(4)]
    selected, strata = sample_other(rows)
    assert len(selected) == 34
    assert [s["selected"] for s in strata] == [4, 30]
    assert sample_other(list(reversed(rows))) == (selected, strata)
    assert selected == sample_other(rows)[0]
    assert selected != sample_other(rows, seed=1)[0]
    assert all(x["category"] == "other" for x in selected)


def test_non_other_not_sampled_and_duplicates_rejected():
    normal = row(0)
    excluded = dict(row(1), category="entry_initialization")
    assert sample_other([normal, excluded])[0] == [normal]
    with pytest.raises(ValueError, match="Duplicate"):
        sample_other([normal, normal])


def bundle(tmp_path):
    source = tmp_path / "c.sol"
    source.write_text("contract C { uint x; }\n")
    event = dict(row(1), source_path=str(source), source_sha256=sha256(source))
    alignment = tmp_path / "alignment.json"
    alignment.write_text(json.dumps(dict(differences=[event])))
    result = prepare(alignment, tmp_path / "review")
    selection = tmp_path / "review/selection.json"
    decisions = tmp_path / "decisions.json"
    content = dict(selection_sha256=sha256(selection), decisions=[
        dict(difference_id=event["difference_id"], verdict="unclear", reason="No verified counterpart.",
             evidence=dict(inspected_source=source.read_text()))])
    decisions.write_text(json.dumps(content))
    return selection, decisions, content, source, alignment


def test_valid_explicit_review_and_no_automatic_verdict(tmp_path):
    selection, decisions, _, _, _ = bundle(tmp_path)
    assert json.loads(selection.read_text())["verdicts_assigned"] is False
    result = validate(selection, decisions)
    assert result["reviewed"] == 1
    assert result["counts"][0]["verdict"] == "unclear"
    assert result["semantic_verdicts_are_analyst_supplied"] is True
    assert result["prompt7_gate"] == "no_sampled_v2_defect"


@pytest.mark.parametrize("change", ["missing", "duplicate", "unknown_verdict", "empty_reason",
                                   "empty_evidence", "wrong_selection", "defect_no_pattern"])
def test_reject_incomplete_or_unbound_decisions(tmp_path, change):
    selection, decisions, content, _, _ = bundle(tmp_path)
    if change == "missing":
        content["decisions"] = []
    elif change == "duplicate":
        content["decisions"] *= 2
    elif change == "unknown_verdict":
        content["decisions"][0]["verdict"] = "correct"
    elif change == "empty_reason":
        content["decisions"][0]["reason"] = " "
    elif change == "empty_evidence":
        content["decisions"][0]["evidence"] = {}
    elif change == "wrong_selection":
        content["selection_sha256"] = "bad"
    else:
        content["decisions"][0]["verdict"] = "v2_defect"
    decisions.write_text(json.dumps(content))
    with pytest.raises(ValueError):
        validate(selection, decisions)


def test_defect_blocks_gate_and_preserves_pattern(tmp_path):
    selection, decisions, content, _, _ = bundle(tmp_path)
    content["decisions"][0].update(verdict="v2_defect", pattern="synthetic_test_shape")
    decisions.write_text(json.dumps(content))
    result = validate(selection, decisions)
    assert result["prompt7_gate"] == "blocked_v2_defect"
    assert len(result["defect_patterns"]["synthetic_test_shape"]) == 1


@pytest.mark.parametrize("target", ["selection", "source", "alignment"])
def test_reject_changed_bound_input(tmp_path, target):
    selection, decisions, _, source, alignment = bundle(tmp_path)
    paths = dict(selection=selection, source=source, alignment=alignment)
    with paths[target].open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="modified"):
        validate(selection, decisions)


def test_refuse_overwriting_selection(tmp_path):
    selection, _, _, _, alignment = bundle(tmp_path)
    with pytest.raises(FileExistsError):
        prepare(alignment, selection.parent)

def test_comparator_artifact_requires_recompute(tmp_path):
    selection, decisions, content, _, _ = bundle(tmp_path)
    content["decisions"][0].update(verdict="comparator_artifact")
    decisions.write_text(json.dumps(content))
    result = validate(selection, decisions)
    assert result["prompt7_gate"] == "pending_comparator_recompute"
