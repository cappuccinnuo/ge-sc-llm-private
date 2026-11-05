"""One parameterless prefix modifier, ending in exactly one top-level _."""
from ...frontend import text, walk, span
from ...models import Unsupported
from ..stage_f.versioning import available

def children(n):
    return [c for c in n.named_children if "comment" not in c.type]

def placeholder(n, source):
    cs = children(n)
    return (n.type == "expression_statement" and len(cs) == 1
            and cs[0].type == "identifier" and text(source, cs[0]) == "_")

def prefix_modifier(view, function, scope):
    calls = [n for n in function.named_children if n.type == "modifier_invocation"]
    if not calls:
        return [], None
    if len(calls) != 1:
        raise Unsupported("J: multiple modifier invocations unsupported")
    call = calls[0]
    cs = children(call)
    if len(cs) != 1 or cs[0].type != "identifier":
        raise Unsupported("J: modifier arguments/qualified invocation unsupported")
    name = text(view.source, cs[0])
    declarations = scope.require_unambiguous(name)
    if len(declarations) != 1 or declarations[0].type != "modifier_definition":
        raise Unsupported("J: modifier binding is not a unique declaration")
    modifier = declarations[0]
    if any(n.type == "parameter" for n in modifier.named_children):
        raise Unsupported("J: modifier parameters unsupported")
    if any(n.type == "modifier_invocation" for n in modifier.named_children):
        raise Unsupported("J: nested modifier invocation unsupported")
    body = modifier.child_by_field_name("body")
    if body is None:
        raise Unsupported("J: modifier has no body")
    statements = children(body)
    holes = [n for n in walk(body) if placeholder(n, view.source)]
    if len(holes) != 1 or not statements or holes[0] != statements[-1]:
        raise Unsupported("J: requires one unconditional terminal placeholder; suffix/conditional/repeated _ unsupported")
    prefix = statements[:-1]
    for statement in prefix:
        if statement.type != "expression_statement":
            raise Unsupported("J: modifier prefix only supports straight-line expressions")
        for node in walk(statement):
            if node.type in ("variable_declaration", "return_statement", "assembly_statement"):
                raise Unsupported("J: modifier local declarations/control unsupported")
            if node.type == "call_expression":
                callee = node.child_by_field_name("function")
                name = text(view.source, callee) if callee is not None else ""
                # Only a top-level, confirmed builtin guard; nested calls are not pure.
                direct = children(statement)
                if len(direct) != 1 or direct[0] != node or callee.type != "identifier":
                    raise Unsupported("J: effectful/nested modifier call unsupported")
                global_shadow = any(n.child_by_field_name("name") is not None and
                    text(view.source, n.child_by_field_name("name")) == name
                    for n in view.tree.root_node.named_children)
                if (name not in ("require", "assert") or name in scope.members or name in scope.hidden
                        or global_shadow or not available(view, name)):
                    raise Unsupported("J: modifier guard builtin binding/version uncertain")
    return prefix, {
        "modifier_name": text(view.source, modifier.child_by_field_name("name")),
        "declaration": {"start": modifier.start_byte, "end": modifier.end_byte},
        "invocation": {"start": call.start_byte, "end": call.end_byte},
        "placeholder": {"start": holes[0].start_byte, "end": holes[0].end_byte},
        "parameter_binding": "none; arguments and parameters rejected",
        "execution": "prefix then function body; no suffix",
        "control_dependence_edges": False,
    }
