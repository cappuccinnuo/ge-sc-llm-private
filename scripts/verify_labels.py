"""Spot-check that labels landed on the right nodes after line translation."""
import sys
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]
GRAPH = REPO / "experiments/ge-sc-data/source_code/reentrancy/cfg_compressed_graphs.gpickle"
TARGETS = sys.argv[1:] or ["reentrancy_insecure.sol", "etherbank.sol", "buggy_20.sol"]

g = nx.read_gpickle(str(GRAPH))
for target in TARGETS:
    print("=" * 78)
    print(target)
    rows = []
    for _, d in g.nodes(data=True):
        if d.get("source_file") != target:
            continue
        code = (d.get("code") or "").splitlines()
        rows.append((
            d.get("node_source_code_lines_original") or [],
            "BUGGY" if d.get("node_info_vulnerabilities") else "clean",
            d.get("node_source_code_lines"),
            d.get("node_type"),
            code[0][:58] if code else "",
        ))
    rows.sort(key=lambda r: (r[0] or [0])[0])
    for orig, flag, pre, ntype, snippet in rows:
        print(f"  {flag:6s} orig={str(orig):20s} pre={str(pre):14s} {ntype:22s} {snippet}")
