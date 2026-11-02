"""NS-P2 M1 text producer (mando, Python 3.7).

Only exact compatibility-AST identities select slices. Frozen Projector and
node_code_view alone inspect structural DOT labels. Labels, filenames and
coordinates are never appended to feature text; identity metadata stays separate.
"""
import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import inspect
import json
from pathlib import Path
import re
import time

from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.frontend import walk
from scripts.DFG.projection import Projector
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2 import AUX_NODE_TYPES
from scripts.DFG.dfg_v2.env import ENV_KEYS
from scripts.DFG.dfg_v2.benchmark_v2.anon_parity import node_code_view
from scripts.DFG.dfg_v2.benchmark_v2.prepare_spelling import load_result
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import reserved
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref, write
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from .carrier import row_key

VERSION = "nodesem-text-v1"
ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/plan.json"
SIGNATURES = {"function_definition", "constructor_definition", "modifier_definition"}
HEADERS = {"contract_declaration", "library_declaration", "interface_declaration"}
FULL = {"expression_statement", "new_variable", "return",
        "continue_statement", "struct_declaration"}
PLACEHOLDERS = {"end_if": "<END_IF>", "end_loop": "<END_LOOP>"}


def sha_text(text):
    return hashlib.sha256(text.encode("utf8")).hexdigest()


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def producer_refs():
    # Imported frozen implementations are provenance, not modifications.
    functions = (Projector, ProjectionView, node_code_view, load_result,
                 reserved, graph_fingerprint, row_key)
    paths = {Path(inspect.getsourcefile(f)).resolve() for f in functions}
    paths.add(Path(__file__).resolve())
    for relative in ("scripts/DFG/frontend.py", "scripts/DFG/graph_audit.py",
                     "scripts/DFG/dfg_v2/benchmark_v2/anon_binding.py",
                     "process_graphs/tree_sitter_codeviews/utils/preprocessor.py"):
        paths.add(ROOT / relative)
    return {str(p.relative_to(ROOT)): ref(p) for p in sorted(paths)}


def load_context(task_id, plan_path=PLAN):
    plan_path = Path(plan_path)
    seal = read(plan_path.with_name("plan.seal.json"))
    if ref(plan_path) != seal["plan"]:
        raise ValueError("8H plan seal differs")
    plan = read(plan_path)
    task = plan["tasks"][task_id]
    preparation = read(checked(plan["source_preparation"]))
    naming_ref = preparation["bound_artifacts"]["spelling_naming"]
    naming = read(checked(naming_ref))
    source_index = read(checked(naming["artifacts"]["sources"]))
    graphs = {name: read_graph(checked(task["profiles"][profile]["graph"]))
              for name, profile in (("F0", "G0"), ("F3", "G3R"))}
    feature_ref = task["feature_view"]
    feature = read(checked(feature_ref))
    source_text, results, naming_rows = {}, {}, {}
    for filename, source_ref in task["record"]["sources"].items():
        item = source_index[task["category"] + "/" + filename]
        if item["source"] != source_ref:
            raise ValueError("8G/task source identity differs")
        source_text[filename], results[filename] = load_result(item)
        naming_rows[filename] = item["result"]
    order = [r["original_graph_node_id"] for r in feature["rows"]]
    if order != list(graphs["F0"]):
        raise ValueError("Frozen 8G/F0 original row order differs")
    return dict(task_id=task_id, graphs=graphs, order=order,
                sources=task["record"]["sources"], source_text=source_text,
                naming=results, feature_rows=feature["rows"],
                provenance=dict(plan=ref(plan_path), naming=naming_ref,
                                spelling_view=feature_ref, naming_results=naming_rows,
                                graphs={name: task["profiles"][profile]["graph"]
                                        for name, profile in (("F0", "G0"), ("F3", "G3R"))}))


def cut_span(ast, projection, node_type):
    """Return selected byte span and literal wrapper; no line-number guesses."""
    start, end = ast.start_byte, ast.end_byte
    if node_type in ("if", "while"):
        condition = ast.child_by_field_name("condition")
        if condition is None:
            return start, end, "", "", "fallback", "missing_condition"
        return condition.start_byte, condition.end_byte, node_type + " ( ", " )", "ast_condition", None
    if node_type == "for":
        body = ast.child_by_field_name("body")
        if body is None:
            return start, end, "", "", "fallback", "missing_loop_body"
        return start, body.start_byte, "", "", "ast_condition", None
    if node_type in SIGNATURES | HEADERS:
        body = ast.child_by_field_name("body")
        return start, body.start_byte if body is not None else end, "", "", (
            "ast_signature" if node_type in SIGNATURES else "ast_header"), None
    if node_type in FULL:
        return start, end, "", "", "full", None
    return start, end, "", "", "fallback", "unrecognized_node_type"


def _render(ast, projection, node_type, mapping, anonymous):
    start, end, prefix, suffix, mode, reason = cut_span(ast, projection, node_type)
    identifiers = [n for n in walk(ast) if n.type == "identifier"
                   and start <= n.start_byte and n.end_byte <= end]
    inverse = {new: old for old, new in mapping.items()}
    text = projection.compat[start:end]
    restored = text
    for node in sorted(identifiers, key=lambda n: n.start_byte, reverse=True):
        name = projection.compat[node.start_byte:node.end_byte].decode("utf8")
        if anonymous:
            if not reserved(name) and name not in inverse:
                raise ValueError("Non-anonymous identifier in feature text")
            replacement = inverse.get(name, name).encode("utf8")
            lo, hi = node.start_byte - start, node.end_byte - start
            restored = restored[:lo] + replacement + restored[hi:]
    rendered = normalize(prefix + text.decode("utf8") + suffix)
    recovered = normalize(prefix + restored.decode("utf8") + suffix)
    return rendered, recovered, mode, reason


def _produce(task_id, view, context, graph=None):
    if view not in ("anonymous", "original") or context["task_id"] != task_id:
        raise ValueError("Unknown text view/task")
    graph = context["graphs"]["F3"] if graph is None else graph
    before = graph_fingerprint(graph)
    original = [n for n, a in graph.nodes(data=True) if a["node_type"] not in AUX_NODE_TYPES]
    if original != context["order"]:
        raise ValueError("Original graph/8G identity or order differs")
    grouped = defaultdict(list)
    for n in original:
        grouped[graph.nodes[n]["source_file"]].append(n)
    if set(grouped) != set(context["sources"]):
        raise ValueError("Source population differs")
    rows_by_id, restored_by_id = {}, {}
    feature_rows = {r["original_graph_node_id"]: r for r in context["feature_rows"]}
    for filename in sorted(grouped):
        source, naming = context["source_text"][filename], context["naming"][filename]
        base = graph.subgraph(grouped[filename]).copy()
        # Gate both views on the same frozen AST identities and 8G bijection.
        codes, _ = node_code_view(base, filename, source, naming)
        temporary = copy.deepcopy(base)
        for nid in base:
            if sha_text(base.nodes[nid]["code"]) != feature_rows[nid]["code_sha256"]:
                raise ValueError("Code differs from frozen feature row")
            if sha_text(codes[nid]) != feature_rows[nid]["rewritten_code_sha256"]:
                raise ValueError("Anonymous node code differs from 8G")
            if view == "anonymous":
                temporary.nodes[nid]["code"] = codes[nid]
        projection = ProjectionView(naming["rewritten"] if view == "anonymous" else source, filename)
        projector = Projector(temporary, projection)
        by_id = {ident: projection.compat_nodes[key] for key, ident in projection.compat_ids.items()}
        ast_by_node = {nid: by_id[ident] for ident, nid in projector.by_ast.items()}
        for nid in base:
            attrs = base.nodes[nid]
            kind = attrs["node_type"]
            if kind in PLACEHOLDERS:
                text = recovered = PLACEHOLDERS[kind]
                mode, reason = "placeholder", None
            else:
                if nid not in ast_by_node:
                    # A corrupt/missing anchor is an identity error, not a fallback.
                    raise ValueError("No verified AST identity for original node")
                text, recovered, mode, reason = _render(
                    ast_by_node[nid], projection, kind, naming["mapping"], view == "anonymous")
            row = dict(row_key=nid, file=filename, node_type=kind,
                       source_sha256=context["sources"][filename]["sha256"],
                       code_sha256=sha_text(attrs["code"]), text=text,
                       text_sha256=sha_text(text), cut_mode=mode, fallback_reason=reason)
            rows_by_id[nid] = row
            restored_by_id[nid] = recovered
    rows = [rows_by_id[n] for n in context["order"]]
    auxiliary = sorted(((n, a) for n, a in graph.nodes(data=True)
                        if a["node_type"] in AUX_NODE_TYPES),
                       key=lambda pair: (pair[1]["source_file"], pair[1]["code"]))
    for nid, attrs in auxiliary:
        key = row_key(nid, attrs)
        text = attrs["code"]
        if text not in ENV_KEYS or attrs["source_file"] not in context["sources"]:
            raise ValueError("Unknown auxiliary text/source identity")
        rows.append(dict(row_key=key, file=attrs["source_file"], node_type="env_source",
                         source_sha256=context["sources"][attrs["source_file"]]["sha256"],
                         code_sha256=sha_text(text), text=text, text_sha256=sha_text(text),
                         cut_mode="full", fallback_reason=None))
        restored_by_id[key] = text
    keys = [r["row_key"] for r in rows]
    if len(keys) != len(set(keys)) or len(keys) != len(graph):
        raise ValueError("Duplicate/missing feature rows")
    if graph_fingerprint(graph) != before:
        raise AssertionError("Text extraction mutated input graph")
    return rows, restored_by_id


def build_text_view(task_id, view, context=None, graph=None):
    """Produce rows directly; optional disposable graph enables leakage tests."""
    context = load_context(task_id) if context is None else context
    return _produce(task_id, view, context, graph)[0]


def write_views(task_id, output, context=None):
    context = load_context(task_id) if context is None else context
    results, recovered, elapsed = {}, {}, {}
    for view in ("original", "anonymous"):
        started = time.monotonic()
        results[view], recovered[view] = _produce(task_id, view, context)
        elapsed[view] = time.monotonic() - started
    for original, anonymous in zip(results["original"], results["anonymous"]):
        if (original["row_key"] != anonymous["row_key"]
                or original["cut_mode"] != anonymous["cut_mode"]
                or original["text"] != recovered["anonymous"][anonymous["row_key"]]):
            raise ValueError("View AST cut/inverse-renaming parity failed")
    profiles = {key: dict(graph_fingerprint=graph_fingerprint(graph))
                for key, graph in context["graphs"].items()}
    references = {}
    for view, rows in results.items():
        directory = Path(output) / view / task_id
        directory.mkdir(parents=True, exist_ok=False)
        with (directory / "text.jsonl").open("x", encoding="utf8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        manifest = dict(version=VERSION, view=view, task_id=task_id,
                        rows=rows, sources=context["sources"], profiles=profiles,
                        input_text=ref(directory / "text.jsonl"),
                        implementation=producer_refs(), provenance=context["provenance"],
                        elapsed_seconds=elapsed[view],
                        cut_modes=dict(Counter(r["cut_mode"] for r in rows)),
                        fallback_by_type=dict(Counter(r["node_type"] for r in rows if r["cut_mode"] == "fallback")),
                        unique_texts=len({r["text"] for r in rows}),
                        inverse_rename_exact=True, cut_modes_equal=True,
                        identifier_whitelist_checked=True, original_graph_unchanged=True)
        write(directory / "manifest.json", manifest)
        write(directory / "manifest.seal.json", dict(manifest=ref(directory / "manifest.json")))
        references[view] = ref(directory / "manifest.json")
    return references


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(write_views(args.task, args.out), indent=2))


if __name__ == "__main__":
    main()
