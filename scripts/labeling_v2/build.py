"""Codex 2026-10-08: build independent label variants; never edit upstream inputs."""
import sys
sys.dont_write_bytecode = True
import argparse
import copy
import hashlib
import json
import pickle
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import numpy as np
from safe_graph import read_graph, write_graph, sha256
from label_rules import (
    author_replay, hit_records, parse_records, source_replay, verified_annotations,
)
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
from line_mapping import build_line_map, preprocessed_to_original

BASE = REPO / "experiments/ge-sc-data/source_code/reentrancy"

def read_json(path):
    return json.loads(path.read_text(encoding="utf8"))

def write_json(path, value):
    with path.open("x", encoding="utf8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

def invariant_digest(graph):
    """Everything except node vulnerability records must remain byte-identical."""
    digest = hashlib.sha256()
    digest.update(pickle.dumps(graph.graph, protocol=4))
    for n, data in graph.nodes(data=True):
        attrs = {k: v for k, v in data.items() if k != "node_info_vulnerabilities"}
        digest.update(pickle.dumps((n, attrs), protocol=4))
    for s, t, k, data in graph.edges(keys=True, data=True):
        digest.update(pickle.dumps((s, t, k, data), protocol=4))
    return digest.hexdigest()

def stats(graph):
    return {
        "nodes": len(graph), "edges": graph.number_of_edges(),
        "files": len({d["source_file"] for _, d in graph.nodes(data=True)}),
        "positive_nodes": sum(bool(parse_records(d.get("node_info_vulnerabilities")))
                              for _, d in graph.nodes(data=True)),
        "edge_types": dict(Counter(d["edge_type"] for _, _, d in graph.edges(data=True))),
        "node_types": dict(Counter(d["node_type"] for _, d in graph.nodes(data=True))),
        "token_widths": sorted({len(d["token"]) for _, d in graph.nodes(data=True)}),
    }

def label_changes(graph, targets, evidence):
    changes = []
    metadata_changed = 0
    for n, data in graph.nodes(data=True):
        before = parse_records(data.get("node_info_vulnerabilities"))
        after = targets[n] or []
        if before != after:
            metadata_changed += 1
        if bool(before) != bool(after):
            changes.append({
                "node_id": n, "source_file": data["source_file"], "node_type": data["node_type"],
                "code": data["code"], "before": bool(before), "after": bool(after),
                "before_records": before, "after_records": after, "evidence": evidence[n],
            })
    return changes, metadata_changed

def emit_variant(mode, original, targets, evidence, annotations, output, common, mode_info):
    directory = output / mode
    directory.mkdir()
    frozen = invariant_digest(original)
    result = original.copy()
    changes, metadata_changed = label_changes(original, targets, evidence)
    for n in result:
        result.nodes[n]["node_info_vulnerabilities"] = copy.deepcopy(targets[n])
    if frozen != invariant_digest(result):
        raise AssertionError("Non-label graph attributes changed")
    entries = common["contract_labels"]
    positive_files = {d["source_file"] for _, d in result.nodes(data=True)
                      if parse_records(d.get("node_info_vulnerabilities"))}
    expected = {entry["contract_name"] for entry in entries if entry["targets"] == 1}
    if positive_files != expected:
        raise ValueError("Positive contract set changed; do not silently drop/add contracts: "
                         + repr(sorted(positive_files ^ expected)))
    # Source corpus membership/order comes from the existing graph-label file.
    keep = [n for n, d in result.nodes(data=True) if d["source_file"] in expected]
    line = result.subgraph(keep).copy()
    line = nx.convert_node_labels_to_integers(
        line, ordering="sorted", label_attribute="original_node_id")
    full_path, line_path = directory / "contractlevel.gpickle", directory / "linelevel.gpickle"
    write_graph(result, full_path)
    write_graph(line, line_path)
    # Keep exact graph-label order and bytes: ordering influences train/val splitting.
    (directory / "graph_labels.json").write_bytes(Path(common["contract_labels_path"]).read_bytes())
    for graph, path in [(result, full_path), (line, line_path)]:
        reloaded = read_graph(path)
        if invariant_digest(graph) != invariant_digest(reloaded):
            raise AssertionError("Graph round-trip changed non-label attributes")
        if [parse_records(d.get("node_info_vulnerabilities")) for _, d in graph.nodes(data=True)] != [
            parse_records(d.get("node_info_vulnerabilities")) for _, d in reloaded.nodes(data=True)
        ]:
            raise AssertionError("Graph round-trip changed labels")
    # This is the actual training label reader; no model fitting occurs.
    sys.path.insert(0, str(REPO))
    from sco_models.graph_utils import get_node_label
    actual_labels, _, _ = get_node_label(line)
    intended = [int(bool(parse_records(d.get("node_info_vulnerabilities"))))
                for _, d in line.nodes(data=True)]
    if actual_labels != intended:
        raise AssertionError("Training label consumer disagrees with builder")
    other_category = [n for n, d in line.nodes(data=True)
                      if parse_records(d.get("node_info_vulnerabilities"))
                      and not any(r["category"] == "reentrancy"
                                  for r in parse_records(d["node_info_vulnerabilities"]))]
    write_json(directory / "annotations.json", annotations)
    write_json(directory / "label_changes.json", {
        "binary_changes": len(changes), "record_changes": metadata_changed,
        "counts_by_type": dict(Counter(x["node_type"] for x in changes)), "nodes": changes,
    })
    report = {
        "created_utc": common["created_utc"], "modified_by_ai": "Codex", "mode": mode,
        "settings": mode_info, "input_hashes": common["input_hashes"],
        "contract_level": stats(result), "line_level": stats(line),
        "binary_changes_vs_local_narrow": len(changes),
        "record_changes_vs_local_narrow": metadata_changed,
        "checks": {
            "all_non_label_node_attributes_and_edges_preserved": True,
            "contract_graph_label_file_bytes_and_order_preserved": True,
            "contract_supervised_inputs_changed": False,
            "node_supervised_targets_changed": bool(changes),
            "training_label_reader_matches": True, "round_trip_verified": True,
            "positive_contract_membership_unchanged": True,
        },
        "non_reentrancy_only_positive_line_nodes": other_category,
        "limitations": [
            "Edges and token vectors remain those of the LOCAL narrow graph (7 edge types).",
            "author_compat aligns training labels only, not the entire author graph or inference line policy.",
            "No claim of exact paper F1 reproduction or new independently validated exploit ground truth.",
            "Current training still uses its existing fold generation and best-checkpoint protocol.",
        ],
        "outputs": {str(path.relative_to(HERE)): sha256(path) for path in [
            full_path, line_path, directory / "graph_labels.json", directory / "annotations.json",
            directory / "label_changes.json",
        ]},
    }
    write_json(directory / "manifest.json", report)
    print("{}: full={}/{} line={}/{} positives={} changed={} other-category={}".format(
        mode, len(result), result.number_of_edges(), len(line), line.number_of_edges(),
        report["line_level"]["positive_nodes"], len(changes), len(other_category)), flush=True)
    return report

def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=["both", "author_compat", "source_range"], default="both")
    p.add_argument("--graph", type=Path, default=BASE / "tokenizer_ids_narrow.gpickle")
    p.add_argument("--author-graph", type=Path, default=REPO / (
        "data/upstream_mando_llm/graph_detection/reentrancy_tree_sitter_cfg_cg_compressed_graphs.gpickle"))
    p.add_argument("--contract-labels", type=Path, default=BASE / "graph_labels.json")
    p.add_argument("--source-dir", type=Path, default=BASE / "source_files")
    p.add_argument("--smartbugs", type=Path, default=REPO / "data/smartbug-dataset/vulnerabilities.json")
    p.add_argument("--solidifi-dir", type=Path,
                   default=REPO / "data/SolidiFI-benchmark/buggy_contracts/Re-entrancy")
    p.add_argument("--output", type=Path, default=HERE / "artifacts/labels_v1")
    return p

def main():
    args = parser().parse_args()
    output = args.output.resolve()
    if HERE not in output.parents:
        raise ValueError("All new artifacts must stay inside scripts/labeling_v2")
    if output.exists():
        raise FileExistsError("Refusing overwrite; choose a new --output: " + str(output))
    print("Loading local graph with restricted NetworkX/NumPy reader", flush=True)
    local = read_graph(args.graph)
    files = {d["source_file"] for _, d in local.nodes(data=True)}
    if any(Path(name).name != name for name in files):
        raise ValueError("source_file must be a basename")
    labels = read_json(args.contract_labels)
    if len({x["contract_name"] for x in labels}) != len(labels):
        raise ValueError("Duplicate contract label entries")
    if {x["contract_name"] for x in labels} != files or any(
        x["targets"] not in [0, 1] for x in labels
    ):
        raise ValueError("Graph/contract-label coverage mismatch")
    if sorted(local.nodes()) != list(range(len(local))):
        raise ValueError("Expected existing contiguous integer full-graph node IDs")
    for _, data in local.nodes(data=True):
        if "token" not in data or len(data["token"]) != 512:
            raise ValueError("Every node needs existing 512-wide tokenizer features")
    hashes = {str(args.graph): sha256(args.graph),
              str(args.contract_labels): sha256(args.contract_labels)}
    for path in sorted(HERE.glob("*.py")):
        hashes[str(path)] = sha256(path)
    hashes[str(HERE.parent / "line_mapping.py")] = sha256(HERE.parent / "line_mapping.py")
    for name in sorted(files):
        hashes[str(args.source_dir / name)] = sha256(args.source_dir / name)
    common = {"created_utc": datetime.now(timezone.utc).isoformat(), "input_hashes": hashes,
              "contract_labels": labels, "contract_labels_path": str(args.contract_labels)}
    jobs = []
    if args.mode in ["both", "author_compat"]:
        author = read_graph(args.author_graph)
        targets, evidence, annotations = author_replay(local, author)
        hashes[str(args.author_graph)] = sha256(args.author_graph)
        out_of_bounds = {}
        for name, records in annotations.items():
            pre_count = len(build_line_map((args.source_dir / name).read_text(encoding="utf8")))
            bad = sorted({n for r in records for n in r["lines"] if n > pre_count})
            if bad:
                out_of_bounds[name] = {"preprocessed_line_count": pre_count, "invalid_lines": bad}
        info = {
            "rule": "author endpoints intersect recovered author annotation lines",
            "annotation_coordinate_system": "author_saved_preprocessed_lines",
            "category_filter": None, "all_reference_binary_labels_replayed": True,
            "preserved_author_out_of_bounds_annotations": out_of_bounds,
            "warning": "Compatibility only: retain author anomalies and other categories; not corrected ground truth.",
        }
        jobs.append(("author_compat", targets, evidence, annotations, info))
        print("Author endpoint replay verified for every node; anomalous files: "
              + ", ".join(out_of_bounds), flush=True)
    if args.mode in ["both", "source_range"]:
        annotations, provenance, source_hashes = verified_annotations(
            args.source_dir, files, args.smartbugs, args.solidifi_dir, "reentrancy", read_json)
        hashes.update(source_hashes)
        targets, evidence = source_replay(
            local, annotations, args.source_dir, build_line_map, preprocessed_to_original)
        info = {
            "rule": "local narrow node original-source lines intersect public reentrancy annotations",
            "annotation_coordinate_system": "original_source_lines",
            "category_filter": "reentrancy", "solidifi_interval": "[loc, loc+length-1]",
            "node_span_policy": "preserve existing local narrow spans; end_if is the closing line",
            "dataset_sources_verified": provenance,
            "warning": "Injection intervals are dataset labels, not a manual proof each line is exploitable.",
        }
        jobs.append(("source_range", targets, evidence, annotations, info))
        print("Public annotations verified against local sources (pragma-only edits recorded)", flush=True)
    # Validate all label policies before creating any output graph.
    output.mkdir(parents=True)
    reports = {}
    for mode, targets, evidence, annotations, info in jobs:
        reports[mode] = emit_variant(mode, local, targets, evidence, annotations, output, common, info)
    for path, digest in hashes.items():
        if sha256(Path(path)) != digest:
            raise AssertionError("Input changed during the build: " + path)
    summary = {
        "modified_by_ai": "Codex", "created_utc": common["created_utc"],
        "all_input_hashes_unchanged": True, "variants": {
            name: {"full": r["contract_level"], "line": r["line_level"],
                   "binary_changes": r["binary_changes_vs_local_narrow"]} for name, r in reports.items()},
    }
    write_json(output / "summary.json", summary)
    print("DONE: " + str(output / "summary.json"), flush=True)

if __name__ == "__main__":
    main()
