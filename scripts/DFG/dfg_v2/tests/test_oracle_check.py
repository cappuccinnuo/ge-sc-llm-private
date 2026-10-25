"""Adversarial checks for the Oracle verifier, not expected-generation tests."""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.DFG.dfg_v2 import DATA_DEF_USE, ENV_FLOW
from scripts.DFG.dfg_v2.oracle_check import (
    DEFAULT_ORACLE, ConstantEncoder, apply_classifications, compare, dump,
    fact_key, graph_for, normalize, observed_facts, run_case, unique_endpoints,
    validate_expected, verify_seal,
)
from scripts.DFG.dfg_v2.pipeline import build

SOURCE = """pragma solidity 0.5.17;
contract OracleTest {
 function run() public returns (uint) {
  uint a = 1;
  a = 2;
  uint b = a;
  return b;
 }
}
"""


def item(src, dst, var="a"):
    return dict(relation=DATA_DEF_USE, src=src, dst=dst, var=var)


def expectation(source_path):
    return dict(source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
                edges=[item("a = 2;", "uint b = a;"),
                       item("uint b = a;", "return b;", "b")],
                absent=[item("uint a = 1;", "uint b = a;")],
                counts={"unmapped_env": 0, "env_nodes": {}})


def simple(tmp_path):
    path = tmp_path / "test.sol"
    path.write_text(SOURCE)
    graph = graph_for(SOURCE, path.name)
    texts = unique_endpoints(graph, SOURCE, path.name)
    out, audit = build(graph, {path.name: SOURCE}, {}, ("L1", "L2", "L3"),
                       token_encoder=ConstantEncoder())
    return path, graph, out, audit, texts


def test_sealed_expectations_are_committed():
    seal = verify_seal()
    assert len(seal["files"]) in (36, 38, 40)


def test_real_baseline_matches_handwritten_small_fixture(tmp_path):
    path, _, out, audit, texts = simple(tmp_path)
    actual, counts = observed_facts(out, audit, texts)
    assert compare(expectation(path), actual, counts)["passed"]


def test_deleted_graph_edge_is_reported(tmp_path):
    path, _, out, audit, texts = simple(tmp_path)
    src, dst, key = next((s, t, k) for s, t, k, d in out.edges(keys=True, data=True)
                        if d["edge_type"] == DATA_DEF_USE)
    out.remove_edge(src, dst, key)
    actual, counts = observed_facts(out, audit, texts)
    report = compare(expectation(path), actual, counts)
    assert sum(i["kind"] == "missing" for i in report["issues"]) == 1
    assert not report["passed"]


def test_extra_graph_edge_and_absent_violation_reported(tmp_path):
    path, _, out, audit, texts = simple(tmp_path)
    by_text = {value: key for key, value in texts.items()}
    src, dst = by_text["uint a = 1;"], by_text["uint b = a;"]
    i = len(audit["layers"]["L1"]["evidence"])
    audit["layers"]["L1"]["evidence"].append(
        dict(source=src, target=dst, symbol="test.sol:decl:a"))
    out.add_edge(src, dst, edge_type=DATA_DEF_USE, ddg_fact_indices=[i])
    actual, counts = observed_facts(out, audit, texts)
    report = compare(expectation(path), actual, counts)
    assert [i["kind"] for i in report["issues"]] == ["unexpected", "absent_violated"]
    assert report["absent_violations"] == 1


def test_same_statement_text_in_distinct_functions_rejected():
    source = """pragma solidity 0.5.17; contract C {
      function f() public returns(uint) { uint x = 1; return x; }
      function g() public returns(uint) { uint x = 1; return x; }
    }"""
    graph = graph_for(source, "duplicate.sol")
    with pytest.raises(ValueError, match="Nonunique"):
        unique_endpoints(graph, source, "duplicate.sol")


def test_encoder_cannot_change_relation_facts(tmp_path):
    source = SOURCE.replace("uint a = 1;", "uint a = block.number;")
    path = tmp_path / "env.sol"
    path.write_text(source)
    expected = expectation(path)
    expected["edges"].append(dict(relation=ENV_FLOW, src="ENV:block.number",
                                  dst="uint a = block.number;", var="block.number"))
    expected["absent"][0]["src"] = "uint a = block.number;"
    expected["counts"]["env_nodes"] = {"block.number": 1}
    first, a = run_case(path, expected, ConstantEncoder(0))
    second, b = run_case(path, expected, ConstantEncoder(17000))
    assert first["passed"] and second["passed"]
    assert first["observed"] == second["observed"]
    assert first["counts"] == second["counts"]
    for layer in ("L1", "L2", "L3"):
        assert a["layers"][layer]["evidence"] == b["layers"][layer]["evidence"]


@pytest.mark.parametrize("damage", ["sha", "duplicate", "contradiction", "relation", "count"])
def test_bad_expected_rejected(tmp_path, damage):
    path = tmp_path / "test.sol"
    path.write_text(SOURCE)
    expected = expectation(path)
    if damage == "sha":
        expected["source_sha256"] = "0" * 64
    elif damage == "duplicate":
        expected["edges"].append(copy.deepcopy(expected["edges"][0]))
    elif damage == "contradiction":
        expected["absent"].append(copy.deepcopy(expected["edges"][0]))
    elif damage == "relation":
        expected["edges"][0]["relation"] = "REV_DATA_DEF_USE"
    else:
        expected["counts"]["env_nodes"] = {"x": -1}
    with pytest.raises(ValueError):
        validate_expected(expected, path)


def test_precision_recall_report_undefined_denominators():
    empty = dict(edges=[], absent=[], counts={})
    result = compare(empty, set(), {})
    assert result["passed"]
    assert result["metrics"][DATA_DEF_USE]["precision"] is None
    assert result["metrics"][DATA_DEF_USE]["recall"] is None


def test_count_mismatch_is_not_hidden():
    result = compare(dict(edges=[], absent=[], counts={"unmapped_env": 1}),
                     set(), {"unmapped_env": 0})
    assert not result["passed"] and result["issues"][0]["kind"] == "count_mismatch"


def test_classification_requires_all_issues_and_expectation_rule():
    report = {"cases": [{"issues": [{"id": "x:0"}]}]}
    digest = hashlib.sha256((json.dumps(report, indent=2, sort_keys=True,
                         ensure_ascii=False) + "\n").encode("utf8")).hexdigest()
    with pytest.raises(ValueError, match="Missing"):
        apply_classifications(report, {"oracle_report_sha256": digest, "issues": {}})
    record = {"category": "expectation_error", "reason": "source expectation invalid"}
    with pytest.raises(ValueError, match="language"):
        apply_classifications(report, {"oracle_report_sha256": digest, "issues": {"x:0": record}})
    record["language_rule"] = "cited official source, with specific rule"
    result = apply_classifications(report, {"oracle_report_sha256": digest, "issues": {"x:0": record}})
    assert result["all_classified"]


def test_normalize_whitespace_only():
    assert normalize("  a =\n 1; ") == "a = 1;"
    assert normalize("a=1;") != normalize("a = 1;")


def test_classification_rejects_wrong_report_binding():
    with pytest.raises(ValueError, match="SHA"):
        apply_classifications({"cases": []},
                             {"oracle_report_sha256": "wrong", "issues": {}})


@pytest.mark.parametrize("property_name,expected_value,broken", [
    ("spellings", ["msg.gas", "gasleft()"], ["msg.gas"]),
    ("via_alias", True, False),
])
def test_required_evidence_property_mutation_rejected(property_name, expected_value, broken):
    edge = dict(relation=ENV_FLOW if property_name == "spellings" else "WRITES_STATE",
                src="ENV:gasleft" if property_name == "spellings" else "alias.x = 2;",
                dst="uint a = msg.gas + gasleft();" if property_name == "spellings" else "Box state;",
                var="gasleft" if property_name == "spellings" else "state")
    edge[property_name] = expected_value
    key = fact_key(edge)
    expected = dict(edges=[edge], absent=[], counts={})
    props = {key: {property_name: sorted(expected_value) if property_name == "spellings" else expected_value}}
    assert compare(expected, {key}, {}, props)["passed"]
    props[key][property_name] = broken
    result = compare(expected, {key}, {}, props)
    assert not result["passed"]
    assert result["issues"][0]["kind"] == "evidence_property_mismatch"


def test_execution_error_keeps_case_and_flags_incomplete_metrics(tmp_path, monkeypatch):
    from scripts.DFG.dfg_v2 import oracle_check as checker
    oracle = tmp_path / "oracle"
    oracle.mkdir()
    (oracle / "SEAL.json").write_text("{}")
    (oracle / "bad.expected.json").write_text("{}")
    monkeypatch.setattr(checker, "verify_seal", lambda _: {"expectations_commit": "sealed"})
    def fail(*args):
        raise RuntimeError("injected construction failure")
    monkeypatch.setattr(checker, "run_case", fail)
    result = checker.run(oracle, tmp_path / "out")
    assert result["execution_error_cases"] == 1
    assert result["scored_cases"] == 0 and not result["metrics_complete"]
    assert result["failed_cases"] == 1
    assert result["cases"][0]["issues"][0]["kind"] == "execution_error"
