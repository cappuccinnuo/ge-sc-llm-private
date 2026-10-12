"""B1 requested read-only projection audit; no changes to production projection."""
from scripts.DFG.ddg_builder import DDGBuilder
from scripts.DFG.projection import Projector
from scripts.DFG.pipeline import augment
from scripts.DFG.graph_audit import fingerprint, assert_augmented
from scripts.DFG.tests.test_call_binding import fact_codes
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source


def test_missing_write_node_still_kills_old_definition_before_projection():
    s = "pragma solidity ^0.5.17; contract C {function f(uint p) public returns(uint){uint x=p;x=2;return x;}}"
    g = generate_cfg_from_source(s, "a.sol")
    missing = next(n for n, d in g.nodes(data=True) if d["code"] == "x=2;")
    g.remove_node(missing)  # Test fixture simulates a frozen HCG lacking this statement.
    r = DDGBuilder().analyze_source(s, "a.sol")
    assert ("x=2;", "return x;") in fact_codes(s, r)
    assert ("uint x=p;", "return x;") not in fact_codes(s, r)
    out, audit = augment(g, {"a.sol": s})
    assert_augmented(g, out)
    assert any(d["kind"] == "projection_missing" for d in audit["files"]["a.sol"]["diagnostics"])
    assert not any(out.nodes[u]["code"] == "uint x=p;" and out.nodes[v]["code"] == "return x;"
                   for u, v, d in out.edges(data=True) if d["edge_type"] == "DATA_DEF_USE")


def test_missing_if_node_does_not_flatten_branch_semantics():
    s = "pragma solidity ^0.5.17; contract C {function f(uint p,bool b) public returns(uint){uint x=p;if(b){x=2;}else{x=3;}return x;}}"
    g = generate_cfg_from_source(s, "a.sol")
    g.remove_node(next(n for n, d in g.nodes(data=True) if d["node_type"] == "if"))
    r = DDGBuilder().analyze_source(s, "a.sol")
    expected = {("x=2;", "return x;"), ("x=3;", "return x;")}
    assert expected <= fact_codes(s, r)
    assert ("uint x=p;", "return x;") not in fact_codes(s, r)
    out, audit = augment(g, {"a.sol": s})
    assert_augmented(g, out)
    pairs = {(out.nodes[u]["code"], out.nodes[v]["code"]) for u, v, d in out.edges(data=True)
             if d["edge_type"] == "DATA_DEF_USE"}
    assert expected <= pairs
    assert any(d["kind"] == "projection_missing" and d["role"] == "if_statement"
               for d in audit["files"]["a.sol"]["diagnostics"])


def test_uninterpretable_semantics_retain_hcg_without_partial_ddg():
    s = "pragma solidity ^0.5.17; contract C {function f(uint p) public returns(uint){uint x=p;uint y=x;assembly {let z := 1}return y;}}"
    g = generate_cfg_from_source(s, "a.sol")
    out, audit = augment(g, {"a.sol": s})
    assert fingerprint(g) == fingerprint(out)
    assert not audit["evidence"]
    assert any(d["kind"] == "function_fallback" for d in audit["files"]["a.sol"]["diagnostics"])
