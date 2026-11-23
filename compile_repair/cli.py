"""CompileRepair command line; survey, revalidation and CP1 repair (PROMPTS 3.10)."""
import argparse
import json
from pathlib import Path

from compile_repair.evaluation.survey import survey, revalidate_cp0
from compile_repair.pipeline import build_index, repair


def main(argv=None, result_check=None):
    """Parse CLI arguments; an optional per-input audit may stop/seal repair."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    index = sub.add_parser("dependency-index", help="Build a sealed offline Solidity release index")
    index.add_argument("--catalog", type=Path, required=True)
    index.add_argument("--catalog-sha256", required=True)
    index.add_argument("--output", type=Path, required=True)
    cp0 = sub.add_parser("survey", help="CP0 inventory, compiler matrix and D3 survey")
    cp0.add_argument("--output", type=Path, required=True)
    cp0.add_argument("--metadata-authorization", type=Path, required=True)
    cp0.add_argument("--inventory-only", action="store_true")
    cp0.add_argument("--trusted-addition", type=Path, action="append", default=[])
    cp01 = sub.add_parser("revalidate-cp0", help="CP0.1 A3 replay of fixed CP0 versions")
    cp01.add_argument("--output", type=Path, required=True)
    cp1 = sub.add_parser("repair", help="Repair files, snippets or projects with production Slither")
    cp1.add_argument("paths", type=Path, nargs="*")
    cp1.add_argument("--snippet", type=Path, action="append", default=[])
    cp1.add_argument("--remapping", action="append", default=[])
    cp1.add_argument("--known-version")
    cp1.add_argument("--output", type=Path, required=True)
    cp1.add_argument("--order", choices=("ascending", "descending"), default="ascending")
    cp1.add_argument("--regression", choices=("mando",))
    benchmark = sub.add_parser("benchmark", help="Evaluate one CP4 source mutation or unmodified control")
    benchmark.add_argument("--catalog", type=Path, required=True)
    benchmark.add_argument("--unit-id", required=True)
    benchmark.add_argument("--operator", required=True)
    benchmark.add_argument("--seed", type=int, default=20261122)
    benchmark.add_argument("--output", type=Path, required=True)
    score = sub.add_parser("benchmark-score", help="Score graphs from a checked CP4 byte/provenance request")
    score.add_argument("--request", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "repair":
        try:
            result = repair(args.paths, args.output, args.snippet, args.known_version, args.order, args.regression,
                            result_check=result_check, remappings=args.remapping)
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
    elif args.command == "benchmark":
        from compile_repair.evaluation.benchmark import benchmark_entry
        result = benchmark_entry(args.catalog, args.unit_id, args.operator, args.output, args.seed)
    elif args.command == "benchmark-score":
        from compile_repair.evaluation.benchmark import score_request
        result = score_request(args.request, args.output)
    elif args.command == "dependency-index":
        result = build_index(args.catalog, args.output, args.catalog_sha256)
    elif args.command == "survey":
        result = survey(args.output, args.metadata_authorization, args.inventory_only, args.trusted_addition)
    elif args.command == "revalidate-cp0":
        result = revalidate_cp0(args.output)
    else:
        parser.error("a subcommand is required")
    print(json.dumps({"status": result["status"], "summary": result.get("summary"),
                      "blockers": result.get("blockers", [])}, indent=2))
    return 0 if result["status"] in ("complete", "inventory_only", "complete_a_awaiting_b_authorization") else 2


if __name__ == "__main__":
    raise SystemExit(main())
