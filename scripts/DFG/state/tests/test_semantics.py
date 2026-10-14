"""Parser/semantic regressions, not claims of solc compilation or vulnerability truth."""
import pytest
from dataclasses import replace
from scripts.DFG.state.analyzer import analyze_source
from scripts.DFG.state.locations import alias
from scripts.DFG.state.reaching_definitions import solve
from scripts.DFG.models import Unsupported

def run(body,decl="uint x; uint y; mapping(uint=>uint) m; mapping(address=>uint) b;",params="bool c, uint k, uint j, address payable to",extra=""):
    source="pragma solidity ^0.5.17; contract C {"+decl+" function f("+params+") public {"+body+"}"+extra+"}"
    view,results=analyze_source(source,"case.sol")
    return view,results[0]

def events(result,kind):
    return [e for bid,es in result.ir.events.items() if bid in result.reachable for e in es if e.kind==kind]

def fragment(view,event):
    a=event.anchor
    return view.raw[a.start:a.end].decode()

def pairs(view,result):
    return {(fragment(view,f.definition),fragment(view,f.use),f.certainty) for f in result.facts}

def test_scalar_strong_kill_and_direct_not_transitive():
    v,r=run("x=1; x=2; y=x; require(y>0);")
    assert r.status=="supported_subset"
    p=pairs(v,r)
    assert ("x=2;","y=x;","EXACT") in p
    assert ("y=x;","require(y>0);","EXACT") in p
    assert not any(a=="x=1;" or (a=="x=2;" and b=="require(y>0);") for a,b,_ in p)
    assert not r.unknown_reads
    assert all(f.cfg_witness and f.path_status=="cfg_reachable_path_conditions_not_solved" for f in r.facts)

def test_entry_unknown_has_no_fabricated_definition():
    _,r=run("require(x>0); x=0;")
    assert len(r.unknown_reads)==1 and r.unknown_reads[0]["origin"].startswith("ENTRY_UNKNOWN:")
    assert not r.facts

def test_branch_union_and_entry_alternative():
    v,r=run("if(c){x=1;}else{x=2;} require(x>0);")
    assert {a for a,b,_ in pairs(v,r) if b=="require(x>0);"}=={"x=1;","x=2;"}
    _,r=run("if(c){x=1;} require(x>0);")
    assert len(r.facts)==1 and len(r.unknown_reads)==1

def test_loop_fixpoint_and_unreachable_writes():
    v,r=run("x=0; while(c){x+=1;} require(x>0); return; x=99;")
    assert r.status=="supported_subset"
    assert any(a=="x+=1;" and b=="x+=1;" for a,b,_ in pairs(v,r))
    assert any(a=="x+=1;" and b=="require(x>0);" for a,b,_ in pairs(v,r))
    assert not any(a=="x=99;" for a,_,_ in pairs(v,r))

@pytest.mark.parametrize("op",["x+=2;","x-=2;","x++;","--x;"])
def test_read_modify_write(op):
    v,r=run("x=1;"+op+"require(x>0);")
    assert ("x=1;",op,"EXACT") in pairs(v,r)
    assert (op,"require(x>0);","EXACT") in pairs(v,r)
    assert not r.unknown_reads

def test_delete_is_a_strong_definition():
    v,r=run("x=1; delete x; require(x==0);")
    assert pairs(v,r)=={("delete x;","require(x==0);","EXACT")}

def test_constants_distinct_and_mapping_identity():
    v,r=run("m[1]=7; m[2]=9; require(m[1]>0);")
    assert pairs(v,r)=={("m[1]=7;","require(m[1]>0);","EXACT")}
    locs=list(r.ir.locations.values())
    assert alias(locs[0],locs[1])=="NO_ALIAS"

def test_same_frame_sender_and_environment_not_state():
    v,r=run("b[msg.sender]=7; require(b[msg.sender]>0); require(block.timestamp>k);")
    assert ("b[msg.sender]=7;","require(b[msg.sender]>0);","EXACT") in pairs(v,r)
    assert all(l.root.name=="b" for l in r.ir.locations.values())
    assert any(e.detail=="block.timestamp" for e in events(r,"ENVIRONMENT"))

def test_parameter_keys_may_alias_without_false_kill():
    v,r=run("m[k]=1; m[j]=2; require(m[k]>0);")
    p=pairs(v,r)
    assert ("m[k]=1;","require(m[k]>0);","EXACT") in p
    assert ("m[j]=2;","require(m[k]>0);","MAY") in p

def test_reassigned_key_is_unknown_not_same_by_name():
    v,r=run("m[k]=1; k=2; require(m[k]>0);")
    assert r.facts and all(f.certainty=="MAY" for f in r.facts)
    assert r.unknown_reads
    assert all(l.certainty=="UNKNOWN" for l in r.ir.locations.values())

def test_shadowing_parameter_and_block_local():
    v,r=run("x=1; {uint x=2; x++;} require(x>0);")
    assert pairs(v,r)=={("x=1;","require(x>0);","EXACT")}
    _,r=run("owner=2; require(owner>0);",decl="uint owner;",params="uint owner")
    assert not r.ir.locations and not r.facts

def test_same_name_different_contract_identity():
    src="pragma solidity ^0.5.17; contract A {uint x; function f() public {x=1;require(x>0);}} contract B {uint x;function f() public {x=2;require(x>0);}}"
    _,rs=analyze_source(src)
    assert len(rs)==2
    a,b=[next(iter(r.ir.locations.values())) for r in rs]
    assert alias(a,b)=="NO_ALIAS" and a.root.id!=b.root.id

@pytest.mark.parametrize("call",['to.call("");','to.send(k);','to.transfer(k);','to.call.value(k)("");'])
def test_external_havoc_suppresses_stale_definitions(call):
    v,r=run("x=1;"+call+"require(x>0); x=3;require(x>1);")
    assert r.status=="supported_subset"
    assert len(events(r,"HAVOC"))==1
    assert not any(a=="x=1;" for a,_,_ in pairs(v,r))
    assert ("x=3;","require(x>1);","EXACT") in pairs(v,r)
    assert any(u["origin"].startswith("HAVOC:") for u in r.unknown_reads)

def test_call_configuration_is_not_an_external_invocation():
    v,r=run("x=1; to.call.value(k); require(x>0);")
    assert not events(r,"HAVOC") and len(events(r,"CALL_CONFIGURATION"))==1
    assert ("x=1;","require(x>0);","EXACT") in pairs(v,r)

def test_unknown_call_havoc_and_arguments_read_before_effect():
    v,r=run("x=1; unknown(x); require(x>0);",extra="function unknown(uint a) internal {}")
    assert ("x=1;","unknown(x);","EXACT") in pairs(v,r)
    assert not any(b=="require(x>0);" for _,b,_ in pairs(v,r))
    assert events(r,"HAVOC")[0].detail.startswith("UNKNOWN_CALL")

def test_require_user_shadow_is_not_assumed_pure():
    _,r=run("x=1; require(x); require(x);",extra="function require(uint a) internal {}")
    assert len(events(r,"HAVOC"))==2

@pytest.mark.parametrize("body",["x=1; return; x=2; require(x>0);",
                              "x=1; revert(); x=2; require(x>0);",
                              "x=1; selfdestruct(to); x=2; require(x>0);"])
def test_termination_keeps_dead_events_out_of_facts(body):
    _,r=run(body)
    assert r.status=="supported_subset" and not r.facts

def test_terminal_arguments_read_before_termination():
    v,r=run("beneficiary=to; selfdestruct(beneficiary);",decl="address payable beneficiary;")
    assert len(r.facts)==1
    assert not events(r,"HAVOC")

@pytest.mark.parametrize("body,decl",[
    ("map[0]=1;","uint[] map;"),
    ("m[1][2]=3;","mapping(uint=>mapping(uint=>uint)) m;"),
    ("x=1; assembly { mstore(0,0) }","uint x;"),
    ("x=1; if(c && unknown()) {x=2;}","uint x;"),
    ("x=1; x = x+unknown();","uint x;"),
])
def test_unsupported_function_has_no_partial_residue(body,decl):
    _,r=run(body,decl=decl,extra="function unknown() internal returns(bool){return true;}")
    assert r.status=="function_fallback" and r.ir is None and not r.facts

def test_fallback_isolated_from_other_function():
    src="pragma solidity ^0.5.17; contract C {uint x;uint[] a;function bad() public{x=1;a[0]=2;} function good() public{x=2;require(x>0);}}"
    _,rs=analyze_source(src)
    assert [r.status for r in rs]==["function_fallback","supported_subset"]
    assert not rs[0].facts and len(rs[1].facts)==1

def test_for_loop_anchor_does_not_duplicate_initial_as_condition():
    v,r=run("x=2; for(uint i=0;i<x;i++){y=x;} require(y>0);")
    assert r.status=="supported_subset"
    reads=events(r,"READ")
    assert any(e.expression.role=="identifier" and v.raw[e.expression.start:e.expression.end]==b"x" and e.anchor.role=="for_statement" for e in reads)

def test_side_table_identity_and_fixpoint_failure_rejected():
    _,r=run("x=1;require(x>0);")
    e=next(e for es in r.ir.events.values() for e in es)
    bid=e.block
    r.ir.events[bid][0]=replace(e,scalar_event="forged")
    with pytest.raises(Unsupported,match="identity"):solve(r.ir)
    _,r=run("x=0;while(c){x++;}")
    with pytest.raises(Unsupported,match="fixpoint"):solve(r.ir,1)

def test_state_declaration_after_function_and_independent_roots():
    source="pragma solidity ^0.5.17; contract C {function f() public {x=1;y=2;require(x>0);} uint x;uint y;}"
    v,rs=analyze_source(source)
    assert len(rs[0].facts)==1
    assert rs[0].facts[0].definition.location.root.name=="x"

def test_unsupported_state_does_not_contaminate_an_independent_function():
    src="pragma solidity ^0.5.17; contract C {uint[] a;uint x;function f() public{x=1;require(x>0);}function g() public{a[0]=1;}}"
    _,rs=analyze_source(src)
    assert rs[0].status=="supported_subset" and len(rs[0].facts)==1
    assert rs[1].status=="function_fallback"

def test_address_balance_is_environment_not_storage():
    _,r=run("require(msg.sender==owner); msg.sender.transfer(address(this).balance);",decl="address owner;")
    assert r.status=="supported_subset"
    assert {e.location.root.name for e in events(r,"READ")}=={"owner"}
    assert len(events(r,"HAVOC"))==1
    assert any(e.detail=="address.balance" for e in events(r,"ENVIRONMENT"))
    assert not r.facts

def test_receiver_state_read_before_unknown_call_and_no_pure_assumption():
    _,r=run("target=to; target.unknown();",decl="address target;")
    assert r.status=="supported_subset"
    assert len(r.facts)==1 and len(events(r,"HAVOC"))==1

def test_environment_shadow_rejected_and_no_masquerade_as_state():
    _,r=run("require(msg.sender==to);",decl="uint msg;")
    assert r.status=="function_fallback" and not r.facts

def test_no_backwards_balance_clear_dependency():
    _,r=run('uint amount=b[msg.sender]; (bool ok,)=to.call.value(amount)(""); require(ok); b[msg.sender]=0;')
    assert r.status=="supported_subset" and not r.facts
    assert len(events(r,"READ"))==1 and len(events(r,"WRITE"))==1
    assert len(events(r,"HAVOC"))==1 and len(r.unknown_reads)==1

def test_unknown_call_multiple_argument_order_falls_back():
    _,r=run("unknown(unknown(),x);",extra="function unknown() internal returns(uint){return 1;}function unknown(uint a,uint b) internal{}")
    assert r.status=="function_fallback"

def test_missing_condition_loop_has_no_fictional_exit_fact():
    _,r=run("for(;;){x=1;}require(x>0);")
    assert r.status=="supported_subset" and not r.facts
