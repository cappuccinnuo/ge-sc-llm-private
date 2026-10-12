"""Label a LOCALLY built fused graph with author_rule.py and write it to a new file.

Only node_info_vulnerabilities is rewritten; nodes, edges, code and any token feature
are left as they are. With --compare the result is aligned node-by-node with the
authors' published graph of the same bug type and the label differences are counted.

    python -B Test_code/labeling_v3/label_local_graph.py --bug_type reentrancy \
        --graph experiments/ge-sc-data/source_code/reentrancy/hcg_narrow.gpickle \
        --contract_labels experiments/ge-sc-data/source_code/reentrancy/graph_labels.json \
        --mode author --output Test_code/labeling_v3/artifacts/reentrancy/hcg_author.gpickle --compare
"""
import argparse
import ast
import json
import pickle
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import author_rule as rule  # noqa: E402

REPO = rule.REPO
sys.path.insert(0, str(REPO / "scripts/labeling_v2"))


def lit(value):
    for _ in range(3):
        if not isinstance(value, str):
            break
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            break
    return value


def is_positive(data):
    return isinstance(lit(data.get("node_info_vulnerabilities")), list)


def relabel(graph, bug_type, targets, source_dir, mode):
    by_file = {}
    for node, data in graph.nodes(data=True):
        ends = rule.node_endpoints(data["label"], data["node_type"])
        if ends is None:
            raise ValueError(f"cannot derive endpoints for node {node}: {data['label']!r}")
        by_file.setdefault(data["source_file"], {})[node] = ends
    missing = sorted(set(by_file) - set(targets))
    if missing:
        raise ValueError(f"contracts without a contract-level label: {missing[:5]}")
    stats = Counter()
    for name, nodes in by_file.items():
        if targets[name] == 1:
            source = (Path(source_dir) / name).read_text(encoding="utf8")
            labels = rule.label_nodes(nodes, rule.annotate_file(bug_type, name, source, mode=mode))
            if not any(labels.values()):
                stats["buggy contracts without any vulnerable node"] += 1
        else:
            labels = dict.fromkeys(nodes)
        for node, hit in labels.items():
            graph.nodes[node]["node_info_vulnerabilities"] = hit
            stats["vulnerable nodes"] += bool(hit)
    return stats


def compare_with_author(local, bug_type):
    import pickle5
    from label_rules import align_graphs
    author = pickle5.load(open(
        REPO / f"data/upstream_mando_llm/graph_detection/{bug_type}_tree_sitter_cfg_cg_compressed_graphs.gpickle", "rb"))
    mapping = align_graphs(local, author)  # raises unless nodes and untyped edges correspond 1:1
    differing = Counter()
    for node, ref in mapping.items():
        if is_positive(local.nodes[node]) != is_positive(author.nodes[ref]):
            differing[local.nodes[node]["source_file"]] += 1
    return {"aligned_nodes": len(mapping), "author_vulnerable_nodes": sum(is_positive(d) for _, d in author.nodes(data=True)),
            "nodes_with_different_label": sum(differing.values()), "files": dict(differing)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bug_type", required=True, choices=rule.BUG_TYPES)
    p.add_argument("--graph", required=True)
    p.add_argument("--contract_labels", required=True)
    p.add_argument("--source_dir", default=None)
    p.add_argument("--mode", choices=("clean", "author"), default="clean")
    p.add_argument("--output", required=True)
    p.add_argument("--compare", action="store_true")
    args = p.parse_args()

    out = Path(args.output)
    if out.exists():
        raise SystemExit(f"refusing to overwrite {out}")
    source_dir = args.source_dir or REPO / f"experiments/ge-sc-data/source_code/{args.bug_type}/source_files"
    with open(args.graph, "rb") as handle:
        graph = pickle.load(handle)
    targets = {c["contract_name"]: int(c["targets"]) for c in json.load(open(args.contract_labels))}
    before = sum(is_positive(d) for _, d in graph.nodes(data=True))
    stats = relabel(graph, args.bug_type, targets, source_dir, args.mode)
    print(f"{args.bug_type} [{args.mode}] nodes {graph.number_of_nodes()} edges {graph.number_of_edges()} "
          f"vulnerable nodes {before} -> {stats['vulnerable nodes']}  {dict(stats)}")
    if args.compare:
        print("   vs author graph:", compare_with_author(graph, args.bug_type))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as handle:
        pickle.dump(graph, handle, protocol=4)
    print("   wrote", out)


if __name__ == "__main__":
    main()
