"""Probe what the shipped reentrancy cfg_cg/*.pkl artifacts actually contain.

Their names follow the merged-graph convention that token_baselines.py feeds to
nx.read_gpickle(), so they may be full merged graphs rather than embedding matrices.
"""
import pickle
from collections import Counter
from pathlib import Path

import networkx as nx

BASE = Path("experiments/ge-sc-data/source_code/reentrancy/cfg_cg")

for name in ["node2vec_cfg_cg_compressed_graphs.pkl",
             "node2vec_coarse_grained_cfg_cg_compressed_graphs.pkl"]:
    path = BASE / name
    print("=" * 70)
    print(name)
    if not path.exists():
        print("  MISSING")
        continue
    with open(path, "rb") as f:
        obj = pickle.load(f)
    print("  type:", type(obj))

    if isinstance(obj, nx.Graph):
        print("  nodes:", obj.number_of_nodes(), " edges:", obj.number_of_edges())
        sources = {d.get("source_file") for _, d in obj.nodes(data=True)}
        print("  distinct source_file:", len(sources))
        print("  sample source_file:", list(sorted(s for s in sources if s))[:5])
        ntypes = Counter(d.get("node_type") for _, d in obj.nodes(data=True))
        print("  node_type:", ntypes.most_common(12))
        etypes = Counter(d.get("edge_type") for _, _, d in obj.edges(data=True))
        print("  edge_type:", etypes.most_common(12))
        # attribute coverage on a sample node
        sample = next(iter(obj.nodes(data=True)))
        print("  sample node attrs:", sorted(sample[1].keys()))
        has_token = sum(1 for _, d in obj.nodes(data=True) if d.get("token") is not None)
        has_vuln = sum(1 for _, d in obj.nodes(data=True) if d.get("node_info_vulnerabilities"))
        has_code = sum(1 for _, d in obj.nodes(data=True) if d.get("code"))
        print(f"  nodes with 'token': {has_token}")
        print(f"  nodes with non-empty 'node_info_vulnerabilities': {has_vuln}")
        print(f"  nodes with 'code': {has_code}")
        tok = next((d.get("token") for _, d in obj.nodes(data=True) if d.get("token") is not None), None)
        if tok is not None:
            try:
                print("  token dim:", len(tok))
            except TypeError:
                print("  token repr:", repr(tok)[:120])
    else:
        try:
            import numpy as np
            arr = np.asarray(obj)
            print("  array shape:", arr.shape, " dtype:", arr.dtype)
        except Exception as exc:
            print("  not array-like:", exc)
            print("  repr:", repr(obj)[:300])
