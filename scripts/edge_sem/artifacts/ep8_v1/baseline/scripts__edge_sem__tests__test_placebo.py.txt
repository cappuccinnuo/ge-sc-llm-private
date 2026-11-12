"""Placebo invariants on independently constructed typed, disconnected graphs."""
import copy
from collections import Counter
import networkx as nx
import numpy as np
import pytest
from scripts.edge_sem.placebo import randomize_edges,permute_attributes,degree_signature


def fixture():
    graph=nx.MultiDiGraph();edges=[]
    for file in ("a.sol","b.sol"):
        for i in range(6):
            graph.add_node((file,"s",i),source_file=file,node_type="statement")
            graph.add_node((file,"t",i),source_file=file,node_type="function")
        for i in range(6):
            for j in (i,(i+1)%6):
                edges.append(dict(src=(file,"s",i),dst=(file,"t",j),file=file,relation="CALL_SITE",evidence="must_not_survive"))
    return graph,edges


def test_random_edges_preserve_exact_typed_in_out_degrees_and_files():
    g,e=fixture();before=copy.deepcopy(e)
    new,report=randomize_edges(g,e)
    assert degree_signature(g,e)==degree_signature(g,new)
    assert len(new)==len(e) and len({(r["src"],r["dst"],r["relation"]) for r in new})==len(e)
    assert report["changed_edges"]>0 and all("evidence" not in r and not r["semantic_evidence"] for r in new)
    assert e==before
    assert randomize_edges(g,e)==(new,report)
    assert randomize_edges(g,e,seed=41)[0]!=new


def test_unrandomizable_star_is_disclosed():
    g,e=fixture();e=[r for r in e if r["src"]==("a.sol","s",0)]
    new,report=randomize_edges(g,e)
    assert report["changed_edges"]==0 and report["zero_switch_partitions"]==1
    assert degree_signature(g,e)==degree_signature(g,new)


def test_random_edges_reject_invalid_input():
    g,e=fixture()
    with pytest.raises(ValueError,match="Duplicate"):randomize_edges(g,e+[e[0]])
    bad=copy.deepcopy(e);bad[0]["file"]="b.sol"
    with pytest.raises(ValueError,match="Cross-file"):randomize_edges(g,bad)
    bad=copy.deepcopy(e);bad[0]["relation"]="next_line"
    with pytest.raises(ValueError,match="E1"):randomize_edges(g,bad)


def test_permutation_is_whole_vector_within_relation_and_immutable():
    rows=[dict(key=str(i),relation="A" if i<20 else "B") for i in range(40)]
    attrs={}
    for i,row in enumerate(rows):
        v=np.zeros(74,dtype=np.uint8);v[i]=1;attrs[row["key"]]=v
    new,audit=permute_attributes(rows,attrs)
    assert all(np.array_equal(attrs[audit["source_key_for_target"][k]],v) for k,v in new.items())
    for relation in ("A","B"):
        keys=[r["key"] for r in rows if r["relation"]==relation]
        assert Counter(attrs[k].tobytes() for k in keys)==Counter(new[k].tobytes() for k in keys)
        assert audit["per_relation"][relation]["changed_vectors"]>0
    repeat,_=permute_attributes(rows,attrs)
    assert all(np.array_equal(new[k],repeat[k]) for k in attrs)
    new["0"][:]=0
    assert attrs["0"].sum()==1


def test_permutation_rejects_missing_duplicate_and_bad_dtype():
    rows=[dict(key="k",relation="R")];attrs={"k":np.zeros(74,dtype=np.uint8)}
    with pytest.raises(ValueError,match="missing"):permute_attributes(rows,{})
    with pytest.raises(ValueError,match="duplicate"):permute_attributes(rows+rows,attrs)
    attrs["k"]=attrs["k"].astype(np.float32)
    with pytest.raises(ValueError,match="uint8"):permute_attributes(rows,attrs)
