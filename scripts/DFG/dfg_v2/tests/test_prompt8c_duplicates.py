"""Focused regressions for Prompt 8C F; synthetic sources, no fitting."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.DFG.dfg_v2.diagnostics8c import duplicates as d


def row(name, text, category="r", outer=0, task="r_node"):
    return {
        "category": category, "cohort": category + "_author", "file": name,
        "source_sha256": hashlib.sha256(text.encode("utf8")).hexdigest(),
        "text": text, "path": "/sources/" + category + "/" + name,
        "task_outer_folds": {task: outer},
    }


def fold(fold_id, train, val, test):
    return {"fold": fold_id, "inner_train_files": train,
            "inner_val_files": val, "outer_test_files": test}


def test_comments_do_not_erase_quoted_comment_tokens():
    text = 'string x="https://host/*keep*/"; // remove\nstring y=\'//keep\'; /* gone */ uint z;'
    norm = d.without_whitespace(d.without_comments(text))
    assert norm == 'stringx="https://host/*keep*/";stringy=\'//keep\';uintz;'


def test_escaped_quote_preserves_literal_slashes():
    text = 'string x="quote\\\"//keep"; /* remove */ uint z;'
    norm = d.without_whitespace(d.without_comments(text))
    assert '//keep' in norm
    assert "remove" not in norm


def test_unicode_whitespace_normalization_is_explicit():
    assert d.without_whitespace("a\t b\n\r\u2003c") == "abc"
    assert d.without_whitespace('"a b"') == '"ab"'


def test_exact_and_comment_only_near_are_distinct():
    records = [row("a.sol", "contract A{}"), row("b.sol", "contract A { }", outer=1),
               row("c.sol", "contract /* comment */ A{}", outer=2)]
    result = d.audit_records(records, {"r_node": [
        fold(0, ["b.sol"], ["c.sol"], ["a.sol"]),
        fold(1, ["c.sol"], ["a.sol"], ["b.sol"]),
        fold(2, ["a.sol"], ["b.sol"], ["c.sol"]),
    ]})
    assert result["summary"]["exact_pairs"] == 1
    assert result["summary"]["near_pairs"] == 3
    assert result["summary"]["tasks"]["r_node"]["exact"]["cross_outer_fold_pairs"] == 1
    assert result["summary"]["tasks"]["r_node"]["near"]["outer_test_files_with_inner_train_cluster_peer"] == 3


def test_equal_filename_different_category_is_not_identity():
    records = [row("buggy_18.sol", "contract A{}", "r"),
               row("buggy_18.sol", "contract A{}", "ac", task="ac_node")]
    result = d.audit_records(records, {"r_node": [fold(0, [], [], ["buggy_18.sol"])],
                                      "ac_node": [fold(0, [], [], ["buggy_18.sol"])]})
    assert len({r["source_id"] for r in result["sources"]}) == 2
    assert result["summary"]["exact_pairs"] == 1
    assert result["summary"]["tasks"]["r_node"]["exact"]["pairs"] == 0


def test_pair_order_and_components_deterministic():
    records = [row("z.sol", "contract A{}"), row("a.sol", "contract A{}")]
    assert d.audit_records(records, {}) == d.audit_records(list(reversed(records)), {})
    groups = d._components(["a", "b", "c", "d"],
                           [{"left": "a", "right": "b"}, {"left": "b", "right": "c"}])
    assert groups == [["a", "b", "c"]]


def test_nonclique_component_never_claims_all_pairs():
    records = [dict(row(x, "contract A{}"), source_id=x) for x in ("a", "b", "c")]
    pairs = [{"left": "a", "right": "b"}, {"left": "b", "right": "c"}]
    clusters = d._cluster_rows("near", records, pairs, {})
    assert len(clusters) == 1
    assert not clusters[0]["is_all_pairs_clique"]


def test_default_autojunk_is_explicit_and_preserved(monkeypatch):
    seen = []
    actual = d.difflib.SequenceMatcher
    def spy(*args, **kwargs):
        seen.append(kwargs["autojunk"])
        return actual(*args, **kwargs)
    monkeypatch.setattr(d.difflib, "SequenceMatcher", spy)
    a = "contract A { uint a;" + "uint x;" * 50 + "}"
    b = "contract A { uint b;" + "uint x;" * 50 + "}"
    d.audit_records([row("a", a), row("b", b)], {})
    assert seen == [True]


def test_duplicate_identity_rejected():
    r = row("a", "contract A{}")
    with pytest.raises(ValueError, match="Repeated source"):
        d.audit_records([r, copy.deepcopy(r)], {})


@pytest.mark.parametrize("text", ["", "   ", "/* only comment */"])
def test_empty_or_comment_only_source_rejected(text):
    with pytest.raises(ValueError):
        d.audit_records([row("a", text)], {})


def write_json(path, document):
    path.write_text(json.dumps(document), encoding="utf8")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def synthetic_plan(tmp_path):
    names = ["a.sol", "b.sol"]
    sources = {}
    for name in names:
        path = tmp_path / name
        path.write_text("contract A{}", encoding="utf8")
        sources[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    splits = [fold(0, ["b.sol"], [], ["a.sol"]), fold(1, ["a.sol"], [], ["b.sol"])]
    task_ref = write_json(tmp_path / "oldtask.json", {"task_id": "r_author_node", "cohort": "r_author"})
    fold_ref = write_json(tmp_path / "folds.json", {"files": names, "folds": splits, "k_folds": 2})
    record = {"task_id": "r_node", "source_task_id": "r_author_node", "category": "r",
              "task": "node", "graph_files": names, "sources": sources, "missing_sources": [],
              "folds": fold_ref, "original_graph": {"path": "unused", "sha256": "unused"},
              "provenance": {"source_task_manifest": task_ref, "source_metadata_manifest": task_ref}}
    prep = {}
    for split in splits:
        prep["%s/1" % split["fold"]] = write_json(
            tmp_path / ("task%s.json" % split["fold"]),
            {"task_id": "r_node", "fold": split["fold"], "seed": 1, "split": split})
    inputs = write_json(tmp_path / "inputs.json", {"tasks": {"r_node": record}})
    path = tmp_path / "plan.json"
    ref = write_json(path, {"input_manifest": inputs, "seeds": [1],
                           "tasks": {"r_node": {"record": record, "prepared": prep}}})
    write_json(tmp_path / "plan.seal.json", {"plan_sha256": ref["sha256"]})
    return path


def test_manifest_bound_loading_and_exclusive_outputs(tmp_path):
    plan = synthetic_plan(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    report = d.run(plan, tmp_path / "F")
    assert report["summary"]["exact_pairs"] == 1
    assert report["training_executed"] is False
    assert report["current_folds_changed"] is False
    assert report["config"]["autojunk"] is True
    assert all(path.read_bytes() == data for path, data in before.items())
    with pytest.raises(FileExistsError):
        d.run(plan, tmp_path / "F")


def test_changed_raw_source_is_rejected(tmp_path):
    plan = synthetic_plan(tmp_path)
    (tmp_path / "a.sol").write_text("contract Changed{}", encoding="utf8")
    with pytest.raises(ValueError, match="SHA mismatch"):
        d.load_inputs(plan)


def test_changed_plan_seal_is_rejected(tmp_path):
    plan = synthetic_plan(tmp_path)
    plan.write_text(plan.read_text() + "\n", encoding="utf8")
    with pytest.raises(ValueError, match="seal"):
        d.load_inputs(plan)


def test_prepared_split_mismatch_rejected_even_if_rehashed(tmp_path):
    plan = synthetic_plan(tmp_path)
    document = json.loads(plan.read_text())
    prepared_path = tmp_path / "task0.json"
    prepared = json.loads(prepared_path.read_text())
    prepared["split"]["outer_test_files"] = ["b.sol"]
    document["tasks"]["r_node"]["prepared"]["0/1"] = write_json(prepared_path, prepared)
    ref = write_json(plan, document)
    write_json(tmp_path / "plan.seal.json", {"plan_sha256": ref["sha256"]})
    with pytest.raises(ValueError, match="Prepared"):
        d.load_inputs(plan)
