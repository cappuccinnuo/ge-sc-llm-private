"""Search for a labelling rule that reproduces appendix C's 6,570 buggy nodes.

We currently mark a node buggy when its line span intersects an annotated line at all
(the rule ported from ge-sc). That yields 6,978, which is 408 too many. Rather than
subtracting node types until the arithmetic works, this enumerates alternative rules
that each have an independent justification, and reports what every one of them gives.
A rule that lands on 6,570 is evidence; one that merely gets close is not.

Rules tried:
  intersect        current behaviour: any overlap counts
  no_container     intersect, but declaration-style nodes never get a label
  first_line       the annotated line must be the node's FIRST line
  contained        the node must sit entirely inside the annotated range
  span_le_K        intersect, but only for nodes spanning at most K lines
  reentrancy_only  intersect, but only annotations whose category is reentrancy
"""
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "experiments/ge-sc-data/source_code/reentrancy"
GRAPH = BASE / "hcg_narrow.gpickle"
TARGET = 6570

CONTAINER = {"contract_declaration", "function_definition", "library_declaration",
             "interface_declaration", "modifier_definition", "constructor_definition",
             "struct_declaration"}

g = nx.read_gpickle(str(GRAPH))
print(f"graph: {GRAPH.name}  {g.number_of_nodes()} nodes")

nodes = []
for n, d in g.nodes(data=True):
    lines = d.get("node_source_code_lines_original") or []
    vulns = d.get("node_info_vulnerabilities") or []
    nodes.append({
        "type": d.get("node_type"),
        "lines": set(lines),
        "first": min(lines) if lines else None,
        "vulns": vulns,
    })

# the annotated lines that actually reached this node, per node
def ann_lines(rec):
    out = set()
    for v in rec["vulns"]:
        out |= set(v["lines"])
    return out


def ann_lines_cat(rec, category):
    out = set()
    for v in rec["vulns"]:
        if v.get("category") == category:
            out |= set(v["lines"])
    return out


def count(rule):
    return sum(1 for rec in nodes if rule(rec))


results = []

results.append(("intersect (current)", count(lambda r: bool(r["vulns"]))))

results.append(("no_container",
                count(lambda r: bool(r["vulns"]) and r["type"] not in CONTAINER)))

results.append(("no contract_declaration only",
                count(lambda r: bool(r["vulns"]) and r["type"] != "contract_declaration")))

results.append(("first_line must be annotated",
                count(lambda r: bool(r["vulns"]) and r["first"] is not None
                      and r["first"] in ann_lines(r))))

results.append(("node fully inside annotated range",
                count(lambda r: bool(r["vulns"]) and r["lines"]
                      and r["lines"] <= ann_lines(r))))

for k in (1, 2, 3, 5, 10, 20, 40):
    results.append((f"span <= {k} lines",
                    count(lambda r, k=k: bool(r["vulns"]) and 0 < len(r["lines"]) <= k)))

results.append(("reentrancy category only",
                count(lambda r: bool(ann_lines_cat(r, "reentrancy")))))

print(f"\n{'rule':38s} {'buggy':>7s} {'delta vs 6570':>14s}")
for name, n in results:
    mark = "   <== EXACT" if n == TARGET else ""
    print(f"{name:38s} {n:7d} {n - TARGET:+14d}{mark}")

print("\nbuggy nodes by type under the current rule:")
by_type = Counter(r["type"] for r in nodes if r["vulns"])
for t, n in by_type.most_common():
    print(f"  {str(t):24s} {n}")

print("\nnode span width among buggy nodes (how many lines each covers):")
widths = sorted(len(r["lines"]) for r in nodes if r["vulns"])
if widths:
    import statistics
    print(f"  min {widths[0]}  median {statistics.median(widths)}  "
          f"p90 {widths[int(0.9 * len(widths))]}  max {widths[-1]}")
