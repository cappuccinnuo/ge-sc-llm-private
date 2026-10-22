import copy
import json
from pathlib import Path

import networkx as nx
import pytest

from scripts.DFG.experiments.stage_i_diagnostics import evidence as e


def graph():
    g = nx.MultiDiGraph()
    for n in range(5):
        g.add_node(n, node_type="stmt", source_file="a.sol", token=[float(n)],
                   node_info_vulnerabilities=None)
    return g


def test_exact_adapter_keeps_state_forward_and_reflects_cfg():
    g = graph()
    g.add_edge(0, 1, edge_type="next")
    g.add_edge(1, 2, edge_type="STATE_DEF_USE")
    saved = copy.deepcopy(g)
    adj, pred, _ = e.model_adjacency(g)
    assert 1 in adj[0] and 0 in adj[1]
    assert 2 in adj[1] and 1 not in adj[2]
    assert nx.utils.graphs_equal(saved, g)
    assert 1 in pred[2]


def test_two_hop_opportunity_is_directional_and_not_transitive_closure():
    base = graph()
    base.add_edge(1, 2, edge_type="DATA_DEF_USE")
    base.add_edge(2, 3, edge_type="DATA_DEF_USE")
    aug = copy.deepcopy(base)
    aug.add_edge(0, 1, edge_type="STATE_ACCESS_ORDER")
    rows, edges, _ = e.context_features(base, aug)
    assert rows[1]["direct_added_relation_target"]
    assert rows[2]["potential_influence_within_two"]
    assert rows[2]["new_upstream_count_two"] == 1
    assert not rows[3]["potential_influence_within_two"]
    assert rows[3]["new_upstream_count_two"] == 0
    assert not rows[0]["potential_influence_within_two"]
    assert not edges[0]["baseline_reachable_within_two"]


def test_existing_reachability_is_not_reported_as_new_context():
    base = graph()
    base.add_edge(0, 1, edge_type="DATA_DEF_USE")
    aug = copy.deepcopy(base)
    aug.add_edge(0, 1, edge_type="STATE_DEF_USE")
    rows, edges, schema = e.context_features(base, aug)
    assert rows[1]["potential_influence_within_two"]
    assert rows[1]["new_upstream_count_two"] == 0
    assert rows[1]["context_class"] == "added_relation_but_no_new_upstream_context"
    assert edges[0]["baseline_reachable_within_two"]
    assert ("stmt", "STATE_DEF_USE", "stmt") in schema


def test_schema_exposure_is_distinct_from_local_edge_scope():
    base = graph()
    base.add_edge(3, 4, edge_type="next")
    aug = copy.deepcopy(base)
    aug.add_edge(0, 1, edge_type="STATE_DEF_USE")
    rows, _, _ = e.context_features(base, aug)
    assert rows[4]["schema_destination_type_exposed"]
    assert not rows[4]["potential_influence_within_two"]
    assert rows[4]["context_class"] == "outside_added_edge_two_hop_scope"


@pytest.mark.parametrize("mutation", ["node", "remove", "relation", "cross_file"])
def test_changed_graph_contract_is_rejected(mutation):
    base = graph()
    base.add_edge(0, 1, edge_type="next")
    aug = copy.deepcopy(base)
    if mutation == "node":
        aug.add_node(5, node_type="stmt", source_file="a.sol")
    elif mutation == "remove":
        aug.remove_edge(0, 1)
    elif mutation == "relation":
        aug.add_edge(1, 2, edge_type="UNAPPROVED")
    else:
        base.nodes[2]["source_file"] = "b.sol"
        aug.nodes[2]["source_file"] = "b.sol"
        aug.add_edge(1, 2, edge_type="STATE_DEF_USE")
    with pytest.raises(ValueError):
        e.context_features(base, aug)


def test_comparison_classifies_corrected_regressed_and_probability_only():
    a = {"target": 1, "source_sha256": "a", "best": 0,
         "best_positive_probability": .4, "fold": 0}
    b = dict(a, best=1, best_positive_probability=.6)
    assert e.compare_prediction(a, b)["status"] == "corrected"
    assert e.compare_prediction(b, a)["status"] == "regressed"
    b = dict(a, best_positive_probability=.45)
    result = e.compare_prediction(a, b)
    assert result["status"] == "both_wrong"
    assert result["probability_changed"] and not result["prediction_changed"]
    with pytest.raises(ValueError):
        e.compare_prediction(a, dict(b, source_sha256="other-source"))


def test_same_filename_and_original_id_still_require_cohort_source_binding(tmp_path, monkeypatch):
    import scripts.DFG.experiments.paper_protocol as pp
    monkeypatch.setattr(pp, "validate_document", lambda d: None)
    splits = tmp_path/"splits.json"
    splits.write_text(json.dumps({"folds": [{"fold": 0, "val_files": ["a.sol"]}]}))
    info = {"task": "node", "task_id": "task", "cohort": "cohort",
            "source_splits_path": str(splits)}
    g = graph()
    sources = {"a.sol": {"sha256": "sourceA"}}
    rows = [{"file": "a.sol", "original_graph_node_id": n, "model_node_id": n,
             "node_type": "stmt", "target": 0, "task_id": "task", "cohort": "cohort",
             "source_sha256": "sourceA", "score_role": "cv_validation", "fold": 0}
            for n in g]
    assert len(e.validate_predictions(rows[::-1], info, g, sources, {})) == 5
    for field, bad in (("cohort", "other"), ("source_sha256", "sourceB"),
                       ("model_node_id", 99), ("target", 1), ("fold", 1),
                       ("score_role", "independent_test")):
        corrupt = copy.deepcopy(rows)
        corrupt[0][field] = bad
        with pytest.raises(ValueError):
            e.validate_predictions(corrupt, info, g, sources, {})
    with pytest.raises(ValueError):
        e.validate_predictions(rows + [rows[0]], info, g, sources, {})
    with pytest.raises(ValueError):
        e.validate_predictions(rows[:-1], info, g, sources, {})


def test_compact_source_anchor_preserves_byte_identity_not_nearest_line():
    proof = {"source_sha256": "sha", "function": "a.sol:0", "certainty": "EXACT",
             "definition": {"anchor": {"file": "a.sol", "start": 2, "end": 3,
                                         "role": "emit_statement"}, "kind": "READ", "id": "d"},
             "use": {"anchor": {"file": "a.sol", "start": 4, "end": 5,
                                  "role": "expression_statement"}, "kind": "WRITE", "id": "u"}}
    compact = e.compact_evidence(proof, {"a.sol": {"sha256": "sha"}},
                                {"a.sol": b"a\nb\nc\n"})
    assert compact["source_anchor"]["source_start_line"] == 2
    assert compact["source_anchor"]["start_byte"] == 2
    assert compact["target_anchor"]["source_start_line"] == 3
    assert "source_node" not in compact
    with pytest.raises(ValueError):
        e.compact_evidence(proof, {"a.sol": {"sha256": "other"}}, {"a.sol": b"a\nb\nc\n"})


def test_refuse_existing_output_before_reading_inputs(tmp_path):
    with pytest.raises(FileExistsError):
        e.produce_evidence(tmp_path/"not-real-h2", tmp_path)


def test_sha_drift_rejected_and_csv_no_overwrite(tmp_path):
    path = tmp_path/"sample"
    path.write_text("a")
    recorded = {}
    e.checked(path, e.sha(path), recorded)
    path.write_text("b")
    with pytest.raises(ValueError):
        e.checked(path, recorded[str(path)], {})
    target = tmp_path/"out.csv"
    e.write_csv(target, [{"id": 1}])
    with pytest.raises(FileExistsError):
        e.write_csv(target, [{"id": 2}])


def test_projection_blank_fields_are_unknown_not_zero():
    row = {"missing_anchors": "", "eligible_relations": "", "file_projection_fallback": "unsupported"}
    assert e.audit_missing(row) == []
    assert e.audit_count(row, "eligible_relations") is None
    assert e.audit_count({"eligible_relations": "0"}, "eligible_relations") == 0
