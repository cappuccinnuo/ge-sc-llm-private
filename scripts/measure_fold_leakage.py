"""Measure how much of each validation fold the model has already seen verbatim.

node_classifier splits folds by contract, which stops nodes of one contract from
straddling the split. It does not stop the same *code* from appearing on both sides:
SolidiFI injects a small pool of bug templates into many contracts, and the corpus has
18,312 nodes drawn from only 6,278 distinct snippets.

Both feature types are deterministic functions of the node, so a repeated snippet
produces a byte-identical feature vector:
  inside_token : tokenizer(code) -> the same 512 numbers
  nodetype     : one-hot of node_type

If a validation node's (code, label) pair also occurs in the training fold, predicting
it correctly needs memorisation, not localisation. This reproduces the exact fold
split node_classifier uses and reports that overlap.
"""
import sys
from collections import Counter
from pathlib import Path

import networkx as nx
import numpy as np
from sklearn.model_selection import KFold

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "experiments/ge-sc-data/source_code/reentrancy"
GRAPH = BASE / "linelevel_tokenizer_ids.gpickle"
K_FOLDS = 10
SEED = 1

g = nx.read_gpickle(str(GRAPH))
print(f"graph: {GRAPH.name}")
print(f"  {g.number_of_nodes()} nodes")

codes = {n: (d.get("code") or "") for n, d in g.nodes(data=True)}
labels = {n: bool(d.get("node_info_vulnerabilities")) for n, d in g.nodes(data=True)}
files = {n: d["source_file"] for n, d in g.nodes(data=True)}

distinct = len(set(codes.values()))
print(f"  distinct code snippets: {distinct}  "
      f"({100.0 * distinct / g.number_of_nodes():.1f}% of nodes)")

# how often a snippet repeats
rep = Counter(codes.values())
multi = sum(v for v in rep.values() if v > 1)
print(f"  nodes whose snippet occurs more than once: {multi} "
      f"({100.0 * multi / g.number_of_nodes():.1f}%)")
print(f"  most repeated snippets:")
for snippet, c in rep.most_common(5):
    print(f"    x{c:4d}  {snippet.strip()[:70]!r}")

# node_classifier: total_train_files = get_all_source_paths(graph); KFold over those
total_train_files = sorted({files[n] for n in g.nodes()})
kfold = KFold(n_splits=K_FOLDS, shuffle=True, random_state=SEED)

print(f"\nreproducing the {K_FOLDS}-fold split over {len(total_train_files)} contracts")
print(f"{'fold':>4s} {'val nodes':>10s} {'seen (code,label)':>18s} {'seen code':>11s}")

seen_pair_all, seen_code_all, val_all = 0, 0, 0
for fold, (tr_idx, va_idx) in enumerate(kfold.split(total_train_files)):
    tr_files = {total_train_files[i] for i in tr_idx}
    va_files = {total_train_files[i] for i in va_idx}
    tr_nodes = [n for n in g.nodes() if files[n] in tr_files]
    va_nodes = [n for n in g.nodes() if files[n] in va_files]

    train_pairs = {(codes[n], labels[n]) for n in tr_nodes}
    train_codes = {codes[n] for n in tr_nodes}

    seen_pair = sum(1 for n in va_nodes if (codes[n], labels[n]) in train_pairs)
    seen_code = sum(1 for n in va_nodes if codes[n] in train_codes)

    seen_pair_all += seen_pair
    seen_code_all += seen_code
    val_all += len(va_nodes)
    print(f"{fold:4d} {len(va_nodes):10d} {seen_pair:12d} "
          f"({100.0 * seen_pair / max(len(va_nodes), 1):4.1f}%) "
          f"{100.0 * seen_code / max(len(va_nodes), 1):9.1f}%")

print(f"\noverall: {seen_pair_all}/{val_all} validation nodes "
      f"({100.0 * seen_pair_all / val_all:.1f}%) appear in their training fold "
      f"with the identical snippet AND the identical label")
print(f"         {seen_code_all}/{val_all} "
      f"({100.0 * seen_code_all / val_all:.1f}%) share a snippet regardless of label")

# what a pure memoriser would score
print("\nscore obtainable by memorisation alone (no model):")
tp = fp = fn = tn = 0
for fold, (tr_idx, va_idx) in enumerate(kfold.split(total_train_files)):
    tr_files = {total_train_files[i] for i in tr_idx}
    va_files = {total_train_files[i] for i in va_idx}
    lookup = {}
    for n in g.nodes():
        if files[n] in tr_files:
            lookup.setdefault(codes[n], Counter())[labels[n]] += 1
    for n in g.nodes():
        if files[n] not in va_files:
            continue
        truth = labels[n]
        c = lookup.get(codes[n])
        guess = c.most_common(1)[0][0] if c else False  # unseen -> predict clean
        if guess and truth:
            tp += 1
        elif guess and not truth:
            fp += 1
        elif not guess and truth:
            fn += 1
        else:
            tn += 1
prec = tp / max(tp + fp, 1)
rec = tp / max(tp + fn, 1)
f1 = 2 * prec * rec / max(prec + rec, 1e-9)
print(f"  lookup table on (code -> majority label): "
      f"P {prec:.4f}  R {rec:.4f}  Buggy-F1 {100 * f1:.2f}")
