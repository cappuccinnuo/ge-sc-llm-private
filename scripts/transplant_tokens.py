"""Copy LLM embeddings from an already-encoded graph onto a rebuilt one.

Restoring the call-edge types changed only edge attributes: the node set, their
order, their code and their line spans are untouched. Re-running a 26-minute encode
to reproduce identical vectors would be wasteful, but transplanting is only safe if
the two graphs really do line up, so every node is checked on source_file, code and
node_source_code_lines before anything is copied. Any mismatch aborts.
"""
import argparse
import sys
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", required=True, help="Graph that already carries node['token']")
    p.add_argument("--target", required=True, help="Rebuilt graph to receive the embeddings")
    p.add_argument("--output", required=True)
    return p


def key(data):
    return (
        data.get("source_file"),
        data.get("code"),
        tuple(data.get("node_source_code_lines") or ()),
        data.get("node_type"),
    )


def main():
    args = build_parser().parse_args()
    src = nx.read_gpickle(args.source)
    dst = nx.read_gpickle(args.target)

    print(f"source: {src.number_of_nodes()} nodes / {src.number_of_edges()} edges")
    print(f"target: {dst.number_of_nodes()} nodes / {dst.number_of_edges()} edges")

    if src.number_of_nodes() != dst.number_of_nodes():
        raise SystemExit("node counts differ - re-encode instead of transplanting")

    src_nodes = list(src.nodes())
    dst_nodes = list(dst.nodes())

    mismatches = 0
    for i, (sn, dn) in enumerate(zip(src_nodes, dst_nodes)):
        if key(src.nodes[sn]) != key(dst.nodes[dn]):
            mismatches += 1
            if mismatches <= 3:
                print(f"  mismatch at position {i}:")
                print(f"    source: {key(src.nodes[sn])}")
                print(f"    target: {key(dst.nodes[dn])}")
    if mismatches:
        raise SystemExit(f"{mismatches} nodes do not line up - re-encode instead")
    print("all nodes line up on (source_file, code, lines, node_type)")

    missing = 0
    for sn, dn in zip(src_nodes, dst_nodes):
        token = src.nodes[sn].get("token")
        if token is None:
            missing += 1
            continue
        dst.nodes[dn]["token"] = token
    if missing:
        raise SystemExit(f"{missing} source nodes had no token")

    dim = len(dst.nodes[dst_nodes[0]]["token"])
    print(f"transplanted {len(dst_nodes)} embeddings of dim {dim}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    nx.write_gpickle(dst, str(out))
    print(f"wrote -> {out}")


if __name__ == "__main__":
    main()
