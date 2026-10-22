import copy
import json

import networkx as nx
import pytest
import torch

from scripts.DFG.experiments.stage_i_diagnostics.entry_validation import (
    FORWARD_RELATIONS, validate_entry,
)
from scripts.DFG.state.stage_f.model_adapter import reflected_input
from sco_models.graph_utils import reflect_graph


def graph(*relations):
    result = nx.MultiDiGraph()
    result.add_node("a", node_type="statement", source_file="sample.sol",
                    node_label=1, source_lines=[3], token=[1, 2, 3])
    result.add_node("b", node_type="statement", source_file="sample.sol",
                    node_label=0, source_lines=[4], token=[4, 5, 6])
    for relation in relations:
        result.add_edge("a", "b", edge_type=relation)
    return result


@pytest.mark.parametrize("entry", ["legacy", "stage_f", "e23_pilot"])
@pytest.mark.parametrize("relations", [
    ("next_line", "pos_next", "neg_next", "internal_call"),
    ("next", "DATA_DEF_USE"),
])
def test_baseline_and_scalar_supported_immutable(entry, relations):
    source = graph(*relations)
    before = copy.deepcopy(source)
    report = validate_entry(source, entry)
    assert report["supported"] is True
    assert report["intercepts_unmodified_legacy_scripts"] is False
    assert dict(source.nodes(data=True)) == dict(before.nodes(data=True))
    assert list(source.edges(keys=True, data=True)) == list(before.edges(keys=True, data=True))
    assert json.loads(json.dumps(report)) == report


@pytest.mark.parametrize("relation", sorted(FORWARD_RELATIONS - {"DATA_DEF_USE"}))
def test_state_on_legacy_rejected_with_unchanged_source(relation):
    source = graph("next_line", relation)
    before = copy.deepcopy(source)
    with pytest.raises(ValueError, match="Legacy reflect_graph"):
        validate_entry(source, "legacy")
    assert list(source.edges(keys=True, data=True)) == list(before.edges(keys=True, data=True))
    for entry in ("stage_f", "e23_pilot"):
        assert validate_entry(source, entry)["state_relations"] == [relation]


@pytest.mark.parametrize("relation", [
    "REV_DATA_DEF_USE", "STATE_UNKNOWN", "DATA_UNREGISTERED",
    "EXTERNAL_CALL_UNKNOWN",
])
def test_unknown_enhancement_rejected(relation):
    with pytest.raises(ValueError, match="Unsupported enhancement"):
        validate_entry(graph(relation), "e23_pilot")


@pytest.mark.parametrize("entry", ["unknown", "HGT", "", None, []])
def test_unknown_entry_rejected(entry):
    with pytest.raises(ValueError, match="Unknown entry"):
        validate_entry(graph("next"), entry)


def test_parallel_relations_preserved():
    source = graph("next", "DATA_DEF_USE", "STATE_DEF_USE", "STATE_DEF_USE")
    result = validate_entry(source, "e23_pilot")
    assert result["edges"] == 4
    assert result["relation_counts"]["STATE_DEF_USE"] == 2
    assert len(result["canonical_relations"]) == 3


@pytest.mark.parametrize("source", [nx.Graph(), nx.MultiGraph(), nx.DiGraph()])
def test_wrong_graph_kind_rejected(source):
    with pytest.raises(ValueError, match="directed HCG multigraph"):
        validate_entry(source, "e23_pilot")


def test_bad_node_metadata_rejected():
    source = graph("next")
    del source.nodes["a"]["node_type"]
    with pytest.raises(ValueError, match="node_type"):
        validate_entry(source, "e23_pilot")


def test_bad_edge_metadata_rejected():
    source = graph("next")
    del source["a"]["b"][0]["edge_type"]
    with pytest.raises(ValueError, match="edge_type"):
        validate_entry(source, "e23_pilot")


def test_guard_matches_real_directional_adapter_and_legacy_hazard():
    relations = ["next", "DATA_DEF_USE", "STATE_DEF_USE",
                 "STATE_ACCESS_ORDER", "EXTERNAL_CALL_BEFORE_STATE_WRITE"]
    source = graph(*relations)
    validate_entry(source, "e23_pilot")
    tensors = {("statement", rel, "statement"):
               (torch.tensor([0]), torch.tensor([1])) for rel in relations}
    before = {key: (a.clone(), b.clone()) for key, (a, b) in tensors.items()}
    adapted = reflected_input(tensors)
    old = reflect_graph(tensors)
    for rel in FORWARD_RELATIONS:
        key = ("statement", rel, "statement")
        assert adapted[key][0].tolist() == [0]
        assert adapted[key][1].tolist() == [1]
    assert adapted[("statement", "next", "statement")][0].tolist() == [0, 1]
    assert old[("statement", "DATA_DEF_USE", "statement")][0].tolist() == [0]
    assert old[("statement", "STATE_DEF_USE", "statement")][0].tolist() == [0, 1]
    for key, (a, b) in before.items():
        assert torch.equal(tensors[key][0], a)
        assert torch.equal(tensors[key][1], b)
