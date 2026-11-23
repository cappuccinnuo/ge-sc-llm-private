"""Command line: python -m combined compare

    python -m combined compare --dataset B --runs runs/method/b_s1 runs/method/b_s2 runs/method/b_s3 \\
        --out runs/method

Training is ``python -m benchmark run ... --profiles G0 FULL`` (one directory per
seed); ``compare`` pairs FULL with G0 over those runs and writes compare.json and
compare.md (``combined.compare``).
"""
import argparse
import json
from pathlib import Path

from combined import compare
from hcg.datasets import get_dataset

REPO = Path(__file__).resolve().parents[1]


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m combined", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("compare", help="FULL vs G0 over seeds (paired tests)")
    cmd.add_argument("--runs", nargs="+", type=Path, required=True, help="benchmark run directories, one per seed")
    cmd.add_argument("--out", type=Path, required=True)
    cmd.add_argument("--dataset", default="B")
    cmd.add_argument("--categories", nargs="+", default=["all"])
    cmd.add_argument("--hcg", type=Path, default=REPO / "data/hcg", help="hcg build output root the runs used")
    return parser


def seed_of(run):
    path = Path(run) / "run.json"
    if not path.is_file():
        raise SystemExit("%s is not a benchmark run (no run.json)" % run)
    return json.loads(path.read_text())["settings"]["seed"]


def main(argv=None):
    args = build_parser().parse_args(argv)
    dataset = get_dataset(args.dataset)
    known = [c.name for c in dataset.categories]
    names = known if args.categories == ["all"] else args.categories
    if set(names) - set(known):
        raise SystemExit("unknown categories %s" % sorted(set(names) - set(known)))
    runs = {}
    for run in args.runs:
        seed = seed_of(run)
        if seed in runs:
            raise SystemExit("seed %s appears in two runs: %s and %s" % (seed, runs[seed], run))
        runs[seed] = run
    print(compare.write(compare.compare(runs, args.hcg, dataset.name, names), args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
