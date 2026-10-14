"""Read-only completed E23 archive verification across descendant Git commits.

Run as python -B -m scripts.verify_e23_archive in the development worktree.
Requires local frozen graphs, initial weights and checkpoints.
"""
import argparse
import subprocess
from pathlib import Path

from scripts.DFG.experiments.e23_pilot import control


def verify(output):
    output = Path(output)
    plan_path = output / "plan.json"
    plan = control.read_json(plan_path)
    seal = control.read_json(output / "plan.seal.json")
    if control.sha256(plan_path) != seal["sha256"]:
        raise ValueError("Pilot plan seal changed")
    if plan["format"] != control.EXPERIMENT_VERSION or plan["device"] != "cuda:0":
        raise ValueError("Wrong experiment/device policy")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", plan["base_git_head"], "HEAD"],
        cwd=str(control.ROOT), check=True,
    )
    if control.runtime_hashes() != plan["runtime_code_sha256"]:
        raise ValueError("Runtime source drift")
    control.check_hashes(plan["frozen_files"])
    expected = {(task, variant) for task in control.TASK_ORDER
                for variant in control.VARIANTS}
    actual = {(job["task_id"], job["variant"]) for job in plan["jobs"]}
    if len(plan["jobs"]) != 12 or actual != expected:
        raise ValueError("Unexpected pilot job population")
    counts = {}
    for mode in ("smoke", "full"):
        counts[mode] = sum(
            control.existing_success(output, job, mode, plan)[0] is not None
            for job in plan["jobs"]
        )
    if counts != {"smoke": 12, "full": 12}:
        raise ValueError("Archive is incomplete: " + str(counts))
    if control.sha256(plan_path) != seal["sha256"]:
        raise ValueError("Plan changed during verification")
    if control.runtime_hashes() != plan["runtime_code_sha256"]:
        raise ValueError("Runtime changed during verification")
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(control.DEFAULT_OUTPUT))
    args = parser.parse_args()
    print(verify(args.output))


if __name__ == "__main__":
    main()
