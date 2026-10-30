"""8G full-view parity, synthetic projection and tamper guards."""
import copy
import pytest
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import anonymize
from scripts.DFG.dfg_v2.benchmark_v2.spelling_parity import check_file, projection_resolution
from scripts.DFG.dfg_v2.benchmark_v2.anon_parity import node_code_view
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.tests.test_l1 import graph_for, FILE
from scripts.DFG.dfg_v2.tests.test_l3 import Encoder
from scripts.DFG.dfg_v2.pipeline import build

SOURCE = """pragma solidity ^0.5.0;
contract C {
 uint stored;
 function f(uint amount) public {
  uint other=amount; stored=other; require(msg.sender != tx.origin);
 }
}"""


def fixture(source=SOURCE):
    base = graph_for(source)
    archive, audit = build(base, {FILE:source}, {}, ["L1","L2","L3"], Encoder())
    return base, archive, audit, anonymize(source)


def test_exact_counts_facts_endpoints_and_original_graph_preserved():
    base, archive, audit, result = fixture()
    before = graph_fingerprint(base)
    row = check_file(base, archive, audit, SOURCE, FILE, result, None, Encoder())
    assert row["passed"] and row["normalized_facts_exact"] and row["projected_endpoints_exact"]
    assert graph_fingerprint(base) == before


def test_identical_synthetic_text_now_has_identical_rewrite():
    source = """pragma solidity ^0.5.0; contract C {
function f(uint amount) public { if(amount>0) { amount--; } }
function g(uint amount) public { if(amount>0) { amount--; } }
}"""
    base, archive, audit, result = fixture(source)
    ids = [n for n, a in base.nodes(data=True) if a["node_type"] == "end_if"]
    assert len(ids) >= 2
    cases = projection_resolution(base, source, FILE, result, ids)
    assert len(cases) == len(ids) and all(r["all_exact_candidates_agree"] for r in cases)
    assert len({r["rewritten_code"] for r in cases}) == 1
    assert check_file(base, archive, audit, source, FILE, result, None, Encoder())["passed"]


def test_fact_tampering_keeps_counts_but_fails_with_actual_evidence():
    base, archive, audit, result = fixture()
    audit = copy.deepcopy(audit)
    audit["layers"]["L1"]["evidence"][0]["target"] = -999
    row = check_file(base, archive, audit, SOURCE, FILE, result, None, Encoder())
    assert not row["passed"] and row["fact_counts_equal"]
    assert row["fact_differences"]["L1"]["original_missing"]
    assert row["fact_differences"]["L1"]["original_extra"]


def test_missing_edge_fails_with_endpoint_identity():
    base, archive, audit, result = fixture()
    s,t,k = next((s,t,k) for s,t,k,a in archive.edges(data=True,keys=True) if a["edge_type"]=="DATA_DEF_USE")
    archive.remove_edge(s,t,k)
    row = check_file(base, archive, audit, SOURCE, FILE, result, None, Encoder())
    assert not row["passed"] and row["edge_differences"]["original_extra"]


def test_modified_hcg_code_is_rejected():
    base, archive, audit, result = fixture()
    base.nodes[next(iter(base))]["code"] = "wrong"
    with pytest.raises(Exception):
        node_code_view(base, FILE, SOURCE, result)


def test_user_type_state_initialization_and_audit_v2_names():
    source = """pragma solidity ^0.5.0; contract C {
address owner=msg.sender; address other=owner;
function f() public { other=msg.sender; }
}"""
    base, archive, audit, result = fixture(source)
    assert check_file(base,archive,audit,source,FILE,result,None,Encoder())["passed"]
