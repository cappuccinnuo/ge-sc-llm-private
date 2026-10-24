"""Acceptance-runner guards and independent legacy identity checks."""
import copy

import networkx as nx
import pytest

from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
from scripts.DFG.dfg_v2.l1 import augment_l1
from scripts.DFG.dfg_v2.l1_build import _unique_tasks, check_legacy, run
from scripts.DFG.integration.io import sha256, write_json
from scripts.DFG.integration.pipeline import build_graph


def test_existing_output_is_never_overwritten(tmp_path):
    output = tmp_path / "old"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("historical")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        run(output, tmp_path / "missing_manifest.json")
    assert sentinel.read_text() == "historical"


@pytest.mark.parametrize("records", [
    [], [{"task_id": "a"}, {"task_id": "a"}],
    [{"task_id": "../bad"}], [{"task_id": "a/b"}], [{"task_id": "a\\\\b"}],
])
def test_bad_task_matrix_rejected(records):
    with pytest.raises(ValueError):
        _unique_tasks({"tasks": records}, "fixture")


def test_bad_reference_sha_rejected_before_output(tmp_path):
    manifest = tmp_path / "manifest.json"
    write_json(manifest, {"tasks": [{"task_id": "arbitrary_contract"}]})
    write_json(tmp_path / "manifest.seal.json", {"sha256": "0" * 64})
    with pytest.raises(ValueError, match="SHA256"):
        run(tmp_path / "out", manifest, tmp_path / "unused.json")
    assert not (tmp_path / "out").exists()


def test_p0_task_matrix_cannot_be_silently_changed(tmp_path):
    manifest = tmp_path / "manifest.json"
    baseline = tmp_path / "baseline.json"
    write_json(manifest, {"tasks": [{"task_id": "arbitrary_contract"}]})
    write_json(tmp_path / "manifest.seal.json", {"sha256": sha256(manifest)})
    write_json(baseline, {"tasks": [{"task_id": "different_contract"}]})
    with pytest.raises(ValueError, match="Task matrix differs"):
        run(tmp_path / "out", manifest, baseline)
    assert not (tmp_path / "out").exists()


def test_legacy_acceptance_includes_zero_fact_success_and_rejects_changed_fact():
    # Tree-sitter parser fixture only; compiler validation is not claimed.
    source = """pragma solidity ^0.5.0;
contract C {
 function empty() public {}
 function old(uint x) public returns(uint) { uint y = x; return y; }
 function fresh(string memory s, uint n) public returns(uint) { uint k = n; return k; }
}"""
    graph = nx.MultiDiGraph(generate_cfg_from_source(source, "sample.sol"))
    sources = {"sample.sol": source}
    old_graph, old_audit = build_graph(graph, sources, profile="scalar")
    new_graph, audit = augment_l1(graph, sources)
    report = check_legacy(graph, old_graph, old_audit, new_graph, audit, sources, {})
    assert report["legacy_supported"] == 2
    assert report["solver_equal_functions"] == 2
    assert len(report["legacy_zero_projected_fact_functions"]) == 1
    assert report["projectors_by_ast_equal_files"] == 1
    changed = copy.deepcopy(audit)
    ev = next(e for e in changed["evidence"] if e["analysis_path"] == "legacy")
    ev["definition"] += "-changed"
    with pytest.raises(AssertionError, match="Legacy projected facts differ"):
        check_legacy(graph, old_graph, old_audit, new_graph, changed, sources, {})
