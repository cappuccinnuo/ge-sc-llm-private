"""Command line: python -m benchmark {run,report}

    python -m benchmark run --out runs/benchmark/full            # 7 categories, all protocols, G0
    python -m benchmark run --out runs/benchmark/try --categories reentrancy --folds 0 --epochs 2
    python -m benchmark report runs/benchmark/full

run trains what is missing (finished fits are skipped, so an interrupted run resumes),
then scores the run and writes evaluation.json, report.md and findings/. It reads the
graphs of ``python -m hcg build`` (and, for profiles other than G0, of
``python -m dfg build``). Protocols: ``paper`` and ``grouped`` train the contract,
line and cascade tracks with the dfg engine; ``upstream`` runs the authors' trainers.
"""
import argparse
import os
from pathlib import Path

from benchmark import evaluate, report, tracks, upstream
from dfg.schema import PROFILES
from dfg.train.trainer import task_config
from hcg.datasets import get_dataset

REPO = Path(__file__).resolve().parents[1]
PROTOCOLS = tracks.PROTOCOLS + ("upstream",)


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m benchmark", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("run", help="train what is missing, then score and report")
    cmd.add_argument("--out", type=Path, required=True, help="run directory, e.g. runs/benchmark/full")
    cmd.add_argument("--protocols", nargs="+", default=list(PROTOCOLS), choices=PROTOCOLS)
    cmd.add_argument("--profiles", nargs="+", default=["G0"], choices=sorted(PROFILES),
                     help="dfg profiles of the paper/grouped tracks (default: the MANDO-LLM baseline G0)")
    cmd.add_argument("--folds", nargs="+", type=int, default=None,
                     help="fold indices of the paper/grouped tracks (default: all); upstream runs all folds")
    cmd.add_argument("--epochs", type=int, default=None, help="override the 50-epoch schedule (smoke runs)")
    cmd.add_argument("--seed", type=int, default=1)
    cmd.add_argument("--device", default="cuda:0" if _cuda() else "cpu",
                     help="device of the paper/grouped tracks; the authors' trainers pick the GPU when present")
    _common(cmd)
    cmd = commands.add_parser("report", help="score a run and write report.md")
    cmd.add_argument("run", type=Path)
    _common(cmd)
    return parser


def _common(cmd):
    cmd.add_argument("--dataset", default="A")
    cmd.add_argument("--categories", nargs="+", default=["all"])
    cmd.add_argument("--hcg", type=Path, default=REPO / "data/hcg", help="hcg build output root")
    cmd.add_argument("--dfg", type=Path, default=REPO / "data/dfg", help="dfg build output root")
    cmd.add_argument("--label-root", type=Path,
                     default=Path(os.environ.get("MANDO_DATA_DIR", REPO / "data")),
                     help="holds smartbug-dataset/ (default $MANDO_DATA_DIR or <repo>/data)")


def _cuda():
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _categories(args):
    dataset = get_dataset(args.dataset)
    known = [c.name for c in dataset.categories]
    names = known if args.categories == ["all"] else args.categories
    unknown = [n for n in names if n not in known]
    if unknown:
        raise SystemExit("unknown categories %s; known: %s" % (unknown, ", ".join(known)))
    return dataset, names


def run(args):
    dataset, names = _categories(args)
    roots = tracks.Roots(args.hcg, args.dfg, args.label_root)
    overrides = None if args.epochs is None else dict(maximum_training_epochs=args.epochs,
                                                       schedule_epochs=args.epochs)
    settings = dict(protocols=args.protocols, profiles=args.profiles, folds=args.folds, seed=args.seed,
                    epochs=args.epochs, device=str(args.device), categories=names)
    tracks.run_manifest(args.out, dataset.name, names, roots, settings)
    epochs = args.epochs or task_config("node")["maximum_training_epochs"]
    for category in names:
        engine = [p for p in args.protocols if p in tracks.PROTOCOLS]
        if engine:
            data = tracks.CategoryData(dataset.name, category, roots)
            for protocol in engine:
                tracks.train(data.tracks(protocol, args.seed), args.out, args.profiles, args.folds,
                             args.seed, args.device, overrides)
        if "upstream" in args.protocols:
            upstream.run(Path(args.hcg) / dataset.name / category, dataset.corpus(REPO, category),
                         category, args.out, epochs, args.seed)
    return _report(args.out, args.hcg, dataset.name, names)


def _report(run_dir, hcg_root, dataset, names):
    evaluation = evaluate.evaluate(run_dir, hcg_root, dataset, names)
    print(report.write(run_dir, evaluation))
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return run(args)
    dataset, names = _categories(args)
    return _report(args.run, args.hcg, dataset.name, names)


if __name__ == "__main__":
    raise SystemExit(main())
