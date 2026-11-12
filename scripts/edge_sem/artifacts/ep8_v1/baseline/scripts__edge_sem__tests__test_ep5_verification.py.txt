"""Final EP5 verifier must use the original per-file digest ordering."""
import networkx as nx
import numpy as np
import pytest
from scripts.edge_sem.attrs import edge_rows
from scripts.edge_sem.attr_batch import numeric_digest
from scripts.edge_sem.recon.ep5_verify import per_file_numeric_digest

def fixture():
    graph=nx.MultiDiGraph()
    for n in [42,8,25]:
        graph.add_node(n,source_file="one.sol",node_type="EXPRESSION")
    for n in range(100,500):
        graph.add_node(n,source_file="other.sol",node_type="EXPRESSION")
    for s,t in [(42,8),(8,25),(25,42)]:
        graph.add_edge(s,t,edge_type="next_line")
    rows=edge_rows(graph,[])
    values={}
    for i,r in enumerate(rows):
        values[r["key"]]=np.eye(74,dtype=np.uint8)[i]
    return graph,values

def test_subgraph_order_matches_receipt_not_full_graph_filter():
    graph,values=fixture()
    global_keys=[r["key"] for r in edge_rows(graph,[])]
    sub=graph.subgraph([42,8,25]).copy()
    original_keys=[r["key"] for r in edge_rows(sub,[])]
    assert original_keys!=global_keys
    expected=numeric_digest(original_keys,np.stack([values[k] for k in original_keys]))
    wrong=numeric_digest(global_keys,np.stack([values[k] for k in global_keys]))
    assert wrong!=expected
    assert per_file_numeric_digest(graph,[],values,"one.sol")==(3,expected)

def test_missing_or_changed_edge_vector_not_silently_accepted():
    graph,values=fixture()
    before=per_file_numeric_digest(graph,[],values,"one.sol")
    key=next(iter(values))
    values[key]=1-values[key]
    assert per_file_numeric_digest(graph,[],values,"one.sol")!=before
    del values[key]
    with pytest.raises(KeyError):
        per_file_numeric_digest(graph,[],values,"one.sol")

def test_empty_file_digest_is_explicit_none():
    graph,values=fixture()
    assert per_file_numeric_digest(graph,[],values,"other.sol")==(0,None)
