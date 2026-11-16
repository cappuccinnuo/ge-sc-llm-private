"""Command line: python -m nodesem {analyze,encode,describe,train,report}

    python -m nodesem analyze                  # facts, CODE text, CTX fields, STATIC (CPU)
    python -m nodesem encode                   # CodeT5+ CODE/CTX vectors (GPU recommended)
    python -m nodesem describe                 # Qwen2.5-Coder-3B descriptions -> teacher text (GPU)
    python -m nodesem encode --teacher         # BGE teacher vectors
    python -m nodesem train --configs S0o S2 S4 S6 S5 S8 --out runs/nodesem/all
    python -m nodesem report runs/nodesem/all

Inputs are ``python -m hcg build`` and ``python -m dfg build`` outputs (L1-L3). The
feature store is <nodesem>/<dataset>/<category>/<task>/; LLM responses are cached in
<nodesem>/llm_cache and reused across runs (an existing cache can be copied there).
"""
import argparse
import os
from pathlib import Path

from dfg.inputs import TASKS
from hcg.datasets import get_dataset
from nodesem.features import CONFIGS

REPO = Path(__file__).resolve().parents[1]


def _common(cmd):
    cmd.add_argument("--dataset", default="A")
    cmd.add_argument("--categories", nargs="+", default=["all"])
    cmd.add_argument("--tasks", nargs="+", default=sorted(TASKS), choices=sorted(TASKS))
    cmd.add_argument("--hcg", type=Path, default=REPO / "data/hcg")
    cmd.add_argument("--dfg", type=Path, default=REPO / "data/dfg")
    cmd.add_argument("--nodesem", type=Path, default=REPO / "data/nodesem", help="feature store root")
    cmd.add_argument("--label-root", type=Path, default=Path(os.environ.get("MANDO_DATA_DIR", REPO / "data")))


def _device():
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m nodesem", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    _common(commands.add_parser("analyze", help="facts, CODE text, CTX fields, STATIC vectors"))
    cmd = commands.add_parser("encode", help="CodeT5+ CODE/CTX vectors, or BGE teacher vectors")
    _common(cmd)
    cmd.add_argument("--teacher", action="store_true", help="encode teacher text (after describe)")
    cmd.add_argument("--device", default=_device())
    cmd.add_argument("--batch-size", type=int, default=32)
    cmd.add_argument("--model-cache", type=Path, default=None, help="Hugging Face cache directory")
    cmd = commands.add_parser("describe", help="LLM descriptions -> teacher text")
    _common(cmd)
    cmd.add_argument("--cache", type=Path, default=None, help="response cache (default <nodesem>/llm_cache)")
    cmd.add_argument("--model-cache", type=Path, default=None, help="Hugging Face cache for the GGUF")
    cmd = commands.add_parser("train", help="grouped nested CV of feature configurations")
    _common(cmd)
    cmd.add_argument("--configs", nargs="+", default=["S0o", "S2", "S4"], choices=sorted(CONFIGS))
    cmd.add_argument("--profiles", nargs="+", default=["G0", "G3R"], choices=["G0", "G3R"])
    cmd.add_argument("--folds", nargs="+", type=int, default=None)
    cmd.add_argument("--seed", type=int, default=1)
    cmd.add_argument("--device", default="cuda:0" if _device() == "cuda" else "cpu")
    cmd.add_argument("--epochs", type=int, default=None, help="override the 50-epoch schedule")
    cmd.add_argument("--out", type=Path, default=REPO / "runs/nodesem/default")
    cmd = commands.add_parser("report", help="summarize a training run")
    cmd.add_argument("run", type=Path)
    cmd.add_argument("--baseline", default="S0o@G3R")
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
    if args.command == "report":
        from dfg.train.report import report
        report(args.run, baseline=args.baseline)
        print((args.run / "report.md").read_text())
        return 0
    dataset, categories = _categories(args)
    pairs = [(c, t) for c in categories for t in args.tasks]
    if args.command == "analyze":
        from nodesem.pipeline import analyze_task
        for c, t in pairs:
            analyze_task(dataset, c, t, args.hcg, args.dfg, args.nodesem, args.label_root)
    elif args.command == "encode":
        from nodesem.pipeline import encode_task
        from nodesem.store import TaskStore
        for c, t in pairs:
            encode_task(TaskStore(args.nodesem, dataset, c, t), args.device, args.batch_size,
                        args.model_cache, args.teacher)
    elif args.command == "describe":
        from nodesem.inputs import load_context
        from nodesem.pipeline import describe_tasks
        from nodesem.store import TaskStore
        items = [(load_context(dataset, c, t, args.hcg, args.dfg, args.label_root), TaskStore(args.nodesem, dataset, c, t))
                 for c, t in pairs]
        describe_tasks(items, args.cache or args.nodesem / "llm_cache", model_cache=args.model_cache)
    elif args.command == "train":
        from dfg.train.report import report
        from nodesem.train import train
        overrides = None if args.epochs is None else dict(maximum_training_epochs=args.epochs,
                                                           schedule_epochs=args.epochs)
        train(dataset, categories, args.tasks, args.hcg, args.dfg, args.nodesem, args.label_root, args.out,
              args.configs, args.profiles, args.folds, args.seed, args.device, overrides)
        report(args.out, baseline="S0o@G3R")
        print((args.out / "report.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
