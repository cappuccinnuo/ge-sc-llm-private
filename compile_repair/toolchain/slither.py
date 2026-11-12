"""CP0 Slither 0.8.0 construction, D3 mapping checks and node fingerprints.

No graph store is written. Source lengths are diagnostics, never identities.
"""
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from compile_repair.toolchain.solc import verify_binary


def node_facts(slither, inputs):
    """Inspect all declared functions/modifiers, including missing mappings.

    Return D3 counts and a multiset of key4, ordered IR and source lengths.
    Empty declared CFGs are recorded explicitly; no node is silently excluded.
    """
    allowed = {str(Path(p).resolve()) for p in inputs}
    rows, counts = [], Counter()
    for contract in slither.contracts:
        for function in contract.functions_and_modifiers_declared:
            counts["declarations"] += 1
            for node in function.nodes:
                mapping = node.source_mapping or {}
                filename, start = mapping.get("filename_absolute"), mapping.get("start")
                counts["nodes"] += 1
                if not filename:
                    counts["missing_filename"] += 1
                elif not isinstance(filename, str) or not Path(filename).is_absolute():
                    counts["invalid_filename"] += 1
                elif str(Path(filename).resolve()) not in allowed:
                    counts["foreign_filename"] += 1
                if start is None:
                    counts["missing_start"] += 1
                rows.append({"key4": [contract.name, function.full_name, str(node.type), start],
                             "ir": [str(ir) for ir in node.irs],
                             "length": mapping.get("length")})
    for key in ["nodes", "declarations", "missing_filename", "invalid_filename",
                "foreign_filename", "missing_start"]:
        counts.setdefault(key, 0)
    key_counts = Counter(json.dumps(r["key4"]) for r in rows)
    return {"mapping_complete": not any(counts[k] for k in [
                "missing_filename", "invalid_filename", "foreign_filename", "missing_start"]),
            "counts": dict(counts), "empty_cfg": counts["nodes"] == 0,
            "duplicate_key4": {k: v for k, v in key_counts.items() if v > 1},
            "nodes": sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))}


def compare_nodes(left, right):
    """Compare multisets, retaining every difference and ordered IR per node."""
    output = {}
    for name, fields in [("key4", ["key4"]), ("slithir", ["key4", "ir"]),
                         ("source_length", ["key4", "length"])]:
        a, b = [Counter(json.dumps([r[k] for k in fields], sort_keys=True) for r in rows)
                for rows in (left, right)]
        output[name] = {"equal": a == b, "only_low": dict(a - b), "only_high": dict(b - a)}
    return output


def run_slither(compilation):
    """Run frozen _compile after verified rc=0, then apply D3.

    Slither/crytic subprocess return codes are not exposed by their API.
    Record the API outcome and bind the observed preceding solc rc separately.
    """
    from scripts.DFG.dfg_v2.validate_slither import _compile
    from importlib_metadata import version
    if version("slither-analyzer") != "0.8.0" or version("crytic-compile") != "0.2.4":
        raise ValueError("CP0 requires Slither 0.8.0 and crytic-compile 0.2.4")
    if compilation.returncode != 0 or compilation.timed_out:
        raise ValueError("D3 requires an observed successful solc invocation")
    path, compiler = Path(compilation.source_path), compilation.compiler
    if hashlib.sha256(path.read_bytes()).hexdigest() != compilation.source_sha256:
        raise ValueError("Slither input differs from compiled source")
    verify_binary(compiler)
    result = {"source_path": str(path), "source_sha256": compilation.source_sha256,
              "version": compiler.version, "compiler_sha256": compiler.sha256,
              "slither_version": "0.8.0", "crytic_compile_version": "0.2.4",
              "command": {"api": "Slither", "target": str(path),
                          "solc": compiler.path, "solc_disable_warnings": True},
              "equivalent_solc_argv": compilation.command,
              "preceding_observed_solc_returncode": compilation.returncode,
              "api_subprocess_returncodes_observed": False, "cost_usd": 0.0}
    start = time.monotonic()
    try:
        facts = node_facts(_compile(path, compiler.path), [path])
        result.update(facts)
        result.update({"constructed": True, "d3": facts["mapping_complete"],
                       "error_first_line": None})
    except Exception as exc:
        result.update({"constructed": False, "d3": False, "nodes": [],
                       "exception_type": type(exc).__name__,
                       "error_first_line": str(exc).splitlines()[0] if str(exc) else type(exc).__name__,
                       "detail": str(exc)})
    result["elapsed_seconds"] = time.monotonic() - start
    if hashlib.sha256(path.read_bytes()).hexdigest() != compilation.source_sha256:
        raise ValueError("Source changed during Slither analysis")
    return result
