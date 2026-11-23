"""Node-local name proofs for ordinary repairs, with real Solidity and independent negative cases."""
import json
from pathlib import Path
import sys

import pytest

from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.evaluation.benchmark import score_graphs
from compile_repair.tests.test_cp42 import graph
from compile_repair.toolchain.solc import load_trusted_compilers


def instructions(lines):
    return {"nodes":[dict(key5=["C","f()","EXPRESSION",i,1],node_type="EXPRESSION",length=1,ir=[line])
                     for i,line in enumerate(lines)]}


def competing_definitions(wrong):
    truth=["TMP_0(uint256) = x + 1","TMP_1(uint256) = x + 2","TMP_2(uint256) = TMP_0 + TMP_1",
           "RETURN TMP_2","TMP_3(uint256) = x + 3","RETURN TMP_3"]
    actual=["TMP_10(uint256) = x + 1","TMP_11(uint256) = x + 2","TMP_12(uint256) = TMP_10 + TMP_11",
            "RETURN TMP_12","TMP_13(uint256) = x + 3","RETURN TMP_13"]
    if wrong=="cross_node_use":
        actual[2]="TMP_12(uint256) = TMP_11 + TMP_11"
    else:
        actual[:2]=["TMP_11(uint256) = x + 1","TMP_10(uint256) = x + 2"]
    return instructions(truth),instructions(actual)


@pytest.mark.parametrize("wrong",["cross_node_use","swapped_definitions"])
def test_counters_do_not_hide_changed_data_flow(wrong):
    truth,actual=competing_definitions(wrong)
    files={"":b"contract C {}"}
    def score():
        return score_graphs(truth,actual,files,files,files,{},{},0,True)
    result=score()
    proof=result["counter_correspondence"]
    assert not result["exact"] and result["kept"]==dict(units=6,equal=5,ratio=5/6)
    assert proof["status"]=="partial" and proof["renamed_count"]==4
    assert proof["nodes"]==dict(candidate=6, structural=0, name_mismatch=1, disputed=0, unanchored_shift=0)
    # Node order must not choose the winner of a conflict.
    truth["nodes"].reverse()
    actual["nodes"].reverse()
    assert score()==result


def test_collision_in_source_reverts_the_whole_score():
    truth,actual=competing_definitions("cross_node_use")
    files={"":br'contract C { string constant s="\x54MP" "_13"; }'}
    result=score_graphs(truth,actual,files,files,files,{},{},0,True)
    assert result["counter_correspondence"]["status"]=="rejected"
    assert result["counter_correspondence"]["reason"]=="source_literal_collision"
    assert result["kept"]==result["raw"]["kept"] and not result["exact"]


@pytest.mark.skipif(Path(sys.prefix).name!="compile-repair-production",reason="uses production Slither")
def test_one_constant_edit_per_kept_node(tmp_path):
    constants=(b"11",b"22",b"33")
    source=(b"pragma solidity ^0.8.0; contract C {\n"+
            b"".join(b"function "+name+b"(uint x) external pure returns(uint) { return x + "+number+b"; }\n"
                     for name,number in zip((b"f",b"g",b"h"),constants))+b"}")
    new_function=b"function extra(uint z) external pure returns(uint) { return z * 7; }\n"
    compiler=load_trusted_compilers()[0]["0.8.38"]
    truth=graph(source,tmp_path/"truth",compiler)
    entries=sorted({n["key5"][3] for n in truth["nodes"] if n["node_type"]=="ENTRYPOINT"},reverse=True)
    assert len(entries)==3
    # Mark entry points as damaged and restore their bytes in every repair. Every kept node now holds a constant.
    damage=[Patch(i,i+1,source[i:i+1],b"?","damage_entry") for i in entries]
    mid,first=apply_patches(source,damage)
    cases={}
    for number in (None,)+constants:
        label="neutral" if number is None else number.decode()
        edits=[Patch(i,i+1,b"?",source[i:i+1],"restore_entry") for i in entries]
        if number is not None:
            pos=mid.index(b"+ "+number)+2
            edits.append(Patch(pos,pos+2,number,b"88","change_constant"))
        pos=source.index(b"{")+1
        edits.append(Patch(pos,pos,b"",new_function,"insert"))
        fixed,second=apply_patches(mid,sorted(edits,key=lambda p:-p.start))
        actual=graph(fixed,tmp_path/label,compiler)
        result=score_graphs(truth,actual,{"":source},{"":mid},{"":fixed},{"":first},{"":second},0,True)
        cases[label]=result
        assert result["counter_correspondence"]["status"]=="verified"
        assert result["kept"]["units"]==3
        assert result["kept"]["equal"]==(3 if number is None else 2)
        assert result["counter_correspondence"]["nodes"]["structural"]==int(number is not None)
    (tmp_path/"proportionality.json").write_text(json.dumps(cases),encoding="utf8")
