"""Spell out the difference between the two line-level graphs, and which is which.

Both were produced by the same pipeline; the only thing that changed between them is
how wide an end_if node's line span is, which changes only that node type's labels.
"""
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

BASE = Path(__file__).resolve().parents[1] / "experiments/ge-sc-data/source_code/reentrancy"
FILES = {
    "linelevel_tokenizer_ids.gpickle": "end_if spans the WHOLE if statement",
    "linelevel_narrow.gpickle": "end_if spans only its CLOSING line",
}
PAPER_BUGGY = 6570

rows = []
for name, note in FILES.items():
    p = BASE / name
    if not p.exists():
        print(f"{name}: MISSING")
        continue
    g = nx.read_gpickle(str(p))
    buggy = Counter()
    total = Counter()
    for _, d in g.nodes(data=True):
        t = d.get("node_type")
        total[t] += 1
        if d.get("node_info_vulnerabilities"):
            buggy[t] += 1
    nb = sum(buggy.values())
    rows.append((name, note, g.number_of_nodes(), g.number_of_edges(), nb,
                 buggy["end_if"], total["end_if"], buggy["if"]))

print(f"{'file':34s} {'nodes':>6s} {'edges':>6s} {'buggy':>6s} "
      f"{'delta vs paper':>15s} {'end_if buggy':>13s} {'if buggy':>9s}")
for name, note, n, e, nb, eib, eit, ifb in rows:
    print(f"{name:34s} {n:6d} {e:6d} {nb:6d} {nb - PAPER_BUGGY:+15d} "
          f"{eib:8d}/{eit:<4d} {ifb:9d}")
print()
for name, note, *_ in rows:
    print(f"  {name:34s} {note}")

print(f"\npaper appendix C (reentrancy): 18,312 nodes / 19,267 edges (full graph), "
      f"{PAPER_BUGGY} buggy nodes")
print("line-level graphs above are the buggy-contracts-only subgraph of that, so their")
print("node/edge totals are smaller; the buggy count is the comparable figure.")

# are the two graphs otherwise identical?
if len(rows) == 2:
    ga = nx.read_gpickle(str(BASE / rows[0][0]))
    gb = nx.read_gpickle(str(BASE / rows[1][0]))
    same_nodes = ga.number_of_nodes() == gb.number_of_nodes()
    same_edges = ga.number_of_edges() == gb.number_of_edges()
    diff_labels = sum(
        1 for n in ga.nodes()
        if bool(ga.nodes[n].get("node_info_vulnerabilities"))
        != bool(gb.nodes[n].get("node_info_vulnerabilities"))
    )
    diff_types = sum(
        1 for n in ga.nodes()
        if ga.nodes[n].get("node_type") != gb.nodes[n].get("node_type")
    )
    print(f"\nsame node count: {same_nodes}   same edge count: {same_edges}")
    print(f"nodes whose buggy label differs between the two: {diff_labels}")
    print(f"nodes whose node_type differs: {diff_types}")
