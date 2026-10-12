"""Check our node/edge type counts against the ceilings the paper states.

mando-llm.md section 5.2 gives the framework's limits as at most 18 node types and at
most 5 edge types, hence 18 x 5 x 18 = 1620 possible meta relations. Node types being
under the ceiling is fine - it is an upper bound. Edge types going OVER it is not:
that means we emit a relation the paper's design does not have room for.

Compares the graph as currently built (add_dummy_edges on) against the same corpus
with those edges removed, which is the state the repository shipped.
"""
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

BASE = Path(__file__).resolve().parents[1] / "experiments/ge-sc-data/source_code/reentrancy"
GRAPH = BASE / "hcg_narrow.gpickle"

PAPER_MAX_NODE_TYPES = 18
PAPER_MAX_EDGE_TYPES = 5
PAPER_NODES = 18312
PAPER_EDGES = 19267

g = nx.read_gpickle(str(GRAPH))
ntypes = Counter(d.get("node_type") for _, d in g.nodes(data=True))
etypes = Counter(d.get("edge_type") for _, _, d in g.edges(data=True))

print(f"graph: {GRAPH.name}")
print(f"  nodes {g.number_of_nodes()} (paper {PAPER_NODES})"
      f"   edges {g.number_of_edges()} (paper {PAPER_EDGES})")

print(f"\nnode types: {len(ntypes)}  (paper ceiling {PAPER_MAX_NODE_TYPES}) "
      f"{'OK' if len(ntypes) <= PAPER_MAX_NODE_TYPES else 'OVER'}")

print(f"\nedge types: {len(etypes)}  (paper ceiling {PAPER_MAX_EDGE_TYPES}) "
      f"{'OK' if len(etypes) <= PAPER_MAX_EDGE_TYPES else 'OVER CEILING'}")
for t, n in etypes.most_common():
    print(f"  {str(t):24s} {n:6d}")

# what the graph looks like without the dummy-edge contribution
dummy = {"recursive_method_call", "function_call", "function_return"}
kept = Counter({t: n for t, n in etypes.items() if t not in dummy})
dropped = sum(n for t, n in etypes.items() if t in dummy)
print(f"\nif add_dummy_edges were off:")
print(f"  edges {g.number_of_edges() - dropped}  (paper {PAPER_EDGES}, "
      f"delta {g.number_of_edges() - dropped - PAPER_EDGES:+d})")
print(f"  edge types {len(kept)}  "
      f"{'within ceiling' if len(kept) <= PAPER_MAX_EDGE_TYPES else 'still over'}")
for t, n in kept.most_common():
    print(f"    {str(t):24s} {n:6d}")

rare = [t for t, n in etypes.items() if n <= 5]
print(f"\nedge types carrying <=5 edges (rounding noise in a type census): {rare}")

meta = {(g.nodes[s].get("node_type"), d.get("edge_type"), g.nodes[t].get("node_type"))
        for s, t, d in g.edges(data=True)}
print(f"\ndistinct meta relations present: {len(meta)}  "
      f"(paper's theoretical max {PAPER_MAX_NODE_TYPES * PAPER_MAX_EDGE_TYPES * PAPER_MAX_NODE_TYPES})")
meta_wo = {m for m in meta if m[1] not in dummy}
print(f"  without dummy-edge types: {len(meta_wo)}")

print("\n--- the conflict ---")
print(f"  edge COUNT  matches the paper only WITH add_dummy_edges "
      f"({g.number_of_edges()} vs {g.number_of_edges() - dropped})")
print(f"  edge TYPE count fits the paper's ceiling only WITHOUT it "
      f"({len(kept)} vs {len(etypes)})")
