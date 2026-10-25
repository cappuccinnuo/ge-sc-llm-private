"""Prompt 5 frozen registration/inputs; synthetic tests do not train."""
import copy
from pathlib import Path

import pytest
import torch

from scripts.DFG.integration.io import read_json, sha256, write_json
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.dfg_v2 import tasks
from scripts.DFG.dfg_v2.inputs import build_manifest, load_manifest, load_task
from scripts.DFG.dfg_v2.tests.task_fixtures import (
    synthetic_registry, SyntheticEncoder, reference)


def revise(ref, edit):
    data = read_json(ref["path"])
    edit(data)
    write_json(ref["path"], data)
    ref["sha256"] = sha256(ref["path"])


def test_public_selection_and_registry_are_not_mutated(tmp_path):
    registry = synthetic_registry(tmp_path, "new_category")
    before = copy.deepcopy(registry)
    selected = tasks.get_tasks(["new_category"], registry)
    assert list(selected) == ["new_category_contract", "new_category_node"]
    assert selected["new_category_node"]["source_task_id"] == "new_category_fixture_node"
    assert list(tasks.get_tasks("new_category_node", registry)) == ["new_category_node"]
    assert registry == before
    for names in (["missing"], ["new_category", "new_category_node"], []):
        with pytest.raises(ValueError):
            tasks.get_tasks(names, registry)


def test_twenty_identity_category_complete_registration_fold_graph_model_chain(tmp_path):
    from scripts.DFG.dfg_v2.pipeline import build
    from scripts.DFG.dfg_v2.model import make_model
    registry = synthetic_registry(tmp_path, "renamed_fixture")
    documents = tasks.make_folds("renamed_fixture", registry)
    assert {doc["k_folds"] for doc in documents.values()} == {5, 10}
    assert len(documents["renamed_fixture_contract"]["files"]) == 20
    assert len(documents["renamed_fixture_node"]["files"]) == 10
    assert set(documents["renamed_fixture_node"]["file_labels"].values()) == {1}
    manifest = build_manifest(tmp_path / "inputs", registry=registry)
    doc = load_manifest(manifest)
    torch.set_num_threads(2)
    for tid, row in doc["tasks"].items():
        base, sources, metadata = load_task(row)
        old = fingerprint(base)
        graph, audit = build(base, sources, metadata, ("L1", "L2", "L3"),
                             token_encoder=SyntheticEncoder())
        assert fingerprint(base) == old
        assert set(sources) == set(documents[tid]["files"])
        assert {"DATA_DEF_USE", "WRITES_STATE", "READS_STATE", "ENV_FLOW"}.issubset(
            {d["edge_type"] for _,_,d in graph.edges(data=True)})
        model = make_model(row["task"], graph, "G3R", device="cpu",
                           hidden_size=16, layers=1, heads=2)
        model.eval()
        with torch.no_grad():
            output = model() if row["task"] == "node" else model(row["graph_files"])[0]
        assert torch.isfinite(output).all()
        assert output.shape[-1] == 2
        assert all(p.grad is None for p in model.parameters())


@pytest.mark.parametrize("category", ["reentrancy", "access_control"])
def test_real_nested_folds_recreate_complete_frozen_document(category):
    ref = tasks.REGISTRY[category]["tasks"]["contract"]["source_task_manifest"]
    if not Path(ref["path"]).exists():
        pytest.skip("Frozen local Dataset A artifacts are not installed")
    results = tasks.make_folds(category)
    for tid, row in tasks.get_tasks([category]).items():
        assert results[tid] == read_json(row["folds"]["path"])


@pytest.mark.parametrize("field", [
    "source_task_manifest", "source_metadata_manifest", "labels", "folds", "prepared_manifest"])
def test_registered_reference_sha_tamper_rejected(tmp_path, field):
    registry = synthetic_registry(tmp_path)
    ref = registry["synthetic"]["tasks"]["contract"][field]
    Path(ref["path"]).write_bytes(Path(ref["path"]).read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA256"):
        tasks.get_tasks(["synthetic_contract"], registry)


@pytest.mark.parametrize("field,value", [
    ("task", "node"), ("task_id", "other"), ("cohort", "other")])
def test_task_identity_mismatch_rejected_even_with_new_file_hash(tmp_path, field, value):
    registry = synthetic_registry(tmp_path)
    ref = registry["synthetic"]["tasks"]["contract"]["source_task_manifest"]
    revise(ref, lambda doc: doc.update({field: value}))
    with pytest.raises(ValueError, match="identity"):
        tasks.get_tasks(["synthetic_contract"], registry)


def test_fold_cannot_reference_different_prepared_manifest(tmp_path):
    registry = synthetic_registry(tmp_path)
    row = registry["synthetic"]["tasks"]["contract"]
    from scripts.DFG.experiments.protocol import make_fold_document
    fold = read_json(row["folds"]["path"])
    wrong = make_fold_document(fold["file_labels"], "contract", "a" * 64)
    write_json(row["folds"]["path"], wrong)
    row["folds"] = reference(row["folds"]["path"])
    with pytest.raises(ValueError, match="protocol"):
        tasks.get_tasks(["synthetic_contract"], registry)


@pytest.mark.parametrize("bad", ["duplicate", "boolean", "nonbinary"])
def test_label_identity_and_values_rejected(tmp_path, bad):
    registry = synthetic_registry(tmp_path)
    ref = registry["synthetic"]["tasks"]["contract"]["labels"]
    doc = read_json(ref["path"])
    if bad == "duplicate":
        doc.append(dict(doc[0]))
    else:
        doc[0]["targets"] = True if bad == "boolean" else 2
    write_json(ref["path"], doc)
    ref["sha256"] = sha256(ref["path"])
    with pytest.raises(ValueError):
        tasks.read_labels(ref)


def test_missing_source_record_is_explicit_and_original_graph_kept(tmp_path):
    registry = synthetic_registry(tmp_path)
    record = registry["synthetic"]["tasks"]["contract"]
    revise(record["source_metadata_manifest"], lambda doc: doc["sources"].pop("case_00.sol"))
    manifest = build_manifest(tmp_path/"inputs", ["synthetic_contract"], registry)
    row = load_manifest(manifest)["tasks"]["synthetic_contract"]
    graph, sources, metadata = load_task(row)
    assert row["missing_sources"] == ["case_00.sol"]
    assert "case_00.sol" not in sources
    assert "case_00.sol" in {d["source_file"] for _, d in graph.nodes(data=True)}
    assert len(graph) == row["original_graph"]["nodes"]


@pytest.mark.parametrize("field", ["source", "original_graph", "asset", "labels", "folds"])
def test_manifest_referenced_asset_tamper_rejected(tmp_path, field):
    registry = synthetic_registry(tmp_path)
    path = build_manifest(tmp_path/"inputs", ["synthetic_contract"], registry)
    doc = load_manifest(path)
    row = doc["tasks"]["synthetic_contract"]
    target = (next(iter(row["sources"].values()))["path"] if field == "source"
              else next(iter(row["feature"]["asset_hashes"])) if field == "asset"
              else row[field]["path"])
    target = Path(target)
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError):
        load_manifest(path)
    # Deliberate binding-only read remains sealed but does not claim asset verification.
    assert load_manifest(path, check_files=False)["tasks"] == doc["tasks"]
    with pytest.raises(ValueError):
        load_task(row)


def test_bound_metadata_csv_tamper_rejected_before_binding_fallback(tmp_path):
    registry = synthetic_registry(tmp_path)
    record = registry["synthetic"]["tasks"]["contract"]
    source_doc = read_json(record["source_metadata_manifest"]["path"])
    ref = source_doc["sources"]["case_00.sol"]
    source = Path(ref["path"])
    csv_path = source.parent.parent/"versions.csv"
    csv_path.write_text("file,compiled version\nsource/case_00.sol,0.5.0\n", encoding="utf8")
    ref["metadata"] = dict(csv_path=str(csv_path), csv_sha256=sha256(csv_path),
        source_path=str(source), source_sha256=ref["sha256"],
        row_file="source/case_00.sol", version="0.5.0")
    write_json(record["source_metadata_manifest"]["path"], source_doc)
    record["source_metadata_manifest"]["sha256"] = sha256(record["source_metadata_manifest"]["path"])
    path = build_manifest(tmp_path/"inputs", ["synthetic_contract"], registry)
    csv_path.write_text("file,compiled version\nsource/case_00.sol,0.4.25\n", encoding="utf8")
    with pytest.raises(ValueError, match="SHA256"):
        load_manifest(path)


@pytest.mark.parametrize("target", ["manifest", "seal"])
def test_manifest_and_seal_tamper_rejected_even_with_checks_disabled(tmp_path, target):
    registry = synthetic_registry(tmp_path)
    path = build_manifest(tmp_path/"inputs", ["synthetic_node"], registry)
    if target == "manifest":
        path.write_bytes(path.read_bytes() + b" ")
    else:
        seal = path.with_name("manifest.seal.json")
        data = read_json(seal)
        data["task_ids"] = ["wrong"]
        write_json(seal, data)
    with pytest.raises(ValueError):
        load_manifest(path, check_files=False)


def test_manifest_preserves_feature_exactly_and_refuses_overwrite(tmp_path):
    registry = synthetic_registry(tmp_path)
    path = build_manifest(tmp_path/"inputs", ["synthetic_contract"], registry)
    row = load_manifest(path)["tasks"]["synthetic_contract"]
    source = read_json(row["provenance"]["source_task_manifest"]["path"])
    assert row["feature"] == source["feature"]
    assert row["original_graph"] == source["graphs"]["HCG"]
    assert row["provenance"]["source_metadata_manifest"] == registry["synthetic"]["tasks"]["contract"]["source_metadata_manifest"]
    with pytest.raises(FileExistsError):
        build_manifest(path.parent, registry=registry)


@pytest.mark.parametrize("flag", ["training_executed", "labels_used_for_analysis"])
def test_resealed_manifest_cannot_claim_analysis_used_labels_or_training(tmp_path, flag):
    registry = synthetic_registry(tmp_path)
    path = build_manifest(tmp_path/"inputs", ["synthetic_node"], registry)
    doc = read_json(path)
    doc[flag] = True
    write_json(path, doc)
    seal = path.with_name("manifest.seal.json")
    old = read_json(seal)
    old["sha256"] = sha256(path)
    write_json(seal, old)
    with pytest.raises(ValueError):
        load_manifest(path, check_files=False)


def test_resealed_label_version_mismatch_rejected(tmp_path):
    registry = synthetic_registry(tmp_path)
    path = build_manifest(tmp_path/"inputs", ["synthetic_node"], registry)
    doc = load_manifest(path)
    row = doc["tasks"]["synthetic_node"]
    row["label_version"] = "another_label_scheme"
    with pytest.raises(ValueError, match="label provenance"):
        load_task(row)


def test_node_task_rejects_clean_file_even_when_graph_reference_is_valid(tmp_path):
    registry = synthetic_registry(tmp_path)
    records = registry["synthetic"]["tasks"]
    contract_graph = read_json(records["contract"]["source_task_manifest"]["path"])["graphs"]["HCG"]
    revise(records["node"]["source_task_manifest"],
           lambda doc: doc["graphs"].update(HCG=contract_graph))
    with pytest.raises(ValueError, match="non-buggy"):
        build_manifest(tmp_path/"inputs", ["synthetic_node"], registry)


def test_metadata_nonexact_recorded_version_is_rejected(tmp_path):
    from scripts.DFG.dfg_v2.inputs import _check_metadata
    registry = synthetic_registry(tmp_path)
    row = registry["synthetic"]["tasks"]["contract"]
    source = next(iter(read_json(row["source_metadata_manifest"]["path"])["sources"].values()))
    source["metadata"] = {"version": "^0.5.0"}
    with pytest.raises(ValueError, match="exact numeric"):
        _check_metadata(source)
