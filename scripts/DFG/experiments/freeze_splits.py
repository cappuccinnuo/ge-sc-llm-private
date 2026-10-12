"""Freeze file-level outer folds and independent inner validation lists."""
import argparse
from pathlib import Path
from scripts.labeling_v2.safe_graph import read_graph
from .common import new_output, read_json, write_json, sha256
from .protocol import make_fold_document
from .run_pair import checked_path


def freeze(prepared, output, seed=1, inner_fraction=0.2):
    prepared = Path(prepared).resolve()
    manifest = read_json(prepared / "manifest.json")
    out = new_output(output)
    label_path = checked_path(prepared, manifest["graph_labels"])
    labels = {x["contract_name"]: int(x["targets"]) for x in read_json(label_path)}
    documents = {}
    for task in ("contract", "node"):
        graph = read_graph(checked_path(prepared, manifest["graphs"]["E0"][task]))
        files = sorted({d["source_file"] for _, d in graph.nodes(data=True)})
        file_labels = {f: labels[f] for f in files}
        doc = make_fold_document(
            file_labels, task, sha256(prepared / "manifest.json"),
            seed=seed, inner_fraction=inner_fraction)
        documents[task] = doc
    out.mkdir(parents=True)
    for task, doc in documents.items():
        write_json(out / (task + "_folds.json"), doc)
    print("Saved contract 5-fold / node 10-fold nested file lists to " + str(out), flush=True)
    return documents


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepared", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--inner_fraction", type=float, default=0.2)
    args = p.parse_args()
    freeze(args.prepared, args.output, args.seed, args.inner_fraction)


if __name__ == "__main__":
    main()
