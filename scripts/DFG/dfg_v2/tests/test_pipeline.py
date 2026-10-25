"""Composition-only tests; parser-backed fixtures are not solc-validated."""
import copy

import networkx as nx
import pytest

from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration.pipeline import computation_fingerprint
from scripts.DFG.dfg_v2 import (PROFILES, DATA_DEF_USE, WRITES_STATE,
                               READS_STATE, ENV_FLOW, ENV_SOURCE)
from scripts.DFG.dfg_v2 import pipeline as p
from scripts.DFG.dfg_v2.l3 import strip_aux
from scripts.DFG.dfg_v2.tests.test_l1 import graph_for, FILE
from scripts.DFG.dfg_v2.tests.test_l3 import Encoder

SOURCE = """pragma solidity ^0.4.24;
contract C {
 uint total;
 function f(uint amount) public returns (uint) {
  uint x = amount;
  total = x;
  require(msg.sender != address(0));
  return total + x;
 }
}"""


def prepared():
    return graph_for(SOURCE), {FILE: SOURCE}, {}


def edges(graph):
    return {(s, t, d["edge_type"]) for s, t, d in graph.edges(data=True)}


def test_F0_is_same_original_object_and_no_layer_called(monkeypatch):
    base, sources, metadata = prepared()
    before = fingerprint(base)
    def forbidden(*args, **kwargs):
        raise AssertionError("F0 may not call an analyzer")
    for module, name in ((p.l1, "augment_l1"), (p.l2, "augment_l2"), (p.l3, "augment_l3")):
        monkeypatch.setattr(module, name, forbidden)
    out, audit = p.build(base, sources, metadata, ())
    assert out is base
    assert fingerprint(out) == before == audit["input_fingerprint"] == audit["output_fingerprint"]
    assert audit["graph_key"] == "F0" and audit["layers"] == {}
    assert audit["profiles"] == ["G0"] and audit["forward_relations"] == []


def test_incremental_exact_parity_and_each_layer_once(monkeypatch):
    base, sources, metadata = prepared()
    before = fingerprint(base)
    direct1, _ = p.l1.augment_l1(base, sources, metadata)
    direct2, _ = p.l2.augment_l2(direct1, sources, metadata)
    direct3, _ = p.l3.augment_l3(direct2, sources, metadata, Encoder())
    calls = []
    for module, name, layer in ((p.l1, "augment_l1", "L1"), (p.l2, "augment_l2", "L2"),
                                (p.l3, "augment_l3", "L3")):
        original = getattr(module, name)
        def wrapped(*args, _original=original, _layer=layer, **kwargs):
            calls.append((_layer, fingerprint(args[0])))
            return _original(*args, **kwargs)
        monkeypatch.setattr(module, name, wrapped)
    outputs = list(p.iter_build(base, sources, metadata, ("L1", "L2", "L3"), Encoder()))
    assert [key for key, _, _ in outputs] == ["F0", "F1", "F2", "F3"]
    assert [x[0] for x in calls] == ["L1", "L2", "L3"]
    assert calls[1][1] == fingerprint(direct1) and calls[2][1] == fingerprint(direct2)
    for (_, actual, audit), expected in zip(outputs, (base, direct1, direct2, direct3)):
        assert fingerprint(actual) == fingerprint(expected) == audit["output_fingerprint"]
        assert computation_fingerprint(actual) == audit["computation_fingerprint"]
        assert audit["invariants"]["evidence_complete"]
        assert audit["labels_used_for_analysis"] is False
        assert not any(d["edge_type"].startswith("REV_") for _, _, d in actual.edges(data=True))
    assert fingerprint(base) == before
    assert [len(audit["layers"]) for _, _, audit in outputs] == [0, 1, 2, 3]
    assert all(edges(outputs[i][1]) <= edges(outputs[i+1][1]) for i in range(3))
    assert fingerprint(strip_aux(outputs[-1][1])) == fingerprint(outputs[-2][1])
    added = set(outputs[-1][1]) - set(base)
    assert added and all(outputs[-1][1].nodes[n]["node_type"] == ENV_SOURCE for n in added)
    assert outputs[-1][2]["tokenizer"] == Encoder.provenance


def test_deterministic_and_previous_yields_remain_unchanged():
    base, sources, metadata = prepared()
    first = p.iter_build(base, sources, metadata, ("L1", "L2", "L3"), Encoder())
    snapshots = []
    for _, graph, audit in first:
        snapshots.append((graph, fingerprint(graph), copy.deepcopy(audit)))
    again, audit = p.build(base, sources, metadata, ("L1", "L2", "L3"), Encoder())
    assert computation_fingerprint(again) == snapshots[-1][2]["computation_fingerprint"]
    assert fingerprint(again) == snapshots[-1][1]
    for graph, saved, old_audit in snapshots:
        assert fingerprint(graph) == saved
        assert old_audit["output_fingerprint"] == saved


def test_missing_source_preserves_file_and_audits_each_layer():
    base, _, metadata = prepared()
    out, audit = p.build(base, {}, metadata, ("L1", "L2", "L3"), Encoder())
    assert fingerprint(out) == fingerprint(base)
    assert audit["missing_sources"] == [FILE]
    assert audit["source_hashes"] == {}
    for layer in audit["layers"].values():
        assert any(d["kind"] == "file_fallback" for d in layer["files"][FILE]["diagnostics"])


def test_two_files_never_connect_and_keep_same_name_separate():
    base, _, metadata = prepared()
    second = copy.deepcopy(base)
    for _, attrs in second.nodes(data=True):
        attrs["source_file"] = "second.sol"
    base = nx.disjoint_union(base, second)
    out, audit = p.build(base, {FILE: SOURCE, "second.sol": SOURCE}, metadata,
                         ("L1", "L2", "L3"), Encoder())
    assert all(out.nodes[s]["source_file"] == out.nodes[t]["source_file"] for s, t in out.edges())
    assert set(audit["source_hashes"]) == {FILE, "second.sol"}
    assert len({d["source_file"] for _, d in out.nodes(data=True) if d["node_type"] == ENV_SOURCE}) == 2


@pytest.mark.parametrize("layers", [("L2",), ("L3",), ("L1", "L3"), ("L2", "L1"),
                                    ("L1", "L1"), ("L1", "L2", "L3", "L4"), "L1", None])
def test_invalid_layer_prefix_rejected(layers):
    base, sources, metadata = prepared()
    with pytest.raises(ValueError, match="prefix"):
        p.build(base, sources, metadata, layers, Encoder())


@pytest.mark.parametrize("key,layers", [("F0", ()), ("F1", ("L1",)),
                                        ("F2", ("L1", "L2")), ("F3", ("L1", "L2", "L3"))])
def test_layer_key_roundtrip(key, layers):
    assert p.layers_for_key(key) == layers
    assert p.key_for_layers(layers) == key


def test_profiles_derive_forward_sets_including_future_directional_controls(monkeypatch):
    assert p.key_for_profile("G0") == "F0"
    assert p.key_for_profile("G1R") == "F1"
    assert p.key_for_profile("G2R") == "F2"
    assert p.key_for_profile("G3") == p.key_for_profile("G3R") == "F3"
    monkeypatch.setitem(PROFILES, "G1", frozenset((DATA_DEF_USE,)))
    monkeypatch.setitem(PROFILES, "G2", frozenset((DATA_DEF_USE, WRITES_STATE, READS_STATE)))
    assert p.key_for_profile("G1") == "F1" and p.key_for_profile("G2") == "F2"
    assert set(p.profiles_for_key("F1")) == {"G1", "G1R"}
    monkeypatch.setitem(PROFILES, "INVALID", frozenset((ENV_FLOW,)))
    with pytest.raises(ValueError, match="graph key"):
        p.key_for_profile("INVALID")


@pytest.mark.parametrize("key", ["F4", None, "", "G0"])
def test_unknown_key_rejected(key):
    with pytest.raises(ValueError, match="graph key"):
        p.layers_for_key(key)


def test_L3_requires_encoder_before_any_build():
    base, sources, metadata = prepared()
    with pytest.raises(ValueError, match="token_encoder"):
        p.build(base, sources, metadata, ("L1", "L2", "L3"))


@pytest.mark.parametrize("limit", [0, -1, 1.2, True])
def test_invalid_limits(limit):
    base, sources, metadata = prepared()
    with pytest.raises(ValueError, match="max_iterations"):
        p.build(base, sources, metadata, (), max_iterations=limit)


def test_original_crossfile_and_preenhanced_input_rejected():
    base, sources, metadata = prepared()
    nodes = list(base)
    base.nodes[nodes[-1]]["source_file"] = "other.sol"
    base.add_edge(nodes[0], nodes[-1], edge_type="next_line")
    with pytest.raises(ValueError, match="Cross-file"):
        p.build(base, sources, metadata, ())
    base, sources, metadata = prepared()
    base.add_edge(nodes[0], nodes[-1], edge_type=DATA_DEF_USE)
    with pytest.raises(ValueError, match="without v2"):
        p.build(base, sources, metadata, ())


@pytest.mark.parametrize("tamper", ["node_label", "base_edge", "graph_attribute", "evidence_missing",
    "evidence_wrong_endpoint", "evidence_unprojected", "evidence_orphan", "duplicate", "self", "reverse",
    "crossfile"])
def test_final_validation_rejects_tampered_outputs(tamper):
    base, sources, metadata = prepared()
    out, audit = p.build(base, sources, metadata, ("L1", "L2", "L3"), Encoder())
    records = copy.deepcopy(audit["layers"])
    if tamper == "node_label":
        out.nodes[next(iter(base))]["node_info_vulnerabilities"] = [{"lines": [999]}]
    elif tamper == "base_edge":
        s, t, k = next(iter(base.edges(keys=True)))
        out.remove_edge(s, t, k)
    elif tamper == "graph_attribute":
        out.graph["unexpected"] = 1
    else:
        s, t, k, d = next((s,t,k,d) for s,t,k,d in out.edges(keys=True,data=True)
                         if d["edge_type"] == ENV_FLOW)
        if tamper == "evidence_missing":
            d["evidence_indices"] = []
        elif tamper == "evidence_wrong_endpoint":
            records["L3"]["evidence"][d["evidence_indices"][0]]["source"] = -123
        elif tamper == "evidence_unprojected":
            records["L3"]["evidence"][d["evidence_indices"][0]]["status"] = "unmapped"
        elif tamper == "evidence_orphan":
            out.remove_edge(s, t, k)
        elif tamper == "duplicate":
            out.add_edge(s, t, **copy.deepcopy(d))
        elif tamper == "self":
            out.add_edge(s, s, **copy.deepcopy(d))
        elif tamper == "reverse":
            out.add_edge(t, s, edge_type="REV_ENV_FLOW")
        elif tamper == "crossfile":
            out.nodes[s]["source_file"] = "other.sol"
    with pytest.raises(AssertionError):
        p.assert_preserved(base, out, "F3", records)


def test_output_false_label_analysis_claim_rejected():
    base, sources, metadata = prepared()
    out, audit = p.build(base, sources, metadata, ("L1",))
    audit["layers"]["L1"]["labels_used_for_analysis"] = True
    with pytest.raises(AssertionError, match="exclude labels"):
        p.assert_preserved(base, out, "F1", audit["layers"])


def test_unknown_profile_relation_cannot_silently_become_baseline(monkeypatch):
    monkeypatch.setitem(PROFILES, "UNKNOWN", frozenset(("SOME_FUTURE_RELATION",)))
    with pytest.raises(ValueError, match="unknown relation"):
        p.key_for_profile("UNKNOWN")


@pytest.mark.parametrize("layer,relation", [("L1", DATA_DEF_USE), ("L2", READS_STATE)])
def test_scalar_and_state_evidence_corruption_rejected(layer, relation):
    base, sources, metadata = prepared()
    out, audit = p.build(base, sources, metadata, ("L1", "L2"))
    _, _, attrs = next((s, t, d) for s, t, d in out.edges(data=True) if d["edge_type"] == relation)
    index = attrs["ddg_fact_indices" if layer == "L1" else "evidence_indices"][0]
    record = audit["layers"][layer]["evidence"][index]
    if layer == "L1":
        record["self_fact"] = True
    else:
        record["relation"] = WRITES_STATE
    with pytest.raises(AssertionError):
        p.assert_preserved(base, out, "F2", audit["layers"])
