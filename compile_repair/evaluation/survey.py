"""CP0 read-only identity, metadata and compiler reconnaissance.

The missing-compiler gate precedes the expensive matrix. This first CP0
checkpoint implements reconnaissance and tool wrappers; matrix orchestration
is deferred at that gate, rather than silently omitting uncovered inputs.
"""
import ast
import hashlib
import json
import re
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from compile_repair.toolchain.solc import inventory, version_tuple, error_first_line

ROOT = Path(__file__).resolve().parents[2]
SIX_C = Path("/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1")
REPORT_SHA = "db56b7066430813540e468c900283414bf49c5e7c1f519cded8a874a760fd2a6"
SEAL_SHA = "91e054c9cdd2331b7f21bc48e195a394d6034ffe85f878daa8fb013c9431e49c"


def checked_json(path, expected):
    """Hash bytes before decoding an evidence JSON; fail on identity drift."""
    raw = Path(path).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise ValueError("Evidence SHA256 mismatch: " + str(path))
    return json.loads(raw.decode("utf8"))


def metadata_refs(root):
    """Read only registry literals; never import task/label/graph loaders."""
    tree = ast.parse((root / "scripts/DFG/dfg_v2/tasks.py").read_text(encoding="utf8"))
    registry = next(ast.literal_eval(n.value) for n in tree.body
                    if isinstance(n, ast.Assign) and any(
                        isinstance(t, ast.Name) and t.id == "REGISTRY" for t in n.targets))
    return {c: registry[c]["tasks"]["contract"]["source_metadata_manifest"]
            for c in ("access_control", "reentrancy")}


def candidate_versions(interval, versions):
    """List installed eligible releases and later-series fallback separately.

    This is CP0 inventory, not a CP1 version-selection implementation.
    No pragma uses the MANDO 0.4.12-0.4.26 window; metadata is handled separately.
    """
    primary, fallback = [], []
    lo, hi = interval or ((0, 4, 12), (0, 4, 27))
    for value in sorted(set(versions), key=version_tuple):
        version = version_tuple(value)
        if version >= (0, 4, 12) and lo <= version < hi:
            (primary if version[:2] == lo[:2] else fallback).append(value)
    return {"primary": primary, "later_series_only_after_primary_failure": fallback}


def input_inventory(root, previous):
    """Bind corpus paths/SHA256 to pre-evidence and frozen pragma semantics."""
    from scripts.DFG.frontend import parse
    from scripts.DFG.state.stage_f.versioning import interval
    from auto_version_solc import get_solc_version
    old = {(r["class"], r["file"]): r for r in previous}
    if len(old) != len(previous):
        raise ValueError("Duplicate cr_pre_v1 file identity")
    rows = []
    for path in sorted((root / "experiments/ge-sc-data/source_code").glob("*/source_files/*.sol")):
        raw = path.read_bytes()
        source = raw.decode("utf8")
        tree = parse(source)
        iv = interval(source, tree.root_node)
        category, filename = path.parent.parent.name, path.name
        if (category, filename) not in old:
            raise ValueError("Corpus file absent from cr_pre_v1: " + str(path))
        rule = get_solc_version(str(path))
        rows.append({"path": str(path.relative_to(root)), "category": category, "file": filename,
                     "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                     "interval": iv, "rule_a_version": rule,
                     "rule_version_outside_interval": bool(iv and not iv[0] <= version_tuple(rule) < iv[1]),
                     "pre_rule_a": old[(category, filename)], "metadata": None})
    if {(r["category"], r["file"]) for r in rows} != set(old) or len(rows) != 846:
        raise ValueError("Expected exactly the 846 cr_pre_v1 files")
    return rows


def bind_metadata(root, rows, refs, authorization):
    """Validate only the approved source manifests and their metadata refs."""
    from scripts.DFG.state.stage_f.versioning import recorded_version
    if authorization.get("allowed_manifests") != refs:
        raise ValueError("Metadata manifests differ from user-approved read scope")
    local = {(r["category"], r["file"]): r for r in rows}
    evidence = []
    for category, ref in refs.items():
        manifest = checked_json(ref["path"], ref["sha256"])
        for filename, entry in sorted(manifest["sources"].items()):
            row = local[(category, filename)]
            if entry["sha256"] != row["sha256"]:
                raise ValueError("Manifest and local source hashes differ")
            metadata = entry.get("metadata")
            if metadata is None:
                continue
            version = recorded_version((root / row["path"]).read_bytes().decode("utf8"), metadata)
            iv = row["interval"]
            row["metadata"] = metadata
            row["metadata_in_interval"] = iv is None or iv[0] <= version < iv[1]
            row["metadata_below_slither_floor"] = version < (0, 4, 12)
            evidence.append({"path": row["path"], "manifest": ref,
                             "field": "sources[" + filename + "].metadata", "metadata": metadata,
                             "verified": True, "below_slither_floor": version < (0, 4, 12)})
    if len(evidence) != 43:
        raise ValueError("Expected 43 verified metadata records")
    return evidence


def compare_six_c(rows, report):
    """Join historical results by byte identity and describe observable differences.

    Historical comparisons are evidence inspection, not a new compiler run.
    Ambiguous duplicate source hashes are reported with all candidate paths.
    """
    by_hash = defaultdict(list)
    for row in rows:
        by_hash[row["sha256"]].append(row)
    comparisons, field_sets = [], defaultdict(set)
    occurrence_counts = Counter()
    for task, data in sorted(report["tasks"].items()):
        category = task[:-len("_contract")]
        for file in data["files"]:
            matches = by_hash.get(file["source_sha256"], [])
            selected = [r for r in matches if r["category"] == category and r["file"] == file["file"]]
            if len(selected) != 1:
                raise ValueError("6c file cannot be bound to corpus by SHA256")
            row = selected[0]
            if file["version_origin"] == "metadata":
                if not row["metadata"] or row["metadata"]["version"] != file["version"]:
                    raise ValueError("6c metadata version differs from verified origin")
            old = row["pre_rule_a"]
            reasons = []
            if file["version"] != old["selected"]:
                reasons.append("6c metadata priority differs from old rule A" if file["version_origin"] == "metadata"
                               else "version disagreement requires review")
            if old["A"] == "unavailable_here":
                reasons.append("old cloud probe lacked early static solc; 6c local compiler existed")
            if file["status"] == "not_comparable":
                reasons.append("6c checks filename mapping; old A checks only solc exit status")
            if (file["status"] == "compile_failed") != (old["A"] == "fail") and old["A"] != "unavailable_here":
                reasons.append("different compilation invocation/environment; causality not yet rerun")
            comparisons.append({"path": row["path"], "source_sha256": row["sha256"],
                                "all_sha_matches": [r["path"] for r in matches],
                                "six_c_version": file["version"], "six_c_origin": file["version_origin"],
                                "six_c_status": file["status"],
                                "error_first_line": error_first_line(file.get("detail", "")) or file.get("reason"),
                                "six_c_blockers": file.get("comparability", {}).get("blockers", {}),
                                "pre_version": old["selected"], "pre_status": old["A"],
                                "pre_error": old.get("A_error"), "difference_reasons": reasons})
            extraction = file.get("slither_extraction", {})
            for item in extraction.get("functions", []):
                field_sets["function"].update(item)
            for item in extraction.get("occurrences", []):
                field_sets["occurrence"].update(item)
                for name in ("function", "node", "declaration"):
                    if item.get(name):
                        field_sets[name + "_span"].update(item[name])
                occurrence_counts[file["status"]] += 1
    if len(comparisons) != 256:
        raise ValueError("Expected 256 historical files")
    return {"files": comparisons,
            "status_counts": dict(Counter(r["six_c_status"] for r in comparisons)),
            "version_origin_counts": dict(Counter(r["six_c_origin"] for r in comparisons)),
            "exceptions": [r for r in comparisons if r["six_c_status"] != "compared"],
            "schema": {k: sorted(v) for k, v in field_sets.items()},
            "occurrence_counts": dict(occurrence_counts),
            "cp2_key_proposal": {"outer": ["source_sha256"],
                "occurrence_multiset": ["layer", "function_name", "function.start", "modifier",
                    "context_contract", "context_declarer", "inherited_context", "node.start",
                    "declaration.start", "canonical_name", "fact", "tags"],
                "source_length_excluded": True,
                "limitations": ["6c occurrences do not expose CFG node type or raw ordered SlithIR",
                    "key4 and complete graph equality cannot be reconstructed from these occurrence rows",
                    "Use multisets and preserve inherited contexts; duplicate keys must not be deduplicated",
                    "CP2 comparison contract requires review before implementation"]}}


def write_json(path, value):
    """Exclusively create a CP0 evidence document; never overwrite a result."""
    with Path(path).open("x", encoding="utf8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def survey(output, metadata_authorization, inventory_only=False):
    """Run CP0 preflight and archive the first blocking condition without retry.

    This checkpoint stops before matrix orchestration. An absent eligible
    compiler is never handled by silently reducing the corpus or changing pragma.
    """
    output = Path(output).resolve()
    artifact_root = (ROOT / "compile_repair/artifacts").resolve()
    if artifact_root not in output.parents:
        raise ValueError("Survey output must be a new compile_repair/artifacts subdirectory")
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    result = {"schema": "compile-repair-cp0-recon-v1", "status": "running", "blockers": [],
              "compilation_executed": False, "slither_executed": False,
              "training_executed": False, "llm_calls": 0, "cost_usd": 0,
              "root": str(ROOT), "command": {"module": "compile_repair.cli", "subcommand": "survey",
                  "output": str(output), "metadata_authorization": str(Path(metadata_authorization).resolve()),
                  "inventory_only": inventory_only},
              "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), universal_newlines=True).strip()}
    try:
        report = checked_json(SIX_C / "slither_full/report.json", REPORT_SHA)
        seal = checked_json(SIX_C / "slither_full/report.seal.json", SEAL_SHA)
        if seal["report_sha256"] != REPORT_SHA:
            raise ValueError("6c seal does not bind the report")
        trust_ref = report["trusted_compiler_manifest"]
        if Path(trust_ref["path"]).resolve() != SIX_C / "trusted_compilers_complete.json":
            raise ValueError("Trusted manifest escapes approved 6c read scope")
        trusted = checked_json(trust_ref["path"], trust_ref["sha256"])
        result["evidence"] = {"six_c_report": {"path": str(SIX_C / "slither_full/report.json"), "sha256": REPORT_SHA},
                              "six_c_seal": {"path": str(SIX_C / "slither_full/report.seal.json"), "sha256": SEAL_SHA},
                              "trusted_compilers": trust_ref}
        pre = ROOT / "compile_repair/artifacts/cr_pre_v1/compile_repro.json"
        result["evidence"]["pre_rule_a"] = {"path": str(pre), "sha256": hashlib.sha256(pre.read_bytes()).hexdigest(),
                                             "contains_source_hashes": False}
        rows = input_inventory(ROOT, json.loads(pre.read_text(encoding="utf8")))
        result["inputs"] = rows
        auth_path = Path(metadata_authorization)
        auth = json.loads(auth_path.read_text(encoding="utf8"))
        refs = metadata_refs(ROOT)
        result["metadata"] = bind_metadata(ROOT, rows, refs, auth)
        result["evidence"]["metadata_authorization"] = {"path": str(auth_path.resolve()),
                    "sha256": hashlib.sha256(auth_path.read_bytes()).hexdigest()}
        result["historical_comparison"] = compare_six_c(rows, report)
        compilers, environment, missing_trusted = inventory(trusted["compilers"])
        result["environment"] = environment
        result["compilers"] = {v: asdict(c) for v, c in compilers.items()}
        result["missing_trusted_versions"] = missing_trusted
        sums = ROOT / "compile_repair/artifacts/cr_pre_v1/solc_github_static_SHA256SUMS"
        known = set(re.findall(r"solc-(\d+\.\d+\.\d+)", sums.read_text())) | set(trusted["compilers"])
        result["evidence"]["known_release_window"] = {"path": str(sums),
                    "sha256": hashlib.sha256(sums.read_bytes()).hexdigest(),
                    "note": "Missing-release counts use this finite observed release list, not an online catalog."}
        missing = defaultdict(list)
        for row in rows:
            candidates = candidate_versions(row["interval"], compilers)
            row["installed_candidates"] = candidates
            known_candidates = candidate_versions(row["interval"], known)
            for v in known_candidates["primary"]:
                if v not in compilers:
                    missing[v].append(row["path"])
            eligible = candidates["primary"] + candidates["later_series_only_after_primary_failure"]
            if not eligible:
                result["blockers"].append({"kind": "no_installed_trusted_candidate", "path": row["path"],
                    "source_sha256": row["sha256"], "interval": row["interval"],
                    "known_required_versions": known_candidates["primary"]})
        result["missing_primary_versions"] = {v: {"file_count": len(paths), "files": paths}
                                               for v, paths in sorted(missing.items(), key=lambda pair: version_tuple(pair[0]))}
        result["summary"] = {"files": len(rows), "no_pragma": sum(r["interval"] is None for r in rows),
            "category_counts": dict(Counter(r["category"] for r in rows)),
            "metadata_count": len(result["metadata"]),
            "metadata_versions": dict(Counter(m["metadata"]["version"] for m in result["metadata"])),
            "metadata_csv_paths": dict(Counter(m["metadata"]["csv_path"] for m in result["metadata"])),
            "metadata_below_slither_floor": sum(m["below_slither_floor"] for m in result["metadata"]),
            "rule_version_outside_interval": sum(r["rule_version_outside_interval"] for r in rows),
            "trusted_installed_count": len(compilers), "uncovered_files": len(result["blockers"]),
            "historical_status_counts": result["historical_comparison"]["status_counts"]}
        result["status"] = "blocked_missing_compilers" if result["blockers"] else (
            "inventory_only" if inventory_only else "stopped_after_preflight")
        result["not_run"] = ["full compiler matrix", "ascending/descending D3 version selection",
                             "full Slither survey", "cross-version corpus comparison", "CP2 runtime estimate"]
    except Exception as exc:
        result.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
    result["elapsed_seconds"] = time.monotonic() - started
    result["implementation_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT / "compile_repair").rglob("*.py")) if "artifacts" not in p.parts and "tests" not in p.parts}
    write_json(output / "recon.json", result)
    write_json(output / "seal.json", {"schema": "compile-repair-cp0-seal-v1", "files": {
        "recon.json": hashlib.sha256((output / "recon.json").read_bytes()).hexdigest()}})
    return result
