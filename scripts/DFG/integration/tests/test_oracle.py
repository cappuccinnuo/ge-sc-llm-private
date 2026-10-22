"""Oracle acceptance checks; fixtures do not replace the real sealed sample."""
import copy
from pathlib import Path
import pytest
from scripts.DFG.integration.oracle import validate_case, validate_selection, sha_bytes
from scripts.DFG.frontend import parse, walk
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source


@pytest.fixture(autouse=True)
def grammar(monkeypatch):
    root = Path(__file__).resolve().parents[4]
    monkeypatch.setenv("TREE_SITTER_LIB_DIR", str(root / "build/linux-x86_64"))


def fixture(source, family, relation, expected, frm=None, to=None):
    fn = next(n for n in walk(parse(source).root_node) if n.type == "function_definition")
    case = {"case_id": "synthetic/f", "cohort": "synthetic", "source_file": "oracle.sol",
            "source_sha256": sha_bytes(source.encode()), "function_span": [fn.start_byte, fn.end_byte],
            "function_sha256": sha_bytes(source.encode()[fn.start_byte:fn.end_byte]),
            "family": family, "relation": relation, "expected": expected,
            "from_text": frm, "to_text": to, "manual_reason": "test fixture"}
    return case, generate_cfg_from_source(source, "oracle.sol")


SOURCE = "pragma solidity ^0.5.17; contract C { function f(uint x) public returns(uint) {uint y=x;return y;} }"


def test_scalar_positive_and_label_independence():
    case, graph = fixture(SOURCE, "scalar", "DATA_DEF_USE", "present", "uint y=x;", "return y;")
    first = validate_case(case, graph, SOURCE)
    for _, data in graph.nodes(data=True):
        data["node_info_vulnerabilities"] = [{"lines": [777], "category": "not_used"}]
    second = validate_case(case, graph, SOURCE)
    assert first == second
    assert first["passed"] and first["classification"] == "projected"


def test_missing_hcg_anchor_is_projection_not_semantic_absence():
    case, graph = fixture(SOURCE, "scalar", "DATA_DEF_USE", "present", "uint y=x;", "return y;")
    graph.remove_node(next(n for n, d in graph.nodes(data=True) if d["code"] == "return y;"))
    result = validate_case(case, graph, SOURCE)
    assert result["semantic_facts"] == 1 and result["projected_facts"] == 0
    assert not result["passed"] and result["classification"] == "projection_missing"


def test_missing_expected_fact_does_not_claim_semantic_absence():
    case, graph = fixture(SOURCE, "scalar", "DATA_DEF_USE", "present", "does_not_exist", "return y;")
    result = validate_case(case, graph, SOURCE)
    assert not result["passed"] and result["classification"] == "missing_expected_semantic_fact"


def test_state_getter_has_no_in_function_def_use():
    source = "pragma solidity ^0.5.17; contract C {uint x;function f() public returns(uint){return x;}}"
    case, graph = fixture(source, "state", "STATE_DEF_USE", "absent")
    result = validate_case(case, graph, source)
    assert result["passed"] and result["classification"] == "semantic_absent"


def test_unsupported_return_preserves_explicit_fallback():
    source = 'pragma solidity ^0.5.17; contract C {function f() public returns(string memory){return "a";}}'
    case, graph = fixture(source, "state", "STATE_DEF_USE", "fallback")
    result = validate_case(case, graph, source)
    assert result["passed"] and result["classification"] == "analysis_scope_unsupported"
    assert result["no_partial_facts"] and result["diagnostics"]


def test_control_v2_projects_require_successor():
    source = "pragma solidity ^0.5.17; contract C {function f(address payable a,uint x) public {require(x>0);a.transfer(x);}}"
    case, graph = fixture(source, "control", "CONTROL_DEPENDENCE", "present", "require(x>0);", "a.transfer(x);")
    result = validate_case(case, graph, source)
    assert result["passed"] and result["projected_facts"] == 1


def test_source_or_function_digest_mismatch_rejected():
    case, graph = fixture(SOURCE, "scalar", "DATA_DEF_USE", "present", "uint y=x;", "return y;")
    with pytest.raises(ValueError, match="source mismatch"):
        validate_case(case, graph, SOURCE + " ")
    case["function_span"][0] += 1
    with pytest.raises(ValueError, match="span mismatch"):
        validate_case(case, graph, SOURCE)


def test_selection_rejects_duplicate_unbounded_and_endpoint_free_positives():
    case, _ = fixture(SOURCE, "scalar", "DATA_DEF_USE", "present", "uint y=x;", "return y;")
    assert validate_selection({"cases": [case]})
    with pytest.raises(ValueError, match="Duplicate"):
        validate_selection({"cases": [case, copy.deepcopy(case)]})
    with pytest.raises(ValueError, match="twelve"):
        validate_selection({"cases": [case] * 13})
    case["from_text"] = None
    with pytest.raises(ValueError, match="endpoints"):
        validate_selection({"cases": [case]})


def test_entry_source_text_cannot_impersonate_assignment_anchor():
    source = "pragma solidity ^0.5.17; contract C {function f(uint a,uint b) public returns(uint c){c = a + b;require(c >= a);}}"
    case, graph = fixture(source, "scalar", "DATA_DEF_USE", "present", "c = a + b;", "require(c >= a);")
    result = validate_case(case, graph, source)
    assert result["passed"] and result["semantic_facts"] == 1
    assert result["proofs"][0]["from_code"] == "c = a + b;"
