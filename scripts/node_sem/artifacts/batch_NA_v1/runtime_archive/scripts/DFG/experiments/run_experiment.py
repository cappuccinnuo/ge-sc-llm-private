"""Versioned entry point. Main default: paper_kfold; nested_strict is opt-in."""
import argparse
from .common import write_json
from .paper_protocol import INITIALIZATION_VERSION, protocol_output


def run(args):
    if args.protocol == "paper_kfold":
        from .paper_run import run as execute
        return execute(args)
    if args.protocol != "nested_strict":
        raise ValueError("Unknown experiment protocol")
    # Alias only: do not relax or modify any legacy nested implementation.
    output = protocol_output(args.output, "nested_strict")
    from .run_pair import run as execute
    result = execute(args)
    write_json(output / "protocol_alias.json", {
        "protocol": "nested_strict", "protocol_version": "ddg-nested-paired-v1",
        "initialization_version": INITIALIZATION_VERSION,
        "forward_scope": "isolated_file_subgraphs", "score_role": "independent_outer_test",
        "legacy_runner_unmodified": True})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--protocol", choices=("paper_kfold", "nested_strict"), default="paper_kfold")
    p.add_argument("--prepared", required=True)
    p.add_argument("--splits", required=True)
    p.add_argument("--task", choices=("node", "contract"), required=True)
    p.add_argument("--mode", choices=("smoke", "full"), default="smoke")
    p.add_argument("--fold", type=int, default=0)
    p.add_argument("--all_folds", action="store_true")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--smoke_epochs", type=int, default=3)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--device", default="cpu")
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    if args.all_folds:
        if args.mode != "full":
            p.error("--all_folds requires --mode full")
        args.fold = None
    run(args)


if __name__ == "__main__":
    main()
