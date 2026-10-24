"""Statement-owned expression regions with exact existing-HCG projection.

A missing child statement never migrates to an enclosing if/function node.
For-header parts are the deliberate exception in the Prompt 3 ownership rule:
a part without its own HCG node belongs to its for node; mapped parts own
themselves.  No executable block is ever used as an expression region.
"""
from collections import namedtuple

from scripts.DFG.frontend import walk

Unit = namedtuple("Unit", "hcg_node_id ast_node regions")
StatementRegions = namedtuple("StatementRegions", "ast_node regions")

WHOLE_STATEMENTS = frozenset((
    "expression_statement", "variable_declaration_statement",
    "return_statement", "emit_statement", "revert_statement", "throw_statement",
))
CALLABLES = frozenset((
    "function_definition", "constructor_definition", "modifier_definition",
    "fallback_receive_definition",
))
CONDITIONALS = frozenset((
    "if_statement", "while_statement", "do_while_statement",
))
HEADER_FIELDS = ("initial", "condition", "update")


def ast_key(node):
    return node.start_byte, node.end_byte, node.type


def projected_node(view, projector, node):
    """Return the exact HCG identity, or None; never infer a nearby anchor."""
    if projector is None:
        return None
    key = view.mapping.get(ast_key(node))
    if key is None:
        return None
    compat_id = view.compat_ids.get(key)
    if compat_id is None:
        return None
    return projector.by_ast.get(compat_id)


def _for_part(node):
    parent = node.parent
    if parent is None or parent.type != "for_statement":
        return False
    return any(parent.child_by_field_name(field) == node for field in HEADER_FIELDS)


def _regions(node, view, projector):
    if node.type in WHOLE_STATEMENTS:
        return (node,)
    if node.type in CONDITIONALS:
        condition = node.child_by_field_name("condition")
        return () if condition is None else (condition,)
    if node.type == "try_statement":
        # The attempt is owned by try itself, never by the enclosing function.
        # Absent exact HCG try nodes remain auditable unmapped occurrences.
        attempt = node.child_by_field_name("attempt")
        return () if attempt is None else (attempt,)
    if node.type == "for_statement":
        parts = [node.child_by_field_name(field) for field in HEADER_FIELDS]
        return tuple(part for part in parts if part is not None
                     and projected_node(view, projector, part) is None)
    if node.type in CALLABLES:
        return tuple(argument
                     for invocation in node.named_children
                     if invocation.type == "modifier_invocation"
                     for argument in invocation.named_children
                     if argument.type == "call_argument")
    if node.type == "state_variable_declaration":
        value = node.child_by_field_name("value")
        return () if value is None else (value,)
    if _for_part(node) and projected_node(view, projector, node) is not None:
        return (node,)
    return None


def iter_statement_regions(view, projector=None):
    """Yield source-only candidates, including statements without HCG nodes.

    Pass the same Projector used by statement_units when auditing unmapped
    accesses: this preserves exactly the same for-header ownership partition.
    With no Projector all header parts belong to their for statement.
    Empty-region declaration/callable units are retained for coverage counts.
    """
    for node in walk(view.tree.root_node):
        if _for_part(node) and projected_node(view, projector, node) is None:
            continue
        regions = _regions(node, view, projector)
        if regions is not None:
            yield StatementRegions(node, regions)


def statement_units(view, projector):
    """Return only exact mapped candidates; no graph attribute drives analysis."""
    result = []
    for candidate in iter_statement_regions(view, projector):
        identifier = projected_node(view, projector, candidate.ast_node)
        if identifier is not None:
            result.append(Unit(identifier, candidate.ast_node, candidate.regions))
    return result
