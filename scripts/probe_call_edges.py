"""Measure how much call-graph structure the tree-sitter path currently loses.

The paper builds Heterogeneous Contract Graphs by fusing a control-flow graph with a
call graph, and the HGT then learns per-meta-relation attention over
(source_type, edge_type, target_type) triples. CFG_solidity.py does add call edges
(add_function_call_edges / add_dummy_edges), but every one of them is emitted as
'next' with the typed variants commented out, and the 'external_function' nodes it
creates carry a label with no line numbers, so _annotate_cfg_graph deletes them.

This compares the raw CFGDriver graph against the annotated one to quantify both.
"""
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from process_graphs.tree_sitter_codeviews.codeviews.CFG.CFG_driver import CFGDriver  # noqa: E402
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_file  # noqa: E402

SRC = REPO / "experiments/ge-sc-data/source_code/reentrancy/source_files"
SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else 40

raw_nodes = Counter()
raw_edges = Counter()
ann_nodes = Counter()
ann_edges = Counter()
dropped_total = 0

import contextlib, io  # noqa: E402

files = sorted(SRC.glob("*.sol"))[:SAMPLE]
for path in files:
    source = path.read_text(encoding="utf8", errors="ignore")
    with contextlib.redirect_stdout(io.StringIO()):
        raw = CFGDriver("solidity", source, output_file=None).graph
        ann = generate_cfg_from_file(path)

    for _, d in raw.nodes(data=True):
        raw_nodes[d.get("node_type")] += 1
    for _, _, d in raw.edges(data=True):
        raw_edges[d.get("edge_type")] += 1
    for _, d in ann.nodes(data=True):
        ann_nodes[d.get("node_type")] += 1
    for _, _, d in ann.edges(data=True):
        ann_edges[d.get("edge_type")] += 1
    dropped_total += raw.number_of_nodes() - ann.number_of_nodes()

print(f"sampled {len(files)} contracts")
print(f"raw nodes {sum(raw_nodes.values())} -> annotated {sum(ann_nodes.values())} "
      f"(dropped {dropped_total})")
print(f"raw edges {sum(raw_edges.values())} -> annotated {sum(ann_edges.values())}")

print("\nnode types dropped by _annotate_cfg_graph:")
for t in sorted(set(raw_nodes) | set(ann_nodes), key=lambda x: (x is None, str(x))):
    lost = raw_nodes[t] - ann_nodes[t]
    flag = "  <-- ALL LOST" if ann_nodes[t] == 0 and raw_nodes[t] else ""
    if lost:
        print(f"  {str(t):24s} raw={raw_nodes[t]:5d}  kept={ann_nodes[t]:5d}  lost={lost}{flag}")

print("\nedge types (raw):")
for t, n in raw_edges.most_common():
    print(f"  {str(t):24s} {n}")
print("\nedge types (annotated):")
for t, n in ann_edges.most_common():
    print(f"  {str(t):24s} {n}")
