"""Read-only: which attributes do locally built nodes carry (needed to derive author-style endpoints)?"""
import pickle
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
path = REPO / "scripts/access_control_test/artifacts/dataset_a_source_range_v1/hcg_labeled.gpickle"
g = pickle.load(open(path, "rb"))
seen = set()
for n, d in g.nodes(data=True):
    if d["node_type"] in ("end_if", "end_loop", "if", "for", "function_definition") and d["node_type"] not in seen:
        seen.add(d["node_type"])
        print(n, {k: (str(v)[:110]) for k, v in d.items() if k not in ("token",)})
print("edge sample:", list(g.edges(data=True))[:3])
src = (REPO / "process_graphs/tree_sitter_codeviews/codeviews/CFG/CFG.py")
print(src.exists())
