"""Read-only mechanical classifications for Prompt 6d.1.

All predicates consume sealed event evidence and the source AST. This module
does not run analyzers, compilers, graph construction, or model computation.
A pattern is not a correctness proof; convention verdicts additionally require
the separately saved, positive direct Slither probe.
"""
from scripts.DFG.frontend import walk

VERSION = "dfg-v2-slither-patterns-v1"
PATTERN_CATEGORIES = (
    "modifier_body_unanalyzed", "loop_header_merge_write",
    "aggregate_base_use", "bare_expression_use", "legacy_alias_unconfirmed",
)
CALLABLES = frozenset(("function_definition", "constructor_definition",
                      "fallback_receive_definition", "modifier_definition"))
CONTAINERS = frozenset(("contract_declaration", "library_declaration",
                       "interface_declaration"))
WRITES = frozenset(("assignment_expression", "augmented_assignment_expression",
                   "update_expression"))
WRAPPERS = frozenset(("expression", "parenthesized_expression",
                      "expression_statement"))


def _interval(node):
    return [node.start_byte, node.end_byte]


def _contains(outer, inner):
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def _overlap(a, b):
    return a[0] < b[1] and b[0] < a[1]


def _unwrap(node):
    while node is not None and node.type in WRAPPERS:
        children = [x for x in node.named_children if "comment" not in x.type]
        if len(children) != 1:
            break
        node = children[0]
    return node


def _ancestor(node, kinds):
    while node is not None and node.type not in kinds:
        node = node.parent
    return node


def _root(node):
    node = _unwrap(node)
    while node is not None and node.type in ("member_expression", "array_access"):
        node = _unwrap(node.child_by_field_name(
            "object" if node.type == "member_expression" else "base"))
    return node if node is not None and node.type == "identifier" else None


def _same_binding(a, b):
    return (a.get("name") == b.get("name") and
            a.get("function_start") == b.get("function_start") and
            a.get("declaration") is not None and b.get("declaration") is not None and
            a["declaration"][0] == b["declaration"][0])


def _exact_declaration(event, ast):
    return ast.named_declaration(event, state=event["layer"] == "L2")


def _declaration_scope(node):
    if node.type == "parameter":
        return _ancestor(node.parent, CALLABLES)
    return _ancestor(node.parent, frozenset(("block_statement", "function_body",
                                             "for_statement")) | CALLABLES | CONTAINERS)


def _bound_identifier(node, event, ast):
    """Check the supplied declaration identity and reject lexical shadowing.

    This is deliberately narrower than Solidity binding. Uncertain duplicate
    declarations fail; inherited state identities must already be sealed.
    """
    if node is None or node.type != "identifier" or ast.text(node) != event["name"]:
        return False
    declaration = _exact_declaration(event, ast)
    if declaration is None:
        return False
    context = _ancestor(node, CALLABLES)
    if context is None or context.start_byte != event.get("function_start"):
        return False
    target_scope = _declaration_scope(declaration)
    if declaration.type != "state_variable_declaration":
        if target_scope is None or not _contains(_interval(target_scope), _interval(node)):
            return False
        if declaration.type != "parameter" and declaration.start_byte > node.start_byte:
            return False
    for other in ast.nodes:
        if other.type not in ("parameter", "variable_declaration"):
            continue
        name = other.child_by_field_name("name")
        if name is None or ast.text(name) != event["name"] or other.start_byte == declaration.start_byte:
            continue
        scope = _declaration_scope(other)
        if scope is None or not _contains(_interval(scope), _interval(node)):
            continue
        if other.type != "parameter" and other.start_byte > node.start_byte:
            continue
        if declaration.type == "state_variable_declaration":
            return False
        if target_scope is None or _contains(_interval(target_scope), _interval(scope)):
            return False
    return True


def _convention(conventions, key, layer=None):
    item = (conventions or {}).get(key)
    if not isinstance(item, dict):
        return None
    if key == "loop_header_merge_write":
        observations = item.get("observations", [])
        field = "local_variables_written" if layer == "L1" else "state_variables_written"
        observed = [o for o in observations if o.get("node_type") == "IF_LOOP"
                    and o.get("target_name") in o.get(field, []) and o.get("phi_in_ssa")]
        if not observed:
            return None
        item = dict(item, confirmed=True, observed_layer=layer, observations=observed)
    if item.get("confirmed") is not True:
        return None
    # A caller must supply the full observed record, not just a truth value.
    if not item.get("observations"):
        return None
    return item


def _result(category, predicate, **basis):
    return category, dict({"predicate": predicate}, **basis), "v2_scope_limit"


def _modifier(event, direction, ast, candidate):
    if event["layer"] != "L1" or direction != "FN":
        return None
    modifiers = [n for n in ast.nodes if n.type == "modifier_definition" and
                 n.start_byte == event.get("function_start")]
    if len(modifiers) != 1 or _exact_declaration(event, ast) is None:
        return None
    modifier = modifiers[0]
    body = modifier.child_by_field_name("body")
    if body is None or not _contains(_interval(body), event["span"]):
        return None
    # A modifier flag/name alone is insufficient. The exact AST context and
    # absence of supported, inlined events within its body are both required.
    inlined = [c["event_id"] for c in candidate
               if c.get("function_scope") == "supported" and
               _contains(_interval(body), c["span"])]
    if inlined:
        return None
    return _result("modifier_body_unanalyzed",
                   "exact_modifier_context_without_supported_L1_body_event",
                   modifier_span=_interval(modifier), body_span=_interval(body),
                   declaration=event["declaration"], inlined_event_ids=[],
                   scope_reference="PROMPTS.md 6d.1 section 2/3: L1 does not separately analyze modifier bodies")


def _write_root(node):
    if node.type in ("assignment_expression", "augmented_assignment_expression"):
        return _root(node.child_by_field_name("left"))
    if node.type == "update_expression":
        return _root(node.child_by_field_name("argument"))
    return None


def _loop(event, direction, ast, conventions):
    if direction != "FN" or event["kind"] not in ("DEF", "WRITE"):
        return None
    convention = _convention(conventions, "loop_header_merge_write", event["layer"])
    if convention is None or _exact_declaration(event, ast) is None:
        return None
    for loop in ast.nodes:
        if loop.type not in ("while_statement", "for_statement", "do_while_statement"):
            continue
        condition = _unwrap(loop.child_by_field_name("condition"))
        if condition is None or _interval(condition) != event["span"]:
            continue
        if any(n.type in WRITES or
               (n.type == "unary_expression" and n.child_by_field_name("operator") is not None
                and n.child_by_field_name("operator").type == "delete")
               for n in walk(condition)):
            continue
        writes = []
        for part in (loop.child_by_field_name("body"), loop.child_by_field_name("update")):
            if part is None:
                continue
            writes.extend(_interval(n) for n in walk(part)
                          if n.type in WRITES and _bound_identifier(_write_root(n), event, ast))
        if writes:
            return ("loop_header_merge_write",
                    dict(predicate="exact_loop_condition_without_assignment_and_same_declaration_body_or_update_write",
                         condition_span=_interval(condition), loop_span=_interval(loop),
                         declaration=event["declaration"], actual_write_spans=sorted(writes),
                         reference_node_type=sorted({r["node_type"] for r in event.get("evidence", [])
                                                     if r.get("node_type")}),
                         reference_node_type_missing=not any(r.get("node_type")
                                                            for r in event.get("evidence", [])),
                         node_type_evidence="exact source AST condition; no Slither node type invented",
                         convention=convention), "slither_convention")
    return None


def _statement(event, ast):
    found = [n for n in ast.nodes if n.type == "expression_statement" and
             _interval(n) == event["span"]]
    return found[0] if len(found) == 1 else None


def _aggregate(event, direction, ast, candidate, reference, conventions):
    if event["layer"] != "L1" or direction != "FP" or event["kind"] != "USE":
        return None
    convention = _convention(conventions, "aggregate_base_use")
    statement = _statement(event, ast)
    if convention is None or statement is None:
        return None
    expression = _unwrap(statement)
    if expression is None or expression.type != "assignment_expression":
        return None
    left = _unwrap(expression.child_by_field_name("left"))
    if left is None or left.type not in ("array_access", "member_expression"):
        return None
    if not _bound_identifier(_root(left), event, ast):
        return None
    defs = [c for c in candidate if c["kind"] == "DEF" and _same_binding(event, c)
            and c["span"] == event["span"] and
            any(r.get("weak_write") is True for r in c.get("evidence", []))]
    ref_defs = [r for r in reference if r["kind"] == "DEF" and _same_binding(event, r)
                and _contains(event["span"], r["span"])]
    ref_uses = [r for r in reference if r["kind"] == "USE" and _same_binding(event, r)
                and _overlap(event["span"], r["span"])]
    if not defs or not ref_defs or ref_uses:
        return None
    return ("aggregate_base_use",
            dict(predicate="exact_aggregate_assignment_root_has_weak_DEF_and_reference_DEF_only",
                 statement_span=event["span"], lhs_span=_interval(left),
                 declaration=event["declaration"], weak_def_event_ids=[r["event_id"] for r in defs],
                 reference_write_event_ids=[r["event_id"] for r in ref_defs],
                 scope_reference="PROMPTS.md section 3.2: aggregate writes use the base and weakly define it",
                 convention=convention), "slither_convention")


def _bare_shape(expression, ast):
    if expression.type == "identifier":
        return "identifier"
    if expression.type != "call_expression":
        return None
    fn = _unwrap(expression.child_by_field_name("function"))
    if fn is None or fn.type != "member_expression":
        return None
    prop, target = fn.child_by_field_name("property"), _unwrap(fn.child_by_field_name("object"))
    if prop is None or ast.text(prop) not in ("value", "gas") or target is None or target.type != "member_expression":
        return None
    method, receiver = target.child_by_field_name("property"), _root(target.child_by_field_name("object"))
    if method is None or ast.text(method) not in ("call", "delegatecall", "callcode") or receiver is None:
        return None
    # This is an uninvoked low-level-call option setter, not an arbitrary
    # method named value/gas and not the outer invocation (...)(...).
    local = [d for d in ast.nodes if d.type in ("parameter", "variable_declaration")
             and d.child_by_field_name("name") is not None
             and ast.text(d.child_by_field_name("name")) == ast.text(receiver)
             and _ancestor(d, CALLABLES) == _ancestor(expression, CALLABLES)]
    if len(local) != 1:
        return None
    typ = local[0].child_by_field_name("type")
    if typ is None or ast.text(typ) not in ("address", "address payable"):
        return None
    return "uninvoked_low_level_option"


def _bare(event, direction, ast, reference, conventions):
    if event["layer"] != "L1" or direction != "FP" or event["kind"] != "USE":
        return None
    convention = _convention(conventions, "bare_expression_use")
    statement = _statement(event, ast)
    if convention is None or statement is None:
        return None
    expression = _unwrap(statement)
    if expression is None:
        return None
    shape = _bare_shape(expression, ast)
    if shape is None or not any(_bound_identifier(n, event, ast) for n in walk(expression)):
        return None
    if any(r["kind"] == "USE" and _same_binding(event, r) and
           _overlap(r["span"], event["span"]) for r in reference):
        return None
    return ("bare_expression_use",
            dict(predicate="exact_unused_expression_with_confirmed_binding_and_no_reference_USE",
                 statement_span=event["span"], shape=shape, declaration=event["declaration"],
                 convention=convention), "slither_convention")


def _legacy_alias(event, direction, ast, diagnostics):
    if event["layer"] != "L2" or direction != "FN":
        return None
    state = _exact_declaration(event, ast)
    if state is None:
        return None
    for diagnostic in diagnostics:
        if diagnostic.get("reason") != "legacy_alias_version_unconfirmed":
            continue
        if str(diagnostic.get("callable", "")).rsplit(":", 1)[-1] != str(event.get("function_start")):
            continue
        interval = [diagnostic.get("start"), diagnostic.get("end")]
        declarations = [n for n in ast.nodes if n.type == "variable_declaration" and
                        _interval(n) == interval]
        if len(declarations) != 1:
            continue
        declaration = declarations[0]
        statement = _ancestor(declaration, frozenset(("variable_declaration_statement",)))
        if statement is None:
            continue
        root = _root(statement.child_by_field_name("value"))
        if not _bound_identifier(root, event, ast):
            continue
        identifier = declaration.child_by_field_name("name")
        if identifier is None:
            continue
        alias_event = dict(event, layer="L1", name=ast.text(identifier), declaration=interval)
        occurrences = [n for n in ast.nodes if _contains(event["span"], _interval(n)) and
                       _bound_identifier(n, alias_event, ast)]
        if not occurrences:
            continue
        # A matching occurrence exclusion links the unresolved alias declaration
        # to this exact reference statement; names alone are not enough.
        exclusions = [d for d in diagnostics if d.get("reason") == "callable_local_shadows_state"
                      and d.get("callable") == diagnostic.get("callable")
                      and any([d.get("start"), d.get("end")] == _interval(n) for n in occurrences)]
        if not exclusions:
            continue
        return _result("legacy_alias_unconfirmed",
                       "exact_unconfirmed_alias_declaration_initializer_and_occurrence_exclusion",
                       state_declaration=event["declaration"], alias_declaration=interval,
                       alias_initializer=_interval(statement.child_by_field_name("value")),
                       diagnostic=diagnostic, occurrence_diagnostics=exclusions,
                       scope_reference="PROMPTS.md section 3.2/3.3 and Prompt 3 accepted policy: no implicit legacy alias without version evidence")
    return None


def classify_pattern(event, direction, ast, candidate, reference, diagnostics,
                     conventions=None):
    """Return (category, evidence, verdict), or None; call after old categories."""
    checks = (
        lambda: _modifier(event, direction, ast, candidate),
        lambda: _loop(event, direction, ast, conventions),
        lambda: _aggregate(event, direction, ast, candidate, reference, conventions),
        lambda: _bare(event, direction, ast, reference, conventions),
        lambda: _legacy_alias(event, direction, ast, diagnostics),
    )
    for check in checks:
        result = check()
        if result is not None:
            return result
    return None


def _inheritance_path(ast, current, target, seen=None):
    """Only unique same-file AST base declarations; no external-name guess."""
    seen = set() if seen is None else set(seen)
    if current.start_byte in seen:
        return None
    seen.add(current.start_byte)
    for spec in (n for n in current.named_children if n.type == "inheritance_specifier"):
        ancestor = spec.child_by_field_name("ancestor")
        if ancestor is None:
            continue
        bases = [n for n in ast.nodes if n.type in CONTAINERS
                 and n.child_by_field_name("name") is not None
                 and ast.text(n.child_by_field_name("name")) == ast.text(ancestor)]
        if len(bases) != 1:
            continue
        base = bases[0]
        if base == target:
            return [_interval(spec)]
        rest = _inheritance_path(ast, base, target, seen)
        if rest is not None:
            return [_interval(spec)] + rest
    return None


def audit_binding_unresolved(event, ast, diagnostics, binding_audits):
    """Subdivide existing binding FNs using exact callable and AST evidence.

    Unknown/unexplained reasons remain unclear. ClosedScopeJ fallback by itself
    is not proof of inheritance: declaration owner and callable owner must
    differ and the callable owner must explicitly declare inheritance.
    """
    relevant = [d for d in diagnostics
                if d.get("kind") in ("state_binding_unresolved", "state_binding_excluded")
                and d.get("name") == event["name"]
                and _overlap([d["start"], d["end"]], event["span"])
                and str(d.get("callable", "")).rsplit(":", 1)[-1] == str(event.get("function_start"))]
    details = []
    declaration = _exact_declaration(event, ast)
    for d in relevant:
        audit = (binding_audits or {}).get(d.get("callable"), {})
        reason, subtype, verdict = d.get("reason"), d.get("reason"), "unclear"
        evidence = {"diagnostic": d, "reference_declaration": event.get("declaration")}
        exact_identifiers = [n for n in ast.nodes if n.type == "identifier"
                             and _interval(n) == [d.get("start"), d.get("end")]
                             and ast.text(n) == event["name"]]
        exact_context = len(exact_identifiers) == 1 and _ancestor(exact_identifiers[0], CALLABLES)
        if (declaration is None or not exact_context or
                exact_context.start_byte != event.get("function_start")):
            details.append(dict(reason=reason, subtype="binding_diagnostic_identity_unconfirmed",
                                verdict="unclear", evidence=evidence))
            continue
        evidence["AST_state_declaration"] = _interval(declaration)
        if reason == "state_name_missing" and audit.get("scope_fallback"):
            callables = [n for n in ast.nodes if n.type in CALLABLES
                         and n.start_byte == event.get("function_start")]
            current = _ancestor(callables[0], CONTAINERS) if len(callables) == 1 else None
            owner = _ancestor(declaration, CONTAINERS) if declaration is not None else None
            inheritance = (_inheritance_path(ast, current, owner)
                           if current is not None and owner is not None and current != owner else None)
            if inheritance:
                subtype = "closed_scope_fallback_inherited_state_missing"
                verdict = "v2_scope_limit"
                evidence.update(scope_fallback=audit["scope_fallback"],
                                callable_owner=_interval(current), declaration_owner=_interval(owner),
                                inheritance_spans=inheritance,
                                scope_reference="Prompt 3 StateBinder conservative ClosedScopeJ fallback: current contract only")
        elif reason in ("state_name_ambiguous", "callable_local_shadows_state",
                        "qualified_namespace_excluded", "contract_qualification_excluded"):
            verdict = "v2_scope_limit"
            evidence["scope_reference"] = "PROMPTS.md section 3.3: unresolved/ambiguous or shadowed occurrences are skipped"
        details.append(dict(reason=reason, subtype=subtype, verdict=verdict, evidence=evidence))
    return details
