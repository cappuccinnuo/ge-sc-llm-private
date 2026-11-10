"""Bounded same-file CALL_SITE resolution (EP0c-EP0e, EdgeSem plan r7).

Frozen dependencies, imported without modification:
scripts/node_sem/facts_ast.py SHA256:
644ca31a1dd890f67ac850e28fa68b9ae6b585cb0be019a6611aba154fc1d5a5
AstSemantics.resolve_callable, root_binding, resolve_identifier, members,
scope, arguments, builtin_call and _postfix. Declaration identity, not a
vulnerability/name pattern, determines targets. Unresolved cases have no target.
Library means a same-file library definition, not an assertion about EVM opcodes.
_resolve_callee copies facts_ast.py::AstSemantics.resolve_callable lines 189-205
(SHA256 above), accepting an explicit callee instead of extracting it from call.
Only unary/binary callees use the frozen _postfix before this local binding step.
The original NodeSem method and its bytecode are never modified.
_using_resolve copies the using traversal/matching in the same frozen file,
lines 226-244 (scope check at 217-218), using the supplied receiver type.
Approved EP0e exception: an any_source_type("*") directive imposes no source
type restriction; the library's first parameter still must match exactly.
receiver_type is EdgeSem-local; it does not alter the frozen type/DFG analysis.
"""
from scripts.node_sem.facts_ast import FUNCTIONS, key, unwrap

FROZEN_AST_SHA256 = "644ca31a1dd890f67ac850e28fa68b9ae6b585cb0be019a6611aba154fc1d5a5"
BUILTINS = frozenset(("require", "assert", "revert", "selfdestruct", "suicide",
    "keccak256", "sha3", "sha256", "ripemd160", "ecrecover", "addmod", "mulmod",
    "blockhash", "gasleft"))
ADDRESS_METHODS = frozenset(("transfer", "send", "call", "delegatecall", "staticcall"))
EVENT_STRUCT = frozenset(("event_definition", "event_declaration", "struct_declaration",
                         "enum_declaration", "error_declaration"))


def result(status, kind=None, target=None, reason=""):
    return dict(status=status, kind=kind, target=target, reason=reason)


def _unshadowed(sem, node, name):
    return (node is not None and node.type == "identifier" and sem.text(node) == name
            and sem.resolve_identifier(node)["kind"] == "unknown"
            and not sem.members(node).get(name)
            and not sem.has_import
            and sem.scope(node) is not None)


def _address_receiver(sem, receiver):
    receiver = unwrap(receiver)
    # Approved EP0d correction: the frozen grammar can attach a prefix to
    # msg.sender inside the receiver rather than to the whole callee. This
    # affects only exclusion classification, never a function binding target.
    if receiver is not None and receiver.type in ("unary_expression", "binary_expression"):
        receiver = sem._postfix(receiver)
    if receiver is None:
        return False
    if receiver.type == "identifier":
        binding = sem.root_binding(receiver)
        return (binding["declaration"] is not None
                and " ".join(binding["type_name"].split()) in ("address", "address payable"))
    if receiver.type == "member_expression":
        obj = unwrap(receiver.child_by_field_name("object"))
        prop = sem.text(receiver.child_by_field_name("property"))
        return ((_unshadowed(sem, obj, "msg") and prop == "sender")
                or (_unshadowed(sem, obj, "tx") and prop == "origin"))
    if receiver.type == "payable_conversion_expression":
        return True
    if receiver.type in ("call_expression", "type_cast_expression"):
        callee = unwrap(receiver.child_by_field_name("function"))
        if callee is None:
            callee = receiver.child_by_field_name("type")
        if callee is None and receiver.type == "type_cast_expression":
            callee = next((n for n in receiver.named_children if n.type == "primitive_type"), None)
        if callee is not None and sem.text(callee) in ("address", "payable"):
            # Primitive type tokens cannot bind a user declaration; identifiers
            # require the usual shadow/import checks.
            return callee.type != "identifier" or _unshadowed(sem, callee, sem.text(callee))
    return False


def _contract_receiver(sem, receiver):
    receiver = unwrap(receiver)
    if receiver is None:
        return False
    if _unshadowed(sem, receiver, "this"):
        return True
    # root_binding alone would confuse struct.member with the root's type.
    # Complex receivers stay unknown unless the cast rule below applies.
    if receiver.type != "identifier":
        return False
    binding = sem.root_binding(receiver)
    if binding["declaration"] is None:
        return False
    types = [c for c in sem.contracts
             if c.type in ("contract_declaration", "interface_declaration")
             and sem.text(c.child_by_field_name("name")) == binding["type_name"].strip()]
    return len(types) == 1


def _resolve_callee(sem, call_node, callee):
    """Frozen resolve_callable binding rules with an explicit callee argument."""
    if callee is None:
        return None
    if callee.type == "identifier":
        binding = sem.resolve_identifier(callee)
        if binding["kind"] != "function" or sem.scope(call_node) is None:
            return None
        rows = sem.members(call_node).get(sem.text(callee), [])
        if len(rows) != 1 or key(rows[0]) != key(binding["declaration"]):
            return None
    elif callee.type == "member_expression":
        receiver = unwrap(callee.child_by_field_name("object"))
        name = sem.text(callee.child_by_field_name("property"))
        library = sem.resolve_identifier(receiver).get("declaration")
        if library is None or library.type != "library_declaration":
            return sem._using_callable(call_node, receiver, name)
        rows = [x for x in library.child_by_field_name("body").named_children
                if sem.text(x.child_by_field_name("name")) == name]
    else:
        return None
    return rows[0] if len(rows) == 1 and rows[0].type == "function_definition" else None


def _resolved(sem, call_node, target, reason):
    contract = sem.contract(target)
    if contract is not None and contract.type == "library_declaration":
        kind = "library"
    elif key(contract) != key(sem.contract(call_node)):
        kind = "inherited"
    else:
        kind = "internal"
    return result("resolved", kind, target, reason)



def _indexed_type(type_name):
    """One index step; delimiters, not names, determine the element type."""
    if not type_name:
        return None
    if type_name.endswith("]"):
        opening = type_name.rfind("[")
        return type_name[:opening] or None if opening >= 0 else None
    if not (type_name.startswith("mapping(") and type_name.endswith(")")):
        return None
    depth, arrows = 0, []
    for i, char in enumerate(type_name):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0 or (depth == 0 and i != len(type_name)-1):
                return None
        elif char == "=" and type_name[i:i+2] == "=>" and depth == 1:
            arrows.append(i)
    if depth != 0 or len(arrows) != 1:
        return None
    return type_name[arrows[0]+2:-1] or None


def _struct_field_type(sem, type_name, field):
    if not type_name:
        return None
    matches = []
    for node in sem.nodes:
        if node.type != "struct_declaration":
            continue
        name = sem.text(node.child_by_field_name("name"))
        contract = sem.contract(node)
        qualified = (sem.text(contract.child_by_field_name("name"))+"."+name
                     if contract is not None else name)
        if type_name == name or type_name == qualified:
            matches.append(node)
    if len(matches) != 1:
        return None
    fields = [n for n in matches[0].named_children if n.type == "struct_member"
              and sem.text(n.child_by_field_name("name")) == field]
    if len(fields) != 1:
        return None
    return sem._canonical_type(sem.text(fields[0].child_by_field_name("type"))) or None


def receiver_type(sem, expr):
    """Bounded expression type from syntax and declarations; unknown is None."""
    expr = unwrap(expr)
    if expr is None:
        return None
    if expr.type == "identifier":
        binding = sem.root_binding(expr)
        if binding["declaration"] is not None:
            return sem._canonical_type(binding["type_name"]) or None
        if _unshadowed(sem, expr, "now"):
            return "uint256"
        return None
    if expr.type == "number_literal":
        return "uint256"
    if expr.type == "array_access":
        return _indexed_type(receiver_type(sem, expr.child_by_field_name("base")))
    if expr.type == "member_expression":
        base = unwrap(expr.child_by_field_name("object"))
        member = sem.text(expr.child_by_field_name("property"))
        base_type = receiver_type(sem, base)
        declared = _struct_field_type(sem, base_type, member)
        if declared is not None:
            return declared
        for namespace, fields in (
                ("msg", {"value": "uint256", "sender": "address"}),
                ("block", {"timestamp": "uint256", "number": "uint256"}),
                ("tx", {"origin": "address"})):
            if member in fields and _unshadowed(sem, base, namespace):
                return fields[member]
        if member == "length" and base_type and (
                base_type.endswith("]") or base_type == "bytes"
                or (base_type.startswith("bytes") and base_type[5:].isdigit())):
            return "uint256"
        if member == "balance" and base_type == "address":
            return "uint256"
        return None
    if expr.type in ("type_cast_expression", "payable_conversion_expression"):
        if expr.type == "payable_conversion_expression":
            return "address"
        primitive = next((n for n in expr.named_children if n.type == "primitive_type"), None)
        return sem._canonical_type(sem.text(primitive)) or None
    if expr.type == "call_expression":
        target = resolve_call(sem, expr)["target"]
        if target is None:
            return None
        returns = target.child_by_field_name("return_type")
        parameters = ([] if returns is None else
                      [n for n in returns.named_children if n.type == "parameter"])
        if len(parameters) != 1:
            return None
        return sem._canonical_type(sem.text(parameters[0].child_by_field_name("type"))) or None
    if expr.type == "binary_expression":
        symbols = {"+", "-", "*", "/", "%", "**", "==", "!=", "<", ">", "<=", ">=", "&&", "||"}
        op = next((sem.text(n) for n in expr.children if not n.is_named and sem.text(n) in symbols), None)
        if op in ("==", "!=", "<", ">", "<=", ">=", "&&", "||"):
            return "bool"
        if op not in ("+", "-", "*", "/", "%", "**"):
            return None
        left, right = unwrap(expr.child_by_field_name("left")), unwrap(expr.child_by_field_name("right"))
        lt, rt = receiver_type(sem, left), receiver_type(sem, right)
        if lt is not None and lt == rt:
            return lt
        if left is not None and left.type == "number_literal":
            return rt
        if right is not None and right.type == "number_literal":
            return lt
    return None


def _using_resolve(sem, call_node, receiver_type, method):
    """Frozen using traversal/matching with a caller-supplied canonical type."""
    if not receiver_type:
        return None
    scope = sem.scope(call_node)
    if scope is None:
        return None
    matches = []
    for contract in scope.chain:
        body = contract.child_by_field_name("body")
        for directive in body.named_children:
            if directive.type != "using_directive":
                continue
            source = directive.child_by_field_name("source")
            wildcard = source is not None and source.type == "any_source_type" and sem.text(source) == "*"
            if source is not None and not wildcard and sem._canonical_type(sem.text(source)) != receiver_type:
                continue
            alias = next((x for x in directive.named_children if x.type == "type_alias"), None)
            if alias is None:
                continue
            libs = [x for x in sem.contracts if x.type == "library_declaration"
                    and sem.text(x.child_by_field_name("name")) == sem.text(alias)]
            if len(libs) != 1:
                continue
            functions = [x for x in libs[0].child_by_field_name("body").named_children
                         if x.type == "function_definition" and sem.text(x.child_by_field_name("name")) == method]
            if len(functions) != 1:
                continue
            fn = functions[0]
            params = [x for x in fn.named_children if x.type == "parameter"]
            if (len(params) != len(sem.arguments(call_node))+1
                    or sem._canonical_type(sem.text(params[0].child_by_field_name("type"))) != receiver_type):
                continue
            matches.append(fn)
    unique = {key(fn): fn for fn in matches}
    return next(iter(unique.values())) if len(unique) == 1 else None


def _call_option_receiver(sem, callee):
    """Return the root receiver of .call[.gas(...)].value(...), if present."""
    if callee is None or callee.type != "member_expression":
        return None
    if sem.text(callee.child_by_field_name("property")) not in ("value", "gas"):
        return None
    base = unwrap(callee.child_by_field_name("object"))
    while base is not None and base.type == "call_expression":
        option = sem._postfix(unwrap(base.child_by_field_name("function")))
        if (option is None or option.type != "member_expression"
                or sem.text(option.child_by_field_name("property")) not in ("value", "gas")):
            return None
        base = unwrap(option.child_by_field_name("object"))
    if (base is not None and base.type == "member_expression"
            and sem.text(base.child_by_field_name("property")) in ("call", "delegatecall", "staticcall")):
        return unwrap(base.child_by_field_name("object"))
    return None


def resolve_call(sem, call_node):
    """Return status/kind/target plus a diagnostic reason; never mutate a graph.

    Resolved statuses have an AST definition target. Arity resolution deliberately
    does not compare argument types or guess overload/override dispatch.
    """
    if call_node is not None and call_node.type == "emit_statement":
        return result("event_or_struct", reason="explicit_emit_statement")
    if call_node is None or call_node.type != "call_expression":
        return result("unknown", reason="not_call_expression")
    target = sem.resolve_callable(call_node)
    if target is not None and target.type in FUNCTIONS:
        return _resolved(sem, call_node, target, "frozen_unique_declaration")

    callee = unwrap(call_node.child_by_field_name("function"))
    if callee is None:
        return result("unknown", reason="missing_callee")
    if sem.builtin_call(call_node, BUILTINS):
        return result("builtin", reason="unshadowed_builtin")
    # EP0d: preserve the original AST and resolve only the suffix already
    # selected by the frozen fact pipeline. Non-composite callees are unchanged.
    diagnostic_callee = sem._postfix(callee)
    postfix = callee.type in ("unary_expression", "binary_expression")
    if postfix:
        target = _resolve_callee(sem, call_node, diagnostic_callee)
        if target is not None:
            return _resolved(sem, call_node, target, "postfix_callee")
        callee = diagnostic_callee
    if callee is not None and callee.type == "identifier":
        binding = sem.resolve_identifier(callee)
        members = sem.members(call_node).get(sem.text(callee), [])
        functions = [n for n in members if n.type == "function_definition"]
        if (sem.scope(call_node) is not None and len(functions) > 1
                and len(functions) == len(members) and binding["kind"] == "unknown"):
            count = len(sem.arguments(call_node))
            matches = [fn for fn in functions
                       if len([p for p in fn.named_children if p.type == "parameter"]) == count]
            if len(matches) == 1:
                return result("resolved", "overload_arity", matches[0],
                              "postfix_callee" if postfix else "unique_parameter_count")
            return result("overload_unresolved", reason="parameter_count_not_unique")
        if members and all(n.type in EVENT_STRUCT for n in members):
            return result("event_or_struct", reason="declared_non_function")
        return result("unknown", reason="unbound_or_unsupported_identifier")

    if diagnostic_callee is not None and diagnostic_callee.type == "new_expression":
        return result("new_contract", reason="new_expression")
    if diagnostic_callee is not None and diagnostic_callee.type == "member_expression":
        receiver = unwrap(diagnostic_callee.child_by_field_name("object"))
        method = sem.text(diagnostic_callee.child_by_field_name("property"))
        target = _using_resolve(sem, call_node, receiver_type(sem, receiver), method)
        if target is not None:
            return result("resolved", "library", target, "typed_receiver")
        option_receiver = _call_option_receiver(sem, diagnostic_callee)
        if option_receiver is not None:
            return result("call_option", reason=("address_receiver"
                if _address_receiver(sem, option_receiver) else "unconfirmed_receiver"))
        if (method in ("encode", "encodePacked", "encodeWithSelector", "encodeWithSignature", "decode")
                and _unshadowed(sem, receiver, "abi")):
            return result("builtin", reason="unshadowed_abi_builtin")
        if _unshadowed(sem, receiver, "super"):
            return result("super", reason="super_dispatch_not_implemented")
        if method in ADDRESS_METHODS and _address_receiver(sem, receiver):
            return result("address_builtin", reason="confirmed_address_receiver")
        if receiver is not None and receiver.type in ("call_expression", "type_cast_expression"):
            cast = unwrap(receiver.child_by_field_name("function"))
            if cast is None:
                cast = receiver.child_by_field_name("type")
            declaration = sem.resolve_identifier(cast).get("declaration")
            if declaration is not None and declaration.type in (
                    "contract_declaration", "interface_declaration"):
                return result("cast_member", reason="confirmed_same_file_contract_cast")
        if _contract_receiver(sem, receiver):
            return result("external_member", reason="confirmed_contract_receiver")
        return result("unknown", reason="receiver_or_member_not_confirmed")
    return result("unknown", reason="unsupported_callee_shape")
