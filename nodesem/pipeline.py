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


# ----------------------------------------------------------------------
# Stages writing the feature store (see nodesem.store).
def analyze_task(dataset, category, task, hcg_root, dfg_root, root, label_root, log=print):
    import time

    from nodesem.inputs import load_context
    from nodesem.store import TaskStore
    started = time.monotonic()
    context = load_context(dataset, category, task, hcg_root, dfg_root, label_root)
    analysis = analyze(context)
    store = TaskStore(root, dataset, category, task)
    store.write_analysis(analysis, dict(task_id=context["task_id"], rows=len(analysis["text"]),
                                        features=dict(static=int(analysis["static"].shape[1])),
                                        analysis_seconds=round(time.monotonic() - started, 1)))
    log("%s: %d rows analysed" % (context["task_id"], len(analysis["text"])))
    return store


def encode_task(store, device="cuda", batch_size=32, cache_dir=None, teacher=False, log=print):
    from nodesem.encode import encode_code, encode_ctx, encode_teacher
    from nodesem.store import read_jsonl
    summary = store.summary()
    features = dict(summary.get("features", {}))
    if teacher:
        rows = read_jsonl(store.path / "teacher.jsonl")
        unique, values = encode_teacher([r["text"] for r in rows], device, batch_size, cache_dir)
        index = {t: i for i, t in enumerate(unique)}
        matrix = np.zeros((len(rows), values.shape[1] if len(values) else 384), dtype=np.float32)
        present = np.array([bool(r["present"]) for r in rows])
        for i, r in enumerate(rows):
            if r["present"]:
                matrix[i] = values[index[r["text"]]]
        store.put_matrices(teacher=matrix, teacher_present=present)
        features["teacher"] = int(matrix.shape[1])
    else:
        text = read_jsonl(store.path / "text.jsonl")
        ctx = read_jsonl(store.path / "ctx.jsonl")
        code = encode_code(text, device, batch_size, cache_dir)
        values = {"code": code}
        for mode, name in (("original", "ctx"), ("masked", "ctx_masked")):
            values[name] = encode_ctx([r[mode] for r in ctx], device, batch_size, cache_dir)
        store.put_matrices(**values)
        features.update(code=int(code.shape[1]), ctx=int(values["ctx"].shape[1]),
                        ctx_masked=int(values["ctx_masked"].shape[1]))
    features["encoder_device"] = device
    store.write_summary(dict(features=features))
    log("%s: encoded %s" % (summary["task_id"], "teacher" if teacher else "code, ctx"))


def describe_tasks(contexts_and_stores, cache_dir, backend=None, model_cache=None, log=print):
    """LLM descriptions for all given tasks (shared prompt cache), then teacher text per task."""
    from nodesem.llm.generate import generate, plan_units, teacher_rows
    from nodesem.store import read_jsonl, write_jsonl
    inputs = []
    for context, store in contexts_and_stores:
        analysis = dict(text=read_jsonl(store.path / "text.jsonl"), facts=read_jsonl(store.path / "facts.jsonl"))
        inputs.append((context, analysis))
    units, rows_by_task, schedule = plan_units(inputs)
    results = generate(units, schedule, cache_dir, backend, model_cache, log)
    for (context, analysis), (_, store) in zip(inputs, contexts_and_stores):
        facts = {r["row_key"]: r["facts"] for r in analysis["facts"]}
        rows = teacher_rows(rows_by_task[context["task_id"]], facts, units, results)
        write_jsonl(store.path / "teacher.jsonl", rows)
        store.write_summary(dict(teacher=dict(present=sum(r["present"] for r in rows), rows=len(rows))))
        log("%s: teacher text present for %d of %d rows" % (context["task_id"], sum(r["present"] for r in rows), len(rows)))
