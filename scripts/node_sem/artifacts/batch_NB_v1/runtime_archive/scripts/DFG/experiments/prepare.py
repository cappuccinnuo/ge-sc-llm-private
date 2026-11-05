"""Freeze Dataset A HCG pairs without modifying DDG, labels or token features."""
import argparse
import ast
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from scripts.DFG.cli import read_sources
from scripts.DFG.configuration import prepare_graph
from scripts.DFG.models import DDGConfig
from scripts.DFG.frontend import library_path, parse, walk, FUNCTION_TYPES
from scripts.DFG.graph_audit import assert_augmented, fingerprint, frozen
from scripts.DFG import DATA_DEF_USE
from scripts.labeling_v2.safe_graph import read_graph, write_graph
from scripts.encode_tokenizer_features import encode_ids
from .common import ROOT, REPO, new_output, read_json, write_json, sha256, utc, code_hashes

TOKENIZER = "Salesforce/codet5p-770m"
REVISION = "3f7cc6e80aee6612f41253b5ee28f09f86faa35f"


def cohort_catalog():
    base = "experiments/ge-sc-data/source_code/"
    upstream = "data/upstream_mando_llm/graph_detection/"
    access = "scripts/access_control_test/artifacts/dataset_a_source_range_v1/"
    return {
        "reentrancy_author": {
            "category": "reentrancy", "label_version": "released_author_node_labels",
            "graph": base + "reentrancy/upstream_contractlevel_tok.gpickle",
            "raw_graph": upstream + "reentrancy_tree_sitter_cfg_cg_compressed_graphs.gpickle",
            "labels": upstream + "reentrancy_graph_labels.json",
            "description": "Released CFG+CG; locally encoded exact serialized code; author labels unchanged"},
        "access_control_author": {
            "category": "access_control", "label_version": "released_author_node_labels",
            "graph": "scripts/access_control_test/artifacts/author_graph_v1/hcg_author_tok.gpickle",
            "raw_graph": upstream + "access_control_tree_sitter_cfg_cg_compressed_graphs.gpickle",
            "labels": upstream + "access_control_graph_labels.json",
            "description": "Released CFG+CG; locally encoded exact serialized code; author labels unchanged"},
        "reentrancy_local_narrow": {
            "category": "reentrancy", "label_version": "local_original_source_range_narrow_end_if",
            "graph": base + "reentrancy/tokenizer_ids_narrow.gpickle",
            "raw_graph": base + "reentrancy/hcg_narrow.gpickle",
            "labels": base + "reentrancy/graph_labels.json",
            "description": "Local narrow HCG and local source-range labels; independent secondary cohort"},
        "access_control_local_narrow": {
            "category": "access_control", "label_version": "local_original_source_range_narrow_end_if",
            "graph": access + "tokenizer_ids_codet5p-770m_hcg_compressed_graphs.gpickle",
            "raw_graph": access + "hcg_labeled.gpickle",
            "labels": access + "graph_labels.json",
            "description": "Local dataset_a_source_range_v1; narrow end_if, local range-overlap labels"},
    }


def positive(data):
    records = data.get("node_info_vulnerabilities")
    for _ in range(3):
        if not isinstance(records, str):
            break
        try:
            records = ast.literal_eval(records)
        except (ValueError, SyntaxError) as exc:
            raise ValueError("Malformed serialized node annotation") from exc
    if records is not None and not isinstance(records, list):
        raise ValueError("Expected list-or-None node labels or their literal serialization")
    if isinstance(records, list) and any(not isinstance(item, dict) for item in records):
        raise ValueError("Malformed node annotation records")
    return int(bool(records))


def check_labels(graph, records):
    if not isinstance(records, list):
        raise ValueError("Graph labels must be a list")
    labels = {}
    for row in records:
        name, value = row["contract_name"], row["targets"]
        if name in labels or type(value) is not int or value not in (0, 1):
            raise ValueError("Duplicate or invalid contract label")
        labels[name] = value
    files = {d["source_file"] for _, d in graph.nodes(data=True)}
    if set(labels) != files:
        raise ValueError("Graph-label file population differs from graph")
    # A clean contract cannot contain positive nodes; a buggy contract may have
    # no hit in this graph. Keep graph labels as the task/population authority.
    for _, data in graph.nodes(data=True):
        if positive(data) and labels[data["source_file"]] == 0:
            raise ValueError("Positive node in graph-labelled clean file")
    # Do not silently normalize encodings the unchanged model cannot read.
    from sco_models.graph_utils import get_node_label
    try:
        model_targets = get_node_label(graph)[0]
    except (TypeError, ValueError, IndexError, KeyError, SyntaxError) as exc:
        raise ValueError("Frozen node-label encoding is incompatible with the original model: " + str(exc))
    if model_targets != [positive(d) for _, d in graph.nodes(data=True)]:
        raise ValueError("Model and audit disagree about node-label meaning")
    return labels


def verify_raw(raw, graph):
    """The token-bearing artifact must differ from its raw graph only by token."""
    if list(raw) != list(graph) or frozen(raw.graph) != frozen(graph.graph):
        raise ValueError("Encoded graph identities/order/metadata differ from raw graph")
    if list(raw.edges(keys=True)) != list(graph.edges(keys=True)):
        raise ValueError("Encoded graph edges/keys differ from raw graph")
    for node in raw:
        a = {k: v for k, v in raw.nodes[node].items() if k != "token"}
        b = {k: v for k, v in graph.nodes[node].items() if k != "token"}
        if frozen(a) != frozen(b):
            raise ValueError("Encoded graph changed raw node attributes: " + str(node))
    for s, t, key, data in raw.edges(keys=True, data=True):
        if frozen(data) != frozen(graph[s][t][key]):
            raise ValueError("Encoded graph changed raw edge attributes")
    return True


def verify_features(graph, tokenizer):
    """Recompute every existing vector for verification; never assign features."""
    pad = tokenizer.pad_token_id
    if pad is None:
        pad = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else 0
    cache, digest = {}, hashlib.sha256()
    truncated = 0
    for node, data in graph.nodes(data=True):
        vector = np.asarray(data.get("token"))
        if vector.dtype != np.float32 or vector.shape != (512,) or not np.isfinite(vector).all():
            raise ValueError("Invalid float32[512] feature at " + str(node))
        code = data.get("code") or ""
        if not isinstance(code, str):
            raise ValueError("Non-string node code")
        if code not in cache:
            ids = tokenizer(code, add_special_tokens=True).input_ids
            cache[code] = (encode_ids(ids, 512, pad), len(ids))
        expected, length = cache[code]
        if not np.array_equal(vector, expected):
            raise ValueError("Token vector differs from exact stored-code ids at " + str(node))
        truncated += int(length > 512)
        digest.update(repr(node).encode("utf8"))
        digest.update(vector.tobytes())
    return {"model": TOKENIZER, "revision": REVISION,
            "tokenizer_class": type(tokenizer).__name__, "scheme": "ids",
            "node_feature": "inside_token", "feature_size": 512, "dtype": "float32",
            "input_text": "node.code exactly as stored, including serialization if present",
            "add_special_tokens": True, "padding_id": pad,
            "local_files_only": True, "model_weights_loaded": False,
            "feature_generation": "Pre-existing local reconstruction, not author-supplied features",
            "verified_nodes": len(graph), "unique_code_values": len(cache),
            "truncated_nodes": truncated, "ordered_feature_sha256": digest.hexdigest()}


def cached_tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(
        TOKENIZER, revision=REVISION, local_files_only=True, trust_remote_code=False)


def tokenizer_assets():
    cache = Path.home() / ".cache/huggingface/hub/models--Salesforce--codet5p-770m/snapshots" / REVISION
    names = ("config.json", "tokenizer_config.json", "special_tokens_map.json",
             "added_tokens.json", "vocab.json", "merges.txt", "tokenizer.json")
    return {str(cache / n): sha256(cache / n) for n in names if (cache / n).is_file()}


def graph_stats(graph):
    return {"nodes": len(graph), "edges": graph.number_of_edges(),
            "files": len({d["source_file"] for _, d in graph.nodes(data=True)}),
            "positive_nodes": sum(positive(d) for _, d in graph.nodes(data=True)),
            "node_types": dict(Counter(d["node_type"] for _, d in graph.nodes(data=True))),
            "edge_types": dict(Counter(d["edge_type"] for _, _, d in graph.edges(data=True))),
            "cross_file_edges": sum(graph.nodes[s]["source_file"] != graph.nodes[t]["source_file"]
                                    for s, t in graph.edges())}


def coverage(graph, enhanced, audit, sources):
    result = {"files_total": len(audit["files"]), "files_with_ddg": 0,
              "functions_in_parseable_sources": 0, "function_count_unknown_files": [],
              "functions_supported": 0, "functions_counted_by_semantic_frontend": 0,
              "functions_with_projected_evidence": len({e["function"] for e in audit["evidence"]}),
              "facts_total_where_projection_attempted": 0, "facts_projected": 0,
              "facts_unmapped_where_projection_attempted": 0, "self_facts": 0,
              "ddg_edges": audit["invariants"]["ddg_edges"], "diagnostic_kinds": {},
              "fallback_reasons": {}, "per_file": {}}
    ddg_files = {enhanced.nodes[s]["source_file"] for s, _, d in enhanced.edges(data=True)
                 if d["edge_type"] == DATA_DEF_USE}
    result["files_with_ddg"] = len(ddg_files)
    kinds, reasons = Counter(), Counter()
    for name, entry in audit["files"].items():
        parsed_count = None
        if name in sources:
            try:
                parsed_count = sum(n.type in FUNCTION_TYPES and n.child_by_field_name("body") is not None
                                   for n in walk(parse(sources[name]).root_node))
            except Exception as exc:
                # Counting is diagnostic only; never override the frozen DDG result.
                count_reason = type(exc).__name__ + ": " + str(exc)
        else:
            count_reason = "source missing"
        if parsed_count is None:
            result["function_count_unknown_files"].append({"file": name, "reason": count_reason})
        else:
            result["functions_in_parseable_sources"] += parsed_count
        a, p = entry.get("analysis", {}), entry.get("projection", {})
        result["functions_supported"] += a.get("functions_supported", 0)
        result["functions_counted_by_semantic_frontend"] += a.get("functions_total", 0)
        result["facts_total_where_projection_attempted"] += p.get("facts_total", 0)
        result["facts_projected"] += p.get("facts_projected", 0)
        result["facts_unmapped_where_projection_attempted"] += p.get("facts_unmapped", 0)
        result["self_facts"] += p.get("self_facts", 0)
        for d in entry.get("diagnostics", []):
            kinds[d["kind"]] += 1
            if "fallback" in d["kind"]:
                reasons[d.get("reason", "unspecified")] += 1
        result["per_file"][name] = {
            "parsed_functions": parsed_count, "analysis": a, "projection": p,
            "has_ddg": name in ddg_files,
            "diagnostic_kinds": dict(Counter(d["kind"] for d in entry.get("diagnostics", [])))}
    result["diagnostic_kinds"], result["fallback_reasons"] = dict(kinds), dict(reasons)
    result["fact_count_limit"] = (
        "Frozen pipeline exposes fact totals only after successful whole-file projection validation; "
        "facts from projection-rejected files are not included in this denominator.")
    result["all_samples_retained"] = list(graph) == list(enhanced)
    return result


def build_pairs(graph, sources, labels, modes=None):
    e0, a0 = prepare_graph(graph, sources, DDGConfig(use_ddg=False), modes)
    e1, a1 = prepare_graph(graph, sources, DDGConfig(use_ddg=True), modes)
    if fingerprint(e0) != fingerprint(graph):
        raise AssertionError("E0 is not the unchanged baseline")
    selected = [n for n, d in graph.nodes(data=True) if labels[d["source_file"]] == 1]
    n0, n1 = e0.subgraph(selected).copy(), e1.subgraph(selected).copy()
    pairs = {"E0": {"contract": e0, "node": n0}, "E1": {"contract": e1, "node": n1}}
    invariants = {"contract": assert_augmented(e0, e1), "node": assert_augmented(n0, n1)}
    return pairs, a1, invariants


def prepare(cohort, output, tokenizer=None):
    out = new_output(output)
    spec = cohort_catalog()[cohort]
    paths = {k: REPO / spec[k] for k in ("graph", "raw_graph", "labels")}
    input_hashes = {k: {"path": str(p), "sha256": sha256(p)} for k, p in paths.items()}
    graph, raw = read_graph(paths["graph"]), read_graph(paths["raw_graph"])
    verify_raw(raw, graph)
    del raw
    records = read_json(paths["labels"])
    labels = check_labels(graph, records)
    source_dir = REPO / "experiments/ge-sc-data/source_code" / spec["category"] / "source_files"
    sources, modes, used, missing = read_sources(graph, directory=source_dir)
    print("Inventory {}: {} nodes / {} edges / {} files / {} buggy files".format(
        cohort, len(graph), graph.number_of_edges(), len(labels), sum(labels.values())), flush=True)
    feature = verify_features(graph, tokenizer or cached_tokenizer())
    feature["asset_hashes"] = tokenizer_assets()
    print("Verified {} existing token vectors; beginning frozen DDG analysis".format(len(graph)), flush=True)
    pairs, audit, invariants = build_pairs(graph, sources, labels, modes)
    cov = coverage(graph, pairs["E1"]["contract"], audit, sources)
    for info in input_hashes.values():
        if sha256(info["path"]) != info["sha256"]:
            raise ValueError("Input changed during preparation")
    for info in used.values():
        if sha256(info["path"]) != info["sha256"]:
            raise ValueError("Source changed during preparation")
    # Do not copy labels between cohorts or regenerate any labels.
    manifest = {"schema": 1, "created_utc": utc(), "modified_by": "Codex",
                "dataset": "A", "category": spec["category"], "cohort": cohort,
                "label_version": spec["label_version"], "description": spec["description"],
                "inputs": input_hashes, "sources": used, "missing_sources": missing,
                "source_dir": str(source_dir), "feature": feature, "graphs": {},
                "invariants": invariants, "code_hashes": code_hashes(),
                "grammar": {"path": str(library_path()), "sha256": sha256(library_path())},
                "ddg_algorithm_frozen": True, "ddg_relation": DATA_DEF_USE,
                "graph_files": len(labels), "buggy_files": sum(labels.values()),
                "node_population": "Induced graph of graph-labelled buggy files; no node renumbering",
                "limitations": [
                    "Released label construction and historical author source hashes remain unknown.",
                    "Token IDs are a fixed verified local reconstruction, not released author vectors.",
                    "Zero-edge/fallback files and functions remain in the model graph.",
                    "Source hash proves present inputs; strict projector validates accepted source anchors.",
                    "Node metrics count graph nodes, not deduplicated source lines."]}
    # Serialize the audit before creating files, catching non-JSON diagnostics.
    json.dumps(audit)
    out.mkdir(parents=True, exist_ok=False)
    for variant, tasks in pairs.items():
        manifest["graphs"][variant] = {}
        for task, g in tasks.items():
            path = out / variant / (task + ".gpickle")
            path.parent.mkdir(exist_ok=True)
            write_graph(g, path)
            if fingerprint(read_graph(path)) != fingerprint(g):
                raise AssertionError("Graph serialization changed content")
            manifest["graphs"][variant][task] = {
                "path": str(path.relative_to(out)), "sha256": sha256(path), "stats": graph_stats(g)}
    write_json(out / "graph_labels.json", records)
    write_json(out / "source_manifest.json", used)
    write_json(out / "ddg_audit.json", audit)
    write_json(out / "coverage.json", cov)
    for key, filename in (("graph_labels", "graph_labels.json"), ("source_manifest", "source_manifest.json"),
                          ("coverage", "coverage.json"), ("ddg_audit", "ddg_audit.json")):
        manifest[key] = {"path": filename, "sha256": sha256(out / filename)}
    write_json(out / "manifest.json", manifest)
    print("Prepared {}: DDG edges={}, files with DDG={}/{}, supported functions={}/{} parsed".format(
        cohort, cov["ddg_edges"], cov["files_with_ddg"], cov["files_total"],
        cov["functions_supported"], cov["functions_in_parseable_sources"]), flush=True)
    print(str(out / "manifest.json"), flush=True)
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort", required=True, choices=sorted(cohort_catalog()))
    p.add_argument("--output", required=True, help="New directory under scripts/DFG/experiments")
    args = p.parse_args(argv)
    return prepare(args.cohort, args.output)


if __name__ == "__main__":
    main()
