"""Explain why some annotated contracts produce zero buggy nodes.

For each contract that carries an annotation but whose merged graph has no node
labelled buggy, print the annotated lines alongside the line ranges the CFG nodes
actually cover, so the gap is visible.
"""
import json
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]
MISSED = [
    "etherbank.sol", "etherstore.sol", "reentrance.sol", "reentrancy_bonus.sol",
    "reentrancy_cross_function.sol", "reentrancy_insecure.sol",
    "reentrancy_simple.sol", "simple_dao.sol",
]

vulns = json.load(open("/tmp/reentrancy_vulnerabilities.json"))
by_name = {v["name"]: v["vulnerabilities"] for v in vulns}
SRC = REPO / "experiments/ge-sc-data/source_code/reentrancy/source_files"

for name in MISSED:
    stem = Path(name).stem
    gp = Path("/tmp/reentrancy_cfg_regen") / f"{stem}.gpickle"
    g = nx.read_gpickle(gp)
    ann = by_name.get(name, [])
    ann_lines = sorted({l for v in ann for l in v["lines"]})

    covered = set()
    ranges = []
    for _, d in g.nodes(data=True):
        lines = d.get("node_source_code_lines") or []
        covered |= set(lines)
        if lines:
            ranges.append((min(lines), max(lines), d.get("node_type")))
    ranges.sort()

    print("=" * 72)
    print(f"{name}")
    print(f"  annotated lines : {ann_lines}")
    print(f"  covered lines   : {sorted(covered)}")
    print(f"  gap (annotated but uncovered): {sorted(set(ann_lines) - covered)}")
    print(f"  node ranges     : {ranges}")

    src = (SRC / name).read_text(encoding="utf8", errors="ignore").splitlines()
    for l in ann_lines:
        text = src[l - 1].strip() if 0 < l <= len(src) else "<out of range>"
        print(f"    line {l}: {text}")
