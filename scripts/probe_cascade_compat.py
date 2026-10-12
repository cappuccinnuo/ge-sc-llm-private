"""Can the line-level checkpoint score nodes of contracts it was not trained over?

Phase 2 was trained on the buggy-contracts-only subgraph (12,036 nodes). Phase 1
runs over the full HCG (18,312 nodes) and will sometimes flag a contract that is not
in that subgraph - a false positive still has to be explainable, so the cascade needs
the node classifier to cover every contract Phase 1 can point at.

HGTVulNodeClassifier.forward() evaluates the graph handed to its constructor, and the
learned weights are indexed by the ntypes/etypes dictionaries derived from that graph.
So reusing the checkpoint on the full HCG is only valid if both graphs yield the same
type dictionaries in the same order. This checks exactly that, and then tries the
load for real.
"""
import contextlib
import io
import sys
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from sco_models.model_hgt import HGTVulNodeClassifier  # noqa: E402

BASE = REPO / "experiments/ge-sc-data/source_code/reentrancy"
FULL = BASE / "tokenizer_ids_codet5p-770m_hcg_compressed_graphs.gpickle"
LINE = BASE / "linelevel_tokenizer_ids.gpickle"
CKPT = REPO / "models/linelevel/tok_ids/reentrancy_hgt.pth"

device = "cuda:0" if torch.cuda.is_available() else "cpu"


def build(path):
    with contextlib.redirect_stdout(io.StringIO()):
        return HGTVulNodeClassifier(str(path), feature_extractor=None,
                                    node_feature="inside_token", device=device)


print("building model over the line-level subgraph ...")
m_line = build(LINE)
print("building model over the full HCG ...")
m_full = build(FULL)

print(f"\nline-level graph : {len(m_line.node_labels)} nodes")
print(f"full HCG         : {len(m_full.node_labels)} nodes")

print(f"\nntypes match : {m_line.ntypes_dict == m_full.ntypes_dict}")
print(f"  line: {m_line.ntypes_dict}")
print(f"  full: {m_full.ntypes_dict}")

same_e = m_line.etypes_dict == m_full.etypes_dict
print(f"\netypes match : {same_e}  ({len(m_line.etypes_dict)} vs {len(m_full.etypes_dict)})")
if not same_e:
    only_line = set(m_line.etypes_dict) - set(m_full.etypes_dict)
    only_full = set(m_full.etypes_dict) - set(m_line.etypes_dict)
    print(f"  only in line-level: {len(only_line)}")
    for e in sorted(map(str, only_line))[:5]:
        print(f"    {e}")
    print(f"  only in full HCG  : {len(only_full)}")
    for e in sorted(map(str, only_full))[:5]:
        print(f"    {e}")

print(f"\nin_size line={m_line.in_size}  full={m_full.in_size}")

state = torch.load(str(CKPT), map_location=device)
print(f"\ncheckpoint tensors: {len(state)}")
try:
    m_full.load_state_dict(state)
    print("load_state_dict onto full HCG: OK")
except Exception as exc:
    msg = str(exc)
    print("load_state_dict onto full HCG: FAILED")
    print("  " + msg[:600])
