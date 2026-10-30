"""Token-only 8G feature adapter invariants on small real graph fixtures."""
import copy
import hashlib
import numpy as np
import pytest
from scripts.DFG.dfg_v2.benchmark_v2.spelling_features import assemble, VERSION
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint, vector_sha, _write_npz
from scripts.DFG.dfg_v2.benchmark_v2.prepare import write, ref
from scripts.DFG.dfg_v2.tests.test_l1 import graph_for


def fixture(tmp_path,anonymous=True):
    source="pragma solidity ^0.5.0; contract C { uint x; function f(uint arg) public { x=arg; } }"
    graph=graph_for(source)
    for n,a in graph.nodes(data=True):
        a["token"]=np.zeros(512,dtype=np.float32)
    rows=[];values=[]
    for n,a in graph.nodes(data=True):
        vector=np.full(512,n+1,dtype=np.float32) if anonymous else a["token"].copy()
        values.append(vector)
        rows.append(dict(original_graph_node_id=n,file=a["source_file"],node_type=a["node_type"],
            source_sha256="source_sha",code_sha256=hashlib.sha256(a["code"].encode()).hexdigest(),
            original_vector_sha256=vector_sha(a["token"]),anonymous_vector_sha256=vector_sha(vector)))
    path=tmp_path/"data.npz";_write_npz(path,np.stack(values))
    view=dict(version=VERSION,view="anonymous",rows=rows,feature_shape=[len(rows),512],
        data=ref(path),vector_sha_field="anonymous_vector_sha256",
        profiles={"G0":dict(graph_fingerprint=graph_fingerprint(graph))},
        sources={rows[0]["file"]:dict(sha256="source_sha")})
    write(tmp_path/"manifest.json",view)
    return graph,ref(tmp_path/"manifest.json"),view


def test_anonymous_changes_only_tokens_on_every_source(tmp_path):
    graph,view,_=fixture(tmp_path)
    before=graph_fingerprint(graph)
    result=assemble(graph,view)
    assert graph_fingerprint(graph)==before
    assert all(not np.array_equal(graph.nodes[n]["token"],result.nodes[n]["token"]) for n in graph)
    for n in graph:result.nodes[n]["token"]=graph.nodes[n]["token"].copy()
    assert graph_fingerprint(result)==before


def test_identity_view_reconstructs_exact_original(tmp_path):
    graph,view,_=fixture(tmp_path,anonymous=False)
    assert graph_fingerprint(assemble(graph,view))==graph_fingerprint(graph)


@pytest.mark.parametrize("change",["node_order","label","code","edge","token"])
def test_wrong_graph_identity_rejected(tmp_path,change):
    graph,view,_=fixture(tmp_path)
    nid=next(iter(graph))
    if change=="node_order":
        last=copy.deepcopy(graph.nodes[nid]);graph.remove_node(nid);graph.add_node(nid,**last)
    elif change=="label":graph.nodes[nid]["label"]="wrong"
    elif change=="code":graph.nodes[nid]["code"]="wrong"
    elif change=="token":graph.nodes[nid]["token"][0]=100
    elif change=="edge":graph.add_edge(nid,nid,edge_type="not_frozen")
    with pytest.raises(ValueError,match="Graph schema"):
        assemble(graph,view)


def test_npz_modification_rejected(tmp_path):
    graph,view,_=fixture(tmp_path)
    with (tmp_path/"data.npz").open("ab") as f:f.write(b"tampered")
    with pytest.raises(ValueError):
        assemble(graph,view)


def test_auxiliary_nodes_keep_features(tmp_path):
    from scripts.DFG.dfg_v2 import ENV_SOURCE
    graph,_,view=fixture(tmp_path)
    anchor=next(iter(graph))
    graph.add_node(99999,node_type=ENV_SOURCE,source_file=graph.nodes[anchor]["source_file"],
                   code="msg.sender",token=np.ones(512,dtype=np.float32))
    view["profiles"]["G3R"]=dict(graph_fingerprint=graph_fingerprint(graph))
    write(tmp_path/"env.json",view)
    result=assemble(graph,ref(tmp_path/"env.json"))
    assert np.array_equal(result.nodes[99999]["token"],graph.nodes[99999]["token"])
