"""Source probes distinguish exact evidence from diagnostic spelling matches."""
import pytest
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.node_sem.facts_ast import AstSemantics
from scripts.edge_sem.recon.ep0b_attributes import shape_safe, declaration_shape, def_kind, write_access, write_op
from scripts.edge_sem.recon.ep0b_calls import gap_category, site_census, call_name, modifier_argument
from scripts.edge_sem.recon.common import key


def semantics(body):
    return AstSemantics(ProjectionView("pragma solidity ^0.4.24; "+body,"x.sol"))


@pytest.mark.parametrize("typ,expected",[
    ("address","address"),("address payable","address"),("addressBook","struct_contract"),
    ("addressBook[]","array"),("mapping(address=>uint)","mapping"),("uint256","integer")])
def test_exact_address_type(typ,expected):
    assert shape_safe(typ)==expected


def test_declaration_identity_and_access_class():
    sem=semantics("contract C { mapping(address=>uint) x; function f(address p) public {x[p] += 1;} }")
    st=next(n for n in sem.nodes if n.type=="expression_statement")
    r=declaration_shape(sem,st,"x")
    assert r["status"]=="resolved" and r["shape"]=="mapping" and r["declaration_count"]==1
    lhs=next(n for n in sem.nodes if n.type=="array_access")
    assert write_access(lhs)=="indexed" and write_op(lhs)=="increase"
    assert def_kind(st)=="compound"
    assert declaration_shape(sem,st,"absent")["status"]=="no_identifier_occurrence"


def test_def_kind_is_assignment_not_increment_heuristic():
    sem=semantics("contract C { function f(uint x) public {x = x + 1; x++; delete x;} }")
    statements=[n for n in sem.nodes if n.type=="expression_statement"]
    assert [def_kind(n)for n in statements]==["assign","incdec_or_delete","incdec_or_delete"]
    lhs=next(n for n in sem.nodes if n.type=="assignment_expression").child_by_field_name("left")
    assert write_op(lhs)=="assign"


def test_missing_expression_and_overload_have_distinct_denominators():
    sem=semantics("contract C { function g(uint x) internal {} function g(address x) internal {} function f() public {g(1);} function h() internal {} }")
    f=next(n for n in sem.functions if sem.text(n.child_by_field_name("name"))=="f")
    g=sem.functions[0];h=sem.functions[-1]
    calls=[n for n in sem.nodes if n.type=="call_expression"]
    assert gap_category(sem,f,g,calls,[])[0]=="overload"
    assert gap_category(sem,f,h,[],[])[0]=="no_call_expression"


def test_statement_to_owner_coverage_is_identity_based():
    sem=semantics("contract C { function g() internal {} function f() public {g(); g();} }")
    raw={i:n for i,n in enumerate(sem.nodes)if n.type in ("function_definition","expression_statement")}
    inverse={key(n):i for i,n in raw.items()}
    records,pairs=site_census(sem,raw,inverse)
    assert len(pairs)==1 and len(next(iter(pairs.values())))==2
    assert sum(r["projected"] for r in records)==2


def test_modifier_argument_retained_as_gap():
    sem=semantics("contract C { modifier m(uint x){_;} function g() internal returns(uint){return 1;} function f() m(g()) public {} }")
    call=next(n for n in sem.nodes if n.type=="call_expression")
    assert modifier_argument(call)
    f=sem.functions[-1];g=sem.functions[1]
    assert gap_category(sem,f,g,[call],[])[0]=="modifier_argument"



def test_negated_call_is_present_even_if_frozen_binding_cannot_resolve_it():
    sem=semantics("contract C { function ready() internal returns(bool){return true;} function f() public {if(!ready()){return;}} }")
    call=next(n for n in sem.nodes if n.type=="call_expression")
    assert call_name(sem,call)=="ready"
    fn=sem.functions[-1]
    assert gap_category(sem,fn,sem.functions[0],[call],[])[0]!="no_call_expression"
