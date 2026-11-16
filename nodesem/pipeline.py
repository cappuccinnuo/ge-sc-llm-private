"""NodeSem analysis stage: one task's code text, statement facts, CTX fields, STATIC vectors.

Rows follow the F3 node order: original HCG nodes first, then ``env_source`` nodes
sorted by (file, key). Every row carries ``row_key``, ``file``, ``node_type`` and the
SHA-256 of its source and code, so later stages join by identity, not position.
"""
import hashlib
import json

import numpy as np

from dfg.graph.audit import fingerprint
from nodesem.context import ctx_fields, enrich
from nodesem.facts.extract import extract
from nodesem.static import encode, load_schema
from nodesem.text import build_text_view

IDENTITY = ("row_key", "file", "node_type", "source_sha256", "code_sha256")
CTX_MODES = ("original", "masked")


def fields_sha(fields):
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def analyze(context):
    """Return dict(text, facts, ctx, ctx_masked, static) for one task context."""
    graph = context["graphs"]["F3"]
    before = fingerprint(graph)
    text = build_text_view(context["task_id"], "original", context)
    facts = extract(context["task_id"], context)
    if [r["row_key"] for r in text] != list(facts):
        raise AssertionError("Text and fact rows are not aligned")
    fact_rows = [dict(row_key=key, facts=value) for key, value in facts.items()]
    enriched = enrich(graph, context["source_text"], text, fact_rows)
    out = dict(text=text, facts=fact_rows)
    for mode in CTX_MODES:
        rows = []
        for fact, row in zip(fact_rows, enriched):
            fields = ctx_fields(fact, row, mode)
            rows.append(dict({k: row[k] for k in IDENTITY}, fields=fields, field_order=list(fields),
                             names=mode, fields_sha256=fields_sha(fields)))
        out["ctx" if mode == "original" else "ctx_masked"] = rows
    schema = load_schema()
    out["static"] = np.stack([encode(row, schema) for row in fact_rows]).astype(np.float32)
    if fingerprint(graph) != before:
        raise AssertionError("Analysis mutated the DFG graph")
    return out
