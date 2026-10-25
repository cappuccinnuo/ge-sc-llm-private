"""Real-parser L1 unit cases; compiler verification is not performed here.

Cases identified as robustness-only intentionally include declarations or
expressions whose Solidity legality is not claimed by the parse-only tests.
"""
from dataclasses import FrozenInstanceError

import pytest

from scripts.DFG.access_extractor import AccessExtractor
from scripts.DFG.frontend import parse_source, text, walk
from scripts.DFG.models import Unsupported
from scripts.DFG.symbol_table import SymbolTable
from scripts.DFG.dfg_v2.l1_access import ExtendedAccessExtractor
from scripts.DFG.dfg_v2.l1_models import V2Event
from scripts.DFG.dfg_v2.l1_symbols import ExtendedSymbolTable


def build(body, params="uint i, uint v", members="", version="^0.5.0", returns=""):
    source = ("pragma solidity " + version + "; contract C { "
              "struct S { uint a; uint b; uint[] xs; } " + members
              + " function f(" + params + ") public " + returns
              + " { " + body + " } }")
    view = parse_source(source, "l1_access.sol")
    function = view.functions[0]
    table = ExtendedSymbolTable(source, view.file, function, view.mode)
    return view, function, table, ExtendedAccessExtractor(source, table)


def named(table, name):
    return [symbol for symbol in table.symbols.values() if symbol.name == name]


def node(view, spelling, node_type=None):
    matches = [item for item in walk(view.tree.root_node)
               if text(view.source, item) == spelling
               and (node_type is None or item.type == node_type)]
    assert len(matches) == 1, [(item.type, item.start_byte) for item in matches]
    return matches[0]


def event(view, access, spelling):
    matches = access.extract(node(view, spelling, "expression_statement"))
    assert len(matches) == 1
    return matches[0]


def names(table, symbols):
    return {table.symbols[symbol].name for symbol in symbols}


def test_v2_event_is_frozen_and_parent_event_api_is_compatible():
    view, function, table, access = build("uint a = v;")
    entry = access.entry(function)
    assert isinstance(entry, V2Event)
    assert entry.weak_writes == ()
    assert names(table, entry.writes) == {"i", "v"}
    condition = access.event(entry.anchor, (named(table, "v")[0].id,), (), "condition")
    assert condition.kind == "condition"
    assert condition.weak_writes == ()
    with pytest.raises(FrozenInstanceError):
        entry.kind = "modified"


def test_type_location_and_declaration_identity_with_aggregate_scopes():
    view, function, table, _ = build(
        "S memory s; { S memory s; s.a = v; } s.b = i;",
        params="string memory t, bytes calldata b, uint[] memory a, C c, uint i, uint v")
    ss = named(table, "s")
    assert len(ss) == 2 and ss[0].id != ss[1].id
    inside = node(view, "s.a", "member_expression").child_by_field_name("object")
    outside = node(view, "s.b", "member_expression").child_by_field_name("object")
    assert table.resolve("s", inside).id == ss[1].id
    assert table.resolve("s", outside).id == ss[0].id
    for symbol in table.symbols.values():
        info = table.aggregate_info[symbol.id]
        assert info["type"] == symbol.type_name
        if symbol.name in ("i", "v"):
            assert info == {"aggregate": False, "location": None, "type": "uint"}
        else:
            assert info["aggregate"]
    assert table.aggregate_info[named(table, "b")[0].id]["location"] == "calldata"
    assert table.aggregate_info[ss[0].id]["location"] == "memory"
    # Parameter calldata + public is a parser robustness case, not a compile claim.


def test_array_mapping_string_bytes_and_legacy_var_are_registered():
    _, _, table, _ = build(
        "var acc = stores[i]; uint[3] memory fixeds; string memory s; bytes memory b; "
        "mapping(uint => S) storage refs = stores; uint[] storage arr = data;",
        members="mapping(uint => S) stores; uint[] data;", version="^0.4.25")
    for name in ("acc", "fixeds", "s", "b", "refs", "arr"):
        assert table.aggregate_info[named(table, name)[0].id]["aggregate"]
    assert named(table, "acc")[0].type_name == "var"
    assert table.aggregate_info[named(table, "arr")[0].id]["location"] == "storage"
    # Mapping local spelling is intentionally parser robustness; no solc claim.


@pytest.mark.parametrize("body,params,match", [
    ("var x = 1;", "", "legacy"),
    ("", "function(uint) external returns (uint) fn", "function type"),
    ("S memory s = s;", "", "initializer"),
])
def test_unsupported_types_and_modern_self_reference_stay_conservative(body, params, match):
    with pytest.raises(Unsupported, match=match):
        build(body, params=params)


def test_legacy_var_tuple_without_declarators_remains_explicit_fallback():
    with pytest.raises(Unsupported, match="without explicit scalar declarators"):
        build("var (x, y) = result();", params="", version="^0.4.25")


@pytest.mark.parametrize("statement,expected_kind", [
    ("s.xs[i] = v;", "assignment"),
    ("s.xs[i] += v;", "assignment"),
    ("s.xs[i] -= v;", "assignment"),
    ("s.xs[i]++;", "update"),
    ("--s.xs[i];", "update"),
    ("++s.xs[i];", "update"),
    ("delete s.a;", "delete"),
    ("delete s.xs[i];", "delete"),
])
def test_member_array_targets_are_weak_and_read_base_and_indices(statement, expected_kind):
    view, _, table, access = build("S memory s; " + statement)
    result = event(view, access, statement)
    assert result.kind == expected_kind
    assert result.writes == ()
    assert names(table, result.weak_writes) == {"s"}
    expected = {"s"}
    if "[i]" in statement:
        expected.add("i")
    if "v" in statement:
        expected.add("v")
    assert names(table, result.reads) == expected


def test_whole_aggregate_assignment_and_delete_are_strong():
    view, _, table, access = build("S memory s; uint[] memory xs; s = S(1, 2, xs); delete s;")
    assigned = event(view, access, "s = S(1, 2, xs);")
    assert names(table, assigned.writes) == {"s"} and assigned.weak_writes == ()
    deleted = event(view, access, "delete s;")
    assert names(table, deleted.writes) == {"s"} and deleted.weak_writes == ()
    assert deleted.reads == ()


@pytest.mark.parametrize("statement,expected_reads", [
    ("arr.push(v);", {"arr", "v"}),
    ("arr.pop();", {"arr"}),
    ("s.xs.push(i);", {"s", "i"}),
])
def test_direct_aggregate_push_pop_emit_weak_definition(statement, expected_reads):
    view, _, table, access = build(
        "uint[] storage arr = data; S storage s = store; " + statement,
        members="uint[] data; S store;")
    result = event(view, access, statement)
    assert result.writes == ()
    assert names(table, result.weak_writes) == ({"arr"} if statement.startswith("arr") else {"s"})
    assert names(table, result.reads) == expected_reads


@pytest.mark.parametrize("statement,expected_reads", [
    ("data[i] = v;", {"i", "v"}),
    ("data.push(v);", {"v"}),
    ("delete data[i];", {"i"}),
])
def test_nonlocal_writes_are_not_promoted_to_local_definitions(statement, expected_reads):
    view, _, table, access = build(statement, members="uint[] data;")
    result = event(view, access, statement)
    assert result.writes == result.weak_writes == ()
    assert names(table, result.reads) == expected_reads


@pytest.mark.parametrize("statement", [
    "s.a = (v = i);",
    "s.a = ++i;",
    "s.a = (delete i);",
    "sink(arr.push(v));",
    "s.a = arr.push(v);",
    "delete arr[i++];",
    "--arr[(i = v)];",
    "delete arr[(delete i)];",
])
def test_nested_writes_delete_and_local_push_are_rejected(statement):
    # Some expressions are parseable but not legal Solidity: robustness-only.
    view, _, _, access = build(
        "S memory s; uint[] storage arr = data; " + statement,
        members="uint[] data;")
    with pytest.raises(Unsupported, match="Nested|nested"):
        event(view, access, statement)


def test_tuple_targets_preserve_strong_weak_split_and_reject_duplicate_base():
    view, _, table, access = build(
        "S memory s; (s.a, i) = result(); (s.a, s.b) = result();")
    result = event(view, access, "(s.a, i) = result();")
    assert names(table, result.writes) == {"i"}
    assert names(table, result.weak_writes) == {"s"}
    with pytest.raises(Unsupported, match="Repeated"):
        event(view, access, "(s.a, s.b) = result();")


def test_ordinary_call_aggregate_arguments_are_read_only_by_declared_approximation():
    view, _, table, access = build("S memory s; sink(s, i);")
    result = event(view, access, "sink(s, i);")
    assert names(table, result.reads) == {"s", "i"}
    assert result.writes == result.weak_writes == ()


def test_original_scalar_symbols_and_event_content_are_identical():
    view, function, table, access = build(
        "uint x = v; x += i; x--; require(x > 0); assert(x >= i); return x;",
        returns="returns (uint)")
    original_table = SymbolTable(view.source, view.file, function, view.mode)
    original = AccessExtractor(view.source, original_table)
    assert table.symbols == original_table.symbols
    assert table.declarations == original_table.declarations
    assert table.entry_symbols == original_table.entry_symbols
    pairs = [(access.entry(function), original.entry(function))]
    for statement in function.child_by_field_name("body").named_children:
        left, right = access.extract(statement), original.extract(statement)
        assert len(left) == len(right)
        pairs.extend(zip(left, right))
    for left, right in pairs:
        assert left.weak_writes == ()
        for field in ("id", "function", "anchor", "reads", "writes", "kind"):
            assert getattr(left, field) == getattr(right, field)


def test_return_and_condition_reads_include_aggregate_base_without_field_symbols():
    view, function, table, access = build(
        "S memory s; if (s.a > i) { return s.b; } return i;",
        returns="returns (uint)")
    conditional = next(item for item in walk(function) if item.type == "if_statement")
    assert names(table, access.reads(conditional.child_by_field_name("condition"))) == {"s", "i"}
    result = access.extract(node(view, "return s.b;", "return_statement"))[0]
    assert names(table, result.reads) == {"s"}
    assert not named(table, "a") and not named(table, "b")


def test_event_cannot_emit_same_symbol_as_both_strong_and_weak():
    _, function, table, access = build("")
    anchor = access.entry(function).anchor
    identity = named(table, "v")[0].id
    with pytest.raises(Unsupported, match="overlapping"):
        access.event(anchor, writes=[identity], weak_writes=[identity])


def test_prefix_chain_scope_binding_and_anchor_remain_exact():
    view, function, table, access = build(
        "uint[] memory a; { uint[] memory a; delete a[i]; } --a[i];")
    outer, inner = named(table, "a")
    deleted = event(view, access, "delete a[i];")
    updated = event(view, access, "--a[i];")
    assert deleted.weak_writes == (inner.id,)
    assert updated.weak_writes == (outer.id,)
    assert view.raw[deleted.anchor.start:deleted.anchor.end].decode("utf8") == "delete a[i];"
    assert view.raw[updated.anchor.start:updated.anchor.end].decode("utf8") == "--a[i];"
    assert len([d for d in access.diagnostics if d["kind"] == "v2_prefix_access_chain"]) == 2


@pytest.mark.parametrize("statement", ["(arr).push(v);", "(arr)[i] = v;"])
def test_parenthesized_local_base_does_not_silently_lose_weak_write(statement):
    view, _, table, access = build("uint[] storage arr = data; " + statement,
                                  members="uint[] data;")
    result = event(view, access, statement)
    assert names(table, result.weak_writes) == {"arr"}
    assert result.writes == ()
    assert names(table, result.reads) == ({"arr", "v"} if "push" in statement
                                         else {"arr", "i", "v"})


# Prompt 6b: parser-backed cases, not compilation validation.
@pytest.mark.parametrize("statement,params,expected", [
    ('target.call{value: x}("");', "address target, uint x, uint value",
     {"target", "x"}),
    ('t.call{value: a, gas: b}(data);',
     "address t, uint a, uint b, bytes memory data, uint value, uint gas",
     {"t", "a", "b", "data"}),
])
def test_prompt6b_call_options_read_values_not_option_names(statement, params, expected):
    view, _, table, access = build(statement, params=params, version="^0.6.12")
    result = event(view, access, statement)
    assert names(table, result.reads) == expected
    assert not result.writes and not result.weak_writes
    for identity in result.reads:
        symbol = table.symbols[identity]
        assert identity == named(table, symbol.name)[0].id


def test_prompt6b_call_option_field_name_does_not_read_same_named_local():
    statement = 'target.call{value: x}("");'
    view, _, table, access = build(
        "uint value = 7; uint x = 1; " + statement,
        params="address target", version="^0.6.12")
    result = event(view, access, statement)
    assert names(table, result.reads) == {"target", "x"}
    assert named(table, "value")[0].id not in result.reads


@pytest.mark.parametrize("value", ["x++", "(x = 2)", "(delete x)"])
def test_prompt6b_call_options_keep_nested_write_rejection(value):
    # Nested writes are intentionally unsupported, even if parseable.
    statement = 'target.call{value: ' + value + '}("");'
    view, _, _, access = build(
        statement, params="address target, uint x", version="^0.6.12")
    with pytest.raises(Unsupported, match="Nested"):
        event(view, access, statement)


def test_prompt6b_call_options_keep_unknown_value_expression_rejection():
    # P6b approved new-expression support supersedes the first probe's new C
    # fallback expectation. Keep an independent unknown-expression guard here.
    # This is parser robustness only, not a claim of a valid value type.
    statement = 'target.call{value: type(C)}("");'
    view, _, _, access = build(
        statement, params="address target", version="^0.6.12")
    with pytest.raises(Unsupported, match="meta_type_expression"):
        event(view, access, statement)


@pytest.mark.parametrize("statement,params,expected", [
    ("new C{value: v}(i);", "uint v, uint i", {"v", "i"}),
    ("new C{value: v, salt: s}(i);", "uint v, uint i, bytes32 s", {"v", "i", "s"}),
    ("new C(i);", "uint v, uint i", {"i"}),
])
def test_prompt6b_new_contract_reads_options_and_arguments_not_type(statement, params, expected):
    # Parser-backed extraction fixtures; constructors are not compile-verified.
    view, _, table, access = build(statement, params=params, version="^0.6.12")
    result = event(view, access, statement)
    assert names(table, result.reads) == expected
    assert not result.writes and not result.weak_writes


def test_prompt6b_new_contract_type_is_not_a_same_named_local_value():
    # A same-named local/type is parser robustness, not a Solidity legality claim.
    statement = "new C{value: v}(i);"
    view, _, table, access = build(
        statement, params="uint v, uint i, uint C", version="^0.6.12")
    result = event(view, access, statement)
    assert names(table, result.reads) == {"v", "i"}
    assert named(table, "C")[0].id not in result.reads


@pytest.mark.parametrize("statement", [
    "new C{value: v++}(i);",
    "new C{value: v}(i++);",
])
def test_prompt6b_new_contract_does_not_allow_nested_writes(statement):
    view, _, _, access = build(
        statement, params="uint v, uint i", version="^0.6.12")
    with pytest.raises(Unsupported, match="Nested"):
        event(view, access, statement)

# Prompt 6d: parser-backed cases; these assertions are not solc validation.
@pytest.mark.parametrize("statement,params,expected", [
    ("new uint[](n);", "uint n", {"n"}),
    ("new bytes(len);", "uint len", {"len"}),
    ("new string(len);", "uint len", {"len"}),
    ("new C(a, b);", "uint a, uint b", {"a", "b"}),
])
def test_prompt6d_allocation_arguments_are_reads(statement, params, expected):
    view, _, table, access = build(statement, params=params, version="^0.6.12")
    result = event(view, access, statement)
    assert names(table, result.reads) == expected
    assert not result.writes and not result.weak_writes
    allocations = [n for n in walk(view.tree.root_node) if n.type == "new_expression"]
    assert len(allocations) == 1
    # Installed grammar places these arguments in the enclosing call.
    assert not [c for c in allocations[0].named_children if c.type == "call_argument"]
    assert access.reads(allocations[0]) == []


class DirectArgumentsNewNode:
    """Parser robustness adapter using real type/argument AST children.

    This models the grammar-permitted direct-child branch; it does not claim
    the installed parser emits that branch for the fixtures above.
    """
    type = "new_expression"

    def __init__(self, allocation, arguments):
        self.declared_type = allocation.child_by_field_name("name")
        self.named_children = [self.declared_type] + list(arguments)

    def child_by_field_name(self, name):
        return self.declared_type if name == "name" else None


def test_prompt6d_direct_new_arguments_read_declaration_identities_not_type():
    # Same local/type spelling is deliberately parser robustness only.
    view, _, table, access = build(
        "new C(a, b);", params="uint a, uint b, uint C", version="^0.6.12")
    call = node(view, "new C(a, b)", "call_expression")
    allocation = next(n for n in walk(call) if n.type == "new_expression")
    args = [n for n in call.named_children if n.type == "call_argument"]
    assert len(args) == 2
    result = access.reads(DirectArgumentsNewNode(allocation, args))
    assert set(result) == {named(table, "a")[0].id, named(table, "b")[0].id}
    assert named(table, "C")[0].id not in result


def test_prompt6d_direct_new_arguments_keep_nested_write_fallback():
    view, _, _, access = build(
        "new C(a++);", params="uint a", version="^0.6.12")
    call = node(view, "new C(a++)", "call_expression")
    allocation = next(n for n in walk(call) if n.type == "new_expression")
    args = [n for n in call.named_children if n.type == "call_argument"]
    with pytest.raises(Unsupported, match="Nested"):
        access.reads(DirectArgumentsNewNode(allocation, args))
