"""Prompt 3 semantic graph acceptance. Parser fixtures, not solc-validated."""
import copy
import networkx as nx
import pytest
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.frontend import text
from scripts.DFG.dfg_v2 import DATA_DEF_USE, WRITES_STATE, READS_STATE
from scripts.DFG.dfg_v2.l1 import augment_l1
from scripts.DFG.dfg_v2.l2 import augment_l2, assert_preserved
from scripts.DFG.dfg_v2.tests.test_l1 import graph_for, MY_BANK, FILE

RELATIONS = {WRITES_STATE, READS_STATE}


def norm(value):
    return " ".join(value.split())


def relation_set(graph):
    return {(norm(graph.nodes[s]["code"]), norm(graph.nodes[t]["code"]), d["edge_type"])
            for s, t, d in graph.edges(data=True) if d["edge_type"] in RELATIONS}


def enhanced(source, l1=False):
    graph = graph_for(source)
    if l1:
        graph, _ = augment_l1(graph, {FILE: source})
    output, audit = augment_l2(graph, {FILE: source})
    assert_preserved(graph, output)
    return graph, output, audit


REENTRANCY = """pragma solidity ^0.4.24;
contract C {
 mapping(address => uint) userBalance;
 function addToBalance() public payable { userBalance[msg.sender] += msg.value; }
 function withdrawBalance() public {
  if (!(msg.sender.call.value(userBalance[msg.sender])())) { throw; }
  userBalance[msg.sender] = 0;
 }
}"""


def test_cross_function_decl_hub_has_exact_four_edges():
    _, graph, audit = enhanced(REENTRANCY, l1=True)
    decl = "mapping(address => uint) userBalance;"
    write = "userBalance[msg.sender] += msg.value;"
    last = "userBalance[msg.sender] = 0;"
    guard = "if (!(msg.sender.call.value(userBalance[msg.sender])())) { throw; }"
    assert relation_set(graph) == {(write, decl, WRITES_STATE), (decl, write, READS_STATE),
                                  (decl, guard, READS_STATE), (last, decl, WRITES_STATE)}
    assert len({e["callable"] for e in audit["evidence"] if e["status"] == "projected"}) == 2
    assert all(s != t for s, t, d in graph.edges(data=True) if d["edge_type"] in RELATIONS)


def test_my_bank_alias_and_min_sum():
    _, graph, audit = enhanced(MY_BANK)
    edges = relation_set(graph)
    assert ("acc.balance -= _am;", "mapping(address => Holder) public Acc;", WRITES_STATE) in edges
    assert ("mapping(address => Holder) public Acc;", "var acc = Acc[msg.sender];", READS_STATE) in edges
    assert any(s == "uint public MinSum;" and t.startswith("if (acc.balance") and r == READS_STATE
               for s, t, r in edges)
    alias = [d for s, t, d in graph.edges(data=True)
             if norm(graph.nodes[s]["code"]) == "acc.balance -= _am;" and d["edge_type"] == WRITES_STATE]
    assert len(alias) == 1 and alias[0]["via_alias"]
    assert audit["files"][FILE]["alias_occurrences"] > 0
    bindings = audit["files"][FILE]["binding_audits"].values()
    aliases = [a for b in bindings for a in b["aliases"]]
    assert any(a["name"] == "acc" and a["state_name"] == "Acc" for a in aliases)
    assert any(b["mode_for_implicit_alias"] == "legacy" and b["version_evidence"] for b in bindings)


def test_guards_modifiers_constructor_and_state_initializer_have_own_units():
    source = """pragma solidity ^0.5.0; contract C {
 uint seed; uint limit = seed + 1; address owner;
 modifier onlyOwner { require(msg.sender == owner); _; }
 constructor(uint x) public { seed = x; }
 function changeOwner(address o) public onlyOwner { require(msg.sender == owner); owner = o; }
}"""
    _, graph, _ = enhanced(source)
    pairs = relation_set(graph)
    assert ("uint seed;", "uint limit = seed + 1;", READS_STATE) in pairs
    assert ("seed = x;", "uint seed;", WRITES_STATE) in pairs
    assert ("owner = o;", "address owner;", WRITES_STATE) in pairs
    # Two distinct require statements retain separate IDs even with equal text.
    requirements = [(s, t) for s, t, d in graph.edges(data=True) if d["edge_type"] == READS_STATE
                    and norm(graph.nodes[t]["code"]) == "require(msg.sender == owner);"]
    assert len(requirements) == 2 and len({t for s, t in requirements}) == 2
    assert not any(t.startswith("function ") or t.startswith("modifier ") for s, t, _ in pairs)


@pytest.mark.parametrize("body", [
    "function f(uint x) public { x = 1; }",
    "function f() public { x = 1; uint x; }",
    "function f() public returns(uint x) { x = 1; }",
])
def test_callable_wide_shadowing_even_before_declaration(body):
    source = "pragma solidity ^0.5.0; contract C { uint x; " + body + " }"
    _, graph, _ = enhanced(source)
    assert not relation_set(graph)


def test_unique_same_file_inherited_declaration():
    source = """pragma solidity ^0.5.0;
 contract A { uint x; } contract B is A { function f() public { x = 1; } }"""
    _, graph, audit = enhanced(source)
    assert relation_set(graph) == {("x = 1;", "uint x;", WRITES_STATE)}
    assert all(e["state"]["start"] < source.index("contract B") for e in audit["evidence"])


def test_memory_copy_read_without_state_write_and_constant_option():
    source = """pragma solidity ^0.5.0; contract C {
 struct S { uint a; } S st; uint constant K=1;
 function f() public { S memory m=st; m.a=1; uint k=K; }
}"""
    base, graph, _ = enhanced(source)
    edges = relation_set(graph)
    assert ("S st;", "S memory m=st;", READS_STATE) in edges
    assert not any(r == WRITES_STATE or s == "uint constant K=1;" for s,t,r in edges)
    with_constants, _ = augment_l2(base, {FILE: source}, include_constants=True)
    assert ("uint constant K=1;", "uint k=K;", READS_STATE) in relation_set(with_constants)


def test_l1_fallback_assembly_function_still_has_l2_and_l1_edges_unchanged():
    source = """pragma solidity ^0.5.0; contract C {
 uint st;
 function bad(uint x) public { st = x; assembly { let y := 1 } }
 function good(uint x) public returns(uint) { uint y=x; return y; }
}"""
    base = graph_for(source)
    l1, old = augment_l1(base, {FILE: source})
    assert any(f["status"] == "fallback" for f in old["files"][FILE]["analysis"]["functions"])
    before = fingerprint(l1)
    graph, _ = augment_l2(l1, {FILE: source})
    assert fingerprint(l1) == before
    assert ("st = x;", "uint st;", WRITES_STATE) in relation_set(graph)
    assert [(s,t,k,d) for s,t,k,d in l1.edges(keys=True,data=True) if d["edge_type"] == DATA_DEF_USE] == [
        (s,t,k,d) for s,t,k,d in graph.edges(keys=True,data=True) if d["edge_type"] == DATA_DEF_USE]
    assert_preserved(l1, graph)


def test_missing_statement_or_decl_anchor_is_counted_and_never_reassigned():
    source = """pragma solidity ^0.5.0; contract C {
 uint x; event E(uint a); function f() public { emit E(x); x=1; }
}"""
    base = graph_for(source)
    _, audit = augment_l2(base, {FILE: source})
    assert any(e["status"] == "unmapped" and e["statement"]["role"] == "emit_statement"
               for e in audit["evidence"])
    declaration = next(n for n,d in base.nodes(data=True) if norm(d["code"]) == "uint x;")
    base.remove_node(declaration)
    graph, audit = augment_l2(base, {FILE: source})
    assert not relation_set(graph)
    assert audit["files"][FILE]["anchor_missing"] >= 1
    assert audit["files"][FILE]["unmapped"] >= 1


def test_no_pragma_direct_state_does_not_require_l1_scope_mode():
    source = "contract C { uint x; function f() public { x=1; } }"
    _, graph, _ = enhanced(source)
    assert relation_set(graph) == {("x=1;", "uint x;", WRITES_STATE)}


def test_labels_and_tokens_cannot_change_inferred_edges():
    source = "pragma solidity ^0.5.0; contract C { uint x; function f() public { x=x+1; } }"
    base = graph_for(source)
    changed = copy.deepcopy(base)
    for _, d in changed.nodes(data=True):
        d["node_info_vulnerabilities"] = [{"lines":[99999]}]
        d["token"][:] = 999
    a, audit_a = augment_l2(base, {FILE: source})
    b, audit_b = augment_l2(changed, {FILE: source})
    assert relation_set(a) == relation_set(b)
    assert audit_a["evidence"] == audit_b["evidence"]
    assert_preserved(changed, b)


def test_missing_source_keeps_entire_graph_and_repeated_layer_rejected():
    base = graph_for(REENTRANCY)
    graph, audit = augment_l2(base, {})
    assert fingerprint(graph) == fingerprint(base)
    assert audit["files"][FILE]["diagnostics"][0]["reason"] == "missing_exact_source"
    graph, _ = augment_l2(base, {FILE: REENTRANCY})
    with pytest.raises(ValueError, match="without L2"):
        augment_l2(graph, {FILE: REENTRANCY})

