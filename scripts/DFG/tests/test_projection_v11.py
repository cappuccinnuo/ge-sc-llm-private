"""v1.1 exact DOT regression tests; Solidity fixtures are parser-only, not solc verified."""
import copy
import pytest
import pydot
from scripts.DFG.ddg_builder import DDGBuilder
from scripts.DFG.frontend import SourceView
from scripts.DFG.models import Unsupported
from scripts.DFG.pipeline import augment
from scripts.DFG.projection import Projector, code_equal
from scripts.DFG.graph_audit import fingerprint
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source


@pytest.mark.parametrize("source", [
    "uint y=x;", 'require(x > 0, "message");',
    r'require(x > 0, "\x19Ethereum Signed Message:\n32");',
    r'require(x > 0, "back\\slash and \"quoted\"");',
    'function f() public {\n\treturn;\n}',
    'function f() public {\r\nreturn;\r\n}',
    'require(x > 0, "\u4f60\u597d\u03bb");',
])
def test_exact_raw_and_pydot_representation(source):
    assert code_equal(source, source)
    assert code_equal(pydot.quote_if_necessary(source), source)


@pytest.mark.parametrize("a,b", [
    (r'require(x, "\x41");', 'require(x, "A");'),
    (r'require(x, "\u0041");', 'require(x, "A");'),
    (r'require(x, "\t");', 'require(x, "\t");'),
    (r'require(x, "\\path");', r'require(x, "\path");'),
    ('uint y=x;', 'uint y = x;'),
    ('return x;', 'return y;'),
    ('require(x, "\u4f60");', 'require(x, "\u597d");'),
])
def test_changed_source_rejected_in_both_directions(a,b):
    assert a != b
    assert pydot.quote_if_necessary(a) != pydot.quote_if_necessary(b)
    for stored,expected in [(a,b),(b,a)]:
        assert not code_equal(stored,expected)
        assert not code_equal(pydot.quote_if_necessary(stored),expected)


SOURCE = r'''pragma solidity ^0.5.17;
contract C {
    function f(uint x) public returns(uint) {
        uint y=x;
        require(x > 0, "\x19Ethereum Signed Message:\n32");
        y=x+1;
        return y;
    }
}
'''


def assets(source=SOURCE):
    g=generate_cfg_from_source(source,"a.sol")
    result=DDGBuilder().analyze_source(source,"a.sol")
    assert result.view is not None
    return g,result


def dot_fields(graph):
    result=copy.deepcopy(graph)
    for _,data in result.nodes(data=True):
        data["code"]=pydot.quote_if_necessary(data["code"])
        data["label"]=pydot.quote_if_necessary(data["label"])
    return result


def test_dot_roundtrip_exact_projection_and_no_graph_mutation():
    raw,r=assets()
    dot=dot_fields(raw)
    before=fingerprint(dot)
    mapping,diagnostics=Projector(dot,r.view).map_facts(r.facts)
    assert mapping and not diagnostics
    raw_map,_=Projector(raw,r.view).map_facts(r.facts)
    assert mapping == raw_map
    out,audit=augment(dot,{"a.sol":SOURCE})
    assert fingerprint(dot)==before
    assert dict(out.nodes(data=True))==dict(dot.nodes(data=True))
    assert audit["files"]["a.sol"]["projection"]["facts_projected"]>0
    assert any(d.get("edge_type")=="DATA_DEF_USE" for _,_,d in out.edges(data=True))
    for u,v,k,d in dot.edges(keys=True,data=True):
        assert out.get_edge_data(u,v,k)==d


@pytest.mark.parametrize("change", ["ast_id", "type", "endpoints", "duplicate", "wrong_text"])
def test_strict_anchor_checks_remain(change):
    raw,r=assets();g=dot_fields(raw)
    n=next(i for i,d in raw.nodes(data=True) if d["code"]=="y=x+1;")
    if change=="ast_id":
        g.nodes[n]["label"]=pydot.quote_if_necessary("999999-expression_statement-1-1")
    elif change=="type":
        g.nodes[n]["node_type"]="return"
    elif change=="endpoints":
        old=raw.nodes[n]["label"];g.nodes[n]["label"]=pydot.quote_if_necessary(old.rsplit("-",1)[0]+"-9999")
    elif change=="duplicate":
        g.add_node(999999,**copy.deepcopy(g.nodes[n]))
    else:
        g.nodes[n]["code"]=pydot.quote_if_necessary("y=x+2;")
    with pytest.raises(Unsupported):Projector(g,r.view)


def collision_sources():
    prefix="pragma solidity ^0.5.17; contract C { function f() public { "
    a='string memory s = "a'+chr(92)+'\nb" "x'+chr(92)*2+'nc";'
    b='string memory s = "a'+chr(92)*2+'nb" "x'+chr(92)+'\nc";'
    return prefix+a+" } }",prefix+b+" } }"


def test_serialized_multiline_literal_collision_falls_back_with_same_ast_endpoints():
    # Both parse with this grammar. No claim of solc validation is made.
    # DOT does not escape pre-existing backslashes: serialized bytes can collide.
    a,b=collision_sources()
    ga=generate_cfg_from_source(a,"a.sol")
    gb=generate_cfg_from_source(b,"a.sol")
    va,vb=SourceView(a,"a.sol"),SourceView(b,"a.sol")
    assert [(d["node_type"],d["label"].splitlines()[-1]) for _,d in ga.nodes(data=True)] == [(d["node_type"],d["label"].splitlines()[-1]) for _,d in gb.nodes(data=True)]
    da,db=dot_fields(ga),dot_fields(gb)
    assert [d["code"] for _,d in da.nodes(data=True)]==[d["code"] for _,d in db.nodes(data=True)]
    # Exact raw source is still supported; ambiguous serialized source is not.
    assert Projector(ga,va).by_ast and Projector(gb,vb).by_ast
    for graph,view in [(da,va),(da,vb),(db,va),(db,vb)]:
        with pytest.raises(Unsupported):Projector(graph,view)
