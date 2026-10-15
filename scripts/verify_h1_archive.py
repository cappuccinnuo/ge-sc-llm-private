"""Read-only completed H1 archive validation; never executes H1 or H2."""
import argparse
import subprocess
from pathlib import Path
from scripts.DFG.experiments.e23_cv import control as c


def verify(output):
    output = Path(output)
    p = c.read_json(output / "plan.json")
    seal = c.read_json(output / "plan.seal.json")["sha256"]
    if c.sha256(output / "plan.json") != seal:
        raise ValueError("H1 seal drift")
    if p["format"] != c.BATCH_VERSION or p["h2_execution_authorized"] or p["device"] != "cuda:0":
        raise ValueError("Wrong batch policy")
    subprocess.run(["git", "merge-base", "--is-ancestor", p["base_git_head"], "HEAD"],
                   cwd=str(c.ROOT), check=True)
    if p["runtime_code_sha256"] != c.runtime_hashes():
        raise ValueError("Runtime source drift")
    c.validate_jobs(p)
    c.check_hashes(p["frozen_files"])
    h2seal = c.read_json(output / "h2_plan.seal.json")["sha256"]
    if c.sha256(output / "h2_plan.json") != h2seal:
        raise ValueError("Reserved H2 plan drift")
    h2 = c.read_json(output / "h2_plan.json")
    if h2["execution_authorized"] or h2["h1_plan_sha256"] != c.digest(p):
        raise ValueError("H2 binding drift")
    if [(j["task_id"], j["fold"], j["variant"]) for j in h2["jobs"]] != c.expected_jobs(("E3a",)):
        raise ValueError("H2 incomplete")
    fresh = reused = 0
    for job in p["jobs"]:
        ok, _ = c.locate(output, job, p)
        if ok is None:
            raise ValueError("Incomplete archive: " + c.identity(job))
        if job["fold"] == 0:
            reused += 1
        else:
            fresh += 1
    if (fresh, reused) != (52, 8):
        raise ValueError("Wrong archive population")
    if c.sha256(output / "plan.json") != seal or c.sha256(output / "h2_plan.json") != h2seal:
        raise ValueError("Plan changed during validation")
    if p["runtime_code_sha256"] != c.runtime_hashes():
        raise ValueError("Runtime changed during validation")
    return {"new_complete": fresh, "stage_g_reused": reused, "total_complete": fresh + reused}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(c.DEFAULT_OUTPUT))
    print(verify(parser.parse_args().output))


if __name__ == "__main__":
    main()
