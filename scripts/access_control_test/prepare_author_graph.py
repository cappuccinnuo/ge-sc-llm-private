"""Re-pickle the authors' access_control HCG at protocol 4 for the Python 3.7 trainers.

Same container-only conversion scripts/convert_upstream_graphs.py does for reentrancy:
the Google Drive gpickle is protocol 5, which Python 3.7 cannot read. The fingerprint
check at the end confirms the graph content is unchanged.
"""
import argparse
import pickle
from collections import Counter
from pathlib import Path

import networkx as nx
import pickle5

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "data/upstream_mando_llm/graph_detection/access_control_tree_sitter_cfg_cg_compressed_graphs.gpickle"


def fingerprint(g):
    return (
        g.number_of_nodes(),
        g.number_of_edges(),
        tuple(sorted(Counter(d.get("node_type") for _, d in g.nodes(data=True)).items())),
        tuple(sorted(Counter(d.get("edge_type") for _, _, d in g.edges(data=True)).items())),
        sum(1 for _, d in g.nodes(data=True) if d.get("node_info_vulnerabilities")),
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    out = Path(args.output)
    if out.exists():
        raise SystemExit(f"refusing to overwrite {out}")
    with open(SOURCE, "rb") as f:
        g = pickle5.load(f)
    before = fingerprint(g)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump(g, f, protocol=4)
    after = fingerprint(nx.read_gpickle(str(out)))
    print(f"nodes {before[0]}  edges {before[1]}  buggy nodes {before[4]}")
    print(f"round-trip identical: {before == after}")
    if before != after:
        raise SystemExit("conversion changed the graph - stop and investigate")


if __name__ == "__main__":
    main()
