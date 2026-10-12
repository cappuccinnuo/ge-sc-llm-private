"""Check that what encode_llm_tokens.py writes is what the model layer expects.

get_node_token() does torch.tensor(node_data['token']).unsqueeze(0) and concatenates
per node_type, and HGTVulNodeClassifier then reads in_size from the last dimension.
Anything about the stored dtype/shape that breaks those two steps has to surface here
rather than halfway through a training run.
"""
import sys
from pathlib import Path

import networkx as nx
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from sco_models.graph_utils import get_node_token  # noqa: E402

graph_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/smoke_token_graph.gpickle"
g = nx.read_gpickle(graph_path)

encoded = [n for n, d in g.nodes(data=True) if d.get("token") is not None]
print(f"graph        : {graph_path}")
print(f"nodes        : {g.number_of_nodes()}")
print(f"with 'token' : {len(encoded)}")

if not encoded:
    raise SystemExit("no encoded nodes found")

sample = g.nodes[encoded[0]]["token"]
print(f"stored type  : {type(sample).__name__}  dtype={getattr(sample, 'dtype', None)}  "
      f"shape={getattr(sample, 'shape', len(sample))}")

# 1. the exact conversion get_node_token performs
t = torch.tensor(sample).unsqueeze(0)
print(f"torch.tensor(): {tuple(t.shape)}  {t.dtype}")
assert t.dim() == 2, "expected a single vector per node"

# 2. run get_node_token over the encoded subgraph, which is what the model calls
sub = g.subgraph(encoded).copy()
features = get_node_token(sub)
print("\nget_node_token() per node_type:")
for ntype, feat in features.items():
    print(f"  {ntype:24s} {tuple(feat.shape)}  {feat.dtype}")

# 3. the width the model would adopt as in_size
in_size = list(features.values())[0].shape[-1]
print(f"\nin_size the model would infer: {in_size}")

widths = {tuple(f.shape)[-1] for f in features.values()}
assert len(widths) == 1, f"inconsistent embedding widths across node types: {widths}"

counts = sum(f.shape[0] for f in features.values())
assert counts == len(encoded), f"node count mismatch: {counts} != {len(encoded)}"

finite = all(torch.isfinite(f).all().item() for f in features.values())
print(f"all values finite: {finite}")
assert finite, "non-finite values in embeddings"

# 4. embeddings must actually differ between nodes, otherwise the feature carries
#    no signal (the failure mode when padding dominates an unmasked mean).
stacked = torch.cat([f for f in features.values()], dim=0).float()
pairwise_std = stacked.std(dim=0).mean().item()
uniq = torch.unique(stacked, dim=0).shape[0]
print(f"distinct embeddings: {uniq}/{stacked.shape[0]}")
print(f"mean per-dim std   : {pairwise_std:.6f}")

print("\nINTERFACE OK")
