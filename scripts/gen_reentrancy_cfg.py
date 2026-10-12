"""Batch-generate tree-sitter CFGs for the reentrancy dataset.

This script exists because the repository ships pre-built
`experiments/ge-sc-data/source_code/<bug>/cfg/*.dot` files but never checked in
the batch driver that produced them (only the library functions in
`process_graphs.tree_sitter_codeviews.generator` and a unit test that calls
them in-memory). Use this to (re)generate CFGs from raw .sol source as the
first concrete step of an end-to-end "from source" reproduction, and to sanity
check the regenerated graphs against the ones already in the repo.

Usage:
    python scripts/gen_reentrancy_cfg.py \
        --source_dir experiments/ge-sc-data/source_code/reentrancy/source_files \
        --output_dir experiments/ge-sc-data/source_code/reentrancy/cfg_regen

    # Compare against the repo's shipped cfg/ directory instead of just writing:
    python scripts/gen_reentrancy_cfg.py --compare_dir experiments/ge-sc-data/source_code/reentrancy/cfg
"""
import argparse
import sys
import traceback
from pathlib import Path

import networkx as nx

from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_file
from process_graphs.tree_sitter_codeviews.utils.postprocessor import write_to_dot


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source_dir",
        default="experiments/ge-sc-data/source_code/reentrancy/source_files",
        help="Directory of raw .sol files to parse",
    )
    parser.add_argument(
        "--output_dir",
        default="experiments/ge-sc-data/source_code/reentrancy/cfg_regen",
        help="Where to write regenerated .dot/.gpickle CFGs",
    )
    parser.add_argument(
        "--compare_dir",
        default=None,
        help="If set, diff node/edge counts against existing .dot files here "
        "(e.g. the repo-shipped experiments/ge-sc-data/source_code/reentrancy/cfg)",
    )
    parser.add_argument(
        "--no_gpickle",
        action="store_true",
        help="Skip writing the per-contract .gpickle (only emit .dot)",
    )
    return parser


def load_existing_dot(path):
    """Read a previously generated .dot back into a MultiDiGraph for comparison.

    networkx's pydot reader materializes a spurious attribute-less node named '\\n'
    from the dot body, which would otherwise inflate every node count by one. Drop
    any node that carries no attributes and is not a real graph node.
    """
    graph = nx.MultiDiGraph(nx.nx_pydot.read_dot(path))
    spurious = [n for n, d in graph.nodes(data=True) if not d and n.strip() in ("", "\\n")]
    graph.remove_nodes_from(spurious)
    return graph


def main():
    args = build_parser().parse_args()
    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sol_files = sorted(source_dir.glob("*.sol"))
    if not sol_files:
        print(f"No .sol files found under {source_dir}")
        sys.exit(1)

    print(f"Found {len(sol_files)} .sol files in {source_dir}")

    ok, failed = 0, []
    compare_rows = []

    for sol_path in sol_files:
        stem = sol_path.stem
        try:
            graph = generate_cfg_from_file(sol_path)
        except Exception as exc:  # noqa: BLE001 - we want to keep going and report all failures
            failed.append((sol_path.name, repr(exc)))
            continue

        dot_path = output_dir / f"{stem}.dot"
        write_to_dot(graph, str(dot_path))
        if not args.no_gpickle:
            nx.write_gpickle(graph, str(output_dir / f"{stem}.gpickle"))
        ok += 1

        if args.compare_dir:
            existing_path = Path(args.compare_dir) / f"{stem}.dot"
            if existing_path.exists():
                try:
                    existing_graph = load_existing_dot(existing_path)
                    compare_rows.append(
                        (
                            stem,
                            graph.number_of_nodes(),
                            existing_graph.number_of_nodes(),
                            graph.number_of_edges(),
                            existing_graph.number_of_edges(),
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    compare_rows.append((stem, "ERROR", repr(exc), "-", "-"))
            else:
                compare_rows.append((stem, "no existing dot", "-", "-", "-"))

    print(f"\nGenerated {ok}/{len(sol_files)} CFGs into {output_dir}")
    if failed:
        print(f"\n{len(failed)} contract(s) failed to parse:")
        for name, err in failed:
            print(f"  - {name}: {err}")

    if args.compare_dir:
        print(f"\nComparison against {args.compare_dir} (new_nodes/old_nodes, new_edges/old_edges):")
        mismatches = 0
        for stem, n_new, n_old, e_new, e_old in compare_rows:
            match = (n_new == n_old and e_new == e_old)
            if not match:
                mismatches += 1
            flag = "OK" if match else "DIFF"
            print(f"  [{flag}] {stem}: nodes {n_new}/{n_old} edges {e_new}/{e_old}")
        print(f"\n{len(compare_rows) - mismatches}/{len(compare_rows)} contracts match exactly")


if __name__ == "__main__":
    main()
