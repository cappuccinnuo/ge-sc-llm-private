"""Audit all main folds without fitting or choosing model weights."""
import argparse
import gc
from pathlib import Path
import torch
from .common import write_json, seed_all, sha256, utc
from .paper_protocol import NAME, VERSION, SCORE_ROLE, protocol_output
from .paper_run import load_inputs
from .paper_runtime import graph_schema_and_support, validate_registration, Supervision
from .runtime import make_model
from .checkpoint import snapshot_input


def audit(prepared_root, splits_root, output, cohorts=("reentrancy_author", "access_control_author")):
    out = protocol_output(output)
    out.mkdir(parents=True)
    rows = []
    torch.set_num_threads(1)
    for cohort in cohorts:
        for task in ("contract", "node"):
            prepared = Path(prepared_root) / cohort / "prepared"
            splits_path = Path(splits_root) / cohort / "splits" / (task + "_folds.json")
            manifest, splits, paths, label_path, labels, graphs, invariants = load_inputs(prepared, splits_path, task)
            schemas = {}
            for v in ("E0", "E1"):
                seed_all(splits["seed"])
                model = make_model(task, paths[v], "cpu")
                schemas[v] = validate_registration(model)
                # Validate graph/features/node labels via the existing input validator.
                input_manifest = snapshot_input(model, {"graph_sha256": sha256(paths[v]),
                    "graph_labels_sha256": sha256(label_path), "protocol_version": VERSION})
                write_json(out / cohort / task / (v + "_registered_input.json"), input_manifest)
                del model
            for split in splits["folds"]:
                support = {}
                for v in ("E0", "E1"):
                    support[v] = graph_schema_and_support(graphs[v], split)
                    if support[v]["schema"] != schemas[v]:
                        raise ValueError("Structural schema differs from actual model registration")
                row = {"cohort": cohort, "task": task, "fold": split["fold"],
                       "status": "pass", "score_role": SCORE_ROLE,
                       "label_version": manifest["label_version"],
                       "train_files": len(split["train_files"]), "val_files": len(split["val_files"]),
                       "invariants": invariants, "variants": support}
                rows.append(row)
                print("AUDIT {} {} fold{} PASS train/val={}/{} unseen(E0/E1)={}/{}".format(
                    cohort, task, split["fold"], row["train_files"], row["val_files"],
                    len(support["E0"]["registered_without_train_relations"]),
                    len(support["E1"]["registered_without_train_relations"])), flush=True)
            del graphs
            gc.collect()
    summary = {"protocol": NAME, "protocol_version": VERSION, "score_role": SCORE_ROLE,
               "created_utc": utc(), "audited_main_folds": len(rows),
               "passed": sum(r["status"] == "pass" for r in rows), "blocked": 0,
               "folds_with_registered_train_unseen": sum(any(
                   a["registered_without_train_nodes"] or a["registered_without_train_relations"]
                   for a in r["variants"].values()) for r in rows),
               "E1_folds_without_any_training_DDG": sum(
                   r["variants"]["E1"]["ddg_training_edges"] == 0 for r in rows),
               "training_performed": False, "rows": rows}
    write_json(out / "summary.json", summary)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepared_root", required=True)
    p.add_argument("--splits_root", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    audit(args.prepared_root, args.splits_root, args.output)


if __name__ == "__main__":
    main()
