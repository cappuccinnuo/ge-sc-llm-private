"""Prompt 8C C: read-only structure audit of frozen model inputs.

No labels, tokens, nodes or model parameters are changed. Modifier identities
come from exact AST anchors and a closed same-source binding. A missing
invocation node is not counted as an isolated node.
"""
import argparse
import copy
import csv
import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path

import dgl
import networkx as nx
from sco_models import graph_utils as gu
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.frontend import FUNCTION_TYPES, text, walk
from scripts.DFG.models import Unsupported
from scripts.DFG.projection import Projector
from scripts.DFG.state.stage_j.binding import ClosedScopeJ
from ..model_input import edge_data, materialize
from ..projection_view import ProjectionView


PROFILES = ("G0", "G1R", "G2R", "G3R", "G3")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_ref(ref):
    path = Path(ref["path"])
    if sha256(path) != ref["sha256"]:
        raise ValueError("Input SHA mismatch: " + str(path))
    return path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def write_json(path, value):
    with Path(path).open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_csv(path, rows):
    if not rows:
        return
    with Path(path).open("x", encoding="utf8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list))
                             else v for k, v in row.items()})


def task_manifest(plan, task_id, fold=0):
    ref = plan["tasks"][task_id]["prepared"][str(fold) + "/1"]
    return read_json(checked_ref(ref))


def canonical_counts(data, node_types):
    """Every registered canonical participates, including globally empty ones."""
    rows = []
    for typ in sorted(node_types):
        incoming = [c for c in data if c[2] == typ]
        rows.append({"node_type": typ, "canonical_count": len(incoming),
                     "nonempty_canonical_count": sum(int(len(data[c][0]) > 0) for c in incoming),
                     "empty_canonical_count": sum(int(len(data[c][0]) == 0) for c in incoming),
                     "incoming_edges": sum(len(data[c][0]) for c in incoming),
                     "canonical_relations": [list(c) for c in sorted(incoming)]})
    return rows


def model_structure(graph, profile):
    """Materialize exactly the production relation directions, retaining IDs."""
    working = gu.add_hetero_ids(copy.deepcopy(graph))
    data = materialize(edge_data(working), profile)
    by_type = {}
    for node, attrs in working.nodes(data=True):
        by_type.setdefault(attrs["node_type"], []).append(node)
    result = nx.DiGraph()
    result.add_nodes_from(graph.nodes())
    for (src, _, dst), (ss, tt) in data.items():
        result.add_edges_from((by_type[src][int(s)], by_type[dst][int(t)])
                              for s, t in zip(ss.tolist(), tt.tolist()))
    return data, result


def path_evidence(graph, source, target):
    if source is None or target is None:
        return {"applicable": False, "direct": None, "two_hop": None, "intermediates": []}
    if source not in graph or target not in graph:
        raise ValueError("Path endpoint missing from actual graph")
    middle = sorted(set(graph.successors(source)).intersection(graph.predecessors(target)), key=str)
    return {"applicable": True, "direct": graph.has_edge(source, target),
            "two_hop": bool(middle), "intermediates": middle}


def mapped_node(view, projector, node):
    if node is None:
        return None
    key = view.mapping.get((node.start_byte, node.end_byte, node.type))
    return projector.by_ast.get(view.compat_ids.get(key))


def invocation_identity(view, projector, invocation):
    callable_node = invocation.parent
    while callable_node is not None and callable_node.type not in FUNCTION_TYPES:
        callable_node = callable_node.parent
    names = [x for x in invocation.named_children if x.type == "identifier"]
    name = text(view.source, names[0]) if names else ""
    result = {"source_file": view.file, "source_sha256": view.sha256,
              "raw_start_byte": invocation.start_byte, "raw_end_byte": invocation.end_byte,
              "raw_start_line": invocation.start_point[0] + 1,
              "raw_end_line": invocation.end_point[0] + 1,
              "name": name, "text": text(view.source, invocation),
              "invocation_node_id": mapped_node(view, projector, invocation),
              "callable_node_id": mapped_node(view, projector, callable_node),
              "definition_node_id": None, "binding": "unresolved", "binding_reason": ""}
    if callable_node is None or not name:
        result["binding_reason"] = "No unique bare name or enclosing callable"
        return result
    try:
        scope = ClosedScopeJ(view, callable_node)
        members = scope.members.get(name, [])
        definitions = [n for n in members if n.type == "modifier_definition"]
        if len(members) == len(definitions) == 1:
            definition = definitions[0]
            result.update(binding="resolved_modifier",
                          definition_node_id=mapped_node(view, projector, definition),
                          definition_raw_span=[definition.start_byte, definition.end_byte],
                          binding_reason="One modifier declaration in closed same-source hierarchy")
        elif name in [text(view.source, n.child_by_field_name("name")) for n in scope.chain
                      if n.child_by_field_name("name") is not None]:
            result.update(binding="base_constructor_syntax",
                          binding_reason="modifier_invocation grammar names a same-source contract constructor")
        else:
            result["binding_reason"] = "Modifier declaration absent or ambiguous: {} members".format(len(members))
    except Unsupported as error:
        result["binding_reason"] = str(error)
    return result


def modifier_inventory(graph, sources):
    records, failures = [], []
    for file in sorted(sources):
        ref = sources[file]
        try:
            view = ProjectionView(checked_ref(ref).read_text(encoding="utf8"), file)
            projector = Projector(graph, view)
            for node in walk(view.tree.root_node):
                if node.type == "modifier_invocation":
                    records.append(invocation_identity(view, projector, node))
        except Unsupported as error:
            failures.append({"source_file": file, "source_sha256": ref["sha256"],
                             "reason": str(error)})
    return records, failures


def audit_profile(graph, profile, invocations):
    data, messages = model_structure(graph, profile)
    records = []
    for item in invocations:
        row = copy.deepcopy(item)
        call, definition, enclosing = (item[k] for k in
                                      ("invocation_node_id", "definition_node_id", "callable_node_id"))
        row.update(profile=profile,
                   nx_in_degree=None if call is None else graph.in_degree(call),
                   nx_out_degree=None if call is None else graph.out_degree(call),
                   model_in_degree=None if call is None else messages.in_degree(call),
                   model_out_degree=None if call is None else messages.out_degree(call),
                   invocation_to_definition_nx=path_evidence(graph, call, definition),
                   invocation_to_definition_model=path_evidence(messages, call, definition),
                   enclosing_callable_to_definition_nx=path_evidence(graph, enclosing, definition),
                   enclosing_callable_to_definition_model=path_evidence(messages, enclosing, definition))
        records.append(row)
    originals = [n for n, d in graph.nodes(data=True) if d["node_type"] != "env_source"]
    nx_isolated = [n for n in originals if graph.degree(n) == 0]
    model_isolated = [n for n in originals if messages.degree(n) == 0]
    return {
        "profile": profile, "nodes": len(graph), "original_nodes": len(originals),
        "edges": graph.number_of_edges(), "model_unique_endpoint_edges": messages.number_of_edges(),
        "node_types": sorted({d["node_type"] for _, d in graph.nodes(data=True)}),
        "schema_counts": canonical_counts(data, {d["node_type"] for _, d in graph.nodes(data=True)}),
        "isolated_original_nx_nodes": nx_isolated, "isolated_original_model_nodes": model_isolated,
        "isolated_original_nx_fraction": len(nx_isolated) / float(len(originals)),
        "isolated_original_model_fraction": len(model_isolated) / float(len(originals)),
        "invocation_records": records,
    }


def dgl_reducer_evidence():
    from dgl.heterograph import reduce_dict_data
    source = inspect.getsource(reduce_dict_data)
    file = inspect.getsourcefile(reduce_dict_data)
    if dgl.__version__ != "0.6.1":
        raise ValueError("This audit is bound to installed DGL 0.6.1")
    if "redfn(F.stack(flist, 0), 0)" not in source:
        raise AssertionError("Installed reduction does not match expected stack/reduce")
    return {"dgl_version": dgl.__version__, "file": file, "file_sha256": sha256(file),
            "function_source_sha256": hashlib.sha256(source.encode("utf8")).hexdigest(),
            "source": source,
            "interpretation": "Frames sharing field t are stacked then mean; no support mask. "
                              "Registered empty canonicals contribute a zero t frame, checked numerically in E."}


def run_structure(plan_path, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=False, exist_ok=False)
    plan = read_json(plan_path)
    results, csv_rows = {}, []
    for task_id, entry in plan["tasks"].items():
        if entry["record"]["task"] != "node":
            continue
        manifest = task_manifest(plan, task_id)
        base = read_graph(checked_ref(manifest["profiles"]["G0"]["graph"]))
        invocations, failures = modifier_inventory(base, entry["record"]["sources"])
        item = {"task_id": task_id, "syntax_invocations": len(invocations),
                "binding_counts": dict(Counter(x["binding"] for x in invocations)),
                "independent_invocation_nodes": sum(x["invocation_node_id"] is not None for x in invocations),
                "missing_invocation_nodes": sum(x["invocation_node_id"] is None for x in invocations),
                "source_projection_failures": failures, "profiles": {}}
        for profile in PROFILES:
            ref = manifest["profiles"][profile]["graph"]
            graph = base if profile == "G0" else read_graph(checked_ref(ref))
            result = audit_profile(graph, profile, invocations)
            result["graph"] = ref
            item["profiles"][profile] = result
            for row in result["schema_counts"]:
                csv_rows.append(dict(task_id=task_id, profile=profile, **row))
        results[task_id] = item
    result = {"version": "prompt8c-structure-v1",
              "plan": {"path": str(Path(plan_path).resolve()), "sha256": sha256(plan_path)},
              "tasks": results, "dgl_reduce_dict_data": dgl_reducer_evidence(),
              "limitations": [
                  "Missing AST invocation nodes have null degrees; they are not isolated existing nodes.",
                  "A two-hop path is structural reachability, not proof of modifier execution semantics.",
                  "Enclosing callable paths are additional context, never substituted for missing invocation nodes.",
                  "Same-source unique bindings only; imported/ambiguous targets remain unresolved."]}
    write_json(output_dir / "structure.json", result)
    write_csv(output_dir / "incoming_canonical_counts.csv", csv_rows)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run_structure(args.plan, args.output)
    print(json.dumps({t: {k: v for k, v in x.items() if k != "profiles"}
                      for t, x in result["tasks"].items()}, indent=2))
