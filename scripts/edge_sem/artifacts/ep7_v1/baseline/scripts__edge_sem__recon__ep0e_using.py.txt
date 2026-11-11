
"""Resolver-independent using candidate set and EP0d binding comparisons."""
from collections import Counter
from .common import key
from .ep0d_equivalence import compare_file as ordinary_callee_equivalence
from .ep0d_common import anchor
from scripts.node_sem.facts_ast import unwrap
from scripts.edge_sem.call_resolve import receiver_type, _using_resolve


def structural_candidates(sem, call):
    """No receiver inference, directive source filter, labels or resolver call."""
    callee = sem._postfix(unwrap(call.child_by_field_name("function")))
    if callee is None or callee.type != "member_expression":
        return dict(extension_member=False, reason="not_member", declarations=[])
    receiver = unwrap(callee.child_by_field_name("object"))
    binding = sem.resolve_identifier(receiver)
    direct = binding.get("declaration")
    if direct is not None and direct.type == "library_declaration":
        return dict(extension_member=False, reason="direct_library", declarations=[])
    scope = sem.scope(call)
    if scope is None:
        return dict(extension_member=True, reason="scope_unavailable", declarations=[])
    method = sem.text(callee.child_by_field_name("property"))
    argc = len(sem.arguments(call))
    declarations = []
    for contract in scope.chain:
        body = contract.child_by_field_name("body")
        for directive in body.named_children:
            if directive.type != "using_directive":
                continue
            alias = next((n for n in directive.named_children if n.type == "type_alias"), None)
            if alias is None:
                continue
            libraries = [n for n in sem.contracts if n.type == "library_declaration"
                         and sem.text(n.child_by_field_name("name")) == sem.text(alias)]
            if len(libraries) != 1:
                continue
            named = [n for n in libraries[0].child_by_field_name("body").named_children
                     if n.type == "function_definition" and sem.text(n.child_by_field_name("name")) == method]
            matched = [n for n in named if len([p for p in n.named_children if p.type == "parameter"]) == argc+1]
            if len(matched) != 1:
                continue
            fn = matched[0]
            first = next(p for p in fn.named_children if p.type == "parameter")
            source = directive.child_by_field_name("source")
            declarations.append(dict(directive_anchor=anchor(directive),
                source_type=sem._canonical_type(sem.text(source)) if source is not None else None,
                wildcard=(source is not None and source.type == "any_source_type" and sem.text(source) == "*"),
                library_anchor=anchor(libraries[0]), function_anchor=anchor(fn),
                first_parameter_type=sem._canonical_type(sem.text(first.child_by_field_name("type"))),
                named_function_count=len(named)))
    unique = {tuple(r["function_anchor"]) for r in declarations}
    return dict(extension_member=True,
                reason="unique_candidate" if len(unique)==1 else ("ambiguous_candidates" if unique else "no_candidate"),
                declarations=declarations)


def shape(sem, receiver):
    if receiver is None:
        return "other"
    if receiver.type == "parenthesized_expression":
        return "parenthesized"
    if receiver.type == "identifier":
        return "identifier"
    if receiver.type == "array_access":
        base_type = receiver_type(sem, receiver.child_by_field_name("base"))
        if base_type and base_type.startswith("mapping("):
            return "mapping_subscript"
        if base_type and base_type.endswith("]"):
            return "array_subscript"
        return "other"
    if receiver.type == "call_expression":
        return "chained_call"
    if receiver.type == "member_expression":
        base_type = receiver_type(sem, receiver.child_by_field_name("object"))
        structs = [n for n in sem.nodes if n.type=="struct_declaration"
                   and sem.text(n.child_by_field_name("name")) == base_type]
        return "struct_member" if len(structs)==1 else "other"
    return "other"


def unresolved_reason(structural, typ, resolved):
    if resolved["target"] is not None:
        return "resolved_to_other_target"
    if typ is None:
        return "receiver_type_unknown"
    rows = structural["declarations"]
    source_matches = [r for r in rows if r["wildcard"] or r["source_type"] is None or r["source_type"] == typ]
    if not source_matches:
        return "using_source_type_mismatch"
    typed = [r for r in source_matches if r["first_parameter_type"] == typ]
    if not typed:
        return "first_parameter_type_mismatch"
    if any(r["named_function_count"] != 1 for r in typed):
        return "library_method_overload_not_unique"
    return "binding_not_unique_or_scope_unavailable"


def audit_file(sem, previous, resolved):
    prior = {tuple(r["call_anchor"]):r for r in previous}
    calls = [n for n in sem.nodes if n.type=="call_expression"]
    assert set(prior) == {key(n) for n in calls}
    rows, equality, unchanged = [], [], 0
    for call in calls:
        old, new = prior[key(call)], resolved[key(call)]
        if old["status"] == "resolved":
            assert (old["status"],old["kind"],old["target_anchor"]) == (
                new["status"],new["kind"],anchor(new["target"]))
            unchanged += 1
        structural = structural_candidates(sem,call)
        if not structural["extension_member"]:
            continue
        callee = sem._postfix(unwrap(call.child_by_field_name("function")))
        raw_receiver = callee.child_by_field_name("object")
        receiver = unwrap(raw_receiver)
        method = sem.text(callee.child_by_field_name("property"))
        typ = receiver_type(sem,receiver)
        targets = sorted({tuple(r["function_anchor"]) for r in structural["declarations"]})
        expected = list(targets[0]) if len(targets)==1 else None
        matched = expected is not None and new["status"]=="resolved" and anchor(new["target"])==expected
        outside = (new["status"]=="resolved" and new["kind"]=="library"
                   and (expected is None or anchor(new["target"])!=expected))
        rows.append(dict(call_anchor=anchor(call), expression=sem.text(call),
            receiver_anchor=anchor(raw_receiver), receiver_shape=shape(sem,raw_receiver),
            inferred_type=typ, candidate=(expected is not None), expected_target=expected,
            matched=matched, outside_candidate=outside, structural=structural,
            status=new["status"],kind=new["kind"],target_anchor=anchor(new["target"]),
            reason=new["reason"], miss_reason=(None if matched or expected is None
                                              else unresolved_reason(structural,typ,new))))
        # Compare all supported legacy receiver shapes, not just successes.
        legacy_type = sem._canonical_type(sem.root_binding(receiver)["type_name"])
        eligible = (receiver is not None and (receiver.type=="identifier"
                    or (receiver.type=="array_access" and legacy_type.endswith("]"))))
        if not eligible:
            continue
        if receiver.type=="array_access":
            legacy_type=legacy_type[:legacy_type.rfind("[")]
        frozen=sem._using_callable(call,receiver,method)
        adapted=_using_resolve(sem,call,typ,method)
        rule_only=_using_resolve(sem,call,legacy_type,method)
        wildcard=any(r["wildcard"] for r in structural["declarations"])
        equal=key(frozen)==key(adapted)
        equality.append(dict(call_anchor=anchor(call),receiver_anchor=anchor(receiver),
            receiver_type=receiver.type, legacy_type=legacy_type, inferred_type=typ,
            frozen_target=anchor(frozen),adapter_target=anchor(adapted),
            rule_only_target=anchor(rule_only),binding_rules_equal=key(frozen)==key(rule_only),
            equal=equal,approved_wildcard_exception=(not equal and wildcard),
            unexpected_mismatch=(not equal and not wildcard)))
    return dict(candidates=rows, using_equivalence=equality,
                resolved_unchanged=unchanged, prior_call_count=len(calls),
                ordinary_callee_equivalence=ordinary_callee_equivalence(sem,previous))


def summarize(rows, files):
    candidates = [r for r in rows if r["candidate"]]
    shape_counts = {}
    for name in ("identifier","mapping_subscript","array_subscript","parenthesized","chained_call","struct_member","other"):
        group = [r for r in candidates if r["receiver_shape"]==name]
        good = sum(r["matched"] for r in group)
        shape_counts[name]=dict(candidates=len(group),matched=good,recall=good/len(group) if group else None)
    matched=sum(r["matched"] for r in candidates)
    outside=[r for r in rows if r["outside_candidate"]]
    equivalence=[r for f in files for r in f["using_equivalence"]]
    unexpected=[r for r in equivalence if r["unexpected_mismatch"]]
    ratio=matched/len(candidates) if candidates else None
    ambiguous=[r for r in rows if r["structural"]["reason"]=="ambiguous_candidates"]
    return dict(candidate_calls=len(candidates),matched_calls=matched,recall=ratio,
        per_shape=shape_counts, misses_by_reason=dict(Counter(r["miss_reason"] for r in candidates if not r["matched"])),
        ambiguous_structural_candidates=len(ambiguous),outside_candidate_calls=len(outside),
        using_equivalence_count=len(equivalence),using_equivalent=sum(r["equal"] for r in equivalence),
        wildcard_exceptions=sum(r["approved_wildcard_exception"] for r in equivalence),
        unexpected_equivalence_mismatches=len(unexpected),
        prior_resolved_unchanged=sum(r["resolved_unchanged"] for r in files),
        recall_gate_pass=bool(ratio is not None and ratio>=.9),
        no_outside_gate_pass=not outside,
        gate_pass=bool(ratio is not None and ratio>=.9 and not outside and not unexpected and not ambiguous))
