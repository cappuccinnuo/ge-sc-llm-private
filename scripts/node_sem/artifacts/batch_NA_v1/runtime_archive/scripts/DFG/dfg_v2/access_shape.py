"""Pure recognition of the installed grammar's prefix/access-chain shape.

The grammar can represent delete a[i].field as a member/array chain whose
base is unary_expression(delete, a). This helper only inspects AST fields;
it neither rewrites the AST nor decides bindings or read/write semantics.
"""
from ..models import Unsupported


def prefix_access_shape(node):
    """Return (operator, operated_base, indices) or None.

    operated_base is the original unary/update argument node. indices contains
    original index nodes in base-to-outer order. For example,
    delete holders[i].amount returns ("delete", <holders>, (<i>,)).
    Only delete/++/-- at the beginning of the entire supplied expression are
    recognized. Nested index side effects remain intact for the caller to
    reject or audit according to its own existing access policy.

    Derived without semantic changes from
    ExtendedAccessExtractor._prefix_access_event (Prompt 2). No source text,
    symbol table, scope/version decision, graph, feature or label is consulted.
    """
    pointer, indices = node, []
    while pointer is not None and pointer.type in ("member_expression", "array_access"):
        if pointer.type == "array_access":
            indices.append(pointer.child_by_field_name("index"))
            pointer = pointer.child_by_field_name("base")
        else:
            pointer = pointer.child_by_field_name("object")
    if pointer is None or pointer.type not in ("unary_expression", "update_expression"):
        return None
    operator = pointer.child_by_field_name("operator")
    argument = pointer.child_by_field_name("argument")
    if operator is None or argument is None:
        raise Unsupported("V2: malformed prefix access chain")
    spelling = operator.type
    if (pointer.start_byte != node.start_byte
            or operator.start_byte != node.start_byte
            or operator.end_byte > argument.start_byte
            or spelling not in ("delete", "++", "--")):
        return None
    return spelling, argument, tuple(reversed(indices))
