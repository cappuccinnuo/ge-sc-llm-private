"""Exact region ownership; all Solidity examples are parser-only fixtures."""
from types import SimpleNamespace

import networkx as nx
import pytest

from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
from scripts.DFG.frontend import text, walk
from scripts.DFG.projection import Projector
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.units import (
    ast_key, iter_statement_regions, projected_node, statement_units,
)

FILE = "sample.sol"


def fixture(body):
    return ProjectionView("pragma solidity ^0.5.0; contract C { "
                          "uint x; uint y; " + body + " }", FILE)


def region_text(view, candidate):
    return tuple(text(view.source, node) for node in candidate.regions)


def exact_projector(view, nodes):
    # Synthetic graph with real AST identity labels, not line-based alignment.
    graph = nx.MultiDiGraph()
    for offset, node in enumerate(nodes):
        key = view.mapping[ast_key(node)]
        compat = view.compat_nodes[key]
        role = {"if_statement": "if", "for_statement": "for",
                "while_statement": "while", "return_statement": "return",
                "variable_declaration_statement": "new_variable"}.get(node.type, node.type)
        identifier = 1000 + offset * 13
        graph.add_node(identifier, source_file=FILE, node_type=role,
            label="%s-%s-%s-%s" % (view.compat_ids[key], role,
                                  compat.start_point[0]+1, compat.end_point[0]+1),
            code=text(view.compat_source, compat))
    return Projector(graph, view)


def candidates(view):
    return list(iter_statement_regions(view))


def test_if_else_and_nested_if_have_only_their_conditions():
    view = fixture("function f() public { if(x>0){if(y>1){x=2;}}else y=3; }")
    nodes = candidates(view)
    ifs = [n for n in nodes if n.ast_node.type == "if_statement"]
    assert [region_text(view, n) for n in ifs] == [("x>0",), ("y>1",)]
    statements = [region_text(view, n) for n in nodes
                  if n.ast_node.type == "expression_statement"]
    assert statements == [("x=2;",), ("y=3;",)]
    function = next(n for n in nodes if n.ast_node.type == "function_definition")
    assert function.regions == ()
    assert not any(region.type in ("function_body", "block_statement")
                   for n in nodes for region in n.regions)


@pytest.mark.parametrize("own_fields", [(), ("update",), ("initial", "condition", "update")])
def test_for_parts_owned_once_and_exact_own_node_used(own_fields):
    view = fixture("function f() public { for(uint i=x;i<y;i++){x+=i;} }")
    loop = next(n for n in walk(view.tree.root_node) if n.type == "for_statement")
    parts = {f: loop.child_by_field_name(f) for f in ("initial", "condition", "update")}
    body = next(n for n in walk(loop.child_by_field_name("body")) if n.type == "expression_statement")
    projector = exact_projector(view, [loop, body] + [parts[f] for f in own_fields])
    units = statement_units(view, projector)
    parent = next(u for u in units if u.ast_node == loop)
    assert parent.regions == tuple(parts[f] for f in ("initial", "condition", "update")
                                   if f not in own_fields)
    for field in own_fields:
        child = next(u for u in units if u.ast_node == parts[field])
        assert child.regions == (parts[field],)
        assert child.hcg_node_id == projected_node(view, projector, parts[field])
    all_regions = [ast_key(region) for unit in units for region in unit.regions]
    assert len(all_regions) == len(set(all_regions))
    assert (body,) == next(u.regions for u in units if u.ast_node == body)
    assert len(units) == 2 + len(own_fields)


def test_for_missing_parts_and_body_are_not_misclassified_as_headers():
    view = fixture("function f() public { for(;x<y;) x++; for(;;) { y++; } }")
    loops = [n for n in candidates(view) if n.ast_node.type == "for_statement"]
    assert [region_text(view, n) for n in loops] == [("x<y;",), ()]
    expressions = [region_text(view, n) for n in candidates(view)
                   if n.ast_node.type == "expression_statement"]
    assert expressions == [("x++;",), ("y++;",)]


def test_while_and_do_while_only_own_condition():
    view = fixture("function f() public { while(x>0){x--;} do{x++;}while(x<1); }")
    regions = {n.ast_node.type: region_text(view, n) for n in candidates(view)
               if n.ast_node.type in ("while_statement", "do_while_statement")}
    assert regions == {"while_statement": ("x>0",), "do_while_statement": ("x<1",)}


def test_callable_modifier_arguments_exclude_body_and_declaration_names():
    view = fixture("""modifier m(uint z) { require(x==z); _; }
    constructor(uint q) m(x) public { x=q; }
    function f(uint n) public m(y+n) returns(uint) { return x; }""")
    own = {n.ast_node.type: region_text(view, n) for n in candidates(view)
           if n.ast_node.type in ("modifier_definition", "constructor_definition", "function_definition")}
    assert own == {"modifier_definition": (), "constructor_definition": ("x",),
                   "function_definition": ("y+n",)}
    expressions = [region_text(view, n) for n in candidates(view)
                   if n.ast_node.type == "expression_statement"]
    assert ("require(x==z);",) in expressions
    assert ("x=q;",) in expressions


def test_state_initializer_only_own_value_no_type_or_name():
    view = fixture("uint z=x+y; uint w;")
    records = [n for n in candidates(view) if n.ast_node.type == "state_variable_declaration"]
    assert [region_text(view, n) for n in records] == [(), (), ("x+y",), ()]


def test_missing_emit_revert_return_cannot_be_attached_to_enclosing_node():
    view = fixture("event E(uint x); function f() public returns(uint) { emit E(x); revert(); return y; }")
    fn = next(n for n in walk(view.tree.root_node) if n.type == "function_definition")
    projector = exact_projector(view, [fn])
    units = statement_units(view, projector)
    assert len(units) == 1 and units[0].regions == ()
    missing = [n for n in iter_statement_regions(view, projector)
               if n.regions and projected_node(view, projector, n.ast_node) is None]
    assert [(n.ast_node.type, region_text(view, n)) for n in missing] == [
        ("emit_statement", ("emit E(x);",)),
        ("revert_statement", ("revert();",)),
        ("return_statement", ("return y;",)),
    ]


def test_actual_generator_for_update_has_own_existing_node():
    source = "pragma solidity ^0.5.17; contract C { uint x; function f(uint n) public { for(uint i=0;i<n;i++){x+=i;} } }"
    view = ProjectionView(source, FILE)
    graph = generate_cfg_from_source(source, FILE)
    projector = Projector(graph, view)
    units = statement_units(view, projector)
    loop = next(u for u in units if u.ast_node.type == "for_statement")
    update = next(u for u in units if text(source, u.ast_node) == "i++")
    assert region_text(view, loop) == ("uint i=0;", "i<n;")
    assert region_text(view, update) == ("i++",)
    assert graph.nodes[update.hcg_node_id]["code"] == "i++"


def test_missing_or_stale_mapping_never_uses_line_number():
    view = fixture("function f() public { x=1; y=2; }")
    statements = [n for n in walk(view.tree.root_node) if n.type == "expression_statement"]
    projector = exact_projector(view, statements)
    assert len(statement_units(view, projector)) == 2
    view.mapping.pop(ast_key(statements[0]))
    units = statement_units(view, projector)
    assert len(units) == 1 and units[0].ast_node == statements[1]
    assert projected_node(view, SimpleNamespace(by_ast={}), statements[1]) is None
