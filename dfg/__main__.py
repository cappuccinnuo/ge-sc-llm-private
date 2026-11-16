"""Command line: python -m dfg {build,train,report}

    python -m dfg build                                  # Dataset A, 7 categories, both tasks
    python -m dfg build --categories reentrancy --tasks node
    python -m dfg train --out runs/dfg/all --device cuda:0
    python -m dfg train --categories reentrancy --tasks node --profiles G0 G3R --folds 0 1
    python -m dfg report runs/dfg/all

build reads <hcg>/<dataset>/<category>/{contract_level,line_level}.gpickle written by
``python -m hcg build`` and writes <dfg>/<dataset>/<category>/<task>/F*/ plus
summary.json. L3 requires HCG node tokens (an HCG built without --no-tokens).
train runs grouped nested cross-validation of the requested profiles and writes
<out>/<task_id>/fold_<k>/<profile>/result.json; rerunning skips finished fits.
"""
import argparse
import os
from pathlib import Path

from dfg.inputs import REPO, TASKS
from dfg.store import ALL_LAYERS, build
from dfg.train.runner import ALL_PROFILES
from hcg.datasets import get_dataset


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m dfg", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("build", help="augment HCG graphs with DFG layers")
    cmd.add_argument("--layers", nargs="+", default=list(ALL_LAYERS), choices=ALL_LAYERS)
    cmd.add_argument("--out", type=Path, default=REPO / "data/dfg")
    _common(cmd)
    cmd = commands.add_parser("train", help="grouped nested CV of DFG profiles")
    _common(cmd)
    cmd.add_argument("--dfg", type=Path, default=REPO / "data/dfg", help="dfg build output root")
    cmd.add_argument("--out", type=Path, default=REPO / "runs/dfg/default")
    cmd.add_argument("--profiles", nargs="+", default=list(ALL_PROFILES), choices=ALL_PROFILES)
    cmd.add_argument("--folds", nargs="+", type=int, default=None, help="default: all folds")
    cmd.add_argument("--seed", type=int, default=1)
    cmd.add_argument("--device", default="cuda:0" if _cuda() else "cpu")
    cmd.add_argument("--features", choices=("original", "anonymous"), default="original",
                     help="node tokens from original code (default) or identifier-anonymized code")
    cmd.add_argument("--epochs", type=int, default=None, help="override the 50-epoch schedule")
    cmd.add_argument("--save-checkpoints", action="store_true")
    cmd = commands.add_parser("report", help="summarize a training run")
    cmd.add_argument("run", type=Path)
    return parser


def _cuda():
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _common(cmd):
    cmd.add_argument("--dataset", default="A")
    cmd.add_argument("--categories", nargs="+", default=["all"])
    cmd.add_argument("--tasks", nargs="+", default=sorted(TASKS), choices=sorted(TASKS))
    cmd.add_argument("--hcg", type=Path, default=REPO / "data/hcg", help="hcg build output root")
    cmd.add_argument("--label-root", type=Path,
                     default=Path(os.environ.get("MANDO_DATA_DIR", REPO / "data")),
                     help="holds smartbug-dataset/ (default $MANDO_DATA_DIR or <repo>/data)")


def _categories(args):
    dataset = get_dataset(args.dataset)
    known = [c.name for c in dataset.categories]
    names = known if args.categories == ["all"] else args.categories
    unknown = [n for n in names if n not in known]
    if unknown:
        raise SystemExit("unknown categories %s for dataset %s; known: %s"
                         % (unknown, dataset.name, ", ".join(known)))
    return dataset, names


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "report":
        from dfg.train.report import report
        report(args.run)
        print((args.run / "report.md").read_text())
        return 0
    if args.command == "train":
        from dfg.train.runner import train
        dataset, names = _categories(args)
        overrides = None if args.epochs is None else dict(maximum_training_epochs=args.epochs,
                                                           schedule_epochs=args.epochs)
        train(dataset.name, names, args.tasks, args.hcg, args.dfg, args.label_root, args.out,
              args.profiles, args.folds, args.seed, args.device, args.features, overrides,
              args.save_checkpoints)
        from dfg.train.report import report
        report(args.out)
        print((args.out / "report.md").read_text())
        return 0
    layers = tuple(layer for layer in ALL_LAYERS if layer in args.layers)
    if layers != ALL_LAYERS[:len(layers)]:
        raise SystemExit("layers are cumulative: choose L1, L1 L2 or L1 L2 L3")
    dataset, names = _categories(args)
    results = build(dataset.name, names, args.tasks, args.hcg, args.out, args.label_root, layers)

    header = ("task", "files", "versioned", "L1 fallback", "nodes", "edges", "seconds")
    rows = []
    for task_id, s in results.items():
        last = s["graphs"]["F%d" % len(layers)]
        rows.append((task_id, s["files"], s["files_with_recorded_version"],
                     last["coverage"]["L1"]["file_fallbacks"], last["nodes"], last["edges"], s["seconds"]))
    widths = [34, 6, 10, 12, 8, 8, 8]
    print()
    for row in [header] + rows:
        print("".join(str(v).ljust(w) for v, w in zip(row, widths)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
