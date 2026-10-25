"""Prompt 2 semantic integration; parser-backed examples, NOT solc verified."""
import copy
import hashlib
import json
from pathlib import Path
import networkx as nx
import numpy as np
import pytest
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
from scripts.DFG.ddg_builder import DDGBuilder
from scripts.DFG.frontend import parse_source, text, walk
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration.pipeline import build_graph
from scripts.DFG.models import Unsupported
from scripts.DFG.projection import Projector
from scripts.DFG.state.stage_k.profile import SupportedSourceView
from scripts.DFG.dfg_v2.l1 import analyze_file, augment_l1
from scripts.DFG.dfg_v2.l1_cfg import V2CFGBuilder
from scripts.DFG.dfg_v2.l1_rd import solve_v2

FILE = "sample.sol"


def normalized(value):
    return " ".join(value.split())


def edges(source, facts):
    raw = source.encode("utf8")
    return {(normalized(raw[f.definition.anchor.start:f.definition.anchor.end].decode("utf8")),
             normalized(raw[f.use.anchor.start:f.use.anchor.end].decode("utf8")),
             f.symbol.rsplit(":", 1)[-1]) for f in facts}


def entry(source, name):
    view = SupportedSourceView(source, FILE)
    return normalized(text(source, next(n for n in view.functions
        if text(source, n.child_by_field_name("name")) == name)))


def ir_for(source, name):
    view = SupportedSourceView(source, FILE)
    fn = next(n for n in view.functions if text(source, n.child_by_field_name("name")) == name)
    return V2CFGBuilder(view, fn).build()


def graph_for(source):
    graph = nx.MultiDiGraph(generate_cfg_from_source(source, FILE))
    for index, (_, data) in enumerate(graph.nodes(data=True)):
        data["token"] = np.zeros(512, dtype=np.float32)
        data["node_info_vulnerabilities"] = [{"lines": [1]}] if index % 2 else None
    return graph


MY_BANK = """pragma solidity ^0.4.25;
contract MY_BANK {
 struct Holder { uint unlockTime; uint balance; }
 mapping(address => Holder) public Acc;
 uint public MinSum;
 function Collect(uint _am) public payable {
  var acc = Acc[msg.sender];
  if (acc.balance >= MinSum && acc.balance >= _am && now > acc.unlockTime) {
   if (msg.sender.call.value(_am)()) {
    acc.balance -= _am;
   }
  }
 }
}"""


def test_my_bank_collect_direct_facts_and_weak_write():
    facts, diagnostics, stats = analyze_file(MY_BANK, FILE)
    assert not DDGBuilder().analyze_source(MY_BANK, FILE).facts
    ir = ir_for(MY_BANK, "Collect")
    events = [e for b in ir.blocks.values() for e in b.events]
    write = next(e for e in events if e.kind == "assignment")
    symbol = next(s.id for s in ir.symbols.values() if s.name == "acc")
    assert write.weak_writes == (symbol,) and not write.writes
    out = edges(MY_BANK, facts)
    outer = next(n for n in walk(parse_source(MY_BANK, FILE).tree.root_node) if n.type == "if_statement")
    inner = next(n for n in walk(outer) if n.type == "if_statement" and n != outer)
    outer, inner = normalized(text(MY_BANK, outer)), normalized(text(MY_BANK, inner))
    assert ("var acc = Acc[msg.sender];", outer, "acc") in out
    assert ("var acc = Acc[msg.sender];", "acc.balance -= _am;", "acc") in out
    for use in (outer, inner, "acc.balance -= _am;"):
        assert (entry(MY_BANK, "Collect"), use, "_am") in out
    assert not any(d == "acc.balance -= _am;" and u == outer for d, u, _ in out)
    assert not any(name in ("Acc", "MinSum", "msg", "now") for _, _, name in out)
    assert stats["recovered"] == 1 and stats["routes"] == {"v2_aggregate": 1}
    assert stats["modifier_facts_dropped"] == 0


AGG = """pragma solidity ^0.5.0;
contract C {
 struct S { uint a; uint b; }
 uint[] data;
 function f() public returns (uint) {
  S memory s = S(1, 2);
  s.a = 3;
  uint y = s.b;
  s = S(4, 5);
  uint z = s.a;
  return y + z;
 }
 function g() public returns (uint) {
  uint[] storage arr = data;
  arr.push(1);
  uint n = arr.length;
  return n;
 }
}"""


def test_weak_field_write_retains_definition_and_whole_write_kills():
    facts, _, stats = analyze_file(AGG, FILE)
    out = edges(AGG, facts)
    assert ("S memory s = S(1, 2);", "uint y = s.b;", "s") in out
    assert ("s.a = 3;", "uint y = s.b;", "s") in out
    assert {d for d, u, v in out if u == "uint z = s.a;" and v == "s"} == {"s = S(4, 5);"}
    assert ("uint[] storage arr = data;", "uint n = arr.length;", "arr") in out
    assert ("arr.push(1);", "uint n = arr.length;", "arr") in out
    assert not any(v == "data" for _, _, v in out)
    assert stats["functions_supported"] == stats["recovered"] == 2


MODIFIER = """pragma solidity ^0.5.0;
contract C {
 address owner;
 modifier onlyOwner { require(msg.sender == owner); _; }
 function f(uint x) public onlyOwner returns (uint) { uint y = x; return y; }
 function g(string memory s, uint n) public returns (uint) { uint k = n; return k; }
 function zero() public {}
}"""


def test_modifier_and_string_parameter_recovery_preserve_zero_fact_legacy():
    facts, _, stats = analyze_file(MODIFIER, FILE)
    out = edges(MODIFIER, facts)
    assert (entry(MODIFIER, "f"), "uint y = x;", "x") in out
    assert ("uint y = x;", "return y;", "y") in out
    assert (entry(MODIFIER, "g"), "uint k = n;", "n") in out
    assert ("uint k = n;", "return k;", "k") in out
    records = {record["name"]: record for record in stats["functions"]}
    assert records["f"]["routes"] == ["v2_modifier"]
    assert records["g"]["routes"] == ["v2_aggregate"]
    assert records["zero"]["routes"] == ["legacy"]
    assert records["zero"]["facts"] == 0 and records["zero"]["legacy_reused"]
    assert stats["modifier_facts_dropped"] == 0
    assert not any("require" in use or "owner" == name for _, use, name in out)
    old = DDGBuilder().analyze_source(MODIFIER, FILE)
    assert not old.facts and old.stats["functions_supported"] == 1


@pytest.mark.parametrize("bad_body,modifiers", [
    ("uint y = n; assembly { let x := 1 } return y;", ""),
    ("uint y = (n = 2); return y;", ""),
    ("uint y = n; return y;", "a b"),
    ("uint y = n; return arr.push(1);", ""),
])
def test_late_function_fallback_publishes_no_partial_facts(bad_body, modifiers):
    source = """pragma solidity ^0.5.0; contract C {
     modifier a { _; } modifier b { _; }
     function bad(uint[] memory arr, uint n) public %s returns(uint) { %s }
     function good(uint n) public returns(uint) { uint z = n; return z; }
    }""" % (modifiers, bad_body)
    facts, _, stats = analyze_file(source, FILE)
    records = {x["name"]: x for x in stats["functions"]}
    assert records["bad"]["status"] == "fallback"
    assert not records["bad"]["partial_facts_published"]
    assert not any(f.use.function == records["bad"]["function"] for f in facts)
    assert records["good"]["routes"] == ["legacy"]
    assert ("uint z = n;", "return z;", "z") in edges(source, facts)


def test_version_and_inheritance_routes_record_actual_recovery():
    source = """pragma solidity >=0.5.0;
    contract Base {} contract C is Base {
     function f(uint n) public returns(uint) { uint z=n; revert(); return z; }
    }"""
    facts, _, stats = analyze_file(source, FILE)
    record = stats["functions"][0]
    assert record["old_reason"] == "inheritance_binding_not_supported"
    assert "v2_inheritance" in record["routes"]
    assert not any(use == "return z;" for _, use, _ in edges(source, facts))
    multi = source.replace("pragma solidity >=0.5.0;", "pragma solidity >=0.5.0; pragma solidity <0.9.0;")
    facts, _, stats = analyze_file(multi, FILE)
    assert "v2_version" in stats["functions"][0]["routes"]
    assert "v2_inheritance" in stats["functions"][0]["routes"]


def test_metadata_is_sha_bound_and_does_not_change_legacy_successes(tmp_path):
    source = """pragma solidity >=0.4.0 <0.9.0; contract C {
     function f(uint x) public returns(uint) { uint y=x; return y; }
    }"""
    # Synthetic trusted-record fixture only; no compiler was run.
    origin = tmp_path / FILE
    origin.write_text(source)
    csv_path = tmp_path / "versions.csv"
    csv_path.write_text("file,compiled version\n" + FILE + ",0.5.17\n")
    metadata = {"version": "0.5.17", "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "source_path": str(origin), "csv_path": str(csv_path),
                "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(), "row_file": FILE}
    facts, _, stats = analyze_file(source, FILE, metadata)
    assert stats["functions_supported"] == 1 and stats["routes"] == {"v2_version": 1}
    wrong = dict(metadata, source_sha256="0"*64)
    facts, _, stats = analyze_file(source, FILE, wrong)
    assert not facts and stats["functions_supported"] == 0
    # New frontend failure cannot erase old success (including zero-fact functions).
    ordinary = "pragma solidity ^0.5.0; contract C { function good(uint n) public returns(uint) { return n; } function bad(string memory s) public {} }"
    old = DDGBuilder().analyze_source(ordinary, FILE)
    facts, _, stats = analyze_file(ordinary, FILE, wrong)
    assert facts == old.facts
    assert stats["functions_supported"] == 1
    assert stats["v2_view_error"]


@pytest.mark.parametrize("source", [MY_BANK, AGG, MODIFIER])
def test_exact_projection_input_preserved_and_evidence_indices(source):
    graph = graph_for(source)
    before = fingerprint(graph)
    legacy, legacy_audit = build_graph(graph, {FILE: source}, profile="scalar")
    enhanced, audit = augment_l1(graph, {FILE: source})
    assert fingerprint(graph) == before
    assert fingerprint(enhanced, exclude_ddg=True) == before
    expected = {(s, t) for s, t, d in legacy.edges(data=True) if d.get("edge_type") == "DATA_DEF_USE"}
    legacy_pairs = {(e["source"], e["target"]) for e in audit["evidence"]
                    if e["analysis_path"] == "legacy" and not e["self_fact"]}
    assert legacy_pairs == expected
    for s, t, d in enhanced.edges(data=True):
        if d.get("edge_type") != "DATA_DEF_USE":
            continue
        assert d["dfg_v2_version"] == "dfg-v2" and d["routes"] and s != t
        assert d["ddg_fact_indices"]
        for i in d["ddg_fact_indices"]:
            ev = audit["evidence"][i]
            assert (ev["source"], ev["target"]) == (s, t)
            assert set(ev["routes"]) <= set(d["routes"])
    a = Projector(graph, parse_source(source, FILE))
    b = Projector(graph, SupportedSourceView(source, FILE))
    assert a.by_ast == b.by_ast
    json.dumps(audit)


def test_all_original_fixture_edges_and_legacy_fact_order_unchanged():
    fixtures = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
    paths = sorted(fixtures.glob("*.sol"))
    assert paths
    for path in paths:
        source = path.read_text()
        old = DDGBuilder().analyze_source(source, FILE)
        facts, _, stats = analyze_file(source, FILE)
        assert facts[:len(old.facts)] == old.facts
        graph = graph_for(source)
        old_graph, _ = build_graph(graph, {FILE: source}, profile="scalar")
        new_graph, audit = augment_l1(graph, {FILE: source})
        old_edges = {(s, t) for s, t, d in old_graph.edges(data=True) if d.get("edge_type") == "DATA_DEF_USE"}
        new_edges = {(s, t) for s, t, d in new_graph.edges(data=True) if d.get("edge_type") == "DATA_DEF_USE"}
        assert old_edges <= new_edges
        assert {(ev["source"], ev["target"]) for ev in audit["evidence"]
                if ev["analysis_path"] == "legacy" and not ev["self_fact"]} == old_edges


def test_missing_source_retains_graph_and_invalid_inputs_fail():
    graph = graph_for(MODIFIER)
    enhanced, audit = augment_l1(graph, {})
    assert fingerprint(graph) == fingerprint(enhanced)
    assert audit["files"][FILE]["diagnostics"]
    for invalid in (True, 0, -1):
        with pytest.raises(ValueError):
            augment_l1(graph, {FILE: MODIFIER}, max_iterations=invalid)
    enhanced, _ = augment_l1(graph, {FILE: MODIFIER})
    with pytest.raises(ValueError, match="unenhanced"):
        augment_l1(enhanced, {FILE: MODIFIER})


def test_failed_projection_does_not_guess_nearby_node():
    graph = graph_for(AGG)
    for _, data in graph.nodes(data=True):
        if data.get("node_type") == "expression_statement":
            data["code"] = "not_the_source"
            break
    before = fingerprint(graph)
    enhanced, audit = augment_l1(graph, {FILE: AGG})
    assert fingerprint(enhanced) == before
    assert any(d["kind"] == "projection_fallback" for d in audit["files"][FILE]["diagnostics"])


def test_labels_and_features_do_not_drive_l1_edges():
    graph = graph_for(AGG)
    changed = copy.deepcopy(graph)
    for _, data in changed.nodes(data=True):
        data["token"] = np.full(512, 7, dtype=np.float32)
        data["node_info_vulnerabilities"] = None
    first, a = augment_l1(graph, {FILE: AGG})
    second, b = augment_l1(changed, {FILE: AGG})
    pairs = lambda g: {(s, t) for s, t, d in g.edges(data=True) if d.get("edge_type") == "DATA_DEF_USE"}
    assert pairs(first) == pairs(second)
    assert a["evidence"] == b["evidence"]


def test_constructor_copy_provenance_and_inherited_semantics():
    from scripts.DFG.semantic_cfg import CFGBuilder
    from scripts.DFG.state.stage_j.analyzer import StageJCFGBuilder
    root = Path(__file__).resolve().parents[4]
    expected = hashlib.sha256((root / "scripts/DFG/state/stage_j/analyzer.py").read_bytes()).hexdigest()
    assert expected in (root / "scripts/DFG/dfg_v2/l1_cfg.py").read_text()
    assert V2CFGBuilder.build is StageJCFGBuilder.build
    assert V2CFGBuilder.statement is CFGBuilder.statement
    assert V2CFGBuilder.sequence is CFGBuilder.sequence


def test_unnamed_aggregate_acceptance_is_not_lost_from_route_audit():
    source = """pragma solidity ^0.5.0; contract C {
     function name() public returns(string memory) { return "name"; }
     function accept(string memory) public returns(uint) { return 1; }
    }"""
    facts, _, stats = analyze_file(source, FILE)
    assert stats["legacy_supported"] == 0 and stats["recovered"] == 2
    assert all(rec["routes"] == ["v2_aggregate"] for rec in stats["functions"])
    assert not facts  # Unnamed accepted types do not invent variable identities.


def test_prefix_ast_compatibility_recovery_has_explicit_route():
    source = """pragma solidity ^0.5.0; contract C {
     uint[] data;
     function remove(uint i) public { delete data[i]; }
    }"""
    facts, _, stats = analyze_file(source, FILE)
    assert stats["recovered"] == 1
    assert stats["functions"][0]["old_reason"] == "Nested delete expression"
    assert stats["functions"][0]["routes"] == ["v2_access_shape"]
    assert (entry(source, "remove"), "delete data[i];", "i") in edges(source, facts)
    assert not any(f.symbol.endswith(":data") for f in facts)


def test_prompt6b_call_option_recovery_preserves_legacy_facts_and_hcg():
    source = """pragma solidity ^0.6.12;
    contract C {
      address target;
      function recovered(uint value) public {
        uint x = 1;
        target.call{value: x}("");
      }
      function stable(uint n) public returns(uint) { uint y=n; return y; }
    }"""
    old = DDGBuilder().analyze_source(source, FILE)
    facts, _, stats = analyze_file(source, FILE)
    records = {record["name"]: record for record in stats["functions"]}
    recovered = records["recovered"]
    assert recovered["old_status"] == "fallback"
    assert recovered["old_reason"] == "Unsupported expression: struct_expression"
    assert recovered["status"] == "supported" and recovered["routes"] == ["v2_retry"]
    assert recovered["recovered"] and not recovered["legacy_reused"]
    assert records["stable"]["routes"] == ["legacy"]
    assert facts[:len(old.facts)] == old.facts
    expected = ('uint x = 1;', 'target.call{value: x}("");', "x")
    actual = edges(source, facts)
    assert expected in actual
    assert not any(variable == "value" for _, _, variable in actual)
    graph = graph_for(source)
    before = fingerprint(graph)
    enhanced, audit = augment_l1(graph, {FILE: source})
    assert fingerprint(graph) == before
    assert fingerprint(enhanced, exclude_ddg=True) == before
    evidence = [item for item in audit["evidence"] if item["analysis_path"] == "v2"]
    assert evidence and all(item["routes"] == ["v2_retry"] for item in evidence)
    assert all(enhanced.has_edge(item["source"], item["target"])
               for item in evidence if not item["self_fact"])


def test_prompt6b_unsupported_nested_option_retains_function_without_partial_facts():
    source = """pragma solidity ^0.6.12;
    contract C {
      function bad(address t, uint x) public {
        uint y = x;
        t.call{value: x++}("");
      }
      function stable(uint n) public returns(uint) { return n; }
    }"""
    facts, _, stats = analyze_file(source, FILE)
    records = {record["name"]: record for record in stats["functions"]}
    bad = records["bad"]
    assert bad["status"] == "fallback"
    assert "Nested expression write" in bad["reason"]
    assert not bad["partial_facts_published"]
    assert not any(fact.use.function == bad["function"] for fact in facts)
    assert records["stable"]["status"] == "supported"
    graph = graph_for(source)
    before = fingerprint(graph)
    enhanced, _ = augment_l1(graph, {FILE: source})
    assert fingerprint(graph) == before
    assert fingerprint(enhanced, exclude_ddg=True) == before


def test_prompt6b_new_contract_option_function_recovers_by_v2_retry():
    source = """pragma solidity ^0.6.12;
    contract D { constructor(uint n) public payable {} }
    contract C {
      function f(uint amount, uint n, bytes32 seed) public {
        new D{value: amount, salt: seed}(n);
      }
    }"""
    facts, _, stats = analyze_file(source, FILE)
    record = next(item for item in stats["functions"] if item["name"] == "f")
    assert record["old_status"] == "fallback"
    assert record["status"] == "supported" and record["routes"] == ["v2_retry"]
    assert record["recovered"]
    target = "new D{value: amount, salt: seed}(n);"
    # The existing entry() helper assumes every function has a name; a
    # constructor has no name. Select this function by its recorded byte ID.
    view = SupportedSourceView(source, FILE)
    function = next(node for node in view.functions if node.start_byte == record["start"])
    function_text = normalized(text(source, function))
    assert {(definition, use, variable) for definition, use, variable in edges(source, facts)
            if use == target} == {(function_text, target, variable)
                                 for variable in ("amount", "n", "seed")}
    graph = graph_for(source)
    before = fingerprint(graph)
    enhanced, _ = augment_l1(graph, {FILE: source})
    assert fingerprint(graph) == before
    assert fingerprint(enhanced, exclude_ddg=True) == before
