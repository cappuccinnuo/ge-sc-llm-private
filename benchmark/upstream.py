"""The authors' own trainers (``mando.graph_classifier`` / ``mando.node_classifier``)
on the rebuilt graphs: an independent check of the ``paper`` protocol.

They are called in-process with the arguments of the smoke run, a 50-epoch schedule
by default (the dfg configuration) and their console output in ``train.log``. The
per-fold score is what their ``main`` appends after restoring the best checkpoint
(``val_results['buggy_f1_folds']`` / ``['macro_f1_folds']``), i.e. the number the
paper averages. Results go to ``<out>/upstream/<category>_<contract|line>/result.json``.
"""
import json
import statistics
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

LEVELS = {"contract": ("contract_level.gpickle", 5), "line": ("line_level.gpickle", 10)}


def _arguments(level, graph, labels, corpus, target, epochs, seed):
    argv = ["--compressed_graph", str(graph), "--dataset", str(corpus), "--testset", str(corpus),
            "--node_feature", "inside_token", "--output_models", str(target / "model.pth"),
            "--log_dir", str(target / "logs"), "--num_epochs", str(epochs),
            "--k_folds", str(LEVELS[level][1]), "--seed", str(seed), "--no_progress",
            "--non_visualize"]
    if level == "contract":
        from mando.models.classifier_cli import build_graph_parser, finalize_graph_args
        return finalize_graph_args(build_graph_parser().parse_args(argv + ["--label", str(labels)]))
    from mando.models.classifier_cli import build_node_parser, finalize_node_args
    return finalize_node_args(build_node_parser().parse_args(argv))


def run(hcg_dir, corpus, category, out_root, epochs=50, seed=1, levels=tuple(LEVELS), log=print):
    """Train each level once (skipped when its result exists); return the result records."""
    import torch
    records = []
    for level in levels:
        target = Path(out_root) / "upstream" / ("%s_%s" % (category, level))
        done = target / "result.json"
        if done.is_file():
            record = json.loads(done.read_text())
            if (record["epochs"], record["seed"]) != (epochs, seed):
                raise ValueError("%s was trained with %d epochs, seed %d; use another --out"
                                 % (target, record["epochs"], record["seed"]))
            records.append(record)
            continue
        target.mkdir(parents=True, exist_ok=True)
        args = _arguments(level, Path(hcg_dir) / LEVELS[level][0], Path(hcg_dir) / "graph_labels.json",
                          corpus, target, epochs, seed)
        log("[upstream] %s_%s: %d folds on %s" % (category, level, args["k_folds"], args["device"]))
        if level == "contract":
            from mando.graph_classifier import main
        else:
            from mando.node_classifier import main
        torch.manual_seed(seed)
        with open(target / "train.log", "w") as stream, redirect_stdout(stream), redirect_stderr(stream):
            _, val = main(args)
        folds = []
        for fold, (buggy, macro) in enumerate(zip(val["buggy_f1_folds"], val["macro_f1_folds"])):
            selection = json.loads((target / ("model_fold%d" % fold) / "selection.json").read_text())
            folds.append(dict(fold=fold, buggy_f1=100.0 * float(buggy), macro_f1=100.0 * float(macro),
                              best_epoch=selection["best_epoch"], last_epoch=selection["last_epoch"],
                              outer_test_files=sorted(selection["val_files"])))
        record = dict(category=category, level=level, seed=seed, epochs=epochs, k_folds=args["k_folds"],
                      device=str(args["device"]), folds=folds,
                      buggy_f1=statistics.mean(f["buggy_f1"] for f in folds),
                      macro_f1=statistics.mean(f["macro_f1"] for f in folds))
        done.write_text(json.dumps(record, indent=2) + "\n")
        log("[upstream] %s_%s: buggy F1 %.2f, macro F1 %.2f" % (category, level, record["buggy_f1"],
                                                                record["macro_f1"]))
        records.append(record)
    return records
