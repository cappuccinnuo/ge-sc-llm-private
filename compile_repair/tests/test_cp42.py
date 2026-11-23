"""Kept-node scoring for ordinary Solidity edits."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

import pytest

from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.evaluation.benchmark import score_graphs
from compile_repair.toolchain.slither import run_slither
from compile_repair.toolchain.solc import compile_file, load_trusted_compilers

H = b"    function h(uint z) internal pure returns (uint) { uint[] memory t = new uint[](z); return t.length * 7 + 1; }\n"
SOURCE = (b"pragma solidity ^0.8.0;\ncontract A {\n    mapping(address => uint) bal;\n"
          b"    function g(address a, uint x) public { bal[a] = bal[a] + h(x) * 2; }\n" + H + b"}\n")


def graph(source, folder, compiler):
    folder.mkdir()
    path = folder/"A.sol"
    path.write_bytes(source)
    result = compile_file(path, compiler)
    (folder/"solc.json").write_text(json.dumps(asdict(result)),encoding="utf8")
    assert result.returncode == 0
    record = run_slither(result, "production")
    (folder/"slither.json").write_text(json.dumps(record),encoding="utf8")
    assert record["d3"]
    return json.loads(json.dumps(record["graph"]))


@pytest.mark.skipif(Path(sys.prefix).name != "compile-repair-production", reason="uses production Slither")
@pytest.mark.parametrize("at_top", [False, True])
def test_review_placement(tmp_path, at_top):
    compiler = load_trusted_compilers()[0]["0.8.38"]
    start = SOURCE.index(H)
    damaged, first = apply_patches(SOURCE,[Patch(start,start+len(H),H,b"","remove")])
    dest = damaged.index(b"    mapping") if at_top else start
    fixed, second = apply_patches(damaged,[Patch(dest,dest,b"",H,"restore")])
    score = score_graphs(graph(SOURCE,tmp_path/"truth",compiler),graph(fixed,tmp_path/"actual",compiler),
                         {"":SOURCE},{"":damaged},{"":fixed},{"":first},{"":second},0,True)
    assert score["raw"]["kept"]["ratio"] == (0.5 if at_top else 1)
    assert all(score[k]["ratio"] == 1 for k in ("kept","cfg_edges","calls"))
    assert score["counter_correspondence"]["status"] == ("verified" if at_top else "identical")
    assert score["lost"] == score["raw"]["lost"] == (3 if at_top else 0)
    assert score["added"] == score["raw"]["added"] == score["lost"]
    (tmp_path/"score.json").write_text(json.dumps(score),encoding="utf8")


@pytest.mark.parametrize("bad", ["operand","results"])
def test_changed_use_is_not_an_alpha_renaming(bad):
    def sample(operations):
        return dict(nodes=[dict(key5=["A","f()","EXPRESSION",0,1],node_type="EXPRESSION",length=1,ir=operations)])
    old = ["TMP_0(uint256) = x + 1","TMP_1(uint256) = x + 2","RETURN TMP_0"]
    new = ["TMP_4(uint256) = x + 1","TMP_5(uint256) = x + 2","RETURN TMP_4"]
    if bad == "operand":
        new[2] = "RETURN TMP_5"
    else:
        new[0], new[1] = new[0].replace("TMP_4","TMP_5"), new[1].replace("TMP_5","TMP_4")
    src = {"":b"contract A {}"}
    score = score_graphs(sample(old),sample(new),src,src,src,{},{},0,True)
    assert not score["exact"] and score["raw"]["kept"] == score["kept"]
    assert score["counter_correspondence"]["status"] == "rejected"


def test_partial_repair_with_renamed_file_scores_surviving_instructions():
    old_path, new_path = "vendor/A.sol", "lib/A.sol"
    raw = b"abcdef"
    damaged, removal = apply_patches(raw,[Patch(4,6,b"ef",b"","remove")])
    def node(path, offset, ir):
        return dict(filename=path,key5=["A","f()","EXPRESSION",offset,1],node_type="EXPRESSION",length=1,ir=ir)
    old = dict(nodes=[node(old_path,0,["TMP_0(uint256) = x + 1","RETURN TMP_0"]),
                      node(old_path,4,["RETURN x"])])
    new = dict(nodes=[node(new_path,0,["TMP_5(uint256) = x + 1","RETURN TMP_5"])])
    score = score_graphs(old,new,{old_path:raw},{old_path:damaged},{new_path:damaged},
                         {old_path:removal},{},0,True,file_renames={old_path:new_path})
    assert score["raw"]["kept"]["ratio"] == 0 and score["kept"]["ratio"] == 1
    assert score["counter_correspondence"]["status"] == "verified"
    assert score["lost"] == score["raw"]["lost"] == 1 and not score["exact"]
    assert score["migration_counters"]["status"] == "rejected"
