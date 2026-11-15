"""Build one category's training graphs from raw .sol, end to end.

The stages reproduce the documented reentrancy rebuild (HANDOVER.md section 3)
for any category:

  1 cfg      tree-sitter CFG + call edges per contract   (gen_reentrancy_cfg.py)
  2 label    disjoint_union in sorted order + line labels (build_labeled_graph.py)
  3 labels   contract-level graph_labels.json            (make_graph_labels.py)
  4 line     buggy-contracts-only line-level graph        (filter_buggy_contracts.py)
  5 tokens   512-wide tokenizer features, optional        (encode_tokenizer_features.py)

The original scripts are NOT modified: sealed DFG/node-sem/edge-sem manifests pin
their SHA-256, and scripts/edge_sem/hgt_edge.py refuses to import if
sco_models/model_hgt.py changes. Their pure helpers are imported unchanged; only
the per-script loops are re-expressed here, with networkx-3-safe pickle I/O. The
--check counts (paper Table 1 for all seven categories, plus an identical
reentrancy graph_labels.json) establish that the two paths agree.

Outputs land next to the category's source_files/ with the names the training
commands already use:

  hcg_compressed_graphs.gpickle                              contract level, nodetype
  graph_labels.json
  linelevel_hcg.gpickle                                      line level, nodetype
  tokenizer_<scheme>_<tok>_hcg_compressed_graphs.gpickle     contract level, tokens
  linelevel_tokenizer_<scheme>.gpickle                       line level, tokens
  build_report.json                                          counts and provenance
"""
import json
import os
import platform
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO, REPO / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from scripts.build_labeled_graph import (  # noqa: E402
    get_vulnerabilities,
    get_vulnerabilities_of_node_by_source_code_line,
    normalize_smartbugs,
    solidifi_buglogs_to_records,
)
from scripts.graph_build.nx_io import read_gpickle, write_gpickle  # noqa: E402
from scripts.line_mapping import build_line_map, preprocessed_to_original  # noqa: E402

DATASET_ROOT = REPO / "experiments/ge-sc-data/source_code"


def grammar_dir():
    """Per-platform directory for the compiled tree-sitter grammar.

    process_graphs/tree_sitter_codeviews/build/my-languages.so in git is a macOS
    arm64 binary that cannot load on Linux. The old machine used
    TREE_SITTER_LIB_DIR=<repo>/build/linux-x86_64 (git-ignored); this keeps that
    convention for every platform. custom_parser compiles the grammar there from
    vendor/tree-sitter-solidity on first use (needs a C compiler).
    """
    return REPO / "build" / f"{sys.platform}-{platform.machine().lower()}"


def use_platform_grammar():
    os.environ.setdefault("TREE_SITTER_LIB_DIR", str(grammar_dir()))


# ---------------------------------------------------------------- stages 1-4 ---
def generate_cfgs(source_dir, cfg_dir):
    """Stage 1. Per-contract graphs as .gpickle; returns [(file, error)] failures."""
    use_platform_grammar()
    from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_file

    cfg_dir.mkdir(parents=True, exist_ok=True)
    failed = []
    for sol in sorted(Path(source_dir).glob("*.sol")):
        try:
            graph = generate_cfg_from_file(sol)
        except Exception as exc:  # noqa: BLE001 - report every failure, keep going
            failed.append((sol.name, repr(exc)))
            continue
        write_gpickle(graph, cfg_dir / f"{sol.stem}.gpickle")
    return failed


def load_annotations(label_root, category, solidifi_lines="range"):
    """SmartBugs records + converted SolidiFI BugLogs, as build_labeled_graph.main()."""
    smartbugs = normalize_smartbugs(json.loads(
        (Path(label_root) / "smartbug-dataset/vulnerabilities.json").read_text()))
    solidifi = solidifi_buglogs_to_records(
        Path(label_root) / "SolidiFI-benchmark/buggy_contracts" / category.solidifi_dir,
        category.name, line_mode=solidifi_lines)
    return smartbugs, solidifi


def merge_and_label(corpus, cfg_dir, source_dir, vulnerabilities):
    """Stage 2. Same order, union and labelling as build_labeled_graph.main()."""
    merged, missing = None, []
    for name in corpus:
        gp = Path(cfg_dir) / f"{Path(name).stem}.gpickle"
        if not gp.exists():
            missing.append(name)
            continue
        g = read_gpickle(gp)
        merged = g.copy() if merged is None else nx.disjoint_union(merged, g)
    if merged is None:
        raise SystemExit(f"no graphs found under {cfg_dir}")

    # node_source_code_lines index the comment/blank-stripped source tree-sitter
    # parsed; annotations use original file lines, so translate before matching.
    per_file_vulns, per_file_linemap = {}, {}
    buggy_nodes, empty_line_nodes, buggy_files = 0, 0, set()
    for _, nd in merged.nodes(data=True):
        source_file = nd.get("source_file")
        if source_file not in per_file_vulns:
            per_file_vulns[source_file] = get_vulnerabilities(source_file, vulnerabilities)
            sol = Path(source_dir) / source_file
            per_file_linemap[source_file] = (
                build_line_map(sol.read_text(encoding="utf8", errors="ignore"))
                if sol.exists() else [])
        pre_lines = nd.get("node_source_code_lines") or []
        if not pre_lines:
            empty_line_nodes += 1
        orig_lines = preprocessed_to_original(pre_lines, per_file_linemap[source_file])
        nd["node_source_code_lines_original"] = orig_lines
        info = get_vulnerabilities_of_node_by_source_code_line(
            orig_lines, per_file_vulns[source_file])
        nd["node_info_vulnerabilities"] = info
        if info:
            buggy_nodes += 1
            buggy_files.add(source_file)

    spread = Counter(v.get("category") for _, nd in merged.nodes(data=True)
                     for v in (nd.get("node_info_vulnerabilities") or []))
    annotated = {f for f, v in per_file_vulns.items() if v}
    stats = {
        "contracts": len(per_file_vulns),
        "annotated_contracts": len(annotated),
        "buggy_contracts": len(buggy_files),
        "annotated_but_no_node_hit": sorted(annotated - buggy_files),
        "nodes": merged.number_of_nodes(),
        "edges": merged.number_of_edges(),
        "buggy_nodes": buggy_nodes,
        "empty_line_nodes": empty_line_nodes,
        "category_spread": dict(spread.most_common()),
        "missing_graphs": missing,
    }
    return merged, stats


def graph_label_entries(g):
    """Stage 3. A contract is buggy when any node has node_info_vulnerabilities."""
    buggy = {}
    for _, d in g.nodes(data=True):
        buggy[d["source_file"]] = buggy.get(d["source_file"], False) or bool(
            d.get("node_info_vulnerabilities"))
    return [{"contract_name": n, "targets": int(buggy[n])} for n in sorted(buggy)]


def filter_buggy(g):
    """Stage 4. Buggy contracts only, relabelled 0..n-1 in sorted node order."""
    buggy_files = {d["source_file"] for _, d in g.nodes(data=True)
                   if d.get("node_info_vulnerabilities")}
    keep = [n for n, d in g.nodes(data=True) if d["source_file"] in buggy_files]
    return nx.convert_node_labels_to_integers(g.subgraph(keep).copy(), ordering="sorted",
                                              label_attribute="original_node_id")


# ------------------------------------------------------------------- stage 5 ---
def tokenizer_pad_and_vocab(tokenizer):
    vocab_size = getattr(tokenizer, "vocab_size", None) or len(tokenizer)
    pad_id = tokenizer.pad_token_id
    if pad_id is None:
        pad_id = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else 0
    return pad_id, vocab_size


def encode_tokens(g, tokenizer, scheme="ids", feature_size=512):
    """Stage 5. node["token"] exactly as encode_tokenizer_features.main() writes it."""
    from scripts.encode_tokenizer_features import encode_hashed_bow, encode_ids

    pad_id, vocab_size = tokenizer_pad_and_vocab(tokenizer)
    lengths, truncated = [], 0
    for node_id in g.nodes():
        ids = tokenizer(g.nodes[node_id].get("code") or "", add_special_tokens=True).input_ids
        lengths.append(len(ids))
        truncated += len(ids) > feature_size
        if scheme == "hashed_bow":
            vec = encode_hashed_bow(ids, feature_size)
        elif scheme == "ids_norm":
            vec = encode_ids(ids, feature_size, pad_id) / float(vocab_size)
        else:
            vec = encode_ids(ids, feature_size, pad_id)
        g.nodes[node_id]["token"] = vec
    return {"scheme": scheme, "feature_size": feature_size, "vocab_size": vocab_size,
            "pad_id": pad_id, "truncated_nodes": int(truncated),
            "max_length": max(lengths) if lengths else 0}


# ------------------------------------------------------------------- driver ---
def build_category(category, label_root, out_root=DATASET_ROOT, work_root=None,
                   tokenizer=None, tokenizer_name=None, scheme="ids", feature_size=512,
                   solidifi_lines="range", dataset_root=DATASET_ROOT, log=print):
    """Run stages 1-5 for one Category; return the build report dict.

    label_root holds smartbug-dataset/ and SolidiFI-benchmark/
    (scripts/graph_build/fetch_labels.sh). dataset_root holds
    <category>/source_files/. tokenizer is a loaded HuggingFace tokenizer, or None
    to skip stage 5.
    """
    source_dir = Path(dataset_root) / category.name / "source_files"
    out_dir = Path(out_root) / category.name
    cfg_dir = (Path(work_root) / category.name if work_root else out_dir / "_build") / "cfg"
    out_dir.mkdir(parents=True, exist_ok=True)
    corpus = sorted(p.name for p in source_dir.glob("*.sol"))

    log(f"[{category.name}] 1/5 cfg: {len(corpus)} contracts")
    failed = generate_cfgs(source_dir, cfg_dir)

    log(f"[{category.name}] 2/5 label")
    smartbugs, solidifi = load_annotations(label_root, category, solidifi_lines)
    merged, stats = merge_and_label(corpus, cfg_dir, source_dir, smartbugs + solidifi)
    write_gpickle(merged, out_dir / "hcg_compressed_graphs.gpickle")

    log(f"[{category.name}] 3/5 graph_labels.json")
    entries = graph_label_entries(merged)
    (out_dir / "graph_labels.json").write_text(json.dumps(entries, indent=2), encoding="utf8")

    log(f"[{category.name}] 4/5 line-level subset")
    line_graph = filter_buggy(merged)
    write_gpickle(line_graph, out_dir / "linelevel_hcg.gpickle")

    report = {
        "category": category.name,
        "solidifi_dir": category.solidifi_dir,
        "solidifi_lines": solidifi_lines,
        "corpus_contracts": len(corpus),
        "parse_failures": failed,
        "annotation_records": {"smartbugs": len(smartbugs), "solidifi": len(solidifi)},
        "contract_level": stats,
        "graph_labels": {"buggy": sum(e["targets"] for e in entries),
                         "clean": sum(1 - e["targets"] for e in entries)},
        "line_level": {"nodes": line_graph.number_of_nodes(),
                       "edges": line_graph.number_of_edges()},
        "environment": {"python": platform.python_version(), "networkx": nx.__version__},
        "tokens": None,
    }

    if tokenizer is not None:
        log(f"[{category.name}] 5/5 tokenizer features ({tokenizer_name}, {scheme})")
        report["tokens"] = dict(encode_tokens(merged, tokenizer, scheme, feature_size),
                                tokenizer=tokenizer_name)
        tag = tokenizer_name.split("/")[-1]
        write_gpickle(merged, out_dir / f"tokenizer_{scheme}_{tag}_hcg_compressed_graphs.gpickle")
        write_gpickle(filter_buggy(merged), out_dir / f"linelevel_tokenizer_{scheme}.gpickle")
    else:
        log(f"[{category.name}] 5/5 tokenizer features skipped")

    (out_dir / "build_report.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    return report


def check_expected(report, expected):
    """Mismatches between a build report and {metric: value}, as strings."""
    cl = report["contract_level"]
    got = {
        "contracts": cl["contracts"],
        "buggy_contracts": cl["buggy_contracts"],
        "nodes": cl["nodes"],
        "edges": cl["edges"],
        "buggy_nodes": cl["buggy_nodes"],
        "line_nodes": report["line_level"]["nodes"],
    }
    return [f"{k}: expected {v}, got {got[k]}" for k, v in expected.items() if got[k] != v]
