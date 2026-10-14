import copy
import numpy as np
import pytest
from scripts.DFG.state.analyzer import analyze_source
from scripts.DFG.state.projection import augment_state,assert_state_augmented
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.pipeline import augment
from scripts.DFG.state import STATE_DEF_USE
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source

def fixture(source=None):
    source=source or "pragma solidity ^0.5.17; contract C {uint x;function f(uint v) public {x=v;require(x>0);}}"
    graph=generate_cfg_from_source(source,"p.sol")
    for i,(n,d) in enumerate(graph.nodes(data=True)):
        d["token"]=np.arange(8,dtype=np.float32)+i
        d["node_info_vulnerabilities"]=None
    e2,_=augment(graph,{"p.sol":source})
    return e2,source

def state_pairs(g):
    return {(s,t) for s,t,d in g.edges(data=True) if d["edge_type"]==STATE_DEF_USE}

def test_original_labels_features_and_parallel_edges_preserved_and_off_exact():
    e2,src=fixture()
    s,t=next(iter(e2.edges()))
    e2.add_edge(s,t,key="same_endpoint_original",edge_type="next")
    before=fingerprint(e2)
    e3,a=augment_state(e2,{"p.sol":src})
    assert a["invariants"]["state_edges"]==1
    assert_state_augmented(e2,e3)
    assert fingerprint(e2)==before
    off,_=augment_state(e2,{},False)
    assert fingerprint(off)==before
    assert any(d["edge_type"]=="DATA_DEF_USE" for _,_,d in e3.edges(data=True))

def test_label_permutation_independent():
    e2,src=fixture()
    a,aa=augment_state(e2,{"p.sol":src})
    for n in e2:e2.nodes[n]["node_info_vulnerabilities"]=[{"category":"anything","lines":[999]}]
    b,bb=augment_state(e2,{"p.sol":src})
    assert state_pairs(a)==state_pairs(b)
    assert aa["evidence"]==bb["evidence"]

def test_unprojectable_write_still_kills():
    src="pragma solidity ^0.5.17; contract C {uint x;function f() public {x=1;x=2;require(x>0);}}"
    e2,src=fixture(src)
    doomed=[n for n,d in e2.nodes(data=True) if d.get("code")=="x=2;"]
    assert len(doomed)==1;e2.remove_node(doomed[0]) # fixture input lacks that semantic anchor
    out,a=augment_state(e2,{"p.sol":src})
    assert not state_pairs(out)
    r=a["files"]["p.sol"]
    assert r["projection_missing"]
    facts=[f for fn in r["functions"] for f in fn["facts"]]
    assert len(facts)==1
    assert "x=2" in src[facts[0]["definition"]["anchor"]["start"]:facts[0]["definition"]["anchor"]["end"]]

def test_wrong_source_and_unsupported_retains_all_e2():
    e2,src=fixture()
    for sources in [{},{"p.sol":src.replace("x=v","x=v+1")}]:
        out,a=augment_state(e2,sources)
        assert fingerprint(out)==fingerprint(e2)
        assert a["files"]["p.sol"]["fallback"]

def test_no_state_duplicate_application():
    g,s=fixture();out,_=augment_state(g,{"p.sol":s})
    with pytest.raises(ValueError,match="unenhanced"):augment_state(out,{"p.sol":s})

def test_may_alias_kept_as_evidence_not_false_certain_model_edge():
    src="pragma solidity ^0.5.17; contract C {mapping(uint=>uint) m;function f(uint k,uint j) public {m[k]=1;require(m[j]>0);}}"
    e2,src=fixture(src);out,a=augment_state(e2,{"p.sol":src})
    assert not state_pairs(out)
    assert a["files"]["p.sol"]["may_alias_sidecar_facts"]==1

def test_scope_fallback_preserves_other_function_and_no_partial_edges():
    src="pragma solidity ^0.5.17; contract C {uint x;uint[] a;function bad() public{x=1;require(x>0);a[0]=1;}function good() public{x=2;require(x>1);}}"
    g,src=fixture(src);out,a=augment_state(g,{"p.sol":src})
    assert len(state_pairs(out))==1
    bad=a["files"]["p.sol"]["functions"][0]
    assert bad["status"]=="function_fallback" and not bad["facts"] and not bad["events"]
    assert_state_augmented(g,out)
