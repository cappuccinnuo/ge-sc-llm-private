"""Does add_dummy_edges change the node side at all?

It is named for edges, but it can still create nodes indirectly: networkx materialises
a bare node whenever add_edge names an id that was never added with attributes. The
'external_function' branch inside it points at exactly such a dummy id, so the node
count has to be checked rather than assumed.
"""
import glob
from collections import Counter

import networkx as nx

PAPER_NODES = 18312
PAPER_EDGES = 19267

for tag, d in [("add_dummy_edges OFF", "/tmp/probe_off"),
               ("add_dummy_edges ON ", "/tmp/probe_on")]:
    nodes = edges = 0
    ntypes = Counter()
    etypes = Counter()
    for p in glob.glob(d + "/*.gpickle"):
        g = nx.read_gpickle(p)
        nodes += g.number_of_nodes()
        edges += g.number_of_edges()
        for _, data in g.nodes(data=True):
            ntypes[data.get("node_type")] += 1
        for _, _, data in g.edges(data=True):
            etypes[data.get("edge_type")] += 1
    ext = ntypes.get("external_function", 0)
    print(f"{tag}: nodes {nodes} (paper {PAPER_NODES})  "
          f"edges {edges} (paper {PAPER_EDGES})")
    print(f"    node types {len(ntypes)}   external_function nodes {ext}")
    print(f"    edge types {len(etypes)}: {dict(etypes)}")
    print()

a = Counter()
b = Counter()
for p in glob.glob("/tmp/probe_off/*.gpickle"):
    for _, data in nx.read_gpickle(p).nodes(data=True):
        a[data.get("node_type")] += 1
for p in glob.glob("/tmp/probe_on/*.gpickle"):
    for _, data in nx.read_gpickle(p).nodes(data=True):
        b[data.get("node_type")] += 1
diff = {t: b[t] - a[t] for t in set(a) | set(b) if b[t] != a[t]}
print(f"node-type differences between the two builds: {diff or 'none'}")
