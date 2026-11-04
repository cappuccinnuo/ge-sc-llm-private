"""Prompt 6d.2: fixed two-version synthetic convention observations.

Only the six selected hand-written fixtures may be compiled. The original
failed composite fixture is archived; future runs select its corrected copy. The five modern
fixtures run once each per trusted solc version; legacy var runs only on 0.4.24.
No dataset input, compiler download, or analyzer mutation is supported.
"""
import argparse
import contextlib
import io
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

from . import slither_conventions, validate_slither
from .slither_conventions import collect_nodes, sha, write_json, SET_ATTRIBUTES, variable_record
from .validate_slither import compiler_for_selection, inspect_environment

VERSION = "dfg-v2-prompt6d2-targeted-probes-v2"
COMPILERS = ("0.4.24", "0.5.11")
MODERN_CASES = ("StateExternalLoops.sol", "StorageLoops.sol",
                "CompositeStateWrites.sol", "StorageAliasWrite.sol",
                "AliasRebinding.sol")
LEGACY_CASE = "LegacyAliasWrite.sol"

# Each condition names one exact function and exact source expression. No search
# across real source paths or corpus file basenames is available.
CHECKS = (
    ("state_loop_send", "StateExternalLoops.sol", "withSend", "balance > x", "balance"),
    ("state_loop_no_send", "StateExternalLoops.sol", "withoutSend", "balance > x", "balance"),
    ("state_array_loop", "StorageLoops.sol", "arrayLoop", "i < n", "arr"),
    ("storage_reference_loop", "StorageLoops.sol", "referenceLoop", "p.x < n", "m"),
    ("struct_member_write", "CompositeStateWrites.sol", "direct", "s.f = v", "s"),
    ("mapping_member_write", "CompositeStateWrites.sol", "mapped", "m[k].f = v", "m"),
    ("array_member_write", "CompositeStateWrites.sol", "arrayWrite", "arr[i].f = v", "arr"),
    ("nested_member_write", "CompositeStateWrites.sol", "nested", "s.inner.g = v", "s"),
    ("mapping_assignment_control", "CompositeStateWrites.sol", "mappingControl", "scalar[k] = v", "scalar"),
    ("mapping_delete_control", "CompositeStateWrites.sol", "deleteControl", "delete scalar[k]", "scalar"),
    ("explicit_storage_member_write", "StorageAliasWrite.sol", "explicitAlias", "p.f = v", "m"),
    ("legacy_storage_member_write", "LegacyAliasWrite.sol", "legacyAlias", "p.f = v", "m"),
    ("direct_state_control", "AliasRebinding.sol", "directControl", "first.value = 7", "first"),
    ("alias_member_read", "AliasRebinding.sol", "readMember", "return ref.value", "first"),
    ("alias_member_compound", "AliasRebinding.sol", "compoundMember", "ref.value += 1", "first"),
    ("alias_first_write", "AliasRebinding.sol", "firstAlias", "ref.value = 7", "first"),
    ("alias_rebound_write", "AliasRebinding.sol", "rebindAlias", "ref.value = 7", "second"),
)


def invocation_matrix():
    return [(version, case) for version in COMPILERS
            for case in MODERN_CASES + ((LEGACY_CASE,) if version == "0.4.24" else ())]


def case_paths():
    directory = Path(__file__).resolve().parent / "convention_cases" / "p6d2"
    result = {}
    for name in MODERN_CASES + (LEGACY_CASE,):
        path = directory / ("CompositeStateWritesRetry.sol" if name == "CompositeStateWrites.sol" else name)
        raw = path.read_text(encoding="utf8")
        expected = ("pragma solidity 0.4.24;" if name == LEGACY_CASE else
                    "pragma solidity >=0.4.24 <=0.5.11;")
        if not raw.startswith(expected) or re.search(r"\bimport\b", raw):
            raise ValueError("Fixture pragma/import outside fixed scope: " + str(path))
        if path.is_symlink() or path.resolve().parent != directory.resolve():
            raise ValueError("Fixture escaped fixed source directory")
        result[name] = path
    return result


def compact(text):
    return re.sub(r"\s+", "", text).rstrip(";")


def observations(cases):
    """Report observed sets, including negative results; no universal verdict."""
    found = {}
    for case in cases:
        key = (case["compiler_version"], case["case"])
        if key in found:
            raise ValueError("Duplicate compiler/case observation")
        found[key] = case
    result = {}
    for version in COMPILERS:
        observed = {}
        for key, name, function, expression, target in CHECKS:
            if name == LEGACY_CASE and version != "0.4.24":
                observed[key] = dict(status="not_applicable",
                                    reason="legacy var intentionally only compiled with 0.4.24")
                continue
            case = found.get((version, name))
            matches = [] if not case or case["status"] != "compiled" else [
                (i, n) for i, n in enumerate(case["nodes"])
                if n["function"].startswith(function + "(") and
                compact(n["source"]) == compact(expression)]
            record = dict(status="observed" if len(matches) == 1 else "missing_or_ambiguous",
                          compiler_version=version, case=name, function=function,
                          expression=expression, target=target, matched_nodes=len(matches))
            if len(matches) == 1:
                index, node = matches[0]
                record.update(dict(
                    node_index=index, node_type=node["node_type_name"],
                    context_kind=node["context_kind"], span=node["span"],
                    source=node["source"],
                    raw_node_pointer="/cases/" + str(cases.index(case)) + "/nodes/" + str(index),
                    ordinary_ir=[op["text"] for op in node["ir"]],
                    ssa_ir=[op["text"] for op in node["ir_ssa"]],
                    phi_in_ssa=[op["text"] for op in node["ir_ssa"]
                                if op["class_name"].startswith("Phi")]))
                for attr in SET_ATTRIBUTES:
                    record[attr] = sorted(v["name"] for v in node[attr])
                record["target_state_read"] = target in record["state_variables_read"]
                record["target_state_write"] = target in record["state_variables_written"]
                record["interpretation"] = (
                    "Observed only in Slither 0.8.0 with solc " + version +
                    " for the bound source expression; absent writes/reads are also evidence.")
            observed[key] = record
        result[version] = observed
    return result


def collect_functions(analysis):
    """Additional declaration metadata; node sets and IR remain unmodified."""
    result, seen = [], set()
    for contract in analysis.contracts:
        for function in list(contract.functions) + list(contract.modifiers):
            if id(function) in seen:
                continue
            seen.add(id(function))
            result.append(dict(
                contract=contract.name,
                function=getattr(function, "full_name", function.name),
                source_mapping=getattr(function, "source_mapping", None),
                parameters=[variable_record(v) for v in function.parameters],
                returns=[variable_record(v) for v in function.returns],
                variables=[variable_record(v) for v in function.variables]))
    return result


def checked_compilers(trusted_path, environment):
    trusted = json.loads(Path(trusted_path).read_text())["compilers"]
    result = {}
    for requested in COMPILERS:
        binary, reason = compiler_for_selection(
            dict(version=requested), environment, trusted)
        if reason:
            raise ValueError("Trusted compiler unavailable: " + requested + ": " + reason)
        completed = subprocess.run([binary, "--version"], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, universal_newlines=True,
                                   timeout=30)
        if completed.returncode or not re.search(
                r"Version:\s*" + re.escape(requested) + r"(?:\+|\s|$)", completed.stdout):
            raise ValueError("Trusted compiler runtime version mismatch: " + requested)
        result[requested] = dict(path=binary, sha256=sha(binary), version=requested,
                                 version_stdout=completed.stdout,
                                 version_stderr=completed.stderr)
    return result


def run(output, trusted_path):
    output, trusted_path = Path(output).resolve(), Path(trusted_path).resolve()
    if output.exists():
        raise ValueError("Refuse to overwrite targeted probe output")
    paths = case_paths()
    sources = {name: dict(path=str(p.resolve()), sha256=sha(p))
               for name, p in paths.items()}
    environment = inspect_environment()
    compilers = checked_compilers(trusted_path, environment)
    runtime = {str(Path(p).resolve()): sha(p)
               for p in (__file__, slither_conventions.__file__, validate_slither.__file__)}
    output.mkdir(parents=True)
    copied = output / "sources"
    copied.mkdir()
    for name, path in paths.items():
        shutil.copyfile(str(path), str(copied / name))
    invocation = dict(
        version=VERSION, fixture_revision="reserved-identifier-corrected", matrix=[dict(compiler_version=v, case=c)
                                for v, c in invocation_matrix()],
        sources=sources, compilers=compilers, environment=environment,
        trusted_manifest=dict(path=str(trusted_path), sha256=sha(trusted_path)),
        runtime_sha256=runtime, dataset_contracts_invoked=0,
        compiler_installation_attempted=False, network_requested=False,
        approved_fixture_controls=[
            "User approved parameter, named return, no-initializer local, explicit local initializer and state initializer controls in an existing fixture.",
            "User approved alias readMember and compoundMember controls because actual corpus alias FP events are READ, not WRITE; invocation count stays eleven."])
    write_json(output / "invocation.json", invocation)
    from slither.slither import Slither
    cases = []
    for version, name in invocation_matrix():
        path, compiler = paths[name], compilers[version]["path"]
        stdout, stderr = io.StringIO(), io.StringIO()
        handler = logging.StreamHandler(stderr)
        logging.getLogger().addHandler(handler)
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                analysis = Slither(str(path), solc=compiler, solc_disable_warnings=True)
                nodes = collect_nodes(analysis, path)
                functions = collect_functions(analysis)
            case = dict(case=name, compiler_version=version, status="compiled",
                        source=sources[name], nodes=nodes, functions=functions)
        except Exception as exc:
            case = dict(case=name, compiler_version=version, status="failed",
                        source=sources[name], error_type=type(exc).__name__,
                        error=str(exc))
        finally:
            logging.getLogger().removeHandler(handler)
        prefix = version + "_" + path.stem
        (output / (prefix + ".stdout.txt")).write_text(stdout.getvalue(), encoding="utf8")
        (output / (prefix + ".stderr.txt")).write_text(stderr.getvalue(), encoding="utf8")
        write_json(output / (prefix + ".nodes.json"), case)
        cases.append(case)
    for name, path in paths.items():
        if sha(path) != sources[name]["sha256"]:
            raise ValueError("Fixture source changed during execution")
    for path, digest in runtime.items():
        if sha(path) != digest:
            raise ValueError("Probe runtime changed during execution")
    for compiler in compilers.values():
        if sha(compiler["path"]) != compiler["sha256"]:
            raise ValueError("Trusted compiler changed during execution")
    if sha(trusted_path) != invocation["trusted_manifest"]["sha256"]:
        raise ValueError("Trusted compiler manifest changed during execution")
    observed = observations(cases)
    report = dict(
        version=VERSION, cases=cases, observations=observed,
        compilers=compilers, slither_version=environment["packages"]["slither-analyzer"],
        slither_invocations=len(cases), dataset_contracts_invoked=0,
        passed_files=sum(c["status"] == "compiled" for c in cases),
        failed_files=sum(c["status"] != "compiled" for c in cases),
        missing_observations=sum(o["status"] == "missing_or_ambiguous"
                                 for row in observed.values() for o in row.values()),
        limitations=[
            "Exactly these two compiler versions and fixed source cases were observed.",
            "This report does not infer corpus verdicts or modify any analyzer.",
            "Legacy var is deliberately not compiled under 0.5.11.",
            "Member-write and alias results must be interpreted per source shape and version."])
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
    print(json.dumps({key: result[key] for key in
                      ("passed_files", "failed_files", "slither_invocations",
                       "dataset_contracts_invoked", "missing_observations")}, indent=2))
    return 1 if result["failed_files"] or result["missing_observations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
