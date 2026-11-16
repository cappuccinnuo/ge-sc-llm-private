"""Command line: python -m dfg build

    python -m dfg build                                  # Dataset A, 7 categories, both tasks
    python -m dfg build --categories reentrancy --tasks node
    python -m dfg build --layers L1 L2                   # no L3 (needs no tokenizer)

Reads <hcg>/<dataset>/<category>/{contract_level,line_level}.gpickle written by
``python -m hcg build`` and writes <out>/<dataset>/<category>/<task>/F*/ plus
summary.json. L3 requires HCG node tokens (an HCG built without --no-tokens).
"""
import argparse
import os
from pathlib import Path

from dfg.inputs import REPO, TASKS
from dfg.store import ALL_LAYERS, build
from hcg.datasets import get_dataset


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m dfg", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("build", help="augment HCG graphs with DFG layers")
    cmd.add_argument("--dataset", default="A")
    cmd.add_argument("--categories", nargs="+", default=["all"])
    cmd.add_argument("--tasks", nargs="+", default=sorted(TASKS), choices=sorted(TASKS))
    cmd.add_argument("--layers", nargs="+", default=list(ALL_LAYERS), choices=ALL_LAYERS)
    cmd.add_argument("--hcg", type=Path, default=REPO / "data/hcg", help="hcg build output root")
    cmd.add_argument("--out", type=Path, default=REPO / "data/dfg")
    cmd.add_argument("--label-root", type=Path,
                     default=Path(os.environ.get("MANDO_DATA_DIR", REPO / "data")),
                     help="holds smartbug-dataset/ (default $MANDO_DATA_DIR or <repo>/data)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    layers = tuple(layer for layer in ALL_LAYERS if layer in args.layers)
    if layers != ALL_LAYERS[:len(layers)]:
        raise SystemExit("layers are cumulative: choose L1, L1 L2 or L1 L2 L3")
    dataset = get_dataset(args.dataset)
    known = [c.name for c in dataset.categories]
    names = known if args.categories == ["all"] else args.categories
    unknown = [n for n in names if n not in known]
    if unknown:
        raise SystemExit("unknown categories %s for dataset %s; known: %s"
                         % (unknown, dataset.name, ", ".join(known)))
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
