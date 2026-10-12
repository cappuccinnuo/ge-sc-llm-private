"""Score every fold's best.pt and last.pt on that fold's own held-out contracts.

The trainers report only the restored-best score. The public upstream code evaluated
the weights at the stopping epoch instead, so both numbers are needed to compare a run
with the paper. Fold membership is read back from each fold's selection.json; nothing
is retrained and no file is written.

Usage:
  python scripts/eval_best_last.py --task line     --graph G.gpickle --run_dir DIR
  python scripts/eval_best_last.py --task contract --graph G.gpickle --run_dir DIR --label L.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import f1_score

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def f1_pair(labels, logits):
    pred = logits.argmax(dim=1).cpu().numpy()
    labels = np.asarray(labels)
    return (f1_score(labels, pred, average=None, labels=[0, 1])[1] * 100,
            f1_score(labels, pred, average='macro') * 100)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--task", choices=("line", "contract"), required=True)
    p.add_argument("--graph", required=True)
    p.add_argument("--run_dir", required=True)
    p.add_argument("--label", default=None)
    p.add_argument("--node_feature", default="inside_token")
    args = p.parse_args()
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    from sco_models.model_hgt import HGTVulGraphClassifier, HGTVulNodeClassifier
    if args.task == "contract":
        model = HGTVulGraphClassifier(args.graph, feature_extractor=None,
                                      node_feature=args.node_feature, device=device)
        with open(args.label) as f:
            target_of = {c["contract_name"]: int(c["targets"]) for c in json.load(f)}
    else:
        model = HGTVulNodeClassifier(args.graph, feature_extractor=None,
                                     node_feature=args.node_feature, device=device)
        node_labels = np.asarray(model.node_labels)
        file_of = [d["source_file"] for _, d in sorted(model.nx_graph.nodes(data=True))]
    model.to(device)

    fold_dirs = sorted(Path(args.run_dir).glob("*_fold*"),
                       key=lambda d: int(d.name.rsplit("fold", 1)[1]))
    scores = {"best": [], "last": []}
    for fold_dir in fold_dirs:
        with open(fold_dir / "selection.json") as f:
            sel = json.load(f)
        val_files = sel["val_files"]
        row = []
        for kind in ("best", "last"):
            model.load_state_dict(torch.load(fold_dir / f"{kind}.pt", map_location=device))
            model.eval()
            with torch.no_grad():
                if args.task == "contract":
                    logits, _ = model(val_files)
                    labels = [target_of[name] for name in val_files]
                else:
                    val = set(val_files)
                    ids = [i for i, name in enumerate(file_of) if name in val]
                    logits = model()[ids]
                    labels = node_labels[ids]
            buggy, macro = f1_pair(labels, logits)
            scores[kind].append((buggy, macro))
            row.append(f"{kind} {buggy:7.3f}/{macro:7.3f}")
        print(f"fold {sel['fold']}: best_epoch {sel['best_epoch']:2d} last_epoch {sel['last_epoch']:2d} | "
              + " | ".join(row))
    for kind in ("best", "last"):
        arr = np.asarray(scores[kind])
        print(f"{kind}: mean Buggy-F1 {arr[:, 0].mean():.4f}  mean Macro-F1 {arr[:, 1].mean():.4f}  "
              f"(std of Buggy-F1 across folds {arr[:, 0].std():.2f})")


if __name__ == "__main__":
    main()
