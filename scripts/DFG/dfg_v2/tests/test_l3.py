"""Parser-backed L3 graph/model tests; Solidity compilation not claimed."""
import copy
import networkx as nx
import numpy as np
import pytest
import torch

from sco_models import graph_utils as gu
from scripts.DFG.graph_audit import fingerprint, frozen
from scripts.DFG.dfg_v2 import ENV_FLOW, ENV_SOURCE, READS_STATE
from scripts.DFG.dfg_v2.l1 import augment_l1
from scripts.DFG.dfg_v2.l2 import augment_l2
from scripts.DFG.dfg_v2.l3 import augment_l3, strip_aux, ENV_NODE_KEYS, assert_preserved
from scripts.DFG.dfg_v2.env import ENV_KEYS
from scripts.DFG.dfg_v2.model import make_model
from scripts.DFG.dfg_v2.supervision import DfgV2Supervision
from scripts.DFG.dfg_v2.tests.test_l1 import graph_for, FILE


class Encoder:
    provenance = {"kind": "deterministic synthetic test encoder, not a tokenizer"}
    def __call__(self, code):
        values = np.zeros(512, dtype=np.float32)
        values[:len(code)] = list(code.encode("ascii"))
        return values


def build(source):
    base = graph_for(source)
    # This shared parser fixture predates classifier tests; complete only its
    # synthetic positive labels to the existing model-required schema.
    for _, data in base.nodes(data=True):
        if data["node_info_vulnerabilities"] is not None:
            data["node_info_vulnerabilities"][0]["category"] = "synthetic"
    l1, _ = augment_l1(base, {FILE: source})
    l2, _ = augment_l2(l1, {FILE: source})
    output, audit = augment_l3(l2, {FILE: source}, {}, Encoder())
    return l2, output, audit


def hubs(graph):
    return {n: d for n, d in graph.nodes(data=True) if d["node_type"] == ENV_SOURCE}


def env_edges(graph):
    return [(graph.nodes[s]["code"], graph.nodes[t]["code"], d)
            for s, t, d in graph.edges(data=True) if d["edge_type"] == ENV_FLOW]


SOURCE = """pragma solidity ^0.4.24;
contract C {
 address owner = msg.sender;
 modifier onlyOwner() { require(msg.sender == owner); _; }
 function f() public onlyOwner { require(tx.origin == owner); owner = msg.sender; }
}"""


def test_owner_reads_and_environment_hubs_keep_original_graph_exact():
    base, out, audit = build(SOURCE)
    assert fingerprint(strip_aux(out)) == fingerprint(base)
    assert_preserved(base, out)
    require = [n for n,d in out.nodes(data=True) if "require(msg.sender" in d["code"] and d["node_type"] == "expression_statement"]
    assert require
    target = require[0]
    incoming = {(out.nodes[s]["code"], d["edge_type"]) for s, _, d in out.in_edges(target, data=True)}
    assert ("msg.sender", ENV_FLOW) in incoming
    assert any("owner" in text and relation == READS_STATE for text, relation in incoming)
    assert {d["code"] for d in hubs(out).values()} == {"msg.sender", "tx.origin"}
    assert any(e["statement"]["role"] == "state_variable_declaration" and e["status"] == "projected"
               for e in audit["evidence"])
    assert any(e["callable_kind"] == "modifier_definition" for e in audit["evidence"])
    for data in hubs(out).values():
        assert set(data) == ENV_NODE_KEYS
        assert data["node_info_vulnerabilities"] is None
        assert data["node_source_code_lines"] == [] and data["method"] == ""
        assert data["label"] == "ENV:" + data["code"]
        assert type(data["token"]) is np.ndarray and data["token"].dtype == np.float32


def test_spellings_merge_per_file_and_edge_not_per_occurrence():
    source = """pragma solidity ^0.4.24; contract C { uint deadline;
      function f(uint n) public {
       if (now % 15 == 0) { deadline=1; }
       if (block.timestamp > deadline) { deadline=2; }
       uint a = msg.gas + gasleft();
       bytes32 b = block.blockhash(n) ^ blockhash(n);
       uint c = this.balance + address(this).balance;
      }}"""
    _, graph, audit = build(source)
    by_key = {}
    for key, code, attrs in env_edges(graph):
        by_key.setdefault(key, []).append(attrs)
    assert len([d for d in hubs(graph).values() if d["code"] == "block.timestamp"]) == 1
    assert sorted(d["spellings"] for d in by_key["block.timestamp"]) == [["block.timestamp"],["now"]]
    assert by_key["gasleft"][0]["spellings"] == ["gasleft()", "msg.gas"]
    assert by_key["blockhash"][0]["spellings"] == ["block.blockhash(...)", "blockhash(...)"]
    assert by_key["this.balance"][0]["spellings"] == ["address(this).balance", "this.balance"]
    assert audit["files"][FILE]["keys"]["gasleft"]["occurrences"] == 2


def test_same_key_different_files_deterministic_ids_and_original_type_rows():
    base = graph_for(SOURCE)
    second = copy.deepcopy(base)
    for _, d in second.nodes(data=True):
        d["source_file"] = "second.sol"
    base = nx.disjoint_union(base, second)
    base = nx.relabel_nodes(base, {n: 50 + n * 3 for n in base})
    a, audit = augment_l3(base, {FILE:SOURCE, "second.sol":SOURCE}, {}, Encoder())
    b, _ = augment_l3(base, {"second.sol":SOURCE, FILE:SOURCE}, {}, Encoder())
    assert fingerprint(a) == fingerprint(b)
    assert len(hubs(a)) == 4
    assert list(hubs(a)) == list(range(max(base)+1,max(base)+5))
    ordered = [(d["source_file"],d["code"]) for d in hubs(a).values()]
    assert ordered == sorted(ordered, key=lambda p:(p[0],ENV_KEYS.index(p[1])))
    left, right = gu.add_hetero_ids(copy.deepcopy(base)), gu.add_hetero_ids(copy.deepcopy(a))
    for n in base:
        assert left.nodes[n]["node_hetero_id"] == right.nodes[n]["node_hetero_id"]
    assert all(a.nodes[s]["source_file"] == a.nodes[t]["source_file"] for s,t in a.edges())
    assert fingerprint(strip_aux(a)) == fingerprint(base)


def test_unmapped_emit_has_evidence_without_orphan_node():
    source = "pragma solidity ^0.5.0; contract C { event E(address a); function f() public { emit E(msg.sender); } }"
    base = graph_for(source)
    out, audit = augment_l3(base, {FILE:source}, {}, Encoder())
    assert not hubs(out)
    assert fingerprint(out) == fingerprint(base)
    assert audit["files"][FILE]["unmapped_by_statement"]["emit_statement"] == 1
    assert audit["evidence"][0]["status"] == "unmapped"


def test_assembly_is_audited_not_interpreted():
    source = "pragma solidity ^0.4.24; contract C { function f() public { assembly { let a := caller() } } }"
    base = graph_for(source)
    out, audit = augment_l3(base, {FILE:source}, {}, Encoder())
    assert not hubs(out)
    assert audit["files"][FILE]["assembly_skipped"] == 1


def test_shadowed_unknown_and_missing_source_are_auditable():
    source = "pragma solidity ^0.5.0; contract C { function gasleft() public {} function f(uint now) public { uint a=now; gasleft(); uint b=block.chainid; } }"
    base = graph_for(source)
    out, audit = augment_l3(base, {FILE:source}, {}, Encoder())
    assert not hubs(out)
    assert audit["files"][FILE]["shadowed"]["block.timestamp"]
    assert audit["files"][FILE]["shadowed"]["gasleft"]
    assert audit["files"][FILE]["unknown_env_member"] == {"block.chainid":1}
    missing, audit = augment_l3(base, {}, {}, Encoder())
    assert fingerprint(missing) == fingerprint(base)
    assert audit["files"][FILE]["diagnostics"][0]["reason"] == "missing_exact_source"


@pytest.mark.parametrize("damage", ["string_id","bool_id","env_edge","reverse","env_node","token_list","token_double","token_width","cross_file"])
def test_bad_inputs_rejected(damage):
    base = graph_for(SOURCE)
    nodes = list(base)
    if damage == "string_id": base = nx.relabel_nodes(base,{nodes[0]:"x"})
    elif damage == "bool_id": base = nx.relabel_nodes(base,{nodes[0]:True})
    elif damage in ("env_edge","reverse"):base.add_edge(nodes[0],nodes[1],edge_type=ENV_FLOW if damage=="env_edge" else "REV_DATA_DEF_USE")
    elif damage == "env_node":base.nodes[nodes[0]]["node_type"]=ENV_SOURCE
    elif damage == "token_list":base.nodes[nodes[0]]["token"]=[0]*512
    elif damage == "token_double":base.nodes[nodes[0]]["token"]=np.zeros(512)
    elif damage == "token_width":base.nodes[nodes[0]]["token"]=np.zeros(2,dtype=np.float32)
    elif damage == "cross_file":base.nodes[nodes[0]]["source_file"]="other.sol"
    with pytest.raises((ValueError,AssertionError)):
        augment_l3(base,{FILE:SOURCE},{},Encoder())


def test_encoder_shape_and_input_immutability():
    base = graph_for(SOURCE)
    before = fingerprint(base)
    with pytest.raises(ValueError,match="Encoder"):
        augment_l3(base,{FILE:SOURCE},{},lambda _: [0]*512)
    assert fingerprint(base)==before
    _, out, _ = build(SOURCE)
    with pytest.raises(ValueError,match="auxiliary"):
        augment_l3(out,{FILE:SOURCE},{},Encoder())


def test_labels_tokens_and_source_iteration_cannot_change_environment_evidence():
    base = graph_for(SOURCE)
    changed = copy.deepcopy(base)
    for _,data in changed.nodes(data=True):
        data["node_info_vulnerabilities"]=[{"lines":[999]}]
        data["token"][:]=77
    a, aa = augment_l3(base,{FILE:SOURCE},{},Encoder())
    b, bb = augment_l3(changed,{FILE:SOURCE},{},Encoder())
    assert aa["evidence"]==bb["evidence"]
    assert [(s,t,d) for s,t,d in a.edges(data=True) if d["edge_type"]==ENV_FLOW] == [(s,t,d) for s,t,d in b.edges(data=True) if d["edge_type"]==ENV_FLOW]
    assert fingerprint(strip_aux(b))==fingerprint(changed)


@pytest.mark.parametrize("task",["node","contract"])
@pytest.mark.parametrize("profile",["G3","G3R"])
def test_real_l3_aux_exclusion_reverse_and_gradients(task,profile):
    base, graph, _ = build(SOURCE)
    model = make_model(task,graph,profile,hidden_size=16,layers=2,heads=4)
    supervision = DfgV2Supervision(model,task,[FILE])
    aux = [n for n,d in model.nx_graph.nodes(data=True) if d["node_type"]==ENV_SOURCE]
    assert all(not model.supervised_node_mask[n] for n in aux)
    if task=="node":
        assert not any(supervision.mask[n] for n in aux)
        assert all(model.node_labels[n]==-1 for n in aux)
    else:
        assert not set(aux)&set(model.node_ids_by_filename[FILE])
    reverse = [c for c in model.etypes_dict if c[1]=="REV_ENV_FLOW"]
    assert bool(reverse)==(profile=="G3R")
    incoming = sum(model.symmetrical_global_graph.num_edges(c) for c in model.etypes_dict if c[2]==ENV_SOURCE)
    assert (incoming>0)==(profile=="G3R")
    logits=supervision.forward(model)
    loss=torch.nn.functional.cross_entropy(logits,supervision.targets(model,{FILE:1}))
    loss.backward()
    index=model.ntypes_dict[ENV_SOURCE]
    assert model.adapt_ws[index].weight.grad.abs().sum()>0
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())


@pytest.mark.parametrize("profile",["G0","G1R","G2R"])
def test_l3_graph_rejected_by_profiles_without_environment(profile):
    _,graph,_=build(SOURCE)
    with pytest.raises(ValueError):
        make_model("node",graph,profile,hidden_size=16,layers=2,heads=4)
