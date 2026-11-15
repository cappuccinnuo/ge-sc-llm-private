"""Build contract- and line-level graphs for any of the seven categories from raw .sol.

    bash scripts/graph_build/fetch_labels.sh          # once: SmartBugs + SolidiFI labels
    python -m scripts.graph_build                     # all seven, with tokenizer features
    python -m scripts.graph_build --categories reentrancy access_control --no_tokens

Label sources are read from --label_root (default $MANDO_DATA_DIR, else <repo>/data).
Outputs go next to each category's source_files/ (see scripts/graph_build/pipeline.py).
With --check, every category must reproduce the paper's Table 1 counts (contracts,
buggy contracts, nodes, edges) and this pipeline's recorded baseline (buggy nodes,
line-level nodes) exactly, or the command exits non-zero.
"""
import argparse
import os
import sys
from pathlib import Path

from scripts.graph_build.categories import expected, resolve
from scripts.graph_build.pipeline import DATASET_ROOT, REPO, build_category, check_expected


def build_parser():
    p = argparse.ArgumentParser(prog="python -m scripts.graph_build", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--categories", nargs="+", default=["all"],
                   help="Category names, or 'all' (default)")
    p.add_argument("--label_root",
                   default=os.environ.get("MANDO_DATA_DIR", str(REPO / "data")),
                   help="Directory holding smartbug-dataset/ and SolidiFI-benchmark/")
    p.add_argument("--out_root", default=str(DATASET_ROOT),
                   help="Per-category output root (default: next to source_files/)")
    p.add_argument("--work_root", default=None,
                   help="Where per-contract CFG pickles go (default <out>/<cat>/_build)")
    p.add_argument("--no_tokens", action="store_true",
                   help="Skip tokenizer features (no HuggingFace download needed)")
    p.add_argument("--tokenizer", default="Salesforce/codet5p-770m")
    p.add_argument("--scheme", choices=("ids", "hashed_bow", "ids_norm"), default="ids")
    p.add_argument("--feature_size", type=int, default=512)
    p.add_argument("--solidifi_lines", choices=("range", "start"), default="range")
    p.add_argument("--check", action="store_true",
                   help="Fail unless every category reproduces the paper and baseline counts")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    categories = resolve(args.categories)

    tokenizer = None
    if not args.no_tokens:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)

    failures = []
    rows = []
    for category in categories:
        r = build_category(category, args.label_root, args.out_root, args.work_root,
                           tokenizer=tokenizer, tokenizer_name=args.tokenizer,
                           scheme=args.scheme, feature_size=args.feature_size,
                           solidifi_lines=args.solidifi_lines)
        cl = r["contract_level"]
        rows.append(f"{category.name:<27}{cl['contracts']:>10}{r['graph_labels']['buggy']:>7}"
                    f"{r['graph_labels']['clean']:>7}{cl['nodes']:>8}{cl['edges']:>8}"
                    f"{cl['buggy_nodes']:>13}{r['line_level']['nodes']:>12}")
        problems = []
        if r["parse_failures"]:
            problems.append(f"{len(r['parse_failures'])} parse failures")
        if cl["contracts"] != category.contracts:
            problems.append(f"{cl['contracts']} contracts in graph, corpus has "
                            f"{category.contracts}")
        if args.check and args.solidifi_lines == "range":
            problems += check_expected(r, expected(category.name))
        if cl["annotated_but_no_node_hit"]:
            print(f"  note [{category.name}]: annotated but no node hit: "
                  f"{cl['annotated_but_no_node_hit']}")
        failures += [f"{category.name}: {p}" for p in problems]

    header = (f"{'category':<27}{'contracts':>10}{'buggy':>7}{'clean':>7}"
              f"{'nodes':>8}{'edges':>8}{'buggy nodes':>13}{'line nodes':>12}")
    print("\n".join(["", header, *rows]))
    if failures:
        print("\nFAILED:\n  " + "\n  ".join(failures))
        return 1
    print("\nall categories built")
    return 0


if __name__ == "__main__":
    sys.exit(main())
