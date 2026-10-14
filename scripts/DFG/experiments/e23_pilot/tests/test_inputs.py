"""Frozen four-task CPU input checks plus small, isolated validation negatives.

Real graphs use the project's existing RestrictedReader allowlist through load_task;
there is no raw pickle.load, model construction, CUDA execution or graph regeneration.
"""
import copy
import gc
from collections import Counter
from pathlib import Path
import networkx as nx
import numpy as np
import pytest
from scripts.DFG.experiments.common import read_json, sha256
from scripts.DFG.experiments.e23_pilot import inputs


@pytest.mark.parametrize("task_id,expected_files", [
    ("reentrancy_author_contract", 142), ("access_control_author_contract", 114),
    ("reentrancy_author_node", 71), ("access_control_author_node", 57)])
def test_real_frozen_four_tasks_match_prepared_initialization(task_id, expected_files):
    """Load once per task, compare all variants, release before the next task."""
    path = inputs.DEFAULT_OUTPUT / "initialization" / task_id / "task_manifest.json"
    assert path.is_file(), "Stage G prepare must complete before this acceptance check"
    prepared = read_json(path)
    info, graphs, labels = inputs.load_task(task_id)
    try:
        # These are stable input/protocol facts, not another model fit or initialization.
        for key in ("config", "source_config_sha256", "source_prepared_manifest_sha256",
                    "source_splits_sha256", "split", "labels_sha256", "feature",
                    "label_version", "graphs", "invariants", "frozen_files"):
            assert info[key] == prepared[key], key
        assert info["fold"] == 0
        assert info["config"]["protocol"] == "paper_kfold"
        assert info["config"]["score_role"] == "cv_validation"
        assert info["config"]["forward_scope"] == "complete_fixed_task_graph"
        assert info["config"]["seed"] == 1 and info["config"]["schedule_epochs"] == 50
        assert info["config"]["patience"] == 7 and info["config"]["delta"] == 0.001
        baseline = graphs["E2"]
        population = {d["source_file"] for _, d in baseline.nodes(data=True)}
        assert len(population) == expected_files
        assert all(labels[f] in (0, 1) for f in population)
        train, val = set(info["split"]["train_files"]), set(info["split"]["val_files"])
        assert train and val and not train & val and train | val == population
        node_types = {d["node_type"] for _, d in baseline.nodes(data=True)}
        for variant, graph in graphs.items():
            assert list(graph) == list(baseline)
            assert {d["node_type"] for _, d in graph.nodes(data=True)} == node_types
            assert {d["source_file"] for _, d in graph.nodes(data=True)} == population
            assert all(graph.nodes[u]["source_file"] == graph.nodes[v]["source_file"]
                       for u, v in graph.edges())
            counts = Counter(d["edge_type"] for _, _, d in graph.edges(data=True))
            expected = (0, 0, 0) if variant == "E2" else (inputs.EXPECTED[task_id][0], 0, 0) if variant == "E3a" else inputs.EXPECTED[task_id]
            assert tuple(counts[k] for k in inputs.RELATIONS) == expected
            assert inputs.sha256(info["graphs"][variant]["path"]) == info["graphs"][variant]["sha256"]
        assert len({info["graphs"][v]["node_attributes_sha256"] for v in graphs}) == 1
    finally:
        del graphs
        gc.collect()


def test_check_hashes_rejects_actual_file_drift(tmp_path):
    p = tmp_path / "frozen.txt"
    p.write_text("original\n")
    records = {str(p): sha256(p)}
    inputs.check_hashes(records)
    p.write_text("changed\n")
    with pytest.raises(ValueError, match="Frozen input drift"):
        inputs.check_hashes(records)


def test_unknown_task_rejected_before_any_io(monkeypatch):
    def forbidden(*args):
        raise AssertionError("Unknown task must not read input files")
    monkeypatch.setattr(inputs, "read_json", forbidden)
    with pytest.raises(ValueError, match="frozen four pilot tasks"):
        inputs.load_task("reentrancy_author_contract_fold1")


@pytest.fixture
def small_task(monkeypatch):
    """Mock metadata I/O only; exercise actual post-load invariants on four nodes.

    validate_document is intentionally stubbed here: the unmodified, signed real
    paper protocol documents are validated in all four real acceptance cases above.
    """
    task_id = "reentrancy_author_contract"
    prep = Path("/synthetic/prepared")
    splits_path = "/synthetic/split.json"
    config_path = inputs.OLD_RUN / "jobs" / (task_id + "_fold0") / "attempt_001/effective_config.json"
    original_config = read_json(config_path)
    config = copy.deepcopy(original_config)
    config.update(prepared_manifest_sha256="bound", split_manifest_sha256="bound")
    split = {"fold": 0, "train_files": ["a.sol"], "val_files": ["b.sol"]}
    labels = [{"contract_name": "a.sol", "targets": 0}, {"contract_name": "b.sol", "targets": 1}]
    manifest = {"graph_labels": {"path": "labels.json", "sha256": "bound"},
                "sources": {}, "feature": {"asset_hashes": {}}, "label_version": "fixture_only"}
    documents = {
        str(inputs.OLD_RUN / "plan.json"): {"seed": 1, "epochs": 50, "frozen_files": {},
            "jobs": [{"id": task_id + "_fold0", "task": "contract", "cohort": "reentrancy_author", "prepared": str(prep), "splits": splits_path}]},
        str(inputs.OLD_RUN / "plan.seal.json"): {"sha256": "bound"},
        str(prep / "manifest.json"): manifest,
        splits_path: {"prepared_manifest_sha256": "bound", "seed": 1, "k_folds": 5,
                      "files": ["a.sol", "b.sol"], "file_labels": {"a.sol": 0, "b.sol": 1}, "folds": [split]},
        str(config_path): config, str(prep / "labels.json"): labels,
        str(inputs.ROOT / "scripts/DFG/experiments/audit/ddg_v11_correctness/D1_PROVENANCE.json"):
            {"graphs": {task_id: {"path": "/synthetic/E2.gpickle", "sha256": "bound"}}},
        str(inputs.STAGE_F / "F3_attempt_002/GRAPH_MANIFEST.json"):
            [{"cohort": "reentrancy_author", "task": "contract", "variant": v,
              "path": "/synthetic/" + v + ".gpickle", "sha256": "bound"} for v in ("E3a", "E3b")],
    }
    g = nx.MultiDiGraph()
    for n, file in enumerate(("a.sol", "a.sol", "b.sol", "b.sol")):
        g.add_node(n, node_type="statement", source_file=file,
                   token=np.arange(512, dtype=np.float32), node_source_code_lines=[n + 1],
                   node_info_vulnerabilities=None)
    g.add_edge(0, 1, edge_type="next")
    g.add_edge(2, 3, edge_type="next")
    graphs = {v: copy.deepcopy(g) for v in inputs.VARIANTS}
    for v in ("E3a", "E3b"):
        graphs[v].add_edge(0, 1, edge_type="STATE_DEF_USE")
    graphs["E3b"].add_edge(0, 1, edge_type="STATE_ACCESS_ORDER")
    graphs["E3b"].add_edge(2, 3, edge_type="EXTERNAL_CALL_BEFORE_STATE_WRITE")
    monkeypatch.setattr(inputs, "read_json", lambda p: documents[str(p)])
    monkeypatch.setattr(inputs, "sha256", lambda p: "bound")
    monkeypatch.setattr(inputs, "validate_document", lambda doc: None)
    monkeypatch.setattr(inputs, "read_graph", lambda p: graphs[Path(p).stem])
    monkeypatch.setitem(inputs.EXPECTED, task_id, (1, 1, 1))
    return task_id, documents, graphs, split, labels


def test_small_mock_accepts_valid_parallel_relations(small_task):
    task_id, _, _, _, _ = small_task
    info, graphs, _ = inputs.load_task(task_id)
    assert graphs["E3b"].number_of_edges(0, 1) == 3
    assert info["invariants"]["E3b"]["base_preserved"]


@pytest.mark.parametrize("change,error", [
    ("seal", "Old plan seal mismatch"), ("split_digest", "Old prepared/split mismatch"),
    ("label_digest", "Label SHA mismatch"), ("duplicate_label", "Invalid labels"),
    ("label_population", "Population or label mismatch"), ("split_overlap", "Supervision partition mismatch"),
    ("graph_digest", "Candidate graph SHA mismatch"), ("variant_node_type", "Variant node/label/feature/order mismatch"),
    ("variant_label", "Variant node/label/feature/order mismatch"), ("feature_shape", "Frozen tokenizer feature mismatch"),
    ("cross_file", "Cross-file"), ("missing_variant", "Missing candidate variant"),
    ("relation_count", "Candidate relation inventory differs")])
def test_small_mock_rejects_metadata_schema_and_supervision_drift(small_task, change, error):
    task_id, docs, graphs, split, labels = small_task
    if change == "seal":
        docs[str(inputs.OLD_RUN / "plan.seal.json")]["sha256"] = "wrong"
    elif change == "split_digest":
        docs["/synthetic/split.json"]["prepared_manifest_sha256"] = "wrong"
    elif change == "label_digest":
        docs["/synthetic/prepared/manifest.json"]["graph_labels"]["sha256"] = "wrong"
    elif change == "duplicate_label":
        labels.append(dict(labels[0]))
    elif change == "label_population":
        docs["/synthetic/split.json"]["file_labels"]["b.sol"] = 0
    elif change == "split_overlap":
        split["val_files"].append("a.sol")
    elif change == "graph_digest":
        docs[str(inputs.ROOT / "scripts/DFG/experiments/audit/ddg_v11_correctness/D1_PROVENANCE.json")]["graphs"][task_id]["sha256"] = "wrong"
    elif change == "variant_node_type":
        graphs["E3a"].nodes[0]["node_type"] = "unregistered_type"
    elif change == "variant_label":
        graphs["E3a"].nodes[0]["node_info_vulnerabilities"] = [{"category": "changed"}]
    elif change == "feature_shape":
        for graph in graphs.values():
            graph.nodes[0]["token"] = np.zeros(511, dtype=np.float32)
    elif change == "cross_file":
        graphs["E3b"].add_edge(0, 2, edge_type="STATE_ACCESS_ORDER")
    elif change == "missing_variant":
        docs[str(inputs.STAGE_F / "F3_attempt_002/GRAPH_MANIFEST.json")].pop()
    elif change == "relation_count":
        graphs["E3b"].add_edge(1, 0, edge_type="STATE_ACCESS_ORDER")
    with pytest.raises(ValueError, match=error):
        inputs.load_task(task_id)
