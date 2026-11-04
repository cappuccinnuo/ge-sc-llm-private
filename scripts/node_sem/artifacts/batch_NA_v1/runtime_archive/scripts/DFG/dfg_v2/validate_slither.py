"""Prompt 6c: read-only Slither 0.8 comparison with explicit compiler hashes.

The legacy helper APIs remain available for Prompt 6 tests. The real runner
uses complete unprojected L1 IR events and frozen L2 evidence. Compiler choice
is metadata first, otherwise the unchanged auto_version_solc rule. A guessed
compiler is NEVER injected as source-analysis metadata. No installation or
global compiler switch is performed by this module.
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

VERSION = "dfg-v2-slither-validation-v2"
TASKS = ("reentrancy_contract", "access_control_contract")
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STORE = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/graphs_v1/store.json"
L1_SCOPE = "partial_projected_def_use_endpoint_start_lines; not all local occurrences"
CATEGORIES = ("grammar_difference", "alias", "inheritance", "inline_assembly",
              "entry_initialization", "unreachable_ir", "identity_ambiguity",
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
    raw[:offset].decode("utf8")
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



def select_version(record):
    """Apply the repository rule verbatim; report defaults honestly."""
    from auto_version_solc import get_solc_version, pattern, DEFAULT_VERSION
    path = _checked(record)
    version = exact_version(record)
    source = path.read_text(encoding="utf8")
    matches = pattern.findall(source)
    if version is not None:
        origin = "metadata"
    else:
        version = get_solc_version(str(path))
        origin = "pragma_derived" if matches else "fallback_default"
    return dict(version=version, origin=origin, pragma_matches=matches,
                selection_rule="bound_metadata_else_auto_version_solc.get_solc_version",
                default_version=DEFAULT_VERSION,
                compiler_version_is_not_analysis_metadata=True)


def compiler_for_selection(selection, environment, trusted=None):
    """Require explicit trusted SHA and inventoried binary; never install."""
    if environment["skip_reasons"]:
        return None, ";".join(environment["skip_reasons"])
    version = selection["version"]
    if not trusted or version not in trusted:
        return None, "local_compiler_not_explicitly_authorized"
    ref = trusted[version]
    path = _checked(ref)
    inventory = {entry["path"]: entry["sha256"]
                 for entry in environment["installed_compilers"]}
    if inventory.get(str(path)) != ref["sha256"]:
        raise ValueError("Trusted compiler is not an inventoried local solc-select artifact")
    if not os.access(str(path), os.X_OK):
        return None, "local_compiler_not_executable"
    return str(path), None


def _load_inputs(store_path):
    from .inputs import load_manifest
    from .store import verify_store
    path = Path(store_path).resolve()
    verification = verify_store(path)
    store = _json(path)
    manifest = load_manifest(_checked(store["input_manifest"]), check_files=True)
    for task in TASKS:
        if task not in store["tasks"] or task not in manifest["tasks"]:
            raise ValueError("Missing required contract task in verified store: " + task)
    return path, verification, store, manifest


def list_versions(store_path, output):
    path, verification, store, manifest = _load_inputs(store_path)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing version output: " + str(output))
    rows = []
    for task in TASKS:
        for filename, source in sorted(manifest["tasks"][task]["sources"].items()):
            rows.append(dict(task=task, file=filename, source_sha256=source["sha256"],
                             path=source["path"], selection=select_version(source)))
    versions = sorted({r["selection"]["version"] for r in rows},
                      key=lambda version: tuple(map(int, version.split("."))))
    report = dict(version=VERSION, status="versions_listed",
        store=dict(path=str(path), sha256=_sha(path)), store_verification=verification,
        selector_source=dict(path=str(ROOT/"auto_version_solc.py"),
                             sha256=_sha(ROOT/"auto_version_solc.py")),
        files=rows, compilation_executed=False, installation_attempted=False,
        versions=[dict(version=v, files=sum(r["selection"]["version"] == v for r in rows),
                       origins=dict(Counter(r["selection"]["origin"] for r in rows
                            if r["selection"]["version"] == v))) for v in versions],
        origin_counts=dict(Counter(r["selection"]["origin"] for r in rows)),
        note="A selected pragma/default version is an attempted compiler, not verified provenance.")
    output.mkdir(parents=True)
    _write_json(output/"versions.json", report)
    _write_json(output/"versions.seal.json", dict(version=VERSION,
        versions_sha256=_sha(output/"versions.json"), store_sha256=_sha(path),
        selector_sha256=report["selector_source"]["sha256"]))
    return report


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n",
                          encoding="utf8")


def _filename_status(mapping, target):
    filename = mapping.get("filename_absolute")
    if filename is None or filename == "":
        return "missing_filename"
    if not isinstance(filename, str) or not Path(filename).is_absolute():
        return "invalid_filename"
    return "target" if Path(filename).resolve() == target else "foreign"


def reference_comparability(counts):
    blockers = {name: counts.get(name, 0) for name in (
        "unsupported_source_mapping", "missing_filename", "invalid_filename",
        "missing_start_byte", "invalid_start_byte") if counts.get(name)}
    if not counts.get("cfg_nodes"):
        blockers["no_target_cfg_nodes"] = 1
    return dict(status="not_comparable" if blockers else "comparable",
                blockers=blockers, foreign_nodes_excluded=counts.get("foreign_nodes", 0))


def _span_identity(obj, raw, target, required=False):
    mapping = _mapping(obj)
    if _filename_status(mapping, target) != "target":
        # An unbound byte offset is not evidence that the object belongs to
        # the target file. Never synthesize a missing filename from context.
        return None
    start, length = mapping.get("start"), mapping.get("length")
    if type(start) is not int:
        if required:
            raise ValueError("Missing Slither source identity byte")
        return None
    raw_line(raw, start)
    if length is not None:
        if type(length) is not int or length < 0:
            raise ValueError("Invalid Slither source identity length")
        raw_line(raw, start+length)
    return dict(start=start, end=start+length if length is not None else None,
                filename=str(target))


def slither_full_facts(slither, path, raw):
    """Collect CFG read/write sets with declaration provenance.

    Do not synthesize parameter/return writes absent from Slither's CFG sets.
    Preserve every primary comparison triple. Ambiguous identities are reported
    separately rather than silently counted as correctly bound occurrences.
    """
    result = {"L1": {}, "L2": {}}
    target = Path(path).resolve()
    counts, occurrences, contexts, duplicates, seen = Counter(), [], [], [], set()
    for contract in slither.contracts:
        modifiers = list(contract.modifiers)
        for function in list(contract.functions) + modifiers:
            fm = _span_identity(function, raw, target)
            if fm is None:
                counts["unknown_function_identity"] += 1
            is_modifier = function in modifiers
            declarer = getattr(function, "contract_declarer", None)
            inherited = declarer is not None and declarer is not contract
            semantic_id = ((fm["start"], fm["end"], is_modifier)
                           if fm is not None else ("object", id(function)))
            if semantic_id in seen:
                counts["duplicate_function_contexts"] += 1
                duplicates.append(dict(function=fm, modifier=is_modifier,
                    contract=getattr(contract, "name", None),
                    declarer=getattr(declarer, "name", None), inherited=inherited))
                # The same source body may have context-dependent Slither reads.
                # Keep every context; primary triples are deduplicated by _put.
            seen.add(semantic_id)
            context = dict(name=getattr(function, "canonical_name",
                                       getattr(function, "name", None)),
                           source=fm, modifier=is_modifier, occurrences=0,
                           contract=getattr(contract, "name", None),
                           declarer=getattr(declarer, "name", None), inherited=inherited)
            context["context_index"] = len(contexts)
            contexts.append(context)
            for node in function.nodes:
                counts["source_nodes_seen"] += 1
                if not isinstance(getattr(node, "source_mapping", None), dict):
                    counts["unsupported_source_mapping"] += 1
                    continue
                mapping = _mapping(node)
                location = _filename_status(mapping, target)
                if location == "foreign":
                    counts["foreign_nodes"] += 1
                    continue
                if location != "target":
                    counts[location] += 1
                    continue
                if mapping.get("start") is None:
                    counts["missing_start_byte"] += 1
                    continue
                if type(mapping["start"]) is not int:
                    counts["invalid_start_byte"] += 1
                    continue
                nm = _span_identity(node, raw, target, required=True)
                line = raw_line(raw, nm["start"])
                counts["cfg_nodes"] += 1
                local_vars = list(getattr(node, "local_variables_read", ())) + list(
                    getattr(node, "local_variables_written", ()))
                alias = any(getattr(var, "location", None) == "storage" for var in local_vars)
                for layer, attr, kind in (
                        ("L2", "state_variables_read", "READ"),
                        ("L2", "state_variables_written", "WRITE"),
                        ("L1", "local_variables_read", "USE"),
                        ("L1", "local_variables_written", "DEF")):
                    for variable in getattr(node, attr, ()):
                        vm = _span_identity(variable, raw, target)
                        if vm is None:
                            counts["unknown_variable_identity"] += 1
                        tags = []
                        if is_modifier:
                            tags.append("modifier_inlining")
                        if inherited:
                            tags.append("inheritance")
                        if alias and (layer == "L2" or getattr(variable, "location", None) == "storage"):
                            tags.append("alias")
                        if len(mapping.get("lines", ())) > 1:
                            tags.append("multiline_cfg_location")
                        fact = (line, variable.name, kind)
                        _put(result[layer], fact, *tags)
                        occurrences.append(dict(layer=layer, fact=list(fact), tags=tags,
                            function=fm, declaration=vm, node=nm,
                            canonical_name=getattr(variable, "canonical_name", None),
                            function_name=context["name"], modifier=is_modifier,
                            context_index=context["context_index"],
                            context_contract=context["contract"],
                            context_declarer=context["declarer"],
                            inherited_context=inherited))
                        context["occurrences"] += 1
    identities = {}
    for row in occurrences:
        key = (row["layer"], tuple(row["fact"]))
        ident = (row["function"]["start"] if row["function"] else None,
                 row["declaration"]["start"] if row["declaration"] else None,
                 row["canonical_name"])
        identities.setdefault(key, set()).add(ident)
    ambiguous = [dict(layer=layer, fact=list(fact),
                      identities=[list(i) for i in sorted(ids, key=repr)])
                 for (layer, fact), ids in sorted(identities.items())
                 if len(ids) > 1]
    return result, dict(counts=dict(counts), occurrences=occurrences,
                        comparability=reference_comparability(counts),
                        functions=contexts, duplicate_contexts=duplicates, ambiguous_triples=ambiguous,
                        parameter_writes_synthesized=False)


def reference_function_scopes(reference, extraction, inventory):
    """Partition reference triples by actual function byte identity, no name guess."""
    supported = {f["start"] for f in inventory["functions"] if f["status"] == "supported"}
    fallback = {f["start"] for f in inventory["functions"] if f["status"] != "supported"}
    groups = {"supported": {}, "fallback": {}, "unmapped": {}}
    for row in extraction["occurrences"]:
        if row["layer"] != "L1":
            continue
        start = row["function"]["start"] if row["function"] else None
        group = "supported" if start in supported else "fallback" if start in fallback else "unmapped"
        fact = tuple(row["fact"])
        _put(groups[group], fact, *reference.get(fact, set()))
    return groups


def identity_audit(candidate_inventory, reference_inventory):
    """Keep published triple metrics, expose declaration collisions/mismatches."""
    candidate = {}
    for row in candidate_inventory["occurrences"]:
        fact = (row["line"], row["name"], row["kind"])
        candidate.setdefault(fact, set()).add((row["function_start"], row["declaration"]["start"]))
    reference, unknown = {}, []
    for row in reference_inventory["occurrences"]:
        if row["layer"] != "L1":
            continue
        fact = tuple(row["fact"])
        if row["function"] is None or row["declaration"] is None:
            unknown.append(row)
            continue
        reference.setdefault(fact, set()).add((row["function"]["start"], row["declaration"]["start"]))
    mismatched = [dict(fact=list(fact), candidate=[list(i) for i in sorted(candidate[fact])],
                      reference=[list(i) for i in sorted(reference[fact])])
                  for fact in sorted(set(candidate) & set(reference))
                  if not candidate[fact].intersection(reference[fact])]
    return dict(primary_comparison="line_name_kind_triples",
        candidate_ambiguous_triples=candidate_inventory["ambiguous_triples"],
        reference_ambiguous_triples=reference_inventory["ambiguous_triples"],
        shared_triples_without_common_declaration=mismatched,
        reference_occurrences_missing_identity=unknown,
        triple_matches_do_not_prove_exact_binding=True)

def summarize_complete(files):
    result = summarize(files)
    compared = [row for row in files if row["status"] == "compared"]
    for layer in ("L1", "L2"):
        metric = result["metrics"][layer]
        metric["recall"] = (metric["matched"]/metric["reference_count"]
                            if metric["reference_count"] else None)
        metric["full_occurrence_metrics"] = True
        metric["scope"] = ("complete_unprojected_IR_event_symbol_sets_vs_Slither_CFG"
                           if layer == "L1" else "raw_occurrence_vs_CFG_node_start_lines")
        metric["ddg_edge_recall"] = False
    scope_totals = {}
    for key in ("supported", "fallback", "unmapped"):
        rows = [row["L1_reference_scopes"][key] for row in compared]
        scope_totals[key] = dict(
            reference_count=sum(row["reference_count"] for row in rows),
            candidate_count=sum(row["candidate_count"] for row in rows),
            matched=sum(row["matched"] for row in rows),
            raw_reference_triples=sum(row.get("raw_reference_triples", row["reference_count"])
                                      for row in rows),
            excluded_context_triples=sum(row.get("excluded_context_triples", 0) for row in rows))
        metric = scope_totals[key]
        metric["recall"] = metric["matched"]/metric["reference_count"] if metric["reference_count"] else None
    result["L1_reference_scopes"] = scope_totals
    result["not_comparable_files"] = sum(row["status"] == "not_comparable" for row in files)
    result["external_failure_phases"] = dict(Counter(
        row.get("failure_phase", "external_pipeline_unknown") for row in files
        if row["status"] == "compile_failed"))
    result["L1_fallback_functions"] = sum(row["v2_scope"]["L1"]["functions_fallback"]
                                        for row in compared)
    return result


def _category(fact, tags, layer, inventory, reference_scopes):
    for tag, category in (("alias", "alias"), ("modifier_inlining", "modifier_inlining"),
                          ("inheritance", "inheritance"),
                          ("entry_initialization", "entry_initialization"),
                          ("unreachable_ir", "unreachable_ir"),
                          ("multiline_cfg_location", "grammar_difference")):
        if tag in tags:
            return category
    if layer == "L1" and fact in reference_scopes["fallback"]:
        return "v2_fallback"
    return "other"


def failure_phase(exception):
    """Classify compiler failures even when Slither wraps their exception.

    Slither 0.8 raises SlitherError from an InvalidCompilation handler. Python
    retains that original exception in __context__ (or __cause__ for explicit
    chaining). Inspect both links without trusting error-message text; cycles
    must not hang reporting.
    """
    try:
        from crytic_compile.platform.exceptions import InvalidCompilation
    except ImportError:
        InvalidCompilation = ()
    try:
        from slither.exceptions import SlitherException
    except ImportError:
        SlitherException = ()
    pending, seen = [exception], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, InvalidCompilation):
            return "solc_compile"
        for attr in ("__cause__", "__context__"):
            linked = getattr(current, attr, None)
            if linked is not None:
                pending.append(linked)
    if isinstance(exception, SlitherException):
        return "slither_analysis"
    return "external_pipeline_unknown"


def run(store_path, output, trusted_compilers=None):
    from .l1_occurrences import extract as local_occurrences
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing validation output: " + str(output))
    store_path, verification, store, manifest = _load_inputs(store_path)
    environment = inspect_environment()
    trusted, trusted_ref = {}, None
    if trusted_compilers is not None:
        trusted_path = Path(trusted_compilers).resolve()
        trusted = _json(trusted_path)["compilers"]
        trusted_ref = dict(path=str(trusted_path), sha256=_sha(trusted_path))
    computation_paths = sorted(Path(__file__).parent.glob("*.py"))
    computation = {str(path): _sha(path) for path in computation_paths}
    report = dict(version=VERSION, graph_store_verification=verification,
        store=dict(path=str(store_path), sha256=_sha(store_path)),
        environment=environment, trusted_compiler_manifest=trusted_ref,
        computation_sha256=computation, tasks={}, limitations=[
            "Complete L1 means IR event-symbol sets, not individual token occurrences.",
            "Metrics compare read/write sets, not DATA_DEF_USE graph-edge recall.",
            "Raw statement/occurrence and Slither CFG start-line granularity can differ.",
            "Main metrics use the requested line/name/kind triples; declaration identities are audited separately.",
            "No parameter/return write absent from Slither CFG sets is synthesized.",
            "Alias and modifier contexts are listed separately rather than counted as v2 errors.",
            "Compiler selection does not alter the analyzer's original metadata.",
            "Mismatches are screening evidence, not automatically confirmed implementation defects."],
        compilation_executed=False, training_executed=False, graph_construction_executed=False)
    for task in TASKS:
        entry = store["tasks"][task]["graphs"]["F3"]
        audit = _json(_checked(entry["audit"]))
        files, examples, categories = [], [], Counter()
        sources = manifest["tasks"][task]["sources"]
        for index, (filename, source) in enumerate(sorted(sources.items())):
            path = _checked(source)
            selection = select_version(source)
            compiler, reason = compiler_for_selection(selection, environment, trusted)
            record = dict(file=filename, source_sha256=source["sha256"],
                          version=selection["version"], version_origin=selection["origin"],
                          compiler_selection=selection)
            if reason:
                record.update(status="skipped", reason=reason)
                files.append(record)
                continue
            report["compilation_executed"] = True
            print(json.dumps(dict(task=task, file=filename, index=index+1, total=len(sources),
                                  phase="compile", version=selection["version"])), flush=True)
            try:
                slither = _compile(path, compiler)
            except Exception as exc:
                record.update(status="compile_failed", reason=type(exc).__name__,
                              exception_module=type(exc).__module__,
                              failure_phase=failure_phase(exc), detail=str(exc)[:6000],
                              compiler=dict(path=compiler, sha256=_sha(compiler)))
                files.append(record)
                continue
            raw = path.read_bytes()
            candidate, old_scope = v2_facts(audit, filename, raw)
            # Crucial: original metadata, never the derived compiler version.
            candidate["L1"], local = local_occurrences(raw.decode("utf8"), filename,
                                                       source.get("metadata"))
            reference, extraction = slither_full_facts(slither, path, raw)
            counts = extraction["counts"]
            if extraction["comparability"]["status"] != "comparable":
                record.update(status="not_comparable", reason="slither_source_mapping_not_comparable",
                              comparability=extraction["comparability"],
                              slither_extraction=extraction,
                              compiler=dict(path=compiler, sha256=_sha(compiler)))
                files.append(record)
                continue
            comparison = {layer: compare_facts(candidate[layer], reference[layer])
                          for layer in ("L1", "L2")}
            reference_groups = reference_function_scopes(reference["L1"], extraction, local)
            scope_comparison = {}
            for group, ref in reference_groups.items():
                group_candidate = candidate["L1"] if group == "supported" else {}
                scope_comparison[group] = compare_facts(group_candidate, ref)
                scope_comparison[group]["raw_reference_triples"] = len(ref)
                scope_comparison[group]["excluded_context_triples"] = len(
                    scope_comparison[group]["excluded"])
                scope_comparison[group]["scope_note"] = (
                    "all accepted v2 event triples versus Slither functions in this group; "
                    "fallback/unmapped candidate sets deliberately empty")
            record.update(status="compared", comparison=comparison,
                v2_scope=dict(L1=local, L2={k:v for k,v in old_scope.items() if k.startswith("L2")}),
                slither_extraction=extraction, L1_reference_scopes=scope_comparison,
                L1_identity_audit=identity_audit(local, extraction),
                compiler=dict(path=compiler, sha256=_sha(compiler)))
            for layer in ("L1", "L2"):
                for side in ("missing", "extra"):
                    for fact_list in comparison[layer][side]:
                        fact = tuple(fact_list)
                        tags = candidate[layer].get(fact, set()) | reference[layer].get(fact, set())
                        category = _category(fact, tags, layer, local, reference_groups)
                        categories[category] += 1
                        if len(examples) < 20:
                            examples.append(dict(file=filename, source_sha256=source["sha256"],
                                layer=layer, side=side, fact=fact_list, category=category,
                                classification_status="requires_review", partial_evidence=False))
            files.append(record)
        origins = ("metadata", "pragma_derived", "fallback_default")
        report["tasks"][task] = dict(summary=summarize_complete(files), files=files,
            by_version_origin={origin: summarize_complete(
                [row for row in files if row["version_origin"] == origin]) for origin in origins},
            first_20_mismatches=examples,
            mismatch_categories={name: categories[name] for name in CATEGORIES})
    report["status"] = ("compared" if any(t["summary"]["compared_files"]
                                        for t in report["tasks"].values()) else "skipped")
    for task in TASKS:
        for source in manifest["tasks"][task]["sources"].values():
            _checked(source)
        _checked(store["tasks"][task]["graphs"]["F3"]["graph"])
        _checked(store["tasks"][task]["graphs"]["F3"]["audit"])
    if _sha(store_path) != report["store"]["sha256"]:
        raise ValueError("Graph store changed during validation")
    for path, digest in computation.items():
        if _sha(path) != digest:
            raise ValueError("Validation computation changed during run: " + path)
    output.mkdir(parents=True)
    _write_json(output/"report.json", report)
    _write_json(output/"report.seal.json", dict(
        version=VERSION, report_sha256=_sha(output/"report.json"),
        store_sha256=report["store"]["sha256"], computation_sha256=computation,
        training_executed=False, graph_construction_executed=False))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", default=str(DEFAULT_STORE))
    parser.add_argument("--output", required=True)
    parser.add_argument("--list-versions", action="store_true",
                        help="List exact attempted versions and provenance without compiling")
    parser.add_argument("--trusted-compilers",
                        help="Explicit authorization manifest for inventoried compiler hashes")
    args = parser.parse_args(argv)
    if args.list_versions:
        report = list_versions(args.store, args.output)
        print(json.dumps(dict(status=report["status"], versions=report["versions"],
                              origin_counts=report["origin_counts"]), indent=2))
    else:
        report = run(args.store, args.output, args.trusted_compilers)
        print(json.dumps(dict(status=report["status"],
            compilation_executed=report["compilation_executed"],
            tasks={k:v["summary"] for k,v in report["tasks"].items()}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
