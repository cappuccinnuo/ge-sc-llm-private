"""NS-P0 section 5 read-only reconnaissance of frozen CFG and modifier APIs.

This module computes audit counts, not graph features or a new CFG algorithm.
No graphs, labels, frozen artifacts, or model parameters are modified.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.frontend import FUNCTION_TYPES, SourceView, span, text, walk
from scripts.DFG.models import Unsupported
from scripts.DFG.semantic_cfg import CFGBuilder
from scripts.DFG.projection import Projector
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.l1_cfg import V2CFGBuilder
from scripts.DFG.state.stage_k.profile import SupportedSourceView
from scripts.DFG.state.stage_j.binding import ClosedScopeJ
from scripts.DFG.state.stage_j.modifiers import prefix_modifier

CFG_RELATIONS = frozenset(("next_line", "first_next_line", "pos_next",
                          "neg_next", "end_if", "end_loop", "post_line"))
REFERENCES = (
    "scripts/DFG/semantic_cfg.py", "scripts/DFG/dfg_v2/l1_cfg.py",
    "scripts/DFG/dfg_v2/l1.py", "scripts/DFG/state/stage_j/analyzer.py",
    "scripts/DFG/state/stage_j/modifiers.py", "scripts/DFG/state/stage_j/binding.py",
    "scripts/DFG/state/stage_f/binding.py", "scripts/DFG/frontend.py",
    "scripts/DFG/state/stage_k/profile.py", "scripts/DFG/projection.py",
    "scripts/DFG/dfg_v2/projection_view.py", "scripts/DFG/call_binding.py",
)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _checked(ref):
    path = Path(ref["path"])
    if _sha(path) != ref["sha256"]:
        raise ValueError("Frozen input SHA differs: " + str(path))
    return path


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def _owner(node):
    while node is not None:
        if node.type in FUNCTION_TYPES or node.type == "modifier_definition":
            return node
        node = node.parent
    return None


def _count_ir(ir, view, projector):
    if ir.entry not in ir.blocks:
        raise AssertionError("CFG has no registered entry")
    if any(s not in ir.blocks for b in ir.blocks.values() for s in b.successors):
        raise AssertionError("CFG has an unregistered successor")
    visited, pending = set(), [ir.entry]
    while pending:
        ident = pending.pop()
        if ident in visited:
            continue
        visited.add(ident)
        pending.extend(ir.blocks[ident].successors)
    anchors = {e.anchor for b in ir.blocks.values() for e in b.events}
    projected, missing, missing_roles = {}, Counter(), Counter()
    for anchor in anchors:
        try:
            key = view.compat_key(anchor)
            identifier = projector.by_ast.get(view.compat_ids[key])
            if identifier is None:
                raise Unsupported("Semantic anchor has no existing HCG node")
            projected[anchor] = identifier
        except Unsupported as exc:
            missing[str(exc)] += 1
            missing_roles[anchor.role] += 1
    entries = [e.anchor for e in ir.blocks[ir.entry].events]
    return {
        "blocks": len(ir.blocks),
        "successor_edges": sum(len(b.successors) for b in ir.blocks.values()),
        "reachable_blocks": len(visited),
        "unreachable_blocks": len(ir.blocks) - len(visited),
        "eventless_blocks": sum(not b.events for b in ir.blocks.values()),
        "unique_event_anchors": len(anchors),
        "projected_event_anchors": len(projected),
        "unprojected_event_anchors": len(anchors) - len(projected),
        "missing_projection_reasons": dict(missing),
        "missing_projection_roles": dict(missing_roles),
        "entry_projected": bool(entries) and all(e in projected for e in entries),
        "fully_projected_event_anchors": len(anchors) == len(projected),
        "projected_nodes": sorted(set(projected.values()), key=str),
    }


def _file(graph, file, source, metadata):
    view = ProjectionView(source, file)
    projector = Projector(graph, view)
    raw_functions = [n for n in walk(view.tree.root_node)
                     if n.type in FUNCTION_TYPES]
    functions = [n for n in raw_functions if n.child_by_field_name("body") is not None]
    modifiers = [n for n in walk(view.tree.root_node) if n.type == "modifier_definition"]
    ordinary = {}
    for key, ast_id in view.compat_ids.items():
        if ast_id in projector.by_ast:
            ordinary[projector.by_ast[ast_id]] = view.compat_nodes[key]
    ownership = {}
    for nid, node in ordinary.items():
        fn = _owner(node)
        if fn is not None:
            ownership[nid] = fn.start_byte
    legacy, extended, legacy_error, extended_error = None, None, None, None
    try:
        legacy = SourceView(source, file)
    except Unsupported as exc:
        legacy_error = str(exc)
    try:
        extended = SupportedSourceView(source, file, metadata)
    except Unsupported as exc:
        extended_error = str(exc)
    result = {
        "file": file, "source_sha256": hashlib.sha256(source.encode("utf8")).hexdigest(),
        "callable_declarations": len(raw_functions),
        "functions_with_body": len(functions),
        "bodyless_callable_declarations": len(raw_functions) - len(functions),
        "modifier_definitions_ast": len(modifiers),
        "modifier_definition_hcg_nodes": sum(
            d["node_type"] == "modifier_definition" for _, d in graph.nodes(data=True)),
        "projection": dict(projector.stats),
        "functions": [], "modifier_calls": [],
        "legacy_source_fallback": legacy_error, "v2_source_fallback": extended_error,
    }
    for fn in functions:
        row = {"start": fn.start_byte, "end": fn.end_byte, "kind": fn.type,
               "name": text(source, fn.child_by_field_name("name"))
               if fn.child_by_field_name("name") is not None else fn.type}
        successes = {}
        for name, frontend, builder_cls, error in (
                ("legacy", legacy, CFGBuilder, legacy_error),
                ("v2", extended, V2CFGBuilder, extended_error)):
            if frontend is None:
                row[name] = {"supported": False, "reason": error, "stage": "source_view"}
                continue
            try:
                builder = builder_cls(frontend, fn)
                ir = builder.build()
                counts = _count_ir(ir, frontend, projector)
                row[name] = dict(counts, supported=True)
                successes[name] = counts
            except Unsupported as exc:
                row[name] = {"supported": False, "reason": str(exc), "stage": "function"}
        route = "legacy" if "legacy" in successes else ("v2" if "v2" in successes else None)
        row["existing_l1_route"] = route
        result["functions"].append(row)
    # Binding classification is distinct from executable-modifier CFG support.
    # ClosedScopeJ reads lexical ancestors; never match a name globally.
    for fn in raw_functions:
        calls = [n for n in fn.named_children if n.type == "modifier_invocation"]
        if not calls:
            continue
        scope, scope_error = None, None
        try:
            scope = ClosedScopeJ(view, fn)
        except Unsupported as exc:
            scope_error = str(exc)
        for call in calls:
            children = [n for n in call.named_children if "comment" not in n.type]
            row = {"function_start": fn.start_byte, "call_start": call.start_byte,
                   "call_end": call.end_byte, "text": text(source, call),
                   "resolved": False, "inherited": False}
            try:
                if scope is None:
                    raise Unsupported(scope_error)
                if not children or children[0].type != "identifier":
                    raise Unsupported("Non-bare modifier invocation not bound")
                name = text(source, children[0])
                declarations = scope.require_unambiguous(name)
                row.update(name=name, visible_declaration_kinds=[d.type for d in declarations])
                if len(declarations) != 1 or declarations[0].type != "modifier_definition":
                    raise Unsupported("Name is not one visible modifier declaration")
                declaration = declarations[0]
                row.update(resolved=True, name=name, declaration_start=declaration.start_byte,
                           declaration_end=declaration.end_byte,
                           inherited=scope.owner[declaration.start_byte].start_byte
                           != scope.contract.start_byte,
                           hierarchy_depth=len(scope.chain))
            except Unsupported as exc:
                row["reason"] = str(exc)
            result["modifier_calls"].append(row)
        prefix_row = {"function_start": fn.start_byte}
        try:
            if extended is None:
                raise Unsupported(extended_error)
            prefix, evidence = prefix_modifier(extended, fn, ClosedScopeJ(extended, fn))
            prefix_row.update(supported=True, prefix_statements=len(prefix), evidence=evidence)
        except Unsupported as exc:
            prefix_row.update(supported=False, reason=str(exc))
        result.setdefault("modifier_execution", []).append(prefix_row)
    cfg_nodes, edges, internal, cross, unknown = set(), [], 0, 0, 0
    for a, b, d in graph.edges(data=True):
        relation = d.get("edge_type")
        if relation not in CFG_RELATIONS:
            continue
        cfg_nodes.update((a, b))
        edges.append((a, b, relation))
        if a not in ownership or b not in ownership:
            unknown += 1
        elif ownership[a] == ownership[b]:
            internal += 1
        else:
            cross += 1
    callable_nodes = set(ownership)
    result["hcg_cfg"] = {
        "nodes": len(graph), "edges": len(edges), "incident_nodes": len(cfg_nodes),
        "ordinary_nodes_owned_by_callable": len(callable_nodes),
        "callable_owned_nodes_incident_cfg": len(callable_nodes & cfg_nodes),
        "exact_owned_endpoints_same_callable_edges": internal,
        "exact_owned_endpoints_different_callable_edges": cross,
        "edges_with_at_least_one_nonexact_callable_owner": unknown,
        "relations": dict(Counter(r for _, _, r in edges)),
        "all_graph_relations": dict(Counter(d.get("edge_type") for _, _, d in graph.edges(data=True))),
    }
    return result


def _aggregate(rows):
    out = {"files": len(rows)}
    for key in ("functions_with_body", "callable_declarations", "bodyless_callable_declarations",
                "modifier_definitions_ast", "modifier_definition_hcg_nodes"):
        out[key] = sum(r[key] for r in rows)
    functions = [f for r in rows for f in r["functions"]]
    for name in ("legacy", "v2"):
        supported = [f[name] for f in functions if f[name]["supported"]]
        reasons = Counter(f[name]["reason"] for f in functions if not f[name]["supported"])
        out[name] = dict(supported_functions=len(supported),
                         fallback_functions=len(functions)-len(supported),
                         fallback_reasons=dict(reasons))
    chosen = [f[f["existing_l1_route"]] for f in functions if f["existing_l1_route"]]
    out["legacy_then_v2"] = {
        "supported_functions": len(chosen),
        "fallback_functions": len(functions)-len(chosen),
        "routes": dict(Counter(f["existing_l1_route"] or "fallback" for f in functions)),
        "entry_projected_functions": sum(r["entry_projected"] for r in chosen),
        "all_event_anchors_projected_functions": sum(r["fully_projected_event_anchors"] for r in chosen),
    }
    for key in ("blocks", "successor_edges", "reachable_blocks", "unreachable_blocks",
                "eventless_blocks", "unique_event_anchors", "projected_event_anchors",
                "unprojected_event_anchors"):
        out["legacy_then_v2"][key] = sum(r[key] for r in chosen)
    out["legacy_then_v2"]["unprojected_reasons"] = dict(sum(
        (Counter(r["missing_projection_reasons"]) for r in chosen), Counter()))
    out["legacy_then_v2"]["unprojected_roles"] = dict(sum(
        (Counter(r["missing_projection_roles"]) for r in chosen), Counter()))
    calls = [c for r in rows for c in r["modifier_calls"]]
    executions = [c for r in rows for c in r.get("modifier_execution", [])]
    out["modifiers"] = {
        "invocations": len(calls),
        "resolved": sum(c["resolved"] for c in calls),
        "resolved_direct": sum(c["resolved"] and not c["inherited"] for c in calls),
        "resolved_inherited": sum(c["resolved"] and c["inherited"] for c in calls),
        "unresolved": sum(not c["resolved"] for c in calls),
        "unresolved_reasons": dict(Counter(c["reason"] for c in calls if not c["resolved"])),
        "invoking_functions": len(executions),
        "supported_prefix_function_executions": sum(c["supported"] for c in executions),
        "unsupported_prefix_function_executions": sum(not c["supported"] for c in executions),
        "unsupported_prefix_reasons": dict(Counter(c["reason"] for c in executions if not c["supported"])),
    }
    out["hcg_cfg"] = {}
    for key in rows[0]["hcg_cfg"]:
        if key.endswith("relations"):
            out["hcg_cfg"][key] = dict(sum((Counter(r["hcg_cfg"][key]) for r in rows), Counter()))
        else:
            out["hcg_cfg"][key] = sum(r["hcg_cfg"][key] for r in rows)
    return out


def run(repo_root=None):
    root = Path(repo_root or ROOT).resolve()
    plan_path = root / "scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/plan.json"
    plan = _json(plan_path)
    tasks, file_records = {}, {}
    for tid, task in plan["tasks"].items():
        print("CFG reconnaissance: " + tid, file=sys.stderr, flush=True)
        record = task["original_record"]
        graph = read_graph(_checked(record["original_graph"]))
        groups = defaultdict(list)
        for nid, data in graph.nodes(data=True):
            groups[data["source_file"]].append(nid)
        rows = []
        for index, file in enumerate(sorted(groups)):
            reference = record["sources"][file]
            source = _checked(reference).read_text(encoding="utf8")
            subgraph = graph.subgraph(groups[file])
            row = _file(subgraph, file, source, reference.get("metadata"))
            rows.append(row)
            if (index + 1) % 20 == 0:
                print("  {}/{} files".format(index+1, len(groups)), file=sys.stderr, flush=True)
        tasks[tid] = _aggregate(rows)
        file_records[tid] = rows
    refs = []
    for relative in REFERENCES:
        path = root / relative
        lines = path.read_text(encoding="utf8").splitlines()
        refs.append({"path": relative, "sha256": _sha(path),
                     "definitions": [{"line": i+1, "text": line.strip()}
                        for i, line in enumerate(lines)
                        if line.startswith(("class ", "def "))
                        or line.startswith(("    def build", "    def statement", "    def __init__"))]})
    return {
        "scope": "NS-P0 section 5; original source and original fixed HCG; CPU, no training",
        "plan": {"path": str(plan_path), "sha256": _sha(plan_path)},
        "code_references": refs, "tasks": tasks, "file_records": file_records,
        "interpretation": [
            "Counts measure CFG construction, not RD completion or complete Solidity semantics.",
            "FUNCTION_TYPES excludes modifier definitions; modifier definitions/invocations are reported separately.",
            "Legacy-then-v2 chooses the existing L1 order; V2-only coverage is separately shown.",
            "Projection is exact AST/compat identity; eventless CFG blocks intentionally have no HCG node.",
            "Original AST label is read only by frozen Projector as structural identity, not used as a prediction target.",
            "Modifier declaration binding is weaker than supported prefix execution; both counts are separate.",
            "Invocation totals count grammar modifier_invocation nodes in callable headers; unresolved nodes may include base-constructor syntax and must not automatically mean a missing security modifier.",
            "HCG CFG incidence is topology coverage, not validated control-flow semantics. Cross-function and synthetic endpoints need exclusion/recovery before any fallback traversal.",
            "Primary candidate: existing semantic CFG, retain auxiliary blocks in analysis and project only exact event anchors. On unsupported functions report missing facts; do not interpret missing guard as no guard.",
            "Successor sets lack branch polarity and exceptional exits. Dominance of an if/while condition alone does not prove branch acceptance or access-control protection.",
            "require/assert normal-continuation dominance is useful only after builtin binding and accepting-branch semantics are verified. External calls are not full interprocedural/exceptions summaries.",
            "No new dominator or modifier analysis is implemented; unresolved imports, overloads/overrides, complex modifiers retain explicit unsupported status.",
            "Anonymous view requires original-SHA metadata not be transferred to rewritten source; 8G semantic parity is separate evidence, not compiler proof.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(ROOT))
    args = parser.parse_args()
    print(json.dumps(run(args.repo_root), ensure_ascii=False, indent=2))
