"""Line-level input = the fused graph restricted to the contracts LABELLED buggy.

Selection uses the contract-level label file, not "has a vulnerable node": a buggy
contract whose nodes are all clean (e.g. parity_wallet_bug_2.sol under author labels)
stays in, which is how the authors' own line-level artefacts were built.

    python -B Test_code/labeling_v3/make_linelevel.py --graph G.gpickle --contract_labels L.json --output OUT.gpickle
"""
import argparse
import ast
import json
import pickle
from pathlib import Path

import networkx as nx


def positive(data):
    value = data.get("node_info_vulnerabilities")
    for _ in range(3):
        if not isinstance(value, str):
            break
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            break
    return isinstance(value, list)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--graph", required=True)
    p.add_argument("--contract_labels", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    out = Path(args.output)
    if out.exists():
        raise SystemExit(f"refusing to overwrite {out}")
    with open(args.graph, "rb") as handle:
        graph = pickle.load(handle)
    buggy = {c["contract_name"] for c in json.load(open(args.contract_labels)) if int(c["targets"]) == 1}
    keep = [n for n, d in graph.nodes(data=True) if d["source_file"] in buggy]
    sub = nx.convert_node_labels_to_integers(graph.subgraph(keep).copy(), ordering="sorted")
    files = {d["source_file"] for _, d in sub.nodes(data=True)}
    if files != buggy:
        raise SystemExit(f"buggy contracts missing from the graph: {sorted(buggy - files)[:5]}")
    with open(out, "wb") as handle:
        pickle.dump(sub, handle, protocol=4)
    print(f"{out}: contracts {len(files)} nodes {sub.number_of_nodes()} edges {sub.number_of_edges()} "
          f"vulnerable nodes {sum(positive(d) for _, d in sub.nodes(data=True))}")


if __name__ == "__main__":
    main()
