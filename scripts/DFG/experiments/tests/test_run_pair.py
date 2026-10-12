"""Actual tiny-HGT nested evaluation leakage regression (Codex 2026-10-12).

Fixtures are synthetic graphs, not Solidity compilation fixtures. The complete
three-epoch optimizer/inner validation/checkpoint/outer evaluation loop is used.
"""
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from scripts.labeling_v2.safe_graph import write_graph
from scripts.DFG.experiments.common import (
    seed_all, read_json, tensor_digest, digest, metrics,
)
from scripts.DFG.experiments.protocol import paired_initialize
from scripts.DFG.experiments.runtime import make_model, GraphView, schema_report
from scripts.DFG.experiments.run_pair import fit_variant, effective_config
from scripts.DFG.experiments.tests.test_runtime import graph_fixture


@pytest.fixture(autouse=True)
def bounded_torch_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def make_pair(tmp_path, changed_outer_labels):
    graphs = {"E0": graph_fixture(ddg=False), "E1": graph_fixture(ddg=True)}
    for graph in graphs.values():
        if changed_outer_labels:
            for _, data in graph.nodes(data=True):
                if data["source_file"] == "test.sol":
                    data["node_info_vulnerabilities"] = (
                        None if data["node_info_vulnerabilities"] else
                        [{"category": "reentrancy", "lines": data["node_source_code_lines"]}])
    pair = {}
    for variant in ("E0", "E1"):
        path = tmp_path / (variant + ".gpickle")
        write_graph(graphs[variant], path)
        seed_all(1234)
        pair[variant] = make_model("node", path, "cpu", hidden_size=8, layers=2, heads=2)
    audit = paired_initialize(pair["E0"], pair["E1"], seed=117)
    return graphs, pair, audit


def test_outer_node_labels_cannot_change_training_selection_or_best_last_weights(tmp_path):
    args = SimpleNamespace(
        mode="smoke", seed=1, epochs=50, smoke_epochs=3, device="cpu", threads=1)
    config = effective_config("node", args)
    config.update(hidden_size=8, heads=2)
    outcomes, graphs_by_case, initializations = {}, {}, {}
    for case, changed in (("original", False), ("outer_flipped", True)):
        folder = tmp_path / case
        folder.mkdir()
        graphs, models, pairing = make_pair(folder, changed)
        graphs_by_case[case] = graphs
        initializations[case] = pairing
        outcomes[case] = {}
        for variant in ("E0", "E1"):
            model = models[variant]
            views = {phase: GraphView(model, [filename]) for phase, filename in (
                ("inner_train", "train.sol"), ("inner_val", "valid.sol"),
                ("outer_test", "test.sol"))}
            assert schema_report(views)["supported"]
            # Binding differs naturally with the frozen outer label version.
            binding = {"fixture": "outer-label-isolation",
                       "variant": variant, "outer_labels_changed": changed,
                       "config_sha256": digest(config),
                       "initial_state_sha256": tensor_digest(model.state_dict())}
            seed_all(90001)
            result = fit_variant(
                model, views, "node", {name: 1 for name in (
                    "train.sol", "valid.sol", "test.sol")},
                config, folder / variant, binding, list(graphs[variant]))
            outcomes[case][variant] = result
            assert result["history_rows"] == 3
            assert result["gradient_audit"]["backbone_update_l1"] > 0
            assert result["checkpoint_roundtrip_exact"] == {"best": True, "last": True}
            if variant == "E1":
                assert result["gradient_audit"]["ddg_message_update_l1"] > 0

    assert initializations["original"] == initializations["outer_flipped"]
    for variant in ("E0", "E1"):
        # Prove the intervention changed only outer node supervision.
        original_graph = graphs_by_case["original"][variant]
        changed_graph = graphs_by_case["outer_flipped"][variant]
        assert list(original_graph) == list(changed_graph)
        assert list(original_graph.edges(keys=True, data=True)) == list(changed_graph.edges(keys=True, data=True))
        for node in original_graph:
            left, right = original_graph.nodes[node], changed_graph.nodes[node]
            assert left.keys() == right.keys()
            for key in left:
                if key == "node_info_vulnerabilities" and left["source_file"] == "test.sol":
                    assert bool(left[key]) != bool(right[key])
                elif key == "token":
                    np.testing.assert_array_equal(left[key], right[key])
                else:
                    assert left[key] == right[key]
        original = tmp_path / "original" / variant
        altered = tmp_path / "outer_flipped" / variant
        assert (original / "history.jsonl").read_text() == (altered / "history.jsonl").read_text()
        results = [outcomes[case][variant] for case in ("original", "outer_flipped")]
        assert results[0]["best_epoch"] == results[1]["best_epoch"]
        assert results[0]["last_epoch"] == results[1]["last_epoch"]
        assert results[0]["best_inner_val_loss"] == results[1]["best_inner_val_loss"]
        for checkpoint in ("best", "last"):
            first = torch.load(str(original / (checkpoint + ".pt")), map_location="cpu")
            second = torch.load(str(altered / (checkpoint + ".pt")), map_location="cpu")
            assert first["state_sha256"] == second["state_sha256"]
            assert tensor_digest(first["state_dict"]) == tensor_digest(second["state_dict"])
            assert first["monitor"] == second["monitor"]
            assert first["epoch"] == second["epoch"]
            # Input binding must notice label changes even though fitted weights
            # and all training decisions remain exactly identical.
            assert first["model_input"]["input_sha256"] != second["model_input"]["input_sha256"]

        before = read_json(original / "outer_predictions.json")
        after = read_json(altered / "outer_predictions.json")
        assert len(before) == len(after) == 4
        expected_ids = ["test.sol:" + str(i * 17) for i in range(4)]
        assert [row["original_graph_node_id"] for row in before] == expected_ids
        assert [row["original_graph_node_id"] for row in after] == expected_ids
        for left, right in zip(before, after):
            assert left["file"] == right["file"] == "test.sol"
            assert left["model_node_id"] == right["model_node_id"]
            assert left["target"] == 1 - right["target"]
            for checkpoint in ("best", "last"):
                assert left[checkpoint] == right[checkpoint]
                assert left[checkpoint + "_positive_probability"] == right[checkpoint + "_positive_probability"]
        for predictions, result in zip((before, after), results):
            for checkpoint in ("best", "last"):
                assert result["outer_test"][checkpoint] == metrics(
                    [x["target"] for x in predictions], [x[checkpoint] for x in predictions])
