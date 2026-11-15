"""Command line: python -m hcg {fetch,build}

    python -m hcg fetch                          # pinned SmartBugs + SolidiFI checkouts
    python -m hcg build                          # Dataset A, all seven categories
    python -m hcg build --categories reentrancy access_control --no-tokens

Outputs: <out>/<dataset>/<category>/{contract_level,line_level}.gpickle,
graph_labels.json, annotations.json, line_node_ids.json, manifest.json.
A build whose structure or contract labels differ from the dataset's reference graphs,
or whose counts differ from the paper's, exits non-zero.
"""
import argparse
import os
import sys
from pathlib import Path

from hcg.datasets import get_dataset
from hcg.pipeline import REPO, build_category
from hcg.sources import repos


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m hcg", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label-root", type=Path,
                        default=Path(os.environ.get("MANDO_DATA_DIR", REPO / "data")),
                        help="holds smartbug-dataset/ and SolidiFI-benchmark/ "
                             "(default $MANDO_DATA_DIR or <repo>/data)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fetch", help="fetch the pinned annotation repositories")
    build = commands.add_parser("build", help="build graphs for a dataset")
    build.add_argument("--dataset", default="A")
    build.add_argument("--categories", nargs="+", default=["all"])
    build.add_argument("--out", type=Path, default=REPO / "data/hcg")
    build.add_argument("--no-tokens", action="store_true",
                       help="skip tokenizer features (no Hugging Face download)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "fetch":
        for name, commit in repos.ensure(args.label_root).items():
            print("%s %s" % (name, commit))
        return 0

    dataset = get_dataset(args.dataset)
    names = ([c.name for c in dataset.categories] if args.categories == ["all"]
             else args.categories)
    tokenizer = None
    if not args.no_tokens:
        from hcg.features import load_tokenizer
        tokenizer = load_tokenizer()

    rows, failed = [], False
    for name in names:
        manifest = build_category(dataset, name, args.out, args.label_root, tokenizer)
        ref = manifest["checks"].get("reference", {})
        rows.append((name, manifest["corpus"]["contracts"],
                     manifest["corpus"]["vulnerable_contracts"],
                     manifest["contract_level"]["nodes"], manifest["contract_level"]["edges"],
                     manifest["contract_level"]["positive_nodes"],
                     manifest["line_level"]["nodes"],
                     "yes" if ref.get("structure_identical") else ("-" if not ref else "NO"),
                     len(ref.get("label_differences", [])) if ref else "-"))
        for failure in manifest["checks"]["failures"]:
            failed = True
            print("FAILED %s: %s" % (name, failure))

    header = ("category", "contracts", "vuln", "nodes", "edges", "pos.nodes", "line nodes",
              "= authors", "label diffs")
    widths = [27, 10, 6, 7, 7, 10, 11, 10, 12]
    print()
    for row in [header] + rows:
        print("".join(str(v).rjust(w) if i else str(v).ljust(w)
                      for i, (v, w) in enumerate(zip(row, widths))))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
