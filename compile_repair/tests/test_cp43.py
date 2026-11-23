"""Regression fixtures for repair-only deletions and witnessed Yul switch source offsets."""
import copy
import json
from pathlib import Path
import sys

import pytest

from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.evaluation.benchmark import score_graphs
from compile_repair.tests.test_cp42 import graph
from compile_repair.toolchain.solc import load_trusted_compilers


production = pytest.mark.skipif(Path(sys.prefix).name != "compile-repair-production", reason="uses production Slither")


@production
def test_repair_deleting_an_undamaged_function(tmp_path):
    h = b"    function h(uint z) internal pure returns (uint) { return z * 7 + 1; }\n"
    u = b"    function u(uint q) public { if (q > 3) { bal[msg.sender] = q; } else { bal[msg.sender] = h(q); } }\n"
    original = (b"pragma solidity ^0.8.0;\ncontract A {\n    mapping(address => uint) bal;\n"
                b"    function g(address a, uint x) public { bal[a] = bal[a] + h(x) * 2; }\n" + h + u + b"}\n")
    start = original.index(h)
    damaged, first = apply_patches(original, [Patch(start, start+len(h), h, b"", "damage")])
    index = damaged.index(u)
    repaired, second = apply_patches(damaged, [Patch(index, index+len(u), u, b"", "delete_good_function"),
                                               Patch(start, start, b"", h, "restore")])
    compiler = load_trusted_compilers()[0]["0.8.38"]
    result = score_graphs(graph(original,tmp_path/"truth",compiler), graph(repaired,tmp_path/"actual",compiler),
                          {"":original},{"":damaged},{"":repaired},{"":first},{"":second},0,True)
    assert result["compiled"] and not result["exact"]
    assert result["kept"] == {"units":7,"equal":2,"ratio":2/7}
    assert result["missing_kept"] == result["removed_by_repair"] == 5 and result["lost"] == 2
    assert result["calls"]["ratio"] == 1/2 and result["cfg_edges"]["ratio"] == 1/6
    assert all(metric["ratio"] == 1 for metric in result["surviving"].values())
    (tmp_path/"score.json").write_text(json.dumps(result),encoding="utf8")


@production
def test_yul_switch_offset_from_composed_mapping(tmp_path):
    original = (b"pragma solidity ^0.8.0; contract A { function f(uint x) public pure returns (uint v) {"
                b"assembly { switch x case 0 { v := 3 } default { v := 7 } } } }")
    added = b"function g() external pure returns(uint) { return 1; } "
    pos = original.index(b"function")
    fixed, second = apply_patches(original, [Patch(pos,pos,b"",added,"insert")])
    compiler = load_trusted_compilers()[0]["0.8.38"]
    truth = graph(original,tmp_path/"truth",compiler)
    actual = graph(fixed,tmp_path/"actual",compiler)
    def score(candidate):
        return score_graphs(truth,candidate,{"":original},{"":original},{"":fixed},{},{"":second},0,True)
    result = score(actual)
    assert all(result[k]["ratio"] == result["surviving"][k]["ratio"] == 1 for k in ("kept","cfg_edges","calls"))
    assert result["raw"]["kept"]["ratio"] < 1 and result["removed_by_repair"] == 0
    proof = result["counter_correspondence"]
    assert proof["status"] == "verified"
    [switch] = proof["yul_switches"]
    before = original.index(b"switch"); after = before+len(added)
    assert int(switch["src_before"].split(":")[0]) == before
    assert int(switch["src_after"].split(":")[0]) == after
    bad_results = {}
    for label, offset in (("off_by_one",after+1),("stale",before)):
        wrong = copy.deepcopy(actual)
        for node in wrong["nodes"]:
            node["ir"] = [line.replace(switch["new"],switch["new"].replace(
                "switch_expr_"+str(after)+"_", "switch_expr_"+str(offset)+"_", 1)) for line in node["ir"]]
        bad = score(wrong)
        assert bad["counter_correspondence"]["status"] == "identical"
        assert bad["counter_correspondence"]["nodes"]["switch"] > 0 and not bad["exact"]
        assert bad["kept"] == bad["raw"]["kept"]
        bad_results[label] = bad
    (tmp_path/"scores.json").write_text(json.dumps(dict(verified=result,rejected=bad_results)),encoding="utf8")


def test_only_deleted_bytes_leave_surviving_denominators():
    def node(name, offset):
        return dict(key5=["C",name,"EXPRESSION",offset,1],node_type="EXPRESSION",length=1,ir=[])
    source = b"abc"
    a,b,c = (node("f()",0),node("g()",1),node("h()",2))
    call = dict(node=a["key5"],ir_index=0,kind="internal",callee={"contract":"C","function":"g()"})
    edge = dict(source=a["key5"],target=c["key5"],kind="next")
    truth = dict(nodes=[a,b,c],calls=[call],cfg_edges=[edge])
    actual = dict(nodes=[a],calls=[],cfg_edges=[])
    fixed, edits = apply_patches(source,[Patch(1,2,b"b",b"","delete_g")])
    score = score_graphs(truth,actual,{"":source},{"":source},{"":fixed},{},{"":edits},0,True)
    assert score["removed_by_repair"] == 1 and score["missing_kept"] == 2 and score["lost"] == 0
    assert score["kept"]["ratio"] == 1/3 and score["surviving"]["kept"]["ratio"] == 1/2
    assert score["calls"]["truth"] == 1 and score["surviving"]["calls"]["truth"] == 0
    assert score["surviving"]["cfg_edges"]["truth"] == 1 and score["surviving"]["cfg_edges"]["matched"] == 0
