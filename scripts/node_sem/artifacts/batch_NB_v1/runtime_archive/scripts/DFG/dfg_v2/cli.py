"""Build and verify the sealed DFG v2 graph store without training."""
import argparse
import json

from .store import build_store, verify_store


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Build requested fixed graph layers and register CPU model schemas")
    build.add_argument("--manifest", required=True, help="Sealed inputs/manifest.json")
    build.add_argument("--tasks", help="Comma-separated task IDs; default all tasks in the sealed input manifest")
    build.add_argument("--graph-keys", default="F1,F2,F3",
        help="Comma-separated graph keys to save; F0 is always referenced. Required earlier layers are computed but not saved unless requested.")
    build.add_argument("--output", required=True, help="New directory; an existing directory is never overwritten")
    build.add_argument("--max-iterations", type=int, default=100000)
    verify = commands.add_parser("verify", help="Verify input seal, graph data, audits and registered schemas")
    verify.add_argument("--store", required=True, help="Sealed graph store.json")
    args = parser.parse_args(argv)
    if args.command == "build":
        result = build_store(args.manifest, tasks=args.tasks, graph_keys=args.graph_keys,
                             output=args.output, max_iterations=args.max_iterations)
        answer = dict(status=result["status"], tasks=len(result["tasks"]),
            graphs=result["graph_keys_produced"], model_constructions=result["model_constructions"],
            model_forward_executed=False, training_executed=False)
    else:
        answer = verify_store(args.store)
    print(json.dumps(answer, ensure_ascii=False, sort_keys=True), flush=True)
    return answer


if __name__ == "__main__":
    main()
