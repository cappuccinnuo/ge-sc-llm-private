"""Pure comparator regressions: no Slither binary, model or graph mutation."""
import copy

import pytest

from scripts.DFG.dfg_v2.slither_align import (
    SourceFacts, classify, match_spans, overlap, _normalize, summarize)

SOURCE = """pragma solidity ^0.4.24;
contract C {
 uint constant K = 1;
 uint s = 3;
 uint[] arr;
 mapping(uint=>uint) m;
 function f(uint p) public returns(uint out) {
   uint x;
   (uint a, uint b) = (p, x);
   m[p] = x;
   arr.push(p);
   out = p;
   assembly { let z := 1 }
   return;
 }
}"""


def node(ast, kind, text=None):
    return next(n for n in ast.nodes if n.type == kind and
                (text is None or ast.text(n) == text))


def interval(ast, kind, text=None):
    return ast.interval(node(ast, kind, text))


def event(ast, layer="L1", name="x", kind="DEF", site="uint x;", declaration="uint x",
          side="v2", tags=(), scope="supported"):
    start = SOURCE.index(site)
    decl_start = SOURCE.index(declaration) if declaration is not None else None
    return dict(event_id="e", layer=layer, name=name, kind=kind,
                span=[start, start+len(site)], side=side,
                declaration=[decl_start, decl_start+len(declaration)] if declaration else None,
                function_scope=scope, tags=list(tags), evidence=[])


def test_half_open_spans_and_empty():
    assert overlap([1,4], [3,7])
    assert not overlap([1,4], [4,7])
    assert not overlap([2,2], [1,4])


def test_matching_one_to_one_deterministic_and_name_kind():
    def ev(i, a, b, name="x", kind="USE"):
        return dict(event_id=i,span=[a,b],name=name,kind=kind)
    c=[ev("c2",3,7),ev("c1",1,5),ev("c3",4,6,"y")]
    r=[ev("r2",4,8),ev("r1",2,6),ev("r3",4,6,kind="DEF")]
    a=match_spans(c,r)
    b=match_spans(list(reversed(c)),list(reversed(r)))
    assert [(x["event_id"],y["event_id"]) for x,y in a[0]] == [("c1","r1"),("c2","r2")]
    assert a == b
    assert a[1][0]["event_id"] == "c3"
    assert a[2][0]["event_id"] == "r3"
    assert len({r["event_id"] for _,r in a[0]}) == len(a[0])


@pytest.fixture
def ast():
    return SourceFacts(SOURCE)


@pytest.mark.parametrize("category", [
    "entry_initialization", "v2_fallback", "unreachable_ir",
    "named_return_implicit", "declaration_without_initializer",
    "tuple_or_var_declaration", "constant_excluded", "state_initializer",
    "write_base_read", "modifier_inlining", "alias",
    "v2_binding_unresolved", "assembly", "push_pop_skipped"])
def test_each_category_positive_and_negative(ast, category):
    e=event(ast, kind="USE", site="out = p;", declaration="uint x")
    direction="FP"
    candidates=[]
    diagnostics=[]
    if category == "entry_initialization":
        e["tags"]=["entry_initialization"]
    elif category == "v2_fallback":
        direction="FN"; e["function_scope"]="fallback"
    elif category == "unreachable_ir":
        e["tags"]=["unreachable_ir"]
    elif category == "named_return_implicit":
        direction="FN"
        e=event(ast,name="out",kind="USE",site="return;",declaration="uint out")
    elif category == "declaration_without_initializer":
        e=event(ast)
    elif category == "tuple_or_var_declaration":
        e=event(ast,name="a",kind="DEF",site="uint a",declaration="uint a")
    else:
        direction="FN"
        e=event(ast,layer="L2",name="m",kind="READ",site="m[p] = x;",
                declaration="mapping(uint=>uint) m;")
        if category == "constant_excluded":
            e=event(ast,layer="L2",name="K",kind="READ",site="out = p;",
                    declaration="uint constant K = 1;")
        elif category == "state_initializer":
            e=event(ast,layer="L2",name="s",kind="WRITE",site="uint s = 3;",
                    declaration="uint s = 3;")
        elif category == "write_base_read":
            w=copy.deepcopy(e);w.update(event_id="write",kind="WRITE",
                span=interval(ast,"array_access","m[p]"),
                evidence=[{"occurrence":{"start":SOURCE.index("m[p]"),
                                         "end":SOURCE.index("m[p]")+4}}])
            candidates=[w]
        elif category in ("modifier_inlining","alias"):
            e["tags"]=[category]
        elif category == "v2_binding_unresolved":
            diagnostics=[dict(kind="state_binding_unresolved",name="m",
                              start=e["span"][0],end=e["span"][0]+1,reason="state_name_missing")]
        elif category == "assembly":
            e["span"]=[SOURCE.index("let z"),SOURCE.index("let z")+10]
        elif category == "push_pop_skipped":
            e["span"]=[SOURCE.index("arr.push(p)"),SOURCE.index("arr.push(p)")+11]
            diagnostics=[dict(kind="state_access_unresolved",reason="push_pop_write_skipped:unconfirmed_array",
                              start=e["span"][0],end=e["span"][1])]
    assert classify(e,direction,ast,candidates,diagnostics)[0] == category
    negative=event(ast,layer=e["layer"],kind="USE" if e["layer"]=="L1" else "READ",
                   site="out = p;",declaration=None)
    assert classify(negative,"FN",ast,[],[])[0] != category


def test_priority_and_direction(ast):
    e=event(ast,tags=["entry_initialization","unreachable_ir"],scope="fallback")
    assert classify(e,"FP",ast,[],[])[0]=="entry_initialization"
    assert classify(e,"FN",ast,[],[])[0]=="v2_fallback"
    e=event(ast,layer="L2",name="K",kind="READ",site="out = p;",
            declaration="uint constant K = 1;",tags=["alias"])
    assert classify(e,"FN",ast,[],[])[0]=="constant_excluded"
    assert classify(e,"FP",ast,[],[])[0]=="alias"


def test_write_base_read_rejects_existing_read(ast):
    e=event(ast,layer="L2",name="m",kind="READ",site="m[p] = x;",
            declaration="mapping(uint=>uint) m;")
    span=interval(ast,"array_access","m[p]")
    w=dict(e,event_id="w",kind="WRITE",span=span,
           evidence=[{"occurrence":{"start":span[0],"end":span[1]}}])
    assert classify(e,"FN",ast,[w],[])[0]=="write_base_read"
    read=dict(w,event_id="r",kind="READ")
    assert classify(e,"FN",ast,[w,read],[])[0]=="other"


def test_unresolved_requires_same_name_and_overlap(ast):
    e=event(ast,layer="L2",name="m",kind="READ",site="m[p] = x;",
            declaration="mapping(uint=>uint) m;")
    d=dict(kind="state_binding_excluded",name="x",start=e["span"][0],end=e["span"][1])
    assert classify(e,"FN",ast,[],[d])[0]=="other"
    d["name"]="m";d["start"]=0;d["end"]=1
    assert classify(e,"FN",ast,[],[d])[0]=="other"


def test_no_initializer_requires_def_and_exact_statement(ast):
    e=event(ast,kind="USE")
    assert classify(e,"FN",ast,[],[])[0]=="other"
    e=event(ast,kind="DEF",site="out = p;")
    assert classify(e,"FN",ast,[],[])[0]=="other"


def test_named_return_requires_declaration_not_name(ast):
    e=event(ast,name="out",kind="USE",site="return;",declaration="uint x")
    assert classify(e,"FN",ast,[],[])[0]=="other"


def test_normalization_preserves_identity_collisions_and_dedups_contexts():
    raw=b"x=x;"
    rows=[dict(node={"start":0,"end":4},fact=[1,"x","USE"],declaration={"start":0,"end":1},
               function={"start":0},tags=[],context_index=0)]
    rows.append(dict(rows[0],context_index=1,tags=["inheritance"]))
    result=_normalize(rows,"slither","L1",raw,[{"start":0,"status":"supported"}])
    assert len(result)==1 and len(result[0]["evidence"])==2
    assert result[0]["tags"]==["inheritance"]
    rows.append(dict(rows[0],declaration={"start":2,"end":3}))
    assert len(_normalize(rows,"slither","L1",raw,[]))==2


def test_entry_uses_declaration_interval_not_whole_function():
    raw=b"uint x; f(x);"
    row=dict(declaration={"start":0,"end":6},event_anchor={"start":0,"end":len(raw)},
             event_kind="entry",event_id="f:e0",function_start=0,name="x",kind="DEF",tags=["entry_initialization"],line=1)
    out=_normalize([row],"v2","L1",raw,[{"start":0,"status":"supported"}])
    assert out[0]["span"]==[0,6]


def test_invalid_spans_rejected():
    row=dict(node={"start":0,"end":99},fact=[1,"x","USE"],declaration=None,function=None,tags=[])
    with pytest.raises(ValueError,match="Invalid raw byte span"):
        _normalize([row],"slither","L1",b"x;",[])


def test_empty_summaries():
    out=summarize([],[])
    assert out["L1"]["metrics"]["precision"] is None
    assert out["L2"]["metrics"]["reference_count"]==0


def test_distinct_ir_events_with_same_anchor_never_collapsed():
    raw=b"uint x; f(x);"
    row=dict(declaration={"start":0,"end":6},event_anchor={"start":8,"end":12},
             event_kind="expression",event_id="f:e1",function_start=0,name="x",
             kind="USE",tags=[],line=1)
    rows=[row,dict(row,event_id="f:e2")]
    out=_normalize(rows,"v2","L1",raw,[{"start":0,"status":"supported"}])
    assert len(out)==2
    assert {e["ir_event_id"] for e in out} == {"f:e1","f:e2"}
    assert len(_normalize([row,row],"v2","L1",raw,[]))==1


def test_same_start_real_definition_precedes_entry_without_changing_start_order():
    def e(i,start,end,tags=()):
        return dict(event_id=i,span=[start,end],name="c",kind="DEF",tags=list(tags))
    entry=e("entry",10,16,["entry_initialization"])
    actual=e("actual",10,25)
    reference=e("reference",10,24)
    matched,extra,missing=match_spans([entry,actual],[reference])
    assert matched[0][0]["event_id"]=="actual"
    assert [e["event_id"] for e in extra]==["entry"]
    assert not missing
    early=e("earlier",9,12,["entry_initialization"])
    assert match_spans([actual,early],[reference])[0][0][0]["event_id"]=="earlier"


def test_scope_rename_requires_unique_exact_declaration_identity():
    source="contract C { function f() public { uint x = 1; uint x_scope_0 = 2; } }"
    ast=SourceFacts(source)
    start=source.index("uint x =")
    renamed=ast.reference_name("x_scope_2",[start,start+10])
    assert renamed["source_name"]=="x"
    assert renamed["original_name"]=="x_scope_2"
    assert ast.reference_name("x_scope_2",[start+1,start+10]) is None
    assert ast.reference_name("other_scope_2",[start,start+10]) is None
    real=source.index("uint x_scope_0")
    assert ast.reference_name("x_scope_0",[real,real+14]) is None
    assert ast.reference_name("x_scope_0",None) is None


@pytest.mark.parametrize("expression",["delete x","delete a[k]","delete a"])
def test_delete_write_base_read_uses_exact_operator_ast(expression):
    source="contract C { uint x; uint[] a; function f(uint k) public { %s; } }" % expression
    ast=SourceFacts(source)
    name="x" if expression.endswith(" x") else "a"
    start=source.index(expression)
    occurrence=next(n for n in ast.nodes if n.start_byte==start and
                    n.end_byte==start+len(expression) and n.type in ("unary_expression","array_access"))
    write=dict(event_id="w",layer="L2",name=name,kind="WRITE",
               span=ast.interval(occurrence),declaration=None,tags=[],function_scope="supported",
               evidence=[{"occurrence":{"start":occurrence.start_byte,"end":occurrence.end_byte}}])
    reference=dict(write,event_id="r",kind="READ",evidence=[])
    assert classify(reference,"FN",ast,[write],[])[0]=="write_base_read"


def test_non_delete_unary_and_wrong_root_do_not_classify_write_base_read():
    source="contract C { uint x; function f() public { !x; } }"
    ast=SourceFacts(source)
    n=node(ast,"unary_expression","!x")
    write=dict(event_id="w",layer="L2",name="x",kind="WRITE",
               span=ast.interval(n),declaration=None,tags=[],function_scope="supported",
               evidence=[{"occurrence":{"start":n.start_byte,"end":n.end_byte}}])
    assert not ast.root_is_chain(write)
    source=source.replace("!x","delete x")
    ast=SourceFacts(source)
    n=node(ast,"unary_expression","delete x")
    write.update(name="not_x",span=ast.interval(n),evidence=[{"occurrence":{
        "start":n.start_byte,"end":n.end_byte}}])
    assert not ast.root_is_chain(write)


def test_delete_identifier_occurrence_requires_exact_parent_and_root():
    source="contract C { uint x; function f() public { delete x; x = 0; } }"
    ast=SourceFacts(source)
    identifiers=[n for n in ast.nodes if n.type=="identifier" and ast.text(n)=="x"]
    def write(n):
        return dict(event_id="w",layer="L2",name="x",kind="WRITE",
               span=ast.interval(n),declaration=None,tags=[],function_scope="supported",
               evidence=[{"occurrence":{"start":n.start_byte,"end":n.end_byte}}])
    deleted=next(n for n in identifiers if n.parent.type=="unary_expression")
    assigned=next(n for n in identifiers if n.start_byte==source.index("x = 0"))
    assert ast.root_is_chain(write(deleted))
    assert not ast.root_is_chain(write(assigned))
    wrong=write(deleted);wrong["name"]="another"
    assert not ast.root_is_chain(wrong)


def test_write_base_read_rejects_different_declaration(ast):
    e=event(ast,layer="L2",name="m",kind="READ",site="m[p] = x;",
            declaration="mapping(uint=>uint) m;")
    span=interval(ast,"array_access","m[p]")
    w=dict(e,event_id="w",kind="WRITE",span=span,declaration=[1,2],
           evidence=[{"occurrence":{"start":span[0],"end":span[1]}}])
    assert classify(e,"FN",ast,[w],[])[0]=="other"
