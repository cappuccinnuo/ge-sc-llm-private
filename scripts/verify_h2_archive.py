"""Verify a completed H2 archive without changing execution guards or training."""
import argparse
import subprocess
from pathlib import Path
from scripts.DFG.experiments.e23_h2 import control as c


def verify(output):
    output = Path(output)
    plan = c.read_json(output / "plan.json")
    seal = c.read_json(output / "plan.seal.json")["sha256"]
    if c.sha256(output / "plan.json") != seal:
        raise ValueError("H2 seal drift")
    if plan["format"] != c.BATCH_VERSION or not plan["execution_authorized"] or plan["device"] != "cuda:0":
        raise ValueError("Wrong H2 policy")
    subprocess.run(["git", "merge-base", "--is-ancestor", plan["base_git_head"], "HEAD"],
                   cwd=str(c.ROOT), check=True)
    if plan["runtime_code_sha256"] != c.runtime_hashes():
        raise ValueError("Runtime source drift")
    c.validate_jobs(plan)
    c.check_hashes(plan["frozen_files"])
    reserved = c.read_json(plan["reserved_h2_plan"])
    if reserved["execution_authorized"] or reserved["jobs"] != plan["jobs"]:
        raise ValueError("Historical reserved plan changed")
    fresh = reused = 0
    for job in plan["jobs"]:
        folder, _ = c.locate(output, job, plan)
        if folder is None:
            raise ValueError("Incomplete archive: " + c.identity(job))
        if job["fold"] == 0:
            reused += 1
        else:
            fresh += 1
    if (fresh, reused) != (26, 4):
        raise ValueError("Unexpected completed population")
    if c.sha256(output / "plan.json") != seal:
        raise ValueError("Plan changed during verification")
    if plan["runtime_code_sha256"] != c.runtime_hashes():
        raise ValueError("Runtime changed during verification")
    return {"new_complete": fresh, "stage_g_reused": reused, "total_complete": fresh + reused}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(c.DEFAULT_OUTPUT))
    print(verify(parser.parse_args().output))


if __name__ == "__main__":
    main()
