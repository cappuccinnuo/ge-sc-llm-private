"""Semantic scope tests parse the existing Linux grammar entirely in memory."""
from pathlib import Path
import pytest
from tree_sitter import Language, Parser
from scripts.DFG.models import Unsupported
from scripts.DFG.symbol_table import SymbolTable

ROOT = Path(__file__).resolve().parents[3]


def walk(node):
    yield node
    for child in node.named_children:
        yield from walk(child)


def parse(body, parameters="", returns="", pragma="^0.8.0"):
    source = "pragma solidity " + pragma + "; contract C { function f(" + parameters + ") public " + returns + " {" + body + "} }"
    parser = Parser()
    parser.set_language(Language(str(ROOT / "build/linux-x86_64/my-languages.so"), "solidity"))
    tree = parser.parse(source.encode("utf8"))
    assert not tree.root_node.has_error
    function = next(n for n in walk(tree.root_node) if n.type == "function_definition")
    return source, function


def ref(function, name, occurrence):
    return [n for n in walk(function) if n.type == "identifier" and n.text.decode() == name][occurrence]


def test_legacy_hoists_locals_modern_does_not():
    source, function = parse("x = a; { uint x; } return x;", "uint a", "returns(uint)", "^0.4.25")
    legacy = SymbolTable(source, "a.sol", function, "legacy")
    modern = SymbolTable(source, "a.sol", function, "modern")
    local = next(s for s in legacy.symbols.values() if s.name == "x")
    assert legacy.resolve("x", ref(function, "x", 0)) == local
    assert legacy.resolve("x", ref(function, "x", 2)) == local
    assert modern.resolve("x", ref(function, "x", 0)) is None
    assert modern.resolve("x", ref(function, "x", 2)) is None
    assert {s.name for s in legacy.entry_symbols} == {"a", "x"}
    assert {s.name for s in modern.entry_symbols} == {"a"}


def test_modern_shadow_begins_after_declaration_and_ends_with_block():
    source, function = parse("uint x=1; {x=2; uint x=3; x=4;} return x;", returns="returns(uint)")
    table = SymbolTable(source, "a.sol", function, "modern")
    declarations = [n for n in walk(function) if n.type == "variable_declaration"]
    outer, inner = [table.lookup_decl(n) for n in declarations]
    assert outer.id != inner.id
    assert table.resolve("x", ref(function, "x", 1)) == outer
    assert table.resolve("x", ref(function, "x", 3)) == inner
    assert table.resolve("x", ref(function, "x", 4)) == outer


def test_for_initial_scope_and_disjoint_sibling_blocks():
    source, function = parse("for(uint i=0;i<2;i++){uint x=i;} uint j=1; {uint x=j; x=2;} return j;", returns="returns(uint)")
    table = SymbolTable(source, "a.sol", function, "modern")
    i_symbol = next(s for s in table.symbols.values() if s.name == "i")
    assert all(table.resolve("i", ref(function, "i", n)) == i_symbol for n in (1, 2, 3))
    final = next(n for n in walk(function) if n.type == "return_statement")
    assert table.resolve("i", final) is None
    xs = [s for s in table.symbols.values() if s.name == "x"]
    assert len(xs) == 2 and xs[0].id != xs[1].id


def test_named_returns_parameters_and_tuple_declarations():
    source, function = parse("(uint x,,uint y) = (a,2,a); out = x+y;", "uint a, uint", "returns(uint out, uint)")
    table = SymbolTable(source, "a.sol", function, "modern")
    assert {(s.name, s.kind) for s in table.entry_symbols} == {("a", "parameter"), ("out", "return")}
    assert {s.name for s in table.symbols.values()} == {"a", "out", "x", "y"}
    assert all(table.lookup_decl(n).declaration.start == n.start_byte for n in walk(function) if n.type == "variable_declaration")


@pytest.mark.parametrize("declaration", ["uint[] memory x;", "string memory x;", "bytes memory x;", "Foo x;", "var x=1;", "uint7 x;", "bytes33 x;"])
def test_unsupported_types_fail_whole_function(declaration):
    source, function = parse(declaration)
    with pytest.raises(Unsupported):
        SymbolTable(source, "a.sol", function, "modern")


@pytest.mark.parametrize("mode", ["legacy", "modern"])
def test_duplicate_same_scope_rejected(mode):
    source, function = parse("uint x; uint x;")
    with pytest.raises(Unsupported, match="Duplicate"):
        SymbolTable(source, "a.sol", function, mode)


def test_legacy_disjoint_blocks_are_still_same_function_scope():
    source, function = parse("{uint x;} {uint x;}", pragma="^0.4.25")
    with pytest.raises(Unsupported, match="Duplicate"):
        SymbolTable(source, "a.sol", function, "legacy")
    assert len(SymbolTable(source, "a.sol", function, "modern").symbols) == 2


def test_scalar_widths_and_utf8_byte_identity():
    source, function = parse("/* non-ASCII: " + chr(0x4E2D) + " */ uint8 x; int256 y; bytes32 z; bool b; address a;")
    table = SymbolTable(source, "a.sol", function, "modern")
    assert {s.type_name for s in table.symbols.values()} == {"uint8", "int256", "bytes32", "bool", "address"}
    raw = source.encode("utf8")
    assert all(raw[s.declaration.start:s.declaration.end].decode().endswith(s.name) for s in table.symbols.values())
    assert all(s.id.startswith(table.function_id + ":") for s in table.symbols.values())


def test_file_identity_and_source_mismatch():
    source, function = parse("uint x;")
    a = SymbolTable(source, "a.sol", function, "modern")
    b = SymbolTable(source, "b.sol", function, "modern")
    assert next(iter(a.symbols)) != next(iter(b.symbols))
    with pytest.raises(ValueError, match="coordinates"):
        SymbolTable(" " + source, "a.sol", function, "modern")


def test_modern_shadow_initializer_is_explicit_conservative_fallback():
    source, function = parse("uint x=1; {uint x=x+1;}")
    with pytest.raises(Unsupported, match="initializer"):
        SymbolTable(source, "a.sol", function, "modern")
