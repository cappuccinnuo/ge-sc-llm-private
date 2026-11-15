"""CompileRepair command line; survey, revalidation and CP1 repair (PROMPTS 3.10)."""
import argparse
import json
from pathlib import Path

from compile_repair.evaluation.survey import survey, revalidate_cp0
from compile_repair.pipeline import repair


def main(argv=None, result_check=None):
    """Parse CLI arguments; an optional per-input audit may stop/seal repair."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    cp0 = sub.add_parser("survey", help="CP0 inventory, compiler matrix and D3 survey")
    cp0.add_argument("--output", type=Path, required=True)
    cp0.add_argument("--metadata-authorization", type=Path, required=True)
    cp0.add_argument("--inventory-only", action="store_true")
    cp0.add_argument("--trusted-addition", type=Path, action="append", default=[])
    cp01 = sub.add_parser("revalidate-cp0", help="CP0.1 A3 replay of fixed CP0 versions")
    cp01.add_argument("--output", type=Path, required=True)
    cp1 = sub.add_parser("repair", help="Repair single files or snippets with production Slither")
    cp1.add_argument("paths", type=Path, nargs="*")
    cp1.add_argument("--snippet", type=Path, action="append", default=[])
    cp1.add_argument("--known-version")
    cp1.add_argument("--output", type=Path, required=True)
    cp1.add_argument("--order", choices=("ascending", "descending"), default="ascending")
    cp1.add_argument("--regression", choices=("mando",))
    args = parser.parse_args(argv)
    if args.command == "repair":
        try:
            result = repair(args.paths, args.output, args.snippet, args.known_version, args.order, args.regression,
                            result_check=result_check)
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
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
