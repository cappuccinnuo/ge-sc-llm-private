"""TODO docstring."""
import copy
import hashlib
import re
from collections import defaultdict

from nodesem.rows import row_key

from dfg.analysis.frontend import walk
from dfg.graph.audit import fingerprint as graph_fingerprint
from dfg.graph.env import ENV_KEYS
from dfg.graph.projection import ProjectionView, Projector
from dfg.schema import AUX_NODE_TYPES
from dfg.train.features import node_code_view, reserved


# ----------------------------------------------------------------------
# node_sem/text_view (picked: VERSION, SIGNATURES, HEADERS, FULL, PLACEHOLDERS, sha_text, normalize, cut_span, _render, _produce, build_text_view)
VERSION = "nodesem-text-v1"

SIGNATURES = {"function_definition", "constructor_definition", "modifier_definition"}

HEADERS = {"contract_declaration", "library_declaration", "interface_declaration"}

FULL = {"expression_statement", "new_variable", "return",
        "continue_statement", "struct_declaration"}

PLACEHOLDERS = {"end_if": "<END_IF>", "end_loop": "<END_LOOP>"}

def sha_text(text):
    return hashlib.sha256(text.encode("utf8")).hexdigest()

def normalize(text):
    return re.sub(r"\s+", " ", text).strip()

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
    for filename in sorted(grouped):
        source, naming = context["source_text"][filename], context["naming"][filename]
        base = graph.subgraph(grouped[filename]).copy()
        # Gate both views on the same frozen AST identities and 8G bijection.
        codes = node_code_view(base, filename, source, naming)
        temporary = copy.deepcopy(base)
        if view == "anonymous":
            for nid in base:
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

def build_text_view(task_id, view, context, graph=None):
    """Produce rows directly; optional disposable graph enables leakage tests."""
    return _produce(task_id, view, context, graph)[0]
