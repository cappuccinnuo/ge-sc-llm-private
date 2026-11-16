"""Build the DFG graph store from HCG outputs.

Layout (``out_root`` is usually ``data/dfg``)::

    <out_root>/<dataset>/<category>/<task>/F1/graph.gpickle   L1
                                          /F2/graph.gpickle   L1+L2
                                          /F3/graph.gpickle   L1+L2+L3
                                          /F*/audit.json
                                          /summary.json

``F0`` is the HCG itself and is referenced, not copied. ``summary.json`` records
per profile the canonical relation edge counts of the DGL graph a model registers,
and per layer how many files fell back to no augmentation.
"""
import copy
import json
import shutil
import time
from collections import Counter
from pathlib import Path

import networkx as nx

import sco_models.graph_utils as gu
from dfg import __version__
from dfg.graph.audit import computation_fingerprint, fingerprint
from dfg.graph.pipeline import GRAPH_RELATIONS, iter_build, layers_for_key, profiles_for_key
from dfg.inputs import TokenEncoder, has_tokens, load_task
from dfg.model.model import build_dgl
from hcg.store.io import dump_json, sha256, write_gpickle

ALL_LAYERS = ("L1", "L2", "L3")
FILE_FALLBACKS = ("file_fallback", "v2_file_fallback")


def canonical_counts(graph, profile):
    """Edge count of every canonical relation the profile's model registers."""
    private = gu.add_hetero_ids(nx.convert_node_labels_to_integers(copy.deepcopy(graph)))
    dgl_graph, _ = build_dgl(private, profile, device="cpu")
    return {"|".join(c): int(dgl_graph.num_edges(c)) for c in dgl_graph.canonical_etypes}


def coverage(audit):
    """Per layer: files seen and files that fell back to no augmentation."""
    out = {}
    for layer, record in audit["layers"].items():
        files = record.get("files", {})
        fallback = sum(any(d.get("kind") in FILE_FALLBACKS for d in r.get("diagnostics", []))
                       for r in files.values())
        out[layer] = dict(files=len(files), file_fallbacks=fallback)
    return out


def _graph_record(graph):
    return dict(nodes=graph.number_of_nodes(), edges=graph.number_of_edges(),
                fingerprint=fingerprint(graph), computation_fingerprint=computation_fingerprint(graph),
                edge_types=dict(sorted(Counter(d["edge_type"] for _, _, d in graph.edges(data=True)).items())))


def build_task(task_input, out_dir, layers=ALL_LAYERS, token_encoder=None, max_iterations=100000,
               profiles=True, log=print):
    """Augment one task and write its cumulative layer graphs; return the summary."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    if "L3" in layers:
        if not has_tokens(task_input.graph):
            raise ValueError("L3 needs node tokens; build the HCG without --no-tokens")
        token_encoder = token_encoder if token_encoder is not None else TokenEncoder()
    started = time.monotonic()
    summary = dict(dfg_version=__version__, dataset=task_input.dataset, category=task_input.category,
                   task=task_input.task, task_id=task_input.task_id,
                   hcg_graph=dict(path=str(task_input.graph_path), sha256=sha256(task_input.graph_path)),
                   files=len(task_input.sources),
                   files_with_recorded_version=sum(v is not None for v in task_input.metadata.values()),
                   layers=list(layers), tokenizer=getattr(token_encoder, "provenance", None), graphs={})
    final = None
    for key, graph, audit in iter_build(task_input.graph, task_input.sources, task_input.metadata,
                                        layers, token_encoder=token_encoder,
                                        max_iterations=max_iterations):
        directory = out_dir / key
        directory.mkdir()
        record = _graph_record(graph)
        if key == "F0":
            record["path"] = str(task_input.graph_path)
        else:
            path = directory / "graph.gpickle"
            write_gpickle(graph, path)
            record.update(path=str(path), sha256=sha256(path))
        with open(directory / "audit.json", "w") as stream:
            json.dump(audit, stream, indent=1, sort_keys=True, default=str)
        record["relations"] = sorted(GRAPH_RELATIONS[key])
        record["coverage"] = coverage(audit)
        if profiles:
            record["profiles"] = {p: canonical_counts(graph, p) for p in profiles_for_key(key)}
        summary["graphs"][key] = record
        log("  %s %s: %d nodes, %d edges" % (task_input.task_id, key, record["nodes"], record["edges"]))
        final = key
    if final != "F%d" % len(layers) or len(layers_for_key(final)) != len(layers):
        raise AssertionError("Pipeline did not produce every requested layer")
    summary["seconds"] = round(time.monotonic() - started, 1)
    dump_json(out_dir / "summary.json", summary)
    return summary


def build(dataset, categories, tasks, hcg_root, out_root, label_root, layers=ALL_LAYERS,
          token_encoder=None, log=print):
    """Build every (category, task); return {task_id: summary}."""
    results = {}
    for category in categories:
        for task in tasks:
            inp = load_task(hcg_root, dataset, category, task, label_root)
            log("%s/%s: %d files, %d with recorded compiler version" % (
                dataset, inp.task_id, len(inp.sources), sum(v is not None for v in inp.metadata.values())))
            results[inp.task_id] = build_task(inp, Path(out_root) / dataset / category / task, layers,
                                              token_encoder, log=log)
    return results
