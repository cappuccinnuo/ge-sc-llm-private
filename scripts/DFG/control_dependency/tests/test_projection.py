"""Projection regressions: parser robustness fixtures, not compiler-verified."""
import copy
from dataclasses import replace
from types import SimpleNamespace
import networkx as nx
import pytest
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
from scripts.DFG.frontend import span, walk
from scripts.DFG.state.stage_k.profile import SupportedSourceView
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.control_dependency.models import ControlFact, ControlResult
from scripts.DFG.control_dependency.projection import project_results, materialize, assert_preserved, RELATION

SOURCE = """pragma solidity ^0.5.17;
contract C {
 function f(bool ok, uint x) public returns(uint) {
  require(ok); x = 1; return x;
 }
}
"""


def assets(source=SOURCE):
    graph = generate_cfg_from_source(source, "case.sol")
    view = SupportedSourceView(source, "case.sol")
    nodes = list(walk(view.tree.root_node))
    def anchor(code):
        found = [n for n in nodes if source.encode()[n.start_byte:n.end_byte].decode() == code
                 and n.type in ("expression_statement", "return_statement")]
        assert len(found) == 1
        return span("case.sol", found[0])
    fact = ControlFact("case.sol:22", view.sha256, anchor("require(ok);"), anchor("x = 1;"),
                       "pass", ("b0", "b1"), ("b1",), {"binding": "builtin"})
    result = ControlResult(fact.function, "analyzed", facts=[fact])
    for n,d in graph.nodes(data=True):
        d["node_info_vulnerabilities"] = [{"lines": [1000+n]}]
        d["token"] = [n % 7, 0, 1]
    return graph, view, fact, result


def test_exact_existing_ids_and_all_attributes_preserved():
    graph, view, fact, result = assets()
    graph = nx.relabel_nodes(graph, {n: 1000+7*i for i,n in enumerate(graph)})
    old = fingerprint(graph)
    evidence, report = project_results(graph, view, [result])
    output, inv, context = materialize(graph, evidence)
    assert evidence and report["projected_facts"] == 1
    assert inv["node_attributes_exact"] and inv["base_edges_exact"]
    assert fingerprint(graph) == old
    assert set(output) == set(graph)
    proof = evidence[0]
    assert graph.nodes[proof["source_node"]]["code"] == "require(ok);"
    assert graph.nodes[proof["target_node"]]["code"] == "x = 1;"


def test_same_endpoints_original_and_ddg_relations_coexist():
    graph, view, fact, result = assets()
    evidence, _ = project_results(graph, view, [result])
    s,t = evidence[0]["source_node"], evidence[0]["target_node"]
    for rel in ("next", "DATA_DEF_USE", "STATE_DEF_USE", "STATE_ACCESS_ORDER", "EXTERNAL_CALL_BEFORE_STATE_WRITE"):
        graph.add_edge(s,t,edge_type=rel, old_attr=[1,2])
    output, inv, context = materialize(graph, evidence)
    assert inv["added_control_edges"] == 1
    assert context["existing_direct_pair_new_relation"] == 1
    assert {d["edge_type"] for d in output[s][t].values()} >= {RELATION, "next", "STATE_DEF_USE"}
    assert_preserved(graph, output)


def test_same_relation_dedup_retains_multiple_function_contexts():
    graph, view, fact, result = assets()
    other = replace(fact, function="case.sol:100")
    evidence, _ = project_results(graph, view, [result, ControlResult(other.function, "analyzed", facts=[other])])
    output, inv, context = materialize(graph, evidence)
    edges = [(s,t,d) for s,t,d in output.edges(data=True) if d["edge_type"] == RELATION]
    assert len(edges) == 1 and len(edges[0][2]["control_evidence_indices"]) == 2
    assert edges[0][2]["control_function_contexts"] == sorted([fact.function,other.function])
    assert context["pairs_with_multiple_function_contexts"] == 1


def test_function_fallback_discards_even_stale_partial_facts():
    graph, view, fact, result = assets()
    result.status = "function_fallback"
    evidence, report = project_results(graph, view, [result])
    output, inv, _ = materialize(graph, evidence)
    assert not evidence and fingerprint(output) == fingerprint(graph)
    assert report["functions"][0]["discarded_fallback_facts"] == 1


def test_bad_fact_after_good_fact_rolls_back_whole_function():
    graph, view, fact, result = assets()
    result.facts.append(replace(fact, source_sha256="wrong"))
    evidence, report = project_results(graph, view, [result])
    assert not evidence
    assert report["functions"][0]["status"] == "function_projection_fallback"
    assert report["functions"][0]["discarded_partial_facts"] == 1


def test_missing_anchor_has_no_nearest_line_guess():
    graph, view, fact, result = assets()
    victim = next(n for n,d in graph.nodes(data=True) if d["code"] == "x = 1;")
    graph.remove_node(victim)
    evidence, report = project_results(graph, view, [result])
    assert not evidence
    assert report["functions"][0]["diagnostics"][0]["kind"] == "projection_missing"


def test_labels_and_features_do_not_select_edges():
    graph, view, fact, result = assets()
    a,_ = project_results(graph, view, [result])
    for _,data in graph.nodes(data=True):
        data["node_info_vulnerabilities"] = None
        data["token"] = [9999]
    b,_ = project_results(graph, view, [result])
    assert a == b


def test_reject_double_augmentation():
    graph, view, fact, result = assets()
    proof,_ = project_results(graph, view, [result])
    output,_,_ = materialize(graph, proof)
    with pytest.raises(ValueError, match="without an existing"):
        materialize(output, proof)


def test_pipeline_disabled_and_missing_source_are_exact():
    from scripts.DFG.control_dependency.pipeline import augment
    graph,_,_,_ = assets()
    for use_control,sources in ((False,{"case.sol": SOURCE}), (True,{})):
        output,audit = augment(graph,sources,use_control=use_control)
        assert fingerprint(output) == fingerprint(graph)
        assert not audit["evidence"]


def test_pipeline_keeps_supported_function_when_other_falls_back(monkeypatch):
    from scripts.DFG.control_dependency import pipeline
    graph,view,fact,result = assets()
    failed = ControlResult("case.sol:999", "function_fallback", facts=[replace(fact,function="case.sol:999")],
                           diagnostics=[{"reason":"unknown binding"}])
    monkeypatch.setattr(pipeline, "analyze_view", lambda v: [result, failed])
    output,audit = pipeline.augment(graph,{"case.sol":SOURCE})
    assert audit["invariants"]["added_control_edges"] == 1
    assert {x["function"] for x in audit["evidence"]} == {fact.function}
    assert audit["function_status_counts"] == {"analyzed":1,"function_fallback":1}


def test_model_context_uses_reflected_ordinary_and_forward_guard_edges():
    from scripts.DFG.experiments.guard_extension.build import model_context
    base = nx.MultiDiGraph()
    for n in (1,2,3,4):
        base.add_node(n,node_type="statement",source_file="x.sol")
    base.add_edge(1,2,edge_type="next")
    base.add_edge(3,2,edge_type="next")
    out = copy.deepcopy(base)
    out.add_edge(1,3,edge_type=RELATION)
    report = model_context(base,out)
    assert report["actual_adapter_tensors_used"]
    assert report["new_control_edges_outside_baseline_two_hops"] == 0
    assert report["new_two_layer_pairs"] == 0
    out.add_edge(3,4,edge_type=RELATION)
    report = model_context(base,out)
    assert report["new_control_edges_outside_baseline_two_hops"] == 1
    assert report["new_two_layer_pairs"] == 3
    assert report["new_context_target_nodes"] == 1
