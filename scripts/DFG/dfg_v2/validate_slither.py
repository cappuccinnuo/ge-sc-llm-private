"""Optional, offline Slither comparison of the frozen Prompt 5 graph store.

No compiler is installed, selected globally, downloaded or executed by default.
A future real run requires an explicit hash-bound trusted-compiler JSON:
{"compilers": {"0.4.25": {"path": "/existing/solc", "sha256": "..."}}}
Only exact versions already bound in source metadata are eligible. Do not use
auto_version_solc.main: it downloads versions and guesses a default version.

L2 compares raw occurrence start lines. Slither CFG node start lines are a
coarser location; multiline discrepancies are not automatically v2 defects.
L1 is explicitly PARTIAL: frozen audits contain projected def-use endpoints,
not every local read/write occurrence. Its recall is deliberately undefined.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path

VERSION = "dfg-v2-slither-validation-v1"
TASKS = ("reentrancy_contract", "access_control_contract")
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORE = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/graphs_v1/store.json"
L1_SCOPE = "partial_projected_def_use_endpoint_start_lines; not all local occurrences"
CATEGORIES = ("grammar_difference", "alias", "inheritance", "inline_assembly",
              "modifier_inlining", "intentional_approximation", "v2_fallback", "other")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def _checked(ref):
    path = Path(ref["path"]).resolve()
    if _sha(path) != ref["sha256"]:
        raise ValueError("SHA mismatch: " + str(path))
    return path


def inspect_environment():
    """Read installed module/package/compiler identities without subprocesses."""
    def found(name):
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            spec = None
        return str(spec.origin) if spec else None

    packages = {}
    try:
        import importlib_metadata
        for name in ("slither-analyzer", "solc-select", "crytic-compile"):
            try:
                packages[name] = importlib_metadata.version(name)
            except importlib_metadata.PackageNotFoundError:
                packages[name] = None
    except ImportError:
        packages["metadata_unavailable"] = True
    modules = {name: found(name) for name in ("slither", "solc_select", "crytic_compile")}
    commands = {name: shutil.which(name) for name in ("slither", "solc-select", "solc")}
    artifacts = Path.home() / ".solc-select/artifacts"
    installed = []
    if artifacts.is_dir():
        for path in sorted(artifacts.glob("solc-*/solc-*")):
            if path.is_file():
                installed.append(dict(path=str(path.resolve()), sha256=_sha(path),
                                      bytes=path.stat().st_size))
    reasons = []
    if not modules["slither"]:
        reasons.append("slither_analyzer_unavailable")
    if not modules["crytic_compile"]:
        reasons.append("crytic_compile_unavailable")
    if packages.get("slither-analyzer") != "0.8.0":
        reasons.append("unsupported_or_unverified_slither_version")
    if not modules["solc_select"] or not commands["solc-select"]:
        reasons.append("solc_select_unavailable")
    if not installed:
        reasons.append("no_local_solc_select_artifacts")
    return dict(modules=modules, commands=commands, packages=packages,
                installed_compilers=installed, skip_reasons=reasons,
                compiler_executed=False, installation_attempted=False,
                network_requested=False)


def exact_version(record):
    metadata = record.get("metadata")
    version = metadata.get("version") if isinstance(metadata, dict) else None
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        return None
    # Full metadata/CSV binding is checked by load_manifest before this function.
    if metadata.get("source_sha256") != record.get("sha256"):
        raise ValueError("Version metadata belongs to a different source")
    return version


def compiler_for(record, environment, trusted=None):
    version = exact_version(record)
    if version is None:
        return None, "no_bound_exact_compiler_version"
    if environment["skip_reasons"]:
        return None, ";".join(environment["skip_reasons"])
    if not trusted or version not in trusted:
        return None, "local_compiler_not_explicitly_authorized"
    compiler = trusted[version]
    path = _checked(compiler)
    installed = {entry["path"]: entry["sha256"]
                 for entry in environment["installed_compilers"]}
    if installed.get(str(path)) != compiler["sha256"]:
        raise ValueError("Trusted compiler is not an inventoried local solc-select artifact")
    if not os.access(str(path), os.X_OK):
        return None, "local_compiler_not_executable"
    return str(path), None


def raw_line(raw, offset):
    if isinstance(raw, str):
        raw = raw.encode("utf8")
    if type(offset) is not int or offset < 0 or offset > len(raw):
        raise ValueError("Invalid raw UTF-8 byte offset")
    return raw[:offset].count(b"\n") + 1


def _put(result, fact, *tags):
    result.setdefault(fact, set()).update(t for t in tags if t)


def v2_facts(audit, file, raw):
    """Extract existing evidence only; no source analyzer and no graph mutation."""
    result = {"L1": {}, "L2": {}}
    l1, l2 = audit["layers"]["L1"], audit["layers"]["L2"]
    record = l1.get("files", {}).get(file, {})
    anchors = {entry["node_id"]: entry for entry in record.get("anchors", [])}
    for ev in l1.get("evidence", []):
        # Source/target identities select anchors in this exact file.
        if ev["source"] not in anchors or ev["target"] not in anchors:
            continue
        symbol = ev["symbol"]
        name = symbol.rsplit(":", 1)[-1]
        for side, kind in (("source", "DEF"), ("target", "USE")):
            anchor = anchors[ev[side]]
            start = anchor["start"]
            if kind == "DEF" and anchor["role"] in (
                    "function_definition", "constructor_definition"):
                # Parameter definitions use their recorded declaration byte.
                try:
                    start = int(symbol.rsplit(":", 2)[-2])
                except (ValueError, IndexError):
                    raise ValueError("Missing declaration byte in L1 symbol identity")
            _put(result["L1"], (raw_line(raw, start), name, kind), "partial_endpoint")
    statuses = Counter()
    for ev in l2.get("evidence", []):
        if ev["file"] != file:
            continue
        statuses[ev["status"]] += 1
        kind = {"READS_STATE": "READ", "WRITES_STATE": "WRITE"}[ev["relation"]]
        tags = []
        if ev.get("via_alias"):
            tags.append("alias")
        if ev.get("callable_kind") == "modifier_definition":
            tags.append("modifier_inlining")
        _put(result["L2"], (raw_line(raw, ev["occurrence"]["start"]),
                            ev["state"]["name"], kind), *tags)
    return result, dict(L1_scope=L1_SCOPE, L2_scope="raw_occurrence_start_line",
                        L2_projection_statuses=dict(statuses))


def _mapping(obj):
    value = getattr(obj, "source_mapping", None)
    return value if isinstance(value, dict) else {}


def slither_facts(slither, path, raw):
    """Use Slither 0.8 CFG read/write sets, without invoking another analyzer."""
    result = {"L1": {}, "L2": {}}
    target = Path(path).resolve()
    counts = Counter()
    seen = set()
    for contract in slither.contracts:
        functions = list(contract.functions) + list(contract.modifiers)
        for function in functions:
            if id(function) in seen:
                continue
            seen.add(id(function))
            is_modifier = function in contract.modifiers
            for node in function.nodes:
                counts["source_nodes_seen"] += 1
                if not isinstance(getattr(node, "source_mapping", None), dict):
                    counts["unsupported_source_mapping"] += 1
                    continue
                mapping = _mapping(node)
                filename = mapping.get("filename_absolute")
                if not filename or Path(filename).resolve() != target:
                    counts["foreign_or_unmapped_nodes"] += 1
                    continue
                if type(mapping.get("start")) is not int:
                    counts["missing_start_byte"] += 1
                    continue
                line = raw_line(raw, mapping["start"])
                counts["cfg_nodes"] += 1
                local_vars = (list(getattr(node, "local_variables_read", ())) +
                              list(getattr(node, "local_variables_written", ())))
                alias = any(getattr(var, "location", None) == "storage" for var in local_vars)
                for layer, attr, kind in (
                        ("L2", "state_variables_read", "READ"),
                        ("L2", "state_variables_written", "WRITE"),
                        ("L1", "local_variables_read", "USE"),
                        ("L1", "local_variables_written", "DEF")):
                    for variable in getattr(node, attr, ()):
                        tags = []
                        if is_modifier:
                            tags.append("modifier_inlining")
                        if alias and layer == "L2":
                            tags.append("alias")
                        if len(mapping.get("lines", ())) > 1:
                            tags.append("multiline_cfg_location")
                        _put(result[layer], (line, variable.name, kind), *tags)
    return result, dict(counts)


def compare_facts(candidate, reference, partial=False):
    """Exclude alias/modifier context from error counts, not from the report."""
    exclusions = {"alias", "modifier_inlining"}
    all_facts = set(candidate) | set(reference)
    excluded = {f for f in all_facts
                if (candidate.get(f, set()) | reference.get(f, set())) & exclusions}
    cand, ref = set(candidate) - excluded, set(reference) - excluded
    matched = cand & ref
    missing, extra = ref - cand, cand - ref
    return dict(candidate_count=len(cand), reference_count=len(ref), matched=len(matched),
                precision=len(matched)/len(cand) if cand else None,
                recall=None if partial or not ref else len(matched)/len(ref),
                recall_defined=not partial and bool(ref),
                full_occurrence_metrics=not partial,
                missing=[list(f) for f in sorted(missing)],
                extra=[list(f) for f in sorted(extra)],
                excluded=[dict(fact=list(f), reasons=sorted(
                    (candidate.get(f, set()) | reference.get(f, set())) & exclusions))
                          for f in sorted(excluded)],
                missing_role="outside_partial_endpoint_evidence" if partial else "reference_only")


def mismatch_category(fact, side, audit, file, raw, tags):
    """Evidence-based screening category, never a claim of confirmed v2 bug."""
    if "alias" in tags:
        return "alias"
    if "modifier_inlining" in tags:
        return "modifier_inlining"
    if "multiline_cfg_location" in tags:
        return "grammar_difference"
    l1 = audit["layers"]["L1"].get("files", {}).get(file, {})
    for function in l1.get("analysis", {}).get("functions", []):
        if (function.get("status") != "supported" and
                raw_line(raw, function["start"]) <= fact[0] <= raw_line(raw, function["end"])):
            return "v2_fallback"
    lines = raw.decode("utf8").splitlines()
    line = lines[fact[0]-1] if 0 < fact[0] <= len(lines) else ""
    if re.search(r"\bassembly\b", line):
        return "inline_assembly"
    # No guess that all mismatches in an inherited/aggregate-containing file
    # have that cause. Unresolved causes stay "other" for manual review.
    return "other"


def summarize(files):
    """Only successfully compiled/comparable files enter metric denominators."""
    compared = [f for f in files if f["status"] == "compared"]
    metrics = {}
    for layer in ("L1", "L2"):
        rows = [f["comparison"][layer] for f in compared]
        candidate = sum(r["candidate_count"] for r in rows)
        reference = sum(r["reference_count"] for r in rows)
        matched = sum(r["matched"] for r in rows)
        metrics[layer] = dict(comparable_files=len(rows), candidate_count=candidate,
            reference_count=reference, matched=matched,
            precision=matched/candidate if candidate else None,
            recall=matched/reference if layer == "L2" and reference else None,
            full_occurrence_metrics=layer == "L2",
            scope=L1_SCOPE if layer == "L1" else "raw_occurrence_vs_CFG_node_start_lines")
    return dict(total_files=len(files), compared_files=len(compared),
                skipped_files=sum(f["status"] == "skipped" for f in files),
                failed_files=sum(f["status"] == "compile_failed" for f in files),
                skip_reasons=dict(Counter(f.get("reason") for f in files
                                         if f["status"] != "compared")), metrics=metrics)


def _compile(path, compiler):
    # Only reached for an existing, hash-inventoried, explicitly trusted binary.
    # A .sol file plus an absolute compiler path avoids package-manager builds.
    from slither.slither import Slither
    return Slither(str(path), solc=str(compiler), solc_disable_warnings=True)


def run(store_path, output, trusted_compilers=None):
    from .inputs import load_manifest
    from .store import verify_store
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing validation output: " + str(output))
    store_path = Path(store_path).resolve()
    verification = verify_store(store_path)
    store = _json(store_path)
    manifest = load_manifest(_checked(store["input_manifest"]), check_files=True)
    environment = inspect_environment()
    trusted = {}
    trusted_ref = None
    if trusted_compilers is not None:
        trusted_path = Path(trusted_compilers).resolve()
        trusted = _json(trusted_path)["compilers"]
        trusted_ref = dict(path=str(trusted_path), sha256=_sha(trusted_path))
    report = dict(version=VERSION, graph_store_verification=verification,
        store=dict(path=str(store_path), sha256=_sha(store_path)),
        environment=environment, trusted_compiler_manifest=trusted_ref,
        tasks={}, limitations=[
            "Slither CFG start lines are coarser than v2 raw occurrence start lines.",
            "L1 frozen evidence is partial; no full local-occurrence recall is reported.",
            "Alias and modifier contexts are listed separately, not counted as v2 errors.",
            "Mismatch categories require review; disagreement does not prove a defect.",
            "Exact compiler versions require bound metadata; pragma/defaults are not guessed."],
        compilation_executed=False, training_executed=False)
    for task in TASKS:
        if task not in store["tasks"] or task not in manifest["tasks"]:
            raise ValueError("Missing required contract task in verified store: " + task)
        entry = store["tasks"][task]["graphs"]["F3"]
        audit = _json(_checked(entry["audit"]))
        row = manifest["tasks"][task]
        files, examples, categories = [], [], Counter()
        for filename, source in sorted(row["sources"].items()):
            path = _checked(source)
            compiler, reason = compiler_for(source, environment, trusted)
            record = dict(file=filename, source_sha256=source["sha256"],
                          version=exact_version(source))
            if reason:
                record.update(status="skipped", reason=reason)
                files.append(record)
                continue
            report["compilation_executed"] = True
            try:
                slither = _compile(path, compiler)
            except Exception as exc:
                record.update(status="compile_failed", reason=type(exc).__name__,
                              detail=str(exc)[:2000])
                files.append(record)
                continue
            raw = path.read_bytes()
            candidate, evidence = v2_facts(audit, filename, raw)
            reference, extraction = slither_facts(slither, path, raw)
            if extraction.get("unsupported_source_mapping") or not extraction.get("cfg_nodes"):
                record.update(status="skipped", reason="slither_source_mapping_not_comparable",
                              slither_extraction=extraction)
                files.append(record)
                continue
            comparison = {layer: compare_facts(candidate[layer], reference[layer],
                                               partial=layer == "L1")
                          for layer in ("L1", "L2")}
            record.update(status="compared", comparison=comparison, v2_scope=evidence,
                          slither_extraction=extraction,
                          compiler=dict(path=compiler, sha256=_sha(compiler)))
            for layer in ("L1", "L2"):
                for side in ("missing", "extra"):
                    for fact_list in comparison[layer][side]:
                        fact = tuple(fact_list)
                        tags = candidate[layer].get(fact, set()) | reference[layer].get(fact, set())
                        category = mismatch_category(fact, side, audit, filename, raw, tags)
                        categories[category] += 1
                        if len(examples) < 20:
                            examples.append(dict(file=filename, source_sha256=source["sha256"],
                                layer=layer, side=side, fact=fact_list, category=category,
                                classification_status="requires_review",
                                partial_evidence=layer == "L1"))
            files.append(record)
        report["tasks"][task] = dict(summary=summarize(files), files=files,
            first_20_mismatches=examples,
            mismatch_categories={name: categories[name] for name in CATEGORIES})
    report["status"] = ("compared" if any(t["summary"]["compared_files"]
                                        for t in report["tasks"].values()) else "skipped")
    # Verify again that no analyzed input bytes changed during optional compiler use.
    for task in TASKS:
        for source in manifest["tasks"][task]["sources"].values():
            _checked(source)
        _checked(store["tasks"][task]["graphs"]["F3"]["graph"])
        _checked(store["tasks"][task]["graphs"]["F3"]["audit"])
    if _sha(store_path) != report["store"]["sha256"]:
        raise ValueError("Graph store changed during validation")
    output.mkdir(parents=True)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    (output / "report.json").write_text(text, encoding="utf8")
    (output / "report.seal.json").write_text(json.dumps(dict(
        version=VERSION, report_sha256=_sha(output/"report.json"),
        store_sha256=report["store"]["sha256"], training_executed=False),
        indent=2) + "\n", encoding="utf8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", default=str(DEFAULT_STORE))
    parser.add_argument("--output", required=True)
    parser.add_argument("--trusted-compilers",
                        help="Explicit authorization manifest for existing inventoried compiler hashes")
    args = parser.parse_args(argv)
    report = run(args.store, args.output, args.trusted_compilers)
    print(json.dumps(dict(status=report["status"], compilation_executed=report["compilation_executed"],
          tasks={k: v["summary"] for k, v in report["tasks"].items()}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
