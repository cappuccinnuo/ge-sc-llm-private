"""Node labels, contract labels and the line-level subset.

Two node-label rules map a file's annotated (preprocessed) lines onto its nodes.
Both give a vulnerable node all of its file's target-category records, the record
layout training already reads, stored in the authors' quoted form.

``endpoints`` (Dataset A; public-annotation policy of Test_code/label_pipeline,
2026-10-10, "author-endpoints"): a node is vulnerable when its label endpoints
(first and last preprocessed line, or the synthetic node's marker) hit an annotated
line. This is the MANDO-LLM authors' rule, reconstructed from their graphs; measured
against their own labels it agrees on 98.69% of Dataset A nodes.

``statement`` (Dataset B): the endpoint hits, and for every annotated line no
endpoint hits, the one node the line belongs to:

1. the smallest statement node whose line range contains the line (the middle line
   of a multi-line call or declaration); synthetic nodes are markers, not statements;
2. otherwise the smallest declaration node (contract, function, modifier, ...)
   whose *header*, from its first line to the line opening its body, contains it
   (a parameter or modifier line of a multi-line signature);
3. otherwise none: a body line without a node of its own (``emit``, ``assembly``,
   a closing brace) stays unlabelled and is counted as unreached.

A line in a declaration's body never labels the declaration, so a large node is not
marked vulnerable for a bug somewhere inside it. ``label_nodes`` also reports how
many annotated lines each step reached.

Contract targets are an explicit input and are never derived from node hits; the
line-level graph keeps every contract with target 1, renumbered 0..n-1.
"""
from pathlib import Path

import networkx as nx

from hcg.cfg import author_schema as schema
from hcg.sources.annotations import preprocess_with_map, project

RULES = ("endpoints", "statement")
DECLARATIONS = ("contract_declaration", "library_declaration", "interface_declaration",
                "function_definition", "modifier_definition", "constructor_definition")
STEPS = ("endpoint", "statement", "header", "unreached")


def project_annotations(annotations, sources):
    """{file: records in preprocessed lines}, {file: preprocessed lines (text)}."""
    projected, texts = {}, {}
    for name, records in annotations.items():
        text, line_map = preprocess_with_map(Path(sources[name]).read_text(encoding="utf8"))
        projected[name], texts[name] = project(records, line_map), text.split("\n")
        if len(texts[name]) != len(line_map):
            raise ValueError("%s: preprocessed text and line map differ in length" % name)
    return projected, texts


def header_end(lines, first, last):
    """Last line of a declaration's header: the line that opens its body (or ends it)."""
    for number in range(first, last + 1):
        text = lines[number - 1]
        if "{" in text or text.rstrip().endswith(";"):
            return number
    return first


def label_nodes(graph, projected, texts, rule="endpoints"):
    """Set node_info_vulnerabilities on every node.

    Returns (number of vulnerable nodes, {file: {step: annotated lines it reached}});
    under ``endpoints`` only the endpoint step can reach a line.
    """
    if rule not in RULES:
        raise ValueError("unknown node-label rule %r; known: %s" % (rule, ", ".join(RULES)))
    by_file = {}
    for node, data in graph.nodes(data=True):
        name = data["source_file"]
        size = len(texts[name])
        ends = schema.label_endpoints(data["node_source_code_lines"])
        synthetic = data["node_type"] in schema.SYNTHETIC
        if any((x < 1 and not (synthetic and x == 0)) or x > size for x in ends):
            raise ValueError("node %s of %s has coordinates %s outside its %d preprocessed "
                             "lines" % (node, name, ends, size))
        spans = [tuple(s) for s in data["node_source_code_lines"] if len(s) == 2]
        by_file.setdefault(name, []).append((node, data["node_type"], set(ends), spans))
    vulnerable, reached = set(), {}
    for name, nodes in by_file.items():
        counts = reached[name] = dict.fromkeys(STEPS, 0)
        for line in sorted({line for rec in projected[name] for line in rec["lines"]}):
            hits = [n for n, _, ends, _ in nodes if line in ends]
            step, chosen = ("endpoint", hits) if hits else _fallback(nodes, line, texts[name], rule)
            counts[step] += 1
            vulnerable.update(chosen)
    for node, data in graph.nodes(data=True):
        records = projected[data["source_file"]]
        data["node_info_vulnerabilities"] = schema.quote(str(records)) if node in vulnerable else None
    return len(vulnerable), reached


def _fallback(nodes, line, lines, rule):
    """(step, [node]) for an annotated line that no endpoint hits."""
    if rule == "endpoints":
        return "unreached", []
    for step, candidates in (
            ("statement", [(b - a, n) for n, kind, _, spans in nodes for a, b in spans
                           if a <= line <= b and kind not in DECLARATIONS and kind not in schema.SYNTHETIC]),
            ("header", [(b - a, n) for n, kind, _, spans in nodes for a, b in spans
                        if kind in DECLARATIONS and a <= line <= header_end(lines, a, b)])):
        if candidates:
            return step, [min(candidates)[1]]
    return "unreached", []


def reached_summary(reached, source_of=None):
    """Totals of ``label_nodes``' per-file counts: {"all": ..., <source>: ...}."""
    groups = {"all": list(reached)}
    for name in sorted(reached):
        if source_of is not None and any(reached[name].values()):
            groups.setdefault(source_of[name], []).append(name)
    return {key: {step: sum(reached[f][step] for f in files) for step in STEPS}
            for key, files in groups.items()}


def contract_entries(targets):
    return [{"contract_name": name, "targets": targets[name]} for name in sorted(targets)]


def line_level(graph, targets):
    """Subgraph of target-1 contracts, renumbered 0..n-1; plus new->old node ids."""
    keep = [n for n, d in graph.nodes(data=True) if targets[d["source_file"]] == 1]
    sub = graph.subgraph(keep).copy()
    old_ids = list(sub.nodes())
    renumbered = nx.relabel_nodes(sub, {n: i for i, n in enumerate(old_ids)}, copy=True)
    renumbered.graph.update(graph.graph)
    return renumbered, old_ids
