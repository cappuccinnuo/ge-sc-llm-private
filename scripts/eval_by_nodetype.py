"""Break the line-level score down by node type, and re-score on statement nodes only.

The headline Buggy-F1 is computed over every node in the graph. Roughly 30% of the
positive class there is reachable without localising anything: container nodes
(contract_declaration, function_definition) span everything inside them and are
positive almost by construction once clean contracts are excluded, and every end_if
currently carries the exact span - and therefore the exact label - of an if node it
is directly connected to.

This reports F1 per node type, then recomputes the aggregate over statement-level
nodes only, which is the number that actually reflects line localisation.
"""
import contextlib
import io
import sys
from collections import Counter
from pathlib import Path

import networkx as nx
import torch
from sklearn.metrics import f1_score, precision_recall_fscore_support

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

BASE = REPO / "experiments/ge-sc-data/source_code/reentrancy"
GRAPH = BASE / "linelevel_tokenizer_ids.gpickle"
CKPT = REPO / "models/linelevel/tok_ids/reentrancy_hgt.pth"

CONTAINER = {"contract_declaration", "function_definition", "library_declaration",
             "interface_declaration", "modifier_definition", "constructor_definition",
             "struct_declaration"}
TWIN = {"end_if", "end_loop"}

device = "cuda:0" if torch.cuda.is_available() else "cpu"

from sco_models.model_hgt import HGTVulNodeClassifier  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    model = HGTVulNodeClassifier(str(GRAPH), feature_extractor=None,
                                 node_feature="inside_token", device=device)
model.load_state_dict(torch.load(str(CKPT), map_location=device))
model.to(device).eval()

g = nx.read_gpickle(str(GRAPH))
with torch.no_grad():
    logits = model()
    pred = torch.argmax(logits, dim=1).cpu().numpy()

targets = torch.tensor(model.node_labels).numpy()
ntypes = [g.nodes[n].get("node_type") for n in sorted(g.nodes())]

print(f"nodes {len(targets)}   positives {int(targets.sum())} "
      f"({100.0 * targets.sum() / len(targets):.2f}%)")
print("\nNOTE: the checkpoint was trained on this graph, so these are fit numbers, "
      "not held-out performance. The point is the relative split across node types.")

print(f"\n{'node_type':26s} {'n':>6s} {'pos':>6s} {'P':>7s} {'R':>7s} {'F1':>7s}")
groups = Counter(ntypes)
for t, n in groups.most_common():
    idx = [i for i, x in enumerate(ntypes) if x == t]
    y, yhat = targets[idx], pred[idx]
    if y.sum() == 0:
        acc = (y == yhat).mean()
        print(f"{str(t):26s} {n:6d} {0:6d} {'-':>7s} {'-':>7s} {'-':>7s}  "
              f"(all negative, acc {acc:.4f})")
        continue
    p, r, f, _ = precision_recall_fscore_support(y, yhat, labels=[1], zero_division=0)
    print(f"{str(t):26s} {n:6d} {int(y.sum()):6d} {p[0]:7.4f} {r[0]:7.4f} {f[0]:7.4f}")


def report(mask, label):
    idx = [i for i, t in enumerate(ntypes) if mask(t)]
    y, yhat = targets[idx], pred[idx]
    bf1 = f1_score(y, yhat, labels=[1], average="binary", zero_division=0)
    mf1 = f1_score(y, yhat, average="macro", zero_division=0)
    print(f"{label:34s} nodes {len(idx):6d}  pos {int(y.sum()):6d}  "
          f"Buggy-F1 {100 * bf1:6.2f}  Macro-F1 {100 * mf1:6.2f}")


print()
report(lambda t: True, "all nodes (headline number)")
report(lambda t: t not in CONTAINER, "excluding container nodes")
report(lambda t: t not in TWIN, "excluding end_if / end_loop twins")
report(lambda t: t not in CONTAINER and t not in TWIN, "statement-level nodes only")
