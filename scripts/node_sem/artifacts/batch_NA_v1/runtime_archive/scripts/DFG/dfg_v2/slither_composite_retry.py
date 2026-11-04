"""Explicit two-item retry of the Prompt 6d.2 synthetic fixture syntax error.

The original fixture and failed sealed output remain untouched. Only the
reserved function identifier indexed is changed to arrayWrite. No successful
probe is repeated, and no source from the real dataset is compiled.
"""
import argparse
import contextlib
import io
import json
import logging
import shutil
from pathlib import Path

from . import slither_targeted_probes as base
from .slither_conventions import collect_nodes, sha, write_json, SET_ATTRIBUTES
from .validate_slither import inspect_environment

VERSION = "dfg-v2-prompt6d2-composite-syntax-retry-v1"


def verify_failed_batch(failed_path):
    failed_path = Path(failed_path).resolve()
    seal_path = failed_path.with_name("report.seal.json")
    seal = json.loads(seal_path.read_text())
    if sha(failed_path) != seal["report_sha256"]:
        raise ValueError("Failed report seal mismatch")
    failed = json.loads(failed_path.read_text())
    if failed["version"] != "dfg-v2-prompt6d2-targeted-probes-v1" or failed["slither_invocations"] != 11:
        raise ValueError("Unexpected failed observation batch")
    rows = [c for c in failed["cases"] if c["case"] == "CompositeStateWrites.sol"]
    if len(rows) != 2 or {c["compiler_version"] for c in rows} != set(base.COMPILERS):
        raise ValueError("Unexpected retry identities")
    if any(c["status"] != "failed" or "Expected identifier" not in c.get("error", "")
           or "indexed" not in c.get("error", "") for c in rows):
        raise ValueError("Retry is restricted to the recorded reserved-word syntax failure")
    original = failed_path.parent / "sources" / "CompositeStateWrites.sol"
    for row in rows:
        if sha(original) != row["source"]["sha256"]:
            raise ValueError("Archived failed source SHA mismatch")
    return failed, original


def observations(cases):
    result = {}
    wanted = [c for c in base.CHECKS if c[1] == "CompositeStateWrites.sol"]
    for case in cases:
        row = {}
        for key, name, function, expression, target in wanted:
            function = "arrayWrite" if function == "indexed" else function
            nodes = [(i, n) for i, n in enumerate(case.get("nodes", ()))
                     if n["function"].startswith(function + "(")
                     and base.compact(n["source"]) == base.compact(expression)]
            obs = dict(status="observed" if len(nodes) == 1 else "missing_or_ambiguous",
                       compiler_version=case["compiler_version"], case=name,
                       fixture_name="CompositeStateWritesRetry.sol",
                       function=function, expression=expression, target=target,
                       matched_nodes=len(nodes))
            if len(nodes) == 1:
                index, node = nodes[0]
                obs.update(dict(
                    node_index=index, node_type=node["node_type_name"],
                    context_kind=node["context_kind"], span=node["span"], source=node["source"],
                    raw_node_pointer="/cases/" + str(cases.index(case)) + "/nodes/" + str(index),
                    ordinary_ir=[op["text"] for op in node["ir"]],
                    ssa_ir=[op["text"] for op in node["ir_ssa"]]))
                for attr in SET_ATTRIBUTES:
                    obs[attr] = sorted(v["name"] for v in node[attr])
                obs["target_state_read"] = target in obs["state_variables_read"]
                obs["target_state_write"] = target in obs["state_variables_written"]
                obs["interpretation"] = (
                    "Observed only in Slither 0.8.0 with solc " + case["compiler_version"] +
                    "; source differs from failed fixture only in the reserved function identifier.")
            row[key] = obs
        result[case["compiler_version"]] = row
    return result


def run(output, trusted_path, failed_path):
    output, trusted_path, failed_path = map(lambda p: Path(p).resolve(),
                                          (output, trusted_path, failed_path))
    if output.exists():
        raise ValueError("Refuse to overwrite syntax-retry output")
    failed, original = verify_failed_batch(failed_path)
    path = Path(__file__).resolve().parent / "convention_cases" / "p6d2" / "CompositeStateWritesRetry.sol"
    if path.is_symlink() or path.read_bytes() != original.read_bytes().replace(
            b"function indexed(", b"function arrayWrite("):
        raise ValueError("Retry changes must only rename the reserved function identifier")
    env = inspect_environment()
    compilers = base.checked_compilers(trusted_path, env)
    runtime = {str(Path(p).resolve()): sha(p)
               for p in (__file__, base.__file__)}
    output.mkdir(parents=True)
    copied = output / "sources"
    copied.mkdir()
    shutil.copyfile(str(path), str(copied / path.name))
    source = dict(path=str(path), sha256=sha(path))
    invocation = dict(
        version=VERSION, failed_report=dict(path=str(failed_path), sha256=sha(failed_path)),
        compiler_versions=list(base.COMPILERS), compilers=compilers, source=source,
        source_edit="Rename only function indexed to arrayWrite; indexed is a Solidity keyword.",
        original_source=dict(path=str(original), sha256=sha(original)),
        explicit_retry=True, successful_original_cases_repeated=0,
        trusted_manifest=dict(path=str(trusted_path), sha256=sha(trusted_path)),
        runtime_sha256=runtime, environment=env,
        dataset_contracts_invoked=0, network_requested=False, compiler_installation_attempted=False)
    write_json(output / "invocation.json", invocation)
    from slither.slither import Slither
    cases = []
    for version in base.COMPILERS:
        stdout, stderr = io.StringIO(), io.StringIO()
        handler = logging.StreamHandler(stderr)
        logging.getLogger().addHandler(handler)
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                analysis = Slither(str(path), solc=compilers[version]["path"], solc_disable_warnings=True)
                nodes = collect_nodes(analysis, path)
                functions = base.collect_functions(analysis)
            case = dict(case="CompositeStateWrites.sol", fixture_name=path.name,
                        compiler_version=version, status="compiled", source=source,
                        nodes=nodes, functions=functions)
        except Exception as exc:
            case = dict(case="CompositeStateWrites.sol", fixture_name=path.name,
                        compiler_version=version, status="failed", source=source,
                        error_type=type(exc).__name__, error=str(exc))
        finally:
            logging.getLogger().removeHandler(handler)
        (output / (version + ".stdout.txt")).write_text(stdout.getvalue())
        (output / (version + ".stderr.txt")).write_text(stderr.getvalue())
        write_json(output / (version + ".nodes.json"), case)
        cases.append(case)
    for runtime_path, digest in runtime.items():
        if sha(runtime_path) != digest:
            raise ValueError("Retry runtime changed during observations")
    if sha(path) != source["sha256"] or sha(trusted_path) != invocation["trusted_manifest"]["sha256"]:
        raise ValueError("Retry source or compiler manifest changed")
    observed = observations(cases)
    report = dict(version=VERSION, cases=cases, observations=observed,
                  compilers=compilers, slither_invocations=len(cases), dataset_contracts_invoked=0,
                  passed_files=sum(c["status"] == "compiled" for c in cases),
                  failed_files=sum(c["status"] != "compiled" for c in cases),
                  missing_observations=sum(o["status"] != "observed"
                                           for row in observed.values() for o in row.values()),
                  total_attempts_including_original=failed["slither_invocations"] + len(cases),
                  original_failed_invocations_retained=2, original_successes_repeated=0,
                  failed_report=invocation["failed_report"])
    write_json(output / "report.json", report)
    write_json(output / "report.seal.json", dict(
        version=VERSION, report_sha256=sha(output / "report.json"),
        files={str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*"))
               if p.is_file() and p.name != "report.seal.json"},
        runtime_sha256=runtime))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--trusted-compilers", required=True)
    parser.add_argument("--failed-report", required=True)
    args = parser.parse_args()
    result = run(args.output, args.trusted_compilers, args.failed_report)
    print(json.dumps({key: result[key] for key in
                      ("passed_files", "failed_files", "slither_invocations",
                       "total_attempts_including_original", "missing_observations")}, indent=2))
    return 1 if result["failed_files"] or result["missing_observations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
