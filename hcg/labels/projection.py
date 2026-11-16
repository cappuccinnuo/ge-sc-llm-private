"""Node labels, contract labels and the line-level subset.

Public-annotation policy of Test_code/label_pipeline (2026-10-10), "author-endpoints":

* a node is vulnerable when its label endpoints (first and last preprocessed line,
  or the synthetic node's marker) hit a preprocessed annotation line of its file;
* a vulnerable node carries all of its file's target-category records, the record
  layout training already reads, stored in the authors' quoted form;
* contract targets are an explicit input and are never derived from node hits;
* the line-level graph keeps every contract with target 1, renumbered 0..n-1.

Measured against the authors' own labels this policy agrees on 98.69% of Dataset A
nodes; the documented differences come from the authors' unpublished annotation
snapshot (Test_code/label_pipeline/DESIGN.txt).
"""
from pathlib import Path

import networkx as nx

from hcg.cfg import author_schema as schema
from hcg.sources.annotations import preprocess_with_map, project


def project_annotations(annotations, sources):
    """{file: records in preprocessed lines}, {file: number of preprocessed lines}."""
    projected, sizes = {}, {}
    for name, records in annotations.items():
        _, line_map = preprocess_with_map(Path(sources[name]).read_text(encoding="utf8"))
        projected[name], sizes[name] = project(records, line_map), len(line_map)
    return projected, sizes


def label_nodes(graph, projected, sizes):
    """Set node_info_vulnerabilities on every node; return the number labelled."""
    positives = 0
    for node, data in graph.nodes(data=True):
        name = data["source_file"]
        lines = schema.label_endpoints(data["node_source_code_lines"])
        synthetic = data["node_type"] in schema.SYNTHETIC
        if any((x < 1 and not (synthetic and x == 0)) or x > sizes[name] for x in lines):
            raise ValueError("node %s of %s has coordinates %s outside its %d preprocessed "
                             "lines" % (node, name, lines, sizes[name]))
        records = projected[name]
        hit = any(set(lines).intersection(rec["lines"]) for rec in records)
        data["node_info_vulnerabilities"] = schema.quote(str(records)) if hit else None
        positives += hit
    return positives


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
