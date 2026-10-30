"""Prompt 8G spelling policy; parser checks do not imply solc validation."""
import copy
import pytest
from scripts.DFG.frontend import parse, walk
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import (
    anonymize, validate, RESERVED, KEYWORD_STRINGS, identifier_rows)
from scripts.DFG.dfg_v2.benchmark_v2.anon_binding import anonymize as declaration_anonymize


def ok(source):
    result = anonymize(source)
    assert result["status"] == "renamed", result["issues"]
    assert validate(source, result)["exact_identifier_selection"]
    return result


def test_shadowing_and_overloads_keep_spelling_equality():
    source = """pragma solidity ^0.5.0;
contract Base { function f(uint amount) public {} }
contract Child is Base {
 function f(uint amount) public { { uint amount=1; amount++; } }
 function f(address amount) public {}
}"""
    result = ok(source)
    assert declaration_anonymize(source)["status"] == "fallback"
    assert len({e["new"] for e in result["edits"] if e["old"] == "amount"}) == 1
    assert len({e["new"] for e in result["edits"] if e["old"] == "f"}) == 1
    assert result["mapping"]["f"] != result["mapping"]["amount"]
    assert not result["binding_resolution_claimed"]


def test_external_undeclared_members_are_selected_without_resolution():
    result = ok("contract C { function f() public { foreign.customMethod(); } }")
    assert {"C", "f", "foreign", "customMethod"} == set(result["mapping"])


def test_old_constructor_follows_same_spelling_without_version_guess():
    result = ok("contract C { function C() public {} function f() public { C other=new C(); } }")
    assert len({e["new"] for e in result["edits"] if e["old"] == "C"}) == 1
    assert not result["compilation_verified"]


def test_only_identifier_ast_nodes_and_unchanged_literals_comments():
    source = 'pragma solidity ^0.5.0; /* amount */ contract C { string note="amount C"; enum E { Member } function f() public { E x=E.Member; } }'
    result = ok(source)
    selected = {(n.start_byte, n.end_byte) for n in walk(parse(source).root_node)
                if n.type == "identifier" and n.text.decode() not in RESERVED}
    assert {(e["start"], e["end"]) for e in result["edits"]} == selected
    assert '/* amount */' in result["rewritten"] and '"amount C"' in result["rewritten"]
    # Literal enum_value nodes are outside the documented identifier-only rule.
    for n in walk(parse(source).root_node):
        if n.type == "enum_value":
            assert (n.start_byte, n.end_byte) not in selected


@pytest.mark.parametrize("name", ["msg", "sender", "origin", "tx", "block", "gasprice", "transfer",
                                  "send", "call", "value", "balance", "length", "push", "pop",
                                  "abi", "keccak256", "selfdestruct", "solidity", "_"])
def test_fixed_meaning_names_preserved_even_when_user_declared(name):
    result = ok("contract C { uint " + name + "; }")
    assert name not in result["mapping"]
    assert name in result["verification"]["preserved_counts"]


def test_keyword_counts_exact():
    source = """contract C { function f(uint amount) public {
require(msg.sender != tx.origin); msg.sender.call.value(amount)();
msg.sender.send(amount); msg.sender.transfer(amount);
} }"""
    result = ok(source)
    assert all(source.count(s) == result["rewritten"].count(s) for s in KEYWORD_STRINGS)


def test_source_sha_seed_is_reproducible_uniform_and_not_occurrence_order():
    source = "contract C { uint first; uint second; uint third; function f(uint arg) public { first=arg; second=first; third=second; } }"
    result = ok(source)
    assert result == anonymize(source)
    assert len(set(result["mapping"].values())) == len(result["mapping"])
    numbers = [int(result["mapping"][name][1:]) for name in result["sorted_spelling_order"]]
    assert numbers != sorted(numbers)
    assert all(v.startswith("v") and v[1:].isdigit() for v in result["mapping"].values())
    assert result["numbering_seed_sha256"] != ok(source+"\n")["numbering_seed_sha256"]


def test_existing_v_spellings_do_not_collide():
    result = ok("contract C { uint v1; uint v2; uint plain; function f() public { plain=v1+v2; } }")
    assert not {"v1", "v2"} & set(result["mapping"].values())


def test_utf8_offsets_and_unchanged_gaps():
    source = '/* 中文 */ contract C { string note="名字"; uint amount; function f() public { amount++; } }'
    result = ok(source)
    assert '/* 中文 */' in result["rewritten"] and '"名字"' in result["rewritten"]


def test_grammar_error_returns_whole_file_identity():
    source = "contract C { function f("
    result = anonymize(source)
    assert result["status"] == "fallback" and result["issues"]
    assert result["rewritten"] == source and not result["edits"] and not result["mapping"]


@pytest.mark.parametrize("mutation", ["missing_edit", "source_sha", "many_to_one", "wrong_token"])
def test_validation_rejects_modified_proof(mutation):
    source = "contract C { uint x; uint y; }"
    result = copy.deepcopy(ok(source))
    if mutation == "missing_edit":
        result["edits"].pop()
    elif mutation == "source_sha":
        result["source_sha256"] = "0"*64
    elif mutation == "many_to_one":
        result["mapping"]["y"] = result["mapping"]["x"]
    else:
        result["edits"][0]["start"] = 0
    with pytest.raises(ValueError):
        validate(source, result)


def test_empty_mapping_still_checked():
    result = ok("pragma solidity ^0.5.0;")
    assert result["mapping"] == {} and result["edits"] == []
