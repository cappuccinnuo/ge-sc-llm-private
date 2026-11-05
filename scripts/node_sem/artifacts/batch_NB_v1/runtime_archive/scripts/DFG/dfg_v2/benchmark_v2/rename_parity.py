"""Prompt 8E approved in-memory rename parity, without changing model graphs.

Frozen analyzers operate on temporary copies whose ONLY initial change is code.
Their ephemeral DDG outputs are discarded. Stored graph artifacts never change.
"""
import argparse
import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from scripts.DFG.frontend import parse, walk
from scripts.DFG.graph_audit import frozen
from scripts.labeling_v2.safe_graph import read_graph
from .. import FORWARD_RELATIONS
from ..pipeline import build
from ..tokens import TokenEncoder
from ..diagnostics8d.renaming import rewrite_node
from .prepare import checked, read, ref, write, sha
from .prepare_real import load_naming
from .feature_view import graph_fingerprint


def offset_maps(original, rewritten):
    left, right = list(walk(parse(original).root_node)), list(walk(parse(rewritten).root_node))
    if len(left) != len(right):
        raise ValueError("AST topology differs")
    starts, ends = {}, {}
    for a, b in zip(left, right):
        if a.type != b.type or len(a.children) != len(b.children):
            raise ValueError("AST topology differs")
        for table, x, y in ((starts, b.start_byte, a.start_byte),
                            (ends, b.end_byte, a.end_byte)):
            if x in table and table[x] != y:
                raise ValueError("Non-unique exact AST offset correspondence")
            table[x] = y
    return starts, ends


def normalize_evidence(value, file, inverse, starts, ends, layer, env_key=None):
    def visit(v, key=None):
        if isinstance(v, dict):
            local_env = v.get("env_key", env_key)
            result = {}
            for k, x in v.items():
                if layer == "L3" and k == "source":
                    result[k] = local_env if x is not None else None
                elif k in ("start", "end"):
                    table = starts if k == "start" else ends
                    if x not in table:
                        raise ValueError("Fact span has no exact AST offset")
                    result[k] = table[x]
                else:
                    result[k] = visit(x, k)
            return result
        if isinstance(v, list):
            return [visit(x) for x in v]
        if isinstance(v, str):
            if key in ("symbol", "function", "definition", "use", "callable") and v.startswith(file + ":"):
                def number(match):
                    x = int(match.group())
                    if x not in starts:
                        raise ValueError("Semantic identity offset absent from exact AST")
                    return str(starts[x])
                v = re.sub(r"(?<=:)\d+(?=:|$)", number, v)
            # Rename only exact identifier lexemes, never arbitrary substrings.
            return rewrite_node(v, inverse)[0] if inverse else v
        return v
    return visit(value)


def evidence_counter(audit, file, source, inverse=None, original=None):
    starts, ends = offset_maps(original or source, source)
    result = {}
    for layer, record in audit["layers"].items():
        selected = [v for v in record["evidence"]
                    if v.get("file") == file or v.get("function", "").startswith(file + ":")]
        result[layer] = Counter(json.dumps(normalize_evidence(
            v, file, inverse or {}, starts, ends, layer), sort_keys=True) for v in selected)
    return result


def count_facts(audit, file):
    result = {}
    l1 = audit["layers"]["L1"]["files"][file]["analysis"]
    result["L1"] = dict(facts=l1["facts_total"], supported=l1["functions_supported"],
                       total=l1["functions_total"],
                       functions=[{k: f.get(k) for k in ("status", "facts", "routes")}
                                  for f in l1["functions"]])
    l2 = audit["layers"]["L2"]["files"][file]
    result["L2"] = dict(occurrences=l2["occurrences"], unmapped=l2["unmapped"],
                       anchor_missing=l2["anchor_missing"],
                       self_accesses_skipped=l2["self_accesses_skipped"])
    l3 = audit["layers"]["L3"]["files"][file]
    result["L3"] = {k: {v: rec[v] for v in ("occurrences", "projected", "unmapped")}
                    for k, rec in l3["keys"].items()}
    return result


def edge_counter(graph, file):
    def endpoint(n):
        a = graph.nodes[n]
        return ("env", file, a["code"]) if a.get("dfg_v2_aux") else ("original", n)
    return Counter((endpoint(s), endpoint(t), a["edge_type"])
                   for s, t, a in graph.edges(data=True)
                   if a["edge_type"] in FORWARD_RELATIONS and graph.nodes[s]["source_file"] == file)


def check_file(base, archived_graph, archived_audit, source, file, mapping, metadata, encoder):
    before = graph_fingerprint(base)
    rewritten, _ = rewrite_node(source, mapping)
    temporary = copy.deepcopy(base)
    for _, attrs in temporary.nodes(data=True):
        attrs["code"] = rewrite_node(attrs["code"], mapping)[0]
    # Assert every attribute except temporary code is unchanged.
    restored = copy.deepcopy(temporary)
    for nid in restored:
        restored.nodes[nid]["code"] = base.nodes[nid]["code"]
    if graph_fingerprint(restored) != before:
        raise AssertionError("Rename checker changed non-code data")
    orig_graph, orig_audit = build(base, {file: source}, {file: metadata},
                                  ["L1", "L2", "L3"], encoder)
    new_graph, new_audit = build(temporary, {file: rewritten}, {file: metadata},
                                ["L1", "L2", "L3"], encoder)
    counters = [
        evidence_counter(archived_audit, file, source),
        evidence_counter(orig_audit, file, source),
        evidence_counter(new_audit, file, rewritten,
                         {new: old for old, new in mapping.items()}, source)]
    counts = [count_facts(a, file) for a in (archived_audit, orig_audit, new_audit)]
    if not counts[0] == counts[1] == counts[2]:
        raise AssertionError("Analyzer fact/support counts differ: " + file)
    if not counters[0] == counters[1] == counters[2]:
        differences = {layer: dict(
            original_vs_archive=sum((counters[1][layer] - counters[0][layer]).values()),
            renamed_extra=sum((counters[2][layer] - counters[1][layer]).values()),
            renamed_missing=sum((counters[1][layer] - counters[2][layer]).values()))
            for layer in counters[0]}
        raise AssertionError("Normalized exact evidence differs: " + repr(differences))
    edges = [edge_counter(g, file) for g in (archived_graph, orig_graph, new_graph)]
    if not edges[0] == edges[1] == edges[2]:
        raise AssertionError("Projected endpoint/relation counts differ")
    if graph_fingerprint(base) != before:
        raise AssertionError("Source HCG mutated")
    return dict(file=file, counts=counts[0],
                evidence_counts={k: sum(v.values()) for k, v in counters[0].items()},
                edge_counts=dict(Counter(k[2] for k in edges[0])),
                normalized_facts_exact=True, projected_endpoints_exact=True,
                old_hcg_exact=True, temporary_code_only=True,
                rewritten_source_sha256=hashlib.sha256(rewritten.encode()).hexdigest())


def run(naming_dir, store_path, output):
    output = Path(output); output.mkdir(exist_ok=False)
    manifest, inventories, _, maps = load_naming(naming_dir)
    formal = read(checked(manifest["formal_plan"]))
    store = read(store_path)
    if read(Path(store_path).with_name("store.seal.json"))["store_sha256"] != sha(store_path):
        raise ValueError("Graph store seal differs")
    rows = []
    for tid, task in formal["tasks"].items():
        info = store["tasks"][tid]["graphs"]["F3"]
        prepared = read(checked(task["prepared"]["0/1"]))
        if info["graph"] != prepared["profiles"]["G3R"]["graph"]:
            raise ValueError("Archived graph store differs from frozen formal graph")
        graph = read_graph(checked(task["record"]["original_graph"]))
        archived = read_graph(checked(info["graph"]))
        audit = read(checked(info["audit"]))
        encoder = TokenEncoder(task["record"]["feature"])
        for name, reference in sorted(task["record"]["sources"].items()):
            identity = task["record"]["category"] + "_node/" + name
            if identity not in maps:
                continue  # non-SolidiFI source/feature view is the identity.
            source = checked(reference).read_text()
            if reference["sha256"] != maps[identity]["source_sha256"]:
                raise ValueError("Contract/node source identity mismatch")
            if reference.get("metadata") is not None:
                raise ValueError("Renamed source cannot impersonate SHA-bound compiler metadata")
            ids = [n for n, attrs in graph.nodes(data=True) if attrs["source_file"] == name]
            base = graph.subgraph(ids).copy()
            row = check_file(base, archived, audit, source, name, maps[identity]["mapping"],
                             reference.get("metadata"), encoder)
            row.update(task=tid, source=reference)
            rows.append(row)
            print("semantic parity", tid, name, flush=True)
        write(output/(tid+".json"), [r for r in rows if r["task"] == tid])
    if len(rows) != 160:
        raise AssertionError("Expected 80 renamed sources in both task granularities")
    result = dict(passed=True, graph_file_checks=len(rows), unique_renamed_sources=80,
                  naming=ref(Path(naming_dir)/"manifest.json"), store=ref(store_path),
                  artifacts={t: ref(output/(t+".json")) for t in formal["tasks"]},
                  original_graphs_changed=False, model_graphs_rebuilt=False,
                  ephemeral_analysis_outputs_discarded=True, gpu_used=False,
                  training_executed=0,
                  approval="user approved code-only in-memory copies for frozen-analyzer parity")
    write(output/"summary.json", result)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--naming", required=True); p.add_argument("--store", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    print(run(a.naming, a.store, a.output))
