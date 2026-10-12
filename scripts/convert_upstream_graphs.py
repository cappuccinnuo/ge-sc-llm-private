"""Re-pickle the authors' graphs at protocol 4 so the Python 3.7 training code can read them.

The Google Drive gpickles are protocol 5, which 3.7 cannot load; the training path goes
through sco_models.graph_utils.read_gpickle and would fail. Loading via the pickle5
backport and writing back at protocol 4 leaves the graph object untouched - this is a
container format change, not a content change, and the check at the end confirms that.
"""
import pickle
from collections import Counter
from pathlib import Path

import networkx as nx

try:
    import pickle5
except ImportError:
    pickle5 = None

REPO = Path(__file__).resolve().parents[1]
UP = REPO / "data/upstream_mando_llm"
OUT = REPO / "experiments/ge-sc-data/source_code/reentrancy"

JOBS = [
    (UP / "node_detection/reentrancy_tree_sitter_cfg_compressed_graphs.gpickle",
     OUT / "upstream_linelevel_cfg.gpickle"),
    (UP / "graph_detection/reentrancy_tree_sitter_cfg_cg_compressed_graphs.gpickle",
     OUT / "upstream_contractlevel_cfg_cg.gpickle"),
]


def load_any(path):
    with open(path, "rb") as f:
        try:
            return pickle.load(f)
        except ValueError:
            pass
    if pickle5 is None:
        raise RuntimeError("protocol 5 file but pickle5 is not installed")
    with open(path, "rb") as f:
        return pickle5.load(f)


def fingerprint(g):
    return (
        g.number_of_nodes(),
        g.number_of_edges(),
        tuple(sorted(Counter(d.get("node_type") for _, d in g.nodes(data=True)).items())),
        tuple(sorted(Counter(d.get("edge_type") for _, _, d in g.edges(data=True)).items())),
        sum(1 for _, d in g.nodes(data=True) if d.get("node_info_vulnerabilities")),
    )


for src, dst in JOBS:
    print(f"{src.name}")
    if not src.exists():
        print("  MISSING")
        continue
    g = load_any(src)
    before = fingerprint(g)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as f:
        pickle.dump(g, f, protocol=4)

    # read it back the way the training code will
    g2 = nx.read_gpickle(str(dst))
    after = fingerprint(g2)
    ok = before == after
    print(f"  -> {dst.name}")
    print(f"     nodes {before[0]}  edges {before[1]}  buggy {before[4]}")
    print(f"     round-trip identical: {ok}")
    if not ok:
        raise SystemExit("conversion changed the graph - stop and investigate")
    print()

print("done")
