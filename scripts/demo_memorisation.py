"""Walk through one repeated snippet to show concretely why the metric is memorisable.

SolidiFI builds its buggy contracts by injecting a handful of bug templates into many
different host contracts. The same few lines therefore appear verbatim across dozens
of .sol files, always carrying the same label. Node features are a deterministic
function of the node's code, so an identical snippet becomes an identical feature
vector. Folds are split by contract, which keeps a contract's own nodes together but
does nothing about a snippet shared across contracts: the model meets the exact
(feature, label) pair in training and then again in validation.
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np
from sklearn.model_selection import KFold

BASE = Path(__file__).resolve().parents[1] / "experiments/ge-sc-data/source_code/reentrancy"
GRAPH = BASE / "linelevel_tokenizer_ids.gpickle"
K, SEED = 10, 1

g = nx.read_gpickle(str(GRAPH))
code = {n: (d.get("code") or "") for n, d in g.nodes(data=True)}
label = {n: bool(d.get("node_info_vulnerabilities")) for n, d in g.nodes(data=True)}
src = {n: d["source_file"] for n, d in g.nodes(data=True)}
tok = {n: d.get("token") for n, d in g.nodes(data=True)}

rep = Counter(code.values())
target_snippet, count = rep.most_common(1)[0]

print("=" * 76)
print("the single most repeated snippet in the line-level graph")
print("=" * 76)
print(f"occurrences: {count} nodes")
print("text:")
for line in target_snippet.split("\n"):
    print(f"    {line}")

nodes = [n for n in g.nodes() if code[n] == target_snippet]
files = sorted({src[n] for n in nodes})
labels = Counter(label[n] for n in nodes)
print(f"\nspread over {len(files)} different .sol files")
print(f"  sample files: {files[:6]}")
print(f"  labels: buggy={labels[True]}  clean={labels[False]}"
      f"   -> {'always the same label' if len(labels) == 1 else 'MIXED labels'}")

vecs = np.stack([tok[n] for n in nodes])
identical = np.unique(vecs, axis=0).shape[0]
print(f"  distinct feature vectors among those {len(nodes)} nodes: {identical}")
print("   (1 means every occurrence is byte-identical to the model)")

# where do those occurrences land across the folds
contracts = sorted({src[n] for n in g.nodes()})
kfold = KFold(n_splits=K, shuffle=True, random_state=SEED)
print(f"\nhow this snippet is distributed by the {K}-fold split over {len(contracts)} contracts")
print(f"{'fold':>4s} {'in train':>9s} {'in val':>7s}")
for fold, (tr, va) in enumerate(kfold.split(contracts)):
    tr_files = {contracts[i] for i in tr}
    va_files = {contracts[i] for i in va}
    n_tr = sum(1 for n in nodes if src[n] in tr_files)
    n_va = sum(1 for n in nodes if src[n] in va_files)
    print(f"{fold:4d} {n_tr:9d} {n_va:7d}"
          + ("   <- every val occurrence already seen in train" if n_tr and n_va else ""))

print()
print("=" * 76)
print("corpus-wide")
print("=" * 76)
print(f"nodes                       : {g.number_of_nodes()}")
print(f"distinct code snippets      : {len(rep)}")
print(f"nodes on a repeated snippet : {sum(v for v in rep.values() if v > 1)}")
top = rep.most_common(5)
print("\ntop repeated snippets:")
for s, c in top:
    flat = re.sub(r"\s+", " ", s).strip()
    print(f"  x{c:4d}  {flat[:66]!r}")
covered = sum(c for _, c in top)
print(f"\nthose 5 snippets alone cover {covered} nodes "
      f"({100.0 * covered / g.number_of_nodes():.1f}% of the graph)")
