"""User-approved Prompt 6d.2 shape supplement: one source, two fixed solc runs.

Covers storage-array and bytes loop/write shapes plus bare expression controls.
Never compiles real corpus contracts or installs a compiler.
"""
import argparse
import contextlib
import io
import json
import logging
import re
import shutil
from pathlib import Path

from . import slither_targeted_probes as base
from .slither_conventions import collect_nodes, sha, write_json, SET_ATTRIBUTES
from .validate_slither import inspect_environment

VERSION = "dfg-v2-prompt6d2-shape-supplement-v2"
CHECKS = (
    ("storage_array_loop", "storageArrayLoop", "i < n", "records"),
    ("storage_array_write", "storageArrayLoop", "records[i] = S(v)", "records"),
    ("bytes_loop", "memoryBytes", "i < n", "out"),
    ("bytes_write", "memoryBytes", "out[i] = byte(1)", "out"),
    ("bare_identifier", "bare", "x", "x"),
    ("uninvoked_call_options", "unused", "msg.sender.call.value(amount)", "amount"),
)


def case_path():
    directory = Path(__file__).resolve().parent / "convention_cases" / "p6d2"
    path = directory / "ShapeSupplementRetry.sol"
    raw = path.read_text()
    if path.is_symlink() or path.resolve().parent != directory.resolve():
        raise ValueError("Shape fixture escaped fixed directory")
    if not raw.startswith("pragma solidity >=0.4.24 <=0.5.11;") or re.search(r"\bimport\b", raw):
        raise ValueError("Unexpected fixture pragma or import")
    return path


def observations(cases):
    result = {}
    for ci, case in enumerate(cases):
        version = case["compiler_version"]
        if version not in base.COMPILERS or version in result:
            raise ValueError("Unexpected or repeated compiler identity")
        row = {}
        for key, function, expression, target in CHECKS:
            matches = [] if case["status"] != "compiled" else [
                (i, n) for i, n in enumerate(case["nodes"])
                if n["function"].startswith(function + "(")
                and (base.compact(n["source"]) == base.compact(expression)
                     or (key == "bytes_write" and base.compact(n["source"]) ==
                         base.compact("out[i] = bytes1(uint8(1))")))]
            record = dict(status="observed" if len(matches) == 1 else "missing_or_ambiguous",
                          compiler_version=version, function=function, source=expression,
                          target=target, matched_nodes=len(matches))
            if len(matches) == 1:
                index, node = matches[0]
                record.update(dict(
                    source=node["source"], node_index=index, node_type=node["node_type_name"],
                    context_kind=node["context_kind"], span=node["span"],
                    raw_node_pointer="/cases/" + str(ci) + "/nodes/" + str(index),
                    ordinary_ir=[op["text"] for op in node["ir"]],
                    ssa_ir=[op["text"] for op in node["ir_ssa"]],
                    phi_in_ssa=[op["text"] for op in node["ir_ssa"]
                                if op["class_name"].startswith("Phi")]))
                for attr in SET_ATTRIBUTES:
                    record[attr] = sorted(v["name"] for v in node[attr])
                record["target_local_read"] = target in record["local_variables_read"]
                record["target_local_write"] = target in record["local_variables_written"]
                record["interpretation"] = (
                    "Observed only in the bound source with Slither 0.8.0 and solc " + version +
                    "; no inference about unobserved compiler versions or corpus contexts.")
            row[key] = record
        result[version] = row
    return result


def run(output, trusted_path):
    output, trusted_path = Path(output).resolve(), Path(trusted_path).resolve()
    if output.exists():
        raise ValueError("Refuse to overwrite shape-supplement output")
    path = case_path()
    env = inspect_environment()
    compilers = base.checked_compilers(trusted_path, env)
    runtime = {str(Path(p).resolve()): sha(p) for p in (__file__, base.__file__)}
    source = dict(path=str(path), sha256=sha(path))
    output.mkdir(parents=True)
    (output / "sources").mkdir()
    shutil.copyfile(str(path), str(output / "sources" / path.name))
    invocation = dict(
        version=VERSION, source=source, compilers=compilers, environment=env,
        matrix=[dict(compiler_version=v, case=path.name) for v in base.COMPILERS],
        trusted_manifest=dict(path=str(trusted_path), sha256=sha(trusted_path)),
        runtime_sha256=runtime, dataset_contracts_invoked=0,
        compiler_installation_attempted=False, network_requested=False,
        authorization="User approved one minimal supplemental source for storage-array/bytes loop and bare-expression controls, once each on existing trusted 0.4.24 and 0.5.11.")
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
            case = dict(case=path.name, compiler_version=version, status="compiled",
                        source=source, nodes=nodes, functions=functions)
        except Exception as exc:
            case = dict(case=path.name, compiler_version=version, status="failed",
                        source=source, error_type=type(exc).__name__, error=str(exc))
        finally:
            logging.getLogger().removeHandler(handler)
        (output / (version + ".stdout.txt")).write_text(stdout.getvalue())
        (output / (version + ".stderr.txt")).write_text(stderr.getvalue())
        write_json(output / (version + ".nodes.json"), case)
        cases.append(case)
    for p, digest in runtime.items():
        if sha(p) != digest:
            raise ValueError("Supplement runtime changed")
    if sha(path) != source["sha256"] or sha(trusted_path) != invocation["trusted_manifest"]["sha256"]:
        raise ValueError("Supplement source or compiler manifest changed")
    for compiler in compilers.values():
        if sha(compiler["path"]) != compiler["sha256"]:
            raise ValueError("Trusted compiler changed")
    observed = observations(cases)
    report = dict(
        version=VERSION, cases=cases, observations=observed, compilers=compilers,
        slither_version=env["packages"]["slither-analyzer"],
        slither_invocations=len(cases), dataset_contracts_invoked=0,
        passed_files=sum(c["status"] == "compiled" for c in cases),
        failed_files=sum(c["status"] != "compiled" for c in cases),
        missing_observations=sum(o["status"] != "observed" for row in observed.values() for o in row.values()))
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
    args = parser.parse_args()
    result = run(args.output, args.trusted_compilers)
    print(json.dumps({k: result[k] for k in
                      ("passed_files", "failed_files", "slither_invocations",
                       "missing_observations")}, indent=2))
    return 1 if result["failed_files"] or result["missing_observations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
