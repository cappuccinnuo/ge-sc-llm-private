"""Compare our rebuilt graphs against the authors' own graphs from Google Drive.

Everything up to now has been inferred from appendix C's totals. These files are the
real thing, so the open questions can be answered directly instead of by elimination:

  - is the +408 buggy-node gap a labelling difference, and on which node types
  - do their node/edge type vocabularies match ours
  - does their node_detection graph hold all 142 contracts or only the 71 buggy ones
  - what attributes do their nodes carry (does 'code' exist, is 'token' precomputed)
  - are their line numbers preprocessed or original
"""
import json
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

# The authors' gpickles were written with pickle protocol 5, which Python 3.7 cannot
# read natively; the pickle5 backport handles them. Ours are protocol <=4, so the
# stdlib loader is fine for those.
try:
    import pickle5
except ImportError:
    pickle5 = None
import pickle


def load_graph(path):
    with open(path, "rb") as f:
        try:
            return pickle.load(f)
        except ValueError:
            if pickle5 is None:
                raise
    with open(path, "rb") as f:
        return pickle5.load(f)

REPO = Path(__file__).resolve().parents[1]
UP = REPO / "data/upstream_mando_llm"
OURS = REPO / "experiments/ge-sc-data/source_code/reentrancy"

PAIRS = [
    ("node_detection (line level)",
     UP / "node_detection/reentrancy_tree_sitter_cfg_compressed_graphs.gpickle",
     OURS / "linelevel_narrow.gpickle"),
    ("graph_detection (contract level)",
     UP / "graph_detection/reentrancy_tree_sitter_cfg_cg_compressed_graphs.gpickle",
     OURS / "hcg_narrow.gpickle"),
]


def summarise(g, name):
    ntypes = Counter(d.get("node_type") for _, d in g.nodes(data=True))
    etypes = Counter(d.get("edge_type") for _, _, d in g.edges(data=True))
    files = {d.get("source_file") for _, d in g.nodes(data=True)}
    buggy = Counter()
    for _, d in g.nodes(data=True):
        if d.get("node_info_vulnerabilities"):
            buggy[d.get("node_type")] += 1
    attrs = Counter()
    for _, d in g.nodes(data=True):
        for k in d:
            attrs[k] += 1
    print(f"  {name}")
    print(f"    nodes {g.number_of_nodes()}  edges {g.number_of_edges()}")
    print(f"    contracts {len(files)}")
    print(f"    buggy nodes {sum(buggy.values())}")
    print(f"    node types {len(ntypes)}  edge types {len(etypes)}")
    print(f"    edge types: {dict(etypes)}")
    print(f"    node attributes: {sorted(attrs)}")
    return ntypes, etypes, buggy, files


for title, up_path, our_path in PAIRS:
    print("=" * 78)
    print(title)
    print("=" * 78)
    if not up_path.exists():
        print(f"  upstream missing: {up_path}")
        continue
    gu = load_graph(up_path)
    nu, eu, bu, fu = summarise(gu, f"UPSTREAM  {up_path.name}")
    print()
    if not our_path.exists():
        print(f"  ours missing: {our_path}")
        continue
    go = load_graph(our_path)
    no, eo, bo, fo = summarise(go, f"OURS      {our_path.name}")

    print(f"\n  --- node types ---")
    for t in sorted(set(nu) | set(no), key=lambda x: -(nu.get(x, 0) + no.get(x, 0))):
        mark = "" if nu.get(t, 0) == no.get(t, 0) else "   <-- differs"
        print(f"    {str(t):26s} upstream {nu.get(t,0):6d}   ours {no.get(t,0):6d}{mark}")

    print(f"\n  --- buggy nodes by type ---")
    for t in sorted(set(bu) | set(bo), key=lambda x: -(bu.get(x, 0) + bo.get(x, 0))):
        d = bo.get(t, 0) - bu.get(t, 0)
        mark = "" if d == 0 else f"   delta {d:+d}"
        print(f"    {str(t):26s} upstream {bu.get(t,0):6d}   ours {bo.get(t,0):6d}{mark}")
    print(f"    {'TOTAL':26s} upstream {sum(bu.values()):6d}   ours {sum(bo.values()):6d}"
          f"   delta {sum(bo.values()) - sum(bu.values()):+d}")

    only_up = fu - fo
    only_ours = fo - fu
    print(f"\n  --- contracts ---")
    print(f"    shared {len(fu & fo)}   only upstream {len(only_up)}   only ours {len(only_ours)}")
    if only_up:
        print(f"      upstream-only sample: {sorted(only_up)[:5]}")
    if only_ours:
        print(f"      ours-only sample: {sorted(only_ours)[:5]}")
    print()

# labels file
lab = UP / "graph_detection/reentrancy_graph_labels.json"
if lab.exists():
    print("=" * 78)
    print("upstream graph_labels.json")
    print("=" * 78)
    data = json.load(open(lab))
    print(f"  entries {len(data)}   buggy {sum(int(e['targets']) for e in data)}")
    print(f"  first entry: {data[0]}")
    ours_lab = OURS / "graph_labels.json"
    if ours_lab.exists():
        od = json.load(open(ours_lab))
        print(f"  ours: entries {len(od)}   buggy {sum(int(e['targets']) for e in od)}")
        up_map = {e["contract_name"]: int(e["targets"]) for e in data}
        our_map = {e["contract_name"]: int(e["targets"]) for e in od}
        disagree = [k for k in up_map if k in our_map and up_map[k] != our_map[k]]
        print(f"  contracts labelled differently: {len(disagree)} {disagree[:5]}")
        print(f"  only upstream: {len(set(up_map) - set(our_map))}"
              f"   only ours: {len(set(our_map) - set(up_map))}")
