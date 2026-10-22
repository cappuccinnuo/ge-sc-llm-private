"""Source/parser regression fixtures; no Solidity compilation is claimed."""
import copy
import hashlib
from pathlib import Path

import pytest

from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
from scripts.DFG.control_dependency import analysis as old_analysis
from scripts.DFG.control_dependency import pipeline as old_pipeline
from scripts.DFG.control_dependency.cfg import ControlCFGBuilder
from scripts.DFG.control_dependency.projection import assert_preserved
from scripts.DFG.frontend import text
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration import control_v2 as new
from scripts.DFG.state.stage_k.profile import SupportedSourceView


def source(body, helper="", pragma="^0.4.24"):
    return ("pragma solidity " + pragma + "; contract C { uint x; " + helper +
            " function f(bool ok,address to,uint y) public { " + body + " } }")


def analyze(src, implementation=new):
    view = SupportedSourceView(src, "case.sol")
    fn = next(n for n in view.functions if n.child_by_field_name("name") is not None
              and text(src, n.child_by_field_name("name")) == "f")
    result = next(r for r in implementation.analyze_view(view)
                  if r.function == "case.sol:" + str(fn.start_byte))
    return view, result


def pairs(view, result):
    return {(view.raw[f.controller.start:f.controller.end].decode(),
             view.raw[f.controlled.start:f.controlled.end].decode(), f.branch)
            for f in result.facts}


@pytest.mark.parametrize("receiver,helper", [
    ("address(unresolved())", ""),
    ("address(target())", "function target() internal returns(address){revert();}"),
    ("address(uint160(target()))", "function target() internal returns(address){return msg.sender;}"),
])
def test_original_receiver_gap_reproduced_new_function_has_no_residual(receiver, helper):
    src = source('require(ok); ' + receiver + '.call(""); x=1;', helper)
    _, before = analyze(src, old_analysis)
    _, after = analyze(src)
    # Same input fails the intended safety requirement in the frozen old module.
    assert before.status == "analyzed" and len(before.facts) == 2
    assert after.status == "function_fallback" and after.ir is None and after.facts == []
    assert "receiver evaluation" in after.diagnostics[0]["reason"]
    assert after.diagnostics[0]["partial_control_facts_published"] is False


@pytest.mark.parametrize("body", [
    'if(ok){address(target()).call("");} x=1;',
    'if(address(target()).send(y)){x=1;}',
    'require(ok); address(target()).transfer(y); x=1;',
    'require(ok); address(target()).call.value(y); x=1;',
])
def test_receiver_calls_rejected_in_control_and_call_configuration_contexts(body):
    src = source(body, "function target() internal returns(address){return msg.sender;}")
    _, result = analyze(src)
    assert result.status == "function_fallback" and result.ir is None and not result.facts
    assert "receiver evaluation" in result.diagnostics[0]["reason"]


@pytest.mark.parametrize("receiver", ["address(y++)", "address(y=1)", "address(y+=1)"])
def test_receiver_side_effects_rejected_as_parser_robustness_cases(receiver):
    _, result = analyze(source('require(ok); '+receiver+'.call("");x=1;'))
    assert result.status == "function_fallback" and result.ir is None and not result.facts
    assert "receiver evaluation" in result.diagnostics[0]["reason"]


@pytest.mark.parametrize("receiver", ["to", "msg.sender", "address(y)", "address(uint160(y))"])
def test_ordinary_receivers_preserve_old_control_facts(receiver):
    src = source('require(ok); '+receiver+'.call("");x=1;')
    ov, old = analyze(src, old_analysis)
    nv, result = analyze(src)
    assert old.status == result.status == "analyzed"
    assert pairs(ov, old) == pairs(nv, result)
    assert len(result.facts) == 2
    assert result.ir.evidence["version"] == new.VERSION


@pytest.mark.parametrize("body", ['require(ok); unresolved();x=1;',
                                   'require(ok);to.call(unresolved());x=1;'])
def test_existing_unknown_and_nested_argument_fallback_preserved(body):
    _, result = analyze(source(body))
    assert result.status == "function_fallback" and result.ir is None and not result.facts


def test_modifier_metadata_clearly_distinguishes_legacy_profile_from_control_facts():
    src = "pragma solidity ^0.4.24; contract C { uint x; modifier m(){require(x>0);_;} function f() public m {x=1;} }"
    ov, before = analyze(src, old_analysis)
    nv, after = analyze(src)
    assert before.facts and pairs(ov, before) == pairs(nv, after)
    old_context = before.facts[0].evidence["modifier_context"]
    new_context = after.facts[0].evidence["modifier_context"]
    assert old_context["control_dependence_edges"] is False
    assert "control_dependence_edges" not in new_context
    assert new_context["legacy_prefix_profile_control_dependence_edges"] is False
    assert new_context["control_dependence_analysis_version"] == new.VERSION


def test_function_fallback_keeps_good_function_and_all_hcg_content():
    src = source('require(ok);address(unresolved()).call("");x=1;',
                 "function good(bool ok) public {require(ok);x=2;}")
    graph = generate_cfg_from_source(src, "case.sol")
    for node, data in graph.nodes(data=True):
        data["token"] = [node % 13, 2, 0]
        data["node_info_vulnerabilities"] = [{"lines": [42]}] if node % 2 else None
    old = fingerprint(graph)
    result, audit = new.augment(graph, {"case.sol": src})
    view, failed = analyze(src)
    assert not [e for e in audit["evidence"] if e["function"] == failed.function]
    assert audit["function_status_counts"] == {"analyzed": 1, "function_fallback": 1}
    assert audit["invariants"]["added_control_edges"] == 1
    assert fingerprint(graph) == old
    assert_preserved(graph, result)
    off, _ = new.augment(graph, {}, use_control=False)
    assert fingerprint(off) == old
    missing, _ = new.augment(graph, {})
    assert fingerprint(missing) == old


def test_no_monkeypatch_and_old_source_hashes_stay_identical():
    old_builder = old_analysis.analyze_view.__globals__["ControlCFGBuilder"]
    old_analyze = old_pipeline.augment.__globals__["analyze_view"]
    paths = [Path(old_analysis.__file__), Path(old_pipeline.__file__)]
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    analyze(source('require(ok);address(unresolved()).call("");x=1;'))
    assert old_builder is ControlCFGBuilder
    assert old_analysis.analyze_view.__globals__["ControlCFGBuilder"] is old_builder
    assert old_pipeline.augment.__globals__["analyze_view"] is old_analyze
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths] == hashes
    assert new.analyze_view.__code__ is old_analysis.analyze_view.__code__
    assert new._augment_template.__code__ is old_pipeline.augment.__code__


def test_control_iteration_bound_falls_back_without_partial_graph_facts():
    src = source("require(ok);x=1;")
    graph = generate_cfg_from_source(src,"case.sol")
    before = fingerprint(graph)
    result,audit = new.augment(graph,{"case.sol":src},max_iterations=1)
    assert audit["effective_max_iterations"] == audit["requested_max_iterations"] == 1
    assert audit["function_status_counts"] == {"function_fallback": 1}
    assert audit["evidence"] == [] and fingerprint(result) == before
    record = audit["files"]["case.sol"]["functions"][0]
    assert record["semantic_facts"] == record["projected_facts"] == 0
    assert "iteration limit" in record["diagnostics"][0]["reason"]
    assert fingerprint(graph) == before


def test_control_default_wrapper_keeps_previous_default_graph_and_facts():
    src = source("require(ok);x=1;")
    graph = generate_cfg_from_source(src,"case.sol")
    previous,old_audit = new._augment_template(graph,{"case.sol":src})
    current,audit = new.augment(graph,{"case.sol":src})
    assert fingerprint(previous) == fingerprint(current)
    assert old_audit["evidence"] == audit["evidence"]
    assert audit["effective_max_iterations"] == 100000
    disabled,off_audit = new.augment(graph,{},use_control=False,max_iterations=1)
    assert fingerprint(disabled) == fingerprint(graph)
    assert off_audit["effective_max_iterations"] is None


@pytest.mark.parametrize("limit", [0, -1, True, 1.2, "3"])
def test_control_invalid_iteration_bound_rejected(limit):
    with pytest.raises(ValueError,match="positive integer"):
        new.augment(None,{},max_iterations=limit)
