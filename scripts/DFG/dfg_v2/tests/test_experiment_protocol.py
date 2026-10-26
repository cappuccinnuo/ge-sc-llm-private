"""Prompt 7 frozen nested protocol and v2 relation support acceptance."""
import copy
import json

import networkx as nx
import numpy as np
import pytest
import torch
from torch.nn import functional as F

from scripts.DFG.dfg_v2 import (DATA_DEF_USE, WRITES_STATE, READS_STATE, ENV_FLOW,
                               ENV_SOURCE, REVERSE_OF)
from scripts.DFG.dfg_v2.experiment.protocol import (
    PARTS, PROTOCOL_NAME, PROTOCOL_VERSION, load_folds, select_split, validate_parts,
)
from scripts.DFG.dfg_v2.experiment.support import support, gradient_audit
from scripts.DFG.dfg_v2.model import make_model, validate_registration
from scripts.DFG.dfg_v2.supervision import DfgV2Supervision
from scripts.DFG.experiments.protocol import make_fold_document, _doc_digest
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration.io import sha256, write_json


def frozen_record(tmp_path, task="contract", seed=1, fraction=.2):
    labels = {"file_%02d.sol" % i: int(task == "node" or i >= 10) for i in range(20)}
    doc = make_fold_document(labels, task, "a" * 64, seed=seed, inner_fraction=fraction)
    fold_path, label_path = tmp_path / "folds.json", tmp_path / "labels.json"
    write_json(fold_path, doc)
    write_json(label_path, [{"contract_name": f, "targets": y} for f, y in labels.items()])
    record = dict(task=task, graph_files=sorted(labels), prepared_manifest_sha256="a" * 64,
                  folds=dict(path=str(fold_path), sha256=sha256(fold_path)),
                  labels=dict(path=str(label_path), sha256=sha256(label_path)))
    return record, doc


@pytest.mark.parametrize("task,count", [("contract", 5), ("node", 10)])
def test_load_frozen_nested_folds_is_read_only_and_complete(tmp_path, task, count):
    record, document = frozen_record(tmp_path, task)
    assert load_folds(record) == document
    assert PROTOCOL_NAME != "paper_kfold"
    assert PROTOCOL_VERSION != document["protocol_version"]
    all_test = []
    for fold in range(count):
        selected = select_split(record, fold)
        assert selected == document["folds"][fold]
        parts = validate_parts(selected, record["graph_files"])
        assert set(parts) == set(PARTS)
        all_test.extend(parts["outer_test"])
        assert set(parts["inner_train"]) | set(parts["inner_val"]) | set(parts["outer_test"]) == set(record["graph_files"])
    assert sorted(all_test) == record["graph_files"]
    assert sha256(record["folds"]["path"]) == record["folds"]["sha256"]


@pytest.mark.parametrize("bad", [-1, 5, "0", True, 1.0, None])
def test_unknown_fold_index_rejected(tmp_path, bad):
    record, _ = frozen_record(tmp_path)
    with pytest.raises(ValueError, match="fold index"):
        select_split(record, bad)


@pytest.mark.parametrize("damage", ["duplicate", "overlap", "omitted", "unknown",
                                    "empty", "mixed_keys", "population_duplicate"])
def test_partition_fail_closed(damage):
    parts = dict(inner_train_files=["train.sol"], inner_val_files=["val.sol"],
                 outer_test_files=["test.sol"])
    files = ["train.sol", "val.sol", "test.sol"]
    if damage == "duplicate":
        parts["inner_train_files"].append("train.sol")
    elif damage == "overlap":
        parts["inner_val_files"].append("train.sol")
    elif damage == "omitted":
        files.append("omitted.sol")
    elif damage == "unknown":
        parts["outer_test_files"] = ["unknown.sol"]
    elif damage == "empty":
        parts["inner_train_files"] = []
    elif damage == "mixed_keys":
        parts["inner_train"] = ["train.sol"]
    else:
        files.append("train.sol")
    with pytest.raises(ValueError):
        validate_parts(parts, files)


@pytest.mark.parametrize("damage", ["fold_bytes", "task", "population", "prepared", "labels", "overlap"])
def test_frozen_inputs_reject_drift_even_with_resigned_file_sha(tmp_path, damage):
    record, doc = frozen_record(tmp_path)
    if damage == "fold_bytes":
        with open(record["folds"]["path"], "a") as handle:
            handle.write("\n")
    elif damage == "task":
        record["task"] = "node"
    elif damage == "population":
        record["graph_files"] = record["graph_files"][:-1]
    elif damage == "prepared":
        record["prepared_manifest_sha256"] = "b" * 64
    elif damage == "labels":
        path = record["labels"]["path"]
        rows = json.loads(open(path).read())
        rows[0]["targets"] = 1
        write_json(path, rows)
        record["labels"]["sha256"] = sha256(path)
    else:
        doc["folds"][0]["inner_val_files"] = doc["folds"][0]["inner_train_files"][:2]
        doc["split_sha256"] = _doc_digest(doc)
        write_json(record["folds"]["path"], doc)
        record["folds"]["sha256"] = sha256(record["folds"]["path"])
    with pytest.raises((ValueError, AssertionError)):
        load_folds(record)


@pytest.mark.parametrize("seed,fraction", [(2, .2), (1, .3)])
def test_fold_generation_configuration_cannot_change(tmp_path, seed, fraction):
    record, _ = frozen_record(tmp_path, seed=seed, fraction=fraction)
    with pytest.raises(ValueError, match="input task"):
        load_folds(record)


def small_graph(profile="G3R"):
    graph = nx.MultiDiGraph()
    for i, filename in enumerate(("train.sol", "val.sol", "test.sol")):
        for suffix, typ in (("f", "function_definition"), ("d", "new_variable"),
                            ("s", "expression_statement")):
            graph.add_node(filename + ":" + suffix, node_type=typ, source_file=filename,
                           code=suffix, token=np.full(512, i + .125, dtype=np.float32),
                           node_info_vulnerabilities=[{"lines": [1], "category": "synthetic"}] if suffix == "s" else None)
        f, d, s = [filename + ":" + suffix for suffix in ("f", "d", "s")]
        graph.add_edge(f, d, edge_type="first_next_line")
        graph.add_edge(d, s, edge_type="next_line")
        if profile != "G0":
            graph.add_edge(d, s, edge_type=DATA_DEF_USE)
            graph.add_edge(s, d, edge_type=WRITES_STATE)
            graph.add_edge(d, s, edge_type=READS_STATE)
            env = filename + ":env"
            graph.add_node(env, node_type=ENV_SOURCE, source_file=filename, code="msg.sender",
                           token=np.full(512, .25, dtype=np.float32))
            graph.add_edge(env, s, edge_type=ENV_FLOW)
    if profile != "G0":
        graph.add_node("test.sol:rare", node_type="return", source_file="test.sol",
                       code="return", token=np.ones(512, dtype=np.float32),
                       node_info_vulnerabilities=None)
        graph.add_edge("test.sol:s", "test.sol:rare", edge_type="next_line")
        graph.add_edge("test.sol:d", "test.sol:rare", edge_type=DATA_DEF_USE)
    return graph


PARTITION = dict(inner_train_files=["train.sol"], inner_val_files=["val.sol"],
                 outer_test_files=["test.sol"])


@pytest.mark.parametrize("profile", ["G0", "G3", "G3R"])
def test_support_uses_actual_materialized_schema_and_preserves_graph(profile):
    graph = small_graph(profile)
    before = fingerprint(graph)
    counts = support(graph, profile, PARTITION)
    model = make_model("node", graph, profile, hidden_size=16, heads=4)
    assert counts["schema"] == validate_registration(model)
    assert counts["files"] == dict(inner_train=1, inner_val=1, outer_test=1)
    for row in counts["relations"]:
        canonical = tuple(row["canonical"])
        assert sum(row[p + "_edges"] for p in PARTS) == model.symmetrical_global_graph.num_edges(canonical)
    if profile == "G0":
        assert counts["v2_training_edges"] == 0
        assert not counts["registered_without_train_relations"]
    else:
        rare = ["new_variable", DATA_DEF_USE, "return"]
        assert rare in counts["registered_without_train_relations"]
        assert "return" in counts["registered_without_train_nodes"]
    if profile == "G3R":
        indexed = {tuple(r["canonical"]): r for r in counts["relations"]}
        for canonical, row in indexed.items():
            if canonical[1] in REVERSE_OF:
                reverse = canonical[2], REVERSE_OF[canonical[1]], canonical[0]
                assert reverse in indexed
                assert all(row[p + "_edges"] == indexed[reverse][p + "_edges"] for p in PARTS)
        assert counts["v2_training_edges"] == 8
    assert fingerprint(graph) == before


def test_support_rejects_cross_file_edges():
    graph = small_graph()
    graph.add_edge("train.sol:d", "test.sol:s", edge_type=DATA_DEF_USE)
    with pytest.raises(ValueError, match="Cross-file"):
        support(graph, "G3R", PARTITION)


@pytest.mark.parametrize("task", ["node", "contract"])
def test_gradient_all_v2_relations_and_heldout_only_support_are_distinct(task):
    graph = small_graph()
    torch.manual_seed(61)
    model = make_model(task, graph, "G3R", hidden_size=16, heads=4)
    counts = support(graph, "G3R", PARTITION)
    supervised = DfgV2Supervision(model, task, PARTITION["inner_train_files"])
    assert all(model.nx_graph.nodes[n]["source_file"] == "train.sol"
               for n in supervised.full_ids)
    if task == "node":
        assert all(model.nx_graph.nodes[n]["node_type"] != ENV_SOURCE for n in supervised.full_ids)
    logits = supervised.forward(model)
    loss = F.cross_entropy(logits, supervised.targets(model, {"train.sol": 1}))
    loss.backward()
    audit = gradient_audit(model, counts)
    assert audit["v2_training_support"] == 8
    assert audit["v2_relations"] == audit["ddg_relations"]
    assert {r["canonical"][1] for r in audit["v2_relations"]} == set(REVERSE_OF) | set(REVERSE_OF.values())
    for row in audit["v2_relations"]:
        if row["inner_train_edges"]:
            assert row["message_gradient_l1"] > 0
            assert row["status"] == "training_support_nonzero_gradient"
        else:
            assert row["message_gradient_l1"] == row["attention_gradient_l1"] == 0
            assert row["status"] == "no_training_v2_support"
        assert len(row["per_layer"]) == 2
        assert row["attention_gradient_l1"] >= 0
    assert audit["backbone_gradient_l1"] > 0


@pytest.mark.parametrize("damage", ["disconnected", "unseen_gradient", "nonfinite", "dictionary"])
def test_gradient_audit_rejects_genuine_integration_errors(damage):
    graph = small_graph()
    model = make_model("node", graph, "G3R", hidden_size=16, heads=4)
    counts = support(graph, "G3R", PARTITION)
    if damage != "disconnected":
        selected = DfgV2Supervision(model, "node", ["train.sol"])
        F.cross_entropy(selected.forward(model), selected.targets(model, {})).backward()
        if damage == "unseen_gradient":
            canonical = ("new_variable", DATA_DEF_USE, "return")
            model.gcs[0].relation_msg.grad[model.etypes_dict[canonical]].fill_(1)
        elif damage == "nonfinite":
            model.gcs[0].relation_msg.grad.fill_(float("nan"))
        else:
            canonical = next(iter(model.etypes_dict))
            model.etypes_dict[canonical] += 1
    with pytest.raises((AssertionError, ValueError)):
        gradient_audit(model, counts)
