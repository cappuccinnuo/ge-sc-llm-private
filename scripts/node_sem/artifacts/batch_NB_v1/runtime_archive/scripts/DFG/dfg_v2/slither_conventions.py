"""Prompt 6d.1: six allowlisted synthetic Slither convention observations.

This validator never compiles dataset contracts, changes analyzer semantics, or
downloads a compiler. Observations concern Slither 0.8.0 with the bound existing
solc 0.5.11 binary; they are evidence for predicates, not universal guarantees.
"""
import argparse
import contextlib
import hashlib
import io
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

from .validate_slither import compiler_for_selection, inspect_environment

VERSION = "dfg-v2-slither-conventions-v1"
COMPILER_VERSION = "0.5.11"
CASE_FILES = ("Loops.sol", "MappingWrites.sol", "RepeatedReads.sol",
              "MemoryArray.sol", "ParameterizedModifier.sol", "BareExpressions.sol")
SET_ATTRIBUTES = ("local_variables_read", "local_variables_written",
                  "state_variables_read", "state_variables_written")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf8")


def case_paths():
    """No user-supplied source path; exactly these packaged hand-written cases."""
    directory = Path(__file__).resolve().parent / "convention_cases"
    paths = [directory / name for name in CASE_FILES]
    for path in paths:
        raw = path.read_text(encoding="utf8")
        if not raw.startswith("pragma solidity " + COMPILER_VERSION + ";"):
            raise ValueError("Unexpected fixture pragma: " + str(path))
        if re.search(r"\bimport\b", raw):
            raise ValueError("Fixture import is outside the six-file scope")
        if path.is_symlink() or path.resolve().parent != directory.resolve():
            raise ValueError("Fixture escaped fixed case directory")
    return paths


def variable_record(value):
    mapping = getattr(value, "source_mapping", None)
    return dict(name=getattr(value, "name", str(value)), text=str(value),
                class_name=type(value).__name__,
                location=getattr(value, "location", None),
                source_mapping=mapping if isinstance(mapping, dict) else None)


def ir_record(operation):
    lvalue = getattr(operation, "lvalue", None)
    return dict(class_name=type(operation).__name__, text=str(operation),
                read=[variable_record(v) for v in getattr(operation, "read", ())],
                lvalue=variable_record(lvalue) if lvalue is not None else None)


def collect_nodes(slither, path):
    """Snapshot raw sets and IR/SSA without modifying any Slither object."""
    raw = Path(path).read_bytes()
    result, seen = [], set()
    for contract in slither.contracts:
        for function in list(contract.functions) + list(contract.modifiers):
            if id(function) in seen:
                continue
            seen.add(id(function))
            is_modifier = function in contract.modifiers
            for node in function.nodes:
                mapping = getattr(node, "source_mapping", None)
                if not isinstance(mapping, dict):
                    raise ValueError("Unsupported synthetic source mapping")
                start, length = mapping.get("start"), mapping.get("length")
                if type(start) is not int or type(length) is not int:
                    raise ValueError("Missing synthetic source byte span")
                if not (0 <= start <= start + length <= len(raw)):
                    raise ValueError("Synthetic source span is out of range")
                filename = mapping.get("filename_absolute")
                if not filename or Path(filename).resolve() != Path(path).resolve():
                    raise ValueError("Foreign or unmapped synthetic CFG node")
                record = dict(
                    node_id=node.node_id, node_type=str(node.type),
                    node_type_name=getattr(node.type, "name", str(node.type)),
                    contract=contract.name,
                    function=getattr(function, "full_name", function.name),
                    context_kind="modifier" if is_modifier else "function",
                    node_function=getattr(getattr(node, "function", None), "full_name", None),
                    function_source_mapping=getattr(function, "source_mapping", None),
                    source_mapping=dict(mapping), span=dict(start=start, end=start + length),
                    source=raw[start:start + length].decode("utf8"),
                    expression=str(node.expression) if node.expression is not None else None,
                    ir=[ir_record(op) for op in node.irs],
                    ir_ssa=[ir_record(op) for op in node.irs_ssa])
                for attr in SET_ATTRIBUTES:
                    record[attr] = [variable_record(v) for v in getattr(node, attr)]
                result.append(record)
    return result


def _names(node, attribute):
    return [v["name"] for v in node[attribute]]


def _compact(value):
    return re.sub(r"\s+", "", value).rstrip(";")


def observations(cases):
    """Derive narrowly stated conclusions from exact synthetic observations."""
    by_name = {c["case"]: c for c in cases if c["status"] == "compiled"}

    def find(case, expression=None, function=None):
        return [n for n in by_name.get(case, {}).get("nodes", ())
                if (expression is None or _compact(n["source"]) == _compact(expression))
                and (function is None or n["function"].startswith(function + "("))]

    def compact(node, name=None):
        result = {k: node[k] for k in ("node_id", "function", "context_kind",
                                       "node_type", "span", "source")}
        result.update({a: _names(node, a) for a in SET_ATTRIBUTES})
        result["phi_in_ssa"] = [op["text"] for op in node["ir_ssa"]
                                if op["class_name"].startswith("Phi")]
        if name is not None:
            result["target_name"] = name
        return result

    loop_observations = []
    for fn, text, name, attr in (
            ("whileLocal", "i < n", "i", "local_variables_written"),
            ("forLocal", "i < n", "i", "local_variables_written"),
            ("whileState", "s < n", "s", "state_variables_written")):
        nodes = find("Loops.sol", text, fn)
        loop_observations += [dict(compact(n, name), written=name in _names(n, attr))
                              for n in nodes]
    mapping = {}
    for key, text in (("mapping_write_base_read", "m[k] = v"),
                      ("mapping_delete_base_read", "delete m[k]")):
        nodes = find("MappingWrites.sol", text)
        obs = [dict(compact(n, "m"), base_read="m" in _names(n, "state_variables_read"),
                    base_write="m" in _names(n, "state_variables_written")) for n in nodes]
        mapping[key] = dict(confirmed=bool(obs) and all(n["base_read"] and n["base_write"]
                                                      for n in obs), observations=obs)
    repeated = []
    for expression, name in (("return m[k] + m[k]", "m"), ("return s + s", "s")):
        repeated += [dict(compact(n, name),
                          read_count=_names(n, "state_variables_read").count(name))
                     for n in find("RepeatedReads.sol", expression)]
    aggregate = [dict(compact(n, "a"),
                      base_read="a" in _names(n, "local_variables_read"),
                      base_write="a" in _names(n, "local_variables_written"))
                 for n in find("MemoryArray.sol", "a[i] = v")]
    modifier = [compact(n) for n in find("ParameterizedModifier.sol", "require(n > threshold)")]
    bare = []
    for expression, fn, name in (("x", "bare", "x"),
                                 ("to.call.value(amount)", "unused", "amount")):
        bare += [dict(compact(n, name), target_read=name in _names(n, "local_variables_read"))
                 for n in find("BareExpressions.sol", expression, fn)]
    called = [compact(n) for n in find("BareExpressions.sol", function="called")
              if "to.call.value" in n["source"]]
    result = dict(
        loop_header_merge_write=dict(
            confirmed=bool(loop_observations) and all(n["written"] for n in loop_observations),
            observations=loop_observations,
            limitation="Only the listed IFLOOP nodes; do not generalize to arbitrary conditions."),
        repeated_state_read=dict(
            confirmed=len(repeated) == 2 and all(n["read_count"] == 1 for n in repeated),
            observations=repeated,
            limitation="Slither set units differ from lexical occurrence units; comparator artifact."),
        aggregate_base_use=dict(
            confirmed=bool(aggregate) and all(n["base_write"] and not n["base_read"]
                                             for n in aggregate),
            observations=aggregate,
            limitation="Memory-array example only; other aggregate receivers need their own evidence."),
        modifier_body_unanalyzed=dict(
            confirmed=bool(modifier) and all(n["context_kind"] == "modifier" for n in modifier),
            observations=modifier,
            limitation="This proves Slither context ownership, not the v2 scope policy."),
        bare_expression_use=dict(
            confirmed=len(bare) == 2 and all(not n["target_read"] for n in bare),
            observations=bare, invoked_call_counterexample=called,
            limitation="An absent target read is confirmed only for the exact bare forms shown."))
    result.update(mapping)
    return result


def run(output, trusted_path):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Refuse to overwrite convention output: " + str(output))
    paths = case_paths()
    sources = {path.name: dict(path=str(path.resolve()), sha256=sha(path)) for path in paths}
    environment = inspect_environment()
    trusted_path = Path(trusted_path).resolve()
    trusted = json.loads(trusted_path.read_text())["compilers"]
    compiler, reason = compiler_for_selection(dict(version=COMPILER_VERSION), environment, trusted)
    if reason:
        raise ValueError("Authorized compiler unavailable: " + reason)
    version = subprocess.run([compiler, "--version"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
    if version.returncode != 0 or not re.search(
            r"Version:\s*" + re.escape(COMPILER_VERSION) + r"(?:\+|\s|$)", version.stdout):
        raise ValueError("Trusted compiler runtime version mismatch")
    output.mkdir(parents=True)
    copied = output / "sources"
    copied.mkdir()
    for path in paths:
        shutil.copyfile(str(path), str(copied / path.name))
    write_json(output / "invocation.json", dict(
        version=VERSION, allowed_cases=list(CASE_FILES), source_inputs=sources,
        trusted_manifest=dict(path=str(trusted_path), sha256=sha(trusted_path)),
        compiler=dict(path=compiler, sha256=sha(compiler), version=COMPILER_VERSION),
        compiler_version_stdout=version.stdout, compiler_version_stderr=version.stderr,
        environment=environment, dataset_contracts_invoked=0,
        compiler_installation_attempted=False, network_requested=False))
    from slither.slither import Slither
    cases = []
    for path in paths:
        stdout, stderr = io.StringIO(), io.StringIO()
        handler = logging.StreamHandler(stderr)
        logging.getLogger().addHandler(handler)
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                slither = Slither(str(path), solc=compiler, solc_disable_warnings=True)
                nodes = collect_nodes(slither, path)
            case = dict(case=path.name, status="compiled", source=sources[path.name], nodes=nodes)
        except Exception as exc:
            case = dict(case=path.name, status="failed", source=sources[path.name],
                        error_type=type(exc).__name__, error=str(exc))
        finally:
            logging.getLogger().removeHandler(handler)
        (output / (path.stem + ".stdout.txt")).write_text(stdout.getvalue())
        (output / (path.stem + ".stderr.txt")).write_text(stderr.getvalue())
        write_json(output / (path.stem + ".nodes.json"), case)
        cases.append(case)
    for path in paths:
        if sha(path) != sources[path.name]["sha256"]:
            raise ValueError("Synthetic source changed during observations")
    report = dict(version=VERSION, compiler_version=COMPILER_VERSION,
                  compiler_sha256=sha(compiler),
                  slither_version=environment["packages"]["slither-analyzer"],
                  invocation_sha256=sha(output / "invocation.json"),
                  cases=cases, conventions=observations(cases),
                  passed_files=sum(c["status"] == "compiled" for c in cases),
                  failed_files=sum(c["status"] != "compiled" for c in cases),
                  slither_invocations=len(cases), dataset_contracts_invoked=0)
    write_json(output / "report.json", report)
    write_json(output / "report.seal.json", dict(
        version=VERSION, report_sha256=sha(output / "report.json"),
        files={str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*"))
               if p.is_file() and p.name != "report.seal.json"},
        runtime_sha256={str(Path(__file__).resolve()): sha(__file__)}))
    return report



def derive_conclusions(report_path, output):
    """Add scoped conclusions to sealed observations without another invocation."""
    report_path, output = Path(report_path).resolve(), Path(output).resolve()
    if output.exists() or output.with_suffix(".seal.json").exists():
        raise ValueError("Refuse to overwrite derived conclusions")
    seal_path = report_path.with_name("report.seal.json")
    seal = json.loads(seal_path.read_text())
    if sha(report_path) != seal["report_sha256"]:
        raise ValueError("Observation report SHA mismatch")
    report = json.loads(report_path.read_text())
    if report["version"] != VERSION or report["slither_invocations"] != 6:
        raise ValueError("Unexpected observation batch")
    obs = observations(report["cases"])
    loop = obs["loop_header_merge_write"]["observations"]
    local = [n for n in loop if n["function"].startswith(("whileLocal(", "forLocal("))]
    state = [n for n in loop if n["function"].startswith("whileState(")]
    result = dict(
        version=VERSION + "-scoped-conclusions-v1",
        observation_report=dict(path=str(report_path), sha256=sha(report_path)),
        observation_seal=dict(path=str(seal_path), sha256=sha(seal_path)),
        additional_slither_invocations=0, conventions=obs,
        loop_header_merge_write=dict(
            L1=dict(confirmed=len(local) == 2 and all(
                n["written"] and n["phi_in_ssa"] for n in local),
                observations=local),
            L2=dict(confirmed=bool(state) and all(
                n["written"] and n["phi_in_ssa"] for n in state),
                observations=state),
            rule="L1 observed; the simple L2 while example is a negative result. "
                 "Do not treat local-variable Phi evidence as a blanket state-variable rule."),
        invocation_limits="Exactly six hand-written files, once each; no corpus or other files.",
        limitations=[
            "Observation of Slither 0.8.0 with bound solc 0.5.11 is not a proof across versions.",
            "Statement-set cardinality is a comparison-unit fact, not a v2 semantic defect.",
            "Modifier ownership is observed; v2 support policy must be justified independently.",
            "Memory array evidence does not establish every struct/member aggregate case.",
            "Mapping assignment does not read its base in this fixture; delete does.",
            "Bare-call option amounts differ from actually invoked-call amounts."])
    write_json(output, result)
    write_json(output.with_suffix(".seal.json"), dict(
        version=result["version"], report_sha256=sha(output),
        runtime_sha256={str(Path(__file__).resolve()): sha(__file__)}))
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--trusted-compilers", required=True)
    args = parser.parse_args()
    report = run(args.output, args.trusted_compilers)
    print(json.dumps(dict(passed_files=report["passed_files"], failed_files=report["failed_files"],
                          confirmations={k: v["confirmed"] for k, v in report["conventions"].items()}),
                     indent=2))
    return 1 if report["failed_files"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
