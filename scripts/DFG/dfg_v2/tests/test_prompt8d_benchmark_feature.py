import copy
import hashlib
import json

import networkx as nx
import numpy as np
import pytest

from scripts.DFG.dfg_v2.benchmark_v2.feature_view import (
    VERSION, _extract_rows, _write_npz, assemble_feature_graph, graph_fingerprint,
    vector_sha, verify_sources)
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref, write


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def fixture(tmp_path, original=False):
    graph = nx.MultiDiGraph()
    zero, one = np.zeros(512, dtype=np.float32), np.ones(512, dtype=np.float32)
    sources = {}
    for name in ("buggy_1.sol", "clean.sol"):
        path = tmp_path/name
        path.write_text("contract C {}")
        sources[name] = {"source": ref(path), "solidifi": name.startswith("buggy_")}
    graph.add_node(10, source_file="buggy_1.sol", node_type="expression_statement",
                   code="a_re_ent = 1", token=zero.copy(), node_info_vulnerabilities=[{"lines":[1]}])
    graph.add_node(30, source_file="clean.sol", node_type="return",
                   code="return 2", token=one.copy(), node_info_vulnerabilities=None)
    graph.add_node("env", source_file="buggy_1.sol", node_type="env_source",
                   code="msg.sender", token=one.copy(), node_info_vulnerabilities=None)
    graph.add_edge("env", 10, key="x", edge_type="ENV_FLOW")
    graph.add_edge(10,10,key=0,edge_type="next")
    rows = []
    for nid in (10,30):
        a=graph.nodes[nid]
        changed=one.copy() if nid==10 else one.copy()
        rows.append({"original_graph_node_id":nid,"file":a["source_file"],
            "node_type":a["node_type"],"source_sha256":sources[a["source_file"]]["source"]["sha256"],
            "code_sha256":_sha(a["code"]),"original_vector_sha256":vector_sha(a["token"]),
            "neutral_vector_sha256":vector_sha(changed),"solidifi":nid==10})
    features=np.stack([zero if original else one,one])
    data=tmp_path/"data.npz"
    _write_npz(data, features)
    manifest={"version":VERSION,"view":"original" if original else "idN_neutral_all_SolidiFI",
        "rows":rows,"data":ref(data),"feature_shape":[2,512],"sources":sources,
        "vector_sha_field":"original_vector_sha256" if original else "neutral_vector_sha256",
        "profiles":{"G3R":{"graph_fingerprint":graph_fingerprint(graph)}}}
    path=tmp_path/"manifest.json"
    write(path,manifest)
    return graph,path


def test_identity_feature_graph_is_bitwise_equal_but_independent_copy(tmp_path):
    graph,path=fixture(tmp_path,original=True)
    before=graph_fingerprint(graph)
    result=assemble_feature_graph(graph,ref(path))
    assert result is not graph
    assert graph_fingerprint(result)==before==graph_fingerprint(graph)
    result.nodes[10]["token"][0]=999
    assert graph.nodes[10]["token"][0]==0


def test_neutral_view_changes_only_bound_original_tokens(tmp_path):
    graph,path=fixture(tmp_path)
    before=graph_fingerprint(graph)
    result=assemble_feature_graph(graph,ref(path))
    assert list(result)==list(graph)
    assert list(result.edges(keys=True,data=True))==list(graph.edges(keys=True,data=True))
    assert np.array_equal(result.nodes[10]["token"],np.ones(512,dtype=np.float32))
    assert np.array_equal(result.nodes[30]["token"],graph.nodes[30]["token"])
    assert np.array_equal(result.nodes["env"]["token"],graph.nodes["env"]["token"])
    for nid in graph:
        for key in graph.nodes[nid]:
            if key!="token":
                assert result.nodes[nid][key]==graph.nodes[nid][key]
    assert graph_fingerprint(graph)==before


@pytest.mark.parametrize("mutation",["edge","token","order","code","label","node"])
def test_changed_graph_rejected(tmp_path,mutation):
    graph,path=fixture(tmp_path)
    if mutation=="edge":
        graph.add_edge(30,10,edge_type="extra")
    elif mutation=="token":
        graph.nodes[30]["token"][0]=9
    elif mutation=="order":
        graph=nx.MultiDiGraph(graph.subgraph(reversed(list(graph))))
        # NetworkX subgraph iteration follows original order; explicitly rebuild.
        original=graph;graph=nx.MultiDiGraph()
        graph.add_nodes_from(reversed(list(original.nodes(data=True))))
        graph.add_edges_from(original.edges(keys=True,data=True))
    elif mutation=="code":
        graph.nodes[10]["code"]="not the frozen code"
    elif mutation=="label":
        graph.nodes[10]["node_info_vulnerabilities"]=None
    else:
        graph.add_node(99,node_type="return",source_file="clean.sol",code="x",token=np.zeros(512,dtype=np.float32))
    with pytest.raises(ValueError,match="differ"):
        assemble_feature_graph(graph,ref(path))


@pytest.mark.parametrize("mutation",["missing","reordered","code","source","vector","duplicate"])
def test_malformed_bound_rows_rejected_even_if_caller_rehashes_manifest(tmp_path,mutation):
    graph,path=fixture(tmp_path)
    manifest=json.loads(path.read_text())
    if mutation=="missing":
        manifest["rows"].pop()
    elif mutation=="reordered":
        manifest["rows"].reverse()
    elif mutation=="duplicate":
        manifest["rows"][1]=copy.deepcopy(manifest["rows"][0])
    else:
        key={"code":"code_sha256","source":"source_sha256","vector":"neutral_vector_sha256"}[mutation]
        manifest["rows"][0][key]="wrong"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        assemble_feature_graph(graph,ref(path))


def test_manifest_and_data_sha_are_checked(tmp_path):
    graph,path=fixture(tmp_path)
    expected=ref(path)
    path.write_text(path.read_text()+" ")
    with pytest.raises(ValueError,match="SHA"):
        assemble_feature_graph(graph,expected)
    manifest=json.loads(path.read_text())
    (tmp_path/"data.npz").write_bytes(b"corrupt")
    with pytest.raises(ValueError,match="SHA"):
        assemble_feature_graph(graph,ref(path))


def test_encoder_must_reproduce_original_before_neutralizing(tmp_path):
    graph=nx.MultiDiGraph()
    graph.add_node(10,node_type="return",source_file="buggy_1.sol",code="a_re_ent",
                   token=np.zeros(512,dtype=np.float32))
    source={"buggy_1.sol":{"solidifi":True,"source":{"sha256":"a"*64}}}
    with pytest.raises(ValueError,match="original feature differs"):
        _extract_rows(graph,source,{"buggy_1.sol":{"a_re_ent":"id0"}},
                      lambda code: np.ones(512,dtype=np.float32))


def test_extract_rows_only_marker_identifiers_changed_and_non_solidifi_kept():
    graph=nx.MultiDiGraph()
    for nid,name,code in [(1,"buggy_1.sol","a_re_ent = 1"),(2,"clean.sol","a_re_ent = 1")]:
        graph.add_node(nid,node_type="return",source_file=name,code=code,
                       token=np.zeros(512,dtype=np.float32))
    sources={name:{"solidifi":name.startswith("buggy"),"source":{"sha256":str(i)*64}}
             for i,name in enumerate(("buggy_1.sol","clean.sol"))}
    def encode(code):
        return np.full(512,1 if "id0" in code else 0,dtype=np.float32)
    rows,original,neutral=_extract_rows(graph,sources,
            {"buggy_1.sol":{"a_re_ent":"id0"},"clean.sol":{}},encode)
    assert rows[0]["feature_changed"] and not rows[1]["feature_changed"]
    assert np.array_equal(original,np.zeros((2,512),dtype=np.float32))
    assert neutral[0,0]==1 and neutral[1,0]==0


def test_filename_candidate_without_pinned_source_match_is_rejected(tmp_path,monkeypatch):
    path=tmp_path/"buggy_1.sol";path.write_text("not pinned source")
    record={"sources":{"buggy_1.sol":ref(path)}}
    def git(args):
        return b"buggy_contracts/category/buggy_1.sol\n" if "ls-tree" in args else b"different"
    monkeypatch.setattr("scripts.DFG.dfg_v2.benchmark_v2.feature_view.subprocess.check_output",git)
    with pytest.raises(ValueError,match="pinned source"):
        verify_sources(record,tmp_path)


def test_pinned_source_confirmation_requires_exact_raw_bytes(tmp_path,monkeypatch):
    path=tmp_path/"buggy_1.sol";path.write_text("uint a_re_ent = 1;")
    record={"sources":{"buggy_1.sol":ref(path)}}
    def git(args):
        return b"buggy_contracts/category/buggy_1.sol\n" if "ls-tree" in args else path.read_bytes()
    monkeypatch.setattr("scripts.DFG.dfg_v2.benchmark_v2.feature_view.subprocess.check_output",git)
    proof,mapping=verify_sources(record,tmp_path,[{"file":"buggy_1.sol","solidifi":True}])
    assert proof["buggy_1.sol"]["pinned_matching_paths"]==["buggy_contracts/category/buggy_1.sol"]
    assert mapping=={"buggy_1.sol":{"a_re_ent":"id0"}}
