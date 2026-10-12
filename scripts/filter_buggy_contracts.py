"""Keep only the buggy contracts, which is what the line-level task trains on.

mando-llm.md section 16 and appendix A separate the two phases' data:

  Contract-level : Clean : Buggy = 1 : 1
  Line-level     : 不使用 clean contracts

Phase 2 localises vulnerable statements inside contracts already known to be
vulnerable, so the clean half of the corpus does not belong in it. Everything run so
far used all 142 contracts, which both dilutes the positive rate and lets the folds
contain contracts that can never contribute a positive node.

A contract counts as buggy when at least one of its nodes carries
node_info_vulnerabilities, which is the same criterion build_labeled_graph reports on.
Node ids are renumbered so the result is a contiguous graph again.
"""
import argparse
from collections import Counter
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--graph", required=True)
    p.add_argument("--output", required=True)
    return p


def main():
    args = build_parser().parse_args()
    g = nx.read_gpickle(args.graph)
    print(f"input : {args.graph}")
    print(f"        {g.number_of_nodes()} nodes / {g.number_of_edges()} edges")

    buggy_files = {
        d["source_file"] for _, d in g.nodes(data=True) if d.get("node_info_vulnerabilities")
    }
    all_files = {d["source_file"] for _, d in g.nodes(data=True)}
    print(f"        {len(all_files)} contracts, {len(buggy_files)} buggy")

    keep = [n for n, d in g.nodes(data=True) if d["source_file"] in buggy_files]
    sub = g.subgraph(keep).copy()
    sub = nx.convert_node_labels_to_integers(sub, ordering="sorted",
                                             label_attribute="original_node_id")

    n_buggy = sum(1 for _, d in sub.nodes(data=True) if d.get("node_info_vulnerabilities"))
    total = sub.number_of_nodes()
    print(f"output: {total} nodes / {sub.number_of_edges()} edges")
    print(f"        buggy nodes {n_buggy}/{total} ({100.0 * n_buggy / total:.2f}%)")

    etypes = Counter(d.get("edge_type") for _, _, d in sub.edges(data=True))
    print(f"        edge types: {dict(etypes)}")
    ntypes = Counter(d.get("node_type") for _, d in sub.nodes(data=True))
    print(f"        node types: {len(ntypes)}")

    has_token = sum(1 for _, d in sub.nodes(data=True) if d.get("token") is not None)
    if has_token:
        width = len(next(d["token"] for _, d in sub.nodes(data=True) if d.get("token") is not None))
        print(f"        nodes carrying 'token': {has_token} (width {width})")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    nx.write_gpickle(sub, str(out))
    print(f"wrote -> {out}")


if __name__ == "__main__":
    main()
