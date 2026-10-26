"""Read-only alias identity audit for Prompt 6d.2.

Consumes the existing statement alignment and F2 binding audit. No StateBinder
or DDG builder is executed, and no source/graph/classification is changed.
This audit establishes alias identities and root cardinality, not dynamic
points-to correctness. Slither convention acceptance requires separate probes.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from .slither_align import SourceFacts
from .state_binding import chain_root

VERSION = "dfg-v2-slither-alias-audit-v1"
CALLABLES = frozenset(("function_definition", "constructor_definition",
                      "fallback_receive_definition", "modifier_definition"))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _ref(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": _sha(path)}


def _checked(ref):
    if _sha(ref["path"]) != ref["sha256"]:
        raise ValueError("input digest mismatch: " + ref["path"])
    return Path(ref["path"])


def _node(ast, start, end, kind=None):
    nodes = [n for n in ast.nodes if n.start_byte == start and n.end_byte == end
             and (kind is None or n.type == kind)]
    if len(nodes) != 1:
        raise ValueError("AST identity is not unique: {}:{} {}".format(start, end, kind))
    return nodes[0]


def _ancestor(node, kinds):
    while node is not None and node.type not in kinds:
        node = node.parent
    return node


def _details(ast, node):
    return {"start": node.start_byte, "end": node.end_byte,
            "role": node.type, "text": ast.text(node)}


def _state(ast, event):
    start = event["declaration"][0]
    nodes = [n for n in ast.nodes if n.type == "state_variable_declaration"
             and n.start_byte == start
             and n.child_by_field_name("name") is not None
             and ast.text(n.child_by_field_name("name")) == event["name"]]
    if len(nodes) != 1:
        raise ValueError("state declaration identity mismatch")
    return nodes[0]


def _local_declarations(ast, context, name):
    return [n for n in ast.nodes
            if n.type in ("variable_declaration", "parameter")
            and context.start_byte <= n.start_byte < n.end_byte <= context.end_byte
            and n.child_by_field_name("name") is not None
            and ast.text(n.child_by_field_name("name")) == name]


def audit_alias(difference, ast, file_audit):
    if difference["layer"] != "L2" or difference["category"] != "alias":
        raise ValueError("expected sealed L2 alias event")
    event = difference["primary"]
    identity = difference["file"] + ":" + str(event["function_start"])
    binding = file_audit["binding_audits"].get(identity)
    if binding is None or binding["callable"] != identity:
        raise ValueError("missing exact callable binding audit")
    contexts = [n for n in ast.nodes if n.type in CALLABLES
                and n.start_byte == event["function_start"]]
    if len(contexts) != 1:
        raise ValueError("missing exact callable AST")
    context, state = contexts[0], _state(ast, event)
    row = {k: difference[k] for k in
           ("difference_id", "task", "file", "source_sha256", "direction",
            "name", "kind", "line", "source_excerpt")}
    row.update({"callable": identity, "state": _details(ast, state),
                "semantic_verdict": "pending_probe", "subtype": "unresolved",
                "scope_fallback": binding["scope_fallback"],
                "occurrences": [], "declaration_checks": []})
    if difference["direction"] == "FP":
        if not event["evidence"] or any(not e.get("via_alias") for e in event["evidence"]):
            raise ValueError("alias FP contains non-alias or empty evidence")
        for evidence in event["evidence"]:
            if evidence["file"] != difference["file"] or evidence["callable"] != identity:
                raise ValueError("occurrence callable mismatch")
            occurrence = evidence["occurrence"]
            node = _node(ast, occurrence["start"], occurrence["end"], occurrence["role"])
            root = chain_root(node)
            if root is None:
                raise ValueError("alias access has no exact bare root")
            alias = ast.text(root)
            declarations = _local_declarations(ast, context, alias)
            if len(declarations) != 1:
                raise ValueError("sealed resolved alias has non-unique declaration")
            declaration = declarations[0]
            sources = [x for x in binding["aliases"] if x["name"] == alias]
            if not sources or any(x["local_start"] != declaration.start_byte or
                                  x["local_end"] != declaration.end_byte for x in sources):
                raise ValueError("sealed alias local declaration mismatch")
            roots = sorted(set((x["state_start"], x["state_end"], x["state_name"])
                               for x in sources))
            if (state.start_byte, state.end_byte, event["name"]) not in roots:
                raise ValueError("event state absent from sealed root set")
            for source in sources:
                rhs = _node(ast, source["source_start"], source["source_end"])
                rhs_root = chain_root(rhs)
                if rhs_root is None or ast.text(rhs_root) != source["state_name"]:
                    raise ValueError("initializer/rebinding root differs from sealed source")
                # Exact declaration identity is retained from the sealed binder;
                # this audit additionally proves the source AST spelling/root.
            row["occurrences"].append({
                "access": _details(ast, node), "root": _details(ast, root),
                "local_declaration": _details(ast, declaration),
                "state_root_set": [list(x) for x in roots],
                "binding_sources": sources,
            })
        if all(len(x["state_root_set"]) == 1 for x in row["occurrences"]):
            row["subtype"] = ("single_root_state_read_missing" if difference["kind"] == "READ"
                              else "single_root_state_write_missing")
        else:
            row["subtype"] = "multiple_root_union_requires_individual_review"
        row["convention_acceptance_requires_direct_probe"] = True
    elif difference["direction"] == "FN":
        # Only the precise, recorded ambiguous-local case is accepted here.
        nodes = [n for n in ast.nodes if n.type in ("assignment_expression",
                   "augmented_assignment_expression") and
                 n.start_byte == event["span"][0] and n.end_byte == event["span"][1]]
        if len(nodes) != 1:
            return row
        root = chain_root(nodes[0].child_by_field_name("left"))
        if root is None:
            return row
        alias = ast.text(root)
        declarations = _local_declarations(ast, context, alias)
        diagnostics = [x for x in binding["diagnostics"]
                       if x.get("reason") == "ambiguous_local_declaration"
                       and x.get("name") == alias and x.get("callable") == identity]
        if len(declarations) <= 1 or len(diagnostics) != 1:
            return row
        if diagnostics[0]["declaration_count"] != len(declarations):
            raise ValueError("ambiguous alias declaration count mismatch")
        if any(x["name"] == alias for x in binding["aliases"]):
            raise ValueError("ambiguous alias nevertheless resolved")
        target_declarations = []
        for declaration in declarations:
            parent = declaration.parent
            rhs = parent.child_by_field_name("value") if parent is not None else None
            rhs_root = chain_root(rhs)
            location = declaration.child_by_field_name("location")
            if rhs_root is None or ast.text(rhs_root) != event["name"] or location is None:
                return row
            scope = _ancestor(declaration.parent, frozenset(("block_statement",
                              "function_body", "for_statement")))
            in_scope = (scope is not None and scope.start_byte <= root.start_byte
                        and root.end_byte <= scope.end_byte
                        and declaration.start_byte < root.start_byte)
            if in_scope:
                target_declarations.append((declaration, ast.text(location)))
            row["declaration_checks"].append({
                "declaration": _details(ast, declaration),
                "lexical_scope": _details(ast, scope) if scope is not None else None,
                "initializer": _details(ast, rhs),
                "root_spelling": ast.text(rhs_root),
                "location": ast.text(location),
                "contains_target_write": in_scope,
            })
        if len(target_declarations) != 1 or target_declarations[0][1] != "storage":
            return row
        row.update({"subtype": "ambiguous_callable_local_alias",
                    "semantic_verdict": "v2_scope_limit",
                    "diagnostic": diagnostics[0],
                    "policy": "callable-wide unique alias declaration required",
                    "not_language_ambiguity": True,
                    "impact": {
                        "layer": "L2 occurrence aggregation; no reaching definitions",
                        "missing_operation": "WRITES_STATE evidence for this access",
                        "l1_fact_generation_depends_on_l2": False,
                        "l2_write_kill_or_propagation": False,
                        "no_claim_about_unobserved_execution": True,
                    }})
    else:
        raise ValueError("invalid difference direction")
    return row


def run(alignment, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(str(output))
    alignment = Path(alignment).resolve()
    seal = alignment.with_name("report.seal.json")
    data = json.loads(alignment.read_text(encoding="utf8"))
    if json.loads(seal.read_text(encoding="utf8"))["report_sha256"] != _sha(alignment):
        raise ValueError("alignment seal mismatch")
    inputs = {"alignment": _ref(alignment), "alignment_seal": _ref(seal),
              "store": data["inputs"]["store"]}
    store = json.loads(_checked(inputs["store"]).read_text(encoding="utf8"))
    differences = [d for d in data["differences"]
                   if d["layer"] == "L2" and d["category"] == "alias"]
    ids = [d["difference_id"] for d in differences]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate difference identity")
    audits, sources, rows = {}, {}, []
    for d in differences:
        task = d["task"]
        if task not in audits:
            ref = store["tasks"][task]["graphs"]["F2"]["audit"]
            inputs[task + "_audit"] = ref
            audits[task] = json.loads(_checked(ref).read_text(encoding="utf8"))["layers"]["L2"]["files"]
        ref = {"path": d["source_path"], "sha256": d["source_sha256"]}
        _checked(ref)
        inputs["source:" + d["task"] + ":" + d["file"]] = ref
        if ref["path"] not in sources:
            sources[ref["path"]] = SourceFacts(Path(ref["path"]).read_text(encoding="utf8"))
        rows.append(audit_alias(d, sources[ref["path"]], audits[task][d["file"]]))
    for ref in inputs.values():
        _checked(ref)
    counts = Counter((row["task"], row["direction"], row["kind"], row["subtype"]) for row in rows)
    result = {"version": VERSION, "inputs": inputs, "rows": rows,
              "counts": [{"task": k[0], "direction": k[1], "kind": k[2],
                          "subtype": k[3], "count": v} for k, v in sorted(counts.items())],
              "all_selected_events_audited": len(rows),
              "alias_FP_lexical_occurrences": sum(len(x["occurrences"]) for x in rows),
              "graph_changed": False, "analyzer_executed": False,
              "slither_executed": False, "training_executed": False,
              "note": "Subtypes are evidence descriptions, not modifications to old alignment categories."}
    output.mkdir(parents=True, exist_ok=False)
    path = output / "report.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    (output / "report.seal.json").write_text(json.dumps({
        "version": VERSION, "report_sha256": _sha(path), "inputs": inputs,
        "implementation": _ref(__file__)}, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alignment", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.alignment, args.output)
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
