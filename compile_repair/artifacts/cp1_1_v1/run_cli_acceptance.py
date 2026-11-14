"""CP1.1 production CLI acceptance across three working directories."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PYTHON = "/home/zhao/miniconda3/envs/compile-repair-production/bin/python"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    with (OUT / name).open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def execute():
    fixtures = ROOT / "compile_repair/tests/fixtures"
    inputs = OUT / "inputs"
    inputs.mkdir()
    specs = [
        ("compat_05", fixtures / "compat_05.sol", None, "0.5.0", [], "none"),
        ("exact_cancun", fixtures / "features/y0824_tstore_asm.sol", "0.8.24",
         "0.8.24", ["--evm-version", "cancun"], "none"),
        ("exact_0410", fixtures / "compat_04.sol", "0.4.10", "0.4.12", [], "rewrite")]
    cases = []
    for name, origin, pragma, version, settings, level in specs:
        raw = origin.read_bytes()
        modified = re.sub(rb"pragma solidity[^;]+;", ("pragma solidity " + pragma + ";").encode(),
                          raw, count=1) if pragma else raw
        source = inputs / (name + ".sol")
        with source.open("xb") as stream:
            stream.write(modified)
        cases.append(dict(name=name, origin=str(origin.relative_to(ROOT)), origin_sha256=sha(origin),
                          input=str(source), input_sha256=sha(source), exact_pragma=pragma,
                          selected_version=version, settings=settings, change_level=level))
    sibling = OUT / "cwd/out"
    sibling.mkdir(parents=True)
    output_parent = OUT / "cwd/out2"
    directories = [("repository", ROOT), ("root", Path("/")), ("prefix_sibling", sibling)]
    jobs = [dict(case=c, cwd=str(cwd), cwd_kind=kind,
                 output=str(output_parent / (c["name"] + "_" + kind)))
            for c in cases for kind, cwd in directories]
    write("cli_plan.json", dict(jobs=jobs, job_count=len(jobs), stop_on_first_unexpected=True,
                                baseline_head=json.loads((OUT / "baseline.json").read_text())["head"]))
    env = dict(os.environ, PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT),
               OMP_NUM_THREADS="2", MKL_NUM_THREADS="2",
               TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64")
    comparable, results = {}, []
    with (OUT / "cli_invocations.jsonl").open("x", encoding="utf8") as journal:
        for index, job in enumerate(jobs, 1):
            case, destination = job["case"], Path(job["output"])
            argv = [PYTHON, "-B", "-m", "compile_repair.cli", "repair", case["input"],
                    "--output", str(destination)]
            start = time.monotonic()
            process = subprocess.run(argv, cwd=job["cwd"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            invocation = dict(command=argv, cwd=job["cwd"], case=case["name"],
                              cwd_kind=job["cwd_kind"], returncode=process.returncode,
                              stdout=process.stdout.decode("utf8"), stderr=process.stderr.decode("utf8"),
                              elapsed_seconds=time.monotonic() - start, cost_usd=0.0)
            journal.write(json.dumps(invocation, ensure_ascii=False, sort_keys=True) + "\n")
            journal.flush()
            failures = []
            row = dict(case=case["name"], cwd_kind=job["cwd_kind"], returncode=process.returncode)
            if process.returncode:
                failures.append("CLI returncode")
            else:
                summary = json.loads((destination / "summary.json").read_text())
                record = json.loads((destination / "manifest.jsonl").read_text().strip())
                node_record = json.loads((destination / "units/input_0001/nodes.json").read_text())
                seal = json.loads((destination / "seal.json").read_text())
                nodes = [{k:n[k] for k in ("key5", "ir", "provenance")} for n in node_record["nodes"]]
                fact = dict(status=record["status"], version=record["selected_version"],
                            settings=record["settings"], nodes=nodes)
                same = case["name"] not in comparable or comparable[case["name"]] == fact
                comparable.setdefault(case["name"], fact)
                sealed = all(sha(destination / p) == h for p,h in seal["files"].items())
                levels = [r["level"] for r in record["provenance"].values()]
                checks = dict(cli_complete=summary["status"] == "complete", success=record["status"] == "success",
                              selected_version=record["selected_version"] == case["selected_version"],
                              settings=record["settings"] == case["settings"],
                              change_level=levels == [case["change_level"]], identical_across_cwd=same,
                              input_unchanged=sha(Path(case["input"])) == case["input_sha256"],
                              original_fixture_unchanged=sha(ROOT / case["origin"]) == case["origin_sha256"],
                              all_sealed_hashes=sealed, nonempty_nodes=bool(nodes),
                              all_nodes_original=all(n["provenance"] == "original" for n in nodes),
                              implementation_count=len(seal["implementation_sha256"]) == 14)
                failures.extend(k for k,v in checks.items() if not v)
                row.update(checks=checks, status=record["status"], selected_version=record["selected_version"],
                           settings=record["settings"], flags=record["flags"], change_levels=levels,
                           node_count=len(nodes), nodes_sha256=hashlib.sha256(
                               json.dumps(nodes, sort_keys=True).encode()).hexdigest(),
                           solc_calls=len(record["attempts"]), slither_calls=sum(
                               a["slither"] is not None for a in record["attempts"]),
                           seal_sha256=sha(destination / "seal.json"),
                           output=str(destination.relative_to(OUT)))
            row["failures"] = failures
            results.append(row)
            print("CLI {}/{} {} {} {}".format(index, len(jobs), case["name"], job["cwd_kind"],
                                              "PASS" if not failures else failures), flush=True)
            if failures:
                write("cli_acceptance.json", dict(passed=False, planned=len(jobs), results=results,
                                                 not_run=len(jobs) - len(results)))
                raise SystemExit(2)
    write("cli_acceptance.json", dict(passed=True, planned=len(jobs), results=results, not_run=0))


if __name__ == "__main__":
    execute()
