import copy
import pytest
from scripts.DFG.experiments.protocol import make_fold_document, validate_fold_document
from scripts.DFG.experiments.paper_protocol import (
    convert_document, validate_document, document_hash, protocol_output, ROOT,
    initialize_pair, INITIALIZATION_VERSION)
from scripts.DFG.experiments.tests.test_protocol import labels, models


@pytest.mark.parametrize("task,k", [("node", 10), ("contract", 5)])
def test_exact_union_conversion_preserves_original(task, k):
    old = make_fold_document(labels(task), task, "a"*64)
    original = copy.deepcopy(old)
    doc = convert_document(old, "b"*64)
    assert old == original
    assert validate_fold_document(old) is old
    assert validate_document(doc) is doc
    assert len(doc["folds"]) == k
    assert doc["score_role"] == "cv_validation"
    vals = []
    for before, after in zip(old["folds"], doc["folds"]):
        assert after["train_files"] == sorted(before["inner_train_files"] + before["inner_val_files"])
        assert after["val_files"] == before["outer_test_files"]
        assert not set(after["train_files"]) & set(after["val_files"])
        vals += after["val_files"]
    assert sorted(vals) == doc["files"]


@pytest.mark.parametrize("key,value", [("score_role", "outer_test"), ("protocol_version", "ddg-nested-paired-v1"),
                                      ("forward_scope", "isolated_file_subgraphs")])
def test_role_or_scope_misnaming_rejected_even_rehashed(key, value):
    d = convert_document(make_fold_document(labels("node"), "node", "a"*64))
    d[key] = value
    d["split_sha256"] = document_hash(d)
    with pytest.raises(ValueError):
        validate_document(d)


def test_new_partition_cannot_be_substituted_even_if_exhaustive():
    d = convert_document(make_fold_document(labels("node"), "node", "a"*64))
    fold = d["folds"][0]
    fold["train_files"][0], fold["val_files"][0] = fold["val_files"][0], fold["train_files"][0]
    fold["train_files"].sort(); fold["val_files"].sort()
    d["split_sha256"] = document_hash(d)
    with pytest.raises(ValueError, match="exact"):
        validate_document(d)


def test_output_must_be_protocol_separated():
    good = ROOT / "artifacts/paper_kfold/test_nonexistent_directory/path"
    assert protocol_output(good) == good
    for p in (ROOT/"artifacts/20261012_v1/new", ROOT/"artifacts/nested_strict/new"):
        with pytest.raises(ValueError, match="paper_kfold"):
            protocol_output(p)


def test_initialization_version_is_separate_from_experiment_protocol():
    a, b = models()
    result = initialize_pair(a, b, 19)
    assert result["initialization_version"] == INITIALIZATION_VERSION
    assert "protocol_version" not in result
    assert len(result["initializer_source_sha256"]) == 64
