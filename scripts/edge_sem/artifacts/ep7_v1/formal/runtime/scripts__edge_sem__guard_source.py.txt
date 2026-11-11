"""Read-only provenance for the frozen modifier guard records.

Parsing sequence copied from scripts/node_sem/facts_guards.py:333-383.
Source SHA256: bb2bad3e65aab2e35a88955b7cc33d53ec324471156cca2f6987b377d24fbda5
Frozen _scope, _bindings, _lexical, _require and _guard remain authoritative.
No graph edges, analyzer audit counters or modifier-cache entries are written.
"""
from collections import Counter
from scripts.node_sem.facts_guards import children, unwrap, walk

FROZEN_SOURCE_SHA256 = "bb2bad3e65aab2e35a88955b7cc33d53ec324471156cca2f6987b377d24fbda5"


def public_record(record):
    return {k: v for k, v in record.items() if not k.startswith("_")}


def inspect_modifier_guards(analyzer, function):
    """Return sources plus unresolved/audit counters without changing cached records."""
    result, unresolved, audit = [], Counter(), Counter()
    sem = analyzer.sem
    invocations = [n for n in children(function) if n.type == "modifier_invocation"
        and not (sem.text(n) == "constant" and not sem.members(function).get("constant"))]
    if not invocations:
        return result, unresolved, audit
    scope = analyzer._scope(function)
    for invocation in invocations:
        cs = children(invocation)
        if scope is None or not cs or cs[0].type != "identifier":
            unresolved["modifier_binding_unresolved"] += 1
            audit["modifier_unresolved"] += 1
            continue
        ds = scope.declarations(sem.text(cs[0]))
        if len(ds) != 1 or ds[0].type != "modifier_definition":
            unresolved["modifier_binding_unresolved"] += 1
            audit["modifier_unresolved"] += 1
            continue
        modifier = ds[0]
        body = modifier.child_by_field_name("body")
        bindings = analyzer._bindings(modifier, invocation)
        holes = [] if body is None else [n for n in walk(body)
            if n.type == "expression_statement" and unwrap(n).type == "identifier"
            and sem.text(unwrap(n)) == "_"]
        if not holes or bindings is None:
            unresolved["modifier_placeholder_or_arguments_unresolved"] += 1
            audit["modifier_unresolved"] += 1
            continue
        if len(holes) != 1:
            unresolved["modifier_multiple_placeholders"] += 1
            audit["modifier_unresolved"] += 1
            continue
        audit["modifier_resolved"] += 1
        if scope.owner.get(modifier.start_byte) != scope.contract:
            audit["modifier_inherited"] += 1
        guards, _ = analyzer._lexical(holes[0], modifier, include_internal=False)
        for guard in guards:
            if guard["rule"] not in {"1", "2", "3"}:
                continue
            anchor = guard["_anchor"]
            condition = (anchor.child_by_field_name("condition") if anchor.type == "if_statement"
                         else analyzer._require(anchor))
            rule = "5p" if guard["rule"] == "2" else "5"
            record = analyzer._guard(rule, "modifier", guard["polarity"], condition,
                                     invocation, bindings)
            result.append(dict(record=public_record(record), invocation=invocation,
                               inner_anchor=anchor))
    return result, unresolved, audit


def modifier_guard_sources(analyzer, function):
    """Required EP0b/EP3 list API; diagnostics are available via inspect_modifier_guards."""
    return inspect_modifier_guards(analyzer, function)[0]
