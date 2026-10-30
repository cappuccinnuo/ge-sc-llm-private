"""Declaration-level regression cases; grammar checks are not solc compilation."""
import pytest
from scripts.DFG.dfg_v2.benchmark_v2.anon_binding import (
    anonymize, RESERVED, KEYWORD_STRINGS, replace_spans,
)

def build(body, version="0.5.11"):
    return "pragma solidity " + version + "; contract C { " + body + " }"

def ok(source):
    result = anonymize(source)
    assert result["status"] == "renamed", result["issues"]
    return result

def edits_for(result, old):
    return [e for e in result["edits"] if e["old"] == old]

def test_shadowed_declarations_are_distinct_and_references_bind():
    r = ok(build("function f(uint amount) public returns(uint) { { uint amount=2; amount++; } return amount; }"))
    a = edits_for(r, "amount")
    assert len(a) == 4
    assert a[0]["new"] == a[-1]["new"]
    assert a[1]["new"] == a[2]["new"]
    assert a[0]["new"] != a[1]["new"]

def test_equal_spelling_in_other_contracts_has_separate_binding():
    r = ok("pragma solidity 0.5.11; contract A { uint amount; function f() public { amount++; } } contract B { uint amount; function f() public { amount++; } }")
    a=edits_for(r, "amount")
    assert len(a)==4 and a[0]["new"]==a[1]["new"] and a[2]["new"]==a[3]["new"]
    assert a[0]["new"]!=a[2]["new"]

def test_old_constructor_aliases_contract():
    r=ok("pragma solidity 0.4.24; contract C { function C() public {} function make() public { C c = new C(); } }")
    assert len({e["new"] for e in edits_for(r,"C")})==1
    assert [d["role"] for d in r["declarations"]].count("function")==1

def test_preserved_user_transfer_and_globals():
    source=build("function transfer(uint amount) public { require(msg.sender != tx.origin); transfer(amount); msg.sender.transfer(amount); }")
    r=ok(source)
    assert "transfer" in r["preserved_counts"] and not edits_for(r,"transfer")
    assert all(source.count(s)==r["rewritten"].count(s) for s in KEYWORD_STRINGS)

def test_comment_and_string_bytes_unchanged():
    r=ok(build('// amount stays\nstring text = "amount C f"; function f(uint amount) public { amount++; }'))
    assert '// amount stays' in r["rewritten"] and '"amount C f"' in r["rewritten"]

def test_uniform_prefix_permutation_and_reproducibility():
    s=build("uint foo; event Ev(uint param); function f(uint amount) public returns(uint result) { uint local=amount; return local; }")
    r=ok(s)
    assert r==anonymize(s)
    numbers=[int(r["names"][d["id"]][1:]) for d in r["declarations"] if not d["preserved"]]
    assert len(numbers)==len(set(numbers)) and numbers!=sorted(numbers)
    assert all(v.startswith("v") and v[1:].isdigit() for v in r["names"].values())
    assert set(d["role"] for d in r["declarations"]) >= {"contract","function","parameter","return","state","event","local"}

def test_collision_avoidance_existing_v_name():
    r=ok(build("uint v0; function f() public { v0++; }"))
    assert "v0" not in r["names"].values()

@pytest.mark.parametrize("body", [
    "uint amount; function f() public { unknown(amount); }",
    "function f(uint amount) public { assembly { pop(amount) } }",
    "function f(uint a) public {} function f(address a) public {}",
    "function f(uint amount) public { uint amount=amount; }",
])
def test_uncertain_file_has_no_partial_edits(body):
    s=build(body)
    r=anonymize(s)
    assert r["status"]=="fallback" and r["issues"]
    assert r["rewritten"]==s and r["edits"]==[] and r["bindings"]==[]

def test_imports_fail_closed():
    s='pragma solidity 0.5.11; import "Other.sol"; contract C { uint amount; }'
    r=anonymize(s)
    assert r["status"]=="fallback" and r["rewritten"]==s

def test_unknown_version_is_not_guessed():
    s="contract C { function f(uint amount) public { amount++; } }"
    r=anonymize(s)
    assert r["status"]=="fallback" and r["edits"]==[]

def test_struct_enum_and_named_fields():
    r=ok(build("struct S { uint amount; } enum E { A, B } S item; E chosen; function f() public { item.amount=2; chosen=E.A; }"))
    assert len({e["new"] for e in edits_for(r,"amount")})==1
    assert len({e["new"] for e in edits_for(r,"A")})==1

def test_known_object_member_and_return_type():
    r=ok("pragma solidity 0.5.11; contract A { function get() public returns(uint) {return 2;} } contract C { A obj; function f() public returns(uint) {return obj.get();} }")
    assert len({e["new"] for e in edits_for(r,"get")})==1

def test_unknown_member_cannot_bind_by_matching_name_elsewhere():
    s=build("uint amount; function get() public {} function f() public { amount.get(); }")
    assert anonymize(s)["status"]=="fallback"

def test_reserved_table_has_required_spellings():
    assert {"gasprice","sender","origin","transfer","push","pop","balance","code","sha3"} <= RESERVED

def test_stale_edit_is_rejected():
    with pytest.raises(ValueError):
        replace_spans("uint amount;",[dict(start=5,end=11,old="wrong",new="v1")])
