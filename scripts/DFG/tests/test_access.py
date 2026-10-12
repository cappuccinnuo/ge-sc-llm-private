import pytest
from scripts.DFG.frontend import parse_source, walk, text
from scripts.DFG.symbol_table import SymbolTable
from scripts.DFG.access_extractor import AccessExtractor
from scripts.DFG.models import Unsupported

def make_context(body, params="uint x, uint y", returns="uint z"):
    s="pragma solidity ^0.5.17; contract C {uint state; function f("+params+") public returns("+returns+") {"+body+"}}"
    view=parse_source(s)
    fn=view.functions[0]
    table=SymbolTable(s,view.file,fn,view.mode)
    ex=AccessExtractor(s,table)
    return view,fn,table,ex

def statement(body):
    v,f,t,e=make_context(body)
    n=f.child_by_field_name("body").named_children[0]
    events=e.extract(n)
    names=lambda ids:{t.symbols[s].name for s in ids}
    return names(events[0].reads),names(events[0].writes)

@pytest.mark.parametrize("code,reads,writes",[
    ("x=y;",{"y"},{"x"}),("x=x+1;",{"x"},{"x"}),
    ("x+=y;",{"x","y"},{"x"}),("++x;",{"x"},{"x"}),
    ("x--;",{"x"},{"x"}),("delete x;",set(),{"x"}),
    ("(x,y)=(y,x);",{"x","y"},{"x","y"}),
    ("uint a=x+y;",{"x","y"},{"a"}),
    ("uint a;",set(),{"a"}),
    ("x=state;",set(),{"x"}),
    ("return;",{"z"},set()),
    ("return x;",{"x"},set()),
    ("x = uint(y);",{"y"},{"x"}),
    ("require(x>y);",{"x","y"},set()),
])
def test_reads_before_writes(code,reads,writes):
    assert statement(code)==(reads,writes)

@pytest.mark.parametrize("body",["x=f(x++,y);", "x=(y=1);", "x>0 && ++y>0;"])
def test_nested_side_effects_fall_back(body):
    with pytest.raises(Unsupported): statement(body)

def test_entry_defaults_and_return_symbols():
    v,f,t,e=make_context("uint a;")
    assert {t.symbols[x].name for x in e.entry(f).writes}=={"x","y","z"}
    assert e.extract(f.child_by_field_name("body").named_children[0])[0].writes

def test_commented_bare_return_keeps_named_return_use():
    assert statement("return /* c */;")==({"z"},set())

def test_legacy_revert_parenthesized_argument_reads():
    assert statement("revert(string(abi.encodePacked(x)));")==({"x"},set())
