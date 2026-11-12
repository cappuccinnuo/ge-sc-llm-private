"""CP0 read-only identity, metadata and compiler reconnaissance.

The missing-compiler gate precedes the expensive matrix. Evidence is written
once, with a flushed invocation journal; expected candidate failures are data,
while uncovered inputs, timeouts and integrity failures stop the survey.
"""
import ast
import gc
import hashlib
import json
import re
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from compile_repair.toolchain.solc import (inventory, version_tuple, error_first_line,
    load_additions, release_coverage, compile_file)
from compile_repair.toolchain.slither import run_slither, compare_nodes

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
    lo, hi = tuple(lo), tuple(hi)
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



def selection_priority(row, available):
    """CP0 regression priorities; does not implement general CP1 inference."""
    metadata = row.get("metadata")
    known = metadata["version"] if metadata else None
    iv = row["interval"]
    if known and known in available and version_tuple(known) >= (0, 4, 12):
        if iv is None or tuple(iv[0]) <= version_tuple(known) < tuple(iv[1]):
            return known
    if iv is None and "0.4.25" in available:
        return "0.4.25"
    return None


def d3_endpoints(versions, probe):
    """Find true D3 endpoints, including compile-success/mapping-failure cases.

    Interior versions need not be analyzed unless an endpoint fails. A caller's
    memoized probe reuses observations; this is not an automatic failure retry.
    """
    ordered = sorted(versions, key=version_tuple)
    low = next((v for v in ordered if probe(v)["d3"]), None)
    high = next((v for v in reversed(ordered) if probe(v)["d3"]), None) if low else None
    return low, high


class Observations:
    """One read-only source, memoized results and a flushed command journal."""

    def __init__(self, path, compilers, journal, scope):
        self.path, self.compilers, self.journal, self.scope = path, compilers, journal, scope
        self.compiled, self.analyzed = {}, {}

    def emit(self, kind, observation):
        item = dict(observation)
        if "nodes" in item:
            nodes = item.pop("nodes")
            item["node_facts_sha256"] = hashlib.sha256(
                json.dumps(nodes, sort_keys=True).encode("utf8")).hexdigest()
        if "stderr" in item:
            stderr = item.pop("stderr")
            item["stderr_sha256"] = hashlib.sha256(stderr.encode("utf8")).hexdigest()
            item["stderr_bytes"] = len(stderr.encode("utf8"))
            item["stderr_excerpt"] = stderr[:8192]
            item["stderr_truncated"] = len(stderr) > 8192
        self.journal.write(json.dumps(dict(kind=kind, scope=self.scope, **item), sort_keys=True) + "\n")
        self.journal.flush()

    def compile(self, version):
        if version not in self.compiled:
            item = compile_file(self.path, self.compilers[version])
            self.compiled[version] = item
            self.emit("solc", asdict(item))
            if item.timed_out:
                raise RuntimeError("solc timeout; no retry: " + str(self.path) + " @ " + version)
        return self.compiled[version]

    def probe(self, version):
        if version not in self.analyzed:
            compiled = self.compile(version)
            if compiled.returncode == 0:
                item = run_slither(compiled)
                self.emit("slither", item)
            else:
                item = {"d3": False, "constructed": False, "not_run": "solc_failed",
                        "error_first_line": compiled.error_first_line, "nodes": []}
            self.analyzed[version] = item
        return self.analyzed[version]


def matrix_file(row, compilers, journal, comparisons):
    """Record the candidate matrix, rule A and two experimental D5 orders."""
    obs = Observations(ROOT / row["path"], compilers, journal, "mando")
    candidate = row["installed_candidates"]
    groups = [candidate["primary"]]
    later = defaultdict(list)
    for version in candidate["later_series_only_after_primary_failure"]:
        later[version_tuple(version)[:2]].append(version)
    groups += [later[k] for k in sorted(later)]
    priority = selection_priority(row, compilers)
    preferred = obs.probe(priority) if priority else None
    low, high, active = None, None, []
    for group in groups:
        active += group
        for version in group:
            obs.compile(version)
        low, high = d3_endpoints(group, obs.probe)
        if low:
            break
    a_version = row["rule_a_version"]
    a = obs.compile(a_version) if a_version in compilers else None
    row["matrix"] = {v: {"returncode": c.returncode, "error_first_line": c.error_first_line,
                         "elapsed_seconds": c.elapsed_seconds} for v, c in obs.compiled.items()}
    row["activated_candidates"] = active
    row["rule_a_result"] = {"status": "unavailable" if a is None else "passed" if a.returncode == 0 else "failed",
                            "returncode": a.returncode if a else None,
                            "error_first_line": a.error_first_line if a else "not installed/trusted"}
    if not low:
        row["failure"] = "no_d3_candidate" if any(obs.compiled[v].returncode == 0 for v in active) else "no_compiling_candidate"
        return False
    selected = priority if preferred and preferred["d3"] else low
    descending = priority if preferred and preferred["d3"] else high
    selected_result = obs.probe(selected)
    base_minor = tuple(row["interval"][0][:2]) if row["interval"] else (0, 4)
    row["selection"] = {"ascending": selected, "descending": descending,
        "priority": priority, "priority_passed": bool(preferred and preferred["d3"]),
        "lowest_d3": low, "highest_d3": high,
        "moved_from_rule_version": selected != a_version,
        "crossed_minor": version_tuple(selected)[:2] != base_minor,
        "known_version_below_slither_floor": row.get("metadata_below_slither_floor", False),
        "ascending_descending_differ": selected != descending,
        "observed_d3_versions": sorted([v for v, r in obs.analyzed.items() if r["d3"]], key=version_tuple)}
    row["selected_slither"] = {k: v for k, v in selected_result.items() if k not in ("nodes", "duplicate_key4")}
    row["selected_duplicate_key4_count"] = len(selected_result["duplicate_key4"])
    row["cross_version"] = None
    if low != high:
        comparison = compare_nodes(obs.probe(low)["nodes"], obs.probe(high)["nodes"])
        selected_comparison = compare_nodes(selected_result["nodes"], obs.probe(high)["nodes"])
        row["cross_version"] = {"low": low, "high": high,
            "lowest_highest": {k: v["equal"] for k, v in comparison.items()},
            "selected_highest": {k: v["equal"] for k, v in selected_comparison.items()}}
        comparisons.write(json.dumps({"path": row["path"], "sha256": row["sha256"],
            "low": low, "selected": selected, "high": high,
            "lowest_highest": comparison, "selected_highest": selected_comparison}, sort_keys=True) + "\n")
        comparisons.flush()
    return True


def corpus_matrix(rows, compilers, output, journal, result):
    """Run the regression once; a no-success input leaves a sealed partial run."""
    started = time.monotonic()
    with (output / "cross_version.jsonl").open("x", encoding="utf8") as comparisons:
        for i, row in enumerate(rows, 1):
            result["compilation_executed"] = True
            result["slither_executed"] = True
            if not matrix_file(row, compilers, journal, comparisons):
                result["blockers"].append({"kind": row["failure"], "path": row["path"]})
                return False
            if i % 20 == 0 or i == len(rows):
                print("CP0 matrix {}/{}; {:.1f}s".format(i, len(rows), time.monotonic() - started), flush=True)
                gc.collect()
    cross = [r["cross_version"] for r in rows if r["cross_version"]]
    result["matrix_summary"] = {
        "files": len(rows), "rule_a": dict(Counter(r["rule_a_result"]["status"] for r in rows)),
        "selected_d3_pass": sum(r["selected_slither"]["d3"] for r in rows),
        "selected_missing_filename_nodes": sum(r["selected_slither"]["counts"]["missing_filename"] for r in rows),
        "selected_empty_cfg_files": sum(r["selected_slither"]["empty_cfg"] for r in rows),
        "selected_duplicate_key4_files": sum(r["selected_duplicate_key4_count"] > 0 for r in rows),
        "ascending_versions": dict(Counter(r["selection"]["ascending"] for r in rows)),
        "descending_versions": dict(Counter(r["selection"]["descending"] for r in rows)),
        "ascending_descending_differ": sum(r["selection"]["ascending_descending_differ"] for r in rows),
        "moved_from_rule_version": sum(r["selection"]["moved_from_rule_version"] for r in rows),
        "crossed_minor": sum(r["selection"]["crossed_minor"] for r in rows),
        "two_d3_versions": len(cross), "cross_version_equal": {
            pair: {k: sum(r[pair][k] for r in cross) for k in ("key4", "slithir", "source_length")}
            for pair in ("lowest_highest", "selected_highest")},
        "elapsed_seconds": time.monotonic() - started}
    result["cp2_runtime_estimate"] = {
        "observed_selected_slither_seconds": sum(r["selected_slither"]["elapsed_seconds"] for r in rows),
        "observed_selected_solc_seconds": sum(r["matrix"][r["selection"]["ascending"]]["elapsed_seconds"] for r in rows),
        "basis": "Serial CPU, observed solc + Slither times for 846 selected versions; excludes storage, regression and serialization",
        "not_a_complete_cp2_wall_time_prediction": True}
    return True


def compatibility(compilers, journal):
    """Probe every installed version, with pre-floor releases as controls."""
    fixture_root = ROOT / "compile_repair/tests/fixtures"
    results = []
    common = ["state_read_write", "internal_call", "modifier", "event", "external_call", "inheritance"]
    for version in sorted(compilers, key=version_tuple):
        minor = version_tuple(version)[1]
        names = ["compat_04.sol" if minor == 4 else "compat_05.sol" if minor == 5 else
                 "compat_06.sol" if minor == 6 else "compat_07.sol" if minor == 7 else "compat_08.sol"]
        if version_tuple(version) >= (0, 8, 4):
            names.append("compat_08_errors.sol")
        for name in names:
            path = fixture_root / name
            obs = Observations(path, compilers, journal, "compatibility")
            compiled = obs.compile(version)
            analysis = obs.probe(version)
            features = ["custom_error"] if name.endswith("errors.sol") else common + (
                ["try_catch"] if minor >= 6 else []) + (["unchecked"] if minor >= 8 else [])
            results.append({"version": version, "fixture": str(path.relative_to(ROOT)),
                "source_sha256": compiled.source_sha256, "features": features,
                "below_supported_floor": version_tuple(version) < (0, 4, 12),
                "solc_returncode": compiled.returncode,
                "slither": {k: v for k, v in analysis.items() if k != "nodes"}})
            print("CP0 compatibility {} {}: solc={} D3={}".format(version, name, compiled.returncode, analysis["d3"]), flush=True)
        gc.collect()
    by_version = {v: all(r["slither"]["d3"] for r in results if r["version"] == v) for v in compilers}
    return {"results": results, "all_applicable_probes_pass_by_version": by_version,
        "supported_range_failures": [r for r in results if not r["below_supported_floor"] and not r["slither"]["d3"]],
        "scope": "Handwritten feature probes only; not all syntax, all patches or arbitrary projects",
        "feature_sources": {
            "try_catch": "https://docs.soliditylang.org/en/v0.6.0/060-breaking-changes.html",
            "unchecked": "https://docs.soliditylang.org/en/v0.8.0/080-breaking-changes.html",
            "custom_error_since_0_8_4": "https://www.soliditylang.org/blog/2021/04/21/solidity-0.8.4-release-announcement/"}}


def survey(output, metadata_authorization, inventory_only=False, trusted_additions=()):
    """Run CP0 once, preserving the first blocker and every prior observation."""
    output = Path(output).resolve()
    artifact_root = (ROOT / "compile_repair/artifacts").resolve()
    if artifact_root not in output.parents:
        raise ValueError("Survey output must be a new compile_repair/artifacts subdirectory")
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    result = {"schema": "compile-repair-cp0-recon-v2", "status": "running", "blockers": [],
              "compilation_executed": False, "slither_executed": False,
              "training_executed": False, "llm_calls": 0, "cost_usd": 0,
              "root": str(ROOT), "command": {"module": "compile_repair.cli", "subcommand": "survey",
                  "output": str(output), "metadata_authorization": str(Path(metadata_authorization).resolve()),
                  "inventory_only": inventory_only, "trusted_additions": [str(Path(p).resolve()) for p in trusted_additions]},
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
        del report
        merged, addition_refs, release_index = load_additions(trusted["compilers"], trusted_additions)
        result["evidence"]["trusted_additions"] = addition_refs
        compilers, environment, missing_trusted = inventory(merged)
        result["environment"] = environment
        result["compilers"] = {v: asdict(c) for v, c in compilers.items()}
        result["missing_trusted_versions"] = missing_trusted
        result["release_coverage"] = release_coverage(release_index, compilers)
        sums = ROOT / "compile_repair/artifacts/cr_pre_v1/solc_github_static_SHA256SUMS"
        known = set(release_index["releases"]) if release_index else (
            set(re.findall(r"solc-(\d+\.\d+\.\d+)", sums.read_text())) | set(merged))
        result["evidence"]["known_release_window"] = {"source": "verified official index" if release_index else str(sums),
            "note": "Missing counts are relative to an observed release snapshot, never guessed."}
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
        result["status"] = "blocked_missing_compilers" if result["blockers"] else "inventory_only"
        if not result["blockers"] and not inventory_only:
            with (output / "invocations.jsonl").open("x", encoding="utf8") as journal:
                if corpus_matrix(rows, compilers, output, journal, result):
                    result["compatibility"] = compatibility(compilers, journal)
                    failures = result["compatibility"]["supported_range_failures"]
                    result["status"] = "awaiting_d16" if failures else "complete"
                    if failures:
                        result["blockers"].append({"kind": "d16_slither_compatibility", "failed_probes": len(failures)})
                else:
                    result["status"] = "blocked_regression"
        result["not_run"] = [] if "compatibility" in result else [
            "full compiler/Slither survey or compatibility probes incomplete; see per-file observations"]
        if any(hashlib.sha256((ROOT / r["path"]).read_bytes()).hexdigest() != r["sha256"] for r in rows):
            raise ValueError("Corpus bytes changed during survey")
    except Exception as exc:
        result.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
    result["elapsed_seconds"] = time.monotonic() - started
    result["implementation_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT / "compile_repair").rglob("*.py")) if "artifacts" not in p.parts and "tests" not in p.parts}
    result["fixture_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT / "compile_repair/tests/fixtures").glob("*.sol"))}
    write_json(output / "recon.json", result)
    write_json(output / "seal.json", {"schema": "compile-repair-cp0-seal-v2", "files": {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file()}})
    return result
