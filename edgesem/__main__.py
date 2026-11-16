"""Command line: python -m edgesem {build,train,report}

    python -m edgesem build                            # F4 edges + uint8[74] edge attributes (CPU)
    python -m edgesem train --out runs/edgesem/all     # P2 grouped nested CV of the EdgeSem profiles
    python -m edgesem report runs/edgesem/all

Inputs are ``python -m hcg build`` and ``python -m dfg build`` outputs (F3 = L1-L3). The store
is <edgesem>/<dataset>/<category>/<task>/; training reads it together with the DFG task
(folds, labels, node tokens) and refuses a store built from another F3 graph.
"""
import argparse
import os
from pathlib import Path

from dfg.inputs import TASKS
from edgesem.schema import PROFILES, TRAIN_PROFILES
from hcg.datasets import get_dataset

REPO = Path(__file__).resolve().parents[1]


def _common(cmd):
    cmd.add_argument("--dataset", default="A")
    cmd.add_argument("--categories", nargs="+", default=["all"])
    cmd.add_argument("--tasks", nargs="+", default=sorted(TASKS), choices=sorted(TASKS))
    cmd.add_argument("--hcg", type=Path, default=REPO / "data/hcg")
    cmd.add_argument("--dfg", type=Path, default=REPO / "data/dfg")
    cmd.add_argument("--edgesem", type=Path, default=REPO / "data/edgesem", help="EdgeSem store root")
    cmd.add_argument("--label-root", type=Path, default=Path(os.environ.get("MANDO_DATA_DIR", REPO / "data")))


def _device():
    try:
        import torch
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m edgesem", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    _common(commands.add_parser("build", help="F4 edges and edge attributes"))
    cmd = commands.add_parser("train", help="P2 grouped nested CV of EdgeSem profiles")
    _common(cmd)
    cmd.add_argument("--profiles", nargs="+", default=list(TRAIN_PROFILES), choices=sorted(PROFILES))
    cmd.add_argument("--folds", nargs="+", type=int, default=None)
    cmd.add_argument("--seed", type=int, default=1)
    cmd.add_argument("--device", default=_device())
    cmd.add_argument("--features", default="original", choices=["original", "anonymous"],
                     help="node token view; edge attributes are always original-view")
    cmd.add_argument("--epochs", type=int, default=None, help="override the 50-epoch schedule (smoke tests)")
    cmd.add_argument("--save-checkpoints", action="store_true")
    cmd.add_argument("--out", type=Path, default=REPO / "runs/edgesem/default")
    cmd = commands.add_parser("report", help="summarize a training run")
    cmd.add_argument("run", type=Path)
    cmd.add_argument("--baseline", default="G3R")
    return parser


def _categories(args):
    dataset = get_dataset(args.dataset)
    known = [c.name for c in dataset.categories]
    names = known if args.categories == ["all"] else args.categories
    unknown = [n for n in names if n not in known]
    if unknown:
        raise SystemExit("unknown categories %s for dataset %s; known: %s" % (unknown, dataset.name, ", ".join(known)))
    return dataset.name, names


def main(argv=None):
    args = build_parser().parse_args(argv)
    from dfg.train.report import report
    if args.command == "report":
        report(args.run, baseline=args.baseline)
        print((args.run / "report.md").read_text())
        return 0
    dataset, categories = _categories(args)
    if args.command == "build":
        from edgesem.pipeline import build_task
        for c in categories:
            for t in args.tasks:
                build_task(dataset, c, t, args.hcg, args.dfg, args.edgesem, args.label_root)
    elif args.command == "train":
        from edgesem.train import train
        overrides = None if args.epochs is None else dict(maximum_training_epochs=args.epochs,
                                                           schedule_epochs=args.epochs)
        train(dataset, categories, args.tasks, args.hcg, args.dfg, args.edgesem, args.label_root, args.out,
              args.profiles, args.folds, args.seed, args.device, args.features, overrides, args.save_checkpoints)
        report(args.out, baseline="G3R" if "G3R" in args.profiles else args.profiles[0])
        print((args.out / "report.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
