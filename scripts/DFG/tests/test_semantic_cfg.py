from scripts.DFG.frontend import parse_source
from scripts.DFG.semantic_cfg import analyze

def make_ir(body):
    v=parse_source("pragma solidity ^0.5.17; contract C {function f(uint x,bool p) public returns(uint) {"+body+"}}")
    a=analyze(v)
    assert len(a.functions)==1,a.diagnostics
    return v,a.functions[0]

def code(view,event):
    return view.raw[event.anchor.start:event.anchor.end].decode()

def reach(ir,start):
    seen=set(); todo=[start]
    while todo:
        x=todo.pop()
        if x not in seen:
            seen.add(x); todo.extend(ir.blocks[x].successors)
    return seen

def block_for(view,ir,source):
    return next(k for k,b in ir.blocks.items()
                if any(code(view,e)==source for e in b.events))

def test_return_has_no_path_to_following_assignment():
    v,ir=make_ir("if(p){return x;} x=2; return x;")
    returns=[k for k,b in ir.blocks.items()
             if any(e.kind=="return" for e in b.events)]
    target=block_for(v,ir,"x=2;")
    assert all(target not in reach(ir,k) for k in returns)

def test_for_continue_routes_through_update():
    v,ir=make_ir("for(uint i=0;i<x;i++){if(p)continue; x=x+1;} return x;")
    updates=[k for k,b in ir.blocks.items() if any(e.kind=="update" for e in b.events)]
    assert len(updates)==1
    # Both the normal tail and a continue jump must reach the update.
    incoming=[k for k,b in ir.blocks.items() if updates[0] in b.successors]
    assert len(incoming)==2

def test_do_while_body_before_condition():
    v,ir=make_ir("do{x=3;}while(p); return x;")
    assign=block_for(v,ir,"x=3;")
    first=next(iter(ir.blocks[ir.entry].successors))
    assert first!=assign
    assert ir.blocks[first].successors=={assign}

def test_infinite_for_has_no_normal_exit():
    v,ir=make_ir("for(;;){x++;} return x;")
    assert block_for(v,ir,"return x;") not in reach(ir,ir.entry)

def test_unsupported_function_retained_as_fallback():
    v=parse_source("pragma solidity ^0.5.17; contract C {function f() public {assembly {let x := 1}} function g(uint x) public returns(uint){return x;}}")
    result=analyze(v)
    assert len(v.functions)==2 and len(result.functions)==1
    assert any(d["kind"]=="function_fallback" for d in result.diagnostics)

def test_nested_side_effect_condition_fallback():
    v=parse_source("pragma solidity ^0.5.17; contract C {function f(uint x,uint y) public {if(x>0 && ++y>0){x=2;}}}")
    result=analyze(v)
    assert not result.functions and result.diagnostics[0]["kind"]=="function_fallback"

def test_commented_throw_and_for_condition():
    v,ir=make_ir("throw /*c*/; x=2; return x;")
    assert block_for(v,ir,"x=2;") not in reach(ir,ir.entry)
    v,ir=make_ir("for(;/*c*/x>0;){x--;} return x;")
    cond=[e for b in ir.blocks.values() for e in b.events if e.kind=="condition"]
    assert len(cond)==1 and {ir.symbols[s].name for s in cond[0].reads}=={"x"}

def test_shadowed_terminator_falls_back_instead_of_false_unreachable():
    v=parse_source("pragma solidity ^0.5.17; contract C {function revert(uint x) internal pure returns(uint){return x;} function f(uint x) public returns(uint y){revert(x);y=x;return y;}}")
    r=analyze(v)
    assert any(d["kind"]=="function_fallback" and "shadowed" in d["reason"] for d in r.diagnostics)
