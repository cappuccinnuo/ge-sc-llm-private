"""Summarize the regenerated reentrancy CFG corpus.

Reports totals, node/edge type distributions, and coverage of the attributes the
downstream MANDO-LLM pipeline depends on (source_file, node_source_code_lines,
code -> needed for LLM token encoding).
"""
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

REGEN_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/reentrancy_cfg_regen")

node_types = Counter()
edge_types = Counter()
total_nodes = 0
total_edges = 0
graphs = 0
missing_code = 0
missing_source_file = 0
missing_lines = 0
empty_graphs = []

for gp in sorted(REGEN_DIR.glob("*.gpickle")):
    g = nx.read_gpickle(gp)
    graphs += 1
    total_nodes += g.number_of_nodes()
    total_edges += g.number_of_edges()
    if g.number_of_nodes() == 0:
        empty_graphs.append(gp.stem)
    for _, d in g.nodes(data=True):
        node_types[d.get("node_type", "<none>")] += 1
        if not d.get("code"):
            missing_code += 1
        if not d.get("source_file"):
            missing_source_file += 1
        if not d.get("node_source_code_lines"):
            missing_lines += 1
    for _, _, d in g.edges(data=True):
        edge_types[d.get("edge_type", "<none>")] += 1

print(f"graphs           : {graphs}")
print(f"total nodes      : {total_nodes}")
print(f"total edges      : {total_edges}")
print(f"empty graphs     : {len(empty_graphs)} {empty_graphs[:10]}")
print()
print(f"nodes missing 'code'              : {missing_code}")
print(f"nodes missing 'source_file'       : {missing_source_file}")
print(f"nodes missing 'node_source_code_lines': {missing_lines}")
print()
print("node_type distribution:")
for k, v in node_types.most_common():
    print(f"  {k:35s} {v}")
print()
print("edge_type distribution:")
for k, v in edge_types.most_common():
    print(f"  {k:35s} {v}")
