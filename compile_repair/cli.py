"""CompileRepair command line; CP0 dispatch only (PROMPTS 3.10)."""
import argparse
import json
from pathlib import Path

from compile_repair.evaluation.survey import survey


def main(argv=None):
    """Run a survey; exit 2 on an archived stop, never retry or overwrite."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    cp0 = sub.add_parser("survey", help="CP0 inventory, compiler matrix and D3 survey")
    cp0.add_argument("--output", type=Path, required=True)
    cp0.add_argument("--metadata-authorization", type=Path, required=True)
    cp0.add_argument("--inventory-only", action="store_true")
    cp0.add_argument("--trusted-addition", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    if args.command != "survey":
        parser.error("a subcommand is required")
    result = survey(args.output, args.metadata_authorization, args.inventory_only, args.trusted_addition)
    print(json.dumps({"status": result["status"], "summary": result.get("summary"),
                      "blockers": result.get("blockers", [])}, indent=2))
    return 0 if result["status"] in ("complete", "inventory_only") else 2


if __name__ == "__main__":
    raise SystemExit(main())
