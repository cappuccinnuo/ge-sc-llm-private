"""Exact binding and exclusion tests for the EP0c production resolver."""
import hashlib
from pathlib import Path
import pytest
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.node_sem.facts_ast import AstSemantics, key
from scripts.edge_sem.call_resolve import resolve_call, FROZEN_AST_SHA256


def semantics(source):
    return AstSemantics(ProjectionView("pragma solidity ^0.5.11; "+source, "fixture.sol"))


def call(sem, text):
    matches = [n for n in sem.nodes if n.type == "call_expression" and sem.text(n) == text]
    assert len(matches) == 1, (text, [sem.text(n) for n in matches])
    return matches[0]


def resolve(sem, text):
    return resolve_call(sem, call(sem, text))


def test_frozen_dependency_hash():
    root = Path(__file__).resolve().parents[3]
    assert hashlib.sha256((root/"scripts/node_sem/facts_ast.py").read_bytes()).hexdigest() == FROZEN_AST_SHA256


def test_internal_inherited_and_modifier_body():
    sem = semantics("contract Base { function base(uint x) internal {} } "
        "contract C is Base { function g() internal {} modifier m(){g(); _;} "
        "function f() public m {base(1);} }")
    assert resolve(sem, "g()")["kind"] == "internal"
    row = resolve(sem, "base(1)")
    assert row["kind"] == "inherited"
    assert sem.text(row["target"].child_by_field_name("name")) == "base"
    assert sem.owner(call(sem, "g()")).type == "modifier_definition"


def test_library_direct_and_using():
    sem = semantics("library SafeMath {function sub(uint a,uint b) internal pure returns(uint){return a-b;}} "
        "contract C {using SafeMath for uint; function f(uint a,uint b) public {SafeMath.sub(a,b); a.sub(b);} }")
    a, b = resolve(sem, "SafeMath.sub(a,b)"), resolve(sem, "a.sub(b)")
    assert a["kind"] == b["kind"] == "library"
    assert key(a["target"]) == key(b["target"])


def test_arity_only_disambiguation():
    sem = semantics("contract C {function g(uint a) internal returns(uint){return a;} "
        "function g(uint a,uint b) internal {} function f() public {g(1);g(1,2);g();}}")
    assert resolve(sem, "g(1)")["kind"] == resolve(sem, "g(1,2)")["kind"] == "overload_arity"
    assert key(resolve(sem, "g(1)")["target"]) != key(resolve(sem, "g(1,2)")["target"])
    assert resolve(sem, "g()")["status"] == "overload_unresolved"


def test_same_arity_and_shadowing_are_not_guessed():
    sem = semantics("contract C {function g(uint a) internal {} function g(address a) internal {} "
        "function f() public {g(1);} function h(uint g) public {g(2);}}")
    assert resolve(sem, "g(1)")["status"] == "overload_unresolved"
    assert resolve(sem, "g(2)")["target"] is None


@pytest.mark.parametrize("expr", [
    "msg.sender.transfer(1)", "owner.send(1)", "tx.origin.call(1)",
    "address(owner).delegatecall(1)", "payable(owner).staticcall(1)"])
def test_address_builtins_do_not_bind_same_name_functions(expr):
    sem = semantics("contract C {address payable owner; function transfer(uint a) internal {} "
        "function send(uint a) internal {} function f() public {"+expr+";}}")
    row = resolve(sem, expr)
    assert row["status"] == "address_builtin"
    assert row["target"] is None


@pytest.mark.parametrize("expr,expected", [
    ("ERC20Interface(token).transfer(a,b)", "cast_member"),
    ("token.transfer(a,b)", "external_member"), ("this.f(a,b)", "external_member"),
    ("new Other()", "new_contract"), ("super.base()", "super"),
    ("require(a>0)", "builtin"), ("keccak256(data)", "builtin"), ("Event(a)", "event_or_struct")])
def test_exclusions(expr, expected):
    sem = semantics("interface ERC20Interface {function transfer(uint a,uint b) external;} "
        "contract Base {function base() internal {}} contract Other {} "
        "contract C is Base {ERC20Interface token; event Event(uint a); "
        "function f(uint a,uint b) public {bytes memory data; "+("emit " if expr=="Event(a)" else "")+expr+";}}")
    row = (resolve_call(sem, next(n for n in sem.nodes if n.type == "emit_statement"))
           if expr == "Event(a)" else resolve(sem, expr))
    assert row["status"] == expected and row["target"] is None


def test_unconfirmed_receiver_and_address_prefix_are_unknown():
    sem = semantics("contract addressBook {function transfer(uint a) public {}} "
        "contract C {addressBook book; function f(uint x) public {book.transfer(1);x.transfer(1);}}")
    assert resolve(sem, "book.transfer(1)")["status"] == "external_member"
    assert resolve(sem, "x.transfer(1)")["status"] == "unknown"


def test_rename_preserves_targets_and_kinds():
    source = ("library L {function sub(uint x,uint y) internal returns(uint){return x-y;}} "
        "contract B {function h() internal {}} contract C is B {using L for uint; "
        "address payable owner; function g(uint x) internal {} function g(uint x,uint y) internal {} "
        "modifier m(){h();_;} function f(uint a,uint b) public m {L.sub(a,b);a.sub(b);g(a);g(a,b);owner.send(a);} }")
    first = semantics(source)
    # Replace identifiers by AST token spans, never by substring.
    names = ("L", "sub", "x", "y", "B", "h", "C", "owner", "g", "m", "f", "a", "b")
    mapping = {name: "v"+str(i) for i,name in enumerate(names)}
    raw = first.view.raw
    spans = [(n.start_byte,n.end_byte,mapping[first.text(n)].encode())
             for n in first.nodes if n.type in ("identifier", "type_alias", "user_defined_type")
             and first.text(n) in mapping and not n.named_children]
    for start,end,value in sorted(set(spans), reverse=True):
        raw = raw[:start]+value+raw[end:]
    second = AstSemantics(ProjectionView(raw.decode(), "renamed.sol"))
    a = [n for n in first.nodes if n.type == "call_expression"]
    b = [n for n in second.nodes if n.type == "call_expression"]
    assert len(a) == len(b)
    for x,y in zip(a,b):
        r,s = resolve_call(first,x),resolve_call(second,y)
        assert (r["status"],r["kind"]) == (s["status"],s["kind"])
        if r["target"] is not None:
            assert first.functions.index(r["target"]) == second.functions.index(s["target"])
        else:
            assert s["target"] is None

def test_composite_callee_resolves_with_frozen_postfix_binding():
    sem = semantics("contract C {function ready() internal returns(bool){return true;} "
        "function f() public {if(!ready()){return;}}}")
    row = resolve(sem, "!ready()")
    assert (row["status"], row["kind"], row["reason"]) == ("resolved", "internal", "postfix_callee")
    assert sem.text(row["target"].child_by_field_name("name")) == "ready"


def test_calls_inside_emit_arguments_are_still_internal_calls():
    sem = semantics("contract C {event E(uint v); function g() internal returns(uint){return 1;} "
        "function f() public {emit E(g());}}")
    assert resolve(sem, "g()")["kind"] == "internal"
    emit = next(n for n in sem.nodes if n.type == "emit_statement")
    assert resolve_call(sem, emit)["target"] is None


def test_struct_constructor_has_no_function_target():
    sem = semantics("contract C {struct Data{uint a;} function f() public {Data(1);}}")
    assert resolve(sem, "Data(1)")["status"] == "event_or_struct"


def test_function_return_receiver_is_not_assumed_contract_cast():
    sem = semantics("contract C {function object() internal returns(address){return msg.sender;} "
        "function f() public {object().transfer(1);}}")
    assert resolve(sem, "object().transfer(1)")["status"] == "unknown"


def test_reference_classes_preserve_unknowns_and_exact_target_identity():
    from scripts.edge_sem.recon.ep0c_calls import classify_reference
    a,b = [1,2,"function_definition"],[3,4,"function_definition"]
    def candidate(status,target=None):
        return dict(status=status,target_anchor=target)
    assert classify_reference(a,[candidate("resolved",a)])[0] == "internal_confirmed"
    assert classify_reference(a,[candidate("resolved",b)])[0] == "rebinding"
    assert classify_reference(a,[candidate("address_builtin")])[0] == "not_internal"
    assert classify_reference(a,[candidate("address_builtin"),candidate("unknown")])[0] == "undetermined"
    assert classify_reference(a,[candidate("super")])[0] == "undetermined"
    assert classify_reference(a,[])[0] == "no_expression"
    assert classify_reference(a,[],False)[0] == "undetermined"

@pytest.mark.parametrize("expr,target_name", [
    ("!isOwner(msg.sender)", "isOwner"),
    ("!_check(a)", "_check"),
    ("x >= y + findOnePercent(y)", "findOnePercent"),
])
def test_postfix_internal_targets(expr,target_name):
    sem = semantics("contract C {function isOwner(address a) internal returns(bool){return true;} "
        "function _check(uint a) internal returns(bool){return true;} "
        "function findOnePercent(uint a) internal returns(uint){return a;} "
        "function f(uint a,uint x,uint y) public {require(!isOwner(msg.sender));"
        "if (!_check(a)) revert(); bool ok = x >= y + findOnePercent(y);}}")
    row = resolve(sem,expr)
    assert (row["status"],row["kind"],row["reason"]) == ("resolved","internal","postfix_callee")
    assert sem.text(row["target"].child_by_field_name("name")) == target_name


@pytest.mark.parametrize("expr", ["!SafeMath.lt(a,b)", "-a.negate()"])
def test_postfix_direct_and_extension_library(expr):
    sem = semantics("library SafeMath {function lt(int a,int b) internal returns(bool){return a<b;} "
        "function negate(int a) internal returns(int){return -a;}} "
        "contract C {using SafeMath for int; function f(int a,int b) public {"+expr+";}}")
    row = resolve(sem,expr)
    assert (row["status"],row["kind"],row["reason"]) == ("resolved","library","postfix_callee")


def test_negative_bare_call_in_library():
    sem = semantics("library L {function negate(int a) internal returns(int){return -a;} "
        "function f(int a) internal returns(int){return -negate(a);}}")
    assert resolve(sem,"-negate(a)")["kind"] == "library"


def test_postfix_overload_arity_and_same_arity_remain_distinct():
    sem = semantics("contract C {function f(uint a) internal returns(bool){return true;} "
        "function f(uint a,uint b) internal returns(bool){return true;} "
        "function run(uint a,uint b) public {!f(a);!f(a,b);}}")
    a,b = resolve(sem,"!f(a)"),resolve(sem,"!f(a,b)")
    assert a["kind"] == b["kind"] == "overload_arity"
    assert a["reason"] == b["reason"] == "postfix_callee"
    assert key(a["target"]) != key(b["target"])
    sem = semantics("contract C {function f(uint a) internal returns(bool){return true;} "
        "function f(address a) internal returns(bool){return true;} "
        "function run(uint a) public {!f(a);}}")
    row = resolve(sem,"!f(a)")
    assert row["status"] == "overload_unresolved" and row["target"] is None


@pytest.mark.parametrize("expr,status",[
    ("!msg.sender.send(v)","address_builtin"),
    ("!token.check(v)","external_member"),
    ("!super.check(v)","super"),
])
def test_postfix_does_not_resolve_external_or_super(expr,status):
    sem = semantics("contract B {function check(uint x) internal returns(bool){return true;}} "
        "interface Token {function check(uint x) external returns(bool);} "
        "contract C is B {Token token; function send(uint v) internal returns(bool){return true;} "
        "function f(uint v) public {"+expr+";}}")
    row = resolve(sem,expr)
    assert row["status"] == status and row["target"] is None


def test_postfix_preserves_inherited_target():
    sem = semantics("contract B {function check(uint a) internal returns(bool){return true;}} "
        "contract C is B {function f(uint a) public {!check(a);}}")
    assert resolve(sem,"!check(a)")["kind"] == "inherited"


def test_postfix_rename_preserves_binding_identity():
    source = ("library L {function less(uint x,uint y) internal returns(bool){return x<y;}} "
        "contract B {function allowed(uint x) internal returns(bool){return true;}} "
        "contract C is B {using L for uint; address payable receiver; "
        "function f(uint x) internal returns(bool){return true;} "
        "function f(uint x,uint y) internal returns(bool){return true;} "
        "function run(uint a,uint b) public {!allowed(a);!f(a);!f(a,b);!L.less(a,b);!a.less(b);!receiver.send(a);}}")
    first=semantics(source)
    reserved={"msg","tx","block","this","super","send"}
    names=sorted({first.text(n) for n in first.nodes if n.type=="identifier"}-reserved)
    replacements={name:"renamed_"+str(i) for i,name in enumerate(names)}
    raw=first.view.raw
    spans={(n.start_byte,n.end_byte,replacements[first.text(n)].encode())
           for n in first.nodes if not n.named_children and first.text(n) in replacements}
    for start,end,value in sorted(spans,reverse=True):
        raw=raw[:start]+value+raw[end:]
    second=AstSemantics(ProjectionView(raw.decode(),"renamed.sol"))
    a=[n for n in first.nodes if n.type=="call_expression"]
    b=[n for n in second.nodes if n.type=="call_expression"]
    assert len(a)==len(b)==6
    for x,y in zip(a,b):
        old,new=resolve_call(first,x),resolve_call(second,y)
        assert (old["status"],old["kind"],old["reason"]) == (new["status"],new["kind"],new["reason"])
        if old["target"] is not None:
            assert first.functions.index(old["target"]) == second.functions.index(new["target"])
        else:
            assert new["target"] is None


@pytest.mark.parametrize("task",["reentrancy_node","access_control_node"])
def test_real_ep0c_calls_adapter_equivalence(task):
    from scripts.edge_sem.recon.ep0d_equivalence import audit_task
    rows=audit_task(task)
    assert rows and sum(r["eligible"] for r in rows)>0
    assert all(r["all_equal"] and r["prior_calls"]==r["eligible"]+r["ineligible"] for r in rows)


def test_postfix_address_receiver_keeps_shadow_checks():
    sem = semantics("contract C {struct Environment {address sender;} Environment msg; "
        "function send(uint a) internal returns(bool){return true;} "
        "function f(uint a) public {!msg.sender.send(a);}}")
    row = resolve(sem,"!msg.sender.send(a)")
    assert row["status"] == "unknown" and row["target"] is None


def test_postfix_address_receiver_does_not_guess_unknown_type():
    sem = semantics("contract C {function send(uint a) internal returns(bool){return true;} "
        "function f(uint a,uint receiver) public {!receiver.send(a);}}")
    row = resolve(sem,"!receiver.send(a)")
    assert row["status"] == "unknown" and row["target"] is None
