"""Unit tests for the dfg package: vocabulary, inputs, one-contract pipeline, CLI."""
import csv
import hashlib

import numpy as np
import pytest

from dfg import schema
from dfg.__main__ import main as cli
from dfg.graph.audit import fingerprint
from dfg.graph.pipeline import iter_build, profiles_for_key
from dfg.graph.projection import code_equal
from dfg.inputs import REPO, has_tokens, version_records
from dfg.store import canonical_counts, coverage
from hcg.cfg.author_schema import quote

CONTRACT = "0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol"   # reentrancy, recorded 0.4.19
CORPUS = REPO / "experiments/ge-sc-data/source_code/reentrancy/source_files"


def fake_encoder(text):
    vec = np.zeros(512, dtype=np.float32)
    vec[:32] = np.frombuffer(hashlib.sha256(text.encode("utf8")).digest(), dtype=np.uint8)
    return vec


def test_profiles_are_cumulative_and_reverse_needs_forward():
    p = schema.PROFILES
    assert p["G0"] == frozenset()
    assert p["G1R"] < p["G2R"] < p["G3R"]
    assert p["G3"] == schema.FORWARD_RELATIONS
    assert schema.has_reverse("G3R", schema.ENV_FLOW) and not schema.has_reverse("G3", schema.ENV_FLOW)
    with pytest.raises(ValueError):
        schema.forward_relations("G9")


def test_code_equal_uses_hcg_quoting():
    source = 'require(msg.sender == "a\\nb");\nx = 1;'
    assert code_equal(quote(source), source)
    assert code_equal(source, source)
    assert not code_equal(quote(source + " "), source)


def _versions(tmp_path, body):
    root = tmp_path / "smartbug-dataset"
    (root / "dataset/reentrancy").mkdir(parents=True)
    with open(root / "versions.csv", "w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["file", "compiled version"])
        writer.writerow(["dataset/reentrancy/" + CONTRACT, "0.4.19"])
    (root / "dataset/reentrancy" / CONTRACT).write_bytes(body)
    return tmp_path


def test_version_record_requires_byte_identical_copy(tmp_path):
    original = (CORPUS / CONTRACT).read_bytes()
    records = version_records("A", "reentrancy", [CONTRACT, "missing.sol"], _versions(tmp_path, original))
    assert set(records) == {CONTRACT}
    assert records[CONTRACT]["version"] == "0.4.19"
    assert records[CONTRACT]["row_file"] == "dataset/reentrancy/" + CONTRACT
    other = tmp_path / "other"
    assert version_records("A", "reentrancy", [CONTRACT], _versions(other, original + b"\n")) == {}


def test_version_records_need_fetched_sources(tmp_path):
    with pytest.raises(FileNotFoundError):
        version_records("A", "reentrancy", [CONTRACT], tmp_path)


@pytest.fixture(scope="module")
def one_contract():
    from hcg.cfg.builder import build_corpus
    graph, failures = build_corpus([CORPUS / CONTRACT])
    assert not failures
    for _, data in graph.nodes(data=True):
        data["token"] = np.zeros(512, dtype=np.float32)
    return graph, {CONTRACT: (CORPUS / CONTRACT).read_bytes().decode("utf8")}


def test_pipeline_adds_every_layer_without_touching_the_hcg(one_contract):
    graph, sources = one_contract
    before = fingerprint(graph)
    outputs = {key: (g, audit) for key, g, audit in
               iter_build(graph, sources, {CONTRACT: None}, ("L1", "L2", "L3"), token_encoder=fake_encoder)}
    assert list(outputs) == ["F0", "F1", "F2", "F3"]
    assert fingerprint(graph) == before
    kinds = {k: {d["edge_type"] for _, _, d in g.edges(data=True)} for k, (g, _) in outputs.items()}
    assert schema.DATA_DEF_USE in kinds["F1"]
    assert {schema.WRITES_STATE, schema.READS_STATE} <= kinds["F2"]
    assert schema.ENV_FLOW in kinds["F3"]
    f3 = outputs["F3"][0]
    env = [d for _, d in f3.nodes(data=True) if d["node_type"] == schema.ENV_SOURCE]
    assert env and all(d["token"].shape == (512,) for d in env)
    assert coverage(outputs["F3"][1])["L1"] == dict(files=1, file_fallbacks=0)
    for key, (g, _) in outputs.items():
        for profile in profiles_for_key(key):
            counts = canonical_counts(g, profile)
            reverse = [c for c in counts if c.split("|")[1].startswith("REV_")]
            assert bool(reverse) == profile.endswith("R")


def test_has_tokens(one_contract):
    graph, _ = one_contract
    assert has_tokens(graph)
    bare = graph.copy()
    for _, data in bare.nodes(data=True):
        data.pop("token")
    assert not has_tokens(bare)


def test_cli_rejects_unknown_category_and_gaps_in_layers():
    with pytest.raises(SystemExit, match="unknown categories"):
        cli(["build", "--categories", "nope"])
    with pytest.raises(SystemExit, match="cumulative"):
        cli(["build", "--layers", "L1", "L3"])


def test_edgesem_pins_the_current_hgt_layer():
    """EdgeSem subclasses dfg.model.hgt; a changed parent layer must be a deliberate update."""
    hgt_edge = pytest.importorskip("scripts.edge_sem.hgt_edge", reason="EdgeSem not checked out")
    hgt_edge.verify_frozen_sources()


def test_legacy_names_are_the_moved_modules():
    """scripts.DFG.<old> resolves to the dfg module itself (one object, own spec)."""
    import importlib
    import scripts.DFG as legacy
    for old, new in legacy.MOVED.items():
        module = importlib.import_module("scripts.DFG." + old)
        assert module is importlib.import_module(new)
        assert module.__spec__.name == new
    from scripts.DFG.dfg_v2 import PROFILES
    assert PROFILES is schema.PROFILES
