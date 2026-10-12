import copy
import networkx as nx
import pytest
from scripts.DFG.ddg_builder import DDGBuilder
from scripts.DFG.projection import Projector
from scripts.DFG.models import Unsupported
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source

SOURCE="""pragma solidity ^0.5.17;
// comment
contract C {
function f(uint x) public returns(uint) {
uint y=x; y=x+1; return y;
}
}
"""

def assets():
    g=generate_cfg_from_source(SOURCE,"a.sol")
    r=DDGBuilder().analyze_source(SOURCE,"a.sol")
    return g,r

def test_ast_mapping_survives_renumber_and_same_line():
    g,r=assets()
    original={n:700+3*i for i,n in enumerate(g)}
    g=nx.relabel_nodes(g,original)
    p=Projector(g,r.view)
    mapping,diag=p.map_facts(r.facts)
    assert not diag and mapping
    edges,_,stats=DDGBuilder().projected_edges(r.facts,mapping)
    codes={(g.nodes[s]["code"],g.nodes[t]["code"]) for s,t,_ in edges}
    assert ("y=x+1;","return y;") in codes
    assert ("uint y=x;","return y;") not in codes

def test_label_values_not_read():
    g,r=assets()
    a=Projector(g,r.view).map_facts(r.facts)[0]
    for n in g: g.nodes[n]["node_info_vulnerabilities"]=[{"lines":[9999]}]
    assert Projector(g,r.view).map_facts(r.facts)[0]==a

@pytest.mark.parametrize("change",["text","anchor","type","duplicate"])
def test_stale_or_ambiguous_node_rejected(change):
    g,r=assets()
    n=next(k for k,d in g.nodes(data=True) if d["node_type"]=="expression_statement")
    if change=="text":g.nodes[n]["code"]="x=999;"
    elif change=="anchor":g.nodes[n]["label"]+="0"
    elif change=="type":g.nodes[n]["node_type"]="wrong"
    else:g.add_node(99999,**g.nodes[n])
    with pytest.raises(Unsupported):Projector(g,r.view)

def test_no_fallback_to_nearest_line_when_node_absent():
    g,r=assets()
    n=next(k for k,d in g.nodes(data=True) if d["code"]=="return y;")
    g.remove_node(n)
    mapping,diag=Projector(g,r.view).map_facts(r.facts)
    assert diag and all(a.role!="return_statement" for a in mapping)

def test_serialized_author_style_code():
    import json
    g,r=assets()
    for _,d in g.nodes(data=True):
        d["code"]=json.dumps(d["code"])
        d["label"]=json.dumps(d["label"])
        d["node_source_code_lines"]="[[1, 99]]"
    mapping,diag=Projector(g,r.view).map_facts(r.facts)
    assert mapping and not diag

def test_for_update_projects_to_own_existing_node():
    s="pragma solidity ^0.5.17; contract C {function f(uint x) public returns(uint y){for(uint i=0;i<x;i++){if(i>0)y=i;} return y;}}"
    g=generate_cfg_from_source(s,"a.sol")
    r=DDGBuilder().analyze_source(s,"a.sol")
    mapping,diag=Projector(g,r.view).map_facts(r.facts)
    update_facts=[f for f in r.facts if f.definition.anchor.role=="update_expression"]
    assert update_facts
    for f in update_facts:
        assert g.nodes[mapping[f.definition.anchor]]["code"]=="i++"
    edges,_,_=DDGBuilder().projected_edges(r.facts,mapping)
    assert any(g.nodes[u]["code"]=="i++" and g.nodes[v]["code"]=="y=i;" for u,v,_ in edges)
