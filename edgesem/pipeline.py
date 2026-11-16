"""EdgeSem build: F4 edges and edge attributes of one task from the HCG and DFG outputs.

Reads ``python -m hcg build`` (sources, F0) and ``python -m dfg build`` (F3 with L1-L3);
statement facts are recomputed from the same inputs with ``nodesem.facts`` (original
view), so the build does not depend on a NodeSem store.
"""
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

from dfg.graph.audit import fingerprint
from edgesem.attributes.compute import _compute_attributes
from edgesem.attributes.layout import edge_rows
from edgesem.graph.f4 import inspect_file
from edgesem.graph.guards import task_guard_audit
from edgesem.schema import VERSION
from edgesem.store import EdgeStore
from hcg.store.io import sha256
from nodesem.facts.extract import extract
from nodesem.inputs import load_context


def build_edges(context):
    """(F4 edge records, F4 audit) of a NodeSem-style task context; the F3 graph is not mutated."""
    graph = context["graphs"]["F3"]
    before = fingerprint(graph)
    edges, files = [], []
    for file, source in sorted(context["source_text"].items()):
        records, audit = inspect_file(file, source, graph)
        if audit["source_sha256"] != context["sources"][file]["sha256"]:
            raise ValueError("%s: source changed since the HCG build" % file)
        edges.extend(records)
        files.append(audit)
    if len({(e["relation"], e["src"], e["dst"]) for e in edges}) != len(edges):
        raise ValueError("Duplicate F4 edge identity")
    if fingerprint(graph) != before:
        raise AssertionError("F3 graph mutated")
    guards = task_guard_audit(graph, files, edges)
    counts, statuses, reasons = Counter(), Counter(), Counter()
    for row in files:
        counts.update(row["counts"])
        statuses.update(row["statuses"])
        reasons.update(row["reasons"])
    passed = guards["nonmodifier_mapping_pass"] and all(f["guards"]["correspondence_pass"] for f in files)
    audit = dict(task_id=context["task_id"], files=files, counts=dict(counts), statuses=dict(statuses),
                 reasons=dict(reasons), guards=guards, hard_conditions_pass=passed)
    return edges, audit


def facts_digest(facts):
    rows = sorted((json.dumps(k, default=str), json.dumps(v, sort_keys=True, default=str)) for k, v in facts.items())
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def build_task(dataset, category, task, hcg_root, dfg_root, root, label_root, log=print):
    started = time.monotonic()
    context = load_context(dataset, category, task, hcg_root, dfg_root, label_root)
    task_id = context["task_id"]
    graph = context["graphs"]["F3"]
    edges, audit = build_edges(context)
    if not audit["hard_conditions_pass"]:
        raise ValueError("%s: F4 guard correspondence failed: %s" % (task_id, audit["guards"]))
    context["f4_audit"] = audit
    facts = extract(task_id, context)
    attrs, diagnostics = _compute_attributes(context, graph, edges, facts)
    rows = edge_rows(graph, edges)
    keys = [r["key"] for r in rows]
    matrix = np.stack([attrs[k] for k in keys]).astype(np.uint8)
    f3_path = Path(dfg_root) / dataset / category / task / "F3/graph.gpickle"
    summary = dict(version=VERSION, task_id=task_id, dfg_f3=dict(sha256=sha256(f3_path)),
                   f3_fingerprint=fingerprint(graph), f4_edges=len(edges),
                   f4_counts=dict(Counter(e["relation"] for e in edges)),
                   attribute_rows=len(keys), attribute_dimension=int(matrix.shape[1]),
                   facts_sha256=facts_digest(facts), source_view="original",
                   seconds=round(time.monotonic() - started, 1))
    EdgeStore(root, dataset, category, task).write(edges, audit, keys, matrix, diagnostics, summary)
    log("%s: %d F4 edges %s, %d attribute rows" % (task_id, len(edges), summary["f4_counts"], len(keys)))
    return summary
