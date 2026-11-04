"""Read-only Prompt 8D A: exact AST scopes and frozen intervention strata."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import re
import numpy as np
from scripts.DFG.frontend import FUNCTION_TYPES, text, walk
from scripts.DFG.projection import Projector, code_equal, decoded
from scripts.DFG.models import Unsupported
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.diagnostics8c import scoring as s
from scripts.DFG.dfg_v2.diagnostics8c.inference import replacement_map, rewrite_code
from scripts.DFG.dfg_v2.diagnostics8c.common import checked_plan
from scripts.labeling_v2.safe_graph import read_graph

VERSION = "prompt8d-readonly-strata-v1"
STRATA = ("a_own_text_renamed", "b_unchanged_in_renamed_injection_function", "c_other")
SYNTHETIC_TYPES = {"end_if": {"if_statement"},
                   "end_loop": {"for_statement", "while_statement", "do_statement"}}

def checked(reference):
    path = Path(reference["path"])
    if s.sha(path) != reference["sha256"]:
        raise ValueError("Input SHA mismatch: " + str(path))
    return path

def enclosing_function(node):
    while node is not None:
        if node.type in FUNCTION_TYPES:
            return node
        node = node.parent
    return None

def classify(own_text_renamed, in_renamed_function):
    if own_text_renamed:
        return STRATA[0]
    if in_renamed_function:
        return STRATA[1]
    return STRATA[2]

def synthetic_owner(attrs, view):
    """Unique exact saved synthetic role/start/code identity; never nearest line."""
    kind = attrs["node_type"]
    label = decoded(attrs.get("label", ""))
    match = re.fullmatch(r"(\d+)_\s*" + kind, label.strip())
    if not match or kind not in SYNTHETIC_TYPES:
        return None, "synthetic_label_not_supported"
    from process_graphs.tree_sitter_codeviews.utils.solidity_nodes import return_if_root
    def saved_start(node):
        return (return_if_root(node).start_point[0] if node.type == "if_statement"
                else node.start_point[0])
    candidates = [node for node in view.compat_nodes.values()
                  if node.type in SYNTHETIC_TYPES[kind]
                  and saved_start(node) == int(match.group(1))
                  and code_equal(attrs.get("code"), view.compat[node.start_byte:node.end_byte].decode("utf8"))]
    if len(candidates) != 1:
        return None, "synthetic_exact_identity_matches_" + str(len(candidates))
    return candidates[0], "synthetic_exact_control_ast_role_start_code"

def scope_inventory(graph, sources):
    rows = []
    for file, reference in sorted(sources.items()):
        source = checked(reference).read_text(encoding="utf8")
        mapping = replacement_map(source)
        file_nodes = [(node, attrs) for node, attrs in graph.nodes(data=True)
                      if attrs["source_file"] == file]
        try:
            view = ProjectionView(source, file)
            projector = Projector(graph, view)
            inverse = {value: key for key, value in projector.by_ast.items()}
            compat_by_id = {value: view.compat_nodes[key] for key, value in view.compat_ids.items()}
        except Unsupported as error:
            view = None
            failure = str(error)
        for node, attrs in file_nodes:
            new_code, edits = rewrite_code(attrs["code"], mapping)
            ast_node, reason = None, ""
            if view is None:
                reason = "source_projection_failed: " + failure
            elif node in inverse:
                ast_node = compat_by_id[inverse[node]]
                reason = "ordinary_projector_ast_identity"
            elif attrs["node_type"] in SYNTHETIC_TYPES:
                ast_node, reason = synthetic_owner(attrs, view)
            else:
                reason = "missing_exact_ast_identity"
            function = enclosing_function(ast_node)
            name_node = function.child_by_field_name("name") if function is not None else None
            name = (text(view.compat_source, name_node) if name_node is not None else "")
            function_text = (text(view.compat_source, function) if function is not None else None)
            renamed_function_text = None
            if function_text is not None:
                renamed_function_text = rewrite_code(function_text, mapping)[0]
            in_renamed = bool(name in mapping)
            rows.append(dict(file=file, source_sha256=reference["sha256"],
                original_graph_node_id=node, node_type=attrs["node_type"],
                solidifi=bool(re.fullmatch(r"buggy_\d+\.sol", file)),
                own_text_renamed=bool(edits), in_renamed_injection_function=in_renamed,
                stratum=classify(bool(edits), in_renamed),
                scope_status=reason, scope_verified=ast_node is not None,
                function_name=name or None,
                function_compat_span=None if function is None else [function.start_byte, function.end_byte],
                function_ast_type=None if function is None else function.type,
                renamed_code=new_code, renamed_function_code=renamed_function_text))
    return rows

def load_context(plan_path, frozen_root):
    plan = checked_plan(plan_path)
    root = Path(frozen_root)
    summary = s.read(root / "D/summary/summary.json")
    if summary["status"] != "complete" or summary["interventions"] != 100:
        raise ValueError("Completed 100 intervention matrix required")
    if summary["bindings"]["plan"] != s.ref(plan_path):
        raise ValueError("8C plan identity differs")
    for reference in summary["bindings"].values():
        checked(reference)
    audit = s.read(root / "A/audit.json")
    views = s.read(checked(audit["node_views"]))
    reports = []
    for item in summary["inputs"]:
        report = s.read(checked(item["intervention"]))
        checked(item["original_predictions"])
        reports.append(report)
    keys = [s.job_key(report["job"]) for report in reports]
    expected = {s.job_key(job) for job in plan["jobs"]
                if plan["tasks"][job["task_id"]]["record"]["task"] == "node"}
    if len(keys) != 100 or len(set(keys)) != 100 or set(keys) != expected:
        raise ValueError("Intervention identity matrix differs")
    return plan, views, reports

def task_scope(plan, task_id):
    task = plan["tasks"][task_id]
    reference = task["record"]["original_graph"]
    graph = read_graph(checked(reference))
    return scope_inventory(graph, task["record"]["sources"])

def group_metrics(rows):
    original = s.metric_counts(s.confusion((r["target"], r["original_best"]) for r in rows))
    renamed = s.metric_counts(s.confusion((r["target"], r["renamed_best"]) for r in rows))
    delta = [r["renamed_probability"] - r["original_probability"] for r in rows]
    positive_delta = [r["renamed_probability"] - r["original_probability"]
                      for r in rows if r["target"] == 1]
    def quantiles(values):
        return dict(zip(("p05", "p25", "p50", "p75", "p95"),
                        [float(x) for x in np.percentile(values, [5,25,50,75,95])])) if values else None
    return dict(n=len(rows), positive=sum(r["target"] for r in rows),
                negative=sum(1-r["target"] for r in rows), original=original,
                renamed=renamed,
                classification_flips=sum(r["original_best"] != r["renamed_best"] for r in rows),
                probability_delta_quantiles=quantiles(delta),
                positive_target_probability_delta_quantiles=quantiles(positive_delta))

def run_stratification(plan_path, frozen_root, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(str(output))
    plan, views, reports = load_context(plan_path, frozen_root)
    inventories = {task: task_scope(plan, task) for task in sorted(views)}
    indexes = {task: s.index_rows(rows) for task, rows in inventories.items()}
    grouped = defaultdict(list)
    for report in reports:
        task = report["job"]["task_id"]
        changed = set(s.index_rows(report["changed_nodes"]))
        for row in report["predictions"]:
            item = indexes[task][s.identity(row)]
            if (item["source_sha256"] != row["source_sha256"]
                    or item["own_text_renamed"] != (s.identity(row) in changed)):
                raise ValueError("Scope/source intervention identity differs")
            if item["solidifi"]:
                grouped[(task, report["job"]["profile"])].append(dict(row, scope=item))
    tables = []
    for (task, profile), rows in sorted(grouped.items()):
        types = sorted({r["scope"]["node_type"] for r in rows})
        for stratum in STRATA:
            for typ in ["ALL"] + types:
                subset = [r for r in rows if r["scope"]["stratum"] == stratum
                          and (typ == "ALL" or r["scope"]["node_type"] == typ)]
                tables.append(dict(task=task, profile=profile, stratum=stratum, node_type=typ,
                                   **group_metrics(subset)))
    result = dict(version=VERSION, training_count=0, model_forward_count=0,
        score_role="outer_test", checkpoint="best", label_view="orig",
        bindings=dict(plan=s.ref(plan_path), summary=s.ref(Path(frozen_root)/"D/summary/summary.json")),
        tables=tables, inventories=inventories,
        scope_counts={task: dict(Counter(r["scope_status"] for r in rows))
                      for task, rows in inventories.items()},
        notes=["Strata use exact AST identity; missing ownership stays explicitly unresolved in c.",
               "Function membership is lexical AST ancestry, not execution/call resolution.",
               "b denotes unchanged own code inside a function whose declaration name was renamed.",
               "Probability delta is P(class=1,renamed)-P(class=1,original); positive-target quantiles also supplied.",
               "Changes in b are consistent with graph-mediated context sensitivity, not a causal proof excluding all model effects."])
    output.mkdir(parents=False)
    s.write(output/"stratification.json", result)
    s._csv(output/"metrics.csv", tables)
    return result

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--frozen-root", required=True)
    parser.add_argument("--output", required=True)
    args=parser.parse_args()
    result=run_stratification(args.plan,args.frozen_root,args.output)
    print(result["scope_counts"])
