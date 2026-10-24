"""Parser-backed ENV tests; no Solidity compiler validation is claimed."""
from dataclasses import asdict

import pytest

from scripts.DFG.frontend import text, walk
from scripts.DFG.dfg_v2.env import ENV_KEYS, SPELLINGS, EnvExtractor
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.state_binding import StateBinder
from scripts.DFG.dfg_v2.units import iter_statement_regions


def source_extractor(source, name="f"):
    view = ProjectionView(source, "env.sol")
    owner = next(n for n in walk(view.tree.root_node)
                 if n.type in ("function_definition", "modifier_definition")
                 and n.child_by_field_name("name") is not None
                 and text(source, n.child_by_field_name("name")) == name)
    return view, owner, EnvExtractor(StateBinder(view, owner))


def build(body, members="address owner;", params="", prefix=""):
    return source_extractor(
        prefix + " pragma solidity ^0.5.0; contract C {" + members +
        " function f(" + params + ") public {" + body + "}}")


def node(view, spelling, kind="expression_statement"):
    matches = [n for n in walk(view.tree.root_node)
               if n.type == kind and text(view.source, n) == spelling]
    assert len(matches) == 1, [(n.type, n.start_byte) for n in matches]
    return matches[0]


def extract_body(view, owner, extractor):
    result = []
    for unit in iter_statement_regions(view):
        if owner.start_byte <= unit.ast_node.start_byte < owner.end_byte:
            result.extend(extractor.extract(unit.regions))
    return result


def signature(events):
    return [(event.key, event.spelling) for event in events]


def test_fixed_key_order_and_spelling_table_is_complete():
    assert ENV_KEYS == (
        "msg.sender", "msg.value", "msg.data", "msg.sig", "tx.origin",
        "tx.gasprice", "block.timestamp", "block.number", "block.difficulty",
        "block.coinbase", "block.gaslimit", "blockhash", "gasleft", "this.balance")
    assert isinstance(ENV_KEYS, tuple) and len(set(ENV_KEYS)) == 14
    assert set(SPELLINGS.values()) == set(ENV_KEYS)
    assert len(SPELLINGS) == 18


@pytest.mark.parametrize("expression,key,spelling", [
    ("msg.sender", "msg.sender", "msg.sender"),
    ("msg.value", "msg.value", "msg.value"),
    ("msg.data", "msg.data", "msg.data"),
    ("msg.sig", "msg.sig", "msg.sig"),
    ("tx.origin", "tx.origin", "tx.origin"),
    ("tx.gasprice", "tx.gasprice", "tx.gasprice"),
    ("block.timestamp", "block.timestamp", "block.timestamp"),
    ("block.number", "block.number", "block.number"),
    ("block.difficulty", "block.difficulty", "block.difficulty"),
    ("block.coinbase", "block.coinbase", "block.coinbase"),
    ("block.gaslimit", "block.gaslimit", "block.gaslimit"),
    ("blockhash(4)", "blockhash", "blockhash(...)"),
    ("gasleft()", "gasleft", "gasleft()"),
    ("this.balance", "this.balance", "this.balance"),
    ("now", "block.timestamp", "now"),
    ("msg.gas", "gasleft", "msg.gas"),
    ("block.blockhash(4)", "blockhash", "block.blockhash(...)"),
    ("address(this).balance", "this.balance", "address(this).balance"),
])
def test_all_approved_spellings(expression, key, spelling):
    view, owner, extractor = build(expression + ";")
    occurrences = extract_body(view, owner, extractor)
    assert signature(occurrences) == [(key, spelling)]
    occurrence = occurrences[0]
    expected_ast_text = "block.blockhash" if expression == "block.blockhash(4)" else expression
    assert view.raw[occurrence.span.start:occurrence.span.end].decode("utf8") == expected_ast_text
    if expression == "block.blockhash(4)":
        assert occurrence.span.role == "member_expression"
    assert asdict(occurrence)["span"]["file"] == "env.sol"
    assert extractor.diagnostics == []


@pytest.mark.parametrize("expression,spelling", [
    ("(msg).sender", "msg.sender"),
    ("msg /* comment */ . sender", "msg.sender"),
    ("(this).balance", "this.balance"),
    ("(address(this)).balance", "address(this).balance"),
    ("address((this)).balance", "address(this).balance"),
])
def test_parentheses_and_whitespace_normalize_spellings(expression, spelling):
    view, owner, extractor = build(expression + ";")
    assert signature(extract_body(view, owner, extractor)) == [(SPELLINGS[spelling], spelling)]


def test_installed_address_cast_grammar_shape():
    view, _, extractor = build("address(this).balance;")
    member = node(view, "address(this).balance", "member_expression")
    cast = member.child_by_field_name("object")
    assert cast.type == "type_cast_expression"
    assert [(c.type, text(view.source, c)) for c in cast.named_children] == [
        ("primitive_type", "address"), ("identifier", "this")]
    assert signature(extractor.extract(member)) == [("this.balance", "address(this).balance")]


def test_aliases_share_keys_but_preserve_occurrence_spellings():
    view, owner, extractor = build(
        "now; block.timestamp; msg.gas; gasleft(); blockhash(1); "
        "block.blockhash(2); this.balance; address(this).balance;")
    assert signature(extract_body(view, owner, extractor)) == [
        ("block.timestamp", "now"), ("block.timestamp", "block.timestamp"),
        ("gasleft", "msg.gas"), ("gasleft", "gasleft()"),
        ("blockhash", "blockhash(...)"), ("blockhash", "block.blockhash(...)"),
        ("this.balance", "this.balance"), ("this.balance", "address(this).balance"),
    ]


def test_only_innermost_env_member_is_emitted_once():
    view, owner, extractor = build("msg.sender.call.value(msg.value)();")
    events = extract_body(view, owner, extractor)
    assert signature(events) == [("msg.sender", "msg.sender"), ("msg.value", "msg.value")]
    assert extractor.diagnostics == []


def test_call_arguments_still_read_environment_and_function_references_are_not_calls():
    view, owner, extractor = build("blockhash(block.number); gasleft; blockhash; x.gasleft();")
    assert signature(extract_body(view, owner, extractor)) == [
        ("blockhash", "blockhash(...)"), ("block.number", "block.number")]


@pytest.mark.parametrize("body,params,members,key,reason", [
    ("now;", "uint now", "", "block.timestamp", "callable_local_name"),
    ("now;", "", "uint now;", "block.timestamp", "contract_member_name"),
    ("gasleft();", "", "function gasleft() internal {}", "gasleft", "contract_member_name"),
    ("msg.sender; uint msg;", "", "", "msg.sender", "callable_local_name"),
    ("blockhash(1);", "uint blockhash", "", "blockhash", "callable_local_name"),
    ("tx.origin;", "", "uint tx;", "tx.origin", "contract_member_name"),
    ("block.timestamp;", "", "uint block;", "block.timestamp", "contract_member_name"),
    ("msg.gas;", "", "uint msg;", "gasleft", "contract_member_name"),
    ("block.blockhash(1);", "", "uint block;", "blockhash", "contract_member_name"),
])
def test_callable_and_member_shadowing_conservative_whole_scope(body, params, members, key, reason):
    # Several samples are intentionally only parser-robustness negatives.
    view, owner, extractor = build(body, members, params)
    assert extract_body(view, owner, extractor) == []
    matches = [d for d in extractor.diagnostics if d["kind"] == "shadowed"]
    assert len(matches) == 1
    assert matches[0]["key"] == key and matches[0]["reason"] == reason


def test_return_parameter_and_legacy_tuple_local_names_shadow():
    view, owner, extractor = source_extractor(
        "contract C {function f() public returns(uint now) {now;}}")
    assert extract_body(view, owner, extractor) == []
    assert extractor.diagnostics[0]["reason"] == "callable_local_name"
    view, owner, extractor = build("now; var(now, x) = pair();")
    assert extract_body(view, owner, extractor) == []
    assert extractor.diagnostics[0]["reason"] == "callable_local_name"


def test_other_function_local_and_other_contract_member_do_not_shadow():
    view, owner, extractor = source_extractor(
        "contract D {uint msg;} contract C {function other(uint msg) public {} "
        "function f() public {msg.sender;}}")
    assert signature(extract_body(view, owner, extractor)) == [("msg.sender", "msg.sender")]


def test_inherited_members_shadow_without_reading_other_files():
    view, owner, extractor = source_extractor(
        "pragma solidity ^0.5.0; contract B {uint msg;} "
        "contract C is B {function f() public {msg.sender;}}")
    assert extract_body(view, owner, extractor) == []
    assert extractor.diagnostics[0]["reason"] == "contract_member_name"


@pytest.mark.parametrize("prefix,body,key", [
    ("contract msg {}", "msg.sender;", "msg.sender"),
    ("uint constant now = 1;", "now;", "block.timestamp"),
    ("function gasleft() pure returns(uint){return 1;}", "gasleft();", "gasleft"),
    ('import * as msg from "X.sol";', "msg.sender;", "msg.sender"),
    ('import "X.sol" as tx;', "tx.origin;", "tx.origin"),
    ('import {T as block} from "X.sol";', "block.timestamp;", "block.timestamp"),
    ('import {gasleft, T as msg} from "X.sol";', "gasleft();", "gasleft"),
])
def test_known_top_level_and_explicit_import_names_shadow(prefix, body, key):
    view, owner, extractor = build(body, prefix=prefix)
    assert extract_body(view, owner, extractor) == []
    diagnostic = extractor.diagnostics[0]
    assert diagnostic["reason"] == "file_top_level_name"
    assert diagnostic["key"] == key


def test_import_alias_replaces_source_name_in_current_scope():
    view, owner, extractor = build(
        "now; msg.sender;",
        prefix='import {now as clock, msg as remoteMsg} from "X.sol";')
    assert signature(extract_body(view, owner, extractor)) == [
        ("block.timestamp", "now"), ("msg.sender", "msg.sender")]


def test_member_property_named_argument_and_type_positions_not_values():
    view, owner, extractor = build(
        "x.now; f({now: 1}); a.call{now: 1}(\"\"); now memory p;")
    assert extract_body(view, owner, extractor) == []
    assert extractor.diagnostics == []
    now_names = [n for n in walk(owner)
                 if n.type == "identifier" and text(view.source, n) == "now"]
    assert len(now_names) == 4
    assert extractor.extract(now_names) == []


def test_named_call_options_preserve_value_expression_not_field_name():
    view, owner, extractor = build('a.call{now: msg.value, gas: gasleft()}("");')
    field = node(view, "now: msg.value", "struct_field_assignment")
    assert field.child_by_field_name("name").type == "identifier"
    assert field.child_by_field_name("value").type == "member_expression"
    assert signature(extract_body(view, owner, extractor)) == [
        ("msg.value", "msg.value"), ("gasleft", "gasleft()")]


def test_named_argument_value_now_is_not_excluded_with_its_name():
    view, owner, extractor = build("f({now: now});")
    assert signature(extract_body(view, owner, extractor)) == [("block.timestamp", "now")]


def test_unknown_members_count_exact_spelling_once_and_do_not_emit():
    view, owner, extractor = build("block.chainid; block.basefee; msg.unknown.call(); tx.nope;")
    assert extract_body(view, owner, extractor) == []
    assert [(d["kind"], d["spelling"]) for d in extractor.diagnostics] == [
        ("unknown_env_member", "block.chainid"), ("unknown_env_member", "block.basefee"),
        ("unknown_env_member", "msg.unknown"), ("unknown_env_member", "tx.nope")]
    assert all(d["key"] == "unregistered:" + d["spelling"] for d in extractor.diagnostics)


def test_shadowed_unknown_namespace_is_not_reported_as_builtin_unknown():
    view, owner, extractor = build("msg.custom;", params="uint msg")
    assert extract_body(view, owner, extractor) == []
    assert extractor.diagnostics[0]["kind"] == "shadowed"
    assert extractor.diagnostics[0]["key"] == "unregistered:msg.custom"


def test_assembly_is_not_interpreted_even_if_direct_child_is_passed():
    view, owner, extractor = build("assembly {let now := timestamp() let x := caller()} msg.sender;")
    assembly = next(n for n in walk(owner) if n.type == "assembly_statement")
    assert extractor.extract(assembly) == []
    assert extractor.diagnostics[-1]["kind"] == "assembly_skipped"
    nested = [n for n in walk(assembly) if n.type == "identifier"]
    assert extractor.extract(nested) == []
    # Deduplicated assembly diagnostic per extract invocation.
    assert len(extractor.diagnostics) == 2
    assert signature(extract_body(view, owner, extractor)) == [("msg.sender", "msg.sender")]


def test_blocks_require_units_and_conditions_exclude_child_statements():
    view, owner, extractor = build("if(now>1){msg.sender;} while(tx.origin==owner){msg.value;}")
    assert extractor.extract(owner.child_by_field_name("body")) == []
    assert extractor.diagnostics[-1]["kind"] == "region_skipped"
    if_unit = next(u for u in iter_statement_regions(view) if u.ast_node.type == "if_statement")
    assert signature(extractor.extract(if_unit)) == [("block.timestamp", "now")]
    all_events = extract_body(view, owner, extractor)
    assert signature(all_events) == [
        ("block.timestamp", "now"), ("msg.sender", "msg.sender"),
        ("tx.origin", "tx.origin"), ("msg.value", "msg.value")]


def test_state_initializer_owner_and_modifier_body():
    view = ProjectionView("contract C {address owner=msg.sender;}", "init.sol")
    declaration = next(n for n in walk(view.tree.root_node) if n.type == "state_variable_declaration")
    extractor = EnvExtractor(StateBinder(view, declaration))
    assert signature(extractor.extract(declaration)) == [("msg.sender", "msg.sender")]
    view, owner, extractor = source_extractor(
        "contract C {address owner; modifier auth(){require(msg.sender==owner); _;}}", "auth")
    assert signature(extract_body(view, owner, extractor)) == [("msg.sender", "msg.sender")]


def test_emit_revert_arguments_preserved_for_unmapped_accounting():
    view, owner, extractor = build(
        "emit E(msg.sender); revert Fail(now);", members="event E(address a); error Fail(uint x);")
    assert signature(extract_body(view, owner, extractor)) == [
        ("msg.sender", "msg.sender"), ("block.timestamp", "now")]


def test_duplicate_regions_do_not_double_count_and_next_extract_resets_events():
    view, owner, extractor = build("msg.sender == msg.sender;")
    statement = node(view, "msg.sender == msg.sender;")
    occurrences = extractor.extract([statement, statement])
    assert len(occurrences) == 2
    assert occurrences[0].span != occurrences[1].span
    assert extractor.extract(statement) == occurrences


def test_no_compiler_version_is_invented_for_legacy_aliases():
    view, owner, extractor = source_extractor(
        "contract C {function f() public {now; msg.gas; block.blockhash(1);}}")
    assert extractor.binder.mode is None
    assert signature(extract_body(view, owner, extractor)) == [
        ("block.timestamp", "now"), ("gasleft", "msg.gas"), ("blockhash", "block.blockhash(...)")]


def test_diagnostics_do_not_consume_binder_or_graph_labels():
    view, owner, extractor = build("require(msg.sender==owner);")
    before = list(extractor.binder.diagnostics)
    assert signature(extract_body(view, owner, extractor)) == [("msg.sender", "msg.sender")]
    assert extractor.binder.diagnostics == before


@pytest.mark.parametrize("body,expected", [
    ("revert(now);", [("block.timestamp", "now")]),
    ("revert(string(msg.data));", [("msg.data", "msg.data")]),
    ("revert();", []),
])
def test_builtin_revert_error_field_is_argument_wrapper_not_custom_error_name(body, expected):
    view, owner, extractor = build(body)
    statement = next(n for n in walk(owner) if n.type == "revert_statement")
    error = statement.child_by_field_name("error")
    if expected:
        assert error.type == "parenthesized_expression"
    assert signature(extract_body(view, owner, extractor)) == expected


@pytest.mark.parametrize("body,expected,recovered", [
    ("uint a = msg.gas + gasleft();",
     [("gasleft", "gasleft()"), ("gasleft", "msg.gas")], 1),
    ("bytes32 b = block.blockhash(1) ^ blockhash(2);",
     [("blockhash", "blockhash(...)"), ("blockhash", "block.blockhash(...)")], 1),
    ("uint c = this.balance + address(this).balance;",
     [("this.balance", "address(this).balance"), ("this.balance", "this.balance")], 1),
    ("uint a = 2 * gasleft();", [("gasleft", "gasleft()")], 1),
    ("uint a = ~gasleft();", [("gasleft", "gasleft()")], 1),
    ("uint a = 1 + gasleft() * 2;", [("gasleft", "gasleft()")], 1),
    ("uint a = 1 + 2 * gasleft();", [("gasleft", "gasleft()")], 1),
    ("uint a = 1 + (address(this)).balance;",
     [("this.balance", "address(this).balance")], 1),
    ("uint a = 1 + (msg).gas;", [("gasleft", "msg.gas")], 1),
    ("uint a = gasleft() + gasleft();",
     [("gasleft", "gasleft()"), ("gasleft", "gasleft()")], 1),
])
def test_approved_postfix_precedence_recovery_preserves_occurrences(body, expected, recovered):
    view, owner, extractor = build(body)
    events = extract_body(view, owner, extractor)
    assert sorted(signature(events)) == sorted(expected)
    records = [d for d in extractor.diagnostics if d["kind"] == "grammar_shape_recovered"]
    assert len(records) == recovered
    for record in records:
        assert record["original_span"]["start"] == record["start"]
        assert record["original_span"]["end"] == record["end"]
        assert record["leaf_span"]["end"] <= record["end"]
        assert record["leaf_span"]["start"] >= record["start"]
        leaf = record["leaf_span"]
        leaf_text = view.raw[leaf["start"]:leaf["end"]].decode("utf8")
        assert leaf_text == record["leaf_text"]
        assert record["steps"] and all(
            step["ast_type"] in ("binary_expression", "unary_expression")
            for step in record["steps"])


@pytest.mark.parametrize("body", [
    "uint a = (1 + gasleft)();",
    "uint a = (gasleft)();",
    "uint a = (1 + msg).sender;",
    "uint a = (1 + address(this)).balance;",
    "uint a = 1 + address(other).balance;",
    "uint a = 1 + target.gasleft();",
    "uint a = 1 + blockhash;",
    "uint a = 1 + (gasleft)();",
])
def test_postfix_recovery_does_not_cross_computed_parentheses_or_invent_calls(body):
    view, owner, extractor = build(body, params="address other")
    assert extract_body(view, owner, extractor) == []
    assert not any(d["kind"] == "grammar_shape_recovered" for d in extractor.diagnostics)


@pytest.mark.parametrize("body,members,params,key,reason", [
    ("uint a=1+gasleft();", "function gasleft() internal returns(uint) {return 1;}",
     "", "gasleft", "contract_member_name"),
    ("uint a=1+blockhash(2);", "", "uint blockhash", "blockhash", "callable_local_name"),
])
def test_recovered_calls_still_apply_binding_shadow_guards(body, members, params, key, reason):
    view, owner, extractor = build(body, members, params)
    assert extract_body(view, owner, extractor) == []
    shadow = [d for d in extractor.diagnostics if d["kind"] == "shadowed"]
    assert len(shadow) == 1 and shadow[0]["key"] == key and shadow[0]["reason"] == reason
    recovery = [d for d in extractor.diagnostics if d["kind"] == "grammar_shape_recovered"]
    assert len(recovery) == 1 and recovery[0]["shadow_reason"] == reason


def test_recovery_keeps_call_arguments_and_left_operand_reads():
    view, owner, extractor = build("uint a=msg.value + blockhash(block.number);")
    events = extract_body(view, owner, extractor)
    assert sorted(signature(events)) == sorted([
        ("msg.value", "msg.value"), ("blockhash", "blockhash(...)"),
        ("block.number", "block.number")])
