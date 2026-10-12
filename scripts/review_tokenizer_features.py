"""Review the tokenizer-derived node features before spending training time on them.

Checks, per scheme:
  - the model contract: torch.tensor(node['token']) gives a 512-wide vector and
    get_node_token() groups it per node type with a single consistent width
  - determinism: identical code snippets must map to identical features, so the
    number of distinct features should equal the number of distinct code strings
  - value range: adapt_ws is a plain Linear(512, 128), so features of magnitude ~3e4
    ('ids') behave very differently from ones in [0, 1] ('ids_norm')
  - information content: how much of the vector is padding, and whether two nodes of
    the same node_type are separable at all
"""
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from sco_models.graph_utils import get_node_token  # noqa: E402

BASE = REPO / "experiments/ge-sc-data/source_code/reentrancy"
SCHEMES = ["ids", "ids_norm", "hashed_bow"]

for scheme in SCHEMES:
    path = BASE / f"tokenizer_{scheme}_codet5p-770m_hcg_compressed_graphs.gpickle"
    print("=" * 74)
    print(f"scheme: {scheme}")
    if not path.exists():
        print("  MISSING")
        continue
    g = nx.read_gpickle(str(path))

    tokens = [d["token"] for _, d in g.nodes(data=True) if d.get("token") is not None]
    codes = [(d.get("code") or "") for _, d in g.nodes(data=True)]
    print(f"  nodes with token : {len(tokens)}/{g.number_of_nodes()}")

    stacked = np.stack(tokens)
    print(f"  shape            : {stacked.shape}  dtype={stacked.dtype}")
    print(f"  value range      : [{stacked.min():.4g}, {stacked.max():.4g}]  "
          f"mean={stacked.mean():.4g}  std={stacked.std():.4g}")

    # model contract
    features = get_node_token(g)
    widths = {tuple(f.shape)[-1] for f in features.values()}
    in_size = list(features.values())[0].shape[-1]
    assert len(widths) == 1, f"inconsistent widths {widths}"
    total = sum(f.shape[0] for f in features.values())
    assert total == g.number_of_nodes(), f"{total} != {g.number_of_nodes()}"
    finite = all(torch.isfinite(f).all().item() for f in features.values())
    print(f"  in_size inferred : {in_size}   node types: {len(features)}   finite: {finite}")

    # determinism
    distinct_feat = np.unique(stacked, axis=0).shape[0]
    distinct_code = len(set(codes))
    match = "OK" if distinct_feat == distinct_code else "MISMATCH"
    print(f"  distinct features: {distinct_feat}   distinct code: {distinct_code}   [{match}]")

    # how much of each vector is padding / zero
    zero_frac = float((stacked == 0).mean())
    print(f"  zero entries     : {100 * zero_frac:.1f}% of all positions")

    # separability within the largest node type
    biggest = max(features, key=lambda k: features[k].shape[0])
    sub = features[biggest].numpy()
    uniq_sub = np.unique(sub, axis=0).shape[0]
    print(f"  largest type     : {biggest} ({sub.shape[0]} nodes, {uniq_sub} distinct)")

print("\nREVIEW DONE")
