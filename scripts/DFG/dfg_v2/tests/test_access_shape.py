"""Prefix-chain grammar regression tests; no Solidity compiler is invoked.

The main three examples are ordinary Solidity constructs. Negative nested-write
examples exercise parser robustness only; parsing is not a compilation claim.
"""
import pytest

from scripts.DFG.dfg_v2.access_shape import prefix_access_shape
from scripts.DFG.dfg_v2.l1_access import ExtendedAccessExtractor
from scripts.DFG.dfg_v2.l1_symbols import ExtendedSymbolTable
from scripts.DFG.frontend import parse_source, text, walk
from scripts.DFG.models import Unsupported


def parsed(expression):
    source = (
        "pragma solidity ^0.5.0; contract C { "
        "struct S { uint amount; uint[] xs; } "
        "mapping(address => uint) balances; "
        "function f(uint[] memory counts, S[] memory holders, "
        "uint i, uint j, uint k) public { " + expression + "; } }")
    view = parse_source(source, "access_shape.sol")
    statement = next(n for n in walk(view.functions[0])
                     if n.type == "expression_statement")
    expression_node = next(n for n in statement.named_children
                           if "comment" not in n.type)
    return view, statement, expression_node


@pytest.mark.parametrize("expression,operator,base,indices", [
    ("delete balances[msg.sender]", "delete", "balances", ("msg.sender",)),
    ("++counts[k]", "++", "counts", ("k",)),
    ("delete holders[i].amount", "delete", "holders", ("i",)),
    ("--holders[i].xs[j]", "--", "holders", ("i", "j")),
    ("delete holders[i].xs[j]", "delete", "holders", ("i", "j")),
    ("delete (holders)[i].amount", "delete", "(holders)", ("i",)),
    ("++k", "++", "k", ()),
    ("delete k", "delete", "k", ()),
])
def test_prefix_shape_returns_original_ast_identity_and_inner_to_outer_indices(
        expression, operator, base, indices):
    view, _, node = parsed(expression)
    original = (node.sexp(), node.start_byte, node.end_byte, node.text)
    result = prefix_access_shape(node)
    assert result is not None
    op, argument, actual_indices = result
    assert op == operator
    assert text(view.source, argument) == base
    assert tuple(text(view.source, n) for n in actual_indices) == indices
    assert isinstance(actual_indices, tuple)
    assert argument.parent.type in ("unary_expression", "update_expression")
    all_nodes = list(walk(node))
    assert argument in all_nodes
    assert all(index in all_nodes for index in actual_indices)
    assert (node.sexp(), node.start_byte, node.end_byte, node.text) == original


@pytest.mark.parametrize("expression", [
    "counts[k]",
    "counts[k]++",
    "holders[i].amount--",
    "-counts[k]",
    "(delete counts)[k]",
    "counts[k++]",
    "counts[(k = i)]",
    "sink(++counts[k])",
])
def test_non_prefix_or_nested_shapes_are_not_reinterpreted(expression):
    _, _, node = parsed(expression)
    assert prefix_access_shape(node) is None


def test_none_has_no_prefix_shape():
    assert prefix_access_shape(None) is None


@pytest.mark.parametrize("expression,weak,reads", [
    ("++counts[k]", "counts", {"counts", "k"}),
    ("delete holders[i].amount", "holders", {"holders", "i"}),
    ("--holders[i].xs[j]", "holders", {"holders", "i", "j"}),
])
def test_l1_delegation_preserves_weak_definition_reads_anchor_and_diagnostic(
        expression, weak, reads):
    view, statement, _ = parsed(expression)
    function = view.functions[0]
    table = ExtendedSymbolTable(view.source, view.file, function, view.mode)
    access = ExtendedAccessExtractor(view.source, table)
    events = access.extract(statement)
    assert len(events) == 1
    event = events[0]
    symbol_names = lambda ids: {table.symbols[symbol].name for symbol in ids}
    assert event.writes == ()
    assert symbol_names(event.weak_writes) == {weak}
    assert symbol_names(event.reads) == reads
    assert view.raw[event.anchor.start:event.anchor.end].decode("utf8") == expression + ";"
    matching = [d for d in access.diagnostics if d["kind"] == "v2_prefix_access_chain"]
    assert len(matching) == 1
    assert matching[0]["anchor_preserved"] is True
    assert matching[0]["byte"] == statement.start_byte
    assert matching[0]["parser_shape"] == (
        "unary_expression" if expression.startswith("delete") else "update_expression")


@pytest.mark.parametrize("expression", [
    "delete holders[i++].amount",
    "++counts[(k = i)]",
    "delete counts[(delete k)]",
])
def test_shared_helper_does_not_hide_nested_index_side_effects_from_l1(expression):
    # These are robustness cases, not compiler-validated Solidity programs.
    view, statement, expression_node = parsed(expression)
    shape = prefix_access_shape(expression_node)
    assert shape is not None
    assert len(shape[2]) == 1
    function = view.functions[0]
    table = ExtendedSymbolTable(view.source, view.file, function, view.mode)
    access = ExtendedAccessExtractor(view.source, table)
    with pytest.raises(Unsupported, match="Nested|nested"):
        access.extract(statement)


def test_malformed_prefix_node_preserves_previous_explicit_fallback():
    class IncompletePrefix:
        type = "unary_expression"

        def child_by_field_name(self, name):
            return None

    with pytest.raises(Unsupported, match="malformed prefix access chain"):
        prefix_access_shape(IncompletePrefix())
