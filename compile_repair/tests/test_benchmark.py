"""CP4 byte alignment, grouping and graph-scoring invariants."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from compile_repair.cli import main
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches, compose_offsets
from compile_repair.evaluation.benchmark import (
    SourceLayout, classify_trigger, group_and_split, score_graphs, stratified_sample)


def edit(raw, a, b, value):
    return apply_patches(raw, [Patch(a, b, raw[a:b], value, "test")])


@pytest.mark.parametrize("a,b,value", [(0,0,b"in"),(2,4,b""),(2,4,b"!!"),(2,4,b"WIDE"),
                                       (0,6,b""),(4,6,b""),(0,2,b"XXYY")])
def test_composition_restores_verified_anchors(a,b,value):
    src=b"abcdef"
    damaged,first=edit(src,a,b,value)
    restored,second=edit(damaged,a,a+len(value),src[a:b])
    spans=compose_offsets(src,damaged,restored,first,second)
    origins=[s.original_start+i for s in spans for i in range(s.new_end-s.new_start)]
    assert src==restored and origins==list(range(len(src)))
    if a!=b and len(value)!=b-a:
        assert any(s.kind=="restored" for s in spans)


def test_unrelated_copy_and_invalid_chain():
    a=b"abcdef"
    b,first=edit(a,2,4,b"")
    c,second=edit(b,0,0,b"cd")
    spans=compose_offsets(a,b,c,first,second)
    assert spans[0].original_start is None
    assert not any(s.original_start is not None and s.original_start<=2<s.original_end for s in spans)
    with pytest.raises(ValueError):
        compose_offsets(a,b,c+b"?",first,second)


def test_split_and_sampling_are_stable_under_input_reordering():
    group,split=group_and_split("MANDO","abcd")
    assert group_and_split("SOChecker","abcd")==(group,split)
    h=hashlib.sha256(("cp4-split-v1:"+group).encode()).hexdigest()
    assert split==("dev" if int(h[:8],16)%5==0 else "test")
    rows=[{"unit_id":str(i),"corpus":"A","series":str(i%3)} for i in range(17)]
    chosen=stratified_sample(rows,7,42,"sample")
    assert chosen==stratified_sample(reversed(rows),7,42,"sample")
    assert len({r["series"] for r in chosen})==3 and len({r["unit_id"] for r in chosen})==7


@pytest.mark.parametrize("stage,success,primary,selected,expected",[
    ("solc",True,[],["encoding"],"resolved_by_environment"), ("solc",False,["encoding"],[],"not_triggered"),
    ("solc",False,[],["encoding"],"not_triggered"), ("solc",False,["encoding"],["encoding"],"included"),
    ("input_format",False,["encoding"],[],"included")])
def test_trigger_requires_applicable_observations(stage,success,primary,selected,expected):
    result=SimpleNamespace(status="success" if success else "unrepaired")
    assert classify_trigger(stage,"encoding",result,primary,selected)==expected


def toy(positions, project=False):
    nodes=[]
    for i,pos in enumerate(positions):
        row=dict(key5=["T","f()","EXPRESSION",pos,1],node_type="EXPRESSION",ir=["v"+str(i)],length=1)
        if project:
            row["filename"]="T.sol"
        nodes.append(row)
    keys=[{"filename":"T.sol","key5":n["key5"]} if project else n["key5"] for n in nodes]
    edge={"source":keys[0],"target":keys[-1],"kind":"next"}
    call={"node":keys[0],"kind":"internal","ir_index":0,"callee":{"contract":"T","function":"g()"}}
    return {"nodes":nodes,"cfg_edges":[edge,dict(edge)],"calls":[call]}


@pytest.mark.parametrize("project",[False,True])
def test_restoration_checks_bytes_nodes_edge_multiplicity_and_calls(project):
    path="T.sol" if project else ""
    a=b"abcdef"
    b,ab=edit(a,2,4,b"")
    c,bc=edit(b,2,2,b"cd")
    truth=toy([0,2,5],project)
    actual=toy([0,2,5],project)
    def score():
        return score_graphs(truth,actual,{path:a},{path:b},{path:c},{path:ab},{path:bc},0,True)
    s=score()
    assert s["exact"] and s["affected_by_deletion"]==1 and s["lost"]==s["added"]==0
    actual["nodes"][1]["ir"]=["wrong"]
    s=score()
    assert s["lost"]==1 and s["kept"]["ratio"]==1 and not s["exact"]
    actual["nodes"][0]["ir"]=["wrong"]
    actual["cfg_edges"].pop()
    actual["calls"][0]["ir_index"]=1
    s=score()
    assert s["kept"]["ratio"]==0.5 and s["cfg_edges"]["ratio"]==0.5 and s["calls"]["ratio"]==0


def test_repair_additions_in_unrelated_definition():
    a=b"contract A {} contract B {}"
    b,ab=edit(a,10,10,b" ")
    pos=b.index(b"B")
    c,bc=edit(b,pos,pos,b"ZZ")
    truth={"nodes":[],"cfg_edges":[],"calls":[]}
    node={"key5":["B","x()","ENTRYPOINT",pos,1],"node_type":"ENTRYPOINT","ir":[],"length":2}
    actual=dict(truth,nodes=[node])
    s=score_graphs(truth,actual,{"":a},{"":b},{"":c},{"":ab},{"":bc},0,True)
    assert s["added"]==1 and s["added_only_in_repair_bytes"] and not s["added_bytes_near_damage"] and not s["exact"]
    assert not score_graphs(truth,None,{"":a},{"":a},{"":a},{},{},None,False)["compiled"]


def test_lexical_sites_ignore_comments_and_strings():
    src=b'/* contract Fake {} */ contract Real { string constant s="function fake() {}"; }'
    layout=SourceLayout(src)
    assert len(layout.definitions)==len(layout.top_regions())==1 and not layout.functions


def test_score_cli_verifies_bytes_and_writes_exclusively(tmp_path):
    graph=tmp_path/"graph.json"
    graph.write_text(json.dumps(toy([0,2])))
    src=tmp_path/"src"
    src.write_bytes(b"abc")
    def ref(p):
        return {"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
    spec=dict(truth_graph=ref(graph),repaired_graph=ref(graph),solc_returncode=0,d3=True,
              files=[dict(name="",original=ref(src),damaged=ref(src),repaired=ref(src))])
    request=tmp_path/"request.json"
    request.write_text(json.dumps(spec))
    out=tmp_path/"out"
    args=["benchmark-score","--request",str(request),"--output",str(out)]
    assert main(args)==0 and json.loads((out/"score.json").read_bytes())["exact"]
    with pytest.raises(FileExistsError):
        main(args)
