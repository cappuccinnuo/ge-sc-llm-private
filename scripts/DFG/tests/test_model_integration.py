"""Phase 7: directed DDG integration, without a training step.

Codex 2026-10-12. These tests deliberately use the public graph/model
constructors. Checking only the serialized NetworkX edges would miss the
legacy reflection performed while loading the HGT graph.
"""
from collections import OrderedDict

import networkx as nx
import numpy as np
import pytest
import torch

from sco_models.graph_utils import reflect_graph
from scripts.labeling_v2.safe_graph import write_graph


DDG = "DATA_DEF_USE"


def _edges(source, target):
    return (
        torch.tensor(source, dtype=torch.int64),
        torch.tensor(target, dtype=torch.int64),
    )


def _assert_edge_dict(actual, expected):
    assert list(actual) == list(expected)
    for canonical, pair in expected.items():
        assert len(actual[canonical]) == 2
        for actual_tensor, expected_tensor in zip(actual[canonical], pair):
            assert actual_tensor.dtype == expected_tensor.dtype
            assert actual_tensor.shape == expected_tensor.shape
            assert torch.equal(actual_tensor, expected_tensor)


def test_legacy_reflection_golden_preserves_order_duplicates_and_loops():
    # Hand-written pre-DDG oracle. "next" includes a parallel edge and a
    # self-loop; "branch" is already supplied in both type directions.
    original = OrderedDict([
        (("expression", "next", "expression"), _edges([0, 0, 1], [1, 1, 1])),
        (("expression", "branch", "condition"), _edges([0, 1], [0, 0])),
        (("condition", "branch", "expression"), _edges([0], [1])),
    ])
    untouched = OrderedDict(
        (key, (pair[0].clone(), pair[1].clone()))
        for key, pair in original.items()
    )
    expected = OrderedDict([
        (
            ("expression", "next", "expression"),
            _edges([0, 0, 1, 1, 1, 1], [1, 1, 1, 0, 0, 1]),
        ),
        (
            ("expression", "branch", "condition"),
            _edges([0, 1, 1], [0, 0, 0]),
        ),
        (
            ("condition", "branch", "expression"),
            _edges([0, 0, 0], [0, 1, 1]),
        ),
    ])
    _assert_edge_dict(reflect_graph(original), expected)
    _assert_edge_dict(original, untouched)


def test_empty_reflection_preserves_empty_graph_data():
    assert reflect_graph({}) == {}


@pytest.mark.parametrize("target_type", ["expression", "condition"])
def test_ddg_keeps_exact_forward_edges_for_same_and_different_node_types(target_type):
    key = ("expression", DDG, target_type)
    original = OrderedDict([(key, _edges([0, 1], [2, 2]))])
    result = reflect_graph(original)
    # Even when source and destination types match, no (2, 0)/(2, 1)
    # edges may be created by the loader.
    _assert_edge_dict(result, original)
    assert not any("REV_DATA_DEF_USE" == item[1] for item in result)


def test_existing_opposite_ddg_facts_remain_separate_without_duplication():
    # A real analysis can supply facts in either type direction. Preserving
    # direction does not mean deleting independently supplied opposite facts.
    original = OrderedDict([
        (("expression", DDG, "condition"), _edges([0], [1])),
        (("condition", DDG, "expression"), _edges([2], [3])),
    ])
    _assert_edge_dict(reflect_graph(original), original)


def test_only_exact_ddg_relation_is_special_and_original_relations_still_reflect():
    original = OrderedDict([
        (("expression", "next", "expression"), _edges([0], [1])),
        (("expression", DDG, "expression"), _edges([0], [1])),
        (("expression", "data_def_use", "expression"), _edges([0], [1])),
    ])
    expected = OrderedDict([
        (("expression", "next", "expression"), _edges([0, 1], [1, 0])),
        (("expression", DDG, "expression"), _edges([0], [1])),
        (("expression", "data_def_use", "expression"), _edges([0, 1], [1, 0])),
    ])
    _assert_edge_dict(reflect_graph(original), expected)


def _fixture_graph(use_ddg):
    graph = nx.MultiDiGraph()
    random = np.random.RandomState(20261012)
    # Two disjoint file graphs, one isolated node type, and two DDG sources
    # for the same destination. The latter also permits meaningful attention
    # gradient checks in the later Phase 8 tests.
    for node in range(9):
        filename = "a.sol" if node < 4 else "b.sol"
        node_type = "condition" if node in (3, 7) else "expression"
        if node == 8:
            node_type = "isolated"
        vulnerabilities = (
            [{"category": "reentrancy", "lines": [node + 1]}]
            if node in (2, 3) else None
        )
        graph.add_node(
            node,
            node_type=node_type,
            source_file=filename,
            code="fixture_statement_{}".format(node),
            node_source_code_lines=[node + 1],
            node_info_vulnerabilities=vulnerabilities,
            token=random.normal(size=512).astype(np.float32),
        )
    for offset in (0, 4):
        graph.add_edge(offset, offset + 1, edge_type="next")
        graph.add_edge(offset + 1, offset + 2, edge_type="next")
        graph.add_edge(offset + 2, offset + 3, edge_type="branch")
    # Original parallel and self edges are intentional legacy graph data.
    graph.add_edge(0, 1, edge_type="next")
    graph.add_edge(1, 1, edge_type="next")
    if use_ddg:
        graph.add_edge(0, 2, edge_type=DDG)
        graph.add_edge(1, 2, edge_type=DDG)
        graph.add_edge(2, 3, edge_type=DDG)
    return graph


def _model_class(task):
    from sco_models.model_hgt import HGTVulGraphClassifier, HGTVulNodeClassifier
    return HGTVulNodeClassifier if task == "node" else HGTVulGraphClassifier


def _make_model(task, graph_path):
    return _model_class(task)(
        compressed_global_graph_path=str(graph_path),
        node_feature="inside_token",
        hidden_size=16,
        num_layers=2,
        num_heads=4,
        use_norm=True,
        device="cpu",
    ).to("cpu")


def _dgl_edges(model, canonical):
    return model.symmetrical_global_graph.edges(etype=canonical, order="eid")


def _global_edge_pairs(model, canonical):
    source, target = _dgl_edges(model, canonical)
    source_ids = model.node_ids_dict[canonical[0]]
    target_ids = model.node_ids_dict[canonical[2]]
    return [
        (source_ids[int(left)], target_ids[int(right)])
        for left, right in zip(source.tolist(), target.tolist())
    ]


@pytest.mark.parametrize("task", ["node", "graph"])
def test_both_model_constructors_preserve_forward_ddg_and_all_baseline_data(tmp_path, task):
    baseline_path = tmp_path / "baseline.gpickle"
    enhanced_path = tmp_path / "enhanced.gpickle"
    write_graph(_fixture_graph(False), baseline_path)
    write_graph(_fixture_graph(True), enhanced_path)
    baseline = _make_model(task, baseline_path)
    enhanced = _make_model(task, enhanced_path)

    base_graph = baseline.symmetrical_global_graph
    ddg_graph = enhanced.symmetrical_global_graph
    assert baseline.total_nodes == enhanced.total_nodes == 9
    assert baseline.ntypes_dict == enhanced.ntypes_dict
    assert baseline.node_ids_dict == enhanced.node_ids_dict
    assert list(baseline.nx_graph) == list(enhanced.nx_graph)

    for node in baseline.nx_graph:
        left = baseline.nx_graph.nodes[node]
        right = enhanced.nx_graph.nodes[node]
        assert set(left) == set(right)
        for key in left:
            if key == "token":
                assert left[key].dtype == right[key].dtype == np.dtype("float32")
                np.testing.assert_array_equal(left[key], right[key])
            else:
                assert left[key] == right[key]

    for node_type in base_graph.ntypes:
        assert base_graph.num_nodes(node_type) == ddg_graph.num_nodes(node_type)
        assert torch.equal(
            base_graph.nodes[node_type].data["inp"],
            ddg_graph.nodes[node_type].data["inp"],
        )
    assert ddg_graph.num_nodes("isolated") == 1

    # Original canonical relations and their edge order/multiplicity must
    # survive, even when DDG has the same endpoint pair as an original edge.
    for canonical in base_graph.canonical_etypes:
        assert canonical in enhanced.etypes_dict
        for left, right in zip(_dgl_edges(baseline, canonical), _dgl_edges(enhanced, canonical)):
            assert torch.equal(left, right)

    added = set(ddg_graph.canonical_etypes) - set(base_graph.canonical_etypes)
    assert added == {
        ("expression", DDG, "expression"),
        ("expression", DDG, "condition"),
    }
    assert _global_edge_pairs(enhanced, ("expression", DDG, "expression")) == [(0, 2), (1, 2)]
    assert _global_edge_pairs(enhanced, ("expression", DDG, "condition")) == [(2, 3)]
    assert ("condition", DDG, "expression") not in enhanced.etypes_dict
    assert all(canonical[1] != "REV_DATA_DEF_USE" for canonical in ddg_graph.canonical_etypes)
    assert ddg_graph.num_edges() == base_graph.num_edges() + 3
    assert all(
        enhanced.nx_graph.nodes[left]["source_file"] == "a.sol"
        and enhanced.nx_graph.nodes[right]["source_file"] == "a.sol"
        for canonical in added
        for left, right in _global_edge_pairs(enhanced, canonical)
    )
    if task == "node":
        assert baseline.node_labels == enhanced.node_labels
        assert baseline.labeled_node_ids == enhanced.labeled_node_ids
    else:
        assert baseline.node_ids_by_filename == enhanced.node_ids_by_filename


# Phase 8: real HGT execution and checkpoint recovery on the same frozen graph.
def _forward_logits(model, task):
    if task == "node":
        return model(), None
    return model(["a.sol", "b.sol"])


@pytest.mark.parametrize("task", ["node", "graph"])
def test_forward_backward_ddg_update_and_checkpoint_roundtrip(tmp_path, task):
    from scripts.DFG.model_validation import capture_model_input, assert_model_input
    import json

    torch.manual_seed(1701)
    graph_path = tmp_path / "enhanced.gpickle"
    write_graph(_fixture_graph(True), graph_path)
    model = _make_model(task, graph_path)
    external = {"file_targets": [["a.sol", 1], ["b.sol", 0]], "fold_id": "fixture"}
    expected_input = capture_model_input(model, external_inputs=external)

    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    optimizer.zero_grad()
    logits, pooled = _forward_logits(model, task)
    expected_count = 9 if task == "node" else 2
    assert tuple(logits.shape) == (expected_count, 2)
    assert torch.isfinite(logits).all()
    if task == "graph":
        assert tuple(pooled.shape) == (2, 16)
        assert torch.isfinite(pooled).all()

    targets = torch.tensor(model.node_labels if task == "node" else [1, 0], dtype=torch.long)
    loss = torch.nn.functional.cross_entropy(logits, targets)
    assert torch.isfinite(loss)
    loss.backward()

    ddg_index = model.etypes_dict[("expression", DDG, "expression")]
    message_parameter = model.gcs[0].relation_msg
    assert message_parameter.grad is not None
    assert torch.isfinite(message_parameter.grad).all()
    assert message_parameter.grad[ddg_index].abs().sum().item() > 0
    assert model.classify.weight.grad is not None
    assert torch.isfinite(model.classify.weight.grad).all()
    assert model.classify.weight.grad.abs().sum().item() > 0
    expression_type = model.ntypes_dict["expression"]
    assert model.adapt_ws[expression_type].weight.grad is not None
    assert model.adapt_ws[expression_type].weight.grad.abs().sum().item() > 0
    # Not every attention/prior parameter must have non-zero gradients: a
    # destination with only one same-relation predecessor has softmax == 1.
    before_update = message_parameter.detach()[ddg_index].clone()
    optimizer.step()
    assert not torch.equal(before_update, message_parameter.detach()[ddg_index])
    assert_model_input(model, expected_input, external_inputs=external)

    model.eval()
    with torch.no_grad():
        before_logits, before_pooled = _forward_logits(model, task)
    checkpoint = tmp_path / "model.pt"
    manifest_path = tmp_path / "model.input.json"
    torch.save(model.state_dict(), str(checkpoint))
    manifest_path.write_text(json.dumps(expected_input, sort_keys=True), encoding="utf-8")

    # Different random initialization proves that loading the saved weights,
    # not merely reconstructing a seeded model, reproduces the outputs.
    torch.manual_seed(9182)
    restored = _make_model(task, graph_path)
    restored_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert_model_input(restored, restored_manifest, external_inputs=external)
    restored.load_state_dict(torch.load(str(checkpoint), map_location="cpu"))
    restored.eval()
    with torch.no_grad():
        after_logits, after_pooled = _forward_logits(restored, task)
    assert torch.equal(before_logits, after_logits)
    if task == "graph":
        assert torch.equal(before_pooled, after_pooled)
    assert_model_input(restored, restored_manifest, external_inputs=external)


@pytest.mark.parametrize("change", ["token", "label", "ddg_direction", "source_file"])
def test_input_manifest_rejects_same_schema_input_drift(tmp_path, change):
    from scripts.DFG.model_validation import capture_model_input, assert_model_input

    original_path = tmp_path / "original.gpickle"
    changed_path = tmp_path / "changed.gpickle"
    graph = _fixture_graph(True)
    write_graph(graph, original_path)
    expected = capture_model_input(_make_model("node", original_path))

    if change == "token":
        graph.nodes[0]["token"][0] += np.float32(1)
    elif change == "label":
        graph.nodes[2]["node_info_vulnerabilities"] = None
    elif change == "ddg_direction":
        graph.remove_edge(0, 2)
        graph.add_edge(2, 0, edge_type=DDG)
    else:
        graph.nodes[1]["source_file"] = "b.sol"
    write_graph(graph, changed_path)
    changed = _make_model("node", changed_path)
    assert capture_model_input(changed)["schema"] == expected["schema"]
    with pytest.raises(ValueError, match="input fingerprint mismatch"):
        assert_model_input(changed, expected)


def test_input_manifest_rejects_relation_id_permutation_before_checkpoint_load(tmp_path):
    from scripts.DFG.model_validation import capture_model_input, assert_model_input

    path = tmp_path / "graph.gpickle"
    write_graph(_fixture_graph(True), path)
    model = _make_model("node", path)
    expected = capture_model_input(model)
    first, second = list(model.etypes_dict)[:2]
    model.etypes_dict[first], model.etypes_dict[second] = (
        model.etypes_dict[second], model.etypes_dict[first]
    )
    # Parameter tensor shapes would be unchanged: state_dict loading alone
    # cannot detect this association of relation weights to the wrong triples.
    with pytest.raises(ValueError, match="schema mismatch"):
        assert_model_input(model, expected)


def test_input_manifest_binds_external_contract_targets_and_fold_identity(tmp_path):
    from scripts.DFG.model_validation import capture_model_input, assert_model_input

    path = tmp_path / "graph.gpickle"
    write_graph(_fixture_graph(True), path)
    model = _make_model("graph", path)
    external = {"contract_targets_sha256": "known-label-digest", "fold_manifest_sha256": "known-fold-digest"}
    expected = capture_model_input(model, external_inputs=external)
    assert_model_input(model, expected, external_inputs=external)
    with pytest.raises(ValueError, match="input fingerprint mismatch"):
        assert_model_input(model, expected)
    changed = dict(external, contract_targets_sha256="different-label-digest")
    with pytest.raises(ValueError, match="input fingerprint mismatch"):
        assert_model_input(model, expected, external_inputs=changed)


@pytest.mark.parametrize("change", ["wrong_feature_mode", "mutated_input"])
def test_graph_input_validation_checks_actual_features_without_mode_attribute(tmp_path, change):
    from scripts.DFG.model_validation import capture_model_input

    path = tmp_path / "graph.gpickle"
    write_graph(_fixture_graph(True), path)
    if change == "wrong_feature_mode":
        model = _model_class("graph")(
            str(path), node_feature="nodetype", hidden_size=16,
            num_layers=2, num_heads=4, use_norm=True, device="cpu",
        ).to("cpu")
    else:
        model = _make_model("graph", path)
        model.symmetrical_global_graph.nodes["expression"].data["inp"][0, 0] += 1
    with pytest.raises(ValueError, match="inside_token feature mismatch"):
        capture_model_input(model)


@pytest.mark.parametrize("task", ["node", "graph"])
def test_e0_matches_frozen_pre_ddg_reflection_weights_and_eval_logits(tmp_path, monkeypatch, task):
    import ast
    from pathlib import Path
    import sco_models.model_hgt as model_module
    from scripts.DFG.model_validation import capture_model_input

    # Execute only the frozen original function, not the rest of the archived
    # module. This independent pre-change snapshot is the E0 oracle.
    snapshot = Path(__file__).resolve().parents[1] / "audit" / "graph_utils_before_2026-10-12.py.txt"
    syntax = ast.parse(snapshot.read_text(encoding="utf-8"), filename=str(snapshot))
    original = [
        node for node in syntax.body
        if isinstance(node, ast.FunctionDef) and node.name == "reflect_graph"
    ]
    assert len(original) == 1
    # Build via ast.parse for compatibility with Python 3.7 and newer ASTs.
    function_module = ast.parse("")
    function_module.body = original
    scope = {"torch": torch}
    exec(compile(function_module, str(snapshot), "exec"), scope)

    path = tmp_path / "e0.gpickle"
    write_graph(_fixture_graph(False), path)
    with monkeypatch.context() as local_patch:
        local_patch.setattr(model_module, "reflect_graph", scope["reflect_graph"])
        torch.manual_seed(20261012)
        legacy = _make_model(task, path)
    torch.manual_seed(20261012)
    current = _make_model(task, path)

    assert capture_model_input(current) == capture_model_input(legacy)
    assert list(current.state_dict()) == list(legacy.state_dict())
    for name, tensor in legacy.state_dict().items():
        assert torch.equal(tensor, current.state_dict()[name])
    legacy.eval()
    current.eval()
    with torch.no_grad():
        legacy_logits, legacy_pool = _forward_logits(legacy, task)
        current_logits, current_pool = _forward_logits(current, task)
    assert torch.equal(legacy_logits, current_logits)
    if task == "graph":
        assert torch.equal(legacy_pool, current_pool)
