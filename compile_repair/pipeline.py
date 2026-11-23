"""PROMPTS 3.1: one compiler, project assembly and dependency repair entry.

Files, snippets and CP3 project closures share one version/settings loop.
Copies and invocation records live in an exclusive store. Tool integrity failures stop the batch without retry.
"""
import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from pathlib import Path

from compile_repair.core.model import CompilationUnit, ManifestRecord, Patch, SourceFile
from compile_repair.core.provenance import apply_patches, mark_span, verify_provenance
from compile_repair.core.store import ArtifactStore, emit, sha256
from compile_repair.rules.dependencies import (OfflineIndex, build_index, dependency_choices,
    relative_repairs)
from compile_repair.rules.environment import (make_plan, mando_known_version,
    ordered_candidates, pragma_patches, settings_retry)
from compile_repair.toolchain.solc import compile_file, load_trusted_compilers, version_tuple, parse_diagnostics
from compile_repair.toolchain.slither import check_profile, run_slither
from compile_repair.toolchain.project import (compile_project, materialize_project,
    verify_project, resolve_project, ProjectIndex, parse_remapping, input_format_evidence,
    assembly_remappings, unpack_sources)
from scripts.DFG.models import Unsupported


def _environment(unit, compilers, store, journal, order, compile_fn, slither_fn, project,
                 project_compile_fn, prefix, initial_settings=(), origins=None, allow_override=True, already_copied=False):
    """Attempt one file or project using the same version/settings policy.

    Project imports are assembled without dependency repair. All input copies,
    provenance maps and D3 checks cover the closure, not only the entry file.
    """
    if project is None and len(unit.sources) != 1:
        raise ValueError("Multiple sources require an explicit project context")
    if project is not None:
        verify_project(project)
        if tuple(unit.sources) != project.files:
            raise ValueError("Unit sources differ from resolved project")
    source = unit.sources[0]
    inputs = [{"path": f.path, "sha256": f.sha256, "bytes": len(f.content), "kind": f.kind}
              for f in unit.sources]
    for f in unit.sources:
        if hashlib.sha256(f.content).hexdigest() != f.sha256:
            raise ValueError("Input record SHA256 mismatch")
    working, maps, originals = {}, {}, {}
    for f in unit.sources:
        name = Path(f.path).relative_to(project.root).as_posix() if project else f.path
        original, patches = (origins or {}).get(name, (f.content, ()))
        working[f.path], maps[f.path] = apply_patches(original, patches)
        originals[f.path] = original
        if working[f.path] != f.content:
            raise ValueError("Candidate contents differ from the recorded changes")
    record = ManifestRecord(unit.unit_id, inputs, "unrepaired", "no_candidate_compiler",
                            None, None, (), [], [], dict(maps))
    language, wrapper = input_format_evidence(source.content)
    inputs[0]["language_evidence"] = language
    if wrapper is not None or language["status"] == "non_solidity":
        record.reason = "standard_json_input" if wrapper is not None else "non_solidity_input"
        details = wrapper if wrapper is not None else language
        record.attempts.append(dict(details, stage="input_format"))
        return record
    if project is not None:
        store.write_json(prefix + "project.json", project.manifest())
        if project.issues:
            record.reason = "unresolved_imports"
            record.attempts.append({"stage": "project_assembly", "issues": project.issues})
            return record
        work_project = project if already_copied else materialize_project(project, store, prefix + "input_project", working)
        path = Path(work_project.root) / project.entry
    else:
        path = store.write_bytes(prefix + "input.sol", working[source.path])
    try:
        plan = make_plan([f.content for f in unit.sources], compilers,
                         unit.known_version, unit.regression, order)
    except Unsupported as exc:
        record.flags.append("unsupported_version_constraints")
        record.attempts.append({"stage": "environment_plan", "exception_type": type(exc).__name__,
                                "error_first_line": str(exc).splitlines()[0]})
        return record
    record.plan = plan
    record.flags.extend(plan.flags)
    if plan.override and not allow_override:
        record.attempts.append(dict(stage="environment_plan", error_first_line="No supported compiler in the declared intersection"))
        return record
    if plan.override and any(plan.groups):
        count = 0
        for f in unit.sources:
            patches = pragma_patches(f.content)
            count += len(patches)
            working[f.path], maps[f.path] = apply_patches(f.content, patches)
            verify_provenance(f.content, working[f.path], maps[f.path])
        if not count:
            raise ValueError("Override plan has no Solidity pragma to replace")
        if project is not None:
            work_project = materialize_project(project, store, prefix + "pragma_overridden_project", working)
            path = Path(work_project.root) / project.entry
        else:
            path = store.write_bytes(prefix + "pragma_overridden.sol", working[source.path])
        record.flags.append("pragma_overridden")
        record.provenance.update(maps)
    relative_maps = ({Path(f.path).relative_to(project.root).as_posix(): maps[f.path]
                      for f in unit.sources} if project is not None else {})
    any_solc_success = False
    base_series = tuple(plan.effective_interval[0][:2])
    for version in ordered_candidates(plan):
        crossed = not plan.override and version != plan.priority and version_tuple(version)[:2] != base_series
        if crossed and "crossed_minor" not in record.flags:
            record.flags.append("crossed_minor")
        settings, retry = initial_settings, None
        for retry_number in range(2):
            compiled = (project_compile_fn(work_project, compilers[version], settings=settings)
                        if project is not None else compile_fn(path, compilers[version], settings=settings))
            attempt = {"version": version, "settings": settings, "stage": "environment",
                       "round": len(record.attempts) + 1, "settings_retry": retry,
                       "crossed_minor": crossed, "solc": asdict(compiled), "slither": None}
            record.attempts.append(attempt)
            emit(journal, dict(kind="solc", unit_id=unit.unit_id, **asdict(compiled)))
            if compiled.timed_out:
                record.reason = "solc_timeout"
                break
            if compiled.returncode == 0:
                any_solc_success = True
                analysis = (slither_fn(compiled, profile="production", project=work_project)
                            if project is not None else slither_fn(compiled, profile="production"))
                emit(journal, dict(kind="slither", unit_id=unit.unit_id,
                                  **{k: v for k, v in analysis.items() if k != "graph"}))
                attempt["slither"] = {k: v for k, v in analysis.items() if k not in ("nodes", "graph")}
                if analysis["d3"] and (project is None or analysis["graph_usable"]):
                    def mark(node):
                        provenance = relative_maps[node["filename"]] if project is not None else maps[source.path]
                        return dict(node, provenance=mark_span(provenance, node["key5"][3], node["length"]))
                    marked = [mark(node) for node in analysis["nodes"]]
                    graph = dict(analysis["graph"])
                    graph["nodes"] = [mark(node) for node in graph["nodes"]]
                    graph_path = store.write_json(prefix + "graph.json", graph)
                    attempt["slither"]["graph_sha256"] = sha256(graph_path)
                    nodes = {"schema": "cp1-marked-node-facts-v1", "input_sha256": source.sha256,
                             "working_sha256": compiled.source_sha256, "nodes": marked,
                             "note": "Ordered CFG edges and calls are stored in graph.json"}
                    if project is not None:
                        nodes.update(schema="cp3-project-marked-node-facts-v1",
                                     input_files=inputs, working_files=work_project.manifest()["files"])
                    store.write_json(prefix + "nodes.json", nodes)
                    record.status, record.reason = "success", None
                    record.selected_version, record.settings = version, settings
                    if retry is not None:
                        record.flags.append("compiler_settings_retry")
                    break
                break
            retry_source = working[source.path]
            if project is not None:
                # Existing location-sensitive retry must inspect the file that
                # owns the first located error, never an unrelated entry token.
                located = next((d for d in parse_diagnostics(compiled.stderr)
                                if d["kind"] != "Warning" and d["filename"]), None)
                retry_source = b""
                if located:
                    target = (Path(work_project.root) / located["filename"]).resolve()
                    retry_source = next((f.content for f in work_project.files
                                         if Path(f.path).resolve() == target), b"")
            retry = settings_retry(compiled, retry_source) if retry_number == 0 else None
            if retry is None or retry["settings"][0] in initial_settings:
                break
            settings = initial_settings + tuple(retry["settings"])
        if record.status == "success" or record.reason == "solc_timeout":
            break
    if record.status != "success" and record.attempts and record.reason != "solc_timeout":
        record.reason = "slither_side_failure" if any_solc_success else "all_solc_candidates_failed"
        if any_solc_success:
            record.flags.append("Slither 侧失败")
    for f in unit.sources:
        current = (Path(work_project.root) / Path(f.path).relative_to(project.root)).read_bytes() if project is not None else path.read_bytes()
        verify_provenance(originals[f.path], current, maps[f.path])
    if project is not None:
        verify_project(project)
    return record


_DEPENDENCY_FAILURES = {"unresolved_package_import", "missing_relative_file", "standard_json_input",
                        "io_error", "closure_version_conflict"}


def _failure_measure(record):
    """Count blocking observations within one attempt; also retain eligibility for CP5."""
    from compile_repair.toolchain.solc import classify_constraints, classify_diagnostic
    if record.status == "success":
        return 0, set()
    categories, counts = set(), []
    for attempt in record.attempts:
        stage = attempt["stage"]
        if stage == "input_format":
            categories.add(record.reason)
            counts.append(1)
        elif stage == "project_assembly":
            issues = attempt["issues"]
            categories.update(r["category"] for r in issues)
            counts.append(len(issues))
        elif stage == "environment_plan":
            sources = [Path(f["path"]).read_bytes() for f in record.inputs if Path(f["path"]).is_file()]
            categories.add(classify_constraints(attempt["error_first_line"], sources)["category"])
            counts.append(1)
        elif attempt.get("solc"):
            result = attempt["solc"]
            if not result["returncode"] or result["timed_out"]:
                continue
            errors = [d for d in parse_diagnostics(result["stderr"]) if d["kind"] != "Warning"]
            categories.update(classify_diagnostic(d)["category"] for d in errors)
            if errors:
                counts.append(len(errors))
    return min(counts) if counts else None, categories


def repair_unit(unit, compilers, store, journal, order="ascending",
                compile_fn=compile_file, slither_fn=run_slither, project=None,
                project_compile_fn=compile_project, *, project_index=None, offline_index=None,
                dependency_policy="latest", environment_only=False):
    """Run environment selection, then deterministic project repairs on exclusive working copies."""
    prefix = "units/" + unit.unit_id + "/"
    tools = dict(order=order, compile_fn=compile_fn, slither_fn=slither_fn, project_compile_fn=project_compile_fn)
    record = _environment(unit, compilers, store, journal, project=project, prefix=prefix, **tools)
    if environment_only or record.status == "success" or not compilers or record.reason == "solc_timeout":
        store.write_json(prefix + "result.json", record)
        return record
    before, categories = _failure_measure(record)
    if not categories.intersection(_DEPENDENCY_FAILURES):
        store.write_json(prefix + "result.json", record)
        return record
    store.write_json(prefix + "environment_result.json", record)
    steps = []
    settings, wrapper = (), None
    original_project = project
    if record.reason == "standard_json_input":
        try:
            project, settings, wrapper = unpack_sources(unit.sources[0].content, store, prefix + "wrapper_sources")
        except (ValueError, UnicodeError, RecursionError) as exc:
            steps.append(dict(step=2, accepted=False, reason=str(exc)))
            store.write_json(prefix + "repair_steps.json", steps)
            store.write_json(prefix + "result.json", record)
            return record
        project_index = ProjectIndex(project.root, [Path(project.root) / n for n, _ in project.source_units])
        steps.append(dict(step=2, operation="unpack", wrapper=wrapper))
    elif project is None:
        # A file or snippet supplies one source. Only a caller-provided project
        # root or wrapper can authorize searching other local files.
        source_path = store.write_bytes(prefix + "standalone/input.sol", unit.sources[0].content)
        project_index = ProjectIndex(source_path.parent, (source_path,))
        project = resolve_project(project_index.root, source_path, index=project_index)
    index = project_index or ProjectIndex(project.root)
    originals = {}
    overlays, origins, existing_releases = {}, {}, {}
    attempts = 0
    accepted_prefix = None

    def select(result, step_record):
        nonlocal record, before, accepted_prefix
        step_record["accepted"] = True
        record, before = result, step_record["errors_after"]
        accepted_prefix = step_record["receipt"][:-len("result.json")]

    def try_project(step, candidate, maps, details, defer=False):
        nonlocal attempts
        attempts += 1
        branch = prefix + "round_{:03d}/".format(attempts)
        for f in candidate.files:
            name = Path(f.path).relative_to(candidate.root).as_posix()
            if name in maps:
                expected, patches = maps[name]
                current, evidence = apply_patches(expected, patches)
                verify_provenance(expected, current, evidence)
                if current != f.content:
                    raise ValueError("Proposed repair differs from provenance for " + name)
                if not Path(f.path).exists() and evidence.level == "additive":
                    continue
            else:
                expected = f.content
            digest = hashlib.sha256(expected).hexdigest()
            if originals.setdefault(f.path, digest) != digest or sha256(f.path) != digest:
                raise ValueError("Project source changed during repair: " + name)
        copy = materialize_project(candidate, store, branch + "input_project")
        next_unit = CompilationUnit(unit.unit_id, copy.files, unit.known_version, unit.regression)
        result = _environment(next_unit, compilers, store, journal, project=copy, prefix=branch,
                              initial_settings=settings, origins=maps, allow_override=False,
                              already_copied=True, **tools)
        after, _ = _failure_measure(result)
        accepted = result.status == "success" or (before is not None and after is not None and 0 < after < before
                   and result.reason not in ("slither_side_failure", "solc_timeout"))
        steps.append(dict(step=step, round=attempts, errors_before=before, errors_after=after, accepted=False,
                          status=result.status, reason=result.reason, receipt=branch + "result.json", **details))
        store.write_json(branch + "result.json", result)
        if accepted and not defer:
            select(result, steps[-1])
        return accepted, result

    needs_assembly = wrapper is not None or original_project is None
    while True:
        changed = False
        remaps, evidence = assembly_remappings(project, index)
        if remaps or needs_assembly:
            assembled = resolve_project(project.root, project.entry, project.remappings + remaps,
                                        index, project.additional_entries, overlays)
            accepted, result = try_project(2, assembled, origins, dict(remapping_evidence=evidence))
            needs_assembly = False
            if accepted:
                project, changed = assembled, True
            if result.status == "success" or result.reason == "solc_timeout":
                break
        else:
            steps.append(dict(step=2, accepted=False, remapping_evidence=evidence, reason="no_applicable_remapping"))
        if isinstance(offline_index, (str, Path)):
            offline_index = OfflineIndex(offline_index)
        if offline_index is not None and project.issues:
            evidence = []
            best, best_rank, timed_out = None, None, False
            try:
                base_plan = make_plan([f.content for f in project.files], compilers, unit.known_version, unit.regression, order)
                preferred = next(ordered_candidates(base_plan), None)
            except Unsupported:
                preferred = None
            for candidate, additions, releases in dependency_choices(
                    project, index, offline_index, compilers, overlays, dependency_policy, evidence, preferred,
                    existing_releases):
                maps = dict(origins)
                for name, data in additions.items():
                    if name not in origins:
                        maps[name] = (b"", (Patch(0, 0, b"", data, "dependency", attempts+1, "verified release file"),))
                manifest = {name: hashlib.sha256(data).hexdigest() for name, data in additions.items()}
                release_facts = {name: dict(fields, inferred=False) for name, fields in releases.items()}
                improves, result = try_project(3, candidate, maps, dict(releases=release_facts, files=manifest), defer=True)
                measurement = steps[-1]
                success = result.status == "success"
                measurement["d3_verified"] = success
                if result.reason == "solc_timeout":
                    timed_out = True
                    break
                if not improves:
                    continue
                distance = (abs(version_tuple(result.selected_version)[1] - version_tuple(preferred)[1])
                            if success and preferred and dependency_policy == "closest" else 0)
                # Compare actual D3 selections. A partial diagnostic improvement
                # never displaces a successful release combination.
                rank = (not success, distance if success else measurement["errors_after"])
                if best is None or rank < best_rank:
                    best_rank = rank
                    best = (result, measurement, candidate, maps, additions)
                if success and (dependency_policy != "closest" or distance == 0):
                    break
            if best is not None and not timed_out:
                result, measurement, project, origins, additions = best
                select(result, measurement)
                overlays.update(additions)
                existing_releases = measurement["releases"]
                changed = True
            steps.append(dict(step=3, operation="candidate_checks", policy=dependency_policy,
                              preferred_compiler=preferred, evidence=evidence))
            if record.status == "success" or timed_out:
                break
        else:
            steps.append(dict(step=3, accepted=False, reason="index_unavailable" if offline_index is None else "no_unresolved_imports"))
        edits, patches, choices = relative_repairs(project, index, compilers, overlays, attempts+1)
        if edits:
            maps = dict(origins)
            for name, extra in patches.items():
                original, previous = maps[name] if name in maps else ((Path(project.root) / name).read_bytes(), ())
                maps[name] = original, previous + extra
            working = dict(overlays)
            working.update(edits)
            candidate = resolve_project(project.root, project.entry, project.remappings, index, project.additional_entries, working)
            accepted, result = try_project(4, candidate, maps, dict(path_search=choices))
            if accepted:
                project, overlays, origins, changed = candidate, working, maps, True
            if result.status == "success" or result.reason == "solc_timeout":
                break
        else:
            steps.append(dict(step=4, accepted=False, path_search=choices, reason="no_unique_compatible_path"))
        if not changed:
            break
    if original_project:
        verify_project(original_project)
    if any(sha256(name) != digest for name, digest in originals.items()):
        raise ValueError("Original project changed during repair")
    if record.status == "success":
        for step in steps:
            if step.get("accepted"):
                for release in step.get("releases", {}).values():
                    release["inferred"] = release["tier"] == "T3"
        for name in ("graph.json", "nodes.json"):
            store.write_bytes(prefix + name, (store.path / (accepted_prefix + name)).read_bytes())
    store.write_json(prefix + "repair_steps.json", steps)
    store.write_json(prefix + "result.json", record)
    return record


def _code_commit(root):
    """Return the code checkout's HEAD, or None when git/HEAD is unavailable."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(root), stderr=subprocess.DEVNULL,
            universal_newlines=True).strip() or None
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def repair(paths, output, snippets=(), known_version=None, order="ascending", regression=None,
           *, compile_fn=compile_file, result_check=None, remappings=(), offline_index=None,
           dependency_policy="latest"):
    """Run the common production entry for files/snippets/project directories; return batch summary.

    Directories expand to one unit per .sol entry and its transitive closure.
    Empty projects, overlapping paths and missing files fail before output. Unrepaired inputs are valid records; unexpected failures stop/seal
    the partial batch. compile_fn can inject recorded compiler outcomes in
    tests. Missing git/HEAD is flagged and sealed as null, with file hashes kept.
    An optional result_check(record, output_path) may raise to stop and seal
    after a flushed per-input record; it never participates in version choice.
    No compiler download, global selection or LLM occurs.
    """
    if order not in ("ascending", "descending") or regression not in (None, "mando"):
        raise ValueError("Unsupported repair configuration")
    if known_version is not None:
        version_tuple(known_version)
    supplied = [(Path(p).resolve(), "file") for p in paths] + [(Path(p).resolve(), "snippet") for p in snippets]
    if not supplied:
        raise ValueError("At least one file or snippet is required")
    if len({str(p) for p, _ in supplied}) != len(supplied):
        raise ValueError("Duplicate input path")
    for remap in remappings:
        parse_remapping(remap)
    expanded = []
    for path, kind in supplied:
        if path.is_dir():
            if kind == "snippet" or regression is not None:
                raise ValueError("Project directories cannot be snippets or MANDO regression inputs")
            index = ProjectIndex(path)
            if not index.entries:
                raise ValueError("Project directory contains no .sol files")
            expanded.extend((p, "project", index) for p in index.entries)
        else:
            if not path.is_file() or kind == "file" and path.suffix != ".sol":
                raise ValueError("Expected an existing .sol file or explicit --snippet text file")
            expanded.append((path, kind, None))
    if len({str(p) for p, _, _ in expanded}) != len(expanded):
        raise ValueError("Overlapping input paths/project directories")
    store = ArtifactStore(output)
    root = Path(__file__).resolve().parents[1]
    commit = _code_commit(root)
    module = root / "compile_repair"
    code = list(module.glob("*.py")) + [p for folder in module.iterdir()
            if folder.is_dir() and folder.name not in ("artifacts", "tests", "docs")
            for p in folder.rglob("*.py")]
    implementation = {str(p.relative_to(root)): sha256(p) for p in sorted(code)}
    summary = {"schema": "cp1-repair-v1", "status": "running", "units": [], "llm_calls": 0,
               "cost_usd": 0.0, "order": order, "regression": regression, "known_version": known_version,
               "supplied": [{"path": str(p), "kind": k} for p, k in supplied]}
    if commit is None:
        summary["flags"] = ["code_commit_unavailable"]
    tools, snapshots = {}, {}
    with store.journal("invocations.jsonl") as journal, store.journal("manifest.jsonl") as manifest:
        try:
            if offline_index is None:
                default_index = root.parent / "corpora/compile-repair-npm-cp5-v1/index"
                offline_index = os.environ.get("COMPILE_REPAIR_DEPENDENCY_INDEX")
                if offline_index is None and (default_index / "seal.json").is_file():
                    offline_index = default_index
            if isinstance(offline_index, (str, Path)):
                offline_index = OfflineIndex(offline_index)
            if offline_index is not None:
                tools["dependency_index"] = offline_index.seal
                summary["dependency_policy"] = dependency_policy
            tools.update(check_profile("production"))
            compilers, frozen_rows, evidence = load_trusted_compilers()
            tools["compilers"] = {v: asdict(c) for v, c in compilers.items()}
            store.write_json("trust.json", evidence)
            for number, (path, kind, project_index) in enumerate(expanded, 1):
                project = (resolve_project(project_index.root, path, remappings, project_index)
                           if project_index is not None else None)
                raw = path.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                sources = project.files if project is not None else (SourceFile(str(path), digest, raw, kind),)
                for source in sources:
                    previous = snapshots.setdefault(Path(source.path), source.sha256)
                    if previous != source.sha256:
                        raise ValueError("Input changed between compilation units")
                metadata_version, metadata = mando_known_version(raw, frozen_rows) if regression == "mando" else (None, [])
                if known_version and metadata_version and known_version != metadata_version:
                    raise ValueError("Explicit known version conflicts with validated regression metadata")
                unit = CompilationUnit("input_{:04d}".format(number), sources, known_version or metadata_version, regression)
                store.write_json("units/" + unit.unit_id + "/input_record.json", {
                    "path": str(path), "sha256": digest, "kind": kind,
                    "known_version": unit.known_version, "metadata": metadata})
                record = repair_unit(unit, compilers, store, journal, order,
                                     compile_fn=compile_fn, project=project, project_index=project_index,
                                     offline_index=offline_index, dependency_policy=dependency_policy)
                emit(manifest, record)
                summary["units"].append({"unit_id": unit.unit_id, "input_sha256": digest,
                    "status": record.status, "reason": record.reason, "selected_version": record.selected_version})
                print("CP1 {}/{}: {} {}".format(number, len(expanded), record.status,
                                               record.selected_version or record.reason), flush=True)
                if result_check is not None:
                    result_check(record, store.path)
            summary["status"] = "complete" if all(x["status"] == "success" for x in summary["units"]) else "unrepaired"
        except Exception as exc:
            summary.update(status="stopped", exception_type=type(exc).__name__, error=str(exc))
        changed = [str(p) for p, digest in snapshots.items() if sha256(p) != digest]
        if changed:
            summary.update(status="stopped", exception_type="InputIntegrityError", changed_inputs=changed)
    store.write_json("summary.json", summary)
    store.seal(tools, commit, implementation)
    return summary
